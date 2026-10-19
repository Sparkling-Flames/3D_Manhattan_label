#!/usr/bin/env python3
"""Build small paired-stage reporting tables; no new selection or model fitting."""
from pathlib import Path
import argparse
import json
import pandas as pd


def num(v, digits=2, sign=False):
    if pd.isna(v):
        return "缺失"
    return format(float(v), ("+" if sign else "") + f".{digits}f")


def intstr(v):
    return "缺失" if pd.isna(v) else str(int(v))


def counts(s):
    return "+".join(f"{v}{c}" for c, v in (z.split(":") for z in s.split("|")) if int(v))


def markdown(columns, rows):
    cell = lambda value: str(value).replace("|", "\\|")
    return "\n".join(["| " + " | ".join(cell(c) for c in columns) + " |", "| " + " | ".join(["---"]*len(columns)) + " |"] +
                     ["| " + " | ".join(cell(v) for v in row) + " |" for row in rows])


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--root", type=Path, default=Path(__file__).resolve().parent)
    args = ap.parse_args()
    defs = json.loads((args.root / "block_discovery_specific/HIGHLIGHT_DEFINITIONS.json").read_text())["definitions"]
    summaries, sources, receipts = {}, {}, {}
    for phase in ("discovery", "validation"):
        folder = args.root / f"block_{phase}_specific"
        s = pd.read_csv(folder / "highlight_summary.csv")
        summaries[phase] = s[s.subset.eq("all_events")].set_index("highlight_id", verify_integrity=True)
        sources[phase] = pd.read_csv(folder / "highlight_source_Q_comparison.csv").set_index(["highlight_id", "subset"], verify_integrity=True)
        receipts[phase] = json.loads((args.root / f"block_{phase}/BLOCK_SUMMARY_RECEIPT.json").read_text())
    rows, table1, table2, table3, table4 = [], [], [], [], []
    abbreviations = {"F_rule_Q_threshold_K3": "Q阈值3", "F_rule_Q2xDetail2": "Q×点数4", "R_geo9_source_signed_p2_K2": "来源残差关系2",
                     "R_role_ward_K5": "几何角色5", "R_role_ward_difficulty_K2": "困难角色2"}
    for i, d in enumerate(defs, 1):
        tag = d["highlight_id"]
        D, V = summaries["discovery"].loc[tag], summaries["validation"].loc[tag]
        row = {"highlight_no": i, **{k: d[k] for k in ["highlight_id", "method_id", "domain", "k", "m", "outgoing_counts", "incoming_counts"]}}
        label = f"{abbreviations[d['method_id']]} {counts(d['outgoing_counts'])}→{counts(d['incoming_counts'])}; n{d['k']}/m{d['m']}"
        support = lambda r: "/".join(intstr(r[x]) for x in ["net_B8L2_change_n", "net_B8L2_change_finite_images", "net_B8L2_change_finite_buildings"])
        for phase, s in [("discovery", D), ("validation", V)]:
            for metric in ["events", "workers", "observed_unique_teams", "net_B8L2_change_n", "net_B8L2_change_finite_images", "net_B8L2_change_finite_buildings",
                           "net_B8L2_change_equal_building_mean", "net_B8L2_change_event_p10", "net_B8L2_change_positive_buildings", "net_B8L2_change_negative_buildings",
                           "within_abs_B8L2_change_equal_building_mean", "changed_abs_B8L2_change_equal_building_mean", "excess_abs_B8L2_change_equal_building_mean",
                           "within_floor_jaccard_difference_equal_building_mean", "changed_floor_jaccard_difference_equal_building_mean", "excess_floor_jaccard_difference_equal_building_mean",
                           "net_ref_edge_recall_9_change_equal_building_mean", "net_diag_wall_coverage_05_change_equal_building_mean",
                           "within_joint_stable_main_equal_building_mean", "changed_joint_stable_main_equal_building_mean",
                           "B_score_missing_events", "C_score_missing_events", "net_lost_complete_events", "net_restored_complete_events",
                           "loow_removed_workers_tested", "loow_min_remaining_events", "loow_min_remaining_images", "loow_min_remaining_buildings",
                           "loow_retained3b_net_B8L2_change_min", "loow_retained3b_net_B8L2_change_max", "loow_retained3b_Q_direction_reversals", "loow_removals_losing_three_Q_buildings"]:
                row[phase + "_" + metric] = s.get(metric)
            for subset in ["actual_source_matched", "matched_new_incoming_blocks", "matched_v1_incoming_blocks", "all_new_teams", "source_and_incoming_Q_close_3"]:
                z = sources[phase].loc[(tag, subset)]
                for metric in ["events", "images", "buildings", "net_B8L2_change_equal_building_mean", "net_B8L2_change_finite_events", "net_B8L2_change_finite_images", "net_B8L2_change_finite_buildings"]:
                    row[phase + "_" + subset + "_" + metric] = z[metric]
        rows.append(row)
        table1.append([i, label, num(D.net_B8L2_change_equal_building_mean, sign=True) + " (" + support(D) + ")",
                       num(V.net_B8L2_change_equal_building_mean, sign=True) + " (" + support(V) + ")",
                       f"{int(V.net_B8L2_change_positive_buildings)}正/{int(V.net_B8L2_change_negative_buildings)}负", num(V.net_B8L2_change_event_p10, sign=True)])
        def src_value(phase, subset):
            z = sources[phase].loc[(tag, subset)]
            if not int(z.events):
                return "无此机会 (0)"
            n = "/".join(intstr(z[x]) for x in ["net_B8L2_change_finite_events", "net_B8L2_change_finite_images", "net_B8L2_change_finite_buildings"])
            return num(z.net_B8L2_change_equal_building_mean, sign=True) + " (" + n + ")"
        table2.append([i, src_value("discovery", "actual_source_matched"), src_value("validation", "actual_source_matched"),
                       src_value("discovery", "source_and_incoming_Q_close_3"), src_value("validation", "source_and_incoming_Q_close_3")])
        table3.append([i, num(V.within_abs_B8L2_change_equal_building_mean) + " / " + num(V.changed_abs_B8L2_change_equal_building_mean),
                       num(V.excess_abs_B8L2_change_equal_building_mean, sign=True),
                       num(V.within_floor_jaccard_difference_equal_building_mean, 3) + " / " + num(V.changed_floor_jaccard_difference_equal_building_mean, 3),
                       num(V.net_ref_edge_recall_9_change_equal_building_mean, 3, True) + " / " + num(V.net_diag_wall_coverage_05_change_equal_building_mean, 3, True),
                       f"{int(V.net_lost_complete_events)} / {int(V.net_restored_complete_events)}"])
        if pd.isna(V.get("loow_removed_workers_tested")):
            table4.append([i, "未过12事件门槛", "—", "—", "—"])
        else:
            table4.append([i, num(V.loow_retained3b_net_B8L2_change_min, sign=True) + "～" + num(V.loow_retained3b_net_B8L2_change_max, sign=True),
                           f"{int(V.loow_retained3b_Q_direction_reversals)} / {int(V.loow_removed_workers_tested)}",
                           "/".join(intstr(V[c]) for c in ["loow_min_remaining_events", "loow_min_remaining_images", "loow_min_remaining_buildings"]),
                           intstr(V.loow_removals_losing_three_Q_buildings)])
    pd.DataFrame(rows).to_csv(args.root / "block_fixed_highlights_compact.csv", index=False)
    src = pd.concat([z.reset_index().assign(phase=phase) for phase, z in sources.items()], ignore_index=True)
    src.to_csv(args.root / "block_source_Q_control_comparison.csv", index=False)
    d, v = receipts["discovery"], receipts["validation"]
    text = f"""# 类别块替换：发现、冻结复查与反例

本附记用于支撑主报告，不能代替纯类／混类、完整配比和人数曲线。每个事件的 A、B、C 保持同一图片、参考、总人数和公共背景：A 是原类别块，B 换入不同人员但保持该块人数构成，C 同规模换入另一类别人数构成。A→B 与 A→C 的真实换人规模均为 m；净方向是 C−B。B 与 C 的换入块可能重叠，故两者的实际相互换人数有时小于 m，已在逐事件表保留。

下面每行固定方法、类别域、出／入人数向量、n、m，并在多种公共背景上检查；每行并非只有一个完整背景构成。完整 A/C 类别构成层在 `block_summary.csv.gz` 的 `full_composition` 视图中，精确成员在 `block_events.csv.gz`。类别只使用 history 建筑；这些 13 行从 discovery 的全部台账中选作说明，validation 沿用相同定义，没有按验证表现改切点或换类别。

## 真实覆盖

- 发现：{d['events']:,} 个事件，{d['primary_m_ge_2']:,} 个 m≥2 主事件；{d['requested_unique_teams']:,} 个唯一团队，{d['images']} 张图片、{d['buildings']} 栋建筑、{d['workers']} 人。
- 冻结复查：{v['events']:,} 个事件，{v['primary_m_ge_2']:,} 个 m≥2 主事件；{v['requested_unique_teams']:,} 个唯一团队，{v['images']} 张图片、{v['buildings']} 栋建筑、{v['workers']} 人。
- 两阶段请求成员、类别构成、参考、人数均逐项重建一致，缺计算团队均为 0。融合／评分失败保留，与缺计算不同。阶段之间可能存在相同人员和相关团队，不能把事件数当独立样本数。
- 搜索为按来源、出／入模式、m 分层的有限候选框架，受每池配额限制，真实成员每模式作确定性抽样；不是穷举全部人员团队。发现和复查所有具体方向均保留，单人结果属于补充。

## 1. 哪些具体方向复现，哪些明显减弱

下表均先在图片内平均，再在建筑内平均图片，最后建筑等权。括号为 **ΔQ 有限的事件／图片／建筑**，p10 为逐事件配对 C−B 的第10百分位，不是置信区间。

{markdown(['号','具体替换','发现 ΔQ (E/I/B)','复查 ΔQ (E/I/B)','复查建筑方向','复查事件 p10'], table1)}

Q 阈值类低→高、中→高以及反方向高→低在复查保持平均方向；角色五类 C01/C02→C05 与反方向也保留总体方向，但有明显成员依赖。困难图 C01→C02 的质量和边／墙几何改善仍然清楚，适用范围很窄，且不是所有建筑或成员都受益。所有正向收益行的验证 p10 均为负，不能承诺每次改善。

来源残差关系二类的净收益从 +4.76 减到 +1.53，控制来源后近零；Q×点数混入只剩5个质量可比事件，不能称清楚复现。该类别名称只表示历史关系中的来源残差处理，不表示已去除全部来源效应。发现阶段困难图 n13/m2 将2C02换成C01+C02的反常收益由 +6.25 缩到 +0.45，4楼2正2负，不能据此提出通用混入收益。

## 2. 类内波动、类间变化与质量方向是三件事

“同类换人幅度小”不能推出结果正确；“改构成的幅度大”也不能推出质量下降。下表 A/B 是构成不变，A/C 是改变类别块；净边／墙方向均为 C−B。距离两列可能各有不同有限集合，所以另列 `共同可比三队的距离差`，不拿两个条件均值直接相减作为配对效应。

{markdown(['号','|ΔQ_AB| / |ΔQ_AC|','共同可比 |ΔQ_AC|−|ΔQ_AB|','底面1−IoU AB / AC','净边对应 / 墙覆盖','完整性丢失 / 恢复'], table3)}

节点／边对应率采用冻结参考几何匹配；新增墙覆盖诊断使用同一参考与固定方向／空间容差。它们不是必要结构的人工语义真值，也未替换 B8L2 或 D10。分数相近时的结构差异和分数下降但边对应率上升均需结合原图及 ERP／BEV／3D 阅读。

## 3. 来源与历史 Q：先报告总效用，再报告可识别的剩余信息

来源匹配要求原块、同类换入块、跨类换入块的完整 new/v1 人数向量相同；公共背景对三臂相同。Q 接近要求 **换入块** 历史均 Q 差≤3，不用全队平均稀释差异。全域用 `q_beta`，hard 用 `theta_hard`，均来自 history 建筑，没有读取目标图质量。

{markdown(['号','发现：来源匹配 ΔQ (E/I/B)','复查：来源匹配 ΔQ (E/I/B)','发现：来源且Q近','复查：来源且Q近'], table2)}

多数强方向没有 Q 接近的换入块机会。这不否定类别整体选人价值，因为 Q 本来就是分类信号；但它们不能被称为 Q 独立的因果类别效应。来源残差关系的少量 Q 接近证据从发现 +5.97（5事件/5图/3楼）变成复查 −4.76（5事件/5图/4楼），是必须保留的控制反例。其来源匹配总体 +3.03→−0.08 也未形成稳健复现。

新批次、v1换入块、整队均新批次及各自 Q 接近的全部零机会与非零结果保存在 `block_source_Q_control_comparison.csv`。来源限制后的方向不能用来证明“批次无影响”；它检验的是在该来源有机会的人群中，是否仍有同方向结果。

困难角色的回归筛查是另一层证据：发现侧相同876队/6图/3楼，用全域Q、困难Q或两者再加来源，参考边对应率预测误差的额外降低分别为7.37%、8.39%、7.23%；B8L2分别0.33%、3.81%、1.33%。不同百分比以各自控制模型误差作分母，不能相减，也不能替代上面的实际融合。难度记录包含用户采纳的非盲参考几何复核，故只支持该已有条件下的规则／解释，不是新图片自动采集前的难度识别与选人验证。

## 4. 具体人员敏感性：删去含某人的全部事件

不重分型、不重算融合、不把团队删小；每次删去 A/B/C 任一臂包含该人的所有事件，再按原规则重算图片／建筑均值。LOOW只对至少3楼且至少12尝试事件的精确方向层运行，该门槛不读效果符号。下列范围仅包含删人后仍有至少3个有限质量建筑的情况，失去支持的删除也保留在详细台账。

{markdown(['号','复查LOOW ΔQ范围（仍≥3楼）','方向反转 / 删除人员数','最小剩余 E/I/B','删除后不足3楼次数'], table4)}

角色五类的 C05 只有6人，hard C02只有7人。验证 role C01→C05 n9/m4 删除所有含 W129 的事件后，只剩7事件/6图/4楼，ΔQ从+8.43变−0.46；反方向 role C05→C02 n5/m2 删除含 W126（C05）的事件后，只剩9事件/7图/4楼，−5.99变+1.09。符号变化与覆盖显著收缩一起报告，既不能忽略，也不能当成新员工泛化验证。Q低→高 n5/m2、Q高→低 n5/m2及困难角色 n5/m2在仍具3楼支持的删除中保留原方向。

## 5. 优先人工看图的精确复查案例

- **同类两队都差，换类别后变好**：`block__a156aafbe51ca0288a193d07`，`UwV83HsGsw3-09`，hard角色 n5/m2。A/B=24.23/24.57，C=89.60，净+65.04；边对应+0.375。A/B节点5→4且底面差0.093，不满足联合稳定，不能把分数相近称作整体稳定。B→C参考底面IoU从0.368到0.931。
- **同一困难类别规则的反例**：`block__8d40651f843bb930caa04008`，`UwV83HsGsw3-22`，n5/m2。B65.42→C48.99，净−16.44。
- **质量与结构诊断相反**：`block__d8ff08842b8d589f7df7ce33`，`X7HyMhZNoso-07`，hard角色 n9/m4。B63.54→C51.51，净−12.03，而参考边对应+0.700；需看图判断范围、连接及匹配含义。
- **高历史Q类不是每次更好**：`block__29ff28657072581ba4a60480`，`q9vSo1VnCiC-03`，Q阈值 n5/m2。A94.52/B94.31，C70.89，净−23.42。

每个阶段各13个精确方向的最大改善、最差下降和存在时的相近分数结构案例已保留在 `highlight_event_candidates.csv.gz`；并未用这些个案替代全方向证据。精确 A/B/C 团队键、成员、类别、参考和冻结参数可回到对应请求与逐事件表。

## 6. 文件与复现

主要代码：`summarize_blocks.py`（从冻结融合结果验证成员并计算事件）、`block_specific_findings.py`（完整具体方向与LOOW）、`report_block_highlights.py`（固定13行及来源子集）、本脚本（两阶段小表与本附记）。运行参数保留在各阶段 receipt；`analysis/figures_summary/make_summary_figures.py` 根据结果小表生成两张科学图并验证逐楼均值一致。

精简交付使用 `compact_block_evidence/`：固定13层全部事件、所有精确方向的37列概要、LOOW按层摘要、13层全部具体删人结果和全部LOOW支持台账。`block_source_Q_control_comparison.csv`另保留新旧来源及Q接近的零机会。原完整逐事件几何状态、全部逐人删除行与重复缓存由代码和精确请求重建；主结论／案例所需事件未省略。此研究仍是已被多轮探索的现有 v2 内部建筑留出及新成员团队复查，不称外部盲测。
"""
    (args.root / "BLOCK_FINDINGS_ZH.md").write_text(text, encoding="utf-8")
    print(json.dumps(dict(highlights=len(rows), source_rows=len(src), output="BLOCK_FINDINGS_ZH.md"), ensure_ascii=False))


if __name__ == "__main__":
    main()
