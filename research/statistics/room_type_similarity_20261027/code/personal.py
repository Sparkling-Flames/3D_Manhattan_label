#!/usr/bin/env python3
"""Cross-building individual room-purpose repeatability; frozen human-v2 inputs.

Every target peer baseline excludes the target worker. Prediction inputs contain
no target response or target quality. Reference geometry is an explicitly known
structural-task diagnostic, not a no-reference deployment claim.
"""
import os
for _k in ['OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','OMP_NUM_THREADS']:
    os.environ.setdefault(_k,'1')
import argparse, hashlib, json, time, warnings
from pathlib import Path
import numpy as np
import pandas as pd
from scipy import sparse
from scipy.stats import spearmanr
from sklearn.linear_model import Ridge
from sklearn.model_selection import GroupKFold

SEED=2026102703
ALPHAS=[.1,1.,10.,100.,1000.]
MODEL_FEATURES={
    'person_ridge':(),
    'person_geometry':('difficulty','geometry'),
    'person_purpose':('purpose',),
    'person_geometry_purpose':('difficulty','geometry','purpose'),
}
NUMERIC_CANDIDATES=['ref_turn5','ref_short_turn_edges','ref_short_edges','ref_min_horizontal','ref_min_horizontal_angle','ref_radius_median','ref_H','ref_area','ref_perimeter']
# Resolve only existing frozen reference fields. No raw-response feature is a predictor.


def save(d,path):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    tmp=path.with_name(path.name+'.writing.'+str(os.getpid()))
    d.to_csv(tmp,index=False,compression={'method':'gzip','mtime':0} if path.suffix=='.gz' else None)
    os.replace(tmp,path)


def centered_prediction(v,d):
    s=pd.Series(np.asarray(v),index=d.index)
    return (s-s.groupby(d.image_key).transform('mean')).to_numpy()


def image_weights(d):
    w=1/d.groupby('image_key').image_key.transform('size').to_numpy()
    return w/np.mean(w)


def image_mse(y,p,d):
    return pd.Series((np.asarray(y)-np.asarray(p))**2,index=d.index).groupby(d.image_key).mean().mean()


def rel_target(d,col):
    val=pd.to_numeric(d[col],errors='coerce')
    n=val.groupby(d.image_key).transform('count')
    s=val.groupby(d.image_key).transform('sum')
    return val-(s-val)/(n-1)


class Features:
    def __init__(self,parts,num_cols):
        self.parts=parts;self.num_cols=num_cols
    def fit(self,d):
        self.workers=sorted(d.worker_id.unique());self.wmap={v:i for i,v in enumerate(self.workers)}
        self.cats={};self.means={};self.scales={};self.medians={}
        for part,col in [('purpose','room_type_model'),('difficulty','difficulty')]:
            if part in self.parts:
                vals=d[col].fillna('__MISSING__').astype(str)
                cats=sorted(vals.unique())
                self.cats[col]=cats
                # Image-weighted centering gives sum-to-zero task contrasts and
                # avoids changing stable-person shrinkage just by copying dummies.
                wt=image_weights(d)
                self.means[col]={v:np.average((vals==v).to_numpy(),weights=wt) for v in cats}
        if 'geometry' in self.parts:
            for col in self.num_cols:
                v=pd.to_numeric(d[col],errors='coerce')
                med=float(v.median()) if v.notna().any() else 0.
                self.medians[col]=med
                a=v.fillna(med).to_numpy();wt=image_weights(d)
                mu=float(np.average(a,weights=wt));sd=float(np.sqrt(np.average((a-mu)**2,weights=wt)))
                self.means[col]=mu;self.scales[col]=sd if sd>1e-12 else 1.
        return self
    def transform(self,d):
        ix=np.array([self.wmap.get(w,-1) for w in d.worker_id]);ok=ix>=0
        W=sparse.csr_matrix((np.ones(ok.sum()),(np.flatnonzero(ok),ix[ok])),shape=(len(d),len(self.workers)))
        blocks=[W];names=['person']
        for col,cats in self.cats.items():
            vals=d[col].fillna('__MISSING__').astype(str)
            for cat in cats:
                z=(vals==cat).to_numpy(dtype=float)-self.means[col][cat]
                blocks.append(W.multiply(z[:,None]));names.append(col+'='+cat)
        if 'geometry' in self.parts:
            for col in self.num_cols:
                v=pd.to_numeric(d[col],errors='coerce')
                z=(v.fillna(self.medians[col]).to_numpy()-self.means[col])/self.scales[col]
                blocks.append(W.multiply(z[:,None]));names.append(col)
                # Missingness is known target metadata, never replaced by a response.
                if v.isna().any():
                    blocks.append(W.multiply(v.isna().to_numpy(dtype=float)[:,None]));names.append(col+'__missing')
        # Missingness feature dimensions must be frozen between train and target.
        return sparse.hstack(blocks,format='csr')
    def dump(self):
        return {'parts':list(self.parts),'numeric_cols':self.num_cols,'workers':self.workers,'categories':self.cats,'means':self.means,'scales':self.scales,'medians':self.medians}


class FrozenFeatures(Features):
    def fit(self,d):
        super().fit(d)
        self.missing_cols=[c for c in self.num_cols if 'geometry' in self.parts and d[c].isna().any()]
        return self
    def transform(self,d):
        ix=np.array([self.wmap.get(w,-1) for w in d.worker_id]);ok=ix>=0
        W=sparse.csr_matrix((np.ones(ok.sum()),(np.flatnonzero(ok),ix[ok])),shape=(len(d),len(self.workers)))
        blocks=[W]
        for col,cats in self.cats.items():
            vals=d[col].fillna('__MISSING__').astype(str)
            for cat in cats:
                z=(vals==cat).to_numpy(dtype=float)-self.means[col][cat]
                blocks.append(W.multiply(z[:,None]))
        if 'geometry' in self.parts:
            for col in self.num_cols:
                v=pd.to_numeric(d[col],errors='coerce')
                z=(v.fillna(self.medians[col]).to_numpy()-self.means[col])/self.scales[col]
                blocks.append(W.multiply(z[:,None]))
                if col in self.missing_cols:blocks.append(W.multiply(v.isna().to_numpy(dtype=float)[:,None]))
        return sparse.hstack(blocks,format='csr')
    def dump(self):
        x=super().dump();x['missing_cols']=self.missing_cols;return x


def inner_select(train,ycol,parts,num_cols):
    groups=train.building.to_numpy();nfold=min(5,len(np.unique(groups)))
    records=[]
    for k,(it,iv) in enumerate(GroupKFold(n_splits=nfold).split(train,groups=groups)):
        tr=train.iloc[it];va=train.iloc[iv]
        f=FrozenFeatures(parts,num_cols).fit(tr);X=f.transform(tr);V=f.transform(va)
        y=tr[ycol].to_numpy();w=image_weights(tr)
        for a in ALPHAS:
            model=Ridge(alpha=a,fit_intercept=False,solver='lsqr',tol=1e-7,max_iter=2000).fit(X,y,sample_weight=w)
            pred=centered_prediction(model.predict(V),va)
            records.append({'inner_fold':k,'alpha':a,'image_mse':image_mse(va[ycol],pred,va),'validation_images':va.image_key.nunique(),
                            'training_buildings':'|'.join(sorted(tr.building.unique())),'validation_buildings':'|'.join(sorted(va.building.unique()))})
    tab=pd.DataFrame(records)
    # Image-equal aggregate across validation folds, not equal folds of unequal size.
    scores=tab.groupby('alpha').apply(lambda g:np.average(g.image_mse,weights=g.validation_images),include_groups=False)
    best=float(scores.idxmin())
    return best,tab


def history_table(train,test,ycol):
    byperson=train.groupby('worker_id')[ycol].mean()
    byg=train.groupby(['worker_id','room_type_model'])[ycol].mean()
    d=test[['object_id','image_key','image','building','worker_id','room_type_model','difficulty']].copy()
    d['history_person_mean']=d.worker_id.map(byperson)
    d['history_same_purpose_mean']=[byg.get((w,r),np.nan) for w,r in zip(d.worker_id,d.room_type_model)]
    for label,keys in [('person',['worker_id']),('same_purpose',['worker_id','room_type_model'])]:
        ag=train.groupby(keys).agg(n_records=('object_id','size'),n_images=('image_key','nunique'),n_buildings=('building','nunique'))
        for c in ag:
            if len(keys)==1:d[label+'_'+c]=d.worker_id.map(ag[c]).fillna(0).astype(int)
            else:d[label+'_'+c]=[int(ag[c].get((w,r),0)) for w,r in zip(d.worker_id,d.room_type_model)]
    return d


def fit_outcome(d,outcome,num_cols,outdir,hyper_from=None):
    d=d.copy().reset_index(drop=True)
    d['relative']=rel_target(d,outcome)
    d=d[d.relative.notna()].copy().reset_index(drop=True)
    # All models and diagnostic histories are evaluated on identical records.
    preds=[];folds=[];cvtabs=[];support=[];coef_records=[];alpha_lookup={}
    for bi,held in enumerate(sorted(d.building.unique())):
        train=d[d.building!=held].copy();test=d[d.building==held].copy()
        if 'training_allowed' in train:
            train=train[train.training_allowed].copy()
            # Legacy gate sensitivity excludes gated scores even from training peer means.
            train['relative']=rel_target(train,outcome)
            train=train[train.relative.notna()].copy()
        hs=history_table(train,test,'relative');hs['outcome']=outcome;support.append(hs)
        bases={'zero':np.zeros(len(test)),
               'person_history':centered_prediction(hs.history_person_mean.fillna(0).to_numpy(),test),
               'same_purpose_history':centered_prediction(hs.history_same_purpose_mean.fillna(hs.history_person_mean).fillna(0).to_numpy(),test)}
        for method,parts in MODEL_FEATURES.items():
            if hyper_from is None:
                alpha,cv=inner_select(train,'relative',parts,num_cols)
                cv['held_out_building']=held;cv['method']=method;cv['outcome']=outcome;cvtabs.append(cv)
            else:alpha=hyper_from[(held,method)]
            alpha_lookup[(held,method)]=alpha
            feature=FrozenFeatures(parts,num_cols).fit(train)
            X=feature.transform(train);T=feature.transform(test)
            model=Ridge(alpha=alpha,fit_intercept=False,solver='lsqr',tol=1e-7,max_iter=2000).fit(X,train.relative.to_numpy(),sample_weight=image_weights(train))
            bases[method]=centered_prediction(model.predict(T),test)
            folds.append({'outcome':outcome,'method':method,'held_out_building':held,'alpha':alpha,
                          'train_rows':len(train),'train_images':train.image_key.nunique(),'train_buildings':train.building.nunique(),'train_people':train.worker_id.nunique(),
                          'target_rows':len(test),'target_images':test.image_key.nunique(),'target_people':test.worker_id.nunique(),
                          'train_building_ids':'|'.join(sorted(train.building.unique())),
                          'feature_count':X.shape[1],'inner_selection':'Primary analysis per-fold alpha reused without reselection' if hyper_from is not None else '5-building-group inner CV; image MSE'})
            coef_records.append({'outcome':outcome,'method':method,'held_out_building':held,'alpha':alpha,'feature_schema':feature.dump(),'coef':model.coef_.tolist()})
        for method,p in bases.items():
            t=test[['object_id','image_key','image','building','worker_id','room_type_model','room_type_status','difficulty']].copy()
            t['outcome']=outcome;t['method']=method;t['observed']=test[outcome].to_numpy();t['actual_relative']=test.relative.to_numpy();t['predicted_relative']=p
            t['error']=p-t.actual_relative;t['absolute_error']=abs(t.error);t['squared_error']=t.error**2
            t['same_purpose_history_buildings']=hs.same_purpose_n_buildings.to_numpy();t['history_buildings']=hs.person_n_buildings.to_numpy()
            preds.append(t)
        print(json.dumps({'outcome':outcome,'fold':bi+1,'total_folds':d.building.nunique(),'held':held,'elapsed':round(time.time()-START,1)}),flush=True)
    P=pd.concat(preds,ignore_index=True);H=pd.concat(support,ignore_index=True)
    save(P,outdir/f'OOF_{outcome}.csv.gz');save(H,outdir/f'HISTORY_SUPPORT_{outcome}.csv.gz');save(pd.DataFrame(folds),outdir/f'FOLDS_{outcome}.csv')
    if cvtabs:save(pd.concat(cvtabs),outdir/f'INNER_CV_{outcome}.csv.gz')
    import gzip
    with gzip.open(outdir/f'MODELS_{outcome}.jsonl.gz','wt',encoding='utf-8') as f:
        for x in coef_records:f.write(json.dumps(x,ensure_ascii=False)+'\n')
    return P,H,alpha_lookup


def corr(a,b):
    a=np.asarray(a);b=np.asarray(b);ok=np.isfinite(a)&np.isfinite(b)
    if ok.sum()<3 or np.std(a[ok])<1e-10 or np.std(b[ok])<1e-10:return np.nan
    return float(np.corrcoef(a[ok],b[ok])[0,1])


def summarize(P,outdir):
    results=[]
    for keys,g in P.groupby(['outcome','method','image_key','image','building','room_type_model','difficulty'],sort=True):
        d=dict(zip(['outcome','method','image_key','image','building','room_type_model','difficulty'],keys))
        d.update(records=len(g),people=g.worker_id.nunique(),mae=g.absolute_error.mean(),mse=g.squared_error.mean(),
                 pearson=corr(g.actual_relative,g.predicted_relative),
                 spearman=float(spearmanr(g.actual_relative,g.predicted_relative).statistic) if g.predicted_relative.std()>1e-10 else np.nan,
                 mean_actual_relative=g.actual_relative.mean(),mean_predicted_relative=g.predicted_relative.mean())
        results.append(d)
    I=pd.DataFrame(results);save(I,outdir/'PER_IMAGE_METHODS.csv.gz')
    B=I.groupby(['outcome','method','building'],as_index=False).agg(images=('image_key','size'),mae=('mae','mean'),mse=('mse','mean'),median_spearman=('spearman','median'))
    save(B,outdir/'PER_BUILDING_METHODS.csv')
    summaries=[]
    for (oc,m),g in I.groupby(['outcome','method']):
        b=B[(B.outcome==oc)&(B.method==m)]
        summaries.append({'outcome':oc,'method':m,'images':len(g),'buildings':g.building.nunique(),'image_equal_mae':g.mae.mean(),'image_equal_rmse':np.sqrt(g.mse.mean()),
                          'building_equal_mae':b.mae.mean(),'building_equal_rmse':np.sqrt(b.mse.mean()),'median_image_spearman':g.spearman.median()})
    save(pd.DataFrame(summaries),outdir/'METHOD_SUMMARY.csv')
    pairs=[('person_history','same_purpose_history'),('person_ridge','person_purpose'),('person_ridge','person_geometry'),('person_geometry','person_geometry_purpose'),('zero','person_ridge'),('person_history','person_geometry_purpose'),('person_history','person_purpose'),('zero','person_geometry')]
    diffs=[];boots=[];rng=np.random.default_rng(SEED)
    for oc in P.outcome.unique():
        for base,new in pairs:
            a=I[(I.outcome==oc)&(I.method==base)].drop(columns=['method']);b=I[(I.outcome==oc)&(I.method==new)].drop(columns=['method'])
            z=a.merge(b,on=['outcome','image_key','image','building','room_type_model','difficulty'],suffixes=('_base','_new'),validate='one_to_one')
            z['baseline']=base;z['augmented']=new;z['mae_gain']=z.mae_base-z.mae_new;z['mse_gain']=z.mse_base-z.mse_new;diffs.append(z)
            bkeys=sorted(z.building.unique());groups={k:z[z.building==k] for k in bkeys}
            ag=z.groupby('building').agg(n=('image_key','size'),gain=('mae_gain','sum'),mse_base=('mse_base','sum'),mse_new=('mse_new','sum')).reindex(bkeys)
            draw=rng.choice(len(bkeys),size=(2000,len(bkeys)),replace=True)
            n=ag.n.to_numpy()[draw].sum(axis=1)
            mean=ag.gain.to_numpy()[draw].sum(axis=1)/n
            rmse=np.sqrt(ag.mse_base.to_numpy()[draw].sum(axis=1)/n)-np.sqrt(ag.mse_new.to_numpy()[draw].sum(axis=1)/n)
            v=np.column_stack([mean,rmse])
            byb=z.groupby('building').mae_gain.mean()
            boots.append({'outcome':oc,'baseline':base,'augmented':new,'images':len(z),'buildings':len(bkeys),'image_equal_mae_gain':z.mae_gain.mean(),
                          'image_equal_rmse_gain':np.sqrt(z.mse_base.mean())-np.sqrt(z.mse_new.mean()),
                          'image_mae_improve':int((z.mae_gain>0).sum()),'image_mae_worse':int((z.mae_gain<0).sum()),'building_mae_improve':int((byb>0).sum()),'building_mae_worse':int((byb<0).sum()),
                          'mae_gain_building_boot_lo':np.quantile(v[:,0],.025),'mae_gain_building_boot_hi':np.quantile(v[:,0],.975),
                          'rmse_gain_building_boot_lo':np.quantile(v[:,1],.025),'rmse_gain_building_boot_hi':np.quantile(v[:,1],.975),
                          'building_equal_mae_gain':byb.mean(),'building_gain_min':byb.min(),'building_gain_max':byb.max()})
    D=pd.concat(diffs,ignore_index=True);save(D,outdir/'PAIRED_IMAGE_GAIN.csv.gz');save(pd.DataFrame(boots),outdir/'PAIRED_GAIN_SUMMARY.csv')
    for groupname,groupcols in [('purpose',['room_type_model']),('difficulty',['difficulty'])]:
        z=D.groupby(['outcome','baseline','augmented']+groupcols,as_index=False).agg(images=('image_key','size'),buildings=('building','nunique'),mae_gain=('mae_gain','mean'),mse_gain=('mse_gain','mean'),images_improve=('mae_gain',lambda x:int((x>0).sum())),images_worse=('mae_gain',lambda x:int((x<0).sum())))
        save(z,outdir/f'GAIN_BY_{groupname.upper()}.csv')
    byperson=P.groupby(['outcome','method','worker_id'],as_index=False).agg(records=('object_id','size'),images=('image_key','nunique'),buildings=('building','nunique'),mae=('absolute_error','mean'),mse=('squared_error','mean'),actual_relative_mean=('actual_relative','mean'),predicted_relative_mean=('predicted_relative','mean'))
    save(byperson,outdir/'PER_PERSON_METHODS.csv')
    bywtype=P.groupby(['outcome','method','worker_id','room_type_model'],as_index=False).agg(records=('object_id','size'),images=('image_key','nunique'),buildings=('building','nunique'),mae=('absolute_error','mean'),mse=('squared_error','mean'),actual_relative_mean=('actual_relative','mean'),predicted_relative_mean=('predicted_relative','mean'),minimum_other_building_type_support=('same_purpose_history_buildings','min'),median_other_building_type_support=('same_purpose_history_buildings','median'))
    save(bywtype,outdir/'PER_PERSON_PURPOSE_METHODS.csv.gz')
    pp=[]
    for oc in P.outcome.unique():
        x=byperson[(byperson.outcome==oc)&(byperson.method=='person_geometry')];y=byperson[(byperson.outcome==oc)&(byperson.method=='person_geometry_purpose')]
        z=x.merge(y,on=['outcome','worker_id'],suffixes=('_base','_new'))
        z['mae_gain']=z.mae_base-z.mae_new;pp.append(z)
    save(pd.concat(pp),outdir/'PER_PERSON_INCREMENTAL_GAIN.csv')
    return I,D


def repeatability(P,H,outdir):
    # Each actual held-out outcome is linked to only history outside its building.
    records=[]
    for oc,g in H.groupby('outcome'):
        a=P[(P.outcome==oc)&(P.method=='person_history')][['object_id','actual_relative','predicted_relative']]
        z=g.merge(a,on='object_id',validate='one_to_one')
        z['history_type_deviation']=z.history_same_purpose_mean-z.history_person_mean
        z['target_after_general']=z.actual_relative-z.predicted_relative
        z['repeatable_source_supported']=z.same_purpose_n_buildings>=1
        z['repeatable_source_2buildings']=z.same_purpose_n_buildings>=2
        records.append(z)
    R=pd.concat(records,ignore_index=True);save(R,outdir/'CROSS_BUILDING_REPEATABILITY_ROWS.csv.gz')
    rows=[]
    for (oc,room),g in R.groupby(['outcome','room_type_model']):
        g=g[g.repeatable_source_supported]
        for bud in [1,2]:
            z=g[g.same_purpose_n_buildings>=bud]
            rows.append({'outcome':oc,'room_type':room,'min_history_buildings':bud,'records':len(z),'images':z.image_key.nunique(),'buildings':z.building.nunique(),'workers':z.worker_id.nunique(),
                         'corr_same_type_history_vs_target':corr(z.history_same_purpose_mean,z.actual_relative),
                         'corr_general_history_vs_target':corr(z.history_person_mean,z.actual_relative),
                         'corr_type_deviation_vs_target_after_general':corr(z.history_type_deviation,z.target_after_general),
                         'type_deviation_sign_agreement':np.mean(np.sign(z.history_type_deviation)==np.sign(z.target_after_general)) if len(z) else np.nan,
                         'median_source_images':z.same_purpose_n_images.median(),'median_source_buildings':z.same_purpose_n_buildings.median()})
    save(pd.DataFrame(rows),outdir/'REPEATABILITY_BY_PURPOSE.csv')
    # Worker x purpose summaries are descriptive outcome cards, not immutable types.
    cards=[]
    for (oc,w,room),g in R.groupby(['outcome','worker_id','room_type_model']):
        cards.append({'outcome':oc,'worker_id':w,'room_type':room,'images':g.image_key.nunique(),'buildings':g.building.nunique(),'records':len(g),
                      'relative_mean':g.actual_relative.mean(),'general_history_mean':g.predicted_relative.mean(),'after_general_mean':g.target_after_general.mean(),
                      'corr_same_type_history_vs_target':corr(g.history_same_purpose_mean,g.actual_relative),
                      'corr_type_deviation_vs_target_after_general':corr(g.history_type_deviation,g.target_after_general),
                      'same_type_history_available_rows':int(g.history_same_purpose_mean.notna().sum()),
                      'same_type_history_ge2buildings_rows':int((g.same_purpose_n_buildings>=2).sum()),
                      'history_type_deviation_mean':g.history_type_deviation.mean()})
    save(pd.DataFrame(cards),outdir/'PERSON_PURPOSE_CARDS.csv')


def numeric_columns(d):
    # The source contract evolves; explicitly resolve and save actual chosen fields.
    priority=[['ref_turn5'],['ref_short_turn_edges','ref_short_edges'],['ref_min_horizontal_deg','ref_min_horizontal_angle','ref_min_horizontal'],['ref_radius_p90_h','ref_radius_median'],['ref_H']]
    chosen=[]
    for alts in priority:
        for c in alts:
            if c in d and pd.to_numeric(d[c],errors='coerce').notna().mean()>=.5:
                chosen.append(c);break
    return chosen


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--inputs',type=Path,required=True);ap.add_argument('--out',type=Path,required=True);ap.add_argument('--condition',default='manual');ap.add_argument('--layer',default='ordinary');ap.add_argument('--skip-structure',action='store_true');ap.add_argument('--summarize-only',action='store_true');ap.add_argument('--gate-file',type=Path);ap.add_argument('--reuse-alpha-dir',type=Path);ap.add_argument('--outcomes',nargs='+')
    a=ap.parse_args();a.out.mkdir(parents=True,exist_ok=True)
    d=pd.read_csv(a.inputs/'annotations.csv.gz',dtype={'object_id':str},low_memory=False)
    d=d[(d.condition==a.condition)&(d.layer==a.layer)&d.formal_quality&d.Q.notna()&d.D10.notna()].copy()
    assert not d[['image_key','worker_id']].duplicated().any()
    d['room_type_model']=d.room_type_model.fillna('__MISSING__');d['difficulty']=d.difficulty.fillna('__UNKNOWN__')
    if a.gate_file:
        gate=pd.read_csv(a.gate_file,dtype={'object_id':str}).set_index('object_id').same_room_v2_training_allowed
        d['training_allowed']=d.object_id.map(gate).fillna(False).astype(bool)
    nums=numeric_columns(d)
    print('ACTUAL_NUMERIC_REFERENCE_FEATURES',nums,flush=True)
    receipt={'condition':a.condition,'layer':a.layer,'records':len(d),'images':d.image_key.nunique(),'buildings':d.building.nunique(),'people':d.worker_id.nunique(),
             'source_input_sha256':hashlib.sha256((a.inputs/'annotations.csv.gz').read_bytes()).hexdigest(),'numeric_reference_predictors':nums,
             'predictor_availability':'Known worker identity, frozen purpose/difficulty, and known reference structural metadata. Reference-geometry model is diagnostic, not a GT-free deployment claim.',
             'target_definition':'value minus same-image mean of all OTHER formally evaluable workers; target is evaluation-only',
             'target_building_exclusion':'entire building from all fit, histories, and hyperparameter selection',
             'model_definitions':{k:list(v) for k,v in MODEL_FEATURES.items()},'alpha_candidates':ALPHAS,'inner_folds':5,'seed':SEED,
             'prediction_centering':'Subtract mean prediction among known target worker identities without using target outcomes.',
             'weighting':'Training equal total image weight, normalized to mean record weight one; evaluation mean image errors, separately building equal.',
             'new_fusion_endpoints':0,'new_classification':False,'run_mode':'reaggregate_saved_OOF' if a.summarize_only else 'fit_and_evaluate','legacy_admission':('Sensitivity: historical training gate; excluded records also absent from training peer means; target evaluation unchanged' if a.gate_file else 'No retroactive v1 development gate; formal current v2 quality qualification only.'),
             'D10_sensitivity':'Same records and Q-selected per-fold alpha, no new outcome-specific hyperparameter search.'}
    (a.out/'METHOD_RECEIPT.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2)+'\n')
    outcomes=a.outcomes or (['Q','D10']+([] if a.skip_structure else ['annotation_turn5']))
    ps=[];hs=[];hyper=None
    for oc in outcomes:
        if a.summarize_only:
            P=pd.read_csv(a.out/f'OOF_{oc}.csv.gz',dtype={'object_id':str});H=pd.read_csv(a.out/f'HISTORY_SUPPORT_{oc}.csv.gz',dtype={'object_id':str})
        else:
            reused=hyper if oc=='D10' else None
            if a.reuse_alpha_dir:
                fs=pd.read_csv(a.reuse_alpha_dir/f'FOLDS_{oc}.csv')
                reused={(r.held_out_building,r.method):r.alpha for r in fs.itertuples()}
            P,H,alphas=fit_outcome(d[d[oc].notna()],oc,nums,a.out,hyper_from=reused)
            if oc=='Q':hyper=alphas
        ps.append(P);hs.append(H)
    P=pd.concat(ps);H=pd.concat(hs)
    summarize(P,a.out);repeatability(P,H,a.out)
    receipt['completed_outcomes']=outcomes;receipt['OOF_rows']=len(P);receipt['elapsed_seconds']=time.time()-START
    receipt['all_oof_group_mean_prediction_abs_max']=float(P.groupby(['outcome','method','image_key']).predicted_relative.mean().abs().max())
    (a.out/'COMPLETE.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(receipt,ensure_ascii=False,indent=2),flush=True)

START=time.time()
if __name__=='__main__':main()
