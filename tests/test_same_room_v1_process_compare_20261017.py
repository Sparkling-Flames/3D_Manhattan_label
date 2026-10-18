import pandas as pd
import pytest

from tools.thesis_main.analysis.same_room_v1_process_compare_20261017 import (
    align_actual, within_view_difference,
)


def test_missing_real_prefix_is_not_run_and_extra_rows_are_rejected():
    plans=pd.DataFrame(dict(request_id=['p','p'],replay_id=['r','r'],side=['a','a'],k=[1,2]))
    actual=plans.iloc[:1].assign(complete_evaluable=True)
    result=align_actual(plans,actual)
    assert result.execution_status.tolist()==['observed','not_run']
    with pytest.raises(ValueError,match='outside'):
        align_actual(plans,actual.assign(k=3))


def test_stability_geometry_is_only_compared_within_the_same_camera():
    state=dict(candidate=dict(footprint=[[0,0],[1,0],[1,1],[0,1]]),node_consensus=dict(nodes=[1]*4))
    assert within_view_difference('image',state,'image',state)['floor_1_minus_iou']==0.
    with pytest.raises(ValueError,match='cross-camera'):
        within_view_difference('camera_a',state,'camera_b',state)
    missing=dict(candidate=dict(footprint=[]),node_consensus=dict(nodes=[]))
    assert within_view_difference('image',state,'image',missing)['floor_1_minus_iou'] is None
