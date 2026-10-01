"""Geometry/expression separation and an explicit hybrid decision prototype.
Tolerance choices are sensitivity inputs, not statistically calibrated thresholds.
"""
import json
from pathlib import Path
import numpy as np
from shapely.geometry import Polygon,Point
from geometry_core import *
from matching import *
from run_insertion_noise import unordered
BASE=Path(__file__).resolve().parents[1]
def classify_path(a,b,epsilon=.01,step=.002):
 """Tri-state geometry decision, retaining expression cardinality. No deletion.
 Only for already declared common open path gates. Use other window extractor for loops.
 """
 s=path_metrics(a,b,step)
 if s['frechet_upper']<=epsilon:status='geometrically_close'
 elif s['frechet_lower']>epsilon:status='geometrically_distinct'
 else:status='resolution_uncertain'
 return dict(geometry=status,point_count_a=len(a),point_count_b=len(b),cardinality_difference=len(a)-len(b),
   epsilon_h=epsilon,source_points_preserved=True,**s)
def main():
 p=np.array([[-3,-3],[3,-3],[3,3],[1,.7],[-3,3]],float);q=p[[0,1,3,2,4]]
 assert Polygon(p).is_valid and Polygon(q).is_valid and Polygon(p).contains(Point(0,0)) and Polygon(q).contains(Point(0,0))
 a,b=from_floor(p),from_floor(q);c=cyclic_align(a,b,4,2,'bound');u=unordered(a,b,4,2)
 ct,cb=endpoint_costs(a,b,4)
 out=dict(a=p.tolist(),b=q.tolist(),space=polygon_metrics(p,q),
   unordered_matches=u,unordered_cost=float(sum((ct[i,j]+cb[i,j])/2 for i,j in u)),cyclic=c,
   column_iou=iou(column_mask(reconstruct(a),1024),column_mask(reconstruct(b),1024)))
 (BASE/'results/order_counterexample.json').write_text(json.dumps(out,indent=2))
 local=json.load(open(BASE/'results/local_path_cases.json'));windows=json.load(open(BASE/'results/real_local_windows.json'))
 out2=[]
 for r in local[:2]:
  for eps in (.005,.01,.02,.05,.1):out2.append(dict(case=r['name'],**classify_path(r['a'],r['b'],eps)))
 for r in windows:
  if len(r['a_paths'])==len(r['b_paths'])==1:
   for eps in (.005,.01,.02,.05,.1):
    out2.append(dict(case=r['image'],**classify_path(r['a_paths'][0]['points'],r['b_paths'][0]['points'],eps,.005)))
 (BASE/'results/hybrid_local_geometry_decisions.json').write_text(json.dumps(out2,indent=2))
 print(json.dumps(out,indent=2));print('Hybrid window decisions:',len(out2))
if __name__=='__main__':main()
