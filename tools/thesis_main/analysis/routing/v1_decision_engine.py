"""Prospective V1 next-offer engine with append-only evidence."""

from __future__ import annotations

import json
import csv
import math
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from tools.thesis_main.analysis.paper_a_contracts import validate_serialized_record
from tools.thesis_main.analysis.materialize_stage3_freeze_gate import assert_frozen_roster, validate_gate_file
from tools.thesis_main.analysis.routing.v1_policy import load_online_frozen_manifest, rank_candidates


def _time(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None: parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


VISIBLE_STATE_FIELDS = {"task", "policy_arm", "available_worker_ids", "remaining_capacity", "already_offered_worker_ids", "next_sequence"}
PREDECISION_TASK_FIELDS = {"task_id", "d_cal_F", "family_scores", "risk_route"}


def _validate_visible_state(state: dict[str, Any]) -> None:
    unknown = sorted(set(state) - VISIBLE_STATE_FIELDS)
    if unknown:
        raise ValueError(f"online V1 state contains non-contract fields:{','.join(unknown)}")
    task = state.get("task")
    if not isinstance(task, dict):
        raise ValueError("online V1 task must be a mapping")
    if set(task) != PREDECISION_TASK_FIELDS:
        unexpected = sorted(set(task) - PREDECISION_TASK_FIELDS)
        if any(
            any(token in field.lower() for token in ("outcome", "result", "gold", "consensus", "iou"))
            for field in unexpected
        ):
            raise ValueError(
                "online V1 task contains future or outcome fields; "
                "v1_predecision_task_v1 rejects them"
            )
        raise ValueError("online V1 task must satisfy v1_predecision_task_v1")
    if not isinstance(task["task_id"], str) or not task["task_id"]:
        raise ValueError("online V1 task_id must be a non-empty string")
    if not isinstance(task["risk_route"], bool) or not isinstance(task["family_scores"], dict):
        raise ValueError("online V1 task has invalid v1_predecision_task_v1 types")
    scores = [task["d_cal_F"], *task["family_scores"].values()]
    if not all(isinstance(value, (int, float)) and math.isfinite(float(value)) for value in scores):
        raise ValueError("online V1 task scores must be finite")


def _calculate_next_offer(
    state: dict[str, Any], *,
    decision_time: str, stage3_gate: Path, validation_roster: Path, enrollment_registry: Path,
    freeze_manifest: Path, freeze_manifest_sha256: str, candidate_roster_csv: Path,
) -> dict[str, Any]:
    manifest = load_online_frozen_manifest(
        freeze_manifest,
        freeze_manifest_sha256,
        candidate_roster_csv,
        stage3_gate,
    )
    gate = validate_gate_file(stage3_gate, expected_gate_kind="V1")
    assert_frozen_roster(gate, validation_roster, enrollment_registry)
    _validate_visible_state(state)
    with candidate_roster_csv.open("r", encoding="utf-8", newline="") as stream:
        candidates = [dict(row) for row in csv.DictReader(stream)]
    if not candidates:
        raise ValueError("online V1 frozen candidate roster is empty")
    for row in candidates:
        validate_serialized_record("policy_candidate_v2", row)
    available = [row for row in candidates if row.get("worker_id") in set(state.get("available_worker_ids", [])) and int(state.get("remaining_capacity", {}).get(str(row.get("worker_id")), 0)) > 0]
    ranking = rank_candidates(available, state["task"], manifest)
    arm = str(state["policy_arm"])
    ordered = ranking[arm]
    offered = next((worker for worker in ordered if worker not in set(state.get("already_offered_worker_ids", []))), "")
    if not offered: raise ValueError("no currently available V1 candidate")
    return {"schema_version": "v1_offer_decision_v2", "sequence": int(state.get("next_sequence", 1)), "decision_time": _time(decision_time).isoformat(), "task_id": str(state["task"]["task_id"]), "policy_arm": arm, "offered_worker_id": offered, "profile_version": str(manifest["profile_version"]), "freeze_manifest_sha256": freeze_manifest_sha256, "method_contract_sha256": manifest["method_contract_sha256"], "policy_manifest_sha256": manifest["policy_manifest_sha256"], "candidate_roster_sha256": manifest["candidate_roster_sha256"], "stage3_gate_sha256": __import__("hashlib").sha256(stage3_gate.read_bytes()).hexdigest(), "validation_roster_sha256": gate["validation_roster_sha256"], "enrollment_registry_sha256": gate["enrollment_registry_sha256"], "state_snapshot_sha256": __import__("hashlib").sha256(json.dumps(state, sort_keys=True, separators=(",", ":")).encode()).hexdigest()}


def append_decision(ledger: Path, decision: dict[str, Any]) -> None:
    existing = [json.loads(line) for line in ledger.read_text(encoding="utf-8").splitlines() if line.strip()] if ledger.exists() else []
    if existing and (int(decision["sequence"]) != int(existing[-1]["sequence"]) + 1 or _time(decision["decision_time"]) <= _time(existing[-1]["decision_time"])):
        raise ValueError("V1 ledger sequence/time must be strictly increasing")
    ledger.parent.mkdir(parents=True, exist_ok=True)
    with ledger.open("a", encoding="utf-8") as stream: stream.write(json.dumps(decision, sort_keys=True) + "\n")


def decide_next_offer(
    state: dict[str, Any], *,
    decision_time: str, stage3_gate: Path, validation_roster: Path, enrollment_registry: Path,
    freeze_manifest: Path, freeze_manifest_sha256: str, candidate_roster_csv: Path,
    ledger: Path,
) -> dict[str, Any]:
    """Make one online offer and durably append its decision evidence."""
    decision = _calculate_next_offer(
        state,
        decision_time=decision_time,
        stage3_gate=stage3_gate,
        validation_roster=validation_roster,
        enrollment_registry=enrollment_registry,
        freeze_manifest=freeze_manifest,
        freeze_manifest_sha256=freeze_manifest_sha256,
        candidate_roster_csv=candidate_roster_csv,
    )
    append_decision(ledger, decision)
    return decision


def replay_next_offer(
    state: dict[str, Any], *,
    decision_time: str, stage3_gate: Path, validation_roster: Path, enrollment_registry: Path,
    freeze_manifest: Path, freeze_manifest_sha256: str, candidate_roster_csv: Path,
) -> dict[str, Any]:
    """Reconstruct a historical decision without mutating the event ledger."""
    return _calculate_next_offer(
        state,
        decision_time=decision_time,
        stage3_gate=stage3_gate,
        validation_roster=validation_roster,
        enrollment_registry=enrollment_registry,
        freeze_manifest=freeze_manifest,
        freeze_manifest_sha256=freeze_manifest_sha256,
        candidate_roster_csv=candidate_roster_csv,
    )
