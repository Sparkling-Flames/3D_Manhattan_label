"""Same exact crews/references in the two observed task conditions.

Condition interaction is descriptive: assignment/order were not randomized,
and these are not initial-to-final geometry corrections.
"""
from __future__ import annotations
import argparse, collections, json
from pathlib import Path
import numpy as np
import pandas as pd
from design_history_panel import read, write
from summarize_blocks import csv_write

KEYS=['within_joint_stable_strict','within_joint_stable_main','within_joint_stable_wide',
      'cross_joint_stable_strict','cross_joint_stable_main','cross_joint_stable_wide',
      'within_geometry_noQ_main','cross_geometry_noQ_main',
      'within_geometry_shape_main','cross_geometry_shape_main',
      'gap_joint_stable_main','gap_geometry_noQ_main','gap_geometry_shape_main',
      'within_abs_B8L2_change','cross_abs_B8L2_change',
      'within_floor_jaccard_difference','cross_floor_jaccard_difference',
      'within_bottom_y_absdiff_deg_p95','cross_bottom_y_absdiff_deg_p95',
      'within_top_y_absdiff_deg_p95','cross_top_y_absdiff_deg_p95',
      'within_Q_drop_gt5','cross_Q_drop_gt5','net_B8L2_change','net_D10_change',
      'B_B8L2','C_B8L2','B_complete','C_complete','net_complete_lost','net_complete_restored',
      'cross_over_within_source_block_time','cross_over_within_target_block_time']

def aggregate(frame,cols):
    metrics=[c for c in frame if c.startswith(('manual_','semi_','interaction_')) and pd.api.types.is_numeric_dtype(frame[c])]
    byimg=frame.groupby(list(dict.fromkeys(cols+['image','building'])),dropna=False)[metrics].mean().reset_index()
    byb=byimg.groupby(list(dict.fromkeys(cols+['building'])),dropna=False)[metrics].mean().reset_index()
    result=byb.groupby(cols,dropna=False)[metrics].mean().reset_index()
    support=frame.groupby(cols,dropna=False).agg(links=('condition_link_id','size'),images=('image','nunique'),buildings=('building','nunique')).reset_index()
    result=result.merge(support,on=cols)
    for k in ['manual_net_B8L2_change','semi_net_B8L2_change','interaction_net_B8L2_change','manual_cross_over_within_source_block_time','semi_cross_over_within_source_block_time','manual_cross_over_within_target_block_time','semi_cross_over_within_target_block_time']:
        av=frame.groupby(cols,dropna=False)[k].count().rename(k+'_available_n').reset_index()
        result=result.merge(av,on=cols)
    return result

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--requests',type=Path,required=True)
    ap.add_argument('--metrics',type=Path,required=True);ap.add_argument('--out',type=Path,required=True)
    a=ap.parse_args();a.out.mkdir(parents=True,exist_ok=True)
    request=read(a.requests);events={e['event_id']:e for e in request['events']}
    metrics=pd.read_csv(a.metrics).set_index('event_id')
    rows=[]
    for link in request['links']:
        row=dict(link);man=events[link['manual_event_id']];sem=events[link['semi_event_id']]
        for arm in 'ABC':assert man[arm+'_workers']==sem[arm+'_workers']
        assert man['reference_id']==sem['reference_id']==link['reference_id']
        assert man['n']==sem['n']==link['n'] and man['m']==sem['m']==link['m']
        for cond in ['manual','semi']:
            event=metrics.loc[link[cond+'_event_id']]
            for key in KEYS:row[cond+'_'+key]=event[key]
        for key in KEYS:
            x,y=row['manual_'+key],row['semi_'+key]
            row['interaction_'+key]=float(y)-float(x) if pd.notna(x) and pd.notna(y) else np.nan
        row['n_band']='03-05' if link['n']<=5 else '06-10' if link['n']<=10 else '11-17' if link['n']<=17 else '18plus'
        rows.append(row)
    frame=pd.DataFrame(rows);csv_write(frame,a.out/'linked_condition_effects.csv.gz')
    primary=frame[(frame.n>=3)&(frame.m>=2)]
    base=['phase','method_id','domain','origin','direction']
    for name,cols in [('direction',base),('n_band',base+['n_band']),('n_m',base+['n','m']),('building',base+['building'])]:
        csv_write(aggregate(primary,cols),a.out/(name+'_summary.csv'))
    csv_write(frame[frame.n==2],a.out/'n2_deferred.csv')
    write(a.out/'RECEIPT.json',dict(linked_comparisons=len(frame),primary_nge3_mge2=len(primary),
        images=primary.image.nunique(),buildings=primary.building.nunique(),
        exact_crew_and_reference_assertions='All passed',
        workers=len({w for e in request['events'] for arm in 'ABC' for w in e[arm+'_workers']}),
        interpretation='Observed Manual/Semi interaction of fixed personnel rules with identical crews, core, n, m and reference. Not randomized condition assignment, not causal treatment effect, not net correction of missing initial geometry.',
        weighting='Links within image, images within building, equal buildings. All unavailable metrics remain missing.'))

if __name__=='__main__':main()
