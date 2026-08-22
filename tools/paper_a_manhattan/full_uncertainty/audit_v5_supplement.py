"""Strict, non-destructive follow-up audit for the v5 uncertainty outputs."""
from __future__ import annotations

import argparse
import itertools
import math
from pathlib import Path
from typing import Iterable

import numpy as np
import pandas as pd
from scipy import stats

ROOT = Path(__file__).resolve().parents[3]
DEFAULT_INPUT = ROOT / "analysis_results" / "full_uncertainty_data_mining_20260821_v5"
DEFAULT_OUTPUT = ROOT / "analysis_results" / "full_uncertainty_data_mining_20260821_v5_supplement"
SEED = 20260822
IMAGE_PREDICTORS = (
    "mean_luma", "horizontal_gradient_mean_wrap", "seam_gradient_mean",
    "vertical_edge_mean", "boundary_gradient_mean", "edge_density_proxy",
    "gt_pair_count", "proposal_initial_quality_mean",
)
LEGACY_LABELS = ("occlusion", "low_texture", "seam", "reflection", "trivial", "low_quality", "residual")
OUTCOME_SOURCE = "IMAGE_FEATURE_VS_SEMI_ASSOCIATIONS.csv"


class SchemaError(ValueError):
    """Raised when a v5 input is absent or its contract has drifted."""


def _require(frame: pd.DataFrame, columns: Iterable[str], name: str) -> None:
    missing = sorted(set(columns) - set(frame.columns))
    if missing:
        raise SchemaError(f"{name}: missing required columns: {', '.join(missing)}")


def _read(input_dir: Path, filename: str, columns: Iterable[str]) -> pd.DataFrame:
    path = input_dir / filename
    if not path.is_file():
        raise SchemaError(f"missing v5 input: {path}")
    frame = pd.read_csv(path, low_memory=False)
    _require(frame, columns, filename)
    return frame


def bh_adjust(values: Iterable[float | None]) -> np.ndarray:
    """Benjamini-Hochberg q values while retaining NA positions."""
    values = np.asarray(list(values), dtype=float)
    result = np.full(values.shape, np.nan, dtype=float)
    valid = np.isfinite(values)
    if not valid.any():
        return result
    order = np.argsort(values[valid], kind="stable")
    ranked = values[valid][order]
    adjusted = np.minimum.accumulate((ranked * len(ranked) / np.arange(1, len(ranked) + 1))[::-1])[::-1]
    restored = np.empty_like(adjusted)
    restored[order] = np.clip(adjusted, 0, 1)
    result[valid] = restored
    return result


def _rank(values: pd.Series) -> pd.Series:
    return pd.to_numeric(values, errors="coerce").rank(method="average")


def _cluster_t(x: np.ndarray, y: np.ndarray, clusters: np.ndarray) -> tuple[float, float, float]:
    X = np.column_stack((np.ones(len(x)), x))
    inv = np.linalg.pinv(X.T @ X)
    beta = inv @ X.T @ y
    residual = y - X @ beta
    meat = np.zeros((2, 2))
    for cluster in pd.unique(clusters):
        score = X[clusters == cluster].T @ residual[clusters == cluster]
        meat += np.outer(score, score)
    g, n, k = len(pd.unique(clusters)), len(y), X.shape[1]
    correction = (g / (g - 1)) * ((n - 1) / (n - k)) if g > 1 and n > k else 1.0
    covariance = correction * inv @ meat @ inv
    se = math.sqrt(max(float(covariance[1, 1]), 0.0))
    return float(beta[1]), se, float(beta[1] / se) if se > 0 else np.nan


def exact_cluster_signflip_p(x: pd.Series, y: pd.Series, cluster: pd.Series, *, seed: int = SEED) -> tuple[float, int, int]:
    """Two-sided wild cluster sign-flip p; enumerate exactly through 12 clusters."""
    work = pd.DataFrame({"x": _rank(x), "y": _rank(y), "cluster": cluster.astype(str)}).dropna()
    if len(work) < 3 or work.x.nunique() < 2 or work.y.nunique() < 2:
        return np.nan, len(work), work.cluster.nunique()
    xv, yv, clusters = work.x.to_numpy(), work.y.to_numpy(), work.cluster.to_numpy()
    _, _, observed = _cluster_t(xv, yv, clusters)
    if not math.isfinite(observed):
        return np.nan, len(work), len(pd.unique(clusters))
    unique = np.asarray(pd.unique(clusters))
    restricted = np.mean(yv)
    residual = yv - restricted
    if len(unique) <= 12:
        signs_iter = itertools.product((-1.0, 1.0), repeat=len(unique))
        denominator = 2 ** len(unique)
    else:
        rng = np.random.default_rng(seed)
        signs_iter = (rng.choice((-1.0, 1.0), len(unique)) for _ in range(20000))
        denominator = 20000
    index = {value: i for i, value in enumerate(unique)}
    row_index = np.array([index[value] for value in clusters])
    extreme = 0
    for signs in signs_iter:
        _, _, simulated = _cluster_t(xv, restricted + residual * np.asarray(signs)[row_index], clusters)
        extreme += int(math.isfinite(simulated) and abs(simulated) >= abs(observed) - 1e-12)
    return extreme / denominator, len(work), len(unique)


def cluster_bootstrap_rank_ci(x: pd.Series, y: pd.Series, cluster: pd.Series, *, seed: int = SEED, replicates: int = 1000) -> tuple[float, float]:
    work = pd.DataFrame({"x": x, "y": y, "cluster": cluster.astype(str)})
    work["x"] = pd.to_numeric(work.x, errors="coerce")
    work["y"] = pd.to_numeric(work.y, errors="coerce")
    work = work.dropna()
    unique = np.asarray(pd.unique(work.cluster))
    if len(unique) < 3:
        return np.nan, np.nan
    x_values = work.x.to_numpy(dtype=float)
    y_values = work.y.to_numpy(dtype=float)
    cluster_values = work.cluster.to_numpy()
    groups = [np.flatnonzero(cluster_values == value) for value in unique]
    rng = np.random.default_rng(seed)
    estimates: list[float] = []
    for _ in range(replicates):
        indices = np.concatenate([groups[index] for index in rng.integers(0, len(groups), len(groups))])
        sample_x, sample_y = x_values[indices], y_values[indices]
        if np.ptp(sample_x) > 0 and np.ptp(sample_y) > 0:
            estimates.append(float(np.corrcoef(stats.rankdata(sample_x), stats.rankdata(sample_y))[0, 1]))
    return tuple(map(float, np.quantile(estimates, [0.025, 0.975]))) if estimates else (np.nan, np.nan)


def image_feature_alias_audit(features: pd.DataFrame) -> pd.DataFrame:
    _require(features, ["base_task_id", "horizontal_gradient_mean_wrap", "vertical_edge_mean"], "image features")
    rows = []
    for left, right in itertools.combinations([c for c in IMAGE_PREDICTORS if c in features], 2):
        pair = features[[left, right]].apply(pd.to_numeric, errors="coerce").dropna()
        rho = stats.spearmanr(pair[left], pair[right]).statistic if len(pair) >= 3 else np.nan
        same_x_gradient_family = {left, right} == {"horizontal_gradient_mean_wrap", "vertical_edge_mean"}
        rows.append({
            "feature_left": left, "feature_right": right, "row_count": len(pair),
            "spearman_rho": float(rho) if math.isfinite(rho) else np.nan,
            "exact_value_identity": bool(len(pair) and np.array_equal(pair[left], pair[right])),
            "max_absolute_difference": float((pair[left] - pair[right]).abs().max()) if len(pair) else np.nan,
            "alias_family": "horizontal_x_gradient" if same_x_gradient_family else "none",
            "excluded_from_unique_multiplicity": same_x_gradient_family,
            "note": "Both fields derive from the x-gradient family (wrap versus no-wrap); vertical_edge_mean is retained for provenance but is not an independent y-gradient test."
            if same_x_gradient_family else "pairwise redundancy audit",
        })
    return pd.DataFrame(rows)


def image_feature_associations(features: pd.DataFrame, outcomes: pd.DataFrame, proposal: pd.DataFrame, original: pd.DataFrame, *, bootstrap_replicates: int = 1000) -> pd.DataFrame:
    _require(features, ["base_task_id", "building_id", *IMAGE_PREDICTORS], "image features")
    _require(outcomes, ["base_task_id", "building_id"], "semi outcomes")
    _require(proposal, ["base_task_id"], "proposal outcomes")
    _require(original, ["predictor", "outcome", "permutation_p"], OUTCOME_SOURCE)
    if len(original) != 72 or original.predictor.nunique() != 8 or original.outcome.nunique() != 9:
        raise SchemaError("IMAGE_FEATURE_VS_SEMI_ASSOCIATIONS.csv must contain the v5 8 x 9 = 72 tests")
    pairs = original[["predictor", "outcome"]].drop_duplicates()
    merged = features.merge(outcomes, on=["base_task_id", "building_id"], how="left", suffixes=("", "_semi"))
    merged = merged.merge(proposal.drop_duplicates("base_task_id"), on="base_task_id", how="left", suffixes=("", "_proposal"))
    rows = []
    for pair in pairs.itertuples(index=False):
        if pair.predictor not in merged or pair.outcome not in merged:
            raise SchemaError(f"cannot derive image test {pair.predictor} ~ {pair.outcome} from v5 outputs")
        work = merged[[pair.predictor, pair.outcome, "building_id"]].copy()
        work[pair.predictor] = pd.to_numeric(work[pair.predictor], errors="coerce")
        work[pair.outcome] = pd.to_numeric(work[pair.outcome], errors="coerce")
        work = work.dropna()
        rho = float(stats.spearmanr(work[pair.predictor], work[pair.outcome]).statistic) if len(work) >= 3 and work[pair.predictor].nunique() > 1 and work[pair.outcome].nunique() > 1 else np.nan
        p, n_tasks, n_buildings = exact_cluster_signflip_p(work[pair.predictor], work[pair.outcome], work.building_id, seed=SEED + sum(map(ord, pair.predictor + pair.outcome)))
        lo, hi = cluster_bootstrap_rank_ci(work[pair.predictor], work[pair.outcome], work.building_id, seed=SEED + 1000 + sum(map(ord, pair.predictor + pair.outcome)), replicates=bootstrap_replicates)
        rows.append({
            "predictor": pair.predictor, "outcome": pair.outcome,
            "predictor_duplicate_alias": pair.predictor == "vertical_edge_mean",
            "task_count": n_tasks, "building_count": n_buildings,
            "rank_effect_spearman": rho, "effect_rank_transformed": rho,
            "effect": rho,
            "cluster_bootstrap_rank_ci_lower": lo, "cluster_bootstrap_rank_ci_upper": hi,
            "ci_lower": lo, "ci_upper": hi, "wild_cluster_exact_or_mc_p": p, "p_value": p,
            "inference_unit": "building_cluster; rank(x), rank(y); exact signflip when clusters <= 12",
        })
    result = pd.DataFrame(rows)
    unique = ~result.predictor_duplicate_alias
    result["q_bh_global_unique"] = np.nan
    result.loc[unique, "q_bh_global_unique"] = bh_adjust(result.loc[unique, "wild_cluster_exact_or_mc_p"])
    result["q_bh_within_outcome_unique"] = np.nan
    for _, indices in result.loc[unique].groupby("outcome").groups.items():
        result.loc[indices, "q_bh_within_outcome_unique"] = bh_adjust(result.loc[indices, "wild_cluster_exact_or_mc_p"])
    result["q_bh_global_unique_predictors"] = result["q_bh_global_unique"]
    result["q_bh_within_outcome_unique_predictors"] = result["q_bh_within_outcome_unique"]
    return result


def difficulty_proxy_outcome_join_audit(proxy: pd.DataFrame, semi: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    _require(proxy, ["base_task_id"], "difficulty proxy")
    _require(semi, ["base_task_id", "building_id", "delta_shannon_entropy"], "semi outcomes")
    joined = semi[["base_task_id", "building_id", "delta_shannon_entropy"]].drop_duplicates("base_task_id").merge(proxy, on="base_task_id", how="left", indicator=True)
    matched = int(joined._merge.eq("both").sum())
    if (semi.base_task_id.nunique(), proxy.base_task_id.nunique(), matched) != (25, 22, 22):
        raise SchemaError("v5 difficulty join drift: expected 25 Semi tasks, 22 proxy tasks, and 22 matches")
    detail = joined[["base_task_id", "building_id", "_merge"]].rename(columns={"_merge": "join_status"})
    detail["join_status"] = detail.join_status.map({"both": "matched", "left_only": "missing_proxy"})
    summary = pd.DataFrame([{
        "audit_level": "summary", "semi_task_count": len(joined), "proxy_task_count": int(proxy.base_task_id.nunique()),
        "matched_task_count": matched, "missing_proxy_task_count": len(joined) - matched,
        "missing_proxy_filled_as_zero": False, "note": "missing proxy predictors remain NA and are excluded per test; no zero imputation",
    }])
    detail.insert(0, "audit_level", "task")
    return pd.concat([summary, detail.assign(matched_task_count=matched, missing_proxy_task_count=len(joined) - matched)], ignore_index=True, sort=False), joined


def difficulty_proxy_associations(proxy: pd.DataFrame, semi: pd.DataFrame, *, bootstrap_replicates: int = 1000) -> pd.DataFrame:
    join_audit, joined = difficulty_proxy_outcome_join_audit(proxy, semi)
    del join_audit
    rows = []
    for predictor in [c for c in ("gt_pair_count", "proposal_initial_quality_mean") if c in joined]:
        work = joined[[predictor, "delta_shannon_entropy", "building_id"]].copy()
        work[predictor] = pd.to_numeric(work[predictor], errors="coerce")
        work = work.dropna()
        p, n_tasks, n_buildings = exact_cluster_signflip_p(work[predictor], work.delta_shannon_entropy, work.building_id, seed=SEED + sum(map(ord, predictor)))
        lo, hi = cluster_bootstrap_rank_ci(work[predictor], work.delta_shannon_entropy, work.building_id, seed=SEED + 2000 + sum(map(ord, predictor)), replicates=bootstrap_replicates)
        rho = stats.spearmanr(work[predictor], work.delta_shannon_entropy).statistic if len(work) >= 3 and work[predictor].nunique() > 1 else np.nan
        rows.append({
            "predictor_family": "legacy_or_reference_proxy", "predictor": predictor,
            "predictor_timing": "preoutcome_or_reference_derived; not frozen confirmatory risk",
            "task_count": n_tasks, "building_count": n_buildings,
            "group_0_count": np.nan, "group_1_count": np.nan,
            "group_0_mean_delta_entropy": np.nan, "group_1_mean_delta_entropy": np.nan,
            "group_mean_difference_1_minus_0": np.nan,
            "spearman_rho": rho, "cluster_bootstrap_rho_ci_lower": lo,
            "cluster_bootstrap_rho_ci_upper": hi, "wild_cluster_exact_or_mc_p": p,
            "missing_predictor_not_imputed": True,
        })
    for source, timing in (
        ("legacy_difficulty_label", "legacy_preoutcome_proxy"),
        ("manual_difficulty_choices_json", "worker_postresponse_tag"),
    ):
        if source not in joined:
            continue
        observed = joined[joined[source].notna() & joined[source].astype(str).str.strip().ne("")].copy()
        source_text = observed[source].astype(str).str.lower()
        for label in LEGACY_LABELS:
            work = observed[["delta_shannon_entropy", "building_id"]].copy()
            work["predictor"] = source_text.str.contains(label, regex=False).astype(int)
            work = work.dropna(subset=["delta_shannon_entropy"])
            group0 = pd.to_numeric(work.loc[work.predictor.eq(0), "delta_shannon_entropy"], errors="coerce").dropna()
            group1 = pd.to_numeric(work.loc[work.predictor.eq(1), "delta_shannon_entropy"], errors="coerce").dropna()
            p, n_tasks, n_buildings = exact_cluster_signflip_p(
                work.predictor, work.delta_shannon_entropy, work.building_id,
                seed=SEED + sum(map(ord, source + label)),
            )
            lo, hi = cluster_bootstrap_rank_ci(
                work.predictor, work.delta_shannon_entropy, work.building_id,
                seed=SEED + 3000 + sum(map(ord, source + label)), replicates=bootstrap_replicates,
            )
            rho = stats.spearmanr(work.predictor, work.delta_shannon_entropy).statistic if work.predictor.nunique() > 1 else np.nan
            rows.append({
                "predictor_family": source, "predictor": label, "predictor_timing": timing,
                "task_count": n_tasks, "building_count": n_buildings,
                "group_0_count": len(group0), "group_1_count": len(group1),
                "group_0_mean_delta_entropy": float(group0.mean()) if len(group0) else np.nan,
                "group_1_mean_delta_entropy": float(group1.mean()) if len(group1) else np.nan,
                "group_mean_difference_1_minus_0": float(group1.mean() - group0.mean()) if len(group0) and len(group1) else np.nan,
                "spearman_rho": float(rho) if math.isfinite(rho) else np.nan,
                "cluster_bootstrap_rho_ci_lower": lo, "cluster_bootstrap_rho_ci_upper": hi,
                "wild_cluster_exact_or_mc_p": p, "missing_predictor_not_imputed": True,
            })
    result = pd.DataFrame(rows)
    result["q_bh_within_predictor_family"] = np.nan
    for _, indices in result.groupby("predictor_family").groups.items():
        result.loc[indices, "q_bh_within_predictor_family"] = bh_adjust(result.loc[indices, "wild_cluster_exact_or_mc_p"])
    result["q_bh_global"] = bh_adjust(result.wild_cluster_exact_or_mc_p)
    return result


def _cluster_mean_signflip(
    values: pd.Series,
    clusters: pd.Series,
    *,
    estimand: str,
    seed: int = SEED,
    replicates: int = 1000,
) -> dict[str, float | int]:
    work = pd.DataFrame({"value": pd.to_numeric(values, errors="coerce"), "cluster": clusters.astype(str)}).dropna()
    if work.empty:
        return {"estimate": np.nan, "median": np.nan, "p": np.nan, "ci_lower": np.nan, "ci_upper": np.nan, "task_count": 0, "building_count": 0}
    grouped = {name: group for name, group in work.groupby("cluster", sort=False)}
    unique = list(grouped)

    def statistic(frame: pd.DataFrame) -> float:
        if estimand == "task_equal":
            return float(frame.value.mean())
        if estimand == "building_equal":
            return float(frame.groupby("cluster", sort=False).value.mean().mean())
        raise ValueError(f"unknown estimand: {estimand}")

    observed = statistic(work)
    median = float(work.value.median()) if estimand == "task_equal" else float(work.groupby("cluster").value.mean().median())
    extreme = 0
    for signs in itertools.product((-1.0, 1.0), repeat=len(unique)):
        sign_map = dict(zip(unique, signs))
        signed = work.assign(value=work.value * work.cluster.map(sign_map))
        extreme += abs(statistic(signed)) >= abs(observed) - 1e-15
    p = extreme / (2 ** len(unique))
    rng = np.random.default_rng(seed)
    draws = []
    for _ in range(replicates):
        selected = rng.choice(unique, len(unique), replace=True)
        if estimand == "task_equal":
            sample = pd.concat([grouped[name].assign(cluster=f"boot_{index}") for index, name in enumerate(selected)], ignore_index=True)
            draws.append(statistic(sample))
        else:
            draws.append(float(np.mean([grouped[name].value.mean() for name in selected])))
    ci_lower, ci_upper = np.quantile(draws, [0.025, 0.975]) if draws else (np.nan, np.nan)
    return {
        "estimate": observed, "median": median, "p": float(p),
        "ci_lower": float(ci_lower), "ci_upper": float(ci_upper),
        "task_count": len(work), "building_count": len(unique),
    }


def partition_failure_rate_sensitivity(semi: pd.DataFrame, *, bootstrap_replicates: int = 1000) -> pd.DataFrame:
    _require(semi, ["base_task_id", "building_id", "manual_subset_count", "manual_nonunique_or_not_evaluable_count", "semi_subset_count", "semi_nonunique_or_not_evaluable_count"], "semi outcomes")
    work = semi.copy()
    for condition in ("manual", "semi"):
        work[f"{condition}_failure_rate"] = pd.to_numeric(work[f"{condition}_nonunique_or_not_evaluable_count"], errors="coerce") / pd.to_numeric(work[f"{condition}_subset_count"], errors="coerce").replace(0, np.nan)
    work["delta_failure_rate"] = work.semi_failure_rate - work.manual_failure_rate
    rows = []
    for estimand in ("task_equal", "building_equal"):
        summary = _cluster_mean_signflip(
            work.delta_failure_rate, work.building_id, estimand=estimand,
            seed=SEED + sum(map(ord, estimand)), replicates=bootstrap_replicates,
        )
        rows.append({
            "estimand": estimand, "metric": "semi_minus_manual_partition_failure_rate",
            "estimate": summary["estimate"], "median_estimand_unit_value": summary["median"],
            "cluster_bootstrap_ci_lower": summary["ci_lower"], "cluster_bootstrap_ci_upper": summary["ci_upper"],
            "task_count": summary["task_count"], "building_count": summary["building_count"],
            "exact_building_signflip_p": summary["p"],
            "definition": "failure_count / subset_count; missing/zero denominator remains NA",
        })
    return pd.DataFrame(rows)


def semi_power_estimand_sensitivity(semi: pd.DataFrame, projection: pd.DataFrame | None = None) -> pd.DataFrame:
    _require(semi, ["building_id", "delta_shannon_entropy"], "semi outcomes")
    values = pd.to_numeric(semi.delta_shannon_entropy, errors="coerce")
    task = pd.DataFrame({"value": values, "building_id": semi.building_id}).dropna()
    building = task.groupby("building_id", as_index=False).value.agg(["sum", "count", "mean"]).reset_index()
    scenarios = [9, 18, 27, 36, 54, 72, 100, 150, 239, 500]
    if projection is not None and "projected_independent_building_count" in projection:
        scenarios = sorted(set(pd.to_numeric(projection.projected_independent_building_count, errors="coerce").dropna().astype(int)))
    rows = []
    task_effect = float(task.value.mean())
    task_cluster_influence = (building["sum"] - task_effect * building["count"]) / building["count"].mean()
    estimands = (
        ("task_equal", task_effect, task_cluster_influence, "cluster influence of the task-equal ratio estimator"),
        ("building_equal", float(building["mean"].mean()), building["mean"], "between-building SD of building means"),
    )
    for estimand, effect, variance_values, variance_basis in estimands:
        sd = float(variance_values.std(ddof=1)) if len(variance_values) > 1 else np.nan
        for count in scenarios:
            se = sd / math.sqrt(count) if math.isfinite(sd) and count > 0 else np.nan
            for assumed in (abs(effect), 0.05, 0.10, 0.20):
                power = float(stats.norm.sf(stats.norm.ppf(.975) - abs(assumed) / se) + stats.norm.cdf(-stats.norm.ppf(.975) - abs(assumed) / se)) if se and se > 0 else np.nan
                rows.append({
                    "estimand": estimand, "current_task_count": len(task), "current_building_count": len(building),
                    "projected_independent_building_count": count, "assumed_true_absolute_effect": assumed,
                    "observed_effect": effect, "observed_cluster_scale_sd": sd, "standard_error": se,
                    "approximate_two_sided_power": power, "independent_unit": "building",
                    "variance_basis": variance_basis,
                    "estimand_note": "task_equal uses a ratio-estimator cluster influence; building_equal averages building means",
                })
    return pd.DataFrame(rows)


def quality_risk_task_building_cluster_audit(
    evidence: pd.DataFrame,
    worker_profile: pd.DataFrame,
    *, seed: int = SEED,
    replicates: int = 1000,
) -> pd.DataFrame:
    _require(evidence, ["base_task_id", "building_id", "risk", "quality", "worker_id", "eligibility_status", "formal_assignment_eligible"], "risk evidence")
    _require(worker_profile, ["worker_id", "administratively_eligible"], "worker profile")
    frame = evidence.merge(worker_profile[["worker_id", "administratively_eligible"]], on="worker_id", how="left")
    administrative = frame.administratively_eligible.astype(str).str.lower().isin(["true", "1", "yes"])
    populations = {
        "all_computable": frame,
        "formal_only": frame[frame.formal_assignment_eligible.astype(str).str.lower().isin(["true", "1", "yes"])],
        "administrative_eligible": frame[administrative],
        "administrative_ineligible": frame[~administrative],
    }
    rows = []
    for population, subset in populations.items():
        subset = subset.assign(risk_num=pd.to_numeric(subset.risk, errors="coerce"), quality_num=pd.to_numeric(subset.quality, errors="coerce"))
        subset = subset.dropna(subset=["risk_num", "quality_num", "base_task_id", "building_id"])
        task = subset.groupby(["base_task_id", "building_id"], as_index=False).agg(risk=("risk_num", "mean"), quality=("quality_num", "mean"), worker_support=("worker_id", "nunique"))
        if len(task) < 3 or task.risk.nunique() < 2:
            rows.append({"population": population, "status": "not_evaluable", "source_row_count": len(subset), "task_count": len(task), "building_count": task.building_id.nunique()})
            continue
        slope = float(stats.linregress(task.risk, task.quality).slope)
        rho = float(stats.spearmanr(task.risk, task.quality).statistic)
        p, _, _ = exact_cluster_signflip_p(task.risk, task.quality, task.building_id, seed=seed + sum(map(ord, population)))
        buildings = list(task.building_id.astype(str).unique())
        risk_values = task.risk.to_numpy(dtype=float)
        quality_values = task.quality.to_numpy(dtype=float)
        building_values = task.building_id.astype(str).to_numpy()
        group_indices = [np.flatnonzero(building_values == building) for building in buildings]
        rng = np.random.default_rng(seed)
        slopes = []
        for _ in range(replicates):
            indices = np.concatenate([group_indices[index] for index in rng.integers(0, len(group_indices), len(group_indices))])
            sample_x, sample_y = risk_values[indices], quality_values[indices]
            denominator = float(np.sum((sample_x - sample_x.mean()) ** 2))
            if denominator > 0:
                slopes.append(float(np.sum((sample_x - sample_x.mean()) * (sample_y - sample_y.mean())) / denominator))
        rows.append({"population": population, "status": "task_aggregated_building_cluster_bootstrap", "source_row_count": len(subset), "task_count": len(task), "building_count": len(buildings), "quality_per_risk_slope": slope, "task_level_spearman_rho": rho, "rank_effect_exact_building_signflip_p": p, "cluster_bootstrap_repetitions": len(slopes), "cluster_bootstrap_ci_lower": float(np.quantile(slopes, .025)) if slopes else np.nan, "cluster_bootstrap_ci_upper": float(np.quantile(slopes, .975)) if slopes else np.nan, "formal_row_level_p_reported": False, "note": "aggregate risk and quality to task first; bootstrap whole buildings; population retained"})
    return pd.DataFrame(rows)


def build_audits(input_dir: Path = DEFAULT_INPUT, *, bootstrap_replicates: int = 1000) -> dict[str, pd.DataFrame]:
    image_original = _read(input_dir, OUTCOME_SOURCE, ["predictor", "outcome", "permutation_p"])
    features = _read(input_dir, "IMAGE_FEATURES_ALL_214.csv", ["base_task_id", "building_id", *IMAGE_PREDICTORS])
    semi = _read(input_dir, "SEMI_25_CONVERGENCE_EXPANSION_ALL_IMAGES.csv", ["base_task_id", "building_id", "delta_shannon_entropy", "delta_gini_simpson", "delta_largest_mode_share", "delta_supported_multimodality", "delta_pairwise_metric_dissimilarity_all", "delta_quality_iou"])
    proposal = _read(input_dir, "PROPOSAL_TASK_ANCHORING_AND_DISCOVERY.csv", ["base_task_id", "edit_rate", "edit_rmse_mean", "delta_metric_mean"])
    proxy = _read(input_dir, "DIFFICULTY_PROXY_COVERAGE.CSV", ["base_task_id", "gt_pair_count", "proposal_initial_quality_mean"])
    risk = _read(input_dir, "C2_TERMINAL_RISK_EVIDENCE_240.csv", ["base_task_id", "building_id", "risk", "quality", "worker_id", "eligibility_status", "formal_assignment_eligible"])
    worker_profile = _read(input_dir, "WORKER_QUALITY_RAW_ADJUSTED_EB.csv", ["worker_id", "administratively_eligible"])
    join, _ = difficulty_proxy_outcome_join_audit(proxy, semi)
    return {
        "CALCULATION_MODE_AUDIT": pd.DataFrame([
            {"component": "image_association", "status": "supplement_primary", "analysis_unit": "task; building cluster", "correction": "rank effect, enumerated wild-cluster sign-flip, fixed-seed cluster bootstrap, BH"},
            {"component": "image_original_nominal", "status": "retained_for_provenance_only", "analysis_unit": "task rows", "correction": "72 original tests retained; not used as primary inference"},
            {"component": "image_alias", "status": "corrected", "analysis_unit": "predictor family", "correction": "vertical_edge_mean retained as x-gradient-family alias; 72 nominal tests -> 63 unique tests"},
            {"component": "difficulty_join", "status": "corrected", "analysis_unit": "matched task", "correction": "22/25 matched; missing predictors remain NA; no zero imputation"},
            {"component": "difficulty_proxy_scope", "status": "audited", "analysis_unit": "predictor", "correction": "gt_keypoint_count is an exact 2x alias of gt_pair_count; vote counts are constant; confidence is provenance status; frozen n_ready is zero"},
            {"component": "partition_failure", "status": "corrected", "analysis_unit": "task_equal and building_equal", "correction": "estimands reported separately with building sign-flip and cluster bootstrap"},
            {"component": "semi_power", "status": "corrected", "analysis_unit": "independent building", "correction": "task-equal ratio influence and equal-building variance reported separately"},
            {"component": "quality_risk", "status": "corrected", "analysis_unit": "task; building cluster", "correction": "risk and quality aggregated to task before building bootstrap"},
        ]),
        "IMAGE_FEATURE_ALIAS_AUDIT": image_feature_alias_audit(features),
        "IMAGE_FEATURE_ASSOCIATIONS_BUILDING_CLUSTERED": image_feature_associations(features, semi, proposal, image_original, bootstrap_replicates=bootstrap_replicates),
        "DIFFICULTY_PROXY_OUTCOME_JOIN_AUDIT": join,
        "DIFFICULTY_PROXY_ASSOCIATIONS_BUILDING_CLUSTERED": difficulty_proxy_associations(proxy, semi, bootstrap_replicates=bootstrap_replicates),
        "PARTITION_FAILURE_RATE_SENSITIVITY": partition_failure_rate_sensitivity(semi, bootstrap_replicates=bootstrap_replicates),
        "SEMI_POWER_ESTIMAND_SENSITIVITY": semi_power_estimand_sensitivity(semi),
        "QUALITY_RISK_TASK_BUILDING_CLUSTER_AUDIT": quality_risk_task_building_cluster_audit(risk, worker_profile, replicates=bootstrap_replicates),
    }


def build_frames(input_dir: Path, *, bootstrap_replicates: int = 10000) -> dict[str, pd.DataFrame]:
    """Return the eight planned CSV frames, keyed by their exact filenames."""
    return {f"{name}.csv": frame for name, frame in build_audits(Path(input_dir), bootstrap_replicates=bootstrap_replicates).items()}


def materialize(input_dir: Path = DEFAULT_INPUT, output_dir: Path = DEFAULT_OUTPUT) -> dict[str, pd.DataFrame]:
    outputs = build_frames(Path(input_dir))
    Path(output_dir).mkdir(parents=True, exist_ok=True)
    for name, frame in outputs.items():
        frame.to_csv(Path(output_dir) / name, index=False, lineterminator="\n")
    return outputs


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input-dir", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    materialize(args.input_dir, args.output_dir)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
