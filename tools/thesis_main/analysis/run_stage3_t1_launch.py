"""Fail-closed T1 launcher that consumes the recursive Stage 3 closure."""

from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path

from tools.thesis_main.analysis.materialize_stage3_freeze_gate import assert_frozen_roster, validate_gate_file


def preflight(gate_path: Path, validation_roster: Path, enrollment_registry: Path) -> dict:
    gate = validate_gate_file(gate_path)
    assert_frozen_roster(gate, validation_roster, enrollment_registry)
    return {"schema_version": "paper_a_t1_launch_preflight_v1", "formal_ready": True, "stage3_gate": str(gate_path)}


def launch(gate_path: Path, validation_roster: Path, enrollment_registry: Path, command: list[str]) -> dict:
    result = preflight(gate_path, validation_roster, enrollment_registry)
    if not command:
        raise ValueError("T1 launch command is required after preflight")
    completed = subprocess.run(command, check=False)
    if completed.returncode != 0:
        raise RuntimeError(f"T1 command failed with exit code {completed.returncode}")
    return {**result, "launch_executed": True, "command": command, "returncode": completed.returncode}


def main() -> None:
    parser = argparse.ArgumentParser(); parser.add_argument("--stage3-gate", type=Path, required=True)
    parser.add_argument("--validation-roster", type=Path, required=True); parser.add_argument("--enrollment-registry", type=Path, required=True)
    parser.add_argument("command", nargs=argparse.REMAINDER)
    args = parser.parse_args(); print(json.dumps(launch(args.stage3_gate, args.validation_roster, args.enrollment_registry, args.command), indent=2))


if __name__ == "__main__": main()
