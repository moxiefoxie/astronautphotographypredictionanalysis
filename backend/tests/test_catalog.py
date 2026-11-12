import csv
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from PIL import Image
from sqlalchemy import select, func
from sqlalchemy.orm import sessionmaker
from app import catalog
from app.db import make_engine, initialize, Photo

class CatalogTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name).resolve()
        self.engine = make_engine('sqlite:///' + str(self.root / 'db.sqlite'))
        initialize(self.engine)
        self.sessions = sessionmaker(self.engine, expire_on_commit=False)
        Image.new('RGB', (32, 32), (20, 80, 120)).save(self.root / 'photo.png')
        self.row = {'image_id':'ISS099-E-123', 'local_image':'photo.png', 'captured_at':'2025-01-01T00:00:00Z',
                    'latitude':'10', 'longitude':'20', 'cloud_percent':'10', 'sun_elevation':'20'}
        self.patcher = patch.object(catalog, 'WORKSPACE', self.root)
        self.patcher.start()
    def tearDown(self):
        self.patcher.stop(); self.engine.dispose(); self.tmp.cleanup()
    def write(self, rows):
        path = self.root / 'catalog.csv'
        with path.open('w', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=list(self.row)); writer.writeheader(); writer.writerows(rows)
        return path
    def test_ingest_is_idempotent_and_needs_no_satellite_label(self):
        path = self.write([self.row])
        self.assertEqual(catalog.ingest(path, self.sessions)['added'], 1)
        self.assertEqual(catalog.ingest(path, self.sessions)['added'], 0)
        with self.sessions() as s:
            self.assertIsNotNone(s.get(Photo, self.row['image_id']).image_sha256)
    def test_rejects_outside_paths_night_clouds_and_invalid_coordinates(self):
        for change in [{'local_image':'../outside.png'}, {'sun_elevation':'-10'}, {'cloud_percent':'50'},
                       {'latitude':'100'}, {'captured_at':'2025-01-01T00:00:00'}]:
            with self.subTest(change=change), self.assertRaises(ValueError):
                catalog.ingest(self.write([{**self.row, **change}]), self.sessions)
    def test_whole_import_is_atomic(self):
        with self.assertRaises(ValueError):
            catalog.ingest(self.write([self.row, {**self.row, 'image_id':'bad'}]), self.sessions)
        with self.sessions() as s:
            self.assertEqual(s.scalar(select(func.count()).select_from(Photo)), 0)

if __name__ == '__main__': unittest.main()
