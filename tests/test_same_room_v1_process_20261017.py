import pandas as pd
import pytest

from tools.thesis_main.analysis.same_room_v1_process_20261017 import (
    balanced_gap, member_exclusion, replay_orders, select_panel,
)


def test_buildings_and_groups_are_equal_weighted_instead_of_pair_count():
    rows=[dict(building='A',user_group_ids='g1',absolute_mean_gap=10.)]
    rows += [dict(building='A',user_group_ids='g2',absolute_mean_gap=20.)]*10
    rows += [dict(building='B',user_group_ids='g3',absolute_mean_gap=0.)]
    result=balanced_gap(pd.DataFrame(rows))
    assert result['building_group_equal_gap']==7.5
    assert result['pair_equal_gap'] != result['building_group_equal_gap']


def test_panel_spreads_buildings_then_rooms_and_ignores_quality_values():
    rows=[dict(request_id='a',building='A',user_group_ids='g1',code_a='1',code_b='2',
               n_common_process=9,reference_quality_primary_eligible=True),
          dict(request_id='b',building='A',user_group_ids='g2',code_a='3',code_b='4',
               n_common_process=8,reference_quality_primary_eligible=True),
          dict(request_id='c',building='B',user_group_ids='g3',code_a='5',code_b='6',
               n_common_process=4,reference_quality_primary_eligible=True)]
    selected=select_panel(rows)
    assert [(r['request_id'],r['priority_wave']) for r in selected]==[('a',1),('c',1),('b',2)]
    for i,r in enumerate(rows): r['B8L2']=(-1)**i*10000
    assert [(r['request_id'],r['priority_wave']) for r in select_panel(rows)]==[('a',1),('c',1),('b',2)]


def test_real_replay_keeps_k1_k2_and_repeated_order_sampling_frequency():
    plans=replay_orders(['b','a'],repeats=4,seed=7)
    assert len(plans)==4 and len({tuple(p) for p in plans})<=2
    assert all(sorted(p)==['a','b'] for p in plans)
    assert [len(p[:k]) for k in range(1,3) for p in plans]==[1]*4+[2]*4
    with pytest.raises(ValueError,match='duplicate'):
        replay_orders(['a','a'],repeats=4,seed=7)


def test_source_pool_keeps_scope_mixture_but_preserves_existing_holdout():
    row=dict(pool_analysis_eligible=True,quality_usable=False,B8L2=None)
    gate=dict(original_holdout=False,role='manual_development_candidate',personnel_barriers=[],context_barriers=[])
    obj=dict(points_1024x512=[[1,2],[1,3]]*3)
    assert member_exclusion(row,gate,obj)==[]
    assert 'original_holdout' in member_exclusion(row,dict(gate,original_holdout=True),obj)
