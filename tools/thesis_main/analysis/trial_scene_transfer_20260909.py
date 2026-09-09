"""单楼无预标注图的分组预测试算；阶段只作来源，不参与分组或加权。"""
import csv
import gzip
import json
import math
import sys
from itertools import combinations
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.optimize import linear_sum_assignment

ROOT=Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:sys.path.insert(0,str(ROOT))
from tools.thesis_main.analysis.order_free_cluster_holdout_20260908 import unit_points, point_distances

OUT=ROOT/'analysis_results/unb9_scene_transfer_trial_20260909_v1'
BASE=ROOT/'analysis_results/uncertainty_cloud_inputs_20260906_v1'
OLD=ROOT/'analysis_results/order_free_cluster_holdout_20260908_v1'
BUILDING='uNb9QFRL6hY'
NODES=[2,3,5,8,10,12,15]
SCHEMES={'two_thirds':2/3,'sixty_percent':.6,'half':.5}


def transport(cost):
    """Exact equal-mass empirical transport via integer-expanded assignment."""
    cost=np.asarray(cost,float)
    if cost.ndim!=2 or min(cost.shape)==0 or not np.isfinite(cost).all() or (cost<0).any():
        raise ValueError('invalid_transport_cost')
    n,m=cost.shape;g=math.gcd(n,m)
    expanded=np.repeat(np.repeat(cost,m//g,axis=0),n//g,axis=1)
    i,j=linear_sum_assignment(expanded)
    return float(expanded[i,j].mean())


def image_splits(images):
    if len(set(images))!=len(images):raise ValueError('duplicate_image')
    for n in range(1,len(images)):
        for source in combinations(images,n):
            yield list(source),[x for x in images if x not in source]


def predict(source,values):
    return np.mean([values[i] for i in source],axis=0)


def save(name,data):
    pd.DataFrame(data).to_csv(OUT/name,index=False)


def main():
    OUT.mkdir(exist_ok=True,parents=True)
    plan=json.loads((OUT/'METHOD_PLAN.json').read_text(encoding='utf-8'))
    assert '阶段、原条件和旧资格只保留' in plan['scope']
    a=pd.read_csv(BASE/'annotations.csv.gz',dtype=str,keep_default_na=False)
    assert a.canonical_annotation_id.is_unique
    st=pd.read_csv(OLD/'response_status.csv.gz',dtype=str,keep_default_na=False).set_index('canonical_annotation_id')
    a['computable']=a.canonical_annotation_id.map(st.status).eq('computable_point_pattern')
    roster={b:set(g.worker_id) for b,g in a.groupby('building_id')}
    hand=a[a.assistance_exposure=='none'].copy()
    coverage=hand.groupby(['image_id','building_id','context_key'],sort=True).agg(
        raw_n=('worker_id','nunique'),computable_n=('computable','sum'),
        source_stage=('stage','first'),source_condition=('raw_condition','first')).reset_index()
    local=coverage[coverage.building_id==BUILDING].copy()
    # This building has one unassisted context per image: no cross-stage duplicate worker pooling.
    assert local.image_id.is_unique and len(local)==27
    selected=coverage[(coverage.building_id==BUILDING)|(coverage.raw_n>15)].copy()
    assert selected.image_id.is_unique
    keep=set(selected.context_key)
    hand=hand[hand.context_key.isin(keep)]
    assert not hand.duplicated(['image_id','worker_id']).any()
    assert hand[hand.building_id==BUILDING].shape[0]==374
    local['dense']=local.raw_n>15
    save('image_inventory.csv',local)
    save('reference_image_inventory.csv',selected[selected.building_id!=BUILDING])
    raw={v['canonical_annotation_id']:v for v in map(json.loads,(BASE/'raw_annotation_versions.jsonl').read_text(encoding='utf-8').splitlines())
         if str(v['selected_canonical_version']).lower()=='true'}
    pairs=pd.read_csv(OLD/'pairwise_point_distances.csv.gz')
    matrices={};ids={};people={};dispersion={};max_error=0.;audited_pairs=0
    for c,g in hand.groupby('context_key'):
        good=g[g.computable].sort_values('worker_id',key=lambda x:x.astype(int))
        image=g.image_id.iloc[0];aid=good.canonical_annotation_id.tolist()
        ids[image]=aid;people[image]=dict(zip(good.worker_id,range(len(good))))
        matrix=np.zeros((len(aid),len(aid)));pos={x:i for i,x in enumerate(aid)}
        pg=pairs[pairs.context_key==c]
        assert len(pg)==len(aid)*(len(aid)-1)//2
        units={x:unit_points(raw[x]['points_1024x512']) for x in aid} if g.building_id.iloc[0]==BUILDING else {}
        for row in pg.itertuples():
            i,j=pos[row.left_canonical],pos[row.right_canonical]
            matrix[i,j]=matrix[j,i]=row.ospa30
            if units:
                actual=point_distances(units[row.left_canonical],units[row.right_canonical])['ospa30']
                max_error=max(max_error,abs(actual-row.ospa30));audited_pairs+=1
        assert np.isfinite(matrix).all()
        matrices[image]=matrix
        dispersion[image]=float(matrix[np.triu_indices(len(aid),1)].mean())
    assert max_error<1e-8
    save('image_disagreement.csv',[dict(image_id=i,mean_pair_distance_degrees=x) for i,x in dispersion.items()])
    print(f'身份覆盖：目标27图/374响应；目标点距独立复算{audited_pairs}对，最大差{max_error:.3g}',flush=True)

    orders=[json.loads(x) for x in (ROOT/'analysis_results/building_holdout_exploration_20260908_v1/census/global_worker_orders.jsonl').read_text(encoding='utf-8').splitlines()]
    response_rows=[];support_rows=[]
    for ordinal,row in enumerate(selected.itertuples(),1):
        im=row.image_id;matrix=matrices[im];pm=people[im]
        for scheme,fraction in SCHEMES.items():
            for order in orders:
                ordered=[w for w in order['worker_ids'] if w in roster[row.building_id]]
                cut=math.floor(len(ordered)*fraction)
                h=[pm[w] for w in ordered[:cut] if w in pm];v=[pm[w] for w in ordered[cut:] if w in pm]
                assert not set(h)&set(v) and len(h)+len(v)==len(pm)
                base=dict(image_id=im,scheme=scheme,replicate=order['replicate'],history_n=len(h),validation_n=len(v))
                support_rows.append(base|dict(history_ids_json=json.dumps([ids[im][x] for x in h]),validation_ids_json=json.dumps([ids[im][x] for x in v])))
                if len(v)<2:continue
                for k in NODES:
                    if k<=len(h):response_rows.append(base|dict(k=k,transport_degrees=transport(matrix[np.ix_(h[:k],v)])))
        if ordinal%10==0:print(f'完成{ordinal}/{len(selected)}图人员重排',flush=True)
    save('worker_splits.csv.gz',support_rows)
    save('resampled_curves.csv.gz',response_rows)
    values=pd.DataFrame(response_rows);support=pd.DataFrame(support_rows)
    curves=[];windows=[]
    for (im,scheme),g in support.groupby(['image_id','scheme']):
        rows=values[(values.image_id==im)&(values.scheme==scheme)]
        for window in [3,10,15]:
            eligible=g[(g.history_n>=window)&(g.validation_n>=2)]
            windows.append(dict(image_id=im,scheme=scheme,window=window,eligible_replicates=len(eligible),all_replicates=len(g)))
            q=rows[rows.replicate.isin(eligible.replicate)&(rows.k<=window)]
            assert len(q)==len(eligible)*sum(k<=window for k in NODES)
            for k,kg in q.groupby('k'):
                curves.append(dict(image_id=im,scheme=scheme,window=window,k=k,
                    mean=kg.transport_degrees.mean(),q10=kg.transport_degrees.quantile(.1),q90=kg.transport_degrees.quantile(.9),
                    replicates=len(kg)))
    curve=pd.DataFrame(curves);save('mean_curves.csv',curve);save('window_support.csv',windows)

    all_images=sorted(local.image_id);dense=sorted(local.loc[local.dense,'image_id'])
    assert len(dense)==12
    folds=[]
    for s,t in image_splits(dense):folds.append(dict(panel='dense12',source=s,target=t))
    rng=np.random.default_rng(20260909)
    for n in [4,9,13]:
        seen=set()
        while len(seen)<200:
            s=tuple(sorted(rng.choice(all_images,n,replace=False)))
            t=[i for i in all_images if i not in s]
            if len(set(s)&set(dense))>=2 and len(set(t)&set(dense))>=2:seen.add(s)
        for s in sorted(seen):
            t=[i for i in all_images if i not in s]
            folds.extend([dict(panel='all27',source=list(s),target=t),dict(panel='all27',source=t,target=list(s))])
    save('image_splits.csv',[dict(fold_id=i,panel=f['panel'],source_n=len(f['source']),target_n=len(f['target']),
        source_images_json=json.dumps(f['source']),target_images_json=json.dumps(f['target'])) for i,f in enumerate(folds)])
    external=set(selected.loc[selected.building_id!=BUILDING,'image_id'])
    predictions=[]
    for (scheme,window),cg in curve.groupby(['scheme','window']):
        nodes=sorted(map(int,cg.k.unique()));vectors={im:g.sort_values('k')['mean'].to_numpy() for im,g in cg.groupby('image_id')}
        outside=[i for i in external if i in vectors]
        baseline=predict(outside,vectors)
        for fid,fold in enumerate(folds):
            if fold['panel']=='all27' and window!=3:continue
            s,t=fold['source'],fold['target']
            assert not set(s)&set(t)
            if not all(i in vectors for i in s+t):continue
            predicted=predict(s,vectors);observed=predict(t,vectors)
            target_values=np.array([vectors[i] for i in t])
            error=np.abs(target_values-predicted).mean();base_error=np.abs(target_values-baseline).mean()
            row=dict(fold_id=fid,panel=fold['panel'],source_n=len(s),target_n=len(t),scheme=scheme,window=window,
                source_prediction_json=json.dumps(predicted.tolist()),target_group_curve_json=json.dumps(observed.tolist()),
                outside_baseline_json=json.dumps(baseline.tolist()),baseline_images=len(outside),nodes_json=json.dumps(nodes),
                target_image_MAE=error,baseline_image_MAE=base_error,mae_gain=base_error-error,
                target_group_MAE=np.abs(observed-predicted).mean(),baseline_group_MAE=np.abs(observed-baseline).mean(),
                disagreement_prediction=float(predict(s,dispersion)),disagreement_target=float(predict(t,dispersion)),
                disagreement_image_MAE=float(np.mean([abs(dispersion[i]-predict(s,dispersion)) for i in t])))
            predictions.append(row)
    pred=pd.DataFrame(predictions);save('group_predictions.csv.gz',pred)
    summary=pred.groupby(['panel','source_n','target_n','scheme','window']).agg(
        image_splits=('fold_id','size'),target_image_MAE=('target_image_MAE','mean'),baseline_image_MAE=('baseline_image_MAE','mean'),
        mae_gain=('mae_gain','mean'),target_group_MAE=('target_group_MAE','mean'),baseline_group_MAE=('baseline_group_MAE','mean'),
        gain_q10=('mae_gain',lambda x:x.quantile(.1)),gain_q90=('mae_gain',lambda x:x.quantile(.9))).reset_index()
    save('prediction_summary.csv',summary)
    qa=dict(status='passed',local_images=len(local),local_responses=int(local.raw_n.sum()),local_computable=int(local.computable_n.sum()),
        dense_images=len(dense),external_images=len(external),audited_local_point_pairs=audited_pairs,max_pair_distance_error=max_error,
        worker_split_records=len(support),resampled_curve_records=len(values),image_splits=len(folds),prediction_records=len(pred),
        no_image_overlap=True,stage_used_for_selection_or_weighting=False,assisted_responses_used=False,
        absolute_distance_onset_withdrawn=True,source_geometry_modified=False,external_new_building_validation=False)
    (OUT/'RUN_QA.json').write_text(json.dumps(qa,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(qa,ensure_ascii=True),flush=True)


if __name__=='__main__':main()
