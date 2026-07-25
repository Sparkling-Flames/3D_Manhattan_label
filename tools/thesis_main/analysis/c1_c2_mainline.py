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
    return str(row.get("building_id") or "").strip()


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
    collection_window_closed: bool | None = None, eligibility_csv: Path | None = None,
    preannotation_feature_ready: bool = False,
) -> dict[str, Any]:
    """Freeze three estimands separately; C2-B admission is not their intersection."""
    completion = {row.get("worker_id", ""): row for row in read_csv(completion_csv)}
    eligibility = {row.get("canonical_annotation_id", ""): row for row in read_csv(eligibility_csv)} if eligibility_csv and eligibility_csv.exists() else {}
    if collection_window_closed is None:
        collection_window_closed = canonical_closed
    quality = read_csv(quality_analysis_csv)
    loo = read_csv(loo_analysis_csv)
    structural = read_csv(structural_analysis_csv)
    support: dict[str, dict[str, set[str]]] = defaultdict(lambda: {"gt": set(), "loo": set(), "struct": set(), "task": set(), "building": set()})
    task_support: dict[str, dict[str, set[str]]] = defaultdict(lambda: {"gt": set(), "loo": set(), "struct": set(), "workers": set(), "buildings": set()})
    source_rows = {
        "gt": (quality, "global_analysis_eligible", "gt"),
        "loo": (loo, "loo_analysis_eligible", "loo"),
        "structural": (structural, "structural_opportunity_eligible", "struct"),
    }
    channels: dict[str, set[tuple[str, str, str]]] = {}
    axis_graphs: dict[str, dict[str, Any]] = {}
    graph_files = {
        "gt": output_dir / "c1_gt_worker_task_graph.csv",
        "loo": output_dir / "c1_loo_worker_task_graph.csv",
        "structural": output_dir / "c1_structural_worker_task_graph.csv",
    }
    for axis, (rows, gate, support_key) in source_rows.items():
        graph_rows = []
        edges: set[tuple[str, str, str]] = set()
        for row in rows:
            identity_row = eligibility.get(str(row.get("canonical_annotation_id", "")), {})
            if not _truth(identity_row.get(gate, row.get(gate))):
                continue
            identity, worker, task = _edge(row)
            if not worker or not task:
                continue
            building = _building(row)
            edges.add((identity, worker, task))
            graph_rows.append({"axis": axis, "canonical_annotation_id": identity, "worker_id": worker, "base_task_id": task, "building_id": building, "edge_evaluable": True})
            support[worker][support_key].add(task)
            support[worker]["task"].add(task)
            task_support[task][support_key].add(worker)
            task_support[task]["workers"].add(worker)
            if building:
                support[worker]["building"].add(building)
                task_support[task]["buildings"].add(building)
        write_csv(graph_files[axis], graph_rows, ["axis", "canonical_annotation_id", "worker_id", "base_task_id", "building_id", "edge_evaluable"])
        channels[axis] = edges
        axis_graphs[axis] = {
            "edge_count": len(edges),
            "worker_count": len({edge[1] for edge in edges}),
            "task_count": len({edge[2] for edge in edges}),
            "connected": _connected(edges),
            "sha256": sha256_file(graph_files[axis]),
        }
    support_rows = list(eligibility.values()) if eligibility else [row for rows, _gate, _key in source_rows.values() for row in rows]
    process_support_by_worker: dict[str, set[str]] = defaultdict(set)
    independence_support_by_worker: dict[str, set[str]] = defaultdict(set)
    scope_reference_support_by_worker: dict[str, set[str]] = defaultdict(set)
    for row in support_rows:
        worker, task = str(row.get("worker_id", "")), str(row.get("base_task_id", ""))
        if not worker or not task:
            continue
        if _truth(row.get("process_eligible")): process_support_by_worker[worker].add(task)
        if _truth(row.get("independence_eligible")): independence_support_by_worker[worker].add(task)
        if _truth(row.get("scope_reference_eligible")): scope_reference_support_by_worker[worker].add(task)
    worker_rows: list[dict[str, Any]] = []
    for worker, completion_row in sorted(completion.items()):
        values = support[worker]
        completion_status = completion_row.get("completion_status", "")
        nonstarter = completion_status == "nonstarter"
        statuses = {"gt": "estimated" if values["gt"] else "insufficient_support", "loo": "estimated" if values["loo"] else "insufficient_support", "struct": "estimated" if values["struct"] else "insufficient_support"}
        three_axis_complete = not nonstarter and all(status == "estimated" for status in statuses.values())
        completion_valid = _truth(completion_row.get("completion_disposition_valid")) if "completion_disposition_valid" in completion_row else completion_status in {"completed", "partial_noncompletion", "nonstarter"}
        worker_rows.append({
            "worker_id": worker, "completion_status": completion_status, "completion_disposition_valid": completion_valid,
            "Q_GT_support": len(values["gt"]), "R_LOO_support": len(values["loo"]),
            "F_struct_opportunity_support": len(values["struct"]), "task_coverage": len(values["task"]),
            "building_coverage": len(values["building"]), "Q_GT_status": statuses["gt"], "R_LOO_status": statuses["loo"], "F_struct_status": statuses["struct"],
            "process_support": len(process_support_by_worker[worker]) if eligibility else "", "independence_support": len(independence_support_by_worker[worker]) if eligibility else "", "scope_reference_support": len(scope_reference_support_by_worker[worker]) if eligibility else "",
            "three_axis_complete": three_axis_complete, "measurement_ready": three_axis_complete,
            "measurement_exclusion_reason": "nonstarter" if nonstarter else "" if three_axis_complete else "estimand_specific_support_incomplete",
        })
    task_rows = []
    for task, values in sorted(task_support.items()):
        ready = all(values[channel] for channel in ("gt", "loo", "struct"))
        task_rows.append({"base_task_id": task, "Q_GT_worker_support": len(values["gt"]), "R_LOO_worker_support": len(values["loo"]), "F_struct_worker_support": len(values["struct"]), "worker_coverage": len(values["workers"]), "building_coverage": len(values["buildings"]), "measurement_ready": ready, "measurement_exclusion_reason": "" if ready else "estimand_specific_support_incomplete"})
    buildings: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in task_rows:
        task = row["base_task_id"]
        building = next(iter(task_support[task]["buildings"]), "")
        if building:
            buildings[building].append(row)
    building_rows = [{"building_id": building, "task_coverage": len(rows), "three_axis_ready_task_count": sum(_truth(row["measurement_ready"]) for row in rows), "measurement_ready": any(_truth(row["measurement_ready"]) for row in rows)} for building, rows in sorted(buildings.items())]
    estimand_freeze = {
        "Q_GT": bool(canonical_closed and collection_window_closed and axis_graphs["gt"]["edge_count"] and axis_graphs["gt"]["connected"]),
        "R_LOO": bool(canonical_closed and collection_window_closed and axis_graphs["loo"]["edge_count"] and axis_graphs["loo"]["connected"]),
        "F_struct": bool(canonical_closed and collection_window_closed and axis_graphs["structural"]["edge_count"] and axis_graphs["structural"]["connected"]),
    }
    measurement_frozen = bool(canonical_closed and collection_window_closed and all(estimand_freeze.values()))
    c2b_ready = bool(measurement_frozen and preannotation_feature_ready)
    write_csv(output_dir / "c1_measurement_readiness_by_worker.csv", worker_rows)
    write_csv(output_dir / "c1_measurement_readiness_by_task.csv", task_rows)
    write_csv(output_dir / "c1_measurement_readiness_by_building.csv", building_rows)
    manifest = {
        "schema_version": "paper_a_c1_measurement_freeze_v1",
        "C1_CANONICAL_CLOSED": canonical_closed,
        "C1_MEASUREMENT_FROZEN": measurement_frozen,
        "C2B_DESIGN_READY": c2b_ready,
        "C2B_RISK_DESIGN_FROZEN": False,
        "C2B_DESIGN_FROZEN": False,
        "C2B_ASSIGNMENT_MATERIALIZED": False,
        "C2B_LAUNCH_READY": False,
        "routing_profile_frozen": False,
        "preannotation_feature_ready": preannotation_feature_ready,
        "collection_window_closed": bool(collection_window_closed),
        "estimand_freeze": estimand_freeze,
        "C1_COLLECTION_INCOMPLETE": not bool(collection_window_closed),
        "inputs": {name: sha256_file(path) for name, path in {"completion": completion_csv, "quality_analysis": quality_analysis_csv, "loo_analysis": loo_analysis_csv, "structural_analysis": structural_analysis_csv}.items()},
        "axis_graphs": axis_graphs,
    }
    manifest["state_machine"] = {
        name: bool(manifest[name])
        for name in (
            "C1_COLLECTION_INCOMPLETE", "C1_CANONICAL_CLOSED", "C1_MEASUREMENT_FROZEN",
            "C2B_RISK_DESIGN_FROZEN", "C2B_DESIGN_FROZEN",
            "C2B_ASSIGNMENT_MATERIALIZED", "C2B_LAUNCH_READY",
        )
    }
    write_json(output_dir / "c1_measurement_freeze_manifest.json", manifest)
    return manifest


def materialize_c2b_design_worker_profile(
    completion_csv: Path, three_axis_csv: Path, parameter_csv: Path, readiness_csv: Path, output_dir: Path,
) -> dict[str, Any]:
    """Materialize the only worker input consumed by C2-B design/build.

    Admission deliberately uses the baseline Q_GT/process/independence evidence
    only.  LOO, structural opportunities and individual slope precision remain
    estimand-specific diagnostics for later confirmation, not a circular C2-B
    prerequisite.
    """
    completion = {row.get("worker_id", ""): row for row in read_csv(completion_csv)}
    state = {row.get("worker_id", ""): row for row in read_csv(three_axis_csv)}
    parameter = {row.get("worker_id", ""): row for row in read_csv(parameter_csv)}
    readiness = {row.get("worker_id", ""): row for row in read_csv(readiness_csv)}
    rows = []
    for worker in sorted(set(completion) | set(state) | set(parameter) | set(readiness)):
        c, s, p, r = completion.get(worker, {}), state.get(worker, {}), parameter.get(worker, {}), readiness.get(worker, {})
        completion_status = c.get("completion_status", "")
        completion_valid = _truth(c.get("completion_disposition_valid")) if "completion_disposition_valid" in c else completion_status in {"completed", "partial_noncompletion", "nonstarter"}
        q_support = _int(r.get("Q_GT_support"))
        process_support = _int(r.get("process_support")) if str(r.get("process_support", "")).strip() else _int(s.get("process_eligible_support"))
        independence_support = _int(r.get("independence_support")) if str(r.get("independence_support", "")).strip() else _int(s.get("independence_support"))
        administrative = _truth(c.get("administrative_exclusion")) or completion_status == "administrative_exclusion"
        eligible = completion_status not in {"nonstarter", "closed_partial_insufficient"} and completion_valid and not administrative and q_support > 0 and process_support > 0 and independence_support > 0
        reasons = []
        if completion_status == "nonstarter": reasons.append("nonstarter")
        if completion_status == "closed_partial_insufficient": reasons.append("closed_partial_support_insufficient")
        if not completion_valid: reasons.append("completion_disposition_not_valid")
        if administrative: reasons.append("administrative_or_safety_exclusion")
        if not q_support: reasons.append("missing_q_gt_baseline_support")
        if not process_support: reasons.append("missing_process_support")
        if not independence_support: reasons.append("missing_independence_support")
        slope_status = p.get("c1_risk_slope_status") or ("estimated_from_C1" if p.get("parameter_status") == "estimated" else "not_evaluable_but_C2B_eligible" if eligible else "group_prior_only")
        rows.append({
            "worker_id": worker, "completion_status": completion_status, "C1_completion_status": completion_status,
            "completion_disposition_valid": completion_valid, "c2b_baseline_eligible": eligible,
            "Q_GT_task_adjusted": s.get("Q_GT_task_adjusted", ""), "Q_GT_CI_lower": s.get("CI_lower", ""), "Q_GT_CI_upper": s.get("CI_upper", ""), "Q_GT_LCB": s.get("LCB", ""), "Q_GT_support": q_support,
            "R_LOO_compatible": s.get("R_LOO_compatible", ""), "R_LOO_CI_lower": s.get("R_LOO_CI_lower", ""), "R_LOO_CI_upper": s.get("R_LOO_CI_upper", ""), "R_LOO_support": s.get("LOO_support", r.get("R_LOO_support", "")), "R_LOO_status": r.get("R_LOO_status", "insufficient_support"),
            "F_struct": s.get("F_struct", ""), "F_struct_numerator": s.get("F_struct_numerator", ""), "F_struct_denominator": s.get("F_struct_denominator", ""), "F_struct_status": r.get("F_struct_status", "insufficient_support"),
            "process_support": process_support, "independence_support": independence_support, "scope_reference_support": r.get("scope_reference_support", ""),
            "risk_slope": p.get("risk_slope", ""), "risk_slope_se": p.get("risk_slope_se", ""), "risk_slope_support": p.get("risk_support", ""), "c1_risk_slope_status": slope_status,
            "group_prior_slope": p.get("group_prior_slope", ""), "group_prior_scale": p.get("group_prior_scale", ""), "risk_slope_for_simulation": p.get("risk_slope_for_simulation", p.get("risk_slope", "")), "risk_slope_scale_for_simulation": p.get("risk_slope_scale_for_simulation", p.get("risk_slope_se", "")),
            "group_slope_mean": p.get("group_slope_mean", ""), "between_worker_slope_sd": p.get("between_worker_slope_sd", ""),
            "outcome_residual_sd": p.get("outcome_residual_sd", ""), "worker_intercept_sd": p.get("worker_intercept_sd", ""),
            "task_sd": p.get("task_sd", ""), "building_sd": p.get("building_sd", ""), "Q_GT_baseline_se": p.get("Q_GT_baseline_se", ""),
            "missing_rate": p.get("missing_rate", ""), "c2_candidate_eligible": eligible, "exclusion_reason": ";".join(filter(None, reasons)),
        })
    profile_path = output_dir / "c2b_design_worker_profile.csv"
    roster_path = output_dir / "c2_eligible_roster_C1.csv"
    write_csv(profile_path, rows)
    write_csv(roster_path, [row for row in rows if _truth(row["c2b_baseline_eligible"])])
    graph_source = readiness_csv.parent / "c1_gt_worker_task_graph.csv"
    if graph_source.exists():
        eligible_workers = {row["worker_id"] for row in rows if _truth(row["c2b_baseline_eligible"])}
        graph_rows = [{**row, "c2b_baseline_eligible": True} for row in read_csv(graph_source) if row.get("worker_id") in eligible_workers]
        write_csv(output_dir / "c1_c2b_design_usable_graph.csv", graph_rows, ["axis", "canonical_annotation_id", "worker_id", "base_task_id", "building_id", "edge_evaluable", "c2b_baseline_eligible"])
    return {
        "n_workers": len(rows),
        "n_eligible": sum(_truth(row["c2_candidate_eligible"]) for row in rows),
        "worker_profile_sha256": sha256_file(profile_path),
        "eligible_roster_sha256": sha256_file(roster_path),
    }


def formal_git_state(project_root: Path) -> dict[str, Any]:
    head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=project_root, check=True, capture_output=True, text=True).stdout.strip()
    status = subprocess.run(["git", "status", "--porcelain"], cwd=project_root, check=True, capture_output=True, text=True).stdout
    return {"git_commit_sha": head, "clean": not status.strip(), "porcelain": status}
