from __future__ import annotations

import csv
import json
from pathlib import Path

from tools.thesis_main.analysis.prescreen_worker_screening_rollup import build_worker_screening_rollup, main


def _csv(path: Path, rows: list[dict]) -> Path:
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)
    return path


def _completion(aid: str, status: str = "complete", eligible: str = "True", known_bad: str = "False", notes: str = "") -> dict:
    return {
        "annotator_id": aid,
        "completion_status": status,
        "eligible_for_primary_prescreen_candidate": eligible,
        "known_bad_or_process_risk": known_bad,
        "total_expected": "10",
        "total_observed": "10" if status == "complete" else "5",
        "total_missing": "0" if status == "complete" else "5",
        "notes": notes,
    }


def _base_inputs(tmp_path: Path, workers: list[dict]):
    return {
        "completion": _csv(tmp_path / "completion.csv", workers),
        "active": _csv(tmp_path / "active.csv", [{"annotator_id": row["annotator_id"], "n_log": "10", "n_rows": "10"} for row in workers]),
        "duplicate": _csv(tmp_path / "duplicate.csv", [{"annotator_id": "unused", "duplicate_geometry_type": "", "task_id": "x"}]),
        "scope": _csv(tmp_path / "scope.csv", [{"annotator_id": row["annotator_id"], "worker_scope_response": "correct_in_scope"} for row in workers]),
        "eligibility": _csv(tmp_path / "elig.csv", [{"annotator_id": row["annotator_id"], "manual_anchor_role": "True"} for row in workers]),
        "alignment": _csv(tmp_path / "align.csv", [{"annotator_id": row["annotator_id"], "alignment_available": "True", "task_id": "t"} for row in workers]),
        "under": _csv(tmp_path / "under.csv", [{"annotator_id": row["annotator_id"], "undercoverage_risk_level": "none", "minority_full_room_candidate": "False"} for row in workers]),
        "guard": _csv(tmp_path / "guard.csv", [{"task_id": "t", "consensus_guard_bucket": "consensus_safe"}]),
    }


def _run(tmp_path: Path, workers: list[dict], **overrides):
    paths = _base_inputs(tmp_path, workers)
    paths.update(overrides)
    return build_worker_screening_rollup(
        paths["completion"],
        paths["active"],
        paths["duplicate"],
        paths["scope"],
        paths["eligibility"],
        paths["alignment"],
        paths["under"],
        paths["guard"],
        paths.get("exact"),
        paths.get("manual_overrides"),
    )


def test_complete_clean_worker_continue_candidate(tmp_path: Path) -> None:
    rows, _summary = _run(tmp_path, [_completion("w1")])

    assert rows[0]["screening_recommendation"] == "continue_candidate"
    assert rows[0]["evidence_tier"] == "review_only"


def test_pending_worker_hold_pending_completion(tmp_path: Path) -> None:
    rows, summary = _run(tmp_path, [_completion("w1", "pending_completion", "False")])

    assert rows[0]["screening_recommendation"] == "hold_pending_completion"
    assert summary["final_stage1_closeout_ready"] is False
    assert summary["completion_input_status"] == "pending_workers_present"
    assert summary["pending_completion_worker_ids"] == ["w1"]


def test_known_bad_or_incomplete_excluded_process_risk(tmp_path: Path) -> None:
    rows, _summary = _run(tmp_path, [_completion("w1", "incomplete_excluded", "False")])

    assert rows[0]["screening_recommendation"] == "exclude_process_risk"
    assert rows[0]["evidence_tier"] == "process_risk"


def test_manual_process_exclusion_is_provisional_override_not_algorithmic_copy_detection(tmp_path: Path) -> None:
    rows, summary = _run(
        tmp_path,
        [
            _completion(
                "21",
                "known_bad_complete",
                "False",
                "True",
                "confirmed process-risk / suspected copied annotation / manually excluded before Stage 2",
            )
        ],
    )

    assert rows[0]["screening_recommendation"] == "exclude_process_risk"
    assert summary["screening_status"] == "ready_for_manual_materialization_review"
    assert summary["manual_process_exclusion_count"] == 1
    assert summary["manual_process_exclusion_ids"] == ["21"]
    assert summary["manual_process_exclusion_basis"] == "manual_process_risk_override_not_algorithmic_copy_detection"
    assert summary["copy_risk_evaluation_status"] == "not_evaluated_missing_optional_input"


def test_exact_copy_fail_recommended_excludes_process_risk(tmp_path: Path) -> None:
    exact = _csv(tmp_path / "exact.csv", [{"worker_id": "w1", "recommended_action": "fail_recommended", "n_exact_copy_low_time_events": "3"}])
    rows, summary = _run(tmp_path, [_completion("w1")], exact=exact)

    assert rows[0]["screening_recommendation"] == "exclude_process_risk"
    assert rows[0]["n_exact_copy_low_time_events"] == 3
    assert summary["copy_risk_evaluation_status"] == "evaluated"


def test_exact_copy_no_action_zero_events_does_not_create_watch_event(tmp_path: Path) -> None:
    exact = _csv(tmp_path / "exact.csv", [{"worker_id": "w1", "recommended_action": "no_action", "n_exact_copy_low_time_events": "0"}])
    rows, _summary = _run(tmp_path, [_completion("w1")], exact=exact)

    assert rows[0]["n_exact_copy_low_time_events"] == 0


def test_revision_duplicate_forces_process_manual_review(tmp_path: Path) -> None:
    duplicate = _csv(tmp_path / "duplicate_revision.csv", [{"annotator_id": "w1", "duplicate_geometry_type": "revision", "task_id": "t1"}])
    rows, _summary = _run(tmp_path, [_completion("w1")], duplicate=duplicate)

    assert rows[0]["screening_recommendation"] == "manual_review"
    assert rows[0]["screening_reason"] == "duplicate_revision_manual_review"
    assert rows[0]["evidence_tier"] == "process_risk"


def test_revision_duplicate_manual_override_resolves_review_but_keeps_audit_trace(tmp_path: Path) -> None:
    duplicate = _csv(tmp_path / "duplicate_revision.csv", [{"annotator_id": "36", "duplicate_geometry_type": "revision", "task_id": "3129"}])
    override = tmp_path / "manual_overrides.json"
    override.write_text(
        json.dumps(
            {
                "duplicate_annotation_overrides": [
                    {
                        "worker_id": "36",
                        "task_id": "3129",
                        "duplicate_geometry_type": "revision",
                        "final_annotation_id": "4595",
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    rows, summary = _run(tmp_path, [_completion("36")], duplicate=duplicate, manual_overrides=override)

    assert rows[0]["n_revision"] == 1
    assert rows[0]["n_revision_resolved_by_manual_override"] == 1
    assert rows[0]["screening_recommendation"] == "continue_candidate"
    assert rows[0]["screening_reason"] == "manual_override_resolved_final_annotation_4595"
    assert rows[0]["evidence_tier"] == "process_risk"
    assert summary["ready_for_manual_materialization_review"] is True
    assert summary["manual_override_resolved_revision_count"] == 1


def test_fallback_only_worker_sets_final_fallback_watch_status(tmp_path: Path) -> None:
    active = _csv(
        tmp_path / "active_fallback.csv",
        [
            {"annotator_id": "34", "n_log": "0", "n_rows": "10", "n_lead_time_fallback": "10"},
            {"annotator_id": "26", "n_log": "0", "n_rows": "10", "n_lead_time_fallback": "10"},
        ],
    )
    rows, summary = _run(tmp_path, [_completion("34"), _completion("26", "incomplete_excluded", "False")], active=active)
    by_worker = {row["annotator_id"]: row for row in rows}

    assert by_worker["34"]["fallback_watch"] is True
    assert by_worker["26"]["fallback_watch"] is False
    assert summary["active_time_input_status"] == "final_with_fallback_watch"
    assert summary["fallback_watch_worker_ids"] == ["34"]


def test_single_high_undercoverage_is_warning_candidate_not_manual_review(tmp_path: Path) -> None:
    under = _csv(tmp_path / "under_high.csv", [{"annotator_id": "w1", "undercoverage_risk_level": "high", "minority_full_room_candidate": "False"}])
    rows, _summary = _run(tmp_path, [_completion("w1")], under=under)

    assert rows[0]["screening_recommendation"] == "continue_candidate"
    assert rows[0]["screening_reason"] == "task_or_worker_undercoverage_watch"
    assert rows[0]["evidence_tier"] == "geometry_risk"


def test_repeated_high_undercoverage_worker_is_nonblocking_watch(tmp_path: Path) -> None:
    under = _csv(
        tmp_path / "under_high2.csv",
        [
            {"annotator_id": "w1", "undercoverage_risk_level": "high", "minority_full_room_candidate": "False"},
            {"annotator_id": "w1", "undercoverage_risk_level": "high", "minority_full_room_candidate": "False"},
        ],
    )
    align = _csv(tmp_path / "align2.csv", [{"annotator_id": "w1", "alignment_available": "True", "task_id": "t1"}, {"annotator_id": "w1", "alignment_available": "True", "task_id": "t2"}])
    rows, _summary = _run(tmp_path, [_completion("w1")], under=under, alignment=align)

    assert rows[0]["screening_recommendation"] == "continue_candidate"
    assert rows[0]["screening_reason"] == "task_or_worker_undercoverage_watch"
    assert rows[0]["evidence_tier"] == "geometry_risk"


def test_task_majority_undercoverage_is_excluded_from_worker_counts(tmp_path: Path) -> None:
    under = _csv(
        tmp_path / "under_task_majority.csv",
        [
            {
                "annotator_id": "w1",
                "undercoverage_risk_level": "high",
                "minority_full_room_candidate": "False",
                "task_majority_undercoverage_risk": "True",
            },
            {
                "annotator_id": "w1",
                "undercoverage_risk_level": "high",
                "minority_full_room_candidate": "False",
                "task_majority_undercoverage_risk": "True",
            },
        ],
    )
    rows, _summary = _run(tmp_path, [_completion("w1")], under=under)

    assert rows[0]["n_undercoverage_high"] == 0
    assert rows[0]["screening_recommendation"] == "continue_candidate"
    assert rows[0]["screening_reason"] == "no_major_dry_run_risk"


def test_minority_full_room_candidate_is_not_punished(tmp_path: Path) -> None:
    under = _csv(tmp_path / "under_minority.csv", [{"annotator_id": "w1", "undercoverage_risk_level": "none", "minority_full_room_candidate": "True"}])
    rows, _summary = _run(tmp_path, [_completion("w1")], under=under)

    assert rows[0]["screening_recommendation"] == "continue_candidate"
    assert rows[0]["screening_reason"] == "protected_full_room_candidate"
    assert rows[0]["evidence_tier"] == "protected_full_room"


def test_insufficient_evidence(tmp_path: Path) -> None:
    paths = _base_inputs(tmp_path, [_completion("w1")])
    paths["eligibility"] = _csv(tmp_path / "elig_empty.csv", [{"annotator_id": "w1", "manual_anchor_role": "False"}])
    paths["alignment"] = _csv(tmp_path / "align_empty.csv", [{"annotator_id": "w1", "alignment_available": "False", "task_id": "t"}])

    rows, _summary = build_worker_screening_rollup(
        paths["completion"], paths["active"], paths["duplicate"], paths["scope"], paths["eligibility"], paths["alignment"], paths["under"], paths["guard"]
    )

    assert rows[0]["screening_recommendation"] == "insufficient_evidence"


def test_cli_writes_only_worker_screening_sidecars(tmp_path: Path) -> None:
    paths = _base_inputs(tmp_path, [_completion("w1")])
    out = tmp_path / "out"

    assert main([
        "--completion-csv", str(paths["completion"]),
        "--active-time-csv", str(paths["active"]),
        "--duplicate-csv", str(paths["duplicate"]),
        "--scope-response-csv", str(paths["scope"]),
        "--geometry-eligibility-csv", str(paths["eligibility"]),
        "--alignment-csv", str(paths["alignment"]),
        "--undercoverage-csv", str(paths["under"]),
        "--consensus-guard-csv", str(paths["guard"]),
        "--exact-copy-csv", "",
        "--output-dir", str(out),
    ]) == 0

    assert {p.name for p in out.iterdir()} == {"prescreen_worker_screening_rollup.csv", "prescreen_worker_screening_summary.json"}
    assert not any(any(token in p.name.lower() for token in ("geometry_score", "admission", "reject", "r0", "r_u", "wmax", "routing", "c1", "handoff", "reliability")) for p in out.iterdir())
    rows = list(csv.DictReader((out / "prescreen_worker_screening_rollup.csv").open(encoding="utf-8-sig")))
    assert not any("score" in key.lower() for row in rows for key in row)
    summary = json.loads((out / "prescreen_worker_screening_summary.json").read_text(encoding="utf-8"))
    assert summary["screening_status"] == "ready_for_manual_materialization_review"
    assert summary["forbidden_materialization_status"] == "not_generated"
