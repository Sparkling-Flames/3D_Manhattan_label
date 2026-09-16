"""Computational and source tests; these are not independent human validation."""
from pathlib import Path
import collections,hashlib,inspect,itertools,json,unittest
import numpy as np
import pandas as pd
from tools.thesis_main.analysis.image_portrait import person_distribution_hypothesis_v1 as c
from tools.thesis_main.analysis.image_portrait.person_distribution_run_v1 import CachedLearner,ReferenceLearner
from tools.thesis_main.analysis.image_portrait.person_distribution_resume_v1 import paired_exact
from tools.thesis_main.analysis.image_portrait.person_distribution_online_v1 import predict_candidates,sample_world
from tools.thesis_main.analysis.image_portrait.person_distribution_growth_v1 import matrix,clusters,trajectory
from tools.thesis_main.analysis.image_portrait.person_distribution_mode_shares_v1 import endstats

class PersonDistributionTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.out=Path(c.OUT_DEFAULT)
  cls.s,cls.pools,cls.bank,cls.raw,cls.meta,cls.workers=c.prepare(cls.out)
  cls.g=next(g for g in cls.pools if g['condition']=='manual'and len(g['ids'])>=12 and g['model_points'])
  cls.train=[g for g in cls.pools if g['condition']=='manual'and g['building']!=cls.g['building']and len(g['ids'])>=2]
  cls.L=CachedLearner(cls.train,cls.meta,cls.workers,[cls.g['building']])
  cls.seeds=[dict(worker_id=cls.g['workers'][j],canonical_id=cls.g['ids'][j],points=cls.g['points'][j].tolist())for j in range(4)]
  cls.recipients=cls.g['workers'][4:8]
 def test_01_frozen_building_isolation(self):
  for f in json.loads((self.out/'folds.json').read_text()):
   self.assertFalse(set(f['training_images'])&set(f['target_images']))
   self.assertTrue(all(i.split('_')[0]!=f['building']for i in f['training_images']))
 def test_02_worker_exclusions_and_W011(self):
  people={w for g in self.pools for w in g['workers']};self.assertNotIn('W019',people);self.assertNotIn('W026',people);self.assertIn('W011',people)
 def test_03_real_response_identity_uniqueness(self):
  for g in self.pools:self.assertEqual(len(g['workers']),len(set(g['workers'])));self.assertEqual(len(g['ids']),len(set(g['ids'])))
 def test_04_prediction_api_has_no_hidden_answer_input(self):
  args=inspect.signature(predict_candidates).parameters
  self.assertEqual(set(args),{'learner','image_id','condition','model_candidates','seed_records','recipient_workers','method','temperature','alpha'})
 def test_05_online_probabilities(self):
  for name in ('equal','personal','context','type2','type3','type4'):
   p=predict_candidates(self.L,self.g['image_id'],'manual',[],self.seeds,self.recipients,name);w=np.array(p['probabilities']);self.assertTrue((w>=0).all());self.assertTrue(np.allclose(w.sum(1),1));self.assertIsNone(p['outside_candidate_probability'])
 def test_06_duplicate_people_rejected(self):
  with self.assertRaises(ValueError):predict_candidates(self.L,self.g['image_id'],'manual',[],self.seeds+self.seeds[:1],self.recipients)
  with self.assertRaises(ValueError):predict_candidates(self.L,self.g['image_id'],'manual',[],self.seeds,self.recipients+self.recipients[:1])
  with self.assertRaises(ValueError):predict_candidates(self.L,self.g['image_id'],'manual',[],self.seeds,[self.seeds[0]['worker_id']])
 def test_07_unknown_is_population_fallback_not_type(self):
  p=predict_candidates(self.L,self.g['image_id'],'manual',[],self.seeds,['UNSEEN_PERSON'],'type4');self.assertEqual(p['known_historical_worker'],[False]);self.assertTrue(np.allclose(p['probabilities'],[[.25]*4]))
 def test_08_identical_model_aliases_deduplicated(self):
  p=self.g['model_points'][0].tolist();bank=[dict(points=p,families=['HoHoNet']),dict(points=p,families=['Bi-enclosed'])]
  r=predict_candidates(self.L,self.g['image_id'],'manual',bank,[],self.recipients,'equal');self.assertEqual(len(r['candidate_points']),1);self.assertTrue(np.allclose(r['probabilities'],1))
 def test_09_reproducible_model_world_not_real_support(self):
  p=predict_candidates(self.L,self.g['image_id'],'manual',[],self.seeds,self.recipients);a=sample_world(p,123,0);b=sample_world(p,123,0);self.assertEqual(a,b);self.assertTrue(all(x['synthetic']and x['adds_independent_real_people']==0 for x in a))
 def test_10_kernel_positive_semidefinite(self):
  K=self.g['K'];self.assertTrue(np.allclose(K,K.T));self.assertGreaterEqual(float(np.linalg.eigvalsh(K).min()),-1e-8)
 def test_11_exact_probability_support(self):
  p=np.array([.2,.4,.7]);no=np.prod(1-p);one=sum(p[j]*np.prod(np.delete(1-p,j))for j in range(3));brute=sum(np.prod(np.where(bits,p,1-p))for bits in itertools.product((0,1),repeat=3)if sum(bits)>=2);self.assertAlmostEqual(1-no-one,brute,12)
 def test_12_cached_count_prior_equivalence(self):
  ref=ReferenceLearner(self.train,self.meta,self.workers,[self.g['building']]);hi=np.array([4,5])
  for ctx in (False,True):
   for personal in (False,True):
    self.assertTrue(np.allclose(ref.count_prior(self.g,hi,ctx,personal),self.L.count_prior(self.g,hi,ctx,personal),atol=1e-12))
 def test_13_exact_cluster_bootstrap_acceleration(self):
  df=pd.DataFrame([dict(image_id=str(i),building=['a','a','b','c'][i],method=m,loss=i*.2+(.04*i-.1 if m=='alt'else 0))for m in ('base','alt')for i in range(4)])
  a=c.boot_pair(df,'alt','base','loss',['image_id','building']);b=paired_exact(df,'alt','base','loss',['image_id','building'])
  for key in ('delta','ci_low','ci_high','building_macro_delta'):self.assertAlmostEqual(a[key],b[key],12)
 def test_14_original_geometry_distance_and_fast_flag(self):
  D,valid,err=matrix(self.g);self.assertLess(err,1e-6);ix=np.arange(len(self.g['ids']));_,a=trajectory(ix,self.g,D,valid,.1);b=endstats(ix,self.g,D,valid,.1);self.assertEqual(a['diagnostic_stable80'],b['original_stable80']);self.assertEqual(a['diagnostic_stable100'],b['original_stable100'])
 def test_15_different_point_counts_never_merge(self):
  D=np.zeros((4,4));lab=clusters(D,np.array([4,4,6,6]),.1);self.assertEqual(lab[0],lab[1]);self.assertEqual(lab[2],lab[3]);self.assertNotEqual(lab[0],lab[2])
 def test_16_input_hashes(self):
  for r in json.loads((self.out/'input_manifest.json').read_text()):
   p=self.out/'inputs'/(r['name']+'__'+Path(r['path']).name);self.assertTrue(p.is_file());self.assertEqual(hashlib.sha256(p.read_bytes()).hexdigest(),r['sha256'])
 def test_17_actual_AABC_distinct_and_seed_exclusion(self):
  p=self.out/'all_role_compositions/real_compositions.csv.gz';self.assertTrue(p.is_file());df=pd.read_csv(p);a=df[df.pattern=='AABC'];self.assertGreater(len(a),0)
  for r in a.itertuples():
   who=r.worker_ids.split('|');ss=r.seed_workers.split('|');self.assertEqual(len(who),4);self.assertEqual(len(set(who)),4);self.assertFalse(set(who)&set(ss));self.assertEqual(len(r.type_roles.split('|')),3)
 def test_18_finite_seed_sampler_cannot_invent_point_count(self):
  p=predict_candidates(self.L,self.g['image_id'],'manual',[],self.seeds,self.recipients);allowed={len(v['points'])for v in self.seeds}
  for world in range(10):self.assertTrue(all(len(r['points'])in allowed for r in sample_world(p,world,world)))
 def test_19_source_profiles_not_target_reference_quality(self):
  source=inspect.getsource(CachedLearner);self.assertNotIn('expert_tag',source);self.assertNotIn('risk_design_score',source)
 def test_20_saved_API_equivalence_was_executed(self):
  r=json.loads((self.out/'online_api_verification.json').read_text());self.assertEqual(r['status'],'passed');self.assertGreater(r['saved_prediction_equivalence_cases'],100);self.assertFalse(r['hidden_answer_argument_exists'])

if __name__=='__main__':unittest.main(verbosity=2)
