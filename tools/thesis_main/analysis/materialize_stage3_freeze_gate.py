"""Recursive, SHA-bound, fail-closed Stage 3 dependency closure."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

from tools.thesis_main.analysis.paper_a_contracts import METHOD_CONTRACT, load_method_contract, sha256_file

METHOD = load_method_contract()
REQUIRED_GATES = tuple(METHOD["stage3"]["required_roles"])
REQUIRED_CHILD_ROLES = {
    role: frozenset(children)
    for role, children in METHOD["stage3"].get("required_child_roles", {}).items()
}


def _resolve(path_value: Any, base: Path) -> Path:
    path = Path(str(path_value))
    return path if path.is_absolute() else (base / path).resolve()


def _validate_dependency(item: dict[str, Any], base: Path, trail: str) -> tuple[dict[str, Any], list[str]]:
    blockers: list[str] = []
    required = ("role", "path", "sha256", "expected_schema", "required_status_field", "required_status_value", "profile_version", "cohort_id")
    missing = [field for field in required if field not in item or str(item[field]).strip() == ""]
    if missing or item.get("frozen") is not True:
        return dict(item), [f"{trail}:incomplete_dependency:{','.join(missing)}"]
    path = _resolve(item.get("resolved_path") or item["path"], base)
    if not path.is_file() or sha256_file(path) != str(item["sha256"]):
        return {**item, "resolved_path": str(path)}, [f"{trail}:missing_or_stale_sha"]
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return {**item, "resolved_path": str(path)}, [f"{trail}:dependency_not_json"]
    if payload.get("schema_version") != item["expected_schema"]:
        blockers.append(f"{trail}:schema_mismatch")
    if payload.get(item["required_status_field"]) != item["required_status_value"]:
        blockers.append(f"{trail}:required_status_not_met")
    if payload.get("blockers"):
        blockers.append(f"{trail}:nested_blockers")
    if "profile_version" not in payload or str(payload["profile_version"]) != str(item["profile_version"]):
        blockers.append(f"{trail}:profile_mismatch")
    if "cohort_id" not in payload or str(payload["cohort_id"]) != str(item["cohort_id"]):
        blockers.append(f"{trail}:cohort_mismatch")
    children = []
    child_roles: list[str] = []
    for index, child in enumerate(payload.get("dependencies", [])):
        child_roles.append(str(child.get("role", "")))
        resolved, child_blockers = _validate_dependency(child, path.parent, f"{trail}/{index}")
        children.append(resolved)
        blockers.extend(child_blockers)
    if len(child_roles) != len(set(child_roles)):
        blockers.append(f"{trail}:duplicate_child_role")
    required_children = REQUIRED_CHILD_ROLES.get(str(item.get("role", "")), frozenset())
    missing_children = sorted(required_children - set(child_roles))
    if missing_children:
        blockers.append(f"{trail}:missing_required_children:{','.join(missing_children)}")
    if str(item.get("role")) == "C1_EVIDENCE_FROZEN" and payload.get("method_contract_sha256") != sha256_file(METHOD_CONTRACT):
        blockers.append(f"{trail}:method_contract_sha_mismatch")
    if str(item.get("role")) == "C1_EVIDENCE_FROZEN":
        for state in ("CALIBRATION_ENROLLMENT_CLOSED", "ALL_CALIBRATION_WORKERS_TERMINAL", "FINAL_POOLED_PROFILE_FROZEN"):
            if payload.get(state) is not True:
                blockers.append(f"{trail}:{state.lower()}_not_met")
    return {**item, "resolved_path": str(path), "dependencies": children}, blockers


def build_gate(state: dict[str, Any], roster_sha256: str, enrollment_sha256: str, *, base_dir: Path = Path(".")) -> dict[str, Any]:
    blockers: list[str] = []
    dependencies: list[dict[str, Any]] = []
    gate_values: dict[str, bool] = {}
    for role in REQUIRED_GATES:
        item = state.get(role)
        if not isinstance(item, dict):
            gate_values[role] = False
            blockers.append(f"{role}:missing_dependency")
            continue
        resolved, errors = _validate_dependency({**item, "role": role}, base_dir, role)
        dependencies.append(resolved)
        gate_values[role] = not errors
        blockers.extend(errors)
    if not roster_sha256 or not enrollment_sha256:
        blockers.append("roster_or_enrollment_sha_missing")
    return {
        "schema_version": "paper_a_stage3_freeze_gate_v3", "formal_ready": not blockers,
        **gate_values, "dependencies": dependencies,
        "validation_roster_sha256": roster_sha256, "enrollment_registry_sha256": enrollment_sha256,
        "method_contract_version": METHOD["contract_version"],
        "method_contract_sha256": sha256_file(METHOD_CONTRACT),
        "STAGE3_LAUNCH_ALLOWED": not blockers, "blockers": blockers,
    }


def validate_gate_file(path: Path) -> dict[str, Any]:
    gate = json.loads(path.read_text(encoding="utf-8"))
    if gate.get("schema_version") != "paper_a_stage3_freeze_gate_v3" or gate.get("STAGE3_LAUNCH_ALLOWED") is not True:
        raise ValueError("Stage 3 freeze gate is missing or closed")
    if any(gate.get(role) is not True for role in REQUIRED_GATES) or len(gate.get("dependencies", [])) != len(REQUIRED_GATES):
        raise ValueError("Stage 3 freeze gate does not contain all required roles")
    if gate.get("method_contract_version") != METHOD["contract_version"] or gate.get("method_contract_sha256") != sha256_file(METHOD_CONTRACT):
        raise ValueError("Stage 3 method contract version or SHA is stale")
    blockers = []
    for index, item in enumerate(gate.get("dependencies", [])):
        _, errors = _validate_dependency(item, path.parent, f"gate/{index}")
        blockers.extend(errors)
    if blockers:
        raise ValueError("Stage 3 dependency closure is stale:" + ";".join(blockers))
    return gate


def assert_frozen_roster(gate: dict[str, Any], roster_path: Path, enrollment_path: Path) -> None:
    if gate.get("STAGE3_LAUNCH_ALLOWED") is not True:
        raise ValueError("Stage 3 freeze gate is not open")
    if gate.get("validation_roster_sha256") != sha256_file(roster_path) or gate.get("enrollment_registry_sha256") != sha256_file(enrollment_path):
        raise ValueError("validation roster or enrollment registry changed after freeze")


def materialize(state_json: Path, roster_csv: Path, enrollment_csv: Path, output_json: Path) -> dict[str, Any]:
    raw = json.loads(state_json.read_text(encoding="utf-8"))
    gate = build_gate(raw.get("gates", raw), sha256_file(roster_csv), sha256_file(enrollment_csv), base_dir=state_json.parent)
    output_json.parent.mkdir(parents=True, exist_ok=True)
    output_json.write_text(json.dumps(gate, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return gate


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--state", type=Path, required=True); parser.add_argument("--validation-roster", type=Path, required=True)
    parser.add_argument("--enrollment-registry", type=Path, required=True); parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(); result = materialize(args.state, args.validation_roster, args.enrollment_registry, args.output)
    if not result["STAGE3_LAUNCH_ALLOWED"]: raise SystemExit("Stage 3 gate blocked:" + ";".join(result["blockers"]))


if __name__ == "__main__": main()
