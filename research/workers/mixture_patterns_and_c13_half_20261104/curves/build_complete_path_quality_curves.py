"""A fixed image AND fixed complete-path curve for Figure 1; reuses saved inputs."""
import pandas as pd,numpy as np
from analyze_existing_natural_paths import OUT,ROOT,STRATA,save,summarize

def main():
 p=pd.read_csv(OUT/'PATH_OUTCOMES.csv.gz');p=p[p.anchor.eq(6)]
 e=pd.read_csv(OUT/'LANDMARK_IMAGE_PAIRED_EFFECTS.csv.gz');e=e[e.anchor.eq(6)&e.min_arm_paths.eq(16)&e.metric.eq('Q_mean_complete_paths')&e.effect.notna()]
 allowed=set(zip(e.method,e.pool_id))
 inv=pd.read_csv(OUT/'NATURAL_SOURCE_POOLS.csv');inv=inv[inv.pool_n.ge(20)]
 pg={k:g for k,g in p.groupby('pool_id')};rows=[]
 for r in inv.itertuples():
  d=pd.read_csv(ROOT/r.path,usecols=['path_id','stratum','k','B8L2','D10']);d=d[d.stratum.isin(STRATA)&d.k.between(6,20)]
  d['path_key']=d.stratum.astype(str)+'::'+d.path_id.astype(str)
  q=d.pivot(index='path_key',columns='k',values='B8L2');dd=d.pivot(index='path_key',columns='k',values='D10')
  for m,g in pg[r.pool_id].groupby('method'):
   if (m,r.pool_id) not in allowed:continue
   g=g[g.complete_path.eq(1)]
   a=g[g.highest_present.eq(1)].path_key.tolist();b=g[g.highest_present.eq(0)].path_key.tolist()
   assert len(a)>0 and len(b)>0 and q.loc[a+b].notna().all().all()
   for metric,z in [('Q_complete',q),('D10_complete',dd)]:
    av=z.loc[a].mean();bv=z.loc[b].mean()
    for k in range(6,21):rows.append(dict(method=m,pool_id=r.pool_id,image=r.image,building=r.building,difficulty=r.difficulty,
      anchor=6,min_arm_paths=16,paths_with=len(a),paths_without=len(b),k=k,metric=metric,with_value=av[k],without_value=bv[k],effect=av[k]-bv[k]))
 z=pd.DataFrame(rows);save('LANDMARK_COMPLETE_PATH_CURVE_IMAGE_EFFECTS.csv.gz',z)
 summarize(z,['method','anchor','min_arm_paths','k'],name='LANDMARK_COMPLETE_PATH_CURVE_SUMMARY.csv')
 for (m,pool),g in z[z.metric.eq('Q_complete')].groupby(['method','pool_id']):
  original=e[e.method.eq(m)&e.pool_id.eq(pool)].effect.iloc[0]
  assert abs(original-g.effect.mean())<1e-10
 print('Complete-path curves verified',len(z),'rows')
if __name__=='__main__':main()
