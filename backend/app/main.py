"""Read API for the dashboard; operator-authenticated durable inference requests."""
import os
import secrets
import math
from contextlib import asynccontextmanager
from datetime import date, timedelta
from typing import Literal
from fastapi import FastAPI, HTTPException, Query, Header, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, RedirectResponse, JSONResponse
from pathlib import Path
from .db import WORKSPACE
from pydantic import BaseModel, Field
from sqlalchemy import select, func, exists
from sqlalchemy.exc import OperationalError
from .db import Session, initialize, Photo, Estimate, ModelVersion, Matchup, Run, Job, InputAsset
from .queue import enqueue
from .calibration import interval
from .confidence import saved_confidence

import json
NASA_METADATA = json.loads((Path(__file__).with_name('photo-metadata.json')).read_text())

def display_metadata(photo_id, metadata):
    result = dict(metadata or {})
    if result.get('focal_length') is None:
        result.update(NASA_METADATA.get(photo_id, {}))
    return result

LIMITATION = 'Research estimates of satellite-derived photo averages. Not field measurements or validated pixel-level retrievals.'

def model_json(m):
    manifest = dict(m.manifest)
    if isinstance(manifest.get('confidence_calibration'), dict):
        manifest['confidence_calibration'] = {k:v for k,v in manifest['confidence_calibration'].items() if k != 'eligible_estimates'}
    return {'id': m.id, 'target': m.target, 'name': m.name, 'units': m.units,
            'serving_enabled': m.manifest.get('serving_enabled', True), **manifest}

def photo_json(p):
    return {k: getattr(p, k) for k in ['id', 'captured_at', 'latitude', 'longitude', 'mission', 'thumbnail_url', 'image_url', 'original_url']} | {'metadata': display_metadata(p.id, p.metadata_json)}

def job_json(j):
    return {k: getattr(j, k) for k in ['id', 'photo_id', 'run_id', 'model_ids', 'status', 'attempts', 'created_at', 'updated_at', 'error']}

def operator(authorization: str | None = Header(default=None)):
    key = os.environ.get('OPERATOR_API_KEY')
    if not key: raise HTTPException(503, 'Operator writes are disabled until an operator key is configured')
    if not authorization or not secrets.compare_digest(authorization, f'Bearer {key}'):
        raise HTTPException(401, 'Operator authentication required')

class JobRequest(BaseModel):
    photo_id: str = Field(min_length=1, max_length=100)
    model_ids: list[str] = Field(min_length=1, max_length=2)

@asynccontextmanager
async def lifespan(app):
    if os.environ.get('DB_AUTO_CREATE', '0' if os.environ.get('VERCEL') else '1') == '1':
        initialize()
    yield

app = FastAPI(title='Astronaut Photography Prediction & Analysis API', version='1.0.0', lifespan=lifespan, docs_url='/api/docs', openapi_url='/api/openapi.json')

@app.exception_handler(OperationalError)
async def database_unavailable(request, exc):
    return JSONResponse(status_code=503, content={'detail': 'The research database is temporarily unavailable. Please try again later.'},
                        headers={'Retry-After': '60'})

app.add_middleware(CORSMiddleware,
    allow_origins=[x.strip() for x in os.environ.get('ALLOWED_ORIGINS', 'http://localhost:5173,http://127.0.0.1:5173').split(',') if x.strip()],
    allow_methods=['GET', 'POST'], allow_headers=['Authorization', 'Content-Type', 'Idempotency-Key'])

@app.get('/api/health')
def health():
    with Session() as s:
        s.execute(select(Photo.id).limit(1))
    return {'status': 'ok', 'schema_version': 3, 'storage': 'postgresql' if Session.kw['bind'].dialect.name == 'postgresql' else 'sqlite',
            'inference_enabled': bool(os.environ.get('OPERATOR_API_KEY')) and os.environ.get('INFERENCE_ENABLED', '1') == '1'}

@app.get('/api/summary')
def summary():
    with Session() as s:
        return {'photos': s.scalar(select(func.count()).select_from(Photo)),
            'estimates': s.scalar(select(func.count()).select_from(Estimate)),
            'matchups': s.scalar(select(func.count()).select_from(Matchup)),
            'runs': s.scalar(select(func.count()).select_from(Run)),
            'missions': s.scalars(select(Photo.mission).distinct().order_by(Photo.mission)).all(),
            'samples': [r.provenance['sample'] for r in s.scalars(select(Run)).all() if 'sample' in r.provenance],
            'limitations': LIMITATION}

@app.get('/api/photos')
def photos(q: str = Query('', max_length=100), mission: str | None = None,
           photo_ids: str | None = Query(None, max_length=2000),
           cohort: Literal['mediterranean', 'legacy'] | None = None,
           split: Literal['train', 'validation', 'test'] | None = None,
           prediction: bool | None = None, satellite: bool | None = None,
           start: date | None = None, end: date | None = None,
           latitude: float | None = Query(None, ge=-90, le=90),
           longitude: float | None = Query(None, ge=-180, le=180),
           radius_km: float | None = Query(None, gt=0, le=20016),
           south: float | None = Query(None, ge=-90, le=90), north: float | None = Query(None, ge=-90, le=90),
           west: float | None = Query(None, ge=-180, le=180), east: float | None = Query(None, ge=-180, le=180),
           sort: Literal['newest', 'oldest'] = 'newest', offset: int = Query(0, ge=0), limit: int = Query(30, ge=1, le=100)):
    if start and end and start > end: raise HTTPException(422, 'Start date must precede end date')
    if south is not None and north is not None and south > north: raise HTTPException(422, 'South must not exceed north')
    radius_fields = [latitude, longitude, radius_km]
    if any(v is not None for v in radius_fields) and not all(v is not None for v in radius_fields):
        raise HTTPException(422, 'Latitude, longitude and radius_km must be supplied together')
    query = select(Photo)
    if radius_km is not None:
        # Great-circle spherical cap, evaluated before count and pagination on both databases.
        rad = math.pi / 180
        dot = (func.sin(Photo.latitude * rad) * math.sin(latitude * rad) +
               func.cos(Photo.latitude * rad) * math.cos(latitude * rad) * func.cos((Photo.longitude - longitude) * rad))
        query = query.where(Photo.latitude.is_not(None), Photo.longitude.is_not(None),
                            dot >= math.cos(min(math.pi, radius_km / 6371.0088)))
    if photo_ids:
        query = query.where(Photo.id.in_(photo_ids.split(',')))
    if q: query = query.where(Photo.id.contains(q.upper(), autoescape=True))
    if mission: query = query.where(Photo.mission == mission)
    if cohort:
        kind = 'mediterranean_import' if cohort == 'mediterranean' else 'benchmark_import'
        query = query.where(exists(select(Estimate.id).join(Run).where(Estimate.photo_id == Photo.id, Run.kind == kind)))
    if start: query = query.where(Photo.captured_at >= start.isoformat())
    if end: query = query.where(Photo.captured_at < (end + timedelta(days=1)).isoformat())
    if south is not None: query = query.where(Photo.latitude >= south)
    if north is not None: query = query.where(Photo.latitude <= north)
    if west is not None and east is not None and west > east:
        query = query.where((Photo.longitude >= west) | (Photo.longitude <= east))
    else:
        if west is not None: query = query.where(Photo.longitude >= west)
        if east is not None: query = query.where(Photo.longitude <= east)
    has_prediction = exists(select(Estimate.id).where(Estimate.photo_id == Photo.id))
    has_match = exists(select(Matchup.id).where(Matchup.photo_id == Photo.id))
    if prediction is not None: query = query.where(has_prediction if prediction else ~has_prediction)
    if satellite is not None: query = query.where(has_match if satellite else ~has_match)
    if split: query = query.where(exists(select(Estimate.id).where(Estimate.photo_id == Photo.id, Estimate.split == split)))
    with Session() as s:
        total = s.scalar(select(func.count()).select_from(query.subquery()))
        records = s.scalars(query.order_by(Photo.captured_at.desc() if sort == 'newest' else Photo.captured_at, Photo.id).offset(offset).limit(limit)).all()
        return {'items': [photo_json(p) for p in records], 'total': total, 'offset': offset, 'limit': limit}

@app.get('/api/photos/{photo_id}')
def detail(photo_id: str):
    with Session() as s:
        photo = s.get(Photo, photo_id)
        if not photo: raise HTTPException(404, 'Photo not found')
        records = s.scalars(select(Estimate).join(Run).where(Estimate.photo_id == photo_id, Run.status == 'complete')
            .order_by(Run.created_at.desc(), Estimate.id)).all()
        latest = {}
        for p in records:
            if p.target in latest: continue
            model = s.get(ModelVersion, p.model_id)
            match = s.get(Matchup, p.matchup_id) if p.matchup_id else None
            reference = match.data['targets'][p.target]['value'] if match else None
            latest[p.target] = {'value': p.value, 'units': model.units, 'model': model_json(model),
                'run_id': p.run_id, 'created_at': p.created_at, 'role': p.role, 'split': p.split,
                'scene_group': p.scene_group, 'evidence': p.evidence, 'confidence': saved_confidence(s, p, photo),
                'prediction_interval': interval(s, p, photo),
                'satellite': ({'id': match.id, 'dataset_sha256': match.dataset_sha256, **match.data} if match else None),
                'difference': p.value - reference if reference is not None else None}
        result = photo_json(photo)
        asset_id = next((p['evidence'].get('input_asset_id') for p in latest.values() if p['evidence'].get('input_asset_id')), None)
        asset = s.get(InputAsset, asset_id) if asset_id else None
        if asset:
            result['metadata'] = display_metadata(photo_id, {**photo.metadata_json, **asset.provenance['metadata']})
        result['preview'] = {'kind': 'registered_crop' if asset else 'canonical_image', 'asset_id': asset_id,
            'available': bool(asset and _asset_path(asset)),
            'caption': ('Registered model-input crop' if asset and _asset_path(asset) else
                        'NASA original preview; predictions refer to the recorded crop' if asset else 'Canonical image')}
        return {**result, 'predictions': latest, 'history_count': len(records),
            'availability': {'calibrated_confidence': any(p['prediction_interval']['status'] == 'available' or (p.get('confidence') or {}).get('status') == 'available' for p in latest.values()), 'segmentation': bool(latest_annotations(s, photo_id)), 'water_clarity': False, 'usefulness_score': False},
            'limitations': LIMITATION}

def _asset_path(asset):
    path = Path(asset.local_path).resolve() if asset.local_path else None
    return path if path and path.is_relative_to(WORKSPACE) and path.is_file() and path.suffix.lower() in {'.png', '.jpg', '.jpeg'} else None

@app.get('/api/input-assets/{asset_id}/image')
def input_image(asset_id: str):
    with Session() as s:
        asset = s.get(InputAsset, asset_id)
        if not asset: raise HTTPException(404, 'Input asset not found')
        path = _asset_path(asset)
        if not path: raise HTTPException(404, 'Registered crop is not hosted on this API')
        return FileResponse(path, headers={'Cache-Control': 'public, max-age=3600'})

@app.get('/api/models')
def models():
    with Session() as s:
        return [model_json(m) for m in s.scalars(select(ModelVersion).order_by(ModelVersion.target)).all()]

@app.get('/api/runs')
def runs():
    with Session() as s:
        return [{k: getattr(r, k) for k in ['id', 'kind', 'status', 'created_at', 'completed_at', 'provenance']}
            for r in s.scalars(select(Run).order_by(Run.created_at.desc()).limit(100)).all()]

@app.get('/api/jobs')
def jobs():
    with Session() as s:
        return [job_json(j) for j in s.scalars(select(Job).order_by(Job.created_at.desc()).limit(50)).all()]

@app.get('/api/jobs/{job_id}')
def job_detail(job_id: str):
    with Session() as s:
        job = s.get(Job, job_id)
        if not job: raise HTTPException(404, 'Job not found')
        return job_json(job)

@app.post('/api/jobs', status_code=202, dependencies=[Depends(operator)])
def create_job(body: JobRequest, idempotency_key: str = Header(min_length=8, max_length=128)):
    if os.environ.get('INFERENCE_ENABLED', '1') != '1':
        raise HTTPException(503, 'Inference is disabled until a compatible worker is running')
    try:
        return job_json(enqueue(body.photo_id, body.model_ids, idempotency_key))
    except LookupError as e: raise HTTPException(404, str(e)) from e
    except ValueError as e: raise HTTPException(409, str(e)) from e

@app.get('/api/photos/{photo_id}/thumbnail')
def thumbnail(photo_id: str):
    with Session() as s:
        photo = s.get(Photo, photo_id)
        if not photo: raise HTTPException(404, 'Photo not found')
        path = Path(photo.local_image).resolve() if photo.local_image else None
        if path and path.is_relative_to(WORKSPACE) and path.is_file() and path.suffix.lower() in {'.png', '.jpg', '.jpeg'}:
            return FileResponse(path, headers={'Cache-Control': 'public, max-age=3600'})
        return RedirectResponse(photo.thumbnail_url)

@app.get('/api/photos/{photo_id}/history')
def history(photo_id: str, offset: int = Query(0, ge=0), limit: int = Query(50, ge=1, le=100)):
    with Session() as s:
        if not s.get(Photo, photo_id): raise HTTPException(404, 'Photo not found')
        records = s.scalars(select(Estimate).where(Estimate.photo_id == photo_id)
            .order_by(Estimate.created_at.desc(), Estimate.id).offset(offset).limit(limit)).all()
        return [{k: getattr(p, k) for k in ['id', 'target', 'value', 'model_id', 'run_id', 'matchup_id', 'role', 'split', 'scene_group', 'created_at', 'evidence']} for p in records]

# Spatial artifacts are stored in the database so Vercel can serve them independently of the worker.
import base64
import json
import zlib
from fastapi.responses import Response
from sqlalchemy.exc import IntegrityError
from .db import Overlay, AnnotationRevision
from .annotations import AnnotationRequest, latest as latest_annotations, serialize as annotation_json

def overlay_json(o):
    return {k: getattr(o, k) for k in ['id', 'photo_id', 'target', 'image_sha256', 'model_version', 'created_at']} | o.manifest

@app.get('/api/photos/{photo_id}/overlays')
def photo_overlays(photo_id: str):
    with Session() as s:
        p = s.get(Photo, photo_id)
        if not p: raise HTTPException(404, 'Photo not found')
        records = s.scalars(select(Overlay).where(Overlay.photo_id == photo_id, Overlay.image_sha256 == p.image_sha256)
            .order_by(Overlay.created_at.desc(), Overlay.id)).all()
        return {'items': [overlay_json(o) for o in records], 'image_sha256': p.image_sha256,
                'annotations': annotation_json(latest_annotations(s, photo_id))}

@app.get('/api/overlays/{overlay_id}/{asset}')
def overlay_asset(overlay_id: str, asset: Literal['image.png', 'source.png', 'values']):
    with Session() as s:
        o = s.get(Overlay, overlay_id)
        if not o: raise HTTPException(404, 'Overlay not found')
        if asset == 'values':
            grid = o.payload.get('log10_grid')
            if grid is None: grid = json.loads(zlib.decompress(base64.b64decode(o.payload['grid_zlib_base64'])))
            return {**overlay_json(o), 'log10_grid': grid}
        key = 'png_base64' if asset == 'image.png' else 'source_png_base64'
        return Response(base64.b64decode(o.payload[key]), media_type='image/png',
            headers={'Cache-Control': 'public, max-age=31536000, immutable'})

@app.get('/api/photos/{photo_id}/annotations')
def annotation_history(photo_id: str):
    with Session() as s:
        if not s.get(Photo, photo_id): raise HTTPException(404, 'Photo not found')
        rows = s.scalars(select(AnnotationRevision).where(AnnotationRevision.photo_id == photo_id)
                         .order_by(AnnotationRevision.revision.desc()).limit(100)).all()
        return {'items': [annotation_json(row) for row in rows]}

@app.post('/api/photos/{photo_id}/annotations', dependencies=[Depends(operator)])
def save_annotations(photo_id: str, body: AnnotationRequest):
    try:
        with Session.begin() as s:
            photo = s.get(Photo, photo_id)
            if not photo: raise HTTPException(404, 'Photo not found')
            if photo.image_sha256 != body.image_sha256: raise HTTPException(409, 'Source image changed; reload before reviewing')
            regions = [r.model_dump(mode='json') for r in body.regions]
            prior = s.get(AnnotationRevision, body.id)
            if prior:
                if (prior.photo_id != photo_id or prior.revision != body.base_revision+1 or prior.regions != regions
                    or prior.reviewer != body.reviewer or prior.image_sha256 != body.image_sha256):
                    raise HTTPException(409, 'Revision ID already used for different content')
                return annotation_json(prior)
            previous = latest_annotations(s, photo_id)
            if (previous.revision if previous else 0) != body.base_revision:
                raise HTTPException(409, 'Another review was saved. Export your draft, then reload to reconcile.')
            row = AnnotationRevision(id=body.id, photo_id=photo_id, revision=body.base_revision+1,
                image_sha256=body.image_sha256, reviewer=body.reviewer.strip(), regions=regions)
            if not row.reviewer: raise HTTPException(422, 'Reviewer name is required')
            s.add(row); s.flush()
            return annotation_json(row)
    except IntegrityError as exc:
        raise HTTPException(409, 'Concurrent review saved. Reload before saving again.') from exc

@app.get('/api/calibrations')
def calibrations():
    from .db import Calibration
    with Session() as s:
        return [{k: getattr(c,k) for k in ['id','model_id','created_at','coverage','log_radius','manifest']}
                for c in s.scalars(select(Calibration).order_by(Calibration.created_at.desc()))]

@app.get('/api/photos/{photo_id}/nasa-metadata')
def source_photo_metadata(photo_id: str):
    from .nasa_metadata import nasa_metadata, ID
    if not ID.fullmatch(photo_id): raise HTTPException(422, 'Invalid NASA photo ID')
    return NASA_METADATA.get(photo_id) or nasa_metadata(photo_id)
