"""Build a result-blind, additive C1 assignment manifest for late entrants."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


FIELDS = [
    "round_id", "worker_id", "task_id", "base_task_id", "dataset_group", "condition",
    "assignment_provenance", "enrollment_batch", "enrolled_at", "P1_version",
    "instruction_version", "interface_version", "assignment_rule_version",
    "expected_completion_order", "active_time_expected",
]


def _read(path: Path | None) -> list[dict[str, str]]:
    if path is None or not path.exists():
        return []
    with path.open(encoding="utf-8-sig", newline="") as stream:
        return list(csv.DictReader(stream))


def _time(value: Any) -> datetime:
    parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _hash(seed: Any, *values: Any) -> str:
    return hashlib.sha256("|".join(map(str, (seed, *values))).encode()).hexdigest()


def build_rows(
    config: dict[str, Any], registry_rows: list[dict[str, str]], assignment_sources: list[tuple[Path, list[dict[str, str]]]],
    exposure_rows: list[dict[str, str]],
) -> list[dict[str, Any]]:
    if config.get("rolling_enrollment_activated") is not True:
        return []
    required = {
        "N_max", "recruitment_window_start", "recruitment_window_end", "latest_P1_start",
        "latest_C1_start", "latest_C2_entry", "activation_recorded_at", "frozen_seed",
        "workload_by_dataset_group", "assignment_rule_version", "instruction_version", "interface_version",
        "P1_version",
    }
    missing = sorted(field for field in required if config.get(field) is None or config.get(field) == "")
    if missing:
        raise ValueError("rolling enrollment config missing:" + ",".join(missing))
    if config.get("stage3_frozen") is True or config.get("validation_roster_frozen") is True:
        raise ValueError("late entry forbidden after Stage 3 or validation roster freeze")
    activated = _time(config["activation_recorded_at"])
    recruitment_start = _time(config["recruitment_window_start"])
    recruitment_end = _time(config["recruitment_window_end"])
    latest_p1 = _time(config["latest_P1_start"])
    latest_c1 = _time(config["latest_C1_start"])
    latest_c2 = _time(config["latest_C2_entry"])
    if not (recruitment_start <= activated <= recruitment_end):
        raise ValueError("rolling enrollment activation outside frozen recruitment window")
    if not (recruitment_start <= latest_p1 <= latest_c1 <= latest_c2):
        raise ValueError("rolling enrollment deadlines are not monotone")
    if activated > latest_c1:
        raise ValueError("rolling enrollment activated after latest C1 start")
    admitted = [
        row for row in registry_rows
        if str(row.get("admission_status", "")).lower().startswith(("pass", "admitted"))
        and str(row.get("worker_id", "")).strip()
    ]
    admitted.sort(key=lambda row: (row.get("enrolled_at", ""), row["worker_id"]))
    admitted = admitted[: int(config["N_max"])]
    for worker in admitted:
        if not worker.get("enrolled_at") or not worker.get("P1_started_at"):
            raise ValueError("late entrant requires enrolled_at and P1_started_at")
        if not recruitment_start <= _time(worker["enrolled_at"]) <= recruitment_end:
            raise ValueError("late entrant enrollment outside frozen window")
        if _time(worker["P1_started_at"]) > latest_p1:
            raise ValueError("late entrant P1 started after frozen deadline")
        if str(worker.get("P1_version", "")) != str(config["P1_version"]):
            raise ValueError("late entrant P1 version mismatch")
    exposures = {
        (str(row.get("worker_id", "")).strip(), str(row.get("base_task_id", "")).strip())
        for row in exposure_rows
    }
    tasks: dict[tuple[str, str, str], dict[str, str]] = {}
    anchors: dict[tuple[str, str, str], dict[str, str]] = {}
    for source, rows in assignment_sources:
        inferred = "semi" if "semi" in source.name.lower() else "manual"
        for row in rows:
            condition = str(row.get("condition") or inferred).lower()
            key = (str(row.get("base_task_id", "")), condition, str(row.get("dataset_group", "")))
            item = {**row, "condition": condition}
            tasks.setdefault(key, item)
            if "anchor" in key[2].lower():
                anchors.setdefault(key, item)
    support = Counter()
    output: list[dict[str, Any]] = []
    for worker in admitted:
        worker_id = worker["worker_id"]
        selected = list(anchors.values())
        for task in selected:
            if (worker_id, task["base_task_id"]) in exposures:
                raise ValueError(f"late entrant anchor exposure conflict:{worker_id}|{task['base_task_id']}")
        for group, count_raw in config["workload_by_dataset_group"].items():
            count = int(count_raw)
            candidates = [
                task for (_base, _condition, dataset_group), task in tasks.items()
                if dataset_group == group and "anchor" not in dataset_group.lower()
                and (worker_id, task["base_task_id"]) not in exposures
            ]
            candidates.sort(key=lambda task: (
                support[(task["base_task_id"], task["condition"])],
                _hash(config["frozen_seed"], worker_id, task["base_task_id"], task["condition"]),
            ))
            if len(candidates) < count:
                raise ValueError(f"insufficient exposure-clean late-entry tasks:{worker_id}|{group}")
            chosen = candidates[:count]
            selected.extend(chosen)
            for task in chosen:
                support[(task["base_task_id"], task["condition"])] += 1
        seen: set[tuple[str, str]] = set()
        for order, task in enumerate(selected, 1):
            key = (task["base_task_id"], task["condition"])
            if key in seen:
                raise ValueError(f"duplicate late-entry worker-base-condition:{worker_id}|{key}")
            seen.add(key)
            output.append({
                "round_id": "C1", "worker_id": worker_id,
                "task_id": task.get("task_id", ""), "base_task_id": task["base_task_id"],
                "dataset_group": task.get("dataset_group", ""), "condition": task["condition"],
                "assignment_provenance": "late_entry_calibration_assignment",
                "enrollment_batch": worker.get("enrollment_batch", "late_entry"),
                "enrolled_at": worker.get("enrolled_at", ""), "P1_version": worker.get("P1_version", ""),
                "instruction_version": config["instruction_version"], "interface_version": config["interface_version"],
                "assignment_rule_version": config["assignment_rule_version"],
                "expected_completion_order": order, "active_time_expected": "true",
            })
    return output


def materialize(config_path: Path, registry_csv: Path, assignment_paths: list[Path], exposure_csv: Path, output_csv: Path) -> dict[str, Any]:
    config = json.loads(config_path.read_text(encoding="utf-8"))
    sources = [(path, _read(path)) for path in assignment_paths]
    rows = build_rows(config, _read(registry_csv), sources, _read(exposure_csv))
    output_csv.parent.mkdir(parents=True, exist_ok=True)
    with output_csv.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=FIELDS)
        writer.writeheader(); writer.writerows(rows)
    summary = {
        "schema_version": "c1_late_entry_assignment_manifest_v1",
        "rolling_enrollment_activated": config.get("rolling_enrollment_activated") is True,
        "row_count": len(rows), "worker_count": len({row["worker_id"] for row in rows}),
        "manifest_sha256": hashlib.sha256(output_csv.read_bytes()).hexdigest(),
        "input_sha256": {
            "config": hashlib.sha256(config_path.read_bytes()).hexdigest(),
            "cohort_registry": hashlib.sha256(registry_csv.read_bytes()).hexdigest(),
            "exposure_ledger": hashlib.sha256(exposure_csv.read_bytes()).hexdigest(),
            "original_assignment": {str(path): hashlib.sha256(path.read_bytes()).hexdigest() for path in assignment_paths},
        },
    }
    output_csv.with_suffix(".summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return summary


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--cohort-registry", type=Path, required=True)
    parser.add_argument("--original-assignment", action="append", type=Path, required=True)
    parser.add_argument("--exposure-ledger", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(materialize(args.config, args.cohort_registry, args.original_assignment, args.exposure_ledger, args.output), indent=2))


if __name__ == "__main__":
    main()
