from __future__ import annotations

import csv
import json
from pathlib import Path

from tools.thesis_main.analysis.prescreen_undercoverage_risk_audit import build_undercoverage_risk_audit, main


def _csv(path: Path, rows: list[dict]) -> Path:
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)
    return path


def _row(task: str, aid: str, ratio: str, *, available: bool = True) -> dict:
    return {
        "annotator_id": aid,
        "task_id": task,
        "dataset_group": "PreScreen_manual",
        "condition": "manual",
        "reference_validation_status": "final_gold_geometry_checked",
        "worker_n_corners": "4",
        "reference_n_corners": "4",
        "bbox_area_ratio_to_reference": ratio,
        "polygon_area_ratio_to_reference": ratio,
        "alignment_available": str(available),
        "alignment_block_reason": "" if available else "worker_geometry_missing",
    }


def test_high_medium_none_and_not_evaluable(tmp_path: Path) -> None:
    rows, summary = build_undercoverage_risk_audit(
        _csv(tmp_path / "alignment.csv", [_row("h", "w1", "0.4"), _row("m", "w1", "0.7"), _row("n", "w1", "0.9"), _row("x", "w1", "", available=False)])
    )

    assert [row["undercoverage_risk_level"] for row in rows] == ["high", "medium", "none", "not_evaluable"]
    assert summary["thresholds"]["medium_lt"] == 0.75


def test_task_majority_undercoverage_and_minority_full_room_protection(tmp_path: Path) -> None:
    rows, _summary = build_undercoverage_risk_audit(_csv(tmp_path / "alignment.csv", [_row("t", "w1", "0.5"), _row("t", "w2", "0.6"), _row("t", "w3", "0.9")]))

    protected = [row for row in rows if row["annotator_id"] == "w3"][0]
    assert all(row["task_majority_undercoverage_risk"] is True for row in rows)
    assert protected["minority_full_room_candidate"] is True
    assert protected["manual_review_required"] is False


def test_cli_writes_only_undercoverage_sidecars(tmp_path: Path) -> None:
    alignment = _csv(tmp_path / "alignment.csv", [_row("t", "w1", "0.9")])
    out = tmp_path / "out"

    assert main(["--alignment-csv", str(alignment), "--output-dir", str(out)]) == 0

    assert {p.name for p in out.iterdir()} == {"prescreen_undercoverage_risk_audit.csv", "prescreen_undercoverage_risk_summary.json"}
    assert not any(any(token in p.name.lower() for token in ("geometry_score", "admission", "reject", "r0", "r_u", "wmax", "routing", "c1", "handoff", "reliability")) for p in out.iterdir())
    rows = list(csv.DictReader((out / "prescreen_undercoverage_risk_audit.csv").open(encoding="utf-8-sig")))
    assert not any("score" in key.lower() for row in rows for key in row)
    assert json.loads((out / "prescreen_undercoverage_risk_summary.json").read_text(encoding="utf-8"))["dry_run"] is True
