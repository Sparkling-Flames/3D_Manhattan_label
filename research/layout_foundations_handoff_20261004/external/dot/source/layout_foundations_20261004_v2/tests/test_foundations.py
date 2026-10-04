import copy,sys,unittest,json
from pathlib import Path
import numpy as np
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'src'))
from arc_consensus import *
from quality import *
from simplify import *
from cases import *
class Tests(unittest.TestCase):
    def setUp(self):self.rs=[rectangle(1.,1.,'a'),rectangle(2.,1.,'b'),rectangle(1.5,1.2,'c')]
    def sample(self,r):return Ring(r).evaluate((np.arange(4096)+.173)*TAU/4096)
    def test_01_two_person_duality(self):
        o=fuse(self.rs[:2]);self.assertEqual(o['methods']['mv50']['equivalent_bev_threshold'],2)
        self.assertLess(Polygon(o['methods']['mv50']['footprint']).symmetric_difference(tile_vote(self.rs[:2],2)).area,1e-10)
        self.assertAlmostEqual(area_scores(Polygon(o['methods']['mv50']['footprint']),tile_vote(self.rs[:2],1))['iou'],.25)
    def test_02_odd_rules_equal(self):
        o=fuse(self.rs);self.assertLess(abs(self.sample(o['methods']['mv50'])-self.sample(o['methods']['mv_strict'])).max(),1e-8)
    def test_03_person_order_invariance(self):
        a=fuse(self.rs)['methods']['mv50'];b=fuse(self.rs[::-1])['methods']['mv50'];self.assertLess(abs(self.sample(a)-self.sample(b)).max(),1e-8)
    def test_04_person_rename_invariance(self):
        q=copy.deepcopy(self.rs)
        for j,r in enumerate(q):r['worker']='X'+str(10-j);r['id']='Y'+str(10-j)
        self.assertLess(abs(self.sample(fuse(q)['methods']['mv50'])-self.sample(fuse(self.rs)['methods']['mv50'])).max(),1e-8)
    def test_05_reverse_ring(self):
        r=copy.deepcopy(self.rs[0]);r['points']=np.array(r['points']).reshape(-1,2,2)[::-1].reshape(-1,2).tolist()
        self.assertLess(abs(self.sample(r)-self.sample(self.rs[0])).max(),1e-8)
    def test_06_cyclic_origin(self):
        r=copy.deepcopy(self.rs[0]);r['points']=np.roll(np.array(r['points']).reshape(-1,2,2),2,axis=0).reshape(-1,2).tolist()
        self.assertLess(abs(self.sample(r)-self.sample(self.rs[0])).max(),1e-8)
    def test_07_yaw_equivariance(self):
        q=copy.deepcopy(self.rs);shift=217.7
        for r in q:r['points']=[[float((x+shift)%W),y] for x,y in r['points']]
        a=fuse(self.rs)['methods']['mv50'];b=fuse(q)['methods']['mv50'];u=(np.arange(4096)+.33)*TAU/4096
        self.assertLess(abs(Ring(b).evaluate((u+shift/W*TAU)%TAU)-Ring(a).evaluate(u)).max(),1e-8)
    def test_08_input_immutable(self):
        before=digest(self.rs);fuse(self.rs);self.assertEqual(before,digest(self.rs))
    def test_09_duplicate_worker(self):
        q=copy.deepcopy(self.rs);q[1]['worker']=q[0]['worker']
        with self.assertRaises(ValueError):fuse(q)
    def test_10_duplicate_id(self):
        q=copy.deepcopy(self.rs);q[1]['id']=q[0]['id']
        with self.assertRaises(ValueError):fuse(q)
    def test_11_same_coordinates_independent_votes(self):
        q=copy.deepcopy(self.rs)
        for r in q:r['points']=copy.deepcopy(self.rs[0]['points'])
        o=fuse(q);self.assertEqual(o['n'],3);self.assertEqual(len(o['methods']['mv50']['provenance_intervals'][0]['top_sources']),3)
    def test_12_missing_points_retained(self):
        q=copy.deepcopy(self.rs);q[1]['points']=None;o=fuse(q)
        self.assertEqual(o['n'],3);self.assertFalse(o['methods']);self.assertEqual(len(o['failures']),1)
    def test_13_wrong_top_hemisphere(self):
        q=copy.deepcopy(self.rs);q[1]['points'][0][1]=300.;o=fuse(q)
        self.assertEqual(o['status'],'unsupported_entire_selected_roster')
    def test_14_canvas_bounds(self):
        q=copy.deepcopy(self.rs);q[1]['points'][0][1]=-1.;self.assertTrue(fuse(q)['failures'])
    def test_15_nan_input(self):
        q=copy.deepcopy(self.rs);q[1]['points'][0][1]=float('nan');self.assertTrue(fuse(q)['failures'])
    def test_16_mixed_population(self):
        q=copy.deepcopy(self.rs);q[1]['evidence_kind']='human_observed'
        with self.assertRaises(ValueError):fuse(q)
    def test_17_mixed_condition(self):
        q=copy.deepcopy(self.rs);q[1]['condition']='semi'
        with self.assertRaises(ValueError):fuse(q)
    def test_18_mixed_image(self):
        q=copy.deepcopy(self.rs);q[1]['image']='other'
        with self.assertRaises(ValueError):fuse(q)
    def test_19_metadata_not_fabricated(self):
        q=copy.deepcopy(self.rs);q[1]['source_point_indices']=[0];self.assertTrue(fuse(q)['failures'])
    def test_20_confirmed_complex_ring_not_resorted(self):
        q=failure_records();h=digest(q);o=fuse(q)
        self.assertEqual(o['status'],'unsupported_entire_selected_roster');self.assertEqual(h,digest(q));self.assertEqual(o['n'],2)
        self.assertTrue(footprint(q[0])[1].is_valid)
    def test_21_identity_boundary_zero(self):
        a=self.rs[0];self.assertLess(directed(a,a,0,.2)['mean_deg'],1e-7)
    def test_22_sampling_step_rejected(self):
        with self.assertRaises(ValueError):directed(self.rs[0],self.rs[1],0,0)
    def test_23_metric_bound_contains_fine(self):
        a,b=thin_feature();coarse=directed(b,a,0,.5);fine=directed(b,a,0,.01)
        self.assertLessEqual(abs(coarse['mean_deg']-fine['mean_deg']),coarse['mean_absolute_numerical_bound_deg']+fine['mean_absolute_numerical_bound_deg'])
        self.assertLessEqual(fine['max_lower_deg'],coarse['max_upper_deg']+1e-8)
    def test_24_narrow_feature_not_seen_in_columns(self):
        a,b=thin_feature();x=(np.arange(512)+.5)*TAU/512
        self.assertLess(abs(Ring(a).evaluate(x)-Ring(b).evaluate(x)).max(),1e-8)
        self.assertGreater(directed(b,a,0,.1)['max_lower_deg'],6.)
    def test_25_compression_narrow_peak(self):
        a,b=thin_feature();o=fuse([b])['methods']['mv50'];c=compress(o,1.)
        self.assertLess(abs(Ring(c).evaluate(100.4/W*TAU)-Ring(b).evaluate(100.4/W*TAU)).max(),1.+1e-8)
    def test_26_stationary_extremum_contains_dense(self):
        rng=np.random.default_rng(812)
        for _ in range(20):
            c,d=rng.normal(size=(2,2))*2;lo=rng.uniform(0,TAU);hi=lo+2.4;x=np.linspace(lo,hi,10001);m=np.c_[np.sin(x),np.cos(x)]
            self.assertGreaterEqual(extrema_error(c,d,lo,hi)+1e-8,H/np.pi*abs(np.arctan(m@c)-np.arctan(m@d)).max())
    def test_27_exact_knots_at_boundaries(self):
        a,b=thin_feature();r=Ring(b);u=np.array(b['points'])[::2,0]/W*TAU
        self.assertLess(abs(r.evaluate(u).T-np.array(b['points']).reshape(-1,2,2)[:,:,1]).max(),1e-8)
    def test_28_gt_fields_not_consumed(self):
        q=copy.deepcopy(self.rs)
        for r in q:r['gt']=dict(points=[[999.,999.]],preferred=True)
        self.assertEqual(fuse(q),fuse(self.rs))
    def test_29_source_points_all_accounted(self):
        o=fuse(self.rs)['methods']['mv50'];self.assertEqual(len(o['source_pair_residuals']),12)
    def test_30_roof_not_silently_constructed(self):
        o=fuse(self.rs)['methods']['mv50'];self.assertEqual(o['roof_interior'],'not_observed_not_assumed')
        self.assertIsNone(quality(o,self.rs[0],step=.2)['solid_iou'])
    def test_31_subdivision_curve_metric_invariance(self):
        a=self.rs[0];r=Ring(a);x=200.;y=r.evaluate(x/W*TAU);q=np.array(a['points']).reshape(-1,2,2).tolist()+[[[x,y[0]],[x,y[1]]]]
        q.sort(key=lambda p:p[0][0]);b=copy.deepcopy(a);b.update(points=[z for p in q for z in p],source_pair_indices=list(range(5)),source_point_indices=list(range(10)))
        self.assertLess(directed(b,a,0,.1)['mean_deg'],1e-6)
        self.assertLess(footprint(a)[1].symmetric_difference(footprint(b)[1]).area,1e-10)
    def test_32_label_not_single_truth(self):
        o=fuse(self.rs)['methods']['mv50'];self.assertFalse(o['ring_confirmed']);self.assertEqual(o['representation'],'paired_boundary_knots_not_semantic_corners')
if __name__=='__main__':unittest.main()
