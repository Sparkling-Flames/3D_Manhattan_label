import hashlib
import json
from pathlib import Path

from tools.paper_a_manhattan.run_m_anchor_1_3741 import run


PROTECTED = (
    Path("export_label/groudTruth.json"),
    Path("tools/paper_a_manhattan/run_manhattan_hypothesis_ranking_core.py"),
    Path("tools/paper_a_manhattan/manhattan_constrained_hypothesis_evaluator.py"),
    Path("tools/paper_a_manhattan/manhattan_hypothesis_portfolio.py"),
)


def _sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_m_anchor_1_materializes_fail_closed_anchor_contract(tmp_path):
    before = {path: _sha(path) for path in PROTECTED}
    paths = run(tmp_path)
    payload = json.loads(paths["json"].read_text(encoding="utf-8"))
    ledger = json.loads(paths["ledger"].read_text(encoding="utf-8"))

    assert payload["schema_version"] == "m_anchor_1_audit_v1"
    assert payload["expert_anchor_constraints_schema"]["schema_version"] == (
        "expert_anchor_constraints_v1"
    )
    assert {row["source_pair_id"]: row["solver_position"] for row in payload["pair_sid_order_seam_mapping_table"]}[2] == 1
    assert {row["source_pair_id"]: row["solver_position"] for row in payload["pair_sid_order_seam_mapping_table"]}[11] == 12
    assert any(row["seam_before_pair"] for row in payload["pair_sid_order_seam_mapping_table"])
    assert any(row["seam_after_pair"] for row in payload["pair_sid_order_seam_mapping_table"])
    assert payload["baseline_per_wall_residual_diagnostic"]["summary"]["wall_count"] == 12

    cards = {row["candidate_id"]: row for row in payload["candidate_explanation_cards"]}
    assert {
        "m_anchor_1_footprint_only_joint_xy",
        "m_anchor_1_height_only_plane_preserving",
        "m_anchor_1_false_drift_reference_robust_all_long_edges",
    } <= set(cards)
    assert cards["m_anchor_1_footprint_only_joint_xy"]["decision"] == "review_available"
    assert cards["m_anchor_1_height_only_plane_preserving"]["decision"] == (
        "rejected_false_visual_drift"
    )
    assert cards["m_anchor_1_false_drift_reference_robust_all_long_edges"][
        "decision"
    ] == "rejected_false_visual_drift"
    assert cards["m_anchor_1_false_drift_reference_robust_all_long_edges"][
        "solver_scope"
    ] == "diagnostic_reference"

    metrics = payload["acceptance_metrics"]
    assert 0.0 <= metrics["anchor_satisfaction_rate"] <= 1.0
    assert 0.0 < metrics["candidate_available_rate"] < 1.0
    assert metrics["expert_accept_at_3"] is None
    assert metrics["expert_accept_at_3_status"] == "pending_human_review"
    assert metrics["false_visual_drift_rate"] == 0.0
    assert metrics["false_visual_drift_rejected_count"] >= 1

    assert ledger["schema_version"] == "m_anchor_1_feedback_ledger_row_v1"
    assert ledger["expert_selected_candidate"] is None
    assert ledger["candidate_verdicts"][
        "m_anchor_1_height_only_plane_preserving"
    ] == "rejected_false_visual_drift"
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
    assert {path: _sha(path) for path in PROTECTED} == before
