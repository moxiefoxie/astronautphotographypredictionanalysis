"""Fit accuracy probabilities with separate confidence fitting/calibration/test scenes.

Run with the scientific environment, DATABASE_URL=sqlite:// and PYTHONPATH=backend.
The protocol is frozen before fitting or evaluating; test results never tune it.
"""
import argparse
import hashlib
import json
from pathlib import Path
import joblib
import numpy as np
import pandas as pd
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler
from app.confidence import PROTOCOL, TOLERANCE, DEFINITION, accurate, group_weights, reliability

WORKSPACE = Path(__file__).resolve().parents[2]
ROOT = WORKSPACE/'appa_calibration_20261103'
PROTOCOL_DATA = {'protocol':PROTOCOL,'tolerance':TOLERANCE,'definition':DEFINITION,
    'features':['log10_prediction','cloud_percent','water_fraction','sun_elevation','earthmatch_verified','log10_footprint_area_km2'],
    'score_fit_split':'validation','probability_calibration_split':'calibration','evaluation_split':'test',
    'score_model':'L2 logistic regression C=1; median imputation and scene-weighted standardization',
    'calibrator':'Sigmoid logistic regression C=1 on standardized raw score; equal total weight per scene',
    'bins':[0,.2,.4,.6,.8,1],'rounding':'nearest 5 percentage points',
    'release_gate':{'max_ece':.12,'max_mean_bias':.10,'max_brier_above_constant':.02,'min_groups_per_bin':5,'max_bin_gap':.15},
    'bootstrap':{'unit':'scene','repetitions':500,'seed':20261103},
    'limitations':'Retrospective Mediterranean satellite-reference study with 20 calibration and 21 test scene groups. Not field-measurement accuracy or a guarantee for an individual photo. Confidence fitting uses the base model validation split, and may reflect its epoch selection; the calibrator and test scenes remain separate. New regions and quality-rejected photos require separate evaluation.'}


def digest(value): return hashlib.sha256(json.dumps(value,sort_keys=True,allow_nan=False).encode()).hexdigest()
def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def freeze_protocol():
    p=ROOT/'results/confidence_protocol.json'
    if p.exists(): assert json.loads(p.read_text())==PROTOCOL_DATA, 'Protocol changed; do not retune after test inspection'
    else: p.write_text(json.dumps(PROTOCOL_DATA,indent=2)+'\n')


def feature_matrix(d,prediction_log10):
    return np.column_stack([prediction_log10,d.cloud_percent,d.water_fraction,d.sun_elevation,
        d.location_source.eq('earthmatch_verified').astype(float),np.log10(d.footprint_area_km2.clip(lower=1e-8))])


def fit(target):
    freeze_protocol()
    recipe='full' if target=='chlor_a' else 'partial'
    output=ROOT/'results'/f'{target}_confidence.json'
    if output.exists():
        print(json.dumps({'status':'already_frozen','target':target}));return
    checkpoint=ROOT/f'runs/{recipe}/checkpoints/{target}_convnext_tiny.pt'
    complete=ROOT/f'runs/{recipe}/results/{target}_convnext_tiny_fit.json'
    assert complete.exists(), 'Base model checkpoint selection must finish first'
    d=pd.read_csv(ROOT/'results/manifest.csv');old=pd.read_csv(WORKSPACE/'mediterranean_20261102/results/manifest.csv')
    assert d.image_id.tolist()==old.image_id.tolist()
    for key in ['group','timelapse_id','granule_file','decoded_pixel_sha256']:
        assert d.groupby(key).split.nunique().max()==1, key
    ids={split:np.flatnonzero(d.split.eq(split)) for split in ['train','validation','calibration','test']}
    group_sets={split:set(d.group.iloc[ix]) for split,ix in ids.items()}
    assert all(not (a&b) for i,a in enumerate(group_sets.values()) for b in list(group_sets.values())[i+1:])
    assert len(group_sets['calibration'])==20 and len(group_sets['test'])==21
    ppath=ROOT/f'runs/{recipe}/cache/{target}_convnext_tiny_predictions.npy'
    plog=np.load(ppath);prediction=10**plog;assert len(prediction)==len(d) and np.isfinite(prediction).all()
    labels=np.array([accurate(p,y) for p,y in zip(prediction,d[target])],dtype=int)
    features=feature_matrix(d,plog)
    v,c,t=ids['validation'],ids['calibration'],ids['test']
    assert len(np.unique(labels[v]))==len(np.unique(labels[c]))==2
    imputer=SimpleImputer(strategy='median',keep_empty_features=True)
    x=imputer.fit_transform(features[v]);scaler=StandardScaler().fit(x,sample_weight=group_weights(d.group.iloc[v].tolist()))
    score=LogisticRegression(C=1.,solver='lbfgs',max_iter=2000,random_state=20261103)
    score.fit(scaler.transform(x),labels[v],sample_weight=group_weights(d.group.iloc[v].tolist()))
    raw=score.decision_function(scaler.transform(imputer.transform(features)))
    cweights=np.asarray(group_weights(d.group.iloc[c].tolist()))
    cscale=StandardScaler().fit(raw[c,None],sample_weight=cweights)
    calibrator=LogisticRegression(C=1.,solver='lbfgs',max_iter=2000,random_state=20261103)
    calibrator.fit(cscale.transform(raw[c,None]),labels[c],sample_weight=cweights)
    probability=calibrator.predict_proba(cscale.transform(raw[:,None]))[:,1]
    fit_hashes={'base_checkpoint_sha256':sha(checkpoint),'base_predictions_sha256':sha(ppath),
        'metadata_preprocessor_sha256':sha(ROOT/'checkpoints/metadata_preprocessor.joblib'),
        'training_contract_sha256':sha(ROOT/'results/training_contract.json'),'confidence_protocol_sha256':sha(ROOT/'results/confidence_protocol.json')}
    coeff={'imputation':imputer.statistics_.tolist(),'feature_means':scaler.mean_.tolist(),'feature_scales':scaler.scale_.tolist(),
        'score_coef':score.coef_[0].tolist(),'score_intercept':float(score.intercept_[0]),
        'calibrator_mean':float(cscale.mean_[0]),'calibrator_scale':float(cscale.scale_[0]),
        'calibrator_coef':float(calibrator.coef_[0,0]),'calibrator_intercept':float(calibrator.intercept_[0])}
    calibration_id='confidence-'+target+'-'+digest({'hashes':fit_hashes,'coefficients':coeff})[:24]
    # The calibrator is now frozen; only evaluate the untouched test partition below.
    frozen={'id':calibration_id,'hashes':fit_hashes,'coefficients':coeff,'target':target,'protocol':PROTOCOL_DATA}
    (ROOT/'checkpoints'/f'{target}_confidence_frozen.json').write_text(json.dumps(frozen,indent=2)+'\n')
    joblib.dump({'imputer':imputer,'scaler':scaler,'score':score,'calibrator_scaler':cscale,'calibrator':calibrator},ROOT/'checkpoints'/f'{target}_confidence.joblib')
    report=reliability(probability[t].tolist(),labels[t].tolist(),d.group.iloc[t].tolist())
    const=float(np.average(labels[c],weights=cweights));tw=np.asarray(group_weights(d.group.iloc[t].tolist()))
    report['constant_baseline_brier']=float(np.average((const-labels[t])**2,weights=tw))
    report['constant_baseline_probability']=const
    # Bootstrap whole scenes, retaining all correlated frames within each draw.
    tg=d.group.iloc[t].to_numpy();unique=sorted(set(tg));rng=np.random.default_rng(20261103)
    boot_observed=[];boot_bias=[];bin_samples={b['index']:[] for b in report['bins']}
    for _ in range(500):
        sampled=rng.choice(unique,len(unique),replace=True);counts={g:int(np.sum(sampled==g)) for g in unique}
        w=tw*np.array([counts[g] for g in tg])
        boot_observed.append(float(np.average(labels[t],weights=w)))
        boot_bias.append(float(np.average(probability[t]-labels[t],weights=w)))
        for b in report['bins']:
            mask=np.minimum(4,(probability[t]*5).astype(int))==b['index']
            if w[mask].sum():bin_samples[b['index']].append(float(np.average(labels[t][mask],weights=w[mask])))
    report['observed_accuracy_95pct_scene_bootstrap']=np.quantile(boot_observed,[.025,.975]).tolist()
    report['mean_bias_95pct_scene_bootstrap']=np.quantile(boot_bias,[.025,.975]).tolist()
    gate=PROTOCOL_DATA['release_gate']
    release=(report['expected_calibration_error']<=gate['max_ece'] and abs(report['mean_confidence']-report['observed_accuracy'])<=gate['max_mean_bias']
        and report['brier_score']<=report['constant_baseline_brier']+gate['max_brier_above_constant'])
    for b in report['bins']:
        b['observed_accuracy_95pct_scene_bootstrap']=np.quantile(bin_samples[b['index']],[.025,.975]).tolist()
        b['release_eligible']=bool(release and b['groups']>=gate['min_groups_per_bin'] and b['absolute_gap']<=gate['max_bin_gap'])
    result={**frozen,'method':'scene_weighted_logistic_accuracy_score_with_independent_sigmoid_calibration',
        'calibration_groups':20,'calibration_photos':len(c),'score_fit_groups':12,'score_fit_photos':len(v),
        'validation':report,'release_eligible':bool(release),'limitations':PROTOCOL_DATA['limitations']}
    output.write_text(json.dumps(result,indent=2,allow_nan=False)+'\n')
    pd.DataFrame({'image_id':d.image_id,'group':d.group,'split':d.split,'prediction':prediction,
        'confidence_probability':probability,'within_25_percent':labels}).to_csv(ROOT/'results'/f'{target}_confidence_predictions.csv',index=False)
    print(json.dumps({'target':target,'release_eligible':release,'validation':report},indent=2),flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--target',choices=['chlor_a','kd_490']);p.add_argument('--freeze-only',action='store_true');a=p.parse_args()
    freeze_protocol()
    if not a.freeze_only:
        for target in ([a.target] if a.target else ['chlor_a','kd_490']):fit(target)
