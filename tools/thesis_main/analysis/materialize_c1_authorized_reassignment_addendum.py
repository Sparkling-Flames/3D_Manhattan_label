"""Materialize the immutable W014 authorized-reassignment addendum."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from pathlib import Path
from typing import Any

from tools.thesis_main.analysis.c1_authorized_reassignment import FIELDS, assignment_row_sha256


def _read(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as stream:
        return list(csv.DictReader(stream))


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build_rows(plan_rows: list[dict[str, str]], assignment_sources: list[tuple[Path, list[dict[str, str]]]], runtime_rows: list[dict[str, str]], *, expected_w034: int = 17, expected_w001: int = 3) -> list[dict[str, str]]:
    originals: dict[tuple[str, str], tuple[dict[str, str], str]] = {}
    for path, rows in assignment_sources:
        digest = _sha(path)
        for row in rows:
            key = (str(row.get("worker_id", "")), str(row.get("base_task_id", "")))
            if key in originals:
                raise ValueError(f"duplicate original worker-base assignment:{key}")
            originals[key] = (row, digest)
    runtime = {
        (str(row.get("project_id", "")), str(row.get("ls_runtime_task_id") or row.get("runtime_task_id") or "")): row
        for row in runtime_rows
    }
    output = []
    seen: set[tuple[str, str]] = set()
    for plan in plan_rows:
        displaced = str(plan.get("displaced_worker_id", ""))
        replacement = str(plan.get("replacement_worker_id", ""))
        base = str(plan.get("base_task_id", ""))
        if displaced != "14" or replacement not in {"34", "1"}:
            raise ValueError("Paper A addendum only permits W014 -> W034/W001")
        original_source = originals.get((displaced, base))
        if original_source is None:
            raise ValueError(f"W014 original assignment missing:{base}")
        original, source_sha = original_source
        if "anchor" in str(original.get("dataset_group", "")).lower():
            raise ValueError("W014 common anchors are not replacement tasks")
        project = str(plan.get("replacement_project_id", ""))
        task = str(plan.get("replacement_runtime_task_id", ""))
        mapped = runtime.get((project, task))
        if mapped is None:
            raise ValueError("replacement runtime mapping missing")
        if any(str(mapped.get(field, "")) != str(original.get(field, "")) for field in ("task_id", "base_task_id", "dataset_group")):
            raise ValueError("replacement runtime does not bind the W014 original row")
        unique = (replacement, base)
        if unique in seen:
            raise ValueError("duplicate replacement worker-base edge")
        seen.add(unique)
        condition = str(plan.get("condition") or mapped.get("condition") or ("semi" if "semi" in str(original.get("dataset_group", "")).lower() else "manual")).lower()
        active_expected = str(plan.get("active_time_expected", "false")).lower()
        if replacement == "34" and active_expected not in {"true", "1", "yes"}:
            raise ValueError("W034 authorized extension requires active_time_expected=true for all 17 rows")
        row = {
            "round_id": "C1", "condition": condition,
            "dataset_group": str(original.get("dataset_group", "")), "task_id": str(original.get("task_id", "")),
            "base_task_id": base, "displaced_worker_id": displaced, "replacement_worker_id": replacement,
            "original_assignment_manifest_sha256": source_sha,
            "original_assignment_row_sha256": assignment_row_sha256(original),
            "authorization_reason": str(plan.get("authorization_reason", "")),
            "authorized_by": str(plan.get("authorized_by", "")), "authorized_at": str(plan.get("authorized_at", "")),
            "replacement_project_id": project, "replacement_runtime_task_id": task,
            "active_time_expected": "true" if replacement == "34" else active_expected,
        }
        if any(not row[field] for field in FIELDS):
            raise ValueError("authorized addendum rows require every contract field")
        output.append(row)
    counts = {worker: sum(row["replacement_worker_id"] == worker for row in output) for worker in ("34", "1")}
    if counts != {"34": expected_w034, "1": expected_w001}:
        raise ValueError(f"authorized addendum count mismatch:{counts}")
    return output


def materialize(plan_csv: Path, assignment_paths: list[Path], runtime_csv: Path, output_csv: Path, *, expected_w034: int = 17, expected_w001: int = 3) -> dict[str, Any]:
    rows = build_rows(_read(plan_csv), [(path, _read(path)) for path in assignment_paths], _read(runtime_csv), expected_w034=expected_w034, expected_w001=expected_w001)
    output_csv.parent.mkdir(parents=True, exist_ok=True)
    with output_csv.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(FIELDS)); writer.writeheader(); writer.writerows(rows)
    freeze = {
        "schema_version": "c1_authorized_reassignment_freeze_v1",
        "row_count": len(rows), "w034_row_count": sum(row["replacement_worker_id"] == "34" for row in rows),
        "w001_row_count": sum(row["replacement_worker_id"] == "1" for row in rows),
        "authorization_plan_sha256": _sha(plan_csv), "authorized_reassignment_manifest_sha256": _sha(output_csv),
    }
    output_csv.with_suffix(".freeze.json").write_text(json.dumps(freeze, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return freeze


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--authorization-plan", type=Path, required=True)
    parser.add_argument("--original-assignment", action="append", type=Path, required=True)
    parser.add_argument("--runtime-mapping", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--expected-w034", type=int, default=17)
    parser.add_argument("--expected-w001", type=int, default=3)
    args = parser.parse_args()
    print(json.dumps(materialize(args.authorization_plan, args.original_assignment, args.runtime_mapping, args.output, expected_w034=args.expected_w034, expected_w001=args.expected_w001), indent=2))


if __name__ == "__main__":
    main()
