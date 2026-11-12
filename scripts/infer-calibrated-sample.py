"""Infer both estimates and confidence on the bounded sample without reference values.

Satellite labels are read only by the separate audit after inference, never as
features. The same path processes matched and unmatched photos.
"""
import argparse, hashlib, json, sys
from pathlib import Path
import joblib
import numpy as np
import pandas as pd
from PIL import Image
from sqlalchemy import create_engine
import torch
from app.db import PROJECT, WORKSPACE
from app.transfer import load_records
from app.confidence import probability_from_features

ROOT=WORKSPACE/'appa_calibration_20261103';SOURCE=WORKSPACE/'mediterranean_20261102'
sys.path.insert(0,str(SOURCE));import run_models as rm


def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def main(target):
    torch.set_num_threads(2)
    recipe='full' if target=='chlor_a' else 'partial'
    report=json.loads((ROOT/'results'/f'{target}_confidence.json').read_text())
    checkpoint=ROOT/f'runs/{recipe}/checkpoints/{target}_convnext_tiny.pt'
    assert sha(checkpoint)==report['hashes']['base_checkpoint_sha256']
    assert sha(ROOT/'checkpoints/metadata_preprocessor.joblib')==report['hashes']['metadata_preprocessor_sha256']
    tables,_=load_records(create_engine(f'sqlite:///{PROJECT/"runtime/dashboard.db"}'))
    records={t.name:rows for t,rows in tables.items()};assets=sorted(records['input_assets'],key=lambda a:a['photo_id'])
    source=pd.concat([pd.read_csv(SOURCE/'all_test/results/manifest.csv'),pd.read_csv(SOURCE/'results/manifest.csv')]).drop_duplicates('image_id',keep='last').set_index('image_id',drop=False)
    d=source.loc[[a['photo_id'] for a in assets]].copy()
    assert len(d)==100 and d.split.eq('test').all()
    trained=pd.read_csv(ROOT/'results/manifest.csv')
    excluded=trained.loc[~trained.split.eq('test')]
    assert not set(d.timelapse_id)&set(excluded.timelapse_id)
    assert not set(d.image_id)&set(excluded.image_id)
    # Optional satellite identity is used only for a leakage audit, never a
    # target value or confidence feature. Missing identities are permitted.
    identities=pd.read_csv(SOURCE/'results/fresh_labels.csv',usecols=['photo_id','granule_file'])
    known_granules=set(identities.loc[identities.photo_id.isin(d.image_id),'granule_file'].dropna())
    assert not known_granules & set(excluded.granule_file)
    excluded_pixels=set(excluded.decoded_pixel_sha256)
    prep=joblib.load(ROOT/'checkpoints/metadata_preprocessor.joblib')
    raw,_=rm.partial.metadata(d);metadata=prep.transform(raw.astype('float32')).astype('float32')
    saved=torch.load(checkpoint,weights_only=False,map_location='cpu')
    stem,tail,norm,width,transform=rm.backbone_parts('convnext_tiny')
    model=rm.partial.LastStageRegressor(tail,norm,width,metadata.shape[1]) if recipe=='partial' else rm.full.FullRegressor('convnext_tiny',metadata.shape[1])
    model.load_state_dict(saved['state_dict']);model.eval();stem.eval();plog=[]
    with torch.inference_mode():
        for first in range(0,len(assets),4):
            batch=[]
            for a in assets[first:first+4]:
                assert sha(a['local_path'])==a['image_sha256']
                with Image.open(a['local_path']) as im:
                    rgb=im.convert('RGB')
                    decoded=hashlib.sha256(str(rgb.size).encode()+rgb.tobytes()).hexdigest()
                    assert decoded not in excluded_pixels, 'Input duplicates a model-fitting or calibration image'
                    batch.append(transform(rgb))
            x=torch.stack(batch)
            if recipe=='partial':x=stem(x).to(torch.float16).to(torch.float32)
            output=model(x,torch.from_numpy(metadata[first:first+len(batch)]))*saved['target_std']+saved['target_mean']
            plog.extend(output.numpy().tolist())
            print(json.dumps({'target':target,'inferred':first+len(batch),'total':100}),flush=True)
    plog=np.asarray(plog);values=10**plog
    # These are the entire confidence inputs; no matchup, label or error column.
    features=np.column_stack([plog,d.cloud_percent,d.water_fraction,d.sun_elevation,
        d.location_source.eq('earthmatch_verified').astype(float),np.log10(d.footprint_area_km2.clip(lower=1e-8))])
    c=joblib.load(ROOT/'checkpoints'/f'{target}_confidence.joblib')
    rawscore=c['score'].decision_function(c['scaler'].transform(c['imputer'].transform(features)))
    probability=c['calibrator'].predict_proba(c['calibrator_scaler'].transform(rawscore[:,None]))[:,1]
    portable=np.array([probability_from_features(f.tolist(),report['coefficients']) for f in features])
    np.testing.assert_allclose(portable,probability,rtol=0,atol=1e-12)
    # Compare separate inference to frozen benchmark outputs only after scoring.
    lookup={pid:i for i,pid in enumerate(trained.image_id)}
    expected=np.load(ROOT/f'runs/{recipe}/cache/{target}_convnext_tiny_predictions.npy')
    errors=[abs(plog[i]-expected[lookup[pid]]) for i,pid in enumerate(d.image_id) if pid in lookup]
    assert max(errors)<=2e-4, max(errors)
    rows=[]
    for i,a in enumerate(assets):
        source_hash=hashlib.sha256(np.asarray(features[i],dtype='<f8').tobytes()).hexdigest()
        rows.append({'photo_id':a['photo_id'],'value':float(values[i]),'probability':float(probability[i]),
            'input_asset_id':a['id'],'image_sha256':a['image_sha256'],'confidence_features_sha256':source_hash,'features':[None if not np.isfinite(v) else float(v) for v in features[i]]})
    result={'target':target,'calibration_id':report['id'],'checkpoint_sha256':sha(checkpoint),
        'photos':100,'max_checkpoint_replay_log10_error':float(max(errors)),
        'satellite_values_used_for_inference':False,'rows':rows}
    (PROJECT/'runtime'/f'calibrated-sample-{target}.json').write_text(json.dumps(result,indent=2,allow_nan=False)+'\n')
    print(json.dumps({k:v for k,v in result.items() if k!='rows'}),flush=True)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--target',required=True,choices=['chlor_a','kd_490']);main(p.parse_args().target)
