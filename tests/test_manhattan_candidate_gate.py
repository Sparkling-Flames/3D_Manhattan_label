"""Tests for M14.3 Paper A Manhattan candidate gating.

The gate is expert-side only. These tests do not modify Label Studio UI,
annotations, export_label, routing, formal g_t, worker quality metrics, or
P1/C1/C2/T1/V1 artifacts.
"""

from __future__ import annotations

import json

from tools.paper_a_manhattan.manhattan_candidate_gate import (
    CANDIDATE_ALLOWED,
    EXPERT_REVIEW_ONLY,
    SUPPRESS,
    compute_max_abs_delta,
    gate_manhattan_candidate,
)


def _clean_record(**overrides):
    record = {
        "fit_status": "ok",
        "fit_residual": 0.001,
        "fit_confidence": "high",
        "direction_label": "no_action",
        "warnings": [],
        "fitted_points": [
            {"pair_index": 1, "top": {"x": 20.0, "y": 40.0}, "bottom": {"x": 20.0, "y": 60.0}}
        ],
        "per_point_delta": [
            {"pair_index": 1, "top_dx": 0.1, "top_dy": -0.2, "bottom_dx": 0.1, "bottom_dy": 0.2}
        ],
        "layout_height_spread": 0.02,
        "layout_height_candidate": 3.0,
        "yaw_fit_residual": 0.001,
        "fit_version": "manhattan_constrained_fit_m14_2_v1",
    }
    record.update(overrides)
    return record


def test_fit_failed_suppresses_candidate():
    result = gate_manhattan_candidate(_clean_record(fit_status="failed"))

    assert result["gate_status"] == SUPPRESS
    assert "fit_status_not_ok:failed" in result["blocking_reasons"]
    assert json.dumps(result)


def test_preview_incompatible_suppresses_candidate():
    result = gate_manhattan_candidate(_clean_record(), {"preview_status": "compatibility_failure_odd_keypoint"})

    assert result["gate_status"] == SUPPRESS
    assert "preview_failure" in result["blocking_reasons"]
    assert "preview_odd_keypoint" in result["blocking_reasons"]


def test_oos_split_level_non_manhattan_metadata_suppresses_candidate():
    result = gate_manhattan_candidate(
        _clean_record(),
        {"metadata": {"scope": "oos_split_level", "layout_type": "non_manhattan"}},
    )

    assert result["gate_status"] == SUPPRESS
    assert "metadata_oos_split_level" in result["blocking_reasons"]
    assert "metadata_non_manhattan" in result["blocking_reasons"]


def test_oos_insufficient_metadata_scope_suppresses_candidate():
    result = gate_manhattan_candidate(_clean_record(), {"metadata": {"scope": "oos_insufficient"}})

    assert result["gate_status"] == SUPPRESS
    assert "metadata_oos_insufficient" in result["blocking_reasons"]


def test_oos_insufficient_top_level_scope_suppresses_candidate():
    result = gate_manhattan_candidate(_clean_record(scope="oos_insufficient"))

    assert result["gate_status"] == SUPPRESS
    assert "metadata_oos_insufficient" in result["blocking_reasons"]


def test_not_manhattan_assumable_metadata_suppresses_candidate():
    result = gate_manhattan_candidate(_clean_record(), {"metadata": {"manhattan_assumable": False}})

    assert result["gate_status"] == SUPPRESS
    assert "metadata_not_manhattan_assumable" in result["blocking_reasons"]


def test_string_false_manhattan_assumable_metadata_suppresses_candidate():
    result = gate_manhattan_candidate(_clean_record(), {"metadata": {"manhattan_assumable": "no"}})

    assert result["gate_status"] == SUPPRESS
    assert "metadata_not_manhattan_assumable" in result["blocking_reasons"]


def test_self_crossing_warning_suppresses_candidate():
    result = gate_manhattan_candidate(_clean_record(warnings=["self_crossing_candidate"]))

    assert result["gate_status"] == SUPPRESS
    assert "warning_self_crossing_candidate" in result["blocking_reasons"]


def test_large_max_abs_delta_is_not_candidate_allowed():
    result = gate_manhattan_candidate(_clean_record(max_abs_delta=9.2))

    assert result["gate_status"] == EXPERT_REVIEW_ONLY
    assert "max_abs_delta_large" in result["gate_reasons"]


def test_severe_max_abs_delta_suppresses_candidate():
    result = gate_manhattan_candidate(_clean_record(max_abs_delta=12.5))

    assert result["gate_status"] == SUPPRESS
    assert "max_abs_delta_exceeds_fit_fail_threshold" in result["blocking_reasons"]


def test_max_abs_delta_can_be_computed_from_per_point_delta():
    record = _clean_record(
        per_point_delta=[
            {"pair_index": 1, "top_dx": 0.1, "top_dy": -6.0, "bottom_dx": 0.2, "bottom_dy": 1.0}
        ]
    )

    assert compute_max_abs_delta(record["per_point_delta"]) == 6.0
    assert gate_manhattan_candidate(record)["gate_status"] == EXPERT_REVIEW_ONLY


def test_missing_per_point_delta_on_clean_ok_record_goes_to_expert_review_only():
    result = gate_manhattan_candidate(_clean_record(per_point_delta=[]))

    assert result["gate_status"] == EXPERT_REVIEW_ONLY
    assert "max_abs_delta_unavailable" in result["gate_reasons"]


def test_unparseable_per_point_delta_on_clean_ok_record_goes_to_expert_review_only():
    result = gate_manhattan_candidate(_clean_record(per_point_delta=[{"pair_index": 1, "top_dx": "bad"}]))

    assert result["gate_status"] == EXPERT_REVIEW_ONLY
    assert "max_abs_delta_unavailable" in result["gate_reasons"]


def test_layout_height_spread_high_goes_to_expert_review_only():
    result = gate_manhattan_candidate(_clean_record(layout_height_spread=0.75))

    assert result["gate_status"] == EXPERT_REVIEW_ONLY
    assert "layout_height_spread_high" in result["gate_reasons"]


def test_warning_only_layout_height_spread_high_goes_to_expert_review_only():
    result = gate_manhattan_candidate(_clean_record(warnings=["layout_height_spread_high"], layout_height_spread=None))

    assert result["gate_status"] == EXPERT_REVIEW_ONLY
    assert "warning_layout_height_spread_high" in result["gate_reasons"]


def test_layout_height_spread_fail_suppresses_candidate():
    result = gate_manhattan_candidate(_clean_record(layout_height_spread=1.3))

    assert result["gate_status"] == SUPPRESS
    assert "layout_height_spread_exceeds_fail_threshold" in result["blocking_reasons"]


def test_low_confidence_goes_to_expert_review_only():
    result = gate_manhattan_candidate(_clean_record(fit_confidence="low"))

    assert result["gate_status"] == EXPERT_REVIEW_ONLY
    assert "fit_confidence_low" in result["gate_reasons"]


def test_clean_high_confidence_candidate_is_allowed():
    result = gate_manhattan_candidate(_clean_record())

    assert result["gate_status"] == CANDIDATE_ALLOWED
    assert result["gate_reasons"] == ["clean_candidate"]
    assert result["blocking_reasons"] == []


def test_known_task_2949_style_algorithm_overfit_large_delta_is_not_allowed():
    result = gate_manhattan_candidate(
        _clean_record(
            fit_confidence="low",
            fit_residual=0.09410975256952664,
            layout_height_spread=0.9538006365859815,
            max_abs_delta=11.367745006426773,
            warnings=["layout_height_spread_high"],
        ),
        {
            "task_id": "2949",
            "annotation_id": "2652",
            "known_review_label": "algorithm_overfit",
            "preview_status": "compatible",
        },
    )

    assert result["gate_status"] == EXPERT_REVIEW_ONLY
    assert result["gate_status"] != CANDIDATE_ALLOWED
    assert "max_abs_delta_large" in result["gate_reasons"]
    assert "fit_confidence_low" in result["gate_reasons"]
