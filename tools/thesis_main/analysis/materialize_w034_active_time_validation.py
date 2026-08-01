"""Validate the W034 active-time sentinel without imputing historical time."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def sha256_bundle(path: Path) -> str:
    """Hash one file or a directory as a deterministic immutable bundle."""
    if path.is_file():
        return hashlib.sha256(path.read_bytes()).hexdigest()
    if not path.is_dir():
        raise FileNotFoundError(path)
    rows = []
    for item in sorted((item for item in path.rglob("*") if item.is_file()), key=lambda item: item.relative_to(path).as_posix()):
        rows.append({"size": item.stat().st_size, "sha256": hashlib.sha256(item.read_bytes()).hexdigest()})
    if not rows:
        raise ValueError("W034 raw active-log bundle is empty")
    payload = json.dumps(sorted(rows, key=lambda row: (row["sha256"], row["size"])), sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _truth(value: Any) -> bool:
    return str(value).strip().lower() in {"1", "true", "yes", "passed", "valid"}


def _read(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as stream:
        return list(csv.DictReader(stream))


def _timestamp(value: Any) -> datetime:
    parsed = datetime.fromisoformat(str(value).strip().replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def validate_sentinel(spec: dict[str, Any], active_rows: list[dict[str, str]], runtime_rows: list[dict[str, str]], *, raw_log_bundle_sha256: str, derived_audit_sha256: str, raw_log_bundle_path: Path | None = None, derived_audit_path: Path | None = None) -> dict[str, Any]:
    required = ("worker_id", "project_id", "runtime_task_id", "annotation_id", "validation_timestamp", "reviewed_by")
    missing = [field for field in required if not str(spec.get(field, "")).strip()]
    if missing:
        raise ValueError("sentinel specification missing:" + ",".join(missing))
    if str(spec["worker_id"]).lstrip("W0") not in {"34", ""}:
        raise ValueError("W034 sentinel must bind worker 34")
    validation_timestamp = _timestamp(spec["validation_timestamp"])
    for label, digest in (("raw bundle", raw_log_bundle_sha256), ("derived audit", derived_audit_sha256)):
        if len(str(digest)) != 64 or any(char not in "0123456789abcdefABCDEF" for char in str(digest)):
            raise ValueError(f"W034 sentinel requires a SHA-256-bound {label}")
    runtime = [row for row in runtime_rows if str(row.get("project_id", "")) == str(spec["project_id"]) and str(row.get("ls_runtime_task_id") or row.get("runtime_task_id") or "") == str(spec["runtime_task_id"])]
    active = [row for row in active_rows if str(row.get("project_id", "")) == str(spec["project_id"]) and str(row.get("ls_runtime_task_id") or row.get("runtime_task_id") or row.get("task_id") or "") == str(spec["runtime_task_id"]) and str(row.get("worker_id") or row.get("annotator_id") or "").lstrip("W0") == "34" and str(row.get("annotation_id") or row.get("canonical_annotation_id") or "") == str(spec["annotation_id"])]
    row = active[0] if len(active) == 1 else {}
    owner_value = row.get("owner_valid", row.get("annotation_owner_valid")) if row else None
    checks = {
        "annotation_owner_binding": len(active) == 1,
        "owner_validation_field_present": owner_value not in {None, ""},
        "active_log_identity": len(active) == 1 and _truth(owner_value),
        "project_runtime_task_mapping": len(runtime) == 1,
        "session_count": int(float(row.get("active_time_session_count") or row.get("session_count") or 0)) >= 1 if row else False,
        "start_end": bool(row.get("started_at") or row.get("active_started_at")) and bool(row.get("completed_at") or row.get("active_completed_at")) if row else False,
        "active_duration": float(row.get("active_time") or row.get("active_duration_seconds") or 0) > 0 if row else False,
        "duplicate_session_unambiguous": not _truth(row.get("duplicate_time_ambiguous")) if row else False,
    }
    passed = all(checks.values())
    return {
        "schema_version": "w034_active_time_validation_manifest_v2",
        "sentinel_task_identity": {key: str(spec[key]) for key in ("project_id", "runtime_task_id", "annotation_id")},
        "worker_id": "34", "validation_timestamp": validation_timestamp.isoformat(),
        "raw_active_log_bundle_sha256": raw_log_bundle_sha256,
        "derived_active_time_audit_sha256": derived_audit_sha256,
        "raw_active_log_bundle_path": str(raw_log_bundle_path.resolve()) if raw_log_bundle_path else "",
        "derived_active_time_audit_path": str(derived_audit_path.resolve()) if derived_audit_path else "",
        "sentinel_annotation_identity": f"{spec['project_id']}|{spec['runtime_task_id']}|34|{spec['annotation_id']}",
        "reviewed_by": spec["reviewed_by"],
        "validation_checks": checks, "validation_result": "passed" if passed else "failed",
        "active_time_expected_disposition": "authorized_rows_after_validation_only" if passed else "fail_closed",
    }


def validate_preassignment_operator_attestation(
    attestation: dict[str, Any], *, authorized_reassignment_manifest_sha256: str,
) -> dict[str, Any]:
    """Validate retrospective documentation without representing it as a sentinel."""
    required = (
        "worker_id", "verified_by", "time_basis", "timestamp_precision",
        "authorized_reassignment_manifest_sha256", "timing_validation_basis",
        "timing_protocol_deviation",
    )
    missing = [field for field in required if not str(attestation.get(field, "")).strip()]
    if missing:
        raise ValueError("W034 preassignment timing attestation missing:" + ",".join(missing))
    if attestation.get("schema_version") != "w034_preassignment_timing_verification_attestation_v1":
        raise ValueError("unsupported W034 preassignment timing attestation")
    if str(attestation["worker_id"]).strip().upper().removeprefix("W").lstrip("0") != "34":
        raise ValueError("W034 preassignment timing attestation is bound to the wrong worker")
    timestamp_precision = str(attestation["timestamp_precision"]).strip().lower()
    if timestamp_precision not in {"unavailable", "date", "second"}:
        raise ValueError("W034 preassignment timing attestation has unsupported timestamp precision")
    verification_timestamp = ""
    if timestamp_precision != "unavailable":
        if not str(attestation.get("verification_timestamp", "")).strip():
            raise ValueError("W034 preassignment timing attestation lacks the declared timestamp")
        verification_timestamp = _timestamp(attestation["verification_timestamp"]).isoformat()
    declared_sha = str(attestation["authorized_reassignment_manifest_sha256"]).strip()
    expected_sha = str(authorized_reassignment_manifest_sha256).strip()
    checks = {
        "operator_verified_before_authorized_tasks": _truth(attestation.get("operator_verified_before_authorized_tasks")),
        "operator_recollection_basis": str(attestation.get("time_basis", "")) == "operator_recollection",
        "authorized_reassignment_manifest_sha256_matches": declared_sha == expected_sha and len(expected_sha) == 64,
        "timing_validation_basis": str(attestation.get("timing_validation_basis", "")) == "preassignment_operator_verification",
        "retrospective_documentation": str(attestation.get("timing_protocol_deviation", "")) == "retrospective_manifest_documentation",
        "annotation_exact_not_claimed": str(attestation.get("annotation_exact_validated", "")).lower() in {"false", "0"},
    }
    return {
        "schema_version": "w034_preassignment_timing_verification_attestation_v1",
        "worker_id": "34",
        "verification_timestamp": verification_timestamp,
        "time_basis": "operator_recollection",
        "timestamp_precision": timestamp_precision,
        "verified_by": str(attestation["verified_by"]).strip(),
        "authorized_reassignment_manifest_sha256": declared_sha,
        "timing_validation_basis": "preassignment_operator_verification",
        "timing_protocol_deviation": "retrospective_manifest_documentation",
        "annotation_exact_validated": False,
        "attestation_checks": checks,
        "attestation_valid": all(checks.values()),
    }


def materialize(spec_json: Path, active_csv: Path, runtime_csv: Path, raw_log_bundle: Path, output_json: Path) -> dict[str, Any]:
    result = validate_sentinel(
        json.loads(spec_json.read_text(encoding="utf-8")), _read(active_csv), _read(runtime_csv),
        raw_log_bundle_sha256=sha256_bundle(raw_log_bundle),
        derived_audit_sha256=hashlib.sha256(active_csv.read_bytes()).hexdigest(),
        raw_log_bundle_path=raw_log_bundle, derived_audit_path=active_csv,
    )
    output_json.parent.mkdir(parents=True, exist_ok=True)
    output_json.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--sentinel-spec", type=Path, required=True)
    parser.add_argument("--active-time-audit", type=Path, required=True)
    parser.add_argument("--runtime-mapping", type=Path, required=True)
    parser.add_argument("--raw-active-log-bundle", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(materialize(args.sentinel_spec, args.active_time_audit, args.runtime_mapping, args.raw_active_log_bundle, args.output), indent=2))


if __name__ == "__main__":
    main()
