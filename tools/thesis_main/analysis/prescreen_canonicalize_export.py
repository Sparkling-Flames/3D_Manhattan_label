from __future__ import annotations

import argparse
import csv
import hashlib
import json
import shutil
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_PROJECT_ROOT = Path(__file__).resolve().parents[3]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from tools.thesis_main.analysis.analyze_quality import extract_data, load_active_logs, lookup_active_log_entry
from tools.thesis_main.analysis.audit_p1_exact_copy_low_time import canonical_geometry_hash
from tools.thesis_main.analysis.active_log_utils import resolve_active_log_files

DEFAULT_OUTPUT_DIR = Path("analysis_results/prescreen_closeout")


def _safe_str(value: Any, default: str = "") -> str:
    if value is None:
        return default
    text = str(value).strip()
    return text if text else default


def _load_export(path: Path) -> list[dict[str, Any]]:
    with path.open("r", encoding="utf-8") as f:
        payload = json.load(f)
    if not isinstance(payload, list):
        raise ValueError(f"{path} is not a Label Studio task-list export")
    return payload


def _worker_id(annotation: dict[str, Any]) -> str:
    completed_by = annotation.get("completed_by")
    if isinstance(completed_by, dict):
        for key in ("id", "email", "username", "pk"):
            value = _safe_str(completed_by.get(key))
            if value:
                return value
    return _safe_str(completed_by, "unknown")


def _annotation_id(annotation: dict[str, Any], index: int) -> str:
    return _safe_str(annotation.get("id"), f"annotation_index_{index}")


def _task_id(task: dict[str, Any], index: int) -> str:
    return _safe_str(task.get("id") or task.get("task_id"), f"task_index_{index}")


def _project_id(task: dict[str, Any]) -> str:
    return _safe_str(task.get("project") or task.get("project_id"))


def _data(task: dict[str, Any]) -> dict[str, Any]:
    data = task.get("data")
    return data if isinstance(data, dict) else {}


def _task_label(task: dict[str, Any]) -> str:
    data = _data(task)
    for key in ("title", "base_task_id", "task_id", "image"):
        value = data.get(key)
        if value:
            return Path(str(value)).name
    return ""


def _sort_value(annotation: dict[str, Any], index: int) -> tuple[str, str, str, str]:
    return (
        _safe_str(annotation.get("updated_at")),
        _safe_str(annotation.get("completed_at")),
        _safe_str(annotation.get("created_at")),
        _annotation_id(annotation, index),
    )


def _active_entry(
    active_times: dict,
    project_id: str,
    task_id: str,
    worker_id: str,
    lead_time_seconds: float,
) -> tuple[str, str, str, str, int, int]:
    entry, match_status = lookup_active_log_entry(active_times, project_id, task_id, worker_id)
    if entry:
        return (
            str(float(entry.get("active_time_value", 0.0))),
            "log",
            match_status,
            str(entry.get("active_time_source_file", "")),
            int(entry.get("active_time_session_count", 0)),
            int(entry.get("active_time_event_count", 0)),
        )
    if lead_time_seconds > 0:
        status = "fallback_no_direct_log" if match_status == "missing" else f"fallback_{match_status}"
        return (str(float(lead_time_seconds)), "lead_time_fallback", status, "", 0, 0)
    return ("", "missing", match_status, "", 0, 0)


def _geometry(annotation: dict[str, Any], round_px: float) -> tuple[str, str, int, str]:
    try:
        corners, _poly, _choice_map, _quality = extract_data(annotation.get("result", []))
        digest, payload, n_corners = canonical_geometry_hash(corners, round_px=round_px)
        return digest, payload, n_corners, ""
    except Exception as exc:
        return "", "", 0, str(exc)


def _canonical_id(project_id: str, task_id: str, worker_id: str) -> str:
    payload = f"{project_id}|{task_id}|{worker_id}".encode("utf-8")
    return hashlib.sha1(payload).hexdigest()[:16]


def build_canonical_tables(
    export_paths: list[Path],
    active_log_path: Path | None = None,
    *,
    geometry_round_px: float = 0.5,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    active_times = load_active_logs(str(active_log_path)) if active_log_path else {}
    groups: dict[tuple[str, str, str], list[dict[str, Any]]] = defaultdict(list)
    n_tasks = 0

    for export_path in export_paths:
        for task_index, task in enumerate(_load_export(export_path), start=1):
            n_tasks += 1
            task_id = _task_id(task, task_index)
            project_id = _project_id(task)
            data = _data(task)
            annotations = task.get("annotations") or []
            if not isinstance(annotations, list):
                continue
            for ann_index, ann in enumerate(annotations, start=1):
                if not isinstance(ann, dict):
                    continue
                worker_id = _worker_id(ann)
                lead_time = float(ann.get("lead_time", 0) or 0)
                active_time, source, match_status, source_file, session_count, event_count = _active_entry(
                    active_times, project_id, task_id, worker_id, lead_time
                )
                geometry_hash, geometry_payload, n_corners, parse_error = _geometry(ann, geometry_round_px)
                row = {
                    "source_export": str(export_path),
                    "project_id": project_id,
                    "task_id": task_id,
                    "task_key": f"{project_id}:{task_id}" if project_id else task_id,
                    "task_label": _task_label(task),
                    "dataset_group": _safe_str(data.get("dataset_group")),
                    "condition": _safe_str(data.get("condition")),
                    "annotator_id": worker_id,
                    "annotation_id": _annotation_id(ann, ann_index),
                    "annotation_sort_key": "|".join(_sort_value(ann, ann_index)),
                    "lead_time_seconds": str(lead_time) if lead_time > 0 else "",
                    "active_time": active_time,
                    "active_time_source": source,
                    "active_time_match_status": match_status,
                    "active_time_source_file": source_file,
                    "active_time_session_count": session_count,
                    "active_time_event_count": event_count,
                    "geometry_hash": geometry_hash,
                    "canonical_geometry": geometry_payload,
                    "n_corners": n_corners,
                    "parse_error": parse_error,
                    "primary_active_time_eligible": source == "log",
                    "sensitivity_active_time_eligible": source in {"log", "lead_time_fallback"},
                }
                groups[(project_id, task_id, worker_id)].append(row)

    canonical_rows: list[dict[str, Any]] = []
    duplicate_rows: list[dict[str, Any]] = []
    for (project_id, task_id, worker_id), rows in sorted(groups.items()):
        rows = sorted(rows, key=lambda r: r["annotation_sort_key"])
        canonical = rows[-1].copy()
        duplicate_ids = [r["annotation_id"] for r in rows if r["annotation_id"] != canonical["annotation_id"]]
        hashes = {r["geometry_hash"] for r in rows if r["geometry_hash"]}
        group_size = len(rows)
        duplicate_type = "single"
        if group_size > 1:
            duplicate_type = "revision" if len(hashes) > 1 else "duplicate_same_geometry"
        canonical.update(
            {
                "canonical_annotation_id": _canonical_id(project_id, task_id, worker_id),
                "raw_canonical_annotation_id": canonical["annotation_id"],
                "duplicate_annotation_ids": ";".join(duplicate_ids),
                "duplicate_group_size": group_size,
                "duplicate_geometry_type": duplicate_type,
                "duplicate_time_ambiguous": group_size > 1,
                "eligible_for_primary_analysis": True,
                "exclusion_reason": "",
            }
        )
        canonical_rows.append(canonical)
        if group_size > 1:
            duplicate_rows.append(
                {
                    "project_id": project_id,
                    "task_id": task_id,
                    "task_key": canonical["task_key"],
                    "annotator_id": worker_id,
                    "canonical_annotation_id": canonical["canonical_annotation_id"],
                    "raw_canonical_annotation_id": canonical["raw_canonical_annotation_id"],
                    "all_annotation_ids": ";".join(r["annotation_id"] for r in rows),
                    "duplicate_annotation_ids": ";".join(duplicate_ids),
                    "duplicate_group_size": group_size,
                    "duplicate_geometry_type": duplicate_type,
                    "n_distinct_geometry_hashes": len(hashes),
                    "duplicate_time_ambiguous": True,
                    "lead_time_policy": "canonical_only_not_summed",
                }
            )

    summary = {
        "n_exports": len(export_paths),
        "n_tasks_seen": n_tasks,
        "n_raw_annotation_rows": sum(len(v) for v in groups.values()),
        "n_canonical_rows": len(canonical_rows),
        "n_duplicate_groups": len(duplicate_rows),
        "n_duplicate_same_geometry_groups": sum(r["duplicate_geometry_type"] == "duplicate_same_geometry" for r in duplicate_rows),
        "n_revision_groups": sum(r["duplicate_geometry_type"] == "revision" for r in duplicate_rows),
    }
    return canonical_rows, duplicate_rows, summary


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def snapshot_inputs(paths: list[Path], output_dir: Path) -> Path:
    raw_dir = output_dir / "raw_inputs"
    raw_dir.mkdir(parents=True, exist_ok=True)
    manifest_rows = []
    for src in paths:
        if not src.exists():
            manifest_rows.append({"source_path": str(src), "snapshot_path": "", "exists": False, "bytes": "", "file_count": ""})
            continue
        dst = raw_dir / src.name
        if src.is_dir():
            _resolved_dir, source_files = resolve_active_log_files(src)
            dst.mkdir(parents=True, exist_ok=True)
            files = []
            for source_file in source_files:
                copied = dst / source_file.name
                shutil.copy2(source_file, copied)
                files.append(copied)
            manifest_rows.append(
                {
                    "source_path": str(src),
                    "snapshot_path": str(dst),
                    "exists": True,
                    "bytes": sum(p.stat().st_size for p in files),
                    "file_count": len(files),
                }
            )
        else:
            shutil.copy2(src, dst)
            manifest_rows.append(
                {"source_path": str(src), "snapshot_path": str(dst), "exists": True, "bytes": dst.stat().st_size, "file_count": 1}
            )
    manifest_path = raw_dir / "raw_input_snapshot_manifest.csv"
    _write_csv(manifest_path, manifest_rows)
    return manifest_path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--export-json", action="append", required=True, help="P1 Label Studio export JSON. Repeat for manual/semi/oos.")
    parser.add_argument("--active-log", default=None, help="active_logs directory or active_times_*.jsonl file.")
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    parser.add_argument("--snapshot-input", action="append", default=[], help="Extra raw input to copy into raw_inputs.")
    parser.add_argument("--geometry-round-px", type=float, default=0.5)
    args = parser.parse_args(argv)

    output_dir = Path(args.output_dir)
    export_paths = [Path(p) for p in args.export_json]
    active_log = Path(args.active_log) if args.active_log else None
    canonical, duplicate, summary = build_canonical_tables(export_paths, active_log, geometry_round_px=args.geometry_round_px)

    canonical_path = output_dir / "prescreen_canonical_annotations.csv"
    duplicate_path = output_dir / "prescreen_duplicate_annotation_audit.csv"
    _write_csv(canonical_path, canonical)
    _write_csv(duplicate_path, duplicate)

    snapshot_paths = export_paths + ([active_log] if active_log else []) + [Path(p) for p in args.snapshot_input]
    manifest_path = snapshot_inputs(snapshot_paths, output_dir)
    summary.update(
        {
            "created_at": datetime.now(timezone.utc).isoformat(),
            "canonical_csv": str(canonical_path),
            "duplicate_audit_csv": str(duplicate_path),
            "raw_input_manifest": str(manifest_path),
        }
    )
    (output_dir / "prescreen_canonicalize_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
