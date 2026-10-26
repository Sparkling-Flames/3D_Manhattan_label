#!/usr/bin/env python3
"""Six fully enumerated small pools: real independent paths against all teams.

This is a predetermined complete finite domain, not a selection on new Q.
All legal k are kept; k=2 stays contract-deferred. It cannot substitute for the
large-N low-k study. Inputs are completed stage2 per-pool natural checkpoints.
"""
from pathlib import Path
import argparse, json, subprocess, sys, os
os.environ.setdefault("MPLCONFIGDIR", "/tmp/hohonet_precision26_matplotlib")
import numpy as np
import pandas as pd
from scipy.stats import binom
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from precision_core import save_csv, save_json, read_csv_exact_seeds
from plot_natural_precision import style, export, COLORS, LABELS

PRIOR = "research/workers/personnel_population_curves_v2_20261023/sampling_precision_20261025"


def narrow_interval_case(root, prior, out, curve, err):
    """Actual observed narrow interval counterexample; no new sample generation."""
    pid = "uNb9QFRL6hY-06__manual__97fff2cf49"; k = 1
    selected = err[err.pool_id.eq(pid) & err.k.eq(k) & err.cohort.eq("pooled256")]
    if selected.empty:
        return []
    reference = selected.iloc[0]
    x = pd.read_csv(prior / "new_endpoints/EXACT_MARGINAL_VALUES.csv.gz", low_memory=False)
    x = x[x.pool_id.eq(pid) & x.k.eq(k)].sort_values("B8L2")
    truth = float(reference.exact_inverted_cdf_p10)
    old = pd.read_csv(root / "analysis_precision26/prior_pool_cache" / (pid + ".csv.gz"), low_memory=False)
    old = old[old.k.eq(k) & old.stratum.isin(["old24", "prior_new24"])]
    chunks = [old]
    for stage, stratum in [(1, "new104A"), (2, "new104B")]:
        d = pd.read_csv(root / "new_endpoints26" / ("stage" + str(stage)) / "prefix_values" / (pid + ".csv.gz"), low_memory=False)
        d = d[d.policy.eq("natural_random") & d.k.eq(k)].copy(); d["stratum"] = stratum; chunks.append(d)
    d = pd.concat(chunks, ignore_index=True)
    assert d.path_id.nunique() == 256 and d.B8L2.notna().all()
    d = d[["pool_id", "path_id", "stratum", "team_key", "k", "B8L2", "reference_id"]].copy()
    d["member_workers"] = d.team_key.map(x.set_index("team_key").member_workers)
    d["at_or_below_true_inverseCDF_P10"] = d.B8L2.le(truth + 1e-9)
    files = [save_csv(d, out / "NARROW_P10_CASE_EXACT_PATHS.csv.gz")]
    fields = [c for c in ["pool_id", "image", "image_id", "building", "k", "team_key", "member_workers",
                          "member_object_ids", "B8L2", "reference_id", "reference_version", "geometry_state_pointer"] if c in x]
    files.append(save_csv(x[fields], out / "NARROW_P10_CASE_FINITE_TEAMS.csv"))
    definitions = {"old48": ["old24", "prior_new24"], "stage1_104": ["new104A"], "stage2_104": ["new104B"],
                   "new208": ["new104A", "new104B"], "pooled256": ["old24", "prior_new24", "new104A", "new104B"]}
    freq = []
    for cohort, strata in definitions.items():
        g = d[d.stratum.isin(strata)]; row = curve[curve.pool_id.eq(pid) & curve.k.eq(k) & curve.cohort.eq(cohort)].iloc[0]
        erow = err[err.pool_id.eq(pid) & err.k.eq(k) & err.cohort.eq(cohort)].iloc[0]
        freq.append(dict(pool_id=pid, image="uNb9QFRL6hY-06", k=k, cohort=cohort, paths=len(g),
                         at_or_below_true_P10_paths=int(g.at_or_below_true_inverseCDF_P10.sum()),
                         observed_frequency=float(g.at_or_below_true_inverseCDF_P10.mean()),
                         exact_uniform_frequency=float(x.B8L2.le(truth + 1e-9).mean()),
                         sample_linear_P10=row.Q_p10, sample_inverseCDF_P10=row.Q_p10_inverse_cdf,
                         exact_catalogue_linear_P10=reference.exact_linear_p10, exact_population_inverseCDF_P10=truth,
                         sample_linear_minus_catalogue_linear=row.Q_p10 - reference.exact_linear_p10,
                         sample_linear_minus_population_inverseCDF=row.Q_p10 - truth,
                         expected_sample_linear_P10_given_valid_n=erow.expected_sample_linear_P10_given_actual_valid_n,
                         expected_sample_inverseCDF_P10_given_valid_n=erow.expected_sample_inverseCDF_P10_given_actual_valid_n,
                         empirical_boot95_low=row.Q_p10_boot_low, empirical_boot95_high=row.Q_p10_boot_high,
                         inverseCDF_order95_low=row.P10_order_low, inverseCDF_order95_high=row.P10_order_high))
    files.append(save_csv(pd.DataFrame(freq), out / "NARROW_P10_CASE_FREQUENCIES_AND_DEFINITIONS.csv"))
    probability = np.array([1.]); strata = []
    for name, g in d.groupby("stratum", sort=True):
        n = len(g); low = int(g.at_or_below_true_inverseCDF_P10.sum()); p = low / n
        probability = np.convolve(probability, binom.pmf(np.arange(n + 1), n, p))
        strata.append(dict(stratum=name, n=n, observed_low=low, empirical_probability=p))
    h = .1 * (len(d) - 1); lower_rank = int(np.floor(h)) + 1; upper_rank = int(np.ceil(h)) + 1
    save_json(dict(pool_id=pid, k=k, scope="conditional exact distribution of the already specified stratified bootstrap counts; no new paths or fusion",
                   strata=strata, linear_P10_lower_order_rank=lower_rank, linear_P10_upper_order_rank=upper_rank,
                   probability_low_count_reaches_lower_order=float(probability[lower_rank:].sum()),
                   probability_low_count_reaches_upper_order=float(probability[upper_rank:].sum()),
                   nominal_lower_tail=.025,
                   conclusion="Even the infinite-bootstrap limit places the lower percentile bound at the second-lowest score for this empirical distribution",
                   target_definitions_separate=True), out / "NARROW_P10_EXACT_BOOTSTRAP_COUNT_DISTRIBUTION.json")
    return files


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--root", type=Path, required=True)
    args = ap.parse_args(); root = args.root.resolve(); owner = root / "analysis_precision26"
    prior = root / "prior_recovered" / PRIOR
    exact = pd.read_csv(prior / "analysis_precision/new_results/EXACT_FINITE_MARGINAL_STATISTICS.csv")
    pids = sorted(exact.loc[exact.exact_kind.eq("all_small_pool_subsets"), "pool_id"].unique())
    assert len(pids) == 6, ("frozen complete-small-pool support changed", pids)
    out = owner / "small_exact_validation"; out.mkdir(parents=True, exist_ok=True)
    files = []
    for stem in ["curves", "intervals", "components", "status", "curve_band_summary", "path_strata"]:
        inputs = [owner / "results_stage2/pool_checkpoints" / (pid + "__" + stem + ".csv.gz") for pid in pids]
        assert all(p.exists() for p in inputs), [str(p) for p in inputs if not p.exists()]
        d = pd.concat([read_csv_exact_seeds(p) for p in inputs], ignore_index=True)
        files.append(save_csv(d, out / ("NATURAL_" + stem.upper() + ".csv.gz")))
    subprocess.run([sys.executable, str(owner / "exact_anchor_and_display.py"), "--root", str(root),
                    "--stage", "2", "--results-dir", str(out)], check=True)
    curve = pd.read_csv(out / "NATURAL_CURVES.csv.gz")
    err = pd.read_csv(out / "EXACT_ANCHOR_MC_ACCURACY.csv.gz")
    files += narrow_interval_case(root, prior, out, curve, err)
    error_metrics = ["Q_mean_error", "D10_mean_error", "Q_sd_error_to_uniform_population",
                     "linear_P10_distance_to_catalogue_linear", "linear_P10_distance_to_population_inverse_cdf",
                     "inverse_CDF_P10_error", "failure_rate_error", "actual_consensus_failure_rate_error"]
    per_pool = []
    for (pid, cohort), g0 in err.groupby(["pool_id", "cohort"], sort=False):
        for scope in ["all_scored_k", "interior_k3_to_Nminus2"]:
            g = g0[g0.k.between(3, g0.pool_n - 2)] if scope.startswith("interior") else g0
            for metric in error_metrics:
                x = g[metric].dropna()
                per_pool.append(dict(pool_id=pid, image=g0.image.iloc[0], building=g0.building.iloc[0],
                                     pool_n=int(g0.pool_n.iloc[0]), cohort=cohort, scope=scope, metric=metric,
                                     estimable_k=len(x), mean_signed_error=x.mean(), MAE=x.abs().mean(),
                                     max_absolute_error=x.abs().max(), k_abs_error_gt2=int(x.abs().gt(2).sum()),
                                     k_abs_error_gt5=int(x.abs().gt(5).sum())))
    pe = pd.DataFrame(per_pool); files.append(save_csv(pe, out / "SMALL_POOLS_ERROR_PER_POOL.csv"))
    summaries = []
    for (cohort, scope, metric), g in pe.groupby(["cohort", "scope", "metric"], sort=False):
        summaries.append(dict(cohort=cohort, scope=scope, metric=metric, pools=g.pool_id.nunique(),
                              buildings=g.building.nunique(), estimable_cells=int(g.estimable_k.sum()),
                              pool_equal_MAE=g.MAE.mean(), pool_equal_mean_signed_error=g.mean_signed_error.mean(),
                              largest_cell_error=g.max_absolute_error.max(),
                              descriptive_only="six complete small pools; no large-N extrapolation"))
    files.append(save_csv(pd.DataFrame(summaries), out / "SMALL_POOLS_ERROR_SUMMARY.csv"))
    # Interval containment and narrow empirical misses remain descriptive
    # finite-anchor counts, not an assertion of general 95% frequentist coverage.
    style(root)
    fig, axes = plt.subplots(6, 4, figsize=(15.8, 17.5))
    cohorts = ["old48", "new208", "pooled256"]
    metrics = ["Q_mean", "Q_p10", "Q_sd_ddof1", "P10_inverseCDF_error"]
    names = ["Q均值", "P10：两种定义分别显示", "团队Q波动 SD", "P10误差（对总体逆CDF）"]
    for ri, pid in enumerate(pids):
        cg = curve[curve.pool_id.eq(pid)]; n = int(cg.pool_n.iloc[0]); image = cg.image.iloc[0]
        truth = err[err.pool_id.eq(pid) & err.cohort.eq("pooled256")].set_index("k").reindex(range(1, n + 1))
        for ci, (metric, title) in enumerate(zip(metrics, names)):
            ax = axes[ri, ci]; scale = 100 if metric.endswith("rate") else 1
            for cohort in cohorts:
                d = cg[cg.cohort.eq(cohort)].set_index("k").reindex(range(1, n + 1))
                y = d.Q_p10 - truth.exact_inverted_cdf_p10 if metric == "P10_inverseCDF_error" else d[metric] * scale
                ax.plot(d.index, y, color=COLORS[cohort], lw=1.3,
                        ls="--" if cohort == "old48" else "-", marker=".", markersize=3, label=LABELS[cohort])
                if cohort == "pooled256" and metric in ["Q_mean", "Q_p10"]:
                    ax.fill_between(d.index, d[metric + "_boot_low"] * scale, d[metric + "_boot_high"] * scale,
                                    color=COLORS[cohort], alpha=.11, linewidth=0)
                if cohort == "pooled256" and metric == "P10_inverseCDF_error":
                    ax.fill_between(d.index, d.Q_p10_boot_low - truth.exact_inverted_cdf_p10,
                                    d.Q_p10_boot_high - truth.exact_inverted_cdf_p10,
                                    color=COLORS[cohort], alpha=.11, linewidth=0)
            if metric == "P10_inverseCDF_error":
                ax.axhline(0, color="#161616", lw=1)
            else:
                tcol = {"Q_mean": "Q_mean_exact", "Q_p10": "exact_inverted_cdf_p10",
                        "Q_sd_ddof1": "Q_sd_population"}[metric]
                ax.plot(truth.index, truth[tcol] * scale, color="#161616", marker="x", ms=5, lw=1.2,
                        label="完整目录逆CDF" if metric == "Q_p10" else "完整有限总体")
            if metric == "Q_p10":
                ax.plot(truth.index, truth.exact_linear_p10, color="#161616", ls=":", lw=1.4, label="完整目录linear")
            ax.set_title(title if ri == 0 else ""); ax.set_xticks(range(1, n + 1)); ax.set_xlim(.7, n + .3)
            if ci == 0:
                ax.set_ylabel(image + "\nN=" + str(n), fontsize=9)
            if ri == 5:
                ax.set_xlabel("进入人数 k；2人延期")
    axes[0, 0].legend(fontsize=8); axes[0, 1].legend(fontsize=7.5, loc="best")
    fig.suptitle("6个完整有限小池：真实追加208条全路径与目录真值逐k比较", fontsize=16, y=.995)
    fig.text(.01, .008, "范围为原先已完整枚举的6池，不按本轮Q选例；所有合法人数保留。彩色P10沿用样本linear定义，黑线分别给总体逆CDF与目录linear。\n"
             "阴影是合256的2000次整路径重抽逐点经验区间；完整目录已给出这些小池的有限总体真值，无须靠继续抽样消除固定k误差。\n"
             "完整目录在所有合法k均无共识失败，本子域不检验罕见失败；它也不能替代157个N≥30普通图的低人数追加验证。\n"
             "新路径均真实独立生成，团队端点全部复用现有完整目录。", fontsize=10, va="bottom")
    fig.tight_layout(rect=[0, .075, 1, .975])
    figures = export(fig, out, "SMALL_POOLS_48_208_256_VS_EXACT")
    meta = curve[["pool_id", "image", "building", "difficulty", "pool_n"]].drop_duplicates()
    files.append(save_csv(meta, out / "SMALL_POOLS_SUPPORT.csv"))
    save_json(dict(scope="all six frozen fully enumerated small pools; not large-N support", pools=len(pids),
                   buildings=meta.building.nunique(), pool_ids=pids, pool_n=meta.pool_n.tolist(),
                   total_pool_k_cells=int(meta.pool_n.sum()), deferred_k2_cells=6,
                   independent_new_paths_per_pool=208, primary_combined_paths_per_pool=256,
                   newly_fused_teams_in_this_subset=0, prior_finite_catalogue_reused=True,
                   figures=figures, files=files, source_commit="b9bcec809fbaec8ab055931a1abb7baa5db44dac"),
              out / "SMALL_EXACT_VALIDATION_RECEIPT.json")


if __name__ == "__main__":
    main()
