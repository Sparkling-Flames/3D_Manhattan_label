import argparse
import json
import subprocess
from pathlib import Path

import pytest

from tools.thesis_main.analysis.run_c1_closeout_launch import _c2_source_images, _final_risk_pool_gate, _future_heldout_images, _materialize_static_evidence_review_queues, _source_identity_aggregate, build_c2b, finalize_c1, freeze_c1, main, preflight_calibration, rehearse_c1
from tools.thesis_main.analysis.run_c1_precloseout_rehearsal import _aggregate_sha, _c1_closeout_blockers


def test_rehearsal_can_read_live_logs_but_cannot_be_formal(monkeypatch, tmp_path):
    captured = {}
    monkeypatch.setattr(
        "tools.thesis_main.analysis.run_c1_closeout_launch.materialize_c1",
        lambda *args, **kwargs: captured.update(kwargs) or {"output_dir": str(tmp_path)},
    )
    args = argparse.Namespace(
        export_dir=[], active_log=tmp_path / "new_server", manual_assignment=tmp_path / "m.csv",
        semi_assignment=tmp_path / "s.csv", worker_distribution=tmp_path / "w.csv",
        gt_export=tmp_path / "gt.json", p1_closeout_dir=tmp_path / "p1",
        output_root=tmp_path, c1_preannotation_feature_csv=None,
    )
    result = rehearse_c1(args)
    assert captured["input_status"] == "precloseout_rehearsal"
    assert result["formal_closeout_ready"] is False


def test_public_cli_exposes_the_eight_stage_commands(capsys):
    with pytest.raises(SystemExit):
        main(["--help"])
    help_text = capsys.readouterr().out
    for command in (
        "rehearse-c1", "prepare-c2b-static", "preflight-calibration", "freeze-c1",
        "audit-c1", "finalize-c1", "design-c2b", "build-c2b",
    ):
        assert command in help_text
    for removed in ("day1-canonical-audit", "day1-formal-audit", "day2-c2b-build", "freeze-c1-active-log"):
        assert removed not in help_text


def test_canonicalizer_is_the_single_owner_of_geometry_and_sidecar_materialization():
    runner = Path("tools/thesis_main/analysis/run_c1_precloseout_rehearsal.py").read_text(encoding="utf-8")
    canonicalizer = Path("tools/thesis_main/analysis/c1_canonicalize_exports.py").read_text(encoding="utf-8")
    assert "materialize_geometry_consensus(" not in runner
    assert "materialize_canonical_evidence(" not in runner
    assert canonicalizer.count("materialize_geometry_consensus(") == 1
    assert canonicalizer.count("materialize_canonical_evidence(") == 1


def test_formal_stage_outputs_are_ignored_so_the_next_clean_git_gate_can_run():
    for path in (
        "analysis_results/c1_formal_audit_sha/result.csv",
        "analysis_results/c1_reviews_sha/disposition.csv",
        "analysis_results/c2b_design_sha/result.csv",
        "analysis_results/c2b_build_sha/result.csv",
    ):
        assert subprocess.run(["git", "check-ignore", "-q", path]).returncode == 0


def test_fresh_checkout_keeps_both_numeric_threshold_contracts():
    for path in (
        "docs/thesis_main/C2B_DESIGN_SELECTION_THRESHOLDS.json",
        "docs/thesis_main/C2B_FEATURE_AUDIT_THRESHOLDS.json",
    ):
        assert subprocess.run(["git", "check-ignore", "-q", path]).returncode != 0


def test_final_risk_pool_freezes_only_after_building_and_both_strata_gates(tmp_path):
    threshold = tmp_path / "threshold.json"
    threshold.write_text(json.dumps({
        "status": "approved", "formal_selection_allowed": True,
        "thresholds": {
            "minimum_eligible_task_count": 2, "minimum_eligible_building_count": 2,
            "minimum_ordinary_task_count": 1, "minimum_stress_task_count": 1,
        },
    }), encoding="utf-8")
    ordinary_only = [
        {"assignment_eligible": "true", "building_id": "b1", "risk_design_stratum": "ordinary"},
        {"assignment_eligible": "true", "building_id": "b2", "risk_design_stratum": "ordinary"},
    ]
    assert _final_risk_pool_gate(ordinary_only, threshold)["frozen"] is False
    ordinary_only[1]["risk_design_stratum"] = "stress"
    gate = _final_risk_pool_gate(ordinary_only, threshold)
    assert gate["frozen"] is True
    assert gate["observed"] == {
        "minimum_eligible_task_count": 2, "minimum_eligible_building_count": 2,
        "minimum_ordinary_task_count": 1, "minimum_stress_task_count": 1,
    }


def test_preflight_rejects_null_thresholds_and_unapproved_feature_freeze(tmp_path):
    static = tmp_path / "static"; (static / "p1_integrity").mkdir(parents=True)
    (static / "paper_a_analysis_environment_manifest.json").write_text(json.dumps({
        "python": "3.11.7", "packages": {"torch": "2.11.0+cu128", "torchvision": "0.26.0+cu128"},
        "cuda_available": True, "cuda_build": "12.8", "physical_batch_size": 4,
        "nvidia_driver_version": "610.62", "dependency_lock_sha256": {"analysis": "a", "torch": "b"},
    }), encoding="utf-8")
    (static / "c2_feature_freeze_manifest.json").write_text(json.dumps({"feature_audit_status": "pending_threshold_approval_or_failed"}), encoding="utf-8")
    for path in (
        static / "p1_integrity" / "p1_post_closeout_correction_summary_v1.json",
        static / "p1_integrity" / "p1_geometry_score_summary_v1.json",
        static / "c2_legacy_reverse_candidate_audit.summary.json",
        static / "c2b_static_evidence_review_queues.summary.json",
    ):
        path.write_text("{}", encoding="utf-8")
    design = tmp_path / "design.json"; feature = tmp_path / "feature.json"
    design.write_text(json.dumps({"status": "pending", "formal_selection_allowed": False, "thresholds": {}}), encoding="utf-8")
    feature.write_text(json.dumps({"status": "pending", "formal_feature_freeze_allowed": False, "thresholds": {}}), encoding="utf-8")
    result = preflight_calibration(argparse.Namespace(
        static_dir=static, threshold_manifest=design, feature_audit_threshold_manifest=feature,
        output=tmp_path / "preflight.json",
    ))
    assert result["ready"] is False
    assert result["blockers"] == [
        "unapproved_or_incomplete:design_thresholds",
        "unapproved_or_incomplete:feature_thresholds",
        "feature_freeze_not_approved",
    ]


def test_static_evidence_queues_do_not_promote_inventory_hints(tmp_path):
    inventory = tmp_path / "inventory.csv"
    inventory.write_text(
        "task_id,base_task_id,image_id,source_path,source_pool,building_id,used_in_prescreen,scope_gold_ready\n"
        "t1,b1,scene_uuid,image.jpg,pool,guessed_building,true,true\n",
        encoding="utf-8",
    )
    legacy = tmp_path / "legacy.csv"
    legacy.write_text("image_id,base_task_id\nscene_uuid,b1\n", encoding="utf-8")

    result = _materialize_static_evidence_review_queues(inventory, legacy, tmp_path / "out")

    assert result["formal_evidence_ready"] is False
    queue = (tmp_path / "out" / "authoritative_building_registry.review_queue.csv").read_text(encoding="utf-8")
    assert "guessed_building" not in queue
    assert "pending_review" in queue


def test_freeze_c1_atomically_creates_active_log_and_collection_contracts(tmp_path):
    live, frozen, exports = tmp_path / "new_server", tmp_path / "c1", tmp_path / "exports"
    live.mkdir(); exports.mkdir()
    (live / "active_times_2026-07-25.jsonl").write_text(
        json.dumps({"server_received_at": "2026-07-25T01:00:00Z", "task_id": "1"}) + "\n",
        encoding="utf-8",
    )
    (exports / "c1.json").write_text("[]", encoding="utf-8")
    manual, semi = tmp_path / "manual.csv", tmp_path / "semi.csv"
    manual.write_text("worker_id,task_id\nW001,1\n", encoding="utf-8")
    semi.write_text("worker_id,task_id\nW001,2\n", encoding="utf-8")
    active_manifest, closure_manifest = tmp_path / "active.json", tmp_path / "closure.json"

    result = freeze_c1(argparse.Namespace(
        source_live_root=live, frozen_root=frozen,
        collection_cutoff_server_time="2026-07-25T02:00:00Z", operator="operator",
        late_submission_policy="exclude_after_cutoff", active_log_freeze_manifest=active_manifest,
        collection_closure_manifest=closure_manifest, export_dir=[exports],
        manual_assignment=manual, semi_assignment=semi,
    ))

    assert result["active_log"]["source_aggregate_sha256"] == result["active_log"]["frozen_aggregate_sha256"]
    assert result["collection_closure"]["collection_window_closed"] is True
    assert result["collection_closure"]["c1_active_log_freeze_manifest_sha256"]


def test_day2_fails_closed_before_materializing_assignments(tmp_path, monkeypatch):
    closeout = tmp_path / "closeout.json"
    risk = tmp_path / "risk.json"
    closeout.write_text(json.dumps({"formal_closeout_ready": False}), encoding="utf-8")
    risk.write_text(json.dumps({"formal_ready": False}), encoding="utf-8")
    args = argparse.Namespace(c1_closeout_summary=closeout, risk_summary=risk)
    monkeypatch.setattr("tools.thesis_main.analysis.run_c1_closeout_launch.formal_git_state", lambda _root: {"clean": True})
    with pytest.raises(ValueError, match="not formally frozen"):
        build_c2b(args)


def test_day1_finalize_freezes_c1_evidence_but_not_routing_profile(tmp_path):
    (tmp_path / "c1_measurement_freeze_manifest.json").write_text(json.dumps({"C1_MEASUREMENT_FROZEN": True, "C1_EVIDENCE_BUNDLE_FROZEN": True, "C2B_BASELINE_INPUT_FROZEN": True, "Q_GT_FREEZE_STATUS": "frozen", "R_LOO_FREEZE_STATUS": "support_limited", "F_STRUCT_FREEZE_STATUS": "frozen"}), encoding="utf-8")
    (tmp_path / "c1_final_canonical_closeout_summary.json").write_text(json.dumps({"blockers": [], "formal_closeout_ready": True}), encoding="utf-8")
    (tmp_path / "formal_audit_summary.json").write_text(json.dumps({"input_status": "formal", "formal_closeout_ready": True, "blockers": [], "method_contract": "Pilot->P1->C1->C2-B->C2-A-RP->T1->V1", "git_commit_sha": "a" * 40, "worktree_clean": True, "full_dependency_bundle_sha256": "bundle", "C1_CANONICAL_CLOSED": True, "collection_closure": {"status": "validated"}}), encoding="utf-8")
    adjudication = tmp_path / "adjudication.json"; adjudication.write_text(json.dumps({"approved": True, "input_bundle_sha256": "bundle"}), encoding="utf-8")
    result = finalize_c1(argparse.Namespace(output_dir=tmp_path, adjudication_manifest=adjudication))
    assert result["formal_closeout_ready"] is True
    assert result["C1_MEASUREMENT_FROZEN"] is True
    assert result["routing_profile_frozen"] is False


def test_day1_finalize_refuses_unresolved_formal_blockers(tmp_path):
    (tmp_path / "c1_measurement_freeze_manifest.json").write_text(json.dumps({"C1_MEASUREMENT_FROZEN": True, "C2B_DESIGN_READY": True}), encoding="utf-8")
    (tmp_path / "c1_final_canonical_closeout_summary.json").write_text(json.dumps({"blockers": ["unreviewed_structural_rows"], "formal_closeout_ready": False}), encoding="utf-8")
    (tmp_path / "formal_audit_summary.json").write_text(json.dumps({"input_status": "formal", "formal_closeout_ready": False, "blockers": ["unreviewed_structural_rows"], "method_contract": "Pilot->P1->C1->C2-B->C2-A-RP->T1->V1", "git_commit_sha": "a" * 40, "worktree_clean": True, "full_dependency_bundle_sha256": "bundle", "C1_CANONICAL_CLOSED": True, "collection_closure": {"status": "validated"}}), encoding="utf-8")
    adjudication = tmp_path / "adjudication.json"; adjudication.write_text(json.dumps({"approved": True, "input_bundle_sha256": "bundle"}), encoding="utf-8")
    result = finalize_c1(argparse.Namespace(output_dir=tmp_path, adjudication_manifest=adjudication))
    assert result["formal_closeout_ready"] is False
    assert "formal_audit_or_closeout_blocked" in result["blockers"]


def test_future_c2_confirmation_never_blocks_c1_closeout_owner():
    assert _c1_closeout_blockers(True, []) == []
    assert "c2b_not_confirmed" not in _c1_closeout_blockers(True, [])


def test_holdout_clear_evidence_row_is_not_misread_as_a_heldout_image():
    source = [{"image_id": "i1", "allocation": "C2"}]
    holdout = [{"image_id": "i1", "future_holdout_clear": "true"}, {"image_id": "i2", "allocation": "future_holdout"}]
    assert _c2_source_images(source) == {"i1"}
    assert _future_heldout_images(holdout) == {"i2"}


def test_raw_snapshot_metadata_does_not_change_source_assignment_identity():
    source = [{"path": "D:/inputs/manual.csv", "size": 12, "sha256": "a" * 64}]
    snapshot = [{**source[0], "input_role": "manual_assignment", "snapshot_path": "D:/snapshot/manual.csv", "snapshot_sha256": "a" * 64}]
    assert _source_identity_aggregate(snapshot) == _aggregate_sha(source)
