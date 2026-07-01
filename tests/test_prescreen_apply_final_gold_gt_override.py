from __future__ import annotations

import json
from pathlib import Path

from tools.thesis_main.analysis.prescreen_apply_final_gold_gt_override import apply_final_gold_v2_corrections, apply_gt_override


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row) + "\n")


def _kp(x: float, y: float) -> dict:
    return {
        "type": "keypointlabels",
        "original_width": 1024,
        "original_height": 512,
        "value": {"x": x, "y": y},
    }


def test_apply_gt_override_replaces_564_with_explicit_pair_counts(tmp_path: Path) -> None:
    old_gold = tmp_path / "final_gold.jsonl"
    gt = tmp_path / "groudTruth.json"
    out = tmp_path / "out"

    _write_jsonl(
        old_gold,
        [
            {
                "task_id": "564",
                "base_task_id": "img106",
                "canonical_corners_norm": [{"id": i, "x_pct": i, "y_top_pct": 1, "y_bottom_pct": 99} for i in range(8)],
                "runtime_pairs_1024x512": [{"x": i, "y_ceiling": 1, "y_floor": 99} for i in range(8)],
                "n_corners": 8,
                "pair_coverage": 1.0,
                "final_gold_notes": ["existing"],
            }
        ],
    )
    gt.write_text(
        json.dumps(
            [
                {
                    "id": 2590,
                    "inner_id": 106,
                    "data": {"title": "img106.jpg"},
                    "annotations": [
                        {
                            "id": 4843,
                            "result": [
                                _kp(10, 20),
                                _kp(10, 80),
                                _kp(30, 15),
                                _kp(30, 85),
                                _kp(50, 25),
                                _kp(50, 75),
                                _kp(70, 30),
                                _kp(70, 70),
                            ],
                        }
                    ],
                }
            ]
        ),
        encoding="utf-8",
    )

    outputs = apply_gt_override(
        final_gold_jsonl=old_gold,
        export_gt_json=gt,
        output_dir=out,
        final_gold_task_id="564",
        gt_task_id="2590",
        gt_inner_id="106",
        expected_pair_count=4,
        expected_keypoint_count=8,
        final_gold_n_corners=4,
    )

    corrected = [json.loads(line) for line in outputs["corrected_final_gold_jsonl"].read_text(encoding="utf-8").splitlines()]
    audit = json.loads(outputs["audit_json"].read_text(encoding="utf-8"))

    assert corrected[0]["n_corners"] == 4
    assert len(corrected[0]["canonical_corners_norm"]) == 4
    assert len(corrected[0]["runtime_pairs_1024x512"]) == 4
    assert "gt106_geometry_override_20260701" in corrected[0]["final_gold_notes"]
    assert audit["expected_pair_count"] == 4
    assert audit["expected_keypoint_count"] == 8
    assert audit["final_gold_n_corners"] == 4
    assert audit["old_564_pair_count"] == 8
    assert audit["new_564_pair_count"] == 4
    assert audit["old_564_keypoint_count"] == 16
    assert audit["new_564_keypoint_count"] == 8


def test_apply_final_gold_v2_corrections_writes_consolidated_audit(tmp_path: Path) -> None:
    old_gold = tmp_path / "final_gold.jsonl"
    gt = tmp_path / "groudTruth.json"
    out = tmp_path / "out"

    _write_jsonl(
        old_gold,
        [
            {
                "task_id": "564",
                "base_task_id": "img106",
                "canonical_corners_norm": [{"id": i, "x_pct": i, "y_top_pct": 1, "y_bottom_pct": 99} for i in range(8)],
                "runtime_pairs_1024x512": [{"x": i, "y_ceiling": 1, "y_floor": 99} for i in range(8)],
                "n_corners": 8,
                "pair_coverage": 1.0,
                "geometry_gold_ready": True,
                "final_gold_notes": [],
            },
            {
                "task_id": "696",
                "base_task_id": "b8cTxDM8gDG_298a2386166a43c8a04e1c24433f7d15",
                "final_scope_binary": "in_scope",
                "final_scope_alias": "normal",
                "geometry_gold_ready": True,
                "canonical_corners_norm": [{"id": 0, "x_pct": 1, "y_top_pct": 1, "y_bottom_pct": 99}],
                "runtime_pairs_1024x512": [{"x": 1, "y_ceiling": 1, "y_floor": 99}],
                "n_corners": 1,
                "pair_coverage": 1.0,
                "final_gold_notes": [],
            },
        ],
    )
    gt.write_text(
        json.dumps(
            [
                {
                    "id": 2590,
                    "inner_id": 106,
                    "data": {"title": "img106.jpg"},
                    "annotations": [
                        {
                            "id": 4843,
                            "result": [
                                _kp(10, 20),
                                _kp(10, 80),
                                _kp(30, 15),
                                _kp(30, 85),
                                _kp(50, 25),
                                _kp(50, 75),
                                _kp(70, 30),
                                _kp(70, 70),
                            ],
                        }
                    ],
                }
            ]
        ),
        encoding="utf-8",
    )

    outputs = apply_final_gold_v2_corrections(final_gold_jsonl=old_gold, export_gt_json=gt, output_dir=out)

    corrected = [json.loads(line) for line in outputs["corrected_final_gold_v2_jsonl"].read_text(encoding="utf-8").splitlines()]
    by_task = {row["task_id"]: row for row in corrected}
    audit = json.loads(outputs["audit_json"].read_text(encoding="utf-8"))

    assert len(by_task["564"]["runtime_pairs_1024x512"]) == 4
    assert by_task["696"]["final_scope_binary"] == "oos"
    assert by_task["696"]["final_scope_subtype"] == "oos_insufficient"
    assert by_task["696"]["final_scope_alias"] == "oos_insufficient"
    assert by_task["696"]["geometry_gold_ready"] is False
    assert by_task["696"]["canonical_corners_norm"] == []
    assert by_task["696"]["runtime_pairs_1024x512"] == []
    assert audit["source_final_gold_sha256"]
    assert audit["corrected_final_gold_v2_sha256"]
    assert audit["corrections"][0]["task_id"] == "564"
    assert audit["corrections"][0]["affected_runtime_tasks"] == ["3065", "3137"]
    assert audit["corrections"][1]["task_id"] == "696"
    assert audit["corrections"][1]["old_final_scope_binary"] == "in_scope"
    assert audit["corrections"][1]["new_final_scope_binary"] == "oos"
    assert audit["corrections"][1]["affected_runtime_tasks"] == ["3077", "3149"]
