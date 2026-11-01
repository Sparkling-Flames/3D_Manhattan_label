#!/usr/bin/env python3
"""Validate multiplicity U against expanded path pairs and prior matching."""
from pathlib import Path
import csv,gzip,json
import numpy as np
import pandas as pd
import doorway_exact_geometry_U as eu
import doorway_geometry_response as dg
import analyze_response as ar
from summarize_response import summarize_values

ROOT=Path(__file__).resolve().parents[1]

def main():
 out=ROOT/'stage04_geometry/doorway_exact_U';method=json.loads((out/'METHOD.json').read_text());assert method['all_pool_run']
 d=pd.read_csv(out/'GEOMETRY_U_CURVES.csv.gz');idx=pd.read_csv(ROOT/'stage02_normalized/doorway/POOL_INDEX.csv')
 assert not d.duplicated(['pool_id','k','metric']).any()
 expected=int(sum(max(0,int(x)-2) for x in idx.N));assert d[['pool_id','k']].drop_duplicates().shape[0]==expected
 assert (d.valid_path_pairs==d.valid_paths*(d.valid_paths-1)//2).all()
 assert d.loc[d.valid_path_pairs.eq(0),'mean'].isna().all()
 # A compact analytic repeated-state check: two paths have state A, one B.
 s=eu.weighted_stats(np.array([1.]),np.array([2]),1,3);assert abs(s['mean']-2/3)<1e-15
 # Expand one real small finite pool to all 256 path-index pairs. The full
 # expansion is validation, not a new source of independent observations.
 pid='2t7WUuJeko7-07__manual__space2';r=idx[idx.pool_id.eq(pid)].iloc[0]
 source=ar.input_file(r.to_dict(),ROOT);raw=pd.read_csv(source);raw=raw[raw.k.eq(3)]
 cat,geo,valid,cent,errors=eu.catalog(r.image);ii=cat.attrs['source_lookup'].reindex(raw.endpoint_source_key).to_numpy(int);ii=ii[valid[ii]]
 a,b=np.triu_indices(len(ii),1);values=[]
 for lo in range(0,len(a),8192):
  hi=min(len(a),lo+8192);pa,pb=geo[ii[a[lo:hi]]],geo[ii[b[lo:hi]]]
  inter=dg.shapely.area(dg.shapely.intersection(pa,pb));union=dg.shapely.area(pa)+dg.shapely.area(pb)-inter
  values.append(np.clip(1-inter/union,0,1))
 brute=float(np.concatenate(values).mean()) if values else np.nan
 exact=float(d[d.pool_id.eq(pid)&d.k.eq(3)&d.metric.eq('floor_distance')]['mean'].iloc[0])
 assert abs(brute-exact)<1e-12,(brute,exact)
 full=d[d.full_pool.eq(True)&d['mean'].notna()]
 # A physical full team can theoretically retain multiple stored geometry
 # states; the actual result must verify the single state before zero is expected.
 one=full[full.unique_geometry_states.eq(1)]
 assert one['mean'].abs().le(1e-12).all()
 matching=pd.read_csv(ROOT/'stage04_geometry/doorway/MATCHING_SENSITIVITY.csv.gz')
 m=matching.rename(columns={'k_from':'k','mean':'matching_mean','valid_pairs':'matching_valid_pairs'})
 m=m.merge(d[['pool_id','k','metric','mean','valid_paths','valid_path_pairs']],on=['pool_id','k','metric'],validate='many_to_one')
 m['matching_minus_exact']=m.matching_mean-m['mean'];m['abs_matching_error']=m.matching_minus_exact.abs()
 ar.write_csv(m,out/'MATCHING_VS_EXACT_U.csv.gz')
 summary=[]
 for met,g in m.groupby('metric'):
  v=g[g.abs_matching_error.notna()]
  summary.append(dict(metric=met,matching_cells=len(g),comparable_matching_cells=len(v),images=v.image.nunique(),pools=v.pool_id.nunique(),
    mean_absolute_matching_error=v.abs_matching_error.mean(),p90_absolute_matching_error=v.abs_matching_error.quantile(.9),
    maximum_absolute_matching_error=v.abs_matching_error.max(),
    matching_cells_abs_error_gt_0p05=int(v.abs_matching_error.gt(.05).sum()),matching_cells_abs_error_gt_0p1=int(v.abs_matching_error.gt(.1).sum())))
 ar.write_csv(pd.DataFrame(summary),out/'MATCHING_APPROXIMATION_ERROR_SUMMARY.csv')
 combined=pd.read_csv(ROOT/'stage04_geometry/doorway/GEOMETRY_PAIR_SUMMARY.csv.gz');combined=combined[combined.kind.eq('same_k_matching')]
 combined=combined.rename(columns={'k_from':'k','mean':'two_matching_mean','valid_pairs':'two_matching_valid_pairs'})
 combined=combined.merge(d[['pool_id','k','metric','mean','valid_paths','valid_path_pairs']],on=['pool_id','k','metric'],validate='many_to_one')
 combined['two_matching_minus_exact']=combined.two_matching_mean-combined['mean']
 ar.write_csv(combined,out/'TWO_MATCHINGS_COMBINED_VS_EXACT_U.csv.gz')
 screening_rows=[];screening_summary=[]
 floor=d[d.metric.eq('floor_distance')]
 for cap in [8,14,20,30,35]:
  before=idx[idx.domain.eq('doorway_before')&idx.N.ge(cap)];after=idx[idx.domain.eq('doorway_after')&idx.N.ge(cap)]
  images=set(before.image)&set(after.image)
  if not images:continue
  for k in [3,6,8,10,14,20,30,35]:
   if k>cap:continue
   zz=floor[floor.image.isin(images)&floor.k.eq(k)&floor.domain.isin(['doorway_before','doorway_after'])]
   xx=zz[zz.domain.eq('doorway_before')].merge(zz[zz.domain.eq('doorway_after')],on='image',suffixes=('_before','_after'))
   zz=pd.DataFrame({'pool_id':xx.pool_id_before+'|'+xx.pool_id_after,'image':xx.image,'building':xx.building_before,
    'delta':xx['mean_after']-xx['mean_before'],'before_value':xx['mean_before'],'after_value':xx['mean_after'],
    'before_N':xx.N_before,'after_N':xx.N_after,'before_valid_paths':xx.valid_paths_before,'after_valid_paths':xx.valid_paths_after})
   zz.loc[xx.valid_paths_before.lt(64)|xx.valid_paths_after.lt(64),'delta']=np.nan
   zz['panel_min_N']=cap;zz['k']=k;screening_rows.append(zz)
   screening_summary.append(dict(panel_min_N=cap,k=k,minimum_valid_paths=64,**summarize_values(zz,'delta',.05)))
 ar.write_csv(pd.concat(screening_rows,ignore_index=True),out/'SCREENING_FIXED_PANEL_IMAGE_COMPARISON.csv.gz')
 ar.write_csv(pd.DataFrame(screening_summary),out/'SCREENING_FIXED_PANEL_COMPARISON.csv')
 bad=[];n=0
 for f in out.rglob('*.csv.gz'):
  try:
   with gzip.open(f,'rt',encoding='utf-8-sig',newline='') as h:
    reader=csv.reader(h);header=next(reader,[])
    for row in reader:
     if len(row)!=len(header):raise ValueError('column count mismatch')
   n+=1
  except Exception as e:bad.append(dict(file=str(f.relative_to(ROOT)),error=str(e)))
 assert not bad,bad
 receipt={'expected_all_pool_k_cells':expected,'actual_pool_k_cells':d[['pool_id','k']].drop_duplicates().shape[0],
  'metric_rows':len(d),'denominator_identity_all_pass':True,'zero_pairs_missing_mean_all_pass':True,
  'analytic_repeated_state_example_mean':s['mean'],'expanded_real_check':{'pool_id':pid,'k':3,'valid_paths':len(ii),'path_pairs':len(a),'brute_force_mean':brute,'multiplicity_U':exact,'absolute_difference':abs(brute-exact)},
  'valid_full_pool_one_state_metric_rows':len(one),'valid_full_one_state_U_zero':True,'gzip_read_to_eof':n,'bad_gzip':bad,
  'comparison_count_note':'sum of distinct state-pair evaluations within each pool/k; cross-pool repeats may recur, not globally unique geometry pairs',
  'validation_did_not_change_fusion_or_Q':True,'validation_expanded_repeated_pair_evaluations':len(a),
  'adopted_result':'exact path-frequency U; original two matchings retained solely as approximation sensitivity'}
 (out/'VALIDATION_AND_COMPARISON.json').write_text(json.dumps(ar.json_clean(receipt),ensure_ascii=False,indent=2,allow_nan=False))
 print(json.dumps(ar.json_clean(receipt),ensure_ascii=False),flush=True)

if __name__=='__main__':main()
