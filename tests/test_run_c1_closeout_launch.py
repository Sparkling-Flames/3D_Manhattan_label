import argparse
import json

import pytest

from tools.thesis_main.analysis.run_c1_closeout_launch import day1_audit, day1_finalize, day2_build
from tools.thesis_main.analysis.run_c1_precloseout_rehearsal import _candidate_design_manifest, _candidate_task_pool


def test_day1_rejects_mutable_active_log_directory(tmp_path):
    args = argparse.Namespace(active_log_snapshot=tmp_path / "new_server")
    with pytest.raises(ValueError, match="frozen C1 active-log snapshot"):
        day1_audit(args)


def test_day2_fails_closed_before_materializing_assignments(tmp_path, monkeypatch):
    closeout = tmp_path / "closeout.json"
    risk = tmp_path / "risk.json"
    closeout.write_text(json.dumps({"formal_closeout_ready": False}), encoding="utf-8")
    risk.write_text(json.dumps({"formal_ready": False}), encoding="utf-8")
    args = argparse.Namespace(c1_closeout_summary=closeout, risk_summary=risk)
    monkeypatch.setattr("tools.thesis_main.analysis.run_c1_closeout_launch.formal_git_state", lambda _root: {"clean": True})
    with pytest.raises(ValueError, match="not formally frozen"):
        day2_build(args)


def test_day1_finalize_freezes_c1_evidence_but_not_routing_profile(tmp_path):
    (tmp_path / "c1_measurement_freeze_manifest.json").write_text(json.dumps({"C1_MEASUREMENT_FROZEN": True, "C2B_DESIGN_READY": True}), encoding="utf-8")
    (tmp_path / "c1_final_canonical_closeout_summary.json").write_text(json.dumps({"blockers": []}), encoding="utf-8")
    (tmp_path / "formal_audit_summary.json").write_text(json.dumps({"input_status": "formal", "method_contract": "Pilot->P1->C1->C2-B->C2-A-RP->T1->V1", "git_commit_sha": "a" * 40, "worktree_clean": True, "full_dependency_bundle_sha256": "bundle", "C1_CANONICAL_CLOSED": True, "collection_closure": {"status": "validated"}}), encoding="utf-8")
    adjudication = tmp_path / "adjudication.json"; adjudication.write_text(json.dumps({"approved": True, "input_bundle_sha256": "bundle"}), encoding="utf-8")
    result = day1_finalize(argparse.Namespace(output_dir=tmp_path, adjudication_manifest=adjudication))
    assert result["formal_closeout_ready"] is True
    assert result["C1_MEASUREMENT_FROZEN"] is True
    assert result["routing_profile_frozen"] is False


def test_candidate_design_allows_same_source_pool_for_distinct_anchor_and_bridge_roles(tmp_path):
    task_pool = tmp_path / "tasks.csv"
    task_pool.write_text(
        "task_id,anchor_eligible,bridge_eligible,assignment_eligible\n" + "\n".join(f"t{i},true,true,true" for i in range(12)) + "\n",
        encoding="utf-8",
    )
    worker_profile = tmp_path / "workers.csv"
    worker_profile.write_text("worker_id,c2_candidate_eligible\nw1,true\n", encoding="utf-8")
    manifest = tmp_path / "design.json"
    _candidate_design_manifest(task_pool, worker_profile, manifest)
    assert len(json.loads(manifest.read_text(encoding="utf-8"))["candidate_designs"]) > 3


def test_legacy_reserve_is_candidate_provenance_not_forced_assignment(tmp_path):
    inventory = tmp_path / "inventory.csv"
    inventory.write_text("task_id,base_task_id,eligible_after_exclusion,geometry_gold_ready,gt_pair_count\nt1,b1,true,true,4\nt2,b2,true,true,4\n", encoding="utf-8")
    reserve = tmp_path / "reserve.csv"
    reserve.write_text("task_id,base_task_id,selection_rank,selection_reason\nt1,b1,1,human curated\n", encoding="utf-8")
    output = _candidate_task_pool(inventory, [], tmp_path / "pool.csv", reserve)
    rows = list(__import__("csv").DictReader(output.open(encoding="utf-8")))
    assert rows[0]["legacy_human_curated_candidate"] == "true"
    assert rows[1]["legacy_human_curated_candidate"] == "false"
    assert all("assignment" not in row for row in rows)
