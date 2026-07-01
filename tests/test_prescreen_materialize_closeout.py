from __future__ import annotations

import csv
import json
from pathlib import Path

from tools.thesis_main.analysis.prescreen_materialize_closeout import build_closeout_materialization, main


def _csv(path: Path, rows: list[dict]) -> Path:
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)
    return path


def _rollup(path: Path) -> Path:
    return _csv(
        path,
        [
            {
                "annotator_id": "36",
                "completion_status": "complete",
                "n_observed_total": "57",
                "n_expected_total": "57",
                "active_time_source_coverage": "1",
                "n_duplicate_same_geometry": "0",
                "n_revision": "1",
                "n_revision_resolved_by_manual_override": "1",
                "duplicate_revision_resolution": "manual_override_resolved_final_annotation_4595",
                "fallback_watch": "False",
                "n_exact_copy_low_time_events": "0",
                "n_scope_correct_in_scope": "40",
                "n_scope_false_positive": "2",
                "n_scope_false_negative": "0",
                "n_alignment_available": "40",
                "n_undercoverage_high": "1",
                "n_undercoverage_medium": "0",
                "screening_recommendation": "continue_candidate",
                "screening_reason": "manual_override_resolved_final_annotation_4595",
                "evidence_tier": "process_risk",
            },
            {
                "annotator_id": "19",
                "completion_status": "known_bad_complete",
                "n_observed_total": "57",
                "n_expected_total": "57",
                "active_time_source_coverage": "1",
                "n_duplicate_same_geometry": "0",
                "n_revision": "0",
                "n_revision_resolved_by_manual_override": "0",
                "duplicate_revision_resolution": "",
                "fallback_watch": "False",
                "n_exact_copy_low_time_events": "0",
                "n_scope_correct_in_scope": "0",
                "n_scope_false_positive": "0",
                "n_scope_false_negative": "0",
                "n_alignment_available": "0",
                "n_undercoverage_high": "0",
                "n_undercoverage_medium": "0",
                "screening_recommendation": "exclude_process_risk",
                "screening_reason": "completion_or_process_risk",
                "evidence_tier": "process_risk",
            },
        ],
    )


def _issue_review(path: Path) -> Path:
    return _csv(
        path,
        [
            {
                "pair_task_ids": "3167 / 3095",
                "en_task_id": "3167",
                "zh_task_id": "3095",
                "planned_operator": "corner_drift",
                "reviewed_primary_issue": "over_parsing",
                "reviewed_secondary_issue": "corner_duplicate",
                "reviewed_tertiary_issue": "corner_drift",
                "issue_label_source": "manual_review",
                "planned_actual_mismatch": "true",
            }
        ],
    )


def test_materialize_admission_and_r0_from_resolved_rollup(tmp_path: Path) -> None:
    rollup = _rollup(tmp_path / "rollup.csv")
    wmax = tmp_path / "wmax.json"
    wmax.write_text(json.dumps({"worker_w_max": {"36": 29}}), encoding="utf-8")

    admission, r0, summary, report = build_closeout_materialization(
        rollup,
        wmax,
        _issue_review(tmp_path / "issue.csv"),
        superseded_closeout_note="old P1 closeout superseded by gtfix run, but retained as historical snapshot",
    )

    by_worker = {row["worker_id"]: row for row in admission}
    assert by_worker["36"]["admission_status"] == "pass_with_watch"
    assert by_worker["36"]["admission_reason"] == "manual_override_resolved_final_annotation_4595"
    assert by_worker["36"]["eligible_for_C1"] is True
    assert by_worker["19"]["admission_status"] == "fail"
    assert by_worker["19"]["watch_flag"] is False
    assert by_worker["19"]["c1_handoff_note"] == "excluded_from_C1"
    assert r0[0]["r_u_0_basis"] == "p1_proxy_scope_geometry_not_formal_r_u"
    assert summary["semi_synthetic_issue_review"]["planned_actual_mismatch_count"] == 1
    assert "planned_operator" in report
    assert "old P1 closeout superseded by gtfix run" in report
    assert "tau_d" in summary["forbidden_freezes_not_created"]


def test_materialize_cli_writes_formal_closeout_artifacts(tmp_path: Path) -> None:
    rollup = _rollup(tmp_path / "rollup.csv")
    wmax = tmp_path / "wmax.json"
    wmax.write_text(json.dumps({"worker_w_max": {"36": 29}}), encoding="utf-8")
    out = tmp_path / "out"

    assert main([
        "--rollup-csv", str(rollup),
        "--w-max-json", str(wmax),
        "--issue-review-csv", str(_issue_review(tmp_path / "issue.csv")),
        "--output-dir", str(out),
        "--superseded-closeout-note", "old P1 closeout superseded by gtfix run, but retained as historical snapshot",
    ]) == 0

    assert (out / "prescreen_worker_admission.csv").exists()
    assert (out / "prescreen_r0_snapshot.csv").exists()
    assert (out / "prescreen_pass_count_decision.json").exists()
    assert (out / "prescreen_round_report.md").exists()
    assert "old P1 closeout superseded by gtfix run" in (out / "prescreen_round_report.md").read_text(encoding="utf-8")
