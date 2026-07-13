from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any

from tools.thesis_main.analysis.geometry_consensus.representation import normalize_geometry
from tools.thesis_main.analysis.quality_core.choice_parser import extract_data
from tools.thesis_main.analysis.vfinal_artifact_utils import COMMON_SIDEcar_FIELDS, dependency_bundle, sha256_file, sidecar_common, write_csv_rows


RULE_VERSION = "model_issue_harmonization_v3"
JITTER_TOLERANCE = 0.002
FUTURE_SCHEMA_FAMILIES = {"c2_future_explicit_acceptable_v1"}
FUTURE_INSTRUCTION_VERSIONS = {"c2_future_explicit_acceptable_v1"}


def _distance(worker: dict[str, Any], initial: dict[str, Any]) -> tuple[float | None, str]:
    if worker.get("n_pairs") != initial.get("n_pairs") or not worker.get("pairs"):
        return None, "pair_count_or_topology_mismatch"
    values = []
    for shift in range(worker["n_pairs"]):
        errors = []
        for index, left in enumerate(worker["pairs"]):
            right = initial["pairs"][(index + shift) % worker["n_pairs"]]
            errors.extend([abs(left["x"] - right["x"]) / worker["width"], abs(left["y_ceiling"] - right["y_ceiling"]) / worker["height"], abs(left["y_floor"] - right["y_floor"]) / worker["height"]])
        values.append(max(errors))
    best = min(values)
    return (None, "cyclic_order_ambiguous") if values.count(best) != 1 else (best, "order_compatible")


def _is_future_schema(schema_family: str = "", ui_schema_version: str = "", instruction_version: str = "") -> bool:
    return str(schema_family).strip().lower() in FUTURE_SCHEMA_FAMILIES or str(instruction_version).strip().lower() in FUTURE_INSTRUCTION_VERSIONS


def _result(*, source: str, issue: str = "", reason: str, provenance: str, order: str, distance: float | None = None) -> dict[str, Any]:
    return {"assertion_source": source, "harmonized_issue": issue, "inference_reason": reason, "provenance_gate": provenance, "order_gate": order, "max_endpoint_chebyshev_normalized": distance, "interpretation_allowed": False}


def harmonize_model_issue(worker_corners: Any, initial_corners: Any, *, explicit_issue: str = "", condition: str = "semi", provenance_complete: bool = False, schema_family: str = "legacy", ui_schema_version: str = "", instruction_version: str = "", jitter_tolerance: float = JITTER_TOLERANCE, width: int = 1024, height: int = 512) -> dict[str, Any]:
    selected = [item.strip().lower() for item in str(explicit_issue).replace(",", ";").split(";") if item.strip()]
    concrete = [item for item in selected if item != "acceptable"]
    if "acceptable" in selected and concrete:
        return _result(source="not_evaluable", reason="acceptable_mutually_exclusive_schema_conflict", provenance="failed", order="not_run")
    if concrete:
        return _result(source="explicit_worker_label", issue=";".join(concrete), reason="explicit_concrete_issue", provenance="not_needed", order="not_needed")
    if "acceptable" not in selected:
        return _result(source="not_applicable", reason="no_explicit_model_issue_assertion", provenance="not_applicable", order="not_applicable")
    if _is_future_schema(schema_family, ui_schema_version, instruction_version):
        return _result(source="explicit_worker_label", issue="acceptable", reason="future_explicit_acceptable", provenance="not_needed", order="not_needed")
    if condition != "semi":
        return _result(source="not_applicable", reason="historical_acceptable_behavior_harmonization_only_for_semi", provenance="not_applicable", order="not_applicable")
    if not provenance_complete:
        return _result(source="not_evaluable", reason="missing_required_initialization", provenance="failed", order="not_run")
    worker, initial = normalize_geometry(worker_corners, width=width, height=height), normalize_geometry(initial_corners, width=width, height=height)
    if not worker.get("valid") or not initial.get("valid"):
        return _result(source="not_evaluable", reason="invalid_geometry", provenance="passed", order="not_run")
    distance, order = _distance(worker, initial)
    if distance is None:
        return _result(source="not_evaluable", reason=order, provenance="passed", order="failed")
    return _result(source="legacy_behavior_inferred", issue="acceptable" if distance <= jitter_tolerance else "corner_drift", reason="within_jitter" if distance <= jitter_tolerance else "beyond_jitter", provenance="passed", order="passed", distance=distance)


def materialize_model_issue_harmonization(export_paths: list[Path], geometry_jsonl: Path, output_dir: Path, *, retrospective_amendment_csv: Path | None = None, quality_csv: Path | None = None, input_status: str = "dry_run") -> dict[str, Any]:
    meta_path, provenance_path = output_dir / "c1_canonical_meta_observations.csv", output_dir / "c1_model_artifact_provenance.csv"
    meta = list(csv.DictReader(meta_path.open(encoding="utf-8-sig"))) if meta_path.exists() else []
    provenance = list(csv.DictReader(provenance_path.open(encoding="utf-8-sig"))) if provenance_path.exists() else []
    amendments = list(csv.DictReader(retrospective_amendment_csv.open(encoding="utf-8-sig"))) if retrospective_amendment_csv and retrospective_amendment_csv.exists() else []
    amendment_by_key = {(item.get("project_id", ""), item.get("ls_runtime_task_id", ""), item.get("initialization_artifact_id", "")): item for item in amendments}
    geometry = [json.loads(line) for line in geometry_jsonl.read_text(encoding="utf-8").splitlines() if line.strip()] if geometry_jsonl.exists() else []
    geometry_by_annotation = {row.get("canonical_annotation_id", ""): row for row in geometry}
    predictions_by_runtime_task: dict[str, list[dict[str, Any]]] = {}
    for export_path in export_paths:
        payload = json.loads(export_path.read_text(encoding="utf-8"))
        for task in payload if isinstance(payload, list) else []:
            predictions = [item for item in task.get("predictions") or [] if isinstance(item, dict)]
            if predictions:
                predictions_by_runtime_task[str(task.get("id", ""))] = predictions
    dependency_paths = [meta_path, geometry_jsonl, provenance_path, *export_paths, *([retrospective_amendment_csv] if retrospective_amendment_csv else [])]
    rows = []
    for row in meta:
        choices = json.loads(row.get("choice_map_json") or "{}")
        selected = choices.get("model_issue", [])
        explicit = ";".join(selected)
        source = geometry_by_annotation.get(row.get("canonical_annotation_id", ""), {})
        prov = next((item for item in provenance if item.get("canonical_annotation_id") == row.get("canonical_annotation_id") or ((item.get("logical_task_id") or item.get("task_id")) == row.get("task_id") and item.get("ls_runtime_task_id") == row.get("ls_runtime_task_id") and item.get("project_id") == row.get("project_id"))), {})
        prov_complete = prov.get("provenance_status") == "complete" and prov.get("prediction_selection_status") not in {"ambiguous_multiple_predictions", "missing"}
        amendment = amendment_by_key.get((row.get("project_id", ""), row.get("ls_runtime_task_id", ""), prov.get("initialization_artifact_id", "")), {})
        if amendment:
            required = ("model_version", "checkpoint_sha256", "inference_config_sha256", "preprocess_postprocess_sha256", "prediction_payload_json")
            prov_complete = all(amendment.get(field, "") for field in required)
        candidates = predictions_by_runtime_task.get(row.get("ls_runtime_task_id", ""), [])
        selected_prediction = next((item for item in candidates if str(item.get("initialization_artifact_id") or item.get("id")) == prov.get("initialization_artifact_id")), None) if prov.get("initialization_artifact_id") else (candidates[0] if len(candidates) == 1 else None)
        initial_payload = json.loads(amendment["prediction_payload_json"]) if amendment.get("prediction_payload_json") else (selected_prediction.get("result", []) if selected_prediction else [])
        initial = extract_data(initial_payload)[0]
        result = harmonize_model_issue(source.get("corners_px", []), initial, explicit_issue=explicit, condition=row.get("condition", ""), provenance_complete=prov_complete, schema_family=row.get("schema_family", "legacy"), ui_schema_version=row.get("ui_schema_version") or row.get("ui_version") or row.get("schema_version", ""), instruction_version=row.get("instruction_version", ""))
        rows.append({**sidecar_common(source_artifact=str(meta_path), source_sha256=sha256_file(meta_path), stage="C1", pool=row.get("dataset_group", ""), condition=row.get("condition", ""), validity_status="dry_run" if input_status != "formal" else ("valid" if result["assertion_source"] == "explicit_worker_label" else "not_evaluable"), rule_version=RULE_VERSION, interpretation_allowed=False, dependency_paths=dependency_paths), "task_id": row.get("task_id", ""), "base_task_id": row.get("base_task_id", ""), "project_id": row.get("project_id", ""), "ls_runtime_task_id": row.get("ls_runtime_task_id", ""), "worker_id": row.get("worker_id", ""), "canonical_annotation_id": row.get("canonical_annotation_id", ""), "raw_model_issue_json": json.dumps(selected), "initialization_artifact_id": prov.get("initialization_artifact_id", ""), "retrospective_amendment_status": "joined_exact_project_runtime_artifact" if amendment else "not_joined", "retrospective_amendment_source": str(retrospective_amendment_csv) if amendment else "", **result})
    write_csv_rows(output_dir / "model_issue_harmonization_C1.csv", rows, COMMON_SIDEcar_FIELDS + ["task_id", "base_task_id", "project_id", "ls_runtime_task_id", "worker_id", "canonical_annotation_id", "raw_model_issue_json", "initialization_artifact_id", "retrospective_amendment_status", "retrospective_amendment_source", "assertion_source", "harmonized_issue", "inference_reason", "provenance_gate", "order_gate", "max_endpoint_chebyshev_normalized"])
    return {"n_rows": len(rows), "n_behavior_inferred": sum(row["assertion_source"] == "legacy_behavior_inferred" for row in rows), "n_retrospective_amendments_joined": sum(bool(row["retrospective_amendment_source"]) for row in rows), "dry_run": input_status != "formal", "interpretation_allowed": False}


if __name__ == "__main__":
    raise SystemExit("Use materialize_model_issue_harmonization from canonicalization.")
