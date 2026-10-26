#!/usr/bin/env python3
"""Four individual full population curves from the completed saved experiment.

No fusion, bootstrap or sampling is run. Three previously fixed cases are
joined by one explicitly post-hoc illustration of the largest independent
old48/new208 mean revision at k=3..10 within the fixed ordinary N>=30 domain.
The final 194-pool marker is mandatory; partial completion cannot choose the
fourth case. Exact finite-population anchors remain different from MC draws.
"""
from pathlib import Path
import argparse
import json
import os
os.environ.setdefault("MPLCONFIGDIR", "/tmp/hohonet_precision26_matplotlib")
import numpy as np
import pandas as pd
from matplotlib.lines import Line2D
from plot_natural_precision import COLORS, LABELS, style, export, plt
from precision_core import save_csv, save_json


COHORTS = ["old48", "new208", "pooled256"]
FIXED_IMAGES = ["wc2JMjhGNzB-46", "VFuaQ6m2Qom-04", "rPc6DW4iMge-06"]
METRICS = [
    ("Q_mean", "Q_mean_boot_low", "Q_mean_boot_high", "Q均值", "整路径bootstrap逐点95%区间", "Q_mean_exact"),
    ("Q_p10", "P10_order_low", "P10_order_high", "样本 linear P10", "总体inverse-CDF分位数的逐点95%秩区间", "exact_inverted_cdf_p10"),
    ("actual_consensus_failure_rate", "actual_consensus_failure_CP_low", "actual_consensus_failure_CP_high",
     "实际共识未形成率", "逐点95%Clopper–Pearson区间；满员遮罩", "actual_consensus_failure_rate_exact"),
]


def select_cases(curve, comparisons):
    meta = curve[["pool_id", "image", "image_id", "building", "layer", "difficulty", "pool_n",
                  "reference_id", "reference_version"]].drop_duplicates("pool_id")
    assert len(meta) == 194
    capacity = meta[meta.layer.eq("ordinary_manual") & meta.pool_n.ge(30)]
    assert len(capacity) == 157, len(capacity)
    rows = []
    for order, image in enumerate(FIXED_IMAGES, 1):
        h = meta[meta.image.eq(image)]
        assert len(h) == 1, (image, len(h))
        r = h.iloc[0].to_dict()
        r.update(case_order=order, selection_type="previously_fixed_case",
                 selection_rule="three preselected finite-margin/original-image cases; not chosen by new mean revision",
                 selection_k=np.nan, independent_mean_revision=np.nan, absolute_independent_mean_revision=np.nan)
        rows.append(r)
    z = comparisons[comparisons.older_cohort.eq("old48") & comparisons.newer_cohort.eq("new208") &
                    comparisons.pool_id.isin(capacity.pool_id) & comparisons.k.between(3, 10) &
                    comparisons.Q_mean_difference.notna()].copy()
    assert not z.duplicated(["pool_id", "k"]).any()
    z["absolute_independent_mean_revision"] = z.Q_mean_difference.abs()
    z["already_fixed_case"] = z.image.isin(FIXED_IMAGES)
    z = z.sort_values(["absolute_independent_mean_revision", "pool_id", "k"],
                      ascending=[False, True, True], kind="stable")
    z["candidate_rank_all_image_k"] = range(1, len(z) + 1)
    selected = z[~z.already_fixed_case].iloc[0]
    r = meta[meta.pool_id.eq(selected.pool_id)].iloc[0].to_dict()
    r.update(case_order=4, selection_type="posthoc_display_only",
             selection_rule="largest |new208 meanQ-old48 meanQ| at any k=3..10 among ordinary N>=30, excluding three fixed cases; ties: pool_id then k",
             selection_k=int(selected.k), independent_mean_revision=float(selected.Q_mean_difference),
             absolute_independent_mean_revision=float(selected.absolute_independent_mean_revision))
    rows.append(r)
    keep = ["candidate_rank_all_image_k", "pool_id", "image", "building", "difficulty", "pool_n", "k",
            "Q_mean_old", "Q_mean_new", "Q_mean_difference", "absolute_independent_mean_revision", "already_fixed_case"]
    return pd.DataFrame(rows), z[keep]


def y_quality(ax, series):
    values = np.concatenate([np.asarray(x, dtype=float).ravel() for x in series])
    values = values[np.isfinite(values)]
    if not len(values):
        ax.set_ylim(0, 100)
        return
    lo, hi = max(0., float(values.min()) - 4), min(102., float(values.max()) + 4)
    if hi - lo < 20:
        centre = (hi + lo) / 2
        lo, hi = max(0., centre - 10), min(102., centre + 10)
    ax.set_ylim(lo, hi)


def render(curve, exact, cases, out):
    fig, axes = plt.subplots(len(cases), 3, figsize=(16.0, 14.0), squeeze=False)
    source = []
    exact_sources = []
    for ri, case in enumerate(cases.to_dict("records")):
        pid, n = case["pool_id"], int(case["pool_n"])
        h = curve[curve.pool_id.eq(pid) & curve.cohort.isin(COHORTS)].copy()
        e = exact[exact.pool_id.eq(pid) & exact.cohort.eq("pooled256") & exact.k.isin([1, n - 1, n])].copy()
        assert not e.duplicated("k").any(), pid
        assert set(e.k) == {1, n - 1, n}, (pid, sorted(e.k))
        for cohort in COHORTS:
            d = h[h.cohort.eq(cohort)]
            assert len(d) == n and set(d.k) == set(range(1, n + 1)), (pid, cohort)
        full = h[h.cohort.eq("pooled256") & h.k.eq(n)].iloc[0]
        qvalid = h[h.cohort.eq("pooled256") & h.k.ne(2)].quality_valid_paths
        q_support = f"Q有效路径 {int(qvalid.min())}–{int(qvalid.max())}/256；满员 {int(full.quality_valid_paths)}/256"
        label = "既定案例" if case["selection_type"] == "previously_fixed_case" else "事后展示：低人数均值修订最大"
        for ci, (metric, lo_col, hi_col, metric_label, interval_label, truth_col) in enumerate(METRICS):
            ax = axes[ri, ci]
            quality_values = []
            scale = 100. if metric.endswith("rate") else 1.
            for cohort in COHORTS:
                d = h[h.cohort.eq(cohort)].set_index("k").sort_index().reindex(range(1, n + 1))
                y = d[metric].copy()
                # k=2 is a design deferral, even where a rate source happens
                # to contain a numeric zero. No line is drawn across the gap.
                y.loc[2] = np.nan
                lo = d[lo_col].copy() if cohort == "pooled256" else pd.Series(np.nan, index=d.index)
                hi = d[hi_col].copy() if cohort == "pooled256" else pd.Series(np.nan, index=d.index)
                lo.loc[2] = hi.loc[2] = np.nan
                if metric == "actual_consensus_failure_rate":
                    # The full population has one known team; it is not a
                    # binomial experiment with 256 unknown repeated trials.
                    lo.loc[n] = hi.loc[n] = np.nan
                ax.plot(d.index, y * scale, color=COLORS[cohort],
                        ls="--" if cohort == "old48" else "-", lw=1.5,
                        marker="o" if cohort == "pooled256" else None,
                        markersize=2.6, label=LABELS[cohort], zorder=3)
                if cohort != "pooled256" and np.isfinite(y.loc[1]):
                    ax.scatter([1], [y.loc[1] * scale], color=COLORS[cohort], s=15, zorder=4)
                if cohort == "pooled256":
                    ax.fill_between(d.index.to_numpy(), lo.to_numpy(float) * scale,
                                    hi.to_numpy(float) * scale, color=COLORS[cohort],
                                    alpha=.17, linewidth=0, zorder=1)
                quality_values += [y.to_numpy(), lo.to_numpy(), hi.to_numpy()]
                for k, r in d.iterrows():
                    source.append(dict(
                        case_order=case["case_order"], pool_id=pid, image=case["image"], image_id=case["image_id"],
                        building=case["building"], difficulty=case["difficulty"], pool_n=n,
                        reference_id=case["reference_id"], reference_version=case["reference_version"],
                        cohort=cohort, k=int(k), metric=metric, estimate=y.loc[k],
                        plotted_interval_low=lo.loc[k], plotted_interval_high=hi.loc[k],
                        interval_definition=interval_label if cohort == "pooled256" else "none displayed",
                        paths_attempted=r.paths_attempted, quality_valid_paths=r.quality_valid_paths,
                        actual_executed_nondeferred_paths=r.actual_executed_nondeferred_paths,
                        actual_consensus_failure_paths=r.actual_consensus_failure_paths,
                        output_unscoreable_paths=r.output_unscoreable_paths,
                        unique_teams=r.unique_teams, policy_deferred_paths=r.policy_deferred_paths,
                        display_units="percent (source estimate remains a proportion)" if scale == 100 else "Q points",
                        point_estimator_definition="sample type7 linear P10; population target inverse CDF" if metric == "Q_p10" else metric,
                        full_failure_interval_masked=bool(metric == "actual_consensus_failure_rate" and k == n),
                    ))
            truth = e[truth_col]
            ax.scatter(e.k, truth * scale, color="black", marker="D" if metric == "Q_p10" else "o",
                       s=31 if metric == "Q_p10" else 25, linewidths=.7, zorder=6)
            quality_values.append(truth.to_numpy())
            if metric == "Q_p10":
                ax.scatter(e.k, e.exact_linear_p10, facecolors="white", edgecolors="black",
                           marker="o", s=57, linewidths=1.05, zorder=7)
                quality_values.append(e.exact_linear_p10.to_numpy())
            for r in e.to_dict("records"):
                exact_sources.append(dict(
                    case_order=case["case_order"], pool_id=pid, image=case["image"], k=r["k"], metric=metric,
                    exact_field=truth_col, exact_value=r[truth_col],
                    exact_catalogue_linear_P10=r["exact_linear_p10"] if metric == "Q_p10" else np.nan,
                    exact_population_inverseCDF_P10=r["exact_inverted_cdf_p10"] if metric == "Q_p10" else np.nan,
                    finite_population_teams=r["finite_population_teams_exact"], quality_valid_teams=r["quality_valid_teams"],
                    actual_executed_nondeferred_teams=r["actual_executed_nondeferred_teams"],
                    actual_consensus_failure_teams=r["actual_consensus_failure_teams"],
                    output_unscoreable_teams=r["output_unscoreable_teams"], anchor_type=r["anchor_type"],
                    anchor_semantics="uniform finite teams, quality conditional on scoreability; not repeated-path weights",
                ))
            ax.axvspan(1.65, 2.35, color="#d9d9d9", alpha=.45, linewidth=0, zorder=0)
            ax.set_xlim(.5, n + .7)
            ticks = sorted(set([1, 3, 6, 10, 15, 20, 25, 30, 35, n - 1, n]))
            # Do not crowd the last two labels if the fixed tick is adjacent.
            ticks = [k for k in ticks if 1 <= k <= n and (k <= n - 3 or k == n)]
            ax.set_xticks(ticks)
            ax.set_xlabel("进入人数 k（2人按合同延期）")
            if metric.endswith("rate"):
                vmax = max(0., float(h[metric].max()), float(e[truth_col].max()),
                           float(h.loc[h.cohort.eq("pooled256") & h.k.ne(n), hi_col].max())) * 100
                ax.set_ylim(-max(0.15, vmax * .03), min(104., max(4., vmax * 1.08)))
                ax.set_ylabel("百分比（%）")
            else:
                y_quality(ax, quality_values)
                ax.set_ylabel("Q分")
                if not np.isfinite(full.Q_mean):
                    ax.text(.985, .035, "满员Q不可评分：保持缺失", transform=ax.transAxes,
                            ha="right", va="bottom", fontsize=8, color="#8c3f32")
            title = case["image"] + f" · {case['difficulty']} · N={n}" if ci == 0 else metric_label
            if ci == 0:
                title += "\n" + label + "；Q均值"
            elif ci == 1:
                title += "\n阴影：总体inverse-CDF P10的秩区间"
            else:
                title += "\n阴影：实际尝试的CP区间（满员除外）"
            ax.set_title(title, fontsize=10.2)
            if ci == 0:
                ax.text(.01, .015, q_support, transform=ax.transAxes, ha="left", va="bottom", fontsize=7.6, color="#555555")
            if case["selection_type"] == "posthoc_display_only" and ci == 0:
                k = int(case["selection_k"])
                selected_y = h.loc[h.cohort.eq("new208") & h.k.eq(k), "Q_mean"].iloc[0]
                ax.annotate(f"k={k}，独立新−旧={case['independent_mean_revision']:+.2f}",
                            xy=(k, selected_y), xytext=(.40, .18), textcoords="axes fraction",
                            fontsize=8, color=COLORS["new208"],
                            arrowprops=dict(arrowstyle="->", color=COLORS["new208"], lw=.7))
    handles = [Line2D([0], [0], color=COLORS[c], ls="--" if c == "old48" else "-", lw=1.8, label=LABELS[c]) for c in COHORTS]
    handles += [
        Line2D([0], [0], color="black", ls="none", marker="o", markersize=5, label="精确有限均值／失败率"),
        Line2D([0], [0], color="black", ls="none", marker="D", markersize=5, label="精确总体 inverse-CDF P10"),
        Line2D([0], [0], color="black", ls="none", marker="o", markerfacecolor="white", markersize=6, label="历史完整目录 linear P10"),
    ]
    fig.suptitle("单张图片：从低人数到实际满员的完整曲线", fontsize=16, y=.994)
    fig.legend(handles=handles, ncol=3, loc="upper center", bbox_to_anchor=(.5, .975), frameon=False, fontsize=9)
    fig.text(.015, .012,
             "绿带仅表示合并256条的逐点区间，不是整曲线同时置信带；Q仅在可评分团队中计算。共识未形成率以实际非延期尝试为分母，\n"
             "输出已生成但不可评分另见SOURCE表，不混入这张失败率曲线。黑色精确锚点限k=1、N−1、N，目录内各团队等权；实际满员只有一队，\n"
             "其失败率是已知0或1，不由重复256次估计未知概率。P10绿线沿用样本linear估计器，秩带针对总体inverse-CDF分位数；空心圆是历史目录\n"
             "linear口径，两种精确P10定义并列且不互换。第四例在194池全部完成后按独立新旧均值修订选择，仅用于事后展示，不影响追加预算或种子。",
             fontsize=8.5, va="bottom")
    fig.tight_layout(rect=[0, .105, 1, .93], h_pad=2.0)
    outputs = export(fig, out, "N05_单图完整人数曲线")
    receipts = [save_csv(pd.DataFrame(source), out / "N05_CURVE_SOURCE.csv.gz"),
                save_csv(pd.DataFrame(exact_sources), out / "N05_EXACT_ANCHOR_SOURCE.csv")]
    return outputs, receipts


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", type=Path, required=True)
    args = ap.parse_args()
    root = args.root.resolve()
    src = root / "analysis_precision26/results_stage2"
    gate = json.loads((src / "NATURAL_FINALIZATION_COMPLETE.json").read_text())
    assert gate["complete"] and gate["pools"] == 194
    curve = pd.read_csv(src / "NATURAL_CURVES.csv.gz")
    comparisons = pd.read_csv(src / "PER_IMAGE_OLD_NEW_COMPARISONS.csv.gz")
    exact = pd.read_csv(src / "EXACT_ANCHOR_MC_ACCURACY.csv.gz")
    cases, candidates = select_cases(curve, comparisons)
    out = root / "analysis_precision26/figures_stage2"
    out.mkdir(parents=True, exist_ok=True)
    style(root)
    receipts = [save_csv(cases, out / "N05_CASE_SELECTION.csv"),
                save_csv(candidates, out / "N05_POSTHOC_CANDIDATE_RANKING.csv.gz")]
    plots, source_receipts = render(curve, exact, cases, out)
    save_json(dict(complete=True, final_pools=194, images=len(cases), new_fusion=False, new_resampling=False,
                   plots=plots, tables=receipts + source_receipts,
                   exact_anchor_k="1,N-1,N", source_tables=["NATURAL_CURVES.csv.gz", "PER_IMAGE_OLD_NEW_COMPARISONS.csv.gz",
                                                            "EXACT_ANCHOR_MC_ACCURACY.csv.gz"],
                   fullN_interval="masked; single known team shown as exact point",
                   fourth_case="posthoc display only, independent old48 versus new208 mean change"),
              out / "N05_RENDER_RECEIPT.json")


if __name__ == "__main__":
    main()
