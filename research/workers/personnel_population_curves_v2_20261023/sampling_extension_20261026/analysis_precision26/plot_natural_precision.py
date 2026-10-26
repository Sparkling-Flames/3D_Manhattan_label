#!/usr/bin/env python3
"""Publication-ready natural curve/precision plots from completed saved tables."""
from pathlib import Path
import argparse, io, json, os
os.environ.setdefault("MPLCONFIGDIR", "/tmp/hohonet_precision26_matplotlib")
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import font_manager
from precision_core import write_bytes, save_csv, save_json

COLORS = {"old48": "#66717e", "stage1_104": "#247ba0", "stage2_104": "#7a5195",
          "new208": "#247ba0", "pooled152": "#719b83", "pooled256": "#28784b"}
LABELS = {"old48": "旧48条", "stage1_104": "独立新104条", "stage2_104": "独立B104条",
          "new208": "独立新208条", "pooled152": "合并152条", "pooled256": "合并256条"}
METRIC_LABELS = {"Q_mean": "可评分Q均值", "Q_p10": "逐图P10的均值", "Q_sd_ddof1": "逐图Q标准差的均值",
                 "failure_rate": "非延期不可评分总率", "actual_consensus_failure_rate": "共识未形成率",
                 "output_unscoreable_rate": "输出不可评分率"}


def style(root):
    font = root / "assets/NotoSansCJKsc-Regular.otf"
    if font.exists():
        font_manager.fontManager.addfont(str(font))
        plt.rcParams["font.family"] = "Noto Sans CJK SC"
    plt.rcParams.update({"axes.unicode_minus": False, "font.size": 10, "axes.titlesize": 11,
                         "axes.labelsize": 10, "legend.fontsize": 9, "figure.dpi": 120,
                         "savefig.dpi": 180, "pdf.fonttype": 42, "svg.fonttype": "path",
                         "axes.spines.top": False, "axes.spines.right": False,
                         "axes.grid": True, "grid.alpha": .18})


def export(fig, folder, stem):
    paths = []
    for suffix in ["png", "pdf"]:
        b = io.BytesIO(); fig.savefig(b, format=suffix, bbox_inches="tight", facecolor="white")
        p = folder / (stem + "." + suffix); write_bytes(p, b.getvalue()); paths.append(str(p))
    plt.close(fig)
    return paths


def continuous(g, max_k):
    return g.set_index("k").reindex(range(1, max_k + 1))


def main_curve(summary, out, cohorts, final):
    """One fixed image set across all legal k and compared cohorts per panel."""
    metrics = ["Q_mean", "Q_p10", "Q_sd_ddof1", "actual_consensus_failure_rate"]
    summary = summary[(summary.panel == "fixed_N_ge_30") & (summary.layer == "ordinary_manual") &
                      (summary.uncertainty == "paths_fixed_images") & (summary.weighting == "image_equal")]
    capacity_rows = summary[summary.difficulty.eq("全部") & summary.cohort.eq(final)]
    capacity_n = int(capacity_rows.capacity_images.iloc[0]) if len(capacity_rows) else None
    fig, axes = plt.subplots(3, 4, figsize=(15.2, 10.3), sharex=True)
    used = []
    for ri, diff in enumerate(["简单", "中等", "困难"]):
        for ci, metric in enumerate(metrics):
            ax = axes[ri, ci]
            title_n = ""; support_signature = None
            for cohort in cohorts:
                g = summary[(summary.difficulty == diff) & (summary.metric == metric) &
                            (summary.cohort == cohort)].sort_values("k")
                if g.empty:
                    continue
                assert all(g[c].nunique(dropna=False) == 1 for c in ["images", "buildings", "capacity_images", "excluded_pool_ids"])
                sig = tuple(g[c].iloc[0] for c in ["images", "buildings", "capacity_images"]) + (str(g.excluded_pool_ids.fillna("").iloc[0]),)
                assert support_signature is None or sig == support_signature, (diff, metric, cohort, "whole-curve support differs")
                support_signature = sig
                title_n = "固定" + str(int(g.images.iloc[0])) + "图/" + str(int(g.buildings.iloc[0])) + "楼；候选" + str(int(g.capacity_images.iloc[0])) + "图"
                used.append(g); d = continuous(g, 30); scale = 100 if "rate" in metric else 1
                ax.plot(d.index, d.estimate * scale, color=COLORS[cohort],
                        ls="--" if cohort == "old48" else "-", lw=1.6, label=LABELS[cohort])
                if 1 in d.index and np.isfinite(d.loc[1, "estimate"]):
                    ax.scatter([1], [d.loc[1, "estimate"] * scale], color=COLORS[cohort], s=15, zorder=4)
                if cohort == final:
                    ax.fill_between(d.index, d.pointwise_low * scale, d.pointwise_high * scale,
                                    color=COLORS[cohort], alpha=.13, linewidth=0)
            ax.set_title(diff + " · " + METRIC_LABELS[metric] + "\n" + title_n)
            ax.set_xlim(1, 30); ax.set_xticks([1, 3, 6, 10, 15, 20, 25, 30])
            if ri == 2:
                ax.set_xlabel("进入人数 k（2人按合同延期）")
            if ci == 0:
                ax.set_ylabel("Q分")
            if "rate" in metric:
                ax.set_ylabel("百分比")
    axes[0, 0].legend(loc="best")
    prefix = "N≥30 普通 Manual" + ("（" + str(capacity_n) + "张候选图）" if capacity_n is not None else "")
    fig.suptitle(prefix + "：完整人数曲线的独立追加检验", fontsize=16, y=.995)
    fig.text(.01, .008, "每个panel固定跨全部合法k及新旧版本的共同图片，图片等权；阴影为该固定图片集的整路径Monte Carlo逐点95%经验范围。\n"
             "逐k尽可能全图的结果及建筑层范围另表保留。Q/P10/SD只对可评分团队计算；失败用全部实际尝试的合法候选图片，输出不可评分另列。", fontsize=9, va="bottom")
    fig.tight_layout(rect=[0, .075, 1, .965])
    paths = export(fig, out, "F01_固定157全曲线_独立追加")
    save_csv(pd.concat(used, ignore_index=True), out / "F01_SOURCE_ROWS.csv")
    return paths


def precision_plot(reach, out, cohorts):
    fig, axes = plt.subplots(1, 3, figsize=(14.5, 4.3), sharex=True, sharey=True)
    used = []
    columns = [("mean_mcse_estimable_images", "mean_mcse_gt1_images", "单图均值 MCSE≤1分"),
               ("P10_boot_estimable_images", "P10_boot_halfwidth_gt2_images", "单图P10经验区间半宽≤2分"),
               ("P10_rank_estimable_images", "P10_rank_halfwidth_gt2_images", "单图P10秩区间半宽≤2分")]
    for ax, (valid, bad, title) in zip(axes, columns):
        for cohort in cohorts:
            g = reach[(reach.panel == "fixed_N_ge_30") & (reach.layer == "ordinary_manual") &
                      (reach.difficulty == "全部") & (reach.cohort == cohort)].sort_values("k")
            if g.empty:
                continue
            used.append(g); d = continuous(g, 30)
            y = 100 * (d[valid] - d[bad]) / d.images
            y.loc[2] = np.nan
            ax.plot(d.index, y, color=COLORS[cohort], ls="--" if cohort == "old48" else "-", lw=1.8, label=LABELS[cohort])
            if 1 in y.index and np.isfinite(y.loc[1]):
                ax.scatter([1], [y.loc[1]], color=COLORS[cohort], s=15, zorder=4)
        ax.set_title(title); ax.set_xlabel("进入人数 k"); ax.set_xlim(1, 30); ax.set_ylim(-2, 102)
        ax.set_xticks([1, 3, 6, 10, 15, 20, 25, 30])
    axes[0].set_ylabel("达到工作精度尺的图片占比（%）"); axes[0].legend(loc="lower right")
    fig.suptitle("固定157张图：增加完整路径后，单图精度改善了多少？", fontsize=15, y=.995)
    fig.text(.01, .008, "未能估计相应精度的图片仍保留在图片分母中；1分/2分是项目工作精度尺。经验bootstrap与逆CDF秩区间不是同一种保证。\n"
             "原48保存区间及其计数单独保留；本图所有经验区间使用本轮统一2000次整路径重抽。精确边际未混入纯路径对照。", fontsize=9, va="bottom")
    fig.tight_layout(rect=[0, .17, 1, .935])
    paths = export(fig, out, "F02_单图精度随人数")
    save_csv(pd.concat(used).drop_duplicates(), out / "F02_SOURCE_ROWS.csv")
    return paths


def later_and_doorway(summary, out, cohorts, final):
    fig, axes = plt.subplots(2, 4, figsize=(15.2, 6.8))
    metrics = ["Q_mean", "Q_p10", "Q_sd_ddof1", "actual_consensus_failure_rate"]
    used = []
    settings = [("ordinary_manual", "全部", "fixed_N_ge_35", 35, "固定 N≥35 普通Manual"),
                ("doorway_manual", "单列", "fixed_N_ge_27", 27, "门洞：共同容量 k≤27")]
    for ri, (layer, diff, panel, last, title) in enumerate(settings):
        for ci, metric in enumerate(metrics):
            ax = axes[ri, ci]
            title_n = ""
            for cohort in cohorts:
                g = summary[(summary.panel == panel) & (summary.layer == layer) & (summary.difficulty == diff) &
                            (summary.metric == metric) & (summary.weighting == "image_equal") & (summary.cohort == cohort) &
                            (summary.uncertainty == "paths_fixed_images") &
                            summary.k.le(last)].sort_values("k")
                if g.empty:
                    continue
                used.append(g); d = continuous(g, last); scale = 100 if "rate" in metric else 1
                ax.plot(d.index, d.estimate * scale, color=COLORS[cohort], ls="--" if cohort == "old48" else "-", lw=1.6, label=LABELS[cohort])
                if 1 in d.index and np.isfinite(d.loc[1, "estimate"]):
                    ax.scatter([1], [d.loc[1, "estimate"] * scale], color=COLORS[cohort], s=15, zorder=4)
                if cohort == final:
                    ax.fill_between(d.index, d.pointwise_low * scale, d.pointwise_high * scale, color=COLORS[cohort], alpha=.12, linewidth=0)
                    title_n = "候选" + str(int(g.capacity_images.iloc[0])) + "图；全程固定" + str(int(g.images.iloc[0])) + "图/" + str(int(g.buildings.iloc[0])) + "楼"
            ax.set_title(title + "\n" + METRIC_LABELS[metric] + "\n" + title_n); ax.set_xlabel("进入人数 k")
            ax.set_xlim(1, last)
            if "rate" in metric:
                ax.set_ylabel("百分比")
    axes[0, 0].legend()
    fig.suptitle("35人端与门洞：保留固定人员池，单列资格与失败", fontsize=15, y=.995)
    fig.text(.01, .008, "每条质量曲线固定全程共同可评图片；失败曲线保留全部合法尝试图片。每k尽可能使用全部可评图片的结果另表保留。\n"
             "满员由同一成员集合重复得到，换组波动归零不表示准确；实际满员不可评分时Q仍缺失。", fontsize=9, va="bottom")
    fig.tight_layout(rect=[0, .105, 1, .95])
    paths = export(fig, out, "F03_35人与门洞曲线")
    save_csv(pd.concat(used, ignore_index=True), out / "F03_SOURCE_ROWS.csv")
    return paths


def complete_curve_band_plot(bands, out, cohorts):
    h = bands[(bands.layer == "ordinary_manual") & bands.pool_n.ge(30)]
    fig, axes = plt.subplots(2, 2, figsize=(11.8, 8.2))
    used = []
    scopes = [("all_random_prefix_k", "纯路径：所有合法可估k"),
              ("nonexact_display_k", "排除已有精确边际后的其余k")]
    for ri, (scope, title) in enumerate(scopes):
        for ci, metric in enumerate(["Q_mean", "Q_p10"]):
            ax = axes[ri, ci]; vals = []; labs = []; present = []
            for cohort in cohorts:
                d = h[(h.cohort == cohort) & (h.metric == metric) & (h.band_scope == scope)]
                if d.empty:
                    continue
                valid = d.max_abs_95.dropna()
                used.append(d); vals.append(valid.to_numpy())
                labs.append(LABELS[cohort] + "\n可估" + str(len(valid)) + "图"); present.append(cohort)
            bp = ax.boxplot(vals, tick_labels=labs, patch_artist=True, showfliers=False)
            for patch, cohort in zip(bp["boxes"], present):
                patch.set_facecolor(COLORS[cohort]); patch.set_alpha(.7)
            ax.set_title(("Q均值" if metric == "Q_mean" else "P10") + " · " + title)
            ax.set_ylabel("95%最大偏差经验带半宽（Q分）")
    fig.suptitle("单点精度与整曲线同时精度分开判断", fontsize=15, y=.995)
    fig.text(.02, .008, "候选为固定N≥30的157图；每图重抽完整路径，按固定可估k的最大绝对偏差构造带。上排包含全部合法可估k，\n"
             "下排另排除已具备完整有限目录的点；没有把精确值混入纯路径估计。箱图描述图片间宽度分布，逐图覆盖k与完整重抽数另表保存。\n"
             "这类经验带仍受未观察到的低分模式影响；它与单点区间、分布无关秩区间的含义不同。", fontsize=9, va="bottom")
    fig.tight_layout(rect=[0, .12, 1, .95])
    paths = export(fig, out, "F04_单图整曲线经验带")
    save_csv(pd.concat(used, ignore_index=True), out / "F04_SOURCE_ROWS.csv")
    return paths


def select_case_candidates(comparisons, out):
    z = comparisons[(comparisons.newer_cohort == "new208") & (comparisons.older_cohort == "old48") &
                    (comparisons.layer == "ordinary_manual") & comparisons.pool_n.ge(30) & comparisons.k.between(3, 20)].copy()
    if z.empty:
        return None
    z["abs_P10_revision"] = z.Q_p10_difference.abs()
    z["abs_mean_revision"] = z.Q_mean_difference.abs()
    first = z.sort_values("abs_P10_revision", ascending=False).head(1).copy()
    first["case_selection_rule"] = "exploratory largest absolute independent P10 revision among ordinary N>=30,k=3..20"
    second = z[~z.pool_id.isin(first.pool_id)].sort_values("abs_mean_revision", ascending=False).head(1).copy()
    second["case_selection_rule"] = "exploratory largest absolute independent mean revision among remaining pools"
    choices = pd.concat([first, second], ignore_index=True)
    save_csv(choices, out / "LOW_K_CASE_CANDIDATES.csv")
    return choices


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--root", type=Path, required=True)
    ap.add_argument("--stage", type=int, choices=[1, 2], default=2)
    ap.add_argument("--allow-partial", action="store_true")
    args = ap.parse_args(); root = args.root.resolve()
    r = root / "analysis_precision26" / ("results_stage" + str(args.stage))
    receipt = json.loads((r / "ANALYSIS_RECEIPT.json").read_text())
    if not args.allow_partial and not receipt["complete_requested_pool_support"]:
        raise RuntimeError("Refusing population figures before all frozen eligible pool inputs are complete")
    out = root / "analysis_precision26" / ("figures_stage" + str(args.stage)); out.mkdir(parents=True, exist_ok=True)
    style(root)
    reach = pd.read_csv(r / "PRECISION_REACH_BY_LAYER_K.csv.gz")
    bands = pd.read_csv(r / "NATURAL_CURVE_BAND_SUMMARY.csv.gz")
    full_band = pd.read_csv(r / "FIXED_IMAGE_AGGREGATE_CURVE_BANDS.csv.gz")
    cohorts = ["old48", "new208", "pooled256"] if args.stage == 2 else ["old48", "stage1_104", "pooled152"]
    paths = main_curve(full_band, out, cohorts, cohorts[-1])
    paths += precision_plot(reach, out, cohorts)
    paths += later_and_doorway(full_band, out, cohorts, cohorts[-1])
    paths += complete_curve_band_plot(bands, out, cohorts)
    comp = r / "PER_IMAGE_OLD_NEW_COMPARISONS.csv.gz"
    if comp.exists():
        select_case_candidates(pd.read_csv(comp), out)
    save_json(dict(stage=args.stage, source_analysis_receipt=str(r / "ANALYSIS_RECEIPT.json"),
                   support_complete=receipt["complete_requested_pool_support"], files=paths,
                   exact_anchors_in_pure_path_figures=False), out / "FIGURE_RECEIPT.json")


if __name__ == "__main__":
    main()
