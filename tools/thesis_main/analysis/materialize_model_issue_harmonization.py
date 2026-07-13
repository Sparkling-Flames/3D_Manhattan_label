from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any

import numpy as np

from tools.thesis_main.analysis.geometry_consensus.representation import normalize_geometry
from tools.thesis_main.analysis.prescreen_canonicalize_export import _data, _project_id, _safe_str, _task_id
from tools.thesis_main.analysis.quality_core.choice_parser import extract_data
from tools.thesis_main.analysis.vfinal_artifact_utils import COMMON_SIDEcar_FIELDS, sha256_file, sidecar_common, write_csv_rows


RULE_VERSION = "model_issue_harmonization_v1"
JITTER_TOLERANCE = 0.002


def _load_tasks(path: Path) -> list[dict[str, Any]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    return [row for row in payload if isinstance(row, dict)] if isinstance(payload, list) else []


def _load_geometry(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _endpoint_distance(worker: dict[str, Any], initial: dict[str, Any], width: int, height: int) -> float | None:
    worker_pairs = worker.get("pairs") or []
    initial_pairs = initial.get("pairs") or []
    if len(worker_pairs) != len(initial_pairs) or not worker_pairs or not initial_pairs:
        return None
    remaining = list(initial_pairs)
    distances = []
    for left in worker_pairs:
        match_index = min(range(len(remaining)), key=lambda i: min(abs(left["x"] - remaining[i]["x"]), width - abs(left["x"] - remaining[i]["x"])))
        right = remaining.pop(match_index)
        distances.extend(
            [
                min(abs(left["x"] - right["x"]), width - abs(left["x"] - right["x"])) / width,
                abs(left["y_ceiling"] - right["y_ceiling"]) / height,
                abs(left["y_floor"] - right["y_floor"]) / height,
            ]
        )
    return float(max(distances)) if distances else None


def harmonize_model_issue(
    worker_corners: Any,
    initial_corners: Any,
    *,
    explicit_issue: str = "",
    jitter_tolerance: float = JITTER_TOLERANCE,
    width: int = 1024,
    height: int = 512,
) -> dict[str, Any]:
    worker = normalize_geometry(worker_corners, width=width, height=height)
    initial = normalize_geometry(initial_corners, width=width, height=height)
    explicit_issue = _safe_str(explicit_issue)
    if not initial.get("valid"):
        inferred = "not_evaluable"
        reason = "missing_or_invalid_initial_geometry"
        distance = None
    elif not worker.get("valid"):
        inferred = "not_evaluable"
        reason = "invalid_worker_geometry"
        distance = None
    elif worker["n_pairs"] != initial["n_pairs"]:
        inferred = "structural_edit_unresolved"
        reason = "pair_count_mismatch"
        distance = None
    else:
        distance = _endpoint_distance(worker, initial, width, height)
        if distance is None:
            inferred = "structural_edit_unresolved"
            reason = "endpoint_pairing_incomparable"
        elif distance > jitter_tolerance:
            inferred = "behavior_inferred_corner_drift"
            reason = "same_topology_moved_beyond_tolerance"
        else:
            inferred = "harmonized_acceptable"
            reason = "same_topology_within_tolerance"
    return {
        "initial_geometry_valid": bool(initial.get("valid")),
        "worker_geometry_valid": bool(worker.get("valid")),
        "initial_pair_count": int(initial.get("n_pairs", 0)),
        "worker_pair_count": int(worker.get("n_pairs", 0)),
        "max_endpoint_chebyshev_normalized": distance,
        "jitter_tolerance": jitter_tolerance,
        "inferred_issue": inferred,
        "inference_reason": reason,
        "explicit_issue": explicit_issue,
        "harmonized_issue": explicit_issue if explicit_issue and explicit_issue.lower() not in {"acceptable", "none"} else inferred,
        "explicit_issue_precedence": bool(explicit_issue and explicit_issue.lower() not in {"acceptable", "none"}),
        "interpretation_allowed": False,
    }


def materialize_model_issue_harmonization(
    export_paths: list[Path],
    geometry_jsonl: Path,
    output_dir: Path,
    *,
    quality_csv: Path | None = None,
    input_status: str = "dry_run",
) -> dict[str, Any]:
    geometry_rows = _load_geometry(geometry_jsonl)
    by_task = {(str(row.get("task_id")), str(row.get("worker_id"))): row for row in geometry_rows}
    explicit: dict[tuple[str, str], str] = {}
    if quality_csv and quality_csv.exists():
        with quality_csv.open("r", newline="", encoding="utf-8-sig") as handle:
            for row in csv.DictReader(handle):
                explicit[(str(row.get("task_id", "")), str(row.get("worker_id") or row.get("annotator_id", "")))] = str(row.get("model_issue_primary") or "").strip()
    rows = []
    source_sha = ";".join(sha256_file(path) for path in export_paths if path.exists())
    for export_path in export_paths:
        for index, task in enumerate(_load_tasks(export_path), start=1):
            task_id = _task_id(task, index)
            predictions = [prediction for prediction in task.get("predictions") or [] if isinstance(prediction, dict)]
            prediction = predictions[0] if predictions else {}
            initial_corners, _poly, _choices, _quality = extract_data(prediction.get("result", [])) if prediction else (np.empty((0, 2)), [], {}, "")
            for geometry_row in [
                row for row in geometry_rows
                if str(row.get("task_id")) == task_id and str(row.get("source_artifact", "")) == str(export_path)
            ]:
                worker_id = str(geometry_row.get("worker_id", ""))
                harmonized = harmonize_model_issue(geometry_row.get("corners_px") or [], initial_corners, explicit_issue=explicit.get((task_id, worker_id), ""))
                status = "dry_run" if input_status != "formal" else ("valid" if harmonized["inferred_issue"] != "not_evaluable" else "not_evaluable")
                rows.append(
                    {
                        **sidecar_common(source_artifact=str(export_path), source_sha256=source_sha, pool=str(geometry_row.get("pool", "")), condition=str(geometry_row.get("condition", "")), validity_status=status, rule_version=RULE_VERSION),
                        "task_id": task_id,
                        "worker_id": worker_id,
                        "canonical_annotation_id": geometry_row.get("canonical_annotation_id", ""),
                        "model_version": prediction.get("model_version", "") if prediction else "",
                        "prediction_payload_present": bool(prediction),
                        **harmonized,
                    }
                )
    write_csv_rows(output_dir / "model_issue_harmonization_C1.csv", rows, COMMON_SIDEcar_FIELDS + [
        "task_id", "worker_id", "canonical_annotation_id", "model_version", "prediction_payload_present",
        "initial_geometry_valid", "worker_geometry_valid", "initial_pair_count", "worker_pair_count",
        "max_endpoint_chebyshev_normalized", "jitter_tolerance", "inferred_issue", "inference_reason",
        "explicit_issue", "harmonized_issue", "explicit_issue_precedence",
    ])
    return {"n_rows": len(rows), "n_behavior_inferred_corner_drift": sum(row.get("inferred_issue") == "behavior_inferred_corner_drift" for row in rows), "dry_run": input_status != "formal", "interpretation_allowed": False}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Materialize model issue harmonization candidate sidecar.")
    parser.add_argument("--export-json", action="append", required=True, type=Path)
    parser.add_argument("--geometry-jsonl", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--quality-csv", type=Path)
    args = parser.parse_args(argv)
    print(json.dumps(materialize_model_issue_harmonization(args.export_json, args.geometry_jsonl, args.output_dir, quality_csv=args.quality_csv), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
