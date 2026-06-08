"""Synthetic tests for the M15.4 Manhattan geometry review sheet renderer.

The renderer consumes review JSONL only. These tests do not read or modify
export_label, Label Studio UI, annotations, routing, formal g_t, or
P1/C1/C2/T1/V1 artifacts.
"""

from __future__ import annotations

import csv
import json

from tools.paper_a_manhattan.render_manhattan_geometry_review_sheet import (
    enrich_rows_from_source_records,
    focus_tasks_appear_first,
    infer_source_records_path,
    main,
    render_html_review_sheet,
)


def _review_row(task_id=2948, *, image=None, fitted=True):
    row = {
        "task_id": task_id,
        "annotation_id": 2624,
        "annotator_id": 2,
        "scope_vote": "normal",
        "preview_status": "compatible",
        "fit_status": "ok",
        "fit_confidence": "high",
        "max_abs_delta": 0.25,
        "layout_height_spread": 0.02,
        "problem_reason": None,
        "review_question": "Focused task-level Manhattan stability inspection row.",
        "not_oos_adjudication": True,
        "original_points": [
            {"x": 20.0, "y": 40.0},
            {"x": 20.0, "y": 60.0},
            {"x": 70.0, "y": 42.0},
            {"x": 70.0, "y": 62.0},
        ],
        "fitted_points": [],
        "per_point_delta": [],
    }
    if image:
        row["image"] = image
    if fitted:
        row["fitted_points"] = [
            {
                "pair_index": 1,
                "top": {"x": 21.0, "y": 41.0},
                "bottom": {"x": 21.0, "y": 61.0},
            },
            {
                "pair_index": 2,
                "top": {"x": 69.0, "y": 43.0},
                "bottom": {"x": 69.0, "y": 63.0},
            },
        ]
        row["per_point_delta"] = [
            {"pair_index": 1, "top_dx": 1.0, "top_dy": 1.0, "bottom_dx": 1.0, "bottom_dy": 1.0},
            {"pair_index": 2, "top_dx": -1.0, "top_dy": 1.0, "bottom_dx": -1.0, "bottom_dy": 1.0},
        ]
    return row


def test_renderer_creates_html_from_synthetic_review_jsonl(tmp_path):
    input_path = tmp_path / "review.jsonl"
    output_path = tmp_path / "smoke_geometry_debug_review_sheet_2026-05-18.html"
    input_path.write_text(json.dumps(_review_row(), ensure_ascii=False) + "\n", encoding="utf-8")

    assert main(["--review-jsonl", str(input_path), "--output", str(output_path)]) == 0

    html = output_path.read_text(encoding="utf-8")
    assert "<!doctype html>" in html
    assert "Manhattan Geometry Debug Review Sheet" in html
    assert "task 2948" in html


def test_html_contains_original_fitted_point_overlays():
    html = render_html_review_sheet([_review_row()])

    assert 'preserveAspectRatio="none"' in html
    assert 'class="overlay-grid"' in html
    assert 'class="point-dot original-dot"' in html
    assert 'class="point-dot fitted-dot"' in html
    assert 'class="delta-arrow"' in html
    assert "red original points, hollow blue fitted candidate points" in html
    assert "width: 7px" in html
    assert "width: 10px" in html


def test_html_contains_manual_review_fields():
    html = render_html_review_sheet([_review_row()])

    assert "plausible_candidate" in html
    assert "likely_issue" in html
    assert "reviewer_note" in html
    assert "annotation_geometry" in html
    assert "algorithm_overfit" in html
    assert "scope_disagreement" in html
    assert "unclear" in html


def test_html_contains_guardrail_text():
    html = render_html_review_sheet([_review_row()])

    assert "Visual review only" in html
    assert "Candidate deltas are not correction instructions" in html
    assert "OOS vote is not final OOS adjudication" in html
    assert "no writeback" in html
    assert "No formal g_t" in html
    assert "No routing" in html
    assert "No worker quality metric" in html
    assert "No P1/C1/C2/T1/V1 artifact" in html


def test_csv_template_is_generated(tmp_path):
    input_path = tmp_path / "review.jsonl"
    output_path = tmp_path / "smoke_geometry_debug_review_sheet_2026-05-18.html"
    input_path.write_text(json.dumps(_review_row(), ensure_ascii=False) + "\n", encoding="utf-8")

    main(["--review-jsonl", str(input_path), "--output", str(output_path)])

    template = tmp_path / "smoke_geometry_debug_manual_review_template_2026-05-18.csv"
    assert template.exists()
    with template.open(encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    assert rows[0]["task_id"] == "2948"
    assert rows[0]["plausible_candidate"] == ""
    assert rows[0]["likely_issue"] == ""
    assert rows[0]["reviewer_note"] == ""


def test_missing_image_url_still_renders_coordinate_canvas():
    html = render_html_review_sheet([_review_row(image=None)])

    assert "coordinate canvas only: no image URL in review row or source records" in html
    assert '<div class="overlay-grid"' in html


def test_image_url_is_rendered_when_available():
    html = render_html_review_sheet([_review_row(image="http://example.test/pano.jpg")])

    assert 'src="http://example.test/pano.jpg"' in html
    assert '<div class="overlay-grid"' in html


def test_missing_fitted_points_are_explained_on_overlay():
    row = _review_row(fitted=False)
    row["problem_reason"] = "compatibility_failure_duplicate"

    html = render_html_review_sheet([row])

    assert "no fitted_points in candidate payload" in html
    assert "compatibility_failure_duplicate" in html


def test_source_records_can_supply_image_url(tmp_path):
    review_path = tmp_path / "smoke_geometry_debug_review_candidates_2026-05-18.jsonl"
    source_path = tmp_path / "smoke_fit_records_2026-05-18.jsonl"
    review_row = _review_row(image=None)
    source_row = {
        "task_id": review_row["task_id"],
        "annotation_id": review_row["annotation_id"],
        "image": "http://example.test/source-record.jpg",
    }
    review_path.write_text(json.dumps(review_row, ensure_ascii=False) + "\n", encoding="utf-8")
    source_path.write_text(json.dumps(source_row, ensure_ascii=False) + "\n", encoding="utf-8")

    assert infer_source_records_path(review_path) == source_path
    rows = enrich_rows_from_source_records([review_row], source_path)
    html = render_html_review_sheet(rows)

    assert 'src="http://example.test/source-record.jpg"' in html
    assert "source_records_exact_task_annotation_match" in html


def test_source_records_do_not_fallback_to_task_only_match(tmp_path):
    source_path = tmp_path / "smoke_fit_records_2026-05-18.jsonl"
    review_row = _review_row(image=None)
    source_row = {
        "task_id": review_row["task_id"],
        "annotation_id": 999999,
        "image": "http://example.test/wrong-task-fallback.jpg",
    }
    source_path.write_text(json.dumps(source_row, ensure_ascii=False) + "\n", encoding="utf-8")

    rows = enrich_rows_from_source_records([review_row], source_path)
    html = render_html_review_sheet(rows)

    assert "wrong-task-fallback.jpg" not in html
    assert "missing_exact_task_annotation_match" in html
    assert "coordinate canvas only: no image URL in review row or source records" in html


def test_focused_tasks_are_ordered_first():
    rows = [_review_row(3100), _review_row(2949), _review_row(2948)]
    html = render_html_review_sheet(rows)

    assert focus_tasks_appear_first(rows) is True
    assert html.index("Task 2948") < html.index("Task 2949") < html.index("Task 3100")


def test_task_summary_explains_shared_source_image_for_multiple_annotations():
    row_a = _review_row(2948, image="http://example.test/task-2948.jpg")
    row_b = _review_row(2948, image="http://example.test/task-2948.jpg")
    row_b["annotation_id"] = 2624
    row_a["title"] = "task-2948.jpg"
    row_b["title"] = "task-2948.jpg"

    html = render_html_review_sheet([row_a, row_b])

    assert "unique_images_in_task" in html
    assert "review_cards" in html
    assert "multiple annotation review cards sharing one source image" in html
    assert "overlays and diagnostics are annotation-specific" in html


def test_task_summary_warns_when_one_task_has_multiple_images():
    row_a = _review_row(2948, image="http://example.test/a.jpg")
    row_b = _review_row(2948, image="http://example.test/b.jpg")
    row_b["annotation_id"] = 2624

    html = render_html_review_sheet([row_a, row_b])

    assert "Multiple image URLs were resolved inside this task" in html
