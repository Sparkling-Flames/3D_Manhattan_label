"""Render read-only Manhattan smoke/probe summaries as Markdown reports.

This M3 report layer consumes an existing probe summary JSON. It does not read
Label Studio exports, does not integrate with UI or Label Studio, does not
modify exports, does not connect to routing or formal g_t, and does not produce
P1/C1/C2/T1/V1 artifacts. Suggestions in the rendered report are preview-only
review prompts, not correctness labels or worker quality labels.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Mapping


GUARD_TEXT = (
    "Compatibility failure is not correctness. Residual values are preview "
    "geometry stability diagnostics, not worker quality. Suggestion counts are "
    "preview-only review prompts. This report does not enter formal g_t, does "
    "not enter routing, is not a P1/C1/C2/T1/V1 artifact, and is not used in "
    "the current worker-facing experiment."
)


def load_summary(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    if not isinstance(payload, dict):
        raise ValueError(f"{path}: expected a probe summary JSON object")
    return payload


def _format_scalar(value: Any) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, float):
        return f"{value:.6g}"
    return str(value)


def _mapping_lines(mapping: Any, empty_text: str = "- none") -> list[str]:
    if not isinstance(mapping, Mapping) or not mapping:
        return [empty_text]
    return [f"- `{key}`: {_format_scalar(value)}" for key, value in sorted(mapping.items())]


def _numeric_summary_lines(summary: Any) -> list[str]:
    if not isinstance(summary, Mapping) or not summary:
        return ["- none"]
    lines = ["| field | count | median | p90 | max |", "| --- | ---: | ---: | ---: | ---: |"]
    for field, values in sorted(summary.items()):
        value_map = values if isinstance(values, Mapping) else {}
        lines.append(
            "| {field} | {count} | {median} | {p90} | {max_value} |".format(
                field=field,
                count=_format_scalar(value_map.get("count")),
                median=_format_scalar(value_map.get("median")),
                p90=_format_scalar(value_map.get("p90")),
                max_value=_format_scalar(value_map.get("max")),
            )
        )
    return lines


def _examples_lines(examples: Any) -> list[str]:
    if not isinstance(examples, list) or not examples:
        return ["- none"]
    lines: list[str] = []
    for index, example in enumerate(examples, start=1):
        if isinstance(example, Mapping):
            details = ", ".join(
                f"{key}={_format_scalar(value)}" for key, value in sorted(example.items())
            )
            lines.append(f"- {index}. {details}")
        else:
            lines.append(f"- {index}. {_format_scalar(example)}")
    return lines


def _suggestion_event_note(summary: Mapping[str, Any]) -> list[str]:
    type_counts = summary.get("suggestion_type_counts")
    if not isinstance(type_counts, Mapping):
        return []
    event_count = sum(value for value in type_counts.values() if isinstance(value, int))
    annotation_count = summary.get("n_suggestion_annotations", 0)
    if isinstance(annotation_count, int) and event_count > annotation_count:
        return [
            "",
            (
                "Note: suggestion events can exceed suggestion annotations because "
                "one annotation can trigger multiple preview-only review prompts."
            ),
        ]
    return []


def render_markdown_report(summary: Mapping[str, Any]) -> str:
    """Render a probe summary JSON object into a Markdown report."""

    lines = [
        "# Manhattan Smoke Probe Report",
        "",
        "## Guardrails",
        "",
        GUARD_TEXT,
        "",
        "## Source",
        "",
        f"- `source_export`: {_format_scalar(summary.get('source_export'))}",
        f"- `probe_version`: {_format_scalar(summary.get('probe_version'))}",
        f"- `legacy_keypoint_only`: {_format_scalar(summary.get('legacy_keypoint_only'))}",
        f"- `meta_labels_trusted`: {_format_scalar(summary.get('meta_labels_trusted'))}",
        "",
        "## Counts",
        "",
        f"- `n_tasks`: {_format_scalar(summary.get('n_tasks'))}",
        f"- `n_annotations`: {_format_scalar(summary.get('n_annotations'))}",
        f"- `n_keypoint_results`: {_format_scalar(summary.get('n_keypoint_results'))}",
        f"- `n_results`: {_format_scalar(summary.get('n_results'))}",
        f"- `parse_error_count`: {_format_scalar(summary.get('parse_error_count'))}",
        "",
        "## Scope Alias Counts",
        "",
        *_mapping_lines(summary.get("scope_alias_counts")),
        "",
        "## Compatibility Status Counts",
        "",
        *_mapping_lines(summary.get("compatibility_status_counts")),
        "",
        "## Preview Residual Summary",
        "",
        f"- `residual_enabled`: {_format_scalar(summary.get('residual_enabled'))}",
        f"- `n_residual_valid`: {_format_scalar(summary.get('n_residual_valid'))}",
        f"- `n_residual_excluded`: {_format_scalar(summary.get('n_residual_excluded'))}",
        "",
        "### Preview Residual Numeric Summary",
        "",
        *_numeric_summary_lines(summary.get("residual_numeric_summary")),
        "",
        "## Audit Eligibility Summary",
        "",
        f"- `audit_eligibility_enabled`: {_format_scalar(summary.get('audit_eligibility_enabled'))}",
        f"- `n_audit_eligible`: {_format_scalar(summary.get('n_audit_eligible'))}",
        f"- `n_audit_ineligible`: {_format_scalar(summary.get('n_audit_ineligible'))}",
        "",
        "### Audit Ineligibility Counts",
        "",
        *_mapping_lines(summary.get("audit_ineligibility_counts")),
        "",
        "## Audit Residual Summary",
        "",
        f"- `n_audit_residual_valid`: {_format_scalar(summary.get('n_audit_residual_valid'))}",
        f"- `n_audit_residual_excluded`: {_format_scalar(summary.get('n_audit_residual_excluded'))}",
        "",
        "### Audit Residual Exclusion Counts",
        "",
        *_mapping_lines(summary.get("audit_residual_exclusion_counts")),
        "",
        "### Audit Residual Numeric Summary",
        "",
        *_numeric_summary_lines(summary.get("audit_residual_numeric_summary")),
        "",
        "## Suggestion Summary",
        "",
        f"- `suggestions_enabled`: {_format_scalar(summary.get('suggestions_enabled'))}",
        f"- `n_suggestion_annotations`: {_format_scalar(summary.get('n_suggestion_annotations'))}",
        "",
        "### Suggestion Type Counts",
        "",
        *_mapping_lines(summary.get("suggestion_type_counts")),
        "",
        "### Suggestion Severity Counts",
        "",
        *_mapping_lines(summary.get("suggestion_severity_counts")),
        "",
        "### Suggestion Source Field Counts",
        "",
        *_mapping_lines(summary.get("suggestion_source_field_counts")),
        *_suggestion_event_note(summary),
        "",
        "## Audit Warnings",
        "",
        *_examples_lines(summary.get("audit_warnings")),
        "",
        "## Candidate Task Examples",
        "",
        *_examples_lines(summary.get("candidate_task_examples")),
        "",
    ]
    return "\n".join(lines)


def write_report(path: Path, report: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(report, encoding="utf-8")


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, type=Path, help="Probe summary JSON path.")
    parser.add_argument(
        "--output",
        type=Path,
        help="Optional Markdown report path. If omitted, the report is printed to stdout.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_arg_parser().parse_args(argv)
    report = render_markdown_report(load_summary(args.input))
    if args.output:
        write_report(args.output, report)
    else:
        print(report)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
