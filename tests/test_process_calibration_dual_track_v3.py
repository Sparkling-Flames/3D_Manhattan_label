from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from tools.thesis_main.analysis import process_calibration_dual_track as base
from tools.thesis_main.analysis import process_calibration_dual_track_v3 as v3


OUTPUT = Path("analysis_results/calibration_dual_track_processing_20260815_v3")


def _train_test() -> tuple[pd.DataFrame, pd.DataFrame]:
    rows = []
    for worker in ("1", "2"):
        for risk in range(1, 7):
            rows.append({"canonical_submission_id": f"{worker}-{risk}", "worker_id": worker, "base_task_id": f"t{risk}", "building_id": "old", "stage": "C2B_C2-B", "task_stratum": "ordinary", "risk": float(risk), "d_model_feat": risk * .2 + (risk % 2) * .1, "quality": .5 + .03 * risk + .01 * int(worker)})
    train = pd.DataFrame(rows)
    test = train.iloc[:2].copy(); test["building_id"] = "new-building"; test["stage"] = "new-stage"
    return train, test


def test_prediction_specs_do_not_encode_test_stage_or_building() -> None:
    assert all("C(stage)" not in row["formula"] and "C(building_id)" not in row["formula"] for row in v3.prediction_specs())


def test_new_stage_and_building_are_predictable_without_category_leakage() -> None:
    train, test = _train_test()
    summary, predictions = v3._fit_predict(next(row for row in v3.prediction_specs() if row["model_name"] == "P1"), train, test)
    assert summary["status"] == "estimated" and len(predictions) == len(test)
    assert summary["new_building_categories"] == 1 and summary["new_stage_categories"] == 1


def test_m2_blup_adds_intercept_and_risk_slope() -> None:
    class Fit:
        random_effects = {"w": np.asarray([.1, .2])}

        @staticmethod
        def predict(frame: pd.DataFrame) -> np.ndarray:
            return np.zeros(len(frame))

    values, source, fallback = v3._mixed_prediction(Fit(), pd.DataFrame({"worker_id": ["w", "w"], "risk_z": [-1.0, 1.0]}))
    assert not np.allclose(values, 0) and values[0] != values[1]
    assert source == ["fixed_plus_worker_random_intercept_and_risk_slope_blup"] * 2 and fallback == [False, False]


def test_train_only_scaling_and_residualization_do_not_use_test_values() -> None:
    train, test = _train_test(); test["risk"] = [100.0, 101.0]
    transformed, applied, details = v3.train_transform(train, test, "d_model_feat")
    assert details["fields"]["risk"]["mean"] == train.risk.mean()
    assert applied.risk_z.abs().min() > 10 and np.isclose(transformed.risk_z.mean(), 0)
    assert details["channel_residualization"]["fit_source"] == "train_fold_only"


def test_current_temporal_and_building_core_folds_no_longer_fail() -> None:
    rows = pd.read_csv(OUTPUT / "conditional_validation_all_models.csv")
    core = rows[rows.model_name.isin(v3.CORE_SPECS)]
    assert ((core.validation_kind == "temporal").sum(), (core.validation_kind == "leave_one_building_out").sum()) == (18, 81)
    assert not (core.status == "failed").any()


def test_m2_boundary_state_remains_explicit_in_association_output() -> None:
    row = pd.read_csv(OUTPUT / "m2_variance_components.csv").iloc[0]
    assert row.status == "boundary_singular" and bool(row.boundary) and bool(row.singular)


def test_qgt_validation_has_baseline_and_all_predeclared_tiers() -> None:
    qgt = pd.read_csv(OUTPUT / "qgt_block2_temporal_validation.csv")
    tiers = pd.read_csv(OUTPUT / "tier_block2_temporal_validation.csv")
    assert {"baseline_risk_deployable_composition", "continuous_Q_GT_EB"} <= set(qgt.model_name)
    assert {"top_3_indicator", "top_5_indicator", "top_10_indicator"} == set(tiers.model_name)


def test_bootstrap_repetitions_are_at_least_1000() -> None:
    bootstrap = pd.read_csv(OUTPUT / "conditional_cluster_bootstrap_sensitivity.csv")
    assert v3.BOOTSTRAP_REPLICATES >= 1000 and (bootstrap.requested_replicates >= 1000).all()


def test_posttask_labels_still_do_not_enter_first_route() -> None:
    row = base.meta_rows_for_submission({"stage": "C2B", "worker_id": "1", "base_task_id": "t", "condition": "manual"}, {"difficulty": ["occlusion"]})[0]
    assert row["feature_timing"] == "post_task" and row["formal_first_route_eligible"] is False
