"""Post-process topology preflight v3 without reconstructing unavailable sidecars.

The committed v3 task-level output is sufficient to repair the exact-k=5
cohort because every F0 replicate sees the same five candidates.  The frozen
C1 task sidecar supplies the intended terminal medoid.  This script therefore:

* audits current-v3 versus frozen-C1 terminal medoids for 66 exact-k=5 tasks;
* replaces every reach-5 M1 terminal with the frozen F0 terminal (TG-EF5);
* preserves v3 k=3/k=4 stopping probabilities and submission counts;
* reports exact-k=5 quality corrections, all-78 stopping opportunity,
  conditional power/safety scenarios, and reviewer-pool feasibility;
* marks metrics that cannot be recovered from task-level v3 aggregates.

It does not claim an exact source-level replay of the 12 k=22 tasks.  Their
reach-5 F0 quality is order-dependent and the committed v3 directory does not
contain replicate-level rows.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import random
import statistics
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Iterable

from scipy.stats import beta, binom, norm

ROOT = Path(__file__).resolve().parents[3]
SEED = 20260818
REPLICATES = 1000
OUTPUT_NAME = "topology_sequential_preflight_20260818_v4_postprocess"
V3_DIR = "topology_sequential_preflight_20260818_v3"
C1_DIR = (
    "c1_formal_audit_20260802_v16_final/"
    "c1_formal_audit_20260802_7fcacc5c2d6c_bf5def46_6bc67c03"
)
LIVE_WORKERS = {1, 2, 6, 8, 10, 11, 12, 13, 15, 17, 28, 29, 30, 31, 32, 33, 34, 35, 36, 37}
NORMALIZER_DRIFT_ID = "370095f69c5b170678fa"


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as stream:
        return list(csv.DictReader(stream))


def _write_csv(path: Path, rows: list[dict[str, Any]], fields: list[str] | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if fields is None:
        fields = sorted({key for row in rows for key in row}) if rows else []
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields, extrasaction="ignore", lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow({key: _serialise(row.get(key)) for key in fields})


def _serialise(value: Any) -> Any:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (dict, list, tuple, set)):
        return json.dumps(value, ensure_ascii=False, sort_keys=True)
    return value


def _float(value: Any) -> float | None:
    try:
        result = float(str(value).strip())
    except (TypeError, ValueError):
        return None
    return result if math.isfinite(result) else None


def _int(value: Any) -> int | None:
    try:
        return int(round(float(str(value).strip())))
    except (TypeError, ValueError):
        return None


def _truth(value: Any) -> bool:
    return str(value).strip().lower() in {"1", "true", "yes", "y", "passed", "valid"}


def _mean(values: Iterable[Any]) -> float | None:
    numbers = [float(value) for value in values if value is not None and math.isfinite(float(value))]
    return statistics.mean(numbers) if numbers else None


def _sd(values: Iterable[Any]) -> float | None:
    numbers = [float(value) for value in values if value is not None and math.isfinite(float(value))]
    return statistics.stdev(numbers) if len(numbers) >= 2 else None


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _annotation_id(row: dict[str, Any]) -> str:
    return str(row.get("canonical_annotation_id") or row.get("annotation_id") or "")


def _membership_ids(row: dict[str, str]) -> list[str]:
    membership = json.loads(str(row.get("cluster_membership_json") or "[]"))
    result = [str(annotation) for group in membership for annotation in group]
    if len(result) != len(set(result)):
        raise AssertionError(f"duplicate frozen cluster member: {row.get('base_task_id')}")
    return result


def _quality_record(row: dict[str, str] | None) -> float | None:
    if not row:
        return None
    if not (_truth(row.get("quality_evaluable")) and _truth(row.get("gt_primary_analysis_eligible"))):
        return None
    return _float(row.get("iou_to_gt"))


def _candidate_signature(
    annotation: str,
    gt: dict[str, str],
    structural: dict[str, str],
) -> dict[str, Any]:
    status = str(structural.get("structural_validation_status") or "").lower()
    return {
        "annotation_id": annotation,
        "worker_id": _int(structural.get("worker_id") or gt.get("worker_id")),
        "quality": _quality_record(gt),
        "structural_invalidity": status != "passed",
        "repair_applied": _truth(gt.get("geometry_repair_applied") or structural.get("geometry_repair_applied")),
        "current_normalizer_evaluable": annotation != NORMALIZER_DRIFT_ID,
        "formal_replacement": structural.get("assignment_provenance") == "authorized_replacement_assignment",
    }


def _observed_current_signature(f0: dict[str, str]) -> dict[str, Any]:
    return {
        "quality": _float(f0.get("mean_public_gt_quality")),
        "structural_invalidity": _float(f0.get("selected_structural_invalidity_probability")),
        "repair_applied": _float(f0.get("selected_repair_probability")),
        "current_normalizer_evaluable": _float(f0.get("selected_current_normalizer_evaluable_probability")),
        "formal_replacement": _float(f0.get("selected_formal_replacement_probability")),
    }


def _matches_observed(candidate: dict[str, Any], observed: dict[str, Any]) -> bool:
    current_quality = observed["quality"]
    candidate_quality = candidate["quality"]
    if current_quality is None:
        if candidate_quality is not None:
            return False
    elif candidate_quality is None or abs(float(candidate_quality) - float(current_quality)) > 5e-12:
        return False
    for field in (
        "structural_invalidity",
        "repair_applied",
        "current_normalizer_evaluable",
        "formal_replacement",
    ):
        observed_value = observed[field]
        if observed_value is None:
            continue
        if abs(float(bool(candidate[field])) - float(observed_value)) > 5e-12:
            return False
    return True


def _count_from_probability(row: dict[str, str], field: str, n: int) -> int:
    probability = _float(row.get(field))
    if probability is None:
        return 0
    count = int(round(probability * n))
    if abs(count / n - probability) > 5e-9:
        raise AssertionError(f"non-integral probability count: {field}={probability}, n={n}")
    return count


def _correct_boolean_metric(
    m1: dict[str, str],
    metric_field: str,
    support_field: str,
    n_cap: int,
    n_reach5: int,
    current_value: bool,
    frozen_value: bool,
) -> tuple[float | None, int]:
    old_probability = _float(m1.get(metric_field))
    old_support = _int(m1.get(support_field)) or 0
    if old_probability is None or old_support <= 0:
        return None, 0
    old_sum = old_probability * old_support
    early_support = old_support - n_cap
    early_sum = old_sum - n_cap * float(current_value)
    new_support = early_support + n_reach5
    new_sum = early_sum + n_reach5 * float(frozen_value)
    if early_support < 0 or new_support <= 0 or early_sum < -1e-6:
        raise AssertionError(f"invalid boolean metric decomposition: {metric_field}")
    return min(1.0, max(0.0, new_sum / new_support)), new_support


def load_inputs(root: Path) -> dict[str, Any]:
    v3 = root / "analysis_results" / V3_DIR / "PREFIX_POLICY_METRICS.csv"
    c1 = root / "analysis_results" / C1_DIR
    profile = root / "analysis_results" / "final_calibration_profile_20260817_v1" / "pooled_worker_profile_v2.csv"
    task_rows = _read_csv(c1 / "geometry_task_crowd_structure_C1.csv")
    frozen_tasks = {
        str(row["base_task_id"]): row
        for row in task_rows
        if row.get("condition") == "manual" and (_int(row.get("valid_k")) or 0) >= 5
    }
    if len(frozen_tasks) != 78:
        raise AssertionError(f"frozen high-support denominator drifted: {len(frozen_tasks)} != 78")
    distribution = Counter(_int(row.get("valid_k")) for row in frozen_tasks.values())
    if distribution != Counter({5: 66, 22: 12}):
        raise AssertionError(f"frozen candidate distribution drifted: {dict(distribution)}")

    gt_rows = _read_csv(c1 / "c1_gt_quality_evidence.csv")
    gt_by_annotation = {_annotation_id(row): row for row in gt_rows if _annotation_id(row)}
    structural_rows = _read_csv(c1 / "structural_validation_analysis.csv")
    structural_by_annotation = {_annotation_id(row): row for row in structural_rows if _annotation_id(row)}

    v3_rows = [
        row for row in _read_csv(v3)
        if row.get("estimand_scope") == "historical_population_replay_78"
        and row.get("fold") == "policy_development_simulation"
    ]
    by_task_policy = {(str(row["base_task_id"]), str(row["policy"])): row for row in v3_rows}
    if len([row for row in v3_rows if row.get("policy") == "F0"]) != 78:
        raise AssertionError("v3 F0 task denominator is not 78")
    if len([row for row in v3_rows if row.get("policy") == "M1"]) != 78:
        raise AssertionError("v3 M1 task denominator is not 78")

    return {
        "paths": {"v3": v3, "task": c1 / "geometry_task_crowd_structure_C1.csv", "gt": c1 / "c1_gt_quality_evidence.csv", "structural": c1 / "structural_validation_analysis.csv", "profile": profile},
        "frozen_tasks": frozen_tasks,
        "gt": gt_by_annotation,
        "structural": structural_by_annotation,
        "v3_rows": v3_rows,
        "by_task_policy": by_task_policy,
        "profile_rows": _read_csv(profile),
    }


def exact5_correction(data: dict[str, Any]) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    binding_rows: list[dict[str, Any]] = []
    corrected_rows: list[dict[str, Any]] = []
    for task_id, frozen in sorted(data["frozen_tasks"].items()):
        if _int(frozen.get("valid_k")) != 5:
            continue
        f0 = data["by_task_policy"][(task_id, "F0")]
        m1 = data["by_task_policy"][(task_id, "M1")]
        n = _int(m1.get("replicate_support")) or 0
        if n != REPLICATES:
            raise AssertionError(f"replicate denominator drifted: {task_id}={n}")
        frozen_id = str(frozen.get("largest_cluster_medoid_annotation_id") or "")
        frozen_worker = _int(frozen.get("largest_cluster_medoid_worker_id"))
        candidate_ids = _membership_ids(frozen)
        if len(candidate_ids) != 5 or frozen_id not in candidate_ids:
            raise AssertionError(f"invalid frozen exact5 membership: {task_id}")
        candidates = [
            _candidate_signature(
                annotation,
                data["gt"].get(annotation, {}),
                data["structural"].get(annotation, {}),
            )
            for annotation in candidate_ids
        ]
        observed = _observed_current_signature(f0)
        matches = [candidate for candidate in candidates if _matches_observed(candidate, observed)]
        current_id = matches[0]["annotation_id"] if len(matches) == 1 else None
        current_worker = matches[0]["worker_id"] if len(matches) == 1 else None
        frozen_candidate = next(candidate for candidate in candidates if candidate["annotation_id"] == frozen_id)
        q_current = observed["quality"]
        q_frozen = frozen_candidate["quality"]
        q_delta = q_current - q_frozen if q_current is not None and q_frozen is not None else None
        proxy_mismatch = (
            (q_current is None) != (q_frozen is None)
            or (q_delta is not None and abs(q_delta) > 5e-12)
        )
        inferred_mismatch = current_id != frozen_id if current_id is not None else None
        binding_rows.append({
            "base_task_id": task_id,
            "building_id": frozen.get("building_id", ""),
            "frozen_medoid_annotation_id": frozen_id,
            "frozen_medoid_worker_id": frozen_worker,
            "inferred_v3_medoid_annotation_id": current_id,
            "inferred_v3_medoid_worker_id": current_worker,
            "inference_candidate_count": len(matches),
            "inference_status": "unique" if len(matches) == 1 else "ambiguous_or_unidentified",
            "inferred_medoid_mismatch": inferred_mismatch,
            "quality_or_missingness_mismatch": proxy_mismatch,
            "v3_medoid_quality": q_current,
            "frozen_medoid_quality": q_frozen,
            "v3_minus_frozen_quality": q_delta,
            "candidate_signatures": candidates,
        })

        n_stop3 = _count_from_probability(m1, "stop_at_3_probability", n)
        n_stop4 = _count_from_probability(m1, "incremental_stop_at_4_probability", n)
        n_reach5 = _count_from_probability(m1, "reach5_probability", n)
        n_cap = _count_from_probability(m1, "cap_resolved_probability", n)
        if n_stop3 + n_stop4 + n_reach5 != n:
            raise AssertionError(f"M1 outcome counts do not close: {task_id}")
        n_selected_old = _int(m1.get("selected_output_replicate_support")) or 0
        n_quality_old = _int(m1.get("complete_case_quality_replicate_support")) or 0
        old_mean_quality = _float(m1.get("mean_public_gt_quality"))
        old_quality_sum = (old_mean_quality or 0.0) * n_quality_old
        cap_quality_support = n_cap if q_current is not None else 0
        cap_quality_sum = n_cap * q_current if q_current is not None else 0.0
        early_quality_support = n_quality_old - cap_quality_support
        early_quality_sum = old_quality_sum - cap_quality_sum
        if early_quality_support < 0 or early_quality_sum < -1e-6:
            raise AssertionError(f"quality decomposition failed: {task_id}")
        terminal_quality_support = n_reach5 if q_frozen is not None else 0
        new_quality_support = early_quality_support + terminal_quality_support
        new_quality_sum = early_quality_sum + (n_reach5 * q_frozen if q_frozen is not None else 0.0)
        new_mean_quality = new_quality_sum / new_quality_support if new_quality_support else None
        new_delta = new_mean_quality - q_frozen if new_mean_quality is not None and q_frozen is not None else None
        early_selected_support = n_selected_old - n_cap
        new_selected_support = early_selected_support + n_reach5
        if early_selected_support < 0 or new_selected_support != n:
            raise AssertionError(
                f"TG-EF5 does not produce one output per exact5 replicate: {task_id}, {new_selected_support}/{n}"
            )

        bool_metrics: dict[str, Any] = {}
        current_values = {
            "selected_structural_invalidity_probability": bool(round(observed["structural_invalidity"] or 0.0)),
            "selected_repair_probability": bool(round(observed["repair_applied"] or 0.0)),
            "selected_current_normalizer_evaluable_probability": bool(round(observed["current_normalizer_evaluable"] if observed["current_normalizer_evaluable"] is not None else 1.0)),
            "selected_formal_replacement_probability": bool(round(observed["formal_replacement"] or 0.0)),
        }
        frozen_values = {
            "selected_structural_invalidity_probability": bool(frozen_candidate["structural_invalidity"]),
            "selected_repair_probability": bool(frozen_candidate["repair_applied"]),
            "selected_current_normalizer_evaluable_probability": bool(frozen_candidate["current_normalizer_evaluable"]),
            "selected_formal_replacement_probability": bool(frozen_candidate["formal_replacement"]),
        }
        supports = {
            "selected_structural_invalidity_probability": "selected_structural_invalidity_replicate_support",
            "selected_repair_probability": "selected_output_replicate_support",
            "selected_current_normalizer_evaluable_probability": "selected_output_replicate_support",
            "selected_formal_replacement_probability": "selected_output_replicate_support",
        }
        for metric, support in supports.items():
            value, metric_support = _correct_boolean_metric(
                m1, metric, support, n_cap, n_reach5, current_values[metric], frozen_values[metric]
            )
            bool_metrics[f"tg_ef5_{metric}"] = value
            bool_metrics[f"tg_ef5_{metric}_support"] = metric_support

        corrected_rows.append({
            "base_task_id": task_id,
            "building_id": frozen.get("building_id", ""),
            "replicate_support": n,
            "stop_at_3_probability": n_stop3 / n,
            "incremental_stop_at_4_probability": n_stop4 / n,
            "reach5_probability": n_reach5 / n,
            "old_cap_resolved_probability": n_cap / n,
            "old_expert_escalation_probability": (n_reach5 - n_cap) / n,
            "tg_ef5_expert_escalation_probability": 0.0,
            "mean_k": _float(m1.get("mean_frozen_geometry_submissions_used")),
            "submission_savings_vs_fixed5": _float(m1.get("mean_frozen_geometry_submission_savings_vs_f0")),
            "old_selected_output_probability": _float(m1.get("selected_output_probability")),
            "tg_ef5_selected_output_probability": new_selected_support / n,
            "old_public_gt_quality": old_mean_quality,
            "old_public_gt_quality_support": n_quality_old,
            "frozen_f0_public_gt_quality": q_frozen,
            "tg_ef5_public_gt_quality": new_mean_quality,
            "tg_ef5_public_gt_quality_support": new_quality_support,
            "tg_ef5_paired_complete_case_delta_vs_frozen_f0": new_delta,
            "early_quality_sum_recovered": early_quality_sum,
            "early_quality_support_recovered": early_quality_support,
            "terminal_quality_sum_added": n_reach5 * q_frozen if q_frozen is not None else None,
            "terminal_quality_support_added": terminal_quality_support,
            "instability_status": "not_identifiable_from_task_level_v3_when_terminal_medoid_changed" if inferred_mismatch or proxy_mismatch else "v3_value_unchanged",
            "selected_worker_distribution_status": "terminal_worker_corrected_but_prefix_worker_distribution_not_recoverable" if inferred_mismatch or proxy_mismatch else "v3_value_unchanged",
            **bool_metrics,
        })

    if len(binding_rows) != 66 or len(corrected_rows) != 66:
        raise AssertionError("exact5 denominator is not 66")

    inferred = [row for row in binding_rows if row["inferred_medoid_mismatch"] is True]
    proxy = [row for row in binding_rows if row["quality_or_missingness_mismatch"]]
    evaluable_deltas = [
        float(row["v3_minus_frozen_quality"])
        for row in binding_rows
        if row["inferred_medoid_mismatch"] is True and row["v3_minus_frozen_quality"] is not None
    ]
    if len(inferred) != 9:
        raise AssertionError(f"inferred exact5 medoid mismatch count drifted: {len(inferred)} != 9")
    if len(evaluable_deltas) != 8:
        raise AssertionError(f"evaluable mismatch quality count drifted: {len(evaluable_deltas)} != 8")

    summary = {
        "exact5_task_count": len(binding_rows),
        "uniquely_inferred_current_medoid_count": sum(row["inference_status"] == "unique" for row in binding_rows),
        "inferred_medoid_mismatch_count": len(inferred),
        "quality_or_missingness_mismatch_count": len(proxy),
        "evaluable_mismatch_quality_count": len(evaluable_deltas),
        "v3_minus_frozen_quality_mean": statistics.mean(evaluable_deltas),
        "v3_minus_frozen_quality_min": min(evaluable_deltas),
        "v3_minus_frozen_quality_max": max(evaluable_deltas),
    }
    return binding_rows, corrected_rows, summary


def cohort_stopping(data: dict[str, Any]) -> tuple[list[dict[str, Any]], dict[str, dict[str, float | None]]]:
    rows: list[dict[str, Any]] = []
    summaries: dict[str, dict[str, float | None]] = {}
    cohorts = {
        "all78": set(data["frozen_tasks"]),
        "exact5_66": {task for task, row in data["frozen_tasks"].items() if _int(row.get("valid_k")) == 5},
        "highsupport22_12": {task for task, row in data["frozen_tasks"].items() if _int(row.get("valid_k")) == 22},
    }
    m1_by_task = {
        task: data["by_task_policy"][(task, "M1")]
        for task in data["frozen_tasks"]
    }
    for cohort, tasks in cohorts.items():
        metrics = {
            "stop_at_3": _mean(_float(m1_by_task[task].get("stop_at_3_probability")) for task in tasks),
            "incremental_stop_at_4": _mean(_float(m1_by_task[task].get("incremental_stop_at_4_probability")) for task in tasks),
            "reach5": _mean(_float(m1_by_task[task].get("reach5_probability")) for task in tasks),
            "old_expert_escalation": _mean(_float(m1_by_task[task].get("expert_escalation_probability")) for task in tasks),
            "mean_k": _mean(_float(m1_by_task[task].get("mean_frozen_geometry_submissions_used")) for task in tasks),
            "mean_savings": _mean(_float(m1_by_task[task].get("mean_frozen_geometry_submission_savings_vs_f0")) for task in tasks),
        }
        metrics["stop_before_5"] = (metrics["stop_at_3"] or 0.0) + (metrics["incremental_stop_at_4"] or 0.0)
        metrics["relative_submission_saving"] = (5.0 - float(metrics["mean_k"])) / 5.0 if metrics["mean_k"] is not None else None
        metrics["k3_only_mean_k"] = 5.0 - 2.0 * float(metrics["stop_at_3"] or 0.0)
        metrics["k3_only_relative_saving"] = (5.0 - float(metrics["k3_only_mean_k"])) / 5.0
        summaries[cohort] = metrics
        for metric, value in metrics.items():
            rows.append({"cohort": cohort, "task_count": len(tasks), "metric": metric, "estimate": value, "status": "development_descriptive_only"})
    return rows, summaries


def _building_bootstrap(
    task_values: dict[str, float],
    building_by_task: dict[str, str],
    *,
    draws: int = 5000,
    seed: int = SEED,
) -> tuple[float | None, float | None]:
    if not task_values:
        return None, None
    blocks: dict[str, list[float]] = defaultdict(list)
    for task, value in task_values.items():
        blocks[building_by_task[task]].append(float(value))
    buildings = sorted(blocks)
    rng = random.Random(seed)
    estimates: list[float] = []
    for _ in range(draws):
        sample: list[float] = []
        for _ in buildings:
            sample.extend(blocks[rng.choice(buildings)])
        estimates.append(statistics.mean(sample))
    estimates.sort()
    return estimates[int(0.025 * (draws - 1))], estimates[int(0.975 * (draws - 1))]


def _ni_power(n: int, true_delta: float, sd: float, margin: float, alpha: float = 0.025) -> float:
    if sd <= 0:
        return 1.0 if true_delta > -margin else 0.0
    return float(norm.cdf((true_delta + margin) * math.sqrt(n) / sd - norm.ppf(1 - alpha)))


def _superiority_power(n: int, true_saving: float, sd: float, alpha: float = 0.025) -> float:
    if sd <= 0:
        return 1.0 if true_saving > 0 else 0.0
    return float(norm.cdf(true_saving * math.sqrt(n) / sd - norm.ppf(1 - alpha)))


def _exact_upper(events: int, n: int, confidence: float = 0.95) -> float:
    if n <= 0:
        return 1.0
    return 1.0 if events >= n else float(beta.ppf(confidence, events + 1, n - events))


def _maximum_events(n: int, threshold: float = 0.05) -> int:
    allowed = -1
    for events in range(n + 1):
        if _exact_upper(events, n) <= threshold:
            allowed = events
    return allowed


def power_and_success_scenarios(
    data: dict[str, Any],
    corrected_rows: list[dict[str, Any]],
    stopping: dict[str, dict[str, float | None]],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    quality_by_task = {
        row["base_task_id"]: float(row["tg_ef5_paired_complete_case_delta_vs_frozen_f0"])
        for row in corrected_rows
        if row.get("tg_ef5_paired_complete_case_delta_vs_frozen_f0") is not None
    }
    building_by_task = {task: str(data["frozen_tasks"][task].get("building_id") or "") for task in quality_by_task}
    quality_mean = statistics.mean(quality_by_task.values())
    quality_sd = statistics.stdev(quality_by_task.values())
    quality_ci = _building_bootstrap(quality_by_task, building_by_task)

    all78_m1 = [data["by_task_policy"][(task, "M1")] for task in sorted(data["frozen_tasks"])]
    saving_values = [
        5.0 - float(_float(row.get("mean_frozen_geometry_submissions_used")) or 5.0)
        for row in all78_m1
    ]
    saving_mean = statistics.mean(saving_values)
    saving_sd = statistics.stdev(saving_values)
    coverage = float(stopping["all78"]["stop_before_5"] or 0.0)

    designs = [
        ("balanced20", 118, 63),
        ("mainfirst20", 130, 70),
        ("mainfirst22", 143, 77),
    ]
    rows: list[dict[str, Any]] = []
    for design, n_audit, n_live in designs:
        count_power = _superiority_power(n_live, saving_mean, saving_sd)
        rows.append({
            "design": design,
            "gate": "submission_count_superiority",
            "n_audit": n_audit,
            "n_live": n_live,
            "assumed_parameter": saving_mean,
            "empirical_sd": saving_sd,
            "conditional_pass_probability": count_power,
            "status": "scenario_operating_characteristic",
        })
        stop_counts = {
            "audit_shadow": max(1, int(round(n_audit * coverage))),
            "live_actual": max(1, int(round(n_live * coverage))),
            "combined_common_policy": max(1, int(round((n_audit + n_live) * coverage))),
        }
        for lane, n_stop in stop_counts.items():
            maximum = _maximum_events(n_stop)
            rows.append({
                "design": design,
                "gate": f"safety_denominator__{lane}",
                "n_audit": n_audit,
                "n_live": n_live,
                "n_stop": n_stop,
                "zero_event_upper_95": _exact_upper(0, n_stop),
                "maximum_events_for_5pct_upper_gate": maximum,
                "status": "scenario_denominator",
            })
        for margin in (0.005, 0.010, 0.0125, 0.015):
            q_power = _ni_power(n_audit, quality_mean, quality_sd, margin)
            rows.append({
                "design": design,
                "gate": "quality_noninferiority_exact5_empirical",
                "n_audit": n_audit,
                "n_live": n_live,
                "ni_margin": margin,
                "assumed_parameter": quality_mean,
                "empirical_sd": quality_sd,
                "conditional_pass_probability": q_power,
                "status": "scenario_operating_characteristic_not_margin_justification",
            })
            combined_n = stop_counts["combined_common_policy"]
            maximum = _maximum_events(combined_n)
            for harm in (0.005, 0.010, 0.015, 0.020, 0.030):
                safety_power = float(binom.cdf(maximum, combined_n, harm)) if maximum >= 0 else 0.0
                lower = max(0.0, q_power + count_power + safety_power - 2.0)
                upper = min(q_power, count_power, safety_power)
                rows.append({
                    "design": design,
                    "gate": "three_gate_joint_frechet_range",
                    "n_audit": n_audit,
                    "n_live": n_live,
                    "ni_margin": margin,
                    "assumed_true_harm": harm,
                    "quality_pass_probability": q_power,
                    "count_pass_probability": count_power,
                    "safety_pass_probability": safety_power,
                    "joint_probability_lower_bound": lower,
                    "joint_probability_upper_bound": upper,
                    "independence_reference_only": q_power * count_power * safety_power,
                    "status": "conditional_range_not_actual_success_probability",
                })

    summary = {
        "exact5_quality_task_support": len(quality_by_task),
        "exact5_corrected_quality_delta_mean": quality_mean,
        "exact5_corrected_quality_delta_sd": quality_sd,
        "exact5_building_bootstrap_ci": list(quality_ci),
        "all78_submission_saving_mean": saving_mean,
        "all78_submission_saving_sd": saving_sd,
        "all78_stop_before5_coverage": coverage,
        "actual_full_success_probability": "not_identifiable",
        "nonidentifiable_inputs": [
            "expert-validated delivery harm",
            "expert repeatability and adjudication error",
            "scientifically justified non-inferiority margin",
            "k22 replicate-level TG-EF5 quality",
            "future no-response/replacement distribution",
            "future active-time and queueing distribution",
            "cross-gate dependence under deployment",
        ],
    }
    return rows, summary


def _hypergeom_probability(N: int, K: int, n: int, x: int) -> float:
    if x < 0 or x > K or n - x < 0 or n - x > N - K:
        return 0.0
    return math.comb(K, x) * math.comb(N - K, n - x) / math.comb(N, n)


def _two_proportion_power(n_each: int, p0: float, p1: float, alpha: float = 0.05) -> float:
    if n_each <= 0:
        return 0.0
    pooled = (p0 + p1) / 2.0
    null_se = math.sqrt(2.0 * pooled * (1.0 - pooled) / n_each)
    alt_se = math.sqrt((p0 * (1.0 - p0) + p1 * (1.0 - p1)) / n_each)
    if null_se <= 0 or alt_se <= 0:
        return 0.0
    critical = norm.ppf(1.0 - alpha / 2.0) * null_se
    delta = abs(p1 - p0)
    return float(norm.cdf((-critical - delta) / alt_se) + 1.0 - norm.cdf((critical - delta) / alt_se))


def reviewer_feasibility(data: dict[str, Any], coverage: float) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    profiles = [row for row in data["profile_rows"] if (_int(row.get("worker_id")) or -1) in LIVE_WORKERS]
    def rank_key(row: dict[str, str]) -> tuple[float, float, float, int]:
        q = _float(row.get("Q_GT_EB_LCB"))
        f = _float(row.get("F_struct_interval_upper"))
        r = _float(row.get("R_LOO_LCB"))
        worker = _int(row.get("worker_id")) or 999
        return (-(q if q is not None else -math.inf), f if f is not None else math.inf, -(r if r is not None else -math.inf), worker)
    profiles.sort(key=rank_key)
    rows: list[dict[str, Any]] = []
    for rank, row in enumerate(profiles, 1):
        rows.append({
            "record_type": "profile_ordering_sensitivity",
            "rank": rank,
            "worker_id": _int(row.get("worker_id")),
            "Q_GT_EB_LCB": _float(row.get("Q_GT_EB_LCB")),
            "F_struct_interval_upper": _float(row.get("F_struct_interval_upper")),
            "R_LOO_LCB": _float(row.get("R_LOO_LCB")),
            "status": "ordering_sensitivity_not_reviewer_validation",
        })
    for pool_size in (4, 6, 8):
        distribution = {x: _hypergeom_probability(20, pool_size, 5, x) for x in range(0, min(pool_size, 5) + 1)}
        p_one = sum(probability for used, probability in distribution.items() if pool_size - used >= 1)
        p_two = sum(probability for used, probability in distribution.items() if pool_size - used >= 2)
        rows.append({
            "record_type": "combinatorial_availability",
            "reviewer_pool_size": pool_size,
            "probability_at_least_one_remaining_after_five": p_one,
            "probability_at_least_two_remaining_after_five": p_two,
            "status": "availability_only",
        })
        for task_total in (181, 200, 220):
            flagged = task_total * coverage
            rows.append({
                "record_type": "reviewer_load",
                "reviewer_pool_size": pool_size,
                "task_total": task_total,
                "expected_reach5_or_flagged_tasks": flagged,
                "expected_reviews_per_reviewer_if_all_flagged_reviewed": flagged / pool_size,
                "expected_reviews_per_reviewer_in_1to1_nested_trial": flagged / (2.0 * pool_size),
                "status": "capacity_scenario",
            })
    flagged_main20 = int(round(200 * coverage))
    n_each = flagged_main20 // 2
    for p0, p1 in ((0.70, 0.90), (0.75, 0.90), (0.80, 0.90), (0.70, 0.85)):
        rows.append({
            "record_type": "nested_reviewer_trial_power",
            "flagged_task_total": flagged_main20,
            "n_per_arm": n_each,
            "baseline_accuracy": p0,
            "reviewer_accuracy": p1,
            "approx_two_sided_power": _two_proportion_power(n_each, p0, p1),
            "status": "scenario_only_role_transfer_effect_not_identified",
        })
    summary = {
        "live_profile_count": len(profiles),
        "reviewer_effect_status": "not_identifiable_from_existing_independent_annotations",
        "anchoring_control_required": True,
        "recommended_protocol": [
            "reviewer pre-commits topology from panorama before seeing candidate annotations",
            "candidate layouts are anonymised and hide worker identity, profile and support counts",
            "reviewer selects one, rejects all, or flags scope-contract failure",
            "reviewer role is nested-randomised before production use",
        ],
    }
    return rows, summary


def run(root: Path, output: Path) -> Path:
    if output.exists():
        raise FileExistsError(f"refusing to overwrite append-only output: {output}")
    output.mkdir(parents=True)
    data = load_inputs(root)
    binding_rows, corrected_rows, binding_summary = exact5_correction(data)
    stopping_rows, stopping_summary = cohort_stopping(data)
    scenario_rows, scenario_summary = power_and_success_scenarios(data, corrected_rows, stopping_summary)
    reviewer_rows, reviewer_summary = reviewer_feasibility(data, float(stopping_summary["all78"]["stop_before_5"] or 0.0))

    _write_csv(output / "EXACT5_MEDOID_BINDING_AUDIT.csv", binding_rows)
    _write_csv(output / "EXACT5_TG_EF5_TASK_METRICS.csv", corrected_rows)
    _write_csv(output / "STOPPING_OPPORTUNITY_BY_COHORT.csv", stopping_rows)
    _write_csv(output / "POWER_SAFETY_AND_JOINT_SCENARIOS.csv", scenario_rows)
    _write_csv(output / "REVIEWER_FEASIBILITY.csv", reviewer_rows)

    summary = {
        "artifact_role": "TOPOLOGY_V3_EXACT5_POSTPROCESS",
        "development_only": True,
        "scientific_conclusion_prohibited": True,
        "source_level_replay_status": "not_identifiable_from_committed_paper_branch",
        "exact5_postprocess_status": "computed_from_committed_v3_task_aggregates_and_frozen_C1_terminal_medoid",
        "k22_tg_ef5_quality_status": "not_identifiable_without_replicate_level_rows_or_historical_pairwise_sidecar",
        "medoid_binding": binding_summary,
        "stopping": stopping_summary,
        "operating_characteristics": scenario_summary,
        "reviewer": reviewer_summary,
        "reference_contract": {
            "confirmatory_main": "single_operational_reference",
            "multiple_materially_different_protocol_consistent_topologies": "scope-unresolved",
            "acceptable_topology_set_as_confirmatory_reference": "prohibited",
            "acceptable_set_permitted_role": "development candidate-hypothesis inventory or future amended annotation contract only",
        },
        "unrecoverable_v3_metrics_after_medoid_change": [
            "prefix/full5 selected-output instability for mismatch tasks",
            "complete selected-worker distribution across prefix stops",
            "all78 TG-EF5 quality because k22 reach5 F0 quality is order-dependent",
        ],
    }
    (output / "SUMMARY.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    inputs = list(data["paths"].values())
    manifest = {
        "schema_version": "topology_v3_exact5_postprocess_v1",
        "development_only": True,
        "seed": SEED,
        "input_sha256": {str(path.relative_to(root)): _sha256(path) for path in inputs},
        "output_files": sorted(path.name for path in output.iterdir()),
        "v3_overwritten": False,
        "frozen_C1_overwritten": False,
    }
    (output / "analysis_manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    all78 = stopping_summary["all78"]
    exact5 = scenario_summary
    readme = f"""# Topology v3 exact-k=5 frozen-medoid postprocess

This append-only diagnostic does not reconstruct unavailable historical C1
sidecars and does not overwrite v3 or frozen C1.

## Scope/reference contract

Paper A retains one operational topology/reference for every confirmatory
in-scope task. Multiple materially different, protocol-consistent topologies
remain `scope-unresolved`; they are not converted into a max-over-reference or
set-valued Main target.

## Medoid binding

- exact-k=5 tasks: {binding_summary['exact5_task_count']}
- uniquely inferred v3 terminal medoids: {binding_summary['uniquely_inferred_current_medoid_count']}
- v3/frozen medoid mismatches: {binding_summary['inferred_medoid_mismatch_count']}
- evaluable mismatch quality pairs: {binding_summary['evaluable_mismatch_quality_count']}
- v3 minus frozen quality: mean={binding_summary['v3_minus_frozen_quality_mean']}, min={binding_summary['v3_minus_frozen_quality_min']}, max={binding_summary['v3_minus_frozen_quality_max']}

## All-78 stopping opportunity

- stop@3: {all78['stop_at_3']}
- incremental stop@4: {all78['incremental_stop_at_4']}
- reach5: {all78['reach5']}
- old expert escalation: {all78['old_expert_escalation']}
- mean K: {all78['mean_k']}
- relative frozen-submission saving: {all78['relative_submission_saving']}
- k3-only mean K: {all78['k3_only_mean_k']}
- k3-only relative saving: {all78['k3_only_relative_saving']}

## Corrected exact-k=5 quality planning input

- task support: {exact5['exact5_quality_task_support']}
- paired delta mean: {exact5['exact5_corrected_quality_delta_mean']}
- paired delta SD: {exact5['exact5_corrected_quality_delta_sd']}
- building-block sensitivity CI: {exact5['exact5_building_bootstrap_ci']}

The complete experiment success probability remains not identifiable. The
scenario file reports conditional gate operating characteristics and Frechet
ranges, not an empirical probability of publication or Main success.

## Reliable reviewer

Existing records measure independent annotation, not performance after viewing
peer layouts. Profile ordering and combinatorial availability are therefore
reported only as feasibility sensitivities. A reviewer mechanism requires a
blinded nested randomisation and anchoring controls before production use.
"""
    (output / "README.md").write_text(readme, encoding="utf-8")
    return output


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--output-dir", type=Path, default=None)
    args = parser.parse_args()
    root = args.root.resolve()
    output = (args.output_dir or root / "analysis_results" / OUTPUT_NAME).resolve()
    print(run(root, output))


if __name__ == "__main__":
    main()
