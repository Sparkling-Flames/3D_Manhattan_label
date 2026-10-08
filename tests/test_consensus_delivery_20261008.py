import copy
import pytest
from tools.thesis_main.analysis.consensus_delivery_20261008 import apply_partition, apply_followup, apply_sorting_policy, relation_error


def state():
    members=[dict(id=str(i),worker=str(i),pair_index=0,points=[[100+i,120],[100+i,390]]) for i in range(6)]
    return dict(n=6,identity_groups=[dict(feature_id=str(j),members=ms,selected=False,support=len(ms),center=None)
        for j,ms in enumerate([members[:2],members[2:4],members[4:]])],
        assignments=[dict(id=m['id'],worker=m['worker'],feature_ids=[str(i//2)]) for i,m in enumerate(members)])


def test_review_merge_preserves_voters_and_revotes_without_gt():
    r=state();before=copy.deepcopy(r)
    c=dict(case='same',kind='partition',groups=[[['0',0],['1',0],['2',0],['3',0]]])
    fixed=apply_partition(r,c)
    assert r==before and fixed['n']==6
    assert sorted(g['support'] for g in fixed['identity_groups'])==[2,4]
    assert [n['support'] for n in fixed['node_consensus']['nodes']]==[4]
    assert len({(m['id'],m['pair_index']) for g in fixed['identity_groups'] for m in g['members']})==6
    assert relation_error(fixed,c)==(False,False)
    # Partial groups require a stated handling policy, not guessed memberships.
    with pytest.raises(ValueError,match='partial'):
        apply_partition(r,dict(case='partial',groups=[[['0',0],['2',0]]]))


def test_mixed_is_not_all_pairs_different_and_duplicate_person_is_not_two_votes():
    r=state();c=dict(kind='mixed',groups=[[['0',0],['1',0],['2',0]]])
    assert relation_error(r,c)==(False,False)
    c['groups']=[[['0',0],['1',0]]]
    assert relation_error(r,c)==(False,True)
    r['identity_groups'][1]['members'][0]['worker']='0'
    with pytest.raises(ValueError,match='same_person'):
        apply_partition(r,dict(case='dup',groups=[[['0',0],['1',0],['2',0],['3',0]]]))


def test_explicit_x_order_keeps_votes_positions_and_automatic_state():
    r=state();r['n']=4
    for g,x in zip(r['identity_groups'],[800,100,450]):
        g.update(selected=True,center=[[x,120],[x,390]])
    before=copy.deepcopy(r)
    ordered,applied=apply_followup(r,dict(order_policy='x_ascending'))
    assert r==before and ordered['identity_groups']==r['identity_groups']
    assert ordered['candidate']['feature_ids']==['1','2','0']
    assert ordered['candidate']['ring_confirmed'] is True
    assert applied==['user_order_x_ascending']


def test_two_person_sorting_is_deferred_without_removing_nodes():
    r=dict(n=2,node_consensus={'nodes':[{'support':1},{'support':2}]},
           candidate={'points':[[1,2]],'feature_ids':['a']},ring_diagnostics={'feature_ids':['a']})
    before=copy.deepcopy(r);actual=apply_sorting_policy(r)
    assert r==before and actual['node_consensus']==r['node_consensus']
    assert actual['candidate']['points'] is None
    assert actual['candidate']['order_status']=='two_person_sorting_deferred'
    r['n']=3
    assert apply_sorting_policy(r)==r


def test_workbench_order_preserves_fixed_node_identity_and_votes():
    from tools.thesis_main.analysis.build_fusion_order_workbench_20261008 import fusion_source
    nodes=[dict(feature_id=f,points=[[x,100],[x,400]],support=s)
           for f,x,s in [('a',100,3),('b',200,4),('c',300,5)]]
    result=dict(n=5,image_id='image',node_consensus={'nodes':nodes},
                candidate={'feature_ids':['c','a','b']})
    source=fusion_source('example',result)
    assert source['default_preview_order']==[2,0,1]
    assert source['feature_ids']==['a','b','c'] and source['node_supports']==[3,4,5]
    assert source['points']==[p for node in nodes for p in node['points']]
    assert source['ring_confirmed'] is False
