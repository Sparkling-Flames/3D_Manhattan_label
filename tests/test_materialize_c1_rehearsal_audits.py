from __future__ import annotations

import csv
import json
from pathlib import Path

from tools.thesis_main.analysis.materialize_c1_rehearsal_audits import (
    apply_structural_dispositions,
    materialize_c2_eligible_roster,
    materialize_completion_support,
    materialize_structural_validation,
)


def _csv(path: Path, rows: list[dict]) -> None:
    fields = list(rows[0])
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader(); writer.writerows(rows)


def test_completion_counts_raw_pending_duplicate_as_observed(tmp_path: Path) -> None:
    assignment = tmp_path / "manual.csv"
    mapping = tmp_path / "mapping.csv"
    canonical = tmp_path / "canonical.csv"
    geometry = tmp_path / "geometry.jsonl"
    export = tmp_path / "export.json"
    _csv(assignment, [
        {"worker_id": "1", "task_id": "t1", "base_task_id": "b1", "dataset_group": "g"},
        {"worker_id": "2", "task_id": "t1", "base_task_id": "b1", "dataset_group": "g"},
    ])
    _csv(mapping, [{"project_id": "66", "ls_runtime_task_id": "10", "task_id": "t1", "base_task_id": "b1", "dataset_group": "g", "condition": "manual"}])
    _csv(canonical, [{"worker_id": "2", "task_id": "t1", "base_task_id": "b1", "dataset_group": "g"}])
    geometry.write_text("", encoding="utf-8")
    export.write_text(json.dumps([{"project": 66, "id": 10, "annotations": [{"id": 1, "completed_by": 1}, {"id": 2, "completed_by": 2}]}]), encoding="utf-8")

    summary = materialize_completion_support([export], [assignment], mapping, canonical, geometry, tmp_path)

    assert summary["observed_submission_count"] == 2
    assert summary["missing_submission_count"] == 0
    rows = list(csv.DictReader((tmp_path / "c1_assignment_realization_audit.csv").open(encoding="utf-8")))
    assert next(row for row in rows if row["worker_id"] == "1")["missing_reason"] == "duplicate_revision_pending"


def test_structural_pass_is_geometry_eligible_but_not_worker_reliability_without_independence(tmp_path: Path) -> None:
    canonical = tmp_path / "canonical.csv"
    geometry = tmp_path / "geometry.jsonl"
    _csv(canonical, [{"canonical_annotation_id": "c1", "project_id": "66", "ls_runtime_task_id": "1", "annotation_id": "a1", "worker_id": "1", "independence_status": "not_evaluable"}])
    geometry.write_text(json.dumps({"canonical_annotation_id": "c1", "worker_id": "1", "task_id": "t1", "corners_px": [[10, 10], [10, 400], [700, 10], [700, 400]], "width": 1024, "height": 512}) + "\n", encoding="utf-8")

    summary = materialize_structural_validation(canonical, geometry, tmp_path)
    apply_structural_dispositions(canonical, tmp_path / "structural_validation_audit.csv")

    assert summary["structural_status_counts"] == {"passed": 1}
    row = next(csv.DictReader(canonical.open(encoding="utf-8")))
    assert row["failure_attribution"] == "none"
    assert row["worker_reliability_eligible"] == "false"


def test_c2_roster_fails_closed_on_unknown_independence(tmp_path: Path) -> None:
    completion = tmp_path / "completion.csv"; canonical = tmp_path / "canonical.csv"
    quality = tmp_path / "quality.csv"; loo = tmp_path / "loo.csv"
    _csv(completion, [{"worker_id": "1", "observed_total_count": "2", "completion_status": "completed"}])
    _csv(canonical, [{"worker_id": "1", "independence_status": "not_evaluable", "structural_validation_status": "passed", "outside_assignment_submission": "false", "duplicate_worker_task_submission": "false"}])
    _csv(quality, [{"worker_id": "1", "quality_evaluable": "true"}])
    _csv(loo, [{"worker_id": "1", "peer_count_excluding_self": "2"}])

    summary = materialize_c2_eligible_roster(completion, canonical, quality, loo, tmp_path)

    assert summary["n_eligible"] == 0
    row = next(csv.DictReader((tmp_path / "c2_eligible_roster_C1.csv").open(encoding="utf-8")))
    assert row["c2_candidate_eligible"] == "False"
    assert "independence_not_frozen" in row["candidate_exclusion_reason"]
