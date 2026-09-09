import math
from itertools import permutations
import numpy as np
import pytest

from tools.thesis_main.analysis.order_free_cluster_holdout_20260908 import (
    unit_points, point_distances, partition, fixed_distribution,
)
from tools.thesis_main.analysis.review_order_free_clusters_20260908 import coassignment_disagreement


def test_point_metric_ignores_all_order_and_wraps_panorama_seam():
    p=np.array([[0,100],[200,380],[400,130],[800,300]],float)
    q=p.copy();q[:,0]=(q[:,0]+2)%1024
    left=point_distances(unit_points(p),unit_points(q))
    right=point_distances(unit_points(p[[2,0,3,1]]),unit_points(q[::-1]))
    assert left==pytest.approx(right,abs=1e-10)
    assert point_distances(unit_points(p),unit_points(p[[0,2,1,3]]))['ospa30']==pytest.approx(0,abs=1e-10)
    assert point_distances(unit_points([[0,256]]),unit_points([[1024,256]]))['ospa30']==0
    assert point_distances(unit_points([[1,256]]),unit_points([[1023,256]]))['ospa30']==pytest.approx(360*2/1024)


def test_extra_duplicate_endpoint_is_preserved_as_count_disagreement():
    a=unit_points([[0,128],[512,384]])
    b=unit_points([[0,128],[512,384],[512,384]])
    d=point_distances(a,b)
    assert d['ospa30']==pytest.approx(10)
    assert d['ospa60']==pytest.approx(20)
    assert d['chamfer']==pytest.approx(0,abs=1e-10)
    with pytest.raises(ValueError,match='empty'):unit_points([])
    with pytest.raises(ValueError,match='coordinate'):unit_points([[1025,80]])
    assert unit_points([[10,20]]).shape==(1,3)  # Partial point data is not a valid-room assertion.


def test_capped_assignment_matches_exhaustive_unequal_size_matching():
    x=np.array([10.,40.,100.]);y=np.array([12.,45.,120.,210.])
    result=point_distances(unit_points(np.column_stack([x*1024/360,np.full(3,256)])),
                           unit_points(np.column_stack([y*1024/360,np.full(4,256)])))
    for cap in (30,60):
        costs=[sum(min(cap,abs(x[i]-y[j]),360-abs(x[i]-y[j])) for i,j in enumerate(match))+cap for match in permutations(range(4),3)]
        assert result['ospa'+str(cap)]==pytest.approx(min(costs)/4,abs=1e-10)


def test_non_unique_partition_is_not_forced_into_one_clustering():
    d=np.array([[0,1,5],[1,0,1],[5,1,0]],float)
    p=partition(d,2)
    assert p['status']=='non_unique' and p['clusters']==[]


def test_two_stable_clusters_have_positive_entropy_and_zero_distribution_gap():
    d=np.full((8,8),20.0);np.fill_diagonal(d,0)
    for group in ([0,1,2,6],[3,4,5,7]):d[np.ix_(group,group)]=0
    p=partition(d[:6,:6],3)
    assert p['status']=='unique' and len(p['clusters'])==2
    f=fixed_distribution(d,[0,1,2,3,4,5],[6,7],p['clusters'],3,[3,6])
    assert f[-1]['training_entropy']==pytest.approx(math.log(2))
    assert f[-1]['distribution_tv']==0 and f[-1]['validation_outside_fraction']==0
    changed=d.copy();changed[6,:6]=changed[:6,6]=30
    other=fixed_distribution(changed,[0,1,2,3,4,5],[6,7],p['clusters'],3,[3,6])
    assert other[-1]['validation_outside_fraction']==.5
    assert other[-1]['training_cluster_support_json']==f[-1]['training_cluster_support_json']


def test_validation_compatible_with_multiple_clusters_stays_ambiguous():
    d=np.array([[0,10,1],[10,0,1],[1,1,0]],float)
    r=fixed_distribution(d,[0,1],[2],[[0],[1]],3,[2])[0]
    assert r['validation_ambiguous_fraction']==1 and math.isnan(r['distribution_tv'])


def test_same_cluster_count_does_not_imply_same_membership():
    a=[['a','b'],['c','d']]
    assert coassignment_disagreement(a,[['d','c'],['b','a']],list('abcd'))==0
    assert coassignment_disagreement(a,[['a','c'],['b','d']],list('abcd'))==pytest.approx(4/6)
