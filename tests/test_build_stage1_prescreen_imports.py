from pathlib import Path

from tools.label_studio.build_stage1_prescreen_imports import build_import_payloads, load_inputs


def test_build_stage1_prescreen_imports_counts_and_structure():
    repo_root = Path(__file__).resolve().parents[1]
    payloads = build_import_payloads(load_inputs(repo_root))

    manual_tasks = payloads["manual"]
    semi_tasks = payloads["semi"]
    semi_audit_stress_tasks = payloads["semi_audit_stress"]
    semi_audit_holdout_tasks = payloads["semi_audit_holdout"]
    oos_tasks = payloads["oos"]
    oos_audit_only_tasks = payloads["oos_audit_only"]
    summary = payloads["summary"]

    assert len(manual_tasks) == 30
    assert len(semi_tasks) == 18
    assert len(semi_audit_stress_tasks) == 0
    assert len(semi_audit_holdout_tasks) == 1
    assert len(oos_tasks) == 9
    assert len(oos_audit_only_tasks) == 1

    assert all("predictions" not in task for task in manual_tasks)
    assert all("predictions" in task for task in semi_tasks)
    assert all("predictions" in task for task in semi_audit_holdout_tasks)
    assert all("predictions" not in task for task in oos_tasks)

    control_count = sum(1 for task in semi_tasks if task["data"]["semi_role"] == "control")
    trap_count = sum(1 for task in semi_tasks if task["data"]["semi_role"] == "trap")
    synthetic_count = sum(1 for task in semi_tasks if task["data"]["source_type"] == "trap_synthetic")
    natural_count = sum(
        1
        for task in semi_tasks
        if task["data"]["source_type"] in {"control_natural", "trap_natural"}
    )

    assert control_count == 6
    assert trap_count == 12
    assert synthetic_count == 6
    assert natural_count == 12

    assert summary["manual_count"] == 30
    assert summary["semi_count"] == 18
    assert summary["semi_audit_stress_count"] == 0
    assert summary["semi_audit_fail_count"] == 0
    assert summary["semi_audit_topology_count"] == 0
    assert summary["semi_audit_holdout_count"] == 1
    assert summary["oos_gate_count"] == 9
    assert summary["oos_audit_only_count"] == 1
    assert summary["oos_directory_subtype_reconciliation_task_ids"] == ["560"]
    assert summary["semi_all_have_predictions"] is True
    assert summary["semi_audit_all_have_predictions"] is True
    assert summary["semi_holdout_all_have_predictions"] is True

    natural_rows = [
        task
        for task in semi_tasks
        if task["data"]["source_type"] in {"control_natural", "trap_natural"}
    ]
    synthetic_rows = [
        task
        for task in semi_tasks
        if task["data"]["source_type"] == "trap_synthetic"
    ]

    assert all(task["data"]["proposal_source_kind"] == "model_output_txt" for task in natural_rows)
    assert all(
        "output/mp3d_layout/HOHO_layout_aug_efficienthc_Transen1_resnet34/" in task["data"]["proposal_source_path"].replace("\\", "/")
        for task in natural_rows
    )
    assert all(task["data"]["proposal_source_kind"] == "frozen_synthetic_asset" for task in synthetic_rows)

    overextend_natural_ids = sorted(
        task["data"]["task_id"]
        for task in semi_tasks
        if task["data"]["trap_family"] == "overextend_adjacent"
        and task["data"]["source_type"] == "trap_natural"
    )
    assert overextend_natural_ids == ["493", "577", "668"]

    assert semi_audit_holdout_tasks[0]["data"]["trap_family"] == "fail"
    assert semi_audit_holdout_tasks[0]["data"]["task_id"] == "475"
    assert oos_audit_only_tasks[0]["data"]["task_id"] == "560"
    assert oos_audit_only_tasks[0]["data"]["family_dir"] == "边界不可判定"
    assert oos_audit_only_tasks[0]["data"]["scope_target"] == "oos_geometry"
