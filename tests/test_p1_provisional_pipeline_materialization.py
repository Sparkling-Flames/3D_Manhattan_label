from __future__ import annotations

import csv
import json
from pathlib import Path

from tools.thesis_main.analysis.p1_provisional_pipeline_materialization import build_provisional_pipeline, main


FORBIDDEN = ("admission", "reject", "r0", "r_u", "wmax", "w_max", "routing", "c1", "handoff", "reliability")


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


def _closeout(tmp_path: Path, readiness_updates: dict | None = None) -> Path:
    root = tmp_path / "closeout"
    readiness = {
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
    }
    readiness.update(readiness_updates or {})
    _json(root / "p1_closeout_readiness_summary.json", readiness)
    _json(root / "p1_pending_completion_summary.json", {"dry_run": True, "pending_worker_ids": ["1"], "pending_completion_count": 1})
    _csv(
        root / "prescreen_completion_audit.csv",
        [
            {
                "annotator_id": "1",
                "language": "zh",
                "completion_status": "pending_completion",
                "total_expected": "57",
                "total_observed": "9",
                "dropout": "False",
                "known_bad_or_process_risk": "False",
            }
        ],
    )
    _csv(
        root / "prescreen_worker_roster.csv",
        [
            {
                "annotator_id": "1",
                "language": "zh",
                "expected_total": "57",
                "will_continue": "true",
                "dropout": "false",
                "known_bad_or_process_risk": "false",
                "exclude_from_primary_candidate": "false",
            }
        ],
    )
    _csv(root / "prescreen_canonical_annotations.csv", [{"annotator_id": "1", "task_id": "t1", "dataset_group": "PreScreen_manual", "condition": "manual"}])
    _csv(
        root / "prescreen_scope_adjudication.csv",
        [
            {
                "task_id": "t1",
                "project_id": "p",
                "dataset_group": "PreScreen_manual",
                "condition": "manual",
                "task_final_scope": "in_scope",
                "task_scope_adjudication_source": "final_gold",
            }
        ],
    )
    _csv(
        root / "prescreen_scope_response_audit.csv",
        [
            {
                "annotator_id": "1",
                "task_id": "t1",
                "dataset_group": "PreScreen_manual",
                "condition": "manual",
                "worker_scope_response": "correct_in_scope",
                "geometry_valid_or_present": "True",
                "scope_response_primary_eligible": "True",
            }
        ],
    )
    _csv(root / "prescreen_worker_scope_summary.csv", [{"annotator_id": "1", "completion_status": "pending_completion"}])
    _csv(
        root / "prescreen_geometry_eligibility_audit.csv",
        [
            {
                "task_id": "t1",
                "geometry_gold_status": "ready",
                "geometry_evidence_role": "manual_prescreen_candidate",
                "manual_anchor_role": "True",
                "manual_anchor_primary_possible": "True",
            }
        ],
    )
    _csv(root / "prescreen_geometry_gold_alignment_audit.csv", [{"task_id": "t1", "dry_run": "True"}])
    _json(root / "prescreen_gold_alignment_summary.json", {"dry_run": True})
    return root


def test_smoke_allowed_when_only_data_and_pending_blockers(tmp_path: Path) -> None:
    state, *_ = build_provisional_pipeline(_closeout(tmp_path))

    assert state["smoke_pipeline_allowed"] is True
    assert state["formal_materialization_allowed"] is False
    assert state["not_for_thesis_claim"] is True


def test_forbidden_artifacts_block_smoke(tmp_path: Path) -> None:
    state, *_ = build_provisional_pipeline(_closeout(tmp_path, {"forbidden_artifact_count": 1}))

    assert state["smoke_pipeline_allowed"] is False


def test_unknown_gold_blocks_smoke(tmp_path: Path) -> None:
    state, *_ = build_provisional_pipeline(_closeout(tmp_path, {"unknown_gold_count": 1}))

    assert state["smoke_pipeline_allowed"] is False


def test_missing_required_artifacts_block_smoke(tmp_path: Path) -> None:
    state, *_ = build_provisional_pipeline(_closeout(tmp_path, {"missing_required_artifacts": ["x.csv"]}))

    assert state["smoke_pipeline_allowed"] is False


def test_cli_writes_only_provisional_outputs_and_no_forbidden_fields(tmp_path: Path) -> None:
    closeout = _closeout(tmp_path)
    out = tmp_path / "analysis_results" / "pipeline_smoke" / "p1_provisional"
    before = {p.name for p in closeout.iterdir()}

    assert main(["--closeout-dir", str(closeout), "--output-dir", str(out)]) == 0

    assert {p.name for p in out.iterdir()} == {
        "p1_provisional_pipeline_state.json",
        "p1_provisional_worker_table.csv",
        "p1_provisional_task_table.csv",
        "p1_provisional_response_table.csv",
        "p1_provisional_stage_contract.json",
    }
    assert {p.name for p in closeout.iterdir()} == before
    for path in out.iterdir():
        assert not any(token in path.name.lower() for token in FORBIDDEN)
        text = path.read_text(encoding="utf-8").lower()
        assert not any(token in text for token in ("worker reliability profile", "c1 handoff"))
    state = json.loads((out / "p1_provisional_pipeline_state.json").read_text(encoding="utf-8"))
    contract = json.loads((out / "p1_provisional_stage_contract.json").read_text(encoding="utf-8"))
    assert state["formal_materialization_allowed"] is False
    assert contract["this_is_not_formal_p1_materialization"] is True
