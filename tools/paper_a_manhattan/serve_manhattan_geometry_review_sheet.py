"""Serve a Manhattan geometry review sheet with local CSV save support.

This M15.x helper is expert-side / localhost-only. It serves one specified
HTML review sheet and writes only the specified manual review CSV sidecar. It
does not connect to Label Studio, does not write annotations, and does not
connect to routing, formal g_t, worker quality metrics, or P1/C1/C2/T1/V1
artifacts.
"""

from __future__ import annotations

import argparse
import csv
import json
import secrets
from html import escape
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Callable, Mapping
from urllib.parse import urlparse


KEY_FIELDS = ("task_id", "annotation_id")
MANUAL_FIELDS = ("plausible_candidate", "likely_issue", "reviewer_note")
REQUIRED_FIELDS = (*KEY_FIELDS, *MANUAL_FIELDS)
VALID_PLAUSIBLE = {"", "yes", "no", "unsure"}
VALID_ISSUES = {"", "annotation_geometry", "algorithm_overfit", "scope_disagreement", "unclear"}


def _row_key(row: Mapping[str, Any]) -> tuple[str, str]:
    return str(row.get("task_id", "")), str(row.get("annotation_id", ""))


def _validate_csv_schema(fieldnames: list[str] | None, path: Path) -> list[str]:
    if not fieldnames:
        raise ValueError(f"{path}: missing CSV header")
    missing = [field for field in REQUIRED_FIELDS if field not in fieldnames]
    if missing:
        raise ValueError(f"{path}: missing required columns: {', '.join(missing)}")
    return fieldnames


def read_manual_review_csv(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    if not path.exists():
        raise FileNotFoundError(f"{path}: manual review CSV does not exist")
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        fieldnames = _validate_csv_schema(reader.fieldnames, path)
        rows = [dict(row) for row in reader]
    seen: set[tuple[str, str]] = set()
    for row in rows:
        key = _row_key(row)
        if key in seen:
            raise ValueError(f"{path}: duplicate task_id/annotation_id key: {key[0]} / {key[1]}")
        seen.add(key)
    return fieldnames, rows


def public_manual_review_rows(path: Path) -> list[dict[str, str]]:
    _, rows = read_manual_review_csv(path)
    return [
        {
            "task_id": row.get("task_id", ""),
            "annotation_id": row.get("annotation_id", ""),
            "annotator_id": row.get("annotator_id", ""),
            "plausible_candidate": row.get("plausible_candidate", ""),
            "likely_issue": row.get("likely_issue", ""),
            "reviewer_note": row.get("reviewer_note", ""),
        }
        for row in rows
    ]


def _validate_manual_payload_row(row: Mapping[str, Any]) -> dict[str, str]:
    normalized = {field: str(row.get(field, "")) for field in (*KEY_FIELDS, *MANUAL_FIELDS)}
    if not normalized["task_id"] or not normalized["annotation_id"]:
        raise ValueError("manual review row missing task_id or annotation_id")
    if normalized["plausible_candidate"] not in VALID_PLAUSIBLE:
        raise ValueError(f"invalid plausible_candidate: {normalized['plausible_candidate']}")
    if normalized["likely_issue"] not in VALID_ISSUES:
        raise ValueError(f"invalid likely_issue: {normalized['likely_issue']}")
    return normalized


def merge_manual_review_csv(path: Path, payload_rows: list[Mapping[str, Any]]) -> int:
    fieldnames, existing_rows = read_manual_review_csv(path)
    by_key = {_row_key(row): row for row in existing_rows}
    updates = [_validate_manual_payload_row(row) for row in payload_rows]

    for update in updates:
        key = _row_key(update)
        if key not in by_key:
            raise ValueError(f"unknown task_id/annotation_id key: {key[0]} / {key[1]}")
        target = by_key[key]
        for field in MANUAL_FIELDS:
            target[field] = update[field]

    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(existing_rows)
    return len(updates)


def _server_injection(token: str) -> str:
    return f"""
<script>
(() => {{
  const REVIEW_SERVER_TOKEN = "{escape(token, quote=True)}";
  const SERVER_STATUS_READY = "Local CSV save enabled.";
  const SAVE_DEBOUNCE_MS = 700;

  function statusNode() {{
    return document.getElementById("review-save-status");
  }}

  function setStatus(message) {{
    const node = statusNode();
    if (node) {{
      node.textContent = message;
    }}
  }}

  function fieldValue(fieldset, suffix) {{
    const field = fieldset.querySelector(`[name$="_${{suffix}}"]`);
    return field ? field.value : "";
  }}

  function setFieldValue(fieldset, suffix, value) {{
    const field = fieldset.querySelector(`[name$="_${{suffix}}"]`);
    if (field) {{
      field.value = value || "";
    }}
  }}

  function collectServerRows() {{
    return Array.from(document.querySelectorAll(".manual-review")).map((fieldset) => ({{
      task_id: fieldValue(fieldset, "task_id"),
      annotation_id: fieldValue(fieldset, "annotation_id"),
      plausible_candidate: fieldValue(fieldset, "plausible_candidate"),
      likely_issue: fieldValue(fieldset, "likely_issue"),
      reviewer_note: fieldValue(fieldset, "reviewer_note"),
    }}));
  }}

  async function api(path, options = {{}}) {{
    const headers = Object.assign({{
      "X-Review-Token": REVIEW_SERVER_TOKEN,
    }}, options.headers || {{}});
    const response = await fetch(path, Object.assign({{}}, options, {{ headers }}));
    const body = await response.json();
    if (!response.ok) {{
      throw new Error(body.error || "request failed");
    }}
    return body;
  }}

  async function loadSavedCsv() {{
    const body = await api("/api/manual-review");
    const rowsByKey = new Map(body.rows.map((row) => [`${{row.task_id}}\\u0000${{row.annotation_id}}`, row]));
    document.querySelectorAll(".manual-review").forEach((fieldset) => {{
      const key = `${{fieldValue(fieldset, "task_id")}}\\u0000${{fieldValue(fieldset, "annotation_id")}}`;
      const row = rowsByKey.get(key);
      if (row) {{
        setFieldValue(fieldset, "plausible_candidate", row.plausible_candidate);
        setFieldValue(fieldset, "likely_issue", row.likely_issue);
        setFieldValue(fieldset, "reviewer_note", row.reviewer_note);
      }}
    }});
    setStatus(SERVER_STATUS_READY);
  }}

  async function saveCsv() {{
    setStatus("Saving CSV...");
    await api("/api/manual-review", {{
      method: "POST",
      headers: {{ "Content-Type": "application/json" }},
      body: JSON.stringify({{ rows: collectServerRows() }}),
    }});
    setStatus("Saved to CSV");
  }}

  function installControls() {{
    const actions = document.querySelector(".manual-save-actions");
    if (!actions || document.getElementById("save-review-csv")) {{
      return;
    }}
    const button = document.createElement("button");
    button.type = "button";
    button.id = "save-review-csv";
    button.textContent = "Save CSV";
    actions.insertBefore(button, actions.firstChild);
    button.addEventListener("click", () => saveCsv().catch((error) => setStatus(`Save failed: ${{error.message}}`)));
  }}

  function installAutosave() {{
    let timer = null;
    document.querySelectorAll(".manual-review select, .manual-review textarea").forEach((field) => {{
      field.addEventListener("input", () => {{
        setStatus("Unsaved changes");
        window.clearTimeout(timer);
        timer = window.setTimeout(() => {{
          saveCsv().catch((error) => setStatus(`Save failed: ${{error.message}}`));
        }}, SAVE_DEBOUNCE_MS);
      }});
      field.addEventListener("change", () => {{
        setStatus("Unsaved changes");
        window.clearTimeout(timer);
        timer = window.setTimeout(() => {{
          saveCsv().catch((error) => setStatus(`Save failed: ${{error.message}}`));
        }}, SAVE_DEBOUNCE_MS);
      }});
    }});
  }}

  document.addEventListener("DOMContentLoaded", () => {{
    installControls();
    loadSavedCsv().catch((error) => setStatus(`Save failed: ${{error.message}}`));
    installAutosave();
  }});
}})();
</script>
""".strip()


def inject_local_save_support(html: str, token: str) -> str:
    banner = (
        '<p class="localhost-save-note">'
        "Local CSV save is enabled by localhost review server. "
        "No external network submit; local CSV save only when served by localhost review server."
        "</p>"
    )
    injection = f"{banner}\n{_server_injection(token)}"
    if "</body>" in html:
        return html.replace("</body>", f"{injection}\n</body>", 1)
    return f"{html}\n{injection}"


def make_handler(html_path: Path, csv_path: Path, token: str) -> type[BaseHTTPRequestHandler]:
    class ReviewHandler(BaseHTTPRequestHandler):
        def log_message(self, format: str, *args: Any) -> None:
            return

        def _authorized(self) -> bool:
            return self.headers.get("X-Review-Token") == token

        def _send(self, status: HTTPStatus, body: bytes, content_type: str) -> None:
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def _send_json(self, status: HTTPStatus, payload: Mapping[str, Any]) -> None:
            self._send(status, json.dumps(payload, ensure_ascii=False).encode("utf-8"), "application/json; charset=utf-8")

        def _send_error_json(self, status: HTTPStatus, message: str) -> None:
            self._send_json(status, {"error": message})

        def do_GET(self) -> None:
            path = urlparse(self.path).path
            if path == "/":
                try:
                    html = html_path.read_text(encoding="utf-8")
                    body = inject_local_save_support(html, token).encode("utf-8")
                    self._send(HTTPStatus.OK, body, "text/html; charset=utf-8")
                except OSError as error:
                    self._send_error_json(HTTPStatus.INTERNAL_SERVER_ERROR, str(error))
                return
            if path == "/api/manual-review":
                if not self._authorized():
                    self._send_error_json(HTTPStatus.FORBIDDEN, "invalid or missing review token")
                    return
                try:
                    rows = public_manual_review_rows(csv_path)
                    self._send_json(HTTPStatus.OK, {"rows": rows, "count": len(rows)})
                except (OSError, ValueError) as error:
                    self._send_error_json(HTTPStatus.BAD_REQUEST, str(error))
                return
            self._send_error_json(HTTPStatus.NOT_FOUND, "not found")

        def do_POST(self) -> None:
            path = urlparse(self.path).path
            if path != "/api/manual-review":
                self._send_error_json(HTTPStatus.NOT_FOUND, "not found")
                return
            if not self._authorized():
                self._send_error_json(HTTPStatus.FORBIDDEN, "invalid or missing review token")
                return
            try:
                length = int(self.headers.get("Content-Length", "0"))
                payload = json.loads(self.rfile.read(length).decode("utf-8") or "{}")
                rows = payload.get("rows")
                if not isinstance(rows, list):
                    raise ValueError("payload must contain rows list")
                updated = merge_manual_review_csv(csv_path, rows)
                self._send_json(HTTPStatus.OK, {"status": "saved", "updated": updated})
            except (OSError, ValueError, json.JSONDecodeError) as error:
                self._send_error_json(HTTPStatus.BAD_REQUEST, str(error))

    return ReviewHandler


def build_server(
    html_path: Path,
    csv_path: Path,
    *,
    host: str = "127.0.0.1",
    port: int = 8765,
    token: str | None = None,
) -> ThreadingHTTPServer:
    token = token or secrets.token_urlsafe(24)
    handler = make_handler(html_path, csv_path, token)
    server = ThreadingHTTPServer((host, port), handler)
    server.review_token = token  # type: ignore[attr-defined]
    return server


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--html", required=True, type=Path, help="HTML review sheet to serve.")
    parser.add_argument("--manual-review-csv", required=True, type=Path, help="Manual review CSV to read and save.")
    parser.add_argument("--host", default="127.0.0.1", help="Bind host. Defaults to 127.0.0.1.")
    parser.add_argument("--port", default=8765, type=int, help="Bind port. Defaults to 8765.")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_arg_parser().parse_args(argv)
    if args.host != "127.0.0.1":
        raise ValueError("This review save service must bind to 127.0.0.1")
    read_manual_review_csv(args.manual_review_csv)
    if not args.html.exists():
        raise FileNotFoundError(f"{args.html}: HTML review sheet does not exist")

    server = build_server(args.html, args.manual_review_csv, host=args.host, port=args.port)
    host, port = server.server_address
    print(
        json.dumps(
            {
                "url": f"http://{host}:{port}/",
                "html": str(args.html),
                "manual_review_csv": str(args.manual_review_csv),
                "guardrails": "localhost-only; no annotation writeback; no routing; no formal g_t",
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        return 0
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
