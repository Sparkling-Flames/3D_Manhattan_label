#!/usr/bin/env python3
"""Same raw-distance summaries, vectorized and saved after every method.
Consumes completed raw-pool contrasts; does not calculate raw geometry,
re-fit labels, rescore quality, or run fusion.
"""
import os
for k in ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS'):os.environ[k]='1'
from pathlib import Path
import gzip,json,time
import numpy as np,pandas as pd
from compare_v21_raw_pairs import METRICS,save,dump
W=Path(__file__).resolve().parents[2];O=W/'raw_similarity';parts=O/'summary_shards';parts.mkdir(exist_ok=True)
table=pd.read_csv(O/'RAW_CLASS_DISTANCE_BY_POOL.csv.gz',low_memory=False)
key=['condition','layer','support','subset'];cols=[m+'_'+c for m in METRICS for c in ['within','cross','gap']]
start=time.monotonic();done=[]
for method,mg in table.groupby('method',sort=True):
 sf=parts/(method+'_SUMMARY.csv.gz');imf=parts/(method+'_IMAGES.csv.gz')
 if sf.exists() and imf.exists():
  done.append(method);print('reuse_summary',method,flush=True);continue
 summaries=[];all_images=[]
 for scope in ['ALL_TARGETS','primary','other_admitted']:
  sg=mg if scope=='ALL_TARGETS' else mg[mg.scope.eq(scope)]
  if sg.empty:continue
  for difficulty in ['ALL','简单','中等','困难','未分级']:
   dg=sg if difficulty=='ALL' else sg[sg.official_difficulty.eq(difficulty)]
   if dg.empty:continue
   images=dg.groupby(key+['image_id','building'],dropna=False)[cols].mean().reset_index()
   images['method']=method;images['scope_summary']=scope;images['difficulty_summary']=difficulty;all_images.append(images)
   pools=dg.groupby(key,dropna=False)
   for group,im in images.groupby(key,dropna=False):
    source=pools.get_group(group)
    # Pairwise finite mask for each metric matches the old dropna(within,cross).
    numeric=im[cols].copy()
    for metric in METRICS:
     mcols=[metric+'_'+s for s in ['within','cross','gap']];good=numeric[mcols[:2]].notna().all(axis=1)
     numeric.loc[~good,mcols]=np.nan
    mu=numeric.mean();cnt=numeric.count();quant=numeric.quantile([.25,.5,.75]);pos=(numeric>1e-10).where(numeric.notna()).sum();neg=(numeric<-1e-10).where(numeric.notna()).sum();zero=numeric.abs().le(1e-10).where(numeric.notna()).sum()
    b=numeric.assign(building=im.building.values).groupby('building').mean();bm=b.mean();bc=b.count();bp=(b>1e-10).where(b.notna()).sum()
    for metric in METRICS:
     wi=metric+'_within';cr=metric+'_cross';ga=metric+'_gap';n=int(cnt[wi])
     if not n:continue
     summaries.append(dict(method=method,**dict(zip(key,group)),scope_summary=scope,difficulty_summary=difficulty,metric=metric,
      images=n,buildings=int(bc[wi]),pools=source.pool_id.nunique(),image_within=mu[wi],image_cross=mu[cr],image_gap=mu[ga],
      image_ratio=mu[cr]/mu[wi] if mu[wi]>1e-12 else np.nan,image_gap_p25=quant.at[.25,ga],image_gap_median=quant.at[.5,ga],image_gap_p75=quant.at[.75,ga],
      images_cross_larger=int(pos[ga]),images_cross_smaller=int(neg[ga]),images_no_gap=int(zero[ga]),
      building_within=bm[wi],building_cross=bm[cr],building_gap=bm[ga],buildings_cross_larger=int(bp[ga]),
      within_finite_pairs=int(source[metric+'_within_finite_pairs'].sum()),cross_finite_pairs=int(source[metric+'_cross_finite_pairs'].sum()),minimum_member_n=int(source.member_n.min())))
 save(pd.DataFrame(summaries),sf);save(pd.concat(all_images,ignore_index=True),imf);done.append(method)
 dump({'completed_methods':len(done),'methods':table.method.nunique(),'saved_methods':done,'seconds':time.monotonic()-start},O/'SUMMARY_PROGRESS.json')
 print('summary',len(done),method,len(summaries),flush=True)
summary=pd.concat([pd.read_csv(parts/(m+'_SUMMARY.csv.gz'),low_memory=False) for m in sorted(table.method.unique())],ignore_index=True)
images=pd.concat([pd.read_csv(parts/(m+'_IMAGES.csv.gz'),low_memory=False) for m in sorted(table.method.unique())],ignore_index=True)
save(summary,O/'RAW_CLASS_DISTANCE_SUMMARY.csv');save(images,O/'RAW_CLASS_DISTANCE_BY_IMAGE.csv.gz')
# Common-pool comparisons are direct vector differences from the same saved rows.
wide=table[table.support.eq('common45_known')];comparisons=[]
metrics=['geometry_pair_angle','geometry_bev_distance','geometry_top_angle','geometry_bottom_angle','turn_difference','redundancy_difference']
for baseline in ['Q_MEDIAN2','DSTRUCT_K3']:
 b=wide[wide.method.eq(baseline)]
 for method,g in wide.groupby('method'):
  if method==baseline:continue
  mer=g.merge(b,on=['pool_id','subset'],suffixes=('_candidate','_baseline'),validate='one_to_one')
  for metric in metrics:
   a=mer[[metric+'_within_candidate',metric+'_cross_candidate',metric+'_within_baseline',metric+'_cross_baseline']].notna().all(axis=1)
   z=mer.loc[a];v=pd.DataFrame(dict(method=method,baseline=baseline,pool_id=z.pool_id,image_id=z.image_id_candidate,building=z.building_candidate,
    condition=z.condition_candidate,layer=z.layer_candidate,scope=z.scope_candidate,subset=z.subset,metric=metric,
    candidate_within=z[metric+'_within_candidate'],candidate_cross=z[metric+'_cross_candidate'],candidate_gap=z[metric+'_gap_candidate'],
    baseline_within=z[metric+'_within_baseline'],baseline_cross=z[metric+'_cross_baseline'],baseline_gap=z[metric+'_gap_baseline'],gap_gain=z[metric+'_gap_candidate']-z[metric+'_gap_baseline']))
   comparisons.append(v)
paired=pd.concat(comparisons,ignore_index=True);save(paired,O/'COMMON45_BASELINE_PAIRED_BY_POOL.csv.gz')
missing=pd.read_csv(O/'RAW_CLASS_DISTANCE_UNESTIMABLE.csv.gz');pair_receipt=json.loads((O/'PAIR_COMPLETION.json').read_text())
dump(dict(methods=table.method.nunique(),raw_pairs=pair_receipt['pairs'],compared_pool_rows=len(table),unestimable_panel_rows=len(missing),summary_rows=len(summary),image_rows=len(images),paired_baseline_rows=len(paired),
 target_weighting='available target contrasts equal within image; images equal; building equal also saved',class_weighting='within class means equal; unordered cross-class-pair means equal',
 unknown_labels='excluded, no fabricated label',same_count='equal actual bottom-point count; retains position/shape distances',
 scope='Manual/Semi separate; ordinary/doorway/special separate; other target grade remains unknown',
 no_new_fusion=True,no_quality_rescoring=True,aggregation_only=True,classification_changed=False,summary_source='complete_from_pool_rows.py'),O/'COMPLETION.json')
print('finished',len(summary),len(images),len(paired),flush=True)
