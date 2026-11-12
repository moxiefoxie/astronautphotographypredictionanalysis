"""Read-only end-to-end audit of imported scientific values against frozen exports."""
import json
import math
from sqlalchemy import select, func
from .db import WORKSPACE, Session, Run, Estimate, Matchup, InputAsset, CatalogSnapshot
from .import_benchmark import rows
from .import_mediterranean import MASK_FLAGS


def verify(session_factory=Session):
    expected = {r['photo_id']: r for r in rows(WORKSPACE/'mediterranean_20261102/all_test/results/selected_full_test_predictions.csv')}
    with session_factory() as s:
        run = s.scalar(select(Run).where(Run.kind == 'mediterranean_import').order_by(Run.created_at.desc()))
        assert run and run.status == 'complete', 'Missing complete import'
        estimates = s.scalars(select(Estimate).where(Estimate.run_id == run.id)).all()
        assert len(estimates) == len(expected)*2
        assets = {a.id: a for a in s.scalars(select(InputAsset))}
        matches = {m.id: m for m in s.scalars(select(Matchup))}
        snapshots = set(s.scalars(select(CatalogSnapshot.id)))
        seen = set(); refs = set()
        for e in estimates:
            key = (e.photo_id,e.target)
            assert key not in seen; seen.add(key)
            row = expected[e.photo_id]
            assert math.isclose(e.value,float(row[e.target+'_prediction']),rel_tol=1e-12)
            assert e.split == 'test'
            assert e.evidence['reference_status'] == row['reference_status']
            asset = assets[e.evidence['input_asset_id']]
            assert asset.photo_id == e.photo_id and asset.image_sha256 == e.evidence['image_sha256']
            assert e.evidence['catalog_snapshot_id'] in snapshots
            assert asset.provenance['metadata']['input_contract'] == 'mediterranean-20261102'
            if row['benchmark_eligible'] == 'True':
                m = matches[e.matchup_id]; refs.add(e.photo_id)
                assert math.isclose(m.data['targets'][e.target]['value'],float(row[e.target+'_reference']),rel_tol=1e-10)
                assert m.data['mask_flags'] == MASK_FLAGS
                assert m.data['overlap_fraction'] >= .9 and m.data['delta_minutes'] <= 180
            else:
                assert e.matchup_id is None and e.role == 'supplied_test_inference_only'
        assert len(refs) == 2624 and len(expected)-len(refs) == 5047
        return {'status':'passed','run_id':run.id,'photos':len(expected),'estimates':len(estimates),
                'usable_references':len(refs),'inference_only':len(expected)-len(refs),
                'all_values_match_frozen_export':True,'versioned_inputs_verified':True}


if __name__ == '__main__':
    print(json.dumps(verify(),indent=2))
