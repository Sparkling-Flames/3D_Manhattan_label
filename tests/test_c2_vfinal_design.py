from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path

import pytest

from tools.thesis_main.analysis.build_c2_assignment_manifest_from_c1_gaps import materialize as materialize_c2b
from tools.thesis_main.analysis.c1_materialize_c2_gap_audits import materialize as materialize_c2a


def _csv(path: Path, fields: list[str], rows: list[dict]) -> None:
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def _rows(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as stream:
        return list(csv.DictReader(stream))


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _inputs(tmp_path: Path) -> tuple[Path, Path, Path]:
    workers = tmp_path / "workers.csv"
    pool = tmp_path / "pool.csv"
    manifest = tmp_path / "design.json"
    _csv(workers, ["worker_id", "support", "ci_half_width", "c2_eligible"], [
        {"worker_id": worker, "support": 8, "ci_half_width": 0.18, "c2_eligible": "true"}
        for worker in ("w1", "w2", "w3", "w4")
    ])
    tasks = [
        {"task_id": "a_o", "base_task_id": "a_o", "task_stratum": "ordinary", "anchor_eligible": "true", "bridge_eligible": "false"},
        {"task_id": "a_s", "base_task_id": "a_s", "task_stratum": "stress", "anchor_eligible": "true", "bridge_eligible": "false"},
    ]
    tasks += [
        {"task_id": f"b{i}", "base_task_id": f"b{i}", "task_stratum": "ordinary" if i % 2 else "stress", "anchor_eligible": "false", "bridge_eligible": "true"}
        for i in range(1, 5)
    ]
    _csv(pool, ["task_id", "base_task_id", "task_stratum", "anchor_eligible", "bridge_eligible"], tasks)
    manifest.write_text(json.dumps({
        "manifest_version": "c2_design_v1",
        "input_sha256": {"worker_profile_csv": _sha(workers), "task_pool_csv": _sha(pool)},
        "c2b_target_ci_half_width": 0.155,
        "candidate_designs": [
            {"design_id": "too_small", "common_anchor_count": 1, "bridge_per_worker": 1, "unique_bridge_tasks": 2, "min_task_support": 2, "max_worker_stratum_imbalance": 1},
            {"design_id": "minimum_feasible", "common_anchor_count": 2, "bridge_per_worker": 2, "unique_bridge_tasks": 4, "min_task_support": 2, "max_worker_stratum_imbalance": 1},
            {"design_id": "larger", "common_anchor_count": 2, "bridge_per_worker": 3, "unique_bridge_tasks": 4, "min_task_support": 2, "max_worker_stratum_imbalance": 2},
        ],
        "precision": {"target_ci_half_width": 0.15, "max_additional_blocks": 3},
    }), encoding="utf-8")
    return pool, workers, manifest


def test_selects_smallest_feasible_connected_balanced_design(tmp_path: Path) -> None:
    pool, workers, design = _inputs(tmp_path)
    summary = materialize_c2b(pool, workers, design, tmp_path / "out")
    assignments = _rows(tmp_path / "out" / "assignment_manifest_C2B.csv")
    graph = _rows(tmp_path / "out" / "c2b_worker_task_graph_audit.csv")[0]
    pairs = {(row["worker_id"], row["task_id"]) for row in assignments}

    assert summary["chosen_design_id"] == "minimum_feasible"
    assert summary["candidate_only"] is True
    assert summary["launch_ready"] is False
    assert len(pairs) == len(assignments) == 16
    assert graph["worker_task_graph_connected"] == "true"
    assert graph["min_bridge_task_support"] == "2"
    assert graph["max_worker_stratum_imbalance"] in {"0", "1"}
    common = [row for row in assignments if row["c2_component"] == "common_anchor"]
    assert {row["task_id"] for row in common} == {"a_o", "a_s"}
    assert all(sum(row["worker_id"] == worker for row in common) == 2 for worker in ("w1", "w2", "w3", "w4"))


def test_stale_design_manifest_fails_closed(tmp_path: Path) -> None:
    pool, workers, design = _inputs(tmp_path)
    closeout = tmp_path / "closeout.json"
    closeout.write_text(json.dumps({"formal_closeout_ready": True, "profile_freeze_status": "C1_frozen"}), encoding="utf-8")
    data = json.loads(design.read_text(encoding="utf-8"))
    data["input_sha256"]["c1_closeout_summary"] = _sha(closeout)
    design.write_text(json.dumps(data), encoding="utf-8")
    with pool.open("a", encoding="utf-8") as stream:
        stream.write("\n")
    with pytest.raises(ValueError, match="stale_or_unbound"):
        materialize_c2b(pool, workers, design, tmp_path / "out", input_status="formal", c1_closeout_summary=closeout)


def test_formal_task_shortage_fails_closed(tmp_path: Path) -> None:
    pool, workers, design = _inputs(tmp_path)
    _csv(pool, ["task_id", "base_task_id", "task_stratum", "anchor_eligible", "bridge_eligible"], [
        {"task_id": "a_o", "base_task_id": "a_o", "task_stratum": "ordinary", "anchor_eligible": "true", "bridge_eligible": "false"},
    ])
    closeout = tmp_path / "closeout.json"
    closeout.write_text(json.dumps({"formal_closeout_ready": True, "profile_freeze_status": "C1_frozen"}), encoding="utf-8")
    data = json.loads(design.read_text(encoding="utf-8"))
    data["input_sha256"] = {
        "worker_profile_csv": _sha(workers),
        "task_pool_csv": _sha(pool),
        "c1_closeout_summary": _sha(closeout),
    }
    design.write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(ValueError, match="no_feasible_c2b_design"):
        materialize_c2b(pool, workers, design, tmp_path / "out", input_status="formal", c1_closeout_summary=closeout)


def test_precision_adds_only_needed_paired_blocks_and_caps_uncertain(tmp_path: Path) -> None:
    profile = tmp_path / "post_c2b.csv"
    _csv(profile, ["worker_id", "support", "ci_half_width"], [
        {"worker_id": "met", "support": 8, "ci_half_width": 0.14},
        {"worker_id": "fillable", "support": 8, "ci_half_width": 0.18},
        {"worker_id": "capped", "support": 8, "ci_half_width": 0.4},
    ])
    design = tmp_path / "design.json"
    design.write_text(json.dumps({
        "manifest_version": "c2_design_v1",
        "input_sha256": {"worker_profile_csv": _sha(profile)},
        "precision": {"target_ci_half_width": 0.15, "max_additional_blocks": 3},
    }), encoding="utf-8")
    summary = materialize_c2a(profile, design, tmp_path / "out")
    rows = {row["worker_id"]: row for row in _rows(tmp_path / "out" / "precision_plan_C2A_RP.csv")}

    assert rows["met"]["additional_blocks"] == "0"
    assert rows["fillable"]["ordinary_tasks"] == rows["fillable"]["stress_tasks"] == "2"
    assert rows["capped"]["additional_blocks"] == "3"
    assert rows["capped"]["routing_eligibility"] == "uncertain_fallback_global"
    assert rows["capped"]["unmet_reason"] == "target_not_met_at_frozen_cap"
    assert summary["searches_new_risk_family"] is False
    assert summary["modifies_c1"] is False
