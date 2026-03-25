from __future__ import annotations

import csv
import json
from pathlib import Path

from tools.extract_truth_layer import (
    build_oos_reconciliation_case,
    classify_priority_flag,
    run,
)


def _sample_keypoints() -> list[dict]:
    return [
        {
            "from_name": "kp",
            "type": "keypointlabels",
            "original_width": 1024,
            "original_height": 512,
            "value": {"x": 10, "y": 20, "keypointlabels": ["Corner"]},
        },
        {
            "from_name": "kp",
            "type": "keypointlabels",
            "original_width": 1024,
            "original_height": 512,
            "value": {"x": 10, "y": 80, "keypointlabels": ["Corner"]},
        },
        {
            "from_name": "kp",
            "type": "keypointlabels",
            "original_width": 1024,
            "original_height": 512,
            "value": {"x": 40, "y": 25, "keypointlabels": ["Corner"]},
        },
        {
            "from_name": "kp",
            "type": "keypointlabels",
            "original_width": 1024,
            "original_height": 512,
            "value": {"x": 40, "y": 75, "keypointlabels": ["Corner"]},
        },
    ]


def test_classify_priority_flag_respects_711_exception() -> None:
    assert classify_priority_flag("") == "default"
    assert classify_priority_flag("低优先") == "low_priority"
    assert classify_priority_flag("墙角太难了,低优先") == "low_priority"
    assert classify_priority_flag("中低优先,难标注") == "special_review"
    assert classify_priority_flag("可能有歧义") == "special_review"


def test_build_oos_reconciliation_case_reports_no_active_mismatch() -> None:
    payload = build_oos_reconciliation_case([], Path("project-20-at-2026-03-25.json"))

    assert payload["case_status"] == "no_active_mismatch_after_directory_update"
    assert payload["directory_sync_needed"] is False
    assert payload["needs_followup"] is False


def test_run_extracts_registry_and_annotation_records(tmp_path: Path) -> None:
    export_root = tmp_path / "export_label"
    export_root.mkdir()
    trap_root = tmp_path / "trappool"
    manual_family = trap_root / "manual" / "遮罩"
    oos_family = trap_root / "OOS" / "边界不可判定"
    manual_task = manual_family / "task711(中低优先,难标注)"
    oos_task = oos_family / "task202"
    manual_task.mkdir(parents=True)
    oos_task.mkdir(parents=True)

    (manual_family / "特别注意.md").write_text("711 > 696，当前保留为 manual non-anchor。", encoding="utf-8")
    (manual_task / "base_a.txt").write_text("100 100\n100 400\n300 110\n300 390\n", encoding="utf-8")
    (oos_task / "base_b.txt").write_text("120 90\n120 410\n500 100\n500 400\n", encoding="utf-8")

    export_payload = [
        {
            "id": 1,
            "data": {
                "title": "base_a.jpg",
                "image": "https://example.com/base_a.jpg",
            },
            "annotations": [
                {
                    "id": 11,
                    "completed_by": 2,
                    "result": _sample_keypoints()
                    + [
                        {"from_name": "scope", "type": "choices", "value": {"choices": ["normal"]}},
                        {"from_name": "difficulty", "type": "choices", "value": {"choices": ["occlusion"]}},
                        {"from_name": "model_issue", "type": "choices", "value": {"choices": ["acceptable"]}},
                    ],
                }
            ],
        },
        {
            "id": 2,
            "data": {
                "title": "base_b.jpg",
                "image": "https://example.com/base_b.jpg",
            },
            "annotations": [
                {
                    "id": 22,
                    "completed_by": 2,
                    "result": _sample_keypoints()
                    + [
                        {"from_name": "scope", "type": "choices", "value": {"choices": ["oos_open_boundary"]}},
                        {"from_name": "difficulty", "type": "choices", "value": {"choices": ["occlusion"]}},
                        {"from_name": "model_issue", "type": "choices", "value": {"choices": ["fail"]}},
                    ],
                }
            ],
        },
    ]
    export_path = export_root / "project-20-at-2026-03-25-01-17-926f4b7f.json"
    export_path.write_text(json.dumps(export_payload, ensure_ascii=False, indent=2), encoding="utf-8")

    output_dir = tmp_path / "out"
    outputs = run(output_dir=output_dir, root=tmp_path)

    assert outputs["registry"].exists()
    assert outputs["annotation_records"].exists()
    assert outputs["summary"].exists()

    with outputs["registry"].open("r", encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    assert len(rows) == 2

    manual_row = next(row for row in rows if row["task_id"] == "711")
    oos_row = next(row for row in rows if row["task_id"] == "202")
    assert manual_row["priority_flag"] == "special_review"
    assert manual_row["recommended_role"] == "manual_non_anchor_candidate"
    assert manual_row["trap_family"] == "遮罩"
    assert manual_row["priority_annotation"] == "中低优先,难标注"
    assert oos_row["recommended_role"] == "oos_gate_candidate"
    assert oos_row["directory_scope_mismatch"] == "False"

    annotation_rows = [
        json.loads(line)
        for line in outputs["annotation_records"].read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    assert len(annotation_rows) == 2
    assert annotation_rows[0]["legacy_txt_not_authoritative"] is True
    assert len(annotation_rows[0]["canonical_corners_norm"]) == 2

    summary = json.loads(outputs["summary"].read_text(encoding="utf-8"))
    assert summary["n_tasks_total"] == 2
    assert summary["n_directory_scope_mismatch"] == 0
    assert summary["summary_status"] == "working_consensus_extraction_ready_not_final_gold"
