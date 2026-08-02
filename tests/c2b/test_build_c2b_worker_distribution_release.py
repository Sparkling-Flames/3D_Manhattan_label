from __future__ import annotations

import csv
import json
from pathlib import Path

from tools.thesis_main.registry.build_c2b_worker_distribution_release import build_release


def _write_csv(path: Path, fields: list[str], rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def test_release_uses_d_and_task4_without_changing_assignment(tmp_path: Path) -> None:
    assignment = tmp_path / "assignment.csv"
    _write_csv(
        assignment,
        ["worker_id", "task_id", "assignment_batch_id"],
        [
            {"worker_id": "1", "task_id": "t1", "assignment_batch_id": "C2B_BATCH_A"},
            {"worker_id": "1", "task_id": "t2", "assignment_batch_id": "C2B_BATCH_A"},
            {"worker_id": "27", "task_id": "t2", "assignment_batch_id": "C2B_BATCH_A"},
            {"worker_id": "27", "task_id": "t1", "assignment_batch_id": "C2B_BATCH_A"},
        ],
    )
    planned_import = tmp_path / "import.json"
    planned_import.write_text(
        json.dumps(
            [
                {"data": {"planned_task_id": "t2", "c2b_batch_id": "C2B_BATCH_A", "selected_design_sha": "design-sha"}},
                {"data": {"planned_task_id": "t1", "c2b_batch_id": "C2B_BATCH_A", "selected_design_sha": "design-sha"}},
            ]
        ),
        encoding="utf-8",
    )
    c1_release = tmp_path / "c1_release"
    _write_csv(c1_release / "worker_W027.csv", ["task_code"], [{"task_code": "A-001"}])
    _write_csv(
        c1_release / "worker_facing_distribution_zh_merged_v3_1.csv",
        ["public_worker_code", "worker_name", "task_code"],
        [{"public_worker_code": "W001", "worker_name": "测试工人", "task_code": "任务1-001"}],
    )

    output = tmp_path / "release"
    audit = build_release(assignment, planned_import, c1_release, output)

    assert audit["passed"] is True
    assert audit["entry_mapping"] == {"D": "C2B_BATCH_A", "任务4": "C2B_BATCH_A"}
    assert _read_csv(output / "worker_W027.csv") == [{"task_code": "D-001"}, {"task_code": "D-002"}]
    assert _read_csv(output / "internal" / "worker_facing_distribution_zh_merged_C2B_D8.csv") == [
        {"public_worker_code": "W001", "worker_name": "测试工人", "task_code": "任务4-002"},
        {"public_worker_code": "W001", "worker_name": "测试工人", "task_code": "任务4-001"},
    ]
    internal = _read_csv(output / "internal" / "worker_distribution_internal_C2B_D8.csv")
    assert {(row["public_worker_code"], row["task_id"]) for row in internal} == {
        ("W001", "t1"), ("W001", "t2"), ("W027", "t1"), ("W027", "t2")
    }
    assert all(row["selected_design_sha"] == "design-sha" for row in internal)
