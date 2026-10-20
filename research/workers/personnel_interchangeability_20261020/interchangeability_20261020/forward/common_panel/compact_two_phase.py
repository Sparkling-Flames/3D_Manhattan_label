#!/usr/bin/env python3
"""Compact both frozen original16 panels without selecting winners."""
from pathlib import Path
import collections
import gzip
import json
import numpy as np
import pandas as pd
import summarize_common_panel as base

HERE = Path(__file__).resolve().parent
OUT = HERE / "compact_two_phase_evidence"
FULL3 = "F20_newCommon_Full_balanced_K3"

def nstr(x):
    return "ALL" if str(x) == "ALL" else str(int(float(x)))

def records(frame):
    return json.loads(frame.to_json(orient="records"))

def main():
    OUT.mkdir(exist_ok=True)
    core_keep = ["method_id", "support", "restriction", "n", "pools", "buildings", "cores", "eligible_A_observations", "unique_teams", "unique_people",
                 "within_directed_pairs_observations", "cross_directed_pairs_observations",
                 "within_joint_stable_strict", "cross_joint_stable_strict", "gap_joint_stable_strict",
                 "within_joint_stable_main", "cross_joint_stable_main", "gap_joint_stable_main",
                 "within_joint_stable_wide", "cross_joint_stable_wide", "gap_joint_stable_wide",
                 "within_geometry_noQ_main", "cross_geometry_noQ_main", "gap_geometry_noQ_main",
                 "within_floor_jaccard_difference", "cross_floor_jaccard_difference", "excess_floor_jaccard_difference",
                 "within_structure_bound_cyclic_deg", "cross_structure_bound_cyclic_deg", "excess_structure_bound_cyclic_deg",
                 "within_abs_B8L2_change", "cross_abs_B8L2_change", "excess_abs_B8L2_change",
                 "within_quality_drop_gt5", "cross_quality_drop_gt5", "within_neighbor_complete", "cross_neighbor_complete",
                 "within_neighbor_B8L2", "cross_neighbor_B8L2", "excess_source_block_log_ratio",
                 "finite_structure_bound_cyclic_deg_pools", "finite_structure_bound_cyclic_deg_buildings",
                 "finite_B8L2_change_pools", "finite_B8L2_change_buildings", "finite_source_block_log_ratio_pools", "finite_source_block_log_ratio_buildings"]
    vector_keep = ["method_id", "support", "restriction", "n", "outgoing_vector", "incoming_vector", "pools", "buildings", "cores", "eligible_A_observations", "unique_teams", "unique_people",
                   "within_joint_stable_main", "cross_joint_stable_main", "gap_joint_stable_main", "within_geometry_noQ_main", "cross_geometry_noQ_main", "gap_geometry_noQ_main",
                   "within_floor_jaccard_difference", "cross_floor_jaccard_difference", "excess_floor_jaccard_difference",
                   "within_structure_bound_cyclic_deg", "cross_structure_bound_cyclic_deg", "excess_node_count_difference",
                   "excess_B8L2_change", "excess_D10_change", "within_quality_drop_gt5", "cross_quality_drop_gt5",
                   "within_neighbor_complete", "cross_neighbor_complete", "excess_source_block_log_ratio"]
    random_keep = ["method_id", "full_method_id", "restriction", "n", "pools", "buildings", "eligible_A_observations",
                   "gap_joint_stable_main", "gap_geometry_noQ_main", "full_gap_joint_stable_main", "full_gap_geometry_noQ_main",
                   "full_minus_random_gap_joint_stable_main", "full_minus_random_gap_geometry_noQ_main"]
    cores, vectors, randoms, deltas, delta_buildings, pure_buildings, pure_frames = [], [], [], [], [], [], []
    registration = {}
    pure = {"|".join(f"C0{i}:{2 if i == c else 0}" for i in (1, 2, 3)) for c in (1, 2, 3)}
    for phase, panel in (("discovery", HERE), ("assessment", HERE / "assessment")):
        result = panel / "results"
        assert (result / "SUMMARY_RECEIPT.json").exists()
        reg = base.read(panel / "COMMON_PANEL_REGISTRATION.json")
        registration[phase] = dict(registration_sha256=base.sha(panel / "COMMON_PANEL_REGISTRATION.json"),
                                    summary_sha256=base.sha(result / "SUMMARY_RECEIPT.json"),
                                    requested_teams=reg["unique_teams"], requested_cores=reg["anchors"], buildings=reg["buildings"])
        c = pd.read_csv(result / "core_aggregate.csv.gz", usecols=core_keep)
        c["phase"] = phase; c.n = c.n.map(nstr); cores.append(c)
        r = pd.read_csv(result / "random_aggregate.csv.gz", usecols=random_keep)
        r["phase"] = phase; r.n = r.n.map(nstr); randoms.append(r)
        v = pd.read_csv(result / "vectors_aggregate.csv.gz", usecols=vector_keep)
        v["phase"] = phase; v.n = v.n.map(nstr); vectors.append(v)
        bp = pd.read_csv(result / "core_per_building.csv.gz")
        bp = bp.loc[bp.support.eq("common16")].copy(); bp.n = bp.n.map(nstr)
        metrics = ["gap_joint_stable_main", "gap_geometry_noQ_main", "excess_floor_jaccard_difference", "excess_abs_B8L2_change", "within_joint_stable_main"]
        for k in (2, 3):
            fullmid = f"F20_newCommon_Full_balanced_K{k}"
            for mid in sorted(bp.method_id.unique()):
                if mid == fullmid or not mid.endswith(f"K{k}"):
                    continue
                keys = ["restriction", "n", "building"]
                d = bp.loc[bp.method_id.eq(fullmid), keys + metrics].merge(bp.loc[bp.method_id.eq(mid), keys + metrics], on=keys, suffixes=("_full", "_deleted"), validate="one_to_one")
                rows = d[keys].copy(); rows["phase"] = phase; rows["K"] = k; rows["deleted_method_id"] = mid
                for m in metrics:
                    rows["Full_minus_deleted_" + m] = d[m + "_full"] - d[m + "_deleted"]
                delta_buildings.append(rows)
        vv = v.loc[v.method_id.eq(FULL3) & v.support.eq("common16") & v.restriction.eq("all") & v.outgoing_vector.isin(pure) & v.incoming_vector.isin(pure)].copy()
        ab = {a["anchor_id"]: a for a in base.read(panel / "common_anchors.json.gz")["anchors"]}
        people = collections.defaultdict(set)
        for path in sorted((result / "parts").glob("*.vectors.csv.gz")):
            needed = {"method_id", "support", "restriction", "anchor_id", "outgoing_vector", "incoming_vector", "n", "used_block_indices"}
            z = pd.read_csv(path, usecols=lambda c: c in needed)
            if z.empty:
                continue
            z = z.loc[z.method_id.eq(FULL3) & z.support.eq("common16") & z.restriction.eq("all") & z.outgoing_vector.isin(pure) & z.incoming_vector.isin(pure)]
            for row in z.itertuples():
                anchor = ab[row.anchor_id]
                workers = set().union(*(set(anchor["blocks"][i]["worker_ids"]) for i in json.loads(row.used_block_indices)))
                for n in (nstr(row.n), "ALL"):
                    people[(row.outgoing_vector, row.incoming_vector, n)].update(workers)
        vv["actual_block_workers"] = ["|".join(sorted(people[(row.outgoing_vector, row.incoming_vector, row.n)])) for row in vv.itertuples()]
        vv["actual_block_people"] = vv.actual_block_workers.str.split("|").str.len()
        vv["source_block_geometric_ratio_C_over_B"] = np.exp(vv.excess_source_block_log_ratio)
        pure_frames.append(vv)
        vb = pd.read_csv(result / "vectors_per_building.csv.gz")
        vb = vb.loc[vb.method_id.eq(FULL3) & vb.support.eq("common16") & vb.restriction.eq("all") & vb.outgoing_vector.isin(pure) & vb.incoming_vector.isin(pure)].copy()
        vb["phase"] = phase; vb.n = vb.n.map(nstr); pure_buildings.append(vb)
    c, v, r = [pd.concat(x, ignore_index=True) for x in (cores, vectors, randoms)]
    db = pd.concat(delta_buildings, ignore_index=True)
    keys = ["phase", "K", "deleted_method_id", "restriction", "n"]
    dc = [x for x in db if x.startswith("Full_minus_deleted_")]
    da = db.groupby(keys)[dc].mean().reset_index()
    for m in dc:
        signs = db.groupby(keys)[m].agg(**{m + "_positive_buildings": lambda x: int((x > 1e-12).sum()), m + "_negative_buildings": lambda x: int((x < -1e-12).sum())}).reset_index()
        da = da.merge(signs, on=keys, validate="one_to_one")
    ranges = []
    for key, g in r.groupby(["phase", "full_method_id", "restriction", "n"]):
        row = dict(zip(["phase", "full_method_id", "restriction", "n"], key), partitions=len(g), pools_min=int(g.pools.min()), pools_max=int(g.pools.max()), A_min=int(g.eligible_A_observations.min()), A_max=int(g.eligible_A_observations.max()))
        for col in random_keep[7:]:
            row.update({col + "_min": g[col].min(), col + "_median": g[col].median(), col + "_max": g[col].max(), col + "_positive_partitions": int((g[col] > 0).sum())})
        ranges.append(row)
    puretable = pd.concat(pure_frames, ignore_index=True)
    files = {
        "common16_methods.csv.gz": c, "feature_deletion_effects.csv.gz": da, "feature_deletion_per_building.csv.gz": db,
        "random_controls_all40.csv.gz": r, "random_baseline_ranges.csv.gz": pd.DataFrame(ranges),
        "all16_specific_vectors.csv.gz": v, "FullK3_six_pure_directions.csv.gz": puretable,
        "FullK3_six_pure_directions_per_building.csv.gz": pd.concat(pure_buildings, ignore_index=True)}
    for name, data in files.items():
        base.write_csv(OUT / name, data)
    profile = pd.read_csv(HERE.parent / "CLASS_EXPLANATIONS_ZH.csv.gz")
    base.write_csv(OUT / "FullK3_history_class_profiles.csv.gz", profile.loc[profile.method_id.eq(FULL3)])
    select = c.loc[c.support.eq("common16") & c.restriction.eq("all") & c.n.eq("ALL")]
    lines = ["# 同26人真实团队共同面板：发现与评估复查", "",
             "分类、固定人数节点5/9/13/17、每节点两个元数据背景、替换2人及同构成／异构成比较规则均已冻结。原16项特征组消融采用同一批26名有七域历史机会的新人；在每个A团队内，对同背景、同人数及相同实际换人规模的所有可行B/C邻块分别平均。未改变融合、参考或B8L2／D10评分。新团队不是新独立图片；本轮仍是既有v2建筑的复查。", "",
             "评估原生有10,577支团队、258个背景、41图6楼；16方法都能同时找到B和C的交集保留8,121个A观测、229个背景、31图6楼、10,235支实际团队。发现对应交集为10,762个A、318个背景、44图6楼、13,896队。被容量排除的图／背景保留在注册台账，不补稳定或失败。", "",
             "## 分类整体效用及消融反例", "", "| 阶段 | 方法 | 同构成联合稳定 | 异构成联合稳定 | 差：百分点 | 无Q几何差：百分点 |", "|---|---|---:|---:|---:|---:|"]
    for phase in ("discovery", "assessment"):
        for mid in ("F20_newCommon_Full_balanced_K2", FULL3, "F20_newCommon_NoQ_balanced_K3", "F20_newCommon_NoT_balanced_K3", "F20_newCommon_Nogeometry_balanced_K3"):
            x = select.loc[select.phase.eq(phase) & select.method_id.eq(mid)].iloc[0]
            lines.append(f"| {phase} | {mid.replace('F20_newCommon_', '')} | {x.within_joint_stable_main:.4f} | {x.cross_joint_stable_main:.4f} | {100*x.gap_joint_stable_main:+.3f} | {100*x.gap_geometry_noQ_main:+.3f} |")
    lines += ["", "Full三类小幅联合区分在两阶段均为正，但未形成普遍可互换的形状类别。删几何组在发现侧削弱了联合差，评估侧却得到比Full更大的差；几何组普适增量未复现。删难度组三类在评估也更大。删scope或新报告未改后三类与Full标签完全一致，说明此次拟合存在冗余，不代表这些行为在所有选人目标下均无价值。特征组删除会重拟合分区，不能解释为单变量因果贡献。", "",
             "Full三类评估相对于20次相同类别容量随机人员分区，在每次两方法共同A上的联合差增量中位数+0.863个百分点、19/20为正；无Q几何增量中位数−0.502个百分点，仅8/20为正。Full二类联合增量中位数约−0.028个百分点。随机分区共用同一真实团队，不增加独立图片；这是基线范围，不能当作随机人员试验或p值检验。", "",
             "整体分类效用先保留Q信号。次级把每个邻块对A的历史q_beta均值差限制在±3后，评估Full三类联合差为+0.165个百分点、无Q几何差−0.127个百分点；共同A缩为3,163个、30图6楼。这一A中心条件允许某些B/C相差超过3，并不等于原生ABC三角Qclose匹配。", "",
             "## 已在发现表列出的六个纯两人块方向", "",
             "C01为9人，较快、相对Q较低；C02为9人，较慢、编辑倾向较高且相对Q较低；C03为8人，相对Q较高、点数偏多。历史Q均值约−3.20／−2.61／+8.58；来源内相对时间倍数约0.890／1.272／0.978。类别名称是多变量描述，不是能力等级。", "",
             "| 阶段 | 换出→换入 | 图／楼 | 替换块人员 | 团队 | B8 C−B | D10 C−B | 来源报告块时间C/B |", "|---|---|---:|---:|---:|---:|---:|---:|"]
    for phase in ("discovery", "assessment"):
        for i, j in ((2, 3), (2, 1), (3, 1), (3, 2), (1, 3), (1, 2)):
            outvec = "|".join(f"C0{k}:{2 if k == i else 0}" for k in (1, 2, 3))
            invec = "|".join(f"C0{k}:{2 if k == j else 0}" for k in (1, 2, 3))
            x = puretable.loc[puretable.phase.eq(phase) & puretable.n.eq("ALL") & puretable.outgoing_vector.eq(outvec) & puretable.incoming_vector.eq(invec)].iloc[0]
            lines.append(f"| {phase} | 2C0{i}→2C0{j} | {x.pools}/{x.buildings} | {x.actual_block_people} | {x.unique_teams} | {x.excess_B8L2_change:+.3f} | {x.excess_D10_change:+.3f} | {x.source_block_geometric_ratio_C_over_B:.3f} |")
    lines += ["", "C02→C03的质量与来源任务效率方向在评估仍清楚：29图6楼，B8约+4.140，来源报告块时间约下降22.9%。该类本来具有较高历史Q，不能据此称为Q之外的独立效应。C02→C01的省时继续，但质量从发现约−0.254变为评估约−1.150，需解释为取舍。C03→C01评估质量下降约4.895；同类Q下降超过5分比例约15.66%，跨类约28.08%。稳定、完整与质量方向分别报告，不能通过一个总分合并。", "",
             "评估Full三类同构成联合稳定率随n=5/9/13/17约为28.5%／47.9%／57.6%／74.7%；替换规模固定2人，比例同时下降，且各n可行图有差异。这一结果不能解释成纯人数因果效应。逐人数、逐楼、全部有向向量和坏尾表均保留，不只展示上述六方向。", "",
             "时间是来源任务报告用时或来源内相对用时，不能解释成GT修订后目标重做成本。共同26人的target_time_seconds全为null、known_n=0，未补零；相同背景的时间缺失不妨碍已知替换块的净用时差。困难标签含非盲全景／人工参考几何复核，属于已有难度口径下的条件解释。", "",
             "## 重建与字段", "",
             "运行design_common_panel.py可按两阶段各自登记种子与精确请求重建成员；原生融合沿用冻结fusion_runner.py。summarize_common_panel.py计算两阶段全部实际无交集两人块关系，compact_two_phase.py生成本目录。gap=同构成稳定率−异构成稳定率；excess=跨类指标−同类指标；excess_B8L2_change是平均C−B。角度只对同节点数有效，缺失不补0；完整失败计不稳定，缺失分数保留。actual_block_people仅计被替换块成员，unique_people包括共同背景。", ""]
    (OUT / "COMMON_PANEL_DISCOVERY_ASSESSMENT_ZH.md").write_text("\n".join(lines))
    base.write_json(OUT / "FIELD_CONTRACT.json", dict(registrations=registration, native_input_and_labels_unchanged=True,
                    image_count="Only ordinary Manual here; pool_id and physical image are one-to-one within each phase. Overall native block studies must distinguish pools/images.",
                    support="eligible_A_observations are repeated same-core/base comparisons; unique_teams is the actual member hash union, not independent image count.",
                    direction="All16 outgoing/incoming vectors retained separately. Six FullK3 pure-block directions were already listed in discovery compact output, not chosen using assessment.",
                    quality_tail="quality_drop_gt5 uses signed neighbor-minus-A<−5, not absolute change.", source_time="Observed positive source-task report block sums; target null remains unknown."))
    base.write_json(OUT / "COMPACT_RECEIPT.json", dict(script_sha256=base.sha(Path(__file__)), files=[dict(file=p.name, bytes=p.stat().st_size, sha256=base.sha(p)) for p in sorted(OUT.iterdir()) if p.is_file() and p.name != "COMPACT_RECEIPT.json"]))
    print(json.dumps({"files": len(list(OUT.iterdir())), "bytes": sum(p.stat().st_size for p in OUT.iterdir())}))

if __name__ == "__main__":
    main()
