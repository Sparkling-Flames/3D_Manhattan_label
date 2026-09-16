"""Resume completed fitting outputs, accelerating ONLY paired resampling.

Building-resampling sums/counts are exact sufficient statistics for the original
image-weighted mean. This changes neither fitted predictions nor selected models.
"""
from pathlib import Path
import argparse,json
import numpy as np
import pandas as pd
from tools.thesis_main.analysis.image_portrait import person_distribution_hypothesis_v1 as c
from tools.thesis_main.analysis.image_portrait.person_distribution_run_v1 import CachedLearner,test_cache

def paired_exact(frame,method,base,metric,keys):
 a=frame[frame.method==method];b=frame[frame.method==base];z=a.merge(b,on=keys,suffixes=('_a','_b'));z=z[np.isfinite(z[metric+'_a'])&np.isfinite(z[metric+'_b'])]
 if not len(z):return None
 delta=z[metric+'_a'].to_numpy()-z[metric+'_b'].to_numpy();bs=(z.building if 'building'in z else z.building_a).to_numpy();names=sorted(set(bs));sums=np.array([delta[bs==b].sum()for b in names]);sizes=np.array([np.sum(bs==b)for b in names]);r=c.seed('paired',method,base,metric,str(keys));draw=r.choice(len(names),size=(1500,len(names)),replace=True);v=sums[draw].sum(1)/sizes[draw].sum(1)
 return dict(method=method,baseline=base,metric=metric,images=z.image_id.nunique(),buildings=len(names),delta=float(delta.mean()),ci_low=float(np.quantile(v,.025)),ci_high=float(np.quantile(v,.975)),building_macro_delta=float(np.mean(sums/sizes)))

def test_boot(out):
 df=pd.DataFrame([dict(image_id=str(i),building=['a','a','b','c','c','c'][i],method=m,loss=i*.2+(.04*i-.1 if m=='alternative'else 0))for m in ['base','alternative']for i in range(6)])
 old=c.boot_pair(df,'alternative','base','loss',['image_id','building']);new=paired_exact(df,'alternative','base','loss',['image_id','building'])
 for k in old:
  if isinstance(old[k],(float,int,np.number)):assert np.isclose(old[k],new[k],atol=1e-12),(k,old[k],new[k])
 c.js(out/'bootstrap_exactness_test.json',dict(status='passed',replicates=1500,meaning='same draws and statistics as original loop',number_of_independent_data_sets=1))

def finish_saved(out):
 frame=pd.read_csv(out/'heldout_distribution_predictions.csv.gz');agg=pd.read_csv(out/'per_image_scores.csv');folds=json.loads((out/'folds.json').read_text());ss=json.loads((out/'growth_prediction_snapshots.json').read_text());assert len(frame)>0 and len(folds)>0 and len(ss)>0
 assert (out/'training_only_selection.csv').is_file() and (out/'unrestricted_count_predictions.csv.gz').is_file()
 diffs=[]
 for (arm,k),g in agg.groupby(['condition','k']):
  base='cold_uniform'if k==0 else 'seed_equal'
  for name in sorted(set(g.method)-{base}):
   for metric in ('kernel_score','count_brier','count_tv','uncovered_count','abs_pair_disagreement_error'):
    r=paired_exact(g,name,base,metric,['image_id','building'])
    if r:diffs.append(dict(condition=arm,k=k,**r))
 pd.DataFrame(diffs).to_csv(out/'paired_increment.csv',index=False)
 cnt=pd.read_csv(out/'unrestricted_count_predictions.csv.gz').groupby(['condition','k','method','image_id','building'],as_index=False)[['count_brier','count_tv','unseen_train_count']].mean();cnt.to_csv(out/'count_per_image.csv',index=False);cnt.groupby(['condition','k','method']).agg(images=('image_id','nunique'),brier=('count_brier','mean'),tv=('count_tv','mean')).reset_index().to_csv(out/'count_summary.csv',index=False)
 cd=[]
 for (arm,k),g in cnt.groupby(['condition','k']):
  for name in sorted(set(g.method)-{'population'}):
   for base in ('population','image'):
    if name==base:continue
    r=paired_exact(g,name,base,'count_brier',['image_id','building'])
    if r:cd.append(dict(condition=arm,k=k,**r))
 pd.DataFrame(cd).to_csv(out/'count_paired_increment.csv',index=False)
 c.js(out/'method.json',dict(input_ref=c.INPUT_REF,prototype_ref=c.PROTO_REF,k_values=c.KS,outer_seed_repeats=c.OUTER_REPEATS,inner_seed_repeats=c.INNER_REPEATS,outer='leave complete target building',inner='three deterministic groups of training buildings',target='distribution of hidden real people, not difficulty truth',training_parameter_selection='mean per-image kernel score',type_candidates=[2,3,4],unknown_type=-1,geometry_candidates='deduplicated model layouts and only exposed real seed responses',counts_only_forecast='allows point-count mass outside geometric anchor support; no invented geometry',raw_experimental_difficulty_used=False,expert_tag_used=False,user_39_review_filled=False,retrospective_known_workers=True,forward_time_validation=False,resampling_implementation='exact sums/counts acceleration; original fitted files retained',input_actual_n_retained=True))
 c.js(out/'FIT_COMPLETE.json',dict(status='complete',prediction_rows=len(frame),images=frame.image_id.nunique(),conditions=sorted(frame.condition.unique()),fitting_reused_from_previous_run=True,bootstrap_completed_here=True))
 print('ACTUAL_SCORE_SUMMARY\n'+pd.read_csv(out/'score_summary.csv').to_string(index=False),flush=True)

def main(out):
 out.mkdir(parents=True,exist_ok=True);c.self_test(out);test_cache(out);test_boot(out);c.boot_pair=paired_exact;c.Learner=CachedLearner
 if (out/'per_image_scores.csv').exists()and(out/'growth_prediction_snapshots.json').exists():finish_saved(out)
 else:c.fit_all(out)

if __name__=='__main__':
 ap=argparse.ArgumentParser();ap.add_argument('--output',type=Path,default=Path(c.OUT_DEFAULT));a=ap.parse_args();main(a.output)
