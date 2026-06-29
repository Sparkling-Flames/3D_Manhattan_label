from __future__ import annotations

import csv
import json
from pathlib import Path

from tools.thesis_main.analysis.pipeline_smoke_runner import main, run_pipeline_smoke


FORBIDDEN = (
    "admission",
    "reject",
    "r0",
    "r_u",
    "tau_d",
    "wmax",
    "w_max",
    "routing",
    "handoff",
    "reliability",
    "quality",
    "efficiency",
    "thesis_claim",
    "formal_main",
    "formal_validation",
)


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


def _closeout(tmp_path: Path) -> Path:
    root = tmp_path / "closeout"
    _json(
        root / "p1_closeout_readiness_summary.json",
        {
            "dry_run": True,
            "formal_materialization_allowed": False,
            "data_complete": False,
            "readiness_status": "blocked",
            "blockers": ["data_complete_false", "pending_completion_present"],
            "pending_completion_count": 1,
            "unknown_gold_count": 0,
            "forbidden_artifact_count": 0,
            "geometry_score_fields_present": False,
            "missing_required_artifacts": [],
            "final_gold_source_snapshot_sha256_match": True,
            "export_gt_source_snapshot_sha256_match": True,
            "source_export_snapshot_count": 1,
        },
    )
    _json(root / "p1_pending_completion_summary.json", {"dry_run": True, "pending_completion_count": 1, "pending_worker_ids": ["2"]})
    _csv(
        root / "prescreen_completion_audit.csv",
        [
            {"annotator_id": "1", "language": "zh", "completion_status": "complete", "total_expected": "57", "total_observed": "57", "dropout": "False", "known_bad_or_process_risk": "False"},
            {"annotator_id": "2", "language": "zh", "completion_status": "pending_completion", "total_expected": "57", "total_observed": "9", "dropout": "False", "known_bad_or_process_risk": "False"},
        ],
    )
    _csv(
        root / "prescreen_worker_roster.csv",
        [
            {"annotator_id": "1", "language": "zh", "expected_total": "57", "dropout": "false", "known_bad_or_process_risk": "false", "exclude_from_primary_candidate": "false"},
            {"annotator_id": "2", "language": "zh", "expected_total": "57", "dropout": "false", "known_bad_or_process_risk": "false", "exclude_from_primary_candidate": "false"},
        ],
    )
    _csv(root / "prescreen_canonical_annotations.csv", [{"annotator_id": "1", "task_id": "t1", "dataset_group": "PreScreen_manual", "condition": "manual"}])
    _csv(
        root / "prescreen_scope_adjudication.csv",
        [{"task_id": "t1", "project_id": "p", "dataset_group": "PreScreen_manual", "condition": "manual", "task_final_scope": "in_scope", "task_scope_adjudication_source": "final_gold"}],
    )
    _csv(
        root / "prescreen_scope_response_audit.csv",
        [
            {"annotator_id": "1", "task_id": "t1", "dataset_group": "PreScreen_manual", "condition": "manual", "worker_scope_response": "correct_in_scope", "geometry_valid_or_present": "True", "scope_response_primary_eligible": "True"}
        ],
    )
    _csv(root / "prescreen_worker_scope_summary.csv", [{"annotator_id": "1", "completion_status": "complete"}])
    _csv(
        root / "prescreen_geometry_eligibility_audit.csv",
        [{"task_id": "t1", "project_id": "p", "dataset_group": "PreScreen_manual", "condition": "manual", "task_final_scope": "in_scope", "task_scope_adjudication_source": "final_gold", "geometry_gold_status": "ready", "geometry_evidence_role": "manual_prescreen_candidate", "manual_anchor_role": "True", "manual_anchor_primary_possible": "True"}],
    )
    _csv(root / "prescreen_geometry_gold_alignment_audit.csv", [{"task_id": "t1", "dry_run": "True"}])
    _json(root / "prescreen_gold_alignment_summary.json", {"dry_run": True})
    return root


def test_runner_completes_and_writes_pipeline_state(tmp_path: Path) -> None:
    out = tmp_path / "pipeline_smoke"
    state = run_pipeline_smoke(_closeout(tmp_path), out)

    assert state["final_status"] == "completed"
    assert [stage["status"] for stage in state["stages"]] == ["completed"] * 5
    assert (out / "pipeline_smoke_state.json").exists()


def test_missing_required_upstream_file_fails_and_records_stage(tmp_path: Path) -> None:
    closeout = _closeout(tmp_path)
    (closeout / "prescreen_scope_response_audit.csv").unlink()
    out = tmp_path / "pipeline_smoke"

    code = main(["--closeout-dir", str(closeout), "--output-root", str(out)])

    state = json.loads((out / "pipeline_smoke_state.json").read_text(encoding="utf-8"))
    assert code == 1
    assert state["final_status"] == "failed"
    assert state["failed_stage"] == "p1_provisional"


def test_runner_preserves_closeout_inputs_and_writes_only_root_state_outside_stage_dirs(tmp_path: Path) -> None:
    closeout = _closeout(tmp_path)
    before = {p.name: p.stat().st_mtime_ns for p in closeout.iterdir()}
    out = tmp_path / "pipeline_smoke"

    assert main(["--closeout-dir", str(closeout), "--output-root", str(out)]) == 0

    assert {p.name: p.stat().st_mtime_ns for p in closeout.iterdir()} == before
    root_files = {p.name for p in out.iterdir() if p.is_file()}
    assert root_files == {"pipeline_smoke_state.json"}


def test_pipeline_state_has_no_forbidden_formal_terms(tmp_path: Path) -> None:
    out = tmp_path / "pipeline_smoke"
    run_pipeline_smoke(_closeout(tmp_path), out)
    state_path = out / "pipeline_smoke_state.json"
    payload = json.loads(state_path.read_text(encoding="utf-8"))

    assert not any(token in state_path.name.lower() for token in FORBIDDEN)
    for key in payload:
        if key == "not_for_thesis_claim":
            continue
        assert not any(token in key.lower() for token in FORBIDDEN)
