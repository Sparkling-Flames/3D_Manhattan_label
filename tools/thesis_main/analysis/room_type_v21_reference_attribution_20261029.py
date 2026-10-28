"""Frozen-fold hyperparameter attribution for same-purpose image prediction."""
import os
for name in ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS'):os.environ[name]='1'
import json
import sys
import numpy as np
import pandas as pd
from sklearn.model_selection import GroupKFold
from .rebuild_v21_room_type_20261028 import BASE, OUT

TARGET=OUT/'reference_only_attribution'
METHODS=['geometry_rich','geometry_purpose_rich']
NUM=['ref_turn5','log_H','short_fraction','log_min_angle','log_radius']


def prepare(images,keys):
    d=images[(images.condition=='manual')&(images.layer=='ordinary')&(images.n_formal>0)&images.image_key.isin(keys)].copy().sort_values('image_key')
    assert d.image_key.is_unique and set(d.image_key)==keys
    d['purpose']=d.room_type_model.fillna('__MISSING__');d['difficulty']=d.difficulty.fillna('__UNKNOWN__')
    d['log_H']=np.log1p(d.ref_H);d['short_fraction']=d.ref_short_edges/d.ref_turn5
    d['log_min_angle']=np.log(np.maximum(d.ref_min_horizontal_deg,1e-5));d['log_radius']=np.log(np.maximum(d.ref_radius_p90_h,1e-5))
    return d


def fit_fixed(data,models,engine,label):
    rows=[];folds=[]
    for held in sorted(data.building.unique()):
        train=data[data.building.ne(held)];test=data[data.building.eq(held)]
        assert not train.empty and not test.empty and held not in set(train.building)
        for method in METHODS:
            cfg=models[(models.metric=='Q')&(models.method==method)&(models.held_out_building==held)]
            assert len(cfg)==1
            cfg=cfg.iloc[0];cat=['difficulty']+(['purpose'] if method=='geometry_purpose_rich' else [])
            assert cfg.numeric_features=='|'.join(NUM) and cfg.categorical_features=='|'.join(cat)
            model=engine.make_pipeline(cat,NUM,cfg.family,float(cfg.alpha));model.fit(train,train.mean_Q.to_numpy())
            pred=np.clip(model.predict(test),0,100)
            for row,value in zip(test.itertuples(),pred):rows.append(dict(experiment=label,method=method,image_key=row.image_key,image=row.image,building=held,actual=row.mean_Q,predicted=value,absolute_error=abs(value-row.mean_Q)))
            folds.append(dict(experiment=label,method=method,held_out_building=held,train_images=len(train),test_images=len(test),family=cfg.family,alpha=cfg.alpha,heldout_excluded=True))
    return pd.DataFrame(rows),pd.DataFrame(folds)


def fit_nested(data,engine):
    """Same inner building folds, candidate order and image MAE as the original portfolio."""
    candidates=[('ridge',v) for v in [0.1,1.,10.,100.]]+[('ridge_quadratic',v) for v in [10.,100.]]+[('hgb',0.)]
    predictions=[];selections=[];tuning=[];splits=[]
    for held in sorted(data.building.unique()):
        train=data[data.building.ne(held)];test=data[data.building.eq(held)];y=train.mean_Q.to_numpy();groups=train.building.to_numpy()
        cv=list(GroupKFold(n_splits=min(5,len(set(groups)))).split(train,y,groups))
        for number,(ix,jx) in enumerate(cv):
            a=set(train.iloc[ix].building);b=set(train.iloc[jx].building)
            assert not a&b and held not in a|b
            splits.append(dict(held_out_building=held,inner_fold=number,train_buildings='|'.join(sorted(a)),validation_buildings='|'.join(sorted(b)),train_images=len(ix),validation_images=len(jx)))
        for method in METHODS:
            cat=['difficulty']+(['purpose'] if method=='geometry_purpose_rich' else [])
            scores=[]
            for family,alpha in candidates:
                fold_scores=[]
                for ix,jx in cv:
                    model=engine.make_pipeline(cat,NUM,family,alpha);model.fit(train.iloc[ix],y[ix])
                    pred=np.clip(model.predict(train.iloc[jx]),0,100);fold_scores.append(np.mean(abs(pred-y[jx])))
                score=float(np.mean(fold_scores));scores.append(score)
                tuning.append(dict(held_out_building=held,method=method,family=family,alpha=alpha,inner_mae=score,inner_folds=len(cv)))
            index=int(np.argmin(scores));family,alpha=candidates[index]
            model=engine.make_pipeline(cat,NUM,family,alpha);model.fit(train,y);pred=np.clip(model.predict(test),0,100)
            selections.append(dict(held_out_building=held,method=method,train_images=len(train),test_images=len(test),family=family,alpha=alpha,inner_mae=scores[index]))
            for row,value in zip(test.itertuples(),pred):predictions.append(dict(experiment='v21_original177_original_nested_selection',method=method,image_key=row.image_key,image=row.image,building=held,actual=row.mean_Q,predicted=value,absolute_error=abs(value-row.mean_Q)))
        print('nested',held,flush=True)
    return pd.DataFrame(predictions),pd.DataFrame(selections),pd.DataFrame(tuning),pd.DataFrame(splits)


def main():
    sys.path.insert(0,str(BASE/'code'));import image_similarity as engine
    support=pd.read_csv(OUT/'inputs/SUPPORT.csv');oldkeys=set(support.loc[support.support.eq('original_support'),'image_key']);newkeys=set(support.loc[support.support.eq('new_support'),'image_key'])
    assert len(oldkeys)==177 and len(newkeys)==29 and not oldkeys&newkeys
    repeated=pd.read_csv(BASE/'results/image/LOBO_TARGET_PURPOSE_SUPPORT.csv');evalkeys=set(repeated.loc[repeated.repeated_recorded_purpose,'image_key'])
    assert len(evalkeys)==161 and evalkeys<=oldkeys
    old=prepare(pd.read_csv(BASE/'inputs/images.csv'),oldkeys);updated=prepare(pd.read_csv(OUT/'inputs/images.csv'),oldkeys);full=prepare(pd.read_csv(OUT/'inputs/images.csv'),oldkeys|newkeys)
    models=pd.read_csv(BASE/'results/image/LOBO_MODELS.csv');oldfit,oldfold=fit_fixed(old,models,engine,'v2_original177_fixed_hyperparameters')
    saved=pd.read_csv(BASE/'results/image/LOBO_IMAGE_PREDICTIONS.csv.gz');saved=saved[(saved.metric=='Q')&saved.method.isin(METHODS)]
    parity=oldfit.merge(saved,on=['method','image_key'],validate='one_to_one',suffixes=('_fit','_saved'))
    assert len(parity)==177*2 and np.allclose(parity.predicted_fit,parity.predicted_saved,atol=1e-8,rtol=0)
    target=updated.set_index('image_key').mean_Q
    frozen=oldfit.copy();frozen['experiment']='v2_frozen_predictions_v21_targets';frozen['actual']=frozen.image_key.map(target);frozen['absolute_error']=(frozen.predicted-frozen.actual).abs()
    revised,revised_folds=fit_fixed(updated,models,engine,'v21_original177_fixed_hyperparameters')
    expanded,expanded_folds=fit_fixed(full,models,engine,'v21_all206_fixed_hyperparameters')
    nested,nested_folds,nested_tuning,nested_splits=fit_nested(updated,engine)
    selected=pd.read_csv(OUT/'results/image/LOBO_IMAGE_PREDICTIONS.csv.gz');selected=selected[(selected.metric=='Q')&selected.method.isin(METHODS)].copy();selected['experiment']='v21_all206_original_nested_selection';selected=selected[['experiment','method','image_key','image','building','actual','predicted','absolute_error']]
    allp=pd.concat([oldfit,frozen,revised,expanded,nested,selected],ignore_index=True)
    assert not allp.duplicated(['experiment','method','image_key']).any()
    result=allp[allp.image_key.isin(evalkeys)].copy();assert result.groupby(['experiment','method']).size().eq(161).all()
    ref=result[result.experiment.eq('v21_original177_fixed_hyperparameters')].set_index(['method','image_key']).actual
    for label in ['v2_frozen_predictions_v21_targets','v21_original177_original_nested_selection','v21_all206_fixed_hyperparameters','v21_all206_original_nested_selection']:
        z=result[result.experiment.eq(label)].set_index(['method','image_key']).actual;assert np.allclose(z.sort_index(),ref.sort_index(),atol=1e-10)
    table=result.groupby(['experiment','method'],as_index=False).agg(images=('image_key','nunique'),buildings=('building','nunique'),mae=('absolute_error','mean'),rmse=('absolute_error',lambda x:np.sqrt(np.mean(np.square(x)))))
    wide=result.pivot(index=['experiment','image_key','building'],columns='method',values='absolute_error').reset_index();wide['gain']=wide.geometry_rich-wide.geometry_purpose_rich
    rng=np.random.default_rng(2026102901);contrasts=[]
    for label,g in wide.groupby('experiment'):
        b=g.groupby('building').gain.agg(['sum','count']);draw=rng.integers(0,len(b),(5000,len(b)));sample=b['sum'].to_numpy()[draw].sum(axis=1)/b['count'].to_numpy()[draw].sum(axis=1)
        contrasts.append(dict(experiment=label,images=len(g),buildings=len(b),gain_mae=g.gain.mean(),improved_images=int((g.gain>1e-10).sum()),worsened_images=int((g.gain< -1e-10).sum()),building_boot_low=np.quantile(sample,.025),building_boot_high=np.quantile(sample,.975)))
    shifts=[]
    for older,newer in [('v2_original177_fixed_hyperparameters','v21_original177_fixed_hyperparameters'),('v21_original177_fixed_hyperparameters','v21_all206_fixed_hyperparameters'),('v21_original177_original_nested_selection','v21_all206_original_nested_selection'),('v21_all206_fixed_hyperparameters','v21_all206_original_nested_selection')]:
        a=wide[wide.experiment.eq(older)];b=wide[wide.experiment.eq(newer)]
        pair=a.merge(b,on=['image_key','building'],validate='one_to_one',suffixes=('_old','_new'));assert len(pair)==161
        pair['difference']=pair.gain_new-pair.gain_old;by=pair.groupby('building').difference.agg(['sum','count'])
        draw=rng.integers(0,len(by),(5000,len(by)));sample=by['sum'].to_numpy()[draw].sum(axis=1)/by['count'].to_numpy()[draw].sum(axis=1)
        shifts.append(dict(older=older,newer=newer,images=len(pair),buildings=len(by),old_gain=pair.gain_old.mean(),new_gain=pair.gain_new.mean(),gain_change=pair.difference.mean(),building_boot_low=np.quantile(sample,.025),building_boot_high=np.quantile(sample,.975)))
    TARGET.mkdir(parents=True,exist_ok=True)
    allp.to_csv(TARGET/'PREDICTIONS.csv.gz',index=False,compression={'method':'gzip','mtime':0});pd.concat([oldfold,revised_folds,expanded_folds],ignore_index=True).to_csv(TARGET/'FIXED_FOLDS.csv',index=False)
    nested_folds.to_csv(TARGET/'NESTED_FOLDS.csv',index=False);nested_tuning.to_csv(TARGET/'NESTED_TUNING.csv',index=False);nested_splits.to_csv(TARGET/'NESTED_INNER_SPLITS.csv',index=False)
    table.to_csv(TARGET/'MODEL_COMPARISON.csv',index=False);pd.DataFrame(contrasts).to_csv(TARGET/'PURPOSE_INCREMENT.csv',index=False);pd.DataFrame(shifts).to_csv(TARGET/'PAIRED_INCREMENT_CHANGES.csv',index=False)
    checks=dict(original_training_images=len(old),updated_training_images=len(updated),expanded_training_images=len(full),evaluation_images=len(evalkeys),evaluation_buildings=result.building.nunique(),original_prediction_parity_rows=len(parity),original_prediction_max_abs_error=float(abs(parity.predicted_fit-parity.predicted_saved).max()),frozen_fold_hyperparameters=True,nested_original177=True,nested_candidates=7,nested_inner_folds=5,target_building_excluded=True,new_sampling=False,new_fusion=False,new_scoring=False,selected_all206='existing nested CV result; not fixed-hyperparameter control')
    (TARGET/'CHECKS.json').write_text(json.dumps(checks,indent=2)+'\n',encoding='utf8');print(table.to_string(index=False),flush=True)


if __name__=='__main__':main()
