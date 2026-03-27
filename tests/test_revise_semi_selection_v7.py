from pathlib import Path

from tools.revise_semi_selection_v7 import build_semi_v7, build_stage1_audit_v3, _load_inputs


def test_revise_semi_selection_v7_applies_semantic_tightening():
    repo_root = Path(__file__).resolve().parents[1]
    inputs = _load_inputs(repo_root)

    semi_v7 = build_semi_v7(inputs)
    stage1_audit_v3 = build_stage1_audit_v3(inputs, semi_v7)

    natural_rows = [row for row in semi_v7["selected_trap_rows"] if row["source_type"] == "trap_natural"]
    natural_corner_drift_rows = [row for row in natural_rows if row["family"] == "corner_drift"]
    natural_overextend_rows = [row for row in natural_rows if row["family"] == "overextend_adjacent"]
    synthetic_overextend_rows = [
        row
        for row in semi_v7["selected_trap_rows"]
        if row["family"] == "overextend_adjacent" and row["source_type"] == "trap_synthetic_disjoint_source"
    ]

    assert semi_v7["selection_name"] == "prescreen_semi_final_selection_v7"
    assert semi_v7["current_selected_control_count"] == 6
    assert semi_v7["current_selected_trap_count"] == 11
    assert semi_v7["selection_ready"] is False
    assert semi_v7["semi_binding_ready"] is False

    assert [row["task_id"] for row in natural_corner_drift_rows] == ["625"]
    assert [row["task_id"] for row in natural_overextend_rows] == ["493", "577"]
    assert synthetic_overextend_rows == []

    overextend_alloc = next(
        row for row in semi_v7["family_allocations"] if row["family"] == "overextend_adjacent"
    )
    assert overextend_alloc["current_selected_count"] == 2
    assert overextend_alloc["current_gap_count"] == 1

    assert stage1_audit_v3["manual_binding_ready"] is True
    assert stage1_audit_v3["oos_binding_ready"] is True
    assert stage1_audit_v3["semi_binding_ready"] is False
    assert stage1_audit_v3["prescreen_ready"] is False
