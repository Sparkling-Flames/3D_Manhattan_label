import pytest

from tools.thesis_main.analysis.quality_downstream_audit_20261013 import centered_cells, check_member, csv_scores, reference_gap_action


def test_centering_uses_equal_workers_and_keeps_reference_condition_separate():
    rows = [dict(record_id=str(i), image_id='image', reference_id=ref, condition=cond,
                 worker_id=worker, scores={'Q': score}) for i, (ref, cond, worker, score) in enumerate([
                     ('A', 'manual', 'w1', 10), ('A', 'manual', 'w1', 30), ('A', 'manual', 'w2', 40),
                     ('B', 'manual', 'w1', 100), ('A', 'semi', 'w1', 100)])]
    cells = centered_cells(rows)
    manual = [c for c in cells if c['reference_id']=='A' and c['condition']=='manual']
    assert sorted(c['within_cell_difference']['Q'] for c in manual) == [-10, 10]
    assert all(c['within_cell_difference']['Q']==0 for c in cells if c not in manual)


def test_member_identity_bridge_never_equates_p_and_w_numbers():
    member = dict(record_id='R1', object_id='obj', quality_worker_id='W029', fusion_worker_alias='P001')
    gate = dict(record_id='R1', object_id='obj', worker_id='W029', image_id='im')
    check_member(member, gate, 'im')
    with pytest.raises(ValueError):
        check_member(member, {**gate, 'worker_id':'W001'}, 'im')


def test_missing_fusion_score_stays_null_distinct_from_zero():
    assert csv_scores({'a':'', 'b':'0'}, ['a','b']) == {'a':None, 'b':0.0}


def test_one_full_reference_does_not_override_an_admitted_floor_alternative():
    assert reference_gap_action(['GT'], [{'reference_id':'GT','full':True}, {'reference_id':'floor','full':False}]) == ('existing_reference_not_bound_to_fused_target', None)
    assert reference_gap_action(['GT'], []) == ('unique_existing_full_reference_conditional', 'GT')
    assert reference_gap_action([], [{'reference_id':'floor','full':False}]) == ('only_confirmed_floor_available', 'floor')
