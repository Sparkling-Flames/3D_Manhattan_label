"""SHA-bound fail-closed gate for launching Paper A Stage 3 (T1/V1)."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

REQUIRED_GATES = (
    "CALIBRATION_ENROLLMENT_CLOSED", "ALL_CALIBRATION_WORKERS_TERMINAL",
    "C1_EVIDENCE_FROZEN", "C2_B_FROZEN", "C2_A_RP_CLOSED",
    "FINAL_POOLED_PROFILE_FROZEN", "STRONG_GLOBAL_FROZEN", "FULL_POLICY_FROZEN",
    "VALIDATION_ROSTER_FROZEN", "SAP_FROZEN",
)


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build_gate(state: dict[str, Any], roster_sha256: str, enrollment_sha256: str) -> dict[str, Any]:
    blockers: list[str] = []
    dependencies: dict[str, str] = {}
    gate_values: dict[str, bool] = {}
    for name in REQUIRED_GATES:
        item = state.get(name)
        passed = isinstance(item, dict) and item.get("frozen") is True and bool(item.get("sha256"))
        gate_values[name] = passed
        if passed:
            dependencies[name] = str(item["sha256"])
        else:
            blockers.append(f"{name}:missing_sha_bound_freeze")
    if not roster_sha256 or not enrollment_sha256:
        blockers.append("roster_or_enrollment_sha_missing")
    return {
        "schema_version": "paper_a_stage3_freeze_gate_v2", **gate_values,
        "gate_dependency_sha256": dependencies,
        "validation_roster_sha256": roster_sha256,
        "enrollment_registry_sha256": enrollment_sha256,
        "STAGE3_LAUNCH_ALLOWED": not blockers, "blockers": blockers,
    }


def assert_frozen_roster(gate: dict[str, Any], roster_path: Path, enrollment_path: Path) -> None:
    if gate.get("STAGE3_LAUNCH_ALLOWED") is not True:
        raise ValueError("Stage 3 freeze gate is not open")
    if gate.get("validation_roster_sha256") != _sha(roster_path) or gate.get("enrollment_registry_sha256") != _sha(enrollment_path):
        raise ValueError("validation roster or enrollment registry changed after freeze")


def materialize(state_json: Path, roster_csv: Path, enrollment_csv: Path, output_json: Path) -> dict[str, Any]:
    raw = json.loads(state_json.read_text(encoding="utf-8"))
    state = raw.get("gates", raw)
    resolved: dict[str, Any] = {}
    for name in REQUIRED_GATES:
        item = state.get(name)
        if not isinstance(item, dict) or item.get("frozen") is not True:
            resolved[name] = item
            continue
        path = Path(str(item.get("path", "")))
        if not path.is_absolute():
            path = (state_json.parent / path).resolve()
        actual = _sha(path) if path.exists() and path.is_file() else ""
        resolved[name] = {**item, "sha256": actual if actual == str(item.get("sha256", "")) else ""}
    gate = build_gate(resolved, _sha(roster_csv), _sha(enrollment_csv))
    output_json.parent.mkdir(parents=True, exist_ok=True)
    output_json.write_text(json.dumps(gate, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return gate


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--state", type=Path, required=True)
    parser.add_argument("--validation-roster", type=Path, required=True)
    parser.add_argument("--enrollment-registry", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = materialize(args.state, args.validation_roster, args.enrollment_registry, args.output)
    if not result["STAGE3_LAUNCH_ALLOWED"]:
        raise SystemExit("Stage 3 gate blocked:" + ";".join(result["blockers"]))
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
