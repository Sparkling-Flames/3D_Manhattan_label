#!/usr/bin/env python3
"""Held-building prediction of centered composition responses on exact top layers.

Only method-independent complete N-1/N-2 member-set layers are admitted.
Every outer building uses ONE outside-building personnel map on both its
training pools and held pools. Unlabelled/feature-missing personnel are fixed
background members, not a class; deletions are confined to supported personnel.

This predicts deviations from a finite pool/n mean, not absolute quality on an
unseen image, and tests a pooled linear direction rather than all local nonlinear
composition mechanisms. No fusion, scoring, qualification or labels are changed.
"""
from __future__ import annotations
import os
for _k in ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS'):os.environ[_k]='1'
import argparse
import gc
import gzip
import hashlib
import io
import itertools
import json
import math
import time
from pathlib import Path
import numpy as np
import pandas as pd

HERE=Path(__file__).resolve().parent
STUDY=HERE.parent
COMP=STUDY/'composition'
MV=STUDY/'multivariate'
ROOT=STUDY.parents[2]
SNAPSHOT=ROOT/'research/workers/pro_personnel_v2_archive_20261019/work_v2_20261019/fusion/INPUT_SNAPSHOT.json.gz'
QT=['q_effect','q_downside','t_effect','t_tail']
METRICS=['B8L2','D10','nodes','failure','iou_2d','S_bottom_deg','dir','Hmean','Hcenter',
         'IoU3D100','height_mean_ratio','height_mean_h','ref_node_recall_9','ref_edge_recall_9','log_source_time_total']
MODERN_MANUAL=['M_structure','A2_relation','MV_QTD_manual','MV_QTD_manual_new','MV_TDScopeSemi_manual_new']
MODERN_SEMI=['SP_scale','A2_relation','MV_QTScopeSemi_semi_new']
LEGACY=['Rnew2','F01']
PENALTY=.01
SEED=2026102157

def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def digest(x):return hashlib.sha256(json.dumps(x,sort_keys=True,separators=(',',':')).encode()).hexdigest()
def clean(x):
    if isinstance(x,dict):return {str(k):clean(v) for k,v in x.items()}
    if isinstance(x,(tuple,list,np.ndarray)):return [clean(v) for v in x]
    if isinstance(x,np.generic):return clean(x.item())
    if isinstance(x,float) and not math.isfinite(x):return None
    return x
def js(p,x):Path(p).write_text(json.dumps(clean(x),ensure_ascii=False,indent=2,allow_nan=False)+'\n')
def save(df,name,out):
    path=out/name;temp=path.with_name(path.name+'.tmp')
    df.to_csv(temp,index=False,encoding='utf-8-sig',compression={'method':'gzip','mtime':0} if name.endswith('.gz') else None)
    temp.replace(path)

def load(deletions,scalar_path):
    scalar_path=scalar_path.resolve()
    raw=scalar_path.read_bytes();scalar_sha=hashlib.sha256(raw).hexdigest()
    needed=set(METRICS)|{'team_key','pool_id','pool_n','k','member_workers','building','condition','layer',
        'image_id','image','reference_id','reference_version','difficulty','complete_evaluable',
        'time_source_kinds','source_time_known_n','source_time_total_seconds'}
    d=pd.read_csv(io.BytesIO(raw),compression='gzip',low_memory=False,usecols=lambda c:c in needed);scalar_rows=len(d);del raw
    assert not d.team_key.duplicated().any()
    layers=pd.read_csv(COMP/'EXACT_LAYERS.csv')
    layers['deletions']=layers.N-layers.n
    layers=layers[layers.deletions.isin(deletions)].copy()
    pools=json.load(gzip.open(SNAPSHOT,'rt'))['images']
    workers={p['pool_id']:frozenset(r['worker_id'] for r in p['records']) for p in pools}
    source={p['pool_id']:{r['worker_id']:r['origin'] for r in p['records']} for p in pools}
    labels=pd.read_csv(COMP/'FROZEN_LABELS.csv',keep_default_na=False)
    feats=pd.read_csv(MV/'continuous_features_lobo.csv.gz')
    d['failure']=(~d.complete_evaluable.astype(bool)).astype(float)
    if 'log_source_time_total' not in d:
        single_source=~d.time_source_kinds.fillna('').str.contains('|',regex=False)&d.time_source_kinds.fillna('').ne('')
        time_ok=single_source&d.source_time_known_n.eq(d.k)&d.source_time_total_seconds.gt(0)
        d['log_source_time_total']=np.log(d.source_time_total_seconds.where(time_ok))
    for m in METRICS:
        if m not in d:d[m]=np.nan
    d['deletions']=d.pool_n-d.k
    d=d[d.deletions.isin(deletions)].copy()
    data={};receipt=[]
    for r in layers.itertuples():
        g=d[d.pool_id.eq(r.pool_id)&d.k.eq(r.n)].copy()
        N=len(workers[r.pool_id]);expected=math.comb(N,int(r.deletions))
        assert expected==int(r.all_member_sets)==int(r.registered_member_sets)
        assert N==int(r.N)
        complete=len(g)==expected
        record={'pool_id':r.pool_id,'condition':r.condition,'layer':r.layer,'building':r.building,'image_id':r.image_id,
                'N':N,'n':int(r.n),'deletions':int(r.deletions),'required_sets':expected,'materialized_sets':len(g),'complete_layer':complete}
        receipt.append(record)
        if not complete:continue
        removed=[]
        for row in g.itertuples():
            member=frozenset(str(row.member_workers).split('|'))
            assert len(member)==int(row.k) and member<=workers[r.pool_id]
            rem=tuple(sorted(workers[r.pool_id]-member));assert len(rem)==int(r.deletions)
            removed.append(rem)
        assert len(set(removed))==expected
        g['_removed']=removed
        g=g.reset_index(drop=True)
        data[r.pool_id,int(r.n)]={'frame':g,'meta':record,'workers':workers[r.pool_id],'origin':source[r.pool_id]}
    inputs={'scalar_path':str(scalar_path.relative_to(ROOT)),'scalar_sha256':scalar_sha,'scalars_rows':scalar_rows,
            'complete_layers':sum(r['complete_layer'] for r in receipt),'registered_layers':len(receipt)}
    return data,labels,feats,pd.DataFrame(receipt),inputs

def label_maps(labels):
    assert not labels.heldout_building.eq('ALL').any()
    maps={};catalog={}
    for (method,condition),g in labels.groupby(['method_id','condition'],sort=True):
        tiers=set(g.tier);coarsetier='coarse' if 'coarse' in tiers else 'single';has_fine='fine' in tiers
        catalog[method,condition]={'has_distinct_fine_definition':has_fine,'target_buildings':sorted(g.heldout_building.unique()),
            'legacy':method in LEGACY,'ordinary_only':method in LEGACY,'native_tiers':sorted(tiers)}
        for b,h in g.groupby('heldout_building'):
            if method in LEGACY:
                for s in h.training_buildings.unique():assert b not in str(s).split('|'),'legacy label includes target building'
            coarse=dict(zip(h[h.tier.eq(coarsetier)].worker_id,h[h.tier.eq(coarsetier)].class_id))
            fine=dict(zip(h[h.tier.eq('fine')].worker_id,h[h.tier.eq('fine')].class_id)) if has_fine else coarse.copy()
            common=set(coarse)&set(fine)
            maps[method,condition,b]={'coarse':{w:coarse[w] for w in common},'fine':{w:fine[w] for w in common},'has_fine':has_fine}
    return maps,catalog

def families(catalog):
    rows=[]
    for (method,condition),spec in sorted(catalog.items()):
        rows.append(('own_supported',condition,[method]))
    rows+=[('common_modern','manual',MODERN_MANUAL),('common_modern','semi',MODERN_SEMI),
           ('common_with_legacy','manual',MODERN_MANUAL+LEGACY)]
    return rows

def center(values,codes,groups):
    """Mean within actual common usable pool/n support, vectorized."""
    a=np.asarray(values,float)
    if a.ndim==1:a=a[:,None]
    sums=np.zeros((groups,a.shape[1]));np.add.at(sums,codes,a)
    counts=np.bincount(codes,minlength=groups)
    return a-sums[codes]/counts[codes,None]

def weights(meta):
    """Each building equal, image equal, reference pool equal, endpoint equal."""
    # One deletion layer per fit; pool_id preserves reference version/pool contract.
    m=meta[['pool_id','image_id','building']].copy()
    p=m.groupby(['building','image_id','pool_id'],sort=False).size().rename('endpoints').reset_index()
    p['pools_in_image']=p.groupby(['building','image_id']).pool_id.transform('size')
    nimages=p[['building','image_id']].drop_duplicates().groupby('building').size()
    p['images_in_building']=p.building.map(nimages)
    p['weight']=1/(p.endpoints*p.pools_in_image*p.images_in_building*len(nimages))
    return m.merge(p[['pool_id','weight']],on='pool_id',how='left',validate='many_to_one').weight.to_numpy(float)

def aggregate_design(pool_items,variable,features,mapping,method):
    coarse_levels=sorted(set(mapping['coarse'].values()));fine_levels=sorted(set(mapping['fine'].values()))
    cix={v:i for i,v in enumerate(coarse_levels)};fix={v:i for i,v in enumerate(fine_levels)}
    names=['source_new_fraction']+['mean_'+q for q in QT]+['second_moment_'+q for q in QT]+['coarse_'+c for c in coarse_levels]+['fine_'+c for c in fine_levels]
    rows=[];arrays=[];support=[]
    # Person history is constant across the training pools in this outer fold.
    # Build it once, rather than repeatedly indexing pandas for each pool/person.
    person_phi={}
    for w in sorted(variable):
        q=features.loc[w,QT].to_numpy(float);assert np.isfinite(q).all()
        cc=np.zeros(len(coarse_levels));cc[cix[mapping['coarse'][w]]]=1
        ff=np.zeros(len(fine_levels));ff[fix[mapping['fine'][w]]]=1
        person_phi[w]=np.r_[float(features.loc[w,'origin']=='new'),q,q*q,cc,ff]
    for item in pool_items:
        g=item['frame'];meta=item['meta'];known=sorted(item['workers']&variable);u=len(known);delta=meta['deletions'];n=meta['n']
        possible=math.comb(u,delta) if u>=delta else 0
        support.append(dict(meta,variable_workers=u,fixed_background_workers=len(item['workers'])-u,restricted_exact_sets=possible,
                            class_known_before_QT_intersection=len(item['workers']&set(mapping['coarse'])),method_id=method))
        if possible<2:continue
        keep=np.fromiter((set(rem)<=variable for rem in g._removed),dtype=bool,count=len(g));a=g[keep].copy()
        assert len(a)==possible
        phi=np.stack([person_phi[w] for w in known]);lookup={w:i for i,w in enumerate(known)}
        assert all(bool(phi[i,0])==(item['origin'][w]=='new') for i,w in enumerate(known))
        # The fixed background contribution cancels exactly in each pool/n.
        # No missing person feature is assigned a numerical zero.
        expected_removed=delta/u*phi.sum(axis=0)
        remove_indices=np.asarray([[lookup[w] for w in rem] for rem in a._removed],int)
        x=(expected_removed-phi[remove_indices].sum(axis=1))/n
        assert np.max(np.abs(x.mean(axis=0)))<1e-8
        rows.append(a);arrays.append(x)
    if not rows:return None,None,names,pd.DataFrame(support)
    return pd.concat(rows,ignore_index=True),np.concatenate(arrays),names,pd.DataFrame(support)

def model_columns(names,has_fine):
    source=[i for i,c in enumerate(names) if c.startswith('source_')]
    qt=[i for i,c in enumerate(names) if c.startswith('mean_')]
    moments=[i for i,c in enumerate(names) if c.startswith('second_moment_')]
    coarse=[i for i,c in enumerate(names) if c.startswith('coarse_')]
    fine=[i for i,c in enumerate(names) if c.startswith('fine_')]
    models={'source':source,'QT_source':source+qt,'coarse_source':source+coarse,
            'QT_plus_coarse_source':source+qt+coarse,'QT_moments_source':source+qt+moments}
    if has_fine:models.update(fine_source=source+fine,QT_plus_fine_source=source+qt+fine,QT_moments_plus_fine_source=source+qt+moments+fine)
    return models

def eligibility_ledger(data,receipts,maps,catalog,features,strata,out):
    """Count every registered target layer, including absent legacy fold maps.

    One row per family/target pool/n/outcome/size stratum. This denominator is
    independent of whether a model was fitted successfully. Unknown supported
    population sizes remain missing, never zero. Family rows are not independent
    experimental endpoints and must not be summed across overlapping families.
    """
    rows=[]
    numeric={k:v['frame'][METRICS].apply(pd.to_numeric,errors='coerce').to_numpy(float) for k,v in data.items()}
    for scope,condition,family in families(catalog):
        rr=receipts[receipts.condition.eq(condition)]
        statcache={}
        for b in sorted(rr.building.unique()):
            absent=[method for method in family if (method,condition,b) not in maps]
            fs=features[features.condition.eq(condition)&features.heldout_building.eq(b)].set_index('worker_id')
            if absent or not len(fs):variable=None;stats={};class_known=None
            else:
                class_known=set.intersection(*(set(maps[method,condition,b]['coarse'])&set(maps[method,condition,b]['fine']) for method in family))
                variable=class_known&set(fs.index[fs[QT].notna().all(axis=1)])
                cachekey=tuple(sorted(variable))
                if cachekey not in statcache:
                    stats={}
                    for key,item in data.items():
                        if item['meta']['condition']!=condition:continue
                        known=item['workers']&variable;u=len(known);delta=item['meta']['deletions']
                        possible=math.comb(u,delta) if u>=delta else 0
                        keep=np.fromiter((all(w in variable for w in rem) for rem in item['frame']._removed),dtype=bool,count=len(item['frame']))
                        assert int(keep.sum())==possible
                        a=numeric[key][keep];valid=np.isfinite(a);counts=valid.sum(axis=0)
                        varies=[]
                        for j in range(len(METRICS)):
                            z=a[valid[:,j],j]
                            varies.append(bool(len(z)>1 and np.var(z)>1e-12))
                        stats[key]={'u':u,'fixed':len(item['workers'])-u,'possible':possible,'counts':counts,'varies':varies}
                    statcache[cachekey]=stats
                stats=statcache[cachekey]
            for stratum in strata:
                eligible=rr if stratum!='n_ge20' else rr[rr.n.ge(20)]
                for (delta,layer),group in eligible.groupby(['deletions','layer'],sort=False):
                    target=group[group.building.eq(b)]
                    if not len(target):continue
                    disallowed=any(catalog[method,condition]['ordinary_only'] for method in family) and not layer.startswith('ordinary_')
                    trains=[set() for _ in METRICS]
                    if variable is not None and not disallowed:
                        for r in group.itertuples():
                            if r.building==b or (r.pool_id,int(r.n)) not in stats:continue
                            ss=stats[r.pool_id,int(r.n)]
                            for j,n in enumerate(ss['counts']):
                                if n>=2:trains[j].add(r.building)
                    for r in target.itertuples():
                        key=(r.pool_id,int(r.n));ss=stats.get(key)
                        base=dict(support_scope=scope,family='|'.join(family),condition=condition,
                            heldout_building=b,pool_id=r.pool_id,image_id=r.image_id,layer=layer,
                            N=r.N,n=r.n,deletions=delta,size_stratum=stratum,
                            required_all_member_sets=r.required_sets,materialized_all_member_sets=r.materialized_sets,
                            complete_full_layer=r.complete_layer,missing_map_methods='|'.join(absent),
                            classified_pool_workers=len(data[key]['workers']&class_known) if class_known is not None and key in data else np.nan,
                            variable_pool_workers=ss['u'] if ss else np.nan,
                            fixed_background_workers=ss['fixed'] if ss else np.nan,
                            restricted_exact_member_sets=ss['possible'] if ss else np.nan)
                        for j,metric in enumerate(METRICS):
                            count=int(ss['counts'][j]) if ss else np.nan
                            if disallowed:status='legacy_declared_ordinary_only'
                            elif absent:status='no_target_excluded_label_map'
                            elif not len(fs):status='no_target_excluded_QT_feature_map'
                            elif not r.complete_layer:status='full_member_set_layer_incomplete'
                            elif ss['possible']<2:status='fewer_than_two_restricted_member_sets'
                            elif count<2:status='fewer_than_two_outcome_available_member_sets'
                            elif len(trains[j])<3:status='fewer_than_three_training_buildings'
                            else:status='evaluated'
                            rows.append(dict(base,outcome=metric,outcome_available_member_sets=count,
                                outcome_missing_member_sets=ss['possible']-count if ss else np.nan,
                                training_buildings_available=len(trains[j]),
                                target_outcome_varies=ss['varies'][j] if ss else None,status=status))
        print('Denominator',scope,condition,'/'.join(family),flush=True)
    ledger=pd.DataFrame(rows);save(ledger,'TEAM_RESPONSE_ELIGIBILITY_LEDGER.csv.gz',out)
    keys=['support_scope','family','condition','deletions','size_stratum','layer','outcome','status']
    summary=ledger.groupby(keys,dropna=False,as_index=False).agg(buildings=('heldout_building','nunique'),
        images=('image_id','nunique'),pools=('pool_id','size'),
        required_all_member_sets=('required_all_member_sets','sum'),materialized_all_member_sets=('materialized_all_member_sets','sum'),
        restricted_population_known_pools=('restricted_exact_member_sets','count'),
        restricted_exact_member_sets=('restricted_exact_member_sets',lambda s:s.sum(min_count=1)),
        outcome_available_member_sets=('outcome_available_member_sets',lambda s:s.sum(min_count=1)),
        variable_target_pools=('target_outcome_varies','sum'))
    save(summary,'TEAM_RESPONSE_ELIGIBILITY_SUMMARY.csv',out)
    return len(ledger)

def evaluate(frame,x,names,heldout,method,condition,scope,family,has_fine,delta,stratum,layer):
    results=[];fits=[];support=[]
    bases=dict(method_id=method,condition=condition,support_scope=scope,family='|'.join(family),heldout_building=heldout,deletions=delta,size_stratum=stratum,layer=layer)
    cache={}
    for metric in METRICS:
        good=np.isfinite(pd.to_numeric(frame[metric],errors='coerce').to_numpy(float))
        cachekey=np.packbits(good).tobytes()
        if cachekey not in cache:
            sub=frame.loc[good].reset_index(drop=True);xx=x[good]
            counts=sub.groupby('pool_id').pool_id.transform('size')
            enough=counts.ge(2).to_numpy();sub=sub[enough].reset_index(drop=True);xx=xx[enough]
            if len(sub):
                codes,levels=pd.factorize(sub.pool_id,sort=False);ng=len(levels);xx=center(xx,codes,ng)
                train=sub.building.ne(heldout).to_numpy();test=~train
                trainmeta=sub.loc[train].reset_index(drop=True);testmeta=sub.loc[test].reset_index(drop=True)
                w=weights(trainmeta) if train.any() else np.array([])
                testcodes,testlevels=pd.factorize(testmeta.pool_id,sort=False);testcounts=np.bincount(testcodes)
                poolinfo=testmeta.drop_duplicates('pool_id')[['pool_id','image_id','image','building','k','pool_n','reference_id','reference_version','difficulty']].reset_index(drop=True)
                prepared={}
                for model,columns in model_columns(names,has_fine).items():
                    a=xx[train][:,columns];bb=xx[test][:,columns];sd=np.sqrt((a*a*w[:,None]).sum(axis=0));active=sd>1e-10;scale=np.where(active,sd,1.)
                    a=a/scale;bb=bb/scale;a[:,~active]=0;bb[:,~active]=0
                    gram=(a*w[:,None]).T@a
                    prepared[model]=(columns,a,bb,np.linalg.inv(gram+PENALTY*np.eye(len(columns))),active,int(np.linalg.matrix_rank(gram)))
                cache[cachekey]=(sub,enough,codes,ng,train,test,trainmeta,testmeta,w,testcodes,testcounts,poolinfo,prepared)
            else:cache[cachekey]=None
        state=cache[cachekey]
        if state is None:continue
        sub,enough,codes,ng,train,test,trainmeta,testmeta,w,testcodes,testcounts,poolinfo,prepared=state
        if len(sub)==0:continue
        yy=center(frame.loc[good,metric].to_numpy()[enough],codes,ng).ravel()
        trainbuild=sub.loc[train,'building'].nunique();testpools=sub.loc[test,'pool_id'].nunique()
        support.append(dict(bases,outcome=metric,all_restricted_endpoints=len(frame),metric_available_endpoints=int(good.sum()),
            nonestimable_singleton_available_endpoints=int((~enough).sum()),train_endpoints=int(train.sum()),train_buildings=trainbuild,
            test_endpoints=int(test.sum()),test_pools=testpools,status='evaluated' if trainbuild>=3 and test.any() else 'insufficient_training_buildings_or_no_target'))
        if trainbuild<3 or not test.any():continue
        yt=yy[train];ye=yy[test]
        assert heldout not in set(trainmeta.building)
        for model,(columns,a,bb,ginv,active,rank) in prepared.items():
            coef=ginv@((a*w[:,None]).T@yt);pred=bb@coef
            # Every complete evaluation support is pool-centered by construction.
            pool=poolinfo.copy();pool['mse']=np.bincount(testcodes,weights=(ye-pred)**2)/testcounts
            pool['mae']=np.bincount(testcodes,weights=abs(ye-pred))/testcounts
            pool['null_mse']=np.bincount(testcodes,weights=ye*ye)/testcounts;pool['response_variance']=pool.null_mse;pool['endpoints']=testcounts
            for c,v in dict(bases,outcome=metric,model=model,has_distinct_fine_definition=has_fine).items():pool[c]=v
            pool['outcome_varies']=pool.response_variance.gt(1e-12)
            results.append(pool)
            fits.append(dict(bases,outcome=metric,model=model,train_buildings=trainbuild,train_images=trainmeta.image_id.nunique(),train_pools=trainmeta.pool_id.nunique(),
                train_endpoints=len(trainmeta),test_pools=testpools,test_endpoints=len(testmeta),entered_predictors=len(columns),identified_training_predictors=int(active.sum()),
                training_design_rank=rank,ridge=PENALTY,
                predictor_fields='|'.join(names[i] for i in columns),target_outcome_used_for_fit=False,target_feature_scale_used=False))
    return results,fits,support

def summaries(pool,out):
    group=['method_id','condition','support_scope','family','deletions','size_stratum','layer','outcome','model','has_distinct_fine_definition']
    # pool rows are one target building's evaluation only; no duplicate targets.
    assert not pool.duplicated(group+['pool_id']).any()
    img=pool.groupby(group+['heldout_building','image_id'],dropna=False,as_index=False).agg(mse=('mse','mean'),mae=('mae','mean'),null_mse=('null_mse','mean'),
        endpoints=('endpoints','sum'),pools=('pool_id','size'),variable_pools=('outcome_varies','sum'))
    build=img.groupby(group+['heldout_building'],dropna=False,as_index=False).agg(mse=('mse','mean'),mae=('mae','mean'),null_mse=('null_mse','mean'),
        endpoints=('endpoints','sum'),pools=('pools','sum'),images=('image_id','size'),variable_pools=('variable_pools','sum'))
    build['R2_vs_finite_pool_mean']=np.where(build.null_mse>1e-12,1-build.mse/build.null_mse,np.nan)
    save(build,'TEAM_RESPONSE_BUILDINGS.csv.gz',out)
    summary=build.groupby(group,dropna=False,as_index=False).agg(mse=('mse','mean'),mae=('mae','mean'),null_mse=('null_mse','mean'),
        buildings=('heldout_building','size'),endpoints=('endpoints','sum'),pools=('pools','sum'),images=('images','sum'),variable_pools=('variable_pools','sum'))
    summary['R2_vs_finite_pool_mean']=np.where(summary.null_mse>1e-12,1-summary.mse/summary.null_mse,np.nan)
    save(summary,'TEAM_RESPONSE_SUMMARY.csv',out)
    comparisons=[]
    keys=[v for v in group if v not in ['model','has_distinct_fine_definition']]
    pairs=[('coarse_source','QT_source'),('fine_source','coarse_source'),('fine_source','QT_source'),('QT_plus_coarse_source','QT_source'),
           ('QT_plus_fine_source','QT_source'),('QT_plus_fine_source','QT_plus_coarse_source'),('QT_moments_plus_fine_source','QT_moments_source'),
           ('QT_moments_source','QT_source')]
    for vals,g in build.groupby(keys,dropna=False):
        meta=dict(zip(keys,vals));wide=g.pivot(index='heldout_building',columns='model',values='mse')
        for new,base in pairs:
            if new not in wide or base not in wide:continue
            paired=wide[[new,base]].dropna();v=paired[base]-paired[new]
            rr=np.random.default_rng(SEED);boot=v.to_numpy()[rr.integers(len(v),size=(2000,len(v)))].mean(axis=1) if len(v)>1 else np.array([np.nan])
            lo,hi=np.quantile(boot,[.025,.975])
            comparisons.append(dict(meta,new_model=new,baseline=base,buildings=len(v),mse_new=paired[new].mean(),mse_baseline=paired[base].mean(),
                mse_reduction=v.mean(),mse_reduction_median=v.median(),positive_buildings=int(v.gt(1e-12).sum()),negative_buildings=int(v.lt(-1e-12).sum()),
                equal_buildings=int(v.abs().le(1e-12).sum()),bootstrap95_low=lo,bootstrap95_high=hi,
                relative_mse_reduction=v.mean()/paired[base].mean() if paired[base].mean()>1e-12 else np.nan,
                inference='paired_building_bootstrap_descriptive_after_exploration;not_blind_confirmatory_test'))
    save(pd.DataFrame(comparisons),'TEAM_RESPONSE_INCREMENT.csv',out)
    return summary,build

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--deletions',nargs='+',type=int,default=[1]);ap.add_argument('--out',type=Path,default=HERE/'team_response');
    ap.add_argument('--size-strata',nargs='+',default=['n_ge20','all_n'])
    ap.add_argument('--scalars',type=Path,default=COMP/'TEAMS_SCALARS.csv.gz')
    ap.add_argument('--denominators-only',action='store_true');args=ap.parse_args()
    assert set(args.deletions)<=set([1,2]);out=args.out;out.mkdir(parents=True,exist_ok=True)
    start=time.time();data,labels,features,layer_receipt,inputs=load(args.deletions,args.scalars);maps,catalog=label_maps(labels)
    save(layer_receipt,'TEAM_RESPONSE_LAYER_COMPLETENESS.csv',out)
    denominator_rows=eligibility_ledger(data,layer_receipt,maps,catalog,features,args.size_strata,out)
    if args.denominators_only:return
    results=[];fitrows=[];opportunities=[];folds=[];missing=[];m=0;parts=[]
    runtime=out/'runtime';runtime.mkdir(exist_ok=True)
    for scope,condition,family in families(catalog):
        available=set.intersection(*(set(catalog[method,condition]['target_buildings']) for method in family))
        for b in sorted(available):
            fs=features[features.condition.eq(condition)&features.heldout_building.eq(b)].set_index('worker_id')
            finite=set(fs.index[fs[QT].notna().all(axis=1)])
            variable=finite & set.intersection(*(set(maps[method,condition,b]['coarse'])&set(maps[method,condition,b]['fine']) for method in family))
            commonmap={method:maps[method,condition,b] for method in family}
            map_sha=digest({'condition':condition,'heldout':b,'maps':commonmap,'variable_workers':sorted(variable)})
            # A single outer map applies to ALL source pools, including the training pools.
            for delta in args.deletions:
                for stratum in args.size_strata:
                    pool_candidates=[v for v in data.values() if v['meta']['condition']==condition and v['meta']['deletions']==delta and (stratum!='n_ge20' or v['meta']['n']>=20)]
                    for layer in sorted(set(v['meta']['layer'] for v in pool_candidates)):
                        if any(catalog[method,condition]['ordinary_only'] for method in family) and not layer.startswith('ordinary_'):
                            missing.append(dict(support_scope=scope,family='|'.join(family),condition=condition,heldout_building=b,deletions=delta,size_stratum=stratum,layer=layer,status='legacy_declared_ordinary_only'))
                            continue
                        items=[v for v in pool_candidates if v['meta']['layer']==layer]
                        if not any(v['meta']['building']==b for v in items):continue
                        for method in family:
                            frame,x,names,sup=aggregate_design(items,variable,fs,commonmap[method],method)
                            if frame is None:continue
                            if not frame.building.eq(b).any():
                                missing.append(dict(method_id=method,support_scope=scope,family='|'.join(family),condition=condition,heldout_building=b,deletions=delta,size_stratum=stratum,layer=layer,status='no_target_restricted_layer_with_two_endpoints'))
                                continue
                            target=sup[sup.building.eq(b)].copy()
                            for c,v in dict(support_scope=scope,heldout_building=b,size_stratum=stratum,outer_map_sha256=map_sha).items():target[c]=v
                            opportunities.append(target)
                            folds.append(dict(method_id=method,condition=condition,heldout_building=b,support_scope=scope,family='|'.join(family),deletions=delta,size_stratum=stratum,layer=layer,
                                outer_variable_workers='|'.join(sorted(variable)),outer_map_sha256=map_sha,available_train_buildings='|'.join(sorted(set(frame.building)-{b})),
                                target_records_used_for_feature_fit=False,label_map_applied_to_train_and_test='same_target_building_excluded_map',legacy_fit_scope='history10_target12' if method in LEGACY else 'outer_building_excluded'))
                            rr,ff,ss=evaluate(frame,x,names,b,method,condition,scope,family,commonmap[method]['has_fine'],delta,stratum,layer)
                            if rr:results.append(pd.concat(rr,ignore_index=True))
                            fitrows.extend(ff);missing.extend(ss)
            m+=1
        print('Completed',scope,condition,'/'.join(family),'seconds',round(time.time()-start,1),flush=True)
        # Keep memory bounded while native fusion may run in other processes.
        # These compact family checkpoints contain analysis only, no geometries.
        slug=scope+'__'+condition+'__'+'-'.join(family)
        chunk={'pool':pd.concat(results,ignore_index=True) if results else pd.DataFrame(),
               'fits':pd.DataFrame(fitrows),'maps':pd.DataFrame(folds),'opportunities':pd.DataFrame(missing),
               'support':pd.concat(opportunities,ignore_index=True) if opportunities else pd.DataFrame()}
        paths={}
        for name,table in chunk.items():
            if len(table):
                filename=slug+'__'+name+'.csv.gz';save(table,filename,runtime);paths[name]=runtime/filename
        parts.append(paths)
        results.clear();fitrows.clear();opportunities.clear();folds.clear();missing.clear();del chunk
        gc.collect()
    def combine(name):
        frames=[pd.read_csv(p[name],low_memory=False) for p in parts if name in p]
        return pd.concat(frames,ignore_index=True) if frames else pd.DataFrame()
    pool=combine('pool')
    if not len(pool):raise RuntimeError('No complete evaluable target layers; inspect completeness ledger')
    save(pool,'TEAM_RESPONSE_POOL_RESULTS.csv.gz',out)
    save(combine('fits'),'TEAM_RESPONSE_FIT_SUPPORT.csv.gz',out)
    save(combine('maps'),'TEAM_RESPONSE_FOLD_MAPS.csv.gz',out)
    save(combine('support'),'TEAM_RESPONSE_TARGET_SUPPORT.csv.gz',out)
    save(combine('opportunities'),'TEAM_RESPONSE_OPPORTUNITIES.csv.gz',out)
    summary,build=summaries(pool,out)
    js(out/'TEAM_RESPONSE_CONTRACT.json',{
      'source_main':'51b519f943b2dd3a4fb2f0198133ac5dd17209ab','source_data':inputs,'deletions':args.deletions,'size_strata':args.size_strata,
      'selection':'Only method-independent registered complete near-census member sets. Completeness verified by choose(N,deletions), unique endpoint keys, valid full-pool subsets and unique deletion sets.',
      'estimand':'Relative response to team composition within a finite pool/n member-set population, centered on the common usable endpoints. Not unseen-image absolute quality. No training R2 used as evidence.',
      'unknown_personnel':'Every unclassified or QT-feature-missing worker is retained in every endpoint as fixed background; deletions only among the joint-supported workers. Fixed missing contributions cancel in centered first/second moments; no imputation or unknown class.',
      'outer_split':'For target building b, the same labels and continuous person features excluding b are used on EVERY training pool and the target pools. Model coefficients and scaling fitted only on buildings !=b.',
      'legacy':'Rnew2/F01 are evaluable only for their 12 original target buildings, which are absent from their fixed 10-building label fit; maps are applied consistently on other training buildings. No invented legacy LOBO map for the 10 history buildings. Their frozen 10-building labels versus current 21-building continuous histories are a practical comparison of available artifacts, not an equal-history-budget algorithm contest.',
      'target_centering':'Subtract pool/n mean from y and every aggregate predictor. Test y mean defines the finite-population relative estimand; it is not a fitted intercept or claim of absolute prospective prediction. Quality moments are conditional on score availability; failures are retained as a separate all-endpoint response.',
      'predictors':'Source share; per-team mean contributions of q_effect/q_downside/t_effect/t_tail; coarse/fine class fractions. Optional fixed QT second raw moments sensitivity protects against unfairly weak mean-only continuous baseline.',
      'weights':'Equal endpoints within reference pool/n; equal reference pools within image; equal images within building; equal buildings. Every model comparison for a method/scope/outcome uses exactly the same endpoints.',
      'regularization':{'fixed_ridge_penalty':PENALTY,'scaling':'weighted RMS of centered training columns only','parameter_search':False,'intercept':False},
      'fine_level':'Single-level A2/Rnew2/F01 produce no fine-increment claims. Coarse and fine models share a common classified+continuous-supported population.',
      'time':'log summed source seconds only when all members have source time and one time_source_kind; mixed source-clock endpoints excluded for this outcome. Time still describes active-time cost, not wall-clock completion.',
      'failure':'1-complete_evaluable on every materialized endpoint. Ridge predicts relative failure response, not a calibrated absolute probability. Missing quality never coded zero.',
      'zero_variation':'Full N endpoint excluded. Constant N-1/N-2 response layers retained in MSE but separately counted; zero response is not evidence of class efficacy.',
      'common_support_families':{'manual_modern':MODERN_MANUAL,'semi_modern':MODERN_SEMI,'manual_with_legacy':MODERN_MANUAL+LEGACY},
      'scope':'Ordinary, doorway and special layers separated. Legacy restricted to ordinary. Less than 3 training buildings or fewer than 2 usable endpoints/pool produces explicit non-estimation.',
      'denominator_ledger':'Every registered target pool/n/outcome/family is retained, including absent legacy fold maps and unusable quality populations. Unknown support counts stay missing. Counts overlap across methods/families and outcome strata; do not sum them as distinct endpoint calculations.',
      'exploration':'Previously explored inventory; no fresh blind test. Paired building bootstrap is descriptive and not multiplicity-adjusted.',
      'metrics':METRICS,'input_sha256':{str(p.relative_to(ROOT)):sha(p) for p in [COMP/'EXACT_LAYERS.csv',COMP/'FROZEN_LABELS.csv',MV/'continuous_features_lobo.csv.gz',SNAPSHOT]},
      'elapsed_seconds':time.time()-start,'pool_result_rows':len(pool),'building_result_rows':len(build),'summary_rows':len(summary),'denominator_rows':denominator_rows,
      'canonical_duplicate_policy':'No endpoints recomputed, only existing scalar outcomes read; no modification of analyze_global.py.'})
    print('DONE',len(pool),'pool/model/outcome rows;',round(time.time()-start,1),'seconds',flush=True)

if __name__=='__main__':main()
