"""Exact cached execution of personalized_simulator_v2 (no estimator changes)."""
from __future__ import annotations
import sys
from pathlib import Path
import numpy as np
ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT))
from tools.thesis_main.analysis import personalized_simulator_v2 as s


def fast_score(g,seed_idx,prof,temp,models,alpha=0.):
 if '_prediction_cache' not in g:
  candidates=[models[g['image_id']][f] for f in s.FAMILIES if f in models.get(g['image_id'],{})]
  pp=g['points']+candidates
  g['_prediction_cache']=(pp,np.array([len(p)//2 for p in pp]),s.kernel(pp,pp))
 all_points,all_counts,K=g['_prediction_cache'];n=len(g['workers']);seed_idx=np.asarray(seed_idx,int);seedset=set(seed_idx);hold=np.array([i for i in range(n) if i not in seedset],int)
 assert seedset.isdisjoint(hold)
 seedw=[g['workers'][i] for i in seed_idx];targetw=[g['workers'][i] for i in hold];nmodels=len(all_points)-n
 if len(seed_idx)==0:
  ai=np.arange(n,len(all_points));weights=np.full((len(hold),len(ai)),1/max(1,len(ai)))
 else:
  ai=seed_idx;weights=s.seed_weights(prof,seedw,targetw,temp)
  if alpha>0 and nmodels:
   ai=np.r_[ai,np.arange(n,len(all_points))];weights=np.c_[weights*(1-alpha),np.full((len(hold),nmodels),alpha/nmodels)]
 if len(ai)==0:return None
 ac=all_counts[ai];hc=all_counts[hold];labels=np.unique(np.r_[ac,hc]);pr=weights@(ac[:,None]==labels).astype(float);y=(hc[:,None]==labels).astype(float)
 ks=1-2*np.sum(weights*K[np.ix_(hold,ai)],axis=1)+np.einsum('ij,jk,ik->i',weights,K[np.ix_(ai,ai)],weights)
 return dict(count_brier=float(np.mean(np.sum((pr-y)**2,axis=1))),kernel_score=float(ks.mean()),count_tv=float(.5*np.abs(pr.mean(0)-y.mean(0)).sum()),uncovered_point_count=float(np.mean(~np.isin(hc,ac))),n_holdout=len(hold),seed_workers='|'.join(seedw),holdout_workers='|'.join(targetw),seed_canonical_ids='|'.join(g['ids'][i]for i in seed_idx),holdout_canonical_ids='|'.join(g['ids'][i]for i in hold),weights=weights,anchors=[all_points[i]for i in ai],hold=hold)


def self_test():
 points=[np.array([[100,100],[100,400],[400,100],[400,400],[700,100],[700,400]],float),np.array([[105,102],[105,399],[402,100],[402,398],[698,99],[698,401]],float),np.array([[110,105],[110,395],[390,103],[390,397],[701,102],[701,402]],float)]
 g=dict(image_id='test_a',building='test',condition='manual',workers=['W001','W002','W003'],points=points,pcs=np.array([6,6,6]),dm=np.array([[0,.05,.1],[.05,0,.08],[.1,.08,0]]),ids=['a','b','c'])
 prof=s.pair_profile([g],g['workers']);models={'test_a':{'HoHoNet':points[0]}}
 for k in (0,1,2):
  for t in s.TEMPS:
   for a in s.ALPHAS:
    r=s.prediction_scores(g,np.arange(k),prof,t,models,a);f=fast_score(g,np.arange(k),prof,t,models,a)
    assert all(abs(r[c]-f[c])<1e-12 for c in ('kernel_score','count_brier','count_tv'))
    assert set(f['seed_canonical_ids'].split('|')).isdisjoint(set(f['holdout_canonical_ids'].split('|')))
    assert np.allclose(f['weights'].sum(1),1)
 K=s.kernel(points,points);assert np.linalg.eigvalsh(K).min()>-1e-10
 g2=dict(g,image_id='outside_a',building='outside');prof2=s.pair_profile([g2],g['workers']);assert np.isfinite(prof2['d']).all()
 assert np.allclose(s.rng_for(1,'a').random(10),s.rng_for(1,'a').random(10))
 assert not np.allclose(s.rng_for(1,'a').random(10),s.rng_for(2,'a').random(10))
 print('SELF_TEST: 108 exact cached scoring cases; PSD; identity; normalization; deterministic RNG: PASS',flush=True)

if __name__=='__main__':
 self_test();s.prediction_scores=fast_score;s.main()
