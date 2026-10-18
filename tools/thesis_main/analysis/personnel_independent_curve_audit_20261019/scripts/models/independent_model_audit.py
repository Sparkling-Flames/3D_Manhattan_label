import os
os.environ['OPENBLAS_NUM_THREADS']='1'
import json,hashlib
from pathlib import Path
import numpy as np,pandas as pd
ROOT=Path('/workspace/shared/personnel_v2_audit_20261018'); SRC=ROOT/'extracted/work_v2_20261019/profiles'; OUT=ROOT/'independent/models'
d=pd.read_csv(SRC/'records_flat.csv'); m=d[d.quality_usable & d.condition.eq('manual') & d.quality_use.eq('ordinary_primary')].copy(); folds=pd.read_csv(SRC/'fold_profiles.csv'); ws=sorted(m.worker_id.unique()); wi={w:i for i,w in enumerate(ws)}; D=['easy','medium','hard']; W=len(ws)
# Independently assemble residualized normal equations via a task-by-worker incidence matrix.
def fit(x,y,lam=None,ridge=0):
 n=W if lam is None else 3*W
 ix=x.worker_id.map(wi).to_numpy(); ix=ix if lam is None else ix+x.difficulty.map(dict(zip(D,range(3)))).to_numpy()*W
 tasks=pd.factorize(x.task)[0]; G=tasks.max()+1
 X=np.zeros((len(x),n)); X[np.arange(len(x)),ix]=1
 H=np.zeros((G,n)); np.add.at(H,tasks,X); counts=np.bincount(tasks); Y=x[y].to_numpy(float); sums=np.bincount(tasks,weights=Y)
 A=X.T@X-H.T@(H/counts[:,None]); b=X.T@Y-H.T@(sums/counts)
 A+=ridge*np.eye(n)
 if lam is not None:A+=lam*np.kron(np.eye(3)-np.ones((3,3))/3,np.eye(W))
 # Orthogonal projection enforces separate zero sums without original bordered-system solver.
 P=np.eye(W)-np.ones((W,W))/W; P=P if lam is None else np.kron(np.eye(3),P)
 return P@np.linalg.pinv(P@A@P,rcond=1e-11)@P@b
errs=[]; preds=[]; checks=[]
for b in sorted(m.building_id.unique()):
 tr=m[m.building_id.ne(b)]; te=m[m.building_id.eq(b)].copy(); fp=folds[folds.heldout_building.eq(b)].set_index('worker_id'); supported=set(fp[fp.Q_supported].index); te=te[te.worker_id.isin(supported)]
 checks.append({'building':b,'training_rows':len(tr),'test_rows':len(te),'train_test_object_overlap':len(set(tr.object_id)&set(te.object_id)),'train_building_excluded':b not in set(tr.building_id)})
 for metric in ['B8L2','D10']:
  models={'FE':fit(tr,metric),'joint20':fit(tr,metric,20),'ridge5':fit(tr,metric,ridge=5),'ridge15':fit(tr,metric,ridge=15),'ridge5_joint20':fit(tr,metric,20,5)}
  for w in ws:
   if w not in set(tr.worker_id):continue
   errs.append(abs(models['FE'][wi[w]]-fp.loc[w,'Q_effect_'+metric]))
   for j,di in enumerate(D):errs.append(abs(models['joint20'][j*W+wi[w]]-fp.loc[w,f'theta_{di}_{metric}']))
  for model,coef in models.items():
   x=te[['object_id','worker_id','building_id','image_id','task','difficulty',metric]].copy().rename(columns={metric:'observed'}); ix=x.worker_id.map(wi).to_numpy(); ix=ix if len(coef)==W else ix+x.difficulty.map(dict(zip(D,range(3)))).to_numpy()*W; x['prediction']=coef[ix];x['metric']=metric;x['model']=model;preds.append(x)
 print('completed',b,flush=True)
pred=pd.concat(preds);pred.to_csv(OUT/'independent_predictions.csv.gz',index=False)
results=[]
for metric in ['B8L2','D10']:
 for base,candidate in [('FE','joint20'),('FE','ridge5'),('ridge5','ridge5_joint20'),('ridge15','ridge5_joint20')]:
  keys=['object_id','worker_id','building_id','image_id','task','difficulty']; p=pred[pred.metric.eq(metric)]; a=p[p.model.eq(base)];z=a.merge(p[p.model.eq(candidate)][keys+['prediction']],on=keys,suffixes=('_base','_candidate'),validate='one_to_one');n=z.groupby('task')['observed'].transform('size');z=z[n>1].copy();n=z.groupby('task')['observed'].transform('size')
  y=(z.observed-z.groupby('task')['observed'].transform('mean'))*n/(n-1)
  for model in ['base','candidate']:
   pr=z['prediction_'+model]; z[model]=(y-(pr-pr.groupby(z.task).transform('mean'))*n/(n-1))**2
  for di in ['all']+D:
   q=z if di=='all' else z[z.difficulty.eq(di)];v=q.groupby(['building_id','image_id'])[['base','candidate']].mean().groupby('building_id').mean(); rng=np.random.default_rng(180026);ix=rng.integers(0,len(v),(20000,len(v)));aa=v.base.to_numpy();bb=v.candidate.to_numpy();gain=100*(aa[ix].mean(1)-bb[ix].mean(1))/aa[ix].mean(1)
   results.append(dict(metric=metric,baseline=base,model=candidate,difficulty=di,n=len(q),buildings=len(v),images=q.image_id.nunique(),base_mse=aa.mean(),candidate_mse=bb.mean(),gain_percent=100*(aa.mean()-bb.mean())/aa.mean(),ci_low=np.quantile(gain,.025),ci_high=np.quantile(gain,.975),improved_buildings=int((bb<aa).sum())))
pd.DataFrame(results).to_csv(OUT/'independent_comparisons.csv',index=False)
report={'data_counts':{'inventory':len(d),'quality':int(d.quality_usable.sum()),'ordinary_manual':len(m),'images':m.image_id.nunique(),'buildings':m.building_id.nunique()},'max_abs_independent_coefficient_error':max(errs),'unique_task_worker':not m.duplicated(['task','worker_id']).any(),'task_key_matches':bool((d.task==d[['image_id','condition','reference_id','reference_version']].fillna('').apply(lambda r:json.dumps(r.tolist(),ensure_ascii=False,separators=(',',':')),axis=1)).all()),'reference_match':bool(m.difficulty_reference_match.all()),'fold_checks':checks,'bootstrap':{'resamples':20000,'unit':'building','conditional_on_fitted_LOBO_models':True,'refits_each_resample':False},'scope':'Independent matrix solver validates delivered 22-fold FE/joint coefficients and generates new equal-global-regularization comparisons; not original collection reconstruction.'}
(OUT/'INDEPENDENT_MODEL_AUDIT.json').write_text(json.dumps(report,indent=2))
print(json.dumps(report,indent=2))
