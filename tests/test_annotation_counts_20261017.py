from tools.thesis_main.analysis.annotation_counts_20261017 import count_annotations


def test_excluded_pending_and_nonindependent_removed_but_one_person_and_held_image_counted():
    images=[dict(image_id='a',image_code='b-01',building_id='b'),dict(image_id='z',image_code='b-02',building_id='b')]
    objects=[];gates=[]
    for oid,image,worker,condition,cleaning,eligible in [
        ('1','a','w','manual','retained',True),('2','a','w','semi','retained',True),
        ('3','a','excluded','manual','historical_not_accepted',False),
        ('4','a','pending','manual','retained_pending',False),
        ('5','a','borrowed','manual','retained',False),('6','z','excluded','manual','excluded_by_review',False)]:
        objects.append(dict(object_id=oid,object_kind='annotation',cleaning_disposition=cleaning))
        gates.append(dict(object_id=oid,image_id=image,worker_id=worker,condition=condition,
            pool_vote_eligible=eligible,pool_analysis_eligible=False,pool_vote_exclusion_reasons=[] if eligible else ['held']))
    tables,checks=count_annotations(gates,objects,images)
    row=tables['image_counts'].set_index('image_id').loc['a']
    assert row.n_retained_workers==1 and row.n_retained_records==2
    assert row.n_manual_workers==1 and row.n_semi_workers==1 and row.n_manual_semi_workers==1
    assert tables['image_counts'].set_index('image_id').loc['z','n_retained_workers']==0
    assert checks['removal_groups']=={'user_excluded':2,'pending':1,'nonindependent_or_other_hold':1}


def test_gt_history_and_current_are_unioned_without_turning_uncertainty_or_detail_into_error():
    from tools.thesis_main.analysis.annotation_counts_20261017 import image_flags
    r=dict(gt_substantive_error_mark=True,gt_uncertainty_explicit_tag=False,gt_detail_omission_mark=False)
    d=dict(gt_error_excluded=False,difficulty_analysis_exclusion='')
    assert image_flags(r,d,[])['gt_error_union']
    r.update(gt_substantive_error_mark=False,gt_uncertainty_explicit_tag=True,gt_detail_omission_mark=True)
    flags=image_flags(r,d,['historical_quality:hold_all_analysis'])
    assert not flags['gt_error_union'] and flags['gt_uncertainty'] and flags['gt_detail_omission']
    assert flags['image_analysis_hold']
    d.update(gt_error_excluded=True,difficulty_analysis_exclusion='user_reported_issue_pending')
    assert image_flags(r,d,[])['current_issue_pending'] and image_flags(r,d,[])['gt_error_union']
    d['gt_error_excluded']=False
    flags=image_flags(r,d,[],dict(quality_reference_hold=True,reference_status='user_confirmed_inaccurate_pending_revision'))
    assert flags['gt_reference_problem'] and not flags['gt_error_union']
    flags=image_flags(r,d,[],dict(quality_reference_hold=False,reference_status='no_user_gt_error_claim'))
    assert not flags['gt_reference_problem']
    d['difficulty_analysis_exclusion']='special_or_pending'
    flags=image_flags(r,d,['current_user_review_pending'],current_review=dict(status='pending'))
    assert flags['current_issue_pending'] and flags['image_analysis_hold']
    assert not flags['gt_reference_problem']
