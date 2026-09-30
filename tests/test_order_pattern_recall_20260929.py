from copy import deepcopy
import csv
import json

import pytest

from tools.thesis_main.analysis import order_pattern_recall_20260929 as pattern


def source(oid='a', xs=(1018, 2, 180, 400, 650), kind='annotation'):
    points = [[x, y] for x, bottom in zip(xs, (440, 350, 400, 390, 430)) for y in (150, bottom)]
    return dict(object_id=oid, object_kind=kind, image_id='image-' + oid, image_code=oid,
                worker_id='W028', condition='manual', preprocessing_status='ready',
                preprocessing='shared_x_periodic_shortest_arc_v1', preprocessed_points=points,
                links_zero_based=[[i, i + 1] for i in range(0, len(points), 2)],
                cleaning_disposition='retained', scene_category='ordinary',
                scene_doorway_status='none', scene_oos_status='not_oos')


def test_ring_identity_seed_and_gt_initial_order():
    assert pattern.ring_relation([0, 1, 2, 3], [2, 3, 0, 1]) == 'equivalent'
    assert pattern.ring_relation([0, 1, 2, 3], [3, 2, 1, 0]) == 'equivalent'
    assert pattern.ring_relation([0, 1, 2, 3], [0, 2, 1, 3]) == 'adjacency_changed'
    obj = source(kind='gt_manual_revision')
    assert pattern.initial_order(obj, {}) == [1, 2, 3, 4, 0]
    assert pattern.initial_order(obj, {'a': {'order': [0, 1, 3, 2, 4]}}) == [0, 1, 3, 2, 4]
    with pytest.raises(ValueError):
        pattern.ring_relation([0, 1, 2, 3], [0, 0, 2, 3])


def test_periodic_density_uses_prechange_coordinates_and_keeps_pair_identity():
    obj = source()
    snapshot = deepcopy(obj)
    result = pattern.prechange_features(obj, [0, 1, 2, 3, 4])
    assert result['min_periodic_gap_px'] == 8
    assert result['dense_two_pairs_24px'] is True
    assert result['dense_three_pairs_24px'] is False
    assert result['near_bearing_depth_jump'] is True
    assert obj == snapshot
    other = deepcopy(obj)
    other['latest_order'] = [0, 2, 1, 3, 4]
    assert pattern.prechange_features(other, [0, 1, 2, 3, 4]) == result


def test_candidate_gate_preserves_four_pair_semantics_and_prior_reviews():
    row = dict(object_kind='annotation', cleaning_disposition='retained',
               current_status='unreviewed', feature_status='ok', pair_count=4,
               explicit_order_evidence=False, any_acute=True, consecutive_acute=True,
               dense_three_pairs_24px=False, near_bearing_depth_jump=True)
    assert pattern.candidate_reason(row) == 'four_pairs_without_human_order_evidence'
    assert pattern.candidate_reason({**row, 'explicit_order_evidence': True}) == 'candidate'
    assert pattern.candidate_reason({**row, 'pair_count': 5}) == 'candidate'
    assert pattern.candidate_reason({**row, 'pair_count': 5, 'current_status': 'confirmed'}) == 'already_confirmed'
    assert pattern.candidate_reason({**row, 'pair_count': 5, 'current_status': 'pairing'}) == 'pairing_deferred'
    assert pattern.candidate_reason({**row, 'pair_count': 5, 'feature_status': 'floor_near_horizon'}) == 'geometry_unavailable'
    assert pattern.candidate_reason({**row, 'current_status': 'confirmed', 'feature_status': 'floor_near_horizon'}) == 'already_confirmed'
    assert pattern.candidate_reason({**row, 'pair_count': 5, 'cleaning_disposition': 'excluded_by_review'}) == 'excluded'
    for code in ('B6ByNegPMKs-40', 'X7HyMhZNoso-05'):
        assert pattern.candidate_reason({**row, 'pair_count': 5, 'image_code': code}) == 'user_no_recall_image'


def test_analysis_preserves_primary_and_crosscheck_groups_and_output_contract(tmp_path, monkeypatch):
    objects = {oid: source(oid) for oid in ('a', 'b', 'c', 'd')}
    objects['b']['image_id'] = objects['a']['image_id']
    objects['c']['scene_doorway_status'] = 'difficult'
    objects['c']['scene_oos_status'] = 'confirmed'
    records = {'a': {'status': 'confirmed', 'order': [0, 2, 1, 3, 4]},
               'b': {'status': 'confirmed', 'order': [0, 1, 2, 3, 4]},
               'c': {'status': 'confirmed', 'order': [0, 2, 1, 3, 4]}}
    origins = {'a': ['user'], 'b': ['user'], 'c': ['yizheng']}
    monkeypatch.setattr(pattern, '_read_context', lambda: ({oid: 'not_selected' for oid in objects}, set(), {}))
    snapshot = deepcopy((objects, records, origins))
    summary = pattern.analyze_patterns(objects, records, {}, origins, tmp_path)
    assert (objects, records, origins) == snapshot
    assert summary['primary_user']['adjacency_changed'] == 1
    assert summary['primary_user']['unchanged'] == 1
    assert summary['yizheng_crosscheck']['adjacency_changed'] == 1
    assert summary['candidate_count'] == 1
    assert summary['candidate_not_in_previous_queue'] == 1
    with (tmp_path / '顺序规律_全量特征.csv').open(encoding='utf-8-sig') as handle:
        rows = {r['object_id']: r for r in csv.DictReader(handle)}
    assert rows['a']['image_fold'] == rows['b']['image_fold']
    assert rows['b']['control_group'] == 'same_image_control'
    assert rows['c']['scene_doorway_status'] == 'difficult'
    assert rows['c']['scene_oos_status'] == 'confirmed'
    assert rows['c']['scene_group'] == 'doorway_and_oos'
    assert summary['same_image_pair_count_rule_results'][0]['changed'] == 1
    assert summary['same_image_pair_count_rule_results'][0]['unchanged_or_equivalent'] == 1
    assert json.loads((tmp_path / '顺序规律_summary.json').read_text(encoding='utf-8')) == summary
