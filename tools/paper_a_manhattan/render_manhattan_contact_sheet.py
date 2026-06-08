"""Render a standalone HTML contact sheet from a Manhattan probe summary JSON.

This M4 prototype consumes probe summary JSON only. It does not read Label
Studio exports, does not load panorama images, does not integrate with UI or
Label Studio, does not modify annotations, and does not connect to formal g_t,
routing, or P1/C1/C2/T1/V1 artifacts.
"""

from __future__ import annotations

import argparse
import json
from html import escape
from pathlib import Path
from typing import Any, Mapping


GUARDRAILS = (
    "Compatibility failure is not correctness. Residual is not worker quality. "
    "Suggestion is a preview-only review prompt. No formal g_t. No routing. "
    "Not a P1/C1/C2/T1/V1 artifact. Not current worker-facing experiment."
)


def load_summary(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    if not isinstance(payload, dict):
        raise ValueError(f"{path}: expected a probe summary JSON object")
    return payload


def _scalar(value: Any) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, float):
        return f"{value:.6g}"
    return str(value)


def _count_items(mapping: Any, *, exclude: set[str] | None = None) -> list[tuple[str, Any]]:
    if not isinstance(mapping, Mapping):
        return []
    excluded = exclude or set()
    return [(str(key), value) for key, value in sorted(mapping.items()) if str(key) not in excluded]


def _count_list(mapping: Any, *, exclude: set[str] | None = None) -> str:
    items = _count_items(mapping, exclude=exclude)
    if not items:
        return "<p class=\"muted\">none</p>"
    rows = "\n".join(
        f"<li><code>{escape(key)}</code>: {escape(_scalar(value))}</li>" for key, value in items
    )
    return f"<ul>{rows}</ul>"


def _examples_table(examples: Any) -> str:
    if not isinstance(examples, list) or not examples:
        return "<p class=\"muted\">No candidate examples in summary.</p>"

    rows: list[str] = []
    for example in examples:
        item = example if isinstance(example, Mapping) else {}
        rows.append(
            "<tr>"
            f"<td>{escape(_scalar(item.get('task_id')))}</td>"
            f"<td>{escape(_scalar(item.get('annotation_id')))}</td>"
            f"<td>{escape(_scalar(item.get('issue')))}</td>"
            f"<td>{escape(_scalar(item.get('compatibility_status')))}</td>"
            f"<td>{escape(_scalar(item.get('completed_by')))}</td>"
            "</tr>"
        )
    return (
        "<table>"
        "<thead><tr><th>task_id</th><th>annotation_id</th><th>issue</th>"
        "<th>compatibility_status</th><th>completed_by</th></tr></thead>"
        f"<tbody>{''.join(rows)}</tbody>"
        "</table>"
    )


def _warnings_list(warnings: Any) -> str:
    if not isinstance(warnings, list) or not warnings:
        return "<p class=\"muted\">none</p>"
    items = "\n".join(f"<li>{escape(_scalar(warning))}</li>" for warning in warnings)
    return f"<ul>{items}</ul>"


def _suggestion_event_note(summary: Mapping[str, Any]) -> str:
    counts = summary.get("suggestion_type_counts")
    if not isinstance(counts, Mapping):
        return ""
    event_count = sum(value for value in counts.values() if isinstance(value, int))
    annotation_count = summary.get("n_suggestion_annotations", 0)
    if isinstance(annotation_count, int) and event_count > annotation_count:
        return (
            "<p class=\"note\">Suggestion events can exceed suggestion annotations because "
            "one annotation can trigger multiple preview-only review prompts.</p>"
        )
    return ""


def _summary_cards(summary: Mapping[str, Any]) -> str:
    fields = (
        "n_tasks",
        "n_annotations",
        "n_keypoint_results",
        "n_residual_valid",
        "n_residual_excluded",
        "n_audit_eligible",
        "n_audit_ineligible",
        "n_audit_residual_valid",
        "n_audit_residual_excluded",
        "n_suggestion_annotations",
    )
    cards = "\n".join(
        "<div class=\"card\">"
        f"<div class=\"label\">{escape(field)}</div>"
        f"<div class=\"value\">{escape(_scalar(summary.get(field)))}</div>"
        "</div>"
        for field in fields
    )
    return f"<div class=\"cards\">{cards}</div>"


def render_html_contact_sheet(summary: Mapping[str, Any]) -> str:
    """Render a standalone HTML contact sheet from a probe summary object."""

    compatibility_failures = _count_list(
        summary.get("compatibility_status_counts"),
        exclude={"compatible"},
    )
    source_export = escape(_scalar(summary.get("source_export")))
    probe_version = escape(_scalar(summary.get("probe_version")))

    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>Manhattan Probe Contact Sheet</title>
  <style>
    body {{ font-family: Arial, sans-serif; margin: 24px; color: #1f2933; }}
    h1, h2 {{ margin-bottom: 8px; }}
    code {{ background: #eef2f7; padding: 1px 4px; border-radius: 4px; }}
    table {{ border-collapse: collapse; width: 100%; margin-top: 8px; }}
    th, td {{ border: 1px solid #d5dce5; padding: 6px 8px; text-align: left; }}
    th {{ background: #f3f6fa; }}
    .guardrails {{ border: 1px solid #b9c6d8; background: #f7fafc; padding: 12px; }}
    .cards {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 8px; }}
    .card {{ border: 1px solid #d5dce5; padding: 10px; }}
    .label {{ color: #627386; font-size: 12px; }}
    .value {{ font-size: 20px; font-weight: 600; }}
    .muted {{ color: #627386; }}
    .note {{ background: #fff7df; border: 1px solid #efd48b; padding: 10px; }}
  </style>
</head>
<body>
  <h1>Manhattan Probe Contact Sheet</h1>
  <section class="guardrails">
    <h2>Guardrails</h2>
    <p>{escape(GUARDRAILS)}</p>
  </section>
  <section>
    <h2>Source</h2>
    <ul>
      <li><code>source_export</code>: {source_export}</li>
      <li><code>probe_version</code>: {probe_version}</li>
    </ul>
  </section>
  <section>
    <h2>Summary Counts</h2>
    {_summary_cards(summary)}
  </section>
  <section>
    <h2>Scope Alias Counts</h2>
    {_count_list(summary.get("scope_alias_counts"))}
  </section>
  <section>
    <h2>Compatibility Failures</h2>
    {compatibility_failures}
  </section>
  <section>
    <h2>Audit Residual Exclusion Counts</h2>
    {_count_list(summary.get("audit_residual_exclusion_counts"))}
  </section>
  <section>
    <h2>Suggestion Type Counts</h2>
    {_count_list(summary.get("suggestion_type_counts"))}
    {_suggestion_event_note(summary)}
  </section>
  <section>
    <h2>Candidate Task Examples</h2>
    {_examples_table(summary.get("candidate_task_examples"))}
  </section>
  <section>
    <h2>Audit Warnings</h2>
    {_warnings_list(summary.get("audit_warnings"))}
  </section>
</body>
</html>
"""


def write_contact_sheet(path: Path, html: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(html, encoding="utf-8")


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, type=Path, help="Probe summary JSON path.")
    parser.add_argument(
        "--output",
        type=Path,
        help="Optional standalone HTML output path. If omitted, HTML is printed to stdout.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_arg_parser().parse_args(argv)
    html = render_html_contact_sheet(load_summary(args.input))
    if args.output:
        write_contact_sheet(args.output, html)
    else:
        print(html)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
