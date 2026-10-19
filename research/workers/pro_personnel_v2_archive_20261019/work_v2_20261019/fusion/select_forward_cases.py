"""Select both extremes of one fully reported frozen forward contrast."""
import pandas as pd
from pool_io import OUT,save,load_pools
from compare_fusions import ComparisonPool


def main():
    x=pd.read_csv(OUT/'FORWARD_POLICY_PAIRED.csv.gz')
    z=x[x.contrast.eq('difficulty_increment_QD_minus_Q')&x.k.eq(16)&x.selection_metric.eq('B8L2')&
        x.candidate_pool.eq('Q_history_supported_all_origins')&x.difficulty.eq('困难')]
    valid=z[z.B8_change.notna()].sort_values(['B8_change','pool_id'])
    selected=[('most_negative',valid.iloc[0]),('most_positive',valid.iloc[-1])]
    pools={p['pool_id']:p for p in load_pools()};cases=[]
    for kind,r in selected:
        p=pools[r.pool_id];c=ComparisonPool(p);a=c.byid[r.baseline_request];b=c.byid[r.treatment_request]
        case=c.pair(r.baseline_request,r.treatment_request)
        case.update(case_id='QD_hard_k16_'+kind,case_kind=kind,label_a='Qfirst（整体LOBO质量）',label_b='QD_allhistory（目标难度LOBO质量）',
            worker_ids_a=a['member_workers'].split('|'),worker_ids_b=b['member_workers'].split('|'),
            ordered_workers_a=a['ordered_workers'].split('|'),ordered_workers_b=b['ordered_workers'].split('|'),
            member_object_ids_a=a['member_object_ids'].split('|'),member_object_ids_b=b['member_object_ids'].split('|'),
            source_time_a=a['source_time_total_seconds'],source_time_b=b['source_time_total_seconds'],
            source_time_known_n_a=a['source_time_known_n'],source_time_known_n_b=b['source_time_known_n'],
            nodes_a=a['nodes'],nodes_b=b['nodes'],reference_pairs=a['reference_pair_count'],
            geometry_state_a=a['geometry_state_pointer'],geometry_state_b=b['geometry_state_pointer'],
            review_question='在同楼外训练、同困难等级和同人数下，换入的成员是否改变了关键节点/连接？底面范围变化与B8损失或增益为何不一致？请只审查这些候选几何，不把未人工确认的环当成正式交付。')
        cases.append(case)
    save(OUT/'FORWARD_CASES.json',dict(schema='forward_frozen_team_diagnostic_cases_v1',
        selection_rule='Among ALL ordinary-Manual hard images at k=16, B8-selected QD_allhistory minus Qfirst on identical Q-supported candidate pools, choose the largest observed B8 loss AND the largest observed gain; ties by pool_id. Post-result representative diagnosis, not an additional validation subset.',
        image_support=len(z),building_support=z.building.nunique(),quality_comparable_images=int(z.B8_change.notna().sum()),
        quality_unavailable_images=int(z.B8_change.isna().sum()),images_gain_gt2=int(z.B8_change.gt(2).sum()),
        images_loss_gt2=int(z.B8_change.lt(-2).sum()),images_same_actual_team=int(z.same_subset.sum()),magnitude_threshold=2,
        all_image_results='FORWARD_POLICY_PAIRED.csv.gz',cases=cases,visual_review_performed_by_fusion_module=False))


if __name__=='__main__':main()
