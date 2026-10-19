"""Independent linear headline screen check from freshly fused team records.
No call to screen_candidates.regress/ridge_predict/aggregate_errors.
"""
import os
for k in ['OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS']:os.environ[k]='1'
import argparse,gzip,hashlib,json
from pathlib import Path
import numpy as np,pandas as pd
P=Path('/workspace/shared/composition_audit_20261019/extracted/personnel_composition_study_20261019/analysis')
METRICS=['B8L2','D10','iou_2d','IoU3D100','ref_node_recall_9','ref_edge_recall_9','omission','extension']
SELECTED=[('F_rule_Q_quantile_K5','all'),('F_rule_Q_threshold_K3','all'),('F_medoids_S_K4','all'),('F_rule_Q2xDetail2','all'),('R_role_ward_K5','all'),('R_geo9_spectral_p2_K3','all'),('R_geo9_source_signed_p2_K2','all'),('R_role_ward_difficulty_K2','hard')]
def read(p):
 with gzip.open(p,'rt') as f:return json.load(f)
def fit_predict(X,Y,Z,w):
 scale=np.sqrt(np.average(X**2,axis=0,weights=w)); good=scale>1e-10
 if not good.any():return np.zeros((len(Z),Y.shape[1]))
 X=X[:,good]/scale[good];Z=Z[:,good]/scale[good]
 beta=np.linalg.solve((X*w[:,None]).T@X+10*np.eye(X.shape[1]),(X*w[:,None]).T@Y)
 return Z@beta
def crossfit(frame,X,C,Y,controlled):
 pred=np.full(Y.shape,np.nan);base=pred.copy();ctrl=pred.copy()
 for fold in [0,1]:
  train=frame.fold.ne(fold).to_numpy();test=~train
  tc=frame.loc[train].groupby('cell').size();sc=frame.loc[test].groupby('cell').size()
  cells=set(tc[tc>=3].index)&set(sc[sc>=2].index)
  train &= frame.cell.isin(cells).to_numpy();test &= frame.cell.isin(cells).to_numpy()
  if train.sum()<10 or test.sum()<2:continue
  counts=frame.loc[train].groupby('cell').size()
  centered=[];means=[]
  for v in [X,C,Y]:
   vf=pd.DataFrame(v);vf['cell']=frame.cell.to_numpy(); mu=vf.loc[train].groupby('cell').mean().reindex(frame.cell).to_numpy()
   centered.append(v-mu);means.append(mu)
  x,c,y=centered;w=1/frame.loc[train,'cell'].map(counts).to_numpy();w*=train.sum()/w.sum()
  base[test]=means[2][test]
  design=np.column_stack([c,x]) if controlled else x
  pred[test]=base[test]+fit_predict(design[train],y[train],design[test],w)
  if controlled:ctrl[test]=base[test]+fit_predict(c[train],y[train],c[test],w)
 return pred,base,ctrl

def main():
 ap=argparse.ArgumentParser();ap.add_argument('--runs',type=Path,required=True);ap.add_argument('--requests',type=Path,required=True);ap.add_argument('--out',type=Path,required=True);a=ap.parse_args();a.out.mkdir(parents=True,exist_ok=True)
 req=read(a.requests)['requests'];expected={r['team_key']:r for r in req};assert len(expected)==len(req)
 teams=[]
 for pool in sorted({r['pool_id'] for r in req}):
  for t in read(a.runs/'pools'/(pool+'.json.gz'))['teams']:
   if t['team_key'] in expected:
    assert sorted(t['member_workers'])==sorted(expected[t['team_key']]['worker_ids']);teams.append(t)
 assert len(teams)==len(req);teams.sort(key=lambda t:t['team_key']);split=json.loads((P/'composition/SPLIT.json').read_text());assert all(t['building'] in split['discovery_buildings'] for t in teams)
 f=pd.read_csv(P/'forward/results/features_train.csv.gz').set_index('worker_id').sort_index();ws=list(f.index);wi={w:i for i,w in enumerate(ws)};inc=np.zeros((len(teams),len(ws)))
 for i,t in enumerate(teams):inc[i,[wi[w] for w in t['member_workers']]]=1
 n=inc.sum(1); y=np.array([[np.nan if t.get(m) is None else t[m] for m in METRICS] for t in teams]);full=np.isfinite(y).all(1);b8=np.isfinite(y[:,0]);bad=[]
 for i in np.flatnonzero(b8&~full):bad.append({'team_key':teams[i]['team_key'],'missing_metrics':','.join(m for m,v in zip(METRICS,y[i]) if not np.isfinite(v))})
 pd.DataFrame(bad,columns=['team_key','missing_metrics']).to_csv(a.out/'b8_valid_quality_mask_exclusions.csv',index=False)
 frame=pd.DataFrame([{k:t[k] for k in ['team_key','pool_id','building','difficulty','k']} for t in teams]);frame['cell']=frame.pool_id+'|'+frame.k.astype(str);frame['fold']=[int(hashlib.sha256(f'2026101961|{key}'.encode()).hexdigest()[:12],16)%2 for key in frame.team_key];frame['difficulty']=frame.difficulty.replace({'简单':'easy','中等':'medium','困难':'hard'})
 labs=pd.concat([pd.read_csv(P/'forward/results/worker_labels.csv.gz'),pd.read_csv(P/'reverse/worker_labels.csv.gz')]);labs.domain=labs.domain.replace({'global':'all'});newprop=inc@f.person_origin.eq('new').to_numpy(float)/n;globalq=inc@f.q_beta.to_numpy()/n
 rows=[];coverage=[]
 for mid,dom in SELECTED:
  g=labs[(labs.method_id==mid)&(labs.domain==dom)&labs.known].set_index('worker_id');known=np.array([w in g.index for w in ws],float);eligible=(inc@known==n)&(frame.difficulty.eq(dom).to_numpy() if dom!='all' else True)
  classes=sorted(g.class_id.unique());M=np.array([[float(w in g.index and g.loc[w,'class_id']==c) for c in classes] for w in ws]);X=inc@M/n[:,None]
  for panel in ['native_support','shared_new35']:
   supported=eligible&(newprop==1 if panel=='shared_new35' else True)
   coverage.append(dict(method_id=mid,domain=dom,panel=panel,eligible=int(supported.sum()),b8_finite=int((supported&b8).sum()),all_quality_finite=int((supported&full).sum()),b8_valid_excluded=int((supported&b8&~full).sum())))
   defs=['q_beta_plus_source'] if dom=='all' else ['q_beta_plus_source','theta_hard_plus_source','q_beta_theta_hard_plus_source']
   for definition in defs:
    knownq=np.ones(len(teams),bool);C=np.column_stack([globalq,newprop])
    if definition!='q_beta_plus_source':
     v=f.theta_hard.to_numpy();knownq=inc@np.isfinite(v).astype(float)==n;hq=inc@np.nan_to_num(v,nan=0)/n;C=np.column_stack([hq,newprop]) if definition=='theta_hard_plus_source' else np.column_stack([globalq,hq,newprop])
    keep=supported&full&knownq;z=frame.loc[keep].reset_index(drop=True);Y=y[keep]
    for controlled in [False,True]:
     if not controlled and definition!='q_beta_plus_source':continue
     pred,base,cp=crossfit(z,X[keep],C[keep],Y,controlled)
     for j,m in enumerate(METRICS):
      take=np.isfinite(pred[:,j])&np.isfinite(base[:,j]);e=z.loc[take,['pool_id','building','k']].copy();e['base']=(Y[take,j]-base[take,j])**2;e['model']=(Y[take,j]-pred[take,j])**2;e['control']=(Y[take,j]-cp[take,j])**2
      cells=e.groupby(['pool_id','building','k'])[['base','model','control']].mean();ims=cells.groupby(['pool_id','building']).mean();build=ims.groupby('building').mean();mean=build.mean()
      rows.append(dict(method_id=mid,domain=dom,panel=panel,model='linear',controlled=controlled,control_definition=definition,outcome=m,tested_teams=int(take.sum()),images=len(ims),buildings=len(build),baseline_mse=mean['base'],model_mse=mean['model'],Q_origin_baseline_mse=mean['control'],mse_reduction_fraction=1-mean['model']/mean['base'],additional_reduction_over_Q_origin=1-mean['model']/mean['control']))
 result=pd.DataFrame(rows);result.to_csv(a.out/'independent_headline_screen.csv',index=False);pd.DataFrame(coverage).to_csv(a.out/'finite_denominator_by_candidate.csv',index=False)
 old=pd.read_csv(P/'forward/screen_final/screen_outcomes.csv.gz');old=old[(old.model=='linear')&old.outcome.isin(METRICS)];common=result[result.control_definition=='q_beta_plus_source'].merge(old,on=['method_id','domain','panel','model','controlled','outcome'],suffixes=('_fresh','_saved'),validate='one_to_one');diffs={c:float((common[c+'_fresh']-common[c+'_saved']).abs().max()) for c in ['tested_teams','images','buildings','baseline_mse','model_mse','Q_origin_baseline_mse','mse_reduction_fraction','additional_reduction_over_Q_origin']};common.to_csv(a.out/'headline_vs_saved.csv',index=False)
 hard=pd.read_csv(P/'forward/screen_final/hard_control_sensitivity.csv');hard=hard[(hard.model=='linear')&hard.outcome.isin(METRICS)];hj=result[(result.method_id=='R_role_ward_difficulty_K2')&result.controlled].merge(hard,on=['method_id','domain','panel','model','controlled','outcome','control_definition'],suffixes=('_fresh','_saved'),validate='one_to_one');hd={c:float((hj[c+'_fresh']-hj[c+'_saved']).abs().max()) for c in diffs};hj.to_csv(a.out/'hard_controls_vs_saved.csv',index=False)
 report=dict(teams=len(teams),b8_finite=int(b8.sum()),quality_group_finite=int(full.sum()),b8_valid_excluded_other_metrics=len(bad),methods=len(SELECTED),rows=len(result),common_comparison_rows=len(common),maximum_differences=diffs,hard_comparison_rows=len(hj),hard_maximum_differences=hd);(a.out/'SCREEN_AUDIT_RECEIPT.json').write_text(json.dumps(report,indent=2));print(json.dumps(report,indent=2))
if __name__=='__main__':main()
