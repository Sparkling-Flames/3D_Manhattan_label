from tools.thesis_main.analysis.audit_c2a_capacity_power_amendment import (
    capacity_curve,
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

