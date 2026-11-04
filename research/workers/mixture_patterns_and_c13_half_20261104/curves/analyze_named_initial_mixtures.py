"""Named first-six class mixtures, conditional on existing uniform random paths.
These compare exact class sets, not fixed within-set proportions or causal replacement.
All contrasts below were listed before computing their outcome summaries.
"""
from pathlib import Path
import json
import pandas as pd
import numpy as np
from analyze_existing_natural_paths import OUT,ROOT,STRATA,METHODS,save,summarize,truth
CONTRASTS={
 'TARGET_DSTRUCT_K3':[('C1+C3','C1+C2'),('C2+C3','C1+C2'),('C1+C2+C3','C1+C2')],
 'RFUSE_GEOM_K2':[('C1+C2','C1'),('C1+C2','C2')],
 'OPPJOINT_K3':[('C1+C3','C1+C2'),('C2+C3','C1+C2'),('C1+C2+C3','C1+C2')],
 'OPPJOINT_K4':[('C1+C2+C4','C1+C2+C3'),('C1+C4','C1+C2'),('C1+C4','C1+C3'),('C1+C2+C3+C4','C1+C2+C3')]
}

def main():
 labels=pd.read_csv(ROOT/'research/workers/current_class_interpretation_20261104/basis/WORKER_LABELS_ALL_LOBO.csv.gz')
 labels=labels[truth(labels.known)&labels.heldout_building.ne('ALL')]
 lm={(m,b):dict(zip(g.worker_id,g.class_id)) for (m,b),g in labels.groupby(['method','heldout_building'])}
 inv=pd.read_csv(OUT/'NATURAL_SOURCE_POOLS.csv');inv=inv[inv.pool_n.ge(20)]
 tags=[]
 for r in inv.itertuples():
  d=pd.read_csv(ROOT/r.path,usecols=['path_id','stratum','k','member_workers']);d=d[d.stratum.isin(STRATA)&d.k.eq(6)]
  assert len(d)==256
  for m in METHODS:
   ml=lm.get((m,r.building),{})
   for x in d.itertuples():
    ls=[ml.get(w,'unknown') for w in x.member_workers.split('|')]
    tags.append(dict(pool_id=r.pool_id,method=m,anchor=6,path_key=x.stratum+'::'+x.path_id,
      class_set='+'.join(sorted(set(ls))),class_counts='|'.join(f'{k}:{ls.count(k)}' for k in sorted(set(ls))),
      highest_class_count=ls.count(METHODS[m]),member_workers=x.member_workers,all_known=('unknown' not in ls)))
 tags=pd.DataFrame(tags);save('INITIAL_SIX_CLASS_MIXTURES.csv.gz',tags)
 paths=pd.read_csv(OUT/'PATH_OUTCOMES.csv.gz');paths=paths[paths.anchor.eq(6)]
 z=paths.merge(tags,on=['pool_id','method','anchor','path_key'],validate='one_to_one');assert z.all_known.all()
 metrics=['Q_mean_complete_paths','complete_path','score_available_fraction','Q20','D10_20','ever_Q80_by20','ever_Q90_by20',
  'ever_Q80_prefix_probability_area','ever_Q90_prefix_probability_area','sustained_Q80_prefix_probability_area','sustained_Q90_prefix_probability_area',
  'first_Q80_n_given_reached','first_Q90_n_given_reached','first_Q80_recorded_seconds_given_reached','first_Q90_recorded_seconds_given_reached',
  'ever_Q80_by_50pct_full_recorded_labor','ever_Q90_by_50pct_full_recorded_labor']
 effects=[];support=[]
 for (method,pool),g in z.groupby(['method','pool_id']):
  row=g.iloc[0];meta=dict(method=method,pool_id=pool,image=row.image,building=row.building,difficulty=row.difficulty,
      pool_n=row.pool_n,time_source=row.time_source)
  for cs,h in g.groupby('class_set'):
   support.append(dict(meta,class_set=cs,paths=len(h),mean_highest_class_count=h.highest_class_count.mean(),Q_mean_complete_paths=h.Q_mean_complete_paths.mean()))
  for with_set,without_set in CONTRASTS[method]:
   a=g[g.class_set.eq(with_set)];b=g[g.class_set.eq(without_set)]
   for minimum in [8,16]:
    if min(len(a),len(b))<minimum:continue
    for metric in metrics:
     effects.append(dict(meta,with_set=with_set,without_set=without_set,min_arm_paths=minimum,
      paths_with=len(a),paths_without=len(b),metric=metric,with_value=a[metric].mean(),without_value=b[metric].mean(),
      effect=a[metric].mean()-b[metric].mean()))
 e=pd.DataFrame(effects);save('NAMED_MIXTURE_PAIRED_IMAGE_EFFECTS.csv.gz',e);save('NAMED_MIXTURE_CLASS_SET_SUPPORT.csv.gz',pd.DataFrame(support))
 group=['method','with_set','without_set','min_arm_paths']
 quality=e[~e.metric.str.contains('recorded|labor')]
 summarize(quality,group,name='NAMED_MIXTURE_SUMMARY.csv')
 summarize(quality,group+['difficulty'],name='NAMED_MIXTURE_DIFFICULTY_SUMMARY.csv')
 summarize(e[e.metric.str.contains('recorded|labor')],group+['time_source'],name='NAMED_MIXTURE_RECORDED_LABOR_SUMMARY.csv')
 coverage=[]
 for method,contrasts in CONTRASTS.items():
  for with_set,without_set in contrasts:
   for minimum in [8,16]:
    h=e[e.method.eq(method)&e.with_set.eq(with_set)&e.without_set.eq(without_set)&e.min_arm_paths.eq(minimum)]
    coverage.append(dict(method=method,with_set=with_set,without_set=without_set,min_arm_paths=minimum,
     registered_images=h.image.nunique(),registered_buildings=h.building.nunique(),
     Q_complete_path_images=h[h.metric.eq('Q_mean_complete_paths')&h.effect.notna()].image.nunique(),
     status='supported' if len(h) else 'no_image_has_both_named_class_sets_with_minimum_saved_path_count'))
 save('NAMED_MIXTURE_ALL_PLANNED_SUPPORT_COUNTS.csv',pd.DataFrame(coverage))
 (OUT/'NAMED_MIXTURE_RECEIPT.json').write_text(json.dumps(dict(contrasts=CONTRASTS,anchor=6,window='6 through20',
  descriptive_class_set_comparison=True,fixed_proportions=False,fixed_members=False,causal_priority_validation=False,
  all_registered_paths_preserved=True,min_arm_paths_primary=16,min_arm_paths_sensitivity=8),ensure_ascii=False,indent=2))
 print('Named mixtures complete',len(e),'paired metric rows',flush=True)
if __name__=='__main__':main()
