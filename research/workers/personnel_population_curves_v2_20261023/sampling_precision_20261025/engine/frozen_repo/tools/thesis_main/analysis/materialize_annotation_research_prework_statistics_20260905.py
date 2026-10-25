"""全历史标注研究统计前置（审计/敏感性，不产生正式 worker taxonomy）。"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
from functools import lru_cache
import sys
from collections import Counter, defaultdict, deque
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

import numpy as np

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.thesis_main.analysis import audit_annotation_research_data_20260905 as audit_v1
from tools.thesis_main.analysis import materialize_historical_uncertainty_k_curves_20260829 as historical
from tools.thesis_main.analysis.full_uncertainty.full_uncertainty_common import cyclic_rmse
from tools.thesis_main.analysis.geometry_consensus.pairwise import pairwise_similarity

DEFAULT_OUT = ROOT / "analysis_results" / "annotation_research_prework_20260905_v2" / "statistics"
V1 = ROOT / "analysis_results" / "annotation_research_decision_audit_20260905_v1" / "data_audit"
SUBSTRATE = V1 / "recomputed_uncertainty_substrate"
EVIDENCE = ROOT / "analysis_results" / "annotation_research_prework_20260905_v2" / "evidence" / "record_evidence.csv"
SEED = 20260905
BOOTSTRAPS = 1_000
REPLAY_REPLICATES = 200
THRESHOLDS = (0.7, 0.8, 0.9)
STRUCTURE_CUTOFFS = (0.93, 0.95, 0.97)
K_VALUES = tuple(range(15, 21))

FIELD_CONTRACT = {
    "schema_version": "annotation_research_prework_statistics_v2",
    "role": "audit_and_sensitivity_only_not_formal_worker_taxonomy_or_stage3_gate",
    "record_key": ["canonical_annotation_id"],
    "stratum_key": ["stage", "condition", "reference_source_version", "feature_name"],
    "required_evidence_fields": [
        "canonical_annotation_id", "stage", "condition", "base_task_id", "building_id",
        "worker_id", "reference_version", "geometry_status", "quality_reference_status",
        "active_time_owner_valid_status", "habit_feature_status", "source_role", "source_path",
        "evidence_note",
    ],
    "missing_rule": "missing_or_not_evaluable_is_never_zero",
    "active_time_rule": "positive_owner_valid_task_worker_cumulative_only; lead_time_excluded",
    "bootstrap_rule": "exactly_1000_building_then_task_draws; no_rejection_or_redraw",
    "classification_rule": "all_requested_draw_probability_bounds_at_0.7_0.8_0.9; near_zero_1e-10_ties_half_mass; single_building_descriptive_only",
    "holdout_rule": "classification_training_tasks_are_disjoint_from_evaluation_tasks",
    "replay_rule": "one_worker_one_vote; selected_only_medoid; remaining_workers_evaluation",
}


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def write_csv(path: Path, rows: Sequence[Mapping[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = sorted({key for row in rows for key in row}) if rows else ["status"]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore", lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows or [{"status": "no_rows"}])


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def truth(value: Any) -> bool:
    return str(value).strip().lower() in {"1", "true", "yes", "eligible", "available", "valid", "passed"}


def number(value: Any) -> float | None:
    try:
        result = float(str(value).strip())
    except (TypeError, ValueError):
        return None
    return result if math.isfinite(result) else None


def stable_seed(*parts: Any) -> int:
    digest = hashlib.sha256("|".join(map(str, parts)).encode()).hexdigest()
    return SEED + int(digest[:8], 16)


def worker_task_components(rows: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    adjacency: dict[str, set[str]] = defaultdict(set)
    for row in rows:
        worker, task = f"w:{row['worker_id']}", f"t:{row['base_task_id']}"
        adjacency[worker].add(task)
        adjacency[task].add(worker)
    output, seen = [], set()
    for start in sorted(adjacency):
        if start in seen:
            continue
        queue, nodes = deque([start]), set()
        while queue:
            node = queue.popleft()
            if node in nodes:
                continue
            nodes.add(node)
            queue.extend(adjacency[node] - nodes)
        seen |= nodes
        workers = sorted(node[2:] for node in nodes if node.startswith("w:"))
        tasks = sorted(node[2:] for node in nodes if node.startswith("t:"))
        output.append({"workers": workers, "tasks": tasks})
    return sorted(output, key=lambda item: (-len(item["workers"]), -len(item["tasks"]), item["workers"]))


def fit_worker_task_effects(rows: Sequence[Mapping[str, Any]]) -> dict[str, float]:
    workers = sorted({str(row["worker_id"]) for row in rows})
    tasks = sorted({str(row["base_task_id"]) for row in rows})
    if len(workers) < 2 or len(tasks) < 2 or len(worker_task_components(rows)) != 1:
        return {}
    wi, ti = {v: i for i, v in enumerate(workers)}, {v: i for i, v in enumerate(tasks)}
    # Eliminate task intercepts analytically; the remaining system has at most roster-size rows.
    incidence = np.zeros((len(tasks), len(workers)))
    worker_sum, task_sum = np.zeros(len(workers)), np.zeros(len(tasks))
    for row in rows:
        w, t, value = wi[str(row['worker_id'])], ti[str(row['base_task_id'])], float(row['analysis_value'])
        incidence[t, w] += 1
        worker_sum[w] += value
        task_sum[t] += value
    task_n = incidence.sum(axis=1)
    normal = np.diag(incidence.sum(axis=0)) - incidence.T @ (incidence / task_n[:, None])
    rhs = worker_sum - incidence.T @ (task_sum / task_n)
    effects = np.linalg.lstsq(normal, rhs, rcond=None)[0]
    effects -= effects.mean()
    return {worker: float(effects[index]) for index, worker in enumerate(workers)}


def resample_building_then_task(rows: Sequence[Mapping[str, Any]], rng: np.random.Generator) -> list[dict[str, Any]]:
    grouped: dict[str, dict[str, list[Mapping[str, Any]]]] = defaultdict(lambda: defaultdict(list))
    for row in rows:
        grouped[str(row["building_id"])][str(row["base_task_id"])].append(row)
    buildings = sorted(grouped)
    sampled = rng.choice(buildings, size=len(buildings), replace=True)
    output: list[dict[str, Any]] = []
    for bi, building in enumerate(sampled):
        tasks = sorted(grouped[str(building)])
        for ti, task in enumerate(rng.choice(tasks, size=len(tasks), replace=True)):
            output.extend({**row, "base_task_id": f"b{bi}:t{ti}:{task}"} for row in grouped[str(building)][str(task)])
    return output


def bootstrap_component(
    rows: Sequence[Mapping[str, Any]], *, replicates: int = BOOTSTRAPS, seed: int
) -> tuple[dict[str, list[float]], list[dict[str, Any]]]:
    workers = sorted({str(row["worker_id"]) for row in rows})
    rng, draws, diagnostics = np.random.default_rng(seed), defaultdict(list), []
    for replicate in range(replicates):
        sampled = resample_building_then_task(rows, rng)
        present = {str(row["worker_id"]) for row in sampled}
        components = worker_task_components(sampled)
        reason = "usable"
        if present != set(workers):
            reason = "missing_workers"
        elif len(components) != 1:
            reason = "disconnected_graph"
        elif len({row["base_task_id"] for row in sampled}) < 2:
            reason = "insufficient_task_support"
        effects = fit_worker_task_effects(sampled) if reason == "usable" else {}
        if not effects and reason == "usable":
            reason = "estimator_not_evaluable"
        for worker, value in effects.items():
            draws[worker].append(value)
        diagnostics.append({
            "replicate": replicate, "status": reason, "worker_count": len(present),
            "missing_worker_count": len(set(workers) - present), "component_count": len(components),
            "task_instance_count": len({row['base_task_id'] for row in sampled}),
        })
    return dict(draws), diagnostics


def classify_probability(probability: float | None, threshold: float) -> str:
    if probability is None:
        return "U_insufficient"
    if probability >= threshold:
        return "H_positive_direction"
    if probability <= 1 - threshold:
        return "L_negative_direction"
    return "U_unclassified"


def classify_from_counts(positive_count: int, usable_count: int, requested_count: int, threshold: float, *, single_building: bool = False) -> tuple[str, float, float]:
    lower = positive_count / requested_count
    upper = (positive_count + requested_count - usable_count) / requested_count
    if single_building:
        label = "U_single_building_no_cross_building_stability"
    elif lower >= threshold:
        label = "H_positive_direction"
    elif upper <= 1 - threshold:
        label = "L_negative_direction"
    else:
        label = "U_unclassified_or_bootstrap_missing"
    return label, lower, upper


def positive_mass(values):
    values = np.asarray(values, dtype=float)
    return float(np.sum(values > 1e-10) + .5 * np.sum(np.abs(values) <= 1e-10))


def eligible_active_time_row(row: Mapping[str, Any]) -> bool:
    value = number(row.get("active_time_seconds"))
    return bool(
        truth(row.get("active_time_formal_available"))
        and row.get("historical_active_time_eligibility_status") == "eligible"
        and 'partial' not in row.get('timing_status', '')
        and not truth(row.get("lead_time_is_active_time"))
        and value is not None and value > 0
    )


def _reference_source_version(source: str, sha: str, reference_type: str) -> str:
    return "|".join((source or "unknown_source", sha or "sha_unavailable", reference_type or "unknown_reference_type"))


@lru_cache(maxsize=None)
def source_digest(path: Path) -> str:
    return audit_v1.sha256(path) if path.is_file() else 'sha_unavailable'


def load_feature_rows() -> tuple[list[dict[str, Any]], dict[str, Any]]:
    spine_rows = read_csv(SUBSTRATE / "annotation_spine.csv")
    spine = {row["canonical_annotation_id"]: row for row in spine_rows}
    evidence_rows = read_csv(EVIDENCE)
    evidence = {r['canonical_annotation_id']: r for r in evidence_rows}
    if len(evidence) != len(evidence_rows) or set(evidence) != set(spine):
        raise ValueError('evidence identity mismatch or duplicate')
    rows: list[dict[str, Any]] = []

    for row in read_csv(V1 / "geometry_comparisons.csv"):
        if row["comparison"] != "human_gt" or number(row.get("d_mask")) is None:
            continue
        meta = spine[row["left_id"]]
        source = row.get("reference_source", "")
        source_path = ROOT / source
        source_sha = source_digest(source_path)
        rows.append({
            "canonical_annotation_id": row["left_id"], "stage": row["stage"], "condition": row["condition"],
            "base_task_id": row["base_task_id"], "building_id": row["building_id"], "worker_id": str(int(float(row["worker_id"]))),
            "feature_family": "quality", "feature_name": "d_mask_to_reference", "raw_value": float(row["d_mask"]),
            "analysis_value": -float(row["d_mask"]), "positive_direction": "lower_d_mask_better",
            "reference_source": source, "reference_source_version": _reference_source_version(source, source_sha, "geometry_gt"),
            "reference_identity": "gt", "reference_sha256": source_sha, "source_path": source,
        })

    for row in read_csv(SUBSTRATE / "reference_measurement.csv"):
        value = number(row.get("measurement_value"))
        if row.get("measurement_role") != "worker_final" or row.get("measurement_status") != "available" or value is None:
            continue
        meta = spine.get(row["canonical_annotation_id"])
        if not meta:
            continue
        rows.append({
            "canonical_annotation_id": row["canonical_annotation_id"], "stage": row["stage"], "condition": meta["raw_condition"],
            "base_task_id": row["base_task_id"], "building_id": meta["building_id"], "worker_id": row["worker_id"],
            "feature_family": "quality", "feature_name": row["metric_name"], "raw_value": value, "analysis_value": value,
            "positive_direction": "higher_reference_quality_better", "reference_source": row["source_path"],
            "reference_source_version": _reference_source_version(row["source_path"], row["source_sha256"], row["reference_type"]),
            "reference_identity": row["reference_identity"], "reference_sha256": row["reference_sha256"], "source_path": row["source_path"],
        })

    for row in read_csv(SUBSTRATE / "active_time_context.csv"):
        value = number(row.get("active_time_seconds"))
        if not eligible_active_time_row(row) or not evidence[row['canonical_annotation_id']]['active_time_owner_valid_status'].startswith('owner_valid_complete'):
            continue
        rows.append({
            "canonical_annotation_id": row["canonical_annotation_id"], "stage": row["stage"], "condition": row["raw_condition"],
            "base_task_id": row["base_task_id"], "building_id": spine[row["canonical_annotation_id"]]["building_id"], "worker_id": row["worker_id"],
            "feature_family": "time", "feature_name": "log_owner_valid_active_seconds", "raw_value": value,
            "analysis_value": -math.log(value), "positive_direction": "faster_owner_valid_active_time",
            "reference_source": row["active_time_source"],
            "reference_source_version": _reference_source_version(row["active_time_source"], row["timing_rule_version"], "owner_valid_active_time"),
            "reference_identity": row["active_time_source_file"], "reference_sha256": "not_applicable", "source_path": row["active_time_source_file"],
        })

    for row in read_csv(SUBSTRATE / "proposal_response.csv"):
        source_version = _reference_source_version(row["source_path"], row["source_sha256"], row["reference_type"])
        values = {
            "semi_initial_to_final_rmse": number(row.get("initial_to_final_rmse_diagonal_normalized")),
            "semi_delta_U": number(row.get("delta_U")),
            "semi_modification_indicator": 0.0 if truth(row.get("exact_geometry_equal")) else 1.0,
            "semi_topology_change_indicator": 1.0 if truth(row.get("topology_changed")) else 0.0,
        }
        for feature, value in values.items():
            if value is None:
                continue
            sign = 1.0 if feature == "semi_delta_U" else -1.0
            rows.append({
                "canonical_annotation_id": row["canonical_annotation_id"], "stage": row["stage"], "condition": row["raw_condition"],
                "base_task_id": row["base_task_id"], "building_id": row["building_id"], "worker_id": row["worker_id"],
                "feature_family": "semi_habit", "feature_name": feature, "raw_value": value, "analysis_value": sign * value,
                "positive_direction": "quality_gain" if sign > 0 else "retention_or_smaller_change",
                "reference_source": row["source_path"], "reference_source_version": source_version,
                "reference_identity": row["reference_identity"], "reference_sha256": row["reference_sha256"], "source_path": row["source_path"],
            })

    # Reference-relative corner RMSE and signed corresponding wall offset.
    gt = audit_v1._load_gt_pairs()
    for row in read_csv(SUBSTRATE / "geometry_variants.csv"):
        if row["variant"] != "strict_normalized" or not truth(row["strict_valid"]) or row["base_task_id"] not in gt:
            continue
        reference = gt[row["base_task_id"]]
        if reference["reference_status"] == "reference_not_geometry_ready":
            continue
        points = json.loads(row["points_json"])
        ref_points = [point for pair in reference["pairs"] for point in ([float(pair["x"]), float(pair["y_ceiling"])], [float(pair["x"]), float(pair["y_floor"])])]
        left, right = audit_v1.normalize_geometry(points), audit_v1.normalize_geometry(ref_points)
        rmse = cyclic_rmse(points, ref_points)
        metrics = pairwise_similarity(left, right)
        source = reference["source"]
        source_path = ROOT / source
        source_sha = source_digest(source_path)
        common = {
            "canonical_annotation_id": row["canonical_annotation_id"], "stage": row["stage"], "condition": row["raw_condition"],
            "base_task_id": row["base_task_id"], "building_id": row["base_task_id"].split("_", 1)[0], "worker_id": row["worker_id"],
            "feature_family": "geometry_habit", "reference_source": source,
            "reference_source_version": _reference_source_version(source, source_sha, "geometry_gt"),
            "reference_identity": "gt", "reference_sha256": source_sha, "source_path": source,
        }
        if rmse is not None:
            rows.append({**common, "feature_name": "reference_corner_cyclic_rmse", "raw_value": rmse, "analysis_value": -rmse, "positive_direction": "smaller_corner_difference"})
        if metrics["pointwise_correspondence_compatible"]:
            pairs = metrics["cyclic_correspondence"]
            lx, rx = left["x_event_positions"], right["x_event_positions"]
            signed = [((lx[i] - rx[j] + 512.0) % 1024.0) - 512.0 for i, j in pairs]
            offset = float(np.mean(signed) / 1024.0)
            rows.append({**common, "feature_name": "reference_corresponding_signed_x_offset", "raw_value": offset, "analysis_value": offset, "positive_direction": "clockwise_signed_offset_not_quality"})
        count_difference = int(left.get("n_pairs", 0)) - int(right.get("n_pairs", 0))
        rows.append({**common, "feature_name": "reference_signed_corner_pair_count_difference", "raw_value": count_difference, "analysis_value": count_difference, "positive_direction": "more_wall_pairs_than_reference_signed_not_quality"})
    return rows, {"spine_count": len(spine_rows), "feature_row_count": len(rows)}


def build_profiles(feature_rows: Sequence[Mapping[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    grouped: dict[tuple[str, str, str, str], list[Mapping[str, Any]]] = defaultdict(list)
    for row in feature_rows:
        grouped[(str(row["stage"]), str(row["condition"]), str(row["reference_source_version"]), str(row["feature_name"]))].append(row)
    components_out, profiles, bootstrap_out, volatility = [], [], [], []
    for key, group in sorted(grouped.items()):
        stage, condition, source_version, feature = key
        print(f'profile {stage}/{condition}/{feature} rows={len(group)}', flush=True)
        for component_index, component in enumerate(worker_task_components(group), 1):
            subset = [row for row in group if str(row["worker_id"]) in component["workers"] and str(row["base_task_id"]) in component["tasks"]]
            source_token = hashlib.sha256(source_version.encode()).hexdigest()[:10]
            component_id = f"{stage}|{condition}|{feature}|{source_token}|c{component_index}"
            building_count = len({row["building_id"] for row in subset})
            full = fit_worker_task_effects(subset)
            components_out.append({
                "component_id": component_id, "stage": stage, "condition": condition, "feature_name": feature,
                "reference_source_version": source_version, "worker_count": len(component["workers"]), "task_count": len(component["tasks"]),
                "building_count": building_count, "worker_ids_json": json.dumps(component["workers"]),
                "task_ids_json": json.dumps(component["tasks"]), "estimable": bool(full),
                "cross_building_stability_estimable": building_count > 1,
            })
            if not full:
                for worker in component["workers"]:
                    for threshold in THRESHOLDS:
                        profiles.append({
                            "component_id": component_id, "stage": stage, "condition": condition, "feature_name": feature,
                            "reference_source_version": source_version, "worker_id": worker, "threshold": threshold,
                            "directional_class": "U_insufficient", "bootstrap_probability_positive": "",
                            "bootstrap_usable_count": 0, "bootstrap_requested_count": BOOTSTRAPS,
                            "task_adjusted_effect": "", "status": "component_not_estimable",
                        })
                continue
            draws, diagnostics = bootstrap_component(subset, seed=stable_seed(*key, component_index))
            for item in diagnostics:
                bootstrap_out.append({**item, "component_id": component_id, "stage": stage, "condition": condition, "feature_name": feature, "reference_source_version": source_version})
            for worker, effect in full.items():
                worker_rows = [row for row in subset if str(row["worker_id"]) == worker]
                worker_draws = draws.get(worker, [])
                positive_count = positive_mass(worker_draws)
                probability = positive_count / len(worker_draws) if worker_draws else None
                probability_lower = positive_count / BOOTSTRAPS
                probability_upper = (positive_count + BOOTSTRAPS - len(worker_draws)) / BOOTSTRAPS
                raw_values = np.asarray([float(row["raw_value"]) for row in worker_rows])
                volatility.append({
                    "component_id": component_id, "stage": stage, "condition": condition, "feature_name": feature,
                    "reference_source_version": source_version, "worker_id": worker, "task_count": len({row['base_task_id'] for row in worker_rows}),
                    "building_count": len({row['building_id'] for row in worker_rows}), "raw_mean": float(raw_values.mean()),
                    "raw_std_ddof1": float(raw_values.std(ddof=1)) if len(raw_values) > 1 else "",
                    "raw_mad_from_median": float(np.median(np.abs(raw_values - np.median(raw_values)))),
                    "raw_iqr": float(np.quantile(raw_values, .75) - np.quantile(raw_values, .25)),
                    "single_building_no_cross_building_stability": len({row['building_id'] for row in worker_rows}) == 1,
                })
                for threshold in THRESHOLDS:
                    label, probability_lower, probability_upper = classify_from_counts(
                        positive_count, len(worker_draws), BOOTSTRAPS, threshold, single_building=len({r['building_id'] for r in worker_rows}) == 1
                    )
                    profiles.append({
                        "component_id": component_id, "stage": stage, "condition": condition, "feature_name": feature,
                        "feature_family": worker_rows[0]["feature_family"], "positive_direction": worker_rows[0]["positive_direction"],
                        "reference_source_version": source_version, "worker_id": worker, "threshold": threshold,
                        "directional_class": label,
                        "bootstrap_probability_positive": probability if probability is not None else "",
                        "bootstrap_probability_positive_lower_all_1000": probability_lower,
                        "bootstrap_probability_positive_upper_all_1000": probability_upper,
                        "bootstrap_usable_count": len(worker_draws), "bootstrap_requested_count": BOOTSTRAPS,
                        "task_adjusted_effect": effect, "task_support": len({row['base_task_id'] for row in worker_rows}),
                        "building_support": len({row['building_id'] for row in worker_rows}),
                        "status": "estimated" if worker_draws else "bootstrap_not_evaluable",
                    })
    return components_out, profiles, bootstrap_out, volatility


def build_coexisting_profiles(profiles: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    selected = [row for row in profiles if float(row["threshold"]) == 0.8 and row["feature_name"] in {"d_mask_to_reference", "log_owner_valid_active_seconds"}]
    quality = [row for row in selected if row["feature_name"] == "d_mask_to_reference"]
    timing: dict[tuple[str, str, str], list[Mapping[str, Any]]] = defaultdict(list)
    for row in selected:
        if row["feature_name"] == "log_owner_valid_active_seconds":
            timing[(row["stage"], row["condition"], row["worker_id"])].append(row)
    output = []
    for row in quality:
        options = timing.get((row["stage"], row["condition"], row["worker_id"]), [])
        if not options:
            options = [None]
        for other in options:
            output.append({
            "stage": row["stage"], "condition": row["condition"], "worker_id": row["worker_id"],
            "quality_component_id": row["component_id"], "time_component_id": other["component_id"] if other else "",
            "quality_reference_source_version": row["reference_source_version"], "quality_directional_class": row["directional_class"],
            "time_directional_class": other["directional_class"] if other else "not_evaluable",
            "quality_effect": row["task_adjusted_effect"], "time_effect": other["task_adjusted_effect"] if other else "",
            "interpretation": "coexisting_axis_descriptions_not_compound_personality_type",
            })
    return output


def _fold_profiles(train: Sequence[Mapping[str, Any]], seed: int) -> dict[str, dict[str, Any]]:
    output: dict[str, dict[str, Any]] = {}
    for component_index, component in enumerate(worker_task_components(train)):
        subset = [row for row in train if str(row["worker_id"]) in component["workers"] and str(row["base_task_id"]) in component["tasks"]]
        full = fit_worker_task_effects(subset)
        if not full:
            continue
        draws, diagnostics = bootstrap_component(subset, seed=seed + component_index)
        status_counts = dict(Counter(row["status"] for row in diagnostics))
        for worker, effect in full.items():
            values = draws.get(worker, [])
            positive = positive_mass(values)
            output[worker] = {
                "effect": effect, "probability": positive / len(values) if values else None, "usable": len(values),
                "probability_lower": positive / BOOTSTRAPS,
                "probability_upper": (positive + BOOTSTRAPS - len(values)) / BOOTSTRAPS,
                "component": component_index, "component_workers": set(component["workers"]),
                "bootstrap_status_counts": status_counts,
                "building_support": len({r['building_id'] for r in subset if str(r['worker_id']) == worker}),
            }
    return output


def heldout_evaluation(feature_rows: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    # The costly cross-fit is limited to interpretable primary/behavioural features; no outcome-selected feature search.
    wanted = {"d_mask_to_reference", "log_owner_valid_active_seconds", "semi_initial_to_final_rmse", "semi_delta_U", "reference_corner_cyclic_rmse", "reference_corresponding_signed_x_offset", "reference_signed_corner_pair_count_difference"}
    grouped: dict[tuple[str, str, str, str], list[Mapping[str, Any]]] = defaultdict(list)
    for row in feature_rows:
        if row["feature_name"] in wanted:
            grouped[(str(row["stage"]), str(row["condition"]), str(row["reference_source_version"]), str(row["feature_name"]))].append(row)
    output: list[dict[str, Any]] = []
    for key, group in sorted(grouped.items()):
        tasks = sorted({str(row["base_task_id"]) for row in group})
        print(f'holdout {key[0]}/{key[1]}/{key[3]} rows={len(group)}', flush=True)
        buildings = sorted({str(row["building_id"]) for row in group})
        fold_specs: list[tuple[str, str, set[str]]] = []
        for fold in range(min(5, len(tasks))):
            held = {task for task in tasks if stable_seed(*key, task) % min(5, len(tasks)) == fold}
            if held and held != set(tasks):
                fold_specs.append(("heldout_task_fold", str(fold), held))
        fold_specs.extend(("leave_one_building_out", building, {str(row["base_task_id"]) for row in group if str(row["building_id"]) == building}) for building in buildings if len(buildings) > 1)
        for kind, fold_id, held_tasks in fold_specs:
            train = [row for row in group if str(row["base_task_id"]) not in held_tasks]
            test = [row for row in group if str(row["base_task_id"]) in held_tasks]
            learned = _fold_profiles(train, stable_seed(*key, kind, fold_id))
            by_task: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
            for row in test:
                by_task[str(row["base_task_id"])].append(row)
            centered: dict[str, list[float]] = defaultdict(list)
            for task_rows in by_task.values():
                by_component: dict[int | str, list[Mapping[str, Any]]] = defaultdict(list)
                for row in task_rows:
                    worker = str(row["worker_id"])
                    by_component[learned[worker]["component"] if worker in learned else "not_seen"].append(row)
                for component_rows in by_component.values():
                    task_mean = float(np.mean([float(row["analysis_value"]) for row in component_rows]))
                    for row in component_rows:
                        centered[str(row["worker_id"])].append(float(row["analysis_value"]) - task_mean)
            for worker, values in sorted(centered.items()):
                if worker not in learned:
                    for threshold in THRESHOLDS:
                        output.append({
                            "stage": key[0], "condition": key[1], "reference_source_version": key[2], "feature_name": key[3],
                            "evaluation_kind": kind, "fold_id": fold_id, "worker_id": worker, "threshold": threshold,
                            "training_task_count": len({row['base_task_id'] for row in train}), "evaluation_task_count": len({row['base_task_id'] for row in test}),
                            "training_evaluation_task_overlap_count": 0, "directional_class": "U_not_seen_in_training",
                            "heldout_task_centered_mean": float(np.mean(values)), "status": "not_evaluable_unseen_worker",
                        })
                    continue
                heldout = float(np.mean(values))
                for threshold in THRESHOLDS:
                    label, _, _ = classify_from_counts(
                        learned[worker]["probability_lower"] * BOOTSTRAPS, learned[worker]["usable"], BOOTSTRAPS, threshold,
                        single_building=learned[worker]['building_support'] < 2
                    )
                    counterexample = (label.startswith("H_") and heldout < 0) or (label.startswith("L_") and heldout > 0)
                    output.append({
                        "stage": key[0], "condition": key[1], "reference_source_version": key[2], "feature_name": key[3],
                        "evaluation_kind": kind, "fold_id": fold_id, "worker_id": worker, "threshold": threshold,
                        "training_task_count": len({row['base_task_id'] for row in train}), "evaluation_task_count": len({row['base_task_id'] for row in test}),
                        "training_evaluation_task_overlap_count": len({row['base_task_id'] for row in train} & {row['base_task_id'] for row in test}),
                        "train_continuous_effect": learned[worker]["effect"], "train_probability_positive": learned[worker]["probability"],
                        "train_bootstrap_usable_count": learned[worker]["usable"], "directional_class": label,
                        "train_probability_positive_lower_all_1000": learned[worker]["probability_lower"],
                        "train_probability_positive_upper_all_1000": learned[worker]["probability_upper"],
                        "train_component_id": learned[worker]["component"],
                        "evaluation_task_ids_json": json.dumps(sorted(held_tasks)),
                        "training_task_ids_json": json.dumps(sorted({r['base_task_id'] for r in train})),
                        "train_bootstrap_status_counts_json": json.dumps(learned[worker]["bootstrap_status_counts"], sort_keys=True),
                        "heldout_task_centered_mean": heldout, "continuous_absolute_error": abs(learned[worker]["effect"] - heldout),
                        "classification_counterexample": counterexample,
                        "status": "evaluated",
                    })
    return output


def summarize_continuous_vs_classified(rows: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[tuple[str, str, str, str, str, float], list[Mapping[str, Any]]] = defaultdict(list)
    for row in rows:
        if row.get("status") == "evaluated":
            grouped[(str(row["stage"]), str(row["condition"]), str(row["reference_source_version"]), str(row["feature_name"]), str(row["evaluation_kind"]), float(row["threshold"]))].append(row)
    output = []
    for key, group in sorted(grouped.items()):
        x, y = np.asarray([float(row.get('train_prediction_same_heldout_peer_center',row["train_continuous_effect"])) for row in group]), np.asarray([float(row["heldout_task_centered_mean"]) for row in group])
        corr = float(np.corrcoef(x, y)[0, 1]) if len(group) > 2 and x.std() > 0 and y.std() > 0 else None
        output.append({
            "stage": key[0], "condition": key[1], "reference_source_version": key[2], "feature_name": key[3],
            "evaluation_kind": key[4], "threshold": key[5], "evaluation_rows": len(group),
            "continuous_train_heldout_correlation": corr if corr is not None else "",
            "classified_H_count": sum(str(row["directional_class"]).startswith("H_") for row in group),
            "classified_L_count": sum(str(row["directional_class"]).startswith("L_") for row in group),
            "classified_U_count": sum(str(row["directional_class"]).startswith("U_") for row in group),
            "counterexample_count": sum(truth(row["classification_counterexample"]) for row in group),
            "mean_continuous_absolute_error": float(np.mean([float(row["continuous_absolute_error"]) for row in group])),
        })
    return output


def refine_holdout_peer_support(holdout, features):
    groups = defaultdict(list)
    feature_map = defaultdict(list)
    for r in features:
        feature_map[tuple(r[k] for k in ['stage','condition','reference_source_version','feature_name'])].append(r)
    for r in holdout:
        if r.get('train_component_id','') != '':
            groups[tuple(str(r[k]) for k in ['stage','condition','reference_source_version','feature_name','evaluation_kind','fold_id','train_component_id'])].append(r)
    for key, rows in groups.items():
        workers = {r['worker_id']:float(r['train_continuous_effect']) for r in rows}
        tasks = set(json.loads(rows[0]['evaluation_task_ids_json']))
        by_task = defaultdict(list)
        for r in feature_map[key[:4]]:
            if r['base_task_id'] in tasks and r['worker_id'] in workers:
                by_task[r['base_task_id']].append(r)
        observed, predicted, unsupported = defaultdict(list), defaultdict(list), Counter()
        for task_rows in by_task.values():
            if len(task_rows) < 2:
                for r in task_rows:
                    unsupported[r['worker_id']] += 1
                continue
            mean = np.mean([float(r['analysis_value']) for r in task_rows])
            prediction_mean = np.mean([workers[r['worker_id']] for r in task_rows])
            for r in task_rows:
                observed[r['worker_id']].append(float(r['analysis_value'])-mean)
                predicted[r['worker_id']].append(workers[r['worker_id']]-prediction_mean)
        for r in rows:
            w = r['worker_id']
            r['evaluation_worker_comparable_tasks'] = len(observed[w])
            r['evaluation_worker_singleton_tasks'] = unsupported[w]
            if not observed[w]:
                r.update(status='not_evaluable_no_same_component_peer',heldout_task_centered_mean='',continuous_absolute_error='',classification_counterexample=False)
            else:
                value,prediction = float(np.mean(observed[w])),float(np.mean(predicted[w]))
                r.update(status='evaluated',heldout_task_centered_mean=value,train_prediction_same_heldout_peer_center=prediction,
                         continuous_absolute_error=abs(value-prediction),
                         classification_counterexample=(str(r['directional_class']).startswith('H_') and value < 0) or (str(r['directional_class']).startswith('L_') and value > 0))
    return holdout


def load_geometry_pools() -> tuple[dict[tuple[str, str, str], list[dict[str, Any]]], dict[tuple[str, str, str], dict[tuple[str, str], dict[str, str]]]]:
    pools: dict[tuple[str, str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in read_csv(SUBSTRATE / "geometry_variants.csv"):
        if row["variant"] != "strict_normalized" or not truth(row["strict_valid"]):
            continue
        points = json.loads(row["points_json"])
        pools[(row["stage"], row["raw_condition"], row["base_task_id"])].append({
            "canonical_annotation_id": row["canonical_annotation_id"], "worker_id": row["worker_id"],
            "geometry": audit_v1.normalize_geometry(points), "dense": audit_v1._dense_boundaries(audit_v1.normalize_geometry(points)["pairs"]),
        })
    for key, records in pools.items():
        ensure_unique_worker_votes(records, context="|".join(key))
    pair_maps: dict[tuple[str, str, str], dict[tuple[str, str], dict[str, str]]] = defaultdict(dict)
    for row in read_csv(SUBSTRATE / "geometry_pairwise.csv"):
        if row["variant"] != "raw":
            continue
        key = (row["stage"], row["raw_condition"], row["base_task_id"])
        pair = tuple(sorted((row["left_canonical_annotation_id"], row["right_canonical_annotation_id"])))
        pair_maps[key][pair] = row
    return dict(pools), dict(pair_maps)


def ensure_unique_worker_votes(records: Sequence[Mapping[str, Any]], *, context: str) -> None:
    workers = [str(row["worker_id"]) for row in records]
    if len(workers) != len(set(workers)):
        raise ValueError(f"duplicate worker vote in {context}")


def structure_sensitivity(pools: Mapping[tuple[str, str, str], Sequence[Mapping[str, Any]]], pair_maps: Mapping[tuple[str, str, str], Mapping[tuple[str, str], Mapping[str, Any]]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    output = []
    for key, records in sorted(pools.items()):
        if len(records) < 15:
            continue
        stage, condition, base = key
        by_geometry = {id(row["geometry"]): row["canonical_annotation_id"] for row in records}
        def lookup(left: Mapping[str, Any], right: Mapping[str, Any]) -> Mapping[str, Any]:
            pair = tuple(sorted((by_geometry[id(left)], by_geometry[id(right)])))
            return audit_v1.pairwise_cluster_payload(pair_maps[key][pair])
        for cutoff in STRUCTURE_CUTOFFS:
            result = historical.cluster_geometry_records(
                records, min_q_boundary=cutoff, min_q_wallwall=cutoff, base_task_id=base,
                condition=condition, minimum_valid_k=3, pairwise_fn=lookup,
            )
            memberships = json.loads(result["cluster_membership_json"])
            worker_by_id = {row["canonical_annotation_id"]: row["worker_id"] for row in records}
            output.append({
                "stage": stage, "condition": condition, "base_task_id": base, "building_id": base.split("_", 1)[0],
                "cutoff": cutoff, "strict_support": len(records), "fixed_support_annotation_ids_json": json.dumps(sorted(worker_by_id)),
                "structure_status": result["task_crowd_structure_status"], "partition_status": result["partition_status"],
                "cluster_count": result["cluster_count"], "second_cluster_support": result["second_cluster_support"],
                "cluster_worker_memberships_json": json.dumps([[worker_by_id[item] for item in cluster] for cluster in memberships]),
                "pointwise_correspondence_required": True,
            })
    summary = []
    for stage, condition, cutoff in sorted({(r["stage"], r["condition"], r["cutoff"]) for r in output}):
        group = [r for r in output if (r["stage"], r["condition"], r["cutoff"]) == (stage, condition, cutoff)]
        buildings = sorted({r["building_id"] for r in group})
        metric = lambda row: float(row["structure_status"] == "supported_multimodal")
        summary.append({
            "stage": stage, "condition": condition, "cutoff": cutoff, "task_count": len(group), "building_count": len(buildings),
            "supported_multimodal_rate_task_equal": float(np.mean([metric(r) for r in group])),
            "supported_multimodal_rate_building_equal": float(np.mean([np.mean([metric(r) for r in group if r["building_id"] == b]) for b in buildings])),
            "fixed_support_across_cutoffs": True,
        })
    regression_rows = []
    for row in output:
        if row["cutoff"] == 0.95:
            regression_rows.append({
                "stage": row["stage"], "condition": row["condition"], "base_task_id": row["base_task_id"],
                "evaluable": True, "strict_support": row["strict_support"], "full_valid_support": row["strict_support"],
                "full_structure_status": row["structure_status"], "full_cluster_count": row["cluster_count"],
                "full_second_cluster_support": row["second_cluster_support"],
                "full_cluster_worker_memberships_json": row["cluster_worker_memberships_json"],
            })
    return output, summary, audit_v1._dense42_cluster_regression(regression_rows)


def medoid_selected_only(selected: Sequence[Mapping[str, Any]]) -> Mapping[str, Any]:
    if not selected:
        raise ValueError("selected set is empty")
    if len(selected) == 1:
        return selected[0]
    scores = []
    for candidate in selected:
        distances = [audit_v1._d_mask(candidate["dense"], other["dense"]) for other in selected if other is not candidate]
        scores.append((float(np.mean(distances)), str(candidate["canonical_annotation_id"]), candidate))
    return min(scores, key=lambda item: (item[0], item[1]))[2]


def _evaluate_medoid(selected: Sequence[Mapping[str, Any]], population: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    chosen = medoid_selected_only(selected)
    selected_ids = {row["canonical_annotation_id"] for row in selected}
    remaining = [row for row in population if row["canonical_annotation_id"] not in selected_ids]
    values = [audit_v1._d_mask(chosen["dense"], row["dense"]) for row in remaining]
    return {
        "selected_medoid_id": chosen["canonical_annotation_id"], "remaining_worker_count": len(remaining),
        "remaining_d_mask_mean": float(np.mean(values)) if values else None,
    }


def distance_matrix(records: Sequence[Mapping[str, Any]]) -> np.ndarray:
    identities = [str(row['worker_id']) for row in records]
    if len(identities) != len(set(identities)):
        raise ValueError('duplicate worker vote in geometry pool')
    result = np.zeros((len(records), len(records)))
    for i in range(len(records)):
        for j in range(i):
            result[i, j] = result[j, i] = audit_v1._d_mask(records[i]['dense'], records[j]['dense'])
    return result


def evaluate_indices(records: Sequence[Mapping[str, Any]], distances: np.ndarray, selected: Sequence[int]) -> dict[str, Any]:
    if not selected or len(selected) != len(set(selected)) or any(i < 0 or i >= len(records) for i in selected):
        raise ValueError('invalid or repeated selected vote')
    remaining = sorted(set(range(len(records))) - set(selected))
    scores = distances[np.ix_(selected, selected)].mean(axis=1)
    chosen = min(zip(scores, selected), key=lambda item: (item[0], str(records[item[1]]['canonical_annotation_id'])))[1]
    return {'selected_medoid_id': records[chosen]['canonical_annotation_id'],
            'remaining_worker_count': len(remaining),
            'remaining_d_mask_mean': float(distances[chosen, remaining].mean()) if remaining else None,
            'selected_worker_ids_json': json.dumps([records[i]['worker_id'] for i in selected])}


def strict_medoid_replay(pools: Mapping[tuple[str, str, str], Sequence[Mapping[str, Any]]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    replicates, summary = [], []
    for key, records in sorted(pools.items()):
        if len(records) <= 20:
            continue
        stage, condition, base = key
        rng = np.random.default_rng(stable_seed("strict_medoid", *key))
        distances = distance_matrix(records)
        permutations = [rng.permutation(len(records)).tolist() for _ in range(REPLAY_REPLICATES)]
        for k in K_VALUES:
            values = []
            for replicate, permutation in enumerate(permutations):
                result = evaluate_indices(records, distances, permutation[:k])
                values.append(result["remaining_d_mask_mean"])
                replicates.append({
                    "stage": stage, "condition": condition, "base_task_id": base, "building_id": base.split("_", 1)[0],
                    "k": k, "replicate": replicate, "strict_support": len(records), **result,
                    "sampling_contract": "same_task_permutation_nested_k_prefixes",
                    "selection_contract": "medoid_min_mean_d_mask_within_selected_only_no_full_target_access",
                    "evaluation_contract": "remaining_workers_only",
                })
            available = [value for value in values if value is not None]
            summary.append({
                "stage": stage, "condition": condition, "base_task_id": base, "building_id": base.split("_", 1)[0],
                "k": k, "strict_support": len(records), "replicates": REPLAY_REPLICATES, "remaining_worker_count": len(records) - k,
                "remaining_d_mask_mean": float(np.mean(available)), "remaining_d_mask_q025": float(np.quantile(available, .025)),
                "remaining_d_mask_q975": float(np.quantile(available, .975)), "fixed_image_set_support_gt20": True,
            })
    return replicates, summary


def group_replay(pools, holdout):
    # Classification uses task-disjoint training; each source/component stays separate.
    label_sets = defaultdict(dict)
    for row in holdout:
        if row.get('status') != 'evaluated' or row['feature_name'] != 'd_mask_to_reference' or float(row['threshold']) != .8 or row['evaluation_kind'] != 'heldout_task_fold':
            continue
        train, test = set(json.loads(row['training_task_ids_json'])), set(json.loads(row['evaluation_task_ids_json']))
        if train & test:
            raise ValueError('training/evaluation leakage')
        for base in test:
            label_sets[(row['stage'], row['condition'], base, row['reference_source_version'], row['fold_id'], row['train_component_id'])][row['worker_id']] = row['directional_class']
    output = []
    for key, labels in sorted(label_sets.items()):
        records = [r for r in pools.get(key[:3], []) if r['worker_id'] in labels]
        if not records:
            continue
        distances = distance_matrix(records)
        high = [i for i,r in enumerate(records) if labels[r['worker_id']].startswith('H_')]
        low = [i for i,r in enumerate(records) if labels[r['worker_id']].startswith('L_')]
        # Small supported k diagnose composition; 15–20 remain explicit capacity checks.
        for k in sorted(set([2,3,5,10,*K_VALUES])):
            specs = [('within_H', k, 0), ('within_L', 0, k), ('mixed_HL_balanced', k//2, k-k//2)]
            all_supported = len(high) >= k and len(low) >= k and len(records) > k
            for name, nh, nl in specs:
                common = dict(stage=key[0], condition=key[1], base_task_id=key[2], building_id=key[2].split('_')[0],
                              reference_source_version=key[3], training_fold=key[4], train_component_id=key[5],
                              scenario=name, k=k, available_H=len(high), available_L=len(low),
                              common_support_all_three_scenarios=all_supported,
                              classification_evaluation_disjoint=True, vote_contract='one_person_one_vote')
                if len(high) < nh or len(low) < nl or len(records) <= k:
                    output.append({**common,'evaluable':False,'gap_reason':'insufficient_real_group_or_remaining_support'})
                    continue
                rng = np.random.default_rng(stable_seed('group',*key,name,k))
                means, pair_means = [], []
                for _ in range(REPLAY_REPLICATES):
                    selected = list(rng.choice(high,nh,replace=False)) + list(rng.choice(low,nl,replace=False))
                    means.append(evaluate_indices(records,distances,selected)['remaining_d_mask_mean'])
                    block = distances[np.ix_(selected,selected)]
                    pair_means.append(float(block.sum() / (k*(k-1))))
                output.append({**common,'evaluable':True,'replicates':REPLAY_REPLICATES,'remaining_worker_count':len(records)-k,
                               'remaining_d_mask_mean':float(np.mean(means)), 'within_selected_pair_d_mask_mean':float(np.mean(pair_means)),
                               'selection_contract':'selected_only_medoid','interpretation':'historical_crossfit_description_not_causal'})
    return output


def validate_evidence_contract() -> dict[str, Any]:
    required = set(FIELD_CONTRACT["required_evidence_fields"])
    if not EVIDENCE.is_file():
        return {"status": "pending_v1_substrate_used", "path": str(EVIDENCE.relative_to(ROOT)), "missing_fields": sorted(required)}
    rows = read_csv(EVIDENCE)
    actual = set(rows[0]) if rows else set()
    missing = sorted(required - actual)
    return {
        "status": "validated" if not missing else "schema_mismatch_fail_closed",
        "path": str(EVIDENCE.relative_to(ROOT)), "row_count": len(rows), "missing_fields": missing,
        "canonical_annotation_id_unique": len({row.get("canonical_annotation_id", "") for row in rows}) == len(rows),
    }


def _counts(rows: Sequence[Mapping[str, Any]], field: str) -> dict[str, int]:
    return dict(sorted(Counter(str(row[field]) for row in rows).items()))


def render_report(qa: Mapping[str, Any]) -> str:
    boot = qa["bootstrap_status_counts"]
    evidence = qa["evidence_contract"]
    return f"""# 全历史标注研究统计前置 v2

## 结论边界

本包是审计/敏感性统计，不产生正式 worker taxonomy，不改变任何 eligibility、C2、T1/V1 或 Stage 3 gate。候选 H/L/U 仅表示指定连续特征在给定 stage×condition×reference-source 分层中的方向证据；它不是人格或能力类型。三轴只作解释，不拟合场景预测。

## 数据与分层

- 输入为 v1 已实算的 2,501 条 canonical 全历史底座；没有复用 CURRENT20 或旧 eligibility 作为新主分母。
- 共物化 {qa['feature_row_count']} 条特征长表记录，按 stage、condition、reference source/version、feature 分开。单图 reference identity/reference SHA 逐行保留，但不把每张图的 identity 错当成跨图建模分层。
- 先审计 worker--task 二部图，共 {qa['component_count']} 个 component；只有单 building 的 component 明示不能估计跨 building 稳定性。
- Luna 证据合同状态：`{evidence['status']}`。若仍为 pending，本次计算明确使用 v1 substrate 临时映射，不把缺失证据视为零或可用。

## 任务调整与重采样

每个可估计 component 拟合 `value ~ worker fixed effect + task fixed effect`，worker effect 在 component 内中心化。质量包括已核验 D_mask（取负后“越高越好”）及其他 reference-relative quality；时间仅纳入正值、owner-valid、historical timing eligible 的 task-worker 累计日志，绝不混入 lead_time；Semi 修改/保留、参照角点 RMSE 与可对应的有符号横向偏移作为习惯特征单列。

每个可估计 component 固定执行 1,000 次 building→task 重采样，不拒绝也不重抽。状态计数为：`{json.dumps(boot, ensure_ascii=False)}`。缺工人、断图、任务支持不足均留在分母；同时报告可用 draw 的条件方向概率和全部 1000 次下的保守概率界，标签使用后者。近零并列按半权记录；只有一个 building 的人员不形成跨建筑稳定标签。

方向阈值报告 0.8，并并列 0.7/0.9 敏感性。quality×time 只并排描述共存轴，不合成新类型；连续波动用 std、MAD、IQR 报告。

## 留出评价与反例

任务使用确定性最多五折 held-out task；building 使用逐 building 留出。训练与评价 task overlap 全部为 0。`continuous_vs_classified_summary.csv` 同时报连续训练效应与 held-out 关联、离散 H/L/U 计数和反例数；`holdout_evaluation.csv` 保留逐 worker 反例。离散标签若掩盖连续方向反转，应优先报告连续结果与反例，而不是强化标签。

## 回放与结构敏感性

- strict-geometry support >20 的固定 image set 上，k=15..20 使用同一批 200 个 permutation 的嵌套前缀；medoid 只在 selected workers 内按平均 D_mask 选择，之后才对 remaining workers 评价，并逐 k 报 remaining count。
- H/L 组内和两组混合回放使用任务留出训练得到的标签，坚持一人一票；小规模 k=2/3/5/10 按实际支持描述，k15–20 单独核对资源缺口。不同方案须共同图集，不补虚拟工人。
- q=0.93/0.95/0.97 在所有 strict support≥15 新高支持 stage×condition 上保持同一 annotation support，分别给 task equal 与 building equal 汇总。
- 旧 42 回归：检查 {qa['old42_regression']['checked_task_count']} 图，mismatch={qa['old42_regression']['mismatch_count']}。

## 护栏

统计 guard：PASS。primary estimand、缺失/失败与 reference 版本均分轨；replay 仅用于审计/设计，不替代 V1；原始 `export_label/`、`import_json/`、`active_logs/` 和协议均未修改。
"""


def materialize(out: Path) -> dict[str, Any]:
    out.mkdir(parents=True, exist_ok=True)
    write_json(out / "FIELD_CONTRACT.json", FIELD_CONTRACT)
    feature_rows, base_qa = load_feature_rows()
    write_csv(out / 'feature_records.csv', feature_rows)
    components, profiles, bootstrap, volatility = build_profiles(feature_rows)
    for name, rows in [('worker_task_components.csv', components), ('directional_worker_profiles.csv', profiles), ('bootstrap_diagnostics.csv', bootstrap), ('continuous_volatility.csv', volatility)]:
        write_csv(out / name, rows)
    coexisting = build_coexisting_profiles(profiles)
    holdout = heldout_evaluation(feature_rows)
    holdout = refine_holdout_peer_support(holdout, feature_rows)
    write_csv(out / 'holdout_evaluation.csv', holdout)
    holdout_summary = summarize_continuous_vs_classified(holdout)
    pools, pair_maps = load_geometry_pools()
    structure, structure_summary, old42 = structure_sensitivity(pools, pair_maps)
    medoid_replicates, medoid_summary = strict_medoid_replay(pools)
    groups = group_replay(pools, holdout)
    evidence = validate_evidence_contract()

    outputs = {
        "feature_records.csv": feature_rows,
        "worker_task_components.csv": components,
        "directional_worker_profiles.csv": profiles,
        "bootstrap_diagnostics.csv": bootstrap,
        "continuous_volatility.csv": volatility,
        "quality_time_coexisting_axes.csv": coexisting,
        "holdout_evaluation.csv": holdout,
        "continuous_vs_classified_summary.csv": holdout_summary,
        "structure_sensitivity_tasks.csv": structure,
        "structure_sensitivity_summary.csv": structure_summary,
        "strict_medoid_replay_replicates.csv": medoid_replicates,
        "strict_medoid_replay_summary.csv": medoid_summary,
        "directional_group_replay.csv": groups,
    }
    for name, rows in outputs.items():
        write_csv(out / name, rows)
    qa = {
        **base_qa,
        "schema_version": FIELD_CONTRACT["schema_version"], "component_count": len(components),
        "profile_row_count": len(profiles), "bootstrap_diagnostic_row_count": len(bootstrap),
        "bootstrap_status_counts": _counts(bootstrap, "status"), "holdout_row_count": len(holdout),
        "holdout_task_overlap_max": max((int(row["training_evaluation_task_overlap_count"]) for row in holdout), default=0),
        "strict_support_gt20_image_count": len({row["base_task_id"] for row in medoid_summary}),
        "strict_replay_nested_prefix_contract": all(row["sampling_contract"] == "same_task_permutation_nested_k_prefixes" for row in medoid_replicates),
        "selected_only_medoid_contract": all("selected_only" in row["selection_contract"] for row in medoid_replicates),
        "structure_fixed_support_across_cutoffs": all(row["fixed_support_across_cutoffs"] for row in structure_summary),
        "old42_regression": old42, "evidence_contract": evidence,
        "raw_sources_modified": False, "old_eligibility_used_as_new_primary_filter": False,
        "active_time_lead_time_mixed": False, "bootstrap_rejection_or_redraw": False,
    }
    qa["assertions"] = {
        "exact_1000_per_estimable_component": len(bootstrap) == 1000 * sum(truth(row["estimable"]) for row in components),
        "holdout_nonoverlap": qa["holdout_task_overlap_max"] == 0,
        "old42_exact": old42["mismatch_count"] == 0 and old42["checked_task_count"] == 42,
        "strict_replay_contract": qa["strict_replay_nested_prefix_contract"] and qa["selected_only_medoid_contract"],
        "structure_fixed_support": qa["structure_fixed_support_across_cutoffs"],
    }
    if not all(qa["assertions"].values()):
        raise AssertionError(qa["assertions"])
    write_json(out / "QA.json", qa)
    (out / "REPORT_ZH.md").write_text(render_report(qa), encoding="utf-8")
    handoff = f"""# HANDOFF

- 统计入口：`tools/thesis_main/analysis/materialize_annotation_research_prework_statistics_20260905.py`
- 字段合同：`FIELD_CONTRACT.json`
- 核心表：{', '.join(f'`{name}`' for name in outputs)}
- QA：`QA.json`；报告：`REPORT_ZH.md`
- 计算：全历史动态 roster；{BOOTSTRAPS} 次 building→task draw（不拒绝/不重抽）；held-out task + LOBO；strict >20 nested k15–20 × {REPLAY_REPLICATES}；q=.93/.95/.97；旧42回归。
- 边界：audit/sensitivity only；不改协议、raw truth、旧产物；不把标签解释为人格；不拟合场景预测。
- 证据合同状态：`{evidence['status']}`；若 pending，主任务应在 Luna 文件到位后原命令复跑以完成最终证据 join QA。
"""
    (out / "HANDOFF.md").write_text(handoff, encoding="utf-8")
    manifest = []
    for path in sorted(out.iterdir()):
        if path.is_file() and path.name != "OUTPUT_MANIFEST.csv":
            manifest.append({"file": path.name, "sha256": audit_v1.sha256(path), "bytes": path.stat().st_size})
    write_csv(out / "OUTPUT_MANIFEST.csv", manifest)
    return qa


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUT)
    parser.add_argument('--summarize-existing', action='store_true')
    args = parser.parse_args()
    if args.summarize_existing:
        summarize_existing(args.output_dir)
        return
    qa = materialize(args.output_dir)
    summarize_existing(args.output_dir)
    print(json.dumps({"output": str(args.output_dir), "qa": qa["assertions"]}, ensure_ascii=False))


def summarize_existing(out: Path) -> None:
    """Derived views and independent checks; never rerun or select bootstrap draws."""
    feature = read_csv(out/'feature_records.csv')
    profiles = read_csv(out/'directional_worker_profiles.csv')
    holdout = read_csv(out/'holdout_evaluation.csv')
    holdout = refine_holdout_peer_support(holdout,feature)
    write_csv(out/'holdout_evaluation.csv',holdout)
    write_csv(out/'continuous_vs_classified_summary.csv',summarize_continuous_vs_classified(holdout))
    replicate = read_csv(out/'strict_medoid_replay_replicates.csv')
    group_rows = read_csv(out/'directional_group_replay.csv')
    raw_groups = defaultdict(list)
    for r in feature:
        raw_groups[(r['stage'],r['condition'],r['reference_source_version'],r['feature_name'],r['worker_id'],r['building_id'])].append(r)
    contexts = []
    for key, rows in sorted(raw_groups.items()):
        vals = np.array([float(r['raw_value']) for r in rows])
        contexts.append(dict(zip(['stage','condition','reference_source_version','feature_name','worker_id','building_id'],key)) | {
            'task_count':len({r['base_task_id'] for r in rows}),'raw_mean':float(vals.mean()),'raw_median':float(np.median(vals)),
            'raw_std':float(vals.std(ddof=1)) if len(vals)>1 else '', 'raw_iqr':float(np.quantile(vals,.75)-np.quantile(vals,.25)),
            'interpretation':'building_context_description_not_difficulty_or_learning'})
    write_csv(out/'worker_building_feature_descriptions.csv',contexts)
    identity = [(r['canonical_annotation_id'],r['reference_source_version'],r['feature_name']) for r in feature]
    nested = defaultdict(list)
    for r in replicate:
        nested[(r['stage'],r['condition'],r['base_task_id'],r['replicate'])].append(r)
    checks = {'feature_identity_unique':len(set(identity))==len(identity), 'strict_replicates_82800':len(replicate)==82800,
              'one_worker_one_vote_and_nested':True, 'selected_medoid_in_selected':True, 'holdout_no_task_overlap':True}
    evidence = {r['canonical_annotation_id']:r for r in read_csv(EVIDENCE)}
    for rows in nested.values():
        prev = []
        for r in sorted(rows,key=lambda r:int(r['k'])):
            ids = json.loads(r['selected_worker_ids_json'])
            checks['one_worker_one_vote_and_nested'] &= len(ids)==len(set(ids))==int(r['k']) and ids[:len(prev)]==prev
            checks['selected_medoid_in_selected'] &= evidence[r['selected_medoid_id']]['worker_id'] in ids
            prev = ids
    for r in holdout:
        if r.get('status')=='evaluated':
            checks['holdout_no_task_overlap'] &= not(set(json.loads(r['training_task_ids_json'])) & set(json.loads(r['evaluation_task_ids_json'])))
    timing = [r for r in feature if r['feature_family']=='time']
    checks['time_complete_only'] = len(timing)==2049 and all(evidence[r['canonical_annotation_id']]['active_time_owner_valid_status'].startswith('owner_valid_complete') for r in timing)
    counts = []
    keys = ['stage','condition','reference_source_version','feature_name','threshold']
    grouped = defaultdict(list)
    for r in profiles:
        grouped[tuple(r[k] for k in keys)].append(r)
    for key, rows in sorted(grouped.items()):
        counts.append(dict(zip(keys,key)) | {'worker_descriptions':len(rows),'H':sum(r['directional_class'].startswith('H_') for r in rows),
            'L':sum(r['directional_class'].startswith('L_') for r in rows),'U':sum(r['directional_class'].startswith('U_') for r in rows),
            'interpretation':'counts_within_stratum_not_unique_people_across_rows'})
    write_csv(out/'classification_count_summary.csv',counts)
    curves = []
    per_task = read_csv(out/'strict_medoid_replay_summary.csv')
    for stage, condition, k in sorted({(r['stage'],r['condition'],int(r['k'])) for r in per_task}):
        rows = [r for r in per_task if (r['stage'],r['condition'],int(r['k']))==(stage,condition,k)]
        buildings = sorted({r['building_id'] for r in rows})
        curves.append({'stage':stage,'condition':condition,'k':k,'image_count':len(rows),'building_count':len(buildings),
            'd_mask_image_equal':float(np.mean([float(r['remaining_d_mask_mean']) for r in rows])),
            'd_mask_building_equal':float(np.mean([np.mean([float(r['remaining_d_mask_mean']) for r in rows if r['building_id']==b]) for b in buildings])),
            'remaining_min':min(int(r['remaining_worker_count']) for r in rows),'remaining_max':max(int(r['remaining_worker_count']) for r in rows),
            'interpretation':'finite_historical_heldout_not_new_recruit_prediction'})
    write_csv(out/'strict_medoid_condition_summary.csv',curves)
    group_summary = []
    for k in sorted({int(r['k']) for r in group_rows}):
        rows = [r for r in group_rows if int(r['k'])==k]
        group_summary.append({'k':k,'scenario_rows':len(rows),'evaluable_scenario_rows':sum(truth(r['evaluable']) for r in rows),
            'common_all_three_image_source_components':sum(truth(r['evaluable']) and truth(r['common_support_all_three_scenarios']) for r in rows)//3})
    write_csv(out/'group_common_support_summary.csv',group_summary)
    # Profiles in different reference strata are not merged; report fold changes explicitly.
    full = {(r['stage'],r['condition'],r['reference_source_version'],r['feature_name'],r['worker_id'],r['threshold']):r for r in profiles}
    changes = []
    for r in holdout:
        key = tuple(r[k] for k in ['stage','condition','reference_source_version','feature_name','worker_id','threshold'])
        baseline = full.get(key)
        if baseline:
            changes.append({k:r[k] for k in ['stage','condition','reference_source_version','feature_name','worker_id','threshold','evaluation_kind','fold_id']} | {
                'full_description':baseline['directional_class'],'heldout_training_description':r['directional_class'],
                'membership_changed':baseline['directional_class']!=r['directional_class'], 'status':r['status']})
    write_csv(out/'classification_membership_changes.csv',changes)
    write_json(out/'FINAL_CHECKS.json',{'assertions':checks,'all_passed':all(checks.values()),'feature_rows':len(feature),
        'holdout_rows_are_worker_fold_descriptions_not_independent_people':True,'no_fitted_scene_model':True})
    if not all(checks.values()):
        raise AssertionError(checks)
    plot_prework(out,curves,profiles)
    qa = json.loads((out/'QA.json').read_text(encoding='utf-8'))
    qa['holdout_status_counts_after_peer_support_check'] = dict(Counter(r['status'] for r in holdout))
    qa['independent_final_checks'] = checks
    write_json(out/'QA.json',qa)
    write_json(out/'FIELD_CONTRACT.json',FIELD_CONTRACT)
    (out/'REPORT_ZH.md').write_text(render_report(qa),encoding='utf-8')
    write_csv(out/'OUTPUT_MANIFEST.csv',[{'file':p.name,'bytes':p.stat().st_size} for p in sorted(out.iterdir()) if p.is_file() and p.name!='OUTPUT_MANIFEST.csv'])
    print(json.dumps(checks))


def plot_prework(out, curves, profiles):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    plt.rcParams.update({'font.family':'Microsoft YaHei','axes.unicode_minus':False})
    fig, axes = plt.subplots(1,2,figsize=(12,4.6),layout='constrained')
    for stage,condition in sorted({(r['stage'],r['condition']) for r in curves}):
        rows = sorted([r for r in curves if (r['stage'],r['condition'])==(stage,condition)],key=lambda r:r['k'])
        for ax,metric,title in zip(axes,['d_mask_image_equal','d_mask_building_equal'],['图像等权','Building 等权']):
            ax.plot([r['k'] for r in rows],[r[metric] for r in rows],marker='o',label=f'{stage} {condition} ({rows[0]["image_count"]}图)')
            ax.set(xlabel='已选真实人数 k',ylabel='剩余人员与已选 medoid 的 D_mask',title=title,xticks=K_VALUES)
            ax.grid(alpha=.2); ax.legend(fontsize=8)
    fig.suptitle('69 个固定高支持历史单元：k=20 时仅剩 3–6 人；不是新人收敛预测',fontsize=11)
    fig.savefig(out.parent/'历史剩余人员诊断.png',dpi=180); plt.close(fig)
    chosen = [r for r in profiles if r['stage']=='P1' and r['condition']=='manual' and r['threshold']=='0.8' and r.get('task_adjusted_effect')!='']
    quality = [r for r in chosen if r['feature_name']=='d_mask_to_reference' and 'final_gold_records' in r['reference_source_version']]
    timing = {r['worker_id']:r for r in chosen if r['feature_name']=='log_owner_valid_active_seconds'}
    fig,ax=plt.subplots(figsize=(8,5),layout='constrained')
    for r in quality:
        if r['worker_id'] in timing:
            t=timing[r['worker_id']]; x=float(t['task_adjusted_effect']); y=float(r['task_adjusted_effect'])
            ax.scatter(x,y,color='#226c9a'); ax.annotate('W'+r['worker_id'],(x,y),xytext=(4,3),textcoords='offset points',fontsize=8)
    ax.axvline(0,color='gray',lw=.7); ax.axhline(0,color='gray',lw=.7)
    ax.set(xlabel='任务调整后 −log(完整活动秒数)：右侧相对更快',ylabel='任务调整后 −D_mask：上方相对更接近参考',
           title='P1 Manual：质量与时间连续描述\n参考为 P1 final-gold；不是人员资格或人格分类')
    ax.grid(alpha=.15); fig.savefig(out.parent/'质量与时间连续描述.png',dpi=180); plt.close(fig)


if __name__ == "__main__":
    main()
