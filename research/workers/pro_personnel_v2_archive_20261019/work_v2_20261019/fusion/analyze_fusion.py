"""Descriptive denominators and building-level uncertainty for real consensus experiments."""
from __future__ import annotations
from pathlib import Path
import json
import argparse
import numpy as np
import pandas as pd
from pool_io import OUT,save,csv,read

SEED=2026101905
def ci(values,seed=SEED):
    x=np.asarray(values,float);x=x[np.isfinite(x)]
    if len(x)<2:return (None,None)
    rng=np.random.default_rng(seed);means=x[rng.integers(0,len(x),(5000,len(x)))].mean(axis=1)
    return tuple(float(v) for v in np.quantile(means,[.025,.975]))
def describe(values,prefix):
    x=pd.to_numeric(values,errors='coerce').dropna().to_numpy(float)
    return {prefix+'_n':len(x),prefix+'_mean':float(x.mean()) if len(x) else None,
        prefix+'_median':float(np.median(x)) if len(x) else None,prefix+'_p10':float(np.quantile(x,.1)) if len(x) else None,
        prefix+'_p90':float(np.quantile(x,.9)) if len(x) else None}
def building_summary(frame,groupkeys,metrics,outname):
    result=[]
    for key,g in frame.groupby(groupkeys,dropna=False):
        key=key if isinstance(key,tuple) else (key,);row=dict(zip(groupkeys,key));row.update(n_rows=len(g),images=g.image_id.nunique(),buildings=g.building.nunique(),pools=g.pool_id.nunique())
        for metric in metrics:
            row.update(describe(g[metric],metric));im=g.groupby(['building','image_id'])[metric].mean();build=im.groupby('building').mean().dropna()
            row[metric+'_image_equal']=float(im.mean()) if im.notna().any() else None
            row[metric+'_building_equal']=float(build.mean()) if len(build) else None
            lo,hi=ci(build);row[metric+'_building_CI_low']=lo;row[metric+'_building_CI_high']=hi
        result.append(row)
    csv(OUT/outname,result);return pd.DataFrame(result)

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--initial-comparisons',action='store_true',help='Use the completed initial uniform/replacement panels while extension comparisons are publishing.')
    args=parser.parse_args();comparison_prefix='INITIAL_' if args.initial_comparisons else ''
    usecols=['request_id','pool_id','image','image_id','building','room_id','condition','layer','difficulty','reference_id','reference_version',
        'request_family','strategy','selection_metric','candidate_pool','k','draw_id','path_id','team_id','member_workers','ordered_workers',
        'nodes','half_vote_nodes','complete_evaluable','connection_available','score_status','B8L2','D10','IoU3D100','iou_2d','omission','extension',
        'Hmean','Hcenter','height_mean_ratio','reference_pair_count','reference_node_shortfall','source_time_known_n','source_time_missing_n',
        'source_time_total_seconds','target_time_known_n','target_time_missing_n','target_time_total_seconds','member_old_n','member_new_n',
        'R_symdiff_h2','R_union_normalized','selected_node_support_mean','selected_node_support_min','nonselected_group_n']
    data=pd.read_csv(OUT/'team_results.csv',usecols=lambda c:c in usecols,low_memory=False)
    for c in ('selection_metric','candidate_pool','path_id'):
        if c not in data:data[c]=np.nan
    data['score_available']=data.B8L2.notna();data['source_time_complete']=data.source_time_missing_n.eq(0);data['target_time_complete']=data.target_time_missing_n.eq(0)
    data['delivery_utility_B8L2']=data.B8L2.fillna(0.) # Explicit team-decision sensitivity only; never an individual Q.
    data['zero_node_shortfall']=data.reference_node_shortfall.eq(0)
    coverage=[]
    for key,g in data.groupby(['layer','request_family','k'],dropna=False):
        coverage.append(dict(zip(('layer','request_family','k'),key),requests=len(g),unique_teams=g.team_id.nunique(),images=g.image_id.nunique(),
            buildings=g.building.nunique(),quality_available=int(g.score_available.sum()),complete=int(g.complete_evaluable.sum()),
            N2_policy_deferred=int(g.k.eq(2).sum()),other_score_missing=int((~g.score_available & g.k.ne(2)).sum()),
            source_complete=int(g.source_time_complete.sum()),target_complete=int(g.target_time_complete.sum()),
            score_status_counts=json.dumps(g.score_status.value_counts().to_dict(),ensure_ascii=False)))
    csv(OUT/'TEAM_COVERAGE_BY_LAYER_K.csv',coverage)
    random=data[data.request_family.isin(['uniform_prefix','independent_random_team'])].drop_duplicates(['pool_id','k','team_id'])
    building_summary(random,['layer','k'],['B8L2','D10','complete_evaluable','delivery_utility_B8L2','iou_2d','omission','extension',
        'reference_node_shortfall','source_time_complete','target_time_complete','source_time_total_seconds','R_union_normalized'],
        'RANDOM_TEAM_SUMMARY.csv')
    image_k=[]
    for key,g in random.groupby(['layer','pool_id','image_id','building','difficulty','k']):
        r=dict(zip(('layer','pool_id','image_id','building','difficulty','k'),key),unique_teams=len(g),complete_rate=g.complete_evaluable.mean(),
            score_available=int(g.B8L2.notna().sum()),source_complete=int(g.source_time_complete.sum()),target_complete=int(g.target_time_complete.sum()))
        for field in ('B8L2','D10','iou_2d','omission','extension','nodes','source_time_total_seconds','R_union_normalized'):r.update(describe(g[field],field))
        image_k.append(r)
    csv(OUT/'RANDOM_PER_IMAGE_K.csv',image_k)
    # A single common-image panel prevents large-k means changing merely because
    # thin pools disappear. Q/R/V remain different quantities.
    primary=random[random.layer.eq('ordinary_manual') & random.k.isin([8,12,16,24])]
    common_pools=primary.groupby('pool_id').k.nunique();common_pools=set(common_pools[common_pools.eq(4)].index)
    primary_common=primary[primary.pool_id.isin(common_pools)]
    building_summary(primary_common,['k'],['B8L2','D10','complete_evaluable','delivery_utility_B8L2','iou_2d',
        'omission','extension','reference_node_shortfall','R_union_normalized','source_time_complete','source_time_total_seconds'],
        'RANDOM_COMMON_8_12_16_24_SUMMARY.csv')
    csv(OUT/'RANDOM_COMMON_8_12_16_24_IMAGES.csv',primary_common[['pool_id','image_id','building','difficulty']].drop_duplicates().to_dict('records'))
    # Exact real uniform paths on common images for each pair of k values; no changing-image denominators.
    prefixes=data[data.request_family.eq('uniform_prefix') & data.layer.eq('ordinary_manual')].copy()
    growth=[]
    for low,high in [(3,8),(8,12),(12,16),(16,24),(24,32),(8,16),(8,24),(8,32)]:
        a=prefixes[prefixes.k.eq(low)];b=prefixes[prefixes.k.eq(high)];keys=['pool_id','path_id','building','image_id','image','difficulty']
        cols=keys+['B8L2','D10','complete_evaluable','delivery_utility_B8L2','source_time_total_seconds','nodes','reference_node_shortfall']
        paired=a[cols].merge(b[cols],on=keys,suffixes=('_low','_high'),validate='one_to_one')
        paired['B8_change']=paired.B8L2_high-paired.B8L2_low;paired['D10_change']=paired.D10_high-paired.D10_low
        paired['complete_change']=paired.complete_evaluable_high.astype(int)-paired.complete_evaluable_low.astype(int)
        paired['utility_change']=paired.delivery_utility_B8L2_high-paired.delivery_utility_B8L2_low
        paired['source_cost_change']=paired.source_time_total_seconds_high-paired.source_time_total_seconds_low
        paired['node_change']=paired.nodes_high-paired.nodes_low
        paired['low_k']=low;paired['high_k']=high
        csv(OUT/f'GROWTH_MATCHED_{low}_{high}.csv',paired.replace({np.nan:None}).to_dict('records'))
        row=dict(low_k=low,high_k=high,images=paired.image_id.nunique(),buildings=paired.building.nunique(),paths=len(paired),
            quality_paired=int(paired.B8_change.notna().sum()),quality_decline=int(paired.B8_change.lt(0).sum()),
            quality_decline_gt2=int(paired.B8_change.lt(-2).sum()),quality_gain_gt2=int(paired.B8_change.gt(2).sum()),
            low_complete=int(paired.complete_evaluable_low.sum()),high_complete=int(paired.complete_evaluable_high.sum()))
        for metric in ('B8_change','D10_change','complete_change','utility_change','source_cost_change','node_change'):
            bm=paired.groupby(['building','image_id'])[metric].mean().groupby('building').mean().dropna();row[metric]=float(bm.mean()) if len(bm) else None
            lo,hi=ci(bm);row[metric+'_CI_low']=lo;row[metric+'_CI_high']=hi
        growth.append(row)
    csv(OUT/'GROWTH_COMMON_PANEL_SUMMARY.csv',growth)
    if (OUT/(comparison_prefix+'prefix_transitions.csv.gz')).exists():
        fields=['pool_id','image_id','building','layer','difficulty','path_family','path_strategy','threshold','k_from','k_to',
            'quality_comparable','B8L2_change','D10_change','complete_to_incomplete','incomplete_to_complete',
            'node_count_change','node_count_difference','changed_coidentity_pairs','floor_jaccard_difference','edge_relation_jaccard_difference']
        trans=pd.read_csv(OUT/(comparison_prefix+'prefix_transitions.csv.gz'),usecols=lambda c:c in fields,low_memory=False)
        trans['quality_decline']=trans.B8L2_change.lt(0).where(trans.B8L2_change.notna())
        trans['quality_drop_gt2']=trans.B8L2_change.lt(-2).where(trans.B8L2_change.notna())
        trans['quality_gain_gt2']=trans.B8L2_change.gt(2).where(trans.B8L2_change.notna())
        trans['node_count_changed']=trans.node_count_difference.gt(0).where(trans.node_count_difference.notna())
        trans['identity_changed']=trans.changed_coidentity_pairs.gt(0).where(trans.changed_coidentity_pairs.notna())
        trans['touches_N2_policy']=trans.k_from.eq(2)|trans.k_to.eq(2)
        building_summary(trans,['layer','path_family','path_strategy','threshold','touches_N2_policy'],
            ['B8L2_change','quality_decline','quality_drop_gt2','quality_gain_gt2','complete_to_incomplete','incomplete_to_complete','node_count_changed','identity_changed','floor_jaccard_difference'],
            'PREFIX_EVENT_SUMMARY.csv')
        trans['parity_to']=trans.k_to%2
        building_summary(trans[trans.k_from.ge(3)],['layer','path_family','path_strategy','threshold','parity_to'],
            ['B8L2_change','quality_decline','quality_drop_gt2','quality_gain_gt2','complete_to_incomplete','incomplete_to_complete','node_count_change',
             'node_count_changed','identity_changed','floor_jaccard_difference'], 'PREFIX_PARITY_SUMMARY.csv')
    if (OUT/(comparison_prefix+'random_same_k.csv.gz')).exists():
        fields=['pool_id','image_id','building','layer','k','abs_B8L2_change','abs_D10_change','both_complete','floor_jaccard_difference',
            'structure_bound_cyclic_deg','structure_reverse_allowed_deg','node_count_difference','edge_relation_jaccard_difference',
            'selected_shared_observation_difference','joint_geometric_stable','joint_with_shared_connections','joint_with_shared_connections_and_retention',
            'mean_height_prism_pair_iou']
        same=pd.read_csv(OUT/(comparison_prefix+'random_same_k.csv.gz'),usecols=lambda c:c in fields,low_memory=False)
        same['node_count_changed']=same.node_count_difference.gt(0).where(same.node_count_difference.notna())
        building_summary(same,['layer','k'],['abs_B8L2_change','abs_D10_change','both_complete','floor_jaccard_difference',
            'structure_bound_cyclic_deg','node_count_changed','joint_geometric_stable','joint_with_shared_connections','mean_height_prism_pair_iou'],
            'SAME_K_VARIATION_SUMMARY.csv')
        building_summary(same[same.layer.eq('ordinary_manual') & same.pool_id.isin(common_pools) & same.k.isin([8,12,16,24])],
            ['k'],['abs_B8L2_change','abs_D10_change','both_complete','floor_jaccard_difference','node_count_changed',
            'joint_geometric_stable','joint_with_shared_connections','mean_height_prism_pair_iou'],
            'SAME_K_VARIATION_COMMON_8_12_16_24.csv')
    # Actual team cost coverage remains separate for inherited vs reported-only teams and mixed-source teams.
    data['team_origin']=np.where(data.member_old_n.eq(0),'new_only',np.where(data.member_new_n.eq(0),'old_only','mixed'))
    building_summary(data[data.k.isin([8,12,16,24])],['layer','request_family','team_origin','k'],
        ['source_time_complete','target_time_complete','source_time_total_seconds','target_time_total_seconds','B8L2','complete_evaluable'],
        'TEAM_TIME_SOURCE_COVERAGE.csv')
    save(OUT/'ANALYSIS_NOTES.json',dict(comparison_input_prefix=comparison_prefix,bootstrap='5000 percentile bootstrap resamples of observed building means; within-building image equal first. Descriptive exploration, not evidence that these buildings are random from a global population.',
        failures='Every request counted; conditional Q is accompanied by completeness. delivery_utility_B8L2=Q if available else0 is a separate team-operation sensitivity and is never used as missing individual Q.',
        R='Original-person pair floor symmetric difference normalized by the fixed whole-pool union; uniform subset expectation does not decrease mechanically with k. Not a structure matching distance or automatic image/person noise decomposition.',
        V='Two actually executed teams at the same image,k,reference compared; floor, bound ring, node retention and shared connection changes separate. Full-pool identical endpoints are a finite-pool identity, not evidence of general stability.',
        structures='Equal node count and small endpoint differences do not certify shared local edges or semantic omissions; joint_with_shared_connections and retention provide additional observable conditions.',
        source_time='Summed observed task cost; neither lead time nor predicted parallel latency. Source and same-target time never substituted.',
        geometry3d='Pair IoU is the same bottom-plane, mean-height-prism proxy; it is not precise continuous solid-volume IoU.'))
    print('summary artifacts written',flush=True)

if __name__=='__main__':main()
