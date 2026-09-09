"""无序球面点集的簇分布留出探索；不读取角点邻接，不构造墙面。"""
from __future__ import annotations
import argparse
import csv
import gzip
import json
import math
import sys
from collections import Counter,defaultdict
from contextlib import ExitStack
from functools import lru_cache
from pathlib import Path
import numpy as np
import pandas as pd
from scipy.optimize import linear_sum_assignment

ROOT=Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:sys.path.insert(0,str(ROOT))
from tools.thesis_main.analysis.geometry_cluster_v2 import _maximum_clique_partitions
from tools.thesis_main.analysis.simulate_building_holdout_20260908 import summarize_local

BASE='analysis_results/uncertainty_cloud_inputs_20260906_v1'
PREVIOUS='analysis_results/building_holdout_exploration_20260908_v1'
OUTPUT='analysis_results/order_free_cluster_holdout_20260908_v1'
CONFIGS=[('ospa30_t3','ospa30',3.),('ospa30_t6','ospa30',6.),('ospa30_t12','ospa30',12.),('ospa60_t6','ospa60',6.)]
META=['context_key','image_id','building_id','stage','block_index','raw_condition','initialization_kind']


def unit_points(points):
    p=np.asarray(points,dtype=float)
    if p.size==0:raise ValueError('empty_point_response')
    if p.ndim!=2 or p.shape[1]!=2:raise ValueError('coordinate_shape')
    if not np.isfinite(p).all() or (p[:,0]<0).any() or (p[:,0]>1024).any() or (p[:,1]<0).any() or (p[:,1]>512).any():
        raise ValueError('coordinate_invalid')
    # 仅对无序特征副本排序以固定浮点运算；不是墙面连接顺序或对原文件的编辑。
    u=(p[:,0]%1024)*2*np.pi/1024;v=np.pi/2-p[:,1]*np.pi/512
    q=np.column_stack([np.cos(v)*np.cos(u),np.cos(v)*np.sin(u),np.sin(v)])
    return q[np.lexsort(q.T[::-1])]


def point_distances(a,b):
    if min(len(a),len(b))==0:raise ValueError('empty_point_response')
    cross=np.linalg.norm(np.cross(a[:,None,:],b[None,:,:]),axis=2)
    angle=np.degrees(np.arctan2(cross,np.clip(a@b.T,-1,1)))
    result={'chamfer':float((angle.min(axis=0).mean()+angle.min(axis=1).mean())/2)}
    for cap in (30,60):
        cost=np.minimum(angle,cap);i,j=linear_sum_assignment(cost)
        result['ospa'+str(cap)]=float((cost[i,j].sum()+cap*abs(len(a)-len(b)))/max(len(a),len(b)))
    return result


@lru_cache(maxsize=30000)
def _partition_graph(n,edges):
    candidates,truncated,_=_maximum_clique_partitions(tuple(range(n)),set(edges),maximum_partition_count=256,maximum_search_nodes=10000)
    return (candidates[0] if len(candidates)==1 and not truncated else (),len(candidates),truncated)


def partition(matrix,threshold):
    matrix=np.asarray(matrix,float);n=len(matrix)
    if matrix.shape!=(n,n) or not np.isfinite(matrix).all() or not np.allclose(matrix,matrix.T) or (matrix<0).any():raise ValueError('invalid_distance_matrix')
    edges=tuple((i,j) for i in range(n) for j in range(i+1,n) if matrix[i,j]<=threshold+1e-12)
    groups,count,truncated=_partition_graph(n,edges)
    return dict(status='truncated' if truncated else 'unique' if count==1 else 'non_unique',
                clusters=[list(x) for x in groups],candidate_partition_count=count,enumeration_truncated=truncated)


def entropy(sizes):
    sizes=np.asarray(sizes,float);p=sizes[sizes>0]/sizes.sum()
    return float(-np.sum(p*np.log(p)))


def fixed_distribution(matrix,history,validation,clusters,threshold,ks):
    """完整历史组学习簇定义。所有k使用同一簇定义/验证分配；不把它称作前缀在线学习。"""
    if set(history)&set(validation):raise ValueError('history_validation_overlap')
    assert sorted(i for g in clusters for i in g)==list(range(len(history)))
    choices=[[j for j,g in enumerate(clusters) if max(matrix[person,history[i]] for i in g)<=threshold+1e-12] for person in validation]
    outside=sum(not c for c in choices);ambiguous=sum(len(c)>1 for c in choices)
    vcounts=[sum(c==[j] for c in choices) for j in range(len(clusters))]+[outside]
    full=np.array([len(g) for g in clusters]+[0],float)/len(history)
    rows=[]
    for k in sorted(set(ks)):
        if not 1<=k<=len(history):continue
        counts=[sum(i<k for i in g) for g in clusters]
        probs=np.array(counts+[0],float)/k
        rows.append(dict(k=k,training_cluster_support_json=json.dumps(counts),training_entropy=entropy(counts),
                         observed_historical_cluster_count=sum(x>0 for x in counts),
                         supported_historical_cluster_count=sum(x>=2 for x in counts),
                         historical_largest_share=max(counts)/k,
                         distribution_tv=float(abs(probs-np.array(vcounts)/len(validation)).sum()/2) if not ambiguous else np.nan,
                         prefix_to_full_history_tv=float(abs(probs-full).sum()/2),
                         validation_outside_fraction=outside/len(validation),validation_ambiguous_fraction=ambiguous/len(validation),
                         validation_cluster_support_json=json.dumps(vcounts),validation_compatible_cluster_ids_json=json.dumps(choices)))
    return rows


def read(path):return pd.read_csv(path,dtype=str,keep_default_na=False)
def save(out,name,rows):pd.DataFrame(rows).to_csv(out/name,index=False,float_format='%.12g')


def run(root,out):
    out.mkdir(parents=True,exist_ok=True)
    plan=dict(scope='2501 canonical,all26,existing200worker_splits,bothfractions',
        user_hypothesis='稳定多簇也可视为一种收敛候选；不是要求熵为零。没有最终收敛门槛或人数。',
        order_free='点坐标转球面方向后无序匹配；无邻接/点对/墙面/多边形；重复点保留为多重性',
        metric='p=1 OSPA式截断角距匹配及未匹配点数量惩罚，度数；Chamfer仅对照',configurations=CONFIGS,
        clustering='复用v5底层逐次最大团complete-link分区枚举；不强制选择非唯一分区',
        full_training_taxonomy='完整历史组学簇、固定验证映射；前缀只是该历史分类下的比例回放，含完整历史组信息',
        independent_prefix_reclustering='每个前缀另行重分簇，不使用其他历史人或验证人决定该前缀的簇',
        validation_rule='验证点集必须与某历史簇所有成员在阈值内；多个兼容簇保留歧义，不强制归属；无兼容簇记outside',
        fixed_vs_adaptive='同一完整历史分组的验证归属在所有k保持不变，避免随k增大簇成员增多而自动收紧接纳条件',
        empty_and_invalid='空点或无效坐标保留但不当作0距离；奇数/少量点可描述，不说明合法布局',
        cluster_thresholds='3/6/12度为探索敏感性，不沿用v5 q=.95，不代表已校准的合法答案判据',
        geometry_limits='相同点集不同连接无法区分；同簇不等于正确/合法/同一enclosed或extended语义')
    (out/'METHOD_PLAN.json').write_text(json.dumps(plan,ensure_ascii=False,indent=2),encoding='utf-8')
    a=read(root/BASE/'annotations.csv.gz');assert a.canonical_annotation_id.is_unique and not a.duplicated(['context_key','worker_id']).any()
    original=read(root/PREVIOUS/'census/canonical_index.csv.gz')
    assert set(a.canonical_annotation_id)==set(original.canonical_annotation_id)
    raw={v['canonical_annotation_id']:v['points_1024x512'] for v in map(json.loads,(root/BASE/'raw_annotation_versions.jsonl').read_text(encoding='utf-8').splitlines()) if str(v['selected_canonical_version']).lower()=='true'}
    init=read(root/PREVIOUS/'initialization_context_index.csv').set_index('context_key').initialization_kind
    a['initialization_kind']=a.context_key.map(init);assert not a.initialization_kind.isna().any()
    unit,status={},[];permutation_errors=[]
    for row in a.to_dict('records'):
        aid=row['canonical_annotation_id'];points=raw[aid];state='computable_point_pattern'
        try:unit[aid]=unit_points(points)
        except ValueError as e:state=str(e)
        if aid in unit:
            shuffled=unit_points(points[::-1]);permutation_errors.append(float(np.max(abs(unit[aid]-shuffled))))
        status.append({k:row[k] for k in META+['canonical_annotation_id','worker_id']}|dict(status=state,raw_endpoint_count=len(points),
            raw_order_used=False,raw_points_changed=False,odd_point_count=bool(len(points)%2)))
    save(out,'response_status.csv.gz',status)
    schedules=defaultdict(list)
    for s in read(root/PREVIOUS/'census/worker_splits.csv.gz').to_dict('records'):
        s['h']=json.loads(s['history_worker_ids_json']);s['v']=json.loads(s['validation_worker_ids_json'])
        assert not set(s['h'])&set(s['v']);schedules[s['building_id']].append(s)
    streams=Counter();pairs=[];fixed_summary=[];cluster_summary=[];paired_summary=[];full_summary=[]
    with ExitStack() as stack:
        writers={}
        def emit(name,row):
            if name not in writers:
                f=stack.enter_context(gzip.open(out/name,'wt',encoding='utf-8',newline=''))
                writers[name]=csv.DictWriter(f,fieldnames=list(row));writers[name].writeheader()
            writers[name].writerow(row);streams[name]+=1
        for ordinal,(context,frame) in enumerate(a.groupby('context_key',sort=True)):
            if ordinal%30==0:print(f'点集分簇 {ordinal}/270',flush=True)
            meta={k:frame.iloc[0][k] for k in META}
            frame=frame.sort_values('worker_id',key=lambda x:x.astype(int));good=frame[frame.canonical_annotation_id.isin(unit)]
            ids=list(good.canonical_annotation_id);workers=list(good.worker_id);pos={w:i for i,w in enumerate(workers)}
            matrices={m:np.zeros((len(ids),len(ids))) for m in ['ospa30','ospa60','chamfer']}
            for i,left in enumerate(ids):
                for j,right in enumerate(ids[:i]):
                    distances=point_distances(unit[left],unit[right])
                    pairs.append(dict(context_key=context,left_canonical=left,right_canonical=right,**distances))
                    for m,d in distances.items():matrices[m][i,j]=matrices[m][j,i]=d
            local_fixed=[];local_cluster=[];local_paired=[];local_full=[]
            for s in schedules[meta['building_id']]:
                h=[pos[w] for w in s['h'] if w in pos];v=[pos[w] for w in s['v'] if w in pos]
                base=meta|dict(split_id=s['split_id'],replicate=int(s['replicate']),scheme=s['scheme'],history_n=len(h),validation_n=len(v))
                support='available' if len(h)>=3 and len(v)>=2 else 'history_lt3' if len(h)<3 else 'validation_lt2'
                emit('split_support.csv.gz',base|dict(status=support))
                if support!='available':continue
                ks=[k for k in sorted({3,5,8,10,12,15,len(h)}) if k<=len(h)]
                for config,metric,tau in CONFIGS:
                    d=matrices[metric];b=base|dict(config=config,metric=metric,threshold_degrees=tau)
                    full=partition(d[np.ix_(h,h)],tau)
                    fullrow=dict(full_partition_status=full['status'],candidate_partition_count=full['candidate_partition_count'],
                        historical_canonical_ids_json=json.dumps([ids[i] for i in h]),validation_canonical_ids_json=json.dumps([ids[i] for i in v]),
                        full_clusters_json=json.dumps([[ids[h[i]] for i in g] for g in full['clusters']]),
                        full_cluster_count=len(full['clusters']) if full['status']=='unique' else np.nan,
                        full_training_entropy=entropy([len(g) for g in full['clusters']]) if full['status']=='unique' else np.nan)
                    emit('historical_cluster_definitions.csv.gz',b|fullrow)
                    local_full.append(dict(config=config,scheme=s['scheme'],unique=float(full['status']=='unique'),
                        non_unique=float(full['status']=='non_unique'),truncated=float(full['status']=='truncated'),
                        cluster_count=fullrow['full_cluster_count'],entropy=fullrow['full_training_entropy']))
                    for k in ks:
                        part=full if k==len(h) else partition(d[np.ix_(h[:k],h[:k])],tau)
                        sizes=[len(g) for g in part['clusters']]
                        cr=dict(k=k,status=part['status'],cluster_count=len(sizes) if sizes else np.nan,
                            supported_cluster_count=sum(n>=2 for n in sizes) if sizes else np.nan,
                            largest_share=max(sizes)/k if sizes else np.nan,entropy=entropy(sizes) if sizes else np.nan,
                            prefix_clusters_json=json.dumps([[ids[h[i]] for i in g] for g in part['clusters']]))
                        emit('prefix_reclustering.csv.gz',b|cr)
                        local_cluster.append(dict(config=config,scheme=s['scheme'],k_label=str(k),unique=float(part['status']=='unique'),
                            cluster_count=cr['cluster_count'],supported_cluster_count=cr['supported_cluster_count'],largest_share=cr['largest_share'],entropy=cr['entropy']))
                    if full['status']!='unique':continue
                    result=fixed_distribution(d,h,v,full['clusters'],tau,ks)
                    for r in result:
                        emit('fixed_taxonomy_prefixes.csv.gz',b|r)
                        values={k:r[k] for k in ['distribution_tv','prefix_to_full_history_tv','validation_outside_fraction','validation_ambiguous_fraction','training_entropy','observed_historical_cluster_count']}
                        local_fixed.append(dict(config=config,scheme=s['scheme'],k_label=str(r['k']),**values))
                        if r['k']==len(h):local_fixed.append(dict(config=config,scheme=s['scheme'],k_label='full_history',**values))
                    by_k={r['k']:r for r in result}
                    for start in (3,5,8,10,12,15):
                        if len(h)<start+2 or start not in by_k:continue
                        contrast=dict(start_k=start,distribution_tv_improvement=by_k[start]['distribution_tv']-by_k[len(h)]['distribution_tv'])
                        emit('paired_distribution_gain.csv.gz',b|contrast)
                        local_paired.append(dict(config=config,scheme=s['scheme'],**contrast))
            for r in summarize_local(local_fixed,['config','scheme','k_label'],['distribution_tv','prefix_to_full_history_tv','validation_outside_fraction','validation_ambiguous_fraction','training_entropy','observed_historical_cluster_count']):fixed_summary.append(meta|r)
            for r in summarize_local(local_cluster,['config','scheme','k_label'],['unique','cluster_count','supported_cluster_count','largest_share','entropy']):cluster_summary.append(meta|r)
            for r in summarize_local(local_paired,['config','scheme','start_k'],['distribution_tv_improvement']):paired_summary.append(meta|r)
            for r in summarize_local(local_full,['config','scheme'],['unique','non_unique','truncated','cluster_count','entropy']):full_summary.append(meta|r)
    save(out,'pairwise_point_distances.csv.gz',pairs)
    save(out,'context_fixed_taxonomy_summary.csv',fixed_summary)
    save(out,'context_prefix_reclustering_summary.csv',cluster_summary)
    save(out,'context_paired_gain_summary.csv',paired_summary)
    save(out,'context_full_partition_summary.csv',full_summary)
    # 此处只汇总context均值；不把共用历史响应的重复划分当成独立实验。
    for name,rows,axis,values in [
        ('building_fixed_taxonomy_summary.csv',fixed_summary,'k_label',['distribution_tv_mean','validation_outside_fraction_mean','validation_ambiguous_fraction_mean','training_entropy_mean']),
        ('building_paired_gain_summary.csv',paired_summary,'start_k',['distribution_tv_improvement_mean'])]:
        f=pd.DataFrame(rows);keys=['building_id','stage','raw_condition','initialization_kind','config','scheme',axis]
        agg=f.groupby(keys).agg(contexts=('context_key','nunique'),minimum_context_splits=('split_count','min'),maximum_context_splits=('split_count','max'),**{v:(v,'mean') for v in values}).reset_index()
        agg.to_csv(out/name,index=False,float_format='%.12g')
    qa=dict(status='completed',canonical=len(a),point_pattern_computable=len(unit),status_counts=Counter(r['status'] for r in status),
        original_floor_computable=1611,nonempty_invalid_points_retained=True,odd_points_are_not_valid_geometry_assertions=True,
        arbitrary_reverse_order_feature_max_difference=max(permutation_errors),pairwise_rows=len(pairs),streams=dict(streams),
        configs=CONFIGS,replicates=200,schemes=2,partition_cache=str(_partition_graph.cache_info()),
        old_clusters_overwritten=False,new_stopping_rule=False,full_historical_taxonomy_not_online_prefix_clustering=True)
    (out/'RUN_QA.json').write_text(json.dumps(qa,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(qa,ensure_ascii=False,indent=2))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--root',type=Path,default=ROOT);p.add_argument('--out',type=Path)
    args=p.parse_args();run(args.root,args.out or args.root/OUTPUT)
