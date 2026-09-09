"""全历史暂定2/3类：楼外分型、楼内人员留出、稳定多簇的有限人数探索。"""
from pathlib import Path
import argparse
import csv
import gzip
import json
import time
import numpy as np
import pandas as pd
from tools.thesis_main.analysis.worker_reference_feasibility_20260909 import (
    ROOT, OUT as SOURCE, POINTS, jsonlines, profiles, ordinal_groups,
)
from tools.thesis_main.analysis.fit_worker_evidence_strata_20260908 import seed_for
from tools.thesis_main.analysis.order_free_cluster_holdout_20260908 import (
    unit_points, point_distances, partition, fixed_distribution,
)

OUT=ROOT/'analysis_results/type_convergence_exploration_20260909_v1'


def split_people(labels, seed):
    """每楼一次全员排列，类型内2/3历史；单人类型没有可用历史人。"""
    order=np.random.default_rng(seed).permutation(sorted(labels,key=int)).tolist()
    history=set()
    for label in sorted(set(labels.values())):
        people=[w for w in order if labels[w]==label]
        history.update(people[:2*len(people)//3])
    return [w for w in order if w in history],[w for w in order if w not in history]


def pattern_sequence(pools, pattern):
    needed={g:pattern.count(g) for g in set(pattern)}
    cycles=min(len(pools.get(g,[]))//count for g,count in needed.items())
    used={g:0 for g in needed};seq=[]
    for _ in range(cycles):
        for g in pattern:
            seq.append(pools[g][used[g]]);used[g]+=1
    return seq,len(pattern)


def evaluate_path(matrix,history,validation,threshold,ks,reference):
    if len(history)!=len(set(history)) or len(validation)!=len(set(validation)) or set(history)&set(validation):
        raise ValueError('duplicate_people_or_history_validation_overlap')
    if len(validation)<2 or len(history)<2:
        raise ValueError('insufficient_history_or_validation')
    sorted_h=sorted(history)
    part=partition(matrix[np.ix_(sorted_h,sorted_h)],threshold)
    fixed={}
    if part['status']=='unique':
        positions={v:i for i,v in enumerate(history)}
        clusters=[[positions[sorted_h[i]] for i in group] for group in part['clusters']]
        fixed={r['k']:r for r in fixed_distribution(matrix,history,validation,clusters,threshold,ks)}
    rows=[]
    for n in ks:
        h=history[:n];sub=matrix[np.ix_(h,h)]
        prefix=partition(sub,threshold)
        medoids=np.flatnonzero(np.isclose(sub.mean(axis=1),sub.mean(axis=1).min(),atol=1e-10,rtol=0))
        ref=np.asarray(reference)[np.asarray(h)[medoids]]
        f=fixed.get(n,{})
        row=dict(n=n,full_partition_status=part['status'],prefix_partition_status=prefix['status'],
            prefix_clusters=len(prefix['clusters']) if prefix['status']=='unique' else np.nan,
            distribution_tv=f.get('distribution_tv',np.nan),
            prefix_to_full_history_tv=f.get('prefix_to_full_history_tv',np.nan),
            historical_largest_share=f.get('historical_largest_share',np.nan),
            full_taxonomy_validation_outside=f.get('validation_outside_fraction',np.nan),
            full_taxonomy_validation_ambiguous=f.get('validation_ambiguous_fraction',np.nan),
            observed_full_taxonomy_clusters=f.get('observed_historical_cluster_count',np.nan),
            prefix_validation_outside=np.nan,prefix_validation_ambiguous=np.nan,
            medoid_reference_error=float(ref.mean()) if np.isfinite(ref).all() else np.nan,
            medoid_tie_count=len(medoids))
        if prefix['status']=='unique':
            v=fixed_distribution(matrix,h,validation,prefix['clusters'],threshold,[n])[0]
            row.update(prefix_validation_outside=v['validation_outside_fraction'],
                       prefix_validation_ambiguous=v['validation_ambiguous_fraction'])
        rows.append(row)
    return rows


def run(replicates=20):
    OUT.mkdir(parents=True,exist_ok=True)
    start=time.time()
    plan=dict(replicates=replicates,types=[2,3],cohorts=['all26','current20'],metrics=['ospa30','ospa60'],
        threshold_degrees=6,grouping='outside_building_Ward_reference_effect',
        split='global_building_worker_permutation_then_2/3_within_type; no replacement',
        fixed_taxonomy='full_selected_history_only; retrospective_prefix_counts_not_online_discovery',
        independent_prefix='recluster_every_prefix_without_future_history_or_validation',
        duplicate_response='one_raw_response_per_image_worker_per_replicate_shared_across_methods',
        unknown_reference='included_for_disagreement; representative_reference_error_missing',
        stop_n=None,stable_multiple_clusters_allowed=True)
    (OUT/'PLAN.json').write_text(json.dumps(plan,ensure_ascii=False,indent=2),encoding='utf-8')
    source=pd.read_csv(SOURCE/'pooled/image_worker_measurements.csv.gz',dtype={'worker_id':str,'current20_member':str})
    scores=pd.read_csv(SOURCE/'response_measurements.csv.gz',dtype={'canonical_annotation_id':str})
    scores=scores.set_index('canonical_annotation_id')
    raw=jsonlines(POINTS);valid=[r for r in raw if r['calculation_included']]
    by_image={}
    for r in valid:by_image.setdefault(r['image_id'],[]).append(r)
    matrices={};nodes={}
    for image,rows in sorted(by_image.items()):
        rows=sorted(rows,key=lambda r:r['canonical_annotation_id']);nodes[image]=rows
        units=[unit_points(r['effective_points_1024x512']) for r in rows]
        matrix={m:np.zeros((len(rows),len(rows))) for m in ['ospa30','ospa60']}
        for i in range(len(rows)):
            for j in range(i):
                values=point_distances(units[i],units[j])
                for m in matrix:matrix[m][i,j]=matrix[m][j,i]=values[m]
        matrices[image]=matrix
    counts={};writers={};streams=[];profile_rows=[]
    def emit(name,row):
        if name not in writers:
            f=gzip.open(OUT/name,'wt',encoding='utf-8',newline='');streams.append(f)
            writers[name]=csv.DictWriter(f,fieldnames=list(row));writers[name].writeheader();counts[name]=0
        writers[name].writerow(row);counts[name]+=1
    try:
        for cohort,data in [('all26',source),('current20',source[source.current20_member.str.lower()=='true'])]:
            for metric in ['ospa30','ospa60']:
                for building in sorted(data.building_id.unique()):
                    train=data[data.building_id!=building].assign(value=lambda x:x[metric])
                    fit=profiles(train)
                    for k in (2,3):
                        grouped=ordinal_groups(fit,k,'ward');labels=dict(zip(grouped.worker_id,grouped.label))
                        for r in grouped.to_dict('records'):
                            profile_rows.append(dict(r,cohort=cohort,metric=metric,k=k,heldout_building=building,
                                training_buildings=json.dumps(sorted(train.building_id.unique()))))
                        patterns={chr(64+i):[i] for i in range(1,k+1)}
                        patterns.update(ALL=None)
                        patterns.update({'AB':[1,2],'AAB':[1,1,2]} if k==2 else {'ABC':[1,2,3],'AABC':[1,1,2,3]})
                        for rep in range(replicates):
                            hs,vs=split_people(labels,seed_for((cohort,building,rep)))
                            for image,rows in nodes.items():
                                if rows[0]['building_id']!=building:continue
                                options={}
                                for i,r in enumerate(rows):
                                    if r['worker_id'] in labels:options.setdefault(r['worker_id'],[]).append(i)
                                chosen={w:ids[int(np.random.default_rng(seed_for((image,w,rep))).integers(len(ids)))] for w,ids in options.items()}
                                h=[chosen[w] for w in hs if w in chosen];v=[chosen[w] for w in vs if w in chosen]
                                hp={g:[i for i in h if labels[rows[i]['worker_id']]==g] for g in range(1,k+1)}
                                vp={g:[i for i in v if labels[rows[i]['worker_id']]==g] for g in range(1,k+1)}
                                refs=np.array([scores.loc[r['canonical_annotation_id'],metric] for r in rows],float)
                                for method,pattern in patterns.items():
                                    history,step=(h,1) if pattern is None else pattern_sequence(hp,pattern)
                                    validation=v if pattern is None else pattern_sequence(vp,pattern)[0]
                                    meta=dict(cohort=cohort,metric=metric,k=k,building_id=building,image_id=image,replicate=rep,method=method)
                                    status='history_lt2' if len(history)<2 else 'validation_lt2' if len(validation)<2 else 'supported'
                                    emit('coverage.csv.gz',dict(meta,history_n=len(history),validation_n=len(validation),status=status,
                                        group_history_counts=json.dumps({g:len(x) for g,x in hp.items()}),
                                        group_validation_counts=json.dumps({g:len(x) for g,x in vp.items()}),
                                        history_workers=json.dumps([rows[i]['worker_id'] for i in history]),
                                        validation_workers=json.dumps([rows[i]['worker_id'] for i in validation]),
                                        history_canonical_ids=json.dumps([rows[i]['canonical_annotation_id'] for i in history]),
                                        validation_canonical_ids=json.dumps([rows[i]['canonical_annotation_id'] for i in validation])))
                                    if status!='supported':continue
                                    ks=list(range(max(2,step),len(history)+1,step))
                                    for r in evaluate_path(matrices[image][metric],history,validation,6.,ks,refs):
                                        emit('curves.csv.gz',dict(meta,history_n=len(history),validation_n=len(validation),**r))
                    print(f'{time.time()-start:.1f}s {cohort} {metric} {building} {counts}',flush=True)
    finally:
        for stream in streams:stream.close()
    pd.DataFrame(profile_rows).to_csv(OUT/'fold_profiles.csv',index=False)
    (OUT/'QA.json').write_text(json.dumps(dict(raw_canonical=len(raw),point_computable=len(valid),
        images=len(nodes),counts=counts,source_point_order_changed=False,replicates=replicates),indent=2),encoding='utf-8')


def summarize():
    coverage=pd.read_csv(OUT/'coverage.csv.gz')
    curves=pd.read_csv(OUT/'curves.csv.gz')
    keys=['cohort','metric','k','method']
    supports=[]
    for key,d in coverage.groupby(keys):
        good=d[d.status=='supported']
        supports.append(dict(zip(keys,key))|dict(total_image_splits=len(d),supported_image_splits=len(good),
            supported_images=good.image_id.nunique(),supported_buildings=good.building_id.nunique(),
            max_supported_history=int(good.history_n.max()) if len(good) else 0,
            distinct_history_sizes=json.dumps(sorted(good.history_n.unique().tolist()))))
    pd.DataFrame(supports).to_csv(OUT/'support_summary.csv',index=False)
    summaries=[];paths=[]
    # 同图同人员划分保留整条路径；不随n更换样本。
    for key,d in curves.groupby(keys):
        for horizon in (4,6,8,12):
            eligible=d[d.n==horizon][['image_id','replicate']]
            if eligible.empty:continue
            path=d[d.n<=horizon].merge(eligible,on=['image_id','replicate'],validate='many_to_one')
            sizes=sorted(path.n.unique())
            if len(sizes)<2:continue
            valid=path.groupby(['image_id','replicate']).distribution_tv.apply(lambda x:x.notna().all())
            good=valid[valid].reset_index()[['image_id','replicate']]
            z=path.merge(good,on=['image_id','replicate'],validate='many_to_one')
            if z.empty:continue
            image=z.groupby(['building_id','image_id','n']).agg(tv=('distribution_tv','mean'),
                medoid_reference_error=('medoid_reference_error','mean'),
                prefix_clusters=('prefix_clusters','mean'),draws=('replicate','size')).reset_index()
            building=image.groupby(['building_id','n'])[['tv','medoid_reference_error','prefix_clusters']].mean().reset_index()
            overall=building.groupby('n')[['tv','medoid_reference_error','prefix_clusters']].mean()
            meta=dict(zip(keys,key))|dict(horizon=horizon,images=z.image_id.nunique(),buildings=z.building_id.nunique(),
                supported_image_splits=len(eligible),valid_tv_image_splits=len(good),
                start_n=sizes[0],end_n=sizes[-1],start_tv=overall.loc[sizes[0],'tv'],end_tv=overall.loc[sizes[-1],'tv'],
                last_step_tv_change=overall.loc[sizes[-1],'tv']-overall.loc[sizes[-2],'tv'])
            summaries.append(meta)
            for n,r in overall.iterrows():paths.append(meta|dict(n=n,**r.to_dict()))
    pd.DataFrame(summaries).to_csv(OUT/'fixed_panel_summary.csv',index=False)
    path_frame=pd.DataFrame(paths)
    path_frame.to_csv(OUT/'fixed_panel_curves.csv',index=False)
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    plt.rcParams['font.family']='Microsoft YaHei'
    fig,axes=plt.subplots(1,2,figsize=(11,4.6))
    for ax,(method,horizon,title) in zip(axes,[('ALL',12,'两类：混合历史池'),('AB',8,'两类：A/B各半')]):
        for metric in ['ospa30','ospa60']:
            z=path_frame[(path_frame.cohort=='current20')&(path_frame.k==2)&
                (path_frame.method==method)&(path_frame.horizon==horizon)&(path_frame.metric==metric)].sort_values('n')
            if len(z):
                ax.plot(z.n,z.tv,marker='o',label=f'{metric}：{z.images.iloc[0]}图/{z.buildings.iloc[0]}楼')
        ax.set(title=title,xlabel='历史组人数（另有固定验证人员）',ylabel='历史与验证簇比例的TV差异')
        ax.grid(alpha=.25);ax.legend(fontsize=8);ax.set_ylim(0,.65)
    fig.suptitle('当前20人：每条曲线使用固定图像/人员划分；不代表已确定停止人数')
    fig.text(.5,.015,'不同曲线的有效图像集合不同，不能直接用曲线高低比较方法优劣。',ha='center',fontsize=9)
    fig.tight_layout(rect=(0,.04,1,.94));fig.savefig(OUT/'fixed_panel_curves.png',dpi=180);plt.close(fig)
    print(pd.DataFrame(summaries).query("cohort=='current20' and metric=='ospa30'").to_string(index=False))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--replicates',type=int,default=20)
    p.add_argument('--summarize',action='store_true')
    args=p.parse_args()
    if args.replicates<1:p.error('replicates must be positive')
    summarize() if args.summarize else run(args.replicates)
