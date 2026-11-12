"""Scientific controls for the exploratory regional scoring calculation."""
import importlib.util
from pathlib import Path
import unittest

spec = importlib.util.spec_from_file_location('regional', Path(__file__).with_name('check-regional-inference.py'))
regional = importlib.util.module_from_spec(spec)
spec.loader.exec_module(regional)


class RegionalAuditTests(unittest.TestCase):
    boxes = [[0, 0, .5, .5], [.5, 0, 1, .5], [0, .5, .5, 1], [.5, .5, 1, 1]]
    reference = {'grid_log10': [[0, 0, 1, 1], [0, 0, 1, 1], [2, 2, 3, 3], [2, 2, 3, 3]]}

    def test_perfect_pattern_beats_flat_and_bias_is_separate(self):
        result = regional.audit_regions([0, 1, 2, 3], 1.5, self.boxes, self.reference)
        self.assertEqual(result['regional_log_mae'], 0)
        self.assertEqual(result['contrast_log_mae'], 0)
        self.assertEqual(result['whole_crop_log_mae'], 1)
        biased = regional.audit_regions([1, 2, 3, 4], 1.5, self.boxes, self.reference)
        self.assertEqual(biased['contrast_log_mae'], 0)
        self.assertEqual(biased['regional_log_mae'], 1)

    def test_flat_prediction_has_zero_spatial_skill(self):
        result = regional.audit_regions([1.5] * 4, 1.5, self.boxes, self.reference)
        self.assertEqual(result['regional_log_mae'], result['whole_crop_log_mae'])
        self.assertEqual(result['contrast_log_mae'], result['flat_contrast_log_mae'])

    def test_gaps_are_not_interpolated_or_scored(self):
        ref = {'grid_log10': [[None] * 4 for _ in range(4)]}
        result = regional.audit_regions([0, 1, 2, 3], 1.5, self.boxes, ref)
        self.assertFalse(result['scored'])
        self.assertEqual(result['supported_regions'], 0)


if __name__ == '__main__':
    unittest.main()
