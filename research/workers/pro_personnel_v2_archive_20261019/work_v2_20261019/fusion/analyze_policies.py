"""Paired, building-weighted forward, composition and metric-sensitivity results.

All teams are frozen in REQUESTS_FORWARD/BEHAVIOR before their outputs. This
module does not select a better threshold, refit a class or change a request.
"""
from __future__ import annotations
import sys
import argparse
from pathlib import Path
import numpy as np
import pandas as pd
from pool_io import OUT, ROOT, csv, save, sha, clean
from analyze_fusion import ci
from compare_fusions import write_csv_gz

sys.path.insert(0, str(ROOT/'work_v2_20261019/profiles'))
from room_weighting import aggregate_declared_groups

MEMBERSHIPS = pd.read_csv(ROOT/'work_v2_20261019/profiles/declared_room_groups.csv')


def summarize(frame, strata, metrics, filename, difficulty=True):
    """Rows -> image mean -> building mean; original-room groups are sensitivity."""
    summaries=[];images=[];groups=[]
    expanded=frame.copy()
    expanded['difficulty_stratum']='all'
    if difficulty and 'difficulty' in frame:
        extra=frame.copy();extra['difficulty_stratum']=extra.difficulty
        expanded=pd.concat([expanded,extra],ignore_index=True)
        strata=[*strata,'difficulty_stratum']
    elif difficulty:strata=[*strata,'difficulty_stratum']
    for key,g in expanded.groupby(strata,dropna=False,sort=True):
        key=key if isinstance(key,tuple) else (key,);label=dict(zip(strata,key))
        im=g.groupby(['pool_id','building','image_id'],dropna=False)[metrics].mean().reset_index()
        assert not im.image_id.duplicated().any(), 'a stratum includes multiple references/conditions of the same image'
        rg,cov=aggregate_declared_groups(im,MEMBERSHIPS,metrics,building_col='building')
        for r in im.to_dict('records'):images.append(dict(label,**r))
        for r in rg.to_dict('records'):groups.append(dict(label,**r))
        for metric in metrics:
            raw=pd.to_numeric(g[metric],errors='coerce').dropna().astype(float);ivals=im[metric].dropna()
            bv=im.groupby('building')[metric].mean().dropna();lo,hi=ci(bv)
            summaries.append(dict(label,metric=metric,attempted_rows=len(g),evaluable_rows=len(raw),
                images=g.image_id.nunique(),buildings=g.building.nunique(),metric_images=len(ivals),metric_buildings=len(bv),
                raw_mean=raw.mean() if len(raw) else None,raw_median=raw.median() if len(raw) else None,
                raw_p10=raw.quantile(.1) if len(raw) else None,raw_p90=raw.quantile(.9) if len(raw) else None,
                image_equal=ivals.mean() if len(ivals) else None,building_equal=bv.mean() if len(bv) else None,
                building_CI_low=lo,building_CI_high=hi,
                declared_group_equal=rg[metric].mean() if len(rg) else None,
                declared_groups=int(rg[metric].notna().sum()) if len(rg) else 0,
                linked_images=cov['linked_input_images'],unlinked_images=len(cov['unlinked_input_image_ids'])))
    csv(OUT/(filename+'_SUMMARY.csv'),summaries)
    write_csv_gz(OUT/(filename+'_PER_IMAGE.csv.gz'),clean(images))
    write_csv_gz(OUT/(filename+'_DECLARED_GROUPS.csv.gz'),clean(groups))
    return pd.DataFrame(summaries)


def policy_comparisons(teams):
    fields=['pool_id','image','image_id','building','layer','difficulty','k','request_a','request_b',
        'comparison_family','strategy_a','strategy_b','selection_metric','candidate_pool','same_subset',
        'quality_comparable','B8L2_a','B8L2_b','D10_a','D10_b','B8L2_change','D10_change','complete_a','complete_b',
        'both_complete','abs_B8L2_change','floor_jaccard_difference','node_count_difference','edge_relation_jaccard_difference',
        'joint_geometric_stable','joint_with_shared_connections','source_time_change_seconds','target_time_change_seconds',
        'source_time_complete_a','source_time_complete_b','target_time_complete_a','target_time_complete_b']
    data=pd.read_csv(OUT/'policy_comparisons.csv.gz',usecols=lambda c:c in fields,low_memory=False)
    # (id, baseline, treatment) orientation is fixed here and never chosen by result.
    definitions=[
        ('Q_vs_eligible_random','eligible_random','Qfirst'),
        ('QD_vs_eligible_random','eligible_random','QD_allhistory'),
        ('QT_vs_eligible_random','eligible_random','QT'),
        ('QTD_vs_eligible_random','eligible_random','QTD_allhistory'),
        ('difficulty_increment_QD_minus_Q','Qfirst','QD_allhistory'),
        ('time_total_QT_minus_Q','Qfirst','QT'),
        ('difficulty_increment_QTD_minus_QT','QT','QTD_allhistory'),
        ('time_total_QTD_minus_QD','QD_allhistory','QTD_allhistory'),
        ('time_within_same_known_band_QT','QT_quality_only_matched','QT'),
        ('time_within_same_known_band_QTD','QTD_allhistory_quality_only_matched','QTD_allhistory'),
        ('difficulty_locally_supported','Qfirst_difficulty_supported','QD_supported'),
        ('origin_centering_QT','QT','QT_origin_time_centered'),
        ('origin_centering_QTD','QTD_allhistory','QTD_allhistory_origin_time_centered'),
        ('behavior_retention_increment','QTD_same_behavior_opportunity_pool','QTD_error_retention_first'),
        ('Q_vs_full_pool_random','full_pool_random','Qfirst'),
        ('QTD_vs_full_pool_random','full_pool_random','QTD_allhistory'),
    ]
    result=[];cost=teams.set_index('request_id')['source_time_total_seconds']
    for label,base,treatment in definitions:
        m=data[(data.strategy_a.eq(base)&data.strategy_b.eq(treatment))|
               (data.strategy_b.eq(base)&data.strategy_a.eq(treatment))].copy()
        if len(m)==0:continue
        forward=m.strategy_a.eq(base);sign=np.where(forward,1.,-1.)
        m['contrast']=label;m['baseline']=base;m['treatment']=treatment
        m['baseline_request']=np.where(forward,m.request_a,m.request_b)
        m['treatment_request']=np.where(forward,m.request_b,m.request_a)
        m['B8_change']=sign*m.B8L2_change;m['D10_change']=sign*m.D10_change
        m['complete_change']=sign*(m.complete_b.astype(float)-m.complete_a.astype(float))
        m['utility_change']=sign*(m.B8L2_b.fillna(0.)-m.B8L2_a.fillna(0.))
        m['source_cost_change']=sign*m.source_time_change_seconds
        m['target_cost_change']=sign*m.target_time_change_seconds
        baseline_cost=m.baseline_request.map(cost)
        m['source_cost_ratio_change']=m.source_cost_change/baseline_cost.where(baseline_cost.gt(0))
        m['source_cost_pair_known']=m.source_time_complete_a&m.source_time_complete_b
        m['target_cost_pair_known']=m.target_time_complete_a&m.target_time_complete_b
        m['node_count_changed']=m.node_count_difference.gt(0).where(m.node_count_difference.notna())
        keep=['pool_id','image','image_id','building','layer','difficulty','k','selection_metric','candidate_pool',
            'comparison_family','contrast','baseline','treatment','baseline_request','treatment_request',
            'B8_change','D10_change','complete_change','utility_change','source_cost_change','target_cost_change',
            'source_cost_ratio_change','source_cost_pair_known','target_cost_pair_known','node_count_changed',
            'abs_B8L2_change','floor_jaccard_difference','joint_geometric_stable','joint_with_shared_connections',
            'quality_comparable','both_complete','same_subset']
        result.append(m[keep])
    paired=pd.concat(result,ignore_index=True)
    write_csv_gz(OUT/'FORWARD_POLICY_PAIRED.csv.gz',clean(paired.to_dict('records')))
    metrics=['B8_change','D10_change','complete_change','utility_change','source_cost_change','source_cost_ratio_change',
        'target_cost_change','source_cost_pair_known','target_cost_pair_known','node_count_changed','abs_B8L2_change',
        'floor_jaccard_difference','joint_geometric_stable','joint_with_shared_connections','quality_comparable','both_complete','same_subset']
    summarize(paired,['contrast','selection_metric','candidate_pool','k'],metrics,'FORWARD_POLICY')
    return paired


def composition_results():
    cols=['pool_id','image','image_id','building','difficulty','k','threshold','scheme','candidate_pool','comparison_family',
        'same_composition','same_subset','request_a','request_b','shared_workers','both_complete','quality_comparable',
        'abs_B8L2_change','abs_D10_change','floor_jaccard_difference','node_count_difference','structure_bound_cyclic_deg',
        'structure_reverse_allowed_deg','mean_height_prism_pair_iou','edge_relation_jaccard_difference',
        'joint_geometric_stable','joint_with_shared_connections','joint_with_shared_connections_and_retention']
    data=pd.read_csv(OUT/'composition_comparisons.csv.gz',usecols=lambda c:c in cols,low_memory=False)
    # Identity perturbations require genuinely different people, not repeated strategy aliases.
    selected=data[~data.same_subset].copy()
    selected['node_count_changed']=selected.node_count_difference.gt(0).where(selected.node_count_difference.notna())
    selected['shared_fraction']=selected.shared_workers/selected.k
    metrics=['abs_B8L2_change','abs_D10_change','floor_jaccard_difference','node_count_changed','structure_bound_cyclic_deg',
        'structure_reverse_allowed_deg','mean_height_prism_pair_iou','edge_relation_jaccard_difference','both_complete',
        'quality_comparable','joint_geometric_stable','joint_with_shared_connections','joint_with_shared_connections_and_retention','shared_fraction']
    summarize(selected,['comparison_family','scheme','threshold','candidate_pool','k','same_composition'],metrics,
        'FIXED_COMPOSITION',difficulty=False)
    coverage=data.groupby(['comparison_family','scheme','threshold','k','same_composition'],dropna=False).agg(
        comparison_rows=('same_subset','size'),same_actual_members=('same_subset','sum'),images=('image_id','nunique'),buildings=('building','nunique')).reset_index()
    csv(OUT/'FIXED_COMPOSITION_COVERAGE.csv',clean(coverage.to_dict('records')))
    # Within each image, compare variation under same versus different count vectors.
    keys=['comparison_family','scheme','threshold','candidate_pool','k','pool_id','image_id','building','difficulty']
    means=selected.groupby(keys+['same_composition'],dropna=False)[metrics].mean().reset_index()
    a=means[means.same_composition];b=means[~means.same_composition]
    pairs=a.merge(b,on=keys,suffixes=('_same','_different'),validate='one_to_one')
    for metric in metrics:pairs[metric+'_same_minus_different']=pairs[metric+'_same']-pairs[metric+'_different']
    summarize(pairs,['comparison_family','scheme','threshold','candidate_pool','k'],
        [m+'_same_minus_different' for m in metrics],'COMPOSITION_MATCHED_VARIATION',difficulty=False)


def metric_sensitivity(teams):
    ordinary=teams[teams.layer.eq('ordinary_manual')].copy()
    unique=ordinary.drop_duplicates('team_id').copy()
    unique['D10_minus_B8']=unique.D10-unique.B8L2
    summarize(unique,['k'],['D10_minus_B8'],'FIXED_TEAM_METRIC_SENSITIVITY',difficulty=False)
    # Reselect with the frozen D10 profile, then score BOTH selected teams under B8 and D10.
    policies=ordinary[ordinary.request_family.eq('profile_policy') & ordinary.candidate_pool.eq('Q_history_supported_all_origins')]
    keys=['pool_id','image','image_id','building','difficulty','k','strategy','candidate_pool']
    a=policies[policies.selection_metric.eq('B8L2')].copy()
    b=policies[policies.selection_metric.eq('D10')].copy()
    for frame in (a,b):
        if 'draw_id' not in frame:frame['draw_id']=-1
        frame['draw_key']=frame.draw_id.fillna(-1)
    keys+=['draw_key']
    cols=keys+['request_id','team_id','B8L2','D10','complete_evaluable','source_time_total_seconds','member_workers']
    pairs=a[cols].merge(b[cols],on=keys,suffixes=('_B8selected','_D10selected'),validate='one_to_one')
    pairs['B8_reselection_change']=pairs.B8L2_D10selected-pairs.B8L2_B8selected
    pairs['D10_reselection_change']=pairs.D10_D10selected-pairs.D10_B8selected
    pairs['same_actual_team']=pairs.team_id_B8selected.eq(pairs.team_id_D10selected)
    pairs['complete_reselection_change']=pairs.complete_evaluable_D10selected.astype(int)-pairs.complete_evaluable_B8selected.astype(int)
    pairs['source_cost_reselection_change']=pairs.source_time_total_seconds_D10selected-pairs.source_time_total_seconds_B8selected
    pairs['changed_member_fraction']=[1-len(set(a.split('|'))&set(b.split('|')))/k for a,b,k in zip(
        pairs.member_workers_B8selected,pairs.member_workers_D10selected,pairs.k)]
    write_csv_gz(OUT/'METRIC_RESELECTION_PAIRED.csv.gz',clean(pairs.to_dict('records')))
    summarize(pairs,['strategy','candidate_pool','k'],['B8_reselection_change','D10_reselection_change',
        'same_actual_team','changed_member_fraction','complete_reselection_change','source_cost_reselection_change'],
        'METRIC_RESELECTION',difficulty=False)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--part',choices=['all','forward','composition','metric'],default='all')
    args=parser.parse_args()
    required=['request_id','pool_id','image','image_id','building','difficulty','layer','request_family','strategy','selection_metric',
        'candidate_pool','k','draw_id','team_id','member_workers','B8L2','D10','complete_evaluable','source_time_total_seconds']
    teams=pd.read_csv(OUT/'team_results.csv',usecols=lambda c:c in required,low_memory=False)
    assert teams.request_id.is_unique
    assert len(teams)==167581,'do not analyze a partial extension as the final run'
    if args.part in ('all','forward'):
        policy_comparisons(teams);print('forward policy summaries done',flush=True)
    if args.part in ('all','composition'):
        composition_results();print('composition summaries done',flush=True)
    if args.part in ('all','metric'):
        metric_sensitivity(teams);print('metric sensitivity done',flush=True)
    save(OUT/'POLICY_ANALYSIS_NOTES.json',dict(
        same_candidate_pool='All policy contrasts preserve the exact pool/ref/k and prescribed support restrictions. The full-pool random comparisons are separately named because admission differs.',
        direction='Signed changes are treatment minus baseline. Positive Q means higher frozen reference score; negative cost means less recorded source work.',
        building_uncertainty='Mean repeats within image first, then images within building; 5000 building-mean bootstrap draws. CI describes these held-out buildings; all strategies remained fixed.',
        composition='Exact frozen class count vectors, four real member draws; same actual-member aliases excluded from perturbation distributions but their number retained. Class schemes can differ in shared-member fractions; this alone is not causal interchangeability.',
        room_groups='Reuse original declared groups with physical_same=支持 only, no transitive closure or synthetic room. Group-equal averages are sensitivity, not independent group inference.',
        room_metadata_sha256=sha(ROOT/'work_v2_20261019/profiles/DECLARED_ROOM_GROUPS.json'),
        metric='Fixed-member D10-minus-B8 is a scale sensitivity. D10-selected minus B8-selected is a distinct personnel-selection sensitivity. Neither establishes accuracy improvement.',
        failures='Unknown conditional Q stays missing. All attempted teams remain in completeness denominators. Utility Q-or-zero is a separate operational sensitivity, never imputed personnel ability.'))


if __name__=='__main__':main()
