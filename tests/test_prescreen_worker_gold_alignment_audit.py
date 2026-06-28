from __future__ import annotations

import csv
import json
from pathlib import Path

from tools.thesis_main.analysis.prescreen_worker_gold_alignment_audit import build_worker_gold_alignment_audit, main


def _csv(path: Path, rows: list[dict]) -> Path:
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)
    return path


def _canonical(task: str, *, aid: str = "w1", geom: list | None = None, parse_error: str = "") -> dict:
    return {
        "project_id": "1",
        "task_id": task,
        "dataset_group": "PreScreen_manual",
        "condition": "manual",
        "annotator_id": aid,
        "canonical_geometry": json.dumps(geom if geom is not None else [[0, 0], [10, 0], [10, 10], [0, 10]]),
        "n_corners": "4",
        "parse_error": parse_error,
    }


def _gold_status(task: str, *, validation: str = "final_gold_geometry_checked", gold_ref: str = "task_id:g1", group: str = "PreScreen_manual") -> dict:
    return {
        "task_id": task,
        "project_id": "1",
        "dataset_group": group,
        "condition": "manual" if group == "PreScreen_manual" else "semi",
        "geometry_gold_task_id": gold_ref,
        "gold_status_for_alignment": "ready_for_alignment",
        "gold_status_for_undercoverage": "ready_for_undercoverage_audit",
        "validation_status": validation,
    }


def _final_gold(path: Path, task_id: str = "g1") -> Path:
    rec = {"task_id": task_id, "runtime_pairs_1024x512": [{"x": 0, "y_ceiling": 0, "y_floor": 10}, {"x": 10, "y_ceiling": 0, "y_floor": 10}]}
    path.write_text(json.dumps(rec) + "\n", encoding="utf-8")
    return path


def _inputs(tmp_path: Path, canonical: list[dict], gold: list[dict], synthetic: list[dict] | None = None):
    return (
        _csv(tmp_path / "canonical.csv", canonical),
        _csv(tmp_path / "gold.csv", gold),
        _final_gold(tmp_path / "final_gold.jsonl"),
        _csv(tmp_path / "synthetic.csv", synthetic or [{"runtime_task_id": "unused", "reference_geometry": ""}]),
    )


def test_worker_geometry_valid_with_checked_final_gold_reference(tmp_path: Path) -> None:
    rows, _summary = build_worker_gold_alignment_audit(*_inputs(tmp_path, [_canonical("t1")], [_gold_status("t1")]))

    assert rows[0]["alignment_available"] is True
    assert rows[0]["gold_alignment_bucket"] == "reference_ready_geometry_present"
    assert rows[0]["reference_validation_status"] == "final_gold_geometry_checked"
    assert rows[0]["manual_review_required"] is False


def test_small_worker_bbox_flags_possible_undercoverage(tmp_path: Path) -> None:
    rows, _summary = build_worker_gold_alignment_audit(
        *_inputs(tmp_path, [_canonical("t1", geom=[[0, 0], [4, 0], [4, 4], [0, 4]])], [_gold_status("t1")])
    )

    assert rows[0]["undercoverage_candidate_flag"] is True
    assert rows[0]["gold_alignment_bucket"] == "possible_undercoverage"


def test_large_worker_bbox_flags_possible_overcoverage(tmp_path: Path) -> None:
    rows, _summary = build_worker_gold_alignment_audit(
        *_inputs(tmp_path, [_canonical("t1", geom=[[0, 0], [20, 0], [20, 20], [0, 20]])], [_gold_status("t1")])
    )

    assert rows[0]["overcoverage_candidate_flag"] is True
    assert rows[0]["gold_alignment_bucket"] == "possible_overcoverage"


def test_worker_missing_or_parse_error_blocks_alignment(tmp_path: Path) -> None:
    rows, _summary = build_worker_gold_alignment_audit(
        *_inputs(tmp_path, [_canonical("t1", geom=[], parse_error="bad")], [_gold_status("t1")])
    )

    assert rows[0]["alignment_available"] is False
    assert rows[0]["manual_review_required"] is True
    assert rows[0]["gold_alignment_bucket"] == "worker_geometry_parse_error"


def test_reference_not_ready_is_not_output(tmp_path: Path) -> None:
    bad = _gold_status("t1")
    bad["gold_status_for_alignment"] = "not_applicable"

    rows, _summary = build_worker_gold_alignment_audit(*_inputs(tmp_path, [_canonical("t1")], [bad]))

    assert rows == []


def test_synthetic_external_source_gt_can_be_reference(tmp_path: Path) -> None:
    rows, _summary = build_worker_gold_alignment_audit(
        *_inputs(
            tmp_path,
            [_canonical("s1")],
            [_gold_status("s1", validation="external_source_gt_checked", gold_ref="2752", group="PreScreen_semi")],
            [{"runtime_task_id": "s1", "reference_geometry": json.dumps([[0, 0], [10, 0], [10, 10], [0, 10]])}],
        )
    )

    assert rows[0]["reference_type"] == "synthetic_source_gt"
    assert rows[0]["alignment_available"] is True


def test_synthetic_external_source_gt_uses_frozen_scope_summary_snapshot(tmp_path: Path) -> None:
    gt = tmp_path / "groudTruth.json"
    gt.write_text(
        json.dumps(
            [
                {
                    "id": 2752,
                    "annotations": [
                        {
                            "result": [
                                {"value": {"x": 0, "y": 0}},
                                {"value": {"x": 0.9765625, "y": 0}},
                                {"value": {"x": 0.9765625, "y": 1.953125}},
                                {"value": {"x": 0, "y": 1.953125}},
                            ]
                        }
                    ],
                }
            ]
        ),
        encoding="utf-8",
    )
    summary = tmp_path / "scope_summary.json"
    summary.write_text(json.dumps({"export_gt_snapshot_path": str(gt)}), encoding="utf-8")
    rows, _summary = build_worker_gold_alignment_audit(
        *_inputs(
            tmp_path,
            [_canonical("s1")],
            [_gold_status("s1", validation="external_source_gt_checked", gold_ref="2752", group="PreScreen_semi")],
            [{"runtime_task_id": "s1", "reference_geometry": ""}],
        ),
        summary,
    )

    assert rows[0]["reference_type"] == "synthetic_source_gt"
    assert rows[0]["alignment_available"] is True


def test_cli_writes_only_worker_gold_alignment_sidecars(tmp_path: Path) -> None:
    paths = _inputs(tmp_path, [_canonical("t1")], [_gold_status("t1")])
    out = tmp_path / "out"

    assert main(["--canonical-csv", str(paths[0]), "--gold-status-csv", str(paths[1]), "--final-gold-jsonl", str(paths[2]), "--synthetic-geometry-csv", str(paths[3]), "--scope-summary-json", "", "--output-dir", str(out)]) == 0

    assert {p.name for p in out.iterdir()} == {"prescreen_worker_gold_alignment_audit.csv", "prescreen_worker_gold_alignment_summary.json"}
    assert not any(any(token in p.name.lower() for token in ("geometry_score", "admission", "reject", "r0", "r_u", "wmax", "routing", "c1", "handoff", "reliability")) for p in out.iterdir())
    rows = list(csv.DictReader((out / "prescreen_worker_gold_alignment_audit.csv").open(encoding="utf-8-sig")))
    assert not any("score" in key.lower() for row in rows for key in row)
