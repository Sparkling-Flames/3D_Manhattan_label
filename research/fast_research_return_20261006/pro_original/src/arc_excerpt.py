"""Relevant unchanged functions from repository arc_consensus.py (2026-10-06).
Source: tools/thesis_main/analysis/layout_reliability_20261005/arc_consensus.py
Only imports and unused functions were omitted. Used for reading/rendering saved
outputs, not for rerunning consensus or changing source geometry.
"""
from __future__ import annotations
from dataclasses import dataclass
import numpy as np
from shapely.geometry import Polygon
W, H, TAU = 1024., 512., 2*np.pi
EPS = 2e-11
class Unsupported(ValueError):
    pass

def rays(p):
    p=np.asarray(p,float)
    u=TAU*(p[...,0]/W-.5); v=np.pi*(.5-p[...,1]/H)
    return np.stack((np.cos(v)*np.sin(u),np.sin(v),-np.cos(v)*np.cos(u)),axis=-1)

def project(xyz):
    z=np.asarray(xyz,float); norm=np.linalg.norm(z,axis=-1)
    if np.any(norm<=0): raise Unsupported('projection_at_camera')
    return np.stack(((np.arctan2(z[...,0],-z[...,2])/TAU+.5)%1*W,
                     (.5-np.arcsin(np.clip(z[...,1]/norm,-1,1))/np.pi)*H),axis=-1)

def pairs(record):
    try: p=np.asarray(record['points'],float)
    except (KeyError,TypeError,ValueError) as e: raise Unsupported('points_missing_or_invalid') from e
    if p.ndim!=2 or p.shape[1]!=2 or len(p)<6 or len(p)%2 or not np.isfinite(p).all():
        raise Unsupported('finite_paired_array_required')
    if np.any(p[:,0]<0) or np.any(p[:,0]>W) or np.any(p[:,1]<0) or np.any(p[:,1]>H):
        raise Unsupported('outside_continuous_canvas')
    q=p.reshape(-1,2,2)
    for key,stride in [('source_point_indices',2),('source_pair_indices',1)]:
        values=record.get(key)
        if values is not None and (len(values)!=stride*len(q) or any(type(v) is not int for v in values)):
            raise Unsupported('invalid_source_identity_metadata:'+key)
    if np.any(abs((q[:,0,0]-q[:,1,0]+W/2)%W-W/2)>1e-8):
        raise Unsupported('shared_longitude_required_no_repair')
    return q

def footprint(record):
    q=pairs(record); rr=rays(q[:,1])
    if np.any(rr[:,1]>=-1e-12): raise Unsupported('bottom_not_finite_below_horizon')
    f=(-rr/rr[:,1,None])[:,[0,2]]
    poly=Polygon(f)
    if not poly.is_valid or poly.area<=1e-12: raise Unsupported('invalid_declared_polygon_no_repair')
    return f,poly

def paired_wall_proxy(record):
    q=pairs(record); f,poly=footprint(record)
    rt=rays(q[:,0]); hz=np.linalg.norm(rt[:,[0,2]],axis=1)
    if np.any(hz<1e-12): raise Unsupported('top_at_pole')
    top=rt*(np.linalg.norm(f,axis=1)/hz)[:,None]
    bottom=np.column_stack((f[:,0],-np.ones(len(f)),f[:,1]))
    return top,bottom

@dataclass
class Piece:
    lo: float
    hi: float
    coeff: np.ndarray
    edge: int
    record: dict
    def value(self,u):
        u=np.asarray(u); return np.einsum('sj,...j->s...',self.coeff,np.stack((np.sin(u),np.cos(u)),axis=-1))

class Ring:
    def __init__(self,record):
        self.record=record; self.q=pairs(record)
        q=self.q
        if np.any(q[:,0,1]<=0) or np.any(q[:,0,1]>=H/2) or np.any(q[:,1,1]<=H/2) or np.any(q[:,1,1]>=H):
            raise Unsupported('strict_horizon_straddling_required')
        u=q[:,0,0]%W/W*TAU
        d=(np.roll(u,-1)-u+np.pi)%TAU-np.pi
        if np.any(abs(d)<EPS) or np.any(abs(d)>=np.pi-EPS):
            raise Unsupported('zero_or_half_turn_longitude_edge')
        if not ((np.all(d>0) or np.all(d<0)) and abs(abs(d.sum())-TAU)<1e-8):
            raise Unsupported('source_ring_not_single_valued_one_turn')
        self.direction=1 if d[0]>0 else -1
        self.foot,self.polygon=footprint(record)
        self.pieces=[]
        for i,span in enumerate(d):
            j=(i+1)%len(q)
            M=np.array([[np.sin(u[i]),np.cos(u[i])],[np.sin(u[j]),np.cos(u[j])]])
            if abs(np.linalg.det(M))<1e-12: raise Unsupported('singular_edge_plane')
            z=np.tan(np.pi*(.5-q[[i,j],:,1]/H))
            C=np.linalg.solve(M,z).T
            lo=float(u[i] if span>0 else u[j]); end=float(u[j] if span>0 else u[i])
            if end>lo:
                self.pieces.append(Piece(lo,end,C,i,record))
            else:
                self.pieces.append(Piece(lo,TAU,C,i,record))
                if end>0.: self.pieces.append(Piece(0.,end,C,i,record))
        self.pieces.sort(key=lambda p:p.lo)
        if abs(sum(p.hi-p.lo for p in self.pieces)-TAU)>1e-8:
            raise Unsupported('incomplete_longitude_coverage')
    def active(self,u):
        u=float(u)%TAU
        pp=[p for p in self.pieces if p.lo<=u<p.hi]
        if len(pp)!=1: raise Unsupported('nonunique_active_edge')
        return pp[0]
    def evaluate(self,u):
        a=np.asarray(u,float); flat=a.reshape(-1)%TAU; out=np.empty((2,len(flat)))
        coverage=np.zeros(len(flat),int)
        for p in self.pieces:
            ix=(flat>=p.lo)&(flat<p.hi)
            out[:,ix]=p.value(flat[ix]); coverage[ix]+=1
        if np.any(coverage!=1): raise Unsupported('sampling_coverage_failure')
        return (H*(.5-np.arctan(out)/np.pi)).reshape((2,)+a.shape)
