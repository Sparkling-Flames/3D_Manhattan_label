#!/usr/bin/env python3
"""Focused, support-matched interpretation of the saved mixture analysis.

Descriptive finite-population analysis only. Nothing is re-fit or re-scored.
Run after analyze_mixtures.py; writes only this directory.
"""
from pathlib import Path
from itertools import combinations
import json
import numpy as np
import pandas as pd
import analyze_mixtures as base

HERE=Path(__file__).resolve().parent
def read(name):return pd.read_csv(HERE/name,low_memory=False)
def save(d,name):base.save(d,name)

def aggregate_pairs(p,metrics,extra_keys=()):
    keys=['method','source_domain','n','from_class','to_class']+list(extra_keys)
    z=p.groupby(keys+['panel_id','pool_id','image','building'],dropna=False)[metrics].mean().reset_index()
    im=z.groupby(keys+['pool_id','image','building'],dropna=False)[metrics].mean().reset_index()
    return base.attach(im)

def main():
    base.META=base.current_meta()
    a=read('DSTRUCT_ALLIANCE_IMAGE_CONTRASTS.csv.gz')
    q=a[a.B8L2.notna()].copy()
    metrics=['B8L2','D10','IoU3D100','fusion_turn_n','fusion_short_turn_edges',
             'boundary_loss','direction_loss','height_loss','omission','extension']
    save(base.strata(q,['method','from_classes','to_classes'],metrics),
         'DSTRUCT_Q_COMMON_COMPONENT_STRATA.csv')
    cross=[]
    for (fr,to,diff,shape),g in a.groupby(['from_classes','to_classes','official_difficulty','structural_condition']):
        for metric in metrics:
            if g[metric].notna().any():
                z=g if metric=='B8L2' else g[g.B8L2.notna()]
                cross.append(dict(from_classes=fr,to_classes=to,official_difficulty=diff,
                    structural_condition=shape,metric=metric,
                    **base.describe(z,metric,'Q_points' if metric=='B8L2' else metric)))
    save(pd.DataFrame(cross),'DSTRUCT_DIFFICULTY_STRUCTURE_CROSS.csv')
    support=a.groupby(['from_classes','to_classes','official_difficulty','structural_condition']).agg(
        registered_images=('image','nunique'),common_Q_images=('B8L2','count'),
        new_Q_images=('new_Q_available','sum'),lost_Q_images=('lost_Q_available','sum'),
        median_n_from=('n_from','median'),median_n_to=('n_to','median')).reset_index()
    save(support,'DSTRUCT_DIFFICULTY_STRUCTURE_SUPPORT.csv')

    endpoints=read('DSTRUCT_CURRENT_ALLIANCE_ENDPOINTS.csv.gz');synergy=[]
    for pool,g in endpoints.groupby('pool_id'):
        z=g.set_index('classes')
        for ca,cb in combinations(['C1','C2','C3'],2):
            mix=ca+'|'+cb
            if not all(c in z.index and pd.notna(z.loc[c,'B8L2']) for c in [ca,cb,mix]):continue
            qa=z.loc[ca,'B8L2'];qb=z.loc[cb,'B8L2'];r=z.loc[mix]
            synergy.append(dict(method='TARGET_DSTRUCT_K3',pool_id=pool,image=r.image,building=r.building,
                combination=mix,Q_pure_a=qa,Q_pure_b=qb,Q_mixed=r.B8L2,
                mixed_minus_better_pure=r.B8L2-max(qa,qb),mixed_minus_worse_pure=r.B8L2-min(qa,qb),
                n_pure_a=z.loc[ca,'n'],n_pure_b=z.loc[cb,'n'],n_mixed=r.n,
                selection='posthoc_better_pure_descriptive_not_a_policy'))
    sy=base.attach(pd.DataFrame(synergy));save(sy,'DSTRUCT_MIXTURE_VS_BOTH_PURE_IMAGE_EFFECTS.csv')
    save(base.strata(sy,['method','combination'],['mixed_minus_better_pure','mixed_minus_worse_pure'],
        unit_map={'mixed_minus_better_pure':'Q_points','mixed_minus_worse_pure':'Q_points'}),
        'DSTRUCT_MIXTURE_VS_BOTH_PURE_STRATA.csv')

    pairs=read('FIXED_N_ADJACENT_CONFIGURATION_PAIRS.csv.gz')
    p=pairs[pairs.metric.eq('B8L2')&pairs.source_domain.eq('all_formal')].copy()
    focused=[];fi=[]
    for label,g in [('available_Q_configuration_means',p),
                    ('all_teams_Q_valid_in_both_configurations',p[p.both_configurations_fully_observed])]:
        im=aggregate_pairs(g,['effect','mean_within_sd','max_within_p05_p95_width'])
        im['support']=label;fi.append(im)
        s=base.strata(im,['method','source_domain','n','from_class','to_class'],['effect'])
        s['support']=label;focused.append(s)
    save(pd.concat(fi),'FIXED_N_FOCUSED_IMAGE_EFFECTS.csv.gz')
    save(pd.concat(focused),'FIXED_N_FOCUSED_STRATA.csv')

    # Monotonicity requires at least 3 consecutive configuration levels.
    # Chain fractions are averaged within a panel, then within image.
    chains=read('FIXED_N_MONOTONICITY_CHAINS.csv.gz')
    chains=chains[chains.source_domain.eq('all_formal')&chains.steps.ge(2)].copy()
    cm=['nondecreasing','no_drop_above_0_5','both_directions','Q_net','max_drop']
    ci=[];cs=[]
    for label,c in [('available_Q_chain',chains),('all_teams_Q_valid_in_every_configuration',chains[chains.fully_observed])]:
        x=aggregate_pairs(c,cm)
        x['support']=label;ci.append(x)
        sm=base.strata(x,['method','source_domain','n','from_class','to_class'],cm,
            unit_map={'Q_net':'Q_points','max_drop':'Q_points',
                      'nondecreasing':'fraction_of_panel_chains',
                      'no_drop_above_0_5':'fraction_of_panel_chains','both_directions':'fraction_of_panel_chains'})
        sm['support']=label;cs.append(sm)
    save(pd.concat(ci),'FIXED_N_THREE_OR_MORE_LEVEL_CHAINS_BY_IMAGE.csv')
    save(pd.concat(cs),'FIXED_N_THREE_OR_MORE_LEVEL_CHAIN_STRATA.csv')
    save(chains,'FIXED_N_THREE_OR_MORE_LEVEL_CHAINS.csv.gz')

    # Joint Q/labor contrasts: same two configurations and complete valid
    # team support for Q AND positive legal recorded time; new source only.
    pq=pairs[pairs.metric.eq('B8L2')&pairs.both_configurations_fully_observed&pairs.source_domain.eq('new_only')].copy()
    pt=pairs[pairs.metric.eq('log_recorded_time')&pairs.both_configurations_fully_observed&pairs.source_domain.eq('new_only')&
        pairs.time_source.eq('user_processed_reported_not_raw_log_replayed')].copy()
    keys=['method','panel_id','pool_id','image','building','source_domain','n',
          'from_class','to_class','from_counts','to_counts']
    jt=pq[keys+['effect','teams_from','teams_to']].merge(
        pt[keys+['effect','teams_from','teams_to']],on=keys,suffixes=('_Q','_logT'),validate='one_to_one')
    counts_match=(jt.teams_from_Q==jt.teams_from_logT)&(jt.teams_to_Q==jt.teams_to_logT)
    excluded_Q_T_pairs=int((~counts_match).sum())
    save(jt[~counts_match],'Q_T_EXCLUDED_UNEQUAL_TEAM_SUPPORT.csv')
    jt=jt[counts_match].copy()
    assert (jt.teams_from_Q==jt.teams_from_logT).all() and (jt.teams_to_Q==jt.teams_to_logT).all()
    jt=base.attach(jt);save(jt,'Q_T_IDENTICAL_COMPLETE_CONFIGURATION_PAIRS.csv.gz')
    j=aggregate_pairs(jt,['effect_Q','effect_logT'])
    j['geometric_team_time_ratio']=np.exp(j.effect_logT)
    j['Q_up_time_not_up']=j.effect_Q.gt(1e-9)&j.effect_logT.le(1e-9)
    j['Q_up_time_up']=j.effect_Q.gt(1e-9)&j.effect_logT.gt(1e-9)
    save(j,'Q_T_IDENTICAL_COMPLETE_IMAGE_EFFECTS.csv')
    sm=base.strata(j,['method','source_domain','n','from_class','to_class'],['effect_Q','effect_logT'],
        unit_map={'effect_Q':'Q_points','effect_logT':'log_team_recorded_time'})
    save(sm,'Q_T_IDENTICAL_COMPLETE_STRATA.csv')
    save(j.groupby(['method','n','from_class','to_class']).agg(images=('image','nunique'),
        buildings=('building','nunique'),Q_up_time_not_up_images=('Q_up_time_not_up','sum'),
        Q_up_time_up_images=('Q_up_time_up','sum')) .reset_index(),'Q_T_IDENTICAL_COMPLETE_QUADRANTS.csv')

    mem=read('SAME_CONFIGURATION_MEMBER_DISTRIBUTIONS.csv.gz')
    mem=mem[mem.source_domain.eq('all_formal')&mem.member_variation_estimable].copy()
    # Equal weighting of configurations within panel and then panels within
    # image, and median as an explicit companion rather than an alternative n.
    keys=['method','source_domain','n','panel_id','pool_id','image','building']
    mm=mem.groupby(keys).agg(mean_member_sd=('sd','mean'),median_member_sd=('sd','median'),
        mean_p05_p95_width=('within_p05_p95_width','mean'),
        median_p05_p95_width=('within_p05_p95_width','median'),
        max_p05_p95_width=('within_p05_p95_width','max'),
        configurations=('class_counts','size')).reset_index()
    save(mm,'MEMBER_SPREAD_BY_PANEL.csv')
    vals=['mean_member_sd','median_member_sd','mean_p05_p95_width','median_p05_p95_width','max_p05_p95_width']
    mi=mm.groupby(['method','source_domain','n','pool_id','image','building'])[vals].mean().reset_index()
    mi=base.attach(mi);save(mi,'MEMBER_SPREAD_BY_IMAGE.csv')
    save(base.strata(mi,['method','source_domain','n'],vals,unit_map={v:'Q_points' for v in vals}),'MEMBER_SPREAD_STRATA.csv')

    # Candidate illustrations are explicitly selected after observing effects:
    # one median of the prespecified occlusion subgroup, an opposite case,
    # and a small-effect nonoccluded control. No population claims use them.
    candidates=[]
    g=q[q.from_classes.eq('C3')&q.to_classes.eq('C2|C3')]
    targets=[('occluded_median_effect',g[g.structural_condition.eq('boundary_self_occlusion')],None),
        ('occluded_reverse_example',g[g.structural_condition.eq('boundary_self_occlusion')&g.B8L2.gt(0)],'highest'),
        ('nonoccluded_near_zero',g[g.structural_condition.eq('no_short_turns_or_boundary_occlusion')],'zero')]
    for kind,z,selector in targets:
        if z.empty:continue
        value=0 if selector=='zero' else z.B8L2.median()
        chosen=z.sort_values('B8L2',ascending=False).iloc[0] if selector=='highest' else z.iloc[np.argmin(abs(z.B8L2-value))]
        row=chosen.to_dict();row['selection']=kind
        row['selection_status']='posthoc_illustration_not_new_evidence_or_predefined_subgroup'
        candidates.append(row)
    save(pd.DataFrame(candidates),'ILLUSTRATION_CANDIDATE_ENDPOINTS.csv')
    checks=dict(current_meta_images=int(base.META[base.META.scope.eq('primary')&base.META.condition.eq('manual')].image.nunique()),
        identical_Q_T_pair_rows=len(jt),identical_Q_T_team_counts=True,
        excluded_Q_T_unequal_team_support_pairs=excluded_Q_T_pairs,
        monotonicity_minimum_levels=3,monotonicity_weighting='chain within panel; panel within image',
        no_new_teams=True,no_Q_imputation=True,status='passed')
    (HERE/'DEPTH_CHECKS.json').write_text(json.dumps(checks,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(checks,ensure_ascii=False),flush=True)

if __name__=='__main__':main()
