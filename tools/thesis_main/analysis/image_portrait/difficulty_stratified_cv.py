"""Nested fixed leave-building evaluation of subjective difficulty labels.

No visual inference. All standardization, PCA, text vocabulary and tuning train-side.
Ridge fits class indicator vectors; probabilities are clipped and renormalized.
The primary tuning loss is cumulative Brier/RPS (order, not equal metric spacing).
"""
from __future__ import annotations
import argparse,itertools,json,time,os,concurrent.futures
import numpy as np,pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from tools.thesis_main.analysis.image_portrait.difficulty_stratified_prepare import *
MODES=['global','coarse','main']
GRID=[]
for p in [0,16,32]:
 for a in [100.,10.,1.,.1]:GRID.append(dict(algorithm='ridge',pca=p,alpha=a,k=0))
 for k in [1,3,5]:GRID.append(dict(algorithm='knn',pca=p,alpha=0.,k=k))

def prob(x):
 x=np.clip(x,1e-6,1);return x/x.sum(-1,keepdims=True)
def rps(p,y):return np.mean((np.cumsum(p,axis=-1)[...,:2]-(np.asarray(y)[...,None]<=np.arange(2)))**2,axis=-1)
def brier(p,y):return np.sum((p-np.eye(3)[y])**2,axis=-1)
def cat_probs(d,train,ev,mode='global',strength=3.):
 yt=d.y.to_numpy(int);prior=(np.bincount(yt[train],minlength=3)+.5)/(len(train)+1.5)
 def level(field,idx,parent):
  vals=d[field].fillna('unknown').astype(str).to_numpy();out=[]
  for i in idx:
   group=train[vals[train]==vals[i]];ct=np.bincount(yt[group],minlength=3)
   par=parent[i]if isinstance(parent,dict)else parent
   out.append((ct+strength*par)/(len(group)+strength))
  return np.asarray(out)
 if mode=='global':return np.tile(prior,(len(ev),1))
 if mode in ['coarse','main','fine','human_focus']:
  field={'coarse':'scene_category','main':'main_function_primary','fine':'fine_ai','human_focus':'main_space_human'}[mode];return level(field,ev,prior)
 if mode=='coarse_main':
  field='joint_key';d=d.copy();d[field]=d.scene_category.astype(str)+'::'+d.main_function_primary.astype(str)
  parent=dict(zip(ev,level('scene_category',ev,prior)));return level(field,ev,parent)
 raise ValueError(mode)

def kernels(X,train,ev,texts=None):
 if texts is not None:
  vec=TfidfVectorizer(analyzer='char',ngram_range=(2,4),min_df=2,max_features=2000)
  try:A=vec.fit_transform(texts[train]).toarray();V=vec.transform(texts[ev]).toarray()
  except ValueError:A=np.zeros((len(train),1));V=np.zeros((len(ev),1))
 else:A=np.asarray(X[train],float);V=np.asarray(X[ev],float)
 mu=A.mean(0);sd=A.std(0);sd[sd<1e-8]=1.;A=(A-mu)/sd;V=(V-mu)/sd
 K=A@A.T;E=V@A.T;diagv=np.einsum('ij,ij->i',V,V)
 eig,U=np.linalg.eigh((K+K.T)*.5);order=np.argsort(eig)[::-1];eig=np.maximum(eig[order],0);U=U[:,order]
 return K,E,diagv,eig,U

def grids(X,d,train,ev,modes=MODES,texts=None):
 K,E,diagv,lam,U=kernels(X,train,ev,texts)
 bases_tr=np.array([cat_probs(d,train,train,m)for m in modes]);bases_ev=np.array([cat_probs(d,train,ev,m)for m in modes])
 Y=np.eye(3)[d.y.to_numpy(int)[train]][None]-bases_tr;inter=Y.mean(1,keepdims=True);YC=Y-inter
 proj=np.einsum('ij,mjc->mic',U.T,YC);EU=E@U
 output=[]
 valid=lam>max(1e-10,lam[0]*1e-12)
 for param in GRID:
  count=len(train)if not param['pca']else min(param['pca'],len(train)-1,len(valid));mask=valid.copy();mask[count:]=False
  if param['algorithm']=='ridge':
   co=mask/(lam+param['alpha']);a=np.einsum('ij,mjc->mic',EU*co,proj)
  else:
   if not param['pca']:dist=diagv[:,None]+np.diag(K)[None]-2*E
   else:
    ZT=U[:,mask]*np.sqrt(lam[mask]);ZE=EU[:,mask]/np.sqrt(lam[mask]);dist=(ZE**2).sum(1)[:,None]+(ZT**2).sum(1)[None]-2*(ZE@ZT.T)
   ix=np.argsort(dist,axis=1,kind='stable')[:,:min(param['k'],len(train))];a=np.array([target[ix].mean(1)for target in YC])
  output.append(prob(bases_ev+a+inter))
 return np.stack(output,axis=1).astype(np.float32)

def make_metadata_features(d):
 fixed=['main_'+x for x in FUNCTIONS]+['position_'+x for x in POSITIONS]
 # Only schema levels from the separately supplied image metadata, not outcome-selected categories.
 specifications={
 'semantic__main_keywords':d[fixed].astype(float).to_numpy(),
 'semantic__position_keywords':d[['position_'+x for x in POSITIONS]].astype(float).to_numpy(),
 'semantic__ai_fine_functions':pd.get_dummies(d.fine_ai.str.get_dummies('|')).to_numpy(float),
 'semantic__coarse':pd.get_dummies(d.scene_category).to_numpy(float),
 'semantic__main_primary':pd.get_dummies(d.main_function_primary).to_numpy(float),
 'semantic__traits':pd.get_dummies(d[TRAITS+['doorway']].fillna('unknown')).to_numpy(float),
 'semantic__traits_recheck':pd.get_dummies(d[[t+'_recheck'for t in TRAITS]+['doorway']].fillna('unknown')).to_numpy(float)}
 for k,x in specifications.items():np.save(O/'cache'/f'{k}.npy',x.astype(np.float32))
 return list(specifications)+['semantic__main_text']

def run_feature(name,within=False):
 t0=time.time();d=pd.read_csv(O/'images/labels106.csv');d['y']=d.y.astype(int)
 texts=d.main_space_safe.fillna('').astype(str).to_numpy()if name=='semantic__main_text'else None
 X=None if texts is not None else np.load(O/'cache'/f'{name}.npy',mmap_mode='r')
 y=d.y.to_numpy();buildings=sorted(d.building.unique());n=len(d);nb=len(buildings)
 field='main_function_primary'if within=='main'else'scene_category'
 parent=('within_main'if within=='main'else'within_coarse')if within else'pooled';dest=O/'cv'/parent;dest.mkdir(parents=True,exist_ok=True)
 paths=(dest/(name+'.csv.gz'),dest/(name+'.inner.npz'))
 if all(p.exists()for p in paths):
  cached=pd.read_csv(paths[0]);counts=d.groupby([field,'building']).size()
  if within:
   zero_ids={d.image_id.iloc[i]for i in range(len(d))if not((d[field]==d[field].iloc[i])&(d.building!=d.building.iloc[i])).any()}
   cached.loc[cached.image_id.isin(zero_ids),'status']='no_training_in_stratum_global_fallback';cached.to_csv(paths[0],index=False)
  return name,'cached'
 # Outer predictions and inner out-of-fold probabilities, full candidate inventory retained.
 inner=np.full((nb,3,len(GRID),n,3),np.nan,np.float32);outer_grid=np.full_like(inner,np.nan);fails=[]
 groups=d.groupby(field).indices if within else{'all':np.arange(n)}
 for group,indices in groups.items():
  indices=np.asarray(indices);bs=[b for b in buildings if np.any(d.building.to_numpy()[indices]==b)]
  bvalues=d.building.to_numpy()
  for size in [1,2]:
   for excluded in itertools.combinations(bs,size):
    tr=indices[~np.isin(bvalues[indices],excluded)];ev=indices[np.isin(bvalues[indices],excluded)]
    if len(tr)==0:
     # Honest global fallback for an unseen stratum, not fit from held-out labels.
     for b in excluded:
      ob=buildings.index(b);fit=np.flatnonzero(~np.isin(bvalues,excluded));ix=ev[bvalues[ev]==b]
      p=cat_probs(d,fit,ix,'global')if len(fit)else np.full((len(ix),3),1/3)
      if size==1:outer_grid[ob,:,:,ix,:]=np.broadcast_to(p[:,None,None,:],(len(ix),3,len(GRID),3))
     fails.append(dict(feature=name,stratum=group,excluded=';'.join(excluded),reason='no_training_in_stratum',n_test=len(ev)))
     continue
    p=grids(X,d,tr,ev,texts=texts)
    if size==1:
     ob=buildings.index(excluded[0]);outer_grid[ob][:,:,ev,:]=p
    else:
     for b in excluded:
      ob=buildings.index(b);mask=bvalues[ev]!=b;inner[ob][:,:,ev[mask],:]=p[:,:,mask,:]
 records=[];settings=[]
 for ob,b in enumerate(buildings):
  te=np.flatnonzero(d.building.to_numpy()==b);training=np.flatnonzero(d.building.to_numpy()!=b)
  # In a stratified scheme tuning is also local to the target category.
  subgroups=d.iloc[te].groupby(field).groups.values()if within else[te]
  for subte in subgroups:
   subte=np.asarray(list(subte),int);seltrain=training[d[field].to_numpy()[training]==d[field].iloc[subte[0]]]if within else training
   for m,mode in enumerate(MODES):
    for algorithm in ['ridge','knn']:
     options=[j for j,g in enumerate(GRID)if g['algorithm']==algorithm];losses=[]
     for j in options:
      v=inner[ob,m,j,seltrain];good=np.isfinite(v).all(1);losses.append(float(rps(v[good],y[seltrain][good]).mean())if good.any()else np.inf)
     choice=options[int(np.argmin(losses))]
     if not np.isfinite(min(losses)):choice=next(j for j,g in enumerate(GRID)if g['algorithm']==algorithm and g['pca']==0 and ((algorithm=='ridge'and g['alpha']==10)or(algorithm=='knn'and g['k']==1)))
     pred=outer_grid[ob,m,choice,subte]
     for i,pp in zip(subte,pred):
      if not np.isfinite(pp).all():
       pp=cat_probs(d,training,[i],mode)[0];status='insufficient_stratum_training_global_fallback'
      else:status='no_training_in_stratum_global_fallback'if within and len(seltrain)==0 else'ok'
      records.append(dict(image_id=d.image_id.iloc[i],building=b,scene=d.scene_category.iloc[i],main_space=d.main_function_primary.iloc[i],y=int(y[i]),feature=name,baseline=mode,algorithm=algorithm,design=parent,p0=pp[0],p1=pp[1],p2=pp[2],prediction=int(np.argmax(pp)),rps=float(rps(pp,y[i])),brier=float(brier(pp,y[i])),status=status,grid=choice))
     settings.append(dict(building=b,stratum=d[field].iloc[subte[0]]if within else'all',feature=name,baseline=mode,grid=choice,inner_rps=min(losses),n_local_training=len(seltrain),train_class_counts=json.dumps(np.bincount(y[seltrain],minlength=3).tolist()),**GRID[choice]))
 pd.DataFrame(records).to_csv(paths[0],index=False);np.savez_compressed(paths[1],inner=inner,outer=outer_grid,buildings=np.array(buildings),image_ids=d.image_id.to_numpy(str))
 pd.DataFrame(settings).to_csv(dest/(name+'.settings.csv'),index=False);pd.DataFrame(fails).to_csv(dest/(name+'.failures.csv'),index=False)
 return name,round(time.time()-t0,2)

def baselines():
 d=pd.read_csv(O/'images/labels106.csv');r=[];f=[]
 for b in sorted(d.building.unique()):
  tr=np.flatnonzero(d.building!=b);te=np.flatnonzero(d.building==b)
  for mode in ['global','coarse','main','fine','human_focus','coarse_main']:
   p=cat_probs(d,tr,te,mode)
   for i,v in zip(te,p):r.append(dict(image_id=d.image_id.iloc[i],building=b,scene=d.scene_category.iloc[i],main_space=d.main_function_primary.iloc[i],y=int(d.y.iloc[i]),feature='baseline__'+mode,baseline='none',algorithm='frequency',design='pooled',p0=v[0],p1=v[1],p2=v[2],prediction=int(v.argmax()),rps=float(rps(v,d.y.iloc[i])),brier=float(brier(v,int(d.y.iloc[i]))),status='ok'))
  f.append(dict(building=b,n_train=len(tr),n_test=len(te),train_labels=json.dumps(np.bincount(d.y.to_numpy(int)[tr],minlength=3).tolist()),test_labels=json.dumps(np.bincount(d.y.to_numpy(int)[te],minlength=3).tolist())))
 csv('cv/baselines.csv',r);csv('audit/folds106.csv',f)

if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--workers',type=int,default=3);p.add_argument('--within',action='store_true');p.add_argument('--stratum',choices=['coarse','main'],default='coarse');p.add_argument('--features',nargs='*');args=p.parse_args()
 d=pd.read_csv(O/'images/labels106.csv');extra=make_metadata_features(d);names=pd.read_csv(O/'models/feature_inventory.csv').feature.tolist()+extra
 if args.features:names=[n for n in names if any(n.startswith(v)for v in args.features)]
 baselines();savej('method/prediction_grid.json',dict(grid=GRID,primary_selection='inner leave-building image-macro cumulative Brier / ranked probability score',modes=MODES,probability_map='clip to [1e-6,1] and renormalize; not a calibrated likelihood guarantee',followup=True,outer_split='fixed leave-building membership from work package',seed=SEED))
 with concurrent.futures.ProcessPoolExecutor(max_workers=args.workers)as ex:
  jobs=[ex.submit(run_feature,n,('main'if args.stratum=='main'else True)if args.within else False)for n in names]
  for f in concurrent.futures.as_completed(jobs):print('CV',args.within,f.result(),flush=True)
