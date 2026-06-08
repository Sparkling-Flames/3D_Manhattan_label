"""Tests for the localhost-only Manhattan geometry review save service.

These tests use temporary HTML/CSV files only. They do not read or modify
export_label, Label Studio UI, annotations, routing, formal g_t, or
P1/C1/C2/T1/V1 artifacts.
"""

from __future__ import annotations

import csv
import json
import threading
import urllib.error
import urllib.request
from pathlib import Path

import pytest

from tools.paper_a_manhattan.serve_manhattan_geometry_review_sheet import (
    build_server,
    merge_manual_review_csv,
    read_manual_review_csv,
)


def _html(path: Path) -> Path:
    path.write_text(
        """<!doctype html>
<html>
<body>
  <section class="manual-save-panel">
    <div class="manual-save-actions">
      <button type="button" id="export-review-csv">Export CSV</button>
      <span id="review-save-status"></span>
    </div>
  </section>
  <fieldset class="manual-review">
    <select name="row_1_plausible_candidate"></select>
    <select name="row_1_likely_issue"></select>
    <textarea name="row_1_reviewer_note"></textarea>
    <input type="hidden" name="row_1_task_id" value="2948">
    <input type="hidden" name="row_1_annotation_id" value="2614">
  </fieldset>
</body>
</html>
""",
        encoding="utf-8",
    )
    return path


def _csv(path: Path) -> Path:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "task_id",
                "annotation_id",
                "annotator_id",
                "scope_vote",
                "problem_reason",
                "max_abs_delta",
                "plausible_candidate",
                "likely_issue",
                "reviewer_note",
            ],
        )
        writer.writeheader()
        writer.writerow(
            {
                "task_id": "2948",
                "annotation_id": "2614",
                "annotator_id": "9",
                "scope_vote": "normal",
                "problem_reason": "compatibility_failure_odd_keypoint",
                "max_abs_delta": "0.25",
                "plausible_candidate": "no",
                "likely_issue": "annotation_geometry",
                "reviewer_note": "existing note",
            }
        )
    return path


class _RunningServer:
    def __init__(self, html_path: Path, csv_path: Path, token: str = "test-token") -> None:
        self.server = build_server(html_path, csv_path, port=0, token=token)
        self.token = token
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)

    def __enter__(self) -> "_RunningServer":
        self.thread.start()
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=5)

    @property
    def base_url(self) -> str:
        host, port = self.server.server_address
        return f"http://{host}:{port}"


def _request(url: str, *, token: str | None = None, data: dict | None = None) -> tuple[int, str]:
    headers = {}
    body = None
    if token is not None:
        headers["X-Review-Token"] = token
    if data is not None:
        body = json.dumps(data).encode("utf-8")
        headers["Content-Type"] = "application/json"
    request = urllib.request.Request(url, data=body, headers=headers)
    try:
        with urllib.request.urlopen(request, timeout=5) as response:
            return response.status, response.read().decode("utf-8")
    except urllib.error.HTTPError as error:
        return error.code, error.read().decode("utf-8")


def test_get_root_returns_html_with_local_save_controls(tmp_path):
    html_path = _html(tmp_path / "review.html")
    csv_path = _csv(tmp_path / "manual.csv")

    with _RunningServer(html_path, csv_path) as running:
        status, body = _request(f"{running.base_url}/")

    assert status == 200
    assert "Save CSV" in body
    assert "Local CSV save is enabled by localhost review server" in body
    assert "No external network submit" in body
    assert "fetch(path" in body
    assert "test-token" in body


def test_get_manual_review_returns_existing_csv_rows(tmp_path):
    html_path = _html(tmp_path / "review.html")
    csv_path = _csv(tmp_path / "manual.csv")

    with _RunningServer(html_path, csv_path) as running:
        status, body = _request(f"{running.base_url}/api/manual-review", token=running.token)

    payload = json.loads(body)
    assert status == 200
    assert payload["count"] == 1
    assert payload["rows"][0]["task_id"] == "2948"
    assert payload["rows"][0]["plausible_candidate"] == "no"
    assert payload["rows"][0]["reviewer_note"] == "existing note"


def test_post_manual_review_updates_manual_fields_and_preserves_metadata(tmp_path):
    html_path = _html(tmp_path / "review.html")
    csv_path = _csv(tmp_path / "manual.csv")

    with _RunningServer(html_path, csv_path) as running:
        status, body = _request(
            f"{running.base_url}/api/manual-review",
            token=running.token,
            data={
                "rows": [
                    {
                        "task_id": "2948",
                        "annotation_id": "2614",
                        "plausible_candidate": "yes",
                        "likely_issue": "unclear",
                        "reviewer_note": "updated note",
                    }
                ]
            },
        )

    assert status == 200
    assert json.loads(body)["updated"] == 1
    with csv_path.open(encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    assert rows[0]["annotator_id"] == "9"
    assert rows[0]["scope_vote"] == "normal"
    assert rows[0]["problem_reason"] == "compatibility_failure_odd_keypoint"
    assert rows[0]["plausible_candidate"] == "yes"
    assert rows[0]["likely_issue"] == "unclear"
    assert rows[0]["reviewer_note"] == "updated note"


def test_token_missing_or_wrong_is_rejected(tmp_path):
    html_path = _html(tmp_path / "review.html")
    csv_path = _csv(tmp_path / "manual.csv")

    with _RunningServer(html_path, csv_path) as running:
        missing_status, missing_body = _request(f"{running.base_url}/api/manual-review")
        wrong_status, wrong_body = _request(f"{running.base_url}/api/manual-review", token="wrong")

    assert missing_status == 403
    assert wrong_status == 403
    assert "invalid or missing review token" in missing_body
    assert "invalid or missing review token" in wrong_body


def test_missing_csv_schema_fails_clearly(tmp_path):
    bad_csv = tmp_path / "bad.csv"
    bad_csv.write_text("task_id,annotation_id,plausible_candidate\n2948,2614,yes\n", encoding="utf-8")

    with pytest.raises(ValueError, match="missing required columns"):
        read_manual_review_csv(bad_csv)


def test_invalid_manual_values_fail_clearly(tmp_path):
    csv_path = _csv(tmp_path / "manual.csv")

    with pytest.raises(ValueError, match="invalid plausible_candidate"):
        merge_manual_review_csv(
            csv_path,
            [
                {
                    "task_id": "2948",
                    "annotation_id": "2614",
                    "plausible_candidate": "maybe",
                    "likely_issue": "unclear",
                    "reviewer_note": "",
                }
            ],
        )


def test_unknown_row_key_is_rejected(tmp_path):
    csv_path = _csv(tmp_path / "manual.csv")

    with pytest.raises(ValueError, match="unknown task_id/annotation_id key"):
        merge_manual_review_csv(
            csv_path,
            [
                {
                    "task_id": "9999",
                    "annotation_id": "2614",
                    "plausible_candidate": "yes",
                    "likely_issue": "unclear",
                    "reviewer_note": "",
                }
            ],
        )
