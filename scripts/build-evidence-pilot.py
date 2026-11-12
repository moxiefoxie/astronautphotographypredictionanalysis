"""Build bounded, static satellite evidence and frozen-model occlusion diagnostics.

No training, network access or cloud writes. Run with the frozen ML environment:
DATABASE_URL=sqlite:// PYTHONPATH=backend ../kd490_proposal/.venv/bin/python scripts/build-evidence-pilot.py
"""
import os
import argparse
os.environ.setdefault('DATABASE_URL', 'sqlite://')
import hashlib
import json
import sys
from pathlib import Path
import numpy as np
import pandas as pd
from PIL import Image
from scipy.spatial import cKDTree
from sqlalchemy import create_engine
import torch
from torchvision.transforms import functional as TF
from app.db import PROJECT, WORKSPACE
from app.transfer import load_records

ROOT = WORKSPACE / 'mediterranean_20261102'
sys.path.insert(0, str(ROOT))
import run_models as rm
sys.path.insert(0, str(WORKSPACE / 'sammy_ocean_color_models'))
from sammy_spatial import SAMMY_MASK


def sha(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()


def homography(points):
    """Map corner order TL, TR, BR, BL to normalized crop coordinates."""
    rows, values = [], []
    for (x, y), (u, v) in zip(points, [(0, 0), (1, 0), (1, 1), (0, 1)]):
        rows.extend([[x, y, 1, 0, 0, 0, -u*x, -u*y], [0, 0, 0, x, y, 1, -v*x, -v*y]])
        values.extend([u, v])
    return np.r_[np.linalg.solve(rows, values), 1].reshape(3, 3)


def project(points, matrix):
    h = np.c_[points, np.ones(len(points))] @ matrix.T
    if not np.isfinite(h).all() or (np.abs(h[:, 2]) < 1e-10).any():
        raise ValueError('Projection singularity')
    return h[:, :2] / h[:, 2:]


def reference_layers(asset, match, row):
    meta = asset['provenance']['metadata']
    corners = np.asarray(meta['corners_latlon'], dtype=float)
    assert corners.shape == (4, 2) and np.isfinite(corners).all()
    # Local lon/lat plane, with longitude scaled at the footprint's latitude.
    lat0, lon0 = corners.mean(0)
    xy = lambda latlon: np.column_stack([
        ((latlon[:, 1] - lon0 + 180) % 360 - 180) * np.cos(np.deg2rad(lat0)), latlon[:, 0] - lat0])
    matrix = homography(xy(corners))
    residual = float(np.max(np.abs(project(xy(corners), matrix) - [[0,0],[1,0],[1,1],[0,1]])))
    assert residual < 1e-8
    subset_path = ROOT / 'results/subsets' / f'{asset["photo_id"]}.parquet'
    subset = pd.read_parquet(subset_path)
    uv = project(xy(subset[['lat', 'lon']].to_numpy()), matrix)
    inside = (uv >= 0).all(1) & (uv <= 1).all(1)
    assert inside.mean() > .95, 'Corner order/footprint consistency check failed'
    uv = uv[inside]
    tree = cKDTree(uv)
    pitch = float(np.median(tree.query(uv, k=2)[0][:, 1]))
    assert 0 < pitch < .1, 'Insufficient spatial sampling'
    side = 32
    x, y = np.meshgrid((np.arange(side)+.5)/side, (np.arange(side)+.5)/side)
    distances, nearest = tree.query(np.c_[x.ravel(), y.ravel()])
    flag_ok = (subset.l2_flags.to_numpy(dtype='uint32') & SAMMY_MASK) == 0
    layers = {}
    for target, column in [('chlor_a', 'chlor_a'), ('kd_490', 'Kd_490')]:
        values = subset[column].to_numpy(dtype=float)
        valid = flag_ok & np.isfinite(values) & (values > 0)
        expected = match['targets'][target]
        assert int(valid.sum()) == int(expected['valid_pixels'])
        mean = float(np.exp(np.log(values[valid]).mean()))
        np.testing.assert_allclose(mean, expected['value'], rtol=1e-10)
        picked = values[inside][nearest]
        accepted = valid[inside][nearest] & (distances <= 1.5*pitch)
        grid = np.where(accepted, np.log10(np.maximum(picked, 1e-30)), np.nan).reshape(side, side)
        layers[target] = {'grid_log10': [[None if not np.isfinite(v) else round(float(v), 6) for v in line] for line in grid],
            'geomean': mean, 'valid_pixels': int(valid.sum()), 'display_coverage': float(accepted.mean()),
            'units': expected['units'], 'range': [.01, 10] if target == 'chlor_a' else [.01, 1]}
    return {'layers': layers, 'grid_size': side, 'corner_residual': residual,
        'inside_fraction': float(inside.mean()), 'median_pixel_pitch_normalized': pitch,
        'subset_sha256': sha(subset_path), 'granule_sha256': match['granule_sha256'],
        'granule_id': match['granule_id'], 'delta_minutes': match['delta_minutes'],
        'mask_flags': match['mask_flags'],
        'registration': 'Approximate corner projection from EarthMatch geometry; no independent pixel-registration validation.',
        'mask_status': 'Satellite quality flags applied. The separate photograph water/cloud masks were unavailable; no photo-mask claim.',
        'method': 'Nearest native satellite pixel on a 32×32 display grid; rejected pixels and distant gaps remain transparent.'}


def model_layers(assets, records, manifest):
    """Replay exact checkpoints first; perturb only their post-preprocessing pixels."""
    import joblib
    torch.set_num_threads(4)
    device = 'cpu'
    rows = manifest.loc[[a['photo_id'] for a in assets]]
    raw_meta, names = rm.partial.metadata(rows)
    estimates = {(e['photo_id'], e['target']): e for e in records['estimates']}
    results = {a['photo_id']: {} for a in assets}
    for model_record in records['model_versions']:
        target = model_record['target']; recipe = model_record['manifest']['recipe']
        bundle = model_record['manifest'].get('model_artifact_bundle', 'mediterranean_20261102')
        assert bundle in ('mediterranean_20261102', 'appa_calibration_20261103')
        model_root = WORKSPACE / bundle
        prep = joblib.load(model_root / 'checkpoints/metadata_preprocessor.joblib')
        metadata = prep.transform(raw_meta.astype('float32')).astype('float32')
        cache = np.load(model_root / 'cache/metadata.npz')
        cached_lookup = {pid: i for i, pid in enumerate(cache['image_id'])}
        cached_indices = [i for i,a in enumerate(assets) if a['photo_id'] in cached_lookup]
        np.testing.assert_allclose(metadata[cached_indices], cache['scaled'][[cached_lookup[assets[i]['photo_id']] for i in cached_indices]], rtol=0, atol=1e-6)

        for relative, expected in model_record['manifest']['artifact_sha256'].items():
            assert sha(model_root / relative) == expected, relative
        checkpoint = model_root / f'runs/{recipe}/checkpoints/{target}_convnext_tiny.pt'
        saved = torch.load(checkpoint, weights_only=False, map_location='cpu')
        stem, tail, norm, width, transform = rm.backbone_parts('convnext_tiny')
        model = rm.partial.LastStageRegressor(tail, norm, width, metadata.shape[1]) if recipe == 'partial' else rm.full.FullRegressor('convnext_tiny', metadata.shape[1])
        model.load_state_dict(saved['state_dict']); model.eval(); stem.eval()
        def predict(batch, meta):
            with torch.inference_mode():
                # The partial training contract caches stem maps at float16.
                inputs = stem(batch).to(torch.float16).to(torch.float32) if recipe == 'partial' else batch
                return (model(inputs, meta) * saved['target_std'] + saved['target_mean']).numpy()
        for i, asset in enumerate(assets):
            pid = asset['photo_id']
            with Image.open(asset['local_path']) as image:
                rgb = image.convert('RGB')
                assert sha(asset['local_path']) == asset['image_sha256']
                pixels = transform(rgb)
                resized = TF.resize(rgb, transform.resize_size, interpolation=transform.interpolation, antialias=transform.antialias)
            h, w = pixels.shape[-2:]; rw, rh = resized.size
            left, top = int(round((rw-w)/2)), int(round((rh-h)/2))
            bounds = [left/rw, top/rh, (left+w)/rw, (top+h)/rh]
            meta = torch.from_numpy(metadata[i:i+1])
            base = float(predict(pixels[None], meta)[0])
            expected = estimates[(pid, target)]['value']
            # Same tolerance as the frozen benchmark's checkpoint replay.
            assert abs(base - np.log10(expected)) <= 2e-4, (pid, target, base, expected)
            changed, boxes = [], []
            replacement = pixels.mean((1,2), keepdim=True)
            for yy in range(4):
                for xx in range(4):
                    x0,x1 = xx*w//4, (xx+1)*w//4
                    y0,y1 = yy*h//4, (yy+1)*h//4
                    altered = pixels.clone(); altered[:,y0:y1,x0:x1] = replacement
                    changed.append(altered)
                    boxes.append([(left+x0)/rw, (top+y0)/rh, (left+x1)/rw, (top+y1)/rh])
            outputs = []
            for first in range(0, len(changed), 4):
                batch = torch.stack(changed[first:first+4])
                outputs.extend(predict(batch, meta.repeat(len(batch),1)).tolist())
            effects = base - np.asarray(outputs)
            strongest = int(np.argmax(np.abs(effects)))
            results[pid][target] = {'model_id':model_record['id'], 'checkpoint_sha256':sha(checkpoint),
                'replayed_value':float(10**base), 'saved_value':expected,
                'replay_abs_log10_error':abs(base-float(np.log10(expected))),
                'input_bounds':bounds, 'tile_boxes':boxes, 'delta_log10':effects.tolist(),
                'occluded_values':(10**np.asarray(outputs)).tolist(), 'strongest_tile':strongest,
                'method':'4×4 non-overlapping occlusion on the exact preprocessed model input, replacing each tile with the image mean RGB. Metadata held fixed.',
                'limitations':'Sensitivity to this artificial replacement, not a concentration map, causal explanation, uncertainty interval or proof of water chemistry. Correlated features and the replacement choice affect the result.',
                'metadata_inputs':names, 'device':device}
            print(json.dumps({'phase':'model_sensitivity','target':target,'photo':pid,'completed':i+1,'total':len(assets)}), flush=True)
    return results


def main():
    parser = argparse.ArgumentParser(); parser.add_argument('--records'); parser.add_argument('--targets', nargs='+', choices=['chlor_a','kd_490']); parser.add_argument('--unmatched-only', action='store_true'); args = parser.parse_args()
    tables,_ = load_records(create_engine(f'sqlite:///{PROJECT / "runtime/dashboard.db"}'))
    records = {t.name:rows for t,rows in tables.items()}
    if args.records: records = json.loads(Path(args.records).read_text())
    previous_index = json.loads((PROJECT/'src/evidence-pilot.json').read_text()) if (PROJECT/'src/evidence-pilot.json').exists() else {}
    all_models = records['model_versions']
    if args.targets: records['model_versions'] = [m for m in all_models if m['target'] in args.targets]
    matches = {m['photo_id']:m['data'] for m in records['satellite_matchups']}
    manifest = pd.concat([pd.read_csv(ROOT/'all_test/results/manifest.csv'),pd.read_csv(ROOT/'results/manifest.csv')]).drop_duplicates('image_id',keep='last').set_index('image_id',drop=False)
    if args.unmatched_only:
        candidates = sorted([a for a in records['input_assets'] if a['photo_id'] not in matches],key=lambda a:(a['photo_id'] != 'ISS042-E-104322',a['photo_id']))
        assets=[]; scenes=set()
        for asset in candidates:
            scene=manifest.loc[asset['photo_id'],'timelapse_id']
            if scene in scenes:continue
            assets.append(asset);scenes.add(scene)
            if len(assets)==3:break
        assert len(assets)==3
    else:
        assets = [a for a in records['input_assets'] if a['photo_id'] in matches and a['provenance']['metadata']['location_source']=='earthmatch_verified']
        assert len(assets) == 15
    references = {}; checked = set()
    for asset in assets:
        pid=asset['photo_id']
        if pid not in matches:
            references[pid]=None
            continue
        row=manifest.loc[pid]; path=ROOT/'raw/granules'/row.granule_file
        if path not in checked:
            assert sha(path)==matches[pid]['granule_sha256']; checked.add(path)
        references[pid]=reference_layers(asset,matches[pid],row)
        print(json.dumps({'phase':'satellite_reference','photo':pid,'verified':True}),flush=True)
    sensitivities=model_layers(assets, records, manifest)
    reused = {}
    for asset in assets:
        pid = asset['photo_id']
        missing = {m['target']: m['id'] for m in all_models if m['target'] not in sensitivities[pid]}
        if missing:
            entry = previous_index[pid]
            old = json.loads((PROJECT/'public'/entry['url'].lstrip('/')).read_text())
            assert old['input_asset_id'] == asset['id'] and old['source_sha256'] == asset['image_sha256']
            for target, model_id in missing.items():
                assert old['sensitivity'][target]['model_id'] == model_id
                sensitivities[pid][target] = old['sensitivity'][target]
            reused[pid] = {'url':entry['url'],'targets':list(missing)}
    out=PROJECT/'public/evidence-pilot';out.mkdir(parents=True,exist_ok=True)
    code_hash=sha(__file__); index=dict(previous_index); report=[]
    for asset in assets:
        pid=asset['photo_id']
        data={'photo_id':pid,'input_asset_id':asset['id'],'source_sha256':asset['image_sha256'],
            'generator_sha256':code_hash,'reused_sensitivity':reused.get(pid),'reference':references[pid],'sensitivity':sensitivities[pid]}
        content=json.dumps(data,allow_nan=False,separators=(',',':')).encode()
        name=f'{pid}-{hashlib.sha256(content).hexdigest()[:16]}.json'
        (out/name).write_bytes(content)
        index[pid]={'url':f'/evidence-pilot/{name}','asset_id':asset['id'],'source_sha256':asset['image_sha256'],
            'has_reference': references[pid] is not None,
            'model_ids':{t:s['model_id'] for t,s in sensitivities[pid].items()}}
        if pid in previous_index:
            old = previous_index[pid]
            alternatives = [{k:v for k,v in old.items() if k != 'variants'}] + old.get('variants', [])
            seen = {index[pid]['url']}; variants = []
            for alternative in alternatives:
                if alternative['url'] not in seen:
                    seen.add(alternative['url']); variants.append(alternative)
            index[pid]['variants'] = variants
        report.append({'photo_id':pid,'reference_verified':references[pid] is not None,'replay_errors':{t:s['replay_abs_log10_error'] for t,s in sensitivities[pid].items()},'bytes':len(content)})
    (PROJECT/'src/evidence-pilot.json').write_text(json.dumps(index,indent=2)+'\n')
    suffix='-unmatched' if args.unmatched_only else ''
    (PROJECT/f'runtime/evidence-pilot-verification{suffix}.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({'status':'complete','photos':len(index),'bytes':sum(r['bytes'] for r in report)}),flush=True)


if __name__=='__main__': main()
