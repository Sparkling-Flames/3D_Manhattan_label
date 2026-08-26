from __future__ import annotations

import csv
import json
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / "analysis_results" / "rq1_raw_audit_20260826"

SOURCE_GROUPS = {
    "P1": [
        "export_label/stage1_English/*.json",
        "export_label/stage1_chinese/*.json",
    ],
    "C1": [
        "export_label/stage2_English/*.json",
        "export_label/stage2_Chinese/*.json",
    ],
    "C2-B": [
        "export_label/c2B_English/*.json",
        "export_label/c2B_Chinese/*.json",
    ],
    "C2-A-RP-B1": ["export_label/c2arp_block1/*.json"],
    "C2-A-RP-B2": ["export_label/c2arp_block2/*.json"],
}

IDENTITY_KEYS = (
    "base_task_id",
    "planned_task_id",
    "task_id",
    "image_id",
    "source_task_id",
    "original_task_id",
)
CONDITION_KEYS = (
    "condition",
    "raw_condition",
    "mode",
    "annotation_mode",
    "task_mode",
    "task_lane",
    "stratum",
    "task_stratum",
    "dataset_group",
    "language",
    "language_group",
)


def scalar(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, (str, int, float, bool)):
        return str(value)
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def image_basename(data: dict[str, Any]) -> str:
    for key in ("image", "img", "image_url", "url"):
        value = data.get(key)
        if not value:
            continue
        path = urlparse(str(value)).path
        name = Path(path).name
        if name:
            return name
    return ""


def base_candidate(data: dict[str, Any]) -> str:
    for key in IDENTITY_KEYS:
        value = data.get(key)
        if value not in (None, ""):
            return scalar(value)
    name = image_basename(data)
    return Path(name).stem if name else ""


def extract_results(annotation: dict[str, Any]) -> tuple[int, dict[str, list[str]], Counter[str]]:
    keypoints = 0
    choices: dict[str, list[str]] = defaultdict(list)
    types: Counter[str] = Counter()
    for row in annotation.get("result") or []:
        if not isinstance(row, dict):
            continue
        kind = str(row.get("type") or "")
        types[kind] += 1
        if kind in {"keypointlabels", "keypointregion"}:
            keypoints += 1
        if kind in {"choices", "labels", "taxonomy"}:
            value = row.get("value") or {}
            raw = value.get("choices") or value.get("labels") or value.get("taxonomy") or []
            if not isinstance(raw, list):
                raw = [raw]
            field = str(row.get("from_name") or row.get("id") or kind)
            choices[field].extend(str(item) for item in raw if item not in (None, ""))
    return keypoints, dict(choices), types


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    rows: list[dict[str, Any]] = []
    file_summaries: list[dict[str, Any]] = []
    key_values: dict[str, Counter[str]] = defaultdict(Counter)
    all_data_keys: Counter[str] = Counter()

    for stage, globs in SOURCE_GROUPS.items():
        files: list[Path] = []
        for pattern in globs:
            files.extend(sorted(ROOT.glob(pattern)))
        for path in sorted(set(files)):
            payload = json.loads(path.read_text(encoding="utf-8-sig"))
            if not isinstance(payload, list):
                raise TypeError(f"Expected list export: {path}")
            file_workers: set[str] = set()
            file_bases: set[str] = set()
            file_projects: set[str] = set()
            annotation_count = 0
            geometry_count = 0
            task_annotation_counts: list[int] = []
            file_data_keys: Counter[str] = Counter()
            result_types: Counter[str] = Counter()

            for task in payload:
                if not isinstance(task, dict):
                    continue
                data = task.get("data") or {}
                if not isinstance(data, dict):
                    data = {}
                for key, value in data.items():
                    file_data_keys[str(key)] += 1
                    all_data_keys[str(key)] += 1
                    text = scalar(value)
                    if text and len(text) <= 200:
                        key_values[str(key)][text] += 1
                runtime_task_id = scalar(task.get("id"))
                project_task = scalar(task.get("project"))
                base = base_candidate(data)
                image_name = image_basename(data)
                annotations = task.get("annotations") or []
                if not isinstance(annotations, list):
                    annotations = []
                task_annotation_counts.append(len(annotations))
                file_bases.add(base)
                if project_task:
                    file_projects.add(project_task)

                for ann in annotations:
                    if not isinstance(ann, dict):
                        continue
                    annotation_count += 1
                    worker = scalar(ann.get("completed_by"))
                    project = scalar(ann.get("project") or task.get("project"))
                    if worker:
                        file_workers.add(worker)
                    if project:
                        file_projects.add(project)
                    keypoint_count, choices, ann_types = extract_results(ann)
                    result_types.update(ann_types)
                    if keypoint_count >= 4 and keypoint_count % 2 == 0:
                        geometry_count += 1
                    selected = {key: scalar(data.get(key)) for key in (*IDENTITY_KEYS, *CONDITION_KEYS) if key in data}
                    rows.append(
                        {
                            "stage_guess": stage,
                            "source_file": path.relative_to(ROOT).as_posix(),
                            "runtime_task_id": runtime_task_id,
                            "annotation_id": scalar(ann.get("id")),
                            "annotation_unique_id": scalar(ann.get("unique_id")),
                            "project_id": project,
                            "worker_raw": worker,
                            "base_task_candidate": base,
                            "image_basename": image_name,
                            "file_upload": scalar(task.get("file_upload")),
                            "created_at": scalar(ann.get("created_at")),
                            "updated_at": scalar(ann.get("updated_at")),
                            "was_cancelled": scalar(ann.get("was_cancelled")),
                            "ground_truth": scalar(ann.get("ground_truth")),
                            "lead_time": scalar(ann.get("lead_time")),
                            "result_count": len(ann.get("result") or []),
                            "keypoint_count": keypoint_count,
                            "geometry_even_pair_candidate": keypoint_count >= 4 and keypoint_count % 2 == 0,
                            "choices_json": json.dumps(choices, ensure_ascii=False, sort_keys=True),
                            "data_identity_json": json.dumps(selected, ensure_ascii=False, sort_keys=True),
                            "prediction_present": bool(ann.get("prediction") or task.get("predictions")),
                            "parent_annotation": scalar(ann.get("parent_annotation")),
                            "parent_prediction": scalar(ann.get("parent_prediction")),
                        }
                    )

            file_summaries.append(
                {
                    "stage_guess": stage,
                    "source_file": path.relative_to(ROOT).as_posix(),
                    "sha256_source_not_recomputed": "git_blob_managed",
                    "task_count": len(payload),
                    "annotation_count": annotation_count,
                    "geometry_even_pair_candidate_count": geometry_count,
                    "distinct_workers": len(file_workers),
                    "distinct_base_candidates": len(file_bases),
                    "project_ids_json": json.dumps(sorted(file_projects)),
                    "task_annotation_min": min(task_annotation_counts) if task_annotation_counts else 0,
                    "task_annotation_median": sorted(task_annotation_counts)[len(task_annotation_counts) // 2] if task_annotation_counts else 0,
                    "task_annotation_max": max(task_annotation_counts) if task_annotation_counts else 0,
                    "data_keys_json": json.dumps(sorted(file_data_keys)),
                    "result_types_json": json.dumps(result_types, sort_keys=True),
                }
            )

    row_fields = list(rows[0]) if rows else []
    with (OUT / "raw_annotation_index.csv").open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=row_fields)
        writer.writeheader()
        writer.writerows(rows)

    summary_fields = list(file_summaries[0]) if file_summaries else []
    with (OUT / "raw_export_file_summary.csv").open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=summary_fields)
        writer.writeheader()
        writer.writerows(file_summaries)

    compact_values = {
        key: dict(counter.most_common(50))
        for key, counter in sorted(key_values.items())
        if len(counter) <= 50
    }
    schema = {
        "source_groups": SOURCE_GROUPS,
        "row_count": len(rows),
        "file_count": len(file_summaries),
        "all_data_keys": dict(sorted(all_data_keys.items())),
        "low_cardinality_data_values": compact_values,
        "stage_counts": dict(Counter(row["stage_guess"] for row in rows)),
        "stage_geometry_candidate_counts": dict(
            Counter(row["stage_guess"] for row in rows if row["geometry_even_pair_candidate"])
        ),
    }
    (OUT / "raw_schema_summary.json").write_text(
        json.dumps(schema, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8"
    )
    print(json.dumps({"output": str(OUT), "rows": len(rows), "files": len(file_summaries)}, indent=2))


if __name__ == "__main__":
    main()
