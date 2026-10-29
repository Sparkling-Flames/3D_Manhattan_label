"""Comparable all-candidate summaries, without treating class IDs as cross-fold roles.
Groups outcomes first within target, then image, then building. All feasible
conditions remain in files, including negative/flat effects and every failure.
"""
from __future__ import annotations
import argparse,gzip,json,os
from pathlib import Path
import numpy as np
import pandas as pd
from measure_registered_events import save,jsave
CORE=['B8L2_within','B8L2_cross','B8L2_gap','B8L2_AC_absolute','B8L2_AC_gap','B8L2_BA','B8L2_CA','B8L2_CB',
'D10_within','D10_cross','D10_gap','D10_CA','D10_CB','IoU3D100_CA','IoU3D100_CB','iou_2d_CA','iou_2d_CB',
'S_bottom_deg_CA','S_bottom_deg_CB','matched_ref_top_abs_deg_CA','matched_ref_top_abs_deg_CB',
'matched_ref_bottom_abs_deg_CA','matched_ref_bottom_abs_deg_CB','matched_ref_horizontal_abs_deg_CA','matched_ref_horizontal_abs_deg_CB',
'boundary_loss_CA','boundary_loss_CB','direction_loss_CA','direction_loss_CB','height_loss_CA','height_loss_CB',
'height_mean_h_CA','height_mean_h_CB','geometry_area_h2_CA','geometry_area_h2_CB','omission_CA','omission_CB','extension_CA','extension_CB',
'fusion_turn_n_CA','fusion_turn_n_CB','fusion_turn_n_gap','fusion_short_turn_edges_CA','fusion_short_turn_edges_CB','fusion_redundancy_n_CA',
'ref_node_recall_9_CA','ref_node_recall_9_CB','reference_node_shortfall_CA','reference_node_shortfall_CB',
'geometry_bev_distance_within','geometry_bev_distance_cross','geometry_bev_distance_gap',
'geometry_pair_angle_within','geometry_pair_angle_cross','geometry_pair_angle_gap','geometry_centroid_distance_gap',
'record_time_CA_pct_source_matched','record_time_CB_pct_source_matched','record_time_CA_pct_single_source','record_time_CB_pct_single_source',
'Q_improved_CA','Q_improved_CB','Q_loss10_CA','Q_loss10_CB','failure_or_loss10_CA','failure_or_loss10_CB',
'A_failed','B_failed','C_failed','A_incomplete','B_incomplete','C_incomplete','ABC_scored','time_comparable_ABC']
PRINCIPAL=['B8L2_gap','B8L2_CA','B8L2_CB','D10_gap','geometry_bev_distance_gap','fusion_turn_n_CA','record_time_CB_pct_source_matched']

def add_roles(ev,roles):
 keys=['method','heldout_building','class_id'];ranks=['turn_rank_asc','size_rank_desc','q_rank_asc','time_rank_asc','area_rank_asc','height_rank_asc','redundancy_rank_asc','challenge_turn_rank_asc','response_turn_rank_asc','response_q_rank_asc']
 cols=keys+['k','workers','members','semantic_training_role']+[c for c in ranks if c in roles]+[c for c in ['m_all_turn_n','m_all_B8L2','m_all_log_time','m_all_log_area_ratio','m_all_matched_top_bias_deg','m_all_matched_bottom_bias_deg'] if c in roles]
 r=roles[cols].copy()
 for arm in ['source','target']:
  d=r.rename(columns={'class_id':arm+'_class',**{c:arm+'_'+c for c in cols if c not in keys}})
  ev=ev.merge(d,on=['method','heldout_building',arm+'_class'],how='left',validate='many_to_one')
 assert ev.source_members.notna().all() and ev.target_members.notna().all()
 def axis(method):
  if 'RFUSE_GEOMQ' in method:return 'q_rank_asc'
  if 'RFUSE' in method:return 'size_rank_desc'
  if any(x in method for x in ['JOINT','Q_MEDIAN','Q_HARD']):return 'q_rank_asc'
  if any(x in method for x in ['BOUNDARY','GEOM','SCALE']):return 'area_rank_asc'
  return 'challenge_turn_rank_asc'
 ev['role_axis']=ev.method.map(axis)
 ev['role_source_rank']=[ev.at[i,'source_'+a] for i,a in zip(ev.index,ev.role_axis)]
 ev['role_target_rank']=[ev.at[i,'target_'+a] for i,a in zip(ev.index,ev.role_axis)]
 for c in ['role_source_rank','role_target_rank','source_k']:ev[c]=ev[c].astype('Int64')
 ev['role_direction']=ev.role_axis+':'+ev.role_source_rank.astype(str)+'/'+ev.source_k.astype(str)+'->'+ev.role_target_rank.astype(str)+'/'+ev.source_k.astype(str)
 ev['direction_is_source_dominant']=ev.source_size_rank_desc.eq(1)
 ev['target_more_turn_history']=ev.target_turn_rank_asc.gt(ev.source_turn_rank_asc)
 ev['target_higher_Q_history']=ev.target_q_rank_asc.gt(ev.source_q_rank_asc)
 ev['target_faster_history']=ev.target_time_rank_asc.lt(ev.source_time_rank_asc)
 ev['selection_phase']=ev.get('selection_phase','v21_internal_exploration')
 return ev

def summarize(ev,keys,metrics):
 # Keep references separate inside each image, then give images equal weight.
 pool_keys=keys+['pool_id','image','building']
 p=ev.groupby(pool_keys,dropna=False,observed=True)[metrics].mean().reset_index()
 images=p.groupby(keys+['image','building'],dropna=False,observed=True)[metrics].mean().reset_index()
 buildings=images.groupby(keys+['building'],dropna=False,observed=True)[metrics].mean().reset_index()
 ig=images.groupby(keys,dropna=False,observed=True);bg=buildings.groupby(keys,dropna=False,observed=True)
 means=ig[metrics].mean().add_suffix('_mean_image')
 counts=ig[metrics].count().add_suffix('_valid_images')
 base=means.join(counts)
 primary=[m for m in PRINCIPAL if m in metrics]
 if primary:
  base=base.join(ig[primary].median().add_suffix('_median_image'))
  base=base.join(ig[primary].quantile(.1).add_suffix('_p10_image')).join(ig[primary].quantile(.9).add_suffix('_p90_image'))
  positive=images.copy();positive[primary]=positive[primary].gt(0).where(positive[primary].notna()).astype(float)
  base=base.join(positive.groupby(keys,dropna=False,observed=True)[primary].sum(min_count=1).add_suffix('_positive_images'))
  for threshold in [1,2]:
   material=[c for c in ['B8L2_gap','B8L2_CA','B8L2_CB'] if c in images]
   pp=images.copy();pp[material]=pp[material].gt(threshold).where(pp[material].notna()).astype(float)
   base=base.join(pp.groupby(keys,dropna=False,observed=True)[material].sum(min_count=1).add_suffix('_images_gt'+str(threshold)))
  positive_b=buildings.copy();positive_b[primary]=positive_b[primary].gt(0).where(positive_b[primary].notna()).astype(float)
  base=base.join(bg[primary].mean().add_suffix('_mean_building')).join(bg[primary].count().add_suffix('_valid_buildings'))
  base=base.join(positive_b.groupby(keys,dropna=False,observed=True)[primary].sum(min_count=1).add_suffix('_positive_buildings'))
 totals=ev.groupby(keys,dropna=False,observed=True).agg(events=('event_id','size'),pools=('pool_id','nunique'),images=('image','nunique'),buildings=('building','nunique'),backgrounds=('background_id','nunique'),blocks=('block_id','nunique'))
 for c in ['A_failed','B_failed','C_failed','ABC_scored']:
  totals[c+'_events']=ev.groupby(keys,dropna=False,observed=True)[c].sum()
 for c in ['Q_loss10_CA','Q_loss10_CB','record_time_CB_pct_source_matched']:
  totals[c+'_events_valid']=ev.groupby(keys,dropna=False,observed=True)[c].count()
  if c.startswith('Q_loss'):totals[c+'_events']=ev.groupby(keys,dropna=False,observed=True)[c].sum()
 return base.join(totals).reset_index(),p,images,buildings

def main():
 ap=argparse.ArgumentParser();ap.add_argument('--metrics',required=True);ap.add_argument('--roles',required=True);ap.add_argument('--out',required=True);args=ap.parse_args()
 out=Path(args.out);out.mkdir(parents=True,exist_ok=True);ev=pd.read_csv(args.metrics,low_memory=False);roles=pd.read_csv(args.roles,low_memory=False)
 original_columns=set(ev.columns);ev=add_roles(ev,roles);metrics=[m for m in CORE if m in ev];keys=['method','condition','layer','scope','n','m','role_direction']
 save(out/'EVENT_ROLE_LINKS.csv.gz',ev[[c for c in ev.columns if c not in original_columns]+['event_id','method','heldout_building','source_class','target_class']])
 report,p,img,bld=summarize(ev,keys,metrics);save(out/'ALL_DIRECTION_N_M_RESULTS.csv.gz',report);save(out/'DIRECTION_IMAGE_RESULTS.csv.gz',img);save(out/'DIRECTION_BUILDING_RESULTS.csv.gz',bld)
 gkeys=['method','condition','layer','scope','n','m'];report,p,img,bld=summarize(ev,gkeys,metrics);save(out/'METHOD_GRID_RESULTS.csv',report);save(out/'METHOD_GRID_POOL_RESULTS.csv.gz',p)
 report,_,_,_=summarize(ev,keys+['official_difficulty'],metrics);save(out/'DIRECTION_FORMAL_DIFFICULTY_RESULTS.csv.gz',report)
 report,_,_,_=summarize(ev,keys+['geometric_challenge'],metrics);save(out/'DIRECTION_STRUCTURE_OPPORTUNITY_RESULTS.csv.gz',report)
 # Method comparison on exactly shared target-pool/n/m cells. No cross-method
 # numerical class correspondence is assumed: all legal directions average first.
 base=p[p.method=='DSTRUCT_K3'];compare=[];ck=['condition','layer','scope','n','m','pool_id','image','building']
 for method,d in p.groupby('method',sort=True):
  both=d.merge(base,on=ck,suffixes=('_candidate','_DSTRUCT'),validate='one_to_one')
  if not len(both):continue
  for kk,g in both.groupby(['condition','layer','scope','n','m'],dropna=False):
   row=dict(zip(['condition','layer','scope','n','m'],kk));row.update(method=method,pools=len(g),images=g.image.nunique(),buildings=g.building.nunique())
   for metric in metrics:
    a=g[metric+'_candidate'];b=g[metric+'_DSTRUCT'];ok=a.notna()&b.notna()
    t=g.loc[ok,['image','building']].copy();t['candidate']=a[ok];t['baseline']=b[ok];im=t.groupby(['image','building'])[['candidate','baseline']].mean()
    row[metric+'_paired_images']=len(im);row[metric+'_candidate']=im.candidate.mean();row[metric+'_DSTRUCT']=im.baseline.mean();row[metric+'_difference']=float((im.candidate-im.baseline).mean())
   compare.append(row)
 save(out/'COMMON_CELL_COMPARISON_VS_DSTRUCT_K3.csv.gz',pd.DataFrame(compare))
 # This shortlist is a transparent screen output, not an adopted result.
 d=pd.read_csv(out/'ALL_DIRECTION_N_M_RESULTS.csv.gz');q=d[(d.B8L2_gap_valid_images>=8)&(d.B8L2_gap_valid_buildings>=4)].copy()
 q['Q_cross_within_ratio']=q.B8L2_cross_mean_image/q.B8L2_within_mean_image
 q['Q_gap_positive_image_fraction']=q.B8L2_gap_positive_images/q.B8L2_gap_valid_images
 q=q.sort_values(['B8L2_gap_mean_image','B8L2_gap_valid_images'],ascending=False);save(out/'SCREEN_SUPPORTED_DIRECTION_CANDIDATES.csv',q)
 jsave(out/'SUMMARY_RECEIPT.json',dict(events=len(ev),methods=ev.method.nunique(),pools=ev.pool_id.nunique(),source_metrics=args.metrics,
  direction_selection='All candidate directions retained; screen-supported table uses >=8 valid images and >=4 buildings, no effect-sign filter',
  crossfold_roles='training-history axis ranks within fold; exact class identities and centers linked; raw class numbers never pooled',
  weighting='events within target and condition; equal targets within image; equal images for primary effect; building-equal effect shown separately',
  new_fusion=0,role_map=args.roles,reporting_does_not_change_labels=True))
 print(json.dumps(dict(events=len(ev),methods=ev.method.nunique(),direction_rows=len(d),supported_direction_rows=len(q))),flush=True)
if __name__=='__main__':main()
