from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from tools.build_experiment_visual_audit import (
    build_anomaly_audit_table,
    build_field_audit_table,
    build_scope_conflict_table,
    build_tag_summary,
    main,
    prepare_quality_frame,
)


def _sample_quality_df() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "task_id": "101",
                "annotator_id": "u1",
                "dataset_group": "SemiAuto_Test",
                "active_time": 12.0,
                "active_time_session_count": 1,
                "export_project_id": "p15",
                "script_version": "v1",
                "has_short_time_flag": False,
                "has_long_time_flag": False,
                "has_unknown_id_flag": False,
                "iou": 0.95,
                "layout_used": True,
                "layout_gate_reason": "",
                "scope": "normal",
                "scope_filled": True,
                "difficulty": "occlusion",
                "difficulty_filled": True,
                "model_issue": "acceptable",
                "model_issue_primary": "",
                "model_issue_required": True,
                "model_issue_missing_required": False,
                "model_issue_conflict": False,
                "difficulty_conflict": False,
                "task_scope_is_mixed": True,
                "type3_flag": False,
                "type4_flag": False,
                "pred_n_pairs": 4,
                "ann_n_pairs": 4,
                "boundary_rmse_px": 1.2,
                "iou_to_consensus_loo": 0.93,
            },
            {
                "task_id": "101",
                "annotator_id": "u2",
                "dataset_group": "SemiAuto_Test",
                "active_time": 130.0,
                "active_time_session_count": 2,
                "export_project_id": "",
                "script_version": "",
                "has_short_time_flag": False,
                "has_long_time_flag": False,
                "has_unknown_id_flag": True,
                "iou": 0.41,
                "layout_used": False,
                "layout_gate_reason": "out_of_scope",
                "scope": "oos_geometry",
                "scope_filled": True,
                "difficulty": "",
                "model_issue": "",
                "model_issue_primary": "",
                "model_issue_required": False,
                "model_issue_missing_required": False,
                "model_issue_conflict": False,
                "difficulty_filled": False,
                "difficulty_conflict": False,
                "task_scope_is_mixed": True,
                "type3_flag": False,
                "type4_flag": False,
                "pred_n_pairs": 6,
                "ann_n_pairs": 4,
                "boundary_rmse_px": 12.0,
                "iou_to_consensus_loo": 0.41,
                "is_oos": True,
            },
            {
                "task_id": "102",
                "annotator_id": "u3",
                "dataset_group": "PreScreen_manual",
                "active_time": 0.0,
                "active_time_session_count": 1,
                "export_project_id": "p16",
                "script_version": "v1",
                "has_short_time_flag": True,
                "has_long_time_flag": False,
                "has_unknown_id_flag": False,
                "iou": 0.88,
                "layout_used": False,
                "layout_gate_reason": "scope_missing",
                "scope": "",
                "scope_filled": False,
                "difficulty": "",
                "model_issue": "",
                "model_issue_primary": "",
                "model_issue_required": True,
                "model_issue_missing_required": True,
                "model_issue_conflict": False,
                "difficulty_filled": False,
                "difficulty_conflict": False,
                "task_scope_is_mixed": False,
                "type3_flag": False,
                "type4_flag": True,
                "pred_n_pairs": 3,
                "ann_n_pairs": 5,
                "boundary_rmse_px": 3.0,
                "iou_to_consensus_loo": 0.88,
            },
            {
                "task_id": "103",
                "annotator_id": "u4",
                "dataset_group": "Validation_semi",
                "active_time": 45.0,
                "active_time_session_count": 1,
                "export_project_id": "p17",
                "script_version": "v2",
                "has_short_time_flag": False,
                "has_long_time_flag": False,
                "has_unknown_id_flag": False,
                "iou": 0.91,
                "layout_used": True,
                "layout_gate_reason": "",
                "scope": "normal",
                "scope_filled": True,
                "difficulty": "trivial;occlusion",
                "difficulty_filled": True,
                "model_issue": "acceptable;underextend",
                "model_issue_primary": "underextend",
                "model_issue_required": True,
                "model_issue_missing_required": False,
                "model_issue_conflict": True,
                "difficulty_conflict": True,
                "task_scope_is_mixed": False,
                "type3_flag": True,
                "type4_flag": True,
                "pred_n_pairs": 5,
                "ann_n_pairs": 5,
                "boundary_rmse_px": 0.5,
                "iou_to_consensus_loo": 0.90,
            },
        ]
    )


def test_prepare_quality_frame_and_field_audit() -> None:
    prepared, metric_info = prepare_quality_frame(_sample_quality_df())
    audit = build_field_audit_table(prepared, metric_info).iloc[0]

    assert metric_info["quality_metric_column"] == "iou"
    assert metric_info["reliability_metric_column"] == "iou_to_consensus_loo"
    assert int(audit["n_rows"]) == 4
    assert int(audit["n_i_rows"]) == 2
    assert int(audit["n_m_rows"]) == 1
    assert int(audit["n_oos_rows"]) == 1
    assert int(audit["n_scope_missing_rows"]) == 1
    assert int(audit["n_type3_rows"]) == 1
    assert int(audit["n_layout_gate_fail_rows"]) == 2
    assert int(audit["n_model_issue_missing_required_rows"]) == 1
    assert int(audit["n_model_issue_conflict_rows"]) == 1
    assert int(audit["n_type4_rows"]) == 2
    assert int(audit["n_multi_session_rows"]) == 1
    assert int(audit["n_missing_script_version_rows"]) == 1
    assert int(audit["n_mixed_scope_tasks"]) == 1
    assert audit["session_count_column"] == "active_time_session_count"
    assert audit["project_id_column"] == "export_project_id"
    assert audit["type4_source"] == "type4_flag"


def test_scope_conflict_tag_summary_and_anomaly_audit() -> None:
    prepared, _ = prepare_quality_frame(_sample_quality_df())
    conflicts = build_scope_conflict_table(prepared)
    difficulty = build_tag_summary(prepared, "difficulty", default_alias="trivial")
    model_issue = build_tag_summary(prepared, "model_issue", default_alias="acceptable")
    anomaly = build_anomaly_audit_table(prepared, {"101"})

    assert list(conflicts["task_id"]) == ["101"]
    difficulty_by_tag = difficulty.set_index("tag")
    assert int(difficulty_by_tag.loc["occlusion", "n_rows"]) == 2
    assert bool(model_issue.set_index("tag").loc["acceptable", "is_default_alias"]) is True
    reasons = ";".join(anomaly["anomaly_reasons"].tolist())
    assert "mixed_scope_task" in reasons
    assert "type4_flag" in reasons
    assert "type3_flag" in reasons
    assert "layout_gate_failure" in reasons


def test_cli_materializes_visual_audit_pack(tmp_path: Path) -> None:
    quality_csv = tmp_path / "quality.csv"
    quality_df = _sample_quality_df()
    quality_df.to_csv(quality_csv, index=False)

    active_log_summary = tmp_path / "active_log_summary.json"
    active_log_summary.write_text(
        json.dumps(
            {
                "parse_error_count": 1,
                "parse_error_rate": 0.1,
                "unknown_task_count": 2,
                "unknown_task_rate": 0.2,
                "unknown_annotator_count": 0,
                "unknown_annotator_rate": 0.0,
                "unknown_project_count": 0,
                "unknown_project_rate": 0.0,
                "unknown_session_count": 1,
                "unknown_session_rate": 0.1,
                "missing_script_version_count": 3,
                "missing_script_version_rate": 0.3,
                "multi_session_pair_count": 1,
                "multi_session_pair_rate": 0.05,
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    active_log_per_file = tmp_path / "active_log_per_file.csv"
    pd.DataFrame(
        [
            {
                "file_name": "active_times_2026-03-29.jsonl",
                "parse_error_count": 1,
                "missing_script_version_count": 3,
            }
        ]
    ).to_csv(active_log_per_file, index=False)

    exit_code = main(
        [
            "--quality-csv",
            str(quality_csv),
            "--out-dir",
            str(tmp_path / "out"),
            "--tag",
            "demo_run",
            "--active-log-summary-json",
            str(active_log_summary),
            "--active-log-per-file-csv",
            str(active_log_per_file),
        ]
    )

    assert exit_code == 0
    out_dir = tmp_path / "out" / "demo_run"
    assert (out_dir / "summary.json").exists()
    assert (out_dir / "SUMMARY.md").exists()
    assert (out_dir / "table_field_audit.csv").exists()
    assert (out_dir / "table_schema_alignment.csv").exists()
    assert (out_dir / "table_b2_scope_conflict.csv").exists()
    assert (out_dir / "table_active_time_row_audit.csv").exists()
    assert (out_dir / "table_active_time_by_annotator.csv").exists()
    assert (out_dir / "table_active_log_summary.csv").exists()
    assert (out_dir / "01_tier_funnel.png").exists()
    assert (out_dir / "09_active_log_quality.png").exists()

    summary = json.loads((out_dir / "summary.json").read_text(encoding="utf-8"))
    assert summary["quality_metric_column"] == "iou"
    assert summary["session_count_column"] == "active_time_session_count"
    assert summary["project_id_column"] == "export_project_id"
    assert summary["field_audit"]["n_mixed_scope_tasks"] == 1
