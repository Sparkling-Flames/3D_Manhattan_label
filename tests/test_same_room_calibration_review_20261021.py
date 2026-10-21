import unittest
import numpy as np
import pandas as pd
from tools.thesis_main.analysis.same_room_calibration_review_20261021 import peer_means, residual_history, aggregate

class CalibrationReviewTests(unittest.TestCase):
    def test_peers_exclude_self_and_keep_absent_person(self):
        p=pd.DataFrame({'A':[0.,np.nan],'B':[100.,20.],'C':[50.,40.]})
        out=peer_means(p)
        self.assertEqual(out.loc[0,'A'],75.)
        self.assertEqual(out.loc[1,'A'],30.)
        self.assertEqual(out.loc[1,'B'],40.)

    def test_matched_observed_source_budget(self):
        p=pd.DataFrame({'A':[10.,np.nan],'B':[30.,80.],'C':[50.,100.]})
        peers=peer_means(p)
        self.assertEqual(peers.where(p.notna()).mean()['A'],40.)
        self.assertEqual(peers.mean()['A'],65.)
        self.assertEqual(p['A'].count(),1)

    def test_outbuilding_only_and_singletons_unknown(self):
        d=pd.DataFrame({'building_id':['held','held','train','train','train'],'image_id':['t','t','s','s','z'],'worker_id':['A','B','A','B','C'],'training_allowed':[True]*5,'Q':[0.,100.,80.,60.,99.]})
        r=residual_history(d,'Q','held')
        self.assertEqual(r.loc['A','relative'],20.)
        self.assertEqual(r.loc['A','baseline'],80.)
        self.assertTrue(np.isnan(r.loc['C','relative']))
        d.loc[d.building_id.eq('held'),'Q']=9999
        pd.testing.assert_frame_equal(r,residual_history(d,'Q','held'))

    def test_admission_excludes_unapproved_person(self):
        d=pd.DataFrame({'building_id':['train']*3,'image_id':['s']*3,'worker_id':['A','B','C'],'training_allowed':[True,True,False],'Q':[80.,60.,0.]})
        r=residual_history(d,'Q','held')
        self.assertEqual(r.loc['A','relative'],20.)
        self.assertNotIn('C',r.index)

    def test_building_equal_not_row_equal(self):
        rows=[]
        for b,targets,error in [('A',['a'],10.),('B',['b','c','d'],30.)]:
            for t in targets:
                rows.append(dict(metric='Q',origin='all',group_id=b,building=b,target_image=t,worker_id='W',m=2,N=3,method='test',absolute_error=error,error=error,actual=40.,relative=-1.))
        _,_,s=aggregate(pd.DataFrame(rows))
        self.assertTrue((s.mae==20.).all())

if __name__=='__main__':unittest.main()

