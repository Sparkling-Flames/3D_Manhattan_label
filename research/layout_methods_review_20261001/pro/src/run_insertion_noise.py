"""Controlled perturbations of two real annotation geometries.
These are NOT newly collected workers. Correspondence identities are known by construction.
Insertion is exactly on the same 3D floor and wall-top segment before pixel noise.
"""
import json,csv
from pathlib import Path
from copy import deepcopy
import numpy as np
from scipy.optimize import linear_sum_assignment
from geometry_core import reconstruct,from_floor
from matching import cyclic_align,endpoint_costs
from real_inputs import get
BASE=Path(__file__).resolve().parents[1]
def unordered(a,b,sigma,gap=8.):
 ct,cb=endpoint_costs(a,b,sigma);c=(ct+cb)/2;n,m=c.shape
 # Deleting one A node and one B node costs two gaps, as in cyclic DP.
 d=np.full((n+m,n+m),1e12);d[:n,:m]=c
 d[np.arange(n),m+np.arange(n)]=gap;d[n+np.arange(m),np.arange(m)]=gap;d[n:,m:]=0
 ii,jj=linear_sum_assignment(d)
 return [(int(i),int(j)) for i,j in zip(ii,jj) if i<n and j<m]
def main():
 rows=[];rng=np.random.default_rng(61001)
 for a,edge in [(get()[1][0],0),(get()[2][0],1)]:
  g=reconstruct(a);p,h=g['floor'],g['heights'];k=edge+1
  q=np.insert(p,k,(p[edge]+p[k])/2,axis=0);hq=np.insert(h,k,(h[edge]+h[k])/2)
  target=from_floor(q,hq);truth={i:i if i<k else i+1 for i in range(len(p))}
  for noise in (.25,.5,1,2,4):
   for rep in range(30):
    b=deepcopy(target);pairs=np.asarray(b['points']).reshape(-1,2,2)
    pairs[:,:,0]=(pairs[:,:,0]+rng.normal(0,noise,(len(pairs),1)))%1024
    pairs[:,:,1]+=rng.normal(0,noise,(len(pairs),2));b['points']=pairs.reshape(-1,2).tolist()
    methods={'unordered_bound':unordered(a,b,noise),'cyclic_bound':cyclic_align(a,b,noise,8,'bound')['matched']}
    top=cyclic_align(a,b,noise,8,'top')['matched'];bot=cyclic_align(a,b,noise,8,'bottom')['matched']
    methods['split_top']=top;methods['split_bottom']=bot
    tm,bm=dict(top),dict(bot);ti={j:i for i,j in tm.items()};bi={j:i for i,j in bm.items()}
    conflict=any(tm[i]!=bm[i] for i in tm.keys()&bm.keys()) or any(ti[j]!=bi[j] for j in ti.keys()&bi.keys())
    for method,pairs in methods.items():
     correct=sum(truth[i]==j for i,j in pairs);wrong=len(pairs)-correct
     rows.append(dict(record=a['id'],noise_px=noise,rep=rep,method=method,correct=correct,wrong=wrong,
        missed=len(truth)-correct,matched=len(pairs),expected=len(truth),inserted_node_wrongly_matched=sum(j==k for i,j in pairs),
        split_pair_conflict=int(conflict)))
 fields=list(rows[0]);
 with (BASE/'results/insertion_noise.csv').open('w',newline='') as f:
  d=csv.DictWriter(f,fields);d.writeheader();d.writerows(rows)
 summary=[]
 for record in sorted({r['record'] for r in rows}):
  for noise in (.25,.5,1,2,4):
   for method in methods:
    sub=[r for r in rows if r['record']==record and r['noise_px']==noise and r['method']==method]
    n=sum(r['expected'] for r in sub);matched=sum(r['matched'] for r in sub);correct=sum(r['correct'] for r in sub)
    summary.append(dict(record=record,noise_px=noise,method=method,runs=len(sub),
      correct_coverage=correct/n,matched_coverage=matched/n,wrong_per_expected=(matched-correct)/n,
      precision_on_matched=correct/matched if matched else None,split_conflict_rate=np.mean([r['split_pair_conflict'] for r in sub])))
 (BASE/'results/insertion_noise_summary.json').write_text(json.dumps(summary,indent=2))
 print(json.dumps(summary,indent=2))
if __name__=='__main__':main()
