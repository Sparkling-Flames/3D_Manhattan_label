from pathlib import Path
import os
import itertools,json,math
import numpy as np,pandas as pd
from finite_pool import make_basis
ROOT=Path(os.environ.get('WORKER_RESEARCH_ROOT',Path(__file__).resolve().parents[1]))

def run(path):
 data=json.loads(path.read_text());records=sorted(data['records'],key=lambda r:r['worker'])
 if len(records)!=24:raise ValueError('pilot_requires_complete_24_person_roster')
 b=make_basis(records,data.get('reference')); print(data['image'],b.checks,flush=True)
 assign=pd.read_csv(ROOT/'results/profile_assignments.csv');images=[];trans=[];defs=[];checks=[];iour=[]
 cfg=[('none','all',np.zeros(24,int))]
 for policy in ['original','revised_where_available']:
  for method in ['median2','ward2']:
   sub=assign.query('policy==@policy and method==@method and target==@data["building"]') if False else assign[(assign.policy==policy)&(assign.method==method)&(assign.target==data['building'])]
   by=dict(zip(sub.worker,sub.subtype)); labels=np.array([by[r['worker']] for r in records],int)
   cfg.append((policy,method,labels))
 for policy,method,labels in cfg:
  N,C=b.group_data(labels)
  defs.append(dict(image=data['image'],policy=policy,method=method,class_sizes=N,classes={str(g):[r['worker'] for r,z in zip(records,labels) if z==g] for g in range(len(N))},calibration_excludes=data['building'],new_vote_weights='all_one'))
  for K in itertools.product(*(range(n+1) for n in N)):
   if not sum(K):continue
   q=b.q(labels,K,'mv50') # cached per-rule below
   for rule in ['mv50','mv_strict']:
    meta=dict(image=data['image'],policy=policy,method=method,rule=rule,k=sum(K),composition='|'.join(map(str,K)),class_sizes='|'.join(map(str,N)))
    q=b.q(labels,K,rule);summary=b.area_summary(q)
    if all(2*k<=n for k,n in zip(K,N)):
     summary['same_k_disjoint_symdiff_union']=b.transition(labels,K,rule,'disjoint',())['expected_shape_change_union']
    images.append(dict(**meta,**summary))
    for g in range(len(N)):
     for step in [1,2]:
      if K[g]+step>N[g]:continue
      A=tuple(step if t==g else 0 for t in range(len(N)))
      vals=b.transition(labels,K,rule,'add',A)
      newK=tuple(k+a for k,a in zip(K,A));q2=b.q(labels,newK,rule)
      identity_error=abs(vals['expected_growth_union']-vals['expected_shrinkage_union']-float(b.area@(q2-q)/b.union_area))
      if identity_error>1e-11:raise ValueError('transition_marginal_identity')
      trans.append(dict(**meta,operation='add',change='|'.join(map(str,A)),**vals))
     for h in range(len(N)):
      if K[g]==0 or K[h]==N[h]:continue
      vals=b.transition(labels,K,rule,'swap',(g,h))
      trans.append(dict(**meta,operation='swap',change=str(g)+'->'+str(h),**vals))
    # Exact mean IoU only when one class supplies all members and <=5000 subsets.
    active=[g for g,k in enumerate(K) if k]
    if b.reference is not None and len(active)==1:
     g=active[0];ng=math.comb(N[g],K[g])
     if ng<=5000:
      pool=np.flatnonzero(labels==g); ms=np.array(list(itertools.combinations(pool,K[g])),int)
      masks=b.votes[ms].sum(axis=1)>=(sum(K)+1)//2 if rule=='mv50' else b.votes[ms].sum(axis=1)>=(sum(K)//2+1)
      inter=masks@b.inside_reference;area=masks@b.area;values=inter/(b.reference.area+area-inter)
      qerr=float(np.max(abs(masks.mean(axis=0)-q)))
      if qerr>1e-11:raise ValueError('hypergeom_vs_enumeration')
      iour.append(dict(**meta,subsets_n=ng,mean_iou=float(values.mean()),sd_iou=float(values.std()),min_iou=float(values.min()),max_iou=float(values.max()),q_max_error=qerr))
 tag=data['image']
 for name,rows in [('area',images),('transitions',trans),('exact_pure_iou',iour)]:pd.DataFrame(rows).to_csv(ROOT/'results'/f'{tag}_{name}.csv',index=False)
 (ROOT/'results'/f'{tag}_definitions.json').write_text(json.dumps(defs,ensure_ascii=False,indent=2)+'\n')
 (ROOT/'results'/f'{tag}_basis_checks.json').write_text(json.dumps(b.checks,indent=2)+'\n')
 np.savez_compressed(ROOT/'results'/f'{tag}_basis.npz',area=b.area,votes=b.votes,inside_reference=b.inside_reference,worker=np.array([r['worker'] for r in records]))
 print(tag,'area rows',len(images),'coupled transitions',len(trans),'exact_iou_rows',len(iour),flush=True)
if __name__=='__main__':
 import argparse
 p=argparse.ArgumentParser();p.add_argument('--input',default='one_image_geometry.json');a=p.parse_args()
 run(ROOT/'inputs'/a.input)
