from __future__ import annotations

import csv
from pathlib import Path

import pytest

from tools.thesis_main.analysis.c1_authorized_reassignment import assignment_row_sha256, validate_authorized_reassignments


def _write(path: Path, rows: list[dict]) -> None:
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0])); writer.writeheader(); writer.writerows(rows)


def _fixture(tmp_path: Path):
    assignment = tmp_path / "assignment.csv"
    original = {"round_id": "C1", "worker_id": "14", "task_id": "t1", "base_task_id": "b1", "dataset_group": "Calibration_core"}
    _write(assignment, [original])
    import hashlib
    manifest = tmp_path / "reassign.csv"
    row = {
        "round_id": "C1", "condition": "manual", "dataset_group": "Calibration_core", "task_id": "t1", "base_task_id": "b1",
        "displaced_worker_id": "14", "replacement_worker_id": "34",
        "original_assignment_manifest_sha256": hashlib.sha256(assignment.read_bytes()).hexdigest(),
        "original_assignment_row_sha256": assignment_row_sha256(original), "authorization_reason": "administrative replacement",
        "authorized_by": "owner", "authorized_at": "2026-07-28T00:00:00Z", "replacement_project_id": "66",
        "replacement_runtime_task_id": "10", "active_time_expected": "false",
    }
    _write(manifest, [row])
    inventory = tmp_path / "inventory.csv"; _write(inventory, [{"base_task_id": "b1", "image_id": "image-1"}])
    p1 = tmp_path / "p1.csv"; _write(p1, [{"annotator_id": "1", "task_label": "other.jpg"}])
    admission = tmp_path / "admission.csv"; _write(admission, [{"worker_id": "34", "admission_status": "pass_with_watch"}])
    runtime = [{"project_id": "66", "ls_runtime_task_id": "10", "task_id": "t1", "base_task_id": "b1", "dataset_group": "Calibration_core", "condition": "manual"}]
    return manifest, assignment, inventory, p1, admission, runtime, row


def test_authorized_reassignment_validates_sha_runtime_and_exposure(tmp_path: Path) -> None:
    manifest, assignment, inventory, p1, admission, runtime, _row = _fixture(tmp_path)
    rows, summary = validate_authorized_reassignments(manifest, [assignment], runtime, inventory, p1, admission)
    assert summary["status"] == "validated" and summary["row_count"] == 1
    assert rows[("66", "10", "34")]["active_time_expected"] == "false"


def test_authorized_reassignment_rejects_observed_outside_assignment_exposure(tmp_path: Path) -> None:
    manifest, assignment, inventory, p1, admission, runtime, _row = _fixture(tmp_path)
    observed = [{"worker_id": "34", "base_task_id": "b1"}]
    with pytest.raises(ValueError, match="observed C1 exposure"):
        validate_authorized_reassignments(
            manifest, [assignment], runtime, inventory, p1, admission,
            c1_observed_rows=observed,
        )


def test_authorized_reassignment_allows_the_replacement_submission_itself(tmp_path: Path) -> None:
    manifest, assignment, inventory, p1, admission, runtime, _row = _fixture(tmp_path)
    observed = [{
        "worker_id": "34", "project_id": "66", "ls_runtime_task_id": "10",
        "base_task_id": "b1",
    }]
    rows, _summary = validate_authorized_reassignments(
        manifest, [assignment], runtime, inventory, p1, admission,
        c1_observed_rows=observed,
    )
    assert ("66", "10", "34") in rows


@pytest.mark.parametrize("failure", ["stale", "runtime", "c1_exposure", "p1_exposure"])
def test_authorized_reassignment_fails_closed(tmp_path: Path, failure: str) -> None:
    manifest, assignment, inventory, p1, admission, runtime, row = _fixture(tmp_path)
    if failure == "stale": row["original_assignment_manifest_sha256"] = "bad"
    elif failure == "runtime": runtime[0]["base_task_id"] = "other"
    elif failure == "c1_exposure":
        with assignment.open("a", encoding="utf-8") as stream: stream.write("C1,34,t2,b1,Calibration_core\n")
        import hashlib
        row["original_assignment_manifest_sha256"] = hashlib.sha256(assignment.read_bytes()).hexdigest()
    else: _write(p1, [{"annotator_id": "34", "task_label": "image-1.jpg"}])
    _write(manifest, [row])
    with pytest.raises(ValueError): validate_authorized_reassignments(manifest, [assignment], runtime, inventory, p1, admission)
