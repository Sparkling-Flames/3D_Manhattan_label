import json

from tools.paper_a_manhattan.run_m_anchor_3_footprint_solver import run


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
        assert row["short_wall_preservation"] is True
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
