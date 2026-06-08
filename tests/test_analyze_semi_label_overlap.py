from __future__ import annotations

from pathlib import Path

from tools.thesis_main.analysis.analyze_semi_label_overlap import build_rows, build_summary


def test_analyze_semi_label_overlap_flags_only_task580_in_latest_verified() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    rows = build_rows(repo_root)
    summary = build_summary(rows)

    assert summary["semi_task_count"] == 21
    assert summary["latest_verified_multi_issue_task_ids"] == ["580"]
    assert "475" in summary["project2_multi_issue_task_ids"]
    assert "665" in summary["project2_multi_issue_task_ids"]
    assert "668" in summary["project2_multi_issue_task_ids"]

    task580 = next(row for row in rows if row["task_id"] == "580")
    assert task580["latest_verified_has_mixed_issue"] is True
    assert task580["project2_has_mixed_issue"] is True

    task475 = next(row for row in rows if row["task_id"] == "475")
    assert task475["latest_verified_model_issue_tags"] == "fail"
    assert task475["latest_verified_has_mixed_issue"] is False

    task665 = next(row for row in rows if row["task_id"] == "665")
    assert task665["latest_verified_model_issue_tags"] == "underextend"
    assert task665["latest_verified_has_mixed_issue"] is False

    task668 = next(row for row in rows if row["task_id"] == "668")
    assert task668["latest_verified_model_issue_tags"] == "overextend_adjacent"
    assert task668["latest_verified_has_mixed_issue"] is False
