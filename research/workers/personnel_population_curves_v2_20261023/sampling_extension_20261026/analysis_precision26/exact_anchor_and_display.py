#!/usr/bin/env python3
"""Preserve pure MC results; independently compare and display exact marginals.

Catalogue linear quantiles and inverse-CDF population quantiles remain distinct.
The exact SD for a uniform finite team distribution uses denominator K; sample
SD with ddof=1 estimates that distributional spread. The historical catalogue
ddof=1 value is retained as a labelled descriptive field, not silently replaced.
"""
from pathlib import Path
import argparse
import numpy as np
import pandas as pd
from scipy.stats import binom
from precision_core import META, METRICS, BOOL, TOL, numeric, save_csv, save_json
from analyze_natural import status_class

PRIOR = "research/workers/personnel_population_curves_v2_20261023/sampling_precision_20261025"


def finite_quantile_expectation(values, n, p=.1):
    """Exact expected sample quantiles from a known discrete finite law.

    Given n scoreable uniform-team draws, P(X_(r)<=v)=P(Bin(n,F(v))>=r).
    Linear interpolation uses the two adjacent expected order statistics.
    This is a deterministic calculation, not a new permutation or bootstrap.
    """
    q = np.asarray(values, float); q = q[np.isfinite(q)]
    if len(q) == 0 or n <= 0:
        return np.nan, np.nan
    value, count = np.unique(q, return_counts=True)
    F = np.cumsum(count) / len(q)
    def order_mean(rank):
        cd = binom.sf(rank - 1, n, F)
        mass = np.diff(np.r_[0., cd])
        return float(value @ mass)
    h = p * (n - 1); lower = int(np.floor(h)) + 1; upper = int(np.ceil(h)) + 1
    frac = h - np.floor(h)
    linear = (1 - frac) * order_mean(lower) + frac * order_mean(upper)
    inverse = order_mean(max(1, int(np.ceil(p * n))))
    return linear, inverse


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--root", type=Path, required=True)
    ap.add_argument("--stage", type=int, choices=[0, 1, 2], default=2)
    ap.add_argument("--results-dir", type=Path, help="Explicit separately labelled support subset")
    args = ap.parse_args(); root = args.root.resolve()
    prior = root / "prior_recovered" / PRIOR
    out = args.results_dir.resolve() if args.results_dir else root / "analysis_precision26" / ("results_stage" + str(args.stage))
    curve = pd.read_csv(out / "NATURAL_CURVES.csv.gz", low_memory=False)
    exact = pd.read_csv(prior / "analysis_precision/new_results/EXACT_FINITE_MARGINAL_STATISTICS.csv")
    qrefs = pd.read_csv(prior / "analysis_precision/p10_definition_sensitivity/EXACT_P10_REFERENCES.csv.gz")
    exact = exact.merge(qrefs[["pool_id", "k", "exact_linear_p10", "exact_inverted_cdf_p10"]],
                        on=["pool_id", "k"], validate="one_to_one")
    raw = pd.read_csv(prior / "new_endpoints/EXACT_MARGINAL_VALUES.csv.gz", low_memory=False)
    assert not raw.duplicated(["pool_id", "k", "team_key"]).any()
    for col in set(BOOL).intersection(raw.columns):
        raw[col] = numeric(raw[col])
    raw["status_class"] = [status_class(r) for r in raw.to_dict("records")]
    ss = []; catalogues = {}
    for (pid, k), g in raw.groupby(["pool_id", "k"]):
        catalogues[(pid, int(k))] = g.B8L2.dropna().to_numpy(float)
        attempt = g.policy_deferred.eq(0) & g.status_class.ne("not_executed")
        scheduled = g.policy_deferred.eq(0)
        ss.append(dict(pool_id=pid, k=k,
                       actual_executed_nondeferred_teams=int(attempt.sum()),
                       actual_consensus_failure_teams=int(g.loc[attempt, "status_class"].eq("consensus_not_formed").sum()),
                       output_unscoreable_teams=int(g.loc[attempt, "status_class"].eq("output_unscoreable").sum()),
                       reference_unavailable_teams=int(g.loc[scheduled, "status_class"].eq("reference_unavailable").sum()),
                       not_executed_teams=int(g.loc[scheduled, "status_class"].eq("not_executed").sum()),
                       actual_consensus_failure_rate=float(g.loc[attempt, "status_class"].eq("consensus_not_formed").mean()),
                       output_unscoreable_rate=float(g.loc[attempt, "status_class"].eq("output_unscoreable").mean()),
                       reference_unavailable_rate=float(g.loc[scheduled, "status_class"].eq("reference_unavailable").mean()),
                       not_executed_rate=float(g.loc[scheduled, "status_class"].eq("not_executed").mean())))
    exact = exact.merge(pd.DataFrame(ss), on=["pool_id", "k"], validate="one_to_one")
    exact = exact[exact.exact_complete.eq(True) & exact.k.ne(2)]
    exact["anchor_type"] = np.select([exact.k.eq(exact.pool_n), exact.k.eq(1), exact.k.eq(exact.pool_n - 1)],
                                      ["full", "single_person", "leave_one_out"], default="small_pool_interior")
    z = curve.merge(exact, on=["pool_id", "k"], suffixes=("", "_exact"), validate="many_to_one")
    keep = META + ["cohort", "k", "paths_attempted", "quality_valid_paths", "unique_teams", "anchor_type",
                   "finite_population_teams_exact", "quality_valid_teams", "actual_failure_teams", "exact_kind",
                   "actual_executed_nondeferred_teams", "actual_consensus_failure_teams", "output_unscoreable_teams",
                   "reference_unavailable_teams", "not_executed_teams"]
    e = z[keep].copy()
    e["actual_failure_teams_historical_semantics"] = "legacy nondeferred score-unavailable teams; not solely consensus failure"
    comparisons = [("Q_mean", "Q_mean_exact", "Q_mean_error"),
                   ("D10_mean", "D10_mean_exact", "D10_mean_error"),
                   ("Q_sd_ddof1", "Q_sd_population", "Q_sd_error_to_uniform_population"),
                   ("Q_p10", "exact_linear_p10", "linear_P10_distance_to_catalogue_linear"),
                   ("Q_p10", "exact_inverted_cdf_p10", "linear_P10_distance_to_population_inverse_cdf"),
                   ("Q_p10_inverse_cdf", "exact_inverted_cdf_p10", "inverse_CDF_P10_error"),
                   ("failure_rate", "failure_rate_exact", "failure_rate_error")]
    for metric in ["actual_consensus_failure_rate", "output_unscoreable_rate"]:
        if metric in curve:
            comparisons.append((metric, metric + "_exact", metric + "_error"))
    for sample, truth, error in comparisons:
        e[sample] = z[sample]; e[truth] = z[truth]
        e[error] = z[sample] - z[truth]
    expectation_cache = {}; expected_linear = []; expected_cdf = []
    for row in z[["pool_id", "k", "quality_valid_paths"]].to_dict("records"):
        key = (row["pool_id"], int(row["k"]), int(row["quality_valid_paths"]))
        if key not in expectation_cache:
            expectation_cache[key] = finite_quantile_expectation(catalogues[key[:2]], key[2])
        l, c = expectation_cache[key]; expected_linear.append(l); expected_cdf.append(c)
    e["expected_sample_linear_P10_given_actual_valid_n"] = expected_linear
    e["expected_sample_inverseCDF_P10_given_actual_valid_n"] = expected_cdf
    e["linear_finite_sample_bias_to_population_inverseCDF"] = e.expected_sample_linear_P10_given_actual_valid_n - e.exact_inverted_cdf_p10
    e["linear_finite_sample_difference_to_catalogue_linear"] = e.expected_sample_linear_P10_given_actual_valid_n - e.exact_linear_p10
    e["observed_linear_P10_minus_finite_sample_expectation"] = e.Q_p10 - e.expected_sample_linear_P10_given_actual_valid_n
    e["expectation_scope"] = "analytic known uniform finite catalogue; conditional on actual valid q count; not new paths"
    e["Q_mean_MCSE_empirical"] = z.Q_mean_MCSE_analytic
    e["Q_mean_MCSE_exact_distribution_given_valid_n"] = z.Q_sd_population / np.sqrt(z.quality_valid_paths.where(z.quality_valid_paths > 0))
    e["zero_empirical_mean_MCSE_but_nonconstant_exact_distribution"] = z.Q_mean_MCSE_analytic.le(TOL) & z.Q_sd_population.gt(TOL)
    e["Q_mean_t95_covers_exact"] = np.where(z.Q_mean_exact.notna() & z.Q_mean_t95_low.notna() & z.Q_mean_t95_high.notna(),
        (z.Q_mean_t95_low.le(z.Q_mean_exact + TOL) & z.Q_mean_t95_high.ge(z.Q_mean_exact - TOL)).astype(float), np.nan)
    e["P10_order_covers_exact_inverse_CDF"] = np.where(z.exact_inverted_cdf_p10.notna() & z.P10_order_low.notna() & z.P10_order_high.notna(),
        (z.P10_order_low.le(z.exact_inverted_cdf_p10 + TOL) & z.P10_order_high.ge(z.exact_inverted_cdf_p10 - TOL)).astype(float), np.nan)
    e["P10_empirical_boot_covers_exact_inverse_CDF"] = np.where(z.exact_inverted_cdf_p10.notna() & z.Q_p10_boot_low.notna() & z.Q_p10_boot_high.notna(),
        (z.Q_p10_boot_low.le(z.exact_inverted_cdf_p10 + TOL) & z.Q_p10_boot_high.ge(z.exact_inverted_cdf_p10 - TOL)).astype(float), np.nan)
    e["Q_sd_boot_covers_uniform_population_SD"] = np.where(z.Q_sd_population.notna() & z.Q_sd_ddof1_boot_low.notna() & z.Q_sd_ddof1_boot_high.notna(),
        (z.Q_sd_ddof1_boot_low.le(z.Q_sd_population + TOL) & z.Q_sd_ddof1_boot_high.ge(z.Q_sd_population - TOL)).astype(float), np.nan)
    e["failure_CP_covers_exact_rate"] = np.where(z.failure_rate_exact.notna() & z.failure_CP_low.notna() & z.failure_CP_high.notna(),
        (z.failure_CP_low.le(z.failure_rate_exact + TOL) & z.failure_CP_high.ge(z.failure_rate_exact - TOL)).astype(float), np.nan)
    e["all_teams_seen_but_frequency_still_sampled"] = z.unique_teams.eq(z.finite_population_teams_exact)
    e["empirical_P10_boot_halfwidth"] = (z.Q_p10_boot_high - z.Q_p10_boot_low) / 2
    for threshold in [2, 5]:
        e["empirical_halfwidth_le2_but_inverseCDF_error_gt" + str(threshold)] = (
            e.empirical_P10_boot_halfwidth.le(2) & e.linear_P10_distance_to_population_inverse_cdf.abs().gt(threshold))
        e["empirical_halfwidth_le2_but_catalogue_linear_error_gt" + str(threshold)] = (
            e.empirical_P10_boot_halfwidth.le(2) & e.linear_P10_distance_to_catalogue_linear.abs().gt(threshold))
    receipts = [save_csv(e, out / "EXACT_ANCHOR_MC_ACCURACY.csv.gz")]
    budget_changes = []
    for newer, older in [("new208", "old48"), ("pooled256", "old48"), ("stage2_104", "stage1_104")]:
        a = e[e.cohort.eq(older)]; b = e[e.cohort.eq(newer)]
        if a.empty or b.empty:
            continue
        matched = a.merge(b, on=["pool_id", "k"], suffixes=("_old", "_new"), validate="one_to_one")
        for r in matched.to_dict("records"):
            observed_change = r["Q_p10_new"] - r["Q_p10_old"]
            expectation_change = r["expected_sample_linear_P10_given_actual_valid_n_new"] - r["expected_sample_linear_P10_given_actual_valid_n_old"]
            budget_changes.append(dict(pool_id=r["pool_id"], k=r["k"], image=r["image_old"], building=r["building_old"],
                                       layer=r["layer_old"], difficulty=r["difficulty_old"], pool_n=r["pool_n_old"], anchor_type=r["anchor_type_old"],
                                       older_cohort=older, newer_cohort=newer,
                                       older_valid_q_n=r["quality_valid_paths_old"], newer_valid_q_n=r["quality_valid_paths_new"],
                                       sample_linear_P10_observed_change=observed_change,
                                       expected_finite_sample_budget_change=expectation_change,
                                       sampling_deviation_change=observed_change - expectation_change,
                                       exact_population_inverseCDF_P10=r["exact_inverted_cdf_p10_old"],
                                       exact_catalogue_linear_P10=r["exact_linear_p10_old"],
                                       interpretation="Known-catalogue identity decomposition; no algorithm/personnel change and no extrapolation to unenumerated teams"))
    if budget_changes:
        receipts.append(save_csv(pd.DataFrame(budget_changes), out / "EXACT_P10_EXPECTATION_BUDGET_COMPARISONS.csv.gz"))
    summaries = []
    for (cohort, layer, anchor), g in e.groupby(["cohort", "layer", "anchor_type"], sort=False):
        for _, _, error in comparisons:
            x = g[error].dropna()
            summaries.append(dict(cohort=cohort, layer=layer, anchor_type=anchor, metric=error,
                                  eligible_cells=len(g), valid_cells=len(x), images=g.pool_id.nunique(),
                                  buildings=g.building.nunique(), mean_signed_error=x.mean(),
                                  MAE=x.abs().mean(), median_absolute_error=x.abs().median(),
                                  p90_absolute_error=x.abs().quantile(.9), max_absolute_error=x.abs().max(),
                                  abs_error_gt1_cells=int(x.abs().gt(1).sum()), abs_error_gt2_cells=int(x.abs().gt(2).sum()),
                                  abs_error_gt5_cells=int(x.abs().gt(5).sum())))
    receipts.append(save_csv(pd.DataFrame(summaries), out / "EXACT_ANCHOR_ACCURACY_SUMMARY.csv"))
    coverage = []
    for (cohort, layer, anchor), g in e.groupby(["cohort", "layer", "anchor_type"], sort=False):
        coverage.append(dict(cohort=cohort, layer=layer, anchor_type=anchor, cells=len(g), images=g.pool_id.nunique(),
                             buildings=g.building.nunique(),
                             Q_mean_exact_evaluable_cells=int(g.Q_mean_t95_covers_exact.notna().sum()),
                             Q_mean_t95_contains_exact_cells=float(g.Q_mean_t95_covers_exact.sum()),
                             zero_empirical_mean_MCSE_nonconstant_truth_cells=int(g.zero_empirical_mean_MCSE_but_nonconstant_exact_distribution.sum()),
                             P10_exact_evaluable_cells=int(g.P10_order_covers_exact_inverse_CDF.notna().sum()),
                             P10_order_contains_exact_inverseCDF_cells=float(g.P10_order_covers_exact_inverse_CDF.sum()),
                             P10_boot_contains_exact_inverseCDF_cells=float(g.P10_empirical_boot_covers_exact_inverse_CDF.sum()),
                             P10_boot_evaluable_intervals=int(g.P10_empirical_boot_covers_exact_inverse_CDF.notna().sum()),
                             Q_sd_boot_contains_exact_population_cells=float(g.Q_sd_boot_covers_uniform_population_SD.sum()),
                             Q_sd_boot_evaluable_intervals=int(g.Q_sd_boot_covers_uniform_population_SD.notna().sum()),
                             failure_CP_contains_exact_rate_cells=float(g.failure_CP_covers_exact_rate.sum()),
                             failure_CP_evaluable_intervals=int(g.failure_CP_covers_exact_rate.notna().sum()),
                             narrow_P10_boot_but_inverseCDF_error_gt2=int(g.empirical_halfwidth_le2_but_inverseCDF_error_gt2.sum()),
                             narrow_P10_boot_but_inverseCDF_error_gt5=int(g.empirical_halfwidth_le2_but_inverseCDF_error_gt5.sum()),
                             narrow_P10_boot_but_catalogue_linear_error_gt2=int(g.empirical_halfwidth_le2_but_catalogue_linear_error_gt2.sum()),
                             narrow_P10_boot_but_catalogue_linear_error_gt5=int(g.empirical_halfwidth_le2_but_catalogue_linear_error_gt5.sum()),
                             all_teams_seen_cells=int(g.all_teams_seen_but_frequency_still_sampled.sum()),
                             all_teams_seen_and_inverseCDF_error_gt5=int((g.all_teams_seen_but_frequency_still_sampled & g.linear_P10_distance_to_population_inverse_cdf.abs().gt(5)).sum()),
                             interpretation="Observed finite-anchor descriptive containment; not generalization coverage"))
    receipts.append(save_csv(pd.DataFrame(coverage), out / "EXACT_ANCHOR_INTERVAL_CONTAINMENT_AND_NARROW_MISSES.csv"))
    # Main visual curve uses exact anchors where complete finite data already
    # exist; every row states origin and keeps the random-path estimate nearby.
    main = "pooled256" if "pooled256" in set(curve.cohort) else "pooled152" if "pooled152" in set(curve.cohort) else "old48"
    d = curve[curve.cohort.eq(main)].copy()
    ex = exact.set_index(["pool_id", "k"])
    rows = []
    for r in d.to_dict("records"):
        key = (r["pool_id"], r["k"])
        row = {c: r[c] for c in META + ["k", "cohort", "paths_attempted", "quality_valid_paths", "unique_teams"]}
        row["sampling_cohort"] = main
        row["estimator"] = "uniform_random_permutation_prefixes"
        row["exact_catalogue_Q_sd_ddof1_historical"] = np.nan
        row["spread_definition"] = "sample SD ddof=1 estimates uniform-team population SD"
        row["P10_linear_definition"] = "sample type7 linear estimator; population target is inverse CDF"
        row["P10_inverseCDF_definition"] = "sample empirical inverse CDF estimator"
        for metric in METRICS:
            row[metric] = r.get(metric, np.nan); row[metric + "_pure_path"] = r.get(metric, np.nan)
        row["Q_mean_MCSE"] = r["Q_mean_MCSE_analytic"]
        row["P10_linear_boot_halfwidth"] = r["P10_linear_boot_halfwidth"]
        row["finite_teams"] = r["finite_population_teams"]
        row["actual_failure_units"] = r["failure_paths"]
        row["actual_attempt_units"] = r["nondeferred_attempts"]
        row["actual_failure_units_historical_semantics"] = "legacy nondeferred score-unavailable count; use explicit consensus/output fields"
        row["score_unavailable_units_legacy"] = r["failure_paths"]
        row["quality_valid_units"] = r["quality_valid_paths"]
        row["actual_executed_nondeferred_units"] = r["actual_executed_nondeferred_paths"]
        row["actual_consensus_failure_units"] = r["actual_consensus_failure_paths"]
        row["output_unscoreable_units"] = r["output_unscoreable_paths"]
        row["reference_unavailable_units"] = r["reference_unavailable_paths"]
        row["not_executed_units"] = r["not_executed_paths"]
        if int(r["k"]) == 2:
            row["estimator"] = "contract_deferred_k2"
        elif key in ex.index:
            x = ex.loc[key]
            row["estimator"] = "exact_finite_uniform_marginal"
            row["exact_kind"] = x.exact_kind
            row["finite_teams"] = int(x.finite_population_teams)
            row["actual_failure_units"] = int(x.actual_failure_teams)
            row["actual_attempt_units"] = int(x.nondeferred_attempts)
            row["score_unavailable_units_legacy"] = int(x.actual_failure_teams)
            row["quality_valid_units"] = int(x.quality_valid_teams)
            for stem in ["actual_executed_nondeferred", "actual_consensus_failure", "output_unscoreable",
                         "reference_unavailable", "not_executed"]:
                row[stem + "_units"] = int(x[stem + "_teams"])
            row["exact_catalogue_Q_sd_ddof1_historical"] = x.Q_sd_ddof1
            row["spread_definition"] = "exact uniform finite-team population SD (ddof=0)"
            row["P10_linear_definition"] = "historical complete-catalogue type7 linear; not the population inverse CDF"
            row["P10_inverseCDF_definition"] = "exact uniform finite-team population inverse CDF"
            for metric in METRICS:
                if metric == "Q_p10_inverse_cdf":
                    row[metric] = x.exact_inverted_cdf_p10
                elif metric == "Q_sd_ddof1":
                    row[metric] = x.Q_sd_population
                elif metric in x:
                    row[metric] = x[metric]
            row["Q_mean_MCSE"] = 0.0 if pd.notna(x.Q_mean) else np.nan
            row["P10_linear_boot_halfwidth"] = 0.0 if pd.notna(x.Q_p10) else np.nan
        # Display spread has its own honest name; the frozen historical field
        # remains in EXACT_* and the pure-path tables rather than mislabeling
        # an exact denominator-K quantity as ddof1.
        row["Q_sd_display"] = row.pop("Q_sd_ddof1")
        rows.append(row)
    receipts.append(save_csv(pd.DataFrame(rows), out / ("HYBRID_" + main.upper() + "_DISPLAY_CURVES.csv.gz")))
    save_json(dict(source_exact_csv=str(prior / "analysis_precision/new_results/EXACT_FINITE_MARGINAL_STATISTICS.csv"),
                   source_P10_definitions=str(prior / "analysis_precision/p10_definition_sensitivity/EXACT_P10_REFERENCES.csv.gz"),
                   exact_anchor_cells=int(exact[exact.pool_id.isin(curve.pool_id)].shape[0]),
                   display_cohort=main, pure_path_results_unchanged=True,
                   analytic_expectation="Uniform finite scoreable-team law, conditioned on actual valid q: binomial order statistics; no additional paths",
                   note="Catalogue linear P10 and inverse-CDF population P10 are both retained; exact spread denominator K is explicit", outputs=receipts),
              out / "EXACT_DISPLAY_RECEIPT.json")


if __name__ == "__main__":
    main()
