from __future__ import annotations

import json
import time
from pathlib import Path

import pytest

from tools.thesis_main.analysis.geometry_consensus.pairwise import cyclic_order_correspondence, pairwise_similarity
from tools.thesis_main.analysis.geometry_consensus.representation import normalize_geometry
from tools.thesis_main.analysis.geometry_consensus.stability import stability_summary
from tools.thesis_main.analysis.materialize_model_issue_harmonization import _validate_amendments
from tools.thesis_main.analysis.routing.temporal_replay import _fold_for_base, _load_policy_manifest, _validate_policy
from tools.thesis_main.analysis.run_c1_closeout_dryrun_chain import _formal_worker_state, _temporal_valid, build_gate_summary, finalize_existing_closeout
from tools.thesis_main.analysis.vfinal_artifact_utils import sha256_file, sha256_json


def _payload() -> list[dict]:
    return [
        {"type": "keypointlabels", "value": {"x": x / 1024 * 100, "y": y / 512 * 100}}
        for x, y in ((100, 100), (100, 400), (500, 100), (500, 400))
    ]


def _amendment(**updates: str) -> dict[str, str]:
    payload = _payload()
    row = {
        "source_export_sha256": "a" * 64,
        "project_id": "zh-project",
        "ls_runtime_task_id": "42",
        "initialization_artifact_id": "init-1",
        "checkpoint_sha256": "b" * 64,
        "inference_config_sha256": "c" * 64,
        "preprocess_postprocess_sha256": "d" * 64,
        "prediction_payload_sha256": sha256_json(payload),
        "prediction_payload_json": json.dumps(payload),
    }
    row.update(updates)
    return row


@pytest.mark.parametrize(
    ("updates", "blocker"),
    [
        ({"checkpoint_sha256": "bad"}, "malformed_sha256"),
        ({"prediction_payload_sha256": "e" * 64}, "prediction_payload_sha256_mismatch"),
        ({"project_id": ""}, "missing_identity"),
        ({"prediction_payload_json": "{"}, "invalid_prediction_payload_json"),
    ],
)
def test_retrospective_amendment_fail_closed(updates, blocker) -> None:
    valid, blockers = _validate_amendments([_amendment(**updates)])
    assert valid == {}
    assert blockers[blocker] == 1


def test_retrospective_amendment_success_duplicate_and_cross_project_identity() -> None:
    zh = _amendment()
    en = _amendment(project_id="en-project")
    valid, blockers = _validate_amendments([zh, en])
    assert len(valid) == 2 and not blockers
    valid, blockers = _validate_amendments([zh, dict(zh)])
    assert valid == {} and blockers["duplicate_key"] == 2


def _cyclic(xs: list[float]) -> dict:
    return {"width": 1024, "height": 512, "x_event_positions": xs}


def test_cyclic_alignment_unique_reverse_ambiguous_and_variable_count() -> None:
    unique = cyclic_order_correspondence(_cyclic([100, 400, 800]), _cyclic([400, 800, 100]))
    assert unique["compatible"] and unique["rotation"] == 2
    reverse = cyclic_order_correspondence(_cyclic([100, 400, 800]), _cyclic([800, 400, 100]))
    assert not reverse["compatible"]
    ambiguous = cyclic_order_correspondence(_cyclic([0, 256, 512, 768]), _cyclic([128, 384, 640, 896]))
    assert not ambiguous["compatible"] and ambiguous["ambiguous"]
    variable = cyclic_order_correspondence(_cyclic([100, 400]), _cyclic([100, 400, 800]))
    assert variable["reason"] == "not_evaluable_variable_count_contract_unfrozen"
    assert variable["insertions"] == 1


def _record(worker: str, offset: int = 0, x_offset: int = 0) -> dict:
    return {
        "worker_id": worker,
        "geometry": normalize_geometry([[100 + x_offset, 100 + offset], [100 + x_offset, 400], [500 + x_offset, 100 + offset], [500 + x_offset, 400]]),
    }


def test_geometry_medoid_tie_and_high_k_is_non_recursive() -> None:
    tied = stability_summary([_record("w1"), _record("w2")])
    assert tied["medoid_ambiguous"] is True
    assert tied["medoid_boundary_worker_id"] == ""
    started = time.monotonic()
    result = stability_summary([_record(f"w{i}", i % 5, i) for i in range(22)], grid=32)
    assert result["valid_k"] == 22
    score_table = json.loads(result["medoid_score_table_json"])
    assert len(score_table) == 22
    records = [_record(f"w{i}", i % 5, i) for i in range(22)]
    worker = records[7]
    pair_scores = [pairwise_similarity(worker["geometry"], peer["geometry"], grid=32) for peer in records if peer["worker_id"] != worker["worker_id"]]
    score = next(row for row in score_table if row["worker_id"] == worker["worker_id"])
    assert score["boundary_score"] == pytest.approx(sum(row["boundary_similarity"] for row in pair_scores) / len(pair_scores))
    assert score["wallwall_score"] == pytest.approx(sum(row["wallwall_similarity"] for row in pair_scores) / len(pair_scores))
    boundary_best = max(score_table, key=lambda row: row["boundary_score"])
    wallwall_best = max(score_table, key=lambda row: row["wallwall_score"])
    if result["medoid_boundary_ambiguous"]:
        assert result["medoid_boundary_worker_id"] == ""
    else:
        assert result["medoid_boundary_worker_id"] == boundary_best["worker_id"]
    if result["medoid_wallwall_ambiguous"]:
        assert result["medoid_wallwall_worker_id"] == ""
    else:
        assert result["medoid_wallwall_worker_id"] == wallwall_best["worker_id"]
    assert result["leave_two_out_status"] in {"robust", "sensitive"}
    assert time.monotonic() - started < 30


def test_policy_manifest_relative_path_and_tampering(tmp_path) -> None:
    artifact = tmp_path / "policy.json"
    artifact.write_text('{"trusted_order_sources":[]}', encoding="utf-8")
    fit_base = next(value for value in (f"fit-{i}" for i in range(100)) if _fold_for_base(value, 2) == 1)
    manifest = tmp_path / "manifest.json"
    manifest.write_text(json.dumps({"0": {"policy_artifact_id": "p0", "policy_artifact_path": "policy.json", "policy_artifact_sha256": sha256_file(artifact), "rule_version": "r1", "fit_folds": [1], "fit_base_task_ids": [fit_base]}}), encoding="utf-8")
    policy = _load_policy_manifest(manifest)[0]
    assert policy["policy_artifact_path"] == str(artifact.resolve())
    assert _validate_policy(policy, 0, 2)["trusted_order_sources"] == []
    artifact.write_text('{"tampered":true}', encoding="utf-8")
    with pytest.raises(ValueError, match="SHA"):
        _validate_policy(policy, 0, 2)


def test_policy_manifest_rejects_equivalent_numeric_fold_keys(tmp_path) -> None:
    manifest = tmp_path / "manifest.json"
    manifest.write_text('{"0": {}, "00": {}}', encoding="utf-8")
    with pytest.raises(ValueError, match="duplicate numeric fold"):
        _load_policy_manifest(manifest)


def test_formal_gate_requires_separate_adjudication_manifest(tmp_path) -> None:
    summary = build_gate_summary(
        {"canonical_meta_fresh": True, "n_quality_rows": 1, "r_u_estimated": True, "blockers": []},
        {"r_u_estimated": True, "r_u_freeze": True},
        {},
        {"c2_freeze": True},
        {"full_profile_ready": True, "pending_adjudication_count": 0, "profile_freeze_status": "C1_provisional"},
        tmp_path / "profile.json",
        {"routing_temporal_replay": {"status": "candidate_only"}},
        input_status="formal",
        artifact_freshness={"fresh": True},
        canonicalization_summary={"structural_integrity_passed": True, "collection_completeness_passed": True},
        snapshot_manifest_fresh=True,
        adjudication={"valid": False},
    )
    assert summary["formal_closeout_ready"] is False
    assert summary["r_u_freeze"] is False
    assert summary["c2_freeze"] is False
    assert summary["formal_routing_conclusion_allowed"] is False


def _formal_worker_fixture(tmp_path: Path):
    evidence = []
    for name, body in {
        "canonical.csv": "canonical_annotation_id\nA\n",
        "quality.csv": "worker_id,used_for_r_u,canonical_eligibility_status,independence_status,assigned_expected,outside_assignment_submission,duplicate_worker_task_submission,schema_interpretable,parse_error,schema_error\nw1,true,valid,independent,true,false,false,true,,\n",
        "geometry.jsonl": '{}\n', "loo.csv": "worker_id\nw1\n", "stability.csv": "worker_id\nw1\n",
    }.items():
        path = tmp_path / name; path.write_text(body, encoding="utf-8"); evidence.append(path)
    state = tmp_path / "worker_state.csv"
    state.write_text("worker_id,n_calib_completed,r_u_hat,r_u_ci_low,r_u_ci_high\nw1,1,0.5,0.4,0.6\n", encoding="utf-8")
    dependencies = [{"path": str(path.resolve()), "sha256": sha256_file(path)} for path in evidence]
    manifest = tmp_path / "worker_state_manifest.json"
    manifest.write_text(json.dumps({
        "worker_state_status": "formal", "rule_version": "external_worker_state_v1", "source_csv_sha256": sha256_file(state),
        "dependency_bundle_id": sha256_json({"rule_version": "external_worker_state_v1", "dependencies": sorted(dependencies, key=lambda item: item["path"])}),
        "dependencies": dependencies, "r_u_estimated": True, "r_u_freeze": True, "eligible_support_count": 1,
    }), encoding="utf-8")
    kwargs = dict(canonical_csv=evidence[0], quality_csv=evidence[1], canonical_geometry_jsonl=evidence[2], geometry_loo_csv=evidence[3], geometry_stability_csv=evidence[4], min_r_u_tasks=1)
    return state, manifest, evidence, kwargs


def test_formal_worker_state_manifest_verifies_frozen_external_input(tmp_path) -> None:
    state, manifest, _, kwargs = _formal_worker_fixture(tmp_path)
    assert _formal_worker_state(state, manifest, **kwargs)["valid"] is True


def test_formal_worker_state_resolves_dependency_paths_from_manifest_directory(tmp_path) -> None:
    state, manifest, evidence, kwargs = _formal_worker_fixture(tmp_path)
    payload = json.loads(manifest.read_text(encoding="utf-8"))
    payload["dependencies"] = [{"path": path.name, "sha256": sha256_file(path)} for path in evidence]
    payload["dependency_bundle_id"] = sha256_json({"rule_version": payload["rule_version"], "dependencies": sorted(payload["dependencies"], key=lambda item: item["path"])})
    manifest.write_text(json.dumps(payload), encoding="utf-8")
    assert _formal_worker_state(state, manifest, **kwargs)["valid"] is True


def test_formal_gate_stays_blocked_until_profile_is_frozen(tmp_path) -> None:
    profile = tmp_path / "profile.json"
    profile.write_text("{}", encoding="utf-8")
    summary = build_gate_summary(
        {"canonical_meta_fresh": True, "n_quality_rows": 2, "r_u_estimated": True, "amendment_blocker_count": 0, "blockers": []},
        {"r_u_estimated": True, "r_u_freeze": True},
        {},
        {"c2_freeze": True},
        {"full_profile_ready": True, "pending_adjudication_count": 0, "profile_freeze_status": "C1_provisional"},
        profile,
        {"routing_temporal_replay": {"status": "candidate_only", "full_stop_contract_valid": True, "n_events": 3, "all_events_legal": True, "prior_state_monotonicity": True, "worker_identity_consistent": True, "policy_dependency_valid": True, "n_nonzero_assertions": 2, "illegal_event_reasons": {}}},
        {"bundle_sha256": "bundle"},
        input_status="formal",
        artifact_freshness={"fresh": True},
        canonicalization_summary={"structural_integrity_passed": True, "collection_completeness_passed": True, "blockers": []},
        snapshot_manifest_fresh=True,
        adjudication={"valid": True},
        formal_worker_state={"valid": True},
    )
    assert summary["formal_closeout_ready"] is False
    assert summary["r_u_freeze"] is False
    assert summary["c2_freeze"] is False
    assert summary["formal_routing_conclusion_allowed"] is False


def test_finalize_existing_closeout_binds_adjudication_without_rerunning_inputs(tmp_path) -> None:
    state, manifest, evidence, kwargs = _formal_worker_fixture(tmp_path)
    verified = _formal_worker_state(state, manifest, **kwargs)
    profile = tmp_path / "profile.json"; profile.write_text("{}", encoding="utf-8")
    contract_fields = ("event_key_uniqueness_valid", "event_coverage_complete", "annotation_tag_atomicity_valid", "batch_atomicity_valid", "arrival_order_contract_valid", "task_purpose_manifest_valid", "candidate_pool_binding_valid", "risk_bucket_valid", "family_gate_contract_valid", "task_completion_contract_valid", "no_future_scope_leakage")
    contract_results = {field: {"valid": True, "checked_count": 1, "failure_count": 0, "failure_reasons": {}, "evidence_artifact": "ledger.csv"} for field in contract_fields}
    temporal_contract = {"status": "formal_replay_audit_complete", "full_stop_contract_valid": True, **{field: True for field in contract_fields}, "contract_results": contract_results, "n_events": 1, "n_primary_annotations": 1, "all_events_legal": True, "prior_state_monotonicity": True, "worker_identity_consistent": True, "policy_dependency_valid": True, "n_nonzero_assertions": 1, "illegal_event_reasons": {}}
    temporal_path = tmp_path / "routing_temporal_contract_summary_C1.json"
    temporal_path.write_text(json.dumps(temporal_contract), encoding="utf-8")
    artifacts = [state, manifest, profile, temporal_path, *evidence]
    bundle = {"bundle_version": "v1", "artifacts": [{"path": str(path), "exists": True, "sha256": sha256_file(path)} for path in artifacts]}
    bundle["bundle_sha256"] = __import__("hashlib").sha256(json.dumps(bundle["artifacts"], sort_keys=True).encode("utf-8")).hexdigest()
    (tmp_path / "c1_closeout_input_bundle.json").write_text(json.dumps(bundle), encoding="utf-8")
    (tmp_path / "c1_closeout_dryrun_gate_summary.json").write_text(json.dumps({"input_status": "formal", "raw_snapshot_manifest_fresh": True, "artifacts_fresh": True, "quality_table_blockers": [], "quality_table_summary": {"n_quality_rows": 1, "amendment_blocker_count": 0}, "canonicalization_summary": {"structural_integrity_passed": True, "collection_completeness_passed": True, "blockers": []}, "formal_worker_state": verified, "r_u_estimated": True, "full_profile_ready": True, "profile_sidecar_generated": True, "profile_summary_path": str(profile), "profile_freeze_status": "C1_provisional", "pending_adjudication_count": 0, "worker_state_summary": {"r_u_freeze": True}, "c2_draft_summary": {"c2_freeze": True}, "dt_backflow": False, "formal_inputs_present": True, "vfinal_sidecars": {"routing_temporal_replay": temporal_contract}}), encoding="utf-8")
    adjudication = {"status": "approved", "approved": True, "manifest_id": "m1", "approved_by": "reviewer", "approved_at": "2026-07-14T00:00:00Z", "input_bundle_sha256": bundle["bundle_sha256"]}
    adjudication_path = tmp_path / "adjudication.json"
    adjudication_path.write_text(json.dumps(adjudication), encoding="utf-8")
    result = finalize_existing_closeout(tmp_path, adjudication_path)
    assert result["finalization"]["bundle_sha256"] == bundle["bundle_sha256"]
    assert result["formal_closeout_ready"] is True
    assert result["blocked_for_launch"] is False
    assert result["blockers"] == []
    assert result["analysis_contract_ready"] is True
    assert result["passed_semantics"] == "formal_closeout_ready"
    assert result["finalization"]["status"] == "approved_frozen"
    assert result["finalization"]["blockers"] == []
    assert result["profile_freeze_status"] == "C1_frozen"
    assert (tmp_path / "worker_profile_freeze_C1.json").exists()


def test_temporal_formal_gate_accepts_scope_only_primary_evidence() -> None:
    contract_fields = (
        "event_key_uniqueness_valid", "event_coverage_complete", "annotation_tag_atomicity_valid",
        "batch_atomicity_valid", "arrival_order_contract_valid", "task_purpose_manifest_valid",
        "candidate_pool_binding_valid", "risk_bucket_valid", "family_gate_contract_valid",
        "task_completion_contract_valid", "no_future_scope_leakage",
    )
    contract_results = {
        field: {"valid": True, "checked_count": 1, "failure_count": 0, "failure_reasons": {}, "evidence_artifact": "ledger.csv"}
        for field in contract_fields
    }
    temporal = {
        "status": "formal_replay_audit_complete", "full_stop_contract_valid": True,
        **{field: True for field in contract_fields}, "contract_results": contract_results,
        "n_events": 1, "n_primary_annotations": 1, "n_tag_state_events": 0,
        "n_nonzero_assertions": 0, "all_events_legal": True, "prior_state_monotonicity": True,
        "worker_identity_consistent": True, "policy_dependency_valid": True, "illegal_event_reasons": {},
    }
    assert _temporal_valid({"vfinal_sidecars": {"routing_temporal_replay": temporal}}) is True
