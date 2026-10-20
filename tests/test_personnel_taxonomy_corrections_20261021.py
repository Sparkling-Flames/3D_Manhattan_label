"""Regression checks for the two adopted taxonomy aggregation corrections."""
import sys
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
TAXONOMY = ROOT / "research/workers/personnel_taxonomy_20261021"
sys.path.insert(0, str(TAXONOMY / "route_b"))
sys.path.insert(0, str(TAXONOMY / "route_a"))

from evaluate_classification import summaries_from_panels  # noqa: E402
from check_route_b_relations import q_source_match  # noqa: E402


def test_reference_panels_are_equal_within_image_before_building_mean():
    panels = pd.DataFrame([
        {"group": "x", "building_id": "B", "image_id": "I1", "difference": 1},
        {"group": "x", "building_id": "B", "image_id": "I1", "difference": 1},
        {"group": "x", "building_id": "B", "image_id": "I2", "difference": 0},
    ])
    row = summaries_from_panels(panels, ["group"], ["difference"]).iloc[0]
    assert row.difference_building_mean == 0.5
    assert (row.n_panels, row.n_images, row.n_buildings) == (3, 2, 1)


def test_q_match_separates_shared_corner_count_and_contributing_pairs():
    pairs = pd.DataFrame([
        {"building_id": "B", "image_id": "I", "origin_pair": "v1|v1", "count_a": count,
         "same_count": 1, "q_mean": 75, "q_absdiff": 1, "within": within,
         **{metric: value for metric in ("same9", "same12", "bound_deg", "bottom_deg", "top_deg", "floor_iou")}}
        for count, within, value in [(4, True, 1), (4, False, 3), (6, True, 10)]
    ])
    row = q_source_match(pairs, "manual", "A")[0]
    assert row["panel"] == "equal_count_origin_count_Qmean10_Qdiff5_matched"
    assert (row["n_pairs"], row["n_pairs_contributing"], row["n_pairs_unmatched"]) == (3, 2, 1)
    assert row["within_minus_between"] == -2
