from __future__ import annotations

import csv
import json
from pathlib import Path

from tools.thesis_main.analysis.p1_pending_completion_audit import build_pending_completion_audit, main


def _csv(path: Path, rows: list[dict[str, str]]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    return path


def _json(path: Path, payload: dict) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def _root(tmp_path: Path, completion: dict[str, str], roster: dict[str, str]) -> Path:
    root = tmp_path / "closeout"
    _csv(root / "prescreen_completion_audit.csv", [completion])
    _csv(root / "prescreen_worker_roster.csv", [roster])
    _csv(
        root / "prescreen_canonical_annotations.csv",
        [
            {"annotator_id": completion["annotator_id"], "dataset_group": "PreScreen_manual"},
            {"annotator_id": completion["annotator_id"], "dataset_group": "PreScreen_semi"},
        ],
    )
    _json(root / "prescreen_canonicalize_summary.json", {"n_canonical_rows": 2})
    _json(root / "p1_closeout_readiness_summary.json", {"dry_run": True, "readiness_status": "blocked"})
    return root


def _completion(aid: str = "1") -> dict[str, str]:
    return {
        "annotator_id": aid,
        "language": "zh",
        "completion_status": "pending_completion",
        "manual_expected": "30",
        "semi_expected": "18",
        "oos_expected": "9",
        "total_expected": "57",
        "manual_observed": "1",
        "semi_observed": "1",
        "oos_observed": "0",
        "total_missing": "55",
        "will_continue": "True",
        "dropout": "False",
        "known_bad_or_process_risk": "False",
    }


def _roster(**updates: str) -> dict[str, str]:
    row = {
        "annotator_id": "1",
        "language": "zh",
        "expected_manual": "30",
        "expected_semi": "18",
        "expected_oos": "9",
        "expected_total": "57",
        "will_continue": "true",
        "dropout": "false",
        "known_bad_or_process_risk": "false",
        "exclude_from_primary_candidate": "false",
        "notes": "",
    }
    row.update(updates)
    return row


def test_pending_will_continue_waits_for_completion(tmp_path: Path) -> None:
    rows, summary = build_pending_completion_audit(_root(tmp_path, _completion(), _roster()))

    assert rows[0]["suggested_closeout_action"] == "wait_for_completion"
    assert summary["n_wait_for_completion"] == 1


def test_pending_dropout_suggests_dropout_if_confirmed(tmp_path: Path) -> None:
    rows, _summary = build_pending_completion_audit(_root(tmp_path, _completion(), _roster(will_continue="false", dropout="true")))

    assert rows[0]["suggested_closeout_action"] == "mark_dropout_no_future_if_confirmed"


def test_pending_process_risk_suggests_incomplete_excluded(tmp_path: Path) -> None:
    rows, _summary = build_pending_completion_audit(
        _root(tmp_path, _completion(), _roster(known_bad_or_process_risk="true", exclude_from_primary_candidate="true"))
    )

    assert rows[0]["suggested_closeout_action"] == "mark_incomplete_excluded_if_confirmed"


def test_conflicting_fields_require_manual_decision(tmp_path: Path) -> None:
    rows, _summary = build_pending_completion_audit(_root(tmp_path, _completion(), _roster(will_continue="true", dropout="true")))

    assert rows[0]["suggested_closeout_action"] == "manual_decision_required"


def test_cli_writes_only_pending_audit_outputs(tmp_path: Path) -> None:
    root = _root(tmp_path, _completion(), _roster())

    assert main(["--closeout-dir", str(root)]) == 0

    names = {p.name for p in root.iterdir()}
    assert {"p1_pending_completion_audit.csv", "p1_pending_completion_summary.json"}.issubset(names)
    forbidden = ("geometry_score", "admission", "reject", "r0", "r_u", "wmax", "routing", "c1", "handoff", "reliability")
    assert not any(any(token in name.lower() for token in forbidden) for name in names)
    summary = json.loads((root / "p1_pending_completion_summary.json").read_text(encoding="utf-8"))
    assert summary["dry_run"] is True
    assert summary["readiness_blocker_cleared"] is False
