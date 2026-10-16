import numpy as np
import pandas as pd
from tools.thesis_main.analysis.wall_consensus_d10_20261017 import add_dual, target_relation, ENGINE
from tools.thesis_main.analysis.scope_quality_scoring_20261016 import scoring_engine
from tools.thesis_main.analysis.quality_b8l2_d10_20261017 import dual_scores


def test_d10_changes_only_scale_preserves_missing_and_diagnostic_mask():
    with scoring_engine(ENGINE/'measurement_engine.zip',ENGINE/'working_models.py') as (_,models):
        metrics=dict(iou_2d=.8,S_bottom_deg=2.,dir=8.,Hmean=.1,Hcenter=.05)
        values=dual_scores(metrics,models)
        expected=100/(1+np.hypot(.25+4/32,1.5*64/(64+100))+(.1/.8)**2+(.05/.25)**2)
        assert np.isclose(values['D10'],expected) and values['D10']>values['B8L2']
        frame=pd.DataFrame([dict(metrics,B8L2=values['B8L2']),dict(metrics,B8L2=np.nan),
                            dict(metrics,B8L2=np.nan,Hmean=np.nan)])
        result=add_dual(frame,models)
        assert result.D10.notna().tolist()==[True,False,False]
        assert result.D10_numeric.notna().tolist()==[True,True,False]


def test_updated_target_binding_does_not_imply_one_shared_target():
    assert target_relation(['a','a'],'a')=='all_declared_target'
    assert target_relation(['a','b'],'a')=='contains_other_target'
    assert target_relation(['a',''],'a')=='pending'
