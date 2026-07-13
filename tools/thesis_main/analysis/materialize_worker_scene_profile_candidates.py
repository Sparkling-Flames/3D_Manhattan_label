from __future__ import annotations

import argparse
import csv
import json
from collections import defaultdict
from pathlib import Path
from typing import Any, Iterable

from tools.thesis_main.analysis.vfinal_artifact_utils import COMMON_SIDEcar_FIELDS, sha256_file, sidecar_common, write_csv_rows


RULE_VERSION = "worker_scene_profile_candidate_v1"


def _text(value: Any) -> str:
    return "" if value is None else str(value).strip()


def _bool(value: Any) -> bool:
    return _text(value).lower() in {"1", "true", "yes"}


def _load_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", newline="", encoding="utf-8-sig") as handle:
        return list(csv.DictReader(handle))


def _load_loo(path: Path | None) -> dict[tuple[str, str], dict[str, str]]:
    if path is None or not path.exists():
        return {}
    return {(row.get("task_id", ""), row.get("worker_id", "")): row for row in _load_csv(path)}


def _scene_key(row: dict[str, Any], definition: str) -> str:
    if definition == "scene_label":
        return _text(row.get("scene_label")) or _text(row.get("base_task_id")) or _text(row.get("task_id"))
    if definition == "dataset_group":
        return _text(row.get("dataset_group"))
    if definition == "task_id":
        return _text(row.get("task_id"))
    return _text(row.get("base_task_id")) or _text(row.get("task_id"))


def materialize_worker_scene_profile_candidates(
    quality_csv: Path,
    output_dir: Path,
    *,
    geometry_loo_csv: Path | None = None,
    input_status: str = "dry_run",
    scene_definitions: tuple[str, ...] = ("base_task_id", "task_id", "dataset_group", "scene_label"),
) -> dict[str, Any]:
    quality_rows = _load_csv(quality_csv)
    loo = _load_loo(geometry_loo_csv)
    source_sha = sha256_file(quality_csv)
    profile_rows = []
    grouped: dict[tuple[str, str, str], list[dict[str, Any]]] = defaultdict(list)
    for definition in scene_definitions:
        for row in quality_rows:
            worker = _text(row.get("worker_id") or row.get("annotator_id"))
            scene = _scene_key(row, definition)
            if not worker or not scene:
                continue
            grouped[(definition, worker, scene)].append(row)
    for (definition, worker, scene), rows in sorted(grouped.items()):
        geometry_values = []
        for row in rows:
            loo_row = loo.get((_text(row.get("task_id")), worker), {})
            try:
                value = float(loo_row.get("loo_similarity_mean", ""))
            except (TypeError, ValueError):
                continue
            geometry_values.append(value)
        positive = sum(bool(_text(row.get("difficulty")) and _text(row.get("difficulty")).lower() not in {"trivial", "none"}) for row in rows)
        issue = sum(bool(_text(row.get("model_issue_primary") or row.get("model_issue")) and _text(row.get("model_issue_primary") or row.get("model_issue")).lower() not in {"acceptable", "none"}) for row in rows)
        profile_rows.append(
            {
                **sidecar_common(source_artifact=str(quality_csv), source_sha256=source_sha, pool=_text(rows[0].get("dataset_group")), condition=_text(rows[0].get("condition")), validity_status="dry_run" if input_status != "formal" else "candidate_only", rule_version=RULE_VERSION),
                "scene_definition": definition,
                "scene_key": scene,
                "worker_id": worker,
                "n_tasks": len(rows),
                "n_positive_difficulty": positive,
                "n_nonacceptable_model_issue": issue,
                "mean_geometry_loo_similarity": sum(geometry_values) / len(geometry_values) if geometry_values else "",
                "scene_profile_candidate": "supported" if len(rows) >= 2 else "insufficient_support",
                "scene_profile_primary": "false",
                "routing_eligible": "false",
            }
        )
    pivotality_rows = []
    for profile in profile_rows:
        same_scene = [row for row in profile_rows if row["scene_definition"] == profile["scene_definition"] and row["scene_key"] == profile["scene_key"]]
        all_tasks = sum(int(row["n_tasks"]) for row in same_scene)
        without_worker = all_tasks - int(profile["n_tasks"])
        pivotality_rows.append(
            {
                **{key: profile.get(key, "") for key in COMMON_SIDEcar_FIELDS},
                "scene_definition": profile["scene_definition"],
                "scene_key": profile["scene_key"],
                "worker_id": profile["worker_id"],
                "all_worker_task_count": all_tasks,
                "without_worker_task_count": without_worker,
                "support_gap_if_removed": int(profile["n_tasks"]),
                "pivotality_candidate": "pivotal_candidate" if all_tasks >= 3 and without_worker < 3 else "not_pivotal_candidate",
                "interpretation_allowed": "false",
            }
        )
    sensitivity_rows = []
    for scene in sorted({row["scene_key"] for row in profile_rows}):
        definitions = [row for row in profile_rows if row["scene_key"] == scene]
        workers_by_definition = {
            definition: {item["worker_id"] for item in definitions if item["scene_definition"] == definition}
            for definition in scene_definitions
        }
        counts = {definition: sum(row["n_tasks"] for row in definitions if row["scene_definition"] == definition) for definition in scene_definitions}
        sensitivity_rows.append(
            {
                **sidecar_common(source_artifact=str(quality_csv), source_sha256=source_sha, validity_status="dry_run" if input_status != "formal" else "candidate_only", rule_version=RULE_VERSION),
                "scene_key": scene,
                "definition_task_counts_json": json.dumps(counts, ensure_ascii=False, sort_keys=True),
                "definition_worker_sets_json": json.dumps({key: sorted(value) for key, value in workers_by_definition.items()}, ensure_ascii=False, sort_keys=True),
                "scene_definition_sensitivity_candidate": "sensitive_candidate" if len({value for value in counts.values() if value}) > 1 else "stable_candidate",
                "interpretation_allowed": "false",
            }
        )
    gap_rows = []
    for profile in profile_rows:
        if profile["scene_profile_candidate"] != "insufficient_support":
            continue
        gap_rows.append(
            {
                **{key: profile.get(key, "") for key in COMMON_SIDEcar_FIELDS},
                "scene_definition": profile["scene_definition"],
                "scene_key": profile["scene_key"],
                "worker_id": profile["worker_id"],
                "observed_support": profile["n_tasks"],
                "minimum_candidate_support": 2,
                "support_gap": max(0, 2 - int(profile["n_tasks"])),
                "support_gap_candidate_status": "candidate_gap",
                "routing_eligible": "false",
                "interpretation_allowed": "false",
            }
        )
    fields = COMMON_SIDEcar_FIELDS
    write_csv_rows(output_dir / "worker_scene_profile_candidates_C1.csv", profile_rows, fields + ["scene_definition", "scene_key", "worker_id", "n_tasks", "n_positive_difficulty", "n_nonacceptable_model_issue", "mean_geometry_loo_similarity", "scene_profile_candidate", "scene_profile_primary", "routing_eligible"])
    write_csv_rows(output_dir / "worker_scene_pivotality_C1.csv", pivotality_rows, fields + ["scene_definition", "scene_key", "worker_id", "all_worker_task_count", "without_worker_task_count", "support_gap_if_removed", "pivotality_candidate"])
    write_csv_rows(output_dir / "scene_definition_sensitivity_C1.csv", sensitivity_rows, fields + ["scene_key", "definition_task_counts_json", "definition_worker_sets_json", "scene_definition_sensitivity_candidate"])
    write_csv_rows(output_dir / "worker_scene_support_gap_candidates_C1.csv", gap_rows, fields + ["scene_definition", "scene_key", "worker_id", "observed_support", "minimum_candidate_support", "support_gap", "support_gap_candidate_status", "routing_eligible"])
    return {"n_profile_rows": len(profile_rows), "n_pivotality_rows": len(pivotality_rows), "n_sensitivity_rows": len(sensitivity_rows), "n_gap_rows": len(gap_rows), "dry_run": input_status != "formal", "interpretation_allowed": False}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Materialize candidate-only worker scene profiles.")
    parser.add_argument("--quality-csv", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--geometry-loo-csv", type=Path)
    args = parser.parse_args(argv)
    print(json.dumps(materialize_worker_scene_profile_candidates(args.quality_csv, args.output_dir, geometry_loo_csv=args.geometry_loo_csv), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
