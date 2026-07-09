import copy
import json

import pytest

from tools.paper_a_manhattan.run_m_anchor_1_3741 import _load_anchor_sidecar
from tools.paper_a_manhattan.run_m_anchor_3b_local_chain_footprint_solver import (
    CHAIN_PAIR_IDS,
    MAX_RAW_CANDIDATES,
    TOP_K,
    _chain_move_ranges,
    _check_m2_for_m3b,
    _load,
    run,
)
from tools.paper_a_manhattan.run_m_anchor_3_footprint_solver import M2_VERDICT_PATH


def test_m_anchor_3b_materializes_local_chain_ranked_review_candidates(tmp_path):
    paths = run(tmp_path)
    payload = json.loads(paths["audit"].read_text(encoding="utf-8"))
    cards = [
        json.loads(line)
        for line in paths["cards"].read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    ledger = json.loads(paths["ledger"].read_text(encoding="utf-8"))

    assert payload["schema_version"] == "m_anchor_3b_local_chain_footprint_solver_audit_v1"
    assert payload["prior_m_anchor_3_role"] == "s6_bottom_y_sensitivity_diagnostic"
    assert payload["chain_pair_ids"] == list(CHAIN_PAIR_IDS)
    assert 0 < payload["raw_candidates_evaluated"] <= MAX_RAW_CANDIDATES
    assert payload["candidate_count"] == TOP_K
    assert cards == payload["candidate_cards"]
    assert ledger["candidate_ids"] == [row["candidate_id"] for row in cards]
    assert any(row["moved_pairs"] != [6] for row in cards)
    assert all(row["top_y_changed"] is False for row in cards)
    assert all(row["reorder_changed"] is False for row in cards)
    assert all(row["annotation_writeback"] is False for row in cards)
    assert all(row["downstream_recommendation"] is False for row in cards)

    previous_key = None
    for row in cards:
        assert set(row["moved_pairs"]) <= set(CHAIN_PAIR_IDS)
        assert row["affected_edges"]
        assert row["improved_edges"]
        assert "worst_edge_before" in row
        assert "worst_edge_after" in row
        assert "movement_by_axis" in row
        assert "anchor_violations" in row
        assert "local_topology_before_after" in row
        assert "per_wall_residual_diagnostic" in row
        assert row["hard_gate_passed"] is True
        assert row["local_affected_residual_max_after"] <= row["local_affected_residual_max_before"]
        assert row["local_affected_residual_sum_after"] < row["local_affected_residual_sum_before"]
        assert row["wall_residual_sum_after"] < row["wall_residual_sum_before"]
        assert row["height_not_entered"] is True
        assert row["decision"] in {"review_available", "neutral_review"}
        assert row["decision"] not in {"accepted", "recommended_final", "downstream_recommendation"}
        key = (
            row["ranking_layers"]["L1_local_max_residual_after"],
            row["ranking_layers"]["L2_local_sum_residual_after"],
            row["ranking_layers"]["L3_global_sum_residual_after"],
            row["ranking_layers"]["L4_movement_cost"],
            row["ranking_layers"]["L5_topology_ratio_cost"],
        )
        if previous_key is not None:
            assert previous_key <= key
        previous_key = key

    for field in (
        "accepted",
        "accepted_as_final_fix",
        "downstream_recommendation",
        "candidate_preference_authorized",
        "annotation_writeback",
        "annotation_patch_generated",
        "active_runner_role",
    ):
        assert payload[field] is False
        assert ledger[field] is False


def test_m_anchor_3b_requires_chain_level_ranges():
    sidecar = copy.deepcopy(_load_anchor_sidecar())
    sidecar["move_ranges"] = [
        row for row in sidecar["move_ranges"] if int(row["source_pair_id"]) != 5
    ]
    with pytest.raises(ValueError, match="missing"):
        _chain_move_ranges(sidecar)


def test_m_anchor_3b_rejects_x_range_without_m2_x_authorization():
    verdict = _load(M2_VERDICT_PATH)
    with pytest.raises(ValueError, match="allowed_variables"):
        _check_m2_for_m3b(verdict, x_enabled=True)
