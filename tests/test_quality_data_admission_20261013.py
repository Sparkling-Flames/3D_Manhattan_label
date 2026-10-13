from tools.thesis_main.analysis.quality_data_admission_20261013 import decide_use, filter_search, conditional_development_allowed, scene_barriers


def test_special_scene_blocks_extension_even_when_source_status_unrecorded():
    for scene in ('oos', 'oos_pending', 'doorway_difficult', 'doorway_annotatable', 'oos_and_doorway'):
        barriers = scene_barriers({'scene': scene})
        assert decide_use('manual_priority', [], barriers, [], False)['role']=='held_or_diagnostic'
    assert scene_barriers({'scene':'unflagged'}) == []


def test_excluded_severe_is_only_an_exception_not_personnel():
    r = decide_use('manual_priority', ['excluded_worker:W019', 'formal_gate:excluded'], [],
                   ['pairing_unavailable'], True)
    assert r['role'] == 'severe_exception_candidate'
    assert not r['full_q_calibration_ready']
    assert not r['personnel_gate_compatible']


def test_exception_never_overrides_holdout_or_reference():
    for barrier in ['original_holdout', 'reference_excluded:original']:
        r = decide_use('manual_priority', ['formal_gate:excluded'], [barrier], [], True)
        assert r['role'] == 'held_or_diagnostic'
        assert not r['full_q_calibration_ready']


def test_ordinary_exclusion_and_unreviewed_do_not_create_anchor():
    r = decide_use('manual_priority', ['formal_gate:excluded'], [], [], False)
    assert r['role'] == 'held_or_diagnostic'
    assert not r['full_q_calibration_ready']


def test_trap_remains_out_even_with_severe_label():
    r = decide_use('semi_trap_separate', [], [], [], True)
    assert not r['full_q_calibration_ready']


def test_pool_membership_is_not_complete_geometry_or_reference():
    r = decide_use('manual_priority', [], [], ['outside_frozen_metrics'], False)
    assert r['role'] == 'manual_development_candidate'
    assert not r['full_q_calibration_ready']


def test_filter_never_keeps_one_side_or_unreviewed_as_negative():
    data = {'rows': [{'id': 'A'}, {'id': 'B'}], 'grades': [{'id': 'A'}, {'id': 'B'}],
            'constraints': [{'record_ids': ['A', 'B']}]}
    view = filter_search(data, {'A'})
    assert view['rows'] == [{'id': 'A'}]
    assert view['grades'] == [{'id': 'A'}]
    assert view['constraints'] == []
    assert len(data['rows']) == 2


def test_latest_borderline_holds_old_grade_without_deleting_geometry():
    data = {'rows': [{'id': 'A'}], 'grades': [{'id': 'A', 'grade': 2}], 'constraints': []}
    view = filter_search(data, {'A'}, {'A': 'J04'})
    assert view['rows'] == data['rows']
    assert view['grades'] == []
    assert data['grades'][0]['grade'] == 2


def test_explicit_applicability_is_not_the_conditional_development_gate():
    gate = dict(applicability_confirmed=False, new_descriptive_development_allowed=True,
                barriers=[], explicit_exposure_barriers=[])
    assert conditional_development_allowed(gate, False, False)
    gate.update(applicability_confirmed=True, explicit_exposure_barriers=['original_holdout'])
    assert not conditional_development_allowed(gate, False, False)


def test_scope_confounded_grade_stays_out_of_current_fit_view():
    data = {'rows': [{'id': 'A'}], 'grades': [{'id': 'A', 'scope_confounded_latest': True}], 'constraints': []}
    assert filter_search(data, {'A'})['grades'] == []
