"""Independent implementation, not the original snapshot verifier.
Model: common camera at origin, Y up, floor Y=-1, continuous 1024x512.
Input records are never modified; source ring order is retained.
"""
from __future__ import annotations
import math
import numpy as np
import shapely
from shapely.geometry import Polygon, Point, LineString

def cross(a,b):return a[...,0]*b[...,1]-a[...,1]*b[...,0]
def rays(xy,convention='continuous'):
 p=np.asarray(xy,float)+(.5 if convention=='pixel_center' else 0.)
 u=2*np.pi*(p[...,0]/1024-.5);v=np.pi*(.5-p[...,1]/512)
 return np.stack([np.cos(v)*np.sin(u),np.sin(v),-np.cos(v)*np.cos(u)],axis=-1)
def project(p):
 p=np.asarray(p,float)
 return np.stack([((np.arctan2(p[...,0],-p[...,2])/(2*np.pi)+.5)*1024)%1024,
 (.5-np.arctan2(p[...,1],np.linalg.norm(p[...,[0,2]],axis=-1))/np.pi)*512],axis=-1)
def from_floor(p,heights=2.7,labels=None):
 p=np.asarray(p,float);h=np.broadcast_to(heights,(len(p),))
 t=project(np.c_[p[:,0],h-1,p[:,1]]);b=project(np.c_[p[:,0],-np.ones(len(p)),p[:,1]])
 return dict(points=np.stack([t,b],axis=1).reshape(-1,2).tolist(),coordinate_convention='continuous',
 source_pair_indices=list(range(len(p))) if labels is None else labels,ring_confirmed=True)
def reconstruct(rec):
 p=np.asarray(rec['points'],float).reshape(-1,2,2);r=rays(p,rec.get('coordinate_convention','continuous'))
 vb=np.arcsin(np.clip(r[:,1,1],-1,1));vt=np.arcsin(np.clip(r[:,0,1],-1,1))
 br='wrong_hemisphere' if (vb>=0).any() else 'near_horizon' if (abs(vb)<np.radians(.5)).any() else None
 tr='wrong_hemisphere' if (vt<=0).any() else 'near_horizon' if (abs(vt)<np.radians(.5)).any() else None
 f=None if br else (-r[:,1]/r[:,1,1,None])[:,[0,2]];h=None;reason=br;camera='unavailable';kernel=None
 if f is not None:
  if tr is None:h=1+np.linalg.norm(f,axis=1)*np.tan(vt)
  poly=Polygon(f);e=np.roll(f,-1,axis=0)-f
  if not poly.is_valid or poly.area<1e-8 or np.linalg.norm(e,axis=1).min()<1e-7:reason='invalid_footprint'
  else:
   camera='inside' if poly.contains(Point(0,0)) else 'boundary' if poly.covers(Point(0,0)) else 'outside'
   orient=1 if poly.exterior.is_ccw else -1
   kernel=bool(camera=='inside' and np.all(orient*cross(e,-f)>=-1e-7))
 wr=reason or tr
 if np.max(abs((p[:,0,0]-p[:,1,0]+512)%1024-512))>1e-6:wr=wr or 'vertical_pair_mismatch'
 if not wr and camera!='inside':wr='camera_not_strictly_inside'
 return dict(floor=f,heights=h,reason=reason,wall_reason=wr,camera=camera,kernel=kernel)
def column_mask(g,w=512):
 if g['wall_reason']:raise ValueError(g['wall_reason'])
 p,h=g['floor'],g['heights'];u=2*np.pi*((np.arange(w)+.5)/w-.5);r=np.c_[np.sin(u),-np.cos(u)]
 d=np.full(w,np.inf);top=np.full(w,np.nan)
 for i,(a,b) in enumerate(zip(p,np.roll(p,-1,axis=0))):
  e=b-a;den=cross(r,e);ok=abs(den)>1e-12;t=np.full(w,np.inf);s=t.copy()
  t[ok]=cross(a,e)/den[ok];s[ok]=cross(a,r[ok])/den[ok]
  hit=ok&(t>0)&(s>=-1e-10)&(s<=1+1e-10)&(t<d)
  d[hit]=t[hit];top[hit]=h[i]+s[hit]*(h[(i+1)%len(p)]-h[i])-1
 if not np.isfinite(d).all():raise ValueError('uncovered_ray')
 v=np.pi*(.5-(np.arange(w//2)+.5)/(w//2))
 return (v[:,None]<=np.arctan2(top,d))&(v[:,None]>=-np.arctan2(1,d))
def iou(a,b):
 den=np.count_nonzero(a|b);return float(np.count_nonzero(a&b)/den) if den else None
def polygon_metrics(p,q,n=512):
 a,b=Polygon(p),Polygon(q)
 if not(a.is_valid and b.is_valid and min(a.area,b.area)>1e-12):raise ValueError('invalid_footprint')
 inter=a.intersection(b).area;ds=[]
 for s,t in ((a,b),(b,a)):
  pts=shapely.line_interpolate_point(s.boundary,np.arange(n)/n,normalized=True)
  ds.append(shapely.distance(pts,t.boundary))
 d=np.r_[ds[0],ds[1]]
 return dict(bev_iou=float(inter/(a.area+b.area-inter)),area_a=float(a.area),area_b=float(b.area),
  coverage_a=float(inter/a.area),coverage_b=float(inter/b.area),centroid=float(a.centroid.distance(b.centroid)),
  boundary_mean=float(d.mean()),boundary_p95=float(np.quantile(d,.95)),boundary_sampled_max=float(d.max()),
  boundary_step_bound=float(max(a.length,b.length)/n/2))
def sample_path(p,step=.01):
 p=np.asarray(p,float);c=[]
 for a,b in zip(p[:-1],p[1:]):
  n=max(1,int(np.ceil(np.linalg.norm(b-a)/step)));c.append(a+(b-a)*np.arange(n)[:,None]/n)
 return np.r_[np.concatenate(c),p[-1:]]
def path_metrics(a,b,step=.01):
 a,b=np.asarray(a,float),np.asarray(b,float);sa,sb=sample_path(a,step),sample_path(b,step)
 da=shapely.distance(shapely.points(sa),LineString(b));db=shapely.distance(shapely.points(sb),LineString(a))
 lo=float(max(da.max(),db.max()));fd=float(shapely.frechet_distance(LineString(sa),LineString(sb)))
 return dict(hausdorff_lower=lo,hausdorff_upper=lo+step/2,
  frechet_lower=max(0.,fd-step),frechet_upper=fd,mean_a_b=float(da.mean()),mean_b_a=float(db.mean()),
  coverage_a_001=float((da<=.01).mean()),coverage_b_001=float((db<=.01).mean()),samples_a=len(sa),samples_b=len(sb))
def turns(p,closed=True):
 p=np.asarray(p,float);e=np.roll(p,-1,axis=0)-p if closed else np.diff(p,axis=0)
 a,b=(np.roll(e,1,axis=0),e) if closed else (e[:-1],e[1:])
 return np.degrees(np.arctan2(cross(a,b),np.sum(a*b,axis=1)))
def axis_residual(p,axis=0.):
 p=np.asarray(p,float);e=np.roll(p,-1,axis=0)-p;l=np.linalg.norm(e,axis=1)
 a=np.arctan2(e[:,1],e[:,0])-axis;d=np.degrees(abs((a+np.pi/4)%(np.pi/2)-np.pi/4))
 return dict(weighted=float(np.average(d,weights=l)),maximum=float(d.max()),per_edge=d.tolist())
