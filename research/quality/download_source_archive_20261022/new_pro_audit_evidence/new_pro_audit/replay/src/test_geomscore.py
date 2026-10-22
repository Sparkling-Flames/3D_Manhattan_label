import unittest,json,copy
from pathlib import Path
from dataclasses import replace
import numpy as np
from geomscore import *
from run_controls import geom,square,micro_steps,bump,rotate,erp

class GeometryTests(unittest.TestCase):
    def setUp(self):self.r=geom(square())
    def check_perfect(self,s):
        for k in ['QA','QB','QC']:self.assertAlmostEqual(s[k],100,places=7)
    def test_identity(self):self.check_perfect(score_pair(self.r,self.r))
    def test_nonorthogonal_reference_is_reference(self):
        g=geom(square()@np.array([[1,.15],[0,1]]));self.check_perfect(score_pair(g,g))
    def test_same_wall_insert(self):
        p=np.insert(square(),1,[0,-2],axis=0);self.check_perfect(score_pair(geom(p),self.r))
    def test_same_wall_variable_height_insert(self):
        p=np.insert(square(),1,[0,-2],axis=0);self.check_perfect(score_pair(geom(p,[1,1.5,2,3,2]),geom(square(),[1,2,3,2])))
    def test_top_kink_not_discarded_with_floor_point(self):
        p=np.insert(square(),1,[0,-2],axis=0);s=score_pair(geom(p,[2,2.8,2,2,2]),self.r)
        self.assertEqual(s['angle_detail']['detail_loss'],0);self.assertGreater(s['surface_height']['local_error'],.10);self.assertLess(s['QA'],90)
    def test_micro_one(self):
        s=score_pair(geom(micro_steps(square(),.001)),self.r);self.assertGreater(s['QA'],99.99)
    def test_micro_four(self):
        s=score_pair(geom(micro_steps(square(),.001,True)),self.r);self.assertGreater(s['QA'],99.99)
    def test_erp_roundtrip(self):
        g=geom(bump(),[2,2.1,2.2,2.3,2.4,2.3,2.2,2.1]);v=from_erp(erp(g))
        self.assertTrue(np.allclose(v['bottom3d'],g['bottom3d']));self.assertTrue(np.allclose(v['top3d'],g['top3d']))
    def test_orientation(self):
        g=geom(bump());s=score_pair(g,self.r)
        z={k:list(reversed(g[k])) for k in ['bottom3d','top3d']};q=score_pair(z,self.r)
        for k in ['QA','QB','QC']:self.assertAlmostEqual(s[k],q[k],places=9)
    def test_cyclic_index(self):
        g=geom(bump());z={k:np.roll(g[k],3,axis=0).tolist() for k in ['bottom3d','top3d']}
        s=score_pair(g,self.r);q=score_pair(z,self.r)
        for k in ['QA','QB','QC']:self.assertAlmostEqual(s[k],q[k],places=9)
    def test_yaw_not_angle_or_missing(self):
        for angle in [5,10]:
            s=score_pair(rotate(self.r,angle),self.r)
            self.assertAlmostEqual(s['angle_detail']['angle_penalty'],0);self.assertAlmostEqual(s['angle_detail']['structural_loss'],0)
            self.assertAlmostEqual(s['turning']['distance_deg'],0,places=7);self.assertLess(s['I'],1)
    def test_rigid_common_rotation(self):
        a=geom(bump());s=score_pair(a,self.r);q=score_pair(rotate(a,23),rotate(self.r,23))
        self.assertAlmostEqual(s['QA'],q['QA'],places=7);self.assertAlmostEqual(s['QB'],q['QB'],places=7);self.assertLess(abs(s['QC']-q['QC']),.15)
    def test_detail_budget(self):
        s=score_pair(self.r,geom(bump()));base=score_pair(self.r,geom(bump()),replace(Config(),edit_budget=0))
        self.assertGreater(s['angle_detail']['detail_loss'],0);self.assertGreaterEqual(s['QA']/base['QA'],.85)
    def test_extra_vs_missing_symmetry_flat(self):
        a=geom(bump());s=score_pair(a,self.r);q=score_pair(self.r,a)
        for k in ['QA','QB','QC']:self.assertAlmostEqual(s[k],q[k],places=7)
    def test_scale_intrinsic_not_global(self):
        s=score_pair(geom(square()*1.2),self.r)
        self.assertAlmostEqual(s['turning']['distance_deg'],0,places=7);self.assertAlmostEqual(s['I'],1/1.2**2);self.assertLess(s['QA'],75)
    def test_translation_intrinsic_not_global(self):
        s=score_pair(geom(square()+[.1,0]),self.r);self.assertAlmostEqual(s['turning']['distance_deg'],0,places=7);self.assertLess(s['I'],1)
    def test_shape_invariance_turning_only(self):
        p=bump();q=np.array(rotate(geom(p),37)['bottom3d'])[:,[0,2]]*1.3+[3,4]
        self.assertAlmostEqual(turning_distance(p,q)['distance_deg'],0,places=5)
    def test_turning_symmetry(self):
        a=bump();b=square()@np.array([[1,.2],[0,1]])
        self.assertAlmostEqual(turning_distance(a,b)['distance_deg'],turning_distance(b,a)['distance_deg'],places=8)
    def test_height_uniform_has_zero_local(self):
        s=score_pair(geom(square(),3),self.r);self.assertAlmostEqual(s['surface_height']['local_error'],0);self.assertGreater(s['surface_height']['mean_log_error'],0)
    def test_height_reciprocity(self):
        s=score_pair(geom(square(),4),self.r);q=score_pair(geom(square(),1),self.r)
        self.assertAlmostEqual(s['QA'],q['QA'])
    def test_height_local_monotone(self):
        qs=[score_pair(geom(square(),[2+x,2-x,2+x,2-x]),self.r)['QA'] for x in [.1,.2,.4,.8]]
        self.assertTrue(np.all(np.diff(qs)<0))
    def test_mean_analytical(self):self.assertAlmostEqual(shell(geom(square(),[1,2,3,2]))['mu'],2)
    def test_disjoint_zero(self):
        s=score_pair(geom(square()+[10,0]),self.r)
        for k in ['QA','QB','QC']:self.assertEqual(s[k],0)
    def test_no_missing_top_imputation(self):
        with self.assertRaises(KeyError):score_pair({'bottom3d':self.r['bottom3d']},self.r)
    def test_invalid_floor_not_repaired(self):
        with self.assertRaises(ValueError):score_pair(geom([[-1,-1],[1,1],[-1,1],[1,-1]]),self.r)
    def test_bad_pairing_rejected(self):
        g=copy.deepcopy(self.r);g['top3d'][0][0]+=.1
        with self.assertRaises(ValueError):score_pair(g,self.r)
    def test_bad_floor_scale_rejected(self):
        g=copy.deepcopy(self.r);g['bottom3d'][0][1]=-2
        with self.assertRaises(ValueError):score_pair(g,self.r)
    def test_nonfinite_rejected(self):
        g=copy.deepcopy(self.r);g['bottom3d'][0][0]=float('nan')
        with self.assertRaises(ValueError):score_pair(g,self.r)
    def test_scope_ledger_present(self):
        p=Path(__file__).resolve().parents[1]/'inputs/current_pairs.json';d=json.load(open(p));self.assertEqual(len(d),244)
        self.assertFalse(any(x['worker_id'] in ['W019','W026'] for x in d));self.assertTrue(all(x['live_loader_verified'] is False for x in d))
    def test_deep_slot_is_known_weakness(self):
        s=score_pair(self.r,geom(bump(-1.5,1)))
        # This records an unfavorable behavior instead of hiding it with a special-case patch.
        self.assertGreater(s['QA'],85);self.assertLess(s['QB'],55)
if __name__=='__main__':unittest.main(verbosity=2)
