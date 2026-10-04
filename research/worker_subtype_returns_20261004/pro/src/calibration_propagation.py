"""Propagate choice of calibration buildings into class membership and team outputs.
Finite descriptive experiment, NOT an independent validation sample or confidence interval.
"""
from pathlib import Path
import os,json,itertools
import numpy as np,pandas as pd
from finite_pool import make_basis
from profile_experiments import fit
ROOT=Path(os.environ.get('WORKER_RESEARCH_ROOT',Path(__file__).resolve().parents[1]))
rows=[];summary=[]
for name in ['one_image_geometry.json','rpc_geometry.json']:
 d=json.loads((ROOT/'inputs'/name).read_text());rec=sorted(d['records'],key=lambda r:r['worker']);workers=[r['worker'] for r in rec];basis=make_basis(rec,d['reference'])
 z=np.load(ROOT/'results'/f'{d["image"]}_six_person_all_sets.npz');subsets=z['subsets'];assert list(z['worker'])==workers
 for policy in ['original','revised_where_available']:
  m=pd.read_csv(ROOT/'inputs'/f'matrix_{policy}_iou.csv');others=sorted(set(m.building)-{d['building']});col=m[workers].to_numpy();bags={rule:[] for rule in ['mv50','mv_strict']}
  for chosen in itertools.combinations(others,4):
   x=col[m.building.isin(chosen)].mean(axis=0);_,labels=fit(x-x.mean(),'median2')
   if labels is None:
    rows.append(dict(image=d['image'],policy=policy,calibration='|'.join(chosen),status='median_tie'));continue
   ix=labels[subsets].sum(axis=1)==6
   if not ix.any():raise ValueError('no_pure_six_member_subsets')
   N,_=basis.group_data(labels)
   for rule in bags:
    y=z['iou_'+rule][ix];q=basis.q(labels,(0,6),rule);v=basis.area_summary(q)
    row=dict(image=d['image'],policy=policy,calibration='|'.join(chosen),status='ok',rule=rule,higher_workers='|'.join(w for w,j in zip(workers,labels) if j==1),higher_n=N[1],sets_n=int(ix.sum()),mean_iou=float(y.mean()),within_team_iou_variance=float(y.var()),same_k_shape=v['same_k_independent_symdiff_union'])
    rows.append(row);bags[rule].append((row,q))
  for rule,bag in bags.items():
   qq=np.array([x[1] for x in bag]);means=np.array([x[0]['mean_iou'] for x in bag]);within=np.mean([x[0]['within_team_iou_variance'] for x in bag]);between=means.var()
   shape_within=np.mean([x[0]['same_k_shape'] for x in bag]);shape_between=float(2*basis.area@qq.var(axis=0)/basis.union_area);shape_total=float(2*basis.area@(qq.mean(axis=0)*(1-qq.mean(axis=0)))/basis.union_area)
   assert abs(shape_total-shape_within-shape_between)<1e-12
   summary.append(dict(image=d['image'],policy=policy,rule=rule,valid_calibrations=len(bag),possible_calibrations=35,distinct_higher_lists=len({x[0]['higher_workers'] for x in bag}),minimum_conditional_mean_iou=means.min(),maximum_conditional_mean_iou=means.max(),average_conditional_mean_iou=means.mean(),iou_variance_due_to_list_fraction=between/(between+within),shape_within_fixed_list=shape_within,shape_between_calibration_lists=shape_between,shape_total=shape_total,shape_between_fraction=shape_between/shape_total))
pd.DataFrame(rows).to_csv(ROOT/'results/calibration_propagation_details.csv',index=False)
s=pd.DataFrame(summary);s.to_csv(ROOT/'results/calibration_propagation_summary.csv',index=False);print(s.to_string(index=False))
