"""Synthetic tests for the Manhattan M6 probe summary validator.

The validator reads only probe summary JSON. These tests do not read real
Label Studio exports and do not validate UI behavior, formal g_t, routing,
worker-facing guidance, or P1/C1/C2/T1/V1 artifacts.
"""

from __future__ import annotations

import json

from tools.paper_a_manhattan.validate_manhattan_probe_summary import main, validate_summary


def _summary():
    return {
        "source_export": "export_label/does-not-need-to-exist.json",
        "probe_version": "manhattan_smoke_export_probe_v1",
        "n_tasks": 5,
        "n_annotations": 26,
        "n_keypoint_results": 236,
        "compatibility_status_counts": {"compatible": 24},
        "residual_enabled": True,
        "n_residual_valid": 24,
        "n_residual_excluded": 2,
        "residual_numeric_summary": {
            "x_spacing_cv": {"count": 24, "median": 0.2, "p90": 1.0, "max": 1.2}
        },
        "audit_eligibility_enabled": True,
        "n_audit_eligible": 22,
        "n_audit_ineligible": 4,
        "n_audit_residual_valid": 20,
        "n_audit_residual_excluded": 2,
        "audit_residual_numeric_summary": {
            "x_spacing_cv": {"count": 20, "median": 0.2, "p90": 1.0, "max": 1.2}
        },
        "suggestions_enabled": True,
        "n_suggestion_annotations": 20,
        "suggestion_type_counts": {
            "no_action": 10,
            "review_ceiling_alignment": 6,
            "review_spacing_irregularity": 6,
        },
    }


def test_valid_m5_like_summary_passes_with_event_count_warning():
    report = validate_summary(_summary(), summary_path="summary.json")

    assert report["validation_status"] == "warning"
    assert report["errors"] == []
    assert any("multiple suggestion events" in warning for warning in report["warnings"])
    assert report["probe_version"] == "manhattan_smoke_export_probe_v1"
    assert report["source_export"] == "export_label/does-not-need-to-exist.json"


def test_missing_required_field_fails():
    summary = _summary()
    summary.pop("n_tasks")

    report = validate_summary(summary, summary_path="summary.json")

    assert report["validation_status"] == "fail"
    assert "missing required field: n_tasks" in report["errors"]


def test_residual_numeric_invariant_broken_fails():
    summary = _summary()
    summary["n_residual_valid"] = 25
    summary["n_residual_excluded"] = 2

    report = validate_summary(summary, summary_path="summary.json")

    assert report["validation_status"] == "fail"
    assert "n_residual_valid + n_residual_excluded exceeds n_annotations" in report["errors"]


def test_audit_residual_numeric_invariant_broken_fails():
    summary = _summary()
    summary["n_audit_residual_valid"] = 21
    summary["n_audit_residual_excluded"] = 2

    report = validate_summary(summary, summary_path="summary.json")

    assert report["validation_status"] == "fail"
    assert (
        "n_audit_residual_valid + n_audit_residual_excluded exceeds n_audit_eligible"
        in report["errors"]
    )


def test_suggestion_annotations_greater_than_audit_residual_valid_fails():
    summary = _summary()
    summary["n_suggestion_annotations"] = 21

    report = validate_summary(summary, summary_path="summary.json")

    assert report["validation_status"] == "fail"
    assert "n_suggestion_annotations exceeds n_audit_residual_valid" in report["errors"]


def test_forbidden_payload_terms_in_keys_fail_and_values_warn():
    summary = _summary()
    summary["snap_coordinates"] = [1, 2]
    summary["audit_note"] = "contains worker tier language"

    report = validate_summary(summary, summary_path="summary.json")

    assert report["validation_status"] == "fail"
    assert any("forbidden payload term in key" in error for error in report["errors"])
    assert any("worker tier" in warning for warning in report["warnings"])


def test_source_export_not_string_warns_not_fail():
    summary = _summary()
    summary["source_export"] = {"path": "export_label/not-opened.json"}
    summary["suggestion_type_counts"] = {"no_action": 20}

    report = validate_summary(summary, summary_path="summary.json")

    assert report["validation_status"] == "warning"
    assert report["errors"] == []
    assert "source_export is present but is not a string" in report["warnings"]


def test_validator_does_not_read_real_export_path():
    summary = _summary()
    summary["source_export"] = "export_label/path-that-would-fail-if-opened.json"

    report = validate_summary(summary, summary_path="summary.json")

    assert report["source_export"] == "export_label/path-that-would-fail-if-opened.json"
    assert not any("source_export" in error for error in report["errors"])


def test_cli_prints_validation_report_to_stdout(tmp_path, capsys):
    input_path = tmp_path / "summary.json"
    input_path.write_text(json.dumps(_summary()), encoding="utf-8")

    assert main(["--input", str(input_path)]) == 0
    payload = json.loads(capsys.readouterr().out)

    assert payload["validation_status"] == "warning"
    assert payload["summary_path"] == str(input_path)


def test_cli_writes_validation_report_only_with_output(tmp_path, capsys):
    input_path = tmp_path / "summary.json"
    output_path = tmp_path / "validation.json"
    input_path.write_text(json.dumps(_summary()), encoding="utf-8")

    assert main(["--input", str(input_path), "--output", str(output_path)]) == 0

    payload = json.loads(output_path.read_text(encoding="utf-8"))
    assert payload["validation_status"] == "warning"
    assert capsys.readouterr().out == ""
