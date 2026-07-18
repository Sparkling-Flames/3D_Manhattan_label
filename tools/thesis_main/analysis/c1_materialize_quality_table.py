from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path
from typing import Any

import pandas as pd

_PROJECT_ROOT = Path(__file__).resolve().parents[3]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from tools.thesis_main.analysis.c1_live_collection_monitor import bool_text, read_csv, safe, truthy, write_csv, write_json
from tools.thesis_main.analysis.vfinal_artifact_utils import dependency_bundle, eligible_independent_evidence, sha256_file
from tools.thesis_main.registry.materialize_meta_label_consensus_summary import build_summary
from tools.thesis_main.registry.materialize_meta_label_three_state_sidecars import materialize_meta_label_three_state
from tools.thesis_main.analysis.failure_disposition import c1_failure_fields

DEFAULT_INPUT = Path("analysis_results/calibration_c1_closeout/c1_canonical_annotations.csv")
DEFAULT_OUTPUT_DIR = Path("analysis_results/calibration_c1_closeout")
DEFAULT_CORE_DRAFT = Path("analysis_results/calibration_rebuild_20260702/calibration_core_draft_v3_1.csv")
RULE_VERSION = "c1_quality_table_v3"

QUALITY_FIELDS = [
    "source_artifact",
    "source_sha256",
    "dependency_bundle_id",
    "dependency_bundle_json",
    "stage",
    "pool",
    "validity_status",
    "rule_version",
    "interpretation_allowed",
    "round_id",
    "task_id",
    "base_task_id",
    "dataset_group",
    "scene_label",
    "scene_bin",
    "scene_stratum",
    "room_type",
    "risk_bucket",
    "condition",
    "worker_id",
    "annotator_id",
    "project_id",
    "ls_runtime_task_id",
    "annotation_id",
    "canonical_annotation_id",
    "response_hash",
    "annotation_version_id",
    "task_final_scope",
    "task_scope_resolution_status",
    "task_oos_subtype",
    "task_outcome_adjudication_status",
    "reference_identity",
    "scope_reference_mode",
    "geometry_reference_mode",
    "reference_worker_excluded",
    "reference_evidence_status",
    "worker_scope_response",
    "worker_scope_outcome",
    "geometry_reference_status",
    "process_evaluable",
    "process_failure_observed",
    "process_failure_subfamily",
    "family",
    "subfamily",
    "response_type",
    "scope",
    "difficulty",
    "model_issue",
    "model_issue_primary",
    "n_corners",
    "geometry_hash",
    "geometry_valid",
    "geometry_score_gate_passed",
    "geometry_component_evaluable",
    "geometry_failure_threshold_status",
    "geometry_failure_family_evaluable",
    "geometry_failure_observed",
    "quality_metric_name",
    "quality_metric_value",
    "geometry_metric_direction",
    "geometry_normalization_rule",
    "geometry_component_name",
    "geometry_score_status",
    "active_time",
    "active_time_source",
    "primary_active_time_eligible",
    "sensitivity_active_time_eligible",
    "unassigned_active_time_seconds",
    "unknown_annotation_event_count",
    "unknown_annotation_session_count",
    "known_unknown_oscillation_flag",
    "unassigned_audit_present",
    "unassigned_active_time_exclusion_reason",
    "active_time_integrity_status",
    "system_collection_issue",
    "active_time_exclusion_reason",
    "audit_only",
    "semi_response_type",
    "semi_evidence_status",
    "semi_issue_recognition_evaluable",
    "semi_geometry_correction_evaluable",
    "semi_correction_failure_observed",
    "undercoverage_risk_level",
    "undercoverage_expert_verdict",
    "undercoverage_evidence_status",
    "undercoverage_response",
    "undercoverage_subfamily",
    "undercoverage_failure_observed",
    "used_for_r_u",
    "used_for_r_u_source_status",
    "r_u_evidence_included",
    "r_u_evidence_classification",
    "r_u_evidence_exclusion_reason",
    "r_u_score_or_outcome",
    "r_u_metric_name",
    "r_u_metric_value",
    "r_u_metric_direction",
    "r_u_normalization_rule",
    "r_u_score_status",
    "r_u_score_source",
    "r_u_reference_mode",
    "r_u_reference_identity",
    "r_u_reference_sha256",
    "r_u_reference_excludes_worker",
    "r_u_reference_support",
    "duplicate_review_status",
    "duplicate_decision",
    "process_disposition",
    "timing_disposition",
    "reviewed_by",
    "reviewed_at",
    "used_for_rq2",
    "assigned_expected",
    "outside_assignment_submission",
    "duplicate_worker_task_submission",
    "eligible_independent_evidence",
    "canonical_source_sha256",
    "canonical_eligibility_status",
    "canonical_eligibility_reason",
    "schema_interpretable",
    "schema_family",
    "schema_error",
    "difficulty_present",
    "model_issue_present",
    "choice_map_json",
    "canonical_registry_sha256",
    "source_export_sha256",
    "annotation_created_at",
    "created_at",
    "arrived_at",
    "raw_result_json",
    "raw_response",
    "harmonized_state",
    "assertion_source",
    "ui_schema_version",
    "model_artifact_id",
    "provenance_status",
    "original_provenance_status",
    "retrospective_amendment_status",
    "effective_provenance_status",
    "harmonization_validity_status",
    "harmonization_reason",
    "retrospective_amendment_source",
    "retrospective_amendment_sha256",
    "prediction_selection_status",
    "exclusion_reason",
    "independence_status",
    "independence_audit_identity",
    "parent_annotation_id",
    "parent_owner_id",
    "parent_cross_owner",
    "parent_derived",
    "copy_risk_status",
    "failure_attribution",
    "incident_id",
    "incident_evidence_status",
    "worker_caused_structural_failure",
    "policy_failure",
    "external_system_failure",
    "structural_failure_evaluable",
    "worker_reliability_eligible",
]

FAILURE_FIELDS = [
    "failure_attribution",
    "incident_id",
    "incident_evidence_status",
    "worker_caused_structural_failure",
    "policy_failure",
    "external_system_failure",
    "structural_failure_evaluable",
    "worker_reliability_eligible",
]


def _c1_failure_fields(row: dict[str, Any]) -> dict[str, Any]:
    if not any(safe(row.get(field)) for field in ("failure_attribution", "incident_id", "incident_evidence_status")):
        row = {**row, "failure_attribution": "not_evaluable", "incident_evidence_status": "not_evaluable"}
    return c1_failure_fields(row)


def _tokens(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, list):
        return ";".join(safe(v) for v in value if safe(v))
    text = safe(value)
    if not text:
        return ""
    try:
        parsed = json.loads(text)
    except Exception:
        return text.replace(",", ";")
    return _tokens(parsed)


def _choice(row: dict[str, Any], name: str) -> str:
    if safe(row.get(name)):
        return _tokens(row.get(name))
    for source in ("choice_map_json", "choice_map", "quality_flags_json"):
        raw = safe(row.get(source))
        if not raw:
            continue
        try:
            payload = json.loads(raw)
        except Exception:
            continue
        if isinstance(payload, dict) and name in payload:
            return _tokens(payload[name])
    return ""


def _geometry_valid(row: dict[str, Any]) -> bool:
    try:
        n_corners = int(float(safe(row.get("n_corners")) or 0))
    except ValueError:
        n_corners = 0
    return bool(safe(row.get("geometry_hash"))) and n_corners >= 4 and not safe(row.get("parse_error"))


def _key(row: dict[str, Any]) -> tuple[str, str, str]:
    return safe(row.get("task_id")), safe(row.get("base_task_id")), safe(row.get("dataset_group"))


def _outcome_exact_key(row: dict[str, Any]) -> tuple[str, str, str, str, str]:
    return (
        safe(row.get("project_id")),
        safe(row.get("ls_runtime_task_id")),
        safe(row.get("task_id")),
        safe(row.get("base_task_id")),
        safe(row.get("condition")),
    )


def _outcome_legacy_key(row: dict[str, Any]) -> tuple[str, str, str]:
    return safe(row.get("task_id")), safe(row.get("base_task_id")), safe(row.get("condition"))


def _inventory_flags(path: Path | None) -> dict[tuple[str, str, str], str]:
    if path is None or not path.exists():
        return {}
    flags: dict[tuple[str, str, str], str] = {}
    for row in read_csv(path):
        group = safe(row.get("dataset_group")) or ("Calibration_" + safe(row.get("calibration_split")) if safe(row.get("calibration_split")) else "")
        key = (safe(row.get("task_id")), safe(row.get("base_task_id")), group)
        if key[0] and key[1] and key[2]:
            flags[key] = safe(row.get("used_for_r_u"))
    return flags


def _used_for_r_u(row: dict[str, Any]) -> bool:
    if not eligible_independent_evidence(row):
        return False
    group = safe(row.get("dataset_group"))
    source_flag = safe(row.get("used_for_r_u"))
    if source_flag.lower().startswith("false"):
        return False
    if group == "Calibration_semi":
        return False
    if group == "Calibration_core" and source_flag and source_flag.lower() != "true":
        return False
    if group == "Calibration_core" and source_flag.lower() == "true":
        return truthy(row.get("assigned_expected", True))
    if group == "Calibration_core" and not source_flag:
        return False
    return group == "Calibration_anchor" and truthy(row.get("assigned_expected", True))


def _used_for_rq2(row: dict[str, Any]) -> bool:
    if not eligible_independent_evidence(row):
        return False
    group = safe(row.get("dataset_group"))
    source_flag = safe(row.get("used_for_rq2"))
    if source_flag:
        return truthy(source_flag)
    return group in {"Calibration_anchor", "Calibration_core", "Calibration_semi"}


def build_quality_rows(canonical_rows: list[dict[str, str]], inventory_flags: dict[tuple[str, str, str], str] | None = None) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    inventory_flags = inventory_flags or {}
    for row in canonical_rows:
        failure = _c1_failure_fields(row)
        source_status = "from_canonical"
        if not safe(row.get("used_for_r_u")) and _key(row) in inventory_flags:
            row = {**row, "used_for_r_u": inventory_flags[_key(row)]}
            source_status = "from_candidate_inventory"
        elif safe(row.get("dataset_group")) == "Calibration_core" and not safe(row.get("used_for_r_u")):
            source_status = "missing_core_used_for_r_u_flag"
        model_issue = _choice(row, "model_issue")
        out.append(
            {
                "source_artifact": "",
                "source_sha256": "",
                "dependency_bundle_id": "",
                "stage": "C1",
                "pool": safe(row.get("dataset_group")),
                "validity_status": safe(row.get("validity_status")),
                "rule_version": RULE_VERSION,
                "interpretation_allowed": "false",
                "round_id": safe(row.get("round_id")) or "C1",
                "task_id": safe(row.get("task_id")),
                "base_task_id": safe(row.get("base_task_id")),
                "dataset_group": safe(row.get("dataset_group")),
                "scene_label": safe(row.get("scene_label")),
                "scene_bin": safe(row.get("scene_bin")),
                "scene_stratum": safe(row.get("scene_stratum")),
                "room_type": safe(row.get("room_type")),
                "risk_bucket": safe(row.get("risk_bucket")),
                "condition": safe(row.get("condition")),
                "worker_id": safe(row.get("worker_id")),
                "annotator_id": safe(row.get("worker_id")),
                "project_id": safe(row.get("project_id")),
                "ls_runtime_task_id": safe(row.get("ls_runtime_task_id") or row.get("task_id")),
                "annotation_id": safe(row.get("annotation_id")),
                "canonical_annotation_id": safe(row.get("canonical_annotation_id")),
                "response_hash": safe(row.get("response_hash")),
                "annotation_version_id": safe(row.get("annotation_version_id")),
                "task_final_scope": safe(row.get("task_final_scope") or row.get("final_scope")),
                "task_scope_resolution_status": safe(row.get("task_scope_resolution_status")),
                "task_oos_subtype": safe(row.get("task_oos_subtype")),
                "task_outcome_adjudication_status": safe(row.get("task_outcome_adjudication_status")),
                "reference_identity": safe(row.get("reference_identity")),
                "scope_reference_mode": safe(row.get("scope_reference_mode")),
                "geometry_reference_mode": safe(row.get("geometry_reference_mode")),
                "reference_worker_excluded": safe(row.get("reference_worker_excluded")),
                "reference_evidence_status": safe(row.get("reference_evidence_status")),
                "worker_scope_response": safe(row.get("worker_scope_response")),
                "worker_scope_outcome": safe(row.get("worker_scope_outcome")),
                "geometry_reference_status": safe(row.get("geometry_reference_status")),
                "process_evaluable": safe(row.get("process_evaluable")) or bool_text(eligible_independent_evidence(row)),
                "process_failure_observed": safe(row.get("process_failure_observed")) or "false",
                "process_failure_subfamily": safe(row.get("process_failure_subfamily")),
                "family": safe(row.get("family")),
                "subfamily": safe(row.get("subfamily")),
                "response_type": safe(row.get("response_type")),
                "scope": _choice(row, "scope"),
                "difficulty": _choice(row, "difficulty"),
                "model_issue": model_issue,
                "model_issue_primary": safe(row.get("model_issue_primary")) or model_issue.split(";")[0],
                "n_corners": safe(row.get("n_corners")),
                "geometry_hash": safe(row.get("geometry_hash")),
                "geometry_valid": _geometry_valid(row),
                "geometry_score_gate_passed": truthy(row.get("geometry_score_gate_passed")),
                "geometry_component_evaluable": truthy(row.get("geometry_component_evaluable")),
                "geometry_failure_threshold_status": safe(row.get("geometry_failure_threshold_status")),
                "geometry_failure_family_evaluable": truthy(row.get("geometry_failure_family_evaluable")),
                "geometry_failure_observed": safe(row.get("geometry_failure_observed")),
                "quality_metric_name": safe(row.get("quality_metric_name")),
                "quality_metric_value": safe(row.get("quality_metric_value")),
                "geometry_metric_direction": safe(row.get("geometry_metric_direction")),
                "geometry_normalization_rule": safe(row.get("geometry_normalization_rule")),
                "geometry_component_name": safe(row.get("geometry_component_name")),
                "geometry_score_status": safe(row.get("geometry_score_status")),
                "active_time": safe(row.get("active_time")),
                "active_time_source": safe(row.get("active_time_source")),
                "primary_active_time_eligible": truthy(row.get("primary_active_time_eligible")),
                "sensitivity_active_time_eligible": truthy(row.get("sensitivity_active_time_eligible")),
                "unassigned_active_time_seconds": safe(row.get("unassigned_active_time_seconds")),
                "unknown_annotation_event_count": safe(row.get("unknown_annotation_event_count")),
                "unknown_annotation_session_count": safe(row.get("unknown_annotation_session_count")),
                "known_unknown_oscillation_flag": truthy(row.get("known_unknown_oscillation_flag")),
                "unassigned_audit_present": truthy(row.get("unassigned_audit_present")),
                "unassigned_active_time_exclusion_reason": safe(row.get("unassigned_active_time_exclusion_reason")),
                "active_time_integrity_status": safe(row.get("active_time_integrity_status")),
                "system_collection_issue": truthy(row.get("system_collection_issue")),
                "active_time_exclusion_reason": safe(row.get("active_time_exclusion_reason")),
                "audit_only": truthy(row.get("audit_only")),
                "semi_response_type": safe(row.get("semi_response_type")),
                "semi_evidence_status": safe(row.get("semi_evidence_status")),
                "semi_issue_recognition_evaluable": truthy(row.get("semi_issue_recognition_evaluable")),
                "semi_geometry_correction_evaluable": truthy(row.get("semi_geometry_correction_evaluable")),
                "semi_correction_failure_observed": safe(row.get("semi_correction_failure_observed")),
                "undercoverage_risk_level": safe(row.get("undercoverage_risk_level")),
                "undercoverage_expert_verdict": safe(row.get("undercoverage_expert_verdict")),
                "undercoverage_evidence_status": safe(row.get("undercoverage_evidence_status")),
                "undercoverage_response": safe(row.get("undercoverage_response")),
                "undercoverage_subfamily": safe(row.get("undercoverage_subfamily")),
                "undercoverage_failure_observed": safe(row.get("undercoverage_failure_observed")),
                "used_for_r_u": _used_for_r_u(row),
                "used_for_r_u_source_status": source_status,
                "r_u_evidence_included": False,
                "r_u_evidence_exclusion_reason": "not_materialized",
                "r_u_score_or_outcome": safe(row.get("r_u_score_or_outcome") or row.get("quality_metric_value")),
                "r_u_metric_name": safe(row.get("r_u_metric_name")),
                "r_u_metric_value": safe(row.get("r_u_metric_value")),
                "r_u_metric_direction": safe(row.get("r_u_metric_direction")),
                "r_u_normalization_rule": safe(row.get("r_u_normalization_rule")),
                "r_u_score_status": safe(row.get("r_u_score_status")),
                "r_u_score_source": safe(row.get("r_u_score_source")),
                "duplicate_review_status": safe(row.get("duplicate_review_status")) or "not_required",
                "duplicate_decision": safe(row.get("duplicate_decision")),
                "process_disposition": safe(row.get("process_disposition")),
                "timing_disposition": safe(row.get("timing_disposition")),
                "reviewed_by": safe(row.get("reviewed_by")),
                "reviewed_at": safe(row.get("reviewed_at")),
                "used_for_rq2": _used_for_rq2(row),
                "assigned_expected": truthy(row.get("assigned_expected", True)),
                "outside_assignment_submission": truthy(row.get("outside_assignment_submission")),
                "duplicate_worker_task_submission": truthy(row.get("duplicate_worker_task_submission")),
                "eligible_independent_evidence": eligible_independent_evidence(row),
                "canonical_source_sha256": safe(row.get("source_sha256")),
                "canonical_eligibility_status": safe(row.get("canonical_eligibility_status")) or "not_evaluable",
                "canonical_eligibility_reason": safe(row.get("canonical_eligibility_reason")),
                "schema_interpretable": safe(row.get("schema_interpretable")) or "true",
                "schema_family": safe(row.get("schema_family")),
                "schema_error": safe(row.get("schema_error")),
                "difficulty_present": safe(row.get("difficulty_present")),
                "model_issue_present": safe(row.get("model_issue_present")),
                "choice_map_json": safe(row.get("choice_map_json")),
                "canonical_registry_sha256": safe(row.get("canonical_registry_sha256")),
                "source_export_sha256": safe(row.get("source_export_sha256") or row.get("source_sha256")),
                "annotation_created_at": safe(row.get("annotation_created_at")),
                "created_at": safe(row.get("created_at")),
                "arrived_at": safe(row.get("arrived_at")),
                "raw_result_json": safe(row.get("raw_result_json")),
                "raw_response": safe(row.get("raw_result_json") or row.get("choice_map_json")),
                "harmonized_state": safe(row.get("harmonized_state")),
                "assertion_source": safe(row.get("assertion_source")),
                "ui_schema_version": safe(row.get("ui_version") or row.get("schema_version")),
                "model_artifact_id": safe(row.get("initialization_artifact_id") or row.get("model_artifact_id")),
                "provenance_status": safe(row.get("provenance_status")),
                "prediction_selection_status": safe(row.get("prediction_selection_status")),
                "exclusion_reason": safe(row.get("canonical_eligibility_reason")),
                "independence_status": safe(row.get("independence_status")) or "not_evaluable",
                "independence_audit_identity": safe(row.get("independence_audit_identity")),
                "parent_annotation_id": safe(row.get("parent_annotation_id")),
                "parent_owner_id": safe(row.get("parent_owner_id")),
                "parent_cross_owner": safe(row.get("parent_cross_owner")),
                "parent_derived": safe(row.get("parent_derived")),
                "copy_risk_status": safe(row.get("copy_risk_status")),
                **failure,
            }
        )
        # A duplicate-review decision can explicitly identify a worker-level
        # process failure.  Preserve that disposition in the shared evidence
        # row; never infer a process failure merely from missing timing data.
        if safe(row.get("process_disposition")) == "worker_process_failure":
            out[-1]["process_failure_observed"] = "true"
            out[-1]["process_failure_subfamily"] = "duplicate_review_worker_process_failure"
    return out


def _canonical_meta_freshness(canonical_csv: Path, meta_rows: list[dict[str, str]]) -> tuple[bool, list[str]]:
    if not meta_rows:
        return False, ["meta_missing"]
    registry_rows = read_csv(canonical_csv)
    registry_ids = [safe(row.get("canonical_annotation_id")) for row in registry_rows if safe(row.get("canonical_annotation_id"))]
    meta_ids = [safe(row.get("canonical_annotation_id")) for row in meta_rows if safe(row.get("canonical_annotation_id"))]
    reasons: list[str] = []
    if len(registry_ids) != len(meta_ids) or set(registry_ids) != set(meta_ids) or len(set(meta_ids)) != len(meta_ids):
        reasons.append("annotation_id_bijection_mismatch")
    canonical_sha = sha256_file(canonical_csv)
    for row in meta_rows:
        if safe(row.get("canonical_registry_sha256")) != canonical_sha:
            reasons.append("canonical_registry_sha_mismatch")
        source = Path(safe(row.get("source_artifact")))
        if not source.is_absolute():
            source = canonical_csv.parent / source
        source_sha = safe(row.get("source_sha256"))
        if not source.exists() or not source_sha or sha256_file(source) != source_sha or (safe(row.get("source_export_sha256")) and safe(row.get("source_export_sha256")) != source_sha):
            reasons.append("raw_export_sha_mismatch")
    return not reasons, sorted(set(reasons))


def _scope_outcome(worker_response: str, final_scope: str) -> str:
    response = worker_response.lower()
    worker_oos = "oos" in response or "out" in response
    worker_in = "in_scope" in response or "in-scope" in response or response in {"normal", "acceptable"}
    if final_scope == "in_scope" and worker_in:
        return "correct_in_scope"
    if final_scope == "oos" and worker_oos:
        return "correct_oos"
    if final_scope == "in_scope" and worker_oos:
        return "scope_false_positive"
    if final_scope == "oos" and worker_in:
        return "scope_false_negative"
    return "not_evaluable"


def _r_u_evidence(row: dict[str, Any], *, formal_score_required: bool = False) -> tuple[bool, str]:
    classification, reasons = _classify_r_u_evidence(row, formal_score_required=formal_score_required)
    return classification == "included", ";".join(reasons)


def _classify_r_u_evidence(row: dict[str, Any], *, formal_score_required: bool = False) -> tuple[str, list[str]]:
    if not truthy(row.get("used_for_r_u")):
        return "excluded", ["not_protocol_r_u_candidate"]
    base_checks = [
        (safe(row.get("task_outcome_adjudication_status")) in {"approved", "resolved"}, "task_outcome_pending"),
        (safe(row.get("task_final_scope")) == "in_scope", "not_in_scope"),
        (safe(row.get("condition")) == "manual", "not_manual"),
        (safe(row.get("geometry_reference_status")) in {"expert_hard_single", "expert_hard_multi", "hard_single_gt", "hard_multi_gt", "worker_excluded_loo_consensus", "global_consensus_fallback"}, "geometry_reference_not_hard"),
        (truthy(row.get("geometry_valid")), "geometry_invalid"),
        (truthy(row.get("process_evaluable")) and not truthy(row.get("process_failure_observed")), "process_not_valid"),
        (safe(row.get("duplicate_review_status")) in {"not_required", "resolved", "auto_resolved_input_duplicate"}, "duplicate_review_pending"),
        (truthy(row.get("eligible_independent_evidence")), "canonical_or_independence_ineligible"),
        (safe(row.get("incident_evidence_status")) == "not_evaluable" or (safe(row.get("failure_attribution")) not in {"worker_caused_structural_failure", "policy_caused_failure", "external_system_failure", "not_evaluable"} and safe(row.get("worker_reliability_eligible")) != "false"), "failure_disposition_not_worker_reliability_eligible"),
    ]
    base_reasons = [reason for passed, reason in base_checks if not passed]
    if "task_outcome_pending" in base_reasons or "duplicate_review_pending" in base_reasons:
        return "pending_adjudication", base_reasons
    if base_reasons:
        return "excluded", base_reasons
    if formal_score_required:
        try:
            reference_support_valid = int(row.get("r_u_reference_support") or 0) >= 2
        except (TypeError, ValueError):
            reference_support_valid = False
        reference_sha = safe(row.get("r_u_reference_sha256")).lower()
        score_checks = [
            (safe(row.get("r_u_reference_mode")) == "worker_excluded_loo_consensus", "r_u_reference_mode_invalid"),
            (bool(safe(row.get("r_u_reference_identity"))), "r_u_reference_identity_missing"),
            (len(reference_sha) == 64 and all(char in "0123456789abcdef" for char in reference_sha), "r_u_reference_sha256_invalid"),
            (truthy(row.get("r_u_reference_excludes_worker")), "r_u_reference_includes_worker"),
            (reference_support_valid, "r_u_reference_support_insufficient"),
        ]
        try:
            score_finite = bool(safe(row.get("r_u_metric_value"))) and math.isfinite(float(row.get("r_u_metric_value")))
        except (TypeError, ValueError):
            score_finite = False
        score_value_in_range = score_finite and 0 <= float(row.get("r_u_metric_value")) <= 1
        score_checks.extend([
            (safe(row.get("r_u_score_status")) == "valid", "r_u_score_not_valid"),
            (safe(row.get("r_u_metric_name")) == "iou_to_consensus_loo", "r_u_metric_name_invalid"),
            (safe(row.get("r_u_metric_direction")) == "higher_is_better", "r_u_metric_direction_invalid"),
            (safe(row.get("r_u_normalization_rule")) == "identity_0_1", "r_u_normalization_rule_invalid"),
            (score_value_in_range, "r_u_score_missing_nonfinite_or_out_of_range"),
            (bool(safe(row.get("r_u_score_source"))), "r_u_score_source_missing"),
        ])
        score_reasons = [reason for passed, reason in score_checks if not passed]
        if score_reasons:
            return "invalid_score_contract", score_reasons
    return "included", []


def materialize(canonical_csv: Path, output_dir: Path = DEFAULT_OUTPUT_DIR, candidate_inventory_csv: Path | None = DEFAULT_CORE_DRAFT, *, input_status: str = "dry_run", task_outcome_csv: Path | None = None, r_u_scoring_evidence_csv: Path | None = None) -> dict[str, Any]:
    canonical_meta_csv = output_dir / "c1_canonical_meta_observations.csv"
    meta_rows = read_csv(canonical_meta_csv) if canonical_meta_csv.exists() else []
    meta_fresh, meta_freshness_reasons = _canonical_meta_freshness(canonical_csv, meta_rows)
    # Dry-run keeps a descriptive compatibility view, but formal quality is
    # strictly registry -> meta bound and never falls back to canonical CSV.
    canonical_failure_by_id = {
        safe(row.get("canonical_annotation_id")): row
        for row in read_csv(canonical_csv)
        if safe(row.get("canonical_annotation_id"))
    }
    source_rows = meta_rows if meta_fresh else ([] if input_status == "formal" else read_csv(canonical_csv))
    if meta_fresh:
        source_rows = [
            {**row, **{field: canonical_failure_by_id.get(safe(row.get("canonical_annotation_id")), {}).get(field, row.get(field, "")) for field in FAILURE_FIELDS}}
            for row in source_rows
        ]
    rows = build_quality_rows(source_rows, _inventory_flags(candidate_inventory_csv))
    score_rows: dict[tuple[str, str, str, str, str, str], dict[str, str]] = {}
    score_blockers: list[str] = []
    if r_u_scoring_evidence_csv and r_u_scoring_evidence_csv.exists():
        for score_row in read_csv(r_u_scoring_evidence_csv):
            key = tuple(safe(score_row.get(field)) for field in ("project_id", "ls_runtime_task_id", "worker_id", "annotation_id", "response_hash", "source_export_sha256"))
            if not all(key):
                score_blockers.append("r_u_score_identity_missing")
                continue
            if key in score_rows:
                score_blockers.append("r_u_score_identity_duplicate")
                continue
            score_rows[key] = score_row
    quality_identity_keys = {tuple(safe(row.get(field)) for field in ("project_id", "ls_runtime_task_id", "worker_id", "annotation_id", "response_hash", "source_export_sha256")) for row in rows}
    if score_rows and set(score_rows) - quality_identity_keys:
        score_blockers.append("r_u_score_orphan_identity")
    for row in rows:
        key = tuple(safe(row.get(field)) for field in ("project_id", "ls_runtime_task_id", "worker_id", "annotation_id", "response_hash", "source_export_sha256"))
        score = score_rows.get(key, {})
        if score:
            row["r_u_metric_name"] = safe(score.get("r_u_metric_name") or score.get("metric_name"))
            row["r_u_metric_value"] = safe(score.get("r_u_metric_value") or score.get("metric_value"))
            row["r_u_metric_direction"] = safe(score.get("r_u_metric_direction") or score.get("metric_direction"))
            row["r_u_normalization_rule"] = safe(score.get("r_u_normalization_rule") or score.get("normalization_rule"))
            row["r_u_score_status"] = safe(score.get("r_u_score_status") or score.get("score_status"))
            row["r_u_score_source"] = safe(score.get("r_u_score_source") or score.get("score_source") or r_u_scoring_evidence_csv)
            for field in ("r_u_reference_mode", "r_u_reference_identity", "r_u_reference_sha256", "r_u_reference_excludes_worker", "r_u_reference_support"):
                row[field] = safe(score.get(field))
        elif input_status != "formal" and safe(row.get("quality_metric_name")) and safe(row.get("quality_metric_value")):
            row["r_u_metric_name"] = safe(row.get("quality_metric_name"))
            row["r_u_metric_value"] = safe(row.get("quality_metric_value"))
            row["r_u_metric_direction"] = safe(row.get("geometry_metric_direction"))
            row["r_u_normalization_rule"] = safe(row.get("geometry_normalization_rule"))
            row["r_u_score_status"] = "evaluable"
            row["r_u_score_source"] = "dry_run_geometry_score_proxy"
        row["r_u_score_or_outcome"] = safe(row.get("r_u_metric_value"))
    outcomes: dict[tuple[str, str, str, str, str], dict[str, str]] = {}
    legacy_outcomes: dict[tuple[str, str, str], list[dict[str, str]]] = {}
    outcome_blockers: list[str] = []
    if task_outcome_csv and task_outcome_csv.exists():
        for outcome in read_csv(task_outcome_csv):
            exact_key = _outcome_exact_key(outcome)
            legacy_key = _outcome_legacy_key(outcome)
            if not all(legacy_key):
                outcome_blockers.append("task_outcome_identity_missing_or_duplicate")
                continue
            if all(exact_key[:2]) and exact_key in outcomes:
                outcome_blockers.append("task_outcome_identity_missing_or_duplicate")
                continue
            final_scope = safe(outcome.get("final_scope"))
            reference_status = safe(outcome.get("geometry_reference_status"))
            reference_mode = safe(outcome.get("geometry_reference_mode") or outcome.get("scope_reference_mode"))
            reference_excludes_worker = (
                truthy(outcome.get("reference_worker_excluded"))
                if reference_status in {"worker_excluded_loo_consensus", "global_consensus_fallback"}
                else safe(outcome.get("reference_worker_excluded")) in {"false", "0", "no"}
            )
            reference_contract_valid = final_scope == "oos" or (
                reference_status in {"expert_hard_single", "expert_hard_multi", "consensus_reference", "hard_single_gt", "hard_multi_gt", "worker_excluded_loo_consensus", "global_consensus_fallback"}
                and safe(outcome.get("reference_identity"))
                and (input_status != "formal" or (reference_excludes_worker and safe(outcome.get("reference_evidence_status")) in {"evaluable", "valid", "adjudicated", "not_required"} and reference_mode in {"expert_adjudicated", "expert_hard_gt", "worker_excluded_loo_consensus", "global_consensus_fallback"}))
            )
            valid = (
                final_scope in {"in_scope", "oos"}
                and safe(outcome.get("scope_resolution_status")) == "resolved"
                and safe(outcome.get("adjudication_status")) in {"approved", "resolved"}
                and bool(safe(outcome.get("reviewed_by")) and safe(outcome.get("reviewed_at")))
                and reference_contract_valid
            )
            if not valid:
                outcome_blockers.append("task_outcome_contract_invalid")
                continue
            if all(exact_key[:2]):
                outcomes[exact_key] = outcome
            legacy_outcomes.setdefault(legacy_key, []).append(outcome)
    legacy_contexts: dict[tuple[str, str, str], set[tuple[str, str]]] = {}
    for row in rows:
        legacy_contexts.setdefault(_outcome_legacy_key(row), set()).add((safe(row.get("project_id")), safe(row.get("ls_runtime_task_id"))))
    for key, contexts in legacy_contexts.items():
        if len(contexts) > 1 and key in legacy_outcomes and input_status == "formal":
            outcome_blockers.append("task_outcome_legacy_identity_ambiguous")
    for row in rows:
        outcome = outcomes.get(_outcome_exact_key(row))
        if outcome is None:
            legacy_matches = legacy_outcomes.get(_outcome_legacy_key(row), [])
            if input_status != "formal" and len(legacy_matches) == 1:
                outcome = legacy_matches[0]
            elif legacy_matches:
                outcome_blockers.append("task_outcome_legacy_identity_ambiguous")
        outcome = outcome or {}
        row["task_final_scope"] = safe(outcome.get("final_scope"))
        row["task_scope_resolution_status"] = safe(outcome.get("scope_resolution_status"))
        row["task_oos_subtype"] = safe(outcome.get("oos_subtype"))
        row["geometry_reference_status"] = safe(outcome.get("geometry_reference_status"))
        row["reference_identity"] = safe(outcome.get("reference_identity"))
        row["scope_reference_mode"] = safe(outcome.get("scope_reference_mode"))
        row["geometry_reference_mode"] = safe(outcome.get("geometry_reference_mode"))
        row["reference_worker_excluded"] = safe(outcome.get("reference_worker_excluded"))
        row["reference_evidence_status"] = safe(outcome.get("reference_evidence_status"))
        row["task_outcome_adjudication_status"] = safe(outcome.get("adjudication_status")) or "pending"
        row["worker_scope_response"] = _choice(row, "scope")
        row["worker_scope_outcome"] = _scope_outcome(row["worker_scope_response"], row["task_final_scope"])
        classification, reasons = _classify_r_u_evidence(row, formal_score_required=input_status == "formal")
        included, reason = classification == "included", ";".join(reasons)
        row["r_u_evidence_included"], row["r_u_evidence_exclusion_reason"] = included, reason
        row["r_u_evidence_classification"] = classification
    harmonization_csv = output_dir / "model_issue_harmonization_C1.csv"
    harmonization_summary_path = output_dir / "model_issue_harmonization_C1.summary.json"
    harmonization_summary = json.loads(harmonization_summary_path.read_text(encoding="utf-8")) if harmonization_summary_path.exists() else {}
    harmonization_rows = read_csv(harmonization_csv) if harmonization_csv.exists() else []
    harmonized = {safe(item.get("canonical_annotation_id")): item for item in harmonization_rows if safe(item.get("canonical_annotation_id"))}
    harmonization_ids = [safe(item.get("canonical_annotation_id")) for item in harmonization_rows if safe(item.get("canonical_annotation_id"))]
    harmonization_fresh = bool(harmonization_rows) and len(harmonization_ids) == len(set(harmonization_ids)) and set(harmonization_ids) == {safe(row.get("canonical_annotation_id")) for row in rows if safe(row.get("canonical_annotation_id"))}
    for row in rows:
        item = harmonized.get(safe(row.get("canonical_annotation_id")))
        if not item:
            continue
        row["harmonized_state"] = safe(item.get("harmonized_issue"))
        row["assertion_source"] = safe(item.get("assertion_source"))
        for field in ("original_provenance_status", "retrospective_amendment_status", "effective_provenance_status", "harmonization_validity_status", "retrospective_amendment_source", "retrospective_amendment_sha256"):
            row[field] = safe(item.get(field))
        row["harmonization_reason"] = safe(item.get("inference_reason"))
        if safe(item.get("harmonization_validity_status")) in {"valid", "valid_behavior_inferred"} and safe(item.get("assertion_source")) in {"explicit_worker_label", "legacy_behavior_inferred"}:
            row["model_issue"] = safe(item.get("harmonized_issue"))
            row["model_issue_primary"] = safe(item.get("harmonized_issue")).split(";")[0]
            row["model_issue_present"] = "true"
        elif safe(item.get("assertion_source")) == "not_evaluable":
            row["model_issue"] = ""
            row["model_issue_primary"] = ""
            row["model_issue_present"] = "false"
    quality_source_sha = sha256_file(canonical_meta_csv) if canonical_meta_csv.exists() else ""
    for row in rows:
        row["source_artifact"] = str(canonical_meta_csv)
        row["source_sha256"] = quality_source_sha
        dependencies = [canonical_meta_csv, harmonization_csv, canonical_csv]
        if task_outcome_csv:
            dependencies.append(task_outcome_csv)
        if candidate_inventory_csv:
            dependencies.append(candidate_inventory_csv)
        if r_u_scoring_evidence_csv:
            dependencies.append(r_u_scoring_evidence_csv)
        row.update(dependency_bundle(dependencies, rule_version=RULE_VERSION))
        row["validity_status"] = "dry_run" if input_status != "formal" else ("valid" if row.get("canonical_eligibility_status") == "valid" else "not_evaluable")
    quality_csv = output_dir / "c1_quality_annotations.csv"
    write_csv(quality_csv, rows, QUALITY_FIELDS)
    outcome_template_csv = output_dir / "c1_task_outcome_adjudication_template.csv"
    pending_tasks = {
        (safe(row.get("project_id")), safe(row.get("ls_runtime_task_id")), safe(row.get("task_id")), safe(row.get("base_task_id")), safe(row.get("condition")))
        for row in rows if row["task_outcome_adjudication_status"] == "pending"
    }
    outcome_fields = ["project_id", "ls_runtime_task_id", "task_id", "base_task_id", "condition", "final_scope", "scope_resolution_status", "oos_subtype", "scope_reference_mode", "geometry_reference_mode", "geometry_reference_status", "reference_identity", "reference_worker_excluded", "reference_evidence_status", "adjudication_status", "reviewed_by", "reviewed_at", "notes"]
    write_csv(
        outcome_template_csv,
        [{field: (project if field == "project_id" else runtime if field == "ls_runtime_task_id" else task if field == "task_id" else base if field == "base_task_id" else condition if field == "condition" else "") for field in outcome_fields} for project, runtime, task, base, condition in sorted(pending_tasks)],
        outcome_fields,
    )
    r_u_evidence_csv = output_dir / "calibration_r_u_evidence_C1.csv"
    r_u_fields = ["round_id", "project_id", "ls_runtime_task_id", "worker_id", "task_id", "base_task_id", "condition", "dataset_group", "annotation_id", "canonical_annotation_id", "response_hash", "source_export_sha256", "annotation_version_id", "assigned_expected", "outside_assignment_submission", "canonical_eligibility_status", "eligible_independent_evidence", "r_u_evidence_classification", "r_u_evidence_included", "r_u_evidence_exclusion_reason", "task_final_scope", "task_outcome_adjudication_status", "duplicate_review_status", "duplicate_decision", "independence_status", "process_evaluable", "process_failure_observed", "geometry_valid", "scope_reference_mode", "geometry_reference_mode", "reference_identity", "reference_worker_excluded", "geometry_reference_status", "reference_evidence_status", "r_u_metric_name", "r_u_metric_value", "r_u_metric_direction", "r_u_normalization_rule", "r_u_score_status", "r_u_score_source", "r_u_score_or_outcome"]
    r_u_fields += ["r_u_reference_mode", "r_u_reference_identity", "r_u_reference_sha256", "r_u_reference_excludes_worker", "r_u_reference_support"]
    write_csv(r_u_evidence_csv, rows, r_u_fields)

    quality_df = pd.DataFrame(rows, columns=QUALITY_FIELDS)
    consensus, audit = build_summary(quality_df)
    consensus_csv = output_dir / "meta_label_consensus_summary_C1.csv"
    audit_json = output_dir / "meta_label_consensus_summary_C1.audit.json"
    consensus_csv.parent.mkdir(parents=True, exist_ok=True)
    consensus.to_csv(consensus_csv, index=False, encoding="utf-8")
    write_json(audit_json, {**audit, "sidecar_only_no_dt_backflow": True})
    three_state_summary = materialize_meta_label_three_state(quality_csv, output_dir, input_status=input_status)

    blockers = (["canonical_meta_missing_or_stale"] if not meta_fresh else []) + (["harmonization_missing_or_stale"] if meta_fresh and not harmonization_fresh else []) + outcome_blockers + score_blockers
    if input_status == "formal" and any(row["task_outcome_adjudication_status"] not in {"approved", "resolved", "not_applicable"} for row in rows):
        blockers.append("task_outcome_adjudication_pending")
    blockers += [f"amendment_{key}" for key in (harmonization_summary.get("amendment_blockers") or {})]
    if any(safe(row.get("independence_status")) not in {"independent", "non_independent_confirmed"} for row in rows):
        blockers.append("independence_not_evaluable")
    if any(row["used_for_r_u_source_status"] == "missing_core_used_for_r_u_flag" for row in rows):
        blockers.append("missing_core_used_for_r_u_flag")
    if input_status == "formal" and any(safe(row.get("r_u_evidence_classification")) in {"pending_adjudication", "invalid_score_contract"} for row in rows):
        blockers.append("formal_r_u_evidence_incomplete")
    if input_status == "formal" and any(safe(row.get("failure_attribution")) == "not_evaluable" for row in rows):
        blockers.append("failure_disposition_not_evaluable")
    included_worker_tasks = [(safe(row.get("project_id")), safe(row.get("ls_runtime_task_id")), safe(row.get("worker_id"))) for row in rows if truthy(row.get("r_u_evidence_included"))]
    if len(included_worker_tasks) != len(set(included_worker_tasks)):
        blockers.append("formal_r_u_included_worker_task_duplicate")
    included_references = [(safe(row.get("project_id")), safe(row.get("ls_runtime_task_id")), safe(row.get("r_u_reference_identity"))) for row in rows if truthy(row.get("r_u_evidence_included"))]
    if len(included_references) != len(set(included_references)):
        blockers.append("formal_r_u_reference_not_worker_specific")
    if input_status == "formal" and harmonization_summary.get("amendment_complete") is False:
        blockers.append("amendment_contract_incomplete")
    summary = {
        "input_csv": str(canonical_csv),
        "canonical_meta_csv": str(canonical_meta_csv),
        "canonical_meta_fresh": meta_fresh,
        "canonical_meta_freshness_reasons": meta_freshness_reasons,
        "harmonization_fresh": harmonization_fresh,
        "input_status": input_status,
        "quality_csv": str(quality_csv),
        "meta_label_consensus_csv": str(consensus_csv),
        "meta_label_consensus_audit_json": str(audit_json),
        "three_state_sidecars": three_state_summary,
        "n_quality_rows": len(rows),
        "n_used_for_r_u": sum(truthy(row["used_for_r_u"]) for row in rows),
        "r_u_evidence_csv": str(r_u_evidence_csv),
        "n_r_u_evidence_included": sum(truthy(row["r_u_evidence_included"]) for row in rows),
        "task_outcome_pending_count": sum(row["task_outcome_adjudication_status"] not in {"approved", "resolved", "not_applicable"} for row in rows),
        "task_outcome_csv": str(task_outcome_csv or ""),
        "task_outcome_adjudication_template_csv": str(outcome_template_csv),
        "n_missing_core_used_for_r_u_flag": sum(row["used_for_r_u_source_status"] == "missing_core_used_for_r_u_flag" for row in rows),
        "n_used_for_rq2": sum(truthy(row["used_for_rq2"]) for row in rows),
        "independence_not_evaluable_count": sum(safe(row.get("independence_status")) not in {"independent", "non_independent_confirmed"} for row in rows),
        "non_independent_confirmed_count": sum(safe(row.get("independence_status")) == "non_independent_confirmed" for row in rows),
        "unassigned_active_time_seconds_total": sum(float(row.get("unassigned_active_time_seconds") or 0) for row in rows),
        "unknown_annotation_event_count_total": sum(int(row.get("unknown_annotation_event_count") or 0) for row in rows),
        "unknown_annotation_session_count_total": sum(int(row.get("unknown_annotation_session_count") or 0) for row in rows),
        "rows_with_unknown_audit_count": sum(truthy(row.get("unassigned_audit_present")) for row in rows),
        "workers_with_unknown_audit_count": len({safe(row.get("worker_id")) for row in rows if truthy(row.get("unassigned_audit_present")) and safe(row.get("worker_id"))}),
        "known_unknown_oscillation_row_count": sum(truthy(row.get("known_unknown_oscillation_flag")) for row in rows),
        "system_collection_issue_row_count": sum(truthy(row.get("system_collection_issue")) for row in rows),
        "failure_attribution_counts": {name: sum(safe(row.get("failure_attribution")) == name for row in rows) for name in ("none", "worker_caused_structural_failure", "policy_caused_failure", "external_system_failure", "not_evaluable")},
        "exact_annotation_primary_count": sum(safe(row.get("active_time_integrity_status")) == "exact_annotation_valid" and truthy(row.get("primary_active_time_eligible")) for row in rows),
        "task_level_sensitivity_count": sum(safe(row.get("active_time_integrity_status")) == "task_level_fallback" and truthy(row.get("sensitivity_active_time_eligible")) for row in rows),
        "candidate_inventory_csv": str(candidate_inventory_csv) if candidate_inventory_csv else "",
        "r_u_scoring_evidence_csv": str(r_u_scoring_evidence_csv or ""),
        "r_u_score_blockers": sorted(set(score_blockers)),
        "harmonization_summary": harmonization_summary,
        "amendment_blocker_count": sum(int(value or 0) for value in (harmonization_summary.get("amendment_blockers") or {}).values()),
        "blockers": blockers,
        "r_u_estimated": False,
        "dt_backflow": False,
    }
    write_json(output_dir / "c1_quality_table_summary.json", summary)
    return summary


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Materialize C1 quality table and meta-label sidecar from canonical annotations.")
    parser.add_argument("--canonical-csv", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--candidate-inventory-csv", type=Path, default=DEFAULT_CORE_DRAFT)
    parser.add_argument("--task-outcome-csv", type=Path)
    parser.add_argument("--r-u-scoring-evidence-csv", type=Path)
    args = parser.parse_args(argv)
    print(json.dumps(materialize(args.canonical_csv, args.output_dir, args.candidate_inventory_csv, task_outcome_csv=args.task_outcome_csv, r_u_scoring_evidence_csv=args.r_u_scoring_evidence_csv), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
