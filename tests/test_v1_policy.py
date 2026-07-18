from __future__ import annotations

import csv
import json

import pytest

from tools.thesis_main.analysis.geometry_consensus.representation import normalize_geometry
from tools.thesis_main.analysis.routing.v1_policy import (
    aggregate_submissions,
    feasibility_report,
    load_frozen_manifest,
    materialize_v1_policy,
    rank_candidates,
    run_v1_trial,
)
from tools.thesis_main.analysis.vfinal_artifact_utils import sha256_file


def _manifest() -> dict:
    return {
        "manifest_version": "v1_policy_execution_v1",
        "freeze_version": "freeze-1",
        "profile_version": "profile-1",
        "dependencies": [],
        "scoring": {
            "lambda_B": 0.4,
            "lambda_P": 0.4,
            "max_total_adjustment": 0.5,
            "d_cal_F_min": 0.0,
            "d_cal_F_max": 1.0,
            "family_activation_threshold": 0.6,
            "family_activation_margin": 0.2,
            "min_conditional_supported": 2,
            "ranking_stability_margin": 0.01,
        },
        "scheduler": {
            "offer_timeout": 60,
            "completion_timeout": 600,
            "max_offer_attempts": 4,
            "k_initial": 2,
            "standard_cap": 3,
            "exceptional_cap": 4,
            "per_worker_arm_quota": 1,
            "seed": 73,
        },
        "aggregation": {
            "min_q_boundary": 0.95,
            "min_q_wallwall": 0.95,
            "min_cluster_size": 2,
            "min_medoid_margin": 0.0,
            "multimodal_second_cluster_min": 2,
        },
        "feasibility": {
            "min_activation_rate": 0.0,
            "max_fallback_rate": 1.0,
            "min_first_choice_divergence": 0.0,
            "min_initial_set_divergence": 0.0,
            "min_capacity_adjusted_divergence": 0.0,
        },
    }


def _candidate(worker: str, score: float, *, boost: float = 0.0) -> dict:
    return {
        "worker_id": worker,
        "eligible": True,
        "available": True,
        "global_lcb": score,
        "B_u_risk": boost,
        "B_u_routing_eligible": True,
        "p1_supported_families": ["undercoverage"],
        "p1_family_scores": {"undercoverage": boost},
        "profile_version": "profile-1",
    }


def _task(task_id: str, arm: str = "") -> dict:
    return {
        "block_id": "b1",
        "task_id": task_id,
        "arm": arm,
        "availability_snapshot_id": "snap-1",
        "d_cal_F": 0.5,
        "risk_route": True,
        "family_scores": {"undercoverage": 0.9, "topology": 0.2},
    }


def _geometry(x_offset: float = 0.0) -> dict:
    return normalize_geometry(
        [
            [100 + x_offset, 100],
            [100 + x_offset, 400],
            [600 + x_offset, 100],
            [600 + x_offset, 400],
        ]
    )


def _valid(geometry: dict | None = None, **extra) -> dict:
    return {
        "outcome": "completed_valid",
        "structurally_valid": True,
        "geometry": geometry or _geometry(),
        **extra,
    }


def test_full_uses_only_supported_adjustments_and_fallback_is_exact_global() -> None:
    manifest = _manifest()
    candidates = [_candidate("w1", 0.9), _candidate("w2", 0.8, boost=1.0)]
    ranked = rank_candidates(candidates, _task("t1"), manifest)
    assert ranked["strong_global"] == ["w1", "w2"]
    assert ranked["full_integrated"] == ["w2", "w1"]

    fallback_task = {**_task("t1"), "d_cal_F": 2.0}
    fallback = rank_candidates(candidates, fallback_task, manifest)
    assert fallback["full_fallback"] is True
    assert fallback["full_integrated"] == fallback["strong_global"]
    assert "d_cal_F_out_of_support" in fallback["fallback_reasons"]


def test_scheduler_rules_are_arm_symmetric_and_capacity_is_not_borrowed() -> None:
    manifest = _manifest()
    candidates = {
        "tg": [_candidate("w1", 1.0), _candidate("w2", 0.9)],
        "tf": [_candidate("w1", 1.0), _candidate("w2", 0.9)],
    }
    outcomes = {
        ("tg", "w1"): _valid(),
        ("tg", "w2"): _valid(),
        ("tf", "w1"): _valid(),
        ("tf", "w2"): _valid(),
    }
    offers, _ = run_v1_trial([_task("tg", "strong_global"), _task("tf", "full_integrated")], candidates, outcomes, manifest)
    first_by_task = {task: next(row for row in offers if row["task_id"] == task) for task in ("tg", "tf")}
    assert first_by_task["tg"]["offered_worker"] == first_by_task["tf"]["offered_worker"] == "w1"
    assert first_by_task["tg"]["offer_timeout"] == first_by_task["tf"]["offer_timeout"] == 60
    assert first_by_task["tg"]["completion_timeout"] == first_by_task["tf"]["completion_timeout"] == 600
    assert first_by_task["tg"]["capacity_before"] == first_by_task["tf"]["capacity_before"] == 1


def test_accepted_not_completed_consumes_only_its_own_arm_capacity() -> None:
    manifest = _manifest()
    tasks = [_task("tg", "strong_global"), _task("tf", "full_integrated")]
    candidates = {task["task_id"]: [_candidate("w1", 1.0), _candidate("w2", 0.9)] for task in tasks}
    outcomes = {
        ("tg", "w1"): {"outcome": "accepted_not_completed"},
        ("tg", "w2"): _valid(),
        ("tf", "w1"): _valid(),
        ("tf", "w2"): _valid(),
    }
    offers, _ = run_v1_trial(tasks, candidates, outcomes, manifest)
    global_first = next(row for row in offers if row["task_id"] == "tg")
    full_first = next(row for row in offers if row["task_id"] == "tf")
    assert global_first["capacity_after"] == 0
    assert full_first["capacity_before"] == 1


def test_invalid_decline_and_candidate_exhaustion_use_the_same_replacement_path() -> None:
    manifest = _manifest()
    task = _task("t1", "strong_global")
    candidates = {"t1": [_candidate("w1", 1.0), _candidate("w2", 0.9), _candidate("w3", 0.8)]}
    outcomes = {
        ("t1", "w1"): {"outcome": "declined"},
        ("t1", "w2"): {"outcome": "completed_invalid"},
        ("t1", "w3"): _valid(),
    }
    offers, summaries = run_v1_trial([task], candidates, outcomes, manifest)
    assert [row["replacement_reason"] for row in offers[:2]] == ["offered_declined", "completed_invalid"]
    assert summaries[0]["terminal_status"] == "unresolved"
    assert summaries[0]["candidate_exhausted"] is True
    assert summaries[0]["policy_failure_reason"] == "candidate_exhaustion"


def test_scheduler_is_reproducible_for_fixed_seed() -> None:
    manifest = _manifest()
    tasks = [_task(f"t{index}") for index in range(6)]
    candidates = {task["task_id"]: [_candidate("w1", 1.0), _candidate("w2", 0.9)] for task in tasks}
    outcomes = {(task["task_id"], worker): _valid() for task in tasks for worker in ("w1", "w2")}
    assert run_v1_trial(tasks, candidates, outcomes, manifest) == run_v1_trial(tasks, candidates, outcomes, manifest)


def test_gt_fields_do_not_change_routing_or_aggregation() -> None:
    manifest = _manifest()
    candidates = [_candidate("w1", 1.0), _candidate("w2", 0.9)]
    base = [_valid(worker_id="w1", global_lcb=1.0), _valid(worker_id="w2", global_lcb=0.9)]
    poisoned = [{**row, "gt_iou": 1.0 - index, "gold_geometry": {"malicious": True}} for index, row in enumerate(base)]
    assert rank_candidates(candidates, _task("t1"), manifest) == rank_candidates(
        [{**row, "gt_iou": -999} for row in candidates], {**_task("t1"), "gt_quality": 999}, manifest
    )
    assert aggregate_submissions(base, manifest, at_cap=True) == aggregate_submissions(poisoned, manifest, at_cap=True)


def test_multimodal_is_unresolved_and_no_legal_submission_is_severe() -> None:
    manifest = _manifest()
    first = _geometry()
    second = _geometry(250)
    rows = [
        _valid(first, worker_id="w1", global_lcb=1.0),
        _valid(first, worker_id="w2", global_lcb=0.9),
        _valid(second, worker_id="w3", global_lcb=0.8),
        _valid(second, worker_id="w4", global_lcb=0.7),
    ]
    result = aggregate_submissions(rows, manifest, at_cap=True)
    assert result["terminal_status"] == "unresolved"
    assert result["multimodal"] is True
    assert aggregate_submissions([{"outcome": "completed_invalid"}], manifest, at_cap=True)["terminal_status"] == "severe_failure"
    assert aggregate_submissions([{"outcome": "external_system_failure_pending_disposition"}], manifest, at_cap=True)["terminal_status"] == "severe_failure"


def test_feasibility_gate_blocks_indistinguishable_policy() -> None:
    manifest = _manifest()
    manifest["feasibility"]["min_first_choice_divergence"] = 0.5
    task = {**_task("t1"), "risk_route": False, "family_scores": {}}
    report = feasibility_report([task], {"t1": [_candidate("w1", 1.0), _candidate("w2", 0.9)]}, manifest)
    assert report["first_choice_divergence"] == 0.0
    assert report["launch_status"] == "not_launched_policy_indistinguishable"


def test_formal_manifest_requires_sha_dependencies_and_rejects_dry_run(tmp_path) -> None:
    dependency = tmp_path / "profile.csv"
    dependency.write_text("worker_id\nw1\n", encoding="utf-8")
    manifest = _manifest()
    manifest["dependencies"] = [{"path": dependency.name, "sha256": sha256_file(dependency)}]
    path = tmp_path / "freeze.json"
    path.write_text(json.dumps(manifest), encoding="utf-8")
    loaded = load_frozen_manifest(path, sha256_file(path), input_status="formal")
    assert loaded["freeze_version"] == "freeze-1"
    with pytest.raises(ValueError, match="dry-run"):
        load_frozen_manifest(path, sha256_file(path), input_status="dry_run")
    dependency.write_text("tampered", encoding="utf-8")
    with pytest.raises(ValueError, match="stale"):
        load_frozen_manifest(path, sha256_file(path), input_status="formal")


def test_csv_materializer_parses_geometry_json_and_writes_formal_outputs(tmp_path) -> None:
    def write_csv(path, rows):
        with path.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
            writer.writeheader()
            writer.writerows(rows)

    manifest_path = tmp_path / "freeze.json"
    manifest_path.write_text(json.dumps(_manifest()), encoding="utf-8")
    tasks = tmp_path / "tasks.csv"
    candidates = tmp_path / "candidates.csv"
    outcomes = tmp_path / "outcomes.csv"
    write_csv(tasks, [_task("t1", "strong_global")])
    write_csv(candidates, [{**_candidate("w1", 1.0), "task_id": "t1"}, {**_candidate("w2", 0.9), "task_id": "t1"}])
    corners = json.dumps([[100, 100], [100, 400], [600, 100], [600, 400]])
    write_csv(outcomes, [
        {"task_id": "t1", "worker_id": "w1", "outcome": "completed_valid", "structurally_valid": "true", "corners_px": corners},
        {"task_id": "t1", "worker_id": "w2", "outcome": "completed_valid", "structurally_valid": "true", "corners_px": corners},
    ])
    output = tmp_path / "out"
    audit = materialize_v1_policy(
        tasks, candidates, outcomes, output,
        freeze_manifest=manifest_path,
        freeze_manifest_sha256=sha256_file(manifest_path),
        input_status="formal",
    )
    assert audit["formal_assignment_generated"] is True
    assert (output / "v1_policy_offer_ledger.csv").exists()
    with (output / "v1_policy_task_summary.csv").open(encoding="utf-8") as handle:
        assert list(csv.DictReader(handle))[0]["terminal_status"] == "resolved"
