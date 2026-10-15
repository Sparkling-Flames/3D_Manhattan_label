import numpy as np
from tools.thesis_main.analysis.difficulty_target_integration_20261015 import compare_floor, classify_use


def test_scope_equivalence_not_best_overlap():
    a = [[0,0],[2,0],[2,2],[0,2]]
    assert compare_floor(a,a[::-1])[0] == 'same_vertices'
    assert compare_floor(a,[[0,0],[1,0],[2,0],[2,2],[0,2]])[0] == 'same_footprint'
    assert compare_floor(a,np.asarray(a)*1.01)[0] == 'different_floor'


def test_scope_and_use_limits_are_independent():
    base=dict(condition='manual',role='manual_development_candidate',stage='ordinary',
              same_target_quality_hold='False',latest_step_reference_pending='False',
              same_target_unconfirmed='False',route_uncertainty='',scope_diagnostic_reason='')
    assert classify_use(base,'same_vertices',True,'简单',False) == 'ordinary_same_target_conditional'
    assert classify_use(base,'same_vertices',False,'简单',False) == 'floor_only_target_equivalence'
    assert classify_use(base,'different_floor',False,'简单',False) == 'image_only_different_target'
    assert classify_use(base,'same_vertices',True,'困难',True) == 'hold_scope_or_reference'
    assert classify_use(dict(base,same_target_quality_hold='True'),'same_vertices',True,'简单',False) == 'hold_scope_or_reference'
    assert classify_use(dict(base,stage='doorway',same_target_unconfirmed='True'),
                        'same_vertices',True,'单列',False) == 'separate_special_or_pending'
