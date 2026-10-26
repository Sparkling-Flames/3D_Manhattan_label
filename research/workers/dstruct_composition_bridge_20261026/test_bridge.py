import unittest
import numpy as np
from build_bridge import decompose
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
if __name__=='__main__':unittest.main()
