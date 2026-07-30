import json
from pathlib import Path

import pytest

from tools.thesis_main.analysis.materialize_final_pooled_profile_freeze import materialize
from tools.thesis_main.analysis.paper_a_contracts import METHOD_CONTRACT, load_method_contract, sha256_file


def _artifact(path: Path, schema: str) -> Path:
    path.write_text(json.dumps({
        "schema_version": schema,
        "formal_ready": True,
        "profile_version": "p1",
        "cohort_id": "c1",
        "method_contract_sha256": sha256_file(METHOD_CONTRACT),
        "blockers": [],
        "dependencies": [],
    }), encoding="utf-8")
    return path


def test_final_pooled_profile_is_independent_from_c1_evidence(tmp_path: Path) -> None:
    c1 = _artifact(tmp_path / "c1.json", "c1_evidence_freeze_manifest_v6")
    payload = json.loads(c1.read_text(encoding="utf-8"))
    payload["C1_EVIDENCE_FROZEN"] = True
    c1.write_text(json.dumps(payload), encoding="utf-8")
    inputs = {
        "c1_evidence": c1,
        "c2b_batch_a": _artifact(tmp_path / "batch_a.json", "batch_a"),
        "c2a_rp": _artifact(tmp_path / "c2a.json", "c2a"),
        "final_qgt": _artifact(tmp_path / "qgt.json", "qgt"),
        "pooled_profile": _artifact(tmp_path / "profile.json", "worker_profile_v2"),
        "enrollment_registry": _artifact(tmp_path / "enrollment.json", "enrollment"),
        "profile_version": "p1",
        "cohort_id": "c1",
    }
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
    assert "paper_a_final_pooled_profile_freeze_v1" in contract["artifact_schemas"]
    assert "FINAL_POOLED_PROFILE_FROZEN" in contract["stage3"]["required_roles"]
