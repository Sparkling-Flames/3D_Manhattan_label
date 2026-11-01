#!/usr/bin/env python3
"""Linear vs inverse-CDF P10 on the SAME saved 256-path weighted samples.

This does not change the main adopted linear percentile. It does not use the
linear-percentile bootstrap bands for the inverse-CDF quantity. No new paths,
teams, quality scores, or fusion are computed.
"""
from pathlib import Path
import json
import numpy as np
import pandas as pd
import analyze_response as ar
from summarize_response import summarize_values

ROOT=Path(__file__).resolve().parents[1]

def main():
 src=ROOT/'stage03_response/manual';out=ROOT/'stage07_summary/p10_definition_sensitivity';out.mkdir(parents=True,exist_ok=True)
 idx=pd.read_csv(ROOT/'stage02_normalized/manual/POOL_INDEX.csv');idx=idx[idx.domain.eq('ordinary_manual_main')]
 c=pd.read_csv(src/'POOL_K_STATISTICS.csv.gz');c=c[c.pool_id.isin(idx.pool_id)&c.k.ge(3)]
 base=[x for x in ar.specifications() if x['metric']=='B8L2_p10'][0]
 spec={**base,'metric':'B8L2_p10_inverse_cdf'}
 ar.specifications=lambda:[spec]
 all_on=[];envelopes=[]
 for row in idx.to_dict('records'):
  g=c[c.pool_id.eq(row['pool_id'])];meta=ar.get_meta(row,g)
  env,onsets,transient,bcheck=ar.tail_analysis(g,meta,{})
  assert bcheck.empty
  all_on.append(onsets);envelopes.append(env)
 all_on=pd.concat(all_on,ignore_index=True);envelopes=pd.concat(envelopes,ignore_index=True)
 primary=all_on[all_on.primary_rule].copy()
 ar.write_csv(all_on,out/'INVERSE_CDF_ONSET_SENSITIVITY.csv.gz');ar.write_csv(primary,out/'INVERSE_CDF_PRIMARY_ONSETS.csv')
 ar.write_csv(envelopes,out/'INVERSE_CDF_TAIL_ENVELOPES.csv.gz')
 linear=pd.read_csv(src/'PRIMARY_SMALL_CHANGE_ONSETS.csv');linear=linear[linear.pool_id.isin(idx.pool_id)&linear.metric.eq('B8L2_p10')]
 common=['pool_id','image','building','N','difficulty_en'];vals=['onset_k','onset_k_fraction','first_small_range_without_followup_gate','onset_tail_range','reason','actual_full_value']
 compare=linear[common+vals].merge(primary[['pool_id']+vals],on='pool_id',validate='one_to_one',suffixes=('_linear','_inverse_cdf'))
 compare['onset_detection_agrees']=compare.onset_k_linear.notna().eq(compare.onset_k_inverse_cdf.notna())
 compare['both_onsets_available']=compare.onset_k_linear.notna()&compare.onset_k_inverse_cdf.notna()
 compare['onset_inverse_minus_linear']=compare.onset_k_inverse_cdf-compare.onset_k_linear
 compare['same_onset_or_same_missing']=(compare.onset_k_linear.eq(compare.onset_k_inverse_cdf))|(~compare.onset_k_linear.notna()&~compare.onset_k_inverse_cdf.notna())
 ar.write_csv(compare,out/'P10_DEFINITION_ONSET_COMPARISON.csv')
 curves=c[common+['k','k_fraction','B8L2_valid_n','B8L2_p10','B8L2_p10_inverse_cdf']].copy()
 curves['inverse_minus_linear']=curves.B8L2_p10_inverse_cdf-curves.B8L2_p10
 ar.write_csv(curves,out/'P10_DEFINITION_PER_K_COMPARISON.csv.gz')
 panel=idx[idx.N.ge(30)].pool_id
 a=c[c.pool_id.isin(panel)&c.k.eq(20)];b=c[c.pool_id.isin(panel)&c.k.eq(30)]
 z=a.merge(b,on='pool_id',suffixes=('_20','_30'),validate='one_to_one')
 image=pd.DataFrame({'pool_id':z.pool_id,'image':z.image_20,'building':z.building_20,'N':z.N_20,'k_from':20,'k_to':30,
  'valid_paths_20':z.B8L2_valid_n_20,'valid_paths_30':z.B8L2_valid_n_30,
  'P10_linear_20':z.B8L2_p10_20,'P10_linear_30':z.B8L2_p10_30,
  'P10_inverse_cdf_20':z.B8L2_p10_inverse_cdf_20,'P10_inverse_cdf_30':z.B8L2_p10_inverse_cdf_30})
 for name in ['linear','inverse_cdf']:
  image[f'delta_{name}']=image[f'P10_{name}_30']-image[f'P10_{name}_20']
  image.loc[image.valid_paths_20.lt(64)|image.valid_paths_30.lt(64),f'delta_{name}']=np.nan
 image['delta_inverse_minus_linear']=image.delta_inverse_cdf-image.delta_linear
 ar.write_csv(image,out/'FIXED171_20_30_IMAGE_COMPARISON.csv')
 summary=[]
 for name in ['linear','inverse_cdf']:
  summary.append(dict(percentile_definition=name,k_from=20,k_to=30,panel='ordinary_manual_main_N_ge30',**summarize_values(image,'delta_'+name,2.)))
 ar.write_csv(pd.DataFrame(summary),out/'FIXED171_20_30_SUMMARY.csv')
 strata=[]
 for name,df in [('linear',linear),('inverse_cdf',primary)]:
  for diff in ['All','Easy','Medium','Hard']:
   g=df if diff=='All' else df[df.difficulty_en.eq(diff)]
   strata.append(dict(definition=name,difficulty_en=diff,images=len(g),observed_onsets=int(g.onset_k.notna().sum()),
     median_onset=g.onset_k.median(),onset_by10=int(g.onset_k.le(10).sum()),onset_by20=int(g.onset_k.le(20).sum())))
 ar.write_csv(pd.DataFrame(strata),out/'ONSET_DEFINITION_SUMMARY.csv')
 target='wc2JMjhGNzB-46';case=curves[curves.image.eq(target)]
 ar.write_csv(case,out/'WC2_46_PATH_P10_DEFINITIONS.csv')
 facts={'scope':'206 ordinary Manual main images; existing path-weighted k>=3 scalar curves',
  'main_definition':'linear empirical P10 remains the adopted primary result',
  'sensitivity_definition':'inverse empirical CDF, sorted finite scores at ceil(0.1*n), retaining path frequencies',
  'same_rules':{'quality_tail_tolerance':2,'minimum_valid_paths':64,'followup':'max(5,ceil(.15N))','minimum_pool_N':8},
  'inverse_bootstrap':'not computed; old linear P10 bootstrap bands are not reused',
  'onset_summary':strata,'onset_detection_agrees_images':int(compare.onset_detection_agrees.sum()),
  'both_onsets_available':int(compare.both_onsets_available.sum()),'same_onset_or_same_missing_images':int(compare.same_onset_or_same_missing.sum()),
  'onset_changed_images':compare[~compare.same_onset_or_same_missing].to_dict('records'),
  'fixed171_20_30':summary,'fixed171_sign_agreement_images':int(np.sign(image.delta_linear).eq(np.sign(image.delta_inverse_cdf)).sum()),
  'wc2_46_k27':case[case.k.eq(27)].to_dict('records'),'wc2_46_onset':compare[compare.image.eq(target)].to_dict('records'),
  'largest_within_sample_percentile_difference':curves.loc[curves.inverse_minus_linear.abs().nlargest(8).index].to_dict('records'),
  'new_fusion':0,'new_person_paths':0,'new_quality_scores':0}
 (out/'FACTS.json').write_text(json.dumps(ar.json_clean(facts),ensure_ascii=False,indent=2,allow_nan=False))
 print(json.dumps(ar.json_clean({'onset_summary':strata,'same_onset_or_same_missing_images':facts['same_onset_or_same_missing_images'],'fixed171_20_30':summary,'wc2_46_k27':facts['wc2_46_k27'],'wc2_46_onset':facts['wc2_46_onset']}),ensure_ascii=False),flush=True)

if __name__=='__main__':main()
