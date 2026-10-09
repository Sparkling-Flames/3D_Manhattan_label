import json

import pytest

from tools.thesis_main.analysis.difficulty_structure_20261009 import (
    classify_structure, apply_exception, select_reference, scene_evidence, explicit_exception, summary,
)


@pytest.mark.parametrize('count,hidden,expected', [
    (4, 0, '简单'), (6, 0, '中等'), (5, 0, '中等'),
    (4, 1, '困难'), (16, 2, '困难'),
])
def test_two_variable_rule(count, hidden, expected):
    assert classify_structure(count, 'valid_camera_inside', hidden) == (expected, '')


@pytest.mark.parametrize('count,status,hidden', [
    (3, 'valid_camera_inside', 0),
    (4, 'invalid_polygon', None),
    (4, 'camera_not_strictly_inside', None),
    (4, 'valid_camera_inside', None),
])
def test_undefined_geometry_or_count_remains_pending(count, status, hidden):
    label, reason = classify_structure(count, status, hidden)
    assert label == '待定' and reason


def test_occlusion_count_drift_is_an_error():
    with pytest.raises(ValueError, match='invalid_hidden_count'):
        classify_structure(4, 'valid_camera_inside', 5)


def test_exception_preserves_raw_class_and_unknown_scene_does_not_gate():
    assert apply_exception('简单', '', None) == ('简单', 'applicable', '')
    hold = {'status': 'user_analysis_hold', 'reason': '明确暂缓'}
    assert apply_exception('简单', '', hold) == ('待定', 'user_analysis_hold', '明确暂缓')
    invalid = {'status': 'confirmed_unannotatable', 'reason': '明确不可标'}
    assert apply_exception('困难', '', invalid) == ('不适用', 'confirmed_unannotatable', '明确不可标')
    assert apply_exception('待定', 'invalid_polygon', None) == ('待定', 'geometry_pending', 'invalid_polygon')


def test_reference_selection_is_a_view_and_missing_original_is_visible():
    original = {'object_id': 'o', 'object_kind': 'gt_original'}
    revised = {'object_id': 'r', 'object_kind': 'gt_manual_revision'}
    image = {'references': {'gt_original': 'o', 'gt_manual_revision': 'r'}}
    objects = {'o': original, 'r': revised}
    assert select_reference(image, objects, True) is revised
    assert select_reference(image, objects, False) is original
    with pytest.raises(KeyError):
        select_reference(image, {'r': revised}, False)


def test_special_status_is_independent_not_certified_ordinary():
    row = dict(oos_status='not_recorded', doorway_status='not_recorded',
               oos_source='inventory', doorway_source='inventory',
               doorway_annotation_source='', stable_nonorthogonal=True,
               latest_scene_note='')
    result = scene_evidence(row, [])
    assert result['scene_stratum'] == 'unflagged'
    assert result['scene_review_status'] == 'unflagged_not_certified_normal'
    assert result['annotatability_status'] == 'nonorthogonal_annotatable'
    assert result['oos_subtype'] == 'nonorthogonal_annotatable'
    json.dumps(result, allow_nan=False)


def test_resolved_hold_and_reference_wording_have_different_effects():
    record = dict(semantic_status='all_analysis_hold_by_user', summary='当前暂停裁决',
                  reason='暂停', source='image_review#/image')
    evidence = [dict(evidence_kind='semantic_image_evidence', source_object_id='object', record=record)]
    hold = explicit_exception(evidence)
    assert hold['status'] == 'user_analysis_hold'
    assert hold['evidence_type'] == 'current_resolved_semantic_decision'
    record['semantic_status'] = 'reference_version_wording_unresolved'
    assert explicit_exception(evidence) is None
    record['semantic_status'] = 'resolved_by_coverage_followup'
    record['reason'] = '本次图片补审；pRb-16按原话暂缓全部分析'
    assert explicit_exception(evidence)['status'] == 'user_analysis_hold'


def test_unknown_room_is_not_an_extra_declared_room():
    template = dict(building='B', room='', raw_structure_class='简单', coarse_class='简单',
                    selected_gt_pair_count=4, structural_occlusion=False,
                    gt_ring_confirmed=False, applicability_status='applicable')
    result = summary([template, dict(template, room=None), dict(template, room='G001')])
    assert result['rooms'] == 1
    assert result['room_unknown_images'] == 2
