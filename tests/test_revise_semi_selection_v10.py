from __future__ import annotations

from pathlib import Path

from tools.revise_semi_selection_v10 import build_semi_v10, build_stage1_audit_v6, load_inputs


def test_build_semi_v10_replaces_task580_with_task668() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    inputs = load_inputs(repo_root)
    semi_v10 = build_semi_v10(inputs)

    assert semi_v10["current_selected_control_count"] == 6
    assert semi_v10["current_selected_trap_count"] == 12
    assert semi_v10["selection_ready"] is True
    assert semi_v10["semi_binding_ready"] is True

    natural_overextend_rows = [
        row
        for row in semi_v10["selected_trap_rows"]
        if row["family"] == "overextend_adjacent" and row["source_type"] == "trap_natural"
    ]
    assert [row["task_id"] for row in natural_overextend_rows] == ["493", "577", "668"]


def test_build_stage1_audit_v6_keeps_prescreen_ready() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    inputs = load_inputs(repo_root)
    semi_v10 = build_semi_v10(inputs)
    audit_v6 = build_stage1_audit_v6(inputs, semi_v10)

    assert audit_v6["manual_binding_ready"] is True
    assert audit_v6["semi_binding_ready"] is True
    assert audit_v6["oos_binding_ready"] is True
    assert audit_v6["prescreen_ready"] is True
