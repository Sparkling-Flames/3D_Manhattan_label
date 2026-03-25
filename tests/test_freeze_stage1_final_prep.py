from __future__ import annotations

from tools.freeze_stage1_final_prep import (
    build_oos_final_quota_binding,
    build_semi_control_keepdrop_resolution,
    build_stage1_final_binding_audit,
)


def test_build_semi_control_keepdrop_resolution_clears_stale_v4_blocker() -> None:
    registry_rows = [
        {
            "task_id": "492",
            "base_task_id": "base_492",
            "bucket_dir": "semi",
            "recommended_role": "semi_control_candidate",
            "default_eligible": "True",
            "priority_flag": "default",
            "review_note_flag": "False",
            "notes": "",
        },
        {
            "task_id": "501",
            "base_task_id": "base_501",
            "bucket_dir": "semi",
            "recommended_role": "semi_control_candidate",
            "default_eligible": "True",
            "priority_flag": "default",
            "review_note_flag": "False",
            "notes": "",
        },
        {
            "task_id": "568",
            "base_task_id": "base_568",
            "bucket_dir": "semi",
            "recommended_role": "semi_control_candidate",
            "default_eligible": "True",
            "priority_flag": "default",
            "review_note_flag": "False",
            "notes": "",
        },
        {
            "task_id": "572",
            "base_task_id": "base_572",
            "bucket_dir": "semi",
            "recommended_role": "semi_control_candidate",
            "default_eligible": "True",
            "priority_flag": "default",
            "review_note_flag": "False",
            "notes": "",
        },
        {
            "task_id": "573",
            "base_task_id": "base_573",
            "bucket_dir": "semi",
            "recommended_role": "semi_control_candidate",
            "default_eligible": "True",
            "priority_flag": "default",
            "review_note_flag": "False",
            "notes": "",
        },
        {
            "task_id": "576",
            "base_task_id": "base_576",
            "bucket_dir": "semi",
            "recommended_role": "semi_control_candidate",
            "default_eligible": "True",
            "priority_flag": "default",
            "review_note_flag": "False",
            "notes": "",
        },
        {"task_id": "470", "base_task_id": "manual_470", "bucket_dir": "manual"},
        {"task_id": "459", "base_task_id": "oos_459", "bucket_dir": "OOS"},
    ]
    semi_v4 = {"control_priority_flag_rows": ["base_576"]}
    source_pool_v1 = {"current_source_rows": [{"base_task_id": "source_a"}]}

    payload = build_semi_control_keepdrop_resolution(registry_rows, semi_v4, source_pool_v1)

    assert payload["selected_control_count"] == 6
    assert payload["control_binding_ready"] is True
    assert payload["selection_ready"] is True
    assert payload["current_priority_flag_rows"] == []
    assert payload["resolved_stale_priority_rows"][0]["task_id"] == "576"


def test_build_oos_final_quota_binding_keeps_low_priority_as_audit_only() -> None:
    registry_rows = [
        {
            "task_id": "459",
            "base_task_id": "oos_a",
            "bucket_dir": "OOS",
            "priority_flag": "default",
            "review_note_flag": "False",
            "default_eligible": "True",
            "current_scope_alias": "oos_open_boundary",
            "notes": "",
        },
        {
            "task_id": "560",
            "base_task_id": "oos_b",
            "bucket_dir": "OOS",
            "priority_flag": "low_priority",
            "review_note_flag": "True",
            "default_eligible": "False",
            "current_scope_alias": "oos_geometry",
            "notes": "",
        },
    ]

    payload, csv_rows = build_oos_final_quota_binding(registry_rows)

    assert payload["final_oos_gate_count"] == 1
    assert payload["audit_only_count"] == 1
    assert payload["low_priority_audit_only_task_ids"] == ["560"]
    row_560 = next(row for row in csv_rows if row["task_id"] == "560")
    assert row_560["final_role"] == "audit_only"
    assert row_560["selected_for_gate"] == "False"


def test_build_stage1_final_binding_audit_stays_blocked_on_non_final_gold() -> None:
    manual_selection = {
        "manual_total_selected": 30,
        "expert_anchor_count": 22,
        "non_anchor_count": 8,
    }
    manual_selection_rows = [{"base_task_id": "manual_a", "keep": "True"}]
    manual_binding_audit = {
        "manual_selection_frozen": True,
        "manual_binding_ready": False,
        "blocked_reasons": ["current reference layer remains working_consensus_not_final_gold rather than final adjudicated gold"],
    }
    semi_selection = {
        "selected_control_rows": [{"base_task_id": "semi_control_a"}],
        "selected_trap_rows": [{"base_task_id": "semi_trap_a"}],
        "current_selected_control_count": 6,
        "current_selected_trap_count": 12,
        "selection_ready": True,
        "semi_binding_ready": False,
        "binding_blocked_reasons": ["current reference layer remains working_consensus_not_final_gold rather than final adjudicated gold"],
    }
    oos_binding = {
        "selected_oos_gate_rows": [{"base_task_id": "oos_a"}],
        "final_oos_gate_count": 9,
        "oos_selection_frozen": True,
        "oos_selection_ready": True,
        "oos_binding_ready": False,
        "binding_blocked_reasons": ["current reference layer remains working_consensus_not_final_gold rather than final adjudicated gold"],
    }
    source_pool_v1 = {"current_source_rows": [{"base_task_id": "source_a"}]}

    payload = build_stage1_final_binding_audit(
        manual_selection,
        manual_selection_rows,
        manual_binding_audit,
        semi_selection,
        oos_binding,
        source_pool_v1,
    )

    assert payload["selection_freeze_complete"] is True
    assert payload["prescreen_ready"] is False
    assert payload["manual_vs_semi_overlap_count"] == 0
    assert payload["semi_control_vs_source_overlap_count"] == 0
