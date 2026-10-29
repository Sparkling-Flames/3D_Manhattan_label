"""Image-balanced AC effects from saved event metrics; no fusion or scoring.

Main A/B equal-size estimates use neutral_members_0 only. Additional backgrounds,
fixed-A paths and complete coalitions are analyzed in separate sensitivity code.
Every scalar keeps its own valid denominator. Missing scores are never zero.
"""
from __future__ import annotations
import argparse, csv, gzip, hashlib, json, math
from pathlib import Path
import numpy as np
import pandas as pd

BASE_METRICS = ['B8L2','D10','IoU3D100','iou_2d','S_bottom_deg','dir','Hmean','Hcenter',
 'omission','extension','fusion_turn_n','fusion_short_turn_edges','fusion_redundancy_n','nodes',
 'geometry_area_h2','height_mean_h','height_min_h','height_max_h','centroid_x_h','centroid_z_h',
 'ref_node_recall_5','ref_node_recall_9','ref_edge_recall_5','ref_edge_recall_9',
 'reference_node_shortfall','reference_node_excess','matched_ref_top_abs_deg',
 'matched_ref_bottom_abs_deg','matched_ref_horizontal_abs_deg','boundary_loss','direction_loss',
 'global_height_loss','local_height_loss','height_loss','floor_WQ','WQ','WQ_no_D','WQ_no_B','WQ_no_H',
 'diag_wall_coverage_03','diag_wall_coverage_05','diag_corner_recall_05']
DELTA_METRICS = [x+'_CA' for x in BASE_METRICS] + [
 'record_time_CA_seconds_source_matched','record_time_CA_pct_source_matched',
 'record_time_CA_seconds_single_source','record_time_CA_pct_single_source',
 'record_time_per_member_CA_seconds_single_source','record_time_per_member_CA_pct_single_source',
 'geometry_area_h2_pct_CA','geometry_area_h2_log_ratio_CA','height_mean_h_pct_CA',
 'geometry_bev_distance_AC','geometry_centroid_distance_AC','geometry_log_area_distance_AC',
 'geometry_pair_angle_AC','geometry_top_angle_AC','geometry_bottom_angle_AC','geometry_unmatched_pairs_AC',
 'geometry_bev_distance_AC_complete_outputs_only','geometry_centroid_distance_AC_complete_outputs_only',
 'Q_missing_risk_change_CA','fusion_structural_failure_risk_change_CA',
 'output_invalid_geometry_risk_change_CA','fusion_failure_observed_risk_change_CA',
 'output_not_complete_risk_change_CA']
ARM_METRICS = [a+'_'+m for a in ['A','C'] for m in [
 'B8L2','D10','nodes','fusion_turn_n','fusion_short_turn_edges','ref_node_recall_5','ref_edge_recall_5',
 'Q_missing','fusion_failure_observed','output_not_complete','insufficient_nodes','connection_failure',
 'output_invalid_geometry','measurement_exception','reference_floor_only','other_Q_missing']]
META = ['event_id','physical_pair_id','method','pool_id','image','building','condition','layer','scope',
 'source_class','target_class','source_role_rank','target_role_rank','role_axis','n','m','n_A','n_C',
 'm_X','m_Z','D_n','whole_source','whole_target','source_class_available_n','target_class_available_n',
 'source_parent_class','target_parent_class','official_difficulty','structural_condition','ref_turn5',
 'A_team_key','C_team_key','design_family']
LINK_COLS = ['event_id','pool_id','design_family','background_profile','at_pool_frontier','zero_background',
             'all_other_classes_in_D','background_n']
GROUP = ['analysis_view','scope','condition','layer','method','role_direction','n_condition','m_condition']


def save(df, path):
    path = Path(path); path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + '.partial')
    if str(path).endswith('.gz'):
        with gzip.open(tmp,'wt',encoding='utf-8-sig',newline='',compresslevel=5) as f:
            df.to_csv(f,index=False)
    else:
        df.to_csv(tmp,index=False,encoding='utf-8-sig')
    tmp.replace(path)


def flag(x):
    return x.astype(str).str.lower().isin(['true','1','1.0'])


def stat_rows(frame, metrics):
    keys = GROUP + ['pool_id','image','building']
    frame=frame.reset_index(drop=True)
    gb=frame.groupby(keys,dropna=False,sort=False)
    agg={'registered_pairs':('event_id','nunique'),
         'source_classes':('source_class',lambda x:'|'.join(sorted(set(x.fillna('').astype(str))))),
         'target_classes':('target_class',lambda x:'|'.join(sorted(set(x.fillna('').astype(str)))))}
    for field in ['n_A','n_C','m_X','m_Z','D_n']:
        for op in ['min','max']:agg['actual_'+field+'_'+op]=(field,op)
    meta=gb.agg(**agg)
    numeric=frame[metrics].apply(pd.to_numeric,errors='coerce').replace([np.inf,-np.inf],np.nan)
    grouping=[frame[k] for k in keys]
    ng=numeric.groupby(grouping,dropna=False,sort=False)
    pieces=[meta,ng.count().rename(columns=lambda c:c+'__valid_pairs'),ng.mean().rename(columns=lambda c:c+'__mean')]
    delta=[m for m in metrics if m in DELTA_METRICS]
    for vals,suffix in [(numeric[delta].abs(),'__mean_absolute'),
                        (numeric[delta].gt(1e-9).astype(float).where(numeric[delta].notna()),'__event_positive_fraction')]:
        pieces.append(vals.groupby(grouping,dropna=False,sort=False).mean().rename(columns=lambda c:c+suffix))
    qfields=[m for m in ['B8L2_CA','D10_CA'] if m in metrics]
    if qfields:
        qg=numeric[qfields].groupby(grouping,dropna=False,sort=False)
        for q,label in [(.1,'p10'),(.5,'p50'),(.9,'p90')]:
            pieces.append(qg.quantile(q).rename(columns=lambda c:c+'__event_'+label))
        for vals,label in [(numeric[qfields].lt(-10),'loss10'),(numeric[qfields].gt(10),'gain10')]:
            vals=vals.astype(float).where(numeric[qfields].notna())
            pieces.append(vals.groupby(grouping,dropna=False,sort=False).mean().rename(columns=lambda c:c+'__event_'+label+'_fraction'))
    return pd.concat(pieces,axis=1).reset_index()


def views(d, links):
    result = []
    families = ['A_equal_AC','B_equal_whole_class','F_strict_common_n_bridge',
                'S_equal_whole_class','B_unequal_whole_classes']
    for family in families:
        lg = links[links.design_family.eq(family)].copy()
        if lg.empty: continue
        if family in ['A_equal_AC','B_equal_whole_class','S_equal_whole_class','F_strict_common_n_bridge']:
            # Bridge may explicitly use a neutral path without naming the policy.
            neutral = lg.background_profile.fillna('neutral_members_0').eq('neutral_members_0')
            lg = lg[neutral]
        if lg.empty: continue
        lg = lg.drop_duplicates('event_id')
        x = d.drop(columns=['design_family'], errors='ignore').merge(lg.drop(columns=['pool_id','design_family']),on='event_id',how='inner',validate='one_to_one')
        if x.empty: continue
        if family == 'B_unequal_whole_classes':
            x['analysis_view'] = np.where(x.D_n.eq(0),'whole_unequal_no_background',
                np.where(flag(x.all_other_classes_in_D),'whole_unequal_all_external_background','whole_unequal_partial_external_background'))
            x['n_condition'] = 'unequal_actual_sizes'; x['m_condition'] = 'both_complete_classes'
            result.append(x); continue
        labels = {'A_equal_AC':'A_fixed_n','B_equal_whole_class':'whole_equal_fixed_n',
                  'F_strict_common_n_bridge':'strict_common_n_AC','S_equal_whole_class':'Semi_whole_equal_fixed_n'}
        x['analysis_view'] = labels[family]
        x['n_condition'] = x.n.astype(int).astype(str); x['m_condition'] = x.m.astype(int).astype(str)
        # Pure-class teams retain their exact n/m, and a distinct named view.
        x.loc[x.D_n.eq(0),'analysis_view'] += '_pure_class'
        result.append(x)
        if 'at_pool_frontier' in x:
            frontier = x[flag(x.at_pool_frontier)].copy()
            if len(frontier):
                frontier['analysis_view'] = labels[family].replace('_fixed_n','_pool_frontier')
                frontier.loc[frontier.D_n.eq(0),'analysis_view'] += '_pure_class'
                frontier['n_condition'] = 'N_minus_m'
                if family != 'A_equal_AC': frontier['m_condition'] = 'whole_class_actual_m'
                result.append(frontier)
        if family in ['B_equal_whole_class','S_equal_whole_class']:
            variable = x.copy(); variable['m_condition'] = 'whole_class_actual_m'
            variable['analysis_view'] = labels[family]+'_all_m'
            variable.loc[variable.D_n.eq(0),'analysis_view'] += '_pure_class'
            result.append(variable)
    return pd.concat(result, ignore_index=True) if result else pd.DataFrame()


def aggregate_reference(pool, out):
    mean_cols = [c for c in pool if c.endswith('__mean') or c.endswith('__mean_absolute') or '__event_' in c]
    imagekeys = GROUP + ['image','building']
    image = pool.groupby(imagekeys,dropna=False,sort=False)[mean_cols].mean().reset_index()
    counts = pool.groupby(imagekeys,dropna=False,sort=False).agg(target_pools=('pool_id','nunique'),registered_pairs=('registered_pairs','sum')).reset_index()
    image = image.merge(counts,on=imagekeys,validate='one_to_one')
    save(image,out/'IMAGE_CONDITION_EFFECTS.csv.gz')
    building = image.groupby(GROUP+['building'],dropna=False,sort=False)[mean_cols].mean().reset_index()
    save(building,out/'BUILDING_CONDITION_EFFECTS.csv.gz')
    # One metric per row makes each denominator explicit and traceable.
    pgrp = {k:d for k,d in pool.groupby(GROUP,dropna=False,sort=False)}
    bgrp = {k:d for k,d in building.groupby(GROUP,dropna=False,sort=False)}
    rows=[]
    metrics=[c[:-6] for c in mean_cols if c.endswith('__mean')]
    for key,d in image.groupby(GROUP,dropna=False,sort=False):
        pp, bb = pgrp[key], bgrp[key]
        base=dict(zip(GROUP,key)); base.update(registered_images=d.image.nunique(),registered_pools=pp.pool_id.nunique(),
          registered_buildings=d.building.nunique(),registered_pairs=int(pp.registered_pairs.sum()),
          actual_n_A_min=pp.actual_n_A_min.min(),actual_n_A_max=pp.actual_n_A_max.max(),
          actual_n_C_min=pp.actual_n_C_min.min(),actual_n_C_max=pp.actual_n_C_max.max(),
          actual_m_X_min=pp.actual_m_X_min.min(),actual_m_X_max=pp.actual_m_X_max.max())
        for metric in metrics:
            col=metric+'__mean';x=d[col].dropna();valid=d.loc[d[col].notna()];xb=bb[col].dropna()
            r=dict(base,metric=metric,valid_pairs=int(pp[metric+'__valid_pairs'].sum()),
              valid_pools=int(pp[metric+'__valid_pairs'].gt(0).sum()),valid_images=len(x),
              valid_buildings=valid.building.nunique(),image_mean=float(x.mean()) if len(x) else np.nan,
              image_median=float(x.median()) if len(x) else np.nan,image_p10=float(x.quantile(.1)) if len(x) else np.nan,
              image_p90=float(x.quantile(.9)) if len(x) else np.nan,image_min=float(x.min()) if len(x) else np.nan,
              image_max=float(x.max()) if len(x) else np.nan,positive_images=int((x>1e-9).sum()),
              negative_images=int((x<-1e-9).sum()),tied_images=int((x.abs()<=1e-9).sum()),
              positive_image_fraction=float((x>1e-9).mean()) if len(x) else np.nan,
              building_balanced_mean=float(xb.mean()) if len(xb) else np.nan,
              positive_buildings=int((xb>1e-9).sum()),negative_buildings=int((xb<-1e-9).sum()))
            for suffix in ['mean_absolute','event_positive_fraction','event_p10','event_p50','event_p90','event_loss10_fraction','event_gain10_fraction']:
                c=metric+'__'+suffix
                if c in d:r['image_balanced_'+suffix]=float(d[c].mean()) if d[c].notna().any() else np.nan
            rows.append(r)
    summary=pd.DataFrame(rows);save(summary,out/'CONDITION_METRIC_SUMMARY.csv.gz')
    q=summary[summary.metric.isin(['B8L2_CA','D10_CA','fusion_turn_n_CA','fusion_short_turn_edges_CA',
       'ref_node_recall_5_CA','ref_edge_recall_5_CA','geometry_bev_distance_AC','geometry_centroid_distance_AC',
       'geometry_area_h2_pct_CA','height_mean_h_pct_CA','record_time_CA_pct_source_matched',
       'fusion_failure_observed_risk_change_CA','Q_missing_risk_change_CA'])]
    save(q,out/'KEY_OUTCOME_SUMMARY.csv.gz')
    headline=q[q.scope.eq('primary') & q.condition.eq('manual') & q.analysis_view.isin(['A_fixed_n','A_pool_frontier','whole_equal_fixed_n_all_m','whole_equal_pool_frontier']) &
        ((q.n_condition.isin(['14','16','18','20','22','N_minus_m']) & q.m_condition.isin(['7','8','9','10','11','12','whole_class_actual_m'])))]
    save(headline,out/'HEADLINE_CONDITIONS.csv')
    return {'pool_condition_rows':len(pool),'image_condition_rows':len(image),'building_condition_rows':len(building),'condition_metric_rows':len(summary)}


def aggregate(pool, out):
    """Vectorized form of the literal image/building-balanced definitions above."""
    valuecols=[c for c in pool if c.endswith('__mean') or c.endswith('__mean_absolute') or '__event_' in c]
    metrics=[c[:-6] for c in valuecols if c.endswith('__mean')]
    meanmap={m+'__mean':m for m in metrics}
    imagekeys=GROUP+['image','building']
    image=pool.groupby(imagekeys,dropna=False,sort=False)[valuecols].mean().reset_index()
    counts=pool.groupby(imagekeys,dropna=False,sort=False).agg(target_pools=('pool_id','nunique'),registered_pairs=('registered_pairs','sum')).reset_index()
    image=image.merge(counts,on=imagekeys,validate='one_to_one')
    save(image,out/'IMAGE_CONDITION_EFFECTS.csv.gz')
    building=image.groupby(GROUP+['building'],dropna=False,sort=False)[valuecols].mean().reset_index()
    save(building,out/'BUILDING_CONDITION_EFFECTS.csv.gz')
    im=image[list(meanmap)].rename(columns=meanmap); bm=building[list(meanmap)].rename(columns=meanmap)
    ik=[image[k] for k in GROUP];bk=[building[k] for k in GROUP];pk=[pool[k] for k in GROUP]
    ig=im.groupby(ik,dropna=False,sort=False);bg=bm.groupby(bk,dropna=False,sort=False)
    pieces={'valid_images':ig.count(),'image_mean':ig.mean(),'image_median':ig.median(),
            'image_p10':ig.quantile(.1),'image_p90':ig.quantile(.9),'image_min':ig.min(),'image_max':ig.max(),
            'valid_buildings':bg.count(),'building_balanced_mean':bg.mean()}
    for label,vals in [('positive_images',im.gt(1e-9)),('negative_images',im.lt(-1e-9)),('tied_images',im.abs().le(1e-9))]:
        pieces[label]=vals.astype(int).groupby(ik,dropna=False,sort=False).sum()
    pieces['positive_image_fraction']=pieces['positive_images']/pieces['valid_images'].replace(0,np.nan)
    for label,vals in [('positive_buildings',bm.gt(1e-9)),('negative_buildings',bm.lt(-1e-9))]:
        pieces[label]=vals.astype(int).groupby(bk,dropna=False,sort=False).sum()
    pm=pool[[m+'__valid_pairs' for m in metrics]].rename(columns=lambda c:c[:-13])
    # len('__valid_pairs') is 13; all per-metric denominators retain their own rows.
    assert list(pm)==metrics
    pieces['valid_pairs']=pm.groupby(pk,dropna=False,sort=False).sum()
    pieces['valid_pools']=pm.gt(0).astype(int).groupby(pk,dropna=False,sort=False).sum()
    for suffix in ['mean_absolute','event_positive_fraction','event_p10','event_p50','event_p90','event_loss10_fraction','event_gain10_fraction']:
        cols={m+'__'+suffix:m for m in metrics if m+'__'+suffix in image}
        if cols:pieces['image_balanced_'+suffix]=image[list(cols)].rename(columns=cols).groupby(ik,dropna=False,sort=False).mean()
    wide=pd.concat(pieces,axis=1)
    wide.columns.names=['statistic','metric']
    summary=wide.stack(level='metric',future_stack=True).reset_index()
    meta=pool.groupby(GROUP,dropna=False,sort=False).agg(registered_pools=('pool_id','nunique'),
      registered_pairs=('registered_pairs','sum'),actual_n_A_min=('actual_n_A_min','min'),actual_n_A_max=('actual_n_A_max','max'),
      actual_n_C_min=('actual_n_C_min','min'),actual_n_C_max=('actual_n_C_max','max'),
      actual_m_X_min=('actual_m_X_min','min'),actual_m_X_max=('actual_m_X_max','max')).reset_index()
    imeta=image.groupby(GROUP,dropna=False,sort=False).agg(registered_images=('image','nunique'),registered_buildings=('building','nunique')).reset_index()
    meta=meta.merge(imeta,on=GROUP,validate='one_to_one')
    summary=summary.merge(meta,on=GROUP,validate='many_to_one')
    save(summary,out/'CONDITION_METRIC_SUMMARY.csv.gz')
    q=summary[summary.metric.isin(['B8L2_CA','D10_CA','fusion_turn_n_CA','fusion_short_turn_edges_CA',
       'ref_node_recall_5_CA','ref_edge_recall_5_CA','geometry_bev_distance_AC','geometry_centroid_distance_AC',
       'geometry_area_h2_pct_CA','height_mean_h_pct_CA','record_time_CA_pct_source_matched',
       'fusion_failure_observed_risk_change_CA','Q_missing_risk_change_CA'])]
    save(q,out/'KEY_OUTCOME_SUMMARY.csv.gz')
    headline=q[q.scope.eq('primary') & q.condition.eq('manual') & q.analysis_view.isin(['A_fixed_n','A_pool_frontier','whole_equal_fixed_n_all_m','whole_equal_pool_frontier']) &
        (q.n_condition.isin(['14','16','18','20','22','N_minus_m']) & q.m_condition.isin(['3','4','7','8','9','10','11','12','whole_class_actual_m']))]
    save(headline,out/'HEADLINE_CONDITIONS.csv')
    return {'pool_condition_rows':len(pool),'image_condition_rows':len(image),'building_condition_rows':len(building),'condition_metric_rows':len(summary)}


def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--metrics',required=True);ap.add_argument('--links',required=True);ap.add_argument('--out',required=True)
    a=ap.parse_args();out=Path(a.out);out.mkdir(parents=True,exist_ok=True)
    links=pd.read_csv(a.links,usecols=lambda c:c in LINK_COLS,low_memory=False)
    for c in LINK_COLS:
        if c not in links:links[c]=np.nan
    links_by_pool={k:v for k,v in links.groupby('pool_id',sort=False)}
    files=sorted((Path(a.metrics)/'metric_shards').glob('*.csv.gz'))
    frames=[];done=[]
    for path in files:
        pid=path.name[:-7]
        if pid not in links_by_pool:continue
        dest=out/'pool_shards'/path.name
        if dest.exists():
            g=pd.read_csv(dest,low_memory=False);frames.append(g);done.append(pid);continue
        d=pd.read_csv(path,usecols=lambda c:c in set(META+DELTA_METRICS+ARM_METRICS),low_memory=False)
        for c in ['source_role_rank','target_role_rank']:
            d[c]=pd.to_numeric(d[c],errors='coerce')
        def direction(r):
            if pd.notna(r.source_role_rank) and pd.notna(r.target_role_rank):return str(int(r.source_role_rank))+'->'+str(int(r.target_role_rank))
            return str(r.source_class)+'->'+str(r.target_class)
        d['role_direction']=d.apply(direction,axis=1)
        selected=views(d,links_by_pool[pid])
        if selected.empty:continue
        metrics=[c for c in DELTA_METRICS+ARM_METRICS if c in selected]
        g=stat_rows(selected,metrics);save(g,dest);frames.append(g);done.append(pid)
        print(json.dumps({'pool':pid,'main_effect_conditions':len(g)}),flush=True)
    if not frames:raise RuntimeError('No completed metric shards available')
    pool=pd.concat(frames,ignore_index=True);save(pool,out/'POOL_CONDITION_EFFECTS.csv.gz')
    receipt=aggregate(pool,out)
    receipt.update(complete_metric_pools=len(files),summarized_pools=len(done),new_fusions=0,new_scores=0,
      registered_metric_pool_count=links.pool_id.nunique(),complete=len(files)==links.pool_id.nunique(),
      main_A_background='neutral_members_0',weights='within-pool sampled blocks; targets within image; equal image and separate equal building',
      missing_Q_imputed=False,method_event_duplicates_not_independent=True,
      geometry_BEV_unit='dimensionless 1-IoU',centroid_unit='h',angles_unit='degree')
    (out/'SUMMARY_RECEIPT.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(receipt,ensure_ascii=False),flush=True)


if __name__=='__main__':main()
