#!/usr/bin/env python3
"""Explain the actual RFUSE_GEOMQ K3 n20/m6 source/target roles and K2 contrast."""
from pathlib import Path
import json
import numpy as np
import pandas as pd
from summarize_exchange import write_csv

ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'analysis/reverse_confirm'

def main():
    support=pd.read_csv(ROOT/'analysis/condition_support/RFUSE_GEOMQ_K3_n20_m6_EXACT_SUPPORT_EVENTS.csv.gz')
    centers=pd.read_csv(ROOT/'reverse/REVERSE_CLASS_CENTERS_ALL_LOBO.csv.gz')
    c=centers[centers.method.eq('RFUSE_GEOMQ_K3')].copy()
    c['is_small']=c.people.eq(c.groupby('heldout_building').people.transform('min'))
    non=c[~c.is_small]
    minq=non.groupby('heldout_building').all_B8L2.min()
    maxq=non.groupby('heldout_building').all_B8L2.max()
    c['response_role']=['small_response_core' if small else ('noncore_lower_Q_response' if q==minq[b] else 'noncore_higher_Q_response')
                        for small,q,b in zip(c.is_small,c.all_B8L2,c.heldout_building)]
    fields=['members','people','response_role','all_B8L2','hard_B8L2','all_floor_turn5_n','hard_floor_turn5_n',
            'all_bottom_y_mean_px','all_top_y_mean_px','hard_bottom_y_mean_px','hard_top_y_mean_px',
            'all_log_floor_area','all_log_height_mean','hard_log_floor_area','hard_log_height_mean']
    details=support.copy()
    for side in ['source','target']:
        cc=c[['heldout_building','class_id']+fields].rename(columns={'heldout_building':'building',
          'class_id':side+'_class',**{k:side+'_response_'+k for k in fields}})
        details=details.merge(cc,on=['building',side+'_class'],how='left',validate='many_to_one')
    write_csv(OUT/'GEOMQ_K3_N20_M6_ROLE_EXACT_SUPPORT.csv.gz',details)
    rolefields=['phase','building','source_class','target_class']+[s+'_response_'+k for s in ['source','target'] for k in fields]
    rd=details[rolefields].drop_duplicates()
    write_csv(OUT/'GEOMQ_K3_N20_M6_FOLD_ROLE_CENTERS.csv',rd)
    pool=pd.read_csv(OUT/'REVERSE_BRANCH_POOL_SUMMARY.csv.gz')
    take=pool[pool.branch.eq('into_smallest_class')&pool.n.eq(20)&pool.m.eq(6)]
    k3=take[take.method.eq('RFUSE_GEOMQ_K3')];k2=take[take.method.eq('RFUSE_GEOMQ_K2')]
    common=k3.merge(k2,on=['phase','pool_id','building','image','difficulty','n','m'],suffixes=('_K3','_K2'),validate='one_to_one')
    metrics=['B8L2_within','B8L2_cross','B8L2_gap','B8L2_CA','B8L2_CB','D10_gap','D10_CB',
             'IoU3D100_CB','geometry_bev_distance_gap','geometry_pair_angle_gap','record_time_CB_pct',
             'C_failed','C_loss10_CB','C_failure_or_loss10_CB']
    for metric in metrics:
        common[metric+'_K3_minus_K2']=common[metric+'_K3']-common[metric+'_K2']
    write_csv(OUT/'GEOMQ_K3_VS_K2_N20_M6_COMMON_POOLS.csv',common)
    rows=[]
    for phase,g in common.groupby('phase'):
        for metric in metrics:
            m=g[[metric+'_K3',metric+'_K2',metric+'_K3_minus_K2']].notna().all(axis=1)
            t=g[m];delta=t[metric+'_K3_minus_K2'];bd=t.groupby('building')[metric+'_K3_minus_K2'].mean()
            rows.append(dict(phase=phase,metric=metric,common_images=len(t),common_buildings=t.building.nunique(),
                K3_image_equal=t[metric+'_K3'].mean(),K2_image_equal=t[metric+'_K2'].mean(),
                K3_minus_K2_image_equal=delta.mean(),positive_difference_images=int(delta.gt(0).sum()),
                positive_difference_buildings=int(bd.gt(0).sum()),
                comparison='same image/n/m and historical small-core role; actual sampled D/XYZ are different'))
    write_csv(OUT/'GEOMQ_K3_VS_K2_N20_M6_COMMON_SUMMARY.csv',pd.DataFrame(rows))
    # The member evidence describes actual target blocks, not the ALL seven-person list.
    meta=[]
    for phase,g in details.groupby('phase'):
        meta.append(dict(phase=phase,events=len(g),images=g.pool_id.nunique(),buildings=g.building.nunique(),
            actual_target_members='|'.join(sorted(set('|'.join(g.Z).split('|')))),
            actual_source_members='|'.join(sorted(set('|'.join(pd.concat([g.X,g.Y])).split('|')))),
            target_blocks=g.Z.nunique(),source_role_event_counts=json.dumps(g.source_response_response_role.value_counts().to_dict()),
            target_fold_sizes=json.dumps(g.target_response_people.value_counts().sort_index().to_dict()),
            each_image_entire_available_target=bool(g.target_capacity.eq(6).all()),
            D_target_always_zero=bool(g.background_target_n.eq(0).all())))
    write_csv(OUT/'GEOMQ_K3_N20_M6_MEMBER_ROLE_OVERVIEW.csv',pd.DataFrame(meta))
    # Compare the two noncore source roles without pretending the class id is stable.
    effects=['B8L2_within','B8L2_cross','B8L2_gap','B8L2_CA','B8L2_CB','D10_gap','D10_CB',
             'IoU3D100_CB','geometry_bev_distance_gap','geometry_pair_angle_gap','record_time_CB_pct','C_failed','C_loss10_CB']
    keep=['phase','method','n','m','pool_id','image','building','source_class','target_class','n_events']+effects
    dirs=pd.read_csv(OUT/'POOL_DIRECTION_SUMMARY.csv.gz',usecols=keep)
    dirs=dirs[dirs.method.eq('RFUSE_GEOMQ_K3')&dirs.n.eq(20)&dirs.m.eq(6)]
    src=c[['heldout_building','class_id','response_role']].rename(columns={'heldout_building':'building','class_id':'source_class','response_role':'source_role'})
    tgt=c[['heldout_building','class_id','is_small']].rename(columns={'heldout_building':'building','class_id':'target_class'})
    dirs=dirs.merge(src,on=['building','source_class'],validate='many_to_one').merge(tgt,on=['building','target_class'],validate='many_to_one')
    dirs=dirs[dirs.is_small]
    outrows=[]
    for (phase,role),g in dirs.groupby(['phase','source_role']):
        for metric in effects:
            v=g.groupby(['pool_id','building'])[metric].mean().reset_index();v=v[v[metric].notna()]
            bv=v.groupby('building')[metric].mean()
            outrows.append(dict(phase=phase,source_role=role,metric=metric,attempted_events=int(g.n_events.sum()),
                valid_images=len(v),valid_buildings=len(bv),image_equal=v[metric].mean(),building_equal=bv.mean(),
                positive_images=int(v[metric].gt(0).sum()),positive_buildings=int(bv.gt(0).sum())))
    write_csv(OUT/'GEOMQ_K3_N20_M6_BY_SOURCE_ROLE.csv',pd.DataFrame(outrows))
    print(pd.DataFrame(meta).to_json(orient='records',indent=2))

if __name__=='__main__':main()
