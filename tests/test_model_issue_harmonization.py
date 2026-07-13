from tools.thesis_main.analysis.materialize_model_issue_harmonization import harmonize_model_issue


def _geometry(top: int = 100, n: int = 2):
    return [point for x in [100, 500, 800][:n] for point in ([x, top], [x, 400])]


def test_explicit_acceptable_has_precedence_over_geometry_behavior() -> None:
    result = harmonize_model_issue(_geometry(120), _geometry(100), explicit_issue="acceptable", condition="semi", provenance_complete=True)
    assert result["harmonized_issue"] == "acceptable"
    assert result["assertion_source"] == "explicit_worker_label"
    assert result["order_gate"] == "not_needed"


def test_manual_and_missing_provenance_never_infer_model_issue() -> None:
    manual = harmonize_model_issue(_geometry(120), _geometry(100), condition="manual", provenance_complete=True)
    missing = harmonize_model_issue(_geometry(120), _geometry(100), condition="semi", provenance_complete=False)
    assert manual["assertion_source"] == "not_applicable"
    assert missing["provenance_gate"] == "failed"


def test_semi_inference_requires_order_compatible_geometry() -> None:
    result = harmonize_model_issue(_geometry(120), _geometry(100), condition="semi", provenance_complete=True)
    assert result["assertion_source"] == "legacy_behavior_inferred"
    assert result["harmonized_issue"] == "corner_drift"
    incompatible = harmonize_model_issue(_geometry(100, 2), _geometry(100, 3), condition="semi", provenance_complete=True)
    assert incompatible["order_gate"] == "failed"
