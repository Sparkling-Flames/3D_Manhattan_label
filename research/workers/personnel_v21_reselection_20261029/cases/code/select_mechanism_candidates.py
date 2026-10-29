#!/usr/bin/env python3
"""Exploratory mechanism case inventory from all completed screen events.
Criteria select mechanisms and moderate/large effects; figures do not estimate effects.
"""
from pathlib import Path
import json,pandas as pd,numpy as np
W=Path(__file__).resolve().parents[2];O=W/'stage06_cases';O.mkdir(exist_ok=True)
base=['event_id','pool_id','image','building','condition','layer','difficulty','scope','method','source_class','target_class','n','m','background_target_n','background_source_n','ref_turn5','ref_H','ref_short_edges','ABC_scored','time_comparable_ABC','record_time_CB_pct_source_matched','record_time_CA_pct_source_matched','B8L2_BA','B8L2_CA','B8L2_CB','D10_CA','D10_CB','B8L2_within','B8L2_cross']
scalars=['B8L2','D10','nodes','fusion_turn_n','fusion_short_turn_edges','minimum_support','ref_node_recall_9','ref_edge_recall_9','S_bottom_deg','dir','matched_ref_top_abs_deg','matched_ref_bottom_abs_deg','matched_ref_horizontal_abs_deg','height_loss','omission','extension','failed','source_time_total_seconds','geometry_area_h2','height_mean_h']
cols=base+[arm+'_'+c for arm in 'ABC'for c in scalars]
d=pd.read_csv(W/'analysis/global_screen/EVENT_METRICS.csv.gz',usecols=cols,low_memory=False)
roles=pd.read_csv(W/'classification/CLASS_ROLES_COMPACT_ALL_LOBO.csv.gz',low_memory=False)
for prefix in ['source','target']:
 r=roles[['method','heldout_building','class_id','challenge_turn_rank_asc','area_rank_asc','q_rank_asc','k']].rename(columns={'heldout_building':'building','class_id':prefix+'_class',**{k:prefix+'_'+k for k in ['challenge_turn_rank_asc','area_rank_asc','q_rank_asc','k']}})
 d=d.merge(r,on=['method','building',prefix+'_class'],how='left',validate='many_to_one')
focus=((d.method.eq('TARGET_DSTRUCT_K3')&d.source_challenge_turn_rank_asc.eq(2)&d.target_challenge_turn_rank_asc.eq(3))|(d.method.eq('OPPGEOM_K3')&d.source_area_rank_asc.eq(2)&d.target_area_rank_asc.eq(3))|(d.method.eq('OPPJOINT_K4')&d.source_q_rank_asc.eq(1)&d.target_q_rank_asc.eq(4)))
f=d[focus].copy();f.to_csv(O/'FOCUS_DIRECTION_ALL_SCREEN_EVENTS.csv.gz',index=False,compression='gzip')
filters={
 'same_node_position_improvement':f.ABC_scored&f.A_nodes.eq(f.B_nodes)&f.A_nodes.eq(f.C_nodes)&f.B8L2_CA.between(4,22)&f.B8L2_CB.ge(4)&f.B8L2_BA.abs().le(8)&f.m.ge(4)&((f.A_matched_ref_top_abs_deg-f.C_matched_ref_top_abs_deg>.3)|(f.A_matched_ref_bottom_abs_deg-f.C_matched_ref_bottom_abs_deg>.3)),
 'structure_recovered':f.ABC_scored&f.method.eq('TARGET_DSTRUCT_K3')&f.ref_turn5.ge(6)&f.C_nodes.gt(f.A_nodes)&f.C_nodes.gt(f.B_nodes)&f.C_ref_node_recall_9.gt(f.A_ref_node_recall_9)&f.C_ref_edge_recall_9.gt(f.A_ref_edge_recall_9)&f.B8L2_CA.between(4,45)&f.B8L2_CB.gt(4)&f.m.ge(5),
 'major_quality_loss':f.ABC_scored&f.B8L2_CA.between(-28,-8)&f.B8L2_CB.lt(-5)&f.m.ge(4),
 'cross_failed':f.C_failed&~f.A_failed&~f.B_failed&f.m.ge(4),
 'within_class_large_change':f.ABC_scored&f.B8L2_BA.abs().between(12,28)&f.m.ge(5),
 'joint_n20m5':f.ABC_scored&f.method.eq('OPPJOINT_K4')&f.n.eq(20)&f.m.eq(5),
}
counts={};allc=[]
show=['event_id','method','image','n','m','A_B8L2','B_B8L2','C_B8L2','B8L2_CA','B8L2_CB','A_nodes','B_nodes','C_nodes','record_time_CB_pct_source_matched']
for name,mask in filters.items():
 g=f[mask].copy();counts[name]={'events':len(g),'images':g.image.nunique(),'buildings':g.building.nunique()}
 if len(g):
  target=g.B8L2_CB.median() if name!='joint_n20m5'else 5
  g['example_rank']=(g.B8L2_CB-target).abs();g['selection_pool']=name;allc.append(g)
  print('\n'+name+' '+str(counts[name]));print(g.sort_values('example_rank').drop_duplicates('image').head(12)[show].round(3).to_string(index=False))
pd.concat(allc,ignore_index=True).to_csv(O/'MECHANISM_CASE_CANDIDATES_ALL.csv.gz',index=False,compression='gzip')
# Exact nested backgrounds with identical X,Y,Z; compare actual C as well as C-A and C-B.
l=pd.read_csv(W/'experiment/global_screen_size_paths/EXACT_NESTED_SIZE_LINKS.csv.gz')
x=l[l.lower_event_id.isin(f.event_id)&l.higher_event_id.isin(f.event_id)].copy()
v=f.set_index('event_id');use=['B8L2','nodes','minimum_support','ref_node_recall_9']
for level in ['lower','higher']:
 for arm in 'ABC':
  for q in use:x[level+'_'+arm+'_'+q]=x[level+'_event_id'].map(v[arm+'_'+q])
 for q in ['B8L2_CA','B8L2_CB']:x[level+'_'+q]=x[level+'_event_id'].map(v[q])
x['C_quality_change']=x.higher_C_B8L2-x.lower_C_B8L2
x['B_quality_change']=x.higher_B_B8L2-x.lower_B_B8L2
x['A_quality_change']=x.higher_A_B8L2-x.lower_A_B8L2
x['net_CB_change']=x.higher_B8L2_CB-x.lower_B8L2_CB
x['case_candidate']=x.lower_B8L2_CB.gt(4)&x.higher_B8L2_CB.lt(-2)&x.C_quality_change.lt(-5)&x.higher_C_nodes.lt(x.lower_C_nodes)&x.n_lower.ge(8)&x.m.ge(4)
x.to_csv(O/'NESTED_SIZE_PATH_CANDIDATES_ALL.csv.gz',index=False,compression='gzip')
z=x[x.case_candidate].copy();counts['nested_size_reversal']={'links':len(z),'images':z.image.nunique(),'buildings':z.building.nunique()}
print('\nnested_size_reversal',counts['nested_size_reversal']);print(z.sort_values('C_quality_change',ascending=False).drop_duplicates('image').head(14)[['lower_event_id','higher_event_id','image','method','n_lower','n_higher','m','lower_C_B8L2','higher_C_B8L2','lower_B8L2_CB','higher_B8L2_CB','lower_C_nodes','higher_C_nodes']].round(3).to_string(index=False))
(O/'CASE_SELECTION_SEARCH_SCOPE.json').write_text(json.dumps({'source_events':len(d),'focused_events':len(f),'criteria':counts,'selection_stage':'exploratory mechanism illustrations after global screen; not independent effect validation','all_labels_frozen_before_event_results':True,'all_signs_and_failures_retained_in_full_screen':True},ensure_ascii=False,indent=2))
