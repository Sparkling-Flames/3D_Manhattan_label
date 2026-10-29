"""Pure aggregation: fixed-A m paths, fixed-XYZ n paths and background changes.

No new teams, fusion, quality evaluation, geometry calculation or class fitting.
Image and building means follow target -> image -> building nesting. Metric
denominators remain explicit; paired C/B decomposition uses common support.
"""
from __future__ import annotations
import os
for v in ['OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS']:os.environ[v]='1'
from pathlib import Path
import argparse,json,hashlib
import numpy as np
import pandas as pd
from measure_registered_events import save,jsave

W=Path(__file__).resolve().parents[1];OUT=W/'analysis/scale_background_summary'
ROLES={'TARGET_DSTRUCT_K3':'challenge_turn_rank_asc:2/3->3/3','OPPGEOM_K3':'area_rank_asc:2/3->3/3','OPPJOINT_K4':'q_rank_asc:1/4->4/4'}
CORE={
 'Q_delta_C':'B8L2_C_increment_matched_CB','Q_delta_B':'B8L2_B_increment_matched_CB','Q_delta_net_CB':'B8L2_net_increment_matched_CB',
 'Q_delta_within_amplitude':'B8L2_within_increment_matched_ABC','Q_delta_cross_amplitude':'B8L2_cross_increment_matched_ABC','Q_delta_amplitude_gap':'B8L2_gap_increment_matched_ABC',
 'Q_net_small':'B8L2_net_small_matched_CB','Q_net_large':'B8L2_net_large_matched_CB',
 'D10_delta_C':'D10_C_increment_matched_CB','D10_delta_B':'D10_B_increment_matched_CB','D10_delta_net_CB':'D10_net_increment_matched_CB',
 'IoU3D_delta_C':'IoU3D100_C_increment_matched_CB','floor_WQ_delta_C':'floor_WQ_C_increment_matched_CB',
 'turn_delta_C':'fusion_turn_n_C_increment_matched_CB','short_edge_delta_C':'fusion_short_turn_edges_C_increment_matched_CB','redundancy_delta_C':'fusion_redundancy_n_C_increment_matched_CB',
 'area_delta_C':'geometry_area_h2_C_increment_matched_CB','height_delta_C':'height_mean_h_C_increment_matched_CB',
 'top_error_delta_C':'matched_ref_top_abs_deg_C_increment_matched_CB','bottom_error_delta_C':'matched_ref_bottom_abs_deg_C_increment_matched_CB',
 'direction_loss_delta_C':'direction_loss_C_increment_matched_CB','height_loss_delta_C':'height_loss_C_increment_matched_CB',
 'time_delta_C_seconds':'record_time_C_increment_seconds_source_matched_CB','time_delta_B_seconds':'record_time_B_increment_seconds_source_matched_CB','time_delta_net_CB_seconds':'record_time_net_increment_seconds_source_matched_CB',
 'time_delta_C_pct':'C_record_time_increment_pct_matched_CB','time_delta_B_pct':'B_record_time_increment_pct_matched_CB',
 'C_small_failure':'C_small_failed','C_large_failure':'C_large_failed','C_new_failure':'C_new_failure','C_recovered':'C_recovered',
 'B_small_failure':'B_small_failed','B_large_failure':'B_large_failed','B_new_failure':'B_new_failure','B_recovered':'B_recovered',
 'C_loss10':'C_Q_loss10','B_loss10':'B_Q_loss10','C_failure_or_loss10':'C_failure_or_loss10','B_failure_or_loss10':'B_failure_or_loss10'}

def aggregate(d,keys,metrics,prefix,core=None,save_units=True):
 metrics=[m for m in metrics if m in d]
 pool=d.groupby(keys+['pool_id','image','building'],dropna=False)[metrics].mean().reset_index()
 im=pool.groupby(keys+['image','building'],dropna=False)[metrics].mean().reset_index()
 b=im.groupby(keys+['building'],dropna=False)[metrics].mean().reset_index()
 group=d.groupby(keys,dropna=False);ig=im.groupby(keys,dropna=False);bg=b.groupby(keys,dropna=False)
 gg=group[metrics].count();pp=pool.groupby(keys,dropna=False)[metrics].count()
 stats={
  'mean_image':ig[metrics].mean(),'median_image':ig[metrics].median(),'p10_image':ig[metrics].quantile(.1),'p90_image':ig[metrics].quantile(.9),
  'valid_images':ig[metrics].count(),'mean_building':bg[metrics].mean(),'valid_buildings':bg[metrics].count(),'valid_path_pairs':gg,'valid_pools':pp}
 for name,unit in [('images',im),('buildings',b)]:
  for direction,mask in [('positive',unit[metrics]>0),('negative',unit[metrics]<0),('zero',unit[metrics]==0)]:
   temp=pd.concat([unit[keys],mask.where(unit[metrics].notna()).astype(float)],axis=1)
   stats[direction+'_'+name]=temp.groupby(keys,dropna=False)[metrics].sum(min_count=1)
 cover=group.agg(path_pairs=('pool_id','size'),pools=('pool_id','nunique'),images=('image','nunique'),buildings=('building','nunique'))
 if 'path_id' in d:cover['distinct_paths']=group.path_id.nunique()
 records=[];arrays={name:frame.reindex(cover.index)[metrics].to_numpy() for name,frame in stats.items()};cover_values=cover.to_dict('records')
 for ki,kk in enumerate(cover.index):
  kk=kk if isinstance(kk,tuple) else (kk,);base=dict(zip(keys,kk));base.update(cover.loc[kk].to_dict())
  base.update(cover_values[ki])
  for mi,metric in enumerate(metrics):
   records.append(dict(base,measure=metric,**{name:array[ki,mi] for name,array in arrays.items()}))
 long=pd.DataFrame(records);save(OUT/(prefix+'_ALL_METRIC_SUMMARY.csv.gz'),long)
 ccols=list(dict.fromkeys((core or {}).values()));ccols=[c for c in ccols if c in metrics]
 if save_units:
  save(OUT/(prefix+'_CORE_BY_IMAGE.csv.gz'),im[keys+['image','building']+ccols]);save(OUT/(prefix+'_CORE_BY_BUILDING.csv.gz'),b[keys+['building']+ccols])
 core_rows=[]
 positions={metric:i for i,metric in enumerate(metrics)}
 for ki,kk in enumerate(cover.index):
  kk=kk if isinstance(kk,tuple) else (kk,);r=dict(zip(keys,kk));r.update(cover_values[ki])
  for alias,col in (core or {}).items():
   if col not in metrics:continue
   for stat in ['mean_image','mean_building','valid_images','valid_buildings','valid_path_pairs','positive_images','positive_buildings']:
    r[alias+'_'+stat]=arrays[stat][ki,positions[col]]
  core_rows.append(r)
 small=pd.DataFrame(core_rows);save(OUT/(prefix+'_CORE_SUMMARY.csv'),small)
 return long,small,im,b

def main():
 ap=argparse.ArgumentParser();ap.add_argument('--merged-input',help='Use the already delivered complete merged increments instead of duplicating both original input tables.');args=ap.parse_args()
 OUT.mkdir(parents=True,exist_ok=True);frames=[];paths=[];manifest=[]
 if args.merged_input:
  fn=Path(args.merged_input).resolve();d=pd.read_csv(fn,low_memory=False);p=d[['path_id','min_registered_m','max_m']].drop_duplicates()
  manifest.append(dict(path=str(fn),rows=len(d),sha256=hashlib.sha256(fn.read_bytes()).hexdigest(),kind='delivered_complete_merged_increments'))
 else:
  for stem,design in [('fixed_A_m_paths','fixed_A_m_design'),('refinement_m_paths','refinement_m_design')]:
   fn=W/'analysis'/stem/'EXACT_M_PATH_INCREMENT_METRICS.csv.gz';d=pd.read_csv(fn,low_memory=False);d['source_batch']=stem;frames.append(d)
   p=pd.read_csv(W/'experiment'/design/'PATHS_EXACT.csv.gz');p['source_batch']=stem;paths.append(p)
   manifest.append(dict(path=str(fn.relative_to(W)),rows=len(d),sha256=hashlib.sha256(fn.read_bytes()).hexdigest()))
  d=pd.concat(frames,ignore_index=True);p=pd.concat(paths,ignore_index=True);p['min_registered_m']=p.m_values.map(lambda x:min(map(int,str(x).split('|'))))
 assert not d.duplicated(['path_id','m_small','m_large']).any() and p.path_id.is_unique
 d['role_direction']=d.method.map(ROLES);d['min_registered_m']=d.path_id.map(p.set_index('path_id').min_registered_m)
 metrics=[]
 bases=sorted(c.removesuffix('_C_increment_matched_CB') for c in d if c.endswith('_C_increment_matched_CB'))
 for metric in bases:
  for part in ['C_increment_matched_CB','B_increment_matched_CB','net_increment_matched_CB','within_increment_matched_ABC','cross_increment_matched_ABC','gap_increment_matched_ABC','C_increment','B_increment']:
   col=metric+'_'+part
   if col in d:metrics.append(col)
  ok=d[metric+'_CB4_scored'].fillna(False).astype(bool)
  for part in ['net_small','net_large']:
   col=metric+'_'+part+'_matched_CB';d[col]=d[metric+'_'+part].where(ok);metrics.append(col)
 for arm in ['B','C']:
  low=d[arm+'_small_failed'].astype(bool);high=d[arm+'_large_failed'].astype(bool)
  d[arm+'_new_failure']=high.astype(float).where(~low);d[arm+'_recovered']=(~high).astype(float).where(low)
  d[arm+'_failure_change']=high.astype(float)-low.astype(float)
  for col in [arm+'_small_failed',arm+'_large_failed',arm+'_new_failure',arm+'_recovered',arm+'_failure_change',arm+'_Q_loss10',arm+'_failure_or_loss10']:
   metrics.append(col)
  ok=d.time_comparable_CB4.fillna(False).astype(bool)&(d.B_small_source_time_total_seconds>0)&(d.C_small_source_time_total_seconds>0)
  d[arm+'_record_time_increment_pct_matched_CB']=100*(d[arm+'_large_source_time_total_seconds']/d[arm+'_small_source_time_total_seconds']-1).where(ok)
  metrics += [arm+'_record_time_increment_pct_matched_CB',arm+'_record_time_increment_pct_source_matched']
 metrics += ['record_time_C_increment_seconds_source_matched_CB','record_time_B_increment_seconds_source_matched_CB','record_time_net_increment_seconds_source_matched_CB']
 metrics=list(dict.fromkeys(metrics));save(OUT/'FIXED_A_ALL_M_INCREMENT_METRICS.csv.gz',d)
 print('merged',len(d),'pairs',len(p),'paths',flush=True)
 keys=['method','condition','scope','role_direction','n','m_small','m_large']
 _,fixed,_,_=aggregate(d,keys,metrics,'FIXED_M_PAIR',CORE)
 # Each path contributes its one actual minimum-to-capacity comparison.
 cap=d[d.m_small.eq(d.min_registered_m)&d.m_large.eq(d.max_m)].copy();assert len(cap)==len(p) and cap.path_id.is_unique
 save(OUT/'MIN_TO_ACTUAL_CAPACITY_EXACT_LINKS.csv.gz',cap[['path_id','pool_id','image','building','method','condition','scope','role_direction','n','m_small','m_large','max_m','background_target_n','event_small','event_large','A_team_key','B_small','B_large','C_small','C_large','source_batch']])
 _,_,_,_=aggregate(cap,keys,metrics,'MIN_TO_CAPACITY_BY_ACTUAL_M',CORE)
 policykeys=['method','condition','scope','role_direction','n']
 _,policy,_,_=aggregate(cap,policykeys,metrics,'CAPACITY_POLICY',CORE)
 coverage=cap.groupby(keys,dropna=False).agg(paths=('path_id','nunique'),pools=('pool_id','nunique'),images=('image','nunique'),buildings=('building','nunique'),Q_CB4_pairs=('B8L2_C_increment_matched_CB','count'),Q_ABC5_pairs=('B8L2_gap_increment_matched_ABC','count'),time_CB4_pairs=('record_time_C_increment_seconds_source_matched_CB','count')).reset_index()
 save(OUT/'MIN_TO_CAPACITY_ACTUAL_M_COVERAGE.csv',coverage)
 mixed=[]
 for kk,g in cap.groupby(policykeys,dropna=False):
  r=dict(zip(policykeys,kk));mix=g.groupby(['m_small','m_large']).size();r.update(actual_m_pairs=';'.join(f'{a}->{b}: {v} paths' for (a,b),v in mix.items()),min_m_small=int(g.m_small.min()),max_m_small=int(g.m_small.max()),min_actual_mmax=int(g.m_large.min()),max_actual_mmax=int(g.m_large.max()));mixed.append(r)
 policy=policy.merge(pd.DataFrame(mixed),on=policykeys,validate='one_to_one');save(OUT/'CAPACITY_POLICY_CORE_SUMMARY.csv',policy)
 # Same-target background contrast: exact XYZ,n,m; D membership changes.
 bf=W/'analysis/focused_contexts/FIXED_XYZ_BACKGROUND_CONTRASTS.csv.gz';back=pd.read_csv(bf,low_memory=False)
 bcore={'Q_delta_C':'C_Q_change_matched_CB','Q_delta_B':'B_Q_change_matched_CB','Q_delta_net_CB':'net_CB_Q_change_matched_CB','Q_delta_amplitude_gap':'B8L2_gap_change',
  'Q_delta_A_common_ABC':'A_Q_change_matched_ABC','geometry_BEV_gap_change':'geometry_bev_distance_gap_change','turn_CA_change':'fusion_turn_n_CA_change',
  'time_CB_relative_pct_change':'record_time_CB_pct_source_matched_change','C_new_failure':'C_new_failure','B_new_failure':'B_new_failure','A_new_failure':'A_new_failure'}
 _,backsummary,_,_=aggregate(back,['method','condition','scope','role_direction','n','m'],list(bcore.values()),'TARGET_BACKGROUND',bcore)
 seats=back.groupby(['method','condition','scope','role_direction','n','m'],dropna=False).agg(D_target_low_min=('target_seats_D_low','min'),D_target_low_max=('target_seats_D_low','max'),D_target_high_min=('target_seats_D_high','min'),D_target_high_max=('target_seats_D_high','max'),D_changed_min=('D_members_changed','min'),D_changed_max=('D_members_changed','max')).reset_index()
 backsummary=backsummary.merge(seats,on=['method','condition','scope','role_direction','n','m']);save(OUT/'TARGET_BACKGROUND_CORE_SUMMARY.csv',backsummary)
 # Existing exact fixed-XYZ/nested-D n paths remain a different experiment.
 nf=W/'analysis/global_size_paths/SIZE_PATH_RESULTS.csv.gz';ns=pd.read_csv(nf,low_memory=False)
 selected=ns[ns.method.isin(ROLES)&ns.role_direction.eq(ns.method.map(ROLES))].copy()
 pre=['paired_CB_delta_C_Q','paired_CB_delta_B_Q','paired_CB_delta_net_CB_Q','paired_ABC_delta_amplitude_gap','delta_C_D10','delta_C_IoU3D100','delta_C_fusion_turn_n','delta_C_height_mean_h','delta_C_minimum_support','C_new_failure','C_Q_loss10','C_turn_loss']
 cols=['method','condition','scope','role_direction','m','n_lower','n_higher','path_pairs','pools','images','buildings']+[c for c in selected if any(c.startswith(x+'_') for x in pre)]
 save(OUT/'FIXED_XYZ_N_PATH_CONTEXT.csv',selected[cols])
 # Equal-support decompositions remain true after both weighting schemes.
 errs=[]
 for table in [fixed,policy,backsummary]:
  for unit in ['image','building']:
   c,b,n=[table['Q_delta_'+part+'_mean_'+unit] for part in ['C','B','net_CB']]
   err=(c-b-n).abs().dropna()
   if len(err):errs.append(float(err.max()))
 assert max(errs)<1e-8
 jsave(OUT/'COMPLETE.json',dict(source_commit='a476461d7ede8db95da43de4139e612c05e618bc',data_release='v2.1',input_files=manifest,
  fixed_A_path_pairs=len(d),fixed_A_paths=len(p),fixed_A_methods=sorted(d.method.unique()),minimum_to_actual_capacity_pairs=len(cap),same_XYZ_background_pairs=len(back),fixed_XYZ_n_path_selected_conditions=len(selected),
  zero_new_fusions=True,zero_new_geometry_calculations=True,zero_new_class_fitting=True,geometry_duplicated_in_this_summary=False,
  weighting='mean of available paths within target; equal legal targets within image; equal images; separately mean images within building then equal buildings; primary/other scope kept separate',
  metric_missing='unknown retained; main C/B/net increments share identical metric-specific four-endpoint support; amplitude uses five unique endpoints including fixed A',
  common_Q_decomposition_max_error=max(errs),capacity_policy='per-path minimum registered m to that path actual mmax; actual m pairs separately listed, never treated as one fixed m'))
 print('complete',len(fixed),'fixed-m cells',len(policy),'capacity-policy cells',len(backsummary),'background cells',flush=True)
if __name__=='__main__':main()
