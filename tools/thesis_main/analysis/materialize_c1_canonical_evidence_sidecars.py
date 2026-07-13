from __future__ import annotations

import argparse
import csv
import json
from collections import defaultdict
from pathlib import Path
from typing import Any

from tools.thesis_main.analysis.prescreen_canonicalize_export import _annotation_id, _data, _project_id, _safe_str, _task_id, _worker_id
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


def _canonical_rows(path: Path) -> dict[tuple[str, str, str, str, str], list[dict[str, str]]]:
    with path.open("r", newline="", encoding="utf-8-sig") as handle:
        rows = list(csv.DictReader(handle))
    indexed: dict[tuple[str, str, str, str, str], list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        key = (
            str(row.get("source_export", "")), str(row.get("project_id", "")),
            str(row.get("ls_runtime_task_id") or row.get("task_id", "")), str(row.get("worker_id", "")),
            str(row.get("raw_canonical_annotation_id") or row.get("annotation_id", "")),
        )
        indexed[key].append(row)
    return indexed


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
    if independence != "independent":
        return "invalid", "independence_not_evaluable", row
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
        fields = {
            "initialization_artifact_id": _safe_str(prediction.get("initialization_artifact_id") or prediction.get("id")),
            "model_version": _safe_str(prediction.get("model_version") or prediction.get("version")),
            "checkpoint_sha256": _safe_str(prediction.get("checkpoint_sha256") or prediction.get("checkpoint_hash")),
            "inference_config_sha256": _safe_str(prediction.get("inference_config_sha256") or prediction.get("config_sha256") or prediction.get("config_hash")),
            "preprocess_postprocess_sha256": _safe_str(prediction.get("preprocess_postprocess_sha256") or prediction.get("preprocess_sha256") or prediction.get("preprocess_hash")),
            "prediction_payload_hash": sha256_json(prediction),
        }
        complete = all(fields.values())
        status, allowed = formal_status(input_status, valid=complete)
        rows.append({**sidecar_common(source_artifact=str(export_path), source_sha256=sha256_file(export_path), stage=stage, pool=pool, condition=condition, validity_status=status, rule_version=RULE_VERSION, interpretation_allowed=allowed), "logical_task_id": _safe_str(data.get("task_id") or data.get("base_task_id")), "ls_runtime_task_id": _task_id(task, 0), "project_id": _project_id(task), "task_id": _safe_str(data.get("task_id") or data.get("base_task_id")), "prediction_index": index, "artifact_kind": "prediction", "prediction_selection_status": "selected_unique" if len(predictions) == 1 else "selected_by_artifact_id", "prediction_result_present": str(isinstance(prediction.get("result"), list)).lower(), "provenance_status": "complete" if complete else "incomplete", **fields})
    return rows


def materialize_canonical_evidence(export_paths: list[Path], canonical_csv: Path, output_dir: Path, *, stage: str = "C1", input_status: str = "dry_run") -> dict[str, Any]:
    registry_sha = sha256_file(canonical_csv)
    canonical = _canonical_rows(canonical_csv)
    meta_rows: list[dict[str, Any]] = []
    geometry_rows: list[dict[str, Any]] = []
    provenance_rows: list[dict[str, Any]] = []
    for export_path in export_paths:
        export_sha = sha256_file(export_path)
        for task_index, task in enumerate(_load_tasks(export_path), 1):
            task_id, project_id, data = _task_id(task, task_index), _project_id(task), _data(task)
            task_provenance = _provenance(task, export_path, stage=stage, pool=_safe_str(data.get("dataset_group")), condition=_safe_str(data.get("condition")), input_status=input_status)
            provenance_rows.extend(task_provenance)
            provenance_summary = task_provenance[0] if task_provenance else {}
            for ann_index, annotation in enumerate(task.get("annotations") or [], 1):
                if not isinstance(annotation, dict):
                    continue
                worker_id, annotation_id = _worker_id(annotation), _annotation_id(annotation, ann_index)
                status, reason, source = _eligibility(canonical.get((str(export_path), project_id, task_id, worker_id, annotation_id), []))
                corners, polygon, choice_map, quality_all = extract_data(annotation.get("result", []))
                schema_ok, schema_reason = _schema(choice_map)
                if not schema_ok and status == "valid":
                    status, reason = "invalid", schema_reason
                validity, allowed = formal_status(input_status, valid=status == "valid" and schema_ok)
                base_task_id = _safe_str(source.get("base_task_id") or data.get("base_task_id") or data.get("task_id") or task_id)
                dependencies = [export_path, canonical_csv]
                if source.get("independence_audit_snapshot_path"):
                    dependencies.append(Path(source["independence_audit_snapshot_path"]))
                common = sidecar_common(source_artifact=str(export_path), source_sha256=export_sha, stage=stage, pool=_safe_str(source.get("dataset_group") or data.get("dataset_group")), condition=_safe_str(source.get("condition") or data.get("condition")), validity_status=validity, rule_version=RULE_VERSION, interpretation_allowed=allowed, dependency_paths=dependencies)
                meta = {**common, "canonical_registry_sha256": registry_sha, "source_export_sha256": export_sha, "task_id": _safe_str(source.get("task_id") or data.get("task_id") or task_id), "base_task_id": base_task_id, "scene_id": _safe_str(source.get("scene_label") or data.get("scene_id") or data.get("scene_label")), "dataset_group": common["pool"], "scene_label": _safe_str(source.get("scene_label") or data.get("scene_label")), "assigned_expected": _safe_str(source.get("assigned_expected")), "outside_assignment_submission": _safe_str(source.get("outside_assignment_submission")), "parse_error": _safe_str(source.get("parse_error")), "active_time": _safe_str(source.get("active_time")), "active_time_source": _safe_str(source.get("active_time_source")), "primary_active_time_eligible": _safe_str(source.get("primary_active_time_eligible")), "task_final_scope": _safe_str(source.get("task_final_scope")), "independence_status": _safe_str(source.get("independence_status")) or "not_evaluable", "independence_audit_status": _safe_str(source.get("independence_audit_status")), "independence_audit_reason": _safe_str(source.get("independence_audit_reason")), "independence_audit_source": _safe_str(source.get("independence_audit_source")), "parent_annotation_id": _safe_str(source.get("parent_annotation_id")), "parent_owner_id": _safe_str(source.get("parent_owner_id")), "parent_cross_owner": _safe_str(source.get("parent_cross_owner")), "parent_derived": _safe_str(source.get("parent_derived")), "copy_risk_status": _safe_str(source.get("copy_risk_status")), "project_id": project_id, "ls_runtime_task_id": task_id, "worker_id": worker_id, "annotation_id": annotation_id, "canonical_annotation_id": _safe_str(source.get("canonical_annotation_id")), "canonical_eligibility_status": status, "canonical_eligibility_reason": reason, "schema_interpretable": str(schema_ok).lower(), "schema_family": _safe_str(data.get("schema_family") or source.get("schema_family")), "schema_error": schema_reason, "schema_version": _safe_str(data.get("schema_version") or source.get("schema_version")), "ui_version": _safe_str(data.get("ui_version") or source.get("ui_version")), "instruction_version": _safe_str(data.get("instruction_version") or source.get("instruction_version")), "provenance_status": _safe_str(provenance_summary.get("provenance_status")), "prediction_selection_status": _safe_str(provenance_summary.get("prediction_selection_status")), "initialization_artifact_id": _safe_str(provenance_summary.get("initialization_artifact_id")), "choice_map_json": json_text(choice_map), "raw_result_json": json_text(annotation.get("result", [])), "difficulty_present": str("difficulty" in choice_map).lower(), "model_issue_present": str("model_issue" in choice_map).lower(), "quality_all": quality_all, "geometry_hash": _safe_str(source.get("geometry_hash")), "n_corners": len(corners), "n_polygon_points": len(polygon), "raw_annotation_sha256": sha256_json(annotation)}
                meta["annotation_created_at"] = _safe_str(annotation.get("created_at"))
                meta["created_at"] = _safe_str(annotation.get("created_at"))
                meta["arrived_at"] = _safe_str(annotation.get("arrived_at") or annotation.get("created_at"))
                meta.update({key: _safe_str(source.get(key)) for key in ("duplicate_worker_task_submission", "independence_audit_source_sha256", "independence_audit_snapshot_path", "independence_audit_snapshot_sha256", "independence_audit_identity")})
                meta_rows.append(meta)
                geometry_rows.append({**common, "task_id": meta["task_id"], "base_task_id": base_task_id, "scene_id": meta["scene_id"], "project_id": project_id, "worker_id": worker_id, "annotation_id": annotation_id, "canonical_annotation_id": meta["canonical_annotation_id"], "canonical_eligibility_status": status, "schema_version": meta["schema_version"], "geometry_hash": meta["geometry_hash"], "width": 1024, "height": 512, "corners_px": corners.tolist(), "polygon_points_px": polygon, "geometry_source": "label_studio_annotation_result"})
    meta_fields = ["canonical_registry_sha256", "source_export_sha256", "task_id", "base_task_id", "scene_id", "dataset_group", "scene_label", "annotation_created_at", "created_at", "arrived_at", "assigned_expected", "outside_assignment_submission", "parse_error", "active_time", "active_time_source", "primary_active_time_eligible", "task_final_scope", "independence_status", "independence_audit_status", "independence_audit_reason", "independence_audit_source", "parent_annotation_id", "parent_owner_id", "parent_cross_owner", "parent_derived", "copy_risk_status", "project_id", "ls_runtime_task_id", "worker_id", "annotation_id", "canonical_annotation_id", "canonical_eligibility_status", "canonical_eligibility_reason", "schema_interpretable", "schema_family", "schema_error", "schema_version", "ui_version", "instruction_version", "provenance_status", "prediction_selection_status", "initialization_artifact_id", "choice_map_json", "raw_result_json", "difficulty_present", "model_issue_present", "quality_all", "geometry_hash", "n_corners", "n_polygon_points", "raw_annotation_sha256"]
    meta_fields += ["duplicate_worker_task_submission", "independence_audit_source_sha256", "independence_audit_snapshot_path", "independence_audit_snapshot_sha256", "independence_audit_identity"]
    write_csv_rows(output_dir / "c1_canonical_meta_observations.csv", meta_rows, COMMON_SIDEcar_FIELDS + meta_fields)
    output_dir.mkdir(parents=True, exist_ok=True)
    with (output_dir / "c1_canonical_geometry.jsonl").open("w", encoding="utf-8") as handle:
        for row in geometry_rows:
            handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
    write_csv_rows(output_dir / "c1_model_artifact_provenance.csv", provenance_rows, COMMON_SIDEcar_FIELDS + ["logical_task_id", "ls_runtime_task_id", "project_id", "task_id", "prediction_index", "artifact_kind", "prediction_selection_status", "initialization_artifact_id", "model_version", "checkpoint_sha256", "inference_config_sha256", "preprocess_postprocess_sha256", "prediction_payload_hash", "prediction_result_present", "provenance_status"])
    return {"schema_version": "paper_a_vfinal_sidecar_v2", "rule_version": RULE_VERSION, "input_status": input_status, "n_meta_observations": len(meta_rows), "n_geometry_rows": len(geometry_rows), "n_model_provenance_rows": len(provenance_rows), "formal_c1_annotation_data_present": bool(meta_rows) and input_status == "formal", "interpretation_allowed": False, "dry_run": input_status != "formal"}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Materialize C1 canonical evidence sidecars.")
    parser.add_argument("--export-json", action="append", required=True, type=Path)
    parser.add_argument("--canonical-csv", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--input-status", choices=["dry_run", "formal"], default="dry_run")
    args = parser.parse_args(argv)
    print(json.dumps(materialize_canonical_evidence(args.export_json, args.canonical_csv, args.output_dir, input_status=args.input_status), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
