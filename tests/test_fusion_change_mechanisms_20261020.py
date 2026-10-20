from tools.thesis_main.analysis.fusion_change_mechanisms_20261020 import partition_changed, step_mechanisms, restore_reviewed_identity


def group(workers, selected=True):
    return dict(feature_id='node_' + ''.join(workers), support=len(workers), selected=selected,
                members=[dict(worker=w, source_pair_index=0) for w in workers])


def test_threshold_rise_can_remove_an_unchanged_group():
    a = dict(n=6, minimum_support=3, identity_groups=[group(['a', 'b', 'c'])])
    b = dict(n=7, minimum_support=4, identity_groups=[group(['a', 'b', 'c'], False), group(['d'], False)])
    r = step_mechanisms(a, b, {'a', 'b', 'c'})
    assert r['threshold_only_losses'] == 1
    assert not r['retained_partition_changed']


def test_new_member_can_split_old_observations_even_without_a_node_count_change():
    assert partition_changed([group(['a', 'b', 'c'])], [group(['a', 'b']), group(['c', 'd'])], {'a', 'b', 'c'})
    assert not partition_changed([group(['a', 'b'])], [group(['a', 'b', 'd'])], {'a', 'b'})


def test_local_review_moves_only_requested_observations_and_keeps_denominator():
    groups=[group(['a','c'],False),group(['b'],False)]
    for g in groups:
        for m in g['members']:
            m.update(id=m['worker'],pair_index=0,points=[[100,100],[100,400]])
    state=dict(n=4,minimum_support=2,identity_groups=groups,assignments=[dict(id=m['id'],worker=m['worker'],feature_ids=[g['feature_id']]) for g in groups for m in g['members']])
    result=restore_reviewed_identity(state,{('a',0),('b',0)})
    assert result['n']==4 and result['minimum_support']==2
    target=next(g for g in result['identity_groups'] if g['feature_id']=='reviewed_target')
    assert target['support']==2 and target['selected']
    assert sum(g['support'] for g in result['identity_groups'])==3
    assert next(g for g in result['identity_groups'] if g['feature_id']!='reviewed_target')['members'][0]['worker']=='c'
