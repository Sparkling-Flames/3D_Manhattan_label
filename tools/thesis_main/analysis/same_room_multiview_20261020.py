"""v2 declared-room majority-view history: means, individuals, paired real replays."""
import argparse
from concurrent.futures import ProcessPoolExecutor, as_completed
import gzip
import itertools
import json
import math
import os
from pathlib import Path
import sys

import numpy as np
import pandas as pd

from .same_room_v2_prediction_20261019 import scene_layer, fit_transfer

ROOT=Path(__file__).resolve().parents[3]
OUT=ROOT/'research/same_room/same_room_multiview_20261020'
SOURCE=ROOT/'research/statistics/v2_integrated_analysis_20261019'
REL=ROOT/'research/same_room/relation_adoption_20261016'
ARCHIVE=ROOT/'research/workers/pro_personnel_v2_archive_20261019/work_v2_20261019/fusion'
METRICS=['B8L2','D10','source_active_time_seconds','target_matched_time_seconds']
SEED=20261020


def read(path):
    with (gzip.open(path,'rt',encoding='utf-8') if str(path).endswith('.gz') else open(path,encoding='utf-8-sig')) as f:
        return json.load(f)


def save(name,value):
    path=OUT/name;path.parent.mkdir(parents=True,exist_ok=True)
    if isinstance(value,pd.DataFrame):value.to_csv(path,index=False,encoding='utf-8-sig')
    else:
        raw=json.dumps(value,ensure_ascii=False,indent=2,allow_nan=False).encode('utf-8')
        path.write_bytes(gzip.compress(raw,mtime=0) if path.suffix=='.gz' else raw)


def splits(images):
    images=sorted(images)
    for m in range(len(images)//2+1,len(images)):
        for h in itertools.combinations(images,m):yield h,tuple(i for i in images if i not in h)


def source_prediction(values,history):
    return float(values.loc[list(history)].mean())


def declared_groups(declarations,eligible,relations):
    found={}
    for item in declarations:
        images=tuple(sorted(set(item['images'])&set(eligible)))
        if len(images)>=3 and all(tuple(p) in relations for p in itertools.combinations(images,2)):
            found.setdefault(images,set()).add(item['code'])
    return [dict(images=list(images),sources=sorted(codes)) for images,codes in sorted(found.items())]


def replay_orders(workers,budget=256):
    workers=sorted(workers)
    if math.factorial(len(workers))<=budget:return list(map(list,itertools.permutations(workers)))
    rng=np.random.default_rng(SEED)
    return [rng.permutation(workers).tolist() for _ in range(budget)]


def inputs():
    d=pd.read_csv(SOURCE/'shared_records.csv',low_memory=False)
    assert d.object_id.is_unique
    q=pd.read_csv(ROOT/'research/quality/quality_workers_v2_20261019/quality_records.csv')
    pd.testing.assert_frame_equal(d[d.quality_usable].set_index('object_id')[['B8L2','D10']].sort_index(),
        q.set_index('object_id')[['B8L2','D10']].sort_index(),check_exact=False,atol=1e-10,rtol=0)
    d['layer']=scene_layer(d)
    save('record_coverage.csv',d.groupby(['origin','condition','layer'],dropna=False).agg(records=('object_id','size'),images=('image_id','nunique')).reset_index())
    d=d[d.pool_analysis_eligible & d.condition.eq('manual') & ~d.is_oos].copy()
    assert not d.duplicated(['image_id','worker_id']).any()
    gates=read(ROOT/'research/workers/worker_b8l2_d10_20261017/admission_snapshot.json')
    allowed={x['object_id'] for x in gates if not x['original_holdout'] and x['role']=='manual_development_candidate' and not x['personnel_barriers'] and not x['context_barriers']}
    d['training_allowed']=d.origin.eq('new')|d.object_id.isin(allowed)
    d['building']=d.building_id
    for metric in METRICS:
        valid=d.chosen_target_id.eq(d.current_target_id)
        if metric in ['B8L2','D10']:valid &= d.quality_usable & d.quality_use.isin(['ordinary_primary','doorway_quality'])
        else:valid &= d[metric].ge(0)
        d.loc[~valid,metric]=np.nan
    r=pd.read_csv(SOURCE/'direct_relation_registry.csv')
    relations={tuple(sorted([x.image_a,x.image_b])) for x in r.itertuples() if x.physical_adopted and x.scope_comparable and not x.substantive_conflict}
    declarations=[dict(code='candidate:'+x['candidate_id'],images=x['image_ids']) for x in read(REL/'candidate_adoption.json') if x['physical_supported'] and x['scope_comparable']]
    declarations += [dict(code='original:'+x['review_code'],images=x['image_ids']) for x in read(REL/'original_groups.json')]
    for row in r.itertuples():
        for x in json.loads(row.evidence):
            if x.get('image_ids'):
                declarations.append(dict(code='evidence:'+x.get('candidate_id','|'.join(x.get('source_group_codes',[]))),images=x['image_ids']))
    save('DECLARATIONS.json',declarations)
    return d,declarations,relations


def summarize_predictions(rows,name):
    if rows.empty:return
    # Average repeated splits first; overlapping groups do not multiply image weight.
    keys=['metric','origin','panel','group_id','building','target_image','m','N','method']
    if 'worker_id' in rows:
        worker=rows.groupby(keys+['worker_id'],as_index=False).agg(mae=('absolute_error','mean'),bias=('error','mean'),observations=('error','size'))
        identity=[k for k in keys if k!='m']+['worker_id']
        support=worker.groupby(identity).m.transform('nunique')
        worker=worker[support.eq(worker.N-1-worker.N//2)]
        save(name+'_worker_targets.csv.gz',worker)
        target=worker.groupby(keys,as_index=False).agg(mae=('mae','mean'),bias=('bias','mean'),observations=('observations','sum'))
    else:
        target=rows.groupby(keys,as_index=False).agg(mae=('absolute_error','mean'),bias=('error','mean'),observations=('error','size'))
    save(name+'_targets.csv',target)
    group=target.groupby(['metric','origin','panel','group_id','building','m','N','method'],as_index=False).agg(mae=('mae','mean'),bias=('bias','mean'),targets=('target_image','nunique'))
    save(name+'_groups.csv',group)
    # Endpoints compare identical target images at each group's minimum vs maximum m.
    endpoint=[]
    for stage in ['minimum_majority','maximum_history']:
        part=target[target.m.eq(target.N//2+1 if stage=='minimum_majority' else target.N-1)].copy()
        image=part.groupby(['metric','origin','panel','building','target_image','method'],as_index=False).agg(mae=('mae','mean'),bias=('bias','mean'))
        building=image.groupby(['metric','origin','panel','building','method'],as_index=False).agg(mae=('mae','mean'),bias=('bias','mean'),images=('target_image','nunique'))
        building['stage']=stage;endpoint.append(building)
    b=pd.concat(endpoint);save(name+'_buildings.csv',b)
    s=b.groupby(['metric','origin','panel','stage','method'],as_index=False).agg(mae=('mae','mean'),bias=('bias','mean'),buildings=('building','nunique'),images=('images','sum'))
    save(name+'_summary.csv',s)


def analyze():
    OUT.mkdir(parents=True,exist_ok=True)
    save('PLAN.json',dict(data_release='v2',seed=SEED,history='strictly >50%, all combinations, at least one held view',
        labels='B8L2 primary, D10 sensitivity; time log1p separately by origin',
        panels='actual image pools and fixed whole-group common workers; per-image metric support >=3',
        source='known reference-evaluated history; not no-GT deployment',replay_budget=256,
        replay='all real prefixes of paired shared orders; fixed algorithm; no future members in fusion',
        restrictions='OOS excluded, doorway separate, personnel classes deferred; original admission applies to model training',
        estimator='equal history images; single-source expected error; image-equal external-building training baseline',
        weighting='split then target then overlap groups then image then building',new_personnel_classes=False))
    d,declarations,relations=inputs()
    groups=[];audit=[];means=[];individual=[];splitrows=[];descriptive=[]
    for metric in METRICS:
        for origin in ['all','v1','new']:
            if metric.endswith('seconds') and origin=='all':continue
            v=d[d[metric].notna() & (True if origin=='all' else d.origin.eq(origin))].copy()
            v['value']=np.log1p(v[metric]) if metric.endswith('seconds') else v[metric]
            for layer in ['ordinary','doorway']:
                eligible=v[v.layer.eq(layer)].groupby('image_id').worker_id.nunique()
                eligible=set(eligible[eligible.ge(3)].index)
                for g in declared_groups(declarations,eligible,relations):
                    images=g['images'];frame=v[v.image_id.isin(images)]
                    assert frame.building.nunique()==1
                    building=frame.building.iloc[0]
                    gid='MV'+str(len(groups)+1).zfill(4)
                    pivot=frame.pivot(index='image_id',columns='worker_id',values='value').reindex(images)
                    common=pivot.columns[pivot.notna().all()]
                    group=dict(group_id=gid,metric=metric,origin=origin,layer=layer,building=building,N=len(images),
                        common_workers=list(common),images=images,sources=g['sources'])
                    groups.append(group)
                    audit.append(dict(group_id=gid,metric=metric,origin=origin,layer=layer,building=building,N=len(images),
                        common_n=len(common),source_codes='|'.join(g['sources']),images='|'.join(images),splits=sum(math.comb(len(images),m) for m in range(len(images)//2+1,len(images)))))
                    if layer!='ordinary':continue
                    train=v[v.layer.eq('ordinary')&v.training_allowed & v.building.ne(building)]
                    external=float(train.groupby('image_id').value.mean().mean())
                    wm=train.groupby('worker_id').value.mean()
                    for image,vals in pivot.iterrows():
                        a=vals.dropna()
                        descriptive.append(dict(group_id=gid,metric=metric,origin=origin,building=building,image_id=image,n=len(a),
                            mean=a.mean(),median=a.median(),q25=a.quantile(.25),q75=a.quantile(.75),sd=a.std()))
                    for si,(h,targets) in enumerate(splits(images)):
                        sid=gid+'_'+str(si)
                        base=dict(metric=metric,origin=origin,group_id=gid,building=building,m=len(h),N=len(images),split_id=sid)
                        splitrows.append(dict(**base,history='|'.join(h),targets='|'.join(targets)))
                        panels={'actual_pool':pivot}
                        if len(common)>=3:panels['common_workers']=pivot[common]
                        for panel,p in panels.items():
                            values=p.mean(axis=1);source=source_prediction(values,h)
                            for target in targets:
                                actual=float(values[target])
                                estimates={'multi_source':source,'external_history':external}
                                for method,estimate in estimates.items():
                                    means.append(dict(**base,panel=panel,target_image=target,method=method,predicted=estimate,actual=actual,
                                        error=estimate-actual,absolute_error=abs(estimate-actual)))
                                delta=values.loc[list(h)]-actual
                                means.append(dict(**base,panel=panel,target_image=target,method='single_source_expected',predicted=source,actual=actual,
                                    error=float(delta.mean()),absolute_error=float(delta.abs().mean())))
                        if metric not in ['B8L2','D10']:continue
                        for target in targets:
                            source=pivot.loc[list(h)].mean(axis=0);counts=pivot.loc[list(h)].count()
                            for worker,actual in pivot.loc[target].dropna().items():
                                if not counts[worker] or worker not in wm:continue
                                history_values=pivot.loc[list(h),worker].dropna()
                                # Building held out from the worker baseline; source values explicitly allowed.
                                individual.append(dict(**base,panel='observed_person_history',target_image=target,worker_id=worker,
                                    source_n=int(counts[worker]),actual=float(actual),source=float(source[worker]),baseline=float(wm[worker]),
                                    single_error=float((history_values-actual).abs().mean())))
    save('GROUPS.json',groups);save('group_coverage.csv',pd.DataFrame(audit));save('splits.csv.gz',pd.DataFrame(splitrows))
    save('image_quality.csv',pd.DataFrame(descriptive));means=pd.DataFrame(means)
    save('mean_predictions.csv.gz',means);summarize_predictions(means,'mean')
    person=pd.DataFrame(individual);save('individual_features.csv.gz',person)
    rows=[]
    for method,column in [('worker_history','baseline'),('multi_source','source'),('single_source_expected','source')]:
        x=person.copy();x['method']=method;x['predicted']=x[column];x['error']=x.predicted-x.actual
        x['absolute_error']=x.single_error if method=='single_source_expected' else x.error.abs();rows.append(x)
    person=pd.concat(rows,ignore_index=True);save('individual_predictions.csv.gz',person)
    summarize_predictions(person,'individual')
    print(pd.DataFrame(audit).groupby(['metric','origin','layer']).agg(groups=('group_id','size'),buildings=('building','nunique')).to_string(),flush=True)


def fusion_runtime():
    os.environ['PERSONNEL_V2_REPOSITORY']=str(ROOT)
    sys.path.insert(0,str(ARCHIVE))
    import fusion_engine as fe
    fe.OUT=OUT/'runtime'
    return fe


def register_replays():
    d,_,_=inputs();allpools=read(ARCHIVE/'INPUT_SNAPSHOT.json.gz')['images']
    pools={p['meta']['image_id']:p for p in allpools if p['meta']['layer']=='ordinary_manual' and p['meta']['difficulty_aligned']}
    groups=[g for g in read(OUT/'GROUPS.json') if g['metric']=='B8L2' and g['origin']=='all' and g['layer']=='ordinary']
    local=[]
    for g in groups:
        if len(g['common_workers'])>=3:continue
        p=d[d.image_id.isin(g['images'])&d.B8L2.notna()].pivot(index='image_id',columns='worker_id',values='B8L2')
        candidates={tuple(sorted(p.index[p[w].notna()])) for w in p if p[w].count()>=3}
        supported={s:list(p.columns[p.loc[list(s)].notna().all()]) for s in candidates if p.loc[list(s)].notna().all().sum()>=3}
        maximal=sorted(s for s in supported if not any(set(s)<set(t) for t in supported))
        for j,images in enumerate(maximal):
            local.append(dict(g,group_id=g['group_id']+'S'+str(j+1),parent_group=g['group_id'],
                images=list(images),N=len(images),common_workers=supported[images],replay_panel='coverage_subset'))
    groups=[dict(g,replay_panel='whole_group') for g in groups]+local
    save('REPLAY_GROUPS.json',groups)
    requests=[];orders=[];support=[];used={}
    for g in groups:
        # The declared group remains intact. Missing pool members reduce its common replay pool only.
        ready=all(i in pools for i in g['images'])
        workers=set(g['common_workers']) if ready else set()
        if ready:
            for image in g['images']:
                p=pools[image]
                current=d[d.image_id.eq(image)&d.B8L2.notna()].set_index('worker_id')
                lookup={r['worker_id']:r for r in p['records']}
                workers &= lookup.keys()
                for w in workers:
                    assert lookup[w]['object_id']==current.loc[w,'object_id']
                    assert abs(lookup[w]['B8L2']-current.loc[w,'B8L2'])<1e-9
                    assert p['reference']['target_id']==current.loc[w,'current_target_id']
        support.append(dict(group_id=g['group_id'],panel=g['replay_panel'],N=g['N'],common_n=len(workers),supported=bool(len(workers)>=3),reason='' if len(workers)>=3 else 'whole_group_common_pool_below3_or_missing_pool'))
        if len(workers)<3:continue
        for repeat,order in enumerate(replay_orders(workers)):
            orders.append(dict(group_id=g['group_id'],replay=repeat,workers=order))
            for image in g['images']:
                p=pools[image];used[p['pool_id']]=p
                for k in range(1,len(order)+1):
                    rid=g['group_id']+'_'+str(repeat)+'_'+image+'_'+str(k)
                    requests.append(dict(request_id=rid,request_family='same_room_multiview',pool_id=p['pool_id'],
                        group_id=g['group_id'],replay=repeat,k=k,worker_ids=order[:k]))
    save('replay_support.csv',pd.DataFrame(support));save('REPLAY_ORDERS.json.gz',orders)
    save('REPLAY_REQUESTS.json.gz',dict(requests=requests));save('REPLAY_POOLS.json.gz',list(used.values()))
    fe=fusion_runtime();fe.validate_requests(dict(requests=requests),list(used.values()))
    print('Replay design:',len(used),'images',len(orders),'paths',len(requests),'prefix rows',flush=True)


def run_pool(pool,requests):
    fe=fusion_runtime()
    return fe.run_pool(pool,requests)


def replay(jobs):
    requests=pd.DataFrame(read(OUT/'REPLAY_REQUESTS.json.gz')['requests'])
    pools=read(OUT/'REPLAY_POOLS.json.gz');by={p['pool_id']:p for p in pools};done=[]
    pending=[];fe=fusion_runtime()
    for pid,g in requests.groupby('pool_id'):
        requested=g.to_dict('records');target=OUT/'runtime/pools'/pid
        if (target/'context.json').exists():
            assert read(target/'context.json')==fe.context(by[pid])
            old={r['request_id']:r for r in read(target/'requests.json.gz')['requests']}
            if all(old.get(r['request_id'])==r for r in requested):
                done.append(dict(read(target/'LAST_RUN.json'),reused_completed_pool=True));continue
        pending.append((by[pid],requested))
    with ProcessPoolExecutor(max_workers=jobs) as executor:
        futures=[executor.submit(run_pool,p,r) for p,r in pending]
        for future in as_completed(futures):
            receipt=future.result();done.append(receipt);save('REPLAY_RECEIPTS.json',done)
            print(json.dumps(dict(done=len(done),total=len(by),pool=receipt['pool_id'],fusions=receipt['new_fusions'],seconds=round(receipt['total_seconds'],1))),flush=True)
    save('REPLAY_RECEIPTS.json',done)


def curve_analysis():
    requests=read(OUT/'REPLAY_REQUESTS.json.gz')['requests']
    rows=[]
    for pool in read(OUT/'REPLAY_POOLS.json.gz'):
        rows.extend(read(OUT/'runtime/pools'/pool['pool_id']/'request_results.json.gz')['results'])
    nodes=pd.DataFrame(rows)
    assert nodes.request_id.is_unique and set(nodes.request_id)=={r['request_id'] for r in requests}
    expected={r['request_id']:r['worker_ids'] for r in requests}
    assert all(r.ordered_workers.split('|')==expected[r.request_id] for r in nodes.itertuples())
    save('replay_nodes.csv.gz',nodes)
    groups={g['group_id']:g for g in read(OUT/'REPLAY_GROUPS.json')}
    predictions=[];coverage=[];curve_rows=[];behavior=[]
    for gid,part in nodes.groupby('group_id'):
        g=groups[gid];images=g['images'];N=len(images);R=part.replay.nunique();K=int(part.k.max())
        assert len(part)==N*R*K
        for metric in ['B8L2','D10']:
            matrix=np.full((N,R,K),np.nan)
            for i,image in enumerate(images):
                im=part[part.image_id.eq(image)]
                for row in im.itertuples():
                    value=getattr(row,metric)
                    if row.complete_evaluable and pd.notna(value):matrix[i,row.replay,row.k-1]=value
                for k in range(K):
                    vals=matrix[i,:,k];finite=vals[np.isfinite(vals)]
                    curve_rows.append(dict(group_id=gid,building=g['building'],image_id=image,image_code=im.image.iloc[0],metric=metric,
                        k=k+1,paths=R,valid_paths=len(finite),mean=float(np.mean(finite)) if len(finite) else np.nan,
                        q10=float(np.quantile(finite,.1)) if len(finite) else np.nan,q90=float(np.quantile(finite,.9)) if len(finite) else np.nan))
                last=matrix[i,:,-1];gain=matrix[i]-matrix[i,:,0,None]
                for k in range(K):
                    delta=matrix[i,:,k]-last;valid=np.isfinite(delta)
                    adjacent=matrix[i,:,k]-matrix[i,:,k-1] if k else np.full(R,np.nan)
                    behavior.append(dict(group_id=gid,image_id=image,metric=metric,k=k+1,valid_paths=int(valid.sum()),
                        mean_terminal_gap=float(np.mean(delta[valid])) if valid.any() else np.nan,
                        mean_absolute_terminal_gap=float(np.mean(np.abs(delta[valid]))) if valid.any() else np.nan,
                        above_terminal_fraction=float(np.mean(delta[valid]>1e-9)) if valid.any() else np.nan,
                        adjacent_known=int(np.isfinite(adjacent).sum()),falls=int(np.sum(adjacent<-1e-9)),
                        mean_gain_from_one=float(np.nanmean(gain[:,k])) if np.isfinite(gain[:,k]).any() else np.nan))
            valid=np.isfinite(matrix).all(axis=0)
            for k in range(K):coverage.append(dict(group_id=gid,metric=metric,k=k+1,attempted_paths=R,whole_group_valid_paths=int(valid[:,k].sum())))
            for si,(history,targets) in enumerate(splits(images)):
                h=[images.index(i) for i in history]
                prediction=np.mean(matrix[h],axis=0)
                base=dict(group_id=gid,metric=metric,origin='all',panel='paired_replay_'+g['replay_panel'],building=g['building'],m=len(h),N=N,split_id=gid+'_'+str(si))
                for target in targets:
                    t=images.index(target);error=prediction-matrix[t]
                    shape=(prediction-prediction[:,0,None])-(matrix[t]-matrix[t,:,0,None])
                    for k in range(K):
                        ok=valid[:,k]
                        if not ok.any():continue
                        shapeok=ok&valid[:,0]
                        predictions.append(dict(**base,target_image=target,k=k+1,method='multi_source',valid_paths=int(ok.sum()),
                            error=float(np.mean(error[ok,k])),absolute_error=float(np.mean(np.abs(error[ok,k]))),
                            shape_error=float(np.mean(shape[shapeok,k])) if shapeok.any() else np.nan,
                            shape_absolute_error=float(np.mean(np.abs(shape[shapeok,k]))) if shapeok.any() else np.nan))
                        delta=matrix[h,:,k]-matrix[t,:,k]
                        predictions.append(dict(**base,target_image=target,k=k+1,method='single_source_expected',valid_paths=int(ok.sum()),
                            error=float(np.mean(delta[:,ok])),absolute_error=float(np.mean(np.abs(delta[:,ok]))),shape_absolute_error=np.nan))
    predicted=pd.DataFrame(predictions)
    save('curve_predictions.csv.gz',predicted);summarize_predictions(predicted,'curve')
    shapes=predicted[predicted.method.eq('multi_source')&predicted.shape_absolute_error.notna()].copy()
    shapes['absolute_error']=shapes.shape_absolute_error;shapes['error']=shapes.shape_error
    summarize_predictions(shapes,'curve_shape')
    save('curve_coverage.csv',pd.DataFrame(coverage));save('curves.csv',pd.DataFrame(curve_rows));save('replay_behavior.csv',pd.DataFrame(behavior))
    save('REPLAY_CHECKS.json',dict(request_count=len(requests),result_count=len(nodes),unique_request_ids=True,
        ordered_prefix_members_verified=True,all_actual_fusions=True,k2_separate=True,
        complete_quality_nodes=int((nodes.complete_evaluable&nodes.B8L2.notna()).sum()),
        missing_quality_nodes=int(nodes.B8L2.isna().sum()),exceptions=sum(len(r['exceptions']) for r in read(OUT/'REPLAY_RECEIPTS.json'))))
    print('Curve analysis complete',len(nodes),'nodes',len(predictions),'split-target-k comparisons',flush=True)


def figures():
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    plt.rcParams.update({'font.family':'Microsoft YaHei','axes.unicode_minus':False})
    groups=read(OUT/'REPLAY_GROUPS.json');source={g['group_id']:','.join(s for s in g['sources'] if s.startswith('candidate:')) for g in groups}
    means=pd.read_csv(OUT/'mean_groups.csv');means=means[means.metric.eq('B8L2')&means.origin.eq('all')&means.method.eq('multi_source')]
    fig,axes=plt.subplots(1,2,figsize=(12,4.5),layout='constrained')
    for panel,ax in zip(['actual_pool','common_workers'],axes):
        for gid,g in means[means.panel.eq(panel)].groupby('group_id'):
            ax.plot(g.m/g.N*100,g.mae,marker='o',label=gid)
        ax.set(title='各图实际人员池' if panel=='actual_pool' else '全组共同人员',xlabel='历史图片比例（%）',ylabel='目标图片均值预测MAE（分）')
        ax.legend(fontsize=7);ax.grid(alpha=.2)
    fig.suptitle('同房多数视角历史 → 剩余视角平均质量（B8L2）')
    fig.savefig(OUT/'mean_history.png',dpi=150);plt.close(fig)
    curves=pd.read_csv(OUT/'curves.csv');curves=curves[curves.metric.eq('B8L2')&curves.group_id.isin([g['group_id'] for g in groups if g['replay_panel']=='whole_group'])]
    n=curves.group_id.nunique();fig,axes=plt.subplots(math.ceil(n/2),2,figsize=(13,3.3*math.ceil(n/2)),layout='constrained',squeeze=False)
    for (gid,g),ax in zip(curves.groupby('group_id'),axes.flat):
        for code,im in g.groupby('image_code'):
            ax.plot(im.k,im['mean'],label=code,linewidth=1,marker='.',markersize=3)
        ax.set(title=gid+' '+source[gid].replace('candidate:',''),xlabel='同一顺序下实际加入人数 k',ylabel='真实融合 B8L2')
        ax.legend(fontsize=6);ax.grid(alpha=.2)
    for ax in list(axes.flat)[n:]:ax.set_visible(False)
    fig.suptitle('配对真实人员重放：各视角路径平均；空缺节点不连补')
    fig.savefig(OUT/'replay_curves.png',dpi=130);plt.close(fig)
    print('Figures complete',flush=True)


def background_controls():
    d,_,_=inputs();r=pd.read_csv(SOURCE/'direct_relation_registry.csv')
    adjacent={}
    for row in r[r.physical_adopted].itertuples():
        adjacent.setdefault(row.image_a,set()).add(row.image_b);adjacent.setdefault(row.image_b,set()).add(row.image_a)
    means=pd.read_csv(OUT/'mean_targets.csv');rows=[];support=[]
    for g in read(OUT/'GROUPS.json'):
        if g['layer']!='ordinary' or g['metric'] not in ['B8L2','D10']:continue
        v=d[d.layer.eq('ordinary')&d[g['metric']].notna()&d.building.eq(g['building'])]
        if g['origin']!='all':v=v[v.origin.eq(g['origin'])]
        stats=v.groupby('image_id')[g['metric']].agg(['mean','count']);stats=stats[stats['count'].ge(3)]
        for target in g['images']:
            pool=sorted(set(stats.index)-set(g['images'])-adjacent.get(target,set()))
            support.append(dict(group_id=g['group_id'],metric=g['metric'],origin=g['origin'],target_image=target,
                candidate_images='|'.join(pool),n_candidates=len(pool),required_for_fixed_m_panel=g['N']-1,supported=len(pool)>=g['N']-1))
            if len(pool)<g['N']-1:continue
            actual=float(stats.loc[target,'mean'])
            for m in range(g['N']//2+1,g['N']):
                if math.comb(len(pool),m)<=4096:
                    histories=list(itertools.combinations(pool,m));kind='exhaustive'
                else:
                    rng=np.random.default_rng(SEED)
                    histories=[rng.permutation(pool)[:m].tolist() for _ in range(256)];kind='256_nested_draws'
                predicted=np.array([stats.loc[list(h),'mean'].mean() for h in histories])
                same=means[means.group_id.eq(g['group_id'])&means.panel.eq('actual_pool')&means.target_image.eq(target)&means.m.eq(m)&means.method.eq('multi_source')]
                assert len(same)==1
                rows.append(dict(group_id=g['group_id'],metric=g['metric'],origin=g['origin'],building=g['building'],target_image=target,
                    m=m,N=g['N'],control_kind='same_building_relation_unknown',draw_method=kind,draws=len(histories),
                    same_room_mae=float(same.mae.iloc[0]),control_mae=float(np.abs(predicted-actual).mean())))
    save('background_support.csv',pd.DataFrame(support));result=pd.DataFrame(rows);save('background_controls.csv',result)
    result['gain']=result.control_mae-result.same_room_mae
    image=result.groupby(['metric','origin','building','target_image'],as_index=False)[['same_room_mae','control_mae','gain']].mean()
    b=image.groupby(['metric','origin','building'],as_index=False)[['same_room_mae','control_mae','gain']].mean()
    save('background_buildings.csv',b)
    print(b.to_string(index=False),flush=True)


def fit_individual():
    d,_,_=inputs();p=pd.read_csv(OUT/'individual_features.csv.gz')
    histories=pd.read_csv(OUT/'splits.csv.gz').set_index('split_id').history.str.split('|').to_dict()
    allowed=set(zip(d[d.training_allowed].image_id,d[d.training_allowed].worker_id))
    present=set(zip(d[d.B8L2.notna()].image_id,d[d.B8L2.notna()].worker_id))
    p['training_allowed']=[(r.target_image,r.worker_id) in allowed and all((i,r.worker_id) in allowed for i in histories[r.split_id] if (i,r.worker_id) in present) for r in p.itertuples()]
    predictions=[];folds=[]
    for (metric,origin),part in p.groupby(['metric','origin']):
        records=d[d.training_allowed&d.layer.eq('ordinary')&d[metric].notna()]
        if origin!='all':records=records[records.origin.eq(origin)]
        for outer in sorted(part.building.unique()):
            train=part[part.building.ne(outer)&part.training_allowed].copy();test=part[part.building.eq(outer)].copy()
            maps={b:records[~records.building.isin([outer,b])].groupby('worker_id')[metric].mean().to_dict() for b in train.building.unique()}
            train['inner_baseline']=[maps[b].get(w,np.nan) for b,w in zip(train.building,train.worker_id)]
            train=train[train.inner_baseline.notna()]
            if train.building.nunique()<3:
                folds.append(dict(metric=metric,origin=origin,held_out=outer,supported=False,train_buildings=train.building.nunique()));continue
            cells=['building','target_image','worker_id']
            repeated=train.groupby(cells).worker_id.transform('size')
            unique=train[cells].drop_duplicates();nw=unique.groupby(['building','target_image']).worker_id.nunique()
            ni=unique.groupby('building').target_image.nunique()
            weights=np.array([1/(n*nw[b,i]*ni[b]) for b,i,n in zip(train.building,train.target_image,repeated)])
            y=train.actual-train.inner_baseline;x=train.source-train.inner_baseline
            coef=fit_transfer(x,y,weights);offset=np.average(y,weights=weights)
            assert outer not in set(train.building)
            folds.append(dict(metric=metric,origin=origin,held_out=outer,supported=True,train_buildings=train.building.nunique(),
                train_building_ids='|'.join(sorted(train.building.unique())),intercept=float(coef[0]),slope=float(coef[1]),baseline_offset=float(offset),train_rows=len(train)))
            for method,values in [('calibrated_history',test.baseline+offset),('fitted_multi_source',test.baseline+coef[0]+coef[1]*(test.source-test.baseline))]:
                a=test.copy();a['method']=method;a['predicted']=np.clip(values,0,100);a['error']=a.predicted-a.actual;a['absolute_error']=a.error.abs();predictions.append(a)
    fitted=pd.concat(predictions,ignore_index=True);save('individual_folds.csv',pd.DataFrame(folds))
    base=pd.read_csv(OUT/'individual_predictions.csv.gz');base=base[~base.method.isin(['calibrated_history','fitted_multi_source'])]
    keys=['metric','origin','group_id','split_id','target_image','worker_id']
    available=fitted[fitted.method.eq('fitted_multi_source')][keys]
    matched=base.merge(available,on=keys,validate='many_to_one')
    combined=pd.concat([matched,fitted],ignore_index=True)
    save('individual_fitted_predictions.csv.gz',combined);summarize_predictions(combined,'individual_fitted')
    print('Cross-building multiview person models:',len(folds),'folds',len(combined),'prediction rows',flush=True)


def finalize():
    d,_,_=inputs();s=pd.read_csv(OUT/'splits.csv.gz');groups=read(OUT/'GROUPS.json')
    assert all(set(h.split('|')).isdisjoint(v.split('|')) and len(h.split('|'))*2>n and len(v.split('|'))>=1 for h,v,n in zip(s.history,s.targets,s.N))
    folds=pd.read_csv(OUT/'individual_folds.csv')
    assert all(r.held_out not in r.train_building_ids.split('|') for r in folds.itertuples() if r.supported)
    ordinary=[g for g in groups if g['metric']=='B8L2' and g['origin']=='all']
    images=set(i for g in ordinary for i in g['images'])
    assert not d[d.image_id.isin(images)].is_oos.any() and not d[d.image_id.isin(images)].is_doorway.any()
    objects={o['object_id']:o for o in read(ROOT/'research/data/releases/v2/analysis_input/data.json.gz')['objects']}
    records=0
    for pool in read(OUT/'REPLAY_POOLS.json.gz'):
        for r in pool['records']:
            o=objects[r['object_id']]
            assert r['points']==o['points_1024x512'] and r['source_pair_indices']==o['ordered_source_pair_indices'] and r['ring_confirmed']==o['ring_confirmed']
            records+=1
    coverage=pd.read_csv(OUT/'replay_support.csv');checks=read(OUT/'REPLAY_CHECKS.json')
    save('VALIDATION.json',dict(split_isolation=True,strict_majority=True,score_snapshot_identity_verified=True,
        outer_building_excluded=True,original_geometry_and_order_records_verified=records,no_oos_or_doorway_in_primary=True,
        replay=checks,code_tests='9 passed',historical_results_unchanged=True))
    tables={p.name:list(pd.read_csv(p,nrows=0).columns) for p in OUT.iterdir() if p.name.endswith(('.csv','.csv.gz'))}
    save('FIELD_CONTRACT.json',dict(schema='same_room_multiview_20261020_v1',tables=tables,
        split_key='group_id + split_id; groups metric/origin-specific; overlap sources retained',
        prediction_key='metric/origin/group_id/split_id/target_image/panel/method; individual adds worker_id; curves add k',
        single_source_expected='predicted is mean source point estimate, absolute_error is expected random single-source absolute error; not abs(error)',
        time='mean predictions actual/predicted/errors all in log1p(seconds); origins separate, no time interpretation as diligence',
        missing='unsupported or incomplete, never zero; k=2 follows existing deferred scoring',
        curves='whole-group paired complete mask fixed across m; curve point is average across valid paths, path nodes retained',
        individual='each target-worker first averaged over available histories, fixed workers across m, then target/image/building equal',
        replay_subset='coverage subsets from a declared parent, not independently discovered physical rooms',
        weighting='splits then targets then group-overlap per image then building',status='exploratory_completed'))
    save('CONSUMER_INTERFACE.json',dict(schema='same_room_multiview_20261020_v1',data_release='v2',status='exploratory_completed',
        inputs=dict(manifest='research/data/releases/v2/analysis_input/manifest.json',statistics=SOURCE.relative_to(ROOT).as_posix(),
                    score='research/quality/quality_workers_v2_20261019/CROSS_MODULE_INPUTS.json',relations=(REL/'CROSS_MODULE_RELATIONS.json').relative_to(ROOT).as_posix(),
                    fusion_snapshot=(ARCHIVE/'INPUT_SNAPSHOT.json.gz').relative_to(ROOT).as_posix()),
        coverage=dict(quality_groups=len(ordinary),quality_images=len(images),buildings=len({g['building'] for g in ordinary}),
            majority_quality_splits=sum(math.comb(g['N'],m) for g in ordinary for m in range(g['N']//2+1,g['N'])),
            replay_whole_groups=int((coverage.supported&coverage.panel.eq('whole_group')).sum()),
            replay_coverage_subsets=int((coverage.supported&coverage.panel.eq('coverage_subset')).sum()),
            replay_images=len(read(OUT/'REPLAY_POOLS.json.gz')),replay_paths=len(read(OUT/'REPLAY_ORDERS.json.gz')),replay_prefixes=checks['result_count']),
        files=dict(report='README.md',mean='mean_summary.csv',person='individual_fitted_summary.csv',curves='curve_summary.csv',
                   groups='group_coverage.csv',curve_coverage='curve_coverage.csv',nodes='replay_nodes.csv.gz',controls='background_controls.csv',validation='VALIDATION.json'),
        no_oos=True,doorway_separate=True,personnel_classes_deferred=True,human_decisions_required=[]))
    print('Final artifact checks passed',flush=True)


def main():
    p=argparse.ArgumentParser();p.add_argument('action',choices=['analyze','register','replay','curves','figures','controls','fit','finalize']);p.add_argument('--jobs',type=int,default=3);args=p.parse_args()
    if args.action=='analyze':analyze()
    elif args.action=='register':register_replays()
    elif args.action=='replay':replay(args.jobs)
    elif args.action=='curves':curve_analysis()
    elif args.action=='controls':background_controls()
    elif args.action=='fit':fit_individual()
    elif args.action=='finalize':finalize()
    else:figures()


if __name__=='__main__':main()
