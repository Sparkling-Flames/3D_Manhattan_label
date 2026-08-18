"""Append-only audit for the topology sequential preflight.

This script does not alter frozen C1 artifacts or the v3 development output. It:
1. checks exact-k=5 medoid reproducibility against the frozen C1 sidecar;
2. binds the full-k=5 terminal output to the frozen C1 medoid where an exact
   historical five-candidate counterfactual exists;
3. evaluates TG-EF5, an early-exit wrapper with an identical fixed-k=5 terminal;
4. reports scenario operating characteristics and reviewer-pool availability.

All outputs are development diagnostics and are not a Stage 3 launch decision.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import random
import statistics
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any, Iterable

from scipy.stats import beta, binom, norm, t as student_t

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.thesis_main.analysis import run_topology_sequential_preflight as v3  # noqa: E402
from tools.thesis_main.analysis.geometry_consensus.medoid import select_medoid  # noqa: E402

SEED = 20260818
REPLICATES = 1000
OUTPUT_NAME = "topology_sequential_preflight_20260818_v4_audit"
TG_POLICY = "TG_EF5"
F0_POLICY = "F0_FROZEN_BOUND"


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as stream:
        return list(csv.DictReader(stream))


def _write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str] | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if fieldnames is None:
        fieldnames = sorted({key for row in rows for key in row}) if rows else []
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fieldnames, extrasaction="ignore", lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow({key: _serialise(row.get(key)) for key in fieldnames})


def _serialise(value: Any) -> Any:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (list, dict, tuple)):
        return json.dumps(value, ensure_ascii=False, sort_keys=True)
    return value


def _float(value: Any) -> float | None:
    try:
        result = float(str(value).strip())
    except (TypeError, ValueError):
        return None
    return result if math.isfinite(result) else None


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


def _record_by_id(records: list[dict[str, Any]], annotation_id: str) -> dict[str, Any] | None:
    return next((row for row in records if v3._key(row) == annotation_id), None)


def _normalise_membership(value: Any) -> list[list[str]]:
    if not value:
        return []
    groups = json.loads(value) if isinstance(value, str) else value
    return sorted((sorted(str(item) for item in group) for group in groups), key=lambda group: (-len(group), group))


def _pair_scores(records: list[dict[str, Any]]) -> dict[tuple[int, int], float]:
    scores: dict[tuple[int, int], float] = {}
    for left in range(len(records)):
        for right in range(left + 1, len(records)):
            item = v3._pairwise_metric(records[left]["_geometry"], records[right]["_geometry"])
            boundary = _float(item.get("q_boundary", item.get("boundary_similarity")))
            wall = _float(item.get("q_wallwall", item.get("wallwall_similarity")))
            if boundary is not None and wall is not None:
                scores[left, right] = min(boundary, wall)
    return scores


def _rank_map(records: list[dict[str, Any]], task_id: str, largest_members: list[str]) -> dict[str, dict[str, Any]]:
    indices = tuple(index for index, row in enumerate(records) if v3._key(row) in set(largest_members))
    _, _, ranked = select_medoid(records, indices, _pair_scores(records), task_id=task_id)
    result: dict[str, dict[str, Any]] = {}
    for rank, (median, mean, sha, annotation_id, seed, index) in enumerate(ranked, 1):
        result[str(annotation_id)] = {
            "rank": rank,
            "median_similarity": float(median),
            "mean_similarity": float(mean),
            "geometry_sha256": sha,
            "tie_seed": seed,
            "worker_id": records[index].get("worker_id"),
        }
    return result


def medoid_consistency_audit(data: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for task_id, candidates in sorted(data["candidates"].items()):
        if len(candidates) != 5:
            continue
        frozen = data["tasks"][task_id]
        current = v3._cluster(candidates, task_id)
        frozen_members = _normalise_membership(frozen.get("cluster_membership_json"))
        current_members = _normalise_membership(current.get("cluster_membership_json"))
        frozen_medoid = str(frozen.get("largest_cluster_medoid_annotation_id") or "")
        current_medoid = str(current.get("largest_cluster_medoid_annotation_id") or "")
        largest_members = current_members[0] if current_members else []
        ranks = _rank_map(candidates, task_id, largest_members) if largest_members else {}
        frozen_record = _record_by_id(candidates, frozen_medoid)
        current_record = _record_by_id(candidates, current_medoid)
        frozen_rank = ranks.get(frozen_medoid, {})
        current_rank = ranks.get(current_medoid, {})
        same_scores = (
            frozen_rank
            and current_rank
            and abs(float(frozen_rank["median_similarity"]) - float(current_rank["median_similarity"])) <= 1e-12
            and abs(float(frozen_rank["mean_similarity"]) - float(current_rank["mean_similarity"])) <= 1e-12
        )
        membership_match = frozen_members == current_members
        status_match = str(frozen.get("task_crowd_structure_status") or "") == str(current.get("task_crowd_structure_status") or "")
        medoid_match = frozen_medoid == current_medoid
        if medoid_match:
            cause = "match"
        elif frozen_medoid not in largest_members:
            cause = "frozen_medoid_not_in_current_largest_cluster"
        elif same_scores:
            cause = "tie_break_contract_drift"
        else:
            cause = "medoid_score_contract_drift"
        frozen_quality = v3._quality(frozen_record)
        current_quality = v3._quality(current_record)
        rows.append({
            "base_task_id": task_id,
            "building_id": frozen.get("building_id", ""),
            "candidate_n": len(candidates),
            "cluster_status_match": status_match,
            "cluster_membership_match": membership_match,
            "frozen_status": frozen.get("task_crowd_structure_status"),
            "current_status": current.get("task_crowd_structure_status"),
            "frozen_medoid_annotation_id": frozen_medoid,
            "current_medoid_annotation_id": current_medoid,
            "frozen_medoid_worker_id": frozen_record.get("worker_id") if frozen_record else None,
            "current_medoid_worker_id": current_record.get("worker_id") if current_record else None,
            "medoid_match": medoid_match,
            "mismatch_cause": cause,
            "frozen_medoid_rank_under_current_rule": frozen_rank.get("rank"),
            "current_medoid_rank_under_current_rule": current_rank.get("rank"),
            "frozen_medoid_median_similarity": frozen_rank.get("median_similarity"),
            "current_medoid_median_similarity": current_rank.get("median_similarity"),
            "frozen_medoid_mean_similarity": frozen_rank.get("mean_similarity"),
            "current_medoid_mean_similarity": current_rank.get("mean_similarity"),
            "frozen_medoid_public_gt_quality": frozen_quality,
            "current_medoid_public_gt_quality": current_quality,
            "current_minus_frozen_quality": (
                current_quality - frozen_quality
                if current_quality is not None and frozen_quality is not None
                else None
            ),
            "largest_cluster_members": largest_members,
        })
    if len(rows) != 66:
        raise AssertionError(f"exact-k=5 audit denominator drifted: {len(rows)} != 66")
    return rows


def _frozen_terminal_record(data: dict[str, Any], task_id: str, accepted: list[dict[str, Any]], cluster: dict[str, Any]) -> dict[str, Any] | None:
    historical = data["candidates"][task_id]
    if len(historical) == 5:
        frozen_id = str(data["tasks"][task_id].get("largest_cluster_medoid_annotation_id") or "")
        return _record_by_id(accepted, frozen_id) if frozen_id else None
    return v3._selected_from_cluster(accepted, cluster)


def run_f0_frozen_bound(order: list[dict[str, Any]], task_id: str, data: dict[str, Any]) -> dict[str, Any]:
    result = v3._empty_result(F0_POLICY, order)
    ledger = v3._admitted_prefixes(order)
    accepted = ledger["accepted"]
    result.update(
        invalid_attempts=ledger["invalid_attempts"],
        replacement_attempts=ledger["replacement_attempts"],
        metric_invalid_attempts=ledger["metric_invalid_attempts"],
        K_attempts=ledger["raw_paid_attempts"],
        K_valid=len(accepted),
    )
    if len(accepted) < 5:
        result.update(
            status="historical_counterfactual_support_shortfall",
            reach5=None,
            historical_counterfactual_support_shortfall=True,
            unresolved=None,
        )
        return result
    prefix = accepted[:5]
    cluster = v3._cluster(prefix, task_id)
    selected = _frozen_terminal_record(data, task_id, prefix, cluster)
    result.update(
        status="fixed_k5" if selected else "policy_failure_no_output",
        reach5=True,
        historical_counterfactual_support_shortfall=False,
        unresolved=selected is None,
        selected=selected,
        topology_status=cluster.get("task_crowd_structure_status"),
    )
    return result


def run_tg_ef5(order: list[dict[str, Any]], task_id: str, data: dict[str, Any]) -> dict[str, Any]:
    result = v3._empty_result(TG_POLICY, order)
    result["supported_multimodal_encountered"] = False
    ledger = v3._admitted_prefixes(order)
    accepted = ledger["accepted"]
    result.update(
        invalid_attempts=ledger["invalid_attempts"],
        replacement_attempts=ledger["replacement_attempts"],
        metric_invalid_attempts=ledger["metric_invalid_attempts"],
        K_attempts=ledger["raw_paid_attempts"],
        K_valid=len(accepted),
    )
    for k in range(3, min(4, len(accepted)) + 1):
        prefix = accepted[:k]
        cluster = v3._cluster(prefix, task_id)
        status = str(cluster.get("task_crowd_structure_status") or "not_evaluable")
        result["topology_status"] = status
        result["supported_multimodal_encountered"] |= status == "supported_multimodal"
        gate = v3.m1_conservative_gate(cluster, k)
        if k == 3:
            result["stop_at_3"] = gate
        elif k == 4:
            result["incremental_stop_at_4"] = gate
        if gate:
            selected = v3._selected_from_cluster(prefix, cluster)
            result.update(
                status=f"stop@{k}" if selected else "policy_failure_no_output",
                stop_k=k if selected else None,
                K_attempts=ledger["attempts_by_k"][k],
                K_valid=k,
                stop_at_3=(k == 3) if selected else False,
                incremental_stop_at_4=(k == 4) if selected else False,
                reach5=False,
                historical_counterfactual_support_shortfall=False,
                unresolved=selected is None,
                selected=selected,
            )
            return result
    if len(accepted) < 5:
        result.update(
            status="historical_counterfactual_support_shortfall",
            historical_counterfactual_support_shortfall=True,
            unresolved=None,
        )
        return result
    terminal = run_f0_frozen_bound(order, task_id, data)
    result.update(
        status=terminal.get("status"),
        K_attempts=ledger["attempts_by_k"][5],
        K_valid=5,
        reach5=True,
        historical_counterfactual_support_shortfall=False,
        unresolved=terminal.get("selected") is None,
        selected=terminal.get("selected"),
        topology_status=terminal.get("topology_status"),
    )
    result["supported_multimodal_encountered"] |= result["topology_status"] == "supported_multimodal"
    return result


def _attach_pair_metrics(row: dict[str, Any], f0: dict[str, Any]) -> None:
    row["paired_rows_status"] = "paired_same_task_replicate_order" if f0.get("paid_valid_submissions") == 5 else "historical_f0_support_shortfall"
    if f0.get("paid_valid_submissions") == 5 and row.get("paid_valid_submissions") is not None:
        row["paid_valid_savings_vs_f0"] = f0["paid_valid_submissions"] - row["paid_valid_submissions"]
        row["frozen_geometry_submission_savings_vs_f0"] = row["paid_valid_savings_vs_f0"]
    if f0.get("raw_paid_attempts") is not None and row.get("raw_paid_attempts") is not None:
        row["raw_paid_attempt_savings_vs_f0"] = f0["raw_paid_attempts"] - row["raw_paid_attempts"]
        row["historical_candidates_examined_savings_vs_f0"] = row["raw_paid_attempt_savings_vs_f0"]
    if f0.get("public_gt_quality") is not None and row.get("public_gt_quality") is not None:
        row["paired_complete_case_quality_delta_vs_f0"] = row["public_gt_quality"] - f0["public_gt_quality"]
    if f0.get("reference_evaluable_autonomous_delivery_quality") is not None and row.get("reference_evaluable_autonomous_delivery_quality") is not None:
        row["reference_evaluable_autonomous_delivery_mitt_delta_vs_f0"] = row["reference_evaluable_autonomous_delivery_quality"] - f0["reference_evaluable_autonomous_delivery_quality"]
    if row.get("selected_annotation_id") and f0.get("selected_annotation_id"):
        row["prefix_full5_selected_output_instability"] = row["selected_annotation_id"] != f0["selected_annotation_id"]
        selected = row.get("_selected_record")
        f0_selected = f0.get("_selected_record")
        if selected and f0_selected:
            row["corner_count_changed_vs_f0"] = selected.get("topology_signature") != f0_selected.get("topology_signature")
            row["continuous_geometry_delta_vs_f0"] = v3._continuous_geometry_delta(selected, f0_selected)


def _task_summary(replicate_rows: list[dict[str, Any]], tasks: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in replicate_rows:
        grouped[(str(row["base_task_id"]), str(row["policy"]))].append(row)
    output: list[dict[str, Any]] = []
    for (task_id, policy), group in sorted(grouped.items()):
        statuses = [row.get("status") for row in group]
        output.append({
            "base_task_id": task_id,
            "building_id": tasks[task_id].get("building_id", ""),
            "policy": policy,
            "replicate_support": len(group),
            "candidate_n": group[0].get("candidate_permutation_n"),
            "stop_at_3_probability": statuses.count("stop@3") / len(group),
            "incremental_stop_at_4_probability": statuses.count("stop@4") / len(group),
            "reach5_probability": sum(row.get("reach5") is True for row in group) / len(group),
            "mean_k": _mean(row.get("paid_valid_submissions") for row in group),
            "mean_savings_vs_f0": _mean(row.get("paid_valid_savings_vs_f0") for row in group),
            "selected_output_probability": sum(bool(row.get("selected_annotation_id")) for row in group) / len(group),
            "autonomous_non_delivery_probability": sum(bool(row.get("autonomous_non_delivery")) for row in group) / len(group),
            "expert_escalation_probability": sum(bool(row.get("expert_escalation_required")) for row in group) / len(group),
            "mean_public_gt_quality": _mean(row.get("public_gt_quality") for row in group),
            "mean_quality_delta_vs_f0": _mean(row.get("paired_complete_case_quality_delta_vs_f0") for row in group),
            "mean_mitt_delta_vs_f0": _mean(row.get("reference_evaluable_autonomous_delivery_mitt_delta_vs_f0") for row in group),
            "instability_probability": _mean(
                float(row["prefix_full5_selected_output_instability"])
                for row in group
                if row.get("prefix_full5_selected_output_instability") is not None
            ),
            "corner_count_change_probability": _mean(
                float(row["corner_count_changed_vs_f0"])
                for row in group
                if row.get("corner_count_changed_vs_f0") is not None
            ),
            "mean_continuous_geometry_delta": _mean(row.get("continuous_geometry_delta_vs_f0") for row in group),
            "selected_structural_invalidity_probability": _mean(
                float(row["selected_structural_invalidity"])
                for row in group
                if row.get("selected_structural_invalidity") is not None
            ),
            "selected_repair_probability": _mean(
                float(row["selected_repair_applied"])
                for row in group
                if row.get("selected_repair_applied") is not None
            ),
            "selected_formal_replacement_probability": _mean(
                float(row["selected_formal_replacement_candidate"])
                for row in group
                if row.get("selected_formal_replacement_candidate") is not None
            ),
            "supported_multimodality_probability": _mean(
                float(row["supported_multimodal_encountered"])
                for row in group
                if row.get("supported_multimodal_encountered") is not None
            ),
        })
    return output


def _building_bootstrap(values: dict[str, float], building_by_task: dict[str, str], seed: int, draws: int = 5000) -> tuple[float | None, float | None]:
    if not values:
        return None, None
    blocks: dict[str, list[float]] = defaultdict(list)
    for task_id, value in values.items():
        blocks[building_by_task[task_id]].append(value)
    buildings = sorted(blocks)
    rng = random.Random(seed)
    estimates: list[float] = []
    for _ in range(draws):
        sample: list[float] = []
        for _ in buildings:
            sample.extend(blocks[rng.choice(buildings)])
        estimates.append(statistics.mean(sample))
    estimates.sort()
    return estimates[int(0.025 * (len(estimates) - 1))], estimates[int(0.975 * (len(estimates) - 1))]


def _overall_metrics(task_rows: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    output: list[dict[str, Any]] = []
    by_policy = defaultdict(list)
    for row in task_rows:
        by_policy[row["policy"]].append(row)
    summary: dict[str, Any] = {}
    for policy, rows in sorted(by_policy.items()):
        building_by_task = {row["base_task_id"]: row["building_id"] for row in rows}
        metrics = {
            "stop_at_3": "stop_at_3_probability",
            "incremental_stop_at_4": "incremental_stop_at_4_probability",
            "reach5": "reach5_probability",
            "mean_k": "mean_k",
            "mean_savings_vs_f0": "mean_savings_vs_f0",
            "selected_output_probability": "selected_output_probability",
            "autonomous_non_delivery_probability": "autonomous_non_delivery_probability",
            "expert_escalation_probability": "expert_escalation_probability",
            "public_gt_quality": "mean_public_gt_quality",
            "quality_delta_vs_f0": "mean_quality_delta_vs_f0",
            "mitt_delta_vs_f0": "mean_mitt_delta_vs_f0",
            "instability_probability": "instability_probability",
            "corner_count_change_probability": "corner_count_change_probability",
            "continuous_geometry_delta": "mean_continuous_geometry_delta",
        }
        policy_summary: dict[str, Any] = {}
        for label, field in metrics.items():
            values = {
                row["base_task_id"]: float(row[field])
                for row in rows
                if row.get(field) is not None and math.isfinite(float(row[field]))
            }
            estimate = _mean(values.values())
            low, high = _building_bootstrap(values, building_by_task, SEED) if values else (None, None)
            output.append({
                "policy": policy,
                "metric": label,
                "estimate": estimate,
                "task_support": len(values),
                "task_total": len(rows),
                "building_ci_low": low,
                "building_ci_high": high,
                "status": "development_descriptive_only" if estimate is not None else "not_identifiable",
            })
            policy_summary[label] = estimate
        policy_summary["quality_delta_task_sd"] = _sd(row.get("mean_quality_delta_vs_f0") for row in rows)
        policy_summary["k_task_sd"] = _sd(row.get("mean_k") for row in rows)
        summary[policy] = policy_summary
    return output, summary


def _ni_power(n: int, true_delta: float, sd: float, margin: float, alpha: float = 0.025) -> float:
    if sd <= 0:
        return 1.0 if true_delta > -margin else 0.0
    critical = norm.ppf(1.0 - alpha)
    return float(norm.cdf((true_delta + margin) * math.sqrt(n) / sd - critical))


def _superiority_power(n: int, true_saving: float, sd: float, alpha: float = 0.025) -> float:
    if sd <= 0:
        return 1.0 if true_saving > 0 else 0.0
    critical = norm.ppf(1.0 - alpha)
    return float(norm.cdf(true_saving * math.sqrt(n) / sd - critical))


def _max_exact_failures(n: int, threshold: float = 0.05, confidence: float = 0.95) -> int:
    maximum = -1
    for events in range(n + 1):
        upper = 1.0 if events == n else float(beta.ppf(confidence, events + 1, n - events))
        if upper <= threshold:
            maximum = events
    return maximum


def _joint_bootstrap(
    quality_values: list[float],
    k_values: list[float],
    n_audit: int,
    n_live: int,
    margin: float,
    seed: int,
    draws: int = 5000,
) -> float | None:
    if len(quality_values) < 2 or len(k_values) < 2:
        return None
    rng = random.Random(seed)
    passes = 0
    for _ in range(draws):
        audit = [rng.choice(quality_values) for _ in range(n_audit)]
        live = [rng.choice(k_values) for _ in range(n_live)]
        q_mean = statistics.mean(audit)
        q_sd = statistics.stdev(audit) if len(audit) > 1 else 0.0
        k_mean = statistics.mean(live)
        k_sd = statistics.stdev(live) if len(live) > 1 else 0.0
        q_lower = q_mean - float(student_t.ppf(0.975, max(1, n_audit - 1))) * q_sd / math.sqrt(n_audit)
        k_upper = k_mean + float(student_t.ppf(0.975, max(1, n_live - 1))) * k_sd / math.sqrt(n_live)
        passes += q_lower > -margin and k_upper < 5.0
    return passes / draws


def operating_characteristics(task_rows: list[dict[str, Any]], overall: dict[str, Any]) -> list[dict[str, Any]]:
    tg_rows = [row for row in task_rows if row["policy"] == TG_POLICY]
    quality_values = [float(row["mean_quality_delta_vs_f0"]) for row in tg_rows if row.get("mean_quality_delta_vs_f0") is not None]
    k_values = [float(row["mean_k"]) for row in tg_rows if row.get("mean_k") is not None]
    quality_mean = statistics.mean(quality_values)
    quality_sd = statistics.stdev(quality_values)
    k_mean = statistics.mean(k_values)
    k_sd = statistics.stdev(k_values)
    stop_coverage = float(overall[TG_POLICY]["stop_at_3"] or 0.0) + float(overall[TG_POLICY]["incremental_stop_at_4"] or 0.0)
    designs = [
        ("balanced_20", 118, 63),
        ("main_first_20", 130, 70),
        ("main_first_22", 143, 77),
    ]
    rows: list[dict[str, Any]] = []
    for design, n_audit, n_live in designs:
        for margin in (0.005, 0.010, 0.0125, 0.015):
            rows.append({
                "design": design,
                "analysis": "quality_noninferiority_empirical_delta",
                "n_audit": n_audit,
                "n_live": n_live,
                "margin": margin,
                "assumed_true_delta": quality_mean,
                "empirical_task_sd": quality_sd,
                "probability": _ni_power(n_audit, quality_mean, quality_sd, margin),
                "interpretation": "conditional normal-approximation operating characteristic; not actual Main success probability",
            })
            rows.append({
                "design": design,
                "analysis": "quality_plus_count_joint_empirical_bootstrap",
                "n_audit": n_audit,
                "n_live": n_live,
                "margin": margin,
                "assumed_true_delta": quality_mean,
                "empirical_task_sd": quality_sd,
                "probability": _joint_bootstrap(quality_values, k_values, n_audit, n_live, margin, SEED + n_audit + int(margin * 10000)),
                "interpretation": "historical task-bootstrap for quality NI plus submission-count superiority only; excludes expert harm, replacement, availability and deployment shift",
            })
        rows.append({
            "design": design,
            "analysis": "submission_count_superiority",
            "n_audit": n_audit,
            "n_live": n_live,
            "margin": None,
            "assumed_true_delta": 5.0 - k_mean,
            "empirical_task_sd": k_sd,
            "probability": _superiority_power(n_live, 5.0 - k_mean, k_sd),
            "interpretation": "conditional normal-approximation operating characteristic for frozen-geometry submission count only",
        })
        for lane, n_stop in (
            ("audit_shadow", max(1, round(n_audit * stop_coverage))),
            ("live_actual", max(1, round(n_live * stop_coverage))),
            ("common_policy_combined", max(1, round((n_audit + n_live) * stop_coverage))),
        ):
            max_events = _max_exact_failures(n_stop)
            for harm in (0.005, 0.01, 0.015, 0.02, 0.03):
                probability = float(binom.cdf(max_events, n_stop, harm)) if max_events >= 0 else 0.0
                rows.append({
                    "design": design,
                    "analysis": f"exact_5pct_safety_gate__{lane}",
                    "n_audit": n_audit,
                    "n_live": n_live,
                    "n_stop": n_stop,
                    "maximum_events_allowed": max_events,
                    "assumed_true_harm": harm,
                    "probability": probability,
                    "interpretation": "scenario exact-binomial operating characteristic; expert-validated harm is currently not identifiable",
                })
    return rows


def reviewer_feasibility(data: dict[str, Any], root: Path) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    profile_path = root / "analysis_results" / "final_calibration_profile_20260817_v1" / "pooled_worker_profile_v2.csv"
    profiles = [row for row in _read_csv(profile_path) if int(float(row["worker_id"])) in v3.LIVE_WORKERS]
    def profile_key(row: dict[str, str]) -> tuple[float, float, float, int]:
        q_lcb = _float(row.get("Q_GT_EB_LCB"))
        f_upper = _float(row.get("F_struct_interval_upper"))
        loo_lcb = _float(row.get("R_LOO_LCB"))
        return (
            -(q_lcb if q_lcb is not None else -math.inf),
            f_upper if f_upper is not None else math.inf,
            -(loo_lcb if loo_lcb is not None else -math.inf),
            int(float(row["worker_id"])),
        )
    profiles.sort(key=profile_key)
    profile_rows = [{
        "conservative_rank": rank,
        "worker_id": int(float(row["worker_id"])),
        "Q_GT_EB": _float(row.get("Q_GT_EB")),
        "Q_GT_EB_LCB": _float(row.get("Q_GT_EB_LCB")),
        "R_LOO_LCB": _float(row.get("R_LOO_LCB")),
        "F_struct_EB": _float(row.get("F_struct_EB")),
        "F_struct_interval_upper": _float(row.get("F_struct_interval_upper")),
        "GT_support": _float(row.get("GT_support")),
        "profile_status": row.get("worker_profile_status"),
    } for rank, row in enumerate(profiles, 1)]

    availability_rows: list[dict[str, Any]] = []
    high_support_tasks = [task for task, candidates in data["candidates"].items() if len(candidates) == 22]
    for pool_size in (4, 6, 8):
        pool = {row["worker_id"] for row in profile_rows[:pool_size]}
        remaining_counts: list[int] = []
        for task_id in high_support_tasks:
            candidates = data["candidates"][task_id]
            for replicate in range(REPLICATES):
                order = v3._stable_order(candidates, task_id, replicate, SEED)
                first5 = {int(row["worker_id"]) for row in order[:5]}
                remaining_counts.append(len(pool - first5))
        availability_rows.append({
            "reviewer_pool_size": pool_size,
            "reviewer_worker_ids": sorted(pool),
            "historical_k22_task_n": len(high_support_tasks),
            "replicate_task_support": len(remaining_counts),
            "mean_reviewers_remaining_after_first5": statistics.mean(remaining_counts),
            "probability_at_least_one_remaining": sum(value >= 1 for value in remaining_counts) / len(remaining_counts),
            "probability_at_least_two_remaining": sum(value >= 2 for value in remaining_counts) / len(remaining_counts),
            "effect_identifiability": "review_accuracy_not_identifiable_from_independent_annotation_records",
        })
    summary = {
        "active_profile_count": len(profile_rows),
        "historical_k22_task_count": len(high_support_tasks),
        "selection_rule_role": "availability sensitivity only; not a frozen reviewer qualification gate",
        "review_effect_status": "not_identifiable",
        "reason": "historical records contain independent full annotations, not blinded verification decisions after viewing candidate layouts",
    }
    return profile_rows, availability_rows, summary


def run(root: Path, output_dir: Path, replicates: int = REPLICATES) -> Path:
    if replicates != REPLICATES:
        raise ValueError(f"this audit requires exactly {REPLICATES} replicates")
    if output_dir.exists():
        raise FileExistsError(f"refusing to overwrite append-only output: {output_dir}")
    output_dir.mkdir(parents=True)
    data = v3.load_frozen_inputs(root)

    medoid_rows = medoid_consistency_audit(data)
    _write_csv(output_dir / "MEDOID_CONSISTENCY_AUDIT.csv", medoid_rows)

    replicate_rows: list[dict[str, Any]] = []
    for replicate in range(replicates):
        for task_id, task in data["tasks"].items():
            order = v3._stable_order(data["candidates"][task_id], task_id, replicate, SEED)
            signature = v3._order_signature(order)
            f0_result = run_f0_frozen_bound(order, task_id, data)
            tg_result = run_tg_ef5(order, task_id, data)
            f0_row = v3._result_row(task, replicate, signature, f0_result)
            f0_row["policy"] = F0_POLICY
            f0_row["paired_rows_status"] = "baseline_same_order"
            tg_row = v3._result_row(task, replicate, signature, tg_result)
            tg_row["policy"] = TG_POLICY
            _attach_pair_metrics(tg_row, f0_row)
            replicate_rows.extend((f0_row, tg_row))

    task_rows = _task_summary(replicate_rows, data["tasks"])
    _write_csv(output_dir / "TG_EF5_TASK_METRICS.csv", task_rows)
    overall_rows, overall = _overall_metrics(task_rows)
    _write_csv(output_dir / "TG_EF5_OPERATING_CHARACTERISTICS.csv", overall_rows)
    oc_rows = operating_characteristics(task_rows, overall)
    _write_csv(output_dir / "TG_EF5_POWER_AND_SAFETY_SCENARIOS.csv", oc_rows)

    profile_rows, availability_rows, reviewer_summary = reviewer_feasibility(data, root)
    _write_csv(output_dir / "REVIEWER_PROFILE_ORDERING_SENSITIVITY.csv", profile_rows)
    _write_csv(output_dir / "REVIEWER_AVAILABILITY_SENSITIVITY.csv", availability_rows)

    mismatch_rows = [row for row in medoid_rows if not row["medoid_match"]]
    quality_deltas = [float(row["current_minus_frozen_quality"]) for row in mismatch_rows if row.get("current_minus_frozen_quality") is not None]
    contract = {
        "paper_a_reference_contract": "single_operational_reference",
        "acceptable_topology_set_in_confirmatory_main": "prohibited",
        "expert_audit_roles": [
            "candidate_matches_frozen_operational_topology",
            "material_geometry_or_delivery_harm",
            "protocol_contract_failure_or_scope_unresolved",
        ],
        "post_randomisation_multiple_protocol_consistent_interpretations": "retain in operational ITT; classify as scope-contract failure; exclude only from pre-specified geometry per-protocol denominator with worst-case and inclusive sensitivity",
    }
    summary = {
        "status": "development_audit_only",
        "source_v3_status": "medoid_dependent_metrics_invalid_pending_binding_fix",
        "medoid_audit": {
            "exact_k5_tasks": len(medoid_rows),
            "cluster_status_mismatch_count": sum(not row["cluster_status_match"] for row in medoid_rows),
            "cluster_membership_mismatch_count": sum(not row["cluster_membership_match"] for row in medoid_rows),
            "medoid_mismatch_count": len(mismatch_rows),
            "mismatch_quality_delta_mean": _mean(quality_deltas),
            "mismatch_quality_delta_min": min(quality_deltas) if quality_deltas else None,
            "mismatch_quality_delta_max": max(quality_deltas) if quality_deltas else None,
            "mismatch_cause_counts": {
                cause: sum(row["mismatch_cause"] == cause for row in mismatch_rows)
                for cause in sorted({row["mismatch_cause"] for row in mismatch_rows})
            },
        },
        "tg_ef5": overall.get(TG_POLICY, {}),
        "f0_frozen_bound": overall.get(F0_POLICY, {}),
        "reviewer_feasibility": reviewer_summary,
        "reference_contract_resolution": contract,
        "success_probability_status": "full_success_not_identifiable_without_expert_harm_and_valid_NI_margin",
        "scenario_file": "TG_EF5_POWER_AND_SAFETY_SCENARIOS.csv",
    }
    (output_dir / "AUDIT_SUMMARY.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    input_paths = [
        Path(__file__).resolve(),
        v3.c1_root(root) / "geometry_task_crowd_structure_C1.csv",
        v3.c1_root(root) / "c1_geometry_pool_eligibility.csv",
        v3.c1_root(root) / "c1_canonical_geometry.jsonl",
        v3.c1_root(root) / "geometry_pairwise_similarity_C1.csv",
        v3.c1_root(root) / "c1_geometry_repair_audit.csv",
        v3.c1_root(root) / "c1_gt_quality_evidence.csv",
        root / "analysis_results" / "final_calibration_profile_20260817_v1" / "pooled_worker_profile_v2.csv",
    ]
    manifest = {
        "artifact_role": "TOPOLOGY_SEQUENTIAL_PREFLIGHT_V4_AUDIT",
        "schema_version": "topology_sequential_preflight_v4_audit",
        "development_only": True,
        "formal_policy_frozen": False,
        "scientific_conclusion_prohibited": True,
        "seed": SEED,
        "replicates": REPLICATES,
        "input_sha256": {str(path.relative_to(root)): _sha256(path) for path in input_paths},
        "output_files": sorted(path.name for path in output_dir.iterdir()),
        "supersedes_v3": False,
        "v3_medoid_dependent_metrics_status": "invalid_pending_repair",
        "v3_stop_path_metrics_status": "retained_development_descriptive",
    }
    (output_dir / "analysis_manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    tg = overall[TG_POLICY]
    readme = f"""# Topology sequential preflight v4 audit

This is an append-only development audit. It does not overwrite or silently repair v3.

## Medoid reproducibility

- exact historical k=5 tasks: {len(medoid_rows)}
- cluster-status mismatches: {summary['medoid_audit']['cluster_status_mismatch_count']}
- cluster-membership mismatches: {summary['medoid_audit']['cluster_membership_mismatch_count']}
- medoid mismatches: {len(mismatch_rows)}
- current-minus-frozen public-GT quality among evaluable mismatches: mean={summary['medoid_audit']['mismatch_quality_delta_mean']}, min={summary['medoid_audit']['mismatch_quality_delta_min']}, max={summary['medoid_audit']['mismatch_quality_delta_max']}

## TG-EF5

TG-EF5 uses the v3 k=3/k=4 conservative gate and, whenever it reaches k=5, uses the identical corrected F0 terminal output.

- stop@3: {tg.get('stop_at_3')}
- incremental stop@4: {tg.get('incremental_stop_at_4')}
- reach5: {tg.get('reach5')}
- mean K: {tg.get('mean_k')}
- frozen-geometry saving versus fixed k=5: {tg.get('mean_savings_vs_f0')}
- public-GT paired delta versus corrected F0: {tg.get('quality_delta_vs_f0')}
- task-level paired-delta SD: {tg.get('quality_delta_task_sd')}
- expert escalation introduced by TG-EF5: {tg.get('expert_escalation_probability')}

The public-GT result is diagnostic. Actual expert-validated harm and a scientifically justified NI margin remain absent.

## Paper A reference semantics

Paper A retains one frozen operational reference for every in-scope geometry-evaluable task. A second materially different, protocol-consistent interpretation is a scope-contract failure (`scope-unresolved`), not an additional acceptable Main reference. Set-valued references remain a possible future re-annotation contract, not the current confirmatory Main contract.

## Reliable reviewer

The reviewer files assess profile ordering and candidate availability only. Historical independent annotations cannot identify the effect of a worker seeing and verifying other annotations. A reviewer mechanism therefore requires a separately randomised, blinded review study before it can affect production delivery.
"""
    (output_dir / "README.md").write_text(readme, encoding="utf-8")
    return output_dir


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--output-dir", type=Path, default=None)
    parser.add_argument("--replicates", type=int, default=REPLICATES)
    args = parser.parse_args()
    output = args.output_dir or args.root / "analysis_results" / OUTPUT_NAME
    print(run(args.root.resolve(), output.resolve(), args.replicates))


if __name__ == "__main__":
    main()
