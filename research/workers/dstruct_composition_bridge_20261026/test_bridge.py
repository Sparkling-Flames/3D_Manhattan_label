import unittest
import os,shutil,subprocess,sys,tempfile
from pathlib import Path
import numpy as np
from build_bridge import decompose,HERE,ROOT
class VarianceTests(unittest.TestCase):
 def test_unbalanced_team_weights(self):
  r=decompose(np.array([0.,2.,10.]),['a','a','b'])
  self.assertAlmostEqual(r['total_variance'],56/3)
  self.assertAlmostEqual(r['within_variance'],2/3)
  self.assertAlmostEqual(r['between_variance'],18)
  self.assertEqual(r['singleton_configurations'],1)
 def test_constant_is_undefined_share(self):
  r=decompose(np.array([4.,4.]),['a','b'])
  self.assertTrue(np.isnan(r['between_share']))
  self.assertEqual(r['total_variance'],0)
 def test_missing_not_zero(self):
  r=decompose(np.array([0.,2.,np.nan]),['a','a','b'])
  self.assertEqual(r['valid_teams'],2)
  self.assertEqual(r['configurations'],1)
  self.assertEqual(r['within_variance'],1)
 def test_nested_partition(self):
  y=np.array([0.,1.,6.,9.])
  a=decompose(y,['a','a','a','b']);b=decompose(y,['a','a','c','b'])
  self.assertGreaterEqual(b['between_variance'],a['between_variance'])
 def test_presentation_utf8_with_default_utf8_mode_disabled(self):
  with tempfile.TemporaryDirectory() as folder:
   output=Path(folder)
   for name in ['SUMMARY.csv','PANEL_VARIANCE.csv','CONFIGURATIONS.csv']:
    shutil.copyfile(HERE/name,output/name)
   code="import runpy,sys,types;from pathlib import Path;m=types.ModuleType('build_bridge');m.HERE=Path(sys.argv[1]);m.ROOT=Path(sys.argv[2]);sys.modules['build_bridge']=m;runpy.run_path(sys.argv[3],run_name='__main__')"
   subprocess.run([sys.executable,'-X','utf8=0','-c',code,str(output),str(ROOT),str(HERE/'build_presentation.py')],
                  env={**os.environ,'PYTHONIOENCODING':'cp936'},check=True,capture_output=True)
   self.assertTrue('困难' in (output/'presentation-data.js').read_text(encoding='utf-8'),'presentation JS must preserve Chinese in UTF-8')
   self.assertIn('构成差异与成员波动并存',(output/'Q_VARIANCE_OVERVIEW.svg').read_text(encoding='utf-8'))
if __name__=='__main__':unittest.main()
