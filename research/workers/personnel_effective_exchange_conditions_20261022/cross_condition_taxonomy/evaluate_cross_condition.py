#!/usr/bin/env python3
"""Frozen raw-response checks; evaluate Manual and Semi separately."""
import os
for v in ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS'):os.environ[v]='1'
import json, time
import numpy as np
import pandas as pd
from discover_cross_condition import HERE,PREVIOUS,REPO,HIST,CONDITIONS,PREFIX,FAMILIES,DOMAIN_FIELDS,save,js,sha
import evaluate_raw_behavior as old_eval

OUTCOMES=HIST+['B8L2_peer_delta','D10_peer_delta','log_time_peer_delta']

def model_specs(method,condition):
 exact=[v for domain in FAMILIES[method]['domains'] for v in DOMAIN_FIELDS[domain]]
 pre=PREFIX[condition]
 own=[pre+'_'+v for v in HIST]
 if method=='XCOND_GEOM_QT':own += [pre+'_'+v for v in ['q_history','q_downside','t_history']]
 models={
  'source':([],[]),'old_primary_coarse':([],['old_coarse']),'old_primary_fine':([],['old_fine']),
  'v3_own_behavior_coarse':([],['v3_behavior_coarse']),'v3_own_behavior_fine':([],['v3_behavior_fine']),
  'cross_coarse':([],['cross_coarse']),'cross_fine':([],['cross_fine']),
  'continuous_own_same_domains':(own,[]),'continuous_cross_exact':(exact,[]),
  'own_continuous_plus_cross_fine':(own,['cross_fine']),
  'cross_exact_plus_cross_fine':(exact,['cross_fine']),
 }
 if method=='XCOND_GEOM_QT':
  models.update({'v3_own_joint_coarse':([],['v3_joint_coarse']),'v3_own_joint_fine':([],['v3_joint_fine']),
   'continuous_own_QT':([pre+'_'+v for v in ['q_history','q_downside','t_history']],[])})
 if method=='XCOND_PAIRED':models['continuous_own_paired_exact']=([f'paired_{pre}_{v}' for v in HIST],[])
 return models

def metrics(y,pred,d):
 z=d[['image_id','reference_id']].copy();z['sq']=(pred-y)**2;z['abs']=abs(pred-y)
 return old_eval.mean_image(z,'sq'),old_eval.mean_image(z,'abs')

def summarize(per,keys):
 out=[]
 for vals,g in per.groupby(keys+['outcome','model'],dropna=False):
  out.append(dict(zip(keys+['outcome','model'],vals),buildings=g.heldout_building.nunique(),test_records=int(g.test_records.sum()),
   test_images=int(g.test_images.sum()),mse=float(g.mse.mean()),mae=float(g.mae.mean())))
 s=pd.DataFrame(out);base=s[s.model.eq('source')][keys+['outcome','mse']].rename(columns={'mse':'source_mse'})
 s=s.merge(base,on=keys+['outcome'],validate='many_to_one');s['r2_vs_source']=1-s.mse/s.source_mse
 return s

def increments(per,keys,comparisons):
 out=[]
 for vals,g in per.groupby(keys+['outcome'],dropna=False):
  for baseline,alternative in comparisons:
   a=g[g.model.eq(baseline)].set_index('heldout_building').mse
   b=g[g.model.eq(alternative)].set_index('heldout_building').mse
   z=pd.concat([a.rename('baseline'),b.rename('alternative')],axis=1).dropna()
   if not len(z):continue
   delta=(z.baseline-z.alternative).to_numpy();rng=np.random.default_rng(2026102203)
   bt=np.mean(rng.choice(delta,size=(3000,len(delta)),replace=True),axis=1)
   out.append(dict(zip(keys+['outcome'],vals),baseline=baseline,alternative=alternative,buildings=len(z),
    mse_baseline=z.baseline.mean(),mse_alternative=z.alternative.mean(),mse_reduction=delta.mean(),
    relative_mse_reduction=1-z.alternative.mean()/z.baseline.mean(),ci_lo=np.quantile(bt,.025),ci_hi=np.quantile(bt,.975),
    improved_buildings=int((delta>0).sum()),worse_buildings=int((delta<0).sum())))
 return pd.DataFrame(out)

def main():
 start=time.time();frozen=sha(HERE/'LABEL_FREEZE.json');assert json.loads((HERE/'LABEL_FREEZE.json').read_text())['status']=='frozen_before_target_endpoint_evaluation'
 x=pd.read_csv(PREVIOUS/'BEHAVIOR_RECORDS.csv.gz');x=x[x.behavior_usable&x.layer.eq('ordinary')].copy()
 labels=pd.read_csv(HERE/'CROSS_LABELS_LOBO.csv.gz');features=pd.read_csv(HERE/'FEATURES_LOBO.csv.gz')
 v3=pd.read_csv(PREVIOUS/'ALL_METHOD_LABELS_LOBO.csv.gz');old=pd.read_csv(HERE/'OLD_METHOD_LABELS_TARGET_MAPS.csv.gz')
 rows=[];support=[];inputrows=[]
 for method in FAMILIES:
  for condition in CONDITIONS:
   for outer in sorted(x.loc[x.condition.eq(condition),'building_id'].unique()):
    fs=features[features.heldout_building.eq(outer)].drop(columns=['heldout_building','origin'])
    z=x[x.condition.eq(condition)].merge(fs,on='worker_id',validate='many_to_one')
    ll=labels[(labels.method==method)&(labels.condition==condition)&(labels.heldout_building==outer)]
    z=z.merge(ll[['worker_id','coarse_label','fine_label','known','selection_status']].rename(columns={'coarse_label':'cross_coarse','fine_label':'cross_fine','known':'cross_known'}),on='worker_id',validate='many_to_one')
    for mid,pref in [('V3_BEHAVIOR','v3_behavior'),('V3_JOINT_QT','v3_joint')]:
     lab=v3[(v3.method==mid)&(v3.condition==condition)&(v3.heldout_building==outer)]
     z=z.merge(lab[['worker_id','coarse_label','fine_label','known']].rename(columns={'coarse_label':pref+'_coarse','fine_label':pref+'_fine','known':pref+'_known'}),on='worker_id',validate='many_to_one')
    pri=old[(old.method==('M_structure' if condition=='manual' else 'SP_scale'))&(old.condition==condition)&(old.heldout_building==outer)]
    for tier in ['coarse','fine']:
     a=pri[pri.tier.eq(tier)][['worker_id','class_id','known']].rename(columns={'class_id':'old_'+tier,'known':'old_'+tier+'_known'})
     z=z.merge(a,on='worker_id',validate='many_to_one')
    models=model_specs(method,condition)
    mask=z.cross_known & z.v3_behavior_known & z.old_coarse_known & z.old_fine_known
    if method=='XCOND_GEOM_QT':mask &= z.v3_joint_known
    z=z[mask].copy();required=sorted({v for numeric,_ in models.values() for v in numeric});z=z.dropna(subset=required)
    support.append(dict(method=method,condition=condition,heldout_building=outer,selection_status=ll.selection_status.iloc[0],workers=z.worker_id.nunique(),
     target_records=int(z.building_id.eq(outer).sum()),target_images=z.loc[z.building_id.eq(outer),'image_id'].nunique(),
     input_conditions='manual|semi',same_records_for_all_models=True))
    for model,(num,cat) in models.items():inputrows.append(dict(method=method,condition=condition,heldout_building=outer,model=model,numeric_fields='|'.join(num),categorical_fields='|'.join(cat)))
    for outcome in OUTCOMES:
     zz=z[z[outcome].notna()];tr=zz[zz.building_id.ne(outer)];te=zz[zz.building_id.eq(outer)]
     if len(tr)<60 or len(te)<6:continue
     for model,(num,cat) in models.items():
      pred=old_eval.fit_predict(tr,te,num,cat,outcome);mse,mae=metrics(te[outcome].to_numpy(),pred,te)
      rows.append(dict(method=method,condition=condition,heldout_building=outer,outcome=outcome,model=model,selection_status=ll.selection_status.iloc[0],
       train_records=len(tr),test_records=len(te),test_images=te.image_id.nunique(),test_workers=te.worker_id.nunique(),mse=mse,mae=mae))
   save(pd.DataFrame(rows),'RAW_RESPONSE_BUILDINGS_CHECKPOINT.csv.gz');save(pd.DataFrame(support),'RAW_RESPONSE_SUPPORT.csv')
   print('evaluated',method,condition,'rows',len(rows),flush=True)
 per=pd.DataFrame(rows);save(per,'RAW_RESPONSE_BUILDINGS.csv.gz');save(summarize(per,['method','condition']),'RAW_RESPONSE_SUMMARY.csv')
 comparisons=[('cross_coarse','cross_fine'),('v3_own_behavior_fine','cross_fine'),('old_primary_fine','cross_fine'),
  ('v3_own_joint_fine','cross_fine'),('continuous_own_same_domains','continuous_cross_exact'),
  ('continuous_own_same_domains','cross_fine'),('continuous_cross_exact','cross_fine'),
  ('continuous_own_same_domains','own_continuous_plus_cross_fine'),('continuous_cross_exact','cross_exact_plus_cross_fine'),
  ('continuous_own_paired_exact','continuous_cross_exact')]
 save(increments(per,['method','condition'],comparisons),'RAW_RESPONSE_INCREMENTS.csv');save(pd.DataFrame(inputrows),'RAW_RESPONSE_MODEL_FIELDS.csv.gz')
 # Direct same-person/image condition-response test. No attempt to mix Manual
 # and Semi fusion endpoints; these are paired raw-annotation differences.
 p=pd.read_csv(HERE/'PAIRED_INPUT_RECORDS.csv.gz');p['source_time_comparable']=p.time_source_kind_m.eq(p.time_source_kind_s)
 for v in ['B8L2','D10']:p['pair_delta_raw_'+v]=p[v+'_s']-p[v+'_m']
 p['pair_delta_raw_log_seconds']=np.log(p.source_active_time_seconds_s.where(p.source_time_comparable))-np.log(p.source_active_time_seconds_m.where(p.source_time_comparable))
 outcomes=['pair_delta_raw_'+v for v in HIST]+['pair_delta_raw_B8L2','pair_delta_raw_D10','pair_delta_raw_log_seconds']
 pairedrows=[];pairsupport=[]
 for method in FAMILIES:
  for outer in sorted(p.building_id.unique()):
   fs=features[features.heldout_building.eq(outer)].drop(columns=['heldout_building','origin'])
   # These feature names also occur as record targets in p: reserve the record
   # values only for outcomes, and all history features get their own suffix.
   ff=fs.rename(columns={c:c+'_historyfit' for c in fs if c!='worker_id'})
   z=p.merge(ff,on='worker_id',validate='many_to_one')
   ll=labels[(labels.method==method)&labels.condition.eq('manual')&labels.heldout_building.eq(outer)]
   z=z.merge(ll[['worker_id','coarse_label','fine_label','known']].rename(columns={'coarse_label':'cross_coarse','fine_label':'cross_fine','known':'cross_known'}),on='worker_id',validate='many_to_one')
   for cond,pre in [('manual','m'),('semi','s')]:
    q=v3[v3.method.eq('V3_BEHAVIOR')&v3.condition.eq(cond)&v3.heldout_building.eq(outer)]
    z=z.merge(q[['worker_id','fine_label','known']].rename(columns={'fine_label':pre+'_class','known':pre+'_class_known'}),on='worker_id',validate='many_to_one')
   ownm=['m_'+v+'_historyfit' for v in HIST];owns=['s_'+v+'_historyfit' for v in HIST]
   exact=[v+'_historyfit' for dom in FAMILIES[method]['domains'] for v in DOMAIN_FIELDS[dom]]
   models={'source':([],[]),'single_Manual_class':([],['m_class']),'single_Semi_class':([],['s_class']),
    'two_single_condition_classes':([],['m_class','s_class']),'cross_coarse':([],['cross_coarse']),'cross_fine':([],['cross_fine']),
    'continuous_Manual_history':(ownm,[]),'continuous_Semi_history':(owns,[]),'continuous_both_geometry':(ownm+owns,[]),
    'continuous_cross_exact':(exact,[]),'exact_plus_cross_fine':(exact,['cross_fine'])}
   required=sorted({v for num,_ in models.values() for v in num});z=z[z.cross_known&z.m_class_known&z.s_class_known].dropna(subset=required)
   pairsupport.append(dict(method=method,heldout_building=outer,workers=z.worker_id.nunique(),target_pairs=int(z.building_id.eq(outer).sum()),target_images=z.loc[z.building_id.eq(outer),'image_id'].nunique()))
   for outcome in outcomes:
    zz=z[z[outcome].notna()];tr=zz[zz.building_id.ne(outer)];te=zz[zz.building_id.eq(outer)]
    if len(tr)<60 or len(te)<6:continue
    for model,(num,cat) in models.items():
     pred=old_eval.fit_predict(tr,te,num,cat,outcome);mse,mae=metrics(te[outcome].to_numpy(),pred,te)
     pairedrows.append(dict(method=method,heldout_building=outer,outcome=outcome,model=model,train_records=len(tr),test_records=len(te),test_images=te.image_id.nunique(),test_workers=te.worker_id.nunique(),mse=mse,mae=mae))
  save(pd.DataFrame(pairedrows),'PAIRED_RESPONSE_BUILDINGS_CHECKPOINT.csv.gz')
  print('paired evaluated',method,flush=True)
 pp=pd.DataFrame(pairedrows);save(pp,'PAIRED_RESPONSE_BUILDINGS.csv.gz');save(pd.DataFrame(pairsupport),'PAIRED_RESPONSE_SUPPORT.csv')
 save(summarize(pp,['method']),'PAIRED_RESPONSE_SUMMARY.csv')
 save(increments(pp,['method'],[('single_Manual_class','cross_fine'),('single_Semi_class','cross_fine'),('two_single_condition_classes','cross_fine'),
  ('continuous_Manual_history','continuous_both_geometry'),('continuous_Semi_history','continuous_both_geometry'),('continuous_both_geometry','continuous_cross_exact'),
  ('continuous_cross_exact','cross_fine'),('continuous_cross_exact','exact_plus_cross_fine')]),'PAIRED_RESPONSE_INCREMENTS.csv')
 assert frozen==sha(HERE/'LABEL_FREEZE.json')
 js('RAW_EVALUATION_RECEIPT.json',dict(label_freeze_sha256=frozen,code_sha256=sha(__file__),seconds=time.time()-start,
  model='fixed ridge .01, intercept unpenalized and source indicator in each model; exact prior evaluator',
  weighting='reference opportunities then images then buildings equal; every model per method/condition/outcome shares exact train/test records',
  label_and_features='both-condition target-building exclusions; no target-derived member features',
  interpretation='raw response and relative source-compatible time prediction, not equivalent percentage time savings; separate condition endpoints',
  paired_target='same-worker/image/reference raw S−M; already-explored data, not randomized causal condition contrast',
  rows=len(per),paired_rows=len(pp),new_team_fusions=0,new_quality_scores=0))
if __name__=='__main__':main()
