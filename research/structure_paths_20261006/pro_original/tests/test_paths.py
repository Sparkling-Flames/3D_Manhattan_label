import sys,json,copy
from pathlib import Path
import numpy as np
import pytest
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'src'))
from frechet import *
from baseline import nodes_from_records,distances,partition,key
from structure import PathBank,report_groups,ring_diagnostics
from controls import path_from_floor,record
from analysis import assisted_partition

@pytest.mark.parametrize('insert',[.1,.2,.5,.9])
def test_continuous_collinear_subdivision_not_discrete_vertex_distance(insert):
    p=np.array([[0.,0],[1.,0]]);q=np.array([[0.,0],[insert,0],[1.,0]])
    lo,hi=euclidean_distance(p,q);assert hi<1e-9
    assert discrete_distance(p,q)>.05

def test_short_bump_analytic_distance():
    p=np.array([[0.,0],[1.,0]]);q=np.array([[0.,0],[.5,.3],[1.,0]])
    lo,hi=euclidean_distance(p,q);assert lo<=.3+1e-8<=hi+1e-8
    assert not continuous_decide(p,q,.2999)

def test_traversal_order_is_not_hausdorff_point_set():
    p=np.array([[-1.,0],[1.,0],[-1.,0],[1.,0]]);q=np.array([[-1.,0],[1.,0]])
    lo,hi=euclidean_distance(p,q);assert abs((lo+hi)/2-1)<1e-7

def test_zero_length_segments():
    p=np.array([[0.,0],[0,0],[1,0]]);q=np.array([[0.,0],[1.,0]])
    assert continuous_decide(p,q,0.)

def test_spherical_subdivision_error_bound():
    p=path_from_floor([[-1,-2],[1,-2]]);q=path_from_floor([[-1,-2],[0,-2],[1,-2]])
    for j in [0,1]:
        d=spherical_distance_interval(rays(p[:,j]),rays(q[:,j]),.5)
        assert d['lower_deg']==0 and d['upper_deg']<.002

def test_narrow_bump_preserved_and_not_skipped():
    p=path_from_floor([[-.01,-2],[.01,-2]])
    q=path_from_floor([[-.01,-2],[0,-2.7],[.01,-2]])
    assert spherical_check(rays(p[:,1]),rays(q[:,1]),5)['status']=='reject'
    assert q.shape[0]==3

def test_lower_same_upper_different():
    a=path_from_floor([[-1,-2],[1,-2]],.4);b=path_from_floor([[-1,-2],[1,-2]],1.2)
    assert spherical_check(rays(a[:,1]),rays(b[:,1]),5)['status']=='accept'
    assert spherical_check(rays(a[:,0]),rays(b[:,0]),12)['status']=='reject'

def test_close_seam_distinct_shapes_can_still_be_ambiguous():
    p=np.array([[1008.,140],[1020.,135],[8.,140]])
    q=p.copy();q[:,0]=(q[:,0]+8)%1024
    assert spherical_check(rays(p),rays(q),5)['status']=='accept'

@pytest.mark.parametrize('n',[0,1,2,3])
def test_raw_mv_has_no_min_four_fill_and_empty_is_explicit(n):
    rs=[record('A',[[-2,-2],[2,-2],[2,2],[-2,2]])]
    ns=nodes_from_records(rs);D=distances(ns)
    gr=[{'feature_id':f'G{i}','node_indices':[i],'support':1,'selected':i<n,
         'center':{'points':ns[i]['points']}} for i in range(4)]
    z=ring_diagnostics(rs,ns,gr,{i:f'G{i}' for i in range(4)})
    assert z['selected_pair_count']==n
    assert len(z['x_diagnostic']['points'])==2*n
    assert not z['minimum_four_pairs_enforced']
    if n<3:assert not z['x_diagnostic']['geometry_valid']

def test_same_worker_cannot_vote_twice_in_identity():
    rs=[record('A',[[-2,-2],[2,-2],[2,2],[-2,2]])]
    ns=nodes_from_records(rs);D=distances(ns);g,_=partition(ns,D['pair'],179)
    assert all(len(x)==1 for x in g)

def test_original_source_ring_and_interiors_unchanged():
    r=json.loads((ROOT/'inputs/rPc6DW4iMge-06.json').read_text())['records'];before=copy.deepcopy(r)
    ns=nodes_from_records(r);cfg=json.loads((ROOT/'config.json').read_text());b=PathBank(r,ns,cfg)
    i=next(i for i,n in enumerate(ns) if key(n)==('R01557',4));p=b.get(i,-1,2)
    assert p['processed_pair_indices']==[4,3,2]
    assert p['source_pair_indices']==[3,2,4]
    assert len(p['internal_observations'])==1 and r==before

def test_human_constraints_do_not_override_gate():
    r=json.loads((ROOT/'inputs/2t7WUuJeko7-06.json').read_text())['records']
    ns=nodes_from_records(r);D=distances(ns);ix={key(n):i for i,n in enumerate(ns)}
    triple=[ix[(rid,0)] for rid in ['R00227','R00539','R01831']]
    x=assisted_partition(ns,D,1,'pair',[triple],[])
    assert x['status']=='human_constraint_outside_numeric_gate'

def test_input_order_is_not_source_ring_change():
    r=json.loads((ROOT/'inputs/2t7WUuJeko7-06.json').read_text())['records']
    a=nodes_from_records(r);b=nodes_from_records(list(reversed(r)))
    assert a==b

def test_sphere_antipodal_not_arbitrarily_repaired():
    with pytest.raises(ValueError):polygonal_arc(np.array([[1.,0,0],[-1.,0,0]]),5)

def test_exact_gate_boundary_stays_numerical_undetermined():
    p=np.array([[0.,1.,0.],[0.,1.,0.]])
    t=np.radians(5);q=np.array([[np.sin(t),np.cos(t),0],[np.sin(t),np.cos(t),0]])
    z=spherical_check(p,q,5)
    assert z['status']=='undetermined'

def test_no_zero_length_reordering_to_fix_failed_source():
    r=json.loads((ROOT/'inputs/uNb9QFRL6hY-67.json').read_text())['records'];before=copy.deepcopy(r)
    ns=nodes_from_records(r);cfg=json.loads((ROOT/'config.json').read_text());b=PathBank(r,ns,cfg)
    i=next(i for i,n in enumerate(ns) if key(n)==('R02928',3));p=b.get(i,-1,2)
    assert p['processed_pair_indices']==[3,2,1]
    assert r==before
