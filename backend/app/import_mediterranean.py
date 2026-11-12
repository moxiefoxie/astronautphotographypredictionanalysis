"""Import verified saved outputs and source snapshots, without fitting or running models.

Run: PYTHONPATH=backend .venv/bin/python -m app.import_mediterranean
The import is atomic and content-addressed. Existing canonical photos remain intact.
"""
import hashlib
import json
import math
from pathlib import Path
from sqlalchemy import select
from .db import (WORKSPACE, Session, initialize, Photo, ModelVersion, Run, Estimate,
                 Matchup, CatalogSnapshot, InputAsset, utcnow)
from .import_benchmark import rows, sha, number, TARGETS
from .catalog import ID

SOURCE = 'supabase:zwdkkwbxlsrlqsqjfdht/public.astronaut_photos'
LIMITS = ('Satellite-derived registered-region averages; no in-situ or independent geographic '
          'validation. Orbital locations are estimates. Pixel retrievals are not validated.')


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, allow_nan=False).encode()).hexdigest()


def metadata(row):
    numeric = ['cloud_percent', 'sun_elevation', 'sun_azimuth', 'focal_length',
               'water_fraction', 'ocean_sea_fraction', 'land_fraction', 'hardware_fraction',
               'clear_water_fraction', 'original_width_px', 'original_height_px',
               'earthmatch_inlier_count']
    result = {k: number(row.get(k)) for k in numeric}
    if result['cloud_percent'] is None and number(row.get('cloud_fraction')) is not None:
        result['cloud_percent'] = number(row['cloud_fraction']) * 100
    if result['sun_elevation'] is None:
        result['sun_elevation'] = number(row.get('solar_elevation_at_center_deg'))
    for key in ['location_source', 'timelapse_id', 'capture_time_source', 'mask_method',
                'processing_signature', 'processed_at', 'reference_status']:
        result[key] = row.get(key) or None
    for key in ['corners_latlon', 'crop_corners_original_px', 'named_water_features', 'water_features']:
        val = row.get(key)
        result[key] = json.loads(val) if isinstance(val, str) and val else val or None
    result['catalog_source'] = SOURCE
    result['catalog_mode'] = 'versioned export'
    result['input_contract'] = 'mediterranean-20261102'
    return result


def make_photo(row, meta):
    pid = row.get('image_id') or row['photo_id']
    match = ID.fullmatch(pid)
    if not match: raise ValueError(f'Invalid photo ID: {pid}')
    mission, roll, frame = match.groups()
    lat = number(row.get('latitude', row.get('center_lat')))
    lon = number(row.get('longitude', row.get('center_lon')))
    if lat is not None and not -90 <= lat <= 90: raise ValueError('Invalid latitude')
    if lon is not None and not -180 <= lon <= 180: raise ValueError('Invalid longitude')
    from datetime import datetime, timezone
    captured = row.get('photo_datetime') or row.get('captured_at')
    if captured:
        dt = datetime.fromisoformat(captured.replace('Z', '+00:00'))
        if dt.utcoffset() is None: raise ValueError('Capture time requires timezone')
        captured = dt.astimezone(timezone.utc).isoformat()
    return Photo(id=pid, mission=mission, captured_at=captured or None, latitude=lat, longitude=lon,
        thumbnail_url=f'https://eol.jsc.nasa.gov/DatabaseImages/ESC/small/{mission}/{pid}.JPG',
        image_url=f'https://eol.jsc.nasa.gov/DatabaseImages/ESC/large/{mission}/{pid}.JPG',
        original_url=f'https://eol.jsc.nasa.gov/SearchPhotos/photo.pl?mission={mission}&roll={roll}&frame={frame}',
        metadata_json=meta, local_image=row.get('local_image') or None,
        image_sha256=row.get('image_sha256') or None)


def import_mediterranean(session_factory=Session, root=None):
    root = Path(root or WORKSPACE / 'mediterranean_20261102')
    paths = ['raw/photos.csv', 'results/manifest.csv', 'results/selection.json',
             'results/family_comparison.csv', 'results/training_contract.json',
             'all_test/results/manifest.csv', 'all_test/results/selected_full_test_predictions.csv',
             'all_test/results/inference_contract.json', 'all_test/results/verification.json']
    hashes = {p: sha(root/p) for p in paths}
    verification = json.loads((root/paths[-1]).read_text())
    if verification['status'] != 'passed': raise ValueError('Full-test verification has not passed')
    selection = json.loads((root/'results/selection.json').read_text())['selected']
    contract = json.loads((root/'all_test/results/inference_contract.json').read_text())
    if contract['benchmark_training_contract_sha256'] != hashes['results/training_contract.json']:
        raise ValueError('Training contract changed after inference')
    if contract['input_manifest_sha256'] != hashes['all_test/results/manifest.csv']:
        raise ValueError('Inference input manifest changed')
    training = json.loads((root/'results/training_contract.json').read_text())
    if training['manifest_sha256'] != hashes['results/manifest.csv']:
        raise ValueError('Benchmark manifest changed')
    source_rows = {r['photo_id']: r for r in rows(root/'raw/photos.csv')}
    benchmark = {r['image_id']: r for r in rows(root/'results/manifest.csv') if r['split'] == 'test'}
    inputs = {r['image_id']: r for r in rows(root/'all_test/results/manifest.csv')}
    inputs.update(benchmark)
    predictions = rows(root/'all_test/results/selected_full_test_predictions.csv')
    ids = [r['photo_id'] for r in predictions]
    if len(set(ids)) != len(ids) or len(ids) != verification['test_photos']:
        raise ValueError('Duplicate or incomplete prediction export')
    if set(inputs) != set(ids) or not set(ids).issubset(source_rows):
        raise ValueError('Prediction / catalog / input mismatch')
    metrics = rows(root/'results/family_comparison.csv')
    models = {}
    for target, selected in selection.items():
        checkpoint = f'runs/{selected["recipe"]}/checkpoints/{selected["candidate"]}.pt'
        artifacts = {p: sha(root/p) for p in [checkpoint, 'checkpoints/metadata_preprocessor.joblib']}
        metric = next(r for r in metrics if r['target'] == target and r['recipe'] == selected['recipe']
                      and r['candidate'] == selected['candidate'] and r['cohort'] == 'all')
        mid = 'med-' + target + '-' + digest({'artifacts': artifacts, 'training': training, 'selection': selected})[:24]
        models[target] = (mid, {'selection': selected['candidate'], 'recipe': selected['recipe'],
            'artifact_sha256': artifacts, 'training_contract_sha256': hashes['results/training_contract.json'],
            'benchmark': 'mediterranean-20261102', 'selection_criterion': 'validation group-balanced log10 MAE',
            'test_metrics': {k: number(metric[k]) for k in ['n', 'groups', 'group_log_mae', 'median_error_factor', 'within_2x_pct']},
            'serving_enabled': False, 'serving_reason': 'Saved predictions available; APPA worker adapter has not been validated.',
            'limitations': LIMITS})
    run_id = 'med-test-' + digest({'hashes': hashes, 'models': models, 'import_contract': 1})[:24]
    with session_factory.begin() as s:
        if s.get(Run, run_id): return {'run_id': run_id, 'imported': False, 'photos': len(ids)}
        s.add(Run(id=run_id, kind='mediterranean_import', status='complete', completed_at=utcnow(),
            provenance={'source': SOURCE, 'source_mode': 'versioned export', 'sources': hashes,
                        'verification': verification, 'split_counts': {'test': len(ids)}, 'limitations': LIMITS}))
        for target, (mid, manifest) in models.items():
            if not s.get(ModelVersion, mid):
                s.add(ModelVersion(id=mid, target=target, name=f'{manifest["recipe"]}_{manifest["selection"]}',
                                   units=TARGETS[target], manifest=manifest))
        s.flush()
        photos = {p.id: p for p in s.scalars(select(Photo))}
        snapshot_ids = set(s.scalars(select(CatalogSnapshot.id)))
        asset_ids = set(s.scalars(select(InputAsset.id)))
        for pred in predictions:
            pid = pred['photo_id']; row = inputs[pid]; source = source_rows[pid]
            eligible = pred['benchmark_eligible'] == 'True'
            if eligible != (pid in benchmark): raise ValueError('Reference eligibility mismatch')
            if row['split'] != 'test' or source['split'] != 'test': raise ValueError('Test split mismatch')
            meta = metadata(row) | {'reference_status': pred['reference_status'], 'benchmark_eligible': eligible}
            if pid not in photos:
                photo = make_photo(row, meta); s.add(photo); photos[pid] = photo
            sid = digest({'source': SOURCE, 'row': source})
            s.flush()
            if sid not in snapshot_ids:
                s.add(CatalogSnapshot(id=sid, photo_id=pid, source=SOURCE, data=source)); snapshot_ids.add(sid)
            aid = digest({'photo': pid, 'image_sha256': row['image_sha256'], 'crop': meta['crop_corners_original_px']})
            if aid not in asset_ids:
                s.add(InputAsset(id=aid, photo_id=pid, image_sha256=row['image_sha256'],
                    local_path=row['local_image'], kind='registered_crop',
                    provenance={'catalog_snapshot_id': sid, 'metadata': meta, 'source_manifest_sha256': hashes['results/manifest.csv'] if eligible else hashes['all_test/results/manifest.csv']}))
                asset_ids.add(aid)
            match_id = None
            if eligible:
                match_id = f'{run_id}-{pid}-reference'
                s.add(Matchup(id=match_id, photo_id=pid, dataset_sha256=hashes['results/manifest.csv'], data={
                    'product': 'MODIS Aqua Level-2 Ocean Color', 'granule_id': row['granule_ur'],
                    'granule_sha256': row['granule_sha256'], 'aggregation': 'Geometric mean of positive finite quality-masked pixels',
                    'delta_minutes': abs(number(row['delta_minutes_midpoint'])), 'overlap_fraction': number(row['overlap_fraction']),
                    'selection_rule': row['selection_rule'], 'mask_flags': MASK_FLAGS,
                    'targets': {t: {'value': number(row[t]), 'units': TARGETS[t],
                        'valid_pixels': number(row[('Kd_490' if t == 'kd_490' else t)+'_n_valid']),
                        'valid_fraction': number(row[('Kd_490' if t == 'kd_490' else t)+'_valid_frac'])} for t in TARGETS}}))
            s.flush()
            for target, (mid, _) in models.items():
                value = number(pred[target+'_prediction'])
                if value is None or value <= 0: raise ValueError('Invalid prediction')
                if pred[target+'_candidate'] != selection[target]['candidate'] or pred[target+'_recipe'] != selection[target]['recipe']:
                    raise ValueError('Wrong selected model')
                if eligible and not math.isclose(number(pred[target+'_reference']), number(row[target]), rel_tol=1e-8):
                    raise ValueError('Reference value mismatch')
                s.add(Estimate(id=f'{run_id}-{target}-{pid}', photo_id=pid, run_id=run_id,
                    model_id=mid, matchup_id=match_id, target=target, value=value,
                    role='held_out_test' if eligible else 'supplied_test_inference_only', split='test',
                    scene_group=row.get('group') or row['timelapse_id'],
                    evidence={'source': 'frozen_mediterranean_export', 'input_asset_id': aid,
                        'catalog_snapshot_id': sid, 'image_sha256': row['image_sha256'],
                        'benchmark_eligible': eligible, 'reference_status': pred['reference_status'], 'confidence': None}))
    return {'run_id': run_id, 'imported': True, 'photos': len(ids), 'estimates': 2*len(ids), 'matchups': len(benchmark)}


MASK_FLAGS = ['ATMFAIL', 'LAND', 'HIGLINT', 'HILT', 'HISATZEN', 'STRAYLIGHT', 'CLDICE',
              'COCCOLITH', 'HISOLZEN', 'LOWLW', 'CHLFAIL', 'NAVFAIL', 'MAXAERITER']

if __name__ == '__main__':
    initialize()
    print(json.dumps(import_mediterranean(), indent=2))
