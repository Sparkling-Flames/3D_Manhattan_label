import json
import csv
from pathlib import Path

import pytest

from tools.thesis_main.analysis.geometry_consensus.representation import normalize_geometry
from tools.thesis_main.analysis.routing.temporal_replay import _fold_for_base, build_temporal_event_ledger, materialize_temporal_replay, replay_temporal_batches, replay_temporal_events
from tools.thesis_main.analysis.vfinal_artifact_utils import sha256_file


def _policy(eval_fold: int, tmp_path) -> dict:
    fit_base = next(f"fit-{index}" for index in range(100) if _fold_for_base(f"fit-{index}", 2) != eval_fold)
    artifact = tmp_path / f"policy-{eval_fold}.json"
    artifact.write_text('{"meta_min_same_state": 2, "meta_max_opposition": 0, "max_unasserted_rate": 0.25, "min_q_boundary": 0.8, "min_q_wallwall": 0.8, "min_geometry_support": 2, "risk_bucket": "low_risk", "k_dispatch_initial": 2, "k_min_for_stop": 2, "standard_cap": 5, "escalation_cap": 7, "min_complete_workers": 2, "trusted_order_sources": ["server_receive_sequence"]}', encoding="utf-8")
    from tools.thesis_main.analysis.vfinal_artifact_utils import sha256_file
    return {"policy_artifact_id": f"policy-{eval_fold}", "policy_artifact_path": str(artifact), "policy_artifact_sha256": sha256_file(artifact), "rule_version": "test-policy-v1", "fit_folds": [1 - eval_fold], "fit_base_task_ids": [fit_base]}


def _batch_inputs(events):
    evidence = {(row["canonical_annotation_id"], row["tag_family"], row["tag_name"]): {**row, "scope": "In-scope", "canonical_eligibility_status": "valid", "independence_status": "independent", "assigned_expected": "true", "outside_assignment_submission": "false", "duplicate_worker_task_submission": "false", "schema_interpretable": "true", "assertion": "+", "semi_geometry_correction_evaluable": "false"} for row in events}
    purposes = {(row["base_task_id"], row["condition"]): {"task_id": row.get("task_id", "t"), "task_purpose": "meta_label_only", "required_components": {"difficulty"}, "required_tags": {("difficulty", "occlusion")}} for row in events}
    roster = {(row["base_task_id"], row["condition"]): {item["worker_id"] for item in events if item["base_task_id"] == row["base_task_id"] and item["condition"] == row["condition"]} for row in events}
    return evidence, purposes, roster


def _write_csv(path: Path, rows: list[dict], fields: list[str] | None = None) -> None:
    fields = fields or list(rows[0])
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def _frozen_temporal_inputs(tmp_path: Path) -> dict[str, Path]:
    canonical = tmp_path / "canonical_meta.csv"
    quality = tmp_path / "quality.csv"
    three = tmp_path / "three_state.csv"
    workers = ("w1", "w2")
    canonical_rows = [{"canonical_annotation_id": f"a{i}", "worker_id": worker} for i, worker in enumerate(workers, 1)]
    quality_rows = [{
        "canonical_annotation_id": f"a{i}", "worker_id": worker, "task_id": "t", "base_task_id": "b", "condition": "manual",
        "arrived_at": "2026-01-01T00:00:00Z", "scope": "In-scope", "canonical_eligibility_status": "valid",
        "independence_status": "independent", "independence_audit_identity": f"audit-{i}", "assigned_expected": "true",
        "outside_assignment_submission": "false", "duplicate_worker_task_submission": "false", "schema_interpretable": "true",
        "parse_error": "", "schema_error": "", "semi_geometry_correction_evaluable": "false",
    } for i, worker in enumerate(workers, 1)]
    three_rows = [{"canonical_annotation_id": f"a{i}", "base_task_id": "b", "condition": "manual", "worker_id": worker, "tag_family": "difficulty", "tag_name": "occlusion", "assertion": "+"} for i, worker in enumerate(workers, 1)]
    _write_csv(canonical, canonical_rows)
    _write_csv(quality, quality_rows)
    _write_csv(three, three_rows)
    admission_source = tmp_path / "p1_admission_frozen.csv"
    assignment_source = tmp_path / "c1_assignment_frozen.csv"
    admission_source.write_text("worker_id\nw1\nw2\n", encoding="utf-8")
    assignment_source.write_text("worker_id\nw1\nw2\n", encoding="utf-8")

    policies = {
        "scope": {"policy_id": "scope-v1", "meta_min_same_state": 2, "meta_max_opposition": 0, "max_unasserted_rate": 0.25},
        "tag": {"policy_id": "tag-v1", "meta_min_same_state": 2, "meta_max_opposition": 0, "max_unasserted_rate": 0.25},
        "geometry": {"policy_id": "geometry-v1", "min_q_boundary": 0.8, "min_q_wallwall": 0.8, "min_geometry_support": 2},
        "correction": {"policy_id": "correction-v1", "min_complete_workers": 2, "require_initialization_provenance": True, "require_final_geometry": True, "require_edit_metrics": True, "require_reference_outcome": True},
        "risk": {"policy_id": "risk-v1", "risk_bucket": "low_risk", "k_dispatch_initial": 2, "k_min_for_stop": 2, "standard_cap": 5, "escalation_cap": 7, "unresolved_rule": "at_cap_or_exhaustion"},
    }
    policy_paths = {}
    for kind, payload in policies.items():
        path = tmp_path / f"{kind}_policy.json"
        path.write_text(json.dumps(payload), encoding="utf-8")
        policy_paths[kind] = path

    purpose = tmp_path / "task_purpose.csv"
    purpose_row = {
        "task_id": "t", "base_task_id": "b", "condition": "manual", "dataset_group": "Calibration_core", "task_purpose": "meta_label_only",
        "required_evidence_components": '["difficulty"]', "required_tag_family": '["difficulty"]', "required_tag_names": '["difficulty/occlusion"]',
        "risk_bucket": "low_risk", "source_assignment_path": str(assignment_source), "source_assignment_sha256": sha256_file(assignment_source), "manifest_version": "task_purpose_v1",
    }
    for kind, path in policy_paths.items():
        purpose_row[f"{kind}_policy_id"] = policies[kind]["policy_id"]
        purpose_row[f"{kind}_policy_path"] = str(path)
        purpose_row[f"{kind}_policy_sha256"] = sha256_file(path)
    _write_csv(purpose, [purpose_row])

    roster = tmp_path / "candidate_roster.csv"
    roster_rows = [{
        "base_task_id": "b", "condition": "manual", "worker_id": worker, "candidate_eligible": "true", "exclusion_reason": "",
        "source_admission_path": str(admission_source), "source_admission_sha256": sha256_file(admission_source),
        "source_assignment_path": str(assignment_source), "source_assignment_sha256": sha256_file(assignment_source), "manifest_version": "candidate_roster_v1",
    } for worker in workers]
    _write_csv(roster, roster_rows)
    history = tmp_path / "assignment_history.csv"
    _write_csv(history, [], ["base_task_id", "condition", "worker_id", "assignment_status", "effective_at", "source_manifest_path", "source_manifest_sha256", "manifest_version"])
    ledger = tmp_path / "temporal_event_ledger.csv"
    build_temporal_event_ledger(canonical, quality, three, ledger)
    geometry = tmp_path / "geometry.jsonl"
    geometry.write_text("", encoding="utf-8")

    fold = _fold_for_base("b", 2)
    fit_base = next(f"fit-{index}" for index in range(100) if _fold_for_base(f"fit-{index}", 2) != fold)
    temporal_policy = tmp_path / "temporal_policy.json"
    temporal_policy.write_text(json.dumps({
        "trusted_order_sources": ["server_receive_sequence"], "arrival_order_contract": "canonical_utc_atomic", "primary_tie_policy": "simultaneous_atomic_batch",
        "sensitivity_seed": 20260714, "sensitivity_permutations": 100, "event_ledger_sha256": sha256_file(ledger),
        "three_state_evidence_sha256": sha256_file(three), "task_purpose_manifest_sha256": sha256_file(purpose),
        "candidate_roster_manifest_sha256": sha256_file(roster), "assignment_history_sha256": sha256_file(history),
    }), encoding="utf-8")
    policy_manifest = tmp_path / "policy_manifest.json"
    policy_manifest.write_text(json.dumps({str(fold): {
        "policy_artifact_id": "temporal-v2", "policy_artifact_path": temporal_policy.name, "policy_artifact_sha256": sha256_file(temporal_policy),
        "rule_version": "temporal-v2", "fit_folds": [1 - fold], "fit_base_task_ids": [fit_base],
    }}), encoding="utf-8")
    return {"canonical": canonical, "quality": quality, "three": three, "purpose": purpose, "roster": roster, "history": history, "ledger": ledger, "geometry": geometry, "policy_manifest": policy_manifest}


def test_legacy_event_entry_is_only_a_batch_engine_wrapper(tmp_path) -> None:
    events = [{"event_id": "e1", "arrived_at": "2026-01-01T00:00:00Z", "arrival_order_source": "second_precision_export", "timestamp_precision": "second", "task_id": "t", "base_task_id": "b", "condition": "manual", "canonical_annotation_id": "a1", "worker_id": "w1", "tag_family": "difficulty", "tag_name": "occlusion"}]
    evidence, purposes, roster = _batch_inputs(events)
    fold = _fold_for_base("b", 2)
    kwargs = {"policy_by_fold": {fold: _policy(fold, tmp_path)}, "evidence_by_id": evidence, "geometry_by_id": {}, "task_purposes": purposes, "candidate_roster": roster, "assignment_rows": [], "source_artifact": "events.csv", "source_sha256": "a" * 64, "dependency_paths": [], "input_status": "formal"}
    assert replay_temporal_events(events, **kwargs) == replay_temporal_batches(events, **kwargs)[0]


def test_same_task_same_timestamp_cross_annotation_is_one_atomic_batch(tmp_path) -> None:
    events = [{"event_id": f"e{i}", "arrived_at": "2026-01-01T00:00:00Z", "arrival_order_source": "second_precision_export", "timestamp_precision": "second", "candidate_available_before_event": "true", "task_id": "shared", "base_task_id": "b", "condition": "manual", "canonical_annotation_id": f"a{i}", "worker_id": f"w{i}", "tag_family": "difficulty", "tag_name": "occlusion"} for i in (1, 2)]
    evidence, purposes, roster = _batch_inputs(events)
    fold = _fold_for_base("b", 2)
    event_rows, batches, tasks, _, contracts = replay_temporal_batches(events, policy_by_fold={fold: _policy(fold, tmp_path)}, evidence_by_id=evidence, geometry_by_id={}, task_purposes=purposes, candidate_roster=roster, assignment_rows=[], source_artifact="events.csv", source_sha256="a" * 64, dependency_paths=[], input_status="formal")
    assert len(batches) == 1 and len(tasks) == 1
    assert {row["pre_batch_snapshot_id"] for row in event_rows} == {event_rows[0]["pre_batch_snapshot_id"]}
    assert batches[0]["post_batch_k"] == 2
    assert contracts["batch_atomicity_valid"]["valid"] is True


def test_same_timestamp_different_task_does_not_merge(tmp_path) -> None:
    events = [{"event_id": f"e{i}", "arrived_at": "2026-01-01T00:00:00Z", "arrival_order_source": "second_precision_export", "timestamp_precision": "second", "candidate_available_before_event": "true", "task_id": "shared", "base_task_id": f"b{i}", "condition": "manual", "canonical_annotation_id": f"a{i}", "worker_id": f"w{i}", "tag_family": "difficulty", "tag_name": "occlusion"} for i in (1, 2)]
    evidence, purposes, roster = _batch_inputs(events)
    policies = {_fold_for_base(row["base_task_id"], 2): _policy(_fold_for_base(row["base_task_id"], 2), tmp_path) for row in events}
    _, batches, tasks, _, _ = replay_temporal_batches(events, policy_by_fold=policies, evidence_by_id=evidence, geometry_by_id={}, task_purposes=purposes, candidate_roster=roster, assignment_rows=[], source_artifact="events.csv", source_sha256="a" * 64, dependency_paths=[], input_status="formal")
    assert len(batches) == 2 and len(tasks) == 2


def test_equivalent_utc_offsets_share_one_atomic_batch(tmp_path) -> None:
    events = [
        {"event_id": "e1", "arrived_at": "2026-01-01T00:00:00Z", "arrival_order_source": "second_precision_export", "timestamp_precision": "second", "task_id": "t", "base_task_id": "b", "condition": "manual", "canonical_annotation_id": "a1", "worker_id": "w1", "tag_family": "difficulty", "tag_name": "occlusion"},
        {"event_id": "e2", "arrived_at": "2026-01-01T08:00:00+08:00", "arrival_order_source": "second_precision_export", "timestamp_precision": "second", "task_id": "t", "base_task_id": "b", "condition": "manual", "canonical_annotation_id": "a2", "worker_id": "w2", "tag_family": "difficulty", "tag_name": "occlusion"},
    ]
    evidence, purposes, roster = _batch_inputs(events)
    fold = _fold_for_base("b", 2)
    _, batches, _, _, _ = replay_temporal_batches(events, policy_by_fold={fold: _policy(fold, tmp_path)}, evidence_by_id=evidence, geometry_by_id={}, task_purposes=purposes, candidate_roster=roster, assignment_rows=[], source_artifact="events.csv", source_sha256="a" * 64, dependency_paths=[], input_status="formal")
    assert len(batches) == 1


def test_temporal_batch_contract_detects_event_coverage_gap(tmp_path) -> None:
    event = {"event_id": "e1", "arrived_at": "2026-01-01T00:00:00Z", "arrival_order_source": "second_precision_export", "timestamp_precision": "second", "candidate_available_before_event": "true", "task_id": "t", "base_task_id": "b", "condition": "manual", "canonical_annotation_id": "a1", "worker_id": "w1", "tag_family": "difficulty", "tag_name": "occlusion"}
    evidence, purposes, roster = _batch_inputs([event])
    evidence[("extra", "difficulty", "occlusion")] = dict(next(iter(evidence.values())))
    fold = _fold_for_base("b", 2)
    *_, contracts = replay_temporal_batches([event], policy_by_fold={fold: _policy(fold, tmp_path)}, evidence_by_id=evidence, geometry_by_id={}, task_purposes=purposes, candidate_roster=roster, assignment_rows=[], source_artifact="events.csv", source_sha256="a" * 64, dependency_paths=[], input_status="formal")
    assert contracts["event_coverage_complete"]["valid"] is False


def test_trusted_sequence_splits_same_timestamp_and_preserves_order(tmp_path) -> None:
    events = [{"event_id": f"e{i}", "arrived_at": "2026-01-01T00:00:00Z", "arrival_order_source": "server_receive_sequence", "timestamp_precision": "second", "trusted_sequence": str(i), "candidate_available_before_event": "true", "task_id": "t", "base_task_id": "b", "condition": "manual", "canonical_annotation_id": f"a{i}", "worker_id": f"w{i}", "tag_family": "difficulty", "tag_name": "occlusion"} for i in (1, 2)]
    evidence, purposes, roster = _batch_inputs(events)
    fold = _fold_for_base("b", 2)
    _, batches, _, _, contracts = replay_temporal_batches(events, policy_by_fold={fold: _policy(fold, tmp_path)}, evidence_by_id=evidence, geometry_by_id={}, task_purposes=purposes, candidate_roster=roster, assignment_rows=[], source_artifact="events.csv", source_sha256="a" * 64, dependency_paths=[], input_status="formal")
    assert [(row["pre_batch_k"], row["post_batch_k"]) for row in batches] == [(0, 1), (1, 2)]
    assert contracts["arrival_order_contract_valid"]["valid"] is True


def test_tied_batch_counts_full_cap_overshoot(tmp_path) -> None:
    events = [{"event_id": f"e{i}", "arrived_at": "2026-01-01T00:00:00Z", "arrival_order_source": "second_precision_export", "timestamp_precision": "second", "candidate_available_before_event": "true", "task_id": "t", "base_task_id": "b", "condition": "manual", "canonical_annotation_id": f"a{i}", "worker_id": f"w{i}", "tag_family": "difficulty", "tag_name": "occlusion"} for i in range(8)]
    evidence, purposes, roster = _batch_inputs(events)
    fold = _fold_for_base("b", 2)
    _, batches, _, _, _ = replay_temporal_batches(events, policy_by_fold={fold: _policy(fold, tmp_path)}, evidence_by_id=evidence, geometry_by_id={}, task_purposes=purposes, candidate_roster=roster, assignment_rows=[], source_artifact="events.csv", source_sha256="a" * 64, dependency_paths=[], input_status="formal")
    assert batches[0]["post_batch_k"] == 8
    assert batches[0]["standard_cap_overshoot_due_to_tie"] == 3
    assert batches[0]["escalation_cap_overshoot_due_to_tie"] == 1
    assert batches[0]["cap_overshoot_due_to_tie"] == 1


def test_scope_only_and_resolved_oos_do_not_require_geometry(tmp_path) -> None:
    events = [{"event_id": f"e{i}", "arrived_at": "2026-01-01T00:00:00Z", "arrival_order_source": "second_precision_export", "timestamp_precision": "second", "candidate_available_before_event": "true", "task_id": "t", "base_task_id": "b", "condition": "manual", "canonical_annotation_id": f"a{i}", "worker_id": f"w{i}", "tag_family": "difficulty", "tag_name": "occlusion"} for i in (1, 2)]
    evidence, purposes, roster = _batch_inputs(events)
    for row in evidence.values(): row["scope"] = "OOS"
    purposes[("b", "manual")].update(task_purpose="geometry_production", required_components={"scope", "geometry"})
    fold = _fold_for_base("b", 2)
    _, batches, _, _, _ = replay_temporal_batches(events, policy_by_fold={fold: _policy(fold, tmp_path)}, evidence_by_id=evidence, geometry_by_id={}, task_purposes=purposes, candidate_roster=roster, assignment_rows=[], source_artifact="events.csv", source_sha256="a" * 64, dependency_paths=[], input_status="formal")
    assert batches[0]["current_scope_state_after"] == "resolved_oos"
    assert batches[0]["geometry_consensus_required"] is False
    assert batches[0]["task_completion_status"] == "complete"


def test_unknown_risk_bucket_fails_closed(tmp_path) -> None:
    event = {"event_id": "e1", "arrived_at": "2026-01-01T00:00:00Z", "arrival_order_source": "second_precision_export", "timestamp_precision": "second", "candidate_available_before_event": "true", "task_id": "t", "base_task_id": "b", "condition": "manual", "canonical_annotation_id": "a1", "worker_id": "w1", "tag_family": "difficulty", "tag_name": "occlusion"}
    evidence, purposes, roster = _batch_inputs([event])
    fold = _fold_for_base("b", 2); policy = _policy(fold, tmp_path)
    artifact = Path(policy["policy_artifact_path"])
    payload = json.loads(artifact.read_text(encoding="utf-8")); payload["risk_bucket"] = "typo"; artifact.write_text(json.dumps(payload), encoding="utf-8")
    from tools.thesis_main.analysis.vfinal_artifact_utils import sha256_file
    policy["policy_artifact_sha256"] = sha256_file(artifact)
    with pytest.raises(ValueError, match="risk_bucket"):
        replay_temporal_batches([event], policy_by_fold={fold: policy}, evidence_by_id=evidence, geometry_by_id={}, task_purposes=purposes, candidate_roster=roster, assignment_rows=[], source_artifact="events.csv", source_sha256="a" * 64, dependency_paths=[], input_status="formal")


def test_materializer_writes_event_batch_task_and_sensitivity_artifacts(tmp_path) -> None:
    paths = _frozen_temporal_inputs(tmp_path)
    output = tmp_path / "routing_temporal_replay_C1.csv"
    summary = materialize_temporal_replay(paths["ledger"], output, policy_manifest=paths["policy_manifest"], canonical_csv=paths["canonical"], quality_csv=paths["quality"], three_state_csv=paths["three"], canonical_geometry_jsonl=paths["geometry"], task_purpose_manifest_csv=paths["purpose"], candidate_roster_manifest_csv=paths["roster"], assignment_history_csv=paths["history"], input_status="formal")
    assert summary["full_stop_contract_valid"] is True
    assert summary["n_batches"] == summary["n_tasks"] == 1
    assert all((tmp_path / name).exists() for name in ("routing_temporal_event_audit_C1.csv", "routing_temporal_batch_decisions_C1.csv", "routing_temporal_task_summary_C1.csv", "routing_temporal_order_sensitivity_C1.csv", "routing_temporal_contract_summary_C1.json"))
    contract = json.loads((tmp_path / "routing_temporal_contract_summary_C1.json").read_text(encoding="utf-8"))
    assert all(set(result) == {"valid", "checked_count", "failure_count", "failure_reasons", "evidence_artifact"} for result in contract["contract_results"].values())
    assert Path(contract["contract_results"]["task_purpose_manifest_valid"]["evidence_artifact"]) == paths["purpose"].resolve()
    assert Path(contract["contract_results"]["candidate_pool_binding_valid"]["evidence_artifact"]) == paths["roster"].resolve()
    assert Path(contract["contract_results"]["no_future_scope_leakage"]["evidence_artifact"]) == paths["history"].resolve()


def test_first_terminal_batch_freezes_task_state(tmp_path) -> None:
    events = [
        {"event_id": f"e{i}", "arrived_at": f"2026-01-01T00:0{i}:00Z", "arrival_order_source": "second_precision_export", "timestamp_precision": "second", "task_id": "t", "base_task_id": "b", "condition": "manual", "canonical_annotation_id": f"a{i}", "worker_id": f"w{i}", "tag_family": "difficulty", "tag_name": "occlusion"}
        for i in (1, 2, 3)
    ]
    evidence, purposes, roster = _batch_inputs(events)
    fold = _fold_for_base("b", 2)
    event_rows, batches, tasks, _, contracts = replay_temporal_batches(events, policy_by_fold={fold: _policy(fold, tmp_path)}, evidence_by_id=evidence, geometry_by_id={}, task_purposes=purposes, candidate_roster=roster, assignment_rows=[], source_artifact="events.csv", source_sha256="a" * 64, dependency_paths=[], input_status="formal")
    assert batches[1]["task_state_after"] == "COMPLETE"
    assert batches[2]["action"] == "post_terminal_audit_only"
    assert batches[2]["task_state_before"] == "COMPLETE"
    assert batches[2]["post_batch_k"] == 2
    assert next(row for row in event_rows if row["event_id"] == "e3")["post_terminal_audit_only"] is True
    assert tasks[0]["terminal_batch_id"] == batches[1]["event_batch_id"]
    assert contracts["task_completion_contract_valid"]["valid"] is True


def test_primary_k_and_tag_counts_use_unique_independent_workers(tmp_path) -> None:
    events = [
        {"event_id": f"e{i}", "arrived_at": "2026-01-01T00:00:00Z", "arrival_order_source": "second_precision_export", "timestamp_precision": "second", "task_id": "t", "base_task_id": "b", "condition": "manual", "canonical_annotation_id": f"a{i}", "worker_id": "w1", "tag_family": "difficulty", "tag_name": "occlusion"}
        for i in (1, 2)
    ]
    evidence, purposes, roster = _batch_inputs(events)
    fold = _fold_for_base("b", 2)
    _, batches, _, _, _ = replay_temporal_batches(events, policy_by_fold={fold: _policy(fold, tmp_path)}, evidence_by_id=evidence, geometry_by_id={}, task_purposes=purposes, candidate_roster=roster, assignment_rows=[], source_artifact="events.csv", source_sha256="a" * 64, dependency_paths=[], input_status="formal")
    assert batches[0]["post_batch_k"] <= 1
    tag = json.loads(batches[0]["family_evidence_status_json"])["difficulty/occlusion"]
    assert tag["a"] <= 1


def test_required_tag_cannot_be_satisfied_by_another_family_tag(tmp_path) -> None:
    events = [
        {"event_id": f"e{i}", "arrived_at": "2026-01-01T00:00:00Z", "arrival_order_source": "second_precision_export", "timestamp_precision": "second", "task_id": "t", "base_task_id": "b", "condition": "manual", "canonical_annotation_id": f"a{i}", "worker_id": f"w{i}", "tag_family": "difficulty", "tag_name": "occlusion"}
        for i in (1, 2)
    ]
    evidence, purposes, roster = _batch_inputs(events)
    purposes[("b", "manual")]["required_tags"] = {("difficulty", "reflection")}
    fold = _fold_for_base("b", 2)
    _, batches, _, _, _ = replay_temporal_batches(events, policy_by_fold={fold: _policy(fold, tmp_path)}, evidence_by_id=evidence, geometry_by_id={}, task_purposes=purposes, candidate_roster=roster, assignment_rows=[], source_artifact="events.csv", source_sha256="a" * 64, dependency_paths=[], input_status="formal")
    assert batches[0]["task_completion_status"] != "complete"


def test_contract_results_are_evidence_backed_records(tmp_path) -> None:
    event = {"event_id": "e1", "arrived_at": "2026-01-01T00:00:00Z", "arrival_order_source": "second_precision_export", "timestamp_precision": "second", "task_id": "t", "base_task_id": "b", "condition": "manual", "canonical_annotation_id": "a1", "worker_id": "w1", "tag_family": "difficulty", "tag_name": "occlusion"}
    evidence, purposes, roster = _batch_inputs([event])
    fold = _fold_for_base("b", 2)
    *_, contracts = replay_temporal_batches([event], policy_by_fold={fold: _policy(fold, tmp_path)}, evidence_by_id=evidence, geometry_by_id={}, task_purposes=purposes, candidate_roster=roster, assignment_rows=[], source_artifact="events.csv", source_sha256="a" * 64, dependency_paths=[], input_status="formal")
    for result in contracts.values():
        assert set(result) == {"valid", "checked_count", "failure_count", "failure_reasons", "evidence_artifact"}


def test_future_assignment_exclusion_does_not_rewrite_earlier_candidate_pool(tmp_path) -> None:
    event = {"event_id": "e1", "arrived_at": "2026-01-01T00:00:00Z", "arrival_order_source": "second_precision_export", "timestamp_precision": "second", "task_id": "t", "base_task_id": "b", "condition": "manual", "canonical_annotation_id": "a1", "worker_id": "w1", "tag_family": "difficulty", "tag_name": "occlusion"}
    evidence, purposes, roster = _batch_inputs([event])
    roster[("b", "manual")].add("spare")
    assignments = [{"base_task_id": "b", "condition": "manual", "worker_id": "spare", "assignment_status": "excluded", "effective_at": "2026-01-02T00:00:00Z"}]
    fold = _fold_for_base("b", 2)
    _, batches, _, _, _ = replay_temporal_batches([event], policy_by_fold={fold: _policy(fold, tmp_path)}, evidence_by_id=evidence, geometry_by_id={}, task_purposes=purposes, candidate_roster=roster, assignment_rows=assignments, source_artifact="events.csv", source_sha256="a" * 64, dependency_paths=[], input_status="formal")
    assert "spare" in json.loads(batches[0]["candidate_pool_before"])


def test_geometry_profile_eligibility_requires_valid_thresholded_geometry(tmp_path) -> None:
    events = [
        {"event_id": f"e{i}", "arrived_at": "2026-01-01T00:00:00Z", "arrival_order_source": "second_precision_export", "timestamp_precision": "second", "task_id": "t", "base_task_id": "b", "condition": "manual", "canonical_annotation_id": f"a{i}", "worker_id": f"w{i}", "tag_family": "difficulty", "tag_name": "occlusion"}
        for i in (1, 2)
    ]
    evidence, purposes, roster = _batch_inputs(events)
    purposes[("b", "manual")].update(task_purpose="geometry_production", required_components={"scope", "geometry"})
    fold = _fold_for_base("b", 2)
    _, batches, _, _, _ = replay_temporal_batches(events, policy_by_fold={fold: _policy(fold, tmp_path)}, evidence_by_id=evidence, geometry_by_id={}, task_purposes=purposes, candidate_roster=roster, assignment_rows=[], source_artifact="events.csv", source_sha256="a" * 64, dependency_paths=[], input_status="formal")
    assert batches[0]["geometry_profile_eligible"] is False


def test_same_annotation_multi_tag_is_one_worker_and_one_batch(tmp_path) -> None:
    events = [
        {"event_id": "e-d", "arrived_at": "2026-01-01T00:00:00Z", "arrival_order_source": "second_precision_export", "timestamp_precision": "second", "task_id": "t", "base_task_id": "b", "condition": "semi", "canonical_annotation_id": "a1", "worker_id": "w1", "tag_family": "difficulty", "tag_name": "occlusion"},
        {"event_id": "e-m", "arrived_at": "2026-01-01T00:00:00Z", "arrival_order_source": "second_precision_export", "timestamp_precision": "second", "task_id": "t", "base_task_id": "b", "condition": "semi", "canonical_annotation_id": "a1", "worker_id": "w1", "tag_family": "model_issue", "tag_name": "corner_drift"},
    ]
    evidence, purposes, roster = _batch_inputs(events)
    evidence[("a1", "model_issue", "corner_drift")]["assertion_source"] = "explicit_worker_label"
    fold = _fold_for_base("b", 2)
    event_rows, batches, _, _, contracts = replay_temporal_batches(events, policy_by_fold={fold: _policy(fold, tmp_path)}, evidence_by_id=evidence, geometry_by_id={}, task_purposes=purposes, candidate_roster=roster, assignment_rows=[], source_artifact="events.csv", source_sha256="a" * 64, dependency_paths=[], input_status="formal")
    assert len(batches) == 1 and batches[0]["post_batch_k"] == 1
    assert len({row["pre_batch_snapshot_id"] for row in event_rows}) == 1
    assert contracts["annotation_tag_atomicity_valid"]["valid"] is True


def test_same_annotation_different_trusted_sequence_fails_atomicity(tmp_path) -> None:
    events = [
        {"event_id": f"e{i}", "arrived_at": "2026-01-01T00:00:00Z", "arrival_order_source": "server_receive_sequence", "trusted_sequence": str(i), "timestamp_precision": "second", "task_id": "t", "base_task_id": "b", "condition": "manual", "canonical_annotation_id": "a1", "worker_id": "w1", "tag_family": "difficulty", "tag_name": tag}
        for i, tag in ((1, "occlusion"), (2, "reflection"))
    ]
    evidence, purposes, roster = _batch_inputs(events)
    fold = _fold_for_base("b", 2)
    rows, _, _, _, contracts = replay_temporal_batches(events, policy_by_fold={fold: _policy(fold, tmp_path)}, evidence_by_id=evidence, geometry_by_id={}, task_purposes=purposes, candidate_roster=roster, assignment_rows=[], source_artifact="events.csv", source_sha256="a" * 64, dependency_paths=[], input_status="formal")
    assert contracts["annotation_tag_atomicity_valid"]["valid"] is False
    assert all("annotation_atomicity_violation" in row["event_invalid_reason"] for row in rows)


def test_first_unresolved_batch_is_terminal_and_later_events_are_audit_only(tmp_path) -> None:
    events = [
        {"event_id": f"e{i}", "arrived_at": "2026-01-01T00:00:00Z" if i < 3 else "2026-01-01T00:01:00Z", "arrival_order_source": "second_precision_export", "timestamp_precision": "second", "task_id": "t", "base_task_id": "b", "condition": "manual", "canonical_annotation_id": f"a{i}", "worker_id": f"w{i}", "tag_family": "difficulty", "tag_name": "occlusion"}
        for i in (1, 2, 3)
    ]
    evidence, purposes, roster = _batch_inputs(events)
    fold = _fold_for_base("b", 2)
    policy = _policy(fold, tmp_path)
    artifact = Path(policy["policy_artifact_path"])
    payload = json.loads(artifact.read_text(encoding="utf-8")); payload.update(meta_min_same_state=3, escalation_cap=2, standard_cap=2, k_min_for_stop=2)
    artifact.write_text(json.dumps(payload), encoding="utf-8"); policy["policy_artifact_sha256"] = sha256_file(artifact)
    rows, batches, tasks, _, _ = replay_temporal_batches(events, policy_by_fold={fold: policy}, evidence_by_id=evidence, geometry_by_id={}, task_purposes=purposes, candidate_roster=roster, assignment_rows=[], source_artifact="events.csv", source_sha256="a" * 64, dependency_paths=[], input_status="formal")
    assert batches[0]["task_state_after"] == "UNRESOLVED"
    assert batches[1]["action"] == "post_terminal_audit_only" and batches[1]["post_batch_k"] == 2
    assert next(row for row in rows if row["event_id"] == "e3")["post_terminal_audit_only"] is True
    assert tasks[0]["terminal_batch_id"] == batches[0]["event_batch_id"]


def test_non_independent_event_stays_forensic_and_never_increments_k(tmp_path) -> None:
    event = {"event_id": "e1", "arrived_at": "2026-01-01T00:00:00Z", "arrival_order_source": "second_precision_export", "timestamp_precision": "second", "task_id": "t", "base_task_id": "b", "condition": "manual", "canonical_annotation_id": "a1", "worker_id": "w1", "tag_family": "difficulty", "tag_name": "occlusion"}
    evidence, purposes, roster = _batch_inputs([event])
    evidence[("a1", "difficulty", "occlusion")]["independence_status"] = "non_independent_confirmed"
    fold = _fold_for_base("b", 2)
    rows, batches, _, _, _ = replay_temporal_batches([event], policy_by_fold={fold: _policy(fold, tmp_path)}, evidence_by_id=evidence, geometry_by_id={}, task_purposes=purposes, candidate_roster=roster, assignment_rows=[], source_artifact="events.csv", source_sha256="a" * 64, dependency_paths=[], input_status="formal")
    assert batches[0]["post_batch_k"] == 0
    assert rows[0]["primary_evidence_included"] is False
    assert rows[0]["event_validity_status"] == "valid"
    assert "ineligible_independent_evidence" in rows[0]["forensic_only_reason"]


def test_scope_only_uses_eligible_annotation_arrival_even_when_tag_assertions_are_na(tmp_path) -> None:
    events = [{"event_id": f"e{i}", "arrived_at": "2026-01-01T00:00:00Z", "arrival_order_source": "second_precision_export", "timestamp_precision": "second", "task_id": "t", "base_task_id": "b", "condition": "manual", "canonical_annotation_id": f"a{i}", "worker_id": f"w{i}", "tag_family": "difficulty", "tag_name": "occlusion"} for i in (1, 2)]
    evidence, purposes, roster = _batch_inputs(events)
    purposes[("b", "manual")].update(task_purpose="scope_only", required_components={"scope"}, required_tags=set())
    for row in evidence.values():
        row["assertion"] = "NA"
        row["scope"] = "OOS"
    fold = _fold_for_base("b", 2)
    rows, batches, _, _, _ = replay_temporal_batches(events, policy_by_fold={fold: _policy(fold, tmp_path)}, evidence_by_id=evidence, geometry_by_id={}, task_purposes=purposes, candidate_roster=roster, assignment_rows=[], source_artifact="events.csv", source_sha256="a" * 64, dependency_paths=[], input_status="formal")
    assert all(row["event_validity_status"] == "valid" for row in rows)
    assert batches[0]["post_batch_k"] == 2
    assert batches[0]["current_scope_state_after"] == "resolved_oos"
    assert batches[0]["task_state_after"] == "COMPLETE"


def test_policy_threshold_change_changes_task_decision(tmp_path) -> None:
    events = [{"event_id": f"e{i}", "arrived_at": "2026-01-01T00:00:00Z", "arrival_order_source": "second_precision_export", "timestamp_precision": "second", "task_id": "t", "base_task_id": "b", "condition": "manual", "canonical_annotation_id": f"a{i}", "worker_id": f"w{i}", "tag_family": "difficulty", "tag_name": "occlusion"} for i in (1, 2)]
    evidence, purposes, roster = _batch_inputs(events)
    fold = _fold_for_base("b", 2)
    low_dir = tmp_path / "low"; low_dir.mkdir()
    low = _policy(fold, low_dir)
    low_action = replay_temporal_batches(events, policy_by_fold={fold: low}, evidence_by_id=evidence, geometry_by_id={}, task_purposes=purposes, candidate_roster=roster, assignment_rows=[], source_artifact="events.csv", source_sha256="a" * 64, dependency_paths=[], input_status="formal")[1][0]["action"]
    high_dir = tmp_path / "high"; high_dir.mkdir()
    high = _policy(fold, high_dir); artifact = Path(high["policy_artifact_path"]); payload = json.loads(artifact.read_text(encoding="utf-8")); payload["meta_min_same_state"] = 3; artifact.write_text(json.dumps(payload), encoding="utf-8"); high["policy_artifact_sha256"] = sha256_file(artifact)
    high_action = replay_temporal_batches(events, policy_by_fold={fold: high}, evidence_by_id=evidence, geometry_by_id={}, task_purposes=purposes, candidate_roster=roster, assignment_rows=[], source_artifact="events.csv", source_sha256="a" * 64, dependency_paths=[], input_status="formal")[1][0]["action"]
    assert (low_action, high_action) == ("stop_candidate", "unresolved_candidate")


def test_standard_cap_changes_candidate_action_before_escalation_cap(tmp_path) -> None:
    events = [{"event_id": f"e{i}", "arrived_at": "2026-01-01T00:00:00Z", "arrival_order_source": "second_precision_export", "timestamp_precision": "second", "task_id": "t", "base_task_id": "b", "condition": "manual", "canonical_annotation_id": f"a{i}", "worker_id": f"w{i}", "tag_family": "difficulty", "tag_name": "occlusion"} for i in (1, 2)]
    evidence, purposes, roster = _batch_inputs(events)
    purposes[("b", "manual")]["required_tags"] = {("difficulty", "reflection")}
    roster[("b", "manual")].add("spare")
    fold = _fold_for_base("b", 2)
    policy = _policy(fold, tmp_path)
    before = replay_temporal_batches(events, policy_by_fold={fold: policy}, evidence_by_id=evidence, geometry_by_id={}, task_purposes=purposes, candidate_roster=roster, assignment_rows=[], source_artifact="events.csv", source_sha256="a" * 64, dependency_paths=[], input_status="formal")[1][0]
    artifact = Path(policy["policy_artifact_path"])
    payload = json.loads(artifact.read_text(encoding="utf-8"))
    payload["standard_cap"] = 2
    artifact.write_text(json.dumps(payload), encoding="utf-8")
    policy["policy_artifact_sha256"] = sha256_file(artifact)
    after = replay_temporal_batches(events, policy_by_fold={fold: policy}, evidence_by_id=evidence, geometry_by_id={}, task_purposes=purposes, candidate_roster=roster, assignment_rows=[], source_artifact="events.csv", source_sha256="a" * 64, dependency_paths=[], input_status="formal")[1][0]
    assert before["action"] == "continue_standard_candidate"
    assert after["action"] == "escalate_candidate"


def test_geometry_production_requires_both_valid_channels(tmp_path) -> None:
    events = [{"event_id": f"e{i}", "arrived_at": "2026-01-01T00:00:00Z", "arrival_order_source": "second_precision_export", "timestamp_precision": "second", "task_id": "t", "base_task_id": "b", "condition": "manual", "canonical_annotation_id": f"a{i}", "worker_id": f"w{i}", "tag_family": "difficulty", "tag_name": "occlusion"} for i in (1, 2)]
    evidence, purposes, roster = _batch_inputs(events)
    purposes[("b", "manual")].update(task_purpose="geometry_production", required_components={"scope", "geometry"})
    geometry = {f"a{i}": normalize_geometry([[100, 100], [100, 400], [500, 100], [500, 400]]) for i in (1, 2)}
    fold = _fold_for_base("b", 2)
    _, batches, _, _, _ = replay_temporal_batches(events, policy_by_fold={fold: _policy(fold, tmp_path)}, evidence_by_id=evidence, geometry_by_id=geometry, task_purposes=purposes, candidate_roster=roster, assignment_rows=[], source_artifact="events.csv", source_sha256="a" * 64, dependency_paths=[], input_status="formal")
    assert batches[0]["geometry_status"] == "evaluable"
    assert batches[0]["geometry_threshold_passed"] is True
    assert batches[0]["geometry_profile_eligible"] is True
    assert batches[0]["task_state_after"] == "COMPLETE"


def test_model_issue_recognition_uses_provenance_but_not_geometry(tmp_path) -> None:
    events = [{"event_id": f"e{i}", "arrived_at": "2026-01-01T00:00:00Z", "arrival_order_source": "second_precision_export", "timestamp_precision": "second", "task_id": "t", "base_task_id": "b", "condition": "semi", "canonical_annotation_id": f"a{i}", "worker_id": f"w{i}", "tag_family": "model_issue", "tag_name": "corner_drift"} for i in (1, 2)]
    evidence, purposes, roster = _batch_inputs(events)
    purposes[("b", "semi")].update(required_components={"model_issue_recognition"}, required_tags={("model_issue", "corner_drift")})
    for row in evidence.values(): row["assertion_source"] = "explicit_worker_label"
    fold = _fold_for_base("b", 2)
    _, batches, _, _, _ = replay_temporal_batches(events, policy_by_fold={fold: _policy(fold, tmp_path)}, evidence_by_id=evidence, geometry_by_id={}, task_purposes=purposes, candidate_roster=roster, assignment_rows=[], source_artifact="events.csv", source_sha256="a" * 64, dependency_paths=[], input_status="formal")
    assert batches[0]["task_state_after"] == "COMPLETE"
    assert batches[0]["geometry_consensus_required"] is False


def test_model_issue_recognition_rejects_missing_provenance(tmp_path) -> None:
    events = [{"event_id": f"e{i}", "arrived_at": "2026-01-01T00:00:00Z", "arrival_order_source": "second_precision_export", "timestamp_precision": "second", "task_id": "t", "base_task_id": "b", "condition": "semi", "canonical_annotation_id": f"a{i}", "worker_id": f"w{i}", "tag_family": "model_issue", "tag_name": "corner_drift"} for i in (1, 2)]
    evidence, purposes, roster = _batch_inputs(events)
    purposes[("b", "semi")].update(required_components={"model_issue_recognition"}, required_tags={("model_issue", "corner_drift")})
    fold = _fold_for_base("b", 2)
    rows, batches, _, _, _ = replay_temporal_batches(events, policy_by_fold={fold: _policy(fold, tmp_path)}, evidence_by_id=evidence, geometry_by_id={}, task_purposes=purposes, candidate_roster=roster, assignment_rows=[], source_artifact="events.csv", source_sha256="a" * 64, dependency_paths=[], input_status="formal")
    assert all("model_issue_provenance_invalid" in row["forensic_only_reason"] for row in rows)
    assert all(row["tag_state_included"] is False for row in rows)
    assert batches[0]["task_state_after"] != "COMPLETE"


def test_invalid_model_tag_does_not_pollute_same_annotation_difficulty_tag(tmp_path) -> None:
    events = []
    for index in (1, 2):
        common = {"arrived_at": "2026-01-01T00:00:00Z", "arrival_order_source": "second_precision_export", "timestamp_precision": "second", "task_id": "t", "base_task_id": "b", "condition": "semi", "canonical_annotation_id": f"a{index}", "worker_id": f"w{index}"}
        events.extend([
            {**common, "event_id": f"d{index}", "tag_family": "difficulty", "tag_name": "occlusion"},
            {**common, "event_id": f"m{index}", "tag_family": "model_issue", "tag_name": "corner_drift"},
        ])
    evidence, purposes, roster = _batch_inputs(events)
    purposes[("b", "semi")].update(required_components={"difficulty", "model_issue_recognition"}, required_tags={("difficulty", "occlusion"), ("model_issue", "corner_drift")})
    fold = _fold_for_base("b", 2)
    rows, batches, _, _, _ = replay_temporal_batches(events, policy_by_fold={fold: _policy(fold, tmp_path)}, evidence_by_id=evidence, geometry_by_id={}, task_purposes=purposes, candidate_roster=roster, assignment_rows=[], source_artifact="events.csv", source_sha256="a" * 64, dependency_paths=[], input_status="formal")
    states = json.loads(batches[0]["family_evidence_status_json"])
    assert states["difficulty/occlusion"]["a"] == 2
    assert states["difficulty/occlusion"]["complete"] is True
    assert states["model_issue/corner_drift"]["k"] == 0
    assert all(row["tag_state_included"] is False for row in rows if row["tag_family"] == "model_issue")


def test_event_ledger_requires_frozen_independence_identity(tmp_path) -> None:
    paths = _frozen_temporal_inputs(tmp_path)
    quality = list(csv.DictReader(paths["quality"].open(encoding="utf-8")))
    quality[0]["independence_audit_identity"] = ""
    _write_csv(paths["quality"], quality)
    with pytest.raises(ValueError, match="independence audit identity"):
        build_temporal_event_ledger(paths["canonical"], paths["quality"], paths["three"], tmp_path / "bad-ledger.csv")


def test_event_ledger_preserves_na_and_forensic_three_state_rows(tmp_path) -> None:
    paths = _frozen_temporal_inputs(tmp_path)
    quality = list(csv.DictReader(paths["quality"].open(encoding="utf-8")))
    quality[0]["canonical_eligibility_status"] = "excluded"
    quality[0]["independence_status"] = "non_independent_confirmed"
    _write_csv(paths["quality"], quality)
    observations = list(csv.DictReader(paths["three"].open(encoding="utf-8")))
    observations[1]["assertion"] = "NA"
    _write_csv(paths["three"], observations)
    ledger = tmp_path / "complete-ledger.csv"
    summary = build_temporal_event_ledger(paths["canonical"], paths["quality"], paths["three"], ledger)
    assert summary["n_events"] == len(observations) == 2


def test_event_ledger_preserves_millisecond_timestamp_precision(tmp_path) -> None:
    paths = _frozen_temporal_inputs(tmp_path)
    quality = list(csv.DictReader(paths["quality"].open(encoding="utf-8")))
    for row in quality:
        row["arrived_at"] = "2026-01-01T00:00:00.123Z"
    _write_csv(paths["quality"], quality)
    ledger = tmp_path / "millisecond-ledger.csv"
    build_temporal_event_ledger(paths["canonical"], paths["quality"], paths["three"], ledger)
    assert {row["timestamp_precision"] for row in csv.DictReader(ledger.open(encoding="utf-8"))} == {"millisecond"}


def test_declared_timestamp_precision_must_match_timestamp(tmp_path) -> None:
    event = {"event_id": "e1", "arrived_at": "2026-01-01T00:00:00.123Z", "arrival_order_source": "second_precision_export", "timestamp_precision": "second", "task_id": "t", "base_task_id": "b", "condition": "manual", "canonical_annotation_id": "a1", "worker_id": "w1", "tag_family": "difficulty", "tag_name": "occlusion"}
    evidence, purposes, roster = _batch_inputs([event])
    fold = _fold_for_base("b", 2)
    traces, _, _, _, contracts = replay_temporal_batches([event], policy_by_fold={fold: _policy(fold, tmp_path)}, evidence_by_id=evidence, geometry_by_id={}, task_purposes=purposes, candidate_roster=roster, assignment_rows=[], source_artifact="events.csv", source_sha256="a" * 64, dependency_paths=[], input_status="formal")
    assert traces[0]["event_validity_status"] == "invalid"
    assert contracts["arrival_order_contract_valid"]["failure_reasons"]["timestamp_precision_mismatch"] == 1


def test_trusted_sequence_must_be_numeric(tmp_path) -> None:
    event = {"event_id": "e1", "arrived_at": "2026-01-01T00:00:00Z", "arrival_order_source": "server_receive_sequence", "trusted_sequence": "later", "timestamp_precision": "second", "task_id": "t", "base_task_id": "b", "condition": "manual", "canonical_annotation_id": "a1", "worker_id": "w1", "tag_family": "difficulty", "tag_name": "occlusion"}
    evidence, purposes, roster = _batch_inputs([event])
    fold = _fold_for_base("b", 2)
    traces, _, _, _, contracts = replay_temporal_batches([event], policy_by_fold={fold: _policy(fold, tmp_path)}, evidence_by_id=evidence, geometry_by_id={}, task_purposes=purposes, candidate_roster=roster, assignment_rows=[], source_artifact="events.csv", source_sha256="a" * 64, dependency_paths=[], input_status="formal")
    assert traces[0]["event_validity_status"] == "invalid"
    assert contracts["arrival_order_contract_valid"]["failure_reasons"]["trusted_source_sequence_not_numeric"] == 1


def test_model_issue_correction_requires_complete_evidence_not_one_boolean(tmp_path) -> None:
    events = [{"event_id": f"e{i}", "arrived_at": "2026-01-01T00:00:00Z", "arrival_order_source": "second_precision_export", "timestamp_precision": "second", "task_id": "t", "base_task_id": "b", "condition": "semi", "canonical_annotation_id": f"a{i}", "worker_id": f"w{i}", "tag_family": "difficulty", "tag_name": "occlusion"} for i in (1, 2)]
    evidence, purposes, roster = _batch_inputs(events)
    purposes[("b", "semi")].update(required_components={"model_issue_correction"}, required_tags=set())
    for row in evidence.values():
        row.update(effective_provenance_status="complete", prediction_selection_status="selected_unique", geometry_valid="true", semi_geometry_correction_evaluable="true", semi_evidence_status="complete", semi_response_type="successful_correction", semi_correction_failure_observed="false", geometry_reference_status="expert_hard_single")
    geometry = {f"a{i}": normalize_geometry([[100, 100], [100, 400], [500, 100], [500, 400]]) for i in (1, 2)}
    fold = _fold_for_base("b", 2)
    _, good, _, _, _ = replay_temporal_batches(events, policy_by_fold={fold: _policy(fold, tmp_path)}, evidence_by_id=evidence, geometry_by_id=geometry, task_purposes=purposes, candidate_roster=roster, assignment_rows=[], source_artifact="events.csv", source_sha256="a" * 64, dependency_paths=[], input_status="formal")
    evidence[("a2", "difficulty", "occlusion")]["geometry_reference_status"] = ""
    _, bad, _, _, _ = replay_temporal_batches(events, policy_by_fold={fold: _policy(fold, tmp_path)}, evidence_by_id=evidence, geometry_by_id=geometry, task_purposes=purposes, candidate_roster=roster, assignment_rows=[], source_artifact="events.csv", source_sha256="a" * 64, dependency_paths=[], input_status="formal")
    assert good[0]["task_state_after"] == "COMPLETE"
    assert bad[0]["task_state_after"] != "COMPLETE"


def test_used_worker_is_removed_from_next_candidate_pool(tmp_path) -> None:
    events = [{"event_id": f"e{i}", "arrived_at": f"2026-01-01T00:0{i}:00Z", "arrival_order_source": "second_precision_export", "timestamp_precision": "second", "task_id": "t", "base_task_id": "b", "condition": "manual", "canonical_annotation_id": f"a{i}", "worker_id": f"w{i}", "tag_family": "difficulty", "tag_name": "occlusion"} for i in (1, 2)]
    evidence, purposes, roster = _batch_inputs(events); roster[("b", "manual")].add("spare")
    fold = _fold_for_base("b", 2)
    _, batches, _, _, _ = replay_temporal_batches(events, policy_by_fold={fold: _policy(fold, tmp_path)}, evidence_by_id=evidence, geometry_by_id={}, task_purposes=purposes, candidate_roster=roster, assignment_rows=[], source_artifact="events.csv", source_sha256="a" * 64, dependency_paths=[], input_status="formal")
    assert "w1" not in json.loads(batches[1]["candidate_pool_before"])


@pytest.mark.parametrize("tamper", ["admission", "canonical", "tag_policy", "purpose_version", "roster_version"])
def test_frozen_dependency_tampering_fails_formal_replay(tmp_path, tamper) -> None:
    paths = _frozen_temporal_inputs(tmp_path)
    if tamper == "admission":
        (tmp_path / "p1_admission_frozen.csv").write_text("tampered", encoding="utf-8")
    elif tamper == "canonical":
        paths["canonical"].write_text("tampered", encoding="utf-8")
    elif tamper == "purpose_version":
        rows = list(csv.DictReader(paths["purpose"].open(encoding="utf-8")))
        rows[0]["manifest_version"] = "unknown"
        _write_csv(paths["purpose"], rows)
    elif tamper == "roster_version":
        rows = list(csv.DictReader(paths["roster"].open(encoding="utf-8")))
        rows[0]["manifest_version"] = "unknown"
        _write_csv(paths["roster"], rows)
    else:
        (tmp_path / "tag_policy.json").write_text("{}", encoding="utf-8")
    summary = materialize_temporal_replay(paths["ledger"], tmp_path / "routing_temporal_replay_C1.csv", policy_manifest=paths["policy_manifest"], canonical_csv=paths["canonical"], quality_csv=paths["quality"], three_state_csv=paths["three"], canonical_geometry_jsonl=paths["geometry"], task_purpose_manifest_csv=paths["purpose"], candidate_roster_manifest_csv=paths["roster"], assignment_history_csv=paths["history"], input_status="formal")
    assert summary["full_stop_contract_valid"] is False
    assert summary["status"] == "not_evaluable_missing_frozen_dependency"


def test_order_sensitivity_is_fixed_and_does_not_replace_primary(tmp_path) -> None:
    events = [{"event_id": f"e{i}", "arrived_at": "2026-01-01T00:00:00Z", "arrival_order_source": "second_precision_export", "timestamp_precision": "second", "task_id": "t", "base_task_id": "b", "condition": "manual", "canonical_annotation_id": f"a{i}", "worker_id": f"w{i}", "tag_family": "difficulty", "tag_name": "occlusion"} for i in (1, 2, 3)]
    evidence, purposes, roster = _batch_inputs(events)
    fold = _fold_for_base("b", 2)
    _, batches, _, sensitivity, _ = replay_temporal_batches(events, policy_by_fold={fold: _policy(fold, tmp_path)}, evidence_by_id=evidence, geometry_by_id={}, task_purposes=purposes, candidate_roster=roster, assignment_rows=[], source_artifact="events.csv", source_sha256="a" * 64, dependency_paths=[], input_status="formal")
    assert sensitivity[0]["random_seed"] == 20260714 and sensitivity[0]["random_permutations"] == 100
    assert sensitivity[0]["primary_k_used"] == batches[0]["post_batch_k"] == 3
