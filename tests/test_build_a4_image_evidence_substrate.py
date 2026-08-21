from tools.thesis_main.analysis.build_a4_image_evidence_substrate import parse_geometry, wrapped_horizontal_gradient


def test_seam_gradient_includes_wrap_edge():
    assert wrapped_horizontal_gradient([0, 10, 20, 30]) == [10, 10, 10, 30]


def test_geometry_descriptor_is_gt_free_and_circular():
    descriptor = parse_geometry("[[0, 10], [100, 20], [990, 30]]", 1000, 100)
    assert descriptor["corner_count"] == 3
    assert descriptor["circular_x_coverage_norm"] > 0


def test_invalid_geometry_fails_closed():
    assert parse_geometry("not-json", 1000, 500) is None
