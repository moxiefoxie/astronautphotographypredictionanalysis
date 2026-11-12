"""Train fresh model versions with an untouched scene calibration partition.

No database/network writes. Original checkpoints and source manifests stay intact.
"""
import hashlib
import json
import sys
from pathlib import Path
import joblib
import numpy as np
import pandas as pd
import torch
from sklearn.impute import SimpleImputer
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

WORKSPACE = Path(__file__).resolve().parents[2]
SOURCE = WORKSPACE / 'mediterranean_20261102'
OUT = WORKSPACE / 'appa_calibration_20261103'
sys.path.insert(0, str(SOURCE))
import run_models as rm


def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for block in iter(lambda: f.read(1024 * 1024), b''): h.update(block)
    return h.hexdigest()


def main():
    torch.set_num_threads(4)
    if not torch.backends.mps.is_available():
        raise RuntimeError('Local GPU is unavailable; do not silently start a much slower CPU training run.')
    for p in ['results','checkpoints','cache','runs/full/results','runs/full/checkpoints','runs/full/cache','runs/partial/results','runs/partial/checkpoints','runs/partial/cache']:
        (OUT/p).mkdir(parents=True, exist_ok=True)
    d = pd.read_csv(SOURCE/'results/manifest.csv')
    original_split = d.split.copy()
    groups = sorted(d.loc[d.split.eq('train'),'group'].unique(), key=lambda g: hashlib.sha256(('appa-calibration-v1:'+g).encode()).hexdigest())
    reserved = groups[:20]
    assert len(groups) == 52 and len(reserved) == 20
    d.loc[d.group.isin(reserved),'split'] = 'calibration'
    for key in ['group','timelapse_id','granule_file','decoded_pixel_sha256']:
        assert d.groupby(key).split.nunique().max() == 1, key
    assert (d.split.eq('test') == original_split.eq('test')).all()
    assert (d.split.eq('validation') == original_split.eq('validation')).all()
    features = np.load(SOURCE/'cache/features.npz')
    assert features['image_id'].tolist() == d.image_id.tolist()
    raw, _ = rm.partial.metadata(d)
    np.testing.assert_allclose(raw.astype('float32'), features['metadata'], rtol=0, atol=0)
    train = np.flatnonzero(d.split.eq('train'))
    prep = make_pipeline(SimpleImputer(strategy='median', add_indicator=True, keep_empty_features=True), StandardScaler())
    prep.fit(features['metadata'][train])
    x = prep.transform(features['metadata']).astype('float32')
    input_files = [SOURCE/'results/manifest.csv', SOURCE/'results/training_contract.json', SOURCE/'cache/features.npz',
        SOURCE/'cache/convnext_tiny_stem.npy', SOURCE/'runs/full/cache/convnext_tiny_pixels.npy']
    for name in ['run_models.py']:
        input_files.append(SOURCE/name)
    input_files += [Path(rm.partial.__file__), Path(rm.full.__file__), Path(__file__)]
    contract = {'version':1, 'source_sha256':{str(p.relative_to(WORKSPACE)):sha(p) for p in input_files},
        'partition_rule':'20 original training groups with smallest SHA256(appa-calibration-v1:group); all existing validation/test groups unchanged',
        'calibration_groups':reserved, 'split_counts':d.groupby('split').size().to_dict(),
        'group_counts':d.groupby('split').group.nunique().to_dict(),
        'initialization':'Fresh ImageNet ConvNeXt Tiny weights and heads; never fine-tune an old fitted checkpoint',
        'metadata':'Imputation and normalization fitted only on the reduced training partition',
        'recipes':{'chlor_a':'full','kd_490':'partial'}, 'selection':'Existing fixed architecture recipes; checkpoint epoch selected only by validation group-balanced log10 MAE',
        'calibration_use':'Reserved labels used only after checkpoints are frozen; never tune on test coverage',
        'test_caveat':'The test cohort was previously reported for older models. This is a separate-fit retrospective evaluation, not a new prospective dataset.',
        'device':'mps','epochs_max':12,'patience':4}
    cp = OUT/'results/training_contract.json'
    if cp.exists():
        assert json.loads(cp.read_text()) == contract, 'Contract changed; use a new run directory'
    else:
        cp.write_text(json.dumps(contract,indent=2)+'\n')
        d.to_csv(OUT/'results/manifest.csv',index=False)
        joblib.dump(prep,OUT/'checkpoints/metadata_preprocessor.joblib')
        np.savez_compressed(OUT/'cache/metadata.npz',scaled=x,image_id=d.image_id.to_numpy(dtype=str))
    assert pd.read_csv(OUT/'results/manifest.csv').split.tolist() == d.split.tolist()
    print(json.dumps({'phase':'partition_frozen','counts':contract['split_counts'],'groups':contract['group_counts']}),flush=True)
    # Stem maps were computed using untrained ImageNet features before any supervised fitting.
    maps = np.load(SOURCE/'cache/convnext_tiny_stem.npy',mmap_mode='r')
    partial = rm.partial.fit('convnext_tiny','kd_490',d,x,maps,OUT/'runs/partial',12,4)
    print(json.dumps({'phase':'model_frozen','target':'kd_490','fit':partial}),flush=True)
    _,_,_,_,transform = rm.backbone_parts('convnext_tiny')
    stamp = json.loads((SOURCE/'runs/full/cache/convnext_tiny_pixels.json').read_text())
    assert stamp['manifest_sha256'] == sha(SOURCE/'results/manifest.csv')
    pixels = np.load(SOURCE/'runs/full/cache/convnext_tiny_pixels.npy',mmap_mode='r')
    assert len(pixels) == len(d)
    rm.full.OUT = OUT/'runs/full'
    full = rm.full.fit('convnext_tiny','chlor_a',d,x,pixels,transform)
    print(json.dumps({'phase':'model_frozen','target':'chlor_a','fit':full}),flush=True)
    frozen = {t:{'recipe':recipe,'checkpoint_sha256':sha(OUT/f'runs/{recipe}/checkpoints/{t}_convnext_tiny.pt'),
        'predictions_sha256':sha(OUT/f'runs/{recipe}/cache/{t}_convnext_tiny_predictions.npy')}
        for t,recipe in contract['recipes'].items()}
    (OUT/'results/frozen_models.json').write_text(json.dumps(frozen,indent=2)+'\n')
    print(json.dumps({'status':'complete','models':frozen}),flush=True)

if __name__ == '__main__': main()
