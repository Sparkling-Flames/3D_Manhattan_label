"""Materialize C1 operational audits that must not depend on canonical eligibility."""

from __future__ import annotations

import csv
import json
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from tools.thesis_main.analysis.geometry_consensus.representation import normalize_geometry
from tools.thesis_main.analysis.failure_disposition import c1_failure_fields


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
        parse_or_system = parsed["reason"] in {"shape_invalid", "non_finite"} or bool(annotation.get("parse_error"))
        status = "passed" if parsed["valid"] else "failed_system_or_parser" if parse_or_system else "failed_worker_attributable"
        rows.append({
            "project_id": annotation.get("project_id", ""), "ls_runtime_task_id": annotation.get("ls_runtime_task_id", ""),
            "annotation_id": annotation.get("annotation_id", ""), "canonical_annotation_id": geometry.get("canonical_annotation_id", ""),
            "worker_id": geometry.get("worker_id", ""), "task_id": geometry.get("task_id", ""),
            "geometry_parse_status": "parsed" if not parse_or_system else "failed", "pairing_valid": parsed.get("n_pairs", 0) >= 2,
            "corner_count_valid": parsed.get("n_points", 0) >= 4 and parsed.get("n_points", 0) % 2 == 0,
            "topology_valid": parsed["valid"], "polygon_valid": parsed["valid"],
            "structural_validation_status": status, "structural_failure_reason": parsed["reason"],
            "worker_attributable": status == "failed_worker_attributable",
            "independence_status": annotation.get("independence_status", "not_evaluable"),
            "failure_attribution": "none" if status == "passed" else "worker_caused_structural_failure" if status == "failed_worker_attributable" else "not_evaluable",
            "worker_reliability_eligibility": status == "passed" and annotation.get("independence_status") == "independent",
        })
    write_csv(output_dir / "structural_validation_audit.csv", rows)
    counts = Counter(row["structural_validation_status"] for row in rows)
    failures = Counter(row["failure_attribution"] for row in rows)
    return {"n_rows": len(rows), "structural_status_counts": dict(counts), "failure_attribution_counts": dict(failures)}


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
        classification = "true_unassigned_submission" if mapping_ok else "runtime_mapping_alias" if row.get("task_id") and row.get("base_task_id") else "unknown"
        rows.append({
            "annotation_id": row.get("annotation_id", ""), "worker_id": row.get("worker_id", ""),
            "runtime_task_id": row.get("ls_runtime_task_id", ""), "base_task_id": row.get("base_task_id", ""),
            "project_id": row.get("project_id", ""), "condition": row.get("condition", ""),
            "expected_assignment": False, "mapping_status": f"{row.get('planned_mapping_status', '')};{row.get('runtime_binding_status', '')}",
            "classification": classification,
            "recommended_disposition": "forensic_process_audit_exclude_quality" if classification == "true_unassigned_submission" else "pending_manual_mapping_review",
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


def materialize_c2_eligible_roster(
    completion_csv: Path, canonical_csv: Path, quality_csv: Path,
    geometry_loo_csv: Path, output_dir: Path, *, min_observed_support: int = 1,
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
        process_ok = bool(rows) and not any(
            _truth(row.get("outside_assignment_submission")) or _truth(row.get("duplicate_worker_task_submission"))
            for row in rows
        )
        independence_ok = bool(rows) and all(row.get("independence_status") == "independent" for row in rows)
        structural_evaluable = sum(row.get("structural_validation_status") in {"passed", "failed_worker_attributable"} for row in rows)
        observed = int(completed.get("observed_total_count") or 0)
        blockers = []
        if completed.get("completion_status") == "nonstarter": blockers.append("nonstarter")
        if observed < min_observed_support: blockers.append("insufficient_observed_support")
        if not process_ok: blockers.append("process_not_cleared")
        if not independence_ok: blockers.append("independence_not_frozen")
        if structural_evaluable == 0: blockers.append("structural_profile_not_evaluable")
        eligible = not blockers
        output.append({
            **completed, "gt_quality_support": quality[worker], "loo_support": loo[worker],
            "process_eligible": process_ok, "independence_eligible": independence_ok,
            "structural_profile_evaluable_count": structural_evaluable,
            "profile_evaluable": observed >= min_observed_support and structural_evaluable > 0,
            "c2_candidate_eligible": eligible, "c2_eligible": eligible,
            "candidate_exclusion_reason": ";".join(blockers),
        })
    write_csv(output_dir / "c2_eligible_roster_C1.csv", output)
    return {"n_workers": len(output), "n_eligible": sum(_truth(row["c2_candidate_eligible"]) for row in output), "n_excluded": sum(not _truth(row["c2_candidate_eligible"]) for row in output)}
