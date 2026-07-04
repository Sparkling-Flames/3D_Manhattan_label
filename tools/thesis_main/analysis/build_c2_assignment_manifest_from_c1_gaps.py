from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

_PROJECT_ROOT = Path(__file__).resolve().parents[3]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from tools.thesis_main.analysis.c1_live_collection_monitor import read_csv, safe, truthy, write_csv, write_json

DEFAULT_REBUILD_DIR = Path("analysis_results/calibration_rebuild_20260702")
DEFAULT_OUTPUT_DIR = Path("analysis_results/calibration_c2_draft")

MANIFEST_FIELDS = ["round_id", "worker_id", "task_id", "base_task_id", "dataset_group", "assignment_batch", "fill_type", "fill_reason", "manifest_version"]
AUDIT_FIELDS = ["worker_id", "fill_type", "n_reserve_tasks_assigned", "reserve_capacity_shortfall", "trigger_metric", "trigger_threshold", "task_side_pool_modified", "reserve_misuse_flag"]


def _reserve_rows(path: Path) -> list[dict[str, str]]:
    rows = read_csv(path)
    return [row for row in rows if safe(row.get("dataset_group") or row.get("calibration_split")) in {"Calibration_reserve", "reserve"} or safe(row.get("calibration_split")) == "reserve"]


def _needs_ci(rows: list[dict[str, str]]) -> list[tuple[str, str]]:
    return [(safe(row.get("worker_id")), safe(row.get("ci_fill_reason")) or "insufficient_c1_reliability_support") for row in rows if truthy(row.get("needs_c2_ci_fill"))]


def _needs_scene(rows: list[dict[str, str]]) -> list[tuple[str, str]]:
    out = []
    for row in rows:
        if truthy(row.get("needs_c2_scene_fill")):
            reason = safe(row.get("scene_fill_reason")) or f"scene_gap:{safe(row.get('scene_label'))}"
            out.append((safe(row.get("worker_id")), reason))
    return out


def build_manifest(reserve_pool: Path, ci_audit: Path, scene_gap: Path, tasks_per_fill: int) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    reserve = _reserve_rows(reserve_pool)
    if not reserve:
        return [], []
    requests = [("ci_precision_fill", worker, reason) for worker, reason in _needs_ci(read_csv(ci_audit))]
    requests += [("scene_coverage_fill", worker, reason) for worker, reason in _needs_scene(read_csv(scene_gap))]

    used_by_worker: dict[str, set[tuple[str, str]]] = defaultdict(set)
    manifest: list[dict[str, Any]] = []
    audit_counts: dict[tuple[str, str], int] = defaultdict(int)
    shortfall: dict[tuple[str, str], int] = defaultdict(int)
    misuse: dict[tuple[str, str], bool] = defaultdict(bool)
    for fill_type, worker, reason in requests:
        if not worker:
            continue
        for _ in range(tasks_per_fill):
            row = next(
                (
                    candidate
                    for candidate in reserve
                    if (safe(candidate.get("task_id")), safe(candidate.get("base_task_id")) or safe(candidate.get("task_id"))) not in used_by_worker[worker]
                ),
                None,
            )
            if row is None:
                shortfall[(worker, fill_type)] += 1
                continue
            is_reserve = safe(row.get("calibration_split")) == "reserve" or safe(row.get("dataset_group")) == "Calibration_reserve"
            misuse[(worker, fill_type)] = misuse[(worker, fill_type)] or not is_reserve
            key = (safe(row.get("task_id")), safe(row.get("base_task_id")) or safe(row.get("task_id")))
            used_by_worker[worker].add(key)
            manifest.append(
                {
                    "round_id": "C2",
                    "worker_id": worker,
                    "task_id": safe(row.get("task_id")),
                    "base_task_id": safe(row.get("base_task_id")) or safe(row.get("task_id")),
                    "dataset_group": "Calibration_reserve",
                    "assignment_batch": "C2_reserve_draft",
                    "fill_type": fill_type,
                    "fill_reason": reason,
                    "manifest_version": "C2_draft_from_C1_gaps_v1",
                }
            )
            audit_counts[(worker, fill_type)] += 1

    audit = []
    for worker, fill_type in sorted(set(audit_counts) | set(shortfall)):
        audit.append(
            {
                "worker_id": worker,
                "fill_type": fill_type,
                "n_reserve_tasks_assigned": audit_counts[(worker, fill_type)],
                "reserve_capacity_shortfall": shortfall[(worker, fill_type)],
                "trigger_metric": "needs_c2_ci_fill" if fill_type == "ci_precision_fill" else "needs_c2_scene_fill",
                "trigger_threshold": "true",
                "task_side_pool_modified": False,
                "reserve_misuse_flag": misuse[(worker, fill_type)],
            }
        )
    return manifest, audit


def materialize(reserve_pool: Path, ci_audit: Path, scene_gap: Path, output_dir: Path, tasks_per_fill: int) -> dict[str, Any]:
    manifest, audit = build_manifest(reserve_pool, ci_audit, scene_gap, tasks_per_fill)
    manifest_csv = output_dir / "assignment_manifest_C2_draft.csv"
    audit_csv = output_dir / "reserve_usage_audit_C2_draft.csv"
    write_csv(manifest_csv, manifest, MANIFEST_FIELDS)
    write_csv(audit_csv, audit, AUDIT_FIELDS)
    summary = {
        "assignment_manifest_C2_draft": str(manifest_csv),
        "reserve_usage_audit_C2_draft": str(audit_csv),
        "n_assignments": len(manifest),
        "reserve_capacity_shortfall_count": sum(int(row["reserve_capacity_shortfall"]) for row in audit),
        "reserve_only": all(not truthy(row["reserve_misuse_flag"]) for row in audit),
        "draft_only": True,
    }
    write_json(output_dir / "assignment_manifest_C2_draft.summary.json", summary)
    return summary


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build reserve-only C2 draft assignment manifest from C1 gap audits.")
    parser.add_argument("--reserve-pool-csv", type=Path, default=DEFAULT_REBUILD_DIR / "calibration_reserve_draft_v3_1.csv")
    parser.add_argument("--ci-audit-csv", type=Path, required=True)
    parser.add_argument("--scene-gap-csv", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--tasks-per-fill", type=int, default=1)
    args = parser.parse_args(argv)
    print(json.dumps(materialize(args.reserve_pool_csv, args.ci_audit_csv, args.scene_gap_csv, args.output_dir, args.tasks_per_fill), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
