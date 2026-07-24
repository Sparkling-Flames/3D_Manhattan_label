import argparse
import json

import pytest

from tools.thesis_main.analysis.run_c1_closeout_launch import day1_audit, day2_build
from tools.thesis_main.analysis.run_c1_precloseout_rehearsal import _candidate_design_manifest, _candidate_task_pool


def test_day1_rejects_mutable_active_log_directory(tmp_path):
    args = argparse.Namespace(active_log_snapshot=tmp_path / "new_server")
    with pytest.raises(ValueError, match="frozen C1 active-log snapshot"):
        day1_audit(args)


def test_day2_fails_closed_before_materializing_assignments(tmp_path):
    closeout = tmp_path / "closeout.json"
    risk = tmp_path / "risk.json"
    closeout.write_text(json.dumps({"formal_closeout_ready": False}), encoding="utf-8")
    risk.write_text(json.dumps({"formal_ready": False}), encoding="utf-8")
    args = argparse.Namespace(c1_closeout_summary=closeout, risk_summary=risk)
    with pytest.raises(ValueError, match="not formally frozen"):
        day2_build(args)


def test_candidate_design_allows_same_source_pool_for_distinct_anchor_and_bridge_roles(tmp_path):
    task_pool = tmp_path / "tasks.csv"
    task_pool.write_text(
        "task_id,anchor_eligible,bridge_eligible,assignment_eligible\n" + "\n".join(f"t{i},true,true,true" for i in range(12)) + "\n",
        encoding="utf-8",
    )
    worker_profile = tmp_path / "workers.csv"
    worker_profile.write_text("worker_id\nw1\n", encoding="utf-8")
    manifest = tmp_path / "design.json"
    _candidate_design_manifest(task_pool, worker_profile, manifest)
    assert len(json.loads(manifest.read_text(encoding="utf-8"))["candidate_designs"]) == 3


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
