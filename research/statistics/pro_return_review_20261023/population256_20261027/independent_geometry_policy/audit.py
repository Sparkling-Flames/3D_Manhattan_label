import argparse, json, numpy as np, pandas as pd
from pathlib import Path
ap=argparse.ArgumentParser();ap.add_argument('--input-root',type=Path,required=True);ap.add_argument('--output',type=Path);args=ap.parse_args();R=args.input_root;out=args.output or R/'independent_geometry_policy';out.mkdir(parents=True,exist_ok=True)
G=R/'analysis_geometry26/results_stage2'
p=pd.read_csv(G/'GEOMETRY_PATH_PRECISION.csv.gz')
i=pd.read_csv(G/'GEOMETRY_PAIRED_INTERVAL_PRECISION.csv.gz')
s=pd.read_csv(G/'GEOMETRY_FIXED_SUPPORT_INTERVALS.csv.gz')
key=['pool_id','cohort','metric']
a=p.rename(columns={'k':'k_from','mean':'value_from'});b=p.rename(columns={'k':'k_to','mean':'value_to'})
t=i.merge(a[key+['k_from','value_from']],on=key+['k_from'],validate='many_to_one').merge(b[key+['k_to','value_to']],on=key+['k_to'],validate='many_to_one')
np.testing.assert_allclose(t.delta,t.value_to-t.value_from,rtol=1e-10,atol=1e-12,equal_nan=True)
records=[]
for (layer,difficulty,kfrom,kto) in [('ordinary_manual','\u56f0\u96be',20,30),('doorway','\u5355\u5217',20,30),('doorway','\u5355\u5217',6,10)]:
 # Identify exact doorway spelling from metadata.
 if layer=='doorway': layer=[v for v in i.layer.unique() if v!='ordinary_manual'][0]
 q=i[(i.layer==layer)&(i.pool_n>=30 if kfrom==20 else i.pool_n>=10)&(i.k_from==kfrom)&(i.k_to==kto)&(i.metric=='V_floor')]
 if layer=='ordinary_manual':q=q[q.difficulty==difficulty]
 keep=q.pivot(index='pool_id',columns='cohort',values='delta')[['old48','stage1_104','stage2_104','new208','pooled256']].notna().all(axis=1)
 q=q[q.pool_id.isin(keep.index[keep])]
 for cohort,g in q.groupby('cohort'):
  bm=g.groupby('building').delta.mean()
  records.append(dict(layer=layer,difficulty=difficulty,k_from=kfrom,k_to=kto,cohort=cohort,images=len(g),buildings=len(bm),estimate=g.delta.mean(),building_equal=bm.mean(),decrease=int((g.delta< -1e-9).sum()),increase=int((g.delta>1e-9).sum()),building_decrease=int((bm< -1e-9).sum()),path_mcse=np.sqrt((g.mcse**2).sum())/len(g)))
d=pd.DataFrame(records);d.to_csv(out/'GEOMETRY_REAGG.csv',index=False)
print('geometry',len(p),len(i),'interval identities passed');print(d.to_string(index=False))
# Reconstruct policy k statistics from all saved paired event rows, not author aggregates.
P=R/'analysis_policy26/results'
e=pd.read_csv(P/'EXACT_PAIRED_EVENTS.csv.gz',low_memory=False)
assert not e.duplicated(['version','policy','pool_id','base_path_id','k']).any()
base=e.groupby(['version','policy','pool_id']).base_path_id.nunique();assert (base==16).all()
metrics=['paired_Q_delta','paired_D10_delta','Q_p10_delta_common','Q_sd_delta_common_ddof1','labor_ratio_legal','QT_paired_Q_delta','actual_consensus_failure_delta','output_generated_unscorable_delta','reference_unavailable_delta']
rows=[]
for version in ['old16','new16','pooled32']:
 z=e if version=='pooled32' else e[e.version==version]
 for (pid,policy,k),g in z.groupby(['pool_id','policy','k'],sort=False):
  q=g.B8L2_natural.notna()&g.B8L2_policy.notna(); nq=g.loc[q,'B8L2_natural'];pq=g.loc[q,'B8L2_policy']
  tm=q&(g.source_time_total_seconds_natural>0)&(g.source_time_total_seconds_policy>0)&g.labor_kind_natural.eq(g.labor_kind_policy)
  x={'pool_id':pid,'policy':policy,'version':version,'k':k,'paired_Q_delta':(pq-nq).mean(),'paired_D10_delta':(g.loc[q,'D10_policy']-g.loc[q,'D10_natural']).mean(),'Q_p10_delta_common':pq.quantile(.1)-nq.quantile(.1),'Q_sd_delta_common_ddof1':pq.std(ddof=1)-nq.std(ddof=1),'labor_ratio_legal':(g.loc[tm,'source_time_total_seconds_policy']/g.loc[tm,'source_time_total_seconds_natural']).mean(),'QT_paired_Q_delta':(g.loc[tm,'B8L2_policy']-g.loc[tm,'B8L2_natural']).mean()}
  for st in ['actual_consensus_failure','output_generated_unscorable','reference_unavailable']:
   x[st+'_delta']=(g[st+'_policy'].astype(float)-g[st+'_natural'].astype(float)).mean()
  rows.append(x)
k=pd.DataFrame(rows).set_index(['pool_id','policy','version','k']).sort_index();saved=pd.read_csv(P/'POLICY_IMAGE_K.csv.gz').set_index(k.index.names).sort_index();assert k.index.equals(saved.index)
for m in metrics:np.testing.assert_allclose(k[m],saved[m],rtol=1e-10,atol=1e-9,equal_nan=True)
print('policy event/k checks',len(e),len(k),len(metrics))
f=pd.read_csv(P/'FIXED_SUPPORT.csv.gz');f=f[f.metric.isin(metrics)]
phase=[]
for rr in f.itertuples():
 ks=[int(x) for x in str(rr.matched_k_list).split('|') if x!='nan' and x]
 val=k.loc[(rr.pool_id,rr.policy,rr.version)].reindex(ks)[rr.metric].to_numpy()
 estimate=np.mean(val) if len(val) else np.nan
 np.testing.assert_allclose(estimate,rr.point,rtol=1e-10,atol=1e-9,equal_nan=True)
 phase.append(dict(pool_id=rr.pool_id,policy=rr.policy,version=rr.version,phase=rr.phase,metric=rr.metric,value=estimate,k_count=len(ks)))
phase=pd.DataFrame(phase).merge(pd.read_csv(R/'analysis_policy26/COMMON_IMAGES.csv')[['pool_id','building']],on='pool_id',validate='many_to_one')
summary=[]
for (policy,version,ph,m),g in phase.groupby(['policy','version','phase','metric']):
 g=g[g.value.notna()];bmean=g.groupby('building').value.mean()
 for w,v in [('image_equal',g.value.mean()),('building_equal',bmean.mean())]:
  summary.append(dict(policy=policy,version=version,phase=ph,metric=m,weighting=w,estimate=v,images=len(g),buildings=len(bmean),positive=int((g.value>1e-9).sum()),negative=int((g.value< -1e-9).sum())))
summary=pd.DataFrame(summary);summary.to_csv(out/'POLICY_REAGG.csv',index=False)
saved=pd.read_csv(P/'POLICY_PRECISION_SUMMARY.csv');saved=saved[saved.difficulty=='\u5168\u90e8'];joined=summary.merge(saved,on=['policy','version','phase','metric','weighting'],suffixes=('_audit','_saved'),validate='one_to_one')
np.testing.assert_allclose(joined.estimate_audit,joined.estimate_saved,rtol=1e-10,atol=1e-9,equal_nan=True)
assert (joined.images_audit==joined.images_saved).all() and (joined.buildings_audit==joined.buildings_saved).all()
assert (joined.positive==joined.positive_images).all() and (joined.negative==joined.negative_images).all()
print('phase rows',len(phase),'summary checks',len(joined));print(summary[(summary.phase=='early_3_to_half')&(summary.weighting=='image_equal')&summary.metric.isin(['paired_Q_delta','labor_ratio_legal','QT_paired_Q_delta'])].to_string(index=False))
(out/'AUDIT_COUNTS.json').write_text(json.dumps(dict(geometry_points=len(p),geometry_intervals=len(i),policy_events=len(e),policy_k_rows=len(k),policy_metrics=metrics,phase_rows=len(phase),summary_rows=len(joined)),indent=2))

