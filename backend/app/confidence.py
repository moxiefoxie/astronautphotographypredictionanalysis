"""Audited probability of a numeric prediction meeting a stated error tolerance.

This is separate from a prediction interval. Only allowlisted, held-out estimates
from the exact frozen model/input can expose a saved confidence probability.
"""
import math
from .db import ModelVersion, InputAsset

PROTOCOL = 'appa-accuracy-probability-v1'
TOLERANCE = .25
DEFINITION = 'Estimated probability that the prediction is within ±25% of the quality-masked satellite reference.'


def accurate(prediction, reference, tolerance=TOLERANCE):
    if not all(math.isfinite(v) and v > 0 for v in [prediction, reference]):
        raise ValueError('Prediction and reference must be finite and positive')
    return abs(prediction / reference - 1) <= tolerance + 1e-12


def group_weights(groups):
    """Each scene receives equal total weight, regardless of its frame count."""
    counts = {}
    for g in groups: counts[g] = counts.get(g, 0) + 1
    return [1 / counts[g] for g in groups]


def reliability(probabilities, labels, groups):
    if not (len(probabilities) == len(labels) == len(groups)) or not groups:
        raise ValueError('Nonempty probability, outcome and group arrays must align')
    if any(not math.isfinite(p) or not 0 <= p <= 1 for p in probabilities):
        raise ValueError('Invalid confidence probability')
    weights = group_weights(groups); total = sum(weights)
    mean = lambda values: sum(w*v for w,v in zip(weights,values))/total
    bins = []
    for b in range(5):
        ids = [i for i,p in enumerate(probabilities) if min(4,int(p*5)) == b]
        if not ids: continue
        weight = sum(weights[i] for i in ids)
        predicted = sum(weights[i]*probabilities[i] for i in ids)/weight
        observed = sum(weights[i]*labels[i] for i in ids)/weight
        bins.append({'index':b,'lower':b/5,'upper':(b+1)/5,'photos':len(ids),
            'groups':len({groups[i] for i in ids}),'weight':weight,
            'predicted':predicted,'observed':observed,'absolute_gap':abs(predicted-observed)})
    return {'photos':len(groups),'groups':len(set(groups)), 'mean_confidence':mean(probabilities),
        'observed_accuracy':mean(labels),'brier_score':mean([(p-y)**2 for p,y in zip(probabilities,labels)]),
        'expected_calibration_error':sum(b['weight']*b['absolute_gap'] for b in bins)/total,'bins':bins}


def probability_from_features(features, coefficients):
    """Portable inference using only the numeric estimate and photo-derived inputs."""
    c = coefficients
    if len(features) != len(c['imputation']): raise ValueError('Confidence feature contract mismatch')
    filled = [c['imputation'][i] if v is None or not math.isfinite(v) else v for i,v in enumerate(features)]
    score = c['score_intercept'] + sum(w*(v-mean)/scale for w,v,mean,scale in zip(c['score_coef'],filled,c['feature_means'],c['feature_scales']))
    logit = c['calibrator_intercept'] + c['calibrator_coef']*(score-c['calibrator_mean'])/c['calibrator_scale']
    if logit >= 0: return 1/(1+math.exp(-logit))
    z = math.exp(logit)
    return z/(1+z)


def saved_confidence(s, estimate, photo):
    model = s.get(ModelVersion, estimate.model_id)
    calibration = model.manifest.get('confidence_calibration') if model else None
    if not calibration or calibration.get('protocol') != PROTOCOL: return None
    unavailable = lambda reason: {'status':'unavailable','reason':reason,'definition':DEFINITION}
    record = estimate.evidence.get('confidence_probability')
    if not record or not calibration.get('release_eligible'):
        return unavailable('This model’s confidence scores did not meet the held-out reliability checks.')
    if estimate.split not in (None, 'test') or estimate.role not in ('held_out_test','supplied_test_inference_only','unseen_inference'):
        return unavailable('Confidence calibration is not served for model-fitting or calibration images.')
    if estimate.scene_group not in calibration.get('serving_scene_ids', []) or estimate.scene_group in calibration.get('excluded_scene_ids', []):
        return unavailable('This scene was not held out from confidence fitting and calibration.')
    expected = calibration.get('eligible_estimates', {}).get(estimate.id)
    asset = s.get(InputAsset, estimate.evidence.get('input_asset_id'))
    if not expected or not asset or asset.photo_id != photo.id:
        return unavailable('This photo is outside the verified calibration release.')
    fields = {'photo_id':photo.id,'model_id':model.id,'target':estimate.target,'prediction':estimate.value,
        'input_asset_id':asset.id,'image_sha256':asset.image_sha256,'scene_group':estimate.scene_group,
        'calibration_id':calibration['id']}
    if any(record.get(k) != v or expected.get(k) != v for k,v in fields.items()):
        return unavailable('Confidence evidence does not match the current model, prediction or input crop.')
    probability = record.get('probability')
    if probability != expected.get('probability') or not isinstance(probability,(int,float)) or not math.isfinite(probability) or not 0 <= probability <= 1:
        return unavailable('Confidence probability failed verification.')
    try:
        features = record['features']
        if features != expected.get('features') or abs(features[0] - math.log10(estimate.value)) > 1e-10:
            return unavailable('Confidence inputs do not match the saved prediction.')
        replay = probability_from_features(features, calibration['coefficients'])
        if abs(replay-probability) > 1e-10:
            return unavailable('Confidence score did not reproduce from its saved photo inputs.')
    except (KeyError, IndexError, TypeError, ValueError, OverflowError, ZeroDivisionError):
        return unavailable('Confidence input contract could not be verified.')
    b = min(4,int(probability*5))
    evidence_bin = next((row for row in calibration['validation']['bins'] if row['index'] == b),None)
    if not evidence_bin or not evidence_bin.get('release_eligible'):
        return unavailable('Too little reliable held-out evidence supports this confidence level.')
    return {'status':'available','probability':probability,'display_percent':int(5*math.floor(probability*20+.5)),
        'tolerance_fraction':TOLERANCE,'definition':DEFINITION,'calibration_id':calibration['id'],
        'method':calibration['method'],'calibration_groups':calibration['calibration_groups'],
        'validation':{k:v for k,v in calibration['validation'].items() if k != 'bins'},
        'reliability_bin':evidence_bin,'limitations':calibration['limitations']}
