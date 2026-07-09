import json
import copy

import pytest

from tools.paper_a_manhattan.run_m_anchor_1_3741 import _load_anchor_sidecar
from tools.paper_a_manhattan.run_m_anchor_3_footprint_solver import (
    M2_VERDICT_PATH,
    _assert_delta_in_range,
    _check_m2,
    _load,
    _move_range,
    run,
)


def test_m_anchor_3_bottom_y_only_review_candidates(tmp_path):
    paths = run(tmp_path)
    payload = json.loads(paths["audit"].read_text(encoding="utf-8"))
    cards = [
        json.loads(line)
        for line in paths["cards"].read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    ledger = json.loads(paths["ledger"].read_text(encoding="utf-8"))

    assert payload["schema_version"] == "m_anchor_3_footprint_solver_audit_v1"
    assert "bottom_y-only adjustment" in payload["goal"]
    assert payload["input_sources"]["m_anchor_1_audit"]["sha256"]
    assert payload["input_sources"]["expert_anchor_constraints_sidecar"]["sha256"]
    assert payload["input_sources"]["m_anchor_2_human_verdict"]["sha256"]
    assert payload["input_sources"]["baseline_ordered_pairs"]["sha256"]
    assert 0 < payload["candidate_count"] <= 5
    assert payload["variable_boundary"]["allowed_variables"] == ["bottom_y"]
    assert payload["variable_boundary"]["top_y_policy"] == "fixed_for_m_anchor_3"

    assert cards == payload["candidate_cards"]
    assert ledger["candidate_ids"] == [row["candidate_id"] for row in cards]
    for row in cards:
        assert row["changed_pairs"] == [6]
        assert row["changed_fields"] == ["bottom_y"]
        assert set(row["bottom_y_delta_by_pair"]) == {"6"}
        assert row["top_y_changed"] is False
        assert row["reorder_changed"] is False
        assert row["hard_anchor_violation"] is False
        assert row["annotation_writeback"] is False
        assert row["downstream_recommendation"] is False
        assert row["wall_residual_sum_after"] < row["wall_residual_sum_before"]
        assert row["wall_residual_max_after"] <= row["wall_residual_max_before"] + 0.25
        per_wall = row["per_wall_residual_diagnostic"]
        assert per_wall["summary"]["wall_count"] == 12
        assert per_wall["summary"]["residual_sum_before_deg"] == pytest.approx(
            row["wall_residual_sum_before"]
        )
        assert per_wall["summary"]["residual_sum_after_deg"] == pytest.approx(
            row["wall_residual_sum_after"]
        )
        assert per_wall["summary"]["residual_max_before_deg"] == pytest.approx(
            row["wall_residual_max_before"]
        )
        assert per_wall["summary"]["residual_max_after_deg"] == pytest.approx(
            row["wall_residual_max_after"]
        )
        assert any(wall["source_edge_ids"] == [6, 5] for wall in per_wall["walls"])
        for wall in per_wall["walls"]:
            assert set(wall) == {
                "source_edge_ids",
                "seam_edge",
                "length_before",
                "length_after",
                "manhattan_residual_before_deg",
                "manhattan_residual_after_deg",
                "residual_delta_deg",
            }
        assert row["short_wall_preservation"] is True
        local = row["local_topology_metrics"]
        assert [edge["source_edge_ids"] for edge in local["edges"]] == [
            [4, 6],
            [6, 5],
            [5, 8],
            [8, 7],
        ]
        assert local["local_min_edge_length"] == min(
            edge["edge_length_after"] for edge in local["edges"]
        )
        for edge in local["edges"]:
            assert edge["edge_length_before"] > 0
            assert edge["edge_length_after"] > 0
            assert edge["ratio"] > 0
        assert row["keep_distinct_margin_5_6"]["after"] > 0.15
        assert row["seam_edge_status"]["preserved"] is True
        assert row["height_not_evaluated_or_fixed"] is True
        assert row["decision"] in {
            "review_available",
            "neutral_review",
            "rejected_hard_anchor_violation",
            "rejected_topology_risk",
            "rejected_visual_drift",
        }
        assert row["decision"] not in {
            "accepted",
            "recommended_final",
            "downstream_recommendation",
        }

    for field in (
        "accepted",
        "downstream_recommendation",
        "candidate_preference_authorized",
        "annotation_writeback",
        "annotation_patch_generated",
        "active_runner_role",
    ):
        assert payload[field] is False
        assert ledger[field] is False


@pytest.mark.parametrize(
    ("path", "value"),
    [
        (("next_stage_authorization", "m_anchor_3_footprint_solver_allowed"), False),
        (("next_stage_authorization", "allowed_variables"), ["top_y"]),
        (("next_stage_authorization", "top_y_policy"), "free"),
        (("next_stage_authorization", "writeback_allowed"), True),
        (("next_stage_authorization", "ranking_entry_allowed"), True),
        (("next_stage_authorization", "solver_scope"), "joint_xy"),
    ],
)
def test_m_anchor_3_rejects_bad_m2_gate(path, value):
    verdict = copy.deepcopy(_load(M2_VERDICT_PATH))
    target = verdict
    for key in path[:-1]:
        target = target[key]
    target[path[-1]] = value

    with pytest.raises(ValueError, match=path[-1]):
        _check_m2(verdict)


def test_m_anchor_3_rejects_missing_or_duplicate_move_range():
    sidecar = copy.deepcopy(_load_anchor_sidecar())
    sidecar["move_ranges"] = []
    with pytest.raises(ValueError, match="exactly one"):
        _move_range(sidecar)

    sidecar = copy.deepcopy(_load_anchor_sidecar())
    sidecar["move_ranges"].append(copy.deepcopy(sidecar["move_ranges"][0]))
    with pytest.raises(ValueError, match="exactly one"):
        _move_range(sidecar)


def test_m_anchor_3_rejects_delta_out_of_range():
    move_range = _move_range(_load_anchor_sidecar())
    with pytest.raises(ValueError, match="out of range"):
        _assert_delta_in_range(float(move_range["max_delta"]) + 0.25, move_range)
