from collections import Counter

from tools.thesis_main.analysis.analyze_rq1_stratified_uncertainty_20260827 import (
    cardinality_shape,
    first_stable_k,
    partial_spearman,
    support_band,
)
from tools.thesis_main.analysis.raw_difficulty_time_recompute_20260826 import normalise_tags


def test_stratification_and_stability_helpers() -> None:
    assert [support_band(k) for k in (0, 1, 2, 4, 5, 7, 8, 14, 15)] == [
        "k0",
        "k1",
        "k2_4",
        "k2_4",
        "k5_7",
        "k5_7",
        "k8_14",
        "k8_14",
        "k15_plus",
    ]
    assert cardinality_shape(Counter({4: 19, 5: 1})) == "cardinality_concentrated"
    assert cardinality_shape(Counter({4: 15, 5: 5})) == "dominant_with_cardinality_dissent"
    assert cardinality_shape(Counter({4: 12, 5: 6, 6: 2})) == "two_dominant_cardinalities"
    assert cardinality_shape(Counter({4: 8, 5: 7, 6: 5})) == "diffuse_cardinality"
    rows = [
        {"k": 5, "p": 0.81},
        {"k": 8, "p": 0.79},
        {"k": 12, "p": 0.88},
        {"k": 15, "p": 0.95},
    ]
    assert first_stable_k(rows, "p") == 12
    tags, _ = normalise_tags('{"difficulty": ["low_texture", "low_quality"]}')
    assert tags == ["low_quality", "low_texture"]


def test_partial_spearman_removes_rank_confounding() -> None:
    rows = [
        {"x": x + residual, "y": x - residual, "z": x}
        for x, residual in zip(range(1, 9), (-1, 1, -1, 1, -1, 1, -1, 1))
    ]
    raw = partial_spearman(rows, "x", "y", "missing")
    adjusted = partial_spearman(rows, "x", "y", "z")
    assert raw is None
    assert adjusted is not None
    assert adjusted < 0
