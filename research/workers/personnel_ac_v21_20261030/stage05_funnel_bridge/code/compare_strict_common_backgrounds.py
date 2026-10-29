"""Exact X/Z, n/m comparisons of registered F-neutral and B-outside teams.

The index is selected solely from frozen member identities.  It is restricted
to the 66 previously registered strict-ABC m9/m10 cells.  It does not create
new teams or infer a same-class control for direct AC.  Outcome analysis is a
separate optional step after the index has been written and hashed.
"""
from pathlib import Path
from collections import Counter, defaultdict
import argparse, csv, gzip, hashlib, json, time
import numpy as np
import pandas as pd

OUT=Path(__file__).resolve().parents[1]; BASE=OUT.parent
CELL=['pool_id','method','n','m','canonical_source_class','canonical_target_class']
SCALARS=['B8L2','D10','IoU3D100','S_bottom_deg','omission','extension','fusion_turn_n',
 'fusion_short_turn_edges','fusion_redundancy_n','geometry_area_h2','height_mean_h',
 'matched_ref_top_abs_deg','matched_ref_bottom_abs_deg','matched_ref_horizontal_abs_deg',
 'boundary_loss','direction_loss','height_loss']
PAIRS=['geometry_pair_angle','geometry_bev_distance','geometry_centroid_distance','geometry_log_area_distance']
FIELDS={m:m+'_CA' for m in SCALARS}
FIELDS.update({m:m+'_AC' for m in PAIRS})
FIELDS.update({'record_time_pct':'record_time_CA_pct_source_matched','record_time_seconds':'record_time_CA_seconds_source_matched',
 'fusion_failure_risk':'fusion_failure_observed_risk_change_CA','incomplete_output_risk':'output_not_complete_risk_change_CA'})
FLAGS=['Q_missing','fusion_execution_exception','fusion_structural_failure','output_invalid_geometry',
 'fusion_failure_observed','measurement_exception','reference_floor_only','output_not_complete']

def cj(x):return json.dumps(x,sort_keys=True,separators=(',',':'),ensure_ascii=False)
def digest(x):return hashlib.sha256(cj(x).encode()).hexdigest()[:24]
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def members(x):return sorted(str(x).split('|')) if pd.notna(x) and str(x) else []
def truth(x):return str(x).lower() in ['true','1','1.0']
def save(d,name):
 p=OUT/name
 with (gzip.open(p,'wt',encoding='utf-8-sig',newline='') if p.name.endswith('.gz') else open(p,'w',encoding='utf-8-sig',newline='')) as f:d.to_csv(f,index=False)
def load_index():
 started=time.monotonic();cap=BASE/'stage01_capacity'
 strict_path=OUT/'inputs/STRICT_LARGE_CELLS.csv'
 strict=pd.read_csv(strict_path)
 roles=pd.read_csv(cap/'FROZEN_ROLE_PARENT_MAP_ALL_LOBO.csv')
 role={(r.method,r.heldout_building,r.class_id):int(r.primary_role_rank) for r in roles.itertuples()}
 pools=pd.read_csv(cap/'POOL_METHOD_CAPACITY.csv.gz')
 poolmap={}
 for r in pools.itertuples():
  cls=json.loads(r.class_members_json);workerclass={w:c for c,ws in cls.items() for w in ws}
  poolmap[r.pool_id,r.method]=(r,cls,workerclass)
 rows=[]
 for r in strict.itertuples():
  s,t=sorted([r.source_class,r.target_class],key=lambda c:(role[r.method,r.building,c],c))
  p,cls,wc=poolmap[r.pool_id,r.method]
  ns,nt=len(cls[r.source_class]),len(cls[r.target_class]);outside=int(p.pool_n)-ns-nt
  rows.append(dict(pool_id=r.pool_id,image=r.image,building=r.building,method=r.method,n=int(r.n),m=int(r.m),
    canonical_source_class=s,canonical_target_class=t,strict_source_class=r.source_class,strict_target_class=r.target_class,
    strict_to_canonical_sign=1 if s==r.source_class else -1,source_capacity=ns,target_capacity=nt,pool_n=int(p.pool_n),
    D_n=int(r.n-r.m),strict_remaining_background_n=int(p.pool_n-3*r.m),outside_both_classes_n=outside,
    strict_background_space_equals_outside_classes=(ns==2*r.m and nt==r.m),
    strict_requires_B_same_class_members=int(r.m),
    B_anchor_same_m_capacity=(min(ns,nt)==r.m and outside>=r.n-r.m)))
 conditions=pd.DataFrame(rows);assert len(conditions)==66 and not conditions.duplicated(CELL).any()
 cells={tuple(r) for r in conditions[CELL].itertuples(index=False,name=None)}
 reg_path=BASE/'stage01_registered/AC_EVENTS.csv.gz'
 cols=['event_id','physical_pair_id','pool_id','image','building','method','n','m','n_A','n_C',
  'source_class','target_class','source_role_rank','target_role_rank','X_workers','Z_workers','D_workers','D_class_counts',
  'A_team_key','C_team_key','design_family','equal_team_size','pure_cross_class_blocks']
 reg=pd.read_csv(reg_path,usecols=cols,low_memory=False)
 reg=reg[reg.equal_team_size.map(truth)&reg.pure_cross_class_blocks.map(truth)].copy()
 reg['canonical_source_class']=reg.source_class;reg['canonical_target_class']=reg.target_class
 reg['_key']=list(reg[CELL].itertuples(index=False,name=None));reg=reg[reg['_key'].isin(cells)].copy()
 for col in ['X_workers','Z_workers','D_workers']:reg[col]=reg[col].fillna('').map(lambda x:'|'.join(members(x)))
 reg['_xz']=reg.X_workers+'::'+reg.Z_workers
 reg['has_main_A_or_B_equal_link']=reg.design_family.str.contains('A_equal_AC|B_equal_whole_class',regex=True)
 f=reg[reg.design_family.str.contains('F_strict_common_n_bridge',regex=False)].copy()
 b=reg[reg.design_family.str.contains('B_unequal_equal_size_anchor',regex=False)].copy()
 assert len(f)==528 and f['_key'].nunique()==66
 for r in b.itertuples():
  _,cls,wc=poolmap[r.pool_id,r.method]
  assert all(wc.get(w,'UNKNOWN') not in [r.source_class,r.target_class] for w in members(r.D_workers)),r.event_id
 fby={k:g for k,g in f.groupby('_key')};bby={k:g for k,g in b.groupby('_key')}
 matches=[];coverage=[]
 for r in conditions.to_dict('records'):
  key=tuple(r[k] for k in CELL);ff=fby[key];bb=bby.get(key,b.iloc[:0]);xz=set(ff._xz)&set(bb._xz)
  count=different=identical=classes_different=0
  for fx in ff.itertuples():
   for bx in bb[bb._xz.eq(fx.X_workers+'::'+fx.Z_workers)].itertuples():
    assert (fx.source_class,fx.target_class,fx.n_A,fx.n_C)==(bx.source_class,bx.target_class,bx.n_A,bx.n_C)
    deq=fx.D_workers==bx.D_workers;ceq=json.loads(fx.D_class_counts)==json.loads(bx.D_class_counts)
    count+=1;different+=not deq;identical+=deq;classes_different+=not ceq
    matches.append(dict(**{k:r[k] for k in CELL},image=r['image'],building=r['building'],
      background_comparison_id=digest([r['pool_id'],r['method'],sorted([fx.event_id,bx.event_id])]),
      physical_background_comparison_id=digest([r['pool_id'],sorted([fx.physical_pair_id,bx.physical_pair_id])]),
      F_event_id=fx.event_id,B_event_id=bx.event_id,F_physical_pair_id=fx.physical_pair_id,B_physical_pair_id=bx.physical_pair_id,
      X_workers=fx.X_workers,Z_workers=fx.Z_workers,F_D_workers=fx.D_workers,B_D_workers=bx.D_workers,
      F_D_class_counts=fx.D_class_counts,B_D_class_counts=bx.D_class_counts,D_identity_equal=deq,D_class_composition_equal=ceq,
      F_A_team_key=fx.A_team_key,F_C_team_key=fx.C_team_key,B_A_team_key=bx.A_team_key,B_C_team_key=bx.C_team_key,
      F_has_main_A_or_B_equal_link=fx.has_main_A_or_B_equal_link,B_has_main_A_or_B_equal_link=bx.has_main_A_or_B_equal_link,
      overlaps_broader_main_AB_background_study=fx.has_main_A_or_B_equal_link,
      strict_to_canonical_sign=r['strict_to_canonical_sign'],strict_source_class=r['strict_source_class'],strict_target_class=r['strict_target_class'],
      strict_background_space_equals_outside_classes=r['strict_background_space_equals_outside_classes']))
  coverage.append(dict(r,F_events=len(ff),F_exact_XZ_blocks=ff._xz.nunique(),B_outside_events=len(bb),B_exact_XZ_blocks=bb._xz.nunique(),
    shared_exact_XZ_blocks=len(xz),exact_XZ_event_pair_matches=count,exact_XZ_different_D_matches=different,
    exact_XZ_identical_D_matches=identical,exact_XZ_different_class_composition_matches=classes_different,
    comparison_availability=('exact_XZ_different_D' if different else 'exact_XZ_same_D_only' if identical else 'common_condition_different_XZ' if len(bb) else 'no_registered_B_outside_at_same_n_m')))
 match=pd.DataFrame(matches);coverage=pd.DataFrame(coverage)
 assert not match.background_comparison_id.duplicated().any()
 save(match,'STRICT66_EXACT_F_NEUTRAL_VS_B_OUTSIDE_BACKGROUND_PAIRS.csv.gz')
 save(coverage,'STRICT66_F_VS_B_BACKGROUND_CONDITION_COVERAGE.csv')
 # Actual recorded strict D class composition, retaining member identities.
 strict_event_path=OUT/'inputs/STRICT_LARGE_EVENTS_EXACT.csv.gz'
 se=pd.read_csv(strict_event_path,usecols=['event_id','pool_id','method','source_class','target_class','n','m','D','X','Y','Z'])
 strict_dist=[]
 for key,g in se.groupby(['pool_id','method','source_class','target_class','n','m']):
  pid,method,s,t,n,m=key;_,cls,wc=poolmap[pid,method];vectors=Counter()
  ds=defaultdict(set)
  for row in g.itertuples():
   vec=cj(dict(sorted(Counter(wc.get(w,'UNKNOWN') for w in members(row.D)).items())));vectors[vec]+=1;ds[vec].add(row.D)
  for vec,c in vectors.items():strict_dist.append(dict(pool_id=pid,method=method,strict_source_class=s,strict_target_class=t,n=n,m=m,
    D_class_counts=vec,strict_events=c,unique_D_members=len(ds[vec]),strict_total_events=len(g)))
 save(pd.DataFrame(strict_dist),'STRICT66_ACTUAL_STRICT_D_CLASS_COMPOSITIONS.csv')
 receipt=dict(index_complete=True,design_uses_scores=False,strict_conditions=len(conditions),F_events=len(f),B_events_in_same_conditions=len(b),
   exact_XZ_event_pair_matches=len(match),different_D_matches=int((~match.D_identity_equal).sum()),
   identical_D_matches=int(match.D_identity_equal.sum()),different_D_physical_comparisons=match[~match.D_identity_equal].physical_background_comparison_id.nunique(),
   conditions_with_B_anchor=int(coverage.B_outside_events.gt(0).sum()),conditions_with_shared_XZ=int(coverage.shared_exact_XZ_blocks.gt(0).sum()),
   conditions_with_exact_different_D=int(coverage.exact_XZ_different_D_matches.gt(0).sum()),
   different_D_same_class_quota_comparisons=int((~match.D_identity_equal & match.D_class_composition_equal).sum()),
   different_D_changed_class_quota_comparisons=int((~match.D_identity_equal & ~match.D_class_composition_equal).sum()),
   conditions_where_strict_D_space_equals_outside=int(coverage.strict_background_space_equals_outside_classes.sum()),
   overlapping_broader_main_AB_method_comparisons=int((~match.D_identity_equal & match.overlaps_broader_main_AB_background_study).sum()),
   same_D_rows_are_identity_checks_not_background_effects=True,new_teams=0,new_fusions=0,
   sources=[dict(path=str(p.relative_to(BASE)),sha256=sha(p)) for p in [reg_path,strict_path,strict_event_path,cap/'POOL_METHOD_CAPACITY.csv.gz']],
   output_sha256={name:sha(OUT/name) for name in ['STRICT66_EXACT_F_NEUTRAL_VS_B_OUTSIDE_BACKGROUND_PAIRS.csv.gz',
    'STRICT66_F_VS_B_BACKGROUND_CONDITION_COVERAGE.csv','STRICT66_ACTUAL_STRICT_D_CLASS_COMPOSITIONS.csv']},seconds=time.monotonic()-started)
 (OUT/'STRICT66_BACKGROUND_INDEX_RECEIPT.json').write_text(json.dumps(receipt,indent=2,ensure_ascii=False))
 print(json.dumps(receipt,indent=2,ensure_ascii=False));return match,coverage

def measure(match,coverage,partial=False):
 start=time.monotonic();different=match[~match.D_identity_equal.map(truth)].copy();joined=[];pending=[];sources=[]
 identity_fields=['event_id','A_output_state','C_output_state','A_score_status','C_score_status','time_comparable_source_count_AC',
  'A_time_source_count_signature','C_time_source_count_signature','A_all_time_sources_known','C_all_time_sources_known']
 statuses=[arm+'_'+flag for arm in ['A','C'] for flag in FLAGS]
 needed=set(identity_fields+statuses+list(FIELDS.values())+[arm+'_'+m for arm in ['A','C'] for m in SCALARS])
 for pid,g in different.groupby('pool_id'):
  p=BASE/'stage04_metrics/metric_shards'/(pid+'.csv.gz')
  if not p.exists():pending.append(pid);continue
  d=pd.read_csv(p,usecols=lambda c:c in needed,low_memory=False).set_index('event_id')
  ids=set(g.F_event_id)|set(g.B_event_id);assert ids<=set(d.index)
  d=d.loc[sorted(ids)];sources.append(dict(pool_id=pid,path=str(p.relative_to(BASE)),sha256=sha(p)))
  for r in g.to_dict('records'):
   f=d.loc[r['F_event_id']];b=d.loc[r['B_event_id']]
   base={k:r[k] for k in ['background_comparison_id','physical_background_comparison_id',*CELL,'image','building','F_event_id','B_event_id',
     'strict_to_canonical_sign','strict_background_space_equals_outside_classes','D_class_composition_equal',
     'overlaps_broader_main_AB_background_study','X_workers','Z_workers']}
   for prefix,row in [('F',f),('B',b)]:
    for s in ['A_output_state','C_output_state','A_score_status','C_score_status',*statuses]:base[prefix+'_'+s]=row.get(s,np.nan)
    base[prefix+'_time_comparable_source_count_AC']=row.get('time_comparable_source_count_AC',np.nan)
    for arm in ['A','C']:base[prefix+'_'+arm+'_time_source_count_signature']=row.get(arm+'_time_source_count_signature','')
   signatures=[str(row.get(arm+'_time_source_count_signature','')) for row in [f,b] for arm in ['A','C']]
   time_four_matched=all(truth(row.get(arm+'_all_time_sources_known',False)) for row in [f,b] for arm in ['A','C']) and len(set(signatures))==1
   base['four_team_time_source_count_matched']=time_four_matched
   for metric,field in FIELDS.items():
    fv=pd.to_numeric(f.get(field,np.nan),errors='coerce');bv=pd.to_numeric(b.get(field,np.nan),errors='coerce')
    a_shift=c_shift=np.nan
    if metric in SCALARS:
     a_shift=pd.to_numeric(f.get('A_'+metric,np.nan),errors='coerce')-pd.to_numeric(b.get('A_'+metric,np.nan),errors='coerce')
     c_shift=pd.to_numeric(f.get('C_'+metric,np.nan),errors='coerce')-pd.to_numeric(b.get('C_'+metric,np.nan),errors='coerce')
     if all(pd.notna(x) and np.isfinite(x) for x in [fv,bv,a_shift,c_shift]):assert abs((fv-bv)-(c_shift-a_shift))<1e-7,(r['background_comparison_id'],metric)
    pairedvalid=pd.notna(fv) and pd.notna(bv) and (time_four_matched if metric.startswith('record_time') else True)
    joined.append(dict(base,metric=metric,numerical_direction_available=metric not in PAIRS,F_effect=fv,B_effect=bv,
      paired_effect_valid=pairedvalid,F_minus_B_pairwise_source_controlled_effect=fv-bv,
      F_minus_B_effect=fv-bv if pairedvalid else np.nan,A_background_shift_F_minus_B=a_shift,C_background_shift_F_minus_B=c_shift))
 if pending and not partial:raise RuntimeError(f'Pending metric shards for {pending}; index remains saved, no final outcomes emitted')
 effects=pd.DataFrame(joined)
 labor=effects[effects.metric.eq('record_time_seconds')&effects.paired_effect_valid] if len(effects) else effects
 if len(labor):assert labor.F_minus_B_effect.abs().max()<1e-7,'Fixed exact X/Z absolute recorded-labor difference must be invariant to D'
 suffix='_PARTIAL' if pending else ''
 save(effects,'STRICT66_EXACT_BACKGROUND_EFFECTS'+suffix+'.csv.gz')
 if len(effects):
  # First equal alternative B backgrounds for the same F/XZ, then equal XZ
  # blocks, then conditions. Raw rows retain dependence and all four states.
  effects['_xz']=effects.X_workers+'::'+effects.Z_workers
  vals=['F_effect','B_effect','F_minus_B_effect','A_background_shift_F_minus_B','C_background_shift_F_minus_B']
  effects['absolute_F_minus_B_effect']=effects.F_minus_B_effect.abs();vals.append('absolute_F_minus_B_effect')
  paired=effects.copy();paired.loc[~paired.paired_effect_valid,vals]=np.nan
  blevel=paired.groupby(CELL+['metric','_xz','F_event_id'],dropna=False)[vals].mean()
  xlevel=blevel.groupby(CELL+['metric','_xz'],dropna=False).mean()
  clevel=xlevel.groupby(CELL+['metric'],dropna=False).mean().reset_index()
  count=effects.groupby(CELL+['metric'],dropna=False).agg(registered_background_comparisons=('background_comparison_id','size'),
    metric_valid_comparisons=('F_minus_B_effect','count'),registered_exact_XZ_blocks=('_xz','nunique')).reset_index()
  validblocks=effects[effects.paired_effect_valid].groupby(CELL+['metric'],dropna=False)._xz.nunique().rename('valid_exact_XZ_blocks').reset_index()
  count=count.merge(validblocks,on=CELL+['metric'],how='left',validate='one_to_one');count['valid_exact_XZ_blocks']=count.valid_exact_XZ_blocks.fillna(0).astype(int)
  clevel=clevel.merge(count,on=CELL+['metric'],validate='one_to_one')
  clevel=clevel.merge(coverage[CELL+['image','building','strict_to_canonical_sign','strict_background_space_equals_outside_classes']],on=CELL,validate='many_to_one')
  save(clevel,'STRICT66_EXACT_BACKGROUND_CONDITION_EFFECTS'+suffix+'.csv')
  physical=effects.drop_duplicates(['physical_background_comparison_id','metric']);support=[]
  for metric,g in physical.groupby('metric'):
   z=g[g.paired_effect_valid];flips=z.F_effect.mul(z.B_effect).lt(-1e-9)
   support.append(dict(metric=metric,registered_physical_background_comparisons=len(g),metric_valid_physical_comparisons=len(z),
     valid_target_pools=z.pool_id.nunique(),valid_images=z.image.nunique(),valid_buildings=z.building.nunique(),
     effect_sign_flips=int(flips.sum()) if metric not in PAIRS else None,
     target_pools_with_effect_sign_flip=z.loc[flips,'pool_id'].nunique() if metric not in PAIRS else None,
     median_abs_background_effect_difference=z.F_minus_B_effect.abs().median(),mean_abs_background_effect_difference=z.F_minus_B_effect.abs().mean(),
     estimand='physical four-endpoint descriptive distribution; pairs can share workers/teams and are not independent subjects'))
  save(pd.DataFrame(support),'STRICT66_BACKGROUND_PHYSICAL_SUPPORT_SUMMARY'+suffix+'.csv')
 receipt=dict(complete=not pending,pending_pools=pending,measured_background_comparisons=effects.background_comparison_id.nunique() if len(effects) else 0,
   measured_physical_background_comparisons=effects.physical_background_comparison_id.nunique() if len(effects) else 0,
   rows=len(effects),metrics=list(FIELDS),all_four_endpoints_required_for_scalar_difference=True,missing_values_imputed=False,
   labor_difference_requires_same_known_time_source_counts_in_all_four_teams=True,
   fixed_XZ_labor_seconds_invariance_valid_pairs=len(labor),fixed_XZ_labor_seconds_max_abs_difference=float(labor.F_minus_B_effect.abs().max()) if len(labor) else None,
   F_legal_source_count_labor_comparisons=int((effects.metric.eq('record_time_seconds')&effects.F_effect.notna()).sum()) if len(effects) else 0,
   B_legal_source_count_labor_comparisons=int((effects.metric.eq('record_time_seconds')&effects.B_effect.notna()).sum()) if len(effects) else 0,
   same_XZ_same_n_m_only_background_changed=True,quality_improvement_direction_only_for=['B8L2','D10'],
   new_teams=0,new_fusions=0,sources=sources,seconds=time.monotonic()-start)
 (OUT/('STRICT66_BACKGROUND_EFFECTS_RECEIPT'+suffix+'.json')).write_text(json.dumps(receipt,indent=2,ensure_ascii=False))
 print(json.dumps(receipt,indent=2,ensure_ascii=False))

if __name__=='__main__':
 parser=argparse.ArgumentParser();parser.add_argument('--metrics',action='store_true');parser.add_argument('--reuse-index',action='store_true');parser.add_argument('--partial',action='store_true');args=parser.parse_args()
 if args.reuse_index:
  match=pd.read_csv(OUT/'STRICT66_EXACT_F_NEUTRAL_VS_B_OUTSIDE_BACKGROUND_PAIRS.csv.gz');coverage=pd.read_csv(OUT/'STRICT66_F_VS_B_BACKGROUND_CONDITION_COVERAGE.csv')
 else:match,coverage=load_index()
 if args.metrics:measure(match,coverage,args.partial)
