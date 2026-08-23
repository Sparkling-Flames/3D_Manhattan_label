import math

import pandas as pd
import pytest

from tools.thesis_main.analysis.full_uncertainty.full_uncertainty_stats_v5 import (
    crossed_task_worker_variance_decomposition,
    filter_structural_zero_lane,
    mean_pairwise_jaccard_disagreement,
    modal_response_share,
    response_pattern_entropy,
)


def test_response_metrics_and_caller_owned_denominators() -> None:
    canonical = ["A", "A", "B", "B"]
    raw = ["A", "A", "A", "B", "B"]
    assert response_pattern_entropy(canonical) == pytest.approx(math.log(2))
    assert response_pattern_entropy(raw) == pytest.approx(-(3 / 5) * math.log(3 / 5) - (2 / 5) * math.log(2 / 5))
    assert modal_response_share(canonical) == 0.5
    assert modal_response_share(raw) == 0.6


def test_jaccard_disagreement_hand_calculation_and_empty_pair() -> None:
    value = mean_pairwise_jaccard_disagreement([{1, 2}, {1}, {2, 3}])
    assert value == pytest.approx(13 / 18)
    assert mean_pairwise_jaccard_disagreement([set(), set()]) == 0.0
    assert mean_pairwise_jaccard_disagreement([set()]) is None


def test_structural_zero_lanes_do_not_treat_missing_as_zero() -> None:
    frame = pd.DataFrame(
        [
            {"id": "zero", "geometry_edit_rmse_px": 0, "delta_U": 0, "formal_assignment_eligible": True},
            {"id": "missing_rmse", "geometry_edit_rmse_px": None, "delta_U": 0, "formal_assignment_eligible": True},
            {"id": "missing_delta", "geometry_edit_rmse_px": 0, "delta_U": None, "formal_assignment_eligible": True},
            {"id": "edited_formal", "geometry_edit_rmse_px": 2, "delta_U": 0.1, "formal_assignment_eligible": True},
            {"id": "edited_nonformal", "geometry_edit_rmse_px": 1, "delta_U": -0.1, "formal_assignment_eligible": False},
        ]
    )
    assert list(filter_structural_zero_lane(frame, "all-computable")["id"]) == ["zero", "edited_formal", "edited_nonformal"]
    assert list(filter_structural_zero_lane(frame, "exclude_joint_near_zero")["id"]) == ["edited_formal", "edited_nonformal"]
    assert list(filter_structural_zero_lane(frame, "edited-positive")["id"]) == ["edited_formal", "edited_nonformal"]
    assert list(filter_structural_zero_lane(frame, "formal-only")["id"]) == ["zero", "edited_formal"]


def test_crossed_variance_decomposition_task_and_worker_dominant() -> None:
    rows = []
    for task_index in range(8):
        for worker_index in range(4):
            rows.append({"quality": 10 * task_index + worker_index * 0.1, "base_task_id": f"t{task_index}", "worker_id": f"w{worker_index}"})
    task_fit = crossed_task_worker_variance_decomposition(pd.DataFrame(rows))
    assert task_fit["status"] in {"estimated", "boundary_zero_component"}
    assert task_fit["task_variance"] > task_fit["worker_variance"]

    rows = []
    for task_index in range(8):
        for worker_index in range(4):
            rows.append({"quality": 10 * worker_index + task_index * 0.1, "base_task_id": f"t{task_index}", "worker_id": f"w{worker_index}"})
    worker_fit = crossed_task_worker_variance_decomposition(pd.DataFrame(rows))
    assert worker_fit["status"] in {"estimated", "boundary_zero_component"}
    assert worker_fit["worker_variance"] > worker_fit["task_variance"]


def test_crossed_variance_decomposition_boundary_and_fail_closed() -> None:
    rows = [{"quality": 10 * task, "base_task_id": f"t{task}", "worker_id": f"w{worker}"} for task in range(8) for worker in range(4)]
    boundary = crossed_task_worker_variance_decomposition(pd.DataFrame(rows))
    assert boundary["status"] == "boundary_zero_component"
    assert boundary["converged"] is True
    assert "boundary_components:" in "".join(boundary["warnings"])

    not_evaluable = crossed_task_worker_variance_decomposition(pd.DataFrame([rows[0], rows[5]]))
    assert not_evaluable["status"] == "not_evaluable_unidentifiable_support"
    assert not_evaluable["task_variance"] is None
