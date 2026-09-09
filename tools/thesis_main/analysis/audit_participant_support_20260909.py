"""核对原始人数、楼内投影、窗口截断和组合共同支持；不重算几何或改变旧结果。"""
import json
from collections import Counter
from pathlib import Path

import numpy as np
import pandas as pd

ROOT=Path(__file__).resolve().parents[3]
OUT=ROOT/'analysis_results/participant_support_audit_20260909_v1'
BASE=ROOT/'analysis_results/uncertainty_cloud_inputs_20260906_v1'
BUILDING=ROOT/'analysis_results/building_convergence_evidence_20260908_v1'
MIX=ROOT/'analysis_results/worker_mixture_replay_20260908_v1'
CENSUS=ROOT/'analysis_results/building_holdout_exploration_20260908_v1/census'
META=['context_key','image_id','building_id','stage','block_index','raw_condition']


def project_people(context_workers, history, validation, computable_workers):
    if len(set(history+validation))!=len(history+validation):
        raise ValueError('duplicate_or_overlapping_groups')
    if not set(context_workers)<=set(history+validation):
        raise ValueError('observed_worker_missing_from_building_groups')
    return ([w for w in history if w in context_workers and w in computable_workers],
            [w for w in validation if w in context_workers and w in computable_workers])


def composition_support(a,b,v,n):
    return (v>=2 and a>=n//2 and b>=n//2, v>=2 and a>=n and b>=n)


def main():
    OUT.mkdir(parents=True,exist_ok=True)
    a=pd.read_csv(BASE/'annotations.csv.gz',dtype=str,keep_default_na=False)
    assert len(a)==2501 and a.canonical_annotation_id.is_unique and not a.duplicated(['context_key','worker_id']).any()
    states={}
    with (BASE/'raw_annotation_versions.jsonl').open(encoding='utf-8') as stream:
        for v in map(json.loads,stream):
            if str(v['selected_canonical_version']).lower()!='true':continue
            aid=v['canonical_annotation_id'];assert aid not in states
            points=np.asarray(v['points_1024x512'],float)
            states[aid]=('empty_point_response' if points.size==0 else
                'coordinate_invalid' if points.ndim!=2 or points.shape[1]!=2 or not np.isfinite(points).all()
                or (points<0).any() or (points>[1024,512]).any() else 'computable_point_pattern')
    assert set(states)==set(a.canonical_annotation_id)
    old=pd.read_csv(BUILDING/'core/response_status.csv.gz',dtype=str,keep_default_na=False)
    assert old.set_index('canonical_annotation_id').status.to_dict()==states
    a['computable']=a.canonical_annotation_id.map(states).eq('computable_point_pattern')
    contexts=a.groupby(META,sort=True).agg(raw_people=('worker_id','nunique'),computable_people=('computable','sum')).reset_index()
    contexts.to_csv(OUT/'context_people.csv',index=False)
    contexts[contexts.raw_people>15].to_csv(OUT/'contexts_over15.csv',index=False)
    contexts.groupby(['stage','raw_condition','raw_people','computable_people']).agg(contexts=('context_key','size'),images=('image_id','nunique')).reset_index().to_csv(OUT/'actual_people_distribution.csv',index=False)
    contextmap={c:g for c,g in a.groupby('context_key')}
    bybuilding={b:list(g.context_key.unique()) for b,g in a.groupby('building_id')}
    saved=pd.read_csv(BUILDING/'core/split_support.csv.gz',dtype=str,keep_default_na=False).set_index(['context_key','split_id'])
    assert saved.index.is_unique
    schedules=pd.read_csv(CENSUS/'worker_splits.csv.gz',dtype=str,keep_default_na=False)
    records=[];closure=0
    for row in schedules.to_dict('records'):
        h=json.loads(row['history_worker_ids_json']);v=json.loads(row['validation_worker_ids_json'])
        for c in bybuilding[row['building_id']]:
            g=contextmap[c];people=set(g.worker_id);good=set(g.loc[g.computable,'worker_id'])
            hh,vv=project_people(people,h,v,good)
            r=saved.loc[c,row['split_id']]
            rawh=[w for w in h if w in people];rawv=[w for w in v if w in people]
            assert int(r.history_raw_n)==len(rawh) and int(r.validation_raw_n)==len(rawv)
            assert set(rawh+rawv)==people
            assert int(r.history_n)==len(hh) and int(r.validation_n)==len(vv)
            idmap=dict(zip(g.worker_id,g.canonical_annotation_id))
            assert json.loads(r.history_canonical_ids_json)==[idmap[w] for w in hh]
            assert json.loads(r.validation_canonical_ids_json)==[idmap[w] for w in vv]
            assert json.loads(r.history_uncomputable_ids_json)==[idmap[w] for w in rawh if w not in good]
            assert json.loads(r.validation_uncomputable_ids_json)==[idmap[w] for w in rawv if w not in good]
            assert set(hh+vv)==good;closure+=1
            records.append({k:g.iloc[0][k] for k in META}|dict(scheme=row['scheme'],replicate=int(row['replicate']),
                raw_people=len(people),computable_people=len(good),history_n=len(hh),validation_n=len(vv)))
    split=pd.DataFrame(records)
    assert closure==len(saved)==108000
    split.to_csv(OUT/'reconstructed_splits.csv.gz',index=False)
    split.groupby(['stage','raw_condition','scheme','raw_people','computable_people','history_n','validation_n']).size().rename('context_replicate_rows').reset_index().to_csv(OUT/'split_people_distribution.csv',index=False)
    masks=pd.read_csv(BUILDING/'core/fixed_window_membership.csv.gz',keep_default_na=False)
    primary=masks[(masks.scheme=='two_thirds')&(masks.config=='ospa30_t6')&(masks.max_k==15)&(masks.measure=='distribution_tv')]
    primary.to_csv(OUT/'window15_masks.csv',index=False)
    cols=['all_splits','support_eligible_splits','valid_splits','non_unique_splits','truncated_splits','ambiguous_splits']
    primary.groupby(['stage','raw_condition','path'])[cols].sum().reset_index().to_csv(OUT/'window15_support_summary.csv',index=False)

    # Existing k>15 terminal records are present even though the report only used max_k<=15 masks.
    use=META+['scheme','replicate','config','k','history_n','validation_n','prefix_status','distribution_tv']
    chunks=[]
    for chunk in pd.read_csv(BUILDING/'core/prefix_validation.csv.gz',usecols=use,chunksize=100000):
        chunks.append(chunk[(chunk.scheme=='two_thirds')&(chunk.config=='ospa30_t6')])
    prefix=pd.concat(chunks,ignore_index=True)
    prefix['tv_valid']=prefix.distribution_tv.notna()
    prefix[prefix.k>15].to_csv(OUT/'existing_prefixes_over15.csv.gz',index=False)
    prefix.groupby(['stage','raw_condition','k']).agg(records=('context_key','size'),contexts=('context_key','nunique'),
        tv_valid_records=('tv_valid','sum'),minimum_history=('history_n','min'),maximum_history=('history_n','max')).reset_index().to_csv(OUT/'existing_prefix_nodes.csv',index=False)
    late=prefix[(prefix.k.isin([15,17]))&(prefix.history_n>=17)]
    paired=late.pivot(index=META+['replicate'],columns='k',values='distribution_tv').reset_index()
    paired['paired_valid']=paired[15].notna()&paired[17].notna()
    paired.to_csv(OUT/'paired_15_17_records.csv.gz',index=False)
    validlate=paired[paired.paired_valid]
    late_summary=validlate.groupby(META).agg(paired_replicates=('replicate','size'),tv_k15=(15,'mean'),tv_k17=(17,'mean')).reset_index()
    late_summary['tv17_minus_tv15']=late_summary.tv_k17-late_summary.tv_k15
    late_summary.to_csv(OUT/'paired_15_17_by_context.csv',index=False)

    # Count-only alternative partitions: first 2/4/6 building workers retained as validation.
    # These are feasibility diagnostics; no claims about TV precision or predictive success follow.
    orders=[json.loads(line) for line in (CENSUS/'global_worker_orders.jsonl').read_text(encoding='utf-8').splitlines()]
    alternative=[]
    for order in orders:
        for b,cs in bybuilding.items():
            roster=set(a.loc[a.building_id==b,'worker_id'])
            people=[w for w in order['worker_ids'] if w in roster]
            for reserve in [2,4,6]:
                v,h=people[:reserve],people[reserve:]
                for c in cs:
                    g=contextmap[c]
                    hh,vv=project_people(set(g.worker_id),h,v,set(g.loc[g.computable,'worker_id']))
                    alternative.append({k:g.iloc[0][k] for k in META}|dict(reserved_building_people=reserve,
                        replicate=order['replicate'],history_n=len(hh),validation_n=len(vv)))
    alternative=pd.DataFrame(alternative)
    alternative.to_csv(OUT/'alternative_count_only_splits.csv.gz',index=False)
    alt_summary=[]
    for key,g in alternative.groupby(['stage','raw_condition','reserved_building_people']):
        for k in [15,17,20,22,24]:
            good=g[(g.history_n>=k)&(g.validation_n>=2)]
            alt_summary.append(dict(zip(['stage','raw_condition','reserved_building_people'],key))|dict(k=k,
                candidate_contexts=g.context_key.nunique(),supported_contexts=good.context_key.nunique(),
                supported_context_replicates=len(good),minimum_validation=int(good.validation_n.min()) if len(good) else None,
                maximum_validation=int(good.validation_n.max()) if len(good) else None))
    pd.DataFrame(alt_summary).to_csv(OUT/'alternative_count_only_support.csv',index=False)

    profiles=pd.read_csv(MIX/'core/fold_worker_profiles.csv',dtype=str,keep_default_na=False)
    label={(r.target_building,r.worker_id):r.group for r in profiles.itertuples()}
    support=pd.read_csv(MIX/'core/combination_support.csv.gz',keep_default_na=False)
    for r in support.itertuples():
        balanced,allfour=composition_support(r.A_n,r.B_n,r.validation_n,r.n)
        assert bool(r.common_count_support)==allfour
    c1=a[(a.stage=='C1')&(a.raw_condition=='manual')]
    whole=[]
    for c,g in c1.groupby('context_key'):
        b=g.building_id.iloc[0];good=g[g.computable]
        counts=Counter(label[b,w] for w in good.worker_id)
        whole.append({k:g.iloc[0][k] for k in META}|dict(raw_people=len(g),computable_people=len(good),
            A=counts['A'],B=counts['B'],unknown=counts['unknown']))
    whole=pd.DataFrame(whole);whole.to_csv(OUT/'c1_full_pool_groups.csv',index=False)
    support['balanced_count_support']=[composition_support(r.A_n,r.B_n,r.validation_n,r.n)[0] for r in support.itertuples()]
    support.groupby(['scheme','n'])[['common_count_support','balanced_count_support']].sum().reset_index().to_csv(OUT/'mixture_count_support.csv',index=False)
    combo_cols=['context_key','image_id','building_id','split_id','scheme','n','composition','distribution_tv','worker_ids_json','validation_canonical_ids_json']
    combos=pd.read_csv(MIX/'core/combinations.csv.gz',usecols=combo_cols)
    tv=combos[combos.distribution_tv.notna()].copy()
    keys=['context_key','split_id','scheme','n']
    comp=tv.groupby(keys).composition.agg(set)
    common=comp[comp.apply(lambda s:{'A_only','B_only','balanced_AB'}<=s)].reset_index()[keys]
    selected=tv.merge(common,on=keys,validate='many_to_one')
    idworker=a.set_index('canonical_annotation_id').worker_id.to_dict()
    waterfall=[]
    for scheme,n in support[['scheme','n']].drop_duplicates().itertuples(index=False,name=None):
        g=support[(support.scheme==scheme)&(support.n==n)]
        subsets=[('全部C1图与排列',g),('验证至少2人',g[g.validation_n>=2]),
            ('另要求A至少n人',g[(g.validation_n>=2)&(g.A_n>=n)]),
            ('另要求B至少n人',g[g.common_count_support])]
        for step,q in subsets:
            waterfall.append(dict(scheme=scheme,n=n,step=step,contexts=q.context_key.nunique(),buildings=q.building_id.nunique(),context_replicate_rows=len(q)))
        q=selected[(selected.scheme==scheme)&(selected.n==n)]
        hp=set();vp=set()
        for value in q.worker_ids_json.unique():hp.update(map(str,json.loads(value)))
        for value in q.validation_canonical_ids_json.unique():vp.update(idworker[x] for x in json.loads(value))
        waterfall.append(dict(scheme=scheme,n=n,step='四方案均有精确TV',contexts=q.context_key.nunique(),
            buildings=q.building_id.nunique(),context_replicate_rows=len(q[keys].drop_duplicates()),
            actual_history_workers=len(hp),actual_validation_workers=len(vp),all_participating_workers=len(hp|vp),
            history_worker_ids_json=json.dumps(sorted(hp,key=int)),validation_worker_ids_json=json.dumps(sorted(vp,key=int))))
    pd.DataFrame(waterfall).to_csv(OUT/'mixture_support_waterfall.csv',index=False)
    result=dict(status='passed',canonical=len(a),workers=a.worker_id.nunique(),contexts=len(contexts),
        contexts_over15=int((contexts.raw_people>15).sum()),images_over15=contexts.loc[contexts.raw_people>15,'image_id'].nunique(),
        reconstructed_splits=closure,raw_and_computable_identity_closure=True,missing_or_overlapping_workers=0,
        response_states=Counter(states.values()),source_prefix_TV_recomputed=False,source_geometry_recomputed=False,
        new_descriptive_summaries_calculated=True,alternative_partition_TV_calculated=False,
        alternative_partitions='人数可行性诊断；不等同完整验证方案或推荐人数',
        coordination='已有协作任务消息被自动审批连接错误阻止，本任务独立复核。')
    (OUT/'AUDIT_QA.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(result,ensure_ascii=True))


if __name__=='__main__':main()
