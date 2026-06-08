from tools.paper_a_manhattan.manhattan_preview_suggestions import build_preview_suggestion_candidates


"""Tests for M2 preview-only suggestion candidates.

These tests do not validate correctness, routing, formal g_t, UI behavior,
worker-facing hints, snap coordinates, adjustment vectors, or writeback payloads.
"""


def _residual(**overrides):
    base = {
        "diagnostic_valid": True,
        "exclusion_reason": None,
        "n_corners": 4,
        "x_spacing_cv": 0.0,
        "ceiling_y_range": 0.0,
        "floor_y_range": 0.0,
        "wall_height_range": 0.0,
        "vertical_pair_x_residual": 0.0,
        "closure_status": "implicit_preview_loop_closure",
        "residual_version": "test",
    }
    base.update(overrides)
    return base


def _types(suggestions):
    return [suggestion["suggestion_type"] for suggestion in suggestions]


def test_clean_residual_outputs_no_action():
    suggestions = build_preview_suggestion_candidates(_residual())

    assert _types(suggestions) == ["no_action"]
    assert suggestions[0]["preview_only"] is True
    assert suggestions[0]["not_correctness"] is True


def test_high_ceiling_y_range_triggers_ceiling_alignment_review():
    suggestions = build_preview_suggestion_candidates(_residual(ceiling_y_range=120.0))

    assert _types(suggestions) == ["review_ceiling_alignment"]
    assert suggestions[0]["source_residual_field"] == "ceiling_y_range"
    assert suggestions[0]["severity"] == "high"


def test_high_floor_y_range_triggers_floor_alignment_review():
    suggestions = build_preview_suggestion_candidates(_residual(floor_y_range=120.0))

    assert _types(suggestions) == ["review_floor_alignment"]
    assert suggestions[0]["source_residual_field"] == "floor_y_range"


def test_high_wall_height_range_triggers_wall_height_review():
    suggestions = build_preview_suggestion_candidates(_residual(wall_height_range=200.0))

    assert _types(suggestions) == ["review_wall_height_inconsistency"]
    assert suggestions[0]["source_residual_field"] == "wall_height_range"


def test_high_vertical_pair_x_residual_triggers_vertical_pair_review():
    suggestions = build_preview_suggestion_candidates(
        _residual(vertical_pair_x_residual=0.05)
    )

    assert _types(suggestions) == ["review_vertical_pair_alignment"]
    assert suggestions[0]["source_residual_field"] == "vertical_pair_x_residual"


def test_invalid_residual_outputs_no_action_only():
    suggestions = build_preview_suggestion_candidates(
        _residual(diagnostic_valid=False, exclusion_reason="compatibility_failure")
    )

    assert _types(suggestions) == ["no_action"]
    assert suggestions[0]["reason"] == "residual_diagnostic_not_valid"


def test_suggestions_have_no_snap_adjustment_or_writeback_fields():
    suggestions = build_preview_suggestion_candidates(
        _residual(x_spacing_cv=1.0, ceiling_y_range=120.0)
    )

    for suggestion in suggestions:
        assert "snap" not in suggestion
        assert "snap_to_axis" not in suggestion
        assert "coordinates" not in suggestion
        assert "adjustment" not in suggestion
        assert "adjustment_vector" not in suggestion
        assert "writeback" not in suggestion
        assert suggestion["preview_only"] is True
        assert suggestion["not_correctness"] is True
