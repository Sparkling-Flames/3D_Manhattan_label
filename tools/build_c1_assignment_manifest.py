from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path


ADMITTED_VALUES = {"admitted", "pass", "passed", "true", "1", "yes", "y"}


def load_admitted_workers(path: Path) -> list[str]:
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        if not reader.fieldnames or "worker_id" not in reader.fieldnames:
            raise ValueError("admission csv must contain worker_id")
        has_status = "admission_status" in reader.fieldnames
        workers: list[str] = []
        for row in reader:
            worker_id = (row.get("worker_id") or "").strip()
            if not worker_id:
                continue
            if has_status:
                status = (row.get("admission_status") or "").strip().lower()
                if status not in ADMITTED_VALUES:
                    continue
            workers.append(worker_id)
    workers = sorted(set(workers))
    if not workers:
        raise ValueError("no admitted workers found")
    return workers


def load_manifest(path: Path) -> dict:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if "task_sets" not in payload:
        raise ValueError("calibration manifest must contain task_sets")
    task_sets = payload["task_sets"]
    for key in ("Calibration_anchor", "Calibration_core"):
        if key not in task_sets or not isinstance(task_sets[key], list):
            raise ValueError(f"calibration manifest missing task set: {key}")
    return payload


def normalize_task(task: dict, expected_group: str) -> dict:
    task_id = str(task.get("task_id") or "").strip()
    base_task_id = str(task.get("base_task_id") or "").strip()
    dataset_group = str(task.get("dataset_group") or expected_group).strip() or expected_group
    if not task_id:
        raise ValueError(f"task missing task_id in {expected_group}")
    if dataset_group != expected_group:
        raise ValueError(f"task {task_id} has dataset_group={dataset_group}, expected {expected_group}")
    return {
        "task_id": task_id,
        "base_task_id": base_task_id,
        "dataset_group": dataset_group,
    }


def build_rows(
    workers: list[str],
    manifest: dict,
    *,
    round_id: str,
    core_redundancy: int,
    manifest_version: str,
) -> list[dict[str, str]]:
    if core_redundancy < 1:
        raise ValueError("core_redundancy must be >= 1")
    if len(workers) < core_redundancy:
        raise ValueError("number of admitted workers is smaller than core_redundancy")

    rows: list[dict[str, str]] = []
    order_by_worker: dict[str, int] = {worker: 0 for worker in workers}

    anchors = [normalize_task(t, "Calibration_anchor") for t in manifest["task_sets"]["Calibration_anchor"]]
    cores = [normalize_task(t, "Calibration_core") for t in manifest["task_sets"]["Calibration_core"]]

    for task in anchors:
        for worker in workers:
            order_by_worker[worker] += 1
            rows.append(
                {
                    "round_id": round_id,
                    "worker_id": worker,
                    "task_id": task["task_id"],
                    "base_task_id": task["base_task_id"],
                    "dataset_group": task["dataset_group"],
                    "assignment_batch": "anchor_all",
                    "assignment_reason": "common_anchor",
                    "is_common_anchor": "true",
                    "expected_completion_order": str(order_by_worker[worker]),
                    "manifest_version": manifest_version,
                }
            )

    core_loads: dict[str, int] = {worker: 0 for worker in workers}
    for task in cores:
        chosen_workers: list[str] = []
        for _ in range(core_redundancy):
            available = [w for w in workers if w not in chosen_workers]
            chosen = min(available, key=lambda w: (core_loads[w], w))
            chosen_workers.append(chosen)
            core_loads[chosen] += 1
            order_by_worker[chosen] += 1
            rows.append(
                {
                    "round_id": round_id,
                    "worker_id": chosen,
                    "task_id": task["task_id"],
                    "base_task_id": task["base_task_id"],
                    "dataset_group": task["dataset_group"],
                    "assignment_batch": f"core_rr_k{core_redundancy}",
                    "assignment_reason": "balanced_core",
                    "is_common_anchor": "false",
                    "expected_completion_order": str(order_by_worker[chosen]),
                    "manifest_version": manifest_version,
                }
            )

    rows.sort(key=lambda r: (r["worker_id"], int(r["expected_completion_order"]), r["task_id"]))
    return rows


def write_rows(path: Path, rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "round_id",
        "worker_id",
        "task_id",
        "base_task_id",
        "dataset_group",
        "assignment_batch",
        "assignment_reason",
        "is_common_anchor",
        "expected_completion_order",
        "manifest_version",
    ]
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    parser = argparse.ArgumentParser(description="Build assignment_manifest_C1.csv from admission + calibration manifest.")
    parser.add_argument("--admission-csv", required=True, type=Path)
    parser.add_argument("--calibration-manifest", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--round-id", default="C1")
    parser.add_argument(
        "--core-redundancy",
        default=4,
        type=int,
        help="Operational target k for Calibration_core assignments; use 5 for the C1 over-assignment run.",
    )
    parser.add_argument("--manifest-version", default="v1")
    args = parser.parse_args()

    workers = load_admitted_workers(args.admission_csv)
    manifest = load_manifest(args.calibration_manifest)
    rows = build_rows(
        workers,
        manifest,
        round_id=args.round_id,
        core_redundancy=args.core_redundancy,
        manifest_version=args.manifest_version,
    )
    write_rows(args.output, rows)


if __name__ == "__main__":
    main()
