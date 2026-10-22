import unittest,json,hashlib,tempfile,copy
from pathlib import Path
import pandas as pd
from dataclasses import replace
from geomscore import Config
from score_manifest import run,digest,sha
from compare_versions import compare
O=Path(__file__).resolve().parents[1]
class Contracts(unittest.TestCase):
 def test_bad_config(self):
  for kw in [dict(edit_budget=2),dict(angle_scale_deg=0),dict(mean_scale_ratio=1),dict(placement_free_deg=45,placement_zero_deg=15),dict(min_samples=0)]:
   with self.assertRaises(ValueError):replace(Config(),**kw)
 def fixture(self,tmp):
  m=json.loads((O/'RUN_MANIFEST.json').read_text());p=json.loads((O/'inputs/current_pairs.json').read_text())[:1]
  pp=tmp/'pairs.json';pp.write_text(json.dumps(p));cp=tmp/'config.json';cp.write_bytes((O/'config.json').read_bytes())
  m.update(pairs_file='pairs.json',config_file='config.json',pairs_file_sha256=sha(pp),config_file_sha256=sha(cp))
  mp=tmp/'manifest.json';mp.write_text(json.dumps(m));return m,p,mp
 def test_ref_identity_change_separate(self):
  with tempfile.TemporaryDirectory() as f:
   t=Path(f);m,p,mp=self.fixture(t);run(mp,t/'a.csv');d=pd.read_csv(t/'a.csv');d['reference_id']='different_reference';d.to_csv(t/'b.csv',index=False)
   z=compare(t/'a.csv',t/'b.csv',t/'c.csv');self.assertEqual(z[0]['comparison_status'],'input_or_reference_or_eligibility_changed');self.assertNotIn('delta_QA',z[0])
 def test_geometry_hash_mismatch(self):
  with tempfile.TemporaryDirectory() as f:
   t=Path(f);m,p,mp=self.fixture(t);p[0]['answer']['top3d'][0][1]+=.01;(t/'pairs.json').write_text(json.dumps(p));m['pairs_file_sha256']=sha(t/'pairs.json');mp.write_text(json.dumps(m));z=run(mp,t/'a.csv');self.assertEqual(z[0]['reason'],'explicit_geometry_hash_mismatch')
 def test_excluded_gt(self):
  with tempfile.TemporaryDirectory() as f:
   t=Path(f);m,p,mp=self.fixture(t);m['authorization'][p[0]['object_id']]['gt_error_excluded']=True;mp.write_text(json.dumps(m));z=run(mp,t/'a.csv');self.assertEqual(z[0]['status'],'excluded');self.assertIsNone(z[0]['QA'])
 def test_source_pool_insufficient(self):
  with tempfile.TemporaryDirectory() as f:
   t=Path(f);m,p,mp=self.fixture(t);m['authorization'][p[0]['object_id']]['pool_source_workers']=2;mp.write_text(json.dumps(m));z=run(mp,t/'a.csv');self.assertEqual(z[0]['reason'],'source_pool_below_three')
if __name__=='__main__':unittest.main()
