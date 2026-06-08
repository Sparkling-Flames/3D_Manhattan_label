from __future__ import annotations

import csv
import json
from pathlib import Path

from tools.thesis_main.registry.materialize_final_gold_records import run


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")


def test_materialize_final_gold_records_from_truth_layer(tmp_path: Path) -> None:
    repo_root = tmp_path
    truth_dir = repo_root / "analysis_results" / "truth_layer_extraction_20260324"

    _write_json(
        truth_dir / "truth_layer_extraction_summary_v1.json",
        {
            "export_snapshot": "project-20-latest.json",
            "summary_status": "working_consensus_extraction_ready_not_final_gold",
        },
    )
    _write_jsonl(
        truth_dir / "manual_annotation_records_v1.jsonl",
        [
            {
                "task_id": "101",
                "base_task_id": "base-101",
                "bucket_dir": "manual",
                "family_dir": "遮挡明显",
                "priority_flag": "default",
                "recommended_role": "manual_anchor_candidate",
                "review_note_flag": False,
                "default_eligible": True,
                "scope": "normal",
                "scope_binary": "in_scope",
                "canonical_corners_norm": [{"id": 0, "x_pct": 10, "y_top_pct": 20, "y_bottom_pct": 80}],
                "runtime_pairs_1024x512": [{"x": 100, "y_ceiling": 100, "y_floor": 400}],
                "n_corners": 1,
                "pair_coverage": 1.0,
                "poly_residue_flag": False,
                "legacy_txt_present": True,
                "source_export": "project20",
            },
            {
                "task_id": "201",
                "base_task_id": "base-201",
                "bucket_dir": "OOS",
                "family_dir": "边界不可判定",
                "priority_flag": "default",
                "recommended_role": "oos_gate_candidate",
                "review_note_flag": False,
                "default_eligible": True,
                "scope": "oos_open_boundary",
                "scope_binary": "oos",
                "canonical_corners_norm": [{"id": 0, "x_pct": 50, "y_top_pct": 10, "y_bottom_pct": 90}],
                "runtime_pairs_1024x512": [{"x": 500, "y_ceiling": 50, "y_floor": 450}],
                "n_corners": 1,
                "pair_coverage": 1.0,
                "poly_residue_flag": True,
                "legacy_txt_present": True,
                "source_export": "project20",
            },
        ],
    )

    outputs = run(root=repo_root)

    assert outputs["final_gold_jsonl"].exists()
    assert outputs["final_gold_csv"].exists()
    assert outputs["final_gold_summary"].exists()

    jsonl_rows = [
        json.loads(line)
        for line in outputs["final_gold_jsonl"].read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    assert len(jsonl_rows) == 2
    assert jsonl_rows[0]["adjudication_status"] == "final_adjudicated_gold"
    assert jsonl_rows[0]["geometry_gold_ready"] is True
    assert jsonl_rows[1]["geometry_gold_ready"] is False
    assert jsonl_rows[1]["scope_gold_ready"] is True

    with outputs["final_gold_csv"].open("r", encoding="utf-8-sig", newline="") as handle:
        csv_rows = list(csv.DictReader(handle))
    assert len(csv_rows) == 2
    assert csv_rows[0]["final_scope_binary"] == "in_scope"
    assert csv_rows[1]["final_scope_binary"] == "oos"

    summary = json.loads(outputs["final_gold_summary"].read_text(encoding="utf-8"))
    assert summary["n_records_total"] == 2
    assert summary["n_geometry_gold_ready"] == 1
    assert summary["difficulty_model_issue_promoted_to_final_gold"] is False
    assert summary["summary_status"] == "final_gold_materialized_from_verified_project20_export"
