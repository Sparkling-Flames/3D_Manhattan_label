import numpy as np
from tools.thesis_main.analysis.wall_consensus_b8l2_20261016 import apply_scores, current_use
from tools.thesis_main.analysis.scope_quality_scoring_20261016 import scoring_engine


def test_b8l2_original_parameters_and_missing_height():
    with scoring_engine() as (_,m):
        row=apply_scores(dict(iou_2d=.8,S_bottom_deg=2.,dir=8.,Hmean=.1,Hcenter=.05,IoU3D100=75.),m,'ordinary_conditional')
        expected=100/(1+np.hypot(1/.8-1+4/32,.75)+(.1/.8)**2+(.05/.25)**2)
        assert np.isclose(row['B8L2'],expected)
        missing=apply_scores(dict(iou_2d=.8,S_bottom_deg=2.,dir=8.,Hmean=None,Hcenter=None),m,'ordinary_conditional')
        assert missing['B8L2'] is None and missing['B8L2_floor_upper_bound'] is not None


def test_current_holds_and_nonorthogonal_do_not_get_primary_score():
    assert current_use(False,True,'clear','not_oos',False)=='source_pool_held'
    assert current_use(True,False,'clear','not_oos',False)=='pending_image_diagnostic'
    assert current_use(True,True,'clear','not_oos',True)=='target_binding_pending_diagnostic'
    with scoring_engine() as (_,m):
        row=apply_scores(dict(iou_2d=.9,S_bottom_deg=1.,dir=12.,Hmean=.1,Hcenter=.05,IoU3D100=85.),m,'nonorthogonal_diagnostic')
        assert row['B8L2'] is None and row['B8L2_no_D_diagnostic'] is not None
        assert row['IoU3D100']==85
