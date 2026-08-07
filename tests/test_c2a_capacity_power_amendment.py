import json
from pathlib import Path

from tools.thesis_main.analysis.audit_c2a_capacity_power_amendment import (
    select_real_reserve,
    capacity_curve,
    materialize_distribution,
    power_scenario,
)


def test_one_new_stress_task_closes_two_worker_gap():
    workers = [{"worker_id": str(i)} for i in range(4)]
    tasks = [
        {"task_id": f"o{i}", "base_task_id": f"o{i}", "task_stratum": "ordinary", "c2a_rp_eligible": "true"}
        for i in range(2)
    ] + [{"task_id": "s0", "base_task_id": "s0", "task_stratum": "stress", "c2a_rp_eligible": "true"}]
    rows = capacity_curve(workers, tasks, [], max_task_support=2, max_new_stress=1)
    assert [row["maximum_block1_workers"] for row in rows] == [2, 4]


def test_boundary_model_has_no_policy_divergence_or_quality_effect():
    workers = [
        {"worker_id": "1", "Q_GT_EB": "0.90", "risk_slope_support": "8", "risk_slope_se": "0.01"},
        {"worker_id": "2", "Q_GT_EB": "0.89", "risk_slope_support": "8", "risk_slope_se": "0.01"},
    ]
    result = power_scenario(
        workers,
        {"1": -0.02, "2": -0.02},
        target_half_width=0.02,
        stress_fraction=0.2,
        total_v1_tasks=100,
        outcome_sd=0.1,
        blocks=1,
        draws=100,
        seed=1,
        force_no_adjustment=True,
    )
    assert result["policy_divergence"] == 0
    assert result["expected_quality_difference"] == 0


def test_real_reserve_uses_frozen_validation_holdout_only():
    rows = select_real_reserve(
        [],
        [{"base_task_id": "a", "formal_dataset_split": "mp3d_validation", "risk_design_stratum": "stress", "risk_design_score_A": "2", "building_id": "b", "image_path": "u"}],
        [{"base_task_id": "a", "history_clear": "true", "scope_ready": "true", "reference_ready": "true", "feature_ready": "true", "risk_ready": "true", "leakage_clear": "true", "exclusion_reason": "source_split_not_clear;future_holdout_not_clear", "task_risk_sha256": "s"}],
        [],
        primary_count=1,
    )
    assert rows[0]["capacity_role"] == "block1_primary"


def test_distribution_preserves_approved_20_by_2_assignment(tmp_path: Path):
    source = Path("analysis_results/c2a_rp_capacity_power_amendment_20260807_v1")
    result = materialize_distribution(tmp_path / "distribution", source)
    assert result["assignment_unchanged"] is True
    assert result["worker_count"] == 20
    assert result["assignment_count"] == 40
    assert result["maximum_blocks_per_worker"] == 5
    assert result["future_blocks_preassigned"] is False
    assert len(result["private_list_sha256"]) == 20
    mapping = Path(result["operational_package"]["runtime_mapping_path"]).read_text(encoding="utf-8-sig")
    assert len({line.split(",")[12] for line in mapping.splitlines()[1:]}) == 20
    for deployment in result["operational_package"]["deployments"].values():
        assert json.loads(Path(deployment["planned_import_path"]).read_text(encoding="utf-8"))
