import copy,json,pathlib,sys,unittest,os
import numpy as np
from corner_distance import corner_compare,project
ROOT=pathlib.Path(os.environ.get('INTERCHANGEABILITY_WORK_ROOT',pathlib.Path(__file__).resolve().parents[1]))
BUNDLE=pathlib.Path(os.environ.get('INTERCHANGEABILITY_BUNDLE',ROOT/'unpacked'))
class TestCorner(unittest.TestCase):
 def setUp(self):
  self.a=json.loads((BUNDLE/'interchangeability_20261020/cases/S01_pure_class.json').read_text())['teams'][0]
 def test_identity_start_and_reverse(self):
  for rev in [False,True]:
   b=copy.deepcopy(self.a);p=np.asarray(b['geometry']['points']).reshape(-1,2,2);f=np.asarray(b['geometry']['footprint'])
   if rev:p=p[::-1];f=f[::-1]
   p=np.roll(p,1,axis=0);f=np.roll(f,1,axis=0)
   b['geometry']['points']=p.reshape(-1,2).tolist();b['geometry']['footprint']=f.tolist()
   row,_=corner_compare(self.a,b)
   self.assertEqual(row['status'],'unique_cyclic_candidate');self.assertLess(row['bev_max_h'],1e-10);self.assertLess(row['top_max_h'],1e-10);self.assertEqual(row['ring_reversed'],rev)
 def test_not_zero_on_failures(self):
  b=copy.deepcopy(self.a);b['complete_evaluable']=False
  r,_=corner_compare(self.a,b);self.assertNotIn('bev_mean_h',r)
  b=copy.deepcopy(self.a);b['geometry']['points']=b['geometry']['points'][:-2]
  r,_=corner_compare(self.a,b);self.assertEqual(r['status'],'different_corner_count');self.assertNotIn('bev_mean_h',r)
 def test_projection_and_symmetry(self):
  for p in (BUNDLE/'interchangeability_20261020/cases').glob('S*.json'):
   teams=json.loads(p.read_text())['teams']
   for t in teams:
    if t['geometry'].get('points') is not None:
     bottom,_=project(t['geometry']['points']);np.testing.assert_allclose(bottom[:,[0,2]],t['geometry']['footprint'],atol=1e-7)
   if len(teams)>=2:
    a,b=teams[:2];r,_=corner_compare(a,b);s,_=corner_compare(b,a)
    if r['status']==s['status']=='unique_cyclic_candidate':
     for field in ['bev_mean_h','bev_max_h','top_mean_h','top_max_h','bev_max_pairscale','bev_max_local_radius_fraction']:
      self.assertAlmostEqual(r[field],s[field],places=10)
if __name__=='__main__':unittest.main()
