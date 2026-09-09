import numpy as np
import pytest
from tools.thesis_main.analysis.audit_point_count_novelty_20260909 import finite_pool_novelty, count_gated_partition
from tools.thesis_main.analysis.geometry_consensus.pairwise import cyclic_order_correspondence


def test_count_discovery_exact_finite_pool_and_singletons():
    assert finite_pool_novelty([23],20)==dict(any_unseen_probability=0.,expected_unseen_types=0.)
    r=finite_pool_novelty([23,1,1],20)
    assert r['any_unseen_probability']==pytest.approx(1-(20*19)/(25*24))
    assert r['expected_unseen_types']==pytest.approx(.4)
    assert finite_pool_novelty([6,4],10)['any_unseen_probability']==0
    with pytest.raises(ValueError):finite_pool_novelty([5],6)


def test_different_point_counts_cannot_merge_even_with_zero_distance():
    r=count_gated_partition(np.zeros((3,3)),[8,10,8],12)
    assert r['status']=='unique'
    assert sorted(sorted(g) for g in r['clusters'])==[[0,2],[1]]


def test_v5_actual_correspondence_rejects_different_event_counts():
    a=dict(width=1024,x_event_positions=[100,400,700])
    b=dict(width=1024,x_event_positions=[100,300,500,700])
    r=cyclic_order_correspondence(a,b)
    assert not r['compatible'] and r['reason']=='not_evaluable_variable_count_contract_unfrozen'
