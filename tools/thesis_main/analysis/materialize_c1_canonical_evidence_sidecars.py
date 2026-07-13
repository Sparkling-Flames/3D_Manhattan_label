from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from tools.thesis_main.analysis.prescreen_canonicalize_export import (
    _annotation_id,
    _data,
    _project_id,
    _safe_str,
    _task_id,
    _worker_id,
)
from tools.thesis_main.analysis.quality_core.choice_parser import extract_data
from tools.thesis_main.analysis.vfinal_artifact_utils import (
    COMMON_SIDEcar_FIELDS,
    formal_status,
    json_text,
    sha256_file,
    sha256_json,
    sidecar_common,
    write_csv_rows,
)


RULE_VERSION = "c1_canonical_evidence_v1"


def _load_tasks(path: Path) -> list[dict[str, Any]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, list):
        raise ValueError(f"{path} must contain a Label Studio task-list export")
    return [row for row in payload if isinstance(row, dict)]


def _canonical_lookup(canonical_csv: Path) -> dict[tuple[str, str, str, str], dict[str, str]]:
    import csv

    with canonical_csv.open("r", newline="", encoding="utf-8-sig") as handle:
        rows = list(csv.DictReader(handle))
    return {
        (
            str(row.get("source_export", "")),
            str(row.get("project_id", "")),
            str(row.get("ls_runtime_task_id", "") or row.get("task_id", "")),
            str(row.get("worker_id", "")),
        ): row
        for row in rows
    }


def _prediction_rows(task: dict[str, Any]) -> list[dict[str, Any]]:
    predictions = task.get("predictions") or []
    return [prediction for prediction in predictions if isinstance(prediction, dict)]


def _model_provenance(
    task: dict[str, Any],
    *,
    source_export: Path,
    pool: str,
    condition: str,
    stage: str,
    input_status: str,
) -> list[dict[str, Any]]:
    predictions = _prediction_rows(task)
    if not predictions:
        status, allowed = formal_status(input_status, valid=False)
        return [
            {
                **sidecar_common(
                    source_artifact=str(source_export),
                    source_sha256=sha256_file(source_export),
                    stage=stage,
                    pool=pool,
                    condition=condition,
                    validity_status="not_applicable" if input_status == "formal" else status,
                    rule_version=RULE_VERSION,
                    interpretation_allowed=False,
                ),
                "task_id": _task_id(task, 0),
                "artifact_kind": "manual_or_no_prediction",
                "model_name": "",
                "model_version": "",
                "checkpoint_sha256": "",
                "config_sha256": "",
                "preprocess_sha256": "",
                "run_id": "",
                "prediction_payload_hash": "",
                "provenance_status": "not_applicable",
                "interpretation_allowed": str(bool(allowed and False)).lower(),
            }
        ]
    rows = []
    for index, prediction in enumerate(predictions, start=1):
        result = prediction.get("result")
        payload_hash = sha256_json(prediction)
        model_name = _safe_str(prediction.get("model_name") or prediction.get("model"))
        model_version = _safe_str(prediction.get("model_version") or prediction.get("version"))
        checkpoint = _safe_str(prediction.get("checkpoint_sha256") or prediction.get("checkpoint_hash"))
        config = _safe_str(prediction.get("config_sha256") or prediction.get("config_hash"))
        preprocess = _safe_str(prediction.get("preprocess_sha256") or prediction.get("preprocess_hash"))
        run_id = _safe_str(prediction.get("run_id") or prediction.get("id"))
        has_explicit_model = bool(model_name or model_version)
        has_hashes = bool(checkpoint and config and preprocess)
        if has_hashes:
            provenance_status = "complete"
        else:
            # A model/version without the immutable runtime hashes is still
            # legacy/incomplete provenance; never upgrade it to formal.
            provenance_status = "legacy_missing"
        status, allowed = formal_status(input_status, valid=provenance_status == "complete")
        rows.append(
            {
                **sidecar_common(
                    source_artifact=str(source_export),
                    source_sha256=sha256_file(source_export),
                    stage=stage,
                    pool=pool,
                    condition=condition,
                    validity_status=status if status != "valid" else "valid",
                    rule_version=RULE_VERSION,
                    interpretation_allowed=allowed,
                ),
                "task_id": _task_id(task, 0),
                "prediction_index": index,
                "artifact_kind": "prediction",
                "model_name": model_name,
                "model_version": model_version,
                "checkpoint_sha256": checkpoint,
                "config_sha256": config,
                "preprocess_sha256": preprocess,
                "run_id": run_id,
                "prediction_payload_hash": payload_hash,
                "prediction_result_present": str(isinstance(result, list)).lower(),
                "provenance_status": provenance_status,
                "interpretation_allowed": str(bool(allowed)).lower(),
            }
        )
    return rows


def materialize_canonical_evidence(
    export_paths: list[Path],
    canonical_csv: Path,
    output_dir: Path,
    *,
    stage: str = "C1",
    input_status: str = "dry_run",
) -> dict[str, Any]:
    lookup = _canonical_lookup(canonical_csv)
    meta_rows: list[dict[str, Any]] = []
    geometry_rows: list[dict[str, Any]] = []
    provenance_rows: list[dict[str, Any]] = []
    for export_path in export_paths:
        export_sha = sha256_file(export_path)
        for task_index, task in enumerate(_load_tasks(export_path), start=1):
            task_id = _task_id(task, task_index)
            project_id = _project_id(task)
            data = _data(task)
            pool = _safe_str(data.get("dataset_group"))
            condition = _safe_str(data.get("condition"))
            for ann_index, annotation in enumerate(task.get("annotations") or [], start=1):
                if not isinstance(annotation, dict):
                    continue
                worker_id = _worker_id(annotation)
                annotation_id = _annotation_id(annotation, ann_index)
                canonical = lookup.get((str(export_path), project_id, task_id, worker_id), {})
                if canonical and canonical.get("raw_canonical_annotation_id") not in {"", annotation_id}:
                    continue
                corners, polygon, choice_map, quality_all = extract_data(annotation.get("result", []))
                status, allowed = formal_status(input_status, valid=not bool(canonical.get("parse_error")))
                common = sidecar_common(
                    source_artifact=str(export_path),
                    source_sha256=export_sha,
                    stage=stage,
                    pool=pool,
                    condition=condition,
                    validity_status=status,
                    rule_version=RULE_VERSION,
                    interpretation_allowed=allowed,
                )
                common.update(
                    {
                        "task_id": task_id,
                        "base_task_id": _safe_str(data.get("base_task_id") or data.get("task_id") or task_id),
                        "project_id": project_id,
                        "worker_id": worker_id,
                        "annotation_id": annotation_id,
                        "canonical_annotation_id": canonical.get("canonical_annotation_id", ""),
                        "raw_canonical_annotation_id": canonical.get("raw_canonical_annotation_id", annotation_id),
                        "choice_map_json": json_text(choice_map),
                        "quality_all": quality_all,
                        "geometry_hash": canonical.get("geometry_hash", ""),
                        "parse_error": canonical.get("parse_error", ""),
                        "n_corners": int(len(corners)),
                        "n_polygon_points": int(len(polygon)),
                    }
                )
                meta_rows.append(common)
                geometry_rows.append(
                    {
                        **sidecar_common(
                            source_artifact=str(export_path),
                            source_sha256=export_sha,
                            stage=stage,
                            pool=pool,
                            condition=condition,
                            validity_status=status,
                            rule_version=RULE_VERSION,
                            interpretation_allowed=allowed,
                        ),
                        "task_id": task_id,
                        "base_task_id": _safe_str(data.get("base_task_id") or data.get("task_id") or task_id),
                        "project_id": project_id,
                        "worker_id": worker_id,
                        "annotation_id": annotation_id,
                        "canonical_annotation_id": canonical.get("canonical_annotation_id", ""),
                        "geometry_hash": canonical.get("geometry_hash", ""),
                        "width": 1024,
                        "height": 512,
                        "corners_px": corners.tolist(),
                        "polygon_points_px": polygon,
                        "geometry_source": "label_studio_annotation_result",
                    }
                )
            provenance_rows.extend(
                _model_provenance(
                    task,
                    source_export=export_path,
                    pool=pool,
                    condition=condition,
                    stage=stage,
                    input_status=input_status,
                )
            )

    ordered = COMMON_SIDEcar_FIELDS
    write_csv_rows(output_dir / "c1_canonical_meta_observations.csv", meta_rows, ordered + [
        "task_id", "base_task_id", "project_id", "worker_id", "annotation_id", "canonical_annotation_id",
        "raw_canonical_annotation_id", "choice_map_json", "quality_all", "geometry_hash", "parse_error",
        "n_corners", "n_polygon_points",
    ])
    output_dir.mkdir(parents=True, exist_ok=True)
    with (output_dir / "c1_canonical_geometry.jsonl").open("w", encoding="utf-8") as handle:
        for row in geometry_rows:
            handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
    write_csv_rows(output_dir / "c1_model_artifact_provenance.csv", provenance_rows, ordered + [
        "task_id", "prediction_index", "artifact_kind", "model_name", "model_version", "checkpoint_sha256",
        "config_sha256", "preprocess_sha256", "run_id", "prediction_payload_hash", "prediction_result_present",
        "provenance_status",
    ])
    return {
        "schema_version": "paper_a_vfinal_sidecar_v1",
        "rule_version": RULE_VERSION,
        "input_status": input_status,
        "n_meta_observations": len(meta_rows),
        "n_geometry_rows": len(geometry_rows),
        "n_model_provenance_rows": len(provenance_rows),
        "formal_c1_annotation_data_present": bool(meta_rows) and input_status == "formal",
        "interpretation_allowed": False,
        "dry_run": input_status != "formal",
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Materialize additive C1 canonical evidence sidecars.")
    parser.add_argument("--export-json", action="append", required=True, type=Path)
    parser.add_argument("--canonical-csv", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--input-status", choices=["dry_run", "formal"], default="dry_run")
    args = parser.parse_args(argv)
    print(json.dumps(materialize_canonical_evidence(args.export_json, args.canonical_csv, args.output_dir, input_status=args.input_status), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
