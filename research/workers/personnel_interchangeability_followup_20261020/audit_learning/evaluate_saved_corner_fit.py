"""Correct outcome reporting only; never refit or select saved labels."""
import json,hashlib,time
from pathlib import Path
import pandas as pd,numpy as np
from learn_corner_types import BASE,ROOT,P,S,SEED,prepare,Anchors,make_inner_folds,write
TIER='legacy'
def run(tier=TIER):
 t=time.perf_counter();out=BASE/('corner_fit_'+tier);manifest=out/'METHOD_MANIFEST.json';before=hashlib.sha256(manifest.read_bytes()).hexdigest();labelhash=hashlib.sha256((out/'worker_labels.csv').read_bytes()).hexdigest()
 files=sorted((BASE/'corner_history').glob('*.csv.gz'))
 if tier=='mixed':files+=sorted((BASE/'corner_h20').glob('*.csv.gz'))
 frame=prepare(pd.concat([pd.read_csv(p) for p in files],ignore_index=True));split=json.load(open(P/'analysis/composition/SPLIT.json'));folds=make_inner_folds(split['history_buildings']);labs=pd.read_csv(out/'fold_labels.csv');qt=pd.read_csv(BASE/'eight_building_QT_features.csv');cv=[];paired=[];support=[]
 for (mid,fi),g in labs.groupby(['method_id','fold']):
  g=g.sort_values('worker_id');ws=g.worker_id.tolist();lab=g.class_id.to_numpy(int);k=len(set(lab));test=frame[frame.building.isin(folds[fi])];fast=Anchors(test,ws)
  for r in fast.evaluate(lab):cv.append({'method_id':mid,'fold':fi,**r})
  ff=qt[qt.fold.eq(fi)].set_index('worker_id')
  for name,col,gate in [('Q_only_same_K','q_beta','core_supported'),('T_only_same_K','t_source_origin_effect','t_supported')]:
   ids=[i for i,w in enumerate(ws) if bool(ff.loc[w,gate]) and np.isfinite(ff.loc[w,col])]
   if len(ids)<4*k:continue
   common=[ws[i] for i in ids];order=sorted(range(len(common)),key=lambda i:(ff.loc[common[i],col],common[i]));bl=np.zeros(len(common),int)
   for c,part in enumerate(np.array_split(order,k)):bl[part]=c
   evaluator=Anchors(test,common)
   for r in evaluator.paired(lab[ids],bl):paired.append({'method_id':mid,'fold':fi,'baseline':name,'draw':0,**r})
  rng=np.random.default_rng(SEED+fi*100000+k)
  for draw in range(40):
   rnd=rng.permutation(lab)
   for r in fast.paired(lab,rnd):paired.append({'method_id':mid,'fold':fi,'baseline':'same_capacity_random','draw':draw,**r})
  support.append({'method_id':mid,'fold':fi,'test_buildings':test.building.nunique(),'observed_common_anchors':int(fast.common(lab,None).sum()),'primary_common_anchors':int(fast.common(lab).sum())})
 cvs=pd.DataFrame(cv);prs=pd.DataFrame(paired);cvs.to_csv(out/'inner_cv_building.csv',index=False);cvs.groupby('method_id').mean(numeric_only=True).to_csv(out/'inner_cv_summary.csv');prs.to_csv(out/'paired_random_building.csv.gz',index=False);pd.DataFrame(support).to_csv(out/'evaluation_support.csv',index=False)
 num=[c for c in prs if c.startswith(('candidate_','baseline_','delta_'))];draws=prs.groupby(['method_id','baseline','draw'])[num].mean().reset_index();draws.to_csv(out/'paired_random_draws.csv',index=False);summary=[]
 for (mid,baseline),g in draws.groupby(['method_id','baseline']):
  r={'method_id':mid,'baseline':baseline,'draws':len(g)}
  for m in num:r[m+'_mean']=g[m].mean();r[m+'_p05']=g[m].quantile(.05);r[m+'_p95']=g[m].quantile(.95)
  summary.append(r)
 pd.DataFrame(summary).to_csv(out/'paired_random_summary.csv',index=False)
 assert before==hashlib.sha256(manifest.read_bytes()).hexdigest() and labelhash==hashlib.sha256((out/'worker_labels.csv').read_bytes()).hexdigest()
 write(out/'EVALUATION_CORRECTION_RECEIPT.json',{'elapsed_seconds':time.perf_counter()-t,'no_refitting':True,'labels_sha256':labelhash,'manifest_sha256':before,'correction':'Verified different_corner_count separated from missinggeometry/notverifiedequal; all observed-common buildings retained even if primarydistance unavailable; angle-specific common masks already corrected before original fits','script_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest()})
 print('Corrected outcome aggregation complete, labels unchanged.',flush=True)
if __name__=='__main__':
 import argparse
 p=argparse.ArgumentParser();p.add_argument('--tier',default='legacy');a=p.parse_args();run(a.tier)
