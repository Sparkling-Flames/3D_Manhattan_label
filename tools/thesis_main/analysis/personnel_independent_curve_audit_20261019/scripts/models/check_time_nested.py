import os
os.environ['OPENBLAS_NUM_THREADS']='1'
import sys,json
from pathlib import Path
import numpy as np,pandas as pd
R=Path('/workspace/shared/personnel_v2_audit_20261018');S=R/'extracted/work_v2_20261019/profiles';O=R/'independent/models';sys.path.insert(0,str(S));from run_profiles import fit_fe,fit_joint
m=pd.read_csv(S/'records_flat.csv');f=pd.read_csv(S/'fold_profiles.csv'); q=m[m.quality_usable&m.condition.eq('manual')&m.quality_use.eq('ordinary_primary')];gate=m.pool_analysis_eligible&m.condition.eq('manual')&m.ordinary_difficulty_eligible&m.difficulty.isin(['easy','medium','hard']);res={}
for name,col in [('source','source_active_time_seconds'),('target','target_matched_time_seconds')]:
 t=m[gate&m[col].gt(0)].copy();t['log']=np.log(t[col]);t['task']=t.source_task if name=='source' else t.task;errs=[];supporterr=0
 for b,p in f.groupby('heldout_building'):
  tr=t[t.building_id.ne(b)];ws=sorted(tr.worker_id.unique()); widx={w:i for i,w in enumerate(ws)};ti=pd.factorize(tr.task)[0];X=np.zeros((len(tr),len(ws)));X[np.arange(len(tr)),tr.worker_id.map(widx)]=1;H=np.zeros((ti.max()+1,len(ws)));np.add.at(H,ti,X);n=np.bincount(ti);yy=tr['log'].to_numpy();A=X.T@X-H.T@(H/n[:,None]);rhs=X.T@yy-H.T@(np.bincount(ti,weights=yy)/n);beta=np.linalg.pinv(A,rcond=1e-11)@rhs
  for r in p.itertuples():
   if r.worker_id in widx:errs.append(abs(beta[widx[r.worker_id]]-getattr(r,'T_'+name+'_effect')))
   g=tr[tr.worker_id.eq(r.worker_id)];supporterr+=int((g.task.nunique()>=6 and g.building_id.nunique()>=3)!=getattr(r,'T_'+name+'_supported'))
 res[name]={'rows':len(t),'workers':t.worker_id.nunique(),'max_effect_error':max(errs),'support_errors':supporterr,'duplicated_task_worker':int(t.duplicated(['task','worker_id']).sum())}
nest=pd.read_csv(S/'nested_fold_features.csv');pairs=nest[['outer_heldout_building','inner_heldout_building']].drop_duplicates().iloc[[0,40,123,240,400]];errs=[]
for a,b in pairs.itertuples(index=False,name=None):
 tr=q[~q.building_id.isin([a,b])];be,_=fit_fe(tr,'B8L2');th=fit_joint(tr,'B8L2',20);p=nest[nest.outer_heldout_building.eq(a)&nest.inner_heldout_building.eq(b)]
 for r in p.itertuples():
  if r.worker_id not in be:continue
  errs.append(abs(be[r.worker_id]-r.Q_effect_B8L2))
  for di in ['easy','medium','hard']:errs.append(abs(th[(r.worker_id,di)]-getattr(r,'theta_'+di+'_B8L2')))
res['nested_5_pairs_direct_refit_max_error']=max(errs);res['time_source_target_overlap_inventory']=int((m.target_matched_time_seconds.notna()&m.target_matched_time_seconds.eq(m.source_active_time_seconds)).sum());res['source_cohort_workers']=m[m.source_active_time_seconds.notna()].groupby('worker_id').origin.nunique().value_counts().to_dict();(O/'TIME_NESTED_CHECKS.json').write_text(json.dumps(res,indent=2));print(json.dumps(res,indent=2))
