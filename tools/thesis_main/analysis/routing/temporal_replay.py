from __future__ import annotations

import csv
import json
from collections import defaultdict
from pathlib import Path
from typing import Any, Iterable

from tools.thesis_main.analysis.routing.crossfit import build_crossfit_folds
from tools.thesis_main.analysis.routing.sequential_rule import candidate_rule_config, decide_candidate_action
from tools.thesis_main.analysis.vfinal_artifact_utils import COMMON_SIDEcar_FIELDS, sha256_file, sidecar_common, write_csv_rows


RULE_VERSION = "temporal_routing_replay_v1"


def replay_temporal_events(events: Iterable[dict[str, Any]], *, policy_by_fold: dict[int, dict[str, Any]], n_folds: int = 2, input_status: str = "dry_run") -> list[dict[str, Any]]:
    """Replay only evidence available before each arrival; policies are pre-fitted inputs."""
    rows = build_crossfit_folds(events, n_folds=n_folds)
    required = {int(row["crossfit_fold"]) for row in rows}
    if required - set(policy_by_fold):
        raise ValueError("policy_by_fold must contain a pre-fitted policy for every evaluation fold")
    seen_ids: set[str] = set()
    for row in rows:
        if not str(row.get("event_id", "")).strip() or not str(row.get("arrived_at", "")).strip():
            raise ValueError("event_id and arrived_at are required for temporal replay")
        if row["event_id"] in seen_ids:
            raise ValueError("event_id must be unique")
        seen_ids.add(row["event_id"])
    rows.sort(key=lambda row: (str(row["arrived_at"]), str(row["event_id"])))
    observed: dict[tuple[str, str], int] = defaultdict(int)
    traces = []
    for row in rows:
        key = (str(row["base_task_id"]), str(row.get("condition", "")))
        prior_k = observed[key]
        policy = policy_by_fold[int(row["crossfit_fold"])]
        risk_bucket = str(policy.get("risk_bucket", "low_risk"))
        decision = decide_candidate_action({"n_independent_workers": prior_k, "support_gap_candidate": row.get("support_gap_candidate", "false")}, candidate_rule_config(risk_bucket))
        traces.append({
            **sidecar_common(source_artifact=str(row.get("source_artifact", "")), source_sha256=str(row.get("source_sha256", "")), stage=str(row.get("stage", "C1")), pool=str(row.get("pool", "")), condition=str(row.get("condition", "")), validity_status="dry_run" if input_status != "formal" else "candidate_only", rule_version=RULE_VERSION, interpretation_allowed=False),
            "event_id": row["event_id"], "arrived_at": row["arrived_at"], "task_id": key[0], "base_task_id": key[1], "canonical_annotation_id": row.get("canonical_annotation_id", ""),
            "crossfit_fold": row["crossfit_fold"], "policy_fit_excludes_fold": "true", "prior_legal_arrivals": prior_k, "action": decision["action"], "action_reason": decision["action"], "formal_assignment_generated": "false",
        })
        if str(row.get("legal_arrival", "true")).lower() == "true":
            observed[key] += 1
    return traces


def materialize_temporal_replay(event_csv: Path | None, output_csv: Path, *, policy_by_fold: dict[int, dict[str, Any]] | None = None, input_status: str = "dry_run") -> dict[str, Any]:
    if input_status != "formal" or event_csv is None or not event_csv.exists():
        write_csv_rows(output_csv, [], COMMON_SIDEcar_FIELDS + ["event_id", "arrived_at", "task_id", "base_task_id", "canonical_annotation_id", "crossfit_fold", "policy_fit_excludes_fold", "prior_legal_arrivals", "action", "action_reason", "formal_assignment_generated"])
        return {"status": "not_evaluable_missing_formal_c1", "n_events": 0, "formal_assignment_generated": False}
    with event_csv.open("r", newline="", encoding="utf-8-sig") as handle:
        traces = replay_temporal_events(csv.DictReader(handle), policy_by_fold=policy_by_fold or {}, input_status=input_status)
    write_csv_rows(output_csv, traces, COMMON_SIDEcar_FIELDS + ["event_id", "arrived_at", "task_id", "base_task_id", "canonical_annotation_id", "crossfit_fold", "policy_fit_excludes_fold", "prior_legal_arrivals", "action", "action_reason", "formal_assignment_generated"])
    return {"status": "candidate_only", "n_events": len(traces), "source_sha256": sha256_file(event_csv), "formal_assignment_generated": False}


if __name__ == "__main__":
    raise SystemExit("Use materialize_temporal_replay from the C1 closeout workflow.")
