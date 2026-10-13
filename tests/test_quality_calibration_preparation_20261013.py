import numpy as np

from tools.thesis_main.analysis import quality_calibration_preparation_20261013 as q


def test_matched_bottom_perturbation_keeps_top_and_declares_budget():
    points = q.reference_points(1, 4)
    original = points.copy()
    for mode in ('single_bottom', 'distributed_bottom'):
        changed = q.perturb_bottom(points, mode, 8, -1)
        np.testing.assert_array_equal(changed[::2], points[::2])
        np.testing.assert_array_equal(changed[:, 0], points[:, 0])
        assert np.isclose(q.paired_2d(changed, points)['bottom_y_rms_px'], 8)
        assert np.count_nonzero(changed[1::2, 1]-points[1::2, 1]) == (1 if mode=='single_bottom' else 4)
    np.testing.assert_array_equal(points, original)


def test_direction_descriptor_does_not_confuse_rotation_with_distortion():
    assert q.direction_profile(q.rectangle(2, 2))['D_rms_deg'] < 1e-10
    e = q.engine()
    p = q.perturb_bottom(q.reference_points(2, 2), 'single_bottom', 8, 1)
    profile = q.direction_profile(e['geometry'](p))
    assert profile['D_rms_deg'] > 0
    assert 0 < profile['two_largest_edges_squared_contribution_share'] <= 1


def test_severe_constraint_requires_individual_review_and_no_other_hold():
    row = dict(severe_exception=True, severe_historical_full_q_ready=True, condition='manual',
               context_barriers=[], original_holdout=False, existing_conditional_development_allowed=True,
               severe_review=dict(effective_review_status='reviewed_severe'))
    assert q.severe_ready(row)
    assert not q.severe_ready(dict(row, original_holdout=True))
    assert not q.severe_ready(dict(row, context_barriers=['reference_unresolved']))
    assert not q.severe_ready(dict(row, severe_review=dict(effective_review_status='unreviewed')))


def test_preparation_contract_keeps_one_config_and_separate_pools():
    baseline = q.read(q.OUT/'BASELINE.json')
    evidence = q.read(q.OUT/'EVIDENCE.json')
    summary = q.read(q.OUT/'SUMMARY.json')
    assert baseline['configuration_count']==1 and baseline['new_parameter_comparison_performed'] is False
    assert len({r['record_id'] for r in baseline['rows']})==583
    assert sum(r['use']=='separate_severe_constraint' for r in baseline['rows'])==9
    assert all(r['original_holdout'] is False and r['formal_eligibility_newly_granted'] is False for r in baseline['rows'])
    t20 = next(r for r in evidence['question_groups'] if r['group']=='T20')
    assert '可以稍微扣多一点' in t20['original_and_interpretation']['verbatim']
    assert t20['numeric_target'] is None
    assert summary['parameter_search_performed'] is False and summary['parameter_files_changed'] is False
