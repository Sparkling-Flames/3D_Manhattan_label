import argparse
import json
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from statistics import median
from typing import Any


M8_EXPECTED_EVENTS = {
    "panel_loaded",
    "heartbeat",
    "visibility_hidden",
    "pagehide",
    "panel_unloaded",
}

M8_REQUIRED_FIELDS = [
    "log_context",
    "tool_stage",
    "script_variant",
    "is_sandbox",
    "sandbox_project",
    "exclude_from_primary_active_time",
    "exclude_from_thesis_evidence",
    "not_worker_facing",
    "not_p1_c1_c2_t1_v1_artifact",
    "manhattan_panel_version",
    "event",
    "session_id",
    "server_received_at",
]

EXCLUSION_TAGS = [
    "exclude_from_primary_active_time",
    "exclude_from_thesis_evidence",
    "not_worker_facing",
    "not_p1_c1_c2_t1_v1_artifact",
]

UNKNOWN_TOKENS = {"", "unknown", "none", "null", "nan", "na"}
PARSE_ERROR_FAIL_RATE = 0.10


def _normalize(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _is_unknown(value: Any) -> bool:
    return _normalize(value).lower() in UNKNOWN_TOKENS


def _is_m8_sandbox_event(record: dict[str, Any]) -> bool:
    version = _normalize(record.get("manhattan_panel_version")).lower()
    return (
        record.get("log_context") == "manhattan_ls_sandbox"
        or record.get("tool_stage") == "M8"
        or record.get("is_sandbox") is True
        or "m8" in version
    )


def _parse_timestamp(value: Any) -> datetime | None:
    text = _normalize(value)
    if not text:
        return None
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        pass
    try:
        number = float(text)
    except ValueError:
        return None
    if number > 1_000_000_000_000:
        number = number / 1000.0
    try:
        return datetime.fromtimestamp(number)
    except (OverflowError, OSError, ValueError):
        return None


def _safe_rate(numerator: int, denominator: int) -> float:
    if denominator <= 0:
        return 0.0
    return round(float(numerator) / float(denominator), 6)


def _is_negation_guard(key_path: str, value: Any) -> bool:
    key = key_path.lower()
    text = _normalize(value).lower()
    return (
        key.startswith(("not_", "no_", "exclude_"))
        or "_not_" in key
        or text.startswith(("not ", "no "))
        or "not " in text
        or "no " in text
    )


def _scan_for_forbidden_payload(record: Any, path: str = "") -> list[str]:
    hits: list[str] = []
    if isinstance(record, dict):
        for key, value in record.items():
            child_path = f"{path}.{key}" if path else str(key)
            lowered_key = str(key).lower()
            if any(
                token in lowered_key
                for token in [
                    "routing",
                    "worker_tier",
                    "worker tier",
                    "formal_g_t",
                    "formal g_t",
                    "p1_artifact",
                    "c1_artifact",
                    "c2_artifact",
                    "t1_artifact",
                    "v1_artifact",
                    "p1/c1/c2/t1/v1",
                ]
            ) and not _is_negation_guard(child_path, value):
                hits.append(child_path)
            hits.extend(_scan_for_forbidden_payload(value, child_path))
    elif isinstance(record, list):
        for index, value in enumerate(record):
            hits.extend(_scan_for_forbidden_payload(value, f"{path}[{index}]"))
    elif isinstance(record, str):
        lowered_value = record.lower()
        if any(
            token in lowered_value
            for token in [
                "routing decision",
                "worker tier",
                "formal g_t",
                "formal_g_t",
                "p1 artifact",
                "c1 artifact",
                "c2 artifact",
                "t1 artifact",
                "v1 artifact",
                "p1/c1/c2/t1/v1 artifact",
            ]
        ) and not _is_negation_guard(path, record):
            hits.append(path or "<value>")
    return hits


def _heartbeat_interval_summary(events: list[dict[str, Any]]) -> tuple[dict[str, Any], list[str]]:
    warnings: list[str] = []
    intervals: list[float] = []
    by_session: dict[str, list[datetime]] = defaultdict(list)
    for record in events:
        if record.get("event") != "heartbeat":
            continue
        session_id = _normalize(record.get("session_id")) or "unknown"
        timestamp = _parse_timestamp(record.get("server_received_at")) or _parse_timestamp(record.get("timestamp"))
        if timestamp is None:
            warnings.append(f"heartbeat_missing_timestamp session_id={session_id}")
            continue
        by_session[session_id].append(timestamp)

    for timestamps in by_session.values():
        timestamps.sort()
        for previous, current in zip(timestamps, timestamps[1:]):
            intervals.append((current - previous).total_seconds())

    summary: dict[str, Any] = {
        "count": len(intervals),
        "median": None,
        "min": None,
        "max": None,
    }
    if intervals:
        summary.update(
            {
                "median": round(float(median(intervals)), 3),
                "min": round(float(min(intervals)), 3),
                "max": round(float(max(intervals)), 3),
            }
        )
        if any(interval < 10 or interval > 25 for interval in intervals):
            warnings.append("heartbeat_interval_deviates_from_15s")
    return summary, warnings


def audit_m8_sandbox_active_log(input_path: str | Path) -> dict[str, Any]:
    path = Path(input_path)
    if not path.exists():
        raise FileNotFoundError(f"Active log file not found: {path}")
    if not path.is_file():
        raise IsADirectoryError(f"Expected a JSONL file, got directory: {path}")

    records: list[dict[str, Any]] = []
    errors: list[str] = []
    warnings: list[str] = []
    parse_errors = 0
    total_lines = 0

    with path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            total_lines += 1
            try:
                parsed = json.loads(line)
            except json.JSONDecodeError as exc:
                parse_errors += 1
                warnings.append(f"parse_error line={line_number}: {exc.msg}")
                continue
            if not isinstance(parsed, dict):
                parse_errors += 1
                warnings.append(f"parse_error line={line_number}: non_object_json")
                continue
            if _is_m8_sandbox_event(parsed):
                records.append(parsed)

    event_counts = Counter(_normalize(record.get("event")) or "unknown" for record in records)
    session_counts = Counter(_normalize(record.get("session_id")) or "unknown" for record in records)
    task_counts = Counter(_normalize(record.get("task_id")) or "unknown" for record in records)
    project_counts = Counter(_normalize(record.get("project_id")) or "unknown" for record in records)

    missing_required = Counter()
    exclusion_tag_failures = Counter()
    unknown_identity_counts = Counter()

    for index, record in enumerate(records, start=1):
        for field in M8_REQUIRED_FIELDS:
            if field not in record or _is_unknown(record.get(field)):
                missing_required[field] += 1
        for tag in EXCLUSION_TAGS:
            if record.get(tag) is not True:
                exclusion_tag_failures[tag] += 1
                errors.append(f"exclusion_tag_not_true record={index} field={tag}")

        if _is_unknown(record.get("task_id")):
            unknown_identity_counts["task_id"] += 1
        if _is_unknown(record.get("project_id")):
            unknown_identity_counts["project_id"] += 1
        if _is_unknown(record.get("annotator_id")):
            unknown_identity_counts["annotator_id"] += 1
        if all(_is_unknown(record.get(field)) for field in ["task_id", "project_id", "annotator_id"]):
            warnings.append(f"all_identity_fields_unknown record={index}")

        event_name = _normalize(record.get("event"))
        if event_name and event_name not in M8_EXPECTED_EVENTS:
            warnings.append(f"unexpected_event record={index} event={event_name}")
        if "server_received_at" not in record or _is_unknown(record.get("server_received_at")):
            warnings.append(f"missing_server_received_at record={index}")
        if "session_id" not in record or _is_unknown(record.get("session_id")):
            warnings.append(f"missing_session_id record={index}")

        forbidden_hits = _scan_for_forbidden_payload(record)
        for hit in forbidden_hits:
            errors.append(f"forbidden_payload_field record={index} path={hit}")

    if not records:
        warnings.append("no_m8_sandbox_events")
    if records and event_counts.get("heartbeat", 0) == 0:
        warnings.append("heartbeat_missing")

    parse_error_rate = _safe_rate(parse_errors, total_lines)
    if parse_errors and parse_error_rate > PARSE_ERROR_FAIL_RATE:
        errors.append(f"parse_error_rate_too_high rate={parse_error_rate}")

    heartbeat_summary, heartbeat_warnings = _heartbeat_interval_summary(records)
    warnings.extend(heartbeat_warnings)

    audit_status = "pass"
    if errors:
        audit_status = "fail"
    elif warnings:
        audit_status = "warning"

    return {
        "audit_status": audit_status,
        "input_path": str(path),
        "n_total_lines": total_lines,
        "n_parse_errors": parse_errors,
        "n_m8_sandbox_events": len(records),
        "event_counts": dict(sorted(event_counts.items())),
        "session_counts": dict(sorted(session_counts.items())),
        "task_counts": dict(sorted(task_counts.items())),
        "project_counts": dict(sorted(project_counts.items())),
        "missing_required_field_counts": dict(sorted(missing_required.items())),
        "exclusion_tag_fail_counts": dict(sorted(exclusion_tag_failures.items())),
        "heartbeat_interval_summary": heartbeat_summary,
        "unknown_identity_counts": dict(sorted(unknown_identity_counts.items())),
        "notes": [
            "M8 sandbox telemetry is excluded from primary active_time.",
            "This audit does not validate RQ1 primary estimand.",
            "This audit does not modify logs.",
            "This audit does not read or modify Label Studio export.",
        ],
        "errors": errors,
        "warnings": warnings,
    }


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Audit M8 sandbox active-log telemetry isolation in a JSONL active log.",
    )
    parser.add_argument("--input", required=True, type=Path, help="Path to active log JSONL file")
    parser.add_argument("--output", default=None, type=Path, help="Optional JSON summary output path")
    args = parser.parse_args(argv)

    summary = audit_m8_sandbox_active_log(args.input)
    if args.output is not None:
        write_json(args.output, summary)
    else:
        print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0 if summary["audit_status"] != "fail" else 1


if __name__ == "__main__":
    raise SystemExit(main())
