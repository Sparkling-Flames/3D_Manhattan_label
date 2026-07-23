from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path

import pytest

from tools.thesis_main.analysis.build_c2_assignment_manifest_from_c1_gaps import materialize as materialize_c2b
from tools.thesis_main.analysis.c1_materialize_c2_gap_audits import materialize as materialize_c2a
from tools.thesis_main.analysis.materialize_c2b_closeout import materialize as materialize_c2b_closeout


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


def _closeout_dependencies(tmp_path: Path, manifest_data: dict) -> tuple[Path, Path, Path, Path]:
    paths = [
        tmp_path / "c1_closeout.json", tmp_path / "c2b_assignment.csv",
        tmp_path / "worker_roster.csv", tmp_path / "rule_config.json",
    ]
    contents = [
        json.dumps({"formal_closeout_ready": True, "profile_freeze_status": "C1_frozen"}),
        "task_id,worker_id,c2_component\nt1,w1,common_anchor\n",
        "worker_id\nw1\n",
        json.dumps({"min_common_anchor_per_worker": 1, "min_bridge_per_worker": 0, "min_task_support": 1}),
    ]
    for path, content in zip(paths, contents):
        path.write_text(content, encoding="utf-8")
    manifest_data.setdefault("input_sha256", {}).update({
        "c1_closeout_summary": _sha(paths[0]),
        "c2b_assignment_csv": _sha(paths[1]),
        "worker_roster_csv": _sha(paths[2]),
        "rule_config": _sha(paths[3]),
    })
    return tuple(paths)


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


def test_formal_c2b_uses_c1_risk_slope_simulation(tmp_path: Path) -> None:
    pool, workers, design = _inputs(tmp_path)
    rows = _rows(workers)
    _csv(workers, list(rows[0]) + ["risk_slope_estimate", "risk_slope_se", "risk_slope_support"], [
        {**row, "risk_slope_estimate": 0.1, "risk_slope_se": 0.05, "risk_slope_support": 8}
        for row in rows
    ])
    closeout = tmp_path / "closeout.json"
    closeout.write_text(json.dumps({
        "formal_closeout_ready": True, "profile_freeze_status": "C1_frozen"
    }), encoding="utf-8")
    data = json.loads(design.read_text(encoding="utf-8"))
    data["input_sha256"] = {
        "worker_profile_csv": _sha(workers),
        "task_pool_csv": _sha(pool),
        "c1_closeout_summary": _sha(closeout),
    }
    data["simulation"] = {"seed": 17, "draws": 500}
    design.write_text(json.dumps(data), encoding="utf-8")

    summary = materialize_c2b(
        pool, workers, design, tmp_path / "out",
        input_status="formal", c1_closeout_summary=closeout,
    )
    audits = _rows(tmp_path / "out" / "c2b_design_candidates.csv")
    assert summary["launch_ready"] is True
    assert {row["design_method"] for row in audits} == {"c1_risk_slope_precision_projection"}


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
    pool = tmp_path / "c2a_pool.csv"
    _csv(pool, ["task_id", "base_task_id", "task_stratum", "c2a_rp_eligible"], [
        {"task_id": f"{stratum}-{index}", "base_task_id": f"{stratum}-{index}",
         "task_stratum": stratum, "c2a_rp_eligible": "true"}
        for stratum in ("ordinary", "stress") for index in range(1, 4)
    ])
    summary = materialize_c2a(profile, design, tmp_path / "out", task_pool_csv=pool)
    rows = {row["worker_id"]: row for row in _rows(tmp_path / "out" / "precision_plan_C2A_RP.csv")}
    assignments = _rows(tmp_path / "out" / "assignment_manifest_C2A_RP.csv")

    assert rows["met"]["additional_blocks"] == "0"
    assert rows["fillable"]["ordinary_tasks"] == rows["fillable"]["stress_tasks"] == "2"
    assert rows["capped"]["additional_blocks"] == "3"
    assert rows["capped"]["routing_eligibility"] == "uncertain_fallback_global"
    assert rows["capped"]["unmet_reason"] == "target_not_met_at_frozen_cap"
    assert len(assignments) == 10
    assert {(row["worker_id"], row["task_stratum"]) for row in assignments} == {
        ("fillable", "ordinary"), ("fillable", "stress"),
        ("capped", "ordinary"), ("capped", "stress"),
    }
    assert all(row["task_id"] for row in assignments)
    assert summary["searches_new_risk_family"] is False
    assert summary["modifies_c1"] is False


def test_formal_c2a_requires_bound_c2b_sha_and_real_task_pool(tmp_path: Path) -> None:
    profile = tmp_path / "post_c2b.csv"
    _csv(profile, ["worker_id", "support", "ci_half_width"], [
        {"worker_id": "w1", "support": 8, "ci_half_width": 0.18},
    ])
    pool = tmp_path / "pool.csv"
    _csv(pool, ["task_id", "base_task_id", "task_stratum"], [
        {"task_id": "o1", "base_task_id": "o1", "task_stratum": "ordinary"},
        {"task_id": "o2", "base_task_id": "o2", "task_stratum": "ordinary"},
        {"task_id": "s1", "base_task_id": "s1", "task_stratum": "stress"},
        {"task_id": "s2", "base_task_id": "s2", "task_stratum": "stress"},
    ])
    history = tmp_path / "history.csv"
    _csv(history, ["worker_id", "task_id", "base_task_id"], [
        {"worker_id": "w1", "task_id": "o1", "base_task_id": "o1"},
    ])
    design = tmp_path / "design.json"
    design.write_text(json.dumps({
        "manifest_version": "c2_design_v1",
        "input_sha256": {
            "worker_profile_csv": _sha(profile),
            "c2a_task_pool_csv": _sha(pool),
            "assignment_history_csv": _sha(history),
        },
        "precision": {"target_ci_half_width": 0.17, "max_additional_blocks": 1},
    }), encoding="utf-8")
    submissions = tmp_path / "c2b_submissions.csv"
    submissions.write_text("task_id,worker_id\nt1,w1\n", encoding="utf-8")
    design_summary = tmp_path / "c2b_design.summary.json"
    design_summary.write_text(json.dumps({
        "c2b_design_ready": True, "launch_ready": True, "candidate_only": False,
        "design_manifest_sha256": _sha(design),
    }), encoding="utf-8")
    profile_manifest = tmp_path / "post_profile.manifest.json"
    profile_manifest_data = {
        "manifest_version": "c2b_post_profile_v1",
        "input_sha256": {
            "c2b_submissions_csv": _sha(submissions),
            "c2b_design_summary": _sha(design_summary),
        },
        "output_sha256": {"post_c2b_worker_profile_csv": _sha(profile)},
    }
    closeout_deps = _closeout_dependencies(tmp_path, profile_manifest_data)
    profile_manifest.write_text(json.dumps(profile_manifest_data), encoding="utf-8")
    c2b = tmp_path / "c2b_closeout.summary.json"
    materialize_c2b_closeout(
        submissions, profile, profile_manifest, design_summary, *closeout_deps, c2b
    )

    with pytest.raises(ValueError, match="stale_or_unbound"):
        materialize_c2a(
            profile, design, tmp_path / "bad", c2b_summary=c2b,
            c2b_summary_sha256="0" * 64, task_pool_csv=pool,
            assignment_history_csv=history, input_status="formal",
        )
    summary = materialize_c2a(
        profile, design, tmp_path / "good", c2b_summary=c2b,
        c2b_summary_sha256=_sha(c2b), task_pool_csv=pool,
        assignment_history_csv=history, input_status="formal",
    )
    assert summary["launch_ready"] is True
    assert summary["n_assignments"] == 2
    assigned = _rows(tmp_path / "good" / "assignment_manifest_C2A_RP.csv")
    assert "o1" not in {row["task_id"] for row in assigned}
    assert all(row["target_component"] and row["gap_reason"] for row in assigned)


def test_c2b_closeout_materializes_real_post_profile_sha_chain(tmp_path: Path) -> None:
    submissions = tmp_path / "c2b_submissions.csv"
    profile = tmp_path / "post_profile.csv"
    design = tmp_path / "c2b_design.summary.json"
    manifest = tmp_path / "post_profile.manifest.json"
    submissions.write_text("task_id,worker_id\nt1,w1\n", encoding="utf-8")
    profile.write_text("worker_id,risk_slope_se\nw1,0.1\n", encoding="utf-8")
    design.write_text(json.dumps({
        "c2b_design_ready": True, "launch_ready": True, "candidate_only": False,
        "design_manifest_sha256": "a" * 64
    }), encoding="utf-8")
    manifest_data = {
        "manifest_version": "c2b_post_profile_v1",
        "input_sha256": {
            "c2b_submissions_csv": _sha(submissions),
            "c2b_design_summary": _sha(design),
        },
        "output_sha256": {"post_c2b_worker_profile_csv": _sha(profile)},
    }
    closeout_deps = _closeout_dependencies(tmp_path, manifest_data)
    manifest.write_text(json.dumps(manifest_data), encoding="utf-8")
    output = tmp_path / "c2b_closeout.summary.json"
    summary = materialize_c2b_closeout(
        submissions, profile, manifest, design, *closeout_deps, output
    )
    assert summary["c2b_closeout_ready"] is True
    assert summary["post_c2b_worker_profile_sha256"] == _sha(profile)
    assert summary["post_c2b_profile_manifest_sha256"] == _sha(manifest)

    profile.write_text("tampered", encoding="utf-8")
    with pytest.raises(ValueError, match="stale_or_unbound"):
        materialize_c2b_closeout(
            submissions, profile, manifest, design, *closeout_deps, output
        )
