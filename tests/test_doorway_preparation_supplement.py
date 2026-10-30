"""Checks for the derived doorway scope proposals, not GT adoption."""
import importlib.util
from pathlib import Path

from shapely.geometry import Polygon


spec = importlib.util.spec_from_file_location(
    "doorway_supplement",
    Path(__file__).resolve().parents[1]
    / "tools/thesis_main/analysis/supplement_doorway_preparation_20261031.py",
)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def test_clip_interpolates_height_and_preserves_half_area():
    polygon = [[-1, -1, 2], [1, -1, 4], [1, 1, 4], [-1, 1, 2]]
    clipped = module.clip(polygon, {"line": [[0, -2], [0, 2]], "side": 1})
    assert Polygon([p[:2] for p in clipped]).area == 2
    assert all(p[2] == 3 for p in clipped if p[0] == 0)


def test_scope_rules_keep_band_and_invalid_separate():
    cuts = [
        {"line": [[-.1, -2], [-.1, 2]], "side": 1},
        {"line": [[.1, -2], [.1, 2]], "side": -1},
    ]
    assert module.classify([[-1, -1], [1, -1], [1, 1], [-1, 1]], cuts)[0] == "both"
    assert module.classify([[-1, -1], [-.2, -1], [-.2, 1], [-1, 1]], cuts)[0] == "space1"
    assert module.classify([[-.05, -1], [.05, -1], [.05, 1], [-.05, 1]], cuts)[0] == "neither"
    assert module.classify([], cuts) == ("invalid", None)
