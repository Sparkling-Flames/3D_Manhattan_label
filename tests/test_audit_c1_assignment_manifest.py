from __future__ import annotations

import csv
import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "tools" / "thesis_main" / "registry" / "audit_c1_assignment_manifest.py"


FIELDNAMES = [
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


def write_manifest(path: Path, rows: list[dict[str, str]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDNAMES)
        writer.writeheader()
        writer.writerows(rows)


def row(worker: str, task: str, group: str, order: int) -> dict[str, str]:
    is_anchor = group == "Calibration_anchor"
    return {
        "round_id": "C1",
        "worker_id": worker,
        "task_id": task,
        "base_task_id": f"base_{task}",
        "dataset_group": group,
        "assignment_batch": "anchor_all" if is_anchor else "core_rr_k5",
        "assignment_reason": "common_anchor" if is_anchor else "balanced_core",
        "is_common_anchor": "true" if is_anchor else "false",
        "expected_completion_order": str(order),
        "manifest_version": "v1",
    }


def test_audit_c1_assignment_manifest_passes_target_k5(tmp_path: Path) -> None:
    workers = [f"worker_{idx:02d}" for idx in range(5)]
    rows = []
    for idx, worker in enumerate(workers, start=1):
        for anchor_idx in range(12):
            rows.append(row(worker, f"anchor_{anchor_idx:02d}", "Calibration_anchor", anchor_idx + 1))
        for core_idx in range(13):
            rows.append(row(worker, f"core_{core_idx:02d}", "Calibration_core", core_idx + 13))

    manifest = tmp_path / "assignment_manifest_C1.csv"
    output = tmp_path / "audit.json"
    write_manifest(manifest, rows)

    subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--assignment-manifest",
            str(manifest),
            "--output",
            str(output),
            "--core-target-k",
            "5",
            "--core-min-accepted-k",
            "4",
            "--min-worker-calibration-tasks",
            "25",
        ],
        check=True,
    )

    summary = json.loads(output.read_text(encoding="utf-8"))
    assert summary["passed"] is True
    assert summary["meta"]["core_target_k"] == 5
    assert summary["meta"]["core_min_accepted_k"] == 4
    assert summary["counts"]["core_tasks"] == 13
    assert summary["counts"]["min_worker_assignments"] == 25


def test_audit_c1_assignment_manifest_rejects_reserve_rows(tmp_path: Path) -> None:
    workers = [f"worker_{idx:02d}" for idx in range(5)]
    rows = [row(worker, "anchor_01", "Calibration_anchor", 1) for worker in workers]
    rows.extend(row(worker, "core_01", "Calibration_core", 2) for worker in workers)
    rows.append(row("worker_01", "reserve_01", "Calibration_reserve", 3))
    manifest = tmp_path / "assignment_manifest_C1.csv"
    write_manifest(manifest, rows)

    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--assignment-manifest",
            str(manifest),
            "--min-worker-calibration-tasks",
            "1",
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 1
    assert "Calibration_reserve" in result.stdout
