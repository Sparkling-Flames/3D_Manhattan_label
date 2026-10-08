import numpy as np

from tools.thesis_main.analysis.ring_correspondence_20261007 import cyclic_match, source_ring


def test_cyclic_matching_allows_omission_and_reversed_start():
    cost=np.full((5,4),80.)
    expected={(0,2),(1,1),(3,0),(4,3)}
    for a,b in expected:cost[a,b]=0
    result=cyclic_match(cost,13.5)
    assert set(map(tuple,result['matches']))==expected
    assert result['cost']==13.5
    assert len({b for _,b in result['matches']})==4


def test_order_cannot_be_replaced_by_nearest_unordered_permutation():
    cost=np.full((4,4),80.)
    for a,b in enumerate([0,2,1,3]):cost[a,b]=0
    result=cyclic_match(cost,13.5)
    assert len(result['matches'])<4


def test_source_ring_retains_non_x_order_and_distinguishes_projected_edges():
    groups=[dict(feature_id=i,center=[[x,120],[x,390]])
            for i,x in zip('ABCD',[690.95,806.28,740.66,794.35])]
    assignments=[dict(worker='p',id='r',feature_ids=list('ABXCD'))]
    result=source_ring(groups,assignments)
    assert result['feature_ids']==list('ABCD')
    edge=next(e for e in result['edges'] if set(e['feature_ids'])==set('BC'))
    assert edge['direct_support']==0 and edge['projected_support']==1
    assert result['ring_confirmed'] is False
    assert source_ring(groups,[dict(worker='p',id='r',feature_ids=list('ABC'))])['feature_ids']==[]


def test_identity_vote_keeps_full_pool_and_source_coordinates():
    import copy
    from tools.thesis_main.analysis.ring_correspondence_20261007 import build
    rows=[dict(id=str(i),worker=str(i),points=[[x,y] for x in ([128,384,640,896] if i<2 else [128,640,896]) for y in [120,390]]) for i in range(3)]
    before=copy.deepcopy(rows)
    result=build(rows)
    assert rows==before
    assert result['n']==3 and result['minimum_support']==2
    assert sorted(g['support'] for g in result['identity_groups'])==[2,3,3,3]
    assert all(g['selected'] for g in result['identity_groups'])
    assert len(result['candidate']['points'])==8
    assert all(len({m['worker'] for m in g['members']})==g['support'] for g in result['identity_groups'])
    assert result['ring_diagnostics']['alternatives'][0]['support']==2


def test_build_gap_changes_matching_not_vote_policy_or_sources():
    import copy
    from tools.thesis_main.analysis.ring_correspondence_20261007 import build
    rows=[dict(id=str(i),worker=str(i),points=[[x,y]
          for x in [128+100*i,384,640,896] for y in [120,390]]) for i in range(2)]
    before=copy.deepcopy(rows)
    small=build(rows,gap=9)
    large=build(rows,gap=18)
    assert sorted(g['support'] for g in small['identity_groups'])==[1,1,2,2,2]
    assert [g['support'] for g in large['identity_groups']]==[2,2,2,2]
    assert rows==before
    assert build(rows)==build(rows,gap=13.5)
    for result in (small,large):
        assert result['n']==2 and result['minimum_support']==1
        assert all(g['selected'] for g in result['identity_groups'])


def test_gap_review_scores_only_explicit_relations_not_unreviewed_members():
    from tools.thesis_main.analysis.correspondence_gap_20261007 import evaluate
    groups=[dict(feature_id=f,support=len(ids),selected=True,center=None,
                 members=[dict(id=i,pair_index=0) for i in ids])
            for f,ids in [('A',['one','unknown']),('B',['two','three'])]]
    case=dict(case='local',image='image',status='confirmed_local',
              groups=[[['one',0],['two',0]],[['three',0]]])
    r=evaluate(dict(identity_groups=groups),case)
    assert (r['same_pairs'],r['split_pairs'],r['different_pairs'],r['merged_pairs'])==(1,1,2,1)
    assert r['reviewed_members']==3
    assert next(g for g in r['groups'] if g['feature_id']=='A')['unreviewed_members']==[('unknown',0)]


def test_fine_selection_does_not_treat_provisional_targets_as_hard_errors():
    from tools.thesis_main.analysis.correspondence_gap_20261007 import local_failure_counts
    rows=[dict(review_status=s,split_pairs=a,merged_pairs=b) for s,a,b in [
        ('confirmed_local',2,0),('confirmed_local',0,56),('confirmed_local',0,0),
        ('provisional',10,20),('user_A_interpretation',4,0)]]
    assert local_failure_counts(rows)==dict(failed_confirmed_cases=2,split_confirmed_cases=1,merged_confirmed_cases=1)


def test_same_identity_does_not_erase_endpoint_position_modes():
    from tools.thesis_main.analysis.ring_correspondence_20261007 import build
    rows=[dict(id=str(i),worker=str(i),points=[[x,y] for x in [145,364,651,878] for y in [113 if i<2 else 147,413]]) for i in range(3)]
    result=build(rows)
    for g in result['identity_groups']:
        assert g['support']==3
        assert sorted(s['support'] for s in g['top_position_groups_9deg'])==[1,2]
        assert [s['support'] for s in g['bottom_position_groups_9deg']]==[3]


def test_retained_nodes_survive_missing_complete_source_ring_and_manual_order():
    from tools.thesis_main.analysis.ring_correspondence_20261007 import assemble_fusion
    groups=[dict(feature_id=f,support=6 if f in 'ABC' else 3,selected=True,
                 center=[[x,120],[x,390]],members=[])
            for f,x in zip('ABCDE',[128,384,640,720,760])]
    sources=[dict(worker=str(i),id=str(i),feature_ids=list('ABCD' if i<3 else 'ABCE')) for i in range(6)]
    r=assemble_fusion(groups,sources)
    assert r['node_consensus']['status']=='ready'
    assert len(r['node_consensus']['nodes'])==5
    assert r['candidate']['points'] is None
    assert r['candidate']['order_status']=='needs_manual_order'
    manual=assemble_fusion(groups,sources,list('ABCDE'))
    assert len(manual['candidate']['points'])==10
    assert manual['candidate']['order_status']=='human_provided'
    assert manual['node_consensus']==r['node_consensus']
    import pytest
    with pytest.raises(ValueError,match='exactly_once'):
        assemble_fusion(groups,sources,list('ABCD'))
    import copy
    incompatible=copy.deepcopy(groups);incompatible[-1]['center'][0][1]=260
    bad=assemble_fusion(incompatible,sources,list('ABCDE'))
    assert bad['node_consensus']['status']=='ready'
    assert len(bad['node_consensus']['nodes'])==5
    assert bad['candidate']['geometry_status']!='ok'


def test_two_cloud_diagnostic_preserves_all_people_without_deciding_identity():
    from tools.thesis_main.analysis.direct_fusion_20261007 import separation_diagnostic
    members=[dict(id=str(i),worker=str(i),pair_index=0,points=[[x,t],[x,b]])
             for i,(x,t,b) in enumerate([(100,100,400)]*3+[(105,140,370)]*3)]
    r=separation_diagnostic(members)
    assert sorted(map(len,r['subgroups']))==[3,3]
    assert r['within_connectivity_deg']==0
    assert r['bridge_deg']>0
    assert r['decision']=='diagnostic_only_no_automatic_split'


def test_human_identity_split_revotes_full_pool_without_dropping_sources():
    import copy
    from tools.thesis_main.analysis.direct_fusion_20261007 import human_split
    members=[dict(id=str(i),worker=str(i),pair_index=0,points=[[100,120],[100,390]]) for i in range(15)]
    artifact=dict(image='example',correspondence=dict(n=15,
        identity_groups=[dict(feature_id='merged',members=members,support=15,selected=True)],
        assignments=[dict(id=m['id'],worker=m['worker'],feature_ids=['merged']) for m in members]))
    before=copy.deepcopy(artifact)
    review=dict(feature_id='merged',review_source='human',groups=[
        dict(identity='rear',members=members[:7]),dict(identity='front',members=members[7:])])
    result=human_split(artifact,review)
    assert artifact==before
    assert [(g['support'],g['selected']) for g in result['identity_groups']]==[(7,False),(8,True)]
    assert len(result['node_consensus']['nodes'])==1
    assert sum(len(g['members']) for g in result['identity_groups'])==15


def test_adjacent_cohorts_need_matching_people_and_real_source_adjacency():
    from tools.thesis_main.analysis.direct_fusion_20261007 import adjacent_cohort_signals
    import copy
    groups=[]
    for fid,x in [('left',100),('right',200)]:
        groups.append(dict(feature_id=fid,selected=True,support=6,members=[
            dict(id=str(i),worker=str(i),pair_index=0 if fid=='left' else 1,
                 points=[[x,100 if i<3 else 150],[x,400 if i<3 else 350]]) for i in range(6)]))
    rows=[dict(id=str(i),worker=str(i),feature_ids=['left','right','other']) for i in range(6)]
    before=copy.deepcopy(groups)
    signals=adjacent_cohort_signals(groups,rows)
    assert len(signals)==1 and signals[0]['direct_neighbor_people']==6
    assert sorted(map(len,signals[0]['common_cohorts']))==[3,3]
    assert groups==before
    # The same two spatial clouds with different people do not imply a shared local choice.
    groups[1]['members'][2]['points'],groups[1]['members'][3]['points']=groups[1]['members'][3]['points'],groups[1]['members'][2]['points']
    assert adjacent_cohort_signals(groups,rows)==[]
    rows=[dict(id=str(i),worker=str(i),feature_ids=['left','other1','right','other2']) for i in range(6)]
    assert adjacent_cohort_signals(before,rows)==[]


def test_population_comparison_uses_members_not_node_labels_or_point_count():
    from tools.thesis_main.analysis.population_gap_20261007 import compare_states
    def state(groups):
        return dict(identity_groups=[dict(feature_id=str(i),members=[dict(id=m,pair_index=0) for m in ms],
            selected=True,center=[[1,2],[1,3]]) for i,ms in enumerate(groups)])
    a=state([['a','b'],['c']]);b=state([['c'],['a','b']])
    assert compare_states(a,b)['changed_observations']==0
    assert compare_states(a,b)['selected_centers_equal']
    c=state([['a'],['b','c']]);r=compare_states(a,c)
    assert r['changed_observations']==3
    assert not r['selected_memberships_equal']
    assert not r['selected_centers_equal']
