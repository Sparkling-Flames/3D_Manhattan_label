"""Bind completed C2-B submissions to the post-C2-B worker profile consumed by C2-A-RP."""

from __future__ import annotations

import argparse
import csv
import json
import math
from collections import Counter
from pathlib import Path
from typing import Any

from tools.thesis_main.analysis.paper_a_contracts import METHOD_CONTRACT, load_method_contract, validate_serialized_record
from tools.thesis_main.analysis.materialize_c1_operational_reference import validate_reference_review_closure
from tools.thesis_main.analysis.vfinal_artifact_utils import sha256_file
from tools.thesis_main.analysis.worker_identity import normalize_worker_id


def _rows(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as stream:
        return list(csv.DictReader(stream))


def _truth(value: Any) -> bool:
    return str(value).strip().lower() in {"true", "1", "yes"}


TERMINAL_STATUSES = {
    "completed",
    "closed_partial_usable",
    "closed_partial_insufficient",
    "nonstarter",
    "administrative_exclusion",
}
NONCOMPLETED_TERMINAL_STATUSES = TERMINAL_STATUSES - {"completed"}
LEGAL_AXIS_STATUSES = {
    "estimated", "estimated_crossed_model", "estimated_from_C1", "weak_descriptive",
    "insufficient_support", "not_evaluable", "not_identifiable", "support_limited",
    "group_prior_available", "group_prior_only", "not_evaluable_but_C2B_eligible",
    "available", "valid", "fallback", "disabled", "unavailable", "pending", "frozen",
}
AXIS_FIELDS = {
    "Q_GT_status": ("Q_GT_status", "Q_GT_profile_status"),
    "R_peer_status": ("R_peer_status", "R_peer_profile_status"),
    "F_struct_status": ("F_struct_status", "F_struct_profile_status"),
    "risk_slope_status": ("risk_slope_status", "c1_risk_slope_status"),
    "conditional_component_status": ("conditional_component_status", "component_status"),
}


def _finite_number(row: dict[str, str], *fields: str) -> bool:
    for field in fields:
        value = str(row.get(field, "")).strip()
        if not value:
            continue
        try:
            if math.isfinite(float(value)):
                return True
        except (TypeError, ValueError):
            pass
    return False


def _first_value(row: dict[str, str], fields: tuple[str, ...]) -> str:
    for field in fields:
        value = str(row.get(field, "")).strip()
        if value:
            return value
    return ""


def _axis_status(row: dict[str, str], axis: str) -> tuple[str, bool]:
    value = _first_value(row, AXIS_FIELDS[axis])
    if value:
        if value not in LEGAL_AXIS_STATUSES:
            raise ValueError(f"post-C2-B profile has invalid {axis}:{value}")
        return value, True
    if axis == "Q_GT_status" and _truth(row.get("Q_GT_estimable")):
        return "estimated", True
    if axis == "Q_GT_status" and _finite_number(row, "Q_GT_EB", "Q_GT_task_adjusted") and _finite_number(row, "Q_GT_support"):
        return "estimated", True
    if axis == "R_peer_status" and _finite_number(row, "R_peer", "R_peer_all") and _finite_number(row, "R_peer_support"):
        return "estimated", True
    if axis == "F_struct_status" and _finite_number(row, "F_struct", "F_struct_EB") and _finite_number(row, "F_struct_denominator"):
        return "estimated", True
    if axis == "risk_slope_status" and _finite_number(row, "risk_slope") and _finite_number(row, "risk_slope_support"):
        return "estimated", True
    return "not_evaluable", False


def _profile_axis_statuses(row: dict[str, str]) -> tuple[dict[str, str], bool]:
    statuses: dict[str, str] = {}
    explicit_or_inferred = False
    for axis in AXIS_FIELDS:
        statuses[axis], present = _axis_status(row, axis)
        explicit_or_inferred = explicit_or_inferred or present
    if not explicit_or_inferred:
        raise ValueError("post-C2-B profile has no legal axis status fields")
    return statuses, explicit_or_inferred


def _profile_terminal_status(row: dict[str, str]) -> str:
    value = _first_value(row, ("terminal_status", "completion_status", "final_completion_disposition"))
    if value and value not in TERMINAL_STATUSES and value not in {"partial_noncompletion", "in_progress", "pending"}:
        raise ValueError(f"post-C2-B profile has invalid terminal status:{value}")
    return value


def _missing_dispositions(path: Path | None) -> tuple[dict[tuple[str, str], dict[str, str]], dict[str, dict[str, str]]]:
    exact: dict[tuple[str, str], dict[str, str]] = {}
    worker_defaults: dict[str, dict[str, str]] = {}
    if path is None:
        return exact, worker_defaults
    for row in _rows(path):
        worker = normalize_worker_id(row.get("worker_id", ""))
        task = str(row.get("task_id", "")).strip()
        status = _first_value(row, ("terminal_status", "completion_status", "final_completion_disposition"))
        reason = _first_value(row, ("missing_reason", "reason", "completion_disposition_reason"))
        if not worker or not status:
            raise ValueError("C2-B missing disposition requires worker_id and terminal status")
        if status not in TERMINAL_STATUSES:
            raise ValueError(f"C2-B missing disposition has invalid terminal status:{status}")
        item = {"terminal_status": status, "missing_reason": reason}
        if task:
            key = (worker, task)
            if key in exact:
                raise ValueError("C2-B duplicate missing disposition")
            exact[key] = item
        else:
            if worker in worker_defaults:
                raise ValueError("C2-B duplicate worker terminal disposition")
            worker_defaults[worker] = item
    return exact, worker_defaults


def _default_missing_reason(status: str) -> str:
    return {
        "closed_partial_usable": "worker_partial_noncompletion",
        "closed_partial_insufficient": "worker_partial_noncompletion",
        "nonstarter": "worker_nonstarter",
        "administrative_exclusion": "administrative_exclusion",
    }.get(status, "")


def materialize(
    submissions_csv: Path,
    post_profile_csv: Path,
    profile_manifest: Path,
    design_summary: Path,
    c1_closeout_summary: Path,
    assignment_csv: Path,
    worker_roster_csv: Path,
    rule_config: Path,
    launch_report: Path,
    runtime_mapping_audit: Path,
    private_assignment_audit: Path,
    output_summary: Path,
    *,
    input_status: str = "formal",
    terminal_disposition_csv: Path | None = None,
    reference_conflict_review_record: Path | None = None,
) -> dict[str, Any]:
    manifest = json.loads(profile_manifest.read_text(encoding="utf-8"))
    method = load_method_contract()
    method_sha = sha256_file(METHOD_CONTRACT)
    if manifest.get("manifest_version") != "c2b_post_profile_v1":
        raise ValueError("unsupported C2-B post-profile manifest")
    design = json.loads(design_summary.read_text(encoding="utf-8"))
    if not design.get("c2b_design_ready") and input_status == "formal":
        raise ValueError("C2-B design was not ready")

    actual = {
        "c2b_submissions_csv": sha256_file(submissions_csv),
        "post_c2b_worker_profile_csv": sha256_file(post_profile_csv),
        "c2b_design_summary": sha256_file(design_summary),
        "c1_a_snapshot": sha256_file(c1_closeout_summary),
        "c2b_assignment_csv": sha256_file(assignment_csv),
        "worker_roster_csv": sha256_file(worker_roster_csv),
        "rule_config": sha256_file(rule_config),
        "c2b_launch_report": sha256_file(launch_report),
        "c2b_runtime_mapping_audit": sha256_file(runtime_mapping_audit),
        "c2b_private_assignment_audit": sha256_file(private_assignment_audit),
    }
    declared = {
        **(manifest.get("input_sha256") or {}),
        **(manifest.get("output_sha256") or {}),
    }
    for name, digest in actual.items():
        if declared.get(name) != digest:
            raise ValueError(f"stale_or_unbound:{name}")

    if input_status != "formal":
        summary = {
            "closeout_version": "c2b_closeout_v2", "c2b_design_ready": bool(design.get("c2b_design_ready")),
            "c2b_closeout_ready": False, "candidate_only": True,
            "post_c2b_worker_profile_sha256": actual["post_c2b_worker_profile_csv"],
            "post_c2b_profile_manifest_sha256": sha256_file(profile_manifest),
        }
        output_summary.parent.mkdir(parents=True, exist_ok=True)
        output_summary.write_text(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        return summary

    snapshot = json.loads(c1_closeout_summary.read_text(encoding="utf-8"))
    if (snapshot.get("schema_version") != "paper_a_c1_batch_analysis_snapshot_v1"
            or snapshot.get("status") != "formal_design_eligible"
            or snapshot.get("C2B_DESIGN_INPUT_FROZEN_FROM_C1_A") is not True):
        raise ValueError("C2-B closeout requires a frozen C1_A batch snapshot")
    if design.get("candidate_only") or not design.get("launch_ready", True):
        raise ValueError("C2-B assignment is not a formal frozen design")
    assignments, submissions, roster, profiles = (_rows(path) for path in (assignment_csv, submissions_csv, worker_roster_csv, post_profile_csv))
    assigned = [(normalize_worker_id(row.get("worker_id", "")), str(row.get("task_id", "")).strip()) for row in assignments]
    submitted = [(normalize_worker_id(row.get("worker_id", "")), str(row.get("task_id", "")).strip()) for row in submissions]
    if not assigned or any(not all(key) for key in assigned) or len(assigned) != len(set(assigned)):
        raise ValueError("C2-B assignment requires unique worker-task rows")
    assigned_set = set(assigned)
    submitted_set = set(submitted)
    if any(key not in assigned_set for key in submitted):
        raise ValueError("C2-B contains unassigned submission")
    if len(submitted) != len(submitted_set):
        raise ValueError("C2-B duplicate/revision disposition is unresolved")
    reference_review = None
    if input_status == "formal" and reference_conflict_review_record is not None:
        affected_base_task_ids = {
            str(row.get("base_task_id") or row.get("task_id") or "").strip()
            for row in assignments
        }
        reference_review = validate_reference_review_closure(
            reference_conflict_review_record,
            affected_base_task_ids=affected_base_task_ids,
            method_contract_sha256=method_sha,
        )
    roster_ids = {normalize_worker_id(row.get("worker_id", "")) for row in roster}
    profile_ids = {normalize_worker_id(row.get("worker_id", "")) for row in profiles}
    assignment_ids = {worker for worker, _task in assigned}
    if (not roster_ids or "" in roster_ids or roster_ids != assignment_ids
            or len(roster_ids) != len(roster) or profile_ids != roster_ids
            or len(profile_ids) != len(profiles)):
        raise ValueError("C2-B worker roster/profile coverage mismatch")
    profile_by_worker = {normalize_worker_id(row.get("worker_id", "")): row for row in profiles}
    profile_versions = {str(row.get("profile_version", "")).strip() for row in profiles if str(row.get("profile_version", "")).strip()}
    profile_cohorts = {str(row.get("cohort_id", "")).strip() for row in profiles if str(row.get("cohort_id", "")).strip()}
    if len(profile_versions) > 1 or len(profile_cohorts) > 1:
        raise ValueError("C2-B worker profiles have conflicting profile identity")
    if manifest.get("profile_version") and profile_versions and manifest.get("profile_version") not in profile_versions:
        raise ValueError("C2-B profile version identity mismatch")
    if manifest.get("cohort_id") and profile_cohorts and manifest.get("cohort_id") not in profile_cohorts:
        raise ValueError("C2-B profile cohort identity mismatch")
    profile_axis_statuses: dict[str, dict[str, str]] = {}
    profile_terminal_statuses: dict[str, str] = {}
    for worker, row in profile_by_worker.items():
        if row.get("schema_version") != "worker_profile_v2":
            raise ValueError("C2-B post-profile requires worker_profile_v2")
        validate_serialized_record("worker_profile_v2", row)
        profile_axis_statuses[worker], _ = _profile_axis_statuses(row)
        profile_terminal_statuses[worker] = _profile_terminal_status(row)
    missing = assigned_set - submitted_set
    exact_dispositions, worker_dispositions = _missing_dispositions(terminal_disposition_csv)
    for key in exact_dispositions:
        if key not in assigned_set:
            raise ValueError("C2-B missing disposition references an unassigned worker-task")
        if key not in missing:
            raise ValueError("C2-B missing disposition references a submitted task")
    if any(worker not in roster_ids for worker in worker_dispositions):
        raise ValueError("C2-B worker terminal disposition references an unknown worker")
    missing_dispositions: dict[tuple[str, str], dict[str, str]] = {}
    for worker, task in sorted(missing):
        disposition = exact_dispositions.get((worker, task)) or worker_dispositions.get(worker)
        if disposition is None:
            profile_status = profile_terminal_statuses.get(worker, "")
            if profile_status in NONCOMPLETED_TERMINAL_STATUSES:
                disposition = {"terminal_status": profile_status, "missing_reason": ""}
        if disposition is None:
            raise ValueError("C2-B missing worker-task has no terminal disposition")
        status = disposition["terminal_status"]
        if status not in NONCOMPLETED_TERMINAL_STATUSES:
            raise ValueError(f"C2-B missing worker-task has invalid terminal disposition:{worker}/{task}")
        reason = disposition.get("missing_reason") or _default_missing_reason(status)
        if not reason:
            raise ValueError(f"C2-B missing worker-task has no reason:{worker}/{task}")
        missing_dispositions[(worker, task)] = {"terminal_status": status, "missing_reason": reason}
    rules = json.loads(rule_config.read_text(encoding="utf-8"))
    min_anchor, min_bridge, min_task = (int(rules.get(name, 1)) for name in ("min_common_anchor_per_worker", "min_bridge_per_worker", "min_task_support"))
    by_worker = {worker: {"common_anchor": 0, "diverse_bridge": 0} for worker in roster_ids}
    task_support: dict[str, int] = {}
    for row in assignments:
        component = row.get("c2_component", "")
        if component not in {"common_anchor", "diverse_bridge"}:
            raise ValueError("C2-B assignment has invalid component")
        by_worker[normalize_worker_id(row.get("worker_id", ""))][component] += 1
        task_support[row["task_id"]] = task_support.get(row["task_id"], 0) + 1
    if any(counts["common_anchor"] < min_anchor or counts["diverse_bridge"] < min_bridge for counts in by_worker.values()):
        raise ValueError("C2-B worker anchor/bridge support is below threshold")
    if min(task_support.values(), default=0) < min_task:
        raise ValueError("C2-B task support is below threshold")

    axis_status_counts = {axis: Counter() for axis in AXIS_FIELDS}
    worker_summaries: list[dict[str, Any]] = []
    for worker in sorted(roster_ids):
        rows = [row for row in assignments if normalize_worker_id(row.get("worker_id", "")) == worker]
        worker_submitted = {
            (worker, str(row.get("task_id", "")).strip()) for row in submissions
            if normalize_worker_id(row.get("worker_id", "")) == worker
        }
        profile = profile_by_worker[worker]
        statuses = profile_axis_statuses[worker]
        for axis, status in statuses.items():
            axis_status_counts[axis][status] += 1
        missing_rows = [row for row in rows if (worker, str(row.get("task_id", "")).strip()) in missing]
        missing_statuses = {missing_dispositions[(worker, str(row.get("task_id", "")).strip())]["terminal_status"] for row in missing_rows}
        profile_terminal = profile_terminal_statuses[worker]
        if missing_rows:
            if profile_terminal in NONCOMPLETED_TERMINAL_STATUSES:
                terminal_status = profile_terminal
            elif len(missing_statuses) == 1:
                terminal_status = next(iter(missing_statuses))
            else:
                raise ValueError(f"C2-B worker has mixed missing terminal statuses without worker disposition:{worker}")
        else:
            terminal_status = profile_terminal or "completed"
        global_field = _first_value(profile, ("global_policy_eligible",))
        if not global_field:
            raise ValueError(f"C2-B post-profile lacks explicit global_policy_eligible:{worker}")
        # Global eligibility is a frozen worker-profile field.  Q_GT status is
        # reported separately and must not be used as a fallback inference.
        global_eligible = _truth(global_field)
        administratively_profile_eligible = terminal_status not in {"nonstarter", "administrative_exclusion"}
        risk_eligible = administratively_profile_eligible and statuses["risk_slope_status"] in {"estimated", "estimated_crossed_model", "estimated_from_C1"}
        component_fallback = administratively_profile_eligible and statuses["conditional_component_status"] not in {"estimated", "available", "valid"}
        fully_evaluable = terminal_status not in {"nonstarter", "administrative_exclusion"} and all(statuses[axis] == "estimated" for axis in ("Q_GT_status", "R_peer_status", "F_struct_status"))
        worker_summaries.append({
            "worker_id": worker,
            "assigned": len(rows), "submitted": len(worker_submitted), "missing": len(missing_rows),
            "assigned_count": len(rows), "submitted_count": len(worker_submitted), "missing_count": len(missing_rows),
            "common_anchor_completed": sum(row.get("c2_component") == "common_anchor" and (worker, str(row.get("task_id", "")).strip()) in submitted_set for row in rows),
            "diverse_bridge_completed": sum(row.get("c2_component") == "diverse_bridge" and (worker, str(row.get("task_id", "")).strip()) in submitted_set for row in rows),
            "ordinary_completed": sum(str(row.get("task_stratum", row.get("risk_bucket", ""))).strip().lower() == "ordinary" and (worker, str(row.get("task_id", "")).strip()) in submitted_set for row in rows),
            "stress_completed": sum(str(row.get("task_stratum", row.get("risk_bucket", ""))).strip().lower() == "stress" and (worker, str(row.get("task_id", "")).strip()) in submitted_set for row in rows),
            "axis_support_status": statuses,
            "Q_GT_status": statuses["Q_GT_status"], "R_peer_status": statuses["R_peer_status"],
            "F_struct_status": statuses["F_struct_status"], "risk_slope_status": statuses["risk_slope_status"],
            "conditional_component_status": statuses["conditional_component_status"],
            "terminal_status": terminal_status,
            "missing_terminal_statuses": sorted(missing_statuses),
            "missing_reasons": sorted({missing_dispositions[(worker, str(row.get("task_id", "")).strip())]["missing_reason"] for row in missing_rows}),
            "fully_evaluable": fully_evaluable,
            "global_eligible": global_eligible,
            "global_policy_eligible": global_eligible,
            "global_eligibility_source": "explicit_worker_profile_field",
            "risk_adjustment_eligible": risk_eligible,
            "component_fallback": component_fallback,
            "risk_adjustment": 0 if not risk_eligible else profile.get("risk_adjustment", ""),
            "conditional_component_adjustment": 0 if component_fallback else profile.get("conditional_component_adjustment", ""),
        })

    batch_ids = {row.get("assignment_batch_id", row.get("assignment_batch", "")) for row in assignments}
    if len(batch_ids) != 1 or not batch_ids <= {"C2B_BATCH_A", "C2B_BATCH_B"}:
        raise ValueError("C2-B closeout requires exactly one assignment batch")
    batch_id = next(iter(batch_ids))
    launch = json.loads(launch_report.read_text(encoding="utf-8"))
    runtime = json.loads(runtime_mapping_audit.read_text(encoding="utf-8"))
    private = json.loads(private_assignment_audit.read_text(encoding="utf-8"))
    if launch.get("schema_version") != "paper_a_c2b_launch_ready_report_v4":
        raise ValueError("C2-B formal closeout requires the multi-deployment launch report")
    if (launch.get("method_contract_version") != method["contract_version"]
            or launch.get("method_contract_sha256") != method_sha):
        raise ValueError("C2-B launch report method contract is stale")
    deployments = launch.get("deployments")
    if not isinstance(deployments, list) or not deployments or "import_sha256" in launch:
        raise ValueError("C2-B launch report must provide per-deployment planned import evidence")
    deployment_manifest_path = Path(str(launch.get("deployment_manifest_path", "")))
    if (not deployment_manifest_path.is_file()
            or sha256_file(deployment_manifest_path) != launch.get("deployment_manifest_sha256")):
        raise ValueError("C2-B deployment manifest is missing or stale")
    deployment_manifest = json.loads(deployment_manifest_path.read_text(encoding="utf-8"))
    if deployment_manifest.get("schema_version") != "c2b_worker_deployment_manifest_v1":
        raise ValueError("C2-B deployment manifest schema is invalid")
    if (deployment_manifest.get("method_contract_version") != method["contract_version"]
            or deployment_manifest.get("method_contract_sha256") != method_sha
            or deployment_manifest.get("assignment_batch_id") != batch_id
            or deployment_manifest.get("assignment_sha256") != actual["c2b_assignment_csv"]):
        raise ValueError("C2-B deployment manifest is stale or bound to another assignment")
    manifest_deployments = {
        str(item.get("deployment_id", "")): item
        for item in deployment_manifest.get("deployments", [])
        if isinstance(item, dict)
    }
    deployment_ids = set()
    for deployment in deployments:
        deployment_id = str(deployment.get("deployment_id", "")).strip()
        planned_path = Path(str(deployment.get("planned_import_path", "")))
        planned_sha = str(deployment.get("planned_import_sha256", "")).strip()
        if (not deployment_id or deployment_id in deployment_ids
                or not str(deployment.get("language_group", "")).strip()
                or not str(deployment.get("server_instance_id", "")).strip()
                or not str(deployment.get("project_id", "")).strip()
                or not planned_path.is_file() or not planned_sha
                or sha256_file(planned_path) != planned_sha):
            raise ValueError("C2-B deployment planned import identity is incomplete or stale")
        manifest_item = manifest_deployments.get(deployment_id)
        if not isinstance(manifest_item, dict) or any(
            str(manifest_item.get(field, "")) != str(deployment.get(field, ""))
            for field in (
                "language_group", "server_instance_id", "project_id", "server_url",
                "method_contract_version", "method_contract_sha256", "assignment_sha256",
                "selected_design_sha", "worker_registry_sha256",
            )
        ):
            raise ValueError("C2-B launch report deployment identity disagrees with the frozen manifest")
        manifest_planned = Path(str(manifest_item.get("planned_import_path", "")))
        if (not manifest_planned.is_file()
                or str(manifest_item.get("planned_import_sha256", "")) != planned_sha
                or sha256_file(manifest_planned) != planned_sha):
            raise ValueError("C2-B deployment manifest planned import is missing or stale")
        if str(manifest_item.get("server_url", "")).strip() != str(deployment.get("server_url", "")).strip():
            raise ValueError("C2-B deployment server URL disagrees with the frozen manifest")
        if str(manifest_item.get("worker_registry_sha256", "")).strip() != str(deployment.get("worker_registry_sha256", "")).strip():
            raise ValueError("C2-B deployment worker registry identity disagrees with the frozen manifest")
        planned_payload = json.loads(planned_path.read_text(encoding="utf-8"))
        planned_rows = planned_payload if isinstance(planned_payload, list) else planned_payload.get("tasks", planned_payload.get("data", []))
        expected_task_ids = {task for _worker, task in assigned}
        if not isinstance(planned_rows, list) or len(planned_rows) != len(expected_task_ids):
            raise ValueError("C2-B planned import task count is not bound to the frozen task pool")
        seen_planned: set[str] = set()
        for item in planned_rows:
            data = item.get("data", {}) if isinstance(item, dict) and isinstance(item.get("data", {}), dict) else {}
            planned_task_id = str(data.get("planned_task_id", "")).strip()
            if (not planned_task_id or planned_task_id in seen_planned or planned_task_id not in expected_task_ids
                    or data.get("deployment_id") != deployment_id
                    or data.get("language_group") != deployment.get("language_group")
                    or data.get("server_instance_id") != deployment.get("server_instance_id")
                    or data.get("project_id") != deployment.get("project_id")
                    or data.get("c2b_batch_id") != batch_id):
                raise ValueError("C2-B planned import identity is incomplete or stale")
            if launch.get("selected_design_sha") and data.get("selected_design_sha") != launch.get("selected_design_sha"):
                raise ValueError("C2-B planned import selected design identity is stale")
            seen_planned.add(planned_task_id)
        if seen_planned != expected_task_ids:
            raise ValueError("C2-B planned import does not cover the frozen task pool")
        deployment_ids.add(deployment_id)
    if deployment_ids != set(manifest_deployments):
        raise ValueError("C2-B launch report does not cover the frozen deployment set")
    if (launch.get("C2B_LAUNCH_READY") is not True or launch.get("assignment_batch_id") != batch_id
            or launch.get("assignment_sha256") != actual["c2b_assignment_csv"]):
        raise ValueError("C2-B launch report is stale or bound to another batch")
    if (runtime.get("schema_version") != "paper_a_c2b_runtime_mapping_audit_v2"
            or runtime.get("method_contract_version") != method["contract_version"]
            or runtime.get("method_contract_sha256") != method_sha
            or runtime.get("formal_ready") is not True or runtime.get("C2B_RUNTIME_BINDING_READY") is not True
            or runtime.get("assignment_batch_id") != batch_id
            or runtime.get("selected_design_sha") != launch.get("selected_design_sha")
            or set(runtime.get("deployment_ids", [])) != deployment_ids
            or runtime.get("deployment_manifest_sha256") != launch.get("deployment_manifest_sha256")
            or int(runtime.get("worker_task_binding_count", -1)) != len(assigned)):
        raise ValueError("C2-B runtime mapping audit is not formally ready for this batch")
    runtime_export_hashes = runtime.get("runtime_export_sha256")
    planned_import_hashes = runtime.get("planned_import_sha256")
    runtime_counts = runtime.get("runtime_task_count_by_deployment")
    if (not isinstance(runtime_export_hashes, dict) or set(runtime_export_hashes) != deployment_ids
            or not isinstance(planned_import_hashes, dict) or set(planned_import_hashes) != deployment_ids
            or not isinstance(runtime_counts, dict) or set(runtime_counts) != deployment_ids
            or sum(int(value) for value in runtime_counts.values()) != int(runtime.get("runtime_task_count", -1))):
        raise ValueError("C2-B runtime mapping audit deployment evidence is incomplete")
    runtime_dependencies = {
        str(item.get("role", "")): item
        for item in runtime.get("dependencies", [])
        if isinstance(item, dict)
    }
    mapping_dependency = runtime_dependencies.get("RUNTIME_MAPPING")
    if (not isinstance(mapping_dependency, dict)
            or mapping_dependency.get("sha256") != runtime.get("runtime_mapping_sha256")
            or not Path(str(mapping_dependency.get("path", ""))).is_file()
            or sha256_file(Path(str(mapping_dependency.get("path", "")))) != runtime.get("runtime_mapping_sha256")):
        raise ValueError("C2-B runtime mapping audit lacks a valid mapping SHA binding")
    for deployment_id in deployment_ids:
        planned_dependency = runtime_dependencies.get(f"PLANNED_IMPORT_{deployment_id}")
        runtime_dependency = runtime_dependencies.get(f"RUNTIME_EXPORT_{deployment_id}")
        if (not isinstance(planned_dependency, dict) or planned_dependency.get("sha256") != planned_import_hashes[deployment_id]
                or not isinstance(runtime_dependency, dict) or runtime_dependency.get("sha256") != runtime_export_hashes[deployment_id]):
            raise ValueError("C2-B runtime mapping audit lacks per-deployment import/export evidence")
        for dependency, declared_sha in ((planned_dependency, planned_import_hashes[deployment_id]), (runtime_dependency, runtime_export_hashes[deployment_id])):
            path = Path(str(dependency.get("path", "")))
            if not path.is_file() or sha256_file(path) != declared_sha:
                raise ValueError("C2-B runtime mapping audit contains a stale deployment file SHA")
    private_dependencies = {
        str(item.get("role", "")): item
        for item in private.get("dependencies", [])
        if isinstance(item, dict)
    }
    private_assignment_dependency = private_dependencies.get("ASSIGNMENT_MANIFEST")
    private_distribution_dependency = private_dependencies.get("WORKER_DISTRIBUTION")
    if (private.get("formal_ready") is not True or private.get("private_assignment_list_audit_passed") is not True
            or private.get("assignment_batch_id") != batch_id
            or private.get("method_contract_version") != method["contract_version"]
            or private.get("method_contract_sha256") != method_sha
            or private.get("assignment_manifest_sha256") != actual["c2b_assignment_csv"]
            or not isinstance(private_assignment_dependency, dict)
            or private_assignment_dependency.get("sha256") != actual["c2b_assignment_csv"]
            or not isinstance(private_distribution_dependency, dict)
            or private_distribution_dependency.get("sha256") != private.get("worker_distribution_sha256")
            or any(
                not Path(str(item.get("path", ""))).is_file()
                or sha256_file(Path(str(item.get("path", "")))) != item.get("sha256")
                for item in (private_assignment_dependency, private_distribution_dependency)
            )):
        raise ValueError("C2-B private assignment audit is not formally ready for this batch")
    runtime_evidence_path = Path(str(runtime.get("runtime_evidence_path", ""))) if runtime.get("runtime_evidence_path") else None
    if launch.get("migration_envelope_path"):
        if runtime_evidence_path is None or not runtime_evidence_path.is_file():
            raise ValueError("C2-B migration runtime evidence is missing")
        runtime_evidence = json.loads(runtime_evidence_path.read_text(encoding="utf-8"))
        if (runtime_evidence.get("schema_version") != "paper_a_c2b_v17_to_v18_runtime_evidence_v1"
                or runtime_evidence.get("formal_ready") is not True
                or runtime_evidence.get("runtime_binding_status") != "bound"
                or runtime_evidence.get("method_contract_sha256") != method_sha
                or runtime_evidence.get("assignment_sha256") != actual["c2b_assignment_csv"]
                or set(runtime_evidence.get("deployment_ids", [])) != deployment_ids
                or runtime_evidence.get("worker_task_binding_count") != len(assigned)):
            raise ValueError("C2-B migration runtime evidence is incomplete or stale")
        if (runtime_evidence.get("launch_report_sha256") != sha256_file(launch_report)
                or runtime_evidence.get("deployment_manifest_sha256") != launch.get("deployment_manifest_sha256")
                or runtime_evidence.get("runtime_mapping_sha256") != runtime.get("runtime_mapping_sha256")
                or runtime_evidence.get("private_assignment_audit_sha256") != sha256_file(private_assignment_audit)):
            raise ValueError("C2-B migration runtime evidence hash chain is inconsistent")
        if runtime_evidence.get("planned_import_sha256") != planned_import_hashes or runtime_evidence.get("runtime_export_sha256") != runtime_export_hashes:
            raise ValueError("C2-B migration runtime evidence per-deployment hashes are inconsistent")
    summary = {
        "schema_version": "c2b_closeout_v2",
        "artifact_role": f"{batch_id}_CLOSEOUT_FROZEN",
        "contract_role": "generated_subordinate",
        "method_contract_version": method["contract_version"],
        "method_contract_sha256": method_sha,
        "profile_version": manifest.get("profile_version", ""),
        "cohort_id": manifest.get("cohort_id", ""),
        "global_policy_eligibility_source": "explicit_worker_profile_v2.global_policy_eligible",
        "deployments": deployments,
        "deployment_manifest_path": str(deployment_manifest_path),
        "deployment_manifest_sha256": launch.get("deployment_manifest_sha256", ""),
        "runtime_evidence_path": str(runtime_evidence_path or ""),
        "runtime_evidence_sha256": sha256_file(runtime_evidence_path) if runtime_evidence_path else "",
        "closeout_version": "c2b_closeout_v2",
        "c2b_design_ready": True,
        "c2b_closeout_ready": True,
        "candidate_only": False,
        "design_manifest_sha256": design.get("design_manifest_sha256"),
        "c2b_design_summary_path": str(design_summary),
        "c2b_design_summary_sha256": actual["c2b_design_summary"],
        "c1_a_snapshot_sha256": actual["c1_a_snapshot"],
        "c2b_assignment_sha256": actual["c2b_assignment_csv"],
        "worker_roster_sha256": actual["worker_roster_csv"],
        "rule_config_sha256": actual["rule_config"],
        "c2b_submissions_path": str(submissions_csv),
        "c2b_submissions_sha256": actual["c2b_submissions_csv"],
        "post_c2b_worker_profile_path": str(post_profile_csv),
        "post_c2b_worker_profile_sha256": actual["post_c2b_worker_profile_csv"],
        "post_c2b_profile_manifest_path": str(profile_manifest),
        "post_c2b_profile_manifest_sha256": sha256_file(profile_manifest),
        "assigned_count": len(assigned),
        "submitted_count": len(submitted),
        "missing_count": len(missing),
        "worker_summaries": worker_summaries,
        "missing_worker_tasks": [
            {"worker_id": worker, "task_id": task, **missing_dispositions[(worker, task)]}
            for worker, task in sorted(missing)
        ],
        "n_workers_fully_evaluable": sum(row["fully_evaluable"] for row in worker_summaries),
        "n_workers_partially_evaluable": sum(not row["fully_evaluable"] and row["terminal_status"] not in {"nonstarter", "administrative_exclusion"} for row in worker_summaries),
        "n_workers_nonstarter": sum(row["terminal_status"] == "nonstarter" for row in worker_summaries),
        "n_workers_administrative_exclusion": sum(row["terminal_status"] == "administrative_exclusion" for row in worker_summaries),
        "n_workers_global_eligible": sum(row["global_eligible"] for row in worker_summaries),
        "n_workers_risk_adjustment_eligible": sum(row["risk_adjustment_eligible"] for row in worker_summaries),
        "n_workers_component_fallback": sum(row["component_fallback"] for row in worker_summaries),
        "per_axis_status_counts": {axis: dict(counts) for axis, counts in axis_status_counts.items()},
        "terminal_disposition_path": str(terminal_disposition_csv or ""),
        "terminal_disposition_sha256": sha256_file(terminal_disposition_csv) if terminal_disposition_csv else "",
        "reference_conflict_review_record_path": str(reference_conflict_review_record or ""),
        "reference_conflict_review_record_sha256": sha256_file(reference_conflict_review_record) if reference_conflict_review_record else "",
        "reference_conflict_review_closed": reference_review is not None,
        "formal_ready": True,
        "blockers": [],
        "dependencies": [
            {"role": role, "path": str(path.resolve()), "sha256": sha256_file(path)}
            for role, path in (
                ("C1_A_SNAPSHOT", c1_closeout_summary), ("C2B_ASSIGNMENT", assignment_csv),
                ("C2B_SUBMISSIONS", submissions_csv), ("C2B_WORKER_ROSTER", worker_roster_csv),
                ("C2B_RULE_CONFIG", rule_config), ("C2B_DESIGN_SUMMARY", design_summary),
                ("C2B_LAUNCH_REPORT", launch_report), ("C2B_RUNTIME_MAPPING_AUDIT", runtime_mapping_audit),
                ("C2B_PRIVATE_ASSIGNMENT_AUDIT", private_assignment_audit),
                ("POST_C2B_PROFILE", post_profile_csv), ("POST_C2B_PROFILE_MANIFEST", profile_manifest),
                ("METHOD_CONTRACT", METHOD_CONTRACT),
            )
        ],
    }
    if terminal_disposition_csv:
        summary["dependencies"].append({
            "role": "C2B_TERMINAL_DISPOSITION", "path": str(terminal_disposition_csv.resolve()),
            "sha256": sha256_file(terminal_disposition_csv),
        })
    if reference_conflict_review_record:
        summary["dependencies"].append({
            "role": "REFERENCE_CONFLICT_REVIEW_CLOSED",
            "path": str(reference_conflict_review_record.resolve()),
            "sha256": sha256_file(reference_conflict_review_record),
        })
    output_summary.parent.mkdir(parents=True, exist_ok=True)
    output_summary.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return summary


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Materialize the formal C2-B closeout SHA chain.")
    parser.add_argument("--submissions-csv", type=Path, required=True)
    parser.add_argument("--post-profile-csv", type=Path, required=True)
    parser.add_argument("--profile-manifest", type=Path, required=True)
    parser.add_argument("--design-summary", type=Path, required=True)
    parser.add_argument("--c1-closeout-summary", type=Path, required=True)
    parser.add_argument("--assignment-csv", type=Path, required=True)
    parser.add_argument("--worker-roster-csv", type=Path, required=True)
    parser.add_argument("--rule-config", type=Path, required=True)
    parser.add_argument("--launch-report", type=Path, required=True)
    parser.add_argument("--runtime-mapping-audit", type=Path, required=True)
    parser.add_argument("--private-assignment-audit", type=Path, required=True)
    parser.add_argument("--output-summary", type=Path, required=True)
    parser.add_argument("--terminal-disposition-csv", type=Path)
    parser.add_argument("--reference-conflict-review-record", type=Path)
    parser.add_argument("--input-status", choices=("dry_run", "precloseout_rehearsal", "formal"), default="formal")
    args = parser.parse_args(argv)
    print(json.dumps(materialize(
        args.submissions_csv, args.post_profile_csv, args.profile_manifest,
        args.design_summary, args.c1_closeout_summary, args.assignment_csv,
        args.worker_roster_csv, args.rule_config, args.launch_report,
        args.runtime_mapping_audit, args.private_assignment_audit,
        args.output_summary, input_status=args.input_status,
        terminal_disposition_csv=args.terminal_disposition_csv,
        reference_conflict_review_record=args.reference_conflict_review_record,
    ), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
