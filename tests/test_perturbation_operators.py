import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent / "tools"))

from perturbation_operators import (  # noqa: E402
    AcceptableOperator,
    CatastrophicFailOperator,
    CornerDuplicateOperator,
    CornerShiftOperator,
    OverExtendOperator,
    OverParsingOperator,
    PerturbationEngine,
    TopologyBreakOperator,
    UnderExtendOperator,
    XML_ALIAS_SET,
    freeze_plan,
)


RECT_CORNERS_NORM = [
    {"id": 0, "x_pct": 10.0, "y_top_pct": 20.0, "y_bottom_pct": 70.0},
    {"id": 1, "x_pct": 35.0, "y_top_pct": 18.0, "y_bottom_pct": 72.0},
    {"id": 2, "x_pct": 65.0, "y_top_pct": 19.0, "y_bottom_pct": 71.0},
    {"id": 3, "x_pct": 90.0, "y_top_pct": 20.0, "y_bottom_pct": 70.0},
]

PANORAMA_WRAP_CASE = [
    {"id": 0, "x_pct": 99.5, "y_top_pct": 2.0, "y_bottom_pct": 98.0},
    {"id": 1, "x_pct": 20.0, "y_top_pct": 20.0, "y_bottom_pct": 80.0},
    {"id": 2, "x_pct": 60.0, "y_top_pct": 20.0, "y_bottom_pct": 80.0},
    {"id": 3, "x_pct": 85.0, "y_top_pct": 20.0, "y_bottom_pct": 80.0},
]


EXPECTED_XML_ALIASES = {
    "acceptable",
    "overextend_adjacent",
    "underextend",
    "over_parsing",
    "corner_drift",
    "corner_duplicate",
    "topology_failure",
    "fail",
}


def test_alias_set_matches_xml_contract():
    assert XML_ALIAS_SET == EXPECTED_XML_ALIASES


def test_acceptable_operator_none_is_noop():
    result = AcceptableOperator().apply(RECT_CORNERS_NORM, 1024, 512, seed=42, lambda_level="none")
    assert result["status"] == "success"
    assert result["family_id"] == "acceptable"
    assert result["corners_norm"] == RECT_CORNERS_NORM


def test_corner_shift_is_seed_deterministic():
    operator = CornerShiftOperator()
    left = operator.apply(RECT_CORNERS_NORM, 1024, 512, seed=77, lambda_level="medium", config={"corner_index": 1})
    right = operator.apply(RECT_CORNERS_NORM, 1024, 512, seed=77, lambda_level="medium", config={"corner_index": 1})
    assert left == right


def test_corner_shift_wraps_x_and_clamps_y():
    result = CornerShiftOperator().apply(
        PANORAMA_WRAP_CASE,
        1024,
        512,
        seed=1,
        lambda_level="strong",
        config={"corner_index": 0, "x_delta_pct": 5.0, "y_top_delta_pct": -10.0, "y_bottom_delta_pct": 10.0},
    )
    mutated = result["corners_norm"][0]
    assert 0.0 <= mutated["x_pct"] <= 100.0
    assert mutated["x_pct"] < 10.0
    assert 0.0 <= mutated["y_top_pct"] <= 100.0
    assert 0.0 <= mutated["y_bottom_pct"] <= 100.0
    assert result["audit"]["x_rule"] == "wrap"
    assert result["audit"]["y_rule"] == "clamp"


def test_corner_duplicate_adds_point():
    result = CornerDuplicateOperator().apply(RECT_CORNERS_NORM, 1024, 512, seed=99, lambda_level="weak", config={"corner_index": 2})
    assert result["status"] == "success"
    assert len(result["corners_norm"]) == len(RECT_CORNERS_NORM) + 1


def test_underextend_reduces_point_count():
    result = UnderExtendOperator().apply(RECT_CORNERS_NORM, 1024, 512, seed=2, lambda_level="weak", config={"remove_index": 1})
    assert result["status"] == "success"
    assert len(result["corners_norm"]) == len(RECT_CORNERS_NORM) - 1


def test_overextend_requires_explicit_context():
    result = OverExtendOperator().apply(RECT_CORNERS_NORM, 1024, 512, seed=3, lambda_level="weak", config={})
    assert result["status"] == "invalid"
    assert result["failure_code"] == "config_missing"


def test_overparsing_requires_context_or_surrogate():
    result = OverParsingOperator().apply(RECT_CORNERS_NORM, 1024, 512, seed=4, lambda_level="weak", config={})
    assert result["status"] == "invalid"
    assert result["failure_code"] == "config_missing"


def test_intentional_invalid_contracts_hold():
    topology = TopologyBreakOperator().apply(RECT_CORNERS_NORM, 1024, 512, seed=5, lambda_level="fixed")
    fail = CatastrophicFailOperator().apply(RECT_CORNERS_NORM, 1024, 512, seed=6, lambda_level="fixed")
    assert topology["audit"]["is_intentionally_invalid"] is True
    assert topology["audit"]["iou_status"] == "na_intentional"
    assert fail["audit"]["is_intentionally_invalid"] is True
    assert fail["audit"]["iou_status"] == "na_intentional"


def test_freeze_plan_replay_is_stable():
    manifest_rows = [
        {
            "manifest_row_id": "row_001",
            "target_registry_uid": "stage1_prescreen_semi:1",
            "base_task_id": "scene_001",
            "title": "scene_001.jpg",
            "operator_id": "corner_duplicate",
            "source_type": "synthetic_operator",
            "lambda_level": "weak",
            "seed": 123,
            "config": {"corner_index": 1},
        }
    ]
    task_sources = {
        "scene_001": {
            "title": "scene_001.jpg",
            "image_width": 1024,
            "image_height": 512,
            "prediction_hash": "demo_hash",
            "corners_norm": RECT_CORNERS_NORM,
        }
    }
    frozen_plan = freeze_plan(manifest_rows, task_sources)
    engine = PerturbationEngine()
    first = engine.generate_batch(frozen_plan, task_sources)
    second = engine.generate_batch(json.loads(json.dumps(frozen_plan)), task_sources)
    assert first == second
