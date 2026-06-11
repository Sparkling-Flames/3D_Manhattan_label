import json
from pathlib import Path

from tools.paper_a_manhattan.manhattan_assist_review_harness import (
    HEIGHT_REPROJECT_ROW_SCHEMA_VERSION,
)
from tools.paper_a_manhattan.run_height_reproject_applicability_smoke import (
    main,
    run_smoke,
)


FIXTURE_PATH = Path("tests/fixtures/paper_a_manhattan/height_reproject_applicability_pack_v1.json")
FORBIDDEN_FIELDS = {"candidate_pairs", "annotation", "writeback", "apply"}


def _reason_tokens(row):
    reasons = list(row.get("height_reproject_blocking_reasons", []))
    reasons.extend(row.get("height_reproject_reasons", []))
    return reasons


def _fixture_records():
    return json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))


def test_smoke_cli_reads_fixture_and_generates_rows_and_summary(tmp_path):
    output_path = tmp_path / "height_smoke.json"

    exit_code = main([
        "--input",
        str(FIXTURE_PATH),
        "--output",
        str(output_path),
        "--pretty",
    ])

    assert exit_code == 0
    payload = json.loads(output_path.read_text(encoding="utf-8"))
    assert set(payload) == {"rows", "summary"}
    assert len(payload["rows"]) == len(_fixture_records())
    assert payload["summary"]["n_records"] == len(_fixture_records())


def test_fixture_cases_match_expected_status_and_reason():
    records = _fixture_records()
    payload = run_smoke(FIXTURE_PATH)
    rows_by_case = {row["task_id"]: row for row in payload["rows"]}

    for record in records:
        row = rows_by_case[record["task_id"]]
        assert row["height_reproject_status"] == record["expected_height_reproject_status"]
        assert record["expected_reason_contains"] in _reason_tokens(row)


def test_smoke_output_has_no_candidate_or_writeback_fields():
    payload = run_smoke(FIXTURE_PATH)

    for row in payload["rows"]:
        assert row["candidate_returned"] is False
        assert row["candidate_retained"] is False
        assert FORBIDDEN_FIELDS.isdisjoint(row)


def test_smoke_summary_counts_match_fixture_expectations():
    payload = run_smoke(FIXTURE_PATH)
    summary = payload["summary"]

    assert summary["n_records"] == 5
    assert summary["n_height_reproject_applicable"] == 1
    assert summary["n_height_reproject_suppressed"] == 2
    assert summary["n_height_reproject_review_only"] == 2
    assert summary["n_height_reproject_blocked"] == 4
    assert summary["height_reproject_applicable_rate"] == 0.2
    assert summary["height_reproject_suppress_rate"] == 0.4
    assert summary["height_reproject_review_only_rate"] == 0.4
    assert summary["n_not_evaluated_no_candidate"] == 5
    assert summary["n_missing_manual_review"] == 5


def test_height_reproject_row_schema_version_is_present():
    payload = run_smoke(FIXTURE_PATH)

    for row in payload["rows"]:
        assert row["height_reproject_row_schema_version"] == HEIGHT_REPROJECT_ROW_SCHEMA_VERSION


def test_smoke_payload_is_json_serializable():
    payload = run_smoke(FIXTURE_PATH)

    json.dumps(payload)
