from __future__ import annotations

import argparse
import csv
import json
import math
from collections import defaultdict
from pathlib import Path
from typing import Any

from tools.thesis_main.analysis.vfinal_artifact_utils import COMMON_SIDEcar_FIELDS, sha256_file, sidecar_common, write_csv_rows


RULE_VERSION = "worker_scene_profile_candidate_v3"


def _rows(path: Path | None) -> list[dict[str, str]]:
    if path is None or not path.exists():
        return []
    with path.open("r", newline="", encoding="utf-8-sig") as handle:
        return list(csv.DictReader(handle))


def _bool(value: Any) -> bool:
    return str(value).strip().lower() == "true"


def _wilson(successes: int, total: int) -> tuple[float, float]:
    if not total:
        return 0.0, 0.0
    z = 1.959963984540054
    p = successes / total
    denominator = 1 + z * z / total
    centre = (p + z * z / (2 * total)) / denominator
    radius = z * math.sqrt(p * (1 - p) / total + z * z / (4 * total * total)) / denominator
    return max(0.0, centre - radius), min(1.0, centre + radius)


def materialize_worker_scene_profile_candidates(
    task_tag_observations_csv: Path,
    output_dir: Path,
    *,
    geometry_loo_csv: Path | None = None,
    input_status: str = "dry_run",
    min_task_support: int = 2,
) -> dict[str, Any]:
    observations = _rows(task_tag_observations_csv)
    summaries = _rows(task_tag_observations_csv.with_name("task_tag_three_state_summary_C1.csv"))
    summary_by_tag = {(row.get("task_id", ""), row.get("tag_family", ""), row.get("tag_name", "")): row for row in summaries}
    geometry = {(row.get("base_task_id", ""), row.get("condition", ""), row.get("worker_id", ""), row.get("geometry_context_provenance", "")): row for row in _rows(geometry_loo_csv)}
    grouped: dict[tuple[str, str, str, str, str], list[dict[str, str]]] = defaultdict(list)
    missing_scene = 0
    scene_candidates: dict[str, set[str]] = defaultdict(set)
    for row in observations:
        scene_id = str(row.get("scene_id", "")).strip()
        base_task_id = str(row.get("base_task_id", "")).strip()
        if scene_id and base_task_id:
            scene_candidates[base_task_id].add(scene_id)
    ambiguous_bases = {base for base, scenes in scene_candidates.items() if len(scenes) != 1}
    for row in observations:
        scene_id = str(row.get("scene_id", "")).strip()
        base_task_id = str(row.get("base_task_id", "")).strip()
        mapping_status = str(row.get("scene_mapping_status", "")).strip().lower()
        if not scene_id or base_task_id in ambiguous_bases or mapping_status in {"invalid", "ambiguous", "unverified"} or (scene_id in {str(row.get("task_id", "")).strip(), base_task_id} and not _bool(row.get("scene_mapping_verified"))):
            missing_scene += 1
            continue
        grouped[(row.get("worker_id", ""), scene_id, row.get("tag_family", ""), row.get("tag_name", ""), row.get("condition", ""))].append(row)

    profiles = []
    for (worker_id, scene_id, family, tag, condition), rows in sorted(grouped.items()):
        legal = [row for row in rows if row.get("assertion") != "NA"]
        tasks = {row.get("task_id", "") for row in legal if row.get("task_id", "")}
        worker_positive = [row for row in legal if row.get("assertion") == "+"]
        broad_tasks = {row.get("task_id", "") for row in worker_positive if _bool(summary_by_tag.get((row.get("task_id", ""), family, tag), {}).get("broad"))}
        strict_tasks = {row.get("task_id", "") for row in worker_positive if _bool(summary_by_tag.get((row.get("task_id", ""), family, tag), {}).get("strict"))}
        conflict_tasks = {row.get("task_id", "") for row in legal if _bool(summary_by_tag.get((row.get("task_id", ""), family, tag), {}).get("replicated_explicit_conflict"))}
        broad_low, broad_high = _wilson(len(broad_tasks), len(tasks))
        strict_low, strict_high = _wilson(len(strict_tasks), len(tasks))

        valid_loo = []
        for task_id in tasks:
            row = next(item for item in legal if item.get("task_id") == task_id)
            loo = geometry.get((row.get("base_task_id", ""), row.get("condition", ""), worker_id, row.get("geometry_context_provenance", "")), {})
            if loo.get("validity_status") in {"valid", "dry_run"} and _bool(loo.get("held_out_valid")) and int(loo.get("valid_k") or 0) >= 3:
                valid_loo.append(loo)
        geometry_status = "eligible_diagnostic" if valid_loo else "insufficient_peer_support"
        support_status = "supported" if len(tasks) >= min_task_support else "insufficient_support"
        profiles.append({
            **sidecar_common(source_artifact=str(task_tag_observations_csv), source_sha256=sha256_file(task_tag_observations_csv), stage="C1", pool=rows[0].get("dataset_group", ""), condition=rows[0].get("condition", ""), validity_status="dry_run" if input_status != "formal" else "not_evaluable", rule_version=RULE_VERSION, interpretation_allowed=False, dependency_paths=[task_tag_observations_csv, geometry_loo_csv] if geometry_loo_csv else [task_tag_observations_csv]),
            "worker_id": worker_id, "scene_id": scene_id, "tag_family": family, "tag_name": tag, "condition": condition,
            "n_legal_tasks": len(tasks), "n_positive": len(worker_positive), "n_negative": sum(row.get("assertion") == "-" for row in legal), "n_unasserted": sum(row.get("assertion") == "0" for row in legal),
            "n_task_broad": len(broad_tasks), "n_task_strict": len(strict_tasks), "n_task_conflict": len(conflict_tasks),
            "broad_ci_low": round(broad_low, 6), "broad_ci_high": round(broad_high, 6), "strict_ci_low": round(strict_low, 6), "strict_ci_high": round(strict_high, 6),
            "broad_lcb95": round(broad_low, 6), "strict_lcb95": round(strict_low, 6), "broad_strict_concordance": round(len(strict_tasks) / len(broad_tasks), 6) if broad_tasks else "",
            "geometry_loo_valid_k": len(valid_loo), "geometry_loo_boundary_values_json": json.dumps([row.get("loo_boundary_median") for row in valid_loo]), "geometry_loo_wallwall_values_json": json.dumps([row.get("loo_wallwall_median") for row in valid_loo]),
            "scene_profile_candidate": "supported_evidence_inventory" if support_status == "supported" else "insufficient_support",
            "support_status": support_status, "profile_geometry_status": geometry_status, "fallback": "geometry_diagnostic_only" if valid_loo else "global_reliability",
            "artifact_role": "worker_scene_evidence_inventory", "scene_profile_primary": "false", "routing_eligible": "false", "interpretation_allowed": "false", "c2_freeze_required": "true",
        })
    fields = COMMON_SIDEcar_FIELDS + ["worker_id", "scene_id", "tag_family", "tag_name", "condition", "n_legal_tasks", "n_positive", "n_negative", "n_unasserted", "n_task_broad", "n_task_strict", "n_task_conflict", "broad_ci_low", "broad_ci_high", "strict_ci_low", "strict_ci_high", "broad_lcb95", "strict_lcb95", "broad_strict_concordance", "geometry_loo_valid_k", "geometry_loo_boundary_values_json", "geometry_loo_wallwall_values_json", "scene_profile_candidate", "support_status", "profile_geometry_status", "fallback", "artifact_role", "scene_profile_primary", "routing_eligible", "interpretation_allowed", "c2_freeze_required"]
    write_csv_rows(output_dir / "worker_scene_profile_candidates_C1.csv", profiles, fields)
    return {"n_profile_rows": len(profiles), "n_missing_scene_rows": missing_scene, "dry_run": input_status != "formal", "interpretation_allowed": False, "routing_eligible": False}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Materialize candidate-only worker-scene-tag evidence inventories.")
    parser.add_argument("--task-tag-observations-csv", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--geometry-loo-csv", type=Path)
    parser.add_argument("--input-status", choices=("dry_run", "formal"), default="dry_run")
    parser.add_argument("--min-task-support", type=int, default=2)
    args = parser.parse_args(argv)
    print(json.dumps(materialize_worker_scene_profile_candidates(args.task_tag_observations_csv, args.output_dir, geometry_loo_csv=args.geometry_loo_csv, input_status=args.input_status, min_task_support=args.min_task_support), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
