import os
import tempfile
import time
import unittest
from unittest.mock import patch
from fastapi.testclient import TestClient
from sqlalchemy import select, func
from sqlalchemy.orm import sessionmaker
from app import main, queue
from app.db import make_engine, initialize, Photo, ModelVersion, Run, Matchup, Estimate, Job

class SystemTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.engine = make_engine('sqlite:///' + self.tmp.name + '/test.db')
        initialize(self.engine)
        self.sessions = sessionmaker(self.engine, expire_on_commit=False)
        self.patch = patch.object(main, 'Session', self.sessions)
        self.patch.start()
        self.client = TestClient(main.app)
        with self.sessions.begin() as s:
            s.add(Photo(id='ISS001-E-1', mission='ISS001', captured_at='2020-01-02T12:00:00Z', latitude=0., longitude=179.,
                thumbnail_url='https://eol.jsc.nasa.gov/image.jpg', image_url='https://eol.jsc.nasa.gov/image.jpg',
                original_url='https://eol.jsc.nasa.gov', local_image='/private/sensitive-path.png', metadata_json={}))
            s.add(ModelVersion(id='model-v1', target='chlor_a', name='test', units='mg/m³', manifest={'test_metrics': {}}))
            s.add(Run(id='r1', kind='benchmark_import', status='complete', provenance={}))
            s.flush()
            s.add(Matchup(id='match-v1', photo_id='ISS001-E-1', dataset_sha256='sha', data={'targets': {'chlor_a': {'value': 1.0}}}))
            s.flush()
            s.add(Estimate(id='p1', run_id='r1', photo_id='ISS001-E-1', model_id='model-v1', matchup_id='match-v1',
                           target='chlor_a', value=1.2, role='in_sample', split='train', scene_group='g1', evidence={}))

    def tearDown(self):
        self.client.close(); self.patch.stop(); self.engine.dispose(); self.tmp.cleanup()

    def request(self, key='test-key-123'):
        return queue.enqueue('ISS001-E-1', ['model-v1'], key, session_factory=self.sessions)

    def test_read_contract_and_no_local_paths(self):
        response = self.client.get('/api/photos/ISS001-E-1')
        self.assertEqual(response.status_code, 200)
        p = response.json()['predictions']['chlor_a']
        self.assertAlmostEqual(p['difference'], .2)
        self.assertIsNone(p['confidence'])
        self.assertEqual(p['split'], 'train')
        self.assertNotIn('/private/', response.text)
        self.assertNotIn('local_image', response.text)
        self.assertEqual(self.client.get('/api/photos/absent').status_code, 404)

    def test_database_outage_returns_retryable_error_without_connection_details(self):
        from sqlalchemy.exc import OperationalError
        with patch.object(main, 'Session', side_effect=OperationalError('private SQL', {}, RuntimeError('private connection details'))):
            response = self.client.get('/api/health')
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.headers['Retry-After'], '60')
        self.assertNotIn('private', response.text)

    def test_filters_pagination_and_validation(self):
        for query, count in [('q=ISS001', 1), ('q=none', 0), ('split=test', 0), ('split=train', 1),
            ('satellite=false', 0), ('prediction=true', 1), ('start=2020-01-02&end=2020-01-02', 1),
            ('start=2020-01-03', 0), ('west=170&east=-170', 1), ('q=%25', 0)]:
            self.assertEqual(self.client.get('/api/photos?' + query).json()['total'], count, query)
        for query in ['limit=1000', 'offset=-1', 'start=bad', 'start=2021-01-01&end=2020-01-01', 'north=-30&south=30']:
            self.assertEqual(self.client.get('/api/photos?' + query).status_code, 422)
        self.assertEqual(self.client.get('/api/photos?offset=10').json()['items'], [])

    def test_operator_auth_fails_closed(self):
        body = {'photo_id': 'ISS001-E-1', 'model_ids': ['model-v1']}
        with patch.dict(os.environ, {'OPERATOR_API_KEY': ''}):
            self.assertEqual(self.client.post('/api/jobs', json=body, headers={'Idempotency-Key': 'test-key-123'}).status_code, 503)
        with patch.dict(os.environ, {'OPERATOR_API_KEY': 'secret-test'}):
            self.assertEqual(self.client.post('/api/jobs', json=body, headers={'Idempotency-Key': 'test-key-123'}).status_code, 401)
            with patch.object(main, 'enqueue', side_effect=lambda *a: queue.enqueue(*a, session_factory=self.sessions)):
                response = self.client.post('/api/jobs', json=body, headers={'Idempotency-Key': 'test-key-123', 'Authorization': 'Bearer secret-test'})
                self.assertEqual(response.status_code, 202)

    def test_radius_filters_across_date_line_before_pagination(self):
        with self.sessions.begin() as s:
            for i, (lat, lon) in enumerate([(0, -179), (0, 170), (None, None), (89.9, 90)]):
                s.add(Photo(id=f'ISS001-E-{i+2}', mission='ISS001', captured_at='2020-01-01T00:00:00Z',
                    latitude=lat, longitude=lon, thumbnail_url='', image_url='', original_url='', metadata_json={}))
        query = '/api/photos?latitude=0&longitude=180&radius_km=150&limit=1'
        first = self.client.get(query).json()
        self.assertEqual(first['total'], 2)
        second = self.client.get(query+'&offset=1').json()
        self.assertNotEqual(first['items'][0]['id'], second['items'][0]['id'])
        self.assertEqual(self.client.get(query+'&west=178&east=180').json()['total'], 1)
        self.assertEqual(self.client.get('/api/photos?latitude=90&longitude=-90&radius_km=20').json()['total'], 1)
        for invalid in ['latitude=0', 'latitude=0&longitude=0', 'latitude=0&longitude=0&radius_km=0',
                        'latitude=91&longitude=0&radius_km=1', 'latitude=0&longitude=nan&radius_km=1']:
            self.assertEqual(self.client.get('/api/photos?'+invalid).status_code, 422, invalid)

    def test_focal_enrichment_preserves_source_metadata(self):
        with patch.dict(main.NASA_METADATA, {'ISS001-E-1': {'focal_length': 24, 'focal_length_source': 'NASA'}}):
            self.assertEqual(self.client.get('/api/photos/ISS001-E-1').json()['metadata']['focal_length'], 24)
            with self.sessions() as s:
                self.assertEqual(s.get(Photo, 'ISS001-E-1').metadata_json, {})
            with self.sessions.begin() as s:
                s.get(Photo, 'ISS001-E-1').metadata_json = {'focal_length': 50}
            self.assertEqual(self.client.get('/api/photos/ISS001-E-1').json()['metadata']['focal_length'], 50)

    def test_saved_only_models_cannot_create_jobs(self):
        with self.sessions.begin() as s:
            model = s.get(ModelVersion, 'model-v1')
            model.manifest = {**model.manifest, 'serving_enabled': False}
        with self.assertRaisesRegex(ValueError, 'saved predictions only'):
            self.request()
        with self.sessions() as s:
            self.assertEqual(s.scalar(select(func.count()).select_from(Job)), 0)

    def test_wrong_input_contract_cannot_create_jobs(self):
        with self.sessions.begin() as s:
            s.get(Photo, 'ISS001-E-1').metadata_json = {'input_contract': 'mediterranean-20261102'}
        with self.assertRaisesRegex(ValueError, 'input contract'):
            self.request()

    def test_idempotency_survives_new_session(self):
        a, b = self.request(), self.request()
        self.assertEqual(a.id, b.id)
        with self.sessions() as s:
            self.assertEqual(s.scalar(select(func.count()).select_from(Job)), 1)
        with self.assertRaises(ValueError):
            queue.enqueue('ISS001-E-1', ['different'], 'test-key-123', session_factory=self.sessions)

    def test_expired_lease_recovery_and_fencing(self):
        self.request()
        first = queue.claim(self.sessions, now=time.time() - queue.LEASE_SECONDS - 1)
        second = queue.claim(self.sessions)
        self.assertEqual(second.id, first.id)
        self.assertEqual(second.attempts, 2)
        self.assertNotEqual(first.lease_token, second.lease_token)
        self.assertFalse(queue.finish(first, error='stale', session_factory=self.sessions))
        self.assertIsNone(queue.claim(self.sessions))
        self.assertTrue(queue.finish(second, [{'model_id':'model-v1', 'target':'chlor_a', 'value':1.25, 'evidence':{'source':'checkpoint_inference'}}], session_factory=self.sessions))
        with self.sessions() as s:
            outputs = s.scalars(select(Estimate).where(Estimate.run_id == second.run_id)).all()
            self.assertEqual(len(outputs), 1)
            self.assertEqual(outputs[0].split, 'train')
            self.assertEqual(outputs[0].role, 'in_sample')
            self.assertEqual(outputs[0].matchup_id, 'match-v1')
        self.assertFalse(queue.finish(second, error='duplicate', session_factory=self.sessions))

    def test_retry_limit(self):
        self.request()
        for i in range(3):
            job = queue.claim(self.sessions, now=time.time() - (3 - i) * (queue.LEASE_SECONDS + 1))
            self.assertEqual(job.attempts, i + 1)
        self.assertIsNone(queue.claim(self.sessions))
        with self.sessions() as s:
            self.assertEqual(s.get(Job, job.id).status, 'failed')
            self.assertEqual(s.get(Run, job.run_id).status, 'failed')

    def test_atomic_completion_rolls_back_on_missing_outputs(self):
        self.request(); job = queue.claim(self.sessions)
        with self.assertRaises(ValueError): queue.finish(job, [], session_factory=self.sessions)
        with self.sessions() as s:
            self.assertEqual(s.get(Job, job.id).status, 'running')
            self.assertEqual(s.get(Run, job.run_id).status, 'running')

    def test_concurrent_workers_claim_only_once(self):
        from concurrent.futures import ThreadPoolExecutor
        self.request()
        with ThreadPoolExecutor(max_workers=6) as pool:
            claimed = list(pool.map(lambda _: queue.claim(self.sessions), range(6)))
        self.assertEqual(sum(job is not None for job in claimed), 1)

    def test_invalid_worker_output_rolls_back(self):
        self.request(); job = queue.claim(self.sessions)
        for value in [float('nan'), float('inf'), -1.0, 0.0]:
            with self.assertRaises(ValueError):
                queue.finish(job, [{'model_id': 'model-v1', 'target': 'chlor_a', 'value': value, 'evidence': {}}], session_factory=self.sessions)
        with self.sessions() as s:
            self.assertEqual(s.get(Job, job.id).status, 'running')

    def test_identical_pixels_do_not_become_unseen_under_new_id(self):
        with self.sessions.begin() as s:
            s.get(Photo, 'ISS001-E-1').image_sha256 = 'identical-pixels'
            s.add(Photo(id='ISS001-E-2', mission='ISS001', thumbnail_url='https://eol.jsc.nasa.gov/2.jpg',
                image_url='https://eol.jsc.nasa.gov/2.jpg', original_url='https://eol.jsc.nasa.gov',
                image_sha256='identical-pixels', metadata_json={}))
        queue.enqueue('ISS001-E-2', ['model-v1'], 'duplicate-pixels', session_factory=self.sessions)
        job = queue.claim(self.sessions)
        queue.finish(job, [{'model_id':'model-v1', 'target':'chlor_a', 'value':1.25, 'evidence':{}}], session_factory=self.sessions)
        with self.sessions() as s:
            output = s.scalar(select(Estimate).where(Estimate.photo_id == 'ISS001-E-2'))
            self.assertEqual(output.split, 'train')
            self.assertEqual(output.role, 'in_sample')
            self.assertIsNone(output.matchup_id)

    def test_worker_spatial_completion_does_not_discard_scalar_outputs(self):
        from app.worker import run_one
        class Predictor:
            def predict(self, photo, models):
                return [{'model_id':'model-v1', 'target':'chlor_a', 'value':1.25, 'evidence':{}}]
        class Spatial:
            def __init__(self, fail=False): self.fail=fail
            def generate(self, photo, sessions):
                if self.fail: raise ValueError('Test-only spatial failure')
                return 2
        for fail in [False,True]:
            job=self.request('worker-spatial-'+str(fail))
            with self.assertLogs(level='INFO'):
                run_one(Predictor(),self.sessions,Spatial(fail))
            with self.sessions() as s:
                self.assertEqual(s.get(Job,job.id).status,'complete')
                self.assertEqual(s.get(Run,job.run_id).provenance['overlay_status'],
                                 'failed; retry with app.overlays' if fail else 'complete')
                self.assertEqual(s.scalar(select(func.count()).select_from(Estimate).where(Estimate.run_id==job.run_id)),1)

if __name__ == '__main__': unittest.main()
