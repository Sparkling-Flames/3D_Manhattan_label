"""Frozen bound-cyclic distance and global affinity partition for the v2 study.

The distance calls GitHub-main's angular/cyclic functions directly.  The MILP
is the same binary-pair/transitivity objective as build_cluster_review_20261018,
with mathematically exact connected-component decomposition and one solver
thread.  No Q, reference, time, or fusion result enters this module.
"""
from __future__ import annotations

import itertools
import time
import warnings
import numpy as np
from scipy.optimize import Bounds, LinearConstraint, milp
from scipy.sparse import coo_matrix, vstack, csr_matrix
from tools.thesis_main.analysis.paired_split_research.study import angular, cyclic, cluster

DISTANCE_VERSION = 'github_main_82c6164_bound_cyclic_max_endpoint_deg'


def bound_cyclic_distance(a, b, diagnostics=True):
    a, b = np.asarray(a, float), np.asarray(b, float)
    base = dict(available=False, distance_deg=None, shift_a_to_b=None,
                shift_margin_deg=None, pair_count_a=len(a)//2,
                pair_count_b=len(b)//2, reason='different_bound_pair_counts')
    if len(a) != len(b):
        return base
    assert a.ndim == b.ndim == 2 and a.shape[1] == b.shape[1] == 2
    assert len(a) >= 6 and len(a) % 2 == 0
    assert np.isfinite(a).all() and np.isfinite(b).all()
    top, bottom = angular(a[::2], b[::2]), angular(a[1::2], b[1::2])
    d, shift, margin = cyclic(np.maximum(top, bottom))
    out = dict(base, available=True, distance_deg=d, shift_a_to_b=shift,
               shift_margin_deg=margin, reason='')
    if diagnostics:
        n = len(a)//2
        ix, jx = np.arange(n), (np.arange(n)+shift) % n
        reverse_b = b.reshape(-1, 2, 2)[::-1].reshape(-1, 2)
        reverse_distance = cyclic(np.maximum(angular(a[::2], reverse_b[::2]),
                                             angular(a[1::2], reverse_b[1::2])))[0]
        out.update(top_max_at_bound_shift_deg=float(top[ix,jx].max()),
                   bottom_max_at_bound_shift_deg=float(bottom[ix,jx].max()),
                   bottom_only_best_cyclic_deg=cyclic(bottom)[0],
                   reverse_ring_diagnostic_deg=reverse_distance,
                   reversal_allowed_diagnostic_deg=min(d, reverse_distance),
                   bottom_y_max_at_bound_shift_px=float(abs(a[1::2,1]-b[1::2,1][jx]).max()))
    return out


def objective(d, groups, cut):
    return float(sum(max(0.,1-float(d[i,j])/cut)**2
                     for g in groups for i,j in itertools.combinations(g,2)))


def complete_link(d, cut):
    labels = cluster(d,cut)
    return [np.flatnonzero(labels == label).tolist() for label in sorted(set(labels))]


def components(near):
    left = set(range(len(near))); out = []
    while left:
        stack = [min(left)]; left.remove(stack[0]); current = []
        while stack:
            i = stack.pop(); current.append(i)
            new = sorted(j for j in left if near[i,j]); left.difference_update(new); stack.extend(new)
        out.append(sorted(current))
    return out


def milp_arrays(d, cut):
    edges = list(itertools.combinations(range(len(d)),2)); edge_ix = {e:i for i,e in enumerate(edges)}
    rows=[]; cols=[]; vals=[]
    for t,(i,j,k) in enumerate(itertools.combinations(range(len(d)),3)):
        ids = [edge_ix[i,j],edge_ix[i,k],edge_ix[j,k]]
        for z in range(3):
            for q in range(3):
                rows.append(3*t+z); cols.append(ids[q]); vals.append(-1. if q==z else 1.)
    m = len(rows)//3
    a = coo_matrix((vals,(rows,cols)),shape=(m,len(edges))).tocsr()
    near=np.asarray([d[i,j] <= cut for i,j in edges],float)
    weights=np.asarray([max(0.,1-d[i,j]/cut)**2 for i,j in edges],float)
    return edges,a,near,weights


def _groups(x, edges, n):
    parent=list(range(n))
    def root(i):
        while parent[i] != i:
            i=parent[i]
        return i
    for v,(i,j) in zip(x,edges):
        if v>.5: parent[root(j)]=root(i)
    result = [[i for i in range(n) if root(i)==r] for r in sorted({root(i) for i in range(n)})]
    assert all((root(i)==root(j)) == (v>.5) for v,(i,j) in zip(x,edges))
    return result


def milp_partition(d, cut, time_limit=60., alternate_check=False):
    edges,a,near,weights=milp_arrays(d,cut); started=time.monotonic()
    options=dict(time_limit=time_limit,mip_rel_gap=0.,threads=1)
    with warnings.catch_warnings():
        warnings.filterwarnings('ignore',message='Unrecognized options detected')
        result=milp(-weights,integrality=np.ones(len(edges)),bounds=Bounds(0,near),
                    constraints=LinearConstraint(a,-np.inf,1) if a.shape[0] else None,options=options)
    fallback = result.x is None
    groups = complete_link(d,cut) if fallback else _groups(result.x,edges,len(d))
    assert all(d[i,j] <= cut for g in groups for i,j in itertools.combinations(g,2))
    value=objective(d,groups,cut)
    status=dict(method='binary_pair_transitivity_milp',optimal=bool(result.status==0),
                status=int(result.status),gap=None if fallback else float(result.mip_gap),
                objective=value,dual_bound=None if fallback else float(result.mip_dual_bound),
                node_count=None if fallback else int(result.mip_node_count),
                seconds=time.monotonic()-started,message=str(result.message),
                no_incumbent_complete_fallback=fallback,alternative_status='not_probed',
                alternative_optimal_partition=None,alternative_affected_members=None)
    # A numerical uniqueness probe is diagnostic, never a mathematical uniqueness claim.
    if alternate_check and status['optimal'] and not fallback:
        chosen=(result.x>.5).astype(int); no_good=2*chosen-1
        aa=vstack([a,csr_matrix(no_good[None,:]),csr_matrix(weights[None,:])]).tocsr()
        lo=np.r_[np.full(a.shape[0],-np.inf),-np.inf,value-1e-7]
        hi=np.r_[np.ones(a.shape[0]),chosen.sum()-1,np.inf]
        with warnings.catch_warnings():
            warnings.filterwarnings('ignore',message='Unrecognized options detected')
            other=milp(np.zeros(len(edges)),integrality=np.ones(len(edges)),bounds=Bounds(0,near),
                       constraints=LinearConstraint(aa,lo,hi),options=dict(options,time_limit=5.))
        status['alternative_status']=str(other.message)
        if other.x is not None:
            alternatives=_groups(other.x,edges,len(d)); status['alternative_optimal_partition']=True
            changed=set()
            for p,(i,j) in enumerate(edges):
                if (other.x[p]>.5) != (result.x[p]>.5): changed.update((i,j))
            status['alternative_affected_members']=sorted(changed)
        elif other.status==2:
            status['alternative_optimal_partition']=False
    return groups,status


def affinity_partition(d, cut, time_limit=60., alternate_check=False):
    d=np.asarray(d,float); assert np.isfinite(d).all() and np.allclose(d,d.T)
    groups=[]; statuses=[]
    for c,ids in enumerate(components(d<=cut)):
        sub=d[np.ix_(ids,ids)]
        if len(ids)==1 or np.all(sub<=cut):
            local=[list(range(len(ids)))]; val=objective(sub,local,cut)
            zero_edges=any(abs(sub[i,j]-cut)<1e-12 for i,j in itertools.combinations(range(len(ids)),2))
            status=dict(method='complete_component_upper_bound',optimal=True,status=0,gap=0.,
                        objective=val,dual_bound=-val,node_count=0,seconds=0.,
                        message='Complete allowed graph: one group attains all nonnegative weights.',
                        no_incumbent_complete_fallback=False,alternative_status='zero_weight_edges_present' if zero_edges else 'strict_positive_complete_component',
                        alternative_optimal_partition=None if zero_edges else False,
                        alternative_affected_members=None)
        else:
            local,status=milp_partition(sub,cut,time_limit,alternate_check and len(ids)<=12)
        groups.extend([[ids[k] for k in g] for g in local])
        statuses.append(dict(component_index=c,n=len(ids),local_indices=ids,**status))
    groups.sort(key=tuple)
    assert sorted(i for g in groups for i in g)==list(range(len(d)))
    return groups,statuses
