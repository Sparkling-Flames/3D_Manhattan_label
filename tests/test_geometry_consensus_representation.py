from tools.thesis_main.analysis.geometry_consensus.pairwise import pairwise_similarity
from tools.thesis_main.analysis.geometry_consensus.representation import normalize_geometry, normalize_geometry_for_c1_calculation
from tools.thesis_main.analysis.quality_core.geometry_metrics import analyze_layout_pairing


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


def test_c1_calculation_repair_requires_one_unique_orphan_point() -> None:
    repaired = normalize_geometry_for_c1_calculation([[100, 100], [100, 400], [500, 100], [500, 400], [800, 250]])
    ambiguous = normalize_geometry_for_c1_calculation([[100, 100], [100, 400], [500, 100], [500, 400], [510, 120]])

    assert repaired["valid"] is True
    assert repaired["geometry_repair_applied"] is True
    assert repaired["dropped_point_index"] == 4
    assert repaired["raw_point_count"] == 5 and repaired["repaired_point_count"] == 4
    assert repaired["raw_geometry_sha256"] and repaired["repaired_geometry_sha256"]
    assert ambiguous["valid"] is False
    assert ambiguous["geometry_repair_status"] == "ambiguous_extra_or_missing_pair"


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


def test_raw_adjacent_pairs_accept_reversed_floor_ceiling_direction() -> None:
    geometry = normalize_geometry([[100, 400], [100, 100], [500, 100], [500, 400]])
    assert geometry["valid"] is True
    assert geometry["pairing_method"] == "raw_order_pairing"
    assert geometry["pairs"][0]["y_ceiling"] < geometry["pairs"][0]["y_floor"]


def test_raw_adjacent_pairs_accept_reversed_floor_ceiling_direction() -> None:
    geometry = normalize_geometry([[100, 400], [100, 100], [500, 100], [500, 400]])
    assert geometry["valid"] is True
    assert geometry["pairing_method"] == "raw_order_pairing"
    assert geometry["pairs"][0]["y_ceiling"] < geometry["pairs"][0]["y_floor"]


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


def test_unordered_28_points_are_solved_without_changing_input() -> None:
    # W15/W21, yqstnuAEVhm_e650c19e3eb34cc0b98374e5a23d1f65:
    # the five independent components formerly exhausted the global search.
    points = [
        [173.96138996138995, 202.95495495495496], [170.007722007722, 316.2934362934363],
        [365.05534105534105, 208.22651222651223], [363.73745173745175, 309.7039897039897],
        [536.3809523809524, 187.14028314028315], [535.063063063063, 333.4259974259974],
        [541.6525096525097, 367.6911196911197], [544.2882882882883, 152.87516087516087],
        [636.5405405405405, 197.68339768339766], [635.2226512226512, 318.9292149292149],
        [666.8519948519948, 338.6975546975547], [665.5341055341055, 181.86872586872587],
        [678.7129987129987, 217.45173745173742], [846.0849420849422, 214.81595881595885],
        [847.4028314028315, 300.4787644787645], [888.2574002574003, 193.72972972972974],
        [889.5752895752896, 321.5649935649936], [925.1583011583011, 208.22651222651223],
        [967.1715302011161, 205.13144186516968], [966.3084003439031, 301.80198587299174],
        [953.3614524857128, 192.1844940069792], [954.2245823429254, 329.42214130379807],
        [923.8769365633271, 302.66511573020443], [991.2010654259175, 362.2210758778805],
        [988.6116758542795, 157.6592997184713], [1004.1480132841078, 332.87466073264886],
        [1003.2848834268952, 187.005714863703], [678.7480571149212, 298.34946644414094],
    ]
    original = [point[:] for point in points]
    geometry = normalize_geometry(points)
    assert geometry["valid"] is True
    assert geometry["pairing_method"] == "circular_x_pairing"
    assert geometry["n_pairs"] == 14
    stats = geometry["pairing_stats"]
    assert stats["pairing_search_exhausted"] is False
    assert stats["pairing_search_nodes"] < 10_000
    assert stats["optimal_matching_count"] == 1
    assert abs(stats["best_cost"] - 20.99198463695501) < 1e-9
    assert abs(stats["second_best_cost"] - 31.535099180069608) < 1e-9
    assert points == original == geometry["raw_points"] == geometry["canonical_points"]


def test_component_pairing_retains_global_ties_and_relative_margin() -> None:
    points = [[offset + x, y] for offset in (100, 500)
              for x, y in ((0, 10), (10, 20), (10.3, 30), (20, 40))]
    _, stats = analyze_layout_pairing(points, ambiguity_abs_epsilon=1.0)
    # Each component has three epsilon-tied solutions, but choosing a worse
    # solution in BOTH costs 1.2 overall: five global ties, not 3 * 3.
    assert stats["optimal_matching_count"] == 5
    assert abs(stats["best_cost"] - 39.4) < 1e-9
    assert abs(stats["second_best_cost"] - 40.6) < 1e-9
    assert stats["ambiguity_reason"] == "exact_tied_optimum"

    _, near = analyze_layout_pairing([[100, 10], [110, 20], [110.2, 30], [120, 40], [600, 10], [640, 40]])
    assert near["optimal_matching_count"] == 1
    assert near["ambiguity_reason"] == "near_equivalent_matching"

    tied = [[x, y] for x in range(100, 1000, 100) for y in (10, 20, 30, 40)]
    _, many = analyze_layout_pairing(tied)
    assert many["pairing_search_exhausted"] is False
    assert many["optimal_matching_count"] == 3 ** 9
    assert many["second_best_cost"] is None
    assert many["ambiguity_reason"] == "exact_tied_optimum"

    pairs, limited = analyze_layout_pairing(tied, maximum_search_nodes=1)
    assert pairs == []
    assert limited["pairing_search_exhausted"] is True
    assert limited["best_cost"] is None
