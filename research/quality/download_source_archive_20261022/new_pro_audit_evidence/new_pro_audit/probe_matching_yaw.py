from pathlib import Path
import sys,json,numpy as np
from dataclasses import replace
from scipy.spatial import ConvexHull
P=Path('/workspace/scratch/81fa50cc64f5/new_pro_return/panorama_quality_three_routes_20261016');sys.path.insert(0,str(P/'src'))
from geomscore import *
from run_controls import geom
rng=np.random.default_rng(2026101602);rot=np.array([[0.,-1.],[1.,0.]])
best=None;tested=0
cfg=replace(Config(),simplify_h=(0.,))
for k in range(6000):
 try:
  p=rng.integers(-4,5,size=(rng.integers(5,11),2));p=p[ConvexHull(p).vertices].astype(float)
  r=rng.integers(-4,5,size=(rng.integers(5,11),2));r=r[ConvexHull(r).vertices].astype(float)
  if not Polygon(p).contains(Point(0,0)) or not Polygon(r).contains(Point(0,0)):continue
  a=angle_detail(p,r,cfg);b=angle_detail(p@rot,r@rot,cfg);delta=abs(a['angle_penalty']-b['angle_penalty']);tested+=1
  if best is None or delta>best['delta']:
   best=dict(trial=k,tested=tested,p=p.tolist(),r=r.tolist(),delta=delta,a=a,b=b)
  if delta>.05:
   best['full0']=score_pair(geom(p),geom(r));best['full90']=score_pair(geom(p@rot),geom(r@rot));break
 except ValueError:pass
print(json.dumps(best));print('TESTED',tested)
Path('/workspace/scratch/81fa50cc64f5/new_pro_audit/matching_yaw_probe.json').write_text(json.dumps(best,indent=2))
