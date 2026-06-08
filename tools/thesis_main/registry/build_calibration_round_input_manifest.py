from __future__ import annotations

import argparse
import json
from pathlib import Path
from urllib.parse import urlparse


TASK_SET_ARGS = [
    ("Calibration_anchor", "anchor_import"),
    ("Calibration_core", "core_import"),
    ("Calibration_reserve", "reserve_import"),
]


def _stem_from_url(value: str) -> str:
    parsed = urlparse(value)
    path = parsed.path or value
    return Path(path).stem


def _task_identifier(task: dict, data: dict) -> str:
    for key in ("task_id", "base_task_id", "image_id", "title", "image"):
        value = data.get(key) or task.get(key)
        if value:
            value_str = str(value).strip()
            if key in {"title", "image"}:
                return _stem_from_url(value_str)
            return value_str
    raise ValueError("task is missing task_id, base_task_id, image_id, title, and image")


def _normalize_import_task(task: dict, expected_group: str, source_path: Path) -> dict[str, str]:
    data = task.get("data") if isinstance(task.get("data"), dict) else task
    if not isinstance(data, dict):
        raise ValueError(f"{source_path} contains a task without data object")

    dataset_group = str(data.get("dataset_group") or expected_group).strip() or expected_group
    if dataset_group != expected_group:
        raise ValueError(f"{source_path} contains dataset_group={dataset_group}, expected {expected_group}")

    task_id = _task_identifier(task, data)
    base_task_id = str(data.get("base_task_id") or task.get("base_task_id") or task_id).strip()
    image_id = str(data.get("image_id") or _stem_from_url(str(data.get("image") or task_id))).strip()

    return {
        "task_id": task_id,
        "base_task_id": base_task_id,
        "image_id": image_id,
        "dataset_group": dataset_group,
        "source_import_json": str(source_path.as_posix()),
    }


def load_import_tasks(path: Path, expected_group: str) -> list[dict[str, str]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, list):
        raise ValueError(f"{path} must be a Label Studio import JSON array")
    tasks = [_normalize_import_task(task, expected_group, path) for task in payload]
    if not tasks:
        raise ValueError(f"{path} does not contain any tasks")
    task_ids = [task["task_id"] for task in tasks]
    if len(task_ids) != len(set(task_ids)):
        raise ValueError(f"{path} contains duplicate task_id values")
    return tasks


def build_manifest(
    *,
    anchor_import: Path,
    core_import: Path,
    reserve_import: Path,
    semi_import: Path | None,
    manifest_version: str,
) -> dict:
    import_paths = {
        "anchor_import": anchor_import,
        "core_import": core_import,
        "reserve_import": reserve_import,
    }
    task_sets = {}
    for expected_group, arg_name in TASK_SET_ARGS:
        task_sets[expected_group] = load_import_tasks(import_paths[arg_name], expected_group)
    if semi_import is not None:
        task_sets["Calibration_semi"] = load_import_tasks(semi_import, "Calibration_semi")

    return {
        "meta": {
            "manifest_version": manifest_version,
            "source": "planned_import_json",
            "c1_core_operational_target_k": 5,
            "c1_core_preregistered_min_k": 4,
            "reserve_policy": "unchanged_C2_only",
            "c1_status": "provisional_only",
        },
        "task_sets": task_sets,
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Build calibration_round_input_manifest_v1.json from planned Stage 2 import JSON files."
    )
    parser.add_argument("--anchor-import", required=True, type=Path)
    parser.add_argument("--core-import", required=True, type=Path)
    parser.add_argument("--reserve-import", required=True, type=Path)
    parser.add_argument("--semi-import", type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--manifest-version", default="v1")
    args = parser.parse_args()

    manifest = build_manifest(
        anchor_import=args.anchor_import,
        core_import=args.core_import,
        reserve_import=args.reserve_import,
        semi_import=args.semi_import,
        manifest_version=args.manifest_version,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
