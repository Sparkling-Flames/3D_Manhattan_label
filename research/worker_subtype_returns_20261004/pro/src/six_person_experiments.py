"""Enumerate real six-person sets. Labels frozen outside target building.
No best-team selection. All extrema are explicitly retrospective diagnostics.
"""
from pathlib import Path
import os, json, itertools, math
import numpy as np
import pandas as pd
from finite_pool import make_basis
ROOT=Path(os.environ.get('WORKER_RESEARCH_ROOT',Path(__file__).resolve().parents[1]))

def run(name,k=6):
 d=json.loads((ROOT/'inputs'/name).read_text());rec=sorted(d['records'],key=lambda r:r['worker']);b=make_basis(rec,d['reference']);n=len(rec)
 subsets=np.array(list(itertools.combinations(range(n),k)),np.uint8)
 values={z:np.empty(len(subsets)) for z in ['iou_mv50','iou_mv_strict','area_mv50','area_mv_strict']}
 for start in range(0,len(subsets),512):
  inds=subsets[start:start+512];counts=b.votes[inds].sum(axis=1)
  for rule,t in [('mv50',(k+1)//2),('mv_strict',k//2+1)]:
   masks=counts>=t;inter=masks@b.inside_reference;area=masks@b.area
   values['iou_'+rule][start:start+len(inds)]=inter/(b.reference.area+area-inter)
   values['area_'+rule][start:start+len(inds)]=area
 ass=pd.read_csv(ROOT/'results/profile_assignments.csv');rows=[];decomp=[];ext=[]
 for policy in ['original','revised_where_available']:
  for method in ['median2','ward2']:
   sub=ass[(ass.policy==policy)&(ass.method==method)&(ass.target==d['building'])].set_index('worker').subtype
   labels=np.array([sub[r['worker']] for r in rec],int);h=labels[subsets].sum(axis=1);Nh=int(labels.sum());Nl=n-Nh
   for rule in ['mv50','mv_strict']:
    y=values['iou_'+rule];global_mean=y.mean();total_var=y.var();between=within=0.
    for c in np.unique(h):
     ix=np.flatnonzero(h==c);yc=y[ix];assert len(ix)==math.comb(Nh,int(c))*math.comb(Nl,k-int(c))
     w=len(ix)/len(y);between+=w*(yc.mean()-global_mean)**2;within+=w*yc.var()
     rows.append(dict(image=d['image'],policy=policy,method=method,rule=rule,k=k,higher_n=int(c),higher_pool_n=Nh,lower_pool_n=Nl,sets_n=len(ix),mean_iou=float(yc.mean()),sd_iou=float(yc.std()),q05_iou=float(np.quantile(yc,.05)),q50_iou=float(np.quantile(yc,.5)),q95_iou=float(np.quantile(yc,.95)),min_iou=float(yc.min()),max_iou=float(yc.max())))
     for label,idx in [('minimum',ix[np.argmin(yc)]),('maximum',ix[np.argmax(yc)])]:
      ext.append(dict(image=d['image'],policy=policy,method=method,rule=rule,k=k,higher_n=int(c),diagnostic=label,iou=float(y[idx]),workers='|'.join(rec[j]['worker'] for j in subsets[idx]),record_ids='|'.join(rec[j]['id'] for j in subsets[idx]),deployment_selection=False))
    assert abs(total_var-between-within)<1e-13
    decomp.append(dict(image=d['image'],policy=policy,method=method,rule=rule,k=k,sets_n=len(y),mean_iou=float(global_mean),total_variance=float(total_var),between_composition_variance=float(between),within_composition_variance=float(within),between_share=float(between/total_var),within_share=float(within/total_var)))
 for suffix,data in [('six_person_compositions',rows),('six_person_variance',decomp),('six_person_extrema_diagnostic',ext)]:
  pd.DataFrame(data).to_csv(ROOT/'results'/f'{d["image"]}_{suffix}.csv',index=False)
 np.savez_compressed(ROOT/'results'/f'{d["image"]}_six_person_all_sets.npz',subsets=subsets,worker=np.array([r['worker'] for r in rec]),record_id=np.array([r['id'] for r in rec]),**values)
 print(d['image'],'complete six-person sets:',len(subsets),flush=True)
if __name__=='__main__':
 import argparse
 p=argparse.ArgumentParser();p.add_argument('--input',default='one_image_geometry.json');a=p.parse_args();run(a.input)
