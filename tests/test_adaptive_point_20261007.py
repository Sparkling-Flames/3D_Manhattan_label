import copy

import numpy as np


def test_trace_distinguishes_vote_loss_from_identity_split():
    from tools.thesis_main.analysis.g184_followup_20261007 import trace_support
    def group(name, ids):
        return dict(feature_id=name,support=len(ids),members=[dict(id=str(i),pair_index=0) for i in ids])
    keys={(str(i),0) for i in range(6)}
    r=dict(minimum_support=9,identity_groups=[group('whole',range(6))])
    assert trace_support(keys,r)['stage']=='one_group_below_vote'
    r['identity_groups']=[group('a',range(3)),group('b',range(3,6))]
    assert trace_support(keys,r)['stage']=='split_before_vote'

from tools.thesis_main.analysis.point_route_panel_20261005 import build_routes


def records():
    return [dict(id=f'R{i}', worker=f'P{i}', points=[[x, y] for x in (128.,384.,640.,896.) for y in (120.,390.)],
                 source_pair_indices=list(range(4))) for i in range(3)]


def test_late_alignment_same_input_is_noop_and_does_not_mutate():
    rows=records(); before=copy.deepcopy(rows)
    normal=build_routes(rows,9)
    late=build_routes(rows,9,endpoint_points={r['id']:r['points'] for r in rows})
    for route in normal:
        assert normal[route]['candidate']['points']==late[route]['candidate']['points']
    assert rows==before


def test_early_vs_late_median_alignment_can_differ_with_same_members():
    rows=records(); raw={}
    for r,(tx,bx) in zip(rows,[(0,0),(0,12),(12,0)]):
        p=np.array(r['points']).reshape(-1,2,2)
        p[:,0,0]+=tx; p[:,1,0]+=bx
        raw[r['id']]=p.reshape(-1,2).tolist()
        p[:,:,0]=p[:,:,0].mean(axis=1)[:,None]
        r['points']=p.reshape(-1,2).tolist()
    early=build_routes(rows,9)['paired']
    late=build_routes(rows,9,endpoint_points=raw)['paired']
    assert [g['support'] for g in early['identity_groups']]==[3]*4
    assert [g['support'] for g in late['identity_groups']]==[3]*4
    np.testing.assert_allclose(np.array(early['candidate']['points'])[:,0]-np.array(late['candidate']['points'])[:,0],6)


def test_adaptive_retains_binding_for_conflicting_endpoint_targets():
    from tools.thesis_main.analysis.adaptive_point_20261007 import choose_components
    def group(fid, keys):
        return dict(feature_id=fid, support=len(keys), center=[[128.,120.],[128.,390.]],
                    members=[dict(id=str(k),pair_index=0,worker=str(k)) for k in keys])
    p=[group('p',[1,2])]; t=[group('t1',[1,2]),group('t2',[3,4])]; b=[group('b',[1,2,3,4])]
    selected,trace=choose_components(p,t,b)
    assert len(selected)==1 and selected[0]['local_mode']=='paired'
    assert trace[0]['choice']=='paired_fallback'
    assert trace[0]['top_n']==2


def test_adaptive_uses_unique_independent_incidence_without_inventing_joint_votes():
    from tools.thesis_main.analysis.adaptive_point_20261007 import choose_components
    def group(fid,keys):
        return dict(feature_id=fid,support=len(keys),center=[[1023.,120.],[1023.,390.]],
                    members=[dict(id=str(k),pair_index=0,worker=str(k)) for k in keys])
    selected,trace=choose_components([], [group('t',[1,2,3])], [group('b',[2,3,4])])
    g=selected[0]
    assert g['top_support']==g['bottom_support']==3 and g['joint_support']==2
    assert g['local_mode']=='split' and trace[0]['choice']=='independent_unique'
