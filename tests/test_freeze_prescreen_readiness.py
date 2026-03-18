from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent / "tools"))

from freeze_prescreen_readiness import (  # noqa: E402
    build_oos_gate_pool_freeze,
    build_prescreen_manual_anchor_inventory,
    build_prescreen_readiness_audit,
    build_prescreen_semi_selection_freeze,
)


def _manual_bank_row(**overrides):
    row = {
        "base_task_id": "scene_anchor_001",
        "planned_stage": "prescreen_manual",
        "dataset_group": "PreScreen_manual",
        "condition": "manual",
        "source_pools": "prescreen_manual;prescreen_manual_anchor",
        "registry_uids": "stage1_prescreen_manual:1;stage1_prescreen_manual_anchor:1",
        "registry_row_count": "2",
        "has_expert_ref": "True",
        "init_type": "",
    }
    row.update(overrides)
    return row


def _natural_failure_row(**overrides):
    row = {
        "bank_id": "nf_001",
        "recommended_role": "main_trap",
        "task_id": "501",
        "base_task_id": "scene_semi_001",
        "primary_issue_family": "acceptable",
        "preferred_registry_uid": "",
    }
    row.update(overrides)
    return row


def _materialized_row(**overrides):
    row = {
        "manifest_row_id": "ctrap_001",
        "target_registry_uid": "stage1_prescreen_semi:1",
        "base_task_id": "scene_semi_010",
        "operator_id": "over_parsing",
        "source_type": "synthetic_operator",
        "materialization_status": "realized",
    }
    row.update(overrides)
    return row


def _task_registry_row(**overrides):
    row = {
        "planned_stage": "prescreen_semi",
        "base_task_id": "scene_semi_stage1",
        "has_expert_ref": "False",
    }
    row.update(overrides)
    return row


def test_manual_anchor_inventory_only_counts_joinable_prescreen_expert_anchor_rows():
    rows = build_prescreen_manual_anchor_inventory(
        [
            _manual_bank_row(),
            _manual_bank_row(
                base_task_id="scene_anchor_candidate",
                source_pools="trap_collection",
                registry_uids="",
                registry_row_count="0",
            ),
            _manual_bank_row(planned_stage="calibration_manual"),
        ]
    )

    assert len(rows) == 2
    assert rows[0]["anchor_task_id"] == "stage1_prescreen_manual_anchor:1"
    assert rows[0]["joinable_for_prescreen_anchor_counting"] is True
    assert rows[1]["joinable_for_prescreen_anchor_counting"] is False
    assert rows[1]["range_collected_status"] == "collected"
    assert rows[1]["expert_annotation_status"] == "in_progress"
    assert rows[1]["status_field_source"] == "current_status_annotation"


def test_semi_selection_freeze_stays_not_ready_and_tracks_control_candidates():
    materialized_rows = [
        _materialized_row(),
        _materialized_row(manifest_row_id="ctrap_002", operator_id="corner_drift"),
        _materialized_row(manifest_row_id="ctrap_003", operator_id="underextend", materialization_status="reject"),
    ]
    natural_failure_rows = [
        _natural_failure_row(),
        _natural_failure_row(bank_id="nf_002", task_id="502", base_task_id="scene_semi_002"),
    ]
    family_target = {
        "target_total_tasks": 18,
        "normal_control_target": {"target_count": 6},
        "misleading_trap_target": {
            "target_count": 12,
            "default_target_families": ["over_parsing", "corner_drift", "corner_duplicate", "overextend_adjacent"],
        },
        "family_target_allocations": [
            {"family": "acceptable", "target_count": 6, "target_role": "normal_control"},
            {"family": "over_parsing", "target_count": 3, "target_role": "misleading_trap_default_family"},
            {"family": "corner_drift", "target_count": 3, "target_role": "misleading_trap_default_family"},
            {"family": "corner_duplicate", "target_count": 3, "target_role": "misleading_trap_default_family"},
            {"family": "overextend_adjacent", "target_count": 3, "target_role": "misleading_trap_default_family"},
            {"family": "underextend", "target_count": 0, "target_role": "misleading_trap_extension_family_not_required"},
        ],
    }
    bundle_gap = {
        "open_subedges": [
            {
                "subedge_id": "underextend+medium+4-corner+transform_degenerate",
                "family": "underextend",
            }
        ],
        "blocked_reasons": ["underextend subedge remains open"],
    }

    payload = build_prescreen_semi_selection_freeze(
        materialized_rows=materialized_rows,
        natural_failure_bank_rows=natural_failure_rows,
        prescreen_semi_family_target=family_target,
        current_bundle_gap=bundle_gap,
    )

    assert payload["selection_ready"] is False
    assert payload["selected_control_rows"] == []
    assert len(payload["current_control_candidate_rows"]) == 2
    assert len(payload["selected_trap_rows"]) == 2
    assert payload["control_gap"] == 6
    assert payload["open_subedges"][0]["subedge_id"] == "underextend+medium+4-corner+transform_degenerate"


def test_oos_gate_pool_freeze_uses_current_candidate_ids_and_keeps_ready_false():
    natural_failure_rows = [
        _natural_failure_row(
            bank_id="nf_009",
            recommended_role="oos_gate",
            task_id="459",
            base_task_id="scene_oos_001",
            primary_issue_family="oos_open_boundary",
            preferred_registry_uid="stage3_validation_semi:22",
        ),
        _natural_failure_row(
            bank_id="nf_010",
            recommended_role="oos_gate",
            task_id="526",
            base_task_id="scene_oos_002",
            primary_issue_family="oos_geometry",
            preferred_registry_uid="",
        ),
    ]
    task_registry_rows = [
        _task_registry_row(planned_stage="prescreen_manual", base_task_id="scene_manual_001", has_expert_ref="True"),
        _task_registry_row(planned_stage="prescreen_semi", base_task_id="scene_semi_stage1"),
    ]

    payload = build_oos_gate_pool_freeze(
        natural_failure_bank_rows=natural_failure_rows,
        task_registry_rows=task_registry_rows,
    )

    assert payload["candidate_pool_exists"] is True
    assert payload["target_quota_declared"] is False
    assert payload["current_candidate_ids"] == ["459", "526"]
    assert payload["manual_anchor_overlap_count"] == 0
    assert payload["semi_pool_overlap_count"] == 0
    assert payload["ready_for_prescreen"] is False


def test_prescreen_readiness_audit_rolls_up_false_states_without_overclaim():
    phase1_manifest = {
        "items": [
            {
                "item_id": "stage1_prescreen_manual_expert_anchor",
                "thesis_target": {"min": 20, "max": 22},
            },
            {
                "item_id": "stage1_prescreen_manual_non_anchor",
                "thesis_target": {"min": 8, "max": 10},
                "current_repo": {"derived_from_split_report": 18},
            },
            {
                "item_id": "stage1_prescreen_semi_total",
                "thesis_target": {"value": 18},
            },
        ]
    }
    manual_inventory_rows = build_prescreen_manual_anchor_inventory(
        [
            _manual_bank_row(),
            _manual_bank_row(
                base_task_id="scene_anchor_candidate",
                source_pools="trap_collection",
                registry_uids="",
                registry_row_count="0",
            ),
        ]
    )
    semi_selection_freeze = {
        "control_target": 6,
        "misleading_trap_target": 12,
        "current_bundle_rows": 15,
        "current_realized_rows": 13,
        "selection_ready": False,
        "blocked_reasons": ["control subset is still unfrozen"],
    }
    oos_gate_pool_freeze = {
        "current_candidate_ids": ["459", "526"],
        "target_quota_declared": False,
        "ready_for_prescreen": False,
        "blocked_reasons": ["current OOS rows remain a candidate bank"],
    }

    payload = build_prescreen_readiness_audit(
        phase1_manifest=phase1_manifest,
        manual_inventory_rows=manual_inventory_rows,
        semi_selection_freeze=semi_selection_freeze,
        oos_gate_pool_freeze=oos_gate_pool_freeze,
    )

    assert payload["manual_anchor_current_joinable_count"] == 1
    assert payload["manual_anchor_range_collected"] is True
    assert payload["manual_anchor_expert_annotation_status"] == "range_collected_annotation_in_progress"
    assert payload["manual_anchor_ready"] is False
    assert payload["semi_selection_ready"] is False
    assert payload["oos_gate_target_declared"] is False
    assert payload["prescreen_overall_ready"] is False
