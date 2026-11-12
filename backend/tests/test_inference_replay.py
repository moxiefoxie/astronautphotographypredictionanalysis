"""Optional real-checkpoint regression test, run with the existing ML environment."""
import unittest
import importlib.util
from sqlalchemy import select
from app.db import Session, Photo, Estimate, ModelVersion, Run

@unittest.skipUnless(importlib.util.find_spec('torch'), 'Run this test with the frozen ML environment')
class FrozenInferenceTest(unittest.TestCase):
    def test_predictions_match_frozen_outputs_across_splits(self):
        from app.inference import Predictor
        predictor = Predictor()
        with Session() as s:
            versions = [m for m in s.scalars(select(ModelVersion)).all() if m.manifest.get('benchmark') == 'sammy-20260923']
            self.assertEqual(len(versions), 2, 'Import the original benchmark first')
            frozen = select(Estimate).join(Run).where(Run.kind == 'benchmark_import')
            photos = []
            for split in ['train', 'validation', 'test']:
                ids = s.scalars(select(Estimate.photo_id).join(Run).where(Run.kind == 'benchmark_import', Estimate.split == split).distinct().order_by(Estimate.photo_id).limit(3)).all()
                self.assertEqual(len(ids), 3)
                photos.extend(s.get(Photo, photo_id) for photo_id in ids)
            expected = {(e.photo_id, e.target): e.value for e in s.scalars(frozen).all()}
        for photo in photos:
            for output in predictor.predict(photo, versions):
                with self.subTest(photo=photo.id, target=output['target']):
                    self.assertLess(abs(output['value'] / expected[photo.id, output['target']] - 1), 1e-5)

if __name__ == '__main__': unittest.main()
