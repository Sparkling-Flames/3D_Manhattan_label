import csv
import json
from pathlib import Path

from tools.thesis_main.analysis.c1_canonicalize_exports import build_canonicalization
from tools.thesis_main.analysis.c1_materialize_quality_table import materialize as materialize_quality
from tools.thesis_main.analysis.materialize_model_issue_harmonization import harmonize_model_issue, materialize_model_issue_harmonization
from tools.thesis_main.analysis.vfinal_artifact_utils import sha256_json


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
    export_sha = "a" * 64
    meta.write_text("source_export_sha256,project_id,ls_runtime_task_id,canonical_annotation_id,task_id,base_task_id,worker_id,condition,choice_map_json\n" + export_sha + ",P,T,A,t,b,w,semi,\"{\"\"model_issue\"\":[\"\"acceptable\"\"]}\"\n", encoding="utf-8")
    provenance.write_text("project_id,ls_runtime_task_id,task_id,initialization_artifact_id,provenance_status,prediction_selection_status\nP,T,t,artifact,incomplete,selected_unique\n", encoding="utf-8")
    geometry.write_text(json.dumps({"canonical_annotation_id": "A", "corners_px": _geometry(120)}) + "\n", encoding="utf-8")
    with amendment.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=["source_export_sha256", "project_id", "ls_runtime_task_id", "initialization_artifact_id", "model_version", "checkpoint_sha256", "inference_config_sha256", "preprocess_postprocess_sha256", "prediction_payload_sha256", "prediction_payload_json"])
        points = _geometry(100)
        payload = [{"type": "keypointlabels", "value": {"x": x / 1024 * 100, "y": y / 512 * 100}} for x, y in points]
        writer.writeheader(); writer.writerow({"source_export_sha256": export_sha, "project_id": "P", "ls_runtime_task_id": "T", "initialization_artifact_id": "artifact", "model_version": "m", "checkpoint_sha256": "b" * 64, "inference_config_sha256": "c" * 64, "preprocess_postprocess_sha256": "d" * 64, "prediction_payload_sha256": sha256_json(payload), "prediction_payload_json": json.dumps(payload)})
    materialize_model_issue_harmonization([], geometry, tmp_path, retrospective_amendment_csv=amendment)
    row = next(csv.DictReader((tmp_path / "model_issue_harmonization_C1.csv").open(encoding="utf-8")))
    assert row["retrospective_amendment_status"] == "joined_exact_identity"
    assert row["harmonized_issue"] == "corner_drift"
    assert row["harmonization_validity_status"] == "valid_behavior_inferred"


def test_complete_original_provenance_needs_no_retrospective_amendment(tmp_path: Path) -> None:
    export = tmp_path / "export.json"
    initial = [{"type": "keypointlabels", "value": {"x": x / 1024 * 100, "y": y / 512 * 100}} for x, y in _geometry(100)]
    export.write_text(json.dumps([{"id": "T", "project": "P", "predictions": [{"id": "artifact", "result": initial}]}]), encoding="utf-8")
    export_sha = __import__("hashlib").sha256(export.read_bytes()).hexdigest()
    (tmp_path / "c1_canonical_meta_observations.csv").write_text(
        "source_export_sha256,project_id,ls_runtime_task_id,canonical_annotation_id,task_id,base_task_id,worker_id,condition,choice_map_json\n"
        + export_sha + ",P,T,A,t,b,w,semi,\"{\"\"model_issue\"\":[\"\"acceptable\"\"]}\"\n",
        encoding="utf-8",
    )
    (tmp_path / "c1_model_artifact_provenance.csv").write_text(
        "project_id,ls_runtime_task_id,task_id,initialization_artifact_id,provenance_status,prediction_selection_status\nP,T,t,artifact,complete,selected_unique\n",
        encoding="utf-8",
    )
    geometry = tmp_path / "geometry.jsonl"
    geometry.write_text(json.dumps({"canonical_annotation_id": "A", "corners_px": _geometry(120)}) + "\n", encoding="utf-8")
    summary = materialize_model_issue_harmonization([export], geometry, tmp_path, input_status="formal")
    row = next(csv.DictReader((tmp_path / "model_issue_harmonization_C1.csv").open(encoding="utf-8")))
    assert summary["amendment_needed_rows"] == 0
    assert summary["amendment_blockers"] == {}
    assert row["retrospective_amendment_status"] == "not_needed_original_provenance_complete"
    assert row["effective_provenance_status"] == "complete"
    assert row["assertion_source"] == "legacy_behavior_inferred"
    assert row["harmonized_issue"] == "corner_drift"


def test_raw_export_to_quality_three_state_consumes_historical_amendment(tmp_path: Path) -> None:
    def write_csv(path: Path, fields: list[str], rows: list[dict[str, str]]) -> None:
        with path.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=fields)
            writer.writeheader()
            writer.writerows(rows)

    def points(top: int) -> list[dict]:
        return [{"type": "keypointlabels", "value": {"x": x / 1024 * 100, "y": y / 512 * 100}} for x, y in ((100, top), (100, 400), (500, top), (500, 400))]

    export = tmp_path / "export.json"
    export.write_text(json.dumps([{
        "id": "100", "project": 66,
        "data": {"task_id": "task-1", "base_task_id": "base-1", "dataset_group": "Calibration_semi", "condition": "semi", "initialization_artifact_id": "init-1"},
        "predictions": [{"id": "init-1", "model_version": "m1", "checkpoint_sha256": "b" * 64, "inference_config_sha256": "c" * 64, "preprocess_postprocess_sha256": "d" * 64, "result": points(100)}],
        "annotations": [{"id": "ann-1", "completed_by": {"id": "worker-1"}, "created_at": "2026-07-14T00:00:00Z", "result": points(120) + [{"type": "choices", "from_name": "model_issue", "value": {"choices": ["acceptable"]}}]}],
    }]), encoding="utf-8")
    assignment_fields = ["round_id", "worker_id", "task_id", "base_task_id", "dataset_group"]
    assignment = [{"round_id": "C1", "worker_id": "worker-1", "task_id": "task-1", "base_task_id": "base-1", "dataset_group": "Calibration_semi"}]
    manual = tmp_path / "manual.csv"; semi = tmp_path / "semi.csv"; internal = tmp_path / "internal.csv"
    write_csv(manual, assignment_fields, []); write_csv(semi, assignment_fields, assignment); write_csv(internal, assignment_fields, assignment)
    mapping = tmp_path / "mapping.csv"
    write_csv(mapping, ["task_id", "base_task_id", "inner_id", "intended_project_group", "mapping_status"], [{"task_id": "task-1", "base_task_id": "base-1", "inner_id": "1", "intended_project_group": "Calibration_semi", "mapping_status": "planned"}])
    audit = tmp_path / "independence.csv"
    write_csv(audit, ["project_id", "ls_runtime_task_id", "worker_id", "raw_annotation_id", "independence_status"], [{"project_id": "66", "ls_runtime_task_id": "100", "worker_id": "worker-1", "raw_annotation_id": "ann-1", "independence_status": "independent"}])
    payload = points(100)
    amendment = tmp_path / "amendment.csv"
    amendment_fields = ["source_export_sha256", "project_id", "ls_runtime_task_id", "initialization_artifact_id", "checkpoint_sha256", "inference_config_sha256", "preprocess_postprocess_sha256", "prediction_payload_sha256", "prediction_payload_json"]
    write_csv(amendment, amendment_fields, [{"source_export_sha256": __import__("hashlib").sha256(export.read_bytes()).hexdigest(), "project_id": "66", "ls_runtime_task_id": "100", "initialization_artifact_id": "init-1", "checkpoint_sha256": "b" * 64, "inference_config_sha256": "c" * 64, "preprocess_postprocess_sha256": "d" * 64, "prediction_payload_sha256": sha256_json(payload), "prediction_payload_json": json.dumps(payload)}])

    out = tmp_path / "out"
    summary = build_canonicalization([export], manual, semi, internal, mapping, active_log=None, output_dir=out, independence_audit_csv=audit, retrospective_provenance_amendment_csv=amendment)
    assert summary["model_issue_harmonization"]["amendment_complete"] is True
    quality = materialize_quality(out / "c1_canonical_annotations.csv", out, None)
    assert quality["amendment_blocker_count"] == 0
    quality_row = next(csv.DictReader((out / "c1_quality_annotations.csv").open(encoding="utf-8")))
    assert quality_row["harmonized_state"] == "corner_drift"
    assert quality_row["assertion_source"] == "legacy_behavior_inferred"
    observation = next(row for row in csv.DictReader((out / "worker_task_tag_observations_C1.csv").open(encoding="utf-8")) if row["tag_name"] == "corner_drift")
    assert observation["assertion"] == "+"

    bad_amendment = tmp_path / "bad_amendment.csv"
    bad_amendment.write_text(amendment.read_text(encoding="utf-8").replace("b" * 64, "bad"), encoding="utf-8")
    blocked = build_canonicalization([export], manual, semi, internal, mapping, active_log=None, output_dir=tmp_path / "blocked", independence_audit_csv=audit, retrospective_provenance_amendment_csv=bad_amendment)
    assert any(item.startswith("amendment_") for item in blocked["blockers"])
