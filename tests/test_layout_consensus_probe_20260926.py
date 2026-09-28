import inspect

import numpy as np
import pytest
from shapely.geometry import Polygon, box

from tools.thesis_main.analysis.layout_consensus_probe_20260926 import (
    bev_aggregate, make_scenarios, polygon_iou, visible_wall_mask,
    periodic_topology, evaluate_case,
)


def test_exact_tiles_ties_and_no_silent_geometry_repair():
    a, b = box(-3, -2, 3, 2), box(-2, -3, 2, 3)
    assert bev_aggregate([a, b], "mv50").equals(a.union(b))
    assert bev_aggregate([a, b], "mv_strict").equals(a.intersection(b))
    assert bev_aggregate([a, b], "medoid").equals(a)
    assert polygon_iou(a, b) == pytest.approx(.5)
    with pytest.raises(ValueError, match="invalid_polygon"):
        bev_aggregate([Polygon([(0, 0), (2, 2), (0, 2), (2, 0)])], "mv50")
    assert "gt" not in inspect.signature(bev_aggregate).parameters
    separated = [box(-3, -1, -2, 1), box(2, -1, 3, 1)]
    assert bev_aggregate(separated, "mv_strict").is_empty
    assert len(bev_aggregate(separated, "mv50").geoms) == 2


def test_periodic_visibility_and_hole_components():
    p = box(-3, -2, 3, 2)
    mask = visible_wall_mask(p, width=128, height=64)
    reverse = Polygon(list(p.exterior.coords)[::-1])
    assert np.array_equal(mask, visible_wall_mask(reverse, 128, 64))
    assert periodic_topology(mask) == dict(components=1, holes=0, empty=False)
    split = np.zeros((8, 12), bool)
    split[2:6, :2] = split[2:6, -2:] = True
    assert periodic_topology(split)["components"] == 1
    split[3, 0] = False
    assert periodic_topology(split)["holes"] == 1
    with pytest.raises(ValueError, match="camera_not_inside"):
        visible_wall_mask(box(2, 2, 3, 3))


def test_common_bias_is_stable_but_wrong_and_modes_remain_separate():
    cases = make_scenarios()
    permutations = [list(range(12)), list(reversed(range(12)))]
    result = evaluate_case(cases["common_bias"], permutations, width=32, height=16,
                           erp_methods=("mv50",))
    rows = [r for r in result["rows"] if r["domain"] == "bev" and r["route"] == "all"]
    assert all(r["q_primary"] == pytest.approx(5 / 6) for r in rows)
    assert all(r["change"] == 0 for r in rows if r["k"] > 1)
    modes = evaluate_case(cases["two_reasonable_scopes"], permutations[:1],
                          width=32, height=16, erp_methods=("mv50",))
    end = [r for r in modes["rows"] if r["domain"] == "bev" and
           r["method"] == "mv50" and r["k"] == 12]
    assert {r["mode"] for r in end if r["route"] == "each_mode_oracle"} == {"A", "B"}
    assert next(r for r in end if r["route"] == "largest_mode_oracle")["used_count"] == 8
    assert all(r["k"] == 12 for r in end)
    tied = evaluate_case(cases["two_reasonable_scopes"], [[8, 0, *range(1, 8), 9, 10, 11]],
                         width=32, height=16, erp_methods=("mv50",))
    assert all(r["selected_largest_mode"] == "B" for r in tied["rows"]
               if r["route"] == "largest_mode_oracle" and r["k"] == 2)
