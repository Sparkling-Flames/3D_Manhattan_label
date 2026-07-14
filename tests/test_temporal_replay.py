import json
import csv
from pathlib import Path

import pytest

from tools.thesis_main.analysis.geometry_consensus.representation import normalize_geometry
from tools.thesis_main.analysis.routing.temporal_replay import _fold_for_base, materialize_temporal_replay, replay_temporal_batches, replay_temporal_events


def _policy(eval_fold: int, tmp_path) -> dict:
    fit_base = next(f"fit-{index}" for index in range(100) if _fold_for_base(f"fit-{index}", 2) != eval_fold)
    artifact = tmp_path / f"policy-{eval_fold}.json"
    artifact.write_text('{"meta_min_same_state": 2, "meta_max_opposition": 0, "max_unasserted_rate": 0.25, "min_q_boundary": 0.8, "min_q_wallwall": 0.8, "risk_bucket": "low_risk", "trusted_order_sources": ["server_receive_sequence"]}', encoding="utf-8")
    from tools.thesis_main.analysis.vfinal_artifact_utils import sha256_file
    return {"policy_artifact_id": f"policy-{eval_fold}", "policy_artifact_path": str(artifact), "policy_artifact_sha256": sha256_file(artifact), "rule_version": "test-policy-v1", "fit_folds": [1 - eval_fold], "fit_base_task_ids": [fit_base]}


def test_temporal_replay_uses_only_prior_arrivals_and_base_folds(tmp_path) -> None:
    events = [
        {"event_id": "e2", "arrived_at": "2026-01-01T00:02:00Z", "task_id": "t2", "base_task_id": "b", "canonical_annotation_id": "a2", "worker_id": "w2", "condition": "semi", "tag_family": "difficulty", "tag_name": "occlusion", "candidate_available_before_event": "true"},
        {"event_id": "e1", "arrived_at": "2026-01-01T00:01:00Z", "task_id": "t1", "base_task_id": "b", "canonical_annotation_id": "a1", "worker_id": "w1", "condition": "semi", "tag_family": "difficulty", "tag_name": "occlusion", "candidate_available_before_event": "true"},
    ]
    evidence = {(event["canonical_annotation_id"], event["tag_family"], event["tag_name"]): {**event, "canonical_eligibility_status": "valid", "independence_status": "independent", "assigned_expected": "true", "outside_assignment_submission": "false", "duplicate_worker_task_submission": "false", "schema_interpretable": "true", "assertion": "+"} for event in events}
    fold = _fold_for_base("b", 2)
    rows = replay_temporal_events(events, policy_by_fold={fold: _policy(fold, tmp_path)}, evidence_by_id=evidence)
    assert [row["prior_legal_arrivals"] for row in rows] == [0, 1]
    assert [row["a"] for row in rows] == [0, 1]
    assert {row["crossfit_fold"] for row in rows} == {rows[0]["crossfit_fold"]}
    assert all(row["policy_fit_excludes_fold"] is True for row in rows)


def test_temporal_replay_rejects_missing_arrival_metadata(tmp_path) -> None:
    with pytest.raises(ValueError, match="event_id"):
        replay_temporal_events([{"task_id": "t", "base_task_id": "b"}], policy_by_fold={_fold_for_base("b", 2): _policy(_fold_for_base("b", 2), tmp_path)})


def test_temporal_replay_preserves_worker_identity_prior_state_and_utc_order(tmp_path) -> None:
    events = [
        {"event_id": "e3", "arrived_at": "2026-01-01T03:00:00+03:00", "task_id": "t3", "base_task_id": "b3", "canonical_annotation_id": "a3", "worker_id": "w3", "condition": "manual", "tag_family": "difficulty", "tag_name": "occlusion", "candidate_available_before_event": "true"},
        {"event_id": "e1", "arrived_at": "2026-01-01T00:00:00Z", "task_id": "t1", "base_task_id": "b3", "canonical_annotation_id": "a1", "worker_id": "w1", "condition": "manual", "tag_family": "difficulty", "tag_name": "occlusion", "candidate_available_before_event": "true"},
        {"event_id": "e2", "arrived_at": "2026-01-01T01:00:00+01:00", "task_id": "t2", "base_task_id": "b3", "canonical_annotation_id": "a2", "worker_id": "w2", "condition": "manual", "tag_family": "difficulty", "tag_name": "occlusion", "candidate_available_before_event": "true"},
    ]
    assertions = {"a1": "+", "a2": "-", "a3": "0"}
    evidence = {
        (event["canonical_annotation_id"], event["tag_family"], event["tag_name"]): {
            **event, "arrived_at": event["arrived_at"], "canonical_eligibility_status": "valid", "independence_status": "independent", "assigned_expected": "true", "outside_assignment_submission": "false", "duplicate_worker_task_submission": "false", "schema_interpretable": "true", "assertion": assertions[event["canonical_annotation_id"]],
        }
        for event in events
    }
    fold = _fold_for_base("b3", 2)
    rows = replay_temporal_events(events, policy_by_fold={fold: _policy(fold, tmp_path)}, evidence_by_id=evidence)
    assert [row["event_id"] for row in rows] == ["e1", "e2", "e3"]
    assert [row["candidate_worker_id"] for row in rows] == ["w1", "w2", "w3"]
    assert rows[0]["arrived_at_utc"] == "2026-01-01T00:00:00+00:00"
    assert all(row["event_legal"] == "true" for row in rows)
    assert rows[0]["assertion"] == "+"
    assert rows[2]["prior_eligible_workers_json"] == '["w1", "w2"]'
    assert (rows[2]["a"], rows[2]["e"], rows[2]["u"]) == (1, 1, 0)
    assert rows[2]["action"] == "escalate_candidate"


def test_temporal_replay_keeps_tags_separate_and_batches_same_annotation(tmp_path) -> None:
    events = [
        {"event_id": "e1a", "arrived_at": "2026-01-01T00:00:00Z", "base_task_id": "b", "canonical_annotation_id": "a1", "worker_id": "w1", "condition": "semi", "tag_family": "difficulty", "tag_name": "occlusion", "candidate_available_before_event": "true"},
        {"event_id": "e1b", "arrived_at": "2026-01-01T00:00:00Z", "base_task_id": "b", "canonical_annotation_id": "a1", "worker_id": "w1", "condition": "semi", "tag_family": "model_issue", "tag_name": "corner_drift", "candidate_available_before_event": "true"},
        {"event_id": "e2", "arrived_at": "2026-01-01T00:01:00Z", "base_task_id": "b", "canonical_annotation_id": "a2", "worker_id": "w2", "condition": "semi", "tag_family": "difficulty", "tag_name": "occlusion", "candidate_available_before_event": "true"},
    ]
    evidence = {(row["canonical_annotation_id"], row["tag_family"], row["tag_name"]): {**row, "canonical_eligibility_status": "valid", "independence_status": "independent", "assigned_expected": "true", "outside_assignment_submission": "false", "duplicate_worker_task_submission": "false", "schema_interpretable": "true", "assertion": "+", "assertion_source": "explicit_worker_label"} for row in events}
    fold = _fold_for_base("b", 2)
    rows = replay_temporal_events(events, policy_by_fold={fold: _policy(fold, tmp_path)}, evidence_by_id=evidence)
    assert [rows[0]["prior_legal_arrivals"], rows[1]["prior_legal_arrivals"]] == [0, 0]
    assert rows[2]["prior_legal_arrivals"] == 1
    assert rows[1]["a"] == 0


def test_temporal_replay_marks_missing_candidate_binding_illegal(tmp_path) -> None:
    event = {"event_id": "e1", "arrived_at": "2026-01-01T00:00:00Z", "base_task_id": "b", "canonical_annotation_id": "a1", "worker_id": "w1", "condition": "manual", "tag_family": "difficulty", "tag_name": "occlusion"}
    evidence = {("a1", "difficulty", "occlusion"): {**event, "canonical_eligibility_status": "valid", "independence_status": "independent", "assigned_expected": "true", "outside_assignment_submission": "false", "duplicate_worker_task_submission": "false", "schema_interpretable": "true", "assertion": "+"}}
    fold = _fold_for_base("b", 2)
    row = replay_temporal_events([event], policy_by_fold={fold: _policy(fold, tmp_path)}, evidence_by_id=evidence)[0]
    assert row["event_legal"] == "false"
    assert "invalid_candidate_available_before_event" in row["event_legal_reason"]


def test_temporal_replay_stop_uses_prior_geometry_channels(tmp_path) -> None:
    events = [{"event_id": f"e{i}", "arrived_at": f"2026-01-01T00:0{i}:00Z", "base_task_id": "b", "canonical_annotation_id": f"a{i}", "worker_id": f"w{i}", "condition": "manual", "tag_family": "difficulty", "tag_name": "occlusion", "candidate_available_before_event": "true"} for i in (1, 2, 3)]
    evidence = {(row["canonical_annotation_id"], "difficulty", "occlusion"): {**row, "canonical_eligibility_status": "valid", "independence_status": "independent", "assigned_expected": "true", "outside_assignment_submission": "false", "duplicate_worker_task_submission": "false", "schema_interpretable": "true", "assertion": "+"} for row in events}
    geometry = {row["canonical_annotation_id"]: normalize_geometry([[100, 100], [100, 400], [500, 100], [500, 400]]) for row in events}
    fold = _fold_for_base("b", 2)
    rows = replay_temporal_events(events, policy_by_fold={fold: _policy(fold, tmp_path)}, evidence_by_id=evidence, geometry_by_id=geometry)
    assert rows[2]["geometry_status"] == "evaluable"
    assert rows[2]["geometry_support"] == 2
    assert rows[2]["action"] == "stop_candidate"


def _batch_inputs(events):
    evidence = {(row["canonical_annotation_id"], row["tag_family"], row["tag_name"]): {**row, "scope": "In-scope", "canonical_eligibility_status": "valid", "independence_status": "independent", "assigned_expected": "true", "outside_assignment_submission": "false", "duplicate_worker_task_submission": "false", "schema_interpretable": "true", "assertion": "+", "semi_geometry_correction_evaluable": "false"} for row in events}
    purposes = {(row["base_task_id"], row["condition"]): {"task_id": row.get("task_id", "t"), "task_purpose": "meta_label_only", "required_components": {"difficulty"}} for row in events}
    roster = {(row["base_task_id"], row["condition"]): {item["worker_id"] for item in events if item["base_task_id"] == row["base_task_id"] and item["condition"] == row["condition"]} for row in events}
    return evidence, purposes, roster


def test_same_task_same_timestamp_cross_annotation_is_one_atomic_batch(tmp_path) -> None:
    events = [{"event_id": f"e{i}", "arrived_at": "2026-01-01T00:00:00Z", "arrival_order_source": "second_precision_export", "timestamp_precision": "second", "candidate_available_before_event": "true", "task_id": "shared", "base_task_id": "b", "condition": "manual", "canonical_annotation_id": f"a{i}", "worker_id": f"w{i}", "tag_family": "difficulty", "tag_name": "occlusion"} for i in (1, 2)]
    evidence, purposes, roster = _batch_inputs(events)
    fold = _fold_for_base("b", 2)
    event_rows, batches, tasks, _, contracts = replay_temporal_batches(events, policy_by_fold={fold: _policy(fold, tmp_path)}, evidence_by_id=evidence, geometry_by_id={}, task_purposes=purposes, candidate_roster=roster, assignment_rows=[], source_artifact="events.csv", source_sha256="a" * 64, dependency_paths=[], input_status="formal")
    assert len(batches) == 1 and len(tasks) == 1
    assert {row["pre_batch_snapshot_id"] for row in event_rows} == {event_rows[0]["pre_batch_snapshot_id"]}
    assert batches[0]["post_batch_k"] == 2
    assert contracts["batch_atomicity_valid"] is True


def test_same_timestamp_different_task_does_not_merge(tmp_path) -> None:
    events = [{"event_id": f"e{i}", "arrived_at": "2026-01-01T00:00:00Z", "arrival_order_source": "second_precision_export", "timestamp_precision": "second", "candidate_available_before_event": "true", "task_id": "shared", "base_task_id": f"b{i}", "condition": "manual", "canonical_annotation_id": f"a{i}", "worker_id": f"w{i}", "tag_family": "difficulty", "tag_name": "occlusion"} for i in (1, 2)]
    evidence, purposes, roster = _batch_inputs(events)
    policies = {_fold_for_base(row["base_task_id"], 2): _policy(_fold_for_base(row["base_task_id"], 2), tmp_path) for row in events}
    _, batches, tasks, _, _ = replay_temporal_batches(events, policy_by_fold=policies, evidence_by_id=evidence, geometry_by_id={}, task_purposes=purposes, candidate_roster=roster, assignment_rows=[], source_artifact="events.csv", source_sha256="a" * 64, dependency_paths=[], input_status="formal")
    assert len(batches) == 2 and len(tasks) == 2


def test_temporal_batch_contract_detects_event_coverage_gap(tmp_path) -> None:
    event = {"event_id": "e1", "arrived_at": "2026-01-01T00:00:00Z", "arrival_order_source": "second_precision_export", "timestamp_precision": "second", "candidate_available_before_event": "true", "task_id": "t", "base_task_id": "b", "condition": "manual", "canonical_annotation_id": "a1", "worker_id": "w1", "tag_family": "difficulty", "tag_name": "occlusion"}
    evidence, purposes, roster = _batch_inputs([event])
    evidence[("extra", "difficulty", "occlusion")] = dict(next(iter(evidence.values())))
    fold = _fold_for_base("b", 2)
    *_, contracts = replay_temporal_batches([event], policy_by_fold={fold: _policy(fold, tmp_path)}, evidence_by_id=evidence, geometry_by_id={}, task_purposes=purposes, candidate_roster=roster, assignment_rows=[], source_artifact="events.csv", source_sha256="a" * 64, dependency_paths=[], input_status="formal")
    assert contracts["event_coverage_complete"] is False


def test_trusted_sequence_splits_same_timestamp_and_preserves_order(tmp_path) -> None:
    events = [{"event_id": f"e{i}", "arrived_at": "2026-01-01T00:00:00Z", "arrival_order_source": "server_receive_sequence", "timestamp_precision": "second", "trusted_sequence": str(i), "candidate_available_before_event": "true", "task_id": "t", "base_task_id": "b", "condition": "manual", "canonical_annotation_id": f"a{i}", "worker_id": f"w{i}", "tag_family": "difficulty", "tag_name": "occlusion"} for i in (1, 2)]
    evidence, purposes, roster = _batch_inputs(events)
    fold = _fold_for_base("b", 2)
    _, batches, _, _, contracts = replay_temporal_batches(events, policy_by_fold={fold: _policy(fold, tmp_path)}, evidence_by_id=evidence, geometry_by_id={}, task_purposes=purposes, candidate_roster=roster, assignment_rows=[], source_artifact="events.csv", source_sha256="a" * 64, dependency_paths=[], input_status="formal")
    assert [(row["pre_batch_k"], row["post_batch_k"]) for row in batches] == [(0, 1), (1, 2)]
    assert contracts["arrival_order_contract_valid"] is True


def test_tied_batch_counts_full_cap_overshoot(tmp_path) -> None:
    events = [{"event_id": f"e{i}", "arrived_at": "2026-01-01T00:00:00Z", "arrival_order_source": "second_precision_export", "timestamp_precision": "second", "candidate_available_before_event": "true", "task_id": "t", "base_task_id": "b", "condition": "manual", "canonical_annotation_id": f"a{i}", "worker_id": f"w{i}", "tag_family": "difficulty", "tag_name": "occlusion"} for i in range(8)]
    evidence, purposes, roster = _batch_inputs(events)
    fold = _fold_for_base("b", 2)
    _, batches, _, _, _ = replay_temporal_batches(events, policy_by_fold={fold: _policy(fold, tmp_path)}, evidence_by_id=evidence, geometry_by_id={}, task_purposes=purposes, candidate_roster=roster, assignment_rows=[], source_artifact="events.csv", source_sha256="a" * 64, dependency_paths=[], input_status="formal")
    assert batches[0]["post_batch_k"] == 8
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
    def write_csv(path, rows):
        with path.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(rows[0])); writer.writeheader(); writer.writerows(rows)
    event = {"event_id": "e1", "arrived_at": "2026-01-01T00:00:00Z", "arrival_order_source": "second_precision_export", "timestamp_precision": "second", "candidate_available_before_event": "true", "task_id": "t", "base_task_id": "b", "condition": "manual", "canonical_annotation_id": "a1", "worker_id": "w1", "tag_family": "difficulty", "tag_name": "occlusion"}
    events = tmp_path / "events.csv"; write_csv(events, [event])
    quality = tmp_path / "quality.csv"; write_csv(quality, [{**event, "scope": "In-scope", "canonical_eligibility_status": "valid", "independence_status": "independent", "assigned_expected": "true", "outside_assignment_submission": "false", "duplicate_worker_task_submission": "false", "schema_interpretable": "true", "parse_error": "", "schema_error": "", "semi_geometry_correction_evaluable": "false"}])
    three = tmp_path / "three.csv"; write_csv(three, [{"canonical_annotation_id": "a1", "base_task_id": "b", "condition": "manual", "worker_id": "w1", "tag_family": "difficulty", "tag_name": "occlusion", "assertion": "+"}])
    purpose = tmp_path / "purpose.csv"; write_csv(purpose, [{"task_id": "t", "base_task_id": "b", "condition": "manual", "dataset_group": "Calibration_core", "task_purpose": "meta_label_only", "required_evidence_components": '["difficulty"]', "scope_policy_id": "s1", "geometry_policy_id": "g1", "tag_policy_id": "t1", "correction_policy_id": "c1", "source_assignment_sha256": "a" * 64, "manifest_version": "v1"}])
    roster = tmp_path / "roster.csv"; write_csv(roster, [{"base_task_id": "b", "condition": "manual", "worker_id": "w1", "candidate_eligible": "true", "exclusion_reason": "", "source_admission_sha256": "b" * 64, "source_assignment_sha256": "a" * 64, "manifest_version": "v1"}])
    assignment = tmp_path / "assignment.csv"; write_csv(assignment, [{"base_task_id": "b", "condition": "manual", "worker_id": "w1", "assignment_status": "assigned"}])
    canonical = tmp_path / "canonical.csv"; canonical.write_text("canonical_annotation_id\na1\n", encoding="utf-8")
    geometry = tmp_path / "geometry.jsonl"; geometry.write_text("", encoding="utf-8")
    fold = _fold_for_base("b", 2); policy = _policy(fold, tmp_path); artifact = Path(policy["policy_artifact_path"]); payload = json.loads(artifact.read_text(encoding="utf-8"))
    from tools.thesis_main.analysis.vfinal_artifact_utils import sha256_file
    payload.update(task_purpose_manifest_sha256=sha256_file(purpose), candidate_roster_manifest_sha256=sha256_file(roster), k_dispatch_initial=2, k_min_for_stop=2, standard_cap=5, escalation_cap=7, unresolved_rule="at_cap", arrival_order_contract="atomic", primary_tie_policy="simultaneous")
    artifact.write_text(json.dumps(payload), encoding="utf-8"); policy["policy_artifact_sha256"] = sha256_file(artifact)
    manifest = tmp_path / "policy_manifest.json"; manifest.write_text(json.dumps({str(fold): {**policy, "policy_artifact_path": artifact.name}}), encoding="utf-8")
    output = tmp_path / "routing_temporal_replay_C1.csv"
    summary = materialize_temporal_replay(events, output, policy_manifest=manifest, canonical_csv=canonical, quality_csv=quality, three_state_csv=three, canonical_geometry_jsonl=geometry, task_purpose_manifest_csv=purpose, candidate_roster_manifest_csv=roster, assignment_history_csv=assignment, input_status="formal")
    assert summary["full_stop_contract_valid"] is True
    assert summary["n_batches"] == summary["n_tasks"] == 1
    assert all((tmp_path / name).exists() for name in ("routing_temporal_batch_decisions_C1.csv", "routing_temporal_task_summary_C1.csv", "routing_temporal_order_sensitivity_C1.csv"))
