import unittest
from app.nasa_metadata import parse_focal_length

class NasaMetadataTests(unittest.TestCase):
    def test_nasa_table_variants_and_missing_values(self):
        self.assertEqual(parse_focal_length('<tr><td><a href="/FAQ#focalLength">Focal Length</a></td><td>24mm</td></tr>'), 24)
        self.assertEqual(parse_focal_length('<tr><td><b>Focal Length:</b></td><td>70.5&nbsp;mm</td></tr>'), 70.5)
        self.assertIsNone(parse_focal_length('<a>Focal Length</a><p>50mm lens example</p>'))
        self.assertIsNone(parse_focal_length('<tr><td>Focal Length</td><td>Not recorded</td></tr>'))
        self.assertIsNone(parse_focal_length('<tr><td>Focal Length</td><td>0mm</td></tr>'))
