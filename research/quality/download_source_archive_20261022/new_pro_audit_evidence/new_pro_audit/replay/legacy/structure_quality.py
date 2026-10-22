"""RCS-0.2: reference-relative cyclic structural correspondence.
Research prototype, not a validated human-quality scale. No geometry repair,
reference selection, alignment or eligibility decisions are performed here.
Coordinates: x,z in camera-height units; bottom y=-1. All functions are pure.
"""
from __future__ import annotations
from dataclasses import dataclass, asdict
from typing import Any
import numpy as np
from shapely.geometry import Polygon, Point

VERSION = 'RCS-0.2-20261016'
INITIAL_VERSION = 'RCS-0.1-20261016'

@dataclass(frozen=True)
class Config:
    position_free_deg: float = 2.0
    position_zero_deg: float = 6.0
    angle_free_deg: float = 5.0
    angle_zero_deg: float = 30.0
    salience_free_h: float = 0.02
    salience_full_h: float = 0.10
    structure_scale: float = 2.0
    feature_resolution_h: float = 0.0
    same_sign_merge_deg: float = 0.0
    boundary_tolerance_h: float = 0.10
    boundary_step_h: float = 0.005
    # Exact collinearity only. This is a numerical, not perceptual, tolerance.
    numerical_tolerance: float = 1e-10

    def __post_init__(self) -> None:
        vals=asdict(self)
        if not all(np.isfinite(v) for v in vals.values()):raise ValueError('finite configuration required')
        for a,b in [(self.position_free_deg,self.position_zero_deg),(self.angle_free_deg,self.angle_zero_deg),(self.salience_free_h,self.salience_full_h)]:
            if not 0<=a<b:raise ValueError('configuration requires 0 <= free < zero/full')
        if self.structure_scale<0 or self.feature_resolution_h<0 or self.same_sign_merge_deg<0:raise ValueError('nonnegative scale/feature thresholds required')
        if min(self.boundary_tolerance_h,self.boundary_step_h,self.numerical_tolerance)<=0:raise ValueError('positive boundary/numerical resolutions required')


def cross2(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    return a[..., 0] * b[..., 1] - a[..., 1] * b[..., 0]


def valid_ring(points: Any) -> np.ndarray:
    p = np.asarray(points, dtype=np.float64).copy()
    if p.ndim != 2 or p.shape[1] != 2 or len(p) < 3 or not np.isfinite(p).all():
        raise ValueError('finite Nx2 closed-ring vertices, N>=3, required')
    # Repeated final endpoint is a serialization convention, not a new vertex.
    if np.array_equal(p[0], p[-1]):
        p = p[:-1]
    if len(p) < 3 or np.any(np.linalg.norm(np.roll(p,-1,axis=0)-p,axis=1) <= 1e-12):
        raise ValueError('degenerate/repeated consecutive vertex')
    poly = Polygon(p)
    if not poly.is_valid or poly.is_empty or poly.area <= 1e-12:
        raise ValueError('invalid/self-intersecting ring; no repair allowed')
    # Camera containment is reported by the caller, not a new eligibility gate.
    # Out-of-camera polygons still have measurable boundary/structure disagreement.
    return p


def canonical_ring(points: Any, eps: float=1e-10) -> np.ndarray:
    """Same curve, CCW orientation and lexicographic starting point.
    Remove only points lying on their neighbor chord within numerical precision.
    Never snap, smooth, simplify a true turn or apply a spatial transformation.
    """
    p = valid_ring(points)
    if cross2(p, np.roll(p,-1,axis=0)).sum() < 0:
        p = p[::-1]
    while len(p) > 3:
        a, b = np.roll(p,1,axis=0), np.roll(p,-1,axis=0)
        chord = b-a
        lens = np.linalg.norm(chord,axis=1)
        dist = np.abs(cross2(p-a,chord))/np.maximum(lens,1e-300)
        inside = np.sum((p-a)*(p-b),axis=1) <= eps**2
        scale = np.maximum(1., lens)
        ix = np.where((dist <= eps*scale)&inside)[0]
        if len(ix)==0: break
        # Canonical lexicographic tie-break makes cyclic serialization irrelevant.
        k = min(ix, key=lambda i: tuple(p[i]))
        p=np.delete(p,k,axis=0)
    k=np.lexsort((p[:,1],p[:,0]))[0]
    return np.roll(p,-int(k),axis=0)


def bounded_feature_ring(points: Any, tolerance: float=0.03, eps: float=1e-10) -> np.ndarray:
    """Deterministic analysis-copy coarsening; never changes input/global metrics.
    Each retained chord must stay within tolerance of its entire original chain,
    verified against ALL original vertices (not just last removed vertex). The
    distance to a segment is convex, so the bound extends to original segments;
    continuity of projection gives the reverse chord-to-chain bound. Every
    accepted ring stays simple. Surviving vertices are original vertices only.
    This is a measurement resolution, not proof that a feature is unnecessary.
    """
    p=canonical_ring(points,eps)
    if tolerance < 0:raise ValueError('nonnegative resolution required')
    if tolerance==0:return p
    ids=list(range(len(p)))
    while len(ids)>3:
        candidates=[]
        for k,j in enumerate(ids):
            before,after=ids[k-1],ids[(k+1)%len(ids)]
            span=np.arange(before,after if after>before else after+len(p)+0)%len(p)
            span=np.r_[span,after]
            a,b=p[before],p[after];v=b-a
            if np.dot(v,v)<=eps**2:continue
            t=np.clip(((p[span]-a)@v)/np.dot(v,v),0.,1.)
            error=float(np.linalg.norm(p[span]-(a+t[:,None]*v),axis=1).max())
            if error<=tolerance:
                remaining=ids[:k]+ids[k+1:];q=Polygon(p[remaining])
                if q.is_valid and q.area>eps:candidates.append((error,tuple(p[j]),k))
        if not candidates:break
        k=min(candidates)[2];ids.pop(k)
    return canonical_ring(p[ids],eps)


def working_config() -> Config:
    """Ordinary-coarse research version; doorway-specific tuning NOT performed."""
    return Config(position_free_deg=3.,position_zero_deg=10.,angle_free_deg=10.,
                  angle_zero_deg=45.,same_sign_merge_deg=3.,structure_scale=1.5)


def direction_rms(points: Any) -> float:
    """Exact global weighted least-squares distance to an arbitrary 90-degree frame.
    Enumerates wrap intervals, then minimizes each convex quadratic analytically.
    This is intrinsic D, retained for auditing, not used in RCS quality.
    """
    p=valid_ring(points);e=np.roll(p,-1,axis=0)-p
    w=np.linalg.norm(e,axis=1); w=w/w.sum()
    theta=np.degrees(np.arctan2(e[:,1],e[:,0])) % 90.
    cuts=np.unique(np.r_[0.,90.,(theta+45.) % 90.])
    best=np.inf
    for lo,hi in zip(cuts[:-1],cuts[1:]):
        mid=(lo+hi)/2
        unwrapped=mid+(theta-mid+45.)%90.-45.
        axis=np.clip(np.sum(w*unwrapped),lo,hi)
        residual=(theta-axis+45.)%90.-45.
        best=min(best,float(np.sum(w*residual**2)))
    return float(np.sqrt(max(best,0.)))


def floor_iou(a: Any, b: Any) -> float:
    pa,pb=Polygon(valid_ring(a)),Polygon(valid_ring(b))
    inter=pa.intersection(pb).area
    return float(inter/(pa.area+pb.area-inter))


def rays(p: np.ndarray) -> np.ndarray:
    v=np.column_stack((p[:,0],-np.ones(len(p)),p[:,1]))
    return v/np.linalg.norm(v,axis=1)[:,None]


def soft_credit(error: Any, free: float, zero: float) -> np.ndarray:
    if not (0<=free<zero): raise ValueError('need 0 <= free < zero')
    return np.clip((zero-np.asarray(error))/(zero-free),0.,1.)


def corner_features(points: Any, cfg: Config=Config()) -> dict[str,Any]:
    p=bounded_feature_ring(points,cfg.feature_resolution_h,cfg.numerical_tolerance)
    incoming=p-np.roll(p,1,axis=0)
    outgoing=np.roll(p,-1,axis=0)-p
    turns=np.degrees(np.arctan2(cross2(incoming,outgoing),np.sum(incoming*outgoing,axis=1)))
    rr=rays(p)
    angular=np.degrees(np.arctan2(np.linalg.norm(np.cross(rr[:,None],rr[None]),axis=2),rr@rr.T))
    groups=[[i] for i in range(len(p))]
    # A tiny bevel divides one convex turn into nearby same-sign turns. Coalesce
    # that angular event, instead of declaring an important corner missing. No
    # inferred intersection or spatial registration is used; original members kept.
    if cfg.same_sign_merge_deg>0:
        while len(groups)>2:
            options=[]
            for i in range(len(groups)):
                j=(i+1)%len(groups);members=groups[i]+groups[j]
                tt=turns[members]
                if (tt>0).all() or (tt<0).all():
                    diameter=float(angular[np.ix_(members,members)].max())
                    if diameter<=cfg.same_sign_merge_deg and abs(tt.sum())<180.-1e-8:
                        tie=tuple(sorted(tuple(p[k]) for k in members))
                        options.append((diameter,tie,i,j,members))
            if not options:break
            _,_,i,j,members=min(options)
            if j==0:groups=[members]+groups[1:i]
            else:groups=groups[:i]+[members]+groups[j+1:]
    centers=[];turn=[];persist=[]
    for members in groups:
        tt=turns[members];weight=np.abs(tt)
        centers.append(np.average(p[members],axis=0,weights=weight))
        turn.append(tt.sum())
        a,b=p[(members[0]-1)%len(p)],p[(members[-1]+1)%len(p)]
        v=b-a
        if v@v<=1e-20:distance=0.
        else:
            t=np.clip(((p[members]-a)@v)/(v@v),0.,1.)
            distance=float(np.linalg.norm(p[members]-(a+t[:,None]*v),axis=1).max())
        persist.append(distance)
    turn=np.asarray(turn);persistence=np.asarray(persist);centers=np.asarray(centers)
    sal=np.clip((persistence-cfg.salience_free_h)/(cfg.salience_full_h-cfg.salience_free_h),0.,1.)
    weight=sal*np.minimum(1.,np.abs(turn)/90.)
    return {'points':centers,'rays':rays(centers),'turn_deg':turn,'persistence_h':persistence,
            'weight':weight,'members':[list(m) for m in groups],'member_rays':[rr[m] for m in groups],
            'raw_points':p}


def cyclic_match(credit: np.ndarray) -> tuple[float,list[tuple[int,int]]]:
    """Maximum-weight, order-preserving, partial one-to-one matching on two cycles.
    DP all rotations of B, with A fixed. Rotates indices only, NOT room coordinates.
    Zero-credit pairs are not returned. O(n*m*m), suitable for short layout rings.
    """
    c=np.asarray(credit,float)
    if c.ndim!=2 or not np.isfinite(c).all() or (c<0).any():
        raise ValueError('finite nonnegative NxM credits required')
    n,m=c.shape
    best=-1.;pairs=[]
    for shift in range(m):
        ix=(np.arange(m)+shift)%m;z=c[:,ix]
        dp=np.zeros((n+1,m+1));how=np.zeros((n+1,m+1),np.uint8)
        for i in range(1,n+1):
            for j in range(1,m+1):
                choices=(dp[i-1,j],dp[i,j-1],dp[i-1,j-1]+z[i-1,j-1])
                k=int(np.argmax(choices));dp[i,j]=choices[k];how[i,j]=k
        if dp[n,m] > best+1e-12:
            best=float(dp[n,m]);i,j=n,m;pr=[]
            while i>0 and j>0:
                k=how[i,j]
                if k==0:i-=1
                elif k==1:j-=1
                else:
                    if z[i-1,j-1]>0:pr.append((i-1,int(ix[j-1])))
                    i-=1;j-=1
            pairs=pr[::-1]
    return best,pairs


def structure(a: Any,b: Any,cfg: Config=Config()) -> dict[str,Any]:
    fa,fb=corner_features(a,cfg),corner_features(b,cfg)
    # atan2 is stable at zero; arccos(dot) alone produces false self-errors.
    v1=fa['rays'][:,None,:];v2=fb['rays'][None,:,:]
    pos=np.degrees(np.arctan2(np.linalg.norm(np.cross(v1,v2),axis=2),np.sum(v1*v2,axis=2)))
    for i,ra in enumerate(fa['member_rays']):
        for j,rb in enumerate(fb['member_rays']):
            if len(ra)>1 or len(rb)>1:
                dist=np.degrees(np.arctan2(np.linalg.norm(np.cross(ra[:,None],rb[None]),axis=2),ra@rb.T))
                pos[i,j]=max(dist.min(axis=1).max(),dist.min(axis=0).max())
    ang=np.abs(fa['turn_deg'][:,None]-fb['turn_deg'][None,:])
    sign=np.sign(fa['turn_deg'][:,None])==np.sign(fb['turn_deg'][None,:])
    cp=soft_credit(pos,cfg.position_free_deg,cfg.position_zero_deg)
    ca=soft_credit(ang,cfg.angle_free_deg,cfg.angle_zero_deg)*sign
    capacity=np.minimum(fa['weight'][:,None],fb['weight'][None,:])
    mass,pairs=cyclic_match(capacity*cp*ca)
    suma,sumb=float(fa['weight'].sum()),float(fb['weight'].sum())
    if min(suma,sumb)<=1e-9:
        raise ValueError('structure unresolvable at configured scale; not perfect score')
    precision,recall=mass/suma,mass/sumb
    f1=2*mass/(suma+sumb)
    posmass,_=cyclic_match(capacity*cp)
    return dict(C=float(f1),precision=float(precision),recall=float(recall),
                corner_position_C=float(2*posmass/(suma+sumb)),
                matched_mass=float(mass),answer_mass=suma,reference_mass=sumb,
                answer_vertices=len(fa['points']),reference_vertices=len(fb['points']),
                pairs=[dict(answer=i,reference=j,position_deg=float(pos[i,j]),
                            turn_error_deg=float(ang[i,j]),credit=float((capacity*cp*ca)[i,j])) for i,j in pairs],
                answer_features={k:(v.tolist() if isinstance(v,np.ndarray) else v) for k,v in fa.items() if k not in ('rays','member_rays')},
                reference_features={k:(v.tolist() if isinstance(v,np.ndarray) else v) for k,v in fb.items() if k not in ('rays','member_rays')})


def _segment_distances(q: np.ndarray,p: np.ndarray) -> np.ndarray:
    e=np.roll(p,-1,axis=0)-p
    delta=q[:,None,:]-p[None,:,:]
    t=np.clip(np.sum(delta*e[None,:,:],axis=2)/np.sum(e*e,axis=1),0.,1.)
    return np.linalg.norm(delta-t[:,:,None]*e[None,:,:],axis=2).min(axis=1)


def sample_boundary(p: np.ndarray, step: float) -> tuple[np.ndarray,np.ndarray]:
    if step<=0: raise ValueError('positive quadrature step')
    points=[];weights=[]
    for a,b in zip(p,np.roll(p,-1,axis=0)):
        length=np.linalg.norm(b-a);n=max(1,int(np.ceil(length/step)))
        t=(np.arange(n)+.5)/n
        points.append(a+t[:,None]*(b-a));weights.append(np.full(n,length/n))
    return np.concatenate(points),np.concatenate(weights)


def length_dsc(a: Any,b: Any,tau: float=.1,step: float=.005) -> dict[str,float]:
    """2D boundary-length adaptation of Surface DSC, NOT voxel Surface DSC.
    Midpoint quadrature along true segments, exact point-to-segment distances.
    """
    if tau<=0: raise ValueError('positive tolerance required')
    a,b=canonical_ring(a),canonical_ring(b)
    pa,wa=sample_boundary(a,step);pb,wb=sample_boundary(b,step)
    da,db=_segment_distances(pa,b),_segment_distances(pb,a)
    den=wa.sum()+wb.sum()
    return dict(length_dsc=float((wa[da<=tau].sum()+wb[db<=tau].sum())/den),
                boundary_mean_h=float((np.sum(wa*da)+np.sum(wb*db))/den),
                answer_within=float(wa[da<=tau].sum()/wa.sum()),reference_within=float(wb[db<=tau].sum()/wb.sum()))


def boundary_iou(a: Any,b: Any,tau: float=.1) -> float:
    """Continuous planar inner-band Boundary IoU analogue; no raster scaling."""
    if tau<=0: raise ValueError('positive tolerance required')
    p,q=Polygon(valid_ring(a)),Polygon(valid_ring(b))
    # Polygonal mitred inward offset explicitly frozen; no repairs to originals.
    bp=p.difference(p.buffer(-tau,join_style=2));bq=q.difference(q.buffer(-tau,join_style=2))
    inter=bp.intersection(bq).area;union=bp.area+bq.area-inter
    if union<=0:raise ValueError('empty bands')
    return float(inter/union)


def mean_height(geom: dict[str,Any]) -> float:
    b,t=np.asarray(geom['bottom3d'],float),np.asarray(geom['top3d'],float)
    if b.shape!=t.shape or not np.allclose(b[:,[0,2]],t[:,[0,2]],atol=1e-10,rtol=0):
        raise ValueError('vertical paired columns required')
    if np.array_equal(b[0],b[-1]):
        if not np.array_equal(t[0],t[-1]):raise ValueError('closure endpoint height mismatch')
        b,t=b[:-1],t[:-1]
    p=valid_ring(b[:,[0,2]])
    h=t[:,1]-b[:,1]
    if (h<=0).any() or not np.isfinite(h).all():raise ValueError('positive complete heights required')
    w=np.linalg.norm(np.roll(p,-1,axis=0)-p,axis=1)
    return float(np.sum(w*(h+np.roll(h,-1))/2)/w.sum())


def old_score(I: Any,Sb: Any,D: Any,Hm: Any,Hc: Any,model: str='B8L2') -> np.ndarray:
    I,Sb,D,Hm,Hc=np.broadcast_arrays(*[np.asarray(v,float) for v in (I,Sb,D,Hm,Hc)])
    if not all(np.isfinite(v).all() for v in (I,Sb,D,Hm,Hc)) or (I<0).any() or (I>1+1e-12).any() or any((v<0).any() for v in (Sb,D,Hm,Hc)):
        raise ValueError('all complete finite in-domain components required; no zero imputation')
    c={'WQ':np.sqrt(37.5),'A10':10.,'S8':8.,'B8L2':8.,'noD':8.}[model]
    d=1.5*D*D/(D*D+c*c)
    fscaled=1-I+I*Sb*Sb/32.
    h=(Hm/.8)**2+(Hc/.25)**2
    if model=='B8L2':m=np.hypot(fscaled,I*d)
    elif model=='noD':m=fscaled
    else:m=fscaled+I*d
    return 100*I/(I+m+I*h)


def candidate_score(I: float,Sb: float,Hm: float,Hc: float,C: float,
                    cfg: Config=Config(),pool: str='l2',keep_bottom: bool=True) -> float:
    # Heights are supplied frozen metrics; their provenance must be recorded by caller.
    vals=np.array([I,Sb,Hm,Hc,C],float)
    if not np.isfinite(vals).all() or not 0<=I<=1+1e-12 or not 0<=C<=1+1e-12 or min(Sb,Hm,Hc)<0:
        raise ValueError('complete in-domain metrics required')
    if I==0:return 0.
    f=(1-I)/I+(Sb*Sb/32. if keep_bottom else 0.)
    s=cfg.structure_scale*(1-C)
    if pool=='l2':burden=np.hypot(f,s)
    elif pool=='sum':burden=f+s
    elif pool=='max':burden=max(f,s)
    else:raise ValueError('unknown pooling')
    h=(Hm/.8)**2+(Hc/.25)**2
    return float(100/(1+burden+h))
