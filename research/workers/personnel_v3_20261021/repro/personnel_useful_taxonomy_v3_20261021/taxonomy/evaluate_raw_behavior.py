#!/usr/bin/env python3
"""Evaluate frozen new classes against old classes and continuous histories.

This is raw-response evaluation, not fusion evaluation. Same outer-excluded
personnel maps are used on every train and test record. Model errors do not
mean equivalent work-hour savings.
"""
import os
for k in ['OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS']:os.environ[k]='1'
import json,itertools
from pathlib import Path
import numpy as np
import pandas as pd
import discover_behavior_classes as b
import discover_joint_qt as j

OUTCOMES=b.HIST+['B8L2_peer_delta','D10_peer_delta','log_time_peer_delta']
QT=['q_effect_old','q_downside_old','t_effect_old','t_tail_old']

def exact_fields(family,joint=False):
    """Use the exact feature columns that formed this fold's selected classes."""
    domains=j.DOMAIN if joint else b.DOMAINS
    families=j.FAMILIES if joint else b.FAMILIES
    fields=[v for domain in families[family] for v in domains[domain]]
    return [v+('_joint_train' if v in ['q_history','q_downside','t_history'] else '_train') for v in fields]

def weights(d):
    keys=['building_id','image_id','reference_id']
    z=d.groupby(keys,dropna=False).size().rename('people').reset_index()
    z['refs']=z.groupby(['building_id','image_id'],dropna=False).people.transform('size')
    ni=z[['building_id','image_id']].drop_duplicates().groupby('building_id').size()
    z['images']=z.building_id.map(ni)
    s=pd.Series((1/(z.people*z.refs*z.images*len(ni))).to_numpy(),index=pd.MultiIndex.from_frame(z[keys]))
    return s.reindex(pd.MultiIndex.from_frame(d[keys])).to_numpy()

def design(train,test,numeric,categorical):
    a=[np.ones(len(train)),train.origin.eq('new').to_numpy(float)]
    z=[np.ones(len(test)),test.origin.eq('new').to_numpy(float)]
    for name in numeric:
        av=train[name].to_numpy(float);bv=test[name].to_numpy(float)
        mean=av.mean();sd=av.std();sd=sd if sd>1e-8 else 1.
        a.append((av-mean)/sd);z.append((bv-mean)/sd)
    for name in categorical:
        for level in sorted(train[name].unique())[1:]:
            a.append(train[name].eq(level).to_numpy(float));z.append(test[name].eq(level).to_numpy(float))
    return np.column_stack(a),np.column_stack(z)

def fit_predict(train,test,numeric,categorical,outcome):
    a,z=design(train,test,numeric,categorical);w=weights(train)
    p=np.eye(a.shape[1])*.01;p[0,0]=0
    beta=np.linalg.solve((a*w[:,None]).T@a+p,(a*w[:,None]).T@train[outcome].to_numpy(float))
    return z@beta

def mean_image(d,col):return d.groupby(['image_id','reference_id'],dropna=False)[col].mean().groupby('image_id').mean().mean()

def summaries(per):
    out=[]
    keys=['condition','support','outcome','model']
    for vals,g in per.groupby(keys,dropna=False):
        r=dict(zip(keys,vals));r.update(buildings=len(g),images=int(g.test_images.sum()),records=int(g.test_records.sum()),
            mse=g.mse.mean(),mae=g.mae.mean())
        out.append(r)
    out=pd.DataFrame(out)
    base=out[out.model.eq('source')][['condition','support','outcome','mse']].rename(columns={'mse':'source_mse'})
    out=out.merge(base,on=['condition','support','outcome']);out['r2_vs_source']=1-out.mse/out.source_mse
    return out

def main():
    assert (b.HERE/'LABEL_FREEZE.json').exists(),'labels must be frozen before evaluation'
    x=b.load();x=x[x.behavior_usable & x.layer.eq('ordinary')].copy()
    # Individual expression fields in x are responses. Personnel history
    # covariates are renamed to avoid accidental use of target observations.
    f=pd.read_csv(b.HERE/'CONTINUOUS_FEATURES_LOBO.csv.gz')
    f=f.rename(columns={v:v+'_train' for v in b.HIST+b.CONTEXT})
    labels=pd.read_csv(b.HERE/'ALL_METHOD_LABELS_LOBO.csv.gz')
    oldm=pd.read_csv(b.REPO/'research/workers/personnel_taxonomy_20261021/route_b/lobo_labels.csv')
    olds=pd.read_csv(b.REPO/'research/workers/personnel_taxonomy_20261021/route_b/semi_adopted_lobo_labels.csv')
    if 'coarse_class' not in olds:
        print('semi columns',olds.columns.tolist());raise RuntimeError('old Semi schema')
    qt=pd.read_csv(b.REPO/'research/workers/personnel_global_composition_20261021/multivariate/continuous_features_lobo.csv.gz')
    qt=qt.rename(columns={n:n+'_old' for n in ['q_effect','q_downside','t_effect','t_tail']})
    rows=[];supportrows=[];exactrows=[]
    structural=[v+'_train' for v in b.HIST]
    all_structural=[v+'_train' for v in b.HIST+b.CONTEXT]
    for cond in ['manual','semi']:
        old=oldm[oldm.condition.eq(cond)] if cond=='manual' else olds[olds.condition.eq(cond)]
        for building in sorted(x[x.condition.eq(cond)].building_id.unique()):
            fs=f[f.condition.eq(cond)&f.heldout_building.eq(building)]
            z=x[x.condition.eq(cond)].merge(fs[['worker_id']+all_structural],on='worker_id',validate='many_to_one')
            ol=old[old.heldout_building.eq(building)][['worker_id','coarse_class','fine_class']].rename(columns={'coarse_class':'old_coarse','fine_class':'old_fine'})
            z=z.merge(ol,on='worker_id',validate='many_to_one')
            for method,prefix in [('V3_BEHAVIOR','new'),('V3_JOINT_QT','joint')]:
                ll=labels[(labels.condition==cond)&(labels.heldout_building==building)&(labels.method==method)]
                extra=['q_history','q_downside','t_history'] if prefix=='joint' else []
                ll=ll[['worker_id','coarse_label','fine_label','known','selected_family']+extra].rename(columns={
                    'coarse_label':prefix+'_coarse','fine_label':prefix+'_fine','known':prefix+'_known',
                    'selected_family':prefix+'_family',**{q:q+'_joint_train' for q in extra}})
                z=z.merge(ll,on='worker_id',validate='many_to_one')
            geom_family=z.new_family.iloc[0];joint_family=z.joint_family.iloc[0]
            geom_exact=exact_fields(geom_family);joint_exact=exact_fields(joint_family,joint=True)
            for method,fam,fields in [('V3_BEHAVIOR',geom_family,geom_exact),('V3_JOINT_QT',joint_family,joint_exact)]:
                exactrows.append(dict(condition=cond,heldout_building=building,method=method,selected_family=fam,
                    numeric_fields='|'.join(fields),coarse_fine_same_input=True))
            ff=qt[(qt.condition==cond)&(qt.heldout_building==building)]
            z=z.merge(ff[['worker_id']+QT],on='worker_id',validate='many_to_one')
            core=z[z.new_known & ~z.old_coarse.isin(['unassigned','unknown'])].dropna(subset=structural)
            for support,zz in [('geometry_common',core),('joint_QT_common',core[core.joint_known].dropna(subset=QT))]:
                models={'source':([],[]),'old_coarse':([],['old_coarse']),'old_fine':([],['old_fine']),
                    'new_coarse':([],['new_coarse']),'new_fine':([],['new_fine']),
                    'continuous_structure':(structural,[]),
                    'continuous_geometry_exact':(geom_exact,[]),'geometry_exact_plus_new_fine':(geom_exact,['new_fine'])}
                if support=='joint_QT_common':
                    models.update({'joint_coarse':([],['joint_coarse']),'joint_fine':([],['joint_fine']),
                        'continuous_QT':(QT,[]),'continuous_QT_structure':(QT+structural,[]),
                        'QT_plus_joint_fine':(QT,['joint_fine']),'QT_structure_plus_joint_fine':(QT+structural,['joint_fine']),
                        'continuous_joint_exact':(joint_exact,[]),'joint_exact_plus_joint_fine':(joint_exact,['joint_fine'])})
                for outcome in OUTCOMES:
                    v=zz[zz[outcome].notna()].copy();tr=v[v.building_id.ne(building)];te=v[v.building_id.eq(building)]
                    if len(tr)<60 or len(te)<6:continue
                    for model,(numeric,cats) in models.items():
                        assert tr[numeric].notna().all().all() and te[numeric].notna().all().all(),(cond,building,support,model)
                        pred=fit_predict(tr,te,numeric,cats,outcome)
                        ee=te[['image_id','reference_id']].copy();ee['sq']=(pred-te[outcome].to_numpy())**2;ee['abs']=abs(pred-te[outcome].to_numpy())
                        rows.append(dict(condition=cond,heldout_building=building,support=support,outcome=outcome,model=model,
                            train_records=len(tr),test_records=len(te),test_images=te.image_id.nunique(),test_workers=te.worker_id.nunique(),
                            mse=mean_image(ee,'sq'),mae=mean_image(ee,'abs')))
                supportrows.append(dict(condition=cond,heldout_building=building,support=support,workers=zz.worker_id.nunique(),
                    target_records=int(zz.building_id.eq(building).sum()),target_images=zz.loc[zz.building_id.eq(building),'image_id'].nunique()))
        # Save each complete condition before the next.
        b.save(pd.DataFrame(rows), 'RAW_PREDICTION_BUILDINGS.csv')
        b.save(pd.DataFrame(supportrows),'RAW_PREDICTION_SUPPORT.csv')
        b.save(pd.DataFrame(exactrows),'RAW_PREDICTION_EXACT_FEATURES.csv')
    per=pd.DataFrame(rows);out=summaries(per);b.save(out,'RAW_PREDICTION_SUMMARY.csv')
    comparisons=[]
    compare=[('new_coarse','new_fine'),('old_fine','new_fine'),('new_fine','continuous_structure'),
        ('joint_coarse','joint_fine'),('continuous_QT','joint_fine'),('continuous_QT','continuous_QT_structure'),
        ('continuous_QT_structure','QT_structure_plus_joint_fine'),
        ('new_fine','continuous_geometry_exact'),('continuous_geometry_exact','geometry_exact_plus_new_fine'),
        ('joint_fine','continuous_joint_exact'),('continuous_joint_exact','joint_exact_plus_joint_fine')]
    for (cond,support,outcome),g in per.groupby(['condition','support','outcome']):
        for aa,bb in compare:
            left=g[g.model.eq(aa)].set_index('heldout_building').mse
            right=g[g.model.eq(bb)].set_index('heldout_building').mse
            z=pd.concat([left.rename('a'),right.rename('b')],axis=1).dropna()
            if not len(z):continue
            delta=z.a-z.b;rng=np.random.default_rng(2026102131)
            boot=np.mean(rng.choice(delta.to_numpy(),size=(2000,len(delta)),replace=True),axis=1)
            comparisons.append(dict(condition=cond,support=support,outcome=outcome,baseline=aa,alternative=bb,
                buildings=len(z),mse_baseline=z.a.mean(),mse_alternative=z.b.mean(),mse_reduction=delta.mean(),
                relative_mse_reduction=1-z.b.mean()/z.a.mean(),ci_lo=np.quantile(boot,.025),ci_hi=np.quantile(boot,.975),
                positive_buildings=int(delta.gt(0).sum()),negative_buildings=int(delta.lt(0).sum())))
    b.save(pd.DataFrame(comparisons),'RAW_PREDICTION_INCREMENT.csv')
    b.js('RAW_EVALUATION_CONTRACT.json',dict(stage='frozen-class outer-building evaluation',outcomes=OUTCOMES,
        model='fixed ridge .01, source indicator in every model, same map excluding target building for all train/test records',
        weights='reference then image then building equal',support='all model comparisons within a support use exactly the same records for each outcome',
        interpretation='relative raw-expression/quality/log-source-time prediction; no percentage-hour-saving claim',
        scope='ordinary non-OOS behavior with original quality gates; doorway and special-conditional remain separate',
        exact_continuous_control='each outer fold uses the same numerical input columns as its selected geometry or joint family; existing structure5 and historical QT4 benchmarks are retained',
        repeated_data=True,external_blind_test=False))
    print(out[['condition','support','outcome','model','r2_vs_source']].round(4).to_string(index=False))

if __name__=='__main__':main()
