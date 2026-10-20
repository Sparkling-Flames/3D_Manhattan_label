"""Independent discovery reaggregation and paired building uncertainty.
No model fitting or researcher module imports.
"""
from pathlib import Path
import pandas as pd,numpy as np,json,hashlib
B=Path('/workspace/shared/interchangeability_audit_20261020');D=B/'audit_corner/discovery_evaluation';O=B/'audit_statistics/discovery_legacy';O.mkdir(exist_ok=True)
f=pd.concat([pd.read_csv(x) for x in sorted((B/'audit_corner/discovery_endpoints').glob('*.csv.gz'))],ignore_index=True);f=f[(f.entrant_origin_a=='new')&(f.entrant_origin_b=='new')].copy();f['distance']=((f.bev_mean_pairscale+f.top_mean_pairscale)/2).where(f.status=='unique_cyclic_candidate');f['distance9']=f.distance.where(f.angle_deg<=9);f['distance12']=f.distance.where(f.angle_deg<=12);f['distance_valid']=f.distance.notna().astype(float);f['incomplete']=(~f.complete).astype(float);f['different_count']=(f.status=='different_corner_count').astype(float)
labels=pd.read_csv(B/'audit_learning/corner_fit_legacy/worker_labels.csv');r=pd.read_csv(D/'DISCOVERY_BUILDINGS.csv').set_index(['method_id','building']);pr=pd.read_csv(D/'PAIRED_BASELINE_BUILDINGS.csv.gz');err=[];out=[]
K=['building','pool_id','k','background_id'];metrics=['distance','distance9','distance12','distance_valid','incomplete','different_count']
def table(df,mp):
 z=df[df.worker_a.isin(mp)&df.worker_b.isin(mp)].copy();z['same']=z.worker_a.map(mp)==z.worker_b.map(mp);return {m:z.groupby(K+['same'])[m].mean().unstack('same') for m in metrics}
def reduce(t,keep):return t.loc[keep].groupby(['building','pool_id','k']).mean().groupby(['building','pool_id']).mean().groupby('building').mean()
feat=pd.read_csv(B/'unpacked/interchangeability_20261020/forward/features_train.csv.gz').set_index('worker_id');rev=pd.read_csv(B/'unpacked/interchangeability_20261020/reverse/mixed_fit/worker_labels.csv.gz');rev=rev[rev.method_id.eq('R_directswap_geometry_partition_b2_K2__ordinary_new__mixed_history_v1')&rev.known];rm=dict(zip(rev.worker_id,rev.class_id))
for mid,g in labels.groupby('method_id'):
 g=g[g.known].sort_values('worker_id');mp=dict(zip(g.worker_id,g.class_id));ct=table(f,mp);workers=g.worker_id.tolist();counts=g.class_id.value_counts().sort_index().to_numpy();controls={'Rnew2':{w:rm[w] for w in workers}}
 for name,col in [('Q','q_beta'),('T','t_source_origin_effect')]:
  ordered=sorted(workers,key=lambda w:(feat.loc[w,col],w));cuts=np.cumsum(counts);controls[name+'_same_capacity']={w:int(np.searchsorted(cuts,i,side='right')) for i,w in enumerate(ordered)}
 for m,t in ct.items():
  keep=t.index[t.notna().all(axis=1)];v=reduce(t,keep)
  for b,rr in v.iterrows():
   for same,arm in [(False,'between'),(True,'within')]:
    col=arm+'_'+('allanchors_' if m in ['distance_valid','incomplete','different_count'] else '')+m;value=r.loc[(mid,b),col];e=abs(rr[same]-value);assert e<1e-9,(mid,b,col,e);err.append(e)
 for baseline,bl in controls.items():
  bt=table(f,bl);rr=pr[(pr.method_id==mid)&(pr.baseline==baseline)].set_index('building')
  for m,t in ct.items():
   u=bt[m];keep=t.index[t.notna().all(axis=1)].intersection(u.index[u.notna().all(axis=1)]);a=reduce(t,keep);b=reduce(u,keep)
   for building in a.index:
    for same,arm in [(False,'between'),(True,'within')]:
     col=arm+'_'+('allanchors_' if m in ['distance_valid','incomplete','different_count'] else '')+m
     for prefix,val in [('candidate_',a.loc[building,same]),('baseline_',b.loc[building,same]),('delta_',a.loc[building,same]-b.loc[building,same])]:
      e=abs(val-rr.loc[building,prefix+col]);assert e<1e-9,(mid,baseline,building,prefix+col,e);err.append(e)
# Full paired raw arithmetic check; summarize 40random labels inside each building.
for c in [c for c in pr if c.startswith('delta_')]:assert np.allclose(pr[c],pr['candidate_'+c[6:]]-pr['baseline_'+c[6:]],equal_nan=True,atol=1e-10)
pr['baseline_family']=pr.baseline.where(~pr.baseline.str.startswith('random_'),'same_capacity_random');rng=np.random.default_rng(20261020)
for (mid,baseline),g in pr.groupby(['method_id','baseline_family']):
 cols=['delta_within_distance','delta_distance_gap','delta_within_allanchors_distance_valid','delta_within_allanchors_different_count','delta_within_allanchors_incomplete'];bb=g.groupby('building')[cols].mean()
 for m in cols:
  x=bb[m].dropna().to_numpy();dist=x[rng.integers(0,len(x),(50000,len(x)))].mean(axis=1) if len(x)>=3 else np.array([np.nan]);out.append(dict(method_id=mid,baseline=baseline,metric=m,buildings=len(x),draws=g.baseline.nunique(),estimate=x.mean(),ci025=np.quantile(dist,.025),ci975=np.quantile(dist,.975)))
pd.DataFrame(out).to_csv(O/'DISCOVERY_PAIRED_BOOTSTRAP.csv',index=False)
receipt=dict(events=len(f),images=f.pool_id.nunique(),buildings=f.building.nunique(),event_level_checked_values=len(err),max_error=max(err),paired_arithmetic_pass=True,source='Independent pandas reductions from discovery event rows and six frozen labels; primary and angle-specific candidate/baseline common supports; random uncertainty clustered by building, not permutation count')
(O/'DISCOVERY_STATS_RECEIPT.json').write_text(json.dumps(receipt,indent=2));print(receipt)
