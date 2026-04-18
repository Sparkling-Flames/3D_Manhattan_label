from __future__ import annotations

import csv
import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "tools" / "build_c1_assignment_manifest.py"


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

    assert len(rows) == 6
    assert {r["worker_id"] for r in rows} == {"worker_a", "worker_b"}

    anchor_rows = [r for r in rows if r["dataset_group"] == "Calibration_anchor"]
    assert len(anchor_rows) == 2
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
