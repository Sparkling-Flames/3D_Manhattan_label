from tools.thesis_main.analysis.quality_calibration_cohorts_20261013 import source_cohort, select_evidence


def record(condition='semi', trap='confirmed_nontrap', edit='changed_coordinates', **extra):
    return dict(condition=condition, trap_status=trap, model_edit_status=edit,
                explicit_model_influence=False, annotation_traits={'tags': []}, **extra)


def test_traps_stay_separate_even_after_editing():
    for edit in ('changed_coordinates', 'unchanged_coordinates'):
        assert source_cohort(record(trap='confirmed_trap', edit=edit)) == 'semi_trap_separate'


def test_manual_bad_quality_is_not_a_source_exclusion():
    r = record('manual', 'unknown', 'not_checked_non_semi', score=0)
    assert source_cohort(r) == 'manual_priority'


def test_nontrap_unchanged_and_unknown_are_not_clean_semi():
    assert source_cohort(record(edit='unchanged_coordinates')) == 'semi_unchanged_separate'
    assert source_cohort(record(trap='unknown')) == 'semi_unverified_separate'
    assert source_cohort(record()) == 'semi_nontrap_changed_candidate'
    r = record()
    r['annotation_traits'] = {}
    assert source_cohort(r) == 'semi_nontrap_changed_candidate'
    r = record()
    r['annotation_traits']['tags'] = ['model_unchanged']
    assert source_cohort(r) == 'semi_model_issue_separate'


def test_evidence_requires_all_members_and_preserves_originals():
    grades = [{'id': 'A'}, {'id': 'B'}]
    constraints = [{'record_ids': ['A', 'B']}, {'record_ids': ['A']}]
    result = select_evidence(grades, constraints, {'A'})
    assert result == {'grades': [{'id': 'A'}], 'constraints': [{'record_ids': ['A']}]}
    assert len(grades) == len(constraints) == 2
