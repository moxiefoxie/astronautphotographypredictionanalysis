"""Import frozen results atomically and idempotently; never retrain or rewrite them."""
import csv
import hashlib
import json
import math
from pathlib import Path
from .db import WORKSPACE, Session, initialize, Photo, ModelVersion, Matchup, Estimate, Run, utcnow

TARGETS = {'chlor_a': 'mg/m³', 'kd_490': 'm⁻¹'}

def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()

def number(value):
    if value in ('', None):
        return None
    value = float(value)
    return value if math.isfinite(value) else None

def rows(path):
    with Path(path).open(newline='') as f:
        return list(csv.DictReader(f))

def fingerprint(root, target):
    summary = json.loads((root / 'results' / f'{target}_summary.json').read_text())
    files = [root / 'cache/feature_schema.json', root / 'checkpoints' / f'{target}_models.joblib',
             WORKSPACE / 'quick_chl_kd_baseline/run_baseline.py',
             Path(__file__).with_name('inference.py')]
    if summary['selected'] == 'small_cnn_metadata':
        files += [root / 'checkpoints' / f'{target}_cnn_metadata.joblib',
                  root / 'checkpoints' / f'{target}_small_cnn.pt', root / 'deep_models.py']
    hashes = {str(p.relative_to(WORKSPACE)): sha(p) for p in files}
    signature = hashlib.sha256(json.dumps({'hashes': hashes, 'selected': summary['selected']}, sort_keys=True).encode()).hexdigest()
    return f'{target}-{signature[:24]}', {
        'artifact_sha256': hashes, 'selection': summary['selected'],
        'feature_schema': json.loads((root / 'cache/feature_schema.json').read_text()),
        'test_metrics': summary['test_metrics'], 'benchmark': 'sammy-20260923',
        'training_photos': summary['train_photos'], 'validation_photos': summary['validation_photos'],
        'test_photos': summary['test_photos'], 'confidence_calibration': None,
        'limitations': 'Satellite-derived photo aggregate benchmark; no in-situ or pixel-level validation. Holdout reuses an earlier image pool.',
    }

def import_benchmark(session_factory=Session, root=None):
    root = root or WORKSPACE / 'sammy_ocean_color_models'
    manifest = rows(root / 'results/manifest.csv')
    audit = json.loads((root / 'results/data_audit.json').read_text())
    predictions = {t: rows(root / 'results' / f'{t}_predictions_all.csv') for t in TARGETS}
    ids = {r['image_id'] for r in manifest}
    if len(ids) != len(manifest):
        raise ValueError('Duplicate image IDs in manifest')
    for target, records in predictions.items():
        if len(records) != len(ids) or {r['image_id'] for r in records} != ids:
            raise ValueError(f'{target}: predictions do not match the frozen manifest')
    source_hashes = {p.name: sha(p) for p in [root / 'results/manifest.csv', root / 'results/data_audit.json', *[root / 'results' / f'{t}_predictions_all.csv' for t in TARGETS]]}
    models = {t: fingerprint(root, t) for t in TARGETS}
    digest = hashlib.sha256(json.dumps({'sources': source_hashes, 'models': [v[0] for v in models.values()]}, sort_keys=True).encode()).hexdigest()
    run_id = f'benchmark-{digest[:24]}'
    label_hash = audit['sammy_labels_sha256']
    with session_factory.begin() as s:
        if s.get(Run, run_id):
            return {'run_id': run_id, 'photos': len(manifest), 'imported': False}
        s.add(Run(id=run_id, kind='benchmark_import', status='complete', completed_at=utcnow(), provenance={
            'sources': source_hashes, 'dataset_sha256': label_hash, 'filters': audit['filters'],
            'mask_flags': audit['sammy_mask_flags'], 'split_counts': audit['split_counts'],
        }))
        for target, (model_id, description) in models.items():
            if not s.get(ModelVersion, model_id):
                s.add(ModelVersion(id=model_id, target=target, name=description['selection'], units=TARGETS[target], manifest=description))
        s.flush()
        by_id = {r['image_id']: r for r in manifest}
        for r in manifest:
            photo_id = r['image_id']
            mission, roll, frame = photo_id.split('-')
            # Do not replace canonical photo metadata during an import of another experiment.
            if not s.get(Photo, photo_id):
                s.add(Photo(id=photo_id, mission=mission, captured_at=r['photo_datetime'] or None,
                    latitude=number(r['latitude']), longitude=number(r['longitude']),
                    thumbnail_url=r['thumbnail_url'], image_url=r['thumbnail_url'].replace('/small/', '/large/'),
                    original_url=f'https://eol.jsc.nasa.gov/SearchPhotos/photo.pl?mission={mission}&roll={roll}&frame={frame}',
                    local_image=r['local_image'], image_sha256=r['image_sha256'], metadata_json={
                        key: number(r.get(key)) for key in ['cloud_percent', 'sun_elevation', 'sun_azimuth', 'focal_length']
                    }))
                s.flush()
            match_id = f'{photo_id}-{label_hash[:24]}'
            if not s.get(Matchup, match_id):
                s.add(Matchup(id=match_id, photo_id=photo_id, dataset_sha256=label_hash, data={
                    'product': 'MODIS Aqua Level-2 Ocean Color', 'granule_id': r['granule_ur'],
                    'aggregation': 'Geometric mean of positive finite pixels after L2 flag masking',
                    'delta_minutes': number(r['delta_minutes']), 'overlap_fraction': number(r['overlap_fraction']),
                    'selection_rule': r['selection_rule'], 'mask_flags': audit['sammy_mask_flags'],
                    'targets': {t: {'value': number(r[spec]), 'valid_pixels': number(r[count]),
                                    'valid_fraction': number(r[fraction]), 'units': TARGETS[t]} for t, spec, count, fraction in [
                        ('chlor_a', 'chlor_a_geomean', 'chlor_a_n_valid', 'chlor_a_valid_frac'),
                        ('kd_490', 'Kd_490_geomean', 'Kd_490_n_valid', 'Kd_490_valid_frac')]},
                }))
        s.flush()
        for target, records in predictions.items():
            model_id = models[target][0]
            for p in records:
                m = by_id[p['image_id']]
                value = number(p[f'predicted_{target}'])
                if value is None or value <= 0 or p['model'] != models[target][1]['selection']:
                    raise ValueError(f'Invalid {target} output for {p["image_id"]}')
                if p['split'] != m['split'] or p['group'] != m['group']:
                    raise ValueError('Split/group mismatch')
                s.add(Estimate(id=f'{run_id}-{target}-{p["image_id"]}', photo_id=p['image_id'], run_id=run_id,
                    model_id=model_id, matchup_id=f'{p["image_id"]}-{label_hash[:24]}', target=target, value=value,
                    role=p['prediction_role'], split=p['split'], scene_group=p['group'],
                    evidence={'source': 'frozen_prediction_export', 'image_sha256': m['image_sha256'], 'confidence': None}))
    return {'run_id': run_id, 'photos': len(manifest), 'estimates': sum(map(len, predictions.values())), 'imported': True}

if __name__ == '__main__':
    initialize()
    print(json.dumps(import_benchmark(), indent=2))
