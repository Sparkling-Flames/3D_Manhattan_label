#!/usr/bin/env python3
"""Reuse previously computed raw annotation distances with new frozen labels."""
import os
for v in ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS'):os.environ[v]='1'
import pandas as pd
from discover_cross_condition import HERE,PREVIOUS,CONDITIONS,PREFIX,FAMILIES,save,js,sha
from check_raw_geometric_similarity import aggregate

def main():
 freeze=sha(HERE/'LABEL_FREEZE.json');pairs_path=PREVIOUS/'RAW_GEOMETRIC_PAIRS.csv.gz'
 raw=pd.read_csv(pairs_path);labels=pd.read_csv(HERE/'CROSS_LABELS_LOBO.csv.gz')
 features=pd.read_csv(HERE/'FEATURES_LOBO.csv.gz');v3=pd.read_csv(PREVIOUS/'ALL_METHOD_LABELS_LOBO.csv.gz')
 summaries=[];byb=[];ledger=[]
 metrics=['bound_deg','bottom_deg','top_deg','floor_jaccard_difference','height_abslog','turn_absdiff','redundancy_absdiff','short_absdiff']
 for method in FAMILIES:
  for cond in CONDITIONS:
   p=raw[raw.condition.eq(cond)].copy();lab=labels[labels.method.eq(method)&labels.condition.eq(cond)]
   old=v3[v3.method.eq('V3_BEHAVIOR')&v3.condition.eq(cond)]
   for suffix in ['a','b']:
    keys={'heldout_building':'building_id','worker_id':'worker_'+suffix}
    ll=lab[['heldout_building','worker_id','coarse_label','fine_label','known']].rename(columns={**keys,'coarse_label':'coarse_'+suffix,'fine_label':'fine_'+suffix,'known':'known_'+suffix})
    p=p.merge(ll,on=['building_id','worker_'+suffix],validate='many_to_one')
    o=old[['heldout_building','worker_id','fine_label','known']].rename(columns={**keys,'fine_label':'old_'+suffix,'known':'old_known_'+suffix})
    p=p.merge(o,on=['building_id','worker_'+suffix],validate='many_to_one')
    ff=features[['heldout_building','worker_id',PREFIX[cond]+'_q_history']].rename(columns={**keys,PREFIX[cond]+'_q_history':'hist_q_'+suffix})
    p=p.merge(ff,on=['building_id','worker_'+suffix],validate='many_to_one')
   p=p[p.known_a&p.known_b&p.old_known_a&p.old_known_b].copy()
   p['hist_q_mean']=(p.hist_q_a+p.hist_q_b)/2;p['hist_q_diff']=abs(p.hist_q_a-p.hist_q_b)
   for tier in ['coarse','fine','fine_within_parent','old_own_behavior_fine']:
    z=p[p.coarse_a.eq(p.coarse_b)].copy() if tier=='fine_within_parent' else p
    col='fine' if tier.startswith('fine') else ('old' if tier=='old_own_behavior_fine' else 'coarse')
    within=z[col+'_a'].eq(z[col+'_b'])
    ledger.append(dict(method=method,condition=cond,tier=tier,known_pairs=len(z),same_count_pairs=int(z.same_count.sum()),same_class_pairs=int(within.sum()),different_class_pairs=int((~within).sum()),
     class_comparison_estimable=bool(within.any() and (~within).any())))
    for scheme in ['equal_count_source','equal_count_source_historyQ']:
     for metric in metrics:
      r=aggregate(z,within,scheme,metric)
      if r is None:continue
      s,b=r;meta=dict(method=method,condition=cond,tier=tier)
      summaries.append(dict(meta,**s));byb.append(b.assign(**meta,scheme=scheme,metric=metric))
   save(pd.DataFrame(summaries),'RAW_SIMILARITY_SUMMARY_CHECKPOINT.csv')
   print('raw distance reuse',method,cond,len(p),flush=True)
 save(pd.DataFrame(summaries),'RAW_SIMILARITY_SUMMARY.csv');save(pd.concat(byb,ignore_index=True),'RAW_SIMILARITY_BUILDINGS.csv.gz');save(pd.DataFrame(ledger),'RAW_SIMILARITY_OPPORTUNITIES.csv')
 assert freeze==sha(HERE/'LABEL_FREEZE.json')
 js('RAW_SIMILARITY_RECEIPT.json',dict(label_freeze_sha256=freeze,previous_distance_path=str(pairs_path),previous_distance_sha256=sha(pairs_path),reused_pairs=len(raw),
  new_geometry_computations=0,new_quality_scores=0,new_team_fusions=0,
  distance='frozen top/bottom angular distance with common cyclic alignment, continuous floor Jaccard; same point count comparisons; not fusion correspondence thresholds',
  support='same known-person raw pairs for cross classes and original own-condition behavior fine class; equal point count and source pair strata',
  q_adjustment='optional historical condition-specific q_history pair mean and absolute difference in 5-score bins; missing stays unknown',
  aggregation='same image/reference strata require both within/between; strata to image to building equal, building bootstrap CI',
  interpretation='similar raw annotations does not automatically mean correctness or interchangeable fusion effect'))
 print(pd.DataFrame(summaries).query("scheme=='equal_count_source' and metric=='bound_deg'").round(4).to_string(index=False))
if __name__=='__main__':main()
