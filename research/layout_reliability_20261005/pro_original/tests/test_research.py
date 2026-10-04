import unittest,json,sys,copy,hashlib,itertools
from pathlib import Path
import numpy as np
import pandas as pd
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'src'))
from arc_consensus import Ring,TAU,W,H,Unsupported,footprint,fuse
from compression_study import make_candidate,bottom_turns,path_costs
from simplify import compression_costs
from continuous_metrics import fixed_longitude,height_delta_extrema,signed_extrema,depth_height_change,witness_and_provenance,height_envelope,height_envelope_audit
from localize_failures import diagnostic

def load(image):return json.loads((ROOT/'inputs'/f'{image}.json').read_text())['records']
def exact(image):
 f=json.loads((ROOT/'results/construction'/f'{image}_exact.json').read_text());return f['methods'][f['bev_mv50_complete_method']]
def costs(image):return np.load(ROOT/'results/compression'/f'{image}_circular_costs.npy')
I3='2t7WUuJeko7-06';I24='7y3sRwLe3Va-04'
class ResearchTests(unittest.TestCase):
 def test_01_current_inputs_byte_bound(self):
  expected={I3:'ca532c9a723ac6f2d6e0338d272de535528a8558',I24:'1e03b76d492c33c7c764156fb4ac5556d150cdf9','rPc6DW4iMge-06':'7db75a7bd2066e1753d8475b8f0a43949d7fbf52','uNb9QFRL6hY-67':'3527a7335389336bc0bc16805f4a4dfe89e65285'}
  for image,sha in expected.items():
   b=(ROOT/'inputs'/f'{image}.json').read_bytes();self.assertEqual(hashlib.sha1(b'blob '+str(len(b)).encode()+b'\0'+b).hexdigest(),sha)
 def test_02_roster_metadata(self):
  counts=[]
  for p in (ROOT/'inputs').glob('*.json'):
   r=json.loads(p.read_text())['records'];counts.append(len(r));self.assertEqual(len(set(x['worker'] for x in r)),len(r))
   for x in r:
    self.assertIs(x['independent'],True);self.assertIs(x['consensus_eligible'],True);self.assertEqual(len(x['points']),len(x['source_point_indices']))
  self.assertEqual(sorted(counts),[3,15,24,24]);self.assertEqual(sum(counts),66)
 def test_03_fixed_identity(self):
  d=fixed_longitude(exact(I3),exact(I3));self.assertLess(d['top_max_abs_px'],1e-10);self.assertLess(d['bottom_mean_abs_px'],1e-10)
 def test_04_fixed_symmetry(self):
  a,b=load(I3)[:2];x=fixed_longitude(a,b);y=fixed_longitude(b,a)
  self.assertAlmostEqual(x['top_mean_abs_px'],y['top_mean_abs_px'],places=10);self.assertAlmostEqual(x['top_mean_signed_px'],-y['top_mean_signed_px'],places=10)
 def test_05_fixed_triangle(self):
  a,b,c=load(I3);ab=fixed_longitude(a,b);bc=fixed_longitude(b,c);ac=fixed_longitude(a,c)
  for side in ['top','bottom']:self.assertLessEqual(ac[side+'_mean_abs_px'],ab[side+'_mean_abs_px']+bc[side+'_mean_abs_px']+1e-8)
 def test_06_fixed_cyclic_reencoding(self):
  a=exact(I3);b=copy.deepcopy(a);q=np.array(a['points']).reshape(-1,2,2);b['points']=np.roll(q,7,axis=0).reshape(-1,2).tolist();self.assertLess(fixed_longitude(a,b)['top_max_abs_px'],1e-8)
 def test_07_signed_extrema_dense(self):
  rng=np.random.default_rng(7105)
  for k in range(40):
   c,d=rng.normal(size=(2,2));lo=rng.uniform(0,5);hi=lo+rng.uniform(.05,1);a,b,_,_=signed_extrema(c,d,lo,hi);u=np.linspace(lo,hi,20001);v=np.c_[np.sin(u),np.cos(u)];z=-H/np.pi*(np.arctan(v@c)-np.arctan(v@d));self.assertLessEqual(a,z.min()+1e-8);self.assertGreaterEqual(b,z.max()-1e-8)
 def test_08_height_extrema_dense(self):
  rng=np.random.default_rng(8205)
  for k in range(40):
   c=rng.uniform(.2,2,(2,2));d=rng.uniform(.2,2,(2,2));c[1]*=-1;d[1]*=-1;lo,hi=.1,1.4;a,b,_,_=height_delta_extrema(c,d,lo,hi);u=np.linspace(lo,hi,20001);v=np.c_[np.sin(u),np.cos(u)];z=-(v@c[0])/(v@c[1])+(v@d[0])/(v@d[1]);self.assertLessEqual(a,z.min()+1e-9);self.assertGreaterEqual(b,z.max()-1e-9)
 def test_09_fixed_start_costs_match_archived(self):
  a=compression_costs(exact(I3));b=path_costs(costs(I3));np.testing.assert_allclose(a,b,atol=1e-8,rtol=1e-8)
 def test_10_bottom_lock_all_budgets(self):
  for image in [I3,I24]:
   e=exact(image);_,p=footprint(e)
   for eps in [.25,.5,1,2]:
    c=make_candidate(e,eps,costs(image),bottom_turns(e)[0],True);_,q=footprint(c);self.assertLess(p.symmetric_difference(q).area,1e-10)
    self.assertGreaterEqual(c['pair_count'],len(bottom_turns(e)));self.assertLessEqual(c['maximum_vertical_curve_error_px'],eps+1e-8)
 def test_11_no_source_mutation(self):
  e=exact(I3);s=json.dumps(e,sort_keys=True);make_candidate(e,.5,costs(I3),4,True);self.assertEqual(json.dumps(e,sort_keys=True),s)
 def test_12_provenance_not_inherited(self):
  c=make_candidate(exact(I3),.5,costs(I3),4,True);self.assertIs(c['exact_source_guarantee_inherited'],False)
  for e in c['connections']:self.assertTrue(e['exact_edge_indices']);self.assertNotIn('exact_edge_range',e)
 def test_13_required_anchor_invariance(self):
  for image in [I3,I24]:
   e=exact(image);cc=costs(image)
   for eps in [.5,2.]:
    ss={tuple(sorted(make_candidate(e,eps,cc,s,True)['retained_exact_knot_indices'])) for s in bottom_turns(e)};self.assertEqual(len(ss),1)
 def test_14_witness_event_vs_dense(self):
  rr=load(I3);c=make_candidate(exact(I3),.5,costs(I3),4,True);w=witness_and_provenance(c,rr,2);u=(np.arange(100001)+.5)/100001*TAU;C=Ring(c).evaluate(u);s=np.array([Ring(r).evaluate(u) for r in rr]);count=((s[:,0]<=C[0]+1e-8)&(s[:,1]>=C[1]-1e-8)).sum(axis=0)
  self.assertAlmostEqual(w['longitude_share_zero_witness'],np.mean(count==0),delta=3e-5)
 def test_15_witness_failure_not_suppressed(self):
  rr=load(I3);c=make_candidate(exact(I3),.5,costs(I3),4,True);w=witness_and_provenance(c,rr,2);self.assertGreater(w['longitude_share_zero_witness'],.23)
 def test_16_exact_witness_bound(self):
  for image in [I3,I24]:
   rr=load(image);w=witness_and_provenance(exact(image),rr,len(rr)//2+1);self.assertEqual(w['longitude_share_below_exact_lower_bound'],0.)
 def test_17_height_envelope_real(self):
  rr=load(I3);env=height_envelope(rr);z=height_envelope_audit(exact(I3),env);self.assertLess(z['height_envelope_violation_h'],1e-10)
 def test_18_depth_lock(self):
  e=exact(I24);c=make_candidate(e,.5,costs(I24),bottom_turns(e)[0],True);d=depth_height_change(c,e);self.assertLess(d['radial_max_relative_change'],1e-10)
 def test_19_domain_failures_keep_roster(self):
  for image,n,bad in [('rPc6DW4iMge-06',24,3),('uNb9QFRL6hY-67',15,2)]:
   f=fuse(load(image));self.assertEqual(f['n'],n);self.assertEqual(len(f['failures']),bad);self.assertEqual(f['status'],'unsupported_entire_selected_roster');self.assertFalse(f['methods'])
 def test_20_domain_location(self):
  d=diagnostic(load('uNb9QFRL6hY-67'));self.assertAlmostEqual(d['non_single_valued_longitude_share'],((34.87881727815137-7.737737177364656)+(231.88919667590025-210.61495844875347))/1024,places=10)
 def test_21_reference_independence(self):
  a=load(I3);b=copy.deepcopy(a)
  for x in b:x['target_GT']={'points':'not a geometry'}
  fa,fb=fuse(a),fuse(b);self.assertEqual(fa['methods'][fa['bev_mv50_complete_method']]['points'],fb['methods'][fb['bev_mv50_complete_method']]['points'])
 def test_22_score_shift_certificates(self):
  d=pd.read_csv(ROOT/'results/metrics/compression_score_certificates.csv');self.assertTrue(d.bound_passed.all());self.assertTrue(d.point_order_reversed.any());self.assertFalse((d.point_order_certified&d.point_order_reversed).any())
 def test_23_raw_duplicate_people_kept(self):
  a=load(I24);s={tuple(np.array(x['points']).ravel()) for x in a};self.assertLess(len(s),24);self.assertEqual(fuse(a)['n'],24)
 def test_24_no_general_volume(self):
  e=exact(I3);self.assertEqual(e['roof_interior'],'not_observed_not_assumed')
if __name__=='__main__':unittest.main()
