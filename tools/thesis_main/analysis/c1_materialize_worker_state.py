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
DEFAULT_QUALITY = DEFAULT_OUTPUT_DIR / "c1_quality_annotations.csv"

FIELDS = [
    "worker_id",
    "round_id",
    "admission_status",
    "r0_prescreen",
    "w_max_locked",
    "n_anchor_completed",
    "n_core_completed",
    "n_calib_completed",
    "r_u_hat",
    "r_u_ci_low",
    "r_u_ci_high",
    "r_u_h",
    "needs_c2_ci_fill",
    "needs_c2_scene_fill",
    "worker_state_version",
    "blind_trust_pre_flag",
    "notes",
]


def _assignment_workers(paths: list[Path]) -> set[str]:
    workers: set[str] = set()
    for path in paths:
        workers.update(safe(row.get("worker_id")) for row in read_csv(path) if safe(row.get("worker_id")))
    return workers


def build_worker_state(quality_rows: list[dict[str, str]], assignment_paths: list[Path], min_r_u_tasks: int) -> list[dict[str, Any]]:
    workers = _assignment_workers(assignment_paths) | {safe(row.get("worker_id")) for row in quality_rows if safe(row.get("worker_id"))}
    by_worker: dict[str, list[dict[str, str]]] = {worker: [] for worker in workers}
    for row in quality_rows:
        by_worker.setdefault(safe(row.get("worker_id")), []).append(row)

    out: list[dict[str, Any]] = []
    for worker in sorted(workers):
        rows = by_worker.get(worker, [])
        anchor = sum(row.get("dataset_group") == "Calibration_anchor" for row in rows)
        core = sum(row.get("dataset_group") == "Calibration_core" for row in rows)
        calib = sum(truthy(row.get("used_for_r_u")) for row in rows)
        out.append(
            {
                "worker_id": worker,
                "round_id": "C1",
                "admission_status": "provisional_from_assignment_manifest",
                "r0_prescreen": "",
                "w_max_locked": "",
                "n_anchor_completed": anchor,
                "n_core_completed": core,
                "n_calib_completed": calib,
                "r_u_hat": "",
                "r_u_ci_low": "",
                "r_u_ci_high": "",
                "r_u_h": "",
                "needs_c2_ci_fill": calib < min_r_u_tasks,
                "needs_c2_scene_fill": False,
                "worker_state_version": "C1_provisional_no_r_u_estimate_v1",
                "blind_trust_pre_flag": "",
                "notes": "semi_excluded_from_r_u;used_for_r_u_false_core_excluded",
            }
        )
    return out


def materialize(quality_csv: Path, assignments: list[Path], output_dir: Path, min_r_u_tasks: int) -> dict[str, Any]:
    rows = build_worker_state(read_csv(quality_csv), assignments, min_r_u_tasks)
    out_csv = output_dir / "worker_state_snapshot_C1.csv"
    write_csv(out_csv, rows, FIELDS)
    summary = {
        "worker_state_csv": str(out_csv),
        "n_workers": len(rows),
        "min_r_u_tasks_for_ci_fill": min_r_u_tasks,
        "n_needs_c2_ci_fill": sum(truthy(row["needs_c2_ci_fill"]) for row in rows),
        "r_u_estimated": False,
        "provisional": True,
    }
    write_json(output_dir / "worker_state_snapshot_C1.summary.json", summary)
    return summary


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Materialize provisional C1 worker state without estimating r_u.")
    parser.add_argument("--quality-csv", type=Path, default=DEFAULT_QUALITY)
    parser.add_argument("--assignment-manifest", action="append", required=True, type=Path)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--min-r-u-tasks", type=int, default=5)
    args = parser.parse_args(argv)
    print(json.dumps(materialize(args.quality_csv, args.assignment_manifest, args.output_dir, args.min_r_u_tasks), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
