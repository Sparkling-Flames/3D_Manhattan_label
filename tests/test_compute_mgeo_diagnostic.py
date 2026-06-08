import json
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.paper_a_manhattan.compute_mgeo_diagnostic import diagnose_submission, main, summarize_workers


def _row(**overrides):
    row = {
        "task_id": "t1",
        "worker_id": "w1",
        "submission_id": "s1",
        "scope": "normal",
        "manhattan_assumable": True,
        "layout_corners": [[0, 0], [4, 0], [4, 3], [0, 3]],
    }
    row.update(overrides)
    return row


def test_valid_rectangle_has_low_residual():
    out = diagnose_submission(_row())

    assert out["geometry_diag_valid"] is True
    assert out["geometry_diag_exclusion_reason"] is None
    assert out["mgeo_renderability_flag"] is True
    assert out["mgeo_manhattan_angle_residual"] == 0.0
    assert out["mgeo_composite_residual"] == 0.0


def test_skewed_quadrilateral_has_higher_angle_residual():
    rectangle = diagnose_submission(_row())
    skewed = diagnose_submission(_row(submission_id="s2", layout_corners=[[0, 0], [4, 0], [5, 3], [0, 3]]))

    assert skewed["geometry_diag_valid"] is True
    assert skewed["mgeo_manhattan_angle_residual"] > rectangle["mgeo_manhattan_angle_residual"]
    assert skewed["mgeo_composite_residual"] > rectangle["mgeo_composite_residual"]


def test_self_intersecting_polygon_is_invalid_renderability():
    out = diagnose_submission(_row(layout_corners=[[0, 0], [4, 4], [0, 4], [4, 0]]))

    assert out["geometry_diag_valid"] is False
    assert out["geometry_diag_exclusion_reason"] == "invalid_polygon"
    assert out["mgeo_renderability_flag"] is False
    assert out["mgeo_composite_residual"] is None


@pytest.mark.parametrize(
    "scope_alias",
    ["oos_geometry", "oos_open_boundary", "oos_split_level", "oos_insufficient"],
)
def test_oos_scope_aliases_are_excluded_not_geometry_failures(scope_alias):
    out = diagnose_submission(_row(scope=scope_alias))

    assert out["geometry_diag_valid"] is False
    assert out["geometry_diag_exclusion_reason"] == scope_alias
    assert out["mgeo_renderability_flag"] is None


@pytest.mark.parametrize("scope_value", [None, "in-scope", "unknown_scope"])
def test_missing_or_unknown_scope_is_excluded(scope_value):
    row = _row(scope=scope_value)
    if scope_value is None:
        row.pop("scope")
    out = diagnose_submission(row)

    assert out["geometry_diag_valid"] is False
    assert out["geometry_diag_exclusion_reason"] == "scope_unknown_or_missing"
    assert out["mgeo_renderability_flag"] is None


def test_missing_manhattan_assumable_is_distinct_from_false():
    row = _row()
    row.pop("manhattan_assumable")
    out = diagnose_submission(row)

    assert out["geometry_diag_valid"] is False
    assert out["geometry_diag_exclusion_reason"] == "missing_manhattan_assumable"
    assert out["mgeo_renderability_flag"] is None


def test_non_manhattan_assumable_is_excluded():
    out = diagnose_submission(_row(manhattan_assumable=False))

    assert out["geometry_diag_valid"] is False
    assert out["geometry_diag_exclusion_reason"] == "not_manhattan_assumable"
    assert out["mgeo_renderability_flag"] is None


def test_paired_ceiling_floor_fields_take_priority_over_xy():
    out = diagnose_submission(
        _row(
            layout_corners=[
                {"x": 99, "y": 99, "x_floor": 0, "y_floor": 0, "x_ceiling": 0.2, "y_ceiling": 10},
                {"x": 99, "y": 99, "x_floor": 4, "y_floor": 0, "x_ceiling": 4.2, "y_ceiling": 10},
                {"x": 99, "y": 99, "x_floor": 4, "y_floor": 3, "x_ceiling": 4.2, "y_ceiling": 13},
                {"x": 99, "y": 99, "x_floor": 0, "y_floor": 3, "x_ceiling": 0.2, "y_ceiling": 13},
            ]
        )
    )

    assert out["geometry_diag_valid"] is True
    assert out["mgeo_vertical_residual"] is not None
    assert out["mgeo_vertical_residual"] > 0


def test_missing_geometry_is_excluded():
    row = _row()
    row.pop("layout_corners")
    out = diagnose_submission(row)

    assert out["geometry_diag_valid"] is False
    assert out["geometry_diag_exclusion_reason"] == "missing_geometry"
    assert out["mgeo_renderability_flag"] is None


def test_worker_summary_uses_valid_rows_only_for_median_and_p90():
    rows = [
        diagnose_submission(_row(worker_id="w1", submission_id="valid_low")),
        diagnose_submission(_row(worker_id="w1", submission_id="valid_high", layout_corners=[[0, 0], [4, 0], [5, 3], [0, 3]])),
        diagnose_submission(_row(worker_id="w1", submission_id="ineligible", scope="oos_geometry")),
        diagnose_submission(_row(worker_id="w1", submission_id="invalid", layout_corners=[[0, 0], [4, 4], [0, 4], [4, 0]])),
        diagnose_submission(_row(worker_id="w1", submission_id="missing", layout_corners=None)),
    ]

    summary = summarize_workers(rows)[0]

    assert summary["worker_id"] == "w1"
    assert summary["n_total_submissions"] == 5
    assert summary["n_geometry_diag_valid"] == 2
    assert summary["n_geometry_diag_excluded"] == 3
    assert summary["n_geometry_diag_ineligible"] == 1
    assert summary["n_geometry_diag_invalid_render"] == 1
    assert summary["n_geometry_diag_missing_or_unparseable"] == 1
    assert summary["mgeo_median"] is not None
    assert summary["mgeo_p90"] is not None
    assert summary["mgeo_invalid_render_count"] == 1


def test_cli_writes_sidecar_and_summary(tmp_path):
    input_path = tmp_path / "submissions.jsonl"
    output_path = tmp_path / "mgeo_sidecar.jsonl"
    summary_path = tmp_path / "mgeo_summary.json"
    rows = [_row(), _row(worker_id="w2", submission_id="excluded", manhattan_assumable=False)]
    input_path.write_text("\n".join(json.dumps(row) for row in rows) + "\n", encoding="utf-8")

    assert main(["--input", str(input_path), "--output", str(output_path), "--summary", str(summary_path)]) == 0

    sidecar_rows = [json.loads(line) for line in output_path.read_text(encoding="utf-8").splitlines()]
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    assert len(sidecar_rows) == 2
    assert sidecar_rows[0]["geometry_diag_valid"] is True
    assert sidecar_rows[1]["geometry_diag_exclusion_reason"] == "not_manhattan_assumable"
    assert summary["score_contract"] == "audit/sensitivity only; not annotation correctness, routing, or formal g_t"
    assert len(summary["workers"]) == 2
