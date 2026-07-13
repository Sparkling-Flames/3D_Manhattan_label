from tools.thesis_main.analysis.geometry_consensus.pairwise import pairwise_similarity
from tools.thesis_main.analysis.geometry_consensus.representation import normalize_geometry


def _rectangle(offset: int = 0):
    return [[100, 100 + offset], [100, 400], [500, 100 + offset], [500, 400]]


def test_representation_is_seam_aware_and_pairwise_metric_is_compatible() -> None:
    left = normalize_geometry(_rectangle())
    right = normalize_geometry(_rectangle(1))
    metrics = pairwise_similarity(left, right)
    assert left["valid"] is True
    assert metrics["metric_compatible"] is True
    assert metrics["overall_similarity"] > 0.99


def test_representation_rejects_odd_or_out_of_range_points() -> None:
    assert normalize_geometry([[0, 10], [0, 400], [500, 10]])["valid"] is False
    assert normalize_geometry([[0, 10], [0, 400], [1025, 10], [1025, 400]])["reason"] == "out_of_range"

