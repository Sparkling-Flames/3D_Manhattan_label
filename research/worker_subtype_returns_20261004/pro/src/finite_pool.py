"""Exact finite-worker-pool region probabilities and coupled changes.
No worker independence assumption: annotations are fixed. Independence refers only
 to the specified random subset draws. GT is evaluation-only; no shape repair.
"""
from __future__ import annotations
from dataclasses import dataclass
from functools import lru_cache
import itertools, math
import numpy as np
from shapely.geometry import Polygon
from shapely.ops import unary_union, polygonize

@lru_cache(None, typed=True)
def hg(N:int,c:int,k:int):
    if any(isinstance(x,bool) or not isinstance(x,(int,np.integer)) for x in (N,c,k)):
        raise ValueError('hypergeom_requires_integer_counts')
    if not (0<=c<=N and 0<=k<=N):raise ValueError('infeasible_hypergeom')
    den=math.comb(N,k)
    return tuple((j,math.comb(c,j)*math.comb(N-c,k-j)/den)
                 for j in range(max(0,k-(N-c)),min(c,k)+1))

def threshold(n:int,rule:str):
    if isinstance(n,bool) or not isinstance(n,(int,np.integer)) or n<1:raise ValueError('nonempty_integer_consensus_size_required')
    if rule=='mv50':return (n+1)//2
    if rule=='mv_strict':return n//2+1
    raise ValueError('unknown_rule')

def states(N,C,K):
    if len(N)!=len(C) or len(N)!=len(K):raise ValueError('class_dimension_mismatch')
    for x in itertools.product(*(hg(n,c,k) for n,c,k in zip(N,C,K))):
        yield tuple(i[0] for i in x),math.prod(i[1] for i in x)

@lru_cache(None)
def _marginal(N,C,K,rule):
    t=threshold(sum(K),rule)
    return sum(p for J,p in states(N,C,K) if sum(J)>=t)

@lru_cache(None)
def _coupled(N,C,K,rule,operation,change):
    """Return Pr(flip), Pr(0->1), Pr(1->0) for a specified coupled draw.
    add: change is count vector of new people, without replacement.
    swap: change=(removed_class, added_class), incoming person outside OLD subset.
    disjoint: second subset same composition, excludes all first-subset members.
    """
    k=sum(K); t=threshold(k,rule); flip=grow=shrink=0.
    if operation=='add':
        A=change
        if len(A)!=len(N) or not any(A) or any(a<0 or a+k>n for a,k,n in zip(A,K,N)):
            raise ValueError('infeasible_add')
        t2=threshold(k+sum(A),rule)
    elif operation=='swap':
        a,b=change
        if not (0<=a<len(N) and 0<=b<len(N)) or K[a]==0 or K[b]==N[b]:
            raise ValueError('infeasible_swap')
        t2=t
    elif operation=='disjoint':
        if any(2*k>n for k,n in zip(K,N)):raise ValueError('disjoint_groups_not_supported')
        t2=t
    else:raise ValueError('unknown_coupling')
    for J,p in states(N,C,K):
        j=sum(J);old=j>=t
        if operation=='add':
            nxt=((j+sum(Z),pz) for Z,pz in states(tuple(n-k for n,k in zip(N,K)),tuple(c-j for c,j in zip(C,J)),A))
        elif operation=='disjoint':
            nxt=((sum(Z),pz) for Z,pz in states(tuple(n-k for n,k in zip(N,K)),tuple(c-j for c,j in zip(C,J)),K))
        else:
            pr=J[a]/K[a];pa=(C[b]-J[b])/(N[b]-K[b])
            nxt=((j-u+v,pu*pv) for u,pu in ((0,1-pr),(1,pr)) for v,pv in ((0,1-pa),(1,pa)))
        for z,pz in nxt:
            new=z>=t2
            if new!=old:
                w=p*pz;flip+=w
                if new:grow+=w
                else:shrink+=w
    return float(flip),float(grow),float(shrink)

@dataclass
class Basis:
    records:list
    polygons:list
    tiles:list
    area:np.ndarray
    votes:np.ndarray
    reference:object|None
    inside_reference:np.ndarray|None
    reference_outside_union:float|None
    checks:dict
    @property
    def union_area(self):return float(self.area.sum())
    def group_data(self,labels):
        labels=np.asarray(labels)
        if len(labels)!=len(self.records):raise ValueError('labels_roster_mismatch')
        unique=np.unique(labels)
        if not np.array_equal(unique,np.arange(len(unique))):raise ValueError('labels_must_be_contiguous_zero_based')
        N=tuple(int(np.sum(labels==j)) for j in unique)
        C=np.array([self.votes[labels==j].sum(axis=0) for j in unique]).T
        return N,C
    def q(self,labels,K,rule):
        N,C=self.group_data(labels);K=tuple(K)
        return np.array([marginal(N,tuple(map(int,c)),K,rule) for c in C])
    def area_summary(self,q):
        q=np.asarray(q,float);A=self.union_area
        if len(q)!=len(self.area) or np.any(q<-1e-12) or np.any(q>1+1e-12):raise ValueError('invalid_probabilities')
        v=float(np.sum(self.area*q*(1-q)))
        out=dict(expected_area_union=float(self.area@q/A),same_k_independent_symdiff_union=2*v/A)
        if self.reference is not None:
            inside=self.inside_reference
            omission=float(inside@(1-q)+self.reference_outside_union)
            extension=float((self.area-inside)@q)
            out.update(expected_ref_symdiff_union=(omission+extension)/A,
                       expected_omission_union=omission/A,expected_extension_union=extension/A,
                       expected_ref_symdiff_gt=(omission+extension)/self.reference.area,
                       squared_bias_union=(omission+extension-v)/A)
        return out
    def transition(self,labels,K,rule,operation,change):
        N,C=self.group_data(labels);K=tuple(K);change=tuple(change)
        p=np.array([coupled(N,tuple(map(int,c)),K,rule,operation,change) for c in C]);A=self.union_area
        out=dict(expected_shape_change_union=float(self.area@p[:,0]/A),expected_growth_union=float(self.area@p[:,1]/A),expected_shrinkage_union=float(self.area@p[:,2]/A))
        if self.reference is not None:
            out['expected_ref_error_change_union']=float((self.area-2*self.inside_reference)@(p[:,1]-p[:,2])/A)
        return out
    def subset(self,indices,rule):
        indices=list(indices)
        if any(isinstance(x,bool) or not isinstance(x,(int,np.integer)) for x in indices):raise ValueError('integer_member_indices_required')
        if not indices or len(set(indices))!=len(indices) or min(indices)<0 or max(indices)>=len(self.records):raise ValueError('invalid_subset')
        return self.votes[indices].sum(axis=0)>=threshold(len(indices),rule)
    def iou(self,mask):
        if self.reference is None:return None
        I=float(self.inside_reference@mask);U=float(self.reference.area+self.area@mask-I)
        return I/U if U>0 else 1.

def make_basis(records,reference=None):
    if not records:raise ValueError('empty_roster')
    for key in ['id','worker']:
        v=[r.get(key) for r in records]
        if any(not x for x in v) or len(set(v))!=len(v):raise ValueError('missing_or_duplicate_'+key)
    if len({r.get('condition') for r in records})!=1 or not records[0].get('condition'):raise ValueError('one_explicit_condition_required')
    for r in records:
        if r.get('independent') is not True or r.get('consensus_eligible') is not True or r.get('borrowed_points') is True:raise ValueError('non_independent_or_noneligible_member:'+r['id'])
        if r.get('footprint') is None:raise ValueError('whole_pool_unavailable:'+r['id'])
    P=[]
    for r in records:
        p=np.asarray(r['footprint'],float)
        if p.ndim!=2 or p.shape[1]!=2 or len(p)<3 or not np.isfinite(p).all():raise ValueError('invalid_footprint:'+r['id'])
        poly=Polygon(p)
        if not poly.is_valid or poly.area<=0:raise ValueError('invalid_polygon_no_repair:'+r['id'])
        P.append(poly)
    U=unary_union(P)
    tiles=[p for p in polygonize(unary_union([p.boundary for p in P])) if U.covers(p.representative_point())]
    areas=np.array([p.area for p in tiles]);v=np.array([[p.covers(t.representative_point()) for t in tiles] for p in P],bool)
    covered=np.array([float(areas@row) for row in v]); err=float(np.max(np.abs(covered-[p.area for p in P])))
    if err>1e-9*max(1.,U.area) or abs(areas.sum()-U.area)>1e-9*max(1.,U.area):raise ValueError('tiling_area_validation_failed')
    G=None
    if reference is not None:
        rp=np.asarray(reference.get('footprint'),float)
        if rp.ndim!=2 or rp.shape[1]!=2 or len(rp)<3 or not np.isfinite(rp).all():raise ValueError('reference_unavailable_no_repair')
        G=Polygon(rp)
        if not G.is_valid or G.area<=0:raise ValueError('reference_unavailable_no_repair')
    inside=np.array([t.intersection(G).area for t in tiles]) if G is not None else None
    outside=float(G.difference(U).area) if G is not None else None
    return Basis(records,P,tiles,areas,v,G,inside,outside,dict(tile_n=len(tiles),max_individual_area_error=err,union_area_error=float(abs(areas.sum()-U.area))))

@lru_cache(None)
def _next_member_loss(N,C,K,rule,new_group):
    """Probability current fused bit disagrees with next unseen SAME-pool person.
    Unlike add-one change, the second bit is the person's annotation, not refusion.
    """
    if not 0<=new_group<len(N) or K[new_group]>=N[new_group]:raise ValueError('no_remaining_member')
    t=threshold(sum(K),rule);out=0.
    for J,p in states(N,C,K):
        q=(C[new_group]-J[new_group])/(N[new_group]-K[new_group])
        out+=p*((1-q) if sum(J)>=t else q)
    return float(out)


def _validate_counts(N,C,K):
    if len(N)!=len(C) or len(N)!=len(K) or not len(N):
        raise ValueError('class_dimension_mismatch')
    for n,c,k in zip(N,C,K):
        hg(n,c,k)

def marginal(N,C,K,rule):
    _validate_counts(N,C,K)
    return _marginal(tuple(N),tuple(C),tuple(K),rule)

def coupled(N,C,K,rule,operation,change):
    _validate_counts(N,C,K)
    if any(isinstance(x,bool) or not isinstance(x,(int,np.integer)) for x in change):
        raise ValueError('integer_changes_required')
    return _coupled(tuple(N),tuple(C),tuple(K),rule,operation,tuple(change))

def next_member_loss(N,C,K,rule,new_group):
    _validate_counts(N,C,K)
    if isinstance(new_group,bool) or not isinstance(new_group,(int,np.integer)):
        raise ValueError('integer_group_required')
    return _next_member_loss(tuple(N),tuple(C),tuple(K),rule,new_group)
