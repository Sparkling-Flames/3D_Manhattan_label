from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import os
import sys
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from statistics import median
from typing import Any


_PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from tools.analyze_quality import extract_data, load_active_logs, lookup_active_log_entry


DEFAULT_OUTPUT_DIR = "analysis_results/p1_exact_copy_low_time_audit"


@dataclass(frozen=True)
class AuditConfig:
    stage_filter: str = "P1"
    assume_p1_export: bool = False
    active_log_start: str | None = None
    active_log_end: str | None = None
    geometry_round_px: float = 0.5
    min_valid_tasks_for_worker: int = 10
    event_active_time_ratio: float = 0.25
    event_active_time_floor_sec: float = 10.0
    manual_review_min_events: int = 5
    manual_review_rate: float = 0.30
    fail_recommended_rate: float = 0.70
    fail_if_all_valid: bool = True
    allow_lead_time_primary: bool = False


def _bool_from_cli(value: str | bool) -> bool:
    if isinstance(value, bool):
        return value
    text = str(value).strip().lower()
    if text in {"1", "true", "yes", "y"}:
        return True
    if text in {"0", "false", "no", "n"}:
        return False
    raise argparse.ArgumentTypeError(f"Expected boolean value, got {value!r}")


def _safe_str(value: Any, default: str = "") -> str:
    if value is None:
        return default
    text = str(value).strip()
    return text if text else default


def _get_worker_id(annotation: dict[str, Any]) -> str:
    completed_by = annotation.get("completed_by")
    if isinstance(completed_by, dict):
        for key in ("id", "email", "username", "pk"):
            value = _safe_str(completed_by.get(key))
            if value:
                return value
        return "unknown"
    return _safe_str(completed_by, "unknown")


def _get_annotation_id(annotation: dict[str, Any], index: int) -> str:
    return _safe_str(annotation.get("id"), f"annotation_index_{index}")


def _get_project_id(task: dict[str, Any]) -> str:
    return _safe_str(task.get("project") or task.get("project_id"))


def _task_id(task: dict[str, Any], index: int) -> str:
    return _safe_str(task.get("id") or task.get("task_id"), f"task_index_{index}")


def _data(task: dict[str, Any]) -> dict[str, Any]:
    data = task.get("data")
    return data if isinstance(data, dict) else {}


def _task_label(task: dict[str, Any]) -> str:
    data = _data(task)
    for key in ("title", "base_task_id", "task_id", "image"):
        value = data.get(key)
        if value:
            return Path(str(value)).name
    return ""


def _stage_tokens(task: dict[str, Any]) -> str:
    data = _data(task)
    values = []
    for key in (
        "dataset_group",
        "condition",
        "final_role",
        "semi_role",
        "task_role",
        "round_id",
        "source_split",
    ):
        value = data.get(key)
        if value is not None:
            values.append(str(value))
    return " ".join(values).lower()


def _stage_filter_bucket(task: dict[str, Any], stage_filter: str, assume_p1_export: bool = False) -> tuple[bool, str]:
    filt = (stage_filter or "P1").strip().lower()
    if filt == "all":
        return True, "all"

    tokens = _stage_tokens(task)
    if filt in {"manual", "semi", "oos"}:
        return (filt in tokens), f"{filt}_token_only" if filt in tokens else "filtered_out"

    if filt in {"p1", "stage1", "prescreen"}:
        if "p1" in tokens or "stage1" in tokens or "prescreen" in tokens:
            return True, "explicit_p1"
        if "manual" in tokens:
            return True, "manual_token_only"
        if "semi" in tokens:
            return True, "semi_token_only"
        if "oos" in tokens:
            return True, "oos_token_only"
        if not tokens and assume_p1_export:
            return True, "unlabeled_included_assume_p1_export"
        if not tokens:
            return False, "unlabeled_excluded_requires_assume_p1_export"
        return False, "filtered_out"

    return (filt in tokens), f"{filt}_token" if filt in tokens else "filtered_out"


def canonical_geometry_hash(corners, round_px: float = 0.5) -> tuple[str, str, int]:
    if corners is None or len(corners) == 0:
        raise ValueError("missing_corner_geometry")
    if round_px <= 0:
        raise ValueError("geometry_round_px must be positive")

    canonical_points: list[tuple[float, float]] = []
    for point in corners:
        if len(point) < 2:
            raise ValueError("invalid_corner_point")
        x = float(point[0])
        y = float(point[1])
        if not math.isfinite(x) or not math.isfinite(y):
            raise ValueError("non_finite_corner_point")
        rx = round(x / round_px) * round_px
        ry = round(y / round_px) * round_px
        canonical_points.append((round(rx, 4), round(ry, 4)))

    if len(canonical_points) < 2:
        raise ValueError("too_few_corner_points")

    canonical_points.sort()
    payload = json.dumps(canonical_points, ensure_ascii=False, separators=(",", ":"))
    digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()
    return digest, payload, len(canonical_points)


def _load_export(path: Path) -> list[dict[str, Any]]:
    with path.open("r", encoding="utf-8") as f:
        payload = json.load(f)
    if not isinstance(payload, list):
        raise ValueError("Label Studio export JSON must be a list of tasks")
    return payload


def _active_log_path(active_log_file: str | None, active_log_dir: str | None) -> str | None:
    if active_log_file:
        return active_log_file
    return active_log_dir


def _active_entry_for_annotation(
    active_times: dict,
    project_id: str,
    task_id: str,
    worker_id: str,
    lead_time_seconds: float,
) -> tuple[float | None, str, str, str, int, int]:
    active_log_entry, match_status = lookup_active_log_entry(
        active_times,
        project_id,
        task_id,
        worker_id,
    )
    if active_log_entry:
        return (
            float(active_log_entry.get("active_time_value", 0.0)),
            "log",
            match_status,
            str(active_log_entry.get("active_time_source_file", "")),
            int(active_log_entry.get("active_time_session_count", 0)),
            int(active_log_entry.get("active_time_event_count", 0)),
        )
    if lead_time_seconds > 0:
        return (
            float(lead_time_seconds),
            "lead_time_fallback",
            "fallback_no_direct_log" if match_status == "missing" else f"fallback_{match_status}",
            "",
            0,
            0,
        )
    return (None, "missing", match_status, "", 0, 0)


def build_audit_rows(
    export_json: str | Path,
    active_log_path: str | None,
    config: AuditConfig,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    export_path = Path(export_json)
    tasks = _load_export(export_path)
    active_times = (
        load_active_logs(active_log_path, start_time=config.active_log_start, end_time=config.active_log_end)
        if active_log_path
        else {}
    )

    rows: list[dict[str, Any]] = []
    parse_error_count = 0
    filtered_task_count = 0
    stage_filter_breakdown: dict[str, int] = defaultdict(int)
    included_task_ids: set[str] = set()
    unknown_worker_count = 0

    for task_index, task in enumerate(tasks, start=1):
        include_task, stage_bucket = _stage_filter_bucket(task, config.stage_filter, config.assume_p1_export)
        stage_filter_breakdown[stage_bucket] += 1
        if not include_task:
            filtered_task_count += 1
            continue

        task_id = _task_id(task, task_index)
        included_task_ids.add(task_id)
        project_id = _get_project_id(task)
        data = _data(task)
        dataset_group = _safe_str(data.get("dataset_group"))
        condition = _safe_str(data.get("condition"))
        task_label = _task_label(task)
        annotations = task.get("annotations") or []
        if not isinstance(annotations, list):
            annotations = []

        for ann_index, ann in enumerate(annotations, start=1):
            if not isinstance(ann, dict):
                continue
            annotation_id = _get_annotation_id(ann, ann_index)
            worker_id = _get_worker_id(ann)
            if worker_id == "unknown":
                unknown_worker_count += 1
            lead_time_seconds = float(ann.get("lead_time", 0) or 0)
            active_time, active_time_source, match_status, source_file, session_count, event_count = _active_entry_for_annotation(
                active_times,
                project_id,
                task_id,
                worker_id,
                lead_time_seconds,
            )

            parse_error = ""
            geometry_hash = ""
            canonical_geometry = ""
            n_corners = 0
            is_valid_geometry = False
            try:
                corners, _poly, _choice_map, _quality = extract_data(ann.get("result", []))
                geometry_hash, canonical_geometry, n_corners = canonical_geometry_hash(
                    corners,
                    round_px=config.geometry_round_px,
                )
                is_valid_geometry = True
            except Exception as exc:
                parse_error = str(exc)
                parse_error_count += 1

            rows.append(
                {
                    "task_id": task_id,
                    "project_id": project_id,
                    "task_label": task_label,
                    "dataset_group": dataset_group,
                    "condition": condition,
                    "stage_filter_bucket": stage_bucket,
                    "annotation_id": annotation_id,
                    "worker_id": worker_id,
                    "is_valid_geometry": is_valid_geometry,
                    "parse_error": parse_error,
                    "n_corners": n_corners,
                    "geometry_hash": geometry_hash,
                    "canonical_geometry": canonical_geometry,
                    "active_time": "" if active_time is None else float(active_time),
                    "active_time_source": active_time_source,
                    "active_time_match_status": match_status,
                    "active_time_source_file": source_file,
                    "active_time_session_count": session_count,
                    "active_time_event_count": event_count,
                    "lead_time_seconds": lead_time_seconds,
                }
            )

    metadata = {
        "export_json": str(export_path),
        "n_tasks_in_export": len(tasks),
        "n_tasks_included": len(included_task_ids),
        "n_tasks_filtered_out": filtered_task_count,
        "n_annotation_rows": len(rows),
        "parse_error_count": parse_error_count,
        "active_log_path": active_log_path or "",
        "active_log_start": config.active_log_start or "",
        "active_log_end": config.active_log_end or "",
        "active_log_loaded": bool(active_times),
        "stage_filter": config.stage_filter,
        "assume_p1_export": config.assume_p1_export,
        "stage_filter_task_breakdown": dict(sorted(stage_filter_breakdown.items())),
        "unknown_worker_count": unknown_worker_count,
    }
    return rows, metadata


def apply_exact_copy_low_time_rules(
    rows: list[dict[str, Any]],
    config: AuditConfig,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    task_valid_rows: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        row["task_valid_annotation_count"] = 0
        row["task_median_active_time"] = ""
        row["low_time_threshold"] = ""
        row["same_hash_cluster_size"] = 0
        row["same_hash_annotation_count"] = 0
        row["same_hash_worker_count"] = 0
        row["is_exact_duplicate_geometry"] = False
        row["same_worker_duplicate_annotation_anomaly"] = False
        row["exact_copy_low_time_event"] = False
        row["fallback_low_time_duplicate_audit"] = False
        row["event_basis"] = ""
        if row.get("is_valid_geometry"):
            task_valid_rows[str(row["task_id"])].append(row)

    primary_event_count = 0
    fallback_audit_count = 0
    exact_duplicate_annotation_count = 0

    for task_id, valid_rows in task_valid_rows.items():
        hash_clusters: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for row in valid_rows:
            hash_clusters[str(row["geometry_hash"])].append(row)

        log_times = [
            float(row["active_time"])
            for row in valid_rows
            if row.get("active_time_source") == "log" and row.get("active_time") != ""
        ]
        task_median = float(median(log_times)) if log_times else None
        threshold = (
            max(config.event_active_time_floor_sec, config.event_active_time_ratio * task_median)
            if task_median is not None
            else None
        )

        for cluster in hash_clusters.values():
            annotation_count = len(cluster)
            worker_count = len({str(row.get("worker_id")) for row in cluster})
            is_same_worker_duplicate = annotation_count >= 2 and worker_count == 1
            is_duplicate_cluster = annotation_count >= 2 and worker_count >= 2 and len(valid_rows) >= 2
            for row in cluster:
                row["task_valid_annotation_count"] = len(valid_rows)
                row["same_hash_cluster_size"] = annotation_count
                row["same_hash_annotation_count"] = annotation_count
                row["same_hash_worker_count"] = worker_count
                row["task_median_active_time"] = "" if task_median is None else round(task_median, 6)
                row["low_time_threshold"] = "" if threshold is None else round(threshold, 6)
                row["is_exact_duplicate_geometry"] = bool(is_duplicate_cluster)
                row["same_worker_duplicate_annotation_anomaly"] = bool(is_same_worker_duplicate)

                if not is_duplicate_cluster:
                    if is_same_worker_duplicate:
                        row["event_basis"] = "same_worker_duplicate_annotation_export_anomaly"
                    continue
                exact_duplicate_annotation_count += 1

                active_time = row.get("active_time")
                if active_time == "" or active_time is None or threshold is None:
                    row["event_basis"] = "duplicate_geometry_missing_primary_active_time"
                    continue

                active_time_value = float(active_time)
                is_low_time = active_time_value <= float(threshold)
                if row.get("active_time_source") == "log" and is_low_time:
                    row["exact_copy_low_time_event"] = True
                    row["event_basis"] = "exact_geometry_duplicate+log_active_time_low"
                    primary_event_count += 1
                elif row.get("active_time_source") == "lead_time_fallback" and is_low_time:
                    row["fallback_low_time_duplicate_audit"] = True
                    row["event_basis"] = "exact_geometry_duplicate+lead_time_low_fallback_only"
                    fallback_audit_count += 1
                    if config.allow_lead_time_primary:
                        row["exact_copy_low_time_event"] = True
                        row["event_basis"] = "exact_geometry_duplicate+lead_time_low_allowed_primary"
                        primary_event_count += 1
                else:
                    row["event_basis"] = "exact_geometry_duplicate_time_not_low_or_not_primary"

    worker_rows: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        if row.get("is_valid_geometry"):
            worker_rows[str(row["worker_id"])].append(row)

    summaries: list[dict[str, Any]] = []
    for worker_id in sorted(worker_rows):
        wr = worker_rows[worker_id]
        valid_task_ids = {str(row["task_id"]) for row in wr}
        n_valid = len(valid_task_ids)
        n_exact_duplicate_tasks = len({row["task_id"] for row in wr if row.get("is_exact_duplicate_geometry")})
        n_events = len({row["task_id"] for row in wr if row.get("exact_copy_low_time_event")})
        n_log_tasks = len({row["task_id"] for row in wr if row.get("active_time_source") == "log"})
        event_rate = (n_events / n_valid) if n_valid else 0.0
        coverage = (n_log_tasks / n_valid) if n_valid else 0.0
        max_cluster = max([int(row.get("same_hash_cluster_size") or 0) for row in wr] or [0])

        insufficient = n_valid < config.min_valid_tasks_for_worker
        manual_review = False
        fail_recommended = False
        reasons: list[str] = []
        if insufficient:
            reasons.append(f"n_valid_tasks<{config.min_valid_tasks_for_worker}")
            recommended_action = "insufficient_support"
        else:
            if n_events >= config.manual_review_min_events:
                manual_review = True
                reasons.append(f"event_count>={config.manual_review_min_events}")
            if event_rate >= config.manual_review_rate:
                manual_review = True
                reasons.append(f"event_rate>={config.manual_review_rate:.2f}")
            if event_rate >= config.fail_recommended_rate:
                fail_recommended = True
                manual_review = True
                reasons.append(f"event_rate>={config.fail_recommended_rate:.2f}")
            if config.fail_if_all_valid and n_valid > 0 and n_events >= n_valid:
                fail_recommended = True
                manual_review = True
                reasons.append("all_valid_tasks_exact_copy_low_time")
            if fail_recommended:
                recommended_action = "fail_recommended"
            elif manual_review:
                recommended_action = "manual_review"
            elif n_events > 0:
                recommended_action = "warning"
                reasons.append("exact_copy_low_time_events_below_review_threshold")
            else:
                recommended_action = "no_action"
                reasons.append("no_exact_copy_low_time_events")

        summaries.append(
            {
                "worker_id": worker_id,
                "n_valid_tasks": n_valid,
                "n_exact_duplicate_tasks": n_exact_duplicate_tasks,
                "n_exact_copy_low_time_events": n_events,
                "exact_copy_low_time_rate": round(event_rate, 6),
                "max_same_hash_cluster_size": max_cluster,
                "active_time_source_coverage": round(coverage, 6),
                "manual_review_required": manual_review,
                "fail_recommended": fail_recommended,
                "recommended_action": recommended_action,
                "reason": ";".join(reasons),
            }
        )

    rule_summary = {
        "n_primary_exact_copy_low_time_events": primary_event_count,
        "n_fallback_low_time_duplicate_audit": fallback_audit_count,
        "n_exact_duplicate_annotation_rows": exact_duplicate_annotation_count,
        "n_workers": len(summaries),
        "n_workers_manual_review": sum(1 for row in summaries if row["manual_review_required"]),
        "n_workers_fail_recommended": sum(1 for row in summaries if row["fail_recommended"]),
    }
    return rows, summaries, rule_summary


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    fieldnames = list(rows[0].keys())
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def _write_report(path: Path, summary: dict[str, Any], config: AuditConfig) -> None:
    lines = [
        "# P1 Exact-Copy Low-Time Process-Integrity Audit",
        "",
        "## Scope",
        "",
        "- This is a process-integrity audit, not a geometry quality metric.",
        "- This is a high-precision exact-copy-low-time detector, not a complete collusion detector.",
        "- It checks only exact canonical corner-geometry duplicates combined with anomalously low primary active_time.",
        "- It does not implement near-duplicate, small-edit copy, IoU-similarity, or BoundaryRMSE-similarity detection.",
        "- It does not silently delete annotations or workers; outputs are warning / manual_review / fail_recommended only.",
        "",
        "## Timing Boundary",
        "",
        "- `active_time` from active logs is the primary timing source.",
        "- Label Studio `lead_time` is reported only as fallback/audit by default and is not mixed into the primary event rule.",
        "- `lead_time` can enter primary events only if the CLI explicitly enables it.",
        "- Active-log start/end bounds are recorded to prevent cross-round active_time accumulation.",
        "",
        "## Conservative Worker-Level Rule",
        "",
        "- A small number of low-time tasks does not trigger exclusion.",
        "- Semi-auto tasks with high-quality initialization can legitimately be fast.",
        "- Therefore review/fail decisions use worker-level event counts and rates, not a single-task low-time flag.",
        "",
        "## Default Thresholds Used",
        "",
        f"- `min_valid_tasks_for_worker`: {config.min_valid_tasks_for_worker}",
        f"- `event_active_time_ratio`: {config.event_active_time_ratio}",
        f"- `event_active_time_floor_sec`: {config.event_active_time_floor_sec}",
        f"- `manual_review_min_events`: {config.manual_review_min_events}",
        f"- `manual_review_rate`: {config.manual_review_rate}",
        f"- `fail_recommended_rate`: {config.fail_recommended_rate}",
        f"- `fail_if_all_valid`: {config.fail_if_all_valid}",
        f"- `geometry_round_px`: {config.geometry_round_px}",
        f"- `assume_p1_export`: {config.assume_p1_export}",
        f"- `active_log_start`: {config.active_log_start or ''}",
        f"- `active_log_end`: {config.active_log_end or ''}",
        "",
        "## Run Summary",
        "",
        f"- `n_tasks_in_export`: {summary.get('n_tasks_in_export')}",
        f"- `n_tasks_included`: {summary.get('n_tasks_included')}",
        f"- `n_tasks_filtered_out`: {summary.get('n_tasks_filtered_out')}",
        f"- `n_annotation_rows`: {summary.get('n_annotation_rows')}",
        f"- `parse_error_count`: {summary.get('parse_error_count')}",
        f"- `unknown_worker_count`: {summary.get('unknown_worker_count')}",
        f"- `stage_filter_task_breakdown`: `{json.dumps(summary.get('stage_filter_task_breakdown', {}), ensure_ascii=False)}`",
        f"- `n_primary_exact_copy_low_time_events`: {summary.get('n_primary_exact_copy_low_time_events')}",
        f"- `n_fallback_low_time_duplicate_audit`: {summary.get('n_fallback_low_time_duplicate_audit')}",
        f"- `n_workers_manual_review`: {summary.get('n_workers_manual_review')}",
        f"- `n_workers_fail_recommended`: {summary.get('n_workers_fail_recommended')}",
        "",
        "## Protocol Boundary",
        "",
        "- This audit does not change P1 manual / semi / OOS pool definitions.",
        "- This audit does not change `r_u^(0)`, `w_max`, blind-trust, or scope-gate formulas.",
        "- This audit does not upgrade PreScreen output into a formal routing profile.",
        "- Final exclusion decisions must be made by manual review or downstream admission summary logic.",
        "",
    ]
    if int(summary.get("unknown_worker_count") or 0) > 0:
        lines.extend(
            [
                "## Warnings",
                "",
                "- Unknown worker IDs were found. Review `completed_by` export fields before using worker-level recommendations.",
                "",
            ]
        )
    path.write_text("\n".join(lines), encoding="utf-8")


def run_audit(
    export_json: str | Path,
    output_dir: str | Path = DEFAULT_OUTPUT_DIR,
    active_log_path: str | None = None,
    config: AuditConfig | None = None,
) -> dict[str, Any]:
    cfg = config or AuditConfig()
    rows, metadata = build_audit_rows(export_json, active_log_path, cfg)
    rows, worker_summary, rule_summary = apply_exact_copy_low_time_rules(rows, cfg)

    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)

    event_path = output / "p1_exact_copy_low_time_event_audit.csv"
    worker_path = output / "p1_worker_independence_summary.csv"
    summary_path = output / "p1_exact_copy_low_time_summary.json"
    report_path = output / "p1_exact_copy_low_time_report.md"

    _write_csv(event_path, rows)
    _write_csv(worker_path, worker_summary)

    summary = {
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "tool": "tools/audit_p1_exact_copy_low_time.py",
        "config": cfg.__dict__,
        **metadata,
        **rule_summary,
        "outputs": {
            "event_audit_csv": str(event_path.as_posix()),
            "worker_summary_csv": str(worker_path.as_posix()),
            "summary_json": str(summary_path.as_posix()),
            "report_md": str(report_path.as_posix()),
        },
    }
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    _write_report(report_path, summary, cfg)
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Conservative P1 exact-copy-low-time process-integrity audit."
    )
    parser.add_argument("--export-json", required=True, help="Label Studio export JSON.")
    parser.add_argument("--active-log-dir", default=None, help="Directory containing active_times_*.jsonl.")
    parser.add_argument("--active-log-file", default=None, help="Concrete active_times_*.jsonl file.")
    parser.add_argument("--active-log-start", default=None, help="Inclusive server_received_at lower bound.")
    parser.add_argument("--active-log-end", default=None, help="Inclusive server_received_at upper bound.")
    parser.add_argument("--stage-filter", default="P1", help="P1/manual/semi/oos/all; default P1.")
    parser.add_argument(
        "--assume-p1-export",
        action="store_true",
        help="Allow unlabeled tasks to pass stage-filter=P1. Use only for known single-purpose P1 exports.",
    )
    parser.add_argument("--output-dir", default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--geometry-round-px", type=float, default=0.5)
    parser.add_argument("--min-valid-tasks-for-worker", type=int, default=10)
    parser.add_argument("--event-active-time-ratio", type=float, default=0.25)
    parser.add_argument("--event-active-time-floor-sec", type=float, default=10.0)
    parser.add_argument("--manual-review-min-events", type=int, default=5)
    parser.add_argument("--manual-review-rate", type=float, default=0.30)
    parser.add_argument("--fail-recommended-rate", type=float, default=0.70)
    parser.add_argument("--fail-if-all-valid", type=_bool_from_cli, default=True)
    parser.add_argument(
        "--allow-lead-time-primary",
        action="store_true",
        help="Allow low lead_time fallback to count as primary event. Off by default.",
    )
    args = parser.parse_args()

    cfg = AuditConfig(
        stage_filter=args.stage_filter,
        assume_p1_export=args.assume_p1_export,
        active_log_start=args.active_log_start,
        active_log_end=args.active_log_end,
        geometry_round_px=args.geometry_round_px,
        min_valid_tasks_for_worker=args.min_valid_tasks_for_worker,
        event_active_time_ratio=args.event_active_time_ratio,
        event_active_time_floor_sec=args.event_active_time_floor_sec,
        manual_review_min_events=args.manual_review_min_events,
        manual_review_rate=args.manual_review_rate,
        fail_recommended_rate=args.fail_recommended_rate,
        fail_if_all_valid=args.fail_if_all_valid,
        allow_lead_time_primary=args.allow_lead_time_primary,
    )
    active_path = _active_log_path(args.active_log_file, args.active_log_dir)
    summary = run_audit(args.export_json, args.output_dir, active_path, cfg)
    print(json.dumps(summary["outputs"], ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
