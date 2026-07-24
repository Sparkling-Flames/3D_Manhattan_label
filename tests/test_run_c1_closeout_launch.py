import argparse
import json

import pytest

from tools.thesis_main.analysis.run_c1_closeout_launch import day1_audit, day2_build
from tools.thesis_main.analysis.run_c1_precloseout_rehearsal import _candidate_design_manifest


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
        "task_id,anchor_eligible,bridge_eligible\n" + "\n".join(f"t{i},true,true" for i in range(12)) + "\n",
        encoding="utf-8",
    )
    worker_profile = tmp_path / "workers.csv"
    worker_profile.write_text("worker_id\nw1\n", encoding="utf-8")
    manifest = tmp_path / "design.json"
    _candidate_design_manifest(task_pool, worker_profile, manifest)
    assert len(json.loads(manifest.read_text(encoding="utf-8"))["candidate_designs"]) == 3
