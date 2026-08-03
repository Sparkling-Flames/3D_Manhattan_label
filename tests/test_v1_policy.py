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
from tools.thesis_main.analysis.paper_a_contracts import METHOD_CONTRACT


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
            "formal_structure_min_k": 3,
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


def _write_stage3(tmp_path, *, gate_kind: str = "V1"):
    from tools.thesis_main.analysis.materialize_stage3_freeze_gate import build_gate, required_gates
    tmp_path.mkdir(parents=True, exist_ok=True)
    child_items = []
    for child_role in ("C1_ROW_ELIGIBILITY_FROZEN", "C1_PEER_EVIDENCE_FROZEN", "C1_STRUCTURAL_EB_FROZEN", "W034_SENSITIVITY_FROZEN"):
        child = tmp_path / f"{child_role}.json"
        child.write_text(json.dumps({"schema_version": "test_dependency_v2", "formal_ready": True, "profile_version": "p", "cohort_id": "c", "blockers": [], "dependencies": []}), encoding="utf-8")
        child_items.append({"role": child_role, "frozen": True, "path": child.name, "sha256": sha256_file(child), "expected_schema": "test_dependency_v2", "required_status_field": "formal_ready", "required_status_value": True, "profile_version": "p", "cohort_id": "c"})
    state = {}
    for role in required_gates(gate_kind):
        dependency = tmp_path / f"{role}.json"
        payload = {"schema_version": "test_dependency_v2", "formal_ready": True, "profile_version": "p", "cohort_id": "c", "blockers": [], "dependencies": child_items if role == "C1_EVIDENCE_FROZEN" else []}
        if role.startswith(("T1_", "V1_")):
            payload["artifact_role"] = role
        if role == "C1_EVIDENCE_FROZEN":
            payload.update({
                "method_contract_sha256": sha256_file(METHOD_CONTRACT),
            })
        if role == "FINAL_POOLED_PROFILE_FROZEN":
            payload.update({"artifact_role": "FINAL_POOLED_PROFILE_FROZEN", "C1_EVIDENCE_FROZEN": True, "C2B_BATCH_A_CLOSEOUT_FROZEN": True, "C2A_RP_CLOSEOUT_FROZEN": True, "FINAL_C1_C2_Q_GT_MODEL_FROZEN": True, "POOLED_WORKER_PROFILE_FROZEN": True})
        dependency.write_text(json.dumps(payload), encoding="utf-8")
        state[role] = {"frozen": True, "path": dependency.name, "sha256": sha256_file(dependency), "expected_schema": "test_dependency_v2", "required_status_field": "formal_ready", "required_status_value": True, "profile_version": "p", "cohort_id": "c"}
    gate = build_gate(state, "r" * 64, "e" * 64, base_dir=tmp_path, gate_kind=gate_kind)
    path = tmp_path / "stage3.json"
    path.write_text(json.dumps(gate), encoding="utf-8")
    return path


def test_v1_gate_rejects_t1_kind_and_missing_v1_policy_roles(tmp_path) -> None:
    from tools.thesis_main.analysis.materialize_stage3_freeze_gate import validate_gate_file

    t1_gate = _write_stage3(tmp_path / "t1", gate_kind="T1")
    with pytest.raises(ValueError, match="gate kind mismatch"):
        validate_gate_file(t1_gate, expected_gate_kind="V1")
    v1_gate = _write_stage3(tmp_path / "v1", gate_kind="V1")
    payload = json.loads(v1_gate.read_text(encoding="utf-8"))
    payload["STRONG_GLOBAL_FROZEN"] = False
    v1_gate.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(ValueError, match="does not contain all required roles"):
        validate_gate_file(v1_gate, expected_gate_kind="V1")


def _candidate(worker: str, score: float, *, boost: float = 0.0) -> dict:
    return {
        "schema_version": "policy_candidate_v2",
        "worker_id": worker,
        "global_policy_eligible": True,
        "S_G": score,
        "global_rank_S_G": {"w1": 1, "w2": 2, "w3": 3}[worker],
        "R_peer_stable": .9,
        "R_peer_profile_status": "estimated",
        "R_LOO_medoid": .8,
        "LOO_medoid_status": "estimated",
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


def test_v1_consumes_frozen_global_rank_not_peer_or_loo() -> None:
    manifest = _manifest()
    candidates = [_candidate("w1", .9), _candidate("w2", .8)]
    candidates[0].update(R_peer_stable=None, R_peer_profile_status="not_evaluable", R_LOO_medoid=None, LOO_medoid_status="not_evaluable")
    candidates[1].update(R_peer_stable=.99, R_LOO_medoid=.99)
    ranked = rank_candidates(candidates, {**_task("t1"), "risk_route": False, "family_scores": {}}, manifest)
    assert ranked["strong_global"] == ["w1", "w2"]


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
    offers, _ = run_v1_trial(
        [_task("tg", "strong_global"), _task("tf", "full_integrated")],
        candidates, outcomes, manifest, allow_preassigned_arms=True,
    )
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
    offers, _ = run_v1_trial(tasks, candidates, outcomes, manifest, allow_preassigned_arms=True)
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
    assert summaries[0]["policy_failure_reason"] == "policy_candidate_exhaustion"


def test_scheduler_is_reproducible_for_fixed_seed() -> None:
    manifest = _manifest()
    tasks = [_task(f"t{index}") for index in range(6)]
    candidates = {task["task_id"]: [_candidate("w1", 1.0), _candidate("w2", 0.9)] for task in tasks}
    outcomes = {(task["task_id"], worker): _valid() for task in tasks for worker in ("w1", "w2")}
    assert run_v1_trial(tasks, candidates, outcomes, manifest) == run_v1_trial(tasks, candidates, outcomes, manifest)


def test_formal_scheduler_ignores_prepopulated_arm() -> None:
    manifest = _manifest()
    tasks = [_task(f"t{index}", "strong_global") for index in range(4)]
    candidates = {task["task_id"]: [_candidate("w1", 1.0), _candidate("w2", 0.9)] for task in tasks}
    outcomes = {(task["task_id"], worker): _valid(annotation_id=f"{task['task_id']}-{worker}") for task in tasks for worker in ("w1", "w2")}
    _, summaries = run_v1_trial(tasks, candidates, outcomes, manifest)
    assert {row["policy_arm"] for row in summaries} == {"strong_global", "full_integrated"}


def test_gt_fields_do_not_change_routing_or_aggregation() -> None:
    manifest = _manifest()
    candidates = [_candidate("w1", 1.0), _candidate("w2", 0.9)]
    base = [_valid(worker_id="w1", S_G=1.0), _valid(worker_id="w2", S_G=0.9)]
    poisoned = [{**row, "gt_iou": 1.0 - index, "gold_geometry": {"malicious": True}} for index, row in enumerate(base)]
    assert rank_candidates(candidates, _task("t1"), manifest) == rank_candidates(
        [{**row, "gt_iou": -999} for row in candidates], {**_task("t1"), "gt_quality": 999}, manifest
    )
    assert aggregate_submissions(base, manifest, at_cap=True) == aggregate_submissions(poisoned, manifest, at_cap=True)


def test_gt_blind_medoid_tie_break_does_not_consume_global_quality() -> None:
    manifest = _manifest()
    geometry = _geometry()
    base = [
        _valid(geometry, worker_id="w1", annotation_id="a1", S_G=0.1),
        _valid(geometry, worker_id="w2", annotation_id="a2", S_G=0.9),
        _valid(geometry, worker_id="w3", annotation_id="a3", S_G=0.5),
    ]
    changed = [{**row, "S_G": 1.0 - float(row["S_G"])} for row in base]
    first = aggregate_submissions(base, manifest, at_cap=True, seed_key="task-1")
    second = aggregate_submissions(changed, manifest, at_cap=True, seed_key="task-1")
    assert first["terminal_status"] == second["terminal_status"] == "resolved"
    assert first["selected_annotation_id"] == second["selected_annotation_id"]


def test_two_legal_submissions_cannot_formally_resolve() -> None:
    manifest = _manifest()
    rows = [_valid(_geometry(), worker_id="w1"), _valid(_geometry(), worker_id="w2")]
    assert aggregate_submissions(rows, manifest, at_cap=False)["terminal_status"] == "needs_more"
    assert aggregate_submissions(rows, manifest, at_cap=True)["terminal_status"] == "unresolved"
    duplicate_worker = rows + [_valid(_geometry(), worker_id="w1")]
    with pytest.raises(ValueError, match="canonical adjudication"):
        aggregate_submissions(duplicate_worker, manifest, at_cap=True)


def test_multimodal_is_unresolved_and_no_legal_submission_is_severe() -> None:
    manifest = _manifest()
    first = _geometry()
    second = _geometry(250)
    rows = [
        _valid(first, worker_id="w1", annotation_id="a1", S_G=1.0),
        _valid(first, worker_id="w2", annotation_id="a2", S_G=0.9),
        _valid(second, worker_id="w3", annotation_id="a3", S_G=0.8),
        _valid(second, worker_id="w4", annotation_id="a4", S_G=0.7),
    ]
    result = aggregate_submissions(rows, manifest, at_cap=True)
    assert result["terminal_status"] == "unresolved"
    assert result["multimodal"] is True
    assert aggregate_submissions([{"outcome": "completed_invalid"}], manifest, at_cap=True)["terminal_status"] == "severe_failure"
    assert aggregate_submissions([{"outcome": "external_system_failure_pending_disposition"}], manifest, at_cap=True)["terminal_status"] == "external_system_failure_pending_disposition"


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
    policy = tmp_path / "strong_global_policy.json"
    policy.write_text("{}", encoding="utf-8")
    roster = tmp_path / "candidate_roster.csv"
    roster.write_text("worker_id\nw1\n", encoding="utf-8")
    manifest = _manifest()
    stage3 = _write_stage3(tmp_path)
    manifest["dependencies"] = [
        {"path": dependency.name, "sha256": sha256_file(dependency)},
        {"path": policy.name, "sha256": sha256_file(policy), "role": "strong_global_policy_manifest"},
        {"path": roster.name, "sha256": sha256_file(roster), "role": "candidate_roster"},
        {"path": stage3.name, "sha256": sha256_file(stage3), "role": "stage3_freeze_gate"},
    ]
    manifest.update(method_contract_sha256=sha256_file(METHOD_CONTRACT), policy_manifest_sha256=sha256_file(policy), candidate_roster_sha256=sha256_file(roster))
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
    manifest = _manifest()
    stage3 = _write_stage3(tmp_path)
    policy = tmp_path / "strong_global_policy.json"
    policy.write_text("{}", encoding="utf-8")
    tasks = tmp_path / "tasks.csv"
    candidates = tmp_path / "candidates.csv"
    outcomes = tmp_path / "outcomes.csv"
    capacity = tmp_path / "capacity.csv"
    write_csv(tasks, [_task("t1", "strong_global")])
    write_csv(candidates, [
        {**_candidate("w1", 1.0), "task_id": "t1"},
        {**_candidate("w2", 0.9), "task_id": "t1"},
        {**_candidate("w3", 0.8), "task_id": "t1"},
    ])
    corners = json.dumps([[100, 100], [100, 400], [600, 100], [600, 400]])
    write_csv(outcomes, [
        {"task_id": "t1", "worker_id": "w1", "annotation_id": "a1", "outcome": "completed_valid", "structurally_valid": "true", "corners_px": corners},
        {"task_id": "t1", "worker_id": "w2", "annotation_id": "a2", "outcome": "completed_valid", "structurally_valid": "true", "corners_px": corners},
        {"task_id": "t1", "worker_id": "w3", "annotation_id": "a3", "outcome": "completed_valid", "structurally_valid": "true", "corners_px": corners},
    ])
    write_csv(capacity, [
        {"block_id": "b1", "worker_id": worker, "availability_snapshot_id": "snap-1", "available": "true",
         "total_capacity": "2", "strong_global_quota": "1", "full_integrated_quota": "1"}
        for worker in ("w1", "w2", "w3")
    ])
    manifest["dependencies"] = [
        {"path": stage3.name, "sha256": sha256_file(stage3), "role": "stage3_freeze_gate"},
        {"path": policy.name, "sha256": sha256_file(policy), "role": "strong_global_policy_manifest"},
        {"path": candidates.name, "sha256": sha256_file(candidates), "role": "candidate_roster"},
    ]
    manifest.update(method_contract_sha256=sha256_file(METHOD_CONTRACT), policy_manifest_sha256=sha256_file(policy), candidate_roster_sha256=sha256_file(candidates))
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    output = tmp_path / "out"
    audit = materialize_v1_policy(
        tasks, candidates, outcomes, output,
        freeze_manifest=manifest_path,
            freeze_manifest_sha256=sha256_file(manifest_path),
            input_status="formal",
            capacity_manifest_csv=capacity,
        )
    assert audit["formal_assignment_generated"] is False
    assert audit["artifact_role"] == "deterministic_replay_audit"
    assert (output / "v1_policy_offer_ledger.csv").exists()
    with (output / "v1_policy_task_summary.csv").open(encoding="utf-8") as handle:
        row = list(csv.DictReader(handle))[0]
        assert row["terminal_status"] == "resolved"
        assert row["selected_annotation_id"] in {"a1", "a2"}
        assert len(row["selected_geometry_sha256"]) == 64
