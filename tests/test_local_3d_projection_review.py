import copy
import json
from pathlib import Path

import pytest

from tools.paper_a_manhattan.run_local_3d_projection_review import (
    SAFETY_BOUNDARY,
    apply_candidate_row,
    resolve_local_image,
    run_local_review,
)
from tools.paper_a_manhattan.run_single_image_manhattan_assist import TOOL_VERSION


def _ordered_pairs():
    return [
        {"top": {"x": 10.0, "y": 20.0}, "bottom": {"x": 10.3, "y": 80.0}},
        {"top": {"x": 35.0, "y": 20.0}, "bottom": {"x": 35.0, "y": 80.0}},
        {"top": {"x": 60.0, "y": 20.0}, "bottom": {"x": 60.0, "y": 80.0}},
        {"top": {"x": 85.0, "y": 20.0}, "bottom": {"x": 85.0, "y": 80.0}},
    ]


def _candidate_row():
    return {
        "effective_pair_index": 1,
        "source_preview_order_index": 2,
        "probe_mode": "align_then_translate_column",
        "recommendation_eligible": True,
        "top_x_before": 10.0,
        "bottom_x_before": 10.3,
        "top_x_after": 10.5,
        "bottom_x_after": 10.5,
        "top_y_before": 20.0,
        "bottom_y_before": 80.0,
        "top_y_after": 20.0,
        "bottom_y_after": 80.0,
        "vertical_x_residual_before": 0.3,
        "vertical_x_residual_after": 0.0,
        "dense_pair_indices": [1, 2],
    }


def test_candidate_application_is_copy_only_and_aligns_column():
    original = _ordered_pairs()
    frozen = copy.deepcopy(original)
    candidate = apply_candidate_row(original, _candidate_row())

    assert original == frozen
    assert candidate[0]["top"]["x"] == candidate[0]["bottom"]["x"] == 10.5
    assert candidate[0]["source_preview_order_index"] == 2
    assert [row["top"]["x"] for row in candidate[1:]] == [35.0, 60.0, 85.0]


def test_local_image_resolver_explicit_path_has_priority(tmp_path):
    root = tmp_path / "images"
    root.mkdir()
    rooted = root / "source.jpg"
    rooted.write_bytes(b"rooted")
    explicit = tmp_path / "explicit.jpg"
    explicit.write_bytes(b"explicit")
    payload = {"source_image": "https://example.invalid/source.jpg"}

    info, resolved = resolve_local_image(
        payload, image_root=root, image_path=explicit
    )
    assert resolved == explicit.resolve()
    assert info["resolution_method"] == "explicit_image_path"
    assert info["image_path"] == "explicit.jpg"
    assert info["network_access_used"] is False

    root_info, root_resolved = resolve_local_image(payload, image_root=root)
    assert root_resolved == rooted.resolve()
    assert root_info["resolution_method"] == "image_root_basename"


def test_missing_image_still_generates_geometry_only_outputs(tmp_path):
    input_path = tmp_path / "input.json"
    input_path.write_text(
        json.dumps(
            {
                "ordered_pairs": _ordered_pairs(),
                "source_image": "https://example.invalid/missing.jpg",
            }
        ),
        encoding="utf-8",
    )
    out_dir = tmp_path / "review"
    paths = run_local_review(
        input_path=input_path,
        out_dir=out_dir,
        image_root=tmp_path / "missing-root",
        coordinate_mode="ls_percent",
    )

    assert all(path.is_file() for path in paths.values())
    payload = json.loads(paths["json"].read_text(encoding="utf-8"))
    assert payload["input_provenance"]["image"]["image_exists"] is False
    assert "texture unavailable" in paths["html"].read_text(encoding="utf-8").lower()


def test_candidate_metrics_and_static_html_contract(tmp_path):
    image_root = tmp_path / "images"
    image_root.mkdir()
    image = image_root / "pano.jpg"
    image.write_bytes(b"local panorama fixture")
    input_path = tmp_path / "input.json"
    input_path.write_text(
        json.dumps(
            {
                "ordered_pairs": _ordered_pairs(),
                "source_image": "https://example.invalid/pano.jpg",
            }
        ),
        encoding="utf-8",
    )
    candidate_path = tmp_path / "candidate.json"
    candidate_path.write_text(
        json.dumps(
            {
                "pair_index_mapping": [
                    {"effective_pair_index": 1, "source_preview_order_index": 2}
                ],
                "verified_3d_local_assist": {
                    "local_dense_corner_probe_rows": [_candidate_row()]
                },
            }
        ),
        encoding="utf-8",
    )
    paths = run_local_review(
        input_path=input_path,
        candidate_json=candidate_path,
        image_root=image_root,
        out_dir=tmp_path / "review",
        coordinate_mode="ls_percent",
    )

    payload = json.loads(paths["json"].read_text(encoding="utf-8"))
    assert [variant["name"] for variant in payload["variants"]] == [
        "original",
        "candidate_1",
    ]
    candidate = payload["variants"][1]
    assert candidate["candidate_row"]["top_x_after"] == candidate["candidate_row"]["bottom_x_after"]
    assert "delta_from_original" in candidate
    assert candidate["metric_comparison"]["wall_residual_sum_deg"].keys() == {
        "before",
        "after",
        "delta",
    }
    assert candidate["metric_comparison"]["pair_vertical_x_residual"] == {
        "before": 0.3,
        "after": 0.0,
        "delta": pytest.approx(-0.3),
    }
    assert candidate["summary"]["minimum_dense_floor_3d_separation"] is not None
    assert candidate["summary"]["vertical_x_residual_sum"] < payload["variants"][0]["summary"]["vertical_x_residual_sum"]

    page = paths["html"].read_text(encoding="utf-8")
    lower = page.lower()
    assert "vis_3d.html" in page
    assert "postMessage" in page
    assert "update_layout" in page
    assert "Hide labels" in page and "Show labels" in page
    for forbidden in (
        "fetch(",
        "label studio api",
        "writeback",
        "annotation patch",
        "submit",
        "routing",
        "formal_g_t",
    ):
        assert forbidden not in lower


def test_safety_regression_keeps_m1518_and_formal_boundaries():
    assert TOOL_VERSION == "single_image_manhattan_assist_m15_18_3_v1"
    assert SAFETY_BOUNDARY["annotation_write_allowed"] is False
    assert SAFETY_BOUNDARY["annotation_patch_generated"] is False
    assert SAFETY_BOUNDARY["automatic_optimization"] is False
    assert SAFETY_BOUNDARY["automatic_reorder_merge_delete"] is False
    assert SAFETY_BOUNDARY["worker_facing"] is False
    assert SAFETY_BOUNDARY["formal_artifact"] is False
