from __future__ import annotations

import argparse
import csv
import json
from collections import defaultdict
from pathlib import Path
from typing import Any

from tools.thesis_main.analysis.vfinal_artifact_utils import COMMON_SIDEcar_FIELDS, sha256_file, sidecar_common, write_csv_rows


RULE_VERSION = "worker_scene_profile_candidate_v2"


def _rows(path: Path | None) -> list[dict[str, str]]:
    if path is None or not path.exists():
        return []
    with path.open("r", newline="", encoding="utf-8-sig") as handle:
        return list(csv.DictReader(handle))


def materialize_worker_scene_profile_candidates(task_tag_observations_csv: Path, output_dir: Path, *, geometry_loo_csv: Path | None = None) -> dict[str, Any]:
    observations = _rows(task_tag_observations_csv)
    summaries = _rows(task_tag_observations_csv.with_name("task_tag_three_state_summary_C1.csv"))
    summary_by_tag = {(row.get("task_id", ""), row.get("tag_family", ""), row.get("tag_name", "")): row for row in summaries}
    geometry = {(row.get("base_task_id", ""), row.get("worker_id", "")): row for row in _rows(geometry_loo_csv)}
    grouped: dict[tuple[str, str, str, str], list[dict[str, str]]] = defaultdict(list)
    missing_scene = 0
    for row in observations:
        scene_id = str(row.get("scene_id", "")).strip()
        if not scene_id:
            missing_scene += 1
            continue
        grouped[(row.get("worker_id", ""), scene_id, row.get("tag_family", ""), row.get("tag_name", ""))].append(row)
    profiles = []
    for (worker_id, scene_id, family, tag), rows in sorted(grouped.items()):
        legal = [row for row in rows if row.get("assertion") != "NA"]
        states = [summary_by_tag.get((row.get("task_id", ""), family, tag), {}).get("task_tag_state", "none_observed") for row in legal]
        loo = [geometry.get((row.get("base_task_id", ""), worker_id), {}) for row in legal]
        valid_loo = [row for row in loo if row.get("validity_status") == "candidate_only"]
        first = rows[0]
        profiles.append({
            **sidecar_common(source_artifact=str(task_tag_observations_csv), source_sha256=sha256_file(task_tag_observations_csv), stage="C1", pool=first.get("dataset_group", ""), condition=first.get("condition", ""), validity_status="dry_run", rule_version=RULE_VERSION, interpretation_allowed=False),
            "worker_id": worker_id, "scene_id": scene_id, "tag_family": family, "tag_name": tag,
            "n_legal_tasks": len({row.get("task_id", "") for row in legal}), "n_positive": sum(row.get("assertion") == "+" for row in legal), "n_negative": sum(row.get("assertion") == "-" for row in legal), "n_unasserted": sum(row.get("assertion") == "0" for row in legal),
            "n_task_broad": sum(state in {"convergent_positive", "high_replication_positive"} for state in states), "n_task_strict": sum(state == "high_replication_positive" for state in states), "n_task_conflict": sum(state == "replicated_explicit_conflict" for state in states),
            "geometry_loo_valid_k": len(valid_loo), "geometry_loo_boundary_values_json": json.dumps([row.get("loo_boundary_median") for row in valid_loo]), "geometry_loo_wallwall_values_json": json.dumps([row.get("loo_wallwall_median") for row in valid_loo]),
            "scene_profile_candidate": "strict" if any(state == "high_replication_positive" for state in states) else "broad" if any(state == "convergent_positive" for state in states) else "descriptive" if any(row.get("assertion") == "+" for row in legal) else "none",
            "profile_geometry_status": "eligible_diagnostic" if valid_loo else "fallback_global_reliability", "scene_profile_primary": "false", "routing_eligible": "false", "c2_freeze_required": "true",
        })
    fields = COMMON_SIDEcar_FIELDS + ["worker_id", "scene_id", "tag_family", "tag_name", "n_legal_tasks", "n_positive", "n_negative", "n_unasserted", "n_task_broad", "n_task_strict", "n_task_conflict", "geometry_loo_valid_k", "geometry_loo_boundary_values_json", "geometry_loo_wallwall_values_json", "scene_profile_candidate", "profile_geometry_status", "scene_profile_primary", "routing_eligible", "c2_freeze_required"]
    write_csv_rows(output_dir / "worker_scene_profile_candidates_C1.csv", profiles, fields)
    return {"n_profile_rows": len(profiles), "n_missing_scene_rows": missing_scene, "dry_run": True, "interpretation_allowed": False, "routing_eligible": False}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Materialize candidate-only worker-scene-tag profiles.")
    parser.add_argument("--task-tag-observations-csv", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--geometry-loo-csv", type=Path)
    args = parser.parse_args(argv)
    print(json.dumps(materialize_worker_scene_profile_candidates(args.task_tag_observations_csv, args.output_dir, geometry_loo_csv=args.geometry_loo_csv), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
