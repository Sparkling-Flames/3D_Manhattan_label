#!/usr/bin/env python3
from pathlib import Path
import pandas as pd,numpy as np,json
W=Path(__file__).resolve().parents[2];O=W/'stage06_cases'
cols=['event_id','pool_id','image','building','method','heldout_building','source_class','target_class','n','m','ABC_scored','background_id','background_target_n','background_source_n','B8L2_BA','B8L2_CA','B8L2_CB','record_time_CB_pct_source_matched','time_comparable_ABC','A_B8L2','B_B8L2','C_B8L2','A_nodes','B_nodes','C_nodes','A_S_bottom_deg','B_S_bottom_deg','C_S_bottom_deg','A_IoU3D100','B_IoU3D100','C_IoU3D100','A_omission','B_omission','C_omission','official_difficulty']
d=pd.read_csv(W/'analysis/focused/EVENT_METRICS.csv.gz',usecols=cols,low_memory=False)
d=d[d.method.eq('OPPJOINT_K4')&d.n.eq(12)&d.m.eq(6)]
r=pd.read_csv(W/'classification/CLASS_ROLES_COMPACT_ALL_LOBO.csv.gz')
for p in ['source','target']:
 z=r[['method','heldout_building','class_id','q_rank_asc']].rename(columns={'class_id':p+'_class','q_rank_asc':p+'_q_rank'})
 d=d.merge(z,on=['method','heldout_building',p+'_class'],how='left',validate='many_to_one')
d=d[d.source_q_rank.eq(1)&d.target_q_rank.eq(4)].copy();d.to_csv(O/'FOCUS_OPPJOINT_N12M6_ALL_EVENTS.csv.gz',index=False,compression='gzip')
sc=d[d.ABC_scored].copy();med=sc.B8L2_CB.median();timemed=sc.record_time_CB_pct_source_matched.median();print('all events',len(d),'scored',len(sc),'images',sc.image.nunique(),'medianCB',med,'medianTime',timemed)
z=sc[sc.B8L2_CB.between(3,15)&sc.B8L2_CA.gt(3)&sc.record_time_CB_pct_source_matched.between(2,35)].copy()
z['distance_to_median_CB']=(z.B8L2_CB-med).abs();z['illustration_rank']=z.distance_to_median_CB+(z.record_time_CB_pct_source_matched-11.3).abs()/8
z=z.sort_values('illustration_rank');z.to_csv(O/'FOCUS_OPPJOINT_N12M6_ILLUSTRATION_CANDIDATES.csv',index=False)
print(z.drop_duplicates('image').head(15)[['event_id','image','official_difficulty','A_B8L2','B_B8L2','C_B8L2','B8L2_BA','B8L2_CA','B8L2_CB','record_time_CB_pct_source_matched','A_nodes','B_nodes','C_nodes','illustration_rank']].round(3).to_string(index=False))
(O/'FOCUS_CASE_SELECTION_SCOPE.json').write_text(json.dumps({'method':'OPPJOINT_K4','q_role':'1_to_4','n':12,'m':6,'all_events':len(d),'scored_events':len(sc),'scored_images':sc.image.nunique(),'event_CB_median':med,'source_comparable_time_CB_median_pct':timemed,'illustration_filter':'CB 3..15;CA>3;source-comparable CB record time +2..35%;rank closeness to full scored-event median CB plus time-to+11.3/8','status':'illustration search after full focused results; not method adoption evidence'},ensure_ascii=False,indent=2))
