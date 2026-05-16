"""Read-only smoke export probe for the experiment-outside Manhattan toolchain.

This utility inspects Label Studio smoke exports and summarizes whether their
keypoints can be parsed by the current 3D preview compatibility parser. It is a
read-only probe: no UI integration, no Label Studio integration, no export
modification, no write back, no routing, no formal g_t, no correctness claim,
and no worker-facing guidance. Its output is a smoke/probe summary only and is
not a P1/C1/C2/T1/V1 artifact.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any, Iterable, Mapping

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tools.manhattan_preview_compat import (
    FAILURE_DUPLICATE,
    FAILURE_ODD_KEYPOINT,
    FAILURE_WRAPAROUND,
    check_preview_compatibility,
)
from tools.manhattan_geometry_residual import compute_m1_residual
from tools.manhattan_preview_suggestions import build_preview_suggestion_candidates


PROBE_VERSION = "manhattan_smoke_export_probe_v1"
VALID_SCOPE_ALIASES = {
    "normal",
    "oos_geometry",
    "oos_open_boundary",
    "oos_split_level",
    "oos_insufficient",
}
MAX_EXAMPLES = 10
RESIDUAL_NUMERIC_FIELDS = (
    "x_spacing_cv",
    "ceiling_y_range",
    "floor_y_range",
    "wall_height_range",
    "vertical_pair_x_residual",
)


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


def _as_list(value: Any) -> list[Any]:
    if isinstance(value, list):
        return value
    return []


def _as_mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _load_tasks(path: Path) -> list[Mapping[str, Any]]:
    with path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    if isinstance(payload, list):
        return [task for task in payload if isinstance(task, Mapping)]
    if isinstance(payload, Mapping):
        for key in ("tasks", "items", "data"):
            maybe_tasks = payload.get(key)
            if isinstance(maybe_tasks, list):
                return [task for task in maybe_tasks if isinstance(task, Mapping)]
    raise ValueError(f"{path}: expected a Label Studio export list or a dict containing tasks")


def _result_value(result: Mapping[str, Any]) -> Mapping[str, Any]:
    return _as_mapping(result.get("value"))


def _extract_xy(value: Mapping[str, Any]) -> tuple[float, float, bool] | None:
    if "x" in value and "y" in value:
        return float(value["x"]), float(value["y"]), False
    wrapped = _as_mapping(value.get("value"))
    if "x" in wrapped and "y" in wrapped:
        return float(wrapped["x"]), float(wrapped["y"]), True
    return None


def extract_keypoints(annotation: Mapping[str, Any]) -> tuple[list[dict[str, Any]], int, int]:
    """Extract current smoke keypoints from one annotation.

    Returns (points, keypoint_result_count, wrapped_value_count).
    """

    points: list[dict[str, Any]] = []
    keypoint_result_count = 0
    wrapped_value_count = 0
    for idx, result in enumerate(_as_list(annotation.get("result"))):
        if not isinstance(result, Mapping):
            continue
        if result.get("type") != "keypointlabels" or result.get("from_name") != "kp":
            continue
        keypoint_result_count += 1
        xy = _extract_xy(_result_value(result))
        if xy is None:
            continue
        x, y, used_wrapped_value = xy
        if used_wrapped_value:
            wrapped_value_count += 1
        points.append({"x": x, "y": y, "original_index": idx})
    return points, keypoint_result_count, wrapped_value_count


def extract_scope_aliases(annotation: Mapping[str, Any]) -> list[str]:
    aliases: list[str] = []
    for result in _as_list(annotation.get("result")):
        if not isinstance(result, Mapping):
            continue
        if result.get("type") != "choices" or result.get("from_name") != "scope":
            continue
        value = _result_value(result)
        choices = value.get("choices")
        if isinstance(choices, list):
            aliases.extend(str(choice).strip() for choice in choices if str(choice).strip())
        elif isinstance(choices, str) and choices.strip():
            aliases.append(choices.strip())
    return aliases


def extract_manhattan_assumable(
    task: Mapping[str, Any],
    annotation: Mapping[str, Any],
) -> tuple[bool, bool | None]:
    """Return whether manhattan_assumable is present and its parsed value."""

    for source in (annotation, _as_mapping(task.get("data"))):
        if "manhattan_assumable" in source:
            return True, _as_bool(source.get("manhattan_assumable"))

    for result in _as_list(annotation.get("result")):
        if not isinstance(result, Mapping):
            continue
        if result.get("from_name") != "manhattan_assumable":
            continue
        value = _result_value(result)
        for key in ("value", "text"):
            if key in value:
                return True, _as_bool(value.get(key))
        choices = value.get("choices")
        if isinstance(choices, list) and choices:
            return True, _as_bool(choices[0])
        if isinstance(choices, str):
            return True, _as_bool(choices)
    return False, None


def _primary_scope_reason(scope_aliases: list[str]) -> str:
    if not scope_aliases:
        return "scope_missing"
    if len(scope_aliases) != 1:
        return "scope_ambiguous"
    scope = scope_aliases[0]
    if scope not in VALID_SCOPE_ALIASES:
        return "scope_unknown"
    return scope


def _audit_eligibility(
    scope_aliases: list[str],
    legacy_keypoint_only: bool,
    manhattan_assumable_field_present: bool,
    manhattan_present: bool,
    manhattan_assumable: bool | None,
) -> tuple[bool, str | None]:
    if legacy_keypoint_only:
        return False, "meta_labels_untrusted"
    scope_reason = _primary_scope_reason(scope_aliases)
    if scope_reason != "normal":
        return False, scope_reason
    if manhattan_assumable_field_present:
        if not manhattan_present:
            return False, "missing_manhattan_assumable"
        if manhattan_assumable is not True:
            return False, "not_manhattan_assumable"
    return True, None


def _empty_residual_numeric_summary() -> dict[str, dict[str, float | int | None]]:
    return {
        field: {"count": 0, "median": None, "p90": None, "max": None}
        for field in RESIDUAL_NUMERIC_FIELDS
    }


def _percentile(values: list[float], q: float) -> float | None:
    if not values:
        return None
    sorted_values = sorted(values)
    if len(sorted_values) == 1:
        return sorted_values[0]
    position = (len(sorted_values) - 1) * q
    lower = int(position)
    upper = min(lower + 1, len(sorted_values) - 1)
    if lower == upper:
        return sorted_values[lower]
    fraction = position - lower
    return sorted_values[lower] * (1.0 - fraction) + sorted_values[upper] * fraction


def _summarize_numeric_residuals(
    residual_values: Mapping[str, list[float]],
) -> dict[str, dict[str, float | int | None]]:
    summary = _empty_residual_numeric_summary()
    for field, values in residual_values.items():
        if not values:
            continue
        summary[field] = {
            "count": len(values),
            "median": _percentile(values, 0.5),
            "p90": _percentile(values, 0.9),
            "max": max(values),
        }
    return summary


def _empty_summary(
    source_export: str,
    legacy_keypoint_only: bool,
    include_residuals: bool,
    include_suggestions: bool,
) -> dict[str, Any]:
    meta_labels_trusted = not legacy_keypoint_only
    return {
        "source_export": source_export,
        "probe_version": PROBE_VERSION,
        "legacy_keypoint_only": legacy_keypoint_only,
        "meta_labels_trusted": meta_labels_trusted,
        "legacy_mode_note": (
            "legacy-keypoint-only mode: only keypoints are trusted; scope, "
            "difficulty, and model_issue are not current-schema conclusions"
            if legacy_keypoint_only
            else None
        ),
        "n_tasks": 0,
        "n_annotations": 0,
        "n_results": 0,
        "n_keypoint_results": 0,
        "n_scope_results": 0,
        "wrapped_value_keypoint_count": 0,
        "scope_alias_counts": {} if meta_labels_trusted else None,
        "unknown_scope_alias_counts": {} if meta_labels_trusted else None,
        "missing_scope_count": 0 if meta_labels_trusted else None,
        "missing_keypoint_count": 0,
        "odd_keypoint_annotation_count": 0,
        "near_duplicate_annotation_count": 0,
        "wraparound_candidate_count": 0,
        "compatibility_status_counts": {},
        "parse_error_count": 0,
        "residual_enabled": include_residuals,
        "n_residual_valid": 0,
        "n_residual_excluded": 0,
        "residual_exclusion_counts": {},
        "residual_numeric_summary": _empty_residual_numeric_summary(),
        "audit_eligibility_enabled": include_residuals and meta_labels_trusted,
        "n_audit_eligible": 0,
        "n_audit_ineligible": 0,
        "audit_ineligibility_counts": {},
        "n_audit_residual_valid": 0,
        "n_audit_residual_excluded": 0,
        "audit_residual_exclusion_counts": {},
        "audit_residual_numeric_summary": _empty_residual_numeric_summary(),
        "suggestions_enabled": include_suggestions,
        "n_suggestion_annotations": 0,
        "suggestion_type_counts": {},
        "suggestion_severity_counts": {},
        "suggestion_source_field_counts": {},
        "audit_warnings": [],
        "candidate_task_examples": [],
    }


def _add_example(summary: dict[str, Any], example: dict[str, Any]) -> None:
    if len(summary["candidate_task_examples"]) < MAX_EXAMPLES:
        summary["candidate_task_examples"].append(example)


def _task_id(task: Mapping[str, Any]) -> Any:
    data = _as_mapping(task.get("data"))
    return task.get("id", data.get("task_id", data.get("base_task_id")))


def _annotation_id(annotation: Mapping[str, Any]) -> Any:
    return annotation.get("id", annotation.get("pk"))


def probe_tasks(
    tasks: Iterable[Mapping[str, Any]],
    source_export: str = "<memory>",
    legacy_keypoint_only: bool = False,
    include_residuals: bool = False,
    include_suggestions: bool = False,
) -> dict[str, Any]:
    """Build a smoke/probe summary from Label Studio export tasks."""

    if include_suggestions and not include_residuals:
        raise ValueError("include_suggestions requires include_residuals")

    summary = _empty_summary(
        source_export,
        legacy_keypoint_only,
        include_residuals,
        include_suggestions,
    )
    scope_counts: Counter[str] = Counter()
    unknown_scope_counts: Counter[str] = Counter()
    compatibility_counts: Counter[str] = Counter()
    residual_exclusion_counts: Counter[str] = Counter()
    residual_values: dict[str, list[float]] = {
        field: [] for field in RESIDUAL_NUMERIC_FIELDS
    }
    audit_ineligibility_counts: Counter[str] = Counter()
    audit_residual_values: dict[str, list[float]] = {
        field: [] for field in RESIDUAL_NUMERIC_FIELDS
    }
    audit_residual_exclusion_counts: Counter[str] = Counter()
    suggestion_type_counts: Counter[str] = Counter()
    suggestion_severity_counts: Counter[str] = Counter()
    suggestion_source_field_counts: Counter[str] = Counter()
    audit_warnings: set[str] = set()

    task_list = list(tasks)
    manhattan_assumable_field_present = any(
        extract_manhattan_assumable(task, annotation)[0]
        for task in task_list
        for annotation in _as_list(task.get("annotations"))
        if isinstance(annotation, Mapping)
    )
    if include_residuals and manhattan_assumable_field_present:
        audit_warnings.add("schema_level_manhattan_assumable_gate_active")
    summary["n_tasks"] = len(task_list)

    for task in task_list:
        annotations = _as_list(task.get("annotations"))
        task_id = _task_id(task)
        for annotation in annotations:
            if not isinstance(annotation, Mapping):
                summary["parse_error_count"] += 1
                continue

            results = _as_list(annotation.get("result"))
            summary["n_annotations"] += 1
            summary["n_results"] += len(results)

            scope_aliases = extract_scope_aliases(annotation)
            manhattan_present, manhattan_assumable = extract_manhattan_assumable(task, annotation)
            audit_candidate = False
            if not legacy_keypoint_only:
                summary["n_scope_results"] += len(scope_aliases)
                if not scope_aliases:
                    summary["missing_scope_count"] += 1
                    _add_example(
                        summary,
                        {
                            "issue": "missing_scope",
                            "task_id": task_id,
                            "annotation_id": _annotation_id(annotation),
                            "completed_by": annotation.get("completed_by"),
                        },
                    )
                for alias in scope_aliases:
                    if alias in VALID_SCOPE_ALIASES:
                        scope_counts[alias] += 1
                    else:
                        unknown_scope_counts[alias] += 1
                        audit_warnings.add(f"unknown_scope_alias:{alias}")
                        _add_example(
                            summary,
                            {
                                "issue": "unknown_scope_alias",
                                "scope": alias,
                                "task_id": task_id,
                                "annotation_id": _annotation_id(annotation),
                                "completed_by": annotation.get("completed_by"),
                            },
                        )

            if include_residuals:
                audit_candidate, audit_ineligible_reason = _audit_eligibility(
                    scope_aliases=scope_aliases,
                    legacy_keypoint_only=legacy_keypoint_only,
                    manhattan_assumable_field_present=manhattan_assumable_field_present,
                    manhattan_present=manhattan_present,
                    manhattan_assumable=manhattan_assumable,
                )
                if audit_candidate:
                    summary["n_audit_eligible"] += 1
                else:
                    summary["n_audit_ineligible"] += 1
                    audit_ineligibility_counts[str(audit_ineligible_reason)] += 1

            try:
                points, keypoint_count, wrapped_count = extract_keypoints(annotation)
            except (TypeError, ValueError):
                summary["parse_error_count"] += 1
                _add_example(
                    summary,
                    {
                        "issue": "unparseable_keypoint",
                        "task_id": task_id,
                        "annotation_id": _annotation_id(annotation),
                        "completed_by": annotation.get("completed_by"),
                    },
                )
                continue

            summary["n_keypoint_results"] += keypoint_count
            summary["wrapped_value_keypoint_count"] += wrapped_count

            if not points:
                summary["missing_keypoint_count"] += 1
                if include_residuals:
                    summary["n_residual_excluded"] += 1
                    residual_exclusion_counts["missing_keypoints"] += 1
                    if audit_candidate:
                        summary["n_audit_residual_excluded"] += 1
                        audit_residual_exclusion_counts["missing_keypoints"] += 1
                _add_example(
                    summary,
                    {
                        "issue": "missing_keypoints",
                        "task_id": task_id,
                        "annotation_id": _annotation_id(annotation),
                        "completed_by": annotation.get("completed_by"),
                    },
                )
                continue

            result = check_preview_compatibility(points)
            compatibility_counts[result.status] += 1
            if result.status == FAILURE_ODD_KEYPOINT:
                summary["odd_keypoint_annotation_count"] += 1
            elif result.status == FAILURE_DUPLICATE:
                summary["near_duplicate_annotation_count"] += 1
            elif result.status == FAILURE_WRAPAROUND:
                summary["wraparound_candidate_count"] += 1

            if result.status != "compatible":
                if include_residuals:
                    summary["n_residual_excluded"] += 1
                    residual_exclusion_counts[result.status] += 1
                    if audit_candidate:
                        summary["n_audit_residual_excluded"] += 1
                        audit_residual_exclusion_counts[result.status] += 1
                _add_example(
                    summary,
                    {
                        "issue": "compatibility_failure",
                        "compatibility_status": result.status,
                        "task_id": task_id,
                        "annotation_id": _annotation_id(annotation),
                        "completed_by": annotation.get("completed_by"),
                        "n_keypoints": len(points),
                        "n_pairs": len(result.pairs),
                        "n_unpaired_points": len(result.unpaired_points),
                    },
                )
            elif include_residuals:
                residual = compute_m1_residual(result)
                if residual.get("diagnostic_valid") is True:
                    summary["n_residual_valid"] += 1
                    for field in RESIDUAL_NUMERIC_FIELDS:
                        value = residual.get(field)
                        if isinstance(value, (int, float)):
                            residual_values[field].append(float(value))
                else:
                    summary["n_residual_excluded"] += 1
                    reason = str(residual.get("exclusion_reason") or "residual_invalid")
                    residual_exclusion_counts[reason] += 1

                if audit_candidate and residual.get("diagnostic_valid") is True:
                    summary["n_audit_residual_valid"] += 1
                    for field in RESIDUAL_NUMERIC_FIELDS:
                        value = residual.get(field)
                        if isinstance(value, (int, float)):
                            audit_residual_values[field].append(float(value))
                    if include_suggestions:
                        suggestions = build_preview_suggestion_candidates(residual)
                        summary["n_suggestion_annotations"] += 1
                        for suggestion in suggestions:
                            suggestion_type_counts[str(suggestion.get("suggestion_type"))] += 1
                            suggestion_severity_counts[str(suggestion.get("severity"))] += 1
                            source_field = suggestion.get("source_residual_field") or "none"
                            suggestion_source_field_counts[str(source_field)] += 1
                elif audit_candidate:
                    summary["n_audit_residual_excluded"] += 1
                    reason = str(residual.get("exclusion_reason") or "residual_invalid")
                    audit_residual_exclusion_counts[reason] += 1

    if not legacy_keypoint_only:
        summary["scope_alias_counts"] = dict(sorted(scope_counts.items()))
        summary["unknown_scope_alias_counts"] = dict(sorted(unknown_scope_counts.items()))
    summary["compatibility_status_counts"] = dict(sorted(compatibility_counts.items()))
    if include_residuals:
        summary["residual_exclusion_counts"] = dict(sorted(residual_exclusion_counts.items()))
        summary["residual_numeric_summary"] = _summarize_numeric_residuals(residual_values)
        summary["audit_ineligibility_counts"] = dict(sorted(audit_ineligibility_counts.items()))
        summary["audit_residual_exclusion_counts"] = dict(
            sorted(audit_residual_exclusion_counts.items())
        )
        summary["audit_residual_numeric_summary"] = _summarize_numeric_residuals(
            audit_residual_values
        )
    if include_suggestions:
        summary["suggestion_type_counts"] = dict(sorted(suggestion_type_counts.items()))
        summary["suggestion_severity_counts"] = dict(sorted(suggestion_severity_counts.items()))
        summary["suggestion_source_field_counts"] = dict(
            sorted(suggestion_source_field_counts.items())
        )
    summary["audit_warnings"] = sorted(audit_warnings)
    return summary


def probe_export(
    input_path: Path,
    legacy_keypoint_only: bool = False,
    include_residuals: bool = False,
    include_suggestions: bool = False,
) -> dict[str, Any]:
    return probe_tasks(
        _load_tasks(input_path),
        source_export=str(input_path),
        legacy_keypoint_only=legacy_keypoint_only,
        include_residuals=include_residuals,
        include_suggestions=include_suggestions,
    )


def write_summary(path: Path, summary: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, type=Path, help="Read-only Label Studio export JSON.")
    parser.add_argument(
        "--output",
        type=Path,
        help="Optional smoke/probe summary JSON path. This is not a formal round artifact.",
    )
    parser.add_argument(
        "--legacy-keypoint-only",
        action="store_true",
        help=(
            "Only trust keypoints for legacy server exports. Scope, difficulty, "
            "and model_issue are not counted as current-schema conclusions."
        ),
    )
    parser.add_argument(
        "--include-residuals",
        action="store_true",
        help=(
            "Include M1 residual summaries for preview-compatible annotations only. "
            "Residuals are preview geometry stability diagnostics, not correctness, "
            "routing, formal g_t, or round artifacts."
        ),
    )
    parser.add_argument(
        "--include-suggestions",
        action="store_true",
        help=(
            "Include preview-only suggestion type counts for audit-eligible, "
            "residual-valid annotations. Requires --include-residuals and does "
            "not produce snap coordinates, adjustment vectors, writeback payloads, "
            "correctness labels, or routing decisions."
        ),
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_arg_parser()
    args = parser.parse_args(argv)
    if args.include_suggestions and not args.include_residuals:
        parser.error("--include-suggestions requires --include-residuals")
    summary = probe_export(
        args.input,
        legacy_keypoint_only=args.legacy_keypoint_only,
        include_residuals=args.include_residuals,
        include_suggestions=args.include_suggestions,
    )
    if args.output:
        write_summary(args.output, summary)
    else:
        print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
