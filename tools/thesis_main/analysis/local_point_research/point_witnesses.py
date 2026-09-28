"""Expose actual nearest-neighbour witnesses for reviewed cases, not semantic correspondences."""
import json
from pathlib import Path
import numpy as np,pandas as pd
from scipy.optimize import linear_sum_assignment
from . import local_points as lp
R=lp.ROOT

def run(root=R, output_dir=None):
 R=Path(root)
 output_dir=Path(output_dir) if output_dir is not None else R/'local_recheck'
 output_dir.mkdir(parents=True,exist_ok=True)
 cases=json.loads((output_dir/'visual_cases.json').read_text(encoding='utf-8'));out=[];matching=[]
 for r in cases:
  a=np.array(r['points_a']);b=np.array(r['points_b']);C=lp.angular(a,b)
  for direction,p,q,m in [('a_to_b',a,b,C),('b_to_a',b,a,C.T)]:
   for i,row in enumerate(m):
    j=int(np.argmin(row));v=float(row[j]);ties=np.flatnonzero(np.isclose(row,v,atol=1e-8,rtol=0))+1
    out.append(dict(case_id=r['case_id'],code=r['code'],condition=r['condition'],worker_a=r['worker_a'],worker_b=r['worker_b'],direction=direction,source_point_index_1based=i+1,source_x=p[i,0],source_y=p[i,1],nearest_index_1based=j+1,nearest_x=q[j,0],nearest_y=q[j,1],nearest_deg=v,equal_minimum_indices=';'.join(map(str,ties)),outside_6=v>6,outside_9=v>9,outside_12=v>12,meaning='geometric_nearest_only_not_confirmed_same_structure'))
  for rad in [6.,9.,12.]:
   i,j=linear_sum_assignment((C>rad).astype(int))
   chosen=[(int(x+1),int(y+1))for x,y in zip(i,j)if C[x,y]<=rad]
   matching.append(dict(case_id=r['case_id'],radius=rad,matched=len(chosen),n_a=len(a),n_b=len(b),example_maximum_matching=chosen,meaning='one_maximum_solution_not_unique_semantic_mapping'))
 pd.DataFrame(out).to_csv(output_dir/'reviewed_point_witnesses.csv',index=False)
 (output_dir/'reviewed_radius_matchings.json').write_text(json.dumps(matching,ensure_ascii=False,indent=2), encoding='utf-8')
