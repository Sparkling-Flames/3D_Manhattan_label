from __future__ import annotations

import csv
import json
from pathlib import Path

from tools.thesis_main.analysis.p1_closeout_readiness_audit import build_readiness_summary, main


def _write_json(path: Path, payload: dict) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def _write_csv(path: Path, rows: list[dict[str, str]]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    return path


def _closeout_dir(tmp_path: Path, *, data_complete: bool = True, unknown_gold: int = 0, pending: bool = False) -> Path:
    root = tmp_path / "closeout"
    _write_json(root / "prescreen_canonicalize_summary.json", {"raw_input_manifest": "raw_inputs/raw_input_snapshot_manifest.csv"})
    _write_csv(
        root / "raw_inputs" / "raw_input_snapshot_manifest.csv",
        [{"source_path": "x", "snapshot_path": "y", "completion_basis": "manifest_basis"}],
    )
    _write_json(
        root / "prescreen_scope_summary.json",
        {
            "dry_run": True,
            "data_complete": data_complete,
            "base_image_count": 2,
            "runtime_task_rows": 4,
            "unknown_gold_tasks": unknown_gold,
            "n_unknown_gold_allowlisted": 0,
            "mixed_scope_tasks": 1,
            "source_export_snapshot_count": 2,
            "final_gold_source_snapshot_sha256_match": True,
            "export_gt_source_snapshot_sha256_match": True,
            "geometry_score_fields_present": False,
        },
    )
    _write_csv(
        root / "prescreen_completion_audit.csv",
        [
            {
                "annotator_id": "1",
                "completion_status": "pending_completion" if pending else "complete",
                "dropout": "False",
                "known_bad_or_process_risk": "False",
                "eligible_for_primary_prescreen_candidate": "False",
            }
        ],
    )
    _write_csv(root / "prescreen_worker_roster.csv", [{"annotator_id": "1", "known_bad_or_process_risk": "False", "dropout": "False"}])
    _write_csv(root / "prescreen_scope_response_audit.csv", [{"task_id": "1", "dry_run": "True"}])
    _write_csv(root / "prescreen_worker_scope_summary.csv", [{"annotator_id": "1", "completion_status": "complete"}])
    _write_csv(root / "prescreen_geometry_eligibility_audit.csv", [{"task_id": "1", "dry_run": "True"}])
    return root


def test_data_incomplete_blocks_materialization(tmp_path: Path) -> None:
    summary = build_readiness_summary(_closeout_dir(tmp_path, data_complete=False))

    assert summary["dry_run"] is True
    assert summary["completion_basis"] == "manifest_basis"
    assert summary["formal_materialization_allowed"] is False
    assert summary["readiness_status"] == "blocked"
    assert "data_complete_false" in summary["blockers"]


def test_forbidden_artifact_blocks(tmp_path: Path) -> None:
    root = _closeout_dir(tmp_path)
    (root / "worker_admission.csv").write_text("x\n", encoding="utf-8")

    summary = build_readiness_summary(root)

    assert summary["forbidden_artifact_count"] == 1
    assert "forbidden_artifacts_present" in summary["blockers"]


def test_raw_export_hash_containing_c1_is_not_forbidden_artifact(tmp_path: Path) -> None:
    root = _closeout_dir(tmp_path)
    raw = root / "raw_inputs"
    raw.mkdir(exist_ok=True)
    (raw / "project-30-at-2026-06-28-05-14-c2c3c1f7.json").write_text("[]\n", encoding="utf-8")

    summary = build_readiness_summary(root)

    assert summary["forbidden_artifact_count"] == 0


def test_unknown_gold_unresolved_blocks(tmp_path: Path) -> None:
    summary = build_readiness_summary(_closeout_dir(tmp_path, unknown_gold=1))

    assert summary["unknown_gold_count"] == 1
    assert "unknown_gold_unresolved" in summary["blockers"]


def test_required_artifacts_present_can_reach_review_without_formal_artifacts(tmp_path: Path) -> None:
    summary = build_readiness_summary(_closeout_dir(tmp_path))

    assert summary["readiness_status"] == "ready_for_materialization_review"
    assert summary["formal_materialization_allowed"] is False
    assert summary["missing_required_artifacts"] == []


def test_pending_completion_blocks(tmp_path: Path) -> None:
    summary = build_readiness_summary(_closeout_dir(tmp_path, pending=True))

    assert summary["pending_completion_count"] == 1
    assert "pending_completion_present" in summary["blockers"]


def test_cli_writes_only_readiness_summary(tmp_path: Path) -> None:
    root = _closeout_dir(tmp_path)

    assert main(["--closeout-dir", str(root)]) == 0

    names = {p.name for p in root.iterdir()}
    assert "p1_closeout_readiness_summary.json" in names
    forbidden = ("geometry_score", "admission", "reject", "r0", "r_u", "wmax", "routing", "c1", "handoff", "reliability")
    assert not any(any(token in name.lower() for token in forbidden) for name in names)
    summary = json.loads((root / "p1_closeout_readiness_summary.json").read_text(encoding="utf-8"))
    assert not any(token in json.dumps(summary).lower() for token in ("worker reliability profile", "c1 handoff"))
