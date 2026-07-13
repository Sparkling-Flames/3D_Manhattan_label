from __future__ import annotations

import csv
import json
from collections import Counter, defaultdict
import hashlib
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from tools.thesis_main.analysis.routing.crossfit import build_crossfit_folds
from tools.thesis_main.analysis.routing.sequential_rule import candidate_rule_config, decide_candidate_action
from tools.thesis_main.analysis.vfinal_artifact_utils import COMMON_SIDEcar_FIELDS, eligible_independent_evidence, read_csv_rows, sha256_file, sidecar_common, write_csv_rows


RULE_VERSION = "temporal_routing_replay_v1"


def _arrival(value: Any) -> datetime:
    text = str(value or "").strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    parsed = datetime.fromisoformat(text)
    if parsed.tzinfo is None:
        raise ValueError("arrived_at must include a timezone")
    return parsed.astimezone(timezone.utc)


def _event_evidence_key(row: dict[str, Any]) -> tuple[str, str, str]:
    return (str(row.get("canonical_annotation_id", "")), str(row.get("tag_family", "")), str(row.get("tag_name", "")))


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


def _load_policy_manifest(path: Path) -> dict[int, dict[str, Any]]:
    pairs = json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=lambda values: values)
    if not isinstance(pairs, list):
        raise ValueError("policy manifest must be a fold-keyed JSON object")
    keys = [str(key) for key, _ in pairs]
    if len(keys) != len(set(keys)):
        raise ValueError("policy manifest contains duplicate fold keys")
    policies: dict[int, dict[str, Any]] = {}
    for key, raw_policy in pairs:
        policy = dict(raw_policy)
        artifact = Path(str(policy.get("policy_artifact_path", "")))
        policy["policy_artifact_path"] = str((path.parent / artifact).resolve() if not artifact.is_absolute() else artifact.resolve())
        policies[int(key)] = policy
    return policies


def replay_temporal_events(events: Iterable[dict[str, Any]], *, policy_by_fold: dict[int, dict[str, Any]], evidence_by_id: dict[tuple[str, str, str], dict[str, Any]] | None = None, source_artifact: str = "", source_sha256: str = "", dependency_paths: list[Path] | None = None, n_folds: int = 2, input_status: str = "dry_run") -> list[dict[str, Any]]:
    """Replay only evidence available before each arrival; policies are pre-fitted inputs."""
    rows = build_crossfit_folds(events, n_folds=n_folds)
    seen_ids: set[str] = set()
    parsed_arrivals: dict[str, datetime] = {}
    for row in rows:
        if not str(row.get("event_id", "")).strip() or not str(row.get("arrived_at", "")).strip():
            raise ValueError("event_id and arrived_at are required for temporal replay")
        if not str(row.get("tag_family", "")).strip() or not str(row.get("tag_name", "")).strip():
            raise ValueError("tag_family and tag_name are required for temporal replay")
        try:
            parsed_arrivals[str(row["event_id"])] = _arrival(row["arrived_at"])
        except ValueError as exc:
            raise ValueError("arrived_at must be an ISO-8601 timestamp") from exc
        if row["event_id"] in seen_ids:
            raise ValueError("event_id must be unique")
        seen_ids.add(row["event_id"])
    required = {int(row["crossfit_fold"]) for row in rows}
    if set(policy_by_fold) != required:
        raise ValueError("policy_by_fold must exactly match the evaluation folds")
    rows.sort(key=lambda row: (parsed_arrivals[str(row["event_id"])], str(row["event_id"])))
    observed: dict[tuple[str, str], list[dict[str, str]]] = defaultdict(list)
    traces = []
    illegal_reasons: Counter[str] = Counter()
    previous_prior_k_by_group: dict[tuple[str, str], int] = {}
    for row in rows:
        candidate_worker_id = str(row.get("candidate_worker_id") or row.get("worker_id") or row.get("annotator_id") or "")
        group_key = (str(row["base_task_id"]), str(row.get("condition", "")))
        prior = observed[group_key]
        eligible_workers = {item["worker_id"] for item in prior}
        prior_k = len(eligible_workers)
        prior_a = sum(item["assertion"] == "+" for item in prior)
        prior_e = sum(item["assertion"] == "-" for item in prior)
        prior_u = sum(item["assertion"] == "0" for item in prior)
        prior_candidate_available = any(item["candidate_available"] for item in prior)
        eval_fold = int(row["crossfit_fold"])
        policy = policy_by_fold[eval_fold]
        policy_audit = _validate_policy(policy, eval_fold, n_folds)
        risk_bucket = str(policy.get("risk_bucket", "low_risk"))
        decision = decide_candidate_action({"n_independent_workers": prior_k, "support_gap_candidate": prior_k < 2}, candidate_rule_config(risk_bucket))
        traces.append({
            **sidecar_common(source_artifact=source_artifact, source_sha256=source_sha256, stage=str(row.get("stage", "C1")), pool=str(row.get("pool", "")), condition=str(row.get("condition", "")), validity_status="dry_run" if input_status != "formal" else "candidate_only", rule_version=RULE_VERSION, interpretation_allowed=False, dependency_paths=dependency_paths or [source_artifact]),
            "event_id": row["event_id"], "arrived_at": row["arrived_at"], "arrived_at_utc": parsed_arrivals[str(row["event_id"])].isoformat(), "task_id": row.get("task_id", ""), "base_task_id": row["base_task_id"], "condition": row.get("condition", ""), "canonical_annotation_id": row.get("canonical_annotation_id", ""), "tag_family": row["tag_family"], "tag_name": row["tag_name"], "crossfit_fold": row["crossfit_fold"], **policy_audit, "policy_artifact_id": policy["policy_artifact_id"], "policy_artifact_sha256": policy["policy_artifact_sha256"], "policy_artifact_path": policy.get("policy_artifact_path", ""), "policy_rule_version": policy["rule_version"], "policy_fit_folds_json": json.dumps(sorted({int(value) for value in policy["fit_folds"]})), "policy_fit_base_task_ids_json": json.dumps(sorted({str(value) for value in policy["fit_base_task_ids"]})), "policy_fit_base_task_count": len(policy["fit_base_task_ids"]), "prior_legal_arrivals": prior_k, "prior_eligible_workers_json": json.dumps(sorted(eligible_workers)), "prior_evidence_json": json.dumps(prior, sort_keys=True), "a": prior_a, "e": prior_e, "u": prior_u, "replicated_explicit_conflict": str(prior_a >= 2 and prior_e >= 2).lower(), "geometry_disagreement": str(any(item["geometry_disagreement"] for item in prior)).lower(), "provenance_status": "available" if prior and all(item["provenance_available"] for item in prior) else "not_available", "fallback": "support_available" if prior_k >= 2 else "insufficient_support", "prior_candidate_availability": str(prior_candidate_available).lower(), "candidate_worker_id": candidate_worker_id, "selected_worker_id": row.get("selected_worker_id") or candidate_worker_id, "action": decision["action"], "action_reason": decision["action"], "formal_assignment_generated": "false",
        })
        evidence = (evidence_by_id or {}).get(_event_evidence_key(row), {})
        evidence_arrival = str(evidence.get("arrived_at") or evidence.get("annotation_created_at") or evidence.get("created_at") or "")
        try:
            evidence_time_matches = bool(evidence_arrival) and _arrival(evidence_arrival) == parsed_arrivals[str(row["event_id"])]
        except ValueError:
            evidence_time_matches = False
        reasons = []
        if not evidence:
            reasons.append("missing_three_state_evidence")
        if evidence and not evidence_time_matches:
            reasons.append("arrival_timestamp_mismatch")
        if evidence and not eligible_independent_evidence(evidence):
            reasons.append("ineligible_quality_evidence")
        if evidence and (str(evidence.get("base_task_id")) != str(row.get("base_task_id")) or str(evidence.get("condition")) != str(row.get("condition"))):
            reasons.append("task_condition_mismatch")
        if evidence and str(evidence.get("worker_id") or evidence.get("annotator_id")) != candidate_worker_id:
            reasons.append("worker_identity_mismatch")
        if evidence and (str(evidence.get("tag_family")) != str(row.get("tag_family")) or str(evidence.get("tag_name")) != str(row.get("tag_name"))):
            reasons.append("tag_identity_mismatch")
        if evidence and str(evidence.get("assertion")) not in {"+", "-", "0"}:
            reasons.append("missing_or_invalid_assertion")
        legal = not reasons
        traces[-1]["event_legal"] = str(legal).lower()
        traces[-1]["event_legal_reason"] = "canonical_quality_three_state_join_valid" if legal else ";".join(reasons)
        if not legal:
            illegal_reasons[traces[-1]["event_legal_reason"]] += 1
        if legal:
            traces[-1]["assertion"] = str(evidence["assertion"])
            observed[group_key].append({"event_id": str(row["event_id"]), "canonical_annotation_id": str(row.get("canonical_annotation_id", "")), "worker_id": candidate_worker_id, "assertion": str(evidence["assertion"]), "geometry_disagreement": str(evidence.get("geometry_disagreement", "false")).lower() == "true", "provenance_available": str(evidence.get("effective_provenance_status") or evidence.get("provenance_status")) not in {"", "missing", "incomplete", "not_evaluable"}, "candidate_available": str(evidence.get("candidate_available", "true")).lower() == "true"})
        if prior_k < previous_prior_k_by_group.get(group_key, 0):
            traces[-1]["prior_state_monotonicity"] = "failed"
        else:
            traces[-1]["prior_state_monotonicity"] = "passed"
        previous_prior_k_by_group[group_key] = prior_k
    for trace in traces:
        trace["illegal_event_count"] = sum(illegal_reasons.values())
        trace["illegal_event_reasons_json"] = json.dumps(dict(illegal_reasons), sort_keys=True)
    return traces


def materialize_temporal_replay(event_csv: Path | None, output_csv: Path, *, policy_manifest: Path | None = None, policy_by_fold: dict[int, dict[str, Any]] | None = None, canonical_csv: Path | None = None, quality_csv: Path | None = None, three_state_csv: Path | None = None, input_status: str = "dry_run") -> dict[str, Any]:
    if input_status != "formal" or event_csv is None or not event_csv.exists():
        write_csv_rows(output_csv, [], COMMON_SIDEcar_FIELDS + ["event_id", "arrived_at", "arrived_at_utc", "task_id", "base_task_id", "condition", "tag_family", "tag_name", "canonical_annotation_id", "crossfit_fold", "policy_fit_excludes_fold", "policy_validation_status", "policy_artifact_id", "policy_artifact_sha256", "policy_artifact_path", "policy_rule_version", "policy_fit_folds_json", "policy_fit_base_task_ids_json", "policy_fit_base_task_count", "prior_legal_arrivals", "a", "e", "u", "replicated_explicit_conflict", "geometry_disagreement", "provenance_status", "fallback", "candidate_worker_id", "action", "action_reason", "formal_assignment_generated"])
        return {"status": "not_evaluable_missing_formal_c1", "n_events": 0, "formal_assignment_generated": False}
    if policy_manifest:
        policy_by_fold = _load_policy_manifest(policy_manifest)
    if not policy_by_fold:
        write_csv_rows(output_csv, [], COMMON_SIDEcar_FIELDS + ["event_id", "arrived_at", "arrived_at_utc", "task_id", "base_task_id", "condition", "canonical_annotation_id", "candidate_worker_id", "selected_worker_id", "prior_evidence_json", "action", "action_reason"])
        return {"status": "not_evaluable_missing_policy_artifact", "n_events": 0, "formal_assignment_generated": False}
    evidence_rows = read_csv_rows(quality_csv) if quality_csv else []
    tag_rows = read_csv_rows(three_state_csv) if three_state_csv and three_state_csv.exists() else []
    quality_by_id = {row.get("canonical_annotation_id", ""): row for row in evidence_rows if row.get("canonical_annotation_id")}
    evidence_by_id = {}
    for row in tag_rows:
        quality = quality_by_id.get(row.get("canonical_annotation_id", ""))
        if quality:
            evidence_by_id[_event_evidence_key(row)] = {**quality, **row}
    with event_csv.open("r", newline="", encoding="utf-8-sig") as handle:
        events = list(csv.DictReader(handle))
    required_folds = {int(row["crossfit_fold"]) for row in build_crossfit_folds(events)}
    if set(policy_by_fold) != required_folds:
        raise ValueError("policy manifest folds must exactly match evaluation folds")
    policy_artifacts = [Path(policy["policy_artifact_path"]) for policy in policy_by_fold.values()]
    dependencies = [event_csv, *([policy_manifest] if policy_manifest else []), *policy_artifacts, *([canonical_csv] if canonical_csv else []), *([quality_csv] if quality_csv else []), *([three_state_csv] if three_state_csv else [])]
    traces = replay_temporal_events(events, policy_by_fold=policy_by_fold, evidence_by_id=evidence_by_id, source_artifact=str(event_csv.resolve()), source_sha256=sha256_file(event_csv), dependency_paths=dependencies, input_status=input_status)
    write_csv_rows(output_csv, traces, COMMON_SIDEcar_FIELDS + ["event_id", "arrived_at", "arrived_at_utc", "task_id", "base_task_id", "condition", "tag_family", "tag_name", "canonical_annotation_id", "crossfit_fold", "policy_fit_excludes_fold", "policy_validation_status", "policy_artifact_id", "policy_artifact_sha256", "policy_artifact_path", "policy_rule_version", "policy_fit_folds_json", "policy_fit_base_task_ids_json", "policy_fit_base_task_count", "prior_legal_arrivals", "prior_eligible_workers_json", "prior_evidence_json", "a", "e", "u", "replicated_explicit_conflict", "geometry_disagreement", "provenance_status", "fallback", "prior_candidate_availability", "candidate_worker_id", "selected_worker_id", "assertion", "event_legal", "event_legal_reason", "prior_state_monotonicity", "illegal_event_count", "illegal_event_reasons_json", "action", "action_reason", "formal_assignment_generated"])
    legal_count = sum(str(row.get("event_legal")) == "true" for row in traces)
    return {"status": "candidate_only", "n_events": len(traces), "n_legal_events": legal_count, "n_illegal_events": len(traces) - legal_count, "all_events_legal": legal_count == len(traces) and bool(traces), "prior_state_monotonicity": all(row.get("prior_state_monotonicity") == "passed" for row in traces), "n_nonzero_assertions": sum(str(row.get("assertion")) in {"+", "-"} for row in traces), "worker_identity_consistent": all(row.get("candidate_worker_id") == row.get("selected_worker_id") for row in traces), "policy_dependency_valid": all(row.get("policy_validation_status") == "verified" and row.get("policy_artifact_sha256") for row in traces) and bool(traces), "illegal_event_reasons": dict(Counter(reason for row in traces for reason in str(row.get("event_legal_reason", "")).split(";") if reason and reason != "canonical_quality_three_state_join_valid")), "source_sha256": sha256_file(event_csv), "policy_manifest_sha256": sha256_file(policy_manifest) if policy_manifest else "", "formal_assignment_generated": False}


if __name__ == "__main__":
    raise SystemExit("Use materialize_temporal_replay from the C1 closeout workflow.")
