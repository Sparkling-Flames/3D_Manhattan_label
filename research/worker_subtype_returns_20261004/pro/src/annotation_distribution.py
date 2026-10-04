from pathlib import Path
import os
import json,math,itertools
import numpy as np,pandas as pd
from finite_pool import make_basis,next_member_loss
ROOT=Path(os.environ.get('WORKER_RESEARCH_ROOT',Path(__file__).resolve().parents[1]))

def run(name):
 d=json.loads((ROOT/'inputs'/name).read_text());rec=sorted(d['records'],key=lambda r:r['worker']);basis=make_basis(rec,d.get('reference'));A=basis.union_area;n=len(rec)
 D=np.array([[p.symmetric_difference(q).area/A for q in basis.polygons] for p in basis.polygons]);L=np.sqrt(D)
 I=np.array([[1-p.intersection(q).area/p.union(q).area for q in basis.polygons] for p in basis.polygons])
 ass=pd.read_csv(ROOT/'results/profile_assignments.csv');rows=[];pairrows=[];cfg=[('none','all',np.zeros(n,int))]
 for policy in ['original','revised_where_available']:
  for method in ['median2','ward2']:
   z=ass[(ass.policy==policy)&(ass.method==method)&(ass.target==d['building'])].set_index('worker').subtype
   cfg.append((policy,method,np.array([z[r['worker']] for r in rec])))
 for policy,method,labels in cfg:
  N,C=basis.group_data(labels)
  for g in range(len(N)):
   ids=np.flatnonzero(labels==g);m=len(ids)
   if m<2:continue
   mu=float(L[np.ix_(ids,ids)].sum()/(m*(m-1)))
   raw=float(I[np.ix_(ids,ids)].sum()/(m*(m-1)))
   pairrows.append(dict(image=d['image'],policy=policy,method=method,subtype=g,n=m,mean_raw_pair_1_minus_iou=raw,mean_raw_pair_sqrt_symdiff_union=mu))
   for k in range(1,m):
    K=tuple(k if j==g else 0 for j in range(len(N)))
    # Expected minimum distance from an unobserved member to a k-person seed.
    den=math.comb(m-1,k); w=np.array([math.comb(m-1-j,k-1)/den if m-1-j>=k-1 else 0. for j in range(1,m)])
    nearest=np.mean([np.sort(L[i,[j for j in ids if j!=i]])@w for i in ids])
    for rule in ['mv50','mv_strict']:
     p=np.array([next_member_loss(N,tuple(map(int,c)),K,rule,g) for c in C]);loss=float(basis.area@p/A)
     add=basis.transition(labels,K,rule,'add',tuple(1 if j==g else 0 for j in range(len(N))))
     rows.append(dict(image=d['image'],policy=policy,method=method,subtype=g,n=m,k=k,rule=rule,next_member_annotation_error_union=loss,add_one_fusion_change_union=add['expected_shape_change_union'],expected_empirical_energy_distance=2*mu*(1/k-1/m),expected_nearest_seed_sqrt_symdiff_union=float(nearest),mean_pairwise_dispersion_expected_at_any_k_ge2=raw))
 pd.DataFrame(rows).to_csv(ROOT/'results'/f'{d["image"]}_annotation_vs_fusion.csv',index=False)
 pd.DataFrame(pairrows).to_csv(ROOT/'results'/f'{d["image"]}_raw_dispersion.csv',index=False)
 print(pd.DataFrame(pairrows).to_string(index=False))
if __name__=='__main__':
 import argparse
 p=argparse.ArgumentParser();p.add_argument('--input',default='one_image_geometry.json');a=p.parse_args();run(a.input)
