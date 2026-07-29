"""Deterministically audit an append-only V1 decision ledger."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Callable


def audit_ledger(ledger: Path, state_at_sequence: Callable[[int], dict[str, Any]], decide: Callable[[dict[str, Any], str], dict[str, Any]]) -> dict[str, Any]:
    rows = [json.loads(line) for line in ledger.read_text(encoding="utf-8").splitlines() if line.strip()]
    mismatches = []
    for expected_sequence, recorded in enumerate(rows, 1):
        if int(recorded.get("sequence", 0)) != expected_sequence:
            raise ValueError("V1 ledger is not append-only sequential evidence")
        expected = decide(state_at_sequence(expected_sequence), recorded["decision_time"])
        if expected.get("offered_worker_id") != recorded.get("offered_worker_id") or expected.get("state_snapshot_sha256") != recorded.get("state_snapshot_sha256"):
            mismatches.append(expected_sequence)
    return {"schema_version": "v1_replay_audit_v2", "artifact_role": "deterministic_replay_audit", "formal_assignment_generated": False, "event_count": len(rows), "mismatch_sequences": mismatches, "replay_passed": not mismatches}
