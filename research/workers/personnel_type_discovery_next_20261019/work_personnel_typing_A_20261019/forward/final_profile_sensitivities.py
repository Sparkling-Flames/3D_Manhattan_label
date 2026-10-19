#!/usr/bin/env python3
"""Fixed-choice D10, source-time threshold and difficulty-support descriptions.

This step makes no model choice and does not read replacement outcomes.
"""
from pathlib import Path
import hashlib,json
import numpy as np
import pandas as pd
from sklearn.metrics import adjusted_rand_score
from atomic_exports import csv_verified

P=Path(__file__).resolve().parent
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def safe(x):
    if isinstance(x,dict):return {str(k):safe(v)for k,v in x.items()}
    if isinstance(x,(list,tuple)):return [safe(v)for v in x]
    if isinstance(x,(np.integer,)):return int(x)
    if isinstance(x,(np.bool_,)):return bool(x)
    if isinstance(x,(float,np.floating)):return float(x)if np.isfinite(x)else None
    return x
def js(n,x):(P/n).write_text(json.dumps(safe(x),ensure_ascii=False,indent=2,allow_nan=False)+'\n')
def timebin(s,a,b):
    return pd.Series(np.select([s.isna(),s<a,s<b],['unknown','fast','middle'],default='slow'),index=s.index)

def main():
    b=pd.read_csv(P/'selected_classes_by_fold.csv.gz')
    d=pd.read_csv(P/'candidate_classes_by_fold_D10.csv.gz')
    keys=['fold_id','candidate_method','difficulty','worker_id']
    d=d.rename(columns={'method_id':'candidate_method','class_id':'D10_class_id'})
    j=b.merge(d[keys+['D10_class_id']],on=keys,how='left',validate='many_to_one')
    assert len(j)==len(b) and j.D10_class_id.notna().all()
    dout=b.copy();dout['B8_frozen_class_id']=dout.class_id;dout['class_id']=j.D10_class_id.to_numpy();dout['history_quality_metric']='D10'
    csv_verified(dout,P/'selected_classes_by_fold_D10.csv.gz')
    rows=[]
    for (fold,method,diff),g in j.groupby(['fold_id','method_id','difficulty']):
        known=g.class_id.ne('unknown')&g.D10_class_id.ne('unknown');h=g[known]
        a=h.class_id.to_numpy();c=h.D10_class_id.to_numpy();ii=np.triu_indices(len(h),1)
        sa=a[ii[0]]==a[ii[1]];sb=c[ii[0]]==c[ii[1]]
        rows.append({'fold_id':fold,'method_id':method,'candidate_method':g.candidate_method.iloc[0],'difficulty':diff,
                     'K':int(g.K.iloc[0]),'n_workers':len(g),'known_B8':int(g.class_id.ne('unknown').sum()),
                     'known_D10':int(g.D10_class_id.ne('unknown').sum()),'known_both':len(h),'support_status_changed':int((g.class_id.eq('unknown')!=g.D10_class_id.eq('unknown')).sum()),
                     'known_pairs':len(sa),'same_class_relation_changed_fraction':float(np.mean(sa!=sb)),
                     'ARI':float(adjusted_rand_score(a,c)),'same_pair_jaccard':float(np.sum(sa&sb)/np.sum(sa|sb))if np.any(sa|sb)else None})
    pd.DataFrame(rows).to_csv(P/'selected_metric_sensitivity.csv',index=False)
    features=pd.read_csv(P/'fold_features.csv.gz');full=features[features.fold_id.eq('FULL')].copy()
    timecols=['fold_id','heldout_building','train_key','worker_id','person_origin','t_supported','t_records','t_images','t_buildings','time_source_kind','source_time_n','source_time_median','source_time_p10','source_time_p90','t_source_origin_effect','t_log_residual_tail','target_time_n','target_time_images','target_time_median']
    tf=features[timecols].copy()
    tf['source_median_T60_180']=timebin(tf.source_time_median,60,180);tf['source_median_T90_240']=timebin(tf.source_time_median,90,240)
    tf['fixed_threshold_label_changed']=tf.source_median_T60_180.ne(tf.source_median_T90_240)
    tf['source_time_analysis_scope']='eligible ordinary Manual source-task time pool; Q qualification is a separate gate'
    csv_verified(tf,P/'fixed_time_threshold_profiles.csv.gz')
    ts=[]
    for (fold,origin),g in tf.groupby(['fold_id','person_origin']):
        known=g.source_time_median.notna();s=g[known]
        ts.append({'fold_id':fold,'person_origin':origin,'workers':len(g),'observed_source_median_workers':int(known.sum()),'relative_time_supported_workers':int(g.t_supported.sum()),
                   'n_label_changed':int(s.fixed_threshold_label_changed.sum()),'changed_fraction_observed':s.fixed_threshold_label_changed.mean(),
                   'T60_180_counts':json.dumps(s.source_median_T60_180.value_counts().to_dict(),sort_keys=True),
                   'T90_240_counts':json.dumps(s.source_median_T90_240.value_counts().to_dict(),sort_keys=True),
                   'target_matched_time_workers':int(g.target_time_n.gt(0).sum())})
    pd.DataFrame(ts).to_csv(P/'fixed_time_threshold_stability.csv',index=False)
    records=pd.read_csv(P/'records_flat.csv')
    trows=[]
    time_eligible=records[records.pool_analysis_eligible&records.condition.eq('manual')&records.ordinary_difficulty_eligible&records.difficulty.isin(['easy','medium','hard'])]
    for scope,df in [('inventory',records),('quality',records[records.quality_usable]),('ordinary_manual',records[records.quality_usable&records.condition.eq('manual')&records.quality_use.eq('ordinary_primary')]),('ordinary_manual_time_eligible',time_eligible)]:
        for (origin,source),g in df.groupby(['origin','time_source_kind'],dropna=False):
            s=pd.to_numeric(g.source_active_time_seconds,errors='coerce').dropna();target=pd.to_numeric(g.target_matched_time_seconds,errors='coerce').dropna()
            trows.append({'scope':scope,'origin':origin,'time_source_kind':source,'inventory_records':len(g),'source_time_records':len(s),'target_time_records':len(target),
                          'source_median':s.median(),'source_mean':s.mean(),'source_p10':s.quantile(.1),'source_p90':s.quantile(.9),'source_p95':s.quantile(.95),'source_p99':s.quantile(.99),'source_max':s.max(),
                          'target_median':target.median(),'source_T60_180_counts':json.dumps(timebin(s,60,180).value_counts().to_dict(),sort_keys=True),'source_T90_240_counts':json.dumps(timebin(s,90,240).value_counts().to_dict(),sort_keys=True)})
    pd.DataFrame(trows).to_csv(P/'time_source_coverage_and_tails.csv',index=False)
    ordinary=records[records.quality_usable&records.condition.eq('manual')&records.quality_use.eq('ordinary_primary')].copy()
    ordinary['pair_count_band']=pd.cut(ordinary.declared_pair_count,[-np.inf,3,4,6,np.inf],labels=['up_to_3','4','5_to_6','7_plus']).astype(str)
    tr=[]
    time_eligible=time_eligible.copy();time_eligible['pair_count_band']=pd.cut(time_eligible.declared_pair_count,[-np.inf,3,4,6,np.inf],labels=['up_to_3','4','5_to_6','7_plus']).astype(str)
    for scope,frame in [('ordinary_manual_quality',ordinary),('ordinary_manual_time_eligible',time_eligible)]:
        for (origin,source,diff,pairs),g in frame.groupby(['origin','time_source_kind','difficulty','pair_count_band'],dropna=False,observed=True):
            s=g.source_active_time_seconds.dropna()
            tr.append({'scope':scope,'origin':origin,'time_source_kind':source,'difficulty':diff,'pair_count_band':pairs,'records':len(g),'images':g.image_id.nunique(),'buildings':g.building_id.nunique(),'workers':g.worker_id.nunique(),'valid_source_time_records':len(s),'median_source_seconds':s.median(),'p90_source_seconds':s.quantile(.9)})
    pd.DataFrame(tr).to_csv(P/'time_difficulty_structure_strata.csv',index=False)
    dcols=['worker_id','person_origin','q_beta','q_abs_mean','q_abs_p10','q_abs_sd','core_images','core_buildings']
    for diff in ['easy','medium','hard']:dcols += [f'{diff}_images',f'{diff}_buildings',f'{diff}_supported',f'absolute_{diff}_mean',f'absolute_{diff}_p10',f'theta_{diff}',f'theta_{diff}_estimate']
    dcols += ['hard_minus_easy','hard_minus_medium','medium_minus_easy']
    dp=full[dcols].copy();outer=features[features.fold_id.ne('FULL')]
    for name in ['q_beta','theta_easy','theta_medium','theta_hard','hard_minus_easy','hard_minus_medium']:
        stats=outer.groupby('worker_id')[name].agg(n_folds='count',min='min',max='max',positive_fraction=lambda s:float(s.dropna().gt(0).mean())if s.notna().any()else np.nan)
        stats=stats.add_prefix(name+'_leave_building_out_')
        dp=dp.merge(stats,left_on='worker_id',right_index=True,validate='one_to_one')
    dp['uncertainty_interpretation']='leave-one-building-out fitted-history perturbation range; overlapping fits, not an independent confidence interval or heldout task success rate'
    dp.to_csv(P/'difficulty_adaptation_profiles.csv',index=False)
    js('FINAL_PROFILE_SENSITIVITY_RECEIPT.json',{'status':'COMPLETE','selected_D10_rows':len(dout),'B8_selected_classes_sha256':sha(P/'selected_classes_by_fold.csv.gz'),
      'D10_candidate_source_sha256':sha(P/'candidate_classes_by_fold_D10.csv.gz'),'D10_selected_classes_sha256':sha(P/'selected_classes_by_fold_D10.csv.gz'),
      'metric_sensitivity_rows':len(rows),'D10_changed_only':'historical Q and difficulty scoring with same train sets and B8-selected family/K; no new fusion or D10 model selection',
      'time_threshold_definitions':'source median <60 / [60,180) / >=180; <90 / [90,240) / >=240; missing remains unknown; exploratory sensitivity, not adopted thresholds',
      'thresholds_used_to_reselect_types':False,'difficulty_perturbations_are_confidence_intervals':False,'replacement_outcomes_read':False})
    print('COMPLETE',len(dout),len(rows))
if __name__=='__main__':main()
