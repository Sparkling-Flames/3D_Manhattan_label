from __future__ import annotations

from pathlib import Path

from tools.revise_semi_selection_v9 import build_semi_v9, build_stage1_audit_v5, load_inputs


def test_build_semi_v9_removes_active_fail_audit_and_keeps_holdout() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    inputs = load_inputs(repo_root)
    semi_v9 = build_semi_v9(inputs)

    assert semi_v9["current_selected_control_count"] == 6
    assert semi_v9["current_selected_trap_count"] == 12
    assert semi_v9["audit_stress_candidates"]["fail_task_ids"] == []
    assert semi_v9["audit_stress_holdout_candidates"]["fail_task_ids"] == ["475"]


def test_build_stage1_audit_v5_stays_prescreen_ready() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    inputs = load_inputs(repo_root)
    semi_v9 = build_semi_v9(inputs)
    audit_v5 = build_stage1_audit_v5(inputs, semi_v9)

    assert audit_v5["manual_binding_ready"] is True
    assert audit_v5["semi_binding_ready"] is True
    assert audit_v5["oos_binding_ready"] is True
    assert audit_v5["prescreen_ready"] is True
