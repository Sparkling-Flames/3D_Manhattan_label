"""Render an offline HTML review sheet for Manhattan geometry-debug candidates.

This M15.4 renderer consumes review-candidate JSONL sidecars only. It does not
read Label Studio exports, does not integrate with Label Studio UI, does not
submit form fields, does not write annotations, and does not connect to formal
g_t, routing, worker quality metrics, or P1/C1/C2/T1/V1 artifacts.
"""

from __future__ import annotations

import argparse
import csv
import json
from collections import defaultdict
from html import escape
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence


FOCUS_TASK_IDS = ("2948", "2949")
MANUAL_REVIEW_FIELDS = (
    "plausible_candidate",
    "likely_issue",
    "reviewer_note",
)
CSV_TEMPLATE_FIELDS = (
    "task_id",
    "annotation_id",
    "annotator_id",
    "scope_vote",
    "problem_reason",
    "max_abs_delta",
    "plausible_candidate",
    "likely_issue",
    "reviewer_note",
)
GUARDRAIL_TEXT = (
    "Visual review only. Candidate deltas are not correction instructions. "
    "OOS vote is not final OOS adjudication. No annotation writeback; no writeback. "
    "No formal g_t. No routing. No worker quality metric. "
    "No P1/C1/C2/T1/V1 artifact. The fitted candidate is not target truth."
)


def load_review_rows(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            stripped = line.strip()
            if not stripped:
                continue
            payload = json.loads(stripped)
            if not isinstance(payload, dict):
                raise ValueError(f"{path}:{line_number}: expected JSON object")
            rows.append(payload)
    return rows


def infer_source_records_path(review_jsonl: Path) -> Path | None:
    name = review_jsonl.name
    prefix = "smoke_geometry_debug_review_candidates_"
    suffix = ".jsonl"
    if not name.startswith(prefix) or not name.endswith(suffix):
        return None
    date = name[len(prefix) : -len(suffix)]
    candidate = review_jsonl.with_name(f"smoke_fit_records_{date}.jsonl")
    return candidate if candidate.exists() else None


def _row_key(row: Mapping[str, Any]) -> tuple[str, str]:
    return str(row.get("task_id")), str(row.get("annotation_id"))


def enrich_rows_from_source_records(
    review_rows: Sequence[Mapping[str, Any]],
    source_records_path: Path | None,
) -> list[dict[str, Any]]:
    rows = [dict(row) for row in review_rows]
    if source_records_path is None:
        return rows

    source_rows = load_review_rows(source_records_path)
    by_annotation = {_row_key(row): row for row in source_rows}

    for row in rows:
        if _image_url(row):
            row.setdefault("image_source", "review_row")
            continue
        source = by_annotation.get(_row_key(row))
        if source:
            image = _image_url(source)
            if image:
                row["image"] = image
                row["image_source"] = "source_records_exact_task_annotation_match"
            for field in ("title", "base_task_id", "source_export"):
                if field not in row and source.get(field) is not None:
                    row[field] = source.get(field)
            row["source_records_path"] = str(source_records_path)
        else:
            row["image_source"] = "missing_exact_task_annotation_match"
    return rows


def _scalar(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, float):
        return f"{value:.6g}"
    return str(value)


def _num(value: Any) -> float | None:
    if isinstance(value, (int, float)):
        return float(value)
    try:
        if isinstance(value, str) and value.strip():
            return float(value)
    except ValueError:
        return None
    return None


def _as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _point_xy(point: Mapping[str, Any]) -> tuple[float, float] | None:
    x = _num(point.get("x"))
    y = _num(point.get("y"))
    if x is None or y is None:
        return None
    return x, y


def _flatten_fitted_points(value: Any) -> list[dict[str, float]]:
    points: list[dict[str, float]] = []
    for pair in _as_list(value):
        if not isinstance(pair, Mapping):
            continue
        for key in ("top", "bottom"):
            nested = pair.get(key)
            if isinstance(nested, Mapping):
                xy = _point_xy(nested)
                if xy:
                    points.append({"x": xy[0], "y": xy[1]})
    return points


def _image_url(row: Mapping[str, Any]) -> str | None:
    for key in ("image", "image_url", "source_image", "panorama_url", "url"):
        value = row.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    data = row.get("data")
    if isinstance(data, Mapping):
        return _image_url(data)
    source = row.get("source_record")
    if isinstance(source, Mapping):
        return _image_url(source)
    return None


def _arrow(x1: float, y1: float, x2: float, y2: float) -> str:
    return (
        f'<line class="delta-arrow" x1="{x1:.4f}" y1="{y1:.4f}" '
        f'x2="{x2:.4f}" y2="{y2:.4f}" marker-end="url(#arrowhead)" />'
    )


def _point_dot(x: float, y: float, class_name: str, label: str) -> str:
    return (
        f'<span class="point-dot {class_name}" style="left:{x:.4f}%; top:{y:.4f}%;" '
        f'aria-label="{escape(label, quote=True)}"></span>'
    )


def _fit_absence_note(row: Mapping[str, Any], fitted_count: int) -> str:
    if fitted_count:
        return ""
    reason = row.get("problem_reason") or row.get("fit_status") or row.get("preview_status") or "unavailable"
    return (
        '<div class="fit-note">no fitted_points in candidate payload: '
        f"{escape(_scalar(reason))}</div>"
    )


def _overlay_markup(row: Mapping[str, Any]) -> str:
    original_points = [
        xy
        for point in _as_list(row.get("original_points"))
        if isinstance(point, Mapping)
        for xy in [_point_xy(point)]
        if xy is not None
    ]
    fitted_points = _flatten_fitted_points(row.get("fitted_points"))
    can_draw_arrows = bool(fitted_points) and bool(_as_list(row.get("per_point_delta")))

    arrow_parts = [
        '<svg class="delta-overlay" viewBox="0 0 100 100" preserveAspectRatio="none" aria-hidden="true">',
        "<defs>",
        '<marker id="arrowhead" viewBox="0 0 10 10" refX="8" refY="5" '
        'markerWidth="4" markerHeight="4" orient="auto-start-reverse">',
        '<path d="M 0 0 L 10 5 L 0 10 z" class="delta-arrow-head" />',
        "</marker>",
        "</defs>",
    ]
    if can_draw_arrows:
        for original, fitted in zip(original_points, fitted_points):
            arrow_parts.append(_arrow(original[0], original[1], fitted["x"], fitted["y"]))
    arrow_parts.append("</svg>")

    point_parts = [
        '<div class="overlay-grid" role="img" '
        'aria-label="Coordinate overlay: red original points, hollow blue fitted candidate points.">',
        "".join(arrow_parts),
    ]
    for x, y in original_points:
        point_parts.append(_point_dot(x, y, "original-dot", "original point"))
    for fitted in fitted_points:
        point_parts.append(_point_dot(fitted["x"], fitted["y"], "fitted-dot", "fitted candidate point"))
    point_parts.append(_fit_absence_note(row, len(fitted_points)))
    point_parts.append("</div>")
    return "".join(point_parts)


def _visual_panel(row: Mapping[str, Any]) -> str:
    image = _image_url(row)
    image_tag = ""
    if image:
        image_tag = f'<img class="source-image" src="{escape(image, quote=True)}" alt="" />'
    else:
        image_tag = '<div class="no-image">coordinate canvas only: no image URL in review row or source records</div>'
    return (
        '<div class="visual-panel">'
        f"{image_tag}"
        f"{_overlay_markup(row)}"
        '<div class="legend"><span class="legend-red"></span> original_points '
        '<span class="legend-blue"></span> fitted_points candidate '
        '<span class="legend-arrow"></span> delta arrows when available</div>'
        "</div>"
    )


def _field_grid(row: Mapping[str, Any]) -> str:
    fields = (
        "task_id",
        "annotation_id",
        "annotator_id",
        "scope_vote",
        "preview_status",
        "fit_status",
        "fit_confidence",
        "max_abs_delta",
        "layout_height_spread",
        "problem_reason",
        "review_question",
        "not_oos_adjudication",
        "title",
        "base_task_id",
        "image_source",
        "source_records_path",
    )
    items = []
    for field in fields:
        items.append(
            '<div class="kv">'
            f'<div class="key">{escape(field)}</div>'
            f'<div class="val">{escape(_scalar(row.get(field)))}</div>'
            "</div>"
        )
    return f'<div class="field-grid">{"".join(items)}</div>'


def _manual_fields(row: Mapping[str, Any], index: int) -> str:
    prefix = f"row_{index}"
    return f"""
      <fieldset class="manual-review">
        <legend>Manual visual review fields</legend>
        <label>plausible_candidate
          <select name="{prefix}_plausible_candidate">
            <option value=""></option>
            <option value="yes">yes</option>
            <option value="no">no</option>
            <option value="unsure">unsure</option>
          </select>
        </label>
        <label>likely_issue
          <select name="{prefix}_likely_issue">
            <option value=""></option>
            <option value="annotation_geometry">annotation_geometry</option>
            <option value="algorithm_overfit">algorithm_overfit</option>
            <option value="scope_disagreement">scope_disagreement</option>
            <option value="unclear">unclear</option>
          </select>
        </label>
        <label>reviewer_note
          <textarea name="{prefix}_reviewer_note" rows="3"></textarea>
        </label>
        <input type="hidden" name="{prefix}_task_id" value="{escape(_scalar(row.get('task_id')), quote=True)}">
        <input type="hidden" name="{prefix}_annotation_id" value="{escape(_scalar(row.get('annotation_id')), quote=True)}">
      </fieldset>
    """


def _card(row: Mapping[str, Any], index: int) -> str:
    task_id = escape(_scalar(row.get("task_id")))
    annotation_id = escape(_scalar(row.get("annotation_id")))
    return f"""
    <article class="review-card" data-task-id="{task_id}">
      <h3>task {task_id} / annotation {annotation_id}</h3>
      {_visual_panel(row)}
      {_field_grid(row)}
      {_manual_fields(row, index)}
    </article>
    """


def _unique_values(rows: Sequence[Mapping[str, Any]], field: str) -> list[str]:
    values = sorted({_scalar(row.get(field)) for row in rows if _scalar(row.get(field))})
    return values


def _task_summary(task_id: str, rows: Sequence[Mapping[str, Any]]) -> str:
    images = _unique_values(rows, "image")
    titles = _unique_values(rows, "title")
    base_task_ids = _unique_values(rows, "base_task_id")
    image_sources = _unique_values(rows, "image_source")

    def values_line(label: str, values: Sequence[str]) -> str:
        if not values:
            return ""
        rendered = ", ".join(f"<code>{escape(value)}</code>" for value in values[:3])
        if len(values) > 3:
            rendered += f", ... +{len(values) - 3}"
        return f'<div class="task-meta-item"><span>{escape(label)}</span>{rendered}</div>'

    shared_note = ""
    if len(images) == 1 and len(rows) > 1:
        shared_note = (
            '<p class="task-note">This task has multiple annotation review cards sharing one source image; '
            "the repeated image is intentional for this task, while overlays and diagnostics are annotation-specific.</p>"
        )
    elif not images:
        shared_note = (
            '<p class="task-note warning">No image URL was resolved for this task; cards use coordinate canvas only.</p>'
        )
    elif len(images) > 1:
        shared_note = (
            '<p class="task-note warning">Multiple image URLs were resolved inside this task; inspect provenance before review.</p>'
        )

    return (
        '<div class="task-summary">'
        f'<div class="task-meta-item"><span>review_cards</span><code>{len(rows)}</code></div>'
        f'<div class="task-meta-item"><span>unique_images_in_task</span><code>{len(images)}</code></div>'
        f"{values_line('title', titles)}"
        f"{values_line('base_task_id', base_task_ids)}"
        f"{values_line('image_source', image_sources)}"
        f"{shared_note}"
        "</div>"
    )


def _ordered_groups(rows: Sequence[Mapping[str, Any]]) -> list[tuple[str, list[Mapping[str, Any]]]]:
    grouped: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[str(row.get("task_id"))].append(row)

    ordered_ids: list[str] = []
    for task_id in FOCUS_TASK_IDS:
        if task_id in grouped:
            ordered_ids.append(task_id)
    ordered_ids.extend(sorted(task_id for task_id in grouped if task_id not in set(FOCUS_TASK_IDS)))
    return [(task_id, grouped[task_id]) for task_id in ordered_ids]


def focus_tasks_appear_first(rows: Sequence[Mapping[str, Any]]) -> bool:
    groups = [task_id for task_id, _ in _ordered_groups(rows)]
    expected_prefix = [task_id for task_id in FOCUS_TASK_IDS if any(str(row.get("task_id")) == task_id for row in rows)]
    return groups[: len(expected_prefix)] == expected_prefix


def render_html_review_sheet(rows: Sequence[Mapping[str, Any]], *, source_path: str | None = None) -> str:
    cards: list[str] = []
    index = 0
    sections: list[str] = []
    for task_id, group_rows in _ordered_groups(rows):
        section_cards = []
        for row in group_rows:
            index += 1
            section_cards.append(_card(row, index))
        focus_label = " focus-task" if task_id in FOCUS_TASK_IDS else ""
        sections.append(
            f'<section class="task-section{focus_label}" id="task-{escape(task_id)}">'
            f"<h2>Task {escape(task_id)}</h2>"
            f"{_task_summary(task_id, group_rows)}"
            f"{''.join(section_cards)}"
            "</section>"
        )
        cards.extend(section_cards)

    source = escape(source_path or "")
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>Manhattan Geometry Debug Review Sheet</title>
  <style>
    body {{ margin: 24px; font-family: Arial, sans-serif; color: #1f2933; background: #fbfcfe; }}
    h1, h2, h3 {{ margin: 0 0 10px; }}
    h1 {{ font-size: 26px; }}
    h2 {{ margin-top: 28px; padding-bottom: 6px; border-bottom: 2px solid #d5dce5; }}
    h3 {{ font-size: 17px; }}
    code {{ background: #eef2f7; padding: 1px 4px; border-radius: 4px; }}
    .guardrails {{ border: 1px solid #a9b8c9; background: #f4f8fb; padding: 12px; margin: 14px 0; }}
    .summary {{ color: #526173; margin-bottom: 18px; }}
    .task-summary {{ border: 1px solid #cbd5e1; background: #f8fafc; padding: 10px; margin: 10px 0 14px; }}
    .task-meta-item {{ display: inline-block; margin: 4px 14px 4px 0; }}
    .task-meta-item span {{ color: #66768a; margin-right: 5px; }}
    .task-note {{ margin: 8px 0 0; color: #344255; }}
    .task-note.warning {{ color: #8a4b00; }}
    .review-card {{ background: white; border: 1px solid #d8e0ea; border-radius: 6px; padding: 14px; margin: 12px 0; }}
    .focus-task .review-card {{ border-left: 4px solid #2f6db3; }}
    .visual-panel {{ position: relative; width: min(100%, 820px); aspect-ratio: 2 / 1; border: 1px solid #cbd5e1; background: #eef3f8; overflow: hidden; margin: 10px 0; }}
    .source-image {{ position: absolute; inset: 0; width: 100%; height: 100%; object-fit: fill; opacity: 0.86; }}
    .no-image {{ position: absolute; inset: 0; display: flex; align-items: center; justify-content: center; color: #66768a; font-size: 14px; }}
    .overlay-grid {{ position: absolute; inset: 0; width: 100%; height: 100%;
      background-image:
        linear-gradient(to right, transparent 24.9%, rgba(70, 85, 105, 0.28) 25%, transparent 25.1%),
        linear-gradient(to right, transparent 49.9%, rgba(70, 85, 105, 0.28) 50%, transparent 50.1%),
        linear-gradient(to right, transparent 74.9%, rgba(70, 85, 105, 0.28) 75%, transparent 75.1%),
        linear-gradient(to bottom, transparent 24.9%, rgba(70, 85, 105, 0.28) 25%, transparent 25.1%),
        linear-gradient(to bottom, transparent 49.9%, rgba(70, 85, 105, 0.28) 50%, transparent 50.1%),
        linear-gradient(to bottom, transparent 74.9%, rgba(70, 85, 105, 0.28) 75%, transparent 75.1%);
    }}
    .delta-overlay {{ position: absolute; inset: 0; width: 100%; height: 100%; }}
    .point-dot {{ position: absolute; transform: translate(-50%, -50%); border-radius: 50%; box-sizing: border-box; pointer-events: none; }}
    .original-dot {{ width: 7px; height: 7px; background: #d22f27; border: 1px solid white; }}
    .fitted-dot {{ width: 10px; height: 10px; background: transparent; border: 2px solid #1f6fc2; }}
    .delta-arrow {{ stroke: #58687b; stroke-width: 0.16; fill: none; }}
    .delta-arrow-head {{ fill: #58687b; }}
    .fit-note {{ position: absolute; right: 8px; top: 8px; background: rgba(255,255,255,0.9); border: 1px solid #d8e0ea; padding: 3px 6px; font-size: 12px; color: #4d5f73; }}
    .legend {{ position: absolute; left: 8px; bottom: 6px; background: rgba(255,255,255,0.86); padding: 4px 6px; font-size: 12px; }}
    .legend-red, .legend-blue, .legend-arrow {{ display: inline-block; width: 10px; height: 10px; margin-left: 8px; vertical-align: -1px; }}
    .legend-red {{ background: #d22f27; border-radius: 50%; margin-left: 0; }}
    .legend-blue {{ border: 2px solid #1f6fc2; border-radius: 50%; }}
    .legend-arrow {{ border-top: 2px solid #58687b; height: 0; }}
    .field-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 8px; }}
    .kv {{ border: 1px solid #e0e7ef; padding: 7px; min-height: 44px; }}
    .key {{ color: #66768a; font-size: 12px; }}
    .val {{ overflow-wrap: anywhere; }}
    .manual-review {{ margin-top: 12px; border: 1px dashed #b9c6d8; }}
    .manual-review label {{ display: block; margin: 8px 0; }}
    select, textarea {{ width: min(100%, 520px); display: block; margin-top: 4px; }}
  </style>
</head>
<body>
  <h1>Manhattan Geometry Debug Review Sheet</h1>
  <div class="summary">source: <code>{source}</code>; review cards: {len(rows)}</div>
  <section class="guardrails">
    <h2>Guardrails</h2>
    <p>{escape(GUARDRAIL_TEXT)}</p>
    <p>Manual review fields are local visual form fields only: no network submit and no annotation writeback.</p>
  </section>
  {''.join(sections)}
</body>
</html>
"""


def write_html(path: Path, html: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(html, encoding="utf-8")


def manual_review_template_path(output_path: Path) -> Path:
    name = output_path.name
    if name.endswith(".html"):
        name = name[: -len(".html")]
    name = name.replace("review_sheet", "manual_review_template")
    return output_path.with_name(f"{name}.csv")


def write_manual_review_template(path: Path, rows: Iterable[Mapping[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=CSV_TEMPLATE_FIELDS)
        writer.writeheader()
        for row in rows:
            writer.writerow(
                {
                    "task_id": row.get("task_id"),
                    "annotation_id": row.get("annotation_id"),
                    "annotator_id": row.get("annotator_id"),
                    "scope_vote": row.get("scope_vote"),
                    "problem_reason": row.get("problem_reason"),
                    "max_abs_delta": row.get("max_abs_delta"),
                    "plausible_candidate": "",
                    "likely_issue": "",
                    "reviewer_note": "",
                }
            )


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--review-jsonl", required=True, type=Path, help="Geometry-debug review candidate JSONL.")
    parser.add_argument("--output", required=True, type=Path, help="Standalone offline HTML output path.")
    parser.add_argument(
        "--source-records",
        type=Path,
        help="Optional smoke_fit_records JSONL used to add image URLs. Defaults to same-date sibling if present.",
    )
    parser.add_argument(
        "--manual-review-template",
        type=Path,
        help="Optional CSV template output path. Defaults to output name with review_sheet replaced.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_arg_parser().parse_args(argv)
    source_records = args.source_records if args.source_records is not None else infer_source_records_path(args.review_jsonl)
    rows = enrich_rows_from_source_records(load_review_rows(args.review_jsonl), source_records)
    html = render_html_review_sheet(rows, source_path=str(args.review_jsonl))
    write_html(args.output, html)
    template = args.manual_review_template or manual_review_template_path(args.output)
    write_manual_review_template(template, rows)
    print(
        json.dumps(
            {
                "review_cards": len(rows),
                "focus_tasks_appear_first": focus_tasks_appear_first(rows),
                "html": str(args.output),
                "manual_review_template": str(template),
                "source_records": str(source_records) if source_records else None,
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
