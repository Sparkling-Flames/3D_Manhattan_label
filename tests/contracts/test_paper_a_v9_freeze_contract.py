import json
import csv
from pathlib import Path

import pytest

from tools.thesis_main.analysis.materialize_final_pooled_profile_freeze import materialize
from tools.thesis_main.analysis.paper_a_contracts import METHOD_CONTRACT, load_method_contract, sha256_file


def _artifact(path: Path, schema: str, role: str) -> Path:
    path.write_text(json.dumps({
        "schema_version": schema,
        "artifact_role": role,
        "contract_role": "generated_subordinate",
        "formal_ready": True,
        "profile_version": "p1",
        "cohort_id": "c1",
        "method_contract_version": load_method_contract()["contract_version"],
        "method_contract_sha256": sha256_file(METHOD_CONTRACT),
        "blockers": [],
        "dependencies": [],
    }), encoding="utf-8")
    return path


def _closed_reference_review(path: Path) -> Path:
    fields = [
        "schema_version", "base_task_id", "registry_status_before_review", "reference_status_before_review",
        "reference_normalizer_status_before_review", "geometry_reference_ready_before_review",
        "review_status", "review_disposition", "reviewer_blinding", "review_evidence", "reviewed_by", "reviewed_at",
        "original_reference_sha256", "method_contract_sha256",
    ]
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerow({
            "schema_version": "paper_a_reference_conflict_review_record_v2",
            "base_task_id": "known",
            "registry_status_before_review": "approved_by_frozen_reference_policy",
            "reference_status_before_review": "use_existing_public_gt_as_is",
            "reference_normalizer_status_before_review": "passed",
            "geometry_reference_ready_before_review": "true",
            "review_status": "closed",
            "review_disposition": "retain_original",
            "reviewer_blinding": "worker_and_analysis_metric_blinded",
            "review_evidence": "manual_scene_review_record",
            "reviewed_by": "reviewer-1",
            "reviewed_at": "2026-08-05T12:00:00Z",
            "original_reference_sha256": "a" * 64,
            "method_contract_sha256": sha256_file(METHOD_CONTRACT),
        })
    return path


def test_final_pooled_profile_is_independent_from_c1_evidence(tmp_path: Path) -> None:
    c1 = _artifact(tmp_path / "c1.json", "c1_evidence_freeze_manifest_v6", "C1_EVIDENCE_FROZEN")
    payload = json.loads(c1.read_text(encoding="utf-8"))
    payload["C1_EVIDENCE_FROZEN"] = True
    c1.write_text(json.dumps(payload), encoding="utf-8")
    inputs = {
        "c1_evidence": c1,
        "c2b_batch_a": _artifact(tmp_path / "batch_a.json", "c2b_closeout_v2", "C2B_BATCH_A_CLOSEOUT_FROZEN"),
        "c2a_rp": _artifact(tmp_path / "c2a.json", "c2a_rp_closeout_v2", "C2A_RP_CLOSEOUT_FROZEN"),
        "final_qgt": _artifact(tmp_path / "qgt.json", "final_c1_c2_qgt_model_v1", "FINAL_C1_C2_Q_GT_MODEL_FROZEN"),
        "pooled_profile": _artifact(tmp_path / "profile.json", "worker_profile_v2", "POOLED_WORKER_PROFILE_FROZEN"),
        "enrollment_registry": tmp_path / "enrollment.csv",
        "profile_version": "p1",
        "cohort_id": "c1",
        "reference_conflict_review_record": _closed_reference_review(tmp_path / "reference_review.csv"),
    }
    inputs["enrollment_registry"].write_text(
        "worker_id,enrollment_batch,rolling_activated,admission_status,terminal_status,enrolled_at\n"
        "1,original,false,pass,completed,2026-07-01T00:00:00Z\n",
        encoding="utf-8",
    )
    output = tmp_path / "final.json"
    result = materialize(output=output, **inputs)
    assert result["schema_version"] == "paper_a_final_pooled_profile_freeze_v1"
    assert result["C1_EVIDENCE_FROZEN"] is True
    assert result["CALIBRATION_ENROLLMENT_CLOSED"] is True
    assert all(dep["role"] != "FINAL_POOLED_PROFILE_FROZEN" for dep in result["dependencies"])

    payload["FINAL_POOLED_PROFILE_FROZEN"] = True
    c1.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(ValueError, match="pooled closure state"):
        materialize(output=tmp_path / "rejected.json", **inputs)


def test_v9_contract_has_separate_pooled_schema() -> None:
    contract = load_method_contract()
    assert contract["schema_version"] == "paper_a_method_contract_v9"
    assert contract["contract_version"] == "paper_a_method_20260810_v20"
    assert contract["c2"]["c2_a_rp_task_support_cap"] == {
        "block1_historical": 2,
        "blocks2_to_5": 4,
        "future_blocks_preassigned": False,
        "future_block_requires_prior_closeout_and_real_reestimate": True,
    }
    assert contract["c2"]["c2_a_rp_instruction"]["blocks1_to_5"] == "scope_instruction_v1"
    assert contract["full_materialization_procedure"]["calibration_only"] is True
    procedure = METHOD_CONTRACT.parents[2] / contract["full_materialization_procedure"]["path"]
    assert sha256_file(procedure) == contract["full_materialization_procedure"]["sha256"]
    procedure_payload = json.loads(procedure.read_text(encoding="utf-8"))
    assert procedure_payload["weight_and_cap_selection"]["eligible_data"] == "Calibration_only"
    assert "V1_p_value" in procedure_payload["prohibited_inputs"]
    assert contract["predispatch_amendment"]["candidate_specific_relaxation"] is False
    assert contract["geometry_cluster"]["similarity_cutoff"] == .95
    assert contract["geometry_cluster"]["sensitivity_cutoffs"] == [.93, .97]
    assert contract["geometry_cluster"]["require_pointwise_correspondence"] is True
    assert contract["peer"]["bootstrap_statistic"] == "task_equal_median"
    assert contract["peer"]["stable_includes"] == ["unimodal", "dominant_with_dissent"]
    assert "paper_a_final_pooled_profile_freeze_v1" in contract["artifact_schemas"]
    assert "FINAL_POOLED_PROFILE_FROZEN" in contract["stage3"]["required_roles"]
    assert contract["c2"]["c2_a_rp_formal_target"] == "risk_slope_precision"
    assert contract["c2"]["c2_a_rp_max_tasks_per_worker"] == 10
    assert contract["c2"]["c2_a_rp_block"]["allowed_additional_tasks"] == [0, 2, 4, 6, 8, 10]
    assert "STRONG_GLOBAL_FROZEN" not in contract["stage3"]["required_roles"]
    assert "STRONG_GLOBAL_FROZEN" in contract["stage3"]["v1_required_roles"]
