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
from tools.thesis_main.analysis.worker_identity import normalize_worker_id


def _truth(value: Any) -> bool:
    return str(value).strip().lower() in {"1", "true", "yes"}


def _int(value: Any) -> int:
    try:
        return int(float(value or 0))
    except (TypeError, ValueError):
        return 0


def _building(row: dict[str, Any]) -> str:
    return str(row.get("building_id") or "").strip()


def _normalize_worker_rows(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    return [{**row, "worker_id": normalize_worker_id(row.get("worker_id", ""))} for row in rows]


def _worker_keyed(rows: list[dict[str, str]]) -> dict[str, dict[str, str]]:
    keyed: dict[str, dict[str, str]] = {}
    for row in _normalize_worker_rows(rows):
        worker = row.get("worker_id", "")
        if worker in keyed:
            raise ValueError(f"duplicate worker identity after normalization:{worker}")
        if worker:
            keyed[worker] = row
    return keyed


def _join(rows: list[dict[str, str]], eligibility: dict[str, dict[str, str]]) -> list[dict[str, Any]]:
    output = []
    for row in rows:
        merged = {**row, **eligibility.get(str(row.get("canonical_annotation_id", "")), {})}
        if row.get("schema_version"):
            merged["schema_version"] = row["schema_version"]
        merged["worker_id"] = normalize_worker_id(merged.get("worker_id", ""))
        output.append(merged)
    return output


def materialize_task_building_binding(
    canonical_csv: Path, building_registry_csv: Path | None, output_dir: Path, *, formal: bool = False,
) -> dict[str, Any]:
    """Bind task identity to an approved building without mutating canonical rows."""
    bases = sorted({row.get("base_task_id", "") for row in read_csv(canonical_csv) if row.get("base_task_id", "")})
    grouped: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in read_csv(building_registry_csv) if building_registry_csv and building_registry_csv.exists() else []:
        grouped[row.get("base_task_id", "")].append(row)
    output, blockers = [], []
    for base in bases:
        candidates = grouped.get(base, [])
        approved = [row for row in candidates if row.get("registry_status", "").lower() == "approved" and all(row.get(field, "") for field in ("building_id", "reviewed_by", "reviewed_at"))]
        building_ids = {row.get("building_id", "") for row in approved}
        status = "approved" if len(approved) == 1 and len(building_ids) == 1 else "conflict" if len(building_ids) > 1 or len(approved) > 1 else "missing"
        if status != "approved": blockers.append(f"building_binding_{status}:{base}")
        output.append({
            "base_task_id": base, "building_id": next(iter(building_ids), ""), "binding_status": status,
            "registry_status": approved[0].get("registry_status", "") if len(approved) == 1 else "",
            "reviewed_by": approved[0].get("reviewed_by", "") if len(approved) == 1 else "",
            "reviewed_at": approved[0].get("reviewed_at", "") if len(approved) == 1 else "",
            "building_registry_sha256": sha256_file(building_registry_csv) if building_registry_csv and building_registry_csv.exists() else "",
        })
    if formal and blockers:
        raise ValueError("formal C1 building registry incomplete:" + ";".join(blockers[:5]))
    path = output_dir / "c1_task_building_binding.csv"
    write_csv(path, output, list(output[0]) if output else ["base_task_id", "building_id", "binding_status"])
    return {"status": "validated" if not blockers else "not_evaluable", "n_tasks": len(output), "n_approved": len(output) - len(blockers), "blockers": blockers, "registry_sha256": sha256_file(building_registry_csv) if building_registry_csv and building_registry_csv.exists() else "", "output_sha256": sha256_file(path)}


def _edge(row: dict[str, str]) -> tuple[str, str, str]:
    """Use a canonical row when present; otherwise retain the worker/task edge."""
    worker, task = normalize_worker_id(row.get("worker_id", "")), str(row.get("base_task_id", ""))
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
    *, peer_csv: Path | None = None, building_binding_csv: Path | None = None,
) -> dict[str, Any]:
    """Create analysis joins without mutating any upstream evidence artifact."""
    eligibility_rows = read_csv(eligibility_csv)
    eligibility = {row.get("canonical_annotation_id", ""): row for row in eligibility_rows}
    buildings = {row.get("base_task_id", ""): row.get("building_id", "") for row in read_csv(building_binding_csv)} if building_binding_csv and building_binding_csv.exists() else {}
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
    if peer_csv is not None:
        inputs["peer"] = peer_csv
        outputs["peer"] = output_dir / "geometry_worker_task_peer_analysis.csv"
    if building_binding_csv is not None:
        inputs["building_binding"] = building_binding_csv
    sources = [("quality", quality_csv), ("loo", loo_csv), ("structural", structural_csv)] + ([("peer", peer_csv)] if peer_csv is not None else [])
    for name, source in sources:
        rows = _join(read_csv(source), eligibility)
        rows = [{**row, "building_id": buildings.get(row.get("base_task_id", ""), row.get("building_id", ""))} for row in rows]
        if name == "peer":
            rows = [row for row in rows if _truth(row.get("peer_analysis_eligible"))]
        if rows:
            fields = list(rows[0])
        else:
            with source.open(encoding="utf-8-sig", newline="") as stream:
                source_fields = list(csv.DictReader(stream).fieldnames or [])
            with eligibility_csv.open(encoding="utf-8-sig", newline="") as stream:
                eligibility_fields = list(csv.DictReader(stream).fieldnames or [])
            fields = list(dict.fromkeys([*source_fields, *eligibility_fields, "building_id"])) or ["canonical_annotation_id"]
        write_csv(outputs[name], rows, fields)
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
    completion_csv: Path, quality_analysis_csv: Path, peer_analysis_csv: Path,
    structural_analysis_csv: Path, output_dir: Path, *, canonical_closed: bool,
    collection_window_closed: bool | None = None, eligibility_csv: Path | None = None,
    worker_profile_csv: Path, loo_analysis_csv: Path | None = None,
    preannotation_feature_ready: bool = False,
) -> dict[str, Any]:
    """Freeze the authoritative Q_GT/R_peer/F_struct axes from worker_profile_v2."""
    completion = _worker_keyed(read_csv(completion_csv))
    profiles = _worker_keyed(read_csv(worker_profile_csv))
    if set(profiles) != set(completion):
        raise ValueError("worker_profile_v2 and completion worker sets differ")
    eligibility = {row.get("canonical_annotation_id", ""): row for row in read_csv(eligibility_csv)} if eligibility_csv and eligibility_csv.exists() else {}
    if collection_window_closed is None:
        collection_window_closed = canonical_closed
    quality = _normalize_worker_rows(read_csv(quality_analysis_csv))
    peer = _normalize_worker_rows(read_csv(peer_analysis_csv))
    loo = _normalize_worker_rows(read_csv(loo_analysis_csv)) if loo_analysis_csv and loo_analysis_csv.exists() else []
    structural = _normalize_worker_rows(read_csv(structural_analysis_csv))
    support: dict[str, dict[str, set[str]]] = defaultdict(lambda: {"gt": set(), "peer": set(), "struct": set(), "task": set(), "building": set()})
    task_support: dict[str, dict[str, set[str]]] = defaultdict(lambda: {"gt": set(), "peer": set(), "struct": set(), "workers": set(), "buildings": set()})
    source_rows = {
        "gt": (quality, "gt_primary_analysis_eligible", "gt"),
        "peer": (peer, "peer_analysis_eligible", "peer"),
        "structural": (structural, "structural_opportunity_eligible", "struct"),
    }
    channels: dict[str, set[tuple[str, str, str]]] = {}
    axis_graphs: dict[str, dict[str, Any]] = {}
    graph_files = {
        "gt": output_dir / "c1_gt_worker_task_graph.csv",
        "peer": output_dir / "c1_peer_worker_task_graph.csv",
        "structural": output_dir / "c1_structural_worker_task_graph.csv",
    }
    for axis, (rows, gate, support_key) in source_rows.items():
        graph_rows = []
        edges: set[tuple[str, str, str]] = set()
        for row in rows:
            identity_row = eligibility.get(str(row.get("canonical_annotation_id", "")), {})
            gate_value = identity_row.get(gate, row.get(gate))
            if axis == "peer" and row.get("schema_version") == "peer_worker_task_v2":
                gate_value = True
            if not _truth(gate_value):
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
        if _truth(row.get("gt_reference_eligible", row.get("scope_reference_eligible"))): scope_reference_support_by_worker[worker].add(task)
    worker_rows: list[dict[str, Any]] = []
    for worker, completion_row in sorted(completion.items()):
        values = support[worker]
        profile = profiles[worker]
        completion_status = completion_row.get("completion_status", "")
        nonstarter = completion_status == "nonstarter"
        statuses = {
            "gt": profile.get("Q_GT_profile_status", "not_evaluable"),
            "peer": profile.get("R_peer_profile_status", "not_evaluable"),
            "struct": profile.get("F_struct_profile_status", "not_evaluable"),
        }
        three_axis_complete = not nonstarter and all(status == "estimated" for status in statuses.values())
        completion_valid = _truth(completion_row.get("completion_disposition_valid")) if "completion_disposition_valid" in completion_row else completion_status in {"completed", "partial_noncompletion", "nonstarter"}
        worker_rows.append({
            "worker_id": worker, "completion_status": completion_status, "completion_disposition_valid": completion_valid,
            "Q_GT_support": len(values["gt"]), "R_peer_support": len(values["peer"]),
            "F_struct_opportunity_support": len(values["struct"]), "task_coverage": len(values["task"]),
            "building_coverage": len(values["building"]), "Q_GT_status": statuses["gt"], "R_peer_status": statuses["peer"], "F_struct_status": statuses["struct"],
            "R_LOO_MEDOID_STATUS": profile.get("LOO_medoid_status", "not_evaluable"),
            "R_LOO_STRICT_STATUS": profile.get("LOO_strict_status", "not_evaluable"),
            "process_support": len(process_support_by_worker[worker]) if eligibility else "", "independence_support": len(independence_support_by_worker[worker]) if eligibility else "", "scope_reference_support": len(scope_reference_support_by_worker[worker]) if eligibility else "",
            "three_axis_complete": three_axis_complete, "measurement_ready": three_axis_complete,
            "measurement_exclusion_reason": "nonstarter" if nonstarter else "" if three_axis_complete else "estimand_specific_support_incomplete",
        })
    task_rows = []
    for task, values in sorted(task_support.items()):
        ready = all(values[channel] for channel in ("gt", "peer", "struct"))
        task_rows.append({"base_task_id": task, "Q_GT_worker_support": len(values["gt"]), "R_peer_worker_support": len(values["peer"]), "F_struct_worker_support": len(values["struct"]), "worker_coverage": len(values["workers"]), "building_coverage": len(values["buildings"]), "measurement_ready": ready, "measurement_exclusion_reason": "" if ready else "estimand_specific_support_incomplete"})
    buildings: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in task_rows:
        task = row["base_task_id"]
        building = next(iter(task_support[task]["buildings"]), "")
        if building:
            buildings[building].append(row)
    building_rows = [{"building_id": building, "task_coverage": len(rows), "three_axis_ready_task_count": sum(_truth(row["measurement_ready"]) for row in rows), "measurement_ready": any(_truth(row["measurement_ready"]) for row in rows)} for building, rows in sorted(buildings.items())]
    estimand_freeze = {
        "Q_GT": bool(canonical_closed and collection_window_closed and axis_graphs["gt"]["edge_count"] and axis_graphs["gt"]["connected"]),
        "R_peer": bool(canonical_closed and collection_window_closed and axis_graphs["peer"]["edge_count"] and axis_graphs["peer"]["connected"]),
        "F_struct": bool(canonical_closed and collection_window_closed and axis_graphs["structural"]["edge_count"] and axis_graphs["structural"]["connected"]),
    }
    terminal = bool(canonical_closed and collection_window_closed)
    estimand_status = {
        name: "frozen" if frozen else "support_limited" if terminal else "pending_collection_close"
        for name, frozen in estimand_freeze.items()
    }
    evidence_bundle_frozen = terminal and all(status in {"frozen", "support_limited"} for status in estimand_status.values())
    baseline_workers = [
        worker for worker in completion
        if support[worker]["gt"]
        and process_support_by_worker[worker]
        and independence_support_by_worker[worker]
        and completion[worker].get("completion_status", "") not in {"nonstarter", "closed_partial_insufficient", "administrative_exclusion"}
    ] if eligibility else [worker for worker in completion if support[worker]["gt"] and completion[worker].get("completion_status", "") not in {"nonstarter", "closed_partial_insufficient", "administrative_exclusion"}]
    c2b_baseline_frozen = bool(terminal and estimand_freeze["Q_GT"] and baseline_workers)
    # Compatibility alias: the C1 evidence bundle is frozen once every axis is
    # terminal.  It does not claim that every estimand was estimable.
    measurement_frozen = evidence_bundle_frozen
    c2b_ready = bool(c2b_baseline_frozen and preannotation_feature_ready)
    write_csv(output_dir / "c1_measurement_readiness_by_worker.csv", worker_rows)
    write_csv(output_dir / "c1_measurement_readiness_by_task.csv", task_rows)
    write_csv(output_dir / "c1_measurement_readiness_by_building.csv", building_rows)
    manifest = {
        "schema_version": "paper_a_c1_measurement_freeze_v1",
        "C1_CANONICAL_CLOSED": canonical_closed,
        "C1_MEASUREMENT_FROZEN": measurement_frozen,
        "C1_EVIDENCE_BUNDLE_FROZEN": evidence_bundle_frozen,
        "C2B_BASELINE_INPUT_FROZEN": c2b_baseline_frozen,
        "Q_GT_FREEZE_STATUS": estimand_status["Q_GT"],
        "R_PEER_FREEZE_STATUS": estimand_status["R_peer"],
        "F_STRUCT_FREEZE_STATUS": estimand_status["F_struct"],
        "R_LOO_MEDOID_STATUS": "frozen" if terminal and any(row.get("LOO_medoid_status") == "estimated" for row in profiles.values()) else "support_limited" if terminal else "pending_collection_close",
        "R_LOO_STRICT_STATUS": "frozen" if terminal and any(row.get("LOO_strict_status") == "estimated" for row in profiles.values()) else "support_limited" if terminal else "pending_collection_close",
        "C2B_DESIGN_READY": c2b_ready,
        "C2B_RISK_DESIGN_FROZEN": False,
        "C2B_DESIGN_FROZEN": False,
        "C2B_ASSIGNMENT_MATERIALIZED": False,
        "C2B_LAUNCH_READY": False,
        "routing_profile_frozen": False,
        "preannotation_feature_ready": preannotation_feature_ready,
        "collection_window_closed": bool(collection_window_closed),
        "estimand_freeze": estimand_freeze,
        "estimand_status": estimand_status,
        "c2b_baseline_worker_count": len(baseline_workers),
        "C1_COLLECTION_INCOMPLETE": not bool(collection_window_closed),
        "inputs": {name: sha256_file(path) for name, path in {"completion": completion_csv, "quality_analysis": quality_analysis_csv, "peer_analysis": peer_analysis_csv, "loo_analysis": loo_analysis_csv, "structural_analysis": structural_analysis_csv, "worker_profile": worker_profile_csv}.items() if path is not None},
        "axis_graphs": axis_graphs,
    }
    manifest["state_machine"] = {
        name: bool(manifest[name])
        for name in (
            "C1_COLLECTION_INCOMPLETE", "C1_CANONICAL_CLOSED", "C1_MEASUREMENT_FROZEN",
            "C1_EVIDENCE_BUNDLE_FROZEN", "C2B_BASELINE_INPUT_FROZEN",
            "C2B_RISK_DESIGN_FROZEN", "C2B_DESIGN_FROZEN",
            "C2B_ASSIGNMENT_MATERIALIZED", "C2B_LAUNCH_READY",
        )
    }
    write_json(output_dir / "c1_measurement_freeze_manifest.json", manifest)
    return manifest


def materialize_c2b_design_worker_profile(
    completion_csv: Path, three_axis_csv: Path, parameter_csv: Path, readiness_csv: Path, output_dir: Path, *, c1_batch_snapshot: Path | None = None,
) -> dict[str, Any]:
    """Materialize the only worker input consumed by C2-B design/build.

    Admission is copied from worker_profile_v2.c2_risk_model_eligible. This
    function may enrich the design table, but it must never re-derive roster
    eligibility from support counts or LOO/timing diagnostics.
    """
    completion = _worker_keyed(read_csv(completion_csv))
    state = _worker_keyed(read_csv(three_axis_csv))
    parameter = _worker_keyed(read_csv(parameter_csv))
    readiness = _worker_keyed(read_csv(readiness_csv))
    rows = []
    for worker in sorted(set(completion) | set(state) | set(parameter) | set(readiness)):
        c, s, p, r = completion.get(worker, {}), state.get(worker, {}), parameter.get(worker, {}), readiness.get(worker, {})
        from tools.thesis_main.analysis.paper_a_contracts import validate_serialized_record
        if not s:
            continue
        s = validate_serialized_record("worker_profile_v2", s)
        completion_status = c.get("completion_status", "")
        completion_valid = _truth(c.get("completion_disposition_valid")) if "completion_disposition_valid" in c else completion_status not in {"nonstarter", "administrative_exclusion"}
        q_support = _int(r.get("Q_GT_support"))
        process_support = _int(s.get("process_eligible_support"))
        independence_support = _int(s.get("independence_support"))
        administrative = not _truth(s.get("administratively_eligible"))
        eligible = _truth(s.get("c2_risk_model_eligible"))
        reasons = []
        if not _truth(s.get("administratively_eligible")): reasons.append("administratively_ineligible")
        if not _truth(s.get("process_eligible")): reasons.append("process_ineligible")
        if not _truth(s.get("independence_eligible")): reasons.append("independence_ineligible")
        if s.get("Q_GT_profile_status") != "estimated": reasons.append("q_gt_not_estimated")
        if s.get("R_peer_profile_status") != "estimated": reasons.append("r_peer_not_estimated")
        if s.get("F_struct_profile_status") != "estimated": reasons.append("f_struct_not_estimated")
        slope_status = p.get("c1_risk_slope_status") or ("estimated_from_C1" if p.get("parameter_status") == "estimated" else "not_evaluable_but_C2B_eligible" if eligible else "group_prior_only")
        rows.append({
            "worker_id": worker, "profile_version": s.get("profile_version", ""), "cohort_id": s.get("cohort_id", ""), "enrollment_batch": s.get("enrollment_batch", ""), "completion_status": completion_status, "C1_completion_status": completion_status,
            "completion_disposition_valid": completion_valid, "c2b_baseline_eligible": eligible,
            "Q_GT_EB": s.get("Q_GT_EB", ""), "Q_GT_EB_LCB": s.get("Q_GT_EB_LCB", ""),
            "Q_GT_task_adjusted_FE": s.get("Q_GT_task_adjusted_FE", s.get("Q_GT_task_adjusted", "")),
            "Q_GT_task_adjusted": s.get("Q_GT_task_adjusted", ""), "Q_GT_CI_lower": s.get("CI_lower", ""), "Q_GT_CI_upper": s.get("CI_upper", ""), "Q_GT_LCB": s.get("LCB", ""), "Q_GT_support": q_support,
            "R_peer": s.get("R_peer_all", ""), "R_peer_support": s.get("peer_task_support", ""), "R_peer_status": s.get("R_peer_profile_status", "insufficient_support"),
            "R_LOO_medoid": s.get("R_LOO_medoid", ""), "R_LOO_medoid_status": s.get("LOO_medoid_status", "not_evaluable"), "R_LOO_strict": s.get("R_LOO_strict", ""), "R_LOO_strict_status": s.get("LOO_strict_status", "not_evaluable"), "R_LOO_support": s.get("LOO_support", r.get("R_LOO_support", "")),
            "F_struct": s.get("F_struct", ""), "F_struct_numerator": s.get("F_struct_numerator", ""), "F_struct_denominator": s.get("F_struct_denominator", ""), "F_struct_status": r.get("F_struct_status", "insufficient_support"),
            "process_support": process_support, "independence_support": independence_support, "scope_reference_support": r.get("scope_reference_support", ""),
            "risk_slope": p.get("risk_slope", ""), "risk_slope_se": p.get("risk_slope_se", ""), "risk_slope_support": p.get("risk_support", ""), "c1_risk_slope_status": slope_status,
            "group_prior_slope": p.get("group_prior_slope", ""), "group_prior_scale": p.get("group_prior_scale", ""), "risk_slope_for_simulation": p.get("risk_slope_for_simulation", p.get("risk_slope", "")), "risk_slope_scale_for_simulation": p.get("risk_slope_scale_for_simulation", p.get("risk_slope_se", "")),
            "group_slope_mean": p.get("group_slope_mean", ""), "group_slope_se": p.get("group_slope_se", ""),
            "between_worker_slope_sd": p.get("between_worker_slope_sd", ""), "slope_model_form": p.get("slope_model_form", ""),
            "outcome_residual_sd": p.get("outcome_residual_sd", ""), "worker_intercept_sd": p.get("worker_intercept_sd", ""),
            "task_sd": p.get("task_sd", ""), "building_sd": p.get("building_sd", ""), "Q_GT_baseline_se": p.get("Q_GT_baseline_se", ""),
            "Q_GT_contrast_covariance_row_json": s.get("Q_GT_contrast_covariance_row_json", ""),
            "missing_rate": p.get("missing_rate", ""), "c2_candidate_eligible": eligible, "exclusion_reason": ";".join(filter(None, reasons)),
        })
    profile_path = output_dir / "c2b_design_worker_profile.csv"
    roster_path = output_dir / "c2_eligible_roster_C1.csv"
    write_csv(profile_path, rows)
    write_csv(roster_path, [row for row in rows if _truth(row["c2b_baseline_eligible"])])
    from tools.thesis_main.analysis.paper_a_contracts import METHOD_CONTRACT, load_method_contract, sha256_file
    method = load_method_contract()
    roster_manifest = {
        "schema_version": "paper_a_c2b_formal_roster_v1",
        "artifact_role": "FORMAL_C2B_ROSTER",
        "contract_role": "generated_subordinate",
        "method_contract_version": method["contract_version"],
        "method_contract_sha256": sha256_file(METHOD_CONTRACT),
        "worker_profile_sha256": sha256_file(three_axis_csv),
        "design_worker_profile_sha256": sha256_file(profile_path),
        "eligible_roster_sha256": sha256_file(roster_path),
        "c1_batch_snapshot_sha256": sha256_file(c1_batch_snapshot) if c1_batch_snapshot else "",
    }
    write_json(output_dir / "c2_eligible_roster_C1.manifest.json", roster_manifest)
    graph_source = readiness_csv.parent / "c1_gt_worker_task_graph.csv"
    if graph_source.exists():
        eligible_workers = {row["worker_id"] for row in rows if _truth(row["c2b_baseline_eligible"])}
        graph_rows = [{**row, "worker_id": normalize_worker_id(row.get("worker_id", "")), "c2b_baseline_eligible": True} for row in read_csv(graph_source) if normalize_worker_id(row.get("worker_id", "")) in eligible_workers]
        write_csv(output_dir / "c1_c2b_design_usable_graph.csv", graph_rows, ["axis", "canonical_annotation_id", "worker_id", "base_task_id", "building_id", "edge_evaluable", "c2b_baseline_eligible"])
    return {
        "n_workers": len(rows),
        "n_eligible": sum(_truth(row["c2_candidate_eligible"]) for row in rows),
        "worker_profile_sha256": sha256_file(profile_path),
        "eligible_roster_sha256": sha256_file(roster_path),
        "eligible_roster_manifest_sha256": sha256_file(output_dir / "c2_eligible_roster_C1.manifest.json"),
    }


def formal_git_state(project_root: Path) -> dict[str, Any]:
    options = {"cwd": project_root, "check": True, "capture_output": True, "text": True, "encoding": "utf-8", "errors": "replace"}
    head = subprocess.run(["git", "rev-parse", "HEAD"], **options).stdout.strip()
    status = subprocess.run(["git", "status", "--porcelain"], **options).stdout
    return {"git_commit_sha": head, "clean": not status.strip(), "porcelain": status}
