import pytest

from tools.probe_manhattan_smoke_export import probe_tasks


"""Synthetic tests for the read-only smoke export probe.

These tests do not validate correctness, formal g_t, routing behavior, snap or
adjustment suggestions, worker-facing guidance, UI integration, Label Studio
integration, or P1/C1/C2/T1/V1 artifacts.
"""


def _keypoint(x, y):
    return {
        "type": "keypointlabels",
        "from_name": "kp",
        "value": {"x": x, "y": y, "keypointlabels": ["Corner"]},
    }


def _wrapped_keypoint(x, y):
    return {
        "type": "keypointlabels",
        "from_name": "kp",
        "value": {"value": {"x": x, "y": y}, "keypointlabels": ["Corner"]},
    }


def _scope(alias):
    return {"type": "choices", "from_name": "scope", "value": {"choices": [alias]}}


def _annotation(annotation_id, results, completed_by=7):
    return {"id": annotation_id, "completed_by": completed_by, "result": results}


def _clean_points():
    return [
        _keypoint(20.0, 25.0),
        _keypoint(20.0, 78.0),
        _keypoint(40.0, 22.0),
        _keypoint(40.0, 80.0),
        _keypoint(60.0, 22.0),
        _keypoint(60.0, 80.0),
        _keypoint(80.0, 25.0),
        _keypoint(80.0, 78.0),
    ]


def _odd_points():
    return _clean_points()[:-1]


def _duplicate_points():
    return [
        _keypoint(20.0, 25.0),
        _keypoint(20.0, 78.0),
        _keypoint(40.0, 22.0),
        _keypoint(40.0, 80.0),
        _keypoint(40.3, 22.2),
        _keypoint(40.3, 79.8),
        _keypoint(80.0, 25.0),
        _keypoint(80.0, 78.0),
    ]


def _current_fixture():
    return [
        {
            "id": 101,
            "data": {"image": "/data/local-files/?d=smoke/a.jpg", "smoke_test": True},
            "annotations": [
                _annotation(1001, [_scope("normal"), *_clean_points()]),
                _annotation(1002, [_scope("oos_split_level"), *_odd_points()]),
                _annotation(1003, [_scope("legacy_scope_text"), *_duplicate_points()]),
            ],
        },
        {
            "id": 102,
            "data": {"image": "/data/local-files/?d=smoke/b.jpg", "smoke_test": True},
            "annotations": [
                _annotation(1004, _clean_points()),
                _annotation(1005, [_scope("normal")]),
                _annotation(
                    1006,
                    [
                        _scope("oos_geometry"),
                        _wrapped_keypoint(20.0, 25.0),
                        _wrapped_keypoint(20.0, 78.0),
                    ],
                ),
            ],
        },
    ]


def test_current_smoke_fixture_counts_scope_and_keypoints():
    summary = probe_tasks(_current_fixture(), source_export="synthetic.json")

    assert summary["source_export"] == "synthetic.json"
    assert summary["meta_labels_trusted"] is True
    assert summary["legacy_keypoint_only"] is False
    assert summary["n_tasks"] == 2
    assert summary["n_annotations"] == 6
    assert summary["n_scope_results"] == 5
    assert summary["scope_alias_counts"] == {
        "normal": 2,
        "oos_geometry": 1,
        "oos_split_level": 1,
    }
    assert summary["unknown_scope_alias_counts"] == {"legacy_scope_text": 1}
    assert summary["audit_warnings"] == ["unknown_scope_alias:legacy_scope_text"]
    assert summary["residual_enabled"] is False
    assert summary["n_residual_valid"] == 0
    assert summary["n_residual_excluded"] == 0


def test_missing_scope_and_missing_keypoints_are_counted_separately():
    summary = probe_tasks(_current_fixture())

    assert summary["missing_scope_count"] == 1
    assert summary["missing_keypoint_count"] == 1
    assert any(example["issue"] == "missing_scope" for example in summary["candidate_task_examples"])
    assert any(example["issue"] == "missing_keypoints" for example in summary["candidate_task_examples"])


def test_preview_compatibility_failures_are_counted_without_quality_claims():
    summary = probe_tasks(_current_fixture())

    assert summary["odd_keypoint_annotation_count"] == 1
    assert summary["near_duplicate_annotation_count"] == 1
    assert summary["wraparound_candidate_count"] == 0
    assert summary["compatibility_status_counts"] == {
        "compatible": 3,
        "compatibility_failure_duplicate": 1,
        "compatibility_failure_odd_keypoint": 1,
    }


def test_wrapped_value_keypoints_are_read_and_counted():
    summary = probe_tasks(_current_fixture())

    assert summary["wrapped_value_keypoint_count"] == 2
    assert summary["n_keypoint_results"] == 33


def test_legacy_keypoint_only_mode_does_not_trust_meta_labels():
    summary = probe_tasks(_current_fixture(), legacy_keypoint_only=True)

    assert summary["meta_labels_trusted"] is False
    assert summary["legacy_keypoint_only"] is True
    assert summary["scope_alias_counts"] is None
    assert summary["unknown_scope_alias_counts"] is None
    assert summary["missing_scope_count"] is None
    assert summary["n_scope_results"] == 0
    assert "legacy-keypoint-only mode" in summary["legacy_mode_note"]
    assert summary["compatibility_status_counts"] == {
        "compatible": 3,
        "compatibility_failure_duplicate": 1,
        "compatibility_failure_odd_keypoint": 1,
    }


def test_include_residuals_summarizes_compatible_rows_only():
    summary = probe_tasks(_current_fixture(), include_residuals=True)

    assert summary["residual_enabled"] is True
    assert summary["n_residual_valid"] == 2
    assert summary["n_residual_excluded"] == 4
    assert summary["residual_exclusion_counts"] == {
        "compatibility_failure_duplicate": 1,
        "compatibility_failure_odd_keypoint": 1,
        "insufficient_compatible_corners": 1,
        "missing_keypoints": 1,
    }
    assert summary["audit_eligibility_enabled"] is True
    assert summary["n_audit_eligible"] == 2
    assert summary["n_audit_ineligible"] == 4


def test_include_residuals_numeric_summary_is_reproducible():
    summary = probe_tasks(_current_fixture(), include_residuals=True)
    numeric = summary["residual_numeric_summary"]

    assert numeric["x_spacing_cv"]["count"] == 2
    assert numeric["x_spacing_cv"]["median"] == pytest.approx(0.0, abs=1e-12)
    assert numeric["x_spacing_cv"]["p90"] == pytest.approx(0.0, abs=1e-12)
    assert numeric["x_spacing_cv"]["max"] == pytest.approx(0.0, abs=1e-12)

    assert numeric["ceiling_y_range"]["count"] == 2
    assert numeric["ceiling_y_range"]["median"] == pytest.approx(15.36)
    assert numeric["ceiling_y_range"]["p90"] == pytest.approx(15.36)
    assert numeric["ceiling_y_range"]["max"] == pytest.approx(15.36)

    assert numeric["floor_y_range"]["count"] == 2
    assert numeric["floor_y_range"]["median"] == pytest.approx(10.24)
    assert numeric["floor_y_range"]["p90"] == pytest.approx(10.24)
    assert numeric["floor_y_range"]["max"] == pytest.approx(10.24)

    assert numeric["wall_height_range"]["count"] == 2
    assert numeric["wall_height_range"]["median"] == pytest.approx(25.6)
    assert numeric["wall_height_range"]["p90"] == pytest.approx(25.6)
    assert numeric["wall_height_range"]["max"] == pytest.approx(25.6)

    assert numeric["vertical_pair_x_residual"]["count"] == 2
    assert numeric["vertical_pair_x_residual"]["median"] == pytest.approx(0.0)
    assert numeric["vertical_pair_x_residual"]["p90"] == pytest.approx(0.0)
    assert numeric["vertical_pair_x_residual"]["max"] == pytest.approx(0.0)


def test_audit_residual_only_includes_normal_scope():
    summary = probe_tasks(_current_fixture(), include_residuals=True)
    audit_numeric = summary["audit_residual_numeric_summary"]

    assert summary["audit_ineligibility_counts"] == {
        "oos_geometry": 1,
        "oos_split_level": 1,
        "scope_missing": 1,
        "scope_unknown": 1,
    }
    assert audit_numeric["x_spacing_cv"]["count"] == 1
    assert audit_numeric["ceiling_y_range"]["count"] == 1
    assert audit_numeric["floor_y_range"]["count"] == 1
    assert audit_numeric["wall_height_range"]["count"] == 1
    assert audit_numeric["vertical_pair_x_residual"]["count"] == 1


def test_manhattan_assumable_field_controls_audit_eligibility_when_present():
    tasks = [
        {
            "id": 201,
            "annotations": [
                _annotation(2001, [_scope("normal"), *_clean_points()]),
                {
                    "id": 2002,
                    "completed_by": 7,
                    "manhattan_assumable": True,
                    "result": [_scope("normal"), *_clean_points()],
                },
                {
                    "id": 2003,
                    "completed_by": 7,
                    "manhattan_assumable": False,
                    "result": [_scope("normal"), *_clean_points()],
                },
            ],
        }
    ]

    summary = probe_tasks(tasks, include_residuals=True)

    assert summary["n_audit_eligible"] == 1
    assert summary["n_audit_ineligible"] == 2
    assert summary["audit_ineligibility_counts"] == {
        "missing_manhattan_assumable": 1,
        "not_manhattan_assumable": 1,
    }
    assert summary["audit_residual_numeric_summary"]["x_spacing_cv"]["count"] == 1


def test_legacy_keypoint_only_with_residuals_keeps_meta_labels_untrusted():
    summary = probe_tasks(_current_fixture(), legacy_keypoint_only=True, include_residuals=True)

    assert summary["meta_labels_trusted"] is False
    assert summary["scope_alias_counts"] is None
    assert summary["unknown_scope_alias_counts"] is None
    assert summary["audit_eligibility_enabled"] is False
    assert summary["residual_enabled"] is True
    assert summary["n_residual_valid"] == 2
    assert summary["n_audit_eligible"] == 0
    assert summary["n_audit_ineligible"] == 6
    assert summary["audit_ineligibility_counts"] == {"meta_labels_untrusted": 6}


def test_probe_summary_has_no_snap_or_adjustment_fields_when_residuals_enabled():
    summary = probe_tasks(_current_fixture(), include_residuals=True)
    keys = set(summary)
    numeric_keys = set(summary["residual_numeric_summary"])

    assert "snap" not in keys
    assert "snap_to_axis" not in keys
    assert "adjustment" not in keys
    assert "adjustment_vector" not in keys
    assert "snap" not in numeric_keys
    assert "adjustment" not in numeric_keys
