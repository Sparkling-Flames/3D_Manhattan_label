from tools.thesis_main.analysis.b8l2_shared_snapshot_20261016 import quality_reasons, member_changes
import pandas as pd


def test_new_coverage_does_not_need_old_score_but_pending_issue_and_holds_still_block():
    row=dict(pool_analysis_eligible=True,pool_analysis_exclusion_reasons=[],
        same_target_quality_hold='',latest_step_reference_pending='',original_holdout='',same_target_unconfirmed='')
    binding=dict(chosen_target_id='new',score_input_eligible=True,person_quality_restriction_clear=True)
    ref=dict(full_reference_available=True,current_target=True)
    difficulty=dict(difficulty_analysis_exclusion='')
    assert quality_reasons(row,binding,ref,difficulty)==[]
    assert 'current_image_issue_pending' in quality_reasons(row,binding,ref,
        dict(difficulty_analysis_exclusion='user_reported_issue_pending'))
    row['latest_step_reference_pending']='True'
    assert 'legacy:latest_step_reference_pending' in quality_reasons(row,binding,ref,difficulty)
    row['latest_step_reference_pending']=''
    assert 'reference_not_full' in quality_reasons(row,binding,dict(ref,full_reference_available=False),difficulty)
    assert 'space_binding_not_unique' in quality_reasons(row,dict(binding,chosen_target_id=''),None,difficulty)


def test_changes_keep_new_coverage_separate_from_same_member_metric_and_label_changes():
    prior=pd.DataFrame([dict(object_id='a',B8L2=40.,reference_id='r',current_target_id='r',
        difficulty_class='easy'),dict(object_id='b',B8L2=60.,reference_id='r',current_target_id='r',difficulty_class='hard')])
    current=pd.DataFrame([dict(object_id='a',B8L2=40.,reference_id='r',current_target_id='r',
        difficulty_class='medium',current_quality_eligible=True,quality_exclusion_reasons=[]),
        dict(object_id='b',B8L2=None,reference_id='r',current_target_id='new',
        difficulty_class='hard',current_quality_eligible=False,quality_exclusion_reasons=['reference_not_full']),
        dict(object_id='c',B8L2=80.,reference_id='r',current_target_id='r',
        difficulty_class='easy',current_quality_eligible=True,quality_exclusion_reasons=[])])
    result=member_changes(current,prior).set_index('object_id')
    assert result.loc['a','membership_change']=='retained'
    assert result.loc['a','label_changed'] and not result.loc['a','score_changed']
    assert result.loc['b','membership_change']=='removed' and result.loc['b','target_changed']
    assert result.loc['c','membership_change']=='added_new_score_coverage'
