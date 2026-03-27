from __future__ import annotations

from pathlib import Path

from tools.revise_semi_selection_v8 import build_semi_v8, load_inputs, build_stage1_audit_v4


def test_build_semi_v8_restores_main_trap_count_and_uses_task580() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    inputs = load_inputs(repo_root)
    semi_v8 = build_semi_v8(inputs)

    assert semi_v8["current_selected_control_count"] == 6
    assert semi_v8["current_selected_trap_count"] == 12
    assert semi_v8["selection_ready"] is True
    assert semi_v8["semi_binding_ready"] is True

    natural_overextend_rows = [
        row
        for row in semi_v8["selected_trap_rows"]
        if row["family"] == "overextend_adjacent" and row["source_type"] == "trap_natural"
    ]
    assert [row["task_id"] for row in natural_overextend_rows] == ["493", "577", "580"]


def test_build_stage1_audit_v4_marks_prescreen_ready() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    inputs = load_inputs(repo_root)
    semi_v8 = build_semi_v8(inputs)
    audit_v4 = build_stage1_audit_v4(inputs, semi_v8)

    assert audit_v4["manual_binding_ready"] is True
    assert audit_v4["semi_binding_ready"] is True
    assert audit_v4["oos_binding_ready"] is True
    assert audit_v4["prescreen_ready"] is True
