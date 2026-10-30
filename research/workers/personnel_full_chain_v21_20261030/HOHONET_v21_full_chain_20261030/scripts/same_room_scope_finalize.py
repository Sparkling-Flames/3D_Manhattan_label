"""Keep the frozen v2 support and separately report relation OOS-pending edges.

The frozen relation registry says scope_comparable alone does not clear
oos_pending. Four legacy use-panel edges have that flag; no relation is edited.
"""
from pathlib import Path
import json,sys
import pandas as pd
import numpy as np
ROOT=Path(__file__).resolve().parents[1];SRC=ROOT/'source';OUT=ROOT/'stage02_same_room/prediction'
sys.path.insert(0,str(SRC/'research/same_room/same_room_profile_return_review_20261021/pro/room_similarity/code'))
import run_similarity as rs
def save(d,p):d.to_csv(p,index=False,compression={'method':'gzip','compresslevel':3,'mtime':0} if str(p).endswith('.gz') else 'infer')
def wcorr(x,y,w):
 x,y,w=map(np.asarray,(x,y,w));ok=np.isfinite(x)&np.isfinite(y)&np.isfinite(w);x,y,w=x[ok],y[ok],w[ok]
 if len(x)<3:return np.nan
 w=w/w.sum();x=x-(w*x).sum();y=y-(w*y).sum();den=np.sqrt((w*x*x).sum()*(w*y*y).sum());return (w*x*y).sum()/den if den>1e-12 else np.nan
rel=json.loads((SRC/'research/same_room/relation_adoption_20261016/relations.json').read_text());rm={tuple(sorted([r['image_a'],r['image_b']])):r for r in rel}
scopes=['legacy_combined','ordinary_no_relation_oos_pending','relation_oos_pending']
means=[];people=[];predsumm=[];mean_hist=[];matchedsum=[];support=[];rec=[]
for label in ['v2_frozen','v21_on_v2_records','v21_all']:
 out=OUT/label;dp=pd.read_csv(out/'DIRECT_PAIRS.csv');pending=dp.drop_duplicates('pair_id').set_index('pair_id').oos_pending.to_dict()
 mean=pd.read_csv(out/'DIRECT_MEAN_VALUES.csv.gz');pp=pd.read_csv(out/'DIRECT_PERSON_VALUES.csv.gz');ps=pd.read_csv(out/'PERSON_PAIR_REPETITION.csv')
 pred=pd.read_csv(out/'PERSON_PREDICTION_VALUES.csv.gz');target=pd.read_csv(out/'PERSON_PREDICTION_TARGETS.csv.gz');wt=pd.read_csv(out/'PERSON_PREDICTION_TARGET_WORKERS.csv.gz')
 cache={}
 for target_image,sources in pred[['target_image','source_images']].drop_duplicates().itertuples(index=False,name=None):
  rr=[rm.get(tuple(sorted([target_image,src]))) for src in sources.split('|')]
  assert all(r and r['physical_adopted'] and r['scope_comparable'] and not r['substantive_conflict'] for r in rr),(target_image,sources)
  cache[target_image,sources]=any(r['oos_pending'] for r in rr)
 pred['relation_oos_pending']=[cache[i,s] for i,s in zip(pred.target_image,pred.source_images)]
 gkeys=['metric','budget','building','group_id','target_image','m','N']
 gg=pred.groupby(gkeys).relation_oos_pending.agg(['first','nunique']).reset_index();assert gg['nunique'].eq(1).all()
 gs=gg[gkeys+['first']].rename(columns={'first':'relation_oos_pending'});target=target.merge(gs,on=gkeys,validate='many_to_one');wt=wt.merge(gs,on=gkeys,validate='many_to_one')
 save(gs,out/'PREDICTION_RELATION_SCOPE.csv.gz')
 mh=pd.read_csv(out/'MEAN_HISTORY_BUILDINGS.csv');mhv=pd.read_csv(out/'MEAN_HISTORY_VALUES.csv.gz',usecols=['metric','panel','group_id','building_id','target_image','history'])
 mhv['relation_oos_pending']=[any(rm[tuple(sorted([i,src]))]['oos_pending'] for src in h.split('|')) for i,h in zip(mhv.target_image,mhv.history)]
 mb=mhv.groupby(['building_id']).relation_oos_pending.agg(['first','nunique']);assert mb['nunique'].eq(1).all();mh['relation_oos_pending']=mh.building_id.map(mb['first'])
 for scope in scopes:
  test=lambda s:np.ones(len(s),bool) if scope=='legacy_combined' else s if scope=='relation_oos_pending' else ~s
  z=mean[test(mean.pair_id.map(pending))];bparts=[]
  for method in ['external_image_mean','outside_roster_mean','outside_peer_roster_mean','source_mean','peer_adjusted_source','common_source']:
   v=z.copy();actual=v.common_actual if method=='common_source' else v.actual;v['ae']=(v[method]-actual).abs();v['bias']=v[method]-actual;v['bad10']=np.where(v.ae.notna(),v.ae>10,np.nan)
   tt=v.groupby(['metric','building','target_image']).agg(mae=('ae','mean'),bias=('bias','mean'),bad10=('bad10','mean'),directions=('source_image','size')).reset_index();b=tt.groupby(['metric','building']).agg(mae=('mae','mean'),bias=('bias','mean'),bad10=('bad10','mean'),images=('target_image','nunique'),directions=('directions','sum')).reset_index();b['method']=method;bparts.append(b)
  b=pd.concat(bparts,ignore_index=True);b['scope']=scope;b['scenario']=label;save(b,out/('DIRECT_MEAN_BUILDINGS_'+scope+'.csv'))
  su=b.groupby(['metric','method']).agg(mae=('mae','mean'),bias=('bias','mean'),bad10=('bad10','mean'),images=('images','sum'),directions=('directions','sum'),buildings=('building','nunique')).reset_index();su['scenario']=label;su['scope']=scope
  bw=b.pivot(index=['metric','building'],columns='method',values='mae');gain=bw.external_image_mean-bw.source_mean
  su['buildings_source_better_than_external']=[int((gain.loc[m]>0).sum()) for m in su.metric];means.append(su)
  s=pp[test(pp.pair_id.map(pending))]
  for metric,dd in s.groupby('metric'):
   pr=ps[ps.metric.eq(metric)&ps.pair_id.isin(dd.pair_id)];w=1/(dd.groupby('building').pair_id.transform('nunique')*dd.groupby('pair_id').worker_id.transform('size'))
   wr=dd.groupby(['worker_id','building']).same_relative_sign.mean().groupby('worker_id').mean()
   row=dict(scenario=label,scope=scope,metric=metric,pairs=dd.pair_id.nunique(),images=len(set(dd.image_a)|set(dd.image_b)),buildings=dd.building.nunique(),persons=dd.worker_id.nunique(),person_pairs=len(dd),surprise_valid_person_pairs=int(dd.surprise_a.notna().sum()),positive_rank_pairs=int(pr.rank_rho.gt(0).sum()),valid_rank_pairs=int(pr.rank_rho.notna().sum()),persons_repeat_gt_half=int(wr.gt(.5).sum()),same_relative_sign=pr.groupby('building').same_relative_sign.mean().mean(),chance_relative_sign=pr.groupby('building').chance_relative_sign.mean().mean())
   for c in ['Q','relative','surprise']:row['symmetric_corr_'+c]=wcorr(np.r_[dd[c+'_a'],dd[c+'_b']],np.r_[dd[c+'_b'],dd[c+'_a']],np.r_[w,w])
   people.append(row)
  t=target[test(target.relation_oos_pending)]
  bs=[]
  for budget,x in t.groupby('budget'):
   for stage in (['minimum_majority','maximum_history'] if budget=='majority' else ['single']):
    x1=x[x.m.eq(x.N//2+1 if stage=='minimum_majority' else x.N-1)] if budget=='majority' else x
    im=x1.groupby(['metric','budget','building','target_image','method']).agg(mae=('mae','mean'),mse=('mse','mean'),bias=('bias','mean'),bad20=('bad20','mean'),rho=('rho','mean'),workers=('workers','mean')).reset_index();bb=im.groupby(['metric','budget','building','method']).agg(mae=('mae','mean'),mse=('mse','mean'),bias=('bias','mean'),bad20=('bad20','mean'),rho=('rho','mean'),images=('target_image','nunique')).reset_index();bb['stage']=stage;bs.append(bb)
  bs=pd.concat(bs,ignore_index=True);bs['scope']=scope;bs['scenario']=label;save(bs,out/('PERSON_PREDICTION_BUILDINGS_'+scope+'.csv'))
  su=bs.groupby(['metric','budget','stage','method']).agg(mae=('mae','mean'),mse=('mse','mean'),bias=('bias','mean'),bad20=('bad20','mean'),rho=('rho','mean'),images=('images','sum'),buildings=('building','nunique')).reset_index();su['scenario']=label;su['scope']=scope
  cs=[]
  for r in su.itertuples():
   zz=pred[pred.metric.eq(r.metric)&pred.budget.eq(r.budget)&pred.all_methods_supported&test(pred.relation_oos_pending)]
   if r.budget=='majority':zz=zz[zz.m.eq(zz.N//2+1 if r.stage=='minimum_majority' else zz.N-1)]
   cs.append((zz.target_object_id.nunique(),zz.worker_id.nunique(),len(zz)))
  su[['unique_target_answers','unique_people','prediction_rows']]=cs;predsumm.append(su)
  if scope=='legacy_combined':save(su.drop(columns=['scope','scenario']),out/'PERSON_PREDICTION_SUMMARY.csv')
  mm=mh[test(mh.relation_oos_pending)];sm=mm.groupby(['metric','panel','method','stage']).agg(mae=('mae','mean'),mse=('rmse2','mean'),bad10=('bad10','mean'),bad15=('bad15','mean'),images=('images','sum'),buildings=('building_id','nunique')).reset_index();sm['scenario']=label;sm['scope']=scope;mean_hist.append(sm)
  matching=pd.read_csv(out/'MATCHED_UNKNOWN_CONTROLS.csv.gz');matching=matching[test(matching.pair_id.map(pending))];dpp=dp[test(dp.pair_id.map(pending))]
  _,ms,dirs=rs.summaries(dpp,matching);ms['scenario']=label;ms['scope']=scope;matchedsum.append(ms);save(dirs,out/('MATCHED_DIRECTIONS_'+scope+'.csv.gz'))
  support.append(dict(scenario=label,scope=scope,direct_pairs=z.pair_id.nunique(),images=len(set(z.source_image)|set(z.target_image)),buildings=z.building.nunique(),person_pairs=int(len(s)/2),unique_people=s.worker_id.nunique()))
 # Save exact four flagged legacy edges, without adjudicating them.
 rr=dp[dp.metric.eq('B8L2')&dp.origin.eq('all')&dp.condition.eq('manual')&dp.layer.eq('ordinary')&dp.scope_comparable&~dp.substantive_conflict&dp.n_common.ge(4)&dp.oos_pending].copy();rr['scenario']=label;rec.append(rr)
 print('SCOPE_DONE',label,flush=True)
save(pd.concat(means,ignore_index=True),OUT/'DIRECT_MEAN_SUMMARY_BY_SCOPE.csv');save(pd.DataFrame(people),OUT/'PERSONAL_SIMILARITY_BY_SCOPE.csv');save(pd.concat(predsumm,ignore_index=True),OUT/'PERSON_PREDICTION_SUMMARY_BY_SCOPE.csv');save(pd.concat(mean_hist,ignore_index=True),OUT/'MEAN_HISTORY_SUMMARY_BY_SCOPE.csv');save(pd.concat(matchedsum,ignore_index=True),OUT/'MATCHED_UNKNOWN_SUMMARY_BY_SCOPE.csv');save(pd.DataFrame(support),OUT/'SUPPORT_BY_SCOPE.csv');save(pd.concat(rec,ignore_index=True),OUT/'RELATION_PENDING_EDGES.csv')
(OUT/'RELATION_SCOPE_CHECKS.json').write_text(json.dumps(dict(flagged_legacy_pairs=4,relationship_flags_unchanged=True,legacy_combined_preserved=True,main_scope='ordinary and scope_comparable and no substantive_conflict and no relation_oos_pending',no_inferred_OOS_adjudication=True,prediction_source_target_relations_all_direct=True,no_new_fusion=True),ensure_ascii=False,indent=2))
