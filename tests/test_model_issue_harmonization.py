import csv
import json

from tools.thesis_main.analysis.materialize_model_issue_harmonization import harmonize_model_issue, materialize_model_issue_harmonization


def _geometry(top: int = 100, n: int = 2):
    return [point for x in [100, 500, 800][:n] for point in ([x, top], [x, 400])]


def test_historical_acceptable_in_semi_is_behavior_harmonized() -> None:
    result = harmonize_model_issue(_geometry(120), _geometry(100), explicit_issue="acceptable", condition="semi", provenance_complete=True, schema_family="legacy")
    assert result["harmonized_issue"] == "corner_drift"
    assert result["assertion_source"] == "legacy_behavior_inferred"


def test_future_acceptable_and_concrete_issue_remain_explicit() -> None:
    future = harmonize_model_issue(_geometry(), _geometry(), explicit_issue="acceptable", condition="semi", provenance_complete=False, schema_family="c2_future_explicit_acceptable_v1")
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


def test_retrospective_amendment_joins_project_runtime_artifact(tmp_path) -> None:
    meta = tmp_path / "c1_canonical_meta_observations.csv"
    provenance = tmp_path / "c1_model_artifact_provenance.csv"
    geometry = tmp_path / "geometry.jsonl"
    amendment = tmp_path / "amendment.csv"
    meta.write_text("project_id,ls_runtime_task_id,canonical_annotation_id,task_id,base_task_id,worker_id,condition,choice_map_json\nP,T,A,t,b,w,semi,\"{\"\"model_issue\"\":[\"\"acceptable\"\"]}\"\n", encoding="utf-8")
    provenance.write_text("project_id,ls_runtime_task_id,task_id,initialization_artifact_id,provenance_status,prediction_selection_status\nP,T,t,artifact,incomplete,selected_unique\n", encoding="utf-8")
    geometry.write_text(json.dumps({"canonical_annotation_id": "A", "corners_px": _geometry(120)}) + "\n", encoding="utf-8")
    with amendment.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=["project_id", "ls_runtime_task_id", "initialization_artifact_id", "model_version", "checkpoint_sha256", "inference_config_sha256", "preprocess_postprocess_sha256", "prediction_payload_json"])
        points = _geometry(100)
        writer.writeheader(); writer.writerow({"project_id": "P", "ls_runtime_task_id": "T", "initialization_artifact_id": "artifact", "model_version": "m", "checkpoint_sha256": "c", "inference_config_sha256": "i", "preprocess_postprocess_sha256": "p", "prediction_payload_json": json.dumps([{"type": "keypointlabels", "value": {"x": x / 1024 * 100, "y": y / 512 * 100}} for x, y in points])})
    materialize_model_issue_harmonization([], geometry, tmp_path, retrospective_amendment_csv=amendment)
    row = next(csv.DictReader((tmp_path / "model_issue_harmonization_C1.csv").open(encoding="utf-8")))
    assert row["retrospective_amendment_status"] == "joined_exact_project_runtime_artifact"
    assert row["harmonized_issue"] == "corner_drift"
