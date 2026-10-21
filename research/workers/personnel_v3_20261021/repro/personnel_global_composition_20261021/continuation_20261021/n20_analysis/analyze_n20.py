"""Finite n=20 class-vector design: weighted descriptions and outer-building CV.

Every configuration is observed, at most three member sets per configuration.
Configuration-uniform and member-universe inverse sampling weights are separate.
No new fusion and no outcome-dependent method or hyperparameter selection.
"""
from __future__ import annotations
import os
for _k in ('OPENBLAS_NUM_THREADS', 'OMP_NUM_THREADS', 'MKL_NUM_THREADS'):
    os.environ[_k] = '1'
import argparse
import gc
import gzip
import hashlib
import importlib.util
import json
import math
from pathlib import Path
import time
import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
STUDY = HERE.parents[1]
NEXT = HERE.parent/'next_stage'
DESIGN = NEXT/'candidate_n20'
SNAPSHOT = STUDY.parents[2]/'research/workers/pro_personnel_v2_archive_20261019/work_v2_20261019/fusion/INPUT_SNAPSHOT.json.gz'
QT = ['q_effect', 'q_downside', 't_effect', 't_tail']
OUTCOMES = ['B8L2', 'D10', 'failure', 'nodes', 'iou_2d', 'IoU3D100',
            'S_bottom_deg', 'dir', 'Hmean', 'Hcenter', 'omission', 'extension',
            'height_mean_h', 'ref_node_recall_9', 'ref_edge_recall_9', 'log_source_time_total']
MODERN = {'manual':['M_structure', 'A2_relation', 'MV_QTD_manual_new'],
          'semi':['SP_scale', 'A2_relation', 'MV_QTScopeSemi_semi_new']}
ANCHOR = {'manual':'M_structure', 'semi':'SP_scale'}
PENALTY = .01
SEED = 2026102163


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def safe_json(value):
    if isinstance(value,dict):return {str(k):safe_json(v) for k,v in value.items()}
    if isinstance(value,(list,tuple,np.ndarray)):return [safe_json(v) for v in value]
    if isinstance(value,np.generic):return safe_json(value.item())
    if isinstance(value,float) and not np.isfinite(value):return None
    return value


def js(path,value):
    tmp=path.with_name(path.name+'.partial')
    tmp.write_text(json.dumps(safe_json(value),ensure_ascii=False,indent=2,allow_nan=False)+'\n',encoding='utf-8')
    json.loads(tmp.read_text());os.replace(tmp,path)


def save(frame,path):
    tmp=path.with_name(path.name+'.partial')
    compression={'method':'gzip','mtime':0} if path.name.endswith('.gz') else None
    frame.to_csv(tmp,index=False,encoding='utf-8-sig',compression=compression)
    read=pd.read_csv(tmp,compression='gzip' if compression else None,low_memory=False)
    assert read.shape==frame.shape,(path.name,read.shape,frame.shape)
    os.replace(tmp,path)


def source_files():
    return [NEXT/'batches/REUSED_ENDPOINT_SCALARS.csv.gz']+sorted((NEXT/'batches').glob('batch_*/ENDPOINT_SCALARS.csv.gz'))


def load(condition):
    design=json.loads((DESIGN/'DESIGN_CANDIDATE.json').read_text())
    memberships=pd.read_csv(DESIGN/'CONFIG_MEMBERSHIP.csv.gz',low_memory=False)
    cells=pd.read_csv(DESIGN/'CONFIG_CELLS.csv.gz',low_memory=False)
    assert len(memberships)==design['member_references'] and len(cells)==design['cells']
    assert not memberships.duplicated(['cell_id','team_key']).any()
    assert not cells.cell_id.duplicated().any()
    assert not cells.duplicated(['method_id','pool_id','composition']).any()
    registered=memberships.groupby('cell_id').size()
    assert cells.set_index('cell_id').sampled_member_sets.eq(registered).all()
    memberships=memberships[memberships.condition.eq(condition)].copy()
    cells=cells[cells.condition.eq(condition)].copy()
    need=set(memberships.team_key)
    pieces=[];inputs={}
    for path in source_files():
        if not path.exists():continue
        d=pd.read_csv(path,low_memory=False)
        d=d[d.team_key.isin(need)]
        if len(d):pieces.append(d);inputs[str(path.relative_to(STUDY))]=sha(path)
    scalars=pd.concat(pieces,ignore_index=True)
    assert not scalars.team_key.duplicated().any(),'native checkpoint sets overlap'
    missing=need-set(scalars.team_key)
    if missing:raise RuntimeError(f'{condition}: {len(missing)} registered native endpoints not yet completed')
    assert set(scalars.team_key)==need
    scalars['failure']=(~scalars.complete_evaluable.astype(bool)).astype(float)
    time_ok=(scalars.source_time_known_n.eq(scalars.k)&scalars.source_time_total_seconds.gt(0)&
             ~scalars.time_source_kinds.fillna('').str.contains('|',regex=False)&
             scalars.time_source_kinds.fillna('').ne(''))
    scalars['log_source_time_total']=np.log(scalars.source_time_total_seconds.where(time_ok))
    for metric in OUTCOMES:
        if metric not in scalars:scalars[metric]=np.nan
    assert scalars.k.eq(20).all()
    old_panel=set(pd.read_csv(STUDY/'composition/PANEL_POOLS.csv').pool_id)
    memberships['target_panel']=np.where(memberships.pool_id.isin(old_panel),'prior_panel','added_images')
    cells['target_panel']=np.where(cells.pool_id.isin(old_panel),'prior_panel','added_images')
    scalars['target_panel']=np.where(scalars.pool_id.isin(old_panel),'prior_panel','added_images')
    fields=['team_key','member_workers','time_source_kinds','source_time_known_n','source_time_total_seconds','score_status']+OUTCOMES
    frame=memberships.merge(scalars[fields],on='team_key',how='left',validate='many_to_one')
    assert len(frame)==len(memberships)
    return frame,cells,scalars,inputs


def validate_universe(cells,out):
    rows=[]
    for (method,pool),g in cells.groupby(['method_id','pool_id']):
        total=0
        for r in g.itertuples():
            capacity={a:int(b) for a,b in (v.split(':') for v in r.class_capacities.split('|'))}
            counts={a:int(b) for a,b in (v.split(':') for v in r.composition.split('|'))}
            assert set(counts)==set(capacity)
            assert sum(counts.values())==20 and sum(capacity.values())==r.labelled_pool_n
            expected=math.prod(math.comb(capacity[k],v) for k,v in counts.items())
            assert expected==int(r.possible_member_sets),(method,pool,r.cell_id)
            total+=expected
        possible=math.comb(int(g.labelled_pool_n.iloc[0]),20)
        assert total==possible,(method,pool,total,possible)
        rows.append(dict(method_id=method,pool_id=pool,cells=len(g),
            possible_member_sets=str(possible),sampled_draws=int(g.sampled_member_sets.sum()),
            exact_cell_population_sum=str(total),all_class_vectors_complete=True,
            singleton_cells=int(g.singleton.sum()),
            member_exhaustive_cells=int(g.exhaustive_members.sum())))
    save(pd.DataFrame(rows),out/'N20_WEIGHT_UNIVERSE_CHECK.csv')


def weights_for(frame,good,scheme):
    """After common feature/metric support, define each weighting estimand."""
    sub=frame.loc[good].copy()
    if scheme=='configuration_uniform':
        raw=1/sub.groupby('cell_id').cell_id.transform('size').to_numpy(float)
    else:
        raw=(pd.to_numeric(sub.possible_member_sets).to_numpy(float)/
             sub.registered_member_sets.to_numpy(float))
    return sub,raw


def pooled_mean(values,codes,raw):
    a=np.asarray(values,float)
    if a.ndim==1:a=a[:,None]
    n=int(codes.max())+1
    sums=np.zeros((n,a.shape[1]));np.add.at(sums,codes,a*raw[:,None])
    den=np.bincount(codes,weights=raw,minlength=n)
    return sums/den[:,None]


def training_weights(frame,codes,raw,train):
    pool_sum=np.bincount(codes,weights=raw)
    pool_weights=raw/pool_sum[codes]
    p=frame.loc[train,['pool_id','image_id','building']].drop_duplicates('pool_id')
    p['pools_in_image']=p.groupby(['building','image_id']).pool_id.transform('size')
    nim=p[['building','image_id']].drop_duplicates().groupby('building').size()
    p['factor']=1/(p.pools_in_image*p.building.map(nim)*len(nim))
    factor=dict(zip(p.pool_id,p.factor))
    return pool_weights[train]*frame.loc[train,'pool_id'].map(factor).to_numpy(float)


def describe(frame,cells,out):
    rows=[];curve=[];within=[]
    for (method,pool),g in frame.groupby(['method_id','pool_id'],sort=True):
        first=g.iloc[0]
        metadata={c:first[c] for c in ['method_id','condition','pool_id','image_id','image','building','difficulty','target_panel']}
        metadata.update(n=20,cells=g.cell_id.nunique(),sampled_member_sets=len(g),
                        unique_member_sets=g.team_key.nunique(),labelled_pool_n=int(first.labelled_pool_n),
                        formal_pool_n=int(first.formal_pool_n))
        bycell=dict(tuple(g.groupby('cell_id')))
        for metric in OUTCOMES:
            cm=[]
            for cell,h in bycell.items():
                y=pd.to_numeric(h[metric],errors='coerce').dropna().to_numpy(float)
                population=int(h.possible_member_sets.iloc[0]);draw=len(h)
                valid=len(y)
                samplevar=float(np.var(y,ddof=1)) if valid>=2 else (0. if population==1 and valid==1 else np.nan)
                meanvar=samplevar/valid*(1-valid/population) if valid else np.nan
                cm.append(dict(cell_id=cell,mean=float(y.mean()) if valid else np.nan,
                               sample_variance=samplevar,mean_variance=meanvar,
                               population=population,draw=draw,valid=valid,
                               composition=h.composition.iloc[0]))
            cm=pd.DataFrame(cm)
            for scheme in ['configuration_uniform','member_universe_estimate']:
                usable=cm.valid.gt(0)
                v=cm[usable].copy()
                r=dict(metadata,outcome=metric,weighting=scheme,available_member_sets=int(cm.valid.sum()),
                       missing_member_sets=len(g)-int(cm.valid.sum()),outcome_available_cells=len(v),
                       repeated_valid_cells=int(cm.valid.ge(2).sum()),
                       singleton_population_cells=int(cm.population.eq(1).sum()),
                       declared_member_universe=str(int(cm.population.sum())),
                       estimand='sample_estimate; full class vectors but not all actual members')
                if not len(v):
                    r['status']='no_outcome_available';rows.append(r);continue
                if scheme=='configuration_uniform':cw=np.ones(len(v))/len(v)
                else:
                    # For quality, success-conditioned member-universe mass is
                    # estimated from each cell's sampled success fraction.
                    mass=v.population.to_numpy(float)*v.valid.to_numpy()/v.draw.to_numpy()
                    cw=mass/mass.sum()
                mu=v['mean'].to_numpy(float);grand=np.dot(cw,mu)
                between=np.dot(cw,(mu-grand)**2)
                haswithin=(v.population.gt(1)&v.valid.ge(2)&v.sample_variance.notna()).to_numpy()
                within_est=np.dot(cw[haswithin]/cw[haswithin].sum(),v.loc[haswithin,'sample_variance']) if haswithin.any() else np.nan
                all_observed=bool(cm.valid.eq(cm.draw).all())
                noise=float(np.dot(cw*(1-cw),v.mean_variance)) if all_observed and v.mean_variance.notna().all() else np.nan
                r.update(status='observed',mean=grand,between_sample_cell_means_variance=between,
                         within_cell_member_variance_estimate=within_est,
                         within_variance_available_weight=float(cw[haswithin].sum()),
                         within_variance_estimable_cells=int(haswithin.sum()),
                         singleton_zero_only_used_for_mean_sampling_noise=True,
                         cell_mean_sampling_noise_estimate=noise,
                         between_variance_noise_subtracted=between-noise if np.isfinite(noise) else np.nan,
                         noise_correction_status='all_outcomes_observed' if np.isfinite(noise) else 'missing_outcome_or_unestimable_cell_variance',
                         all_sampled_outcomes_observed=all_observed)
                rows.append(r)
            # Preserve every cell, including failures or singleton opportunities.
            for c in cm.to_dict('records'):
                curve.append(dict(metadata,outcome=metric,**c))
    pool=pd.DataFrame(rows);save(pool,out/'N20_CONFIGURATION_POOL_RESULTS.csv.gz')
    save(pd.DataFrame(curve),out/'N20_CONFIGURATION_CELL_OUTCOMES.csv.gz')
    met=['mean','between_sample_cell_means_variance','within_cell_member_variance_estimate',
         'between_variance_noise_subtracted','cell_mean_sampling_noise_estimate','within_variance_available_weight']
    summary=[]
    for panel in ['all','prior_panel','added_images']:
        z=pool if panel=='all' else pool[pool.target_panel.eq(panel)]
        keys=['method_id','condition','outcome','weighting']
        im=z.groupby(keys+['building','image_id'],dropna=False)[met].mean()
        b=im.groupby(level=keys+['building'],dropna=False).mean().reset_index()
        for vals,g in b.groupby(keys,dropna=False):
            x=dict(zip(keys,vals),target_panel=panel,buildings=g.building.nunique())
            src=z
            for col,value in zip(keys,vals):src=src[src[col].eq(value)]
            x.update(images=src.image_id.nunique(),pools=len(src),cells=int(src.cells.sum()),
                     available_member_sets=int(src.available_member_sets.sum()),
                     missing_member_sets=int(src.missing_member_sets.sum()))
            for m in met:
                x[m]=g[m].mean();x[m+'_buildings']=int(g[m].notna().sum())
                x[m+'_images']=int(src.loc[src[m].notna(),'image_id'].nunique())
            summary.append(x)
    save(pd.DataFrame(summary),out/'N20_CONFIGURATION_SUMMARY.csv')


def load_maps():
    spec=importlib.util.spec_from_file_location('original_cv',STUDY/'analysis/team_continuous_check.py')
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    labels=pd.read_csv(STUDY/'composition/FROZEN_LABELS.csv',keep_default_na=False)
    maps,catalog=module.label_maps(labels)
    feats=pd.read_csv(STUDY/'multivariate/continuous_features_lobo.csv.gz')
    return maps,catalog,feats


def families(condition):
    result=[dict(scope='own_class_supported',anchor=m,methods=[m],class_only=True) for m in MODERN[condition]]
    result.extend(dict(scope='own_design',anchor=m,methods=[m]) for m in MODERN[condition])
    result.append(dict(scope='common_modern_anchor',anchor=ANCHOR[condition],methods=MODERN[condition]))
    result.append(dict(scope='common_new_anchor',anchor=MODERN[condition][-1],methods=MODERN[condition]))
    if condition=='manual':
        result.extend(dict(scope='legacy_anchor',anchor=ANCHOR[condition],methods=[m]) for m in ['Rnew2','F01'])
    return result


def designs(frame,workers,person_idx,fs,mapping,class_only=False):
    levels_c=sorted(set(mapping['coarse'].values()));levels_f=sorted(set(mapping['fine'].values()))
    names=['source_new_fraction']
    if not class_only:names+=['mean_'+q for q in QT]+['second_moment_'+q for q in QT]
    nbase=len(names)
    names+=['coarse_'+c for c in levels_c]+['fine_'+c for c in levels_f]
    phi=np.zeros((len(workers),len(names)),float)
    for w,i in person_idx.items():
        phi[i,0]=float(fs.loc[w,'origin']=='new')
        if not class_only:
            q=fs.loc[w,QT].to_numpy(float);phi[i,1:9]=np.r_[q,q*q]
        phi[i,nbase+levels_c.index(mapping['coarse'][w])]=1
        phi[i,nbase+len(levels_c)+levels_f.index(mapping['fine'][w])]=1
    members=np.asarray([[person_idx[w] for w in s.split('|')] for s in frame.member_workers],int)
    matrix=phi[members].mean(axis=1)
    extra=[];extra_names=[]
    for prefix,indices in [('qtquad_',[i for i,n in enumerate(names) if n.startswith('mean_')]),
                           ('coarsequad_',[i for i,n in enumerate(names) if n.startswith('coarse_')]),
                           ('finequad_',[i for i,n in enumerate(names) if n.startswith('fine_')])]:
        for pos,i in enumerate(indices):
            for j in indices[pos:]:
                extra.append(matrix[:,i]*matrix[:,j]);extra_names.append(prefix+names[i]+'__'+names[j])
    matrix=np.column_stack([matrix]+extra)
    return matrix,names+extra_names


def columns(names,hasfine):
    src=[i for i,n in enumerate(names) if n.startswith('source_')]
    qt=[i for i,n in enumerate(names) if n.startswith('mean_')]
    second=[i for i,n in enumerate(names) if n.startswith('second_moment_')]
    coarse=[i for i,n in enumerate(names) if n.startswith('coarse_')]
    fine=[i for i,n in enumerate(names) if n.startswith('fine_')]
    qtquad=[i for i,n in enumerate(names) if n.startswith('qtquad_')]
    coarsequad=[i for i,n in enumerate(names) if n.startswith('coarsequad_')]
    finequad=[i for i,n in enumerate(names) if n.startswith('finequad_')]
    c={'source':src,'coarse_source':src+coarse,'coarse_quadratic_source':src+coarse+coarsequad}
    if qt:c.update(QT_source=src+qt,QT_moments_source=src+qt+second,
       QT_plus_coarse_source=src+qt+coarse,QT_moments_team_quadratic_source=src+qt+second+qtquad)
    if hasfine:
        c.update(fine_source=src+fine,fine_quadratic_source=src+fine+finequad)
        if qt:c.update(QT_plus_fine_source=src+qt+fine,QT_moments_plus_fine_source=src+qt+second+fine,
            QT_moments_plus_fine_quadratic_source=src+qt+second+fine+finequad)
    return c


def fit_one(frame,x,names,heldout,method,condition,family,hasfine):
    pools=[];fits=[];denominators=[]
    meta=dict(condition=condition,method_id=method,support_scope=family['scope'],
              design_anchor=family['anchor'],family='|'.join(family['methods']),heldout_building=heldout)
    for scheme in ['configuration_uniform','member_universe_estimate']:
        cache={}
        for metric in OUTCOMES:
            ok=frame[metric].notna().to_numpy()
            key=np.packbits(ok).tobytes()
            if key not in cache:
                sub,raw=weights_for(frame,ok,scheme)
                original=np.flatnonzero(ok)
                enough=sub.groupby('pool_id').pool_id.transform('size').ge(2).to_numpy()
                sub=sub.loc[enough].reset_index(drop=True);raw=raw[enough];original=original[enough]
                if not len(sub):cache[key]=None;continue
                codes,levels=pd.factorize(sub.pool_id,sort=False)
                xx=x[original];xx=xx-pooled_mean(xx,codes,raw)[codes]
                train=sub.building.ne(heldout).to_numpy();test=~train
                if not train.any() or not test.any():cache[key]=None;continue
                trainbuild=sub.loc[train,'building'].nunique()
                if trainbuild<3:cache[key]=None;continue
                wt=training_weights(sub,codes,raw,train)
                testcodes,testlevels=pd.factorize(sub.loc[test,'pool_id'],sort=False)
                testweight=raw[test]/np.bincount(testcodes,weights=raw[test])[testcodes]
                info=sub.loc[test].drop_duplicates('pool_id').set_index('pool_id').loc[testlevels,
                    ['image_id','image','building','difficulty','reference_id','reference_version','target_panel']].rename_axis('pool_id').reset_index()
                prepared={}
                for model,ix in columns(names,hasfine).items():
                    a=xx[train][:,ix];b=xx[test][:,ix]
                    sd=np.sqrt((a*a*wt[:,None]).sum(axis=0));active=sd>1e-10
                    scale=np.where(active,sd,1.)
                    a=a/scale;b=b/scale;a[:,~active]=0;b[:,~active]=0
                    gram=(a*wt[:,None]).T@a
                    prepared[model]=(ix,a,b,np.linalg.inv(gram+PENALTY*np.eye(len(ix))),
                                     int(active.sum()),int(np.linalg.matrix_rank(gram)))
                cache[key]=(sub,raw,original,codes,train,test,wt,testcodes,testweight,info,prepared,trainbuild)
            state=cache.get(key)
            if state is None:
                denominators.append(dict(meta,weighting=scheme,outcome=metric,status='insufficient_common_target_or_training_support',
                    supported_draws=len(frame),outcome_available_draws=int(ok.sum())))
                continue
            sub,raw,original,codes,train,test,wt,testcodes,testweight,info,prepared,trainbuild=state
            y=frame[metric].to_numpy(float)[original]
            y=y-pooled_mean(y,codes,raw)[codes,0]
            tr=y[train];te=y[test]
            denominators.append(dict(meta,weighting=scheme,outcome=metric,status='evaluated',
                supported_draws=len(frame),outcome_available_draws=int(ok.sum()),train_draws=int(train.sum()),
                target_draws=int(test.sum()),train_buildings=trainbuild,target_pools=len(info)))
            for model,(ix,a,b,inv,active,rank) in prepared.items():
                coef=inv@((a*wt[:,None]).T@tr);pred=b@coef
                pp=info.copy()
                pp['mse']=np.bincount(testcodes,weights=testweight*(te-pred)**2)
                pp['mae']=np.bincount(testcodes,weights=testweight*abs(te-pred))
                pp['null_mse']=np.bincount(testcodes,weights=testweight*te*te)
                pp['sampled_draws']=np.bincount(testcodes)
                pp['member_estimator_effective_sample_size']=1/np.bincount(testcodes,weights=testweight*testweight)
                for k,v in dict(meta,weighting=scheme,outcome=metric,model=model,n=20).items():pp[k]=v
                pools.append(pp)
                fits.append(dict(meta,weighting=scheme,outcome=metric,model=model,train_buildings=trainbuild,
                    train_draws=int(train.sum()),target_draws=int(test.sum()),entered_predictors=len(ix),
                    active_predictors=active,training_rank=rank,ridge=PENALTY,
                    predictors='|'.join(names[i] for i in ix),target_y_used_for_fit=False,
                    target_feature_scale_used=False))
    return pools,fits,denominators


def predict(frame,out,condition):
    maps,catalog,feats=load_maps()
    original_pools=json.load(gzip.open(SNAPSHOT,'rt'))['images']
    formal_workers={p['pool_id']:set(r['worker_id'] for r in p['records']) for p in original_pools}
    origin_map={}
    for p in original_pools:
        for r in p['records']:
            assert r['worker_id'] not in origin_map or origin_map[r['worker_id']]==r['origin']
            origin_map[r['worker_id']]=r['origin']
    buildings=sorted(frame.building.unique())
    parts=[];support_rows=[];fold_rows=[]
    for family in families(condition):
        anchor=frame[frame.method_id.eq(family['anchor'])].copy()
        family_pools=[];family_fits=[];family_den=[]
        for b in buildings:
            fs=feats[feats.condition.eq(condition)&feats.heldout_building.eq(b)].set_index('worker_id')
            absent=[m for m in family['methods'] if (m,condition,b) not in maps]
            if absent:
                for pid,g in anchor[anchor.building.eq(b)].groupby('pool_id'):
                    support_rows.append(dict(support_scope=family['scope'],design_anchor=family['anchor'],
                        family='|'.join(family['methods']),heldout_building=b,pool_id=pid,status='missing_outer_map',missing_methods='|'.join(absent),
                        registered_draws=len(g),supported_draws=0))
                continue
            class_known=set.intersection(*(set(maps[m,condition,b]['coarse'])&set(maps[m,condition,b]['fine']) for m in family['methods']))
            class_only=family.get('class_only',False)
            if class_only:
                variable=class_known&set(origin_map)
                fs=pd.DataFrame({'worker_id':sorted(variable),'origin':[origin_map[w] for w in sorted(variable)]}).set_index('worker_id')
            else:variable=set(fs.index[fs[QT].notna().all(axis=1)])&class_known
            keep=np.fromiter((set(s.split('|'))<=variable for s in anchor.member_workers),bool,len(anchor))
            restricted=anchor.loc[keep].reset_index(drop=True)
            for pid,g in anchor[anchor.building.eq(b)].groupby('pool_id'):
                h=restricted[restricted.pool_id.eq(pid)]
                anchor_known=set(maps[family['anchor'],condition,b]['coarse'])&set(maps[family['anchor'],condition,b]['fine'])
                represented=formal_workers[pid]&anchor_known
                u=len(represented&variable);possible=math.comb(u,20) if u>=20 else 0
                status='supported' if len(h)>=2 else ('joint_capacity_lt20' if u<20 else ('only_one_possible_member_set' if possible==1 else 'sampled_support_insufficient'))
                support_rows.append(dict(support_scope=family['scope'],design_anchor=family['anchor'],
                    family='|'.join(family['methods']),heldout_building=b,pool_id=pid,
                    status=status,condition=condition,feature_gate='class_and_source_only' if class_only else 'class_QT_common',image_id=g.image_id.iloc[0],target_panel=g.target_panel.iloc[0],
                    formal_pool_n=len(formal_workers[pid]),anchor_labelled_pool_n=len(represented),class_known_pool_n=len(represented&class_known),
                    joint_supported_pool_n=u,joint_possible_member_sets=str(possible),
                    registered_draws=len(g),supported_draws=len(h),registered_cells=g.cell_id.nunique(),
                    supported_cells=h.cell_id.nunique(),joint_supported_workers=len(variable)))
            if not restricted.building.eq(b).any():continue
            workers=sorted(variable);person_idx={w:i for i,w in enumerate(workers)}
            for method in family['methods']:
                mapping=maps[method,condition,b]
                xx,names=designs(restricted,workers,person_idx,fs,mapping,class_only=class_only)
                fold_rows.append(dict(condition=condition,method_id=method,support_scope=family['scope'],
                    design_anchor=family['anchor'],family='|'.join(family['methods']),heldout_building=b,
                    feature_gate='class_and_source_only' if class_only else 'class_QT_common',variable_workers='|'.join(workers),supported_endpoint_ids_sha256=hashlib.sha256('|'.join(sorted(restricted.team_key)).encode()).hexdigest(),
                    outside_building_maps_used_on_all_training_and_test_pools=True))
                pp,ff,dd=fit_one(restricted,xx,names,b,method,condition,family,mapping['has_fine'])
                family_pools.extend(pp);family_fits.extend(ff);family_den.extend(dd)
        slug=family['scope']+'__'+family['anchor']+'__'+'-'.join(family['methods'])
        if family_pools:
            path=out/(slug+'__POOL_RESULTS.csv.gz');save(pd.concat(family_pools,ignore_index=True),path);parts.append(path)
        if family_fits:save(pd.DataFrame(family_fits),out/(slug+'__FIT_SUPPORT.csv.gz'))
        if family_den:save(pd.DataFrame(family_den),out/(slug+'__OUTCOME_SUPPORT.csv.gz'))
        print('CV completed',condition,slug,flush=True)
        gc.collect()
    save(pd.DataFrame(support_rows),out/'N20_COMMON_SUPPORT.csv')
    save(pd.DataFrame(fold_rows),out/'N20_FOLD_MAPS.csv.gz')
    if not parts:return
    allpool=pd.concat([pd.read_csv(p,low_memory=False) for p in parts],ignore_index=True)
    save(allpool,out/'N20_PREDICTION_POOL_RESULTS.csv.gz')
    prediction_summary(allpool,out)


def prediction_summary(pool,out):
    keys=['condition','method_id','support_scope','design_anchor','family','weighting','outcome','model']
    buildframes=[]
    for panel in ['all','prior_panel','added_images']:
        p=pool if panel=='all' else pool[pool.target_panel.eq(panel)]
        im=p.groupby(keys+['heldout_building','image_id'],dropna=False,as_index=False).agg(
            mse=('mse','mean'),mae=('mae','mean'),null_mse=('null_mse','mean'),draws=('sampled_draws','sum'))
        b=im.groupby(keys+['heldout_building'],dropna=False,as_index=False).agg(
            mse=('mse','mean'),mae=('mae','mean'),null_mse=('null_mse','mean'),images=('image_id','size'),draws=('draws','sum'))
        b['target_panel']=panel;buildframes.append(b)
    building=pd.concat(buildframes,ignore_index=True)
    save(building,out/'N20_PREDICTION_BUILDINGS.csv.gz')
    s=building.groupby(keys+['target_panel'],dropna=False,as_index=False).agg(
        mse=('mse','mean'),mae=('mae','mean'),null_mse=('null_mse','mean'),
        buildings=('heldout_building','size'),images=('images','sum'),draws=('draws','sum'))
    s['R2_relative_to_pool_mean']=np.where(s.null_mse>1e-12,1-s.mse/s.null_mse,np.nan)
    save(s,out/'N20_PREDICTION_SUMMARY.csv')
    contrasts=[]
    pairs=[('coarse_source','source'),('fine_source','source'),('coarse_quadratic_source','source'),('fine_quadratic_source','source'),('fine_source','coarse_source'),('coarse_source','QT_source'),('fine_source','QT_source'),
           ('QT_plus_fine_source','QT_source'),('QT_moments_plus_fine_source','QT_moments_source'),
           ('QT_moments_source','QT_source'),
           ('fine_quadratic_source','coarse_quadratic_source'),
           ('coarse_quadratic_source','QT_moments_team_quadratic_source'),
           ('fine_quadratic_source','QT_moments_team_quadratic_source'),
           ('QT_moments_plus_fine_quadratic_source','QT_moments_team_quadratic_source'),
           ('fine_quadratic_source','fine_source'),
           ('QT_moments_team_quadratic_source','QT_moments_source')]
    group=[k for k in keys if k!='model']+['target_panel']
    for values,g in building.groupby(group,dropna=False):
        wide=g.pivot(index='heldout_building',columns='model',values='mse')
        for new,base in pairs:
            if new not in wide or base not in wide:continue
            x=wide[[new,base]].dropna();gain=x[base]-x[new]
            rng=np.random.default_rng(SEED)
            boot=gain.to_numpy()[rng.integers(len(gain),size=(2000,len(gain)))].mean(axis=1) if len(gain)>1 else np.array([np.nan])
            lo,hi=np.quantile(boot,[.025,.975])
            contrasts.append(dict(zip(group,values),new_model=new,baseline=base,buildings=len(x),
                mse_new=x[new].mean(),mse_baseline=x[base].mean(),mse_gain=gain.mean(),
                relative_mse_gain=gain.mean()/x[base].mean() if x[base].mean()>1e-12 else np.nan,
                positive_buildings=int((gain>1e-12).sum()),negative_buildings=int((gain<-1e-12).sum()),
                bootstrap95_low=lo,bootstrap95_high=hi))
    save(pd.DataFrame(contrasts),out/'N20_PREDICTION_INCREMENT.csv')


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--condition',choices=['manual','semi'],required=True)
    parser.add_argument('--phase',choices=['descriptive','prediction','all'],default='all')
    args=parser.parse_args();out=HERE/args.condition;out.mkdir(exist_ok=True)
    start=time.time()
    frame,cells,scalars,inputs=load(args.condition)
    js(out/'N20_ANALYSIS_CONTRACT.json',dict(
        condition=args.condition,n=20,registered_member_references=len(frame),unique_native_teams=len(scalars),
        vector_cells=len(cells),sources=inputs,design_manifest_sha256=sha(NEXT/'DESIGN_MANIFEST.csv'),
        event_or_geometry_recalculation=False,qualification_changed=False,
        estimands=['configuration_uniform','member_universe_inverse_sampling_estimate'],
        all_vectors_in_registered_design=True,all_members=False,cell_member_draws_max=3,
        prediction_support='Common feature support can remove configurations. Exact per-pool capacity and sampled support are recorded separately; this filtered model is not complete composition coverage.',
        weights='Each original fine/A2 cell: equal cell weight or exact product choose(capacity,count)/registered sample size. Images and buildings equal. Quality conditions on available score; failures use all sampled teams.',
        feature_gate='own_class_supported: only method labels and source are required, no QT gate. For all other comparative families, each team member must have all common method coarse/fine labels and finite four-dimensional outside-building QT. Missing membership is not imputed as class zero.',
        outer_split='Same target-building-excluded personnel label and QT map applied to all training and target pools. Regression scaling/coefficients use buildings other than target.',
        target_centering='Weighted common-support pool mean defines relative member-set response. Not absolute unseen-image prediction.',
        models=['source','QT_source','QT_moments_source','coarse_source','QT_plus_coarse_source',
                'fine_source','QT_plus_fine_source','QT_moments_plus_fine_source','coarse_quadratic_source',
                'fine_quadratic_source','QT_moments_team_quadratic_source','QT_moments_plus_fine_quadratic_source'],
        ridge=PENALTY,hyperparameter_search=False,
        common_new_anchor='Support-driven addition after structural anchor proved sparse; fixed MV new-source design is evaluated without new fusion or outcome-driven selection.',
        quadratic_check='One fixed quadratic expansion of class proportions versus QT mean second-order interactions plus worker moments; actual fold rank recorded, no tuning.',selection='Exploratory fixed extension of retained methods; no new blind test.',
        qt_worker_fields=QT,metrics=OUTCOMES,
        quality_missingness='Missing quality is not zero; per-outcome common support and failure response retained.',
        time='Log of total source seconds only with complete same-clock coverage; not wall-clock parallel time.',
        no_universal_interchangeability_from_configuration_variance=True,
        legacy='Rnew2/F01 keep original legal target buildings; M-grid support is explicit, absence of sampled legal teams is not an effect failure.'))
    if args.phase in ['descriptive','all']:
        validate_universe(cells,out)
        describe(frame,cells,out)
        print('Descriptive checkpoint complete',args.condition,round(time.time()-start,1),flush=True)
    if args.phase in ['prediction','all']:predict(frame,out,args.condition)
    js(out/'N20_ANALYSIS_COMPLETION.json',dict(condition=args.condition,phase=args.phase,
       elapsed_seconds=time.time()-start,files={p.name:{'bytes':p.stat().st_size,'sha256':sha(p)}
       for p in out.iterdir() if p.is_file() and p.name!='N20_ANALYSIS_COMPLETION.json'}))
    print('DONE',args.condition,round(time.time()-start,1),flush=True)


if __name__=='__main__':main()
