"""重算单楼逐人前缀的单/多簇稳定及留出图验证；不按阶段区分。"""
import json
import math
import sys
from itertools import combinations
from pathlib import Path
import numpy as np
import pandas as pd

ROOT=Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:sys.path.insert(0,str(ROOT))
from tools.thesis_main.analysis.order_free_cluster_holdout_20260908 import partition, fixed_distribution

PREVIOUS=ROOT/'analysis_results/unb9_scene_transfer_trial_20260909_v1'
OUT=PREVIOUS/'stability'
EPSILONS=[.05,.10,.20]


def partition_change(left,right,k,j):
    a={x:i for i,g in enumerate(left) for x in g};b={x:i for i,g in enumerate(right) for x in g}
    if len(a)!=k or len(b)!=j or not set(a)<=set(b):raise ValueError('invalid_partition_members')
    common=set(a)
    membership=sum((a[x]==a[y])!=(b[x]==b[y]) for x,y in combinations(sorted(common),2))/math.comb(k,2) if k>=2 else 0.
    shares=.5*sum(abs(len(common&set(g))/k-len(g)/j) for g in right)
    return dict(membership_change=membership,share_change=shares,
        new_supported_clusters=sum(len(g)>=2 and not common.intersection(g) for g in right))


def envelope(trajectory,k,horizon):
    if horizon-k<3:raise ValueError('need_at_least_three_later_responses')
    statuses=[trajectory[j]['status'] for j in range(k,horizon+1)]
    if any(s!='unique' for s in statuses):
        return dict(status='unresolved',max_membership_change=np.nan,max_share_change=np.nan,max_new_supported_clusters=np.nan)
    changes=[partition_change(trajectory[k]['clusters'],trajectory[j]['clusters'],k,j) for j in range(k+1,horizon+1)]
    return dict(status='evaluated',max_membership_change=max(r['membership_change'] for r in changes),
        max_share_change=max(r['share_change'] for r in changes),max_new_supported_clusters=max(r['new_supported_clusters'] for r in changes))


def stable_state(e,epsilon):
    if e['status']!='evaluated':return 'unknown'
    return 'stable' if e['max_membership_change']<=epsilon+1e-12 and e['max_share_change']<=epsilon+1e-12 and e['max_new_supported_clusters']==0 else 'changing'


def save(name,rows):
    pd.DataFrame(rows).to_csv(OUT/name,index=False)


def summarize(curves):
    images=sorted(curves.image_id.unique())
    onsets=[]
    image_folds=pd.read_csv(PREVIOUS/'image_splits.csv');image_folds=image_folds[image_folds.panel=='dense12']
    fold_rows=image_folds.to_dict('records')
    predictions=[]
    for key,c in curves.groupby(['scheme','tau','horizon','tolerance_pp']):
        vectors={im:g.sort_values('k') for im,g in c.groupby('image_id')}
        nodes=sorted(c.k.unique())
        assert set(vectors)==set(images)
        for rate in [.5,.8,.9]:
            for im,g in vectors.items():
                yes=g[g.stable_lower>=rate-1e-12];possible=g[g.stable_upper>=rate-1e-12]
                onset=int(yes.k.iloc[0]) if len(yes) else np.nan
                onsets.append(dict(zip(['scheme','tau','horizon','tolerance_pp'],key))|dict(image_id=im,repeat_rate=rate,
                    onset=onset,earliest_possible=int(possible.k.iloc[0]) if len(possible) else np.nan,
                    status='observed_candidate' if len(yes) else 'unresolved_partitions' if len(possible) else 'not_reached_in_window'))
            for f in fold_rows:
                s=json.loads(f['source_images_json']);t=json.loads(f['target_images_json']);assert not set(s)&set(t)
                predicted=np.mean([vectors[i].stable_lower.to_numpy() for i in s],axis=0)
                target_lower=np.array([vectors[i].stable_lower.to_numpy() for i in t]);target_upper=np.array([vectors[i].stable_upper.to_numpy() for i in t])
                ix=np.flatnonzero(predicted>=rate-1e-12);j=int(ix[0]) if len(ix) else None
                actual=[]
                for i in t:
                    possible=np.flatnonzero(vectors[i].stable_lower.to_numpy()>=rate-1e-12)
                    actual.append(int(nodes[possible[0]]) if len(possible) else None)
                predictions.append(dict(zip(['scheme','tau','horizon','tolerance_pp'],key))|dict(fold_id=f['fold_id'],source_n=len(s),target_n=len(t),repeat_rate=rate,
                    predicted_onset=int(nodes[j]) if j is not None else np.nan,target_onsets_json=json.dumps(actual),
                    target_image_curve_MAE=np.abs(target_lower-predicted).mean(),target_group_curve_MAE=np.abs(target_lower.mean(axis=0)-predicted).mean(),
                    target_reached_fraction=float(np.mean(target_lower[:,j]>=rate-1e-12)) if j is not None else np.nan,
                    target_unknown_fraction=float(np.mean((target_lower[:,j]<rate-1e-12)&(target_upper[:,j]>=rate-1e-12))) if j is not None else np.nan,
                    target_stable_lower_at_prediction=float(target_lower[:,j].mean()) if j is not None else np.nan,
                    validation_confirmed_lower_at_prediction=float(np.mean([vectors[i].validation_confirmed_lower.iloc[j] for i in t])) if j is not None else np.nan,
                    onset_MAE_on_both_reached=float(np.mean([abs(int(nodes[j])-n) for n in actual if n is not None])) if j is not None and any(n is not None for n in actual) else np.nan))
    save('image_onset_candidates.csv',onsets)
    pred=pd.DataFrame(predictions);save('image_group_stability_predictions.csv.gz',pred)
    pred['prediction_reached']=pred.predicted_onset.notna()
    grouped=pred.groupby(['scheme','tau','horizon','tolerance_pp','repeat_rate','source_n','target_n']).agg(
        image_splits=('fold_id','size'),prediction_reached_fraction=('prediction_reached','mean'),predicted_onset_mean=('predicted_onset','mean'),
        target_reached_fraction=('target_reached_fraction','mean'),target_unknown_fraction=('target_unknown_fraction','mean'),
        target_stable_lower_at_prediction=('target_stable_lower_at_prediction','mean'),
        validation_confirmed_lower_at_prediction=('validation_confirmed_lower_at_prediction','mean'),
        onset_MAE_on_both_reached=('onset_MAE_on_both_reached','mean'),
        target_image_curve_MAE=('target_image_curve_MAE','mean'),target_group_curve_MAE=('target_group_curve_MAE','mean')).reset_index()
    save('transfer_summary.csv',grouped)
    return len(pred)


def main():
    OUT.mkdir(parents=True,exist_ok=True)
    plan=dict(question='留出图是否在与源图相近人数后形成稳定单簇或多簇',
        scope='所有阶段统一；原始人数>15的12张无预标注图主探索；15张5–6人图只保留盘点，不按旧资格或目标结果筛图',
        point_representation='原有OSPA30无序点集；3/6/12度只用于划分点集簇的分辨尺度，不是稳定人数过线门槛',
        workers='沿用每图200次全局一致人员顺序，2/3、60%、50%比例',
        horizons=[10,15],prefixes='每个整数人数1至观察窗口；候选k后至少还观察3个历史人员，不用完整自身终点当收敛',
        envelopes='比较k与每个后续j直至窗口终点：原k人同簇关系变化比例；在后续簇定义下前k与前j的份额TV；是否出现前k未见且j时至少两人支持的新簇',
        unknown='任一所需分区非唯一或搜索截断时稳定状态unknown，不作为已知changing。稳定率下界用全体人数合格排列作分母，上界再加unknown。',
        candidate_tolerances=EPSILONS,tolerance_meaning='关系变化比例和份额TV均不超过5/10/20个百分点，且无新增多人支持簇；探索性敏感性，不是正式停止定义',
        candidate_repeat_rates=[.5,.8,.9],repeat_rate_meaning='均为重复历史人员排列上的稳定下界，不是总体概率或置信度；列示首次达到及未达到',
        heldout_people='在历史窗口末加入全部独立留出的验证响应，再分簇核对与前k的关系、份额和新簇；另存验证响应本身的TV/outside/ambiguous',
        transfer='沿用12图4094种有向互补划分，源组平均稳定率曲线预测目标图；目标结果不参与源组预测；不使用阶段',
        reference='只用来源图统计做基准：所有目标图统一预测为源组均值；不新加复杂模型。不宣称新楼或新人泛化。',
        boundary='本轮是新增独立人员回放，不是同一人迭代修改；簇稳定不等于点集几何完全不变或布局正确；历史复核使用后续响应确定稳定起点，非在线可执行规则。',
        old_absolute_thresholds='撤回2/4/6度绝对运输误差作为人数稳定性诊断，旧运输曲线只保留为不同问题的计算证据')
    (OUT/'METHOD_PLAN.json').write_text(json.dumps(plan,ensure_ascii=False,indent=2),encoding='utf-8')
    inv=pd.read_csv(PREVIOUS/'image_inventory.csv')
    images=sorted(inv.loc[inv.dense,'image_id']);assert len(images)==12
    support=pd.read_csv(PREVIOUS/'worker_splits.csv.gz');support=support[support.image_id.isin(images)]
    pairs=pd.read_csv(ROOT/'analysis_results/order_free_cluster_holdout_20260908_v1/pairwise_point_distances.csv.gz')
    trajectories=[];records=[];support_rows=[]
    for ordinal,im in enumerate(images,1):
        sg=support[support.image_id==im]
        allids=sorted(set(x for r in sg.itertuples() for name in ('history_ids_json','validation_ids_json') for x in json.loads(getattr(r,name))))
        pos={x:i for i,x in enumerate(allids)}
        pg=pairs[pairs.context_key.str.contains(im,regex=False)]
        assert len(pg)==len(allids)*(len(allids)-1)//2
        matrix=np.zeros((len(allids),len(allids)))
        for r in pg.itertuples():
            i,j=pos[r.left_canonical],pos[r.right_canonical];matrix[i,j]=matrix[j,i]=r.ospa30
        cache={}
        def cluster(indices,tau):
            key=(tuple(sorted(indices)),tau)
            if key not in cache:
                ix=list(key[0]);r=partition(matrix[np.ix_(ix,ix)],tau)
                cache[key]=dict(status=r['status'],clusters=[[ix[j] for j in g] for g in r['clusters']],
                    candidate_partition_count=r['candidate_partition_count'])
            return cache[key]
        for row in sg.itertuples():
            h=[pos[x] for x in json.loads(row.history_ids_json)];v=[pos[x] for x in json.loads(row.validation_ids_json)]
            assert not set(h)&set(v) and len(h)+len(v)==len(allids)
            for L in [10,15]:
                support_rows.append(dict(image_id=im,scheme=row.scheme,replicate=row.replicate,horizon=L,
                    history_n=len(h),validation_n=len(v),eligible=len(h)>=L and len(v)>=2))
            if len(v)<2 or len(h)<10:continue
            for tau in [3.,6.,12.]:
                end=min(15,len(h));parts={k:cluster(h[:k],tau) for k in range(1,end+1)}
                for k,r in parts.items():
                    trajectories.append(dict(image_id=im,scheme=row.scheme,replicate=row.replicate,tau=tau,k=k,status=r['status'],
                        cluster_count=len(r['clusters']) if r['status']=='unique' else np.nan,
                        supported_clusters=sum(len(g)>=2 for g in r['clusters']) if r['status']=='unique' else np.nan,
                        clusters_json=json.dumps([[allids[x] for x in g] for g in r['clusters']]),
                        candidate_partitions=r['candidate_partition_count']))
                for L in [10,15]:
                    if L>end:continue
                    joint=cluster(h[:L]+v,tau)
                    for k in range(1,L-2):
                        e=envelope(parts,k,L);prefix=parts[k]
                        r=dict(image_id=im,scheme=row.scheme,replicate=row.replicate,tau=tau,horizon=L,k=k,
                            history_n=len(h),validation_n=len(v),prefix_status=prefix['status'],
                            prefix_clusters=len(prefix['clusters']) if prefix['status']=='unique' else np.nan,
                            **e,joint_status=joint['status'],validation_tv=np.nan,validation_outside=np.nan,validation_ambiguous=np.nan,
                            joint_membership_change=np.nan,joint_share_change=np.nan,joint_new_supported_clusters=np.nan)
                        if prefix['status']=='unique':
                            hp={x:j for j,x in enumerate(h[:k])}
                            vd=fixed_distribution(matrix,h[:k],v,[[hp[x] for x in g] for g in prefix['clusters']],tau,[k])[0]
                            r.update(validation_tv=vd['distribution_tv'],validation_outside=vd['validation_outside_fraction'],validation_ambiguous=vd['validation_ambiguous_fraction'])
                            if joint['status']=='unique':
                                delta=partition_change(prefix['clusters'],joint['clusters'],k,L+len(v))
                                r.update(joint_membership_change=delta['membership_change'],joint_share_change=delta['share_change'],joint_new_supported_clusters=delta['new_supported_clusters'])
                        for epsilon in EPSILONS:
                            name=str(int(round(epsilon*100)))
                            state=stable_state(e,epsilon);r['state_'+name]=state
                            if state=='changing':confirmed='changing'
                            elif state=='unknown' or joint['status']!='unique':confirmed='unknown'
                            else:confirmed='stable' if r['joint_membership_change']<=epsilon+1e-12 and r['joint_share_change']<=epsilon+1e-12 and r['joint_new_supported_clusters']==0 else 'changing'
                            r['confirmed_'+name]=confirmed
                        records.append(r)
        print(f'完成{ordinal}/12图：前缀{len(trajectories)}；稳定窗口记录{len(records)}',flush=True)
    save('all_integer_prefixes.csv.gz',trajectories);save('stability_records.csv.gz',records);save('support.csv.gz',support_rows)
    df=pd.DataFrame(records);curves=[]
    keys=['image_id','scheme','tau','horizon','k']
    for key,g in df.groupby(keys):
        for eps in [5,10,20]:
            states=g['state_'+str(eps)];confirmed=g['confirmed_'+str(eps)]
            curves.append(dict(zip(keys,key))|dict(tolerance_pp=eps,replicates=len(g),
                evaluated=int((g.status=='evaluated').sum()),stable=int((states=='stable').sum()),unknown=int((states=='unknown').sum()),
                stable_lower=(states=='stable').mean(),stable_upper=(states!='changing').mean(),
                validation_confirmed_lower=(confirmed=='stable').mean(),validation_confirmed_upper=(confirmed!='changing').mean(),
                stable_single=int(((states=='stable')&(g.prefix_clusters==1)).sum()),
                stable_multi=int(((states=='stable')&(g.prefix_clusters>1)).sum()),
                max_membership_mean=g.max_membership_change.mean(),max_share_mean=g.max_share_change.mean(),
                joint_unknown=g.joint_status.ne('unique').mean(),validation_tv_mean=g.validation_tv.mean(),validation_tv_count=g.validation_tv.count()))
    curves=pd.DataFrame(curves);save('stability_curves.csv',curves)
    prediction_count=summarize(curves)
    qa=dict(status='passed',images=len(images),prefix_records=len(trajectories),stability_records=len(df),image_prediction_records=prediction_count,
        prefixes_start_at_one=True,minimum_later_history_people=3,all_stages_pooled=True,unique_not_equated_to_single=True,
        unknown_not_encoded_as_changing=True,old_absolute_distance_threshold_used=False,
        single_and_multicluster_allowed=True,source_target_image_overlap=False,formal_stopping_rule=False)
    (OUT/'RUN_QA.json').write_text(json.dumps(qa,ensure_ascii=False,indent=2),encoding='utf-8');print(json.dumps(qa),flush=True)


if __name__=='__main__':main()
