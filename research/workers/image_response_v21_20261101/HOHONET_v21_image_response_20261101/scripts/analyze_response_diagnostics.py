#!/usr/bin/env python3
"""Precision, tolerance, late-change and fixed-panel diagnostics, no fusion."""
from pathlib import Path
import json
import numpy as np
import pandas as pd
import analyze_response as ar
from summarize_response import summarize_values,MEASURES

ROOT=Path(__file__).resolve().parents[1]

def main():
 src=ROOT/'stage03_response/manual';out=ROOT/'stage07_summary/manual';out.mkdir(parents=True,exist_ok=True)
 idx=pd.read_csv(ROOT/'stage02_normalized/manual/POOL_INDEX.csv');idx=idx[idx.domain.eq('ordinary_manual_main')]
 curves=pd.read_csv(src/'POOL_K_STATISTICS.csv.gz');curves=curves[curves.pool_id.isin(idx.pool_id)]
 all_on=pd.read_csv(src/'PLATEAU_SENSITIVITY.csv.gz');all_on=all_on[all_on.pool_id.isin(idx.pool_id)]
 primary=all_on[all_on.primary_rule];q=primary[primary.metric.eq('B8L2_mean')]
 env=pd.read_csv(src/'TAIL_ENVELOPES.csv.gz');env=env[env.pool_id.isin(idx.pool_id)]
 path=pd.read_csv(src/'PATH_CHANGE_SUMMARY.csv.gz');path=path[path.pool_id.isin(idx.pool_id)]
 transient=pd.read_csv(src/'TRANSIENT_FLAT_THEN_CHANGE.csv.gz');transient=transient[transient.pool_id.isin(idx.pool_id)]
 panel_rows=[]
 for cap,windows in [(20,[(3,6),(6,10),(10,20)]),(30,[(3,6),(6,10),(10,20),(20,30)]),(35,[(3,6),(6,10),(10,20),(20,30),(30,35)])]:
  ids=idx[idx.N>=cap].pool_id;d=curves[curves.pool_id.isin(ids)]
  for a,b in windows:
   x=d[d.k.eq(a)].merge(d[d.k.eq(b)],on='pool_id',suffixes=('_from','_to'))
   for met,(cnt,tol) in MEASURES.items():
    z=pd.DataFrame({'pool_id':x.pool_id,'image':x.image_from,'building':x.building_from,'delta':x[met+'_to']-x[met+'_from']})
    z.loc[x[cnt+'_from'].lt(64)|x[cnt+'_to'].lt(64),'delta']=np.nan
    panel_rows.append(dict(panel_min_N=cap,k_from=a,k_to=b,metric=met,**summarize_values(z,'delta',tol)))
 ar.write_csv(pd.DataFrame(panel_rows),out/'PRIMARY_SELECTED_PANEL_CHANGES.csv')
 sensitivity=[]
 for dl in ['All','Easy','Medium','Hard']:
  d=all_on if dl=='All' else all_on[all_on.difficulty_en.eq(dl)]
  for (metric,tol,minvalid),g in d.groupby(['metric','tolerance','minimum_valid_paths']):
   f=g[g.onset_k.notna()]
   sensitivity.append(dict(difficulty_en=dl,metric=metric,tolerance=tol,minimum_valid_paths=minvalid,pools=len(g),buildings=g.building.nunique(),
     adequate_N_pools=int(g.N.ge(8).sum()),observed_onsets=len(f),onset_median=f.onset_k.median(),onset_p10=f.onset_k.quantile(.1),onset_p90=f.onset_k.quantile(.9),
     onset_at_or_before10=int(f.onset_k.le(10).sum()),onset_at_or_before20=int(f.onset_k.le(20).sum()),near_full_onsets=int(f.near_exhaustion_onset.eq(True).sum()),
     point_onset_MC_upper_within=int(f.onset_MC_class.eq('upper_bound_within_tolerance').sum()),point_onset_MC_band_crosses=int(f.onset_MC_class.eq('band_crosses_tolerance').sum())))
 ar.write_csv(pd.DataFrame(sensitivity),out/'TOLERANCE_SUPPORT_SENSITIVITY.csv')
 precision=[]
 for (pool,metric),g in env[env.metric.isin(['B8L2_mean','B8L2_p10'])].groupby(['pool_id','metric']):
  g=g.sort_values('k');mm=primary[primary.pool_id.eq(pool)&primary.metric.eq(metric)].iloc[0]
  for tol in [1.,2.,3.,5.]:
   supported=g[g.primary_support_valid.eq(True)&g.adequate_followup.eq(True)]
   available=supported[supported.MC_full_tail_band_available.eq(True)]
   possible=available[available.MC_range_lower.le(tol+ar.TOL)];confirmed=available[available.MC_range_upper.le(tol+ar.TOL)]
   point=supported[supported.tail_range.le(tol+ar.TOL)]
   precision.append({**mm[ar.META].to_dict(),'metric':metric,'tolerance':tol,'minimum_valid_paths':64,
      'point_onset_k':point.k.min() if len(point) else np.nan,
      'earliest_MC_compatible_k':possible.k.min() if len(possible) else np.nan,
      'earliest_MC_upper_within_k':confirmed.k.min() if len(confirmed) else np.nan,
      'adequate_tail_candidates':len(supported),'MC_band_available_tail_candidates':len(available),
      'MC_state':'no_adequate_supported_tail' if not len(supported) else 'no_matching_simultaneous_band' if not len(available) else 'some_tail_certified' if len(confirmed) else 'no_adequate_tail_upper_bound_within_tolerance',
      'precision_scope':'2000 saved whole-path bootstrap simultaneous band; fixed existing worker pool, not new buildings'})
 precision=pd.DataFrame(precision);ar.write_csv(precision,out/'MC_ONSET_BRACKETS.csv')
 precsum=[]
 for dl in ['All','Easy','Medium','Hard']:
  dd=precision if dl=='All' else precision[precision.difficulty_en.eq(dl)]
  for (met,tol),g in dd.groupby(['metric','tolerance']):
   precsum.append(dict(difficulty_en=dl,metric=met,tolerance=tol,pools=len(g),point_onsets=int(g.point_onset_k.notna().sum()),
     any_adequate_band_candidates=int(g.MC_band_available_tail_candidates.gt(0).sum()),
     confirmed_later_onsets=int(g.earliest_MC_upper_within_k.notna().sum()),confirmed_onset_median=g.earliest_MC_upper_within_k.median(),
     median_delay_to_confirm=(g.earliest_MC_upper_within_k-g.point_onset_k).median()))
 ar.write_csv(pd.DataFrame(precsum),out/'MC_ONSET_BRACKET_SUMMARY.csv')
 joined=env.merge(q[q.onset_k.notna()][['pool_id','onset_k']],on='pool_id');joined=joined[joined.k.eq(joined.onset_k)]
 ar.write_csv(joined,out/'OTHER_DIMENSIONS_AT_MEAN_Q_ONSET.csv')
 jsummary=[]
 for met,g in joined.groupby('metric'):
  jsummary.append(dict(metric=met,mean_Q_onset_pools=len(g),tail_range_exceeds_own_tolerance=int(g.tail_range.gt(g.primary_tolerance+ar.TOL).sum()),unsupported_tail=int((~g.primary_support_valid).sum())))
 tr=[]
 for dl in ['All','Easy','Medium','Hard']:
  d=transient if dl=='All' else transient[transient.difficulty_en.eq(dl)]
  for start in [3,10,20]:
   dd=d[d.start_k.ge(start)]
   for (metric,reason),g in dd.groupby(['metric','change_reason']):
    tr.append(dict(difficulty_en=dl,start_k_at_least=start,metric=metric,reason=reason,images=g.image.nunique(),buildings=g.building.nunique(),overlapping_windows=len(g),
      earliest_later_change=g.first_later_change_k.min(),latest_later_change=g.first_later_change_k.max()))
 ar.write_csv(pd.DataFrame(tr),out/'TRANSIENT_FLAT_IMAGE_BUILDING_SUPPORT.csv')
 late=[]
 for start in [10,20,25,30]:
  for step in [1,2]:
   dd=path[path.metric.eq('B8L2')&path.k_from.ge(start)&path.k_to.sub(path.k_from).eq(step)&path.interval_labels.str.contains('adjacent_')]
   for pid,g in dd.groupby('pool_id'):
    v=g[g.both_valid_n.ge(64)];r=g.iloc[0]
    late.append(dict(pool_id=pid,image=r.image,building=r.building,difficulty_en=r.difficulty_en,N=r.N,late_start_k=start,step=step,
      transition_cells=len(g),valid_transition_cells=len(v),max_gt5_probability=v.absolute_jump_gt5_rate.max(),max_gt10_probability=v.absolute_jump_gt10_rate.max(),
      worst_k_from=v.loc[v.absolute_jump_gt5_rate.idxmax(),'k_from'] if len(v) else np.nan,worst_k_to=v.loc[v.absolute_jump_gt5_rate.idxmax(),'k_to'] if len(v) else np.nan,
      max_mean_abs_delta=v.mean_abs_delta.max(),max_abs_mean_delta=v.mean_delta.abs().max(),
      max_from_only_rate=(g.from_only_valid_n/g.pair_rows).max(),max_to_only_rate=(g.to_only_valid_n/g.pair_rows).max()))
 late=pd.DataFrame(late);ar.write_csv(late,out/'LATE_JUMP_PRIMARY_CANDIDATES.csv')
 late_summary=[]
 for (start,step),g in late.groupby(['late_start_k','step']):
  v=g[g.valid_transition_cells>0]
  late_summary.append(dict(late_start_k=start,step=step,capacity_images=len(g),capacity_buildings=g.building.nunique(),valid_images=len(v),
    images_with_transition_at_least10pct_gt5=int(v.max_gt5_probability.ge(.1).sum()),images_with_transition_at_least25pct_gt5=int(v.max_gt5_probability.ge(.25).sum()),
    images_with_transition_at_least10pct_gt10=int(v.max_gt10_probability.ge(.1).sum())))
 ar.write_csv(pd.DataFrame(late_summary),out/'LATE_JUMP_PRIMARY_SUMMARY.csv')
 full=curves[curves.k.eq(curves.N)]
 facts={'primary_images':len(idx),'primary_buildings':idx.building.nunique(),'no_onset_reason_B8_mean':q[q.onset_k.isna()].reason.value_counts().to_dict(),
  'early_mean_onset_counts_by_difficulty':q.groupby('difficulty_en').apply(lambda g:pd.Series({'images':len(g),'adequate_N':int(g.N.ge(8).sum()),'onset_by10':int(g.onset_k.le(10).sum()),'onset_by20':int(g.onset_k.le(20).sum())}),include_groups=False).reset_index().to_dict('records'),
  'selected_fixed_panels':panel_rows,'other_dimensions_at_mean_Q_onset':jsummary,'MC_onset_brackets':precsum,
  'sensitivity':[r for r in sensitivity if r['difficulty_en']=='All' and r['metric'] in ['B8L2_mean','B8L2_p10','B8L2_sd','complete_evaluable_rate']],
  'transient_meanQ':[r for r in tr if r['metric']=='B8L2_mean'],'late_jumps':late_summary,
  'actual_full_Q_unavailable':full[full.B8L2_valid_n.eq(0)][['pool_id','image','building','N','complete_evaluable_rate','quality_available_rate']].to_dict('records'),
  'new_fusion':False,'new_paths':False}
 (out/'DIAGNOSTIC_FACTS.json').write_text(json.dumps(ar.json_clean(facts),ensure_ascii=False,indent=2,allow_nan=False))
 print(json.dumps({'primary_images':len(idx),'MC_tables_rows':len(precision),'sensitivity_rows':len(sensitivity),'output':str(out)}),flush=True)

if __name__=='__main__':main()
