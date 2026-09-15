"""Nested fixed-building evaluation, numerically equivalent ridge/PCA/kNN.

No fitted transform crosses an outer or inner test building. Identical panels of
nonmissing targets share matrix operations, not target values or fitted choices.
Every prespecified hyperparameter is evaluated. Outputs include native coverage,
inner scores, parameters, fixed candidates and train-only layer selection inputs.
"""
from __future__ import annotations
import argparse,itertools,json,time,collections,warnings
from pathlib import Path
import numpy as np
import pandas as pd
from scipy.linalg import eigh
from scipy.stats import spearmanr
from tools.thesis_main.analysis.image_portrait.pro_core import BUNDLE,OUT,SEED,TARGETS,SCOPE,load,write_json,write_csv

PTARGETS=TARGETS+['scope_p_'+s for s in SCOPE if s!='unknown']
CONFIGS=[dict(algorithm=algorithm,pca=pca,parameter=par) for algorithm in ['ridge','knn'] for pca in [None,16,32] for par in ([100.,10.,1.,.1] if algorithm=='ridge' else [1,3,5])]


def clip_predictions(pred,targets):
    p=np.array(pred,copy=True)
    for j,t in enumerate(targets):
        hi=np.inf if t=='owner_valid_active_seconds' else np.log2(5) if t=='scope_entropy' else 1.
        p[...,j]=np.clip(p[...,j],0.,hi)
    return p


def numeric_grid(X,Y,train,test,targets):
    """All 21 candidate fits. Scaler/PCA use train only, float64 mathematics.

    PCA through the training Gram eigensystem is exact (not a random projection).
    Ridge intercept is unpenalized; nearest neighbors have uniform weights.
    """
    train=np.asarray(train,int);test=np.asarray(test,int);n=len(train);d=Y.shape[1]
    if n==0:return np.full((len(CONFIGS),len(test),d),np.nan),dict(status='no_training_targets',n_train=0,p_retained=0)
    xt=np.asarray(X[train],dtype=np.float64);xv=np.asarray(X[test],dtype=np.float64)
    if not np.isfinite(xt).all() or not np.isfinite(xv).all():raise ValueError('Missing predictors must be excluded explicitly before fitting')
    mu=xt.mean(0);sd=xt.std(0);keep=sd>1e-12
    yt=Y[train];ym=yt.mean(0);yc=yt-ym
    if keep.sum()==0 or n<2:
        pred=np.broadcast_to(np.median(yt,axis=0),(len(CONFIGS),len(test),d)).copy()
        return clip_predictions(pred,targets),dict(status='constant_features_or_single_training_image',n_train=n,p_retained=int(keep.sum()))
    xt=(xt[:,keep]-mu[keep])/sd[keep];xv=(xv[:,keep]-mu[keep])/sd[keep];p=xt.shape[1]
    # Eigenvalues in descending order; exact thin decomposition in smaller space.
    if p<n:
        ev,V=eigh(xt.T@xt,check_finite=False,driver='evr');order=np.argsort(ev)[::-1];ev=ev[order];V=V[:,order]
        ev=np.clip(ev,0,None);s=np.sqrt(ev);zt=xt@V;zv=xv@V
        U=np.divide(zt,s[None,:],out=np.zeros_like(zt),where=s[None,:]>1e-10)
    else:
        ev,U=eigh(xt@xt.T,check_finite=False,driver='evr');order=np.argsort(ev)[::-1];ev=np.clip(ev[order],0,None);U=U[:,order];s=np.sqrt(ev)
        zt=U*s;kt=xv@xt.T
        zv=np.divide(kt@U,s[None,:],out=np.zeros((len(test),len(ev))),where=s[None,:]>1e-10)
    yproj=U.T@yc
    output=[]
    for cfg in CONFIGS:
        kdim=min(n-1,p) if cfg['pca'] is None else min(cfg['pca'],n-1,p)
        if cfg['algorithm']=='ridge':
            beta=(s[:kdim,None]*yproj[:kdim])/(ev[:kdim,None]+cfg['parameter'])
            pred=zv[:,:kdim]@beta+ym
        else:
            k=min(int(cfg['parameter']),n)
            if cfg['pca'] is None:
                # Full Euclidean distances also retain the test component outside
                # the training span. It is a row-wise constant but kept explicitly.
                dist=np.maximum((xv*xv).sum(1)[:,None]+(xt*xt).sum(1)[None,:]-2*xv@xt.T,0)
            else:
                a=zv[:,:kdim];b=zt[:,:kdim];dist=np.maximum((a*a).sum(1)[:,None]+(b*b).sum(1)[None,:]-2*a@b.T,0)
            ix=np.argsort(dist,axis=1,kind='stable')[:,:k];pred=yt[ix].mean(1)
        output.append(pred)
    return clip_predictions(np.stack(output),targets),dict(status='ok',n_train=n,p_retained=p,target_constant_columns=[targets[j] for j in range(d) if np.ptp(yt[:,j])<1e-12])


def baseline_predictions(t,features):
    folds=load(BUNDLE/'evaluation/folds.jsonl.gz');scene=features.set_index('image_id').scene.to_dict();rows=[]
    for arm,g in t.groupby('condition'):
        by=g.set_index('image_id')
        for f in folds:
            for target in PTARGETS:
                train=by.loc[by.index.intersection(f['train'])].dropna(subset=[target]);test=by.loc[by.index.intersection(f['test'])].dropna(subset=[target])
                for i,r in test.iterrows():
                    for method in ['constant_median','scene_median']:
                        same=train[train.index.map(scene.get)==scene.get(i)] if method=='scene_median' else train
                        pred=float(same[target].median()) if len(same) else float(train[target].median()) if len(train) else np.nan
                        rows.append(dict(feature='baseline',algorithm=method,condition=arm,target=target,design=f['design'],fold_id=f['fold_id'],room_id=f.get('room_id',''),image_id=i,building=r.building,n_train=len(train),scene_unseen=len(same)==0,truth=r[target],prediction=pred,absolute_error=abs(pred-r[target]),status='ok' if len(train) else 'no_training_targets'))
    write_csv('prediction/baselines.csv.gz',rows)
    return pd.DataFrame(rows)


def feature_registry(root):
    return json.loads((root/'registry.json').read_text())


def evaluate_feature(name,record,root,t,overwrite=False):
    destination=OUT/'prediction'/f'{name}.csv.gz';scores_dest=OUT/'prediction'/f'{name}.inner.csv.gz'
    if destination.exists() and scores_dest.exists() and not overwrite:return
    start=time.monotonic();z=np.load(root/record['file'],allow_pickle=False);images=z['image_ids'].tolist();Xall=z['X'];indices={i:j for j,i in enumerate(images)}
    good=np.isfinite(Xall).all(1);available={i for i,j in indices.items() if good[j]}
    folds=load(BUNDLE/'evaluation/folds.jsonl.gz');rows=[];score_rows=[];coverage=[]
    for arm,g in t.groupby('condition'):
        original=g.copy();g=g[g.image_id.isin(available)].sort_values('image_id').reset_index(drop=True)
        patterns=collections.defaultdict(list)
        for target in PTARGETS:patterns[tuple(g[target].notna())].append(target)
        for mask,targets in patterns.items():
            q=g[np.asarray(mask)].reset_index(drop=True)
            if not len(q):continue
            image_ids=q.image_id.tolist();x=np.asarray(Xall[[indices[i] for i in image_ids]],float);y=q[targets].to_numpy(float);buildings=q.building.to_numpy();bset=sorted(set(buildings))
            cache={}
            provider=None
            if record.get('dynamic_assignment'):
                from tools.thesis_main.analysis.image_portrait.pro_person_increment import AssignmentFeatures
                provider=AssignmentFeatures(image_ids,arm,x,record['dynamic_assignment'])
            def fits(excluded):
                key=tuple(sorted(excluded))
                if key not in cache:
                    tr=np.flatnonzero(~np.isin(buildings,key));te=np.flatnonzero(np.isin(buildings,key))
                    xx=provider(excluded) if provider is not None else x
                    good=np.isfinite(xx).all(1);tr=tr[good[tr]];okte=te[good[te]]
                    small,meta=numeric_grid(xx,y,tr,okte,targets)
                    pred=np.full((len(CONFIGS),len(te),len(targets)),np.nan);pred[:,good[te]]=small
                    meta['dynamic_missing_test']=int((~good[te]).sum())
                    cache[key]=(te,pred,meta)
                return cache[key]
            for outer in bset:
                te,pout,meta=fits([outer]);train_ids=np.flatnonzero(buildings!=outer);score=np.zeros((len(CONFIGS),len(targets)));den=0
                for inner in bset:
                    if inner==outer:continue
                    ix,p,im=fits([outer,inner]);valid=buildings[ix]==inner
                    if len(im.get('target_constant_columns',[]))==len(targets):pass
                    if im['n_train']==0:continue
                    valid &= np.isfinite(p).all(axis=(0,2))
                    score+=np.abs(p[:,valid]-y[ix[valid]][None]).sum(1);den+=valid.sum()
                score=score/den if den else np.full_like(score,np.nan)
                for j,target in enumerate(targets):
                    for c,cfg in enumerate(CONFIGS):score_rows.append(dict(feature=name,condition=arm,target=target,outer_building=outer,algorithm=cfg['algorithm'],pca='None' if cfg['pca'] is None else cfg['pca'],parameter=cfg['parameter'],inner_images=den,inner_MAE=score[c,j]))
                    for alg in ['ridge','knn']:
                        candidate=[c for c,cfg in enumerate(CONFIGS) if cfg['algorithm']==alg]
                        chosen=min(candidate,key=lambda c:(score[c,j],c)) if den else next(c for c,cfg in enumerate(CONFIGS) if cfg['algorithm']==alg and cfg['pca'] is None and cfg['parameter']==(10 if alg=='ridge' else 1))
                        cfg=CONFIGS[chosen]
                        for pos,i in enumerate(te):
                            pred=pout[chosen,pos,j]
                            rows.append(dict(feature=name,algorithm=alg,condition=arm,target=target,design='leave_building',fold_id='building:'+outer,room_id='',image_id=image_ids[i],building=outer,n_train=meta['n_train'],p_retained=meta['p_retained'],pca='None' if cfg['pca'] is None else cfg['pca'],parameter=cfg['parameter'],inner_images=den,inner_MAE=score[chosen,j],truth=y[i,j],prediction=pred,absolute_error=abs(pred-y[i,j]),status=meta['status'] if np.isfinite(pred) else 'missing_predictor_or_training_targets'))
                # Results from unordered pair exclusions are reused by the other outer
                # building. They never use either held-out building in fitting.
            for f in folds:
                if f['design']!='same_room_leave_view':continue
                tr=np.array([j for j,i in enumerate(image_ids) if i in set(f['train'])],int);te=np.array([j for j,i in enumerate(image_ids) if i in set(f['test'])],int)
                if not len(te):continue
                xx=provider({image_ids[te[0]].split('_')[0]}) if provider is not None else x
                good=np.isfinite(xx).all(1);tr=tr[good[tr]];okte=te[good[te]]
                small,meta=numeric_grid(xx,y,tr,okte,targets);p=np.full((len(CONFIGS),len(te),len(targets)),np.nan);p[:,good[te]]=small
                for alg in ['ridge','knn']:
                    cfgid=next(j for j,c in enumerate(CONFIGS) if c['algorithm']==alg and c['pca'] is None and c['parameter']==(10 if alg=='ridge' else 1))
                    for j,target in enumerate(targets):
                        for pos,i in enumerate(te):
                            pred=p[cfgid,pos,j];rows.append(dict(feature=name,algorithm=alg,condition=arm,target=target,design=f['design'],fold_id=f['fold_id'],room_id=f.get('room_id',''),image_id=image_ids[i],building=buildings[i],n_train=len(tr),p_retained=meta['p_retained'],pca='None',parameter=10 if alg=='ridge' else 1,inner_images=0,inner_MAE=np.nan,truth=y[i,j],prediction=pred,absolute_error=abs(pred-y[i,j]),status=meta['status'] if np.isfinite(pred) else 'missing_predictor_or_training_targets'))
            coverage.extend([dict(feature=name,condition=arm,target=target,human_target_images=int(original[target].notna().sum()),predictor_available_target_images=len(q),missing_predictor_images=int(original[target].notna().sum())-len(q),input_dimensions=Xall.shape[1]) for target in targets])
        # Explicit unavailable predictor rows, not silent exclusions.
        for _,r in original[~original.image_id.isin(available)].iterrows():
            for target in PTARGETS:
                if pd.notna(r[target]):
                    for alg in ['ridge','knn']:rows.append(dict(feature=name,algorithm=alg,condition=arm,target=target,design='leave_building',fold_id='building:'+r.building,room_id='',image_id=r.image_id,building=r.building,n_train=0,truth=r[target],prediction=np.nan,absolute_error=np.nan,status='missing_or_nonfinite_predictor'))
    result=pd.DataFrame(rows)
    # Conservative room folds have exactly the same outside-building training set.
    room_rows=[]
    for f in folds:
        if f['design']!='leave_supported_room_conservative':continue
        subset=result[(result.design=='leave_building')&result.image_id.isin(f['test'])].copy()
        subset['design']=f['design'];subset['fold_id']=f['fold_id'];subset['room_id']=f['room_id'];room_rows.append(subset)
    if room_rows:result=pd.concat([result,*room_rows],ignore_index=True)
    write_csv(f'prediction/{name}.csv.gz',result);write_csv(f'prediction/{name}.inner.csv.gz',score_rows);write_csv(f'prediction/{name}.coverage.csv',coverage)
    print(name,'seconds',round(time.monotonic()-start,2),'rows',len(result),'p',Xall.shape[1],flush=True)


def summarize():
    files=[p for p in (OUT/'prediction').glob('*.csv.gz') if not p.name.endswith('.inner.csv.gz') and p.name not in {'all_predictions.csv.gz','selected_layers.csv.gz'}]
    frames=[]
    for p in files:
        a=pd.read_csv(p)
        if 'prediction' in a:frames.append(a)
    if not frames:return
    a=pd.concat(frames,ignore_index=True);scene=pd.read_csv(OUT/'A/interpretable_inputs.csv')[['image_id','source_split']]
    a=a.merge(scene,on='image_id',how='left');write_csv('prediction/all_predictions.csv.gz',a)
    summary=[]
    for key,g in a.groupby(['feature','algorithm','condition','target','design'],dropna=False):
        for split in ['all',*sorted(g.source_split.dropna().unique())]:
            q=g if split=='all' else g[g.source_split==split];v=q.dropna(subset=['prediction','truth'])
            if not len(v):rho=np.nan
            elif v.prediction.nunique()<2 or v.truth.nunique()<2:rho=np.nan
            else:rho=spearmanr(v.prediction,v.truth).statistic
            summary.append(dict(feature=key[0],algorithm=key[1],condition=key[2],target=key[3],design=key[4],source_split=split,n_target_images=q.image_id.nunique(),n_prediction_images=v.image_id.nunique(),n_buildings=v.building.nunique(),n_rooms=v.room_id.nunique() if 'room_id' in v else 0,image_MAE=v.absolute_error.mean(),building_macro_MAE=v.groupby('building').absolute_error.mean().mean(),room_macro_MAE=v.groupby('room_id').absolute_error.mean().mean() if len(v) and key[4]!='leave_building' else np.nan,spearman=rho))
    write_csv('prediction/score_summary.csv',summary)


def run(root,names=None,overwrite=False):
    t=pd.read_csv(OUT/'human/image_outcomes.csv');t=t[(t.view=='reviewed') & t.condition.isin(['manual','semi'])]
    registry=feature_registry(root);features=pd.read_csv(OUT/'A/interpretable_inputs.csv')
    if not (OUT/'prediction/baselines.csv.gz').exists():baseline_predictions(t,features)
    for name,record in registry.items():
        if names and name not in names:continue
        evaluate_feature(name,record,root,t,overwrite=overwrite)
    summarize()

if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--feature-root',type=Path,default=OUT/'features');ap.add_argument('--names',nargs='*');ap.add_argument('--overwrite',action='store_true');ap.add_argument('--summarize',action='store_true');args=ap.parse_args()
    if args.summarize:summarize()
    else:run(args.feature_root,args.names,args.overwrite)
