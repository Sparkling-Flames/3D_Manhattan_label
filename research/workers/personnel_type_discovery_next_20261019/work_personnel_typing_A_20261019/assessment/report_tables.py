#!/usr/bin/env python3
"""Compact review tables from frozen prediction/outcome files; no fitting."""
from pathlib import Path
import sys
import numpy as np
import pandas as pd
HERE=Path(__file__).resolve().parent;ROOT=HERE.parent
sys.path.insert(0,str(HERE));sys.path.insert(0,str(ROOT/'forward'))
from evaluate_common import unit_summary,boolcol,savej,PRIMARY
from atomic_exports import csv_verified

def main():
    e=pd.read_csv(HERE/'COMMON_EVENT_ANALYSIS_INPUT.csv.gz',low_memory=False);w=pd.read_csv(HERE/'EVENT_PREDICTIONS_WIDE.csv.gz');assert e.event_id.equals(w.event_id)
    for c in ['stable_main','stable_strict','stable_loose','stable_D10','either_failure','q_near']:e[c]=boolcol(e[c])
    rows=[];y=e.stable_main.to_numpy(float)
    full='forward_full_mainK'
    for m in ['forward_minus_difficulty_mainK','forward_minus_semi_mainK','forward_minus_scope_mainK','forward_minus_structure_mainK','forward_QT_only_mainK']:
        assert 'p__'+m in w,m
        f=e[['panel_id','k','building','image_id','q_near','pair_origin']].copy()
        f['full_gain']=(w['p__'+m].to_numpy()-y)**2-(w['p__'+full].to_numpy()-y)**2
        for s,mask in [('all_same_events',np.ones(len(e),bool)),('Q_near_3',e.q_near.to_numpy())]+[(o,e.pair_origin.eq(o).to_numpy())for o in ['old-old','new-new','old-new']]:
            for (panel,k),g in f.loc[mask].groupby(['panel_id','k']):rows.append(dict(full_method=full,ablated_method=m,panel_id=panel,k=k,stratum=s,**unit_summary(g,'full_gain')))
    csv_verified(pd.DataFrame(rows),HERE/'FROZEN_K_ABLATION_COMPARISONS.csv')
    chains=pd.read_csv(HERE/'NESTED_FOUR_NODE_CHAINS.csv.gz');chainids=chains.loc[chains.complete_four_nodes,'nested_chain_id']
    mask=e.panel_id.eq('A_nested_even_v1')&e.nested_chain_id.isin(chainids)
    rows=[];outcome_rows=[]
    for m in ['Q3','old_QT','old_QTD_archive','forward_selected','forward_full','reverse_selected','reverse_selected_swap','reverse_selected_difficulty']:
        f=e.loc[mask].copy();f['relation']=w.loc[mask,'rel__'+m].to_numpy()
        p=w.loc[mask,'p__'+m].to_numpy();ref=w.loc[mask,'p__old_QT'].to_numpy();y=f.stable_main.to_numpy(float)
        f['brier']=(p-y)**2;f['gain_vs_old_QT']=(ref-y)**2-f.brier
        for k,g in f.groupby('k'):
            for metric in ['brier','gain_vs_old_QT']:rows.append(dict(method_id=m,k=k,metric=metric,**unit_summary(g,metric)))
        for (k,r),g in f.groupby(['k','relation']):
            for metric in ['stable_main','stable_strict','stable_loose','stable_D10','abs_delta_Q','floor_change','either_failure']:outcome_rows.append(dict(method_id=m,k=k,relation=r,metric=metric,**unit_summary(g,metric)))
    csv_verified(pd.DataFrame(rows),HERE/'NESTED_COMMON_FOUR_NODE_PREDICTIONS.csv')
    csv_verified(pd.DataFrame(outcome_rows),HERE/'NESTED_COMMON_FOUR_NODE_GEOMETRY.csv')
    # Human-readable personnel table joins FULL descriptive classes, not OOF outcomes.
    people=pd.read_csv(ROOT/'forward/full_selected_worker_portraits.csv.gz')
    old=pd.read_csv(ROOT/'recovered/work_v2_20261019/profiles/full_profiles.csv')
    people=people.merge(old[['worker_id','Q3_B8L2','QT_B8L2','fine_dtype_merged_B8L2','Q_effect_D10']],on='worker_id',validate='one_to_one')
    labels=pd.read_csv(HERE/'ALL_SELECTED_AND_BASELINE_LABELS.csv.gz');labels=labels[labels.heldout_building.eq('FULL')&labels.difficulty.eq('global')]
    for m in ['reverse_selected','reverse_selected_swap','forward_full']:
        a=labels[labels.method_id.eq(m)][['worker_id','class_id']].rename(columns={'class_id':m+'_FULL_class'})
        people=people.merge(a,on='worker_id',validate='one_to_one')
    peers=pd.read_csv(ROOT/'reverse/results/worker_classmate_stability.csv')
    for m in ['reverse_selected','reverse_selected_swap']:
        a=peers[peers.method_id.eq(m)&peers.domain.eq('global')][['worker_id','full_classmates','mean_classmate_jaccard','minimum_classmate_jaccard','unknown_folds']]
        a=a.rename(columns={c:m+'_'+c for c in a if c!='worker_id'});people=people.merge(a,on='worker_id',validate='one_to_one')
    people['class_labels_are_FULL_descriptive_not_validation']=True;people['no_formal_personnel_tier_changed']=True
    csv_verified(people,HERE/'WORKER_PORTRAITS_60.csv')
    # Native endpoint failures and time completeness have their own denominator.
    cols=['request_id','team_id','image_id','building','k','complete_evaluable','source_time_missing_n','target_time_missing_n','geometry_reason']
    teams=pd.read_csv(ROOT/'events/native_runs/team_results.csv',usecols=cols)
    assert len(teams)==58882 and teams.request_id.is_unique
    per=teams.groupby('k').agg(requests=('request_id','size'),unique_teams=('team_id','nunique'),complete=('complete_evaluable','sum'),full_source_time=('source_time_missing_n',lambda x:x.eq(0).sum()),full_target_time=('target_time_missing_n',lambda x:x.eq(0).sum())).reset_index()
    csv_verified(per,HERE/'TEAM_COMPLETENESS_AND_TIME_COVERAGE.csv')
    savej(HERE/'REPORT_TABLE_RECEIPT.json',{'n_people':len(people),'new_class_fit_done':False,'common_four_node_chains':len(chainids),'common_four_node_images':e.loc[mask].image_id.nunique(),'common_four_node_events':int(mask.sum()),'native_unique_complete':int(teams.drop_duplicates('team_id').complete_evaluable.sum()),'native_unique_teams':teams.team_id.nunique(),'native_failed_reason_request_counts':teams.loc[~teams.complete_evaluable,'geometry_reason'].value_counts().to_dict()})
    print('compact review tables complete',flush=True)
if __name__=='__main__':main()
