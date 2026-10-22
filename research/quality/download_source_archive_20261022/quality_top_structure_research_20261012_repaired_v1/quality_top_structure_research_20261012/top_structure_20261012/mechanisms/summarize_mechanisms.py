#!/usr/bin/env python3
"""Generate Chinese audit tables and scientific figures from fixed results."""
from __future__ import annotations
import csv
import json
import math
from pathlib import Path
import sys
import argparse
import numpy as np
from run_mechanisms import csvwrite, dump, sha


def readcsv(path):
    return list(csv.DictReader(path.open(encoding="utf-8-sig")))


def num(r, k):
    return float(r[k]) if r.get(k) not in ("", None, "None") else None


def fmt(x, n=5):
    return "不可算" if x is None else f"{x:.{n}g}"


def table(rows, columns):
    out = ["| " + " | ".join(label for _, label in columns) + " |", "|" + "|".join("---" for _ in columns) + "|"]
    for r in rows:
        out.append("| " + " | ".join(str(r.get(k, "")) for k, _ in columns) + " |")
    return "\n".join(out)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", type=Path, default=Path.cwd())
    ap.add_argument("--results", type=Path, default=Path(__file__).resolve().parent / "results")
    args = ap.parse_args()
    root, out = args.root.resolve(), args.results.resolve()
    work = out.parent
    records = readcsv(out / "synthetic_components.csv")
    centered = {r["case_id"]: r for r in readcsv(out / "synthetic_centered_components.csv")}
    real = readcsv(out / "real_39_height_components.csv")
    realc = {r["case_id"]: r for r in readcsv(out / "real_39_centered_components.csv")}
    cases = json.loads((out / "synthetic_design.json").read_text())["cases"]
    meanings = {
        "uniform_height_repeated_subset": "恒定墙高偏差被Hmean/Hlocal捕捉；F近零。相同相对墙高误差的St及旧Q随水平尺度变化。",
        "equal_mean_different_local_profile": "全局均高准确不保证顶界准确；Hmean约零，Hlocal/Hcenter/F/St仍响应，且响应随起伏形状和幅度变化。",
        "perfect_nonflat_reference_applicability": "作答等于构造非平顶参考时H和St为零，但绝对自身F仍扣分。此例检验评价对象，不批准任何真实替代GT。",
        "localized_spike": "相同峰高、不同支持周长得到不同平均损失；Hmean/Hlocal/F/St均会受局部支持影响。没有为构造峰指定等级。",
        "narrow_spike_quadrature_probe": "有限全周均匀采样可能漏掉或高估极窄峰；精确同底积分保留非零误差。St按顶弧采样仍响应但总扣分可能很小。",
        "cyclic_start_same_curve": "物理曲线不变，只改循环起点；精确矩和几何不变，有限数值积分可能有相位误差。",
        "collinear_same_curve": "在同一上下3D曲线上加点，周长积分与自身几何应保持；官方等角点均高代理可能受点数改变。",
        "top_bottom_compensation": "底y与top y共同影响重建墙高，能够补偿或放大；H为零不表示定位或范围正确。",
        "near_horizon_fixed_pixel": "固定底角1px改变时St仍约零，但底面和墙高可随近地平线条件大幅放大；删St不能修正这种效应。",
        "explicit_invalid_projection": "底角跨过地平线，固定相机/地板模型不再给正半径；保留不可算状态，未填零分。",
        "changed_footprint_matching": "底面范围改变后最近边不必是同一语义墙；Hlocal/Hcenter混入对应与周长权重改变，不能解释成纯顶面不平。",
        "nearest_wall_tie": "同一最近距离对应不同高度时max规则保持数组起点不敏感，但微小跨越Voronoi分界可能造成高度残差跳变。",
    }
    conclusion_rows = []
    for r in records:
        cid = r["case_id"]
        c = centered[cid]
        z = {"case_id": cid, "family": r["family"], "status": r["status"],
             **{k: num(r, k) for k in ["Hmean", "Hlocal", "Hstar", "flat", "S_top_deg", "S_bottom_deg", "Q_v11", "Q_no_topS"]},
             "Hcenter": num(c, "Hcenter"), "interpretation_zh": meanings[r["family"]],
             "limitation_zh": "合成构造；没有人工等级或人员误差分布；对比分数不是人工认可的目标分。"}
        if r["family"] == "localized_spike":
            z["interpretation_zh"] += f" 本例峰幅={r['amplitude_h']}h，支持周长比例={r['support_perimeter_fraction']}。"
        if r["family"] == "narrow_spike_quadrature_probe":
            z["interpretation_zh"] += f" Hlocal数值={fmt(num(r,'Hlocal'))}，精确={fmt(num(r,'exact_Hlocal_same_floor_constant_gt'))}。"
        conclusion_rows.append(z)
    csvwrite(out / "control_conclusions_71.csv", conclusion_rows)
    display = [{**r, **{k: fmt(r[k]) for k in ["Hmean", "Hlocal", "Hstar", "Hcenter", "flat", "S_top_deg", "Q_v11", "Q_no_topS"]}} for r in conclusion_rows]
    (work / "CONTROL_CONCLUSIONS_ZH.md").write_text("# 71项控制逐例结论\n\n70项几何可计算；1项越地平线保留不可算。表中全部为合成证据，不赋人工等级。\n\n" + table(display, [("case_id", "控制ID"), ("Hmean", "Hmean"), ("Hcenter", "Hcenter"), ("Hstar", "H*"), ("flat", "F/°"), ("S_top_deg", "St/°"), ("Q_v11", "旧Q"), ("Q_no_topS", "去St"), ("interpretation_zh", "结论与限制")]) + "\n", encoding="utf-8")

    # Expose already-existing exact extrema as diagnostics, not another penalty.
    profile_rows = []
    for kind, seq, cc in [("synthetic", records, centered), ("real_development", real, realc)]:
        for r in seq:
            if num(r, "annotation_height_mean_h") is None:
                continue
            mu, mg = num(r, "annotation_height_mean_h"), num(r, "reference_height_mean_h")
            lo, hi = num(r, "annotation_height_min_h"), num(r, "annotation_height_max_h")
            profile_rows.append({"case_id": r["case_id"], "cohort": kind,
                                 "annotation_wall_height_min_h": lo, "annotation_wall_height_max_h": hi,
                                 "annotation_wall_height_mean_h": mu, "reference_wall_height_mean_h": mg,
                                 "height_range_over_gt_mean": (hi-lo)/mg,
                                 "height_max_deviation_from_own_mean_over_gt_mean": max(abs(lo-mu), abs(hi-mu))/mg,
                                 "height_std_over_gt_mean": num(r, "annotation_height_std_over_gt_mean"),
                                 "Hcenter": num(cc[r["case_id"]], "Hcenter"),
                                 "new_score_penalty_applied": False})
    csvwrite(out / "height_profile_diagnostics.csv", profile_rows)
    rprobe = readcsv(out / "real_selected_numerical_probes.csv")
    sample_summary = []
    for component, base, high in [("Hlocal", 4096, 32768), ("F", 512, 32768), ("S_top", 2048, 8192)]:
        for cid in dict.fromkeys(r["case_id"] for r in rprobe):
            values = {int(r["sample_count"]): float(r["value"]) for r in rprobe if r["case_id"] == cid and r["component"] == component}
            sample_summary.append({"case_id": cid, "component": component, "default_n": base, "higher_n": high,
                                   "default_value": values[base], "higher_n_value": values[high],
                                   "absolute_change": abs(values[high]-values[base])})
    csvwrite(out / "real_sampling_change_summary.csv", sample_summary)
    summary = {
        "control_count": len(records), "valid_controls": sum(r["status"] == "available" for r in records),
        "real_count": len(real), "real_unique_images": len(set(r["image_id"] for r in real)),
        "real_unique_references": len(set(r["reference_object_id"] for r in real)),
        "real_Hstar_recompute_max_error": max(num(r, "frozen_Hstar_error") for r in real),
        "real_Hmean_guard_dominant_cases": [r["case_id"] for r in real if num(r,"Hmean") > num(r,"Hlocal")],
        "real_max_reference_relative_height_std": max(num(r,"reference_height_std_over_gt_mean") for r in real),
        "real_sampling_max_absolute_changes": {c: max(r["absolute_change"] for r in sample_summary if r["component"] == c) for c in ["Hlocal", "F", "S_top"]},
        "real_nonzero_distinct_height_tie_cases": [r["case_id"] for r in real if num(r,"AG_distinct_tied_height_fraction") > 0 or num(r,"GA_distinct_tied_height_fraction") > 0],
        "no_new_score_or_grade_recommendation_from_controls_alone": True,
    }
    dump(out / "mechanism_summary.json", summary)

    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    figs = work / "figures"
    figs.mkdir(exist_ok=True)
    spike_rows = sorted([r for r in records if r["family"] in {"localized_spike", "narrow_spike_quadrature_probe"} and num(r,"amplitude_h") == 1.44 and r["case_id"] != "spike_narrow_sample_aligned"], key=lambda r: num(r,"support_perimeter_fraction"))
    x = [num(r,"support_perimeter_fraction") for r in spike_rows]
    fig, axs = plt.subplots(1, 3, figsize=(14, 4.3), constrained_layout=True)
    axs[0].plot(x, [num(r,"Hlocal") for r in spike_rows], "o-", label="Hlocal: fixed 4096 samples")
    axs[0].plot(x, [num(r,"exact_Hlocal_same_floor_constant_gt") for r in spike_rows], "s--", label="exact same-floor integral")
    axs[0].set_ylabel("relative height RMS")
    axs[1].plot(x, [num(r,"flat") for r in spike_rows], "o-", label="F: 512 floor samples")
    axs[1].plot(x, [num(r,"S_top_deg") for r in spike_rows], "s--", label="St: 2048 spherical samples")
    axs[1].set_ylabel("degrees; different measured quantities")
    axs[2].plot(x, [num(r,"Q_v11") for r in spike_rows], "o-", label="v1.1")
    axs[2].plot(x, [num(r,"Q_no_topS") for r in spike_rows], "s--", label="no top S")
    axs[2].set_ylabel("score")
    axs[2].set_ylim(70, 101)
    for ax in axs:
        ax.set_xscale("log")
        ax.set_xlabel("fraction of floor perimeter supporting triangular spike")
        ax.grid(alpha=.25)
        ax.legend(fontsize=8)
    fig.suptitle("Synthetic spike amplitude 1.44 h: footprint and all other heights exact; no human severity assigned", fontsize=11)
    fig.savefig(figs / "localized_spike_support.png", dpi=180)
    plt.close(fig)

    rr = sorted([r for r in records if r["family"] == "near_horizon_fixed_pixel" and num(r,"bottom_delta_px") == -1], key=lambda r:num(r,"horizontal_scale"))
    fig, axs = plt.subplots(1, 3, figsize=(13.6, 4.3), constrained_layout=True)
    x = [num(r,"reference_bottom_horizon_margin_px") for r in rr]
    axs[0].plot(x, [num(r,"Hstar") for r in rr], "o-", label="Hstar")
    axs[0].set_ylabel("relative reconstructed height error")
    axs[1].plot(x, [num(r,"flat") for r in rr], "o-", label="F")
    axs[1].plot(x, [num(r,"S_top_deg") for r in rr], "s--", label="St")
    axs[1].set_ylabel("degrees; different measured quantities")
    axs[2].plot(x, [num(r,"Q_no_topS") for r in rr], "o-", label="v1.1 = no top S")
    axs[2].set_ylabel("score")
    axs[2].set_ylim(0, 102)
    for ax in axs:
        ax.set_xscale("log")
        ax.invert_xaxis()
        ax.set_xlabel("reference far-corner margin below horizon (px)")
        ax.grid(alpha=.25)
        ax.legend(fontsize=8)
    fig.suptitle("One bottom corner moved 1 px toward horizon; every top pixel fixed (synthetic)", fontsize=11)
    fig.savefig(figs / "fixed_pixel_near_horizon.png", dpi=180)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(7.1, 5.1), constrained_layout=True)
    xs, ys = [num(r,"Hmean") for r in real], [num(realc[r['case_id']],"Hcenter") for r in real]
    scatter = ax.scatter(xs, ys, c=[num(r,"flat") for r in real], cmap="viridis", s=42, edgecolors="white", linewidths=.4)
    fig.colorbar(scatter, ax=ax, shrink=.8, label="F: intrinsic angular flatness (degrees)")
    for r in real:
        if r["case_id"] in {"T20", "T19", "S071", "S107", "S034", "T09", "T22"}:
            offset = (-25, 8) if r["case_id"] == "S071" else (5, 4)
            ax.annotate(r["case_id"], (num(r,"Hmean"), num(realc[r['case_id']],"Hcenter")), xytext=offset, textcoords="offset points", fontsize=9)
    ax.set_xlabel("Hmean: global wall-height mean bias / GT mean")
    ax.set_ylabel("Hcenter: centered nearest-floor residual / GT mean")
    ax.set_title("39 conditional development records; no fitted decision boundary", fontsize=11)
    ax.set_xlim(-.015, .385)
    ax.set_ylim(-.01, .27)
    ax.grid(alpha=.22)
    fig.savefig(figs / "real_global_vs_centered_height.png", dpi=180)
    plt.close(fig)
    dump(figs / "manifest.json", {"figures": [{"path": str(p.relative_to(work)), "sha256": sha(p)} for p in sorted(figs.glob("*.png"))],
                                 "human_grades_assigned_to_synthetic_controls": False})
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
