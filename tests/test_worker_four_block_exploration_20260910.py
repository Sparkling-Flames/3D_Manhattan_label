import numpy as np
import pandas as pd
from tools.thesis_main.analysis.worker_four_block_exploration_20260910 import (
    cluster_blocks, scope_axis, classify_training, prepare_axis_cache, fit_axis_cache,
)
from tools.thesis_main.analysis import worker_reference_feasibility_20260909 as reference


def test_report_inventory_keeps_singletons_and_missing_people_visible():
    from tools.thesis_main.analysis.build_worker_four_block_report_20260910 import inventory_groups
    p=pd.DataFrame({'worker_id':[1,2,3,4,5,6], 'quality':[0,0,0,0,0,100],
                    'label':[0]*6, 'status':['singleton_rejected']*6})
    rows=inventory_groups(p,'Q',set(range(1,8)))
    assert sorted(r['n'] for r in rows)==[1,5]
    assert all(not r['accepted'] and r['missing_ids']==[7] for r in rows)
    assert set(sum([r['worker_ids'] for r in rows],[]))==set(range(1,7))
    p['quality']=[0,1,2,8,9,10];p['label']=[1,1,1,2,2,2];p['status']='usable'
    rows=inventory_groups(p,'Q',set(range(1,8)))
    assert [r['worker_ids'] for r in rows]==[[1,2,3],[4,5,6]]


def test_variable_group_count_recovers_three_groups_and_preserves_singletons():
    from tools.thesis_main.analysis.worker_group_count_exploration_20260910 import partitions
    p=pd.DataFrame({'quality':[0,.1,.2,10,10.1,10.2,20,20.1,20.2]})
    r=partitions(p,'Q',[2,3,4])
    assert np.array_equal(r[3],[1,1,1,2,2,2,3,3,3])
    assert len(set(r[4]))==4 and min(np.bincount(r[4])[1:])==1
    assert 10 not in partitions(p,'Q',[10])


def test_subtype_replay_constant_layout_and_singletons_are_distinct():
    from tools.thesis_main.analysis.worker_subtype_stages_20260910 import make_evaluator
    n=8;orders=[list(range(n)),list(reversed(range(n)))]
    ref=np.arange(n,dtype=float);dist=np.zeros((n,n))
    full=[((1<<n)-1)^(1<<i) for i in range(n)]
    evaluate=make_evaluator({'q95':full},{'q95':0},orders,ref,dist)
    rows,scores=evaluate(tuple(range(n)),(8,))
    assert len(rows)==2 and all(r['lower']==1 and r['stable_single']==2 for r in rows)
    assert [r['k'] for r in rows]==[2,3] and scores[8]==3.5
    evaluate=make_evaluator({'q95':[0]*n},{'q95':0},orders,ref,dist)
    rows,_=evaluate(tuple(range(n)),(8,))
    assert all(r['lower']==0 and r['upper']==1 and r['unknown']==2 for r in rows)


def test_random_overlap_accounts_for_group_size():
    from tools.thesis_main.analysis.worker_group_count_exploration_20260910 import expected_jaccard
    assert np.isclose(expected_jaccard(4,1,1),.25)
    assert expected_jaccard(4,4,4)==1
    assert expected_jaccard(4,0,2)==0


def test_named_subtype_follows_behavior_not_group_number():
    from tools.thesis_main.analysis.worker_group_count_exploration_20260910 import named_groups
    p=pd.DataFrame({'quality':[0,0,1,1,2,2],'time':[2,2,-3,-3,1,1]})
    assert named_groups(p,'QT',[1,1,2,2,3,3])['time_low']==2
    assert named_groups(p,'QT',[2,2,3,3,1,1])['time_low']==3
    p['time']=0
    assert named_groups(p,'QT',[1,1,2,2,3,3])['time_low'] is None


def test_scope_two_errors_and_missing_are_distinct():
    assert scope_axis('in_scope', 'oos') == ('scope_reject', 1.)
    assert scope_axis('oos', 'in_scope') == ('scope_accept', 1.)
    assert scope_axis('oos', 'oos') == ('scope_accept', 0.)
    assert scope_axis('unknown_gold', 'in_scope') == (None, None)
    assert scope_axis('in_scope', 'missing') == (None, None)


def test_blocks_equal_weight_and_units_do_not_change_classification():
    p = pd.DataFrame({'worker_id': list('abcdef'), 'quality': [0,1,2,8,9,10],
                      'scope_reject': [0,1,2,8,9,10], 'scope_accept': [0,1,2,8,9,10]})
    a, status = cluster_blocks(p, ('Q','S'))
    b, status2 = cluster_blocks(p.assign(quality=p.quality*1000), ('Q','S'))
    assert status == status2 == 'usable'
    assert np.array_equal(a, b)
    p['quality'] = [0,0,0,0,0,100]
    labels, status = cluster_blocks(p, ('Q',))
    assert status == 'singleton_rejected' and not labels.any()


def test_target_building_cannot_change_classification():
    rows = [dict(worker_id=w, context_key=f'{b}_{i}', image_id=f'{b}_{i}',
                 building_id=str(b), axis='quality', value=100*b+i+e)
            for b in range(5) for i in range(2)
            for w,e in [('1',0),('2',1),('3',2),('4',8),('5',9),('6',10)]]
    d = pd.DataFrame(rows)
    a = classify_training(d, {'0','1','2','3'}, ('Q',))
    d.loc[d.building_id == '4', 'value'] *= -1000
    b = classify_training(d, {'0','1','2','3'}, ('Q',))
    assert a.status.eq('usable').all()
    pd.testing.assert_frame_equal(a, b)
    cached=fit_axis_cache(prepare_axis_cache(d),{'0','1','2','3'})
    expected=reference.profiles(d[d.building_id!='4'])
    both=cached.merge(expected,on='worker_id')
    assert np.allclose(both.quality,both.effect,atol=1e-10)


def test_two_axis_block_has_same_total_weight_as_one_axis_block():
    # S的两个重复轴应相当于一个轴，不能因字段数多获得两倍权重。
    from scipy.cluster.hierarchy import linkage, cut_tree
    p=pd.DataFrame({'worker_id':list('abcdefgh'), 'quality':[0,0,1,1,2,2,3,3],
                    'scope_reject':[0,1,0,1,3,2,3,2], 'scope_accept':[0,1,0,1,3,2,3,2]})
    labels,status=cluster_blocks(p,('Q','S'))
    x=p[['quality','scope_reject']].to_numpy(float);x=(x-x.mean(0))/x.std(0)
    expected=cut_tree(linkage(x,method='ward'),n_clusters=2).ravel()
    assert status=='usable'
    assert np.array_equal(labels[:,None]==labels[None,:],expected[:,None]==expected[None,:])


def test_fast_replay_exactly_matches_existing_partition_and_changes():
    from tools.thesis_main.analysis.worker_four_block_exploration_20260910 import graph_partition_bits, compare_bits
    from tools.thesis_main.analysis.validate_worker_coarse_20260910 import hard_partition
    from tools.thesis_main.analysis.replay_multibuilding_stability_20260909 import changes
    rng=np.random.default_rng(5)
    for _ in range(35):
        n=8;x=rng.random((n,n));x=(x+x.T)/2;np.fill_diagonal(x,0)
        counts=rng.choice([8,10],n);valid=np.ones(n,bool)
        edges=(x<=.5+1e-12)&(counts[:,None]==counts[None,:]);np.fill_diagonal(edges,False)
        neighbors=[sum(1<<j for j in np.flatnonzero(row)) for row in edges]
        masks=[7,31,255];partitions=[]
        for mask in masks:
            idx=[i for i in range(n) if mask&(1<<i)]
            expected=hard_partition(x,counts,valid,idx,.5)
            result=graph_partition_bits(neighbors,mask,0)
            assert (result is not None)==(expected['status']=='unique')
            if result is not None:
                assert set(result)=={sum(1<<i for i in g) for g in expected['clusters']}
            partitions.append((expected,result))
        a,b=partitions[0],partitions[-1]
        expected=1
        if a[0]['status']=='unique' and b[0]['status']=='unique' and any(len(g)>=2 for g in a[0]['clusters']):
            v=changes(a[0]['clusters'],b[0]['clusters'])
            expected=2 if v['membership']>.1+1e-12 or v['shares']>.1+1e-12 or v['promotions'][1] else 0
        assert compare_bits(a[1],b[1])==expected
    assert graph_partition_bits([2,1],3,1) is None
