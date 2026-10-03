import copy,itertools,json,sys,unittest
from pathlib import Path
import numpy as np
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'src'))
from consensus_lab import *
R=json.loads((ROOT/'inputs/current_excerpt.json').read_text(encoding='utf-8'))['images'][0]['annotations']

class LabTests(unittest.TestCase):
 def test_current_projection(self):
  for r in R:np.testing.assert_allclose(footprint(r),r['footprint'],atol=1e-14)
 def test_angular_identity_and_symmetry(self):
  a,b=pairs(R[0]),pairs(R[1]);np.testing.assert_allclose(angular(a[:,0],b[:,0]),angular(b[:,0],a[:,0]).T,atol=1e-12)
  self.assertLess(np.max(np.diag(angular(a[:,0],a[:,0]))),1e-10)
 def test_seam_equivalence(self):
  a=pairs(R[0]);b=a.copy();b[:,:,0]+=W
  self.assertLess(full_alignment(a,b)['distance'],1e-10)
 def test_circular_and_reverse_alignment(self):
  a=pairs(R[0]);b=np.roll(a[::-1],2,axis=0);z=full_alignment(a,b)
  self.assertFalse(z['ambiguous']);self.assertLess(z['distance'],1e-10)
  np.testing.assert_allclose(a,b[z['mapping']],atol=1e-10)
 def test_no_input_mutation(self):
  s=json.dumps(R,sort_keys=True);derive_candidates(R,5.);self.assertEqual(s,json.dumps(R,sort_keys=True))
 def test_duplicate_worker_rejected(self):
  x=copy.deepcopy(R[:2]);x[1]['worker']=x[0]['worker']
  with self.assertRaises(ValueError):derive_candidates(x)
 def test_missing_is_not_negative_vote_or_dropped(self):
  x=copy.deepcopy(R);x[1]['points']=None;r=derive_candidates(x)
  self.assertEqual(r['n_requested'],3);self.assertEqual(r['n_available'],2);self.assertEqual(len(r['failures']),1)
  self.assertEqual(conditional_decision(x,r)['status'],'unresolved_method_coverage')
 def test_unknown_independence_not_promoted(self):
  for key in ['independent','consensus_eligible']:
   x=copy.deepcopy(R);x[1].pop(key);r=derive_candidates(x)
   self.assertEqual(r['n_available'],2);self.assertEqual(r['n_requested'],3)
 def test_borrowed_not_independent(self):
  x=copy.deepcopy(R);x[1]['borrowed_points']=True;r=derive_candidates(x)
  self.assertEqual(r['n_available'],2);self.assertEqual(r['n_requested'],3)
 def test_does_not_inherit_confirmation(self):
  x=copy.deepcopy(R);[r.update(ring_confirmed=True) for r in x]
  self.assertTrue(all(c['ring_confirmed'] is False for c in derive_candidates(x)['candidates']))
 def test_no_reference_consumption(self):
  x=copy.deepcopy(R);[r.update(reference={'points':[[999,999]]},future_records=['poison']) for r in x]
  self.assertEqual(derive_candidates(x),derive_candidates(R))
 def test_permutation_invariance(self):
  self.assertEqual(derive_candidates(R),derive_candidates(R[::-1]))
  a=conditional_decision(R)['single_candidate']['points'];b=conditional_decision(R[::-1])['single_candidate']['points']
  self.assertEqual(a,b)
 def test_neutral_subdivision(self):
  x=insert_subdivision(R[0]);self.assertEqual(len(pairs(x)),5)
  self.assertAlmostEqual(iou(polygon(R[0]),polygon(x)),1,places=12)
  np.testing.assert_allclose(band(R[0],1024)[1],band(x,1024)[1],atol=1e-10)
  m=partial_alignment(pairs(R[0]),pairs(x));self.assertEqual(m['matched'],4);self.assertFalse(m['ambiguous'])
 def test_upper_detail_not_bottom_detail(self):
  x=insert_subdivision(R[0],upper_delta_px=20.)
  self.assertAlmostEqual(iou(polygon(R[0]),polygon(x)),1,places=12)
  self.assertGreater(abs(band(R[0],1024)[1][0]-band(x,1024)[1][0]).max(),19)
 def test_partial_dp_bruteforce(self):
  rng=np.random.default_rng(9217)
  for seed in range(12):
   a=pairs(R[0])[:3].copy();b=pairs(R[1]).copy()
   a[:,:,1]+=rng.normal(0,4,(3,2));b[:,:,1]+=rng.normal(0,4,(4,2));t=3.
   c=costs(a,b);found={};m,n=c.shape
   for order in (np.arange(n),np.arange(n)[::-1]):
    for sh in range(n):
     order=np.roll(order,-sh)
     for size in range(min(m,n)+1):
      for ia in itertools.combinations(range(m),size):
       for js in itertools.combinations(range(n),size):
        mapping=tuple(zip(ia,[int(order[j]) for j in js]))
        if all(c[i,j]<=t+1e-10 for i,j in mapping):found[mapping]=(size,sum(c[i,j] for i,j in mapping),mapping)
   z=sorted(found.values(),key=lambda q:(-q[0],q[1],q[2]));got=partial_alignment(a,b,t)
   self.assertEqual(got['matched'],z[0][0]);self.assertAlmostEqual(got['sum_angle'],z[0][1],places=10)
   self.assertEqual(got['mapping'],[list(v) for v in z[0][2]])
   if len(z)>1 and z[1][0]==z[0][0]:
    self.assertAlmostEqual(got['margin'],z[1][1]-z[0][1],places=10)
 def test_cycle_inconsistency_blocks_single(self):
  r=json.loads((ROOT/'results/pairwise_unique_but_cycle_inconsistent.json').read_text(encoding='utf-8'))['records']
  a=cycle_audit(r,5.);self.assertTrue(a['all_pairs_compatible_and_unique']);self.assertEqual(len(a['conflicts']),1)
  self.assertEqual(conditional_decision(r)['status'],'unresolved_global_correspondence')
 def test_single_requires_all_pair_checks(self):
  self.assertEqual(conditional_decision(R, tolerance=2.5)['status'],'retain_alternatives_or_correspondence_uncertainty')
  self.assertEqual(conditional_decision(R, tolerance=5.)['status'],'single_candidate_conditional_on_method_tolerance')
 def test_original_ring_not_sorted(self):
  r=copy.deepcopy(R[0]);r['points']=pairs(r)[[0,2,1,3]].reshape(-1,2).tolist()
  with self.assertRaises(ValueError):band(r)
 def test_majority_keeps_unsupported(self):
  r=copy.deepcopy(R[1]);r['points']=pairs(r)[[0,2,1,3]].reshape(-1,2).tolist()
  with self.assertRaises(ValueError):majority([R[0],r])
 def test_explicit_ties(self):
  # Identical duplicate pair geometry creates two genuinely distinct index maps.
  a=pairs(R[0])[:3];b=np.insert(a,1,a[0],axis=0)
  z=partial_alignment(a,b,.1);self.assertTrue(z['ambiguous']);self.assertEqual(z['matched'],3)
 def test_direct_edge_vs_subdivision_path(self):
  src=copy.deepcopy(R[0]);sub=insert_subdivision(src);r=derive_candidates([src,sub])
  a=next(c for c in r['candidates'] if c['anchor']==src['id'])
  self.assertEqual(a['point_support_counts'],[2,2,2,2])
  self.assertEqual(len(a['direct_edge_witnesses'][0]),1)
  self.assertEqual(len(a['endpoint_connection_with_intermediate_pairs'][0]),1)
  self.assertEqual(len(a['complete_ring_mapping_witnesses']),1)

class JointTests(unittest.TestCase):
 def test_real_unique_global_correspondence(self):
  z=joint_ring_alignment(R,5.);self.assertEqual(z['feasible_count'],1);self.assertEqual(z['optimal_count'],1)
 def test_two_global_optima_not_arbitrary_winner(self):
  r=json.loads((ROOT/'results/pairwise_unique_but_cycle_inconsistent.json').read_text(encoding='utf-8'))['records']
  z=joint_ring_alignment(r,5.);self.assertEqual(z['states_enumerated'],64)
  self.assertEqual(z['feasible_count'],2);self.assertEqual(z['optimal_count'],2)
  self.assertTrue(all(max(c['induced_pair_errors_deg'])<5 for c in z['candidates']))
 def test_search_budget_is_explicit_failure(self):
  self.assertEqual(joint_ring_alignment(R,max_states=1)['status'],'budget_exceeded_no_exact_result')
 def test_no_joint_solution_at_smaller_cut(self):
  self.assertEqual(joint_ring_alignment(R,2.5)['status'],'no_joint_alignment_within_tolerance')

if __name__=='__main__':unittest.main(verbosity=2)
