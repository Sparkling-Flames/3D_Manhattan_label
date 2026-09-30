import pytest
from tools.thesis_main.analysis.audit_x_pairing_20260929 import x_adjacent,pairset,OUT,read


def test_periodic_x_and_roles_below_horizon_with_partial_locks():
    points=[[244.37,256.7],[270.2,257.25],[243.82,317.15],[266.35,316.6],[732.73,195.92],[799.32,197.1],[797.79,355.09],[732.39,353.91]]
    expected=[[0,2],[1,3],[4,7],[5,6]]
    assert pairset(x_adjacent(points)['pairs'])==pairset(expected)
    assert pairset(x_adjacent(points,[[4,7],[5,6]])['pairs'])==pairset(expected)
    assert pairset(x_adjacent([[1023,100],[1,400],[500,100],[502,400]])['pairs'])=={(0,1),(2,3)}
    assert x_adjacent(points[:-1])['status']=='odd_remaining_points'
    with pytest.raises(ValueError):x_adjacent(points,[[0,2],[0,3]])
    summary=read(OUT/'summary.json')
    assert summary['raw_verified']==summary['annotations']==3152
    assert summary['comparisons']=={'same_pairs':2986,'previously_unavailable_x_candidate':118,'unavailable_both':48}
    assert summary['affected_confirmed_orders']==0
    assert summary['accepted_return_status']=={'deferred':3,'checked':31}
    assert summary['returned_detail_states']=={'point_edit_pending':3,'manual_vs_x_difference':13,'user_oos_uncalculable':5,'horizon_role_limit':6,'user_oos_pairing_ok':1,'x_completion_required':6}
    assert x_adjacent(points,expected)['same_horizon_side_pairs']==[[0,2],[1,3]]
