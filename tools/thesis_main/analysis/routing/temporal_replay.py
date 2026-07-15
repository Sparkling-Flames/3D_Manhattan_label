from __future__ import annotations

import csv
import hashlib
import json
import random
import re
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from tools.thesis_main.analysis.geometry_consensus.pairwise import pairwise_similarity
from tools.thesis_main.analysis.geometry_consensus.representation import normalize_geometry
from tools.thesis_main.analysis.routing.crossfit import build_crossfit_folds
from tools.thesis_main.analysis.vfinal_artifact_utils import (
    COMMON_SIDEcar_FIELDS,
    canonical_path,
    dependency_bundle,
    eligible_independent_evidence,
    read_csv_rows,
    sha256_file,
    sha256_json,
    sidecar_common,
    write_csv_rows,
)
from tools.thesis_main.registry.materialize_meta_label_three_state_sidecars import DIFFICULTY_TAGS, MODEL_ISSUE_TAGS


RULE_VERSION = "temporal_routing_replay_v3"
LEDGER_VERSION = "temporal_event_ledger_v2"
TASK_PURPOSE_MANIFEST_VERSION = "task_purpose_v1"
CANDIDATE_ROSTER_MANIFEST_VERSION = "candidate_roster_v1"
ASSIGNMENT_HISTORY_MANIFEST_VERSION = "assignment_history_v1"
RISK_BUCKETS = {"low_risk", "high_risk", "stress"}
TASK_PURPOSES = {"scope_only", "geometry_production", "calibration_scene_profile", "meta_label_only", "semi_correction_evaluation"}
EVIDENCE_COMPONENTS = {"scope", "difficulty", "model_issue_recognition", "model_issue_correction", "geometry", "scene"}
POLICY_KINDS = ("scope", "tag", "geometry", "correction", "risk")
CONTRACT_FIELDS = (
    "event_key_uniqueness_valid",
    "event_coverage_complete",
    "annotation_tag_atomicity_valid",
    "batch_atomicity_valid",
    "arrival_order_contract_valid",
    "task_purpose_manifest_valid",
    "candidate_pool_binding_valid",
    "risk_bucket_valid",
    "family_gate_contract_valid",
    "task_completion_contract_valid",
    "no_future_scope_leakage",
)
SENSITIVITY_SEED = 20260714
SENSITIVITY_PERMUTATIONS = 100
TERMINAL_STATES = {"COMPLETE", "UNRESOLVED"}


def _arrival(value: Any) -> datetime:
    text = str(value or "").strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    parsed = datetime.fromisoformat(text)
    if parsed.tzinfo is None:
        raise ValueError("arrival timestamp must include a timezone")
    return parsed.astimezone(timezone.utc)


def _event_time(row: dict[str, Any]) -> datetime:
    return _arrival(row.get("canonical_arrival_timestamp") or row.get("arrived_at"))


def _timestamp_precision(value: Any) -> str:
    match = re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.(\d+))?(?:Z|[+-]\d{2}:\d{2})", str(value or "").strip())
    if not match:
        raise ValueError("arrival timestamp precision cannot be determined")
    digits = len(match.group(1) or "")
    if digits == 0:
        return "second"
    if digits <= 3:
        return "millisecond"
    if digits <= 6:
        return "microsecond"
    raise ValueError("arrival timestamp precision exceeds the frozen microsecond contract")


def _event_evidence_key(row: dict[str, Any]) -> tuple[str, str, str]:
    return str(row.get("canonical_annotation_id", "")), str(row.get("tag_family", "")), str(row.get("tag_name", ""))


def _task_key(row: dict[str, Any]) -> tuple[str, str]:
    return str(row.get("base_task_id", "")), str(row.get("condition", ""))


def _fold_for_base(base_task_id: str, n_folds: int) -> int:
    return int(hashlib.sha256(base_task_id.encode("utf-8")).hexdigest()[:8], 16) % max(2, int(n_folds))


def _strict_bool(value: Any) -> bool:
    text = str(value).strip().lower()
    if text not in {"true", "false"}:
        raise ValueError("boolean value must be true or false")
    return text == "true"


def _items(value: Any) -> list[str]:
    if isinstance(value, (list, tuple, set)):
        return [str(item).strip() for item in value if str(item).strip()]
    text = str(value or "").strip()
    if not text:
        return []
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        parsed = text.replace(";", ",").split(",")
    return [str(item).strip() for item in (parsed if isinstance(parsed, list) else [parsed]) if str(item).strip()]


def _sha_matches(path: Path, declared: Any) -> bool:
    return path.exists() and sha256_file(path) == str(declared or "").lower()


def _resolve(base: Path, value: Any) -> Path:
    path = Path(str(value or ""))
    return (base / path).resolve() if not path.is_absolute() else path.resolve()


def _policy_json(path: Path, declared_sha: Any, policy_id: Any, required: tuple[str, ...]) -> dict[str, Any]:
    if not _sha_matches(path, declared_sha):
        raise ValueError(f"policy artifact SHA mismatch: {path}")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"policy artifact is invalid JSON: {path}") from exc
    if payload.get("policy_id") != str(policy_id) or any(payload.get(field) in (None, "") for field in required):
        raise ValueError(f"policy artifact contract is incomplete: {path}")
    return payload


def _required_tags(families: list[str], names: list[str]) -> set[tuple[str, str]]:
    tags: set[tuple[str, str]] = set()
    for name in names:
        if "/" in name:
            family, tag = name.split("/", 1)
        elif len(families) == 1:
            family, tag = families[0], name
        else:
            raise ValueError("unqualified required tag requires exactly one required family")
        if tag == "*":
            vocabulary = DIFFICULTY_TAGS if family == "difficulty" else MODEL_ISSUE_TAGS if family == "model_issue" else ()
            tags.update((family, item) for item in vocabulary)
        else:
            tags.add((family, tag))
    allowed = {("difficulty", tag) for tag in DIFFICULTY_TAGS} | {("model_issue", tag) for tag in MODEL_ISSUE_TAGS}
    if not tags.issubset(allowed):
        raise ValueError("task-purpose manifest contains an unknown required tag")
    return tags


def _load_task_purposes(path: Path) -> tuple[dict[tuple[str, str], dict[str, Any]], list[Path]]:
    rows = read_csv_rows(path)
    required = {
        "task_id", "base_task_id", "condition", "dataset_group", "task_purpose", "required_evidence_components",
        "required_tag_family", "required_tag_names", "scope_policy_id", "tag_policy_id", "geometry_policy_id",
        "correction_policy_id", "risk_policy_id", "risk_bucket", "source_assignment_path", "source_assignment_sha256", "manifest_version",
    }
    policy_fields = {f"{kind}_policy_{suffix}" for kind in POLICY_KINDS for suffix in ("path", "sha256")}
    if not rows or not required.union(policy_fields).issubset(rows[0]):
        raise ValueError("task-purpose manifest schema is incomplete")
    purposes: dict[tuple[str, str], dict[str, Any]] = {}
    dependencies: list[Path] = [path.resolve()]
    policy_required = {
        "scope": ("meta_min_same_state", "meta_max_opposition", "max_unasserted_rate"),
        "tag": ("meta_min_same_state", "meta_max_opposition", "max_unasserted_rate"),
        "geometry": ("min_q_boundary", "min_q_wallwall", "min_geometry_support"),
        "correction": ("min_complete_workers", "require_initialization_provenance", "require_final_geometry", "require_edit_metrics", "require_reference_outcome"),
        "risk": ("risk_bucket", "k_dispatch_initial", "k_min_for_stop", "standard_cap", "escalation_cap", "unresolved_rule"),
    }
    for row in rows:
        key = _task_key(row)
        components = set(_items(row["required_evidence_components"]))
        families = _items(row["required_tag_family"])
        tags = _required_tags(families, _items(row["required_tag_names"]))
        if key in purposes or not all(key) or row["task_purpose"] not in TASK_PURPOSES or not components or not components.issubset(EVIDENCE_COMPONENTS) or row["manifest_version"] != TASK_PURPOSE_MANIFEST_VERSION:
            raise ValueError("task-purpose manifest contains a duplicate or invalid task")
        if "difficulty" in components and not any(family == "difficulty" for family, _ in tags):
            raise ValueError("difficulty component requires frozen difficulty tags")
        if "model_issue_recognition" in components and not any(family == "model_issue" for family, _ in tags):
            raise ValueError("model-issue recognition requires frozen model-issue tags")
        source_assignment = _resolve(path.parent, row["source_assignment_path"])
        if not _sha_matches(source_assignment, row["source_assignment_sha256"]):
            raise ValueError("task-purpose assignment dependency is missing or stale")
        dependencies.append(source_assignment)
        policies: dict[str, dict[str, Any]] = {}
        policy_paths: dict[str, str] = {}
        for kind in POLICY_KINDS:
            artifact = _resolve(path.parent, row[f"{kind}_policy_path"])
            payload = _policy_json(artifact, row[f"{kind}_policy_sha256"], row[f"{kind}_policy_id"], policy_required[kind])
            policies[kind] = payload
            policy_paths[kind] = str(artifact)
            dependencies.append(artifact)
        if row["risk_bucket"] not in RISK_BUCKETS or policies["risk"]["risk_bucket"] != row["risk_bucket"]:
            raise ValueError("task-purpose risk bucket is invalid or disagrees with its policy")
        purposes[key] = {**row, "required_components": components, "required_tags": tags, "policies": policies, "policy_paths": policy_paths}
    return purposes, dependencies


def _load_candidate_roster(path: Path) -> tuple[dict[tuple[str, str], dict[str, dict[str, Any]]], list[Path]]:
    rows = read_csv_rows(path)
    required = {
        "base_task_id", "condition", "worker_id", "candidate_eligible", "exclusion_reason", "source_admission_path",
        "source_admission_sha256", "source_assignment_path", "source_assignment_sha256", "manifest_version",
    }
    if not rows or not required.issubset(rows[0]):
        raise ValueError("candidate roster manifest schema is incomplete")
    roster: dict[tuple[str, str], dict[str, dict[str, Any]]] = defaultdict(dict)
    dependencies: list[Path] = [path.resolve()]
    for row in rows:
        key, worker = _task_key(row), str(row.get("worker_id", ""))
        if not all((*key, worker)) or worker in roster[key] or row["manifest_version"] != CANDIDATE_ROSTER_MANIFEST_VERSION:
            raise ValueError("candidate roster contains a duplicate or missing identity")
        admission = _resolve(path.parent, row["source_admission_path"])
        assignment = _resolve(path.parent, row["source_assignment_path"])
        if not _sha_matches(admission, row["source_admission_sha256"]) or not _sha_matches(assignment, row["source_assignment_sha256"]):
            raise ValueError("candidate roster source dependency is missing or stale")
        roster[key][worker] = {**row, "candidate_eligible": _strict_bool(row["candidate_eligible"])}
        dependencies.extend((admission, assignment))
    return dict(roster), dependencies


def _load_assignment_history(path: Path) -> tuple[list[dict[str, Any]], list[Path]]:
    rows = read_csv_rows(path)
    required = {"base_task_id", "condition", "worker_id", "assignment_status", "effective_at", "source_manifest_path", "source_manifest_sha256", "manifest_version"}
    if not rows:
        raise ValueError("assignment history has no semantic baseline rows")
    if not required.issubset(rows[0]):
        raise ValueError("assignment history schema is incomplete")
    allowed = {"eligible", "available", "unassigned", "assigned", "completed", "excluded", "withdrawn", "ineligible"}
    seen: set[tuple[str, str, str, str]] = set()
    dependencies: list[Path] = [path.resolve()]
    output: list[dict[str, Any]] = []
    for row in rows:
        identity = (*_task_key(row), str(row.get("worker_id", "")), str(row.get("effective_at", "")))
        source = _resolve(path.parent, row["source_manifest_path"])
        if not all(identity) or identity in seen or str(row.get("assignment_status", "")).lower() not in allowed or row["manifest_version"] != ASSIGNMENT_HISTORY_MANIFEST_VERSION or not _sha_matches(source, row["source_manifest_sha256"]):
            raise ValueError("assignment history contains invalid, duplicate, or stale rows")
        seen.add(identity)
        output.append({**row, "assignment_status": str(row["assignment_status"]).lower(), "_effective_at": _arrival(row["effective_at"])})
        dependencies.append(source)
    allowed_transitions = {
        "eligible": {"eligible", "available", "unassigned", "assigned", "excluded", "withdrawn", "ineligible"},
        "available": {"available", "eligible", "unassigned", "assigned", "excluded", "withdrawn", "ineligible"},
        "unassigned": {"unassigned", "eligible", "available", "assigned", "excluded", "withdrawn", "ineligible"},
        "assigned": {"assigned", "available", "unassigned", "completed", "excluded", "withdrawn", "ineligible"},
        "completed": {"completed"},
        "excluded": {"excluded", "eligible", "available", "unassigned"},
        "withdrawn": {"withdrawn", "eligible", "available", "unassigned"},
        "ineligible": {"ineligible", "eligible", "available", "unassigned"},
    }
    histories: dict[tuple[str, str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in output:
        histories[(*_task_key(row), str(row["worker_id"]))].append(row)
    for history in histories.values():
        ordered = sorted(history, key=lambda row: row["_effective_at"])
        for previous, current in zip(ordered, ordered[1:]):
            if current["assignment_status"] not in allowed_transitions[previous["assignment_status"]]:
                raise ValueError("assignment history contains illegal state transition")
    return output, dependencies


def _validate_assignment_history_for_replay(
    rows: list[dict[str, Any]], events: list[dict[str, Any]], roster: dict[tuple[str, str], dict[str, dict[str, Any]]]
) -> None:
    roster_keys = {(task, worker) for task, workers in roster.items() for worker in workers}
    if any((_task_key(row), str(row["worker_id"])) not in roster_keys for row in rows):
        raise ValueError("assignment history worker is absent from candidate roster")
    first_arrival: dict[tuple[str, str], datetime] = {}
    for event in events:
        task = _task_key(event)
        arrived = _arrival(event.get("canonical_arrival_timestamp"))
        first_arrival[task] = min(first_arrival.get(task, arrived), arrived)
    for task, arrived in first_arrival.items():
        if not any(_task_key(row) == task and row["_effective_at"] <= arrived for row in rows):
            raise ValueError("assignment history lacks a trusted baseline for replay task")


def _load_policy_manifest(path: Path) -> dict[int, dict[str, Any]]:
    pairs = json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=lambda values: values)
    if not isinstance(pairs, list):
        raise ValueError("policy manifest must be a fold-keyed JSON object")
    keys = [str(key) for key, _ in pairs]
    if len(keys) != len(set(keys)):
        raise ValueError("policy manifest contains duplicate fold keys")
    policies: dict[int, dict[str, Any]] = {}
    for key, value in pairs:
        fold = int(key)
        if fold in policies:
            raise ValueError("policy manifest contains duplicate numeric fold keys")
        policy = dict(value)
        policy["policy_artifact_path"] = str(_resolve(path.parent, policy.get("policy_artifact_path")))
        policies[fold] = policy
    return policies


def _validate_policy(policy: dict[str, Any], eval_fold: int, n_folds: int) -> dict[str, Any]:
    required = ("policy_artifact_id", "policy_artifact_sha256", "policy_artifact_path", "rule_version", "fit_folds", "fit_base_task_ids")
    if any(policy.get(field) in (None, "") for field in required):
        raise ValueError("temporal policy is missing audit fields")
    artifact = canonical_path(policy["policy_artifact_path"])
    if not _sha_matches(artifact, policy["policy_artifact_sha256"]):
        raise ValueError("temporal policy artifact SHA mismatch")
    fit_folds = {int(value) for value in policy["fit_folds"]}
    fit_base_ids = {str(value).strip() for value in policy["fit_base_task_ids"] if str(value).strip()}
    if not fit_base_ids or eval_fold in fit_folds or any(_fold_for_base(base, n_folds) == eval_fold for base in fit_base_ids):
        raise ValueError("temporal policy fit set leaks into the evaluation fold")
    if any(_fold_for_base(base, n_folds) not in fit_folds for base in fit_base_ids):
        raise ValueError("temporal policy fit base-tasks and folds disagree")
    try:
        payload = json.loads(artifact.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError("temporal policy artifact must be valid JSON") from exc
    if not isinstance(payload.get("trusted_order_sources"), list):
        raise ValueError("temporal policy must freeze trusted order sources")
    policy["payload"] = payload
    return payload


def build_temporal_event_ledger(canonical_meta_csv: Path, quality_csv: Path, three_state_csv: Path, output_csv: Path) -> dict[str, Any]:
    quality_rows = read_csv_rows(quality_csv)
    quality_by_id: dict[str, dict[str, str]] = {}
    for row in quality_rows:
        annotation = str(row.get("canonical_annotation_id", ""))
        if not annotation or annotation in quality_by_id:
            raise ValueError("quality annotation identity must be non-empty and unique")
        quality_by_id[annotation] = row
    annotation_sha, three_state_sha = sha256_file(canonical_meta_csv), sha256_file(three_state_csv)
    rows = []
    seen: set[tuple[str, str, str]] = set()
    for observation in read_csv_rows(three_state_csv):
        quality = quality_by_id.get(str(observation.get("canonical_annotation_id", "")))
        merged = {**quality, **observation} if quality else {}
        if not merged:
            raise ValueError("three-state observation is missing its quality annotation identity")
        key = _event_evidence_key(merged)
        if key in seen:
            raise ValueError("eligible three-state keys must be unique")
        seen.add(key)
        independence_identity = str(quality.get("independence_audit_identity", "")).strip()
        if not independence_identity:
            raise ValueError("eligible evidence is missing its frozen independence audit identity")
        arrived = str(quality.get("arrived_at") or quality.get("annotation_created_at") or quality.get("created_at") or "")
        normalized = _arrival(arrived).isoformat()
        precision = _timestamp_precision(arrived)
        event_id = "evt-" + hashlib.sha256("|".join(key).encode("utf-8")).hexdigest()[:24]
        rows.append({
            "event_id": event_id,
            "canonical_annotation_id": key[0],
            "worker_id": str(quality.get("worker_id") or quality.get("annotator_id") or ""),
            "task_id": str(quality.get("task_id", "")),
            "base_task_id": str(quality.get("base_task_id", "")),
            "condition": str(quality.get("condition", "")),
            "tag_family": key[1],
            "tag_name": key[2],
            "canonical_arrival_timestamp": normalized,
            "timestamp_precision": precision,
            "arrival_order_source": "canonical_annotation_arrival_timestamp",
            "trusted_sequence": "",
            "independence_audit_identity": independence_identity,
            "source_annotation_path": str(canonical_meta_csv.resolve()),
            "source_annotation_sha256": annotation_sha,
            "source_three_state_path": str(three_state_csv.resolve()),
            "source_three_state_sha256": three_state_sha,
            "manifest_version": LEDGER_VERSION,
        })
    write_csv_rows(output_csv, sorted(rows, key=lambda row: (_arrival(row["canonical_arrival_timestamp"]), row["event_id"])))
    return {"event_ledger_csv": str(output_csv.resolve()), "event_ledger_sha256": sha256_file(output_csv), "n_events": len(rows), "manifest_version": LEDGER_VERSION}


def _scope_vote(evidence: dict[str, Any]) -> str:
    text = str(evidence.get("scope") or "").strip().lower()
    if "oos" in text or "out-of-scope" in text or "out of scope" in text:
        return "-"
    if "in-scope" in text or "in scope" in text or "camera room" in text or "normal" in text:
        return "+"
    return "0"


def _three_state(values: dict[str, str], policy: dict[str, Any], k_min: int) -> dict[str, Any]:
    a = sum(value == "+" for value in values.values())
    e = sum(value == "-" for value in values.values())
    u = sum(value == "0" for value in values.values())
    k = a + e + u
    same = int(policy["meta_min_same_state"])
    opposition = int(policy["meta_max_opposition"])
    max_u = float(policy["max_unasserted_rate"])
    gates = {
        "support": k >= int(k_min),
        "same_state": max(a, e) >= same,
        "opposition": min(a, e) <= opposition,
        "unasserted": k > 0 and u / k <= max_u,
    }
    complete = all(gates.values())
    conflict = a >= same and e >= same
    status = "complete_positive" if complete and a > e else "complete_negative" if complete and e > a else "conflicted" if conflict else "insufficient"
    return {"a": a, "e": e, "u": u, "k": k, "unasserted_rate": u / k if k else 0.0, "replicated_explicit_conflict": conflict, "gates": gates, "status": status, "complete": complete}


def _geometry_state(annotation_ids: set[str], geometry_by_id: dict[str, dict[str, Any]]) -> dict[str, Any]:
    geometries = [geometry_by_id[annotation] for annotation in sorted(annotation_ids) if annotation in geometry_by_id]
    if len(geometries) < 2:
        return {"status": "not_evaluable_insufficient_support", "support": len(geometries), "q_boundary_min": None, "q_wallwall_min": None}
    pairs = [pairwise_similarity(left, right) for index, left in enumerate(geometries) for right in geometries[index + 1 :]]
    valid = [pair for pair in pairs if pair["validity_status"] == "valid"]
    if len(valid) != len(pairs):
        return {"status": "not_evaluable_incompatible_geometry", "support": len(geometries), "q_boundary_min": None, "q_wallwall_min": None}
    return {"status": "evaluable", "support": len(geometries), "q_boundary_min": min(pair["q_boundary"] for pair in valid), "q_wallwall_min": min(pair["q_wallwall"] for pair in valid)}


def _eligible_roster(roster: Any) -> set[str]:
    if isinstance(roster, set):
        return set(roster)
    return {worker for worker, row in (roster or {}).items() if row.get("candidate_eligible") is True}


def _history_at(rows: list[dict[str, Any]], task: tuple[str, str], when: datetime) -> tuple[dict[str, str], list[dict[str, Any]], list[dict[str, Any]]]:
    applicable, future = [], []
    for row in rows:
        if _task_key(row) != task:
            continue
        effective = row.get("_effective_at") or _arrival(row.get("effective_at"))
        (applicable if effective <= when else future).append({**row, "_effective_at": effective})
    latest: dict[str, dict[str, Any]] = {}
    for row in sorted(applicable, key=lambda item: item["_effective_at"]):
        latest[str(row.get("worker_id", ""))] = row
    return {worker: str(row.get("assignment_status", "")).lower() for worker, row in latest.items()}, applicable, future


def _new_state() -> dict[str, Any]:
    return {"task_state": "OPEN", "workers": set(), "annotations_by_worker": {}, "arrival_by_worker": {}, "tags": defaultdict(dict), "scope": {}, "correction": {}, "terminal_batch_id": "", "terminal_snapshot_id": ""}


def _clone_state(state: dict[str, Any]) -> dict[str, Any]:
    return {
        "task_state": state["task_state"],
        "workers": set(state["workers"]),
        "annotations_by_worker": dict(state["annotations_by_worker"]),
        "arrival_by_worker": dict(state["arrival_by_worker"]),
        "tags": defaultdict(dict, {key: dict(value) for key, value in state["tags"].items()}),
        "scope": dict(state["scope"]),
        "correction": dict(state["correction"]),
        "terminal_batch_id": state["terminal_batch_id"],
        "terminal_snapshot_id": state["terminal_snapshot_id"],
    }


def _snapshot(state: dict[str, Any], task: tuple[str, str]) -> str:
    payload = {
        "task": task,
        "task_state": state["task_state"],
        "workers": sorted(state["workers"]),
        "annotations_by_worker": dict(sorted(state["annotations_by_worker"].items())),
        "arrival_by_worker": {worker: value.isoformat() for worker, value in sorted(state["arrival_by_worker"].items())},
        "tags": {"/".join(key): dict(sorted(values.items())) for key, values in sorted(state["tags"].items())},
        "scope": dict(sorted(state["scope"].items())),
        "correction": dict(sorted(state["correction"].items())),
    }
    return sha256_json(payload)


def _purpose_policy(purpose: dict[str, Any], kind: str, fallback: dict[str, Any]) -> dict[str, Any]:
    return dict((purpose.get("policies") or {}).get(kind) or fallback)


def _risk_config(purpose: dict[str, Any], fallback: dict[str, Any]) -> dict[str, Any]:
    policy = _purpose_policy(purpose, "risk", fallback)
    risk = str(policy.get("risk_bucket") or purpose.get("risk_bucket") or fallback.get("risk_bucket") or "")
    fields = ("k_dispatch_initial", "k_min_for_stop", "standard_cap", "escalation_cap")
    try:
        values = {field: int(policy[field]) for field in fields}
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError("risk policy is missing k/cap thresholds") from exc
    if risk not in RISK_BUCKETS or not 1 <= values["k_dispatch_initial"] <= values["k_min_for_stop"] <= values["standard_cap"] <= values["escalation_cap"]:
        raise ValueError("risk_bucket or k/cap order is invalid")
    return {**policy, **values, "risk_bucket": risk}


def _correction_complete(evidence: dict[str, Any], annotation: str, geometry_by_id: dict[str, dict[str, Any]], policy: dict[str, Any]) -> bool:
    original = str(evidence.get("original_provenance_status") or evidence.get("provenance_status") or "")
    effective = str(evidence.get("effective_provenance_status") or original)
    original_ok = original == "complete" or (not evidence.get("original_provenance_status") and effective in {"complete", "valid"})
    amendment_ok = (
        str(evidence.get("retrospective_amendment_status", "")) == "joined_exact_identity"
        and effective == "complete_retrospective_amendment"
    )
    initial_ok = original_ok or amendment_ok
    final_ok = annotation in geometry_by_id and str(evidence.get("geometry_valid", "")).lower() == "true"
    edit_ok = str(evidence.get("semi_geometry_correction_evaluable", "")).lower() == "true" and str(evidence.get("semi_evidence_status", "")).lower() in {"complete", "valid", "evaluable"}
    outcome = str(evidence.get("semi_correction_failure_observed", "")).lower()
    reference_ok = bool(str(evidence.get("semi_response_type", "")).strip()) and outcome in {"true", "false"} and bool(str(evidence.get("geometry_reference_status", "")).strip())
    checks = {
        "require_initialization_provenance": initial_ok,
        "require_final_geometry": final_ok,
        "require_edit_metrics": edit_ok,
        "require_reference_outcome": reference_ok,
    }
    return all(not _strict_bool(policy[field]) or checks[field] for field in checks)


def _apply_annotation(state: dict[str, Any], annotation: str, worker: str, rows: list[tuple[dict[str, Any], dict[str, Any]]], geometry_by_id: dict[str, dict[str, Any]], correction_policy: dict[str, Any], arrived_at: datetime | None = None) -> None:
    state["workers"].add(worker)
    state["annotations_by_worker"][worker] = annotation
    if arrived_at is not None:
        state["arrival_by_worker"][worker] = arrived_at
    first_evidence = rows[0][1]
    state["scope"][worker] = _scope_vote(first_evidence)
    state["correction"][worker] = _correction_complete(first_evidence, annotation, geometry_by_id, correction_policy)
    for event, evidence in rows:
        assertion = str(evidence.get("assertion", ""))
        if evidence.get("_tag_state_eligible", True) and assertion in {"+", "-", "0"}:
            state["tags"][(str(event["tag_family"]), str(event["tag_name"]))][worker] = assertion


def _evaluate_state(state: dict[str, Any], purpose: dict[str, Any], fallback_policy: dict[str, Any], geometry_by_id: dict[str, dict[str, Any]]) -> dict[str, Any]:
    risk = _risk_config(purpose, fallback_policy)
    scope_policy = _purpose_policy(purpose, "scope", fallback_policy)
    tag_policy = _purpose_policy(purpose, "tag", fallback_policy)
    geometry_policy = _purpose_policy(purpose, "geometry", fallback_policy)
    correction_policy = _purpose_policy(purpose, "correction", fallback_policy)
    scope = _three_state(state["scope"], scope_policy, risk["k_min_for_stop"])
    required_tags = set(purpose.get("required_tags") or set())
    all_tags = set(state["tags"]) | required_tags
    tag_states = {tag: _three_state(state["tags"].get(tag, {}), tag_policy, risk["k_min_for_stop"]) for tag in sorted(all_tags)}
    annotation_ids = set(state["annotations_by_worker"].values())
    geometry = _geometry_state(annotation_ids, geometry_by_id)
    geometry_payload_valid = bool(annotation_ids) and all(annotation in geometry_by_id for annotation in annotation_ids)
    geometry_threshold_passed = (
        geometry["status"] == "evaluable"
        and geometry["support"] >= int(geometry_policy["min_geometry_support"])
        and float(geometry["q_boundary_min"]) >= float(geometry_policy["min_q_boundary"])
        and float(geometry["q_wallwall_min"]) >= float(geometry_policy["min_q_wallwall"])
    )
    scope_oos = scope["complete"] and scope["status"] == "complete_negative"
    components = set(purpose.get("required_components") or set())
    geometry_required = "geometry" in components and not scope_oos
    geometry_profile_eligible = (
        geometry_required
        and scope["status"] == "complete_positive"
        and geometry_payload_valid
        and geometry["status"] == "evaluable"
        and geometry_threshold_passed
        and len(state["workers"]) == len(state["annotations_by_worker"])
    )
    difficulty_tags = [tag for tag in required_tags if tag[0] == "difficulty"]
    model_tags = [tag for tag in required_tags if tag[0] == "model_issue"]
    checks = {
        "scope": scope["complete"],
        "difficulty": bool(difficulty_tags) and all(tag_states[tag]["complete"] for tag in difficulty_tags),
        "model_issue_recognition": bool(model_tags) and all(tag_states[tag]["complete"] for tag in model_tags),
        "model_issue_correction": sum(state["correction"].values()) >= int(correction_policy["min_complete_workers"]),
        "geometry": not geometry_required or geometry_threshold_passed,
        "scene": geometry_profile_eligible and geometry["support"] >= int(geometry_policy["min_geometry_support"]),
    }
    complete = len(state["workers"]) >= risk["k_min_for_stop"] and all(checks[component] for component in components)
    return {
        "risk": risk,
        "scope": scope,
        "tag_states": tag_states,
        "geometry": geometry,
        "geometry_required": geometry_required,
        "geometry_payload_valid": geometry_payload_valid,
        "geometry_threshold_passed": geometry_threshold_passed,
        "geometry_profile_eligible": geometry_profile_eligible,
        "component_checks": checks,
        "complete": complete,
    }


def _derive_task_action(
    state: dict[str, Any], evaluation: dict[str, Any], pool: set[str], pending: set[str], risk: dict[str, Any], *, terminal_before: bool = False
) -> tuple[str, str, str]:
    if terminal_before:
        return state["task_state"], "post_terminal_audit_only", "task_already_terminal"
    if evaluation["complete"]:
        return "COMPLETE", "stop_candidate", "required_evidence_components_complete"
    k = len(state["workers"])
    if k >= int(risk["escalation_cap"]) or (not pool and not pending):
        return "UNRESOLVED", "unresolved_candidate", "required_components_missing_at_cap_or_candidate_exhausted"
    if pending and not pool:
        return "OPEN", "await_pending_assignments_candidate", "assigned_workers_pending"
    if k < int(risk["k_dispatch_initial"]):
        return "OPEN", "continue_initial", "minimum_support_not_met"
    if k < int(risk["k_min_for_stop"]):
        return "OPEN", "continue_to_stop_support_candidate", "stop_support_not_yet_reached"
    if k < int(risk["standard_cap"]):
        return "OPEN", "continue_standard_candidate", "required_components_incomplete_before_standard_cap"
    return "OPEN", "escalate_candidate", "required_components_incomplete_at_or_after_standard_cap"


def _contract(checked: int, failures: Counter[str], artifact: str) -> dict[str, Any]:
    failures = Counter({reason: count for reason, count in failures.items() if count > 0})
    return {
        "valid": checked > 0 and not failures,
        "checked_count": checked,
        "failure_count": sum(failures.values()),
        "failure_reasons": dict(sorted(failures.items())),
        "evidence_artifact": artifact,
    }


def replay_temporal_batches(
    events: list[dict[str, Any]], *, policy_by_fold: dict[int, dict[str, Any]], evidence_by_id: dict[tuple[str, str, str], dict[str, Any]],
    geometry_by_id: dict[str, dict[str, Any]], task_purposes: dict[tuple[str, str], dict[str, Any]], candidate_roster: dict[tuple[str, str], Any],
    assignment_rows: list[dict[str, Any]], source_artifact: str, source_sha256: str, dependency_paths: list[Path], input_status: str,
    candidate_pool_source_sha256: str = "", validate_frozen_sources: bool = False,
    contract_evidence_artifacts: dict[str, str] | None = None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]], dict[str, dict[str, Any]]]:
    folded = build_crossfit_folds(events)
    required_folds = {int(row["crossfit_fold"]) for row in folded}
    if set(policy_by_fold) != required_folds:
        raise ValueError("policy manifest folds must exactly match evaluation folds")
    fold_payloads = {fold: _validate_policy(policy_by_fold[fold], fold, 2) for fold in required_folds}

    checked = Counter()
    failures = {field: Counter() for field in CONTRACT_FIELDS}
    event_ids = [str(row.get("event_id", "")) for row in folded]
    event_keys = [_event_evidence_key(row) for row in folded]
    event_key_counts = Counter(event_keys)
    checked["event_key_uniqueness_valid"] = len(folded)
    failures["event_key_uniqueness_valid"].update({"missing_event_identity": sum(not event_id or not all(key) for event_id, key in zip(event_ids, event_keys))})
    failures["event_key_uniqueness_valid"].update({"duplicate_event_id": len(event_ids) - len(set(event_ids)), "duplicate_annotation_tag_key": len(event_keys) - len(set(event_keys))})
    failures["event_key_uniqueness_valid"] += Counter()
    failures["event_key_uniqueness_valid"] = Counter({key: value for key, value in failures["event_key_uniqueness_valid"].items() if value})
    checked["event_coverage_complete"] = max(len(event_keys), len(evidence_by_id))
    event_key_set, evidence_key_set = set(event_keys), set(evidence_by_id)
    failures["event_coverage_complete"]["missing_ledger_event"] = len(evidence_key_set - event_key_set)
    failures["event_coverage_complete"]["extra_ledger_event"] = len(event_key_set - evidence_key_set)
    failures["event_coverage_complete"]["coverage_multiplicity_mismatch"] = abs(len(event_keys) - len(evidence_by_id))
    failures["event_coverage_complete"] = Counter({key: value for key, value in failures["event_coverage_complete"].items() if value})

    parsed: dict[str, datetime] = {}
    identities: dict[str, set[tuple[str, ...]]] = defaultdict(set)
    event_failures: dict[str, list[str]] = defaultdict(list)
    for row in folded:
        event_id = str(row.get("event_id", ""))
        try:
            parsed[event_id] = _event_time(row)
        except ValueError:
            parsed[event_id] = datetime.min.replace(tzinfo=timezone.utc)
            failures["arrival_order_contract_valid"]["invalid_canonical_arrival_timestamp"] += 1
            event_failures[event_id].append("invalid_canonical_arrival_timestamp")
        checked["arrival_order_contract_valid"] += 1
        precision, source = str(row.get("timestamp_precision", "")), str(row.get("arrival_order_source", ""))
        if precision not in {"second", "millisecond", "microsecond"} or not source:
            failures["arrival_order_contract_valid"]["missing_or_invalid_arrival_metadata"] += 1
            event_failures[event_id].append("missing_or_invalid_arrival_metadata")
        try:
            if precision != _timestamp_precision(row.get("canonical_arrival_timestamp") or row.get("arrived_at")):
                failures["arrival_order_contract_valid"]["timestamp_precision_mismatch"] += 1
                event_failures[event_id].append("timestamp_precision_mismatch")
        except ValueError:
            failures["arrival_order_contract_valid"]["timestamp_precision_not_verifiable"] += 1
            event_failures[event_id].append("timestamp_precision_not_verifiable")
        if validate_frozen_sources and str(row.get("manifest_version", "")) != LEDGER_VERSION:
            failures["arrival_order_contract_valid"]["event_ledger_version_mismatch"] += 1
            event_failures[event_id].append("event_ledger_version_mismatch")
        if validate_frozen_sources:
            for path_field, sha_field in (("source_annotation_path", "source_annotation_sha256"), ("source_three_state_path", "source_three_state_sha256")):
                path = canonical_path(row.get(path_field, ""))
                if not _sha_matches(path, row.get(sha_field)):
                    failures["arrival_order_contract_valid"][f"{sha_field}_mismatch"] += 1
                    event_failures[event_id].append(f"{sha_field}_mismatch")
        evidence = evidence_by_id.get(_event_evidence_key(row), {})
        if validate_frozen_sources:
            ledger_identity = str(row.get("independence_audit_identity", "")).strip()
            evidence_identity = str(evidence.get("independence_audit_identity", "")).strip()
            if not ledger_identity or not evidence_identity or ledger_identity != evidence_identity:
                failures["annotation_tag_atomicity_valid"]["missing_or_mismatched_independence_identity"] += 1
                event_failures[event_id].append("missing_or_mismatched_independence_identity")
        identities[str(row.get("canonical_annotation_id", ""))].add((
            str(row.get("worker_id", "")), *_task_key(row), parsed[event_id].isoformat(), precision, source,
            str(row.get("trusted_sequence", "")), str(row.get("independence_audit_identity", "")),
        ))
    checked["annotation_tag_atomicity_valid"] = len(identities)
    bad_annotations = {annotation for annotation, variants in identities.items() if len(variants) != 1}
    failures["annotation_tag_atomicity_valid"]["annotation_identity_or_sequence_mismatch"] = len(bad_annotations)
    failures["annotation_tag_atomicity_valid"] = Counter({key: value for key, value in failures["annotation_tag_atomicity_valid"].items() if value})

    batches: dict[tuple[str, str, datetime, str], list[dict[str, Any]]] = defaultdict(list)
    for row in folded:
        event_id = str(row.get("event_id", ""))
        payload = fold_payloads[int(row["crossfit_fold"])]
        trusted_sources = set(payload.get("trusted_order_sources") or [])
        source, sequence = str(row.get("arrival_order_source", "")), str(row.get("trusted_sequence", ""))
        trusted_sequence = sequence if source in trusted_sources else ""
        if source in trusted_sources and not sequence.isdigit():
            failures["arrival_order_contract_valid"]["trusted_source_sequence_not_numeric"] += 1
            event_failures[event_id].append("trusted_source_sequence_not_numeric")
        batches[(*_task_key(row), parsed[event_id], trusted_sequence)].append(row)
    annotation_batches: dict[str, set[tuple[str, str, datetime, str]]] = defaultdict(set)
    for batch_key, rows in batches.items():
        for row in rows:
            annotation_batches[str(row.get("canonical_annotation_id", ""))].add(batch_key)
    split_annotations = {annotation for annotation, keys in annotation_batches.items() if len(keys) != 1}
    failures["batch_atomicity_valid"]["annotation_split_across_batches"] = len(split_annotations)

    states: dict[tuple[str, str], dict[str, Any]] = defaultdict(_new_state)
    event_rows: list[dict[str, Any]] = []
    batch_rows: list[dict[str, Any]] = []
    sensitivity_rows: list[dict[str, Any]] = []
    terminal_rows: dict[tuple[str, str], dict[str, Any]] = {}
    common = lambda row: sidecar_common(
        source_artifact=source_artifact, source_sha256=source_sha256, stage="C1", pool=str(row.get("dataset_group", "")),
        condition=str(row.get("condition", "")), validity_status="candidate_only" if input_status == "formal" else "dry_run",
        rule_version=RULE_VERSION, interpretation_allowed=False, dependency_paths=dependency_paths or [source_artifact],
    )

    def batch_sort_key(key: tuple[str, str, datetime, str]) -> tuple[Any, ...]:
        sequence = key[3]
        order = (0, int(sequence)) if sequence.isdigit() else (1, sequence)
        return key[2], key[0], key[1], order

    for batch_index, batch_key in enumerate(sorted(batches, key=batch_sort_key), start=1):
        rows = batches[batch_key]
        task = batch_key[:2]
        state = states[task]
        purpose = task_purposes.get(task)
        checked["task_purpose_manifest_valid"] += 1
        if purpose is None:
            failures["task_purpose_manifest_valid"]["missing_task_purpose"] += 1
            purpose = {"task_id": rows[0].get("task_id", ""), "task_purpose": "invalid", "required_components": set(), "required_tags": set()}
        if task not in candidate_roster:
            failures["candidate_pool_binding_valid"]["missing_task_candidate_roster"] += 1
        roster = _eligible_roster(candidate_roster.get(task, set()))
        policy = policy_by_fold[int(rows[0]["crossfit_fold"])]
        fallback = policy["payload"]
        try:
            risk = _risk_config(purpose, fallback)
            checked["risk_bucket_valid"] += 1
        except ValueError:
            failures["risk_bucket_valid"]["invalid_risk_policy"] += 1
            raise
        pre_snapshot = _snapshot(state, task)
        pre_k = len(state["workers"])
        state_before = state["task_state"]
        terminal_before = state["task_state"] in TERMINAL_STATES
        statuses, applied_history, future_history = _history_at(assignment_rows, task, batch_key[2])
        checked["no_future_scope_leakage"] += max(1, len(state["arrival_by_worker"]) + len(applied_history))
        if any(arrived > batch_key[2] for arrived in state["arrival_by_worker"].values()):
            failures["no_future_scope_leakage"]["future_annotation_present_in_pre_batch_state"] += 1
        if any(row["_effective_at"] > batch_key[2] for row in applied_history):
            failures["no_future_scope_leakage"]["future_assignment_row_applied"] += 1
        excluded = {worker for worker, status in statuses.items() if status in {"assigned", "completed", "excluded", "withdrawn", "ineligible"}}
        pending_assigned = {worker for worker, status in statuses.items() if status == "assigned"} - state["workers"]
        pool_before = roster - state["workers"] - excluded
        event_batch_id = hashlib.sha256("|".join(map(str, batch_key)).encode("utf-8")).hexdigest()[:20]
        legal: list[tuple[dict[str, Any], dict[str, Any]]] = []
        batch_event_rows: list[dict[str, Any]] = []
        required_model_tags = {tag for tag in purpose.get("required_tags", set()) if tag[0] == "model_issue"}
        for row in rows:
            event_id, key = str(row.get("event_id", "")), _event_evidence_key(row)
            evidence = evidence_by_id.get(key, {})
            worker = str(row.get("worker_id", ""))
            reasons = list(event_failures[event_id])
            forensic_reasons: list[str] = []
            if event_key_counts[key] != 1:
                reasons.append("duplicate_annotation_tag_key")
            if key not in evidence_by_id:
                reasons.append("missing_three_state_evidence")
            evidence_eligible = bool(evidence) and eligible_independent_evidence(evidence)
            assertion = str(evidence.get("assertion", ""))
            if evidence and not evidence_eligible:
                forensic_reasons.append("ineligible_independent_evidence")
            if evidence and assertion not in {"+", "-", "0", "NA"}:
                reasons.append("invalid_three_state_assertion")
            if evidence and worker != str(evidence.get("worker_id") or evidence.get("annotator_id") or ""):
                reasons.append("worker_identity_mismatch")
            if evidence and (_task_key(evidence) != task or str(evidence.get("tag_family")) != key[1] or str(evidence.get("tag_name")) != key[2]):
                reasons.append("task_or_tag_identity_mismatch")
            if evidence:
                try:
                    if _event_time(evidence) != parsed[event_id]:
                        reasons.append("arrival_timestamp_mismatch")
                except ValueError:
                    reasons.append("arrival_timestamp_mismatch")
            if str(row.get("canonical_annotation_id", "")) in bad_annotations | split_annotations:
                reasons.append("annotation_atomicity_violation")
            if evidence_eligible and worker not in roster:
                reasons.append("worker_not_in_frozen_candidate_roster")
            tag_state_eligible = evidence_eligible and assertion in {"+", "-", "0"}
            if (key[1], key[2]) in required_model_tags:
                source = str(evidence.get("assertion_source", ""))
                provenance_valid = task[1] == "semi" and (source == "explicit_worker_label" or (source == "legacy_behavior_inferred" and str(evidence.get("harmonization_validity_status")) == "valid_behavior_inferred"))
                if not provenance_valid:
                    forensic_reasons.append("model_issue_provenance_invalid")
                    tag_state_eligible = False
            if evidence_eligible and assertion == "NA":
                forensic_reasons.append("not_evaluable_tag_assertion")
            claim = str(row.get("candidate_available_before_event", "")).strip()
            if evidence_eligible and claim:
                try:
                    if _strict_bool(claim) != bool(pool_before):
                        failures["candidate_pool_binding_valid"]["candidate_availability_claim_mismatch"] += 1
                except ValueError:
                    failures["candidate_pool_binding_valid"]["candidate_availability_claim_invalid"] += 1
            if evidence_eligible:
                checked["candidate_pool_binding_valid"] += 1
                if worker not in roster:
                    failures["candidate_pool_binding_valid"]["event_worker_not_in_roster"] += 1
            if not reasons and evidence_eligible:
                legal.append((row, {**evidence, "_tag_state_eligible": tag_state_eligible}))
            if terminal_before:
                forensic_reasons.append("post_terminal_audit_only")
            audit = {
                **common(row), "event_id": event_id, "event_batch_id": event_batch_id, "canonical_annotation_id": row.get("canonical_annotation_id", ""),
                "worker_id": worker, "task_id": row.get("task_id", ""), "base_task_id": task[0], "condition": task[1], "tag_family": key[1], "tag_name": key[2],
                "assertion": evidence.get("assertion", ""), "canonical_arrival_timestamp": parsed[event_id].isoformat(), "timestamp_precision": row.get("timestamp_precision", ""),
                "arrival_order_source": row.get("arrival_order_source", ""), "trusted_sequence": row.get("trusted_sequence", ""), "event_validity_status": "valid" if not reasons else "invalid",
                "event_invalid_reason": ";".join(sorted(set(reasons))), "pre_batch_snapshot_id": pre_snapshot, "post_batch_snapshot_id": "", "post_terminal_audit_only": terminal_before,
                "primary_annotation_included": False, "primary_evidence_included": False, "tag_state_included": False,
                "forensic_only_reason": ";".join(sorted(set(forensic_reasons))), "candidate_available_derived": bool(pool_before),
                "candidate_pool_before_json": json.dumps(sorted(pool_before)), "future_assignment_rows_ignored": len(future_history),
            }
            event_rows.append(audit)
            batch_event_rows.append(audit)

        grouped: dict[tuple[str, str], list[tuple[dict[str, Any], dict[str, Any]]]] = defaultdict(list)
        for event, evidence in legal:
            grouped[(str(event.get("canonical_annotation_id", "")), str(event.get("worker_id", "")))].append((event, evidence))
        worker_annotations: dict[str, set[str]] = defaultdict(set)
        for annotation, worker in grouped:
            worker_annotations[worker].add(annotation)
        primary_groups: list[tuple[str, str, list[tuple[dict[str, Any], dict[str, Any]]]]] = []
        for (annotation, worker), items in grouped.items():
            if terminal_before:
                continue
            if worker in state["workers"]:
                for audit in batch_event_rows:
                    if audit["canonical_annotation_id"] == annotation:
                        audit["forensic_only_reason"] = "duplicate_worker_task_submission"
                continue
            if len(worker_annotations[worker]) > 1:
                failures["candidate_pool_binding_valid"]["duplicate_worker_task_in_atomic_batch"] += 1
                for audit in batch_event_rows:
                    if audit["worker_id"] == worker:
                        audit["forensic_only_reason"] = "duplicate_worker_task_submission"
                continue
            primary_groups.append((annotation, worker, items))
            tag_event_ids = {str(event.get("event_id", "")) for event, evidence in items if evidence.get("_tag_state_eligible")}
            for audit in batch_event_rows:
                if audit["canonical_annotation_id"] == annotation and audit["event_validity_status"] == "valid":
                    audit["primary_annotation_included"] = True
                    audit["tag_state_included"] = audit["event_id"] in tag_event_ids
                    audit["primary_evidence_included"] = audit["tag_state_included"]

        correction_policy = _purpose_policy(purpose, "correction", {"min_complete_workers": 1, "require_initialization_provenance": "true", "require_final_geometry": "true", "require_edit_metrics": "true", "require_reference_outcome": "true"})
        for annotation, worker, items in primary_groups:
            _apply_annotation(state, annotation, worker, items, geometry_by_id, correction_policy, batch_key[2])
        try:
            evaluation = _evaluate_state(state, purpose, fallback, geometry_by_id)
            checked["family_gate_contract_valid"] += max(1, len(purpose.get("required_components", set())))
        except (KeyError, TypeError, ValueError):
            failures["family_gate_contract_valid"]["family_policy_evaluation_failed"] += 1
            evaluation = {
                "risk": risk, "scope": {"status": "insufficient"}, "tag_states": {}, "geometry": _geometry_state(set(), geometry_by_id),
                "geometry_required": False, "geometry_payload_valid": False, "geometry_threshold_passed": False, "geometry_profile_eligible": False,
                "component_checks": {}, "complete": False,
            }
        post_k = len(state["workers"])
        statuses_after, _, _ = _history_at(assignment_rows, task, batch_key[2])
        excluded_after = {worker for worker, status in statuses_after.items() if status in {"assigned", "completed", "excluded", "withdrawn", "ineligible"}}
        pending_after = {worker for worker, status in statuses_after.items() if status == "assigned"} - state["workers"]
        pool_after = roster - state["workers"] - excluded_after
        state["task_state"], action, reason = _derive_task_action(
            state, evaluation, pool_after, pending_after, risk, terminal_before=terminal_before
        )
        post_snapshot = _snapshot(state, task)
        if not terminal_before and state["task_state"] in TERMINAL_STATES:
            state["terminal_batch_id"] = event_batch_id
            state["terminal_snapshot_id"] = post_snapshot
        for audit in batch_event_rows:
            audit["post_batch_snapshot_id"] = post_snapshot
        tag_json = {"/".join(tag): value for tag, value in evaluation["tag_states"].items()}
        scope_label = {"complete_positive": "resolved_in_scope", "complete_negative": "resolved_oos"}.get(evaluation["scope"].get("status"), evaluation["scope"].get("status", "insufficient"))
        batch = {
            **common(rows[0]), "event_batch_id": event_batch_id, "replay_task_key": "|".join(task), "task_id": purpose.get("task_id", rows[0].get("task_id", "")),
            "base_task_id": task[0], "condition": task[1], "batch_timestamp": batch_key[2].isoformat(), "trusted_sequence": batch_key[3],
            "batch_size_annotations": len({str(row.get("canonical_annotation_id", "")) for row in rows}), "batch_size_tag_events": len(rows),
            "pre_batch_snapshot_id": pre_snapshot, "decision_snapshot_id": post_snapshot, "pre_batch_k": pre_k, "post_batch_k": post_k,
            "primary_k_used": post_k,
            "standard_cap_overshoot_due_to_tie": max(0, post_k - int(risk["standard_cap"])),
            "escalation_cap_overshoot_due_to_tie": max(0, post_k - int(risk["escalation_cap"])),
            # Compatibility alias: historical consumers interpreted this as escalation-cap overshoot.
            "cap_overshoot_due_to_tie": max(0, post_k - int(risk["escalation_cap"])),
            "k_dispatch_initial": risk["k_dispatch_initial"], "k_min_for_stop": risk["k_min_for_stop"],
            "standard_cap": risk["standard_cap"], "escalation_cap": risk["escalation_cap"],
            "task_state_before": state_before, "task_state_after": state["task_state"],
            "current_scope_state_after": scope_label, "family_evidence_status_json": json.dumps(tag_json, sort_keys=True),
            "geometry_status": evaluation["geometry"]["status"], "geometry_support": evaluation["geometry"]["support"],
            "q_boundary_min": evaluation["geometry"].get("q_boundary_min"), "q_wallwall_min": evaluation["geometry"].get("q_wallwall_min"),
            "geometry_payload_present": evaluation["geometry"]["support"] > 0, "geometry_payload_valid": evaluation["geometry_payload_valid"],
            "geometry_consensus_required": evaluation["geometry_required"], "geometry_threshold_passed": evaluation["geometry_threshold_passed"],
            "geometry_profile_eligible": evaluation["geometry_profile_eligible"], "task_purpose": purpose.get("task_purpose", ""),
            "required_evidence_components": json.dumps(sorted(purpose.get("required_components", set()))),
            "required_tags_json": json.dumps(sorted("/".join(tag) for tag in purpose.get("required_tags", set()))),
            "component_gate_status_json": json.dumps(evaluation["component_checks"], sort_keys=True),
            "task_completion_status": state["task_state"].lower(), "candidate_pool_before": json.dumps(sorted(pool_before)),
            "candidate_pool_after": json.dumps(sorted(pool_after)), "pending_assigned_workers_after": json.dumps(sorted(pending_after)),
            "next_candidate_available": bool(pool_after), "candidate_pool_source_sha256": candidate_pool_source_sha256,
            "action": action, "action_reason": reason, "terminal_batch_id": state["terminal_batch_id"],
        }
        batch_rows.append(batch)
        checked["batch_atomicity_valid"] += 1
        if len({audit["pre_batch_snapshot_id"] for audit in batch_event_rows}) != 1 or len({audit["post_batch_snapshot_id"] for audit in batch_event_rows}) != 1:
            failures["batch_atomicity_valid"]["batch_snapshot_not_atomic"] += 1
        checked["task_completion_contract_valid"] += 1
        if terminal_before:
            state_action_inconsistent = action != "post_terminal_audit_only"
        elif state["task_state"] == "COMPLETE":
            state_action_inconsistent = action != "stop_candidate"
        elif state["task_state"] == "UNRESOLVED":
            state_action_inconsistent = action != "unresolved_candidate"
        else:
            state_action_inconsistent = action in {"stop_candidate", "unresolved_candidate", "post_terminal_audit_only"}
        if state_action_inconsistent:
            failures["task_completion_contract_valid"]["state_action_inconsistent"] += 1
        if state["task_state"] in TERMINAL_STATES and task not in terminal_rows:
            terminal_rows[task] = batch

        if terminal_before:
            sensitivity_rows.append({
                **common(rows[0]), "event_batch_id": event_batch_id, "replay_task_key": "|".join(task), "tie_policy": "simultaneous_atomic_primary",
                "primary_k_used": post_k, "sensitivity_k_used_min": post_k, "sensitivity_k_used_max": post_k,
                "primary_final_action": action, "alternative_final_actions": json.dumps([action]),
                "stop_order_sensitivity": False, "sensitivity_not_applicable_post_terminal": True,
                "random_seed": SENSITIVITY_SEED, "random_permutations": 0,
            })
            continue

        annotations = sorted({annotation for annotation, _, _ in primary_groups})
        rng = random.Random(SENSITIVITY_SEED + batch_index)
        orders = [annotations, list(reversed(annotations))] + [rng.sample(annotations, len(annotations)) for _ in range(SENSITIVITY_PERMUTATIONS)] if annotations else [[]]
        by_annotation = {annotation: (worker, items) for annotation, worker, items in primary_groups}
        sensitivity_k, sensitivity_actions = [], set()
        pre_state = _clone_state(state)
        for annotation, worker, _ in reversed(primary_groups):
            pre_state["workers"].discard(worker)
            pre_state["annotations_by_worker"].pop(worker, None)
            pre_state["arrival_by_worker"].pop(worker, None)
            pre_state["scope"].pop(worker, None)
            pre_state["correction"].pop(worker, None)
            for values in pre_state["tags"].values():
                values.pop(worker, None)
        for order in orders:
            simulated = _clone_state(pre_state)
            simulated_action = ""
            for annotation in order:
                worker, items = by_annotation[annotation]
                _apply_annotation(simulated, annotation, worker, items, geometry_by_id, correction_policy, batch_key[2])
                result = _evaluate_state(simulated, purpose, fallback, geometry_by_id)
                simulated_pending = {worker for worker, status in statuses_after.items() if status == "assigned"} - simulated["workers"]
                simulated_pool = roster - simulated["workers"] - excluded_after
                simulated["task_state"], simulated_action, _ = _derive_task_action(
                    simulated, result, simulated_pool, simulated_pending, risk
                )
                if simulated["task_state"] in TERMINAL_STATES:
                    break
            if not simulated_action:
                result = _evaluate_state(simulated, purpose, fallback, geometry_by_id)
                simulated_pending = {worker for worker, status in statuses_after.items() if status == "assigned"} - simulated["workers"]
                simulated_pool = roster - simulated["workers"] - excluded_after
                simulated["task_state"], simulated_action, _ = _derive_task_action(
                    simulated, result, simulated_pool, simulated_pending, risk
                )
            sensitivity_k.append(len(simulated["workers"]))
            sensitivity_actions.add(simulated_action)
        sensitivity_rows.append({
            **common(rows[0]), "event_batch_id": event_batch_id, "replay_task_key": "|".join(task), "tie_policy": "simultaneous_atomic_primary",
            "primary_k_used": post_k, "sensitivity_k_used_min": min(sensitivity_k), "sensitivity_k_used_max": max(sensitivity_k),
            "primary_final_action": action, "alternative_final_actions": json.dumps(sorted(sensitivity_actions)),
            "stop_order_sensitivity": min(sensitivity_k) != max(sensitivity_k) or sensitivity_actions != {action},
            "sensitivity_not_applicable_post_terminal": False,
            "random_seed": SENSITIVITY_SEED, "random_permutations": SENSITIVITY_PERMUTATIONS,
        })

    task_rows = []
    for task, state in sorted(states.items()):
        decisions = [row for row in batch_rows if row["replay_task_key"] == "|".join(task)]
        selected = terminal_rows.get(task) or decisions[-1]
        if state["task_state"] == "OPEN":
            failures["task_completion_contract_valid"]["task_left_open_after_ledger"] += 1
        task_rows.append({
            **{key: selected.get(key, "") for key in COMMON_SIDEcar_FIELDS}, "task_id": selected.get("task_id", ""), "base_task_id": task[0], "condition": task[1],
            "task_state": state["task_state"], "terminal_batch_id": state["terminal_batch_id"], "terminal_snapshot_id": state["terminal_snapshot_id"],
            "first_terminal_batch_timestamp": selected.get("batch_timestamp", "") if state["task_state"] in TERMINAL_STATES else "",
            "primary_k_used": selected["post_batch_k"], "final_scope_state": selected["current_scope_state_after"], "final_geometry_state": selected["geometry_status"],
            "family_final_states_json": selected["family_evidence_status_json"], "task_completion_status": state["task_state"].lower(),
            "final_action": selected["action"], "unresolved_reason": selected["action_reason"] if state["task_state"] == "UNRESOLVED" else "",
            "expert_review_required": state["task_state"] == "UNRESOLVED", "budget_used": selected["post_batch_k"], "decision_snapshot_id": selected["decision_snapshot_id"],
        })

    contract_evidence_artifacts = contract_evidence_artifacts or {}
    contracts = {field: _contract(checked[field], failures[field], contract_evidence_artifacts.get(field, str(source_artifact))) for field in CONTRACT_FIELDS}
    return event_rows, batch_rows, task_rows, sensitivity_rows, contracts


def replay_temporal_events(events: Iterable[dict[str, Any]], **kwargs: Any) -> list[dict[str, Any]]:
    """Deprecated compatibility wrapper; all replay semantics live in replay_temporal_batches()."""
    return replay_temporal_batches(list(events), **kwargs)[0]


def _empty_outputs(output_csv: Path, status: str, reason: str) -> dict[str, Any]:
    paths = {
        "event_audit": output_csv.parent / "routing_temporal_event_audit_C1.csv",
        "legacy_event_audit": output_csv,
        "batch": output_csv.parent / "routing_temporal_batch_decisions_C1.csv",
        "task": output_csv.parent / "routing_temporal_task_summary_C1.csv",
        "sensitivity": output_csv.parent / "routing_temporal_order_sensitivity_C1.csv",
        "contract": output_csv.parent / "routing_temporal_contract_summary_C1.json",
    }
    for name, path in paths.items():
        if name != "contract":
            write_csv_rows(path, [], COMMON_SIDEcar_FIELDS)
    contracts = {field: _contract(0, Counter({reason: 1}), "") for field in CONTRACT_FIELDS}
    summary = {
        "status": status,
        "contract_results": contracts,
        **{field: False for field in CONTRACT_FIELDS},
        "full_stop_contract_valid": False,
        "n_events": 0,
        "n_primary_annotations": 0,
        "n_tag_state_events": 0,
        "n_nonzero_assertions": 0,
        "formal_assignment_generated": False,
    }
    paths["contract"].write_text(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
    return summary


def materialize_temporal_replay(
    event_csv: Path | None, output_csv: Path, *, policy_manifest: Path | None = None, policy_by_fold: dict[int, dict[str, Any]] | None = None,
    canonical_csv: Path | None = None, quality_csv: Path | None = None, three_state_csv: Path | None = None, canonical_geometry_jsonl: Path | None = None,
    task_purpose_manifest_csv: Path | None = None, candidate_roster_manifest_csv: Path | None = None, assignment_history_csv: Path | None = None,
    input_status: str = "dry_run",
) -> dict[str, Any]:
    if input_status != "formal":
        return _empty_outputs(output_csv, "not_evaluable_missing_formal_c1", "input_status_not_formal")
    required_paths = (event_csv, policy_manifest, canonical_csv, quality_csv, three_state_csv, task_purpose_manifest_csv, candidate_roster_manifest_csv, assignment_history_csv)
    if not all(path and path.exists() for path in required_paths):
        return _empty_outputs(output_csv, "not_evaluable_missing_frozen_dependency", "missing_frozen_temporal_dependency")
    try:
        policies = _load_policy_manifest(policy_manifest) if policy_manifest else policy_by_fold or {}
        events = read_csv_rows(event_csv)
        quality_rows = read_csv_rows(quality_csv)
        quality_by_id: dict[str, dict[str, str]] = {}
        for row in quality_rows:
            annotation = str(row.get("canonical_annotation_id", ""))
            if not annotation or annotation in quality_by_id:
                raise ValueError("quality annotation identity must be unique")
            quality_by_id[annotation] = row
        evidence_by_id: dict[tuple[str, str, str], dict[str, Any]] = {}
        for row in read_csv_rows(three_state_csv):
            quality = quality_by_id.get(str(row.get("canonical_annotation_id", "")))
            merged = {**quality, **row} if quality else {}
            if not merged:
                raise ValueError("three-state observation is missing its quality annotation identity")
            key = _event_evidence_key(merged)
            if key in evidence_by_id:
                raise ValueError("three-state evidence identity is duplicated")
            evidence_by_id[key] = merged
        purposes, purpose_dependencies = _load_task_purposes(task_purpose_manifest_csv)
        roster, roster_dependencies = _load_candidate_roster(candidate_roster_manifest_csv)
        assignments, assignment_dependencies = _load_assignment_history(assignment_history_csv)
        _validate_assignment_history_for_replay(assignments, events, roster)
        geometry_by_id: dict[str, dict[str, Any]] = {}
        if canonical_geometry_jsonl and canonical_geometry_jsonl.exists():
            for line in canonical_geometry_jsonl.read_text(encoding="utf-8").splitlines():
                if line.strip():
                    row = json.loads(line)
                    geometry_by_id[str(row.get("canonical_annotation_id", ""))] = normalize_geometry(row.get("corners_px") or [], width=int(row.get("width") or 1024), height=int(row.get("height") or 512))
        required_folds = {int(row["crossfit_fold"]) for row in build_crossfit_folds(events)}
        if set(policies) != required_folds:
            raise ValueError("policy manifest folds must exactly match event ledger folds")
        policy_artifacts = []
        expected_hashes = {
            "event_ledger_sha256": sha256_file(event_csv),
            "three_state_evidence_sha256": sha256_file(three_state_csv),
            "task_purpose_manifest_sha256": sha256_file(task_purpose_manifest_csv),
            "candidate_roster_manifest_sha256": sha256_file(candidate_roster_manifest_csv),
            "assignment_history_sha256": sha256_file(assignment_history_csv),
        }
        for fold in required_folds:
            payload = _validate_policy(policies[fold], fold, 2)
            if any(payload.get(field) != value for field, value in expected_hashes.items()):
                raise ValueError("temporal policy is stale against a frozen replay input")
            if payload.get("sensitivity_seed") != SENSITIVITY_SEED or payload.get("sensitivity_permutations") != SENSITIVITY_PERMUTATIONS or payload.get("primary_tie_policy") != "simultaneous_atomic_batch":
                raise ValueError("temporal policy does not freeze the required tie sensitivity contract")
            policy_artifacts.append(canonical_path(policies[fold]["policy_artifact_path"]))
        for row in events:
            for field, expected_path, expected_sha in (
                ("source_annotation", canonical_csv.resolve(), sha256_file(canonical_csv)),
                ("source_three_state", three_state_csv.resolve(), sha256_file(three_state_csv)),
            ):
                declared_path = canonical_path(row.get(f"{field}_path", ""))
                if declared_path != expected_path or row.get(f"{field}_sha256") != expected_sha:
                    raise ValueError("event ledger source binding is stale")
        dependencies = [
            event_csv, policy_manifest, *policy_artifacts, canonical_csv, quality_csv, three_state_csv,
            *([canonical_geometry_jsonl] if canonical_geometry_jsonl else []), task_purpose_manifest_csv, candidate_roster_manifest_csv, assignment_history_csv,
            *purpose_dependencies, *roster_dependencies, *assignment_dependencies,
        ]
        unique_dependencies = list({str(canonical_path(path)): canonical_path(path) for path in dependencies if path}.values())
        traces, batches, tasks, sensitivity, contracts = replay_temporal_batches(
            events, policy_by_fold=policies, evidence_by_id=evidence_by_id, geometry_by_id=geometry_by_id, task_purposes=purposes,
            candidate_roster=roster, assignment_rows=assignments, source_artifact=str(event_csv.resolve()), source_sha256=sha256_file(event_csv),
            dependency_paths=unique_dependencies, input_status=input_status, candidate_pool_source_sha256=sha256_file(candidate_roster_manifest_csv), validate_frozen_sources=True,
            contract_evidence_artifacts={
                "task_purpose_manifest_valid": str(task_purpose_manifest_csv.resolve()),
                "risk_bucket_valid": str(task_purpose_manifest_csv.resolve()),
                "family_gate_contract_valid": str(task_purpose_manifest_csv.resolve()),
                "task_completion_contract_valid": str(task_purpose_manifest_csv.resolve()),
                "candidate_pool_binding_valid": str(candidate_roster_manifest_csv.resolve()),
                "no_future_scope_leakage": str(assignment_history_csv.resolve()),
            },
        )
    except (OSError, UnicodeError, ValueError, KeyError, TypeError, json.JSONDecodeError) as exc:
        return _empty_outputs(output_csv, "not_evaluable_missing_frozen_dependency", str(exc))

    event_audit = output_csv.parent / "routing_temporal_event_audit_C1.csv"
    batch_output = output_csv.parent / "routing_temporal_batch_decisions_C1.csv"
    task_output = output_csv.parent / "routing_temporal_task_summary_C1.csv"
    sensitivity_output = output_csv.parent / "routing_temporal_order_sensitivity_C1.csv"
    contract_output = output_csv.parent / "routing_temporal_contract_summary_C1.json"
    write_csv_rows(event_audit, traces)
    write_csv_rows(output_csv, traces)
    write_csv_rows(batch_output, batches)
    write_csv_rows(task_output, tasks)
    write_csv_rows(sensitivity_output, sensitivity)
    flattened = {field: result["valid"] for field, result in contracts.items()}
    full_valid = bool(traces and batches and tasks) and all(flattened.values()) and all(row["event_validity_status"] == "valid" for row in traces)
    bundle = dependency_bundle(unique_dependencies, rule_version=RULE_VERSION)
    summary = {
        "status": "formal_replay_audit_complete" if full_valid else "not_evaluable_temporal_contract_failed",
        "rule_version": RULE_VERSION,
        "source_artifact": str(event_csv.resolve()),
        "source_sha256": sha256_file(event_csv),
        "contract_results": contracts,
        **flattened,
        "full_stop_contract_valid": full_valid,
        "n_events": len(traces),
        "n_batches": len(batches),
        "n_tasks": len(tasks),
        "n_legal_events": sum(row["event_validity_status"] == "valid" for row in traces),
        "n_illegal_events": sum(row["event_validity_status"] != "valid" for row in traces),
        "all_events_legal": all(row["event_validity_status"] == "valid" for row in traces),
        "prior_state_monotonicity": all(int(row["post_batch_k"]) >= int(row["pre_batch_k"]) for row in batches),
        "n_primary_annotations": len({
            str(row.get("canonical_annotation_id", ""))
            for row in traces
            if row.get("primary_annotation_included") and row.get("canonical_annotation_id")
        }),
        "n_tag_state_events": sum(bool(row.get("tag_state_included")) for row in traces),
        "n_nonzero_assertions": sum(bool(row.get("tag_state_included")) and str(row.get("assertion")) in {"+", "-"} for row in traces),
        "worker_identity_consistent": contracts["annotation_tag_atomicity_valid"]["valid"],
        "policy_dependency_valid": True,
        "illegal_event_reasons": dict(Counter(row["event_invalid_reason"] for row in traces if row["event_invalid_reason"])),
        "event_ledger_sha256": sha256_file(event_csv),
        "policy_manifest_sha256": sha256_file(policy_manifest),
        "event_audit_sha256": sha256_file(event_audit),
        "batch_decisions_sha256": sha256_file(batch_output),
        "task_summary_sha256": sha256_file(task_output),
        "order_sensitivity_sha256": sha256_file(sensitivity_output),
        **bundle,
        "formal_assignment_generated": False,
    }
    contract_output.write_text(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
    return summary


if __name__ == "__main__":
    raise SystemExit("Use materialize_temporal_replay from the C1 closeout workflow.")
