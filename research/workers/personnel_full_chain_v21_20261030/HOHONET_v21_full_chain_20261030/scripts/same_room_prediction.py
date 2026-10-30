"""Recover v2 same-room mean/personal-use chain with current v2.1 records.

Three separate supports: frozen v2; current scores on v2 original records;
all currently eligible primary records. Direct relations and original history
panels are reused. No transitive room relation or new team/fusion is created.
"""
from pathlib import Path
import importlib.util,sys,json,gzip,itertools
import numpy as np
import pandas as pd
from scipy.stats import spearmanr
ROOT=Path(__file__).resolve().parents[1];SRC=ROOT/'source';OUT=ROOT/'stage02_same_room/prediction';OUT.mkdir(parents=True,exist_ok=True)
OLD=SRC/'research/same_room/same_room_profile_return_review_20261021/pro'
sys.path.insert(0,str(OLD/'room_similarity/code'))
import common as legacy_common
import run_similarity as legacy_similarity
import run_mean_prediction as legacy_mean
sp=importlib.util.spec_from_file_location('legacy_personal',OLD/'personal_similarity/analyze.py');personal=importlib.util.module_from_spec(sp);sp.loader.exec_module(personal)
def save(d,p):
 p=Path(p);p.parent.mkdir(parents=True,exist_ok=True);t=p.with_name(p.name+'.tmp');d.to_csv(t,index=False,compression={'method':'gzip','compresslevel':3,'mtime':0} if str(p).endswith('.gz') else None);t.replace(p)
personal.save=save
def wcorr(x,y,w):
 x,y,w=map(np.asarray,(x,y,w));v=np.isfinite(x)&np.isfinite(y)&np.isfinite(w);x,y,w=x[v],y[v],w[v]
 if len(x)<3:return np.nan
 w=w/w.sum();x=x-np.sum(w*x);y=y-np.sum(w*y);den=np.sqrt(np.sum(w*x*x)*np.sum(w*y*y));return np.sum(w*x*y)/den if den>1e-12 else np.nan
def enrich(q):
 q=q.copy();q['building']=q.building_id;q['task_key']=q.image_id+'|'+q.condition+'|'+q.reference_id+'|'+q.reference_version
 for m in ['B8L2','D10']:
  g=q.groupby('task_key')[m];n=g.transform('count');s=g.transform('sum');q['peer_'+m]=((s-q[m])/(n-1)).where(n>1);q['relative_'+m]=q[m]-q['peer_'+m];q['rank_'+m]=g.rank(pct=True)
 return q
def histories(q,metric):
 out={}
 for c in q.condition.unique():
  for b in q.building.unique():
   z=q[q.condition.eq(c)&q.layer.eq('ordinary')&q.training_allowed&~q.building.eq(b)].copy()
   # Peer levels use the same admitted historical candidate pool, excluding self.
   gg=z.groupby('task_key')[metric];nn=gg.transform('size');ss=gg.transform('sum');z['theta']=(z[metric]-(ss-z[metric])/(nn-1)).where(nn>1)
   out[c,b]=z.groupby('worker_id').agg(ext_abs=(metric,'mean'),theta=('theta','mean'),history_images=('image_id','nunique'),history_buildings=('building','nunique'))
 return out
raw,oldq,rels,declared,candidates=legacy_common.load(SRC)
oldq=enrich(oldq)
inv=pd.read_json(SRC/'research/data/releases/v2.1/quality_inventory.json').set_index('object_id');current=raw.set_index('object_id').copy()
for c in ['B8L2','D10','quality_usable','quality_use','pool_analysis_eligible','reference_id','reference_version','chosen_target_id','current_class']:
 current[c]=inv[c].reindex(current.index)
dr=json.loads((SRC/'research/data/releases/v2.1/difficulty_records.json').read_text())['records'];dm={r['image_id']:r for r in dr}
current['current_target_id']=current.image_id.map({i:r.get('target_version') for i,r in dm.items()});current['target_aligned']=current.chosen_target_id.eq(current.current_target_id)
for c in ['N_floor','N_turn','H','conditional_difficulty']:current[c]=current.image_id.map({i:r.get(c) for i,r in dm.items()})
gate=current.pool_analysis_eligible&current.quality_usable&~current.is_oos&current.target_aligned&current.quality_use.isin(['ordinary_primary','doorway_quality'])
current['formal_quality']=gate;newq=enrich(current[gate].reset_index())
assert len(newq[newq.condition.eq('manual')&newq.layer.eq('ordinary')])==6512
assert not newq.duplicated(['image_id','condition','worker_id']).any()
oldids=set(oldq.object_id);newids=set(newq.object_id);removed=oldids-newids
save(newq,OUT/'CURRENT_FORMAL_RECORDS.csv.gz');save(oldq,OUT/'V2_FORMAL_RECORDS.csv.gz')
scenarios={'v2_frozen':oldq,'v21_on_v2_records':enrich(newq[newq.object_id.isin(oldids)]),'v21_all':newq}
all_summary=[];personal_summary=[];direct_summary=[];support=[]
gs=[g for g in json.loads((SRC/'research/same_room/same_room_multiview_20261020/GROUPS.json').read_text()) if g['metric']=='B8L2' and g['origin']=='all' and g['layer']=='ordinary']
assert len(gs)==9
for label,q in scenarios.items():
 out=OUT/label;out.mkdir(exist_ok=True);print('SCENARIO',label,len(q),flush=True)
 im=legacy_similarity.image_table(q);pairs,cov=legacy_similarity.pairs(q,rels,im)
 save(pairs,out/'DIRECT_PAIRS.csv');save(cov,out/'RELATION_COVERAGE.csv')
 pri=pairs[pairs.condition.eq('manual')&pairs.origin.eq('all')&pairs.layer.eq('ordinary')&pairs.scope_comparable&~pairs.substantive_conflict&pairs.n_common.ge(4)]
 support.append(dict(scenario=label,formal_records=len(q),ordinary_manual_records=int((q.condition.eq('manual')&q.layer.eq('ordinary')).sum()),direct_pairs=pri[pri.metric.eq('B8L2')].pair_id.nunique(),images=len(set(pri.image_a)|set(pri.image_b)),buildings=pri.building_id.nunique()))
 # Same-room public mean prediction, using original hierarchy (sources -> target -> building).
 mr=[];people=[];pairperson=[];hist_by_metric={m:histories(q,m) for m in ['B8L2','D10']}
 cells={(c,i):z.set_index('worker_id') for (c,i),z in q.groupby(['condition','image_id'])}
 for r in pri.itertuples():
  metric=r.metric;b=r.building_id;h=hist_by_metric[metric]['manual',b];tq=q[q.condition.eq('manual')&q.layer.eq('ordinary')&q.training_allowed&~q.building.eq(b)];pop=tq.groupby('image_id')[metric].mean().mean()
  for s,t in [(r.image_a,r.image_b),(r.image_b,r.image_a)]:
   aa=cells['manual',s];bb=cells['manual',t];common=aa.index.intersection(bb.index)
   mr.append(dict(pair_id=r.pair_id,pair_index=r.pair_index,metric=metric,building=b,groups=r.user_group_ids,source_image=s,target_image=t,source_n=len(aa),target_n=len(bb),common_n=len(common),actual=bb[metric].mean(),source_mean=aa[metric].mean(),external_image_mean=pop,outside_roster_mean=bb.index.map(h.ext_abs).to_numpy().mean(),outside_peer_roster_mean=pop+bb.index.map(h.theta).to_numpy().mean(),peer_adjusted_source=aa[metric].mean()+bb.index.map(h.theta).to_numpy().mean()-aa.index.map(h.theta).to_numpy().mean(),common_actual=bb.loc[common,metric].mean(),common_source=aa.loc[common,metric].mean(),source_object_ids='|'.join(aa.object_id),target_object_ids='|'.join(bb.object_id),source_reference=aa.reference_id.iloc[0],target_reference=bb.reference_id.iloc[0],history_candidate_records=len(tq),history_buildings=tq.building.nunique()))
  aa=cells['manual',r.image_a];bb=cells['manual',r.image_b];ws=sorted(aa.index.intersection(bb.index));qa=aa.loc[ws,metric].to_numpy();qb=bb.loc[ws,metric].to_numpy();ra=aa.loc[ws,'relative_'+metric].to_numpy();rb=bb.loc[ws,'relative_'+metric].to_numpy();theta=h.reindex(ws).theta.to_numpy()
  for j,w in enumerate(ws):people.append(dict(metric=metric,pair_id=r.pair_id,pair_index=r.pair_index,building=b,groups=r.user_group_ids,image_a=r.image_a,image_b=r.image_b,worker_id=w,object_a=aa.loc[w,'object_id'],object_b=bb.loc[w,'object_id'],Q_a=qa[j],Q_b=qb[j],relative_a=ra[j],relative_b=rb[j],theta=theta[j],surprise_a=ra[j]-theta[j],surprise_b=rb[j]-theta[j],same_relative_sign=(ra[j]>=0)==(rb[j]>=0)))
  pairperson.append(dict(metric=metric,pair_id=r.pair_id,building=b,n_common=len(ws),rank_rho=spearmanr(qa,qb).statistic if np.std(qa)>0 and np.std(qb)>0 else np.nan,same_relative_sign=np.mean((ra>=0)==(rb>=0)),chance_relative_sign=np.mean(ra>=0)*np.mean(rb>=0)+(1-np.mean(ra>=0))*(1-np.mean(rb>=0))))
 mean=pd.DataFrame(mr);pp=pd.DataFrame(people);ps=pd.DataFrame(pairperson);save(mean,out/'DIRECT_MEAN_VALUES.csv.gz');save(pp,out/'DIRECT_PERSON_VALUES.csv.gz');save(ps,out/'PERSON_PAIR_REPETITION.csv')
 for metric,s in pp.groupby('metric'):
  w=1/(s.groupby('building').pair_id.transform('nunique')*s.groupby('pair_id').worker_id.transform('size'))
  pr=ps[ps.metric.eq(metric)];wr=s.groupby(['worker_id','building']).same_relative_sign.mean().groupby('worker_id').mean()
  row=dict(scenario=label,metric=metric,pairs=s.pair_id.nunique(),images=len(set(s.image_a)|set(s.image_b)),buildings=s.building.nunique(),persons=s.worker_id.nunique(),person_pairs=len(s),surprise_valid_person_pairs=int(s.surprise_a.notna().sum()),positive_rank_pairs=int(pr.rank_rho.gt(0).sum()),valid_rank_pairs=int(pr.rank_rho.notna().sum()),persons_repeat_gt_half=int(wr.gt(.5).sum()),same_relative_sign=pr.groupby('building').same_relative_sign.mean().mean(),chance_relative_sign=pr.groupby('building').chance_relative_sign.mean().mean())
  for c in ['Q','relative','surprise']:row['symmetric_corr_'+c]=wcorr(np.r_[s[c+'_a'],s[c+'_b']],np.r_[s[c+'_b'],s[c+'_a']],np.r_[w,w])
  personal_summary.append(row);save(wr.rename('building_equal_same_sign').reset_index(),out/('PERSON_REPETITION_'+metric+'.csv'))
 allb=[]
 for method in ['external_image_mean','outside_roster_mean','outside_peer_roster_mean','source_mean','peer_adjusted_source','common_source']:
  v=mean.copy();actual=v.common_actual if method=='common_source' else v.actual;v['ae']=(v[method]-actual).abs();v['bias']=v[method]-actual;v['bad10']=np.where(v.ae.notna(),v.ae>10,np.nan)
  t=v.groupby(['metric','building','target_image']).agg(mae=('ae','mean'),bias=('bias','mean'),bad10=('bad10','mean'),directions=('source_image','size')).reset_index();b=t.groupby(['metric','building']).agg(mae=('mae','mean'),bias=('bias','mean'),bad10=('bad10','mean'),images=('target_image','nunique'),directions=('directions','sum')).reset_index();b['method']=method;allb.append(b)
 b=pd.concat(allb,ignore_index=True);save(b,out/'DIRECT_MEAN_BUILDINGS.csv');su=b.groupby(['metric','method']).agg(mae=('mae','mean'),bias=('bias','mean'),bad10=('bad10','mean'),images=('images','sum'),directions=('directions','sum'),buildings=('building','nunique')).reset_index();su['scenario']=label;direct_summary.append(su)
 # Reuse the original historical subsets and both original mean support definitions.
 meanrows=[];folds=[]
 for metric in ['B8L2','D10']:
  qm=q[q.condition.eq('manual')&q.layer.eq('ordinary')]
  for panel in ['actual_pool','common_workers']:
   for outer in sorted({g['building'] for g in gs}):
    test=legacy_mean.build_rows(qm,gs,metric,panel,outer,False)
    if test.empty:continue
    train=legacy_mean.build_rows(qm,gs,metric,panel,outer,True);estimates,coefs=legacy_mean.fit_one(train,test)
    for co in coefs:folds.append(dict(scenario=label,metric=metric,panel=panel,held_building=outer,**co))
    z=test.copy()
    for method in legacy_mean.METHODS:z['pred_'+method]=np.clip(test[method].to_numpy() if method in test else estimates[method],0,100)
    meanrows.append(z)
 wide=pd.concat(meanrows,ignore_index=True);methods=['pred_'+m for m in legacy_mean.METHODS];wide['all_methods_supported']=wide[methods].notna().all(axis=1);save(wide,out/'MEAN_HISTORY_VALUES.csv.gz');save(pd.DataFrame(folds),out/'MEAN_CALIBRATION_FOLDS.csv')
 long=[]
 for method in legacy_mean.METHODS:
  z=wide[wide.all_methods_supported].copy();z['method']=method;z['predicted']=z['pred_'+method];z['error']=z.predicted-z.actual;z['absolute_error']=z.error.abs();z['squared_error']=z.error**2;z['bad10']=z.absolute_error>10;z['bad15']=z.absolute_error>15;long.append(z.drop(columns=methods))
 targ,gr,bld,sm=legacy_mean.aggregate(pd.concat(long,ignore_index=True));save(targ,out/'MEAN_HISTORY_TARGETS.csv.gz');save(gr,out/'MEAN_HISTORY_GROUPS.csv');save(bld,out/'MEAN_HISTORY_BUILDINGS.csv');sm['scenario']=label;all_summary.append(sm)
 # Predict individuals on frozen original target/history panel plus supported direct pairs.
 # Strong baseline and the fixed half-own residual rule are precisely the old specifications.
 primary=pp[pp.metric.eq('B8L2')].copy();primary['pair_id']=primary.pair_index
 p,srcmap=personal.make_base(q,SRC,primary,out)
 predparts=[]
 for metric in ['B8L2','D10']:
  manual=q[q.condition.eq('manual')&q.layer.eq('ordinary')].set_index(['image_id','worker_id']);md=manual.to_dict('index');hist=hist_by_metric[metric]
  rows=[];cache={}
  for r in p.itertuples():
   key=(r.building,r.source_images,r.worker_id)
   if key not in cache:
    sr=[md[i,r.worker_id] for i in r.source_images.split('|')];h=hist['manual',r.building];theta=h.theta.get(r.worker_id,np.nan);ea=h.ext_abs.get(r.worker_id,np.nan);pe=float(np.mean([z['peer_'+metric] for z in sr]));own=float(np.mean([z[metric] for z in sr]));sur=own-pe-theta
    cache[key]=dict(external_abs=ea,own_source=own,public_source=pe,theta=theta,own_surprise=sur,public_external=float(np.clip(pe+theta,0,100)),public_external_halfown=float(np.clip(pe+theta+.5*sur,0,100)),history_images=h.history_images.get(r.worker_id,0),history_buildings=h.history_buildings.get(r.worker_id,0))
   rows.append(dict(row_id=r.row_id,metric=metric,actual=md[r.target_image,r.worker_id][metric],**cache[key]))
  f=pd.DataFrame(rows);z=p.merge(f,on='row_id',validate='one_to_one');z['all_methods_supported']=z[['external_abs','own_source','public_source','public_external','public_external_halfown']].notna().all(axis=1);predparts.append(z)
 pred=pd.concat(predparts,ignore_index=True);save(pred,out/'PERSON_PREDICTION_VALUES.csv.gz')
 wtparts=[]
 for method in ['external_abs','own_source','public_source','public_external','public_external_halfown']:
  z=pred[pred.all_methods_supported].copy();z['ae']=(z[method]-z.actual).abs();z['se']=(z[method]-z.actual)**2;z['bias']=z[method]-z.actual;z['bad20']=z.ae>20
  keys=['metric','budget','building','group_id','target_image','worker_id','target_object_id','m','N']
  wt=z.groupby(keys,dropna=False).agg(mae=('ae','mean'),mse=('se','mean'),bias=('bias','mean'),bad20=('bad20','mean'),actual=('actual','first'),prediction=(method,'mean'),histories=('row_id','size')).reset_index();wt['method']=method;wtparts.append(wt)
 wt=pd.concat(wtparts,ignore_index=True);save(wt,out/'PERSON_PREDICTION_TARGET_WORKERS.csv.gz')
 target=wt.groupby(['metric','budget','building','group_id','target_image','m','N','method']).agg(mae=('mae','mean'),mse=('mse','mean'),bias=('bias','mean'),bad20=('bad20','mean'),workers=('worker_id','nunique')).reset_index()
 # Per-history within-image rank correlation, followed by identical target/building weighting.
 ranks=[];methods=['external_abs','own_source','public_source','public_external','public_external_halfown']
 for k,z in pred[pred.all_methods_supported].groupby(['metric','budget','building','group_id','target_image','m','N','split_id']):
  if len(z)<3:continue
  rr=z[['actual']+methods].rank().to_numpy(float);rr-=np.nanmean(rr,axis=0);den=np.sqrt((rr[:,0]**2).sum()*(rr[:,1:]**2).sum(axis=0));rho=np.divide((rr[:,0,None]*rr[:,1:]).sum(axis=0),den,out=np.full(len(methods),np.nan),where=den>1e-12)
  for met,v in zip(methods,rho):ranks.append(dict(zip(['metric','budget','building','group_id','target_image','m','N'],k[:-1]),method=met,rho=v))
 rk=pd.DataFrame(ranks).groupby(['metric','budget','building','group_id','target_image','m','N','method']).rho.mean().reset_index();target=target.merge(rk,how='left');save(target,out/'PERSON_PREDICTION_TARGETS.csv.gz')
 bs=[]
 for budget,t in target.groupby('budget'):
  for stage in (['minimum_majority','maximum_history'] if budget=='majority' else ['single']):
   x=t[t.m.eq(t.N//2+1 if stage=='minimum_majority' else t.N-1)] if budget=='majority' else t
   im=x.groupby(['metric','budget','building','target_image','method']).agg(mae=('mae','mean'),mse=('mse','mean'),bias=('bias','mean'),bad20=('bad20','mean'),rho=('rho','mean'),workers=('workers','mean')).reset_index();b=im.groupby(['metric','budget','building','method']).agg(mae=('mae','mean'),mse=('mse','mean'),bias=('bias','mean'),bad20=('bad20','mean'),rho=('rho','mean'),images=('target_image','nunique'),target_workers=('workers','sum')).reset_index();b['stage']=stage;bs.append(b)
 bs=pd.concat(bs,ignore_index=True);save(bs,out/'PERSON_PREDICTION_BUILDINGS.csv');sm=bs.groupby(['metric','budget','stage','method']).agg(mae=('mae','mean'),mse=('mse','mean'),bias=('bias','mean'),bad20=('bad20','mean'),rho=('rho','mean'),images=('images','sum'),target_workers=('target_workers','sum'),buildings=('building','nunique')).reset_index();save(sm,out/'PERSON_PREDICTION_SUMMARY.csv')
 sm=sm.rename(columns={'target_workers':'weighted_worker_support_sum'})
 counts=[]
 for r in sm.itertuples():
  z=pred[pred.metric.eq(r.metric)&pred.budget.eq(r.budget)&pred.all_methods_supported]
  if r.budget=='majority':z=z[z.m.eq(z.N//2+1 if r.stage=='minimum_majority' else z.N-1)]
  counts.append((z.target_object_id.nunique(),z.worker_id.nunique(),len(z)))
 sm[['unique_target_answers','unique_people','prediction_rows']]=counts
 save(sm,out/'PERSON_PREDICTION_SUMMARY.csv')
 # Frozen matching rules: same declared difficulty, N_turn, H; same three-image roster.
 matched=legacy_similarity.matched_unknown(q,rels,pairs,im if 'image_id' in im.columns else legacy_similarity.image_table(q))
 _,ms,dirs=legacy_similarity.summaries(pairs,matched);save(matched,out/'MATCHED_UNKNOWN_CONTROLS.csv.gz');save(ms,out/'MATCHED_UNKNOWN_SUMMARY.csv');save(dirs,out/'MATCHED_UNKNOWN_DIRECTIONS.csv.gz')
 print('DONE',label,len(pp),len(pred),flush=True)
save(pd.DataFrame(support),OUT/'SUPPORT.csv');save(pd.concat(direct_summary,ignore_index=True),OUT/'DIRECT_MEAN_SUMMARY.csv');save(pd.DataFrame(personal_summary),OUT/'PERSONAL_SIMILARITY_SUMMARY.csv');save(pd.concat(all_summary,ignore_index=True),OUT/'MEAN_HISTORY_SUMMARY.csv')
checks=dict(current_formal_records=len(newq),old_formal_records=len(oldq),old_records_removed=sorted(removed),direct_relation_version='same_room_user_working_classification_20261016_v2',new_transitive_relations=0,history_groups=9,history_group_identity='original frozen groups and split IDs',new_fusion_calls=0,original_training_admission_unchanged=True,personal_increment_rule='old fixed public + outside-person theta + 0.5*own source residual; no tuning on target outcomes',scenarios=list(scenarios),quality_missing_never_zero=True)
(OUT/'CHECKS.json').write_text(json.dumps(checks,ensure_ascii=False,indent=2));print(json.dumps(checks,ensure_ascii=False),flush=True)
