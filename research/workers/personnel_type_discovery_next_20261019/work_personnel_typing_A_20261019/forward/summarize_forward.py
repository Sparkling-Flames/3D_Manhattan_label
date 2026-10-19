#!/usr/bin/env python3
"""Compact descriptive deliverables; no event outcome or model reselection."""
from pathlib import Path
import hashlib,json
import numpy as np
import pandas as pd
from atomic_exports import csv_verified

P=Path(__file__).resolve().parent
NAMES={'C01':'偏快、交付均值偏低的候选组','C02':'中部大组，质量跨度较宽','C03':'低尾较低的小组','C04':'调整Q较高的小组','unknown':'历史质量支持不足'}
def safe(x):
    if isinstance(x,dict):return {str(k):safe(v)for k,v in x.items()}
    if isinstance(x,(list,tuple)):return [safe(v)for v in x]
    if isinstance(x,(np.integer,)):return int(x)
    if isinstance(x,(np.bool_,)):return bool(x)
    if isinstance(x,(float,np.floating)):return float(x)if np.isfinite(x)else None
    return x
def js(n,x):(P/n).write_text(json.dumps(safe(x),ensure_ascii=False,indent=2,allow_nan=False)+'\n')
def main():
    f=pd.read_csv(P/'fold_features.csv.gz');full=f[f.fold_id.eq('FULL')].copy()
    labels=pd.read_csv(P/'selected_classes_by_fold.csv.gz')
    labs=labels[labels.fold_id.eq('FULL')&labels.method_id.eq('forward_selected')][['worker_id','class_id','candidate_method']]
    portrait=full.merge(labs,on='worker_id',validate='one_to_one');portrait['descriptive_FULL_class_name']=portrait.class_id.map(NAMES)
    peer=pd.read_csv(P/'worker_class_peer_stability.csv.gz');peer=peer[peer.method_id.eq('fw_QT_only_K4')]
    peers=peer.groupby('worker_id').same_class_peer_jaccard.agg(peer_jaccard_mean='mean',peer_jaccard_min='min',peer_jaccard_max='max')
    portrait=portrait.merge(peers,left_on='worker_id',right_index=True,how='left',validate='one_to_one')
    t=pd.read_csv(P/'fixed_time_threshold_profiles.csv.gz');t=t[t.fold_id.eq('FULL')][['worker_id','source_median_T60_180','source_median_T90_240','fixed_threshold_label_changed']]
    portrait=portrait.merge(t,on='worker_id',validate='one_to_one')
    portrait['border_interpretation']='Peer Jaccard is sensitivity to historical building removal, not error probability; names describe FULL only.'
    csv_verified(portrait,P/'full_selected_worker_portraits.csv.gz')
    sup=pd.read_csv(P/'class_replacement_support.csv.gz');s=sup[sup.fold_id.eq('FULL')&sup.method_id.eq('fw_QT_only_K4')]
    classes=[]
    for cl,g in portrait.groupby('class_id'):
        r={'class_id':cl,'name':NAMES[cl],'members':sorted(g.worker_id),'n_workers':len(g),
           'core_images_min':int(g.core_images.min()),'core_images_max':int(g.core_images.max()),'core_buildings_min':int(g.core_buildings.min()),'core_buildings_max':int(g.core_buildings.max()),
           'time_supported_workers':int(g.t_supported.sum()),'source_time_observed_workers':int(g.source_time_n.gt(0).sum()),'origin_counts':g.person_origin.value_counts().to_dict()}
        for c in ['q_beta','q_abs_mean','q_abs_p10','q_abs_sd','source_time_median','t_source_origin_effect','t_log_residual_tail','hard_minus_easy','hard_minus_medium']:
            v=g[c].dropna();r[c]={'observed':len(v),'median':v.median(),'min':v.min(),'max':v.max()}
        if cl!='unknown':r['coobserved_support']=s[s.class_id.eq(cl)].iloc[0].drop(['method_id','fold_id','difficulty','class_id','members']).to_dict()
        classes.append(r)
    js('FULL_FORWARD_CLASSES.json',{'status':'training_descriptive_candidates_not_formal_ratings','method':'fw_QT_only_K4','names_are_FULL_only':True,'classes':classes})
    allclass=sup[sup.fold_id.eq('FULL')].copy();allclass.to_csv(P/'all_candidate_full_class_members.csv',index=False)
    proc=pd.read_csv(P/'candidate_selection_process.csv');fp=proc[proc.fold_id.eq('FULL')].sort_values('mean')
    stab=pd.read_csv(P/'cross_fold_partition_stability.csv');selstab=stab[stab.method_id.eq('fw_QT_only_K4')]
    met=pd.read_csv(P/'selected_metric_sensitivity.csv');met=met[met.method_id.eq('forward_selected')&met.fold_id.ne('FULL')]
    fidelity=pd.read_csv(P/'explanation_fidelity.csv');fs=fidelity[fidelity.method_id.eq('forward_selected')&fidelity.fold_id.ne('FULL')]
    perturb=pd.read_csv(P/'explanation_building_perturbation.csv.gz');ps=perturb[perturb.method_id.eq('forward_selected')]
    numbers={'features':{'distinct_training_sets':69,'workers':60,'supported_core_FULL':int(full.core_supported.sum()),'B8L2_rows':4140,'D10_rows':4140,'ordinary_quality_records':int(full.core_records.sum()),'source_time_pool_records':int(full.source_time_n.sum()),'time_relative_supported_workers':int(full.t_supported.sum()),'scope_supported_workers':int(full.scope_supported.sum())},
      'candidates':28,'nested_training_contexts_including_full':23,'selected_candidate_counts':pd.read_csv(P/'selected_methods.csv').candidate_method.value_counts().to_dict(),
      'all_candidates_within_1SE_in_every_context':bool(proc.groupby('fold_id').within_one_se.sum().eq(28).all()),
      'full_inner_best_mean_candidate':fp.method_id.iloc[0],'full_inner_best_mean':fp['mean'].iloc[0],'full_inner_selected_mean':fp[fp.selected]['mean'].iloc[0],'full_inner_selected_minus_best':fp[fp.selected]['mean'].iloc[0]-fp['mean'].iloc[0],
      'cross_building_partition_sensitivity':{'median_ARI':selstab.ARI.median(),'mean_ARI':selstab.ARI.mean(),'median_same_pair_jaccard':selstab.same_pair_jaccard.median(),'range_ARI':[selstab.ARI.min(),selstab.ARI.max()]},
      'D10_fixed_choice_repartition':{'outer_median_pair_relation_change':met.same_class_relation_changed_fraction.median(),'outer_range_pair_relation_change':[met.same_class_relation_changed_fraction.min(),met.same_class_relation_changed_fraction.max()],'support_changes':int(met.support_status_changed.sum())},
      'explanation':{'outer_median_cross_worker_accuracy':fs.cross_worker_accuracy.median(),'outer_median_majority_baseline':fs.majority_class_accuracy.median(),'outer_mean_cross_worker_minus_majority':(fs.cross_worker_accuracy-fs.majority_class_accuracy).mean(),'inner_building_perturbation_median_rule_ARI':ps.rule_ARI.median(),'inner_building_perturbation_median_rule_same_pair_jaccard':ps.rule_same_pair_jaccard.median()},
      'limitations':['descriptive full classes are not target-building labels','cross-worker surrogate fidelity is not future-task predictive performance','heldout geometric stability and quality are evaluated independently by root on shared events','all 28 candidates are saved; a simpler selected family does not prove optional features are useless','D10 fixed-choice repartition differs from same-members metric sensitivity']}
    js('FORWARD_SUMMARY_NUMBERS.json',numbers)
    expected={'explanation_worker_predictions.csv.gz':21566,'explanation_building_perturbation.csv.gz':1056,'class_feature_summary.csv.gz':31280,'fixed_time_threshold_profiles.csv.gz':1380,'selected_classes_by_fold_D10.csv.gz':22080,'full_selected_worker_portraits.csv.gz':60}
    checks={}
    for n,count in expected.items():
        rows=sum(len(x)for x in pd.read_csv(P/n,chunksize=25000));assert rows==count
        checks[n]={'rows':rows,'sha256':hashlib.sha256((P/n).read_bytes()).hexdigest(),'complete_crc_readback':True}
    js('EXPLANATION_AND_PROFILE_EXPORT_COMPLETE.json',{'status':'COMPLETE','outputs':checks,'model_reselection_after_diagnostics':False})
    print(json.dumps(safe(numbers),ensure_ascii=False))
if __name__=='__main__':main()
