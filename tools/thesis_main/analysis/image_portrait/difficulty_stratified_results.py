"""All-candidate results, inner-only layer selection, fair paired increments."""
from __future__ import annotations
import json,itertools
import numpy as np,pandas as pd
from sklearn.metrics import confusion_matrix,f1_score,balanced_accuracy_score
from tools.thesis_main.analysis.image_portrait.difficulty_stratified_cv import *

def measure(g):
 p=g[['p0','p1','p2']].to_numpy(float);y=g.y.to_numpy(int);pred=p.argmax(1);cm=confusion_matrix(y,pred,labels=[0,1,2]);rec=np.divide(np.diag(cm),cm.sum(1),out=np.full(3,np.nan),where=cm.sum(1)>0)
 out=dict(n_images=len(g),n_buildings=g.building.nunique(),rps_mean=float(rps(p,y).mean()),brier_mean=float(brier(p,y).mean()),accuracy=float(np.mean(pred==y)),balanced_accuracy=float(np.nanmean(rec)),macro_f1=float(np.mean(np.divide(2*np.diag(cm),cm.sum(0)+cm.sum(1),out=np.zeros(3,dtype=float),where=cm.sum(0)+cm.sum(1)>0)[np.unique(y)])),building_macro_rps=float(g.groupby('building').rps.mean().mean()),simple_recall=rec[0],medium_recall=rec[1],hard_recall=rec[2],simple_n=int((y==0).sum()),medium_n=int((y==1).sum()),hard_n=int((y==2).sum()))
 return out

def select_families(parent='pooled'):
 field='main_function_primary'if parent=='within_main'else'scene_category'
 d=pd.read_csv(O/'images/labels106.csv');y=d.y.to_numpy(int);buildings=sorted(d.building.unique());paths=sorted((O/'cv'/parent).glob('*.inner.npz'))
 arrays={p.name.removesuffix('.inner.npz'):dict(np.load(p,allow_pickle=False))for p in paths};families={}
 for m in ['hohonet','bilayout','ulayout','dinov3','da3','feedback','semantic']:families[m]=[n for n in arrays if n.startswith(m+'__')]
 families['existing']=[n for n in arrays if n.split('__')[0]in ['hohonet','bilayout','ulayout','da3','feedback']]
 families['all_models']=families['existing']+families['dinov3']
 result=[];settings=[];chosen={}
 for family,names in families.items():
  if not names:continue
  for mi,mode in enumerate(MODES):
   for alg in ['ridge','knn']:
    opts=[j for j,g in enumerate(GRID)if g['algorithm']==alg]
    for ob,b in enumerate(buildings):
     te=np.flatnonzero(d.building.to_numpy()==b);tr=np.flatnonzero(d.building.to_numpy()!=b)
     subgroups=d.iloc[te].groupby(field).groups.values()if parent!='pooled'else[te]
     for ev in subgroups:
      ev=np.array(list(ev));ix=tr[d[field].to_numpy()[tr]==d[field].iloc[ev[0]]]if parent!='pooled'else tr
      candidates=[]
      for name in names:
       for j in opts:
        a=arrays[name]['inner'][ob,mi,j,ix];good=np.isfinite(a).all(1)
        loss=float(rps(a[good],y[ix][good]).mean())if good.any()else np.inf
        candidates.append((loss,bool(GRID[j]['pca']),GRID[j]['pca'],-GRID[j]['alpha'],GRID[j]['k'],name,j,int(good.sum())))
      best=min(candidates);loss,*_,name,j,ni=best
      if not np.isfinite(loss):name=names[0];j=next(j for j,g in enumerate(GRID)if g['algorithm']==alg and g['pca']==0 and(g['alpha']==10 if alg=='ridge'else g['k']==1))
      p=arrays[name]['outer'][ob,mi,j,ev]
      for i,pp in zip(ev,p):
       status='no_training_in_stratum_global_fallback'if parent!='pooled'and len(ix)==0 else'ok'
       if not np.isfinite(pp).all():pp=cat_probs(d,tr,[i],mode)[0];status='no_stratum_training_fallback'
       result.append(dict(image_id=d.image_id.iloc[i],building=b,scene=d.scene_category.iloc[i],main_space=d.main_function_primary.iloc[i],y=int(y[i]),feature='selected__'+family,baseline=mode,algorithm=alg,design=parent,p0=pp[0],p1=pp[1],p2=pp[2],prediction=int(pp.argmax()),rps=float(rps(pp,y[i])),brier=float(brier(pp,y[i])),status=status))
      settings.append(dict(family=family,baseline=mode,algorithm=alg,building=b,stratum=d[field].iloc[ev[0]]if parent!='pooled'else'all',feature=name,grid=j,inner_loss=loss,n_inner=ni))
      chosen[family,mode,alg,b,('all'if parent=='pooled'else d[field].iloc[ev[0]])]=(arrays[name]['inner'][ob,mi,j].copy(),arrays[name]['outer'][ob,mi,j].copy(),name,j)
 print('SELECTED',parent,len(result),flush=True)
 # Blend family-selected existing output and DINO, with weight chosen on outer training only.
 for mode in MODES:
  for alg in ['ridge','knn']:
   for b in buildings:
    tr0=np.flatnonzero(d.building.to_numpy()!=b);ev0=np.flatnonzero(d.building.to_numpy()==b)
    panels=d.iloc[ev0].groupby(field).groups.values()if parent!='pooled'else[ev0]
    for ev in panels:
     ev=np.asarray(list(ev),int);stratum='all'if parent=='pooled'else d[field].iloc[ev[0]];tr=tr0 if parent=='pooled'else tr0[d[field].to_numpy()[tr0]==stratum]
     a,ao,an,aj=chosen['existing',mode,alg,b,stratum];z,zo,zn,zj=chosen['dinov3',mode,alg,b,stratum];weights=[0,.25,.5,.75,1.]
     ix=tr[np.isfinite(a[tr]).all(1)&np.isfinite(z[tr]).all(1)]
     losses=[float(rps((1-w)*a[ix]+w*z[ix],y[ix]).mean())if len(ix)else np.inf for w in weights];w=weights[int(np.argmin(losses))];p=(1-w)*ao[ev]+w*zo[ev]
     for i,pp in zip(ev,p):
      status='no_training_in_stratum_global_fallback'if parent!='pooled'and len(tr)==0 else'ok'
      if not np.isfinite(pp).all():pp=cat_probs(d,tr0,[i],mode)[0];status='no_training_in_stratum_global_fallback'
      result.append(dict(image_id=d.image_id.iloc[i],building=b,scene=d.scene_category.iloc[i],main_space=d.main_function_primary.iloc[i],y=int(y[i]),feature='selected__existing_plus_dino',baseline=mode,algorithm=alg,design=parent,p0=pp[0],p1=pp[1],p2=pp[2],prediction=int(pp.argmax()),rps=float(rps(pp,y[i])),brier=float(brier(pp,y[i])),status=status))
     settings.append(dict(family='existing_plus_dino',baseline=mode,algorithm=alg,building=b,stratum=stratum,feature=an+' + '+zn,grid=str(aj)+'/'+str(zj),inner_loss=min(losses),n_inner=len(ix),dino_weight=w))
 csv('results/'+parent+'_selected_predictions.csv.gz',result);csv('results/'+parent+'_selection_details.csv',settings)
 return pd.DataFrame(result)

def paired(a,b,title,scope='all'):
 keys=['image_id'];q=a.merge(b,on=keys,suffixes=('_a','_b'));assert not q.image_id.duplicated().any()
 if not len(q):return None
 assert (q.y_a==q.y_b).all();delta=q.rps_a-q.rps_b;correct=(q.prediction_a==q.y_a).astype(float)-(q.prediction_b==q.y_b).astype(float);q=q.assign(delta=delta,accuracy_delta=correct)
 grouped=q.groupby('building_a')[['delta','accuracy_delta']].agg(['sum','count','mean']);rng=np.random.default_rng(SEED);nb=len(grouped);ix=rng.integers(nb,size=(10000,nb));arr=grouped.to_numpy();dr=arr[ix,0].sum(1)/arr[ix,1].sum(1);dm=arr[ix,2].mean(1);ar=arr[ix,3].sum(1)/arr[ix,4].sum(1)
 return dict(comparison=title,scope=scope,n_images=len(q),n_buildings=nb,rps_a=q.rps_a.mean(),rps_b=q.rps_b.mean(),rps_delta=delta.mean(),rps_delta_lo=np.quantile(dr,.025),rps_delta_hi=np.quantile(dr,.975),building_macro_delta=grouped[('delta','mean')].mean(),building_macro_lo=np.quantile(dm,.025),building_macro_hi=np.quantile(dm,.975),accuracy_delta=correct.mean(),accuracy_lo=np.quantile(ar,.025),accuracy_hi=np.quantile(ar,.975),ci_kind='paired building bootstrap; conditional on this exploratory dataset, no fresh confirmation')

def summarize():
 d=pd.read_csv(O/'images/labels106.csv');dfs=[pd.read_csv(O/'cv/baselines.csv')]
 for parent in ['pooled','within_coarse','within_main']:
  paths=sorted(p for p in (O/'cv'/parent).glob('*.csv.gz') if not p.name.startswith('control__'));dfs.extend(pd.read_csv(p)for p in paths)
  if paths:dfs.append(select_families(parent))
 allp=pd.concat(dfs,ignore_index=True)
 for design,field in [('within_coarse','scene_category'),('within_main','main_function_primary')]:
  zero_ids={d.image_id.iloc[i]for i in range(len(d))if not((d[field]==d[field].iloc[i])&(d.building!=d.building.iloc[i])).any()}
  allp.loc[(allp.design==design)&allp.image_id.isin(zero_ids),'status']='no_training_in_stratum_global_fallback'
 csv('results/all_oof_predictions.csv.gz',allp)
 keys=['design','feature','baseline','algorithm'];summary=[];strata=[];cm=[]
 for kk,g in allp.groupby(keys):
  assert len(g)==106 and g.image_id.nunique()==106,(kk,len(g))
  row=dict(zip(keys,kk));summary.append(dict(row,**measure(g)))
  for field in ['scene','main_space','building']:
   for cat,x in g.groupby(field):strata.append(dict(row,stratum_type=field,stratum=cat,**measure(x)))
  for true in range(3):
   for pred in range(3):cm.append(dict(row,true=LABELS[true],predicted=LABELS[pred],count=int(((g.y==true)&(g.prediction==pred)).sum())))
 csv('results/all_candidate_scores.csv',summary);csv('results/stratified_scores.csv',strata);csv('results/confusion_matrices.csv',cm)
 base=pd.read_csv(O/'cv/baselines.csv');pairs=[]
 def get(name,mode='none',alg='frequency',design='pooled'):return allp[(allp.feature==name)&(allp.baseline==mode)&(allp.algorithm==alg)&(allp.design==design)]
 for m in ['coarse','main','fine','human_focus','coarse_main']:
  pairs.append(paired(get('baseline__'+m),get('baseline__global'),m+' vs global'))
 pairs.append(paired(get('baseline__main'),get('baseline__coarse'),'main vs coarse'))
 for family in ['hohonet','bilayout','ulayout','dinov3','da3','feedback','semantic','existing','all_models','existing_plus_dino']:
  for mode in MODES:
   for alg in ['ridge','knn']:
    a=get('selected__'+family,mode,alg)
    if not len(a):continue
    for bm in ['coarse','main']:
     for scope in ['all','卧室','卫浴','厨房与用餐','工作与学习']:
      b=get('baseline__'+bm)
      aa=a if scope=='all'else a[a.scene==scope];bb=b if scope=='all'else b[b.scene==scope]
      pairs.append(paired(aa,bb,family+'['+mode+','+alg+'] vs '+bm,scope))
 for mode in MODES:
  for alg in ['ridge','knn']:
   for family in ['dinov3','existing_plus_dino','all_models']:
    for scope in ['all','卧室','卫浴','厨房与用餐']:
     a=get('selected__'+family,mode,alg);b=get('selected__existing',mode,alg)
     pairs.append(paired(a if scope=='all'else a[a.scene==scope],b if scope=='all'else b[b.scene==scope],family+' vs existing ['+mode+','+alg+']',scope))
   for family in ['dinov3','existing','all_models','semantic']:
    for design in ['within_coarse','within_main']:
     a=get('selected__'+family,mode,alg,design);b=get('selected__'+family,mode,alg)
     if len(a):pairs.append(paired(a,b,design+' vs pooled '+family+'['+mode+','+alg+']'))
 for design in ['within_coarse','within_main']:
  for mode in MODES:
   for alg in ['ridge','knn']:
    for fam in ['existing','feedback','dinov3','existing_plus_dino','all_models']:
     a=get('selected__'+fam,mode,alg,design)
     for bn in ['baseline__coarse','baseline__main']:
      pairs.append(paired(a,get(bn),design+' '+fam+'['+mode+','+alg+'] vs '+bn))
     if fam in ['dinov3','existing_plus_dino','all_models']:
      pairs.append(paired(a,get('selected__existing',mode,alg,design),design+' '+fam+' vs existing ['+mode+','+alg+']'))
    pairs.append(paired(get('selected__existing',mode,alg,design),get('selected__feedback',mode,alg,design),design+' existing vs feedback ['+mode+','+alg+']'))
 csv('results/paired_increments.csv',[x for x in pairs if x is not None])
 # Same held-out predictions, room macro restricted to relation eligible components only.
 q=allp.merge(d[['image_id','room_id','room_status','source_split']],on='image_id');rr=[]
 for kk,g in q.groupby(keys):
  elig=g[g.room_status=='supported_component'];vals=elig.groupby('room_id').rps.mean()
  rr.append(dict(zip(keys,kk),n_relation_eligible_images=len(elig),n_supported_components=len(vals),supported_component_macro_rps=vals.mean(),total_images=len(g)))
 csv('results/supported_component_macro.csv',rr)
 ss=[]
 for kk,g in q.groupby(keys+['source_split']):ss.append(dict(zip(keys+['source_split'],kk),**measure(g)))
 csv('results/source_split_scores.csv',ss)
 print(pd.DataFrame(summary).query("feature.str.startswith('baseline__') or (feature.str.startswith('selected__') and baseline=='main' and algorithm=='ridge')",engine='python')[['design','feature','rps_mean','accuracy','balanced_accuracy']].to_string(index=False))
if __name__=='__main__':summarize()
