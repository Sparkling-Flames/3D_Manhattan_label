from __future__ import annotations

import csv
import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "tools" / "thesis_main" / "registry" / "build_c1_assignment_manifest.py"


def write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, str]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def test_build_c1_assignment_manifest(tmp_path: Path) -> None:
    admission_csv = tmp_path / "admission.csv"
    write_csv(
        admission_csv,
        ["worker_id", "admission_status"],
        [
            {"worker_id": "worker_b", "admission_status": "admitted"},
            {"worker_id": "worker_a", "admission_status": "admitted"},
            {"worker_id": "worker_watch", "admission_status": "pass_with_watch"},
            {"worker_id": "worker_c", "admission_status": "failed"},
        ],
    )

    manifest_json = tmp_path / "calibration_manifest.json"
    manifest_json.write_text(
        json.dumps(
            {
                "task_sets": {
                    "Calibration_anchor": [
                        {"task_id": "anchor_01", "base_task_id": "base_a1", "dataset_group": "Calibration_anchor"}
                    ],
                    "Calibration_core": [
                        {"task_id": "core_01", "base_task_id": "base_c1", "dataset_group": "Calibration_core"},
                        {"task_id": "core_02", "base_task_id": "base_c2", "dataset_group": "Calibration_core"},
                    ],
                    "Calibration_reserve": [],
                }
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    output_csv = tmp_path / "assignment_manifest_C1.csv"
    subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--admission-csv",
            str(admission_csv),
            "--calibration-manifest",
            str(manifest_json),
            "--output",
            str(output_csv),
            "--core-redundancy",
            "2",
        ],
        check=True,
    )

    with output_csv.open("r", encoding="utf-8", newline="") as f:
        rows = list(csv.DictReader(f))

    assert len(rows) == 7
    assert {r["worker_id"] for r in rows} == {"worker_a", "worker_b", "worker_watch"}

    anchor_rows = [r for r in rows if r["dataset_group"] == "Calibration_anchor"]
    assert len(anchor_rows) == 3
    assert all(r["assignment_reason"] == "common_anchor" for r in anchor_rows)
    assert all(r["is_common_anchor"] == "true" for r in anchor_rows)

    core_rows = [r for r in rows if r["dataset_group"] == "Calibration_core"]
    assert len(core_rows) == 4
    assert all(r["assignment_reason"] == "balanced_core" for r in core_rows)
    assert all(r["assignment_batch"] == "core_rr_k2" for r in core_rows)

    task_counts = {}
    for row in core_rows:
        task_counts[row["task_id"]] = task_counts.get(row["task_id"], 0) + 1
    assert task_counts == {"core_01": 2, "core_02": 2}

    worker_orders = {}
    for row in rows:
        worker_orders.setdefault(row["worker_id"], []).append(int(row["expected_completion_order"]))
    assert worker_orders["worker_a"] == sorted(worker_orders["worker_a"])
    assert worker_orders["worker_b"] == sorted(worker_orders["worker_b"])


def test_build_c1_assignment_manifest_supports_core_redundancy_5(tmp_path: Path) -> None:
    admission_csv = tmp_path / "admission.csv"
    workers = [f"worker_{idx:02d}" for idx in range(6)]
    write_csv(
        admission_csv,
        ["worker_id", "admission_status"],
        [{"worker_id": worker, "admission_status": "admitted"} for worker in workers],
    )

    manifest_json = tmp_path / "calibration_manifest.json"
    manifest_json.write_text(
        json.dumps(
            {
                "task_sets": {
                    "Calibration_anchor": [
                        {"task_id": "anchor_01", "base_task_id": "base_a1", "dataset_group": "Calibration_anchor"}
                    ],
                    "Calibration_core": [
                        {"task_id": "core_01", "base_task_id": "base_c1", "dataset_group": "Calibration_core"},
                        {"task_id": "core_02", "base_task_id": "base_c2", "dataset_group": "Calibration_core"},
                    ],
                    "Calibration_reserve": [
                        {"task_id": "reserve_01", "base_task_id": "base_r1", "dataset_group": "Calibration_reserve"}
                    ],
                }
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    output_csv = tmp_path / "assignment_manifest_C1.csv"
    subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--admission-csv",
            str(admission_csv),
            "--calibration-manifest",
            str(manifest_json),
            "--output",
            str(output_csv),
            "--core-redundancy",
            "5",
        ],
        check=True,
    )

    with output_csv.open("r", encoding="utf-8", newline="") as f:
        rows = list(csv.DictReader(f))

    core_rows = [r for r in rows if r["dataset_group"] == "Calibration_core"]
    assert len(core_rows) == 10
    assert {r["assignment_batch"] for r in core_rows} == {"core_rr_k5"}

    workers_by_task = {}
    for row in core_rows:
        workers_by_task.setdefault(row["task_id"], set()).add(row["worker_id"])
    assert {task_id: len(worker_ids) for task_id, worker_ids in workers_by_task.items()} == {
        "core_01": 5,
        "core_02": 5,
    }
    assert all(row["dataset_group"] != "Calibration_reserve" for row in rows)


def test_build_c1_assignment_manifest_rejects_too_few_workers_for_target_k(tmp_path: Path) -> None:
    admission_csv = tmp_path / "admission.csv"
    write_csv(
        admission_csv,
        ["worker_id", "admission_status"],
        [{"worker_id": f"worker_{idx:02d}", "admission_status": "admitted"} for idx in range(4)],
    )
    manifest_json = tmp_path / "calibration_manifest.json"
    manifest_json.write_text(
        json.dumps(
            {
                "task_sets": {
                    "Calibration_anchor": [],
                    "Calibration_core": [
                        {"task_id": "core_01", "base_task_id": "base_c1", "dataset_group": "Calibration_core"}
                    ],
                }
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--admission-csv",
            str(admission_csv),
            "--calibration-manifest",
            str(manifest_json),
            "--output",
            str(tmp_path / "assignment_manifest_C1.csv"),
            "--core-redundancy",
            "5",
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode != 0
    assert "number of admitted workers is smaller than core_redundancy" in result.stderr
