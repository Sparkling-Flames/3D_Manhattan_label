from __future__ import annotations

import json
import hashlib
import math
import random
import sys
from collections import Counter, defaultdict, deque
from pathlib import Path
from typing import Any

import numpy as np

_PROJECT_ROOT = Path(__file__).resolve().parents[3]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from tools.thesis_main.analysis.c1_live_collection_monitor import read_csv, safe, truthy, write_csv, write_json
from tools.thesis_main.analysis.vfinal_artifact_utils import sha256_file


RISK_CONTRACT = _PROJECT_ROOT / "docs" / "thesis_main" / "C2B_RISK_DESIGN_CONTRACT_v1.json"
DESIGN_THRESHOLDS = _PROJECT_ROOT / "docs" / "thesis_main" / "C2B_DESIGN_SELECTION_THRESHOLDS.json"
PREDISPATCH_AMENDMENT = _PROJECT_ROOT / "docs" / "thesis_main" / "C2B_PREDISPATCH_METHOD_AMENDMENT_v1.json"


def _load_risk_contract() -> tuple[dict[str, Any], str]:
    try:
        contract = json.loads(RISK_CONTRACT.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError("C2-B risk design contract unavailable") from exc
    if contract.get("schema_version") != "paper_a_c2b_risk_design_contract_v1":
        raise ValueError("unsupported C2-B risk design contract")
    return contract, sha256_file(RISK_CONTRACT)


def _load_thresholds(path: Path = DESIGN_THRESHOLDS) -> tuple[dict[str, Any], str]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if payload.get("schema_version") not in {
        "paper_a_c2b_design_selection_thresholds_v1",
        "paper_a_c2b_design_selection_thresholds_v2",
    }:
        raise ValueError("unsupported C2-B design threshold manifest")
    return payload, sha256_file(path)


def _load_predispatch_amendment() -> tuple[dict[str, Any], str]:
    payload = json.loads(PREDISPATCH_AMENDMENT.read_text(encoding="utf-8"))
    if (
        payload.get("schema_version") != "paper_a_c2b_predispatch_method_amendment_v1"
        or payload.get("status") != "normative"
        or payload.get("effective_timing") != "before_any_C2_worker_outcome"
        or payload.get("uniform_application") != ["D8", "D10", "D12"]
    ):
        raise ValueError("invalid C2-B pre-dispatch amendment")
    return payload, sha256_file(PREDISPATCH_AMENDMENT)


ASSIGNMENT_FIELDS = [
    "round_id", "worker_id", "task_id", "base_task_id", "task_stratum",
    "image_id", "dataset_group", "image_path", "risk_design_score_A",
    "assignment_batch", "c2_component", "design_id", "design_manifest_sha256",
    "selection_role", "selection_reason", "maximin_distance_at_selection", "building_gain", "legacy_curated_priority_used",
]
DESIGN_AUDIT_FIELDS = [
    "design_id", "common_anchor_count", "bridge_per_worker", "unique_bridge_tasks_upper_bound", "unique_bridge_tasks",
    "bridge_search_attempt_count", "stress_bridge_task_count", "stress_bridge_assignment_support",
    "stress_bridge_repeat_support", "deterministic_min_worker_support", "deterministic_min_task_support",
    "min_task_support", "n_assignments", "projected_max_ci_half_width",
    "worker_task_graph_connected", "stratum_balance_valid", "design_method",
    "rank_displacement_gate_role", "feasible", "non_dominated", "failure_reason", "all_failure_gates",
]
WORKER_PROJECTION_FIELDS = [
    "design_id", "worker_id", "current_interval_half_width", "projected_interval_half_width",
    "projection_status", "slope_precision_source",
    "ordinary_support", "stress_support", "common_anchor_support", "bridge_support",
    "unique_image_coverage", "building_coverage", "common_bridge_with_other_min",
    "missing_rate", "structural_failure_rate", "effective_information",
    "expected_fallback_rate", "expected_global_full_divergence", "v1_usable_support",
]
GRAPH_AUDIT_FIELDS = [
    "design_id", "n_workers", "n_tasks", "n_edges", "n_connected_components",
    "worker_task_graph_connected", "bridge_only_n_connected_components", "bridge_only_graph_connected",
    "duplicate_worker_task_count", "minimum_worker_support", "min_bridge_task_support",
    "max_worker_stratum_imbalance", "stress_bridge_task_count", "stress_bridge_assignment_support",
]
TASK_SELECTION_AUDIT_FIELDS = [
    "design_id", "selection_step", "task_id", "base_task_id", "selection_role",
    "risk_design_vector_A", "risk_design_score_A", "risk_design_stratum", "selection_distance", "building_gain",
    "legacy_curated_priority_used", "selection_reason",
]
SIMULATION_FIELDS = [
    "design_id", "seed", "draws", "max_ci_half_width", "median_ci_half_width",
    "q_gt_max_ci_half_width", "risk_slope_max_ci_half_width",
    "rank_stability", "worker_rank_spearman", "top_k_overlap", "mean_rank_displacement",
    "risk_slope_direction_stability", "minimum_worker_support", "minimum_task_support",
    "minimum_worker_support_p05", "minimum_task_support_p05",
    "minimum_worker_support_threshold_probability", "minimum_task_support_threshold_probability",
    "support_extreme_minimum_role",
    "graph_connectivity_probability", "bridge_only_connectivity_probability", "building_coverage", "building_coverage_probability",
    "ordinary_coverage_probability", "stress_coverage_probability", "ordinary_coverage_probability_per_worker", "stress_coverage_probability_per_worker", "expected_assignment_count",
    "uncertainty_fields_used", "known_c1_worker_intercept_sd_resampled", "population_worker_intercept_sd_recorded",
    "simulation_method", "simulation_status",
]


def _int(row: dict[str, Any], *fields: str, default: int = 0) -> int:
    for field in fields:
        value = safe(row.get(field))
        if value:
            return int(float(value))
    return default


def _float(row: dict[str, Any], *fields: str, default: float = math.inf) -> float:
    for field in fields:
        value = safe(row.get(field))
        if value:
            return float(value)
    return default


def _eligible_workers(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    out = []
    for row in rows:
        worker = safe(row.get("worker_id"))
        eligible = safe(row.get("c2b_baseline_eligible") or row.get("c2_candidate_eligible") or row.get("c2_eligible") or row.get("eligible"))
        blocked = truthy(row.get("process_blocker")) or truthy(row.get("independence_blocker"))
        if worker and not blocked and truthy(eligible):
            out.append(row)
    return sorted(out, key=lambda row: safe(row.get("worker_id")))


def _task_stratum(row: dict[str, str]) -> str:
    return safe(row.get("risk_design_stratum")) or "unstratified"


def _task_id(row: dict[str, str]) -> str:
    return safe(row.get("task_id"))


def _anchor_pool(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    return sorted(
        [row for row in rows if _task_id(row) and truthy(row.get("assignment_eligible"))],
        key=lambda row: (_task_stratum(row), _task_id(row)),
    )


def _bridge_pool(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    return sorted(
        [
            row for row in rows
            if _task_id(row)
            and truthy(row.get("assignment_eligible"))
        ],
        key=lambda row: (_task_stratum(row), _task_id(row)),
    )


def _balanced_tasks(rows: list[dict[str, str]], count: int) -> list[dict[str, str]]:
    by_stratum: dict[str, deque[dict[str, str]]] = defaultdict(deque)
    for row in rows:
        by_stratum[_task_stratum(row)].append(row)
    chosen: list[dict[str, str]] = []
    strata = sorted(by_stratum)
    while len(chosen) < count and any(by_stratum.values()):
        for stratum in strata:
            if by_stratum[stratum] and len(chosen) < count:
                chosen.append(by_stratum[stratum].popleft())
    return chosen


def _risk_vector(row: dict[str, str]) -> tuple[float, ...]:
    try:
        vector = json.loads(row.get("risk_design_vector_A", ""))
        if isinstance(vector, list) and len(vector) == 4:
            return tuple(float(value) for value in vector)
    except (TypeError, ValueError, json.JSONDecodeError):
        pass
    return tuple(_float(row, field, default=0.0) for field in ("d_model_feat", "d_model_feat_local_max", "g_model_struct", "d_cal_A"))


def _thresholds_allow_formal_selection(thresholds: dict[str, Any]) -> bool:
    values = thresholds.get("thresholds", thresholds)
    anchors = thresholds.get("common_anchor_requirements", {})
    required = (
        "q_gt_ci_half_width", "risk_slope_ci_half_width", "minimum_worker_rank_spearman",
        "minimum_top_k_overlap", "maximum_mean_rank_displacement", "minimum_worker_support",
        "minimum_task_support", "graph_connectivity_probability", "minimum_building_coverage",
        "building_coverage_probability", "ordinary_coverage_probability", "stress_coverage_probability",
        "minimum_eligible_task_count", "minimum_eligible_building_count",
        "minimum_ordinary_task_count", "minimum_stress_task_count",
    )
    base_ready = (
        thresholds.get("status") == "approved"
        and thresholds.get("formal_selection_allowed") is True
        and all(str(thresholds.get(field, "")).strip() for field in ("approved_by", "approved_at"))
        and int(anchors.get("minimum_count", 0)) >= 2
        and set(anchors.get("required_strata", [])) >= {"ordinary", "stress"}
        and all(values.get(name) not in {None, ""} for name in required)
    )
    if thresholds.get("schema_version") == "paper_a_c2b_design_selection_thresholds_v2":
        derivation = thresholds.get("derivation", {})
        return base_ready and (
            derivation.get("derived_before_candidate_enumeration") is True
            and derivation.get("post_feasibility_inputs_consumed") is False
            and all(str(derivation.get(field, "")).strip() for field in (
                "formula_contract_sha256", "c1_design_parameters_sha256",
                "capacity_manifest_sha256", "reviewer_approval_sha256",
            ))
        )
    return base_ready


def _task_set_sha(task_ids: set[str]) -> str:
    payload = json.dumps(sorted(task_ids), separators=(",", ":"), ensure_ascii=False)
    return __import__("hashlib").sha256(payload.encode("utf-8")).hexdigest()


def build_candidate_design_manifest(
    task_pool_csv: Path, worker_profile_csv: Path, c1_closeout_summary: Path | None,
    output: Path, *, threshold_manifest: Path = DESIGN_THRESHOLDS,
    risk_summary: Path | None = None, seed: int = 20260724, draws: int = 1000,
) -> Path:
    task_pool_rows = read_csv(task_pool_csv)
    c1_snapshot = json.loads(c1_closeout_summary.read_text(encoding="utf-8")) if c1_closeout_summary else {}
    c1_eligible_base_tasks = {safe(value) for value in c1_snapshot.get("eligible_base_task_ids", [])}
    c1_reference_sha = safe(c1_snapshot.get("reference_registry_sha256"))
    cross_stage_anchor_base_task_ids = sorted({
        safe(row.get("base_task_id"))
        for row in task_pool_rows
        if safe(row.get("base_task_id"))
        and truthy(row.get("cross_stage_anchor"))
        and safe(row.get("base_task_id")) in c1_eligible_base_tasks
        and c1_reference_sha
        and safe(row.get("reference_registry_sha256")) == c1_reference_sha
    })
    """Enumerate designs from the realized frozen pool; never select one."""
    tasks = [row for row in read_csv(task_pool_csv) if truthy(row.get("assignment_eligible"))]
    workers = _eligible_workers(read_csv(worker_profile_csv))
    anchors, bridges = len(_anchor_pool(tasks)), len(_bridge_pool(tasks))

    fixed = (("D8", 4, 4), ("D10", 6, 4), ("D12", 6, 6))
    candidates = [{
        "design_id": design_id, "common_anchor_count": common,
        "bridge_per_worker": per_worker,
        "unique_bridge_tasks": min(bridges, max(1, math.ceil(len(workers) * per_worker / 2))),
        "unique_bridge_tasks_role": "upper_bound_search_downward",
        "min_task_support": 2, "max_worker_stratum_imbalance": 2,
    } for design_id, common, per_worker in fixed]
    _amendment, amendment_sha = _load_predispatch_amendment()
    manifest = {
        "manifest_version": "c2_design_v1",
        "contract_role": "generated_subordinate",
        "method_contract_version": __import__("tools.thesis_main.analysis.paper_a_contracts", fromlist=["load_method_contract"]).load_method_contract()["contract_version"],
        "method_contract_sha256": __import__("tools.thesis_main.analysis.paper_a_contracts", fromlist=["METHOD_CONTRACT", "sha256_file"]).sha256_file(__import__("tools.thesis_main.analysis.paper_a_contracts", fromlist=["METHOD_CONTRACT"]).METHOD_CONTRACT),
        "artifact_role": "formal_candidate_enumeration_only",
        "input_sha256": {
            "worker_profile_csv": sha256_file(worker_profile_csv),
            "task_pool_csv": sha256_file(task_pool_csv),
            **({"c1_closeout_summary": sha256_file(c1_closeout_summary)} if c1_closeout_summary else {}),
            **({"risk_summary": sha256_file(risk_summary)} if risk_summary else {}),
        },
        "risk_contract_sha256": sha256_file(RISK_CONTRACT),
        "predispatch_amendment_sha256": amendment_sha,
        "threshold_manifest_path": str(threshold_manifest.resolve()),
        "threshold_manifest_sha256": sha256_file(threshold_manifest),
        "candidate_designs": candidates,
        "cross_stage_anchor_base_task_ids": cross_stage_anchor_base_task_ids,
        "cross_stage_anchor_count": len(cross_stage_anchor_base_task_ids),
        "simulation": {"seed": seed, "draws": draws, "resampling": "C1 empirical building/task/worker bootstrap"},
        "bridge_task_count_policy": "search_downward_from_unique_bridge_tasks_upper_bound_and_maximize_unique_images_subject_to_deterministic_assignment_gates",
        "selection_rule": "first_minimum_design_meeting_graph_coverage_precision_budget_then_sha_bound_human_approval",
    }
    write_json(output, manifest)
    return output


def _float_le(actual: float, limit: float) -> bool:
    return actual < limit or math.isclose(actual, limit, rel_tol=1e-12, abs_tol=1e-12)


def _float_ge(actual: float, limit: float) -> bool:
    return actual > limit or math.isclose(actual, limit, rel_tol=1e-12, abs_tol=1e-12)


def _threshold_failures(simulation_row: dict[str, Any], graph: dict[str, Any], thresholds: dict[str, Any]) -> list[str]:
    values = thresholds.get("thresholds", thresholds)
    checks = {
        "q_gt_ci_half_width": (simulation_row, "q_gt_max_ci_half_width", _float_le),
        "risk_slope_ci_half_width": (simulation_row, "risk_slope_max_ci_half_width", _float_le),
        "minimum_worker_rank_spearman": (simulation_row, "worker_rank_spearman", _float_ge),
        "minimum_top_k_overlap": (simulation_row, "top_k_overlap", _float_ge),
        "minimum_worker_support": (graph, "minimum_worker_support", _float_ge),
        "minimum_task_support": (graph, "min_bridge_task_support", _float_ge),
        "graph_connectivity_probability": (simulation_row, "graph_connectivity_probability", _float_ge),
        "minimum_building_coverage": (simulation_row, "building_coverage", _float_ge),
        "building_coverage_probability": (simulation_row, "building_coverage_probability", _float_ge),
        "ordinary_coverage_probability": (simulation_row, "ordinary_coverage_probability", _float_ge),
        "stress_coverage_probability": (simulation_row, "stress_coverage_probability", _float_ge),
    }
    failures = []
    for name, (source, field, predicate) in checks.items():
        limit = values.get(name)
        if limit in {None, ""}:
            continue
        try:
            actual = float(source.get(field, ""))
            if not predicate(actual, float(limit)):
                failures.append(name)
        except (TypeError, ValueError):
            failures.append(f"{name}_not_evaluable")
    return failures


def _risk_distance(left: dict[str, str], right: dict[str, str]) -> float:
    return sum((a - b) ** 2 for a, b in zip(_risk_vector(left), _risk_vector(right))) ** .5


def _select_anchors(rows: list[dict[str, str]], count: int) -> list[dict[str, str]]:
    if not rows or count <= 0: return []
    if count < 2:
        return []
    strata = {"ordinary": [row for row in rows if _task_stratum(row) == "ordinary"], "stress": [row for row in rows if _task_stratum(row) == "stress"]}
    if not strata["ordinary"] or not strata["stress"]:
        return []
    center = tuple(sum(vector[index] for vector in map(_risk_vector, rows)) / len(rows) for index in range(4))
    ranked = sorted(rows, key=lambda row: (sum((left - right) ** 2 for left, right in zip(_risk_vector(row), center)), bool(row.get("building_id")) is False, _task_id(row)))
    ordinary = min(strata["ordinary"], key=lambda row: (sum((left - right) ** 2 for left, right in zip(_risk_vector(row), center)), _task_id(row)))
    ordinary_building = safe(ordinary.get("building_id"))
    stress = min(strata["stress"], key=lambda row: (
        bool(ordinary_building) and safe(row.get("building_id")) == ordinary_building,
        sum((left - right) ** 2 for left, right in zip(_risk_vector(row), center)),
        _task_id(row),
    ))
    chosen = [ordinary, stress]
    chosen_ids = {_task_id(row) for row in chosen}
    return chosen + [row for row in _balanced_tasks([row for row in ranked if _task_id(row) not in chosen_ids], count - 2)]


def _select_bridges(rows: list[dict[str, str]], count: int, anchor_rows: list[dict[str, str]]) -> list[dict[str, str]]:
    selected, remaining = [], list(rows)
    reference = list(anchor_rows)
    while remaining and len(selected) < count:
        buildings = {safe(row.get("building_id")) for row in [*anchor_rows, *selected]} - {""}
        def key(row: dict[str, str]) -> tuple:
            vector = _risk_vector(row)
            distance = min((_risk_distance(row, other) for other in [*reference, *selected]), default=math.inf)
            return (-distance, -(safe(row.get("building_id")) not in buildings), _task_id(row))
        chosen = min(remaining, key=key); selected.append(chosen); remaining.remove(chosen)
    return selected


def _assign_bridges(
    workers: list[str],
    tasks: list[dict[str, str]],
    per_worker: int,
    min_support: int,
) -> list[tuple[str, dict[str, str]]] | None:
    if per_worker > len(tasks) or len(workers) * per_worker < len(tasks) * min_support or min_support > len(workers):
        return None
    assigned: set[tuple[str, str]] = set()
    remaining = {worker: per_worker for worker in workers}
    support: Counter[str] = Counter()
    worker_strata: dict[str, Counter[str]] = defaultdict(Counter)

    def add(worker: str, task: dict[str, str]) -> None:
        task_id = _task_id(task)
        assigned.add((worker, task_id))
        remaining[worker] -= 1
        support[task_id] += 1
        worker_strata[worker][_task_stratum(task)] += 1

    for task in tasks:
        for _ in range(min_support):
            candidates = [
                worker for worker in workers
                if remaining[worker] and (worker, _task_id(task)) not in assigned
            ]
            if not candidates:
                return None
            worker = min(
                candidates,
                key=lambda value: (
                    worker_strata[value][_task_stratum(task)],
                    -remaining[value],
                    value,
                ),
            )
            add(worker, task)

    for worker in workers:
        while remaining[worker]:
            candidates = [task for task in tasks if (worker, _task_id(task)) not in assigned]
            if not candidates:
                return None
            task = min(
                candidates,
                key=lambda value: (
                    worker_strata[worker][_task_stratum(value)],
                    support[_task_id(value)],
                    _task_stratum(value),
                    _task_id(value),
                ),
            )
            add(worker, task)
    task_by_id = {_task_id(task): task for task in tasks}
    return [(worker, task_by_id[task_id]) for worker, task_id in sorted(assigned)]


def _search_bridge_assignment(
    design_id: str,
    workers: list[str],
    bridge_pool: list[dict[str, str]],
    anchor_rows: list[dict[str, str]],
    upper_bound: int,
    per_worker: int,
    min_support: int,
    max_imbalance: int,
    minimum_building_coverage: int,
) -> tuple[list[dict[str, str]], list[tuple[str, dict[str, str]]], dict[str, Any], int, str]:
    """Maximize unique bridges while satisfying deterministic dispatch gates."""
    last_selected: list[dict[str, str]] = []
    last_edges: list[tuple[str, dict[str, str]]] = []
    last_graph = _graph_audit(design_id, workers, [], set())
    last_failures = ["bridge_support_or_worker_capacity_infeasible"]
    attempts = 0
    for count in range(min(upper_bound, len(bridge_pool)), per_worker - 1, -1):
        attempts += 1
        selected = _select_bridges(bridge_pool, count, anchor_rows)
        edges = _assign_bridges(workers, selected, per_worker, min_support) or []
        rows = [
            {"worker_id": worker, "task_id": _task_id(task), "task_stratum": _task_stratum(task)}
            for worker, task in edges
        ]
        graph = _graph_audit(design_id, workers, rows, {_task_id(task) for task in selected})
        buildings = {safe(task.get("building_id") or task.get("building")) for task in [*anchor_rows, *selected]} - {""}
        failures = []
        if len(selected) != count or not edges:
            failures.append("bridge_support_or_worker_capacity_infeasible")
        if graph["min_bridge_task_support"] < min_support:
            failures.append("minimum_task_support")
        if graph["max_worker_stratum_imbalance"] > max_imbalance:
            failures.append("worker_stratum_imbalance")
        if len(buildings) < minimum_building_coverage:
            failures.append("minimum_building_coverage")
        last_selected, last_edges, last_graph, last_failures = selected, edges, graph, failures
        if not failures:
            return selected, edges, graph, attempts, ""
    return last_selected, last_edges, last_graph, attempts, ";".join(last_failures)


def _graph_audit(
    design_id: str,
    workers: list[str],
    assignments: list[dict[str, Any]],
    bridge_task_ids: set[str],
) -> dict[str, Any]:
    edges = [(safe(row["worker_id"]), safe(row["task_id"])) for row in assignments]
    nodes = {f"w:{worker}" for worker in workers} | {f"t:{task}" for _, task in edges}
    graph: dict[str, set[str]] = defaultdict(set)
    for worker, task in edges:
        graph[f"w:{worker}"].add(f"t:{task}")
        graph[f"t:{task}"].add(f"w:{worker}")
    def components_for(edge_rows: list[tuple[str, str]]) -> tuple[int, bool]:
        local_nodes = {f"w:{worker}" for worker in workers} | {f"t:{task}" for _, task in edge_rows}
        local_graph: dict[str, set[str]] = defaultdict(set)
        for worker, task in edge_rows:
            local_graph[f"w:{worker}"].add(f"t:{task}"); local_graph[f"t:{task}"].add(f"w:{worker}")
        unseen = set(local_nodes); count = 0
        while unseen:
            count += 1; queue = [unseen.pop()]
            while queue:
                for neighbor in local_graph[queue.pop()]:
                    if neighbor in unseen:
                        unseen.remove(neighbor); queue.append(neighbor)
        return count, bool(local_nodes) and bool(edge_rows) and count == 1

    components, connected = components_for(edges)
    bridge_components, bridge_connected = components_for([(worker, task) for worker, task in edges if task in bridge_task_ids])
    duplicate_count = len(edges) - len(set(edges))
    support = Counter(task for _, task in edges if task in bridge_task_ids)
    worker_support = Counter(worker for worker, _task in edges)
    by_worker_stratum: dict[str, Counter[str]] = defaultdict(Counter)
    task_strata = {safe(row["task_id"]): safe(row["task_stratum"]) for row in assignments}
    bridge_strata = {task_strata[task] for task in bridge_task_ids if task in task_strata}
    for worker, task in edges:
        if task in bridge_task_ids:
            by_worker_stratum[worker][task_strata[task]] += 1
    imbalances = [
        max((counts[stratum] for stratum in bridge_strata), default=0)
        - min((counts[stratum] for stratum in bridge_strata), default=0)
        for counts in by_worker_stratum.values()
    ]
    return {
        "design_id": design_id,
        "n_workers": len(workers),
        "n_tasks": len({task for _, task in edges}),
        "n_edges": len(edges),
        "n_connected_components": components,
        "worker_task_graph_connected": connected,
        "bridge_only_n_connected_components": bridge_components,
        "bridge_only_graph_connected": bridge_connected,
        "duplicate_worker_task_count": duplicate_count,
        "minimum_worker_support": min((worker_support[worker] for worker in workers), default=0),
        "min_bridge_task_support": min(support.values()) if support else 0,
        "max_worker_stratum_imbalance": max(imbalances, default=0),
        "stress_bridge_task_count": len({task for task in bridge_task_ids if task_strata.get(task) == "stress"}),
        "stress_bridge_assignment_support": sum(count for task, count in support.items() if task_strata.get(task) == "stress"),
    }


def _resolve_slope_distribution(row: dict[str, Any]) -> dict[str, Any]:
    """Resolve the sole frozen worker-slope distribution used everywhere.

    The group fixed-slope uncertainty is a shared draw.  The returned
    ``independent_sd`` is the worker-specific posterior uncertainty for an
    identified worker, or the between-worker prior scale for an unidentified
    worker.  ``total_sd`` is used by analytic projections.
    """
    group_mean = _float(row, "group_slope_mean", "group_prior_slope", default=math.nan)
    group_sd = _float(row, "group_slope_se", default=math.nan)
    between_sd = _float(row, "between_worker_slope_sd", "group_prior_scale", default=math.nan)
    model_form = safe(row.get("slope_model_form"))
    common = model_form == "crossed_common_worker_slope" or between_sd == 0
    if common:
        mean, independent_sd, source = group_mean, 0.0, "common_group_posterior"
    else:
        individual_mean = _float(row, "risk_slope_for_simulation", "risk_slope", default=math.nan)
        individual_sd = _float(row, "risk_slope_se", default=math.nan)
        support = _int(row, "risk_slope_support", "risk_support", "support", "n_support")
        if math.isfinite(individual_mean) and math.isfinite(individual_sd) and individual_sd >= 0 and support > 0:
            mean, independent_sd, source = individual_mean, individual_sd, "individual_posterior"
        else:
            mean, independent_sd, source = group_mean, between_sd, "group_prior"
    valid = (
        math.isfinite(mean) and math.isfinite(group_sd) and group_sd >= 0
        and math.isfinite(independent_sd) and independent_sd >= 0
    )
    total_sd = math.sqrt(group_sd ** 2 + independent_sd ** 2) if valid else math.inf
    return {
        "mean": mean, "group_sd": group_sd, "independent_sd": independent_sd,
        "total_sd": total_sd, "source": source if valid else "missing", "common": common,
        "valid": valid,
    }


def _resolve_fitted_worker_slope_distribution(
    model: dict[str, Any], worker: str, support: int,
) -> dict[str, Any]:
    """Adapt one fitted worker to the sole frozen slope-distribution rule."""
    return _resolve_slope_distribution({
        "group_slope_mean": model.get("group_slope_mean", ""),
        "group_slope_se": model.get("group_slope_se", ""),
        "between_worker_slope_sd": model.get("between_worker_slope_sd", ""),
        "slope_model_form": model.get("slope_model_form", ""),
        "risk_slope": model.get("worker_slopes", {}).get(worker, ""),
        "risk_slope_se": model.get("worker_slope_ses", {}).get(worker, ""),
        "risk_slope_support": support,
    })


def _joint_qgt_posterior(
    prior_mean: np.ndarray,
    prior_covariance: np.ndarray,
    design: np.ndarray,
    *,
    risk_adjusted_outcomes: np.ndarray,
    likelihood_covariance: np.ndarray,
) -> tuple[np.ndarray, np.ndarray]:
    """Gaussian C1/C2 update retaining the complete C1 worker covariance."""
    mean = np.asarray(prior_mean, dtype=float)
    covariance = np.asarray(prior_covariance, dtype=float)
    matrix = np.asarray(design, dtype=float)
    outcomes = np.asarray(risk_adjusted_outcomes, dtype=float)
    likelihood = np.asarray(likelihood_covariance, dtype=float)
    if matrix.shape == (0, len(mean)):
        return mean.copy(), covariance.copy()
    if (
        covariance.shape != (len(mean), len(mean))
        or matrix.ndim != 2 or matrix.shape[1] != len(mean)
        or outcomes.shape != (matrix.shape[0],)
        or likelihood.shape != (matrix.shape[0], matrix.shape[0])
        or not all(np.isfinite(value).all() for value in (mean, covariance, matrix, outcomes, likelihood))
    ):
        raise ValueError("invalid joint Q_GT posterior inputs")
    innovation_covariance = matrix @ covariance @ matrix.T + likelihood
    residual = outcomes - matrix @ mean
    try:
        solved_residual = np.linalg.solve(innovation_covariance, residual)
        solved_design_covariance = np.linalg.solve(innovation_covariance, matrix @ covariance)
    except np.linalg.LinAlgError as exc:
        raise ValueError("singular joint Q_GT posterior covariance") from exc
    posterior_mean = mean + covariance @ matrix.T @ solved_residual
    posterior_covariance = covariance - covariance @ matrix.T @ solved_design_covariance
    posterior_covariance = (posterior_covariance + posterior_covariance.T) / 2
    if not np.isfinite(posterior_mean).all() or not np.isfinite(posterior_covariance).all():
        raise ValueError("nonfinite joint Q_GT posterior")
    return posterior_mean, posterior_covariance


def _projected_worker_intervals(
    worker_rows: list[dict[str, str]],
    assignments: list[dict[str, Any]],
    task_by_id: dict[str, dict[str, str]],
    *,
    seed: int,
    draws: int,
    require_c1_slopes: bool,
) -> tuple[float, list[dict[str, Any]]]:
    if require_c1_slopes and draws < 200:
        raise ValueError("formal C2-B simulation requires at least 200 draws")
    assignments_by_worker: dict[str, list[dict[str, Any]]] = defaultdict(list)
    worker_sets: dict[str, set[str]] = defaultdict(set)
    for edge in assignments:
        assignments_by_worker[safe(edge.get("worker_id"))].append(edge)
        if safe(edge.get("c2_component")) == "diverse_bridge":
            worker_sets[safe(edge.get("worker_id"))].add(safe(edge.get("task_id")))
    projected, audits = [], []
    for row in worker_rows:
        worker = safe(row.get("worker_id"))
        edges = assignments_by_worker.get(worker, [])
        tasks = [task_by_id[safe(edge.get("task_id"))] for edge in edges if safe(edge.get("task_id")) in task_by_id]
        raw_information = sum(_float(task, "risk_information_weight", default=1.0) for task in tasks)
        assigned = _int(row, "assigned_total_count", default=0)
        observed = _int(row, "observed_total_count", default=assigned)
        missing_rate = _float(row, "missing_rate", default=math.nan)
        structural_rate = _float(row, "F_struct", default=math.nan)
        rate_contract_valid = (
            math.isfinite(missing_rate) and 0.0 <= missing_rate <= 1.0
            and math.isfinite(structural_rate) and 0.0 <= structural_rate <= 1.0
        )
        buildings = {safe(task.get("building_id") or task.get("building")) for task in tasks} - {""}
        cluster_factor = math.sqrt(len(buildings) / len(tasks)) if tasks and buildings else 1.0
        added_information = (
            raw_information * (1 - missing_rate) * (1 - structural_rate) * cluster_factor
            if rate_contract_valid else 0.0
        )
        slope_distribution = _resolve_slope_distribution(row)
        slope_se = float(slope_distribution["total_sd"])
        slope_precision_source = str(slope_distribution["source"])
        projection_status = "estimable"
        if not rate_contract_valid:
            projection_status = "not_estimable_missing_or_invalid_rate"
        elif not (math.isfinite(slope_se) and slope_se > 0):
            projection_status = "not_estimable_missing_slope_precision"
        if projection_status == "estimable":
            rng = random.Random(f"{seed}|{worker}|{added_information:.12g}")
            errors = []
            task_variance = max(0.0, _float(row, "task_sd", default=0.0)) ** 2
            building_variance = max(0.0, _float(row, "building_sd", default=0.0)) ** 2
            for _ in range(draws):
                delivered = [task for task in tasks if rng.random() >= missing_rate and rng.random() >= structural_rate]
                information = sum(_float(task, "risk_information_weight", default=1.0) for task in delivered)
                projected_se = math.sqrt(
                    1.0 / ((1.0 / slope_se ** 2) + information)
                    + task_variance / max(1, len(delivered))
                    + building_variance / max(1, len({safe(task.get("building_id")) for task in delivered}))
                )
                errors.append(abs(rng.gauss(0.0, projected_se)))
            errors.sort()
            value = errors[min(draws - 1, math.ceil(0.95 * draws) - 1)]
            current = 1.96 * slope_se
        else:
            # Missing both individual precision and a frozen group-prior scale
            # is genuinely not estimable and remains fail-closed.
            value, current = math.inf, ""
        projected.append(value)
        strata = Counter(_task_stratum(task) for task in tasks)
        base_ids = {safe(task.get("base_task_id")) or _task_id(task) for task in tasks}
        worker_bridge_set = worker_sets.get(worker, set())
        overlaps = [len(worker_bridge_set & values) for other, values in list(worker_sets.items()) if other != worker]
        audits.append({
            "design_id": safe(edges[0].get("design_id")) if edges else "", "worker_id": worker,
            "current_interval_half_width": current,
            "projected_interval_half_width": "" if not math.isfinite(value) else value,
            "projection_status": projection_status, "slope_precision_source": slope_precision_source,
            "ordinary_support": strata["ordinary"], "stress_support": strata["stress"],
            "common_anchor_support": sum(safe(edge.get("c2_component")) == "common_anchor" for edge in edges),
            "bridge_support": len(worker_sets[worker]), "unique_image_coverage": len(base_ids),
            "building_coverage": len(buildings), "common_bridge_with_other_min": min(overlaps, default=0),
            "missing_rate": missing_rate, "structural_failure_rate": structural_rate,
            "effective_information": added_information,
            "expected_fallback_rate": missing_rate ** len(tasks) if tasks and rate_contract_valid else "",
            "expected_global_full_divergence": abs(float(slope_distribution["mean"])) * (max((_float(task, "risk_design_score_A", default=0.0) for task in tasks), default=0.0) - min((_float(task, "risk_design_score_A", default=0.0) for task in tasks), default=0.0)) if slope_distribution["valid"] else "",
            "v1_usable_support": len(tasks) * (1 - missing_rate) * (1 - structural_rate) if rate_contract_valid else "",
        })
    return max(projected, default=math.inf), audits


def _recompute_stability_audits(
    design_id: str,
    worker_rows: list[dict[str, str]],
    assignments: list[dict[str, Any]],
    task_by_id: dict[str, dict[str, str]],
    *,
    seed: int,
    draws: int,
) -> list[dict[str, Any]]:
    """Physically remove task/building/anchor instances and recompute diagnostics."""
    perturbations: list[tuple[str, str, set[str]]] = []
    task_ids = sorted({safe(row.get("task_id")) for row in assignments})
    for task_id in task_ids:
        perturbations.append(("leave_one_task_out", task_id, {task_id}))
    buildings: dict[str, set[str]] = defaultdict(set)
    for task_id in task_ids:
        building = safe(task_by_id.get(task_id, {}).get("building_id") or task_by_id.get(task_id, {}).get("building"))
        if building:
            buildings[building].add(task_id)
    for building, members in sorted(buildings.items()):
        perturbations.append(("leave_one_building_out", building, members))
    anchor_ids = sorted({safe(row.get("task_id")) for row in assignments if safe(row.get("c2_component")) == "common_anchor"})
    for task_id in anchor_ids:
        perturbations.append(("leave_one_anchor_out", task_id, {task_id}))
    workers = [safe(row.get("worker_id")) for row in worker_rows]
    output: list[dict[str, Any]] = []
    for kind, removed_id, removed_tasks in perturbations:
        kept = [row for row in assignments if safe(row.get("task_id")) not in removed_tasks]
        kept_tasks = {task_id: row for task_id, row in task_by_id.items() if task_id not in removed_tasks}
        bridge_ids = {safe(row.get("task_id")) for row in kept if safe(row.get("c2_component")) == "diverse_bridge"}
        graph = _graph_audit(design_id, workers, kept, bridge_ids)
        projected, worker_projection = _projected_worker_intervals(
            worker_rows, kept, kept_tasks, seed=seed, draws=draws, require_c1_slopes=False,
        )
        support_by_worker = Counter(safe(row.get("worker_id")) for row in kept)
        support_by_task = Counter(safe(row.get("task_id")) for row in kept)
        strata = {safe(kept_tasks.get(safe(row.get("task_id")), {}).get("risk_design_stratum")) for row in kept}
        per_worker_strata = {
            worker: {safe(kept_tasks.get(safe(row.get("task_id")), {}).get("risk_design_stratum")) for row in kept if safe(row.get("worker_id")) == worker}
            for worker in workers
        }
        output.append({
            "design_id": design_id, "perturbation": kind, "removed_id": removed_id,
            "removed_task_count": len(removed_tasks), "remaining_edge_count": len(kept),
            "minimum_worker_support": min((support_by_worker[worker] for worker in workers), default=0),
            "minimum_task_support": min(support_by_task.values(), default=0),
            "worker_task_graph_connected": graph["worker_task_graph_connected"],
            "bridge_only_graph_connected": graph["bridge_only_graph_connected"],
            "building_coverage": len({safe(row.get("building_id") or row.get("building")) for row in kept_tasks.values()} - {""}),
            "ordinary_coverage": "ordinary" in strata, "stress_coverage": "stress" in strata,
            "ordinary_coverage_all_workers": all("ordinary" in per_worker_strata[worker] for worker in workers),
            "stress_coverage_all_workers": all("stress" in per_worker_strata[worker] for worker in workers),
            "projected_max_ci_half_width": "" if not math.isfinite(projected) else projected,
            "worker_projection_recomputed": bool(worker_projection),
        })
    return output


def _empirical_cluster_bootstrap(
    design_id: str, worker_rows: list[dict[str, str]], assignments: list[dict[str, Any]],
    task_by_id: dict[str, dict[str, str]], graph: dict[str, Any], *, seed: int, draws: int,
    minimum_worker_support_threshold: int | None = None,
    minimum_task_support_threshold: int | None = None,
) -> dict[str, Any]:
    """Nested building/task resampling plus C1-prior outcome generation.

    Each draw resamples buildings with multiplicity, then one task within every
    sampled building. Delivery, graph connectivity and re-estimation are rebuilt
    from those realized edges. It is a C2-B design simulation, never evidence of
    routing eligibility.
    """
    if not assignments or not worker_rows or draws < 1:
        return {field: "" for field in SIMULATION_FIELDS} | {"design_id": design_id, "seed": seed, "draws": draws, "simulation_status": "insufficient_design_input"}
    required_variances = (
        "group_slope_mean", "group_slope_se", "between_worker_slope_sd", "outcome_residual_sd",
        "task_sd", "building_sd", "Q_GT_baseline_se",
    )
    nonnegative_fields = set(required_variances) - {"group_slope_mean"}
    invalid_variance = any(
        not math.isfinite(value) or (field in nonnegative_fields and value < 0)
        for row in worker_rows for field in required_variances
        for value in [_float(row, field, default=math.nan)]
    )
    if invalid_variance:
        return {field: "" for field in SIMULATION_FIELDS} | {
            "design_id": design_id, "seed": seed, "draws": draws,
            "variance_fields_used": list(required_variances),
            "simulation_status": "insufficient_variance_parameters",
        }
    if any(
        not math.isfinite(value) or value < 0 or value > 1
        for row in worker_rows for value in [_float(row, "missing_rate", default=math.nan)]
    ):
        return {field: "" for field in SIMULATION_FIELDS} | {
            "design_id": design_id, "seed": seed, "draws": draws,
            "variance_fields_used": list(required_variances),
            "simulation_status": "insufficient_missingness_parameters",
        }
    structural_values = [_float(row, "F_struct", default=math.nan) for row in worker_rows]
    if any(math.isfinite(value) and not 0 <= value <= 1 for value in structural_values):
        return {field: "" for field in SIMULATION_FIELDS} | {
            "design_id": design_id, "seed": seed, "draws": draws,
            "variance_fields_used": list(required_variances),
            "simulation_status": "invalid_structural_failure_parameters",
        }
    supported_structural = [value for value in structural_values if math.isfinite(value) and 0 <= value <= 1]
    if any(not math.isfinite(value) for value in structural_values) and len(supported_structural) < 2:
        return {field: "" for field in SIMULATION_FIELDS} | {
            "design_id": design_id, "seed": seed, "draws": draws,
            "variance_fields_used": list(required_variances),
            "simulation_status": "insufficient_structural_failure_model",
        }
    rng = random.Random(f"c1-hierarchical-resampling|{seed}|{design_id}")
    edges_by_worker: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for edge in assignments:
        edges_by_worker[safe(edge["worker_id"])].append(edge)
    baseline = {safe(row.get("worker_id")): _float(row, "Q_GT_task_adjusted", default=math.nan) for row in worker_rows}
    if any(not math.isfinite(value) for value in baseline.values()):
        return {field: "" for field in SIMULATION_FIELDS} | {"design_id": design_id, "seed": seed, "draws": draws, "simulation_status": "insufficient_q_gt_baseline"}
    baseline_rank = sorted(baseline, key=lambda worker: (-baseline[worker], worker))
    baseline_position = {worker: index + 1 for index, worker in enumerate(baseline_rank)}
    covariance_rows: dict[str, dict[str, float]] = {}
    try:
        for row in worker_rows:
            worker = safe(row.get("worker_id"))
            covariance_rows[worker] = {key: float(value) for key, value in json.loads(safe(row.get("Q_GT_contrast_covariance_row_json"))).items()}
        covariance = np.asarray([[covariance_rows[left][right] for right in baseline_rank] for left in baseline_rank], dtype=float)
        if covariance.shape != (len(baseline_rank), len(baseline_rank)) or not np.isfinite(covariance).all() or not np.allclose(covariance, covariance.T, atol=1e-10) or np.linalg.eigvalsh(covariance).min() < -1e-10:
            raise ValueError("invalid covariance")
        declared_variance = np.asarray([
            _float(next(row for row in worker_rows if safe(row.get("worker_id")) == worker), "Q_GT_baseline_se", default=math.nan) ** 2
            for worker in baseline_rank
        ])
        if not np.allclose(np.diag(covariance), declared_variance, rtol=1e-6, atol=1e-12):
            raise ValueError("covariance diagonal does not match Q_GT baseline SE")
    except (KeyError, TypeError, ValueError, json.JSONDecodeError):
        return {field: "" for field in SIMULATION_FIELDS} | {
            "design_id": design_id, "seed": seed, "draws": draws,
            "variance_fields_used": list(required_variances),
            "simulation_status": "insufficient_q_gt_baseline_covariance",
        }
    np_rng = np.random.default_rng(int(hashlib.sha256(f"{seed}|{design_id}".encode()).hexdigest()[:16], 16))
    selected_task_ids = {safe(edge.get("task_id")) for edge in assignments}
    task_by_building: dict[str, list[dict[str, str]]] = defaultdict(list)
    for task_id in selected_task_ids:
        task = task_by_id.get(task_id, {})
        building = safe(task.get("building_id") or task.get("building"))
        if building:
            task_by_building[building].append(task)
    buildings = sorted(task_by_building)
    edges_by_building: dict[str, list[dict[str, Any]]] = defaultdict(list)
    edges_by_task: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for edge in assignments:
        task = task_by_id.get(safe(edge.get("task_id")), {})
        building = safe(task.get("building_id") or task.get("building"))
        if building:
            edges_by_building[building].append(edge)
        edges_by_task[safe(edge.get("task_id"))].append(edge)
    q_half_widths: list[float] = []
    slope_half_widths: list[float] = []
    rank_stable = slope_stable = connected = bridge_connected = ordinary = stress = full_building_coverage = 0
    ordinary_per_worker = stress_per_worker = 0.0
    spearman_values: list[float] = []
    top_k_values: list[float] = []
    rank_displacements: list[float] = []
    min_worker_supports: list[int] = []
    min_task_supports: list[int] = []
    delivered_counts: list[int] = []
    delivered_building_counts: list[int] = []
    sampled_task_edge_identity_violations = 0

    def _connected_delivered(delivered: list[tuple[str, str]]) -> bool:
        nodes = {f"w:{worker}" for worker in baseline}
        graph_nodes: dict[str, set[str]] = defaultdict(set)
        for worker, task in delivered:
            left, right = f"w:{worker}", f"t:{task}"
            graph_nodes[left].add(right); graph_nodes[right].add(left); nodes.add(right)
        if not delivered:
            return False
        pending, seen = [next(iter(nodes))], set()
        while pending:
            node = pending.pop()
            if node in seen:
                continue
            seen.add(node); pending.extend(graph_nodes[node] - seen)
        return seen == nodes

    def _slope(values: list[tuple[float, float]], prior_mean: float, prior_sd: float, residual_sd: float, common_slope_se: float) -> tuple[float, float]:
        if prior_sd == 0 and math.isfinite(common_slope_se) and common_slope_se >= 0:
            return prior_mean, 1.96 * common_slope_se
        if not math.isfinite(prior_sd) or prior_sd < 0 or not math.isfinite(residual_sd) or residual_sd <= 0:
            return prior_mean, math.inf
        prior_precision = 1.0 / prior_sd ** 2
        if len(values) < 2:
            return prior_mean, 1.96 * prior_sd
        mean_x = sum(value[0] for value in values) / len(values)
        mean_y = sum(value[1] for value in values) / len(values)
        denominator = sum((value[0] - mean_x) ** 2 for value in values)
        if denominator <= 0:
            return prior_mean, 1.96 * prior_sd
        likelihood_precision = denominator / residual_sd ** 2
        observed = sum((x - mean_x) * (y - mean_y) for x, y in values) / denominator
        posterior = (prior_precision * prior_mean + likelihood_precision * observed) / (prior_precision + likelihood_precision)
        return posterior, 1.96 / math.sqrt(prior_precision + likelihood_precision)

    def _common_slope(
        values_by_worker: dict[str, list[tuple[float, float]]], prior_mean: float, prior_sd: float,
    ) -> tuple[float, float]:
        if prior_sd == 0:
            return prior_mean, 0.0
        if not math.isfinite(prior_sd) or prior_sd < 0:
            return prior_mean, math.inf
        prior_precision = 1.0 / prior_sd ** 2
        likelihood_precision = weighted_cross_product = 0.0
        for worker, values in values_by_worker.items():
            residual_sd = _float(
                next(row for row in worker_rows if safe(row.get("worker_id")) == worker),
                "outcome_residual_sd", default=math.inf,
            )
            if len(values) < 2 or not math.isfinite(residual_sd) or residual_sd <= 0:
                continue
            mean_x = sum(value[0] for value in values) / len(values)
            mean_y = sum(value[1] for value in values) / len(values)
            denominator = sum((value[0] - mean_x) ** 2 for value in values)
            if denominator <= 0:
                continue
            likelihood_precision += denominator / residual_sd ** 2
            weighted_cross_product += sum(
                (x - mean_x) * (y - mean_y) for x, y in values
            ) / residual_sd ** 2
        if likelihood_precision <= 0:
            return prior_mean, 1.96 * prior_sd
        observed = weighted_cross_product / likelihood_precision
        posterior = (prior_precision * prior_mean + likelihood_precision * observed) / (prior_precision + likelihood_precision)
        return posterior, 1.96 / math.sqrt(prior_precision + likelihood_precision)

    def _variance(field: str, *, nonnegative: bool = True) -> float:
        values = [_float(row, field, default=math.nan) for row in worker_rows]
        values = [value for value in values if math.isfinite(value) and (value >= 0 or not nonnegative)]
        return sum(values) / len(values) if values else math.nan

    building_sd, task_sd = _variance("building_sd"), _variance("task_sd")
    worker_intercept_sd = _variance("worker_intercept_sd")
    group_slope_mean, group_slope_se = _variance("group_slope_mean", nonnegative=False), _variance("group_slope_se")
    between_worker_slope_sd = _variance("between_worker_slope_sd")
    slope_distributions = {
        safe(row.get("worker_id")): _resolve_slope_distribution(row)
        for row in worker_rows
    }
    if any(not distribution["valid"] for distribution in slope_distributions.values()):
        return {field: "" for field in SIMULATION_FIELDS} | {
            "design_id": design_id, "seed": seed, "draws": draws,
            "variance_fields_used": list(required_variances),
            "simulation_status": "insufficient_worker_slope_distribution",
        }
    common_flags = {bool(distribution["common"]) for distribution in slope_distributions.values()}
    if len(common_flags) != 1:
        return {field: "" for field in SIMULATION_FIELDS} | {
            "design_id": design_id, "seed": seed, "draws": draws,
            "variance_fields_used": list(required_variances),
            "simulation_status": "inconsistent_slope_model_form",
        }
    common_slope_model = common_flags == {True}
    group_structural_rate = sum(supported_structural) / len(supported_structural) if supported_structural else math.nan
    for _ in range(draws):
        shared_group_delta = rng.gauss(0.0, group_slope_se) if group_slope_se > 0 else 0.0
        sampled_baseline_values = np_rng.multivariate_normal(
            np.asarray([baseline[worker] for worker in baseline_rank], dtype=float), covariance,
            check_valid="raise",
        )
        sampled_baseline = {worker: float(sampled_baseline_values[index]) for index, worker in enumerate(baseline_rank)}
        sampled_buildings = [rng.choice(buildings) for _ in range(len(buildings))] if buildings else []
        task_instances = [
            (
                f"building-instance-{building_index}",
                f"building-instance-{building_index}|task-slot-{task_index}",
                building,
                rng.choice(task_by_building[building]),
            )
            for building_index, building in enumerate(sampled_buildings)
            for task_index in range(len(task_by_building[building]))
        ]
        building_effect = {
            f"building-instance-{index}": rng.gauss(0.0, building_sd)
            for index in range(len(sampled_buildings))
        }
        task_effect = {
            task_instance: rng.gauss(0.0, task_sd)
            for _building_instance, task_instance, _building, _task in task_instances
        }
        rank_score, q_widths, draw_slope_widths, signs, support = {}, [], [], [], Counter()
        worker_outcomes: dict[str, list[tuple[float, float]]] = defaultdict(list)
        delivered_observations: list[dict[str, Any]] = []
        delivered_edges: list[tuple[str, str]] = []
        delivered_bridge_edges: list[tuple[str, str]] = []
        delivered_building_instances: set[str] = set()
        delivered_strata: set[str] = set()
        delivered_strata_by_worker: dict[str, set[str]] = defaultdict(set)
        instance_support = Counter({task_instance: 0 for _building_instance, task_instance, _building, _task in task_instances})
        for row in worker_rows:
            worker = safe(row.get("worker_id"))
            slope_distribution = slope_distributions[worker]
            independent_sd = float(slope_distribution["independent_sd"])
            sampled_slope = float(slope_distribution["mean"]) + shared_group_delta
            if independent_sd > 0:
                sampled_slope += rng.gauss(0.0, independent_sd)
            missing = _float(row, "missing_rate", default=math.nan)
            structural = _float(row, "F_struct", default=group_structural_rate)
            residual_scale = _float(row, "outcome_residual_sd", default=math.inf)
            for building_instance, task_instance, building, task in task_instances:
                sampled_task_id = safe(task.get("task_id"))
                for edge in edges_by_task.get(sampled_task_id, []):
                    if safe(edge.get("worker_id")) != worker or rng.random() < missing or rng.random() < structural:
                        continue
                    if safe(edge.get("task_id")) != sampled_task_id:
                        sampled_task_edge_identity_violations += 1
                        continue
                    risk = _float(task, "risk_design_score_A", default=0.0)
                    noise = rng.gauss(0.0, residual_scale) if math.isfinite(residual_scale) and residual_scale > 0 else 0.0
                    outcome = sampled_baseline[worker] + sampled_slope * risk + building_effect[building_instance] + task_effect[task_instance] + noise
                    worker_outcomes[worker].append((risk, outcome))
                    delivered_observations.append({
                        "worker": worker, "risk": risk, "outcome": outcome,
                        "building_instance": building_instance, "task_instance": task_instance,
                        "residual_sd": residual_scale,
                    })
                    delivered_edges.append((worker, task_instance)); instance_support[task_instance] += 1
                    if safe(edge.get("c2_component")) == "diverse_bridge":
                        delivered_bridge_edges.append((worker, task_instance))
                    delivered_building_instances.add(building_instance)
                    delivered_strata.add(_task_stratum(task)); delivered_strata_by_worker[worker].add(_task_stratum(task))
        if delivered_observations:
            worker_index = {worker: index for index, worker in enumerate(baseline_rank)}
            observation_count = len(delivered_observations)
            posterior_design = np.zeros((observation_count, len(baseline_rank)), dtype=float)
            risk_adjusted = np.zeros(observation_count, dtype=float)
            likelihood_covariance = np.zeros((observation_count, observation_count), dtype=float)
            for index, observation in enumerate(delivered_observations):
                worker = observation["worker"]
                risk = float(observation["risk"])
                posterior_design[index, worker_index[worker]] = 1.0
                risk_adjusted[index] = float(observation["outcome"]) - float(slope_distributions[worker]["mean"]) * risk
                likelihood_covariance[index, index] += float(observation["residual_sd"]) ** 2
                for other_index, other in enumerate(delivered_observations):
                    other_risk = float(other["risk"])
                    likelihood_covariance[index, other_index] += group_slope_se ** 2 * risk * other_risk
                    if worker == other["worker"]:
                        likelihood_covariance[index, other_index] += float(slope_distributions[worker]["independent_sd"]) ** 2 * risk * other_risk
                    if observation["building_instance"] == other["building_instance"]:
                        likelihood_covariance[index, other_index] += building_sd ** 2
                    if observation["task_instance"] == other["task_instance"]:
                        likelihood_covariance[index, other_index] += task_sd ** 2
            posterior_mean, posterior_covariance = _joint_qgt_posterior(
                np.asarray([baseline[worker] for worker in baseline_rank], dtype=float),
                covariance,
                posterior_design,
                risk_adjusted_outcomes=risk_adjusted,
                likelihood_covariance=likelihood_covariance,
            )
        else:
            posterior_mean = np.asarray([baseline[worker] for worker in baseline_rank], dtype=float)
            posterior_covariance = covariance.copy()
        rank_score = {worker: float(posterior_mean[index]) for index, worker in enumerate(baseline_rank)}
        q_widths.extend(1.96 * math.sqrt(max(0.0, float(posterior_covariance[index, index]))) for index in range(len(baseline_rank)))
        if common_slope_model:
            estimate, slope_width = _common_slope(worker_outcomes, group_slope_mean, group_slope_se)
            draw_slope_widths.extend([slope_width] * len(worker_rows))
            common_sign = (group_slope_mean == 0) or (estimate == 0) or (group_slope_mean * estimate > 0)
            signs.extend([common_sign] * len(worker_rows))
        else:
            for row in worker_rows:
                worker = safe(row.get("worker_id"))
                residual_scale = _float(row, "outcome_residual_sd", default=math.inf)
                delivered = worker_outcomes.get(worker, [])
                slope_distribution = slope_distributions[worker]
                estimate, slope_width = _slope(
                    delivered, float(slope_distribution["mean"]), float(slope_distribution["total_sd"]),
                    residual_scale, group_slope_se,
                )
                draw_slope_widths.append(slope_width)
                prior_slope = float(slope_distribution["mean"])
                signs.append((prior_slope == 0) or (estimate == 0) or (prior_slope * estimate > 0))
        draw_rank = sorted(rank_score, key=lambda worker: (-rank_score[worker], worker))
        rank_stable += draw_rank == baseline_rank
        slope_stable += all(signs)
        positions = {worker: index + 1 for index, worker in enumerate(draw_rank)}
        count = len(baseline_position)
        spearman_values.append(1.0 if count < 2 else 1 - (6 * sum((baseline_position[worker] - positions[worker]) ** 2 for worker in baseline_position)) / (count * (count ** 2 - 1)))
        top_k = min(3, count)
        top_k_values.append(len(set(draw_rank[:top_k]) & set(baseline_rank[:top_k])) / top_k if top_k else 0.0)
        rank_displacements.append(sum(abs(baseline_position[worker] - positions[worker]) for worker in baseline_position) / max(1, count))
        connected += _connected_delivered(delivered_edges)
        bridge_connected += _connected_delivered(delivered_bridge_edges)
        ordinary += "ordinary" in delivered_strata; stress += "stress" in delivered_strata
        ordinary_per_worker += sum("ordinary" in delivered_strata_by_worker.get(worker, set()) for worker in baseline) / max(1, len(baseline))
        stress_per_worker += sum("stress" in delivered_strata_by_worker.get(worker, set()) for worker in baseline) / max(1, len(baseline))
        full_building_coverage += len(delivered_building_instances) == len(sampled_buildings)
        delivered_building_counts.append(len(delivered_building_instances))
        min_worker_supports.append(min((len(worker_outcomes.get(worker, [])) for worker in baseline), default=0))
        min_task_supports.append(min(instance_support.values(), default=0))
        delivered_counts.append(len(delivered_edges))
        q_half_widths.extend(q_widths)
        slope_half_widths.extend(value for value in draw_slope_widths if math.isfinite(value))
    finite_q = [value for value in q_half_widths if math.isfinite(value)]
    finite_slope = [value for value in slope_half_widths if math.isfinite(value)]
    def p05(values: list[int]) -> int | str:
        ordered = sorted(values)
        return ordered[max(0, math.ceil(.05 * len(ordered)) - 1)] if ordered else ""

    return {
        "design_id": design_id, "seed": seed, "draws": draws,
        "max_ci_half_width": max(finite_q) if finite_q else "",
        "median_ci_half_width": sorted(finite_q)[len(finite_q) // 2] if finite_q else "",
        "q_gt_max_ci_half_width": max(finite_q) if finite_q else "",
        "risk_slope_max_ci_half_width": max(finite_slope) if finite_slope else "",
        "rank_stability": rank_stable / draws, "worker_rank_spearman": sum(spearman_values) / len(spearman_values) if spearman_values else "",
        "top_k_overlap": sum(top_k_values) / len(top_k_values) if top_k_values else "", "mean_rank_displacement": sum(rank_displacements) / len(rank_displacements) if rank_displacements else "",
        "risk_slope_direction_stability": slope_stable / draws,
        "minimum_worker_support": min(min_worker_supports, default=0), "minimum_task_support": min(min_task_supports, default=0),
        "minimum_worker_support_p05": p05(min_worker_supports), "minimum_task_support_p05": p05(min_task_supports),
        "minimum_worker_support_threshold_probability": (
            sum(value >= minimum_worker_support_threshold for value in min_worker_supports) / draws
            if minimum_worker_support_threshold is not None else ""
        ),
        "minimum_task_support_threshold_probability": (
            sum(value >= minimum_task_support_threshold for value in min_task_supports) / draws
            if minimum_task_support_threshold is not None else ""
        ),
        "support_extreme_minimum_role": "extreme_audit_only_not_dispatch_gate",
        "graph_connectivity_probability": connected / draws, "bridge_only_connectivity_probability": bridge_connected / draws, "building_coverage": min(delivered_building_counts, default=0), "building_coverage_probability": full_building_coverage / draws,
        "ordinary_coverage_probability": ordinary / draws, "stress_coverage_probability": stress / draws,
        "ordinary_coverage_probability_per_worker": ordinary_per_worker / draws,
        "stress_coverage_probability_per_worker": stress_per_worker / draws,
        "expected_assignment_count": sum(delivered_counts) / len(delivered_counts) if delivered_counts else 0,
        "sampled_task_edge_identity_violations": sampled_task_edge_identity_violations,
        "variance_fields_used": list(required_variances),
        "uncertainty_fields_used": ["risk_slope_for_simulation", "risk_slope_se", "risk_slope_support", "group_slope_mean", "group_slope_se", "between_worker_slope_sd", "Q_GT_contrast_covariance", "outcome_residual_sd", "task_sd", "building_sd", "missing_rate", "F_struct"],
        "worker_slope_distribution_sources": dict(sorted((worker, value["source"]) for worker, value in slope_distributions.items())),
        "risk_slope_posterior_method": "shared_common_slope_pooled_within_worker" if common_slope_model else "worker_specific_or_group_prior_posterior",
        "rank_score_method": "joint_gaussian_C1_C2_posterior_mean_with_full_C1_covariance",
        "known_c1_worker_intercept_sd_resampled": False,
        "population_worker_intercept_sd_recorded": worker_intercept_sd if math.isfinite(worker_intercept_sd) else "not_applicable_worker_fixed_intercepts",
        "simulation_method": "hierarchical_building_task_resampling_with_joint_qgt_and_unified_slope_posterior_v2", "simulation_status": "estimated",
    }


def _dependencies_valid(
    manifest: dict[str, Any],
    worker_profile_csv: Path,
    task_pool_csv: Path,
    c1_closeout_summary: Path | None,
    risk_summary: Path | None,
) -> tuple[bool, str]:
    expected = manifest.get("input_sha256") or {}
    actual = {
        "worker_profile_csv": sha256_file(worker_profile_csv),
        "task_pool_csv": sha256_file(task_pool_csv),
    }
    for key, value in actual.items():
        if expected.get(key) != value:
            return False, f"stale_or_unbound:{key}"
    if not c1_closeout_summary or not c1_closeout_summary.exists():
        return False, "formal_c1_closeout_missing"
    closeout = json.loads(c1_closeout_summary.read_text(encoding="utf-8"))
    if not closeout.get("C2B_BASELINE_INPUT_FROZEN"):
        return False, "c2b_baseline_input_not_frozen"
    if expected.get("c1_closeout_summary") != sha256_file(c1_closeout_summary):
        return False, "stale_or_unbound:c1_closeout_summary"
    if not risk_summary or not risk_summary.exists():
        return False, "formal_risk_summary_missing"
    risk = json.loads(risk_summary.read_text(encoding="utf-8"))
    if not risk.get("formal_ready") or not risk.get("state_machine", {}).get("C2B_RISK_DESIGN_FROZEN"):
        return False, "c2b_risk_design_not_frozen"
    if expected.get("risk_summary") != sha256_file(risk_summary):
        return False, "stale_or_unbound:risk_summary"
    return True, ""


def enumerate_candidates(
    task_pool_csv: Path,
    worker_profile_csv: Path,
    design_manifest: Path,
    output_dir: Path,
    *,
    c1_closeout_summary: Path,
    threshold_manifest: Path,
    eligibility_evidence_csv: Path,
    risk_summary: Path,
) -> dict[str, Any]:
    """Enumerate SHA-bound C2-B candidates; this function never selects or assigns."""
    manifest = json.loads(design_manifest.read_text(encoding="utf-8"))
    if manifest.get("manifest_version") != "c2_design_v1":
        raise ValueError("unsupported C2 design manifest version")
    manifest_sha = sha256_file(design_manifest)
    risk_contract, risk_contract_sha = _load_risk_contract()
    threshold_payload, threshold_sha = _load_thresholds(threshold_manifest)
    _amendment, amendment_sha = _load_predispatch_amendment()
    formal_thresholds_ready = _thresholds_allow_formal_selection(threshold_payload)
    designs = manifest.get("candidate_designs")
    design_ids = [safe(row.get("design_id")) for row in designs or []]
    if not designs or not all(design_ids) or len(design_ids) != len(set(design_ids)):
        raise ValueError("candidate_designs require unique non-empty design_id values")
    if design_ids != ["D8", "D10", "D12"]:
        raise ValueError("C2-B candidate designs must be exactly ordered D8, D10, D12")
    dependency_valid, dependency_reason = _dependencies_valid(
        manifest, worker_profile_csv, task_pool_csv, c1_closeout_summary, risk_summary
    )
    if safe(manifest.get("threshold_manifest_sha256")) != threshold_sha:
        dependency_valid, dependency_reason = False, "stale_or_unbound:threshold_manifest"
    if safe(manifest.get("predispatch_amendment_sha256")) != amendment_sha:
        dependency_valid, dependency_reason = False, "stale_or_unbound:predispatch_amendment"
    upstream_state: dict[str, Any] = {}
    if c1_closeout_summary and c1_closeout_summary.exists():
        try:
            upstream_state = json.loads(c1_closeout_summary.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            upstream_state = {}
    risk_state: dict[str, Any] = {}
    if risk_summary and risk_summary.exists():
        try:
            risk_state = json.loads(risk_summary.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            risk_state = {}
    if not eligibility_evidence_csv.exists():
        dependency_valid, dependency_reason = False, "c2b_task_eligibility_evidence_missing"
    evidence_rows = {safe(row.get("task_id")): row for row in read_csv(eligibility_evidence_csv)} if eligibility_evidence_csv.exists() else {}
    pool_rows_for_selection = read_csv(task_pool_csv)
    pool_ids = {safe(row.get("task_id")) for row in pool_rows_for_selection}
    if pool_ids and not pool_ids.issubset(evidence_rows):
        dependency_valid, dependency_reason = False, "c2b_task_eligibility_evidence_not_covering_pool"
    for row in pool_rows_for_selection:
        evidence_row = evidence_rows.get(safe(row.get("task_id")))
        row["assignment_eligible"] = str(evidence_row and truthy(evidence_row.get("assignment_eligible"))).lower()
    if safe(manifest.get("risk_contract_sha256")) != risk_contract_sha:
        dependency_valid, dependency_reason = False, "stale_or_unbound:risk_design_contract"
    workers_rows = _eligible_workers(read_csv(worker_profile_csv))
    workers = [safe(row["worker_id"]) for row in workers_rows]
    pool = pool_rows_for_selection
    eligible_pool = [row for row in pool if truthy(row.get("assignment_eligible"))]
    invalid_risk = [row for row in eligible_pool if safe(row.get("risk_design_stratum_status")) != "frozen_from_C1" or _task_stratum(row) not in {"ordinary", "stress"}]
    contract_shas = {safe(row.get("risk_contract_sha256")) for row in eligible_pool}
    expected_contract_sha = safe(manifest.get("risk_contract_sha256"))
    if invalid_risk or not expected_contract_sha or contract_shas != {expected_contract_sha} or expected_contract_sha != risk_contract_sha:
        raise ValueError("formal C2-B task pool requires one frozen risk_design_stratum contract")
    anchors, bridges = _anchor_pool(pool), _bridge_pool(pool)
    audits: list[dict[str, Any]] = []
    candidates: list[tuple[int, str, list[dict[str, Any]], dict[str, Any], dict[str, Any]]] = []
    evaluated: list[tuple[int, str, list[dict[str, Any]], dict[str, Any], dict[str, Any]]] = []
    worker_projections: list[dict[str, Any]] = []
    simulation_rows: list[dict[str, Any]] = []
    stability_rows: list[dict[str, Any]] = []
    task_selection_rows: list[dict[str, Any]] = []
    simulation = manifest.get("simulation") or {}
    simulation_seed = int(simulation.get("seed", 0))
    simulation_draws = int(simulation.get("draws", 1000))
    threshold_values = threshold_payload.get("thresholds", threshold_payload)

    for raw in designs:
        design_id = safe(raw.get("design_id"))
        common_n = _int(raw, "common_anchor_count")
        bridge_per_worker = _int(raw, "bridge_per_worker")
        unique_bridge_upper = _int(raw, "unique_bridge_tasks")
        min_support = _int(raw, "min_task_support", default=1)
        max_imbalance = _int(raw, "max_worker_stratum_imbalance", default=1)
        if min(common_n, bridge_per_worker, unique_bridge_upper, min_support) < 1 or max_imbalance < 0:
            raise ValueError(f"invalid positive design counts: {design_id}")
        if min_support < int(risk_contract["simulation"]["minimum_task_support"]):
            raise ValueError(f"C2-B min_task_support is below frozen contract: {design_id}")
        selected_anchors = _select_anchors(anchors, common_n)
        anchor_ids = {_task_id(task) for task in selected_anchors}
        selected_bridges, bridge_edges, search_graph, search_attempts, search_failure = _search_bridge_assignment(
            design_id,
            workers,
            [task for task in bridges if _task_id(task) not in anchor_ids],
            selected_anchors,
            unique_bridge_upper,
            bridge_per_worker,
            min_support,
            max_imbalance,
            math.ceil(float(threshold_values.get("minimum_building_coverage", 0))),
        )
        unique_bridge_n = len(selected_bridges)
        anchor_center = {index: sum(_risk_vector(task)[index] for task in selected_anchors) / len(selected_anchors) for index in range(4)} if selected_anchors else {}
        prior = []
        for step, task in enumerate(selected_anchors, 1):
            task_selection_rows.append({
                "design_id": design_id, "selection_step": step, "task_id": _task_id(task), "base_task_id": safe(task.get("base_task_id")) or _task_id(task), "selection_role": "common_anchor",
                "risk_design_vector_A": task.get("risk_design_vector_A", ""), "risk_design_score_A": task.get("risk_design_score_A", ""), "risk_design_stratum": _task_stratum(task),
                "selection_distance": sum((_risk_vector(task)[index] - anchor_center[index]) ** 2 for index in anchor_center) ** .5 if anchor_center else "",
                "building_gain": safe(task.get("building_id")) not in {safe(item.get("building_id")) for item in prior}, "legacy_curated_priority_used": False, "selection_reason": "risk_center_scope_reference_feature_gate",
            })
            prior.append(task)
        for step, task in enumerate(selected_bridges, 1):
            reference = [*selected_anchors, *selected_bridges[:step - 1]]
            task_selection_rows.append({
                "design_id": design_id, "selection_step": step, "task_id": _task_id(task), "base_task_id": safe(task.get("base_task_id")) or _task_id(task), "selection_role": "diverse_bridge",
                "risk_design_vector_A": task.get("risk_design_vector_A", ""), "risk_design_score_A": task.get("risk_design_score_A", ""), "risk_design_stratum": _task_stratum(task),
                "selection_distance": min((_risk_distance(task, item) for item in reference), default=""),
                "building_gain": safe(task.get("building_id")) not in {safe(item.get("building_id")) for item in reference}, "legacy_curated_priority_used": False, "selection_reason": "continuous_risk_maximin_building_gain",
            })
        rows: list[dict[str, Any]] = []
        pre_failures = [dependency_reason] if dependency_reason else []
        if not workers:
            pre_failures.append("no_eligible_workers")
        if len(selected_anchors) != common_n:
            pre_failures.append("insufficient_common_anchor_tasks")
        if search_failure:
            pre_failures.extend(search_failure.split(";"))
        if workers and len(selected_anchors) == common_n and bridge_edges:
            for worker in workers:
                for task in selected_anchors:
                    rows.append({
                        "round_id": "C2-B", "worker_id": worker, "task_id": _task_id(task),
                        "base_task_id": safe(task.get("base_task_id")) or _task_id(task),
                        "image_id": safe(task.get("image_id")), "dataset_group": safe(task.get("dataset_group")),
                        "image_path": safe(task.get("image_path") or task.get("source_path")), "risk_design_score_A": task.get("risk_design_score_A", ""),
                        "task_stratum": _task_stratum(task), "assignment_batch": "C2-B",
                        "c2_component": "common_anchor", "design_id": design_id,
                        "design_manifest_sha256": manifest_sha,
                        "selection_role": "common_anchor", "selection_reason": "risk_center_and_stratum_building_coverage", "maximin_distance_at_selection": "", "building_gain": "", "legacy_curated_priority_used": False,
                    })
            for worker, task in bridge_edges or []:
                rows.append({
                    "round_id": "C2-B", "worker_id": worker, "task_id": _task_id(task),
                    "base_task_id": safe(task.get("base_task_id")) or _task_id(task),
                    "image_id": safe(task.get("image_id")), "dataset_group": safe(task.get("dataset_group")),
                    "image_path": safe(task.get("image_path") or task.get("source_path")), "risk_design_score_A": task.get("risk_design_score_A", ""),
                    "task_stratum": _task_stratum(task), "assignment_batch": "C2-B",
                    "c2_component": "diverse_bridge", "design_id": design_id,
                    "design_manifest_sha256": manifest_sha,
                    "selection_role": "diverse_bridge", "selection_reason": "deterministic_risk_space_maximin", "maximin_distance_at_selection": "recorded_by_frozen_selection_order", "building_gain": bool(task.get("building_id")), "legacy_curated_priority_used": False,
                })
        graph = _graph_audit(design_id, workers, rows, {_task_id(task) for task in selected_bridges})
        projected, projection_rows = _projected_worker_intervals(
            workers_rows,
            rows,
            {_task_id(task): task for task in [*selected_anchors, *selected_bridges]},
            seed=simulation_seed,
            draws=simulation_draws,
            require_c1_slopes=False,
        )
        worker_projections.extend(projection_rows)
        simulation_row = _empirical_cluster_bootstrap(
            design_id, workers_rows, rows, {_task_id(task): task for task in [*selected_anchors, *selected_bridges]}, graph,
            seed=simulation_seed, draws=simulation_draws,
            minimum_worker_support_threshold=int(threshold_values["minimum_worker_support"]),
            minimum_task_support_threshold=int(threshold_values["minimum_task_support"]),
        )
        simulation_rows.append(simulation_row)
        stability_rows.extend(_recompute_stability_audits(
            design_id, workers_rows, rows,
            {_task_id(task): task for task in [*selected_anchors, *selected_bridges]},
            seed=simulation_seed, draws=simulation_draws,
        ))
        target_raw = risk_contract["simulation"].get("max_q_gt_ci_half_width")
        target = float(target_raw) if target_raw not in {None, ""} else math.inf
        simulated_half_width = _float(simulation_row, "max_ci_half_width", default=projected)
        failures = list(pre_failures)
        if simulation_row.get("simulation_status") != "estimated":
            failures.append(f"simulation_{simulation_row.get('simulation_status') or 'not_estimable'}")
        if not _float_le(projected, target) or not _float_le(simulated_half_width, target):
            failures.append("projected_ci_half_width_above_target")
        if not graph["worker_task_graph_connected"]:
            failures.append("worker_task_graph_disconnected")
        if graph["max_worker_stratum_imbalance"] > max_imbalance:
            failures.append("worker_stratum_imbalance")
        threshold_failures = _threshold_failures(simulation_row, graph, threshold_payload)
        failures.extend(f"threshold_gate_failed:{failure}" for failure in threshold_failures)
        failures = list(dict.fromkeys(failures))
        reason = failures[0] if failures else ""
        stress_task_count = search_graph.get("stress_bridge_task_count", 0)
        stress_support = search_graph.get("stress_bridge_assignment_support", 0)
        audit = {
            "design_id": design_id, "common_anchor_count": common_n,
            "bridge_per_worker": bridge_per_worker, "unique_bridge_tasks_upper_bound": unique_bridge_upper,
            "unique_bridge_tasks": unique_bridge_n, "bridge_search_attempt_count": search_attempts,
            "stress_bridge_task_count": stress_task_count,
            "stress_bridge_assignment_support": stress_support,
            "stress_bridge_repeat_support": max(0, stress_support - stress_task_count * min_support),
            "deterministic_min_worker_support": graph["minimum_worker_support"],
            "deterministic_min_task_support": graph["min_bridge_task_support"],
            "min_task_support": min_support, "n_assignments": len(rows),
            "projected_max_ci_half_width": "" if not math.isfinite(simulated_half_width) else simulated_half_width,
            "worker_task_graph_connected": graph["worker_task_graph_connected"],
            "stratum_balance_valid": graph["max_worker_stratum_imbalance"] <= max_imbalance,
            "design_method": "c1_risk_slope_precision_candidate_with_downward_unique_bridge_search",
            "rank_displacement_gate_role": "post_C2_diagnostic_not_dispatch_gate",
            "feasible": not failures, "non_dominated": False, "failure_reason": reason,
            "all_failure_gates": ";".join(failures),
        }
        audits.append(audit)
        evaluated.append((len(rows), design_id, rows, graph, simulation_row))
        if not failures:
            candidates.append((len(rows), design_id, rows, graph, simulation_row))

    candidates.sort(key=lambda item: (item[0], item[1]))
    costs = ("q_gt_max_ci_half_width", "risk_slope_max_ci_half_width")
    benefits = ("rank_stability", "graph_connectivity_probability", "building_coverage", "ordinary_coverage_probability", "stress_coverage_probability")

    def dominates(left: tuple, right: tuple) -> bool:
        left_values = [float(left[0]), *(_float(left[4], field) for field in costs), *(-_float(left[4], field, default=-math.inf) for field in benefits)]
        right_values = [float(right[0]), *(_float(right[4], field) for field in costs), *(-_float(right[4], field, default=-math.inf) for field in benefits)]
        return all(_float_le(a, b) for a, b in zip(left_values, right_values)) and any(
            a < b and not math.isclose(a, b, rel_tol=1e-12, abs_tol=1e-12)
            for a, b in zip(left_values, right_values)
        )

    non_dominated = [candidate for candidate in candidates if not any(dominates(other, candidate) for other in candidates if other is not candidate)]
    non_dominated_ids = {item[1] for item in non_dominated}
    for audit in audits:
        audit["non_dominated"] = audit["design_id"] in non_dominated_ids
    output_dir.mkdir(parents=True, exist_ok=True)
    write_csv(output_dir / "c2b_design_candidates.csv", audits, DESIGN_AUDIT_FIELDS)
    write_csv(output_dir / "c2b_worker_projection_audit.csv", worker_projections, WORKER_PROJECTION_FIELDS)
    write_csv(output_dir / "c2b_task_selection_audit.csv", task_selection_rows, TASK_SELECTION_AUDIT_FIELDS)
    write_csv(output_dir / "c2b_simulation_draw_summary.csv", simulation_rows, SIMULATION_FIELDS)
    write_csv(output_dir / "c2b_loto_lobo_anchor_stability_audit.csv", stability_rows)
    write_csv(output_dir / "c2b_policy_feasibility_audit.csv", audits, DESIGN_AUDIT_FIELDS)
    candidate_edges = [row for _count, _design, rows, _graph, _simulation in evaluated for row in rows]
    write_csv(output_dir / "c2b_candidate_worker_task_edges.csv", candidate_edges, ASSIGNMENT_FIELDS)
    write_csv(output_dir / "c2b_worker_task_graph_audit.csv", [item[3] for item in evaluated], GRAPH_AUDIT_FIELDS)
    summary = {
        "design_manifest": str(design_manifest),
        "design_manifest_sha256": manifest_sha,
        "threshold_manifest_sha256": threshold_sha,
        "predispatch_amendment_sha256": amendment_sha,
        "input_sha256": {
            "worker_profile_csv": sha256_file(worker_profile_csv),
            "task_pool_csv": sha256_file(task_pool_csv),
            "c1_closeout_summary": sha256_file(c1_closeout_summary),
            "risk_summary": sha256_file(risk_summary),
            "eligibility_evidence_csv": sha256_file(eligibility_evidence_csv),
        },
        "dependency_binding_valid": dependency_valid,
        "chosen_design_id": "",
        "recommended_design_id": candidates[0][1] if candidates else "",
        "recommendation_rule": "first minimum ordered design satisfying graph coverage precision and budget gates",
        "n_assignments": 0,
        "c2b_design_ready": False,
        "candidate_only": True,
        "launch_ready": False,
        "formal_selection_allowed": formal_thresholds_ready,
        "failure_reason": "candidate_only_no_selection" if candidates else (dependency_reason or "no_feasible_c2b_design"),
        "n_feasible_candidate_designs": len(candidates),
        "n_non_dominated_candidate_designs": len(non_dominated),
        "candidate_assignment_rows": 0,
    }
    summary["state_machine"] = {
        "C1_COLLECTION_INCOMPLETE": bool(upstream_state.get("C1_COLLECTION_INCOMPLETE", False)),
        "C1_CANONICAL_CLOSED": bool(upstream_state.get("C1_CANONICAL_CLOSED", False)),
        "C1_MEASUREMENT_FROZEN": bool(upstream_state.get("C1_MEASUREMENT_FROZEN", False)),
        "C1_EVIDENCE_BUNDLE_FROZEN": bool(upstream_state.get("C1_EVIDENCE_BUNDLE_FROZEN", False)),
        "C2B_BASELINE_INPUT_FROZEN": bool(upstream_state.get("C2B_BASELINE_INPUT_FROZEN", False)),
        "C2B_RISK_DESIGN_FROZEN": bool(risk_state.get("state_machine", {}).get("C2B_RISK_DESIGN_FROZEN")),
        "C2B_DESIGN_FROZEN": False,
        "C2B_ASSIGNMENT_MATERIALIZED": False,
        "C2B_LAUNCH_READY": False,
    }
    write_json(output_dir / "c2b_design.summary.json", summary)
    return summary


def materialize_approved_assignment(
    candidate_dir: Path,
    design_manifest: Path,
    threshold_manifest: Path,
    selected_design_approval: Path,
    selected_task_approval: Path,
    eligibility_evidence_csv: Path,
    c1_closeout_summary: Path,
    risk_summary: Path,
    output_dir: Path,
) -> dict[str, Any]:
    """Materialize an approved design from frozen candidate edges without recomputation."""
    manifest_sha = sha256_file(design_manifest)
    threshold_payload = json.loads(threshold_manifest.read_text(encoding="utf-8"))
    if not _thresholds_allow_formal_selection(threshold_payload):
        raise ValueError("formal_selection_thresholds_unapproved")

    c1 = json.loads(c1_closeout_summary.read_text(encoding="utf-8"))
    risk = json.loads(risk_summary.read_text(encoding="utf-8"))
    if not c1.get("C2B_BASELINE_INPUT_FROZEN"):
        raise ValueError("C1 Q_GT/process/independence baseline is not formally frozen")
    if not risk.get("formal_ready") or not risk.get("state_machine", {}).get("C2B_RISK_DESIGN_FROZEN"):
        raise ValueError("C2 task risk is not formally frozen")

    candidate_summary_path = candidate_dir / "c2b_design.summary.json"
    candidate_edges_path = candidate_dir / "c2b_candidate_worker_task_edges.csv"
    candidate_audit_path = candidate_dir / "c2b_design_candidates.csv"
    for path in (candidate_summary_path, candidate_edges_path, candidate_audit_path):
        if not path.exists():
            raise ValueError(f"candidate bundle missing: {path.name}")
    candidate_summary = json.loads(candidate_summary_path.read_text(encoding="utf-8"))
    if candidate_summary.get("design_manifest_sha256") != manifest_sha:
        raise ValueError("candidate bundle design manifest SHA mismatch")
    if candidate_summary.get("threshold_manifest_sha256") != sha256_file(threshold_manifest):
        raise ValueError("candidate bundle threshold manifest SHA mismatch")
    if candidate_summary.get("candidate_only") is not True:
        raise ValueError("approved assignment requires a candidate-only design bundle")

    design_approval = json.loads(selected_design_approval.read_text(encoding="utf-8"))
    selected_id = safe(design_approval.get("selected_design_id"))
    if (
        design_approval.get("approved") is not True
        or design_approval.get("design_manifest_sha256") != manifest_sha
        or design_approval.get("candidate_summary_sha256") != sha256_file(candidate_summary_path)
        or design_approval.get("candidate_edges_sha256") != sha256_file(candidate_edges_path)
        or not selected_id
    ):
        raise ValueError("selected design approval is invalid or stale")
    audits = {safe(row.get("design_id")): row for row in read_csv(candidate_audit_path)}
    selected_audit = audits.get(selected_id)
    if not selected_audit or not truthy(selected_audit.get("feasible")) or not truthy(selected_audit.get("non_dominated")):
        raise ValueError("selected design is not a feasible non-dominated candidate")
    if selected_id != safe(candidate_summary.get("recommended_design_id")):
        raise ValueError("selected design is not the first minimum feasible D8/D10/D12 design")

    candidate_edges = [row for row in read_csv(candidate_edges_path) if safe(row.get("design_id")) == selected_id]
    if not candidate_edges:
        raise ValueError("selected design has no frozen candidate edges")
    eligible_tasks = {
        safe(row.get("task_id")) for row in read_csv(eligibility_evidence_csv)
        if truthy(row.get("assignment_eligible"))
    }
    actual_task_ids = {safe(row.get("task_id")) for row in candidate_edges}
    if not actual_task_ids or not actual_task_ids <= eligible_tasks:
        raise ValueError("selected design contains a task outside frozen eligibility evidence")

    task_approval = json.loads(selected_task_approval.read_text(encoding="utf-8"))
    approved_ids = {safe(value) for value in task_approval.get("selected_task_ids", [])}
    if (
        task_approval.get("approved") is not True
        or task_approval.get("design_manifest_sha256") != manifest_sha
        or task_approval.get("task_eligibility_evidence_sha256") != sha256_file(eligibility_evidence_csv)
        or task_approval.get("approved_task_set_sha256") != _task_set_sha(actual_task_ids)
        or approved_ids != actual_task_ids
    ):
        raise ValueError("selected task approval does not bind the frozen selected task set")

    output_dir.mkdir(parents=True, exist_ok=True)
    assignment_path = output_dir / "assignment_manifest_C2B.csv"
    write_csv(assignment_path, candidate_edges, ASSIGNMENT_FIELDS)
    summary = {
        "design_manifest_sha256": manifest_sha,
        "threshold_manifest_sha256": sha256_file(threshold_manifest),
        "candidate_summary_sha256": sha256_file(candidate_summary_path),
        "candidate_edges_sha256": sha256_file(candidate_edges_path),
        "eligibility_evidence_sha256": sha256_file(eligibility_evidence_csv),
        "selected_design_approval_sha256": sha256_file(selected_design_approval),
        "selected_task_approval_sha256": sha256_file(selected_task_approval),
        "chosen_design_id": selected_id,
        "n_assignments": len(candidate_edges),
        "n_tasks": len(actual_task_ids),
        "candidate_only": False,
        "c2b_design_ready": True,
        "launch_ready": True,
        "state_machine": {
            "C1_COLLECTION_INCOMPLETE": bool(c1.get("C1_COLLECTION_INCOMPLETE", False)),
            "C1_CANONICAL_CLOSED": bool(c1.get("C1_CANONICAL_CLOSED")),
            "C1_MEASUREMENT_FROZEN": bool(c1.get("C1_MEASUREMENT_FROZEN")),
            "C1_EVIDENCE_BUNDLE_FROZEN": bool(c1.get("C1_EVIDENCE_BUNDLE_FROZEN")),
            "C2B_BASELINE_INPUT_FROZEN": bool(c1.get("C2B_BASELINE_INPUT_FROZEN")),
            "C2B_RISK_DESIGN_FROZEN": bool(risk.get("state_machine", {}).get("C2B_RISK_DESIGN_FROZEN")),
            "C2B_DESIGN_FROZEN": True,
            "C2B_ASSIGNMENT_MATERIALIZED": True,
            "C2B_LAUNCH_READY": True,
        },
    }
    write_json(output_dir / "c2b_design.summary.json", summary)
    from tools.thesis_main.analysis.paper_a_contracts import METHOD_CONTRACT, load_method_contract
    write_json(output_dir / "c2b_selected_design.json", {"design_id": selected_id, "n_assignments": len(candidate_edges), "formal": True, "contract_role": "generated_subordinate", "method_contract_version": load_method_contract()["contract_version"], "method_contract_sha256": sha256_file(METHOD_CONTRACT)})
    return summary
