import argparse
import csv
import json
from collections import defaultdict
from pathlib import Path
from typing import Any

from tools.active_log_utils import resolve_active_log_files


UNKNOWN_TOKENS = {"", "unknown", "none", "null", "nan", "na"}


def _normalize_scalar(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _is_unknown(value: Any) -> bool:
    return _normalize_scalar(value).lower() in UNKNOWN_TOKENS


def _safe_rate(numerator: int, denominator: int) -> float:
    if denominator <= 0:
        return 0.0
    return float(numerator) / float(denominator)


def audit_active_logs(active_log_path: str | Path) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    resolved_dir, files = resolve_active_log_files(active_log_path)
    path = Path(active_log_path)
    if resolved_dir is None and not path.exists():
        raise FileNotFoundError(f"Active log path not found: {path}")

    summary: dict[str, Any] = {
        "requested_path": str(path),
        "selected_log_root": str(resolved_dir) if resolved_dir else "",
        "selected_file_count": len(files),
        "selected_file_names": [file.name for file in files],
        "blank_line_count": 0,
        "nonempty_line_count": 0,
        "parsed_event_count": 0,
        "parse_error_count": 0,
        "unknown_task_count": 0,
        "unknown_annotator_count": 0,
        "unknown_project_count": 0,
        "unknown_session_count": 0,
        "missing_script_version_count": 0,
    }

    per_file_rows: list[dict[str, Any]] = []
    valid_pairs_seen: set[tuple[str, str]] = set()
    pair_sessions: dict[tuple[str, str], set[str]] = defaultdict(set)

    for file_path in files:
        file_stats: dict[str, Any] = {
            "file_name": file_path.name,
            "blank_line_count": 0,
            "nonempty_line_count": 0,
            "parsed_event_count": 0,
            "parse_error_count": 0,
            "unknown_task_count": 0,
            "unknown_annotator_count": 0,
            "unknown_project_count": 0,
            "unknown_session_count": 0,
            "missing_script_version_count": 0,
        }
        file_valid_pairs: set[tuple[str, str]] = set()
        file_pair_sessions: dict[tuple[str, str], set[str]] = defaultdict(set)

        with file_path.open("r", encoding="utf-8") as handle:
            for line in handle:
                if not line.strip():
                    summary["blank_line_count"] += 1
                    file_stats["blank_line_count"] += 1
                    continue

                summary["nonempty_line_count"] += 1
                file_stats["nonempty_line_count"] += 1

                try:
                    data = json.loads(line)
                except json.JSONDecodeError:
                    summary["parse_error_count"] += 1
                    file_stats["parse_error_count"] += 1
                    continue

                if not isinstance(data, dict):
                    summary["parse_error_count"] += 1
                    file_stats["parse_error_count"] += 1
                    continue

                summary["parsed_event_count"] += 1
                file_stats["parsed_event_count"] += 1

                task_id = _normalize_scalar(data.get("task_id"))
                annotator_id = _normalize_scalar(data.get("annotator_id"))
                project_id = _normalize_scalar(data.get("project_id"))
                session_id = _normalize_scalar(data.get("session_id"))
                script_version = _normalize_scalar(data.get("script_version"))

                if _is_unknown(task_id):
                    summary["unknown_task_count"] += 1
                    file_stats["unknown_task_count"] += 1
                if _is_unknown(annotator_id):
                    summary["unknown_annotator_count"] += 1
                    file_stats["unknown_annotator_count"] += 1
                if _is_unknown(project_id):
                    summary["unknown_project_count"] += 1
                    file_stats["unknown_project_count"] += 1
                if _is_unknown(session_id):
                    summary["unknown_session_count"] += 1
                    file_stats["unknown_session_count"] += 1
                if _is_unknown(script_version):
                    summary["missing_script_version_count"] += 1
                    file_stats["missing_script_version_count"] += 1

                if not _is_unknown(task_id) and not _is_unknown(annotator_id):
                    pair = (task_id, annotator_id)
                    valid_pairs_seen.add(pair)
                    file_valid_pairs.add(pair)
                    if not _is_unknown(session_id):
                        pair_sessions[pair].add(session_id)
                        file_pair_sessions[pair].add(session_id)

        file_stats["valid_task_annotator_pair_count"] = len(file_valid_pairs)
        file_stats["multi_session_pair_count"] = sum(1 for sessions in file_pair_sessions.values() if len(sessions) > 1)
        file_stats["multi_session_pair_rate"] = round(
            _safe_rate(file_stats["multi_session_pair_count"], file_stats["valid_task_annotator_pair_count"]),
            6,
        )
        file_stats["parse_error_rate"] = round(
            _safe_rate(file_stats["parse_error_count"], file_stats["nonempty_line_count"]),
            6,
        )
        file_stats["missing_script_version_rate"] = round(
            _safe_rate(file_stats["missing_script_version_count"], file_stats["parsed_event_count"]),
            6,
        )
        per_file_rows.append(file_stats)

    summary["valid_task_annotator_pair_count"] = len(valid_pairs_seen)
    summary["multi_session_pair_count"] = sum(1 for sessions in pair_sessions.values() if len(sessions) > 1)
    summary["multi_session_pair_rate"] = round(
        _safe_rate(summary["multi_session_pair_count"], summary["valid_task_annotator_pair_count"]),
        6,
    )
    summary["parse_error_rate"] = round(
        _safe_rate(summary["parse_error_count"], summary["nonempty_line_count"]),
        6,
    )
    summary["missing_script_version_rate"] = round(
        _safe_rate(summary["missing_script_version_count"], summary["parsed_event_count"]),
        6,
    )
    summary["unknown_task_rate"] = round(_safe_rate(summary["unknown_task_count"], summary["parsed_event_count"]), 6)
    summary["unknown_annotator_rate"] = round(
        _safe_rate(summary["unknown_annotator_count"], summary["parsed_event_count"]),
        6,
    )
    summary["unknown_project_rate"] = round(
        _safe_rate(summary["unknown_project_count"], summary["parsed_event_count"]),
        6,
    )
    summary["unknown_session_rate"] = round(
        _safe_rate(summary["unknown_session_count"], summary["parsed_event_count"]),
        6,
    )

    return summary, per_file_rows


def _write_per_file_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "file_name",
        "blank_line_count",
        "nonempty_line_count",
        "parsed_event_count",
        "parse_error_count",
        "parse_error_rate",
        "unknown_task_count",
        "unknown_annotator_count",
        "unknown_project_count",
        "unknown_session_count",
        "missing_script_version_count",
        "missing_script_version_rate",
        "valid_task_annotator_pair_count",
        "multi_session_pair_count",
        "multi_session_pair_rate",
    ]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({key: row.get(key, "") for key in fieldnames})


def _write_summary_json(path: Path, summary: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Audit active-log quality signals for P1/T1 timing readiness.")
    parser.add_argument("active_logs", help="Path to an active-log directory or a concrete JSONL file")
    parser.add_argument("--summary-json", type=Path, default=None, help="Write overall audit summary JSON")
    parser.add_argument("--per-file-csv", type=Path, default=None, help="Write per-file audit CSV")
    args = parser.parse_args(argv)

    summary, per_file_rows = audit_active_logs(args.active_logs)

    if args.summary_json is not None:
        _write_summary_json(args.summary_json, summary)
    if args.per_file_csv is not None:
        _write_per_file_csv(args.per_file_csv, per_file_rows)

    if args.summary_json is None and args.per_file_csv is None:
        print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
