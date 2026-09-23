"""从先行数值表生成可重跑的质心诊断，不作视觉裁决或人员能力推断。"""
import argparse
from pathlib import Path
import tempfile

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


DEFAULT = Path(__file__).resolve().parents[3] / "analysis_results/consensus_research_20260923"
GROUPS = ["mode", "gt_version", "condition"]
METRICS = {
    "abs_dy_px": ("dy_px", True), "abs_erp_dx_px": ("erp_dx_px", True),
    "erp_distance_px": ("erp_distance_px", False),
    "abs_circular_dx_px": ("circular_dx_px", True),
    "circular_R": ("circular_R", False), "gt_circular_R": ("gt_circular_R", False),
    "iou": ("iou", False),
}


def summarize(frame):
    required = set(GROUPS + ["status"] + [value[0] for value in METRICS.values()])
    missing = sorted(required - set(frame.columns))
    if missing:
        raise ValueError("missing_columns:" + ",".join(missing))
    if frame[GROUPS + ["status"]].isna().any().any():
        raise ValueError("missing_group_or_status")
    frame = frame.copy()
    for metric, (source, absolute) in METRICS.items():
        values = pd.to_numeric(frame[source], errors="raise")
        if np.isinf(values).any():
            raise ValueError("infinite_metric:" + source)
        frame[metric] = values.abs() if absolute else values
    rows = []
    for key, group in frame.groupby(GROUPS, sort=True):
        ok = group[group.status == "ok"]
        for metric in METRICS:
            values = ok[metric].dropna()
            rows.append(dict(zip(GROUPS, key), metric=metric, total_rows=len(group),
                             ok_rows=len(ok), unavailable_rows=len(group)-len(ok),
                             n=len(values), median=values.median(), p90=values.quantile(.9),
                             p95=values.quantile(.95)))
    return frame, pd.DataFrame(rows, columns=GROUPS + ["metric", "total_rows", "ok_rows",
                                                    "unavailable_rows", "n", "median", "p90", "p95"])


def gt_sensitivity(frame):
    """仅同一作答两个可评价GT版本配对；差值均为修订减原始。"""
    keys = ["canonical_annotation_id", "condition", "mode"]
    required = keys + ["image_id", "manual_gt_changed", "status", "gt_version", "iou", "dy_px"]
    missing = sorted(set(required) - set(frame.columns))
    if missing:
        raise ValueError("missing_GT_sensitivity_columns:" + ",".join(missing))
    changed = frame.manual_gt_changed.astype(str).str.lower()
    if not changed.isin(["true", "false", "1", "0"]).all():
        raise ValueError("invalid_manual_gt_changed")
    eligible = frame[(frame.status == "ok") & changed.isin(["true", "1"])]
    columns = keys + ["image_id", "iou", "dy_px"]
    original = eligible.loc[eligible.gt_version == "gt_original", columns]
    revised = eligible.loc[eligible.gt_version == "gt_revised", columns]
    paired = original.merge(revised, on=keys, suffixes=("_original", "_revised"), validate="one_to_one")
    if (paired.image_id_original != paired.image_id_revised).any():
        raise ValueError("paired_annotation_image_mismatch")
    paired["iou_delta"] = paired.iou_revised - paired.iou_original
    paired["iou_abs_delta"] = paired.iou_delta.abs()
    paired["abs_dy_delta_px"] = paired.dy_px_revised.abs() - paired.dy_px_original.abs()
    paired["abs_dy_abs_delta_px"] = paired.abs_dy_delta_px.abs()
    metrics = ["iou_delta", "iou_abs_delta", "abs_dy_delta_px", "abs_dy_abs_delta_px"]
    fields = ["condition", "mode", "affected_images", "paired_responses"]
    fields += [f"{metric}_{quantile}" for metric in metrics for quantile in ("median", "p95")]
    rows = []
    for (condition, mode), group in paired.groupby(["condition", "mode"], sort=True):
        row = dict(condition=condition, mode=mode, affected_images=group.image_id_original.nunique(),
                   paired_responses=len(group))
        for metric in metrics:
            if group[metric].isna().any():
                raise ValueError("missing_evaluable_GT_pair_metric:" + metric)
            row[metric + "_median"] = group[metric].median()
            row[metric + "_p95"] = group[metric].quantile(.95)
        rows.append(row)
    return pd.DataFrame(rows, columns=fields)


def write_outputs(frame, out):
    frame, summary = summarize(frame)
    sensitivity = gt_sensitivity(frame)
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    summary.to_csv(out / "centroid_summary.csv", index=False, encoding="utf-8-sig")
    sensitivity.to_csv(out / "gt_sensitivity_summary.csv", index=False, encoding="utf-8-sig")
    target = frame[(frame["mode"] == "curve") & (frame.gt_version == "gt_revised")]
    ok = target[target.status == "ok"]
    fig, axes = plt.subplots(2, 2, figsize=(11, 8))
    panels = [(axes[0, 0], "abs_dy_px", "Absolute vertical centroid difference (px)"),
              (axes[0, 1], "abs_circular_dx_px", "Absolute circular direction difference (px)"),
              (axes[1, 0], "iou", "Region IoU")]
    for condition, group in ok.groupby("condition", sort=True):
        for ax, metric, label in panels:
            vals = np.sort(group[metric].dropna().to_numpy())
            if len(vals):
                ax.step(vals, np.arange(1, len(vals)+1) / len(vals), where="post",
                        label=f"{condition} (n={len(vals)})")
        valid = group[["circular_R", "gt_circular_R", "abs_circular_dx_px"]].dropna()
        axes[1, 1].scatter(valid[["circular_R", "gt_circular_R"]].min(axis=1),
                           valid.abs_circular_dx_px, s=9, alpha=.35, label=str(condition))
    for ax, _, label in panels:
        ax.set(xlabel=label, ylabel="Empirical cumulative fraction", ylim=(0, 1.02))
    axes[1, 1].set(xlabel="min(annotation R, GT R)",
                   ylabel="Absolute circular direction difference (px)", xlim=(0, 1))
    for ax in axes.flat:
        ax.grid(alpha=.2)
        if ax.get_legend_handles_labels()[0]:
            ax.legend(fontsize=8)
    fig.suptitle(f"Curve / revised GT: {len(ok)} evaluable of {len(target)} rows\n"
                 "Conditional descriptive diagnostics; pixels on 1024 x 512 ERP")
    fig.tight_layout()
    fig.savefig(out / "centroid_diagnostics.png", dpi=170)
    plt.close(fig)
    lines = ["# 质心偏移先行诊断", "",
             "来源：individual_quality.csv。按区域构造、GT版本、条件分别汇总，"
             "仅 status=ok 的行参与指标分布；不跨条件混算。", "",
             "所有位移以原始1024×512图像像素计。CSV中的n为该指标非缺失作答行数，"
             "另列total_rows、ok_rows与unavailable_rows，不能把成功条件分布推广到全部作答。", "",
             "CSV报告绝对垂直偏移、绝对ERP水平偏移、ERP欧氏距离、绝对圆周水平偏移、"
             "人员区域R、GT区域R和IoU的中位数、第90及第95百分位。", "",
             "## 曲线区域与修订GT", "",
             "| 条件 | 总作答行 | 可评价 | 绝对垂直偏移中位数 / P95 | 圆周水平偏移中位数 / P95 |",
             "|---|---:|---:|---:|---:|"]
    def stat(group, metric):
        vals = group.loc[group.status == "ok", metric].dropna()
        return f"{vals.median():.2f} / {vals.quantile(.95):.2f} px（n={len(vals)}）" if len(vals) else "不可评价"
    for condition, group in target.groupby("condition", sort=True):
        lines.append(f"| {condition} | {len(group)} | {(group.status == 'ok').sum()} | "
                     f"{stat(group, 'abs_dy_px')} | {stat(group, 'abs_circular_dx_px')} |")
    lines += ["", "## 人工修订GT敏感性", "",
              "仅manual_gt_changed=true、同canonical作答/条件/区域模式下，原始与修订GT均可评价的行配对。"
              "差值统一为修订减原始：IoU正值表示评价提高；绝对垂直质心偏移变化负值表示偏移减小。",
              "受影响图数仅指成功配对的图，不等同全部修订清单覆盖数。"
              "gt_sensitivity_summary.csv另列有符号差和绝对差的中位数/P95；不跨条件或模式累加作答数。", "",
              "| 条件 | 模式 | 配对图数 | 配对作答 | IoU差中位数 / P95 | 绝对垂直偏移变化中位数 / P95(px) |",
              "|---|---|---:|---:|---:|---:|"]
    for row in sensitivity.itertuples():
        lines.append(f"| {row.condition} | {row.mode} | {row.affected_images} | {row.paired_responses} | "
                     f"{row.iou_delta_median:.4f} / {row.iou_delta_p95:.4f} | "
                     f"{row.abs_dy_delta_px_median:.2f} / {row.abs_dy_delta_px_p95:.2f} |")
    lines += ["", "## 解释边界", "",
              "- 圆周集中程度R趋近0时，方向不稳定；该角度的像素换算不等于标注整体平移。"
              "本次不设置低R自动排除阈值，图中完整保留可定义值，同时展示双方R。",
              "- ERP水平质心和欧氏距离依赖接缝位置；圆周方向解决周期性，但不能解决低R退化。",
              "- 质心是区域整体位置诊断，不是局部形状指标；质心接近不能证明IoU高。",
              "- 这是作答层面的条件分布，不是调整图片难度后的人员能力、人员分类或置信区间。"
              "同人、同图及不同GT版本重复出现，不可将这些行当独立受试者。",
              "- 未额外按known_wrong或imputed_point删除行；该表用于清洗前诊断，"
              "既有排除标志与借点来源须在独立作答分析中另行控制。",
              "- 不可评价可能来自GT或二维表示失败，不可直接推断人员标错。", ""]
    (out / "centroid_findings.md").write_text("\n".join(lines), encoding="utf-8")
    return summary


def self_test():
    base = dict(mode="curve", gt_version="gt_revised", condition="manual", status="ok",
                canonical_annotation_id="a", image_id="image1", manual_gt_changed=True,
                dy_px=-2., erp_dx_px=-3., erp_distance_px=np.sqrt(13), circular_dx_px=-8.,
                circular_R=.01, gt_circular_R=.02, iou=.9)
    frame = pd.DataFrame([base, {**base, "canonical_annotation_id": "b", "dy_px": 4., "circular_dx_px": None},
                          {**base, "canonical_annotation_id": "c", "status": "not_evaluable", "dy_px": 999.}])
    with tempfile.TemporaryDirectory() as tmp:
        summary = write_outputs(frame, tmp).set_index("metric")
        assert summary.loc["abs_dy_px", "median"] == 3
        assert summary.loc["abs_dy_px", "ok_rows"] == 2
        assert summary.loc["abs_circular_dx_px", "n"] == 1
        assert summary.loc["abs_dy_px", "total_rows"] == 3
        assert (Path(tmp) / "centroid_diagnostics.png").stat().st_size > 1000
    paired = pd.DataFrame([base, {**base, "gt_version": "gt_original", "iou": .7, "dy_px": -5.},
                           {**base, "canonical_annotation_id": "not_paired"},
                           {**base, "canonical_annotation_id": "unchanged", "manual_gt_changed": False},
                           {**base, "canonical_annotation_id": "unchanged", "manual_gt_changed": False,
                            "gt_version": "gt_original"}])
    sensitivity = gt_sensitivity(paired).iloc[0]
    assert sensitivity.paired_responses == 1 and sensitivity.affected_images == 1
    assert np.isclose(sensitivity.iou_delta_median, .2)
    assert sensitivity.abs_dy_delta_px_median == -3
    assert sensitivity.abs_dy_abs_delta_px_median == 3
    print("synthetic centroid summary check passed")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=DEFAULT / "individual_quality.csv")
    parser.add_argument("--out", type=Path, default=DEFAULT)
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()
    if args.self_test:
        self_test()
    else:
        write_outputs(pd.read_csv(args.input), args.out)
