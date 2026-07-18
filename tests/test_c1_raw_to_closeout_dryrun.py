from __future__ import annotations

import csv
import json
from pathlib import Path

import pytest

from tools.thesis_main.analysis.routing.temporal_replay import _fold_for_base, build_temporal_event_ledger
from tools.thesis_main.analysis.c1_materialize_quality_table import materialize as materialize_quality
from tools.thesis_main.analysis.run_c1_closeout_dryrun_chain import finalize_existing_closeout
from tools.thesis_main.analysis.run_c1_raw_to_closeout_dryrun import materialize
from tools.thesis_main.analysis.vfinal_artifact_utils import sha256_file, sha256_json


def _csv(path: Path, fields: list[str], rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def _rows(path: Path) -> list[dict[str, str]]:
    return list(csv.DictReader(path.open(encoding="utf-8")))


def _kp(x: float, y: float) -> dict:
    return {"type": "keypointlabels", "value": {"x": x, "y": y, "keypointlabels": ["Corner"]}}


def _choice(name: str, value: str) -> dict:
    return {"type": "choices", "from_name": name, "value": {"choices": [value]}}


def test_raw_to_closeout_dryrun_smoke_generates_provisional_gate_and_p1_readonly(tmp_path: Path) -> None:
    fields = ["round_id", "worker_id", "task_id", "base_task_id", "dataset_group"]
    manual = tmp_path / "manual.csv"
    semi = tmp_path / "semi.csv"
    workers = tmp_path / "workers.csv"
    mapping = tmp_path / "mapping.csv"
    reserve = tmp_path / "reserve.csv"
    inventory = tmp_path / "inventory.csv"
    p1 = tmp_path / "p1.csv"
    export = tmp_path / "raw_export.json"

    _csv(manual, fields, [{"round_id": "C1", "worker_id": "w1", "task_id": "a1", "base_task_id": "scene_a", "dataset_group": "Calibration_anchor"}])
    _csv(semi, fields, [])
    _csv(workers, fields, [{"round_id": "C1", "worker_id": "w1", "task_id": "a1", "base_task_id": "scene_a", "dataset_group": "Calibration_anchor"}])
    _csv(mapping, ["task_id", "base_task_id", "inner_id", "intended_project_group", "mapping_status"], [{"task_id": "a1", "base_task_id": "scene_a", "inner_id": "1", "intended_project_group": "Calibration_anchor", "mapping_status": "planned"}])
    _csv(reserve, ["task_id", "base_task_id", "dataset_group", "calibration_split"], [{"task_id": "r1", "base_task_id": "reserve_scene", "dataset_group": "Calibration_reserve", "calibration_split": "reserve"}])
    _csv(inventory, ["task_id", "base_task_id", "dataset_group", "used_for_r_u"], [])
    _csv(p1, ["worker_id", "r_u_0"], [{"worker_id": "w1", "r_u_0": "0.8"}])
    export.write_text(
        json.dumps(
            [
                {
                    "id": "100",
                    "project": 66,
                    "data": {
                        "task_id": "a1",
                        "base_task_id": "scene_a",
                        "condition": "manual",
                    },
                    "annotations": [
                        {
                            "id": "ann1",
                            "completed_by": {"id": "w1"},
                            "lead_time": 6,
                            "result": [_kp(1, 1), _kp(2, 2), _kp(3, 3), _kp(4, 4)],
                        }
                    ],
                }
            ]
        ),
        encoding="utf-8",
    )

    out = tmp_path / "out"
    c2 = tmp_path / "c2"
    summary = materialize(
        [export],
        out,
        c2,
        reserve,
        inventory,
        min_r_u_tasks=2,
        min_scene_support=1,
        min_calib=2,
        epsilon_r=0.15,
        tasks_per_fill=1,
        manual_assignment=manual,
        semi_assignment=semi,
        worker_distribution=workers,
        planned_task_mapping=mapping,
        active_log=None,
        p1_artifacts=[p1],
    )

    gate = json.loads((out / "c1_closeout_dryrun_gate_summary.json").read_text(encoding="utf-8"))
    sidecar = json.loads((out / "worker_profile_sidecar_C1.summary.json").read_text(encoding="utf-8"))

    assert summary["canonical_csv"] == str(out / "c1_canonical_annotations.csv")
    assert (out / "c1_closeout_dryrun_gate_summary.md").exists()
    assert gate["passed"] is False
    assert gate["raw_pipeline_ready"] is False
    assert gate["formal_closeout_ready"] is False
    assert gate["formal_inputs_present"] is False
    assert gate["c2_decision_chain_ready"] is False
    assert not (c2 / "assignment_manifest_C2_draft.csv").exists()
    assert sidecar["profile_freeze_status"] == "C1_provisional"
    assert sidecar["input_p1_artifacts"] == [str(p1)]
    assert (out / "c1_raw_to_closeout_dryrun_summary.json").exists()


def _complete_p1_fixture(tmp_path: Path, workers: tuple[str, ...]) -> tuple[Path, Path, Path, Path]:
    task_rows: list[dict[str, str]] = []
    score_rows: list[dict[str, str]] = []
    canonical_sha = "c" * 64
    final_gold_sha = "f" * 64
    for worker in workers:
        for condition in ("manual", "semi"):
            for index in range(10):
                task_id = f"p1-{worker}-{condition}-{index}"
                annotation_id = f"p1-ann-{worker}-{condition}-{index}"
                row = {
                    "worker_id": worker, "task_id": task_id, "annotation_id": annotation_id,
                    "condition": condition, "dataset_group": "PreScreen_manual" if condition == "manual" else "PreScreen_semi",
                    "task_final_scope": "in_scope", "scope_evidence_status": "evaluable", "process_evaluable": "true",
                    "process_failure_observed": "false", "canonical_eligibility_status": "valid", "independence_status": "independent",
                    "assigned_expected": "true", "outside_assignment_submission": "false", "duplicate_worker_task_submission": "false",
                    "schema_interpretable": "true", "parse_error": "", "schema_error": "", "adjudication_status": "resolved",
                    "undercoverage_evidence_status": "evaluable_expert_adjudicated", "model_issue_primary": "corner_drift" if condition == "semi" else "",
                    "semi_issue_recognition_evaluable": "true" if condition == "semi" else "false",
                    "semi_geometry_correction_evaluable": "true" if condition == "semi" else "false",
                    "source_canonical_sha256": canonical_sha, "source_scope_sha256": "1" * 64,
                    "source_semi_sha256": "2" * 64, "source_undercoverage_sha256": "3" * 64,
                    "rule_version": "p1-correction-v1",
                }
                task_rows.append(row)
                score_rows.append({
                    "worker_id": worker, "task_id": task_id, "annotation_id": annotation_id,
                    "included_in_p1_geometry_profile": "true" if condition == "manual" else "false",
                    "source_canonical_sha256": canonical_sha, "source_final_gold_sha256": final_gold_sha,
                    "scoring_rule_version": "p1-geometry-v1",
                })
    task = tmp_path / "p1_task_evidence_frozen.csv"
    worker_status = tmp_path / "p1_worker_status_frozen.csv"
    scores = tmp_path / "p1_geometry_scores_frozen.csv"
    profile = tmp_path / "p1_worker_geometry_profile_frozen.csv"
    _csv(task, list(task_rows[0]), task_rows)
    _csv(worker_status, ["worker_id", "rule_version"], [{"worker_id": worker, "rule_version": "p1-correction-v1"} for worker in workers])
    _csv(scores, list(score_rows[0]), score_rows)
    _csv(profile, ["worker_id", "source_canonical_sha256", "source_final_gold_sha256", "scoring_rule_version"], [{"worker_id": worker, "source_canonical_sha256": canonical_sha, "source_final_gold_sha256": final_gold_sha, "scoring_rule_version": "p1-geometry-v1"} for worker in workers])
    return task, worker_status, scores, profile


def test_raw_to_finalize_contract_positive_path_uses_only_materialized_intermediates(tmp_path: Path) -> None:
    workers = ("w1", "w2", "w3")
    assignment_fields = ["round_id", "worker_id", "task_id", "base_task_id", "dataset_group"]
    assignment_rows = [{"round_id": "C1", "worker_id": worker, "task_id": "a1", "base_task_id": "scene_a", "dataset_group": "Calibration_anchor"} for worker in workers]
    manual = tmp_path / "manual.csv"
    semi = tmp_path / "semi.csv"
    distribution = tmp_path / "workers.csv"
    mapping = tmp_path / "mapping.csv"
    reserve = tmp_path / "reserve.csv"
    inventory = tmp_path / "inventory.csv"
    task_outcome = tmp_path / "task_outcome.csv"
    audit = tmp_path / "independence_audit_frozen.csv"
    failure_disposition = tmp_path / "failure_disposition.csv"
    export = tmp_path / "raw_export.json"
    _csv(manual, assignment_fields, assignment_rows)
    _csv(semi, assignment_fields, [])
    _csv(distribution, assignment_fields, assignment_rows)
    _csv(mapping, ["task_id", "base_task_id", "inner_id", "intended_project_group", "mapping_status"], [{"task_id": "a1", "base_task_id": "scene_a", "inner_id": "1", "intended_project_group": "Calibration_anchor", "mapping_status": "planned"}])
    _csv(reserve, ["task_id", "base_task_id", "dataset_group", "calibration_split"], [{"task_id": "r1", "base_task_id": "reserve_scene", "dataset_group": "Calibration_reserve", "calibration_split": "reserve"}])
    _csv(inventory, ["task_id", "base_task_id", "dataset_group", "used_for_r_u"], [])
    _csv(task_outcome, ["project_id", "ls_runtime_task_id", "task_id", "base_task_id", "condition", "final_scope", "scope_resolution_status", "oos_subtype", "scope_reference_mode", "geometry_reference_mode", "geometry_reference_status", "reference_identity", "reference_worker_excluded", "reference_evidence_status", "adjudication_status", "reviewed_by", "reviewed_at"], [{"project_id": "66", "ls_runtime_task_id": "100", "task_id": "a1", "base_task_id": "scene_a", "condition": "manual", "final_scope": "in_scope", "scope_resolution_status": "resolved", "oos_subtype": "", "scope_reference_mode": "expert_adjudicated", "geometry_reference_mode": "expert_hard_gt", "geometry_reference_status": "expert_hard_single", "reference_identity": "synthetic-ref", "reference_worker_excluded": "false", "reference_evidence_status": "evaluable", "adjudication_status": "approved", "reviewed_by": "reviewer", "reviewed_at": "2026-07-15T00:00:00Z"}])
    annotations = []
    for index, worker in enumerate(workers, 1):
        annotations.append({
            "id": f"ann-{index}", "completed_by": {"id": worker}, "lead_time": 10,
            "created_at": "2026-07-14T00:00:00Z",
            "result": [_kp(10, 20), _kp(10, 80), _kp(50, 20), _kp(50, 80)] + [_choice("scope", "normal"), _choice("difficulty", "occlusion")],
        })
    export.write_text(json.dumps([{"id": "100", "project": 66, "data": {"task_id": "a1", "base_task_id": "scene_a", "condition": "manual", "dataset_group": "Calibration_anchor", "scene_label": "room_a"}, "annotations": annotations}]), encoding="utf-8")
    _csv(audit, ["project_id", "ls_runtime_task_id", "worker_id", "raw_annotation_id", "independence_status", "parent_derived", "copy_risk_status"], [{"project_id": "66", "ls_runtime_task_id": "100", "worker_id": worker, "raw_annotation_id": f"ann-{index}", "independence_status": "independent", "parent_derived": "false", "copy_risk_status": "cleared"} for index, worker in enumerate(workers, 1)])
    _csv(failure_disposition, ["project_id", "ls_runtime_task_id", "worker_id", "annotation_id", "failure_attribution", "incident_evidence_status", "failure_disposition_reason"], [{"project_id": "66", "ls_runtime_task_id": "100", "worker_id": worker, "annotation_id": f"ann-{index}", "failure_attribution": "none", "incident_evidence_status": "not_applicable", "failure_disposition_reason": "no_failure_adjudication"} for index, worker in enumerate(workers, 1)])
    p1_task, p1_status, p1_scores, p1_profile = _complete_p1_fixture(tmp_path, workers)
    p1_hashes_before = {path: sha256_file(path) for path in (p1_task, p1_status, p1_scores, p1_profile)}

    out = tmp_path / "out"
    c2 = tmp_path / "c2"
    first = materialize(
        [export], out, c2, reserve, inventory, 1, 1, 1, 0.15, 1,
        manual_assignment=manual, semi_assignment=semi, worker_distribution=distribution, planned_task_mapping=mapping,
        active_log=None, p1_task_evidence_csv=p1_task, p1_worker_status_csv=p1_status,
        p1_geometry_task_scores=p1_scores, p1_worker_geometry_profile=p1_profile,
        require_complete=True, input_status="formal", independence_audit_csv=audit,
        task_outcome_csv=task_outcome,
        failure_disposition_csv=failure_disposition,
    )
    assert first["canonicalization_summary"]["blockers"] == []
    canonical_rows = _rows(out / "c1_canonical_annotations.csv")
    assert {row["parent_derived"] for row in canonical_rows} == {"false"}
    assert {row["parent_cross_owner"] for row in canonical_rows} == {""}
    canonical_meta_header = next(csv.reader((out / "c1_canonical_meta_observations.csv").open(encoding="utf-8")))
    assert len(canonical_meta_header) == len(set(canonical_meta_header))

    score = tmp_path / "r_u_scoring_evidence.csv"
    score_fields = ["project_id", "ls_runtime_task_id", "worker_id", "annotation_id", "response_hash", "source_export_sha256", "r_u_metric_name", "r_u_metric_value", "r_u_metric_direction", "r_u_normalization_rule", "r_u_score_status", "r_u_score_source", "r_u_reference_mode", "r_u_reference_identity", "r_u_reference_sha256", "r_u_reference_excludes_worker", "r_u_reference_support"]
    quality_rows = _rows(out / "c1_quality_annotations.csv")
    _csv(score, score_fields, [{**{field: row.get(field, "") for field in score_fields[:6]}, "r_u_metric_name": "iou_to_consensus_loo", "r_u_metric_value": "0.9", "r_u_metric_direction": "higher_is_better", "r_u_normalization_rule": "identity_0_1", "r_u_score_status": "valid", "r_u_score_source": "synthetic_external_score", "r_u_reference_mode": "worker_excluded_loo_consensus", "r_u_reference_identity": f"loo-{row['worker_id']}", "r_u_reference_sha256": "a" * 64, "r_u_reference_excludes_worker": "true", "r_u_reference_support": "2"} for row in quality_rows])
    materialize_quality(out / "c1_canonical_annotations.csv", out, inventory, input_status="formal", task_outcome_csv=task_outcome, r_u_scoring_evidence_csv=score)
    ledger = tmp_path / "temporal_event_ledger_frozen.csv"
    build_temporal_event_ledger(out / "c1_canonical_meta_observations.csv", out / "c1_quality_annotations.csv", out / "worker_task_tag_observations_C1.csv", ledger)
    admission = tmp_path / "p1_admission_frozen.csv"
    _csv(admission, ["worker_id", "eligible"], [{"worker_id": worker, "eligible": "true"} for worker in workers])
    policies = {
        "scope": {"policy_id": "scope-v1", "meta_min_same_state": 2, "meta_max_opposition": 0, "max_unasserted_rate": 0.25},
        "tag": {"policy_id": "tag-v1", "meta_min_same_state": 2, "meta_max_opposition": 0, "max_unasserted_rate": 0.25},
        "geometry": {"policy_id": "geometry-v1", "min_q_boundary": 0.8, "min_q_wallwall": 0.8, "min_geometry_support": 2},
        "correction": {"policy_id": "correction-v1", "min_complete_workers": 2, "require_initialization_provenance": True, "require_final_geometry": True, "require_edit_metrics": True, "require_reference_outcome": True},
        "risk": {"policy_id": "risk-v1", "risk_bucket": "low_risk", "k_dispatch_initial": 2, "k_min_for_stop": 2, "standard_cap": 5, "escalation_cap": 7, "unresolved_rule": "at_cap_or_exhaustion"},
    }
    policy_paths: dict[str, Path] = {}
    for kind, payload in policies.items():
        path = tmp_path / f"{kind}_policy_frozen.json"
        path.write_text(json.dumps(payload), encoding="utf-8")
        policy_paths[kind] = path
    purpose = tmp_path / "task_purpose_frozen.csv"
    purpose_row = {"task_id": "a1", "base_task_id": "scene_a", "condition": "manual", "dataset_group": "Calibration_anchor", "task_purpose": "meta_label_only", "required_evidence_components": '["difficulty"]', "required_tag_family": '["difficulty"]', "required_tag_names": '["difficulty/occlusion"]', "risk_bucket": "low_risk", "source_assignment_path": str(manual), "source_assignment_sha256": sha256_file(manual), "manifest_version": "task_purpose_v1"}
    for kind, path in policy_paths.items():
        purpose_row[f"{kind}_policy_id"] = policies[kind]["policy_id"]
        purpose_row[f"{kind}_policy_path"] = str(path)
        purpose_row[f"{kind}_policy_sha256"] = sha256_file(path)
    _csv(purpose, list(purpose_row), [purpose_row])
    roster = tmp_path / "candidate_roster_frozen.csv"
    roster_rows = [{"base_task_id": "scene_a", "condition": "manual", "worker_id": worker, "candidate_eligible": "true", "exclusion_reason": "", "source_admission_path": str(admission), "source_admission_sha256": sha256_file(admission), "source_assignment_path": str(manual), "source_assignment_sha256": sha256_file(manual), "manifest_version": "candidate_roster_v1"} for worker in workers]
    _csv(roster, list(roster_rows[0]), roster_rows)
    history = tmp_path / "assignment_history_frozen.csv"
    history_fields = ["base_task_id", "condition", "worker_id", "assignment_status", "effective_at", "source_manifest_path", "source_manifest_sha256", "manifest_version"]
    history_rows = [{"base_task_id": "scene_a", "condition": "manual", "worker_id": worker, "assignment_status": "available", "effective_at": "2025-12-31T00:00:00Z", "source_manifest_path": str(manual), "source_manifest_sha256": sha256_file(manual), "manifest_version": "assignment_history_v1"} for worker in workers]
    _csv(history, history_fields, history_rows)
    fold = _fold_for_base("scene_a", 2)
    fit_base = next(f"fit-{index}" for index in range(100) if _fold_for_base(f"fit-{index}", 2) != fold)
    temporal_policy = tmp_path / "temporal_policy_frozen.json"
    temporal_policy.write_text(json.dumps({"trusted_order_sources": ["server_receive_sequence"], "arrival_order_contract": "canonical_utc_atomic", "primary_tie_policy": "simultaneous_atomic_batch", "sensitivity_seed": 20260714, "sensitivity_permutations": 100, "event_ledger_sha256": sha256_file(ledger), "three_state_evidence_sha256": sha256_file(out / "worker_task_tag_observations_C1.csv"), "task_purpose_manifest_sha256": sha256_file(purpose), "candidate_roster_manifest_sha256": sha256_file(roster), "assignment_history_sha256": sha256_file(history)}), encoding="utf-8")
    policy_manifest = tmp_path / "temporal_policy_manifest_frozen.json"
    policy_manifest.write_text(json.dumps({str(fold): {"policy_artifact_id": "temporal-v3", "policy_artifact_path": temporal_policy.name, "policy_artifact_sha256": sha256_file(temporal_policy), "rule_version": "temporal-v3", "fit_folds": [1 - fold], "fit_base_task_ids": [fit_base]}}), encoding="utf-8")

    worker_state = tmp_path / "worker_state_frozen.csv"
    _csv(worker_state, ["worker_id", "n_calib_completed", "r_u_hat", "r_u_ci_low", "r_u_ci_high", "r_u_status", "support_status", "interpretation_allowed"], [{"worker_id": worker, "n_calib_completed": "1", "r_u_hat": "0.8", "r_u_ci_low": "0.7", "r_u_ci_high": "0.9", "r_u_status": "estimated", "support_status": "sufficient", "interpretation_allowed": "true"} for worker in workers])
    r_u_evidence = out / "calibration_r_u_evidence_C1.csv"
    worker_dependencies = [out / "c1_canonical_annotations.csv", out / "c1_quality_annotations.csv", r_u_evidence, out / "c1_canonical_geometry.jsonl", out / "geometry_worker_task_loo_C1.csv", out / "geometry_stability_C1.csv"]
    dependency_rows = [{"path": str(path.resolve()), "sha256": sha256_file(path)} for path in worker_dependencies]
    worker_manifest = tmp_path / "worker_state_manifest_frozen.json"
    worker_manifest.write_text(json.dumps({"worker_state_status": "formal", "rule_version": "external-worker-state-v1", "source_csv_sha256": sha256_file(worker_state), "dependency_bundle_id": sha256_json({"rule_version": "external-worker-state-v1", "dependencies": sorted(dependency_rows, key=lambda item: item["path"])}), "dependencies": dependency_rows, "r_u_estimated": True, "r_u_freeze": True, "eligible_support_count": 3, "estimator_id": "external_protocol_r_u", "estimator_version": "v1", "ci_method": "bootstrap", "confidence_level": 0.95, "evidence_manifest_path": str(r_u_evidence.resolve()), "evidence_manifest_sha256": sha256_file(r_u_evidence)}), encoding="utf-8")

    prepared = materialize(
        [export], out, c2, reserve, inventory, 1, 1, 1, 0.15, 1,
        manual_assignment=manual, semi_assignment=semi, worker_distribution=distribution, planned_task_mapping=mapping,
        active_log=None, p1_task_evidence_csv=p1_task, p1_worker_status_csv=p1_status,
        p1_geometry_task_scores=p1_scores, p1_worker_geometry_profile=p1_profile,
        require_complete=True, input_status="formal", independence_audit_csv=audit,
        temporal_event_csv=ledger, temporal_policy_manifest=policy_manifest, task_purpose_manifest_csv=purpose,
        candidate_roster_manifest_csv=roster, assignment_history_csv=history,
        formal_worker_state_csv=worker_state, formal_worker_state_manifest=worker_manifest,
            task_outcome_csv=task_outcome, r_u_scoring_evidence_csv=score,
            failure_disposition_csv=failure_disposition,
    )["gate_summary"]
    assert prepared["formal_closeout_ready"] is False
    assert prepared["formal_worker_state"]["valid"] is True
    assert prepared["vfinal_sidecars"]["routing_temporal_replay"]["full_stop_contract_valid"] is True
    assert prepared["full_profile_ready"] is True
    assert {path: sha256_file(path) for path in p1_hashes_before} == p1_hashes_before

    bundle = json.loads((out / "c1_closeout_input_bundle.json").read_text(encoding="utf-8"))
    adjudication = tmp_path / "formal_adjudication.json"
    adjudication.write_text(json.dumps({"status": "approved", "approved": True, "manifest_id": "synthetic-contract-only", "approved_by": "test-reviewer", "approved_at": "2026-07-14T00:00:00Z", "input_bundle_sha256": bundle["bundle_sha256"]}), encoding="utf-8")
    frozen_p1_bytes = p1_task.read_bytes()
    p1_task.write_bytes(frozen_p1_bytes + b"\n")
    with pytest.raises(ValueError, match="bundle is stale"):
        finalize_existing_closeout(out, adjudication)
    p1_task.write_bytes(frozen_p1_bytes)
    final = finalize_existing_closeout(out, adjudication)
    assert final["formal_closeout_ready"] is True
    assert final["profile_freeze_status"] == "C1_frozen"
    assert final["r_u_freeze"] is True
    assert final["c2_freeze"] is False
    assert final["formal_routing_conclusion_allowed"] is False
    assert not (c2 / "assignment_manifest_C2_draft.csv").exists()
