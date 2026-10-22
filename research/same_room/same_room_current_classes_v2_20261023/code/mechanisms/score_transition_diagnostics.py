"""Describe frozen score changes and edgewise intrinsic direction error.

5-component transition Shapley is an algebraic allocation of the saved Q
change, not a causal estimate. Edge contributions sum to saved dir**2.
No fusion, geometric correction, point rematching or score replacement.
"""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from local_study_paths import WORK,CODE_ROOT,NATIVE,TAXONOMY,MECHANISMS,BUDGET,BUDGET_CASES,BUDGET_FINAL,FIGURES,ENGINE,REPO

from pathlib import Path
import ast,gzip,json,importlib.util,sys,hashlib,os
from math import factorial
from zipfile import ZipFile
import pandas as pd,numpy as np
P=MECHANISMS;R=REPO;E=R/'research/statistics/b8l2_shared_v6_20261016/inputs'
sp=importlib.util.spec_from_file_location('frozen_models',E/'working_models.py');m=importlib.util.module_from_spec(sp);sys.modules[sp.name]=m;sp.loader.exec_module(m)
with ZipFile(E/'measurement_engine.zip') as z:src=z.read('engine/audit_geometry.py').decode()
tree=ast.parse(src);keep={'direction_data','direction_residual','direction_axis'}
ns={'np':np};exec(compile(ast.Module(body=[n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name in keep],type_ignores=[]),'<frozen direction functions>','exec'),ns)
metrics=['iou_2d','S_bottom_deg','dir','Hmean','Hcenter']
result=[];edges=[]
for prefix in sys.argv[1:]:
 path=P/(prefix+'_EVIDENCE.json.gz')
 if not path.exists():path=P/(prefix+'_REPLAY.json.gz')
 data=json.load(gzip.open(path,'rt'))
 for r in data:
  t=r['team'];p=np.array(t['geometry']['footprint']);a={'bottom3d':np.c_[p[:,0],np.full(len(p),-1),p[:,1]]}
  theta,w=ns['direction_data'](a);axis=ns['direction_axis'](a);d=ns['direction_residual'](a,axis)
  assert abs(d-t['dir'])<1e-8,(prefix,r['side'],r['phase'],d,t['dir'])
  residual=np.rad2deg((theta-axis+np.pi/4)%(np.pi/2)-np.pi/4)
  for i in range(len(p)):
   edges.append(dict(case_id=prefix,side=r['side'],phase=r['phase'],image=t['image'],team_key=t['team_key'],
      edge_index=i,from_feature=t['geometry']['feature_ids'][i],to_feature=t['geometry']['feature_ids'][(i+1)%len(p)],
      length_h=w[i],length_fraction=w[i]/w.sum(),axis_deg=np.rad2deg(axis),wall_residual_deg=residual[i],
      contribution_to_squared_dir=residual[i]**2*w[i]/w.sum(),saved_dir=t['dir']))
 for side in 'ab':
  rows={r['phase']:r for r in data if r['side']==side};before=rows['before']['team'];after=rows['after']['team']
  aa=[before[k] for k in metrics];bb=[after[k] for k in metrics]
  vals={s:float(m.score(*[bb[i] if s&(1<<i) else aa[i] for i in range(5)],params=m.B)) for s in range(32)}
  assert abs(vals[0]-before['B8L2'])<1e-8 and abs(vals[31]-after['B8L2'])<1e-8
  for i,key in enumerate(metrics):
   change=sum(factorial(s.bit_count())*factorial(4-s.bit_count())/factorial(5)*(vals[s|(1<<i)]-vals[s]) for s in range(32) if not s&(1<<i))
   result.append(dict(case_id=prefix,side=side,image=before['image'],metric=key,before=aa[i],after=bb[i],
     transition_shapley_Q_points=change,total_Q_change=after['B8L2']-before['B8L2'],
     interpretation='algebraic saved-score transition allocation; not causal'))
pd.DataFrame(result).to_csv(P/'CASE_SCORE_TRANSITION_COMPONENTS.csv',index=False)
pd.DataFrame(edges).to_csv(P/'CASE_WALL_DIRECTION_LEDGER.csv',index=False)
(P/'SCORE_DIAGNOSTICS_PROVENANCE.json').write_text(json.dumps(dict(
 repository_commit='72a44e80c344975962e1071bd54d894dd86bb4b4',
 measurement_engine_sha256=hashlib.sha256((E/'measurement_engine.zip').read_bytes()).hexdigest(),
 working_models_sha256=hashlib.sha256((E/'working_models.py').read_bytes()).hexdigest(),
 direction_source='measurement_engine.zip::engine/audit_geometry.py; three original function AST nodes',
 attribution='32 saved component combinations per within-view transition, exact Shapley of before-to-after B8L2 change',
 new_fusion_count=0,new_scoring_scheme=False),ensure_ascii=False,indent=2))
print(pd.DataFrame(result).pivot(index=['case_id','image'],columns='metric',values='transition_shapley_Q_points').round(4).to_string())
