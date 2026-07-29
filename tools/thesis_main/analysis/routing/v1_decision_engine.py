"""Prospective V1 next-offer engine with append-only evidence."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from tools.thesis_main.analysis.paper_a_contracts import validate_record
from tools.thesis_main.analysis.materialize_stage3_freeze_gate import assert_frozen_roster, validate_gate_file
from tools.thesis_main.analysis.routing.v1_policy import rank_candidates


def _time(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None: parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


VISIBLE_STATE_FIELDS = {"task", "policy_arm", "available_worker_ids", "remaining_capacity", "already_offered_worker_ids", "next_sequence"}
FORBIDDEN_VISIBLE_TOKENS = ("outcome", "result", "realized", "post_decision", "completed_quality")


def _validate_visible_state(state: dict[str, Any]) -> None:
    unknown = sorted(set(state) - VISIBLE_STATE_FIELDS)
    if unknown:
        raise ValueError(f"online V1 state contains non-contract fields:{','.join(unknown)}")
    serialized_keys = " ".join(str(key).lower() for key in state.get("task", {}))
    if any(token in serialized_keys for token in FORBIDDEN_VISIBLE_TOKENS):
        raise ValueError("online V1 task contains future or outcome fields")


def decide_next_offer(
    state: dict[str, Any], candidates: list[dict[str, Any]], manifest: dict[str, Any], *,
    decision_time: str, stage3_gate: Path, validation_roster: Path, enrollment_registry: Path,
) -> dict[str, Any]:
    gate = validate_gate_file(stage3_gate)
    assert_frozen_roster(gate, validation_roster, enrollment_registry)
    _validate_visible_state(state)
    for row in candidates: validate_record("policy_candidate_v2", row)
    available = [row for row in candidates if row.get("worker_id") in set(state.get("available_worker_ids", [])) and int(state.get("remaining_capacity", {}).get(str(row.get("worker_id")), 0)) > 0]
    ranking = rank_candidates(available, state["task"], manifest)
    arm = str(state["policy_arm"])
    ordered = ranking[arm]
    offered = next((worker for worker in ordered if worker not in set(state.get("already_offered_worker_ids", []))), "")
    if not offered: raise ValueError("no currently available V1 candidate")
    return {"schema_version": "v1_offer_decision_v2", "sequence": int(state.get("next_sequence", 1)), "decision_time": _time(decision_time).isoformat(), "task_id": str(state["task"]["task_id"]), "policy_arm": arm, "offered_worker_id": offered, "profile_version": str(manifest["profile_version"]), "stage3_gate_sha256": __import__("hashlib").sha256(stage3_gate.read_bytes()).hexdigest(), "validation_roster_sha256": gate["validation_roster_sha256"], "enrollment_registry_sha256": gate["enrollment_registry_sha256"], "state_snapshot_sha256": __import__("hashlib").sha256(json.dumps(state, sort_keys=True, separators=(",", ":")).encode()).hexdigest()}


def append_decision(ledger: Path, decision: dict[str, Any]) -> None:
    existing = [json.loads(line) for line in ledger.read_text(encoding="utf-8").splitlines() if line.strip()] if ledger.exists() else []
    if existing and (int(decision["sequence"]) != int(existing[-1]["sequence"]) + 1 or _time(decision["decision_time"]) <= _time(existing[-1]["decision_time"])):
        raise ValueError("V1 ledger sequence/time must be strictly increasing")
    ledger.parent.mkdir(parents=True, exist_ok=True)
    with ledger.open("a", encoding="utf-8") as stream: stream.write(json.dumps(decision, sort_keys=True) + "\n")
