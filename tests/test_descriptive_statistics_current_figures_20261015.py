import pandas as pd
import pytest

from tools.thesis_main.analysis.descriptive_statistics_current_figures_20261015 import ordinary_manual


def test_manual_panel_does_not_mix_conditions_special_layer_or_duplicate_people():
    frame=pd.DataFrame(dict(image_id=['i','i','j'],worker_id=['a','a','b'],condition=['manual','semi','manual'],
        analysis_layer=['ordinary_current','ordinary_current','special_or_pending_separate'],pool_source_workers=[3,8,4]))
    assert ordinary_manual(frame).worker_id.tolist()==['a']
    with pytest.raises(AssertionError):ordinary_manual(frame.assign(pool_source_workers=[2,8,4]))
    with pytest.raises(AssertionError):ordinary_manual(pd.concat([frame,frame.iloc[:1]]))


def test_scope_coverage_separates_reference_binding_and_statistical_admission():
    from tools.thesis_main.analysis.descriptive_statistics_current_figures_20261015 import scope_quality_coverage
    catalog=pd.DataFrame(dict(target_id=['A','B','old'],image_id=['i','j','i'],current_target=[True,True,False],
        full_reference_available=[True,False,True]))
    affected=pd.DataFrame(dict(object_id=['o1','o2','o3'],image_id=['i','i','j'],
        chosen_target_id=['A','A',None],current_target_id=['A','A','B'],score_input_eligible=[True]*3,
        person_quality_restriction_clear=[True,False,True],pool_analysis_eligible=[True]*3))
    audit=pd.DataFrame(dict(object_id=['o1','o2','o3'],current_quality_eligible=[True,False,False],
        rescore_status=['complete','complete','pending']))
    counts=scope_quality_coverage(catalog,affected,audit).set_index('state').n
    assert counts.tolist()==[1,1,2,1,2,1,1]
    with pytest.raises(AssertionError):
        scope_quality_coverage(catalog,pd.concat([affected,affected.iloc[:1]]),audit)
