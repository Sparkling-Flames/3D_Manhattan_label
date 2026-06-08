import csv
from pathlib import Path

from tools.paper_b import validate_b0_relabel_audit as validator

ROOT = Path(__file__).resolve().parents[1]


FIELDNAMES = [
    "task_id",
    "image_id",
    "scene_id",
    "source_group",
    "dedup_primary",
    "hohonet_crossdoor_score",
    "bilayout_crossdoor_score",
    "overextend_reduced",
    "overparse_reduced",
    "bilayout_undercoverage",
    "bilayout_new_error",
    "both_wrong",
    "oos_suspect",
    "open_boundary_ambiguity",
    "expert_verdict",
    "usable_for_B1",
    "audit_notes",
]


def write_csv(path, rows, fieldnames=FIELDNAMES):
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def base_row(**overrides):
    row = {
        "task_id": "1",
        "image_id": "img",
        "scene_id": "scene",
        "source_group": "hard_prediction_failure",
        "dedup_primary": "true",
        "hohonet_crossdoor_score": "1",
        "bilayout_crossdoor_score": "0",
        "overextend_reduced": "false",
        "overparse_reduced": "false",
        "bilayout_undercoverage": "false",
        "bilayout_new_error": "false",
        "both_wrong": "false",
        "oos_suspect": "false",
        "open_boundary_ambiguity": "false",
        "expert_verdict": "accept_bilayout_enclosed",
        "usable_for_B1": "true",
        "audit_notes": "",
    }
    row.update(overrides)
    return row


def test_valid_csv_accepts_new_reject_verdict(tmp_path):
    path = tmp_path / "audit.csv"
    write_csv(
        path,
        [
            base_row(
                expert_verdict="reject_model_error_needs_manual_fix",
                usable_for_B1="false",
            )
        ],
    )

    result = validator.validate_csv(path)

    assert result.errors == []
    assert result.total_rows == 1
    assert result.dedup_primary_rows == 1
    assert result.reviewed_primary_rows == 1
    assert result.rows_by_expert_verdict["reject_model_error_needs_manual_fix"] == 1


def test_invalid_vocabulary_is_error(tmp_path):
    path = tmp_path / "audit.csv"
    write_csv(path, [base_row(source_group="bad_group")])

    result = validator.validate_csv(path)

    assert result.errors
    assert "invalid source_group" in result.errors[0]


def test_logical_contamination_is_warning_not_error(tmp_path):
    path = tmp_path / "audit.csv"
    write_csv(
        path,
        [
            base_row(
                expert_verdict="reject_model_error_needs_manual_fix",
                usable_for_B1="true",
            )
        ],
    )

    result = validator.validate_csv(path)

    assert result.errors == []
    assert result.warnings
    assert "should not have usable_for_B1=true" in result.warnings[0]


def test_moderate_minor_fix_note_warns(tmp_path):
    path = tmp_path / "audit.csv"
    write_csv(
        path,
        [
            base_row(
                expert_verdict="accept_with_minor_fix",
                usable_for_B1="true",
                audit_notes="needs moderate redraw",
            )
        ],
    )

    result = validator.validate_csv(path)

    assert result.errors == []
    assert any("moderate/major relabel" in warning for warning in result.warnings)


def test_report_file_is_written(tmp_path):
    path = tmp_path / "audit.csv"
    report = tmp_path / "report.md"
    write_csv(path, [base_row()])

    exit_code = validator.main(["--input", str(path), "--report-md", str(report)])

    assert exit_code == 0
    text = report.read_text(encoding="utf-8")
    assert "B0 Partial Validation Report" in text
    assert "total_rows: 1" in text
