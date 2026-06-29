from __future__ import annotations

import csv
import json
from pathlib import Path

import pytest

from tools.thesis_main.analysis.c1_calibration_metric_dryrun import build_metric_dryrun, main


FORBIDDEN = ("admission", "reject", "r0", "r_u", "tau_d", "wmax", "w_max", "routing", "handoff", "reliability", "score")


def _json(path: Path, payload: dict) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def _csv(path: Path, rows: list[dict[str, str]]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    return path


def _preview(tmp_path: Path, *, formal: bool = False) -> Path:
    root = tmp_path / "preview"
    _json(
        root / "c1_calibration_preview_state.json",
        {
            "dry_run": True,
            "formal_c1_allowed": formal,
            "n_workers_total": 3,
            "n_workers_included_for_smoke_preview": 1,
            "n_tasks_total": 1,
            "blocked_reasons": [],
        },
    )
    _csv(
        root / "c1_worker_input_preview.csv",
        [
            {"annotator_id": "1", "language": "zh", "included_for_smoke_preview": "True"},
            {"annotator_id": "2", "language": "zh", "included_for_smoke_preview": "False"},
        ],
    )
    _csv(
        root / "c1_task_input_preview.csv",
        [
            {
                "task_id": "t1",
                "dataset_group": "PreScreen_manual",
                "condition": "manual",
                "usable_for_scope_preview": "True",
                "usable_for_geometry_preview": "True",
            }
        ],
    )
    _csv(
        root / "c1_response_input_preview.csv",
        [
            {
                "annotator_id": "1",
                "task_id": "t1",
                "dataset_group": "PreScreen_manual",
                "condition": "manual",
                "worker_scope_response": "correct_in_scope",
                "geometry_valid_or_present": "True",
                "worker_included_for_smoke_preview": "True",
                "task_usable_for_scope_preview": "True",
                "task_usable_for_geometry_preview": "True",
            },
            {
                "annotator_id": "2",
                "task_id": "t1",
                "dataset_group": "PreScreen_manual",
                "condition": "manual",
                "worker_scope_response": "scope_false_positive",
                "geometry_valid_or_present": "True",
                "worker_included_for_smoke_preview": "False",
                "task_usable_for_scope_preview": "True",
                "task_usable_for_geometry_preview": "True",
            },
        ],
    )
    return root


def test_normal_preview_generates_three_dryrun_outputs(tmp_path: Path) -> None:
    state, workers, tasks = build_metric_dryrun(_preview(tmp_path))

    assert state["metric_dryrun_only"] is True
    assert state["formal_c1_allowed"] is False
    assert len(workers) == 2
    assert len(tasks) == 1


def test_formal_c1_allowed_fails_closed(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="formal_c1_allowed"):
        build_metric_dryrun(_preview(tmp_path, formal=True))


def test_pending_or_excluded_worker_not_counted(tmp_path: Path) -> None:
    _state, workers, _tasks = build_metric_dryrun(_preview(tmp_path))
    by_id = {row["annotator_id"]: row for row in workers}

    assert by_id["1"]["n_scope_preview_rows"] == 1
    assert by_id["2"]["n_scope_preview_rows"] == 0
    assert by_id["2"]["n_geometry_preview_rows"] == 0


def test_scope_and_geometry_counts_follow_preview_flags(tmp_path: Path) -> None:
    _state, workers, tasks = build_metric_dryrun(_preview(tmp_path))

    assert workers[0]["n_scope_preview_correct_in_scope"] == 1
    assert workers[0]["n_geometry_present_rows"] == 1
    assert tasks[0]["n_scope_preview_rows"] == 1
    assert tasks[0]["n_geometry_preview_rows"] == 1


def test_cli_outputs_have_no_forbidden_names_or_fields_and_preserve_inputs(tmp_path: Path) -> None:
    preview = _preview(tmp_path)
    before = {p.name: p.stat().st_mtime_ns for p in preview.iterdir()}
    out = tmp_path / "out"

    assert main(["--preview-dir", str(preview), "--output-dir", str(out)]) == 0

    assert {p.name for p in out.iterdir()} == {
        "c1_calibration_metric_dryrun_state.json",
        "c1_worker_metric_dryrun.csv",
        "c1_task_metric_dryrun.csv",
    }
    assert {p.name: p.stat().st_mtime_ns for p in preview.iterdir()} == before
    for path in out.iterdir():
        assert not any(token in path.name.lower() for token in FORBIDDEN)
        if path.suffix == ".csv":
            headers = next(csv.reader(path.open(encoding="utf-8-sig")))
            assert not any(any(token in header.lower() for token in FORBIDDEN) for header in headers)
