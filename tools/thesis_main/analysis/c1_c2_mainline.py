"""Single vFinal C1→C2 materialization contracts.

This module deliberately owns only derived joins, readiness and C2-B worker
input.  It never rewrites canonical annotations, geometry, GT evidence or
structural evidence.
"""

from __future__ import annotations

import csv
import hashlib
import json
import subprocess
from collections import defaultdict
from pathlib import Path
from typing import Any

from tools.thesis_main.analysis.c1_live_collection_monitor import read_csv, write_csv, write_json
from tools.thesis_main.analysis.vfinal_artifact_utils import sha256_file


def _truth(value: Any) -> bool:
    return str(value).strip().lower() in {"1", "true", "yes"}


def _int(value: Any) -> int:
    try:
        return int(float(value or 0))
    except (TypeError, ValueError):
        return 0


def _building(row: dict[str, Any]) -> str:
    return str(row.get("building_id") or row.get("building") or str(row.get("base_task_id", "")).split("_", 1)[0]).strip()


def _join(rows: list[dict[str, str]], eligibility: dict[str, dict[str, str]]) -> list[dict[str, Any]]:
    return [{**row, **eligibility.get(str(row.get("canonical_annotation_id", "")), {})} for row in rows]


def _edge(row: dict[str, str]) -> tuple[str, str, str]:
    """Use a canonical row when present; otherwise retain the worker/task edge."""
    worker, task = str(row.get("worker_id", "")), str(row.get("base_task_id", ""))
    return (str(row.get("canonical_annotation_id", "")) or f"{worker}|{task}", worker, task)


def _connected(edges: set[tuple[str, str, str]]) -> bool:
    if not edges:
        return False
    graph: dict[str, set[str]] = defaultdict(set)
    for _identity, worker, task in edges:
        if not worker or not task:
            continue
        left, right = f"w:{worker}", f"t:{task}"
        graph[left].add(right); graph[right].add(left)
    if not graph:
        return False
    seen, pending = set(), [next(iter(graph))]
    while pending:
        node = pending.pop()
        if node in seen:
            continue
        seen.add(node); pending.extend(graph[node] - seen)
    return len(seen) == len(graph)


def materialize_analysis_views(
    quality_csv: Path, loo_csv: Path, structural_csv: Path, eligibility_csv: Path, output_dir: Path,
) -> dict[str, Any]:
    """Create analysis joins without mutating any upstream evidence artifact."""
    eligibility_rows = read_csv(eligibility_csv)
    eligibility = {row.get("canonical_annotation_id", ""): row for row in eligibility_rows}
    inputs = {
        "quality": quality_csv,
        "loo": loo_csv,
        "structural": structural_csv,
        "eligibility": eligibility_csv,
    }
    outputs = {
        "quality": output_dir / "c1_gt_quality_analysis.csv",
        "loo": output_dir / "geometry_worker_task_loo_analysis.csv",
        "structural": output_dir / "structural_validation_analysis.csv",
    }
    for name, source in (("quality", quality_csv), ("loo", loo_csv), ("structural", structural_csv)):
        rows = _join(read_csv(source), eligibility)
        write_csv(outputs[name], rows, list(rows[0]) if rows else ["canonical_annotation_id"])
    manifest = {
        "schema_version": "paper_a_c1_analysis_views_v1",
        "artifact_owner": "c1_c2_mainline.materialize_analysis_views",
        "join_key": "canonical_annotation_id",
        "inputs": {name: {"path": str(path), "sha256": sha256_file(path)} for name, path in inputs.items()},
        "outputs": {name: {"path": str(path), "sha256": sha256_file(path)} for name, path in outputs.items()},
        "upstream_mutated": False,
    }
    write_json(output_dir / "c1_analysis_views_manifest.json", manifest)
    return {"quality_analysis_csv": str(outputs["quality"]), "loo_analysis_csv": str(outputs["loo"]), "structural_analysis_csv": str(outputs["structural"]), "upstream_mutated": False}


def materialize_measurement_readiness(
    completion_csv: Path, quality_analysis_csv: Path, loo_analysis_csv: Path,
    structural_analysis_csv: Path, output_dir: Path, *, canonical_closed: bool,
    preannotation_feature_ready: bool = False,
) -> dict[str, Any]:
    """Separate canonical closure, C1 measurement freeze and C2-B readiness."""
    completion = {row.get("worker_id", ""): row for row in read_csv(completion_csv)}
    quality = read_csv(quality_analysis_csv)
    loo = read_csv(loo_analysis_csv)
    structural = read_csv(structural_analysis_csv)
    support: dict[str, dict[str, set[str]]] = defaultdict(lambda: {"gt": set(), "loo": set(), "struct": set(), "task": set(), "building": set()})
    task_support: dict[str, dict[str, set[str]]] = defaultdict(lambda: {"gt": set(), "loo": set(), "struct": set(), "workers": set(), "buildings": set()})
    channels = {
        "gt": {edge for row in quality if _truth(row.get("global_analysis_eligible")) for edge in [_edge(row)] if edge[1] and edge[2]},
        "loo": {edge for row in loo if _truth(row.get("loo_analysis_eligible")) for edge in [_edge(row)] if edge[1] and edge[2]},
        "struct": {edge for row in structural if _truth(row.get("structural_opportunity_eligible")) for edge in [_edge(row)] if edge[1] and edge[2]},
    }
    # A measurement edge is usable only when the same canonical annotation (or
    # the same worker/task in legacy fixtures) is evaluable on all three axes.
    three_axis_edges = set.intersection(*channels.values()) if all(channels.values()) else set()
    building_by_edge = {
        _edge(row): _building(row)
        for row in [*quality, *loo, *structural]
        if _edge(row)[1] and _edge(row)[2] and _building(row)
    }
    for _identity, worker, task in three_axis_edges:
        building = building_by_edge.get((_identity, worker, task), "")
        for bucket in ("gt", "loo", "struct"):
            support[worker][bucket].add(task)
            task_support[task][bucket].add(worker)
        support[worker]["task"].add(task); task_support[task]["workers"].add(worker)
        if building:
            support[worker]["building"].add(building); task_support[task]["buildings"].add(building)
    worker_rows: list[dict[str, Any]] = []
    for worker, completion_row in sorted(completion.items()):
        values = support[worker]
        nonstarter = completion_row.get("completion_status") == "nonstarter"
        ready = not nonstarter and all(values[channel] for channel in ("gt", "loo", "struct"))
        worker_rows.append({
            "worker_id": worker, "completion_status": completion_row.get("completion_status", ""),
            "Q_GT_support": len(values["gt"]), "R_LOO_support": len(values["loo"]),
            "F_struct_opportunity_support": len(values["struct"]), "task_coverage": len(values["task"]),
            "building_coverage": len(values["building"]), "measurement_ready": ready,
            "measurement_exclusion_reason": "nonstarter" if nonstarter else "" if ready else "missing_one_or_more_three_axis_support",
        })
    task_rows = []
    for task, values in sorted(task_support.items()):
        ready = all(values[channel] for channel in ("gt", "loo", "struct"))
        task_rows.append({"base_task_id": task, "Q_GT_worker_support": len(values["gt"]), "R_LOO_worker_support": len(values["loo"]), "F_struct_worker_support": len(values["struct"]), "worker_coverage": len(values["workers"]), "building_coverage": len(values["buildings"]), "measurement_ready": ready, "measurement_exclusion_reason": "" if ready else "missing_one_or_more_three_axis_support"})
    buildings: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in task_rows:
        task = row["base_task_id"]
        building = next(iter(task_support[task]["buildings"]), "")
        if building:
            buildings[building].append(row)
    building_rows = [{"building_id": building, "task_coverage": len(rows), "three_axis_ready_task_count": sum(_truth(row["measurement_ready"]) for row in rows), "measurement_ready": any(_truth(row["measurement_ready"]) for row in rows)} for building, rows in sorted(buildings.items())]
    graph_workers = {row["worker_id"] for row in worker_rows if _truth(row["measurement_ready"])}
    graph_tasks = {row["base_task_id"] for row in task_rows if _truth(row["measurement_ready"])}
    graph_connected = _connected(three_axis_edges)
    measurement_frozen = canonical_closed and bool(graph_workers) and bool(graph_tasks) and bool(building_rows) and graph_connected and all(_truth(row["measurement_ready"]) for row in worker_rows if row["completion_status"] != "nonstarter")
    c2b_ready = measurement_frozen and preannotation_feature_ready
    write_csv(output_dir / "c1_measurement_readiness_by_worker.csv", worker_rows)
    write_csv(output_dir / "c1_measurement_readiness_by_task.csv", task_rows)
    write_csv(output_dir / "c1_measurement_readiness_by_building.csv", building_rows)
    manifest = {
        "schema_version": "paper_a_c1_measurement_freeze_v1",
        "C1_CANONICAL_CLOSED": canonical_closed,
        "C1_MEASUREMENT_FROZEN": measurement_frozen,
        "C2B_DESIGN_READY": c2b_ready,
        "routing_profile_frozen": False,
        "preannotation_feature_ready": preannotation_feature_ready,
        "inputs": {name: sha256_file(path) for name, path in {"completion": completion_csv, "quality_analysis": quality_analysis_csv, "loo_analysis": loo_analysis_csv, "structural_analysis": structural_analysis_csv}.items()},
        "worker_task_graph": {"worker_count": len(graph_workers), "task_count": len(graph_tasks), "edge_count": len(three_axis_edges), "connected": graph_connected},
    }
    write_json(output_dir / "c1_measurement_freeze_manifest.json", manifest)
    return manifest


def materialize_c2b_design_worker_profile(
    completion_csv: Path, three_axis_csv: Path, parameter_csv: Path, readiness_csv: Path, output_dir: Path,
) -> dict[str, Any]:
    """Materialize the only worker input consumed by C2-B design/build."""
    completion = {row.get("worker_id", ""): row for row in read_csv(completion_csv)}
    state = {row.get("worker_id", ""): row for row in read_csv(three_axis_csv)}
    parameter = {row.get("worker_id", ""): row for row in read_csv(parameter_csv)}
    readiness = {row.get("worker_id", ""): row for row in read_csv(readiness_csv)}
    rows = []
    for worker in sorted(set(completion) | set(state) | set(parameter) | set(readiness)):
        c, s, p, r = completion.get(worker, {}), state.get(worker, {}), parameter.get(worker, {}), readiness.get(worker, {})
        eligible = _truth(r.get("measurement_ready")) and s.get("worker_state_status") == "estimated" and p.get("parameter_status") == "estimated"
        reasons = []
        if not _truth(r.get("measurement_ready")): reasons.append(r.get("measurement_exclusion_reason") or "measurement_not_frozen")
        if s.get("worker_state_status") != "estimated": reasons.append("three_axis_not_estimated")
        if p.get("parameter_status") != "estimated": reasons.append("risk_slope_not_estimated")
        rows.append({
            "worker_id": worker, "C1_completion_status": c.get("completion_status", ""),
            "Q_GT_task_adjusted": s.get("Q_GT_task_adjusted", ""), "Q_GT_CI_lower": s.get("CI_lower", ""), "Q_GT_CI_upper": s.get("CI_upper", ""), "Q_GT_LCB": s.get("LCB", ""), "Q_GT_support": s.get("GT_support", ""),
            "R_LOO_compatible": s.get("R_LOO_compatible", ""), "R_LOO_CI_lower": s.get("R_LOO_CI_lower", ""), "R_LOO_CI_upper": s.get("R_LOO_CI_upper", ""), "R_LOO_support": s.get("LOO_support", ""),
            "F_struct": s.get("F_struct", ""), "F_struct_numerator": s.get("F_struct_numerator", ""), "F_struct_denominator": s.get("F_struct_denominator", ""),
            "process_support": s.get("process_eligible_support", ""), "independence_support": s.get("independence_support", ""), "scope_reference_support": s.get("scope_reference_support", ""),
            "risk_slope": p.get("risk_slope", ""), "risk_slope_se": p.get("risk_slope_se", ""), "risk_slope_support": p.get("risk_support", ""), "missing_rate": p.get("missing_rate", ""),
            "c2_candidate_eligible": eligible, "exclusion_reason": ";".join(filter(None, reasons)),
        })
    write_csv(output_dir / "c2b_design_worker_profile.csv", rows)
    return {"n_workers": len(rows), "n_eligible": sum(_truth(row["c2_candidate_eligible"]) for row in rows), "worker_profile_sha256": sha256_file(output_dir / "c2b_design_worker_profile.csv")}


def formal_git_state(project_root: Path) -> dict[str, Any]:
    head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=project_root, check=True, capture_output=True, text=True).stdout.strip()
    status = subprocess.run(["git", "status", "--porcelain"], cwd=project_root, check=True, capture_output=True, text=True).stdout
    return {"git_commit_sha": head, "clean": not status.strip(), "porcelain": status}
