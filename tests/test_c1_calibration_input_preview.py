from __future__ import annotations

import csv
import json
from pathlib import Path

from tools.thesis_main.analysis.c1_calibration_input_preview import build_c1_preview, main


FORBIDDEN = ("admission", "reject", "r0", "r_u", "tau_d", "wmax", "w_max", "routing", "handoff", "reliability")


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


def _p1(tmp_path: Path, *, smoke_allowed: bool = True) -> Path:
    root = tmp_path / "p1"
    _json(root / "p1_provisional_pipeline_state.json", {"smoke_pipeline_allowed": smoke_allowed, "readiness_blockers": ["blocked"]})
    _json(root / "p1_provisional_stage_contract.json", {"this_is_not_formal_p1_materialization": True})
    _csv(
        root / "p1_provisional_worker_table.csv",
        [
            {
                "annotator_id": "1",
                "language": "zh",
                "completion_status": "complete",
                "expected_total": "57",
                "observed_total": "57",
                "pending_completion": "False",
                "dropout": "false",
                "known_bad_or_process_risk": "false",
                "exclude_from_primary_candidate": "false",
                "provisional_worker_status": "review_only",
            },
            {
                "annotator_id": "2",
                "language": "zh",
                "completion_status": "pending_completion",
                "expected_total": "57",
                "observed_total": "9",
                "pending_completion": "True",
                "dropout": "false",
                "known_bad_or_process_risk": "false",
                "exclude_from_primary_candidate": "false",
                "provisional_worker_status": "pending_completion",
            },
            {
                "annotator_id": "3",
                "language": "zh",
                "completion_status": "complete",
                "expected_total": "57",
                "observed_total": "57",
                "pending_completion": "False",
                "dropout": "false",
                "known_bad_or_process_risk": "true",
                "exclude_from_primary_candidate": "true",
                "provisional_worker_status": "process_risk_or_excluded",
            },
        ],
    )
    _csv(
        root / "p1_provisional_task_table.csv",
        [
            {
                "task_id": "t1",
                "project_id": "p",
                "dataset_group": "PreScreen_manual",
                "condition": "manual",
                "task_final_scope": "in_scope",
                "task_scope_adjudication_source": "final_gold",
                "geometry_gold_status": "ready",
                "geometry_evidence_role": "manual_prescreen_candidate",
                "manual_anchor_role": "True",
                "manual_anchor_primary_possible": "True",
            }
        ],
    )
    _csv(
        root / "p1_provisional_response_table.csv",
        [
            {
                "annotator_id": "1",
                "task_id": "t1",
                "dataset_group": "PreScreen_manual",
                "condition": "manual",
                "worker_scope_response": "correct_in_scope",
                "geometry_valid_or_present": "True",
                "scope_response_primary_eligible": "True",
            },
            {
                "annotator_id": "2",
                "task_id": "t1",
                "dataset_group": "PreScreen_manual",
                "condition": "manual",
                "worker_scope_response": "correct_in_scope",
                "geometry_valid_or_present": "True",
                "scope_response_primary_eligible": "True",
            },
        ],
    )
    return root


def test_smoke_allowed_writes_four_preview_files(tmp_path: Path) -> None:
    out = tmp_path / "out"

    state, workers, tasks, responses = build_c1_preview(_p1(tmp_path), out)

    assert state["calibration_preview_only"] is True
    assert state["formal_c1_allowed"] is False
    assert state["p1_smoke_pipeline_allowed"] is True
    assert len(workers) == 3
    assert len(tasks) == 1
    assert len(responses) == 2


def test_smoke_blocked_writes_state_only_with_blocked_reason(tmp_path: Path) -> None:
    out = tmp_path / "out"

    state, workers, tasks, responses = build_c1_preview(_p1(tmp_path, smoke_allowed=False), out)

    assert state["formal_c1_allowed"] is False
    assert state["blocked_reasons"]
    assert workers == []
    assert tasks == []
    assert responses == []


def test_worker_inclusion_excludes_pending_and_process_risk(tmp_path: Path) -> None:
    _state, workers, _tasks, _responses = build_c1_preview(_p1(tmp_path), tmp_path / "out")
    by_id = {row["annotator_id"]: row for row in workers}

    assert by_id["1"]["included_for_smoke_preview"] is True
    assert by_id["2"]["included_for_smoke_preview"] is False
    assert by_id["3"]["included_for_smoke_preview"] is False


def test_cli_writes_only_c1_preview_outputs_and_preserves_p1_inputs(tmp_path: Path) -> None:
    p1 = _p1(tmp_path)
    before = {p.name: p.stat().st_mtime_ns for p in p1.iterdir()}
    out = tmp_path / "analysis_results" / "pipeline_smoke" / "c1_calibration_preview"

    assert main(["--p1-dir", str(p1), "--output-dir", str(out)]) == 0

    assert {p.name for p in out.iterdir()} == {
        "c1_calibration_preview_state.json",
        "c1_worker_input_preview.csv",
        "c1_task_input_preview.csv",
        "c1_response_input_preview.csv",
    }
    assert {p.name: p.stat().st_mtime_ns for p in p1.iterdir()} == before
    for path in out.iterdir():
        text = path.read_text(encoding="utf-8").lower()
        assert not any(token in text for token in ("c1 handoff", "worker reliability profile"))
        if path.suffix == ".csv":
            headers = next(csv.reader(path.open(encoding="utf-8-sig")))
            assert not any(any(token in h.lower() for token in FORBIDDEN) for h in headers)
    state = json.loads((out / "c1_calibration_preview_state.json").read_text(encoding="utf-8"))
    assert state["formal_c1_allowed"] is False
