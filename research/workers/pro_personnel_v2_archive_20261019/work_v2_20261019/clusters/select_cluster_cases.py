"""Small rank-selected whole-cluster case catalogue with explicit denominators."""
from __future__ import annotations
import gzip,json
from pathlib import Path
import numpy as np
import pandas as pd
HERE=Path(__file__).resolve().parent

def clean(v):
    if isinstance(v,dict):return {str(k):clean(x) for k,x in v.items()}
    if isinstance(v,(list,tuple)):return [clean(x) for x in v]
    if isinstance(v,np.integer):return int(v)
    if isinstance(v,(float,np.floating)):return float(v) if np.isfinite(v) else None
    if isinstance(v,np.bool_):return bool(v)
    return v

def main():
    pairs=pd.read_csv(HERE/'geometry_case_candidates.csv');groups=pd.read_csv(HERE/'cluster_summary.csv')
    assignments=pd.read_csv(HERE/'assignments.csv');profiles=pd.read_csv(HERE.parent/'profiles/full_profiles.csv')
    if 'panel' in profiles:profiles=profiles[profiles.panel.eq('manual|ordinary_primary')]
    profiles=profiles.drop_duplicates('worker_id').set_index('worker_id')
    flat=pd.read_csv(HERE.parent/'profiles/records_flat.csv').set_index('object_id')
    cases=[]
    for kind,question in [('angle_near_floor_far','端点在球面上接近，但底面范围/投影深度分离是否能在整簇ERP、BEV、3D联动里清楚看出？请判断误差位置及遮挡，不需逐对打分。'),
                          ('floor_near_height_far','底面很接近时，顶界或高度差异是否具有实际语义意义？冻结棱柱IoU只是平均高度代理。')]:
        g=pairs[pairs.case_kind.eq(kind)];row=g.iloc[0].to_dict()
        cases.append(dict(case_id='geometry_'+kind,case_kind=kind,question=question,selection='first ranked image in complete metric-defined candidate set',
            image_id=row['image_id'],image_code=row['image_code'],pool_id=row['pool_id'],thresholds=[9,12],
            object_ids=[row['object_id_a'],row['object_id_b']],workers=[row['worker_id_a'],row['worker_id_b']],
            distance_deg=row['distance_deg'],floor_iou=row['floor_iou'],prism_3d_iou=row['prism_3d_iou'],selection_denominator=row['selection_denominator'],
            review_status='not_newly_visually_adjudicated'))
    # Four images where opposite declared direction affects angular comparison.
    rev=pd.read_csv(HERE/'reverse_ring_partition_summary.csv');rev=rev[rev.layer.eq('ordinary_manual') & rev.threshold_deg.eq(9) & rev.changed_coassigned_pairs.gt(0)]
    rev=rev.sort_values('changed_coassigned_pairs',ascending=False)
    if len(rev):
        r=rev.iloc[0];cases.append(dict(case_id='declared_direction_equivalence',case_kind='ring_direction',pool_id=r.pool_id,image_id=r.image_id,image_code=r.image_code,
            thresholds=[9,12],object_ids=[],workers=[],question='主距离不允许整环反向；保持上下绑定时反向是否仅改变画环方向、并未改变空间？这是表示等价性核查，不更改既有点位或主分簇。',
            changed_pairs=int(r.changed_coassigned_pairs),selection_denominator=len(rev),review_status='not_newly_visually_adjudicated'))
    candidate=[]
    for r in groups[groups.layer.eq('ordinary_manual') & groups.method.eq('affinity') & groups.threshold_deg.eq(9) & groups['size'].ge(3)].itertuples():
        workers=r.workers.split('|');oids=r.object_ids.split('|');pc=float(flat.loc[oids[0],'reference_pair_count'])
        if not np.isfinite(pc) or r.pair_count>=pc:continue
        values=[profiles.loc[w,'Q_effect_B8L2'] for w in workers if w in profiles.index and profiles.loc[w,'Q_supported']]
        if not values:continue
        candidate.append(dict(pool_id=r.pool_id,image_id=r.image_id,image_code=r.image_code,building_id=r.building_id,cluster_id=r.cluster_id,
            cluster_size=r.size,pair_count=r.pair_count,reference_pair_count=pc,mean_global_Q_effect=float(np.mean(values)),
            supported_profile_n=len(values),positive_relative_Q_n=int(sum(v>0 for v in values)),
            worker_relative_Q={w:float(profiles.loc[w,'Q_effect_B8L2']) for w in workers if w in profiles.index and profiles.loc[w,'Q_supported']},
            mean_actual_B8L2=r.mean_B8L2,object_ids=oids,workers=workers))
    candidate.sort(key=lambda r:(-r['mean_global_Q_effect'],-r['cluster_size'],r['pool_id']))
    pd.DataFrame(candidate).to_csv(HERE/'high_Q_reference_node_gap_candidates.csv',index=False)
    if candidate:
        r=candidate[0];cases.append(dict(case_id='high_Q_shared_node_count_gap',case_kind='global_high_Q_same_count_reference_gap',thresholds=[9,12],**r,
            question='该簇平均相对Q较高，但成员个体有差异（请联动逐人画像），均采用比绑定参考更少的节点。整簇是否共享简化、是否遗漏有效结构，还是参考分点粒度/合理范围不同？不能把簇均值称为人人高Q；节点差尚不是gold遗漏裁定。',
            selection='highest mean supported global relative Q among >=3-member clusters with fewer nodes than reference',selection_denominator=len(candidate),review_status='not_newly_visually_adjudicated'))
    path=HERE/'fusion_analysis/representative_counterexample_candidates.csv'
    if path.exists():
        c=pd.read_csv(path);c=c[c.threshold_deg.eq(9)]
        all_candidates=pd.read_csv(HERE/'fusion_analysis/case_candidates_all_pools.csv')
        questions={'within_cluster_large_geometry':'同一标法簇且同点数，固定背景换一人为什么仍有较大变化？请检查角度近/深度远、投票边界、连接和共同遗漏。',
            'within_cluster_stable':'同一标法簇内换人得到稳定输出时，端点质量、几何范围、共享连接及保留细节是否分别保持？这是代表性稳定实例，不据此认定全簇可互换。',
            'cross_cluster_large_geometry':'同点数但跨标法簇换人产生大变化时，换入位置、背景支持和连接变化中哪个解释实际差异？',
            'cross_cluster_small_geometry':'跨簇且同点数换人，为什么结果仍几乎不变？请查看强背景共识是否压过了换入人的差异。',
            'stable_low_quality':'两队输出很稳定但对参考质量较低；请看稳定的是哪一段错误范围/结构，不把稳定性当质量。',
            'within_cluster_failure':'同簇成员替换仍导致完整输出失败；请检查节点与连接的阈值触发。'}
        for kind,question in questions.items():
            s=c[c.case_kind.eq(kind)]
            if not len(s):continue
            r=s.iloc[0]
            all_kind=all_candidates[all_candidates.threshold_deg.eq(9) & all_candidates.case_kind.eq(kind)]
            cases.append(dict(case_id='fusion_'+kind,case_kind=kind,pool_id=r.pool_id,image_id=r.image_id,image_code=r.image_code,
                thresholds=[9,12],request_a=r.request_a,request_b=r.request_b,team_id_a=r.team_id_a,team_id_b=r.team_id_b,
                workers_a=r.member_workers_a.split('|'),workers_b=r.member_workers_b.split('|'),entrant_a=r.entrant_a,entrant_b=r.entrant_b,
                k=int(r.k),B8L2_a=r.B8L2_a,B8L2_b=r.B8L2_b,floor_jaccard_difference=r.floor_jaccard_difference,
                question=question,selection='predefined metric tail or counterexample rank, no manual hand-picking',
                selection_denominator=int(r.all_pool_candidate_denominator),selection_unit='eligible pool-level tail candidates',
                eligible_actual_replacement_pairs=int(all_kind.pool_candidate_denominator.sum()),
                eligible_pool_count=len(all_kind),selected_pool_candidate_pairs=int(r.pool_candidate_denominator),
                review_status='not_newly_visually_adjudicated'))
    result=dict(schema='v2_cluster_whole_overlay_cases_20261019_r1',purpose='few whole-cluster/team comparisons; not a pairwise review queue',cases=cases,
        available_manuscript_images='Original images have independent availability ledger; no visual correctness claim for absent originals',
        clustering_cannot_relabel_gold=True,user_review_not_backfilled_as_current_evidence=True)
    (HERE/'CASE_CATALOG.json').write_text(json.dumps(clean(result),ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(dict(cases=len(cases),ids=[c['case_id'] for c in cases]),ensure_ascii=False))

if __name__=='__main__':main()
