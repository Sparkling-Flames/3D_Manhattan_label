"""Executable research baselines: no learned semantic correspondences.
Cyclic alignment preserves the supplied ring, never sorts longitude.
Positive gap cost is a sampling-sensitive EXPRESSION baseline, not a space metric.
"""
from __future__ import annotations
import numpy as np
from geometry_core import rays,cross

def endpoint_costs(a,b,sigma_px=4.):
 if not np.isfinite(sigma_px) or sigma_px<=0:raise ValueError('sigma_must_be_positive')
 p=np.asarray(a['points'],float).reshape(-1,2,2);q=np.asarray(b['points'],float).reshape(-1,2,2)
 r,s=rays(p,a.get('coordinate_convention','continuous')),rays(q,b.get('coordinate_convention','continuous'))
 ans=[]
 for side in (0,1):
  dot=np.sum(r[:,None,side]*s[None,:,side],axis=-1)
  c=np.linalg.norm(np.cross(r[:,None,side],s[None,:,side]),axis=-1)
  angle=np.arctan2(c,np.clip(dot,-1,1));ans.append((angle/(sigma_px*2*np.pi/1024))**2)
 return ans

def align_cost(c,gap=2.):
 if not np.isfinite(gap) or gap<=0:raise ValueError('gap_must_be_positive')
 c=np.asarray(c,float);n,m=c.shape
 d=np.full((n+1,m+1),np.inf);prev=np.zeros((n+1,m+1),np.int8)
 d[:,0]=np.arange(n+1)*gap;d[0,:]=np.arange(m+1)*gap;prev[1:,0]=1;prev[0,1:]=2
 for i in range(1,n+1):
  for j in range(1,m+1):
   options=(d[i-1,j-1]+c[i-1,j-1],d[i-1,j]+gap,d[i,j-1]+gap)
   op=int(np.argmin(options));prev[i,j]=op;d[i,j]=options[op]
 i,j=n,m;matched=[];ua=[];ub=[]
 while i or j:
  op=prev[i,j]
  if i and j and op==0:matched.append([i-1,j-1]);i-=1;j-=1
  elif i and (j==0 or op==1):ua.append(i-1);i-=1
  else:ub.append(j-1);j-=1
 return dict(cost=float(d[n,m]),matched=matched[::-1],unmatched_a=ua[::-1],unmatched_b=ub[::-1])

def cyclic_align(a,b,sigma_px=4.,gap=2.,side='bound'):
 if side not in ('bound','top','bottom'):raise ValueError('unknown_endpoint_mode')
 ct,cb=endpoint_costs(a,b,sigma_px);c=(ct+cb)/2 if side=='bound' else ct if side=='top' else cb
 n,m=c.shape;out=[]
 for rev in (False,True):
  seq=np.arange(m)[::-1] if rev else np.arange(m)
  for k in range(m):
   ix=np.roll(seq,-k);ans=align_cost(c[:,ix],gap)
   ans['matched']=[[i,int(ix[j])] for i,j in ans['matched']]
   ans['unmatched_b']=[int(ix[j]) for j in ans['unmatched_b']]
   ans.update(reverse=rev,shift=k);out.append(ans)
 out.sort(key=lambda a:(a['cost'],-len(a['matched']),a['reverse'],a['shift']))
 ans=out[0];maps={tuple(map(tuple,v['matched'])) for v in out if abs(v['cost']-ans['cost'])<1e-10}
 ans.update(sigma_px=sigma_px,gap=gap,side=side,coverage_a=len(ans['matched'])/n,coverage_b=len(ans['matched'])/m,
   equally_best_maps=len(maps))
 if ans['matched']:
  ij=np.asarray(ans['matched']);ans['matched_top_rms_sigma']=float(np.sqrt(ct[ij[:,0],ij[:,1]].mean()))
  ans['matched_bottom_rms_sigma']=float(np.sqrt(cb[ij[:,0],ij[:,1]].mean()))
 else:ans.update(matched_top_rms_sigma=None,matched_bottom_rms_sigma=None)
 return ans

def angular_window_paths(p,lo_px,hi_px):
 """Intersect PHYSICAL ring with an angular wedge, retaining all components.
 Gates are derived intersections on existing edges, not new annotations.
 Returns paths in ring order and edge/fraction provenance. No x sorting.
 """
 p=np.asarray(p,float);span=hi_px-lo_px
 if not 0<span<512:raise ValueError('window_span_must_be_less_than_half_circle')
 def inside(x):
  u=(np.arctan2(x[0],-x[1])/(2*np.pi)+.5)*1024
  return (u-lo_px)%1024 <=span+1e-8
 parts=[]
 for i,(a,b) in enumerate(zip(p,np.roll(p,-1,axis=0))):
  e=b-a;cuts=[0.,1.]
  for boundary in (lo_px,hi_px):
   u=2*np.pi*(boundary/1024-.5);r=np.array([np.sin(u),-np.cos(u)])
   den=cross(r,e)
   if abs(den)>1e-12:
    t=cross(a,e)/den;s=cross(a,r)/den
    if t>0 and 1e-10<s<1-1e-10:cuts.append(float(s))
  cuts=sorted(set(cuts))
  for l,h in zip(cuts[:-1],cuts[1:]):parts.append((inside(a+(l+h)/2*e),a+l*e,a+h*e,i,l,h))
 # Cut at an excluded part so a wraparound path remains one component.
 outside=next((j for j,x in enumerate(parts) if not x[0]),None)
 if outside is None:return [dict(points=np.r_[p,p[:1]].tolist(),closed=True,interior_vertex_indices=list(range(len(p))))]
 parts=parts[outside+1:]+parts[:outside+1];paths=[];points=[];ids=[];provenance=[]
 for yes,a,b,i,l,h in parts:
  if yes:
   if not points:points=[a]
   if l==0 and len(points)>1:ids.append(i)
   points.append(b);provenance.append(dict(edge=i,start_fraction=l,end_fraction=h))
  elif points:
   paths.append(dict(points=np.asarray(points).tolist(),interior_vertex_indices=ids,segments=provenance,closed=False))
   points=[];ids=[];provenance=[]
 return paths
