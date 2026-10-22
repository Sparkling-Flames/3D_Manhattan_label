"""Build compact, interpretable tables from frozen expansion aggregates.

No endpoint calculation and no result-dependent condition selection. Tables
retain all registered conditions, seed cohorts, difficulty strata, and failures.
"""
from __future__ import annotations
import os
for _k in ['OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS']:
    os.environ[_k]='1'
from pathlib import Path
import argparse,json,sys
import numpy as np,pandas as pd
HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE))
import analyze_expanded_results as analysis
from analyze_expanded_results import save_csv,save_json,sha,define_group,BASE,VIEWS,truth

META=BASE+['view','cohort','direction','difficulty_stratum','summary_id','status',
 'registered_events','complete_events','registered_panels','complete_panels',
 'registered_images','complete_images','registered_buildings','complete_buildings','complete_backgrounds']
SHORT={
 'common_quality_within_abs':'within_abs_Q','common_quality_cross_abs':'cross_abs_Q',
 'abs_Q_change_advantage':'abs_Q_advantage','cross_B8L2':'delta_Q','cross_D10':'delta_D10',
 'cross_IoU3D100':'delta_3Dproxy','cross_iou_2d':'delta_BEV',
 'cross_ref_node_recall_5':'delta_node_recall','cross_ref_edge_recall_5':'delta_edge_recall',
 'cross_omission':'delta_omission','cross_extension':'delta_extension',
 'cross_fusion_turn_n':'delta_effective_turns','cross_fusion_short_turn_edges':'delta_short_edges',
 'cross_fusion_redundancy_n':'delta_redundant_vertices',
 'cross_recorded_time_pct':'delta_recorded_person_seconds_pct',
 'cross_B8L2_time_qualified':'delta_Q_time_qualified',
 'cross_history_block_Q_change':'delta_history_Q',
 'A_failure':'A_failure_fraction','B_failure':'B_failure_fraction','C_failure':'C_failure_fraction',
 'same_loss_gt10':'within_success_loss_gt10','cross_loss_gt10':'cross_success_loss_gt10',
 'same_failure_or_loss_gt10':'within_failure_or_loss_gt10',
 'cross_failure_or_loss_gt10':'cross_failure_or_loss_gt10',
 'fraction_cross_larger_abs_Q':'fraction_cross_larger_abs_Q',
 'common_geometry_advantage_floor_jaccard_difference':'floor_geometry_advantage',
 'common_geometry_advantage_mean_height_prism_pair_difference':'prism_geometry_advantage'}

def readable(core):
    out=core[META].drop_duplicates('summary_id').set_index('summary_id')
    for metric,label in SHORT.items():
        g=core[core.metric.eq(metric)].set_index('summary_id')
        for f,tag in [('building_mean','mean'),('building_median','median'),('valid_events','valid_events'),
          ('valid_images','valid_images'),('valid_buildings','valid_buildings'),
          ('positive_images','positive_images'),('negative_images','negative_images'),
          ('positive_buildings','positive_buildings'),('negative_buildings','negative_buildings')]:
            out[label+'__'+tag]=g[f]
        if metric in ['cross_B8L2','abs_Q_change_advantage']:
            for f in ['building_bootstrap_lo95','building_bootstrap_hi95','exact_event_median']:
                out[label+'__'+f]=g[f]
        if metric in ['A_failure','B_failure','C_failure','same_loss_gt10','cross_loss_gt10']:
            # Binary event metrics have integer numerators; use the exact
            # event-weighted mean/denominator, never multiply building means.
            out[label+'__event_numerator']=(g.event_weighted_mean*g.valid_events).round()
        if metric.startswith('cross_recorded_time'):
            out[label+'__negative_backgrounds']=g.negative_backgrounds
    return out.reset_index()

def member_variation(p,m,registered,status):
    # A and B enumerate identical source sets in complementary orientation;
    # report A once. C's singleton is not a member-variation opportunity.
    cols=[c for c in m if c.startswith(('B8L2_','D10_','fusion_turn_n_'))]
    out=[];detail=[]
    for view in VIEWS:
        for cohort in ['all_images','priority_seed_images','additional_images']:
            x,idx=define_group(p,view,cohort,False)
            context=x[['panel_id','summary_id','building','image','background_id']]
            z=m[m.arm.isin(['A','C'])][['panel_id','arm','unique_member_sets','failed_member_sets','failed_fraction']+cols].merge(context,on='panel_id',validate='many_to_many')
            if not len(z):continue
            z['composition_role']=np.where(z.arm.eq('A'),'unchanged_source_composition','changed_target_composition')
            for metric in ['B8L2','D10','fusion_turn_n']:
                z[metric+'_range']=z[metric+'_max']-z[metric+'_min']
                z[metric+'_p90_minus_p10']=z[metric+'_q90']-z[metric+'_q10']
                # Do not mislabel a singleton zero as evidence of interchangeability.
                z.loc[z[metric+'_valid_member_sets'].lt(2),[metric+'_std',metric+'_range',metric+'_p90_minus_p10']]=np.nan
            detail.append(z.assign(view=view,cohort=cohort))
            measurements=['failed_fraction']+[metric+'_'+stat for metric in ['B8L2','D10','fusion_turn_n'] for stat in ['std','range','p90_minus_p10','q05','mean']]
            bg=z.groupby(['summary_id','composition_role','building','image','background_id'])[measurements].mean()
            im=bg.groupby(level=['summary_id','composition_role','building','image']).mean()
            buildings=im.groupby(level=['summary_id','composition_role','building']).mean()
            for (sid,role),g in z.groupby(['summary_id','composition_role']):
                b=buildings.loc[(sid,role)]
                meta=idx[idx.summary_id.eq(sid)].iloc[0].to_dict()
                row=dict(meta,composition_role=role,status=status,panels=len(g),images=g.image.nunique(),buildings=g.building.nunique(),
                  panels_with_at_least_two_member_sets=int(g.unique_member_sets.ge(2).sum()),
                  singleton_panels=int(g.unique_member_sets.eq(1).sum()),
                  registered_member_sets_min=int(g.unique_member_sets.min()),registered_member_sets_max=int(g.unique_member_sets.max()),
                  member_counts_are_panel_specific_not_global_unique=True)
                for metric in measurements:
                    v=b[metric].dropna().to_numpy(float)
                    row[metric+'__valid_buildings']=len(v)
                    row[metric+'__building_mean']=float(v.mean()) if len(v) else np.nan
                    row[metric+'__building_median']=float(np.median(v)) if len(v) else np.nan
                out.append(row)
    return pd.DataFrame(out),pd.concat(detail,ignore_index=True)

def background_sensitivity(p,status):
    """Within the same image/direction, how do the two sampled backgrounds vary?"""
    rows=[]
    metrics=['common_quality_within_abs','common_quality_cross_abs','abs_Q_change_advantage','cross_B8L2',
             'cross_ref_node_recall_5','cross_ref_edge_recall_5','cross_fusion_turn_n','cross_recorded_time_pct']
    for cell,g in p.groupby('cell_id'):
        meta={k:g.iloc[0][k] for k in CONTEXT_BG if k in g}
        row=dict(meta,status=status,registered_panels=len(g),distinct_backgrounds=g.background_id.nunique(),events=int(g.events.sum()))
        for metric in metrics:
            v=g.groupby('background_id')[metric].mean().dropna().to_numpy(float)
            row[metric+'__backgrounds']=len(v)
            row[metric+'__mean']=float(v.mean()) if len(v) else np.nan
            row[metric+'__min']=float(v.min()) if len(v) else np.nan
            row[metric+'__max']=float(v.max()) if len(v) else np.nan
            row[metric+'__range']=float(v.max()-v.min()) if len(v)>=2 else np.nan
            row[metric+'__both_or_all_positive']=bool((v>1e-10).all()) if len(v)>=2 else None
            row[metric+'__both_or_all_negative']=bool((v< -1e-10).all()) if len(v)>=2 else None
            row[metric+'__opposite_signs']=bool((v>1e-10).any() and (v< -1e-10).any()) if len(v)>=2 else None
        rows.append(row)
    return pd.DataFrame(rows)

CONTEXT_BG=['cell_id','pool_id','image','building','condition','difficulty','layer','method_id','tier','source_domain',
 'n','m','source_class','target_class','source_role','target_role','selected_family','training_turn_direction',
 'seed_cohort','parent_fixed']

def run(partial=False):
    prefix='PARTIAL' if partial else 'FINAL'
    receipt=json.loads((HERE/(prefix+'_ANALYSIS_COMPLETION.json')).read_text())
    if not partial:
        assert receipt['status']=='FINAL_COMPLETE' and receipt['pending_cells']==0
        assert receipt['complete_events']==receipt['registered_events'] and receipt['complete_panels']==receipt['registered_panels']
    state=receipt['status']
    p=pd.read_csv(HERE/('PANEL_COMPLETE_RESULTS_'+state+'.csv.gz'),low_memory=False)
    m=pd.read_csv(HERE/('MEMBER_RESPONSE_'+state+'.csv.gz'),low_memory=False)
    registered=analysis.prepare_registered(pd.read_csv(analysis.EX/'REGISTERED_MEMBER_PANELS.csv.gz'))
    core=pd.read_csv(HERE/(prefix+'_CORE_SUMMARY.csv.gz'),low_memory=False)
    r=readable(core)
    files=[save_csv(prefix+'_READABLE_CONDITIONS.csv.gz',r)]
    principal=r[(r.difficulty_stratum=='ALL') & ((r.view=='class_direction') |
      ((r.method_id=='V3_BEHAVIOR') & (r.view=='training_turn_direction')) |
      (r.view=='method_n_m'))].copy()
    files.append(save_csv(prefix+'_PRINCIPAL_CONDITIONS.csv',principal))
    member,detail=member_variation(p,m,registered,state)
    files.extend([save_csv(prefix+'_CONDITION_MEMBER_VARIATION.csv.gz',member),
                  save_csv(prefix+'_MEMBER_VARIATION_PANEL_DETAIL.csv.gz',detail),
                  save_csv(prefix+'_BACKGROUND_SENSITIVITY.csv',background_sensitivity(p,state))])
    result=dict(status=state,source_receipt_sha256=sha(HERE/(prefix+'_ANALYSIS_COMPLETION.json')),files=files,
      no_result_dependent_condition_selection=True,native_calls=0,
      population_sd='finite registered member census within each panel; A/B symmetric source sets reported once',
      singleton='C has one member set in some panels; variance/range are unknown rather than evidence from a zero',
      member_counts='panel-specific; do not sum overlapping panels as globally distinct endpoints')
    save_json(prefix+'_READABLE_COMPLETION.json',result)
    print(json.dumps({k:v for k,v in result.items() if k!='files'},ensure_ascii=False))

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--partial',action='store_true');run(parser.parse_args().partial)
