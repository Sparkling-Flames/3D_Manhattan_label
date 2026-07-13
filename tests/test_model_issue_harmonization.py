from tools.thesis_main.analysis.materialize_model_issue_harmonization import harmonize_model_issue


def _geometry(top: int = 100, n: int = 2):
    corners = []
    for x in [100, 500, 800][:n]:
        corners.extend([[x, top], [x, 400]])
    return corners


def test_harmonization_distinguishes_jitter_and_corner_drift() -> None:
    acceptable = harmonize_model_issue(_geometry(100), _geometry(100))
    drift = harmonize_model_issue(_geometry(120), _geometry(100))
    explicit = harmonize_model_issue(_geometry(120), _geometry(100), explicit_issue="topology_failure")
    assert acceptable["inferred_issue"] == "harmonized_acceptable"
    assert drift["inferred_issue"] == "behavior_inferred_corner_drift"
    assert explicit["harmonized_issue"] == "topology_failure"
    assert explicit["explicit_issue_precedence"] is True


def test_harmonization_does_not_force_structurally_incomparable_geometry() -> None:
    result = harmonize_model_issue(_geometry(100, 2), _geometry(100, 3))
    assert result["inferred_issue"] == "structural_edit_unresolved"
    assert result["interpretation_allowed"] is False
