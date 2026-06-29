from __future__ import annotations

import csv
import json
from pathlib import Path

import pytest

from tools.thesis_main.analysis.t1_main_aggregation_dryrun import build_t1_main_dryrun, main


FORBIDDEN = ("score", "reliability", "routing", "admission", "reject", "r_u", "tau_d", "wmax", "efficiency", "quality_claim", "handoff")


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


def _c1(tmp_path: Path, *, formal: bool = False, metric: bool = True) -> tuple[Path, Path]:
    metric_dir = tmp_path / "c1_metric"
    preview_dir = tmp_path / "c1_preview"
    _json(
        metric_dir / "c1_calibration_metric_dryrun_state.json",
        {
            "dry_run": True,
            "metric_dryrun_only": metric,
            "formal_c1_allowed": formal,
            "n_workers_total": 2,
            "n_workers_included_for_smoke_preview": 1,
            "n_tasks_total": 2,
            "n_scope_preview_responses": 3,
            "n_geometry_preview_responses": 2,
            "blocked_reasons": [],
        },
    )
    _csv(
        metric_dir / "c1_worker_metric_dryrun.csv",
        [
            {"annotator_id": "1", "included_for_smoke_preview": "True", "n_scope_preview_rows": "2", "n_geometry_preview_rows": "1", "n_geometry_present_rows": "1"},
            {"annotator_id": "2", "included_for_smoke_preview": "False", "n_scope_preview_rows": "0", "n_geometry_preview_rows": "0", "n_geometry_present_rows": "0"},
        ],
    )
    _csv(
        metric_dir / "c1_task_metric_dryrun.csv",
        [
            {
                "task_id": "t1",
                "dataset_group": "PreScreen_manual",
                "condition": "manual",
                "task_usable_for_scope_preview": "True",
                "task_usable_for_geometry_preview": "True",
                "n_scope_preview_rows": "2",
                "n_geometry_preview_rows": "1",
            },
            {
                "task_id": "t2",
                "dataset_group": "PreScreen_semi",
                "condition": "semi",
                "task_usable_for_scope_preview": "True",
                "task_usable_for_geometry_preview": "False",
                "n_scope_preview_rows": "1",
                "n_geometry_preview_rows": "0",
            },
        ],
    )
    _csv(preview_dir / "c1_response_input_preview.csv", [{"annotator_id": "1", "task_id": "t1"}])
    return metric_dir, preview_dir


def test_normal_c1_metric_input_generates_four_outputs(tmp_path: Path) -> None:
    metric_dir, preview_dir = _c1(tmp_path)
    state, workers, tasks, conditions = build_t1_main_dryrun(metric_dir, preview_dir)

    assert state["main_dryrun_only"] is True
    assert state["formal_main_allowed"] is False
    assert len(workers) == 2
    assert len(tasks) == 2
    assert len(conditions) == 2


def test_formal_c1_allowed_fails_closed(tmp_path: Path) -> None:
    metric_dir, preview_dir = _c1(tmp_path, formal=True)

    with pytest.raises(ValueError, match="formal_c1_allowed"):
        build_t1_main_dryrun(metric_dir, preview_dir)


def test_condition_coverage_is_counts_only(tmp_path: Path) -> None:
    metric_dir, preview_dir = _c1(tmp_path)
    _state, _workers, _tasks, conditions = build_t1_main_dryrun(metric_dir, preview_dir)
    manual = [row for row in conditions if row["condition"] == "manual"][0]

    assert manual["n_tasks"] == 1
    assert manual["n_scope_preview_rows"] == 2
    assert manual["n_geometry_preview_rows"] == 1
    assert not any("ratio" in key or "claim" in key for row in conditions for key in row)


def test_cli_outputs_have_no_forbidden_names_or_fields_and_preserve_inputs(tmp_path: Path) -> None:
    metric_dir, preview_dir = _c1(tmp_path)
    before_metric = {p.name: p.stat().st_mtime_ns for p in metric_dir.iterdir()}
    before_preview = {p.name: p.stat().st_mtime_ns for p in preview_dir.iterdir()}
    out = tmp_path / "out"

    assert main(["--metric-dir", str(metric_dir), "--preview-dir", str(preview_dir), "--output-dir", str(out)]) == 0

    assert {p.name for p in out.iterdir()} == {
        "t1_main_dryrun_state.json",
        "t1_worker_coverage_dryrun.csv",
        "t1_task_coverage_dryrun.csv",
        "t1_condition_coverage_dryrun.csv",
    }
    assert {p.name: p.stat().st_mtime_ns for p in metric_dir.iterdir()} == before_metric
    assert {p.name: p.stat().st_mtime_ns for p in preview_dir.iterdir()} == before_preview
    for path in out.iterdir():
        assert not any(token in path.name.lower() for token in FORBIDDEN)
        if path.suffix == ".csv":
            headers = next(csv.reader(path.open(encoding="utf-8-sig")))
            assert not any(any(token in header.lower() for token in FORBIDDEN) for header in headers)
