"""Check model/input parity of every pilot layer and optionally the public API."""
import argparse
import json
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def verify(live=False):
    records = json.loads((ROOT/'runtime/pilot-calibrated-records.json').read_text())
    estimates = {(e['photo_id'],e['target']):e for e in records['estimates']}
    assets = {a['photo_id']:a for a in records['input_assets']}
    models = {m['id']:m for m in records['model_versions']}
    index = json.loads((ROOT/'src/evidence-pilot.json').read_text())
    unmatched = []; maximum_error = 0
    for pid, entry in index.items():
        data = json.loads((ROOT/'public'/entry['url'].lstrip('/')).read_text())
        assert data['input_asset_id'] == assets[pid]['id'] == entry['asset_id']
        assert data['source_sha256'] == assets[pid]['image_sha256'] == entry['source_sha256']
        if data['reference'] is None:
            unmatched.append(pid)
            assert all(estimates[pid,t]['matchup_id'] is None for t in ['chlor_a','kd_490'])
        for target, layer in data['sensitivity'].items():
            expected = estimates[pid,target]
            assert layer['model_id'] == expected['model_id'] == entry['model_ids'][target]
            assert layer['saved_value'] == expected['value']
            error = abs(math.log10(layer['replayed_value']/expected['value']))
            assert error <= 2e-4
            maximum_error = max(maximum_error,error)
            assert len(layer['tile_boxes']) == len(layer['occluded_values']) == len(layer['delta_log10']) == 16
            assert all(math.isfinite(v) and v > 0 for v in layer['occluded_values'])
    report = {'pilot_photos':len(index),'without_reference':unmatched,'max_replay_log10_error':maximum_error}
    if live:
        import httpx
        chosen = list(unmatched) + [next(pid for pid in index if pid not in unmatched)]
        # Also exercise a score that the held-out reliability gate rejected.
        for e in estimates.values():
            c = models[e['model_id']]['manifest'].get('confidence_calibration')
            if not c: continue
            probability = e['evidence']['confidence_probability']['probability']
            band = next(b for b in c['validation']['bins'] if b['index'] == min(4,int(probability*5)))
            if not band['release_eligible']:
                chosen.append(e['photo_id']);break
        checked=[]
        with httpx.Client(timeout=40) as client:
            for pid in dict.fromkeys(chosen):
                response=client.get('https://appa-api.vercel.app/api/photos/'+pid);response.raise_for_status();photo=response.json()
                result={'photo':pid,'targets':{}}
                for target in ['chlor_a','kd_490']:
                    expected=estimates[pid,target];actual=photo['predictions'][target]
                    assert actual['model']['id']==expected['model_id'] and actual['value']==expected['value']
                    assert (actual['satellite'] is None)==(expected['matchup_id'] is None)
                    c=models[expected['model_id']]['manifest'].get('confidence_calibration')
                    if c:
                        probability=expected['evidence']['confidence_probability']['probability']
                        band=next(b for b in c['validation']['bins'] if b['index']==min(4,int(probability*5)))
                        assert actual['confidence']['status']==('available' if band['release_eligible'] else 'unavailable')
                        if band['release_eligible']:assert actual['confidence']['probability']==probability
                    result['targets'][target]={'value':actual['value'],'confidence':actual['confidence'],'has_reference':actual['satellite'] is not None}
                checked.append(result)
        report['public_checks']=checked
    (ROOT/'runtime/confidence-release-verification.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({k:v for k,v in report.items() if k!='public_checks'},indent=2))
    if live:print('Public model, prediction, optional reference and confidence parity verified for',len(checked),'photos.')


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--live',action='store_true');verify(parser.parse_args().live)
