import math
import tempfile
import unittest
from sqlalchemy.orm import sessionmaker
from app.db import make_engine, initialize, Photo, ModelVersion, Run, Estimate, InputAsset, Matchup
from app.confidence import accurate, group_weights, reliability, saved_confidence, PROTOCOL, probability_from_features

class ConfidenceTests(unittest.TestCase):
    def test_tolerance_is_relative_to_reference_and_inclusive(self):
        self.assertTrue(accurate(.75,1));self.assertTrue(accurate(1.25,1))
        self.assertFalse(accurate(.74,1));self.assertFalse(accurate(1.26,1))
        with self.assertRaises(ValueError):accurate(float('nan'),1)
        with self.assertRaises(ValueError):accurate(1,0)

    def test_adjacent_frames_do_not_inflate_scene_weight(self):
        r=reliability([.8]*100+[.2],[True]*100+[False],['many']*100+['one'])
        self.assertAlmostEqual(r['observed_accuracy'],.5)
        self.assertAlmostEqual(r['mean_confidence'],.5)
        self.assertAlmostEqual(sum(group_weights(['many']*100)),1)
        self.assertEqual(r['groups'],2)
        self.assertAlmostEqual(r['expected_calibration_error'],.2)

    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.engine=make_engine('sqlite:///'+self.tmp.name+'/test.db');initialize(self.engine)
        self.sessions=sessionmaker(self.engine,expire_on_commit=False)
        record={'photo_id':'p','model_id':'m','target':'chlor_a','prediction':1.,'input_asset_id':'a',
            'image_sha256':'a'*64,'scene_group':'test','calibration_id':'c','probability':.72,'features':[0.,0.,1.,45.,1.,2.]}
        coefficients={'imputation':[0.]*6,'feature_means':[0.]*6,'feature_scales':[1.]*6,'score_coef':[0.]*6,'score_intercept':0.,'calibrator_mean':0.,'calibrator_scale':1.,'calibrator_coef':1.,'calibrator_intercept':math.log(.72/.28)}
        calibration={'coefficients':coefficients,'protocol':PROTOCOL,'id':'c','release_eligible':True,'serving_scene_ids':['test'],
            'excluded_scene_ids':['calibration'],'eligible_estimates':{'e':record},'calibration_groups':20,
            'method':'test','limitations':'test only','validation':{'groups':21,'bins':[{'index':3,'release_eligible':True,'groups':12}]}}
        with self.sessions.begin() as s:
            s.add(ModelVersion(id='m',target='chlor_a',name='synthetic',units='mg/m³',manifest={'confidence_calibration':calibration}))
            s.add(Photo(id='p',mission='test',image_url='',thumbnail_url='',original_url='',metadata_json={}))
            s.add(Run(id='r',kind='test',status='complete',provenance={}));s.flush()
            s.add(InputAsset(id='a',photo_id='p',image_sha256='a'*64,kind='registered_crop',provenance={}))
            s.add(Matchup(id='reference',photo_id='p',dataset_sha256='s',data={}));s.flush()
            s.add(Estimate(id='e',photo_id='p',run_id='r',model_id='m',matchup_id='reference',target='chlor_a',value=1.,
                role='held_out_test',split='test',scene_group='test',evidence={'input_asset_id':'a','confidence_probability':record}))
    def tearDown(self):self.engine.dispose();self.tmp.cleanup()
    def result(self,s):return saved_confidence(s,s.get(Estimate,'e'),s.get(Photo,'p'))

    def test_verified_saved_probability_and_display_rounding(self):
        with self.sessions() as s:
            r=self.result(s);self.assertEqual(r['status'],'available');self.assertEqual(r['probability'],.72);self.assertEqual(r['display_percent'],70)

    def test_changed_prediction_crop_or_scene_fails_closed(self):
        for field,value in [('value',2.),('scene_group','calibration'),('split','train')]:
            with self.sessions.begin() as s:
                e=s.get(Estimate,'e');old=getattr(e,field);setattr(e,field,value)
                self.assertEqual(self.result(s)['status'],'unavailable',field);setattr(e,field,old)
        with self.sessions.begin() as s:
            s.get(InputAsset,'a').image_sha256='b'*64
            self.assertEqual(self.result(s)['status'],'unavailable')

    def test_reference_is_not_required_at_prediction_time(self):
        with self.sessions.begin() as s:
            e=s.get(Estimate,'e');e.matchup_id=None;e.role='supplied_test_inference_only'
            self.assertEqual(self.result(s)['status'],'available')

    def test_unsupported_reliability_bin_cannot_claim_confidence(self):
        with self.sessions.begin() as s:
            m=s.get(ModelVersion,'m');manifest=dict(m.manifest);c=dict(manifest['confidence_calibration']);c['validation']={'bins':[{'index':3,'release_eligible':False}]};m.manifest={**manifest,'confidence_calibration':c}
            self.assertEqual(self.result(s)['status'],'unavailable')

    def test_corrupt_confidence_feature_vector_fails_closed(self):
        with self.sessions.begin() as s:
            e=s.get(Estimate,'e'); evidence=dict(e.evidence)
            record={**evidence['confidence_probability'],'features':[]}
            e.evidence={**evidence,'confidence_probability':record}
            m=s.get(ModelVersion,'m');c=dict(m.manifest['confidence_calibration'])
            c['eligible_estimates']={'e':record};m.manifest={**m.manifest,'confidence_calibration':c}
            self.assertEqual(self.result(s)['status'],'unavailable')

    def test_legacy_models_remain_unscored(self):
        with self.sessions.begin() as s:
            s.get(ModelVersion,'m').manifest={};self.assertIsNone(self.result(s))
