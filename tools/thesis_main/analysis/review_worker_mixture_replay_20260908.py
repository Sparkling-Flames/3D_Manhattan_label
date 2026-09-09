"""人员组合回放的独立覆盖、统计与审查；不生成或更改真人响应。"""
from __future__ import annotations
import argparse
import csv
import gzip
import json
import math
from collections import defaultdict, Counter
from functools import lru_cache
from itertools import combinations, groupby
from pathlib import Path
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / 'analysis_results/worker_mixture_replay_20260908_v1'
BASE = ROOT / 'analysis_results/uncertainty_cloud_inputs_20260906_v1'
WORKERS = ROOT / 'analysis_results/worker_evidence_strata_20260908_v1'
OLD = ROOT / 'analysis_results/building_convergence_evidence_20260908_v1/core'
ARMS = ['A_only', 'AB_balanced', 'B_only', 'random_AB']
METHODS = ['A_only', 'balanced_AB', 'B_only', 'random_AB_pool']
MEASURES = ['pairwise_distance_mean','pairwise_distance_max','cluster_count','supported_historical_cluster_count',
            'singleton_response_fraction','training_entropy','historical_largest_share','distribution_tv',
            'validation_outside_fraction','validation_ambiguous_fraction','unique_indicator','non_unique_indicator','truncated_indicator']


def read(path):
    return pd.read_csv(path, dtype=str, keep_default_na=False)


def candidate_counts(a, b, unknown, n):
    if n not in [2, 4] or min(a, b, unknown) < 0:
        raise ValueError('invalid_composition_counts')
    choose = lambda m, k: math.comb(m, k) if m >= k else 0
    return dict(A_only=choose(a, n), AB_balanced=choose(a, n//2)*choose(b, n//2),
                B_only=choose(b, n), random_AB=choose(a+b, n), random_all=choose(a+b+unknown, n))


def check_profile(row):
    if row['fold'] == 'full' or row['fold'] in json.loads(row['training_buildings']):
        raise ValueError('target_in_training')
    if row['label'] not in ['high', 'low', 'uncertain', 'insufficient']:
        raise ValueError('unknown_profile_label')
    if row['fit_status'] != 'usable':
        return 'unknown'
    return {'high': 'A', 'low': 'B'}.get(row['label'], 'unknown')


def paired_summary(data, arms):
    """相同context/划分配对后，先图内平均，再楼内平均，最后楼等权。"""
    keys = ['building_id', 'context_key', 'split_id']
    if data.duplicated(keys + ['arm']).any():
        raise ValueError('duplicate_arm_observation')
    wide = data.pivot(index=keys, columns='arm', values='value').reindex(columns=arms)
    common = wide.replace([np.inf, -np.inf], np.nan).dropna().reset_index()
    if common.empty:
        return dict(paired_splits=0, paired_contexts=0, paired_buildings=0, means={a: np.nan for a in arms})
    contexts = common.groupby(['building_id', 'context_key'])[arms].mean()
    buildings = contexts.groupby('building_id')[arms].mean()
    return dict(paired_splits=len(common), paired_contexts=len(contexts), paired_buildings=len(buildings),
                means=buildings.mean().to_dict())


def coverage():
    out = OUT/'review'; out.mkdir(parents=True, exist_ok=True)
    a = read(BASE/'annotations.csv.gz')
    assert len(a) == 2501 and a.canonical_annotation_id.is_unique
    ids = a.set_index('canonical_annotation_id').to_dict('index')
    profiles = read(WORKERS/'worker_profiles_all_folds.csv.gz')
    p = profiles[(profiles.stage == 'C1') & (profiles.raw_condition == 'manual') &
                 (profiles.metric == 'corner_pair_count') & (profiles.reading == 'raw_point_count') &
                 (profiles.representation == 'not_applicable') & (profiles.cohort == 'available') &
                 (profiles.fold != 'full')].copy()
    assert not p.duplicated(['fold', 'worker_id']).any()
    assert p.groupby('fold').component.nunique().max() == 1
    p['group'] = [check_profile(r) for r in p.to_dict('records')]
    groups = {(r['fold'], r['worker_id']): r['group'] for r in p.to_dict('records')}
    p.to_csv(out/'independent_fold_profiles.csv', index=False)
    target = a[(a.stage == 'C1') & (a.raw_condition == 'manual')]
    source = read(OLD/'split_support.csv.gz')
    source = source[(source.stage == 'C1') & (source.raw_condition == 'manual')]
    rows = []
    for s in source.to_dict('records'):
        h, v = [json.loads(s[k+'_canonical_ids_json']) for k in ['history', 'validation']]
        assert not set(h) & set(v)
        for aid in h+v:
            assert ids[aid]['context_key'] == s['context_key']
        counts = {label: sum(groups.get((s['building_id'], ids[aid]['worker_id']), 'unknown') == label for aid in h)
                  for label in ['A', 'B', 'unknown']}
        for n in [2, 4]:
            c = candidate_counts(counts['A'], counts['B'], counts['unknown'], n)
            rows.append(dict(building_id=s['building_id'], context_key=s['context_key'], image_id=s['image_id'],
                             split_id=s['split_id'], scheme=s['scheme'], replicate=int(s['replicate']), n=n,
                             history_n=len(h), validation_n=len(v), A=counts['A'], B=counts['B'], unknown=counts['unknown'],
                             **c, common_support=len(v)>=2 and all(c[k]>0 for k in ARMS)))
    d = pd.DataFrame(rows)
    d.to_csv(out/'independent_combination_support.csv.gz', index=False)
    summaries=[]
    for (scheme,n),g in d.groupby(['scheme','n']):
        usable=g[g.common_support]
        summaries.append(dict(scheme=scheme,n=int(n),all_splits=len(g),common_splits=len(usable),
                              common_contexts=usable.context_key.nunique(),common_buildings=usable.building_id.nunique()))
    pd.DataFrame(summaries).to_csv(out/'independent_support_summary.csv',index=False)
    context=[]
    for (scheme,n,c),g in d.groupby(['scheme','n','context_key']):
        context.append(dict(scheme=scheme,n=n,context_key=c,building_id=g.building_id.iloc[0],image_id=g.image_id.iloc[0],
                            common_splits=int(g.common_support.sum()),all_splits=len(g),
                            max_A=int(g.A.max()),max_B=int(g.B.max()),max_validation=int(g.validation_n.max()),
                            no_A_splits=int((g.A<n).sum()),no_B_splits=int((g.B<n).sum()),
                            validation_below_2_splits=int((g.validation_n<2).sum())))
    pd.DataFrame(context).to_csv(out/'context_combination_coverage.csv',index=False)
    qa=dict(canonical=len(a),historical_workers=a.worker_id.nunique(),target_responses=len(target),
            target_contexts=target.context_key.nunique(),target_buildings=target.building_id.nunique(),
            fold_profile_rows=len(p),coverage_rows=len(d),summary=summaries,
            independent_scope='independently recomputed combinations from previously audited point-support and fold profiles')
    (out/'COVERAGE_QA.json').write_text(json.dumps(qa,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(qa,ensure_ascii=False))


def profile_audit():
    """用任务哑变量最小二乘独立复算13个训练折的连续人员效应。"""
    p = read(OUT/'review/independent_fold_profiles.csv')
    m = read(WORKERS/'inputs/worker_metrics.csv.gz')
    m = m[(m.stage=='C1') & (m.raw_condition=='manual') & (m.metric=='corner_pair_count')].copy()
    m['value'] = pd.to_numeric(m.value, errors='coerce')
    m = m[np.isfinite(m.value)]
    max_error = 0.
    for building,g in p.groupby('fold'):
        train=m[m.building_id!=building].copy()
        train=train[train.groupby('context_key').worker_id.transform('nunique')>=2]
        workers=sorted(train.worker_id.unique()); contexts=sorted(train.context_key.unique())
        assert set(workers)==set(g.worker_id)
        x=np.column_stack([(train.context_key==c).to_numpy(float) for c in contexts]+
                          [(train.worker_id==w).to_numpy(float) for w in workers])
        effect=np.linalg.lstsq(x,train.value.to_numpy(),rcond=None)[0][-len(workers):]
        effect-=effect.mean()
        original=g.set_index('worker_id').reindex(workers)
        error=float(np.max(np.abs(effect-original.effect.to_numpy(float))))
        max_error=max(max_error,error)
        assert error<1e-9
        for row in g.to_dict('records'):
            assert set(json.loads(row['training_buildings']))==set(train.building_id)
            low,high=float(row['lower']),float(row['upper'])
            expected='insufficient' if int(row['informative_buildings'])<3 or float(row['bootstrap_valid_fraction'])<.8 else (
                'high' if low>0 else 'low' if high<0 else 'uncertain')
            assert row['label']==expected
    qa=dict(training_folds=p.fold.nunique(),worker_effects=len(p),max_effect_error=max_error,
            target_buildings_excluded=True,interval_label_rule_checked=True,
            interval_values='reused previously audited bootstrap intervals; not recomputed here')
    (OUT/'review/PROFILE_AUDIT.json').write_text(json.dumps(qa,indent=2),encoding='utf-8')
    print(json.dumps(qa))


def coverage_figure():
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    plt.rcParams.update({'font.family':'Microsoft YaHei','axes.unicode_minus':False,'font.size':10})
    d=pd.read_csv(OUT/'review/context_combination_coverage.csv')
    g=d[d.scheme=='two_thirds'].copy()
    totals=g[g.n==2].groupby('building_id').size()
    supported=g[g.common_splits>0].groupby(['building_id','n']).size().unstack().reindex(totals.index).fillna(0)
    fig,ax=plt.subplots(figsize=(10,6.4))
    y=np.arange(len(totals))
    ax.barh(y,totals,color='#dddddd',label='全部C1 Manual分析单元')
    for offset,n,color in [(-.17,2,'#444444'),(.17,4,'#999999')]:
        v=supported[n].to_numpy()
        ax.barh(y+offset,v,height=.3,color=color,label=f'{n}人组合有共同人数支持')
        for yy,val in zip(y+offset,v):
            if val: ax.text(val+.15,yy,str(int(val)),va='center',fontsize=8)
    ax.set_yticks(y,totals.index); ax.invert_yaxis()
    ax.set_xlabel('分析单元数'); ax.set_title('C1 Manual：各楼人员组合覆盖（历史组占2/3）')
    ax.legend(loc='lower right',frameon=False,fontsize=9)
    fig.text(.5,.015,'同一划分下A、B各够n人且验证至少2人；尚未扣除分簇非唯一或验证多重兼容。',ha='center',fontsize=9)
    fig.tight_layout(rect=(0,.05,1,1))
    (OUT/'figures').mkdir(exist_ok=True)
    fig.savefig(OUT/'figures/combination_coverage.png',dpi=160)
    plt.close(fig)


@lru_cache(maxsize=256)
def small_partitions(n, edges):
    """穷举最多4人的所有最大团选择，与底层图搜索独立实现。"""
    edges=set(edges)
    def visit(left):
        if not left: return {()}
        for size in range(len(left),0,-1):
            cliques=[c for c in combinations(left,size) if all(e in edges for e in combinations(c,2))]
            if cliques: break
        return {tuple(sorted((c,)+rest,key=lambda z:(-len(z),z)))
                for c in cliques for rest in visit(tuple(x for x in left if x not in c))}
    return sorted(visit(tuple(range(n))))


def finite(value):
    try: return math.isfinite(float(value))
    except (ValueError,TypeError): return False


def expected_geometry(combo, validation, distance):
    value={m:np.nan for m in MEASURES}
    if len(validation)<2: return 'validation_lt2',None,value
    d=[distance[a,b] for a,b in combinations(combo,2)]
    edges=tuple((i,j) for i,j in combinations(range(len(combo)),2) if distance[combo[i],combo[j]]<=6+1e-12)
    parts=small_partitions(len(combo),edges)
    unique=len(parts)==1
    value.update(pairwise_distance_mean=float(np.mean(d)),pairwise_distance_max=max(d),
                 unique_indicator=int(unique),non_unique_indicator=int(not unique),truncated_indicator=0)
    if not unique: return 'non_unique',parts,value
    clusters=parts[0]; sizes=[len(c) for c in clusters]
    choices=[[j for j,c in enumerate(clusters) if all(distance[v,combo[i]]<=6+1e-12 for i in c)] for v in validation]
    outside=sum(len(c)==0 for c in choices); ambiguous=sum(len(c)>1 for c in choices)
    vh=[sum(c==[j] for c in choices) for j in range(len(clusters))]+[outside]
    probs=np.array(sizes+[0])/len(combo)
    value.update(cluster_count=len(sizes),supported_historical_cluster_count=sum(s>=2 for s in sizes),
                 singleton_response_fraction=sum(s==1 for s in sizes)/len(combo),
                 historical_largest_share=max(probs),training_entropy=-sum(p*math.log(p) for p in probs if p),
                 validation_outside_fraction=outside/len(validation),validation_ambiguous_fraction=ambiguous/len(validation),
                 distribution_tv=float(np.abs(probs-np.array(vh)/len(validation)).sum()/2) if not ambiguous else np.nan)
    return 'unique',parts,value


def grouped_csv(path):
    with gzip.open(path,'rt',encoding='utf-8',newline='') as f:
        for context,rows in groupby(csv.DictReader(f),key=lambda r:r['context_key']):
            yield context,list(rows)


def identity_audit():
    old=read(OLD/'split_support.csv.gz')
    old=old[(old.stage=='C1')&(old.raw_condition=='manual')].set_index(['context_key','split_id']).to_dict('index')
    count=0
    for context,rows in grouped_csv(OUT/'core/combination_support.csv.gz'):
        for r in rows:
            source=old[context,r['split_id']]
            for group in ['history','validation']:
                assert json.loads(r[group+'_canonical_ids_json'])==json.loads(source[group+'_canonical_ids_json'])
                for suffix in ['_n','_raw_n']:assert r[group+suffix]==source[group+suffix]
            count+=1
    original=read(BASE/'annotations.csv.gz')
    new=read(OUT/'core/coverage.csv.gz').set_index('canonical_annotation_id')
    original=original.set_index('canonical_annotation_id')
    assert new.index.is_unique and set(new.index)==set(original.index)
    pd.testing.assert_frame_equal(new.reindex(original.index)[original.columns],original)
    status=read(OLD/'response_status.csv.gz').set_index('canonical_annotation_id')
    assert (new.reindex(status.index).status==status.status).all()
    prof=read(OUT/'core/fold_worker_profiles.csv')
    assert len(prof)==338 and not prof.duplicated(['target_building','worker_id']).any()
    expected=read(OUT/'review/independent_fold_profiles.csv').set_index(['fold','worker_id']).to_dict('index')
    for r in prof.to_dict('records'):
        e=expected.get((r['target_building'],r['worker_id']))
        if e is None:assert r['group']=='unknown' and r['source_label']=='missing_profile'
        else:
            assert r['group']==e['group'] and r['source_label']==e['label']
            for field in ['fit_id','component','training_buildings','effect','lower','upper']:assert r[field]==e[field]
    qa=dict(status='passed',all_original_columns_unchanged=len(new),profile_rows=len(prof),
            support_rows_with_exact_original_history_validation_ids=count)
    (OUT/'review/IDENTITY_AUDIT.json').write_text(json.dumps(qa,indent=2),encoding='utf-8')
    print(json.dumps(qa))


def audit_and_summarize():
    identity_audit()
    core=OUT/'core'; out=OUT/'review'
    assert json.loads((core/'RUN_QA.json').read_text(encoding='utf-8'))['status']=='passed'
    a=read(BASE/'annotations.csv.gz').set_index('canonical_annotation_id').to_dict('index')
    profiles=read(out/'independent_fold_profiles.csv')
    labels={(r['fold'],r['worker_id']):r['group'] for r in profiles.to_dict('records')}
    independent=pd.read_csv(out/'independent_combination_support.csv.gz').set_index(['context_key','split_id','n'])
    pairs=read(ROOT/'analysis_results/order_free_cluster_holdout_20260908_v1/pairwise_point_distances.csv.gz')
    distances={c:{(r.left_canonical,r.right_canonical):float(r.ospa30) for r in g.itertuples()} for c,g in pairs.groupby('context_key')}
    ci=iter(grouped_csv(core/'combinations.csv.gz')); pending=next(ci,None)
    methods_iter=iter(grouped_csv(core/'method_summary.csv.gz'))
    paired_iter=iter(grouped_csv(core/'paired_support.csv.gz'))
    checked=Counter(); max_error=0.; context_stats=[]
    def same(actual,expected):
        nonlocal max_error
        assert finite(actual)==finite(expected),(actual,expected)
        if finite(expected):
            error=abs(float(actual)-float(expected));max_error=max(max_error,error)
            assert error<1e-10,(actual,expected)
    for ordinal,(context,support_rows) in enumerate(grouped_csv(core/'combination_support.csv.gz')):
        support={(r['split_id'],int(r['n'])):r for r in support_rows}
        assert len(support)==len(support_rows)==800
        for (split,n),r in support.items():
            ix=independent.loc[context,split,n]
            for k,source in [('A_n','A'),('B_n','B'),('unknown_n','unknown'),('history_n','history_n'),('validation_n','validation_n'),
                             ('A_only_combinations','A_only'),('balanced_AB_combinations','AB_balanced'),
                             ('B_only_combinations','B_only'),('random_AB_pool_combinations','random_AB')]:
                assert int(r[k])==int(ix[source]),(context,k)
            assert (r['common_count_support']=='True')==bool(ix.common_support)
            h,v=[json.loads(r[k+'_canonical_ids_json']) for k in ['history','validation']]
            assert not set(h)&set(v)
            for label,key in [('A','A_ids_json'),('B','B_ids_json'),('unknown','unknown_ids_json')]:
                assert set(json.loads(r[key]))=={x for x in h if labels.get((r['building_id'],a[x]['worker_id']),'unknown')==label}
        checked['support_rows']+=len(support_rows)
        combo_rows=[]
        if pending and pending[0]==context:
            combo_rows=pending[1];pending=next(ci,None)
        dist=distances.get(context,{}).copy();dist.update({(b,a):v for (a,b),v in list(dist.items())})
        pool=defaultdict(list);seen=defaultdict(set)
        for r in combo_rows:
            key=r['split_id'],int(r['n']);s=support[key]
            combo=json.loads(r['canonical_ids_json']); val=json.loads(r['validation_canonical_ids_json'])
            assert len(combo)==len(set(combo))==key[1]
            assert val==json.loads(s['validation_canonical_ids_json'])
            assert not set(combo)&set(val)
            assert set(combo)<=set(json.loads(s['A_ids_json'])+json.loads(s['B_ids_json']))
            assert all(a[x]['context_key']==context for x in combo+val)
            assert json.loads(r['worker_ids_json'])==[a[x]['worker_id'] for x in combo]
            groups=[labels[(r['building_id'],a[x]['worker_id'])] for x in combo]
            assert groups==json.loads(r['groups_json'])
            count=groups.count('A')
            comp='A_only' if count==len(combo) else 'B_only' if count==0 else 'balanced_AB' if count==len(combo)//2 else 'other_AB'
            assert r['composition']==comp
            frozen=tuple(sorted(combo));assert frozen not in seen[key];seen[key].add(frozen)
            state,parts,values=expected_geometry(combo,val,dist)
            assert r['partition_status']==state
            if parts is not None:
                assert int(r['candidate_partition_count'])==len(parts)
                expected=[list(g) for g in parts[0]] if state=='unique' else []
                assert json.loads(r['training_clusters_local_json'])==expected
            for measure,value in values.items():same(r[measure],value)
            pool[key].append(r)
        for key,s in support.items():assert len(pool[key])==int(s['random_AB_pool_combinations'])
        checked['combinations_geometry']+=len(combo_rows)
        expected={}
        for key,s in support.items():
            for arm in METHODS:
                selected=[r for r in pool[key] if arm=='random_AB_pool' or r['composition']==arm]
                for measure in MEASURES:
                    values=[float(r[measure]) for r in selected if finite(r[measure])]
                    expected[key+(arm,measure)]=(len(selected),len(values),float(np.mean(values)) if values else np.nan)
        cm,method_rows=next(methods_iter);assert cm==context
        cp,paired_rows=next(paired_iter);assert cp==context
        assert len(method_rows)==800*4*len(MEASURES)
        method_keys=set()
        for r in method_rows:
            key=r['split_id'],int(r['n']),r['method'],r['measure'];assert key not in method_keys;method_keys.add(key)
            total,valid,mean=expected[key]
            assert total==int(r['total_combinations']) and valid==int(r['valid_combinations'])
            same(r['mean'],mean);same(r['valid_fraction'],valid/total if total else np.nan)
        for r in paired_rows:
            values={arm:expected[(r['split_id'],int(r['n']),arm,r['measure'])] for arm in METHODS}
            assert (r['paired_any_values']=='True')==all(v[1]>0 for v in values.values())
            assert (r['paired_all_combinations_valid']=='True')==all(v[0]>0 and v[0]==v[1] for v in values.values())
            assert json.loads(r['method_support_json'])=={arm:dict(total_combinations=v[0],valid_combinations=v[1]) for arm,v in values.items()}
        checked['method_rows']+=len(method_rows);checked['paired_rows']+=len(paired_rows)
        frame=pd.DataFrame(method_rows)
        for c in ['mean','total_combinations','valid_combinations']:frame[c]=pd.to_numeric(frame[c],errors='coerce')
        for (scheme,n,measure),g in frame.groupby(['scheme','n','measure']):
            wide=g.pivot(index='split_id',columns='method',values='mean').reindex(columns=METHODS)
            counts=g.pivot(index='split_id',columns='method',values='valid_combinations').reindex(columns=METHODS)
            totals=g.pivot(index='split_id',columns='method',values='total_combinations').reindex(columns=METHODS)
            masks={'paired_any':wide.notna().all(axis=1), 'all_combinations_valid':(totals>0).all(axis=1)&(counts==totals).all(axis=1)}
            for mask,valid in masks.items():
                for arm in METHODS:
                    context_stats.append(dict(context_key=context,image_id=g.image_id.iloc[0],building_id=g.building_id.iloc[0],
                        scheme=scheme,n=int(n),measure=measure,mask=mask,method=arm,paired_splits=int(valid.sum()),
                        mean=wide.loc[valid,arm].mean(),minimum_valid_fraction=(counts.loc[valid,arm]/totals.loc[valid,arm]).min()))
        if ordinal%10==0:print(f'独立审查 {ordinal+1}/87：组合{checked["combinations_geometry"]}',flush=True)
    assert pending is None and next(methods_iter,None) is None and next(paired_iter,None) is None
    stats=pd.DataFrame(context_stats);stats.to_csv(out/'paired_context_results.csv',index=False,float_format='%.12g')
    keys=['scheme','n','measure','mask','method']
    good=stats[stats.paired_splits>0]
    buildings=good.groupby(keys+['building_id']).agg(mean=('mean','mean'),contexts=('context_key','nunique'),
                 paired_splits=('paired_splits','sum'),minimum_valid_fraction=('minimum_valid_fraction','min')).reset_index()
    buildings.to_csv(out/'paired_building_results.csv',index=False,float_format='%.12g')
    overall=buildings.groupby(keys).agg(mean=('mean','mean'),buildings=('building_id','nunique'),
                 contexts=('contexts','sum'),paired_splits=('paired_splits','sum'),minimum_valid_fraction=('minimum_valid_fraction','min')).reset_index()
    overall.to_csv(out/'paired_overall_results.csv',index=False,float_format='%.12g')
    qa=dict(status='passed',checked=dict(checked),max_numeric_error=max_error,partition_search='independent exhaustive maximum-clique choices for n<=4',
            distance_input='previously audited unordered point-distance cache',
            aggregation='paired within context/split, then equal contexts within building, then equal buildings')
    (out/'INDEPENDENT_AUDIT.json').write_text(json.dumps(qa,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(qa,ensure_ascii=False),flush=True)


def result_figures():
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    plt.rcParams.update({'font.family':'Microsoft YaHei','axes.unicode_minus':False,'font.size':10})
    overall=pd.read_csv(OUT/'review/paired_overall_results.csv')
    contexts=pd.read_csv(OUT/'review/paired_context_results.csv')
    labels=['仅A','A+B各半','仅B','同池随机']
    fig,axes=plt.subplots(2,2,figsize=(11,8),sharey=True)
    for ax,(scheme,n) in zip(axes.flat,[('two_thirds',2),('two_thirds',4),('sixty_percent',2),('sixty_percent',4)]):
        z=overall[(overall.scheme==scheme)&(overall.n==n)&(overall.measure=='distribution_tv')]
        descriptions=[]
        for offset,mask,color,name in [(-.18,'paired_any','#555555','各方法至少一组可算'),(.18,'all_combinations_valid','#cccccc','全部组合可算')]:
            g=z[z['mask']==mask].set_index('method').reindex(METHODS)
            ax.bar(np.arange(4)+offset,g['mean'],width=.32,color=color,label=name)
            for x,y in zip(np.arange(4)+offset,g['mean']):ax.text(x,y+.009,f'{y:.3f}',ha='center',fontsize=8)
            descriptions.append(f"{name}：{int(g.contexts.iloc[0])}图/{int(g.buildings.iloc[0])}楼/{int(g.paired_splits.iloc[0])}划分")
        ax.set_xticks(range(4),labels);ax.set_ylim(0,.57);ax.set_ylabel('历史组合与验证人员的分布差异 TV')
        ax.set_title(f"历史比例{'2/3' if scheme=='two_thirds' else '60%'}，组合{n}人")
        ax.text(.02,.98,'\n'.join(descriptions),transform=ax.transAxes,va='top',fontsize=8)
    axes[1,1].legend(loc='upper right',bbox_to_anchor=(1,-.1),fontsize=8,frameon=False)
    fig.text(.5,.015,'先在同图同划分配对，再图内平均、楼内等图、总体等楼。人数或有效规则改变时，实际比较集合也会改变。',ha='center',fontsize=9)
    fig.tight_layout(rect=(0,.055,1,1));fig.savefig(OUT/'figures/paired_tv_comparison.png',dpi=170);plt.close(fig)
    z=contexts[(contexts.scheme=='two_thirds')&(contexts.n==4)&(contexts.measure=='distribution_tv')&(contexts['mask']=='paired_any')&(contexts.paired_splits>0)]
    fig,axes=plt.subplots(4,2,figsize=(11,12),sharey=True)
    for ax,(context,g) in zip(axes.flat,z.groupby('context_key')):
        g=g.set_index('method').reindex(METHODS)
        ax.bar(range(4),g['mean'],color=['#444444','#777777','#aaaaaa','#cccccc'])
        for x,y in enumerate(g['mean']):ax.text(x,y+.018,f'{y:.3f}',ha='center',fontsize=9)
        ax.set_xticks(range(4),labels);ax.set_ylim(0,1);ax.set_ylabel('验证分布 TV')
        ax.set_title(f"{g.building_id.iloc[0]} / 图ID末8位 {g.image_id.iloc[0][-8:]}\n共同有效划分 {int(g.paired_splits.iloc[0])}/200",fontsize=10)
    axes.flat[-1].axis('off')
    fig.text(.5,.01,'固定4人、2/3历史组；列出全部7张有共同有效TV的图。每张图四种方法使用相同的人员划分集合。',ha='center',fontsize=9)
    fig.tight_layout(rect=(0,.035,1,1));fig.savefig(OUT/'figures/seven_image_tv.png',dpi=160);plt.close(fig)
    # 只按人数覆盖选示例：最多和最少正支持各一张；不按TV或组间差异挑图。
    c=pd.read_csv(OUT/'review/context_combination_coverage.csv')
    c=c[(c.scheme=='two_thirds')&(c.n==4)&(c.common_splits>0)].sort_values(['common_splits','context_key'],ascending=[False,True])
    picks=[c.iloc[0].context_key,c.sort_values(['common_splits','context_key']).iloc[0].context_key]
    versions={}
    with (BASE/'raw_annotation_versions.jsonl').open(encoding='utf-8') as f:
        for line in f:
            r=json.loads(line)
            if str(r['selected_canonical_version']).lower()=='true':versions[r['canonical_annotation_id']]=r
    supports=read(OUT/'core/combination_support.csv.gz')
    examples=[]
    for context,rows in grouped_csv(OUT/'core/combinations.csv.gz'):
        if context not in picks:continue
        s=supports[(supports.context_key==context)&(supports.scheme=='two_thirds')&(supports.n=='4')&(supports.common_count_support=='True')].copy()
        s['replicate']=s.replicate.astype(int);s=s.sort_values('replicate').iloc[0]
        chosen=[]
        for arm in METHODS[:3]:
            candidates=[r for r in rows if r['split_id']==s.split_id and r['n']=='4' and r['composition']==arm]
            chosen.append(min(candidates,key=lambda r:tuple(json.loads(r['canonical_ids_json']))))
        image=ROOT/'data/mp3d_layout/img_v'/(s.image_id+'.jpg')
        assert image.is_file()
        selected=[json.loads(r['canonical_ids_json']) for r in chosen]+[json.loads(s.validation_canonical_ids_json)]
        fig,axes=plt.subplots(2,2,figsize=(14,10))
        colors=['#ff7000','#15df50','#f744cf','#fff000','#cf80ff','#ff4030','#80ffcc','#333333','#ffb580','#9be344']
        for ax,ids,title in zip(axes.flat,selected,['仅A：4人','A+B：各2人','仅B：4人',f'固定验证组：{len(selected[-1])}人']):
            ax.imshow(plt.imread(image),extent=(0,1024,512,0))
            for i,aid in enumerate(ids):
                xy=np.asarray(versions[aid]['points_1024x512'])
                ax.scatter(xy[:,0],xy[:,1],s=32,facecolors='none',edgecolors=colors[i%len(colors)],linewidths=1.2,label='W'+versions[aid]['worker_id'])
            ax.set_title(title);ax.set_xlim(0,1024);ax.set_ylim(512,0);ax.set_xticks([]);ax.set_yticks([])
            ax.legend(loc='upper center',bbox_to_anchor=(.5,-.01),ncol=5,fontsize=8,frameon=False)
        fig.suptitle(f'{s.image_id}\nC1 Manual / 人员排列编号{s.replicate}（从0计）',fontsize=12)
        fig.text(.5,.02,'显示真实原始点，不连接墙面。示例按覆盖数量选择；固定划分内取各组成按canonical ID排序的第一个组合。',ha='center',fontsize=10)
        fig.subplots_adjust(left=.025,right=.975,top=.88,bottom=.11,wspace=.12,hspace=.32)
        name=f'point_combination_example_{picks.index(context)+1}.png'
        fig.savefig(OUT/'figures'/name,dpi=170);plt.close(fig)
        examples.append(dict(context_key=context,split_id=s.split_id,image_source=str(image.relative_to(ROOT)),figure='figures/'+name,
                             selected_combinations=chosen,validation_ids=selected[-1],selection_rule='largest/smallest positive count support; first replicate; lexicographic canonical subset',
                             final_judgment='',visual_review_status='pending'))
    assert len(examples)==2
    (OUT/'review/POINT_EXAMPLES.json').write_text(json.dumps(examples,ensure_ascii=False,indent=2),encoding='utf-8')
    print('已生成比较图2张、原始点组合示例2张。')


if __name__ == '__main__':
    parser=argparse.ArgumentParser(); parser.add_argument('--coverage-only',action='store_true'); parser.add_argument('--identity-only',action='store_true'); parser.add_argument('--figures-only',action='store_true'); args=parser.parse_args()
    if args.coverage_only:
        coverage(); profile_audit(); coverage_figure()
    elif args.identity_only:
        identity_audit()
    elif args.figures_only:
        result_figures()
    else:
        audit_and_summarize()
