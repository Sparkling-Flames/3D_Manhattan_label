"""独立核对同用途研究的输入、比较、留出预测；不修改作者结果。"""
import os
for _name in ('OMP_NUM_THREADS', 'OPENBLAS_NUM_THREADS', 'MKL_NUM_THREADS'):
    os.environ[_name] = '1'
import argparse
import csv
import gzip
import itertools
import json
from pathlib import Path
import numpy as np
import pandas as pd
from scipy.stats import rankdata
from sklearn.compose import ColumnTransformer
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler, PolynomialFeatures
from sklearn.impute import SimpleImputer
from sklearn.linear_model import Ridge
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.model_selection import GroupKFold

ROOT = Path(__file__).resolve().parents[3]
STUDY = ROOT / 'research/statistics/room_type_similarity_20261027'
OUT = STUDY / 'independent_review_20261027'


def read(name):
    return pd.read_csv(STUDY / name, low_memory=False)


def equal(a, b, name, tol=1e-9):
    aa, bb = np.asarray(a, dtype=float), np.asarray(b, dtype=float)
    assert aa.shape == bb.shape, (name, aa.shape, bb.shape)
    assert np.array_equal(np.isnan(aa), np.isnan(bb)), (name, 'missingness')
    err = float(np.nanmax(np.abs(aa-bb))) if np.isfinite(aa).any() else 0.
    assert err < tol, (name, err)
    return err


def save_json(name, value):
    OUT.mkdir(exist_ok=True)
    (OUT / name).write_text(json.dumps(value, ensure_ascii=False, indent=2,
        default=lambda x: x.item() if isinstance(x, np.generic) else str(x)), encoding='utf-8')


def load_primary():
    a = read('inputs/annotations.csv.gz')
    a = a[a.condition.eq('manual') & a.layer.eq('ordinary') & a.formal_quality
          & a.Q.notna() & a.D10.notna()].copy()
    d = read('inputs/images.csv')
    d = d[d.condition.eq('manual') & d.layer.eq('ordinary') & d.n_formal.gt(0)].copy()
    d = d.sort_values('image_key').reset_index(drop=True)
    repeated = set(d.loc[d.room_type_status.eq('recorded_purpose') &
        d.groupby('room_type_model').building.transform('nunique').ge(2), 'image_key'])
    assert (len(a), len(d), len(repeated)) == (5719, 177, 161)
    return a, d, repeated


def core():
    files = []
    for path in sorted(STUDY.rglob('*')):
        if not path.is_file() or OUT in path.parents:
            continue
        if path.name.endswith(('.csv', '.csv.gz', '.jsonl.gz', '.json.gz', '.json')):
            opener = gzip.open if path.suffix == '.gz' else open
            with opener(path, 'rt', encoding='utf-8-sig', newline='') as f:
                if '.csv' in path.name:
                    rows = csv.reader(f); header = next(rows); n = 0
                    for row in rows:
                        assert len(row) == len(header), (path, n, 'row width')
                        n += 1
                elif '.jsonl' in path.name:
                    n = sum(1 for line in f if json.loads(line) is not None)
                else:
                    json.load(f); n = None
            files.append(dict(path=str(path.relative_to(STUDY)), rows=n))
    pd.DataFrame(files).to_csv(OUT / 'FILE_READS.csv', index=False)
    with gzip.open(ROOT/'research/statistics/v2_evidence_audit_20261019/records.json.gz', 'rt', encoding='utf-8') as f:
        canonical = {x['object_id']: x for x in json.load(f)['records']}
    all_a = read('inputs/annotations.csv.gz')
    assert len(all_a) == len(canonical) == 10439 and all_a.object_id.is_unique
    for row in all_a.itertuples():
        r = canonical[row.object_id]
        for col in ('worker_id', 'image_id', 'condition', 'quality_use', 'reference_id', 'reference_version'):
            value = getattr(row, col)
            assert value == r[col] or (pd.isna(value) and r[col] in (None, '')), (row.object_id, col)
        assert row.formal_quality == r['quality_usable']
        assert row.difficulty == r['current_class']
        label = r['image_evidence']['room_spatial_classification'].get('coarse_type')
        assert (None if pd.isna(row.room_type) else row.room_type) == (label or None)
        if row.formal_quality:
            equal([row.Q, row.D10], [r['B8L2'], r['D10']], 'source scores')
    a, d, repeated = load_primary()
    for metric in ('Q','D10'):
        actual = a.groupby('image_key')[metric].mean()
        equal(d['mean_'+metric], d.image_key.map(actual), 'image means '+metric)
    # Frozen structural features are compared against repository source, not author receipts.
    features = pd.read_csv(ROOT/'research/difficulty/difficulty_mechanisms_v2_20261020/record_conditions.csv.gz', low_memory=False).set_index('object_id')
    for col in ('annotation_turn5', 'turn_delta', 'bottom_bias_9', 'ref_turn5', 'ref_H'):
        if col in features:
            equal(a[col], a.object_id.map(features[col]), 'feature '+col)
    meta = d.set_index('image_key')
    # Rebuild all saved image prediction errors and common-support summaries.
    p = read('results/image/LOBO_IMAGE_PREDICTIONS.csv.gz')
    assert len(p) == 4248 and not p.duplicated(['metric','method','image_key']).any()
    sums=[]
    for (metric, method), g in p.groupby(['metric','method']):
        equal(g.actual, g.image_key.map(meta['mean_'+metric]), 'prediction truth')
        equal(g.absolute_error, abs(g.predicted-g.actual), 'prediction absolute error')
        for name, h in [('all177',g), ('main161',g[g.image_key.isin(repeated)])]:
            sums.append(dict(metric=metric,method=method,support=name,images=len(h),
                mae=abs(h.predicted-h.actual).mean(),rmse=np.sqrt(((h.predicted-h.actual)**2).mean()),
                building_mae=h.assign(ae=abs(h.predicted-h.actual)).groupby('building').ae.mean().mean()))
    sums=pd.DataFrame(sums); sums.to_csv(OUT/'IMAGE_PREDICTION_RECOMPUTED.csv',index=False)
    for row in read('key_tables/K02_IMAGE_PREDICTION_161.csv').itertuples():
        hit=sums[(sums.metric==row.metric)&(sums.method==row.method)&(sums.support=='main161')].iloc[0]
        equal([hit.mae,hit.rmse,hit.building_mae],[row.mae,row.rmse,row.building_equal_mae],'key image model')
    gain_rows=[]
    for metric in ('Q','D10'):
        h=p[p.metric.eq(metric)&p.image_key.isin(repeated)].pivot(index=['image_key','building'],columns='method',values='absolute_error')
        gain=h.geometry_rich-h.geometry_purpose_rich
        bg=gain.groupby('building').mean()
        gain_rows.append(dict(metric=metric,gain=gain.mean(),improve=int((gain>1e-10).sum()),
            buildings_improve=int((bg>1e-10).sum()),building_gain=bg.mean()))
    pd.DataFrame(gain_rows).to_csv(OUT/'IMAGE_PURPOSE_GAIN.csv',index=False)
    # No target response enters the independently rebuilt person-history prediction.
    person_rows=[]
    for metric in ('Q','D10','annotation_turn5'):
        target=a[metric]-(a.groupby('image_key')[metric].transform('sum')-a[metric])/(a.groupby('image_key')[metric].transform('count')-1)
        tmap=pd.Series(target.to_numpy(),index=a.object_id)
        filename='turn5' if metric=='annotation_turn5' else metric
        matches=list((STUDY/'results/personal').glob('OOF_*.csv.gz'))
        filename=next(x for x in matches if (x.name==f'OOF_{metric}.csv.gz' or metric=='annotation_turn5' and x.name not in ('OOF_Q.csv.gz','OOF_D10.csv.gz')))
        pp=pd.read_csv(filename)
        equal(pp.actual_relative, pp.object_id.map(tmap),'personal target '+metric)
        equal(pp.absolute_error,abs(pp.predicted_relative-pp.actual_relative),'personal errors')
        for method,g in pp[pp.image_key.isin(repeated)].groupby('method'):
            im=g.groupby('image_key').agg(mae=('absolute_error','mean'),mse=('squared_error','mean'))
            person_rows.append(dict(outcome=metric,method=method,images=len(im),mae=im.mae.mean(),rmse=np.sqrt(im.mse.mean())))
        if metric in ('Q','D10'):
            work=a.assign(relative=target)
            for held in sorted(work.building.unique()):
                train=work[work.building!=held]; test=work[work.building==held]
                pred=test.worker_id.map(train.groupby('worker_id').relative.mean()).fillna(0)
                pred=pred-pred.groupby(test.image_key).transform('mean')
                stored=pp[pp.method.eq('person_history')].set_index('object_id').loc[test.object_id]
                equal(pred,stored.predicted_relative,'independent person history')
    person_rows=pd.DataFrame(person_rows);person_rows.to_csv(OUT/'PERSON_PREDICTION_RECOMPUTED.csv',index=False)
    for row in read('results/personal/main161/METHOD_SUMMARY.csv').itertuples():
        h=person_rows[(person_rows.outcome==row.outcome)&(person_rows.method==row.method)].iloc[0]
        equal([h.mae,h.rmse],[row.image_equal_mae,row.image_equal_rmse],'person summary')
    save_json('CORE_CHECK.json',dict(files_read=len(files),source_rows=len(all_a),manual_rows=len(a),
        manual_images=len(d),image_predictions=len(p),image_gain=gain_rows,
        scope='Input, structural source fields, all image/personal OOF truth and errors; independent all-building general histories.'))
    print('CORE COMPLETE',flush=True)


def models():
    a,d,repeated=load_primary()
    for metric in ('Q','D10'):
        a['r_'+metric]=a[metric]-(a.groupby('image_key')[metric].transform('sum')-a[metric])/(a.groupby('image_key')[metric].transform('count')-1)
    saved=read('results/personal_protected_purpose/PROTECTED_PURPOSE_OOF.csv.gz')
    lambdas=[np.inf,64.,16.,4.,1.,0.]

    def estimate(train,test,metric,lam):
        means=train.groupby('worker_id')['r_'+metric].mean()
        types=train.groupby(['worker_id','room_type_model'])['r_'+metric].mean()
        counts=train.groupby(['worker_id','room_type_model']).building.nunique()
        baseline=test.worker_id.map(means).fillna(0).to_numpy()
        tuples=list(zip(test.worker_id,test.room_type_model))
        own=np.array([types.get(k,np.nan) for k in tuples])
        n=np.array([counts.get(k,0) for k in tuples])
        shrink=np.zeros(len(n)) if np.isinf(lam) else np.divide(n,n+lam,out=np.zeros(len(n)),where=(n+lam)>0)
        value=pd.Series(baseline+np.nan_to_num(own-baseline)*shrink,index=test.index)
        return value-value.groupby(test.image_key).transform('mean')

    folds=[]
    frozen_cv=read('results/personal_protected_purpose/INNER_CV.csv.gz')
    for held in sorted(a.building.unique()):
        train=a[a.building!=held];test=a[a.building==held];scores=np.zeros(len(lambdas));nimages=0
        # Replay saved fold membership: equal-size group ties differ across NumPy versions.
        split_rows=frozen_cv[frozen_cv.held_out_building.eq(held)].drop_duplicates('inner_fold')
        validation_seen=[]
        for split in split_rows.itertuples():
            tb=set(split.train_buildings.split('|'));vb=set(split.validation_buildings.split('|'))
            assert not tb&vb and held not in tb|vb and tb|vb==set(train.building)
            validation_seen.extend(vb)
            tr,va=train[train.building.isin(tb)],train[train.building.isin(vb)]
            nimages+=va.image_key.nunique()
            for j,lam in enumerate(lambdas):
                err=(estimate(tr,va,'Q',lam)-va.r_Q)**2
                scores[j]+=err.groupby(va.image_key).mean().sum()
        assert len(validation_seen)==len(set(validation_seen))==train.building.nunique()
        best=int(np.argmin(scores)); lam=lambdas[best]
        expected=read('results/personal_protected_purpose/OUTER_FOLD_LAMBDA.csv').set_index('held_out_building').loc[held]
        assert np.isinf(lam)==np.isinf(expected['lambda'])
        equal([lam] if np.isfinite(lam) else [0],[expected['lambda']] if np.isfinite(expected['lambda']) else [0],'chosen lambda')
        equal([scores[best]/nimages],[expected.inner_image_mse],'inner mse '+held)
        for metric in ('Q','D10'):
            pred=estimate(train,test,metric,lam)
            old=saved[(saved.building==held)&(saved.outcome==metric)].set_index('object_id').loc[test.object_id]
            err=equal(pred,old.purpose_prediction,'protected prediction')
            folds.append(dict(building=held,metric=metric,lambda_value=str(lam),max_error=err))
    pd.DataFrame(folds).to_csv(OUT/'PROTECTED_PERSON_REFIT.csv',index=False)
    print('PROTECTED ALL 22 FOLDS COMPLETE',flush=True)
    # Refit every selected image model; verify full candidate selection on two buildings.
    d['purpose']=d.room_type_model.fillna('__MISSING__')
    d['log_H']=np.log1p(d.ref_H); d['short_fraction']=d.ref_short_edges/d.ref_turn5
    d['log_min_angle']=np.log(np.maximum(d.ref_min_horizontal_deg,1e-5));d['log_radius']=np.log(np.maximum(d.ref_radius_p90_h,1e-5))
    nums=['ref_turn5','log_H','short_fraction','log_min_angle','log_radius']
    def pipeline(method,family,alpha):
        cats=['difficulty']+(['purpose'] if method=='geometry_purpose_rich' else [])
        steps=[('impute',SimpleImputer(strategy='median',add_indicator=True)),('scale',StandardScaler())]
        if family=='ridge_quadratic':steps.append(('poly',PolynomialFeatures(2,include_bias=False)))
        pre=ColumnTransformer([('cats',OneHotEncoder(handle_unknown='ignore',sparse_output=False),cats),('nums',Pipeline(steps),nums)])
        estimator=Ridge(alpha=alpha) if family.startswith('ridge') else HistGradientBoostingRegressor(max_iter=120,max_leaf_nodes=7,min_samples_leaf=15,learning_rate=.05,l2_regularization=10.,random_state=2026102703)
        return Pipeline([('pre',pre),('est',estimator)])
    models=read('results/image/LOBO_MODELS.csv'); pred=read('results/image/LOBO_IMAGE_PREDICTIONS.csv.gz'); fits=[];inner=[]
    for row in models[models.method.isin(['geometry_rich','geometry_purpose_rich'])].itertuples():
        train=d[d.building!=row.held_out_building];test=d[d.building==row.held_out_building]
        assert set(row.train_buildings.split('|'))==set(train.building)
        fit=pipeline(row.method,row.family,row.alpha).fit(train,train['mean_'+row.metric])
        yhat=np.clip(fit.predict(test),0,100)
        old=pred[(pred.method==row.method)&(pred.metric==row.metric)&(pred.building==row.held_out_building)].set_index('image_key').loc[test.image_key]
        err=equal(yhat,old.predicted,'selected image model',tol=1e-7)
        fits.append(dict(metric=row.metric,method=row.method,building=row.held_out_building,rows=len(test),max_error=err))
        if row.held_out_building in ['jtcxE69GiFV','uNb9QFRL6hY']:
            candidates=[('ridge',x) for x in [.1,1.,10.,100.]]+[('ridge_quadratic',x) for x in [10.,100.]]+[('hgb',0.)]
            scores=[]
            for family,alpha in candidates:
                losses=[]
                for ti,vi in GroupKFold(5).split(train,groups=train.building):
                    tr,va=train.iloc[ti],train.iloc[vi]
                    model=pipeline(row.method,family,alpha).fit(tr,tr['mean_'+row.metric])
                    losses.append(abs(np.clip(model.predict(va),0,100)-va['mean_'+row.metric]).mean())
                scores.append(np.mean(losses))
            chosen=candidates[int(np.argmin(scores))]
            inner.append(dict(metric=row.metric,method=row.method,building=row.held_out_building,
                selected=str(chosen),saved_selected=str((row.family,row.alpha)),
                same_selection=chosen==(row.family,row.alpha),inner_mae=min(scores),
                saved_inner_mae=row.inner_mae,
                note='Local runtime CV group-size ties may use different folds; selected final model refit checked separately.'))
    pd.DataFrame(fits).to_csv(OUT/'IMAGE_SELECTED_MODEL_REFIT.csv',index=False)
    pd.DataFrame(inner).to_csv(OUT/'IMAGE_INNER_SELECTION_REFIT.csv',index=False)
    import sklearn
    save_json('MODEL_CHECK.json',dict(protected_outer_folds=22,image_selected_models=len(fits),
        image_local_runtime_inner_checks=len(inner),image_local_runtime_same_selection=sum(x['same_selection'] for x in inner),
        max_selected_prediction_error=max(x['max_error'] for x in fits),numpy_version=np.__version__,sklearn_version=sklearn.__version__,
        note='Protected-person inner folds replay exact saved membership; image selected models refit completely; image inner losses are local-runtime checks, not byte-equivalent folds.'))
    print('MODEL COMPLETE',flush=True)


def matching():
    a,d,_=load_primary();meta=d.set_index('image_key')
    cells={k:g.set_index('worker_id') for k,g in a.groupby('image_key')}
    tr=read('results/image/MATCHED_THREE_IMAGE_EVENTS.csv.gz')
    assert len(tr)==44694 and not tr.duplicated(['regime','target_key','source_same_key','source_different_key']).any()
    errors=[]
    for row in tr.itertuples():
        t,s,c=[meta.loc[k] for k in (row.target_key,row.source_same_key,row.source_different_key)]
        assert t.building!=s.building and s.building==c.building
        assert t.room_type_model==s.room_type_model and s.room_type_model!=c.room_type_model
        people=sorted(set(cells[row.target_key].index)&set(cells[row.source_same_key].index)&set(cells[row.source_different_key].index))
        assert people==row.common_workers.split('|') and len(people)==row.n_common>=3
        if row.regime!='source_building':assert s.difficulty==c.difficulty
        if row.regime=='source_building_difficulty_geometry':
            for metric in ('Q','D10','annotation_turn5','turn_delta','bottom_bias_9','dir'):
                v,w,x=[cells[k].loc[people,metric].to_numpy(float) for k in (row.target_key,row.source_same_key,row.source_different_key)]
                for name,z in [('same',w),('different',x)]:
                    ok=np.isfinite(v)&np.isfinite(z);vv,zz=v[ok],z[ok];n=len(vv)
                    if n<3:continue
                    for suffix,val in [('mean_absdiff',abs(vv.mean()-zz.mean())),('relative_absdiff',np.mean(abs((vv-vv.mean())-(zz-zz.mean())))*n/(n-1))]:
                        key=f'{metric}_common_{suffix}_{name}'
                        errors.append(equal([val],[getattr(row,key)],key))
                    if metric in ('Q','D10') and vv.std()>1e-12 and zz.std()>1e-12:
                        errors.append(equal([np.corrcoef(rankdata(vv),rankdata(zz))[0,1]],[getattr(row,f'{metric}_common_spearman_{name}')],'rank corr'))
    # Verify closest geometry among all legal same-building, same-difficulty controls.
    keep=d[d.room_type_status.eq('recorded_purpose')].copy()
    geo=keep[['ref_turn5','ref_H','ref_short_edges','ref_min_horizontal_deg','ref_radius_p90_h']].to_numpy(float)
    geo[:,1:3]=np.log1p(geo[:,1:3]);geo[:,3:5]=np.log(np.maximum(geo[:,3:5],1e-5))
    sd=np.nanstd(geo,axis=0);sd[sd<1e-12]=1;geo=(geo-np.nanmean(geo,axis=0))/sd
    lookup={k:g for k,g in zip(keep.image_key,geo)}
    broad=tr[tr.regime.eq('source_building_difficulty')]
    expected={}
    for (tk,sk),g in broad.groupby(['target_key','source_same_key']):
        expected[(tk,sk)]=min((np.linalg.norm(lookup[sk]-lookup[ck]),ck) for ck in g.source_different_key)[1]
    strict=tr[tr.regime.eq('source_building_difficulty_geometry')]
    assert len(strict)==len(expected)==2832
    for row in strict.itertuples():assert row.source_different_key==expected[(row.target_key,row.source_same_key)]
    rows=[]
    same=strict[strict.target_difficulty==strict.source_same_difficulty]
    for metric in ('Q_common_mean_absdiff','D10_common_mean_absdiff','Q_common_relative_absdiff','Q_common_spearman','annotation_turn5_common_mean_absdiff','turn_delta_common_mean_absdiff','bottom_bias_9_common_mean_absdiff','dir_common_mean_absdiff'):
        cols=[metric+s for s in ('_same','_different','_contrast')]
        sb=same.groupby(['target_key','target_building','purpose','source_building'])[cols].mean()
        img=sb.groupby(['target_key','target_building','purpose']).mean().reset_index()
        for purpose,g in [('ALL',img)]+list(img.groupby('purpose')):
            b=g.groupby('target_building')[cols[2]].mean()
            rows.append(dict(metric=metric,purpose=purpose,images=len(g),same=g[cols[0]].mean(),different=g[cols[1]].mean(),effect=g[cols[2]].mean(),images_closer=int((g[cols[2]]<-1e-10).sum()),buildings_closer=int((b<-1e-10).sum())))
    summary=pd.DataFrame(rows);summary.to_csv(OUT/'STRICT_MATCH_RECOMPUTED.csv',index=False)
    old=read('results/image/MATCHED_ALL_THREE_SAME_DIFFICULTY_SUMMARY.csv').set_index(['metric','purpose'])
    for row in summary.itertuples():
        prev=old.loc[(row.metric,row.purpose)]
        equal([row.same,row.different,row.effect,row.images_closer,row.buildings_closer],[prev.same,prev.different,prev.effect_image_equal,prev.negative_images,prev.negative_buildings],'strict summary')
    save_json('MATCHING_CHECK.json',dict(events=len(tr),strict_events=len(strict),same_difficulty_events=len(same),max_metric_error=max(errors),metric_scalar_checks=len(errors),strict_target_images=same.target_key.nunique()))
    print('MATCHING COMPLETE',flush=True)


def extras():
    gains=read('results/image/LOBO_INCREMENT_PER_IMAGE.csv')
    a,d,repeated=load_primary()
    saved=read('results/image/LOBO_INCREMENT_SUMMARY.csv').set_index(['metric','method','baseline','subset'])
    rng=np.random.default_rng(2026102705);largest=0.;count=0
    for (metric,m,b),g in gains.groupby(['metric','method','baseline']):
        slices=[('ALL',g),('RECORDED_PURPOSE',g[~g.purpose.isin(['__MISSING__','无法判断','开放复合空间'])]),('REPEATED_RECORDED_PURPOSE',g[g.image_key.isin(repeated)])]+list(g.groupby('purpose'))
        for subset,sub in slices:
            groups=sub.groupby('building').gain_mae.agg(['sum','count'])
            ix=rng.integers(0,len(groups),size=(2000,len(groups)))
            values=groups['sum'].to_numpy()[ix].sum(1)/groups['count'].to_numpy()[ix].sum(1)
            lo,hi=np.quantile(values,[.025,.975]);old=saved.loc[(metric,m,b,subset)]
            largest=max(largest,equal([lo,hi],[old.building_boot_p025,old.building_boot_p975],'building bootstrap'));count+=1
    standard=read('results/image/DIFFICULTY_STANDARDIZED_PURPOSE.csv')
    major=d[d.room_type_model.isin(standard.purpose.unique())]
    weights=major.difficulty.value_counts(normalize=True)
    for row in standard.itertuples():
        g=major[major.room_type_model.eq(row.purpose)]
        means=g.groupby('difficulty')[row.metric].mean().reindex(weights.index)
        value=(means*weights).sum() if means.notna().all() else np.nan
        equal([g[row.metric].mean(),value],[row.raw_mean,row.standardized_mean],'difficulty standardization')
    leftovers=[]
    for f in (STUDY/'results/personal').glob('*.writing.*'):
        try:
            with gzip.open(f,'rt',encoding='utf-8') as stream:n=sum(1 for _ in csv.reader(stream))-1
            status='readable'
        except (EOFError,OSError) as e:n=None;status=type(e).__name__
        leftovers.append({'path':f.relative_to(STUDY).as_posix(),'rows':n,'status':status,'adopted':False})
    cases=read('cases_history/CASE_IMAGE_SUMMARY.csv');case_results=[]
    for row in cases.itertuples():
        g=a[a.image==row.image_code]
        equal([len(g),g.Q.mean(),g.D10.mean(),g.actual_simplification.sum()],[row.n,row.Q_mean,row.D10_mean,row.reduced_n],'case values')
        case_results.append({'image':row.image_code,'records':len(g),'mean_Q':g.Q.mean(),'simplified':int(g.actual_simplification.sum())})
    save_json('EXTRA_CHECK.json',{'bootstrap_cells':count,'bootstrap_max_error':largest,'standardization_cells':len(standard),'temporary_author_exports':leftovers,'cases':case_results})
    print('EXTRAS COMPLETE',flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('part',choices=['core','models','matching','extras']);args=p.parse_args()
    OUT.mkdir(exist_ok=True)
    {'core':core,'models':models,'matching':matching,'extras':extras}[args.part]()
