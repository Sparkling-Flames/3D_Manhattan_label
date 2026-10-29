#!/usr/bin/env python3
"""Select the explicitly reported difficulty strata from full frozen summaries."""
from pathlib import Path
import pandas as pd
R=Path(__file__).resolve().parents[1]
p=R/'RAW_CLASS_DISTANCE_SUMMARY.csv'
if not p.exists():p=p.with_suffix('.csv.gz')
d=pd.read_csv(p)
methods=['DSTRUCT_K3','MSDGEOM_SCOPE_K3','OPPGEOM_K3','OPPSTRUCT_K3','RFUSE_GEOM_K2','TARGET_DSTRUCT_K3']
metrics=['geometry_pair_angle','geometry_bev_distance','turn_difference']
a=d[d.method.isin(methods)&d.metric.isin(metrics)&d.condition.eq('manual')&d.layer.eq('ordinary_manual')&d.support.eq('common45_known')&d.scope_summary.eq('ALL_TARGETS')&d.difficulty_summary.ne('ALL')]
a=a.rename(columns={'difficulty_summary':'difficulty','image_within':'within','image_cross':'cross','image_gap':'gap','images_cross_larger':'positive_images','images_no_gap':'zero_images'})
a=a[['method','subset','difficulty','metric','images','buildings','within','cross','gap','positive_images','zero_images']]
p=R/'RAW_MAIN_DIFFICULTY_TABLE.csv';q=p.with_name(p.name+'.writing');a.to_csv(q,index=False,encoding='utf-8-sig');q.replace(p)
print('saved',len(a),'difficulty rows')
