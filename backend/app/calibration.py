"""Versioned, scene-group split conformal intervals for independently reviewed new scenes.

Usage: python -m app.calibration cohort.json
Never calibrate on the frozen train/validation/test benchmark. No fitting of prediction models.
"""
import argparse
import hashlib
import json
import math
from pathlib import Path
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from .db import Session, Photo, Estimate, Run, Matchup, ModelVersion, Calibration, initialize

class CalibrationRow(BaseModel):
    model_config = ConfigDict(extra='forbid')
    estimate_id: str
    scene_group: str = Field(min_length=1, max_length=200)
    reference: float = Field(gt=0, allow_inf_nan=False)
    granule_id: str = Field(min_length=1)
    reference_source: str = Field(min_length=1)
    reference_sha256: str = Field(pattern=r'^[a-f0-9]{64}$')

class Cohort(BaseModel):
    model_config = ConfigDict(extra='forbid')
    model_id: str
    coverage: float = Field(default=.9, ge=.8, le=.99)
    domain: str = Field(min_length=1, max_length=200)
    independence_review: str = Field(min_length=40, max_length=10000)
    grouping_protocol: str = Field(min_length=40, max_length=10000)
    reference_kind: Literal['quality_masked_satellite_geometric_mean']
    rows: list[CalibrationRow] = Field(min_length=20, max_length=10000)

def radius(scores, coverage):
    ordered = sorted(scores)
    rank = math.ceil((len(ordered)+1)*coverage)
    if not ordered or rank > len(ordered): raise ValueError('Too few independent groups for a finite interval at this coverage')
    return ordered[rank-1]

def fit(cohort, session_factory=Session):
    data = cohort.model_dump(mode='json')
    code_sha = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    cid = hashlib.sha256(json.dumps({'cohort': data, 'method_sha256': code_sha}, sort_keys=True).encode()).hexdigest()
    with session_factory.begin() as s:
        prior = s.get(Calibration, cid)
        if prior: return cid
        model = s.get(ModelVersion, cohort.model_id)
        if not model: raise ValueError('Unknown model version')
        known = s.execute(select(Estimate, Photo).join(Photo).where(Estimate.split.is_not(None))).all()
        known_ids = {p.id for e,p in known}; known_hashes = {p.image_sha256 for e,p in known if p.image_sha256}
        known_groups = {e.scene_group for e,p in known if e.scene_group}
        known_granules = {m.data.get('granule_id') for m in s.scalars(select(Matchup))}
        groups, photo_ids, hashes, records = {}, set(), set(), []
        granule_groups = {}
        for row in cohort.rows:
            e = s.get(Estimate, row.estimate_id)
            if not e or e.model_id != cohort.model_id or e.split is not None or e.role != 'unseen_inference':
                raise ValueError('Calibration requires unseen estimates from the exact frozen model version')
            if s.get(Run, e.run_id).status != 'complete': raise ValueError('Inference run is not complete')
            p = s.get(Photo, e.photo_id)
            if p.id in known_ids or p.image_sha256 in known_hashes or row.scene_group in known_groups or row.granule_id in known_granules:
                raise ValueError('Calibration overlaps a previously exposed photo, decoded image, scene group, or satellite granule')
            if not p.image_sha256 or p.id in photo_ids or p.image_sha256 in hashes:
                raise ValueError('Missing source hash or duplicate calibration image')
            meta = p.metadata_json
            if (meta.get('scene_group') != row.scene_group or meta.get('calibration_domain') != cohort.domain
                or not meta.get('independence_review')):
                raise ValueError('Photo needs matching scene_group, calibration_domain, and independence_review in its catalog metadata')
            if row.granule_id in granule_groups and granule_groups[row.granule_id] != row.scene_group:
                raise ValueError('Shared satellite granules must belong to the same scene group')
            granule_groups[row.granule_id] = row.scene_group
            score = abs(math.log10(e.value)-math.log10(row.reference))
            groups[row.scene_group] = max(groups.get(row.scene_group, 0), score)
            photo_ids.add(p.id); hashes.add(p.image_sha256)
            records.append({**row.model_dump(), 'photo_id': p.id, 'image_sha256': p.image_sha256, 'prediction': e.value})
        if len(groups) < 20: raise ValueError('At least 20 independent scene groups are required')
        q = radius(list(groups.values()), cohort.coverage)
        if not math.isfinite(10**q): raise ValueError('Interval radius is not finite')
        s.add(Calibration(id=cid, model_id=cohort.model_id, coverage=cohort.coverage, log_radius=q,
            manifest={**data, 'rows': records, 'group_count': len(groups), 'photo_count': len(records),
                'method': 'split_conformal_log10_scene_max', 'group_scores': groups,
                'code_sha256': code_sha,
                'validation_status': 'calibrated; independent coverage evaluation pending',
                'assumption': 'Calibration and future scene groups are exchangeable within the reviewed domain',
                'limitation': 'Nominal scene-group marginal coverage against satellite aggregates; not a per-photo correctness probability or field-measurement accuracy.'}))
    return cid

def interval(s, estimate, photo):
    if estimate.split is not None or estimate.role != 'unseen_inference':
        return {'status': 'unavailable', 'reason': 'This saved evaluation cohort has no independently calibrated prediction interval.'}
    calibrations = s.scalars(select(Calibration).where(Calibration.model_id == estimate.model_id)
                            .order_by(Calibration.created_at.desc(), Calibration.id)).all()
    if not calibrations: return {'status': 'unavailable', 'reason': 'Fresh independent scene groups are needed to calibrate this model.'}
    meta = photo.metadata_json
    group = meta.get('scene_group') or estimate.scene_group
    if not group or not meta.get('independence_review'):
        return {'status': 'unavailable', 'reason': 'Scene grouping and independence review are required.'}
    if any(photo.id == r['photo_id'] or photo.image_sha256 == r['image_sha256'] or group == r['scene_group']
           for c in calibrations for r in c.manifest['rows']):
        return {'status': 'unavailable', 'reason': 'This image or scene was used for calibration.'}
    # All versions remain visible; never select one based on the reference/error of this photo.
    for c in calibrations:
        if meta.get('calibration_domain') != c.manifest['domain']: continue
        exposed = s.scalar(select(Estimate.id).join(Photo).where(Estimate.split.is_not(None),
            (Photo.image_sha256 == photo.image_sha256) | (Estimate.scene_group == group)).limit(1))
        if exposed: return {'status': 'unavailable', 'reason': 'Image or scene overlaps the frozen benchmark.'}
        low, high = estimate.value / 10**c.log_radius, estimate.value * 10**c.log_radius
        if not math.isfinite(high) or low <= 0: return {'status': 'unavailable', 'reason': 'Interval exceeds supported numeric range.'}
        return {'status': 'available', 'lower': low, 'upper': high, 'nominal_coverage': c.coverage,
                'calibration_id': c.id, 'method': c.manifest['method'], 'group_count': c.manifest['group_count'],
                'validation_status': c.manifest['validation_status'], 'limitation': c.manifest['limitation']}
    return {'status': 'unavailable', 'reason': 'No calibration matches this photo’s reviewed domain.'}

if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__); p.add_argument('cohort_json'); args = p.parse_args()
    initialize()
    print(json.dumps({'calibration_id': fit(Cohort.model_validate_json(Path(args.cohort_json).read_text()))}))
