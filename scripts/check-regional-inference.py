"""Bounded diagnostic: apply the saved scalar models to 4x4 enlarged input tiles.

This is NOT a trained spatial model or a public map release. No fitting, network,
database writes, satellite inputs, or confidence reuse. References are read only
after predictions, for an exploratory check against a spatially flat control.
"""
import hashlib
import json
import sys
from pathlib import Path
import joblib
import numpy as np
import pandas as pd
from PIL import Image
import torch
from torch.nn.functional import interpolate

PROJECT = Path(__file__).resolve().parents[1]
WORKSPACE = PROJECT.parent
ROOT = WORKSPACE / 'mediterranean_20261102'
sys.path.insert(0, str(ROOT))
import run_models as rm


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def audit_regions(values, baseline, boxes, reference):
    grid = np.array([[np.nan if v is None else v for v in line]
                     for line in reference['grid_log10']])
    yy, xx = np.mgrid[:grid.shape[0], :grid.shape[1]]
    xx = (xx + .5) / grid.shape[1]; yy = (yy + .5) / grid.shape[0]
    estimates, labels = [], []
    for value, (x0, y0, x1, y1) in zip(values, boxes):
        area = (xx >= x0) & (xx < x1) & (yy >= y0) & (yy < y1)
        valid = area & np.isfinite(grid)
        # Fixed before scoring; display samples are correlated, not independent.
        if valid.sum() < 4 or valid.sum() / max(1, area.sum()) < .75:
            continue
        estimates.append(value); labels.append(grid[valid].mean())
    if len(labels) < 4:
        return {'supported_regions': len(labels), 'scored': False}
    p, y = np.asarray(estimates), np.asarray(labels)
    return {'supported_regions': len(y), 'scored': True,
            'regional_log_mae': float(np.abs(p-y).mean()),
            'whole_crop_log_mae': float(np.abs(baseline-y).mean()),
            'contrast_log_mae': float(np.abs((p-p.mean())-(y-y.mean())).mean()),
            'flat_contrast_log_mae': float(np.abs(y-y.mean()).mean())}


def main():
    torch.set_num_threads(4)
    index = json.loads((PROJECT/'src/evidence-pilot.json').read_text())
    records = json.loads((PROJECT/'runtime/pilot-calibrated-records.json').read_text())
    assets = [a for a in records['input_assets'] if a['photo_id'] in index]
    assert len(assets) == 18
    manifest = pd.concat([pd.read_csv(ROOT/'all_test/results/manifest.csv'),
                          pd.read_csv(ROOT/'results/manifest.csv')]).drop_duplicates('image_id', keep='last').set_index('image_id', drop=False)
    raw, _ = rm.partial.metadata(manifest.loc[[a['photo_id'] for a in assets]])
    predictions = {a['photo_id']: {} for a in assets}
    for record in records['model_versions']:
        target = record['target']; recipe = record['manifest']['recipe']
        root = WORKSPACE / record['manifest'].get('model_artifact_bundle', 'mediterranean_20261102')
        for path, expected in record['manifest']['artifact_sha256'].items():
            assert sha(root/path) == expected
        prep = joblib.load(root/'checkpoints/metadata_preprocessor.joblib')
        metadata = prep.transform(raw.astype('float32')).astype('float32')
        checkpoint = root/f'runs/{recipe}/checkpoints/{target}_convnext_tiny.pt'
        saved = torch.load(checkpoint, weights_only=False, map_location='cpu')
        stem, tail, norm, width, transform = rm.backbone_parts('convnext_tiny')
        model = rm.partial.LastStageRegressor(tail, norm, width, metadata.shape[1]) if recipe == 'partial' else rm.full.FullRegressor('convnext_tiny', metadata.shape[1])
        model.load_state_dict(saved['state_dict']); model.eval(); stem.eval()
        def infer(batch, meta):
            with torch.inference_mode():
                x = stem(batch).to(torch.float16).to(torch.float32) if recipe == 'partial' else batch
                return (model(x, meta) * saved['target_std'] + saved['target_mean']).numpy()
        for i, asset in enumerate(assets):
            pid = asset['photo_id']
            assert sha(asset['local_path']) == asset['image_sha256']
            evidence = json.loads((PROJECT/'public'/index[pid]['url'].lstrip('/')).read_text())
            s = evidence['sensitivity'][target]
            assert s['model_id'] == record['id'] and s['checkpoint_sha256'] == sha(checkpoint)
            with Image.open(asset['local_path']) as im:
                pixels = transform(im.convert('RGB'))
            meta = torch.from_numpy(metadata[i:i+1])
            base = float(infer(pixels[None], meta)[0])
            assert abs(base - np.log10(s['saved_value'])) < 2e-4
            h, w = pixels.shape[-2:]
            tiles = torch.stack([interpolate(pixels[:, y*h//4:(y+1)*h//4, x*w//4:(x+1)*w//4][None],
                size=(h, w), mode='bilinear', align_corners=False, antialias=True)[0]
                for y in range(4) for x in range(4)])
            values = np.concatenate([infer(tiles[j:j+4], meta.repeat(len(tiles[j:j+4]), 1)) for j in range(0,16,4)])
            assert np.isfinite(values).all()
            predictions[pid][target] = {'model_id': record['id'], 'checkpoint_sha256': sha(checkpoint),
                'source_sha256': asset['image_sha256'], 'input_asset_id': asset['id'],
                'whole_crop_log10': base, 'tile_log10': values.tolist(), 'boxes': s['tile_boxes'],
                'confidence': None, 'spatial_accuracy_validated': False}
            print(json.dumps({'target': target, 'photo': pid, 'completed': i+1, 'total': len(assets)}), flush=True)
    # Labels are deliberately unavailable to the entire inference pass above.
    summary = {}
    for target in ('chlor_a', 'kd_490'):
        audits = []
        for pid, targets in predictions.items():
            e = json.loads((PROJECT/'public'/index[pid]['url'].lstrip('/')).read_text())
            if not e.get('reference'): continue
            p = targets[target]
            audit = audit_regions(p['tile_log10'], p['whole_crop_log10'], p['boxes'], e['reference']['layers'][target])
            audit['photo_id'] = pid; audits.append(audit)
        scored = [a for a in audits if a['scored']]
        means = {k: float(np.mean([a[k] for a in scored])) for k in
                 ('regional_log_mae', 'whole_crop_log_mae', 'contrast_log_mae', 'flat_contrast_log_mae')}
        summary[target] = {'photos': len(scored), **means,
            'contrast_skill_vs_flat': 1-means['contrast_log_mae']/means['flat_contrast_log_mae'], 'per_photo': audits}
    output = {'method': '4x4 scalar-model crops enlarged 4x, original whole-photo metadata fixed. No spatial training.',
              'limitations': 'Out-of-distribution scale/context; no photo water mask. Reference projection approximate. This reused pilot is exploratory, not an independent spatial validation set. Whole-photo confidence does not apply.',
              'satellite_values_used_for_inference': False, 'public_release': False,
              'code_sha256': sha(__file__), 'predictions': predictions, 'evaluation': summary}
    (PROJECT/'runtime/regional-inference-diagnostic.json').write_text(json.dumps(output, indent=2, allow_nan=False)+'\n')
    print(json.dumps({t: {k:v for k,v in s.items() if k != 'per_photo'} for t,s in summary.items()}), flush=True)


if __name__ == '__main__':
    main()
