"""Prepare a bounded, append-only release for one calibrated target; no cloud writes."""
import argparse,hashlib,json,math
from datetime import datetime,timezone
from pathlib import Path
import numpy as np
import pandas as pd
from sqlalchemy import create_engine
from app.db import PROJECT,WORKSPACE
from app.transfer import load_records
from app.confidence import PROTOCOL,probability_from_features

ROOT=WORKSPACE/'appa_calibration_20261103';SOURCE=WORKSPACE/'mediterranean_20261102'
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def digest(d):return hashlib.sha256(json.dumps(d,sort_keys=True,allow_nan=False).encode()).hexdigest()


def main(target):
    path=PROJECT/'runtime'/f'confidence-release-{target}.json'
    report=json.loads((ROOT/'results'/f'{target}_confidence.json').read_text())
    if not report['release_eligible']:raise ValueError('Confidence model failed predeclared held-out checks; do not publish this target')
    inference=json.loads((PROJECT/'runtime'/f'calibrated-sample-{target}.json').read_text())
    recipe='full' if target=='chlor_a' else 'partial'
    checkpoint=f'runs/{recipe}/checkpoints/{target}_convnext_tiny.pt'
    assert sha(ROOT/checkpoint)==inference['checkpoint_sha256']==report['hashes']['base_checkpoint_sha256']
    assert inference['calibration_id']==report['id'] and not inference['satellite_values_used_for_inference']
    tables,_=load_records(create_engine(f'sqlite:///{PROJECT/"runtime/dashboard.db"}'))
    records={t.name:rows for t,rows in tables.items()}
    d=pd.read_csv(ROOT/'results/manifest.csv');t=d.split.eq('test')
    train=d.loc[~t]
    source=pd.concat([pd.read_csv(SOURCE/'all_test/results/manifest.csv'),pd.read_csv(SOURCE/'results/manifest.csv')]).drop_duplicates('image_id',keep='last').set_index('image_id',drop=False)
    predictions=np.load(ROOT/f'runs/{recipe}/cache/{target}_convnext_tiny_predictions.npy')
    error=abs(predictions[t]-np.log10(d.loc[t,target].to_numpy()))
    group_errors=pd.DataFrame({'group':d.loc[t,'group'],'error':error}).groupby('group').error.mean()
    artifacts={checkpoint:sha(ROOT/checkpoint),'checkpoints/metadata_preprocessor.joblib':sha(ROOT/'checkpoints/metadata_preprocessor.joblib')}
    mid='med-cal-'+target+'-'+digest({'artifacts':artifacts,'training':report['hashes']['training_contract_sha256'],'confidence':report['id']})[:24]
    rid='confidence-run-'+target+'-'+digest({'model':mid,'photos':[r['photo_id'] for r in inference['rows']]})[:20]
    stamp=datetime.fromtimestamp((ROOT/'results'/f'{target}_confidence.json').stat().st_mtime,tz=timezone.utc).isoformat()
    old={e['photo_id']:e for e in records['estimates'] if e['target']==target}
    estimates=[];allowed={};serving_groups=set()
    for row in inference['rows']:
        pid=row['photo_id'];prior=old[pid];raw=source.loc[pid]
        assert raw['split']=='test' and raw.timelapse_id not in set(train.timelapse_id) and pid not in set(train.image_id)
        features=[math.log10(row['value']),float(raw.cloud_percent),float(raw.water_fraction),float(raw.sun_elevation),
            float(raw.location_source=='earthmatch_verified'),math.log10(max(1e-8,float(raw.footprint_area_km2)))]
        features=[v if math.isfinite(v) else None for v in features]
        replay=probability_from_features(features,report['coefficients'])
        assert abs(replay-row['probability'])<1e-10
        eid=digest({'run':rid,'photo':pid,'target':target})
        confidence={'photo_id':pid,'model_id':mid,'target':target,'prediction':row['value'],
            'input_asset_id':row['input_asset_id'],'image_sha256':row['image_sha256'],'scene_group':prior['scene_group'],
            'calibration_id':report['id'],'probability':row['probability'],'features':features}
        allowed[eid]=confidence;serving_groups.add(prior['scene_group'])
        estimates.append({**prior,'id':eid,'model_id':mid,'run_id':rid,'value':row['value'],'created_at':stamp,
            'evidence':{**prior['evidence'],'source':'calibrated_checkpoint_inference','confidence_probability':confidence,
                'previous_estimate_id':prior['id'],'model_artifact_bundle':'appa_calibration_20261103'}})
    calibration={'id':report['id'],'protocol':PROTOCOL,'method':report['method'],'coefficients':report['coefficients'],
        'calibration_groups':report['calibration_groups'],'validation':report['validation'],'release_eligible':True,
        'eligible_estimates':allowed,'serving_scene_ids':sorted(serving_groups),
        'evaluation_scene_ids':sorted(d.loc[t,'group'].unique()),'excluded_scene_ids':sorted(train.group.unique()),
        'limitations':report['limitations']+' A satellite reference is not an inference input. Transfer to unmatched photos assumes comparable photo quality and input domain.'}
    model={'id':mid,'target':target,'name':f'calibrated_{recipe}_{target}_convnext_tiny','units':'mg/m³' if target=='chlor_a' else 'm⁻¹',
        'manifest':{'selection':f'{target}_convnext_tiny','recipe':recipe,'artifact_sha256':artifacts,
            'model_artifact_bundle':'appa_calibration_20261103','training_contract_sha256':report['hashes']['training_contract_sha256'],
            'benchmark':'mediterranean-20261102','selection_criterion':'Fixed architecture; validation-only checkpoint epoch selection; separate calibration groups',
            'test_metrics':{'n':int(t.sum()),'groups':int(d.loc[t,'group'].nunique()),'group_log_mae':float(group_errors.mean()),
                'median_error_factor':float(10**np.median(error)),'within_2x_pct':float(np.mean(error<=np.log10(2))*100)},
            'serving_enabled':False,'serving_reason':'Saved inference and confidence verified; public job submission remains disabled.',
            'confidence_calibration':calibration,'limitations':'Research estimates of satellite-derived regional averages. Confidence means ±25% agreement with the reference definition; not field accuracy or validated pixel-level retrievals.'}}
    run={'id':rid,'kind':'confidence_calibrated_inference','status':'pending_release','created_at':stamp,'completed_at':None,
        'provenance':{'target':target,'model_id':mid,'confidence_calibration_id':report['id'],'training_split_groups':{'train':32,'validation':12,'calibration':20,'test':21},
            'photos':100,'with_reference':50,'without_reference':50,'satellite_values_used_for_inference':False,
            'replay_max_log10_error':inference['max_checkpoint_replay_log10_error'],'source_sample_run':records['prediction_runs'][0]['id']}}
    release={'version':1,'destination':'qcjkgrelvnivgpfwrfan','target':target,'model_versions':[model],'prediction_runs':[run],'estimates':estimates}
    encoded=json.dumps(release,allow_nan=False,indent=2)+'\n'
    assert len(encoded.encode())<512*1024 and len(estimates)==100
    if path.exists(): assert json.loads(path.read_text())==release,'Conflicting existing immutable release'
    else:path.write_text(encoded)
    # A combined artifact for the pilot builder, selecting only finished releases.
    for candidate in ['chlor_a','kd_490']:
        rp=PROJECT/'runtime'/f'confidence-release-{candidate}.json'
        if not rp.exists():continue
        rel=json.loads(rp.read_text());records['estimates']=[e for e in records['estimates'] if e['target']!=candidate]+rel['estimates']
        records['model_versions']=[m for m in records['model_versions'] if m['target']!=candidate]+rel['model_versions']
    (PROJECT/'runtime/pilot-calibrated-records.json').write_text(json.dumps(records,allow_nan=False)+'\n')
    accepted=sum(next((b.get('release_eligible',False) for b in report['validation']['bins'] if b['index']==min(4,int(r['probability']*5))),False) for r in inference['rows'])
    print(json.dumps({'target':target,'model':mid,'rows':100,'confidence_supported':accepted,'bytes':len(encoded.encode()),'run':rid},indent=2))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--target',required=True,choices=['chlor_a','kd_490']);main(p.parse_args().target)
