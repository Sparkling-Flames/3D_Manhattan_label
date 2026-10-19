#!/usr/bin/env python3
"""Translate the frozen, outcome-selected case catalog; no case reselection."""
from pathlib import Path
import json

HERE=Path(__file__).resolve().parent
source=HERE.parent/'clusters/CASE_CATALOG.json'
catalog=json.loads(source.read_text())
titles={
'geometry_angle_near_floor_far':'角度接近，底面与三维范围却分离',
'geometry_floor_near_height_far':'底面接近，顶部与高度仍不同',
'declared_direction_equivalence':'环方向不同是否仅是表示差异',
'high_Q_shared_node_count_gap':'簇平均历史 Q 偏高，仍有共同节点差',
'fusion_within_cluster_large_geometry':'同簇换一人，融合仍可发生大变化',
'fusion_within_cluster_stable':'同簇换人得到相同端点的实例',
'fusion_cross_cluster_large_geometry':'跨簇换人改变了范围与质量',
'fusion_cross_cluster_small_geometry':'跨簇换人也可能几乎没有变化',
'fusion_stable_low_quality':'输出近似不变，但对参考质量很低',
'fusion_within_cluster_failure':'同簇替换也可能触发不可评分输出',
}
for c in catalog['cases']:
    c['title']=titles[c['case_id']]
    facts=[]
    if c.get('distance_deg') is not None:
        facts += [f"绑定角距 {c['distance_deg']:.3f}°", f"底面 IoU {c['floor_iou']:.4f}",f"平均高度棱柱 IoU {c['prism_3d_iou']:.4f}"]
    if c.get('B8L2_a') is not None:
        b=f"{c['B8L2_b']:.3f}" if c.get('B8L2_b') is not None else '不可评分'
        facts += [f"固定 {c['k']-1} 人背景，{c['entrant_a']} → {c['entrant_b']}",f"B8L2 {c['B8L2_a']:.3f} → {b}"]
        if c.get('floor_jaccard_difference') is not None:facts.append(f"底面 V {max(0,c['floor_jaccard_difference']):.4f}")
    if c['case_id']=='high_Q_shared_node_count_gap':
        facts += [f"4 人簇平均全量 β +{c['mean_global_Q_effect']:.2f}，个体 β −0.41/+0.31/+14.99/+0.47",f"当图平均 B8L2 {c['mean_actual_B8L2']:.2f}；4 点对，参考 6 点对"]
    if c.get('changed_pairs') is not None:facts.append(f"该图有 {c['changed_pairs']} 对作答受整环反向敏感性影响")
    c['evidence']='；'.join(facts)+'。'+c['question']+f" 展示筛选分母：{c['selection_denominator']}（原始单位与筛选规则见完整案例清单）。"
    c['visual_status']='预选机制案例；视觉查看不回写资格、参考或错误金标'
forward=json.loads((HERE.parent/'fusion/FORWARD_CASES.json').read_text())
for c in forward['cases']:
    c['title']='难度选人收益的反例' if c['B8L2_change']<0 else '难度选人改善的实例'
    c['image_code']=c['image']
    c['selection_denominator']=forward['image_support']
    c['question']=c['review_question']
    c['evidence']=f"{c['image']}，同为 16 人：Q优先 {c['B8L2_a']:.3f} → Q＋难度 {c['B8L2_b']:.3f}；底面 V {c['floor_jaccard_difference']:.4f}，点对 {c['nodes_a']} → {c['nodes_b']}。"+c['question']+' 两例按所有31张困难图的损失／增益极值同时选出；30图质量可比，5图增益>2，10图损失>2。'
    c['visual_status']='建筑外训练选人；事后选取正反极值展示，不是额外验证集'
    catalog['cases'].append(c)
(HERE/'viewer_cases.json').write_text(json.dumps(catalog,ensure_ascii=False,indent=2))
print(json.dumps({'cases':len(catalog['cases']),'selection_unchanged':True,'source':str(source)},ensure_ascii=False))
