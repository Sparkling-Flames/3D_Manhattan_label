"""Materialize frozen T1/V1 failure dispositions without changing C2 state."""

from __future__ import annotations

import argparse
import csv
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from tools.thesis_main.analysis.failure_disposition import (
    t1_outcome_fields,
    text,
    v1_outcome_fields,
)


T1_FIELDS = [
    "task_id", "pair_id", "condition", "failure_attribution", "incident_id",
    "incident_evidence_status", "analysis_disposition", "iou_to_gt",
    "structurally_valid", "delivery_adjusted_quality", "quality_evaluable",
]
V1_FIELDS = [
    "task_id", "policy_arm", "failure_attribution", "incident_id",
    "incident_evidence_status", "analysis_disposition", "policy_terminal_status",
    "iou_to_gt", "rerun_of_task_id", "frozen_rule_version",
    "rerun_capacity_reservation_id", "itt_included", "policy_failure",
    "delivery_adjusted_quality",
]


def _required(row: dict[str, Any], *fields: str) -> None:
    missing = [field for field in fields if not text(row.get(field))]
    if missing:
        raise ValueError(f"missing required fields: {', '.join(missing)}")


def _row_with_fields(row: dict[str, Any], fields: dict[str, Any]) -> dict[str, Any]:
    return {**row, **fields}


def materialize_t1_rows(source_rows: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    output = []
    pairs: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in source_rows:
        _required(row, "task_id", "pair_id", "condition", "failure_attribution", "analysis_disposition")
        outcome = _row_with_fields(row, t1_outcome_fields(row))
        output.append(outcome)
        pairs[text(row.get("pair_id"))].append(outcome)

    for pair_id, rows in pairs.items():
        conditions = {text(row.get("condition")) for row in rows}
        if conditions != {"manual", "semi"}:
            raise ValueError(f"T1 pair {pair_id} must contain exactly manual and semi conditions")
        external = any(text(row.get("failure_attribution")) == "external_system_failure" for row in rows)
        if external:
            dispositions = {text(row.get("analysis_disposition")) for row in rows}
            if dispositions not in ({"rerun"}, {"administrative_censor"}, {"not_evaluable"}):
                raise ValueError(f"T1 external incident requires whole pair rerun or administrative censor: {pair_id}")

    counts = Counter(text(row.get("analysis_disposition")) for row in output)
    return output, {
        "n_rows": len(output),
        "administrative_censor_count": counts["administrative_censor"],
        "rerun_count": counts["rerun"],
        "not_evaluable_count": counts["not_evaluable"],
    }


def materialize_v1_rows(source_rows: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    output = []
    policy_failure_by_arm: Counter[str] = Counter()
    administrative_censor_by_arm: Counter[str] = Counter()
    not_evaluable_by_arm: Counter[str] = Counter()
    for row in source_rows:
        _required(row, "task_id", "policy_arm", "failure_attribution", "analysis_disposition")
        if text(row.get("analysis_disposition")) == "rerun":
            _required(row, "rerun_of_task_id", "frozen_rule_version", "rerun_capacity_reservation_id")
        outcome = _row_with_fields(row, v1_outcome_fields(row))
        arm = text(outcome["policy_arm"])
        if outcome["policy_failure"]:
            policy_failure_by_arm[arm] += 1
        if outcome["analysis_disposition"] == "administrative_censor":
            administrative_censor_by_arm[arm] += 1
        if outcome["analysis_disposition"] == "not_evaluable":
            not_evaluable_by_arm[arm] += 1
        output.append(outcome)
    return output, {
        "n_rows": len(output),
        "policy_failure_by_arm": dict(sorted(policy_failure_by_arm.items())),
        "administrative_censor_by_arm": dict(sorted(administrative_censor_by_arm.items())),
        "not_evaluable_by_arm": dict(sorted(not_evaluable_by_arm.items())),
    }


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", newline="", encoding="utf-8-sig") as handle:
        return list(csv.DictReader(handle))


def _write_csv(path: Path, rows: list[dict[str, Any]], fields: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def materialize(stage: str, input_csv: Path, output_dir: Path) -> dict[str, Any]:
    normalized_stage = stage.upper()
    rows = _read_csv(input_csv)
    if normalized_stage == "T1":
        output_rows, audit = materialize_t1_rows(rows)
        output_csv = output_dir / "t1_outcome_disposition.csv"
        fields = T1_FIELDS
    elif normalized_stage == "V1":
        output_rows, audit = materialize_v1_rows(rows)
        output_csv = output_dir / "v1_itt_outcome_disposition.csv"
        fields = V1_FIELDS
    else:
        raise ValueError("stage must be T1 or V1")
    _write_csv(output_csv, output_rows, fields)
    summary = {"stage": normalized_stage, "input_csv": str(input_csv), "output_csv": str(output_csv), "audit": audit}
    (output_dir / f"{normalized_stage.lower()}_failure_disposition_audit.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return summary


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Materialize frozen T1/V1 failure outcomes.")
    parser.add_argument("--stage", required=True, choices=("T1", "V1", "t1", "v1"))
    parser.add_argument("--input-csv", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    args = parser.parse_args(argv)
    print(json.dumps(materialize(args.stage, args.input_csv, args.output_dir), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
