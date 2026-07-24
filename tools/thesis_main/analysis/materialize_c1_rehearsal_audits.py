"""Materialize C1 operational audits that must not depend on canonical eligibility."""

from __future__ import annotations

import csv
import hashlib
import json
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from tools.thesis_main.analysis.geometry_consensus.representation import normalize_geometry
from tools.thesis_main.analysis.failure_disposition import c1_failure_fields
from tools.thesis_main.analysis.quality_core.active_time import is_unknown_annotation_id, _parse_active_log_event_time


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
) -> dict[str, Any]:
    assignments: dict[tuple[str, str, str, str], dict[str, Any]] = {}
    for path in assignment_paths:
        condition = "semi" if "semi" in path.name.lower() else "manual"
        for row in read_csv(path):
            key = _assignment_key(row)
            if key in assignments:
                raise ValueError(f"duplicate assignment identity: {key}")
            assignments[key] = {**row, "condition": condition}

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
        if normalize_geometry(row.get("corners_px") or [], width=int(row.get("width") or 1024), height=int(row.get("height") or 512))["valid"]:
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
        status = "nonstarter" if complete == 0 else "completed" if complete == total else "partial_noncompletion"
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

    write_csv(output_dir / "c1_worker_completion_audit.csv", completion_rows)
    write_csv(output_dir / "c1_assignment_realization_audit.csv", realization_rows)
    write_csv(output_dir / "c1_missing_submission_by_worker.csv", missing_rows)
    condition_rows = [{"condition": condition, "assigned_count": sum(row["condition"] == condition for row in realization_rows), "observed_count": sum(row["condition"] == condition and row["observed_submission"] for row in realization_rows), "missing_count": sum(row["condition"] == condition and row["missing_submission"] for row in realization_rows)} for condition in ("manual", "semi")]
    write_csv(output_dir / "c1_missing_submission_by_condition.csv", condition_rows)
    write_csv(output_dir / "c1_task_support_deficit.csv", task_rows)
    counts = Counter(row["completion_status"] for row in completion_rows)
    return {
        "roster_count": len(completion_rows), "assigned_submission_count": len(realization_rows),
        "observed_submission_count": sum(row["observed_submission"] for row in realization_rows), "missing_submission_count": len(missing_rows),
        "completed_worker_count": counts["completed"], "partial_noncompletion_worker_count": counts["partial_noncompletion"], "nonstarter_worker_count": counts["nonstarter"],
        "completed_worker_ids": [row["worker_id"] for row in completion_rows if row["completion_status"] == "completed"],
        "partial_worker_ids": [row["worker_id"] for row in completion_rows if row["completion_status"] == "partial_noncompletion"],
        "nonstarter_worker_ids": [row["worker_id"] for row in completion_rows if row["completion_status"] == "nonstarter"],
        "missing_nonstarter_count": sum(row["missing_reason"] == "worker_nonstarter" for row in missing_rows),
        "missing_partial_count": sum(row["missing_reason"] == "worker_partial_noncompletion" for row in missing_rows),
        "missing_other_count": sum(row["missing_reason"] not in {"worker_nonstarter", "worker_partial_noncompletion"} for row in missing_rows),
        "task_support_counts": dict(Counter(row["support_status"] for row in task_rows)),
    }


def materialize_structural_validation(canonical_csv: Path, geometry_jsonl: Path, output_dir: Path) -> dict[str, Any]:
    canonical = {row["canonical_annotation_id"]: row for row in read_csv(canonical_csv)}
    rows = []
    for line in geometry_jsonl.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        geometry = json.loads(line); annotation = canonical.get(geometry.get("canonical_annotation_id", ""), {})
        parsed = normalize_geometry(geometry.get("corners_px") or [], width=int(geometry.get("width") or 1024), height=int(geometry.get("height") or 512))
        reason = parsed["reason"]
        worker_reason = reason in {"odd_keypoint_count", "incomplete_pairing", "duplicate_event_positions", "top_floor_order_invalid", "self_intersecting_or_open_topology"}
        system_reason = reason in {"shape_invalid", "non_finite", "out_of_range", "ambiguous_pairing"} or bool(annotation.get("parse_error"))
        status = "passed" if parsed["valid"] else "failed_confirmed_worker_submission" if worker_reason else "failed_system_or_parser" if system_reason else "not_evaluable"
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
            "structural_validation_status": status, "structural_failure_reason": parsed["reason"],
            "detected_structural_issue": not parsed["valid"],
            "worker_attributable": status == "failed_confirmed_worker_submission",
            "independence_status": annotation.get("independence_status", "not_evaluable"),
            "failure_attribution": "none" if status == "passed" else "worker_caused_structural_failure" if status == "failed_confirmed_worker_submission" else "not_evaluable",
            "analysis_inclusion": "geometry_and_structural" if status == "passed" else "structural_only" if status == "failed_confirmed_worker_submission" else "excluded_with_reason",
            "worker_reliability_eligibility": status == "passed" and annotation.get("independence_status") == "independent",
        })
    write_csv(output_dir / "structural_validation_audit.csv", rows)
    counts = Counter(row["structural_validation_status"] for row in rows)
    failures = Counter(row["failure_attribution"] for row in rows)
    return {"n_rows": len(rows), "structural_status_counts": dict(counts), "failure_attribution_counts": dict(failures)}


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
        "odd_keypoint_count": ("worker_invalid_pair_count", "worker_caused_structural_failure", False),
        "incomplete_pairing": ("worker_invalid_pair_count", "worker_caused_structural_failure", False),
        "duplicate_event_positions": ("worker_duplicate_corner", "worker_caused_structural_failure", False),
        "top_floor_order_invalid": ("worker_pair_fold", "worker_caused_structural_failure", False),
        "self_intersecting_or_open_topology": ("worker_self_intersection", "worker_caused_structural_failure", False),
        "ambiguous_pairing": ("canonical_pairing_ambiguous", "not_evaluable", True),
        "out_of_range": ("coordinate_conversion_failure", "not_evaluable", True),
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
        root, attribution, review = _root_cause(validation.get("structural_failure_reason", ""))
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
            "root_cause_class": root, "failure_attribution": attribution,
            "score_unavailable_reason": validation.get("structural_failure_reason", ""), "gt_quality_eligible": False,
            "loo_eligible": False, "structural_denominator_eligible": attribution == "worker_caused_structural_failure",
            "worker_structural_failure_numerator": attribution == "worker_caused_structural_failure",
            "analysis_inclusion": validation.get("analysis_inclusion", "excluded_with_reason"),
            "manual_review_required": review, "review_reason": root if review else "",
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


def materialize_outside_assignment(canonical_csv: Path, output_dir: Path) -> dict[str, Any]:
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
            "annotation_id": row.get("annotation_id", ""), "worker_id": row.get("worker_id", ""),
            "runtime_task_id": row.get("ls_runtime_task_id", ""), "base_task_id": row.get("base_task_id", ""),
            "project_id": row.get("project_id", ""), "condition": row.get("condition", ""),
            "expected_assignment": False, "mapping_status": f"{row.get('planned_mapping_status', '')};{row.get('runtime_binding_status', '')}",
            "classification": classification,
            "recommended_disposition": "forensic_process_audit_exclude_quality" if classification in {"true_unassigned_submission", "test_annotation"} else "fold_duplicate_or_revision" if classification in {"duplicate_export", "legitimate_revision"} else "pending_manual_mapping_review",
        })
    write_csv(output_dir / "c1_outside_assignment_classification_audit.csv", rows)
    write_csv(output_dir / "c1_outside_assignment_adjudication_queue.csv", [row for row in rows if row["classification"] != "true_unassigned_submission"])
    return {"count": len(rows), "classification_counts": dict(Counter(row["classification"] for row in rows))}


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
        if len(candidates) == 1:
            reason = "exact_match"
        elif len(candidates) > 1:
            reason = "multiple_candidate_logs"
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
    contextual_count = sum(row["binding_reason"] in {"exact_match", "multiple_candidate_logs", "annotation_id_missing_in_log"} for row in reason_rows)
    inside = sum(row["inside_c1_window_count"] for row in source_rows)
    return {
        "c1_expected_time_window": {"start": window_min.isoformat() if window_min else "", "end": window_max.isoformat() if window_max else ""},
        "observed_log_time_min": min(timestamps).isoformat() if timestamps else "", "observed_log_time_max": max(timestamps).isoformat() if timestamps else "",
        "logs_inside_c1_window": inside, "logs_outside_c1_window": len(events) - inside,
        "active_time_exact_count": exact_count,
        "active_time_contextual_count": contextual_count,
        "active_log_source_valid_for_c1": bool(inside and contextual_count),
        "active_log_source_invalid_for_c1": not bool(inside and contextual_count),
        "primary_exact_binding_ready": bool(exact_count),
        "binding_reason_counts": dict(Counter(row["binding_reason"] for row in reason_rows)),
    }


def materialize_active_time_ledgers(meta_csv: Path, active_log_dir: Path, output_dir: Path) -> dict[str, Any]:
    """Materialize cumulative event/session evidence; unknown time never binds."""
    canonical = read_csv(meta_csv)
    canonical_ids = {
        (row.get("project_id", ""), row.get("ls_runtime_task_id", ""), row.get("worker_id", ""), row.get("annotation_id", "")): row
        for row in canonical
    }
    events, payload_seen = [], set()
    for path in sorted(active_log_dir.rglob("*.jsonl")):
        for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if not line.strip():
                continue
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                continue
            payload = {key: value for key, value in event.items() if key != "server_received_at"}
            payload_sha = hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
            duplicate_retry = payload_sha in payload_seen
            payload_seen.add(payload_sha)
            project = str(event.get("project_id") or "").strip()
            task = str(event.get("task_id") or "").strip()
            worker = str(event.get("annotator_id") or "").strip()
            annotation = str(event.get("server_annotation_id") or event.get("annotation_id") or "").strip()
            session = str(event.get("session_id") or "default")
            script = str(event.get("script_version") or "")
            unknown = is_unknown_annotation_id(annotation)
            parent_derived = _truth(event.get("parent_derived")) or str(event.get("annotation_id_source", "")).startswith("parent")
            try:
                seconds = float(event.get("active_seconds") or 0)
            except (TypeError, ValueError):
                seconds = 0.0
            schema = "cumulative" if "active_seconds" in event else "incremental" if "active_seconds_fragment" in event else "unknown"
            event_dt = _parse_active_log_event_time(event)
            events.append({
                "source_file": path.name, "source_line": line_number, "payload_sha256": payload_sha,
                "network_retry_duplicate": duplicate_retry, "project_id": project, "runtime_task_id": task,
                "worker_id": worker, "annotation_id": annotation or "unknown_annotation", "session_id": session, "script_version": script,
                "active_seconds": seconds, "active_seconds_fragment": event.get("active_seconds_fragment", ""),
                "event_schema": schema,
                "unknown_annotation": unknown, "parent_derived": parent_derived,
                "client_annotation_id": event.get("client_annotation_id", event.get("selected_annotation_id", "")),
                "server_annotation_id": event.get("server_annotation_id", event.get("annotation_id", "")),
                "selected_annotation_id": event.get("selected_annotation_id", ""), "annotation_id_source": event.get("annotation_id_source", ""),
                "active_time_alias_from": event.get("active_time_alias_from", ""), "late_binding_status": event.get("late_binding_status", ""),
                "annotation_match_status": event.get("annotation_match_status", ""), "page_gate_reason": event.get("page_gate_reason", ""),
                "event_time": event_dt.isoformat() if event_dt else "",
            })
    write_csv(output_dir / "c1_active_time_event_ledger.csv", events)
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
        exact = len(known_annotations) == 1 and (key[0], key[1], key[2], next(iter(known_annotations))) in canonical_ids
        status = "audit_only_unknown" if unknown else "forensic_parent_derived" if parent else "audit_only_mixed_schema" if unsafe_mixed else "audit_only_mixed_known_unknown" if mixed_known_unknown else "not_evaluable_annotation_identity" if not exact else "eligible_cumulative_session"
        seconds = max((float(row["active_seconds"]) for row in known_rows), default=0.0) if status == "eligible_cumulative_session" else 0.0
        unknown_seconds = max((float(row["active_seconds"]) for row in unknown_rows), default=0.0)
        sessions.append({
            "project_id": key[0], "runtime_task_id": key[1], "worker_id": key[2], "annotation_id": next(iter(known_annotations)) if len(known_annotations) == 1 else "",
            "annotation_ids": json.dumps(sorted(known_annotations)), "session_id": key[3], "script_version": key[4],
            "raw_event_count": len(rows), "deduplicated_event_count": len(unique), "network_retry_duplicate_count": len(rows) - len(unique),
            "session_active_seconds": seconds, "unknown_active_seconds": unknown_seconds, "session_status": status, "unknown_annotation": unknown,
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
        annotations.append({
            "project_id": key[0], "runtime_task_id": key[1], "worker_id": key[2], "annotation_id": key[3],
            "session_count": len(rows), "eligible_session_count": len(eligible), "active_seconds": sum(float(row["session_active_seconds"]) for row in eligible),
            "binding_status": "exact_annotation" if eligible else "unknown_audit_only" if all(_truth(row["unknown_annotation"]) for row in rows) else "not_evaluable",
            "primary_active_time_eligible": bool(eligible), "exclusion_reason": "" if eligible else ";".join(sorted({row["session_status"] for row in rows})),
        })
    write_csv(output_dir / "c1_active_time_annotation_summary.csv", annotations)
    write_csv(output_dir / "c1_active_time_binding_audit.csv", annotations)
    unknown_sessions = [row for row in sessions if float(row.get("unknown_active_seconds") or 0) > 0]
    write_csv(output_dir / "c1_active_time_unknown_audit.csv", unknown_sessions)
    summary = {
        "raw_event_count": len(events), "deduplicated_event_count": sum(not row["network_retry_duplicate"] for row in events),
        "session_count": len(sessions), "exact_annotation_count": sum(row["binding_status"] == "exact_annotation" for row in annotations),
        "task_sensitivity_annotation_count": sum(row["binding_status"] != "unknown_audit_only" for row in annotations),
        "unknown_event_count": sum(row["unknown_annotation"] for row in events), "unknown_session_count": len(unknown_sessions),
        "unknown_active_seconds": sum(float(row["unknown_active_seconds"]) for row in unknown_sessions),
        "parent_derived_session_count": sum(row["session_status"] == "forensic_parent_derived" for row in sessions),
        "primary_active_time_status": "available" if any(row["primary_active_time_eligible"] for row in annotations) else "unavailable",
        "blocks_c2": False, "session_status_counts": dict(Counter(row["session_status"] for row in sessions)),
    }
    (output_dir / "c1_active_time_source_summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return summary


def materialize_independence(meta_csv: Path, output_dir: Path) -> dict[str, Any]:
    rows, queue = [], []
    for row in read_csv(meta_csv):
        identity_complete = all(str(row.get(field, "")).strip() for field in ("project_id", "ls_runtime_task_id", "worker_id", "annotation_id", "canonical_annotation_id"))
        cross_owner = _truth(row.get("parent_cross_owner"))
        copy_risk = row.get("copy_risk_status") in {"confirmed_copy", "cross_owner_parent"}
        if cross_owner or copy_risk:
            status, basis = "non_independent_confirmed", "cross_owner_parent_or_confirmed_copy"
        elif identity_complete:
            status, basis = "independent", "independent_by_observed_provenance"
        else:
            status, basis = "not_evaluable", "identity_or_provenance_incomplete"
        evidence = {
            "project_id": row.get("project_id", ""), "runtime_task_id": row.get("ls_runtime_task_id", ""), "task_id": row.get("task_id", ""),
            "worker_id": row.get("worker_id", ""), "annotation_id": row.get("annotation_id", ""), "canonical_annotation_id": row.get("canonical_annotation_id", ""),
            "parent_annotation_id": row.get("parent_annotation_id", ""), "parent_owner_id": row.get("parent_owner_id", ""),
            "parent_cross_owner": cross_owner, "copy_risk_status": row.get("copy_risk_status", ""),
            "independence_status": status, "independence_basis": basis, "worker_wide_contamination": False,
        }
        rows.append(evidence)
        if status == "not_evaluable": queue.append(evidence)
    write_csv(output_dir / "c1_independence_evidence.csv", rows)
    write_csv(output_dir / "c1_independence_review_queue.csv", queue)
    summary = {"n_rows": len(rows), "status_counts": dict(Counter(row["independence_status"] for row in rows)), "n_review": len(queue)}
    (output_dir / "c1_independence_summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return summary


def apply_independence(canonical_csv: Path, independence_csv: Path) -> None:
    rows = read_csv(canonical_csv)
    evidence = {row["canonical_annotation_id"]: row for row in read_csv(independence_csv)}
    for row in rows:
        item = evidence.get(row.get("canonical_annotation_id", ""), {})
        row["independence_status"] = item.get("independence_status", "not_evaluable")
        row["independence_audit_status"] = item.get("independence_basis", "missing_independence_evidence")
    write_csv(canonical_csv, rows, list(rows[0]) if rows else None)


def materialize_c2_eligible_roster(
    completion_csv: Path, canonical_csv: Path, quality_csv: Path,
    geometry_loo_csv: Path, output_dir: Path, *, min_observed_support: int = 5,
    min_gt_support: int = 3, min_loo_support: int = 3,
) -> dict[str, Any]:
    """Build the strict, explicit roster consumed by candidate-only C2 design."""
    completion = {row["worker_id"]: row for row in read_csv(completion_csv)}
    by_worker: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in read_csv(canonical_csv):
        by_worker[row.get("worker_id", "")].append(row)
    quality = Counter(
        row.get("worker_id", "") for row in read_csv(quality_csv)
        if _truth(row.get("quality_evaluable"))
    )
    loo = Counter(
        row.get("worker_id", "") for row in read_csv(geometry_loo_csv)
        if int(float(row.get("peer_count_excluding_self") or 0)) > 0
    )
    output = []
    for worker, completed in sorted(completion.items(), key=lambda item: (0, int(item[0])) if item[0].isdigit() else (1, item[0])):
        rows = by_worker.get(worker, [])
        process_valid = [row for row in rows if not _truth(row.get("outside_assignment_submission")) and not _truth(row.get("duplicate_worker_task_submission"))]
        independence_valid = [row for row in process_valid if row.get("independence_status") == "independent"]
        structural_evaluable = sum(row.get("structural_validation_status") in {"passed", "failed_confirmed_worker_submission"} for row in independence_valid)
        observed = int(completed.get("observed_total_count") or 0)
        blockers = []
        if completed.get("completion_status") == "nonstarter": blockers.append("nonstarter")
        if observed < min_observed_support: blockers.append("insufficient_observed_support")
        if not process_valid: blockers.append("no_process_valid_support")
        if not independence_valid: blockers.append("no_independence_valid_support")
        if structural_evaluable == 0: blockers.append("structural_profile_not_evaluable")
        if quality[worker] < min_gt_support: blockers.append("insufficient_gt_support")
        if loo[worker] < min_loo_support: blockers.append("insufficient_loo_support")
        eligible = not blockers
        output.append({
            **completed, "gt_quality_support": quality[worker], "loo_support": loo[worker],
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
    write_csv(output_dir / "c2_eligible_roster_C1.csv", output)
    return {"n_workers": len(output), "n_eligible": sum(_truth(row["c2_candidate_eligible"]) for row in output), "n_excluded": sum(not _truth(row["c2_candidate_eligible"]) for row in output)}


def materialize_analysis_rosters(completion_csv: Path, canonical_csv: Path, output_dir: Path) -> dict[str, Any]:
    completion = read_csv(completion_csv)
    support = Counter(row.get("worker_id", "") for row in read_csv(canonical_csv) if not _truth(row.get("outside_assignment_submission")) and not _truth(row.get("duplicate_worker_task_submission")))
    assigned = [{**row, "roster_role": "assigned"} for row in completion]
    observed = [{**row, "roster_role": "observed"} for row in completion if int(row.get("observed_total_count") or 0) > 0]
    analysis = [{**row, "roster_role": "analysis", "local_process_valid_support": support[row["worker_id"]]} for row in completion if row.get("completion_status") != "nonstarter" and support[row["worker_id"]] > 0]
    write_csv(output_dir / "C1_assigned_roster.csv", assigned)
    write_csv(output_dir / "C1_observed_roster.csv", observed)
    write_csv(output_dir / "C1_analysis_roster.csv", analysis)
    return {"assigned": len(assigned), "observed": len(observed), "analysis": len(analysis)}


def materialize_three_track_worker_state(
    global_csv: Path, geometry_loo_csv: Path, structural_csv: Path,
    completion_csv: Path, output_dir: Path, quality_csv: Path | None = None,
) -> dict[str, Any]:
    globals_ = {row.get("worker_id", ""): row for row in read_csv(global_csv)}
    loo_by_worker: dict[str, list[float]] = defaultdict(list)
    for row in read_csv(geometry_loo_csv):
        for field in ("loo_boundary_median", "loo_wallwall_median"):
            try:
                loo_by_worker[row.get("worker_id", "")].append(float(row[field]))
            except (TypeError, ValueError):
                pass
    struct = defaultdict(lambda: {"opportunity": 0, "failure": 0})
    for row in read_csv(structural_csv):
        worker = row.get("worker_id", "")
        if row.get("structural_validation_status") in {"passed", "failed_confirmed_worker_submission"}:
            struct[worker]["opportunity"] += 1
        if row.get("failure_attribution") == "worker_caused_structural_failure":
            struct[worker]["failure"] += 1
    raw_quality: dict[str, list[float]] = defaultdict(list)
    for row in read_csv(quality_csv) if quality_csv else []:
        if not _truth(row.get("quality_evaluable")):
            continue
        for field in ("Q_GT_raw", "iou_2d", "iou"):
            try:
                raw_quality[row.get("worker_id", "")].append(float(row[field]))
                break
            except (KeyError, TypeError, ValueError):
                continue
    rows = []
    for completion in read_csv(completion_csv):
        worker = completion["worker_id"]
        values = loo_by_worker[worker]
        opportunity = struct[worker]["opportunity"]
        global_row = globals_.get(worker, {})
        rows.append({
            "worker_id": worker, "completion_status": completion.get("completion_status", ""),
            "Q_GT_raw_median": __import__("statistics").median(raw_quality[worker]) if raw_quality[worker] else global_row.get("Q_GT_raw", ""), "Q_GT_task_adjusted": global_row.get("Q_GT_task_adjusted", ""),
            "standard_error": global_row.get("Q_GT_standard_error", ""), "CI_lower": global_row.get("Q_GT_CI_lower", ""),
            "CI_upper": global_row.get("Q_GT_CI_upper", ""), "LCB": global_row.get("Q_GT_LCB", ""),
            "GT_support": global_row.get("GT_support", 0), "task_support": global_row.get("task_support", 0),
            "R_LOO_compatible": sum(values) / len(values) if values else "", "LOO_support": len(values) // 2,
            "F_struct": struct[worker]["failure"] / opportunity if opportunity else "",
            "F_struct_numerator": struct[worker]["failure"], "F_struct_denominator": opportunity,
            "worker_state_status": "provisional" if completion.get("completion_status") != "nonstarter" else "not_generated_nonstarter",
            "formal_frozen": False,
        })
    write_csv(output_dir / "c1_three_track_worker_state.csv", rows)
    summary = {"n_workers": len(rows), "n_profile_rows": sum(row["worker_state_status"] == "provisional" for row in rows), "formal_frozen": False}
    (output_dir / "c1_three_track_worker_state.summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return summary
