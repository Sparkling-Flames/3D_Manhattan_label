"""Restore original odd-length arrays for the two historically borrowed-point repairs.
Retains both people. Recompute their two image groups; reuse other groups unchanged.
A separate representation sensitivity, never edits raw/effective source snapshots.
"""
import json,itertools,math
import numpy as np,pandas as pd
import local_points as lp
R=lp.ROOT

def run():
 rows,audit=lp.load();by={r['canonical_annotation_id']:r for r in rows}
 original=json.loads((R/'results/cache.json').read_text());cache=json.loads((R/'results/cache.json').read_text())
 modifications=[];members=[]
 for key,g in cache.items():
  changed=[cid for cid in g['ids']if by[cid]['imputed_point']]
  if not changed:continue
  points=[by[cid]['raw_points_1024x512']if cid in changed else by[cid]['effective_points_1024x512'] for cid in g['ids']]
  n=len(points);counts=np.array([len(p)for p in points]);ds={k:np.zeros((n,n))for k in ['ospa1','ospa2','hausdorff','bottleneck','count_diff']}
  for i,j in itertools.combinations(range(n),2):
   f=lp.features(lp.angular(points[i],points[j]))
   for k in ds:
    val=abs(counts[i]-counts[j])if k=='count_diff'else f[k]
    ds[k][i,j]=ds[k][j,i]=val if np.isfinite(val)else 180.
  for cid in changed:
   x=by[cid];modifications.append(dict(id=cid,image_id=x['image_id'],code=g['code'],worker=x['worker_id'],raw_count=x['raw_point_count'],previous_count=x['effective_point_count'],retained=True))
  g['Ds']={k:v.tolist()for k,v in ds.items()};g['counts']=counts.tolist()
  for name,D,cut in lp.config_matrices(ds):
   l=lp.cluster(D,cut);g['labels'][name]=l.tolist()
   for i,cid in enumerate(g['ids']):members.append(dict(key=key,code=g['code'],method=name,id=cid,worker=g['workers'][i],point_count=counts[i],cluster=int(l[i])))
 out=[]
 for key,g in cache.items():
  N=len(g['ids']);iid,cond=key.split('|');O=np.array(g['Ds']['ospa1']);H=np.array(g['Ds']['hausdorff'])
  AO=O<=6.;np.fill_diagonal(AO,False)
  for k in [2,4,8,12,16]:
   if k>=N:continue
   def none(A):return float(np.mean([math.comb(N-1-int(v),k)/math.comb(N-1,k)if N-1-int(v)>=k else 0. for v in A.sum(1)]))
   for t in [6,9,12]:
    AH=H<=t;np.fill_diagonal(AH,False)
    po=none(AO);ph=none(AH);pn=none(AO|AH)
    out.append(dict(code=g['code'],image_id=iid,condition=cond,N=N,k=k,local_radius=t,ospa_uncovered=po,local_uncovered=ph,ospa_covered_but_local_uncovered=ph-pn,local_covered_but_ospa_uncovered=po-pn,borrowed_points_removed=any(x in g['ids']for x in [m['id']for m in modifications])))
 pd.DataFrame(modifications).to_csv(R/'results/no_borrowed_changes.csv',index=False)
 pd.DataFrame(members).to_csv(R/'results/no_borrowed_changed_memberships.csv',index=False)
 pd.DataFrame(out).to_csv(R/'results/no_borrowed_next_person.csv',index=False)
 (R/'results/cache_no_borrowed.json').write_text(json.dumps(cache,separators=(',',':')))
 z=pd.DataFrame(out).query('N>=19 and k==8 and local_radius==9')
 print(z.groupby('condition')[['ospa_uncovered','local_uncovered','ospa_covered_but_local_uncovered']].mean().to_string())
 assert len(modifications)==2
if __name__=='__main__':run()
