"""Frozen-input adapters and candidate quality formulas; no reference selection.
Angles in degrees; heights relative to reference perimeter-mean wall height.
"""
from __future__ import annotations
import json, sys, math, hashlib
from pathlib import Path
import numpy as np
ROOT = Path(__file__).resolve().parents[1]
INPUT = ROOT/'frozen_input'
sys.path.insert(0, str(INPUT/'engine'))
import audit_geometry as au
import geometric_components as sp
import strict_geometry as valid
import height_revision as hm
import centered_height as center
import traditional_metrics as trad
import score as frozen_score
from prepare_inputs import geometry
from evaluate_geometry import evaluate_geometry

BASE = dict(frozen_score.BASELINE, name='current_hill08')
METRICS = ('iou_2d','S_bottom_deg','dir','Hmean','Hcenter')

def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))

def clean(x):
    if isinstance(x,dict): return {str(k):clean(v) for k,v in x.items()}
    if isinstance(x,(list,tuple)): return [clean(v) for v in x]
    if isinstance(x,np.ndarray): return clean(x.tolist())
    if isinstance(x,np.generic): return clean(x.item())
    if isinstance(x,float) and not math.isfinite(x): return None
    return x

def dump(path,x):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(clean(x),ensure_ascii=False,indent=2,allow_nan=False)+'\n',encoding='utf-8')

def sha(path): return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def digest(x): return hashlib.sha256(json.dumps(clean(x),sort_keys=True,ensure_ascii=False,separators=(',',':')).encode()).hexdigest()

def engine():
    return dict(au=au,sp=sp,valid=valid,hm=hm,center=center,trad=trad,score=frozen_score,configs={'current':BASE})

def components(metrics,config,extra=None):
    """Full Q is None when either height term is missing. I=0 has exact zero limit.
    loss_sum: Q=100/(1/I + B + Ld + H), i.e. additive neutral losses.
    max_floor is included as a comparison, not silently renamed loss_sum.
    """
    c=dict(config); combine=c.get('combine','additive'); direction=c.get('direction_metric','dir')
    m=dict(metrics)
    if direction!='dir':
        if extra is None or extra.get(direction) is None:
            return dict(status='unavailable',reason='missing_'+direction,score=None,floor_score=None)
        # Frozen validator applies a D-specific domain bound, so use a validated
        # placeholder there, then evaluate the explicitly named alternative below.
        alt=float(extra[direction]);m['dir']=0.
        if not math.isfinite(alt) or alt<0 or alt>90.+1e-7:
            return dict(status='unavailable',reason='invalid_'+direction,score=None,floor_score=None)
    c['combine']='additive' if combine=='loss_sum' or direction!='dir' else combine
    out=frozen_score.score_metrics(m,c)
    if out['status'] not in ('complete','floor_only','height_unavailable'):return out
    if direction!='dir':out['direction_loss']=float(frozen_score.direction_loss(alt,c))
    I=float(frozen_score.normalized_metrics(m)['I']);I=min(I,1.)
    B=out['boundary_loss'];Ld=out['direction_loss']
    H=out['height_loss'] if out['height_loss'] is not None else 0.
    Ip=1. if c.get('overlap_disabled') else I**c['iou_power']
    if combine=='loss_sum':
        # Numerically stable form, including I=0.
        floor=100*Ip/(1+Ip*(B+Ld));q=100*Ip/(1+Ip*(B+Ld+H))
        den=1+Ip*(B+Ld+H)
    elif direction!='dir':
        if combine!='additive':raise ValueError('alternative direction supports additive/loss_sum only')
        floor=100*Ip/(1+B+Ld);q=100*Ip/(1+B+Ld+H);den=1+B+Ld+H
    else:return out
    out.update(score=q if out['status']=='complete' else None,floor_score=floor,
               height_score_drop=floor-q if out['status']=='complete' else None,
               denominator=den,denominator_semantics='stable_I_numerator' if combine=='loss_sum' else 'unit_numerator_loss',
               overlap_neutral_loss=1/Ip-1 if Ip else None)
    return out

def profile(g):
    theta,w=au.direction_data(g);ax=au.direction_axis(g)
    t=np.rad2deg(theta);axis=np.rad2deg(ax);w=w/w.sum()
    r=(t-axis+45)%90-45
    edges=np.roll(np.asarray(g['bottom3d']),-1,axis=0)-np.asarray(g['bottom3d'])
    turns=(np.roll(t,-1)-t+180)%360-180
    return dict(axis_deg=float(axis),D=float(np.sqrt(w@(r*r))),D_equal_edge=float(np.sqrt(np.mean(r*r))),
        edge_angle_deg=t.tolist(),weights=w.tolist(),residual_deg=r.tolist(),
        axis_family=(np.rint((t-axis)/90).astype(int)%2).tolist(),
        signed_turn_deg=turns.tolist(),edge_length=np.linalg.norm(edges,axis=1).tolist(),
        near_parallel_adjacent_fraction=float(np.mean(np.abs(turns)<45)),
        absolute_turn_total=float(np.sum(abs(turns))))

def _nearest_normal(p,q,n):
    """All-edge, perimeter-weighted diagnostic; nearest geometric point, not best angle.
    Endpoint/nearest-edge ties use the largest orientation residual, never best-Q.
    Independent of ring start/orientation in the continuum; discretization is tested.
    """
    p=np.asarray(p)[:,[0,2]];q=np.asarray(q)[:,[0,2]]
    ep=np.roll(p,-1,axis=0)-p;eq=np.roll(q,-1,axis=0)-q
    lp=np.linalg.norm(ep,axis=1);lq=np.linalg.norm(eq,axis=1)
    if np.any(lp<1e-10) or np.any(lq<1e-10):raise ValueError('zero_edge')
    cum=np.r_[0,np.cumsum(lp)];s=(np.arange(n)+.5)/n*cum[-1]
    idx=np.searchsorted(cum,s,side='right')-1
    sam=p[idx]+((s-cum[idx])/lp[idx])[:,None]*ep[idx]
    vec=sam[:,None,:]-q[None,:,:]
    t=np.clip(np.sum(vec*eq[None,:,:],axis=2)/(lq*lq)[None,:],0,1)
    dist=np.sum((vec-t[:,:,None]*eq[None,:,:])**2,axis=2)
    near=dist<=np.min(dist,axis=1)[:,None]+1e-12
    a=np.rad2deg(np.arctan2(ep[idx,1],ep[idx,0]));b=np.rad2deg(np.arctan2(eq[:,1],eq[:,0]))
    diff=np.abs((a[:,None]-b[None,:]+90)%180-90)
    err=np.max(np.where(near,diff,-1),axis=1)
    return float(np.mean(err**2)),float(np.mean(near.sum(axis=1)>1))

def normal_distance(a,g,n=1024):
    x,ta=_nearest_normal(a['bottom3d'],g['bottom3d'],n)
    y,tg=_nearest_normal(g['bottom3d'],a['bottom3d'],n)
    return dict(N_nearest_deg=float(np.sqrt((x+y)/2)),normal_tie_fraction=(ta+tg)/2)

def ray_profile(g,n=2048):
    """First-positive-hit viewing profile; refuses multihit rings for a main replacement.
    Used only as a diagnostic. Does not overwrite or reorder declared geometry.
    """
    p=np.asarray(g['bottom3d'])[:,[0,2]];e=np.roll(p,-1,axis=0)-p
    angle=(np.arange(n)+.5)*2*np.pi/n
    ray=np.c_[np.sin(angle),-np.cos(angle)]
    den=ray[:,0,None]*e[None,:,1]-ray[:,1,None]*e[None,:,0]
    with np.errstate(divide='ignore',invalid='ignore'):
        t=(p[:,0]*e[:,1]-p[:,1]*e[:,0])[None,:]/den
        u=(p[None,:,0]*ray[:,1,None]-p[None,:,1]*ray[:,0,None])/den
    ok=(t>1e-10)&(u>=-1e-10)&(u<=1+1e-10)&(abs(den)>1e-12)
    dist=np.where(ok,t,np.inf);idx=np.argmin(dist,axis=1);r=dist[np.arange(n),idx]
    hits=np.sort(dist,axis=1)
    multi=np.isfinite(hits[:,1]) & (abs(hits[:,1]-hits[:,0])>1e-7)
    missing=~np.isfinite(r)
    normal=np.rad2deg(np.arctan2(e[idx,1],e[idx,0]))
    y=(.5+np.arctan2(1.,r)/np.pi)*512
    return dict(radius=r,y=y,normal=normal,edge=idx,multihit_fraction=float(multi.mean()),missing_fraction=float(missing.mean()))

def diagnostics(a,g,n=2048):
    pa=profile(a);pg=profile(g);ray_a=ray_profile(a,n);ray_g=ray_profile(g,n)
    dy=abs(ray_a['y']-ray_g['y']);amb=max(ray_a['multihit_fraction'],ray_g['multihit_fraction'],ray_a['missing_fraction'],ray_g['missing_fraction'])
    nr=np.abs((ray_a['normal']-ray_g['normal']+90)%180-90)
    # Quantile alone can ignore a small important feature; include maximum and top10% RMS.
    q=max(1,int(math.ceil(.1*n)));top=np.sort(dy)[-q:]
    same=dict(azimuth_bottom_mean_px=float(dy.mean()),azimuth_bottom_rms_px=float(np.sqrt(np.mean(dy**2))),
              azimuth_bottom_max_px=float(dy.max()),azimuth_bottom_top10_rms_px=float(np.sqrt(np.mean(top**2))),
              ray_ambiguity_fraction=amb,N_ray_deg=float(np.sqrt(np.mean(nr**2))) if amb==0 else None)
    # All declared arcs, not visibility envelope.
    da=sp.spherical_point_to_arcs_distance(sp.sample_spherical_ring(a['bottom3d'],n),g['bottom3d'])*180/np.pi
    dg=sp.spherical_point_to_arcs_distance(sp.sample_spherical_ring(g['bottom3d'],n),a['bottom3d'])*180/np.pi
    dist=np.r_[da,dg];q=max(1,int(math.ceil(.1*len(dist))))
    same.update(spherical_bottom_max_deg=float(dist.max()),spherical_bottom_top10_mean_deg=float(np.sort(dist)[-q:].mean()),
                spherical_bottom_mean_deg=float(dist.mean()))
    return dict(profile=pa,reference_profile=pg,**normal_distance(a,g),**same)

def full_measure(a,g,with_diagnostics=True):
    result=evaluate_geometry(a,g,engine())
    if result['status']=='complete' and with_diagnostics:
        try:result['diagnostics']=diagnostics(a,g)
        except (ValueError,ArithmeticError) as err:result['diagnostic_failure']=type(err).__name__+':'+str(err)
    return result
