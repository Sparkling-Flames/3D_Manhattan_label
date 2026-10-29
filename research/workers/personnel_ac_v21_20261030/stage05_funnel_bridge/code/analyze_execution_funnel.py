"""Capacity -> registration -> execution -> evaluability -> direction.

Manual ordinary pools are the primary denominator. Metrics are read by pool;
missing values are never zero-filled. Existing strict ABC is a separately
matched reference and is never manufactured for the new direct AC design.
"""
from pathlib import Path
from collections import defaultdict
import argparse,csv,gzip,hashlib,json,math,time
import numpy as np
import pandas as pd

OUT=Path(__file__).resolve().parents[1];BASE=OUT.parent;CAP=BASE/'stage01_capacity'
DEST=OUT
KEYS=['pool_id','method','n','m','source_class','target_class']
SCALARS=['B8L2','D10','IoU3D100','S_bottom_deg','omission','extension','fusion_turn_n',
 'fusion_short_turn_edges','fusion_redundancy_n','geometry_area_h2','height_mean_h',
 'matched_ref_top_abs_deg','matched_ref_bottom_abs_deg','matched_ref_horizontal_abs_deg',
 'boundary_loss','direction_loss','height_loss']
PAIRS=['geometry_pair_angle','geometry_bev_distance','geometry_centroid_distance','geometry_log_area_distance']
FIELDS={m:m+'_CA' for m in SCALARS}
FIELDS.update({m:m+'_AC' for m in PAIRS})
FIELDS.update({'record_time_pct':'record_time_CA_pct_source_matched','record_time_seconds':'record_time_CA_seconds_source_matched',
 'fusion_failure_risk':'fusion_failure_observed_risk_change_CA','incomplete_output_risk':'output_not_complete_risk_change_CA'})
FUNNEL_METRICS=['B8L2','D10','fusion_turn_n','fusion_short_turn_edges','geometry_area_h2','height_mean_h',
 'geometry_pair_angle','geometry_centroid_distance','record_time_pct','record_time_seconds','fusion_failure_risk','incomplete_output_risk']
STATUS=['fusion_execution_exception','fusion_structural_failure','output_invalid_geometry','fusion_failure_observed','measurement_exception','Q_missing','output_not_complete']

def truth(x):return str(x).lower() in ['true','1','1.0']
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def save(d,name):
 p=DEST/name;p.parent.mkdir(parents=True,exist_ok=True)
 with (gzip.open(p,'wt',encoding='utf-8-sig',newline='') if p.name.endswith('.gz') else open(p,'w',encoding='utf-8-sig',newline='')) as f:d.to_csv(f,index=False)
def valid_summary(values):
 s=pd.to_numeric(values,errors='coerce').dropna()
 return {'valid_pools':len(s),'mean_change':s.mean(),'median_change':s.median(),'p10_change':s.quantile(.1) if len(s) else np.nan,
   'p90_change':s.quantile(.9) if len(s) else np.nan,'positive_pools':int((s>1e-9).sum()),'negative_pools':int((s<-1e-9).sum()),
   'nearzero_pools':int((s.abs()<=1e-9).sum()),'positive_fraction':float((s>1e-9).mean()) if len(s) else np.nan}

def main(args):
 global DEST
 DEST=OUT/args.output_subdir if args.output_subdir else OUT
 DEST.mkdir(parents=True,exist_ok=True)
 started=time.monotonic();registered=BASE/'stage01_registered/AC_EVENTS.csv.gz'
 idcols=KEYS+['event_id','physical_pair_id','image','building','scope','condition','layer','D_n','X_workers','Z_workers',
  'source_role_rank','target_role_rank','equal_team_size','pure_cross_class_blocks','whole_source','whole_target','design_family']
 reg_all=pd.read_csv(registered,usecols=idcols,low_memory=False)
 target=reg_all.condition.eq('manual')&reg_all.layer.eq('ordinary_manual')&reg_all.equal_team_size.map(truth)&reg_all.pure_cross_class_blocks.map(truth)
 reg=reg_all[target].copy();reg['n']=reg.n.astype(int);reg['m']=reg.m.astype(int)
 roles=pd.read_csv(CAP/'FROZEN_ROLE_PARENT_MAP_ALL_LOBO.csv');k_by_method=roles.groupby('method').k.first().astype(int).to_dict()
 def role_direction(frame):
  k=frame.method.map(k_by_method).astype(int).astype(str)
  return frame.source_role_rank.astype(int).astype(str)+'/'+k+'->'+frame.target_role_rank.astype(int).astype(str)+'/'+k
 reg['role_direction']=role_direction(reg);reg['_block']=reg.X_workers+'::'+reg.Z_workers
 reg['design_A_or_bridge']=reg.design_family.str.contains('A_equal_AC|F_strict_common_n_bridge',regex=True)
 reg['explicit_equal_whole']=reg.design_family.str.contains('B_equal_whole_class',regex=False)
 rstats=reg.groupby(KEYS,dropna=False).agg(registered_events=('event_id','size'),registered_blocks=('_block','nunique'),
   registered_A_or_bridge_events=('design_A_or_bridge','sum'),registered_equal_whole_events=('explicit_equal_whole','sum')).reset_index()
 meta=reg.groupby(KEYS,dropna=False)[['image','building','scope','role_direction','D_n']].first().reset_index()
 rstats=rstats.merge(meta,on=KEYS,validate='one_to_one')
 pm=pd.read_csv(CAP/'POOL_METHOD_CAPACITY.csv.gz')
 poolmeta={r.pool_id:(r.image,r.building,r.scope,int(r.pool_n)) for r in pm.itertuples()}
 strict=pd.read_csv(OUT/'STRICT_IMAGE_CONDITION_METRICS.csv.gz',low_memory=False)
 strict_keys={tuple(r) for r in strict[['pool_id','method','n','m','canonical_source_class','canonical_target_class']].drop_duplicates().itertuples(index=False,name=None)}
 cells=[];bridge_cells=[];pending=[];complete_pools=set();native_checks=[];metric_sources=[]
 groups={pid:g for pid,g in reg.groupby('pool_id',sort=True)}
 flagcols=[arm+'_'+f for arm in ['A','C'] for f in STATUS]
 wanted=['event_id',*FIELDS.values(),*flagcols,'time_comparable_source_count_AC']
 for index,(pid,design) in enumerate(groups.items()):
  checkfile=BASE/'stage03_endpoints/pools'/pid/'CHECKS.json'
  if checkfile.exists():
   check=json.loads(checkfile.read_text());native_checks.append({'pool_id':pid,'complete':bool(check.get('complete')),'requested':check.get('requested'),'total':check.get('total')})
   if check.get('complete'):complete_pools.add(pid)
  p=BASE/'stage04_metrics/metric_shards'/(pid+'.csv.gz')
  if not p.exists():pending.append(pid);continue
  assert pid in complete_pools,(pid,'measurement_without_complete_native_receipt')
  frame=pd.read_csv(p,usecols=lambda c:c in wanted,low_memory=False)
  assert not frame.event_id.duplicated().any()
  frame=design.merge(frame,on='event_id',how='left',validate='one_to_one',indicator=True)
  assert frame['_merge'].eq('both').all(),(pid,'missing_registered_event_metric')
  frame=frame.drop(columns='_merge');metric_sources.append({'pool_id':pid,'file':str(p.relative_to(BASE)),'sha256':sha(p),'selected_equal_pure_events':len(frame)})
  for col in FIELDS.values():
   if col not in frame:frame[col]=np.nan
   else:frame[col]=pd.to_numeric(frame[col],errors='coerce')
  for flag in STATUS:
   assert frame['A_'+flag].notna().all() and frame['C_'+flag].notna().all()
   frame['pair_'+flag]=frame['A_'+flag].map(truth)|frame['C_'+flag].map(truth)
  for metric,col in FIELDS.items():frame[metric+'_numeric']=frame[col];frame[metric+'_absolute']=frame[col].abs()
  valuecols=[m+s for m in FIELDS for s in ['_numeric','_absolute']]
  blocks=frame.groupby(KEYS+['_block'],dropna=False)[valuecols].mean()
  means=blocks.groupby(KEYS,dropna=False).mean();block_n=blocks.groupby(KEYS,dropna=False).count()
  valid_n=frame.groupby(KEYS,dropna=False)[valuecols].count()
  flag_n=frame.groupby(KEYS,dropna=False)[['pair_'+s for s in STATUS]].sum()
  ev_n=frame.groupby(KEYS,dropna=False).size()
  for key,averages in means.iterrows():
   common=dict(zip(KEYS,key));common.update(image=poolmeta[pid][0],building=poolmeta[pid][1],scope=poolmeta[pid][2],
     measured_events=int(ev_n.loc[key]),**{s+'_pair_events':int(flag_n.loc[key,'pair_'+s]) for s in STATUS})
   for metric in FUNNEL_METRICS:
    cells.append(dict(common,metric=metric,numerical_direction_available=metric not in PAIRS,
      mean_change=averages[metric+'_numeric'],mean_absolute_change=averages[metric+'_absolute'],
      valid_events=int(valid_n.loc[key,metric+'_numeric']),valid_blocks=int(block_n.loc[key,metric+'_numeric'])))
  # Fair shared-condition reference: designated A samples for prior m7/8;
  # only the explicitly registered F bridge samples for latest strict m9/10.
  frame['_strict_key']=list(frame[KEYS].itertuples(index=False,name=None))
  matching=frame['_strict_key'].isin(strict_keys)
  reference_sets={
    'A_registered_m7_m8':frame.m.isin([7,8])&frame.design_family.str.contains('A_equal_AC',regex=False),
    'F_neutral_common_n':frame.m.isin([9,10])&frame.design_family.str.contains('F_strict_common_n_bridge',regex=False),
    'B_outside_equal_anchor':frame.design_family.str.contains('B_unequal_equal_size_anchor',regex=False)}
  for reference_set,eligible in reference_sets.items():
   bb=frame[matching&eligible]
   if not len(bb):continue
   bk=bb.groupby(KEYS+['_block'],dropna=False)[valuecols].mean();bm=bk.groupby(KEYS,dropna=False).mean();bn=bk.groupby(KEYS,dropna=False).count()
   vn=bb.groupby(KEYS,dropna=False)[valuecols].count();en=bb.groupby(KEYS,dropna=False).size()
   for key,averages in bm.iterrows():
    for metric in SCALARS+PAIRS:
     bridge_cells.append(dict(zip(KEYS,key),metric=metric,new_reference_set=reference_set,new_registered_direct_AC_events=int(en.loc[key]),
       new_valid_events=int(vn.loc[key,metric+'_numeric']),new_valid_blocks=int(bn.loc[key,metric+'_numeric']),
       new_canonical_signed_or_distance_mean=averages[metric+'_numeric'],new_absolute_change_mean=averages[metric+'_absolute']))
  if index%30==0:print(json.dumps({'phase':'measured_pools','pools':index+1,'condition_metric_rows':len(cells)}),flush=True)
 if pending and not args.partial:raise RuntimeError(f'{len(pending)} ordinary Manual pools have pending metric shards; no final funnel written')
 measured=pd.DataFrame(cells)
 if not len(measured):raise RuntimeError('No measured ordinary Manual direct-AC rows are available')
 cell=rstats.merge(measured,on=KEYS+['image','building','scope'],how='left',validate='one_to_many')
 save(cell,'POOL_DIRECTION_N_M_METRIC_SUPPORT.csv.gz')
 save(pd.DataFrame(native_checks),'NATIVE_EXECUTION_POOL_CHECKS.csv')
 # Detailed pool funnel uses a union of all actually registered n/m and the
 # fixed major-scale grid, without selecting on an observed effect.
 canonical={}
 rolemap={(r.method,r.heldout_building,r.class_id):(float(r.primary_role_rank),int(r.k)) for r in roles.itertuples()}
 directions=pd.read_csv(CAP/'DIRECTED_CLASS_CAPACITY.csv.gz')
 dd=[]
 for r in directions.itertuples():
  sr,k=rolemap[r.method,r.building,r.source_class];tr,_=rolemap[r.method,r.building,r.target_class]
  if (sr,r.source_class)>=(tr,r.target_class):continue
  dd.append(dict(pool_id=r.pool_id,method=r.method,scope=r.scope,role_direction=f'{int(sr)}/{k}->{int(tr)}/{k}',max_m_AC=r.max_m,
    pool_n=r.pool_n,known_n=r.known_n,image=r.image,building=r.building))
 direction_caps=pd.DataFrame(dd)
 full=pm[['pool_id','method','scope','max_m_AC','pool_n','known_n','image','building']].copy();full['role_direction']='ALL_CANONICAL_DIRECTIONS'
 direction_caps=pd.concat([full,direction_caps],ignore_index=True)
 direction_caps=direction_caps.groupby(['method','scope','role_direction','pool_id'],dropna=False).agg(
    max_m_AC=('max_m_AC','max'),pool_n=('pool_n','first'),known_n=('known_n','first'),image=('image','first'),building=('building','first')).reset_index()
 all_cells=cell.copy();all_cells['role_direction']='ALL_CANONICAL_DIRECTIONS'
 cellboth=pd.concat([cell,all_cells],ignore_index=True)
 # Vectorized cohort summaries preserve the same equal-pool estimand while
 # avoiding tens of thousands of tiny groupby/quantile operations.
 cohort=['method','scope','role_direction','n','m','metric']
 pooled=cellboth[cellboth.metric.notna()].groupby(cohort+['pool_id'],dropna=False).agg(
   mean_change=('mean_change','mean'),mean_absolute_change=('mean_absolute_change','mean'),
   valid_events=('valid_events','sum'),registered_events=('registered_events','sum'),measured_events=('measured_events','sum'),
   exception_events=('fusion_execution_exception_pair_events','sum'),structural_failure_events=('fusion_structural_failure_pair_events','sum'),
   invalid_geometry_events=('output_invalid_geometry_pair_events','sum'),measurement_exception_events=('measurement_exception_pair_events','sum'),
   image=('image','first'),building=('building','first')).reset_index()
 pooled['positive']=pooled.mean_change.gt(1e-9);pooled['negative']=pooled.mean_change.lt(-1e-9)
 pooled['nearzero']=pooled.mean_change.abs().le(1e-9);pooled['fully_valid']=pooled.valid_events.eq(pooled.registered_events)
 for stem in ['exception','structural_failure','invalid_geometry','measurement_exception']:pooled['has_'+stem]=pooled[stem+'_events'].gt(0)
 stats=pooled.groupby(cohort,dropna=False).agg(valid_pools=('mean_change','count'),mean_change=('mean_change','mean'),median_change=('mean_change','median'),
   positive_pools=('positive','sum'),negative_pools=('negative','sum'),nearzero_pools=('nearzero','sum'),
   measured_pools=('pool_id','size'),metric_valid_events=('valid_events','sum'),registered_events=('registered_events','sum'),
   metric_all_registered_events_valid_pools=('fully_valid','sum'),mean_absolute_change_over_pools=('mean_absolute_change','mean'),
   pools_with_native_execution_exception=('has_exception','sum'),pools_with_structural_failure=('has_structural_failure','sum'),
   pools_with_invalid_geometry=('has_invalid_geometry','sum'),pools_with_measurement_exception=('has_measurement_exception','sum'))
 quantiles=pooled.groupby(cohort,dropna=False).mean_change.quantile([.1,.9]).unstack().rename(columns={.1:'p10_change',.9:'p90_change'})
 supports=pooled[pooled.valid_events.gt(0)].groupby(cohort,dropna=False).agg(metric_valid_images=('image','nunique'),metric_valid_buildings=('building','nunique'))
 stats=stats.join(quantiles).join(supports)
 stats[['metric_valid_images','metric_valid_buildings']]=stats[['metric_valid_images','metric_valid_buildings']].fillna(0).astype(int)
 stats['positive_fraction']=stats.positive_pools.div(stats.valid_pools.where(stats.valid_pools.gt(0)))
 summaries={key:row.to_dict() for key,row in stats.iterrows()}
 funnel=[];pool_funnel=[]
 major={(n,m) for n in [12,14,16,18,20,22,24,26,28,30] for m in [7,8,9,10,12] if n>=m}
 for (method,scope,direction),capacity in direction_caps.groupby(['method','scope','role_direction'],sort=True):
  observed=cellboth[(cellboth.method==method)&(cellboth.scope==scope)&(cellboth.role_direction==direction)]
  nm=major|set(observed[['n','m']].itertuples(index=False,name=None))
  cap=capacity.set_index('pool_id')
  for n,m in sorted(nm):
   total=cap.pool_n.ge(n+m);history=total&cap.known_n.ge(2*m);feasible=history&cap.max_m_AC.ge(m)
   obs=observed[(observed.n==n)&(observed.m==m)]
   registered_pools=set(obs.pool_id);feasible_pools=set(cap.index[feasible]);assert registered_pools<=feasible_pools
   completed=registered_pools&complete_pools
   base=dict(method=method,scope=scope,role_direction=direction,n=n,m=m,replacement_fraction=m/n,
      pure_n_equals_m=n==m,block_can_reach_MV50=m>=math.ceil(n/2),background_can_reach_MV50=n-m>=math.ceil(n/2),
      legal_pools=len(cap),legal_images=cap.image.nunique(),legal_buildings=cap.building.nunique(),
      total_n_sufficient_pools=int(total.sum()),known_history_2m_sufficient_pools=int(history.sum()),class_capacity_pools=int(feasible.sum()),
      total_people_insufficient_pools=int((~total).sum()),history_insufficient_after_total_pools=int((total&~history).sum()),
      class_capacity_insufficient_after_history_pools=int((history&~feasible).sum()),registered_pools=len(registered_pools),
      capacity_feasible_not_registered_pools=len(feasible_pools-registered_pools),native_complete_registered_pools=len(completed),
      registered_native_pending_pools=len(registered_pools-completed))
   if direction=='ALL_CANONICAL_DIRECTIONS' and ((n,m) in major or m in [9,10,12]):
    for pid,r in cap.iterrows():
     reason='total_people_insufficient' if not total[pid] else 'historical_classification_total_insufficient' if not history[pid] else 'class_capacity_insufficient' if not feasible[pid] else 'capacity_feasible_not_registered' if pid not in registered_pools else 'registered_native_pending' if pid not in completed else 'native_complete'
     pool_funnel.append(dict(pool_id=pid,image=r.image,building=r.building,method=method,scope=scope,n=n,m=m,pool_n=r.pool_n,known_n=r.known_n,
       max_m_AC=r.max_m_AC,capacity_execution_stage=reason))
   for metric in FUNNEL_METRICS:
    sk=(method,scope,direction,n,m,metric)
    if sk in summaries:
     saved=summaries[sk]
     stat={k:saved[k] for k in ['valid_pools','mean_change','median_change','p10_change','p90_change','positive_pools','negative_pools','nearzero_pools','positive_fraction']}
     extra={k:v for k,v in saved.items() if k not in stat}
     extra['native_complete_no_valid_metric_pools']=len(completed)-int(stat['valid_pools'])
     extra['native_complete_unmeasured_pools']=len(completed)-int(extra['measured_pools'])
     extra['measured_no_valid_metric_pools']=int(extra['measured_pools'])-int(stat['valid_pools'])
    else:
     stat=valid_summary(pd.Series([],dtype=float));extra=dict(measured_pools=0,metric_valid_events=0,registered_events=0,metric_all_registered_events_valid_pools=0,
       native_complete_no_valid_metric_pools=len(completed),native_complete_unmeasured_pools=len(completed),measured_no_valid_metric_pools=0,
       metric_valid_images=0,metric_valid_buildings=0,mean_absolute_change_over_pools=np.nan,
       pools_with_native_execution_exception=0,pools_with_structural_failure=0,pools_with_invalid_geometry=0,pools_with_measurement_exception=0)
    nonzero=stat['positive_pools']+stat['negative_pools']
    if metric in PAIRS:
     stat.update(positive_pools=None,negative_pools=None,positive_fraction=np.nan)
    funnel.append(dict(base,metric=metric,numerical_direction_available=metric not in PAIRS,
       nonzero_difference_pools=nonzero,positive_means_quality_improvement=metric in ['B8L2','D10'],**stat,**extra))
 save(pd.DataFrame(funnel),'CAPACITY_REGISTRATION_EXECUTION_EVALUABILITY_DIRECTION_FUNNEL.csv.gz')
 save(pd.DataFrame(pool_funnel),'FIXED_SCALE_POOL_FUNNEL.csv.gz')
 # Shared-condition ABC bridge. Canonical orientation controls the sign;
 # the historical B control remains explicitly in its original source class.
 new=pd.DataFrame(bridge_cells).rename(columns={'source_class':'canonical_source_class','target_class':'canonical_target_class'})
 matchkeys=['pool_id','method','n','m','canonical_source_class','canonical_target_class','metric']
 assert not new.duplicated(matchkeys+['new_reference_set']).any()
 # The same historical ABC condition can have several explicitly separated
 # new sampling references. Repeated historical rows are views, not more ABC.
 bridge=strict.merge(new,on=matchkeys,how='left',indicator='new_AC_condition_match')
 bridge['new_strict_direction_signed_or_distance_mean']=bridge.new_canonical_signed_or_distance_mean
 scalar_mask=bridge.metric.isin(SCALARS)
 bridge.loc[scalar_mask,'new_strict_direction_signed_or_distance_mean']*=bridge.loc[scalar_mask,'strict_to_canonical_sign']
 bridge['new_has_no_B']=True
 save(bridge,'STRICT_ABC_AND_DIRECT_AC_SAME_CONDITION_REFERENCE.csv.gz')
 bridge_summary=[]
 matched=bridge[bridge.new_AC_condition_match.eq('both')]
 for key,g in matched.groupby(['strict_source_family','new_reference_set','method','n','m','strict_role_direction','metric'],dropna=False):
  oldcol='strict_signed_CA_mean' if key[-1] in SCALARS else 'absolute_CA_mean'
  ok=g[oldcol].notna()&g.new_strict_direction_signed_or_distance_mean.notna();z=g[ok]
  bridge_summary.append(dict(zip(['strict_source_family','new_reference_set','method','n','m','strict_role_direction','metric'],key),
   matched_target_pools=len(g),jointly_evaluable_pools=len(z),buildings=z.building.nunique(),
   strict_signed_or_distance_mean=z[oldcol].mean(),direct_AC_signed_or_distance_mean=z.new_strict_direction_signed_or_distance_mean.mean(),
   strict_absolute_CA_mean=z.absolute_CA_mean.mean(),direct_AC_absolute_CA_mean=z.new_absolute_change_mean.mean(),
   strict_within_AB_mean=z.within_AB_mean.mean(),strict_G_A_mean=z.G_A_mean.mean(),strict_G_S_mean=z.G_S_mean.mean(),
   strict_G_A_positive_pools=int(z.G_A_mean.gt(1e-9).sum()),strict_G_A_valid_pools=int(z.G_A_mean.notna().sum()),
   direct_AC_positive_pools=int(z.new_strict_direction_signed_or_distance_mean.gt(1e-9).sum()) if key[-1] in SCALARS else None,
   direct_AC_negative_pools=int(z.new_strict_direction_signed_or_distance_mean.lt(-1e-9).sum()) if key[-1] in SCALARS else None,
   signed_direction_agreement_pools=int((np.sign(z[oldcol])==np.sign(z.new_strict_direction_signed_or_distance_mean)).sum()) if key[-1] in SCALARS else None,
   note='New AC has no B; historical within/G metrics are a separate strict-ABC reference, not a new cross-minus-within estimate.'))
 save(pd.DataFrame(bridge_summary),'STRICT_ABC_DIRECT_AC_COMMON_CONDITION_SUMMARY.csv')
 receipt=dict(complete=not pending,registered_equal_pure_manual_events=len(reg),registered_equal_pure_manual_pools=reg.pool_id.nunique(),
   native_complete_pools=len(complete_pools),measured_pool_files=len(metric_sources),pending_pools=pending,
   pool_direction_n_m_metric_rows=len(cell),funnel_rows=len(funnel),fixed_scale_pool_rows=len(pool_funnel),
   strict_reference_rows=len(strict),strict_rows_with_new_same_condition=int(bridge.new_AC_condition_match.eq('both').sum()),
   canonical_pair_conditions_with_new_same_condition=matched[matchkeys[:-1]].drop_duplicates().shape[0],
   strict_directed_conditions_with_new_same_condition=matched[['strict_source_family','pool_id','method','n','m','source_class','target_class']].drop_duplicates().shape[0],
   direct_AC_reference_sets=sorted(new.new_reference_set.unique()),
   no_Q_zero_fill=True,every_metric_has_own_denominator=True,no_new_B_or_ABC=True,
   pure_n_equals_m_separately_flagged=True,scope_never_mixed=True,
   aggregation='Within exact XZ block average registered backgrounds; equal-weight blocks within pool/class-pair/n/m; equal class pairs within pool for all-direction row; equal pools for population summary.',
   source_registered_sha256=sha(registered),metric_sources=metric_sources,seconds=time.monotonic()-started)
 (DEST/'FUNNEL_AND_STRICT_BRIDGE_RECEIPT.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2)+'\n')
 print(json.dumps({**{k:v for k,v in receipt.items() if k not in ['metric_sources','pending_pools']},'pending_pool_count':len(pending)},ensure_ascii=False,indent=2))

if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--partial',action='store_true');p.add_argument('--output-subdir');main(p.parse_args())
