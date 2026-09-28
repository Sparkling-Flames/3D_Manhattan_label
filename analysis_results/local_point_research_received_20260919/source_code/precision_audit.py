from pathlib import Path
import itertools,collections,json,math
import pandas as pd,numpy as np
from scipy.optimize import linear_sum_assignment
import local_points as lp
R=lp.ROOT

def stable_angles(a,b):
 va,vb=lp.vectors(a),lp.vectors(b)
 # chord representation avoids cancellation near arccos(1), preserving identical points exactly.
 d=np.linalg.norm(va[:,None,:]-vb[None,:,:],axis=2)
 return np.degrees(2*np.arcsin(np.clip(d/2,0,1)))

def run():
 rows,au=lp.load();rr={r['canonical_annotation_id']:r for r in rows}
 p=pd.read_csv(R/'results/pairwise.csv');metrics=[]
 for r in p.itertuples():
  C=stable_angles(rr[r.id_a]['effective_points_1024x512'],rr[r.id_b]['effective_points_1024x512']);q=np.minimum(C,30);i,j=linear_sum_assignment(q);dist=(q[i,j].sum()+30*abs(C.shape[0]-C.shape[1]))/max(C.shape)
  metrics.append(dict(image_id=r.image_id,condition=r.condition,code=r.code,id_a=r.id_a,id_b=r.id_b,worker_a=r.worker_a,worker_b=r.worker_b,n_a=r.n_a,n_b=r.n_b,legacy=r.ospa1,stable=dist,delta=dist-r.ospa1,local_max_stable=max(C.min(0).max(),C.min(1).max()),cardinality_floor=r.cardinality_floor))
 d=pd.DataFrame(metrics);d.to_csv(R/'results/precision_pairwise.csv',index=False)
 cache=json.loads((R/'results/cache.json').read_text());lookup={tuple(sorted((x.id_a,x.id_b))):x for x in d.itertuples()};impact=[]
 for key,g in cache.items():
  ids=g['ids'];n=len(ids);newD=np.zeros((n,n));oldD=np.array(g['Ds']['ospa1'])
  for i,j in itertools.combinations(range(n),2):newD[i,j]=newD[j,i]=lookup[tuple(sorted((ids[i],ids[j])))].stable
  tri=np.triu_indices(n,1)
  for cut in [3.,6.,9.]:
   before=lp.cluster(oldD,cut);after=lp.cluster(newD,cut)
   impact.append(dict(code=g['code'],key=key,cut=cut,N=n,threshold_flips=int(((oldD[tri]<=cut)!=(newD[tri]<=cut)).sum()),changed_relations=int(((before[:,None]==before[None,:])!=(after[:,None]==after[None,:])).sum()//2),old_sizes=lp.stats(before)['sizes'],new_sizes=lp.stats(after)['sizes']))
 pd.DataFrame(impact).to_csv(R/'results/precision_partition_impact.csv',index=False)
 print('max error',d.delta.abs().max());print(pd.DataFrame(impact).groupby('cut').agg(threshold_flips=('threshold_flips','sum'),changed_units=('changed_relations',lambda x:(x>0).sum()),changed_pairs=('changed_relations','sum')))
 print(d[((d.legacy<=6)!=(d.stable<=6))].to_string(index=False))
 print('Q9',d[(d.code=='q9vSo1VnCiC-15')&d.worker_a.eq('W002')&d.worker_b.eq('W006')].to_dict('records'))
if __name__=='__main__':run()
