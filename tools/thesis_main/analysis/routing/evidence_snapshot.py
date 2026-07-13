from __future__ import annotations

import argparse
import csv
import json
from collections import defaultdict
from pathlib import Path
from typing import Any, Iterable

from tools.thesis_main.analysis.vfinal_artifact_utils import COMMON_SIDEcar_FIELDS, eligible_independent_evidence, sha256_file, sha256_json, sidecar_common, write_csv_rows


RULE_VERSION = "sequential_routing_candidate_v1"


def _text(value: Any) -> str:
    return "" if value is None else str(value).strip()


def _truth(value: Any) -> bool:
    return _text(value).lower() in {"true", "1", "yes"}


def build_evidence_snapshot(
    task_rows: Iterable[dict[str, Any]],
    *,
    source_artifacts: list[str] | None = None,
    source_sha256: str = "",
    stage: str = "C1",
    input_status: str = "dry_run",
) -> list[dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in task_rows:
        grouped[_text(row.get("task_id"))].append(row)
    artifacts = source_artifacts or []
    source_text = ";".join(artifacts)
    rows = []
    for task_id, values in sorted(grouped.items()):
        eligible = [row for row in values if eligible_independent_evidence(row)]
        workers = {_text(row.get("worker_id") or row.get("annotator_id")) for row in eligible if _text(row.get("worker_id") or row.get("annotator_id"))}
        geometry_valid = sum(_truth(row.get("geometry_valid")) or (_text(row.get("geometry_hash")) and not _text(row.get("parse_error"))) for row in eligible)
        primary_active = sum(_truth(row.get("primary_active_time_eligible")) for row in eligible)
        explicit_issue = sum(bool(_text(row.get("model_issue_primary") or row.get("model_issue")) and _text(row.get("model_issue_primary") or row.get("model_issue")).lower() not in {"acceptable", "none"}) for row in eligible)
        snapshot = {
            "task_id": task_id,
            "base_task_id": _text(values[0].get("base_task_id")),
            "dataset_group": _text(values[0].get("dataset_group")),
            "condition": _text(values[0].get("condition")),
            "n_observations": len(values),
            "n_independent_workers": len(workers),
            "n_independence_not_evaluable": sum(_text(row.get("independence_status")) not in {"independent", "non_independent_confirmed"} for row in values),
            "n_non_independent_confirmed": sum(_text(row.get("independence_status")) == "non_independent_confirmed" for row in values),
            "n_invalid_geometry": sum(not _truth(row.get("geometry_valid")) for row in values),
            "n_invalid_schema": sum(_text(row.get("schema_interpretable")).lower() == "false" or bool(_text(row.get("schema_error"))) for row in values),
            "n_unassigned_or_duplicate": sum(not _truth(row.get("assigned_expected")) or _truth(row.get("outside_assignment_submission")) or _truth(row.get("duplicate_worker_task_submission")) for row in values),
            "geometry_valid_k": geometry_valid,
            "primary_active_time_k": primary_active,
            "explicit_issue_k": explicit_issue,
            "support_gap_candidate": len(workers) < 2,
            "evidence_complete_candidate": bool(workers and geometry_valid),
        }
        rows.append(
            {
                **sidecar_common(source_artifact=source_text, source_sha256=source_sha256, stage=stage, pool=snapshot["dataset_group"], condition=snapshot["condition"], validity_status="dry_run" if input_status != "formal" else "candidate_only", rule_version=RULE_VERSION),
                **snapshot,
                "snapshot_id": sha256_json(snapshot)[:20],
                "routing_eligible": "false",
                "interpretation_allowed": "false",
            }
        )
    return rows


def materialize_evidence_snapshot(input_csv: Path, output_csv: Path, *, input_status: str = "dry_run") -> dict[str, Any]:
    with input_csv.open("r", newline="", encoding="utf-8-sig") as handle:
        rows = list(csv.DictReader(handle))
    snapshots = build_evidence_snapshot(rows, source_artifacts=[str(input_csv)], source_sha256=sha256_file(input_csv), input_status=input_status)
    write_csv_rows(output_csv, snapshots, COMMON_SIDEcar_FIELDS + ["task_id", "base_task_id", "dataset_group", "condition", "n_observations", "n_independent_workers", "n_independence_not_evaluable", "n_non_independent_confirmed", "n_invalid_geometry", "n_invalid_schema", "n_unassigned_or_duplicate", "geometry_valid_k", "primary_active_time_k", "explicit_issue_k", "support_gap_candidate", "evidence_complete_candidate", "snapshot_id", "routing_eligible"])
    return {"n_tasks": len(snapshots), "dry_run": input_status != "formal", "routing_eligible": False}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Materialize candidate-only routing evidence snapshot.")
    parser.add_argument("--input-csv", required=True, type=Path)
    parser.add_argument("--output-csv", required=True, type=Path)
    args = parser.parse_args(argv)
    print(json.dumps(materialize_evidence_snapshot(args.input_csv, args.output_csv), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
