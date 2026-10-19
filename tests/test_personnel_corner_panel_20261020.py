import numpy as np
from tools.thesis_main.analysis.personnel_corner_panel_20261020 import compare


def team(points, complete=True):
    return {'complete_evaluable':complete,'geometry':{'points':points}}


def test_circular_start_is_not_displacement():
    a=np.array([[100,180],[100,340],[370,180],[370,340],[680,180],[680,340],[900,180],[900,340]],float)
    b=np.roll(a.reshape(4,2,2),1,axis=0).reshape(-1,2)
    result,points=compare(team(a),team(b))
    assert result['status']=='unique_cyclic_candidate'
    assert result['shift']==1 and result['bev_max_h']==0 and result['top_max_h']==0
    assert len(points)==4


def test_incomplete_and_unequal_counts_are_not_zero_distance():
    a=[[100,180],[100,340],[370,180],[370,340],[680,180],[680,340],[900,180],[900,340]]
    result,_=compare(team(a),team(a[:-2]))
    assert result['status']=='different_corner_count' and 'bev_max_h' not in result
    result,_=compare(team(a),team(a,False))
    assert result['status']=='incomplete_geometry' and 'bev_max_h' not in result


def test_reversed_pairs_preserve_geometry():
    a=np.array([[100,180],[100,340],[370,180],[370,340],[680,180],[680,340],[900,180],[900,340]],float)
    b=a.reshape(4,2,2)[::-1].reshape(-1,2)
    result,_=compare(team(a),team(b))
    assert result['ring_reversed'] and result['bev_max_h']==0 and result['top_max_h']==0
    assert result['legacy_angle_deg']>20 and result['angle_deg']<1e-6
