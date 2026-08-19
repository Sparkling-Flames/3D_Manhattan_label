"""Read-only development simulation for the C1 topology sequential preflight."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import random
import statistics
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Iterable

ROOT = Path(__file__).resolve().parents[3]
LIVE_WORKERS = {1, 2, 6, 8, 10, 11, 12, 13, 15, 17, 28, 29, 30, 31, 32, 33, 34, 35, 36, 37}
REPLAY_REPAIR_IDS = {"63001f819a4a6b408ae2", "9e5409147dcedaf906b7"}
NORMALIZER_DRIFT_ID = "370095f69c5b170678fa"
SEED = 20260818
DEFAULT_REPLICATES = 1000
Q_BOUNDARY = 0.95
Q_WALLWALL = 0.95
FLAGS = {
    "development_only": True,
    "diagnostic_pre_stage3": True,
    "scientific_conclusion_prohibited": True,
    "block3": False,
    "formal_policy_frozen": False,
    "formal_profile_frozen": False,
}
M2_STATUS = "not_evaluated_leakage_safe_estimator_absent"
M3_STATUS = "pending_pre_peer_timing_binding"

try:
    from tools.thesis_main.analysis.geometry_cluster_v2 import cluster_geometry_records
    from tools.thesis_main.analysis.geometry_consensus.medoid import select_medoid
    from tools.thesis_main.analysis.geometry_consensus.pairwise import pairwise_similarity
    from tools.thesis_main.analysis.geometry_consensus.representation import normalize_geometry_for_c1_calculation
except ModuleNotFoundError:  # pragma: no cover - supports direct execution from another cwd
    sys.path.insert(0, str(ROOT))
    from tools.thesis_main.analysis.geometry_cluster_v2 import cluster_geometry_records
    from tools.thesis_main.analysis.geometry_consensus.medoid import select_medoid
    from tools.thesis_main.analysis.geometry_consensus.pairwise import pairwise_similarity
    from tools.thesis_main.analysis.geometry_consensus.representation import normalize_geometry_for_c1_calculation


def _truth(value: Any) -> bool:
    return str(value).strip().lower() in {"1", "true", "yes", "y", "passed", "valid"}


def _int(value: Any) -> int | None:
    try:
        return int(float(str(value).strip()))
    except (TypeError, ValueError):
        return None


def _float(value: Any) -> float | None:
    try:
        value = float(str(value).strip())
        return value if math.isfinite(value) else None
    except (TypeError, ValueError):
        return None


def _topology_signature_from_structural(structural_row: dict[str, Any], gt_row: dict[str, Any] | None = None) -> str | None:
    """Build the M0 signature from structural evidence; GT is consistency-only."""
    repaired = _int(structural_row.get("repaired_point_count"))
    gt_repaired = _int((gt_row or {}).get("repaired_point_count"))
    if repaired is None or repaired <= 0 or repaired % 2:
        return None
    if gt_repaired is not None and gt_repaired != repaired:
        raise AssertionError(f"structural/GT repaired point-count conflict: {repaired} != {gt_repaired}")
    return f"n_pairs:{repaired / 2:g}"


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8-sig") as handle:
        return list(csv.DictReader(handle))


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows = []
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                rows.append(json.loads(line))
    return rows


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def c1_root(root: Path = ROOT) -> Path:
    return root / "analysis_results" / "c1_formal_audit_20260802_v16_final" / "c1_formal_audit_20260802_7fcacc5c2d6c_bf5def46_6bc67c03"


def _key(row: dict[str, Any]) -> str:
    return str(row.get("canonical_annotation_id") or row.get("annotation_id") or "")


def load_frozen_inputs(root: Path = ROOT) -> dict[str, Any]:
    """Load the frozen C1 geometry pool; later roster/parser versions are diagnostics only."""
    base = c1_root(root)
    sidecar = _read_csv(base / "geometry_task_crowd_structure_C1.csv")
    tasks = {
        str(row["base_task_id"]): row
        for row in sidecar
        if row.get("condition") == "manual" and (_int(row.get("valid_k")) or 0) >= 5
    }
    if len(tasks) != 78:
        raise AssertionError(f"frozen manual k>=5 denominator drifted: {len(tasks)} != 78")

    bindings = {
        str(row["base_task_id"]): row
        for row in _read_csv(base / "c1_task_building_binding.csv")
        if str(row.get("base_task_id")) in tasks
    }
    if set(bindings) != set(tasks):
        raise AssertionError("task-building binding is incomplete for the 78-task denominator")

    gt_rows = _read_csv(base / "c1_gt_quality_evidence.csv")
    gt_by_annotation: dict[str, dict[str, str]] = {}
    for row in gt_rows:
        annotation = _key(row)
        if annotation and annotation not in gt_by_annotation:
            gt_by_annotation[annotation] = row

    structural_rows = _read_csv(base / "structural_validation_analysis.csv")
    structural_by_annotation = {
        _key(row): row for row in structural_rows if _key(row)
    }
    reference_audit = json.loads((base / "c1_operational_reference_audit.json").read_text(encoding="utf-8"))
    conflict_queue = _read_csv(base / "c1_gt_conflict_review_queue.csv")
    if reference_audit.get("gt_issue_declared") is not False or reference_audit.get("n_pending_contexts") != 0 or conflict_queue:
        raise AssertionError("current operational GT/reference audit is not the expected zero-declared, zero-pending state")

    pool_rows = _read_csv(base / "c1_geometry_pool_eligibility.csv")
    pool_ids = {
        _key(row)
        for row in pool_rows
        if str(row.get("base_task_id")) in tasks
        and row.get("condition") == "manual"
        and _truth(row.get("geometry_pool_eligible"))
    }
    if len(pool_ids) != 594:
        raise AssertionError(f"frozen geometry-pool candidate count drifted: {len(pool_ids)} != 594")

    repair_by_annotation = {
        _key(row): row for row in _read_csv(base / "c1_geometry_repair_audit.csv") if _key(row)
    }
    geometry_rows = _read_jsonl(base / "c1_canonical_geometry.jsonl")
    candidates: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for geometry in geometry_rows:
        annotation = _key(geometry)
        task = str(geometry.get("base_task_id") or "")
        if annotation not in pool_ids:
            continue
        worker = _int(geometry.get("worker_id"))
        if task not in tasks or worker is None:
            raise AssertionError(f"frozen geometry-pool identity is incomplete: {annotation}")
        gt = gt_by_annotation.get(annotation, {})
        structural_row = structural_by_annotation.get(annotation, {})
        repair_row = repair_by_annotation.get(annotation, {})
        repaired = _int(structural_row.get("repaired_point_count"))
        topology_signature_from_structural = _topology_signature_from_structural(structural_row, gt)
        repair_applied = _truth(repair_row.get("geometry_repair_applied"))
        calculation_points = (
            json.loads(str(repair_row.get("repaired_points_json") or "[]"))
            if repair_applied
            else geometry.get("corners_px") or []
        )
        normalized = normalize_geometry_for_c1_calculation(
            calculation_points,
            width=_int(geometry.get("width")) or 1024,
            height=_int(geometry.get("height")) or 512,
        )
        if repaired is None or repaired <= 0 or topology_signature_from_structural is None:
            raise AssertionError(f"frozen geometry-pool topology is incomplete: {annotation}")
        structural = structural_row.get("structural_validation_status", "not_evaluable")
        normalized_pairs = _int(normalized.get("n_pairs"))
        current_normalizer_evaluable = normalized.get("valid") is True
        if current_normalizer_evaluable and normalized_pairs != repaired // 2:
            raise AssertionError(f"current normalizer topology conflict for {annotation}: {normalized_pairs} != {repaired // 2}")
        frozen_sha = str(repair_row.get("repaired_geometry_sha256") or repair_row.get("raw_geometry_sha256") or "")
        if not frozen_sha:
            raise AssertionError(f"frozen geometry hash is missing: {annotation}")
        item = dict(geometry)
        item.update({
            "_geometry": {
                "valid": True,
                "base_task_id": task,
                "worker_id": worker,
                "canonical_annotation_id": annotation,
                "frozen_geometry_sha256": frozen_sha,
            },
            "canonical_annotation_id": annotation,
            "worker_id": worker,
            "repaired_point_count": repaired,
            "topology_signature": topology_signature_from_structural,
            "frozen_geometry_sha256": frozen_sha,
            "frozen_geometry_pool_member": True,
            "frozen_geometry_valid": True,
            "replay_geometry_admissible": True,
            "historical_replay_admitted": True,
            "geometry_metric_evaluable": True,
            "current_normalizer_evaluable": current_normalizer_evaluable,
            "current_normalizer_status": str(normalized.get("reason") or ("valid" if current_normalizer_evaluable else "not_evaluable")),
            "current_roster_member": worker in LIVE_WORKERS,
            "structural_validation_status": str(structural),
            "structurally_valid": str(structural).lower() == "passed",
            "raw_structural_failure": str(structural).lower() != "passed",
            "formal_structural_eligible": str(structural).lower() == "passed",
            "repair_applied": repair_applied,
            "repair_required_attempt": repair_applied,
            "preflight_development_repair_binding": repair_applied,
            "formal_c1_derivation": not repair_applied,
            "formal_replacement_candidate": structural_row.get("assignment_provenance") == "authorized_replacement_assignment",
            "assignment_provenance": str(structural_row.get("assignment_provenance") or ""),
            "gt": gt,
        })
        candidates[task].append(item)

    if {_key(row) for rows in candidates.values() for row in rows} != pool_ids:
        raise AssertionError("canonical geometry does not bind one-to-one to the frozen geometry pool")
    frozen_distribution = Counter(len(candidates[task]) for task in tasks)
    if frozen_distribution != Counter({5: 66, 22: 12}):
        raise AssertionError(f"frozen geometry-pool distribution drifted: {dict(frozen_distribution)}")

    pairwise_by_key: dict[tuple[str, int, int], dict[str, Any]] = {}
    for row in _read_csv(base / "geometry_pairwise_similarity_C1.csv"):
        task = str(row.get("base_task_id") or "")
        if task not in tasks or row.get("condition") != "manual":
            continue
        left, right = _int(row.get("worker_id_left")), _int(row.get("worker_id_right"))
        if left is None or right is None:
            raise AssertionError("frozen pairwise worker identity is incomplete")
        key = (task, *sorted((left, right)))
        if key in pairwise_by_key:
            raise AssertionError(f"duplicate frozen pairwise row: {key}")
        pairwise_by_key[key] = {
            "metric_compatible": _truth(row.get("metric_compatible")),
            "pointwise_correspondence_compatible": _truth(row.get("pointwise_correspondence_compatible")),
            "q_boundary": _float(row.get("q_boundary")),
            "q_wallwall": _float(row.get("q_wallwall")),
        }
    expected_pairs = 0
    for task, rows in candidates.items():
        workers = [int(row["worker_id"]) for row in rows]
        if len(workers) != len(set(workers)):
            raise AssertionError(f"frozen geometry pool has duplicate task-worker candidates: {task}")
        expected_pairs += len(rows) * (len(rows) - 1) // 2
        for row in rows:
            worker = int(row["worker_id"])
            row["_geometry"]["_frozen_pairwise_by_worker"] = {
                other: pairwise_by_key[(task, *sorted((worker, other)))]
                for other in workers if other != worker
            }
    if len(pairwise_by_key) != expected_pairs:
        raise AssertionError(f"frozen pairwise coverage drifted: {len(pairwise_by_key)} != {expected_pairs}")

    all_candidates = [row for task in tasks for row in candidates[task]]
    repair_ids = {_key(row) for row in all_candidates if row["repair_applied"]}
    normalizer_invalid_ids = {_key(row) for row in all_candidates if not row["current_normalizer_evaluable"]}
    replacement_workers = Counter(row["worker_id"] for row in all_candidates if row["formal_replacement_candidate"])
    outside_rows = [
        row for row in structural_rows
        if row.get("condition") == "manual"
        and str(row.get("base_task_id")) in tasks
        and row.get("assignment_provenance") == "outside_assignment_submission"
    ]
    if repair_ids != REPLAY_REPAIR_IDS or normalizer_invalid_ids != {NORMALIZER_DRIFT_ID}:
        raise AssertionError(f"repair/normalizer binding drifted: {repair_ids}, {normalizer_invalid_ids}")
    if replacement_workers != Counter({34: 14, 1: 1}) or len(outside_rows) != 7:
        raise AssertionError(f"replacement/outside-assignment inventory drifted: {replacement_workers}, {len(outside_rows)}")
    worker_counts = Counter(row["worker_id"] for row in all_candidates)
    if worker_counts[18] != 26 or worker_counts[27] != 26 or worker_counts[14] != 0:
        raise AssertionError("historical worker retention inventory drifted")

    def supported(predicate) -> int:
        return sum(sum(bool(predicate(row)) for row in candidates[task]) >= 5 for task in tasks)

    sensitivity_counts = {
        "frozen_geometry_pool": supported(lambda row: True),
        "current_normalizer": supported(lambda row: row["current_normalizer_evaluable"]),
        "raw_structural_pass": supported(lambda row: row["structurally_valid"]),
        "raw_structural_and_current_normalizer": supported(lambda row: row["structurally_valid"] and row["current_normalizer_evaluable"]),
        "current20_frozen_geometry_pool": supported(lambda row: row["current_roster_member"]),
        "current20_current_normalizer": supported(lambda row: row["current_roster_member"] and row["current_normalizer_evaluable"]),
        "current20_raw_structural_pass": supported(lambda row: row["current_roster_member"] and row["structurally_valid"]),
        "current20_raw_structural_and_current_normalizer": supported(lambda row: row["current_roster_member"] and row["structurally_valid"] and row["current_normalizer_evaluable"]),
    }
    expected_sensitivity = {
        "frozen_geometry_pool": 78,
        "current_normalizer": 77,
        "raw_structural_pass": 76,
        "raw_structural_and_current_normalizer": 75,
        "current20_frozen_geometry_pool": 50,
        "current20_current_normalizer": 49,
        "current20_raw_structural_pass": 48,
        "current20_raw_structural_and_current_normalizer": 47,
    }
    if sensitivity_counts != expected_sensitivity:
        raise AssertionError(f"sensitivity inventory drifted: {sensitivity_counts}")

    for task in tasks:
        tasks[task]["building_id"] = bindings[task].get("building_id", "")
        tasks[task]["frozen_geometry_candidate_count"] = len(candidates[task])
        tasks[task]["structural_candidate_count"] = sum(row["structurally_valid"] for row in candidates[task])
    support_counts = {
        "historical": {
            "frozen_geometry_pool": sensitivity_counts["frozen_geometry_pool"],
            "current_normalizer": sensitivity_counts["current_normalizer"],
            "structural_passed": sensitivity_counts["raw_structural_pass"],
            "normalizer_and_structural": sensitivity_counts["raw_structural_and_current_normalizer"],
        },
        "current20": {
            "frozen_geometry_pool": sensitivity_counts["current20_frozen_geometry_pool"],
            "current_normalizer": sensitivity_counts["current20_current_normalizer"],
            "structural_passed": sensitivity_counts["current20_raw_structural_pass"],
            "normalizer_and_structural": sensitivity_counts["current20_raw_structural_and_current_normalizer"],
        },
    }
    historical_candidates = dict(candidates)
    return {
        "base": base,
        "tasks": tasks,
        "candidates": historical_candidates,
        "historical_candidates": historical_candidates,
        "bindings": bindings,
        "reference_audit": reference_audit,
        "conflict_queue_rows": conflict_queue,
        "sensitivity_counts": sensitivity_counts,
        "support_counts": support_counts,
        "historical_replay_filters": {"live_roster": False, "current_normalizer": False, "structural_status": False},
        "repair_ids": sorted(repair_ids),
        "normalizer_invalid_ids": sorted(normalizer_invalid_ids),
        "outside_assignment_rows": len(outside_rows),
        "formal_replacement_workers": dict(replacement_workers),
        "assignment_audit": {
            "formal_replacement_count": sum(replacement_workers.values()),
            "formal_replacement_by_worker": {str(worker): count for worker, count in sorted(replacement_workers.items())},
            "outside_assignment_count": len(outside_rows),
        },
    }


def topology_status(records: list[dict[str, Any]]) -> tuple[str, list[list[dict[str, Any]]]]:
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in records:
        signature = str(row.get("topology_signature") or "")
        if not signature:
            return "not_evaluable", []
        groups[signature].append(row)
    ordered = sorted(groups.values(), key=lambda group: (-len(group), tuple(_key(row) for row in group)))
    if not ordered:
        return "not_evaluable", []
    if len(ordered) == 1:
        return "unimodal", ordered
    n1, n2 = len(ordered[0]), len(ordered[1])
    if n1 > n2 and n2 <= 1:
        return "dominant_with_dissent", ordered
    if n2 >= 2:
        return "supported_multimodal", ordered
    return "not_evaluable", ordered


def _pairwise_metric(left: dict[str, Any], right: dict[str, Any]) -> dict[str, Any]:
    frozen = left.get("_frozen_pairwise_by_worker")
    if frozen is not None:
        worker = _int(right.get("worker_id"))
        if worker not in frozen:
            raise AssertionError("frozen pairwise metric is missing for an admitted candidate pair")
        return frozen[worker]
    return pairwise_similarity(left, right)


def _medoid(records: list[dict[str, Any]]) -> dict[str, Any] | None:
    records = [row for row in records if row.get("geometry_metric_evaluable", True)]
    if not records:
        return None
    scores: dict[tuple[int, int], float] = {}
    for left in range(len(records)):
        for right in range(left + 1, len(records)):
            item = _pairwise_metric(records[left]["_geometry"], records[right]["_geometry"])
            boundary = item.get("q_boundary", item.get("boundary_similarity"))
            wall = item.get("q_wallwall", item.get("wallwall_similarity"))
            if boundary is not None and wall is not None:
                scores[left, right] = min(float(boundary), float(wall))
    index, _, _ = select_medoid(tuple(records), tuple(range(len(records))), scores, task_id=str(records[0].get("base_task_id", "")))
    return records[index] if index is not None else None


def _cluster(records: list[dict[str, Any]], task: str) -> dict[str, Any]:
    return cluster_geometry_records(
        records,
        min_q_boundary=Q_BOUNDARY,
        min_q_wallwall=Q_WALLWALL,
        base_task_id=task,
        condition="manual",
        minimum_valid_k=3,
        pairwise_fn=_pairwise_metric,
    )


def _admitted_prefixes(order: list[dict[str, Any]], limit: int = 5) -> dict[str, Any]:
    """Apply one validity/replacement ledger shared by F0, M0 and M1."""
    accepted: list[dict[str, Any]] = []
    attempts_by_k: dict[int, int] = {}
    invalid_attempts = 0
    metric_invalid_attempts = 0
    for attempt, row in enumerate(order, 1):
        metric_valid = bool(row.get("geometry_metric_evaluable"))
        replay_admissible = row.get("replay_geometry_admissible")
        if replay_admissible is None:
            replay_admissible = bool(row.get("structurally_valid")) and metric_valid
        if not replay_admissible:
            invalid_attempts += 1
            metric_invalid_attempts += not metric_valid
            continue
        accepted.append(row)
        attempts_by_k[len(accepted)] = attempt
        if len(accepted) == limit:
            break
    return {
        "accepted": accepted,
        "attempts_by_k": attempts_by_k,
        "invalid_attempts": invalid_attempts,
        "replacement_attempts": invalid_attempts,
        "metric_invalid_attempts": metric_invalid_attempts,
        "raw_paid_attempts": attempts_by_k.get(len(accepted), len(order)),
    }


def m1_conservative_gate(cluster: dict[str, Any], k: int) -> bool:
    """Development-only pre-outcome gate; not a formal policy."""
    largest = _int(cluster.get("largest_cluster_support")) or 0
    second = _int(cluster.get("second_cluster_support")) or 0
    return (largest, second) in {
        3: {(3, 0)},
        4: {(4, 0), (3, 1)},
        5: {(5, 0), (4, 1)},
    }.get(k, set())


def _selected_from_cluster(records: list[dict[str, Any]], cluster: dict[str, Any]) -> dict[str, Any] | None:
    annotation_id = str(cluster.get("largest_cluster_medoid_annotation_id") or "")
    return next((row for row in records if _key(row) == annotation_id), None)


def _empty_result(policy: str, order: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "policy": policy,
        "status": "not_evaluable",
        "stop_k": None,
        "K_attempts": None,
        "K_valid": None,
        "stop_at_3": None,
        "incremental_stop_at_4": None,
        "reach5": None,
        "historical_counterfactual_support_shortfall": None,
        "unresolved": None,
        "invalid_attempts": 0,
        "replacement_attempts": 0,
        "metric_invalid_attempts": 0,
        "supported_multimodal_encountered": None,
        "selected": None,
        "topology_status": None,
        "order": order,
    }


def _fail_closed_result(policy: str, order: list[dict[str, Any]], status: str) -> dict[str, Any]:
    result = _empty_result(policy, order)
    result.update(status=status, invalid_attempts=None, replacement_attempts=None, metric_invalid_attempts=None, supported_multimodal_encountered=None)
    return result


def run_f0(order: list[dict[str, Any]], task: str) -> dict[str, Any]:
    result = _empty_result("F0", order)
    ledger = _admitted_prefixes(order)
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
            historical_counterfactual_support_shortfall=True,
            unresolved=None,
        )
        return result
    cluster = _cluster(accepted, task)
    selected = _selected_from_cluster(accepted, cluster)
    result.update(
        status="fixed_k5" if selected else "policy_failure_no_output",
        reach5=True,
        historical_counterfactual_support_shortfall=False,
        unresolved=selected is None,
        selected=selected,
        topology_status=cluster.get("task_crowd_structure_status"),
    )
    return result


def run_m0(order: list[dict[str, Any]], task: str, *, allow_stop: bool = True) -> dict[str, Any]:
    result = _empty_result("M0_corner_count_gate_geometry_medoid", order)
    result["supported_multimodal_encountered"] = False
    ledger = _admitted_prefixes(order)
    accepted = ledger["accepted"]
    result.update(
        invalid_attempts=ledger["invalid_attempts"],
        replacement_attempts=ledger["replacement_attempts"],
        metric_invalid_attempts=ledger["metric_invalid_attempts"],
        K_attempts=ledger["raw_paid_attempts"],
        K_valid=len(accepted),
    )
    groups: list[list[dict[str, Any]]] = []
    for k in range(3, len(accepted) + 1):
        status, groups = topology_status(accepted[:k])
        result["topology_status"] = status
        result["supported_multimodal_encountered"] |= status == "supported_multimodal"
        gate = status in {"unimodal", "dominant_with_dissent"}
        if k == 3:
            result["stop_at_3"] = gate
        elif k == 4:
            result["incremental_stop_at_4"] = gate
        if allow_stop and k in {3, 4} and gate:
            selected = _medoid(groups[0]) if groups else None
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
    else:
        status, groups = topology_status(accepted[:5])
        selected = _medoid(groups[0]) if groups else None
        result.update(
            status="cap_reached_output" if selected else "policy_failure_no_output",
            K_attempts=ledger["attempts_by_k"][5],
            K_valid=5,
            reach5=True,
            historical_counterfactual_support_shortfall=False,
            unresolved=selected is None,
            topology_status=status,
            selected=selected,
        )
    return result


def run_m1(order: list[dict[str, Any]], task: str, *, allow_stop: bool = True) -> dict[str, Any]:
    result = _empty_result("M1", order)
    result["supported_multimodal_encountered"] = False
    ledger = _admitted_prefixes(order)
    accepted = ledger["accepted"]
    result.update(
        invalid_attempts=ledger["invalid_attempts"],
        replacement_attempts=ledger["replacement_attempts"],
        metric_invalid_attempts=ledger["metric_invalid_attempts"],
        K_attempts=ledger["raw_paid_attempts"],
        K_valid=len(accepted),
    )
    for k in range(3, len(accepted) + 1):
        prefix = accepted[:k]
        cluster = _cluster(prefix, task)
        status = str(cluster.get("task_crowd_structure_status") or "not_evaluable")
        result["topology_status"] = status
        result["supported_multimodal_encountered"] |= status == "supported_multimodal"
        gate = m1_conservative_gate(cluster, k)
        if k == 3:
            result["stop_at_3"] = gate
        elif k == 4:
            result["incremental_stop_at_4"] = gate
        if allow_stop and k in {3, 4} and gate:
            selected = _selected_from_cluster(prefix, cluster)
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
        if k == 5:
            selected = _selected_from_cluster(prefix, cluster) if gate else None
            result.update(
                status="cap_resolved" if selected else "unresolved_expert_escalation_required",
                K_attempts=ledger["attempts_by_k"][5],
                K_valid=5,
                reach5=True,
                historical_counterfactual_support_shortfall=False,
                unresolved=selected is None,
                selected=selected,
            )
            return result
    result.update(
        status="historical_counterfactual_support_shortfall",
        historical_counterfactual_support_shortfall=True,
        unresolved=None,
    )
    return result


def _quality(row: dict[str, Any] | None) -> float | None:
    if not row:
        return None
    gt = row.get("gt", {})
    if not (_truth(gt.get("quality_evaluable")) and _truth(gt.get("gt_primary_analysis_eligible"))):
        return None
    return _float(gt.get("iou_to_gt"))


def _continuous_geometry_delta(left: dict[str, Any] | None, right: dict[str, Any] | None) -> float | None:
    if not left or not right:
        return None
    if _key(left) == _key(right):
        return 0.0
    pair = _pairwise_metric(left["_geometry"], right["_geometry"])
    boundary = _float(pair.get("q_boundary", pair.get("boundary_similarity")))
    wall = _float(pair.get("q_wallwall", pair.get("wallwall_similarity")))
    return 1.0 - min(boundary, wall) if boundary is not None and wall is not None else None


def _result_row(task: dict[str, Any], replicate: int, order_signature: str, result: dict[str, Any]) -> dict[str, Any]:
    selected = result.get("selected")
    quality = _quality(selected)
    autonomous_non_delivery = result.get("status") in {"policy_failure_no_output", "unresolved_expert_escalation_required"}
    expert_escalation_required = result.get("status") == "unresolved_expert_escalation_required"
    accepted = _admitted_prefixes(result["order"])["accepted"]
    used = accepted[: int(result.get("K_valid") or 0)]
    return {
        "replicate_id": replicate,
        "base_task_id": task["base_task_id"],
        "building_id": task.get("building_id", ""),
        "condition": "manual",
        "policy": result["policy"],
        "order_signature": order_signature,
        "candidate_permutation_n": len(result["order"]),
        "status": result.get("status"),
        "stop_at_3": result.get("stop_at_3"),
        "incremental_stop_at_4": result.get("incremental_stop_at_4"),
        "reach5": result.get("reach5"),
        "stop_k": result.get("stop_k"),
        "raw_paid_attempts": result.get("K_attempts"),
        "paid_valid_submissions": result.get("K_valid"),
        "historical_candidates_examined": result.get("K_attempts"),
        "frozen_geometry_submissions_used": result.get("K_valid"),
        "invalid_attempts": result.get("invalid_attempts"),
        "replacement_attempts": result.get("replacement_attempts"),
        "metric_invalid_attempts": result.get("metric_invalid_attempts"),
        "raw_structural_failure_attempts": sum(row.get("raw_structural_failure") is True for row in used),
        "repair_required_attempts": sum(row.get("repair_required_attempt") is True for row in used),
        "current_normalizer_invalid_attempts": sum(row.get("current_normalizer_evaluable") is False for row in used),
        "formal_replacement_candidates_used": sum(row.get("formal_replacement_candidate") is True for row in used),
        "historical_counterfactual_support_shortfall": result.get("historical_counterfactual_support_shortfall"),
        "unresolved": result.get("unresolved"),
        "autonomous_non_delivery": autonomous_non_delivery,
        "expert_escalation_required": expert_escalation_required,
        "supported_multimodal_encountered": result.get("supported_multimodal_encountered"),
        "topology_status": result.get("topology_status"),
        "selected_annotation_id": _key(selected) if selected else None,
        "selected_worker_id": selected.get("worker_id") if selected else None,
        "selected_geometry_hash": selected.get("geometry_hash") if selected else None,
        "selected_structural_invalidity": (not selected.get("structurally_valid")) if selected else None,
        "selected_repair_applied": selected.get("repair_applied") if selected else None,
        "selected_current_normalizer_evaluable": selected.get("current_normalizer_evaluable") if selected else None,
        "selected_formal_replacement_candidate": selected.get("formal_replacement_candidate") if selected else None,
        "public_gt_quality": quality,
        "public_gt_quality_status": "eligible" if quality is not None else "not_evaluable",
        "reference_evaluable_autonomous_delivery_quality": 0.0 if autonomous_non_delivery else quality,
        "paired_complete_case_quality_delta_vs_f0": None,
        "reference_evaluable_autonomous_delivery_mitt_delta_vs_f0": None,
        "paid_valid_savings_vs_f0": None,
        "raw_paid_attempt_savings_vs_f0": None,
        "frozen_geometry_submission_savings_vs_f0": None,
        "historical_candidates_examined_savings_vs_f0": None,
        "prefix_full5_selected_output_instability": None,
        "corner_count_changed_vs_f0": None,
        "continuous_geometry_delta_vs_f0": None,
        "paired_rows_status": "pending_f0_support" if result["policy"] in {"F0", "M0_corner_count_gate_geometry_medoid", "M1"} else "not_identifiable",
        "_selected_record": selected,
    }


def attach_pair_metrics(row: dict[str, Any], f0: dict[str, Any]) -> dict[str, Any]:
    if row.get("policy") not in {"M0_corner_count_gate_geometry_medoid", "M1"}:
        return row
    for field in (
        "paid_valid_savings_vs_f0",
        "raw_paid_attempt_savings_vs_f0",
        "paired_complete_case_quality_delta_vs_f0",
        "reference_evaluable_autonomous_delivery_mitt_delta_vs_f0",
        "prefix_full5_selected_output_instability",
        "corner_count_changed_vs_f0",
        "continuous_geometry_delta_vs_f0",
    ):
        row.setdefault(field, None)
    f0_cost_supported = f0.get("paid_valid_submissions") == 5
    row["paired_rows_status"] = "paired_same_task_replicate_order" if f0_cost_supported else "historical_f0_support_shortfall"
    if f0_cost_supported and row.get("paid_valid_submissions") is not None:
        row["paid_valid_savings_vs_f0"] = f0["paid_valid_submissions"] - row["paid_valid_submissions"]
        row["frozen_geometry_submission_savings_vs_f0"] = row["paid_valid_savings_vs_f0"]
    if f0_cost_supported and f0.get("raw_paid_attempts") is not None and row.get("raw_paid_attempts") is not None:
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
            row["continuous_geometry_delta_vs_f0"] = _continuous_geometry_delta(selected, f0_selected)
    return row


def _stable_order(candidates: list[dict[str, Any]], task: str, replicate: int, seed: int) -> list[dict[str, Any]]:
    digest = hashlib.sha256(f"{seed}|{task}|{replicate}".encode()).digest()
    rng = random.Random(int.from_bytes(digest[:8], "big"))
    order = list(candidates)
    rng.shuffle(order)
    return order


def _order_signature(order: list[dict[str, Any]]) -> str:
    return hashlib.sha256("|".join(_key(row) for row in order).encode()).hexdigest()


def _na(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value)


def _write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore", lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow({field: _na(row.get(field)) for field in fieldnames})


PRIMARY_METRICS = (
    ("stop_at_3_probability", "stop@3", "replicate_support", "policy_development_simulation"),
    ("incremental_stop_at_4_probability", "incremental_stop@4", "replicate_support", "policy_development_simulation"),
    ("reach5_probability", "reach5", "replicate_support", "policy_development_simulation"),
    ("mean_frozen_geometry_submissions_used", "mean frozen geometry submissions used", "paid_valid_replicate_support", "historical_replay_count"),
    ("mean_historical_candidates_examined", "mean historical candidates examined", "raw_attempt_replicate_support", "historical_replay_count"),
    ("mean_frozen_geometry_submission_savings_vs_f0", "frozen geometry submission-count delta vs F0", "paired_cost_replicate_support", "historical_replay_count"),
    ("mean_historical_candidates_examined_savings_vs_f0", "historical candidates-examined delta vs F0", "paired_cost_replicate_support", "historical_replay_count"),
    ("mean_raw_structural_failure_attempts", "raw structural-failure candidates used", "replicate_support", "structural_audit_lane"),
    ("mean_repair_required_attempts", "frozen repair-required candidates used", "replicate_support", "repair_audit_lane"),
    ("mean_current_normalizer_invalid_attempts", "current-normalizer-invalid frozen candidates used", "replicate_support", "parser_version_sensitivity"),
    ("mean_formal_replacement_candidates_used", "formal replacement candidates used", "replicate_support", "assignment_audit_lane"),
    ("historical_counterfactual_support_shortfall_probability", "historical counterfactual support shortfall", "replicate_support", "historical_support_diagnostic"),
    ("selected_output_probability", "selected-output probability", "replicate_support", "policy_development_simulation"),
    ("autonomous_non_delivery_probability", "autonomous non-delivery probability", "autonomous_non_delivery_replicate_support", "autonomous_delivery_sensitivity"),
    ("expert_escalation_probability", "expert-escalation-required probability", "expert_escalation_replicate_support", "expert_fallback_trigger"),
    ("mean_public_gt_quality", "public-GT quality", "complete_case_quality_replicate_support", "diagnostic_complete_case"),
    ("mean_reference_evaluable_autonomous_delivery_quality", "reference-evaluable autonomous-delivery mITT quality", "reference_evaluable_autonomous_delivery_replicate_support", "autonomous_delivery_sensitivity"),
    ("mean_paired_complete_case_quality_delta_vs_f0", "public-GT complete-case paired delta vs F0", "paired_complete_case_quality_replicate_support", "diagnostic_complete_case"),
    ("mean_reference_evaluable_autonomous_delivery_mitt_delta_vs_f0", "reference-evaluable autonomous-delivery mITT paired delta vs F0", "paired_reference_evaluable_autonomous_delivery_replicate_support", "autonomous_delivery_sensitivity"),
    ("instability_probability", "prefix-vs-full5 selected-output instability", "paired_instability_replicate_support", "diagnostic_complete_case"),
    ("corner_count_change_probability", "corner-count change vs F0", "paired_corner_count_replicate_support", "diagnostic_complete_case"),
    ("mean_continuous_geometry_delta_vs_f0", "continuous geometry delta vs F0", "paired_geometry_delta_replicate_support", "diagnostic_complete_case"),
    ("selected_structural_invalidity_probability", "raw structural-failure probability among selected outputs", "selected_structural_invalidity_replicate_support", "structural_audit_lane"),
    ("selected_repair_probability", "frozen-repair probability among selected outputs", "selected_output_replicate_support", "repair_audit_lane"),
    ("selected_current_normalizer_evaluable_probability", "current-normalizer evaluable probability among selected outputs", "selected_output_replicate_support", "parser_version_sensitivity"),
    ("selected_formal_replacement_probability", "formal-replacement probability among selected outputs", "selected_output_replicate_support", "assignment_audit_lane"),
    ("supported_multimodality_probability", "supported multimodality encountered", "replicate_support", "separate_harm_lane"),
)


def _mean(values: Iterable[Any]) -> float | None:
    numbers = [float(value) for value in values if value is not None]
    return statistics.mean(numbers) if numbers else None


def _bootstrap(task_values: dict[str, float], building_by_task: dict[str, str], seed: int, draws: int = 1000) -> tuple[float | None, float | None, int, int]:
    if not task_values:
        return None, None, 0, draws
    by_building: dict[str, list[float]] = defaultdict(list)
    for task, value in task_values.items():
        by_building[building_by_task.get(task, "")].append(value)
    blocks = {building: values for building, values in by_building.items() if values}
    if not blocks:
        return None, None, 0, draws
    rng = random.Random(seed)
    buildings = list(blocks)
    estimates = []
    for _ in range(draws):
        sampled_values = []
        for _ in buildings:
            sampled_values.extend(blocks[rng.choice(buildings)])
        if sampled_values:
            estimates.append(statistics.mean(sampled_values))
    if not estimates:
        return None, None, 0, draws
    estimates.sort()
    success, failed = len(estimates), draws - len(estimates)
    return estimates[int(0.025 * (success - 1))], estimates[int(0.975 * (success - 1))], success, failed


def operating_rows(rows: list[dict[str, Any]], tasks: dict[str, dict[str, Any]], seed: int, sensitivity_counts: dict[str, int] | None = None) -> list[dict[str, Any]]:
    output: list[dict[str, Any]] = []
    primary = [row for row in rows if row["estimand_scope"] == "historical_population_replay_78"]
    primary_tasks = {str(row["base_task_id"]) for row in primary}
    primary_buildings = {str(row["building_id"]) for row in primary}
    for policy in ("F0", "M0_corner_count_gate_geometry_medoid", "M1"):
        policy_rows = [row for row in primary if row["policy"] == policy]
        for summary_field, label, support_field, role in PRIMARY_METRICS:
            if policy == "F0" and "vs F0" in label:
                continue
            task_values = {
                str(row["base_task_id"]): _float(row.get(summary_field))
                for row in policy_rows
                if _float(row.get(summary_field)) is not None
            }
            task_values = {task: value for task, value in task_values.items() if value is not None}
            estimate = _mean(task_values.values())
            by_building = {task: tasks[task].get("building_id", "") for task in task_values}
            if task_values:
                low, high, bootstrap_success, bootstrap_fail = _bootstrap(task_values, by_building, seed)
            else:
                low, high, bootstrap_success, bootstrap_fail = None, None, 0, 0
            metric_support = sum(int(row.get(support_field) or 0) for row in policy_rows)
            replicate_total = sum(int(row.get("replicate_support") or 0) for row in policy_rows)
            status = "ready_development_descriptive" if estimate is not None else "not_identifiable"
            reason = "historical frozen-pool submission-count replay; not paid deployment cost" if role == "historical_replay_count" else "reference-evaluable autonomous-delivery sensitivity; not the full expert-fallback workflow" if role == "autonomous_delivery_sensitivity" else "13-building block sensitivity after task-equal aggregation" if task_values else "no estimable task values"
            output.append({
                "cohort": "historical_population_replay_78",
                "policy": policy,
                "comparator": "F0" if "vs F0" in label else "",
                "metric": label,
                "estimate": estimate,
                "task_support": len(task_values),
                "task_total": len(primary_tasks),
                "replicate_support": metric_support,
                "replicate_total": replicate_total,
                "building_support": len({by_building[task] for task in task_values}),
                "building_total": len(primary_buildings),
                "estimand_role": role,
                "bootstrap_unit": "building" if task_values else "not_applicable",
                "bootstrap_draws": 1000 if task_values else None,
                "bootstrap_seed": seed if task_values else None,
                "bootstrap_success_draws": bootstrap_success if task_values else None,
                "bootstrap_fail_draws": bootstrap_fail if task_values else None,
                "ci_low": low,
                "ci_high": high,
                "status": status,
                "reason": reason,
            })

    for label, count in (sensitivity_counts or {}).items():
        output.append({
            "cohort": "admission_sensitivity_inventory",
            "policy": "NOT_A_POLICY_COMPARISON",
            "comparator": "",
            "metric": f"tasks_with_k>=5__{label}",
            "estimate": count / 78,
            "task_support": count,
            "task_total": 78,
            "replicate_support": None,
            "replicate_total": None,
            "building_support": 13,
            "building_total": 13,
            "estimand_role": "admission_version_or_roster_sensitivity",
            "bootstrap_unit": "not_applicable",
            "status": "development_descriptive_only",
            "reason": f"deterministic inventory: {count}/78; not the primary historical replay and not prospective candidate exhaustion",
        })
    output.extend([
        {"cohort": "harm_lane", "policy": "ALL", "metric": "actual_expert_reference_harm", "estimand_role": "actual_harm", "status": "source_absent", "reason": "actual expert/reference delivery-harm source absent; no exact or building interval is estimable"},
        {"cohort": "harm_lane", "policy": "F0/M0_corner_count_gate_geometry_medoid/M1", "metric": "selected_raw_structural_failure", "estimand_role": "structural_audit_lane", "status": "ready_development_descriptive", "reason": "raw failure is retained even when frozen repaired geometry is admitted; this is not expert delivery harm"},
        {"cohort": "harm_lane", "policy": "M0_corner_count_gate_geometry_medoid/M1", "metric": "material_geometry_delta", "estimand_role": "geometry", "status": "source_absent", "reason": "continuous geometry delta is reported; no frozen materiality tolerance exists"},
        {"cohort": "model_status", "policy": "M2", "metric": "worker_portrait", "status": M2_STATUS, "reason": "leakage-safe training-fold estimator not implemented in this correction"},
        {"cohort": "model_status", "policy": "M3", "metric": "posttask_meta", "status": M3_STATUS, "reason": "canonical join exists; pre-peer-view timing remains unbound and first-route use is prohibited"},
        {"cohort": "workflow_identifiability", "policy": "M1_with_expert_fallback", "metric": "final delivery quality after expert fallback", "estimand_role": "full_workflow_quality", "status": "not_identifiable", "reason": "expert fallback outputs and their reference-evaluable quality are absent"},
        {"cohort": "workflow_identifiability", "policy": "M1_with_expert_fallback", "metric": "total deployment cost including expert fallback", "estimand_role": "full_workflow_cost", "status": "not_identifiable", "reason": "expert minutes, expert output cost, future invalid/replacement, availability and scheduling cost are absent"},
        {"cohort": "workflow_identifiability", "policy": "ALL", "metric": "paid deployment cost or savings", "estimand_role": "production_cost", "status": "not_identifiable", "reason": "historical replay counts frozen geometry candidates; it does not estimate live invalid, repair, replacement, availability, scheduling or expert cost"},
        {"cohort": "harm_lane", "policy": "ALL", "metric": "GT_reference_conflict", "estimand_role": "reference_conflict", "status": "ready_current_operational_audit_zero_declared", "reason": "separate lane; not actual expert delivery harm and not proof of zero upstream GT error"},
    ])
    return output


def summarize_rows(
    rows: list[dict[str, Any]],
    tasks: dict[str, dict[str, Any]],
    replicates: int,
    *,
    estimand_scope: str = "historical_population_replay_78",
) -> list[dict[str, Any]]:
    """Collapse replicate rows before writing: one auditable row per task and policy."""
    grouped: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[str(row["base_task_id"]), str(row["policy"])].append(row)
    summary = []
    for (task_id, policy), group in sorted(grouped.items()):
        task = tasks[task_id]
        signature_count = len({row["order_signature"] for row in group})
        outcome_probabilities = {"stop@3": None, "stop@4": None, "reach5": None, "historical_shortfall": None}
        if policy in {"F0", "M0_corner_count_gate_geometry_medoid", "M1"}:
            statuses = [row.get("status") for row in group]
            outcome_probabilities = {
                "stop@3": statuses.count("stop@3") / len(statuses),
                "stop@4": statuses.count("stop@4") / len(statuses),
                "reach5": sum(row.get("reach5") is True for row in group) / len(group),
                "historical_shortfall": statuses.count("historical_counterfactual_support_shortfall") / len(statuses),
            }
            assert abs(sum(outcome_probabilities.values()) - 1.0) < 1e-12
        def probability(field: str, expected: Any = True) -> float | None:
            values = [row.get(field) for row in group if row.get(field) is not None]
            return sum(value == expected for value in values) / len(values) if values else None
        def mean_field(field: str) -> float | None:
            return _mean(row.get(field) for row in group)
        summary.append({
            "estimand_scope": estimand_scope,
            "fold": "policy_development_simulation",
            "base_task_id": task_id,
            "building_id": task.get("building_id", ""),
            "condition": "manual",
            "policy": policy,
            "replicate_support": len(group),
            "order_signature_support": signature_count,
            "candidate_permutation_n": group[0]["candidate_permutation_n"],
            "stop_at_3_probability": outcome_probabilities["stop@3"],
            "incremental_stop_at_4_probability": outcome_probabilities["stop@4"],
            "reach5_probability": outcome_probabilities["reach5"],
            "cap_resolved_probability": probability("status", "cap_resolved"),
            "historical_counterfactual_support_shortfall_probability": outcome_probabilities["historical_shortfall"],
            "unresolved_probability": probability("unresolved"),
            "policy_failure_probability": probability("status", "policy_failure_no_output"),
            "autonomous_non_delivery_probability": probability("autonomous_non_delivery"),
            "expert_escalation_probability": probability("expert_escalation_required"),
            "status_probability_fixed_k5": probability("status", "fixed_k5"),
            "mean_raw_paid_attempts": mean_field("raw_paid_attempts"),
            "mean_paid_valid_submissions": mean_field("paid_valid_submissions"),
            "mean_historical_candidates_examined": mean_field("historical_candidates_examined"),
            "mean_frozen_geometry_submissions_used": mean_field("frozen_geometry_submissions_used"),
            "mean_invalid_attempts": mean_field("invalid_attempts"),
            "mean_replacement_attempts": mean_field("replacement_attempts"),
            "mean_metric_invalid_attempts": mean_field("metric_invalid_attempts"),
            "mean_raw_structural_failure_attempts": mean_field("raw_structural_failure_attempts"),
            "mean_repair_required_attempts": mean_field("repair_required_attempts"),
            "mean_current_normalizer_invalid_attempts": mean_field("current_normalizer_invalid_attempts"),
            "mean_formal_replacement_candidates_used": mean_field("formal_replacement_candidates_used"),
            "mean_paid_valid_savings_vs_f0": mean_field("paid_valid_savings_vs_f0"),
            "mean_raw_paid_attempt_savings_vs_f0": mean_field("raw_paid_attempt_savings_vs_f0"),
            "mean_frozen_geometry_submission_savings_vs_f0": mean_field("frozen_geometry_submission_savings_vs_f0"),
            "mean_historical_candidates_examined_savings_vs_f0": mean_field("historical_candidates_examined_savings_vs_f0"),
            "mean_public_gt_quality": mean_field("public_gt_quality"),
            "mean_reference_evaluable_autonomous_delivery_quality": mean_field("reference_evaluable_autonomous_delivery_quality"),
            "mean_paired_complete_case_quality_delta_vs_f0": mean_field("paired_complete_case_quality_delta_vs_f0"),
            "mean_reference_evaluable_autonomous_delivery_mitt_delta_vs_f0": mean_field("reference_evaluable_autonomous_delivery_mitt_delta_vs_f0"),
            "instability_probability": probability("prefix_full5_selected_output_instability"),
            "corner_count_change_probability": probability("corner_count_changed_vs_f0"),
            "mean_continuous_geometry_delta_vs_f0": mean_field("continuous_geometry_delta_vs_f0"),
            "selected_structural_invalidity_probability": probability("selected_structural_invalidity"),
            "selected_repair_probability": probability("selected_repair_applied"),
            "selected_current_normalizer_evaluable_probability": probability("selected_current_normalizer_evaluable"),
            "selected_formal_replacement_probability": probability("selected_formal_replacement_candidate"),
            "selected_output_probability": sum(bool(row.get("selected_annotation_id")) for row in group) / len(group),
            "supported_multimodality_probability": probability("supported_multimodal_encountered"),
            "selected_output_replicate_support": sum(bool(row.get("selected_annotation_id")) for row in group),
            "raw_attempt_replicate_support": sum(row.get("raw_paid_attempts") is not None for row in group),
            "paid_valid_replicate_support": sum(row.get("paid_valid_submissions") is not None for row in group),
            "complete_case_quality_replicate_support": sum(row.get("public_gt_quality") is not None for row in group),
            "reference_evaluable_autonomous_delivery_replicate_support": sum(row.get("reference_evaluable_autonomous_delivery_quality") is not None for row in group),
            "paired_cost_replicate_support": sum(row.get("raw_paid_attempt_savings_vs_f0") is not None for row in group),
            "paired_complete_case_quality_replicate_support": sum(row.get("paired_complete_case_quality_delta_vs_f0") is not None for row in group),
            "paired_reference_evaluable_autonomous_delivery_replicate_support": sum(row.get("reference_evaluable_autonomous_delivery_mitt_delta_vs_f0") is not None for row in group),
            "paired_instability_replicate_support": sum(row.get("prefix_full5_selected_output_instability") is not None for row in group),
            "paired_corner_count_replicate_support": sum(row.get("corner_count_changed_vs_f0") is not None for row in group),
            "paired_geometry_delta_replicate_support": sum(row.get("continuous_geometry_delta_vs_f0") is not None for row in group),
            "selected_structural_invalidity_replicate_support": sum(row.get("selected_structural_invalidity") is not None for row in group),
            "autonomous_non_delivery_replicate_support": sum(row.get("autonomous_non_delivery") is not None for row in group),
            "expert_escalation_replicate_support": sum(row.get("expert_escalation_required") is not None for row in group),
            "paired_rows_status": group[0].get("paired_rows_status"),
            "status": "development_descriptive_only",
        })
    return summary


def run(root: Path = ROOT, output_dir: Path | None = None, *, replicates: int = DEFAULT_REPLICATES, seed: int = SEED) -> Path:
    if replicates < 1000:
        raise ValueError("at least 1000 replicates are required")
    data = load_frozen_inputs(root)
    output_dir = output_dir or root / "analysis_results" / "topology_sequential_preflight_20260818_v3"
    if output_dir.exists():
        raise FileExistsError(f"refusing to overwrite output directory: {output_dir}")
    output_dir.mkdir(parents=True)

    replicate_rows: list[dict[str, Any]] = []
    for replicate in range(replicates):
        for task_id, task in data["tasks"].items():
            order = _stable_order(data["candidates"][task_id], task_id, replicate, seed)
            signature = _order_signature(order)
            results = [
                run_f0(order, task_id),
                run_m0(order, task_id),
                run_m1(order, task_id),
            ]
            converted = [_result_row(task, replicate, signature, result) for result in results]
            f0 = next(row for row in converted if row["policy"] == "F0")
            f0["paired_rows_status"] = "baseline_same_order"
            for row in converted:
                attach_pair_metrics(row, f0)
                replicate_rows.append(row)
            assert len({row["order_signature"] for row in converted}) == 1

    primary_task_ids = set(data["tasks"])
    unsupported = {
        task_id for task_id, candidates in data["candidates"].items()
        if len(_admitted_prefixes(candidates)["accepted"]) < 5
    }
    if len(primary_task_ids) != 78 or unsupported:
        raise AssertionError(f"frozen-pool historical replay support drifted: {len(primary_task_ids)}, {sorted(unsupported)}")
    primary_tasks = {task_id: data["tasks"][task_id] for task_id in primary_task_ids}
    primary_replicates = replicate_rows
    expected_per_policy = len(primary_task_ids) * replicates
    counts = Counter(row["policy"] for row in primary_replicates)
    if counts != Counter({"F0": expected_per_policy, "M0_corner_count_gate_geometry_medoid": expected_per_policy, "M1": expected_per_policy}):
        raise AssertionError(f"primary paired row counts drifted: {dict(counts)}")
    paired_orders: dict[tuple[str, int], set[str]] = defaultdict(set)
    for row in primary_replicates:
        paired_orders[str(row["base_task_id"]), int(row["replicate_id"])].add(str(row["order_signature"]))
    if len(paired_orders) != expected_per_policy or any(len(signatures) != 1 for signatures in paired_orders.values()):
        raise AssertionError("primary F0/M0/M1 rows are not exactly paired on task, replicate and order")

    summary_rows = summarize_rows(primary_replicates, primary_tasks, replicates, estimand_scope="historical_population_replay_78")
    _write_csv(output_dir / "PREFIX_POLICY_METRICS.csv", summary_rows, [
        "estimand_scope", "fold", "base_task_id", "building_id", "condition", "policy", "replicate_support", "order_signature_support", "candidate_permutation_n", "stop_at_3_probability", "incremental_stop_at_4_probability", "reach5_probability", "cap_resolved_probability", "historical_counterfactual_support_shortfall_probability", "unresolved_probability", "policy_failure_probability", "autonomous_non_delivery_probability", "expert_escalation_probability", "status_probability_fixed_k5", "mean_historical_candidates_examined", "mean_frozen_geometry_submissions_used", "mean_raw_structural_failure_attempts", "mean_repair_required_attempts", "mean_current_normalizer_invalid_attempts", "mean_formal_replacement_candidates_used", "mean_frozen_geometry_submission_savings_vs_f0", "mean_historical_candidates_examined_savings_vs_f0", "mean_public_gt_quality", "mean_reference_evaluable_autonomous_delivery_quality", "mean_paired_complete_case_quality_delta_vs_f0", "mean_reference_evaluable_autonomous_delivery_mitt_delta_vs_f0", "instability_probability", "corner_count_change_probability", "mean_continuous_geometry_delta_vs_f0", "selected_structural_invalidity_probability", "selected_repair_probability", "selected_current_normalizer_evaluable_probability", "selected_formal_replacement_probability", "selected_output_probability", "supported_multimodality_probability", "selected_output_replicate_support", "raw_attempt_replicate_support", "paid_valid_replicate_support", "complete_case_quality_replicate_support", "reference_evaluable_autonomous_delivery_replicate_support", "paired_cost_replicate_support", "paired_complete_case_quality_replicate_support", "paired_reference_evaluable_autonomous_delivery_replicate_support", "paired_instability_replicate_support", "paired_corner_count_replicate_support", "paired_geometry_delta_replicate_support", "selected_structural_invalidity_replicate_support", "autonomous_non_delivery_replicate_support", "expert_escalation_replicate_support", "paired_rows_status", "status",
    ])
    operating = operating_rows(summary_rows, data["tasks"], seed, data["sensitivity_counts"])
    _write_csv(output_dir / "PREFLIGHT_OPERATING_CHARACTERISTICS.csv", operating, ["cohort", "policy", "comparator", "metric", "estimate", "task_support", "task_total", "replicate_support", "replicate_total", "building_support", "building_total", "estimand_role", "bootstrap_unit", "bootstrap_draws", "bootstrap_seed", "bootstrap_success_draws", "bootstrap_fail_draws", "ci_low", "ci_high", "status", "reason"])

    topology_distribution = dict(Counter(len(data["candidates"][task]) for task in data["tasks"]))
    structural_distribution = dict(Counter(data["tasks"][task]["structural_candidate_count"] for task in data["tasks"]))
    readiness = {
        **FLAGS,
        "seed": seed,
        "replicates": replicates,
        "supersedes": [
            {"artifact": "analysis_results/topology_sequential_preflight_20260818_v1", "status": "superseded_development_descriptive_only"},
            {"artifact": "analysis_results/topology_sequential_preflight_20260818_v2", "status": "superseded_development_descriptive_only"},
        ],
        "denominator": {
            "status": "ready",
            "primary_historical_replay_tasks": len(primary_task_ids),
            "primary_historical_replay_buildings": len({primary_tasks[task]["building_id"] for task in primary_tasks}),
            "frozen_geometry_pool_candidates": sum(len(rows) for rows in data["candidates"].values()),
            "frozen_geometry_pool_distribution": topology_distribution,
            "raw_structural_passed_distribution": structural_distribution,
            "admission_sensitivity_tasks_with_k_ge_5": data["sensitivity_counts"],
            "interpretation": "78 frozen C1 geometry-pool tasks are primary; current normalizer, raw structural pass and current20 roster are sensitivity inventories only",
        },
        "current20_roster_sensitivity": {"status": "development_descriptive_only", "count": len(LIVE_WORKERS), "worker_ids": sorted(LIVE_WORKERS), "not_primary": {"14": "administrative_exclusion", "18": "later_withdrawn_but_retained_in_historical_C1_replay", "27": "later_withdrawn_but_retained_in_historical_C1_replay"}},
        "topology_sequential_f0_m0_m1": {"status": "development_descriptive_only", "reason": "78 frozen-pool tasks, identical task-replicate-order rows and task-equal aggregation"},
        "m0_corner_count_gate_geometry_medoid": {"status": "development_descriptive_only", "reason": "stopping reads repaired point count/2; selected output uses full geometry-medoid similarity, so timing and resolution both differ from F0"},
        "m1_conservative_development_gate": {"status": "recomputed_not_formal_policy", "rule": {"k3": "3:0", "k4": "4:0 or 3:1", "k5": "5:0 or 4:1; otherwise unresolved/expert escalation"}},
        "quality_estimand": {"status": "ready_descriptive", "formal_rule": "superiority", "complete_case": "diagnostic only", "autonomous_delivery_sensitivity": "unresolved/autonomous no-output=0; resolved output with unavailable eligible reference remains missing, so this is reference-evaluable mITT rather than full ITT", "expert_fallback_workflow": "not_identifiable_without_expert_output_quality", "ni_margin": "not_created_or_selected"},
        "cost_estimand": {"status": "historical_submission_count_only", "scope": "78 frozen C1 tasks already having at least five geometry-pool candidates", "excluded_costs": ["future invalid/repair/replacement attempts", "expert fallback", "availability", "scheduling"], "production_cost_claim_allowed": False},
        "repair_binding": {"status": "development_replay_only", "canonical_annotation_ids": data["repair_ids"], "raw_structural_failure_retained": True, "formal_c1_derivation": False},
        "parser_version_sensitivity": {"status": "development_descriptive_only", "current_normalizer_invalid_ids": data["normalizer_invalid_ids"], "changes_primary_admission": False},
        "m2_worker_portrait": {"status": M2_STATUS, "risk_slope": "disabled"},
        "m3_posttask_meta": {"status": M3_STATUS, "first_route_meta": "excluded", "causal_routing_effect": "not_claimed"},
        "actual_expert_reference_harm": {"status": "source_absent", "code": "actual_harm_source_absent", "confidence_or_upper_bound": "not_reported"},
        "gt_reference_conflict": {"status": "ready", "code": "ready_current_operational_audit_zero_declared", "gt_issue_declared": data["reference_audit"].get("gt_issue_declared"), "pending": data["reference_audit"].get("n_pending_contexts", 0), "review_queue_rows": len(data["conflict_queue_rows"]), "caveat": "does not establish absence of all upstream GT error and is not actual expert delivery harm"},
        "availability_and_main_candidate_inventory": {"status": "not_identifiable", "code": "live_feasibility_inputs_absent", "budget": "20x50=1000"},
        "prospective_shadow_development_readiness": {"status": "conditional_go_shadow_only", "scope": "simulation_only", "formal_policy_frozen": False, "reason": "shadow may record autonomous stops and expert-escalation triggers; expert fallback quality/cost and formal Stage 3 amendment remain absent"},
        "actual_live_stops_main_readiness": {"status": "not_ready", "reason": "no live assignment/availability proof and actual harm source absent"},
    }
    (output_dir / "PREFLIGHT_READINESS.json").write_text(json.dumps(readiness, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")

    input_paths = [
        c1_root(root) / "geometry_task_crowd_structure_C1.csv",
        c1_root(root) / "c1_geometry_pool_eligibility.csv",
        c1_root(root) / "c1_canonical_geometry.jsonl",
        c1_root(root) / "geometry_pairwise_similarity_C1.csv",
        c1_root(root) / "c1_geometry_repair_audit.csv",
        c1_root(root) / "c1_gt_quality_evidence.csv",
        c1_root(root) / "structural_validation_analysis.csv",
        c1_root(root) / "c1_task_building_binding.csv",
        c1_root(root) / "c1_operational_reference_audit.json",
        c1_root(root) / "c1_gt_conflict_review_queue.csv",
    ]
    manifest = {
        "artifact_role": "TOPOLOGY_SEQUENTIAL_PREFLIGHT",
        "schema_version": "topology_sequential_preflight_v3",
        **FLAGS,
        "seed": seed,
        "replicates": replicates,
        "input_sha256": {str(path.relative_to(root)): _sha256(path) for path in input_paths},
        "code_sha256": _sha256(Path(__file__).resolve()),
        "asserted_frozen_facts": {
            "primary_historical_replay_tasks": 78,
            "primary_historical_replay_buildings": 13,
            "frozen_geometry_pool_candidates": 594,
            "frozen_geometry_pool_distribution": {"5": 66, "22": 12},
            "admission_sensitivity_tasks_with_k_ge_5": data["sensitivity_counts"],
            "historical_worker_candidate_counts": {"W18": 26, "W27": 26, "W14": 0},
            "formal_replacements": {"W34": 14, "W1": 1},
            "outside_assignment_excluded": data["outside_assignment_rows"],
            "repair_ids": data["repair_ids"],
            "current_normalizer_invalid_ids": data["normalizer_invalid_ids"],
        },
        "estimands": {
            "primary": "task-equal F0/M0_corner_count_gate_geometry_medoid/M1 paired historical replay on the same 78 frozen geometry-pool tasks and task-replicate-order rows",
            "admission_sensitivity": "current normalizer, raw structural pass and current20 roster are deterministic support inventories only",
            "quality": {"complete_case_public_gt": "diagnostic", "reference_evaluable_autonomous_delivery_mitt": "autonomous unresolved/no-output=0; resolved output with unavailable eligible reference=missing", "full_m1_expert_fallback_workflow": "not_identifiable", "formal_rule": "superiority"},
            "cost": "historical frozen-geometry submission count only; paid deployment cost is not identifiable",
        },
        "supersedes": [
            {"path": "analysis_results/topology_sequential_preflight_20260818_v1", "status": "superseded_development_descriptive_only"},
            {"path": "analysis_results/topology_sequential_preflight_20260818_v2", "status": "superseded_development_descriptive_only"},
        ],
        "output_files": ["PREFLIGHT_DATA_AND_PROVENANCE.md", "PREFIX_POLICY_METRICS.csv", "PREFLIGHT_OPERATING_CHARACTERISTICS.csv", "PREFLIGHT_READINESS.json", "analysis_manifest.json"],
    }
    (output_dir / "analysis_manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    provenance = f"""# HOHONET topology sequential preflight v3

开发诊断工件；不构成科学结论、正式政策冻结或 Main 启动依据。v1/v2 均为 `superseded_development_descriptive_only`。

- development_only: true
- diagnostic_pre_stage3: true
- scientific_conclusion_prohibited: true
- block3: false
- formal_policy_frozen: false
- formal_profile_frozen: false

## 冻结历史 replay 准入

主分析使用78个 frozen C1 manual geometry-pool task、594条正式候选和13个building。`frozen_geometry_pool_member=true` 是本次 development replay 的准入条件，不等同正式 C1 analysis eligibility。W18/W27 后续退出不追溯删除其已完成的 C1 记录；W14、7条 outside-assignment 以及未进入冻结pool的记录继续排除。15条正式 replacement 已包含在冻结pool中。

两条 owner-confirmed 偶发多点提交使用既有冻结 repaired geometry，标记 `preflight_development_repair_binding=true`、`formal_c1_derivation=false`；原始 structural failure、repair requirement 和 attribution 均保留。该处置不扩展 parser amendment 对正式 Q_GT/peer/LOO 或未来 live delivery 的授权。冻结有效但当前 normalizer 失败的 `{NORMALIZER_DRIFT_ID}` 保留在主 replay，并单独标记版本漂移。

## 主 estimand、顺序与敏感性

seed={seed}，replicates={replicates}。F0、M0_corner_count_gate_geometry_medoid、M1在每个task/replicate使用完全相同的无放回order，共{78 * replicates * 3}个政策行；先在task内汇总，再做78个task等权平均。cluster和medoid读取冻结 pairwise similarity，不重跑旧 parser。

主口径为 frozen pool 78任务。current normalizer、raw structural pass、二者交集以及current20 roster仅报告确定性support敏感性：`{json.dumps(data['sensitivity_counts'], ensure_ascii=False, sort_keys=True)}`。这些口径不是独立政策比较，不估计未来 candidate exhaustion 或 transportability。

M0停止门只读取corner count，最终输出使用geometry medoid，因此其准确名称是 `corner-count stopping gate with geometry-medoid selection`。M1开发门仍为k=3仅3:0，k=4仅4:0或3:1，k=5仅5:0或4:1；其他k=5状态为`unresolved_expert_escalation_required`，不是`policy_failure`。

## 质量、成本与边界

public-GT complete-case质量仅作诊断。自主未交付记0的结果只称 `reference-evaluable autonomous-delivery mITT sensitivity`；成功输出若缺少合格reference仍保持missing。包含expert fallback的最终质量和总成本均为`not_identifiable`。E[K]及其差值只表示冻结历史几何候选的submission-count replay，不代表paid production cost或生产节省。

raw structural failure、repair、formal replacement、current-normalizer drift、prefix instability、multimodality、GT conflict和actual expert harm分 lane 报告；actual expert/reference delivery harm仍为`source_absent`。M2状态为`{M2_STATUS}`；M3状态为`{M3_STATUS}`。post-task meta不进入首次路由，不声称causal routing effect。
"""
    (output_dir / "PREFLIGHT_DATA_AND_PROVENANCE.md").write_text(provenance, encoding="utf-8", newline="\n")
    return output_dir


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", type=Path, default=ROOT)
    parser.add_argument("--output-dir", type=Path, default=None)
    parser.add_argument("--replicates", type=int, default=DEFAULT_REPLICATES)
    parser.add_argument("--seed", type=int, default=SEED)
    args = parser.parse_args()
    output = run(args.repo_root.resolve(), args.output_dir.resolve() if args.output_dir else None, replicates=args.replicates, seed=args.seed)
    print(output)


if __name__ == "__main__":
    main()
