"""Exploratory E interaction test: relative worker effects within real image/context.

Image/context intercepts are eliminated without using held-out values for fitting.
Outer building folds are the fixed package folds. Alpha is selected on inner
building image-macro MAE. Stable categorical dictionaries are not fitted values;
all feature scaling and variance filtering is performed within training folds.
"""
from __future__ import annotations
import collections,itertools,json,time
import numpy as np
import pandas as pd
from scipy.linalg import eigh
from tools.thesis_main.analysis.image_portrait.pro_core import *
from tools.thesis_main.analysis.image_portrait.pro_workers import ProfileCache,ALL_AXES,evaluate_in_image,inputs
from tools.thesis_main.analysis.image_portrait.pro_statistics import building_bootstrap
ALPHAS=[100.,10.,1.,.1]


def ridge_contrasts(X,y,train,test):
    """Train-only standard deviation; through-origin after within-context centering."""
    tr=np.asarray(train,int);te=np.asarray(test,int)
    if not len(tr):return np.full((4,len(te)),np.nan),None
    sd=X[tr].std(0);keep=sd>1e-12;a=X[tr][:,keep]/sd[keep];b=X[te][:,keep]/sd[keep]
    if not keep.any():return np.zeros((4,len(te))),dict(keep=keep,scale=sd)
    ev,v=eigh(a.T@a,check_finite=False);ev=np.maximum(ev,0);rhs=v.T@(a.T@y[tr]);pred=np.stack([b@((v*(1/(ev+alpha)))@rhs)for alpha in ALPHAS])
    return pred,dict(keep=keep,scale=sd)


def interactions():
    r=pd.read_csv(OUT/'human/response_metrics.csv.gz');r=r[r.main_worker_included & r.raw_condition.isin(['manual','semi'])].copy()
    f=pd.read_csv(OUT/'A/interpretable_inputs.csv');r=r.merge(f.drop(columns='building'),on='image_id');workers=sorted(r.worker_id.unique());rows=[];params=[];coefs=[]
    # Focused existing varying traits. Near constants, perfect duplicate occlusion,
    # and low-specificity connected-space labels are excluded, with source retained.
    for arm,col in itertools.product(['manual','semi'],['quality','active_seconds','effective_point_count']):
        q=r[(r.raw_condition==arm)&r[col].notna()].copy()
        if col!='active_seconds':q=q[q.geometry_valid]
        q['value']=np.log1p(q[col]) if col=='active_seconds' else q[col]
        counts=q.groupby('context_key').worker_id.transform('nunique');q=q[counts>=2].reset_index(drop=True)
        q['yc']=q.value-q.groupby('context_key').value.transform('mean')
        W=np.column_stack([(q.worker_id==w).astype(float) for w in workers]);Z=[];z_names=[]
        for name,level in [('floor_boundary','partial'),('ceiling_boundary','partial'),('doorway','确认'),('doorway','疑似'),('reflection_glass','present'),('reflection_glass','unknown')]:Z.append((q[name]==level).astype(float));z_names.append(name+'='+level)
        Z=np.column_stack(Z)
        designs={'worker_additive':(W,workers),'worker_trait_interactions':(np.concatenate([W,*[W*Z[:,j,None]for j in range(Z.shape[1])]],axis=1),workers+[w+'*'+z for z in z_names for w in workers])}
        ctx=q.context_key.to_numpy();build=q.building.to_numpy();ctxgroups=list(q.groupby('context_key').indices.values());ctxweights=np.array([1/len(ix)for ix in ctxgroups]);y=q.yc.to_numpy();bset=sorted(set(build))
        for model,(raw,names) in designs.items():
            X=raw.copy()
            for ix in ctxgroups:X[ix]-=X[ix].mean(0)
            cache={}
            def get(exclude):
                key=tuple(sorted(exclude))
                if key not in cache:
                    tr=np.flatnonzero(~np.isin(build,key));te=np.flatnonzero(np.isin(build,key));cache[key]=(te,*ridge_contrasts(X,y,tr,te))
                return cache[key]
            for outer in bset:
                loss=np.zeros(4);den=0
                for inner in bset:
                    if inner==outer:continue
                    ix,pr,_=get([outer,inner]);mask=build[ix]==inner
                    if not mask.any():continue
                    ids=ix[mask];errs=np.abs(pr[:,mask]-y[ids][None])
                    temp=pd.DataFrame(errs.T,columns=range(4));temp['image_id']=q.image_id.iloc[ids].to_numpy();im=temp.groupby('image_id')[list(range(4))].mean()
                    loss+=im.sum().to_numpy();den+=len(im)
                loss=loss/den if den else loss;chosen=int(np.argmin(loss));ix,pred,meta=get([outer]);pred=pred[chosen]
                train_workers=set(q.loc[build!=outer,'worker_id']);out=q.iloc[ix].copy();out['prediction']=pred
                params.append(dict(condition=arm,endpoint=col,model=model,heldout_building=outer,alpha=ALPHAS[chosen],inner_images=den,inner_MAE=loss[chosen],test_rows=len(ix)))
                for context,g in out.groupby('context_key'):
                    # Unknown new people are reported and omitted from the paired
                    # contrast evaluation rather than assigned a learned identity.
                    good=g[g.worker_id.isin(train_workers)];n=len(good)
                    if n<2:continue
                    actual=good.value.to_numpy()-good.value.mean();pp=good.prediction.to_numpy()-good.prediction.mean()
                    rows.append(dict(condition=arm,endpoint=col,model=model,image_id=g.image_id.iloc[0],context=context,building=outer,n_workers=n,unknown_workers=len(g)-n,baseline_MAE=np.mean(np.abs(actual)),method_MAE=np.mean(np.abs(actual-pp)),baseline_MSE=np.mean(actual**2),method_MSE=np.mean((actual-pp)**2),alpha=ALPHAS[chosen]))
            print('interactions',arm,col,model,'done',flush=True)
    write_csv('E/worker_trait_interactions_oof.csv',rows);write_csv('E/interaction_inner_choices.csv',params)
    a=pd.DataFrame(rows);s=[]
    for key,g in a.groupby(['condition','endpoint','model']):
        im=g.groupby(['image_id','building'],as_index=False)[['baseline_MAE','method_MAE','baseline_MSE','method_MSE']].mean();im['delta']=im.method_MAE-im.baseline_MAE;ci=building_bootstrap(im,'delta')
        s.append(dict(condition=key[0],endpoint=key[1],model=key[2],n_images=len(im),n_buildings=im.building.nunique(),baseline_MAE=im.baseline_MAE.mean(),method_MAE=im.method_MAE.mean(),relative_MSE_reduction=1-im.method_MSE.mean()/im.baseline_MSE.mean(),delta_MAE=im.delta.mean(),CI_low=ci[0],CI_high=ci[1]))
    for key,g in a[a.model=='worker_trait_interactions'].groupby(['condition','endpoint']):
        b=a[(a.condition==key[0])&(a.endpoint==key[1])&(a.model=='worker_additive')];p=g.merge(b,on=['image_id','building','context'],suffixes=('','_additive'));im=p.groupby(['image_id','building'],as_index=False)[['method_MAE','method_MAE_additive']].mean();im['delta']=im.method_MAE-im.method_MAE_additive;ci=building_bootstrap(im,'delta');s.append(dict(condition=key[0],endpoint=key[1],model='interaction_minus_additive',n_images=len(im),n_buildings=im.building.nunique(),baseline_MAE=im.method_MAE_additive.mean(),method_MAE=im.method_MAE.mean(),delta_MAE=im.delta.mean(),CI_low=ci[0],CI_high=ci[1]))
    write_csv('E/worker_trait_interaction_summary.csv',s)


def quality_median_baseline():
    old,current,r=inputs();oc=ProfileCache(old);cc=ProfileCache(current);rows=[];members=[]
    for building in sorted(current.building_id.unique()):
        op,_=oc.fit([building]);cp,_=cc.fit([building]);test=current[current.building_id==building]
        if 'quality' not in op:continue
        for panel in ['native','common_all_blocks']:
            p=op.dropna(subset=['quality'] if panel=='native' else ALL_AXES).copy();cut=p.quality.median();labels=(p.quality>cut).astype(int)
            for w,l in labels.items():members.append(dict(heldout_building=building,panel=panel,worker_id=w,label=chr(65+l),training_cut=cut,training_quality=p.loc[w,'quality'],class_size=int((labels==l).sum())))
            for axis,g in test.groupby('axis'):
                if axis not in cp:continue
                target=cp[axis].reindex(p.index);pred={}
                for k in [0,1]:
                    value=target[labels==k].mean()
                    for w in labels[labels==k].index:pred[w]=value
                gg=g[g.worker_id.isin(target.dropna().index)] if panel=='common_all_blocks' else g
                rows+=evaluate_in_image(gg,pred,dict(heldout_building=building,panel=panel,information='Q_median2',k=2,algorithm='training_quality_median',axis=axis))
    write_csv('E/Q_median2_predictions.csv.gz',rows);write_csv('E/Q_median2_memberships.csv',members)

if __name__=='__main__':
    import argparse
    p=argparse.ArgumentParser();p.add_argument('--stage',choices=['interactions','median','all'],default='all');a=p.parse_args()
    if a.stage in ['interactions','all']:interactions()
    if a.stage in ['median','all']:quality_median_baseline()
