import json

from tools.paper_a_manhattan.manhattan_assist_review_harness import (
    HEIGHT_REPROJECT_APPLICABILITY_OPERATION,
    HEIGHT_REPROJECT_ROW_SCHEMA_VERSION,
    SUMMARY_SCHEMA_VERSION,
    build_pair_assist_review_rows,
    summarize_height_reproject_applicability_review,
    summarize_pair_assist_review,
)


TOP_Y = 32.0
BOTTOM_Y = 70.0
COUNT_FIELDS = [
    "n_records",
    "n_candidate_returned",
    "n_suppressed",
    "n_review_only",
    "n_eligible",
    "n_large_delta_blocked",
    "n_manual_review",
    "n_missing_manual_review",
    "n_manual_candidate_returned",
    "n_manual_plausible_yes",
    "n_manual_unsafe_candidate",
    "n_manual_algorithm_overfit",
]


def _record(target_pair, **overrides):
    record = {
        "task_id": "task-1",
        "annotation_id": "ann-1",
        "target_pair_index": 2,
        "ordered_pairs": [
            {"top": {"x": 10.0, "y": TOP_Y}, "bottom": {"x": 10.0, "y": BOTTOM_Y}},
            target_pair,
            {"top": {"x": 60.0, "y": TOP_Y}, "bottom": {"x": 60.0, "y": BOTTOM_Y}},
            {"top": {"x": 80.0, "y": TOP_Y}, "bottom": {"x": 80.0, "y": BOTTOM_Y}},
        ],
    }
    record.update(overrides)
    return record


def _small_mismatch_record(**overrides):
    return _record(
        {"top": {"x": 34.0, "y": TOP_Y}, "bottom": {"x": 30.0, "y": BOTTOM_Y}},
        **overrides,
    )


def _clean_height_record(**overrides):
    return _record(
        {"top": {"x": 30.0, "y": TOP_Y}, "bottom": {"x": 30.0, "y": BOTTOM_Y}},
        **overrides,
    )


def test_candidate_returned_for_clean_small_mismatch_row():
    rows = build_pair_assist_review_rows([_small_mismatch_record()])

    assert len(rows) == 1
    row = rows[0]
    assert row["task_id"] == "task-1"
    assert row["annotation_id"] == "ann-1"
    assert row["operation"] == "align_pair_x"
    assert row["target_pair_index"] == 2
    assert row["state_status"] == "ok"
    assert row["assist_status"] == "eligible"
    assert row["candidate_returned"] is True
    assert row["candidate_retained"] is True
    assert row["movement_gate_status"] == "candidate_retained"
    assert row["max_abs_delta"] == 2.0
    assert row["vertical_x_residual"] == 4.0


def test_large_delta_row_blocks_candidate_and_summary_counts_it():
    records = [
        _record({"top": {"x": 40.0, "y": TOP_Y}, "bottom": {"x": 30.0, "y": BOTTOM_Y}})
    ]

    rows = build_pair_assist_review_rows(records)
    summary = summarize_pair_assist_review(rows)

    assert rows[0]["candidate_returned"] is False
    assert rows[0]["assist_status"] == "review_only"
    assert rows[0]["movement_gate_status"] == "review_only_large_delta"
    assert "max_abs_delta_large" in rows[0]["assist_reasons"]
    assert summary["large_delta_block_rate"] > 0
    assert summary["candidate_retention_rate"] == 0.0


def test_suppressed_metadata_row():
    rows = build_pair_assist_review_rows([
        _small_mismatch_record(metadata={"scope": "oos_insufficient"})
    ])

    assert rows[0]["state_status"] == "excluded"
    assert rows[0]["assist_status"] == "suppress"
    assert rows[0]["candidate_returned"] is False
    assert "state_excluded" in rows[0]["assist_reasons"]


def test_review_only_layout_height_spread_high_row():
    record = _small_mismatch_record()
    record["ordered_pairs"][3]["top"]["y"] = 10.0

    rows = build_pair_assist_review_rows([record])

    assert rows[0]["assist_status"] == "review_only"
    assert rows[0]["candidate_returned"] is False
    assert "layout_height_spread_high" in rows[0]["state_warnings"]
    assert "state_warning_layout_height_spread_high" in rows[0]["assist_reasons"]


def test_manual_review_fields_are_copied():
    rows = build_pair_assist_review_rows([
        _small_mismatch_record(
            manual_review={
                "plausible_candidate": "yes",
                "unsafe_candidate": True,
                "likely_issue": "algorithm_overfit",
                "reviewer_note": "candidate looked risky",
            }
        )
    ])

    row = rows[0]
    assert row["has_manual_review"] is True
    assert row["manual_plausible_candidate"] == "yes"
    assert row["manual_unsafe_candidate"] is True
    assert row["manual_algorithm_overfit"] is True
    assert row["manual_review_notes"] == "candidate looked risky"


def test_summary_handles_empty_rows():
    summary = summarize_pair_assist_review([])

    for field_name in COUNT_FIELDS:
        assert summary[field_name] == 0
    assert summary["candidate_retention_rate"] == 0.0
    assert summary["suppress_rate"] == 0.0
    assert summary["review_only_rate"] == 0.0
    assert summary["eligible_rate"] == 0.0
    assert summary["large_delta_block_rate"] == 0.0
    assert summary["unsafe_candidate_rate"] == 0.0
    assert summary["algorithm_overfit_rate"] == 0.0
    assert summary["manual_review_plausible_rate"] == 0.0
    assert summary["missing_manual_review_rate"] == 0.0
    assert summary["max_abs_delta_p50"] is None
    assert summary["max_abs_delta_p90"] is None
    assert summary["max_abs_delta_max"] is None


def test_summary_handles_rows_without_manual_review():
    rows = build_pair_assist_review_rows([_small_mismatch_record()])
    summary = summarize_pair_assist_review(rows)

    assert rows[0]["has_manual_review"] is False
    assert rows[0]["manual_plausible_candidate"] is None
    assert rows[0]["manual_unsafe_candidate"] is None
    assert rows[0]["manual_algorithm_overfit"] is None
    assert summary["n_records"] == 1
    assert summary["n_candidate_returned"] == 1
    assert summary["n_manual_review"] == 0
    assert summary["n_missing_manual_review"] == 1
    assert summary["n_manual_candidate_returned"] == 0
    assert summary["n_manual_plausible_yes"] == 0
    assert summary["n_manual_unsafe_candidate"] == 0
    assert summary["n_manual_algorithm_overfit"] == 0
    assert summary["missing_manual_review_rate"] == 1.0
    assert summary["manual_review_plausible_rate"] == 0.0
    assert summary["unsafe_candidate_rate"] == 0.0


def test_summary_rates_and_delta_quantiles_are_computed():
    rows = build_pair_assist_review_rows([
        _small_mismatch_record(
            task_id="task-1",
            manual_review={
                "plausible_candidate": "yes",
                "unsafe_candidate": "no",
                "likely_issue": "annotation_geometry",
            },
        ),
        _record(
            {"top": {"x": 40.0, "y": TOP_Y}, "bottom": {"x": 30.0, "y": BOTTOM_Y}},
            task_id="task-2",
            manual_review={
                "plausible_candidate": "unsure",
                "unsafe_candidate": "yes",
                "likely_issue": "algorithm_overfit",
            },
        ),
        _small_mismatch_record(task_id="task-3", metadata={"scope": "oos_insufficient"}),
    ])

    summary = summarize_pair_assist_review(rows)

    assert summary["n_records"] == 3
    assert summary["n_candidate_returned"] == 1
    assert summary["n_suppressed"] == 1
    assert summary["n_review_only"] == 1
    assert summary["n_eligible"] == 1
    assert summary["n_large_delta_blocked"] == 1
    assert summary["n_manual_review"] == 2
    assert summary["n_missing_manual_review"] == 1
    assert summary["n_manual_candidate_returned"] == 1
    assert summary["n_manual_plausible_yes"] == 1
    assert summary["n_manual_unsafe_candidate"] == 0
    assert summary["n_manual_algorithm_overfit"] == 1
    assert summary["candidate_retention_rate"] == 1 / 3
    assert summary["suppress_rate"] == 1 / 3
    assert summary["review_only_rate"] == 1 / 3
    assert summary["eligible_rate"] == 1 / 3
    assert summary["large_delta_block_rate"] == 1 / 3
    assert summary["manual_review_plausible_rate"] == 0.5
    assert summary["algorithm_overfit_rate"] == 0.5
    assert summary["unsafe_candidate_rate"] == 0.0
    assert summary["missing_manual_review_rate"] == 1 / 3
    assert summary["max_abs_delta_p50"] == 3.5
    assert summary["max_abs_delta_p90"] == 4.7
    assert summary["max_abs_delta_max"] == 5.0


def test_manual_candidate_returned_denominator_is_counted_separately():
    rows = build_pair_assist_review_rows([
        _small_mismatch_record(
            task_id="task-1",
            manual_review={
                "plausible_candidate": "no",
                "unsafe_candidate": "yes",
                "likely_issue": "annotation_geometry",
            },
        ),
        _record(
            {"top": {"x": 40.0, "y": TOP_Y}, "bottom": {"x": 30.0, "y": BOTTOM_Y}},
            task_id="task-2",
            manual_review={
                "plausible_candidate": "unsure",
                "unsafe_candidate": "yes",
                "likely_issue": "algorithm_overfit",
            },
        ),
    ])

    summary = summarize_pair_assist_review(rows)

    assert summary["n_manual_review"] == 2
    assert summary["n_manual_candidate_returned"] == 1
    assert summary["n_manual_unsafe_candidate"] == 1
    assert summary["unsafe_candidate_rate"] == 1.0


def test_output_is_json_serializable():
    rows = build_pair_assist_review_rows([_small_mismatch_record()])
    summary = summarize_pair_assist_review(rows)

    assert summary["summary_schema_version"] == SUMMARY_SCHEMA_VERSION
    assert summary["review_harness_version"] == "manhattan_assist_review_harness_m15_6_v1"
    assert "summary_schema_version" not in rows[0]
    assert "height_reproject_row_schema_version" not in rows[0]
    json.dumps(rows)
    json.dumps(summary)


def test_no_annotation_writeback_or_apply_fields_are_produced():
    rows = build_pair_assist_review_rows([_small_mismatch_record()])

    for row in rows:
        assert "annotation" not in row
        assert "writeback" not in row
        assert "apply" not in row
        assert "candidate_pairs" not in row


def test_height_reproject_applicability_operation_generates_row_without_candidate():
    rows = build_pair_assist_review_rows(
        [_clean_height_record()],
        operation=HEIGHT_REPROJECT_APPLICABILITY_OPERATION,
    )

    assert len(rows) == 1
    row = rows[0]
    assert row["operation"] == HEIGHT_REPROJECT_APPLICABILITY_OPERATION
    assert row["state_status"] == "ok"
    assert row["height_reproject_status"] == "eligible"
    assert row["height_reproject_applicable"] is True
    assert row["height_reproject_blocking_reasons"] == []
    assert row["height_reproject_reasons"] == ["height_reproject_applicable"]
    assert row["estimated_layout_height"] is not None
    assert row["layout_height_spread"] == 0.0
    assert row["target_height_residual_before"] == 0.0
    assert row["max_y_delta"] is None
    assert row["y_delta_gate_status"] == "not_evaluated_no_candidate"
    assert row["candidate_returned"] is False
    assert row["candidate_retained"] is False
    assert row["height_reproject_row_schema_version"] == HEIGHT_REPROJECT_ROW_SCHEMA_VERSION
    assert "candidate_pairs" not in row
    assert "annotation" not in row
    assert "writeback" not in row
    assert "apply" not in row


def test_height_reproject_oos_metadata_suppresses_and_keeps_reason():
    rows = build_pair_assist_review_rows(
        [_clean_height_record(metadata={"scope": "oos_insufficient"})],
        operation=HEIGHT_REPROJECT_APPLICABILITY_OPERATION,
    )

    assert rows[0]["height_reproject_status"] == "suppress"
    assert rows[0]["height_reproject_applicable"] is False
    assert "metadata_oos_insufficient" in rows[0]["height_reproject_blocking_reasons"]


def test_height_reproject_layout_height_spread_high_is_review_only():
    record = _clean_height_record()
    record["ordered_pairs"][3]["top"]["y"] = 10.0

    rows = build_pair_assist_review_rows(
        [record],
        operation=HEIGHT_REPROJECT_APPLICABILITY_OPERATION,
    )

    assert rows[0]["height_reproject_status"] == "review_only"
    assert (
        "state_warning_layout_height_spread_high"
        in rows[0]["height_reproject_blocking_reasons"]
    )


def test_height_reproject_summary_counts_statuses_and_reasons():
    review_only_record = _clean_height_record(task_id="review-only")
    review_only_record["ordered_pairs"][3]["top"]["y"] = 10.0
    rows = build_pair_assist_review_rows(
        [
            _clean_height_record(task_id="eligible"),
            _clean_height_record(
                task_id="suppress",
                metadata={"scope": "oos_insufficient"},
                manual_review={"plausible_candidate": "unsure"},
            ),
            review_only_record,
        ],
        operation=HEIGHT_REPROJECT_APPLICABILITY_OPERATION,
    )

    summary = summarize_height_reproject_applicability_review(rows)

    assert summary["n_records"] == 3
    assert summary["n_height_reproject_applicable"] == 1
    assert summary["n_height_reproject_suppressed"] == 1
    assert summary["n_height_reproject_review_only"] == 1
    assert summary["n_height_reproject_blocked"] == 2
    assert summary["height_reproject_applicable_rate"] == 1 / 3
    assert summary["height_reproject_suppress_rate"] == 1 / 3
    assert summary["height_reproject_review_only_rate"] == 1 / 3
    assert summary["n_not_evaluated_no_candidate"] == 3
    assert summary["n_missing_manual_review"] == 2
    assert summary["layout_height_spread_p50"] is not None
    assert summary["layout_height_spread_p90"] is not None
    assert summary["layout_height_spread_max"] is not None
    assert summary["target_height_residual_before_p50"] is not None
    assert summary["target_height_residual_before_p90"] is not None
    assert summary["target_height_residual_before_max"] is not None
    assert summary["height_reproject_reason_counts"]["height_reproject_applicable"] == 1
    assert summary["height_reproject_reason_counts"]["metadata_oos_insufficient"] == 1
    assert (
        summary["height_reproject_reason_counts"]["state_warning_layout_height_spread_high"]
        == 1
    )
    assert "unsafe_candidate_rate" not in summary
    json.dumps(rows)
    json.dumps(summary)


def test_height_reproject_summary_handles_empty_rows():
    summary = summarize_height_reproject_applicability_review([])

    assert summary["n_records"] == 0
    assert summary["n_height_reproject_applicable"] == 0
    assert summary["n_height_reproject_suppressed"] == 0
    assert summary["n_height_reproject_review_only"] == 0
    assert summary["n_height_reproject_blocked"] == 0
    assert summary["height_reproject_applicable_rate"] == 0.0
    assert summary["height_reproject_suppress_rate"] == 0.0
    assert summary["height_reproject_review_only_rate"] == 0.0
    assert summary["n_not_evaluated_no_candidate"] == 0
    assert summary["n_missing_manual_review"] == 0
    assert summary["layout_height_spread_p50"] is None
    assert summary["layout_height_spread_p90"] is None
    assert summary["layout_height_spread_max"] is None
    assert summary["target_height_residual_before_p50"] is None
    assert summary["target_height_residual_before_p90"] is None
    assert summary["target_height_residual_before_max"] is None
    assert summary["height_reproject_reason_counts"] == {}
    assert summary["summary_schema_version"] == (
        "manhattan_height_reproject_applicability_summary_m15_9_v1"
    )
