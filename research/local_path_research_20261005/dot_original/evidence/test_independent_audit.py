"""Small self-tests for the independent checker; not the delivered 27-test suite."""
import unittest
from pathlib import Path
import independent_audit as A
class TestExactAudit(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.d=A.read(A.ROOT/'inputs/domain.json');cls.p=A.read(A.ROOT/'inputs/probes.json')
        cls.c=A.build(cls.d,cls.p);cls.h=[c for c in cls.c if c['admissible']]
        cls.byid={c['id']:c for c in cls.c}
    def test_exact_boundary_and_inside(self):
        c=self.byid['C000000'];self.assertTrue(A.covers(c['nodes'],[-2,0]));self.assertTrue(A.covers(c['nodes'],[0,0]));self.assertFalse(A.covers(c['nodes'],[-2.01,0]))
    def test_invalid_intersection_and_anchor(self):
        self.assertFalse(self.byid['C002000']['geometry_valid']);self.assertFalse(self.byid['C000020']['geometry_valid'])
    def test_collinear_representation_equivalence(self):
        self.assertEqual(self.byid['C000000']['key'],self.byid['C200000']['key'])
    def test_top_visible_but_footprint_unchanged(self):
        a,b=self.byid['C000000'],self.byid['C000200']
        self.assertNotEqual(a['key'],b['key']);self.assertFalse(a['code'][4]);self.assertTrue(b['code'][4])
        self.assertEqual(a['code'][:4]+a['code'][5:],b['code'][:4]+b['code'][5:])
    def test_missing_not_false(self):
        claims=[dict(id=p['id'],probe_id=p['id'],source_group=p['id'],status='missing',value=False) for p in self.p]
        self.assertEqual(len(A.select(self.h,claims,self.p,0)),110)
    def test_group_count_not_assertion_count(self):
        t=self.byid['C101100'];claims=[dict(id=p['id'],probe_id=p['id'],source_group=p['id'],status='observed',value=v) for p,v in zip(self.p,t['code'])]
        claims[0]['value']=not claims[0]['value'];one=A.select(self.h,claims,self.p,1)
        same=A.select(self.h,claims+[dict(claims[0],id='repeat')],self.p,1)
        split=A.select(self.h,claims+[dict(claims[0],id='repeat',source_group='split')],self.p,1)
        self.assertEqual([c['id'] for c in one],[c['id'] for c in same]);self.assertIn(t,one);self.assertNotIn(t,split)
    def test_unique_wrong_or_right_same_observation(self):
        y=(False,False,False,True,True,True,True)
        cs=[c for c in self.h if sum(v!=w for v,w in zip(c['code'],y))<=1]
        self.assertEqual({c['key'] for c in cs},{self.byid['C000210']['key']})
        self.assertEqual(sum(v!=w for v,w in zip(self.byid['C000210']['code'],y)),1)
        self.assertEqual(sum(v!=w for v,w in zip(self.byid['C000010']['code'],y)),2)
if __name__=='__main__':unittest.main()
