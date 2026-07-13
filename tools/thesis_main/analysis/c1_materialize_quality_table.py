from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

import pandas as pd

_PROJECT_ROOT = Path(__file__).resolve().parents[3]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from tools.thesis_main.analysis.c1_live_collection_monitor import bool_text, read_csv, safe, truthy, write_csv, write_json
from tools.thesis_main.registry.materialize_meta_label_consensus_summary import build_summary
from tools.thesis_main.registry.materialize_meta_label_three_state_sidecars import materialize_meta_label_three_state

DEFAULT_INPUT = Path("analysis_results/calibration_c1_closeout/c1_canonical_annotations.csv")
DEFAULT_OUTPUT_DIR = Path("analysis_results/calibration_c1_closeout")
DEFAULT_CORE_DRAFT = Path("analysis_results/calibration_rebuild_20260702/calibration_core_draft_v3_1.csv")

QUALITY_FIELDS = [
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
    "canonical_annotation_id",
    "task_final_scope",
    "task_oos_subtype",
    "worker_scope_response",
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
    "used_for_rq2",
    "assigned_expected",
    "canonical_source_sha256",
    "canonical_eligibility_status",
    "canonical_eligibility_reason",
    "schema_interpretable",
    "schema_error",
    "difficulty_present",
    "model_issue_present",
    "choice_map_json",
]


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
    group = safe(row.get("dataset_group"))
    source_flag = safe(row.get("used_for_rq2"))
    if source_flag:
        return truthy(source_flag)
    return group in {"Calibration_anchor", "Calibration_core", "Calibration_semi"}


def build_quality_rows(canonical_rows: list[dict[str, str]], inventory_flags: dict[tuple[str, str, str], str] | None = None) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    inventory_flags = inventory_flags or {}
    for row in canonical_rows:
        source_status = "from_canonical"
        if not safe(row.get("used_for_r_u")) and _key(row) in inventory_flags:
            row = {**row, "used_for_r_u": inventory_flags[_key(row)]}
            source_status = "from_candidate_inventory"
        elif safe(row.get("dataset_group")) == "Calibration_core" and not safe(row.get("used_for_r_u")):
            source_status = "missing_core_used_for_r_u_flag"
        model_issue = _choice(row, "model_issue")
        out.append(
            {
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
                "canonical_annotation_id": safe(row.get("canonical_annotation_id")),
                "task_final_scope": safe(row.get("task_final_scope") or row.get("final_scope") or row.get("scope")),
                "task_oos_subtype": safe(row.get("task_oos_subtype")),
                "worker_scope_response": safe(row.get("worker_scope_response")),
                "geometry_reference_status": safe(row.get("geometry_reference_status")),
                "process_evaluable": safe(row.get("process_evaluable")),
                "process_failure_observed": safe(row.get("process_failure_observed")),
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
                "used_for_rq2": _used_for_rq2(row),
                "assigned_expected": truthy(row.get("assigned_expected", True)),
                "canonical_source_sha256": safe(row.get("source_sha256")),
                "canonical_eligibility_status": safe(row.get("canonical_eligibility_status")) or "valid",
                "canonical_eligibility_reason": safe(row.get("canonical_eligibility_reason")),
                "schema_interpretable": safe(row.get("schema_interpretable")) or "true",
                "schema_error": safe(row.get("schema_error")),
                "difficulty_present": safe(row.get("difficulty_present")),
                "model_issue_present": safe(row.get("model_issue_present")),
                "choice_map_json": safe(row.get("choice_map_json")),
            }
        )
    return out


def materialize(canonical_csv: Path, output_dir: Path = DEFAULT_OUTPUT_DIR, candidate_inventory_csv: Path | None = DEFAULT_CORE_DRAFT) -> dict[str, Any]:
    canonical_meta_csv = output_dir / "c1_canonical_meta_observations.csv"
    canonical_sha = __import__("hashlib").sha256(canonical_csv.read_bytes()).hexdigest()
    meta_rows = read_csv(canonical_meta_csv) if canonical_meta_csv.exists() else []
    meta_fresh = bool(meta_rows) and all(safe(row.get("canonical_registry_sha256")) == canonical_sha for row in meta_rows)
    rows = build_quality_rows(meta_rows if meta_fresh else read_csv(canonical_csv), _inventory_flags(candidate_inventory_csv))
    quality_csv = output_dir / "c1_quality_annotations.csv"
    write_csv(quality_csv, rows, QUALITY_FIELDS)

    quality_df = pd.DataFrame(rows, columns=QUALITY_FIELDS)
    consensus, audit = build_summary(quality_df)
    consensus_csv = output_dir / "meta_label_consensus_summary_C1.csv"
    audit_json = output_dir / "meta_label_consensus_summary_C1.audit.json"
    consensus_csv.parent.mkdir(parents=True, exist_ok=True)
    consensus.to_csv(consensus_csv, index=False, encoding="utf-8")
    write_json(audit_json, {**audit, "sidecar_only_no_dt_backflow": True})
    three_state_summary = materialize_meta_label_three_state(quality_csv, output_dir)

    summary = {
        "input_csv": str(canonical_csv),
        "canonical_meta_csv": str(canonical_meta_csv),
        "canonical_meta_fresh": meta_fresh,
        "quality_csv": str(quality_csv),
        "meta_label_consensus_csv": str(consensus_csv),
        "meta_label_consensus_audit_json": str(audit_json),
        "three_state_sidecars": three_state_summary,
        "n_quality_rows": len(rows),
        "n_used_for_r_u": sum(truthy(row["used_for_r_u"]) for row in rows),
        "n_missing_core_used_for_r_u_flag": sum(row["used_for_r_u_source_status"] == "missing_core_used_for_r_u_flag" for row in rows),
        "n_used_for_rq2": sum(truthy(row["used_for_rq2"]) for row in rows),
        "unassigned_active_time_seconds_total": sum(float(row.get("unassigned_active_time_seconds") or 0) for row in rows),
        "unknown_annotation_event_count_total": sum(int(row.get("unknown_annotation_event_count") or 0) for row in rows),
        "unknown_annotation_session_count_total": sum(int(row.get("unknown_annotation_session_count") or 0) for row in rows),
        "rows_with_unknown_audit_count": sum(truthy(row.get("unassigned_audit_present")) for row in rows),
        "workers_with_unknown_audit_count": len({safe(row.get("worker_id")) for row in rows if truthy(row.get("unassigned_audit_present")) and safe(row.get("worker_id"))}),
        "known_unknown_oscillation_row_count": sum(truthy(row.get("known_unknown_oscillation_flag")) for row in rows),
        "system_collection_issue_row_count": sum(truthy(row.get("system_collection_issue")) for row in rows),
        "exact_annotation_primary_count": sum(safe(row.get("active_time_integrity_status")) == "exact_annotation_valid" and truthy(row.get("primary_active_time_eligible")) for row in rows),
        "task_level_sensitivity_count": sum(safe(row.get("active_time_integrity_status")) == "task_level_fallback" and truthy(row.get("sensitivity_active_time_eligible")) for row in rows),
        "candidate_inventory_csv": str(candidate_inventory_csv) if candidate_inventory_csv else "",
        "blockers": (["canonical_meta_missing_or_stale"] if not meta_fresh else []) + (["missing_core_used_for_r_u_flag"] if any(row["used_for_r_u_source_status"] == "missing_core_used_for_r_u_flag" for row in rows) else []),
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
    args = parser.parse_args(argv)
    print(json.dumps(materialize(args.canonical_csv, args.output_dir, args.candidate_inventory_csv), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
