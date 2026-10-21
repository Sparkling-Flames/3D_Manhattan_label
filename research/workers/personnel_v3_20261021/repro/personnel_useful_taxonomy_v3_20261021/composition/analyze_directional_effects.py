"""Directed A->C effects, stratified only by pre-target historical behavior.

The numeric S/J cluster IDs need not retain a role across outer folds.  This
analysis therefore groups the actual incoming-minus-outgoing block history,
never a numerical class ID.  Quality, expression, stability and failure are
separate outcomes.  Unknown history is a recorded stratum, never zero.
"""
from __future__ import annotations
import argparse,collections,json,math,sys
import numpy as np
import pandas as pd
from multin_design import HERE,OLD,gs,write_csv,sha,h
from evaluate_matched_events import load_expression
from consolidate_deliverables import GzipCsv
sys.path.insert(0,str(OLD/'analysis'))
from analyze_global import COMPONENTS

AXES=['turn_history','short_history','redundancy_history','area_history','height_history']
EXP=['fusion_turn_n','fusion_short_turn_edges','fusion_redundancy_n']
BASE=['method_id','tier','condition','source_domain','design_scope']
METRICS=['cross_'+c for c in COMPONENTS]+['cross_'+c for c in EXP]+[
 'A_failure','C_failure','cross_failure_difference','cross_complete_to_failure',
 'cross_failure_to_complete','cross_loss_gt5','cross_loss_gt10',
 'cross_gain_gt5','cross_gain_gt10','cross_recorded_time_pct',
 'abs_Q_change_advantage','stable_advantage','net_B8L2','net_D10',
 'cross_positive_ref_node_recall','cross_negative_ref_node_recall',
 'cross_positive_ref_edge_recall','cross_negative_ref_edge_recall']
CORE=['cross_B8L2','cross_D10','cross_IoU3D100','cross_ref_node_recall_5',
 'cross_ref_edge_recall_5','cross_extension','cross_omission','cross_fusion_turn_n',
 'cross_fusion_short_turn_edges','cross_fusion_redundancy_n','cross_loss_gt10',
 'cross_failure_difference','cross_complete_to_failure','cross_recorded_time_pct',
 'abs_Q_change_advantage','stable_advantage']

def load(stage,condition=None):
    kind=stage.lower();cross=kind=='pure_cross';prefix=kind.upper()
    receipt=gs.read(HERE/'matched'/f'{prefix}_RESULT_RECEIPT.json')
    index=pd.read_csv(HERE/'matched'/f'{prefix}_RESULT_SHARDS.csv')
    if condition is not None:index=index[index.condition.eq(condition)]
    expression=load_expression();frames=[];needed=set();have=set()
    for entry in index.itertuples():
        path=HERE/entry.path;cols=pd.read_csv(path,nrows=0).columns
        metadata=['event_id','pool_id','image','building','condition','difficulty','method_id','tier',
          'panel_id','source_domain','common_background','n','m_AC','composition_turnover_AC',
          'class_seat_transfer','design_scope','within_parent_fine_change','team_A','team_C',
          'A_failure','C_failure','fold_selected_family','fold_coarse_k','fold_fine_k',
          'same_source_counts','source_and_historyQ5_matched','cross_recorded_time_pct',
          'recorded_time_pct','physical_pair_id']
        wanted=set(metadata+METRICS+['cross_'+f+'_change' for f in AXES])
        d=pd.read_csv(path,usecols=[c for c in cols if c in wanted],low_memory=False,
                      dtype={'event_id':str,'team_A':str,'team_C':str})
        if 'design_scope' not in d:
            d['design_scope']=np.where(d.within_parent_fine_change,'within_parent_fine_change','all_composition_changes')
        for field in ['same_source_counts','source_and_historyQ5_matched']:
            if field not in d:d[field]=np.nan
        if 'physical_pair_id' not in d:d['physical_pair_id']=d.team_A+'__to__'+d.team_C
        if 'class_seat_transfer' not in d:d['class_seat_transfer']=np.nan
        d['cross_failure_difference']=d.C_failure.astype(int)-d.A_failure.astype(int)
        d['cross_complete_to_failure']=(~d.A_failure)&d.C_failure
        d['cross_failure_to_complete']=d.A_failure&(~d.C_failure)
        for threshold in [5,10]:
            q=d.cross_B8L2
            d[f'cross_loss_gt{threshold}']=q.lt(-threshold).astype(float).where(q.notna())
            d[f'cross_gain_gt{threshold}']=q.gt(threshold).astype(float).where(q.notna())
        if 'cross_recorded_time_pct' not in d:d['cross_recorded_time_pct']=d.get('recorded_time_pct',np.nan)
        for target in ['node','edge']:
            r=d['cross_ref_'+target+'_recall_5']
            d['cross_positive_ref_'+target+'_recall']=r.gt(1e-10).astype(float).where(r.notna())
            d['cross_negative_ref_'+target+'_recall']=r.lt(-1e-10).astype(float).where(r.notna())
        for metric in EXP:
            values=[]
            for a,c in zip(d.team_A,d.team_C):
                needed.update([a,c])
                if a not in expression or c not in expression:values.append(np.nan);continue
                have.update([a,c]);av,cv=expression[a][metric],expression[c][metric]
                values.append(cv-av if av is not None and cv is not None else np.nan)
            d['cross_'+metric]=values
        for metric in METRICS:
            if metric not in d:d[metric]=np.nan
        d['stage']=stage;d['matched_same_class_arm']=not cross
        d['actual_m_band']=np.where(d.m_AC.ge(8),'m_ge_8','m_lt_8')
        d['class_seat_band']=np.where(d.composition_turnover_AC.eq(d.m_AC),'whole_class_seats','partial_class_seats')
        d['common_background_unit']=d.pool_id+'|n'+d.n.astype(str)+'|'+d.common_background.fillna('')
        frames.append(d)
    d=pd.concat(frames,ignore_index=True) if frames else pd.DataFrame()
    return d,receipt,needed-have

def run(stage,condition=None,allow_partial=False):
    d,receipt,missing=load(stage,condition)
    if not allow_partial and (receipt['status']!='complete' or missing):
        raise RuntimeError(('Wait for registered result/expression completion',stage,receipt['status'],len(missing)))
    if not len(d):raise RuntimeError('No event results available')
    partial=receipt['status']!='complete' or bool(missing)
    tag=stage.upper()+('_'+condition.upper() if condition else '')+('_CHECKPOINT' if partial else '')
    out=HERE/'direction';out.mkdir(exist_ok=True)
    event_path=out/f'{tag}_DIRECTION_EVENT_FEATURES.csv.gz'
    writer=GzipCsv(event_path,list(d.columns),key='event_id')
    for r in d.to_dict('records'):writer.add(gs.clean(r))
    event_receipt=writer.finish(set(d.event_id))
    summary_fields=['summary_id','stage','view']+BASE+['history_axis','history_direction',
      'difficulty','actual_m_band','class_seat_band','events','distinct_directed_pairs',
      'distinct_teams','panels','common_background_units','images','buildings',
      'history_known_events','n_min','n_max','m_min','m_max','metric','mean','valid_events',
      'valid_buildings','positive_buildings','negative_buildings','lo95','hi95']
    summary_writer=GzipCsv(out/f'{tag}_DIRECTED_COMPONENT_SUMMARY.csv.gz',summary_fields,key='summary_id')
    core_rows=[];building_rows=[];support_rows=[];summary_keys=set()
    views=[('overall',[]),('target_difficulty',['difficulty']),
           ('m_band_and_seats',['actual_m_band','class_seat_band']),
           ('difficulty_m_band_and_seats',['difficulty','actual_m_band','class_seat_band'])]
    for axis in AXES:
        field='cross_'+axis+'_change';x=d.copy()
        x['history_axis']=axis;x['history_change']=x[field]
        x['history_direction']=np.select([x[field].gt(1e-10),x[field].lt(-1e-10),x[field].abs().le(1e-10)],
                                         ['increase','decrease','unchanged'],default='unknown')
        for view,extra in views:
            keys=BASE+['history_axis','history_direction']+extra
            group=keys+['building','image','pool_id','panel_id']
            metrics=METRICS+['history_change','composition_turnover_AC','m_AC']
            # Each registered panel/background supplies a local comparison;
            # images and buildings, not duplicated event counts, get equal weight.
            p=x.groupby(group,dropna=False)[metrics].mean()
            b=p.groupby(level=keys+['building','image','pool_id'],dropna=False).mean()
            b=b.groupby(level=keys+['building','image'],dropna=False).mean()
            b=b.groupby(level=keys+['building'],dropna=False).mean().reset_index()
            bb=b.copy();bb['stage']=stage;bb['view']=view;building_rows.append(bb)
            for kk,gg in x.groupby(keys,dropna=False):
                meta=dict(zip(keys,kk));mask=np.ones(len(b),bool)
                for key,val in meta.items():mask &= b[key].eq(val).to_numpy()
                z=b[mask];den=dict(events=len(gg),distinct_directed_pairs=gg.physical_pair_id.nunique(),
                  distinct_teams=len(set(gg.team_A)|set(gg.team_C)),panels=gg.panel_id.nunique(),
                  common_background_units=gg.common_background_unit.nunique(),images=gg.image.nunique(),
                  buildings=gg.building.nunique(),history_known_events=int(gg[field].notna().sum()),
                  n_min=int(gg.n.min()),n_max=int(gg.n.max()),m_min=int(gg.m_AC.min()),m_max=int(gg.m_AC.max()))
                support_rows.append(dict(stage=stage,view=view,**meta,**den))
                for metric in metrics:
                    v=z[metric].dropna().to_numpy(float);lo=hi=None
                    if len(v)>=3 and metric in CORE:
                        rng=np.random.default_rng(2026102158);boot=v[rng.integers(len(v),size=(2000,len(v)))].mean(axis=1)
                        lo,hi=np.quantile(boot,[.025,.975])
                    row=dict(stage=stage,view=view,**meta,**den,metric=metric,
                      mean=float(v.mean()) if len(v) else None,valid_events=int(gg[metric].notna().sum()),
                      valid_buildings=len(v),positive_buildings=int((v>1e-10).sum()),
                      negative_buildings=int((v < -1e-10).sum()),lo95=lo,hi95=hi)
                    row['summary_id']=h(stage,view,meta,metric)[:24];summary_keys.add(row['summary_id']);summary_writer.add(gs.clean(row))
                    if metric in CORE:core_rows.append(row)
        summary_writer.flush()
        print(json.dumps(dict(stage=stage,axis=axis,events=len(d),summary_rows=len(summary_keys))),flush=True)
    summary_writer.finish(summary_keys)
    write_csv(out/f'{tag}_DIRECTED_CORE_SUMMARY.csv',pd.DataFrame(core_rows))
    write_csv(out/f'{tag}_DIRECTED_BUILDING_MEANS.csv.gz',pd.concat(building_rows,ignore_index=True))
    write_csv(out/f'{tag}_DIRECTED_SUPPORT.csv',pd.DataFrame(support_rows))
    result=dict(status='partial_checkpoint' if partial else 'complete',stage=stage,condition=condition,
       events=len(d),registered_stage_events=receipt['registered_events'],missing_expression_endpoints=len(missing),
       distinct_directed_pairs=d.physical_pair_id.nunique(),summary_rows=len(summary_keys),event_file=event_receipt,
       target_scores_used_to_define_history_direction=False,native_calls=0,
       numeric_cluster_ids_not_aligned_across_buildings=True,
       history_direction_tolerance=1e-10,unknown_history_retained=True,
       metric_sign_note='All cross_* changes are C minus A; higher extension/omission is more error, not better.',
       repeated_exploration_note='This is an explanatory stratification on previously explored data, not a new blinded validation.')
    gs.save(out/f'{tag}_DIRECTED_COMPLETION.json',result);print(json.dumps(result),flush=True)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('stage',choices=['panel','large','pure','pure_cross'])
    p.add_argument('--condition',choices=['manual','semi']);p.add_argument('--allow-partial',action='store_true')
    a=p.parse_args();run(a.stage,a.condition,a.allow_partial)
