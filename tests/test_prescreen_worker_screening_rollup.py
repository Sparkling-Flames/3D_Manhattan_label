from __future__ import annotations

import csv
from pathlib import Path

from tools.thesis_main.analysis.prescreen_worker_screening_rollup import build_worker_screening_rollup, main


def _csv(path: Path, rows: list[dict]) -> Path:
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)
    return path


def _completion(aid: str, status: str = "complete", eligible: str = "True") -> dict:
    return {
        "annotator_id": aid,
        "completion_status": status,
        "eligible_for_primary_prescreen_candidate": eligible,
        "total_expected": "10",
        "total_observed": "10" if status == "complete" else "5",
        "total_missing": "0" if status == "complete" else "5",
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
    )


def test_complete_clean_worker_continue_candidate(tmp_path: Path) -> None:
    rows, _summary = _run(tmp_path, [_completion("w1")])

    assert rows[0]["screening_recommendation"] == "continue_candidate"


def test_pending_worker_hold_pending_completion(tmp_path: Path) -> None:
    rows, _summary = _run(tmp_path, [_completion("w1", "pending_completion", "False")])

    assert rows[0]["screening_recommendation"] == "hold_pending_completion"


def test_known_bad_or_incomplete_excluded_process_risk(tmp_path: Path) -> None:
    rows, _summary = _run(tmp_path, [_completion("w1", "incomplete_excluded", "False")])

    assert rows[0]["screening_recommendation"] == "exclude_process_risk"


def test_exact_copy_fail_recommended_excludes_process_risk(tmp_path: Path) -> None:
    exact = _csv(tmp_path / "exact.csv", [{"annotator_id": "w1", "copy_audit_recommended_action": "fail_recommended"}])
    rows, _summary = _run(tmp_path, [_completion("w1")], exact=exact)

    assert rows[0]["screening_recommendation"] == "exclude_process_risk"


def test_high_undercoverage_worker_manual_review(tmp_path: Path) -> None:
    under = _csv(tmp_path / "under_high.csv", [{"annotator_id": "w1", "undercoverage_risk_level": "high", "minority_full_room_candidate": "False"}])
    rows, _summary = _run(tmp_path, [_completion("w1")], under=under)

    assert rows[0]["screening_recommendation"] == "manual_review"


def test_minority_full_room_candidate_is_not_punished(tmp_path: Path) -> None:
    under = _csv(tmp_path / "under_minority.csv", [{"annotator_id": "w1", "undercoverage_risk_level": "none", "minority_full_room_candidate": "True"}])
    rows, _summary = _run(tmp_path, [_completion("w1")], under=under)

    assert rows[0]["screening_recommendation"] == "continue_candidate"
    assert rows[0]["screening_reason"] == "protected_full_room_candidate"


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
        "--output-dir", str(out),
    ]) == 0

    assert {p.name for p in out.iterdir()} == {"prescreen_worker_screening_rollup.csv", "prescreen_worker_screening_summary.json"}
    assert not any(any(token in p.name.lower() for token in ("geometry_score", "admission", "reject", "r0", "r_u", "wmax", "routing", "c1", "handoff", "reliability")) for p in out.iterdir())
    rows = list(csv.DictReader((out / "prescreen_worker_screening_rollup.csv").open(encoding="utf-8-sig")))
    assert not any("score" in key.lower() for row in rows for key in row)
