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
    assert metrics["boundary_similarity"] > 0.99
    assert metrics["wallwall_similarity"] > 0.99
    assert metrics["overall_similarity"] is None


def test_representation_rejects_odd_or_out_of_range_points() -> None:
    assert normalize_geometry([[0, 10], [0, 400], [500, 10]])["valid"] is False
    assert normalize_geometry([[0, 10], [0, 400], [1025, 10], [1025, 400]])["reason"] == "out_of_range"


def test_legal_seam_polygon_is_not_planar_self_intersection() -> None:
    geometry = normalize_geometry([[1000, 100], [1000, 400], [20, 100], [20, 400]])
    assert geometry["seam_crossing_detected"] is True
    assert geometry["polygon_simple"] is True
    assert geometry["topology_valid"] is True


def test_raw_alternating_order_resolves_an_unordered_pairing_tie() -> None:
    geometry = normalize_geometry([[100, 100], [110, 400], [110, 120], [120, 420]])
    assert geometry["valid"] is True
    assert geometry["pairing_method"] == "raw_order_pairing"
    assert geometry["pairing_stats"]["unordered_pairing_ambiguous"] is True


def test_variable_corner_counts_keep_boundary_and_wall_diagnostics() -> None:
    metrics = pairwise_similarity(
        normalize_geometry(_rectangle()),
        normalize_geometry([[100, 100], [100, 400], [500, 100], [500, 400], [800, 100], [800, 400]]),
    )
    assert metrics["boundary_metric_compatible"] is True
    assert metrics["wall_event_metric_compatible"] is True
    assert metrics["pointwise_correspondence_compatible"] is False
    assert metrics["boundary_similarity"] is not None
    assert metrics["wallwall_similarity"] is not None
