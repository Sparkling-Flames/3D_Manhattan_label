from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path

import pytest

from tools.thesis_main.analysis.materialize_reviewer_profile_dual_stage import (
    DEFAULT_OUTPUT_DIR,
    REQUIRED_OUTPUTS,
    _task_centered_correlation_bootstrap,
    _task_centered_residuals,
    bootstrap_ci,
    classify_behavior,
    load_runtime,
    materialize,
    validate_c1_reference,
    validate_import_pair,
)


def _write_json(path: Path, value: object) -> Path:
    path.write_text(json.dumps(value), encoding="utf-8")
    return path


def _import_task(base: str = "scene", x: float = 10.0) -> dict:
    return {
        "data": {"base_task_id": base, "task_id": "1", "condition": "semi"},
        "predictions": [
            {
                "model_version": "model-v1",
                "result": [
                    {"type": "keypointlabels", "value": {"x": x, "y": 10.0}},
                    {"type": "keypointlabels", "value": {"x": x, "y": 90.0}},
                    {"type": "keypointlabels", "value": {"x": 60.0, "y": 10.0}},
                    {"type": "keypointlabels", "value": {"x": 60.0, "y": 90.0}},
                ],
            }
        ],
    }


def test_import_pair_fails_closed_on_missing_duplicate_and_language_conflict(tmp_path: Path) -> None:
    en = _write_json(tmp_path / "en.json", [_import_task()])
    zh = _write_json(tmp_path / "zh.json", [_import_task()])
    assert len(validate_import_pair("C1", {"en": en, "zh": zh}, expected_count=1)) == 2

    missing = _import_task()
    missing["predictions"] = []
    _write_json(en, [missing])
    with pytest.raises(ValueError, match="prediction_count"):
        validate_import_pair("C1", {"en": en, "zh": zh}, expected_count=1)

    duplicate = _import_task()
    duplicate["predictions"] *= 2
    _write_json(en, [duplicate])
    with pytest.raises(ValueError, match="prediction_count"):
        validate_import_pair("C1", {"en": en, "zh": zh}, expected_count=1)

    _write_json(en, [_import_task(x=11.0)])
    with pytest.raises(ValueError, match="language_prediction_geometry_conflict"):
        validate_import_pair("C1", {"en": en, "zh": zh}, expected_count=1)


def test_runtime_and_reference_sha_checks_fail_closed(tmp_path: Path) -> None:
    prediction = _import_task()["predictions"][0]
    runtime = _write_json(
        tmp_path / "runtime.json",
        [
            {
                "id": 10,
                "project": 20,
                "data": {"base_task_id": "scene"},
                "annotations": [{"id": 30, "completed_by": 40, "result": [], "prediction": prediction}],
            }
        ],
    )
    digest = hashlib.sha256(runtime.read_bytes()).hexdigest()
    assert load_runtime(runtime, "20", expected_sha256=digest)["scene"]["runtime_task_id"] == "10"
    with pytest.raises(ValueError, match="runtime_export_sha256_mismatch"):
        load_runtime(runtime, "20", expected_sha256="0" * 64)

    frozen = {"reference_identity": "gt:1", "reference_sha256": "a" * 64, "geometry_reference_ready": "true"}
    reference = {"identity": "gt:1", "sha256": "a" * 64, "points": [[1, 2]], "structural_status": "valid"}
    assert validate_c1_reference(frozen, reference) is reference
    with pytest.raises(ValueError, match="reference_missing"):
        validate_c1_reference(frozen, {})
    with pytest.raises(ValueError, match="reference_sha256_mismatch"):
        validate_c1_reference(frozen, {**reference, "sha256": "b" * 64})


def test_threshold_boundaries_missingness_and_stage_vocabulary() -> None:
    p1 = classify_behavior(
        stage="P1", role="trap", issue_reported=True, acceptable=False,
        exact_equal=False, delta_u=0.01, epsilon=0.01,
    )
    assert p1["issue_reported_without_quality_improvement"] is True
    assert p1["quality_improving_correction"] is False
    assert p1["harmful_correction"] is False
    assert "successful_correction" not in p1
    assert "safe_control_acceptance" not in p1

    unchanged = classify_behavior(
        stage="P1", role="trap", issue_reported=True, acceptable=False,
        exact_equal=True, delta_u=0.0, epsilon=0.01,
    )
    assert unchanged["unmodified_trap_submission"] is True
    assert unchanged["strict_blind_trust"] is False
    assert "unmodified_trap_acceptance" not in unchanged

    missing = classify_behavior(
        stage="P1", role="trap", issue_reported=True, acceptable=False,
        exact_equal=False, delta_u=None, epsilon=0.01,
    )
    assert missing["quality_improving_correction"] is None
    assert missing["issue_reported_without_quality_improvement"] is None

    c1 = classify_behavior(
        stage="C1", role="", issue_reported=False, acceptable=True,
        exact_equal=True, delta_u=0.0, epsilon=0.01,
    )
    assert "strict_blind_trust" not in c1
    assert c1["proposal_accepted_unchanged"] is True
    assert c1["non_harmful_handling"] is True
    assert c1["issue_geometry_edit_concordant"] is True
    assert "non_harmful_correction" not in c1


def test_task_centering_and_adjusted_worker_bootstrap_are_deterministic() -> None:
    rows = [
        {"worker_id": "1", "base_task_id": "a", "value": 1.0},
        {"worker_id": "2", "base_task_id": "a", "value": 3.0},
        {"worker_id": "1", "base_task_id": "b", "value": 2.0},
        {"worker_id": "2", "base_task_id": "b", "value": 4.0},
    ]
    residuals = _task_centered_residuals(rows, "value", {"1", "2"})
    assert residuals == {"1": [-1.0, -1.0], "2": [1.0, 1.0]}
    first = _task_centered_correlation_bootstrap(
        {"1": 0.0, "2": 1.0}, rows, "value", {"1", "2"}, draws=1000, seed=20260819,
    )
    second = _task_centered_correlation_bootstrap(
        {"1": 0.0, "2": 1.0}, rows, "value", {"1", "2"}, draws=1000, seed=20260819,
    )
    assert first == second


def test_bootstrap_is_reproducible_at_required_draw_count() -> None:
    first = bootstrap_ci([0.0, 1.0, 2.0, 3.0], draws=1000, seed=20260819)
    second = bootstrap_ci([0.0, 1.0, 2.0, 3.0], draws=1000, seed=20260819)
    assert first == second
    assert first[2] == 1000


def test_real_dual_stage_materialization_closes_denominators_and_manifest(tmp_path: Path) -> None:
    root = Path(__file__).resolve().parents[1]
    assert DEFAULT_OUTPUT_DIR.name == "reviewer_profile_dual_stage_processing_20260819_v2"
    summary = materialize(root, tmp_path, bootstrap_draws=20)

    assert summary["p1_canonical"] == 468
    assert summary["p1_raw"] == 469
    assert summary["p1_extra_raw_disposition"] == "duplicate_same_geometry"
    assert summary["p1_workers"] == 26
    assert summary["p1_trap"] == 312
    assert summary["p1_control"] == 156
    assert summary["p1_c1_eligible_support"] == 414
    assert summary["p1_current20_support"] == 360
    assert summary["c1_canonical"] == 106
    assert summary["c1_tasks"] == 25
    assert summary["c1_workers"] == 23
    assert summary["c1_formal_assignment_eligible"] == 104
    assert summary["c1_semi_correction_eligible"] == 88
    assert summary["c1_delta_u_evaluable"] == 82
    assert summary["c1_delta_u_missing"] == 6
    assert summary["cross_stage_worker_evaluable"] == 22
    assert summary["cross_stage_worker_missing"] == 1
    assert summary["observed_canonical_initialization_binding"] == "recovered"

    assert {path.name for path in tmp_path.iterdir()} == set(REQUIRED_OUTPUTS)
    manifest = json.loads((tmp_path / "analysis_manifest.json").read_text(encoding="utf-8"))
    assert manifest["method_contract_version"] == "paper_a_method_20260811_v23"
    inputs = {item["role"]: item for item in manifest["inputs"]}
    for role, path in {
        "processing_script": root / "tools/thesis_main/analysis/materialize_reviewer_profile_dual_stage.py",
        "processing_test": Path(__file__),
    }.items():
        assert inputs[role]["sha256"] == hashlib.sha256(path.read_bytes()).hexdigest()
    for item in manifest["outputs"]:
        path = tmp_path / item["path"]
        assert hashlib.sha256(path.read_bytes()).hexdigest() == item["sha256"]
    for name in REQUIRED_OUTPUTS:
        if not name.endswith(".csv"):
            continue
        rows = list(csv.DictReader((tmp_path / name).open(encoding="utf-8")))
        assert rows and all(row["diagnostic_pre_stage3"] == "true" for row in rows)
        assert all(row["main_launch_authorized"] == "false" for row in rows)

    evidence_header = next(csv.reader((tmp_path / "SEMI_ROW_LEVEL_REVIEWER_EVIDENCE.csv").open(encoding="utf-8")))
    assert any("unmodified_trap_submission" in field for field in evidence_header)
    assert not any(
        "successful_correction" in field
        or "safe_control_acceptance" in field
        or "non_harmful_correction" in field
        or "unmodified_trap_acceptance" in field
        for field in evidence_header
    )
    c1_header = next(csv.reader((tmp_path / "C1_REVIEWER_VALIDATION_PROFILE.csv").open(encoding="utf-8")))
    assert "task_centered_delta_u_mean" in c1_header
    assert not any(field.startswith("task_adjusted_") for field in c1_header)
    readiness = {row["check_id"]: row for row in csv.DictReader((tmp_path / "REVIEWER_PROFILE_READINESS.csv").open(encoding="utf-8"))}
    assert readiness["c1_delta_u_row_support"]["observed"] == "82/88"
    assert readiness["cross_stage_worker_support"]["observed"] == "22/23"
    assert readiness["c1_task_adjustment"]["status"] == "warning"
    assert readiness["c1_task_adjustment"]["observed"] == "partial_task_centering"
    assert readiness["append_only_audit_history"]["status"] == "warning"
    assert readiness["cross_stage_reviewer_ability_validation"]["status"] == "not_ready"
    assert readiness["expert_or_m1_selection"]["status"] == "no_go"

    threshold_metrics = {
        row["metric"]
        for row in csv.DictReader((tmp_path / "REVIEWER_PROFILE_THRESHOLD_SENSITIVITY.csv").open(encoding="utf-8"))
    }
    assert "unmodified_trap_submission" in threshold_metrics
    assert "unmodified_trap_acceptance" not in threshold_metrics

    cross = list(csv.DictReader((tmp_path / "CROSS_STAGE_REVIEWER_VALIDATION.csv").open(encoding="utf-8")))
    adjusted = {
        row["mapping_id"]: float(row["spearman_rho"])
        for row in cross
        if row["analysis_cohort"] == "c1_eligible23_primary"
        and row["analysis_variant"] == "c1_task_centered_primary_diagnostic"
        and float(row["epsilon"]) == 0.02
    }
    assert adjusted == pytest.approx({
        "fixed_1_p1_trap_delta_to_c1_delta": 0.39582156973461324,
        "fixed_2_p1_blind_trust_to_c1_acceptable_unchanged": 0.5369433736705885,
        "fixed_3_p1_youden_to_c1_issue_geometry_edit_concordance": 0.4213309765899886,
        "fixed_4_p1_control_harm_to_c1_harmful_edit": 0.7325702215461277,
    })
