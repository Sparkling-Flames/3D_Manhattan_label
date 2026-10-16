from tools.thesis_main.analysis.b8l2_usage_snapshot_20261016 import usage_policy


def inputs():
    row=dict(pool_analysis_eligible=True,pool_analysis_exclusion_reasons=[],difficulty_analysis_exclusion='',
             same_target_quality_hold=False,latest_step_reference_pending=False,original_holdout=False,
             same_target_unconfirmed=True,stage='doorway')
    obj=dict(cleaning_disposition='retained',independent_vote_eligible=True,
             main_quality_gate=dict(status='out_of_primary_scene',reasons=['doorway_difficult']),
             worker_quality_gate='out_of_primary_scene')
    binding=dict(chosen_target_id='target')
    reference=dict(full_reference_available=True,current_target=True)
    geometry=dict(full_input_available=True)
    scene=dict(is_doorway=True,is_oos=False)
    return row,obj,binding,reference,geometry,scene


def test_doorway_scene_blanket_and_old_uncertified_hold_are_explicitly_bypassed():
    args=inputs();result=usage_policy(*args,full_score_state='computed')
    assert result['quality_usable'] and result['purpose_bypass']


def test_specific_hold_and_unconfirmed_are_not_scene_bypasses():
    args=inputs();args[0]['same_target_quality_hold']=True
    result=usage_policy(*args,full_score_state='computed')
    assert not result['quality_usable'] and not result['target_binding_unique']
    args=inputs();args[1]['main_quality_gate']=dict(status='hold_scene_or_reference',reasons=['unconfirmed'])
    result=usage_policy(*args,full_score_state='computed')
    assert not result['target_binding_unique'] and not result['quality_usable']


def test_oos_dominates_doorway_and_calculated_is_not_quality():
    args=inputs();args[-1]['is_oos']=True
    result=usage_policy(*args,full_score_state='computed')
    assert not result['quality_usable'] and 'oos_diagnostic_only' in result['quality_exclusion_reasons']


def test_cleaning_pool_and_other_reference_restrictions_survive():
    for key in ['cleaning','pool','reference']:
        args=inputs()
        if key=='cleaning':args[1]['cleaning_disposition']='excluded_by_review'
        if key=='pool':args[0].update(pool_analysis_eligible=False,pool_analysis_exclusion_reasons=['effective_workers_below_3'])
        if key=='reference':args[3]['current_target']=False
        assert not usage_policy(*args,full_score_state='computed')['quality_usable']


def test_blanket_exemption_requires_real_doorway_source_stage():
    args=inputs();args[0]['stage']='ordinary'
    result=usage_policy(*args,full_score_state='computed')
    assert not result['target_binding_unique']
    assert 'legacy:same_target_unconfirmed' in result['quality_exclusion_reasons']
