from pathlib import Path
import sys,json,numpy as np
P=Path('/workspace/scratch/81fa50cc64f5/new_pro_return/panorama_quality_three_routes_20261016');sys.path.insert(0,str(P/'src'))
from geomscore import *
from run_controls import geom
OUT=Path('/workspace/scratch/81fa50cc64f5/new_pro_audit')
rot=np.array([[0.,-1.],[1.,0.]])
rng=np.random.default_rng(2026101601)
best=None
for n in range(1500):
 w=rng.uniform(.01,.09);x=np.sort(rng.uniform(-1.99,1.99,8));upper=rng.uniform(-w,w,8);lower=rng.uniform(-w,w,8)
 # Narrow but simple polygon, all additional points strictly within the box.
 upper=np.abs(upper)*.8+w*.2;lower=-np.abs(lower)*.8-w*.2
 p=np.array([[-2,-w],[2,-w],*zip(x[::-1],upper[::-1]),[-2,w],*zip(x,lower)],float)
 if not Polygon(p).is_valid:continue
 r=np.array([[-2,-w],[2,-w],[2,w],[-2,w]])
 try:
  a=angle_detail(p,r,Config());b=angle_detail(p@rot,r@rot,Config());e=abs(a['angle_penalty']-b['angle_penalty'])+abs(a['structural_loss']-b['structural_loss'])
 except ValueError:continue
 if best is None or e>best['error']:
  best=dict(trial=n,w=w,p=p.tolist(),r=r.tolist(),error=e,a=a,b=b)
  if e>.05:break
print('SIMPLIFY_BEST',json.dumps(best))
(OUT/'simplify_yaw_probe.json').write_text(json.dumps(best,indent=2))
# Height/nearest tie: source polygon has a diagonal exactly on the square-corner bisector.
a=np.array([[-2,-2],[2,-2],[1.5,1.5],[.5,.5],[-2,2]],float);r=np.array([[-2,-2],[2,-2],[2,2],[-2,2]],float)
rows=[]
for heights in [[2,2,2,6],[2,6,6,2],[1,1,1,8],[1,8,8,1]]:
 for k,R in [(0,np.eye(2)),(90,rot),(180,-np.eye(2)),(270,-rot)]:
  s=score_pair(geom(a@R,2),geom(r@R,heights));rows.append(dict(heights=heights,yaw=k,s=s))
print('HEIGHT_TIE',[(x['heights'],x['yaw'],x['s']['QA'],x['s']['surface_height']['local_error']) for x in rows])
(OUT/'height_tie_probe.json').write_text(json.dumps(dict(answer=a.tolist(),reference=r.tolist(),rows=rows),indent=2))
