"""Pairing-free whole-point coverage study. Fixed angular units, no ROI/scale learning.
OSPA1: previous c=30, p=1. OSPA2: c=30, p=2.
Hausdorff: untruncated symmetric max of directed nearest-neighbour angular distances.
Matching coverage: maximum cardinality one-to-one pairs within each fixed radius.
No coordinate changes, imputation, worker weights, time or model output enters distances.
"""
from __future__ import annotations
from pathlib import Path
import argparse,collections,gzip,hashlib,itertools,json,math
import numpy as np,pandas as pd
from scipy.optimize import linear_sum_assignment
from scipy.cluster.hierarchy import linkage,fcluster
from scipy.spatial.distance import squareform
ROOT=Path(__file__).resolve().parents[4]/'analysis_results/local_point_research_received_20260919'
RADII=[3.,6.,9.,12.]

def load(root=ROOT):
 rows=[json.loads(l)for l in gzip.open(root/'inputs/responses.jsonl.gz','rt',encoding='utf-8')]
 audit=pd.read_csv(root/'inputs/all_response_audit.csv').set_index('id')
 return rows,audit

def point_ok(r):
 if r['worker_id']in {'W019','W026'} or not r['calculation_included']:return False
 p=np.asarray(r['effective_points_1024x512'],float)
 return p.ndim==2 and p.shape[1:]==(2,)and len(p)>0 and np.isfinite(p).all()and np.all(p>=0)and np.all(p[:,0]<=1024)and np.all(p[:,1]<512)

def vectors(p):
 p=np.asarray(p,float);u=((p[:,0]+.5)/1024-.5)*2*np.pi;v=((p[:,1]+.5)/512-.5)*np.pi
 return np.column_stack([np.cos(v)*np.cos(u),np.cos(v)*np.sin(u),np.sin(v)])

def angular(a,b):
 # Same convention and numerical formula as the archived OSPA comparator.
 return np.degrees(np.arccos(np.clip(vectors(a)@vectors(b).T,-1,1)))

def features(C):
 m,n=C.shape;cap=np.minimum(C,30.);i,j=linear_sum_assignment(cap)
 ospa=(cap[i,j].sum()+30*abs(m-n))/max(m,n)
 i2,j2=linear_sum_assignment(cap**2)
 ospa2=math.sqrt(((cap[i2,j2]**2).sum()+900*abs(m-n))/max(m,n))
 near_a=C.min(1);near_b=C.min(0);h=max(near_a.max(),near_b.max())
 row={'n_a':m,'n_b':n,'same_count':m==n,'ospa1':ospa,'ospa2':ospa2,'cardinality_floor':30*abs(m-n)/max(m,n),'hausdorff':h,'directed_a':near_a.max(),'directed_b':near_b.max(),'nn_mean':.5*(near_a.mean()+near_b.mean()),'sum_assignment_max':C[i,j].max(),'bottleneck':np.nan}
 if m==n:
  vals=np.unique(C);lo=0;hi=len(vals)-1
  while lo<hi:
   mid=(lo+hi)//2;ib,jb=linear_sum_assignment((C>vals[mid]).astype(int))
   if (C[ib,jb]<=vals[mid]).all():hi=mid
   else:lo=mid+1
  row['bottleneck']=float(vals[lo])
 for t in RADII:
  ib,jb=linear_sum_assignment((C>t).astype(int));k=int((C[ib,jb]<=t).sum())
  row[f'uncovered_a_{int(t)}']=int((near_a>t).sum());row[f'uncovered_b_{int(t)}']=int((near_b>t).sum())
  row[f'matched_{int(t)}']=k;row[f'one_to_one_unmatched_{int(t)}']=m+n-2*k
 return row

def cluster(D,cut):
 if len(D)<2:return np.ones(len(D),int)
 return fcluster(linkage(squareform(D,checks=True),method='complete'),cut,criterion='distance')

def stats(lab):
 n=len(lab);c=np.array(list(collections.Counter(lab).values()));return dict(N=n,clusters=len(c),supported=int((c>=2).sum()),singletons=int((c==1).sum()),singleton_mass=float((c==1).sum()/n),largest_share=float(c.max()/n),sizes=';'.join(map(str,sorted(c,reverse=True))))

def config_matrices(ds):
 yield 'count_only',(ds['count_diff']>0).astype(float),0.
 for t in [3.,6.,9.]:yield f'OSPA1_{int(t)}',ds['ospa1'],t
 for t in RADII:yield f'OSPA2_{int(t)}',ds['ospa2'],t
 for t in RADII:yield f'Hausdorff_{int(t)}',ds['hausdorff'],t
 for t in [6.,9.,12.]:yield f'OSPA1_6_AND_H{int(t)}',np.maximum(ds['ospa1']/6.,ds['hausdorff']/t),1.
 # A deliberately strict multiplicity-sensitive comparator, no automatic count repair.
 for t in [6.,9.,12.]:yield f'Bottleneck_equal_{int(t)}',ds['bottleneck'],t

def run(root=ROOT, output_dir=None):
 out=Path(output_dir) if output_dir is not None else root/'local_recheck';out.mkdir(parents=True,exist_ok=True);rows,audit=load(root);groups=collections.defaultdict(list);coverage=[]
 for r in rows:
  ok=point_ok(r);coverage.append(dict(id=r['canonical_annotation_id'],worker=r['worker_id'],image_id=r['image_id'],condition=r['raw_condition'],eligible=ok,excluded_worker=r['worker_id']in {'W019','W026'},processing_status=r['processing_status'],raw_count=r['raw_point_count'],effective_count=r['effective_point_count'],imputed_point=r['imputed_point']))
  if ok:groups[r['image_id'],r['raw_condition']].append(r)
 pd.DataFrame(coverage).to_csv(out/'coverage.csv',index=False)
 old=pd.read_csv(root/'inputs/old_ospa_pairwise.csv');oldmap={tuple(sorted((r.id_a,r.id_b))):r.ospa30_deg for r in old.itertuples()}
 pairrows=[];summary=[];members=[];cache={};errors=[];novel=[];graph=[];jackknife=[]
 for (iid,cond),rr in sorted(groups.items()):
  rr=sorted(rr,key=lambda x:x['worker_id']);ids=[r['canonical_annotation_id']for r in rr];N=len(rr);cnt=np.array([r['effective_point_count']for r in rr]);code=audit.loc[ids[0],'code']
  assert len(set(r['worker_id']for r in rr))==N
  ds={k:np.zeros((N,N))for k in ['ospa1','ospa2','hausdorff','bottleneck','count_diff']}
  for ia,ib in itertools.combinations(range(N),2):
   a,b=rr[ia],rr[ib];C=angular(a['effective_points_1024x512'],b['effective_points_1024x512']);f=features(C)
   pairrows.append(dict(code=code,image_id=iid,building=a['building_id'],condition=cond,id_a=ids[ia],id_b=ids[ib],worker_a=a['worker_id'],worker_b=b['worker_id'],**f))
   errors.append(abs(f['ospa1']-oldmap[tuple(sorted((ids[ia],ids[ib])))]) )
   for k in ds:
    v=float(abs(cnt[ia]-cnt[ib])) if k=='count_diff' else f[k]
    if not np.isfinite(v):v=180.
    ds[k][ia,ib]=ds[k][ib,ia]=v
  glabs={}
  for name,D,t in config_matrices(ds):
   lab=cluster(D,t);glabs[name]=lab.tolist();row=dict(code=code,image_id=iid,building=rr[0]['building_id'],condition=cond,method=name,**stats(lab))
   summary.append(row)
   for i,r in enumerate(rr):members.append(dict(code=code,image_id=iid,condition=cond,id=ids[i],worker=r['worker_id'],point_count=cnt[i],method=name,cluster=int(lab[i])))
   if name in ['OSPA1_6','Hausdorff_6','Hausdorff_9','Hausdorff_12','OSPA1_6_AND_H9']:
    A=D<=t;np.fill_diagonal(A,False);same=lab[:,None]==lab[None,:];positive=int(A.sum()//2);sep=int((A&~same).sum()//2)
    wedges=0
    for i,j,k in itertools.combinations(range(N),3):
     edges=int(A[i,j])+int(A[i,k])+int(A[j,k]);wedges+=edges==2
    graph.append(dict(**row,compatible_pairs=positive,compatible_pairs_split=sep,open_triangles=int(wedges),total_triples=math.comb(N,3)if N>=3 else 0))
    if N>=3:
     for omit in range(N):
      ix=np.delete(np.arange(N),omit);l2=cluster(D[np.ix_(ix,ix)],t)
      change=int(((lab[ix,None]==lab[ix][None,:])!=(l2[:,None]==l2[None,:])).sum()//2)
      jackknife.append(dict(code=code,image_id=iid,condition=cond,method=name,N=N,omitted_worker=rr[omit]['worker_id'],changed_pairs=change,total_pairs=math.comb(N-1,2)))
  cache[iid+'|'+cond]=dict(code=code,ids=ids,workers=[r['worker_id']for r in rr],counts=cnt.tolist(),Ds={k:v.tolist()for k,v in ds.items()},labels=glabs)
  # Exact finite-pool next-person diagnostics; no full-pool clusters needed.
  for k in [2,4,8,12,16]:
   if k>=N:continue
   def none(neighbors):
    return np.mean([math.comb(N-1-int(v),k)/math.comb(N-1,k)if N-1-int(v)>=k else 0. for v in neighbors])
   AO=ds['ospa1']<=6.;np.fill_diagonal(AO,False);po=none(AO.sum(1))
   for t in [6.,9.,12.]:
    AH=ds['hausdorff']<=t;np.fill_diagonal(AH,False)
    ph=none(AH.sum(1));bothnone=none((AO|AH).sum(1))
    novel.append(dict(code=code,image_id=iid,condition=cond,N=N,k=k,local_radius=t,ospa_uncovered=po,local_uncovered=ph,ospa_covered_but_local_uncovered=ph-bothnone,local_covered_but_ospa_uncovered=po-bothnone))
 pd.DataFrame(pairrows).to_csv(out/'pairwise.csv',index=False)
 for name,r in [('group_summary',summary),('memberships',members),('compatibility_graph',graph),('leave_one_out',jackknife),('next_person_diagnostics',novel)]:pd.DataFrame(r).to_csv(out/(name+'.csv'),index=False)
 (out/'cache.json').write_text(json.dumps(cache,separators=(',',':')), encoding='utf-8')
 basic=dict(raw_records=len(rows),retained=sum(not x['excluded_worker']for x in coverage),eligible=sum(x['eligible']for x in coverage),groups=len(groups),pairs=len(pairrows),configurations=len(glabs),ospa_max_absolute_reproduction_error=max(errors),count_only_is_baseline_not_semantic_truth=True)
 # arccos near 1 differs across BLAS/NumPy platforms; boundary changes are
 # reported separately, never hidden by a tolerance added to cluster cuts.
 assert basic['eligible']==2381 and basic['pairs']==20672 and max(errors)<3e-6
 (out/'NUMERICAL_SCOPE.json').write_text(json.dumps(basic,indent=2,default=lambda v:v.item()), encoding='utf-8');print(basic)
 print(pd.DataFrame(summary).groupby('method')[['clusters','singletons']].sum().to_string())
