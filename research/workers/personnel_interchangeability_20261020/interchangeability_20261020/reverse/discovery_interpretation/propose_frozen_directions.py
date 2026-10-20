#!/usr/bin/env python3
"""Create a reviewable discovery-selected reverse direction proposal.

These are recommendations to the parent experiment owner, not an assertion
that assessment replication has occurred. No assessment outcomes are read.
"""
import json
from pathlib import Path
import sys

import pandas as pd

HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE))
import analyze_reverse_discovery as rev


def main():
    prefix="R_directswap_";suffix="__mixed_history_v1"
    inputs=[
        ("R01","geometry_partition_b2_K2__ordinary_new","same_source_team","C01","C02","positive_separation_quality_decline","全新来源粗两类的下降方向；总体清楚，中等人数仅换2人的效应弱，直接冻结检验稀释。"),
        ("R02","geometry_partition_b2_K2__ordinary_new","same_source_team","C02","C01","quality_improvement_nonuniversal_within_advantage","配套改善方向；跨类变化可变好，不要求类间比类内更不稳定。"),
        ("R03","geometry_partition_b0_K7__ordinary","primary","C02","C01","positive_separation_source_and_Q_qualification","七类高Q新批为主组换入低Q混合来源组；保留整体效用，来源匹配另列，不能称已超Q。"),
        ("R04","geometry_partition_b0_K7__ordinary_new","same_source_team","C07","C06","conditional_shape_separation","m=2,n=11..17 的预定窗口内形状分离较清楚；两类均4人，低尾与楼方向保留，Qclose3仅作既定次分析。"),
        ("R05","geometry_partition_b0_K7__ordinary_new","same_source_team","C04","C01","negative_control_cross_more_joint_stable","宽人数m>=2发现跨类比同类主稳定更高，不能说所有同类都更可互换；4人类容量反例。"),
        ("R06","joint_partition_b0_K10__ordinary","primary","C07","C01","fine_class_separation_capacity_control","K10的有多楼支持细类方向；C07=11人/C01=5人，来源及Q差较强，不能用高K宏观均值宣称算法胜出。"),
        ("R07","geometry_partition_b0_K7__hard_new","same_source_team","C03","C06","conditional_geometry_decline","已有参考相符困难判定下的高Q多点组向近中Q略少点组；形状差清楚但仅6图3楼10事件，需新成员/背景复查。"),
        ("R08","geometry_partition_b0_K7__hard_new","same_source_team","C06","C03","negative_control_cross_more_stable_and_better","配套困难反例：跨类更稳定且质量改善，拒绝把更大类间变化当唯一成功；旧发现仅9事件。"),
    ]
    methods=json.load(open(rev.BASE/"mixed_fit/METHOD_MANIFEST.json"))
    labels=rev.BASE/"mixed_fit/worker_labels.csv.gz"
    shortlist=json.load(open(rev.BASE/"MIXED_SCREEN_SHORTLIST.json"))
    assert rev.sha(labels)==shortlist["labels_sha256"]
    all_d=pd.read_csv(HERE/"direction_aggregate.csv.gz")
    bands=pd.read_csv(HERE/"focused_bands_aggregate.csv.gz")
    proposal=[];table_parts=[]
    metric_cols=["events","images","buildings","unique_teams","all_people","block_people","n_min","n_max","m_min","m_max",
        "within_joint_stable_main","cross_joint_stable_main","gap_joint_stable_main",
        "within_geometry_noQ_main","cross_geometry_noQ_main","gap_geometry_noQ_main",
        "within_geometry_shape_main","cross_geometry_shape_main","gap_geometry_shape_main",
        "within_abs_B8L2_change","cross_abs_B8L2_change","within_absQ_gt5","cross_absQ_gt5",
        "within_floor_jaccard_difference","cross_floor_jaccard_difference","within_prism_distance","cross_prism_distance",
        "net_B8L2_change","net_D10_change","net_B8L2_change_per_image_p10","B_B8L2_per_image_p10","C_B8L2_per_image_p10",
        "net_Q_worsen_gt5","B_complete","C_complete","B_score_missing","C_score_missing",
        "net_diag_wall_coverage_05_delta","net_diag_corner_recall_05_delta","net_IoU3D100_delta",
        "cross_minus_within_history_Q","all_blocks_history_Q_close3","actual_source_match",
        "gap_joint_stable_main_positive_buildings","gap_joint_stable_main_negative_buildings",
        "gap_geometry_shape_main_positive_buildings","gap_geometry_shape_main_negative_buildings",
        "net_B8L2_change_positive_buildings","net_B8L2_change_negative_buildings"]
    for rid,short,ctx,out,inc,role,note in inputs:
        mid=prefix+short+suffix;spec=methods[mid]
        classes=spec["classes"]
        chosen=[]
        for frame,band in [(all_d,"all_supported_n_m")]+[(bands,x) for x in bands.focused_band.unique()]:
            take=frame[(frame.method_id==mid)&(frame.context_id==ctx)&(frame.outgoing_class==out)&(frame.incoming_class==inc)].copy()
            if band!="all_supported_n_m":take=take[take.focused_band==band]
            take["proposal_id"]=rid;take["review_band"]=band
            chosen.append(take)
        combined=pd.concat(chosen,ignore_index=True)
        keep=["proposal_id","review_band","subset","method_id","domain","context_id","outgoing_class","incoming_class"]+[c for c in metric_cols if c in combined]
        table_parts.append(combined[keep])
        overview=combined[(combined.review_band=="all_supported_n_m")&(combined.subset=="primary_nge3_mge2_all")]
        focused=combined[(combined.review_band=="m2_n11_17")&(combined.subset=="primary_nge3_mge2_all")]
        proposal.append({
            "proposal_id":rid,"method_id":mid,"domain":spec["domain"],"context_id":ctx,
            "outgoing_class":out,"incoming_class":inc,"direction":out+"->"+inc,
            "interpretive_role":role,"reason_zh":note,
            "proposed_assessment_primary":{"n":13,"m":5 if rid in ["R01","R02"] else 2,"difficulty":"hard" if spec["domain"].startswith("hard") else "all_eligible_ordinary_manual",
                "whole_team_origins":["new"] if ctx=="same_source_team" else None,
                "source_matching_views":["overall", "actual_source_matched", "actual_source_matched_and_all_blocks_history_Q_close3"]},
            "root_decided_nested_ratio_panel":{"m_values":[2,5],"n_values":"all capacity-allowed integers","fixed_block_sets_per_pool":2,"nested_fixed_core_order":True,"n13_m2_role":"dilution_control","n13_m5_role":"large_block_primary"} if rid in ["R01","R02"] else None,
            "suggested_stress_n":[5,9,17,21],"suggested_stress_m":[m for m in [2,3,4] if m<=min(len(classes[out])//2,len(classes[inc]))],
            "outgoing_members":classes[out],"incoming_members":classes[inc],
            "outgoing_class_size":len(classes[out]),"incoming_class_size":len(classes[inc]),
            "m_capacity_before_core":min(len(classes[out])//2,len(classes[inc])),
            "capacity_note":"A/B两组同类块必须互斥，故out_class至少2m人；入类至少m人。实际池机会和固定背景还会收窄。4人out类的m2用尽本类全部4名人员，不等于未见人员验证。",
            "discovery_all_supported":overview[metric_cols].iloc[0].to_dict() if len(overview) else None,
            "discovery_fixed_window_m2_n11_17":focused[metric_cols].iloc[0].to_dict() if len(focused) else None,
        })
    table=pd.concat(table_parts,ignore_index=True)
    rev.write_csv(HERE/"RECOMMENDED_DIRECTIONS_DISCOVERY_SUPPORT.csv.gz",table)
    obj={"schema":"reverse_discovery_direction_proposal_v1","phase":"discovery_selection_before_assessment_read",
        "assessment_outcomes_read":False,"labels_sha256":rev.sha(labels),
        "class_fit_scope":"Only the frozen 10 history buildings, including 5-fold internal selection; discovery outcomes select these direction hypotheses only.",
        "proposals":proposal,
        "comparison":"Common A base/core; A->B same composition, A->C changed composition, identical n and turnover m. Signed utility is C-B; gap=within stability-cross stability.",
        "aggregation":"event means within image; image means within building; building equal. Counts are actual support, not independent-event sample size.",
        "failure_rule":"Incomplete and unscorable endpoints retained separately; missing score never zero. Joint stability includes completeness; continuous geometry missing remains missing.",
        "no_external_blind_claim":"Assessment is reused v2 buildings/images held from this round's fitting/discovery; new members are not new independent images.",
        "source_files_sha256":{p.name:rev.sha(p) for p in [HERE/"direction_aggregate.csv.gz",HERE/"focused_bands_aggregate.csv.gz",HERE/"REVERSE_DISCOVERY_INTERPRETATION_RECEIPT.json",Path(__file__)]}}
    rev.write_json(HERE/"RECOMMENDED_DIRECTIONS.json",rev.clean(obj))
    lines=["# 反向真实类别块：8条待冻结方向建议", "", "这些方向从发现集实际融合中选择；分类本身仍只由10栋历史楼训练。评估图尚未读取。主代理决定：new-only K2双向各以 n13/m5 为大块主方向、n13/m2为稀释对照，并冻结每池两组固定块、嵌套背景顺序和所有容量允许整数n；其余六条以 n13/m2 为主，再做人数/规模压力面板。发现总体 n/m 与单个节点的效应不应混称。", "", "|编号|分类与来源条件|方向|发现定位|", "|---|---|---|---|"]
    for row in proposal:
        lines.append(f"|{row['proposal_id']}|{row['method_id'].replace(prefix,'').replace(suffix,'')}；{row['context_id']}|{row['direction']}|{row['reason_zh']}|")
    lines += ["", "## 必须保留的边界", "", "- new-only K2 的总体 C01→C02 净质量下降约4.25分，反向改善约4.14分；在固定 m2、n11–17 窗口两方向净变化仅−0.16/+0.17分。这是实际窗口稀释的线索，不能保证 n13 复制总体差异。", "- new-only K7 C07→C06 的 m2、n11–17 窗口为13事件、12图、5楼；全 n/m 为51事件、32图、6楼，形状 gap 从条件31.67个百分点降至总体7.69个百分点。两者同时留存。", "- hard-new K7 C03→C06 与反向只有6图3楼。既有难度判定含目标参考信息，不能称新图自动预先挑人成功。", "- K7中4人类的 m2 已用完全部同类4人；新背景/新组合无法扩展到未观察的新人员。高K的支持和替换容量必须一起报告。", "- No-Q 是学习目标未含Q，并不代表类别与Q独立。K2、ordinary K7、K10主要清楚方向仍有历史Q/来源差。整体效用先报告，source/Qclose 控制只作剩余信息检查。", "- 新shape与旧joint、相同节点的noQ分别报告；相近Q和相同节点都不保证结构稳定，ref节点/边召回只是参考诊断。", "- 源时间为原作答的报告用时；缺始几何的Semi不编造净纠错，本面板仅普通Manual资格。", "", "全部支持与反向、邻接人数窗口见 `RECOMMENDED_DIRECTIONS_DISCOVERY_SUPPORT.csv.gz`。这份建议不替代主代理的最终评估冻结文件。"]
    (HERE/"RECOMMENDED_DIRECTIONS_ZH.md").write_text("\n".join(lines)+"\n")


if __name__=="__main__":main()
