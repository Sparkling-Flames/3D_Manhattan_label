from pathlib import Path

import pandas as pd
import pytest

from tools.paper_a_manhattan.full_uncertainty.audit_v5_supplement import (
    SchemaError,
    bh_adjust,
    build_frames,
    partition_failure_rate_sensitivity,
    semi_power_estimand_sensitivity,
)


V5 = Path("analysis_results/full_uncertainty_data_mining_20260821_v5")


def test_v5_supplement_contract_and_counts():
    frames = build_frames(V5, bootstrap_replicates=1)
    assert len(frames) == 8
    assert all(name.endswith(".csv") for name in frames)
    image = frames["IMAGE_FEATURE_ASSOCIATIONS_BUILDING_CLUSTERED.csv"]
    assert len(image) == 72
    assert image["predictor_duplicate_alias"].sum() == 9
    assert (~image["predictor_duplicate_alias"]).sum() == 63
    partition = frames["PARTITION_FAILURE_RATE_SENSITIVITY.csv"]
    assert set(partition["estimand"]) == {"task_equal", "building_equal"}
    estimates = partition.set_index("estimand")["estimate"]
    assert estimates["task_equal"] == pytest.approx(-0.016)
    assert estimates["building_equal"] == pytest.approx(-0.014814814814814815)
    join = frames["DIFFICULTY_PROXY_OUTCOME_JOIN_AUDIT.csv"].iloc[0]
    assert (join["matched_task_count"], join["missing_proxy_task_count"]) == (22, 3)
    assert frames["SEMI_POWER_ESTIMAND_SENSITIVITY.csv"]["estimand"].nunique() == 2
    assert frames["QUALITY_RISK_TASK_BUILDING_CLUSTER_AUDIT.csv"]["population"].tolist() == [
        "all_computable", "formal_only", "administrative_eligible", "administrative_ineligible",
    ]
    assert len(frames["DIFFICULTY_PROXY_ASSOCIATIONS_BUILDING_CLUSTERED.csv"]) == 16


def test_task_and_building_equal_estimands_do_not_collapse():
    semi = pd.DataFrame([
        {"base_task_id": "a1", "building_id": "a", "manual_subset_count": 1, "manual_nonunique_or_not_evaluable_count": 0, "semi_subset_count": 1, "semi_nonunique_or_not_evaluable_count": 1, "delta_shannon_entropy": 1.0},
        {"base_task_id": "a2", "building_id": "a", "manual_subset_count": 1, "manual_nonunique_or_not_evaluable_count": 0, "semi_subset_count": 1, "semi_nonunique_or_not_evaluable_count": 1, "delta_shannon_entropy": 1.0},
        {"base_task_id": "a3", "building_id": "a", "manual_subset_count": 1, "manual_nonunique_or_not_evaluable_count": 0, "semi_subset_count": 1, "semi_nonunique_or_not_evaluable_count": 1, "delta_shannon_entropy": 1.0},
        {"base_task_id": "b1", "building_id": "b", "manual_subset_count": 1, "manual_nonunique_or_not_evaluable_count": 0, "semi_subset_count": 1, "semi_nonunique_or_not_evaluable_count": 0, "delta_shannon_entropy": -1.0},
    ])
    partition = partition_failure_rate_sensitivity(semi, bootstrap_replicates=10).set_index("estimand")
    assert partition.loc["task_equal", "estimate"] == 0.75
    assert partition.loc["building_equal", "estimate"] == 0.5
    power = semi_power_estimand_sensitivity(semi)
    effects = power.groupby("estimand")["observed_effect"].first()
    assert effects["task_equal"] == 0.5
    assert effects["building_equal"] == 0.0
    assert set(power["independent_unit"]) == {"building"}


def test_bh_is_na_safe():
    result = bh_adjust([0.01, None, 0.20, float("nan")])
    assert result[1] != result[1]
    assert result[3] != result[3]
    assert result[0] <= result[2]


def test_missing_schema_fails_closed(tmp_path):
    path = tmp_path / "IMAGE_FEATURE_VS_SEMI_ASSOCIATIONS.csv"
    pd.DataFrame({"predictor": ["x"], "outcome": ["y"]}).to_csv(path, index=False)
    with pytest.raises(SchemaError):
        build_frames(tmp_path, bootstrap_replicates=1)
