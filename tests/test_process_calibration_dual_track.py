from __future__ import annotations

import pytest
import pandas as pd

from tools.thesis_main.analysis.process_calibration_dual_track import (
    analysis_stage,
    common_evidence,
    evidence_key,
    meta_rows_for_submission,
    model_row,
    ROLE_FIELDS,
    tier_cutpoints,
    validate_unique_evidence_keys,
)


def test_evidence_key_rejects_duplicate_canonical_submission() -> None:
    row = {
        "stage": "C2B",
        "worker_id": "1",
        "base_task_id": "task-1",
        "condition": "manual",
        "canonical_submission_id": "annotation-1",
    }
    assert evidence_key(row) == ("C2B", "1", "task-1", "manual", "annotation-1")
    with pytest.raises(ValueError, match="duplicate evidence key"):
        validate_unique_evidence_keys([row, dict(row)])


def test_meta_rows_mark_post_task_labels_not_routable() -> None:
    rows = meta_rows_for_submission(
        {"stage": "C2B", "worker_id": "1", "base_task_id": "task-1", "condition": "manual"},
        {"difficulty": ["occlusion"], "scope": ["normal"]},
    )
    occlusion = next(row for row in rows if row["tag_family"] == "difficulty" and row["tag_value"] == "occlusion")
    assert occlusion["selected"] is True
    assert occlusion["feature_timing"] == "post_task"
    assert occlusion["formal_first_route_eligible"] is False
    assert {key: occlusion[key] for key in ROLE_FIELDS} == ROLE_FIELDS


def test_tier_cutpoints_are_scalar_and_ordered() -> None:
    two_tier, lower_third, upper_third = tier_cutpoints([.1, .2, .3, .4, .5, .6])
    assert two_tier == pytest.approx(.35)
    assert lower_third < two_tier < upper_third


def test_c2_risk_quality_is_exposed_as_unified_reference_quality() -> None:
    row = common_evidence(
        "C2B", "C2-B", {"worker_id": "1", "condition": "manual"},
        base_task_id="task-1", canonical_id="c-1", annotation_id="a-1",
        risk={"risk": "4.2", "quality": "0.81", "risk_slope_estimand_eligible": "true"}, labels={},
    )
    assert row["iou_to_reference"] == pytest.approx(.81)


def test_analysis_stage_keeps_c2b_substage_identity() -> None:
    assert analysis_stage({"stage": "C2B", "substage_block": "C2-B"}) == "C2B_C2-B"


def test_model_row_fails_closed_without_residual_degrees_of_freedom() -> None:
    frame = pd.DataFrame([
        {"worker_id": "1", "base_task_id": "task-1", "building_id": "b-1", "risk": 1.0, "quality": 0.5},
        {"worker_id": "1", "base_task_id": "task-2", "building_id": "b-1", "risk": 2.0, "quality": 0.7},
    ])
    row, _ = model_row("two_point", "quality ~ risk", frame)
    assert row["status"] == "not_evaluable_insufficient_residual_df"


def test_model_row_allows_a_baseline_without_risk_term() -> None:
    frame = pd.DataFrame([
        {"worker_id": "1", "base_task_id": "task-1", "building_id": "b-1", "risk": 1.0, "quality": 0.5},
        {"worker_id": "1", "base_task_id": "task-2", "building_id": "b-1", "risk": 2.0, "quality": 0.7},
        {"worker_id": "1", "base_task_id": "task-3", "building_id": "b-1", "risk": 3.0, "quality": 0.8},
    ])
    row, _ = model_row("baseline", "quality ~ C(worker_id)", frame)
    assert row["status"] == "estimated"
    assert row["coefficient"] == ""
