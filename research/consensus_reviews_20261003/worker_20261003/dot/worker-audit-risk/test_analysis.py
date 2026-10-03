import unittest
from itertools import combinations
from math import comb
import numpy as np
from shapely.geometry import box
from analyze import cyclic_key, q_hypergeom, common_basis, pure_current_subset_region

class RiskTests(unittest.TestCase):
    def test_all_compositions_hypergeom_against_enumeration(self):
        rng=np.random.default_rng(92413)
        votes=rng.integers(0,2,size=(24,61)).astype(bool)
        higher=np.zeros(24,dtype=bool);higher[[1,2,3,5,7,8,9,11,14,17,21,22]]=True
        members=np.array(list(combinations(range(24),4)))
        counts=votes[members].sum(1); hcount=higher[members].sum(1)
        for threshold in [2,3]:
            for h in range(5):
                q,n=q_hypergeom(votes,higher,h,threshold)
                self.assertEqual(n,comb(12,h)*comb(12,4-h))
                np.testing.assert_array_equal(q,(counts[hcount==h]>=threshold).mean(0))

    def test_all_cover_and_no_cover(self):
        votes=np.array([[True,False]]*24);h=np.arange(24)<12
        for rule in [2,3]:
            for upper in range(5):
                np.testing.assert_array_equal(q_hypergeom(votes,h,upper,rule)[0],[1.,0.])

    def test_saved_ring_reversal_rotation(self):
        p=[[0,0],[0,1],[1,1],[1,0]]
        self.assertEqual(cyclic_key(p),cyclic_key(p[2:]+p[:2]))
        self.assertEqual(cyclic_key(p),cyclic_key(list(reversed(p))))
        self.assertEqual(cyclic_key(p),cyclic_key(p+[p[0]]))

    def test_gt_extends_beyond_union(self):
        # This tests the constant outside-domain term in B, often accidentally lost.
        q=np.array([.2,.8]);areas=np.array([1.,2.]);intersection=np.array([.5,.7]);gt=4.
        risk=gt-intersection@q+(areas-intersection)@q
        bias=intersection@(1-q)**2+(areas-intersection)@(q*q)+gt-intersection.sum()
        variance=areas@(q*(1-q))
        self.assertAlmostEqual(risk,bias+variance,places=14)

    def test_pair_area_direct_cross_product(self):
        # All ordered draws include the same output twice and arbitrary overlap.
        c=np.array([[1,1,0],[1,0,0],[0,1,1],[1,1,1]],dtype=bool);area=np.array([.6,1.,2.3])
        q=c.mean(0)
        direct=np.mean([np.sum(area*(a!=b)) for a in c for b in c])
        self.assertAlmostEqual(direct,2*np.sum(area*q*(1-q)),places=14)

    def test_current_subset_matches_global_refinement(self):
        polys=[box(0,0,2,2),box(1,0,3,2),box(0,1,2,3),box(1,1,3,3),box(.1,.2,.5,.7)]
        rs=[dict(footprint=list(p.exterior.coords)) for p in polys]
        faces,votes,area,domain=common_basis(rs)
        for threshold in [2,3]:
            region=pure_current_subset_region(rs,[0,1,2,3],threshold)
            selected=votes[:4].sum(0)>=threshold
            self.assertAlmostEqual(region.area,float(area@selected),places=13)

if __name__=='__main__':unittest.main(verbosity=2)
