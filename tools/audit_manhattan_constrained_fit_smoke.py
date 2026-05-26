"""Read-only smoke audit for the M14 Manhattan constrained fitting core.

This utility consumes a Label Studio export JSON, builds current-preview paired
corners, runs a normal-only audit candidate pass, and also runs a
scope-independent geometry_debug pass on every annotation with parseable
keypoints. Scope vote is not adjudicated OOS. Outputs are smoke/probe sidecars
only: candidate deltas are not correction instructions, there is no writeback,
no formal g_t, no routing, no worker quality metric, and no P1/C1/C2/T1/V1
artifact role.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import sys
from collections import Counter
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tools.manhattan_constrained_fit import fit_manhattan_layout
from tools.manhattan_preview_compat import COMPATIBLE, check_preview_compatibility


AUDIT_VERSION = "manhattan_constrained_fit_smoke_audit_m15_v1"
VALID_SCOPE_ALIASES = {
    "normal",
    "oos_geometry",
    "oos_open_boundary",
    "oos_split_level",
    "oos_insufficient",
}
MAX_EXAMPLES = 12
LARGE_MOVE_THRESHOLD = 5.0
NUMERIC_SUMMARY_FIELDS = (
    "fit_residual",
    "manhattan_yaw_deg",
    "layout_height_candidate",
    "layout_height_spread",
    "max_abs_delta",
)
FOCUS_TASK_IDS = {"2948", "2949"}


def _as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _as_mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _as_bool(value: Any) -> bool | None:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"1", "true", "yes", "y"}:
            return True
        if normalized in {"0", "false", "no", "n"}:
            return False
    return None


def _load_tasks(path: Path) -> list[Mapping[str, Any]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(payload, list):
        return [task for task in payload if isinstance(task, Mapping)]
    if isinstance(payload, Mapping):
        for key in ("tasks", "items", "data"):
            maybe_tasks = payload.get(key)
            if isinstance(maybe_tasks, list):
                return [task for task in maybe_tasks if isinstance(task, Mapping)]
    raise ValueError(f"{path}: expected a Label Studio export list or task container")


def find_latest_export_for_date(export_root: Path, date: str) -> Path:
    candidates = [
        path
        for path in export_root.rglob("*.json")
        if date in path.name or date in str(path)
    ]
    if not candidates:
        raise FileNotFoundError(f"no Label Studio export JSON found under {export_root} for {date}")
    return max(candidates, key=lambda path: (path.stat().st_mtime, str(path)))


def _task_id(task: Mapping[str, Any]) -> Any:
    data = _as_mapping(task.get("data"))
    return task.get("id", data.get("task_id", data.get("base_task_id")))


def _annotation_id(annotation: Mapping[str, Any]) -> Any:
    return annotation.get("id", annotation.get("pk", annotation.get("unique_id")))


def _annotator_id(annotation: Mapping[str, Any]) -> Any:
    completed_by = annotation.get("completed_by")
    if isinstance(completed_by, Mapping):
        return completed_by.get("id", completed_by.get("email", completed_by.get("username")))
    return completed_by


def _result_value(result: Mapping[str, Any]) -> Mapping[str, Any]:
    return _as_mapping(result.get("value"))


def extract_scope(annotation: Mapping[str, Any]) -> str | None:
    aliases: list[str] = []
    for result in _as_list(annotation.get("result")):
        if not isinstance(result, Mapping):
            continue
        if result.get("type") != "choices" or result.get("from_name") != "scope":
            continue
        choices = _result_value(result).get("choices")
        if isinstance(choices, list):
            aliases.extend(str(choice).strip() for choice in choices if str(choice).strip())
        elif isinstance(choices, str) and choices.strip():
            aliases.append(choices.strip())
    if len(aliases) != 1:
        return None
    return aliases[0]


def extract_manhattan_assumable(
    task: Mapping[str, Any],
    annotation: Mapping[str, Any],
) -> tuple[bool, bool | None]:
    for source in (annotation, _as_mapping(task.get("data"))):
        if "manhattan_assumable" in source:
            return True, _as_bool(source.get("manhattan_assumable"))
    for result in _as_list(annotation.get("result")):
        if not isinstance(result, Mapping):
            continue
        if result.get("from_name") != "manhattan_assumable":
            continue
        value = _result_value(result)
        if "value" in value:
            return True, _as_bool(value.get("value"))
        choices = value.get("choices")
        if isinstance(choices, list) and choices:
            return True, _as_bool(choices[0])
        if isinstance(choices, str):
            return True, _as_bool(choices)
    return False, None


def extract_keypoints(annotation: Mapping[str, Any]) -> tuple[list[dict[str, Any]], int, int]:
    points: list[dict[str, Any]] = []
    parse_errors = 0
    keypoint_result_count = 0
    for idx, result in enumerate(_as_list(annotation.get("result"))):
        if not isinstance(result, Mapping):
            continue
        if result.get("type") != "keypointlabels" or result.get("from_name") != "kp":
            continue
        keypoint_result_count += 1
        value = _result_value(result)
        try:
            if "x" in value and "y" in value:
                x = float(value["x"])
                y = float(value["y"])
            else:
                wrapped = _as_mapping(value.get("value"))
                x = float(wrapped["x"])
                y = float(wrapped["y"])
        except (KeyError, TypeError, ValueError):
            parse_errors += 1
            continue
        points.append({"x": x, "y": y, "original_index": idx})
    return points, keypoint_result_count, parse_errors


def preview_result_to_ordered_pairs(preview_result: Any) -> list[dict[str, Any]]:
    ordered_pairs: list[dict[str, Any]] = []
    for pair in preview_result.ordered_corners:
        top = pair.p1 if pair.p1.y <= pair.p2.y else pair.p2
        bottom = pair.p2 if pair.p1.y <= pair.p2.y else pair.p1
        ordered_pairs.append(
            {
                "top": {"x": top.x_percent, "y": top.y_percent},
                "bottom": {"x": bottom.x_percent, "y": bottom.y_percent},
            }
        )
    return ordered_pairs


def _max_abs_delta(per_point_delta: Sequence[Mapping[str, Any]]) -> float | None:
    values: list[float] = []
    for row in per_point_delta:
        for field in ("top_dx", "top_dy", "bottom_dx", "bottom_dy"):
            value = row.get(field)
            if isinstance(value, (int, float)):
                values.append(abs(float(value)))
    return max(values) if values else None


def _percentile(values: Sequence[float], q: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    if len(ordered) == 1:
        return ordered[0]
    position = (len(ordered) - 1) * q
    lower = int(position)
    upper = min(lower + 1, len(ordered) - 1)
    fraction = position - lower
    return ordered[lower] * (1.0 - fraction) + ordered[upper] * fraction


def _numeric_summary(values: Sequence[float]) -> dict[str, float | int | None]:
    if not values:
        return {"count": 0, "median": None, "p90": None, "max": None}
    return {
        "count": len(values),
        "median": _percentile(values, 0.5),
        "p90": _percentile(values, 0.9),
        "max": max(values),
    }


def _review_priority(record: Mapping[str, Any]) -> str:
    if record.get("fit_status") != "ok":
        return "excluded"
    max_abs_delta = record.get("max_abs_delta")
    if record.get("fit_confidence") == "low" or (
        isinstance(max_abs_delta, (int, float)) and max_abs_delta >= LARGE_MOVE_THRESHOLD
    ):
        return "high"
    if record.get("direction_label") != "no_action":
        return "medium"
    return "low"


def _scope_ineligibility_reason(scope: str | None) -> str:
    if scope is None:
        return "scope_missing_or_unknown"
    if scope == "normal":
        return "audit_eligible"
    if scope in VALID_SCOPE_ALIASES:
        return scope
    return "scope_missing_or_unknown"


def _base_record(
    source_export: str,
    task: Mapping[str, Any],
    annotation: Mapping[str, Any],
    scope: str | None,
) -> dict[str, Any]:
    data = _as_mapping(task.get("data"))
    return {
        "audit_version": AUDIT_VERSION,
        "source_export": source_export,
        "task_id": _task_id(task),
        "base_task_id": data.get("base_task_id"),
        "title": data.get("title"),
        "image": data.get("image"),
        "annotation_id": _annotation_id(annotation),
        "annotator_id": _annotator_id(annotation),
        "scope": scope,
        "scope_vote": scope,
    }


def _apply_geometry_debug(record: dict[str, Any], points: Sequence[Mapping[str, Any]]) -> None:
    record.update(
        {
            "geometry_debug_preview_status": None,
            "geometry_debug_n_pairs": 0,
            "geometry_debug_fit_status": None,
            "geometry_debug_fit_confidence": None,
            "geometry_debug_fit_residual": None,
            "geometry_debug_max_abs_delta": None,
            "geometry_debug_layout_height_spread": None,
            "geometry_debug_problem_flag": False,
            "geometry_debug_problem_reason": None,
            "geometry_debug_scope_vote": record.get("scope"),
            "geometry_debug_not_oos_adjudication": True,
            "geometry_debug_direction_label": None,
            "geometry_debug_fitted_points": [],
            "geometry_debug_per_point_delta": [],
        }
    )
    if not points:
        record["geometry_debug_preview_status"] = "missing_keypoints"
        record["geometry_debug_problem_flag"] = True
        record["geometry_debug_problem_reason"] = "missing_keypoints"
        return

    preview = check_preview_compatibility(points)
    record["geometry_debug_preview_status"] = preview.status
    record["geometry_debug_n_pairs"] = len(preview.ordered_corners)
    if preview.status != COMPATIBLE:
        record["geometry_debug_problem_flag"] = True
        record["geometry_debug_problem_reason"] = preview.status
        return

    fit = fit_manhattan_layout(preview_result_to_ordered_pairs(preview))
    max_abs_delta = _max_abs_delta(fit.get("per_point_delta", []))
    record.update(
        {
            "geometry_debug_fit_status": fit.get("fit_status"),
            "geometry_debug_fit_confidence": fit.get("fit_confidence"),
            "geometry_debug_fit_residual": fit.get("fit_residual"),
            "geometry_debug_max_abs_delta": max_abs_delta,
            "geometry_debug_layout_height_spread": fit.get("layout_height_spread"),
            "geometry_debug_direction_label": fit.get("direction_label"),
            "geometry_debug_fitted_points": fit.get("fitted_points", []),
            "geometry_debug_per_point_delta": fit.get("per_point_delta", []),
        }
    )
    if fit.get("fit_status") != "ok":
        record["geometry_debug_problem_flag"] = True
        record["geometry_debug_problem_reason"] = str(fit.get("direction_label") or "fit_failed")
    elif isinstance(max_abs_delta, (int, float)) and max_abs_delta >= LARGE_MOVE_THRESHOLD:
        record["geometry_debug_problem_flag"] = True
        record["geometry_debug_problem_reason"] = "large_candidate_delta"


def audit_tasks(tasks: Iterable[Mapping[str, Any]], source_export: str) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    task_list = list(tasks)
    records: list[dict[str, Any]] = []
    scope_counts: Counter[str] = Counter()
    audit_ineligibility_counts: Counter[str] = Counter()
    preview_incompatibility_counts: Counter[str] = Counter()
    fit_status_counts: Counter[str] = Counter()
    fit_failure_counts: Counter[str] = Counter()
    direction_label_counts: Counter[str] = Counter()
    fit_confidence_counts: Counter[str] = Counter()

    manhattan_field_present = any(
        extract_manhattan_assumable(task, annotation)[0]
        for task in task_list
        for annotation in _as_list(task.get("annotations"))
        if isinstance(annotation, Mapping)
    )

    n_annotations = 0
    n_scope_normal = 0
    n_scope_oos = 0
    n_preview_compatible = 0
    n_preview_excluded = 0
    n_audit_eligible = 0
    n_audit_ineligible = 0
    n_fit_ok = 0
    n_fit_failed = 0
    n_large_move_candidates = 0

    for task in task_list:
        for annotation in _as_list(task.get("annotations")):
            if not isinstance(annotation, Mapping):
                continue
            n_annotations += 1
            scope = extract_scope(annotation)
            if scope in VALID_SCOPE_ALIASES:
                scope_counts[scope] += 1
            else:
                scope_counts["scope_missing_or_unknown"] += 1

            record = _base_record(source_export, task, annotation, scope)
            manhattan_present, manhattan_assumable = extract_manhattan_assumable(task, annotation)
            points, keypoint_results, parse_errors = extract_keypoints(annotation)
            record.update(
                {
                    "original_points": [
                        {"x": point.get("x"), "y": point.get("y"), "original_index": point.get("original_index")}
                        for point in points
                    ],
                    "n_keypoints": len(points),
                    "n_keypoint_results": keypoint_results,
                    "parse_error_count": parse_errors,
                    "preview_status": None,
                    "n_pairs": 0,
                    "fit_status": "ineligible",
                    "fit_confidence": None,
                    "direction_label": "ineligible",
                    "fit_residual": None,
                    "manhattan_yaw_deg": None,
                    "layout_height_candidate": None,
                    "layout_height_spread": None,
                    "max_abs_delta": None,
                    "warnings": [],
                    "review_priority": "excluded",
                }
            )
            record.update(
                {
                    "audit_eligible": False,
                    "audit_ineligibility_reason": None,
                }
            )

            if parse_errors:
                _apply_geometry_debug(record, [])
                record["geometry_debug_preview_status"] = "unparseable_keypoints"
                record["geometry_debug_problem_reason"] = "unparseable_keypoints"
            else:
                _apply_geometry_debug(record, points)

            eligible = True
            exclusion_reason = None
            if scope != "normal":
                eligible = False
                exclusion_reason = _scope_ineligibility_reason(scope)
                n_scope_oos += 1
            else:
                n_scope_normal += 1
            if eligible and manhattan_field_present:
                if not manhattan_present:
                    eligible = False
                    exclusion_reason = "missing_manhattan_assumable"
                elif manhattan_assumable is not True:
                    eligible = False
                    exclusion_reason = "not_manhattan_assumable"
            if parse_errors:
                eligible = False
                exclusion_reason = "unparseable_keypoints"
            if not points:
                eligible = False
                exclusion_reason = exclusion_reason or "missing_keypoints"

            if not eligible:
                record["audit_ineligibility_reason"] = exclusion_reason
                audit_ineligibility_counts[str(exclusion_reason)] += 1
                n_audit_ineligible += 1
                record["preview_status"] = exclusion_reason
                records.append(record)
                continue
            record["audit_eligible"] = True
            n_audit_eligible += 1

            preview = check_preview_compatibility(points)
            record["preview_status"] = preview.status
            record["n_pairs"] = len(preview.ordered_corners)
            if preview.status != COMPATIBLE:
                preview_incompatibility_counts[preview.status] += 1
                n_preview_excluded += 1
                records.append(record)
                continue
            n_preview_compatible += 1

            ordered_pairs = preview_result_to_ordered_pairs(preview)
            fit = fit_manhattan_layout(
                ordered_pairs,
                metadata={"scope": scope, "manhattan_assumable": manhattan_assumable}
                if manhattan_field_present
                else {"scope": scope},
            )
            max_abs_delta = _max_abs_delta(fit.get("per_point_delta", []))
            record.update(
                {
                    "fit_status": fit.get("fit_status"),
                    "fit_confidence": fit.get("fit_confidence"),
                    "direction_label": fit.get("direction_label"),
                    "fit_residual": fit.get("fit_residual"),
                    "manhattan_yaw_deg": fit.get("manhattan_yaw_deg"),
                    "layout_height_candidate": fit.get("layout_height_candidate"),
                    "layout_height_spread": fit.get("layout_height_spread"),
                    "max_abs_delta": max_abs_delta,
                    "warnings": fit.get("warnings", []),
                    "fit": fit,
                }
            )
            record["review_priority"] = _review_priority(record)
            if fit.get("fit_status") == "ok":
                n_fit_ok += 1
                if isinstance(max_abs_delta, (int, float)) and max_abs_delta >= LARGE_MOVE_THRESHOLD:
                    n_large_move_candidates += 1
            else:
                n_fit_failed += 1
                fit_failure_counts[str(fit.get("direction_label") or "fit_failed")] += 1
            fit_status_counts[str(fit.get("fit_status"))] += 1
            direction_label_counts[str(fit.get("direction_label"))] += 1
            fit_confidence_counts[str(fit.get("fit_confidence"))] += 1
            records.append(record)

    numeric_values = {field: [] for field in NUMERIC_SUMMARY_FIELDS}
    for record in records:
        if record.get("fit_status") != "ok":
            continue
        for field in NUMERIC_SUMMARY_FIELDS:
            value = record.get(field)
            if isinstance(value, (int, float)) and math.isfinite(value):
                numeric_values[field].append(float(value))

    examples = sorted(
        [
            {
                "task_id": record.get("task_id"),
                "annotation_id": record.get("annotation_id"),
                "annotator_id": record.get("annotator_id"),
                "review_priority": record.get("review_priority"),
                "direction_label": record.get("direction_label"),
                "fit_residual": record.get("fit_residual"),
                "max_abs_delta": record.get("max_abs_delta"),
                "warnings": record.get("warnings"),
            }
            for record in records
            if record.get("review_priority") in {"high", "medium"}
        ],
        key=lambda row: (
            0 if row["review_priority"] == "high" else 1,
            -(row["max_abs_delta"] or 0),
        ),
    )[:MAX_EXAMPLES]

    summary = {
        "audit_version": AUDIT_VERSION,
        "source_export": source_export,
        "n_tasks": len(task_list),
        "n_annotations": n_annotations,
        "n_scope_vote_normal": n_scope_normal,
        "n_scope_vote_oos": n_scope_oos,
        "scope_vote_distribution": dict(sorted(scope_counts.items())),
        "n_scope_normal": n_scope_normal,
        "n_scope_oos": n_scope_oos,
        "scope_alias_counts": dict(sorted(scope_counts.items())),
        "n_audit_eligible": n_audit_eligible,
        "n_audit_ineligible": n_audit_ineligible,
        "audit_ineligibility_counts": dict(sorted(audit_ineligibility_counts.items())),
        "n_preview_compatible": n_preview_compatible,
        "n_preview_excluded": n_preview_excluded,
        "preview_incompatibility_counts": dict(sorted(preview_incompatibility_counts.items())),
        "preview_exclusion_counts": dict(sorted(preview_incompatibility_counts.items())),
        "n_fit_ok": n_fit_ok,
        "n_fit_failed": n_fit_failed,
        "fit_status_counts": dict(sorted(fit_status_counts.items())),
        "fit_failure_counts": dict(sorted(fit_failure_counts.items())),
        "failure_reason_counts": dict(sorted(fit_failure_counts.items())),
        "direction_label_counts": dict(sorted(direction_label_counts.items())),
        "fit_confidence_counts": dict(sorted(fit_confidence_counts.items())),
        "fit_residual_summary": _numeric_summary(numeric_values["fit_residual"]),
        "yaw_deg_summary": _numeric_summary(numeric_values["manhattan_yaw_deg"]),
        "layout_height_candidate_summary": _numeric_summary(numeric_values["layout_height_candidate"]),
        "layout_height_spread_summary": _numeric_summary(numeric_values["layout_height_spread"]),
        "abs_delta_summary": _numeric_summary(numeric_values["max_abs_delta"]),
        "n_large_move_candidates": n_large_move_candidates,
        "top_candidate_examples": examples,
        "audit_notes": [
            "smoke-only / dev-only audit",
            "scope vote is not adjudicated OOS",
            "geometry_debug_not_oos_adjudication=true",
            "candidate deltas are not correction instructions",
            "no writeback",
            "no formal g_t",
            "no routing",
            "no worker quality metric",
            "no P1/C1/C2/T1/V1 artifact",
        ],
    }
    return records, summary


def _write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _write_jsonl(path: Path, records: Sequence[Mapping[str, Any]]) -> None:
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        for record in records:
            handle.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")


def _write_candidates_csv(path: Path, records: Sequence[Mapping[str, Any]]) -> None:
    fields = [
        "task_id",
        "annotation_id",
        "annotator_id",
        "scope",
        "n_pairs",
        "fit_status",
        "fit_confidence",
        "direction_label",
        "fit_residual",
        "manhattan_yaw_deg",
        "layout_height_candidate",
        "layout_height_spread",
        "max_abs_delta",
        "warnings",
        "review_priority",
    ]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for record in records:
            row = {field: record.get(field) for field in fields}
            row["warnings"] = ";".join(str(item) for item in _as_list(record.get("warnings")))
            writer.writerow(row)


def _write_geometry_debug_annotation_csv(path: Path, records: Sequence[Mapping[str, Any]]) -> None:
    fields = [
        "task_id",
        "annotation_id",
        "annotator_id",
        "scope",
        "geometry_debug_scope_vote",
        "geometry_debug_not_oos_adjudication",
        "geometry_debug_preview_status",
        "geometry_debug_n_pairs",
        "geometry_debug_fit_status",
        "geometry_debug_fit_confidence",
        "geometry_debug_fit_residual",
        "geometry_debug_max_abs_delta",
        "geometry_debug_layout_height_spread",
        "geometry_debug_problem_flag",
        "geometry_debug_problem_reason",
        "audit_eligible",
        "audit_ineligibility_reason",
    ]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for record in records:
            writer.writerow({field: record.get(field) for field in fields})


def _geometry_debug_task_rows(records: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[str, list[Mapping[str, Any]]] = {}
    for record in records:
        grouped.setdefault(str(record.get("task_id")), []).append(record)

    rows: list[dict[str, Any]] = []
    for task_id in sorted(grouped):
        task_records = grouped[task_id]
        scope_distribution = Counter(str(record.get("scope") or "scope_missing_or_unknown") for record in task_records)
        problem_distribution = Counter(
            str(record.get("geometry_debug_problem_reason") or "none") for record in task_records
        )
        rows.append(
            {
                "task_id": task_id,
                "n_annotations": len(task_records),
                "scope_vote_distribution": json.dumps(dict(sorted(scope_distribution.items())), ensure_ascii=False),
                "scope_distribution": json.dumps(dict(sorted(scope_distribution.items())), ensure_ascii=False),
                "n_geometry_debug_problem": sum(
                    bool(record.get("geometry_debug_problem_flag")) for record in task_records
                ),
                "geometry_debug_problem_distribution": json.dumps(
                    dict(sorted(problem_distribution.items())),
                    ensure_ascii=False,
                ),
                "not_oos_adjudication": True,
            }
        )
    return rows


def _write_geometry_debug_task_csv(path: Path, records: Sequence[Mapping[str, Any]]) -> None:
    rows = _geometry_debug_task_rows(records)
    fields = [
        "task_id",
        "n_annotations",
        "scope_vote_distribution",
        "scope_distribution",
        "n_geometry_debug_problem",
        "geometry_debug_problem_distribution",
        "not_oos_adjudication",
    ]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def _json_cell(value: Any) -> str:
    if value in (None, [], {}):
        return ""
    return json.dumps(value, ensure_ascii=False, sort_keys=True)


def _review_question(record: Mapping[str, Any]) -> str:
    reason = record.get("geometry_debug_problem_reason")
    preview_status = record.get("geometry_debug_preview_status")
    max_abs_delta = record.get("geometry_debug_max_abs_delta")
    if preview_status and preview_status != COMPATIBLE:
        return "Inspect whether current keypoint geometry is parseable by the preview-compatible pairing rule."
    if reason == "self_crossing_candidate":
        return "Inspect whether the fitted Manhattan candidate crosses itself; this is geometry debug, not OOS adjudication."
    if isinstance(max_abs_delta, (int, float)) and max_abs_delta >= LARGE_MOVE_THRESHOLD:
        return "Inspect whether the large candidate delta indicates unstable Manhattan fit; deltas are not correction instructions."
    if str(record.get("task_id")) in FOCUS_TASK_IDS:
        return "Focused task-level Manhattan stability inspection row; compare scope vote and geometry debug separately."
    return "Geometry debug review candidate."


def _is_geometry_review_candidate(record: Mapping[str, Any]) -> bool:
    max_abs_delta = record.get("geometry_debug_max_abs_delta")
    return (
        bool(record.get("geometry_debug_problem_flag"))
        or (isinstance(max_abs_delta, (int, float)) and max_abs_delta >= LARGE_MOVE_THRESHOLD)
        or record.get("geometry_debug_problem_reason") == "self_crossing_candidate"
        or record.get("geometry_debug_preview_status") not in {None, COMPATIBLE}
        or str(record.get("task_id")) in FOCUS_TASK_IDS
    )


def _review_candidate_record(record: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "task_id": record.get("task_id"),
        "annotation_id": record.get("annotation_id"),
        "annotator_id": record.get("annotator_id"),
        "scope_vote": record.get("scope_vote"),
        "n_keypoints": record.get("n_keypoints"),
        "preview_status": record.get("geometry_debug_preview_status"),
        "fit_status": record.get("geometry_debug_fit_status"),
        "fit_confidence": record.get("geometry_debug_fit_confidence"),
        "max_abs_delta": record.get("geometry_debug_max_abs_delta"),
        "layout_height_spread": record.get("geometry_debug_layout_height_spread"),
        "problem_reason": record.get("geometry_debug_problem_reason"),
        "original_points": record.get("original_points", []),
        "fitted_points": record.get("geometry_debug_fitted_points", []),
        "per_point_delta": record.get("geometry_debug_per_point_delta", []),
        "review_question": _review_question(record),
        "not_oos_adjudication": True,
    }


def _geometry_review_candidates(records: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    return [_review_candidate_record(record) for record in records if _is_geometry_review_candidate(record)]


def _write_geometry_review_candidates_csv(path: Path, rows: Sequence[Mapping[str, Any]]) -> None:
    fields = [
        "task_id",
        "annotation_id",
        "annotator_id",
        "scope_vote",
        "n_keypoints",
        "preview_status",
        "fit_status",
        "fit_confidence",
        "max_abs_delta",
        "layout_height_spread",
        "problem_reason",
        "original_points",
        "fitted_points",
        "per_point_delta",
        "review_question",
        "not_oos_adjudication",
    ]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            csv_row = {field: row.get(field) for field in fields}
            for field in ("original_points", "fitted_points", "per_point_delta"):
                csv_row[field] = _json_cell(csv_row[field])
            writer.writerow(csv_row)


def _render_geometry_review_report(
    rows: Sequence[Mapping[str, Any]],
    records: Sequence[Mapping[str, Any]],
    summary: Mapping[str, Any],
) -> str:
    problem_count = sum(1 for row in rows if row.get("problem_reason"))
    lines = [
        "# Manhattan geometry-debug review report",
        "",
        "This review package is smoke-only / dev-only. OOS vote is not final OOS adjudication. "
        "Candidate deltas are not correction instructions; no writeback, no formal g_t, no routing, "
        "and no P1/C1/C2/T1/V1 artifact role.",
        "",
        f"- source_export: `{summary.get('source_export')}`",
        f"- n_review_candidates: {len(rows)}",
        f"- n_review_candidates_with_problem_reason: {problem_count}",
        f"- scope_vote_distribution: `{summary.get('scope_vote_distribution')}`",
        f"- audit_ineligibility_counts: `{summary.get('audit_ineligibility_counts')}`",
        f"- preview_incompatibility_counts: `{summary.get('preview_incompatibility_counts')}`",
        f"- fit_failure_counts: `{summary.get('fit_failure_counts')}`",
        "",
        "## Review candidate policy",
        "",
        "Rows are included when geometry_debug has a problem flag, max_abs_delta >= 5, "
        "self_crossing_candidate, preview incompatibility, or task_id is 2948/2949. "
        "Scope vote and geometry problem are separate columns.",
        "",
        "## Focus: task 2948",
        "",
    ]
    lines.extend(_focus_task_lines(records, "2948"))
    lines.extend(["", "## Focus: task 2949", ""])
    lines.extend(_focus_task_lines(records, "2949"))
    return "\n".join(lines) + "\n"


def _render_report(summary: Mapping[str, Any]) -> str:
    lines = [
        "# Manhattan constrained fit smoke report",
        "",
        "This is smoke-only / dev-only. Candidate deltas are not correction instructions. "
        "There is no annotation writeback, no formal g_t, no routing, no worker quality "
        "metric, and no P1/C1/C2/T1/V1 artifact role.",
        "",
        f"- source_export: `{summary.get('source_export')}`",
        f"- n_tasks: {summary.get('n_tasks')}",
        f"- n_annotations: {summary.get('n_annotations')}",
        f"- n_scope_vote_normal: {summary.get('n_scope_vote_normal')}",
        f"- n_scope_vote_oos: {summary.get('n_scope_vote_oos')}",
        f"- scope_vote_distribution: `{summary.get('scope_vote_distribution')}`",
        f"- n_preview_compatible: {summary.get('n_preview_compatible')}",
        f"- n_preview_excluded: {summary.get('n_preview_excluded')}",
        f"- n_fit_ok: {summary.get('n_fit_ok')}",
        f"- n_fit_failed: {summary.get('n_fit_failed')}",
        f"- n_large_move_candidates: {summary.get('n_large_move_candidates')}",
        "",
        "## Main counts",
        "",
        f"- audit_ineligibility_counts: `{summary.get('audit_ineligibility_counts')}`",
        f"- preview_incompatibility_counts: `{summary.get('preview_incompatibility_counts')}`",
        f"- fit_failure_counts: `{summary.get('fit_failure_counts')}`",
        f"- direction_label_counts: `{summary.get('direction_label_counts')}`",
        f"- fit_confidence_counts: `{summary.get('fit_confidence_counts')}`",
        "",
        "## Movement statistics",
        "",
        f"- fit_residual_summary: `{summary.get('fit_residual_summary')}`",
        f"- yaw_deg_summary: `{summary.get('yaw_deg_summary')}`",
        f"- layout_height_candidate_summary: `{summary.get('layout_height_candidate_summary')}`",
        f"- layout_height_spread_summary: `{summary.get('layout_height_spread_summary')}`",
        f"- abs_delta_summary: `{summary.get('abs_delta_summary')}`",
        "",
        "## Candidate examples",
        "",
    ]
    for example in _as_list(summary.get("top_candidate_examples")):
        lines.append(f"- `{example}`")
    return "\n".join(lines) + "\n"


def _render_geometry_debug_report(records: Sequence[Mapping[str, Any]], summary: Mapping[str, Any]) -> str:
    lines = [
        "# Manhattan constrained fit geometry debug report",
        "",
        "This report is smoke-only / dev-only. A scope vote is not adjudicated OOS. "
        "Majority OOS is scope_distribution / disagreement evidence only. Geometry "
        "debug runs on parseable keypoints regardless of scope. Candidate deltas are "
        "not correction instructions; no writeback, no formal g_t, no routing, and "
        "no P1/C1/C2/T1/V1 artifact role.",
        "",
        f"- source_export: `{summary.get('source_export')}`",
        f"- audit_ineligibility_counts: `{summary.get('audit_ineligibility_counts')}`",
        f"- preview_incompatibility_counts: `{summary.get('preview_incompatibility_counts')}`",
        f"- fit_failure_counts: `{summary.get('fit_failure_counts')}`",
        "",
        "## Focus: task 2948",
        "",
    ]
    lines.extend(_focus_task_lines(records, "2948"))
    lines.extend(["", "## Focus: task 2949", ""])
    lines.extend(_focus_task_lines(records, "2949"))
    return "\n".join(lines) + "\n"


def _focus_task_lines(records: Sequence[Mapping[str, Any]], task_id: str) -> list[str]:
    rows = [record for record in records if str(record.get("task_id")) == task_id]
    if not rows:
        return [f"- task {task_id}: no rows present in this smoke export."]
    out = [
        "| annotator_id | annotation_id | scope vote | preview status | geometry_debug fit status | max delta | geometry problem | problem reason |",
        "| --- | --- | --- | --- | --- | ---: | --- | --- |",
    ]
    for record in rows:
        out.append(
            "| {annotator} | {annotation} | {scope} | {preview} | {fit} | {delta} | {problem} | {reason} |".format(
                annotator=record.get("annotator_id"),
                annotation=record.get("annotation_id"),
                scope=record.get("geometry_debug_scope_vote"),
                preview=record.get("geometry_debug_preview_status"),
                fit=record.get("geometry_debug_fit_status"),
                delta=record.get("geometry_debug_max_abs_delta"),
                problem="problem" if record.get("geometry_debug_problem_flag") else "non-problem",
                reason=record.get("geometry_debug_problem_reason"),
            )
        )
    out.append("")
    out.append("Note: task-level scope votes here are not OOS adjudication.")
    return out


def _write_readme(path: Path, date: str, source_export: str) -> None:
    path.write_text(
        "\n".join(
            [
                "# Manhattan constrained fit smoke outputs",
                "",
                f"Generated from `{source_export}` for smoke date `{date}`.",
                "",
                "These files are smoke/probe sidecar outputs only.",
                "Scope vote is not adjudicated OOS; task-level OOS requires expert adjudication or an explicit adjudication artifact.",
                "Geometry debug rows run on parseable keypoints regardless of scope vote.",
                "Geometry debug review candidates are task-level Manhattan stability inspection aids, not adjudication.",
                "Candidate deltas are not correction instructions.",
                "No annotation writeback was performed.",
                "This directory is not formal `g_t`, not routing input, not a worker quality metric,",
                "and not a `P1/C1/C2/T1/V1` artifact.",
                "",
            ]
        ),
        encoding="utf-8",
    )


def write_outputs(records: Sequence[Mapping[str, Any]], summary: Mapping[str, Any], output_dir: Path, date: str) -> dict[str, str]:
    output_dir.mkdir(parents=True, exist_ok=True)
    review_candidates = _geometry_review_candidates(records)
    paths = {
        "records": output_dir / f"smoke_fit_records_{date}.jsonl",
        "summary": output_dir / f"smoke_fit_summary_{date}.json",
        "candidates": output_dir / f"smoke_fit_candidates_{date}.csv",
        "report": output_dir / f"smoke_fit_report_{date}.md",
        "geometry_debug_by_annotation": output_dir / f"smoke_geometry_debug_by_annotation_{date}.csv",
        "geometry_debug_by_task": output_dir / f"smoke_geometry_debug_by_task_{date}.csv",
        "geometry_debug_report": output_dir / f"smoke_geometry_debug_report_{date}.md",
        "geometry_debug_review_candidates_csv": output_dir / f"smoke_geometry_debug_review_candidates_{date}.csv",
        "geometry_debug_review_candidates_jsonl": output_dir / f"smoke_geometry_debug_review_candidates_{date}.jsonl",
        "geometry_debug_review_report": output_dir / f"smoke_geometry_debug_review_report_{date}.md",
        "readme": output_dir / "README.md",
    }
    _write_jsonl(paths["records"], records)
    _write_json(paths["summary"], summary)
    _write_candidates_csv(paths["candidates"], records)
    paths["report"].write_text(_render_report(summary), encoding="utf-8")
    _write_geometry_debug_annotation_csv(paths["geometry_debug_by_annotation"], records)
    _write_geometry_debug_task_csv(paths["geometry_debug_by_task"], records)
    paths["geometry_debug_report"].write_text(
        _render_geometry_debug_report(records, summary),
        encoding="utf-8",
    )
    _write_geometry_review_candidates_csv(paths["geometry_debug_review_candidates_csv"], review_candidates)
    _write_jsonl(paths["geometry_debug_review_candidates_jsonl"], review_candidates)
    paths["geometry_debug_review_report"].write_text(
        _render_geometry_review_report(review_candidates, records, summary),
        encoding="utf-8",
    )
    _write_readme(paths["readme"], date, str(summary.get("source_export")))
    return {key: str(path) for key, path in paths.items()}


def audit_export(input_path: Path, output_dir: Path, date: str) -> tuple[list[dict[str, Any]], dict[str, Any], dict[str, str]]:
    records, summary = audit_tasks(_load_tasks(input_path), source_export=str(input_path))
    paths = write_outputs(records, summary, output_dir, date)
    return records, summary, paths


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--input", type=Path, help="Read-only Label Studio export JSON.")
    source.add_argument(
        "--auto-latest-date",
        help="Search export_label/ locally and select the most likely export JSON for this date.",
    )
    parser.add_argument(
        "--export-root",
        type=Path,
        default=Path("export_label"),
        help="Local export root used with --auto-latest-date.",
    )
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--date", required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_arg_parser().parse_args(argv)
    input_path = args.input
    if input_path is None:
        input_path = find_latest_export_for_date(args.export_root, args.auto_latest_date)
    _, summary, paths = audit_export(input_path, args.output_dir, args.date)
    print(json.dumps({"summary": summary, "outputs": paths}, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
