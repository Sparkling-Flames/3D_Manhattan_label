#!/usr/bin/env python3
"""One post-primary method check: protect strongest person-history baseline.
Historical person x purpose deviations receive independent shrinkage; no shared
ridge penalty can change the fitted general person-history baseline.
"""
import os
for k in ['OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS']:os.environ.setdefault(k,'1')
import argparse,json,hashlib
from pathlib import Path
import numpy as np,pandas as pd
from sklearn.model_selection import GroupKFold
from personal import rel_target,centered_prediction,history_table,image_mse,save

LAMBDAS=[np.inf,64.,16.,4.,1.,0.]
SEED=2026102704

def predict(train,test,outcome,lam):
 byp=train.groupby('worker_id')[outcome].mean()
 byt=train.groupby(['worker_id','room_type_model'])[outcome].mean()
 cnt=train.groupby(['worker_id','room_type_model']).building.nunique()
 b=test.worker_id.map(byp).fillna(0).to_numpy()
 t=np.array([byt.get((w,r),np.nan) for w,r in zip(test.worker_id,test.room_type_model)])
 n=np.array([cnt.get((w,r),0) for w,r in zip(test.worker_id,test.room_type_model)])
 dev=np.nan_to_num(t-b,nan=0.)
 shrink=np.zeros(len(test)) if np.isinf(lam) else np.divide(n,n+lam,out=np.zeros(len(test),dtype=float),where=(n+lam)>0)
 base=centered_prediction(b,test)
 pred=centered_prediction(b+shrink*dev,test)
 return pred,base,dev,n,shrink

def main():
 ap=argparse.ArgumentParser();ap.add_argument('--inputs',type=Path,required=True);ap.add_argument('--primary',type=Path,required=True);ap.add_argument('--out',type=Path,required=True);a=ap.parse_args();a.out.mkdir(exist_ok=True,parents=True)
 d=pd.read_csv(a.inputs/'annotations.csv.gz',dtype={'object_id':str},low_memory=False)
 d=d[(d.condition=='manual')&(d.layer=='ordinary')&d.formal_quality&d.Q.notna()&d.D10.notna()].copy().reset_index(drop=True)
 for oc in ['Q','D10']:d['r_'+oc]=rel_target(d,oc)
 d.room_type_model=d.room_type_model.fillna('__MISSING__')
 protocol={'study_status':'Post-primary finite internal method comparison; not independent external validation',
  'reason':'Shared ridge shrinkage may perturb stable person effects; isolate purpose contribution while retaining exact general-history baseline.',
  'formula':'center_target_roster[general_person_history + b/(b+lambda)*(same_purpose_person_history-general_person_history)]',
  'b':'number of distinct eligible historical buildings for worker and purpose outside target building',
  'lambda_candidates':['infinity',64,16,4,1,0],'infinity':'exact zero purpose increment',
  'selection':'5-building-group inner CV minimizing image-equal MSE, outer entire building omitted; tie order prefers stronger shrinkage',
  'main_Q_support':'177 ordinary Manual images; also retain prespecified 161 images of recorded purposes with >=2 buildings',
  'D10':'Same support and Q-selected lambda; no additional hyperparameter search',
  'target_peer_baseline':'Target self excluded; prediction uses no target response; target roster centering only',
  'new_fusion':0,'new_personnel_classification':False,'input_sha256':hashlib.sha256((a.inputs/'annotations.csv.gz').read_bytes()).hexdigest()}
 (a.out/'DESIGN_BEFORE_FIT.json').write_text(json.dumps(protocol,ensure_ascii=False,indent=2)+'\n')
 folds=[];cvs=[];preds=[]
 for held in sorted(d.building.unique()):
  tr=d[d.building!=held];te=d[d.building==held]
  scores=[]
  for fi,(ii,vi) in enumerate(GroupKFold(n_splits=5).split(tr,groups=tr.building)):
   t=tr.iloc[ii];v=tr.iloc[vi]
   for lam in LAMBDAS:
    pred,_,_,_,_=predict(t,v,'r_Q',lam)
    scores.append({'held_out_building':held,'inner_fold':fi,'lambda':('infinity' if np.isinf(lam) else str(int(lam))),'mse':image_mse(v.r_Q,pred,v),'images':v.image_key.nunique(),
                   'train_buildings':'|'.join(sorted(t.building.unique())),'validation_buildings':'|'.join(sorted(v.building.unique()))})
  cv=pd.DataFrame(scores);avg=cv.groupby('lambda').apply(lambda g:np.average(g.mse,weights=g.images),include_groups=False)
  ordered=[('infinity' if np.isinf(x) else str(int(x))) for x in LAMBDAS]
  best=min(ordered,key=lambda x:avg[x]);lam=np.inf if best=='infinity' else float(best)
  folds.append({'held_out_building':held,'lambda':best,'inner_image_mse':avg[best],'inner_baseline_mse':avg['infinity'],'train_records':len(tr),'train_images':tr.image_key.nunique(),'train_buildings':tr.building.nunique(),'target_records':len(te),'target_images':te.image_key.nunique()});cvs.append(cv)
  for oc in ['Q','D10']:
   pred,base,dev,n,shrink=predict(tr,te,'r_'+oc,lam)
   z=te[['object_id','image_key','image','building','worker_id','room_type_model','room_type_status','difficulty']].copy()
   z['outcome']=oc;z['actual_relative']=te['r_'+oc].to_numpy();z['baseline_prediction']=base;z['purpose_prediction']=pred;z['source_type_deviation']=dev;z['same_purpose_history_buildings']=n;z['shrinkage_weight']=shrink;z['selected_lambda']=best
   z['baseline_ae']=abs(z.baseline_prediction-z.actual_relative);z['purpose_ae']=abs(z.purpose_prediction-z.actual_relative)
   z['baseline_se']=(z.baseline_prediction-z.actual_relative)**2;z['purpose_se']=(z.purpose_prediction-z.actual_relative)**2;z['ae_gain']=z.baseline_ae-z.purpose_ae
   preds.append(z)
 P=pd.concat(preds);save(P,a.out/'PROTECTED_PURPOSE_OOF.csv.gz');save(pd.DataFrame(folds),a.out/'OUTER_FOLD_LAMBDA.csv');save(pd.concat(cvs),a.out/'INNER_CV.csv.gz')
 # Verify the supposedly protected baseline is exactly the established baseline.
 errs=[]
 for oc in ['Q','D10']:
  old=pd.read_csv(a.primary/f'OOF_{oc}.csv.gz',dtype={'object_id':str});old=old[old.method=='person_history'][['object_id','predicted_relative']]
  new=P[P.outcome==oc].merge(old,on='object_id',validate='one_to_one')
  errs.append({'outcome':oc,'rows':len(new),'baseline_max_abs_difference':float(abs(new.baseline_prediction-new.predicted_relative).max())})
 assert max(x['baseline_max_abs_difference'] for x in errs)<1e-10
 I=P.groupby(['outcome','image_key','image','building','room_type_model','room_type_status','difficulty'],as_index=False).agg(records=('object_id','size'),baseline_mae=('baseline_ae','mean'),purpose_mae=('purpose_ae','mean'),baseline_mse=('baseline_se','mean'),purpose_mse=('purpose_se','mean'),people=('worker_id','nunique'))
 I['mae_gain']=I.baseline_mae-I.purpose_mae;save(I,a.out/'PER_IMAGE.csv')
 rng=np.random.default_rng(SEED);sums=[]
 for oc in ['Q','D10']:
  for label,sub in [('all177',I[I.outcome==oc]),('recorded_multibuilding161',I[(I.outcome==oc)&I.room_type_status.eq('recorded_purpose')&~I.room_type_model.eq('特殊用途')])]:
   b=sub.groupby('building').agg(n=('image_key','size'),gain=('mae_gain','sum'),bm=('baseline_mse','sum'),pm=('purpose_mse','sum'));dr=rng.integers(0,len(b),(2000,len(b)))
   ns=b.n.to_numpy()[dr].sum(1);g=b.gain.to_numpy()[dr].sum(1)/ns;rg=np.sqrt(b.bm.to_numpy()[dr].sum(1)/ns)-np.sqrt(b.pm.to_numpy()[dr].sum(1)/ns)
   bg=sub.groupby('building').mae_gain.mean()
   sums.append(dict(outcome=oc,support=label,images=len(sub),buildings=sub.building.nunique(),baseline_mae=sub.baseline_mae.mean(),purpose_mae=sub.purpose_mae.mean(),mae_gain=sub.mae_gain.mean(),baseline_rmse=np.sqrt(sub.baseline_mse.mean()),purpose_rmse=np.sqrt(sub.purpose_mse.mean()),
     image_improve=int((sub.mae_gain>1e-12).sum()),image_worse=int((sub.mae_gain< -1e-12).sum()),image_equal=int((abs(sub.mae_gain)<=1e-12).sum()),building_improve=int((bg>1e-12).sum()),building_worse=int((bg< -1e-12).sum()),building_equal=int((abs(bg)<=1e-12).sum()),
     mae_gain_boot_lo=np.quantile(g,.025),mae_gain_boot_hi=np.quantile(g,.975),rmse_gain_boot_lo=np.quantile(rg,.025),rmse_gain_boot_hi=np.quantile(rg,.975),building_equal_mae_gain=bg.mean()))
 save(pd.DataFrame(sums),a.out/'SUMMARY.csv')
 bytype=I.groupby(['outcome','room_type_model'],as_index=False).agg(images=('image_key','size'),buildings=('building','nunique'),mae_gain=('mae_gain','mean'),images_improve=('mae_gain',lambda x:int((x>1e-12).sum())),images_worse=('mae_gain',lambda x:int((x< -1e-12).sum())),images_equal=('mae_gain',lambda x:int((abs(x)<=1e-12).sum())))
 save(bytype,a.out/'BY_PURPOSE.csv')
 byw=P.groupby(['outcome','worker_id','room_type_model'],as_index=False).agg(images=('image_key','nunique'),buildings=('building','nunique'),mae_gain=('ae_gain','mean'),source_buildings_min=('same_purpose_history_buildings','min'),shrinkage_mean=('shrinkage_weight','mean'))
 save(byw,a.out/'BY_PERSON_PURPOSE.csv')
 protocol.update(completed=True,baseline_checks=errs,selected_lambda_counts=pd.DataFrame(folds)['lambda'].value_counts().to_dict(),OOF_rows=len(P))
 (a.out/'COMPLETE.json').write_text(json.dumps(protocol,ensure_ascii=False,indent=2)+'\n')
 print(pd.DataFrame(sums).to_string(index=False));print(pd.DataFrame(folds)['lambda'].value_counts())
if __name__=='__main__':main()
