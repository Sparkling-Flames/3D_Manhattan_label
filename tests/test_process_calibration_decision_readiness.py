from __future__ import annotations

from pathlib import Path

import pandas as pd

from tools.thesis_main.analysis import process_calibration_decision_readiness as readiness


OUT = Path("analysis_results/calibration_decision_readiness_20260815_v2")


def test_required_addendum_outputs_exist() -> None:
    required = {"BLOCK1_ELIGIBILITY_RECONCILIATION.csv", "BLOCK1_CANONICAL_INVALID_SIX_ROWS.csv", "REFERENCE_CROSSWALK_UNRESOLVED.csv", "STRONG_GLOBAL_DIRECT_VALIDATION.csv", "STRONG_GLOBAL_PAIRED_BOOTSTRAP.csv", "CONDITIONAL_PAIRED_MODEL_DELTAS.csv", "FAMILY_COMPONENT_CHAIN_STATUS.csv", "FINAL_READINESS_MATRIX.csv", "COMPUTATION_REPORT.md", "source_manifest.json", "analysis_manifest.json"}
    assert required <= {path.name for path in OUT.iterdir()}


def test_block1_chain_is_stage_correct_and_six_rows_are_explicit() -> None:
    rows = pd.read_csv(OUT / "BLOCK1_ELIGIBILITY_RECONCILIATION.csv")
    six = pd.read_csv(OUT / "BLOCK1_CANONICAL_INVALID_SIX_ROWS.csv")
    assert len(rows) == 40 and rows.canonical_submission_id.is_unique and len(six) == 6
    assert rows.canonical_status.astype(str).str.lower().eq("true").sum() == 33
    assert rows.risk_eligibility.eq("eligible").sum() == 32
    assert rows.risk_eligibility.eq("not_evaluable").sum() == 2
    assert not rows.reported_chain.str.contains("38 geometry", regex=False).any()
    assert set(rows.reported_chain) == {"Block1: 40 canonical; 33 canonical-valid; 32 risk-eligible; 2 not-evaluable"}


def test_reference_inventory_has_the_requested_unresolved_rows() -> None:
    rows = pd.read_csv(OUT / "REFERENCE_CROSSWALK_UNRESOLVED.csv")
    counts = rows.case.value_counts().to_dict()
    assert counts["crosswalk_not_joined"] == 7 and counts["reference_unavailable"] == 2 and counts["C2B_157_to_155_researcher_confirmed_bad_gt"] == 2


def test_strong_global_uses_sg_not_worker_dummies_and_has_all_folds() -> None:
    rows = pd.read_csv(OUT / "STRONG_GLOBAL_DIRECT_VALIDATION.csv")
    assert set(rows.baseline_formula) == {"quality ~ risk"}
    assert set(rows.strong_global_formula) == {"quality ~ risk + S_G"}
    assert len(rows[rows.validation_kind.eq("temporal")]) == 2 and len(rows[rows.validation_kind.eq("leave_one_building_out")]) == 9 and len(rows[rows.validation_kind.eq("leave_one_base_task_out")]) == 67


def test_bootstrap_is_paired_and_at_least_1000() -> None:
    rows = pd.read_csv(OUT / "STRONG_GLOBAL_PAIRED_BOOTSTRAP.csv")
    assert (rows.requested_replicates >= 1000).all() and rows.paired_same_draw.astype(bool).all()
    assert rows.point_estimate.notna().all()


def test_conditional_deltas_are_matched_oof_rows() -> None:
    rows = pd.read_csv(OUT / "CONDITIONAL_PAIRED_MODEL_DELTAS.csv")
    bootstrap = pd.read_csv(OUT / "CONDITIONAL_PAIRED_BOOTSTRAP.csv")
    assert rows.same_test_rows.astype(bool).all() and {"P2_vs_P1", "worker_x_risk_diagnostic_vs_P1", "P3_d_model_feat_local_max_vs_P1", "P3_d_model_feat_local_max_residualized_sensitivity_vs_P1"} <= set(rows.comparison)
    assert (bootstrap.requested_replicates >= 1000).all() and bootstrap.paired_same_draw.astype(bool).all()
    assert bootstrap.point_estimate.notna().all()


def test_family_chain_is_fail_closed_and_not_negative_evidence() -> None:
    rows = pd.read_csv(OUT / "FAMILY_COMPONENT_CHAIN_STATUS.csv")
    inventory = pd.read_csv(OUT / "FAMILY_MISSING_INPUT_INVENTORY.csv")
    assert len(rows) == 60 and set(rows.family) == {"undercoverage", "adjacent_space_overextension", "corner_topology_instability"}
    assert (rows.all_gates_status == "not_ready_missing_inputs").all()
    assert set(rows.p1_family_integrity_status) == {"not_evaluable_missing_family_level_input"}
    assert set(rows.c1_predictive_status) == {"not_materialized"}
    assert set(rows.c2b_confirmation_status) == {"not_materialized"}
    assert rows.required_chain_status_json.str.contains('"P1_integrity_eligible"').all()
    assert inventory.source_statuses.notna().all()
    assert set(inventory[inventory.required_input.eq("P1 family integrity")].source_statuses) == {"not_evaluable_missing_family_level_input"}
    assert set(inventory[inventory.required_input.eq("frozen family threshold/activation")].source_statuses) == {"threshold_manifest_not_approved"}


def test_readiness_uses_latest_block2_state_without_promoting_it_to_terminal() -> None:
    rows = pd.read_csv(OUT / "FINAL_READINESS_MATRIX.csv").set_index("item")
    terminal = rows.loc["C2-A-RP terminal closeout"]
    risk = rows.loc["risk component"]
    assert terminal.status == "not_ready"
    assert terminal.evidence_path.endswith("c2a_rp_block2_reestimate_summary.json")
    assert "multiple_variance_components_unidentifiable" in terminal.reason
    assert "formal terminal state not materialized" in terminal.reason
    assert risk.evidence_path.endswith("c2a_rp_block2_reestimate_summary.json")
    assert "multiple_variance_components_unidentifiable" in risk.reason


def test_addendum_stays_pre_stage3() -> None:
    assert readiness.REPS >= 1000
    report = (OUT / "COMPUTATION_REPORT.md").read_text(encoding="utf-8")
    assert "scientific_conclusion_prohibited=true" in report and "Block 3" in report


def test_manifest_declares_corrected_schema() -> None:
    manifest = pd.read_json(OUT / "analysis_manifest.json", typ="series")
    assert manifest.schema_version == "calibration_decision_readiness_v2"
