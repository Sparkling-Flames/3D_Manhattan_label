from __future__ import annotations

import hashlib
import csv
import json
import sys
from pathlib import Path

import pytest

from tools.thesis_main.analysis.geometry_cluster_v2 import cluster_geometry_records
from tools.thesis_main.analysis.materialize_stage3_freeze_gate import REQUIRED_GATES, build_gate, validate_gate_file
from tools.thesis_main.analysis.paper_a_contracts import METHOD_CONTRACT, load_method_contract, sha256_file, validate_record
from tools.thesis_main.analysis.routing.v1_decision_engine import append_decision, decide_next_offer, replay_next_offer
from tools.thesis_main.analysis.routing.v1_policy import RULE_VERSION
from tools.thesis_main.analysis.routing.v1_replay_auditor import audit_ledger
from tools.thesis_main.analysis.run_stage3_t1_launch import launch
from tools.thesis_main.analysis import run_c1_precloseout_rehearsal as rehearsal


def _record_examples() -> dict[str, dict]:
    return {
        "assignment_evidence_v2": {
            "schema_version": "assignment_evidence_v2", "canonical_annotation_id": "a", "worker_id": "1",
            "base_task_id": "t", "condition": "manual", "assignment_provenance": "original_assignment",
            "formal_assignment_eligible": True, "gt_primary_analysis_eligible": True,
            "peer_analysis_eligible": True, "loo_medoid_analysis_eligible": True,
            "strict_loo_analysis_eligible": False, "structural_opportunity_eligible": True,
            "time_analysis_eligible": True,
            "semi_correction_analysis_eligible": True,
            "predictive_validity_analysis_eligible": True,
            "routing_feature_analysis_eligible": True,
        },
        "peer_worker_task_v2": {
            "schema_version": "peer_worker_task_v2", "base_task_id": "t", "condition": "manual",
            "dataset_group": "core", "task_crowd_structure_status": "unimodal", "worker_id": "1",
            "canonical_annotation_id": "a", "R_peer_task": .8, "peer_count": 4,
        },
        "worker_profile_v2": {
            "schema_version": "worker_profile_v2", "worker_id": "1", "profile_version": "p",
            "cohort_id": "c", "enrollment_batch": "original", "administratively_eligible": True,
            "process_eligible": True, "independence_eligible": True, "Q_GT_estimable": True, "reference_evaluable": True,
            "Q_GT_profile_status": "estimated", "R_peer_profile_status": "estimated",
            "peer_task_support": 5, "F_struct_profile_status": "estimated", "LOO_medoid_status": "estimated",
            "LOO_strict_status": "not_evaluable", "global_policy_eligible": True,
            "c2_risk_model_eligible": True, "peer_tiebreak_eligible": True,
            "structural_gate_eligible": True, "F_struct_raw": .1, "F_struct_EB": .1,
            "F_struct_interval_lower": 0.0, "F_struct_interval_upper": .2,
        },
        "policy_candidate_v2": {
            "schema_version": "policy_candidate_v2", "worker_id": "1", "S_G": 1.0, "global_rank_S_G": 1,
            "global_policy_eligible": True, "R_peer_stable": .9, "R_peer_profile_status": "estimated", "R_LOO_medoid": .8,
            "LOO_medoid_status": "estimated", "profile_version": "p",
        },
        "geometry_cluster_v2": {
            "schema_version": "geometry_cluster_v2", "base_task_id": "t", "condition": "manual",
            "valid_k": 3, "partition_status": "unique", "cluster_membership_json": '[["a","b","c"]]',
            "cluster_count": 1, "largest_cluster_support": 3, "second_cluster_support": 0,
            "cluster_margin_all": 1.0, "cluster_margin_top2": 1.0,
            "largest_cluster_medoid_annotation_id": "a", "task_crowd_structure_status": "unimodal",
        },
    }


def _write_artifact(path: Path, schema: str, *, dependencies: list[dict] | None = None, method_sha: str | None = None) -> dict:
    payload = {
        "schema_version": schema, "status": "ready", "profile_version": "p", "cohort_id": "c",
        "blockers": [], "dependencies": dependencies or [],
    }
    if method_sha is not None:
        payload["method_contract_sha256"] = method_sha
    path.write_text(json.dumps(payload), encoding="utf-8")
    return {
        "path": str(path), "sha256": sha256_file(path), "expected_schema": schema,
        "required_status_field": "status", "required_status_value": "ready",
        "profile_version": "p", "cohort_id": "c", "frozen": True,
    }


def _formal_gate(tmp_path: Path) -> tuple[Path, Path, Path, dict]:
    roster, enrollment = tmp_path / "roster.csv", tmp_path / "enrollment.csv"
    roster.write_text("worker_id\n1\n", encoding="utf-8")
    enrollment.write_text("worker_id\n1\n", encoding="utf-8")
    child_items = []
    for role in load_method_contract()["stage3"]["required_child_roles"]["C1_EVIDENCE_FROZEN"]:
        item = _write_artifact(tmp_path / f"{role}.json", f"{role.lower()}_v2")
        child_items.append({"role": role, **item})
    state = {}
    for role in REQUIRED_GATES:
        item = _write_artifact(
            tmp_path / f"{role}.json", f"{role.lower()}_v2",
            dependencies=child_items if role == "C1_EVIDENCE_FROZEN" else [],
            method_sha=sha256_file(METHOD_CONTRACT) if role == "C1_EVIDENCE_FROZEN" else None,
        )
        if role == "C1_EVIDENCE_FROZEN":
            path = Path(item["path"])
            payload = json.loads(path.read_text(encoding="utf-8"))
            path.write_text(json.dumps(payload), encoding="utf-8")
            item["sha256"] = sha256_file(path)
        if role == "FINAL_POOLED_PROFILE_FROZEN":
            path = Path(item["path"])
            payload = json.loads(path.read_text(encoding="utf-8"))
            payload.update({"artifact_role": "FINAL_POOLED_PROFILE_FROZEN", "C1_EVIDENCE_FROZEN": True, "C2B_BATCH_A_CLOSEOUT_FROZEN": True, "C2A_RP_CLOSEOUT_FROZEN": True, "FINAL_C1_C2_Q_GT_MODEL_FROZEN": True, "POOLED_WORKER_PROFILE_FROZEN": True})
            path.write_text(json.dumps(payload), encoding="utf-8")
            item["sha256"] = sha256_file(path)
        state[role] = item
    gate = build_gate(
        state, hashlib.sha256(roster.read_bytes()).hexdigest(),
        hashlib.sha256(enrollment.read_bytes()).hexdigest(), base_dir=tmp_path,
    )
    gate_path = tmp_path / "gate.json"
    gate_path.write_text(json.dumps(gate), encoding="utf-8")
    return gate_path, roster, enrollment, state


def test_all_record_contracts_reject_wrong_version_missing_and_nonfinite() -> None:
    for name, valid in _record_examples().items():
        validate_record(name, valid)
        with pytest.raises(ValueError, match="schema_version"):
            validate_record(name, {**valid, "schema_version": "v1"})
        missing = dict(valid); missing.pop(next(field for field in valid if field != "schema_version"))
        with pytest.raises(ValueError, match="missing fields"):
            validate_record(name, missing)
    candidate = _record_examples()["policy_candidate_v2"]
    with pytest.raises(ValueError, match="legacy fields"):
        validate_record("policy_candidate_v2", {**candidate, "global_lcb": 1.0})
    with pytest.raises(ValueError, match="legacy fields"):
        validate_record("assignment_evidence_v2", {**_record_examples()["assignment_evidence_v2"], "global_analysis_eligible": True})
    with pytest.raises(ValueError, match="non-finite"):
        validate_record("policy_candidate_v2", {**candidate, "S_G": float("nan")})
    for name, field, value in (
        ("peer_worker_task_v2", "R_peer_task", float("inf")),
        ("worker_profile_v2", "F_struct_EB", float("nan")),
        ("geometry_cluster_v2", "valid_k", float("inf")),
    ):
        with pytest.raises(ValueError, match="non-finite"):
            validate_record(name, {**_record_examples()[name], field: value})
    with pytest.raises(ValueError, match="legacy fields"):
        validate_record("geometry_cluster_v2", {**_record_examples()["geometry_cluster_v2"], "normalized_cluster_margin": 1.0})


def test_shared_geometry_rejects_multiple_maximum_cliques(monkeypatch) -> None:
    rows = [
        {"worker_id": str(i), "canonical_annotation_id": f"a{i}", "geometry": {"valid": True, "tag": i}}
        for i in range(3)
    ]
    def similarity(left, right):
        edge = tuple(sorted((left["tag"], right["tag"])))
        score = 1.0 if edge in {(0, 1), (1, 2)} else 0.0
        return {"metric_compatible": True, "q_boundary": score, "q_wallwall": score}
    monkeypatch.setattr("tools.thesis_main.analysis.geometry_cluster_v2.pairwise_similarity", similarity)
    result = cluster_geometry_records(rows, min_q_boundary=.8, min_q_wallwall=.8)
    assert result["partition_status"] == "not_evaluable"
    assert result["largest_cluster_medoid_annotation_id"] == ""
    assert len(json.loads(result["ambiguity_candidates_json"])) == 2


def test_stage3_requires_c1_children_and_revalidates_method_sha(tmp_path: Path) -> None:
    gate_path, roster, enrollment, state = _formal_gate(tmp_path)
    assert validate_gate_file(gate_path)["STAGE3_LAUNCH_ALLOWED"] is True
    c1 = json.loads(Path(state["C1_EVIDENCE_FROZEN"]["path"]).read_text(encoding="utf-8"))
    c1["dependencies"] = c1["dependencies"][:-1]
    Path(state["C1_EVIDENCE_FROZEN"]["path"]).write_text(json.dumps(c1), encoding="utf-8")
    state["C1_EVIDENCE_FROZEN"]["sha256"] = sha256_file(Path(state["C1_EVIDENCE_FROZEN"]["path"]))
    assert build_gate(state, sha256_file(roster), sha256_file(enrollment), base_dir=tmp_path)["STAGE3_LAUNCH_ALLOWED"] is False
    gate = json.loads(gate_path.read_text(encoding="utf-8")); gate["method_contract_sha256"] = "0" * 64
    gate_path.write_text(json.dumps(gate), encoding="utf-8")
    with pytest.raises(ValueError, match="method contract"):
        validate_gate_file(gate_path)


def test_online_v1_requires_stage3_and_replay_is_consistent(tmp_path: Path) -> None:
    gate, roster, enrollment, _ = _formal_gate(tmp_path)
    candidate = _record_examples()["policy_candidate_v2"]
    candidate_roster = tmp_path / "candidate_roster.csv"
    with candidate_roster.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(candidate))
        writer.writeheader()
        writer.writerow({key: json.dumps(value) if isinstance(value, (dict, list)) else value for key, value in candidate.items()})
    policy_manifest = tmp_path / "strong_global_policy_manifest.json"
    policy_manifest.write_text("{}", encoding="utf-8")
    manifest = {"manifest_version": RULE_VERSION, "freeze_version": "f", "profile_version": "p", "scoring": {"d_cal_F_min": 0, "d_cal_F_max": 1, "family_activation_threshold": .5, "family_activation_margin": .1, "min_conditional_supported": 1, "lambda_B": 0, "lambda_P": 0, "max_total_adjustment": 0, "ranking_stability_margin": 0}, "scheduler": {"seed": 1, "formal_structure_min_k": 3, "offer_timeout": 1, "completion_timeout": 1, "max_offer_attempts": 1, "k_initial": 1, "standard_cap": 1, "exceptional_cap": 1}, "aggregation": {}, "feasibility": {}, "method_contract_sha256": sha256_file(METHOD_CONTRACT), "policy_manifest_sha256": sha256_file(policy_manifest), "candidate_roster_sha256": sha256_file(candidate_roster), "dependencies": [{"role": "stage3_freeze_gate", "path": str(gate), "sha256": sha256_file(gate)}, {"role": "strong_global_policy_manifest", "path": str(policy_manifest), "sha256": sha256_file(policy_manifest)}, {"role": "candidate_roster", "path": str(candidate_roster), "sha256": sha256_file(candidate_roster)}]}
    freeze_manifest = tmp_path / "v1_freeze_manifest.json"
    freeze_manifest.write_text(json.dumps(manifest), encoding="utf-8")
    state = {"task": {"task_id": "t", "d_cal_F": .5, "family_scores": {}, "risk_route": False}, "policy_arm": "strong_global", "available_worker_ids": ["1"], "remaining_capacity": {"1": 1}, "next_sequence": 1}
    replay_kwargs = {"stage3_gate": gate, "validation_roster": roster, "enrollment_registry": enrollment, "freeze_manifest": freeze_manifest, "freeze_manifest_sha256": sha256_file(freeze_manifest), "candidate_roster_csv": candidate_roster}
    ledger = tmp_path / "ledger.jsonl"
    kwargs = {**replay_kwargs, "ledger": ledger}
    with pytest.raises(ValueError, match="non-contract fields"):
        decide_next_offer({**state, "outcomes": {}}, decision_time="2026-07-29T00:00:00Z", **kwargs)
    with pytest.raises(ValueError, match="future or outcome"):
        decide_next_offer({**state, "task": {**state["task"], "realized_outcome": .9}}, decision_time="2026-07-29T00:00:00Z", **kwargs)
    with pytest.raises(ValueError, match="freeze manifest SHA mismatch"):
        decide_next_offer(state, decision_time="2026-07-29T00:00:00Z", **{**kwargs, "freeze_manifest_sha256": "0" * 64})
    decision = decide_next_offer(state, decision_time="2026-07-29T00:00:00Z", **kwargs)
    assert ledger.is_file()
    with pytest.raises(ValueError, match="strictly increasing"):
        append_decision(ledger, decision)
    audit = audit_ledger(
        ledger, lambda sequence: state,
        lambda replay_state, at: replay_next_offer(replay_state, decision_time=at, **replay_kwargs),
    )
    assert audit["replay_passed"] is True


def test_t1_launcher_executes_only_after_full_preflight(tmp_path: Path) -> None:
    gate, roster, enrollment, _ = _formal_gate(tmp_path)
    marker = tmp_path / "launched.txt"
    result = launch(gate, roster, enrollment, [sys.executable, "-c", f"from pathlib import Path; Path(r'{marker}').write_text('ok')"])
    assert result["launch_executed"] is True
    assert marker.read_text() == "ok"


def test_w034_original_only_branch_is_derived_from_canonical_provenance(tmp_path: Path, monkeypatch) -> None:
    def write(name: str, rows: list[dict]) -> Path:
        path = tmp_path / name
        with path.open("w", newline="", encoding="utf-8") as stream:
            writer = csv.DictWriter(stream, fieldnames=list(rows[0])); writer.writeheader(); writer.writerows(rows)
        return path
    eligibility = [
        {"schema_version": "assignment_evidence_v2", "canonical_annotation_id": "a0", "annotation_id": "a0", "worker_id": "34", "base_task_id": "t0", "condition": "manual", "assignment_provenance": "original_assignment", "formal_assignment_eligible": True, "gt_primary_analysis_eligible": True, "peer_analysis_eligible": True, "loo_medoid_analysis_eligible": True, "strict_loo_analysis_eligible": True, "structural_opportunity_eligible": True, "time_analysis_eligible": True, "semi_correction_analysis_eligible": True, "predictive_validity_analysis_eligible": True, "routing_feature_analysis_eligible": True},
        {"schema_version": "assignment_evidence_v2", "canonical_annotation_id": "a1", "annotation_id": "a1", "worker_id": "34", "base_task_id": "t1", "condition": "manual", "assignment_provenance": "authorized_replacement_assignment", "formal_assignment_eligible": True, "gt_primary_analysis_eligible": True, "peer_analysis_eligible": True, "loo_medoid_analysis_eligible": True, "strict_loo_analysis_eligible": True, "structural_opportunity_eligible": True, "time_analysis_eligible": True, "semi_correction_analysis_eligible": True, "predictive_validity_analysis_eligible": True, "routing_feature_analysis_eligible": True},
    ]
    write("c1_row_analysis_eligibility.csv", eligibility)
    base_rows = [{"canonical_annotation_id": annotation, "annotation_id": annotation, "worker_id": "34", "base_task_id": task, "value": "1"} for annotation, task in (("a0", "t0"), ("a1", "t1"))]
    for name in ("c1_gt_quality_analysis.csv", "geometry_worker_task_loo_analysis.csv", "geometry_worker_task_peer_analysis.csv", "structural_validation_analysis.csv"):
        write(name, base_rows)
    write("c1_worker_completion_audit.csv", [{"worker_id": "34", "completion_status": "completed"}])

    def fake_qgt(rows, estimator_contract):
        assert {row["canonical_annotation_id"] for row in rows} == {"a0"}
        return ([{"worker_id": "34", "Q_GT_EB": .8, "GT_support": 1}], [], {"status": "estimated"})
    def fake_structural(source, output, policy):
        assert "a1" not in source.read_text(encoding="utf-8")
        write_target = output
        with write_target.open("w", newline="", encoding="utf-8") as stream:
            writer = csv.DictWriter(stream, fieldnames=["worker_id", "F_struct_EB"]); writer.writeheader(); writer.writerow({"worker_id": "34", "F_struct_EB": .1})
        return {"status": "estimated"}
    def fake_profile(global_csv, loo_csv, structural_csv, completion_csv, output_dir, **kwargs):
        for path in (global_csv, loo_csv, structural_csv, kwargs["quality_csv"], kwargs["eligibility_csv"], kwargs["peer_csv"]):
            assert "a1" not in path.read_text(encoding="utf-8")
        write_target = output_dir / "c1_three_track_worker_state.csv"
        with write_target.open("w", newline="", encoding="utf-8") as stream:
            writer = csv.DictWriter(stream, fieldnames=["worker_id", "Q_GT_EB"]); writer.writeheader(); writer.writerow({"worker_id": "34", "Q_GT_EB": .8})
        return {"n_workers": 1}
    monkeypatch.setattr(rehearsal, "estimate_task_adjusted_qgt", fake_qgt)
    monkeypatch.setattr(rehearsal, "materialize_structural_eb", fake_structural)
    monkeypatch.setattr(rehearsal, "materialize_three_track_worker_state", fake_profile)
    profile = rehearsal._materialize_w034_original_only_profile(tmp_path, formal=False)
    assert profile.is_file()
    monkeypatch.setattr(
        rehearsal, "estimate_task_adjusted_qgt",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(ValueError("task-adjusted Q_GT requires at least two workers and two base tasks")),
    )
    assert rehearsal._materialize_w034_original_only_profile(tmp_path, formal=False) is None
    assert '"status": "not_evaluable"' in (tmp_path / "w034_original_only_branch" / "qgt_original_only_audit.json").read_text(encoding="utf-8")
