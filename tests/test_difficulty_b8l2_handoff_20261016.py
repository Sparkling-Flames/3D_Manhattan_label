from copy import deepcopy
from tools.thesis_main.analysis.difficulty_b8l2_handoff_20261016 import changes
from tools.thesis_main.analysis.difficulty_pending_scope_audit_20261016 import displacement
from shapely.geometry import Polygon


def test_class_only_does_not_hide_reference_or_hold_changes():
    a=dict(current_class='简单',target_version='a',selected=dict(floor=[[0,0],[1,0],[0,1]]),
        gt_error_excluded=False,difficulty_analysis_eligible=True,difficulty_analysis_exclusion='')
    b=deepcopy(a);b['current_class']='中等'
    assert changes(a,b)['class_only']
    b['target_version']='b'
    assert changes(a,b)['target_changed'] and not changes(a,b)['class_only']
    b=deepcopy(a);b.update(gt_error_excluded=True,difficulty_analysis_eligible=False,difficulty_analysis_exclusion='gt_error')
    assert changes(a,b)['gt_or_eligibility_changed'] and not changes(a,b)['class_only']


def test_scope_displacement_is_directed_and_wrap_safe():
    source=Polygon([[-1,1],[1,1],[1,2],[-1,2]])
    assert displacement([[-.5,1.1],[.5,1.1],[.5,1.9],[-.5,1.9]],source)==0
    # 在ERP背面横跨环缝附近，小空间扩张不能被计成约1024像素。
    assert 0 < displacement([[-1.001,1],[1.001,1],[1.001,2],[-1.001,2]],source) < 1
