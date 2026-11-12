"""Package verified native rasters for APPA, without database writes or model inference."""
from pathlib import Path
import hashlib
import json
import shutil
import argparse
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT.parent / 'high_density_pixel_20261109'
parser = argparse.ArgumentParser()
parser.add_argument('--fullframe', action='store_true', help='Package verified single-pass maps and their updated evaluation')
args = parser.parse_args()
MAPS = SOURCE / ('maps_fullframe_v2' if args.fullframe else 'maps')
index = json.loads((MAPS / 'index.json').read_text())
for name in ['preparation_audit', 'verification', 'map_verification']:
    audit = json.loads((SOURCE / f'results/{name}.json').read_text())
    assert audit.get('passed', audit.get('complete', False)), name
if args.fullframe:
    assert json.loads((MAPS / 'verification.json').read_text())['passed']
    assert index['inference_version'] == 'fullframe-v2'
assert len(index['photos']) <= 6
dest = ROOT / 'public/native-maps'
dest.mkdir(exist_ok=True)
photos = []
total = 0
for item in index['photos']:
    item = dict(item)
    urls = {}
    for filename, digest in item['sha256'].items():
        source = MAPS / filename
        assert hashlib.sha256(source.read_bytes()).hexdigest() == digest
        output = f'{source.stem}-{digest[:16]}{source.suffix}'
        shutil.copyfile(source, dest / output)
        total += source.stat().st_size
        urls[filename] = f'/native-maps/{output}'
    image_id = item['image_id']
    with np.load(MAPS / f'{image_id}.npz') as data:
        values = np.stack([data['chlor_a_log10'], data['kd_490_log10']]).astype('<f4')
        assert values.shape == (2, item['height'], item['width'])
        assert np.array_equal(np.isfinite(values).all(axis=0), data['valid_mask'])
    raw = values.tobytes()
    digest = hashlib.sha256(raw).hexdigest()
    filename = f'{image_id}-{digest[:16]}.f32'
    (dest / filename).write_bytes(raw)
    total += len(raw)
    item['assets'] = {
        'photo': urls[f'{image_id}_photo.jpg'],
        'chlor_a': urls[f'{image_id}_chlor_a.png'],
        'kd_490': urls[f'{image_id}_kd_490.png'],
        'download': urls[f'{image_id}.npz'],
        'values': f'/native-maps/{filename}',
        'values_sha256': digest,
    }
    photos.append(item)
assert total <= 250 * 1024**2
bundle = {**index, 'photos': photos, 'packaged_bytes': total,
          'preparation': json.loads((SOURCE / 'results/preparation_audit.json').read_text()),
          'metrics': json.loads((MAPS / 'metrics.json' if args.fullframe else SOURCE / 'results/metrics.json').read_text())}
(ROOT / 'src/native-maps.json').write_text(json.dumps(bundle, indent=2) + '\n')
(dest / 'index.json').write_text(json.dumps(bundle, indent=2) + '\n')
# The six exported photos use the existing dashboard photo-detail contract.
# All metadata and scalar values come from saved source records, never map averages.
source_photos = pd.read_csv(SOURCE/'results/selected_photos.csv').set_index('image_id')
scalar = ROOT.parent/'high_density_models_20261109'
assert json.loads((scalar/'results/model_verification.json').read_text())['status']=='passed'
selection = json.loads((scalar/'results/completed.json').read_text())['selected']
predictions = pd.read_parquet(scalar/'results/all_model_predictions.parquet')
metrics = pd.read_csv(scalar/'results/model_comparison.csv')
def number(value):
    try: return float(value) if np.isfinite(float(value)) else None
    except (ValueError, TypeError): return None
catalog = {}
for item in photos:
    pid=item['image_id']; row=source_photos.loc[pid]; mission,roll,frame=pid.split('-')
    metadata={k:number(row.get(k)) for k in ['sun_elevation','sun_azimuth','focal_length','water_fraction','earthmatch_inlier_count']}
    metadata.update({'cloud_percent':100*float(row.cloud_fraction),'location_source':row.location_source,
        'named_water_features':json.loads(row.named_water_features),'catalog_source':'saved high-density catalog',
        'input_contract':'high-density-20261109','reference_status':'quality_masked_reference_available'})
    match={'id':f'hd-reference-{pid}','dataset_sha256':row.granule_sha256,'product':'MODIS Aqua Level-2 ocean color',
        'granule_id':row.granule_file,'delta_minutes':abs(float(row.delta_minutes)),
        'overlap_fraction':float(row.overlap_fraction),'aggregation':'Quality-masked footprint geometric mean',
        'selection_rule':'Frozen high-density matched reference; provisional geometric alignment',
        'mask_flags':['Frozen high-density joint MODIS quality mask'], 'targets':{}}
    for t,unit in [('chlor_a','mg/m³'),('kd_490','m⁻¹')]:
        match['targets'][t]={'value':float(row[t]),'units':unit,'valid_pixels':int(row[t+'_n_valid']),'valid_fraction':float(row[t+'_valid_fraction'])}
    estimates={}
    for t,choice in selection.items():
        pred=predictions[(predictions.image_id==pid)&(predictions.target==t)&(predictions.recipe==choice['recipe'])&(predictions.candidate==choice['candidate'])]
        assert len(pred)==1
        score=metrics[(metrics.target==t)&(metrics.recipe==choice['recipe'])&(metrics.candidate==choice['candidate'])&(metrics.cohort=='all')].iloc[0]
        estimates[t]={'value':float(pred.iloc[0].prediction),'units':match['targets'][t]['units'],
            'model':{'id':f'high-density-{t}-{choice["candidate"]}','name':choice['candidate'],'serving_enabled':False,
                'test_metrics':{'median_error_factor':float(score.median_error_factor)},'limitations':'Scalar photo-level evaluation; not pixel accuracy'},
            'run_id':'high-density-models-20261109','role':'held_out_test','split':'test','scene_group':row.group,
            'evidence':{'source':'frozen_high_density_export','image_sha256':row.image_sha256},
            'confidence':{'status':'unavailable'},'prediction_interval':{'status':'unavailable'},
            'satellite':match,'difference':float(pred.iloc[0].prediction)-float(row[t])}
    catalog[pid]={'id':pid,'captured_at':row.photo_datetime,'latitude':float(row.latitude),'longitude':float(row.longitude),
        'mission':mission,'original_url':f'https://eol.jsc.nasa.gov/SearchPhotos/photo.pl?mission={mission}&roll={roll}&frame={frame}',
        'metadata':metadata,'predictions':estimates,'history_count':2,
        'preview':{'available':True,'kind':'native_registered_crop','caption':'Registered native photo; scalar results refer to the saved footprint crop'},
        'limitations':'Frozen high-density outputs. Native-pixel overlays have separate models and unvalidated fine-scale accuracy.'}
(ROOT/'src/native-photo-catalog.json').write_text(json.dumps(catalog,indent=2,allow_nan=False)+'\n')
print(f'Packaged {len(photos)} verified maps; {total:,} bytes; no database writes')
