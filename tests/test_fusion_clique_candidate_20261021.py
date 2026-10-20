from tools.thesis_main.analysis.fusion_mechanism_followup_20261021 import support_first_partition, rescue_candidate, initialization_flag


def test_larger_compatible_identity_wins_over_close_incompatible_fragments():
    edges={(0,1),(0,2),(1,2),(2,3)}
    groups,_=support_first_partition(4,edges,lambda c:0)
    assert groups==[(0,1,2),(3,)]


def test_chain_does_not_merge_unmatched_neighbors():
    edges={(0,1),(1,2)}
    groups,_=support_first_partition(3,edges,lambda c:0)
    assert sorted(map(len,groups))==[1,2]
    assert all(not ({0,2}<=set(g)) for g in groups)


def test_exact_ties_use_canonical_ids_not_entering_order():
    edges={(0,1),(2,3)}
    groups,_=support_first_partition(4,edges,lambda c:0)
    assert groups==[(0,1),(2,3)]


def test_rescue_does_not_reassign_or_move_already_selected_neighbors():
    groups=[];assignments=[]
    for i,workers in enumerate([['a','b'],['c','d']]):
        ms=[dict(id=w,worker=w,pair_index=0,source_pair_index=0,points=[[100+i,100],[100+i,400]]) for w in workers]
        groups.append(dict(feature_id=str(i),members=ms,support=2,selected=True,center=ms[0]['points']))
        assignments.extend(dict(id=w,worker=w,feature_ids=[str(i)]) for w in workers)
    baseline=dict(n=4,minimum_support=2,identity_groups=groups,assignments=assignments,pairwise=[])
    result=rescue_candidate(baseline)
    assert result['identity_groups']==groups
    assert result['assignments']==assignments


def test_reported_unchanged_is_not_promoted_to_verified_initialization():
    r=dict(condition='semi',object_id='new',worker_id='W',image_code='image',pool_analysis_eligible=True,
           quality_usable=True,is_oos=False,is_doorway=False,
           semi_evidence=dict(known_error_unchanged=None,reported_known_error_unchanged=True,edited=False,
                              exact_initialization_bound=False))
    assert initialization_flag(r)['evidence']=='reported_only'
    assert initialization_flag(r)['current_final_matches_historical'] is None
    r['semi_evidence'].update(known_error_unchanged=True,reported_known_error_unchanged=None,
         exact_initialization_bound=True,initialization_points=[[470.19199999999995,180.2288]],
         raw_final_points=[[470.192,180.2288]],correction_evidence={'initialization_error_type':'corner_duplicate'})
    assert initialization_flag(r)['evidence']=='confirmed_unchanged'
