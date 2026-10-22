"""Independent geometry-first panorama scores, experimental version GQS-20261016-v2.
No image-based adjudication, registration, angle snapping, or reference selection.
Floor units are camera height h=1. All top heights are measured from explicit vertices.
A: corresponding included angles + bounded multiscale edit loss.
B: translation/rotation/scale-invariant turning-function shape + unregistered IoU.
C: tolerant continuous boundary distance/normal loss + unregistered IoU.
"""
from dataclasses import dataclass, asdict
import numpy as np
from shapely.geometry import Polygon, Point

@dataclass(frozen=True)
class Config:
    version: str = 'GQS-20261016-v2'
    simplify_h: tuple = (.01, .03, .06)
    angle_free_deg: float = 3.
    angle_scale_deg: float = 20.
    angle_penalty_cap: float = 4.
    edit_budget: float = .15
    turning_free_deg: float = 2.
    turning_scale_deg: float = 60.
    placement_free_deg: float = 15.
    placement_zero_deg: float = 45.
    range_power_bc: float = .7
    distance_free_h: float = .03
    distance_scale_h: float = .30
    normal_free_deg: float = 5.
    normal_scale_deg: float = 25.
    tangent_window_h: float = .04
    wall_weight: float = 1.5
    local_free: float = .02
    local_scale: float = .20
    mean_free_ratio: float = 1.05
    mean_scale_ratio: float = 2.
    step_h: float = .01
    min_samples: int = 256
    max_samples: int = 30000

    def __post_init__(self):
        if not self.simplify_h or not all(np.isfinite(x) and x>=0 for x in self.simplify_h):
            raise ValueError('finite nonnegative simplification resolutions required')
        for key in ('angle_scale_deg','angle_penalty_cap','turning_scale_deg','range_power_bc','distance_scale_h','normal_scale_deg','tangent_window_h','local_scale','step_h'):
            if not np.isfinite(getattr(self,key)) or getattr(self,key)<=0:raise ValueError('positive finite '+key+' required')
        for key in ('angle_free_deg','turning_free_deg','distance_free_h','normal_free_deg','wall_weight','local_free'):
            if not np.isfinite(getattr(self,key)) or getattr(self,key)<0:raise ValueError('nonnegative finite '+key+' required')
        if not 0<=self.edit_budget<=1:raise ValueError('edit budget must be in [0,1]')
        if not 0<=self.placement_free_deg<self.placement_zero_deg<=180:raise ValueError('invalid placement tolerance')
        if not 1<=self.mean_free_ratio<self.mean_scale_ratio or not np.isfinite(self.mean_scale_ratio):raise ValueError('invalid global height ratios')
        if not isinstance(self.min_samples,int) or not isinstance(self.max_samples,int) or not 4<=self.min_samples<=self.max_samples:raise ValueError('invalid quadrature sample limits')


def signed_area(p):
    q=np.roll(p,-1,axis=0)
    return float(np.sum(p[:,0]*q[:,1]-p[:,1]*q[:,0])/2)


def canonical(p, values=None):
    p=np.asarray(p,dtype=float)
    if p.ndim!=2 or p.shape[1]!=2 or len(p)<3 or not np.isfinite(p).all():
        raise ValueError('invalid coordinates')
    v=None if values is None else np.asarray(values,dtype=float)
    if v is not None and len(v)!=len(p): raise ValueError('height cardinality')
    if np.linalg.norm(p[-1]-p[0])<1e-12:
        if v is not None and abs(v[-1]-v[0])>1e-10: raise ValueError('conflicting closure heights')
        p=p[:-1]; v=v[:-1] if v is not None else None
    if (np.linalg.norm(np.roll(p,-1,axis=0)-p,axis=1)<1e-12).any():
        raise ValueError('zero length edge; no automatic repair')
    po=Polygon(p)
    if not po.is_valid or po.area<1e-12: raise ValueError('invalid floor polygon')
    if signed_area(p)<0:
        p=p[::-1];v=v[::-1] if v is not None else None
    k=int(np.lexsort((p[:,1],p[:,0]))[0]);p=np.roll(p,-k,axis=0)
    return p if v is None else (p,np.roll(v,-k))


def exact_floor(p):
    p=canonical(p)
    while len(p)>3:
        u=p-np.roll(p,1,axis=0);v=np.roll(p,-1,axis=0)-p
        cross=u[:,0]*v[:,1]-u[:,1]*v[:,0]
        keep=~((abs(cross)<1e-10*np.linalg.norm(u,axis=1)*np.linalg.norm(v,axis=1))&((u*v).sum(1)>0))
        if keep.all():break
        p=p[keep]
    return canonical(p)


def shell(g):
    b=np.asarray(g['bottom3d'],float);t=np.asarray(g['top3d'],float)
    if b.shape!=t.shape or b.ndim!=2 or b.shape[1]!=3: raise ValueError('explicit paired geometry required')
    if not np.isfinite(b).all() or not np.isfinite(t).all():raise ValueError('nonfinite geometry')
    if np.max(abs(b[:,1]+1))>1e-7:raise ValueError('requires normalized common floor y=-1')
    if np.max(abs(b[:,[0,2]]-t[:,[0,2]]))>1e-7:raise ValueError('nonvertical wall pairs')
    h=t[:,1]-b[:,1]
    if min(h)<=0:raise ValueError('nonpositive height')
    p,h=canonical(b[:,[0,2]],h)
    vec=np.roll(p,-1,axis=0)-p;length=np.linalg.norm(vec,axis=1);L=float(sum(length))
    hn=np.roll(h,-1);mu=float(np.dot(length,(h+hn)/2)/L)
    m2=float(np.dot(length,(h*h+h*hn+hn*hn)/3)/L)
    return dict(p=p,h=h,vec=vec,length=length,L=L,cum=np.r_[0,np.cumsum(length)],mu=mu,std=np.sqrt(max(m2-mu*mu,0)))


def from_erp(points):
    z=np.asarray(points,float)
    if z.ndim!=2 or z.shape[1]!=2 or len(z)%2:raise ValueError('unpaired ERP')
    top=z[::2];bot=z[1::2]
    if np.max(abs(top[:,0]-bot[:,0]))>1e-6:raise ValueError('unshared longitude')
    bf=(bot[:,1]/512-.5)*np.pi;bc=(.5-top[:,1]/512)*np.pi
    if np.any(bf<=0) or np.any(bf>=np.pi/2):raise ValueError('invalid floor ray')
    r=1/np.tan(bf);u=bot[:,0]/1024*2*np.pi;x=-r*np.sin(u);zz=r*np.cos(u)
    return dict(bottom3d=np.c_[x,-np.ones(len(x)),zz].tolist(),top3d=np.c_[x,r*np.tan(bc),zz].tolist(),points_1024x512=z.tolist())


def at(s,t):
    t=np.mod(np.asarray(t),s['L']);j=np.searchsorted(s['cum'],t,side='right')-1;j=np.minimum(j,len(s['p'])-1)
    a=(t-s['cum'][j])/s['length'][j]
    return s['p'][j]+a[:,None]*s['vec'][j],s['h'][j]*(1-a)+s['h'][(j+1)%len(s['p'])]*a


def nearest(s,pts):
    delta=pts[:,None,:]-s['p'][None,:,:]
    t=np.clip(np.sum(delta*s['vec'][None,:,:],axis=2)/s['length'][None,:]**2,0,1)
    q=s['p'][None,:,:]+t[:,:,None]*s['vec'][None,:,:]
    dd=np.sum((pts[:,None,:]-q)**2,axis=2);j=np.argmin(dd,axis=1);i=np.arange(len(pts));f=t[i,j]
    return np.sqrt(dd[i,j]),s['cum'][j]+f*s['length'][j],s['h'][j]*(1-f)+s['h'][(j+1)%len(s['p'])]*f


def tangent(s,t,window):
    p1,_=at(s,t-window/2);p2,_=at(s,t+window/2);v=p2-p1;n=np.linalg.norm(v,axis=1)
    # Degenerate smoothing chord: use explicit containing edge, never invent geometry.
    bad=n<1e-10
    if bad.any():
        j=np.minimum(np.searchsorted(s['cum'],np.mod(t,s['L']),side='right')-1,len(s['p'])-1)
        v[bad]=s['vec'][j[bad]];n=np.linalg.norm(v,axis=1)
    return v/n[:,None]


def boundary_height(a,r,cfg):
    data=[]
    for s,t in [(a,r),(r,a)]:
        n=max(cfg.min_samples,int(np.ceil(s['L']/cfg.step_h)))
        if n>cfg.max_samples:raise ValueError('perimeter too long for frozen quadrature')
        ss=(np.arange(n)+.5)*s['L']/n;pts,hh=at(s,ss);d,st,ht=nearest(t,pts)
        va=tangent(s,ss,cfg.tangent_window_h);vb=tangent(t,st,cfg.tangent_window_h)
        ang=np.rad2deg(np.arccos(np.clip(np.sum(va*vb,axis=1),-1,1)))
        ld=np.minimum(np.maximum(d-cfg.distance_free_h,0)/cfg.distance_scale_h,1)**2
        ln=np.minimum(np.maximum(ang-cfg.normal_free_deg,0)/cfg.normal_scale_deg,1)**2
        dh=((hh-s['mu'])-(ht-t['mu']))/r['mu']
        data.append(dict(local2=float(np.mean(dh*dh)),wall=float(np.mean(np.maximum(ld,ln))),
                         distance=float(ld.mean()),normal=float(ln.mean()),normal2=float(np.mean(ang*ang)),dmean=float(d.mean()),step=s['L']/n))
    el=float(np.sqrt(np.mean([x['local2'] for x in data])));em=float(abs(np.log(a['mu']/r['mu'])))
    hl=(max(el-cfg.local_free,0)/cfg.local_scale)**2
    hm=(max(em-np.log(cfg.mean_free_ratio),0)/np.log(cfg.mean_scale_ratio))**2
    return dict(mean_A=a['mu'],mean_R=r['mu'],local_error=el,mean_log_error=em,local_penalty=hl,mean_penalty=hm,
                wall_loss=float(np.mean([x['wall'] for x in data])),normal_loss=float(np.mean([x['normal'] for x in data])),
                distance_loss=float(np.mean([x['distance'] for x in data])),normal_RMS_deg=float(np.sqrt(np.mean([x['normal2'] for x in data]))),
                mean_boundary_distance_h=float(np.mean([x['dmean'] for x in data])),max_step_h=max(x['step'] for x in data))


def rdp_indices(p,eps):
    if len(p)<=2:return [0,len(p)-1]
    v=p[-1]-p[0];v2=float(v@v)
    t=np.clip(((p-p[0])@v)/v2,0,1) if v2>1e-20 else np.zeros(len(p))
    d=np.linalg.norm(p-(p[0]+t[:,None]*v),axis=1);j=int(np.argmax(d))
    if d[j]<=eps:return [0,len(p)-1]
    left=rdp_indices(p[:j+1],eps);right=rdp_indices(p[j:],eps)
    return left[:-1]+[j+i for i in right]


def simplify(p,eps):
    p=exact_floor(p);n=len(p)
    if eps<=0:return p,False
    # Two original, farthest-apart anchors prevent an arbitrary open-curve seam.
    dd=np.sum((p[:,None,:]-p[None,:,:])**2,axis=2);i,j=np.unravel_index(np.argmax(dd),dd.shape)
    if i>j:i,j=j,i
    arc1=list(range(i,j+1));arc2=list(range(j,n))+list(range(0,i+1))
    ids=[arc1[k] for k in rdp_indices(p[arc1],eps)][:-1]+[arc2[k] for k in rdp_indices(p[arc2],eps)][:-1]
    if len(ids)<3 or not Polygon(p[ids]).is_valid:return p,True
    return exact_floor(p[ids]),False


def turns(p):
    v=np.roll(p,-1,axis=0)-p;u=np.roll(v,1,axis=0)
    ang=np.rad2deg(np.arctan2(u[:,0]*v[:,1]-u[:,1]*v[:,0],(u*v).sum(1)))
    length=np.linalg.norm(v,axis=1)
    support=np.minimum(np.minimum(length,np.roll(length,1)),.5)
    return ang,support


def ordered_matching(pa,pr,aa,ar):
    """Maximal sign-compatible cardinality first; position only selects correspondence.
    Cyclic reference offsets; every endpoint is original, no rigid registration.
    """
    na,nr=len(pa),len(pr);best=None
    for shift in range(nr):
        ids=np.roll(np.arange(nr),-shift);rr=pr[ids];ra=ar[ids]
        dp=[[None]*(nr+1) for _ in range(na+1)];dp[0][0]=(0,0.,())
        for i in range(na+1):
            for j in range(nr+1):
                if i==0 and j==0:continue
                options=[]
                if i:options.append(dp[i-1][j])
                if j:options.append(dp[i][j-1])
                if i and j and aa[i-1]*ra[j-1]>0:
                    prev=dp[i-1][j-1]
                    options.append((prev[0]+1,prev[1]+float(np.linalg.norm(pa[i-1]-rr[j-1])),prev[2]+((i-1,int(ids[j-1])),)))
                dp[i][j]=min(options,key=lambda q:(-q[0],round(q[1],12),q[2]))
        cand=dp[-1][-1]
        if best is None or (-cand[0],round(cand[1],12),cand[2])<(-best[0],round(best[1],12),best[2]):best=cand
    return best[2]


def angle_detail(pa,pr,cfg):
    levels=[]
    for eps in cfg.simplify_h:
        a,fa=simplify(pa,eps);r,fr=simplify(pr,eps);aa,wa=turns(a);ar,wr=turns(r)
        pairs=ordered_matching(a,r,aa,ar)
        e=np.array([abs(aa[i]-ar[j]) for i,j in pairs]);w=np.array([min(wa[i],wr[j]) for i,j in pairs])
        if not pairs or sum(w)<=0:raise ValueError('no comparable structural turns')
        xa=np.c_[a[:,0],-np.ones(len(a)),a[:,1]]; xr=np.c_[r[:,0],-np.ones(len(r)),r[:,1]]
        xa/=np.linalg.norm(xa,axis=1)[:,None];xr/=np.linalg.norm(xr,axis=1)[:,None]
        pd=np.array([np.rad2deg(np.arccos(np.clip(xa[i]@xr[j],-1,1))) for i,j in pairs])
        credit=np.clip((cfg.placement_zero_deg-pd)/(cfg.placement_zero_deg-cfg.placement_free_deg),0,1)
        # Position is NOT part of the angle error. Gross misplacement gets only the bounded auxiliary budget.
        place_loss=float(2*np.sum(1-credit)/(len(a)+len(r)))
        pen=float(np.average(np.minimum((np.maximum(e-cfg.angle_free_deg,0)/cfg.angle_scale_deg)**2,cfg.angle_penalty_cap),weights=w))
        levels.append(dict(eps_h=eps,nA=len(a),nR=len(r),matched=len(pairs),precision=len(pairs)/len(a),recall=len(pairs)/len(r),
                           edit=1-2*len(pairs)/(len(a)+len(r)),placement_loss=place_loss,structural_loss=1-2*len(pairs)/(len(a)+len(r))+place_loss,angle_penalty=pen,angle_rms=float(np.sqrt(np.average(e*e,weights=w))),
                           simplification_fallback=bool(fa or fr),pairs=[list(x) for x in pairs]))
    return dict(structural_loss=float(np.mean([x['structural_loss'] for x in levels])),placement_loss=float(np.mean([x['placement_loss'] for x in levels])),angle_penalty=float(np.mean([x['angle_penalty'] for x in levels])),detail_loss=float(np.mean([x['edit'] for x in levels])),
                angle_RMS_deg=float(np.sqrt(np.mean([x['angle_rms']**2 for x in levels]))),event_scales=levels)


def turning_rep(p):
    p=exact_floor(p);v=np.roll(p,-1,axis=0)-p;l=np.linalg.norm(v,axis=1);cum=np.r_[0,np.cumsum(l)/sum(l)]
    increments=np.arctan2(v[:-1,0]*v[1:,1]-v[:-1,1]*v[1:,0],(v[:-1]*v[1:]).sum(1))
    values=np.r_[np.arctan2(v[0,1],v[0,0]),np.arctan2(v[0,1],v[0,0])+np.cumsum(increments)]
    return cum,values


def turning_value(cum,val,x):
    k=np.floor(x);s=x-k;j=np.minimum(np.searchsorted(cum,s,side='right')-1,len(val)-1)
    return val[j]+k*2*np.pi


def turning_distance(pa,pr):
    """Exact piecewise integrals, exhaustive vertex-alignment events (not the fast sweep).
    Between events the mean-centered square loss is concave quadratic in shift;
    an interval minimum lies at its endpoints. Reflection is NOT quotiented out.
    """
    ca,va=turning_rep(pa);cr,vr=turning_rep(pr)
    candidates=np.unique(np.mod((cr[:-1,None]-ca[None,:-1]).ravel(),1))
    best=(np.inf,None,None)
    for shift in candidates:
        br=np.mod(cr[:-1]-shift,1);breaks=np.unique(np.r_[0,ca[1:-1],br,1]);ds=np.diff(breaks);ss=(breaks[:-1]+breaks[1:])/2
        delta=turning_value(ca,va,ss)-turning_value(cr,vr,ss+shift);alpha=float(ds@delta)
        loss=float(ds@((delta-alpha)**2))
        if loss<best[0]:best=(loss,float(shift),alpha)
    return dict(distance_deg=float(np.rad2deg(np.sqrt(max(best[0],0)))),cyclic_shift=best[1],tangent_offset_deg=float(np.rad2deg(best[2])),alignment_events=len(candidates))


def score_pair(ga,gr,cfg=Config()):
    a=shell(ga);r=shell(gr);pa=Polygon(a['p']);pr=Polygon(r['p']);inter=pa.intersection(pr).area;I=float(inter/(pa.area+pr.area-inter))
    b=boundary_height(a,r,cfg);ad=angle_detail(a['p'],r['p'],cfg);tf=turning_distance(a['p'],r['p']);H=b['local_penalty']+b['mean_penalty']
    tp=(max(tf['distance_deg']-cfg.turning_free_deg,0)/cfg.turning_scale_deg)**2
    return dict(I=I,QA=float(100*I*np.exp(-ad['angle_penalty']-H)*(1-cfg.edit_budget*ad['structural_loss'])),
                QB=float(100*I**cfg.range_power_bc*np.exp(-tp-H)),QC=float(100*I**cfg.range_power_bc*np.exp(-cfg.wall_weight*b['wall_loss']-H)),
                turning_penalty=tp,answer_camera_inside=pa.covers(Point(0,0)),reference_camera_inside=pr.covers(Point(0,0)),
                surface_height=b,angle_detail=ad,turning=tf)
