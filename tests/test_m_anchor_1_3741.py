import hashlib
import json
import copy
from pathlib import Path

import pytest

from tools.paper_a_manhattan.run_m_anchor_1_3741 import (
    BASELINE_PATH,
    _anchor_constraints,
    _by_source,
    _candidate,
    _load,
    _load_anchor_sidecar,
    run,
)


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

    assert payload["schema_version"] == "m_anchor_1_1_audit_v1"
    assert payload["expert_anchor_constraints_schema"]["schema_version"] == (
        "expert_anchor_constraints_v1"
    )
    assert payload["expert_anchor_constraints_schema"]["source"] == "independent_sidecar"
    assert set(payload["expert_anchor_constraints_schema"]["anchor_strengths"]) == {
        "hard",
        "soft",
        "preferred",
    }
    assert payload["input_sources"]["expert_anchor_constraints_sidecar"]["sha256"]
    assert {
        row["anchor_strength"] for row in payload["expert_anchor_constraints"]
    } == {"hard", "soft", "preferred"}
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
    assert cards["m_anchor_1_height_only_plane_preserving"]["decision"].startswith(
        "rejected_"
    )
    assert cards["m_anchor_1_false_drift_reference_robust_all_long_edges"][
        "decision"
    ].startswith("rejected_")
    assert cards["m_anchor_1_false_drift_reference_robust_all_long_edges"][
        "solver_scope"
    ] == "diagnostic_reference"

    metrics = payload["acceptance_metrics"]
    assert 0.0 <= metrics["anchor_satisfaction_rate"] <= 1.0
    assert 0.0 < metrics["candidate_available_rate"] < 1.0
    assert metrics["expert_accept_at_3"] is None
    assert metrics["expert_accept_at_3_status"] == "pending_human_review"
    assert "false_visual_drift_rate" not in metrics
    assert 0.0 <= metrics["rejected_false_drift_rate"] <= 1.0
    assert metrics["available_false_drift_rate"] == 0.0
    assert metrics["false_visual_drift_rejected_count"] >= 1

    assert ledger["schema_version"] == "m_anchor_1_1_feedback_ledger_row_v1"
    assert ledger["expert_selected_candidate"] is None
    assert ledger["candidate_verdicts"]["m_anchor_1_height_only_plane_preserving"].startswith(
        "rejected_"
    )
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


def test_hard_anchor_violation_fails_closed_without_geometry_improvement():
    baseline_rows = _load(BASELINE_PATH)["ordered_pairs"]
    rows = copy.deepcopy(baseline_rows)
    for row in rows:
        if int(row["source_pair_id"]) == 2:
            row["top"]["x"] += 2.0
            break

    candidate = _candidate(
        "hard_violation_no_geometry_improvement_negative",
        "footprint_only_constrained_solver_prototype",
        rows,
        _by_source(baseline_rows),
        _anchor_constraints(_load_anchor_sidecar()),
        baseline_wall_residual=-1.0,
    )

    assert candidate["geometry_improved_vs_baseline"] is False
    assert candidate["hard_anchor_violation"] is True
    assert candidate["candidate_available"] is False
    assert candidate["decision"] == "rejected_hard_anchor_violation"


@pytest.mark.parametrize(
    ("mutate", "message"),
    [
        (lambda payload: payload.update({"case_name": "wrong"}), "case_name"),
        (lambda payload: payload.update({"source_annotation_id": 9999}), "source_annotation_id"),
        (lambda payload: payload.update({"coordinate_space": "pixels"}), "coordinate_space"),
        (lambda payload: payload["constraints"][0].update({"constraint_type": "line_anchor"}), "constraint_type"),
        (lambda payload: payload["constraints"][0].update({"constraint_id": "bad"}), "constraint_id"),
        (lambda payload: payload["constraints"][0].update({"endpoint": "middle"}), "endpoint"),
        (lambda payload: payload["constraints"][0].update({"axis": "z"}), "axis"),
    ],
)
def test_anchor_sidecar_schema_hardening_rejects_bad_fields(tmp_path, mutate, message):
    sidecar = copy.deepcopy(_load_anchor_sidecar())
    mutate(sidecar)
    sidecar_path = tmp_path / "bad_anchor_sidecar.json"
    sidecar_path.write_text(json.dumps(sidecar), encoding="utf-8")

    if message in {"case_name", "source_annotation_id", "coordinate_space"}:
        with pytest.raises(ValueError, match=message):
            _load_anchor_sidecar(sidecar_path)
    else:
        with pytest.raises(ValueError, match=message):
            _anchor_constraints(sidecar)
