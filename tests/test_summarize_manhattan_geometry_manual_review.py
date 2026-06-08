import csv
import json

import pytest

from tools.paper_a_manhattan.summarize_manhattan_geometry_manual_review import (
    load_manual_review_csv,
    main,
    summarize_manual_review,
)


FIELDS = [
    "task_id",
    "annotation_id",
    "plausible_candidate",
    "likely_issue",
    "reviewer_note",
    "problem_reason",
    "max_abs_delta",
]


def _write_csv(path, rows):
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(rows)
    return path


def _row(task_id, annotation_id, plausible, issue, note="reviewed", reason="", delta=""):
    return {
        "task_id": str(task_id),
        "annotation_id": str(annotation_id),
        "plausible_candidate": plausible,
        "likely_issue": issue,
        "reviewer_note": note,
        "problem_reason": reason,
        "max_abs_delta": delta,
    }


def test_completed_csv_produces_summary(tmp_path):
    path = _write_csv(
        tmp_path / "manual.csv",
        [
            _row(2948, 1, "yes", "unclear"),
            _row(2949, 2, "unsure", "algorithm_overfit", reason="large_candidate_delta", delta="8"),
        ],
    )

    rows = load_manual_review_csv(path)
    summary = summarize_manual_review(rows, source_csv=str(path))

    assert summary["n_review_rows"] == 2
    assert summary["n_review_completed"] == 2
    assert summary["plausible_candidate_counts"]["yes"] == 1
    assert summary["likely_issue_counts"]["algorithm_overfit"] == 1
    assert summary["m16_decision_recommendation"] == "m16_blocked"


def test_invalid_plausible_candidate_fails_clearly(tmp_path):
    path = _write_csv(tmp_path / "manual.csv", [_row(2948, 1, "maybe", "unclear")])

    with pytest.raises(ValueError, match="invalid plausible_candidate"):
        load_manual_review_csv(path)


def test_invalid_likely_issue_fails_clearly(tmp_path):
    path = _write_csv(tmp_path / "manual.csv", [_row(2948, 1, "yes", "bad_issue")])

    with pytest.raises(ValueError, match="invalid likely_issue"):
        load_manual_review_csv(path)


def test_missing_rows_are_counted(tmp_path):
    path = _write_csv(
        tmp_path / "manual.csv",
        [
            _row(2948, 1, "", "", note=""),
            _row(2948, 2, "yes", "unclear"),
        ],
    )

    summary = summarize_manual_review(load_manual_review_csv(path))

    assert summary["n_review_rows"] == 2
    assert summary["n_review_completed"] == 1
    assert summary["n_review_missing"] == 1
    assert summary["missing_manual_field_counts"]["plausible_candidate"] == 1
    assert summary["missing_manual_field_counts"]["likely_issue"] == 1
    assert summary["missing_manual_field_counts"]["reviewer_note"] == 1


def test_algorithm_overfit_unsure_blocks_m16(tmp_path):
    path = _write_csv(
        tmp_path / "manual.csv",
        [
            _row(2949, 1, "unsure", "algorithm_overfit", reason="large_candidate_delta", delta="9"),
            _row(2949, 2, "yes", "annotation_geometry"),
        ],
    )

    summary = summarize_manual_review(load_manual_review_csv(path))

    assert summary["unsure_and_algorithm_overfit_count"] == 1
    assert summary["m16_decision_recommendation"] == "m16_blocked"


def test_no_algorithm_overfit_and_mostly_yes_can_produce_limited_expert_discussion(tmp_path):
    path = _write_csv(
        tmp_path / "manual.csv",
        [
            _row(2948, 1, "yes", "unclear"),
            _row(2948, 2, "yes", "annotation_geometry"),
            _row(2948, 3, "no", "annotation_geometry"),
        ],
    )

    summary = summarize_manual_review(load_manual_review_csv(path))

    assert summary["likely_issue_counts"]["algorithm_overfit"] == 0
    assert summary["m16_decision_recommendation"] == "m16_limited_expert_only_discussion"


def test_task_level_summary_includes_2948_and_2949(tmp_path):
    path = _write_csv(
        tmp_path / "manual.csv",
        [
            _row(2948, 1, "yes", "unclear"),
            _row(2949, 2, "unsure", "algorithm_overfit", reason="large_candidate_delta", delta="9"),
        ],
    )

    summary = summarize_manual_review(load_manual_review_csv(path))

    assert "2948" in summary["task_level_summary"]
    assert "2949" in summary["task_level_summary"]
    assert "Task 2948 is mostly stable" in summary["task_2948_summary"]["interpretation"]
    assert "Task 2949 shows mixed behavior" in summary["task_2949_summary"]["interpretation"]


def test_cli_writes_summary_and_report(tmp_path):
    path = _write_csv(
        tmp_path / "manual.csv",
        [_row(2949, 1, "unsure", "algorithm_overfit", reason="large_candidate_delta", delta="9")],
    )
    out = tmp_path / "out"

    assert main(["--input", str(path), "--output-dir", str(out), "--date", "2026-05-18"]) == 0

    summary_path = out / "smoke_geometry_manual_review_summary_2026-05-18.json"
    report_path = out / "smoke_geometry_manual_review_report_2026-05-18.md"
    assert summary_path.exists()
    assert report_path.exists()
    assert json.loads(summary_path.read_text(encoding="utf-8"))["m16_decision_recommendation"] == "m16_blocked"
    report = report_path.read_text(encoding="utf-8")
    assert "Candidate is useful for expert-side review." in report
    assert "Candidate is not stable enough for UI ghost candidate." in report


def test_no_test_modifies_export_label(tmp_path):
    path = _write_csv(tmp_path / "manual.csv", [_row(2948, 1, "yes", "unclear")])
    before = path.read_text(encoding="utf-8")

    summarize_manual_review(load_manual_review_csv(path))

    assert path.read_text(encoding="utf-8") == before
