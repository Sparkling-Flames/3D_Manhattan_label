"""Nested leave-building-out selection; target outcomes never select method or labels."""
from pathlib import Path
import os
import json,itertools
import numpy as np,pandas as pd
from profile_experiments import fit
ROOT=Path(os.environ.get('WORKER_RESEARCH_ROOT',Path(__file__).resolve().parents[1]))
METHODS=['no_worker','median2','ward2','ward3','ward4','individual']
rows=[];choices=[];audit=[]
for policy in ['original','revised_where_available']:
 df=pd.read_csv(ROOT/'inputs'/f'matrix_{policy}_iou.csv');W=list(df.columns[2:]);y=df[W].to_numpy();r=y-y.mean(axis=1,keepdims=True);b=df.building.to_numpy();bs=sorted(set(b))
 for outer in bs:
  tr=b!=outer;te=~tr;inner_scores={m:[] for m in METHODS}
  for inner in bs:
   if inner==outer:continue
   itr=tr&(b!=inner);ite=tr&(b==inner)
   for method in METHODS:
    pred,z=fit(r[itr].mean(0),method)
    value=np.inf if pred is None else float(np.mean((r[ite]-pred)**2))
    inner_scores[method].append(value)
    audit.append(dict(policy=policy,outer=outer,inner=inner,method=method,train_buildings='|'.join(q for q in bs if q not in [outer,inner]),inner_mse=value))
  scores={m:float(np.mean(v)) for m,v in inner_scores.items()}
  # Predeclared simple-first order only breaks exact score ties.
  chosen=min(METHODS,key=lambda m:(scores[m],METHODS.index(m)))
  pred,z=fit(r[tr].mean(0),chosen)
  if pred is None:raise ValueError('selected_unavailable_fit')
  choices.append(dict(policy=policy,target=outer,selected_method=chosen,inner_mse=scores[chosen],test_mse=float(np.mean((r[te]-pred)**2)),baseline_mse=float(np.mean(r[te]**2)),test_n=int(te.sum()),test_sse=float(np.sum((r[te]-pred)**2)),baseline_sse=float(np.sum(r[te]**2))))
  for ix in np.flatnonzero(te):
   for j,w in enumerate(W):rows.append(dict(policy=policy,image=df.image.iloc[ix],worker=w,method=chosen,centered_target=r[ix,j],prediction=pred[j]))
for name,data in [('nested_method_choices',choices),('nested_prediction_cells',rows),('nested_inner_folds',audit)]:pd.DataFrame(data).to_csv(ROOT/'results'/f'{name}.csv',index=False)
f=pd.DataFrame(choices)
s=f.groupby('policy').agg(test_sse=('test_sse','sum'),baseline_sse=('baseline_sse','sum'),building_equal_mse=('test_mse','mean'),building_equal_baseline=('baseline_mse','mean'))
s['pooled_relative_improvement']=1-s.test_sse/s.baseline_sse;s['building_equal_relative_improvement']=1-s.building_equal_mse/s.building_equal_baseline
s.to_csv(ROOT/'results/nested_summary.csv');print(f.to_string(index=False));print(s.to_string())
