from copy import deepcopy

from tools.thesis_main.analysis.quality_current_candidate_view_20261013 import candidate_row, load_inputs, existing_routed_view


def test_raw_and_admission_diagnostics_do_not_change_processed_scores():
    scorer, configs, search, admission = load_inputs()
    row = search['rows'][0]
    gate = admission[row['id']]
    original = candidate_row(row, gate, scorer, configs)
    changed = deepcopy(row)
    changed['raw_alignment'] = {'status': 'available', 'X_rms_deg': 90}
    blocked = {**gate, 'role': 'held_or_diagnostic', 'personnel_barriers': ['excluded_worker:test'],
               'full_q_calibration_ready': False}
    updated = candidate_row(changed, blocked, scorer, configs)
    assert original['scores'] == updated['scores']
    assert updated['raw_alignment'] != original['raw_alignment']
    assert not updated['raw_input_penalty_included']
    assert not updated['formal_eligibility_newly_granted']


def test_missing_height_stays_null_not_zero_or_floor_score():
    scorer, configs, search, admission = load_inputs()
    row = deepcopy(search['rows'][0])
    row['metrics']['Hmean'] = None
    row['metrics']['Hm'] = None
    result = candidate_row(row, admission[row['id']], scorer, configs)
    for score in result['scores'].values():
        assert score['score'] is None
        assert score['height_loss'] is None
        assert score['floor_score'] is not None


def test_unconfirmed_old_applicability_does_not_suppress_conditional_scores():
    scorer, configs, search, admission = load_inputs()
    row = next(r for r in search['rows'] if not r['applicability_confirmed'])
    result = candidate_row(row, admission[row['id']], scorer, configs)
    assert not result['old_applicability_confirmed']
    assert result['conditional_diagnostic_use']
    assert all(v['score'] is not None for v in result['scores'].values())


def test_existing_routed_floor_only_preserves_missing_full_score():
    _, _, _, admission = load_inputs()
    result = existing_routed_view(admission)
    floor_only = [r for r in result['rows'] if r['route']['status'] == 'available'
                  and r['route']['selected_full_status'] != 'available']
    assert floor_only
    for row in floor_only:
        assert all(v['full'] is None and v['floor'] is not None for v in row['scores_under_selected_reference'].values())
        assert not row['current_coordinates_recomputed']
        assert not row['formal_eligibility_newly_granted']
    by_id = {r['record_id']: r for r in result['rows']}
    assert by_id['R02962']['route']['selected_candidate_id'] == 'uNb9QFRL6hY-88:D'
    for rid in ('R03258', 'R01412'):
        assert by_id[rid]['route']['selected_candidate_id'] in ('uNb9QFRL6hY-88:A', 'uNb9QFRL6hY-88:B')
    assert result['summary']['explicit_human_assignments_preserved'] == 5
    assert result['summary']['human_family_restrictions_preserved'] == 2
