import base64
import hashlib
import os
import tempfile
import unittest
from unittest.mock import patch
from fastapi.testclient import TestClient
from sqlalchemy.orm import sessionmaker
from app import main
from app.db import make_engine, initialize, Photo, ModelVersion, Run, Estimate, Overlay, Calibration, AnnotationRevision
from app.calibration import Cohort, fit, radius, interval

class SpatialTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.engine = make_engine('sqlite:///' + self.tmp.name + '/test.db'); initialize(self.engine)
        self.sessions = sessionmaker(self.engine, expire_on_commit=False)
        self.patch = patch.object(main, 'Session', self.sessions); self.patch.start()
        self.client = TestClient(main.app)
        with self.sessions.begin() as s:
            s.add(ModelVersion(id='model', target='chlor_a', name='test-only', units='mg/m³', manifest={}))
            s.add(Run(id='r', kind='test', status='complete', provenance={})); s.flush()
            for i in range(22):
                s.add(Photo(id=f'p{i}', mission='test', thumbnail_url='https://example.com', image_url='https://example.com', original_url='https://example.com',
                    image_sha256=hashlib.sha256(str(i).encode()).hexdigest(), metadata_json={
                        'scene_group': f'g{i}', 'calibration_domain': 'test-domain', 'independence_review': 'Synthetic test-only independent scene'}))
            s.flush()
            for i in range(22): s.add(Estimate(id=f'e{i}', photo_id=f'p{i}', model_id='model', run_id='r', target='chlor_a', value=2., role='unseen_inference', evidence={}))
            s.add(Overlay(id='overlay', photo_id='p0', target='chlor_a', image_sha256=hashlib.sha256(b'0').hexdigest(), model_version='spatial-v1',
                manifest={'status': 'experimental', 'pixel_accuracy_validated': False}, payload={'png_base64': base64.b64encode(b'png-test').decode(), 'source_png_base64': base64.b64encode(b'original-test').decode(), 'log10_grid': [[1., None]]}))
        self.body = {'id': 'review-1234', 'base_revision': 0, 'image_sha256': hashlib.sha256(b'0').hexdigest(), 'reviewer':'Test reviewer',
                     'regions':[{'label':'water', 'points': [[.1,.1],[.8,.1],[.5,.8]]}]}
        self.cohort = Cohort(model_id='model', domain='test-domain', independence_review='Synthetic test cohort; each scene is separate for unit-test purposes.',
            grouping_protocol='Group by synthetic scene ID, sharing neither images nor satellite granules.', reference_kind='quality_masked_satellite_geometric_mean',
            rows=[{'estimate_id': f'e{i}', 'scene_group': f'g{i}', 'reference':1., 'granule_id': f'granule{i}', 'reference_source':'synthetic test', 'reference_sha256':'a'*64} for i in range(20)])
    def tearDown(self):
        self.client.close(); self.patch.stop(); self.engine.dispose(); self.tmp.cleanup()
    def post(self, body=None):
        with patch.dict(os.environ, {'OPERATOR_API_KEY':'test'}):
            return self.client.post('/api/photos/p0/annotations', json=body or self.body, headers={'Authorization':'Bearer test'})
    def test_overlay_portable_assets_and_no_binary_in_listing(self):
        listing = self.client.get('/api/photos/p0/overlays').json()
        self.assertFalse(listing['items'][0]['pixel_accuracy_validated'])
        self.assertNotIn('payload', listing['items'][0])
        self.assertEqual(self.client.get('/api/overlays/overlay/source.png').content, b'original-test')
        self.assertEqual(self.client.get('/api/overlays/overlay/values').json()['log10_grid'], [[1.,None]])
        with self.sessions.begin() as s: s.get(Photo,'p0').image_sha256 = 'b'*64
        self.assertEqual(self.client.get('/api/photos/p0/overlays').json()['items'], [])
    def test_annotation_revision_idempotency_conflict_and_history(self):
        self.assertEqual(self.post().json()['revision'],1)
        self.assertEqual(self.post().json()['revision'],1)
        self.assertEqual(self.post({**self.body,'id':'review-5678'}).status_code,409)
        self.assertEqual(self.post({**self.body,'id':'review-5678','base_revision':1,'regions':[]}).json()['revision'],2)
        rows = self.client.get('/api/photos/p0/annotations').json()['items']
        self.assertEqual([r['revision'] for r in rows],[2,1]); self.assertEqual(rows[1]['regions'],self.body['regions'])
    def test_invalid_coordinates_intersections_auth_and_hash(self):
        for points in [[[0,0],[1,1],[0,1],[1,0]], [[0,0],[0,0],[1,1]], [[0,0],[2,0],[0,1]], [[0,0],[.5,.5],[1,1]]]:
            self.assertEqual(self.post({**self.body,'regions':[{'label':'water','points':points}]}).status_code,422)
        self.assertEqual(self.post({**self.body,'image_sha256':'b'*64}).status_code,409)
        with patch.dict(os.environ, {'OPERATOR_API_KEY':'test'}):
            self.assertEqual(self.client.post('/api/photos/p0/annotations',json=self.body).status_code,401)
    def test_finite_sample_rank(self):
        self.assertEqual(radius(list(range(20)),.9),18)
        with self.assertRaises(ValueError): radius([1,2],.9)
    def test_fit_interval_and_exclusion_of_calibration_scenes(self):
        cid = fit(self.cohort,self.sessions); self.assertEqual(fit(self.cohort,self.sessions),cid)
        with self.sessions() as s:
            c = s.get(Calibration,cid); self.assertAlmostEqual(c.log_radius,.3010299956639812)
            result = interval(s,s.get(Estimate,'e20'),s.get(Photo,'p20'))
            self.assertEqual(result['status'],'available'); self.assertAlmostEqual(result['lower'],1.); self.assertAlmostEqual(result['upper'],4.)
            self.assertEqual(interval(s,s.get(Estimate,'e0'),s.get(Photo,'p0'))['status'],'unavailable')
    def test_benchmark_overlap_rejected(self):
        with self.sessions.begin() as s: s.get(Estimate,'e0').split='validation'
        with self.assertRaises(ValueError): fit(self.cohort,self.sessions)
    def test_renamed_duplicate_image_rejected(self):
        with self.sessions.begin() as s:
            s.get(Estimate,'e21').split='train'; s.get(Photo,'p21').image_sha256=hashlib.sha256(b'0').hexdigest()
        with self.assertRaises(ValueError): fit(self.cohort,self.sessions)
    def test_shared_granule_cannot_inflate_group_count(self):
        cohort = self.cohort.model_copy(deep=True); cohort.rows[1].granule_id='granule0'
        with self.assertRaises(ValueError): fit(cohort,self.sessions)
    def test_missing_review_and_wrong_domain_suppress_interval(self):
        fit(self.cohort,self.sessions)
        with self.sessions.begin() as s:
            p=s.get(Photo,'p20'); p.metadata_json={**p.metadata_json,'calibration_domain':'different'}
            self.assertEqual(interval(s,s.get(Estimate,'e20'),p)['status'],'unavailable')
            p.metadata_json={}; self.assertEqual(interval(s,s.get(Estimate,'e20'),p)['status'],'unavailable')

if __name__ == '__main__': unittest.main()
