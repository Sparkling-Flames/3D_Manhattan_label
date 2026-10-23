"""Finite-panel sensitivity and nested building-held-out early prediction.
All thresholds here are exploratory diagnostics, not a stopping policy.
"""
from pathlib import Path
import sys,math,json
from itertools import combinations
import numpy as np
import pandas as pd
from scipy.cluster.hierarchy import linkage,fcluster
from scipy.spatial.distance import squareform
from scipy.stats import spearmanr,hypergeom
from sklearn.pipeline import make_pipeline
from sklearn.impute import SimpleImputer
from sklearn.preprocessing import StandardScaler
from sklearn.linear_model import Ridge
ROOT=Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:sys.path.insert(0,str(ROOT))
from tools.thesis_main.analysis.preflight_data_20260906 import load,save,OUT,CURRENT
SEED=20260906
B=240

def moments(D):
 n=len(D);e=D[np.triu_indices(n,1)];s=e.sum();s2=e@e
 h=((D.sum(1)**2-(D**2).sum(1)).sum())/2
 j=(s*s-s2)/2-h
 theta=D.mean();z1=np.var(D.mean(1));v=np.mean(D**2)-theta**2
 return n,s,s2,h,j,theta,z1,v

def finite_var(m,k):
 n,s,s2,h,j,*_=m
 if k==n:return 0.
 pi=lambda r: math.comb(k,r)/math.comb(n,r) if k>=r and n>=r else 0.
 return max(0.,(pi(2)*s2+2*pi(3)*h+2*pi(4)*j)/math.comb(k,2)**2-(s/math.comb(n,2))**2)

def iid_var(m,k):
 return max(0.,(2*m[7]+4*(k-2)*m[6])/(k*(k-1)))

def modes(D,corners,cutoff):
 # Count compatibility is a descriptor, not proof of topological equivalence.
 dis=np.array(D);dis[corners[:,None]!=corners[None,:]]=1.
 labels=fcluster(linkage(squareform(dis,checks=False),method='complete'),cutoff,criterion='distance')
 ids=sorted(np.unique(labels),key=lambda v:(-np.sum(labels==v),int(np.flatnonzero(labels==v)[0])))
 return labels,ids

def check_math():
 rng=np.random.default_rng(SEED);x=rng.normal(size=(7,3));D=np.linalg.norm(x[:,None]-x[None,:],axis=2);m=moments(D);rr=[]
 for k in range(2,8):
  values=[D[np.ix_(s,s)].sum()/(k*(k-1)) for s in combinations(range(7),k)]
  rr.append(dict(n=7,k=k,enumerated_variance=np.var(values),analytic_variance=finite_var(m,k),mean=np.mean(values),full_mean=D.sum()/42))
  assert np.isclose(rr[-1]['analytic_variance'],rr[-1]['enumerated_variance'],atol=1e-11)
 save('mathematical_checks.csv',rr)
 # Exhaustive with-replacement check for the empirical-iid diagnostic.
 from itertools import product
 for k in [2,3,4]:
  vals=[]
  for s in product(range(4),repeat=k): vals.append(D[:4,:4][np.ix_(s,s)].sum()/(k*(k-1)))
  assert np.isclose(np.var(vals),iid_var(moments(D[:4,:4]),k),atol=1e-11)

def precision(groups):
 rng=np.random.default_rng(SEED);curves=[];sens=[];stand=[];signals=[]
 for g in groups.values():
  if g['n']<20:continue
  D=g['D'];n=g['n'];mm=moments(D);perms=np.argsort(rng.random((B,n)),axis=1)
  medoids={};step={};quality={}
  for k in range(2,n+1):
   ids=perms[:,:k];sub=D[ids[:,:,None],ids[:,None,:]]
   pick=ids[np.arange(B),sub.sum(2).argmin(1)];medoids[k]=pick
   rem=perms[:,k:]
   peer=np.mean(D[pick[:,None],rem]) if k<n else np.nan
   quality[k]=float(np.nanmean(g['reference'][pick])) if np.isfinite(g['reference']).any() else np.nan
   step[k]=np.mean(D[medoids[k-1],pick]) if k>2 else np.nan
   curves.append(dict(context=g['context'],image=g['image'],building=g['building'],stage=g['stage'],condition=g['condition'],N=n,k=k,fraction=k/n,
                     full_disagreement=g['D_mean'],finite_sd=math.sqrt(finite_var(mm,k)),empirical_iid_sd=math.sqrt(iid_var(mm,k)),
                     selected_medoid_to_remaining=peer,selected_medoid_reference_distance=quality[k],medoid_step_distance=step[k],remaining=n-k,
                     iid_role='with_replacement_empirical_distribution_diagnostic_not_new_workers'))
  for eps in [.005,.01,.02]:
   kf=next(k for k in range(2,n+1) if math.sqrt(finite_var(mm,k))<=eps)
   ki=next((k for k in range(2,201) if math.sqrt(iid_var(mm,k))<=eps),np.nan)
   km=next((k for k in range(3,min(n,20)+1) if all(step[j]<=eps for j in range(k,min(n,20)+1))),np.nan)
   sens.append(dict(context=g['context'],image=g['image'],building=g['building'],stage=g['stage'],condition=g['condition'],N=n,epsilon=eps,
                    finite_first_k=kf,finite_fraction=kf/n,empirical_iid_first_k_to200=ki,
                    finite_pass20=kf<=20,iid_pass20=bool(np.isfinite(ki) and ki<=20),finite_only_pass20=bool(kf<=20 and not(np.isfinite(ki) and ki<=20)),
                    finite_sd20=math.sqrt(finite_var(mm,20)),iid_sd20=math.sqrt(iid_var(mm,20)),late_fraction_gt80=kf/n>.8,
                    medoid_hindsight_first_stable_k=km,medoid_rule='all_later_observed_steps_to20_below_same_numeric_tolerance_different_estimand'))
  for cutoff in [.03,.05,.07]:
   labs,order=modes(D,g['corners'],cutoff);second=np.sum(labs==order[1]) if len(order)>1 else 0
   supported=second>=2
   for k in range(2,n+1):
    capture=float(hypergeom.sf(1,n,second,k)) if supported else np.nan
    signals.append(dict(context=g['context'],image=g['image'],building=g['building'],stage=g['stage'],condition=g['condition'],N=n,k=k,fraction=k/n,
                        distance_cutoff=cutoff,second_mode_count=int(second),second_mode_supported=supported,second_mode_capture2=capture,
                        definition='two_drawn_members_of_full_empirical_second_complete_link_group; not_validated_alternative_truth'))
  # Standardize support to 20 on the same images, without inventing new responses.
  for rep in range(100):
   ids=rng.choice(n,20,replace=False);ms=moments(D[np.ix_(ids,ids)])
   for eps in [.005,.01,.02]:
    k=next(k for k in range(2,21) if math.sqrt(finite_var(ms,k))<=eps)
    stand.append(dict(context=g['context'],stage=g['stage'],condition=g['condition'],original_N=n,replicate=rep,epsilon=eps,standardized_N=20,first_k=k))
 save('precision_curves_k_and_fraction.csv',curves);save('denominator_tolerance_sensitivity.csv',sens)
 save('minority_capture_curves.csv',signals);save('standardized_N20_draws.csv',stand)
 ss=pd.DataFrame(sens);summary=ss.groupby(['epsilon','stage','condition'],sort=True).agg(contexts=('N','size'),N_min=('N','min'),N_max=('N','max'),
   finite_pass20=('finite_pass20','sum'),iid_diagnostic_pass20=('iid_pass20','sum'),finite_only_pass20=('finite_only_pass20','sum'),
   median_first_k=('finite_first_k','median'),median_fraction=('finite_fraction','median'),late_gt80=('late_fraction_gt80','sum')).reset_index()
 save('denominator_tolerance_summary.csv',summary)
 association=[]
 for eps,part in ss.groupby('epsilon'):
  y=part.finite_first_k.values; X=np.column_stack([np.ones(len(part)),part.N.values]);pred=X@np.linalg.lstsq(X,y,rcond=None)[0]
  rho,p=spearmanr(part.N,y)
  cat=pd.get_dummies(part.stage+'|'+part.condition,dtype=float);base=np.c_[np.ones(len(part)),cat.values]
  resy=y-base@np.linalg.lstsq(base,y,rcond=None)[0];resn=part.N.values-base@np.linalg.lstsq(base,part.N.values,rcond=None)[0]
  association.append(dict(epsilon=eps,N_only_R2=1-np.sum((y-pred)**2)/np.sum((y-y.mean())**2),spearman_N_k=rho,
                          within_stage_condition_slope=(resn@resy)/(resn@resn),interpretation='descriptive_not_causal_attribution'))
 save('N_association.csv',association)
 return pd.DataFrame(curves),ss,pd.DataFrame(signals)

FEATURES=['early_D','corner_mean','corner_sd','corner_pair_disagreement','bilayout_gap','hoho_enclosed_gap','hoho_extended_gap']

def early_data(groups):
 rng=np.random.default_rng(SEED+1);result=[]
 for g in groups.values():
  if g['n']<20:continue
  n=g['n'];D=g['D']
  for rep in range(B):
   p=rng.permutation(n)
   for k in [3,5]:
    s=p[:k];rest=p[k:];sub=D[np.ix_(s,s)];R=D[np.ix_(rest,rest)];c=g['corners'][s]
    counts=np.unique(c,return_counts=True)[1];corner_dis=(k*k-np.sum(counts**2))/(k*(k-1))
    restlabs,restorder=modes(R,g['corners'][rest],.05)
    second=rest[restlabs==restorder[1]] if len(restorder)>1 else np.array([],int)
    late_mode=False
    if len(second)>=2:
     med=second[D[np.ix_(second,second)].sum(1).argmin()]
     late_mode=not np.any((g['corners'][s]==g['corners'][med]) & (D[s,med]<=.05))
    result.append(dict(context=g['context'],image=g['image'],building=g['building'],stage=g['stage'],condition=g['condition'],
                        N=n,k=k,replicate=rep,early_workers=';'.join(map(str,g['workers'][s])),remaining_workers=';'.join(map(str,g['workers'][rest])),
                        early_indices=';'.join(map(str,s)),remaining_indices=';'.join(map(str,rest)),
                        early_D=sub.sum()/(k*(k-1)),corner_mean=c.mean(),corner_sd=c.std(),corner_pair_disagreement=corner_dis,
                        bilayout_gap=g['models'][0],hoho_enclosed_gap=g['models'][1],hoho_extended_gap=g['models'][2],
                        target=R.sum()/(len(rest)*(len(rest)-1)),late_second_mode_supported=len(second)>=2,late_mode_unseen=late_mode))
 return pd.DataFrame(result)

def pipeline(alpha):
 return make_pipeline(SimpleImputer(strategy='median',add_indicator=True,keep_empty_features=True),StandardScaler(),Ridge(alpha=alpha))

def predict(df):
 predrows=[];foldrows=[]
 modelsets={'calibrated_early':['early_D'],'early_plus_corners':FEATURES[:4],'early_plus_corners_models':FEATURES}
 for k,data in df.groupby('k'):
  data=data.copy().reset_index(drop=True);cats=pd.get_dummies(data.stage+'|'+data.condition,dtype=float)
  # These fixed design-condition indicators contain no target statistics.
  for building in sorted(data.building.unique()):
   tr=data.building!=building;te=~tr;train=data[tr];test=data[te]
   stage_means=train.groupby(['stage','condition']).target.mean();overall=train.target.mean()
   bas=np.array([stage_means.get((s,c),overall) for s,c in zip(test.stage,test.condition)])
   alternatives={'stage_condition_mean':bas,'direct_early_D':test.early_D.to_numpy()}
   qlow=train.groupby('context').early_D.mean().quantile(.25);qhigh=train.groupby('context').target.mean().quantile(.75)
   foldrows.append(dict(k=k,heldout_building=building,model='diagnostic_thresholds',train_images=train.image.nunique(),test_images=test.image.nunique(),
                         early_low_threshold=qlow,later_high_threshold=qhigh))
   for name,cols in modelsets.items():
    X=np.c_[data[cols].to_numpy(),cats.values];y=data.target.values
    # Regularization and preprocessing are chosen only inside the training buildings.
    losses={}
    for alpha in [.1,1.,10.,100.]:
     sse=[]
     for b in sorted(train.building.unique()):
      a=tr & (data.building!=b);v=tr & (data.building==b)
      fit=pipeline(alpha).fit(X[a],y[a]);sse.append(np.mean((fit.predict(X[v])-y[v])**2))
     losses[alpha]=np.mean(sse)
    best=min(losses,key=losses.get);fit=pipeline(best).fit(X[tr],y[tr]);alternatives[name]=fit.predict(X[te])
    foldrows.append(dict(k=k,heldout_building=building,model=name,selected_alpha=best,inner_building_MSE=losses[best],
                         train_images=train.image.nunique(),test_images=test.image.nunique(),feature_count=len(cols)))
   for name,values in alternatives.items():
    part=test.copy();part['model']=name;part['prediction']=values;part['baseline']=bas
    part['underestimate']=part.target-part.prediction;part['squared_error']=(part.target-part.prediction)**2
    part['absolute_error']=abs(part.target-part.prediction);part['baseline_sqerror']=(part.target-part.baseline)**2
    part['early_low_train_cutoff']=qlow;part['late_high_train_cutoff']=qhigh
    part['false_reassurance']=(part.early_D<=qlow)&(part.target>=qhigh)
    predrows.append(part)
 P=pd.concat(predrows,ignore_index=True)
 # Repeated subsets integrate finite-panel draws; inference does not count them as independent images.
 save('early_prediction_all_draws.csv.gz',P);save('early_prediction_training_audit.csv',foldrows)
 summary=[];bb=[]
 for (k,name),p in P.groupby(['k','model']):
  by=p.groupby('context').agg(MSE=('squared_error','mean'),MAE=('absolute_error','mean'),base=('baseline_sqerror','mean'))
  b=p.groupby('building').agg(MSE=('squared_error','mean'),base=('baseline_sqerror','mean'))
  summary.append(dict(k=k,model=name,contexts=len(by),buildings=len(b),draws=len(p),RMSE=np.sqrt(by.MSE.mean()),MAE=by.MAE.mean(),
                      R2_vs_train_stage_condition_mean=1-by.MSE.mean()/by.base.mean(),building_equal_R2=1-b.MSE.mean()/b.base.mean(),
                      underestimate_q95=p.underestimate.quantile(.95),underestimate_max=p.underestimate.max(),negative_prediction_rate=(p.prediction<0).mean()))
  for building,q in p.groupby('building'):
   bb.append(dict(k=k,model=name,building=building,images=q.image.nunique(),RMSE=np.sqrt(q.squared_error.mean()),MAE=q.absolute_error.mean(),
                 mean_underestimate=q.underestimate.mean(),max_underestimate=q.underestimate.max(),R2_vs_baseline=1-q.squared_error.mean()/q.baseline_sqerror.mean()))
 save('early_prediction_baselines.csv',summary);save('early_prediction_by_building.csv',bb)
 worst=P.sort_values('underestimate',ascending=False).groupby(['k','model','context'],sort=False).head(1)
 save('early_prediction_worst_cases.csv',worst.groupby(['k','model'],sort=False).head(15))
 save('early_prediction_false_reassurance.csv',P[(P.model=='early_plus_corners_models') & P.false_reassurance].sort_values('underestimate',ascending=False).groupby(['k','context'],sort=False).head(1))
 # Paired task-balanced loss differences; building bootstrap conditions on the observed roster.
 contrasts=[];rng=np.random.default_rng(SEED+2)
 for k,p in P.groupby('k'):
  pv=p.groupby(['building','context','model']).squared_error.mean().unstack('model')
  for name,comparator in [(name,'direct_early_D') for name in modelsets]+[('early_plus_corners_models','calibrated_early'),('early_plus_corners','calibrated_early')]:
   delta=(pv[name]-pv[comparator]).groupby(level='building').mean(); vals=delta.values
   draws=np.mean(rng.choice(vals,size=(3000,len(vals)),replace=True),axis=1)
   contrasts.append(dict(k=k,comparison=name+' minus '+comparator,MSE_difference_building_equal=vals.mean(),
                          building_bootstrap_q025=np.quantile(draws,.025),building_bootstrap_q975=np.quantile(draws,.975),
                          interpretation='conditional_observed_workers_exploratory_no_multiple_testing_claim'))
 save('early_prediction_incremental_gain.csv',contrasts)
 return P

if __name__=='__main__':
 rows,groups,refs=load();check_math();precision(groups);df=early_data(groups);predict(df)
 print('DONE statistics',len(df),flush=True)
