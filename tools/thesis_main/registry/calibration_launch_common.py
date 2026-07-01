from __future__ import annotations

import csv
import json
from pathlib import Path
from urllib.parse import urlparse


HASH_FIELDS = (
    "source_image_hash",
    "image_hash",
    "image_sha256",
    "source_sha256",
    "sha256",
    "audit_hash",
)


def safe(value: object) -> str:
    return str(value or "").strip()


def truthy(value: object) -> bool:
    return safe(value).lower() in {"1", "true", "yes", "y", "watch", "pass_with_watch"}


def stem_from_url(value: object) -> str:
    text = safe(value)
    if not text:
        return ""
    parsed = urlparse(text)
    return Path(parsed.path or text).stem


def load_json(path: Path) -> object:
    return json.loads(path.read_text(encoding="utf-8"))


def load_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", newline="", encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def task_data(task: dict) -> dict:
    data = task.get("data") if isinstance(task.get("data"), dict) else task
    if not isinstance(data, dict):
        return {}
    return data


def task_record(task: dict, *, source_path: Path | None = None, default_group: str = "") -> dict[str, str]:
    data = task_data(task)
    task_id = safe(data.get("task_id") or task.get("task_id"))
    title = safe(data.get("title") or task.get("title"))
    image = safe(data.get("image") or task.get("image"))
    if not task_id:
        task_id = stem_from_url(title or image)
    base_task_id = safe(data.get("base_task_id") or task.get("base_task_id") or task_id)
    image_id = safe(data.get("image_id") or task.get("image_id") or stem_from_url(image) or task_id)
    image_hash = ""
    for field in HASH_FIELDS:
        image_hash = safe(data.get(field) or task.get(field))
        if image_hash:
            break
    return {
        "task_id": task_id,
        "base_task_id": base_task_id,
        "image_id": image_id,
        "title_stem": stem_from_url(title),
        "image_stem": stem_from_url(image),
        "image_hash": image_hash,
        "dataset_group": safe(data.get("dataset_group") or task.get("dataset_group") or default_group),
        "source_path": str(source_path or ""),
        "source_import_json": safe(data.get("source_import_json") or task.get("source_import_json")),
    }


def load_ls_import_tasks(path: Path) -> list[dict[str, str]]:
    payload = load_json(path)
    if not isinstance(payload, list):
        raise ValueError(f"{path} must be a Label Studio import JSON array")
    return [task_record(task, source_path=path) for task in payload if isinstance(task, dict)]


def load_calibration_manifest_tasks(path: Path) -> dict[str, list[dict[str, str]]]:
    payload = load_json(path)
    if not isinstance(payload, dict) or not isinstance(payload.get("task_sets"), dict):
        raise ValueError(f"{path} must contain task_sets")
    out: dict[str, list[dict[str, str]]] = {}
    for group, tasks in payload["task_sets"].items():
        if not isinstance(tasks, list):
            raise ValueError(f"{path} task_sets.{group} must be a list")
        out[group] = [task_record(task, source_path=path, default_group=group) for task in tasks if isinstance(task, dict)]
    return out


def unique_by(rows: list[dict[str, str]], key: str) -> set[str]:
    return {safe(row.get(key)) for row in rows if safe(row.get(key))}
