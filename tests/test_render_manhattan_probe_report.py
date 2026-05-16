"""Synthetic tests for the Manhattan M3 probe report renderer.

The report renderer consumes probe summary JSON only. These tests do not read
real Label Studio exports and do not validate UI behavior, correctness, formal
g_t, routing behavior, worker-facing guidance, or P1/C1/C2/T1/V1 artifacts.
"""

from __future__ import annotations

import json

from tools.render_manhattan_probe_report import main, render_markdown_report


def _summary(include_suggestions=True):
    summary = {
        "source_export": "export_label/smoke.json",
        "probe_version": "manhattan_smoke_export_probe_v1",
        "legacy_keypoint_only": False,
        "meta_labels_trusted": True,
        "n_tasks": 5,
        "n_annotations": 26,
        "n_keypoint_results": 236,
        "n_results": 314,
        "parse_error_count": 0,
        "scope_alias_counts": {"normal": 22, "oos_geometry": 1, "oos_split_level": 3},
        "compatibility_status_counts": {
            "compatible": 24,
            "compatibility_failure_duplicate": 1,
            "compatibility_failure_odd_keypoint": 1,
        },
        "residual_enabled": True,
        "n_residual_valid": 24,
        "n_residual_excluded": 2,
        "residual_numeric_summary": {
            "x_spacing_cv": {"count": 24, "median": 0.21, "p90": 1.22, "max": 1.23},
            "ceiling_y_range": {"count": 24, "median": 28.0, "p90": 138.0, "max": 149.0},
        },
        "audit_eligibility_enabled": True,
        "n_audit_eligible": 22,
        "n_audit_ineligible": 4,
        "audit_ineligibility_counts": {"oos_geometry": 1, "oos_split_level": 3},
        "n_audit_residual_valid": 20,
        "n_audit_residual_excluded": 2,
        "audit_residual_exclusion_counts": {
            "compatibility_failure_duplicate": 1,
            "compatibility_failure_odd_keypoint": 1,
        },
        "audit_residual_numeric_summary": {
            "x_spacing_cv": {"count": 20, "median": 0.2, "p90": 1.1, "max": 1.2},
            "ceiling_y_range": {"count": 20, "median": 28.0, "p90": 44.0, "max": 142.0},
        },
        "audit_warnings": ["unknown_scope_alias:legacy_scope_text"],
        "candidate_task_examples": [
            {
                "issue": "compatibility_failure",
                "compatibility_status": "compatibility_failure_duplicate",
                "task_id": 2948,
                "annotation_id": 2626,
            }
        ],
    }
    if include_suggestions:
        summary.update(
            {
                "suggestions_enabled": True,
                "n_suggestion_annotations": 20,
                "suggestion_type_counts": {
                    "no_action": 10,
                    "review_ceiling_alignment": 6,
                    "review_spacing_irregularity": 6,
                },
                "suggestion_severity_counts": {"low": 10, "medium": 6, "high": 6},
                "suggestion_source_field_counts": {
                    "none": 10,
                    "ceiling_y_range": 6,
                    "x_spacing_cv": 6,
                },
            }
        )
    return summary


def test_render_report_contains_probe_residual_audit_and_suggestion_sections():
    report = render_markdown_report(_summary())

    assert "# Manhattan Smoke Probe Report" in report
    assert "`source_export`: export_label/smoke.json" in report
    assert "`n_tasks`: 5" in report
    assert "`n_annotations`: 26" in report
    assert "`n_keypoint_results`: 236" in report
    assert "`normal`: 22" in report
    assert "`compatible`: 24" in report
    assert "`n_residual_valid`: 24" in report
    assert "`n_audit_eligible`: 22" in report
    assert "`n_audit_residual_valid`: 20" in report
    assert "`review_ceiling_alignment`: 6" in report
    assert "`high`: 6" in report
    assert "unknown_scope_alias:legacy_scope_text" in report


def test_render_report_states_required_guardrails():
    report = render_markdown_report(_summary())

    assert "Compatibility failure is not correctness" in report
    assert "Residual values are preview geometry stability diagnostics" in report
    assert "not worker quality" in report
    assert "preview-only review prompts" in report
    assert "does not enter formal g_t" in report
    assert "does not enter routing" in report
    assert "not a P1/C1/C2/T1/V1 artifact" in report
    assert "not used in the current worker-facing experiment" in report


def test_render_report_handles_missing_suggestion_fields():
    report = render_markdown_report(_summary(include_suggestions=False))

    assert "## Suggestion Summary" in report
    assert "`suggestions_enabled`: null" in report
    assert "### Suggestion Type Counts" in report
    assert "- none" in report


def test_render_report_explains_multiple_suggestion_events_per_annotation():
    report = render_markdown_report(_summary())

    assert "suggestion events can exceed suggestion annotations" in report
    assert "one annotation can trigger multiple preview-only review prompts" in report


def test_render_report_avoids_disallowed_payload_terms():
    report = render_markdown_report(_summary()).lower()

    assert "snap" not in report
    assert "adjustment" not in report
    assert "writeback" not in report
    assert "corrected annotation" not in report
    assert "worker tier" not in report
    assert "routing decision" not in report


def test_cli_prints_report_to_stdout(tmp_path, capsys):
    input_path = tmp_path / "summary.json"
    input_path.write_text(json.dumps(_summary()), encoding="utf-8")

    assert main(["--input", str(input_path)]) == 0
    stdout = capsys.readouterr().out

    assert "# Manhattan Smoke Probe Report" in stdout
    assert "`source_export`: export_label/smoke.json" in stdout


def test_cli_writes_report_only_when_output_is_provided(tmp_path, capsys):
    input_path = tmp_path / "summary.json"
    output_path = tmp_path / "report.md"
    input_path.write_text(json.dumps(_summary()), encoding="utf-8")

    assert main(["--input", str(input_path), "--output", str(output_path)]) == 0

    assert output_path.exists()
    assert "# Manhattan Smoke Probe Report" in output_path.read_text(encoding="utf-8")
    assert capsys.readouterr().out == ""
