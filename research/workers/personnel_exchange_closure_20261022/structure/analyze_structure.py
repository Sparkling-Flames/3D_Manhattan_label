#!/usr/bin/env python3
"""Exact-denominator, hierarchy-aware structure replacement summaries.

Events are never treated as independent people or images. The primary mean is
events within D, D within feasible background-count stratum, strata within an
image, images within a building, then buildings equally. Raw event means and
all metric-specific denominators are also exported. This preserves the exact
count-vector coverage without letting the deeper member panels dominate it.
"""
from __future__ import annotations
import collections, json, math, sys
from pathlib import Path
import numpy as np
import pandas as pd
from register_structure import HERE, h, sha, write, save, gs

BASE=['study_group','source_domain','source_role','target_role','n','m']
MAIN_METRICS=['same_B8L2','cross_B8L2','net_B8L2','same_D10','cross_D10','net_D10',
 'common_quality_within_abs','common_quality_cross_abs','abs_Q_change_advantage',
 'A_failure','B_failure','C_failure','cross_loss_gt10','net_loss_gt10',
 'cross_loss_gt10_or_destination_failure','net_loss_gt10_or_destination_failure',
 'cross_IoU3D100','net_IoU3D100','cross_iou_2d','net_iou_2d',
 'cross_S_bottom_deg','net_S_bottom_deg','cross_dir','net_dir','cross_Hmean','net_Hmean',
 'cross_Hcenter','net_Hcenter','cross_omission','net_omission','cross_extension','net_extension',
 'cross_nodes','net_nodes','cross_fusion_turn_n','net_fusion_turn_n',
 'cross_ref_node_recall_5','net_ref_node_recall_5','cross_ref_edge_recall_5','net_ref_edge_recall_5',
 'cross_ref_node_recall_9','net_ref_node_recall_9','cross_ref_edge_recall_9','net_ref_edge_recall_9',
 'cross_recorded_time_pct','net_recorded_time_pct','cross_recorded_time_logratio','net_recorded_time_logratio',
 'common_geometry_advantage_floor_jaccard_difference','common_geometry_advantage_mean_height_prism_pair_difference',
 'common_geometry_advantage_centroid_distance_h','common_geometry_advantage_structure_bound_cyclic_deg',
 'common_corner_within_bev_mean_h','common_corner_cross_bev_mean_h','common_corner_advantage_bev_mean_h',
 'common_corner_within_top_mean_h','common_corner_cross_top_mean_h','common_corner_advantage_top_mean_h']

def numeric_metrics(E):
    pref=('same_','cross_','net_','within_','common_quality_','common_geometry_','common_expression_','common_corner_','common_component_','stable_')
    want=[c for c in E.columns if c.startswith(pref) or c in ['abs_Q_change_advantage','time_abs_variation_advantage']]
    want += [a+'_'+f for a in 'ABC' for f in ['failure','B8L2','D10','nodes','fusion_turn_n','fusion_short_turn_edges',
             'fusion_redundancy_n','half_vote_nodes'] if a+'_'+f in E]
    out=[]
    for c in dict.fromkeys(want):
        if any(x in c for x in ['_workers','_counts','_status','_reason','_feature_ids']):continue
        x=pd.to_numeric(E[c],errors='coerce')
        if x.notna().any():E[c]=x;out.append(c)
    return out

def common_local_components(E):
    cols=[]
    for f in ['bev_mean_h','bev_max_h','top_mean_h','top_max_h','angle_deg']:
        x=pd.to_numeric(E['within_corner_'+f],errors='coerce');y=pd.to_numeric(E['cross_corner_'+f],errors='coerce')
        ok=E.all_complete.eq(True)&x.notna()&y.notna()
        for label,v in [('within',x),('cross',y),('advantage',y-x)]:
            c='common_corner_'+label+'_'+f;E[c]=v.where(ok);cols.append(c)
    for f in ['D10','IoU3D100','iou_2d','S_bottom_deg','dir','Hmean','Hcenter','omission','extension']:
        x=pd.to_numeric(E['same_'+f],errors='coerce');y=pd.to_numeric(E['cross_'+f],errors='coerce')
        ok=E.all_complete.eq(True)&x.notna()&y.notna()
        for label,v in [('within_abs',x.abs()),('cross_abs',y.abs()),('advantage',y.abs()-x.abs())]:
            c='common_component_'+label+'_'+f;E[c]=v.where(ok);cols.append(c)
    return E[['event_id','pool_id','image','building']+BASE+cols].copy()

def hierarchy(E,metrics,extra=()):
    base=BASE+list(extra)
    image=base+['building','image','pool_id']
    strata=image+['background_stratum']
    panel=strata+['panel_id']
    P=E.groupby(panel,dropna=False)[metrics].mean().reset_index()
    S=P.groupby(strata,dropna=False)[metrics].mean().reset_index()
    I=S.groupby(image,dropna=False)[metrics].mean().reset_index()
    B=I.groupby(base+['building'],dropna=False)[metrics].mean().reset_index()
    return P,S,I,B

def condition_key(r,extra=()):return tuple(r[k] for k in BASE+list(extra))
def ci(values,seed):
    a=np.asarray(values,float);a=a[np.isfinite(a)]
    if len(a)<2:return (np.nan,np.nan)
    rng=np.random.default_rng(int(h('building-bootstrap',gs.clean(seed))[:16],16))
    vals=a[rng.integers(0,len(a),size=(2048,len(a)))].mean(axis=1)
    return tuple(np.quantile(vals,[.025,.975]))

def summarize(E,metrics,P,I,B,extra=()):
    base=BASE+list(extra);rows=[];wide=[]
    groups={condition_key(dict(zip(base,k if isinstance(k,tuple) else (k,))),extra):g for k,g in E.groupby(base,dropna=False)}
    pi={k:g for k,g in P.groupby(base,dropna=False)};ii={k:g for k,g in I.groupby(base,dropna=False)};bb={k:g for k,g in B.groupby(base,dropna=False)}
    for key,g in groups.items():
        panel,image,building=pi[key],ii[key],bb[key];meta=dict(zip(base,key))
        w=dict(meta,registered_events=len(g),unique_physical_triples=g.physical_triple_id.nunique(),
            unique_endpoints=len(set(g.team_A)|set(g.team_B)|set(g.team_C)),
            images_total=g.image.nunique(),buildings_total=g.building.nunique(),backgrounds_total=g.panel_id.nunique(),
            count_vectors_observed=g.groupby(['pool_id','background_stratum']).ngroups,
            all_three_Q_events=int(g.all_scored.sum()),all_three_geometry_events=int(g.all_complete.sum()),
            recorded_time_events=int(g.recorded_time_single_source.sum()))
        for arm in 'ABC':
            ts=g[['team_'+arm,arm+'_failure']].drop_duplicates('team_'+arm)
            w[arm+'_unique_endpoints']=len(ts);w[arm+'_unique_failed_endpoints']=int(ts[arm+'_failure'].sum())
        for metric in metrics:
            a=pd.to_numeric(g[metric],errors='coerce').dropna();p=panel[metric].dropna();i=image[metric].dropna();b=building[metric].dropna()
            if not len(a):continue
            lo,hi=ci(b.to_numpy(),(key,metric)) if metric in MAIN_METRICS else (np.nan,np.nan)
            row=dict(meta,metric=metric,event_n=len(a),panel_n=len(p),image_n=len(i),building_n=len(b),
                event_mean=float(a.mean()),image_equal_mean=float(i.mean()),building_equal_mean=float(b.mean()),
                images_positive=int((i>1e-9).sum()),images_zero=int((i.abs()<=1e-9).sum()),images_negative=int((i < -1e-9).sum()),
                buildings_positive=int((b>1e-9).sum()),buildings_zero=int((b.abs()<=1e-9).sum()),buildings_negative=int((b < -1e-9).sum()),
                panel_positive=int((p>1e-9).sum()),building_bootstrap_95_low=lo,building_bootstrap_95_high=hi)
            rows.append(row)
            if metric in MAIN_METRICS:
                w[metric+'_mean']=row['building_equal_mean'];w[metric+'_event_n']=row['event_n']
                for f in ['image_n','building_n','images_positive','buildings_positive','images_negative','buildings_negative']:
                    w[metric+'_'+f]=row[f]
                if metric in ['same_B8L2','cross_B8L2','net_B8L2','abs_Q_change_advantage']:
                    w[metric+'_image_median']=float(i.median());w[metric+'_image_p10']=float(i.quantile(.1));w[metric+'_image_p90']=float(i.quantile(.9))
                    w[metric+'_images_ge1']=int((i>=1).sum());w[metric+'_images_le_minus5']=int((i<=-5).sum())
                    w[metric+'_building_ci_low']=lo;w[metric+'_building_ci_high']=hi
                if metric.endswith('_recorded_time_logratio'):w[metric+'_geometric_pct']=100*math.expm1(row['building_equal_mean'])
        # The raw event positive rate has its own denominator; no extra events
        # are described as new independent images or backgrounds.
        for prefix in ['same','cross','net']:
            q=g[prefix+'_B8L2'].dropna()
            w[prefix+'_Q_positive_events']=int((q>0).sum());w[prefix+'_Q_evaluable_events']=len(q)
            w[prefix+'_Q_positive_event_fraction']=float((q>0).mean()) if len(q) else np.nan
            w[prefix+'_Q_at_least_1_event_fraction']=float((q>=1).mean()) if len(q) else np.nan
        wide.append(w)
    return pd.DataFrame(rows),pd.DataFrame(wide)

def background_and_member_robustness(E):
    rows=[]
    for kind,fields in [('background',['panel_id']),('source_pair',['panel_id','source_pair_index']),('target_block',['panel_id','target_block_index'])]:
        g=E.groupby(BASE+['building','image']+fields,dropna=False)[['cross_B8L2','net_B8L2','abs_Q_change_advantage','C_failure']].mean().reset_index()
        for key,d in g.groupby(BASE,dropna=False):
            for f in ['cross_B8L2','net_B8L2','abs_Q_change_advantage']:
                v=d[f].dropna()
                rows.append(dict(zip(BASE,key),unit=kind,metric=f,units=len(v),units_positive=int((v>0).sum()),
                    positive_fraction=float((v>0).mean()) if len(v) else np.nan,images=d.image.nunique(),buildings=d.building.nunique(),
                    mean=float(v.mean()) if len(v) else np.nan,p10=float(v.quantile(.1)) if len(v) else np.nan,
                    median=float(v.median()) if len(v) else np.nan,p90=float(v.quantile(.9)) if len(v) else np.nan))
    return rows

def concrete_block_diversity(E):
    rows=[]
    for key,g in E[E.study_group.isin(['main_n20','new_only_n20_recorded_time'])].groupby(BASE+['building','image','pool_id']):
        xs=set(g.outgoing_block_X)|set(g.same_count_block_Y);zs=set(g.changed_count_block_Z)
        byD=g.groupby('common_background').changed_count_block_Z.nunique()
        source_people=set(w for block in xs for w in block.split('|'));target_people=set(w for block in zs for w in block.split('|'))
        rows.append(dict(zip(BASE+['building','image','pool_id'],key),
            different_common_backgrounds=g.common_background.nunique(),source_unique_blocks=len(xs),target_unique_blocks=len(zs),
            different_unordered_source_pairs=len({tuple(sorted((x,y))) for x,y in zip(g.outgoing_block_X,g.same_count_block_Y)}),
            source_people_exercised=len(source_people),target_people_exercised=len(target_people),
            backgrounds_with_multiple_target_blocks=int(byD.gt(1).sum()),
            target_member_variation_estimable_across_registered_backgrounds=len(zs)>1,
            target_member_variation_estimable_at_some_fixed_background=bool(byD.gt(1).any()),
            unique_C_endpoints=g.team_C.nunique()))
    return pd.DataFrame(rows)

def matched_explanatory_checks(E,metrics):
    rows=[]
    for label,mask in [('all_registered',pd.Series(True,index=E.index)),
                       ('same_origin_counts',E.same_source_counts.eq(True)),
                       ('same_origin_historyQ_within_5',E.source_and_historyQ5_matched.eq(True)),
                       ('same_origin_historyQ_within_2',E.source_and_historyQ2_matched.eq(True))]:
        d=E[mask].copy()
        if not len(d):continue
        mm=[f for f in MAIN_METRICS if f in metrics]
        P,S,I,B=hierarchy(d,mm);long,wide=summarize(d,mm,P,I,B)
        wide.insert(0,'explanatory_subset',label);rows.append(wide)
    return pd.concat(rows,ignore_index=True) if rows else pd.DataFrame()

def linked_n_changes(E):
    d=E[E.study_group.eq('linked_n')];out=[]
    fields=['same_B8L2','cross_B8L2','net_B8L2','abs_Q_change_advantage','A_nodes','B_nodes','C_nodes',
       'A_failure','B_failure','C_failure','A_half_vote_nodes','B_half_vote_nodes','C_half_vote_nodes',
       'cross_ref_node_recall_5','cross_ref_edge_recall_5','net_ref_node_recall_5','net_ref_edge_recall_5',
       'cross_IoU3D100','net_IoU3D100','cross_S_bottom_deg','net_S_bottom_deg']
    for path,g in d.groupby('linked_n_path_id'):
        gg=g.sort_values('n');records=list(gg.to_dict('records'))
        for left,right in zip(records,records[1:]):
            r={k:left[k] for k in BASE if k!='n'}
            r.update(linked_n_path_id=path,image=left['image'],building=left['building'],difficulty=left['difficulty'],
                n_from=left['n'],n_to=right['n'],support_from=left['minimum_support'],support_to=right['minimum_support'],
                added_D='|'.join(sorted(set(right['common_background'].split('|'))-set(left['common_background'].split('|')))),
                event_from=left['event_id'],event_to=right['event_id'],same_XYZ=True)
            for f in fields:
                x,y=left.get(f,np.nan),right.get(f,np.nan);r[f+'_from']=x;r[f+'_to']=y
                r[f+'_delta']=y-x if pd.notna(x) and pd.notna(y) else np.nan
            x,y=r['net_B8L2_from'],r['net_B8L2_to']
            r['net_Q_sign_reversal']=int(x*y<0) if pd.notna(x) and pd.notna(y) else np.nan
            r['net_Q_material_reversal']=int((x>=2 and y<=-2) or (x<=-2 and y>=2)) if pd.notna(x) and pd.notna(y) else np.nan
            r['threshold_jump_plus_node_loss_C']=bool(r['support_to']>r['support_from'] and pd.notna(r['C_nodes_delta']) and r['C_nodes_delta']<0)
            out.append(r)
    df=pd.DataFrame(out)
    if not len(df):return df,pd.DataFrame()
    ff=[c for c in df.columns if c.endswith('_delta') or c in ['net_Q_sign_reversal','net_Q_material_reversal','threshold_jump_plus_node_loss_C']]
    group=['source_role','target_role','m','n_from','n_to','support_from','support_to']
    I=df.groupby(group+['building','image'])[ff].mean().reset_index()
    B=I.groupby(group+['building'])[ff].mean().reset_index()
    rows=[]
    for key,g in B.groupby(group):
        sub=df
        for f,v in zip(group,key):sub=sub[sub[f].eq(v)]
        r=dict(zip(group,key),paths=len(sub),images=sub.image.nunique(),buildings=sub.building.nunique())
        r.update({f+'_building_mean':float(g[f].mean()) for f in ff})
        rows.append(r)
    return df,pd.DataFrame(rows)

def mechanism_candidates(E,changes):
    candidate=[];d=E[E.study_group.eq('main_n20') & E.all_scored.eq(True)].copy()
    masks={
      'position_gain_same_node_count':d.net_nodes.eq(0)&d.net_B8L2.ge(3)&d.net_S_bottom_deg.lt(0),
      'structure_added_quality_gain':d.net_fusion_turn_n.gt(0)&d.net_ref_edge_recall_5.gt(0)&d.net_B8L2.ge(3),
      'large_quality_loss':d.net_B8L2.le(-10),
    }
    for typ,mask in masks.items():
        x=d[mask].copy()
        # Several buildings, closest to a representative rather than extreme gain.
        target=6 if typ!='large_quality_loss' else -15
        x['case_distance']=(x.net_B8L2-target).abs()
        x=x.sort_values(['case_distance','event_id']).drop_duplicates('building').head(8)
        for r in x.to_dict('records'):candidate.append(dict(case_type=typ,**r))
    x=E[E.study_group.eq('main_n20')&E.C_failure.eq(True)&E.B_failure.eq(False)].sort_values('event_id').drop_duplicates('building').head(8)
    for r in x.to_dict('records'):candidate.append(dict(case_type='destination_fusion_failure',**r))
    if len(changes):
        x=changes[(changes.n_from.eq(20)&changes.n_to.eq(21)) &
                  (changes.net_Q_material_reversal.eq(1)|changes.threshold_jump_plus_node_loss_C.eq(True))]
        x=x.sort_values(['net_Q_material_reversal','net_B8L2_delta'],ascending=[False,True]).drop_duplicates('building').head(8)
        for r in x.to_dict('records'):
            ev=E[E.event_id.eq(r['event_to'])].iloc[0].to_dict()
            candidate.append(dict(case_type='n20_to_n21_threshold_candidate',**ev,
                paired_event_from=r['event_from'],paired_n_from=r['n_from'],paired_net_Q_from=r['net_B8L2_from'],
                paired_net_Q_to=r['net_B8L2_to'],paired_added_D=r['added_D']))
    return pd.DataFrame(candidate)

def linked_m_changes(E):
    d=E[E.study_group.eq('linked_m')]
    if not len(d):return pd.DataFrame(),pd.DataFrame()
    fields=[c for c in MAIN_METRICS if c in d]
    out=[]
    for path,g in d.groupby('linked_m_path_id'):
        records=list(g.sort_values('m').to_dict('records'))
        contrasts=[('adjacent',a,b) for a,b in zip(records,records[1:])]
        if len(records)>2:contrasts.append(('m4_to_max',records[0],records[-1]))
        for kind,left,right in contrasts:
            assert left['team_A']==right['team_A']
            lx=set(left['outgoing_block_X'].split('|'));rx=set(right['outgoing_block_X'].split('|'))
            ly=set(left['same_count_block_Y'].split('|'));ry=set(right['same_count_block_Y'].split('|'))
            lz=set(left['changed_count_block_Z'].split('|'));rz=set(right['changed_count_block_Z'].split('|'))
            ld=set(left['common_background'].split('|'));rd=set(right['common_background'].split('|'))
            assert lx<=rx and ly<=ry and lz<=rz and rd<=ld and ld-rd==rx-lx
            r=dict(path_kind=kind,linked_m_path_id=path,image=left['image'],building=left['building'],difficulty=left['difficulty'],
                source_role=left['source_role'],target_role=left['target_role'],n=20,m_from=left['m'],m_to=right['m'],
                incremental_actual_m=right['m']-left['m'],A_fixed_team_key=left['team_A'],same_A=True,
                moved_D_to_X='|'.join(sorted(rx-lx)),added_Y='|'.join(sorted(ry-ly)),added_Z='|'.join(sorted(rz-lz)),
                event_from=left['event_id'],event_to=right['event_id'],minimum_support=left['minimum_support'])
            for f in fields:
                x,y=left.get(f,np.nan),right.get(f,np.nan);r[f+'_from']=x;r[f+'_to']=y
                r[f+'_delta']=y-x if pd.notna(x) and pd.notna(y) else np.nan
            x,y=r['net_B8L2_from'],r['net_B8L2_to']
            r['net_Q_sign_reversal']=int(x*y<0) if pd.notna(x) and pd.notna(y) else np.nan
            out.append(r)
    df=pd.DataFrame(out)
    if not len(df):return df,pd.DataFrame()
    group=['path_kind','source_role','target_role','n','m_from','m_to','incremental_actual_m']
    metrics=[c for c in df if c.endswith('_delta')]+['net_Q_sign_reversal']
    I=df.groupby(group+['building','image'])[metrics].mean().reset_index()
    B=I.groupby(group+['building'])[metrics].mean().reset_index()
    rows=[]
    for key,g in B.groupby(group):
        sub=df;ii=I
        for f,v in zip(group,key):sub=sub[sub[f].eq(v)];ii=ii[ii[f].eq(v)]
        r=dict(zip(group,key),paths=len(sub),images=sub.image.nunique(),buildings=sub.building.nunique())
        for f in metrics:
            r[f+'_building_mean']=float(g[f].mean())
            r[f+'_images_evaluable']=int(ii[f].notna().sum());r[f+'_images_positive']=int(ii[f].gt(0).sum())
            r[f+'_buildings_evaluable']=int(g[f].notna().sum());r[f+'_buildings_positive']=int(g[f].gt(0).sum())
        rows.append(r)
    return df,pd.DataFrame(rows)

def main():
    E=pd.read_csv(HERE/'EVENTS_COMPLETE.csv.gz',low_memory=False)
    local=common_local_components(E)
    metrics=numeric_metrics(E)
    P,S,I,B=hierarchy(E,metrics)
    long,wide=summarize(E,metrics,P,I,B)
    outputs=[write(HERE/'analysis/PAIR_LOCAL_COMPONENTS_COMMON.csv.gz',local)]
    for name,d in [('PANEL_EFFECTS.csv.gz',P),('COUNT_STRATUM_EFFECTS.csv.gz',S),('IMAGE_EFFECTS.csv.gz',I),
                   ('BUILDING_EFFECTS.csv.gz',B),('CONDITION_METRICS_LONG.csv.gz',long),('EFFECTIVE_CONDITIONS.csv',wide)]:
        outputs.append(write(HERE/'analysis'/name,d))
    # Difficulty and background composition are pre-outcome metadata conditions.
    for extra,name in [(['difficulty'],'DIFFICULTY_CONDITIONS.csv'),(['background_target_band'],'BACKGROUND_CONDITIONS.csv'),
                       (['selection_partition'],'MEMBER_BACKGROUND_CHECK_PARTITIONS.csv')]:
        mm=[f for f in MAIN_METRICS if f in metrics]
        pp,ss,ii,bb=hierarchy(E,mm,extra);ll,ww=summarize(E,mm,pp,ii,bb,extra)
        outputs.append(write(HERE/'analysis'/name,ww))
    outputs.append(write(HERE/'analysis/MEMBER_BACKGROUND_ROBUSTNESS.csv',background_and_member_robustness(E)))
    outputs.append(write(HERE/'analysis/CONCRETE_BLOCK_DIVERSITY.csv',concrete_block_diversity(E)))
    outputs.append(write(HERE/'analysis/POSTHOC_Q_SOURCE_CHECKS.csv',matched_explanatory_checks(E,metrics)))
    common_time=E[E.recorded_time_single_source.eq(True)&E.all_scored.eq(True)].copy()
    if len(common_time):
        mm=[f for f in MAIN_METRICS if f in metrics]
        pp,ss,ii,bb=hierarchy(common_time,mm);ll,ww=summarize(common_time,mm,pp,ii,bb)
        outputs.append(write(HERE/'analysis/TIME_QUALITY_COMMON_SUPPORT.csv',ww))
    changes,nsummary=linked_n_changes(E)
    outputs.append(write(HERE/'analysis/LINKED_N_CHANGES.csv.gz',changes));outputs.append(write(HERE/'analysis/LINKED_N_SUMMARY.csv',nsummary))
    mchanges,msummary=linked_m_changes(E)
    if len(mchanges):
        outputs.append(write(HERE/'analysis/LINKED_M_CHANGES.csv.gz',mchanges));outputs.append(write(HERE/'analysis/LINKED_M_SUMMARY.csv',msummary))
    outputs.append(write(HERE/'analysis/MECHANISM_CANDIDATES.csv.gz',mechanism_candidates(E,changes)))
    save(HERE/'analysis/COMPLETION.json',dict(status='complete_for_available_event_table',events=len(E),
        event_source_sha256=sha(HERE/'EVENTS_COMPLETE.csv.gz'),analysis_script_sha256=sha(Path(__file__)),
        main_aggregation='events within exact D; D within feasible background-count vector; vectors within image; images within building; buildings equally',
        metric_denominators='every long metric row retains event/panel/image/building n; failed fusion stays in A/B/C failure denominators',
        replicated_n20_physical_events='linked_n n20 explicitly reuses main_n20 endpoints; groups never pooled as independent evidence',
        time='same provenance kind for all ABC; all n participants time known and sum positive; inventory recorded seconds only, not newly observed production duration',
        outputs=outputs))
    print(wide[['study_group','source_role','target_role','n','m','images_total','buildings_total','cross_B8L2_mean','net_B8L2_mean',
                'common_quality_within_abs_mean','common_quality_cross_abs_mean','C_failure_mean','net_recorded_time_pct_mean']].to_string(index=False))

if __name__=='__main__':main()
