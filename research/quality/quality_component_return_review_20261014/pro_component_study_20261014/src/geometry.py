"""Explicit-geometry probes, not a replacement for the repository's ERP loader.
Coordinates are horizontal (x,y); walls are vertical. Signed interior angles preserve
concavity. Reference correspondence is supplied, never optimized to improve a score.
"""
from __future__ import annotations
import numpy as np
from scipy.optimize import minimize_scalar
from scipy.spatial import cKDTree
from shapely.geometry import Polygon, Point

def check_polygon(points):
    a=np.asarray(points,dtype=float)
    if a.ndim!=2 or a.shape[1]!=2 or len(a)<3 or not np.isfinite(a).all():
        raise ValueError('Need >=3 finite horizontal vertices')
    p=Polygon(a)
    if not p.is_valid or p.area<1e-12: raise ValueError('Invalid or degenerate polygon')
    if np.any(np.linalg.norm(np.roll(a,-1,axis=0)-a,axis=1)<1e-12):
        raise ValueError('Zero-length edge')
    return a

def interior_angles(points):
    a=check_polygon(points); e=np.roll(a,-1,axis=0)-a; prev=np.roll(e,1,axis=0)
    area2=np.sum(a[:,0]*np.roll(a[:,1],-1)-a[:,1]*np.roll(a[:,0],-1))
    cross=prev[:,0]*e[:,1]-prev[:,1]*e[:,0]
    turn=np.arctan2(cross,np.sum(prev*e,axis=1))*np.sign(area2)
    return 180-np.rad2deg(turn)

def simplify_collinear(points,tol=1e-10):
    a=check_polygon(points).copy()
    # Representation equivalence only. A nonzero bump is not removed.
    while len(a)>3:
        e=np.roll(a,-1,axis=0)-a; prev=np.roll(e,1,axis=0)
        cr=prev[:,0]*e[:,1]-prev[:,1]*e[:,0]
        cos=np.sum(prev*e,axis=1)
        lengths=np.linalg.norm(prev,axis=1)*np.linalg.norm(e,axis=1)
        ids=np.flatnonzero((np.abs(cr)<=tol*lengths)&(cos>0))
        if not len(ids):break
        a=np.delete(a,ids[0],axis=0)
    return a

def matched_angle_error(candidate,reference,correspondence):
    a=interior_angles(candidate); b=interior_angles(reference)
    if correspondence is None: return {'available':False,'reason':'correspondence_required'}
    pairs=np.asarray(correspondence,dtype=int)
    if pairs.ndim!=2 or pairs.shape[1]!=2 or not len(pairs):
        raise ValueError('Explicit nonempty (candidate,reference) index pairs required')
    if len(np.unique(pairs[:,0]))!=len(pairs) or len(np.unique(pairs[:,1]))!=len(pairs):
        raise ValueError('One-to-one correspondence required')
    if (pairs<0).any() or (pairs[:,0]>=len(a)).any() or (pairs[:,1]>=len(b)).any():
        raise ValueError('Index out of bounds')
    diff=a[pairs[:,0]]-b[pairs[:,1]] # 90 vs 270 is a real concavity difference, not folded.
    return {'available':True,'matched_angle_rms_deg':float(np.sqrt(np.mean(diff**2))),
            'matched_angle_max_deg':float(np.max(np.abs(diff))),
            'candidate_corner_coverage':len(pairs)/len(a),
            'reference_corner_coverage':len(pairs)/len(b),
            'complete_correspondence':len(pairs)==len(a)==len(b),
            'candidate_angles_deg':a.tolist(),'reference_angles_deg':b.tolist()}

def direction_rms(points):
    a=check_polygon(points); e=np.roll(a,-1,axis=0)-a
    lengths=np.linalg.norm(e,axis=1); theta=np.rad2deg(np.arctan2(e[:,1],e[:,0]))
    def objective(phi):
        r=(theta-phi+45)%90-45
        return np.average(r*r,weights=lengths)
    # The wrapped quadratic has finitely many breakpoints, so optimize each interval.
    breaks=np.unique(np.r_[0,90,(theta+45)%90]); vals=[]
    for lo,hi in zip(breaks[:-1],breaks[1:]):
        opt=minimize_scalar(objective,bounds=(lo,hi),method='bounded',options={'xatol':1e-12})
        vals.extend([objective(lo),objective(hi),opt.fun])
    return float(np.sqrt(max(0,min(vals))))

def floor_iou(a,b):
    pa,pb=Polygon(check_polygon(a)),Polygon(check_polygon(b))
    return pa.intersection(pb).area/pa.union(pb).area

def spherical_bottom_distance(a,b,n=2048):
    def samples(v):
        v=check_polygon(v);e=np.roll(v,-1,axis=0)-v;length=np.linalg.norm(e,axis=1)
        cum=np.r_[0,np.cumsum(length)]; t=(np.arange(n)+.5)*cum[-1]/n
        idx=np.minimum(np.searchsorted(cum,t,side='right')-1,len(v)-1)
        xy=v[idx]+e[idx]*((t-cum[idx])/length[idx])[:,None]
        xyz=np.c_[xy,-np.ones(n)];return xyz/np.linalg.norm(xyz,axis=1)[:,None]
    # Probe-only fixed-perimeter sampling; do not assert equivalence to native Sb sampling.
    x,y=samples(a),samples(b)
    d1=cKDTree(y).query(x)[0];d2=cKDTree(x).query(y)[0]
    return float(np.rad2deg(np.r_[2*np.arcsin(np.minimum(d1/2,1)),
                                 2*np.arcsin(np.minimum(d2/2,1))]).mean())
