"""Two-day fail-closed C1 closeout and C2-B launch orchestration."""

from __future__ import annotations

import argparse
import csv
import hashlib
import importlib.metadata
import json
import platform
import subprocess
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np

_PROJECT_ROOT = Path(__file__).resolve().parents[3]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from tools.thesis_main.analysis import build_c2_assignment_manifest_from_c1_gaps as c2b
from tools.thesis_main.analysis.active_log_utils import freeze_active_log_snapshot, validate_active_log_freeze_manifest
from tools.thesis_main.analysis.run_c1_precloseout_rehearsal import _aggregate_sha, _manifest_rows, materialize as materialize_c1
from tools.thesis_main.analysis.materialize_c2b_task_eligibility import materialize as materialize_c2b_task_eligibility
from tools.thesis_main.analysis.materialize_c2_task_risk import materialize_formal as materialize_task_risk
from tools.thesis_main.analysis.c1_c2_mainline import formal_git_state
from tools.thesis_main.analysis.c1_c2_mainline import materialize_c2b_design_worker_profile
from tools.thesis_main.analysis.materialize_c1_c2_design_parameters import materialize as materialize_design_parameters
from tools.thesis_main.analysis.paper_a_contracts import METHOD_CONTRACT, load_method_contract, validate_generated_subordinate
from tools.thesis_main.analysis.derive_c2b_design_thresholds import derive_threshold_manifest, validate_formula_contract
from tools.thesis_main.analysis.materialize_c2_task_risk import _feature_audit_passes, freeze_feature_reference, refresh_feature_freeze_approval
from tools.thesis_main.analysis.materialize_c2b_legacy_provenance import materialize as materialize_legacy_provenance
from tools.thesis_main.analysis.materialize_p1_post_closeout_evidence_correction import materialize as materialize_p1_correction
from tools.thesis_main.analysis.materialize_p1_post_closeout_geometry_scores import materialize_scores as materialize_p1_geometry
from tools.thesis_main.analysis.c2b_static_evidence import (
    candidate_scene_mapping_key,
    materialize_history_overlap,
    materialize_building_registry_from_scene_mapping,
    materialize_p1_integrity_bundle,
    materialize_reference_candidate_leakage,
    materialize_split_proposals,
    materialize_static_freeze_manifest,
    materialize_static_model_risk,
    validate_p1_integrity_bundle,
)
from tools.thesis_main.analysis.vfinal_artifact_utils import sha256_file
from tools.thesis_main.registry.hohonet_feature_backend import extract_orbit_descriptors


COMMAND_ARTIFACT_CONTRACT = {
    "rehearse-c1": {"outputs": ("analysis_dependency_manifest.json",)},
    "expand-building-registry": {
        "outputs": ("authoritative_building_registry.csv",),
    },
    "prepare-c2b-static": {
        "outputs": ("c2b_static_freeze_manifest.json", "c2b_source_holdout_split_proposals.summary.json"),
    },
    "freeze-c1": {
        "outputs": ("c1_active_log_freeze_manifest.json", "c1_collection_closure_manifest.json"),
    },
    "audit-c1": {
        "requires": (("freeze-c1", "c1_active_log_freeze_manifest.json"), ("freeze-c1", "c1_collection_closure_manifest.json")),
        "outputs": ("formal_audit_summary.json", "c1_measurement_freeze_manifest.json"),
    },
    "finalize-c1": {
        "requires": (("audit-c1", "formal_audit_summary.json"), ("audit-c1", "c1_measurement_freeze_manifest.json")),
        "outputs": ("c1_evidence_freeze_manifest.json",),
    },
    "freeze-c1-batch": {"outputs": ("c1_a_analysis_snapshot.json",)},
    "design-c2b": {
        "requires": (("prepare-c2b-static", "c2b_static_freeze_manifest.json"), ("freeze-c1-batch", "c1_a_analysis_snapshot.json")),
        "outputs": ("c2_task_risk.summary.json", "c2b_evidence_freeze_envelope.json", "c2b_design.summary.json"),
    },
    "build-c2b": {
        "requires": (("design-c2b", "c2_task_risk.summary.json"), ("design-c2b", "c2b_design.summary.json")),
        "outputs": ("assignment_manifest_C2B.csv", "c2b_launch_ready_report.json"),
    },
    "bind-c2b-runtime-mapping": {"outputs": ("c2b_runtime_task_mapping.csv", "c2b_worker_task_binding_audit.json")},
    "check-command-contract": {"outputs": ()},
}

FORMAL_BATCH_COMMANDS = ("rehearse-c1", "freeze-c1-batch", "design-c2b", "build-c2b", "bind-c2b-runtime-mapping")


def validate_runbook_command_contract(runbook: Path) -> dict[str, Any]:
    text = runbook.read_text(encoding="utf-8")
    missing = []
    for command in FORMAL_BATCH_COMMANDS:
        contract = COMMAND_ARTIFACT_CONTRACT[command]
        if command not in text:
            missing.append(f"missing_command:{command}")
        for artifact in contract.get("outputs", ()):
            if artifact not in text:
                missing.append(f"missing_output:{command}:{artifact}")
        for producer, artifact in contract.get("requires", ()):
            if producer not in COMMAND_ARTIFACT_CONTRACT or artifact not in COMMAND_ARTIFACT_CONTRACT[producer].get("outputs", ()):
                missing.append(f"unproduced_input:{command}:{artifact}")
    if "c2_task_risk_summary.json" in text:
        missing.append("deprecated_artifact_name:c2_task_risk_summary.json")
    return {"valid": not missing, "violations": missing, "command_count": len(COMMAND_ARTIFACT_CONTRACT)}


def _read(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as stream:
        return list(csv.DictReader(stream))


def _write(path: Path, rows: list[dict[str, Any]]) -> None:
    fields = list(dict.fromkeys(key for row in rows for key in row)) if rows else ["status"]
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields, extrasaction="ignore"); writer.writeheader(); writer.writerows(rows)


def _source_identity_aggregate(rows: list[dict[str, Any]]) -> str:
    """Hash source identity only; raw-snapshot bookkeeping must not change it."""
    return _aggregate_sha([{name: row[name] for name in ("path", "size", "sha256")} for row in rows])


_TERMINAL_CALIBRATION_STATUSES = {"completed", "closed_partial_usable", "closed_partial_insufficient", "nonstarter", "administrative_exclusion"}


def _method_identity() -> dict[str, str]:
    method = load_method_contract()
    return {"method_contract_version": method["contract_version"], "method_contract_sha256": sha256_file(METHOD_CONTRACT)}


def _require_current_subordinate(path: Path, role: str) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    validate_generated_subordinate(payload, role=role)
    return payload


def _truth(value: Any) -> bool:
    return str(value).strip().lower() in {"true", "1", "yes"}


def _identity_key(row: dict[str, Any]) -> tuple[str, str, str]:
    return (
        str(row.get("worker_id", "")).strip(),
        str(row.get("base_task_id", "")).strip(),
        str(row.get("condition", "")).strip().lower(),
    )


def _repair_scope(scope: dict[str, Any]) -> dict[str, list[dict[str, str]]]:
    repairs = scope.get("authorized_repair_identities")
    if not isinstance(repairs, dict):
        raise ValueError("C1_A scope requires authorized_repair_identities grouped by w034 and w001")
    normalized: dict[str, list[dict[str, str]]] = {}
    for group, expected_count in (("w034", 17), ("w001", 3)):
        entries = repairs.get(group)
        if not isinstance(entries, list) or len(entries) != expected_count:
            raise ValueError(f"C1_A scope requires exactly {expected_count} {group} authorized repair identities")
        normalized[group] = []
        seen: set[tuple[str, str, str]] = set()
        for entry in entries:
            if not isinstance(entry, dict):
                raise ValueError(f"{group} repair identity is not an object")
            item = {name: str(entry.get(name, "")).strip() for name in ("worker_id", "base_task_id", "condition", "authorized_addendum_row_identity", "authorized_addendum_row_sha256")}
            item["condition"] = item["condition"].lower()
            key = _identity_key(item)
            expected_worker = "34" if group == "w034" else "1"
            worker_number = key[0].upper().removeprefix("W").lstrip("0") or "0"
            if not all(key) or key in seen or worker_number != expected_worker:
                raise ValueError(f"{group} repair identities must be complete and unique by worker/base-task/condition")
            seen.add(key); normalized[group].append(item)
    return normalized


def _snapshot_dependencies(snapshot: dict[str, Any], *roles: str) -> dict[str, Path]:
    resolved: dict[str, Path] = {}
    dependencies = snapshot.get("dependencies", [])
    if not isinstance(dependencies, list):
        raise ValueError("C1_A snapshot dependencies are invalid")
    for role in roles:
        matches = [item for item in dependencies if isinstance(item, dict) and item.get("role") == role]
        if len(matches) != 1:
            raise ValueError(f"C1_A snapshot dependency is missing or ambiguous:{role}")
        path = Path(str(matches[0].get("path", "")))
        if not path.is_file() or matches[0].get("sha256") != sha256_file(path):
            raise ValueError(f"C1_A snapshot dependency is stale or unavailable:{role}")
        resolved[role] = path
    return resolved


def _addendum_row_sha256(row: dict[str, str]) -> str:
    return hashlib.sha256(json.dumps(row, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()


def freeze_c1_batch(args: argparse.Namespace) -> dict[str, Any]:
    """Freeze C1-A analysis/design inputs without closing future enrollment."""
    c1_dir = args.c1_output_dir.resolve()
    scope = json.loads(args.batch_scope_manifest.read_text(encoding="utf-8"))
    if scope.get("schema_version") != "paper_a_c1_batch_scope_v1" or scope.get("batch_id") != "C1_A":
        raise ValueError("freeze-c1-batch requires a C1_A batch-scope manifest")
    cutoff = str(scope.get("data_cutoff_server_time", "")).strip()
    originals = {str(value) for value in scope.get("original_worker_ids", []) if str(value)}
    repairs = _repair_scope(scope)
    completion_exceptions = {str(value) for value in scope.get("original_completion_exception_task_ids", []) if str(value)}
    if not cutoff or not originals:
        raise ValueError("C1_A scope must bind cutoff and original roster")
    profile_path = c1_dir / "c1_three_track_worker_state.csv"
    eligibility_path = c1_dir / "c1_row_analysis_eligibility.csv"
    readiness_path = c1_dir / "c1_measurement_freeze_manifest.json"
    required = {
        "ANALYSIS_DEPENDENCY_BUNDLE": c1_dir / "analysis_dependency_manifest.json",
        "CANONICAL_ELIGIBILITY": eligibility_path,
        "VARIABLE_K": c1_dir / "c1_estimand_specific_task_support.csv",
        "PEER": c1_dir / "geometry_worker_task_peer_analysis.csv",
        "LOO": c1_dir / "geometry_worker_task_loo_analysis.csv",
        "Q_GT": c1_dir / "c1_gt_quality_analysis.csv",
        "Q_GT_MODEL_AUDIT": c1_dir / "c1_task_adjusted_qgt_model_audit.json",
        "STRUCTURAL_EB": c1_dir / "structural_validation_analysis.csv",
        "STRUCTURAL_EB_AUDIT": c1_dir / "c1_structural_reliability_eb.csv",
        "COMPLETION": c1_dir / "c1_worker_completion_audit.csv",
        "REFERENCE": c1_dir / "c1_task_outcome_reference.csv",
        "BUILDING": c1_dir / "c1_task_building_binding.csv",
        "W034_SENSITIVITY": c1_dir / "w034_original_vs_authorized_sensitivity.json",
        "WORKER_PROFILE": profile_path,
        "MEASUREMENT_READINESS": readiness_path,
    }
    blockers = [f"missing:{role}" for role, path in required.items() if not path.is_file()]
    profile_rows = _read(profile_path) if profile_path.is_file() else []
    repair_workers = {entry["worker_id"] for values in repairs.values() for entry in values}
    included_workers = originals | repair_workers
    if not originals <= {row.get("worker_id", "") for row in profile_rows if row.get("enrollment_batch") == "original"}:
        blockers.append("original_roster_not_bound_to_worker_profile")
    if any(row.get("enrollment_batch") == "late_entry" for row in profile_rows):
        blockers.append("late_entry_profile_present_in_c1_a_source")
    eligibility_rows = _read(eligibility_path) if eligibility_path.is_file() else []
    repair_rows: list[dict[str, str]] = []
    addendum_rows = _read(args.authorized_reassignment_manifest) if getattr(args, "authorized_reassignment_manifest", None) else []
    for group, entries in repairs.items():
        for entry in entries:
            label = ":".join((group, *(_identity_key(entry))))
            candidates = [
                row for row in eligibility_rows
                if _identity_key(row) == _identity_key(entry)
                and row.get("assignment_provenance") == "authorized_replacement_assignment"
                and _truth(row.get("formal_assignment_eligible"))
                and str(row.get("canonical_annotation_id", "")).strip()
            ]
            if len(candidates) != 1:
                blockers.append(f"authorized_repair_identity_unresolved:{label}")
                continue
            if entry["authorized_addendum_row_identity"] or entry["authorized_addendum_row_sha256"]:
                matching_addenda = [row for row in addendum_rows if _identity_key(row) == _identity_key(entry)]
                if len(matching_addenda) != 1:
                    blockers.append(f"authorized_addendum_identity_unresolved:{label}")
                    continue
                addendum = matching_addenda[0]
                row_identity = next((str(addendum.get(name, "")).strip() for name in ("authorized_addendum_row_identity", "authorized_reassignment_row_id", "row_id", "id") if str(addendum.get(name, "")).strip()), "")
                if (entry["authorized_addendum_row_identity"] and entry["authorized_addendum_row_identity"] != row_identity) or (entry["authorized_addendum_row_sha256"] and entry["authorized_addendum_row_sha256"] != _addendum_row_sha256(addendum)):
                    blockers.append(f"authorized_addendum_identity_mismatch:{label}")
                    continue
            repair_rows.append({**candidates[0], "repair_group": group})
    canonical_repair_ids = {row["canonical_annotation_id"] for row in repair_rows}
    if len(canonical_repair_ids) != 20:
        blockers.append("authorized_repair_count_not_exactly_20")
    completion_rows = {str(row.get("task_id") or row.get("planned_task_id") or row.get("canonical_annotation_id") or ""): row for row in eligibility_rows if row.get("worker_id") in originals}
    missing_completion = sorted(completion_exceptions - set(completion_rows))
    if missing_completion:
        blockers.append("original_completion_exception_missing:" + ",".join(missing_completion))
    nonterminal_completion = sorted(task for task in completion_exceptions & set(completion_rows) if not (_truth(completion_rows[task].get("formal_assignment_eligible")) or str(completion_rows[task].get("completion_status", "")) in _TERMINAL_CALIBRATION_STATUSES))
    if nonterminal_completion:
        blockers.append("original_completion_exception_not_terminal:" + ",".join(nonterminal_completion))
    included_rows = [
        row for row in eligibility_rows
        if (row.get("worker_id") in originals and row.get("assignment_provenance") == "original_assignment")
        or row.get("canonical_annotation_id") in canonical_repair_ids
    ]
    eligible_base_task_ids = sorted({str(row.get("base_task_id", "")) for row in included_rows if _truth(row.get("formal_assignment_eligible")) and row.get("base_task_id")})
    identity_rows = [{
        "canonical_annotation_id": row.get("canonical_annotation_id", ""), "worker_id": row.get("worker_id", ""),
        "base_task_id": row.get("base_task_id", ""), "condition": row.get("condition", ""),
        "assignment_provenance": row.get("assignment_provenance", ""),
        "included_in_c1_a": str(row in included_rows).lower(),
    } for row in eligibility_rows]
    identity_manifest = args.output.parent / "c1_a_canonical_annotation_identity_manifest.csv"
    _write(identity_manifest, identity_rows)
    w034 = json.loads(required["W034_SENSITIVITY"].read_text(encoding="utf-8")) if required["W034_SENSITIVITY"].is_file() else {}
    if w034.get("status") != "frozen": blockers.append("w034_sensitivity_not_frozen")
    readiness = json.loads(readiness_path.read_text(encoding="utf-8")) if readiness_path.is_file() else {}
    if readiness.get("C1_CANONICAL_CLOSED") is not True: blockers.append("c1_a_canonical_evidence_not_closed")
    if not any(_truth(row.get("c2_risk_model_eligible")) for row in profile_rows if row.get("worker_id") in included_workers): blockers.append("no_c2b_eligible_original_worker")
    frozen = not blockers
    snapshot = {
        "schema_version": "paper_a_c1_batch_analysis_snapshot_v1", "artifact_role": "C1_A_ANALYSIS_SNAPSHOT", "batch_id": "C1_A",
        "status": "formal_design_eligible" if frozen else "provisional", "data_cutoff_server_time": cutoff,
        "source_c1_output_dir": str(c1_dir), "source_c1_output_manifest_sha256": sha256_file(required["ANALYSIS_DEPENDENCY_BUNDLE"]) if required["ANALYSIS_DEPENDENCY_BUNDLE"].is_file() else "",
        "original_worker_ids": sorted(originals), "authorized_repair_set": {"w034": [entry for entry in repairs["w034"]], "w001": [entry for entry in repairs["w001"]], "resolved_canonical_annotation_ids": sorted(canonical_repair_ids), "expected_count": 20}, "original_completion_exception_task_ids": sorted(completion_exceptions),
        "included_canonical_annotation_identity_manifest_sha256": sha256_file(identity_manifest),
        "eligible_base_task_ids": eligible_base_task_ids, "reference_registry_sha256": sha256_file(required["REFERENCE"]) if required["REFERENCE"].is_file() else "",
        "C1_A_ANALYSIS_SNAPSHOT_MATERIALIZED": True, "C1_A_ANALYSIS_SNAPSHOT_FROZEN": frozen, "C2B_BASELINE_INPUT_FROZEN": frozen, "C2B_DESIGN_INPUT_FROZEN_FROM_C1_A": frozen,
        "C2B_ASSIGNMENT_BATCH_A_MATERIALIZED": False, "C2B_ASSIGNMENT_BATCH_B_MATERIALIZED": False,
        "CALIBRATION_ENROLLMENT_CLOSED": False, "ALL_CALIBRATION_WORKERS_TERMINAL": False, "FINAL_POOLED_PROFILE_FROZEN": False,
        "blockers": blockers, **_method_identity(),
        "dependencies": [{"role": role, "path": str(path.resolve()), "sha256": sha256_file(path)} for role, path in required.items() if path.is_file()] + ([{"role": "AUTHORIZED_REASSIGNMENT_MANIFEST", "path": str(args.authorized_reassignment_manifest.resolve()), "sha256": sha256_file(args.authorized_reassignment_manifest)}] if getattr(args, "authorized_reassignment_manifest", None) else []) + [{"role": "BATCH_SCOPE", "path": str(args.batch_scope_manifest.resolve()), "sha256": sha256_file(args.batch_scope_manifest)}, {"role": "CANONICAL_IDENTITY_MANIFEST", "path": str(identity_manifest.resolve()), "sha256": sha256_file(identity_manifest)}, {"role": "METHOD_CONTRACT", "path": str(METHOD_CONTRACT.resolve()), "sha256": sha256_file(METHOD_CONTRACT)}],
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(snapshot, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return snapshot


def _require_approval(path: Path, evidence: Path, sha_field: str) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if payload.get("approved") is not True or payload.get(sha_field) != sha256_file(evidence):
        raise ValueError(f"approval_invalid_or_stale:{sha_field}")
    return payload


def _c2_source_images(rows: list[dict[str, str]]) -> set[str]:
    return {
        row.get("image_id", "") for row in rows
        if str(row.get("allocation", row.get("source_split_allowed", ""))).lower() in {"c2", "true", "1", "allowed"}
        and row.get("image_id")
    }


def _future_heldout_images(rows: list[dict[str, str]]) -> set[str]:
    return {
        row.get("image_id", "") for row in rows
        if row.get("image_id") and (
            str(row.get("allocation", "")).lower() in {"future_holdout", "t1", "v1", "holdout"}
            or str(row.get("future_holdout_clear", row.get("clear", ""))).lower() in {"false", "0", "held", "holdout", "blocked"}
        )
    }


def _final_risk_pool_gate(rows: list[dict[str, str]], threshold_manifest: Path) -> dict[str, Any]:
    thresholds = json.loads(threshold_manifest.read_text(encoding="utf-8"))
    values = thresholds.get("thresholds", {})
    required = (
        "minimum_eligible_task_count", "minimum_eligible_building_count",
        "minimum_ordinary_task_count", "minimum_stress_task_count",
    )
    approved = (
        thresholds.get("status") == "approved"
        and thresholds.get("formal_selection_allowed") is True
        and all(values.get(name) not in {None, ""} for name in required)
    )
    eligible = [row for row in rows if str(row.get("assignment_eligible", "")).lower() in {"true", "1"}]
    counts = Counter(row.get("risk_design_stratum", "") for row in eligible)
    buildings = {row.get("building_id", "") for row in eligible} - {""}
    observed = {
        "minimum_eligible_task_count": len(eligible),
        "minimum_eligible_building_count": len(buildings),
        "minimum_ordinary_task_count": counts["ordinary"],
        "minimum_stress_task_count": counts["stress"],
    }
    failures = [name for name in required if not approved or observed[name] < int(values.get(name) or 0)]
    return {"frozen": approved and not failures, "approved_thresholds": approved, "observed": observed, "failures": failures}


def _materialize_c2b_evidence_envelope(args: argparse.Namespace) -> dict[str, Any]:
    static = json.loads(args.static_freeze_manifest.read_text(encoding="utf-8"))
    source_approval = _require_approval(args.source_split_approval, args.source_split_evidence, "source_split_evidence_sha256")
    holdout_approval = _require_approval(args.future_holdout_approval, args.future_holdout_evidence, "future_holdout_evidence_sha256")
    split_summary_sha = static.get("artifacts", {}).get("split_proposals", {}).get("sha256", "")
    selected_proposal_id = str(source_approval.get("selected_proposal_id", "")).strip()
    split_approval_bound = (
        bool(selected_proposal_id)
        and selected_proposal_id == holdout_approval.get("selected_proposal_id")
        and source_approval.get("split_proposal_summary_sha256") == split_summary_sha
        and holdout_approval.get("split_proposal_summary_sha256") == split_summary_sha
    )
    artifacts = {
        "static_freeze_manifest": args.static_freeze_manifest,
        "feature_freeze_manifest": args.feature_freeze_manifest,
        "building_registry": args.building_registry,
        "source_split_evidence": args.source_split_evidence,
        "source_split_approval": args.source_split_approval,
        "future_holdout_evidence": args.future_holdout_evidence,
        "future_holdout_approval": args.future_holdout_approval,
        "history_overlap_audit": args.history_overlap_audit,
        "scope_registry": args.scope_registry,
        "reference_registry": args.reference_registry,
        "leakage_audit": args.feature_freeze_manifest.parent / "c2b_reference_candidate_leakage_audit.summary.json",
    }
    missing = [name for name, path in artifacts.items() if not path.exists()]
    static_feature = static.get("artifacts", {}).get("feature_freeze", {}).get("sha256", "")
    proposal_rows_raw = str(static.get("artifacts", {}).get("split_proposal_rows", {}).get("path", ""))
    proposal_rows_path = Path(proposal_rows_raw) if proposal_rows_raw else Path("__missing_split_proposal_rows__")
    proposal_rows = _read(proposal_rows_path) if proposal_rows_path.is_file() else []
    expected_allocations = {
        (row.get("image_id", ""), row.get("base_task_id", "")): row.get("allocation", "")
        for row in proposal_rows if row.get("proposal_id") == selected_proposal_id
    }

    def allocations(path: Path, *, holdout: bool = False) -> dict[tuple[str, str], str]:
        output: dict[tuple[str, str], str] = {}
        for row in _read(path):
            key = (row.get("image_id", ""), row.get("base_task_id", ""))
            allocation = str(row.get("allocation", "")).lower()
            if allocation in {"c2", "c2_source", "source", "allowed"}:
                normalized = "c2_source"
            elif allocation in {"future_holdout", "holdout", "t1", "v1"}:
                normalized = "future_holdout"
            elif holdout:
                normalized = "c2_source" if str(row.get("future_holdout_clear", "")).lower() in {"true", "1", "clear"} else "future_holdout"
            else:
                normalized = "c2_source" if str(row.get("source_split_allowed", "")).lower() in {"true", "1", "allowed"} else "future_holdout"
            output[key] = normalized
        return output

    source_allocations = allocations(args.source_split_evidence)
    holdout_allocations = allocations(args.future_holdout_evidence, holdout=True)
    selected_split_exact = bool(expected_allocations) and source_allocations == expected_allocations and holdout_allocations == expected_allocations
    bindings_ok = (
        not missing and static.get("static_evidence_frozen") is True
        and static_feature == sha256_file(args.feature_freeze_manifest)
        and split_approval_bound and selected_split_exact
    )
    rows_complete = True
    for path, status_fields in (
        (args.building_registry, ("registry_status", "reviewed_by", "reviewed_at")),
        (args.scope_registry, ("registry_status", "reviewed_by", "reviewed_at")),
        (args.reference_registry, ("registry_status", "reviewed_by", "reviewed_at")),
    ):
        rows = _read(path) if path.exists() else []
        rows_complete = rows_complete and bool(rows) and all(all(str(row.get(field, "")).strip() for field in status_fields) for row in rows)
    payload = {
        "schema_version": "paper_a_c2b_evidence_freeze_envelope_v1",
        "artifact_owner": "design-c2b", "artifacts": {
            name: {"path": path.resolve().as_posix(), "sha256": sha256_file(path)}
            for name, path in artifacts.items() if path.exists()
        },
        "source_split_approval": source_approval,
        "future_holdout_approval": holdout_approval,
        "selected_proposal_id": selected_proposal_id,
        "split_approval_bound": split_approval_bound,
        "selected_split_exact": selected_split_exact,
        "missing_artifacts": missing,
        "registry_rows_complete": rows_complete,
        "C2B_EVIDENCE_FROZEN": bindings_ok and rows_complete,
        "selected_design_frozen": False,
        "selected_task_reference_frozen": False,
        "capacity_approved": False,
    }
    path = args.output_dir / "c2b_evidence_freeze_envelope.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return payload


def _environment_manifest(checkpoint: Path, config: Path) -> dict[str, Any]:
    import torch

    packages = {}
    for name in (
        "torch", "torchvision", "numpy", "pandas", "scipy", "statsmodels",
        "scikit-learn", "Shapely", "PyYAML", "Pillow", "imageio",
    ):
        try: packages[name] = importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError: packages[name] = "missing"
    try:
        driver = subprocess.run(
            ["nvidia-smi", "--query-gpu=driver_version", "--format=csv,noheader"],
            capture_output=True, text=True, check=False,
        )
        driver_version = driver.stdout.splitlines()[0].strip() if driver.returncode == 0 and driver.stdout.strip() else ""
    except OSError:
        driver_version = ""
    device = torch.cuda.get_device_properties(0) if torch.cuda.is_available() else None
    lock_files = {
        name: _PROJECT_ROOT / "config" / name
        for name in ("paper_a_analysis_requirements.lock.txt", "paper_a_torch_requirements.lock.txt")
    }
    git_head = subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True, check=False).stdout.strip()
    diff = subprocess.run(["git", "diff", "--binary", "HEAD"], capture_output=True, check=False).stdout
    return {
        "schema_version": "paper_a_analysis_environment_v1", "python": platform.python_version(),
        "python_executable": sys.executable, "platform": platform.platform(), "packages": packages,
        "cuda_build": torch.version.cuda, "cuda_available": torch.cuda.is_available(),
        "gpu_name": torch.cuda.get_device_name(0) if torch.cuda.is_available() else "",
        "gpu_count": torch.cuda.device_count(),
        "gpu_total_memory_bytes": int(device.total_memory) if device else 0,
        "gpu_compute_capability": f"{device.major}.{device.minor}" if device else "",
        "nvidia_driver_version": driver_version,
        "checkpoint_sha256": sha256_file(checkpoint),
        "config_sha256": sha256_file(config), "formal_device": "cuda:0", "dtype": "float32",
        "physical_batch_size": 4, "automatic_device_fallback": False,
        "dependency_lock_sha256": {
            name: sha256_file(path) if path.exists() else ""
            for name, path in lock_files.items()
        },
        "git_head": git_head,
        "worktree_diff_sha256": __import__("hashlib").sha256(diff).hexdigest(),
    }


def _materialize_static_evidence_review_queues(
    inventory_csv: Path, legacy_manifest: Path, output_dir: Path,
) -> dict[str, Any]:
    """Create non-authoritative review queues for every formal C2-B registry.

    The queues deliberately contain no approved gate value.  They make the
    missing evidence visible before C1 closeout without allowing inventory
    booleans or image-name conventions to become formal evidence.
    """
    inventory = _read(inventory_csv)
    legacy_keys = {
        (row.get("image_id", ""), row.get("base_task_id", ""))
        for row in _read(legacy_manifest)
    }
    identities: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    for row in inventory:
        key = (str(row.get("image_id", "")).strip(), str(row.get("base_task_id", "")).strip())
        if not all(key) or key in seen:
            raise ValueError("candidate inventory requires unique image_id + base_task_id")
        seen.add(key)
        identities.append({
            "image_id": key[0], "base_task_id": key[1], "task_id": row.get("task_id", ""),
            "source_path": row.get("source_path", ""), "source_pool": row.get("source_pool", ""),
            "scene_id": row.get("scene_id", ""), "scene_key": row.get("scene_key", ""),
            "legacy_reverse_member": key in legacy_keys,
            "inventory_diagnostic_used_in_prescreen": row.get("used_in_prescreen", ""),
            "inventory_diagnostic_used_in_random_c1": row.get("used_in_random_c1_deprecated", ""),
            "inventory_diagnostic_geometry_gold_ready": row.get("geometry_gold_ready", ""),
            "inventory_diagnostic_scope_gold_ready": row.get("scope_gold_ready", ""),
        })

    by_scene: dict[str, dict[str, Any]] = {}
    for row in identities:
        scene_key, scene_key_source = candidate_scene_mapping_key(row)
        by_scene.setdefault(scene_key, {
            **row, "scene_mapping_key": scene_key, "scene_key_source": scene_key_source,
            "scene_key_status": "requires_human_validation", "building_id": "",
            "registry_status": "pending_scene_mapping_review", "reviewed_by": "", "reviewed_at": "",
        })
    scene_pilot = [by_scene[key] for key in sorted(by_scene)[:15]]
    scope_queue = [
        {**row, "final_scope": "", "registry_status": "pending_missing_or_conflicting_scope", "reviewed_by": "", "reviewed_at": ""}
        for row in identities
        if str(row.get("inventory_diagnostic_scope_gold_ready", "")).lower() not in {"true", "1"}
    ]
    reference_queue = [
        {**row, "geometry_reference_ready": "", "registry_status": "pending_missing_or_conflicting_reference", "reviewed_by": "", "reviewed_at": ""}
        for row in identities
        if str(row.get("inventory_diagnostic_geometry_gold_ready", "")).lower() not in {"true", "1"}
    ]
    queue_rows = {
        "authoritative_building_scene_mapping_pilot.review_queue.csv": scene_pilot,
        "scope_registry.minimal_review_queue.csv": scope_queue,
        "reference_registry.minimal_review_queue.csv": reference_queue,
    }
    outputs: dict[str, str] = {}
    for name, rows in queue_rows.items():
        path = output_dir / name
        _write(path, rows)
        outputs[name] = sha256_file(path)
    summary = {
        "schema_version": "paper_a_c2b_static_evidence_review_queues_v1",
        "n_tasks": len(identities), "formal_evidence_ready": False,
        "building_scene_pilot_count": len(scene_pilot),
        "scope_manual_review_count": len(scope_queue),
        "reference_manual_review_count": len(reference_queue),
        "inventory_sha256": sha256_file(inventory_csv),
        "legacy_manifest_sha256": sha256_file(legacy_manifest), "queue_sha256": outputs,
        "contract": "history is derived automatically; split proposals are generated separately; building review starts with at most 15 scene keys; scope/reference queues contain only missing/conflicting diagnostics; queues are non-authoritative",
    }
    (output_dir / "c2b_static_evidence_review_queues.summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8",
    )
    return summary


def prepare_c2b_static(args: argparse.Namespace) -> dict[str, Any]:
    args.output_dir.mkdir(parents=True, exist_ok=True)
    p1_dir = args.output_dir / "p1_integrity"
    correction = materialize_p1_correction(
        args.p1_closeout_dir / "prescreen_canonical_annotations.csv",
        [args.p1_closeout_dir / "p1_combined_exports_for_exact_copy_audit.json"],
        args.p1_closeout_dir / "prescreen_worker_admission.csv", p1_dir,
        initialization_import_json=list(getattr(args, "p1_initialization_import", []) or []),
    )
    geometry = materialize_p1_geometry(
        p1_dir / "p1_task_evidence_correction_v1.csv",
        args.p1_closeout_dir / "prescreen_canonical_annotations.csv",
        args.p1_closeout_dir / "prescreen_gold_status_audit.csv",
        args.p1_closeout_dir / "final_gold_records_v2_p1_closeout_corrected.jsonl", p1_dir,
    )
    p1_bundle = materialize_p1_integrity_bundle(p1_dir)
    legacy = materialize_legacy_provenance(args.legacy_manifest, args.inventory_csv, args.output_dir)
    evidence_review = _materialize_static_evidence_review_queues(
        args.inventory_csv, args.legacy_manifest, args.output_dir,
    )
    inventory_rows = _read(args.inventory_csv)
    declared_candidate_paths = {
        Path(row.get("source_path", ""))
        for row in inventory_rows
        if str(row.get("source_path", "")).strip()
    }
    missing_candidate_paths = sorted(str(path) for path in declared_candidate_paths if not path.exists())
    if not inventory_rows or len(declared_candidate_paths) != len(inventory_rows) or missing_candidate_paths:
        raise ValueError(
            "candidate inventory must bind one existing unique source_path per task; "
            f"rows={len(inventory_rows)}, unique_paths={len(declared_candidate_paths)}, "
            f"missing={missing_candidate_paths[:5]}"
        )
    candidate_paths = sorted(declared_candidate_paths)
    feature_manifest = args.output_dir / "c2_feature_freeze_manifest.json"
    candidate_cache = args.output_dir / "c2_candidate_lhfeat_cache.npz"
    if feature_manifest.exists() and candidate_cache.exists():
        feature = refresh_feature_freeze_approval(
            feature_manifest, args.feature_audit_threshold_manifest,
            checkpoint=args.checkpoint, config=args.config, reference_dir=args.reference_dir,
            candidate_inventory=args.inventory_csv,
        )
    else:
        feature = freeze_feature_reference(
            args.reference_dir, args.checkpoint, args.config,
            args.output_dir / "c2_feature_reference_cache.npz", feature_manifest,
            device=args.device, audit_threshold_manifest=args.feature_audit_threshold_manifest,
        )
        candidate_descriptors, candidate_audit = extract_orbit_descriptors(
            candidate_paths, args.checkpoint, args.config, device=args.device, batch_size=4, audit_seam=True,
        )
        ordered = [path.resolve().as_posix() for path in candidate_paths]
        np.savez_compressed(
            candidate_cache, paths=np.asarray(ordered),
            global_descriptors=np.stack([candidate_descriptors[path][0] for path in ordered]),
            local_descriptors=np.stack([candidate_descriptors[path][1] for path in ordered]),
        )
        feature.update({
            "candidate_descriptor_cache_path": candidate_cache.resolve().as_posix(),
            "candidate_descriptor_cache_sha256": sha256_file(candidate_cache),
            "candidate_inventory_sha256": sha256_file(args.inventory_csv),
            "candidate_descriptor_count": len(ordered), "candidate_extraction_audit": candidate_audit,
            "cache_reused_without_model_inference": False,
        })
    feature_thresholds = json.loads(args.feature_audit_threshold_manifest.read_text(encoding="utf-8"))
    candidate_circular_ready, candidate_seam_ready = _feature_audit_passes(
        feature.get("candidate_extraction_audit", {}),
        feature.get("candidate_extraction_audit", {}),
        feature_thresholds,
    )
    feature["candidate_off_grid_circular_robustness"] = candidate_circular_ready
    feature["candidate_seam_robustness"] = candidate_seam_ready
    feature["feature_audit_status"] = (
        "approved"
        if feature.get("circular_shift_invariant") is True
        and feature.get("seam_invariant") is True
        and candidate_circular_ready and candidate_seam_ready
        else "pending_threshold_approval_or_failed"
    )
    feature_manifest.write_text(json.dumps(feature, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    leakage = materialize_reference_candidate_leakage(
        args.reference_dir, args.reference_dir.parent / "label_cor",
        args.inventory_csv, args.layout_dir, args.output_dir,
    )
    feature["reference_candidate_leakage_audit_sha256"] = sha256_file(args.output_dir / "c2b_reference_candidate_leakage_audit.summary.json")
    feature["reference_candidate_leakage_status"] = leakage["status"]
    if not leakage["formal_feature_pool_allowed"]:
        feature["feature_audit_status"] = "failed_reference_candidate_leakage"
    feature_manifest.write_text(json.dumps(feature, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    static_risk = materialize_static_model_risk(
        feature_manifest, args.inventory_csv, args.output_dir / "c2b_static_model_risk.csv",
    )
    history = materialize_history_overlap(
        args.inventory_csv,
        p1_dir / "p1_task_evidence_correction_v1.csv",
        args.c1_assignment,
        args.output_dir / "history_overlap_audit.csv",
    )
    split: dict[str, Any] = {"status": "not_evaluable_missing_approved_building_registry"}
    if args.building_registry and args.building_registry.exists():
        split = materialize_split_proposals(
            args.inventory_csv, args.output_dir / "history_overlap_audit.csv",
            args.building_registry, args.output_dir / "c2b_static_model_risk.csv", args.output_dir,
        )
    environment = _environment_manifest(args.checkpoint, args.config)
    (args.output_dir / "paper_a_analysis_environment_manifest.json").write_text(json.dumps(environment, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    static_manifest = materialize_static_freeze_manifest(
        args.output_dir,
        {
            "p1_integrity": p1_dir / "p1_integrity_bundle_manifest.json",
            "feature_freeze": feature_manifest,
            "leakage_audit": args.output_dir / "c2b_reference_candidate_leakage_audit.summary.json",
            "leakage_audit_rows": args.output_dir / "c2b_reference_candidate_leakage_audit.csv",
            "reference_image_listing": args.output_dir / "c2b_reference_image_file_listing.csv",
            "reference_layout_listing": args.output_dir / "c2b_reference_layout_file_listing.csv",
            "candidate_image_listing": args.output_dir / "c2b_candidate_image_file_listing.csv",
            "candidate_layout_listing": args.output_dir / "c2b_candidate_layout_file_listing.csv",
            "history_overlap": args.output_dir / "history_overlap_audit.csv",
            "static_model_risk": args.output_dir / "c2b_static_model_risk.csv",
            "split_proposals": args.output_dir / "c2b_source_holdout_split_proposals.summary.json",
            "split_proposal_rows": args.output_dir / "c2b_source_holdout_split_proposals.csv",
            "split_disjointness_audit": args.output_dir / "c2b_source_holdout_split_disjointness_audit.csv",
            "environment": args.output_dir / "paper_a_analysis_environment_manifest.json",
        },
        code_sha256=_aggregate_sha(_manifest_rows([
            Path(__file__), _PROJECT_ROOT / "tools/thesis_main/analysis/c2b_static_evidence.py",
            _PROJECT_ROOT / "tools/thesis_main/analysis/materialize_c2_task_risk.py",
            _PROJECT_ROOT / "tools/thesis_main/registry/hohonet_feature_backend.py",
        ])),
    )
    return {
        "phase": "prepare-c2b-static", "p1_correction": correction,
        "p1_geometry": geometry, "p1_integrity_bundle": p1_bundle, "legacy": legacy,
        "evidence_review": evidence_review, "feature": feature,
        "leakage": leakage, "history": history, "static_risk": static_risk,
        "split_proposals": split, "static_freeze": static_manifest,
        "environment": environment,
    }


def expand_building_registry(args: argparse.Namespace) -> dict[str, Any]:
    return materialize_building_registry_from_scene_mapping(
        args.inventory_csv, args.approved_scene_mapping, args.output_csv,
    )


def check_command_contract(args: argparse.Namespace) -> dict[str, Any]:
    return validate_runbook_command_contract(args.runbook)


def preflight_calibration(args: argparse.Namespace) -> dict[str, Any]:
    required = {
        "environment": args.static_dir / "paper_a_analysis_environment_manifest.json",
        "feature_freeze": args.static_dir / "c2_feature_freeze_manifest.json",
        "p1_correction": args.static_dir / "p1_integrity" / "p1_post_closeout_correction_summary_v1.json",
        "p1_geometry": args.static_dir / "p1_integrity" / "p1_geometry_score_summary_v1.json",
        "p1_integrity_bundle": args.static_dir / "p1_integrity" / "p1_integrity_bundle_manifest.json",
        "legacy_audit": args.static_dir / "c2_legacy_reverse_candidate_audit.summary.json",
        "evidence_review": args.static_dir / "c2b_static_evidence_review_queues.summary.json",
        "leakage_audit": args.static_dir / "c2b_reference_candidate_leakage_audit.summary.json",
        "split_proposals": args.static_dir / "c2b_source_holdout_split_proposals.summary.json",
        "static_freeze": args.static_dir / "c2b_static_freeze_manifest.json",
    }
    blockers = [f"missing:{name}" for name, path in required.items() if not path.exists()]
    try:
        design_thresholds = json.loads(args.threshold_manifest.read_text(encoding="utf-8"))
        try:
            validate_formula_contract(design_thresholds)
        except ValueError:
            blockers.append("unapproved_or_incomplete:design_thresholds")
    except (OSError, json.JSONDecodeError, ValueError):
        blockers.append("invalid:design_thresholds")
    try:
        feature_thresholds = json.loads(args.feature_audit_threshold_manifest.read_text(encoding="utf-8"))
        feature_values = feature_thresholds.get("thresholds", {})
        feature_thresholds_ready = (
            feature_thresholds.get("status") == "approved"
            and feature_thresholds.get("formal_feature_freeze_allowed") is True
            and all(str(feature_thresholds.get(field, "")).strip() for field in ("approved_by", "approved_at"))
            and all(feature_values.get(field) not in {None, ""} for field in (
                "circular_relative_l2_max", "seam_relative_l2_q95",
                "minimum_circular_audited_image_count", "minimum_seam_audited_image_count",
            ))
            and feature_thresholds.get("fail_closed_rules", {}).get("require_finite_metrics") is True
        )
        if not feature_thresholds_ready:
            blockers.append("unapproved_or_incomplete:feature_thresholds")
    except (OSError, json.JSONDecodeError):
        blockers.append("invalid:feature_thresholds")
    feature_freeze: dict[str, Any] = {}
    if required["feature_freeze"].exists():
        feature_freeze = json.loads(required["feature_freeze"].read_text(encoding="utf-8"))
        if feature_freeze.get("feature_audit_status") != "approved":
            blockers.append("feature_freeze_not_approved")
    if required["p1_integrity_bundle"].exists() and not validate_p1_integrity_bundle(args.static_dir / "p1_integrity")["valid"]:
        blockers.append("p1_integrity_bundle_invalid")
    if required["leakage_audit"].exists():
        leakage = json.loads(required["leakage_audit"].read_text(encoding="utf-8"))
        if leakage.get("status") != "passed" or leakage.get("formal_feature_pool_allowed") is not True:
            blockers.append("reference_candidate_leakage_audit_failed")
    if required["split_proposals"].exists():
        split = json.loads(required["split_proposals"].read_text(encoding="utf-8"))
        if split.get("status") != "candidate_only" or split.get("approval_materialized") is not False:
            blockers.append("source_holdout_split_proposals_invalid")
    if required["static_freeze"].exists():
        static_freeze = json.loads(required["static_freeze"].read_text(encoding="utf-8"))
        if static_freeze.get("static_evidence_frozen") is not True:
            blockers.append("static_evidence_not_frozen")
    if required["environment"].exists():
        environment = json.loads(required["environment"].read_text(encoding="utf-8"))
        if not environment.get("cuda_available"): blockers.append("cuda_unavailable")
        if str(environment.get("python", "")).split(".")[:2] != ["3", "11"]: blockers.append("python_version_mismatch")
        if str(environment.get("packages", {}).get("torch", "")).split("+")[0] != "2.11.0": blockers.append("torch_version_mismatch")
        if str(environment.get("packages", {}).get("torchvision", "")).split("+")[0] != "0.26.0": blockers.append("torchvision_version_mismatch")
        if environment.get("cuda_build") != "12.8": blockers.append("cuda_build_mismatch")
        if not environment.get("nvidia_driver_version"): blockers.append("nvidia_driver_version_missing")
        if environment.get("physical_batch_size") != 4: blockers.append("physical_batch_size_mismatch")
        locks = environment.get("dependency_lock_sha256", {})
        if len(locks) != 2 or any(not value for value in locks.values()): blockers.append("dependency_lock_missing")
        if feature_freeze and any(
            environment.get(field) != feature_freeze.get(field)
            for field in ("checkpoint_sha256", "config_sha256")
        ):
            blockers.append("environment_feature_identity_mismatch")
    report = {
        "schema_version": "paper_a_calibration_preflight_v1", "ready": not blockers,
        "blockers": blockers, "static_artifacts": {name: {"path": str(path), "sha256": sha256_file(path) if path.exists() else ""} for name, path in required.items()},
        "next_stage": "freeze-c1" if not blockers else "resolve_preflight_blockers",
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return report


def _materialize_rehearsal_root_cause_report(summary: dict[str, Any]) -> dict[str, Any]:
    output_dir = Path(summary["output_dir"])
    readiness = json.loads((output_dir / "c1_measurement_freeze_manifest.json").read_text(encoding="utf-8"))
    closeout = json.loads((output_dir / "c1_final_canonical_closeout_summary.json").read_text(encoding="utf-8"))
    independence = json.loads((output_dir / "c1_independence_summary.json").read_text(encoding="utf-8"))
    model = json.loads((output_dir / "c1_task_adjusted_qgt_model_audit.json").read_text(encoding="utf-8"))
    design_thresholds = json.loads((_PROJECT_ROOT / "docs/thesis_main/C2B_DESIGN_SELECTION_THRESHOLDS.json").read_text(encoding="utf-8"))
    feature_thresholds = json.loads((_PROJECT_ROOT / "docs/thesis_main/C2B_FEATURE_AUDIT_THRESHOLDS.json").read_text(encoding="utf-8"))
    payload = {
        "schema_version": "paper_a_c1_c2b_root_cause_rehearsal_report_v1",
        "input_export_count": summary.get("n_export_files", 0),
        "state": {
            "formal_closeout_ready": bool(summary.get("formal_closeout_ready")),
            "profile_frozen": bool(summary.get("profile_frozen")),
            "c2_launch_ready": bool(summary.get("c2_launch_ready")),
            "assignment_rows": int(summary.get("c2b_assignment_row_count") or 0),
        },
        "owners": {
            "collection_closure": "freeze-c1", "formal_audit": "audit-c1",
            "c1_evidence_freeze_manifest.json": "finalize-c1",
            "c2b_static_freeze_manifest.json": "prepare-c2b-static",
            "c2b_evidence_freeze_envelope.json": "design-c2b",
            "assignment_manifest_C2B.csv": "build-c2b",
        },
        "collection": summary.get("completion_summary", {}),
        "three_axis_support_after_exclusion": closeout.get("support_after_exclusion", {}),
        "three_axis_freeze_status": {
            "Q_GT": readiness.get("Q_GT_FREEZE_STATUS"), "R_peer": readiness.get("R_PEER_FREEZE_STATUS"),
            "F_struct": readiness.get("F_STRUCT_FREEZE_STATUS"),
            "R_LOO_medoid": readiness.get("R_LOO_MEDOID_STATUS"), "R_LOO_strict": readiness.get("R_LOO_STRICT_STATUS"),
        },
        "p1_integrity": summary.get("p1_integrity", {}),
        "independence": independence, "qgt_model": model,
        "feature_leakage": {"feature": summary.get("c2_task_risk_summary", {}), "leakage": {"status": "not_run_in_c1_stage"}},
        "split": {"status": "not_run_in_c1_stage", "approval_materialized": False},
        "risk_model_boundary": {"status": "not_run_until_design_c2b", "slope_model_form": ""},
        "design_threshold_blocker": {
            "status": design_thresholds.get("status"),
            "formula_contract_frozen": bool(design_thresholds.get("formula_contract_frozen")),
            "final_numeric_threshold_status": "pending_post_c1_sha_bound_derivation",
            "reviewer_input_approval_required": True,
        },
        "feature_threshold_blocker": {
            "status": feature_thresholds.get("status"), "formal_feature_freeze_allowed": feature_thresholds.get("formal_feature_freeze_allowed"),
            "null_thresholds": sorted(name for name, value in feature_thresholds.get("thresholds", {}).items() if value is None),
        },
        "closeout_blockers": summary.get("blockers", []),
    }
    path = output_dir / "c1_c2b_root_cause_rehearsal_report.json"
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return {"path": path.resolve().as_posix(), "sha256": sha256_file(path), **payload}


def rehearse_c1(args: argparse.Namespace) -> dict[str, Any]:
    summary = materialize_c1(
        args.export_dir, args.active_log, args.manual_assignment, args.semi_assignment,
        args.worker_distribution, args.gt_export, args.p1_closeout_dir, args.output_root,
        input_status="precloseout_rehearsal",
        c1_preannotation_feature_csv=getattr(args, "c1_preannotation_feature_csv", None),
        p1_integrity_dir=getattr(args, "p1_integrity_dir", None),
        authorized_reassignment_manifest=getattr(args, "authorized_reassignment_manifest", None),
        late_entry_assignment_manifest=getattr(args, "late_entry_assignment_manifest", None),
        calibration_enrollment_registry=getattr(args, "calibration_enrollment_registry", None),
        w034_active_time_validation_manifest=getattr(args, "w034_active_time_validation_manifest", None),
        building_registry=getattr(args, "building_registry", None),
        independence_disposition=getattr(args, "independence_disposition", None),
        project_independence_disposition=getattr(args, "project_independence_disposition", None),
        duplicate_adjudication=getattr(args, "duplicate_adjudication", None),
        structural_disposition=getattr(args, "structural_disposition", None),
        scope_adjudication=getattr(args, "scope_adjudication", None),
        reference_amendment=getattr(args, "reference_amendment", None),
        outside_assignment_disposition=getattr(args, "outside_assignment_disposition", None),
        completion_disposition=getattr(args, "completion_disposition", None),
    )
    report = _materialize_rehearsal_root_cause_report(summary)
    return {"stage": "C1", "phase": "rehearsal", "output_dir": summary["output_dir"], "formal_closeout_ready": False, "review_required": True, "root_cause_report": report}


def freeze_c1(args: argparse.Namespace) -> dict[str, Any]:
    active = freeze_active_log_snapshot(
        args.source_live_root, args.frozen_root, args.collection_cutoff_server_time,
        args.operator, args.active_log_freeze_manifest,
    )
    closure_args = argparse.Namespace(
        export_dir=args.export_dir,
        manual_assignment=args.manual_assignment,
        semi_assignment=args.semi_assignment,
        c1_active_log_freeze_manifest=args.active_log_freeze_manifest,
        closure_time=args.collection_cutoff_server_time,
        operator=args.operator,
        late_submission_policy=args.late_submission_policy,
        output=args.collection_closure_manifest,
    )
    closure = build_collection_closure(closure_args)
    return {"stage": "C1", "phase": "freeze", "active_log": active, "collection_closure": closure}


def build_collection_closure(args: argparse.Namespace) -> dict[str, Any]:
    freeze_payload = json.loads(args.c1_active_log_freeze_manifest.read_text(encoding="utf-8"))
    frozen_root = Path(str(freeze_payload.get("frozen_root", "")))
    validate_active_log_freeze_manifest(args.c1_active_log_freeze_manifest, frozen_root)
    cutoff = datetime.fromisoformat(str(freeze_payload.get("collection_cutoff_server_time", "")).replace("Z", "+00:00"))
    closure = datetime.fromisoformat(str(args.closure_time).replace("Z", "+00:00"))
    cutoff = cutoff if cutoff.tzinfo else cutoff.replace(tzinfo=timezone.utc)
    closure = closure if closure.tzinfo else closure.replace(tzinfo=timezone.utc)
    if cutoff.astimezone(timezone.utc) != closure.astimezone(timezone.utc):
        raise ValueError("closure_time must equal the active-log collection cutoff")
    export_files = [path for directory in args.export_dir for path in directory.rglob("*.json")]
    assignment_files = [args.manual_assignment, args.semi_assignment]
    payload = {
        "schema_version": "paper_a_c1_collection_closure_v1",
        "c1_export_aggregate_sha256": _aggregate_sha(_manifest_rows(export_files)),
        "c1_active_log_freeze_manifest_sha256": sha256_file(args.c1_active_log_freeze_manifest),
        "c1_assignment_sha256": _aggregate_sha(_manifest_rows(assignment_files)),
        "collection_window_closed": True, "closure_time": args.closure_time,
        "operator": args.operator, "late_submission_policy": args.late_submission_policy,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return payload


def audit_c1(args: argparse.Namespace) -> dict[str, Any]:
    if not getattr(args, "authorized_reassignment_manifest", None) or not getattr(args, "building_registry", None) or not getattr(args, "w034_active_time_validation_manifest", None) or not getattr(args, "calibration_enrollment_registry", None):
        raise ValueError("formal C1 requires authorized reassignment, W034 active-time validation, authoritative building registry, and calibration enrollment registry")
    validate_active_log_freeze_manifest(args.c1_active_log_freeze_manifest, args.active_log)
    summary = materialize_c1(
        args.export_dir, args.active_log, args.manual_assignment, args.semi_assignment,
        args.worker_distribution, args.gt_export, args.p1_closeout_dir, args.output_root,
        input_status="formal", independence_disposition=args.independence_disposition,
        project_independence_disposition=args.project_independence_disposition,
        structural_disposition=args.structural_disposition,
        duplicate_adjudication=args.duplicate_adjudication,
        scope_adjudication=args.scope_adjudication,
        reference_amendment=args.reference_amendment,
        outside_assignment_disposition=args.outside_assignment_disposition,
        completion_disposition=args.completion_disposition,
        c1_preannotation_feature_csv=getattr(args, "c1_preannotation_feature_csv", None),
        c1_active_log_freeze_manifest=args.c1_active_log_freeze_manifest,
        collection_closure_manifest=args.collection_closure_manifest,
        p1_integrity_dir=getattr(args, "p1_integrity_dir", None),
        authorized_reassignment_manifest=args.authorized_reassignment_manifest,
        late_entry_assignment_manifest=getattr(args, "late_entry_assignment_manifest", None),
        calibration_enrollment_registry=args.calibration_enrollment_registry,
        w034_active_time_validation_manifest=args.w034_active_time_validation_manifest,
        building_registry=args.building_registry,
    )
    return {
        "stage": "C1", "phase": "audit", "output_dir": summary["output_dir"],
        "formal_closeout_ready": bool(summary["formal_closeout_ready"]), "blockers": summary["blockers"],
    }


def finalize_c1(args: argparse.Namespace) -> dict[str, Any]:
    audit_path = args.output_dir / "formal_audit_summary.json"
    final_path = args.output_dir / "c1_final_canonical_closeout_summary.json"
    measurement_path = args.output_dir / "c1_measurement_freeze_manifest.json"
    if not all(path.exists() for path in (audit_path, final_path, measurement_path)):
        raise ValueError("finalize-c1 requires a complete formal audit bundle")
    audit, final, measurement = (json.loads(path.read_text(encoding="utf-8")) for path in (audit_path, final_path, measurement_path))
    from tools.thesis_main.analysis.paper_a_contracts import METHOD_CONTRACT, load_method_contract, validate_serialized_record
    method = load_method_contract()
    method_sha = sha256_file(METHOD_CONTRACT)
    worker_manifest_path = args.output_dir / "c1_three_track_worker_state_manifest.json"
    worker_profile_path = args.output_dir / "c1_three_track_worker_state_formal.csv"
    enrollment_registry_path = args.output_dir / "calibration_enrollment_registry.csv"
    enrollment_summary_path = args.output_dir / "calibration_enrollment_registry.summary.json"
    w034_path = args.output_dir / "w034_original_vs_authorized_sensitivity.json"
    dependency_blockers: list[str] = []
    profile_dependency_paths: list[tuple[str, Path]] = []

    def validate_dependency_payload(payload: dict[str, Any], base: Path, trail: str) -> None:
        for index, dependency in enumerate(payload.get("dependencies", [])):
            path = Path(str(dependency.get("path", "")))
            if not path.is_absolute():
                path = base / path
            if not path.is_file() or dependency.get("sha256") != sha256_file(path):
                dependency_blockers.append(f"{trail}:{index}:stale_or_missing")
                continue
            if path.suffix.lower() == ".json":
                child = json.loads(path.read_text(encoding="utf-8"))
                if isinstance(child, dict) and child.get("dependencies"):
                    validate_dependency_payload(child, path.parent, f"{trail}:{index}")

    if not worker_manifest_path.is_file() or not worker_profile_path.is_file():
        dependency_blockers.append("worker_profile_manifest_or_csv_missing")
        worker_manifest: dict[str, Any] = {}
        worker_rows: list[dict[str, str]] = []
    else:
        worker_manifest = json.loads(worker_manifest_path.read_text(encoding="utf-8"))
        worker_rows = [validate_serialized_record("worker_profile_v2", row) for row in _read(worker_profile_path)]
        if worker_manifest.get("worker_state_sha256") != sha256_file(worker_profile_path):
            dependency_blockers.append("worker_profile_sha_mismatch")
        if worker_manifest.get("method_contract_sha256") != method_sha:
            dependency_blockers.append("worker_profile_method_contract_sha_mismatch")
        dependency_roles = {item.get("role") for item in worker_manifest.get("dependencies", [])}
        if "ENROLLMENT_REGISTRY" not in dependency_roles:
            dependency_blockers.append("worker_profile_enrollment_dependency_missing")
        for role in ("REFERENCE_REGISTRY", "REFERENCE_APPROVAL", "BUILDING_REGISTRY", "TASK_BUILDING_BINDING"):
            if role not in dependency_roles:
                dependency_blockers.append(f"worker_profile_{role.lower()}_dependency_missing")
        for dependency in worker_manifest.get("dependencies", []):
            if dependency.get("role") in {"REFERENCE_REGISTRY", "REFERENCE_APPROVAL", "BUILDING_REGISTRY", "TASK_BUILDING_BINDING"}:
                path = Path(str(dependency.get("path", "")))
                profile_dependency_paths.append((str(dependency["role"]), path if path.is_absolute() else worker_manifest_path.parent / path))
        validate_dependency_payload(worker_manifest, worker_manifest_path.parent, "worker_profile")
    if not enrollment_registry_path.is_file() or not enrollment_summary_path.is_file():
        dependency_blockers.append("calibration_enrollment_registry_missing")
        enrollment_rows: list[dict[str, str]] = []
        enrollment_summary: dict[str, Any] = {}
    else:
        enrollment_rows = _read(enrollment_registry_path)
        enrollment_summary = json.loads(enrollment_summary_path.read_text(encoding="utf-8"))
        registry_workers = {row.get("worker_id", "") for row in enrollment_rows}
        profile_workers = {row.get("worker_id", "") for row in worker_rows}
        if registry_workers != profile_workers:
            dependency_blockers.append("enrollment_profile_worker_set_mismatch")
        if enrollment_summary.get("status") != "validated" or enrollment_summary.get("all_registered_workers_terminal") is not True:
            dependency_blockers.append("enrollment_registry_not_validated_or_nonterminal")
        if enrollment_summary.get("registry_sha256") != sha256_file(enrollment_registry_path):
            dependency_blockers.append("enrollment_registry_sha_mismatch")
        if enrollment_summary.get("rolling_activated") is False and int(enrollment_summary.get("N_late") or 0) != 0:
            dependency_blockers.append("rolling_disabled_with_late_workers")
    if not w034_path.is_file():
        dependency_blockers.append("w034_sensitivity_freeze_missing")
        w034: dict[str, Any] = {}
    else:
        w034 = json.loads(w034_path.read_text(encoding="utf-8"))
        if w034.get("schema_version") != "w034_authorized_extension_sensitivity_freeze_v1" or w034.get("status") != "frozen":
            dependency_blockers.append("w034_sensitivity_not_frozen")
        if w034.get("method_contract_sha256") != method_sha:
            dependency_blockers.append("w034_method_contract_sha_mismatch")
        validate_dependency_payload(w034, w034_path.parent, "w034_sensitivity")
    terminal_statuses = {"completed", "closed_partial_usable", "closed_partial_insufficient", "nonstarter", "administrative_exclusion"}
    nonterminal_workers = [row.get("worker_id", "") for row in worker_rows if row.get("completion_status", "") not in terminal_statuses]
    if nonterminal_workers:
        dependency_blockers.append("nonterminal_enrollment:" + ",".join(sorted(nonterminal_workers)))
    adjudication = json.loads(args.adjudication_manifest.read_text(encoding="utf-8"))
    bundle_sha = audit.get("full_dependency_bundle_sha256", "")
    approved = adjudication.get("approved") is True and adjudication.get("input_bundle_sha256") == bundle_sha
    canonical_ready = bool(audit.get("C1_CANONICAL_CLOSED")) and bool(final.get("C1_CANONICAL_CLOSED", True))
    blockers = []
    blockers.extend(dependency_blockers)
    if audit.get("input_status") != "formal": blockers.append("rehearsal_bundle_refused")
    if audit.get("method_contract") != "Pilot->P1->C1->C2-B->C2-A-RP->T1->V1" or not audit.get("git_commit_sha") or not audit.get("worktree_clean"):
        blockers.append("formal_method_contract_or_clean_commit_missing")
    if not canonical_ready: blockers.extend(final.get("canonical_blockers", []) or ["c1_canonical_not_closed"])
    if not measurement.get("C1_EVIDENCE_BUNDLE_FROZEN"): blockers.append("c1_evidence_bundle_not_frozen")
    collection_closed = audit.get("collection_closure", {}).get("status") == "validated" and measurement.get("collection_window_closed") is True
    if not collection_closed: blockers.append("collection_closure_missing_or_invalid")
    if audit.get("formal_closeout_ready") is not True or final.get("formal_closeout_ready") is not True or audit.get("blockers") or final.get("blockers"):
        blockers.append("formal_audit_or_closeout_blocked")
    if not approved: blockers.append("formal_closeout_adjudication_missing_invalid_or_stale")
    evidence_ready = canonical_ready and collection_closed and not blockers
    c2b_baseline_ready = bool(measurement.get("C2B_BASELINE_INPUT_FROZEN")) and evidence_ready and any(str(row.get("c2_risk_model_eligible", "")).lower() in {"true", "1"} for row in worker_rows)
    c2b_blockers = [] if c2b_baseline_ready else ["q_gt_baseline_support_limited_or_not_frozen"]
    freeze = {"schema_version": "c1_evidence_freeze_manifest_v5", "method_contract": audit.get("method_contract", ""), "method_contract_version": method["contract_version"], "method_contract_sha256": method_sha, "profile_version": worker_manifest.get("profile_version", ""), "cohort_id": worker_manifest.get("cohort_id", ""), "git_commit_sha": audit.get("git_commit_sha", ""), "CALIBRATION_ENROLLMENT_CLOSED": collection_closed, "ALL_CALIBRATION_WORKERS_TERMINAL": not nonterminal_workers, "FINAL_POOLED_PROFILE_FROZEN": evidence_ready, "C1_COLLECTION_INCOMPLETE": not collection_closed, "C1_CANONICAL_CLOSED": canonical_ready, "C1_MEASUREMENT_FROZEN": evidence_ready, "C1_EVIDENCE_BUNDLE_FROZEN": bool(measurement.get("C1_EVIDENCE_BUNDLE_FROZEN")) and evidence_ready, "C2B_BASELINE_INPUT_FROZEN": c2b_baseline_ready, "Q_GT_FREEZE_STATUS": measurement.get("Q_GT_FREEZE_STATUS", "pending"), "R_PEER_FREEZE_STATUS": measurement.get("R_PEER_FREEZE_STATUS", "pending"), "F_STRUCT_FREEZE_STATUS": measurement.get("F_STRUCT_FREEZE_STATUS", "pending"), "R_LOO_MEDOID_STATUS": measurement.get("R_LOO_MEDOID_STATUS", "pending"), "R_LOO_STRICT_STATUS": measurement.get("R_LOO_STRICT_STATUS", "pending"), "rolling_activated": enrollment_summary.get("rolling_activated"), "N_late": enrollment_summary.get("N_late"), "C2B_DESIGN_READY": c2b_baseline_ready, "C2B_RISK_DESIGN_FROZEN": False, "C2B_DESIGN_FROZEN": False, "C2B_ASSIGNMENT_MATERIALIZED": False, "C2B_LAUNCH_READY": False, "routing_profile_frozen": False, "formal_closeout_ready": evidence_ready, "full_dependency_bundle_sha256": bundle_sha, "adjudication_sha256": sha256_file(args.adjudication_manifest), "blockers": blockers, "c2b_baseline_blockers": c2b_blockers, "dependencies": [{"role": role, "path": str(path.resolve()), "sha256": sha256_file(path)} for role, path in (("FORMAL_AUDIT", audit_path), ("CANONICAL_CLOSEOUT", final_path), ("MEASUREMENT_FREEZE", measurement_path), ("WORKER_PROFILE_MANIFEST", worker_manifest_path), ("WORKER_PROFILE", worker_profile_path), ("ENROLLMENT_REGISTRY", enrollment_registry_path), ("ENROLLMENT_REGISTRY_SUMMARY", enrollment_summary_path), ("W034_SENSITIVITY_FROZEN", w034_path), *profile_dependency_paths, ("ADJUDICATION", args.adjudication_manifest), ("METHOD_CONTRACT", METHOD_CONTRACT)) if path.is_file()]}
    freeze["state_machine"] = {name: bool(freeze[name]) for name in ("C1_COLLECTION_INCOMPLETE", "C1_CANONICAL_CLOSED", "C1_MEASUREMENT_FROZEN", "C2B_RISK_DESIGN_FROZEN", "C2B_DESIGN_FROZEN", "C2B_ASSIGNMENT_MATERIALIZED", "C2B_LAUNCH_READY")}
    (args.output_dir / "c1_evidence_freeze_manifest.json").write_text(json.dumps(freeze, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return {"day": 1, "phase": "measurement-freeze", "formal_closeout_ready": evidence_ready, "C1_CANONICAL_CLOSED": freeze["C1_CANONICAL_CLOSED"], "C1_MEASUREMENT_FROZEN": freeze["C1_MEASUREMENT_FROZEN"], "C2B_DESIGN_READY": freeze["C2B_DESIGN_READY"], "routing_profile_frozen": False, "blockers": blockers, "c2b_baseline_blockers": c2b_blockers}


def design_c2b(args: argparse.Namespace) -> dict[str, Any]:
    git_state = formal_git_state(_PROJECT_ROOT)
    if not git_state["clean"]:
        raise ValueError("formal C2-B design requires a committed clean worktree")
    closeout = json.loads(args.c1_closeout_summary.read_text(encoding="utf-8"))
    if closeout.get("schema_version") != "paper_a_c1_batch_analysis_snapshot_v1" or closeout.get("status") != "formal_design_eligible":
        raise ValueError("C2-B design requires a formal C1_A batch analysis snapshot")
    if closeout.get("method_contract_version") != load_method_contract()["contract_version"] or closeout.get("method_contract_sha256") != sha256_file(METHOD_CONTRACT):
        raise ValueError("C1_A batch snapshot method contract is stale")
    if closeout.get("C2B_DESIGN_INPUT_FROZEN_FROM_C1_A") is not True:
        raise ValueError("C1_A design input is not frozen")
    c1_inputs = _snapshot_dependencies(
        closeout, "WORKER_PROFILE", "COMPLETION", "Q_GT", "STRUCTURAL_EB",
        "MEASUREMENT_READINESS", "CANONICAL_ELIGIBILITY", "REFERENCE", "BUILDING",
    )
    evidence_envelope = _materialize_c2b_evidence_envelope(args)
    if not evidence_envelope["C2B_EVIDENCE_FROZEN"]:
        return {
            "day": 2, "phase": "risk-plan", "risk_pool_formal_ready": False,
            "assignment_materialized": False, "design": {"candidate_only": True, "n_feasible_candidate_designs": 0},
            "state_machine": {"C2B_EVIDENCE_FROZEN": False, "C2B_RISK_DESIGN_FROZEN": False},
            "blockers": ["c2b_evidence_freeze_envelope_incomplete"],
        }
    source_rows, holdout_rows = _read(args.source_split_evidence), _read(args.future_holdout_evidence)
    c2_images = _c2_source_images(source_rows)
    held_images = _future_heldout_images(holdout_rows)
    if c2_images & held_images:
        raise ValueError("C2 source split overlaps future holdout")
    risk = materialize_task_risk(
        args.inventory_csv, args.layout_dir, args.c1_task_feature_csv, args.output_dir,
        checkpoint=args.checkpoint,
        c1_freeze_manifest=args.c1_closeout_summary, feature_freeze_manifest=args.feature_freeze_manifest,
        building_registry_csv=args.building_registry, device=args.device,
    )
    risk["git_commit_sha"] = git_state["git_commit_sha"]
    risk["worktree_clean"] = True
    risk["c2b_evidence_freeze_envelope_sha256"] = sha256_file(args.output_dir / "c2b_evidence_freeze_envelope.json")
    (args.output_dir / "c2_task_risk.summary.json").write_text(json.dumps(risk, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    evidence = materialize_c2b_task_eligibility(
        args.inventory_csv, args.output_dir / "c2_task_risk_inventory.csv",
        args.source_split_evidence, args.future_holdout_evidence,
        args.history_overlap_audit, args.scope_registry, args.reference_registry,
        args.feature_freeze_manifest, args.output_dir / "c2b_task_eligibility_evidence.csv",
    )
    evidence_rows = _read(args.output_dir / "c2b_task_eligibility_evidence.csv")
    _write(args.output_dir / "c2_selected_task_review_queue.csv", [row for row in evidence_rows if row.get("assignment_eligible", "").lower() in {"true", "1"}])
    preliminary_ready = bool(risk.get("C2_TASK_FEATURES_FROZEN")) and bool(closeout.get("C2B_DESIGN_INPUT_FROZEN_FROM_C1_A"))
    parameter_summary: dict[str, Any] = {"formal_design_input_ready": False}
    profile_summary: dict[str, Any] = {"n_eligible": 0}
    derived_thresholds: dict[str, Any] = {}
    pool_gate: dict[str, Any] = {"frozen": False, "approved_thresholds": False, "observed": {}, "failures": ["design_inputs_not_ready"]}
    design_input_blocker = ""
    if preliminary_ready:
        worker_profile_path = c1_inputs["WORKER_PROFILE"]
        parameter_summary = materialize_design_parameters(
            c1_inputs["Q_GT"], args.output_dir / "c1_task_risk_reference.csv",
            c1_inputs["STRUCTURAL_EB"], c1_inputs["COMPLETION"],
            args.output_dir, worker_state_csv=worker_profile_path,
        )
        profile_summary = materialize_c2b_design_worker_profile(
            c1_inputs["COMPLETION"], worker_profile_path,
            args.output_dir / "c1_c2_design_parameters.csv", c1_inputs["MEASUREMENT_READINESS"],
            args.output_dir, c1_batch_snapshot=args.c1_closeout_summary,
        )
        if parameter_summary["formal_design_input_ready"] and profile_summary["n_eligible"]:
            if not args.threshold_formula_contract.exists():
                design_input_blocker = "threshold_formula_contract_missing"
            elif not args.capacity_manifest.exists():
                design_input_blocker = "capacity_manifest_missing_before_threshold_review"
            else:
                try:
                    validate_formula_contract(json.loads(args.threshold_formula_contract.read_text(encoding="utf-8")))
                    _require_current_subordinate(args.threshold_formula_contract, "threshold_formula_contract")
                except (OSError, ValueError, TypeError, json.JSONDecodeError):
                    design_input_blocker = "threshold_formula_contract_invalid"
            if not design_input_blocker:
                threshold_review_request = {
                    "schema_version": "paper_a_c2b_threshold_input_review_request_v1",
                    "formula_contract_sha256": sha256_file(args.threshold_formula_contract),
                    "c1_design_parameters_sha256": sha256_file(args.output_dir / "c1_c2_design_parameters.csv"),
                    "capacity_manifest_sha256": sha256_file(args.capacity_manifest),
                    "candidate_enumeration_started": False,
                    "required_approval_schema_version": "paper_a_c2b_threshold_input_approval_v1",
                }
                (args.output_dir / "c2b_threshold_input_review_request.json").write_text(
                    json.dumps(threshold_review_request, indent=2, sort_keys=True) + "\n", encoding="utf-8",
                )
                if args.threshold_input_approval.exists():
                    derived_thresholds = derive_threshold_manifest(
                        args.threshold_formula_contract,
                        args.output_dir / "c1_c2_design_parameters.csv",
                        args.capacity_manifest,
                        args.threshold_input_approval,
                        args.threshold_manifest,
                    )
                    pool_gate = _final_risk_pool_gate(evidence_rows, args.threshold_manifest)
    ready = preliminary_ready and bool(parameter_summary["formal_design_input_ready"]) and bool(profile_summary["n_eligible"]) and pool_gate["frozen"]
    risk["task_eligibility_evidence"] = evidence
    risk["formal_ready"] = ready
    risk["C2B_ELIGIBLE_RISK_POOL_FROZEN"] = ready
    risk["eligible_pool_gate"] = pool_gate
    risk["derived_threshold_manifest_sha256"] = sha256_file(args.threshold_manifest) if derived_thresholds else ""
    risk["threshold_formula_contract_sha256"] = sha256_file(args.threshold_formula_contract) if args.threshold_formula_contract.exists() else ""
    risk["threshold_input_approval_sha256"] = sha256_file(args.threshold_input_approval) if args.threshold_input_approval.exists() else ""
    risk["state_machine"]["C2B_ELIGIBLE_RISK_POOL_FROZEN"] = ready
    risk["state_machine"]["C2B_RISK_DESIGN_FROZEN"] = ready
    (args.output_dir / "c2_task_risk.summary.json").write_text(json.dumps(risk, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    design_summary: dict[str, Any] = {"candidate_only": True, "n_feasible_candidate_designs": 0}
    if ready:
        worker_profile = args.output_dir / "c2b_design_worker_profile.csv"
        design_manifest = c2b.build_candidate_design_manifest(
            args.output_dir / "c2b_task_eligibility_evidence.csv", worker_profile,
            args.c1_closeout_summary, args.output_dir / "c2b_candidate_design_manifest.json",
            threshold_manifest=args.threshold_manifest,
            risk_summary=args.output_dir / "c2_task_risk.summary.json",
        )
        design_summary = c2b.enumerate_candidates(
            args.output_dir / "c2b_task_eligibility_evidence.csv", worker_profile,
            design_manifest, args.output_dir / "c2_candidates",
            c1_closeout_summary=args.c1_closeout_summary,
            risk_summary=args.output_dir / "c2_task_risk.summary.json",
            threshold_manifest=args.threshold_manifest,
            eligibility_evidence_csv=args.output_dir / "c2b_task_eligibility_evidence.csv",
        )
    if ready:
        blockers = []
    elif design_input_blocker:
        blockers = [design_input_blocker]
    elif preliminary_ready and parameter_summary["formal_design_input_ready"] and profile_summary["n_eligible"] and not args.threshold_input_approval.exists():
        blockers = ["threshold_input_approval_missing_before_candidate_enumeration"]
    elif preliminary_ready and (not parameter_summary["formal_design_input_ready"] or not profile_summary["n_eligible"]):
        blockers = ["c1_design_parameters_or_worker_profile_insufficient"]
    else:
        blockers = ["risk_or_task_eligibility_pool_insufficient"]
    return {"day": 2, "phase": "risk-plan", "risk_pool_formal_ready": ready, "assignment_materialized": False, "design": design_summary, "evidence_envelope": evidence_envelope, "state_machine": risk["state_machine"], "blockers": blockers}


def _write_c2b_import(output_dir: Path, distribution: list[dict[str, Any]], *, batch_id: str, selected_design_sha: str) -> Path:
    selected = {row["task_id"]: row for row in distribution}
    imports = [{
        "data": {"image": row["image_path"], "title": task_id, "planned_task_id": task_id, "c2b_batch_id": batch_id, "selected_design_sha": selected_design_sha},
        "meta": {"round_id": "C2-B", "batch_id": batch_id, "selected_design_sha": selected_design_sha},
    } for task_id, row in sorted(selected.items())]
    path = output_dir / "label_studio_import_C2B.json"
    path.write_text(json.dumps(imports, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path


def _build_c2b_batch_b(args: argparse.Namespace) -> dict[str, Any]:
    if not all(getattr(args, name, None) for name in ("batch_a_launch_report", "batch_a_assignment", "batch_worker_profile", "p1_admission_evidence")):
        raise ValueError("C2B_BATCH_B requires Batch A report/assignment, C1-B worker profile, and P1 admission evidence")
    batch_a = _require_current_subordinate(args.batch_a_launch_report, "batch_a_launch_report")
    if batch_a.get("assignment_batch_id") != "C2B_BATCH_A" or not batch_a.get("C2B_ASSIGNMENT_BATCH_A_MATERIALIZED"):
        raise ValueError("Batch B requires a frozen Batch A launch report")
    roster = _require_current_subordinate(args.c2b_roster_manifest, "batch_b_roster")
    if roster.get("worker_profile_sha256") != sha256_file(args.batch_worker_profile):
        raise ValueError("Batch B roster is not bound to the submitted C1-B worker profile")
    profiles = _read(args.batch_worker_profile)
    p1 = {row.get("worker_id", ""): row for row in _read(args.p1_admission_evidence)}
    workers = []
    for row in profiles:
        worker = row.get("worker_id", "")
        if not worker:
            continue
        if row.get("schema_version") != "worker_profile_v2" or row.get("enrollment_batch") != "late_entry" or row.get("completion_status") != "completed" or not _truth(row.get("c2_risk_model_eligible")):
            continue
        if str(p1.get(worker, {}).get("admission_status", "")).lower() not in {"pass", "admitted", "approved"}:
            raise ValueError(f"Batch B worker lacks passed P1 evidence:{worker}")
        workers.append(worker)
    if not workers:
        raise ValueError("Batch B has no P1-passed, completed C1-B formal roster workers")
    base = _read(args.batch_a_assignment)
    if not base or any(row.get("assignment_batch_id") not in {"", "C2B_BATCH_A"} for row in base):
        raise ValueError("Batch A assignment is not a stable C2B_BATCH_A artifact")
    design_sha = str(batch_a.get("selected_design_sha", ""))
    if not design_sha:
        raise ValueError("Batch A launch report lacks selected design SHA")
    anchors = {row["task_id"]: row for row in base if row.get("c2_component") == "common_anchor"}
    bridges = {row["task_id"]: row for row in base if row.get("c2_component") == "diverse_bridge"}
    bridge_per_worker = max((sum(row.get("c2_component") == "diverse_bridge" for row in base if row.get("worker_id") == worker) for worker in {row.get("worker_id") for row in base}), default=0)
    if not anchors or not bridges or bridge_per_worker < 1:
        raise ValueError("Batch A does not contain a frozen common-anchor and bridge generator")
    bridge_ids = sorted(bridges)
    rows: list[dict[str, Any]] = []
    for worker in sorted(set(workers)):
        for row in anchors.values(): rows.append({**row, "worker_id": worker, "assignment_batch_id": "C2B_BATCH_B"})
        start = int(hashlib.sha256(f"{design_sha}:{worker}".encode("utf-8")).hexdigest(), 16) % len(bridge_ids)
        for offset in range(bridge_per_worker):
            row = bridges[bridge_ids[(start + offset) % len(bridge_ids)]]
            rows.append({**row, "worker_id": worker, "assignment_batch_id": "C2B_BATCH_B"})
    if len({(row["worker_id"], row["task_id"]) for row in rows}) != len(rows):
        raise ValueError("Batch B bridge replay generated duplicate worker-task rows")
    capacities = {row.get("worker_id", ""): int(float(row.get("c2b_capacity", "0"))) for row in _read(args.capacity_manifest)}
    if any(sum(row["worker_id"] == worker for row in rows) > capacities.get(worker, 0) for worker in workers):
        raise ValueError("Batch B assignment exceeds frozen capacity")
    args.output_dir.mkdir(parents=True, exist_ok=True)
    assignment_path = args.output_dir / "assignment_manifest_C2B.csv"; _write(assignment_path, rows)
    _write(args.output_dir / "worker_distribution_C2B.csv", rows)
    worker_dir = args.output_dir / "worker_facing_distribution_C2B"; worker_dir.mkdir(parents=True, exist_ok=True)
    for worker in sorted(set(workers)): _write(worker_dir / f"worker_{worker}_C2B.csv", [row for row in rows if row["worker_id"] == worker])
    import_path = _write_c2b_import(args.output_dir, rows, batch_id="C2B_BATCH_B", selected_design_sha=design_sha)
    report = {
        "schema_version": "paper_a_c2b_launch_ready_report_v3", "contract_role": "generated_subordinate", **_method_identity(),
        "assignment_batch_id": "C2B_BATCH_B", "selected_design_sha": design_sha, "assignment_sha256": sha256_file(assignment_path), "import_sha256": sha256_file(import_path),
        "C2B_ASSIGNMENT_BATCH_A_MATERIALIZED": True, "C2B_ASSIGNMENT_BATCH_B_MATERIALIZED": True, "C2B_LAUNCH_READY": True,
        "automatic_label_studio_import": False, "n_assignments": len(rows), "n_workers": len(workers),
        "dependencies": [{"role": role, "path": str(path.resolve()), "sha256": sha256_file(path)} for role, path in (("BATCH_A_LAUNCH_REPORT", args.batch_a_launch_report), ("BATCH_A_ASSIGNMENT", args.batch_a_assignment), ("BATCH_B_ROSTER", args.c2b_roster_manifest), ("BATCH_B_PROFILE", args.batch_worker_profile), ("P1_ADMISSION", args.p1_admission_evidence), ("METHOD_CONTRACT", METHOD_CONTRACT))],
    }
    (args.output_dir / "c2b_launch_ready_report.json").write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return {"day": 2, "phase": "build", **report}


def build_c2b(args: argparse.Namespace) -> dict[str, Any]:
    if not formal_git_state(_PROJECT_ROOT)["clean"]:
        raise ValueError("formal C2-B build requires a committed clean worktree")
    if getattr(args, "assignment_batch", "C2B_BATCH_A") == "C2B_BATCH_B":
        return _build_c2b_batch_b(args)
    closeout = json.loads(args.c1_closeout_summary.read_text(encoding="utf-8"))
    risk = json.loads(args.risk_summary.read_text(encoding="utf-8"))
    if closeout.get("schema_version") != "paper_a_c1_batch_analysis_snapshot_v1" or closeout.get("status") != "formal_design_eligible" or not closeout.get("C2B_DESIGN_INPUT_FROZEN_FROM_C1_A"):
        raise ValueError("C1_A Batch A design input is not formally frozen")
    if closeout.get("method_contract_version") != load_method_contract()["contract_version"] or closeout.get("method_contract_sha256") != sha256_file(METHOD_CONTRACT):
        raise ValueError("Batch A snapshot method contract is stale")
    _require_current_subordinate(args.c2b_roster_manifest, "c2b_roster")
    roster = json.loads(args.c2b_roster_manifest.read_text(encoding="utf-8"))
    if roster.get("c1_batch_snapshot_sha256") != sha256_file(args.c1_closeout_summary):
        raise ValueError("formal C2-B roster is not bound to the C1_A snapshot")
    validate_generated_subordinate(risk, role="c2_task_risk")
    if not risk.get("formal_ready") or not risk.get("state_machine", {}).get("C2B_RISK_DESIGN_FROZEN"):
        raise ValueError("C2 task risk is not formally frozen")
    if risk.get("derived_threshold_manifest_sha256") != sha256_file(args.threshold_manifest):
        raise ValueError("C2-B derived threshold manifest is stale or unbound")
    threshold_payload = json.loads(args.threshold_manifest.read_text(encoding="utf-8"))
    validate_generated_subordinate(threshold_payload, role="derived_threshold_manifest")
    if (
        threshold_payload.get("schema_version") != "paper_a_c2b_design_selection_thresholds_v2"
        or threshold_payload.get("derivation", {}).get("capacity_manifest_sha256") != sha256_file(args.capacity_manifest)
    ):
        raise ValueError("C2-B thresholds were not mechanically derived from the frozen capacity")
    envelope_path = args.risk_summary.parent / "c2b_evidence_freeze_envelope.json"
    if not envelope_path.exists() or risk.get("c2b_evidence_freeze_envelope_sha256") != sha256_file(envelope_path):
        raise ValueError("C2 task risk lacks the bound evidence-freeze envelope")
    envelope = json.loads(envelope_path.read_text(encoding="utf-8"))
    if envelope.get("C2B_EVIDENCE_FROZEN") is not True:
        raise ValueError("C2-B evidence freeze is not ready")
    source_approval = _require_approval(args.source_split_approval, args.source_split_evidence, "source_split_evidence_sha256")
    holdout_approval = _require_approval(args.future_holdout_approval, args.future_holdout_evidence, "future_holdout_evidence_sha256")
    if (
        source_approval.get("selected_proposal_id") != envelope.get("selected_proposal_id")
        or holdout_approval.get("selected_proposal_id") != envelope.get("selected_proposal_id")
        or sha256_file(args.source_split_approval) != envelope.get("artifacts", {}).get("source_split_approval", {}).get("sha256")
        or sha256_file(args.future_holdout_approval) != envelope.get("artifacts", {}).get("future_holdout_approval", {}).get("sha256")
    ):
        raise ValueError("source/holdout approvals do not match the frozen evidence envelope")
    task_approval = _require_approval(
        args.selected_task_reference_manifest, args.task_eligibility_evidence,
        "task_eligibility_evidence_sha256",
    )
    if task_approval.get("reference_registry_sha256") != sha256_file(args.reference_registry):
        raise ValueError("selected_task_reference_approval_invalid_or_stale:reference_registry_sha256")
    if risk.get("output_inventory_sha256") != sha256_file(args.task_pool):
        raise ValueError("C2 task pool is not the inventory bound by the frozen risk summary")
    capacities = {row.get("worker_id", ""): row for row in _read(args.capacity_manifest)}
    if not capacities or len(capacities) != len(_read(args.capacity_manifest)):
        raise ValueError("C2-B capacity manifest requires unique worker rows")
    _require_current_subordinate(args.design_manifest, "candidate_design")
    _require_current_subordinate(args.selected_design_approval, "selected_design_approval")
    design = c2b.materialize_approved_assignment(
        args.candidate_dir, args.design_manifest, args.threshold_manifest,
        args.selected_design_approval, args.selected_task_reference_manifest,
        args.task_eligibility_evidence, args.c1_closeout_summary,
        args.risk_summary, args.output_dir,
    )
    assignment_path = args.output_dir / "assignment_manifest_C2B.csv"
    assignments, tasks = _read(assignment_path), {row["task_id"]: row for row in _read(args.task_pool)}
    assignments = [{**row, "assignment_batch_id": "C2B_BATCH_A"} for row in assignments]
    _write(assignment_path, assignments)
    assigned_by_worker = Counter(row["worker_id"] for row in assignments)
    for worker, count in assigned_by_worker.items():
        try:
            available = int(float(capacities[worker]["c2b_capacity"]))
        except (KeyError, TypeError, ValueError):
            raise ValueError(f"C2-B capacity is missing or invalid for worker {worker}")
        if count > available:
            raise ValueError(f"C2-B assignment exceeds frozen capacity for worker {worker}")
    distribution = [{
        **row,
        "image_path": row.get("image_path") or tasks.get(row["task_id"], {}).get("image_path") or tasks.get(row["task_id"], {}).get("source_path", ""),
    } for row in assignments]
    if any(not row.get("image_path") for row in distribution):
        raise ValueError("C2-B assigned task lacks a materializable image path")
    def resolvable_image(value: str) -> bool:
        value = str(value).strip()
        return value.startswith(("http://", "https://", "/data/")) or Path(value).is_file() or (_PROJECT_ROOT / value).is_file()
    if any(not resolvable_image(row["image_path"]) for row in distribution):
        raise ValueError("C2-B assigned task image path is not resolvable")
    _write(args.output_dir / "worker_distribution_C2B.csv", distribution)
    worker_dir = args.output_dir / "worker_facing_distribution_C2B"; worker_dir.mkdir(parents=True, exist_ok=True)
    for worker in sorted({row["worker_id"] for row in distribution}):
        _write(worker_dir / f"worker_{worker}_C2B.csv", [row for row in distribution if row["worker_id"] == worker])
    selected_design_sha = sha256_file(args.selected_design_approval)
    import_path = _write_c2b_import(args.output_dir, distribution, batch_id="C2B_BATCH_A", selected_design_sha=selected_design_sha)
    imports = json.loads(import_path.read_text(encoding="utf-8"))
    support = Counter(row["task_id"] for row in assignments)
    assignment_identities = {(row["worker_id"], row["task_id"]) for row in assignments}
    distribution_identities = {(row["worker_id"], row["task_id"]) for row in distribution}
    explicit_gt_count = sum(_truth(tasks.get(row["task_id"], {}).get("is_gt")) or str(tasks.get(row["task_id"], {}).get("task_role", "")).upper() == "GT" or str(tasks.get(row["task_id"], {}).get("dataset_group", "")).upper() == "GT" for row in distribution)
    worker_files = sorted(worker_dir.glob("worker_*_C2B.csv"))
    method_sha = sha256_file(METHOD_CONTRACT)
    audit = {
        "schema_version": "paper_a_c2b_launch_ready_report_v3", "contract_role": "generated_subordinate", "method_contract": risk["method_contract"], "method_contract_version": load_method_contract()["contract_version"], "method_contract_sha256": method_sha, "git_commit_sha": risk["git_commit_sha"], "assignment_batch_id": "C2B_BATCH_A", "selected_design_sha": selected_design_sha,
        "assignment_sha256": sha256_file(assignment_path), "worker_distribution_sha256": sha256_file(args.output_dir / "worker_distribution_C2B.csv"), "worker_distribution_bundle_sha256": _aggregate_sha(_manifest_rows(worker_files)), "import_sha256": sha256_file(import_path),
        "n_assignments": len(assignments), "n_workers": len({row["worker_id"] for row in assignments}),
        "n_tasks": len(support), "min_task_support": min(support.values(), default=0),
        "duplicate_worker_task_count": len(assignments) - len({(row["worker_id"], row["task_id"]) for row in assignments}),
        "import_smoke_passed": bool(imports) and all(item.get("data", {}).get("image") for item in json.loads(import_path.read_text(encoding="utf-8"))),
        "assignment_distribution_consistent": assignment_identities == distribution_identities,
        "gt_isolated_from_worker_import": explicit_gt_count == 0,
        "image_paths_resolvable": all(resolvable_image(row["image_path"]) for row in distribution),
        "capacity_manifest_sha256": sha256_file(args.capacity_manifest),
        "automatic_label_studio_import": False,
        "dependencies": [{"role": role, "path": str(path.resolve()), "sha256": sha256_file(path)} for role, path in (("C1_A_SNAPSHOT", args.c1_closeout_summary), ("C2B_ROSTER", args.c2b_roster_manifest), ("C2_RISK", args.risk_summary), ("THRESHOLDS", args.threshold_manifest), ("CAPACITY", args.capacity_manifest), ("SELECTED_DESIGN_APPROVAL", args.selected_design_approval), ("METHOD_CONTRACT", METHOD_CONTRACT))],
    }
    audit["launch_ready"] = bool(design.get("launch_ready")) and audit["duplicate_worker_task_count"] == 0 and audit["import_smoke_passed"] and audit["assignment_distribution_consistent"] and audit["gt_isolated_from_worker_import"] and audit["image_paths_resolvable"]
    audit["C2B_LAUNCH_READY"] = audit["launch_ready"]
    audit["C2B_ASSIGNMENT_BATCH_A_MATERIALIZED"] = bool(assignments)
    audit["C2B_ASSIGNMENT_BATCH_B_MATERIALIZED"] = False
    audit["state_machine"] = {**design.get("state_machine", {}), "C2B_ASSIGNMENT_MATERIALIZED": bool(assignments), "C2B_ASSIGNMENT_BATCH_A_MATERIALIZED": bool(assignments), "C2B_ASSIGNMENT_BATCH_B_MATERIALIZED": False, "C2B_LAUNCH_READY": audit["launch_ready"]}
    (args.output_dir / "c2b_launch_ready_report.json").write_text(json.dumps(audit, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return {"day": 2, "phase": "build", "state_machine": design.get("state_machine", {}), **audit}


def bind_c2b_runtime_mapping(args: argparse.Namespace) -> dict[str, Any]:
    """Bind a manual Label Studio import export to the frozen planned task IDs."""
    report = _require_current_subordinate(args.launch_report, "c2b_launch_report")
    assignments = _read(args.worker_distribution)
    imports = json.loads(args.planned_import.read_text(encoding="utf-8"))
    expected = {
        str(item.get("data", {}).get("planned_task_id", "")): item
        for item in imports if isinstance(item, dict) and item.get("data", {}).get("planned_task_id")
    }
    if not expected or set(expected) != {row.get("task_id", "") for row in assignments}:
        raise ValueError("planned import does not exactly cover the frozen worker distribution")
    runtime_payload = json.loads(args.runtime_export.read_text(encoding="utf-8"))
    runtime_rows = runtime_payload if isinstance(runtime_payload, list) else runtime_payload.get("tasks", runtime_payload.get("data", []))
    if not isinstance(runtime_rows, list):
        raise ValueError("runtime export must contain a task list")
    runtime_by_planned: dict[str, dict[str, Any]] = {}
    runtime_ids: set[str] = set()
    for row in runtime_rows:
        if not isinstance(row, dict):
            continue
        data = row.get("data", {}) if isinstance(row.get("data", {}), dict) else {}
        planned = str(data.get("planned_task_id", ""))
        runtime_id = str(row.get("id", row.get("task_id", "")))
        if not planned:
            continue
        if planned in runtime_by_planned or not runtime_id or runtime_id in runtime_ids:
            raise ValueError("runtime export has duplicate planned or runtime task IDs")
        if planned not in expected or data.get("selected_design_sha") != report.get("selected_design_sha") or data.get("c2b_batch_id") != report.get("assignment_batch_id"):
            raise ValueError("runtime export task is outside the frozen batch/design identity")
        if str(data.get("dataset_group", "")).upper() == "GT" or str(data.get("task_role", "")).upper() == "GT":
            raise ValueError("GT task leaked into runtime C2-B import")
        runtime_by_planned[planned] = row; runtime_ids.add(runtime_id)
    if set(runtime_by_planned) != set(expected):
        raise ValueError("runtime export is missing or adds planned C2-B tasks")
    bindings = [{
        "worker_id": row["worker_id"], "planned_task_id": row["task_id"],
        "runtime_task_id": str(runtime_by_planned[row["task_id"]].get("id", runtime_by_planned[row["task_id"]].get("task_id", ""))),
        "assignment_batch_id": report["assignment_batch_id"], "selected_design_sha": report["selected_design_sha"],
    } for row in assignments]
    if len({(row["worker_id"], row["runtime_task_id"]) for row in bindings}) != len(bindings):
        raise ValueError("runtime mapping is not one-to-one within worker distributions")
    args.output_dir.mkdir(parents=True, exist_ok=True)
    mapping = args.output_dir / "c2b_runtime_task_mapping.csv"; _write(mapping, bindings)
    audit = {
        "schema_version": "paper_a_c2b_runtime_mapping_audit_v1", "contract_role": "generated_subordinate", **_method_identity(),
        "assignment_batch_id": report["assignment_batch_id"], "selected_design_sha": report["selected_design_sha"],
        "runtime_mapping_sha256": sha256_file(mapping), "runtime_task_count": len(runtime_by_planned), "worker_task_binding_count": len(bindings),
        "one_to_one": True, "gt_isolated": True, "open_tasks_allowed": True,
        "dependencies": [{"role": role, "path": str(path.resolve()), "sha256": sha256_file(path)} for role, path in (("LAUNCH_REPORT", args.launch_report), ("WORKER_DISTRIBUTION", args.worker_distribution), ("PLANNED_IMPORT", args.planned_import), ("RUNTIME_EXPORT", args.runtime_export), ("METHOD_CONTRACT", METHOD_CONTRACT))],
    }
    (args.output_dir / "c2b_worker_task_binding_audit.json").write_text(json.dumps(audit, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return audit


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Paper A C1 closeout and C2-B launch")
    sub = parser.add_subparsers(dest="command", required=True)

    def add_c1_inputs(command: argparse.ArgumentParser, *, active_name: str) -> None:
        command.add_argument("--export-dir", action="append", type=Path, required=True)
        command.add_argument(active_name, type=Path, required=True)
        for name in ("manual-assignment", "semi-assignment", "worker-distribution", "gt-export"):
            command.add_argument(f"--{name}", type=Path, required=True)
        command.add_argument("--p1-closeout-dir", type=Path, required=True)
        command.add_argument("--p1-integrity-dir", type=Path)
        command.add_argument("--output-root", type=Path, required=True)
        command.add_argument("--c1-preannotation-feature-csv", type=Path)
        command.add_argument("--authorized-reassignment-manifest", type=Path)
        command.add_argument("--late-entry-assignment-manifest", type=Path)
        command.add_argument("--calibration-enrollment-registry", type=Path)
        command.add_argument("--w034-active-time-validation-manifest", type=Path)
        command.add_argument("--building-registry", type=Path)

    rehearsal = sub.add_parser("rehearse-c1")
    add_c1_inputs(rehearsal, active_name="--active-log")
    rehearsal.add_argument("--annotation-independence-disposition", dest="independence_disposition", type=Path)
    for name in ("duplicate-adjudication", "structural-disposition", "project-independence-disposition", "scope-adjudication", "reference-amendment", "outside-assignment-disposition", "completion-disposition"):
        rehearsal.add_argument(f"--{name}", type=Path)

    static = sub.add_parser("prepare-c2b-static")
    for name in ("p1-closeout-dir", "inventory-csv", "legacy-manifest", "reference-dir", "layout-dir", "checkpoint", "config", "feature-audit-threshold-manifest", "output-dir"):
        static.add_argument(f"--{name}", type=Path, required=True)
    static.add_argument("--c1-assignment", action="append", type=Path, required=True)
    static.add_argument("--p1-initialization-import", action="append", type=Path, required=True)
    static.add_argument("--building-registry", type=Path)
    static.add_argument("--device", default="cuda:0")

    expand = sub.add_parser("expand-building-registry")
    expand.add_argument("--inventory-csv", type=Path, required=True)
    expand.add_argument("--approved-scene-mapping", type=Path, required=True)
    expand.add_argument("--output-csv", type=Path, required=True)

    contract_check = sub.add_parser("check-command-contract")
    contract_check.add_argument("--runbook", type=Path, required=True)

    preflight = sub.add_parser("preflight-calibration")
    for name in ("static-dir", "threshold-manifest", "feature-audit-threshold-manifest", "output"):
        preflight.add_argument(f"--{name}", type=Path, required=True)

    freeze = sub.add_parser("freeze-c1")
    freeze.add_argument("--source-live-root", type=Path, required=True)
    freeze.add_argument("--frozen-root", type=Path, required=True)
    freeze.add_argument("--collection-cutoff-server-time", required=True)
    freeze.add_argument("--operator", required=True)
    freeze.add_argument("--late-submission-policy", required=True)
    freeze.add_argument("--active-log-freeze-manifest", type=Path, required=True)
    freeze.add_argument("--collection-closure-manifest", type=Path, required=True)
    freeze.add_argument("--export-dir", action="append", type=Path, required=True)
    freeze.add_argument("--manual-assignment", type=Path, required=True)
    freeze.add_argument("--semi-assignment", type=Path, required=True)

    audit = sub.add_parser("audit-c1")
    add_c1_inputs(audit, active_name="--active-log")
    audit.add_argument("--c1-active-log-freeze-manifest", type=Path, required=True)
    audit.add_argument("--collection-closure-manifest", type=Path, required=True)
    audit.add_argument("--annotation-independence-disposition", dest="independence_disposition", type=Path)
    for name in ("duplicate-adjudication", "structural-disposition", "project-independence-disposition", "scope-adjudication", "reference-amendment", "outside-assignment-disposition", "completion-disposition"):
        audit.add_argument(f"--{name}", type=Path, required=True)

    finalize = sub.add_parser("finalize-c1")
    finalize.add_argument("--output-dir", type=Path, required=True)
    finalize.add_argument("--adjudication-manifest", type=Path, required=True)

    batch_freeze = sub.add_parser("freeze-c1-batch")
    batch_freeze.add_argument("--c1-output-dir", type=Path, required=True)
    batch_freeze.add_argument("--batch-scope-manifest", type=Path, required=True)
    batch_freeze.add_argument("--authorized-reassignment-manifest", type=Path)
    batch_freeze.add_argument("--output", type=Path, required=True)

    plan = sub.add_parser("design-c2b")
    for name in ("c1-closeout-summary", "inventory-csv", "layout-dir", "c1-task-feature-csv", "checkpoint", "building-registry", "source-split-evidence", "source-split-approval", "future-holdout-evidence", "future-holdout-approval", "history-overlap-audit", "scope-registry", "reference-registry", "feature-freeze-manifest", "static-freeze-manifest", "threshold-formula-contract", "threshold-input-approval", "threshold-manifest", "capacity-manifest", "output-dir"):
        plan.add_argument(f"--{name}", type=Path, required=True)
    plan.add_argument("--device", default="auto")

    build = sub.add_parser("build-c2b")
    for name in ("c1-closeout-summary", "risk-summary", "task-pool", "task-eligibility-evidence", "candidate-dir", "design-manifest", "threshold-manifest", "source-split-evidence", "source-split-approval", "future-holdout-evidence", "future-holdout-approval", "reference-registry", "selected-task-reference-manifest", "selected-design-approval", "capacity-manifest", "output-dir"):
        build.add_argument(f"--{name}", type=Path, required=True)
    build.add_argument("--c2b-roster-manifest", type=Path, required=True)
    build.add_argument("--assignment-batch", choices=("C2B_BATCH_A", "C2B_BATCH_B"), default="C2B_BATCH_A")
    for name in ("batch-a-launch-report", "batch-a-assignment", "batch-worker-profile", "p1-admission-evidence"):
        build.add_argument(f"--{name}", type=Path)

    runtime = sub.add_parser("bind-c2b-runtime-mapping")
    for name in ("launch-report", "worker-distribution", "planned-import", "runtime-export", "output-dir"):
        runtime.add_argument(f"--{name}", type=Path, required=True)
    args = parser.parse_args(argv)
    command = {
        "prepare-c2b-static": prepare_c2b_static,
        "expand-building-registry": expand_building_registry,
        "check-command-contract": check_command_contract,
        "preflight-calibration": preflight_calibration,
        "rehearse-c1": rehearse_c1,
        "freeze-c1": freeze_c1,
        "freeze-c1-batch": freeze_c1_batch,
        "audit-c1": audit_c1,
        "finalize-c1": finalize_c1,
        "design-c2b": design_c2b,
        "build-c2b": build_c2b,
        "bind-c2b-runtime-mapping": bind_c2b_runtime_mapping,
    }[args.command]
    print(json.dumps(command(args), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

