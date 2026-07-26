from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any

from tools.thesis_main.analysis.prescreen_canonicalize_export import _annotation_id, _data, _project_id, _safe_str, _task_id, _worker_id, annotation_version_id, annotation_version_identity
from tools.thesis_main.analysis.audit_p1_exact_copy_low_time import canonical_geometry_hash
from tools.thesis_main.analysis.quality_core.choice_parser import extract_data
from tools.thesis_main.analysis.vfinal_artifact_utils import COMMON_SIDEcar_FIELDS, formal_status, json_text, sha256_file, sha256_json, sidecar_common, write_csv_rows


RULE_VERSION = "c1_canonical_evidence_v2"
_CHOICES = {
    "difficulty": {"trivial", "occlusion", "low_texture", "seam", "reflection", "low_quality"},
    "model_issue": {"acceptable", "overextend_adjacent", "underextend", "over_parsing", "corner_drift", "corner_duplicate", "topology_failure", "fail"},
}


def _load_tasks(path: Path) -> list[dict[str, Any]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, list):
        raise ValueError(f"{path} must contain a Label Studio task-list export")
    return [row for row in payload if isinstance(row, dict)]


def _truthy(value: Any) -> bool:
    return str(value).strip().lower() in {"true", "1", "yes"}


def _eligibility(rows: list[dict[str, str]]) -> tuple[str, str, dict[str, str]]:
    if not rows:
        return "invalid", "missing_canonical_registry", {}
    if len(rows) != 1:
        return "invalid", "duplicate_canonical_registry", rows[0]
    row = rows[0]
    if _truthy(row.get("duplicate_worker_task_submission")):
        return "invalid", "duplicate_worker_task_submission", row
    if _truthy(row.get("outside_assignment_submission")) or str(row.get("assigned_expected", "")).lower() == "false":
        return "excluded", "nonindependent_or_unassigned", row
    if str(row.get("planned_mapping_status", "")).endswith("missing") or str(row.get("runtime_binding_status", "")).endswith("collision"):
        return "invalid", "runtime_mapping_invalid", row
    if str(row.get("parse_error", "")).strip():
        return "invalid", "canonical_parse_error", row
    independence = str(row.get("independence_status", "")).strip().lower()
    parent_derived = str(row.get("parent_derived", "")).strip().lower() == "true"
    parent_cross_owner = str(row.get("parent_cross_owner", "")).strip().lower() == "true"
    copy_risk = str(row.get("copy_risk_status", "")).strip().lower()
    if independence == "non_independent_confirmed" or parent_derived or parent_cross_owner or copy_risk in {"confirmed", "high", "non_independent_confirmed"}:
        return "excluded", "non_independent_confirmed", row
    return "valid", "", row


def _schema(choice_map: dict[str, list[str]]) -> tuple[bool, str]:
    for field, allowed in _CHOICES.items():
        values = {str(value).lower() for value in choice_map.get(field, [])}
        if values - allowed:
            return False, f"unknown_{field}_choice"
        negative = "trivial" if field == "difficulty" else "acceptable"
        if negative in values and len(values) > 1:
            return False, f"conflicting_{field}_choice"
    return True, ""


def _provenance(task: dict[str, Any], export_path: Path, *, stage: str, pool: str, condition: str, input_status: str) -> list[dict[str, Any]]:
    predictions = [item for item in task.get("predictions") or [] if isinstance(item, dict)]
    if not predictions:
        missing_status = "not_applicable" if condition == "manual" else "missing_required_initialization"
        return [{**sidecar_common(source_artifact=str(export_path), source_sha256=sha256_file(export_path), stage=stage, pool=pool, condition=condition, validity_status="not_evaluable" if condition != "manual" else "not_applicable", rule_version=RULE_VERSION, interpretation_allowed=False), "logical_task_id": _safe_str(_data(task).get("task_id") or _data(task).get("base_task_id")), "ls_runtime_task_id": _task_id(task, 0), "project_id": _project_id(task), "task_id": _safe_str(_data(task).get("task_id") or _data(task).get("base_task_id")), "artifact_kind": "manual_or_no_prediction", "provenance_status": missing_status, "prediction_selection_status": "missing"}]
    rows = []
    data = _data(task)
    requested = _safe_str(data.get("initialization_artifact_id") or data.get("prediction_id") or data.get("prediction_artifact_id"))
    selected = [item for item in predictions if requested and _safe_str(item.get("initialization_artifact_id") or item.get("id")) == requested]
    if not selected:
        selected = predictions if len(predictions) == 1 else []
    if not selected:
        return [{**sidecar_common(source_artifact=str(export_path), source_sha256=sha256_file(export_path), stage=stage, pool=pool, condition=condition, validity_status="not_evaluable", rule_version=RULE_VERSION, interpretation_allowed=False), "logical_task_id": _safe_str(data.get("task_id") or data.get("base_task_id")), "ls_runtime_task_id": _task_id(task, 0), "project_id": _project_id(task), "task_id": _safe_str(data.get("task_id") or data.get("base_task_id")), "artifact_kind": "prediction", "prediction_selection_status": "ambiguous_multiple_predictions", "provenance_status": "incomplete"}]
    for index, prediction in enumerate(selected, 1):
        try:
            initial_corners, _polygon, _choices, _quality = extract_data(prediction.get("result", []))
            initial_geometry_hash, _payload, _count = canonical_geometry_hash(initial_corners, round_px=0.5)
        except Exception:
            initial_geometry_hash = ""
        fields = {
            "initialization_artifact_id": _safe_str(prediction.get("initialization_artifact_id") or prediction.get("id")),
            "model_version": _safe_str(prediction.get("model_version") or prediction.get("version")),
            "checkpoint_sha256": _safe_str(prediction.get("checkpoint_sha256") or prediction.get("checkpoint_hash")),
            "inference_config_sha256": _safe_str(prediction.get("inference_config_sha256") or prediction.get("config_sha256") or prediction.get("config_hash")),
            "preprocess_postprocess_sha256": _safe_str(prediction.get("preprocess_postprocess_sha256") or prediction.get("preprocess_sha256") or prediction.get("preprocess_hash")),
            "prediction_payload_hash": sha256_json(prediction),
            "initial_geometry_hash": initial_geometry_hash,
        }
        complete = all(fields.values())
        status, allowed = formal_status(input_status, valid=complete)
        rows.append({**sidecar_common(source_artifact=str(export_path), source_sha256=sha256_file(export_path), stage=stage, pool=pool, condition=condition, validity_status=status, rule_version=RULE_VERSION, interpretation_allowed=allowed), "logical_task_id": _safe_str(data.get("task_id") or data.get("base_task_id")), "ls_runtime_task_id": _task_id(task, 0), "project_id": _project_id(task), "task_id": _safe_str(data.get("task_id") or data.get("base_task_id")), "prediction_index": index, "artifact_kind": "prediction", "prediction_selection_status": "selected_unique" if len(predictions) == 1 else "selected_by_artifact_id", "prediction_result_present": str(isinstance(prediction.get("result"), list)).lower(), "provenance_status": "complete" if complete else "incomplete", **fields})
    return rows


def materialize_canonical_evidence(export_paths: list[Path], canonical_csv: Path, output_dir: Path, *, stage: str = "C1", input_status: str = "dry_run", version_disposition_csv: Path | None = None) -> dict[str, Any]:
    registry_sha = sha256_file(canonical_csv)
    registry_rows = list(csv.DictReader(canonical_csv.open(encoding="utf-8-sig"))) if canonical_csv.exists() else []
    canonical_ids = [str(row.get("canonical_annotation_id", "")).strip() for row in registry_rows]
    binding_blockers: list[str] = []
    if any(not item for item in canonical_ids):
        binding_blockers.append("canonical_registry_blank_identity")
    if len(canonical_ids) != len(set(canonical_ids)):
        binding_blockers.append("canonical_registry_duplicate_identity")
    records: dict[tuple[str, str, str, str, str, str], dict[str, Any]] = {}
    for export_path in export_paths:
        export_sha = sha256_file(export_path)
        for task_index, task in enumerate(_load_tasks(export_path), 1):
            task_id, project_id, data = _task_id(task, task_index), _project_id(task), _data(task)
            for ann_index, annotation in enumerate(task.get("annotations") or [], 1):
                if not isinstance(annotation, dict):
                    continue
                annotation_id = _annotation_id(annotation, ann_index)
                response_hash = sha256_json(annotation.get("result", []))
                key = (export_sha, project_id, task_id, _worker_id(annotation), annotation_id, response_hash)
                if key in records:
                    # Identical rows within one export are input repetition,
                    # not a second worker submission.
                    continue
                records[key] = {"annotation": annotation, "task": task, "export_path": export_path, "data": data}
    selected_records: list[tuple[dict[str, str], dict[str, Any]]] = []
    for row in registry_rows:
        source_sha = _safe_str(row.get("source_export_sha256"))
        project_id = _safe_str(row.get("project_id"))
        task_id = _safe_str(row.get("ls_runtime_task_id") or row.get("task_id"))
        worker_id = _safe_str(row.get("worker_id"))
        annotation_id = _safe_str(row.get("annotation_id") or row.get("raw_canonical_annotation_id"))
        response_hash = _safe_str(row.get("response_hash"))
        if not all((source_sha, project_id, task_id, worker_id, annotation_id, response_hash)):
            binding_blockers.append("canonical_registry_version_identity_missing")
            continue
        record = records.get((source_sha, project_id, task_id, worker_id, annotation_id, response_hash))
        if record is None:
            binding_blockers.append("canonical_registry_version_not_found")
            continue
        selected_records.append((row, record))
    if len(selected_records) != len(registry_rows):
        binding_blockers.append("canonical_registry_raw_binding_not_bijective")
    if len({str(row.get("canonical_annotation_id", "")) for row, _record in selected_records}) != len(selected_records):
        binding_blockers.append("canonical_registry_selected_identity_not_unique")
    disposition_rows = list(csv.DictReader(version_disposition_csv.open(encoding="utf-8-sig"))) if version_disposition_csv and version_disposition_csv.exists() else []
    disposition_by_version: dict[str, dict[str, str]] = {}
    allowed_dispositions = {"selected_canonical", "input_duplicate_folded", "unselected_forensic", "pending_review", "excluded_group", "forensic_only"}
    for disposition in disposition_rows:
        version_id = _safe_str(disposition.get("annotation_version_id"))
        if not version_id or version_id in disposition_by_version:
            binding_blockers.append("annotation_version_disposition_missing_or_duplicate")
        elif _safe_str(disposition.get("version_disposition")) not in allowed_dispositions:
            binding_blockers.append("annotation_version_disposition_invalid")
        else:
            disposition_by_version[version_id] = disposition
    raw_version_ids = {
        annotation_version_id(annotation_version_identity(stage, project, task, worker, annotation, response, export_sha))
        for export_sha, project, task, worker, annotation, response in records
    }
    if version_disposition_csv:
        if raw_version_ids != set(disposition_by_version):
            binding_blockers.append("annotation_version_disposition_raw_coverage_mismatch")
        selected_version_ids = {_safe_str(row.get("annotation_version_id")) for row in registry_rows}
        disposition_selected_ids = {key for key, row in disposition_by_version.items() if _safe_str(row.get("version_disposition")) == "selected_canonical"}
        if selected_version_ids != disposition_selected_ids:
            binding_blockers.append("annotation_version_disposition_selected_binding_mismatch")
    else:
        selected_raw_keys = {
            (_safe_str(row.get("source_export_sha256")), _safe_str(row.get("project_id")), _safe_str(row.get("ls_runtime_task_id") or row.get("task_id")), _safe_str(row.get("worker_id")), _safe_str(row.get("annotation_id") or row.get("raw_canonical_annotation_id")), _safe_str(row.get("response_hash")))
            for row in registry_rows
        }
        if set(records) != selected_raw_keys:
            binding_blockers.append("canonical_registry_raw_extra_row")
    meta_rows: list[dict[str, Any]] = []
    geometry_rows: list[dict[str, Any]] = []
    provenance_rows: list[dict[str, Any]] = []
    for row, record in selected_records:
        annotation, task, export_path, data = record["annotation"], record["task"], record["export_path"], record["data"]
        export_sha = sha256_file(export_path)
        task_id, project_id = _task_id(task, 0), _project_id(task)
        worker_id, annotation_id = _worker_id(annotation), _annotation_id(annotation, 0)
        status, reason, source = _eligibility([row])
        corners, polygon, choice_map, quality_all = extract_data(annotation.get("result", []))
        schema_ok, schema_reason = _schema(choice_map)
        if not schema_ok and status == "valid":
            status, reason = "invalid", schema_reason
        validity, allowed = formal_status(input_status, valid=status == "valid" and schema_ok and not binding_blockers)
        base_task_id = _safe_str(row.get("base_task_id") or data.get("base_task_id") or data.get("task_id") or task_id)
        dependencies = [export_path, canonical_csv] + ([version_disposition_csv] if version_disposition_csv else [])
        if row.get("independence_audit_snapshot_path"):
            dependencies.append(Path(row["independence_audit_snapshot_path"]))
        common = sidecar_common(source_artifact=str(export_path), source_sha256=export_sha, stage=stage, pool=_safe_str(row.get("dataset_group") or data.get("dataset_group")), condition=_safe_str(row.get("condition") or data.get("condition")), validity_status=validity, rule_version=RULE_VERSION, interpretation_allowed=allowed, dependency_paths=dependencies)
        independence_status = _safe_str(row.get("independence_status")) or "not_evaluable"
        geometry_eligible = status == "valid" and schema_ok and bool(len(corners))
        reliability_eligible = geometry_eligible and independence_status == "independent"
        raw_parent = annotation.get("parent_annotation") or annotation.get("parent_annotation_id")
        raw_parent_id = _safe_str(raw_parent.get("id") if isinstance(raw_parent, dict) else raw_parent)
        raw_parent_owner = _safe_str(
            (raw_parent.get("completed_by") or raw_parent.get("annotator_id")) if isinstance(raw_parent, dict) else annotation.get("parent_owner_id")
        )
        meta = {**common, "canonical_registry_sha256": registry_sha, "source_export_sha256": export_sha, "raw_export_sha256": export_sha, "response_hash": _safe_str(row.get("response_hash")), "annotation_version_id": _safe_str(row.get("annotation_version_id")), "task_id": _safe_str(row.get("task_id") or data.get("task_id") or task_id), "base_task_id": base_task_id, "scene_id": _safe_str(row.get("scene_label") or data.get("scene_id") or data.get("scene_label")), "dataset_group": common["pool"], "scene_label": _safe_str(row.get("scene_label") or data.get("scene_label")), "assigned_expected": _safe_str(row.get("assigned_expected")), "outside_assignment_submission": _safe_str(row.get("outside_assignment_submission")), "parse_error": _safe_str(row.get("parse_error")), "active_time": _safe_str(row.get("active_time")), "active_time_source": _safe_str(row.get("active_time_source")), "primary_active_time_eligible": _safe_str(row.get("primary_active_time_eligible")), "task_final_scope": _safe_str(row.get("task_final_scope")), "independence_status": independence_status, "eligible_for_geometry_loo": str(geometry_eligible).lower(), "worker_reliability_eligible": str(reliability_eligible).lower(), "independence_audit_status": _safe_str(row.get("independence_audit_status")), "independence_audit_reason": _safe_str(row.get("independence_audit_reason")), "independence_audit_source": _safe_str(row.get("independence_audit_source")), "parent_annotation_id": _safe_str(row.get("parent_annotation_id")), "parent_owner_id": _safe_str(row.get("parent_owner_id")), "parent_cross_owner": _safe_str(row.get("parent_cross_owner")), "parent_derived": _safe_str(row.get("parent_derived")), "copy_risk_status": _safe_str(row.get("copy_risk_status")), "raw_parent_field_present": str(any(key in annotation for key in ("parent_annotation", "parent_annotation_id", "parent_owner_id"))).lower(), "raw_parent_annotation_id": raw_parent_id, "raw_parent_owner_id": raw_parent_owner, "raw_annotation_owner_id": worker_id, "project_id": project_id, "ls_runtime_task_id": task_id, "worker_id": worker_id, "annotation_id": annotation_id, "canonical_annotation_id": _safe_str(row.get("canonical_annotation_id")), "canonical_eligibility_status": status, "canonical_eligibility_reason": reason, "schema_interpretable": str(schema_ok).lower(), "schema_family": _safe_str(data.get("schema_family") or row.get("schema_family")), "schema_error": schema_reason, "schema_version": _safe_str(data.get("schema_version") or row.get("schema_version")), "ui_version": _safe_str(data.get("ui_version") or row.get("ui_version")), "instruction_version": _safe_str(data.get("instruction_version") or row.get("instruction_version")), "provenance_status": "", "prediction_selection_status": "", "initialization_artifact_id": "", "choice_map_json": json_text(choice_map), "raw_result_json": json_text(annotation.get("result", [])), "difficulty_present": str("difficulty" in choice_map).lower(), "model_issue_present": str("model_issue" in choice_map).lower(), "quality_all": quality_all, "geometry_hash": _safe_str(row.get("geometry_hash")), "n_corners": len(corners), "n_polygon_points": len(polygon), "raw_annotation_sha256": sha256_json(annotation)}
        meta["annotation_created_at"] = _safe_str(annotation.get("created_at"))
        meta["created_at"] = _safe_str(annotation.get("created_at"))
        meta["arrived_at"] = _safe_str(annotation.get("arrived_at") or annotation.get("created_at"))
        meta.update({key: _safe_str(row.get(key)) for key in ("duplicate_worker_task_submission", "duplicate_review_status", "duplicate_decision", "process_disposition", "timing_disposition", "reviewed_by", "reviewed_at", "independence_audit_source_sha256", "independence_audit_snapshot_path", "independence_audit_snapshot_sha256", "independence_audit_identity")})
        meta_rows.append(meta)
        geometry_rows.append({**common, "task_id": meta["task_id"], "base_task_id": base_task_id, "scene_id": meta["scene_id"], "project_id": project_id, "worker_id": worker_id, "annotation_id": annotation_id, "canonical_annotation_id": meta["canonical_annotation_id"], "canonical_eligibility_status": status, "eligible_for_geometry_loo": str(geometry_eligible).lower(), "worker_reliability_eligible": str(reliability_eligible).lower(), "schema_version": meta["schema_version"], "geometry_hash": meta["geometry_hash"], "width": 1024, "height": 512, "corners_px": corners.tolist(), "polygon_points_px": polygon, "geometry_source": "label_studio_annotation_result"})
    if not binding_blockers:
        task_seen: set[tuple[str, str, str]] = set()
        for _row, record in selected_records:
            task = record["task"]
            export_path = record["export_path"]
            task_key = (sha256_file(export_path), _project_id(task), _task_id(task, 0))
            if task_key in task_seen:
                continue
            task_seen.add(task_key)
            data = record["data"]
            provenance_rows.extend(_provenance(task, export_path, stage=stage, pool=_safe_str(data.get("dataset_group")), condition=_safe_str(data.get("condition")), input_status=input_status))
        if {str(row.get("canonical_annotation_id", "")) for row in meta_rows} != set(canonical_ids):
            binding_blockers.append("canonical_meta_registry_set_mismatch")
        if {str(row.get("canonical_annotation_id", "")) for row in geometry_rows} != set(canonical_ids):
            binding_blockers.append("canonical_geometry_registry_set_mismatch")
    if binding_blockers:
        meta_rows, geometry_rows, provenance_rows = [], [], []
    meta_fields = ["canonical_registry_sha256", "source_export_sha256", "raw_export_sha256", "response_hash", "annotation_version_id", "task_id", "base_task_id", "scene_id", "dataset_group", "scene_label", "annotation_created_at", "created_at", "arrived_at", "assigned_expected", "outside_assignment_submission", "parse_error", "active_time", "active_time_source", "primary_active_time_eligible", "task_final_scope", "independence_status", "eligible_for_geometry_loo", "worker_reliability_eligible", "independence_audit_status", "independence_audit_reason", "independence_audit_source", "parent_annotation_id", "parent_owner_id", "parent_cross_owner", "parent_derived", "copy_risk_status", "raw_parent_field_present", "raw_parent_annotation_id", "raw_parent_owner_id", "raw_annotation_owner_id", "project_id", "ls_runtime_task_id", "worker_id", "annotation_id", "canonical_annotation_id", "canonical_eligibility_status", "canonical_eligibility_reason", "schema_interpretable", "schema_family", "schema_error", "schema_version", "ui_version", "instruction_version", "provenance_status", "prediction_selection_status", "initialization_artifact_id", "choice_map_json", "raw_result_json", "difficulty_present", "model_issue_present", "quality_all", "geometry_hash", "n_corners", "n_polygon_points", "raw_annotation_sha256"]
    meta_fields += ["duplicate_worker_task_submission", "duplicate_review_status", "duplicate_decision", "process_disposition", "timing_disposition", "reviewed_by", "reviewed_at", "independence_audit_source_sha256", "independence_audit_snapshot_path", "independence_audit_snapshot_sha256", "independence_audit_identity"]
    write_csv_rows(output_dir / "c1_canonical_meta_observations.csv", meta_rows, COMMON_SIDEcar_FIELDS + meta_fields)
    output_dir.mkdir(parents=True, exist_ok=True)
    with (output_dir / "c1_canonical_geometry.jsonl").open("w", encoding="utf-8") as handle:
        for row in geometry_rows:
            handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
    write_csv_rows(output_dir / "c1_model_artifact_provenance.csv", provenance_rows, COMMON_SIDEcar_FIELDS + ["logical_task_id", "ls_runtime_task_id", "project_id", "task_id", "prediction_index", "artifact_kind", "prediction_selection_status", "initialization_artifact_id", "model_version", "checkpoint_sha256", "inference_config_sha256", "preprocess_postprocess_sha256", "prediction_payload_hash", "initial_geometry_hash", "prediction_result_present", "provenance_status"])
    return {"schema_version": "paper_a_vfinal_sidecar_v3", "rule_version": RULE_VERSION, "input_status": input_status, "n_meta_observations": len(meta_rows), "n_geometry_rows": len(geometry_rows), "n_model_provenance_rows": len(provenance_rows), "n_annotation_version_dispositions": len(disposition_rows), "annotation_version_disposition_csv": str(version_disposition_csv or ""), "annotation_version_disposition_sha256": sha256_file(version_disposition_csv) if version_disposition_csv and version_disposition_csv.exists() else "", "formal_c1_annotation_data_present": bool(meta_rows) and input_status == "formal", "interpretation_allowed": False, "dry_run": input_status != "formal", "canonical_registry_bijection_valid": not binding_blockers, "blockers": sorted(set(binding_blockers))}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Materialize C1 canonical evidence sidecars.")
    parser.add_argument("--export-json", action="append", required=True, type=Path)
    parser.add_argument("--canonical-csv", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--input-status", choices=["dry_run", "formal"], default="dry_run")
    parser.add_argument("--version-disposition-csv", type=Path)
    args = parser.parse_args(argv)
    print(json.dumps(materialize_canonical_evidence(args.export_json, args.canonical_csv, args.output_dir, input_status=args.input_status, version_disposition_csv=args.version_disposition_csv), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
