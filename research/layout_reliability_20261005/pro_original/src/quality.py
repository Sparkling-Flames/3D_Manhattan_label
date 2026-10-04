"""Declared spherical-boundary and area diagnostics; no compound quality score.
The directed spherical distance is sampled uniformly in arc length with an
explicit 1-Lipschitz quadrature error bound. All declared edges participate,
including hidden edges. This is not visibility or topology matching.
"""
from __future__ import annotations
import numpy as np
from arc_consensus import rays,pairs,footprint,area_scores,paired_wall_proxy,Unsupported,H

def angle(a,b):
    a=np.asarray(a); b=np.asarray(b)
    return np.arctan2(np.linalg.norm(np.cross(a,b),axis=-1),np.sum(a*b,axis=-1))

def unit_arcs(record,side):
    a=rays(pairs(record)[:,side]); b=np.roll(a,-1,axis=0)
    length=angle(a,b)
    if np.any(length>=np.pi-1e-10): raise Unsupported('antipodal_or_camera_crossing_edge')
    use=length>1e-12
    if not use.any(): raise Unsupported('zero_boundary_length')
    return a[use],b[use],length[use]

def sample_arcs(record,side,max_step_deg=.1):
    if not np.isfinite(max_step_deg) or max_step_deg<=0: raise ValueError('positive_finite_sample_step_required')
    a,b,length=unit_arcs(record,side); pts=[]; weights=[]; max_step=0.
    for u,v,l in zip(a,b,length):
        n=max(1,int(np.ceil(np.degrees(l)/max_step_deg))); step=l/n
        t=(np.arange(n)+.5)/n
        pts.append((np.sin((1-t)*l)[:,None]*u+np.sin(t*l)[:,None]*v)/np.sin(l))
        weights.extend([step]*n); max_step=max(max_step,step)
    return np.concatenate(pts),np.array(weights),max_step

def point_arc_dist(points,record,side):
    u,v,l=unit_arcs(record,side); n=np.cross(u,v); n/=np.linalg.norm(n,axis=1)[:,None]
    near=np.cross(n,u); far=np.cross(v,n); result=[]
    for w in np.array_split(np.asarray(points,float),max(1,int(np.ceil(len(points)/2048)))):
        edge_dot=np.maximum(w@u.T,w@v.T)
        endpoint=np.arccos(np.clip(edge_dot,-1,1))
        within=((w@near.T)>=-1e-12)&((w@far.T)>=-1e-12)
        perp=np.arcsin(np.clip(abs(w@n.T),0,1))
        result.append(np.minimum(endpoint,np.where(within,perp,np.inf)).min(axis=1))
    return np.concatenate(result)

def directed(source,target,side,step=.1):
    p,w,h=sample_arcs(source,side,step); d=point_arc_dist(p,target,side)
    order=np.argsort(d); cum=np.cumsum(w[order])/w.sum()
    mean=float(np.sum(w*d)/w.sum()); mx=float(d.max())
    return dict(mean_deg=float(np.degrees(mean)),p95_deg=float(np.degrees(d[order[np.searchsorted(cum,.95)]])),
                max_lower_deg=float(np.degrees(mx)),max_upper_deg=float(np.degrees(mx+h/2)),
                mean_absolute_numerical_bound_deg=float(np.degrees(h/4)),sample_n=len(p),
                interpretation='distance to declared curve union; not correspondence or semantic correctness')

def quality(candidate,reference,step=.1):
    _,A=footprint(candidate);_,G=footprint(reference); out=area_scores(A,G)
    out['centroid_normalized']=out['centroid_distance_h']/np.sqrt(G.area) if out['centroid_distance_h'] is not None else None
    for side,name in [(0,'top'),(1,'bottom')]:
        out[name+'_candidate_to_reference']=directed(candidate,reference,side,step)
        out[name+'_reference_to_candidate']=directed(reference,candidate,side,step)
    t,b=paired_wall_proxy(candidate)
    out['top_height_proxy_min_h']=float(t[:,1].min());out['top_height_proxy_max_h']=float(t[:,1].max())
    out['solid_iou']=None;out['solid_iou_reason']='roof_interior_not_specified'
    out['height_profile_difference']=height_profile_difference(candidate,reference)
    out['height_coordinate_definition']='top Y relative to camera; floor Y=-1; full local wall height is top Y+1'
    out['pair_count']=len(pairs(candidate));return out

def height_profile_difference(candidate,reference):
    """Conditional eaves-height disagreement at common camera azimuths.
    Relative camera height is the unit. Floor depth and top angle BOTH enter.
    Not a roof/shell volume and not a direct independent height observation.
    """
    from scipy.integrate import quad
    from arc_consensus import Ring,TAU,unique_angles
    try:a,b=Ring(candidate),Ring(reference)
    except Unsupported as e:return dict(status='unsupported',reason=str(e))
    cuts=unique_angles([0.,TAU]+[v for r in (a,b) for p in r.pieces for v in (p.lo,p.hi)])
    total=0.;bound=0.
    for lo,hi in zip(cuts[:-1],cuts[1:]):
        ca=a.active((lo+hi)/2).coeff;cb=b.active((lo+hi)/2).coeff
        def fun(u):
            v=np.array([np.sin(u),np.cos(u)]);za=ca@v;zb=cb@v
            return abs(-za[0]/za[1]+zb[0]/zb[1])
        val,err=quad(fun,lo,hi,epsabs=1e-10,epsrel=1e-10,limit=100);total+=val;bound+=err
    return dict(status='conditional_on_common_floor',azimuth_mean_absolute_height_difference_h=total/TAU,
                quadrature_error_estimate_h=bound/TAU,depends_on='both_floor_depth_and_top_angle',
                unknown_roof_interior_not_evaluated=True)
