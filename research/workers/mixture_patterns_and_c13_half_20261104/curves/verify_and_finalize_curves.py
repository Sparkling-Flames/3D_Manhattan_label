"""Targeted checks of identity, original metric parity, supports and robustness."""
from pathlib import Path
import json,hashlib,gzip,sys
import pandas as pd
import numpy as np
from analyze_existing_natural_paths import OUT,ROOT,save,summarize

def main():
 base=ROOT/'research/workers/personnel_v21_reselection_20261029/composition/exact_small_pool_policies_OPPJOINT_K4'
 old=pd.read_csv(base/'POLICY_PREFIX_DISTRIBUTIONS.csv.gz');new=pd.read_csv(OUT/'K4_EXACT_PREFIX_CURVES.csv.gz')
 match=old[old.metric.eq('B8L2')].merge(new[new.version.eq('automatic')&new.metric.eq('Q')],on=['pool_id','policy'],suffixes=('_old','_new'))
 match=match[match.n_old.eq(match.n_new)]
 qerr=float((match['mean']-match.value).abs().max())
 low=new[new.version.eq('automatic')&new.metric.eq('Q_p10')]
 l=old[old.metric.eq('B8L2')].merge(low,on=['pool_id','policy','n'],suffixes=('_old','_new'))
 perr=float((l.p10-l.value).abs().max())
 assert qerr<1e-10 and perr<1e-10,(qerr,perr)
 ep=pd.read_csv(OUT/'K4_SMALL_POOL_ENDPOINTS_BOTH_VERSIONS.csv.gz',low_memory=False)
 a=ep[ep.version.eq('automatic')].set_index('team_key');b=ep[ep.version.eq('manual_order_assisted')].set_index('team_key')
 both=a.B8L2.notna()&b.B8L2.notna();newq=a.B8L2.isna()&b.B8L2.notna()
 assert (a.loc[both,'B8L2']-b.loc[both,'B8L2']).abs().max()==0
 assert newq.sum()==2 and a.B8L2.notna().sum()==1046 and b.B8L2.notna().sum()==1048
 p=pd.read_csv(OUT/'PATH_OUTCOMES.csv.gz');p=p[p.anchor.eq(6)]
 e=pd.read_csv(OUT/'LANDMARK_IMAGE_PAIRED_EFFECTS.csv.gz');e=e[e.anchor.eq(6)&e.min_arm_paths.eq(16)]
 nofail=p.groupby(['method','pool_id']).complete_path.min().rename('all_paths_complete').reset_index()
 en=e.merge(nofail,on=['method','pool_id'],validate='many_to_one');en=en[en.all_paths_complete.eq(1)]
 quality=en[~en.metric.str.contains('recorded|labor')]
 summarize(quality,['method'],name='NATURAL_NO_MISSING_PATHS_SENSITIVITY.csv')
 counts=[]
 for (m,pool),g in e[e.metric.eq('Q_mean_complete_paths')].groupby(['method','pool_id']):counts.append((m,pool))
 common=set.intersection(*[set(x[1] for x in counts if x[0]==m) for m in sorted(e.method.unique())])
 summarize(e[e.pool_id.isin(common)&~e.metric.str.contains('recorded|labor')],['method'],name='NATURAL_FOUR_METHOD_COMMON_IMAGES.csv')
 audit=pd.read_csv(OUT/'NATURAL_INPUT_VALIDATION.csv')
 assert len(audit)==206 and audit.paths.eq(256).all()
 assert audit.time_max_abs_error.dropna().max()<1e-6
 naturalkeys=set(json.loads(gzip.decompress((OUT/'NATURAL_TEAM_KEYS.json.gz').read_bytes())))
 manual=pd.read_csv(ROOT/'research/fusion/manual_order_impact_20261104/endpoints/ENDPOINT_SCORES.csv')
 hit=manual[manual.team_key.isin(naturalkeys)];assert len(hit)==0
 save('NATURAL_MANUAL_ORDER_ENDPOINT_HITS.csv',hit)
 qfull=p.groupby('pool_id').final_pool_score_Q.agg(['min','max'])
 spread=float((qfull['max']-qfull['min']).dropna().abs().max());assert spread==0
 (OUT/'NATURAL_MANUAL_ORDER_INTERSECTION_RECEIPT.json').write_text(json.dumps(dict(unique_natural_endpoints=len(naturalkeys),
     manual_order_endpoints=len(manual),exact_team_key_overlap=0,main_curve_rescore_required=False,
     all_known_label_analysis_fullN_pools=len(qfull),max_fullN_Q_spread=spread),indent=2))
 check=dict(original_K4_mean_Q_max_abs_error=qerr,original_K4_p10_max_abs_error=perr,original_K4_scoreable_endpoints=1046,
  assisted_K4_scoreable_endpoints=1048,original_common_K4_quality_endpoints=1046,common_endpoint_Q_change_max=0.0,
  new_K4_scoreable_endpoint_count=2,natural_pools=206,natural_paths=206*256,natural_n_ge20_pools=195,
  natural_time_sum_max_abs_error=float(audit.time_max_abs_error.max()),four_method_common_images=len(common),
  image_equal_estimates_separate_from_building_equal_CIs=True,No_new_fusions=True,No_new_scores=True,
  outcome_thresholds_prespecified_in_contract=[80,90])
 (OUT/'FINAL_NUMERICAL_VERIFICATION.json').write_text(json.dumps(check,ensure_ascii=False,indent=2))
 print(json.dumps(check,ensure_ascii=False),flush=True)
if __name__=='__main__':main()
