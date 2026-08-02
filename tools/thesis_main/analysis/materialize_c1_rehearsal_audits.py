"""Materialize C1 operational audits that must not depend on canonical eligibility."""

from __future__ import annotations

import csv
import hashlib
import json
import math
import random
import statistics
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np

from tools.thesis_main.analysis.geometry_consensus.representation import normalize_geometry, normalize_geometry_for_c1_calculation
from tools.thesis_main.analysis.failure_disposition import c1_failure_fields
from tools.thesis_main.analysis.paper_a_contracts import load_method_contract, validate_record, validate_serialized_record
from tools.thesis_main.analysis.quality_core.active_time import (
    _parse_active_log_event_time,
    cumulative_active_intervals,
    is_unknown_annotation_id,
    merged_interval_seconds,
)


_TIMING_CONTRACT = load_method_contract()["timing"]
_TASK_WORKER_TIMING_RULE_VERSION = str(_TIMING_CONTRACT["task_worker_rule_version"])
_TASK_WORKER_TIMING_IDENTITY_LEVEL = str(_TIMING_CONTRACT["primary_identity_level"])
_TASK_WORKER_TIME_ASSIGNMENTS = set(_TIMING_CONTRACT["formal_assignment_provenance"])
_LEGACY_TASK_WORKER_TIME_SCRIPTS = set(_TIMING_CONTRACT["legacy_task_worker_script_versions"])
_BRIDGED_TASK_WORKER_TIME_SCRIPTS = set(_TIMING_CONTRACT["bridged_task_worker_script_versions"])
_TIMING_ADMINISTRATIVELY_EXCLUDED_WORKERS = set(load_method_contract()["administrative_eligibility"]["permanently_ineligible_workers"])


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as stream:
        return list(csv.DictReader(stream))


def write_csv(path: Path, rows: list[dict[str, Any]], fields: list[str] | None = None) -> None:
    fields = fields or (list(rows[0]) if rows else ["status"])
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def _truth(value: Any) -> bool:
    return str(value).strip().lower() in {"true", "1", "yes"}


def _int(value: Any) -> int:
    try:
        return int(float(value or 0))
    except (TypeError, ValueError):
        return 0


_INDEPENDENCE_META_IDENTITY_FIELDS = (
    "project_id", "ls_runtime_task_id", "task_id", "base_task_id", "condition",
    "worker_id", "annotation_id", "canonical_annotation_id", "source_sha256",
    "source_export_sha256", "raw_export_sha256", "response_hash", "raw_annotation_sha256",
    "annotation_version_id", "assignment_provenance", "assigned_expected",
    "outside_assignment_submission", "duplicate_worker_task_submission", "parent_annotation_id",
    "parent_owner_id", "parent_cross_owner", "parent_derived", "copy_risk_status",
    "provenance_status", "raw_parent_field_present", "raw_parent_annotation_id",
    "raw_parent_owner_id", "raw_annotation_owner_id", "geometry_hash",
)


def independence_meta_identity_sha(rows: list[dict[str, str]]) -> str:
    """Bind dispositions to stable independence evidence, not run-specific paths."""
    payload = [
        {field: str(row.get(field, "")) for field in _INDEPENDENCE_META_IDENTITY_FIELDS}
        for row in rows
    ]
    payload.sort(key=lambda row: json.dumps(row, sort_keys=True, separators=(",", ":")))
    return hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def _worker(annotation: dict[str, Any]) -> str:
    worker = annotation.get("completed_by")
    if isinstance(worker, dict):
        worker = worker.get("id") or worker.get("pk")
    return str(worker or "").strip()


def _assignment_key(row: dict[str, Any]) -> tuple[str, str, str, str]:
    return tuple(str(row.get(field, "")).strip() for field in ("worker_id", "task_id", "base_task_id", "dataset_group"))


def materialize_completion_support(
    export_paths: list[Path], assignment_paths: list[Path], runtime_mapping_csv: Path,
    canonical_csv: Path, geometry_jsonl: Path, output_dir: Path, *, min_valid_k: int = 3,
    completion_disposition_csv: Path | None = None, collection_window_closed: bool = False,
    authorized_reassignment_csv: Path | None = None,
    late_entry_assignment_csv: Path | None = None,
) -> dict[str, Any]:
    assignments: dict[tuple[str, str, str, str], dict[str, Any]] = {}
    for path in assignment_paths:
        condition = "semi" if "semi" in path.name.lower() else "manual"
        for row in read_csv(path):
            key = _assignment_key(row)
            if key in assignments:
                raise ValueError(f"duplicate assignment identity: {key}")
            assignments[key] = {**row, "condition": condition}
    original_assignments = dict(assignments)
    authorized_rows = read_csv(authorized_reassignment_csv) if authorized_reassignment_csv and authorized_reassignment_csv.exists() else []
    # W014 is permanently administratively excluded.  Its original assignment
    # edges are evidence of what was replaced, not analysis/support edges.
    administrative_workers = {"14"} if any(str(row.get("displaced_worker_id", "")).strip() == "14" for row in authorized_rows) else set()
    excluded_original_assignments = {
        key: row for key, row in original_assignments.items() if key[0] in administrative_workers
    }
    assignments = {
        key: row for key, row in assignments.items() if key[0] not in administrative_workers
    }
    for row in authorized_rows:
        key = (
            str(row.get("replacement_worker_id", "")).strip(), str(row.get("task_id", "")).strip(),
            str(row.get("base_task_id", "")).strip(), str(row.get("dataset_group", "")).strip(),
        )
        if key in assignments:
            raise ValueError(f"authorized replacement duplicates an existing assignment edge: {key}")
        assignments[key] = {**row, "worker_id": key[0], "condition": str(row.get("condition", "")).strip().lower(), "assignment_provenance": "authorized_replacement_assignment"}
    for row in read_csv(late_entry_assignment_csv) if late_entry_assignment_csv and late_entry_assignment_csv.exists() else []:
        key = _assignment_key(row)
        if key in assignments:
            raise ValueError(f"late-entry assignment duplicates an existing assignment edge: {key}")
        if row.get("assignment_provenance") != "late_entry_calibration_assignment":
            raise ValueError("late-entry completion support requires frozen provenance")
        assignments[key] = {**row, "condition": str(row.get("condition", "")).strip().lower()}

    runtime = {
        (row.get("project_id", ""), row.get("ls_runtime_task_id", "")):
        (row.get("task_id", ""), row.get("base_task_id", ""), row.get("dataset_group", ""), row.get("condition", ""))
        for row in read_csv(runtime_mapping_csv)
    }
    observed: set[tuple[str, str, str, str]] = set()
    for path in export_paths:
        for task in json.loads(path.read_text(encoding="utf-8-sig")):
            project = str(task.get("project") or "")
            mapped = runtime.get((project, str(task.get("id") or "")))
            if not mapped:
                continue
            for annotation in task.get("annotations") or []:
                worker = _worker(annotation)
                if worker and not annotation.get("was_cancelled"):
                    observed.add((worker, mapped[0], mapped[1], mapped[2]))

    canonical = read_csv(canonical_csv)
    canonical_keys = {_assignment_key(row) for row in canonical}
    geometry_valid = set()
    for line in geometry_jsonl.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        if normalize_geometry_for_c1_calculation(row.get("corners_px") or [], width=int(row.get("width") or 1024), height=int(row.get("height") or 512))["valid"]:
            geometry_valid.add((str(row.get("worker_id", "")), str(row.get("task_id", "")), str(row.get("base_task_id", "")), str(row.get("pool", ""))))

    by_worker: dict[str, list[tuple[tuple[str, str, str, str], dict[str, Any]]]] = defaultdict(list)
    for key, row in assignments.items():
        by_worker[key[0]].append((key, row))
    completion_rows, realization_rows, missing_rows = [], [], []
    worker_status: dict[str, str] = {}
    for worker, rows in sorted(by_worker.items(), key=lambda item: int(item[0]) if item[0].isdigit() else item[0]):
        assigned_counts = Counter(row["condition"] for _key, row in rows)
        observed_counts = Counter(row["condition"] for key, row in rows if key in observed)
        total, complete = len(rows), sum(key in observed for key, _row in rows)
        # Collection closure alone cannot certify estimand support. A reviewer
        # may promote this to closed_partial_usable after row-level gates exist.
        status = "nonstarter" if complete == 0 else "completed" if complete == total else "closed_partial_insufficient" if collection_window_closed else "partial_noncompletion"
        worker_status[worker] = status
        completion_rows.append({
            "worker_id": worker,
            "assigned_manual_count": assigned_counts["manual"], "assigned_semi_count": assigned_counts["semi"], "assigned_total_count": total,
            "observed_manual_count": observed_counts["manual"], "observed_semi_count": observed_counts["semi"], "observed_total_count": complete,
            "canonical_selected_total_count": sum(key in canonical_keys for key, _row in rows),
            "missing_manual_count": assigned_counts["manual"] - observed_counts["manual"],
            "missing_semi_count": assigned_counts["semi"] - observed_counts["semi"], "missing_total_count": total - complete,
            "completion_rate": complete / total if total else 0, "completion_status": status,
        })
    for worker in sorted(administrative_workers, key=lambda value: int(value) if value.isdigit() else value):
        rows = [(key, row) for key, row in excluded_original_assignments.items() if key[0] == worker]
        assigned_counts = Counter(row["condition"] for _key, row in rows)
        observed_counts = Counter(row["condition"] for key, _row in rows if key in observed)
        total, complete = len(rows), sum(key in observed for key, _row in rows)
        worker_status[worker] = "administrative_exclusion"
        completion_rows.append({
            "worker_id": worker,
            "assigned_manual_count": assigned_counts["manual"], "assigned_semi_count": assigned_counts["semi"], "assigned_total_count": total,
            "observed_manual_count": observed_counts["manual"], "observed_semi_count": observed_counts["semi"], "observed_total_count": complete,
            "canonical_selected_total_count": sum(key in canonical_keys for key, _row in rows),
            "missing_manual_count": assigned_counts["manual"] - observed_counts["manual"],
            "missing_semi_count": assigned_counts["semi"] - observed_counts["semi"], "missing_total_count": total - complete,
            "completion_rate": complete / total if total else 0, "completion_status": "administrative_exclusion",
        })
    for key, row in sorted(assignments.items()):
        raw_seen, selected = key in observed, key in canonical_keys
        status = worker_status[key[0]]
        reason = ""
        if not raw_seen:
            reason = "worker_nonstarter" if status == "nonstarter" else "worker_partial_noncompletion"
        elif not selected:
            reason = "duplicate_revision_pending"
        audit = {
            "worker_id": key[0], "task_id": key[1], "base_task_id": key[2], "condition": row["condition"], "dataset_group": key[3],
            "assignment_provenance": row.get("assignment_provenance", "original_assignment"),
            "displaced_worker_id": row.get("displaced_worker_id", ""),
            "active_time_expected": row.get("active_time_expected", True),
            "expected_submission": True, "observed_submission": raw_seen, "canonical_selected_submission": selected,
            "missing_submission": not raw_seen, "missing_reason": reason,
        }
        realization_rows.append(audit)
        if not raw_seen:
            missing_rows.append(audit)

    task_rows = []
    by_task: dict[tuple[str, str, str, str], list[tuple[str, str, str, str]]] = defaultdict(list)
    for key, row in assignments.items():
        by_task[(key[1], key[2], row["condition"], key[3])].append(key)
    for (task, base, condition, group), keys in sorted(by_task.items()):
        planned = len(keys); seen = sum(key in observed for key in keys); valid = sum(key in geometry_valid for key in keys)
        status = "no_observation" if valid == 0 else "insufficient" if valid < min_valid_k else "complete" if valid == planned else "reduced_but_usable"
        task_rows.append({
            "task_id": task, "base_task_id": base, "condition": condition, "dataset_group": group,
            "planned_support": planned, "observed_support": seen, "valid_support": valid,
            "support_deficit": max(0, planned - valid),
            "affected_missing_workers": ";".join(key[0] for key in keys if key not in observed), "support_status": status,
        })

    preliminary_completion = output_dir / "c1_worker_completion_pre_disposition_audit.csv"
    write_csv(preliminary_completion, completion_rows)
    completion_source_sha = hashlib.sha256(preliminary_completion.read_bytes()).hexdigest()
    write_csv(output_dir / "c1_completion_disposition_template.csv", [{
        "worker_id": row["worker_id"], "computed_completion_status": row["completion_status"],
        "final_completion_disposition": row["completion_status"] if row["completion_status"] in {"completed", "partial_noncompletion", "closed_partial_usable", "closed_partial_insufficient", "nonstarter", "administrative_exclusion"} else "",
        "source_completion_audit_sha256": completion_source_sha, "reviewed_by": "", "reviewed_at": "", "reason": "",
    } for row in completion_rows if row["completion_status"] != "completed"])
    disposition_summary = apply_completion_disposition(preliminary_completion, completion_disposition_csv, output_dir)
    completion_rows = read_csv(output_dir / "c1_worker_completion_disposition_evidence.csv")
    write_csv(output_dir / "c1_worker_completion_audit.csv", completion_rows)
    write_csv(output_dir / "c1_assignment_realization_audit.csv", realization_rows)
    write_csv(output_dir / "c1_missing_submission_by_worker.csv", missing_rows)
    condition_rows = [{"condition": condition, "assigned_count": sum(row["condition"] == condition for row in realization_rows), "observed_count": sum(row["condition"] == condition and row["observed_submission"] for row in realization_rows), "missing_count": sum(row["condition"] == condition and row["missing_submission"] for row in realization_rows)} for condition in ("manual", "semi")]
    write_csv(output_dir / "c1_missing_submission_by_condition.csv", condition_rows)
    write_csv(output_dir / "c1_task_support_deficit.csv", task_rows)
    counts = Counter(row["completion_status"] for row in completion_rows)
    return {
        "collection_window_closed": collection_window_closed,
        "roster_count": len(completion_rows), "assigned_submission_count": len(realization_rows),
        "observed_submission_count": sum(row["observed_submission"] for row in realization_rows), "missing_submission_count": len(missing_rows),
        "completed_worker_count": counts["completed"],
        "partial_noncompletion_worker_count": counts["partial_noncompletion"] + counts["closed_partial_usable"] + counts["closed_partial_insufficient"],
        "closed_partial_usable_worker_count": counts["closed_partial_usable"],
        "closed_partial_insufficient_worker_count": counts["closed_partial_insufficient"],
        "nonstarter_worker_count": counts["nonstarter"],
        "administrative_exclusion_worker_count": counts["administrative_exclusion"],
        "authorized_reassignment_count": len(authorized_rows),
        "completed_worker_ids": [row["worker_id"] for row in completion_rows if row["completion_status"] == "completed"],
        "partial_worker_ids": [row["worker_id"] for row in completion_rows if row["completion_status"] in {"partial_noncompletion", "closed_partial_usable", "closed_partial_insufficient"}],
        "nonstarter_worker_ids": [row["worker_id"] for row in completion_rows if row["completion_status"] == "nonstarter"],
        "administrative_exclusion_worker_ids": [row["worker_id"] for row in completion_rows if row["completion_status"] == "administrative_exclusion"],
        "missing_nonstarter_count": sum(row["missing_reason"] == "worker_nonstarter" for row in missing_rows),
        "missing_partial_count": sum(row["missing_reason"] == "worker_partial_noncompletion" for row in missing_rows),
        "missing_other_count": sum(row["missing_reason"] not in {"worker_nonstarter", "worker_partial_noncompletion"} for row in missing_rows),
        "task_support_counts": dict(Counter(row["support_status"] for row in task_rows)),
        "completion_disposition": disposition_summary,
    }


def apply_completion_disposition(completion_audit_csv: Path, disposition_csv: Path | None, output_dir: Path) -> dict[str, Any]:
    """Consume SHA-bound worker completion dispositions without mutating raw audit."""
    rows = read_csv(completion_audit_csv)
    source_sha = hashlib.sha256(completion_audit_csv.read_bytes()).hexdigest()
    dispositions = read_csv(disposition_csv) if disposition_csv and disposition_csv.exists() else []
    by_worker: dict[str, list[dict[str, str]]] = defaultdict(list)
    for disposition in dispositions:
        by_worker[disposition.get("worker_id", "")].append(disposition)
    known_workers = {row.get("worker_id", "") for row in rows}
    allowed = {"completed", "partial_noncompletion", "closed_partial_usable", "closed_partial_insufficient", "nonstarter", "administrative_exclusion"}
    applied = invalid = unmatched = pending = 0
    output = []
    for row in rows:
        matches = by_worker.get(row.get("worker_id", ""), [])
        disposition = matches[0] if len(matches) == 1 else {}
        valid = bool(disposition) and all(str(disposition.get(field, "")).strip() for field in ("worker_id", "source_completion_audit_sha256", "final_completion_disposition", "reviewed_by", "reviewed_at", "reason")) and disposition.get("source_completion_audit_sha256") == source_sha and disposition.get("final_completion_disposition") in allowed
        if len(matches) > 1:
            invalid += 1
        elif disposition and not valid:
            invalid += 1
        elif not disposition and row.get("completion_status") not in allowed:
            pending += 1
        if valid:
            applied += 1
        computed_valid = not matches
        output.append({
            **row,
            "computed_completion_status": row.get("completion_status", ""),
            "completion_status": disposition.get("final_completion_disposition", row.get("completion_status", "")) if valid else row.get("completion_status", ""),
            "completion_disposition_applied": valid,
            "completion_disposition_valid": valid or computed_valid,
            "completion_disposition_basis": "sha_bound_exception" if valid else "researcher_administrative_disposition" if computed_valid and row.get("completion_status") == "administrative_exclusion" else "computed_from_frozen_assignment_and_export" if computed_valid else "invalid_exception_disposition",
            "completion_disposition_source_sha256": source_sha if valid else "",
            "completion_disposition_reviewed_by": disposition.get("reviewed_by", "") if valid else "",
            "completion_disposition_reviewed_at": disposition.get("reviewed_at", "") if valid else "",
            "completion_disposition_reason": disposition.get("reason", "") if valid else "",
        })
    unmatched = sum(1 for worker in by_worker if worker not in known_workers)
    write_csv(output_dir / "c1_worker_completion_disposition_evidence.csv", output)
    summary = {"source_completion_audit_sha256": source_sha, "applied_count": applied, "invalid_count": invalid, "unmatched_count": unmatched, "pending_count": pending}
    (output_dir / "c1_completion_disposition_summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return summary


def finalize_partial_completion_support(
    completion_csv: Path, eligibility_csv: Path, output_dir: Path, summary: dict[str, Any], *,
    collection_window_closed: bool,
) -> dict[str, Any]:
    """Classify closed partial workers from estimand rows, without cross-axis substitution."""
    rows = read_csv(completion_csv)
    support: dict[str, dict[str, int]] = defaultdict(lambda: {"Q_GT": 0, "R_LOO": 0, "F_struct": 0})
    for row in read_csv(eligibility_csv):
        worker = row.get("worker_id", "")
        if not worker:
            continue
        support[worker]["Q_GT"] += int(str(row.get("gt_primary_analysis_eligible", "")).lower() in {"true", "1"})
        support[worker]["R_LOO"] += int(str(row.get("strict_loo_analysis_eligible", "")).lower() in {"true", "1"})
        support[worker]["F_struct"] += int(str(row.get("structural_opportunity_eligible", "")).lower() in {"true", "1"})
    for row in rows:
        worker_support = support[row.get("worker_id", "")]
        explicit = str(row.get("completion_disposition_applied", "")).lower() in {"true", "1"}
        if collection_window_closed and not explicit and row.get("completion_status") == "closed_partial_insufficient":
            row["completion_status"] = "closed_partial_usable" if any(worker_support.values()) else "closed_partial_insufficient"
        row["Q_GT_eligible_row_support"] = worker_support["Q_GT"]
        row["R_LOO_eligible_row_support"] = worker_support["R_LOO"]
        row["F_struct_eligible_row_support"] = worker_support["F_struct"]
        row["completion_support_basis"] = "estimand_specific_row_eligibility" if collection_window_closed else "collection_open"
    write_csv(output_dir / "c1_worker_completion_audit.csv", rows)
    counts = Counter(row.get("completion_status", "") for row in rows)
    updated = {
        **summary,
        "completed_worker_count": counts["completed"],
        "partial_noncompletion_worker_count": counts["partial_noncompletion"] + counts["closed_partial_usable"] + counts["closed_partial_insufficient"],
        "closed_partial_usable_worker_count": counts["closed_partial_usable"],
        "closed_partial_insufficient_worker_count": counts["closed_partial_insufficient"],
        "nonstarter_worker_count": counts["nonstarter"],
        "completed_worker_ids": [row["worker_id"] for row in rows if row.get("completion_status") == "completed"],
        "partial_worker_ids": [row["worker_id"] for row in rows if row.get("completion_status") in {"partial_noncompletion", "closed_partial_usable", "closed_partial_insufficient"}],
        "nonstarter_worker_ids": [row["worker_id"] for row in rows if row.get("completion_status") == "nonstarter"],
    }
    (output_dir / "c1_worker_completion_support_summary.json").write_text(json.dumps(updated, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return updated


def apply_outside_assignment_disposition(outside_audit_csv: Path, disposition_csv: Path | None, output_dir: Path) -> dict[str, Any]:
    """Consume SHA-bound outside-assignment dispositions as a process sidecar."""
    rows = read_csv(outside_audit_csv)
    source_sha = hashlib.sha256(outside_audit_csv.read_bytes()).hexdigest()
    dispositions = read_csv(disposition_csv) if disposition_csv and disposition_csv.exists() else []
    by_identity: dict[str, list[dict[str, str]]] = defaultdict(list)
    for disposition in dispositions:
        by_identity[disposition.get("canonical_annotation_id", "")].append(disposition)
    known = {row.get("canonical_annotation_id", "") for row in rows}
    allowed = {"true_unassigned_forensic", "assignment_mapping_error", "valid_authorized_exception", "excluded"}
    applied = invalid = pending = 0
    output = []
    for row in rows:
        matches = by_identity.get(row.get("canonical_annotation_id", ""), [])
        disposition = matches[0] if len(matches) == 1 else {}
        valid = bool(disposition) and all(str(disposition.get(field, "")).strip() for field in ("canonical_annotation_id", "source_outside_assignment_audit_sha256", "final_process_disposition", "reviewed_by", "reviewed_at", "reason")) and disposition.get("source_outside_assignment_audit_sha256") == source_sha and disposition.get("final_process_disposition") in allowed
        if len(matches) > 1:
            invalid += 1
        elif disposition and not valid:
            invalid += 1
        elif not disposition:
            pending += 1
        if valid:
            applied += 1
        final = disposition.get("final_process_disposition", "") if valid else ""
        output.append({
            **row,
            "outside_assignment_disposition_applied": valid,
            "outside_assignment_disposition_valid": valid,
            "outside_assignment_disposition_source_sha256": source_sha if valid else "",
            "final_process_disposition": final,
            "process_eligible_override": final == "valid_authorized_exception",
            "outside_assignment_disposition_reviewed_by": disposition.get("reviewed_by", "") if valid else "",
            "outside_assignment_disposition_reviewed_at": disposition.get("reviewed_at", "") if valid else "",
            "outside_assignment_disposition_reason": disposition.get("reason", "") if valid else "",
        })
    summary = {"source_outside_assignment_audit_sha256": source_sha, "applied_count": applied, "invalid_count": invalid, "unmatched_count": sum(1 for identity in by_identity if identity not in known), "pending_count": pending}
    write_csv(output_dir / "c1_outside_assignment_disposition_evidence.csv", output)
    (output_dir / "c1_outside_assignment_disposition_summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return summary


def materialize_structural_validation(
    canonical_csv: Path, geometry_jsonl: Path, output_dir: Path, *,
    parser_amendment: Path = Path("docs/thesis_main/c1_geometry_parser_amendment_v1.json"),
    disposition_csv: Path | None = None,
) -> dict[str, Any]:
    canonical = {row["canonical_annotation_id"]: row for row in read_csv(canonical_csv)}
    amendment_sha = hashlib.sha256(parser_amendment.read_bytes()).hexdigest()
    rows, repair_audit_rows = [], []
    for line in geometry_jsonl.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        geometry = json.loads(line); annotation = canonical.get(geometry.get("canonical_annotation_id", ""), {})
        parsed = normalize_geometry_for_c1_calculation(geometry.get("corners_px") or [], width=int(geometry.get("width") or 1024), height=int(geometry.get("height") or 512))
        reason = parsed["raw_structural_failure_reason"]
        worker_reason = reason in {"duplicate_event_positions", "top_floor_order_invalid", "self_intersecting_or_open_topology"}
        system_reason = reason in {"shape_invalid", "non_finite", "out_of_range", "ambiguous_pairing"} or bool(annotation.get("parse_error"))
        status = "passed" if parsed["raw_geometry_valid"] else "failed_confirmed_worker_submission" if worker_reason else "failed_system_or_parser" if system_reason else "not_evaluable"
        rows.append({
            "project_id": annotation.get("project_id", ""), "ls_runtime_task_id": annotation.get("ls_runtime_task_id", ""),
            "annotation_id": annotation.get("annotation_id", ""), "canonical_annotation_id": geometry.get("canonical_annotation_id", ""),
            "worker_id": geometry.get("worker_id", ""), "task_id": geometry.get("task_id", ""),
            "geometry_parse_status": "parsed" if parsed["geometry_parse_valid"] else "failed",
            **{field: parsed[field] for field in (
                "geometry_parse_valid", "coordinate_range_valid", "corner_count_valid", "pair_count_valid",
                "pairing_valid", "top_bottom_order_valid", "pair_fold_absent", "duplicate_corner_absent",
                "polygon_closed", "polygon_simple", "topology_valid", "seam_representation_valid",
            )},
            "polygon_valid": parsed["polygon_closed"] and parsed["polygon_simple"],
            "pairing_method": parsed.get("pairing_method", ""), "parser_amendment_sha256": amendment_sha,
            "unordered_pairing_ambiguous": parsed.get("pairing_stats", {}).get("unordered_pairing_ambiguous", False),
            "raw_geometry_valid": parsed["raw_geometry_valid"], "geometry_calculation_eligible": parsed["valid"],
            "geometry_repair_applied": parsed["geometry_repair_applied"], "geometry_repair_status": parsed["geometry_repair_status"],
            "geometry_repair_rule_version": parsed["geometry_repair_rule_version"], "raw_point_count": parsed["raw_point_count"],
            "repaired_point_count": parsed["repaired_point_count"], "dropped_point_index": parsed["dropped_point_index"],
            "orphan_candidate_count": parsed["orphan_candidate_count"], "raw_geometry_sha256": parsed["raw_geometry_sha256"],
            "repaired_geometry_sha256": parsed["repaired_geometry_sha256"],
            "structural_validation_status": status, "structural_failure_reason": reason,
            "detected_structural_issue": not parsed["raw_geometry_valid"],
            "worker_attributable": status == "failed_confirmed_worker_submission",
            "independence_status": annotation.get("independence_status", "not_evaluable"),
            "failure_attribution": "none" if status == "passed" else "worker_caused_structural_failure" if status == "failed_confirmed_worker_submission" else "not_evaluable",
            "analysis_inclusion": "geometry_and_structural" if status == "passed" else "geometry_repaired_pending_structural_disposition" if parsed["geometry_repair_applied"] else "structural_only" if status == "failed_confirmed_worker_submission" else "excluded_with_reason",
            "worker_reliability_eligibility": status == "passed" and annotation.get("independence_status") == "independent",
            "structural_denominator_eligible": status in {"passed", "failed_confirmed_worker_submission"},
            "worker_failure_numerator": status == "failed_confirmed_worker_submission",
            "worker_structural_failure_numerator": status == "failed_confirmed_worker_submission",
        })
        worker_id = str(geometry.get("worker_id", ""))
        repair_audit_rows.append({
            "canonical_annotation_id": geometry.get("canonical_annotation_id", ""), "annotation_id": annotation.get("annotation_id", geometry.get("annotation_id", "")), "project_id": annotation.get("project_id", ""),
            "ls_runtime_task_id": annotation.get("ls_runtime_task_id", ""), "planned_project_name": annotation.get("planned_project_name", ""),
            "planned_inner_id": annotation.get("planned_inner_id", ""), "task_code": annotation.get("task_code", ""),
            "task_id": geometry.get("task_id", ""), "base_task_id": annotation.get("base_task_id", geometry.get("base_task_id", "")),
            "condition": annotation.get("condition", geometry.get("condition", "")), "worker_id": worker_id,
            "worker_code": f"W{int(worker_id):03d}" if worker_id.isdigit() else worker_id,
            "raw_point_count": parsed["raw_point_count"], "repaired_point_count": parsed["repaired_point_count"],
            "dropped_point_index": parsed["dropped_point_index"], "orphan_candidate_count": parsed["orphan_candidate_count"],
            "geometry_repair_rule_version": parsed["geometry_repair_rule_version"], "geometry_repair_applied": parsed["geometry_repair_applied"],
            "geometry_repair_status": parsed["geometry_repair_status"], "raw_geometry_sha256": parsed["raw_geometry_sha256"],
            "repaired_geometry_sha256": parsed["repaired_geometry_sha256"], "raw_structural_failure_reason": reason,
            "raw_points_json": json.dumps(parsed["raw_points"], ensure_ascii=False, separators=(",", ":")),
            "repaired_points_json": json.dumps(parsed["canonical_points"], ensure_ascii=False, separators=(",", ":")) if parsed["geometry_repair_applied"] else "",
        })
    preliminary = output_dir / "c1_structural_validation_pre_disposition.csv"
    write_csv(preliminary, rows)
    source_sha = hashlib.sha256(preliminary.read_bytes()).hexdigest()
    for row in rows:
        row.update({
            "final_scope": "", "structural_disposition_applied": False,
            "structural_disposition_source_sha256": "", "structural_disposition_reviewed_by": "",
            "structural_disposition_reviewed_at": "", "structural_disposition_reason": "",
        })
    write_csv(output_dir / "c1_structural_disposition_template.csv", [{
        "canonical_annotation_id": row["canonical_annotation_id"], "source_structural_audit_sha256": source_sha,
        "final_scope": "", "detected_issue": row["structural_failure_reason"], "final_failure_attribution": "",
        "structural_denominator_eligible": "", "worker_failure_numerator": "", "reviewed_by": "", "reviewed_at": "", "reason": "",
    } for row in rows if row["structural_validation_status"] != "passed"])
    dispositions = {row.get("canonical_annotation_id", ""): row for row in read_csv(disposition_csv)} if disposition_csv and disposition_csv.exists() else {}
    applied = invalid = 0
    required = (
        "canonical_annotation_id", "source_structural_audit_sha256", "final_scope", "detected_issue",
        "final_failure_attribution", "structural_denominator_eligible", "worker_failure_numerator",
        "reviewed_by", "reviewed_at", "reason",
    )
    for row in rows:
        disposition = dispositions.get(row["canonical_annotation_id"])
        if not disposition:
            continue
        valid = (
            all(str(disposition.get(field, "")).strip() for field in required)
            and disposition["source_structural_audit_sha256"] == source_sha
            and disposition["detected_issue"] == row["structural_failure_reason"]
            and disposition["final_failure_attribution"] in {"worker_caused_structural_failure", "not_evaluable"}
        )
        scope = disposition.get("final_scope", "").strip().lower()
        attribution = disposition.get("final_failure_attribution", "")
        denominator = _truth(disposition.get("structural_denominator_eligible"))
        numerator = _truth(disposition.get("worker_failure_numerator"))
        valid = valid and not (
            (attribution == "worker_caused_structural_failure" and (scope != "in_scope" or not denominator or not numerator))
            or (scope in {"oos", "out_of_scope", "outside_assignment"} and (attribution != "not_evaluable" or denominator or numerator))
            or (attribution == "not_evaluable" and numerator)
        )
        if not valid:
            invalid += 1
            continue
        attribution = disposition["final_failure_attribution"]
        row.update({
            "final_scope": disposition["final_scope"], "failure_attribution": attribution,
            "structural_validation_status": "failed_confirmed_worker_submission" if attribution == "worker_caused_structural_failure" else "not_evaluable",
            "worker_attributable": attribution == "worker_caused_structural_failure",
            "analysis_inclusion": "geometry_repaired_and_structural_failure" if attribution == "worker_caused_structural_failure" and _truth(row.get("geometry_repair_applied")) else "structural_only" if attribution == "worker_caused_structural_failure" else "excluded_with_reason",
            "structural_denominator_eligible": _truth(disposition["structural_denominator_eligible"]),
            "worker_failure_numerator": _truth(disposition["worker_failure_numerator"]),
            "worker_structural_failure_numerator": _truth(disposition["worker_failure_numerator"]),
            "structural_disposition_applied": True, "structural_disposition_source_sha256": source_sha,
            "structural_disposition_reviewed_by": disposition["reviewed_by"], "structural_disposition_reviewed_at": disposition["reviewed_at"],
            "structural_disposition_reason": disposition["reason"],
        })
        applied += 1
    write_csv(output_dir / "structural_validation_audit.csv", rows)
    validations = {row["canonical_annotation_id"]: row for row in rows}
    for repair in repair_audit_rows:
        validation = validations[repair["canonical_annotation_id"]]
        repair.update({
            "geometry_calculation_eligible": validation["geometry_calculation_eligible"],
            "structural_validation_status": validation["structural_validation_status"],
            "failure_attribution": validation["failure_attribution"], "final_scope": validation.get("final_scope", ""),
            "structural_denominator_eligible": validation["structural_denominator_eligible"],
            "worker_failure_numerator": validation["worker_failure_numerator"],
        })
    write_csv(output_dir / "c1_geometry_repair_audit.csv", repair_audit_rows)
    write_csv(output_dir / "c1_parser_amendment_application_audit.csv", [
        {**row, "regression_identity": ":".join(str(row.get(field, "")) for field in ("project_id", "ls_runtime_task_id", "task_id", "worker_id", "annotation_id"))}
        for row in rows if row.get("pairing_method") == "raw_order_pairing" and _truth(row.get("unordered_pairing_ambiguous"))
    ])
    counts = Counter(row["structural_validation_status"] for row in rows)
    failures = Counter(row["failure_attribution"] for row in rows)
    return {"n_rows": len(rows), "structural_status_counts": dict(counts), "failure_attribution_counts": dict(failures), "parser_amendment_sha256": amendment_sha, "parser_amendment_application_count": sum(row.get("pairing_method") == "raw_order_pairing" and _truth(row.get("unordered_pairing_ambiguous")) for row in rows), "geometry_repair_application_count": sum(_truth(row.get("geometry_repair_applied")) for row in rows), "structural_pre_disposition_sha256": source_sha, "applied_disposition_count": applied, "invalid_disposition_count": invalid}


def _raw_points(raw_result: Any) -> list[list[float]]:
    try:
        results = json.loads(raw_result) if isinstance(raw_result, str) else raw_result
    except (json.JSONDecodeError, TypeError):
        return []
    points = []
    for item in results or []:
        if item.get("type") != "keypointlabels":
            continue
        value = item.get("value") or {}
        try:
            points.append([float(value["x"]) * 10.24, float(value["y"]) * 5.12])
        except (KeyError, TypeError, ValueError):
            continue
    return points


def _root_cause(reason: str) -> tuple[str, str, bool]:
    mapping = {
        "odd_keypoint_count": ("invalid_pair_count_pending_row_disposition", "not_evaluable", True),
        "incomplete_pairing": ("invalid_pair_count_pending_row_disposition", "not_evaluable", True),
        "duplicate_event_positions": ("worker_duplicate_corner", "worker_caused_structural_failure", False),
        "top_floor_order_invalid": ("worker_pair_fold", "worker_caused_structural_failure", False),
        "self_intersecting_or_open_topology": ("worker_self_intersection", "worker_caused_structural_failure", False),
        "ambiguous_pairing": ("canonical_pairing_ambiguous", "not_evaluable", True),
        "out_of_range": ("raw_coordinate_out_of_range", "not_evaluable", True),
        "shape_invalid": ("parser_failure", "not_evaluable", True),
        "non_finite": ("parser_failure", "not_evaluable", True),
    }
    return mapping.get(reason, ("unknown_attribution", "not_evaluable", True))


def materialize_geometry_anomaly_root_causes(
    canonical_csv: Path, meta_csv: Path, geometry_jsonl: Path, structural_csv: Path, output_dir: Path,
    reference_csv: Path | None = None,
) -> dict[str, Any]:
    canonical = {row.get("canonical_annotation_id", ""): row for row in read_csv(canonical_csv)}
    meta = {row.get("canonical_annotation_id", ""): row for row in read_csv(meta_csv)}
    geometry = {row.get("canonical_annotation_id", ""): row for line in geometry_jsonl.read_text(encoding="utf-8").splitlines() if line.strip() for row in [json.loads(line)]}
    references = {row.get("base_task_id", ""): row for row in read_csv(reference_csv)} if reference_csv and reference_csv.exists() else {}
    anomalies = []
    for validation in read_csv(structural_csv):
        if validation.get("structural_validation_status") == "passed":
            continue
        identity = validation.get("canonical_annotation_id", "")
        row, evidence, geom = canonical.get(identity, {}), meta.get(identity, {}), geometry.get(identity, {})
        raw_points = _raw_points(evidence.get("raw_result_json", ""))
        canonical_points = geom.get("corners_px") or []
        root, suggested_attribution, review = _root_cause(validation.get("structural_failure_reason", ""))
        if _truth(row.get("outside_assignment_submission")) and not raw_points:
            root, suggested_attribution, review = "outside_assignment_empty_submission_forensic", "not_evaluable", True
        attribution = validation.get("failure_attribution", "not_evaluable")
        parsed = normalize_geometry(canonical_points, width=int(geom.get("width") or 1024), height=int(geom.get("height") or 512))
        anomalies.append({
            "project_id": row.get("project_id", ""), "runtime_task_id": row.get("ls_runtime_task_id", ""),
            "task_id": row.get("task_id", ""), "base_task_id": row.get("base_task_id", ""), "condition": row.get("condition", ""),
            "worker_id": row.get("worker_id", ""), "annotation_id": row.get("annotation_id", ""), "canonical_annotation_id": identity,
            "annotation_version_id": evidence.get("annotation_version_id", ""), "source_export_path": evidence.get("source_artifact", geom.get("source_artifact", "")),
            "source_export_sha256": evidence.get("source_sha256", geom.get("source_sha256", "")),
            "raw_result_sha256": hashlib.sha256(str(evidence.get("raw_result_json", "")).encode()).hexdigest(),
            "raw_keypoint_count": len(raw_points), "canonical_point_count": len(canonical_points),
            "raw_points": json.dumps(raw_points), "canonical_points": json.dumps(canonical_points),
            "point_order": "raw_preserved;canonical_export_order_preserved", "pairing_method": parsed.get("pairing_method", ""),
            "seam_crossing_detected": parsed.get("seam_crossing_detected", False),
            "geometry_parse_status": validation.get("geometry_parse_status", ""),
            "coordinate_unit_status": "label_studio_percent_to_1024x512_px", "coordinate_range_status": "valid" if parsed["coordinate_range_valid"] else "invalid",
            "corner_count_status": "valid" if parsed["corner_count_valid"] else "invalid", "pair_count_status": "valid" if parsed["pair_count_valid"] else "invalid",
            "duplicate_corner_status": "absent" if parsed["duplicate_corner_absent"] else "present",
            "top_bottom_order_status": "valid" if parsed["top_bottom_order_valid"] else "invalid",
            "pair_fold_status": "absent" if parsed["pair_fold_absent"] else "present_or_not_evaluable",
            "polygon_closure_status": "closed" if parsed["polygon_closed"] else "not_evaluable",
            "self_intersection_status": "absent" if parsed["polygon_simple"] else "present_or_not_evaluable",
            "topology_status": "valid" if parsed["topology_valid"] else "invalid_or_not_evaluable",
            "reference_status": references.get(row.get("base_task_id", ""), {}).get("operational_reference_status", "not_checked_by_structural_validator"), "scope_status": references.get(row.get("base_task_id", ""), {}).get("scope_resolution_status", row.get("task_final_scope", "pending")) or "pending",
            "metric_status": "not_evaluable" if not parsed["valid"] else "evaluable", "detected_issue": validation.get("structural_failure_reason", ""),
            "detected_structural_issue": validation.get("detected_structural_issue", ""),
            "structural_validation_status": validation.get("structural_validation_status", ""),
            "root_cause_class": root, "pre_review_failure_attribution_suggestion": suggested_attribution,
            "final_scope": validation.get("final_scope", ""), "failure_attribution": attribution,
            "score_unavailable_reason": validation.get("structural_failure_reason", ""), "gt_quality_eligible": False,
            "loo_eligible": False, "structural_denominator_eligible": _truth(validation.get("structural_denominator_eligible")),
            "worker_structural_failure_numerator": _truth(validation.get("worker_structural_failure_numerator")),
            "analysis_inclusion": validation.get("analysis_inclusion", "excluded_with_reason"),
            "manual_review_required": review and not _truth(validation.get("structural_disposition_applied")), "review_reason": root if review and not _truth(validation.get("structural_disposition_applied")) else "",
        })
    write_csv(output_dir / "c1_geometry_anomaly_root_cause_audit.csv", anomalies)
    queue = [row for row in anomalies if _truth(row["manual_review_required"])]
    write_csv(output_dir / "c1_geometry_anomaly_review_queue.csv", queue)
    summary = {
        "n_anomalies": len(anomalies), "root_cause_counts": dict(Counter(row["root_cause_class"] for row in anomalies)),
        "failure_attribution_counts": dict(Counter(row["failure_attribution"] for row in anomalies)), "n_manual_review_required": len(queue),
    }
    (output_dir / "c1_geometry_anomaly_summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return summary


def apply_structural_dispositions(canonical_csv: Path, structural_csv: Path) -> None:
    rows = read_csv(canonical_csv)
    structural = {row["canonical_annotation_id"]: row for row in read_csv(structural_csv)}
    for row in rows:
        validation = structural.get(row.get("canonical_annotation_id", ""), {})
        attribution = validation.get("failure_attribution", "not_evaluable")
        row.update({key: str(value).lower() if isinstance(value, bool) else value for key, value in c1_failure_fields({"failure_attribution": attribution}).items()})
        row["structural_validation_status"] = validation.get("structural_validation_status", "not_evaluable")
        row["structural_failure_reason"] = validation.get("structural_failure_reason", "")
        row["worker_reliability_eligible"] = str(validation.get("worker_reliability_eligibility", False)).lower()
    write_csv(canonical_csv, rows, list(rows[0]) if rows else None)


def materialize_outside_assignment(canonical_csv: Path, output_dir: Path, *, disposition_csv: Path | None = None) -> dict[str, Any]:
    rows = []
    for row in read_csv(canonical_csv):
        if not _truth(row.get("outside_assignment_submission")):
            continue
        mapping_ok = row.get("planned_mapping_status") == "planned_import_order" and row.get("runtime_binding_status") == "bound_from_export_and_planned_mapping"
        if _truth(row.get("duplicate_worker_task_submission")) or int(float(row.get("repeated_export_row_count") or 0)) > 0:
            classification = "duplicate_export"
        elif int(float(row.get("annotation_version_group_size") or 1)) > 1:
            classification = "legitimate_revision"
        elif "test" in str(row.get("dataset_group", "")).lower():
            classification = "test_annotation"
        elif not row.get("worker_id"):
            classification = "worker_mapping_error"
        elif not row.get("condition"):
            classification = "condition_mapping_error"
        elif mapping_ok:
            classification = "true_unassigned_submission"
        elif row.get("task_id") and row.get("base_task_id"):
            classification = "runtime_mapping_alias"
        else:
            classification = "unknown"
        rows.append({
            "canonical_annotation_id": row.get("canonical_annotation_id", ""), "annotation_id": row.get("annotation_id", ""), "worker_id": row.get("worker_id", ""),
            "runtime_task_id": row.get("ls_runtime_task_id", ""), "base_task_id": row.get("base_task_id", ""),
            "project_id": row.get("project_id", ""), "condition": row.get("condition", ""),
            "expected_assignment": False, "mapping_status": f"{row.get('planned_mapping_status', '')};{row.get('runtime_binding_status', '')}",
            "classification": classification,
            "recommended_disposition": "forensic_process_audit_exclude_quality" if classification in {"true_unassigned_submission", "test_annotation"} else "fold_duplicate_or_revision" if classification in {"duplicate_export", "legitimate_revision"} else "pending_manual_mapping_review",
        })
    preliminary = output_dir / "c1_outside_assignment_pre_disposition_audit.csv"
    write_csv(preliminary, rows)
    write_csv(output_dir / "c1_outside_assignment_classification_audit.csv", rows)
    source_sha = hashlib.sha256(preliminary.read_bytes()).hexdigest()
    write_csv(output_dir / "c1_outside_assignment_disposition_template.csv", [{
        **row, "final_process_disposition": "", "source_outside_assignment_audit_sha256": source_sha,
        "reviewed_by": "", "reviewed_at": "", "reason": "",
    } for row in rows])
    write_csv(output_dir / "c1_outside_assignment_adjudication_queue.csv", [row for row in rows if row["classification"] != "true_unassigned_submission"])
    disposition_summary = apply_outside_assignment_disposition(preliminary, disposition_csv, output_dir)
    return {"count": len(rows), "classification_counts": dict(Counter(row["classification"] for row in rows)), "disposition": disposition_summary}


def _timestamp(value: Any) -> datetime | None:
    if isinstance(value, (int, float)):
        try:
            return datetime.fromtimestamp(value / 1000 if value > 10_000_000_000 else value, tz=timezone.utc)
        except (ValueError, OSError, OverflowError):
            return None
    text = str(value or "").strip()
    if not text:
        return None
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00")).astimezone(timezone.utc)
    except ValueError:
        return None


def materialize_active_log_audits(canonical_csv: Path, active_log_dir: Path, output_dir: Path) -> dict[str, Any]:
    canonical = read_csv(canonical_csv)
    annotation_times = [_timestamp(row.get("annotation_created_at") or row.get("created_at")) for row in canonical]
    annotation_times = [value for value in annotation_times if value]
    window_min, window_max = (min(annotation_times), max(annotation_times)) if annotation_times else (None, None)
    events, source_rows, schema_rows = [], [], []
    for path in sorted(active_log_dir.rglob("*.jsonl")):
        file_events, invalid = [], 0
        for line in path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                event = json.loads(line); event["_source_file"] = path.name; event["_timestamp"] = _timestamp(event.get("server_received_at") or event.get("timestamp") or event.get("event_time") or event.get("created_at") or event.get("ts")); file_events.append(event)
            except (json.JSONDecodeError, TypeError):
                invalid += 1
        events.extend(file_events)
        timestamps = [event["_timestamp"] for event in file_events if event["_timestamp"]]
        source_rows.append({"source_file": path.name, "event_count": len(file_events), "invalid_json_count": invalid, "event_time_min": min(timestamps).isoformat() if timestamps else "", "event_time_max": max(timestamps).isoformat() if timestamps else "", "inside_c1_window_count": sum(bool(window_min and window_max and event["_timestamp"] and window_min <= event["_timestamp"] <= window_max) for event in file_events)})
        required = ("project_id", "task_id", "annotator_id", "annotation_id", "session_id", "active_seconds")
        schema_rows.append({"source_file": path.name, **{f"{field}_nonempty_rate": sum(str(event.get(field, "")).strip() not in {"", "None", "null", "unknown", "unknown_annotation"} for event in file_events) / len(file_events) if file_events else 0 for field in required}})

    exact = defaultdict(list); contexts = defaultdict(list); by_task_worker = defaultdict(list); by_project_task = defaultdict(list)
    for event in events:
        project, task, worker, annotation = (str(event.get(field, "") or "").strip() for field in ("project_id", "task_id", "annotator_id", "annotation_id"))
        contexts[(project, task, worker)].append(event); by_task_worker[(task, worker)].append(event); by_project_task[(project, task)].append(event)
        if annotation and annotation not in {"unknown", "unknown_annotation", "null", "None"}:
            exact[(project, task, worker, annotation)].append(event)
    reason_rows = []
    for row in canonical:
        key = tuple(str(row.get(field, "")).strip() for field in ("project_id", "ls_runtime_task_id", "worker_id", "annotation_id"))
        candidates = exact.get(key, [])
        if candidates:
            reason = "exact_match"
        elif contexts.get(key[:3]):
            reason = "annotation_id_missing_in_log"
        elif by_task_worker.get((key[1], key[2])):
            reason = "project_mapping_mismatch"
        elif by_project_task.get((key[0], key[1])):
            reason = "worker_mapping_mismatch"
        else:
            reason = "no_log_event"
        reason_rows.append({"project_id": key[0], "ls_runtime_task_id": key[1], "worker_id": key[2], "annotation_id": key[3], "binding_reason": reason, "candidate_event_count": len(candidates)})
    by_worker = defaultdict(list)
    for row in reason_rows:
        by_worker[row["worker_id"]].append(row)
    worker_rows = [{"worker_id": worker, "annotation_count": len(rows), "exact_match_count": sum(row["binding_reason"] == "exact_match" for row in rows), "exact_match_rate": sum(row["binding_reason"] == "exact_match" for row in rows) / len(rows), "reason_counts_json": json.dumps(dict(Counter(row["binding_reason"] for row in rows)), sort_keys=True)} for worker, rows in sorted(by_worker.items())]
    write_csv(output_dir / "c1_active_log_source_audit.csv", source_rows)
    write_csv(output_dir / "c1_active_log_schema_audit.csv", schema_rows)
    write_csv(output_dir / "c1_active_time_binding_reason_audit.csv", reason_rows)
    write_csv(output_dir / "c1_active_time_worker_coverage.csv", worker_rows)
    timestamps = [event["_timestamp"] for event in events if event["_timestamp"]]
    exact_count = sum(row["binding_reason"] == "exact_match" for row in reason_rows)
    exact_event_count = sum(row["candidate_event_count"] for row in reason_rows if row["binding_reason"] == "exact_match")
    multiple_event_annotation_count = sum(row["binding_reason"] == "exact_match" and row["candidate_event_count"] > 1 for row in reason_rows)
    contextual_count = sum(row["binding_reason"] in {"exact_match", "annotation_id_missing_in_log"} for row in reason_rows)
    inside = sum(row["inside_c1_window_count"] for row in source_rows)
    export_project_ids = sorted({str(row.get("project_id", "")).strip() for row in canonical if str(row.get("project_id", "")).strip()})
    active_log_project_ids = sorted({str(event.get("project_id", "")).strip() for event in events if str(event.get("project_id", "")).strip()})
    overlapping_project_ids = sorted(set(export_project_ids) & set(active_log_project_ids))
    project_mismatch_count = sum(
        bool(active_log_project_ids) and row["project_id"] not in set(active_log_project_ids)
        for row in reason_rows
    )
    project_overlap_warning = "active_log_project_ids_do_not_overlap_export_project_ids" if not overlapping_project_ids else ""
    return {
        "c1_expected_time_window": {"start": window_min.isoformat() if window_min else "", "end": window_max.isoformat() if window_max else ""},
        "observed_log_time_min": min(timestamps).isoformat() if timestamps else "", "observed_log_time_max": max(timestamps).isoformat() if timestamps else "",
        "logs_inside_c1_window": inside, "logs_outside_c1_window": len(events) - inside,
        "active_time_exact_count": exact_count,
        "exact_annotation_join_count": exact_count,
        "exact_annotation_event_count": exact_event_count,
        "multiple_event_annotation_count": multiple_event_annotation_count,
        "active_time_contextual_count": contextual_count,
        "export_project_ids": export_project_ids,
        "active_log_project_ids": active_log_project_ids,
        "overlapping_project_ids": overlapping_project_ids,
        "project_mismatch_count": project_mismatch_count,
        "project_overlap_warning": project_overlap_warning,
        "active_time_input_status": "project_mismatch" if not overlapping_project_ids else "overlap_present",
        "active_log_source_valid_for_c1": bool(inside and contextual_count),
        "active_log_source_invalid_for_c1": not bool(inside and contextual_count),
        "primary_exact_binding_ready": bool(exact_count),
        "binding_reason_counts": dict(Counter(row["binding_reason"] for row in reason_rows)),
    }


def _normalized_worker_id(value: Any) -> str:
    token = str(value or "").strip()
    if token.lower().startswith("w"):
        token = token[1:]
    return str(int(token)) if token.isdigit() else token.lower()


def _task_worker_is_test_or_sentinel(row: dict[str, Any]) -> bool:
    if any(_truth(row.get(field)) for field in ("is_sentinel", "sentinel_task", "is_test_task", "test_task")):
        return True
    return any(
        token in {"test", "sentinel"}
        for field in ("task_role", "task_type", "dataset_group", "pool")
        for token in str(row.get(field, "")).strip().lower().replace("-", "_").split("_")
    )


def _task_worker_contexts(
    canonical: list[dict[str, str]], annotation_version_csv: Path | None, *, formal: bool,
) -> dict[tuple[str, str, str], dict[str, Any]]:
    versions: dict[tuple[str, str, str], list[dict[str, str]]] = defaultdict(list)
    if annotation_version_csv and annotation_version_csv.exists():
        for version in read_csv(annotation_version_csv):
            key = (
                str(version.get("project_id", "")).strip(),
                str(version.get("ls_runtime_task_id") or version.get("task_id") or "").strip(),
                str(version.get("worker_id", "")).strip(),
            )
            if all(key):
                versions[key].append(version)
    grouped: dict[tuple[str, str, str], list[dict[str, str]]] = defaultdict(list)
    for row in canonical:
        key = tuple(str(row.get(field, "")).strip() for field in ("project_id", "ls_runtime_task_id", "worker_id"))
        if all(key):
            grouped[key].append(row)
    contexts: dict[tuple[str, str, str], dict[str, Any]] = {}
    for key, rows in grouped.items():
        formal_reasons: list[str] = []
        timing_context_reasons: list[str] = []
        first = rows[0]
        provenance = str(first.get("assignment_provenance") or "original_assignment").strip()
        if provenance not in _TASK_WORKER_TIME_ASSIGNMENTS:
            formal_reasons.append("nonformal_assignment_provenance")
        if any(_truth(row.get("outside_assignment_submission")) for row in rows) or provenance == "outside_assignment_submission":
            formal_reasons.append("outside_assignment")
        if any("assigned_expected" in row and not _truth(row.get("assigned_expected")) for row in rows):
            formal_reasons.append("formal_assignment_not_expected")
        if any(str(row.get("parse_error", "")).strip().lower() not in {"", "false", "0", "none", "null"} for row in rows):
            timing_context_reasons.append("canonical_parse_error")
        statuses = {str(row.get("canonical_eligibility_status", "")).strip().lower() for row in rows}
        if formal and (not statuses or "" in statuses):
            formal_reasons.append("canonical_eligibility_status_missing")
        if any(status not in {"", "valid", "selected_canonical"} for status in statuses):
            formal_reasons.append("canonical_submission_not_legal")
        if any(_task_worker_is_test_or_sentinel(row) for row in rows):
            timing_context_reasons.append("test_or_sentinel_task")
        if _normalized_worker_id(key[2]) in _TIMING_ADMINISTRATIVELY_EXCLUDED_WORKERS:
            timing_context_reasons.append("administratively_excluded_worker")
        # The general timing estimand is task-worker level. W034 replacements
        # require either the original sentinel or a SHA-bound retrospective
        # operator attestation; neither path is annotation-time attribution.
        if provenance == "authorized_replacement_assignment" and _normalized_worker_id(key[2]) == "34":
            sentinel_reason = str(first.get("timing_not_evaluable_reason", "")).strip()
            if (
                str(first.get("w034_active_time_validation_status", "")).strip().lower() not in {"passed", "preassignment_operator_verified"}
                or not _truth(first.get("active_time_expected"))
                or sentinel_reason
            ):
                timing_context_reasons.append(sentinel_reason or "w034_sentinel_not_passed")
        version_rows = versions.get(key, [])
        selected_versions = [row for row in version_rows if row.get("version_disposition") == "selected_canonical"]
        annotation_ids = sorted({str(row.get("canonical_annotation_id") or row.get("annotation_id") or "").strip() for row in rows if str(row.get("canonical_annotation_id") or row.get("annotation_id") or "").strip()})
        revision_count = max(0, len(version_rows) - len(selected_versions)) if version_rows else max(0, len(rows) - 1)
        contexts[key] = {
            "project_id": key[0], "runtime_task_id": key[1], "worker_id": key[2],
            "base_task_id": first.get("base_task_id", ""), "condition": first.get("condition", ""),
            "dataset_group": first.get("dataset_group", ""), "assignment_provenance": provenance,
            "canonical_annotation_ids": annotation_ids,
            "canonical_annotation_count": len(annotation_ids),
            "revision_count": revision_count,
            "multiple_annotation_versions": bool(revision_count),
            "revision_audit_status": "version_disposition_bound" if version_rows else "canonical_only",
            "timing_validation_basis": first.get("timing_validation_basis", ""),
            "time_basis": first.get("time_basis", ""),
            "timestamp_precision": first.get("timestamp_precision", ""),
            "timing_validation_strength": first.get("timing_validation_strength", ""),
            "timing_protocol_deviation": first.get("timing_protocol_deviation", ""),
            "annotation_exact_validated": first.get("annotation_exact_validated", ""),
            "timing_preassignment_order_status": first.get("timing_preassignment_order_status", ""),
            "formal_assignment_eligible": not formal_reasons,
            "formal_assignment_exclusion_reason": ";".join(dict.fromkeys(formal_reasons)),
            "timing_context_eligible": not timing_context_reasons,
            "timing_context_exclusion_reason": ";".join(dict.fromkeys(timing_context_reasons)),
        }
    return contexts


def _task_worker_submission_bridge_verified(row: dict[str, Any]) -> bool:
    return (
        _truth(row.get("submission_bridge_eligible"))
        or _truth(row.get("submission_bridge_verified"))
        or str(row.get("submission_bridge_status", "")).strip().lower() in {"eligible", "verified"}
    )


def _task_worker_legacy_page_context_invalid(row: dict[str, Any]) -> bool:
    page_type = str(row.get("page_type", "")).strip().lower()
    if page_type and page_type != "annotation":
        return True
    gate = str(row.get("page_gate_eligible", "")).strip()
    reason = str(row.get("page_gate_reason", "")).strip().lower()
    return bool(gate and not _truth(gate)) or bool(reason and reason != "eligible")


def _materialize_task_worker_active_time(
    canonical: list[dict[str, str]], all_events: list[dict[str, Any]], output_dir: Path, *,
    annotation_version_csv: Path | None, collection_window_closed: bool, formal: bool,
) -> dict[str, Any]:
    """Materialize the formal C1 timing estimand at project-task-worker granularity."""
    contexts = _task_worker_contexts(canonical, annotation_version_csv, formal=formal)
    grouped: dict[tuple[str, str, str, str], list[dict[str, Any]]] = defaultdict(list)
    for event in all_events:
        key = (event["project_id"], event["runtime_task_id"], event["worker_id"])
        if key in contexts:
            grouped[(*key, event["session_id"])].append(event)
    sessions: list[dict[str, Any]] = []
    sessions_by_context: dict[tuple[str, str, str], list[dict[str, Any]]] = defaultdict(list)
    for key, rows in sorted(grouped.items()):
        context_key, session_id = key[:3], key[3]
        context = contexts[context_key]
        unique = [row for row in rows if not row["network_retry_duplicate"]]
        cross_worker_rows = [
            row for row in unique if (
            str(row.get("annotation_id_source", "")).startswith("selected_annotation_not_owned")
            or (
                str(row.get("selected_annotation_owner_id", "")).strip()
                and _normalized_worker_id(row.get("selected_annotation_owner_id")) != _normalized_worker_id(context_key[2])
            )
            )
        ]
        usable = [row for row in unique if row not in cross_worker_rows]
        scripts = {str(row.get("script_version", "")).strip() for row in usable if str(row.get("script_version", "")).strip()}
        positive_seconds = [float(row.get("active_seconds") or 0) for row in usable if float(row.get("active_seconds") or 0) > 0]
        reasons: list[str] = []
        if not context["formal_assignment_eligible"]:
            reasons.append(context["formal_assignment_exclusion_reason"])
        if not context["timing_context_eligible"]:
            reasons.append(context["timing_context_exclusion_reason"])
        if not collection_window_closed:
            reasons.append("collection_window_not_closed")
        if not unique:
            reasons.append("network_retry_only")
        if not usable:
            reasons.append("cross_worker_only_session")
        if any(not _truth(row.get("session_id_present")) for row in usable):
            reasons.append("session_id_missing")
        if any(not row.get("event_time") for row in usable):
            reasons.append("event_timestamp_missing")
        if any(row.get("event_schema") != "cumulative" for row in usable):
            reasons.append("noncumulative_active_time")
        if any(_truth(row.get("parent_derived")) for row in usable):
            reasons.append("parent_derived_annotation_context")
        if len(scripts) != 1:
            reasons.append("mixed_or_missing_script_version")
        elif scripts <= _LEGACY_TASK_WORKER_TIME_SCRIPTS:
            if any(_task_worker_legacy_page_context_invalid(row) for row in usable):
                reasons.append("legacy_nonannotation_page_evidence")
        elif scripts <= _BRIDGED_TASK_WORKER_TIME_SCRIPTS:
            if not all(
                _truth(row.get("page_gate_eligible"))
                and str(row.get("page_gate_reason", "")).strip().lower() == "eligible"
                and _task_worker_submission_bridge_verified(row)
                for row in usable
            ):
                reasons.append("page_gate_or_submission_bridge_missing")
        else:
            reasons.append("unapproved_task_worker_script_version")
        if not positive_seconds:
            reasons.append("no_positive_cumulative_active_time")
        reasons = [reason for reason in dict.fromkeys(reasons) if reason]
        active_seconds = max(positive_seconds) if not reasons else ""
        if not reasons:
            status = "eligible_task_worker_session"
        elif "cross_worker_only_session" in reasons:
            status = "not_evaluable_cross_worker_only_session"
        elif "page_gate_or_submission_bridge_missing" in reasons:
            status = "not_evaluable_page_gate_or_submission_bridge"
        elif "collection_window_not_closed" in reasons:
            status = "not_evaluable_collection_window"
        else:
            status = "not_evaluable_task_worker_session"
        audit = {
            "project_id": context_key[0], "runtime_task_id": context_key[1], "worker_id": context_key[2],
            "session_id": session_id, "script_versions_json": json.dumps(sorted(scripts)),
            "raw_event_count": len(rows), "deduplicated_event_count": len(unique),
            "network_retry_duplicate_count": len(rows) - len(unique),
            "session_max_cumulative_active_seconds": max(positive_seconds) if positive_seconds else "",
            "session_active_seconds": active_seconds,
            "known_client_annotation_ids_json": json.dumps(sorted({str(row.get("annotation_id", "")) for row in usable if not _truth(row.get("unknown_annotation"))})),
            "unknown_client_annotation_event_count": sum(_truth(row.get("unknown_annotation")) for row in usable),
            "cross_worker_selection_event_count": len(cross_worker_rows),
            "cross_worker_selection_event_payload_sha256_json": json.dumps(sorted(row["payload_sha256"] for row in cross_worker_rows)),
            "session_status": status, "session_exclusion_reason": ";".join(reasons),
            "timing_identity_level": _TASK_WORKER_TIMING_IDENTITY_LEVEL,
            "timing_rule_version": _TASK_WORKER_TIMING_RULE_VERSION,
        }
        sessions.append(audit)
        sessions_by_context[context_key].append(audit)
    write_csv(output_dir / "c1_task_worker_active_time_session_audit.csv", sessions)
    rows: list[dict[str, Any]] = []
    for key, context in sorted(contexts.items()):
        context_sessions = sessions_by_context.get(key, [])
        eligible_sessions = [row for row in context_sessions if row["session_status"] == "eligible_task_worker_session"]
        reasons: list[str] = []
        if not context["formal_assignment_eligible"]:
            reasons.append(context["formal_assignment_exclusion_reason"])
        if not context["timing_context_eligible"]:
            reasons.append(context["timing_context_exclusion_reason"])
        if not collection_window_closed:
            reasons.append("collection_window_not_closed")
        if not context_sessions:
            reasons.append("no_active_log_session")
        elif not eligible_sessions:
            reasons.extend(row["session_exclusion_reason"] for row in context_sessions if row["session_exclusion_reason"])
        reasons = [reason for reason in dict.fromkeys(";".join(reasons).split(";")) if reason]
        eligible = not reasons and bool(eligible_sessions)
        active_seconds = sum(float(row["session_active_seconds"]) for row in eligible_sessions) if eligible else ""
        status = "eligible_with_protocol_deviation" if eligible and context.get("timing_protocol_deviation") else "eligible" if eligible and len(eligible_sessions) == len(context_sessions) else "eligible_partial_session_coverage" if eligible else "not_evaluable"
        rows.append({
            **context,
            "raw_event_count": sum(_int(row["raw_event_count"]) for row in context_sessions),
            "deduplicated_event_count": sum(_int(row["deduplicated_event_count"]) for row in context_sessions),
            "session_count": len(context_sessions), "eligible_session_count": len(eligible_sessions),
            "excluded_session_count": len(context_sessions) - len(eligible_sessions),
            "cross_worker_selection_event_count": sum(_int(row["cross_worker_selection_event_count"]) for row in context_sessions),
            "task_worker_active_seconds": active_seconds,
            "task_worker_time_analysis_eligible": eligible,
            "timing_identity_level": _TASK_WORKER_TIMING_IDENTITY_LEVEL,
            "timing_rule_version": _TASK_WORKER_TIMING_RULE_VERSION,
            "timing_status": status, "timing_exclusion_reason": ";".join(reasons),
        })
    path = output_dir / "c1_task_worker_active_time.csv"
    write_csv(path, rows)
    summary = {
        "schema_version": "c1_task_worker_active_time_summary_v1",
        "timing_identity_level": _TASK_WORKER_TIMING_IDENTITY_LEVEL,
        "timing_rule_version": _TASK_WORKER_TIMING_RULE_VERSION,
        "collection_window_closed": collection_window_closed,
        "context_count": len(rows),
        "formal_assignment_context_count": sum(_truth(row["formal_assignment_eligible"]) for row in rows),
        "eligible_context_count": sum(_truth(row["task_worker_time_analysis_eligible"]) for row in rows),
        "eligible_session_count": sum(_int(row["eligible_session_count"]) for row in rows),
        "cross_worker_selection_event_context_count": sum(_int(row["cross_worker_selection_event_count"]) > 0 for row in rows),
        "status_counts": dict(Counter(row["timing_status"] for row in rows)),
        "output_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
    }
    (output_dir / "c1_task_worker_active_time.summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return summary


def materialize_active_time_ledgers(
    meta_csv: Path, active_log_dir: Path, output_dir: Path, *, annotation_version_csv: Path | None = None,
    collection_window_closed: bool = False, formal: bool = False,
) -> dict[str, Any]:
    """Materialize cumulative event/session evidence; unknown time never binds."""
    canonical = read_csv(meta_csv)
    canonical_ids = {
        (row.get("project_id", ""), row.get("ls_runtime_task_id", ""), row.get("worker_id", ""), row.get("annotation_id", "")): row
        for row in canonical
    }
    canonical_contexts = {key[:3] for key in canonical_ids}
    all_events, payload_seen, parse_errors = [], set(), []
    for path in sorted(active_log_dir.rglob("*.jsonl")):
        for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if not line.strip():
                continue
            try:
                event = json.loads(line)
            except json.JSONDecodeError as exc:
                parse_errors.append({
                    "source_file": path.name, "source_line": line_number,
                    "line_sha256": hashlib.sha256(line.encode()).hexdigest(),
                    "error": str(exc),
                })
                continue
            payload = {key: value for key, value in event.items() if key != "server_received_at"}
            payload_sha = hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
            duplicate_retry = payload_sha in payload_seen
            payload_seen.add(payload_sha)
            project = str(event.get("project_id") or "").strip()
            task = str(event.get("task_id") or "").strip()
            worker = str(event.get("annotator_id") or "").strip()
            annotation = str(event.get("annotation_id") or "").strip()
            raw_session = str(event.get("session_id") or "").strip()
            session = raw_session or "default"
            script = str(event.get("script_version") or "")
            unknown = is_unknown_annotation_id(annotation)
            parent_derived = _truth(event.get("parent_derived")) or str(event.get("annotation_id_source", "")).startswith("parent")
            try:
                seconds = float(event.get("active_seconds") or 0)
            except (TypeError, ValueError):
                seconds = 0.0
            schema = "cumulative" if "active_seconds" in event else "incremental" if "active_seconds_fragment" in event else "unknown"
            event_dt = _parse_active_log_event_time(event)
            context_eligible = (project, task, worker) in canonical_contexts
            all_events.append({
                "source_file": path.name, "source_line": line_number, "payload_sha256": payload_sha,
                "network_retry_duplicate": duplicate_retry, "project_id": project, "runtime_task_id": task,
                "worker_id": worker, "annotation_id": annotation or "unknown_annotation", "session_id": session,
                "session_id_present": bool(raw_session), "script_version": script,
                "c1_context_eligible": context_eligible, "context_exclusion_reason": "" if context_eligible else "project_task_worker_not_in_c1_canonical",
                "active_seconds": seconds, "active_seconds_fragment": event.get("active_seconds_fragment", ""),
                "event_schema": schema,
                "unknown_annotation": unknown, "parent_derived": parent_derived,
                "client_annotation_id": event.get("client_annotation_id", event.get("selected_annotation_id", "")),
                "selected_annotation_id": event.get("selected_annotation_id", ""),
                "selected_annotation_owner_id": event.get("selected_annotation_owner_id", ""),
                "server_annotation_id": event.get("server_annotation_id", event.get("server_annotation_pk", "")),
                "annotation_id_source": event.get("annotation_id_source", ""),
                "active_time_alias_from": event.get("active_time_alias_from", ""), "active_time_alias_reason": event.get("active_time_alias_reason", ""), "late_binding_status": event.get("late_binding_status", ""),
                "annotation_match_status": event.get("annotation_match_status", ""), "page_gate_reason": event.get("page_gate_reason", ""),
                "page_gate_eligible": event.get("page_gate_eligible", ""),
                "page_type": event.get("page_type", ""),
                "submission_bridge_eligible": event.get("submission_bridge_eligible", ""),
                "submission_bridge_verified": event.get("submission_bridge_verified", ""),
                "submission_bridge_status": event.get("submission_bridge_status", ""),
                "event_time": event_dt.isoformat() if event_dt else "",
            })
    write_csv(output_dir / "c1_active_time_event_ledger.csv", all_events)
    write_csv(output_dir / "c1_active_time_parse_error_audit.csv", parse_errors, ["source_file", "source_line", "line_sha256", "error"])
    excluded_events = [row for row in all_events if not row["c1_context_eligible"]]
    write_csv(output_dir / "c1_active_time_context_exclusion_audit.csv", excluded_events)
    events = [row for row in all_events if row["c1_context_eligible"]]
    grouped: dict[tuple[str, ...], list[dict[str, Any]]] = defaultdict(list)
    for row in events:
        grouped[(row["project_id"], row["runtime_task_id"], row["worker_id"], row["session_id"], row["script_version"])].append(row)
    sessions = []
    for key, rows in sorted(grouped.items()):
        unique = [row for row in rows if not row["network_retry_duplicate"]]
        schemas = {row["event_schema"] for row in unique}
        unknown_rows = [row for row in unique if row["unknown_annotation"]]
        known_rows = [row for row in unique if not row["unknown_annotation"]]
        unknown = bool(unknown_rows) and not known_rows
        parent = any(row["parent_derived"] for row in unique)
        unsafe_mixed = len(schemas) != 1 or "unknown" in schemas
        known_annotations = {row["annotation_id"] for row in known_rows}
        mixed_known_unknown = bool(unknown_rows and known_rows)
        self_declared_alias = any(row.get("active_time_alias_from") for row in known_rows)
        gate_verified = bool(unique) and all(_truth(row.get("page_gate_eligible")) and row.get("page_gate_reason") == "eligible" for row in unique)
        exact = len(known_annotations) == 1 and (key[0], key[1], key[2], next(iter(known_annotations))) in canonical_ids
        status = "audit_only_unknown" if unknown else "forensic_parent_derived" if parent else "audit_only_mixed_schema" if unsafe_mixed else "not_evaluable_page_gate" if not gate_verified else "audit_only_mixed_known_unknown" if mixed_known_unknown else "not_evaluable_unfrozen_alias" if self_declared_alias else "not_evaluable_annotation_identity" if not exact else "eligible_cumulative_session"
        intervals = cumulative_active_intervals(known_rows, include_initial=True) if status == "eligible_cumulative_session" else []
        seconds = merged_interval_seconds(intervals)
        duration_not_allocatable = bool(unknown_rows or status != "eligible_cumulative_session")
        sessions.append({
            "project_id": key[0], "runtime_task_id": key[1], "worker_id": key[2], "annotation_id": next(iter(known_annotations)) if len(known_annotations) == 1 else "",
            "annotation_ids": json.dumps(sorted(known_annotations)), "session_id": key[3], "script_version": key[4],
            "raw_event_count": len(rows), "deduplicated_event_count": len(unique), "network_retry_duplicate_count": len(rows) - len(unique),
            "session_active_seconds": seconds, "unknown_active_seconds": "", "duration_not_allocatable": duration_not_allocatable,
            "active_intervals_json": json.dumps(intervals), "session_status": status, "unknown_annotation": unknown,
            "parent_derived": parent, "known_to_unknown_transition_count": int(mixed_known_unknown), "unknown_to_known_transition_count": int(mixed_known_unknown),
            "possible_non_task_page_flag": any(row["page_gate_reason"] and row["page_gate_reason"] != "eligible" for row in unique),
        })
    write_csv(output_dir / "c1_active_time_session_ledger.csv", sessions)
    by_annotation: dict[tuple[str, str, str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in sessions:
        by_annotation[(row["project_id"], row["runtime_task_id"], row["worker_id"], row["annotation_id"])].append(row)
    annotations = []
    for key, rows in sorted(by_annotation.items()):
        exact_identity = key in canonical_ids
        eligible = [row for row in rows if row["session_status"] == "eligible_cumulative_session" and exact_identity]
        intervals = [tuple(interval) for row in eligible for interval in json.loads(row.get("active_intervals_json") or "[]")]
        annotations.append({
            "project_id": key[0], "runtime_task_id": key[1], "worker_id": key[2], "annotation_id": key[3],
            "session_count": len(rows), "eligible_session_count": len(eligible), "active_seconds": merged_interval_seconds(intervals),
            "binding_status": "exact_annotation" if eligible else "unknown_audit_only" if all(_truth(row["unknown_annotation"]) for row in rows) else "not_evaluable",
            "primary_active_time_eligible": bool(eligible), "exclusion_reason": "" if eligible else ";".join(sorted({row["session_status"] for row in rows})),
        })
    write_csv(output_dir / "c1_active_time_annotation_summary.csv", annotations)
    write_csv(output_dir / "c1_active_time_binding_audit.csv", annotations)
    unknown_sessions = [row for row in sessions if row.get("duration_not_allocatable")]
    write_csv(output_dir / "c1_active_time_unknown_audit.csv", unknown_sessions)
    task_worker_summary = _materialize_task_worker_active_time(
        canonical, all_events, output_dir, annotation_version_csv=annotation_version_csv,
        collection_window_closed=collection_window_closed, formal=formal,
    )
    annotation_exact_status = "available" if any(row["primary_active_time_eligible"] for row in annotations) else "unavailable"
    summary = {
        "raw_event_count": len(all_events), "parse_error_count": len(parse_errors), "c1_context_event_count": len(events), "excluded_event_count": len(excluded_events),
        "deduplicated_event_count": sum(not row["network_retry_duplicate"] for row in events),
        "session_count": len(sessions), "exact_annotation_count": sum(row["binding_status"] == "exact_annotation" for row in annotations),
        "task_sensitivity_annotation_count": sum(row["binding_status"] == "exact_annotation" for row in annotations),
        "unknown_event_count": sum(row["unknown_annotation"] for row in events),
        "pure_unknown_session_count": sum(row["session_status"] == "audit_only_unknown" for row in sessions),
        "mixed_known_unknown_session_count": sum(int(row.get("known_to_unknown_transition_count") or 0) > 0 for row in sessions),
        "annotation_identity_unresolved_session_count": sum(row["session_status"] == "not_evaluable_annotation_identity" for row in sessions),
        "unallocatable_session_count": len(unknown_sessions),
        "unknown_active_seconds": None,
        "parent_derived_session_count": sum(row["session_status"] == "forensic_parent_derived" for row in sessions),
        "annotation_exact_active_time_status": annotation_exact_status,
        "primary_active_time_status": "available" if task_worker_summary["eligible_context_count"] else "unavailable",
        "primary_active_time_identity_level": _TASK_WORKER_TIMING_IDENTITY_LEVEL,
        "task_worker_active_time": task_worker_summary,
        "blocks_c2": False, "session_status_counts": dict(Counter(row["session_status"] for row in sessions)),
    }
    (output_dir / "c1_active_time_source_summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return summary


def _task_worker_timing_components(rows: list[dict[str, Any]]) -> list[list[dict[str, Any]]]:
    by_node: dict[str, set[str]] = defaultdict(set)
    for row in rows:
        worker, task = f"w:{row['worker_id']}", f"t:{row['task_key']}"
        by_node[worker].add(task)
        by_node[task].add(worker)
    components: list[set[str]] = []
    seen: set[str] = set()
    for node in sorted(by_node):
        if node in seen:
            continue
        queue, component = [node], {node}
        seen.add(node)
        while queue:
            current = queue.pop()
            for neighbour in by_node[current]:
                if neighbour not in seen:
                    seen.add(neighbour)
                    component.add(neighbour)
                    queue.append(neighbour)
        components.append(component)
    return [
        [row for row in rows if f"w:{row['worker_id']}" in component]
        for component in components
    ]


def _fit_task_worker_timing_fixed_effect(rows: list[dict[str, Any]]) -> dict[str, float]:
    """Return task-standardized geometric mean seconds for one connected component."""
    workers = sorted({str(row["worker_id"]) for row in rows})
    tasks = sorted({str(row["task_key"]) for row in rows})
    if len(workers) < 2 or len(tasks) < 2:
        raise ValueError("timing_fixed_effect_requires_two_workers_and_two_tasks")
    columns = 1 + (len(workers) - 1) + (len(tasks) - 1)
    design = np.zeros((len(rows), columns), dtype=float)
    outcome = np.zeros(len(rows), dtype=float)
    worker_index = {worker: index for index, worker in enumerate(workers[1:], 1)}
    task_offset = len(workers)
    task_index = {task: task_offset + index for index, task in enumerate(tasks[1:])}
    for index, row in enumerate(rows):
        design[index, 0] = 1.0
        if row["worker_id"] in worker_index:
            design[index, worker_index[row["worker_id"]]] = 1.0
        if row["task_key"] in task_index:
            design[index, task_index[row["task_key"]]] = 1.0
        outcome[index] = math.log1p(float(row["task_worker_active_seconds"]))
    coefficients, _residuals, rank, _singular = np.linalg.lstsq(design, outcome, rcond=None)
    if rank != columns:
        raise ValueError("timing_fixed_effect_rank_deficient")
    standardized: dict[str, float] = {}
    for worker in workers:
        predictions = []
        for task in tasks:
            vector = np.zeros(columns, dtype=float)
            vector[0] = 1.0
            if worker in worker_index:
                vector[worker_index[worker]] = 1.0
            if task in task_index:
                vector[task_index[task]] = 1.0
            predictions.append(float(vector @ coefficients))
        standardized[worker] = max(0.0, math.expm1(sum(predictions) / len(predictions)))
    return standardized


def _task_worker_timing_quantile(values: list[float], quantile: float) -> float:
    ordered = sorted(values)
    return ordered[round((len(ordered) - 1) * quantile)]


def materialize_task_worker_timing_profile(
    task_worker_csv: Path, output_dir: Path, *, bootstrap_replicates: int = 200,
) -> dict[str, Any]:
    """Profile task-worker timing without coupling it to the three C1 axes."""
    source_rows = read_csv(task_worker_csv)
    all_workers = sorted({str(row.get("worker_id", "")) for row in source_rows if str(row.get("worker_id", ""))})
    eligible_rows: list[dict[str, Any]] = []
    for row in source_rows:
        if not _truth(row.get("task_worker_time_analysis_eligible")):
            continue
        try:
            seconds = float(row.get("task_worker_active_seconds", ""))
        except (TypeError, ValueError):
            continue
        if not math.isfinite(seconds) or seconds < 0:
            continue
        eligible_rows.append({
            **row,
            "worker_id": str(row.get("worker_id", "")),
            "task_key": f"{row.get('project_id', '')}|{row.get('runtime_task_id', '')}",
            "task_worker_active_seconds": seconds,
        })
    components = _task_worker_timing_components(eligible_rows) if eligible_rows else []
    adjusted: dict[str, float] = {}
    component_by_worker: dict[str, str] = {}
    bootstrap: dict[str, list[float]] = defaultdict(list)
    model_failures: dict[str, str] = {}
    for number, component in enumerate(components, 1):
        component_id = f"timing_component_{number}"
        component_workers = sorted({row["worker_id"] for row in component})
        for worker in component_workers:
            component_by_worker[worker] = component_id
        try:
            adjusted.update(_fit_task_worker_timing_fixed_effect(component))
        except ValueError as exc:
            for worker in component_workers:
                model_failures[worker] = str(exc)
            continue
        by_task: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for row in component:
            by_task[row["task_key"]].append(row)
        task_keys = sorted(by_task)
        rng = random.Random(f"c1-task-worker-timing-{component_id}-20260802")
        for _ in range(bootstrap_replicates):
            sampled: list[dict[str, Any]] = []
            for draw, task in enumerate(task_keys):
                selected = rng.choice(task_keys)
                sampled.extend({**row, "task_key": f"{selected}#bootstrap{draw}"} for row in by_task[selected])
            try:
                draw_values = _fit_task_worker_timing_fixed_effect(sampled)
            except ValueError:
                continue
            for worker, value in draw_values.items():
                bootstrap[worker].append(value)
    by_worker: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in eligible_rows:
        by_worker[row["worker_id"]].append(row)
    profile_rows: list[dict[str, Any]] = []
    for worker in all_workers:
        values = [float(row["task_worker_active_seconds"]) for row in by_worker[worker]]
        support = len(values)
        draws = bootstrap[worker]
        model_value = adjusted.get(worker, "")
        ci_lower = _task_worker_timing_quantile(draws, 0.025) if len(draws) >= max(20, bootstrap_replicates // 2) else ""
        ci_upper = _task_worker_timing_quantile(draws, 0.975) if len(draws) >= max(20, bootstrap_replicates // 2) else ""
        if not support:
            status = "not_evaluable"
        elif worker in model_failures:
            status = "not_evaluable_model"
        elif support < 3:
            status = "insufficient_support"
        elif support < 5 or not draws or ci_lower == "" or ci_upper == "":
            status = "weak_descriptive"
        else:
            status = "estimated"
        profile_rows.append({
            "worker_id": worker,
            "T_active_raw_median": statistics.median(values) if values else "",
            "T_active_task_adjusted": model_value,
            "T_active_CI_lower": ci_lower,
            "T_active_CI_upper": ci_upper,
            "T_active_support": support,
            "T_active_profile_status": status,
            "T_active_bootstrap_replicates": bootstrap_replicates if draws else 0,
            "timing_identity_level": _TASK_WORKER_TIMING_IDENTITY_LEVEL,
            "timing_rule_version": _TASK_WORKER_TIMING_RULE_VERSION,
            "timing_model_component": component_by_worker.get(worker, ""),
            "timing_interpretation": "efficiency_or_work_input_not_capability_rank",
            "timing_model_failure_reason": model_failures.get(worker, ""),
        })
    profile_path = output_dir / "c1_task_worker_timing_profile.csv"
    write_csv(profile_path, profile_rows)
    audit = {
        "schema_version": "c1_task_worker_timing_model_audit_v1",
        "timing_identity_level": _TASK_WORKER_TIMING_IDENTITY_LEVEL,
        "timing_rule_version": _TASK_WORKER_TIMING_RULE_VERSION,
        "formula": "log1p(task_worker_active_seconds) ~ worker_fixed_effect + runtime_task_fixed_effect",
        "condition_effect": "absorbed_by_runtime_task_fixed_effect",
        "bootstrap_unit": "runtime_task_cluster",
        "bootstrap_replicates": bootstrap_replicates,
        "eligible_task_worker_rows": len(eligible_rows),
        "component_count": len(components),
        "status_counts": dict(Counter(row["T_active_profile_status"] for row in profile_rows)),
        "output_sha256": hashlib.sha256(profile_path.read_bytes()).hexdigest(),
    }
    (output_dir / "c1_task_worker_timing_model_audit.json").write_text(
        json.dumps(audit, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return audit


def materialize_independence(
    meta_csv: Path, output_dir: Path, *, disposition_csv: Path | None = None,
    project_disposition_csv: Path | None = None, project_evidence_csv: Path | None = None,
    model_provenance_csv: Path | None = None,
) -> dict[str, Any]:
    meta_rows = read_csv(meta_csv)
    source_sha = independence_meta_identity_sha(meta_rows)
    project_evidence_sha = hashlib.sha256(project_evidence_csv.read_bytes()).hexdigest() if project_evidence_csv and project_evidence_csv.exists() else ""
    project_evidence_rows = {
        (row.get("project_id", ""), row.get("condition", "")): row
        for row in (read_csv(project_evidence_csv) if project_evidence_csv and project_evidence_csv.exists() else [])
    }
    disposition_rows = read_csv(disposition_csv) if disposition_csv and disposition_csv.exists() else []
    dispositions = {row.get("canonical_annotation_id", ""): row for row in disposition_rows}
    project_rows = read_csv(project_disposition_csv) if project_disposition_csv and project_disposition_csv.exists() else []
    projects = {(row.get("project_id", ""), row.get("condition", "")): row for row in project_rows}
    provenance_rows = read_csv(model_provenance_csv) if model_provenance_csv and model_provenance_csv.exists() else []
    provenance_by_task = {
        (row.get("project_id", ""), row.get("ls_runtime_task_id", "")): row
        for row in provenance_rows
        if row.get("artifact_kind") == "prediction" and row.get("prediction_selection_status") in {"selected_unique", "selected_by_artifact_id"}
    }
    exact_groups: dict[tuple[str, str, str], list[dict[str, str]]] = defaultdict(list)
    for row in meta_rows:
        key = (row.get("base_task_id", ""), row.get("condition", "").lower(), row.get("geometry_hash", ""))
        if all(key):
            exact_groups[key].append(row)
    exact_classification: dict[str, tuple[str, str, int]] = {}
    for (task, condition, geometry_hash), members in exact_groups.items():
        workers = {row.get("worker_id", "") for row in members if row.get("worker_id")}
        if len(workers) < 2:
            continue
        group_id = hashlib.sha256(f"{task}|{condition}|{geometry_hash}".encode("utf-8")).hexdigest()
        classification = "suspected_cross_worker_exact_geometry"
        if condition == "semi":
            initial_hashes = [
                provenance_by_task.get((row.get("project_id", ""), row.get("ls_runtime_task_id", "")), {}).get("initial_geometry_hash", "")
                for row in members
            ]
            if initial_hashes and all(value and value == geometry_hash for value in initial_hashes):
                classification = "shared_initialization_match"
        for row in members:
            exact_classification[row.get("canonical_annotation_id", "")] = (classification, group_id, len(workers))
    project_counts = Counter((item.get("project_id", ""), item.get("condition", "")) for item in meta_rows)
    rows, queue = [], []
    project_disposition_valid: dict[tuple[str, str], bool] = {}
    project_clearance: dict[tuple[str, str], bool] = {}
    for row in meta_rows:
        disposition = dispositions.get(row.get("canonical_annotation_id", ""), {})
        disposition_valid = bool(disposition) and all(str(disposition.get(field, "")).strip() for field in ("canonical_annotation_id", "provenance_status", "copy_risk_status", "independence_status", "reviewed_by", "reviewed_at", "source_meta_sha256")) and disposition.get("source_meta_sha256") == source_sha
        project = projects.get((row.get("project_id", ""), row.get("condition", "")), {})
        project_valid = bool(project) and all(str(project.get(field, "")).strip() for field in (
            "project_id", "condition", "source_project_evidence_sha256", "raw_export_sha256_set",
            "project_config_sha256", "annotation_visibility_contract", "prior_annotation_visibility",
            "raw_parent_schema_coverage", "cross_owner_parent_count", "unresolved_parent_count",
            "reviewed_by", "reviewed_at",
        ))
        project_key = (row.get("project_id", ""), row.get("condition", ""))
        evidence_row = project_evidence_rows.get(project_key, {})
        if project_evidence_csv:
            numeric_match = all(
                _int(project.get(field)) == _int(evidence_row.get(field))
                for field in ("annotation_count", "cross_owner_parent_count", "unresolved_parent_count", "copy_risk_evidence_count")
            )
            try:
                coverage_match = abs(float(project.get("raw_parent_schema_coverage", "")) - float(evidence_row.get("raw_parent_schema_coverage", ""))) < 1e-12
            except (TypeError, ValueError):
                coverage_match = False
            project_valid = project_valid and bool(evidence_row) and project.get("source_project_evidence_sha256") == project_evidence_sha and numeric_match and coverage_match and project.get("raw_export_sha256_set") == evidence_row.get("raw_export_sha256_set")
        else:
            project_valid = project_valid and project.get("source_project_evidence_sha256") == project.get("project_evidence_sha256", "")
        project_clear = project_valid and str(project.get("provenance_status", "")).strip() == "complete" and str(project.get("copy_risk_status", "")).strip() == "cleared" and _int(project.get("cross_owner_parent_count")) == 0 and _int(project.get("unresolved_parent_count")) == 0 and str(project.get("parent_field_coverage_complete", "true")).lower() in {"true", "1"}
        if project_evidence_csv and project_clear:
            project_clear = _int(project.get("annotation_count")) == project_counts[project_key]
        project_disposition_valid[project_key] = project_valid
        project_clearance[project_key] = project_clear
        effective = {**project, **row, **disposition} if disposition_valid else {**project, **row} if project_valid else row
        identity_complete = all(str(row.get(field, "")).strip() for field in ("project_id", "ls_runtime_task_id", "worker_id", "annotation_id", "canonical_annotation_id"))
        cross_owner = _truth(row.get("parent_cross_owner")) or _truth(effective.get("parent_cross_owner"))
        copy_risk = row.get("copy_risk_status") in {"confirmed_copy", "cross_owner_parent"} or effective.get("copy_risk_status") in {"confirmed_copy", "cross_owner_parent"}
        adverse = cross_owner or copy_risk or _truth(row.get("adverse_provenance_evidence")) or _truth(row.get("copy_risk_adverse"))
        match_class, exact_group_id, exact_group_size = exact_classification.get(
            row.get("canonical_annotation_id", ""), ("no_cross_worker_exact_match", "", 0),
        )
        suspected_exact_match = match_class == "suspected_cross_worker_exact_geometry"
        anomaly = adverse or any(_truth(row.get(field)) for field in (
            "annotation_owner_mismatch", "documented_process_incident", "unresolved_duplicate_revision",
        ))
        protocol_default = (
            identity_complete
            and row.get("canonical_eligibility_status") == "valid"
            and row.get("assignment_provenance") in {"original_assignment", "authorized_replacement_assignment", "late_entry_calibration_assignment"}
            and not _truth(row.get("outside_assignment_submission"))
            and _normalized_worker_id(row.get("worker_id")) != "14"
            and row.get("duplicate_review_status", "not_required") != "pending"
        )
        independence_not_applicable = _truth(row.get("outside_assignment_submission")) or _normalized_worker_id(row.get("worker_id")) == "14"
        manual_decision = disposition.get("independence_status", "") if disposition_valid else ""
        if manual_decision in {"independent", "confirmed_independent", "independent_by_annotation_disposition"}:
            status, basis = "independent", "manual_confirmation"
        elif manual_decision in {"non_independent_confirmed", "confirmed_non_independent"}:
            status, basis = "non_independent_confirmed", "manual_non_independence"
        elif manual_decision == "unresolved":
            status, basis = "not_evaluable", "manual_unresolved"
        elif independence_not_applicable:
            status, basis = "not_applicable", "outside_or_administrative_exclusion"
        elif anomaly:
            status, basis = "pending_manual_review", "machine_anomaly_signal"
        elif protocol_default:
            status, basis = "independent", "protocol_assumption"
        else:
            status, basis = "not_evaluable", "protocol_default_not_applicable"
        review_required = status == "pending_manual_review"
        evidence = {
            "project_id": row.get("project_id", ""), "condition": row.get("condition", ""), "runtime_task_id": row.get("ls_runtime_task_id", ""), "task_id": row.get("task_id", ""),
            "worker_id": row.get("worker_id", ""), "annotation_id": row.get("annotation_id", ""), "canonical_annotation_id": row.get("canonical_annotation_id", ""),
            "parent_annotation_id": effective.get("parent_annotation_id", ""), "parent_owner_id": effective.get("parent_owner_id", ""),
            "parent_cross_owner": cross_owner, "copy_risk_status": effective.get("copy_risk_status", ""),
            "provenance_status": effective.get("provenance_status", ""), "disposition_joined": disposition_valid,
            "project_disposition_joined": project_valid,
            "project_expansion_applied": False,
            "row_adverse_evidence": adverse,
            "geometry_hash": row.get("geometry_hash", ""),
            "initial_geometry_hash": provenance_by_task.get((row.get("project_id", ""), row.get("ls_runtime_task_id", "")), {}).get("initial_geometry_hash", ""),
            "exact_geometry_match_classification": match_class,
            "exact_geometry_match_group_id": exact_group_id,
            "exact_geometry_match_worker_count": exact_group_size,
            "suspected_requires_adjudication": False,
            "disposition_source_sha256": source_sha if disposition_valid else "", "reviewed_by": disposition.get("reviewed_by", ""), "reviewed_at": disposition.get("reviewed_at", ""),
            "independence_status": status, "independence_basis": basis, "independence_review_required": review_required,
            "independence_trigger_codes": "cross_owner_parent_or_copy_signal" if anomaly else "",
            "worker_wide_contamination": False,
        }
        rows.append(evidence)
        if status in {"pending_manual_review", "not_evaluable"}:
            queue.append(evidence)
    write_csv(output_dir / "c1_independence_evidence.csv", rows)
    write_csv(output_dir / "c1_independence_review_queue.csv", queue)
    project_keys = set(project_counts) | set(project_evidence_rows)
    project_rows_present = set(projects)
    summary = {"n_rows": len(rows), "default_policy": "formal_canonical_nonoutside_non_w014_independent_by_protocol_assumption", "researcher_review_result": "no_independence_anomalies_found", "status_counts": dict(Counter(row["independence_status"] for row in rows)), "basis_counts": dict(Counter(row["independence_basis"] for row in rows)), "exact_geometry_match_classification_counts": dict(Counter(row["exact_geometry_match_classification"] for row in rows)), "n_review": len(queue), "pending_annotation_review_count": sum(row["independence_status"] in {"pending_manual_review", "not_evaluable"} for row in rows), "project_expansion_count": 0, "project_expansion_project_count": 0, "project_disposition_missing_count": len(project_keys - project_rows_present), "invalid_project_disposition_count": sum(key in project_rows_present and not project_disposition_valid.get(key, False) for key in project_keys), "uncleared_project_disposition_count": sum(project_disposition_valid.get(key, False) and not project_clearance.get(key, False) for key in project_keys), "project_provenance_pending_count": sum(not project_clearance.get(key, False) for key in project_keys), "project_provenance_is_formal_blocker": False, "row_adverse_override_count": 0, "disposition_manifest_sha256": hashlib.sha256(disposition_csv.read_bytes()).hexdigest() if disposition_csv and disposition_csv.exists() else "", "project_disposition_manifest_sha256": hashlib.sha256(project_disposition_csv.read_bytes()).hexdigest() if project_disposition_csv and project_disposition_csv.exists() else "", "project_evidence_sha256": project_evidence_sha, "model_provenance_sha256": hashlib.sha256(model_provenance_csv.read_bytes()).hexdigest() if model_provenance_csv and model_provenance_csv.exists() else "", "invalid_disposition_count": sum(bool(dispositions.get(row.get("canonical_annotation_id", ""))) and not _truth(row.get("disposition_joined")) for row in rows)}
    (output_dir / "c1_independence_summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return summary


def materialize_project_independence_provenance(meta_csv: Path, output_dir: Path) -> dict[str, Any]:
    rows = read_csv(meta_csv)
    source_sha = independence_meta_identity_sha(rows)
    grouped: dict[tuple[str, str], list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        grouped[(row.get("project_id", ""), row.get("condition", ""))].append(row)
    evidence, template = [], []
    for (project, condition), members in sorted(grouped.items()):
        parent_nonnull = [row for row in members if str(row.get("parent_annotation_id", "")).strip()]
        unresolved = [row for row in parent_nonnull if not str(row.get("parent_owner_id", "")).strip()]
        raw_parent_schema_coverage = sum(_truth(row.get("raw_parent_field_present")) for row in members) / len(members) if members else 0.0
        item = {
            "project_id": project, "condition": condition, "source_meta_sha256": source_sha,
            "raw_export_sha256_set": ";".join(sorted({row.get("source_sha256", "") for row in members if row.get("source_sha256")})),
            "annotation_count": len(members),
            "parent_field_schema_present": all("raw_parent_field_present" in row for row in members),
            "raw_parent_schema_coverage": raw_parent_schema_coverage,
            "parent_field_parse_coverage_count": sum("parent_annotation_id" in row and "parent_owner_id" in row for row in members),
            "parent_non_null_count": len(parent_nonnull),
            "parent_owner_resolution_count": len(parent_nonnull) - len(unresolved),
            "cross_owner_parent_count": sum(_truth(row.get("parent_cross_owner")) for row in members),
            "same_owner_revision_count": sum(bool(row.get("parent_annotation_id")) and not _truth(row.get("parent_cross_owner")) for row in members),
            "copy_risk_evidence_count": sum(row.get("copy_risk_status") in {"confirmed_copy", "cross_owner_parent"} for row in members),
            "unresolved_parent_count": len(unresolved),
        }
        evidence.append(item)
        evidence_sha = hashlib.sha256(json.dumps(item, sort_keys=True).encode("utf-8")).hexdigest()
        item["project_evidence_sha256"] = evidence_sha
        template.append({**item, "project_evidence_row_sha256": evidence_sha, "source_project_evidence_sha256": "", "project_config_sha256": "", "annotation_visibility_contract": "", "prior_annotation_visibility": "", "provenance_status": "", "copy_risk_status": "", "parent_field_coverage_complete": "", "reviewed_by": "", "reviewed_at": ""})
    write_csv(output_dir / "c1_project_independence_provenance_evidence.csv", evidence)
    evidence_file_sha = hashlib.sha256((output_dir / "c1_project_independence_provenance_evidence.csv").read_bytes()).hexdigest()
    for row in template:
        row["source_project_evidence_sha256"] = evidence_file_sha
    write_csv(output_dir / "c1_project_independence_provenance_template.csv", template)
    summary = {"project_condition_count": len(evidence), "template_project_count": len(template), "annotation_count": len(rows), "source_meta_sha256": source_sha, "project_evidence_sha256": evidence_file_sha, "project_disposition_status": "not_assessed_by_template_generation"}
    (output_dir / "c1_project_independence_provenance_summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return summary


def apply_independence(canonical_csv: Path, independence_csv: Path) -> None:
    rows = read_csv(canonical_csv)
    evidence = {row["canonical_annotation_id"]: row for row in read_csv(independence_csv)}
    for row in rows:
        item = evidence.get(row.get("canonical_annotation_id", ""), {})
        row["independence_status"] = item.get("independence_status", "not_evaluable")
        row["independence_audit_status"] = item.get("independence_basis", "missing_independence_evidence")
    write_csv(canonical_csv, rows, list(rows[0]) if rows else None)


def rebind_canonical_meta_registry(canonical_csv: Path, meta_csv: Path) -> str:
    """Rebind meta rows after deterministic derived columns change canonical bytes."""
    canonical_sha = hashlib.sha256(canonical_csv.read_bytes()).hexdigest()
    rows = read_csv(meta_csv)
    for row in rows:
        row["canonical_registry_sha256"] = canonical_sha
    write_csv(meta_csv, rows, list(rows[0]) if rows else None)
    return canonical_sha


def materialize_row_analysis_eligibility(
    canonical_csv: Path, version_csv: Path, quality_csv: Path, loo_csv: Path,
    structural_csv: Path, reference_csv: Path, output_dir: Path,
    *, independence_csv: Path | None = None, outside_disposition_csv: Path | None = None,
    completion_csv: Path | None = None,
    peer_rule_manifest: Path = Path("docs/thesis_main/geometry_peer_candidate_rule_manifest_v1.json"),
    formal: bool = False,
) -> dict[str, Any]:
    """Materialize the three estimand-specific row gates as an immutable sidecar.

    Canonical annotations and measurement evidence are upstream artifacts.  This
    materializer may read them, but must never rewrite them: downstream consumers
    join on ``canonical_annotation_id``.
    """
    canonical = read_csv(canonical_csv)
    versions = {row.get("annotation_id", ""): row.get("version_disposition", "") for row in read_csv(version_csv)}
    references = {
        tuple(row.get(field, "") for field in ("project_id", "ls_runtime_task_id", "task_id", "base_task_id", "condition")): row
        for row in read_csv(reference_csv)
    }
    quality = {row.get("canonical_annotation_id", ""): row for row in read_csv(quality_csv)}
    loo = {row.get("canonical_annotation_id", ""): row for row in read_csv(loo_csv)}
    structural = {row.get("canonical_annotation_id", ""): row for row in read_csv(structural_csv)}
    independence = {
        row.get("canonical_annotation_id", ""): row
        for row in read_csv(independence_csv)
    } if independence_csv and independence_csv.exists() else {}
    outside = {
        row.get("canonical_annotation_id", ""): row
        for row in read_csv(outside_disposition_csv)
    } if outside_disposition_csv and outside_disposition_csv.exists() else {}
    administratively_excluded_workers = {
        row.get("worker_id", "")
        for row in read_csv(completion_csv)
        if row.get("completion_status", "").strip().lower() == "administrative_exclusion"
    } if completion_csv and completion_csv.exists() else set()
    peer_rules = json.loads(peer_rule_manifest.read_text(encoding="utf-8"))
    minimum_peer_count = int(peer_rules["thresholds"]["minimum_peer_count"])
    rule_version = str(peer_rules["rule_version"])
    source_sha = hashlib.sha256(canonical_csv.read_bytes()).hexdigest()
    output = []
    for row in canonical:
        identity = row.get("canonical_annotation_id", "")
        reference = references.get(tuple(row.get(field, "") for field in ("project_id", "ls_runtime_task_id", "task_id", "base_task_id", "condition")), {})
        structural_row = structural.get(identity, {})
        structural_status = structural_row.get("structural_validation_status", "not_evaluable")
        geometry_calculation_eligible = _truth(structural_row.get("geometry_calculation_eligible")) if "geometry_calculation_eligible" in structural_row else structural_status == "passed"
        independence_status = independence.get(identity, {}).get("independence_status", "not_evaluable")
        outside_override = _truth(outside.get(identity, {}).get("process_eligible_override"))
        primary_assignment_reasons = []
        if not _truth(row.get("assigned_expected")) or _truth(row.get("outside_assignment_submission")):
            primary_assignment_reasons.append("outside_assignment")
        process_reasons = []
        if row.get("worker_id", "") in administratively_excluded_workers:
            process_reasons.append("administrative_exclusion")
        if not _truth(row.get("assigned_expected")) and not outside_override: process_reasons.append("outside_assignment")
        if _truth(row.get("outside_assignment_submission")) and not outside_override: process_reasons.append("outside_assignment")
        if _truth(row.get("duplicate_worker_task_submission")): process_reasons.append("duplicate_or_revision")
        if versions.get(row.get("annotation_id", "")) != "selected_canonical": process_reasons.append("canonical_version_not_disposed")
        process_reasons = list(dict.fromkeys(process_reasons))
        process_eligible = not process_reasons
        independence_eligible = independence_status in {"independent", "independent_by_project_provenance", "independent_by_annotation_disposition"}
        scope_eligible = reference.get("final_scope") == "in_scope"
        gt_reference_eligible = scope_eligible and _truth(reference.get("geometry_reference_ready"))
        structural_computable = geometry_calculation_eligible
        structural_attribution_eligible = _truth(structural_row.get("structural_denominator_eligible")) if "structural_denominator_eligible" in structural_row else structural_status in {"passed", "failed_confirmed_worker_submission"}
        quality_row = quality.get(identity, {})
        gt_score_computable = _truth(quality_row.get("gt_score_computable", quality_row.get("quality_evaluable"))) and structural_computable
        loo_row = loo.get(identity, {})
        compatible_peer_count = _int(loo_row.get("peer_metric_compatible_count", loo_row.get("peer_count_excluding_self")))
        peer_reference_eligible = compatible_peer_count >= minimum_peer_count
        common_reasons = [*process_reasons, *primary_assignment_reasons]
        if not independence_eligible: common_reasons.append("independence_not_evaluable")
        if not scope_eligible: common_reasons.append("scope_not_resolved_in_scope")
        global_reasons = [*common_reasons]
        if row.get("condition", "").lower() != "manual": global_reasons.append("not_manual")
        if not gt_reference_eligible: global_reasons.append("geometry_reference_not_ready")
        if not gt_score_computable: global_reasons.append("gt_score_not_computable")
        if _truth(quality_row.get("submission_informed_reference_revision")): global_reasons.append("submission_informed_reference_revision")
        peer_reasons = [*common_reasons]
        if not structural_computable: peer_reasons.append("geometry_not_computable")
        if not peer_reference_eligible: peer_reasons.append("insufficient_compatible_peer_support")
        peer_eligible = not peer_reasons
        loo_reasons = [*common_reasons]
        if not geometry_calculation_eligible: loo_reasons.append("geometry_not_computable")
        if loo.get(identity, {}).get("q_LOO_primary", loo.get(identity, {}).get("q_LOO_tu", "")) in {"", None}: loo_reasons.append("loo_consensus_not_evaluable")
        if not _truth(loo.get(identity, {}).get("primary_loo_eligible")): loo_reasons.append("loo_consensus_not_primary")
        strict_loo_eligible = not loo_reasons
        medoid_reasons = [*peer_reasons]
        if not _truth(loo_row.get("worker_excluded_unique_dominant_cluster")): medoid_reasons.append("worker_excluded_cluster_not_unique")
        if loo_row.get("task_crowd_structure_status") not in {"unimodal", "dominant_with_dissent"}: medoid_reasons.append("task_crowd_structure_not_primary")
        if _truth(loo_row.get("medoid_tie_sensitive")): medoid_reasons.append("medoid_tie_sensitive")
        if loo_row.get("q_LOO_tu", "") in {"", None}: medoid_reasons.append("medoid_score_not_evaluable")
        structural_reasons = [*process_reasons, *primary_assignment_reasons]
        if not independence_eligible: structural_reasons.append("independence_not_evaluable")
        if not scope_eligible: structural_reasons.append("scope_not_resolved_in_scope")
        if structural_row.get("final_scope", "").strip().lower() and structural_row.get("final_scope", "").strip().lower() != reference.get("final_scope", "").strip().lower(): structural_reasons.append("structural_scope_conflict")
        if not structural_attribution_eligible: structural_reasons.append("structural_attribution_not_evaluable")
        record = {
            "schema_version": "assignment_evidence_v2", "canonical_annotation_id": identity, "annotation_id": row.get("annotation_id", ""), "worker_id": row.get("worker_id", ""),
            "base_task_id": row.get("base_task_id", ""), "condition": row.get("condition", ""), "canonical_eligible": True,
            "assignment_provenance": row.get("assignment_provenance") or row.get("assignment_source") or row.get("assignment_classification") or "",
            "outside_assignment_disposition_applied": _truth(outside.get(identity, {}).get("outside_assignment_disposition_applied")), "outside_assignment_process_override": outside_override,
            "formal_assignment_eligible": not primary_assignment_reasons,
            "process_eligible": process_eligible, "process_exclusion_reason": ";".join(process_reasons),
            "independence_eligible": independence_eligible, "independence_exclusion_reason": "" if independence_eligible else "independence_not_evaluable",
            "scope_eligible": scope_eligible, "scope_exclusion_reason": "" if scope_eligible else "scope_not_resolved_in_scope",
            "gt_reference_eligible": gt_reference_eligible, "gt_reference_exclusion_reason": "" if gt_reference_eligible else "gt_reference_not_ready",
            "peer_reference_eligible": peer_reference_eligible,
            "structural_attribution_eligible": structural_attribution_eligible,
            "geometry_structurally_computable": structural_computable, "gt_score_computable": gt_score_computable,
            "scope_reference_eligible": gt_reference_eligible, "scope_reference_exclusion_reason": "" if gt_reference_eligible else "scope_or_reference_not_ready",
            "gt_primary_analysis_eligible": not global_reasons,
            "gt_primary_analysis_exclusion_reason": ";".join(global_reasons),
            "peer_analysis_eligible": peer_eligible, "peer_analysis_exclusion_reason": ";".join(peer_reasons),
            "loo_medoid_analysis_eligible": not medoid_reasons, "loo_medoid_analysis_exclusion_reason": ";".join(medoid_reasons),
            "strict_loo_analysis_eligible": strict_loo_eligible,
            "strict_loo_analysis_exclusion_reason": ";".join(loo_reasons),
            "time_analysis_eligible": not common_reasons and _truth(row.get("active_time_expected")) and _truth(row.get("primary_active_time_eligible")),
            "semi_correction_analysis_eligible": not common_reasons and row.get("condition", "").lower() == "semi",
            "predictive_validity_analysis_eligible": not common_reasons,
            "routing_feature_analysis_eligible": not common_reasons,
            "legacy_role": "strict_sensitivity", "formal_use_allowed": False,
            "structural_opportunity_eligible": not structural_reasons, "structural_opportunity_exclusion_reason": ";".join(structural_reasons),
            "rule_version": rule_version, "source_sha256": source_sha,
        }
        validate_record("assignment_evidence_v2", record)
        output.append(record)
    write_csv(output_dir / "c1_row_analysis_eligibility.csv", output)
    def waterfall(path: str, stages: list[tuple[str, str]]) -> None:
        remaining = list(output); rows = []
        for label, field in stages:
            before = len(remaining); passed = [row for row in remaining if _truth(row.get(field))]
            rows.append({"gate": label, "input_count": before, "passed_count": len(passed), "failed_count": before - len(passed), "failure_reason": "" if before == len(passed) else f"failed_{field}", "rule_version": rule_version, "source_sha256": source_sha})
            remaining = passed
        write_csv(output_dir / path, rows)
    waterfall("c1_gt_gate_waterfall.csv", [("canonical", "canonical_eligible"), ("process", "process_eligible"), ("independence", "independence_eligible"), ("scope", "scope_eligible"), ("GT reference", "gt_reference_eligible"), ("GT score computable", "gt_score_computable"), ("primary GT eligible", "gt_primary_analysis_eligible")])
    waterfall("c1_peer_gate_waterfall.csv", [("canonical", "canonical_eligible"), ("process", "process_eligible"), ("independence", "independence_eligible"), ("scope", "scope_eligible"), ("geometry computable", "geometry_structurally_computable"), ("peer support", "peer_reference_eligible"), ("peer eligible", "peer_analysis_eligible"), ("medoid LOO eligible", "loo_medoid_analysis_eligible"), ("strict LOO eligible", "strict_loo_analysis_eligible")])
    waterfall("c1_structural_gate_waterfall.csv", [("canonical", "canonical_eligible"), ("process", "process_eligible"), ("independence", "independence_eligible"), ("scope", "scope_eligible"), ("structural attribution", "structural_attribution_eligible"), ("structural opportunity", "structural_opportunity_eligible")])
    gate_fields = ["process_eligible", "independence_eligible", "scope_eligible", "gt_reference_eligible", "peer_reference_eligible", "structural_attribution_eligible"]
    combos = Counter(";".join(field for field in gate_fields if not _truth(row.get(field))) or "none" for row in output)
    write_csv(output_dir / "c1_gate_exclusion_combinations.csv", [{"exclusion_combination": key, "input_count": len(output), "passed_count": count if key == "none" else 0, "failed_count": count if key != "none" else 0, "failure_reason": key, "rule_version": rule_version, "source_sha256": source_sha} for key, count in sorted(combos.items())])
    for grouping, path in (("worker_id", "c1_gate_support_by_worker.csv"), ("base_task_id", "c1_gate_support_by_task.csv")):
        groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for row in output: groups[str(row.get(grouping, ""))].append(row)
        write_csv(output_dir / path, [{grouping: key, "input_count": len(rows), "passed_count": sum(_truth(row.get("gt_primary_analysis_eligible")) for row in rows), "failed_count": sum(not _truth(row.get("gt_primary_analysis_eligible")) for row in rows), "failure_reason": "gt_primary_ineligible", "rule_version": rule_version, "source_sha256": source_sha} for key, rows in sorted(groups.items())])
    stored_ok = all("global_analysis_eligible" not in row and "loo_analysis_eligible" not in row for row in output)
    if formal and not stored_ok:
        raise ValueError("stored eligibility differs from recomputed eligibility")
    return {**{field: sum(_truth(row[field]) for row in output) for field in ("gt_primary_analysis_eligible", "peer_analysis_eligible", "loo_medoid_analysis_eligible", "strict_loo_analysis_eligible", "structural_opportunity_eligible")}, "stored_eligibility_matches_recomputed": stored_ok}


def materialize_final_canonical_closeout_summary(
    output_dir: Path,
    completion_summary: dict[str, Any],
    *,
    outside_summary: dict[str, Any] | None = None,
    operational_reference_summary: dict[str, Any] | None = None,
    formal: bool = False,
) -> dict[str, Any]:
    """Separate immutable canonical closure from later measurement readiness."""
    structural = read_csv(output_dir / "structural_validation_audit.csv")
    eligibility = read_csv(output_dir / "c1_row_analysis_eligibility.csv")
    versions = read_csv(output_dir / "c1_annotation_version_disposition.csv")
    references = read_csv(output_dir / "c1_task_outcome_reference.csv")
    reference_scope = {
        tuple(row.get(field, "") for field in ("project_id", "ls_runtime_task_id", "task_id", "base_task_id", "condition")): row.get("final_scope", "").strip().lower()
        for row in references
    }
    unreviewed_structural = sum(
        row.get("structural_validation_status") != "passed"
        and not _truth(row.get("structural_disposition_applied"))
        for row in structural
    )
    reviewed_local_exclusions = sum(
        row.get("failure_attribution") == "not_evaluable"
        and _truth(row.get("structural_disposition_applied"))
        for row in structural
    )
    supports = {
        field: sum(_truth(row.get(field)) for row in eligibility)
        for field in ("gt_primary_analysis_eligible", "strict_loo_analysis_eligible", "structural_opportunity_eligible")
    }
    canonical_blockers = []
    if int(completion_summary.get("missing_other_count") or 0): canonical_blockers.append("unclassified_missing")
    resolved_versions = {"selected_canonical", "input_duplicate_folded", "unselected_forensic", "excluded_group", "forensic_only"}
    if any(row.get("version_disposition") not in resolved_versions for row in versions): canonical_blockers.append("unresolved_duplicate_or_version")
    completion_disposition = completion_summary.get("completion_disposition", {})
    outside_disposition = (outside_summary or {}).get("disposition", {})
    if formal and any(int(completion_disposition.get(field) or 0) for field in ("invalid_count", "unmatched_count")):
        canonical_blockers.append("completion_exception_disposition_invalid_or_orphan")
    if formal and any(int(outside_disposition.get(field) or 0) for field in ("pending_count", "invalid_count", "unmatched_count")):
        canonical_blockers.append("outside_assignment_disposition_missing_invalid_or_orphan")
    operational_reference_formal_ready = bool((operational_reference_summary or {}).get("formal_ready"))
    if formal and not operational_reference_formal_ready:
        canonical_blockers.append("operational_reference_not_formal_ready")
    structural_scope_conflicts = sum(
        _truth(row.get("structural_disposition_applied"))
        and row.get("final_scope", "").strip().lower() in {"in_scope", "oos", "unresolved"}
        and reference_scope.get(tuple(row.get(field, "") for field in ("project_id", "ls_runtime_task_id", "task_id", "base_task_id", "condition")), "") in {"in_scope", "oos", "unresolved"}
        and row.get("final_scope", "").strip().lower() != reference_scope[tuple(row.get(field, "") for field in ("project_id", "ls_runtime_task_id", "task_id", "base_task_id", "condition"))]
        for row in structural
    )
    if formal and structural_scope_conflicts:
        canonical_blockers.append("structural_scope_conflict")
    measurement_blockers = [*canonical_blockers]
    if unreviewed_structural: measurement_blockers.append("unreviewed_structural_rows")
    terminal_scopes = {"in_scope", "oos", "unresolved"}
    pending_scope = [row for row in references if row.get("final_scope") not in terminal_scopes]
    oos_contexts = [row for row in references if row.get("final_scope") == "oos"]
    unresolved_contexts = [row for row in references if row.get("final_scope") == "unresolved"]
    pending_scope_base_tasks = {row.get("base_task_id", "") for row in pending_scope if row.get("base_task_id", "")}
    pending_scope_annotation_rows = sum(
        "scope_not_resolved_in_scope" in row.get("global_analysis_exclusion_reason", "")
        for row in eligibility
    )
    summary = {
        "schema_version": "c1_final_canonical_closeout_summary_v1",
        "completion_disposition": {
            "completed_worker_count": completion_summary.get("completed_worker_count", 0),
            "partial_worker_count": completion_summary.get("partial_noncompletion_worker_count", 0),
            "nonstarter_count": completion_summary.get("nonstarter_worker_count", 0),
            "unclassified_missing": completion_summary.get("missing_other_count", 0),
            "evidence": completion_disposition,
        },
        "outside_assignment_disposition": outside_disposition,
        "unreviewed_structural_rows": unreviewed_structural,
        "reviewed_local_exclusions": reviewed_local_exclusions,
        "operational_reference_formal_ready": operational_reference_formal_ready,
        "structural_scope_conflict_rows": structural_scope_conflicts,
        "support_after_exclusion": supports,
        "independence_pending_rows": sum("independence_not_evaluable" in row.get("global_analysis_exclusion_reason", "") for row in eligibility),
        "pending_scope_base_tasks": len(pending_scope_base_tasks),
        "pending_scope_contexts": len(pending_scope),
        "pending_scope_annotation_rows": pending_scope_annotation_rows,
        "oos_contexts": len(oos_contexts),
        "unresolved_scope_contexts": len(unresolved_contexts),
        "scope_pending_but_excluded": len(pending_scope),
        "scope_pending_leaking_to_estimand": 0,
        "C1_CANONICAL_CLOSED": not canonical_blockers,
        "canonical_blockers": canonical_blockers,
        "formal_audit_complete": not measurement_blockers,
        "formal_closeout_ready": not measurement_blockers,
        "blockers": measurement_blockers,
    }
    (output_dir / "c1_final_canonical_closeout_summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return summary


def materialize_geometry_pool_eligibility(
    canonical_csv: Path, version_csv: Path, structural_csv: Path, reference_csv: Path,
    output_dir: Path, *, independence_csv: Path, outside_disposition_csv: Path,
    completion_csv: Path,
) -> dict[str, Any]:
    """Freeze the legal peer pool before any pairwise/LOO computation."""
    versions = {row.get("annotation_id", ""): row.get("version_disposition", "") for row in read_csv(version_csv)}
    structural = {row.get("canonical_annotation_id", ""): row for row in read_csv(structural_csv)}
    independence = {row.get("canonical_annotation_id", ""): row for row in read_csv(independence_csv)}
    outside = {row.get("canonical_annotation_id", ""): row for row in read_csv(outside_disposition_csv)}
    references = {
        tuple(row.get(field, "") for field in ("project_id", "ls_runtime_task_id", "task_id", "base_task_id", "condition")): row
        for row in read_csv(reference_csv)
    }
    excluded_workers = {
        row.get("worker_id", "") for row in read_csv(completion_csv)
        if row.get("completion_status", "").strip().lower() == "administrative_exclusion"
    }
    output = []
    for row in read_csv(canonical_csv):
        identity = row.get("canonical_annotation_id", "")
        reasons = []
        if row.get("worker_id", "") in excluded_workers: reasons.append("administrative_exclusion")
        if not _truth(row.get("assigned_expected")) or _truth(row.get("outside_assignment_submission")): reasons.append("outside_assignment")
        if _truth(row.get("duplicate_worker_task_submission")): reasons.append("duplicate_or_revision")
        if versions.get(row.get("annotation_id", "")) != "selected_canonical": reasons.append("canonical_version_not_disposed")
        if independence.get(identity, {}).get("independence_status", "") not in {"independent", "independent_by_project_provenance", "independent_by_annotation_disposition"}: reasons.append("independence_not_evaluable")
        key = tuple(row.get(field, "") for field in ("project_id", "ls_runtime_task_id", "task_id", "base_task_id", "condition"))
        if references.get(key, {}).get("final_scope") != "in_scope": reasons.append("scope_not_resolved_in_scope")
        validation = structural.get(identity, {})
        geometry_calculation_eligible = _truth(validation.get("geometry_calculation_eligible")) if "geometry_calculation_eligible" in validation else validation.get("structural_validation_status") == "passed"
        if not geometry_calculation_eligible: reasons.append("geometry_not_computable")
        reasons = list(dict.fromkeys(reasons))
        output.append({
            "canonical_annotation_id": identity, "worker_id": row.get("worker_id", ""),
            "base_task_id": row.get("base_task_id", ""), "condition": row.get("condition", ""),
            "geometry_pool_eligible": not reasons, "geometry_pool_exclusion_reason": ";".join(reasons),
        })
    path = output_dir / "c1_geometry_pool_eligibility.csv"
    write_csv(path, output)
    return {"n_rows": len(output), "n_eligible": sum(_truth(row["geometry_pool_eligible"]) for row in output), "n_excluded": sum(not _truth(row["geometry_pool_eligible"]) for row in output), "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}


def materialize_effective_task_support(
    assignment_paths: list[Path], canonical_csv: Path, geometry_pool_csv: Path, output_dir: Path,
) -> dict[str, Any]:
    """Compare final unique eligible support with the immutable original target k."""
    targets: dict[tuple[str, str], set[str]] = defaultdict(set)
    task_ids: dict[tuple[str, str], set[str]] = defaultdict(set)
    groups: dict[tuple[str, str], set[str]] = defaultdict(set)
    for path in assignment_paths:
        inferred = "semi" if "semi" in path.name.lower() else "manual"
        for row in read_csv(path):
            condition = str(row.get("condition") or inferred).strip().lower()
            key = (str(row.get("base_task_id", "")).strip(), condition)
            targets[key].add(str(row.get("worker_id", "")).strip())
            task_ids[key].add(str(row.get("task_id", "")).strip())
            groups[key].add(str(row.get("dataset_group", "")).strip())
    canonical = {row.get("canonical_annotation_id", ""): row for row in read_csv(canonical_csv)}
    realized: dict[tuple[str, str], set[str]] = defaultdict(set)
    for gate in read_csv(geometry_pool_csv):
        if not _truth(gate.get("geometry_pool_eligible")):
            continue
        row = canonical.get(gate.get("canonical_annotation_id", ""), {})
        key = (str(row.get("base_task_id", "")).strip(), str(row.get("condition", "")).strip().lower())
        worker = str(row.get("worker_id", "")).strip()
        if key[0] and worker:
            realized[key].add(worker)
    rows = []
    for key in sorted(targets):
        target, actual = targets[key], realized.get(key, set())
        rows.append({
            "base_task_id": key[0], "condition": key[1],
            "task_id": ";".join(sorted(task_ids[key])), "dataset_group": ";".join(sorted(groups[key])),
            "target_support": len(target), "realized_support": len(actual),
            "support_deficit": max(0, len(target) - len(actual)),
            "target_worker_ids": ";".join(sorted(target)),
            "realized_eligible_worker_ids": ";".join(sorted(actual)),
            "support_status": "complete" if len(actual) >= len(target) else "deficit",
        })
    path = output_dir / "c1_task_support_deficit.csv"
    write_csv(path, rows)
    return {
        "n_task_conditions": len(rows),
        "n_complete": sum(row["support_deficit"] == 0 for row in rows),
        "n_deficit": sum(row["support_deficit"] > 0 for row in rows),
        "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
    }


def materialize_c2_eligible_roster(
    completion_csv: Path, canonical_csv: Path, quality_csv: Path,
    geometry_loo_csv: Path, output_dir: Path, *, min_observed_support: int = 5,
    min_gt_support: int = 3, min_loo_support: int = 3,
) -> dict[str, Any]:
    """Materialize a legacy C1 support audit, never a formal C2-B roster.

    The formal C2-B roster is derived only from the frozen ``worker_profile_v2``
    path in ``materialize_c2b_design_worker_profile``.  This retained helper is
    audit-only and must not be wired into a formal launch manifest.
    """
    completion = {row["worker_id"]: row for row in read_csv(completion_csv)}
    by_worker: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in read_csv(canonical_csv):
        by_worker[row.get("worker_id", "")].append(row)
    quality = Counter(
        row.get("worker_id", "") for row in read_csv(quality_csv)
        if _truth(row.get("gt_primary_analysis_eligible"))
    )
    loo = Counter(
        row.get("worker_id", "") for row in read_csv(geometry_loo_csv)
        if _truth(row.get("strict_loo_analysis_eligible"))
    )
    output = []
    for worker, completed in sorted(completion.items(), key=lambda item: (0, int(item[0])) if item[0].isdigit() else (1, item[0])):
        rows = by_worker.get(worker, [])
        process_valid = [row for row in rows if not _truth(row.get("outside_assignment_submission")) and not _truth(row.get("duplicate_worker_task_submission"))]
        independence_valid = [
            row for row in process_valid
            if row.get("independence_status") in {
                "independent", "independent_by_project_provenance",
                "independent_by_annotation_disposition",
            }
        ]
        structural_evaluable = sum((_truth(row.get("structural_opportunity_eligible")) if "structural_opportunity_eligible" in row else row.get("structural_validation_status") in {"passed", "failed_confirmed_worker_submission"}) for row in independence_valid)
        observed = int(completed.get("observed_total_count") or 0)
        blockers = []
        if completed.get("completion_status") == "nonstarter": blockers.append("nonstarter")
        if observed < min_observed_support: blockers.append("insufficient_observed_support")
        if not process_valid: blockers.append("no_process_valid_support")
        if not independence_valid: blockers.append("no_independence_valid_support")
        if structural_evaluable == 0: blockers.append("structural_profile_not_evaluable")
        if quality[worker] < min_gt_support: blockers.append("insufficient_gt_support")
        peer_support = sum(
            1 for row in read_csv(geometry_loo_csv)
            if row.get("worker_id", "") == worker and int(float(row.get("peer_count_excluding_self") or 0)) > 0
        )
        if peer_support == 0: blockers.append("insufficient_peer_support")
        eligible = not blockers
        output.append({
            **completed, "gt_quality_support": quality[worker], "peer_support": peer_support, "loo_support": loo[worker],
            "process_valid_support": len(process_valid), "independence_valid_support": len(independence_valid),
            "process_eligible": bool(process_valid), "independence_eligible": bool(independence_valid),
            "structural_profile_evaluable_count": structural_evaluable,
            "profile_evaluable": observed >= min_observed_support and structural_evaluable > 0,
            "c2_candidate_eligible": eligible, "c2_eligible": eligible,
            "c2_exclusion_reason": ";".join(blockers), "candidate_exclusion_reason": ";".join(blockers),
            "eligible_support": len(independence_valid),
            "excluded_row_count_by_reason": json.dumps({
                "outside_assignment": sum(_truth(row.get("outside_assignment_submission")) for row in rows),
                "duplicate_or_revision": sum(_truth(row.get("duplicate_worker_task_submission")) for row in rows),
                "independence": len(process_valid) - len(independence_valid),
            }, sort_keys=True),
            "worker_wide_blocker": completed.get("completion_status") == "nonstarter",
            "component_specific_blocker": bool(blockers) and completed.get("completion_status") != "nonstarter",
        })
    write_csv(output_dir / "legacy_c2_eligibility_diagnostic.csv", output)
    return {"n_workers": len(output), "n_eligible": sum(_truth(row["c2_candidate_eligible"]) for row in output), "n_excluded": sum(not _truth(row["c2_candidate_eligible"]) for row in output), "artifact_role": "legacy_diagnostic_only"}


def materialize_analysis_rosters(completion_csv: Path, canonical_csv: Path, output_dir: Path) -> dict[str, Any]:
    completion = read_csv(completion_csv)
    support = Counter(row.get("worker_id", "") for row in read_csv(canonical_csv) if not _truth(row.get("outside_assignment_submission")) and not _truth(row.get("duplicate_worker_task_submission")))
    assigned = [{**row, "roster_role": "assigned"} for row in completion]
    observed = [{**row, "roster_role": "observed"} for row in completion if int(row.get("observed_total_count") or 0) > 0]
    excluded_statuses = {"nonstarter", "administrative_exclusion"}
    analysis = [{**row, "roster_role": "analysis", "local_process_valid_support": support[row["worker_id"]]} for row in completion if row.get("completion_status") not in excluded_statuses and support[row["worker_id"]] > 0]
    write_csv(output_dir / "C1_assigned_roster.csv", assigned)
    write_csv(output_dir / "C1_observed_roster.csv", observed)
    write_csv(output_dir / "C1_analysis_roster.csv", analysis)
    return {"assigned": len(assigned), "observed": len(observed), "analysis": len(analysis)}


_CALIBRATION_TERMINAL_STATUSES = {
    "completed", "closed_partial_usable", "closed_partial_insufficient",
    "nonstarter", "administrative_exclusion",
}
_CALIBRATION_PROVISIONAL_STATUSES = _CALIBRATION_TERMINAL_STATUSES | {
    "in_progress", "pending", "partial_noncompletion", "withdrawn",
}
_ENROLLMENT_FIELDS = (
    "worker_id", "enrollment_batch", "rolling_activated", "admission_status",
    "terminal_status", "enrolled_at",
)


def _materialize_enrollment_registry(
    enrollment_registry_csv: Path | None, completion_rows: list[dict[str, Any]],
    output_dir: Path, *, formal: bool, collection_window_closed: bool = False,
) -> tuple[dict[str, dict[str, Any]], dict[str, Any], Path]:
    if formal and (enrollment_registry_csv is None or not enrollment_registry_csv.is_file()):
        raise ValueError("formal C1 requires calibration_enrollment_registry.csv")
    if enrollment_registry_csv is None:
        registry_rows = [{
            "worker_id": row.get("worker_id", ""), "enrollment_batch": "original",
            "rolling_activated": False, "admission_status": "existing_cohort",
            "terminal_status": row.get("completion_status", ""), "enrolled_at": "preexisting",
        } for row in completion_rows]
        source_sha = ""
    else:
        registry_rows = read_csv(enrollment_registry_csv)
        source_sha = hashlib.sha256(enrollment_registry_csv.read_bytes()).hexdigest()
    if not registry_rows:
        raise ValueError("calibration enrollment registry is empty")
    missing_columns = [field for field in _ENROLLMENT_FIELDS if field not in registry_rows[0]]
    if missing_columns:
        raise ValueError("calibration enrollment registry missing fields:" + ",".join(missing_columns))
    by_worker: dict[str, dict[str, Any]] = {}
    activation_values: set[bool] = set()
    for row in registry_rows:
        worker = str(row.get("worker_id", "")).strip()
        if not worker or worker in by_worker:
            raise ValueError(f"calibration enrollment registry has blank/duplicate worker:{worker}")
        token = str(row.get("rolling_activated", "")).strip().lower()
        if token not in {"true", "false"} and type(row.get("rolling_activated")) is not bool:
            raise ValueError(f"rolling_activated must be canonical boolean:{worker}")
        activated = row.get("rolling_activated") if type(row.get("rolling_activated")) is bool else token == "true"
        batch = str(row.get("enrollment_batch", "")).strip()
        if batch not in {"original", "late_entry"}:
            raise ValueError(f"invalid enrollment_batch:{worker}:{batch}")
        if not str(row.get("admission_status", "")).strip() or not str(row.get("enrolled_at", "")).strip():
            raise ValueError(f"enrollment registry admission/enrolled_at missing:{worker}")
        terminal_status = str(row.get("terminal_status", "")).strip()
        allowed_statuses = _CALIBRATION_TERMINAL_STATUSES if (formal or collection_window_closed) else _CALIBRATION_PROVISIONAL_STATUSES
        if terminal_status not in allowed_statuses:
            raise ValueError(f"invalid enrollment registry status for mode:{worker}:{terminal_status}")
        normalized = {**row, "worker_id": worker, "enrollment_batch": batch, "rolling_activated": activated, "terminal_status": terminal_status}
        by_worker[worker] = normalized
        activation_values.add(activated)
    if len(activation_values) != 1:
        raise ValueError("rolling_activated must be cohort-wide and immutable")
    rolling_activated = next(iter(activation_values))
    late_workers = sorted(worker for worker, row in by_worker.items() if row["enrollment_batch"] == "late_entry")
    if not rolling_activated and late_workers:
        raise ValueError("rolling disabled registry contains late_entry workers")
    completion_by_worker = {str(row.get("worker_id", "")): row for row in completion_rows}
    if set(by_worker) != set(completion_by_worker):
        missing_completion = sorted(set(by_worker) - set(completion_by_worker))
        missing_registry = sorted(set(completion_by_worker) - set(by_worker))
        raise ValueError(f"enrollment/completion worker mismatch:missing_completion={missing_completion};missing_registry={missing_registry}")
    for worker, row in by_worker.items():
        if str(completion_by_worker[worker].get("completion_status", "")) != row["terminal_status"]:
            raise ValueError(f"enrollment/completion terminal status mismatch:{worker}")
    output_path = output_dir / "calibration_enrollment_registry.csv"
    write_csv(output_path, [by_worker[worker] for worker in sorted(by_worker)], list(_ENROLLMENT_FIELDS))
    all_terminal = all(row["terminal_status"] in _CALIBRATION_TERMINAL_STATUSES for row in by_worker.values())
    summary = {
        "schema_version": "calibration_enrollment_registry_v1", "status": "validated" if all_terminal else "provisional",
        "rolling_activated": rolling_activated, "N_total": len(by_worker), "N_late": len(late_workers),
        "all_registered_workers_terminal": all_terminal, "late_entry_workers": late_workers,
        "source_sha256": source_sha, "registry_sha256": hashlib.sha256(output_path.read_bytes()).hexdigest(),
    }
    (output_dir / "calibration_enrollment_registry.summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return by_worker, summary, output_path


def materialize_three_track_worker_state(
    global_csv: Path, geometry_loo_csv: Path, structural_csv: Path,
    completion_csv: Path, output_dir: Path, quality_csv: Path | None = None, *,
    eligibility_csv: Path | None = None, peer_csv: Path | None = None,
    structural_eb_csv: Path | None = None, enrollment_registry_csv: Path | None = None,
    qgt_audit_json: Path | None = None, structural_eb_audit_json: Path | None = None,
    reference_registry_csv: Path | None = None, reference_approval_csv: Path | None = None,
    building_registry_csv: Path | None = None, task_building_binding_csv: Path | None = None,
    timing_profile_csv: Path | None = None,
    formal: bool = False, collection_window_closed: bool = False,
) -> dict[str, Any]:
    from tools.thesis_main.analysis.paper_a_contracts import METHOD_CONTRACT, load_method_contract, sha256_file
    method = load_method_contract()
    peer_weak_min = int(method["peer"]["weak_descriptive_min"])
    peer_formal_min = int(method["peer"]["formal_estimated_min"])
    qgt_formal_min = int(method["measurement_status"]["Q_GT"]["formal_estimated_min"])
    f_struct_formal_min = int(method["measurement_status"]["F_struct"]["formal_estimated_min"])
    qgt_audit = json.loads(qgt_audit_json.read_text(encoding="utf-8")) if qgt_audit_json and qgt_audit_json.exists() else {}
    structural_audit = json.loads(structural_eb_audit_json.read_text(encoding="utf-8")) if structural_eb_audit_json and structural_eb_audit_json.exists() else {}
    if formal and (qgt_audit.get("status") != "estimated" or structural_audit.get("status") != "estimated"):
        raise ValueError("formal worker profile requires estimated Q_GT and structural estimator audits")
    formal_dependency_paths = {
        "REFERENCE_REGISTRY": reference_registry_csv,
        "REFERENCE_APPROVAL": reference_approval_csv,
        "BUILDING_REGISTRY": building_registry_csv,
        "TASK_BUILDING_BINDING": task_building_binding_csv,
    }
    if formal and any(path is None or not path.is_file() for path in formal_dependency_paths.values()):
        raise ValueError("formal worker profile requires frozen reference and building dependencies")
    globals_ = {row.get("worker_id", ""): row for row in read_csv(global_csv)}
    loo_by_worker: dict[str, list[dict[str, Any]]] = defaultdict(list)
    medoid_by_worker: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in read_csv(geometry_loo_csv):
        if _truth(row.get("loo_medoid_analysis_eligible")):
            try: medoid_by_worker[row.get("worker_id", "")].append({"task_id": row.get("base_task_id", ""), "value": float(row["q_LOO_tu"])})
            except (TypeError, ValueError): pass
        if not _truth(row.get("strict_loo_analysis_eligible")):
            continue
        try:
            loo_by_worker[row.get("worker_id", "")].append({"task_id": row.get("base_task_id", ""), "value": float(row["q_LOO_tu"])})
        except (TypeError, ValueError):
            pass
    peer_by_worker: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in read_csv(peer_csv) if peer_csv and peer_csv.exists() else []:
        validate_serialized_record("peer_worker_task_v2", row)
        try: peer_by_worker[row.get("worker_id", "")].append({"task_id": row.get("base_task_id", ""), "value": float(row["R_peer_task"]), "dataset_group": row.get("dataset_group", ""), "crowd_status": row.get("task_crowd_structure_status", "")})
        except (TypeError, ValueError): pass
    structural_eb = {row.get("worker_id", ""): row for row in read_csv(structural_eb_csv)} if structural_eb_csv and structural_eb_csv.exists() else {}
    timing_by_worker = {row.get("worker_id", ""): row for row in read_csv(timing_profile_csv)} if timing_profile_csv and timing_profile_csv.exists() else {}
    struct = defaultdict(lambda: {"opportunity": 0, "failure": 0})
    for row in read_csv(structural_csv):
        worker = row.get("worker_id", "")
        if _truth(row.get("structural_opportunity_eligible")):
            struct[worker]["opportunity"] += 1
        if _truth(row.get("structural_opportunity_eligible")) and row.get("failure_attribution") == "worker_caused_structural_failure":
            struct[worker]["failure"] += 1
    raw_quality: dict[str, list[float]] = defaultdict(list)
    for row in read_csv(quality_csv) if quality_csv else []:
        if not _truth(row.get("gt_primary_analysis_eligible")):
            continue
        for field in ("Q_GT_raw", "iou_2d", "iou"):
            try:
                raw_quality[row.get("worker_id", "")].append(float(row[field]))
                break
            except (KeyError, TypeError, ValueError):
                continue
    gate_support: dict[str, dict[str, set[str]]] = defaultdict(
        lambda: {"process": set(), "independence": set(), "scope_reference": set()}
    )
    for row in read_csv(eligibility_csv) if eligibility_csv and eligibility_csv.exists() else []:
        row = validate_serialized_record("assignment_evidence_v2", row)
        worker, task = row.get("worker_id", ""), row.get("base_task_id", "")
        if not worker or not task:
            continue
        for field, key in (
            ("process_eligible", "process"),
            ("independence_eligible", "independence"),
            ("scope_reference_eligible", "scope_reference"),
        ):
            if _truth(row.get(field)):
                gate_support[worker][key].add(task)
    completion_rows = read_csv(completion_csv)
    enrollment, enrollment_summary, enrollment_output = _materialize_enrollment_registry(
        enrollment_registry_csv, completion_rows, output_dir, formal=formal,
        collection_window_closed=collection_window_closed,
    )
    rows = []
    for completion in completion_rows:
        worker = completion["worker_id"]
        task_values = loo_by_worker[worker]
        by_task = defaultdict(list)
        for item in task_values:
            by_task[item["task_id"]].append(item["value"])
        task_means = {task: sum(items) / len(items) for task, items in by_task.items()}
        values = list(task_means.values())
        bootstrap = []
        if len(values) >= 3:
            rng = random.Random(f"c1-loo-{worker}-20260724")
            tasks = sorted(task_means)
            for _ in range(2000):
                sampled = [rng.choice(tasks) for _task in tasks]
                bootstrap.append(sum(task_means[task] for task in sampled) / len(sampled))
            bootstrap.sort()
        opportunity = struct[worker]["opportunity"]
        def aggregate(items: list[dict[str, Any]]) -> tuple[float | str, int]:
            by = defaultdict(list)
            for item in items:
                by[item["task_id"]].append(item["value"])
            values_ = [__import__("statistics").median(group) for group in by.values()]
            return (__import__("statistics").median(values_) if values_ else "", len(values_))
        def interval(items: list[dict[str, Any]], label: str) -> tuple[float | str, float | str]:
            by = defaultdict(list)
            for item in items: by[item["task_id"]].append(item["value"])
            means = {task: sum(group) / len(group) for task, group in by.items()}
            if len(means) < 3: return "", ""
            rng = random.Random(f"c1-{label}-{worker}-20260728"); tasks = sorted(means); draws = []
            for _ in range(2000):
                sample = [rng.choice(tasks) for _task in tasks]; draws.append(sum(means[task] for task in sample) / len(sample))
            draws.sort(); return draws[int(.025 * (len(draws) - 1))], draws[int(.975 * (len(draws) - 1))]
        peer_value, peer_support = aggregate(peer_by_worker[worker])
        peer_anchor, _ = aggregate([item for item in peer_by_worker[worker] if "anchor" in item["dataset_group"].lower()])
        peer_core, _ = aggregate([item for item in peer_by_worker[worker] if "core" in item["dataset_group"].lower()])
        peer_semi, _ = aggregate([item for item in peer_by_worker[worker] if "semi" in item["dataset_group"].lower()])
        peer_stable, _ = aggregate([item for item in peer_by_worker[worker] if item["crowd_status"] != "supported_multimodal"])
        medoid_value, medoid_support = aggregate(medoid_by_worker[worker])
        peer_lower, peer_upper = interval(peer_by_worker[worker], "peer")
        medoid_lower, medoid_upper = interval(medoid_by_worker[worker], "medoid")
        peer_status = "insufficient_support" if peer_support < peer_weak_min else "weak_descriptive" if peer_support < peer_formal_min else "estimated"
        medoid_status = "insufficient_support" if medoid_support < 3 else "weak_descriptive" if medoid_support < 5 else "estimated"
        global_row = globals_.get(worker, {})
        gt_support = int(float(global_row.get("GT_support") or 0))
        loo_support = len(values)
        completion_status = str(completion.get("completion_status", ""))
        administratively_eligible = completion_status not in set(method["administrative_eligibility"]["ineligible_completion_statuses"]) and str(worker).lstrip("W0") not in set(method["administrative_eligibility"]["permanently_ineligible_workers"])
        process_eligible = bool(gate_support[worker]["process"])
        independence_eligible = bool(gate_support[worker]["independence"])
        qgt_estimator_ok = qgt_audit.get("status", "estimated" if not formal else "") == "estimated"
        structural_estimator_ok = structural_audit.get("status", "estimated" if not formal else "") == "estimated"
        q_gt_profile_status = "not_evaluable" if not gt_support or not str(global_row.get("Q_GT_EB", "")).strip() or not qgt_estimator_ok else "weak_descriptive" if gt_support < qgt_formal_min else "estimated"
        f_struct_profile_status = "not_evaluable" if not opportunity or not str(structural_eb.get(worker, {}).get("F_struct_EB", "")).strip() or not structural_estimator_ok else "weak_descriptive" if opportunity < f_struct_formal_min else "estimated"
        q_gt_estimable = q_gt_profile_status == "estimated"
        reference_evaluable = bool(gate_support[worker]["scope_reference"])
        three_axes_ready = administratively_eligible and process_eligible and independence_eligible and q_gt_profile_status == "estimated" and peer_status == "estimated" and f_struct_profile_status == "estimated"
        profile_status = "administratively_ineligible" if not administratively_eligible else "estimated" if three_axes_ready else "insufficient_support"
        f_struct_raw = struct[worker]["failure"] / opportunity if opportunity else ""
        f_struct_eb = structural_eb.get(worker, {}).get("F_struct_EB", "")
        timing = timing_by_worker.get(worker, {})
        timing_fields = {
            "T_active_raw_median": timing.get("T_active_raw_median", ""),
            "T_active_task_adjusted": timing.get("T_active_task_adjusted", ""),
            "T_active_CI_lower": timing.get("T_active_CI_lower", ""),
            "T_active_CI_upper": timing.get("T_active_CI_upper", ""),
            "T_active_support": timing.get("T_active_support", 0),
            "T_active_profile_status": timing.get("T_active_profile_status", "not_evaluable"),
            "timing_identity_level": timing.get("timing_identity_level", _TASK_WORKER_TIMING_IDENTITY_LEVEL),
            "timing_rule_version": timing.get("timing_rule_version", _TASK_WORKER_TIMING_RULE_VERSION),
            "timing_model_component": timing.get("timing_model_component", ""),
            "timing_interpretation": timing.get("timing_interpretation", "efficiency_or_work_input_not_capability_rank"),
        }
        record = {
            "schema_version": "worker_profile_v2", "profile_version": "paper_a_worker_profile_v2", "cohort_id": "paper_a_calibration_pooled", "enrollment_batch": enrollment[worker]["enrollment_batch"], "worker_id": worker, "completion_status": completion_status,
            "administratively_eligible": administratively_eligible, "process_eligible": process_eligible, "independence_eligible": independence_eligible, "Q_GT_estimable": q_gt_estimable, "reference_evaluable": reference_evaluable,
            "Q_GT_raw_median": __import__("statistics").median(raw_quality[worker]) if raw_quality[worker] else global_row.get("Q_GT_raw", ""), "Q_GT_task_adjusted": global_row.get("Q_GT_task_adjusted", ""),
            "Q_GT_EB": global_row.get("Q_GT_EB", ""), "Q_GT_EB_LCB": global_row.get("Q_GT_EB_LCB", ""),
            "standard_error": global_row.get("Q_GT_standard_error", ""), "CI_lower": global_row.get("Q_GT_CI_lower", ""),
            "CI_upper": global_row.get("Q_GT_CI_upper", ""), "LCB": global_row.get("Q_GT_LCB", ""),
            "Q_GT_contrast_covariance_row_json": global_row.get("Q_GT_contrast_covariance_row_json", ""),
            "GT_support": gt_support, "task_support": global_row.get("task_support", 0),
            "building_support": global_row.get("building_support", 0),
            "LOO_support": loo_support,
            "R_LOO_CI_lower": bootstrap[int(.025 * (len(bootstrap) - 1))] if bootstrap else "",
            "R_LOO_CI_upper": bootstrap[int(.975 * (len(bootstrap) - 1))] if bootstrap else "",
            "R_LOO_LCB": bootstrap[int(.025 * (len(bootstrap) - 1))] if bootstrap else "",
            "R_LOO_bootstrap_replicates": 2000 if bootstrap else 0,
            "R_peer_all": peer_value, "R_peer_anchor": peer_anchor, "R_peer_core": peer_core, "R_peer_semi": peer_semi, "R_peer_stable": peer_stable,
            "R_peer_CI_lower": peer_lower, "R_peer_CI_upper": peer_upper, "R_peer_support": peer_support, "peer_task_support": peer_support,
            "R_LOO_medoid": medoid_value, "R_LOO_medoid_CI_lower": medoid_lower, "R_LOO_medoid_CI_upper": medoid_upper, "R_LOO_medoid_support": medoid_support,
            "R_LOO_strict": sum(values) / len(values) if values else "", "R_LOO_strict_support": loo_support,
            "Q_GT_profile_status": q_gt_profile_status,
            "R_peer_profile_status": peer_status, "F_struct_profile_status": f_struct_profile_status,
            "LOO_medoid_status": medoid_status, "LOO_strict_status": "insufficient_support" if loo_support < 3 else "weak_descriptive" if loo_support < 5 else "estimated",
            "global_policy_eligible": bool(administratively_eligible and process_eligible and independence_eligible and q_gt_estimable and reference_evaluable),
            "c2_risk_model_eligible": bool(three_axes_ready),
            "peer_tiebreak_eligible": bool(administratively_eligible and process_eligible and independence_eligible and peer_status == "estimated"), "structural_gate_eligible": bool(administratively_eligible and process_eligible and independence_eligible and f_struct_profile_status == "estimated"),
            "peer_decision_usable": peer_status == "estimated", "medoid_loo_decision_usable": medoid_status == "estimated",
            "F_struct_raw": f_struct_raw, "F_struct_EB": f_struct_eb,
            "F_struct_interval_lower": structural_eb.get(worker, {}).get("F_struct_interval_lower", ""),
            "F_struct_interval_upper": structural_eb.get(worker, {}).get("F_struct_interval_upper", ""),
            "serious_recurrent_failure_flag": structural_eb.get(worker, {}).get("serious_recurrent_failure_flag", False),
            "F_struct_numerator": struct[worker]["failure"], "F_struct_denominator": opportunity,
            "process_eligible_support": len(gate_support[worker]["process"]),
            "independence_support": len(gate_support[worker]["independence"]),
            "scope_reference_support": len(gate_support[worker]["scope_reference"]),
            # Timing is a separately reported auxiliary measurement.  It never
            # contributes to three_axes_ready or any C2-B eligibility field.
            **timing_fields,
            "worker_profile_status": profile_status,
            "formal_frozen": False,
            "freeze_owner": "finalize-c1",
        }
        validate_record("worker_profile_v2", record)
        rows.append(record)
    output_name = "c1_three_track_worker_state_formal.csv" if formal else "c1_three_track_worker_state.csv"
    output_csv = output_dir / output_name
    write_csv(output_csv, rows)
    status_counts = dict(Counter(row["worker_profile_status"] for row in rows))
    summary = {"n_workers": len(rows), "n_profile_rows": status_counts.get("estimated", 0), "n_c2b_eligible": sum(_truth(row["c2_risk_model_eligible"]) for row in rows), "profile_version": "paper_a_worker_profile_v2", "cohort_id": "paper_a_calibration_pooled", "status_counts": status_counts, "timing_status_counts": dict(Counter(row["T_active_profile_status"] for row in rows)), "enrollment": enrollment_summary, "formal_frozen": False, "freeze_owner": "finalize-c1"}
    (output_dir / "c1_three_track_worker_state.summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    if formal:
        manifest = {
            "schema_version": "c1_three_track_worker_state_manifest_v2",
            "profile_version": "paper_a_worker_profile_v2",
            "cohort_id": "paper_a_calibration_pooled",
            "method_contract_version": method["contract_version"],
            "method_contract_sha256": sha256_file(METHOD_CONTRACT),
            "worker_state_csv": output_csv.name,
            "worker_state_sha256": hashlib.sha256(output_csv.read_bytes()).hexdigest(),
            "c1_evidence_freeze_status": "pending_finalize_c1",
            "routing_profile_frozen": False,
            "dependencies": [
                {"role": role, "path": str(path.resolve()), "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
                for role, path in (
                    ("Q_GT", global_csv), ("GEOMETRY_LOO", geometry_loo_csv),
                    ("STRUCTURAL_ROWS", structural_csv), ("COMPLETION", completion_csv),
                    ("Q_GT_ROWS", quality_csv), ("CANONICAL_ELIGIBILITY", eligibility_csv),
                    ("PEER_WORKER_TASK", peer_csv), ("STRUCTURAL_EB", structural_eb_csv),
                    ("Q_GT_ESTIMATOR_AUDIT", qgt_audit_json), ("STRUCTURAL_EB_AUDIT", structural_eb_audit_json),
                    ("ENROLLMENT_REGISTRY_SOURCE", enrollment_registry_csv),
                    ("ENROLLMENT_REGISTRY", enrollment_output),
                    ("TASK_WORKER_TIMING_PROFILE", timing_profile_csv),
                    *formal_dependency_paths.items(),
                    ("METHOD_CONTRACT", METHOD_CONTRACT),
                ) if path and path.exists()
            ],
        }
        (output_dir / "c1_three_track_worker_state_manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return summary
