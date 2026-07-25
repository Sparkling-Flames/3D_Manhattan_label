from __future__ import annotations

import json
import math
import random
import sys
from collections import Counter, defaultdict, deque
from pathlib import Path
from typing import Any

_PROJECT_ROOT = Path(__file__).resolve().parents[3]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from tools.thesis_main.analysis.c1_live_collection_monitor import read_csv, safe, truthy, write_csv, write_json
from tools.thesis_main.analysis.vfinal_artifact_utils import sha256_file


RISK_CONTRACT = _PROJECT_ROOT / "docs" / "thesis_main" / "C2B_RISK_DESIGN_CONTRACT_v1.json"
DESIGN_THRESHOLDS = _PROJECT_ROOT / "docs" / "thesis_main" / "C2B_DESIGN_SELECTION_THRESHOLDS.json"


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
    if payload.get("schema_version") != "paper_a_c2b_design_selection_thresholds_v1":
        raise ValueError("unsupported C2-B design threshold manifest")
    return payload, sha256_file(path)


ASSIGNMENT_FIELDS = [
    "round_id", "worker_id", "task_id", "base_task_id", "task_stratum",
    "image_id", "dataset_group", "image_path", "risk_design_score_A",
    "assignment_batch", "c2_component", "design_id", "design_manifest_sha256",
    "selection_role", "selection_reason", "maximin_distance_at_selection", "building_gain", "legacy_curated_priority_used",
]
DESIGN_AUDIT_FIELDS = [
    "design_id", "common_anchor_count", "bridge_per_worker", "unique_bridge_tasks",
    "min_task_support", "n_assignments", "projected_max_ci_half_width",
    "worker_task_graph_connected", "stratum_balance_valid", "design_method",
    "feasible", "non_dominated", "failure_reason",
]
WORKER_PROJECTION_FIELDS = [
    "design_id", "worker_id", "current_interval_half_width", "projected_interval_half_width",
    "ordinary_support", "stress_support", "common_anchor_support", "bridge_support",
    "unique_image_coverage", "building_coverage", "common_bridge_with_other_min",
    "missing_rate", "structural_failure_rate", "effective_information",
    "expected_fallback_rate", "expected_global_full_divergence", "v1_usable_support",
]
GRAPH_AUDIT_FIELDS = [
    "design_id", "n_workers", "n_tasks", "n_edges", "n_connected_components",
    "worker_task_graph_connected", "duplicate_worker_task_count", "min_bridge_task_support",
    "max_worker_stratum_imbalance",
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
    "graph_connectivity_probability", "building_coverage", "building_coverage_probability",
    "ordinary_coverage_probability", "stress_coverage_probability", "ordinary_coverage_probability_per_worker", "stress_coverage_probability_per_worker", "expected_assignment_count",
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
        [row for row in rows if _task_id(row) and truthy(row.get("assignment_eligible")) and truthy(row.get("anchor_eligible") or row.get("is_common_anchor") or row.get("eligible_for_anchor_candidate"))],
        key=lambda row: (_task_stratum(row), _task_id(row)),
    )


def _bridge_pool(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    return sorted(
        [
            row for row in rows
            if _task_id(row)
            and truthy(row.get("assignment_eligible"))
            and truthy(row.get("bridge_eligible") or row.get("is_diverse_bridge") or row.get("eligible_for_reserve_candidate"))
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
    required = ("q_gt_ci_half_width", "risk_slope_ci_half_width", "rank_stability", "minimum_worker_support", "minimum_task_support", "graph_connectivity_probability", "minimum_building_coverage", "building_coverage_probability", "ordinary_coverage_probability", "stress_coverage_probability")
    return (
        thresholds.get("status") == "approved"
        and thresholds.get("formal_selection_allowed") is True
        and all(str(thresholds.get(field, "")).strip() for field in ("approved_by", "approved_at"))
        and int(anchors.get("minimum_count", 0)) >= 2
        and set(anchors.get("required_strata", [])) >= {"ordinary", "stress"}
        and all(values.get(name) not in {None, ""} for name in required)
    )


def _task_set_sha(task_ids: set[str]) -> str:
    payload = json.dumps(sorted(task_ids), separators=(",", ":"), ensure_ascii=False)
    return __import__("hashlib").sha256(payload.encode("utf-8")).hexdigest()


def build_candidate_design_manifest(
    task_pool_csv: Path, worker_profile_csv: Path, c1_closeout_summary: Path | None,
    output: Path, *, threshold_manifest: Path = DESIGN_THRESHOLDS,
    risk_summary: Path | None = None, seed: int = 20260724, draws: int = 1000,
) -> Path:
    """Enumerate designs from the realized frozen pool; never select one."""
    tasks = [row for row in read_csv(task_pool_csv) if truthy(row.get("assignment_eligible"))]
    workers = _eligible_workers(read_csv(worker_profile_csv))
    anchors, bridges = len(_anchor_pool(tasks)), len(_bridge_pool(tasks))

    def levels(low: int, high: int) -> list[int]:
        if high < low:
            return []
        span = high - low
        return sorted({low, low + (span + 2) // 3, low + (2 * span + 2) // 3, high})

    candidates = []
    for common in levels(2, min(anchors, max(2, len(workers)))):
        for per_worker in levels(1, min(bridges, max(1, 2 * math.ceil(bridges / max(1, len(workers)))))):
            minimum_unique = max(1, math.ceil(len(workers) * per_worker / 2))
            for unique in levels(minimum_unique, min(bridges, len(workers) * per_worker)):
                candidates.append({
                    "design_id": f"candidate_a{common}_b{per_worker}_u{unique}",
                    "common_anchor_count": common,
                    "bridge_per_worker": per_worker,
                    "unique_bridge_tasks": unique,
                    "min_task_support": 2,
                    "max_worker_stratum_imbalance": 2,
                })
    manifest = {
        "manifest_version": "c2_design_v1",
        "artifact_role": "formal_candidate_enumeration_only",
        "input_sha256": {
            "worker_profile_csv": sha256_file(worker_profile_csv),
            "task_pool_csv": sha256_file(task_pool_csv),
            **({"c1_closeout_summary": sha256_file(c1_closeout_summary)} if c1_closeout_summary else {}),
            **({"risk_summary": sha256_file(risk_summary)} if risk_summary else {}),
        },
        "risk_contract_sha256": sha256_file(RISK_CONTRACT),
        "threshold_manifest_sha256": sha256_file(threshold_manifest),
        "candidate_designs": candidates,
        "simulation": {"seed": seed, "draws": draws, "resampling": "C1 empirical building/task/worker bootstrap"},
        "selection_rule": "human_approval_of_a_feasible_candidate_required",
    }
    write_json(output, manifest)
    return output


def _threshold_failures(simulation_row: dict[str, Any], graph: dict[str, Any], thresholds: dict[str, Any]) -> list[str]:
    values = thresholds.get("thresholds", thresholds)
    checks = {
        "q_gt_ci_half_width": ("q_gt_max_ci_half_width", lambda actual, limit: actual <= limit),
        "risk_slope_ci_half_width": ("risk_slope_max_ci_half_width", lambda actual, limit: actual <= limit),
        "rank_stability": ("rank_stability", lambda actual, limit: actual >= limit),
        "minimum_worker_support": ("minimum_worker_support", lambda actual, limit: actual >= limit),
        "minimum_task_support": ("minimum_task_support", lambda actual, limit: actual >= limit),
        "graph_connectivity_probability": ("graph_connectivity_probability", lambda actual, limit: actual >= limit),
        "minimum_building_coverage": ("building_coverage", lambda actual, limit: actual >= limit),
        "building_coverage_probability": ("building_coverage_probability", lambda actual, limit: actual >= limit),
        "ordinary_coverage_probability": ("ordinary_coverage_probability", lambda actual, limit: actual >= limit),
        "stress_coverage_probability": ("stress_coverage_probability", lambda actual, limit: actual >= limit),
    }
    failures = []
    for name, (field, predicate) in checks.items():
        limit = values.get(name)
        if limit in {None, ""}:
            continue
        try:
            actual = float(simulation_row.get(field, graph.get(field, "")))
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
    ranked = sorted(rows, key=lambda row: (sum((left - right) ** 2 for left, right in zip(_risk_vector(row), center)), bool(row.get("building_id")) is False, not truthy(row.get("legacy_human_curated_candidate")), _task_id(row)))
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
            return (-distance, -(safe(row.get("building_id")) not in buildings), not truthy(row.get("legacy_human_curated_candidate")), _task_id(row))
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
    unseen = set(nodes)
    components = 0
    while unseen:
        components += 1
        queue = [unseen.pop()]
        while queue:
            for neighbor in graph[queue.pop()]:
                if neighbor in unseen:
                    unseen.remove(neighbor)
                    queue.append(neighbor)
    duplicate_count = len(edges) - len(set(edges))
    support = Counter(task for _, task in edges if task in bridge_task_ids)
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
        "worker_task_graph_connected": bool(nodes) and components == 1,
        "duplicate_worker_task_count": duplicate_count,
        "min_bridge_task_support": min(support.values()) if support else 0,
        "max_worker_stratum_imbalance": max(imbalances, default=0),
    }


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
        missing_rate = _float(row, "missing_rate", default=(max(0, assigned - observed) / assigned if assigned else 0.0))
        structural_rate = _float(row, "F_struct", default=0.0)
        buildings = {safe(task.get("building_id") or task.get("building")) for task in tasks} - {""}
        cluster_factor = math.sqrt(len(buildings) / len(tasks)) if tasks and buildings else 1.0
        added_information = raw_information * max(0.0, 1 - missing_rate) * max(0.0, 1 - structural_rate) * cluster_factor
        slope_se = _float(row, "risk_slope_se", default=math.inf)
        slope_support = _int(row, "risk_slope_support", "support", "n_support")
        if math.isfinite(slope_se) and slope_se > 0 and slope_support > 0:
            rng = random.Random(f"{seed}|{worker}|{added_information:.12g}")
            errors = []
            worker_variance = max(0.0, _float(row, "worker_intercept_sd", default=0.0)) ** 2
            task_variance = max(0.0, _float(row, "task_sd", default=0.0)) ** 2
            building_variance = max(0.0, _float(row, "building_sd", default=0.0)) ** 2
            for _ in range(draws):
                delivered = [task for task in tasks if rng.random() >= missing_rate and rng.random() >= structural_rate]
                information = sum(_float(task, "risk_information_weight", default=1.0) for task in delivered)
                projected_se = math.sqrt(1.0 / ((1.0 / slope_se ** 2) + information) + worker_variance + task_variance / max(1, len(delivered)) + building_variance / max(1, len({safe(task.get("building_id")) for task in delivered})))
                errors.append(abs(rng.gauss(0.0, projected_se)))
            errors.sort()
            value = errors[min(draws - 1, math.ceil(0.95 * draws) - 1)]
            current = 1.96 * slope_se
        else:
            # No unbound Bernoulli/CI fallback is permitted.  A worker without
            # an individual C1 slope uses only the frozen group-prior scale.
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
            "ordinary_support": strata["ordinary"], "stress_support": strata["stress"],
            "common_anchor_support": sum(safe(edge.get("c2_component")) == "common_anchor" for edge in edges),
            "bridge_support": len(worker_sets[worker]), "unique_image_coverage": len(base_ids),
            "building_coverage": len(buildings), "common_bridge_with_other_min": min(overlaps, default=0),
            "missing_rate": missing_rate, "structural_failure_rate": structural_rate,
            "effective_information": added_information,
            "expected_fallback_rate": missing_rate ** len(tasks) if tasks else 1.0,
            "expected_global_full_divergence": abs(_float(row, "risk_slope_for_simulation", "risk_slope", default=0.0)) * (max((_float(task, "risk_design_score_A", default=0.0) for task in tasks), default=0.0) - min((_float(task, "risk_design_score_A", default=0.0) for task in tasks), default=0.0)),
            "v1_usable_support": len(tasks) * max(0.0, 1 - missing_rate) * max(0.0, 1 - structural_rate),
        })
    return max(projected, default=math.inf), audits


def _empirical_cluster_bootstrap(
    design_id: str, worker_rows: list[dict[str, str]], assignments: list[dict[str, Any]],
    task_by_id: dict[str, dict[str, str]], graph: dict[str, Any], *, seed: int, draws: int,
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
        "between_worker_slope_sd", "outcome_residual_sd", "worker_intercept_sd",
        "task_sd", "building_sd", "Q_GT_baseline_se",
    )
    if any(not math.isfinite(_float(row, field, default=math.nan)) for row in worker_rows for field in required_variances):
        return {field: "" for field in SIMULATION_FIELDS} | {
            "design_id": design_id, "seed": seed, "draws": draws,
            "variance_fields_used": list(required_variances),
            "simulation_status": "insufficient_variance_parameters",
        }
    rng = random.Random(f"c1-hierarchical-resampling|{seed}|{design_id}")
    edges_by_worker: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for edge in assignments:
        edges_by_worker[safe(edge["worker_id"])].append(edge)
    baseline = {safe(row.get("worker_id")): _float(row, "Q_GT_task_adjusted", default=0.0) for row in worker_rows}
    baseline_rank = sorted(baseline, key=lambda worker: (-baseline[worker], worker))
    baseline_position = {worker: index + 1 for index, worker in enumerate(baseline_rank)}
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
    rank_stable = slope_stable = connected = ordinary = stress = full_building_coverage = 0
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

    def _slope(values: list[tuple[float, float]], default: float, scale: float) -> tuple[float, float]:
        if len(values) < 2:
            return default, math.inf
        mean_x = sum(value[0] for value in values) / len(values)
        mean_y = sum(value[1] for value in values) / len(values)
        denominator = sum((value[0] - mean_x) ** 2 for value in values)
        if denominator <= 0:
            return default, math.inf
        estimate = sum((x - mean_x) * (y - mean_y) for x, y in values) / denominator
        return estimate, 1.96 * max(scale, 1e-9) / math.sqrt(denominator)

    def _variance(field: str) -> float:
        values = [_float(row, field, default=math.nan) for row in worker_rows]
        values = [value for value in values if math.isfinite(value) and value >= 0]
        return sum(values) / len(values) if values else math.nan

    building_sd, task_sd = _variance("building_sd"), _variance("task_sd")
    worker_intercept_sd = _variance("worker_intercept_sd")
    for _ in range(draws):
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
        delivered_edges: list[tuple[str, str]] = []
        delivered_building_instances: set[str] = set()
        delivered_strata: set[str] = set()
        delivered_strata_by_worker: dict[str, set[str]] = defaultdict(set)
        instance_support = Counter({task_instance: 0 for _building_instance, task_instance, _building, _task in task_instances})
        worker_intercepts = {safe(row.get("worker_id")): rng.gauss(0.0, worker_intercept_sd) for row in worker_rows}
        for row in worker_rows:
            worker = safe(row.get("worker_id"))
            slope = _float(row, "risk_slope_for_simulation", "risk_slope", "group_prior_slope", default=0.0)
            slope_scale = _float(row, "between_worker_slope_sd", default=math.inf)
            missing, structural = _float(row, "missing_rate", default=0.0), _float(row, "F_struct", default=0.0)
            residual_scale = _float(row, "outcome_residual_sd", default=math.inf)
            sampled_slope = rng.gauss(slope, slope_scale) if math.isfinite(slope_scale) and slope_scale > 0 else slope
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
                    outcome = baseline.get(worker, 0.0) + worker_intercepts[worker] + sampled_slope * risk + building_effect[building_instance] + task_effect[task_instance] + noise
                    worker_outcomes[worker].append((risk, outcome))
                    delivered_edges.append((worker, task_instance)); instance_support[task_instance] += 1
                    delivered_building_instances.add(building_instance)
                    delivered_strata.add(_task_stratum(task)); delivered_strata_by_worker[worker].add(_task_stratum(task))
        for row in worker_rows:
            worker = safe(row.get("worker_id"))
            slope = _float(row, "risk_slope_for_simulation", "risk_slope", "group_prior_slope", default=0.0)
            scale = _float(row, "outcome_residual_sd", default=math.inf)
            delivered = worker_outcomes.get(worker, [])
            estimate, slope_width = _slope(delivered, slope, scale)
            q_se = _float(row, "Q_GT_baseline_se", default=math.inf)
            if math.isfinite(q_se):
                q_widths.append(1.96 * max(q_se, 1e-9) / math.sqrt(max(1, len(delivered))))
            draw_slope_widths.append(slope_width)
            signs.append((slope == 0) or (estimate == 0) or (slope * estimate > 0))
            rank_score[worker] = sum(value[1] for value in delivered) / len(delivered) if delivered else baseline.get(worker, 0.0)
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
        "graph_connectivity_probability": connected / draws, "building_coverage": min(delivered_building_counts, default=0), "building_coverage_probability": full_building_coverage / draws,
        "ordinary_coverage_probability": ordinary / draws, "stress_coverage_probability": stress / draws,
        "ordinary_coverage_probability_per_worker": ordinary_per_worker / draws,
        "stress_coverage_probability_per_worker": stress_per_worker / draws,
        "expected_assignment_count": sum(delivered_counts) / len(delivered_counts) if delivered_counts else 0,
        "sampled_task_edge_identity_violations": sampled_task_edge_identity_violations,
        "variance_fields_used": list(required_variances),
        "simulation_method": "hierarchical_building_task_resampling_with_c1_group_prior", "simulation_status": "estimated",
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
    if not closeout.get("C1_MEASUREMENT_FROZEN"):
        return False, "c1_measurement_not_frozen"
    if not closeout.get("C2B_DESIGN_READY"):
        return False, "c2b_design_inputs_not_ready"
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
    formal_thresholds_ready = _thresholds_allow_formal_selection(threshold_payload)
    designs = manifest.get("candidate_designs")
    design_ids = [safe(row.get("design_id")) for row in designs or []]
    if not designs or not all(design_ids) or len(design_ids) != len(set(design_ids)):
        raise ValueError("candidate_designs require unique non-empty design_id values")
    dependency_valid, dependency_reason = _dependencies_valid(
        manifest, worker_profile_csv, task_pool_csv, c1_closeout_summary, risk_summary
    )
    if safe(manifest.get("threshold_manifest_sha256")) != threshold_sha:
        dependency_valid, dependency_reason = False, "stale_or_unbound:threshold_manifest"
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
    worker_projections: list[dict[str, Any]] = []
    simulation_rows: list[dict[str, Any]] = []
    task_selection_rows: list[dict[str, Any]] = []
    simulation = manifest.get("simulation") or {}
    simulation_seed = int(simulation.get("seed", 0))
    simulation_draws = int(simulation.get("draws", 1000))

    for raw in designs:
        design_id = safe(raw.get("design_id"))
        common_n = _int(raw, "common_anchor_count")
        bridge_per_worker = _int(raw, "bridge_per_worker")
        unique_bridge_n = _int(raw, "unique_bridge_tasks")
        min_support = _int(raw, "min_task_support", default=1)
        max_imbalance = _int(raw, "max_worker_stratum_imbalance", default=1)
        if min(common_n, bridge_per_worker, unique_bridge_n, min_support) < 1 or max_imbalance < 0:
            raise ValueError(f"invalid positive design counts: {design_id}")
        if min_support < int(risk_contract["simulation"]["minimum_task_support"]):
            raise ValueError(f"C2-B min_task_support is below frozen contract: {design_id}")
        selected_anchors = _select_anchors(anchors, common_n)
        anchor_ids = {_task_id(task) for task in selected_anchors}
        selected_bridges = _select_bridges([task for task in bridges if _task_id(task) not in anchor_ids], unique_bridge_n, selected_anchors)
        anchor_center = {index: sum(_risk_vector(task)[index] for task in selected_anchors) / len(selected_anchors) for index in range(4)} if selected_anchors else {}
        prior = []
        for step, task in enumerate(selected_anchors, 1):
            task_selection_rows.append({
                "design_id": design_id, "selection_step": step, "task_id": _task_id(task), "base_task_id": safe(task.get("base_task_id")) or _task_id(task), "selection_role": "common_anchor",
                "risk_design_vector_A": task.get("risk_design_vector_A", ""), "risk_design_score_A": task.get("risk_design_score_A", ""), "risk_design_stratum": _task_stratum(task),
                "selection_distance": sum((_risk_vector(task)[index] - anchor_center[index]) ** 2 for index in anchor_center) ** .5 if anchor_center else "",
                "building_gain": safe(task.get("building_id")) not in {safe(item.get("building_id")) for item in prior}, "legacy_curated_priority_used": truthy(task.get("legacy_human_curated_candidate")), "selection_reason": "risk_center_scope_reference_feature_gate",
            })
            prior.append(task)
        for step, task in enumerate(selected_bridges, 1):
            reference = [*selected_anchors, *selected_bridges[:step - 1]]
            task_selection_rows.append({
                "design_id": design_id, "selection_step": step, "task_id": _task_id(task), "base_task_id": safe(task.get("base_task_id")) or _task_id(task), "selection_role": "diverse_bridge",
                "risk_design_vector_A": task.get("risk_design_vector_A", ""), "risk_design_score_A": task.get("risk_design_score_A", ""), "risk_design_stratum": _task_stratum(task),
                "selection_distance": min((_risk_distance(task, item) for item in reference), default=""),
                "building_gain": safe(task.get("building_id")) not in {safe(item.get("building_id")) for item in reference}, "legacy_curated_priority_used": truthy(task.get("legacy_human_curated_candidate")), "selection_reason": "continuous_risk_maximin_building_gain",
            })
        bridge_edges = _assign_bridges(workers, selected_bridges, bridge_per_worker, min_support)
        rows: list[dict[str, Any]] = []
        reason = dependency_reason
        if not workers:
            reason = reason or "no_eligible_workers"
        elif len(selected_anchors) != common_n:
            reason = reason or "insufficient_common_anchor_tasks"
        elif len(selected_bridges) != unique_bridge_n:
            reason = reason or "insufficient_diverse_bridge_tasks"
        elif bridge_edges is None:
            reason = reason or "bridge_support_or_worker_capacity_infeasible"
        if not reason:
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
                        "selection_role": "common_anchor", "selection_reason": "risk_center_and_stratum_building_coverage", "maximin_distance_at_selection": "", "building_gain": "", "legacy_curated_priority_used": truthy(task.get("legacy_human_curated_candidate")),
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
                    "selection_role": "diverse_bridge", "selection_reason": "deterministic_risk_space_maximin", "maximin_distance_at_selection": "recorded_by_frozen_selection_order", "building_gain": bool(task.get("building_id")), "legacy_curated_priority_used": truthy(task.get("legacy_human_curated_candidate")),
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
        )
        simulation_rows.append(simulation_row)
        target_raw = risk_contract["simulation"].get("max_q_gt_ci_half_width")
        target = float(target_raw) if target_raw not in {None, ""} else math.inf
        simulated_half_width = _float(simulation_row, "max_ci_half_width", default=projected)
        if not reason and simulation_row.get("simulation_status") != "estimated":
            reason = f"simulation_{simulation_row.get('simulation_status') or 'not_estimable'}"
        if not reason and (projected > target or simulated_half_width > target):
            reason = "projected_ci_half_width_above_target"
        if not reason and not graph["worker_task_graph_connected"]:
            reason = "worker_task_graph_disconnected"
        if not reason and graph["max_worker_stratum_imbalance"] > max_imbalance:
            reason = "worker_stratum_imbalance"
        threshold_failures = _threshold_failures(simulation_row, graph, threshold_payload)
        if not reason and threshold_failures:
            reason = "threshold_gate_failed:" + ";".join(threshold_failures)
        audit = {
            "design_id": design_id, "common_anchor_count": common_n,
            "bridge_per_worker": bridge_per_worker, "unique_bridge_tasks": unique_bridge_n,
            "min_task_support": min_support, "n_assignments": len(rows),
            "projected_max_ci_half_width": "" if not math.isfinite(simulated_half_width) else simulated_half_width,
            "worker_task_graph_connected": graph["worker_task_graph_connected"],
            "stratum_balance_valid": graph["max_worker_stratum_imbalance"] <= max_imbalance,
            "design_method": "c1_risk_slope_precision_projection_candidate",
            "feasible": not reason, "non_dominated": False, "failure_reason": reason,
        }
        audits.append(audit)
        if not reason:
            candidates.append((len(rows), design_id, rows, graph, simulation_row))

    candidates.sort(key=lambda item: (item[0], item[1]))
    costs = ("q_gt_max_ci_half_width", "risk_slope_max_ci_half_width")
    benefits = ("rank_stability", "graph_connectivity_probability", "building_coverage", "ordinary_coverage_probability", "stress_coverage_probability")

    def dominates(left: tuple, right: tuple) -> bool:
        left_values = [float(left[0]), *(_float(left[4], field) for field in costs), *(-_float(left[4], field, default=-math.inf) for field in benefits)]
        right_values = [float(right[0]), *(_float(right[4], field) for field in costs), *(-_float(right[4], field, default=-math.inf) for field in benefits)]
        return all(a <= b for a, b in zip(left_values, right_values)) and any(a < b for a, b in zip(left_values, right_values))

    non_dominated = [candidate for candidate in candidates if not any(dominates(other, candidate) for other in candidates if other is not candidate)]
    non_dominated_ids = {item[1] for item in non_dominated}
    for audit in audits:
        audit["non_dominated"] = audit["design_id"] in non_dominated_ids
    output_dir.mkdir(parents=True, exist_ok=True)
    write_csv(output_dir / "c2b_design_candidates.csv", audits, DESIGN_AUDIT_FIELDS)
    write_csv(output_dir / "c2b_worker_projection_audit.csv", worker_projections, WORKER_PROJECTION_FIELDS)
    write_csv(output_dir / "c2b_task_selection_audit.csv", task_selection_rows, TASK_SELECTION_AUDIT_FIELDS)
    write_csv(output_dir / "c2b_simulation_draw_summary.csv", simulation_rows, SIMULATION_FIELDS)
    write_csv(output_dir / "c2b_loto_lobo_audit.csv", [{"design_id": row["design_id"], "worker_id": row["worker_id"], "loto_support_after_one_task": max(0, int(row["unique_image_coverage"]) - 1), "lobo_support_after_one_building": max(0, int(row["building_coverage"]) - 1)} for row in worker_projections])
    write_csv(output_dir / "c2b_policy_feasibility_audit.csv", audits, DESIGN_AUDIT_FIELDS)
    candidate_edges = [row for _count, _design, rows, _graph, _simulation in candidates for row in rows]
    write_csv(output_dir / "c2b_candidate_worker_task_edges.csv", candidate_edges, ASSIGNMENT_FIELDS)
    write_csv(output_dir / "c2b_worker_task_graph_audit.csv", [item[3] for item in candidates], GRAPH_AUDIT_FIELDS)
    summary = {
        "design_manifest": str(design_manifest),
        "design_manifest_sha256": manifest_sha,
        "threshold_manifest_sha256": threshold_sha,
        "input_sha256": {
            "worker_profile_csv": sha256_file(worker_profile_csv),
            "task_pool_csv": sha256_file(task_pool_csv),
            "c1_closeout_summary": sha256_file(c1_closeout_summary),
            "risk_summary": sha256_file(risk_summary),
            "eligibility_evidence_csv": sha256_file(eligibility_evidence_csv),
        },
        "dependency_binding_valid": dependency_valid,
        "chosen_design_id": "",
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
    if not c1.get("C1_MEASUREMENT_FROZEN") or not c1.get("C2B_DESIGN_READY"):
        raise ValueError("C1 measurement or C2-B design inputs are not formally frozen")
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
            "C1_MEASUREMENT_FROZEN": True,
            "C2B_RISK_DESIGN_FROZEN": True,
            "C2B_DESIGN_FROZEN": True,
            "C2B_ASSIGNMENT_MATERIALIZED": True,
            "C2B_LAUNCH_READY": True,
        },
    }
    write_json(output_dir / "c2b_design.summary.json", summary)
    write_json(output_dir / "c2b_selected_design.json", {"design_id": selected_id, "n_assignments": len(candidate_edges), "formal": True})
    return summary
