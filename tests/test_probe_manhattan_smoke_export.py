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
