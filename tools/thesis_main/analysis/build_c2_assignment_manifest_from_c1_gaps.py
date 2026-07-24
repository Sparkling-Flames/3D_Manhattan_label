from __future__ import annotations

import argparse
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


ASSIGNMENT_FIELDS = [
    "round_id", "worker_id", "task_id", "base_task_id", "task_stratum",
    "assignment_batch", "c2_component", "design_id", "design_manifest_sha256",
]
DESIGN_AUDIT_FIELDS = [
    "design_id", "common_anchor_count", "bridge_per_worker", "unique_bridge_tasks",
    "min_task_support", "n_assignments", "projected_max_ci_half_width",
    "worker_task_graph_connected", "stratum_balance_valid", "design_method",
    "feasible", "failure_reason",
]
WORKER_PROJECTION_FIELDS = [
    "design_id", "worker_id", "current_interval_half_width", "projected_interval_half_width",
    "ordinary_support", "stress_support", "common_anchor_support", "bridge_support",
    "unique_image_coverage", "building_coverage", "common_bridge_with_other_min",
]
GRAPH_AUDIT_FIELDS = [
    "design_id", "n_workers", "n_tasks", "n_edges", "n_connected_components",
    "worker_task_graph_connected", "duplicate_worker_task_count", "min_bridge_task_support",
    "max_worker_stratum_imbalance",
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
        eligible = safe(row.get("c2_candidate_eligible") or row.get("c2_eligible") or row.get("eligible"))
        blocked = truthy(row.get("process_blocker")) or truthy(row.get("independence_blocker"))
        if worker and not blocked and truthy(eligible):
            out.append(row)
    return sorted(out, key=lambda row: safe(row.get("worker_id")))


def _task_stratum(row: dict[str, str]) -> str:
    return safe(row.get("task_stratum") or row.get("scene_stratum") or row.get("risk_bucket") or row.get("scene_label")) or "unstratified"


def _task_id(row: dict[str, str]) -> str:
    return safe(row.get("task_id"))


def _anchor_pool(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    return sorted(
        [row for row in rows if _task_id(row) and truthy(row.get("anchor_eligible") or row.get("is_common_anchor") or row.get("eligible_for_anchor_candidate"))],
        key=lambda row: (_task_stratum(row), _task_id(row)),
    )


def _bridge_pool(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    return sorted(
        [
            row for row in rows
            if _task_id(row)
            and truthy(row.get("bridge_eligible") or row.get("is_diverse_bridge") or row.get("eligible_for_reserve_candidate"))
            and not truthy(row.get("anchor_eligible") or row.get("is_common_anchor") or row.get("eligible_for_anchor_candidate"))
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
        added_information = sum(_float(task, "risk_information_weight", default=1.0) for task in tasks)
        slope_se = _float(row, "risk_slope_se", default=math.inf)
        slope_support = _int(row, "risk_slope_support", "support", "n_support")
        if math.isfinite(slope_se) and slope_se > 0 and slope_support > 0:
            projected_se = 1.0 / math.sqrt((1.0 / slope_se ** 2) + added_information)
            rng = random.Random(f"{seed}|{worker}|{added_information:.12g}")
            errors = sorted(abs(rng.gauss(0.0, projected_se)) for _ in range(draws))
            value = errors[min(draws - 1, math.ceil(0.95 * draws) - 1)]
            current = 1.96 * slope_se
        elif require_c1_slopes:
            value, current = math.inf, ""
        else:
            support = _int(row, "support", "n_calib_completed", "n_support")
            half_width = _float(row, "ci_half_width", "r_u_h")
            if not math.isfinite(half_width):
                # Candidate-only rehearsal uses a conservative Bernoulli bound;
                # formal design still requires the frozen C1 slope estimator.
                half_width = 1.96 * 0.5 / math.sqrt(max(support, 1))
            value = half_width * math.sqrt(max(support, 1) / (max(support, 1) + len(tasks)))
            current = half_width
        projected.append(value)
        strata = Counter(_task_stratum(task) for task in tasks)
        base_ids = {safe(task.get("base_task_id")) or _task_id(task) for task in tasks}
        buildings = {safe(task.get("building_id") or task.get("building")) for task in tasks} - {""}
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
        })
    return max(projected, default=math.inf), audits


def _dependencies_valid(
    manifest: dict[str, Any],
    worker_profile_csv: Path,
    task_pool_csv: Path,
    c1_closeout_summary: Path | None,
    input_status: str,
) -> tuple[bool, str]:
    expected = manifest.get("input_sha256") or {}
    actual = {
        "worker_profile_csv": sha256_file(worker_profile_csv),
        "task_pool_csv": sha256_file(task_pool_csv),
    }
    for key, value in actual.items():
        if expected.get(key) != value:
            return False, f"stale_or_unbound:{key}"
    if input_status != "formal":
        return True, ""
    if not c1_closeout_summary or not c1_closeout_summary.exists():
        return False, "formal_c1_closeout_missing"
    closeout = json.loads(c1_closeout_summary.read_text(encoding="utf-8"))
    if not closeout.get("formal_closeout_ready") or closeout.get("profile_freeze_status") != "C1_frozen":
        return False, "formal_c1_closeout_not_frozen"
    if expected.get("c1_closeout_summary") != sha256_file(c1_closeout_summary):
        return False, "stale_or_unbound:c1_closeout_summary"
    return True, ""


def materialize(
    task_pool_csv: Path,
    worker_profile_csv: Path,
    design_manifest: Path,
    output_dir: Path,
    *,
    input_status: str = "dry_run",
    c1_closeout_summary: Path | None = None,
) -> dict[str, Any]:
    manifest = json.loads(design_manifest.read_text(encoding="utf-8"))
    if manifest.get("manifest_version") != "c2_design_v1":
        raise ValueError("unsupported C2 design manifest version")
    manifest_sha = sha256_file(design_manifest)
    designs = manifest.get("candidate_designs")
    design_ids = [safe(row.get("design_id")) for row in designs or []]
    if not designs or not all(design_ids) or len(design_ids) != len(set(design_ids)):
        raise ValueError("candidate_designs require unique non-empty design_id values")
    dependency_valid, dependency_reason = _dependencies_valid(
        manifest, worker_profile_csv, task_pool_csv, c1_closeout_summary, input_status
    )
    workers_rows = _eligible_workers(read_csv(worker_profile_csv))
    workers = [safe(row["worker_id"]) for row in workers_rows]
    pool = read_csv(task_pool_csv)
    anchors, bridges = _anchor_pool(pool), _bridge_pool(pool)
    audits: list[dict[str, Any]] = []
    candidates: list[tuple[int, str, list[dict[str, Any]], dict[str, Any]]] = []
    worker_projections: list[dict[str, Any]] = []
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
        selected_anchors = _balanced_tasks(anchors, common_n)
        selected_bridges = _balanced_tasks(bridges, unique_bridge_n)
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
                        "task_stratum": _task_stratum(task), "assignment_batch": "C2-B",
                        "c2_component": "common_anchor", "design_id": design_id,
                        "design_manifest_sha256": manifest_sha,
                    })
            for worker, task in bridge_edges or []:
                rows.append({
                    "round_id": "C2-B", "worker_id": worker, "task_id": _task_id(task),
                    "base_task_id": safe(task.get("base_task_id")) or _task_id(task),
                    "task_stratum": _task_stratum(task), "assignment_batch": "C2-B",
                    "c2_component": "diverse_bridge", "design_id": design_id,
                    "design_manifest_sha256": manifest_sha,
                })
        graph = _graph_audit(design_id, workers, rows, {_task_id(task) for task in selected_bridges})
        projected, projection_rows = _projected_worker_intervals(
            workers_rows,
            rows,
            {_task_id(task): task for task in [*selected_anchors, *selected_bridges]},
            seed=simulation_seed,
            draws=simulation_draws,
            require_c1_slopes=input_status == "formal",
        )
        worker_projections.extend(projection_rows)
        target = float(manifest.get("c2b_target_ci_half_width", math.inf))
        if not reason and projected > target:
            reason = "projected_ci_half_width_above_target"
        if not reason and not graph["worker_task_graph_connected"]:
            reason = "worker_task_graph_disconnected"
        if not reason and graph["max_worker_stratum_imbalance"] > max_imbalance:
            reason = "worker_stratum_imbalance"
        audit = {
            "design_id": design_id, "common_anchor_count": common_n,
            "bridge_per_worker": bridge_per_worker, "unique_bridge_tasks": unique_bridge_n,
            "min_task_support": min_support, "n_assignments": len(rows),
            "projected_max_ci_half_width": "" if not math.isfinite(projected) else projected,
            "worker_task_graph_connected": graph["worker_task_graph_connected"],
            "stratum_balance_valid": graph["max_worker_stratum_imbalance"] <= max_imbalance,
            "design_method": "c1_risk_slope_precision_projection" if input_status == "formal" else "candidate_projection_or_dryrun_fallback",
            "feasible": not reason, "failure_reason": reason,
        }
        audits.append(audit)
        if not reason:
            candidates.append((len(rows), design_id, rows, graph))

    candidates.sort(key=lambda item: (item[0], item[1]))
    chosen = candidates[0] if candidates else None
    chosen_rows = chosen[2] if chosen else []
    chosen_graph = chosen[3] if chosen else {
        "design_id": "", "n_workers": len(workers), "n_tasks": 0, "n_edges": 0,
        "n_connected_components": 0, "worker_task_graph_connected": False,
        "duplicate_worker_task_count": 0, "min_bridge_task_support": 0,
        "max_worker_stratum_imbalance": 0,
    }
    output_dir.mkdir(parents=True, exist_ok=True)
    write_csv(output_dir / "c2b_design_candidates.csv", audits, DESIGN_AUDIT_FIELDS)
    write_csv(output_dir / "c2b_worker_projection_audit.csv", worker_projections, WORKER_PROJECTION_FIELDS)
    if input_status == "precloseout_rehearsal":
        candidate_edges = [row for _count, _design, rows, _graph in candidates for row in rows]
        write_csv(output_dir / "c2b_candidate_worker_task_edges.csv", candidate_edges, ASSIGNMENT_FIELDS)
        write_csv(output_dir / "c2b_worker_task_graph_audit.csv", [item[3] for item in candidates], GRAPH_AUDIT_FIELDS)
        chosen = None
        chosen_rows = []
    else:
        write_csv(output_dir / "assignment_manifest_C2B.csv", chosen_rows, ASSIGNMENT_FIELDS)
        write_csv(output_dir / "c2b_worker_task_graph_audit.csv", [chosen_graph], GRAPH_AUDIT_FIELDS)
    summary = {
        "design_manifest": str(design_manifest),
        "design_manifest_sha256": manifest_sha,
        "input_sha256": {
            "worker_profile_csv": sha256_file(worker_profile_csv),
            "task_pool_csv": sha256_file(task_pool_csv),
            **({"c1_closeout_summary": sha256_file(c1_closeout_summary)} if c1_closeout_summary and c1_closeout_summary.exists() else {}),
        },
        "dependency_binding_valid": dependency_valid,
        "chosen_design_id": chosen[1] if chosen else "",
        "n_assignments": len(chosen_rows),
        "c2b_design_ready": bool(chosen),
        "candidate_only": input_status != "formal",
        "input_status": input_status,
        "launch_ready": bool(chosen) and input_status == "formal",
        "failure_reason": (
            "precloseout_candidate_only_no_selection"
            if input_status == "precloseout_rehearsal" and candidates
            else "" if chosen else (dependency_reason or "no_feasible_c2b_design")
        ),
        "n_feasible_candidate_designs": len(candidates),
    }
    write_json(output_dir / "c2b_design.summary.json", summary)
    if not chosen and input_status == "formal":
        raise ValueError(summary["failure_reason"])
    return summary


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Select and materialize the frozen C2-B common-anchor/diverse-bridge design.")
    parser.add_argument("--task-pool-csv", type=Path, required=True)
    parser.add_argument("--worker-profile-csv", type=Path, required=True)
    parser.add_argument("--design-manifest", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--input-status", choices=("dry_run", "precloseout_rehearsal", "formal"), default="dry_run")
    parser.add_argument("--c1-closeout-summary", type=Path)
    args = parser.parse_args(argv)
    print(json.dumps(materialize(
        args.task_pool_csv, args.worker_profile_csv, args.design_manifest, args.output_dir,
        input_status=args.input_status, c1_closeout_summary=args.c1_closeout_summary,
    ), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
