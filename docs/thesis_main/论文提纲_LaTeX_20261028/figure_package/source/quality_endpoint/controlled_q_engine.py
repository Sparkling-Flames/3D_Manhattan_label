"""Eight deterministic geometry experiments comparing frozen B8L2 and mean-prism IoU.

Independent numerical implementation of the equations in the supplied manuscript
and inspected repository functions; NOT a full run of the repository's scorer.
No rating data, parameter fitting, or hypothesis-directed selection is performed.
Units: metres. Camera at origin, floor y=-1.6m, wall height normally 3m.
Dependencies: numpy, pandas, shapely. Run: python run_cases.py
"""
from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
import json
import math
import numpy as np
import pandas as pd
from shapely.geometry import Polygon, Point

OUT = Path(__file__).resolve().parent
CAMERA_HEIGHT = 1.6
HEIGHT = 3.0

@dataclass
class Layout:
    xz: np.ndarray
    heights: np.ndarray
    def __post_init__(self):
        self.xz = np.asarray(self.xz, dtype=float)
        self.heights = np.broadcast_to(np.asarray(self.heights,dtype=float),(len(self.xz),)).copy()
        assert self.xz.shape == (len(self.heights),2)
        assert np.isfinite(self.xz).all() and np.isfinite(self.heights).all()
        assert (self.heights > CAMERA_HEIGHT).all(), 'all test ceilings above camera'
        assert np.all(np.linalg.norm(np.roll(self.xz,-1,axis=0)-self.xz,axis=1)>1e-10)
        p = Polygon(self.xz)
        assert p.is_valid and p.area > 0 and p.contains(Point(0,0))
    @property
    def bottom(self):
        return np.column_stack((self.xz[:,0],np.full(len(self.xz),-CAMERA_HEIGHT),self.xz[:,1]))
    def data(self):
        return {'floor_xz_m':self.xz.tolist(),'wall_heights_m':self.heights.tolist()}


def unit(v):
    v=np.asarray(v,dtype=float)
    return v/np.linalg.norm(v,axis=-1,keepdims=True)


def spherical_arc_basis(ring):
    a=unit(ring); b=np.roll(a,-1,axis=0)
    cross=np.cross(a,b); sine=np.linalg.norm(cross,axis=1)
    length=np.arctan2(sine,np.sum(a*b,axis=1))
    if np.any(length<1e-12) or np.any(np.pi-length<1e-10):
        raise ValueError('zero or antipodal angular edge')
    normal=cross/sine[:,None]; tangent=np.cross(normal,a)
    return a,b,tangent,normal,length


def spherical_samples(ring,n):
    a,b,tangent,normal,length=spherical_arc_basis(ring)
    cum=np.r_[0.,np.cumsum(length)]
    s=(np.arange(n)+.5)*cum[-1]/n
    i=np.searchsorted(cum,s,side='right')-1
    angle=s-cum[i]
    return a[i]*np.cos(angle)[:,None]+tangent[i]*np.sin(angle)[:,None]


def spherical_directed(src,tgt,n):
    p=spherical_samples(src,n)
    a,b,tangent,normal,length=spherical_arc_basis(tgt)
    x=p@a.T; y=p@tangent.T
    phase=np.arctan2(y,x)
    inside=(phase>=-1e-12)&(phase<=length[None,:]+1e-12)
    arc=np.arctan2(np.abs(p@normal.T),np.hypot(x,y))
    ea=np.arctan2(np.linalg.norm(np.cross(p[:,None,:],a[None,:,:]),axis=-1),x)
    eb=np.arctan2(np.linalg.norm(np.cross(p[:,None,:],b[None,:,:]),axis=-1),p@b.T)
    return np.where(inside,arc,np.minimum(ea,eb)).min(axis=1).mean()


def boundary_angle(P,R,n=2048):
    return np.degrees((spherical_directed(P.bottom,R.bottom,n)+spherical_directed(R.bottom,P.bottom,n))/2)


def direction_residual(P):
    e=np.roll(P.xz,-1,axis=0)-P.xz
    w=np.linalg.norm(e,axis=1)
    alpha=np.degrees(np.arctan2(e[:,1],e[:,0]))%90
    wrap=lambda x:(x+45)%90-45
    # Weighted squared wrapped distance is quadratic on each interval.
    breaks=np.unique(np.r_[0.,(alpha+45)%90,90.])
    choices=[0.,90.]
    for lo,hi in zip(breaks[:-1],breaks[1:]):
        mid=(lo+hi)/2
        unwrapped=mid+wrap(alpha-mid)
        optimum=np.dot(w,unwrapped)/w.sum()
        choices.append(float(np.clip(optimum,lo,hi)))
    return float(np.sqrt(min(np.dot(w,wrap(alpha-phi)**2)/w.sum() for phi in choices)))


def height_moments(P):
    ell=np.linalg.norm(np.roll(P.xz,-1,axis=0)-P.xz,axis=1)
    h=P.heights; hn=np.roll(h,-1)
    mean=float(np.dot(ell,(h+hn)/2)/ell.sum())
    d=h-mean; dn=np.roll(d,-1)
    variance=float(np.dot(ell,(d*d+d*dn+dn*dn)/3)/ell.sum())
    return mean,max(0.,variance)


def floor_samples(P,n):
    e=np.roll(P.xz,-1,axis=0)-P.xz
    ell=np.linalg.norm(e,axis=1)
    cum=np.r_[0.,np.cumsum(ell)]
    s=(np.arange(n)+.5)*cum[-1]/n
    i=np.searchsorted(cum,s,side='right')-1
    u=(s-cum[i])/ell[i]
    return P.xz[i]+u[:,None]*e[i],P.heights[i]+u*(np.roll(P.heights,-1)[i]-P.heights[i])


def directed_height(P,R,n,shiftP=0.,shiftR=0.):
    x,ph=floor_samples(P,n); ph=ph+shiftP
    q=R.xz; e=np.roll(q,-1,axis=0)-q
    vec=x[:,None,:]-q[None,:,:]
    u=np.clip(np.sum(vec*e[None,:,:],axis=2)/np.sum(e*e,axis=1)[None,:],0,1)
    d2=np.sum((vec-u[:,:,None]*e[None,:,:])**2,axis=2)
    tol=64*np.finfo(float).eps*max(1.,float(np.abs(x).max())**2,float(np.abs(q).max())**2)
    tied=d2<=d2.min(axis=1)[:,None]+tol
    rh=R.heights[None,:]+u*(np.roll(R.heights,-1)-R.heights)[None,:]+shiftR
    sq=(ph[:,None]-rh)**2
    return float(np.max(np.where(tied,sq,-np.inf),axis=1).mean())


def score(P,R,nb=2048,nh=4096):
    p=Polygon(P.xz);r=Polygon(R.xz)
    ai=p.intersection(r).area
    i=ai/(p.area+r.area-ai)
    mp,vp=height_moments(P); mr,vr=height_moments(R)
    hm=abs(mp-mr)/mr
    delta=mp-mr
    hc=math.sqrt((directed_height(P,R,nh,-delta,0.)+directed_height(R,P,nh,0.,-delta))/2)/mr
    sb=float(boundary_angle(P,R,nb)); d=direction_residual(P)
    F=(1/i-1)+sb*sb/32 if i>0 else math.inf
    loss_d=1.5*d*d/(d*d+8*8)
    H=(hm/.8)**2+(hc/.25)**2
    Q=100/(1+math.hypot(F,loss_d)+H) if i>0 else 0.
    D10=100/(1+math.hypot(F,1.5*d*d/(d*d+100))+H) if i>0 else 0.
    cp=float(P.heights.mean());cr=float(R.heights.mean())
    inter=ai*min(cp,cr)
    prism=inter/(p.area*cp+r.area*cr-inter)
    interw=ai*min(mp,mr)
    weighted=interw/(p.area*mp+r.area*mr-interw)
    return dict(iou2d100=100*i,prism_iou100=100*prism,Q=Q,D10=D10,Sb_deg=sb,Ddir_deg=d,
                Hmean=hm,Hcenter=hc,weighted_prism_iou100=100*weighted,
                candidate_mean_corner_height_m=cp,candidate_perimeter_mean_height_m=mp,
                reference_mean_corner_height_m=cr,reference_perimeter_mean_height_m=mr,
                candidate_height_sd_m=math.sqrt(vp),candidate_floor_area_m2=p.area,reference_floor_area_m2=r.area,
                max_floor_displacement_m=p.boundary.hausdorff_distance(r.boundary),
                candidate_nodes=len(P.xz),reference_nodes=len(R.xz),
                candidate_height_range_m=float(np.ptp(P.heights)))


def square(): return np.array([[-2.,-2.],[2.,-2.],[2.,2.],[-2.,2.]])
def rectangle(x0,x1,z0,z1):return np.array([[x0,z0],[x1,z0],[x1,z1],[x0,z1]],float)
def flat(q):return Layout(q,HEIGHT)
def shear(q,s):
    p=q.copy();p[:,0]+=s*p[:,1];return p

def designs():
    R=flat(square()); jobs=[]
    def add(cid,variant,amount,P,ref=R,**meta):
        jobs.append(dict(case=cid,variant=variant,amount=amount,P=P,R=ref,meta=meta))
    for a in [0.,.02,.05,.1,.2,.4]:
        add('C1','uniform_height',a,Layout(square(),HEIGHT*(1+a)),
            height_error_m=HEIGHT*a)
    for a in [0.,.02,.05,.1,.2,.4]:
        h=HEIGHT*(1+a*square()[:,0]/2)
        add('C2','balanced_tilt',a,Layout(square(),h),
            max_height_error_m=HEIGHT*a,actual_planar_volume_iou100=100*(1-a/4)/(1+a/4))
    for a in [0.,.05,.1,.2,.4,.8]:
        h=np.full(4,HEIGHT);h[0]+=HEIGHT*a
        add('C3','single_corner',a,Layout(square(),h),max_height_error_m=HEIGHT*a)
        add('C3','uniform_equal_corner_mean',a,Layout(square(),HEIGHT*(1+a/4)),max_height_error_m=HEIGHT*a/4)
    # Geometry is fixed. Insert collinear paired vertices on the high wall only.
    q=square();h=HEIGHT*(1+.2*q[:,0]/2)
    for m in [0,1,4,12]:
        qn=[q[0],q[1]];hn=[h[0],h[1]]
        for t in np.linspace(0,1,m+2)[1:-1]:
            qn.append((1-t)*q[1]+t*q[2]);hn.append((1-t)*h[1]+t*h[2])
        qn.extend([q[2],q[3]]);hn.extend([h[2],h[3]])
        add('C4','same_geometry_resegmented',m,Layout(np.array(qn),np.array(hn)),
            max_height_error_m=.6,actual_planar_volume_iou100=100*(1-.2/4)/(1+.2/4))
    for s in [0.,.02,.05,.1,.2,.3]:
        add('C5','shear',s,flat(shear(square(),s)),max_reference_corner_displacement_m=2*s,
            adjacent_wall_angle_error_deg=float(np.degrees(np.arctan(s))))
        add('C5','translation_equal_iou',s,flat(square()+np.array([s,0.])),max_reference_corner_displacement_m=s,
            adjacent_wall_angle_error_deg=0.)
    q=rectangle(-.8,7.2,-2.,2.);ref=flat(q)
    for d in [0.,.05,.1,.2,.4,.8]:
        add('C6','near_wall_outward',d,flat(rectangle(-.8-d,7.2,-2.,2.)),ref=ref,wall_displacement_m=d)
        add('C6','far_wall_outward',d,flat(rectangle(-.8,7.2+d,-2.,2.)),ref=ref,wall_displacement_m=d)
    for depth in [.1,.3,.6,1.2]:
        width=.4
        # True reference has a narrow outward alcove on the north wall.
        q=np.array([[-2,-2],[2,-2],[2,2],[width/2,2],[width/2,2+depth],[-width/2,2+depth],[-width/2,2],[-2,2]],float)
        add('C7','omitted_alcove',depth,flat(square()),ref=flat(q),
            omitted_floor_area_m2=width*depth,omitted_effective_turns=4,max_missing_depth_m=depth)
    for s in [0.,.05,.1,.3,.5]:
        ref=flat(shear(square(),s))
        add('C8','exact_non_manhattan',s,flat(shear(square(),s)),ref=ref,
            scope='OOS diagnostic; mechanically evaluated Q is NOT a formal in-scope quality score')
        add('C8','orthogonal_approximation',s,flat(square()),ref=ref,
            scope='OOS diagnostic; mechanically evaluated Q is NOT a formal in-scope quality score')
    return jobs


def main():
    jobs=designs();rows=[];coords=[]
    for j in jobs:
        m=score(j['P'],j['R'])
        rows.append(dict(case=j['case'],variant=j['variant'],amount=j['amount'],**j['meta'],**m))
        coords.append(dict(case=j['case'],variant=j['variant'],amount=j['amount'],metadata=j['meta'],
                           candidate=j['P'].data(),reference=j['R'].data()))
    frame=pd.DataFrame(rows)
    frame.to_csv(OUT/'results_all.csv',index=False,encoding='utf-8-sig')
    (OUT/'geometries.json').write_text(json.dumps(coords,indent=2,ensure_ascii=False),encoding='utf-8')
    # Verify analytic properties independently of the numerical boundary/height sampler.
    checks={}
    zero=score(flat(square()),flat(square()))
    checks['identical_manhattan_Q_error']=abs(zero['Q']-100)
    c1=frame[frame.case.eq('C1')]
    checks['global_height_prism_analytic_max_error']=float(np.max(np.abs(c1.prism_iou100-100/(1+c1.amount))))
    c2=frame[frame.case.eq('C2')]
    checks['balanced_tilt_hc_analytic_max_error']=float(np.max(np.abs(c2.Hcenter-c2.amount*np.sqrt(2/3))))
    checks['balanced_tilt_prism_max_error']=float(np.max(np.abs(c2.prism_iou100-100)))
    checks['replicates_manuscript_20pct_Q']=float(c2.loc[np.isclose(c2.amount,.2),'Q'].iloc[0])
    c4=frame[frame.case.eq('C4')]
    checks['resegmentation_Q_range']=float(np.ptp(c4.Q))
    c5=frame[frame.case.eq('C5')].pivot(index='amount',columns='variant',values='prism_iou100')
    checks['matched_shear_translation_iou_max_difference']=float(np.max(abs(c5['shear']-c5['translation_equal_iou'])))
    c6=frame[frame.case.eq('C6')].pivot(index='amount',columns='variant',values='prism_iou100')
    checks['matched_near_far_iou_max_difference']=float(np.max(abs(c6['near_wall_outward']-c6['far_wall_outward'])))
    # Report numerical sampling convergence: fixed published n vs 4x n.
    conv=[]
    for j in jobs:
        hi=score(j['P'],j['R'],8192,16384)
        low=frame[(frame.case==j['case'])&(frame.variant==j['variant'])&(frame.amount==j['amount'])].iloc[0]
        conv.append({'case':j['case'],'variant':j['variant'],'amount':j['amount'],
                     'abs_Q_difference':abs(hi['Q']-low.Q),'abs_Sb_difference_deg':abs(hi['Sb_deg']-low.Sb_deg),
                     'abs_Hcenter_difference':abs(hi['Hcenter']-low.Hcenter)})
    cv=pd.DataFrame(conv);cv.to_csv(OUT/'sampling_convergence.csv',index=False)
    checks['fourfold_samples_max_Q_difference']=float(cv.abs_Q_difference.max())
    checks['fourfold_samples_max_Sb_difference_deg']=float(cv.abs_Sb_difference_deg.max())
    # Coordinate-transform invariances on a nontrivial candidate, both transformed.
    R=flat(square()); P=flat(shear(square(),.1)); base=score(P,R)
    ang=1.13;rot=np.array([[np.cos(ang),-np.sin(ang)],[np.sin(ang),np.cos(ang)]])
    checks['common_yaw_Q_difference']=abs(score(flat(P.xz@rot.T),flat(R.xz@rot.T))['Q']-base['Q'])
    checks['common_ring_reversal_Q_difference']=abs(score(flat(P.xz[::-1]),flat(R.xz[::-1]))['Q']-base['Q'])
    checks['common_ring_shift_Q_difference']=abs(score(flat(np.roll(P.xz,2,axis=0)),flat(np.roll(R.xz,2,axis=0)))['Q']-base['Q'])
    (OUT/'checks.json').write_text(json.dumps(checks,indent=2),encoding='utf-8')
    assert checks['identical_manhattan_Q_error']<1e-10
    assert checks['global_height_prism_analytic_max_error']<1e-10
    assert checks['balanced_tilt_hc_analytic_max_error']<1e-6
    assert checks['resegmentation_Q_range']<1e-6
    assert checks['matched_shear_translation_iou_max_difference']<1e-10
    assert checks['matched_near_far_iou_max_difference']<1e-10
    print('Computed',len(frame),'synthetic layouts, eight experiment families.')
    print(json.dumps(checks,indent=2))
    return frame

if __name__=='__main__':
    main()
