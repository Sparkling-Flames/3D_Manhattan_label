from __future__ import annotations

import csv
from pathlib import Path

import numpy as np
import pandas as pd

from tools.thesis_main.analysis import process_calibration_dual_track as base
from tools.thesis_main.analysis.process_calibration_dual_track_v2 import (
    CHANNELS,
    exact_duplicate_feature,
    fit_spec,
    mixed_is_boundary,
    reference_sensitivity,
    specs,
    vector_channels,
)


def _frame() -> pd.DataFrame:
    rows = []
    for worker in ("1", "2", "3"):
        for index in range(6):
            risk = 1.0 + index
            rows.append({"worker_id": worker, "base_task_id": f"t{index}", "building_id": f"b{index % 2}", "stage": "C2B_C2-B" if index < 3 else "C2A_RP_Block1", "task_stratum": "ordinary" if index < 4 else "stress", "risk": risk, "quality": .5 + .02 * index + .01 * int(worker), "d_model_feat": .1 * index, "d_model_feat_local_max": .2 * index, "g_model_struct": .3 * index, "d_cal_A": .4 * index})
    return pd.DataFrame(rows)


def test_exact_duplicate_risk_feature_is_rejected() -> None:
    frame = _frame(); frame["risk_design_score_A"] = frame.risk
    assert exact_duplicate_feature(frame, "risk_design_score_A") is True


def test_risk_vector_four_channel_contract_order() -> None:
    assert list(vector_channels("[1,2,3,4]")) == list(CHANNELS)


def test_current_eligible_evidence_has_225_complete_vectors() -> None:
    inputs = base.load_inputs(); risk = base.csv_rows(inputs["risk"])  # type: ignore[arg-type]
    pool = {row["base_task_id"]: row for row in base.csv_rows(inputs["feature_pool"])}  # type: ignore[arg-type]
    eligible = [row for row in risk if base.truth(row.get("risk_slope_estimand_eligible"))]
    assert len(eligible) == 225
    assert all(row["base_task_id"] in pool and pool[row["base_task_id"]]["risk_design_vector_A"] for row in eligible)


def test_rank_deficient_m3_is_not_estimated() -> None:
    frame = _frame(); frame["d_model_feat"] = frame.risk
    summary, _, _ = fit_spec({"model_name": "M3_bad", "formula": "quality ~ C(worker_id) + risk + d_model_feat", "kind": "ols", "channel": "d_model_feat"}, frame)
    assert summary["status"] == "not_evaluable_rank_deficient"


def test_m2_spec_uses_random_worker_risk_slope() -> None:
    m2 = next(row for row in specs(_frame()) if row["model_name"] == "M2")
    assert m2["kind"] == "mixed" and "risk" in m2["formula"]


def test_near_singular_m2_covariance_is_not_ordinary_estimated() -> None:
    assert mixed_is_boundary(np.asarray([[.004, -.0012], [-.0012, .00036]]))


def test_m3_specs_have_worker_channel_interactions() -> None:
    rows = {row["model_name"]: row for row in specs(_frame())}
    assert all(f"M3_{channel}" in rows and f"C(worker_id):{channel}" in rows[f"M3_{channel}"]["formula"] for channel in CHANNELS)


def test_validation_spec_set_includes_m2_and_all_m3() -> None:
    names = {row["model_name"] for row in specs(_frame())}
    assert {"M0", "M1", "M2", *(f"M3_{channel}" for channel in CHANNELS)} <= names


def test_building_bootstrap_targets_m1_and_each_m3() -> None:
    source = Path("tools/thesis_main/analysis/process_calibration_dual_track_v2.py").read_text(encoding="utf-8")
    assert "conditional_building_bootstrap_sensitivity.csv" in source and 'item["model_name"].startswith("M3_")' in source


def test_tier_validation_contract_is_preblock2() -> None:
    source = Path("tools/thesis_main/analysis/process_calibration_dual_track_v2.py").read_text(encoding="utf-8")
    assert "pre_Block2_frozen_Q_GT_EB" in source and "C2A_RP_Block2" in source


def test_reference_sensitivity_is_a_denominator_audit(tmp_path: Path) -> None:
    inputs = base.load_inputs(); reference_sensitivity(inputs, tmp_path)
    with (tmp_path / "reference_sensitivity_denominators.csv").open(encoding="utf-8", newline="") as stream:
        row = next(csv.DictReader(stream))
    assert row["sensitivity_status"] == "not_evaluable_already_excluded_by_formal_eligibility"


def test_posttask_labels_remain_outside_first_route() -> None:
    row = base.meta_rows_for_submission({"stage": "C2B", "worker_id": "1", "base_task_id": "t", "condition": "manual"}, {"difficulty": ["occlusion"]})[0]
    assert row["feature_timing"] == "post_task" and row["formal_first_route_eligible"] is False
