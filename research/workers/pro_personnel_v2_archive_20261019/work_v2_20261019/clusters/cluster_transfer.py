"""Nested-feature leave-building-out prediction of local annotation behavior."""
from __future__ import annotations
import argparse,collections,gzip,hashlib,json,math,time,warnings
from pathlib import Path
import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import roc_auc_score
from threadpoolctl import threadpool_limits

HERE=Path(__file__).resolve().parent;BASE=HERE.parents[1];PROFILES=HERE.parent/'profiles'
SEED=2026101921
DIFF={'简单':'easy','中等':'medium','困难':'hard','easy':'easy','medium':'medium','hard':'hard'}

def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()

def compact_evidence():
    path=BASE/'repo_main_20261019/research/statistics/v2_evidence_audit_20261019/records.json.gz'
    with gzip.open(path,'rt') as f:raw=json.load(f)['records']
    rows=[]
    for r in raw:
        se=r.get('semi_evidence') or {};sc=r.get('scope_evidence') or {}
        rows.append(dict(worker_id=r['worker_id'],building_id=r['building_id'],
            confirmed_n=int(se.get('confirmed_error_opportunity') is True),
            confirmed_bad=int(se.get('confirmed_error_opportunity') is True and se.get('known_error_unchanged') is True),
            reported_n=int(se.get('reported_error_opportunity') is True),
            reported_bad=int(se.get('reported_error_opportunity') is True and se.get('reported_known_error_unchanged') is True),
            scope_n=int(sc.get('response_recorded') is True),scope_out=int(sc.get('response')=='out_of_scope')))
    return pd.DataFrame(rows)

def building_weights(df):
    per_image=df.groupby('pool_id').size();image_building=df[['pool_id','building_id']].drop_duplicates()
    per_building=image_building.groupby('building_id').size();nimages=len(image_building);nbuild=len(per_building)
    return np.asarray([nimages/nbuild/(per_image[p]*per_building[b]) for p,b in zip(df.pool_id,df.building_id)],float)

def augment_profiles(frame,exclude,records,behaviors,cache):
    key=tuple(sorted(exclude))
    if key not in cache:
        z=records[~records.building_id.isin(exclude)]
        absolute=z.groupby('worker_id').B8L2.mean().rename('absolute_mean')
        b=behaviors[~behaviors.building_id.isin(exclude)].groupby('worker_id').sum(numeric_only=True)
        for prefix in ['confirmed','reported']:
            b[prefix+'_rate']=np.where(b[prefix+'_n']>0,(b[prefix+'_bad']+.5)/(b[prefix+'_n']+1),np.nan)
            b[prefix+'_log_n']=np.log1p(b[prefix+'_n'])
        b['scope_propensity']=np.where(b.scope_n>0,(b.scope_out+.5)/(b.scope_n+1),np.nan)
        cache[key]=pd.concat([absolute,b],axis=1)
    return frame.merge(cache[key],left_on='worker_id',right_index=True,how='left',validate='one_to_one')

def profile_for_examples(df,outer,fold,nested,records,behaviors,cache):
    # Each training building receives the double-excluded profile; the target
    # building receives the ordinary outer-held-out profile.
    result={}
    for b in df.building_id.unique():
        if b==outer:
            source=fold[fold.heldout_building==outer].copy();excluded={outer}
        else:
            source=nested[(nested.outer_heldout_building==outer)&(nested.inner_heldout_building==b)].copy();excluded={outer,b}
        assert len(source)==60 and not source.worker_id.duplicated().any()
        result[b]=augment_profiles(source,excluded,records,behaviors,cache).set_index('worker_id').to_dict('index')
    return result

TRAITS=['q','absolute','t','t_origin','delta','confirmed_rate','reported_rate','scope_propensity','confirmed_log_n','reported_log_n']

def trait_vector(profile,difficulty):
    q=profile['Q_effect_B8L2'] if bool(profile['Q_supported']) else np.nan
    t=profile['T_source_effect'] if bool(profile['T_source_supported']) else np.nan
    to=profile['T_source_origin_effect'] if bool(profile['T_source_supported']) else np.nan
    supported=bool(profile.get('difficulty_supported_'+difficulty,False))
    theta=profile.get('theta_'+difficulty+'_B8L2',np.nan) if supported else np.nan
    return [q,profile.get('absolute_mean',np.nan),t,to,theta-q,
            profile.get('confirmed_rate',np.nan),profile.get('reported_rate',np.nan),profile.get('scope_propensity',np.nan),
            profile.get('confirmed_log_n',np.nan),profile.get('reported_log_n',np.nan)]

def make_features(df,lookup,kind):
    diff=[DIFF[x] for x in df.difficulty]
    first=[trait_vector(lookup[b][w],d) for b,w,d in zip(df.building_id,df.worker_id_a if kind=='pair' else df.worker_id,diff)]
    first=np.asarray(first,float); features={'difficulty_medium':np.asarray(diff)=='medium','difficulty_hard':np.asarray(diff)=='hard'}
    if kind=='pair':
        second=np.asarray([trait_vector(lookup[b][w],d) for b,w,d in zip(df.building_id,df.worker_id_b,diff)],float)
        for i,name in enumerate(TRAITS):
            features[name+'_mean']=(first[:,i]+second[:,i])/2
            features[name+'_absdiff']=abs(first[:,i]-second[:,i])
    else:
        for i,name in enumerate(TRAITS):features[name]=first[:,i]
    return pd.DataFrame(features,index=df.index).astype(float)

def columns_for(model,kind):
    vars={'Q_absolute':['absolute'],'Q_relative':['q'],'QT':['q','t'],
          'QTD':['q','t','delta'],'QTD_origin_time':['q','t_origin','delta'],
          'QTD_behavior':['q','t','delta','confirmed_rate','reported_rate','scope_propensity','confirmed_log_n','reported_log_n']}[model]
    cols=['difficulty_medium','difficulty_hard']
    for v in vars:cols.extend([v+'_mean',v+'_absdiff'] if kind=='pair' else [v])
    return cols

def fit_predict(xtrain,xtest,y,w):
    a,b=xtrain.to_numpy(float),xtest.to_numpy(float)
    missing_a=~np.isfinite(a);missing_b=~np.isfinite(b)
    with warnings.catch_warnings():
        warnings.simplefilter('ignore',RuntimeWarning);med=np.nanmedian(a,axis=0)
    med[~np.isfinite(med)]=0. # Numerical encoding only; indicator remains explicit.
    a=np.where(missing_a,med,a);b=np.where(missing_b,med,b)
    a=np.column_stack([a,missing_a.astype(float)]);b=np.column_stack([b,missing_b.astype(float)])
    scale=StandardScaler();a=scale.fit_transform(a,sample_weight=w);b=scale.transform(b)
    model=LogisticRegression(C=1.,solver='lbfgs',max_iter=500,random_state=SEED)
    model.fit(a,y,sample_weight=w)
    return model.predict_proba(b)[:,1],model,scale,med

def prior_predict(train,test,target):
    means=train.groupby(['pool_id','building_id','difficulty'])[target].mean().reset_index()
    by=means.groupby(['building_id','difficulty'])[target].mean().reset_index()
    prior=by.groupby('difficulty')[target].mean().to_dict();global_prior=means.groupby('building_id')[target].mean().mean()
    return np.asarray([prior.get(d,global_prior) for d in test.difficulty],float)

def run_kind(kind,df,fold,nested,records,behaviors,out):
    buildings=sorted(df.building_id.unique());cache={};predictions=[];coefficients=[];foldmeta=[]
    model_names=['Q_absolute','Q_relative','QT','QTD','QTD_origin_time','QTD_behavior']
    for outer in buildings:
        tr=df[df.building_id!=outer].copy();te=df[df.building_id==outer].copy()
        lookup=profile_for_examples(df,outer,fold,nested,records,behaviors,cache)
        feat=make_features(df,lookup,kind);xtr=feat.loc[tr.index];xte=feat.loc[te.index];w=building_weights(tr)
        for cut in [9,12]:
            target=f'target_{cut}';train_good=tr[target].notna();test_good=te[target].notna()
            train=tr[train_good];test=te[test_good];yy=train[target].astype(int).to_numpy();ww=w[train_good]
            base=prior_predict(train,test,target)
            identity_cols=['pool_id','image_id','image_code','building_id','difficulty','N']+(['object_id_a','object_id_b','worker_id_a','worker_id_b','available','cohort_pair'] if kind=='pair' else ['object_id','worker_id','origin'])
            saved=test[identity_cols].copy();saved['threshold_deg']=cut;saved['target']=test[target].to_numpy();saved['kind']=kind
            def save_model(name,p):
                z=saved.copy();z['model']=name;z['prediction']=p
                z['squared_error']=(z.target-z.prediction)**2
                pp=np.clip(p,1e-6,1-1e-6);z['log_loss']=-(z.target*np.log(pp)+(1-z.target)*np.log1p(-pp))
                predictions.append(z)
            save_model('difficulty_prevalence',base)
            if kind=='pair':
                hist=train.groupby(['worker_id_a','worker_id_b'])[target].agg(['sum','count'])
                predictions_history=[]
                for i,(a,b) in enumerate(zip(test.worker_id_a,test.worker_id_b)):
                    counts=hist.loc[(a,b)] if (a,b) in hist.index else None
                    predictions_history.append(base[i] if counts is None else (counts['sum']+5*base[i])/(counts['count']+5))
                save_model('worker_pair_history',np.asarray(predictions_history))
            if len(np.unique(yy))<2:
                raise ValueError('Single-class training outcome; requires explicit fallback')
            for modelname in model_names:
                cols=columns_for(modelname,kind)
                pred,model,scale,med=fit_predict(xtr.loc[train.index,cols],xte.loc[test.index,cols],yy,ww)
                save_model(modelname,pred)
                names=cols+[c+'__missing' for c in cols]
                for j,c in enumerate(names):coefficients.append(dict(kind=kind,heldout_building=outer,threshold_deg=cut,model=modelname,feature=c,
                    standardized_coefficient=model.coef_[0,j],train_encoding_median=med[j] if j<len(cols) else np.nan,
                    train_feature_center=scale.mean_[j],train_feature_scale=scale.scale_[j]))
            foldmeta.append(dict(kind=kind,heldout_building=outer,threshold_deg=cut,train_examples=len(train),test_examples=len(test),
                train_images=train.pool_id.nunique(),test_images=test.pool_id.nunique(),train_buildings=train.building_id.nunique(),
                unavailable_test_targets=int((~test_good).sum()),feature_self_building_excluded=True,target_building_excluded=True))
        print(json.dumps(dict(task='cluster_transfer',kind=kind,heldout=outer,test=len(te))),flush=True)
    pred=pd.concat(predictions,ignore_index=True)
    pred.to_csv(out/(kind+'_heldout_predictions.csv.gz'),index=False)
    pd.DataFrame(coefficients).to_csv(out/(kind+'_model_coefficients.csv'),index=False)
    pd.DataFrame(foldmeta).to_csv(out/(kind+'_fold_coverage.csv'),index=False)
    return pred

def summarize(pred,out,kind):
    rows=[]
    panels={'all':np.ones(len(pred),bool)}
    if kind=='pair':
        panels.update(same_point_count_retrospective=pred.available.eq(True),old_old=pred.cohort_pair.eq('v1|v1'),new_new=pred.cohort_pair.eq('new|new'),mixed=pred.cohort_pair.eq('mixed'))
    else:panels.update(old=pred.origin.eq('v1'),new=pred.origin.ne('v1'))
    for panel,mask in panels.items():
        p=pred[mask]
        for key,g in p.groupby(['threshold_deg','model','pool_id','image_id','image_code','building_id','difficulty']):
            z=dict(zip(['threshold_deg','model','pool_id','image_id','image_code','building_id','difficulty'],key));z.update(panel=panel,n=len(g),brier=g.squared_error.mean(),log_loss=g.log_loss.mean(),prevalence=g.target.mean(),mean_prediction=g.prediction.mean(),
                auc=roc_auc_score(g.target,g.prediction) if g.target.nunique()==2 else np.nan)
            rows.append(z)
    image=pd.DataFrame(rows);image.to_csv(out/(kind+'_image_scores.csv'),index=False)
    summaries=[];brows=[];rng=np.random.default_rng(SEED)
    for key,g in image.groupby(['panel','threshold_deg','model']):
        by=g.groupby('building_id')[['brier','log_loss','auc']].mean()
        for b,v in by.iterrows():brows.append(dict(zip(['panel','threshold_deg','model'],key),building_id=b,**v.to_dict()))
        row=dict(zip(['panel','threshold_deg','model'],key),images=len(g),buildings=len(by),n=int(g.n.sum()),image_equal_brier=g.brier.mean(),building_equal_brier=by.brier.mean(),building_equal_log_loss=by.log_loss.mean(),mean_image_auc=by.auc.mean())
        sims=rng.choice(by.brier.to_numpy(),(3000,len(by)),replace=True).mean(1);row.update(brier_low=np.quantile(sims,.025),brier_high=np.quantile(sims,.975));summaries.append(row)
    pd.DataFrame(summaries).to_csv(out/(kind+'_transfer_summary.csv'),index=False)
    bdf=pd.DataFrame(brows);bdf.to_csv(out/(kind+'_building_scores.csv'),index=False)
    comparisons=[]
    for (panel,cut),g in bdf.groupby(['panel','threshold_deg']):
        w=g.pivot(index='building_id',columns='model',values='brier')
        contrasts=[(m,'difficulty_prevalence') for m in w.columns if m!='difficulty_prevalence']+[('QT','Q_relative'),('QTD','QT'),('QTD_origin_time','QTD'),('QTD_behavior','QTD')]
        for model,base in contrasts:
            d=(w[model]-w[base]).dropna();sims=rng.choice(d.to_numpy(),(3000,len(d)),replace=True).mean(1)
            comparisons.append(dict(panel=panel,threshold_deg=cut,model=model,baseline=base,buildings=len(d),
                delta_brier_model_minus_baseline=d.mean(),low=np.quantile(sims,.025),high=np.quantile(sims,.975),improved_buildings=int((d<0).sum()),worse_buildings=int((d>0).sum())))
    pd.DataFrame(comparisons).to_csv(out/(kind+'_paired_comparisons.csv'),index=False)

def main():
    ap=argparse.ArgumentParser(__doc__);ap.add_argument('--kind',choices=['pair','largest','both'],default='both');ap.add_argument('--summarize-only',action='store_true');args=ap.parse_args()
    out=HERE/'transfer';out.mkdir(exist_ok=True)
    if args.summarize_only:
        for kind in (['pair','largest'] if args.kind=='both' else [args.kind]):
            summarize(pd.read_csv(out/(kind+'_heldout_predictions.csv.gz')),out,kind)
        receipt=json.loads((out/'TRANSFER_RECEIPT.json').read_text())
        receipt['summary_code_sha256']=sha(Path(__file__))
        receipt['output_files']={p.name:dict(sha256=sha(p),bytes=p.stat().st_size) for p in out.iterdir() if p.is_file() and p.name!='TRANSFER_RECEIPT.json'}
        (out/'TRANSFER_RECEIPT.json').write_text(json.dumps(receipt,indent=2)+'\n')
        return
    fold=pd.read_csv(PROFILES/'fold_profiles.csv');nested=pd.read_csv(PROFILES/'nested_fold_features.csv')
    records=pd.read_csv(PROFILES/'records_flat.csv');records=records[records.quality_usable & records.condition.eq('manual') & records.quality_use.eq('ordinary_primary')]
    origin=records.set_index('object_id').origin.to_dict();behaviors=compact_evidence()
    with threadpool_limits(limits=1):
        if args.kind in ['pair','both']:
            df=pd.read_csv(HERE/'pair_distances.csv.gz');df=df[df.layer.eq('ordinary_manual')].copy().reset_index(drop=True)
            df['target_9']=df.same_affinity_9.astype(int);df['target_12']=df.same_affinity_12.astype(int)
            df['cohort_pair']=[(origin[a]+'|'+origin[b]) if origin[a]==origin[b] else 'mixed' for a,b in zip(df.object_id_a,df.object_id_b)]
            p=run_kind('pair',df,fold,nested,records,behaviors,out);summarize(p,out,'pair')
        if args.kind in ['largest','both']:
            a=pd.read_csv(HERE/'assignments.csv');a=a[a.layer.eq('ordinary_manual')&a.method.eq('affinity')].copy()
            groups=pd.read_csv(HERE/'cluster_summary.csv');groups=groups[groups.layer.eq('ordinary_manual')&groups.method.eq('affinity')]
            targets={}
            for (pid,cut),g in groups.groupby(['pool_id','threshold_deg']):
                maxn=g['size'].max(); winners=g[g['size']==maxn];unique=len(winners)==1
                targets[pid,int(cut)]=set(winners.iloc[0].object_ids.split('|')) if unique else None
            df=a[a.threshold_deg.eq(9)].copy().reset_index(drop=True)
            for cut in [9,12]:df[f'target_{cut}']=[np.nan if targets[pid,cut] is None else int(oid in targets[pid,cut]) for pid,oid in zip(df.pool_id,df.object_id)]
            p=run_kind('largest',df,fold,nested,records,behaviors,out);summarize(p,out,'largest')
    receipt=dict(registration_sha256=sha(HERE/'TRANSFER_REGISTRATION.json'),fold_profiles_sha256=sha(PROFILES/'fold_profiles.csv'),nested_features_sha256=sha(PROFILES/'nested_fold_features.csv'),
                 all_source_geometry_preserved=True,worker_features_target_and_own_building_excluded=True,models_tuned_to_result=False,
                 output_files={p.name:dict(sha256=sha(p),bytes=p.stat().st_size) for p in out.iterdir() if p.is_file()})
    (out/'TRANSFER_RECEIPT.json').write_text(json.dumps(receipt,indent=2)+'\n');print(json.dumps(receipt,indent=2))

if __name__=='__main__':main()
