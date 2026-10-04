import unittest, sys, itertools, math, copy, json, hashlib
from pathlib import Path
import numpy as np
import pandas as pd
from shapely.geometry import box
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'src'))
from finite_pool import hg,marginal,coupled,threshold,next_member_loss,make_basis

def selections(groups,K):
 return [frozenset(itertools.chain.from_iterable(parts)) for parts in itertools.product(*(itertools.combinations(g,k) for g,k in zip(groups,K)))]

def brute(groups,bits,K,rule,op,change):
 out=np.zeros(3);pool=set(itertools.chain.from_iterable(groups));sets=selections(groups,K)
 for S in sets:
  old=sum(bits[j] for j in S)>=threshold(len(S),rule)
  if op=='add':
   remain=[sorted(set(g)-S) for g in groups]
   targets=[S|Z for Z in selections(remain,change)]
  elif op=='disjoint':targets=selections([sorted(set(g)-S) for g in groups],K)
  elif op=='swap':
   a,b=change;targets=[S-{u}|{v} for u in sorted(S&set(groups[a])) for v in sorted(set(groups[b])-S)]
  else:raise ValueError(op)
  for T in targets:
   new=sum(bits[j] for j in T)>=threshold(len(T),rule)
   out+=np.array([old!=new,not old and new,old and not new],float)/len(sets)/len(targets)
 return out

def records():
 return [dict(id=f'R{i}',worker=f'P{i}',condition='manual',independent=True,consensus_eligible=True,footprint=list(box(-1+i*.08,-1,1+i*.02,1+.03*i).exterior.coords)[:-1]) for i in range(6)]

class ProbabilityTests(unittest.TestCase):
 def setUp(self):
  self.groups=[list(range(3)),list(range(3,6))];self.bits=[1,1,0,1,0,0];self.N=(3,3);self.C=(2,1)
 def test_hypergeom_matches_combinations(self):
  for N in range(1,8):
   for C in range(N+1):
    for k in range(N+1):
     p=dict(hg(N,C,k));obs={}
     ss=list(itertools.combinations(range(N),k))
     for S in ss:
      j=sum(i<C for i in S);obs[j]=obs.get(j,0)+1/len(ss)
     self.assertEqual(set(p),set(obs));self.assertAlmostEqual(sum(p.values()),1)
     np.testing.assert_allclose(list(p.values()),[obs[j] for j in p],atol=2e-14)
 def test_hypergeom_rejects_bad_counts(self):
  for x in [(2,3,1),(2,1,3),(2,-1,0),(2,1,1.5),(True,1,1)]:
   with self.assertRaises(ValueError):hg(*x)
 def test_marginal_all_compositions(self):
  for K in itertools.product(range(4),repeat=2):
   if not sum(K):continue
   for rule in ['mv50','mv_strict']:
    SS=selections(self.groups,K);expected=np.mean([sum(self.bits[j] for j in S)>=threshold(sum(K),rule) for S in SS])
    self.assertAlmostEqual(marginal(self.N,self.C,K,rule),expected)
 def test_add_one_all_feasible(self):self._add((1,0));self._add((0,1))
 def test_add_two_all_feasible(self):self._add((2,0));self._add((0,2));self._add((1,1))
 def _add(self,A):
  for K in itertools.product(range(4),repeat=2):
   if not sum(K) or any(k+a>3 for k,a in zip(K,A)):continue
   for rule in ['mv50','mv_strict']:
    np.testing.assert_allclose(coupled(self.N,self.C,K,rule,'add',A),brute(self.groups,self.bits,K,rule,'add',A),atol=1e-13)
 def test_same_class_swap(self):self._swap((0,0));self._swap((1,1))
 def test_cross_class_swap(self):self._swap((0,1));self._swap((1,0))
 def _swap(self,A):
  for K in itertools.product(range(4),repeat=2):
   if not sum(K) or K[A[0]]==0 or K[A[1]]==3:continue
   for rule in ['mv50','mv_strict']:
    np.testing.assert_allclose(coupled(self.N,self.C,K,rule,'swap',A),brute(self.groups,self.bits,K,rule,'swap',A),atol=1e-13)
 def test_disjoint_draws(self):
  for K in [(1,0),(0,1),(1,1)]:
   for rule in ['mv50','mv_strict']:
    np.testing.assert_allclose(coupled(self.N,self.C,K,rule,'disjoint',()),brute(self.groups,self.bits,K,rule,'disjoint',()),atol=1e-13)
 def test_impossible_disjoint_not_zero(self):
  with self.assertRaises(ValueError):coupled(self.N,self.C,(2,1),'mv50','disjoint',())
 def test_next_raw_person_is_not_refusion(self):
  for K in itertools.product(range(4),repeat=2):
   if not sum(K):continue
   for g in range(2):
    if K[g]>=3:continue
    for rule in ['mv50','mv_strict']:
     ss=selections(self.groups,K);v=0
     for S in ss:
      old=sum(self.bits[i] for i in S)>=threshold(sum(K),rule);rem=set(self.groups[g])-S
      v+=sum(old!=bool(self.bits[i]) for i in rem)/len(rem)/len(ss)
     self.assertAlmostEqual(v,next_member_loss(self.N,self.C,K,rule,g))
 def test_rules_equal_on_odd_n(self):
  for K in itertools.product(range(4),repeat=2):
   if sum(K)%2:self.assertEqual(marginal(self.N,self.C,K,'mv50'),marginal(self.N,self.C,K,'mv_strict'))
 def test_full_pool_probability_is_deterministic(self):
  for rule in ['mv50','mv_strict']:self.assertIn(marginal(self.N,self.C,self.N,rule),(0,1))

class GeometryTests(unittest.TestCase):
 def setUp(self):
  self.r=records();self.ref={'footprint':list(box(-.9,-1.05,1.1,1).exterior.coords)[:-1]};self.b=make_basis(self.r,self.ref)
 def test_source_not_mutated(self):
  before=copy.deepcopy(self.r);make_basis(self.r,self.ref);self.assertEqual(self.r,before)
 def test_individual_areas(self):
  for i,p in enumerate(self.b.polygons):self.assertAlmostEqual(self.b.area@self.b.votes[i],p.area)
 def test_current_subset_retiling_equivalent(self):
  from shapely.ops import unary_union
  for ids in [(0,2),(0,1,3),(1,2,4,5)]:
   bb=make_basis([self.r[i] for i in ids],self.ref)
   for rule in ['mv50','mv_strict']:
    a=unary_union([t for t,m in zip(self.b.tiles,self.b.subset(ids,rule)) if m]);z=unary_union([t for t,m in zip(bb.tiles,bb.subset(range(len(ids)),rule)) if m]);self.assertLess(a.symmetric_difference(z).area,1e-12)
 def test_reference_does_not_change_tiles_or_votes(self):
  x=make_basis(self.r);np.testing.assert_array_equal(x.votes,self.b.votes);np.testing.assert_array_equal(x.area,self.b.area)
 def test_expected_error_matches_enumeration(self):
  labels=np.array([0]*3+[1]*3);SS=selections([range(3),range(3,6)],(1,2));masks=np.array([self.b.subset(list(s),'mv50') for s in SS]);q=self.b.q(labels,(1,2),'mv50')
  np.testing.assert_allclose(q,masks.mean(axis=0),atol=1e-13)
  summary=self.b.area_summary(q);errs=[self.b.reference.area+self.b.area@m-2*self.b.inside_reference@m for m in masks]
  self.assertAlmostEqual(summary['expected_ref_symdiff_union'],np.mean(errs)/self.b.union_area)
 def test_independent_same_k_shape_matches_enumeration(self):
  labels=np.array([0]*3+[1]*3);SS=selections([range(3),range(3,6)],(1,1));ms=[self.b.subset(list(s),'mv50') for s in SS]
  brutev=np.mean([self.b.area@(a!=b) for a in ms for b in ms])/self.b.union_area
  self.assertAlmostEqual(brutev,self.b.area_summary(self.b.q(labels,(1,1),'mv50'))['same_k_independent_symdiff_union'])
 def test_reference_change_identity(self):
  lab=np.array([0]*3+[1]*3)
  for rule in ['mv50','mv_strict']:
   x=self.b.area_summary(self.b.q(lab,(1,1),rule));y=self.b.area_summary(self.b.q(lab,(2,1),rule));t=self.b.transition(lab,(1,1),rule,'add',(1,0))
   self.assertAlmostEqual(y['expected_ref_symdiff_union']-x['expected_ref_symdiff_union'],t['expected_ref_error_change_union'])
 def test_duplicates_geometries_are_independent_votes(self):
  rr=copy.deepcopy(self.r);rr[1]['footprint']=rr[0]['footprint'];x=make_basis(rr);self.assertEqual(len(x.records),6);np.testing.assert_array_equal(x.votes[0],x.votes[1])
 def test_duplicate_worker_rejected(self):
  rr=copy.deepcopy(self.r);rr[1]['worker']=rr[0]['worker']
  with self.assertRaises(ValueError):make_basis(rr)
 def test_missing_geometry_blocks_whole_roster(self):
  rr=copy.deepcopy(self.r);rr[1]['footprint']=None
  with self.assertRaises(ValueError):make_basis(rr)
 def test_nonindependent_not_restored(self):
  rr=copy.deepcopy(self.r);rr[1]['independent']=False
  with self.assertRaises(ValueError):make_basis(rr)
 def test_mixed_conditions_rejected(self):
  rr=copy.deepcopy(self.r);rr[1]['condition']='semi'
  with self.assertRaises(ValueError):make_basis(rr)
 def test_invalid_polygon_not_repaired(self):
  rr=copy.deepcopy(self.r);rr[1]['footprint']=[[0,0],[1,1],[1,0],[0,1]]
  with self.assertRaises(ValueError):make_basis(rr)
 def test_reference_absent_does_not_stop_shape(self):
  b=make_basis(self.r);self.assertIsNone(b.iou(b.subset([0,1],'mv50')));self.assertNotIn('expected_ref_symdiff_union',b.area_summary(b.q([0]*6,(3,),'mv50')))
 def test_invalid_subset_rejected(self):
  for S in [[],[0,0],[-1],[6],[1.5]]:
   with self.assertRaises(ValueError):self.b.subset(S,'mv50')
 def test_scalar_counts_not_silently_truncated(self):
  with self.assertRaises(ValueError):self.b.q([0]*6,(2.5,),'mv50')

 def test_local_reference_failure_keeps_geometry(self):
  import tempfile
  from run_local import run
  with tempfile.TemporaryDirectory() as td:
   path=Path(td);d=dict(image='image-A',building='building-A',records=self.r,reference=dict(id='G1',footprint=None))
   c=dict(image='image-A',target_building='building-A',condition='manual',training_target_isolation_verified=True,calibration_buildings=['building-B'],feature_source_bindings=[dict(axis='Q',source='synthetic_validation_only')],reference_evaluation_allowed=True,reference_id='G1',reference_eligibility_source='synthetic_reference_failure_test',members=[dict(id=x['id'],worker=x['worker'],**{'class':i//3}) for i,x in enumerate(self.r)])
   (path/'data.json').write_text(json.dumps(d));(path/'classes.json').write_text(json.dumps(c));run(path/'data.json',path/'classes.json',path/'out')
   status=json.loads((path/'out/status.json').read_text());self.assertEqual(status['status'],'computed');self.assertEqual(status['reference_status'],'unavailable');self.assertEqual(status['roster_n'],6)
   self.assertNotIn('expected_ref_symdiff_union',pd.read_csv(path/'out/area.csv').columns)

class SourceTests(unittest.TestCase):
 def test_exact_archived_blob_hashes(self):
  expected={'matrix_original_iou.csv':'85a4f601dc32ca9a93b9668223acd401190b49d0','matrix_revised_where_available_iou.csv':'493173aa20638ee9fb9c25b81e9a01080350fafe','one_image_geometry.json':'d435129575849339e264867e2f9c797084b31a26'}
  for f,e in expected.items():
   raw=(ROOT/'inputs'/f).read_bytes();self.assertEqual(hashlib.sha1(f'blob {len(raw)}\0'.encode()+raw).hexdigest(),e)
 def test_all_48_polygon_scores_crosscheck(self):
  mat=pd.read_csv(ROOT/'inputs/matrix_original_iou.csv').set_index('image')
  for f in ['one_image_geometry.json','rpc_geometry.json']:
   d=json.loads((ROOT/'inputs'/f).read_text());b=make_basis(d['records'],d['reference']);self.assertEqual(len(b.records),24)
   for i,r in enumerate(b.records):self.assertAlmostEqual(b.iou(b.subset([i],'mv50')),float(mat.loc[d['image'],r['worker']]),places=12)
 def test_inventory_counts(self):
  d=pd.read_csv(ROOT/'inputs/high_support_inventory_excerpt.csv');m=d[d.condition=='manual'];s=d[d.condition=='semi'];o=d[d.condition=='oos']
  self.assertEqual((len(m),int(m.curve_ready.sum()),int((m.curve_ready&m.reference_quality_compatible).sum()),len(s),len(o)),(47,44,33,17,9))
 def test_failure_coverage_exact(self):
  n=6;b=2;k=3
  valid=sum(all(i>=b for i in S) for S in itertools.combinations(range(n),k))/math.comb(n,k)
  self.assertAlmostEqual(valid,math.comb(n-b,k)/math.comb(n,k))
 def test_empirical_energy_finite_pool_formula(self):
  x=np.array([0.,1.,3.,4.]);D=abs(x[:,None]-x[None,:]);n=len(x);mu=D.sum()/n/(n-1)
  for k in range(1,n+1):
   sets=list(itertools.combinations(range(n),k));v=[]
   for a in sets:
    for b in sets:v.append(2*D[np.ix_(a,b)].mean()-D[np.ix_(a,a)].mean()-D[np.ix_(b,b)].mean())
   self.assertAlmostEqual(np.mean(v),2*mu*(1/k-1/n))
 def test_nearest_unseen_member_formula(self):
  D=np.abs(np.array([0.,1.,3.,7.])[:,None]-np.array([0.,1.,3.,7.])[None,:]);m=len(D)
  for k in range(1,m):
   w=np.array([math.comb(m-1-j,k-1)/math.comb(m-1,k) if m-1-j>=k-1 else 0. for j in range(1,m)])
   for i in range(m):
    others=[j for j in range(m) if j!=i]
    self.assertAlmostEqual(np.sort(D[i,others])@w,np.mean([D[i,list(S)].min() for S in itertools.combinations(others,k)]))
if __name__=='__main__':unittest.main()
