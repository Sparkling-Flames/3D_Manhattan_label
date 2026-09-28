import pytest
from tools.thesis_main.analysis.prepare_review_repairs_20260928 import preview_operation


def test_preview_preserves_input_and_stable_labels():
    points=[[1,2],[3,4],[5,6]]
    result=preview_operation(points,['p1','p2','p3'],delete=['p2'],set_x_from=['p3','p1'])
    assert points==[[1,2],[3,4],[5,6]]
    assert result==dict(after_points=[[1,2],[1,6]],after_labels=['p1','p3'])
    with pytest.raises(ValueError,match='requested_point_missing'):
        preview_operation(result['after_points'],result['after_labels'],delete=['p2'])
