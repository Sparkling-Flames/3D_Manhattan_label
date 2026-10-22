"""EBC-1: fixed-envelope, length-weighted oriented boundary coverage.

This is NOT a physical-wall detector, vertex F1, Surface DSC, or learned human
score. All closed target edges, including protocol cuts, define the envelope.
Source coordinates and reference identity are never changed. Simplification is
limited to exact 3D-equivalent redundant vertices in a temporary computation view.

The two directed integrals use edge-wise quadrature, finite-segment projection,
and scalar max/min over *all* candidate segments; no index-based correspondence.
Heights retain the earlier perimeter-centred nearest-footprint family and its
conservative max-residual tie rule, with order-invariant edge-wise quadrature.
"""
from __future__ import annotations
from dataclasses import dataclass,asdict
import numpy as np
from shapely.geometry import Polygon,Point
from shapely.validation import explain_validity

@dataclass(frozen=True)
class Config:
    version:str='EBC1_working_20261016'
    position_free_h:float=.03
    position_scale_h:float=.30
    normal_free_deg:float=5.
    normal_scale_deg:float=25.
    tangent_window_h:float=.08
    step_h:float=.02
    boundary_weight:float=1.
    mean_scale:float=.8
    local_scale:float=.25
    max_samples:int=40000
    def validate(self):
        for k in ['position_scale_h','normal_scale_deg','tangent_window_h','step_h','mean_scale','local_scale']:
            if not np.isfinite(getattr(self,k)) or getattr(self,k)<=0:raise ValueError('invalid_config:'+k)
        for k in ['position_free_h','normal_free_deg','boundary_weight']:
            if not np.isfinite(getattr(self,k)) or getattr(self,k)<0:raise ValueError('invalid_config:'+k)
        if self.max_samples<4:raise ValueError('invalid_max_samples')
        return self

def configurations():
    return [Config(),Config(version='EBC1_strict',position_free_h=.02,position_scale_h=.15,normal_free_deg=3.,normal_scale_deg=15.,tangent_window_h=.06),Config(version='EBC1_soft',position_free_h=.05,position_scale_h=.5,normal_free_deg=7.,normal_scale_deg=35.,tangent_window_h=.12)]

def area_signed(p):
    q=p-p[0];r=np.roll(q,-1,axis=0)
    return float(np.sum(q[:,0]*r[:,1]-q[:,1]*r[:,0])/2)

def shell(g):
    b=np.asarray(g.get('bottom3d'),float);t=np.asarray(g.get('top3d'),float)
    if b.ndim!=2 or b.shape[1:]!=(3,) or b.shape!=t.shape or len(b)<3:raise ValueError('missing_or_unpaired_geometry')
    if not np.isfinite(b).all() or not np.isfinite(t).all():raise ValueError('nonfinite_geometry')
    if np.max(abs(b[:,1]+1))>1e-7:raise ValueError('not_common_normalized_floor_minus1')
    if np.max(abs(b[:,[0,2]]-t[:,[0,2]]))>1e-7:raise ValueError('nonvertical_pair_geometry')
    p=b[:,[0,2]].copy();h=t[:,1]-b[:,1]
    if np.min(h)<=0:raise ValueError('nonpositive_wall_height')
    # Exact closure encoding is not a new polygon vertex.
    if np.array_equal(p[0],p[-1]):
        if abs(h[0]-h[-1])>1e-12:raise ValueError('conflicting_duplicate_closure')
        p=p[:-1];h=h[:-1]
    if np.any(np.linalg.norm(np.roll(p,-1,axis=0)-p,axis=1)<1e-12):raise ValueError('zero_length_edge')
    poly=Polygon(p)
    if not poly.is_valid or poly.area<=1e-12:raise ValueError('invalid_polygon:'+explain_validity(poly))
    # Full 3D redundancy only. Top peaks on a straight bottom are retained.
    removed=0
    while len(p)>3:
        u=p-np.roll(p,1,axis=0);v=np.roll(p,-1,axis=0)-p
        lu=np.linalg.norm(u,axis=1);lv=np.linalg.norm(v,axis=1)
        straight=(abs(u[:,0]*v[:,1]-u[:,1]*v[:,0]) <= 1e-12*lu*lv)&((u*v).sum(1)>0)
        alpha=lu/(lu+lv);expected=(1-alpha)*np.roll(h,1)+alpha*np.roll(h,-1)
        drop=straight & (abs(h-expected)<=1e-12*np.maximum(1,np.max(abs(h))))
        if not drop.any():break
        # One redundant point at a time preserves the represented polyline.
        j=int(np.flatnonzero(drop)[0]);p=np.delete(p,j,0);h=np.delete(h,j);removed+=1
    if area_signed(p)<0:p=p[::-1];h=h[::-1]
    e=np.roll(p,-1,axis=0)-p;l=np.linalg.norm(e,axis=1);L=float(l.sum())
    mu=float(np.dot(l,(h+np.roll(h,-1))/2)/L)
    return dict(p=p,h=h,e=e,l=l,L=L,cum=np.r_[0,np.cumsum(l)],mu=mu,poly=poly,camera_inside=poly.covers(Point(0,0)),removed_3d_redundant=removed)

def at(s,u):
    u=np.mod(np.asarray(u,float),s['L']);shape=u.shape;x=u.ravel()
    j=np.minimum(np.searchsorted(s['cum'],x,side='right')-1,len(s['p'])-1)
    t=(x-s['cum'][j])/s['l'][j]
    p=s['p'][j]+t[:,None]*s['e'][j]
    h=s['h'][j]+t*(np.roll(s['h'],-1)[j]-s['h'][j])
    return p.reshape(shape+(2,)),h.reshape(shape)

def tangent(s,u,window):
    # Fixed physical support, capped only to avoid traversing a tiny loop twice.
    window=min(window,s['L']/4)
    a,_=at(s,u-window/2);b,_=at(s,u+window/2);v=b-a
    n=np.linalg.norm(v,axis=-1);bad=n<1e-12
    if bad.any():
        x=np.mod(np.asarray(u),s['L']);j=np.minimum(np.searchsorted(s['cum'],x,side='right')-1,len(s['p'])-1)
        v[bad]=s['e'][j[bad]];n[bad]=s['l'][j[bad]]
    return v/n[...,None],int(np.sum(bad))

def samples(s,c):
    ns=np.maximum(1,np.ceil(s['l']/c.step_h-1e-10).astype(int))
    if int(ns.sum())>c.max_samples:raise ValueError('quadrature_budget_exceeded')
    pos=[];hei=[];arc=[];weights=[];edgeidx=[]
    for i,n in enumerate(ns):
        u=(np.arange(n)+.5)/n
        pos.append(s['p'][i]+u[:,None]*s['e'][i]);hei.append(s['h'][i]+u*(s['h'][(i+1)%len(s['h'])]-s['h'][i]));arc.append(s['cum'][i]+u*s['l'][i]);weights.append(np.full(n,s['l'][i]/n));edgeidx.append(np.full(n,i))
    return np.vstack(pos),np.concatenate(hei),np.concatenate(arc),np.concatenate(weights),np.concatenate(edgeidx)

def directed(a,b,c,detail=False):
    p,hh,arc,weights,idx=samples(a,c);ta,ba=tangent(a,arc,c.tangent_window_h)
    # Shared origin keeps arithmetic tie tolerance translation-independent.
    pp=p-a['p'][0];qq=b['p']-a['p'][0]
    delta=pp[:,None,:]-qq[None,:,:]
    u=np.clip(np.sum(delta*b['e'][None,:,:],axis=2)/(b['l'][None,:]**2),0,1)
    d2=np.sum((delta-u[:,:,None]*b['e'][None,:,:])**2,axis=2)
    arc_b=b['cum'][:-1][None,:]+u*b['l'][None,:]
    tb,bb=tangent(b,arc_b,c.tangent_window_h)
    dot=np.clip(np.sum(ta[:,None,:]*tb,axis=2),-1,1)
    theta=np.degrees(np.arccos(dot))
    cp=(np.maximum(np.sqrt(d2)-c.position_free_h,0)/c.position_scale_h)**2
    cn=(np.maximum(theta-c.normal_free_deg,0)/c.normal_scale_deg)**2
    credit=(1/(1+cp+cn)).max(axis=1)
    positional=(1/(1+cp)).max(axis=1)
    # Conservative, order-independent statistic over all equally closest floor
    # projections; scalar extrema do not break ties using the polygon start.
    hbt=b['h'][None,:]+u*(np.roll(b['h'],-1)-b['h'])[None,:]
    residual=(hh[:,None]-a['mu'])-(hbt-b['mu'])
    nearest=d2.min(axis=1)
    roundoff=128*np.finfo(float).eps*max(1,float(np.max(np.sum(pp*pp,axis=1))),float(np.max(np.sum(qq*qq,axis=1))))
    tie=d2<=nearest[:,None]+roundoff
    local2=np.max(np.where(tie,residual*residual,-np.inf),axis=1)
    local2min=np.min(np.where(tie,residual*residual,np.inf),axis=1)
    hi=np.max(np.where(tie,hbt,-np.inf),axis=1);lo=np.min(np.where(tie,hbt,np.inf),axis=1)
    r=dict(credit_integral=float(weights@credit),position_integral=float(weights@positional),local_mse=float(weights@local2/a['L']),local_mse_lower=float(weights@local2min/a['L']),height_tie_fraction=float(weights@(hi-lo>1e-10)/a['L']),distance_mean_h=float(weights@np.sqrt(nearest)/a['L']),samples=len(p),degenerate_tangent_evaluations=ba+bb)
    if detail:r.update(points=p.tolist(),credit=credit.tolist(),position_credit=positional.tolist(),sample_weights=weights.tolist(),edge_indices=idx.tolist())
    return r

def combine(I,C,Hmean,Hcenter,c=Config(),pool='sum',range_weight=1.):
    if I<=0 or C<=0:return 0.
    area=1/I-1;boundary=c.boundary_weight*(1/C-1)
    if pool=='sum':ge=range_weight*area+boundary
    elif pool=='l2':ge=float(np.hypot(range_weight*area,boundary))
    elif pool=='max':ge=max(range_weight*area,boundary)
    else:raise ValueError('unknown_pool')
    H=(Hmean/c.mean_scale)**2+(Hcenter/c.local_scale)**2
    return float(100/(1+ge+H))

def measure_pair(answer,reference,c=Config(),detail=False):
    c.validate()
    try:a=shell(answer)
    except (ValueError,TypeError) as e:return dict(status='not_evaluable',reason='answer:'+str(e),score=None)
    try:b=shell(reference)
    except (ValueError,TypeError) as e:return dict(status='not_evaluable',reason='reference:'+str(e),score=None)
    try:
        inter=a['poly'].intersection(b['poly']).area;union=a['poly'].union(b['poly']).area;I=float(inter/union)
        ag=directed(a,b,c,detail);ga=directed(b,a,c,detail)
    except (ValueError,ArithmeticError) as e:return dict(status='not_evaluable',reason='measurement:'+str(e),score=None)
    C=(ag['credit_integral']+ga['credit_integral'])/(a['L']+b['L']);C=float(np.clip(C,0,1))
    Cpos=float(np.clip((ag['position_integral']+ga['position_integral'])/(a['L']+b['L']),0,1))
    Hm=abs(a['mu']/b['mu']-1);Hc=np.sqrt((ag['local_mse']+ga['local_mse'])/2)/b['mu']
    Hclo=np.sqrt((ag['local_mse_lower']+ga['local_mse_lower'])/2)/b['mu']
    out=dict(status='complete',version=c.version,I=I,boundary_coverage=C,position_only_coverage=Cpos,answer_boundary_credit=ag['credit_integral']/a['L'],reference_boundary_credit=ga['credit_integral']/b['L'],Hmean=float(Hm),Hcenter=float(Hc),Hcenter_tie_lower=float(Hclo),answer_camera_inside=a['camera_inside'],reference_camera_inside=b['camera_inside'],height_tie_fraction_AG=ag['height_tie_fraction'],height_tie_fraction_GA=ga['height_tie_fraction'],removed_3d_redundant_A=a['removed_3d_redundant'],removed_3d_redundant_R=b['removed_3d_redundant'],score=combine(I,C,Hm,Hc,c),score_no_normals=combine(I,Cpos,Hm,Hc,c),score_l2=combine(I,C,Hm,Hc,c,pool='l2'),score_range_only=combine(I,1,Hm,Hc,c),samples_AG=ag['samples'],samples_GA=ga['samples'],distance_mean_AG=ag['distance_mean_h'],distance_mean_GA=ga['distance_mean_h'])
    if detail:out.update(AG=ag,GA=ga)
    return out

@dataclass(frozen=True)
class NormalizedConfig:
    version:str='EBC2_reference_scale_20261016'
    position_free_side:float=.01
    position_scale_side:float=.10
    normal_free_deg:float=5.
    normal_scale_deg:float=25.
    tangent_window_side:float=.02
    step_side:float=.0025
    boundary_weight:float=1.

def normalized_pair(answer,reference,c=NormalizedConfig(),detail=False):
    """Same boundary measurement, with frozen sqrt(reference footprint area) units.
    This changes normalization, not the reference or its geometry. It does not
    align the answer to the reference. Area and position remain in original frame.
    """
    try:s=shell(reference);scale=float(np.sqrt(s['poly'].area))
    except (ValueError,TypeError) as e:return dict(status='not_evaluable',score=None,reason='reference:'+str(e))
    cfg=Config(version=c.version,position_free_h=c.position_free_side*scale,position_scale_h=c.position_scale_side*scale,normal_free_deg=c.normal_free_deg,normal_scale_deg=c.normal_scale_deg,tangent_window_h=c.tangent_window_side*scale,step_h=c.step_side*scale,boundary_weight=c.boundary_weight)
    r=measure_pair(answer,reference,cfg,detail);r['reference_size_h']=scale
    return r
