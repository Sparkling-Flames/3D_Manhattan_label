"""Read-only components and conditional 3-D projection, C canvas 1024x512.
Intrinsic model consistency is not reference accuracy or an automatic validity label.
"""
from __future__ import annotations
import sys, math, copy
from pathlib import Path
from functools import lru_cache
import numpy as np
from scipy.optimize import minimize_scalar
from shapely.geometry import Polygon, Point
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'vendor'))
import geometry as upstream
from arc_excerpt import pairs,footprint,paired_wall_proxy,Ring,Unsupported,rays
from quality import region_metrics, height_diagnostic, directed_arc_measure

DEG=180/np.pi

def payload(r):
 q=pairs(r)
 return dict(width=1024,height=512,coordinate_mode='pixels',ordered_pairs=[
  dict(source_pair_id=str(i),top=dict(zip(('x','y'),a)),bottom=dict(zip(('x','y'),b))) for i,(a,b) in enumerate(q)])

def sample_polyline(vertices,n=512,closed=True):
 """Midpoint equal-3D-arclength quadrature, no node deletion or new annotation."""
 v=np.asarray(vertices,float);a=v if closed else v[:-1];b=np.roll(v,-1,axis=0) if closed else v[1:]
 lengths=np.linalg.norm(b-a,axis=1);L=float(lengths.sum())
 if not np.isfinite(L) or L<=0:raise ValueError('zero_or_nonfinite_length')
 cum=np.r_[0.,np.cumsum(lengths)];d=(np.arange(n)+.5)*L/n
 i=np.minimum(np.searchsorted(cum,d,side='right')-1,len(lengths)-1)
 t=(d-cum[i])/lengths[i]
 return a[i]+t[:,None]*(b-a)[i],i,t,L

def segment_distances(q,vertices,closed=True):
 """Exact Euclidean query-to-finite-segment-union distances (not correspondence)."""
 q=np.asarray(q,float);v=np.asarray(vertices,float)
 a=v if closed else v[:-1];b=np.roll(v,-1,axis=0) if closed else v[1:];e=b-a;l2=(e*e).sum(1)
 delta=q[:,None,:]-a[None,:,:]
 t=np.divide(np.einsum('qed,ed->qe',delta,e),l2[None,:],out=np.zeros((len(q),len(a))),where=l2[None,:]>1e-24)
 t=np.clip(t,0,1);return np.linalg.norm(delta-t[:,:,None]*e[None,:,:],axis=-1).min(1)

def curve_distance(a,b,n=512):
 vals=[];out={}
 for x,y,lab in [(a,b,'a_to_g'),(b,a,'g_to_a')]:
  q,_,_,L=sample_polyline(x,n);d=segment_distances(q,y)
  out[lab+'_mean_h']=float(d.mean());out[lab+'_p95_h']=float(np.quantile(d,.95))
  out[lab+'_mean_quadrature_bound_h']=L/n/4
  out[lab+'_max_gap_bound_h']=L/n/2
  out[lab+'_sampled_max_h']=float(max(d.max(),segment_distances(x,y).max()))
  vals.append(float(d.mean()))
 out['symmetric_mean_h']=sum(vals)/2;return out

def intrinsic(r):
 out=dict(pair_count=len(r.get('points') or [])//2,geometry_status='unavailable',reason=None)
 try:
  q=pairs(r);f,p=footprint(r);top,bottom=paired_wall_proxy(r)
 except (Unsupported,ValueError,KeyError,TypeError) as ex:out['reason']=str(ex);return out
 if np.any(q[:,0,1]>=256) or np.any(q[:,0,1]<=0):out['reason']='top_not_strictly_above_horizon';return out
 out.update(geometry_status='ok',camera_relation='inside' if p.contains(Point(0,0)) else 'boundary' if p.covers(Point(0,0)) else 'outside',area_h2=p.area)
 hs=height_diagnostic(r);out.update(hs)
 e=np.roll(f,-1,axis=0)-f;length=np.linalg.norm(e,axis=1)
 if np.any(length<1e-8):out.update(axis_status='unavailable',axis_reason='zero_length_edge')
 else:
  axis=upstream.heading_frame(f);res=np.abs((np.arctan2(e[:,1],e[:,0])-axis+np.pi/4)%(np.pi/2)-np.pi/4)*DEG
  out.update(axis_status='ok',axis_deg=float(axis*DEG),direction_rms_deg=float(np.sqrt(np.average(res**2,weights=length))),direction_max_deg=float(res.max()))
 # angular residual of a horizontal wall-top plane, original floor held fixed;
 # samples on original floor perimeter so exact collinear subdivision is invariant.
 fq,ix,t,L=sample_polyline(f,n=512);h=top[:,1];observed=h[ix]+t*(np.roll(h,-1)-h)[ix];rho=np.linalg.norm(fq,axis=1)
 alpha=np.arctan2(observed,rho)
 fit=minimize_scalar(lambda logk:float(np.mean((alpha-np.arctan2(np.exp(logk),rho))**2)),bounds=(-9,9),method='bounded',options={'xatol':1e-10})
 k=np.exp(fit.x);out.update(flat_top_angular_rms_deg=float(np.sqrt(fit.fun)*DEG),flat_top_fitted_height_h=float(1+k),flat_top_model='conditional_horizontal_wall_top; not physical truth')
 beta=(q[:,1,1]-256)/512*np.pi;radii=1/np.tan(beta)
 out['max_depth_sensitivity_h_per_Cpx']=float(np.max((1+radii*radii)*np.pi/512))
 try:Ring(r);out['single_valued']='ok'
 except (Unsupported,ValueError) as ex:out.update(single_valued='unavailable',single_valued_reason=str(ex))
 return out

def compare(a,g,nlongitude=4096,ncurve=512):
 out=dict(reference_id=g.get('id'),reference_version=g.get('version'),reference_status='unavailable')
 try:
  f,p=footprint(a);fg,pg=footprint(g);out.update(region_metrics(p,pg));out['reference_status']='ok'
 except (Unsupported,ValueError,KeyError,TypeError) as ex:out['reference_reason']=str(ex);return out
 try:
  ra,rg=Ring(a),Ring(g);u=(np.arange(nlongitude)+.5)*2*np.pi/nlongitude
  err=(ra.evaluate(u)-rg.evaluate(u))*180/512
  out.update(longitude_status='ok',longitude_samples=nlongitude)
  for j,side in enumerate(['top','bottom']):
   out[side+'_mae_deg']=float(np.mean(abs(err[j])));out[side+'_signed_deg']=float(err[j].mean());out[side+'_p95_deg']=float(np.quantile(abs(err[j]),.95))
 except (Unsupported,ValueError,KeyError,TypeError) as ex:out.update(longitude_status='unavailable',longitude_reason=str(ex))
 try:
  ha,hg=height_diagnostic(a),height_diagnostic(g);top,bot=paired_wall_proxy(a);topg,botg=paired_wall_proxy(g)
  I=p.intersection(pg).area;hi=ha['height_mean_h'];hj=hg['height_mean_h'];iv=I*min(hi,hj)
  out.update(height_mean_signed_h=hi-hj,height_mean_relative_error=abs(hi-hj)/hj,conditional_volume_iou=iv/(p.area*hi+pg.area*hj-iv))
  for side,x,y in [('top3d',top,topg),('floor3d',bot,botg)]:
   for key,val in curve_distance(x,y,ncurve).items():out[side+'_'+key]=val
  # Direction to reference frame is EXTRINSIC, not intrinsic.
  axis=upstream.heading_frame(fg);ed=np.roll(f,-1,axis=0)-f;l=np.linalg.norm(ed,axis=1)
  res=np.abs((np.arctan2(ed[:,1],ed[:,0])-axis+np.pi/4)%(np.pi/2)-np.pi/4)*DEG
  out['direction_to_reference_rms_deg']=float(np.sqrt(np.average(res**2,weights=l)))
 except (Unsupported,ValueError,KeyError,TypeError) as ex:out.update(conditional_3d_reason=str(ex))
 return out

def project_existing(r):
 """Reuse provided fixed-axis / fixed-neighbor Manhattan+flat-top optimizer.
 It returns an analysis copy; no GT, vote or original-data mutation.
 """
 try:
  ans=upstream.analyze(payload(r),compute_fit=True,coordinate_convention='continuous');fit=ans['fit']
  if fit['status']!='ok':return dict(status=fit['status'],reason=';'.join(fit.get('reasons',[])),solver_message=fit.get('solver_message'))
  pts=[]
  for q in fit['reprojected_pairs']:pts.extend([q['top'],q['bottom']])
  rec=copy.deepcopy(r);rec.update(id=r['id']+'__projected',points=pts,ring_confirmed=False,derived_from=r['id'],operation='upstream_fixed_axis_manhattan_flat_top_projection',not_independent_vote=True,independent=False,consensus_eligible=False,quality_candidate=False)
  return dict(status='ok',record=rec,residual_max_deg=fit['residual_max_deg'],residual_mean_deg=fit['residual_mean_deg'],iterations=fit['iterations'],axis_assignment=fit['axis_assignment'])
 except (Unsupported,ValueError,TypeError,np.linalg.LinAlgError) as ex:return dict(status='unavailable',reason=str(ex))

def interpolate_3d(r,fit,alpha):
 a,b=paired_wall_proxy(r);c,d=paired_wall_proxy(fit)
 top=(1-alpha)*a+alpha*c;bottom=(1-alpha)*b+alpha*d
 pts=[]
 for t,f in zip(top,bottom):pts.extend([upstream.project_pixel(t,1024,512),upstream.project_pixel(f,1024,512)])
 out=copy.deepcopy(r);out.update(id=r['id']+f'__projected_alpha{alpha:g}',points=pts,derived_from=r['id'],operation='3d_interpolation_towards_upstream_projection',alpha=alpha,ring_confirmed=False,not_independent_vote=True,independent=False,consensus_eligible=False,quality_candidate=False)
 return out
