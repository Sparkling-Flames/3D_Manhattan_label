from __future__ import annotations

import csv
import json
from pathlib import Path

from tools.freeze_prescreen_manual import freeze_manual_selection, run


def _manual_registry_rows() -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []

    for idx in range(1, 18):
        rows.append(
            {
                "task_id": str(100 + idx),
                "base_task_id": f"manual_anchor_base_{idx}",
                "bucket_dir": "manual",
                "trap_family": "非常简单" if idx <= 4 else "遮挡明显",
                "current_scope_alias": "normal",
                "scope_binary": "in_scope",
                "difficulty_tags": "trivial" if idx <= 4 else "occlusion",
                "model_issue_tags": "acceptable",
                "has_kp": "True",
                "has_poly": "False",
                "has_txt": "True",
                "txt_role": "legacy_mp3d_reference",
                "geometry_truth_source": "project20_kp",
                "priority_annotation": "",
                "priority_flag": "default",
                "has_folder_note": "False",
                "recommended_role": "manual_anchor_candidate",
                "review_note_flag": "False",
                "needs_manual_review": "False",
                "default_eligible": "True",
                "directory_scope_mismatch": "False",
                "notes": "",
            }
        )

    reviewed_cases = {
        "509": ("玻璃", "可能有歧义", "special_review", "manual_anchor_candidate", "True"),
        "564": ("遮挡明显", "较为困难", "special_review", "manual_anchor_candidate", "True"),
        "567": ("玻璃", "低优先", "low_priority", "manual_non_anchor_candidate", "False"),
        "569": ("纹理弱 纯色墙", "同时是一角多点,纹理弱", "special_review", "manual_anchor_candidate", "True"),
        "570": ("拼接缝及拉伸", "同时是角点错位", "special_review", "manual_anchor_candidate", "True"),
        "635": ("遮挡明显", "低优先,有歧义,尽量不考虑", "low_priority", "manual_non_anchor_candidate", "False"),
        "676": ("遮挡明显", "低优先,太难标注了,暂时不考虑", "low_priority", "manual_non_anchor_candidate", "False"),
        "677": ("遮挡明显", "略微有点遮挡", "special_review", "manual_anchor_candidate", "True"),
        "696": ("遮罩", "低优先,不确定,难标注", "low_priority", "manual_non_anchor_candidate", "False"),
        "711": ("遮罩", "中低优先,难标注", "special_review", "manual_non_anchor_candidate", "True"),
        "714": ("玻璃", "高难度", "special_review", "manual_anchor_candidate", "True"),
    }
    for task_id, (family, annotation, priority, role, default_eligible) in reviewed_cases.items():
        rows.append(
            {
                "task_id": task_id,
                "base_task_id": f"manual_case_base_{task_id}",
                "bucket_dir": "manual",
                "trap_family": family,
                "current_scope_alias": "normal",
                "scope_binary": "in_scope",
                "difficulty_tags": "occlusion",
                "model_issue_tags": "corner_drift",
                "has_kp": "True",
                "has_poly": "False",
                "has_txt": "True",
                "txt_role": "legacy_mp3d_reference",
                "geometry_truth_source": "project20_kp",
                "priority_annotation": annotation,
                "priority_flag": priority,
                "has_folder_note": "False",
                "recommended_role": role,
                "review_note_flag": "True",
                "needs_manual_review": "True",
                "default_eligible": default_eligible,
                "directory_scope_mismatch": "False",
                "notes": f"priority_annotation={annotation}",
            }
        )

    rows.extend(
        [
            {
                "task_id": "462",
                "base_task_id": "manual_audit_base_462",
                "bucket_dir": "manual",
                "trap_family": "拼接缝及拉伸",
                "current_scope_alias": "normal",
                "scope_binary": "in_scope",
                "difficulty_tags": "low_texture;seam",
                "model_issue_tags": "corner_drift",
                "has_kp": "True",
                "has_poly": "False",
                "has_txt": "True",
                "txt_role": "legacy_mp3d_reference",
                "geometry_truth_source": "project20_kp",
                "priority_annotation": "",
                "priority_flag": "default",
                "has_folder_note": "True",
                "recommended_role": "audit_only",
                "review_note_flag": "True",
                "needs_manual_review": "True",
                "default_eligible": "False",
                "directory_scope_mismatch": "False",
                "notes": "unstable geometry note",
            },
            {
                "task_id": "533",
                "base_task_id": "manual_audit_base_533",
                "bucket_dir": "manual",
                "trap_family": "遮挡明显",
                "current_scope_alias": "normal",
                "scope_binary": "in_scope",
                "difficulty_tags": "occlusion",
                "model_issue_tags": "corner_drift",
                "has_kp": "True",
                "has_poly": "False",
                "has_txt": "True",
                "txt_role": "legacy_mp3d_reference",
                "geometry_truth_source": "project20_kp",
                "priority_annotation": "低优先,有歧义",
                "priority_flag": "low_priority",
                "has_folder_note": "True",
                "recommended_role": "audit_only",
                "review_note_flag": "True",
                "needs_manual_review": "True",
                "default_eligible": "False",
                "directory_scope_mismatch": "False",
                "notes": "severe missing evidence",
            },
        ]
    )

    rows.extend(
        [
            {
                "task_id": "800",
                "base_task_id": "semi_base_1",
                "bucket_dir": "semi",
                "trap_family": "模型标注质量好",
                "current_scope_alias": "normal",
                "scope_binary": "in_scope",
                "difficulty_tags": "occlusion",
                "model_issue_tags": "acceptable",
                "has_kp": "True",
                "has_poly": "False",
                "has_txt": "True",
                "txt_role": "legacy_mp3d_reference",
                "geometry_truth_source": "project20_kp",
                "priority_annotation": "",
                "priority_flag": "default",
                "has_folder_note": "False",
                "recommended_role": "semi_control_candidate",
                "review_note_flag": "False",
                "needs_manual_review": "False",
                "default_eligible": "True",
                "directory_scope_mismatch": "False",
                "notes": "",
            },
            {
                "task_id": "900",
                "base_task_id": "oos_base_1",
                "bucket_dir": "OOS",
                "trap_family": "边界不可判定",
                "current_scope_alias": "oos_open_boundary",
                "scope_binary": "oos",
                "difficulty_tags": "occlusion",
                "model_issue_tags": "corner_drift",
                "has_kp": "True",
                "has_poly": "False",
                "has_txt": "True",
                "txt_role": "legacy_mp3d_reference",
                "geometry_truth_source": "project20_kp",
                "priority_annotation": "",
                "priority_flag": "default",
                "has_folder_note": "False",
                "recommended_role": "oos_gate_candidate",
                "review_note_flag": "False",
                "needs_manual_review": "False",
                "default_eligible": "True",
                "directory_scope_mismatch": "False",
                "notes": "",
            },
        ]
    )

    return rows


def _annotation_rows() -> list[dict]:
    rows = []
    for row in _manual_registry_rows():
        if row["bucket_dir"] == "manual":
            rows.append(
                {
                    "task_id": row["task_id"],
                    "base_task_id": row["base_task_id"],
                    "bucket_dir": "manual",
                    "scope": row["current_scope_alias"],
                    "difficulty": [p for p in row["difficulty_tags"].split(";") if p],
                    "model_issue": [p for p in row["model_issue_tags"].split(";") if p],
                    "poly_residue_flag": row["task_id"] in {"578", "707"},
                    "adjudication_status": "working_consensus_not_final_gold",
                }
            )
    return rows


def test_freeze_manual_selection_demotes_one_reviewed_anchor_to_meet_quota() -> None:
    selection_rows, selection_summary, audit_payload = freeze_manual_selection(
        _manual_registry_rows(),
        _annotation_rows(),
    )

    assert len(selection_rows) == 30
    assert selection_summary["expert_anchor_count"] == 22
    assert selection_summary["non_anchor_count"] == 8
    assert selection_summary["promoted_anchor_task_ids"] == []
    assert selection_summary["demoted_anchor_candidate_task_ids"] == ["509"]
    assert selection_summary["manual_binding_ready"] is False
    assert audit_payload["manual_binding_ready"] is False

    role_by_task = {row["task_id"]: row["final_role"] for row in selection_rows}
    assert role_by_task["509"] == "non_anchor"
    assert role_by_task["569"] == "expert_anchor"
    assert role_by_task["677"] == "expert_anchor"
    assert role_by_task["711"] == "non_anchor"
    assert role_by_task["462"] == "non_anchor"
    assert role_by_task["533"] == "non_anchor"


def test_run_writes_manual_selection_outputs(tmp_path: Path) -> None:
    truth_dir = tmp_path / "analysis_results" / "truth_layer_extraction_20260324"
    truth_dir.mkdir(parents=True)

    with (truth_dir / "trap_task_registry_v1.csv").open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(_manual_registry_rows()[0].keys()))
        writer.writeheader()
        writer.writerows(_manual_registry_rows())

    with (truth_dir / "manual_annotation_records_v1.jsonl").open("w", encoding="utf-8") as handle:
        for row in _annotation_rows():
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")

    output_dir = tmp_path / "analysis_results" / "phase1_progress_20260324"
    outputs = run(output_dir=output_dir, root=tmp_path)

    assert outputs["selection_json"].exists()
    assert outputs["selection_csv"].exists()
    assert outputs["binding_audit"].exists()

    selection_summary = json.loads(outputs["selection_json"].read_text(encoding="utf-8"))
    assert selection_summary["expert_anchor_count"] == 22
    assert selection_summary["non_anchor_count"] == 8
    assert selection_summary["demoted_anchor_candidate_task_ids"] == ["509"]

    with outputs["selection_csv"].open("r", encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    assert len(rows) == 30
    assert any(row["task_id"] == "677" and row["final_role"] == "expert_anchor" for row in rows)
    assert any(row["task_id"] == "711" and row["final_role"] == "non_anchor" for row in rows)

    binding_audit = json.loads(outputs["binding_audit"].read_text(encoding="utf-8"))
    assert binding_audit["anchor_target_met"] is True
    assert binding_audit["non_anchor_target_met"] is True
    assert binding_audit["manual_binding_ready"] is False


def test_freeze_manual_selection_keeps_existing_anchor_pool_when_already_in_range() -> None:
    registry_rows = _manual_registry_rows()
    for task_id in {"509", "569"}:
        row = next(item for item in registry_rows if item["task_id"] == task_id)
        row["recommended_role"] = "manual_non_anchor_candidate"

    selection_rows, selection_summary, _ = freeze_manual_selection(
        registry_rows,
        _annotation_rows(),
    )

    assert selection_summary["expert_anchor_count"] == 21
    assert selection_summary["non_anchor_count"] == 9
    assert selection_summary["promoted_anchor_task_ids"] == []
    assert selection_summary["demoted_anchor_candidate_task_ids"] == []
    assert any(
        row["task_id"] == "677" and row["final_role"] == "expert_anchor"
        for row in selection_rows
    )
