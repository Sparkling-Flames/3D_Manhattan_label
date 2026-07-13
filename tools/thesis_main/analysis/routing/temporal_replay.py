from __future__ import annotations

import csv
import json
from collections import defaultdict
import hashlib
from pathlib import Path
from typing import Any, Iterable

from tools.thesis_main.analysis.routing.crossfit import build_crossfit_folds
from tools.thesis_main.analysis.routing.sequential_rule import candidate_rule_config, decide_candidate_action
from tools.thesis_main.analysis.vfinal_artifact_utils import COMMON_SIDEcar_FIELDS, sha256_file, sidecar_common, write_csv_rows


RULE_VERSION = "temporal_routing_replay_v1"


def _fold_for_base(base_task_id: str, n_folds: int) -> int:
    return int(hashlib.sha256(base_task_id.encode("utf-8")).hexdigest()[:8], 16) % max(2, int(n_folds))


def _validate_policy(policy: dict[str, Any], eval_fold: int, n_folds: int) -> dict[str, Any]:
    required = ("policy_artifact_id", "policy_artifact_sha256", "policy_artifact_path", "rule_version", "fit_folds", "fit_base_task_ids")
    missing = [key for key in required if not policy.get(key)]
    if missing:
        raise ValueError(f"policy is missing audit fields: {', '.join(missing)}")
    artifact = Path(str(policy["policy_artifact_path"])).expanduser().resolve()
    if not artifact.exists() or sha256_file(artifact) != str(policy["policy_artifact_sha256"]):
        raise ValueError("policy artifact SHA256 does not match its declared file")
    fit_folds = {int(value) for value in policy["fit_folds"]}
    fit_base_ids = {str(value).strip() for value in policy["fit_base_task_ids"] if str(value).strip()}
    if eval_fold in fit_folds or any(_fold_for_base(base_id, n_folds) == eval_fold for base_id in fit_base_ids):
        raise ValueError("policy fit set includes the evaluation fold")
    if not fit_base_ids:
        raise ValueError("policy fit_base_task_ids must not be empty")
    if any(_fold_for_base(base_id, n_folds) not in fit_folds for base_id in fit_base_ids):
        raise ValueError("policy fit_base_task_ids and fit_folds disagree")
    return {"policy_fit_excludes_fold": True, "policy_validation_status": "verified"}


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
    observed: dict[tuple[str, str], list[dict[str, str]]] = defaultdict(list)
    traces = []
    for row in rows:
        group_key = (str(row["base_task_id"]), str(row.get("condition", "")))
        prior = observed[group_key]
        prior_k = len(prior)
        eval_fold = int(row["crossfit_fold"])
        policy = policy_by_fold[eval_fold]
        policy_audit = _validate_policy(policy, eval_fold, n_folds)
        risk_bucket = str(policy.get("risk_bucket", "low_risk"))
        decision = decide_candidate_action({"n_independent_workers": prior_k, "support_gap_candidate": row.get("support_gap_candidate", "false")}, candidate_rule_config(risk_bucket))
        traces.append({
            **sidecar_common(source_artifact=str(row.get("source_artifact", "")), source_sha256=str(row.get("source_sha256", "")), stage=str(row.get("stage", "C1")), pool=str(row.get("pool", "")), condition=str(row.get("condition", "")), validity_status="dry_run" if input_status != "formal" else "candidate_only", rule_version=RULE_VERSION, interpretation_allowed=False),
            "event_id": row["event_id"], "arrived_at": row["arrived_at"], "task_id": row.get("task_id", ""), "base_task_id": row["base_task_id"], "condition": row.get("condition", ""), "canonical_annotation_id": row.get("canonical_annotation_id", ""), "crossfit_fold": row["crossfit_fold"], **policy_audit, "policy_artifact_id": policy["policy_artifact_id"], "policy_artifact_sha256": policy["policy_artifact_sha256"], "policy_artifact_path": policy.get("policy_artifact_path", ""), "policy_rule_version": policy["rule_version"], "policy_fit_folds_json": json.dumps(sorted({int(value) for value in policy["fit_folds"]})), "policy_fit_base_task_ids_json": json.dumps(sorted({str(value) for value in policy["fit_base_task_ids"]})), "policy_fit_base_task_count": len(policy["fit_base_task_ids"]), "prior_legal_arrivals": prior_k, "prior_evidence_json": json.dumps(prior, sort_keys=True), "a": row.get("a", ""), "e": row.get("e", ""), "u": row.get("u", ""), "replicated_explicit_conflict": row.get("replicated_explicit_conflict", ""), "geometry_disagreement": row.get("geometry_disagreement", ""), "provenance_status": row.get("provenance_status", ""), "fallback": row.get("fallback", ""), "candidate_worker_id": row.get("candidate_worker_id", ""), "selected_worker_id": row.get("selected_worker_id") or row.get("candidate_worker_id", ""), "action": decision["action"], "action_reason": decision["action"], "formal_assignment_generated": "false",
        })
        if str(row.get("legal_arrival", "true")).lower() == "true":
            observed[group_key].append({"event_id": str(row["event_id"]), "canonical_annotation_id": str(row.get("canonical_annotation_id", "")), "worker_id": str(row.get("candidate_worker_id", ""))})
    return traces


def materialize_temporal_replay(event_csv: Path | None, output_csv: Path, *, policy_manifest: Path | None = None, policy_by_fold: dict[int, dict[str, Any]] | None = None, input_status: str = "dry_run") -> dict[str, Any]:
    if input_status != "formal" or event_csv is None or not event_csv.exists():
        write_csv_rows(output_csv, [], COMMON_SIDEcar_FIELDS + ["event_id", "arrived_at", "task_id", "base_task_id", "condition", "canonical_annotation_id", "crossfit_fold", "policy_fit_excludes_fold", "policy_validation_status", "policy_artifact_id", "policy_artifact_sha256", "policy_artifact_path", "policy_rule_version", "policy_fit_folds_json", "policy_fit_base_task_ids_json", "policy_fit_base_task_count", "prior_legal_arrivals", "a", "e", "u", "replicated_explicit_conflict", "geometry_disagreement", "provenance_status", "fallback", "candidate_worker_id", "action", "action_reason", "formal_assignment_generated"])
        return {"status": "not_evaluable_missing_formal_c1", "n_events": 0, "formal_assignment_generated": False}
    if policy_manifest:
        payload = json.loads(policy_manifest.read_text(encoding="utf-8"))
        policy_by_fold = {int(key): value for key, value in payload.items()}
    if not policy_by_fold:
        write_csv_rows(output_csv, [], COMMON_SIDEcar_FIELDS + ["event_id", "arrived_at", "task_id", "base_task_id", "condition", "canonical_annotation_id", "candidate_worker_id", "selected_worker_id", "prior_evidence_json", "action", "action_reason"])
        return {"status": "not_evaluable_missing_policy_artifact", "n_events": 0, "formal_assignment_generated": False}
    with event_csv.open("r", newline="", encoding="utf-8-sig") as handle:
        traces = replay_temporal_events(csv.DictReader(handle), policy_by_fold=policy_by_fold, input_status=input_status)
    write_csv_rows(output_csv, traces, COMMON_SIDEcar_FIELDS + ["event_id", "arrived_at", "task_id", "base_task_id", "condition", "canonical_annotation_id", "crossfit_fold", "policy_fit_excludes_fold", "policy_validation_status", "policy_artifact_id", "policy_artifact_sha256", "policy_artifact_path", "policy_rule_version", "policy_fit_folds_json", "policy_fit_base_task_ids_json", "policy_fit_base_task_count", "prior_legal_arrivals", "prior_evidence_json", "a", "e", "u", "replicated_explicit_conflict", "geometry_disagreement", "provenance_status", "fallback", "candidate_worker_id", "selected_worker_id", "action", "action_reason", "formal_assignment_generated"])
    return {"status": "candidate_only", "n_events": len(traces), "source_sha256": sha256_file(event_csv), "policy_manifest_sha256": sha256_file(policy_manifest), "formal_assignment_generated": False}


if __name__ == "__main__":
    raise SystemExit("Use materialize_temporal_replay from the C1 closeout workflow.")
