from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def resolve_active_log_files(active_log_path: str | Path) -> tuple[Path | None, list[Path]]:
    """Resolve active log files without recursing into legacy archives.

    Rules:
    - If a concrete file is passed, use only that file.
    - If a directory is passed and it contains `active_times_*.jsonl`, use those files.
    - Otherwise, if the directory contains `new_server/active_times_*.jsonl`, use that folder.
    - Never recurse into nested subdirectories such as `legacy/`.
    """
    path = Path(active_log_path)
    if not path.exists():
        return None, []

    if path.is_file():
        return path.parent, [path]

    direct_files = sorted(path.glob("active_times_*.jsonl"))
    if direct_files:
        return path, direct_files

    new_server_dir = path / "new_server"
    if new_server_dir.exists() and new_server_dir.is_dir():
        new_server_files = sorted(new_server_dir.glob("active_times_*.jsonl"))
        if new_server_files:
            return new_server_dir, new_server_files

    return path, []


def active_log_manifest(root: str | Path) -> dict[str, Any]:
    """Return a deterministic manifest for a frozen/direct active-log root."""
    base = Path(root).resolve()
    _resolved, files = resolve_active_log_files(base)
    rows = []
    for path in sorted(files, key=lambda item: item.name.lower()):
        rows.append({
            "relative_path": path.relative_to(base).as_posix() if path.is_relative_to(base) else path.name,
            "size": path.stat().st_size,
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        })
    payload = json.dumps(rows, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return {"root": base.as_posix(), "file_manifest": rows, "file_count": len(rows), "aggregate_sha256": hashlib.sha256(payload.encode("utf-8")).hexdigest()}


def _event_time(event: dict[str, Any]) -> datetime | None:
    for key in ("server_received_at", "server_time", "event_time", "timestamp", "time", "created_at"):
        value = event.get(key)
        if value in (None, ""):
            continue
        try:
            if isinstance(value, (int, float)) or str(value).replace(".", "", 1).isdigit():
                seconds = float(value)
                if seconds > 10_000_000_000:
                    seconds /= 1000
                return datetime.fromtimestamp(seconds, tz=timezone.utc)
            parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
            return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
        except (OSError, OverflowError, ValueError):
            continue
    return None


def freeze_active_log_snapshot(
    source_live_root: str | Path,
    frozen_root: str | Path,
    collection_cutoff_server_time: str,
    freeze_operator: str,
    manifest_path: str | Path,
) -> dict[str, Any]:
    """Copy a live C1 log root and bind the copy to a cutoff and source SHA."""
    source = Path(source_live_root).resolve()
    frozen = Path(frozen_root).resolve()
    source_display = source.as_posix()
    frozen_display = frozen.as_posix()
    if source == frozen:
        raise ValueError("frozen_root must differ from source_live_root")
    cutoff = datetime.fromisoformat(str(collection_cutoff_server_time).replace("Z", "+00:00"))
    if cutoff.tzinfo is None:
        cutoff = cutoff.replace(tzinfo=timezone.utc)
    source_manifest = active_log_manifest(source)
    for row in source_manifest["file_manifest"]:
        with (source / row["relative_path"]).open(encoding="utf-8", errors="replace") as stream:
            for line_number, line in enumerate(stream, 1):
                try:
                    event = json.loads(line)
                except json.JSONDecodeError as exc:
                    raise ValueError(f"active-log JSON parse error: {row['relative_path']}:{line_number}") from exc
                if _event_time(event) is None:
                    raise ValueError(f"active-log event lacks server/event time: {row['relative_path']}:{line_number}")
    if frozen.exists():
        if any(frozen.iterdir()):
            raise ValueError("frozen_root must be empty before C1 freeze")
    else:
        frozen.mkdir(parents=True, exist_ok=False)
    source_post_cutoff = 0
    event_min: datetime | None = None
    event_max: datetime | None = None
    for row in source_manifest["file_manifest"]:
        src = source / row["relative_path"]
        dst = frozen / row["relative_path"]
        dst.parent.mkdir(parents=True, exist_ok=True)
        included: list[str] = []
        with src.open(encoding="utf-8", errors="replace") as stream:
            for line in stream:
                try:
                    event = json.loads(line)
                except json.JSONDecodeError as exc:
                    raise ValueError(f"active-log changed during freeze: {row['relative_path']}") from exc
                when = _event_time(event)
                if when is None:
                    raise ValueError(f"active-log changed during freeze: {row['relative_path']}")
                if when > cutoff:
                    source_post_cutoff += 1
                    continue
                included.append(line)
                event_min = when if event_min is None or when < event_min else event_min
                event_max = when if event_max is None or when > event_max else event_max
        dst.write_text("".join(included), encoding="utf-8")
    frozen_manifest = active_log_manifest(frozen)
    if active_log_manifest(source)["aggregate_sha256"] != source_manifest["aggregate_sha256"]:
        raise ValueError("active-log source changed during freeze")
    payload = {
        "schema_version": "paper_a_c1_active_log_freeze_v1", "stage": "C1",
        "freeze_mode": "cutoff_filtered_immutable_copy",
        "source_live_root": source_display, "frozen_root": frozen_display,
        "collection_cutoff_server_time": cutoff.isoformat(),
        "freeze_created_at": datetime.now(timezone.utc).isoformat(), "freeze_operator": freeze_operator,
        "source_file_count": source_manifest["file_count"],
        "source_live_aggregate_sha256": source_manifest["aggregate_sha256"],
        # The contract binds the cutoff-eligible source bytes to the frozen
        # copy. Raw live bytes remain separately auditable above.
        "source_aggregate_sha256": frozen_manifest["aggregate_sha256"],
        "frozen_file_count": frozen_manifest["file_count"], "frozen_aggregate_sha256": frozen_manifest["aggregate_sha256"],
        "file_manifest": frozen_manifest["file_manifest"],
        "event_time_min": event_min.isoformat() if event_min else "", "event_time_max": event_max.isoformat() if event_max else "",
        "source_post_cutoff_event_count": source_post_cutoff,
        "excluded_post_cutoff_event_count": source_post_cutoff,
        "post_cutoff_event_count": 0,
    }
    manifest = Path(manifest_path)
    manifest.parent.mkdir(parents=True, exist_ok=True)
    manifest.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return payload


def validate_active_log_freeze_manifest(
    manifest_path: str | Path, active_root: str | Path, *, allow_immutable_copy: bool = False,
) -> dict[str, Any]:
    payload = json.loads(Path(manifest_path).read_text(encoding="utf-8"))
    source = Path(payload.get("source_live_root", "")).resolve()
    frozen = Path(payload.get("frozen_root", "")).resolve()
    active = Path(active_root).resolve()
    if payload.get("stage") != "C1" or not source or not frozen or source == frozen:
        raise ValueError("invalid C1 active-log freeze contract")
    if not payload.get("freeze_operator") or not payload.get("collection_cutoff_server_time"):
        raise ValueError("C1 active-log freeze lacks operator or cutoff")
    if not payload.get("source_file_count") or payload.get("source_file_count") != payload.get("frozen_file_count"):
        raise ValueError("C1 active-log freeze file counts are empty or inconsistent")
    if payload.get("post_cutoff_event_count") != 0:
        raise ValueError("C1 active-log freeze contains post-cutoff events")
    if active != frozen and not allow_immutable_copy:
        raise ValueError("active_root is not the frozen root bound by the C1 manifest")
    if payload.get("source_aggregate_sha256") != payload.get("frozen_aggregate_sha256"):
        raise ValueError("cutoff-eligible source and frozen aggregate SHA differ")
    actual = active_log_manifest(active)
    if actual["aggregate_sha256"] != payload.get("frozen_aggregate_sha256"):
        raise ValueError("C1 active-log freeze aggregate SHA mismatch")
    if payload.get("freeze_mode") != "cutoff_filtered_immutable_copy":
        raise ValueError("C1 active-log freeze mode is not cutoff-filtered")
    return payload
