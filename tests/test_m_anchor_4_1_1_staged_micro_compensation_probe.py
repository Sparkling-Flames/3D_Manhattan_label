import copy
import json
from pathlib import Path

import pytest

from tools.paper_a_manhattan.run_m_anchor_3_footprint_solver import M1_AUDIT_PATH, M2_VERDICT_PATH
from tools.paper_a_manhattan.run_m_anchor_4_1_1_staged_micro_compensation_probe import (
    FEEDBACK_PATH, _constraints, _geometry, _geometry_improved, _load,
    _validate_constraints, run,
)


def _baseline_rows():
    m1, m2 = _load(M1_AUDIT_PATH), _load(M2_VERDICT_PATH)
    return next(row for row in m1["solver_prototypes"] if row["candidate_id"] == m2["reviewed_candidate"])["corrected_coordinates"]


def test_staged_probe_is_bounded_deterministic_and_audit_only(tmp_path: Path) -> None:
    one = run(tmp_path / "one", tmp_path / "review_one", tmp_path / "one_constraints.json")
    two = run(tmp_path / "two", tmp_path / "review_two", tmp_path / "two_constraints.json")
    first = json.loads(one["audit"].read_text(encoding="utf-8"))
    second = json.loads(two["audit"].read_text(encoding="utf-8"))
    assert first["stages_executed"] == ["A", "B", "C"]
    assert first["raw_candidates_evaluated"] <= 1200
    assert first["candidate_count_by_stage"]["A"] > 0
    assert first["geometry_improved_count_by_stage"]["A"] == 0
    assert first["expansion_trigger_reason"]["B"] == "prior_stage_has_no_geometry_improved_candidate"
    assert [row["candidate_id"] for row in first["review_candidates"]] == [row["candidate_id"] for row in second["review_candidates"]]
    assert any(row["micro_actions"] for row in first["review_candidates"])
    for row in first["review_candidates"]:
        moves = {int(k): value for k, value in row["movement_by_axis"].items()}
        assert moves[4]["x"] < 0 and moves[9]["x"] < 0 and moves[10]["x"] > 0
        assert all(abs(delta) <= 0.5 for value in moves.values() for delta in value.values())
        assert len(row["micro_actions"]) <= 2
        assert row["top_y_changed"] is False and row["height_not_entered"] is True
        assert all(row["hard_gate"].values())
        assert row["annotation_writeback"] is False and row["active_runner_role"] is False
    assert first["m_anchor_4_2_height_completion_authorized"] is False


def test_stage_expansion_only_follows_absence_of_geometry_improvement() -> None:
    assert _geometry_improved([{"candidate_class": "review_available_geometry_improved"}])
    assert not _geometry_improved([{"candidate_class": "neutral_geometry_tradeoff"}])
    assert not _geometry_improved([{"candidate_class": "diagnostic_human_direction_only"}])


def test_constraints_fail_closed() -> None:
    feedback = _load(FEEDBACK_PATH)
    for mutate, text in (
        (lambda c: c["stage_candidate_deltas"]["A"].update(min_delta=0.2), "min_delta"),
        (lambda c: c["stage_candidate_deltas"]["A"]["candidate_deltas"].append(0.2), "stage cap"),
        (lambda c: c.update(micro_adjustment_pairs=[1, 2, 3, 4, 5, 7, 8]), "overlap"),
        (lambda c: c.update(locked_source_pair_ids=[4, 6, 11, 12]), "locked pair"),
    ):
        value = copy.deepcopy(_constraints()); mutate(value)
        with pytest.raises(ValueError, match=text):
            _validate_constraints(value, feedback)


def test_top_y_only_change_does_not_change_floor_heading_geometry() -> None:
    before = _baseline_rows(); after = copy.deepcopy(before)
    after[0]["top"]["y"] += 0.5
    after[1]["top"]["y"] -= 0.5
    left, right = _geometry(before), _geometry(after)
    for a, b in zip(left["floorprint"]["walls"], right["floorprint"]["walls"]):
        for key in ("direction_deg", "angle_residual_deg", "floor_wall_length"):
            assert a[key] == pytest.approx(b[key], abs=1e-12)
    for key in ("wall_residual_sum_deg", "wall_residual_max_deg", "self_intersection"):
        assert left["floorprint"]["summary"][key] == pytest.approx(right["floorprint"]["summary"][key], abs=1e-12)
    for key in ("corner_residual_sum_deg", "corner_residual_max_deg"):
        assert left["corner_turns"]["summary"][key] == pytest.approx(right["corner_turns"]["summary"][key], abs=1e-12)
    assert left["heights"] != right["heights"]
