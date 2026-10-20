#!/usr/bin/env python3
"""Make small, exact-table evidence and a Chinese interpretation; no new fit."""
from __future__ import annotations
import collections
import gzip
import hashlib
import json
import math
from pathlib import Path
import numpy as np
import pandas as pd

P = Path(__file__).resolve().parent
R = P / "results"
OUT = P / "compact_common_evidence"


def read(path):
    return json.loads(gzip.decompress(path.read_bytes())) if path.suffix == ".gz" else json.loads(path.read_text())


def csv(path, frame):
    raw = frame.to_csv(index=False).encode()
    data = gzip.compress(raw, compresslevel=6, mtime=0) if path.suffix == ".gz" else raw
    path.write_bytes(data)
    assert path.read_bytes() == data
    if path.suffix == ".gz":
        assert gzip.decompress(path.read_bytes()) == raw


def nstr(v):
    return "ALL" if str(v) == "ALL" else str(int(float(v)))


def main():
    assert (R / "SUMMARY_RECEIPT.json").exists()
    OUT.mkdir(parents=True, exist_ok=True)
    reg = read(P / "COMMON_PANEL_REGISTRATION.json")
    profile = pd.read_csv(P.parent / "CLASS_EXPLANATIONS_ZH.csv.gz", usecols=["method_id", "class_id", "class_name_zh", "people", "new_people", "old_people", "q_beta_mean", "new_time_multiplier", "exact_members"])
    core_cols = ["method_id", "support", "restriction", "n", "pools", "buildings", "cores", "eligible_A_observations", "unique_teams", "unique_people",
                 "within_directed_pairs_observations", "cross_directed_pairs_observations",
                 "within_joint_stable_strict", "cross_joint_stable_strict", "gap_joint_stable_strict",
                 "within_joint_stable_main", "cross_joint_stable_main", "gap_joint_stable_main",
                 "within_joint_stable_wide", "cross_joint_stable_wide", "gap_joint_stable_wide",
                 "within_geometry_noQ_main", "cross_geometry_noQ_main", "gap_geometry_noQ_main",
                 "within_floor_jaccard_difference", "cross_floor_jaccard_difference", "excess_floor_jaccard_difference",
                 "within_structure_bound_cyclic_deg", "cross_structure_bound_cyclic_deg", "excess_structure_bound_cyclic_deg",
                 "within_abs_B8L2_change", "cross_abs_B8L2_change", "excess_abs_B8L2_change",
                 "within_neighbor_B8L2", "cross_neighbor_B8L2", "within_neighbor_complete", "cross_neighbor_complete",
                 "within_quality_drop_gt5", "cross_quality_drop_gt5", "excess_source_block_log_ratio",
                 "finite_structure_bound_cyclic_deg_pools", "finite_structure_bound_cyclic_deg_buildings",
                 "finite_B8L2_change_pools", "finite_B8L2_change_buildings", "finite_source_block_log_ratio_pools", "finite_source_block_log_ratio_buildings"]
    core = pd.read_csv(R / "core_aggregate.csv.gz", usecols=core_cols)
    core.n = core.n.map(nstr)
    csv(OUT / "method_common_support.csv.gz", core)
    # Full minus each removal is paired at the building and n/restriction level.
    dcols = ["method_id", "support", "restriction", "n", "building", "gap_joint_stable_main", "gap_geometry_noQ_main",
             "excess_floor_jaccard_difference", "excess_abs_B8L2_change", "within_joint_stable_main"]
    bd = pd.read_csv(R / "core_per_building.csv.gz", usecols=dcols)
    bd = bd.loc[bd.support.eq("common16")].copy()
    bd.n = bd.n.map(nstr)
    delta_rows, delta_buildings = [], []
    for k in (2, 3):
        full = f"F20_newCommon_Full_balanced_K{k}"
        for mid in sorted(bd.method_id.unique()):
            if mid == full or not mid.endswith(f"K{k}"):
                continue
            key = ["restriction", "n", "building"]
            pair = bd.loc[bd.method_id.eq(full)].merge(bd.loc[bd.method_id.eq(mid)], on=key, suffixes=("_full", "_deleted"), validate="one_to_one")
            pair["K"] = k
            pair["deleted_method_id"] = mid
            metrics = dcols[5:]
            for m in metrics:
                pair["Full_minus_deleted_" + m] = pair[m + "_full"] - pair[m + "_deleted"]
            for r in pair.itertuples():
                delta_buildings.append(dict(K=k, deleted_method_id=mid, restriction=r.restriction, n=r.n, building=r.building,
                    **{"Full_minus_deleted_" + m: getattr(r, "Full_minus_deleted_" + m) for m in metrics}))
            for (restriction, n), g in pair.groupby(["restriction", "n"]):
                row = dict(K=k, deleted_method_id=mid, restriction=restriction, n=n, paired_buildings=g.building.nunique())
                for m in metrics:
                    z = g["Full_minus_deleted_" + m].dropna()
                    row["Full_minus_deleted_" + m] = z.mean()
                    row["positive_buildings_" + m] = int((z > 1e-12).sum())
                    row["negative_buildings_" + m] = int((z < -1e-12).sum())
                delta_rows.append(row)
    csv(OUT / "ablation_delta_same_bases.csv.gz", pd.DataFrame(delta_rows))
    csv(OUT / "ablation_delta_per_building.csv.gz", pd.DataFrame(delta_buildings))
    randcols = ["method_id", "full_method_id", "restriction", "n", "pools", "buildings", "eligible_A_observations",
                "gap_joint_stable_main", "gap_geometry_noQ_main", "full_gap_joint_stable_main", "full_gap_geometry_noQ_main",
                "full_minus_random_gap_joint_stable_main", "full_minus_random_gap_geometry_noQ_main"]
    rand = pd.read_csv(R / "random_aggregate.csv.gz", usecols=randcols)
    rand.n = rand.n.map(nstr)
    csv(OUT / "random_partition_comparisons.csv.gz", rand)
    rrows = []
    for (mid, restriction, n), g in rand.groupby(["full_method_id", "restriction", "n"]):
        row = dict(full_method_id=mid, restriction=restriction, n=n, random_partitions=len(g), pools_min=g.pools.min(), pools_max=g.pools.max(),
                   eligible_A_min=g.eligible_A_observations.min(), eligible_A_max=g.eligible_A_observations.max())
        for m in randcols[7:]:
            z = g[m].dropna()
            row.update({m + "_" + s: v for s, v in (("min", z.min()), ("p10", z.quantile(.1)), ("median", z.median()), ("p90", z.quantile(.9)), ("max", z.max()), ("positive_partitions", int((z > 0).sum())))})
        rrows.append(row)
    csv(OUT / "random_baseline_range.csv", pd.DataFrame(rrows))
    vcols = ["method_id", "support", "restriction", "n", "outgoing_vector", "incoming_vector", "pools", "buildings", "cores", "eligible_A_observations", "unique_teams", "unique_people",
             "within_joint_stable_main", "cross_joint_stable_main", "gap_joint_stable_main", "within_geometry_noQ_main", "cross_geometry_noQ_main", "gap_geometry_noQ_main",
             "within_floor_jaccard_difference", "cross_floor_jaccard_difference", "excess_floor_jaccard_difference",
             "within_structure_bound_cyclic_deg", "cross_structure_bound_cyclic_deg", "excess_node_count_difference",
             "within_neighbor_B8L2", "cross_neighbor_B8L2", "excess_B8L2_change", "excess_D10_change",
             "within_quality_drop_gt5", "cross_quality_drop_gt5", "within_neighbor_complete", "cross_neighbor_complete", "excess_source_block_log_ratio"]
    vectors = pd.read_csv(R / "vectors_aggregate.csv.gz", usecols=vcols)
    vectors.n = vectors.n.map(nstr)
    csv(OUT / "all_specific_vectors.csv.gz", vectors)
    fullmid = "F20_newCommon_Full_balanced_K3"
    pure = {c: "|".join(f"C0{i}:{2 if i == c else 0}" for i in (1, 2, 3)) for c in (1, 2, 3)}
    selected = {(pure[i], pure[j]) for i in (1, 2, 3) for j in (1, 2, 3) if i != j}
    vbcols = [c for c in vcols if c not in ("pools", "buildings", "cores", "eligible_A_observations", "unique_teams", "unique_people")] + ["building"]
    vb = pd.read_csv(R / "vectors_per_building.csv.gz", usecols=vbcols)
    vb = vb.loc[vb.method_id.eq(fullmid) & vb.support.eq("common16") & vb.restriction.eq("all") &
                pd.Series(list(zip(vb.outgoing_vector, vb.incoming_vector)), index=vb.index).isin(selected)].copy()
    vb.n = vb.n.map(nstr)
    vb["source_block_geometric_ratio_C_over_B"] = np.exp(vb.excess_source_block_log_ratio)
    csv(OUT / "FullK3_pure_block_directions_per_building.csv.gz", vb)
    # Actual distinct changed-block people, separate from the whole-team union.
    anchors = {x["anchor_id"]: x for x in read(P / "common_anchors.json.gz")["anchors"]}
    seen = collections.defaultdict(set)
    bcols = ["method_id", "support", "restriction", "anchor_id", "outgoing_vector", "incoming_vector", "n", "used_block_indices"]
    for path in sorted((R / "parts").glob("*.vectors.csv.gz")):
        z = pd.read_csv(path, usecols=lambda c: c in bcols)
        if z.empty:
            continue
        z = z.loc[z.method_id.eq(fullmid) & z.support.eq("common16") & z.restriction.eq("all")]
        for r in z.itertuples():
            pair = (r.outgoing_vector, r.incoming_vector)
            if pair not in selected:
                continue
            anchor = anchors[r.anchor_id]
            workers = set().union(*(set(anchor["blocks"][i]["worker_ids"]) for i in json.loads(r.used_block_indices)))
            seen[pair + (nstr(r.n),)].update(workers)
            seen[pair + ("ALL",)].update(workers)
    support = pd.DataFrame([dict(outgoing_vector=k[0], incoming_vector=k[1], n=k[2], actual_block_people=len(v), actual_block_workers="|".join(sorted(v))) for k, v in seen.items()])
    selected_table = vectors.loc[vectors.method_id.eq(fullmid) & vectors.support.eq("common16") & vectors.restriction.eq("all") &
                    pd.Series(list(zip(vectors.outgoing_vector, vectors.incoming_vector)), index=vectors.index).isin(selected)].copy()
    selected_table = selected_table.merge(support, on=["outgoing_vector", "incoming_vector", "n"], validate="one_to_one")
    for (outvec, invec, n), z in vb.groupby(["outgoing_vector", "incoming_vector", "n"]):
        where = selected_table.outgoing_vector.eq(outvec) & selected_table.incoming_vector.eq(invec) & selected_table.n.eq(n)
        selected_table.loc[where, "Q_positive_buildings"] = int((z.excess_B8L2_change > 0).sum())
        selected_table.loc[where, "Q_negative_buildings"] = int((z.excess_B8L2_change < 0).sum())
        selected_table.loc[where, "source_faster_buildings"] = int((z.excess_source_block_log_ratio < 0).sum())
        selected_table.loc[where, "Q_building_min"] = z.excess_B8L2_change.min()
        selected_table.loc[where, "Q_building_max"] = z.excess_B8L2_change.max()
    selected_table["source_block_geometric_ratio_C_over_B"] = np.exp(selected_table.excess_source_block_log_ratio)
    csv(OUT / "FullK3_pure_block_directions.csv.gz", selected_table)
    csv(OUT / "FullK3_class_explanations.csv", profile.loc[profile.method_id.eq(fullmid)])

    whole = core.loc[core.support.eq("common16") & core.restriction.eq("all") & core.n.eq("ALL")].set_index("method_id")
    lines = ["# 同 26 人、同团队、同两人替换面板：特征组消融与具体构成方向", "",
             "本面板用于比较候选分区的信息增量。分类全部来自旧 10 栋 history；从发现侧 6 栋楼普通 Manual 池中，只纳入七域共同机会的 26 名新人。仅用元数据固定 n=5/9/13/17、每池人数节点两个不同共同背景、m=2。剩余两人块不多于48时全取，否则按固定哈希取48；穷举已选块间所有不共享成员的关系。主比较对每个 A 分别平均同构成 B 和异构成 C，再对共同背景、图片、建筑等权。", "",
             f"计算了 {reg['unique_teams']:,} 支不同团队，{reg['anchors']} 个背景，49 图/6 楼，{reg['disjoint_pair_observations']:,} 个无序两人块关系；不是遍历所有人员团队。16 方法都能同时找到 B、C 的共同 A 交集为 10,762 个 A 观测、318 个背景、44 图/6 楼、13,896 支实际团队。多次出现的 A、成对关系或团队不是新增独立图片。", "",
             "## 1. 总体互换区分不强，人数效应比新增变量的普适区分更清楚", "",
             "| 方法 | 同构成联合稳定 | 异构成联合稳定 | 差（百分点） | 无 Q 几何差（百分点） |", "|---|---:|---:|---:|---:|"]
    for mid in ("F20_newCommon_Full_balanced_K2", "F20_newCommon_Full_balanced_K3", "F20_newCommon_NoQ_balanced_K3", "F20_newCommon_NoT_balanced_K3", "F20_newCommon_Nogeometry_balanced_K3"):
        r = whole.loc[mid]
        lines.append(f"| {mid} | {r.within_joint_stable_main:.4f} | {r.cross_joint_stable_main:.4f} | {100*r.gap_joint_stable_main:+.3f} | {100*r.gap_geometry_noQ_main:+.3f} |")
    lines += ["", "Full K3 在 n=9 时联合差为 +2.448 个百分点，但无 Q 几何差为 −0.047 个百分点。n=5 的同构成联合稳定约39.5%，n=13/17约75.4%/76.4%；m固定为2，替换比例同时从40%下降到15.4%/11.8%，因此这是人数与替换比例共同变化，不能解释为纯人数因果效应。",
              "", "删 geometry 后的 K2、删 new-report-nonedit 或 scope 后的 K3，与各自 Full 产生同一人员分区；精确相同结果说明此拟合中删字段未改分类，不等于相关行为没有独立价值。七域分区存在冗余和相关信号。",
              "", "## 2. 随机分区给出量级参照，不能用作显著性裁判", "",
              "每 K 做20个保持人员类别容量的固定随机分区，使用同一批真实团队。每个随机分区与对应 Full 在共同可比较 A 中配对；不同随机分区的 A 支持略有差别。K2随机联合差范围 −0.755 到 +0.549 个百分点，Full 与随机的配对差中位数 +0.183 个百分点。K3随机联合差范围 −0.892 到 +1.459 个百分点，Full 与随机的配对差中位数 +0.868 个百分点，20次中17次为正；这些计数不是外部样本，也不是 p 值。K3无 Q 几何的配对增量中位数仅 +0.340 个百分点。",
              "", "## 3. 具体有向构成仍然揭示质量和效率角色", "",
              "Full K3：C01 为9人、较快但相对Q低/新报告未改倾向较高；C02 为9人、较慢且相对Q低、编辑倾向较高；C03 为8人、相对Q高、点数偏多。Q均值分别约−3.20、−2.61、+8.58；来源内历史时间倍数约0.890、1.272、0.978。这里全部是新人，不混入新旧来源差。", "",
              "下表固定换2人，其他背景逐比较完全相同；B是A同构成的新成员，C是另一构成。时间比为来源任务报告块用时 C/B 的几何均值；不是目标重做成本。", "",
              "| 两人块方向 | 图/楼 | 实际块人员 | 不同团队 | C−B B8 | D10 | C/B来源用时 | Q正/负楼 |", "|---|---:|---:|---:|---:|---:|---:|---:|"]
    for i, j in ((2, 3), (2, 1), (1, 3), (3, 1), (3, 2), (1, 2)):
        r = selected_table.loc[selected_table.outgoing_vector.eq(pure[i]) & selected_table.incoming_vector.eq(pure[j]) & selected_table.n.eq("ALL")].iloc[0]
        lines.append(f"| 2×C0{i}→2×C0{j} | {r.pools}/{r.buildings} | {r.actual_block_people} | {r.unique_teams} | {r.excess_B8L2_change:+.3f} | {r.excess_D10_change:+.3f} | {r.source_block_geometric_ratio_C_over_B:.3f} | {int(r.Q_positive_buildings)}/{int(r.Q_negative_buildings)} |")
    lines += ["", "C02→C03 同时表现为质量改善和来源报告时间降低，且异构成结果对A的几何偏差更小；这是一种有方向的质量/效率角色，不是‘所有不同类都更不稳定’。C02→C01 可作为效率方向继续复查：平均质量接近，报告用时更短；必须保留逐楼质量下降和具体成员失败，不能据总体均值直接宣布等效。",
              "", "C03→C01 的同构成下降超过5分比例约8.28%，异构成约21.01%；平均 C−B B8下降4.223。前后方向的A资格和实际背景集合不同，所以反向数值不必严格互为相反数。图表不能用有向收益正负相抵后的全表平均掩盖这种差异。",
              "", "## 4. 历史 Q 限制与泛化边界", "",
              "次级分析把每个邻块与A块的历史 q_beta 均值差限制在±3；它不是任意B和C之间都相差≤3的三角匹配。重新取16方法共同A后为4,156个A、302背景、43图/6楼。Full K3联合差变为−0.545个百分点，无Q几何差+0.610个百分点。既报告整体分类效用，也报告此限制后的剩余信息；不先消掉Q信号再宣布分类无用。纯类C01/C02到C03的质量收益本来含有较强历史Q差异，不能称超越Q的独立因果效应。",
              "", "本轮仍是已多轮探索v2内的发现，尚未在assessment六栋楼冻结复查这些方向。26人为同一历史共同机会群；历史删楼 Full K2/K3分别有2/3折失去完整分型容量。此面板不证明新员工的标签可可靠估计。目标难度用于条件解释且包含既有非盲复核信息，不当作未经标注新图的自动预选特征。",
              "", "## 复现与精简证据", "",
              "同目录上一级保留 design_common_panel.py、summarize_common_panel.py、common_requests.json.gz、common_anchors.json.gz、COMMON_PANEL_REGISTRATION.json、REGISTERED_COMPARISON.json 及随机标签。融合仍用固定 analysis/composition/fusion_runner.py 和恢复的科学输入；请求成员哈希已核。此目录小表来自已完成的全表，保留全部具体向量汇总、Full/删组逐楼差与全部40随机参照，不只保留赢家。原生最终几何可按精确请求重建，不应把全部中间pair/逐池大表打包。",
              "", "字段说明：gap=同构成稳定率−异构成稳定率；excess=异构成指标−同构成指标；excess_B8L2_change为C−B净方向。floor是足迹1−IoU；cyclic angle仅在节点数相同时可定义，不能用缺角度代替0。完整失败按不稳定保留，分数缺失不补0。unique_people包含固定背景；actual_block_people单独只数A/B/C替换块的人。"]
    (OUT / "COMMON_PANEL_FINDINGS_ZH.md").write_text("\n".join(lines) + "\n")
    receipt = {"source_summary_sha256": hashlib.sha256((R / "SUMMARY_RECEIPT.json").read_bytes()).hexdigest(),
               "files": [{"file": p.name, "bytes": p.stat().st_size, "sha256": hashlib.sha256(p.read_bytes()).hexdigest()} for p in sorted(OUT.iterdir()) if p.is_file()]}
    (OUT / "COMPACT_RECEIPT.json").write_text(json.dumps(receipt, ensure_ascii=False, indent=2))
    print(json.dumps({"compact_bytes": sum(p.stat().st_size for p in OUT.iterdir() if p.is_file()), "files": len(list(OUT.iterdir()))}))


if __name__ == "__main__":
    main()
