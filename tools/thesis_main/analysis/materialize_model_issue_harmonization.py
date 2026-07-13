from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any

from tools.thesis_main.analysis.geometry_consensus.representation import normalize_geometry
from tools.thesis_main.analysis.quality_core.choice_parser import extract_data
from tools.thesis_main.analysis.vfinal_artifact_utils import COMMON_SIDEcar_FIELDS, sha256_file, sidecar_common, write_csv_rows


RULE_VERSION = "model_issue_harmonization_v2"
JITTER_TOLERANCE = 0.002


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


def harmonize_model_issue(worker_corners: Any, initial_corners: Any, *, explicit_issue: str = "", condition: str = "semi", provenance_complete: bool = False, jitter_tolerance: float = JITTER_TOLERANCE, width: int = 1024, height: int = 512) -> dict[str, Any]:
    explicit = str(explicit_issue).strip().lower()
    if explicit:
        return {"assertion_source": "explicit_worker_label", "harmonized_issue": explicit, "inference_reason": "explicit_label_precedence", "provenance_gate": "not_needed", "order_gate": "not_needed", "max_endpoint_chebyshev_normalized": None, "interpretation_allowed": False}
    if condition != "semi":
        return {"assertion_source": "not_applicable", "harmonized_issue": "", "inference_reason": "manual_or_nonsemi_condition", "provenance_gate": "not_applicable", "order_gate": "not_applicable", "max_endpoint_chebyshev_normalized": None, "interpretation_allowed": False}
    if not provenance_complete:
        return {"assertion_source": "not_evaluable", "harmonized_issue": "", "inference_reason": "initialization_provenance_incomplete", "provenance_gate": "failed", "order_gate": "not_run", "max_endpoint_chebyshev_normalized": None, "interpretation_allowed": False}
    worker, initial = normalize_geometry(worker_corners, width=width, height=height), normalize_geometry(initial_corners, width=width, height=height)
    if not worker.get("valid") or not initial.get("valid"):
        return {"assertion_source": "not_evaluable", "harmonized_issue": "", "inference_reason": "invalid_geometry", "provenance_gate": "passed", "order_gate": "not_run", "max_endpoint_chebyshev_normalized": None, "interpretation_allowed": False}
    distance, order = _distance(worker, initial)
    if distance is None:
        return {"assertion_source": "not_evaluable", "harmonized_issue": "", "inference_reason": order, "provenance_gate": "passed", "order_gate": "failed", "max_endpoint_chebyshev_normalized": None, "interpretation_allowed": False}
    return {"assertion_source": "legacy_behavior_inferred", "harmonized_issue": "acceptable" if distance <= jitter_tolerance else "corner_drift", "inference_reason": "within_jitter" if distance <= jitter_tolerance else "beyond_jitter", "provenance_gate": "passed", "order_gate": "passed", "max_endpoint_chebyshev_normalized": distance, "interpretation_allowed": False}


def materialize_model_issue_harmonization(export_paths: list[Path], geometry_jsonl: Path, output_dir: Path, *, quality_csv: Path | None = None, input_status: str = "dry_run") -> dict[str, Any]:
    meta_path, provenance_path = output_dir / "c1_canonical_meta_observations.csv", output_dir / "c1_model_artifact_provenance.csv"
    meta = list(csv.DictReader(meta_path.open(encoding="utf-8-sig"))) if meta_path.exists() else []
    provenance = {row.get("task_id", ""): row for row in csv.DictReader(provenance_path.open(encoding="utf-8-sig")) if row.get("provenance_status") == "complete"} if provenance_path.exists() else {}
    geometry = [json.loads(line) for line in geometry_jsonl.read_text(encoding="utf-8").splitlines() if line.strip()] if geometry_jsonl.exists() else []
    geometry_by_annotation = {row.get("canonical_annotation_id", ""): row for row in geometry}
    initial_by_runtime_task: dict[str, Any] = {}
    for export_path in export_paths:
        payload = json.loads(export_path.read_text(encoding="utf-8"))
        for task in payload if isinstance(payload, list) else []:
            predictions = [item for item in task.get("predictions") or [] if isinstance(item, dict)]
            if predictions:
                initial_by_runtime_task[str(task.get("id", ""))] = extract_data(predictions[0].get("result", []))[0]
    rows = []
    for row in meta:
        choices = json.loads(row.get("choice_map_json") or "{}")
        selected = choices.get("model_issue", [])
        explicit = ";".join(selected)
        source = geometry_by_annotation.get(row.get("canonical_annotation_id", ""), {})
        result = harmonize_model_issue(source.get("corners_px", []), initial_by_runtime_task.get(row.get("ls_runtime_task_id", ""), []), explicit_issue=explicit, condition=row.get("condition", ""), provenance_complete=row.get("task_id", "") in provenance)
        rows.append({**sidecar_common(source_artifact=str(meta_path), source_sha256=sha256_file(meta_path), stage="C1", pool=row.get("dataset_group", ""), condition=row.get("condition", ""), validity_status="dry_run" if input_status != "formal" else ("valid" if result["assertion_source"] == "explicit_worker_label" else "not_evaluable"), rule_version=RULE_VERSION, interpretation_allowed=False), "task_id": row.get("task_id", ""), "base_task_id": row.get("base_task_id", ""), "worker_id": row.get("worker_id", ""), "canonical_annotation_id": row.get("canonical_annotation_id", ""), "raw_model_issue_json": json.dumps(selected), "initialization_artifact_id": provenance.get(row.get("task_id", ""), {}).get("initialization_artifact_id", ""), **result})
    write_csv_rows(output_dir / "model_issue_harmonization_C1.csv", rows, COMMON_SIDEcar_FIELDS + ["task_id", "base_task_id", "worker_id", "canonical_annotation_id", "raw_model_issue_json", "initialization_artifact_id", "assertion_source", "harmonized_issue", "inference_reason", "provenance_gate", "order_gate", "max_endpoint_chebyshev_normalized"])
    return {"n_rows": len(rows), "n_behavior_inferred": sum(row["assertion_source"] == "legacy_behavior_inferred" for row in rows), "dry_run": input_status != "formal", "interpretation_allowed": False}


if __name__ == "__main__":
    raise SystemExit("Use materialize_model_issue_harmonization from canonicalization.")
