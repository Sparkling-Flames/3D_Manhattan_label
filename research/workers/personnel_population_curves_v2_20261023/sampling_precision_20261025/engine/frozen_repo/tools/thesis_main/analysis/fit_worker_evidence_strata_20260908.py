"""Fixed-rule exploratory worker strata; no eligibility changes or sample-size replay."""
from __future__ import annotations
import os
os.environ.setdefault('OPENBLAS_NUM_THREADS','1')
os.environ.setdefault('OMP_NUM_THREADS','1')
import argparse
import csv
import gzip
import hashlib
import json
from pathlib import Path
import numpy as np
import pandas as pd
from tools.thesis_main.analysis.audit_annotation_reanalysis_claims_20260905 import fit_effects
from tools.thesis_main.analysis.materialize_annotation_research_prework_statistics_20260905 import worker_task_components

ROOT=Path(__file__).resolve().parents[3]
OUT=ROOT/'analysis_results/worker_evidence_strata_20260908_v1'
SEED=20260908
KEY=['stage','raw_condition','metric','reading','representation','cohort']


def seed_for(key):
    return (SEED+int.from_bytes(hashlib.blake2s(str(key).encode(),digest_size=4).digest(),'little'))%2**32


def sufficient(data):
    """Existing task-intercept elimination, accumulated separately by building."""
    d=data.copy();d['worker_id']=d.worker_id.astype(str);d['building_id']=d.building_id.astype(str)
    if d.duplicated(['context_key','worker_id']).any():raise ValueError('duplicate_worker_context')
    if not np.isfinite(d.value).all():raise ValueError('finite_values_required')
    if (d.groupby('context_key').building_id.nunique()!=1).any():raise ValueError('context_building_conflict')
    workers=sorted(d.worker_id.unique());buildings=sorted(d.building_id.unique())
    wi={w:i for i,w in enumerate(workers)};bi={b:i for i,b in enumerate(buildings)}
    a=np.zeros((len(buildings),len(workers),len(workers)));rhs=np.zeros((len(buildings),len(workers)))
    support=np.zeros_like(rhs)
    for _,g in d.groupby('context_key',sort=False):
        b=bi[g.building_id.iloc[0]];idx=np.array([wi[w] for w in g.worker_id]);v=g.value.to_numpy(float)
        x=np.eye(len(workers))[idx];x-=x.mean(axis=0)
        a[b]+=x.T@x;rhs[b]+=x.T@(v-v.mean());support[b,idx]+=1
    return dict(workers=workers,buildings=buildings,A=a,rhs=rhs,support=support)


def solve(s,weights):
    w=len(s['workers']);presence=np.asarray(weights)@s['support']
    if (presence==0).any():return None,'missing_workers',None
    a=np.tensordot(weights,s['A'],axes=1);b=np.asarray(weights)@s['rhs']
    values,vectors=np.linalg.eigh(a);tol=max(float(values.max()),1.)*1e-10
    keep=values>tol;rank=int(keep.sum())
    if w<2 or rank!=w-1:return None,'disconnected_graph',rank
    beta=vectors[:,keep]@((vectors[:,keep].T@b)/values[keep]);beta-=beta.mean()
    beta[abs(beta)<1e-12]=0. # Numerical zero, not a substantive classification threshold.
    return beta,'usable',rank


def fit_one(data,seed,replicates=500):
    s=sufficient(data);b=len(s['buildings']);full,status,_=solve(s,np.ones(b))
    if status=='usable':
        old=fit_effects(data.assign(base_task_id=data.context_key),'value').reindex(s['workers'])
        assert np.allclose(full,old,atol=1e-8,rtol=1e-8)
    weights=np.random.default_rng(seed).multinomial(b,np.full(b,1/b),size=replicates)
    draws=[];diagnostics=[]
    for i,counts in enumerate(weights):
        beta,why,rank=solve(s,counts)
        if beta is not None:draws.append(beta)
        diagnostics.append(dict(replicate=i,status=why,rank=rank,
            missing_workers=int(((counts@s['support'])==0).sum()),building_counts_json=json.dumps(counts.tolist())))
    lo,hi=np.quantile(draws,[.025,.975],axis=0) if draws else (np.full(len(s['workers']),np.nan),)*2
    profiles=[]
    for j,worker in enumerate(s['workers']):
        d=data[data.worker_id.astype(str)==worker];support=d.building_id.nunique()
        label=('insufficient' if support<3 or len(draws)<.8*replicates or status!='usable' else
               'high' if lo[j]>0 else 'low' if hi[j]<0 else 'uncertain')
        profiles.append(dict(worker_id=worker,effect=full[j] if full is not None else np.nan,
            lower=lo[j],upper=hi[j],label=label,informative_rows=len(d),informative_contexts=d.context_key.nunique(),
            informative_buildings=support,bootstrap_valid=len(draws),bootstrap_requested=replicates,
            bootstrap_valid_fraction=len(draws)/replicates,fit_status=status,
            reference_workers=json.dumps(s['workers']),training_buildings=json.dumps(s['buildings']),seed=seed))
    p=pd.DataFrame(profiles);p['layer_value']=0.;p['component']='single'
    for label in ['high','low']:
        mask=p.label==label
        if mask.any():p.loc[mask,'layer_value']=p.loc[mask,'effect'].mean()
    return p,pd.DataFrame(diagnostics)


def predict_peers(test,profiles):
    """All models and outcomes share exactly the same held-out peer set."""
    p=profiles[profiles.fit_status=='usable']
    d=test.copy();d['worker_id']=d.worker_id.astype(str)
    d=d.merge(p[['worker_id','effect','layer_value','component','label']],on='worker_id',validate='many_to_one')
    group=['context_key','component']
    d=d[d.groupby(group).worker_id.transform('size')>=2].copy()
    d['target']=d.value-d.groupby(group).value.transform('mean')
    d['continuous_prediction']=d.effect-d.groupby(group).effect.transform('mean')
    d['layer_prediction']=d.layer_value-d.groupby(group).layer_value.transform('mean')
    d['baseline_sqerr']=d.target**2
    d['continuous_sqerr']=(d.target-d.continuous_prediction)**2
    d['layer_sqerr']=(d.target-d.layer_prediction)**2
    return d


def informative(d):
    d=d[np.isfinite(d.value)].copy()
    return d[d.groupby('context_key').worker_id.transform('nunique')>=2]


def fit_parts(data,key,fold,writer):
    d=informative(data);parts=[]
    components=worker_task_components(d.assign(base_task_id=d.context_key).to_dict('records'))
    for number,component in enumerate(components):
        sub=d[d.worker_id.isin(component['workers'])]
        fit_id='|'.join(map(str,[*key,fold,number]))
        # Common random numbers isolate measurement/provenance sensitivity from
        # Monte Carlo differences whenever the building and worker rosters match.
        seed_key=(key[0],key[1],fold,tuple(sorted(sub.building_id.unique())),tuple(sorted(sub.worker_id.unique())))
        p,diag=fit_one(sub,seed_for(seed_key))
        p['component']=str(number);p['fit_id']=fit_id;p['fold']=fold
        for k,v in zip(KEY,key):p[k]=v
        for r in diag.to_dict('records'):writer.writerow(dict(fit_id=fit_id,**r))
        parts.append(p)
    return pd.concat(parts,ignore_index=True) if parts else pd.DataFrame(columns=['worker_id','effect','layer_value','component','label','fit_status'])


def evaluate_tables(pred):
    summaries=[];buildings=[]
    for key,g in pred.groupby(['evaluation',*KEY],dropna=False):
        meta=dict(zip(['evaluation',*KEY],key));bm=g.groupby('building_id')[['baseline_sqerr','continuous_sqerr','layer_sqerr']].mean()
        for b,row in bm.iterrows():buildings.append(dict(**meta,building_id=b,rows=int((g.building_id==b).sum()),**row.to_dict()))
        r=dict(**meta,rows=len(g),workers=g.worker_id.nunique(),contexts=g.context_key.nunique(),buildings=len(bm))
        for model in ['continuous','layer']:
            r[model+'_record_r2']=1-g[model+'_sqerr'].mean()/g.baseline_sqerr.mean() if g.baseline_sqerr.mean()>1e-20 else np.nan
            r[model+'_building_r2']=1-bm[model+'_sqerr'].mean()/bm.baseline_sqerr.mean() if bm.baseline_sqerr.mean()>1e-20 else np.nan
            r[model+'_supported']=bool(r[model+'_record_r2']>0 and r[model+'_building_r2']>0)
        r['decision']='retain_strata' if r['layer_supported'] else 'continuous_only' if r['continuous_supported'] else 'not_supported'
        summaries.append(r)
    return pd.DataFrame(summaries),pd.DataFrame(buildings)


def analysis_cohorts(metrics,history):
    metrics=metrics[metrics.raw_condition.isin(['manual','semi'])].copy();metrics['cohort']='available'
    common=[]
    for metric,g in metrics[(metrics.stage=='C1')&(metrics.metric!='corner_pair_count')].groupby('metric'):
        n=g[['reading','representation']].drop_duplicates().shape[0]
        counts=g[np.isfinite(g.value)].groupby('canonical_annotation_id').size()
        z=g[g.canonical_annotation_id.isin(counts[counts==n].index)].copy();z['cohort']='common_geometry';common.append(z)
    # Fixed provenance sensitivity, not a new eligibility rule or outcome trimming.
    clean=history.loc[~history.has_revision & ~history.multiple_condition_observed,'canonical_annotation_id']
    z=metrics[(metrics.stage=='C1')&(metrics.raw_condition=='manual')&
              ~metrics.representation.isin(['legacy_integer','pixel_center_integer'])&metrics.canonical_annotation_id.isin(clean)].copy()
    z['cohort']='no_revision_or_crosscondition';common.append(z)
    return pd.concat([metrics,*common],ignore_index=True)


def run(out=OUT):
    out.mkdir(exist_ok=True,parents=True)
    metrics=pd.read_csv(out/'inputs/worker_metrics.csv.gz',dtype={'worker_id':str,'block_index':str})
    assert not metrics.duplicated(['canonical_annotation_id','metric','reading','representation']).any()
    data=analysis_cohorts(metrics,pd.read_csv(out/'inputs/response_history_flags.csv'))
    profiles=[];held=[];excluded=[];cache={};groups={}
    fields=['fit_id','replicate','status','rank','missing_workers','building_counts_json']
    with gzip.open(out/'bootstrap_diagnostics.csv.gz','wt',encoding='utf-8',newline='') as stream:
        writer=csv.DictWriter(stream,fieldnames=fields);writer.writeheader()
        for key,original in data.groupby(KEY,sort=True):
            d=informative(original);groups[key]=d
            p=fit_parts(d,key,'full',writer);cache[key,'full']=p;profiles.append(p)
            for b in sorted(d.building_id.unique()):
                train=d[d.building_id!=b];test=d[d.building_id==b]
                pp=fit_parts(train,key,b,writer);cache[key,b]=pp;profiles.append(pp)
                result=predict_peers(test,pp)
                for k,v in zip(KEY,key):result[k]=v
                result['heldout_building']=b;result['evaluation']='within_stage_lobo';held.append(result)
                for r in test[~test.canonical_annotation_id.isin(result.canonical_annotation_id)].to_dict('records'):
                    excluded.append(dict(**dict(zip(KEY,key)),evaluation='within_stage_lobo',heldout_building=b,canonical_annotation_id=r['canonical_annotation_id'],worker_id=r['worker_id'],reason='no_train_effect_or_no_two_same_component_peers'))
            print(json.dumps(dict(group=key,rows=len(d),full_high=int((p.label=='high').sum()),full_low=int((p.label=='low').sum())),ensure_ascii=True),flush=True)
        # Cross-stage/condition transfer of C1 Manual profiles, trained outside
        # each target building; no target outcomes inform classes or coefficients.
        for key,d in groups.items():
            stage,condition,metric,reading,rep,cohort=key
            if (stage,condition)==('C1','manual') or cohort!='available' or rep in ['legacy_integer','pixel_center_integer']:continue
            source=('C1','manual',metric,reading,rep,cohort)
            if source not in groups:continue
            for b in sorted(d.building_id.unique()):
                fold=b if b in set(groups[source].building_id) else 'full'
                pp=cache[source,fold];test=d[d.building_id==b];result=predict_peers(test,pp)
                for k,v in zip(KEY,key):result[k]=v
                result['heldout_building']=b;result['evaluation']='C1_manual_transfer';held.append(result)
                for r in test[~test.canonical_annotation_id.isin(result.canonical_annotation_id)].to_dict('records'):
                    excluded.append(dict(**dict(zip(KEY,key)),evaluation='C1_manual_transfer',heldout_building=b,canonical_annotation_id=r['canonical_annotation_id'],worker_id=r['worker_id'],reason='no_C1_train_effect_or_no_two_same_component_peers'))
    prof=pd.concat(profiles,ignore_index=True);pred=pd.concat(held,ignore_index=True)
    prof.to_csv(out/'worker_profiles_all_folds.csv.gz',index=False)
    pred.to_csv(out/'heldout_predictions.csv.gz',index=False)
    pd.DataFrame(excluded).to_csv(out/'heldout_exclusions.csv.gz',index=False)
    summary,building=evaluate_tables(pred)
    summary.to_csv(out/'validation_summary.csv',index=False);building.to_csv(out/'validation_by_building.csv',index=False)
    full=prof[prof.fold=='full'].copy()
    full=full.merge(summary[summary.evaluation=='within_stage_lobo'][KEY+['decision','continuous_record_r2','continuous_building_r2','layer_record_r2','layer_building_r2']],on=KEY,how='left',validate='many_to_one')
    full['decision']=full.decision.fillna('not_evaluable')
    full.to_csv(out/'worker_strata_results.csv',index=False)
    # Ensure all 26 remain visible even where an analysis has no identifiable score.
    index=pd.read_csv(out/'inputs/canonical_index.csv.gz',dtype={'worker_id':str})
    evidence=index.groupby('worker_id').agg(canonical_rows=('canonical_annotation_id','size'),images=('image_id','nunique'),buildings=('building_id','nunique'),current20_member=('current20_member','first')).reset_index()
    assert len(evidence)==26 and evidence.canonical_rows.sum()==2501
    main=full[(full.stage=='C1')&(full.raw_condition=='manual')&(full.cohort=='available')]
    for key,g in main.groupby(['metric','reading','representation']):
        name='__'.join(key)
        cols=['worker_id','effect','lower','upper','label','informative_buildings','bootstrap_valid_fraction','decision']
        evidence=evidence.merge(g[cols].rename(columns={c:name+'__'+c for c in cols if c!='worker_id'}),on='worker_id',how='left',validate='one_to_one')
    evidence.sort_values('worker_id',key=lambda s:s.astype(int)).to_csv(out/'worker_evidence_26.csv',index=False)
    rule=dict(seed=SEED,bootstrap_requested=500,bootstrap_unit='building_only',bootstrap_redraw=False,
        interval=[.025,.975],minimum_informative_buildings=3,minimum_valid_fraction=.8,
        zero_reference='equal_worker_mean_within_fixed_training_component',
        layer_prediction='training_stratum_equal_worker_mean; uncertain_or_insufficient_zero_abstention',
        support_rule='both_record_and_building_equal_heldout_MSE_improve_over_no_worker_baseline',
        primary_model_precision='native_uv',common_geometry_sensitivity='C1 only',new_population_classes=False,
        bootstrap_seed_reference='stage_condition_fold_sorted_buildings_sorted_workers_shared_across_metric_reading_precision_cohort',
        original_annotations_modified=False,new_person_count_simulation=False,profiles=len(prof),heldout_rows=len(pred))
    (out/'RULES_AND_QA.json').write_text(json.dumps(rule,ensure_ascii=False,indent=2),encoding='utf-8')
    print(summary[(summary.stage=='C1')&(summary.raw_condition=='manual')&(summary.cohort=='available')].to_string(index=False),flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--out',type=Path,default=OUT)
    run(parser.parse_args().out)
