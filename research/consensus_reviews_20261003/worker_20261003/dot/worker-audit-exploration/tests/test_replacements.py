import importlib.util
from itertools import combinations
from pathlib import Path
import unittest
import numpy as np

spec=importlib.util.spec_from_file_location('explore',Path(__file__).resolve().parents[1]/'src/explore_replacements.py')
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)

class ReplacementTests(unittest.TestCase):
    def setUp(self):
        self.members=np.array(list(combinations(range(6),3)))
        self.d=m.design(self.members,6)
    def test_complete_counts(self):
        self.assertEqual(self.d['ia'].shape,(15,6))
    def test_pair_backgrounds_exclude_candidates(self):
        for p,bg in zip(self.d['pairs'],self.d['backgrounds']):
            self.assertFalse(np.isin(bg,p).any())
    def test_additive_recovery(self):
        beta=np.array([-.06,-.04,-.01,.02,.04,.05])
        y=.5+self.d['x']@beta
        a=m.analyze_scores(self.d,y)
        np.testing.assert_allclose(a['beta'],beta,atol=1e-15)
        self.assertLess(a['residual_variance'],1e-29)
        self.assertLess(np.max(a['delta'].std(1)),1e-15)
    def test_nonlinear_residual_and_sign_reversal(self):
        x=self.d['x'];y=.5+.2*x[:,0]*x[:,1]-.2*x[:,0]*x[:,2]
        a=m.analyze_scores(self.d,y)
        self.assertGreater(a['residual_variance'],.0001)
        self.assertTrue(((a['delta'].max(1)>0)&(a['delta'].min(1)<0)).any())
        self.assertLess(a['identity_error'],1e-15)
    def test_tolerant_rank_keeps_numerical_ties(self):
        np.testing.assert_array_equal(m.tolerant_rank([1.,1.+1e-15,2.]),[1.5,1.5,3.])
    def test_identical_candidates_tie_every_background(self):
        x=self.d['x'];y=.5+.03*(x[:,0]+x[:,1])+.04*x[:,2]*x[:,3]
        a=m.analyze_scores(self.d,y)
        row=np.flatnonzero((self.d['pairs']==[0,1]).all(1))[0]
        np.testing.assert_array_equal(a['delta'][row],0.)
    def test_constant_scores(self):
        a=m.analyze_scores(self.d,np.ones(20)*.4)
        self.assertLess(np.max(np.abs(a['delta'])),1e-15)
    def test_nonfinite_rejected(self):
        y=np.ones(20);y[0]=np.nan
        with self.assertRaises(ValueError):m.analyze_scores(self.d,y)
    def test_incomplete_design_rejected(self):
        with self.assertRaises(ValueError):m.design(self.members[:-1],6)
    def test_duplicate_subset_rejected(self):
        v=self.members.copy();v[-1]=v[0]
        with self.assertRaises(ValueError):m.design(v,6)
    def test_lobo_target_values_irrelevant(self):
        y=np.arange(24,dtype=float).reshape(4,6);buildings=np.array(['a','a','b','c'])
        p,h=m.lobo_train(y,buildings,'a');y[:2]=-10000
        q,j=m.lobo_train(y,buildings,'a')
        np.testing.assert_array_equal(p,q);np.testing.assert_array_equal(h,j)
    def test_cutoff_tie_rejected(self):
        with self.assertRaises(ValueError):m.lobo_train(np.zeros((3,6)),np.array(['a','b','c']),'a')
    def test_projection_is_least_squares(self):
        rng=np.random.default_rng(41);y=rng.uniform(size=20)
        a=m.analyze_scores(self.d,y)
        fit=self.d['x']@np.linalg.lstsq(self.d['x'],y,rcond=None)[0]
        np.testing.assert_allclose(a['fitted'],fit,atol=2e-15)
    def test_pairwise_mean_transitivity(self):
        rng=np.random.default_rng(98);a=m.analyze_scores(self.d,rng.uniform(size=20))
        lookup={tuple(p):v for p,v in zip(self.d['pairs'],a['delta'].mean(1))}
        self.assertAlmostEqual(lookup[(0,1)]+lookup[(1,2)],lookup[(0,2)],places=14)

if __name__=='__main__':unittest.main(verbosity=2)
