from pathlib import Path

from tools.thesis_main.registry.freeze_prescreen_selection import (
    build_oos_gate_target_freeze_v2,
    build_prescreen_manual_final_selection,
    build_prescreen_manual_non_anchor_selection,
    build_prescreen_semi_final_selection,
)


def _manual_inventory_row(**overrides):
    row = {
        "anchor_task_id": "stage1_prescreen_manual_anchor:1",
        "base_task_id": "scene_anchor_001",
        "joinable_for_prescreen_anchor_counting": True,
    }
    row.update(overrides)
    return row


def _task_registry_row(**overrides):
    row = {
        "registry_uid": "stage1_prescreen_manual:13",
        "planned_stage": "prescreen_manual",
        "base_task_id": "scene_non_anchor_001",
        "has_expert_ref": False,
    }
    row.update(overrides)
    return row


def _semi_selection_freeze(**overrides):
    row = {
        "target_total": 18,
        "control_target": 6,
        "misleading_trap_target": 12,
        "selected_control_rows": [],
        "current_control_candidate_rows": [{"bank_id": "nf_001"}],
        "selected_trap_rows": [{"manifest_row_id": "ctrap_001"} for _ in range(11)],
        "control_gap": 6,
        "family_allocations": [],
        "open_subedges": [{"subedge_id": "underextend+medium+4-corner+transform_degenerate"}],
        "blocked_reasons": ["underextend remains open"],
    }
    row.update(overrides)
    return row


def _oos_pool_freeze(**overrides):
    row = {
        "target_role": "candidate_bank_for_scope_gate_not_geometry_gt",
        "current_candidate_ids": ["459", "526"],
        "candidate_bank_ids": ["nf_009", "nf_010"],
        "oos_family_counts": {"oos_open_boundary": 1, "oos_geometry": 1},
        "manual_anchor_overlap_count": 0,
        "semi_pool_overlap_count": 0,
        "blocked_reasons": ["target quota not declared"],
    }
    row.update(overrides)
    return row


def _natural_failure_row(**overrides):
    row = {
        "recommended_role": "oos_gate",
        "preferred_registry_uid": "stage3_validation_semi:22",
        "task_registry_planned_stages": "validation_semi",
    }
    row.update(overrides)
    return row


def test_manual_final_selection_stays_blocked_when_known_pool_is_below_target():
    phase1_manifest = {
        "items": [
            {
                "item_id": "stage1_prescreen_manual_expert_anchor",
                "thesis_target": {"min": 20, "max": 22},
            }
        ]
    }
    rows = [_manual_inventory_row() for _ in range(12)] + [
        _manual_inventory_row(anchor_task_id="", base_task_id=f"supp_{i}", joinable_for_prescreen_anchor_counting=False)
        for i in range(4)
    ]

    payload = build_prescreen_manual_final_selection(
        manual_inventory_rows=rows,
        phase1_manifest=phase1_manifest,
    )

    assert payload["current_joinable_anchor_count"] == 12
    assert payload["current_known_anchor_candidate_count"] == 16
    assert payload["anchor_gap_to_target_min"] == 4
    assert payload["selection_ready"] is False


def test_manual_non_anchor_selection_requires_future_keep_drop_freeze():
    phase1_manifest = {
        "items": [
            {
                "item_id": "stage1_prescreen_manual_non_anchor",
                "thesis_target": {"min": 8, "max": 10},
            }
        ]
    }
    rows = [_task_registry_row(registry_uid=f"stage1_prescreen_manual:{idx}") for idx in range(18)]

    payload = build_prescreen_manual_non_anchor_selection(
        task_registry_rows=rows,
        phase1_manifest=phase1_manifest,
    )

    assert payload["current_candidate_count"] == 18
    assert payload["selected_non_anchor_registry_uids"] == []
    assert payload["selection_ready"] is False


def test_semi_final_selection_keeps_selection_ready_false_with_trap_and_control_gaps():
    payload = build_prescreen_semi_final_selection(_semi_selection_freeze())

    assert payload["current_selected_control_count"] == 0
    assert payload["current_selected_trap_count"] == 11
    assert payload["control_gap"] == 6
    assert payload["trap_gap"] == 1
    assert payload["selection_ready"] is False


def test_oos_target_freeze_v2_stays_blocked_without_stage1_quota_or_binding():
    payload = build_oos_gate_target_freeze_v2(
        oos_gate_pool_freeze=_oos_pool_freeze(),
        natural_failure_bank_rows=[
            _natural_failure_row(task_registry_planned_stages="validation_semi"),
            _natural_failure_row(preferred_registry_uid="", task_registry_planned_stages="manual_test;semiauto_test"),
        ],
    )

    assert payload["target_quota"] is None
    assert payload["target_quota_declared"] is False
    assert payload["dedicated_stage1_registry_bound_candidate_count"] == 0
    assert payload["target_freeze_ready"] is False
