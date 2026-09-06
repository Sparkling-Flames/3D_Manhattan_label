from __future__ import annotations

import argparse
import itertools
import json
import math
from pathlib import Path
from typing import Any, Iterable

import numpy as np
import pandas as pd
from scipy import stats

ROOT = Path(__file__).resolve().parents[3]
V5 = ROOT / "analysis_results" / "full_uncertainty_data_mining_20260821_v5"
DEFAULT_OUT = ROOT / "analysis_results" / "full_uncertainty_data_mining_20260821_v5_followup_audit"
SEED = 20260822

IMAGE_PREDICTORS = [
    "mean_luma",
    "std_luma",
    "horizontal_gradient_mean_wrap",
    "vertical_edge_mean",
    "seam_gradient_mean",
    "low_texture_fraction",
    "top_boundary_gradient_mean",
    "bottom_boundary_gradient_mean",
]
SEMI_OUTCOMES = [
    "manual_shannon_entropy",
    "delta_shannon_entropy",
    "delta_gini_simpson",
    "delta_largest_mode_share",
    "delta_supported_multimodality",
    "delta_pairwise_correspondence_disagreement",
    "delta_pairwise_metric_dissimilarity_all",
    "delta_quality_iou",
    "edit_rate",
]
LEGACY_LABELS = [
    "occlusion",
    "low_texture",
    "seam",
    "reflection",
    "trivial",
    "low_quality",
    "residual",
]


def read_csv(name: str) -> pd.DataFrame:
    path = V5 / name
    if not path.is_file():
        raise FileNotFoundError(path)
    return pd.read_csv(path, low_memory=False)


def write_csv(path: Path, frame: pd.DataFrame) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(path, index=False, encoding="utf-8", lineterminator="\n")


def bh_qvalues(p_values: Iterable[float]) -> np.ndarray:
    values = np.asarray(list(p_values), dtype=float)
    result = np.full(values.shape, np.nan)
    valid = np.isfinite(values)
    if not valid.any():
        return result
    p = values[valid]
    order = np.argsort(p)
    ranked = p[order]
    adjusted = ranked * len(ranked) / np.arange(1, len(ranked) + 1)
    adjusted = np.minimum.accumulate(adjusted[::-1])[::-1]
    adjusted = np.clip(adjusted, 0.0, 1.0)
    restored = np.empty_like(adjusted)
    restored[order] = adjusted
    result[valid] = restored
    return result


def spearman(x: pd.Series, y: pd.Series) -> float:
    work = pd.DataFrame({"x": pd.to_numeric(x, errors="coerce"), "y": pd.to_numeric(y, errors="coerce")}).dropna()
    if len(work) < 3 or work["x"].nunique() < 2 or work["y"].nunique() < 2:
        return float("nan")
    return float(stats.spearmanr(work["x"], work["y"]).statistic)


def cluster_robust_t(x: np.ndarray, y: np.ndarray, clusters: np.ndarray) -> tuple[float, float, float]:
    x = np.asarray(x, dtype=float)
    y = np.asarray(y, dtype=float)
    clusters = np.asarray(clusters)
    X = np.column_stack([np.ones(len(x)), x])
    xtx_inv = np.linalg.pinv(X.T @ X)
    beta = xtx_inv @ X.T @ y
    residual = y - X @ beta
    unique = pd.unique(clusters)
    meat = np.zeros((2, 2), dtype=float)
    for group in unique:
        mask = clusters == group
        score = X[mask].T @ residual[mask]
        meat += np.outer(score, score)
    n = len(y)
    k = X.shape[1]
    g = len(unique)
    correction = (g / (g - 1)) * ((n - 1) / (n - k)) if g > 1 and n > k else 1.0
    covariance = correction * xtx_inv @ meat @ xtx_inv
    se = float(math.sqrt(max(covariance[1, 1], 0.0)))
    t_value = float(beta[1] / se) if se > 0 else float("nan")
    return float(beta[1]), se, t_value


def wild_cluster_signflip_p(
    x: pd.Series,
    y: pd.Series,
    cluster: pd.Series,
    *,
    max_enumeration_clusters: int = 12,
    monte_carlo_replicates: int = 20000,
    seed: int = SEED,
) -> tuple[float, float, float, int, int]:
    work = pd.DataFrame(
        {
            "x": pd.to_numeric(x, errors="coerce"),
            "y": pd.to_numeric(y, errors="coerce"),
            "cluster": cluster.astype(str),
        }
    ).dropna()
    if len(work) < 5 or work["x"].nunique() < 2 or work["y"].nunique() < 2:
        return float("nan"), float("nan"), float("nan"), len(work), work["cluster"].nunique()
    x_values = work["x"].to_numpy(dtype=float)
    y_values = work["y"].to_numpy(dtype=float)
    clusters = work["cluster"].to_numpy()
    beta, se, observed_t = cluster_robust_t(x_values, y_values, clusters)
    unique = np.asarray(pd.unique(clusters))
    restricted_mean = float(np.mean(y_values))
    residual_null = y_values - restricted_mean
    if not math.isfinite(observed_t):
        return beta, se, float("nan"), len(work), len(unique)

    if len(unique) <= max_enumeration_clusters:
        signs_iter: Iterable[tuple[int, ...]] = itertools.product((-1, 1), repeat=len(unique))
        denominator = 2 ** len(unique)
    else:
        rng = np.random.default_rng(seed)
        signs_iter = (
            tuple(rng.choice((-1, 1), size=len(unique)).tolist())
            for _ in range(monte_carlo_replicates)
        )
        denominator = monte_carlo_replicates

    cluster_index = {value: index for index, value in enumerate(unique)}
    row_cluster_index = np.asarray([cluster_index[value] for value in clusters], dtype=int)
    extreme = 0
    valid_replicates = 0
    for signs in signs_iter:
        signs_array = np.asarray(signs, dtype=float)
        y_star = restricted_mean + residual_null * signs_array[row_cluster_index]
        _beta, _se, t_star = cluster_robust_t(x_values, y_star, clusters)
        if math.isfinite(t_star):
            valid_replicates += 1
            extreme += abs(t_star) >= abs(observed_t) - 1e-12
    if valid_replicates == 0:
        p_value = float("nan")
    else:
        p_value = extreme / valid_replicates if denominator == valid_replicates else (extreme + 1) / (valid_replicates + 1)
    return beta, se, float(p_value), len(work), len(unique)


def cluster_bootstrap_spearman_ci(
    x: pd.Series,
    y: pd.Series,
    cluster: pd.Series,
    *,
    replicates: int = 5000,
    seed: int = SEED,
) -> tuple[float, float]:
    work = pd.DataFrame(
        {
            "x": pd.to_numeric(x, errors="coerce"),
            "y": pd.to_numeric(y, errors="coerce"),
            "cluster": cluster.astype(str),
        }
    ).dropna()
    unique = sorted(work["cluster"].unique())
    if len(unique) < 3:
        return float("nan"), float("nan")
    grouped = {value: work[work["cluster"].eq(value)] for value in unique}
    rng = np.random.default_rng(seed)
    draws: list[float] = []
    for _ in range(replicates):
        parts = []
        for boot_index, selected in enumerate(rng.choice(unique, size=len(unique), replace=True)):
            part = grouped[selected].copy()
            part["boot_cluster"] = boot_index
            parts.append(part)
        sample = pd.concat(parts, ignore_index=True)
        estimate = spearman(sample["x"], sample["y"])
        if math.isfinite(estimate):
            draws.append(estimate)
    if not draws:
        return float("nan"), float("nan")
    return tuple(map(float, np.quantile(draws, [0.025, 0.975])))


def exact_cluster_signflip_mean(
    values: pd.Series,
    clusters: pd.Series,
    *,
    bootstrap_replicates: int = 10000,
    seed: int = SEED,
) -> dict[str, Any]:
    work = pd.DataFrame({"value": pd.to_numeric(values, errors="coerce"), "cluster": clusters.astype(str)}).dropna()
    if work.empty:
        return {
            "task_count": 0,
            "building_count": 0,
            "mean": np.nan,
            "median": np.nan,
            "ci_lower": np.nan,
            "ci_upper": np.nan,
            "exact_signflip_p": np.nan,
        }
    observed = float(work["value"].mean())
    unique = sorted(work["cluster"].unique())
    extreme = 0
    total = 0
    for signs in itertools.product((-1.0, 1.0), repeat=len(unique)):
        sign_map = dict(zip(unique, signs))
        statistic = float((work["value"] * work["cluster"].map(sign_map)).mean())
        extreme += abs(statistic) >= abs(observed) - 1e-15
        total += 1

    grouped = {value: work[work["cluster"].eq(value)] for value in unique}
    rng = np.random.default_rng(seed)
    draws = []
    for _ in range(bootstrap_replicates):
        parts = [grouped[selected] for selected in rng.choice(unique, size=len(unique), replace=True)]
        draws.append(float(pd.concat(parts, ignore_index=True)["value"].mean()))
    lower, upper = np.quantile(draws, [0.025, 0.975])
    return {
        "task_count": len(work),
        "building_count": len(unique),
        "mean": observed,
        "median": float(work["value"].median()),
        "ci_lower": float(lower),
        "ci_upper": float(upper),
        "exact_signflip_p": float(extreme / total),
    }


def duplicate_feature_audit(features: pd.DataFrame) -> pd.DataFrame:
    rows = []
    available = [column for column in IMAGE_PREDICTORS if column in features]
    for left, right in itertools.combinations(available, 2):
        pair = features[[left, right]].apply(pd.to_numeric, errors="coerce").dropna()
        if pair.empty:
            continue
        difference = np.abs(pair[left] - pair[right])
        rows.append(
            {
                "feature_left": left,
                "feature_right": right,
                "shared_row_count": len(pair),
                "maximum_absolute_difference": float(difference.max()),
                "exactly_equal_on_shared_rows": bool((difference <= 1e-15).all()),
                "pearson_r": float(pair[left].corr(pair[right])),
            }
        )
    return pd.DataFrame(rows).sort_values(
        ["exactly_equal_on_shared_rows", "maximum_absolute_difference"],
        ascending=[False, True],
    )


def image_feature_associations(features: pd.DataFrame, semi: pd.DataFrame) -> pd.DataFrame:
    merged = semi.merge(features, how="left", on="base_task_id", suffixes=("", "_image"))
    available_predictors = [column for column in IMAGE_PREDICTORS if column in merged]
    duplicate_pairs = duplicate_feature_audit(features)
    duplicate_aliases: set[str] = set()
    if not duplicate_pairs.empty:
        for row in duplicate_pairs[duplicate_pairs["exactly_equal_on_shared_rows"]].itertuples(index=False):
            if {row.feature_left, row.feature_right} == {"horizontal_gradient_mean_wrap", "vertical_edge_mean"}:
                duplicate_aliases.add("vertical_edge_mean")
    rows = []
    for predictor in available_predictors:
        for outcome in [column for column in SEMI_OUTCOMES if column in merged]:
            work = merged[[predictor, outcome, "building_id"]].copy()
            work[predictor] = pd.to_numeric(work[predictor], errors="coerce")
            work[outcome] = pd.to_numeric(work[outcome], errors="coerce")
            work = work.dropna()
            task_rho = spearman(work[predictor], work[outcome])
            building = work.groupby("building_id", as_index=False).agg(
                predictor_mean=(predictor, "mean"),
                outcome_mean=(outcome, "mean"),
            )
            building_rho = spearman(building["predictor_mean"], building["outcome_mean"])
            beta, cluster_se, p_cluster, n_tasks, n_buildings = wild_cluster_signflip_p(
                work[predictor], work[outcome], work["building_id"],
                seed=SEED + sum(map(ord, predictor + outcome)),
            )
            ci_lower, ci_upper = cluster_bootstrap_spearman_ci(
                work[predictor], work[outcome], work["building_id"],
                seed=SEED + 1000 + sum(map(ord, predictor + outcome)),
            )
            rows.append(
                {
                    "predictor": predictor,
                    "outcome": outcome,
                    "predictor_duplicate_alias": predictor in duplicate_aliases,
                    "task_count": n_tasks,
                    "building_count": n_buildings,
                    "task_level_spearman_rho": task_rho,
                    "building_mean_spearman_rho": building_rho,
                    "cluster_bootstrap_task_rho_ci_lower": ci_lower,
                    "cluster_bootstrap_task_rho_ci_upper": ci_upper,
                    "ols_slope": beta,
                    "cluster_robust_se": cluster_se,
                    "wild_cluster_exact_or_mc_p": p_cluster,
                    "inference_unit": "building-cluster; duplicate aliases excluded from multiplicity families",
                }
            )
    result = pd.DataFrame(rows)
    unique_mask = ~result["predictor_duplicate_alias"]
    result["q_bh_global_unique_predictors"] = np.nan
    result.loc[unique_mask, "q_bh_global_unique_predictors"] = bh_qvalues(
        result.loc[unique_mask, "wild_cluster_exact_or_mc_p"]
    )
    result["q_bh_within_outcome_unique_predictors"] = np.nan
    for _outcome, indices in result[unique_mask].groupby("outcome").groups.items():
        result.loc[indices, "q_bh_within_outcome_unique_predictors"] = bh_qvalues(
            result.loc[indices, "wild_cluster_exact_or_mc_p"]
        )
    return result.sort_values(
        ["predictor_duplicate_alias", "q_bh_global_unique_predictors", "wild_cluster_exact_or_mc_p"],
        na_position="last",
    )


def difficulty_proxy_associations(proxy: pd.DataFrame, semi: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    current = semi[
        [
            "base_task_id",
            "building_id",
            "delta_shannon_entropy",
            "delta_quality_iou",
            "manual_shannon_entropy",
        ]
    ].copy()
    stale_columns = [column for column in proxy if column.startswith("delta_") or column.endswith("_entropy_q095")]
    predictors = proxy.drop(columns=stale_columns, errors="ignore")
    merged = current.merge(predictors, how="left", on="base_task_id", suffixes=("", "_proxy"))
    rows = []

    for predictor in ["gt_pair_count", "proposal_initial_quality_mean"]:
        if predictor not in merged:
            continue
        work = merged[[predictor, "delta_shannon_entropy", "building_id"]].copy()
        work[predictor] = pd.to_numeric(work[predictor], errors="coerce")
        work = work.dropna()
        beta, cluster_se, p_cluster, n_tasks, n_buildings = wild_cluster_signflip_p(
            work[predictor], work["delta_shannon_entropy"], work["building_id"],
            seed=SEED + sum(map(ord, predictor)),
        )
        ci_lower, ci_upper = cluster_bootstrap_spearman_ci(
            work[predictor], work["delta_shannon_entropy"], work["building_id"],
            seed=SEED + 2000 + sum(map(ord, predictor)),
        )
        rows.append(
            {
                "predictor_family": "legacy_or_reference_proxy",
                "predictor": predictor,
                "predictor_timing": "preoutcome_or_reference_derived; not frozen confirmatory risk",
                "task_count": n_tasks,
                "building_count": n_buildings,
                "group_0_count": np.nan,
                "group_1_count": np.nan,
                "group_0_mean_delta_entropy": np.nan,
                "group_1_mean_delta_entropy": np.nan,
                "group_mean_difference_1_minus_0": np.nan,
                "spearman_rho": spearman(work[predictor], work["delta_shannon_entropy"]),
                "cluster_bootstrap_rho_ci_lower": ci_lower,
                "cluster_bootstrap_rho_ci_upper": ci_upper,
                "ols_slope": beta,
                "cluster_robust_se": cluster_se,
                "wild_cluster_exact_or_mc_p": p_cluster,
            }
        )

    label_sources = [
        ("legacy_difficulty_label", "legacy_preoutcome_proxy"),
        ("manual_difficulty_choices_json", "worker_postresponse_tag"),
    ]
    for source_column, timing in label_sources:
        if source_column not in merged:
            continue
        source = merged[source_column].fillna("").astype(str).str.lower()
        for code in LEGACY_LABELS:
            if code == "reflection":
                mask = source.str.contains("reflection", regex=False)
            else:
                mask = source.str.contains(code, regex=False)
            work = merged.loc[:, ["delta_shannon_entropy", "building_id"]].copy()
            work["predictor"] = mask.astype(int)
            work = work.dropna(subset=["delta_shannon_entropy"])
            group0 = pd.to_numeric(work.loc[work["predictor"].eq(0), "delta_shannon_entropy"], errors="coerce").dropna()
            group1 = pd.to_numeric(work.loc[work["predictor"].eq(1), "delta_shannon_entropy"], errors="coerce").dropna()
            beta, cluster_se, p_cluster, n_tasks, n_buildings = wild_cluster_signflip_p(
                work["predictor"], work["delta_shannon_entropy"], work["building_id"],
                seed=SEED + sum(map(ord, source_column + code)),
            )
            rows.append(
                {
                    "predictor_family": source_column,
                    "predictor": code,
                    "predictor_timing": timing,
                    "task_count": n_tasks,
                    "building_count": n_buildings,
                    "group_0_count": len(group0),
                    "group_1_count": len(group1),
                    "group_0_mean_delta_entropy": float(group0.mean()) if len(group0) else np.nan,
                    "group_1_mean_delta_entropy": float(group1.mean()) if len(group1) else np.nan,
                    "group_mean_difference_1_minus_0": (
                        float(group1.mean() - group0.mean()) if len(group0) and len(group1) else np.nan
                    ),
                    "spearman_rho": spearman(work["predictor"], work["delta_shannon_entropy"]),
                    "cluster_bootstrap_rho_ci_lower": np.nan,
                    "cluster_bootstrap_rho_ci_upper": np.nan,
                    "ols_slope": beta,
                    "cluster_robust_se": cluster_se,
                    "wild_cluster_exact_or_mc_p": p_cluster,
                }
            )
    result = pd.DataFrame(rows)
    result["q_bh_within_predictor_family"] = np.nan
    for _family, indices in result.groupby("predictor_family").groups.items():
        result.loc[indices, "q_bh_within_predictor_family"] = bh_qvalues(
            result.loc[indices, "wild_cluster_exact_or_mc_p"]
        )
    result["q_bh_global"] = bh_qvalues(result["wild_cluster_exact_or_mc_p"])

    audit = pd.DataFrame(
        [
            {
                "audit": "proxy_outcome_staleness",
                "stale_columns_removed": ";".join(stale_columns),
                "current_semi_task_count": len(current),
                "merged_task_count": len(merged),
                "note": "Any historical outcome column in the proxy file is discarded; current v5 outcomes are rejoined by base_task_id.",
            }
        ]
    )
    return result.sort_values(["q_bh_global", "wild_cluster_exact_or_mc_p"], na_position="last"), audit


def partition_failure_sensitivity(semi: pd.DataFrame) -> pd.DataFrame:
    work = semi.copy()
    for prefix in ("manual", "semi"):
        subset = pd.to_numeric(work[f"{prefix}_subset_count"], errors="coerce")
        failures = pd.to_numeric(work[f"{prefix}_nonunique_or_not_evaluable_count"], errors="coerce")
        work[f"{prefix}_partition_failure_rate"] = failures / subset.replace(0, np.nan)
    work["delta_partition_failure_rate"] = (
        work["semi_partition_failure_rate"] - work["manual_partition_failure_rate"]
    )
    summary = exact_cluster_signflip_mean(work["delta_partition_failure_rate"], work["building_id"])
    return pd.DataFrame(
        [
            {
                "metric": "semi_minus_manual_partition_failure_rate",
                **summary,
                "definition": "nonunique_or_not_evaluable_subset_count / subset_count",
                "reason": "Shannon entropy is defined only for unique partitions; differential partition failure is a required co-outcome.",
            }
        ]
    )


def power_tables(semi: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    task = semi[["building_id", "delta_shannon_entropy"]].copy()
    task["delta_shannon_entropy"] = pd.to_numeric(task["delta_shannon_entropy"], errors="coerce")
    task = task.dropna()
    building = task.groupby("building_id", as_index=False)["delta_shannon_entropy"].mean()
    effects = building["delta_shannon_entropy"].to_numpy(dtype=float)
    current_buildings = len(effects)
    observed_mean = float(np.mean(effects))
    observed_sd = float(np.std(effects, ddof=1))
    z_alpha = float(stats.norm.ppf(0.975))
    z_power = float(stats.norm.ppf(0.80))

    df = current_buildings - 1
    sd_ci_lower = observed_sd * math.sqrt(df / stats.chi2.ppf(0.975, df))
    sd_ci_upper = observed_sd * math.sqrt(df / stats.chi2.ppf(0.025, df))

    required_rows = []
    for effect in (0.01, 0.05, 0.10, 0.15, 0.20):
        def required(sd: float) -> int:
            return int(math.ceil(((z_alpha + z_power) * sd / effect) ** 2))
        required_rows.append(
            {
                "assumed_true_absolute_entropy_effect": effect,
                "current_building_count": current_buildings,
                "observed_building_effect_mean": observed_mean,
                "observed_building_effect_sd": observed_sd,
                "building_effect_sd_95ci_lower_approx": sd_ci_lower,
                "building_effect_sd_95ci_upper_approx": sd_ci_upper,
                "approximate_total_buildings_for_80pct_power_point_sd": required(observed_sd),
                "approximate_total_buildings_for_80pct_power_low_sd": required(sd_ci_lower),
                "approximate_total_buildings_for_80pct_power_high_sd": required(sd_ci_upper),
                "formula": "ceil(((z_0.975 + z_0.80) * sd_building / effect)^2)",
                "interpretation": "Conditional frequentist power, not probability that the effect is real.",
            }
        )

    def normal_power(building_count: int, effect: float) -> float:
        se = observed_sd / math.sqrt(building_count)
        noncentral = abs(effect) / se
        return float(stats.norm.cdf(-z_alpha - noncentral) + 1 - stats.norm.cdf(z_alpha - noncentral))

    power_rows = []
    for building_count in (9, 18, 27, 36, 54, 72, 100, 150, 239, 500):
        for effect in (abs(observed_mean), 0.01, 0.05, 0.10, 0.15, 0.20):
            power_rows.append(
                {
                    "projected_independent_building_count": building_count,
                    "assumed_true_absolute_entropy_effect": effect,
                    "effect_scenario": "current_observed_building_mean" if math.isclose(effect, abs(observed_mean), rel_tol=0, abs_tol=1e-12) else "fixed_effect_scenario",
                    "approximate_two_sided_power": normal_power(building_count, effect),
                    "observed_building_effect_sd": observed_sd,
                    "warning": "Power is conditional on the assumed true effect and current variance estimate.",
                }
            )

    rng = np.random.default_rng(SEED)
    empirical_rows = []
    for building_count in (9, 18, 27, 36, 54, 72, 100, 150, 239, 500):
        significant = 0
        replicates = 20000
        for _ in range(replicates):
            sample = rng.choice(effects, size=building_count, replace=True)
            test = stats.ttest_1samp(sample, 0.0)
            significant += bool(math.isfinite(test.pvalue) and test.pvalue < 0.05)
        empirical_rows.append(
            {
                "projected_independent_building_count": building_count,
                "empirical_resampling_significance_frequency": significant / replicates,
                "replicates": replicates,
                "source_building_count": current_buildings,
                "source_building_mean": observed_mean,
                "source_building_sd": observed_sd,
                "interpretation": "Frequency under resampling from the nine observed building effects; not posterior probability or guaranteed replication rate.",
            }
        )
    return pd.DataFrame(required_rows), pd.DataFrame(power_rows), pd.DataFrame(empirical_rows)


def coverage_matrix() -> pd.DataFrame:
    rows = [
        ("Raw annotation versions and revision lineage", "covered", "RAW_ANNOTATION_LEDGER_ALL_2513.csv;REVISION_LINEAGE_ALL_2513.csv;RAW_ONLY_TO_SELECTED_CONTEXT_CROSSWALK.csv", ""),
        ("Administrative, excluded, outside-assignment and ineligible records", "covered", "ALL_RECORDS_WITH_ORTHOGONAL_FLAGS.csv;EXCLUSION_REASON_*.csv;EXCLUDED_*", ""),
        ("Manual/Semi convergence and expansion by image", "covered", "SEMI_25_CONVERGENCE_EXPANSION_ALL_IMAGES.csv;CURRENT_MANUAL_SEMI_UNCERTAINTY_SUMMARY.CSV", ""),
        ("Equal-k reclustering and threshold sensitivity", "covered", "TASK_SUBSET_RECLUSTERING.CSV;THRESHOLD_ROBUSTNESS.CSV;POPULATION_SENSITIVITY.CSV", ""),
        ("Meta-label uncertainty", "covered", "META_LABEL_*;META_MANUAL_SEMI_TASK_COMPARISON.csv", "Paired task comparison should be primary over unpaired stage means."),
        ("Geometry uncertainty across stages", "covered", "GEOMETRY_TASK_UNCERTAINTY_ALL_STAGES.CSV;GEOMETRY_PAIRWISE_DISPERSION_ALL_STAGES.CSV", ""),
        ("Active time and separate lead time", "covered", "ACTIVE_TIME_*;TIME_*", "Event clock-offset field requires relabeling before behavior interpretation."),
        ("Crowd/minority modes versus operational GT", "covered_descriptive", "CROWD_GT_101_GEOMETRIC_CAUSE_AUDIT.csv;C1_CROWD_GT_*", "Observable geometric differences are not adjudicated causes."),
        ("Two-annotator sensitivity", "covered", "DUAL_ANNOTATOR_GEOMETRY_SENSITIVITY_ALL.csv;DUAL_ANNOTATOR_GEOMETRY_AND_GT_QUALITY.csv", ""),
        ("Repeated worker viewpoints", "covered_descriptive", "WORKER_VIEWPOINT_*;WORKER_MODE_*", "Internal split-half repeatability is weak; no stable worldview claim."),
        ("Proposal anchoring, revision and tag/behavior mismatch", "covered_descriptive", "PROPOSAL_*;SEMI_REVIEW_*;TAG_BEHAVIOR_*", "Not randomized; cannot separate anchoring from structure discovery causally."),
        ("Image traits and risk associations", "partial", "IMAGE_FEATURES_ALL_214.csv;IMAGE_FEATURE_VS_SEMI_ASSOCIATIONS.csv;DIFFICULTY_PROXY_*", "No frozen semantic pre-assignment risk; existing low-level image tests need clustered inference and multiplicity correction."),
        ("Persistent disagreement at high support", "covered_selected_tasks", "PERSISTENT_DISAGREEMENT_*;C1_K22_PREFIX_REPLAY*", "Selected high-support tasks are not representative prevalence estimates."),
        ("Reference-version trajectory", "missing", "", "Current snapshot does not reconstruct changes in operational GT/reference versions."),
        ("Independent expert mode adjudication/reclustering", "missing", "", "Required to distinguish image ambiguity, protocol ambiguity, worker error and reference error."),
        ("Event-sequence behavior phenotype", "partial", "RAW_ACTIVE_EVENT_FACT.CSV;RAW_ACTIVE_SESSION_FACT.CSV;EVENT_SESSION_INTEGRITY_SUMMARY.csv", "Events are inventoried but no validated pause/revisit/gate-failure phenotype is materialized."),
        ("Missingness probability model", "missing", "", "Missingness is audited descriptively but not modeled as an outcome."),
        ("Task mechanism clustering", "missing", "", "No stable task-type clustering combining geometry, meta, time and image traits."),
    ]
    return pd.DataFrame(rows, columns=["conversation_requirement", "coverage_status", "v5_evidence", "remaining_boundary"])


def method_audit(
    duplicate_features: pd.DataFrame,
    partition_sensitivity: pd.DataFrame,
    image_associations: pd.DataFrame,
) -> pd.DataFrame:
    duplicate_detected = bool(
        not duplicate_features.empty
        and duplicate_features["exactly_equal_on_shared_rows"].any()
    )
    return pd.DataFrame(
        [
            {
                "severity": "high",
                "component": "IMAGE_FEATURE_VS_SEMI_ASSOCIATIONS.csv",
                "finding": "Published p-values permute/bootstrap task rows although 25 tasks are nested in 9 buildings.",
                "impact": "Nominal p-values and confidence intervals can be too narrow when within-building outcomes are correlated.",
                "correction": "Use building-cluster inference; follow-up table provides wild cluster sign-flip p-values and cluster bootstrap intervals.",
            },
            {
                "severity": "high",
                "component": "IMAGE_FEATURE_VS_SEMI_ASSOCIATIONS.csv",
                "finding": "The published 72 tests have no family-level or global multiplicity adjustment.",
                "impact": "A few p<.05 results are expected by chance across many correlated tests.",
                "correction": "Use unique predictors and report BH q-values globally and within outcome families.",
            },
            {
                "severity": "medium",
                "component": "IMAGE_FEATURES_ALL_214.csv",
                "finding": f"Exact duplicate/alias image features detected: {duplicate_detected}.",
                "impact": "Duplicate hypotheses double-count the same signal and distort multiplicity families.",
                "correction": "Treat vertical_edge_mean as an alias of horizontal_gradient_mean_wrap when equality is exact.",
            },
            {
                "severity": "medium",
                "component": "Task entropy",
                "finding": "Shannon entropy is averaged only over subsets with unique partitions.",
                "impact": "If partition failure rates differ by condition, entropy comparisons condition on a post-clustering selection event.",
                "correction": "Report Semi-Manual partition-failure-rate difference as a co-outcome and retain all-pair dissimilarity as a partition-free sensitivity.",
            },
            {
                "severity": "medium",
                "component": "EVENT_SESSION_INTEGRITY_SUMMARY.csv",
                "finding": "client_server_lag_seconds is approximately 28,800 seconds across records.",
                "impact": "This is consistent with a timezone/clock offset and should not be interpreted as network or user latency.",
                "correction": "Rename to client_server_clock_offset_seconds or normalize timezones before behavioral analysis.",
            },
            {
                "severity": "low",
                "component": "SEMI_REQUIRED_BUILDINGS_BY_EFFECT.CSV",
                "finding": "The current v5 inverse power table uses z_0.975 + z_0.80 and is mathematically consistent with the stated normal approximation.",
                "impact": "No correction to the central formula is required, but variance uncertainty from only 9 buildings is not shown.",
                "correction": "Report a sample-size range based on the approximate confidence interval for building-level SD.",
            },
            {
                "severity": "boundary",
                "component": "CROWD_GT_101_GEOMETRIC_CAUSE_AUDIT.csv",
                "finding": "Difference codes are observable geometric contrasts, not verified causal explanations.",
                "impact": "They cannot establish whether crowd, minority mode, protocol or reference is correct.",
                "correction": "Add independent expert mode adjudication and reference-version provenance.",
            },
        ]
    )


def report_markdown(
    coverage: pd.DataFrame,
    method: pd.DataFrame,
    partition: pd.DataFrame,
    image_assoc: pd.DataFrame,
    difficulty: pd.DataFrame,
    required: pd.DataFrame,
    normal_power: pd.DataFrame,
    empirical: pd.DataFrame,
) -> str:
    image_candidates = image_assoc[
        (~image_assoc["predictor_duplicate_alias"])
        & image_assoc["wild_cluster_exact_or_mc_p"].notna()
    ].sort_values("wild_cluster_exact_or_mc_p").head(12)
    difficulty_candidates = difficulty.sort_values("wild_cluster_exact_or_mc_p", na_position="last").head(12)
    current_effect_power = normal_power[
        normal_power["effect_scenario"].eq("current_observed_building_mean")
    ]
    return "\n".join(
        [
            "# v5 标注不确定性补充审计：覆盖、聚类推断与 Semi 扩展功效",
            "",
            "## 1. 对话需求覆盖",
            "",
            coverage.to_markdown(index=False),
            "",
            "## 2. 计算模式审计",
            "",
            method.to_markdown(index=False),
            "",
            "## 3. 唯一分区失败率敏感性",
            "",
            partition.to_markdown(index=False),
            "",
            "Shannon 模式熵只在聚类得到唯一分区时有定义，因此分区失败率必须与熵差同时报告。正值表示 Semi 的不可唯一分区比例更高。",
            "",
            "## 4. 图像特质与 Semi 结果：building-cluster 复算",
            "",
            image_candidates.to_markdown(index=False),
            "",
            "表中 `wild_cluster_exact_or_mc_p` 以 building 为聚类单位；`q_bh_*` 对重复别名删除后的检验进行多重比较校正。它们替代原表的逐任务行置换 p 值作为探索性推断。",
            "",
            "## 5. legacy 难度 proxy 与 worker response tag",
            "",
            difficulty_candidates.to_markdown(index=False),
            "",
            "legacy proxy、reference-derived complexity 和工人作答后的标签属于不同时间层。worker postresponse tag 不能用于声称标注前风险预测。",
            "",
            "## 6. Semi 扩展实验功效",
            "",
            required.to_markdown(index=False),
            "",
            "### 若真实效应等于当前 9 个 building 的观测均值",
            "",
            current_effect_power.to_markdown(index=False),
            "",
            "### 从当前 9 个 building 效应经验分布重采样的显著频率",
            "",
            empirical.to_markdown(index=False),
            "",
            "经验重采样频率不是后验概率，也不是未来显著性的保证；它只回答在把当前 9 个 building 当作未来分布近似时，重复抽样得到 p<.05 的频率。",
            "",
            "## 7. 客观边界",
            "",
            "- 当前总体平均熵差接近零；增加样本可能使其更精确地接近零，也可能揭示预先冻结的交互效应。",
            "- 同一图片增加工人数主要改善少数模式识别；总体主效应和风险交互主要依赖新增独立 task/building。",
            "- 图像特质分析必须在标注前冻结，且不能把同一批工人的 difficulty tag 当作独立预测变量。",
            "- proposal anchoring 与 structure discovery 需要随机化设计，现有观察性记录不能作因果区分。",
        ]
    ) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args()
    out = args.output_dir.resolve()
    out.mkdir(parents=True, exist_ok=True)

    semi = read_csv("SEMI_25_CONVERGENCE_EXPANSION_ALL_IMAGES.csv")
    features = read_csv("IMAGE_FEATURES_ALL_214.csv")
    proxy = read_csv("DIFFICULTY_PROXY_COVERAGE.CSV")
    proposal = read_csv("PROPOSAL_TASK_ANCHORING_AND_DISCOVERY.csv")
    semi_for_features = semi.drop(columns=["edit_rate"], errors="ignore").merge(
        proposal[["base_task_id", "edit_rate"]].drop_duplicates("base_task_id"),
        how="left",
        on="base_task_id",
    )

    duplicates = duplicate_feature_audit(features)
    image_assoc = image_feature_associations(features, semi_for_features)
    difficulty, proxy_audit = difficulty_proxy_associations(proxy, semi)
    partition = partition_failure_sensitivity(semi)
    required, normal_power, empirical = power_tables(semi)
    coverage = coverage_matrix()
    method = method_audit(duplicates, partition, image_assoc)

    outputs = {
        "COVERAGE_MATRIX.csv": coverage,
        "METHOD_AUDIT_FINDINGS.csv": method,
        "IMAGE_FEATURE_DUPLICATE_AUDIT.csv": duplicates,
        "IMAGE_FEATURE_ASSOCIATIONS_BUILDING_CLUSTERED.csv": image_assoc,
        "DIFFICULTY_PROXY_ASSOCIATIONS_BUILDING_CLUSTERED.csv": difficulty,
        "DIFFICULTY_PROXY_OUTCOME_JOIN_AUDIT.csv": proxy_audit,
        "PARTITION_FAILURE_RATE_SENSITIVITY.csv": partition,
        "SEMI_REQUIRED_BUILDINGS_WITH_SD_UNCERTAINTY.csv": required,
        "SEMI_CONDITIONAL_POWER_SCENARIOS.csv": normal_power,
        "SEMI_EMPIRICAL_RESAMPLING_SIGNIFICANCE_FREQUENCY.csv": empirical,
    }
    for name, frame in outputs.items():
        write_csv(out / name, frame)

    report = report_markdown(
        coverage,
        method,
        partition,
        image_assoc,
        difficulty,
        required,
        normal_power,
        empirical,
    )
    (out / "FOLLOWUP_AUDIT_REPORT_ZH.md").write_text(report, encoding="utf-8")

    summary = {
        "source_directory": V5.relative_to(ROOT).as_posix(),
        "paired_task_count": int(semi["base_task_id"].nunique()),
        "building_count": int(semi["building_id"].nunique()),
        "image_feature_test_count_unique_predictors": int((~image_assoc["predictor_duplicate_alias"]).sum()),
        "duplicate_alias_test_count": int(image_assoc["predictor_duplicate_alias"].sum()),
        "coverage_missing_count": int(coverage["coverage_status"].eq("missing").sum()),
        "coverage_partial_count": int(coverage["coverage_status"].str.startswith("partial").sum()),
        "note": "Follow-up audit does not replace v5 raw facts; it corrects clustered/multiplicity inference and exposes remaining design boundaries.",
    }
    (out / "RUN_SUMMARY.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
