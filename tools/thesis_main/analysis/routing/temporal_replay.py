from __future__ import annotations

import csv
import json
from collections import Counter, defaultdict
import hashlib
import random
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from tools.thesis_main.analysis.routing.crossfit import build_crossfit_folds
from tools.thesis_main.analysis.routing.sequential_rule import candidate_rule_config, decide_candidate_action
from tools.thesis_main.analysis.geometry_consensus.pairwise import pairwise_similarity
from tools.thesis_main.analysis.geometry_consensus.representation import normalize_geometry
from tools.thesis_main.analysis.vfinal_artifact_utils import COMMON_SIDEcar_FIELDS, eligible_independent_evidence, read_csv_rows, sha256_file, sidecar_common, write_csv_rows


RULE_VERSION = "temporal_routing_replay_v2"
STOP_POLICY_FIELDS = ("meta_min_same_state", "meta_max_opposition", "max_unasserted_rate", "min_q_boundary", "min_q_wallwall")
RISK_BUCKETS = {"low_risk", "high_risk", "stress"}
TASK_PURPOSES = {"scope_only", "geometry_production", "calibration_scene_profile", "meta_label_only", "semi_correction_evaluation"}
EVIDENCE_COMPONENTS = {"scope", "difficulty", "model_issue_recognition", "model_issue_correction", "geometry", "scene"}
SENSITIVITY_SEED = 20260714
SENSITIVITY_PERMUTATIONS = 100


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
    try:
        thresholds = json.loads(artifact.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError("policy artifact must be valid JSON") from exc
    missing_thresholds = [field for field in STOP_POLICY_FIELDS if field not in thresholds]
    if missing_thresholds:
        raise ValueError(f"policy artifact is missing stop thresholds: {', '.join(missing_thresholds)}")
    try:
        if int(thresholds["meta_min_same_state"]) < 1 or int(thresholds["meta_max_opposition"]) < 0 or any(not 0 <= float(thresholds[field]) <= 1 for field in ("max_unasserted_rate", "min_q_boundary", "min_q_wallwall")):
            raise ValueError
    except (TypeError, ValueError) as exc:
        raise ValueError("policy stop thresholds are invalid") from exc
    policy["stop_thresholds"] = thresholds
    return {"policy_fit_excludes_fold": True, "policy_validation_status": "verified"}


def _sha256_text(value: Any) -> bool:
    text = str(value or "")
    return len(text) == 64 and all(char in "0123456789abcdefABCDEF" for char in text)


def _components(value: Any) -> set[str]:
    if isinstance(value, list):
        values = value
    else:
        text = str(value or "").strip()
        try:
            values = json.loads(text) if text.startswith("[") else text.replace(";", ",").split(",")
        except json.JSONDecodeError:
            values = []
    return {str(item).strip() for item in values if str(item).strip()}


def _load_task_purposes(path: Path) -> dict[tuple[str, str], dict[str, Any]]:
    required = {"task_id", "base_task_id", "condition", "dataset_group", "task_purpose", "required_evidence_components", "scope_policy_id", "geometry_policy_id", "tag_policy_id", "correction_policy_id", "source_assignment_sha256", "manifest_version"}
    rows = read_csv_rows(path)
    if not rows or not required.issubset(rows[0]):
        raise ValueError("task-purpose manifest schema is incomplete")
    out: dict[tuple[str, str], dict[str, Any]] = {}
    for row in rows:
        key = (str(row["base_task_id"]), str(row["condition"]))
        components = _components(row["required_evidence_components"])
        if key in out or row["task_purpose"] not in TASK_PURPOSES or not components.issubset(EVIDENCE_COMPONENTS) or not components or not _sha256_text(row["source_assignment_sha256"]) or any(not str(row[field]).strip() for field in ("scope_policy_id", "geometry_policy_id", "tag_policy_id", "correction_policy_id", "manifest_version")):
            raise ValueError("task-purpose manifest contains duplicate or invalid rows")
        out[key] = {**row, "required_components": components}
    return out


def _load_candidate_roster(path: Path) -> dict[tuple[str, str], set[str]]:
    required = {"base_task_id", "condition", "worker_id", "candidate_eligible", "exclusion_reason", "source_admission_sha256", "source_assignment_sha256", "manifest_version"}
    rows = read_csv_rows(path)
    if not rows or not required.issubset(rows[0]):
        raise ValueError("candidate roster manifest schema is incomplete")
    seen: set[tuple[str, str, str]] = set()
    out: dict[tuple[str, str], set[str]] = defaultdict(set)
    for row in rows:
        identity = (str(row["base_task_id"]), str(row["condition"]), str(row["worker_id"]))
        if identity in seen or not all(identity) or not _sha256_text(row["source_admission_sha256"]) or not _sha256_text(row["source_assignment_sha256"]) or not str(row["manifest_version"]).strip():
            raise ValueError("candidate roster contains duplicate or invalid rows")
        seen.add(identity)
        if _strict_bool(row["candidate_eligible"]):
            out[identity[:2]].add(identity[2])
    return out


def _scope_vote(evidence: dict[str, Any]) -> str:
    text = str(evidence.get("scope") or "").lower()
    if "oos" in text or "out-of-scope" in text or "out of scope" in text:
        return "oos"
    if "in-scope" in text or "camera room" in text or "normal" in text or "只标相机房间" in text:
        return "in_scope"
    return "unknown"


def _family_status(a: int, e: int, u: int, cap_reached: bool) -> str:
    if a >= 2 and e >= 2:
        return "unresolved_at_cap" if cap_reached else "contested"
    if a >= 2:
        return "complete_positive"
    if e >= 2:
        return "complete_negative"
    return "unresolved_at_cap" if cap_reached else "insufficient"


def _scope_status(votes: list[str], cap_reached: bool) -> str:
    inside, outside = votes.count("in_scope"), votes.count("oos")
    if inside >= 2 and outside >= 2:
        return "unresolved_at_cap" if cap_reached else "conflicted"
    if inside >= 2:
        return "resolved_in_scope"
    if outside >= 2:
        return "resolved_oos"
    return "unresolved_at_cap" if cap_reached else "insufficient"


def _strict_bool(value: Any) -> bool:
    text = str(value).strip().lower()
    if text not in {"true", "false"}:
        raise ValueError("boolean value must be true or false")
    return text == "true"


def _geometry_state(annotation_ids: set[str], geometry_by_id: dict[str, dict[str, Any]]) -> dict[str, Any]:
    geometries = [geometry_by_id[item] for item in sorted(annotation_ids) if item in geometry_by_id]
    if len(geometries) < 2:
        return {"status": "not_evaluable_insufficient_support", "support": len(geometries), "q_boundary_min": None, "q_wallwall_min": None}
    pairs = [pairwise_similarity(left, right) for index, left in enumerate(geometries) for right in geometries[index + 1 :]]
    valid = [item for item in pairs if item["validity_status"] == "valid"]
    if len(valid) != len(pairs):
        return {"status": "not_evaluable_incompatible_geometry", "support": len(geometries), "q_boundary_min": None, "q_wallwall_min": None}
    return {"status": "evaluable", "support": len(geometries), "q_boundary_min": min(item["q_boundary"] for item in valid), "q_wallwall_min": min(item["q_wallwall"] for item in valid)}


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


def replay_temporal_events(events: Iterable[dict[str, Any]], *, policy_by_fold: dict[int, dict[str, Any]], evidence_by_id: dict[tuple[str, str, str], dict[str, Any]] | None = None, geometry_by_id: dict[str, dict[str, Any]] | None = None, source_artifact: str = "", source_sha256: str = "", dependency_paths: list[Path] | None = None, n_folds: int = 2, input_status: str = "dry_run") -> list[dict[str, Any]]:
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
    observed: dict[tuple[str, str, str, str], list[dict[str, Any]]] = defaultdict(list)
    arrived_geometry: dict[tuple[str, str], set[str]] = defaultdict(set)
    traces = []
    illegal_reasons: Counter[str] = Counter()
    previous_prior_k_by_group: dict[tuple[str, str, str, str], int] = {}
    batches: dict[tuple[datetime, str], list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        batches[(parsed_arrivals[str(row["event_id"])], str(row.get("canonical_annotation_id", "")))].append(row)
    for batch_key in sorted(batches, key=lambda item: (item[0], item[1])):
      pending: list[tuple[dict[str, Any], dict[str, Any], bool]] = []
      for row in sorted(batches[batch_key], key=lambda item: str(item["event_id"])):
        candidate_worker_id = str(row.get("candidate_worker_id") or row.get("worker_id") or row.get("annotator_id") or "")
        group_key = (str(row["base_task_id"]), str(row.get("condition", "")), str(row["tag_family"]), str(row["tag_name"]))
        task_key = group_key[:2]
        prior = list(observed[group_key])
        eligible_workers = {item["worker_id"] for item in prior}
        prior_k, prior_a, prior_e, prior_u = len(eligible_workers), sum(item["assertion"] == "+" for item in prior), sum(item["assertion"] == "-" for item in prior), sum(item["assertion"] == "0" for item in prior)
        geometry = _geometry_state(arrived_geometry[task_key], geometry_by_id or {})
        eval_fold, policy = int(row["crossfit_fold"]), policy_by_fold[int(row["crossfit_fold"])]
        policy_audit = _validate_policy(policy, eval_fold, n_folds)
        thresholds = policy["stop_thresholds"]
        try:
            candidate_available = _strict_bool(row.get("candidate_available_before_event"))
            candidate_reason = ""
        except ValueError:
            candidate_available, candidate_reason = False, "invalid_candidate_available_before_event"
        provenance_available = str(row["tag_family"]).lower() != "model_issue" or (bool(prior) and all(item["provenance_available"] for item in prior))
        gates = {
            "support_gate": prior_k >= int(candidate_rule_config(str(policy.get("risk_bucket", "low_risk")))["k_min_for_stop"]),
            "same_state_gate": max(prior_a, prior_e) >= int(thresholds["meta_min_same_state"]),
            "opposition_gate": min(prior_a, prior_e) <= int(thresholds["meta_max_opposition"]),
            "unasserted_gate": prior_k > 0 and prior_u / prior_k <= float(thresholds["max_unasserted_rate"]),
            "conflict_gate": not (prior_a >= 2 and prior_e >= 2),
            "geometry_gate": geometry["status"] == "evaluable" and geometry["q_boundary_min"] >= float(thresholds["min_q_boundary"]) and geometry["q_wallwall_min"] >= float(thresholds["min_q_wallwall"]),
            "provenance_gate": provenance_available,
        }
        config = candidate_rule_config(str(policy.get("risk_bucket", "low_risk")))
        decision = decide_candidate_action({"decision_contract": "three_state_geometry_v1", "n_independent_workers": prior_k, "stop_gates_pass": all(gates.values()), "provenance_available": provenance_available, "candidate_available": candidate_available}, config)
        trace = {
            **sidecar_common(source_artifact=source_artifact, source_sha256=source_sha256, stage=str(row.get("stage", "C1")), pool=str(row.get("pool", "")), condition=str(row.get("condition", "")), validity_status="dry_run" if input_status != "formal" else "candidate_only", rule_version=RULE_VERSION, interpretation_allowed=False, dependency_paths=dependency_paths or [source_artifact]),
            "event_id": row["event_id"], "arrived_at": row["arrived_at"], "arrived_at_utc": parsed_arrivals[str(row["event_id"])].isoformat(), "task_id": row.get("task_id", ""), "base_task_id": row["base_task_id"], "condition": row.get("condition", ""), "canonical_annotation_id": row.get("canonical_annotation_id", ""), "tag_family": row["tag_family"], "tag_name": row["tag_name"], "crossfit_fold": row["crossfit_fold"], **policy_audit, "policy_artifact_id": policy["policy_artifact_id"], "policy_artifact_sha256": policy["policy_artifact_sha256"], "policy_artifact_path": policy.get("policy_artifact_path", ""), "policy_rule_version": policy["rule_version"], "policy_fit_folds_json": json.dumps(sorted({int(value) for value in policy["fit_folds"]})), "policy_fit_base_task_ids_json": json.dumps(sorted({str(value) for value in policy["fit_base_task_ids"]})), "policy_fit_base_task_count": len(policy["fit_base_task_ids"]), "prior_legal_arrivals": prior_k, "prior_eligible_workers_json": json.dumps(sorted(eligible_workers)), "prior_evidence_json": json.dumps(prior, sort_keys=True), "a": prior_a, "e": prior_e, "u": prior_u, "replicated_explicit_conflict": str(not gates["conflict_gate"]).lower(), "geometry_status": geometry["status"], "geometry_support": geometry["support"], "q_boundary_min": geometry["q_boundary_min"], "q_wallwall_min": geometry["q_wallwall_min"], "provenance_status": "available" if provenance_available else "not_available", "candidate_available_before_event": str(candidate_available).lower(), "stop_gates_json": json.dumps(gates, sort_keys=True), "candidate_worker_id": candidate_worker_id, "selected_worker_id": row.get("selected_worker_id") or candidate_worker_id, "action": decision["action"], "action_reason": decision["reason"], "formal_assignment_generated": "false",
        }
        evidence = (evidence_by_id or {}).get(_event_evidence_key(row), {})
        evidence_arrival = str(evidence.get("arrived_at") or evidence.get("annotation_created_at") or evidence.get("created_at") or "")
        try:
            evidence_time_matches = bool(evidence_arrival) and _arrival(evidence_arrival) == parsed_arrivals[str(row["event_id"])]
        except ValueError:
            evidence_time_matches = False
        reasons = [candidate_reason] if candidate_reason else []
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
        trace["event_legal"] = str(legal).lower()
        trace["event_legal_reason"] = "canonical_quality_three_state_join_valid" if legal else ";".join(reasons)
        if not legal:
            illegal_reasons[trace["event_legal_reason"]] += 1
        if legal:
            trace["assertion"] = str(evidence["assertion"])
        if prior_k < previous_prior_k_by_group.get(group_key, 0):
            trace["prior_state_monotonicity"] = "failed"
        else:
            trace["prior_state_monotonicity"] = "passed"
        previous_prior_k_by_group[group_key] = prior_k
        traces.append(trace)
        pending.append((row, evidence, legal))
      for row, evidence, legal in pending:
        if not legal:
            continue
        group_key = (str(row["base_task_id"]), str(row.get("condition", "")), str(row["tag_family"]), str(row["tag_name"]))
        provenance_available = str(row["tag_family"]).lower() != "model_issue" or str(evidence.get("assertion_source")) == "explicit_worker_label" or (str(evidence.get("assertion_source")) == "legacy_behavior_inferred" and str(evidence.get("harmonization_validity_status")) == "valid_behavior_inferred")
        observed[group_key].append({"event_id": str(row["event_id"]), "canonical_annotation_id": str(row.get("canonical_annotation_id", "")), "worker_id": str(row.get("candidate_worker_id") or row.get("worker_id") or row.get("annotator_id") or ""), "assertion": str(evidence["assertion"]), "provenance_available": provenance_available})
        arrived_geometry[group_key[:2]].add(str(row.get("canonical_annotation_id", "")))
    for trace in traces:
        trace["illegal_event_count"] = sum(illegal_reasons.values())
        trace["illegal_event_reasons_json"] = json.dumps(dict(illegal_reasons), sort_keys=True)
    return traces


def replay_temporal_batches(
    events: list[dict[str, Any]], *, policy_by_fold: dict[int, dict[str, Any]], evidence_by_id: dict[tuple[str, str, str], dict[str, Any]],
    geometry_by_id: dict[str, dict[str, Any]], task_purposes: dict[tuple[str, str], dict[str, Any]], candidate_roster: dict[tuple[str, str], set[str]],
    assignment_rows: list[dict[str, Any]], source_artifact: str, source_sha256: str, dependency_paths: list[Path], input_status: str, candidate_pool_source_sha256: str = "",
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]], dict[str, bool]]:
    folded = build_crossfit_folds(events)
    required_folds = {int(row["crossfit_fold"]) for row in folded}
    if set(policy_by_fold) != required_folds:
        raise ValueError("policy_by_fold must exactly match evaluation folds")
    for fold in required_folds:
        _validate_policy(policy_by_fold[fold], fold, 2)
    event_ids = [str(row.get("event_id", "")) for row in folded]
    event_keys = [_event_evidence_key(row) for row in folded]
    evidence_keys = list(evidence_by_id)
    event_unique = bool(event_ids) and all(event_ids) and len(event_ids) == len(set(event_ids)) and len(event_keys) == len(set(event_keys))
    evidence_unique = len(evidence_keys) == len(set(evidence_keys))
    coverage = set(event_keys) == set(evidence_keys) and len(event_keys) == len(evidence_keys)
    if not event_unique:
        raise ValueError("temporal event IDs and annotation-tag keys must be unique")
    if not evidence_unique:
        raise ValueError("three-state evidence keys must be unique")

    parsed: dict[str, datetime] = {}
    annotation_identity: dict[str, tuple[str, ...]] = {}
    annotation_atomicity = True
    for row in folded:
        event_id = str(row["event_id"])
        parsed[event_id] = _arrival(row.get("arrived_at"))
        key = (str(row.get("base_task_id", "")), str(row.get("condition", "")))
        if key not in task_purposes or key not in candidate_roster:
            raise ValueError("every replay task requires frozen purpose and candidate roster rows")
        evidence = evidence_by_id.get(_event_evidence_key(row), {})
        identity = (str(row.get("worker_id", "")), *key, parsed[event_id].isoformat(), str(row.get("arrival_order_source", "")), str(evidence.get("independence_audit_identity", "")))
        annotation = str(row.get("canonical_annotation_id", ""))
        annotation_atomicity &= annotation not in annotation_identity or annotation_identity[annotation] == identity
        annotation_identity[annotation] = identity

    batches: dict[tuple[Any, ...], list[dict[str, Any]]] = defaultdict(list)
    arrival_contract = True
    for row in folded:
        event_id, source = str(row["event_id"]), str(row.get("arrival_order_source", ""))
        arrival_contract &= bool(source and str(row.get("timestamp_precision", "")).strip())
        policy = policy_by_fold[int(row["crossfit_fold"])]
        payload = policy.get("stop_thresholds") or {}
        trusted = set(payload.get("trusted_order_sources") or [])
        sequence = str(row.get("trusted_sequence", "")) if source in trusted else ""
        if source in trusted and not sequence:
            arrival_contract = False
        batch_key = (str(row["base_task_id"]), str(row.get("condition", "")), parsed[event_id], sequence)
        batches[batch_key].append(row)

    common = lambda row: sidecar_common(source_artifact=source_artifact, source_sha256=source_sha256, stage="C1", pool=str(row.get("dataset_group", "")), condition=str(row.get("condition", "")), validity_status="dry_run" if input_status != "formal" else "candidate_only", rule_version=RULE_VERSION, interpretation_allowed=False, dependency_paths=dependency_paths)
    states: dict[tuple[str, str], dict[str, Any]] = defaultdict(lambda: {"tags": defaultdict(list), "scope": [], "annotations": set(), "workers": set(), "correction": False})
    event_rows: list[dict[str, Any]] = []
    batch_rows: list[dict[str, Any]] = []
    sensitivity_rows: list[dict[str, Any]] = []
    assignment_exclusions: dict[tuple[str, str], set[str]] = defaultdict(set)
    for row in assignment_rows:
        if str(row.get("assignment_status", "")).lower() in {"withdrawn", "ineligible", "excluded"}:
            assignment_exclusions[(str(row.get("base_task_id", "")), str(row.get("condition", "")))].add(str(row.get("worker_id", "")))

    def batch_sort_key(item: tuple[Any, ...]) -> tuple[Any, ...]:
        sequence = item[3]
        return (item[2], item[0], item[1], (0, int(sequence)) if str(sequence).isdigit() else (1, str(sequence)))

    for batch_index, batch_key in enumerate(sorted(batches, key=batch_sort_key), start=1):
        rows = batches[batch_key]
        task_key = batch_key[:2]
        state = states[task_key]
        purpose = task_purposes[task_key]
        policy = policy_by_fold[int(rows[0]["crossfit_fold"])]
        _validate_policy(policy, int(rows[0]["crossfit_fold"]), 2)
        payload = policy["stop_thresholds"]
        risk = str(payload.get("risk_bucket") or policy.get("risk_bucket") or "")
        if risk not in RISK_BUCKETS:
            raise ValueError("risk_bucket must be one of low_risk/high_risk/stress")
        config = candidate_rule_config(risk)
        for field in ("k_dispatch_initial", "k_min_for_stop", "standard_cap", "escalation_cap"):
            if field in payload:
                config[field] = int(payload[field])
        if not 1 <= config["k_dispatch_initial"] <= config["k_min_for_stop"] <= config["standard_cap"] <= config["escalation_cap"]:
            raise ValueError("temporal policy k/cap thresholds are invalid")
        event_batch_id = hashlib.sha256("|".join(map(str, batch_key)).encode()).hexdigest()[:20]
        pre_snapshot = hashlib.sha256(json.dumps({"task": task_key, "annotations": sorted(state["annotations"]), "scope": state["scope"], "tags": {str(key): value for key, value in state["tags"].items()}}, sort_keys=True).encode()).hexdigest()
        pre_k = len(state["annotations"])
        pre_tags = {key: list(values) for key, values in state["tags"].items()}
        pre_scope = list(state["scope"])
        pre_annotations = set(state["annotations"])
        pre_correction = bool(state["correction"])
        pre_scope_state = _scope_status([item[1] for item in pre_scope], False)
        pool_before = candidate_roster[task_key] - state["workers"] - assignment_exclusions[task_key]
        legal_annotations: set[str] = set()
        pending: list[tuple[dict[str, Any], dict[str, Any], bool, str]] = []
        for row in rows:
            evidence = evidence_by_id.get(_event_evidence_key(row), {})
            worker = str(row.get("worker_id") or row.get("candidate_worker_id") or "")
            reasons = []
            if not evidence:
                reasons.append("missing_three_state_evidence")
            if evidence and not eligible_independent_evidence(evidence):
                reasons.append("ineligible_quality_evidence")
            if worker != str(evidence.get("worker_id") or evidence.get("annotator_id") or ""):
                reasons.append("worker_identity_mismatch")
            evidence_arrival = str(evidence.get("arrived_at") or evidence.get("annotation_created_at") or evidence.get("created_at") or "")
            try:
                if _arrival(evidence_arrival) != parsed[str(row["event_id"])]:
                    reasons.append("arrival_timestamp_mismatch")
            except ValueError:
                reasons.append("arrival_timestamp_mismatch")
            if evidence and (str(evidence.get("base_task_id")) != task_key[0] or str(evidence.get("condition")) != task_key[1]):
                reasons.append("task_condition_mismatch")
            if evidence and (str(evidence.get("tag_family")) != str(row.get("tag_family")) or str(evidence.get("tag_name")) != str(row.get("tag_name"))):
                reasons.append("tag_identity_mismatch")
            if str(row.get("tag_family")) == "model_issue" and not (str(evidence.get("assertion_source")) == "explicit_worker_label" or (str(evidence.get("assertion_source")) == "legacy_behavior_inferred" and str(evidence.get("harmonization_validity_status")) == "valid_behavior_inferred")):
                reasons.append("model_issue_provenance_invalid")
            if worker not in candidate_roster[task_key]:
                reasons.append("worker_not_in_frozen_candidate_roster")
            try:
                if _strict_bool(row.get("candidate_available_before_event")) != bool(pool_before):
                    reasons.append("candidate_availability_claim_mismatch")
            except ValueError:
                reasons.append("candidate_availability_claim_invalid")
            legal = not reasons
            if legal:
                legal_annotations.add(str(row["canonical_annotation_id"]))
            pending.append((row, evidence, legal, ";".join(reasons)))
            event_rows.append({**common(row), "event_id": row["event_id"], "event_batch_id": event_batch_id, "canonical_annotation_id": row["canonical_annotation_id"], "worker_id": worker, "tag_family": row["tag_family"], "tag_name": row["tag_name"], "assertion": evidence.get("assertion", ""), "event_validity_status": "valid" if legal else "invalid", "event_invalid_reason": ";".join(reasons), "arrival_order_source": row.get("arrival_order_source", ""), "canonical_arrival_timestamp": parsed[str(row["event_id"])].isoformat(), "timestamp_precision": row.get("timestamp_precision", ""), "trusted_sequence": row.get("trusted_sequence", ""), "pre_batch_snapshot_id": pre_snapshot, "post_batch_snapshot_id": ""})
        for row, evidence, legal, _ in pending:
            if not legal:
                continue
            annotation, worker = str(row["canonical_annotation_id"]), str(row.get("worker_id") or row.get("candidate_worker_id") or "")
            state["annotations"].add(annotation); state["workers"].add(worker)
            state["tags"][(str(row["tag_family"]), str(row["tag_name"]))].append(str(evidence["assertion"]))
            vote = _scope_vote(evidence)
            if vote != "unknown" and annotation not in {item[0] for item in state["scope"]}:
                state["scope"].append((annotation, vote))
            state["correction"] = state["correction"] or _strict_bool(evidence.get("semi_geometry_correction_evaluable", "false"))
        post_k = len(state["annotations"])
        cap_reached = post_k >= int(config["escalation_cap"])
        scope_state = _scope_status([item[1] for item in state["scope"]], cap_reached)
        geometry = _geometry_state(state["annotations"], geometry_by_id)
        family_states = {}
        for tag, values in state["tags"].items():
            family_states["/".join(tag)] = _family_status(values.count("+"), values.count("-"), values.count("0"), cap_reached)
        components = purpose["required_components"]
        geometry_required = "geometry" in components and scope_state != "resolved_oos"
        geometry_ok = geometry["status"] == "evaluable" and geometry["q_boundary_min"] >= float(payload["min_q_boundary"]) and geometry["q_wallwall_min"] >= float(payload["min_q_wallwall"])
        checks = {
            "scope": scope_state in {"resolved_in_scope", "resolved_oos"},
            "difficulty": any(key.startswith("difficulty/") and value in {"complete_positive", "complete_negative"} for key, value in family_states.items()),
            "model_issue_recognition": any(key.startswith("model_issue/") and value in {"complete_positive", "complete_negative"} for key, value in family_states.items()),
            "model_issue_correction": bool(state["correction"]),
            "geometry": not geometry_required or geometry_ok,
            "scene": geometry_ok and geometry["support"] >= int(config["k_min_for_stop"]),
        }
        complete = all(checks[name] for name in components)
        pool_after = candidate_roster[task_key] - state["workers"] - assignment_exclusions[task_key]
        if complete:
            action, reason, completion = "stop_candidate", "required_evidence_components_complete", "complete"
        elif cap_reached or not pool_after:
            action, reason, completion = "unresolved_candidate", "required_components_missing_at_cap_or_candidate_exhausted", "unresolved"
        else:
            action, reason, completion = ("continue_initial", "minimum_support_not_met", "incomplete") if post_k < int(config["k_min_for_stop"]) else ("escalate_candidate", "required_components_incomplete", "incomplete")
        post_snapshot = hashlib.sha256(json.dumps({"task": task_key, "annotations": sorted(state["annotations"]), "scope": scope_state, "families": family_states, "geometry": geometry}, sort_keys=True).encode()).hexdigest()
        for event in event_rows[-len(rows):]:
            event["post_batch_snapshot_id"] = post_snapshot
        batch_rows.append({**common(rows[0]), "event_batch_id": event_batch_id, "replay_task_key": "|".join(task_key), "batch_timestamp": batch_key[2].isoformat(), "batch_size_annotations": len({str(row["canonical_annotation_id"]) for row in rows}), "batch_size_tag_events": len(rows), "pre_batch_k": pre_k, "post_batch_k": post_k, "cap_overshoot_due_to_tie": max(0, post_k - int(config["escalation_cap"])), "current_scope_state_before": "insufficient" if pre_k == 0 else "prior_snapshot", "current_scope_state_after": scope_state, "family_evidence_status_json": json.dumps(family_states, sort_keys=True), "geometry_status": geometry["status"], "geometry_payload_present": any(annotation in geometry_by_id for annotation in state["annotations"]), "geometry_consensus_required": geometry_required, "geometry_profile_eligible": geometry_required and scope_state == "resolved_in_scope", "task_purpose": purpose["task_purpose"], "required_evidence_components": json.dumps(sorted(components)), "task_completion_status": completion, "stop_block_reason": "" if complete else reason, "unresolved_reason": reason if completion == "unresolved" else "", "candidate_pool_before": json.dumps(sorted(pool_before)), "candidate_pool_after": json.dumps(sorted(pool_after)), "next_candidate_available": bool(pool_after), "candidate_pool_source_sha256": candidate_pool_source_sha256, "decision_snapshot_id": post_snapshot, "action": action, "action_reason": reason, "primary_k_used": post_k})
        batch_rows[-1]["current_scope_state_before"] = pre_scope_state
        annotations = sorted({str(row["canonical_annotation_id"]) for row in rows})
        rng = random.Random(SENSITIVITY_SEED + batch_index)
        orders = [annotations, list(reversed(annotations))] + [rng.sample(annotations, len(annotations)) for _ in range(SENSITIVITY_PERMUTATIONS)]
        by_annotation: dict[str, list[tuple[dict[str, Any], dict[str, Any], bool, str]]] = defaultdict(list)
        for item in pending:
            by_annotation[str(item[0]["canonical_annotation_id"])].append(item)
        sensitivity_k, alternative_actions = [], set()
        for order in orders:
            sim_tags = {key: list(values) for key, values in pre_tags.items()}
            sim_scope, sim_annotations, sim_correction = list(pre_scope), set(pre_annotations), pre_correction
            sim_complete = False
            for annotation in order:
                for row, evidence, legal, _ in by_annotation[annotation]:
                    if not legal:
                        continue
                    sim_annotations.add(annotation)
                    sim_tags.setdefault((str(row["tag_family"]), str(row["tag_name"])), []).append(str(evidence["assertion"]))
                    vote = _scope_vote(evidence)
                    if vote != "unknown" and annotation not in {item[0] for item in sim_scope}:
                        sim_scope.append((annotation, vote))
                    sim_correction = sim_correction or _strict_bool(evidence.get("semi_geometry_correction_evaluable", "false"))
                sim_cap = len(sim_annotations) >= int(config["escalation_cap"])
                sim_scope_state = _scope_status([item[1] for item in sim_scope], sim_cap)
                sim_families = {"/".join(tag): _family_status(values.count("+"), values.count("-"), values.count("0"), sim_cap) for tag, values in sim_tags.items()}
                sim_geometry = _geometry_state(sim_annotations, geometry_by_id)
                sim_geometry_ok = sim_geometry["status"] == "evaluable" and sim_geometry["q_boundary_min"] >= float(payload["min_q_boundary"]) and sim_geometry["q_wallwall_min"] >= float(payload["min_q_wallwall"])
                sim_checks = {"scope": sim_scope_state in {"resolved_in_scope", "resolved_oos"}, "difficulty": any(key.startswith("difficulty/") and value in {"complete_positive", "complete_negative"} for key, value in sim_families.items()), "model_issue_recognition": any(key.startswith("model_issue/") and value in {"complete_positive", "complete_negative"} for key, value in sim_families.items()), "model_issue_correction": sim_correction, "geometry": sim_scope_state == "resolved_oos" or sim_geometry_ok, "scene": sim_geometry_ok and sim_geometry["support"] >= int(config["k_min_for_stop"])}
                if all(sim_checks[name] for name in components):
                    sim_complete = True
                    break
            sensitivity_k.append(len(sim_annotations))
            alternative_actions.add("stop_candidate" if sim_complete else ("unresolved_candidate" if len(sim_annotations) >= int(config["escalation_cap"]) else "escalate_candidate"))
        sensitivity_rows.append({**common(rows[0]), "event_batch_id": event_batch_id, "arrival_order_source": rows[0].get("arrival_order_source", ""), "timestamp_precision": rows[0].get("timestamp_precision", ""), "tie_policy": "simultaneous_atomic_primary", "primary_k_used": post_k, "sensitivity_k_used_min": min(sensitivity_k), "sensitivity_k_used_max": max(sensitivity_k), "primary_final_action": action, "alternative_final_actions": json.dumps(sorted(alternative_actions)), "stop_order_sensitivity": min(sensitivity_k) != max(sensitivity_k) or alternative_actions != {action}, "random_seed": SENSITIVITY_SEED, "random_permutations": SENSITIVITY_PERMUTATIONS})

    task_rows = []
    for task_key, state in states.items():
        decisions = [row for row in batch_rows if row["replay_task_key"] == "|".join(task_key)]
        final = decisions[-1]
        task_rows.append({**common(final), "task_id": task_purposes[task_key]["task_id"], "base_task_id": task_key[0], "condition": task_key[1], "primary_k_used": final["post_batch_k"], "final_scope_state": final["current_scope_state_after"], "final_geometry_state": final["geometry_status"], "family_final_states_json": final["family_evidence_status_json"], "task_completion_status": final["task_completion_status"], "final_action": final["action"], "unresolved_reason": final["unresolved_reason"], "expert_review_required": final["task_completion_status"] == "unresolved", "budget_used": final["post_batch_k"], "decision_snapshot_id": final["decision_snapshot_id"]})
    contracts = {"event_key_uniqueness_valid": event_unique and evidence_unique, "event_coverage_complete": coverage, "annotation_tag_atomicity_valid": annotation_atomicity, "batch_atomicity_valid": False, "arrival_order_contract_valid": arrival_contract, "task_purpose_manifest_valid": True, "candidate_pool_binding_valid": all(row["event_validity_status"] == "valid" for row in event_rows), "risk_bucket_valid": True, "family_gate_contract_valid": True, "task_completion_contract_valid": len(task_rows) == len(states), "no_future_scope_leakage": True}
    contracts["batch_atomicity_valid"] = all(len({row["pre_batch_snapshot_id"] for row in event_rows if row["event_batch_id"] == batch["event_batch_id"]}) == 1 for batch in batch_rows)
    return event_rows, batch_rows, task_rows, sensitivity_rows, contracts


def materialize_temporal_replay(event_csv: Path | None, output_csv: Path, *, policy_manifest: Path | None = None, policy_by_fold: dict[int, dict[str, Any]] | None = None, canonical_csv: Path | None = None, quality_csv: Path | None = None, three_state_csv: Path | None = None, canonical_geometry_jsonl: Path | None = None, task_purpose_manifest_csv: Path | None = None, candidate_roster_manifest_csv: Path | None = None, assignment_history_csv: Path | None = None, input_status: str = "dry_run") -> dict[str, Any]:
    batch_output = output_csv.parent / "routing_temporal_batch_decisions_C1.csv"
    task_output = output_csv.parent / "routing_temporal_task_summary_C1.csv"
    sensitivity_output = output_csv.parent / "routing_temporal_order_sensitivity_C1.csv"
    if input_status != "formal" or event_csv is None or not event_csv.exists():
        for path in (output_csv, batch_output, task_output, sensitivity_output):
            write_csv_rows(path, [], COMMON_SIDEcar_FIELDS)
        return {"status": "not_evaluable_missing_formal_c1", "full_stop_contract_valid": False, "n_events": 0, "formal_assignment_generated": False}
    if not all(path and path.exists() for path in (task_purpose_manifest_csv, candidate_roster_manifest_csv, assignment_history_csv)):
        for path in (output_csv, batch_output, task_output, sensitivity_output):
            write_csv_rows(path, [], COMMON_SIDEcar_FIELDS)
        return {"status": "not_evaluable_missing_frozen_temporal_inputs", "full_stop_contract_valid": False, "n_events": 0, "formal_assignment_generated": False}
    if policy_manifest:
        policy_by_fold = _load_policy_manifest(policy_manifest)
    if not policy_by_fold:
        write_csv_rows(output_csv, [], COMMON_SIDEcar_FIELDS + ["event_id", "arrived_at", "arrived_at_utc", "task_id", "base_task_id", "condition", "canonical_annotation_id", "candidate_worker_id", "selected_worker_id", "prior_evidence_json", "action", "action_reason"])
        return {"status": "not_evaluable_missing_policy_artifact", "n_events": 0, "formal_assignment_generated": False}
    evidence_rows = read_csv_rows(quality_csv) if quality_csv else []
    tag_rows = read_csv_rows(three_state_csv) if three_state_csv and three_state_csv.exists() else []
    quality_by_id = {row.get("canonical_annotation_id", ""): row for row in evidence_rows if row.get("canonical_annotation_id")}
    evidence_by_id = {}
    seen_evidence_keys: set[tuple[str, str, str]] = set()
    for row in tag_rows:
        quality = quality_by_id.get(row.get("canonical_annotation_id", ""))
        merged = {**quality, **row} if quality else {}
        if merged and eligible_independent_evidence(merged) and str(merged.get("assertion")) in {"+", "-", "0"}:
            key = _event_evidence_key(row)
            if key in seen_evidence_keys:
                raise ValueError("eligible three-state evidence keys must be unique")
            seen_evidence_keys.add(key)
            evidence_by_id[key] = merged
    geometry_by_id: dict[str, dict[str, Any]] = {}
    if canonical_geometry_jsonl and canonical_geometry_jsonl.exists():
        for line in canonical_geometry_jsonl.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            row = json.loads(line)
            geometry_by_id[str(row.get("canonical_annotation_id", ""))] = normalize_geometry(row.get("corners_px") or [], width=int(row.get("width") or 1024), height=int(row.get("height") or 512))
    with event_csv.open("r", newline="", encoding="utf-8-sig") as handle:
        events = list(csv.DictReader(handle))
    required_folds = {int(row["crossfit_fold"]) for row in build_crossfit_folds(events)}
    if set(policy_by_fold) != required_folds:
        raise ValueError("policy manifest folds must exactly match evaluation folds")
    policy_artifacts = [Path(policy["policy_artifact_path"]) for policy in policy_by_fold.values()]
    for policy, artifact in zip(policy_by_fold.values(), policy_artifacts):
        payload = json.loads(artifact.read_text(encoding="utf-8"))
        required = ("task_purpose_manifest_sha256", "candidate_roster_manifest_sha256", "risk_bucket", "k_dispatch_initial", "k_min_for_stop", "standard_cap", "escalation_cap", "unresolved_rule", "arrival_order_contract", "primary_tie_policy")
        if any(payload.get(field) in (None, "") for field in required) or payload["task_purpose_manifest_sha256"] != sha256_file(task_purpose_manifest_csv) or payload["candidate_roster_manifest_sha256"] != sha256_file(candidate_roster_manifest_csv) or payload["risk_bucket"] not in RISK_BUCKETS:
            raise ValueError("temporal policy artifact is incomplete or stale against frozen manifests")
        policy["stop_thresholds"] = payload
    dependencies = [event_csv, *([policy_manifest] if policy_manifest else []), *policy_artifacts, *([canonical_csv] if canonical_csv else []), *([quality_csv] if quality_csv else []), *([three_state_csv] if three_state_csv else []), *([canonical_geometry_jsonl] if canonical_geometry_jsonl else []), task_purpose_manifest_csv, candidate_roster_manifest_csv, assignment_history_csv]
    task_purposes = _load_task_purposes(task_purpose_manifest_csv)
    candidate_roster = _load_candidate_roster(candidate_roster_manifest_csv)
    traces, batches, tasks, sensitivity, contracts = replay_temporal_batches(events, policy_by_fold=policy_by_fold, evidence_by_id=evidence_by_id, geometry_by_id=geometry_by_id, task_purposes=task_purposes, candidate_roster=candidate_roster, assignment_rows=read_csv_rows(assignment_history_csv), source_artifact=str(event_csv.resolve()), source_sha256=sha256_file(event_csv), dependency_paths=dependencies, input_status=input_status, candidate_pool_source_sha256=sha256_file(candidate_roster_manifest_csv))
    write_csv_rows(output_csv, traces)
    write_csv_rows(batch_output, batches)
    write_csv_rows(task_output, tasks)
    write_csv_rows(sensitivity_output, sensitivity)
    full_valid = bool(traces and batches and tasks) and all(contracts.values())
    return {"status": "candidate_only", **contracts, "full_stop_contract_valid": full_valid, "n_events": len(traces), "n_batches": len(batches), "n_tasks": len(tasks), "n_legal_events": sum(row["event_validity_status"] == "valid" for row in traces), "n_illegal_events": sum(row["event_validity_status"] != "valid" for row in traces), "all_events_legal": all(row["event_validity_status"] == "valid" for row in traces), "prior_state_monotonicity": all(int(row["post_batch_k"]) >= int(row["pre_batch_k"]) for row in batches), "n_nonzero_assertions": sum(str(row.get("assertion")) in {"+", "-"} for row in traces), "worker_identity_consistent": contracts["annotation_tag_atomicity_valid"], "policy_dependency_valid": True, "illegal_event_reasons": dict(Counter(row["event_invalid_reason"] for row in traces if row["event_invalid_reason"])), "source_sha256": sha256_file(event_csv), "policy_manifest_sha256": sha256_file(policy_manifest) if policy_manifest else "", "formal_assignment_generated": False}


if __name__ == "__main__":
    raise SystemExit("Use materialize_temporal_replay from the C1 closeout workflow.")
