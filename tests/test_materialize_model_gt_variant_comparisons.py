from PIL import Image

from tools.thesis_main.analysis.materialize_model_gt_variant_comparisons import _difference, _panel


def test_identical_geometry_has_zero_difference_and_renders() -> None:
    pairs = [
        {"x": 0.0, "y_ceiling": 90.0, "y_floor": 420.0},
        {"x": 512.0, "y_ceiling": 100.0, "y_floor": 410.0},
    ]
    difference, rmse = _difference(pairs, pairs)
    assert difference == 0.0
    assert rmse == 0.0
    assert _panel(Image.new("RGB", (2048, 1024)), [("model", pairs), ("adopted", pairs)]).size == (1024, 512)
