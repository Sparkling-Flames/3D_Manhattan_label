from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any

_PROJECT_ROOT = Path(__file__).resolve().parents[3]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from tools.thesis_main.analysis.c1_live_collection_monitor import read_csv, safe, truthy, write_csv, write_json

DEFAULT_OUTPUT_DIR = Path("analysis_results/calibration_c1_closeout")

CI_FIELDS = ["worker_id", "round_id", "n_calib_completed", "r_u_ci_low", "r_u_ci_high", "r_u_h", "epsilon_r", "needs_c2_ci_fill", "ci_fill_reason"]
SCENE_FIELDS = ["worker_id", "scene_label", "round_id", "n_u_s", "n_u_s_min_candidate", "coverage_gap", "activation_candidate", "needs_c2_scene_fill", "scene_fill_reason"]


def _scene(row: dict[str, str]) -> str:
    return safe(row.get("scene_label") or row.get("base_task_id") or row.get("task_id"))


def build_ci_rows(worker_rows: list[dict[str, str]], epsilon_r: float, min_calib: int) -> list[dict[str, Any]]:
    out = []
    for row in worker_rows:
        n = int(float(safe(row.get("n_calib_completed")) or 0))
        needs = truthy(row.get("needs_c2_ci_fill")) or n < min_calib or not safe(row.get("r_u_ci_low")) or not safe(row.get("r_u_ci_high"))
        out.append(
            {
                "worker_id": safe(row.get("worker_id")),
                "round_id": "C1",
                "n_calib_completed": n,
                "r_u_ci_low": safe(row.get("r_u_ci_low")),
                "r_u_ci_high": safe(row.get("r_u_ci_high")),
                "r_u_h": safe(row.get("r_u_h")),
                "epsilon_r": epsilon_r,
                "needs_c2_ci_fill": needs,
                "ci_fill_reason": "insufficient_c1_reliability_support" if needs else "",
            }
        )
    return out


def build_scene_rows(quality_rows: list[dict[str, str]], worker_rows: list[dict[str, str]], min_scene: int) -> list[dict[str, Any]]:
    workers = sorted({safe(row.get("worker_id")) for row in worker_rows if safe(row.get("worker_id"))} | {safe(row.get("worker_id")) for row in quality_rows if safe(row.get("worker_id"))})
    scenes = sorted({_scene(row) for row in quality_rows if _scene(row)})
    counts = Counter((safe(row.get("worker_id")), _scene(row)) for row in quality_rows if truthy(row.get("used_for_r_u")) and _scene(row))
    out = []
    for worker in workers:
        for scene in scenes:
            n = counts[(worker, scene)]
            gap = max(0, min_scene - n)
            out.append(
                {
                    "worker_id": worker,
                    "scene_label": scene,
                    "round_id": "C1",
                    "n_u_s": n,
                    "n_u_s_min_candidate": min_scene,
                    "coverage_gap": gap,
                    "activation_candidate": n >= min_scene,
                    "needs_c2_scene_fill": gap > 0,
                    "scene_fill_reason": "below_candidate_scene_support" if gap > 0 else "",
                }
            )
    return out


def materialize(quality_csv: Path, worker_state_csv: Path, output_dir: Path, min_scene: int, min_calib: int, epsilon_r: float) -> dict[str, Any]:
    quality_rows = read_csv(quality_csv)
    worker_rows = read_csv(worker_state_csv)
    ci_rows = build_ci_rows(worker_rows, epsilon_r, min_calib)
    scene_rows = build_scene_rows(quality_rows, worker_rows, min_scene)
    write_csv(output_dir / "ci_precision_audit_C1.csv", ci_rows, CI_FIELDS)
    write_csv(output_dir / "scene_coverage_gap_C1.csv", scene_rows, SCENE_FIELDS)
    summary = {
        "ci_precision_audit_csv": str(output_dir / "ci_precision_audit_C1.csv"),
        "scene_coverage_gap_csv": str(output_dir / "scene_coverage_gap_C1.csv"),
        "n_ci_fill_workers": sum(truthy(row["needs_c2_ci_fill"]) for row in ci_rows),
        "n_scene_fill_cells": sum(truthy(row["needs_c2_scene_fill"]) for row in scene_rows),
        "direct_assignment": False,
    }
    write_json(output_dir / "c2_gap_audits_C1.summary.json", summary)
    return summary


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Materialize C1 provisional C2 gap audits only.")
    parser.add_argument("--quality-csv", type=Path, default=DEFAULT_OUTPUT_DIR / "c1_quality_annotations.csv")
    parser.add_argument("--worker-state-csv", type=Path, default=DEFAULT_OUTPUT_DIR / "worker_state_snapshot_C1.csv")
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--min-scene-support", type=int, default=1)
    parser.add_argument("--min-calib", type=int, default=5)
    parser.add_argument("--epsilon-r", type=float, default=0.15)
    args = parser.parse_args(argv)
    print(json.dumps(materialize(args.quality_csv, args.worker_state_csv, args.output_dir, args.min_scene_support, args.min_calib, args.epsilon_r), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
