"""Synthetic tests for the Manhattan M4 contact sheet renderer.

The renderer consumes probe summary JSON only. These tests do not read real
Label Studio exports and do not validate UI, Label Studio integration,
correctness, formal g_t, routing, worker-facing guidance, or P1/C1/C2/T1/V1
artifacts.
"""

from __future__ import annotations

import json

from tools.render_manhattan_contact_sheet import main, render_html_contact_sheet


def _summary(include_examples=True):
    summary = {
        "source_export": "export_label/smoke.json",
        "probe_version": "manhattan_smoke_export_probe_v1",
        "n_tasks": 5,
        "n_annotations": 26,
        "n_keypoint_results": 236,
        "n_residual_valid": 24,
        "n_residual_excluded": 2,
        "n_audit_eligible": 22,
        "n_audit_ineligible": 4,
        "n_audit_residual_valid": 20,
        "n_audit_residual_excluded": 2,
        "n_suggestion_annotations": 20,
        "scope_alias_counts": {"normal": 22, "oos_geometry": 1, "oos_split_level": 3},
        "compatibility_status_counts": {
            "compatible": 24,
            "compatibility_failure_duplicate": 1,
            "compatibility_failure_odd_keypoint": 1,
        },
        "audit_residual_exclusion_counts": {
            "compatibility_failure_duplicate": 1,
            "compatibility_failure_odd_keypoint": 1,
        },
        "suggestion_type_counts": {
            "no_action": 10,
            "review_ceiling_alignment": 6,
            "review_spacing_irregularity": 6,
        },
        "audit_warnings": ["unknown_scope_alias:legacy_scope_text"],
    }
    summary["candidate_task_examples"] = (
        [
            {
                "task_id": 2948,
                "annotation_id": 2626,
                "issue": "compatibility_failure",
                "compatibility_status": "compatibility_failure_duplicate",
                "completed_by": 11,
            }
        ]
        if include_examples
        else []
    )
    return summary


def test_render_contact_sheet_contains_required_sections():
    html = render_html_contact_sheet(_summary())

    assert "<!doctype html>" in html
    assert "Manhattan Probe Contact Sheet" in html
    assert "export_label/smoke.json" in html
    assert "Summary Counts" in html
    assert "Compatibility Failures" in html
    assert "Audit Residual Exclusion Counts" in html
    assert "Suggestion Type Counts" in html
    assert "Candidate Task Examples" in html
    assert "Audit Warnings" in html
    assert "compatibility_failure_duplicate" in html
    assert "review_ceiling_alignment" in html


def test_render_contact_sheet_contains_guardrails():
    html = render_html_contact_sheet(_summary())

    assert "Compatibility failure is not correctness" in html
    assert "Residual is not worker quality" in html
    assert "Suggestion is a preview-only review prompt" in html
    assert "No formal g_t" in html
    assert "No routing" in html
    assert "Not a P1/C1/C2/T1/V1 artifact" in html
    assert "Not current worker-facing experiment" in html


def test_render_contact_sheet_handles_missing_candidate_examples():
    html = render_html_contact_sheet(_summary(include_examples=False))

    assert "No candidate examples in summary" in html
    assert "Manhattan Probe Contact Sheet" in html


def test_render_contact_sheet_explains_multiple_suggestion_events():
    html = render_html_contact_sheet(_summary())

    assert "Suggestion events can exceed suggestion annotations" in html
    assert "one annotation can trigger multiple preview-only review prompts" in html


def test_render_contact_sheet_avoids_disallowed_payload_terms():
    html = render_html_contact_sheet(_summary()).lower()

    assert "snap" not in html
    assert "adjustment" not in html
    assert "writeback" not in html
    assert "corrected annotation" not in html
    assert "worker tier" not in html
    assert "routing decision" not in html


def test_cli_prints_html_to_stdout(tmp_path, capsys):
    input_path = tmp_path / "summary.json"
    input_path.write_text(json.dumps(_summary()), encoding="utf-8")

    assert main(["--input", str(input_path)]) == 0
    stdout = capsys.readouterr().out

    assert "<!doctype html>" in stdout
    assert "Manhattan Probe Contact Sheet" in stdout


def test_cli_writes_html_only_with_explicit_output(tmp_path, capsys):
    input_path = tmp_path / "summary.json"
    output_path = tmp_path / "contact_sheet.html"
    input_path.write_text(json.dumps(_summary()), encoding="utf-8")

    assert main(["--input", str(input_path), "--output", str(output_path)]) == 0

    assert output_path.exists()
    assert "Manhattan Probe Contact Sheet" in output_path.read_text(encoding="utf-8")
    assert capsys.readouterr().out == ""
