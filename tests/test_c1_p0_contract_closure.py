from __future__ import annotations

import json
import time

import pytest

from tools.thesis_main.analysis.geometry_consensus.pairwise import cyclic_order_correspondence
from tools.thesis_main.analysis.geometry_consensus.representation import normalize_geometry
from tools.thesis_main.analysis.geometry_consensus.stability import stability_summary
from tools.thesis_main.analysis.materialize_model_issue_harmonization import _validate_amendments
from tools.thesis_main.analysis.routing.temporal_replay import _fold_for_base, _load_policy_manifest, _validate_policy
from tools.thesis_main.analysis.run_c1_closeout_dryrun_chain import build_gate_summary
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


def _record(worker: str, offset: int = 0) -> dict:
    return {
        "worker_id": worker,
        "geometry": normalize_geometry([[100, 100 + offset], [100, 400], [500, 100 + offset], [500, 400]]),
    }


def test_geometry_medoid_tie_and_high_k_is_non_recursive() -> None:
    tied = stability_summary([_record("w1"), _record("w2")])
    assert tied["medoid_ambiguous"] is True
    assert tied["medoid_boundary_worker_id"] == ""
    started = time.monotonic()
    result = stability_summary([_record(f"w{i}", i % 5) for i in range(22)], grid=32)
    assert result["valid_k"] == 22
    assert time.monotonic() - started < 30


def test_policy_manifest_relative_path_and_tampering(tmp_path) -> None:
    artifact = tmp_path / "policy.json"
    artifact.write_text("{}", encoding="utf-8")
    fit_base = next(value for value in (f"fit-{i}" for i in range(100)) if _fold_for_base(value, 2) == 1)
    manifest = tmp_path / "manifest.json"
    manifest.write_text(json.dumps({"0": {"policy_artifact_id": "p0", "policy_artifact_path": "policy.json", "policy_artifact_sha256": sha256_file(artifact), "rule_version": "r1", "fit_folds": [1], "fit_base_task_ids": [fit_base]}}), encoding="utf-8")
    policy = _load_policy_manifest(manifest)[0]
    assert policy["policy_artifact_path"] == str(artifact.resolve())
    assert _validate_policy(policy, 0, 2)["policy_validation_status"] == "verified"
    artifact.write_text('{"tampered":true}', encoding="utf-8")
    with pytest.raises(ValueError, match="SHA256"):
        _validate_policy(policy, 0, 2)


def test_formal_gate_requires_separate_adjudication_manifest(tmp_path) -> None:
    summary = build_gate_summary(
        {"canonical_meta_fresh": True, "n_quality_rows": 1, "r_u_estimated": True, "blockers": []},
        {"r_u_estimated": True, "r_u_freeze": True},
        {},
        {"c2_freeze": True},
        {"full_profile_ready": True, "pending_adjudication_count": 0},
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
