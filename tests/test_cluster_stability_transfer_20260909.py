import math
import numpy as np
import pytest
from tools.thesis_main.analysis.cluster_stability_transfer_20260909 import partition_change, envelope, stable_state


def part(groups,status='unique'):
    return dict(status=status,clusters=groups)


def test_one_cluster_can_stabilize_before_five_people():
    trajectory={k:part([list(range(k))]) for k in range(1,9)}
    e=envelope(trajectory,1,8)
    assert e['status']=='evaluated' and stable_state(e,.05)=='stable'


def test_two_persistent_clusters_can_be_stable_with_positive_disagreement():
    trajectory={k:part([list(range(0,k,2)),list(range(1,k,2))]) for k in range(2,11)}
    e=envelope(trajectory,2,10)
    assert e['max_membership_change']==0
    assert e['max_share_change']==pytest.approx(1/6)
    assert stable_state(e,.2)=='stable' and stable_state(e,.1)=='changing'


def test_same_number_of_clusters_can_hide_membership_change():
    r=partition_change([[0,1],[2,3]],[[0,2,4],[1,3]],4,5)
    assert r['membership_change']==pytest.approx(4/6)


def test_late_supported_cluster_is_not_called_stable():
    trajectory={k:part([list(range(min(k,4)))]+([list(range(4,k))] if k>4 else [])) for k in range(1,9)}
    e=envelope(trajectory,4,8)
    assert e['max_new_supported_clusters']==1
    assert stable_state(e,1)=='changing'


def test_nonunique_remains_unknown_and_no_terminal_self_convergence():
    trajectory={k:part([list(range(k))]) for k in range(1,9)}
    trajectory[7]=part([],'non_unique')
    e=envelope(trajectory,2,8)
    assert e['status']=='unresolved' and stable_state(e,.2)=='unknown'
    with pytest.raises(ValueError):envelope(trajectory,7,8)


def test_partition_change_ignores_cluster_labels():
    a=[[0,2],[1,3]];b=[[1,3,5],[0,2,4]]
    r=partition_change(a,b,4,6)
    assert r==dict(membership_change=0.,share_change=0.,new_supported_clusters=0)
