"""Bind frozen C1 task labels and GT geometry without inventing missing review."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import random
import sys
from pathlib import Path
from typing import Any

import numpy as np

_PROJECT_ROOT = Path(__file__).resolve().parents[3]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from tools.thesis_main.analysis.quality_core.geometry_metrics import compute_layout_mask_iou, compute_layout_mask_iou_from_normalized_pairs
from tools.thesis_main.analysis.geometry_consensus.representation import normalize_geometry, normalize_geometry_for_c1_calculation, normalize_ordered_reference_geometry
from tools.thesis_main.analysis.paper_a_contracts import METHOD_CONTRACT, load_method_contract
from tools.thesis_main.analysis.vfinal_artifact_utils import sha256_file


OUTCOME_FIELDS = [
    "project_id", "ls_runtime_task_id", "task_id", "base_task_id", "condition",
    "final_scope", "scope_resolution_status", "oos_subtype", "scope_reference_mode",
    "geometry_reference_mode", "geometry_reference_status", "reference_identity",
    "reference_sha256", "reference_worker_excluded", "reference_evidence_status",
    "adjudication_status", "reviewed_by", "reviewed_at", "notes",
    "operational_reference_status", "submission_informed_reference_revision",
    "geometry_reference_ready", "task_outcome_reference_ready", "estimand_specific_closeout_ready",
    "scope_terminal", "primary_geometry_eligible",
]

SCOPE_INITIAL_FIELDS = [
    "base_task_id", "initial_researcher_scope", "initial_reviewed_by", "initial_reviewed_at",
    "initial_protocol_version", "initial_review_source_sha256", "initial_notes",
]
SCOPE_CONSENSUS_FIELDS = [
    *SCOPE_INITIAL_FIELDS, "n_worker_in_scope", "n_worker_oos", "n_worker_missing",
    "n_worker_scope_eligible", "worker_scope_direction", "worker_scope_margin",
    "mixed_scope_response", "review_trigger",
]
SCOPE_FINAL_FIELDS = [
    *SCOPE_CONSENSUS_FIELDS, "secondary_review_required", "secondary_scope",
    "task_final_scope", "scope_resolution_status", "final_scope_source",
    "reviewed_by", "reviewed_at", "secondary_notes",
    "source_initial_review_sha256", "source_scope_consensus_sha256",
]

IMPLEMENTED_CONFLICT_TRIGGERS = (
    "dominant_cluster_low_gt_alignment",
    "minority_cluster_better_gt_alignment",
    "public_gt_structurally_invalid",
)
REFERENCE_REVIEW_DISPOSITIONS = {
    "retain_original",
    "amended_by_independent_evidence",
    "reference_unavailable",
}
REFERENCE_REVIEW_FIELDS_V2 = {
    "schema_version", "base_task_id", "review_status", "review_disposition",
    "registry_status_before_review", "reference_status_before_review",
    "reference_normalizer_status_before_review", "geometry_reference_ready_before_review",
    "method_contract_sha256",
}


def materialize_gt_cluster_alignment(
    crowd_structure_csv: Path, loo_csv: Path, quality_csv: Path,
    output_dir: Path, *, conflict_rule_manifest: Path = Path("docs/thesis_main/GT_CONFLICT_REVIEW_RULES.json"),
    reference_csv: Path | None = None, input_status: str = "dry_run",
) -> dict[str, Any]:
    """Audit crowd/GT disagreement; candidates never mutate the reference."""
    rules = json.loads(conflict_rule_manifest.read_text(encoding="utf-8"))
    reference_policy = load_method_contract().get("reference_registry", {}).get("reference_policy", "")
    formal_reference_policy_fallback = input_status == "formal" and reference_policy == "use_existing_public_gt_as_is"
    approved = rules.get("status") == "approved" and rules.get("interpretation_allowed") is True and rules.get("approved_by") and rules.get("approved_at")
    implemented_triggers = set(IMPLEMENTED_CONFLICT_TRIGGERS)
    undefined_triggers = sorted(set(rules.get("supported_triggers", [])) - implemented_triggers - {"known_reference_issue"})
    if input_status == "formal" and not approved and not formal_reference_policy_fallback:
        raise ValueError("candidate GT conflict manifest cannot produce formal sidecars")
    if input_status == "formal" and undefined_triggers and not formal_reference_policy_fallback:
        raise ValueError("GT conflict manifest contains triggers without executable definitions:" + ";".join(undefined_triggers))
    thresholds = rules["thresholds"]
    quality = {row.get("canonical_annotation_id", ""): row for row in _read_csv(quality_csv)}
    alignment: list[dict[str, Any]] = []
    context_evidence: list[dict[str, Any]] = []
    source_parts = [crowd_structure_csv, loo_csv, quality_csv, conflict_rule_manifest] + ([reference_csv] if reference_csv else [])
    evidence_sha = hashlib.sha256("".join(hashlib.sha256(path.read_bytes()).hexdigest() for path in source_parts if path and path.exists()).encode()).hexdigest()
    for crowd in _read_csv(crowd_structure_csv):
        base = crowd.get("base_task_id", "")
        condition = crowd.get("condition", "")
        task_context_id = crowd.get("task_context_id") or (f"{base}|{condition}" if condition else base)
        clusters = [("largest", crowd.get("largest_cluster_worker_ids", "")), ("second", crowd.get("second_cluster_worker_ids", ""))]
        cluster_rows = []
        for cluster_id, worker_text in clusters:
            workers = {value for value in worker_text.split(";") if value}
            medoid_id = crowd.get(f"{cluster_id}_cluster_medoid_annotation_id", "")
            medoid_worker = crowd.get(f"{cluster_id}_cluster_medoid_worker_id", "")
            medoid_geometry_sha = crowd.get(f"{cluster_id}_cluster_medoid_geometry_sha256", "")
            try:
                support = int(float(crowd.get(f"{cluster_id}_cluster_support", "")))
            except (TypeError, ValueError):
                support = len(workers)
            q = quality.get(medoid_id, {})
            try: medoid_score = float(q.get("iou_to_gt", ""))
            except (TypeError, ValueError): medoid_score = None
            public_gt_status = str(q.get("public_gt_structural_status", "not_evaluable")).strip().lower() or "not_evaluable"
            row = {
                "base_task_id": base, "condition": condition, "task_context_id": task_context_id,
                "cluster_id": cluster_id, "cluster_support": support,
                "cluster_medoid_annotation_id": medoid_id,
                "cluster_medoid_worker_id": medoid_worker,
                "cluster_medoid_geometry_sha256": medoid_geometry_sha,
                "cluster_medoid_gt_iou": "" if medoid_score is None else medoid_score,
                "largest_cluster_gt_iou": "", "second_cluster_gt_iou": "", "gt_alignment_margin": "",
                "public_gt_status": public_gt_status,
            }
            alignment.append(row); cluster_rows.append(row)
        largest, second = cluster_rows
        try:
            largest_score = float(largest["cluster_medoid_gt_iou"])
        except (TypeError, ValueError):
            largest_score = None
        try:
            second_score = float(second["cluster_medoid_gt_iou"])
        except (TypeError, ValueError):
            second_score = None
        margin = largest_score - second_score if largest_score is not None and second_score is not None else None
        for row in cluster_rows:
            row["largest_cluster_gt_iou"] = "" if largest_score is None else largest_score
            row["second_cluster_gt_iou"] = "" if second_score is None else second_score
            row["gt_alignment_margin"] = "" if margin is None else margin
        statuses = {
            "dominant_cluster_low_gt_alignment": "evaluable" if largest_score is not None else "not_evaluable",
            "minority_cluster_better_gt_alignment": (
                "not_applicable" if second["cluster_support"] == 0 else "evaluable" if margin is not None else "not_evaluable"
            ),
            "public_gt_structurally_invalid": (
                "evaluable" if any(row["public_gt_status"] in {"valid", "invalid"} for row in cluster_rows) else "not_evaluable"
            ),
        }
        triggers = []
        if largest_score is not None and largest_score < float(thresholds["dominant_cluster_low_gt_alignment"]):
            triggers.append("dominant_cluster_low_gt_alignment")
        if margin is not None and margin < -float(thresholds["minority_cluster_better_gt_margin"]):
            triggers.append("minority_cluster_better_gt_alignment")
        if any(row["public_gt_status"] == "invalid" for row in cluster_rows):
            triggers.append("public_gt_structurally_invalid")
        context_evidence.append({
            "base_task_id": base,
            "condition": condition,
            "task_context_id": task_context_id,
            "trigger_status": statuses,
            "triggered": sorted(triggers),
            "largest_cluster_gt_iou": largest_score,
            "second_cluster_gt_iou": second_score,
            "gt_alignment_margin": margin,
        })
    summary_sets = {
        trigger: {key: set() for key in ("evaluable", "not_evaluable", "not_applicable", "triggered")}
        for trigger in IMPLEMENTED_CONFLICT_TRIGGERS
    }
    for evidence in context_evidence:
        base, context = evidence["base_task_id"], evidence["task_context_id"]
        for trigger, status in evidence["trigger_status"].items():
            summary_sets[trigger][status].add(context)
        for trigger in evidence["triggered"]:
            summary_sets[trigger]["triggered"].add(context)
    trigger_summary = {}
    for trigger, values in summary_sets.items():
        trigger_summary[trigger] = {
            "evaluable_count": len(values["evaluable"]),
            "not_evaluable_count": len(values["not_evaluable"]),
            "not_applicable_count": len(values["not_applicable"]),
            "triggered_count": len(values["triggered"]),
            "unique_task_evaluable_count": len({item["base_task_id"] for item in context_evidence if item["task_context_id"] in values["evaluable"]}),
            "unique_task_triggered_count": len({item["base_task_id"] for item in context_evidence if item["task_context_id"] in values["triggered"]}),
        }
    queue_by_key: dict[tuple[str, str], dict[str, Any]] = {}
    for evidence in context_evidence:
        for trigger in evidence["triggered"]:
            item = queue_by_key.setdefault((evidence["base_task_id"], trigger), {
                "base_task_id": evidence["base_task_id"], "trigger": trigger,
                "candidate_only": not approved, "interpretation_allowed": False,
                "reference_modified": False, "rule_version": rules["rule_version"],
                "source_sha256": evidence_sha, "context_count": 0, "context_ids": [],
            })
            item["context_count"] += 1
            item["context_ids"].append(evidence["task_context_id"])
    queue = []
    for item in queue_by_key.values():
        item["context_ids_json"] = json.dumps(sorted(item.pop("context_ids")), ensure_ascii=False, separators=(",", ":"))
        queue.append(item)
    queue.sort(key=lambda row: (row["base_task_id"], row["trigger"]))
    incomplete = bool(undefined_triggers) or any(item["not_evaluable_count"] for item in trigger_summary.values())
    screen_status = "incomplete_not_evaluable" if any(item["not_evaluable_count"] for item in trigger_summary.values()) else "incomplete_undefined_trigger" if undefined_triggers else "completed_implemented_triggers_only"
    _write(output_dir / "c1_gt_cluster_alignment.csv", alignment, list(alignment[0]) if alignment else ["base_task_id"])
    _write(output_dir / "c1_gt_conflict_review_queue.csv", queue, list(queue[0]) if queue else ["base_task_id", "trigger", "candidate_only", "reference_modified", "rule_version", "source_sha256"])
    summary = {
        "schema_version": "paper_a_gt_conflict_trigger_summary_v2",
        "screen_status": screen_status,
        "candidate_count": len({row["base_task_id"] for row in queue}),
        "alignment_context_count": len(context_evidence),
        "undefined_triggers": undefined_triggers,
        "trigger_summary": trigger_summary,
    }
    _write_json(output_dir / "c1_gt_conflict_trigger_summary.json", summary)
    return {
        "alignment_rows": len(alignment), "conflict_candidates": len(queue),
        "candidate_count": summary["candidate_count"], "reference_modified": False,
        "reference_policy": reference_policy, "gt_issue_declared": False,
        "undefined_triggers": undefined_triggers, "screen_status": screen_status,
        "trigger_summary": trigger_summary,
        "interpretation_allowed": bool(input_status == "formal" and approved and not incomplete),
    }


def freeze_spot_check_reserve_order(task_ids: list[str] | set[str], *, stage: str, seed: int = 20260805, count: int = 5) -> dict[str, Any]:
    """Freeze the full deterministic order; final selection can skip later flags mechanically."""
    population = sorted({str(task_id).strip() for task_id in task_ids if str(task_id).strip()})
    order = list(population)
    random.Random(seed).shuffle(order)
    return {
        "stage": stage,
        "sampling_algorithm": "python_random.Random(seed).shuffle(sorted(unique_task_ids))",
        "python_version": sys.version.split()[0],
        "sampling_seed": seed,
        "requested_count": count,
        "population_count": len(population),
        "candidate_population_sha256": _sha_payload(population),
        "reserve_order": order,
    }


def select_final_nonflagged_spot_check(reserve_order: list[str], *, flagged_task_ids: set[str], known_issue_ids: set[str], count: int = 5) -> list[str]:
    excluded = {str(item).strip() for item in flagged_task_ids | known_issue_ids}
    selected = [task_id for task_id in reserve_order if task_id not in excluded][:count]
    if len(selected) != count:
        raise ValueError("not_enough_nonflagged_spot_check")
    return selected


def validate_reference_review_closure(
    review_record_csv: Path,
    *,
    affected_base_task_ids: set[str] | None = None,
    method_contract_sha256: str | None = None,
) -> dict[str, Any]:
    rows = _read_csv(review_record_csv)
    if not rows:
        raise ValueError("reference_conflict_review_record_empty")
    required = REFERENCE_REVIEW_FIELDS_V2 | {"reviewer_blinding", "original_reference_sha256"}
    if any(not required <= set(row) for row in rows):
        raise ValueError("reference_conflict_review_record_schema_mismatch")
    if len({row.get("base_task_id", "") for row in rows}) != len(rows):
        raise ValueError("reference_conflict_review_record_duplicate_task")
    expected_sha = method_contract_sha256 or sha256_file(METHOD_CONTRACT)
    pending = []
    for row in rows:
        if row.get("schema_version") != "paper_a_reference_conflict_review_record_v2":
            raise ValueError("reference_conflict_review_record_legacy_schema")
        if row.get("method_contract_sha256") != expected_sha:
            raise ValueError("reference_conflict_review_record_method_sha_mismatch")
        disposition = str(row.get("review_disposition", "")).strip()
        status = str(row.get("review_status", "")).strip().lower()
        if disposition not in REFERENCE_REVIEW_DISPOSITIONS or status in {"", "pending_review", "open"}:
            pending.append(row.get("base_task_id", ""))
    affected = {str(item).strip() for item in (affected_base_task_ids or set())}
    blocked = sorted(item for item in pending if not affected or item in affected)
    if blocked:
        raise ValueError("reference_conflict_pending_review:" + ",".join(blocked))
    return {"record_count": len(rows), "pending_count": len(pending), "checked_sha256": sha256_file(review_record_csv)}


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as stream:
        return list(csv.DictReader(stream))


def _write(path: Path, rows: list[dict[str, Any]], fields: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _sha_payload(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def _scope(inventory: dict[str, str]) -> tuple[str, str, str, str]:
    status = inventory.get("expert_review_status", "")
    if status == "latest_human_reviewed":
        raw, reviewer = inventory.get("expert_scope_confirmed", "").strip().lower(), "latest_human_reviewed"
        return ("in_scope", "", "expert_adjudicated", reviewer) if raw.startswith("inscope") else (
            ("oos", raw, "expert_adjudicated", reviewer) if raw.startswith("oos") else ("", "", "", "")
        )
    if status == "legacy_labeled_proxy":
        # Historical labels are useful migration evidence, but are not the frozen
        # operational task-outcome reference required by the current protocol.
        return "", "", "legacy_proxy_pending_review", "legacy_human_label"
    return "", "", "", ""


def _truth(value: Any) -> bool:
    return str(value).strip().lower() in {"1", "true", "yes", "y"}


def _worker_key(value: Any) -> str:
    text = str(value).strip().upper()
    if text.startswith("W"):
        text = text[1:]
    try:
        return str(int(text))
    except ValueError:
        return text


def _worker_scope_response(value: str) -> str:
    try:
        choices = json.loads(value or "{}").get("scope") or []
    except json.JSONDecodeError:
        return ""
    if isinstance(choices, str):
        choices = [choices]
    normalized = {str(choice).strip().lower() for choice in choices}
    if normalized & {"normal", "in_scope", "inscope"}:
        return "in_scope"
    if any(choice.startswith("oos") or choice == "out_of_scope" for choice in normalized):
        return "oos"
    return ""


def _initial_scope_review_base_ids(canonical: list[dict[str, str]], inventory_scopes: dict[str, tuple[str, str, str, str]]) -> set[str]:
    """Use the formal C1 core mapping when it is present, not inventory labels."""
    mapped = {
        row.get("base_task_id", "")
        for row in canonical
        if row.get("condition", "").strip().lower() == "manual"
        and row.get("planned_project_name", "").strip() == "C1_core_all"
        and row.get("base_task_id", "")
    }
    return mapped or {base for base, scope in inventory_scopes.items() if not scope[0]}


def _load_initial_scope_reviews(path: Path | None, base_ids: set[str]) -> tuple[dict[str, dict[str, str]], int, str]:
    if not path or not path.exists():
        return {}, 0, ""
    rows = _read_csv(path)
    by_base: dict[str, dict[str, str]] = {}
    invalid = 0
    for row in rows:
        base = row.get("base_task_id", "")
        if base not in base_ids or base in by_base:
            invalid += 1
            continue
        scope = row.get("initial_researcher_scope", "").strip().lower()
        if scope not in {"in_scope", "oos"} or not all(row.get(field, "").strip() for field in ("initial_reviewed_by", "initial_reviewed_at", "initial_protocol_version", "initial_review_source_sha256")):
            invalid += 1
            continue
        by_base[base] = row
    invalid += len(base_ids - set(by_base))
    return by_base, invalid, hashlib.sha256(path.read_bytes()).hexdigest()


def _scope_consensus(
    canonical: list[dict[str, str]], meta_csv: Path | None,
    independence_csv: Path | None, outside_csv: Path | None,
    initial_reviews: dict[str, dict[str, str]],
) -> list[dict[str, Any]]:
    meta_rows = _read_csv(meta_csv) if meta_csv and meta_csv.exists() else []
    outside_rows = _read_csv(outside_csv) if outside_csv and outside_csv.exists() else []
    meta = {row.get("canonical_annotation_id", ""): row for row in meta_rows}
    outside = {row.get("canonical_annotation_id", ""): row for row in outside_rows}
    responses: dict[str, dict[str, set[str]]] = {}
    excluded: dict[str, int] = {}
    base_ids = {row.get("base_task_id", "") for row in canonical if row.get("base_task_id", "")}
    for row in canonical:
        base = row.get("base_task_id", "")
        annotation_id = row.get("canonical_annotation_id", "")
        observation = meta.get(annotation_id, {})
        duplicate_status = row.get("duplicate_review_status", "").strip().lower()
        provenance = row.get("assignment_provenance", observation.get("assignment_provenance", "")).strip()
        eligible = (
            bool(base and annotation_id)
            and provenance in {"original_assignment", "authorized_replacement_assignment", "late_entry_calibration_assignment"}
            and not _truth(row.get("outside_assignment_submission", observation.get("outside_assignment_submission", "")))
            and not _truth(outside.get(annotation_id, {}).get("outside_assignment_disposition_applied", ""))
            and duplicate_status not in {"pending", "unresolved", "needs_review"}
            and _worker_key(row.get("worker_id", observation.get("worker_id", ""))) != "14"
            and _truth(observation.get("schema_interpretable", "true"))
        )
        response = _worker_scope_response(observation.get("choice_map_json", ""))
        if not eligible or not response:
            excluded[base] = excluded.get(base, 0) + 1
            continue
        responses.setdefault(base, {}).setdefault(_worker_key(row.get("worker_id", observation.get("worker_id", ""))), set()).add(response)
    rows: list[dict[str, Any]] = []
    for base in sorted(base_ids):
        worker_responses = responses.get(base, {})
        values = [next(iter(value)) for value in worker_responses.values() if len(value) == 1]
        n_in = values.count("in_scope")
        n_oos = values.count("oos")
        total = n_in + n_oos
        direction = "in_scope" if total >= 3 and n_in > n_oos else "oos" if total >= 3 and n_oos > n_in else "no_consensus"
        initial = initial_reviews.get(base, {})
        initial_scope = initial.get("initial_researcher_scope", "")
        trigger = "initial_review_missing" if not initial_scope else "worker_no_consensus" if direction == "no_consensus" else "researcher_worker_direction_disagreement" if direction != initial_scope else ""
        rows.append({
            "base_task_id": base,
            "initial_researcher_scope": initial_scope,
            "initial_reviewed_by": initial.get("initial_reviewed_by", ""),
            "initial_reviewed_at": initial.get("initial_reviewed_at", ""),
            "initial_protocol_version": initial.get("initial_protocol_version", ""),
            "initial_review_source_sha256": initial.get("initial_review_source_sha256", ""),
            "initial_notes": initial.get("initial_notes", ""),
            "n_worker_in_scope": n_in, "n_worker_oos": n_oos,
            "n_worker_missing": excluded.get(base, 0) + sum(len(value) != 1 for value in worker_responses.values()),
            "n_worker_scope_eligible": total,
            "worker_scope_direction": direction,
            "worker_scope_margin": "" if not total else abs(n_in - n_oos) / total,
            "mixed_scope_response": total > 0 and n_in > 0 and n_oos > 0,
            "review_trigger": trigger,
        })
    return rows


def _gt_references(path: Path) -> dict[str, dict[str, Any]]:
    references = {}
    for task in json.loads(path.read_text(encoding="utf-8-sig")):
        stem = Path(str((task.get("data") or {}).get("title") or (task.get("data") or {}).get("image", ""))).stem
        annotations = [row for row in task.get("annotations", []) if row.get("ground_truth")]
        if not stem or len(annotations) != 1:
            continue
        annotation = annotations[0]
        points = []
        for result in annotation.get("result", []):
            if result.get("type") != "keypointlabels":
                continue
            value = result.get("value") or {}
            points.append([float(value["x"]) * 10.24, float(value["y"]) * 5.12])
        normalized = normalize_ordered_reference_geometry(points)
        references[stem] = {
            "identity": f"gt:{task.get('project')}:{task.get('id')}:{annotation.get('id')}",
            "points": points,
            "pairs": normalized.get("pairs", []),
            "geometry_mode": normalized.get("reference_geometry_mode", "not_evaluable"),
            "sha256": _sha_payload(annotation.get("result", [])),
            "structural_status": "valid" if normalized["valid"] else "invalid",
        }
    return references


def materialize(
    canonical_csv: Path, geometry_jsonl: Path, inventory_csv: Path, gt_export: Path, output_dir: Path,
    *, scope_adjudication_csv: Path | None = None, scope_initial_review_csv: Path | None = None,
    scope_meta_csv: Path | None = None, scope_independence_csv: Path | None = None,
    scope_outside_csv: Path | None = None, reference_amendment: Path | None = None,
    formal: bool = False,
) -> dict[str, Any]:
    canonical = _read_csv(canonical_csv)
    inventory = {row.get("base_task_id", ""): row for row in _read_csv(inventory_csv)}
    geometry = {
        row.get("canonical_annotation_id", ""): row
        for line in geometry_jsonl.read_text(encoding="utf-8").splitlines() if line.strip()
        for row in [json.loads(line)]
    }
    references = _gt_references(gt_export)
    amendments: dict[str, dict[str, Any]] = {}
    invalid_amendments = 0
    canonical_ids_by_base = {
        base: {row.get("canonical_annotation_id", "") for row in canonical if row.get("base_task_id", "") == base}
        for base in {row.get("base_task_id", "") for row in canonical}
    }
    for row in _read_csv(reference_amendment) if reference_amendment and reference_amendment.exists() else []:
        base = row.get("base_task_id", "")
        try:
            points = json.loads(row.get("corrected_points_json", ""))
            triggers = set(json.loads(row.get("triggering_canonical_annotation_ids_json", "[]") or "[]"))
        except (json.JSONDecodeError, TypeError):
            invalid_amendments += 1
            continue
        public_sha = references.get(base, {}).get("sha256", "")
        expected_public_sha = row.get("source_public_gt_sha256", "")
        valid = (
            bool(base and isinstance(points, list) and points)
            and base not in amendments
            and row.get("reference_status") == "reference_corrected"
            and all(row.get(field, "").strip() for field in ("reviewed_by", "reviewed_at"))
            and expected_public_sha == public_sha
            and triggers.issubset(canonical_ids_by_base.get(base, set()))
            and normalize_geometry(points)["valid"]
        )
        if not valid:
            invalid_amendments += 1
            continue
        reference_sha = _sha_payload(points)
        references[base] = {"identity": row.get("reference_identity") or f"corrected_gt:{base}:{reference_sha[:12]}", "points": points, "sha256": reference_sha, "structural_status": "valid"}
        amendments[base] = {**row, "triggers": triggers}
    contexts = {}
    audit = []
    base_ids = {row.get("base_task_id", "") for row in canonical if row.get("base_task_id", "")}
    inventory_scopes = {base: _scope(inventory.get(base, {})) for base in base_ids}
    initial_review_base_ids = _initial_scope_review_base_ids(canonical, inventory_scopes)
    initial_reviews, invalid_initial_reviews, initial_sha = _load_initial_scope_reviews(
        scope_initial_review_csv, initial_review_base_ids,
    )
    use_scope_workflow = scope_initial_review_csv is not None
    raw_scope_decisions = _read_csv(scope_adjudication_csv) if scope_adjudication_csv and scope_adjudication_csv.exists() else []
    scope_decisions: dict[str, dict[str, str]] = {}
    candidate_by_base: dict[str, dict[str, Any]] = {}
    consensus_sha = ""
    invalid_scope_decisions = 0
    if use_scope_workflow:
        has_formal_core_mapping = any(
            row.get("planned_project_name", "").strip() == "C1_core_all"
            and row.get("condition", "").strip().lower() == "manual"
            for row in canonical
        )
        scope_canonical = [
            row for row in canonical
            if row.get("base_task_id", "") in initial_review_base_ids
            and (
                not has_formal_core_mapping
                or (
                    row.get("planned_project_name", "").strip() == "C1_core_all"
                    and row.get("condition", "").strip().lower() == "manual"
                )
            )
        ]
        consensus = _scope_consensus(
            scope_canonical,
            scope_meta_csv, scope_independence_csv, scope_outside_csv, initial_reviews,
        )
        consensus_path = output_dir / "c1_scope_consensus_audit.csv"
        _write(consensus_path, consensus, SCOPE_CONSENSUS_FIELDS)
        consensus_sha = hashlib.sha256(consensus_path.read_bytes()).hexdigest()
        queue = [row for row in consensus if row["review_trigger"]]
        _write(output_dir / "c1_scope_secondary_review_queue.csv", queue, SCOPE_CONSENSUS_FIELDS)
        _write(output_dir / "c1_scope_review_queue.csv", queue, SCOPE_CONSENSUS_FIELDS)
        _write(output_dir / "c1_scope_base_task_review_queue.csv", queue, SCOPE_CONSENSUS_FIELDS)
        for row in consensus:
            direct = not row["review_trigger"]
            candidate_by_base[row["base_task_id"]] = {
                **row,
                "secondary_review_required": str(not direct).lower(),
                "secondary_scope": "",
                "task_final_scope": row["initial_researcher_scope"] if direct else "",
                "scope_resolution_status": "resolved" if direct else "pending",
                "final_scope_source": "worker_researcher_concordant" if direct else "",
                "reviewed_by": row["initial_reviewed_by"] if direct else "",
                "reviewed_at": row["initial_reviewed_at"] if direct else "",
                "secondary_notes": "",
                "source_initial_review_sha256": initial_sha,
                "source_scope_consensus_sha256": consensus_sha,
            }
        _write(output_dir / "c1_scope_initial_review_template.csv", [{"base_task_id": base, **{field: "" for field in SCOPE_INITIAL_FIELDS if field != "base_task_id"}} for base in sorted(initial_review_base_ids)], SCOPE_INITIAL_FIELDS)
        _write(output_dir / "c1_scope_adjudication_template.csv", list(candidate_by_base.values()), SCOPE_FINAL_FIELDS)
        supplied = {row.get("base_task_id", ""): row for row in raw_scope_decisions}
        def valid_scope_decision(row: dict[str, str]) -> bool:
            candidate = candidate_by_base.get(row.get("base_task_id", ""), {})
            terminal = row.get("task_final_scope", "").strip().lower() in {"in_scope", "oos", "unresolved"}
            common = (
                row.get("source_initial_review_sha256") == initial_sha
                and row.get("source_scope_consensus_sha256") == consensus_sha
                and terminal
                and all(row.get(field, "").strip() for field in ("reviewed_by", "reviewed_at"))
            )
            if _truth(candidate.get("secondary_review_required")):
                return common and _truth(row.get("secondary_review_required")) and row.get("secondary_scope", "").strip().lower() == row.get("task_final_scope", "").strip().lower()
            return common and not _truth(row.get("secondary_review_required")) and not row.get("secondary_scope", "").strip() and row.get("task_final_scope", "").strip().lower() == candidate.get("initial_researcher_scope", "").strip().lower()

        valid_rows = {
            row["base_task_id"]: row
            for row in raw_scope_decisions
            if row.get("base_task_id", "") in initial_review_base_ids and valid_scope_decision(row)
        }
        valid_supplied = (
            len(supplied) == len(raw_scope_decisions) == len(initial_review_base_ids)
            and set(supplied) == initial_review_base_ids
            and len(valid_rows) == len(initial_review_base_ids)
        )
        scope_decisions = valid_rows
        if raw_scope_decisions:
            invalid_scope_decisions = len(raw_scope_decisions) - len(valid_rows)
    else:
        scope_queue_by_base = {}
        for row in canonical:
            base = row.get("base_task_id", "")
            item = inventory.get(base, {})
            final_scope, _oos, _mode, _reviewer = _scope(item)
            if base and not final_scope:
                scope_queue_by_base.setdefault(base, {
                    "base_task_id": base,
                    "pending_reason": "unreviewed_or_ambiguous_scope",
                    "inventory_review_status": item.get("expert_review_status", "missing"),
                })
        scope_queue = list(scope_queue_by_base.values())
        queue_path = output_dir / "c1_scope_base_task_review_queue.csv"
        _write(output_dir / "c1_scope_review_queue.csv", scope_queue, ["base_task_id", "pending_reason", "inventory_review_status"])
        _write(queue_path, scope_queue, ["base_task_id", "pending_reason", "inventory_review_status"])
        queue_sha = hashlib.sha256(queue_path.read_bytes()).hexdigest()
        _write(output_dir / "c1_scope_initial_review_template.csv", [
            {"base_task_id": base, **{field: "" for field in SCOPE_INITIAL_FIELDS if field != "base_task_id"}}
            for base in sorted(initial_review_base_ids)
        ], SCOPE_INITIAL_FIELDS)
        _write(output_dir / "c1_scope_adjudication_template.csv", [
            {**row, "final_scope": "", "oos_subtype": "", "reviewed_by": "", "reviewed_at": "", "source_queue_sha256": queue_sha}
            for row in scope_queue
        ], ["base_task_id", "pending_reason", "inventory_review_status", "final_scope", "oos_subtype", "reviewed_by", "reviewed_at", "source_queue_sha256"])
        valid_scope_decisions = [row for row in raw_scope_decisions if row.get("source_queue_sha256") == queue_sha]
        scope_decisions = {row.get("base_task_id", ""): row for row in valid_scope_decisions}
        invalid_scope_decisions = len(raw_scope_decisions) - len(valid_scope_decisions)
    for row in canonical:
        key = tuple(row.get(field, "") for field in ("project_id", "ls_runtime_task_id", "task_id", "base_task_id", "condition"))
        if key in contexts:
            continue
        item = inventory.get(row.get("base_task_id", ""), {})
        workflow_subject = use_scope_workflow and key[3] in initial_review_base_ids
        if workflow_subject:
            # A pending or stale C1-Core disposition must never fall back to the
            # legacy inventory: that would silently turn a review queue into data.
            final_scope, oos_subtype, scope_mode, reviewer = "", "", "", ""
            decision = scope_decisions.get(key[3], candidate_by_base.get(key[3], {}))
        else:
            final_scope, oos_subtype, scope_mode, reviewer = _scope(item)
            decision = scope_decisions.get(key[3], {})
        if decision and decision.get("task_final_scope", decision.get("final_scope", "")).lower() in {"in_scope", "oos", "unresolved"} and all(decision.get(field) for field in ("reviewed_by", "reviewed_at")):
            final_scope = decision.get("task_final_scope", decision.get("final_scope", "")).lower()
            oos_subtype = decision.get("oos_subtype", "")
            scope_mode = decision.get("final_scope_source", "sha_bound_base_task_adjudication") or "sha_bound_base_task_adjudication"
            reviewer = decision["reviewed_by"]
        reference = references.get(row.get("base_task_id", ""), {})
        amendment = amendments.get(row.get("base_task_id", ""), {})
        status = "terminal_unresolved" if final_scope == "unresolved" else "resolved" if final_scope else "pending"
        geometry_ready = bool(reference.get("points")) and reference.get("structural_status") == "valid"
        reference_status = "scope_unresolved_excluded" if final_scope == "unresolved" else "oos_geometry_not_applicable" if final_scope == "oos" else "reference_corrected" if amendment else "reference_ready" if geometry_ready else "pending_adjudication"
        audit.append({
            **dict(zip(("project_id", "ls_runtime_task_id", "task_id", "base_task_id", "condition"), key)),
            "inventory_review_status": item.get("expert_review_status", "missing"),
            "scope_source": scope_mode, "task_outcome_status": status,
            "gt_reference_present": bool(reference), "geometry_reference_ready": geometry_ready,
            "pending_reason": "" if status != "pending" else "unreviewed_or_ambiguous_scope",
        })
        contexts[key] = {
                **dict(zip(("project_id", "ls_runtime_task_id", "task_id", "base_task_id", "condition"), key)),
                "final_scope": final_scope, "scope_resolution_status": status,
                "oos_subtype": oos_subtype, "scope_reference_mode": scope_mode,
                "geometry_reference_mode": "expert_corrected_frozen_gt" if amendment else "public_frozen_gt" if reference else "not_required_oos" if final_scope == "oos" else "",
                "geometry_reference_status": "reference_ready_corrected_gt" if amendment else "reference_ready_public_gt" if geometry_ready else "reference_invalid" if reference else "not_required" if final_scope == "oos" else "reference_missing",
                "reference_identity": reference.get("identity", ""),
                "reference_sha256": reference.get("sha256", ""),
                "reference_worker_excluded": "false", "reference_evidence_status": "evaluable" if reference and final_scope == "in_scope" else "not_required" if final_scope == "oos" else "scope_unresolved_excluded" if final_scope == "unresolved" else "not_evaluable",
                "adjudication_status": status,
                "reviewed_by": amendment.get("reviewed_by") or decision.get("reviewed_by") or reviewer,
                "operational_reference_status": reference_status,
                "submission_informed_reference_revision": bool(amendment.get("triggers")),
                "geometry_reference_ready": geometry_ready if final_scope == "in_scope" else final_scope == "oos",
                "task_outcome_reference_ready": status != "pending",
                "estimand_specific_closeout_ready": (geometry_ready if final_scope == "in_scope" else final_scope in {"oos", "unresolved"}),
                "scope_terminal": status != "pending",
                "primary_geometry_eligible": final_scope == "in_scope" and geometry_ready,
                "reviewed_at": amendment.get("reviewed_at") or decision.get("reviewed_at") or "",
                "notes": amendment.get("notes", "review time absent in frozen candidate inventory; formal mode must fail closed"),
            }
    quality = []
    outcomes_by_key = contexts
    for row in canonical:
        key = tuple(row.get(field, "") for field in ("project_id", "ls_runtime_task_id", "task_id", "base_task_id", "condition"))
        outcome = outcomes_by_key.get(key, {})
        geom = geometry.get(row.get("canonical_annotation_id", ""), {})
        reference = references.get(row.get("base_task_id", ""), {})
        amendment = amendments.get(row.get("base_task_id", ""), {})
        score, meta = None, {"reason": "reference_geometry_missing"}
        calculation_geometry = normalize_geometry_for_c1_calculation(
            geom.get("corners_px") or [], width=int(geom.get("width") or 1024), height=int(geom.get("height") or 512),
        )
        calculation_points = calculation_geometry["canonical_points"] if calculation_geometry["geometry_repair_applied"] else geom.get("corners_px") or []
        # Preserve the legacy scorer's handling of all non-repair rows.  This
        # amendment changes only the uniquely repaired orphan-point input.
        structurally_valid = bool(calculation_points)
        if row.get("canonical_annotation_id", "") in amendment.get("triggers", set()):
            meta = {"reason": "submission_informed_reference_revision"}
        elif not structurally_valid:
            meta = {"reason": "annotation_geometry_invalid"}
        elif outcome.get("final_scope") == "in_scope" and calculation_points and reference.get("points") and reference.get("structural_status") == "valid":
            if reference.get("geometry_mode") == "ordered_consecutive_pairs_with_duplicate_x":
                score, meta = compute_layout_mask_iou_from_normalized_pairs(calculation_geometry["pairs"], reference["pairs"])
            else:
                score, meta = compute_layout_mask_iou(np.asarray(calculation_points, dtype=float), np.asarray(reference["points"], dtype=float))
        quality.append({
            "project_id": row.get("project_id", ""), "ls_runtime_task_id": row.get("ls_runtime_task_id", ""),
            "task_id": row.get("task_id", ""), "base_task_id": row.get("base_task_id", ""),
            "worker_id": row.get("worker_id", ""), "annotation_id": row.get("annotation_id", ""),
            "canonical_annotation_id": row.get("canonical_annotation_id", ""), "condition": row.get("condition", ""),
            "dataset_group": row.get("dataset_group", ""), "iou_to_gt": "" if score is None else score,
            "quality_evaluable": score is not None, "quality_evaluable_legacy_alias": score is not None,
            "gt_score_computable": score is not None, "gt_reference_resolved": bool(reference.get("points")) and reference.get("structural_status") == "valid",
            "public_gt_structural_status": reference.get("structural_status", "not_evaluable"),
            "public_gt_geometry_mode": reference.get("geometry_mode", "not_evaluable"),
            "gt_primary_analysis_eligible": bool(score is not None and row.get("condition", "").lower() == "manual" and outcome.get("final_scope") == "in_scope" and outcome.get("adjudication_status") == "resolved" and row.get("canonical_annotation_id", "") not in amendment.get("triggers", set())),
            "structurally_valid": structurally_valid,
            "geometry_repair_applied": calculation_geometry["geometry_repair_applied"],
            "geometry_repair_status": calculation_geometry["geometry_repair_status"],
            "geometry_repair_rule_version": calculation_geometry["geometry_repair_rule_version"],
            "raw_point_count": calculation_geometry["raw_point_count"],
            "repaired_point_count": calculation_geometry["repaired_point_count"],
            "dropped_point_index": calculation_geometry["dropped_point_index"],
            "raw_geometry_sha256": calculation_geometry["raw_geometry_sha256"],
            "repaired_geometry_sha256": calculation_geometry["repaired_geometry_sha256"],
            "independence_status": row.get("independence_status", ""),
            "failure_attribution": row.get("failure_attribution", ""),
            "outside_assignment_submission": row.get("outside_assignment_submission", ""),
            "duplicate_worker_task_submission": row.get("duplicate_worker_task_submission", ""),
            "worker_caused_structural_failure": row.get("worker_caused_structural_failure", ""),
            "task_outcome_status": outcome.get("adjudication_status", "pending"),
            "geometry_reference_status": outcome.get("geometry_reference_status", "reference_missing"),
            "quality_interpretation_status": "scope_unresolved_excluded" if outcome.get("adjudication_status") == "terminal_unresolved" else "provisional_pending_task_outcome" if score is not None and outcome.get("adjudication_status") != "resolved" else "resolved" if score is not None else "not_evaluable",
            "reference_identity": reference.get("identity", ""), "reference_sha256": reference.get("sha256", ""),
            "submission_informed_reference_revision": row.get("canonical_annotation_id", "") in amendment.get("triggers", set()),
            "score_reason": "" if score is not None else meta.get("reason", "not_evaluable"),
        })
    if use_scope_workflow:
        final_dispositions = []
        for base in sorted(base_ids):
            if base not in candidate_by_base:
                final_scope, oos_subtype, scope_mode, reviewer = inventory_scopes[base]
                candidate = {
                    "base_task_id": base,
                    **{field: "" for field in SCOPE_INITIAL_FIELDS if field != "base_task_id"},
                    **{field: "" for field in SCOPE_CONSENSUS_FIELDS if field not in SCOPE_INITIAL_FIELDS},
                    "secondary_review_required": "false", "secondary_scope": "",
                    "task_final_scope": final_scope,
                    "scope_resolution_status": "resolved" if final_scope else "pending",
                    "final_scope_source": "inventory_latest_human_reviewed" if final_scope else "",
                    "reviewed_by": reviewer, "reviewed_at": "", "secondary_notes": "",
                    "source_initial_review_sha256": "", "source_scope_consensus_sha256": "",
                }
            else:
                candidate = dict(candidate_by_base[base])
            if base in scope_decisions:
                candidate.update(scope_decisions[base])
                candidate["scope_resolution_status"] = "terminal_unresolved" if candidate["task_final_scope"].lower() == "unresolved" else "resolved" if candidate["task_final_scope"].lower() in {"in_scope", "oos"} else "pending"
                candidate["final_scope_source"] = "secondary_review_unresolved" if candidate["task_final_scope"].lower() == "unresolved" else "secondary_protocol_review" if _truth(candidate["secondary_review_required"]) else "worker_researcher_concordant"
            final_dispositions.append(candidate)
        _write(output_dir / "c1_task_scope_final_disposition.csv", final_dispositions, SCOPE_FINAL_FIELDS)
    outcome_rows = list(contexts.values())
    _write(output_dir / "c1_task_outcome_reference.csv", outcome_rows, OUTCOME_FIELDS)
    audit_fields = list(audit[0]) if audit else ["task_id"]
    _write(output_dir / "c1_task_outcome_reference_audit.csv", audit, audit_fields)
    quality_fields = list(quality[0]) if quality else ["task_id"]
    _write(output_dir / "c1_gt_quality_evidence.csv", quality, quality_fields)
    pending_by_base = {}
    for row in audit:
        if row["task_outcome_status"] == "pending":
            pending_by_base.setdefault(row["base_task_id"], {"base_task_id": row["base_task_id"], "pending_reason": row["pending_reason"], "inventory_review_status": row["inventory_review_status"]})
    amendment_candidates = sorted({row["base_task_id"] for row in audit if not row["gt_reference_present"]})
    _write(output_dir / "c1_reference_amendment_template.csv", [{
        "base_task_id": base, "reference_status": "", "corrected_points_json": "",
        "triggering_canonical_annotation_ids_json": "[]", "source_public_gt_sha256": "",
        "reference_identity": "", "reviewed_by": "", "reviewed_at": "", "notes": "",
    } for base in amendment_candidates], ["base_task_id", "reference_status", "corrected_points_json", "triggering_canonical_annotation_ids_json", "source_public_gt_sha256", "reference_identity", "reviewed_by", "reviewed_at", "notes"])
    support_after_exclusion = [{
        "worker_id": worker,
        "resolved_in_scope_support": sum(row.get("worker_id") == worker and contexts.get((row.get("project_id", ""), row.get("ls_runtime_task_id", ""), row.get("task_id", ""), row.get("base_task_id", ""), row.get("condition", "")), {}).get("final_scope") == "in_scope" for row in quality),
        "pending_scope_excluded_support": sum(row.get("worker_id") == worker and row.get("task_outcome_status") == "pending" for row in quality),
        "terminal_scope_excluded_support": sum(row.get("worker_id") == worker and row.get("task_outcome_status") == "terminal_unresolved" for row in quality),
    } for worker in sorted({row.get("worker_id", "") for row in quality})]
    _write(output_dir / "c1_scope_support_after_exclusion_audit.csv", support_after_exclusion, ["worker_id", "resolved_in_scope_support", "pending_scope_excluded_support", "terminal_scope_excluded_support"])
    status_counts = {status: sum(row.get("operational_reference_status") == status for row in outcome_rows) for status in ("reference_ready", "reference_corrected", "pending_adjudication", "oos_geometry_not_applicable", "scope_unresolved_excluded")}
    terminal_ready = bool(outcome_rows) and all(bool(row["scope_terminal"]) for row in outcome_rows)
    estimand_ready = bool(outcome_rows) and all(bool(row["estimand_specific_closeout_ready"]) for row in outcome_rows)
    scope_disposition_frozen = not use_scope_workflow or valid_supplied
    summary = {
        "reference_policy": "use_existing_public_gt_as_is",
        "gt_issue_declared": bool(reference_amendment and amendments),
        "correction_count": len(amendments),
        "review_policy": "amend_only_when_researcher_explicitly_declares_gt_issue",
        "n_task_contexts": len(audit), "n_resolved_contexts": sum(row["adjudication_status"] == "resolved" for row in outcome_rows),
        "n_pending_contexts": sum(row["task_outcome_status"] == "pending" for row in audit),
        "n_gt_quality_evaluable": sum(bool(row["quality_evaluable"]) for row in quality),
        "reference_status_counts": status_counts,
        "geometry_reference_ready": bool(outcome_rows) and all(bool(row["geometry_reference_ready"]) or row.get("final_scope") == "unresolved" for row in outcome_rows),
        "task_outcome_reference_ready": terminal_ready,
        "estimand_specific_closeout_ready": estimand_ready,
        "n_pending_base_tasks": len(pending_by_base),
        "reference_amendment_sha256": hashlib.sha256(reference_amendment.read_bytes()).hexdigest() if reference_amendment and reference_amendment.exists() else "",
        "scope_adjudication_sha256": hashlib.sha256(scope_adjudication_csv.read_bytes()).hexdigest() if scope_adjudication_csv and scope_adjudication_csv.exists() else "",
        "scope_initial_review_sha256": initial_sha,
        "scope_consensus_sha256": consensus_sha,
        "scope_disposition_frozen": scope_disposition_frozen,
        "invalid_or_stale_scope_adjudication_count": invalid_scope_decisions,
        "invalid_initial_scope_review_count": invalid_initial_reviews,
        "applied_reference_amendment_count": len(amendments), "invalid_reference_amendment_count": invalid_amendments,
        "formal_ready": terminal_ready and estimand_ready and scope_disposition_frozen,
        "formal_blocker": "" if terminal_ready and estimand_ready and scope_disposition_frozen else "pending_scope_or_geometry_reference",
    }
    (output_dir / "c1_operational_reference_audit.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    return summary


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--canonical-csv", type=Path, required=True)
    parser.add_argument("--geometry-jsonl", type=Path, required=True)
    parser.add_argument("--inventory-csv", type=Path, required=True)
    parser.add_argument("--gt-export", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--scope-adjudication-csv", type=Path)
    parser.add_argument("--scope-initial-review-csv", type=Path)
    parser.add_argument("--scope-meta-csv", type=Path)
    parser.add_argument("--scope-independence-csv", type=Path)
    parser.add_argument("--scope-outside-csv", type=Path)
    parser.add_argument("--reference-amendment", type=Path)
    parser.add_argument("--formal", action="store_true")
    args = parser.parse_args()
    print(json.dumps(materialize(
        args.canonical_csv, args.geometry_jsonl, args.inventory_csv, args.gt_export, args.output_dir,
        scope_adjudication_csv=args.scope_adjudication_csv,
        scope_initial_review_csv=args.scope_initial_review_csv,
        scope_meta_csv=args.scope_meta_csv,
        scope_independence_csv=args.scope_independence_csv,
        scope_outside_csv=args.scope_outside_csv,
        reference_amendment=args.reference_amendment, formal=args.formal,
    ), indent=2))


if __name__ == "__main__":
    main()
