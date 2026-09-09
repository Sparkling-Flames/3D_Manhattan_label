"""独立回读同building留出输出；不调用模拟的拟合/前缀函数。"""
from __future__ import annotations
import argparse
import gzip
import json
import math
from pathlib import Path
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
OUTPUT = 'analysis_results/building_holdout_exploration_20260908_v1'


def audit(out):
    index = pd.read_csv(out/'census/canonical_index.csv.gz', dtype=str, keep_default_na=False)
    versions = pd.read_csv(out/'census/annotation_version_lineage.csv.gz', dtype=str, keep_default_na=False)
    assert index.canonical_annotation_id.is_unique and not index.duplicated(['context_key','worker_id']).any()
    assert versions.raw_annotation_version_id.is_unique and set(versions.canonical_annotation_id)==set(index.canonical_annotation_id)
    assert len(versions)-len(index)==12
    qa = json.loads((out/'SIMULATION_QA.json').read_text(encoding='utf-8'))
    people = pd.read_csv(out/'census/worker_splits.csv.gz', dtype=str)
    orders = [json.loads(x) for x in (out/'census/global_worker_orders.jsonl').read_text(encoding='utf-8').splitlines()]
    rng = np.random.default_rng(20260908)
    roster = sorted(index.worker_id.unique(), key=int)
    for i, row in enumerate(orders):
        assert row['replicate']==i and row['worker_ids']==list(map(str,rng.permutation(list(map(int,roster)))))
    building_workers = index.groupby('building_id').worker_id.agg(set).to_dict()
    splits = {}
    for row in people.to_dict('records'):
        h = json.loads(row['history_worker_ids_json']); v = json.loads(row['validation_worker_ids_json'])
        all_workers = [w for w in orders[int(row['replicate'])]['worker_ids'] if w in building_workers[row['building_id']]]
        fraction = {'two_thirds':2/3,'sixty_percent':.6}[row['scheme']]
        cut = math.floor(fraction*len(all_workers))
        assert h==all_workers[:cut] and v==all_workers[cut:] and not set(h)&set(v)
        splits[row['split_id']] = (h,v)
    assert len(splits)==len(people)==len(building_workers)*200*2
    status = pd.read_csv(out/'response_metric_status.csv.gz', dtype=str)
    assert not status.duplicated(['canonical_annotation_id','metric']).any()
    assert len(status)==len(index)*3
    assert not status.raw_coordinates_changed.str.lower().eq('true').any()
    assert not status.raw_adjacency_changed.str.lower().eq('true').any()
    by_id = index.set_index('canonical_annotation_id')
    points = status.drop_duplicates('canonical_annotation_id').set_index('canonical_annotation_id').raw_point_count.astype(int).to_dict()
    valid = {m:set(g.loc[g.status.str.startswith('computable'),'canonical_annotation_id']) for m,g in status.groupby('metric')}
    shared = valid['original_floor'] & valid['legacy_linear']
    contexts, matrices = {}, {}
    pairs = pd.read_csv(out/'pairwise_distances.csv.gz')
    assert pairs.distance.between(0,1).all()
    assert not pairs.duplicated(['metric','left_canonical','right_canonical']).any()
    assert (pairs.left_canonical.map(by_id.context_key)==pairs.context_key).all()
    assert (pairs.right_canonical.map(by_id.context_key)==pairs.context_key).all()
    edge = {(r.metric,r.left_canonical,r.right_canonical):r.distance for r in pairs.itertuples()}
    for c,g in index.groupby('context_key'):
        raw = dict(zip(g.worker_id,g.canonical_annotation_id))
        for metric in valid:
            for cohort in (['all_responses'] if metric=='raw_endpoint_count' else ['method_available','common_geometry']):
                eligible = shared if cohort=='common_geometry' else valid[metric]
                mapping = {w:a for w,a in raw.items() if a in eligible}
                ids = sorted(mapping.values())
                matrix = np.zeros((len(ids),len(ids)))
                for i,a in enumerate(ids):
                    for j,b in enumerate(ids[:i]):
                        value = edge.get((metric,a,b),edge.get((metric,b,a)))
                        assert value is not None
                        matrix[i,j]=matrix[j,i]=value
                key = (c,metric,cohort)
                contexts[key]=(mapping,set(raw))
                matrices[key]=(matrix,{a:i for i,a in enumerate(ids)})
    support_n = 0
    for chunk in pd.read_csv(out/'context_split_support.csv.gz', chunksize=30000):
        for r in chunk.itertuples():
            mapping,raw_workers=contexts[(r.context_key,r.metric,r.cohort)]
            h,v=splits[r.split_id]
            nh,nv=len(set(h)&mapping.keys()),len(set(v)&mapping.keys())
            expected='available' if min(nh,nv)>=2 else 'history_lt2' if nh<2 else 'validation_lt2'
            assert (r.history_n,r.validation_n,r.raw_history_n,r.raw_validation_n,r.status)==(nh,nv,len(set(h)&raw_workers),len(set(v)&raw_workers),expected)
        support_n+=len(chunk)
    assert support_n==qa['streams']['context_split_support.csv.gz']==270*5*400

    def data(r):
        key=(r.context_key,r.metric,r.cohort)
        mapping,_=contexts[key]; matrix,positions=matrices[key]; h,v=splits[r.split_id]
        ha=[mapping[w] for w in h if w in mapping]; va=[mapping[w] for w in v if w in mapping]
        return matrix,[positions[a] for a in ha],[positions[a] for a in va],ha,va

    maxima=[]; sampled=0; prefix_count=0; rounded_ties=[]
    for chunk in pd.read_csv(out/'heldout_prefix_draws.csv.gz', chunksize=50000):
        assert chunk.k.ge(2).all() and chunk.k.le(chunk.history_n).all() and chunk.validation_n.ge(2).all()
        assert np.allclose(chunk.absolute_disagreement_gap, abs(chunk.history_prefix_d-chunk.validation_d),atol=1e-10)
        assert np.allclose(chunk.signed_disagreement_gap, chunk.history_prefix_d-chunk.validation_d,atol=1e-10)
        assert (chunk.is_full_history==(chunk.k==chunk.history_n)).all()
        for r in chunk[chunk.replicate.isin([0,199])].itertuples():
            matrix,h,v,ha,va=data(r); hh=matrix[np.ix_(h,h)]; sub=matrix[np.ix_(h[:r.k],h[:r.k])]
            estimated=sub[np.triu_indices(r.k,1)].mean()
            target=matrix[np.ix_(v,v)][np.triu_indices(len(v),1)].mean()
            variance=(2*np.var(hh)+4*(r.k-2)*np.var(hh.mean(axis=1)))/(r.k*(r.k-1))
            errors=[abs(estimated-r.history_prefix_d),abs(target-r.validation_d),abs(math.sqrt(max(0,variance))-r.train_plugin_sd)]
            if r.metric!='raw_endpoint_count':
                pick=int(np.argmin(sub.sum(axis=1)))
                actual=ha.index(r.medoid_canonical_id)
                assert actual<r.k
                excess=float(sub.sum(axis=1)[actual]-sub.sum(axis=1)[pick])
                assert excess<1e-10
                if actual!=pick:
                    rounded_ties.append(dict(context_key=r.context_key,metric=r.metric,cohort=r.cohort,split_id=r.split_id,
                                             k=r.k,serialized_objective_excess=excess,recorded_medoid=r.medoid_canonical_id,
                                             reread_argmin=ha[pick]))
                pick=actual  # 12有效位距离表可能把浮点近并列转成并列；核验实际所选最小值及其验证距离。
                errors.append(abs(matrix[h[pick],v].mean()-r.medoid_validation_distance))
            else:
                a=np.array([points[x] for x in ha[:r.k]]); b=np.array([points[x] for x in va])
                tv=sum(abs(np.mean(a==x)-np.mean(b==x)) for x in np.union1d(a,b))/2
                errors.append(abs(tv-r.count_distribution_tv))
            maxima.extend(errors); sampled+=1
        prefix_count+=len(chunk)
    assert prefix_count==qa['streams']['heldout_prefix_draws.csv.gz'] and max(maxima)<1e-10
    candidate_count=0; sampled_candidates=0
    for chunk in pd.read_csv(out/'precision_candidates.csv.gz',chunksize=50000):
        for r in chunk[chunk.replicate.isin([0,199])].itertuples():
            matrix,h,v,_,_=data(r); hh=matrix[np.ix_(h,h)]
            candidate=next((k for k in range(2,21) if math.sqrt(max(0,(2*np.var(hh)+4*(k-2)*np.var(hh.mean(axis=1)))/(k*(k-1))))<=r.tolerance),None) if len(h)>=4 else None
            expected='history_lt4' if len(h)<4 else 'not_reached_by20' if candidate is None else 'candidate'
            assert r.status==expected
            assert (candidate is None and pd.isna(r.predicted_k)) or candidate==r.predicted_k
            assert r.candidate_within_history==(candidate is not None and candidate<=len(h))
            assert r.candidate_within_validation==(candidate is not None and candidate<=len(v))
            sampled_candidates+=1
        candidate_count+=len(chunk)
    assert candidate_count==qa['streams']['precision_candidates.csv.gz']
    contrast_count=0
    for chunk in pd.read_csv(out/'paired_gain_draws.csv.gz',chunksize=50000):
        assert (chunk.end_history_n>=chunk.start_k+2).all()
        assert (chunk.end_history_n==chunk.history_n).all()
        contrast_count+=len(chunk)
    assert contrast_count==qa['streams']['paired_gain_draws.csv.gz']
    result=dict(status='passed',canonical=len(index),versions=len(versions),worker_splits=len(people),
                support_rows_fully_recomputed=support_n,prefix_rows_arithmetic_checked=prefix_count,
                prefix_rows_independently_recomputed=sampled,candidate_rows_independently_recomputed=sampled_candidates,
                sample_rule='all contexts/metrics/cohorts/schemes at replicates 0 and 199',
                maximum_numeric_difference=max(maxima),paired_gain_rows=contrast_count,
                serialized_medoid_near_ties=len(rounded_ties),medoid_objective_numeric_tolerance=1e-10,
                candidate_rows=candidate_count,geometry_pair_rows=len(pairs),old_eligibility_filter=False,
                limitations='几何函数沿用已审计读法；本次独立重算人员连接、矩阵统计及训练候选，不重新裁定几何或人工意见')
    (out/'INDEPENDENT_AUDIT.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    pd.DataFrame(rounded_ties,columns=['context_key','metric','cohort','split_id','k','serialized_objective_excess','recorded_medoid','reread_argmin']).to_csv(out/'serialized_medoid_near_ties.csv',index=False)
    print(json.dumps(result,ensure_ascii=False,indent=2))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--root',type=Path,default=ROOT);p.add_argument('--out',type=Path)
    a=p.parse_args();audit(a.out or a.root/OUTPUT)
