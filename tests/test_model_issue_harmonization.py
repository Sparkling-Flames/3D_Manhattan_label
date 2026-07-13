from tools.thesis_main.analysis.materialize_model_issue_harmonization import harmonize_model_issue


def _geometry(top: int = 100, n: int = 2):
    return [point for x in [100, 500, 800][:n] for point in ([x, top], [x, 400])]


def test_historical_acceptable_in_semi_is_behavior_harmonized() -> None:
    result = harmonize_model_issue(_geometry(120), _geometry(100), explicit_issue="acceptable", condition="semi", provenance_complete=True, schema_family="legacy")
    assert result["harmonized_issue"] == "corner_drift"
    assert result["assertion_source"] == "legacy_behavior_inferred"


def test_future_acceptable_and_concrete_issue_remain_explicit() -> None:
    future = harmonize_model_issue(_geometry(), _geometry(), explicit_issue="acceptable", condition="semi", provenance_complete=False, schema_family="future_c2")
    concrete = harmonize_model_issue(_geometry(), _geometry(), explicit_issue="underextend", condition="semi", provenance_complete=False, schema_family="legacy")
    assert future["harmonized_issue"] == "acceptable"
    assert future["assertion_source"] == "explicit_worker_label"
    assert concrete["harmonized_issue"] == "underextend"
    assert concrete["assertion_source"] == "explicit_worker_label"


def test_historical_semi_requires_initialization_provenance_and_manual_never_infers() -> None:
    missing = harmonize_model_issue(_geometry(120), _geometry(100), explicit_issue="acceptable", condition="semi", provenance_complete=False)
    manual = harmonize_model_issue(_geometry(120), _geometry(100), explicit_issue="acceptable", condition="manual", provenance_complete=True)
    assert missing["inference_reason"] == "missing_required_initialization"
    assert missing["provenance_gate"] == "failed"
    assert manual["assertion_source"] == "not_applicable"


def test_semi_harmonization_requires_order_compatible_geometry() -> None:
    result = harmonize_model_issue(_geometry(120), _geometry(100), explicit_issue="acceptable", condition="semi", provenance_complete=True)
    incompatible = harmonize_model_issue(_geometry(100, 2), _geometry(100, 3), explicit_issue="acceptable", condition="semi", provenance_complete=True)
    assert result["order_gate"] == "passed"
    assert incompatible["order_gate"] == "failed"


def test_no_explicit_acceptable_does_not_trigger_behavior_inference() -> None:
    result = harmonize_model_issue(_geometry(120), _geometry(100), condition="semi", provenance_complete=True)
    assert result["assertion_source"] == "not_applicable"
