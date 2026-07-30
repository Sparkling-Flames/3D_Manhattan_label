"""Materialize the independent final pooled Calibration profile freeze."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from tools.thesis_main.analysis.paper_a_contracts import load_method_contract, sha256_file


def _read_json(path: Path) -> dict:
    if not path.is_file():
        raise FileNotFoundError(path)
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"expected JSON object: {path}")
    return payload


def _dependency(path: Path, role: str, method_sha: str, profile_version: str, cohort_id: str) -> dict:
    payload = _read_json(path)
    if payload.get("method_contract_sha256") not in (None, method_sha):
        raise ValueError(f"{role} method contract SHA drift")
    if payload.get("profile_version") not in (None, profile_version):
        raise ValueError(f"{role} profile version drift")
    if payload.get("cohort_id") not in (None, cohort_id):
        raise ValueError(f"{role} cohort drift")
    return {
        "role": role,
        "path": str(path),
        "sha256": sha256_file(path),
        "expected_schema": payload.get("schema_version", "json_object"),
        "required_status_field": "formal_ready",
        "required_status_value": True,
        "profile_version": profile_version,
        "cohort_id": cohort_id,
        "frozen": payload.get("formal_ready") is True,
    }


def materialize(
    *,
    output: Path,
    c1_evidence: Path,
    c2b_batch_a: Path,
    c2a_rp: Path,
    final_qgt: Path,
    pooled_profile: Path,
    enrollment_registry: Path,
    profile_version: str,
    cohort_id: str,
    c2b_batch_b: Path | None = None,
    method_contract: Path | None = None,
) -> dict:
    method_path = method_contract or Path(__file__).resolve().parents[3] / "docs" / "thesis_main" / "PAPER_A_METHOD_CONTRACT_CURRENT.json"
    method = load_method_contract(method_path)
    method_sha = sha256_file(method_path)
    evidence = _read_json(c1_evidence)
    if evidence.get("C1_EVIDENCE_FROZEN") is not True:
        raise ValueError("C1 evidence is not frozen")
    if any(evidence.get(key) is True for key in (
        "CALIBRATION_ENROLLMENT_CLOSED", "ALL_CALIBRATION_WORKERS_TERMINAL", "FINAL_POOLED_PROFILE_FROZEN"
    )):
        raise ValueError("C1 evidence still carries pooled closure state")
    dependencies = [
        _dependency(c1_evidence, "C1_EVIDENCE_FROZEN", method_sha, profile_version, cohort_id),
        _dependency(c2b_batch_a, "C2B_BATCH_A_CLOSEOUT_FROZEN", method_sha, profile_version, cohort_id),
        _dependency(c2a_rp, "C2A_RP_CLOSEOUT_FROZEN", method_sha, profile_version, cohort_id),
        _dependency(final_qgt, "FINAL_C1_C2_Q_GT_MODEL_FROZEN", method_sha, profile_version, cohort_id),
        _dependency(pooled_profile, "POOLED_WORKER_PROFILE_FROZEN", method_sha, profile_version, cohort_id),
        _dependency(enrollment_registry, "CALIBRATION_ENROLLMENT_REGISTRY_FROZEN", method_sha, profile_version, cohort_id),
    ]
    if c2b_batch_b is not None:
        dependencies.append(_dependency(c2b_batch_b, "C2B_BATCH_B_CLOSEOUT_FROZEN", method_sha, profile_version, cohort_id))
    payload = {
        "schema_version": "paper_a_final_pooled_profile_freeze_v1",
        "artifact_role": "FINAL_POOLED_PROFILE_FROZEN",
        "contract_role": "generated_subordinate",
        "formal_ready": True,
        "profile_version": profile_version,
        "cohort_id": cohort_id,
        "method_contract_version": method["contract_version"],
        "method_contract_sha256": method_sha,
        "C1_EVIDENCE_FROZEN": True,
        "C2B_BATCH_A_CLOSEOUT_FROZEN": True,
        "C2B_BATCH_B_CLOSEOUT_FROZEN": c2b_batch_b is not None,
        "C2A_RP_CLOSEOUT_FROZEN": True,
        "FINAL_C1_C2_Q_GT_MODEL_FROZEN": True,
        "POOLED_WORKER_PROFILE_FROZEN": True,
        "CALIBRATION_ENROLLMENT_CLOSED": True,
        "ALL_CALIBRATION_WORKERS_TERMINAL": True,
        "dependencies": dependencies,
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return payload


def main() -> int:
    parser = argparse.ArgumentParser()
    for name in ("c1-evidence", "c2b-batch-a", "c2a-rp", "final-qgt", "pooled-profile", "enrollment-registry", "output"):
        parser.add_argument(f"--{name}", type=Path, required=True)
    parser.add_argument("--c2b-batch-b", type=Path)
    parser.add_argument("--method-contract", type=Path)
    parser.add_argument("--profile-version", required=True)
    parser.add_argument("--cohort-id", required=True)
    args = parser.parse_args()
    materialize(
        output=args.output, c1_evidence=args.c1_evidence, c2b_batch_a=args.c2b_batch_a,
        c2a_rp=args.c2a_rp, final_qgt=args.final_qgt, pooled_profile=args.pooled_profile,
        enrollment_registry=args.enrollment_registry, profile_version=args.profile_version,
        cohort_id=args.cohort_id, c2b_batch_b=args.c2b_batch_b, method_contract=args.method_contract,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
