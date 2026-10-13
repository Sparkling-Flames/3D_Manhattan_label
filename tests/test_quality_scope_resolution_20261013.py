import pytest
from tools.thesis_main.analysis.quality_scope_resolution_20261013 import floor_equivalence, route_disposition, calibration_stage, review_questions


def test_height_review_collects_observations_not_reference_assignment():
    card=dict(group='height',image_code='B6ByNegPMKs-33')
    questions=review_questions(card)
    assert [q['id'] for q in questions]==['space_extent','top_in_photo','height_in_3d']
    assert all('uncertain' in dict(q['options']) for q in questions)
    assert all(q['purpose'] and not q.get('default') for q in questions)
    assert review_questions(dict(card,image_code='uNb9QFRL6hY-36'))[-1]['id']=='floor_steps'
    fusion=review_questions(dict(group='fusion',references=[dict(candidate_id='A',label='空间A')]))
    assert [q['id'] for q in fusion]==['fusion_extent']
    assert 'mixed' in dict(fusion[0]['options'])


def test_oos_never_enters_doorway_adjustment_and_unknown_is_not_certified_normal():
    assert calibration_stage('oos_and_doorway','manual')=='oos_diagnostic_only_never_fit'
    assert calibration_stage('clear','oos')=='oos_diagnostic_only_never_fit'
    assert calibration_stage('doorway_annotatable','manual')=='doorway_second_stage_review_before_small_adjustment'
    assert calibration_stage('doorway_difficult','manual')=='doorway_second_stage_review_before_small_adjustment'
    assert calibration_stage('unflagged','manual')=='ordinary_first_stage_candidate'


def test_same_floor_ignores_ring_start_direction_and_collinear_vertices():
    a = [[-1,-1],[1,-1],[1,1],[-1,1]]
    b = [[1,1],[1,0],[1,-1],[-1,-1],[-1,1]]
    assert floor_equivalence(a,b)['equivalent']
    assert not floor_equivalence(a,[[x*2,z] for x,z in a])['equivalent']


def test_frozen_local_route_is_conditional_and_fallback_does_not_bind():
    local = route_disposition({'candidate_id':'B','route_reason':'local_differentiating_structure'})
    assert local['conditional_candidate_id']=='B'
    assert local['confirmed_target_id'] is None
    fallback = route_disposition({'candidate_id':'A','route_reason':'local_evidence_insufficient_floor_iou_fallback'})
    assert fallback['conditional_candidate_id'] is None
    assert fallback['human_review_required_for_single_target']


def test_invalid_floor_never_becomes_equivalent():
    with pytest.raises(ValueError):
        floor_equivalence([[0,0],[1,1],[1,0],[0,1]], [[0,0],[1,0],[1,1]])
