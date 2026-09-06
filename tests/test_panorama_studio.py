"""Independent geometric checks for the read-only panorama studio."""
import copy
import math

import numpy as np
import pytest

from tools.label_studio.panorama_studio.geometry import (
    analyze, pixel_ray, project_pixel, read_layout, triangulate,
)


def room(points, ceiling=1.3, scale=1):
    return {"width": 1024, "height": 512, "coordinate_mode": "pixels",
            "ordered_pairs": [{"source_pair_id": f"p{i}",
                "top": dict(zip(("x", "y"), project_pixel([x*scale, ceiling*scale, z*scale], 1024, 512))),
                "bottom": dict(zip(("x", "y"), project_pixel([x*scale, -scale, z*scale], 1024, 512)))}
                for i, (x, z) in enumerate(points)]}


RECT = [(-2, -3), (3, -3), (3, 2), (-2, 2)]
CONCAVE = [(-3, -3), (1, -3), (1, -1), (3, -1), (3, 3), (-3, 3)]


@pytest.mark.parametrize("points", [RECT, CONCAVE, [(-2,-3),(0,-3),(3,-3),(3,2),(-2,2)]])
def test_exact_manhattan_recovery_and_area(points):
    result = analyze(room(points))
    assert result["fit"]["status"] == "ok", result["fit"]
    assert result["fit"]["residual_mean_deg"] < 1e-4
    assert np.allclose(np.array(result["raw"]["floor"])[:, [0,2]], points)
    tris = triangulate(points)
    area = sum(abs(np.linalg.det(np.array([np.array(points[b])-points[a], np.array(points[c])-points[a]])))/2
               for a,b,c in tris)
    expected = abs(sum(points[i][0]*points[(i+1)%len(points)][1]-points[(i+1)%len(points)][0]*points[i][1]
                       for i in range(len(points))))/2
    assert area == pytest.approx(expected)


def test_seam_roundtrip_scale_and_input_identity():
    for x in [0, .01, 511, 1023.99, 1024]:
        p = project_pixel(pixel_ray(x, 310, 1024,512), 1024,512)
        assert abs((p[0]-x+512)%1024-512) < 1e-8
        assert p[1] == pytest.approx(310)
    original = room(RECT)
    snapshot = copy.deepcopy(original)
    result = analyze(original)
    assert original == snapshot
    assert [p["source_pair_id"] for p in result["pairs"]] == [f"p{i}" for i in range(4)]
    assert analyze(room(RECT, scale=7))["raw"]["floor"] == pytest.approx(np.array(result["raw"]["floor"]))


def test_bad_order_not_silently_sorted():
    data = room(RECT)
    data["ordered_pairs"][1], data["ordered_pairs"][2] = data["ordered_pairs"][2], data["ordered_pairs"][1]
    result = analyze(data)
    assert result["fit"]["status"] == "blocked"
    assert "invalid_footprint" in result["raw"]["issues"]
    assert [p["source_pair_id"] for p in result["pairs"]] == ["p0","p2","p1","p3"]


def test_mismatched_top_x_preserved_and_reprojected():
    data = room(RECT)
    data["ordered_pairs"][0]["top"]["x"] += 8
    result = analyze(data)
    assert "vertical_pair_mismatch" in result["raw"]["issues"]
    top = result["raw"]["ceiling"][0]
    assert project_pixel(top,1024,512)[0] == pytest.approx(data["ordered_pairs"][0]["top"]["x"])
    assert result["fit"]["status"] == "ok"
    assert result["fit"]["residual_max_deg"] > .1


@pytest.mark.parametrize("kind", ["horizon", "wrong_hemisphere", "duplicate", "degenerate"])
def test_invalid_inputs_fail_explicitly(kind):
    data = room(RECT)
    if kind == "horizon": data["ordered_pairs"][0]["bottom"]["y"] = 256.01
    if kind == "wrong_hemisphere": data["ordered_pairs"][0]["bottom"]["y"] = 210
    if kind == "duplicate": data["ordered_pairs"][1] = {**copy.deepcopy(data["ordered_pairs"][0]), "source_pair_id":"p1"}
    if kind == "degenerate": data = room([(-1,2),(0,2),(1,2)])
    result = analyze(data)
    assert result["fit"]["status"] == "blocked"
    assert result["raw"]["issues"]


def test_txt_and_explicit_percent_json(tmp_path):
    path = tmp_path / "corners.txt"
    data = room(RECT)
    path.write_text("\n".join(f"{p[e]['x']} {p[e]['y']}" for p in data["ordered_pairs"] for e in ["top","bottom"]))
    assert len(read_layout(path)["ordered_pairs"]) == 4
    percent = copy.deepcopy(data)
    percent["coordinate_mode"] = "ls_percent"
    for p in percent["ordered_pairs"]:
        for e in ["top","bottom"]:
            p[e]["x"] *= 100/1024
            p[e]["y"] *= 100/512
    assert np.allclose(analyze(percent)["raw"]["floor"], analyze(data)["raw"]["floor"])
    path.write_text("1 2\n3 4\n5 6")
    with pytest.raises(ValueError, match="even"): read_layout(path)


def test_identity_and_nonfinite_validation():
    data = room(RECT)
    data["ordered_pairs"][1]["source_pair_id"] = "p0"
    with pytest.raises(ValueError, match="identity"): analyze(data)
    data = room(RECT)
    data["ordered_pairs"][0]["top"]["x"] = math.nan
    with pytest.raises(ValueError, match="finite"): analyze(data)
