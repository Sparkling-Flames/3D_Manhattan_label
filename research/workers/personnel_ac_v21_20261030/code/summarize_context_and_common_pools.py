"""Existing-context strata and same-pool method comparisons of saved AC effects.

No score determines a stratum. Official difficulty and structural opportunity
conditions are copied unchanged from the frozen v2.1 target table. Method pairs
control image/target/n/m, but not identical members or identical class meanings.
"""
from __future__ import annotations
import json,sys
from itertools import combinations
from pathlib import Path
import numpy as np
import pandas as pd
from summarize_ac_effects import GROUP,aggregate,save

ROOT=Path(__file__).resolve().parents[1]
IMPORTANT=['B8L2_CA','D10_CA','fusion_turn_n_CA','fusion_short_turn_edges_CA','ref_node_recall_5_CA',
 'ref_edge_recall_5_CA','geometry_bev_distance_AC','geometry_centroid_distance_AC','geometry_area_h2_pct_CA',
 'height_mean_h_pct_CA','record_time_CA_pct_source_matched','fusion_failure_observed_risk_change_CA','Q_missing_risk_change_CA']


def main():
    main_receipt=json.loads((ROOT/'stage05_main/SUMMARY_RECEIPT.json').read_text())
    if not main_receipt.get('complete',False):
        raise RuntimeError('Context and common-pool analysis requires the complete frozen event measurement, not a partial preview.')
    out=ROOT/'stage05_context_common';out.mkdir(exist_ok=True)
    source=ROOT/'stage05_main/POOL_CONDITION_EFFECTS.csv.gz'
    pool=pd.read_csv(source,low_memory=False)
    for c in GROUP:pool[c]=pool[c].astype(str)
    target=ROOT/'stage07_reproduction/minimum_source/repo/research/workers/personnel_v21_reselection_20261029/targets/POOL_TARGET_CONDITIONS.csv'
    ctx=pd.read_csv(target,low_memory=False)
    axes=[c for c in ['official_difficulty','structural_condition','geometric_challenge'] if c in ctx]
    context=pool.merge(ctx[['pool_id']+axes],on='pool_id',how='left',validate='many_to_one')
    relevant=context.scope.eq('primary') & context.condition.eq('manual') & context.analysis_view.isin(['A_fixed_n','A_pool_frontier','whole_equal_fixed_n_all_m','whole_equal_pool_frontier'])
    context=context[relevant & context.n_condition.isin(['14','16','18','20','22','N_minus_m'])].copy()
    columns=[c for c in context if '__' not in c or c.split('__')[0] in IMPORTANT]
    context=context[columns]
    frames=[]
    for axis in axes:
        d=context.copy();d['analysis_view']=d.analysis_view+'|ctx:'+axis+'='+d[axis].fillna('ungraded_or_unavailable').astype(str)
        frames.append(d)
    if frames:
        contextual=pd.concat(frames,ignore_index=True)
        interim=out/'context_tables';interim.mkdir(exist_ok=True)
        aggregate(contextual,interim)
        summary=pd.read_csv(interim/'CONDITION_METRIC_SUMMARY.csv.gz',low_memory=False)
        p=summary.analysis_view.str.split('|ctx:',regex=False,expand=True)
        summary['analysis_view']=p[0];q=p[1].str.split('=',n=1,expand=True)
        summary['context_axis']=q[0];summary['context_value']=q[1]
        save(summary,out/'FROZEN_CONTEXT_EFFECT_SUMMARY.csv.gz')
    # Absolute effects summarize all available pure class-pair directions equally
    # within each pool. They do not rank classifiers by maximum improvement.
    a=pool[pool.scope.eq('primary') & pool.condition.eq('manual') & pool.analysis_view.eq('A_fixed_n')].copy()
    fields=[m+'__mean_absolute' for m in IMPORTANT if m+'__mean_absolute' in a]
    signed=[m+'__mean' for m in IMPORTANT if m+'__mean' in a]
    keys=['pool_id','image','building','method','n_condition','m_condition']
    means=a.groupby(keys,sort=False)[fields+signed].mean().reset_index()
    directions=a.groupby(keys,sort=False).agg(role_directions=('role_direction',lambda x:'|'.join(sorted(set(x)))),class_pair_directions=('role_direction','nunique')).reset_index()
    means=means.merge(directions,on=keys,validate='one_to_one');save(means,out/'METHOD_POOL_ALL_DIRECTION_EFFECTS.csv.gz')
    rows=[]
    for (n,m),g in means.groupby(['n_condition','m_condition'],sort=False):
        by={method:d.set_index('pool_id') for method,d in g.groupby('method',sort=False)}
        for left,right in combinations(sorted(by),2):
            x,y=by[left],by[right];common=sorted(set(x.index)&set(y.index))
            if not common:continue
            x=x.loc[common];y=y.loc[common]
            for metric in IMPORTANT:
                col=metric+'__mean_absolute'
                if col not in x:continue
                valid=x[col].notna()&y[col].notna();xx=x.loc[valid,col];yy=y.loc[valid,col]
                rows.append({'method_left':left,'method_right':right,'n':n,'m':m,'metric':metric,
                  'common_registered_pools':len(common),'valid_common_images':int(valid.sum()),
                  'valid_common_buildings':x.loc[valid,'building'].nunique(),
                  'left_image_mean_absolute_change':xx.mean(),'right_image_mean_absolute_change':yy.mean(),
                  'right_minus_left_absolute_change':(yy-xx).mean(),
                  'right_absolute_larger_images':int((yy-xx>1e-9).sum()),
                  'left_full_coverage_pools':len(by[left]),'right_full_coverage_pools':len(by[right]),
                  'common_pool_ids':'|'.join(common),
                  'interpretation':'same image target n m; own class directions averaged equally; members and meanings differ; descriptive contrast, not method superiority'})
    save(pd.DataFrame(rows),out/'COMMON_POOL_METHOD_COMPARISONS.csv.gz')
    # Keep every small mean response, separating within-image cancellation from
    # uniformly small sampled responses; mechanisms still require native traces.
    q=pool[pool.scope.eq('primary') & pool.condition.eq('manual') & pool.analysis_view.eq('A_fixed_n')].copy()
    q['small_signed_Q_mean']=q['B8L2_CA__mean'].abs()<=1
    q['small_mean_absolute_Q_change']=q['B8L2_CA__mean_absolute']<=1
    q['member_or_background_sign_cancellation']=q.small_signed_Q_mean & (q['B8L2_CA__mean_absolute']>=5)
    q['both_high_mean_Q']=q['A_B8L2__mean'].ge(90)&q['C_B8L2__mean'].ge(90)
    q['both_low_mean_Q']=q['A_B8L2__mean'].le(70)&q['C_B8L2__mean'].le(70)
    q['geometry_changes_despite_small_signed_Q']=q.small_signed_Q_mean & q['geometry_bev_distance_AC__mean'].ge(.1)
    keep=GROUP+['pool_id','image','building','registered_pairs']+[c for c in q if c.startswith(('B8L2_CA__','D10_CA__','A_B8L2__','C_B8L2__','fusion_turn_n_CA__','ref_node_recall_5_CA__','geometry_bev_distance_AC__'))]+['small_signed_Q_mean','small_mean_absolute_Q_change','member_or_background_sign_cancellation','both_high_mean_Q','both_low_mean_Q','geometry_changes_despite_small_signed_Q']
    save(q[keep],out/'SMALL_RESPONSE_AND_CANCELLATION_DIAGNOSTICS.csv.gz')
    receipt={'new_fusions':0,'new_labels':0,'official_difficulty_changed':False,'context_axes':axes,
      'quality_thresholds_for_diagnostic_only':[1,5,70,90],'thresholds_used_to_select_teams':False,
      'common_method_controls':['image','target','n','m','neutral_members_0 sampling policy'],
      'not_controlled':['exact members across methods','identical semantic class definitions','identical background composition across methods'],
      'classifier_ranking_by_max_Q':False,'common_comparison_rows':len(rows)}
    (out/'ANALYSIS_RECEIPT.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2)+'\n');print(json.dumps(receipt,ensure_ascii=False))


if __name__=='__main__':main()
