from __future__ import annotations

import csv
import json
from pathlib import Path

import pytest

from tools.thesis_main.analysis.v1_validation_aggregation_dryrun import build_v1_validation_dryrun, main


FORBIDDEN = ("score", "reliability", "routing", "admission", "reject", "r_u", "tau_d", "wmax", "quality", "claim", "generalization", "efficiency", "handoff")


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


def _inputs(tmp_path: Path, *, formal_main: bool = False, main_dryrun: bool | None = True, formal_c1: bool = False) -> tuple[Path, Path]:
    t1 = tmp_path / "t1"
    c1 = tmp_path / "c1"
    t1_state = {
        "dry_run": True,
        "formal_main_allowed": formal_main,
        "n_workers_total": 2,
        "n_tasks_total": 2,
        "n_conditions": 2,
        "blocked_reasons": [],
    }
    if main_dryrun is not None:
        t1_state["main_dryrun_only"] = main_dryrun
    _json(t1 / "t1_main_dryrun_state.json", t1_state)
    _csv(
        t1 / "t1_worker_coverage_dryrun.csv",
        [
            {"annotator_id": "1", "included_for_smoke_preview": "True", "n_scope_preview_rows": "2", "n_geometry_preview_rows": "1", "n_geometry_present_rows": "1"},
            {"annotator_id": "2", "included_for_smoke_preview": "False", "n_scope_preview_rows": "0", "n_geometry_preview_rows": "0", "n_geometry_present_rows": "0"},
        ],
    )
    _csv(
        t1 / "t1_task_coverage_dryrun.csv",
        [
            {"task_id": "t1", "dataset_group": "PreScreen_manual", "condition": "manual", "task_usable_for_scope_preview": "True", "task_usable_for_geometry_preview": "True", "n_scope_preview_rows": "2", "n_geometry_preview_rows": "1"},
            {"task_id": "t2", "dataset_group": "PreScreen_semi", "condition": "semi", "task_usable_for_scope_preview": "True", "task_usable_for_geometry_preview": "False", "n_scope_preview_rows": "1", "n_geometry_preview_rows": "0"},
        ],
    )
    _csv(
        t1 / "t1_condition_coverage_dryrun.csv",
        [
            {"dataset_group": "PreScreen_manual", "condition": "manual", "n_tasks": "1", "n_scope_preview_rows": "2", "n_geometry_preview_rows": "1"},
            {"dataset_group": "PreScreen_semi", "condition": "semi", "n_tasks": "1", "n_scope_preview_rows": "1", "n_geometry_preview_rows": "0"},
        ],
    )
    _json(c1 / "c1_calibration_metric_dryrun_state.json", {"dry_run": True, "metric_dryrun_only": True, "formal_c1_allowed": formal_c1})
    _csv(c1 / "c1_worker_metric_dryrun.csv", [{"annotator_id": "1"}])
    _csv(c1 / "c1_task_metric_dryrun.csv", [{"task_id": "t1"}])
    return t1, c1


def test_normal_t1_c1_dryrun_generates_four_outputs(tmp_path: Path) -> None:
    t1, c1 = _inputs(tmp_path)
    state, workers, tasks, conditions = build_v1_validation_dryrun(t1, c1)

    assert state["validation_dryrun_only"] is True
    assert state["formal_validation_allowed"] is False
    assert len(workers) == 2
    assert len(tasks) == 2
    assert len(conditions) == 2


def test_formal_main_allowed_fails_closed(tmp_path: Path) -> None:
    t1, c1 = _inputs(tmp_path, formal_main=True)

    with pytest.raises(ValueError, match="formal_main_allowed"):
        build_v1_validation_dryrun(t1, c1)


def test_missing_or_false_main_dryrun_only_fails_closed(tmp_path: Path) -> None:
    t1, c1 = _inputs(tmp_path, main_dryrun=None)
    with pytest.raises(ValueError, match="main_dryrun_only"):
        build_v1_validation_dryrun(t1, c1)

    t1, c1 = _inputs(tmp_path / "false", main_dryrun=False)
    with pytest.raises(ValueError, match="main_dryrun_only"):
        build_v1_validation_dryrun(t1, c1)


def test_formal_c1_allowed_fails_closed(tmp_path: Path) -> None:
    t1, c1 = _inputs(tmp_path, formal_c1=True)

    with pytest.raises(ValueError, match="formal_c1_allowed"):
        build_v1_validation_dryrun(t1, c1)


def test_cli_outputs_have_no_forbidden_names_or_fields_and_preserve_inputs(tmp_path: Path) -> None:
    t1, c1 = _inputs(tmp_path)
    before_t1 = {p.name: p.stat().st_mtime_ns for p in t1.iterdir()}
    before_c1 = {p.name: p.stat().st_mtime_ns for p in c1.iterdir()}
    out = tmp_path / "out"

    assert main(["--t1-dir", str(t1), "--c1-dir", str(c1), "--output-dir", str(out)]) == 0

    assert {p.name for p in out.iterdir()} == {
        "v1_validation_dryrun_state.json",
        "v1_worker_validation_coverage_dryrun.csv",
        "v1_task_validation_coverage_dryrun.csv",
        "v1_condition_validation_coverage_dryrun.csv",
    }
    assert {p.name: p.stat().st_mtime_ns for p in t1.iterdir()} == before_t1
    assert {p.name: p.stat().st_mtime_ns for p in c1.iterdir()} == before_c1
    for path in out.iterdir():
        assert not any(token in path.name.lower() for token in FORBIDDEN)
        if path.suffix == ".csv":
            headers = next(csv.reader(path.open(encoding="utf-8-sig")))
            assert not any(any(token in header.lower() for token in FORBIDDEN) for header in headers)
        if path.suffix == ".json":
            keys = json.loads(path.read_text(encoding="utf-8")).keys()
            assert not any(any(token in key.lower() for token in FORBIDDEN) for key in keys if key != "not_for_thesis_claim")
