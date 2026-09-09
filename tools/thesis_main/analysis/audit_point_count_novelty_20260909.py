"""核查点数硬分组、有限历史池中的新点数出现，以及上一轮分簇的口径差异。"""
import json
import math
import sys
from collections import Counter
from itertools import combinations
from pathlib import Path
import numpy as np
import pandas as pd

ROOT=Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:sys.path.insert(0,str(ROOT))
from tools.thesis_main.analysis.order_free_cluster_holdout_20260908 import partition
BASE=ROOT/'analysis_results/unb9_scene_transfer_trial_20260909_v1'
OUT=BASE/'point_count_audit'


def finite_pool_novelty(counts,k):
    counts=list(counts);n=sum(counts)
    if not counts or any(c<=0 or int(c)!=c for c in counts) or not 0<=k<=n:raise ValueError('invalid_counts_or_sample_size')
    denominator=math.comb(n,k)
    def miss(total):return math.comb(n-total,k)/denominator if n-total>=k else 0.
    # ponytail: exact inclusion-exclusion for this small number of observed point-count types; use DP if types grow substantially.
    any_unseen=sum((-1)**(r+1)*sum(miss(sum(group)) for group in combinations(counts,r)) for r in range(1,len(counts)+1))
    return dict(any_unseen_probability=float(np.clip(any_unseen,0,1)),expected_unseen_types=sum(miss(c) for c in counts))


def count_gated_partition(matrix,counts,tau):
    counts=np.asarray(counts);matrix=np.asarray(matrix,float)
    if matrix.shape!=(len(counts),len(counts)):raise ValueError('count_matrix_shape')
    return partition(np.where(counts[:,None]==counts[None,:],matrix,max(31.,tau+1)),tau)


def main():
    OUT.mkdir(exist_ok=True)
    source=ROOT/'analysis_results/uncertainty_cloud_inputs_20260906_v1'
    a=pd.read_csv(source/'annotations.csv.gz',dtype=str,keep_default_na=False)
    raw=[r for r in map(json.loads,(source/'raw_annotation_versions.jsonl').read_text(encoding='utf-8').splitlines()) if str(r['selected_canonical_version']).lower()=='true']
    counts={r['canonical_annotation_id']:len(r['points_1024x512']) for r in raw}
    assert len(raw)==len(counts)==2501 and set(a.canonical_annotation_id)==set(counts)
    status=pd.read_csv(ROOT/'analysis_results/order_free_cluster_holdout_20260908_v1/response_status.csv.gz')
    assert all(counts[r.canonical_annotation_id]==r.raw_endpoint_count for r in status.itertuples())
    local=a[(a.building_id=='uNb9QFRL6hY')&(a.assistance_exposure=='none')].copy()
    assert len(local)==374 and not local.duplicated(['image_id','worker_id']).any()
    local['point_count']=local.canonical_annotation_id.map(counts)
    local=local.merge(status[['canonical_annotation_id','status']],on='canonical_annotation_id',validate='one_to_one')
    local[['image_id','canonical_annotation_id','worker_id','stage','raw_condition','point_count','status']].to_csv(OUT/'response_point_counts.csv.gz',index=False)
    inventory=[];discovery=[];late=[];fixed=[];patterns=[]
    orders=[json.loads(s) for s in (ROOT/'analysis_results/building_holdout_exploration_20260908_v1/census/global_worker_orders.jsonl').read_text(encoding='utf-8').splitlines()]
    pairs=pd.read_csv(ROOT/'analysis_results/order_free_cluster_holdout_20260908_v1/pairwise_point_distances.csv.gz')
    for im,g in local.groupby('image_id'):
        valid=g[g.status=='computable_point_pattern'];hist=Counter(valid.point_count);n=len(valid)
        inventory.append(dict(image_id=im,raw_n=len(g),computable_n=n,point_count_types=len(hist),
            point_count_histogram_json=json.dumps(dict(sorted(hist.items()))),singleton_point_count_types=sum(c==1 for c in hist.values()),
            odd_point_responses=int((valid.point_count%2==1).sum()),empty_responses=int(g.point_count.eq(0).sum()),
            coordinate_invalid_responses=int((g.status!='computable_point_pattern').sum()-g.point_count.eq(0).sum()),dense=len(g)>15))
        for point_count,q in valid.groupby('point_count'):
            patterns.append(dict(image_id=im,point_count=int(point_count),support=len(q),worker_ids_json=json.dumps(q.worker_id.tolist()),canonical_ids_json=json.dumps(q.canonical_annotation_id.tolist())))
        worker_counts=dict(zip(valid.worker_id,valid.point_count))
        for order in orders:
            seq=[worker_counts[w] for w in order['worker_ids'] if w in worker_counts];assert len(seq)==n
            seen=Counter()
            for k,pc in enumerate(seq,1):
                first=seen[pc]==0;seen[pc]+=1
                future=set(seq[k:])-set(seen)
                discovery.append(dict(image_id=im,replicate=order['replicate'],k=k,computable_n=n,
                    added_point_count=int(pc),first_appearance=first,seen_types=len(seen),unseen_types=len(future),
                    supported_types=sum(v>=2 for v in seen.values()),any_later_new_type=bool(future),
                    later_new_type_with_full_support_ge2=any(hist[c]>=2 for c in future),
                    unseen_response_fraction=sum(hist[c] for c in future)/(n-k) if n>k else np.nan))
        for k in [4,10,15,20]:
            if k<n:late.append(dict(image_id=im,k=k,computable_n=n,**finite_pool_novelty(hist.values(),k)))
        if len(g)<=15:continue
        ids=sorted(valid.canonical_annotation_id);pos={x:i for i,x in enumerate(ids)};matrix=np.zeros((n,n))
        pg=pairs[pairs.left_canonical.isin(ids)&pairs.right_canonical.isin(ids)];assert len(pg)==math.comb(n,2)
        for r in pg.itertuples():
            i,j=pos[r.left_canonical],pos[r.right_canonical];matrix[i,j]=matrix[j,i]=r.ospa30
        for tau in [3,6,12]:
            for name,r in [('previous_soft_count',partition(matrix,tau)),('hard_equal_count',count_gated_partition(matrix,[counts[x] for x in ids],tau))]:
                groups=[[ids[i] for i in cluster] for cluster in r['clusters']]
                mixed=sum(len({counts[x] for x in cluster})>1 for cluster in groups)
                if name=='hard_equal_count':assert mixed==0
                fixed.append(dict(image_id=im,tau=tau,method=name,n=n,status=r['status'],cluster_count=len(groups) if r['status']=='unique' else np.nan,
                    mixed_point_count_clusters=mixed if r['status']=='unique' else np.nan,
                    cluster_point_counts_json=json.dumps([[counts[x] for x in cluster] for cluster in groups]),clusters_json=json.dumps(groups)))
    inv=pd.DataFrame(inventory);inv.to_csv(OUT/'image_point_count_inventory.csv',index=False)
    pd.DataFrame(patterns).to_csv(OUT/'point_count_support.csv',index=False)
    d=pd.DataFrame(discovery);d.to_csv(OUT/'point_count_discovery_replay.csv.gz',index=False)
    summary=d.groupby(['image_id','k','computable_n']).agg(replicates=('k','size'),new_type_on_this_person_rate=('first_appearance','mean'),
        mean_seen_types=('seen_types','mean'),mean_unseen_types=('unseen_types','mean'),
        any_later_new_type_rate=('any_later_new_type','mean'),later_new_type_with_full_support_ge2_rate=('later_new_type_with_full_support_ge2','mean')).reset_index()
    summary.to_csv(OUT/'point_count_discovery_summary.csv',index=False)
    pd.DataFrame(late).to_csv(OUT/'exact_late_point_count_discovery.csv',index=False)
    pd.DataFrame(fixed).to_csv(OUT/'full_pool_count_gated_partitions.csv',index=False)
    old=pd.read_csv(BASE/'stability/all_integer_prefixes.csv.gz');audit=[]
    for r in old.itertuples():
        groups=json.loads(r.clusters_json);mixed=sum(len({counts[x] for x in g})>1 for g in groups)
        audit.append(dict(image_id=r.image_id,tau=r.tau,unique=r.status=='unique',mixed_prefix=mixed>0,mixed_clusters=mixed))
    old_audit=pd.DataFrame(audit).groupby(['image_id','tau']).agg(prefix_rows=('unique','size'),unique_prefixes=('unique','sum'),mixed_prefixes=('mixed_prefix','sum'),mixed_clusters=('mixed_clusters','sum')).reset_index()
    old_audit.to_csv(OUT/'previous_mixed_cluster_audit.csv',index=False)
    rows=pd.read_csv(BASE/'stability/stability_records.csv.gz')
    ws=pd.read_csv(BASE/'worker_splits.csv.gz');seqs={(r.image_id,r.scheme,r.replicate):[counts[x] for x in json.loads(r.history_ids_json)] for r in ws.itertuples()}
    novel=[]
    for r in rows.itertuples():
        seq=seqs[(r.image_id,r.scheme,r.replicate)];novel.append(bool(set(seq[r.k:r.horizon])-set(seq[:r.k])))
    rows['new_point_count_after_k']=novel;previous=[]
    keys=['image_id','scheme','tau','horizon']
    for eps in [5,10,20]:
        z=rows.assign(previous_stable=rows['state_'+str(eps)].eq('stable'),stable_despite_new_point_count=rows['state_'+str(eps)].eq('stable')&rows.new_point_count_after_k)
        q=z.groupby(keys).agg(candidate_windows=('k','size'),previous_stable=('previous_stable','sum'),stable_despite_new_point_count=('stable_despite_new_point_count','sum')).reset_index();q['tolerance_pp']=eps;previous.append(q)
    pd.concat(previous).to_csv(OUT/'previous_stability_with_new_point_counts.csv',index=False)
    v5=pd.read_csv(ROOT/'analysis_results/full_uncertainty_data_mining_20260821_v5/C1_K22_PREFIX_REPLAY.csv')
    qa=dict(status='passed',canonical_point_counts_checked=2501,local_raw_responses=len(local),local_images=len(inv),local_computable=int(inv.computable_n.sum()),
        integer_count_discovery_rows=len(d),all_replays_reach_full_observed_types=bool((summary[summary.k==summary.computable_n].mean_unseen_types==0).all()),
        old_prefix_rows_read=len(old),old_stability_windows_read=len(rows),full_pool_partition_comparisons=len(fixed),
        v5_prefix_sampling='k enters sample seed: k=5 and k=8 draws are not nested person sequences',v5_prefix_rows=len(v5),
        scope='所有阶段统一；27图盘点；高人数12图的完整点集分区对照；点数新类统计包括单例，另存重复支持。',
        limitations='只核查点数新类与完整样本分区；未以硬点数门槛重跑完整逐人几何分簇及跨图人数预测；有限历史池的穷尽不代表未来总体无新类。',
        source_annotations_changed=False,formal_protocol_changed=False)
    (OUT/'AUDIT_QA.json').write_text(json.dumps(qa,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(qa,ensure_ascii=False),flush=True)
    print(inv[inv.dense][['image_id','computable_n','point_count_types','point_count_histogram_json']].to_string(index=False),flush=True)


if __name__=='__main__':main()
