import copy
import pytest
from tools.thesis_main.analysis.consensus_delivery_20261008 import apply_partition, apply_followup, apply_sorting_policy, relation_error


def test_delivery_uses_frozen_gap_without_rewriting_calibration(tmp_path,monkeypatch):
    import json
    from tools.thesis_main.analysis import consensus_delivery_20261008 as module
    from tools.thesis_main.analysis.ring_correspondence_20261007 import build
    from tools.thesis_main.analysis.research_artifact_io import write_json
    population=tmp_path/'population';population.mkdir()
    rows=[dict(id=str(i),worker=str(i),points=[[x,y] for x in [128,384,640,896] for y in [120,390]]) for i in range(3)]
    for path,data in [(population/'inputs.json',{'images':[dict(image='example',image_id='example',records=rows)]}),
                      (population/'failures.json',[]),(tmp_path/'user_followup.json',{'records':[]}),
                      (tmp_path/'selection.json',{'gap':7.5,'historical':True})]:
        write_json(path,data)
    saved=(tmp_path/'selection.json').read_bytes();seen=[]
    monkeypatch.setattr(module,'OUT',tmp_path);monkeypatch.setattr(module,'POP',population)
    monkeypatch.setattr(module,'FINE',[8.0])
    monkeypatch.setattr(module,'cases',lambda:([],[]))
    monkeypatch.setattr(module,'gallery',lambda inputs:None)
    def get_state(im,gap):
        seen.append(gap)
        return build(im['records'],gap=gap)
    monkeypatch.setattr(module,'get_state',get_state)
    module.run()
    assert seen==[module.WORKING_GAP]
    assert (tmp_path/'selection.json').read_bytes()==saved
    assert json.loads((tmp_path/'outputs.json').read_text(encoding='utf-8'))[0]['gap']==7.5


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


def test_reviewed_order_preserves_nodes_and_rejects_stale_coordinates():
    r=state();r['n']=4
    for g,x in zip(r['identity_groups'],[800,100,450]):
        g.update(selected=True,center=[[x,120],[x,390]])
    r,_=apply_followup(r,dict(order_policy='x_ascending'))
    nodes=copy.deepcopy(r['node_consensus'])
    feedback=dict(manual_order=['0','1','2'],order_binding=[dict(feature_id=n['feature_id'],points=n['points']) for n in nodes['nodes']])
    actual,applied=apply_followup(r,feedback)
    assert actual['node_consensus']==nodes and actual['candidate']['feature_ids']==['0','1','2']
    assert applied==['user_workbench_order']
    feedback['order_binding']=copy.deepcopy(feedback['order_binding'])
    feedback['order_binding'][0]['points'][0][0]+=1
    actual,applied=apply_followup(r,feedback)
    assert not applied and actual['candidate']['review_status']=='needs_order_reconfirmation'


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


def test_individual_review_binds_each_observation_and_keeps_uploaded_review():
    import json
    import re
    from tools.thesis_main.analysis.build_fusion_order_workbench_20261008 import OUT
    data=json.loads(re.search(r'<script id="data" type="application/json">(.*?)</script>',
        (OUT/'individual_review.html').read_text(encoding='utf-8'),re.S).group(1))
    image=data['image']
    assert data['schema']=='wall_identity_individual_20261008_v2'
    assert data['target_classes']['C']=='玻璃与墙相交处'
    assert data['gt_reference']['source'].endswith('.txt')
    expected={m for g in image['states']['7.5'] for m in g['members']}
    assert data['observations']==[image['observations'][m] for m in sorted(expected)]
    assert len({(o['id'],o['pair_index']) for o in data['observations']})==20
    assert [(o['id'],o['pair_index']) for o in data['references']]==[('R01557',4),('R01557',2)]
    assert data['previous_review']==json.loads((OUT/'user_residual_review_20261008.json').read_text(encoding='utf-8'))


def test_completed_residual_partitions_keep_sources_and_full_pool_vote():
    import json
    from tools.thesis_main.analysis.consensus_delivery_20261008 import OUT
    for code,prefix,supports in [('rPc6DW4iMge-06','review_rpc_individual_targets_ABC',[2,18]),
                               ('uNb9QFRL6hY-08','review_unb08_leftmost_to_g02',[2,21]),
                               ('UwV83HsGsw3-09','review_uw09_two_same_wall_pairs',[3,3])]:
        result=json.loads((OUT/(code+'.json')).read_text(encoding='utf-8'))
        before=result['automatic'];after=result['assisted']
        keys=lambda state: sorted((m['id'],m['pair_index']) for g in state['identity_groups'] for m in g['members'])
        assert keys(before)==keys(after) and before['n']==after['n']
        groups=[g for g in after['identity_groups'] if g['feature_id'].startswith(prefix)]
        assert sorted(g['support'] for g in groups)==supports
        assert all(g['selected']==(2*g['support']>=after['n']) for g in groups)
        assert result['remaining_review_cases']==[]
