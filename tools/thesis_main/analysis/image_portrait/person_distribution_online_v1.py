"""Usable finite-candidate predictor without an argument for hidden answers.

This is a tested prototype, not a certified synthetic-worker replacement.
Novel geometry outside the candidate dictionary is NOT generated here.
"""
from __future__ import annotations
import argparse,json
from pathlib import Path
import numpy as np
from tools.thesis_main.analysis.image_portrait import person_distribution_hypothesis_v1 as c
from tools.thesis_main.analysis.image_portrait.person_distribution_run_v1 import CachedLearner

def predict_candidates(learner,image_id,condition,model_candidates,seed_records,recipient_workers,method='personal',temperature=.25,alpha=.1):
 if method not in ('equal','personal','context','type2','type3','type4','mixture'):raise ValueError('Unknown declared method')
 if not 0<=alpha<=1 or temperature<=0:raise ValueError('Invalid probability or temperature')
 seed_workers=[r['worker_id']for r in seed_records];recipients=list(recipient_workers)
 if len(set(seed_workers))!=len(seed_workers)or len(set(recipients))!=len(recipients):raise ValueError('Each real or model-world roster slot needs a distinct worker ID')
 if set(seed_workers)&set(recipients):raise ValueError('Seed workers cannot be counted again as unseen people')
 points=[];sources=[]
 for r in seed_records:
  p=np.asarray(r['points'],float)
  if p.ndim!=2 or p.shape[1]!=2 or len(p)<6 or len(p)%2 or not np.isfinite(p).all():raise ValueError('Supply confirmed effective even point pairs; no automatic correction')
  points.append(p);sources.append(dict(source='observed_seed',canonical_id=r.get('canonical_id'),worker_id=r['worker_id']))
 model_points=[];model_sources=[]
 for item in model_candidates:
  p=np.asarray(item['points'],float);fams=item['families']
  old=next((j for j,x in enumerate(model_points)if x.shape==p.shape and np.allclose(x,p,atol=1e-9,rtol=0)),None)
  if old is None:model_points.append(p);model_sources.append(list(fams))
  else:model_sources[old]=sorted(set(model_sources[old])|set(fams))
 k=len(points);known_seed=all(w in learner.wi for w in seed_workers);known=np.array([w in learner.wi for w in recipients]);wi=np.array([learner.wi.get(w,0)for w in seed_workers+recipients]);g=dict(key=condition+'|'+image_id,image_id=image_id,condition=condition,wi=wi,model_points=model_points,model_sources=model_sources)
 type_n=int(method[-1])if method.startswith('type')else 0
 if k:
  if method=='equal' or not known_seed:w=np.full((len(recipients),k),1/k)
  else:w=learner.seed_weights(g,np.arange(k),np.arange(k,k+len(recipients)),temp=temperature,context=method in ('context','mixture'),types=type_n)
  w[~known]=1/k
  mass=alpha if method=='mixture'and model_points else 0.
  if mass:
   mw=learner.affinity_weights(g,wi[k:],'context_personal');mw[~known]=learner.affinity_weights(g,wi[k:],'context_population')[~known]
   w=np.c_[(1-mass)*w,mass*mw];points+=model_points;sources.extend(dict(source='frozen_model',families=f)for f in model_sources)
 else:
  if not model_points:raise ValueError('No real seeds and no model candidates: cannot produce geometry')
  points=model_points;sources=[dict(source='frozen_model',families=f)for f in model_sources]
  kind='uniform'if method=='equal'else 'context_personal'if method in ('context','mixture')else 'type'+str(type_n)if type_n else 'personal'
  w=learner.affinity_weights(g,wi,kind);w[~known]=learner.affinity_weights(g,wi,'population')[~known]
 if not len(recipients):raise ValueError('An explicit unseen/model-world roster is required')
 assert np.isfinite(w).all()and(w>=0).all()and np.allclose(w.sum(1),1)
 return dict(schema='finite_candidate_person_distribution_v1',image_id=image_id,condition=condition,method=method,real_observed_people=k,recipient_workers=recipients,known_historical_worker=known.tolist(),unknown_worker_fallback='population model/seed-uniform; never a new genuine type',probabilities=w.tolist(),candidate_sources=sources,candidate_points=[p.tolist()for p in points],synthetic_prediction=True,review_required=True,outside_candidate_probability=None,limitation='finite candidate support; null outside probability means not estimated, not zero',parameter_uncertainty='not fitted by this interface',user_review_status='not_filled')

def sample_world(prediction,random_seed=20260916,world_id=0):
 r=c.seed('online_world',random_seed,world_id,prediction['image_id']);ans=[]
 for who,w in zip(prediction['recipient_workers'],prediction['probabilities']):
  j=int(r.choice(len(w),p=w));ans.append(dict(simulation_id=f'{prediction["image_id"]}:world{world_id}:{who}',source_persona_id=who,synthetic=True,points=prediction['candidate_points'][j],candidate_source=prediction['candidate_sources'][j],real_observed_people=prediction['real_observed_people'],adds_independent_real_people=0,review_required=True))
 return ans

def check_against_saved(out):
 s,pools,bank,raw,meta,workers=c.prepare(out);pool={g['key']:g for g in pools};snaps=json.loads((out/'growth_prediction_snapshots.json').read_text());learn={};tests=0;examples=[]
 mapping={'seed_equal':'equal','seed_person_t025':'personal','seed_context_t025':'context','seed_type4':'type4'}
 for sp in snaps:
  if sp['method']not in mapping or sp['repeat']!=0:continue
  g=pool[sp['condition']+'|'+sp['image_id']];key=(g['condition'],g['building'])
  if key not in learn:learn[key]=CachedLearner([h for h in pools if h['condition']==g['condition']and h['building']!=g['building']and len(h['ids'])>=2],meta,workers,[g['building']])
  seeds=[dict(worker_id=g['workers'][j],canonical_id=g['ids'][j],points=g['points'][j].tolist())for j in sp['seed_index']];recipient=[g['workers'][j]for j in sp['future_index']];models=[dict(points=p.tolist(),families=f)for p,f in zip(g['model_points'],g['model_sources'])]
  pr=predict_candidates(learn[key],g['image_id'],g['condition'],models,seeds,recipient,mapping[sp['method']]);assert np.allclose(pr['probabilities'],sp['weights'],atol=1e-12);tests+=1
  if len(examples)<3 and sp['method']=='seed_person_t025':examples.append(dict(prediction=pr,model_world=sample_world(pr)))
 c.js(out/'online_api_verification.json',dict(status='passed',saved_prediction_equivalence_cases=tests,hidden_answer_argument_exists=False,synthetic_examples=len(examples)))
 c.js(out/'online_api_examples.json',examples)

if __name__=='__main__':
 ap=argparse.ArgumentParser();ap.add_argument('--output',type=Path,default=Path(c.OUT_DEFAULT));ap.add_argument('--verify-saved',action='store_true');a=ap.parse_args()
 if a.verify_saved:check_against_saved(a.output)
 else:raise SystemExit('Import predict_candidates and sample_world; see REPRODUCE.md. The API deliberately takes no hidden responses.')
