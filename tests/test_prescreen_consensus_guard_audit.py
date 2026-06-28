from __future__ import annotations

import csv
from pathlib import Path

from tools.thesis_main.analysis.prescreen_consensus_guard_audit import build_consensus_guard_audit, main


def _csv(path: Path, rows: list[dict]) -> Path:
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)
    return path


def _under(task: str, aid: str, level: str = "none", *, majority: bool = False, minority: bool = False) -> dict:
    return {
        "annotator_id": aid,
        "task_id": task,
        "dataset_group": "PreScreen_manual",
        "condition": "manual",
        "undercoverage_risk_level": level,
        "task_majority_undercoverage_risk": str(majority),
        "minority_full_room_candidate": str(minority),
    }


def _alignment(path: Path) -> Path:
    return _csv(path, [{"task_id": "t", "annotator_id": "w1"}])


def _dup(task: str = "none", aid: str = "w1", dtype: str = "") -> dict:
    return {"task_id": task, "annotator_id": aid, "duplicate_group_size": "2" if dtype else "1", "duplicate_geometry_type": dtype}


def test_consensus_safe_and_optional_exact_copy_missing(tmp_path: Path) -> None:
    rows, summary = build_consensus_guard_audit(_csv(tmp_path / "u.csv", [_under("t", "w1"), _under("t", "w2")]), _alignment(tmp_path / "a.csv"), _csv(tmp_path / "d.csv", [_dup()]))

    assert rows[0]["consensus_guard_bucket"] == "consensus_safe"
    assert summary["optional_exact_copy_summary_missing"] is True
    assert summary["copy_risk_evaluation_status"] == "not_evaluated_missing_optional_input"


def test_majority_undercoverage_and_minority_protection(tmp_path: Path) -> None:
    rows, _summary = build_consensus_guard_audit(
        _csv(tmp_path / "u.csv", [_under("t", "w1", "high", majority=True), _under("t", "w2", "medium", majority=True), _under("t", "w3", "none", majority=True, minority=True)]),
        _alignment(tmp_path / "a.csv"),
        _csv(tmp_path / "d.csv", [_dup()]),
    )

    assert rows[0]["consensus_guard_bucket"] == "minority_full_room_protection"
    assert rows[0]["has_minority_full_room_candidate"] is True


def test_copy_risk_dominated_consensus(tmp_path: Path) -> None:
    rows, _summary = build_consensus_guard_audit(
        _csv(tmp_path / "u.csv", [_under("t", "w1"), _under("t", "w2")]),
        _alignment(tmp_path / "a.csv"),
        _csv(tmp_path / "d.csv", [_dup("t", "w1", "duplicate_same_geometry")]),
    )

    assert rows[0]["copy_cluster_dominated_consensus"] is True
    assert rows[0]["consensus_guard_bucket"] == "copy_risk_guard"


def test_worker_exact_copy_summary_drives_low_time_guard(tmp_path: Path) -> None:
    under = _csv(tmp_path / "u.csv", [_under("t", "w1"), _under("t", "w2")])
    align = _csv(tmp_path / "a.csv", [{"task_id": "t", "annotator_id": "w1"}, {"task_id": "t", "annotator_id": "w2"}])
    exact = _csv(tmp_path / "exact.csv", [{"worker_id": "w1", "recommended_action": "fail_recommended"}, {"worker_id": "w2", "recommended_action": "fail_recommended"}])

    rows, summary = build_consensus_guard_audit(under, align, _csv(tmp_path / "d.csv", [_dup()]), exact)

    assert rows[0]["low_time_dominated_consensus"] is True
    assert rows[0]["consensus_guard_bucket"] == "low_time_guard"
    assert summary["copy_risk_evaluation_status"] == "evaluated"


def test_insufficient_evidence(tmp_path: Path) -> None:
    rows, _summary = build_consensus_guard_audit(_csv(tmp_path / "u.csv", [_under("t", "w1", "not_evaluable")]), _alignment(tmp_path / "a.csv"), _csv(tmp_path / "d.csv", [_dup()]))

    assert rows[0]["consensus_guard_bucket"] == "insufficient_evidence"


def test_cli_writes_only_consensus_guard_sidecars(tmp_path: Path) -> None:
    under = _csv(tmp_path / "u.csv", [_under("t", "w1"), _under("t", "w2")])
    align = _alignment(tmp_path / "a.csv")
    dup = _csv(tmp_path / "d.csv", [_dup()])
    out = tmp_path / "out"

    assert main(["--undercoverage-csv", str(under), "--alignment-csv", str(align), "--duplicate-csv", str(dup), "--exact-copy-csv", "", "--output-dir", str(out)]) == 0

    assert {p.name for p in out.iterdir()} == {"prescreen_consensus_guard_audit.csv", "prescreen_consensus_guard_summary.json"}
    assert not any(any(token in p.name.lower() for token in ("geometry_score", "admission", "reject", "r0", "r_u", "wmax", "routing", "c1", "handoff", "reliability")) for p in out.iterdir())
    rows = list(csv.DictReader((out / "prescreen_consensus_guard_audit.csv").open(encoding="utf-8-sig")))
    assert not any("score" in key.lower() for row in rows for key in row)
