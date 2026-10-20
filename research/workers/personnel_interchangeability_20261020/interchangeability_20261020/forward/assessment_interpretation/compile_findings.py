#!/usr/bin/env python3
"""Compact already-frozen F11 summaries; no re-fitting, fusion or new selection."""
from pathlib import Path
import sys, json, math
import pandas as pd

HERE = Path(__file__).resolve().parent
FORWARD = HERE.parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(FORWARD / "common_panel"))
from summarize_common_panel import write_csv, write_json, sha

NAMES = {
    "F01": "高 Q23 慢→快", "F02": "高 Q18 慢→快", "F03": "高 Q 新人 T／编辑 C02→C01",
    "F04": "Q／T／几何 C04→C02", "F05": "Q／T／几何 C02→C04", "F06": "高 Q23 多点→少点",
    "F07": "困难 T／适应／几何 C03→C02", "F08": "scope 高 OUT→低 OUT", "F09": "Semi 低编辑→高编辑",
    "F10": "Manual 新报告低未改→高未改", "F11": "Semi 新报告低未改→高未改"}

def main():
    d = pd.read_csv(HERE / "F11_aggregate.csv.gz")
    cov = pd.read_csv(HERE / "F11_coverage_and_failures.csv.gz")
    keys = ["route_id", "method_id", "domain", "outgoing_class", "incoming_class", "setting", "control"]
    metrics = ["events", "pools", "images", "buildings", "unique_teams", "outgoing_people", "within_incoming_people", "cross_incoming_people", "n_min", "n_max", "m_min", "m_max",
        "within_joint_stable_main", "cross_joint_stable_main", "gap_joint_stable_main", "gap_geometry_noQ_main",
        "within_geometry_shape_main", "cross_geometry_shape_main", "gap_geometry_shape_main", "excess_floor_jaccard_difference", "excess_structure_bound_cyclic_deg",
        "net_B8L2_change", "net_D10_change", "net_B8L2_change_per_image_p10", "B_B8L2_per_image_p10", "C_B8L2_per_image_p10", "within_Q_drop_gt5", "cross_Q_drop_gt5", "B_complete", "C_complete", "B_score_missing", "C_score_missing",
        "net_ref_node_recall_9_delta", "net_ref_edge_recall_9_delta", "net_IoU3D100_delta", "source_block_geometric_ratio", "source_block_log_ratio", "net_source_block_seconds", "source_seconds_change_per_replaced_person", "source_save20", "source_save20_Q_not_worse2", "source_save20_Q_not_worse2_same_noQ_geometry", "cross_minus_within_history_Q"]
    metrics += [f"{m}_known_{s}" for m in ["net_B8L2_change", "source_block_log_ratio", "gap_geometry_shape_main"] for s in ["events", "images", "buildings"]]
    selected = [c for c in metrics if c in d]
    merged = cov.merge(d[keys + [c for c in selected if c not in cov]], on=keys, how="left", validate="one_to_one")
    assert len(merged) == 66 and (merged.events.eq(0).sum() == 5)
    merged.insert(1, "direction_name_zh", merged.route_id.map(NAMES))
    write_csv(HERE / "F11_all_directions_compact.csv.gz", merged)

    loow = pd.read_csv(HERE / "F11_leave_one_worker_out.csv.gz")
    lc = [c for c in loow if c in {"route_id", "control", "removed_worker", "removed_worker_id", "events_before", "events_after", "pools_after", "images_before", "images_after", "buildings_before", "buildings_after", "class_support_lost", "retained_event_fraction", "zero_support"} or c in {"within_joint_stable_main", "cross_joint_stable_main", "gap_joint_stable_main", "gap_geometry_noQ_main", "gap_geometry_shape_main", "net_B8L2_change", "net_D10_change", "within_Q_drop_gt5", "cross_Q_drop_gt5", "B_complete", "C_complete", "source_block_log_ratio"}]
    write_csv(HERE / "F11_LOOW_compact.csv.gz", loow[lc])
    b = pd.read_csv(HERE / "F11_per_building.csv.gz")
    bk = [c for c in ["route_id", "method_id", "setting", "control", "building", "net_B8L2_change", "net_D10_change", "source_block_log_ratio", "source_block_geometric_ratio", "within_joint_stable_main", "cross_joint_stable_main", "gap_geometry_noQ_main", "gap_geometry_shape_main", "within_Q_drop_gt5", "cross_Q_drop_gt5", "B_complete", "C_complete", "net_B8L2_change_per_image_p10"] if c in b]
    write_csv(HERE / "F11_per_building_compact.csv.gz", b[bk])

    fixed = d[d.setting.eq("fixed_n_m") & d.control.eq("overall")].set_index("route_id")
    stress = d[d.setting.eq("sampled_stress") & d.control.eq("overall")].set_index("route_id")
    # The registered setting name is read from the existing table, never inferred from outcomes.
    if stress.empty:
        candidates = sorted(set(d.setting) - {"fixed_n_m"})
        assert len(candidates) == 1
        stress = d[d.setting.eq(candidates[0]) & d.control.eq("overall")].set_index("route_id")
    rows = []
    for rid in NAMES:
        r, s = fixed.loc[rid], stress.loc[rid]
        rows.append(f"| {rid} {NAMES[rid]} | {int(r.events)}／{int(r.images)}／{int(r.buildings)} | {r.net_B8L2_change:+.3f} | {100*r.gap_joint_stable_main:+.2f}／{100*r.gap_geometry_noQ_main:+.2f} | {100*r.within_Q_drop_gt5:.2f}／{100*r.cross_Q_drop_gt5:.2f} | {r.source_block_geometric_ratio:.3f}（{int(r.source_block_log_ratio_known_events)}） | {s.net_B8L2_change:+.3f}／{s.source_block_geometric_ratio:.3f} |")
    table = "\n".join(rows)
    content = f"""# 正向十一条冻结方向：评估后的保留、降级与反例

## 结论与口径

**保留高 Q 人群中的来源任务效率分层，以及 Q／T／几何四类的有向质量差；不能把这些结果升级为普遍可互换的人员类别。** 高 Q23 慢→快在评估固定 13 人、替换 2 人时，来源块用时的几何均值比为 0.375，B8L2 C−B 为 −0.029 分；这首先是来源报告效率结果。高 Q23 同构成与跨构成的主联合稳定率都只有 63.22%，同类换人也有约 5.92% 的有符号下降超过 5 分。存在更快而明显变差、稳定但在冻结参考下低分，以及同类换人巨降的精确案例，不能只用总体接近零的均差宣布质量等效。

本表读取已经冻结的 11 条 F 方向，未改标签、参考、评分、融合或阈值。评估共 9,004 个 ABC 事件：固定设置 3,804，压力设置 5,200；支持 50 个条件池、45 张真实图片、6 栋建筑。同图 Manual／Semi 不计作两张独立图片。全部 66 个方向×设置×控制单元均保留，5 个空单元不补零。具体成员由冻结请求重建，代表案例另外独立保存。

每个事件的 A 是基准团队；B 与 A 的类别构成相同并换入其他具体人员；C 使用相同背景、总人数、替换规模而换入目标类别。C−B 表示相对同类替换的净方向。事件先在同图内等权，再对楼内图片等权，最后建筑等权。重复团队／A／核心不成为新的独立图；下表的支持顺序为事件／真实图／楼。低尾是每图内分位数再按同样建筑层级汇总，不能当作所有独立人员的总体分位数。

## 全部十一方向：固定设置与压力设置并列

固定为 n=13、m=2；两条 Semi 方向为 n=7、m=2。压力设置从已注册有限整数框架分层抽样，不是穷举所有 n、m、具体成员及背景。主联合与去 Q 阈值几何的差都按“同构成稳定率−跨构成稳定率”报告；正值表示同构成更稳定，单位为百分点。去 Q 阈值几何仍保留节点数相同要求，并不意味着分类的历史 Q 信号被移除。

| 冻结方向 | 固定支持：事件／图／楼 | 固定 C−B B8L2 | 主联合／去 Q 几何差（百分点） | 同类／跨类有符号 Q 降>5（%） | 来源块 C/B 几何均值比（时间可比事件） | 压力 C−B B8L2／时间比 |
|---|---:|---:|---:|---:|---:|---:|
{table}

时间比计算为 `exp(楼等权均值(图均值(事件 log(来源块 C 秒数 / 来源块 B 秒数))))`。它不是 C/B 的算术平均、不是总成本比、不是并行完成时间，也不是修改 GT 后目标重做成本。来源记录秒数与每替换人员净秒差另存表；固定背景缺时间不会抹去已知替换块的净差。新来源的 `target_time_seconds` 全部为 null、已知条数为 0，不是数值 0 哨兵。缺时间、缺分与完整失败分别保留。

## 高 Q 的效率规则：有用，但不保证质量等效

高 Q23 是历史十栋楼 `q_beta≥0` 的 23 人（15 新、8 旧）；旧 Q 三分位高类 18 人是另一定义。二者不能混用。F01 的 11 名慢类与 12 名快类在 42 图／6 楼有实际块支持：固定整体 C−B −0.029，D10 −0.111；B、C 完整率分别 97.43%、99.31%。436／480 个事件的来源块时间可比，几何均值比 0.375，来源块净秒差 −417.3 秒。时间可比事件上的“至少省 20%、B/C 完整、C 不比 B 低超过 2 分”楼等权率为 76.36%；再要求 B/C 去 Q 几何近似则为 68.77%。这保留了联合收益条件，不能把不同支持上的省时均值与质量均值拼接成逐队成功率。

仅保留三块来源人数构成相同，F01 为 332 事件／38 图／6 楼：C−B −0.141，时间比 0.347（309 事件可比）。进一步要求 A、B、C 替换块任意两两的历史条件 Q 均值差≤3，只余 97 事件／35 图／6 楼：C−B −0.745、D10 −0.814，时间比 0.380（89 事件可比）。主联合同类／跨类为 71.37%／70.00%；去 Q 几何差 +6.90 个百分点，允许冗余节点不同的连续形状判据为 85.43%／75.41%。这说明控制后仍有明显效率差，同时几何并非普遍等价。这里使用三块两两 Q 约束；共同 26 人面板的邻块对 A 约束更宽，二者不能混称完全相同的匹配。

F02 高 Q18 固定整体 C−B +0.236、时间比 0.366；同来源后 C−B −0.063、时间比 0.346。Q 近似子集只有 22 事件／10 图／5 楼，时间可比 14 事件／9 图／4 楼，跨类入组只有 2 人；不能拿该子集更大的节时比解释为更广泛证据。F03 高 Q 新人 T／编辑组合固定质量 +0.102、时间比 0.736，Q 近似后 +0.910、0.641；但去 Q 几何差为负，适合作为条件效率角色保留，不能命名为更可互换的结构类。

## 类别、历史 Q、来源与具体人员分别说明什么

F04 Q／T／几何 C04→C02 固定损失 −2.105 分、去 Q 几何同类优势 +10.90 个百分点、时间比 1.161；反向 F05 收益 +2.270 分、几何同类优势 +6.38 个百分点、时间比 0.857。仅来源匹配仍为 −2.250 与 +2.631 分。两方向历史入组 Q 差约 −14.65 与 +15.78，三块 Q 近似都无支持。因此可以报告整体类别效用、方向与结构差，不能据此宣称独立于 Q 的剩余作用已被验证。F06 高 Q23 多点→少点固定 −1.163 分，来源匹配 −0.984；质量方向可保留，但去 Q 几何差仅 +2.25 个百分点，来源匹配后 +1.18，且同样没有 Q 近似支持，不能把“多点”直接写成补足必要结构的因果机制。

删一人敏感性删除所有 A/B/C 中涉及该人的事件，包括固定背景，然后在剩余图／楼支持重算原估计；它不是新员工验证，也不是置信区间。F04 的所有单人删除质量范围 −3.873 至 −0.895、F05 +1.242 至 +3.476、F06 −1.919 至 −0.145，方向均保留。F01 质量范围 −2.017 至 +0.878，几何差也可翻转；来源时间比却始终约 0.330—0.431，显示效率结论比质量近似更不依赖某一人。F01 Q 近似后删人仍为 0.326—0.436，但剩余支持最低降到 10 图／4 楼。F02 的 Q 近似子集中，删去 W002、W030、W033 或 W035 任一人会清空该子集，必须明确其容量依赖；这四人可能处于替换块或共同背景，不统称为目标入组人员。

## 困难、scope 与 Semi：保留条件角色，降级泛化主张

F07 困难三类 C03→C02 在发现广框架中曾有 +7.547 分，评估固定 13／2 变成 −0.965（7 图／5 楼），而压力设置为 +4.482；去 Q 几何同类优势在固定与压力均为负。该结果支持明显条件交互和反例，不能保留为固定配比的通用质量提升规则。时间比固定 0.632、压力 0.603，效率方向仍可描述。困难标签来自既有非盲全景／参考几何复核，不能称为新图自动采集前选人验证。

F08 scope 高 OUT→低 OUT 固定质量 +0.487、来源比 0.855，但去 Q 几何差 −2.29 个百分点、删人质量可翻转。Q 近似只余 24 事件／18 图／6 楼，质量 −0.678、比 0.644，连续形状与节点相同判据方向不一致。scope 只能解释回答范围倾向；裁定正确率与未知机会未混入该类。F10 新报告低未改→高未改在 Manual 的固定质量 +0.533、时间比 0.871，却没有可重复的同类几何优势；作为失败的互换类型／条件效率角色保留。低未改、高未改不是已证实纠错能力排序。

F09 Semi 低编辑→高编辑只有 60 事件／5 图／4 楼，固定 +0.909 分、时间比 1.362，去 Q 几何同类优势 +11.46 个百分点；删人后的质量范围 −2.760 至 +3.062，时间一直较慢。可保留“在这些已测条件下较多编辑的角色可能增加来源用时，质量与几何需要分别复查”，不保留泛化质量增益保证。F11 Semi 新报告高未改的负面质量假设没有复现：发现 −3.583，评估固定 +0.827、压力 +1.305；固定与压力的去 Q 几何差仍为负。5 图／4 楼的方向反转和极小 Q 近似支持不能隐藏。

新报告错误未改、旧确认错误未改、正常未修改和已确认纠正是不同证据。旧确认错误仅在 1 图／1 楼给每人约一次机会，达不到历史至少 3 次／2 楼的拟合条件，失败候选已登记；缺机会不补零。新批缺逐份初始几何，以上编辑／未改只能是报告行为类别，不能编造净纠错收益。

## 同班同图 Manual／Semi 的补充复查

独立冻结的 linked-condition 实验在评估保留 330 个 n≥3、m≥2 的同班、同背景、同人数、同参考配对，合计 5 图／4 楼／35 人。它与 F11 各自原有规则不同，不能借用别的多变量 Semi 类当作 F11 迁移证据，也不能把观察到的模式差异当作随机分配的模式因果效应。

同一高 Q23 慢→快方向在 25 对、3 图、2 楼上，Manual C−B +0.903、Semi −0.202；B 队的冻结质量均值分别 92.45 与 74.66。新编辑低→高在 45 对、5 图、4 楼上，Manual −1.173、Semi +4.878；同类主联合稳定率由 Manual 的 56.94% 到 Semi 的 68.06%，但去 Q 几何稳定率由 87.50% 到 75.00%，B 队质量水平也由 92.39 到 83.10。因而不能笼统写“Semi 同类总是更不稳”，也不能把某个联合稳定率上升解释成质量更好或结构更相似。这里的编辑类别来自已冻结的 `F20_new_NewEdit_qK2`，与 F09 同批机会类的成员阈值应按各自注册文件追溯。

linked-condition 表内时间比使用 C/B 的算术层级均值，本节不拿其数值与 F11 的几何均值比直接排序。该表中的新报告未改低→高在 Manual／Semi 分别约 +0.093／−0.112 分，仍不支持将高未改普遍称为盲信。scope 高 OUT→低 OUT 在同班子集为 −3.875／−1.824 分，是总体结果以外需要保留的机会与成员组合反例。

## 优先人工看图的精确案例

`PRIORITY_CASES.json` 保存精确事件、成员、原始冻结参考、参数、A/B/C 必要最终几何、分数／完整状态、来源块秒数以及可用原图缓存 SHA。

1. **I20_58467a3dfec46697895062，q9vSo1VnCiC-03**：来源和 Q 近似，高 Q23 慢→快；A/B/C 为 96.168／95.727／96.117 分，B/C 块秒数 1387.264／445.642，字面事件比 0.321，两种替换几何均近。缓存原图已定位，适合展示可用效率结果。
2. **I20_280b1d2b8c945dd9fa64e3，UwV83HsGsw3-09**：来源和 Q 近似、两种替换主联合都稳定，但 A/B/C 在冻结参考下只有 25.491／25.868／25.566 分，时间比 0.398。适合展示“稳定且快，仍可能低质量”。
3. **I20_4da3873a0cfaa6960e95dd，q9vSo1VnCiC-30**：快类 C 队仍较省时，却从 B 的 90.546 降到 37.103，净 −53.443，A/C floor 差 0.455。代表跨类失败尾部。
4. **I20_4a6a26f13240998cc23ff9，UwV83HsGsw3-12**：A/B/C 为 96.553／55.830／98.358，同类换人也可发生严重下降，跨类反而改善。该反例直接说明不能把同类内部全部人员视作等价。

## 复现与精简证据

运行 `compile_findings.py` 只从既有汇总导出本说明与小表；不重跑模型或融合。`F11_all_directions_compact.csv.gz` 包含全部 66 个单元、空支持／失败、质量、稳定、几何、来源秒数和各主要指标真实分母；`F11_LOOW_compact.csv.gz` 保留全部单人删除结果与支持变化；`F11_per_building_compact.csv.gz` 保留逐楼值。原 `analyze_assessment_directions.py`、冻结方向请求／标签、根原生融合和 pair 诊断代码可重建这些表。`F11_coverage_and_failures.csv.gz` 是 66 单元的独立覆盖核对表；缺失始终保持缺失。
"""
    (HERE / "F11_FINDINGS_ZH.md").write_text(content, encoding="utf-8")
    files = [HERE / x for x in ["F11_all_directions_compact.csv.gz", "F11_LOOW_compact.csv.gz", "F11_per_building_compact.csv.gz", "F11_FINDINGS_ZH.md", "PRIORITY_CASES.json"]]
    write_json(HERE / "F11_COMPACT_RECEIPT.json", {
        "script_sha256": sha(Path(__file__)), "frozen_rule_sha256": sha(ROOT / "interchangeability_20261020/assessment/ASSESSMENT_FREEZE.json"),
        "no_new_experiment": True, "all_control_cells": len(merged), "empty_cells": int(merged.events.eq(0).sum()),
        "source_time_ratio_is_geometric_hierarchical": True, "files": [{"file": p.name, "bytes": p.stat().st_size, "sha256": sha(p)} for p in files]})
    print(json.dumps({"files": len(files), "bytes": sum(p.stat().st_size for p in files), "loow_rows": len(loow)}, ensure_ascii=False))

if __name__ == "__main__":
    main()
