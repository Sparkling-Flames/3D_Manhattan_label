"""只检查会改变研究解释的重要证据边界。"""
import pytest

from tools.thesis_main.analysis.v2_evidence_audit_20261019 import (
    attribution, index, number, public_value, scope_evidence, semi_evidence, time_evidence,
)


def object_record(**extra):
    return dict(object_id='v2:new:1', condition='manual', scene_category='clear',
        scene_oos_status='not_oos', scene_doorway_status='none',
        worker_scope_response='out_of_scope', source={'path':'received.json'},
        cleaning_disposition='retained', geometry={'status':'surface_valid'}, **extra)


def test_image_oos_labels_never_create_scope_accuracy_opportunities():
    obj = object_record()
    assert not scope_evidence(obj, {})['judgement_opportunity']
    old = dict(raw_binding_verified='True', historical_gold_current_clear_compatible='True',
               historical_task_gold='in_scope')
    assert scope_evidence(obj, old)['correct'] is False
    obj['scene_oos_status'] = 'confirmed'
    assert scope_evidence(obj, old)['correct'] is None


def test_new_reported_time_does_not_become_target_time():
    obj = object_record()
    quality = dict(source_active_time_seconds=123, reference_id='a', reference_version='v', pool_analysis_eligible=True)
    old = dict(target_matched_time_seconds='123', reference_id='a', reference_version='v')
    assert time_evidence(obj, quality, old)['target_matched_time_seconds'] is None
    obj['object_id'] = 'old'
    assert time_evidence(obj, quality, old)['target_matched_time_seconds'] == 123
    quality['reference_id'] = 'b'
    assert time_evidence(obj, quality, old)['target_matched_time_seconds'] is None


def test_reported_semi_edit_cannot_prove_correction_or_exact_initialization():
    obj = object_record()
    obj.update(condition='semi', semi_reported=dict(initialization_unchanged=False,
        known_error_unchanged=False, error_specific_outcome='unknown_after_edit'))
    evidence = semi_evidence(obj, {}, {}, {}, {}, {})
    assert evidence['reported_error_opportunity']
    assert evidence['edited_but_correction_unknown']
    assert not evidence['confirmed_error_opportunity']
    assert not evidence['exact_initialization_bound']
    assert evidence['corrected_confirmed'] is None


def test_historical_semi_gain_requires_current_geometry_reference_and_score_alignment():
    pts = [[100,100],[100,300],[500,100],[500,300]]
    obj = object_record()
    obj.update(object_id='old',condition='semi',points_1024x512=pts,original_export_points=pts)
    recovered = dict(initial_points_1024x512=pts,raw_final_points_1024x512=pts,current_final_points_1024x512=pts)
    frozen = dict(initial_points=pts, final_points=pts)
    gains = dict(paired_score_available='True',worker_gain_attributable_under_current_view='True',
        reference_id='ref',reference_version='v',final_B8L2='80',final_D10='81',
        initial_B8L2='78',initial_D10='79',worker_attributable_gain_B8L2='2',worker_attributable_gain_D10='2')
    q = dict(reference_id='ref',reference_version='v',diagnostic_B8L2=80,diagnostic_D10=81,quality_usable=True)
    init = dict(initialization_source_verified='True',recovered_edit_status='changed_coordinates')
    evidence = semi_evidence(obj,init,{},gains,recovered,frozen,q)
    assert evidence['paired_scores_current_adopted'] and evidence['worker_attributable_gain_available']
    q['reference_id']='another'
    assert not semi_evidence(obj,init,{},gains,recovered,frozen,q)['paired_scores_current_adopted']


def test_gt_and_policy_exclusion_does_not_become_individual_severe_error():
    obj = object_record(review_evidence={'gt_substantive_error':True})
    quality = dict(quality_usable=False, chosen_target_id='ref', quality_exclusion_reasons=['hold_gt_error'])
    evidence = attribution(obj, quality, {}, {})
    assert evidence['category'] == 'analysis_purpose_or_context_restriction'
    assert not evidence['legacy_explicit_person_error']
    assert evidence['independently_confirmed_severe_error'] is None
    assert evidence['context_factors']['gt_substantive_error']


def test_duplicate_objects_and_nonfinite_values_fail():
    with pytest.raises(ValueError, match='duplicate'):
        index([{'object_id':'a'},{'object_id':'a'}])
    with pytest.raises(ValueError, match='nonfinite'):
        number('NaN')
    assert number('') is None


def test_public_evidence_drops_source_accounts_and_machine_paths():
    value = public_value(dict(source_account_id=200, worker_id='W100',
        source={'completed_by':200,'path':'C:/Users/Example/private.json'},
        review={'reviewer':'real name','text':'review evidence'}))
    assert value['worker_id'] == 'W100'
    assert 'source_account_id' not in value
    assert 'completed_by' not in value['source']
    assert value['source']['path'] == '[non_repository_absolute_path_redacted]'
    assert value['review'] == {'text':'review evidence'}
