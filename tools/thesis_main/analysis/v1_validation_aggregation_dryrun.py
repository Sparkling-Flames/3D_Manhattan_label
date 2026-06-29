from __future__ import annotations

import argparse
import csv
import json
from collections import defaultdict
from pathlib import Path
from typing import Any

DEFAULT_T1_DIR = Path("analysis_results/pipeline_smoke/t1_main_dryrun")
DEFAULT_C1_DIR = Path("analysis_results/pipeline_smoke/c1_metric_dryrun")
DEFAULT_OUTPUT_DIR = Path("analysis_results/pipeline_smoke/v1_validation_dryrun")

WORKER_FIELDS = [
    "annotator_id",
    "included_for_smoke_preview",
    "has_scope_preview_rows",
    "has_geometry_preview_rows",
    "n_scope_preview_rows",
    "n_geometry_preview_rows",
    "dry_run",
    "provisional_only",
]

TASK_FIELDS = [
    "task_id",
    "dataset_group",
    "condition",
    "has_scope_preview_rows",
    "has_geometry_preview_rows",
    "n_scope_preview_rows",
    "n_geometry_preview_rows",
    "dry_run",
    "provisional_only",
]

CONDITION_FIELDS = [
    "dataset_group",
    "condition",
    "n_tasks",
    "n_tasks_with_scope_preview_rows",
    "n_tasks_with_geometry_preview_rows",
    "n_scope_preview_rows",
    "n_geometry_preview_rows",
    "dry_run",
    "provisional_only",
]


def _safe(value: Any) -> str:
    return str(value or "").strip()


def _truthy(value: Any) -> bool:
    return _safe(value).lower() in {"1", "true", "yes", "y"}


def _int(value: Any) -> int:
    try:
        return int(_safe(value))
    except ValueError:
        return 0


def _load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"missing required input: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def _load_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        raise FileNotFoundError(f"missing required input: {path}")
    with path.open("r", newline="", encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _write_csv(path: Path, fields: list[str], rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def build_v1_validation_dryrun(t1_dir: Path = DEFAULT_T1_DIR, c1_dir: Path = DEFAULT_C1_DIR) -> tuple[dict[str, Any], list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    t1_root = Path(t1_dir)
    c1_root = Path(c1_dir)
    t1_state = _load_json(t1_root / "t1_main_dryrun_state.json")
    c1_state = _load_json(c1_root / "c1_calibration_metric_dryrun_state.json")
    if t1_state.get("formal_main_allowed") is True:
        raise ValueError("formal_main_allowed=true is not allowed for validation dry-run")
    if t1_state.get("main_dryrun_only") is not True:
        raise ValueError("main_dryrun_only=true is required for validation dry-run")
    if c1_state.get("formal_c1_allowed") is True:
        raise ValueError("formal_c1_allowed=true is not allowed for validation dry-run")

    workers_in = _load_csv(t1_root / "t1_worker_coverage_dryrun.csv")
    tasks_in = _load_csv(t1_root / "t1_task_coverage_dryrun.csv")
    _load_csv(t1_root / "t1_condition_coverage_dryrun.csv")
    _load_csv(c1_root / "c1_worker_metric_dryrun.csv")
    _load_csv(c1_root / "c1_task_metric_dryrun.csv")

    worker_rows = []
    for row in workers_in:
        scope_n = _int(row.get("n_scope_preview_rows"))
        geom_n = _int(row.get("n_geometry_preview_rows"))
        worker_rows.append(
            {
                "annotator_id": _safe(row.get("annotator_id")),
                "included_for_smoke_preview": _truthy(row.get("included_for_smoke_preview")),
                "has_scope_preview_rows": scope_n > 0,
                "has_geometry_preview_rows": geom_n > 0,
                "n_scope_preview_rows": scope_n,
                "n_geometry_preview_rows": geom_n,
                "dry_run": True,
                "provisional_only": True,
            }
        )
    task_rows = []
    grouped: dict[tuple[str, str], dict[str, int]] = defaultdict(lambda: defaultdict(int))
    for row in tasks_in:
        scope_n = _int(row.get("n_scope_preview_rows"))
        geom_n = _int(row.get("n_geometry_preview_rows"))
        dataset_group = _safe(row.get("dataset_group"))
        condition = _safe(row.get("condition"))
        task_rows.append(
            {
                "task_id": _safe(row.get("task_id")),
                "dataset_group": dataset_group,
                "condition": condition,
                "has_scope_preview_rows": scope_n > 0,
                "has_geometry_preview_rows": geom_n > 0,
                "n_scope_preview_rows": scope_n,
                "n_geometry_preview_rows": geom_n,
                "dry_run": True,
                "provisional_only": True,
            }
        )
        key = (dataset_group, condition)
        grouped[key]["n_tasks"] += 1
        grouped[key]["n_tasks_with_scope_preview_rows"] += int(scope_n > 0)
        grouped[key]["n_tasks_with_geometry_preview_rows"] += int(geom_n > 0)
        grouped[key]["n_scope_preview_rows"] += scope_n
        grouped[key]["n_geometry_preview_rows"] += geom_n

    condition_rows = [
        {
            "dataset_group": dataset_group,
            "condition": condition,
            "n_tasks": values["n_tasks"],
            "n_tasks_with_scope_preview_rows": values["n_tasks_with_scope_preview_rows"],
            "n_tasks_with_geometry_preview_rows": values["n_tasks_with_geometry_preview_rows"],
            "n_scope_preview_rows": values["n_scope_preview_rows"],
            "n_geometry_preview_rows": values["n_geometry_preview_rows"],
            "dry_run": True,
            "provisional_only": True,
        }
        for (dataset_group, condition), values in sorted(grouped.items())
    ]
    state = {
        "dry_run": True,
        "provisional_only": True,
        "validation_dryrun_only": True,
        "formal_validation_allowed": False,
        "t1_main_available": True,
        "c1_metric_available": True,
        "n_workers_total": t1_state.get("n_workers_total", len(worker_rows)),
        "n_workers_with_scope_preview_rows": sum(bool(row["has_scope_preview_rows"]) for row in worker_rows),
        "n_tasks_total": t1_state.get("n_tasks_total", len(task_rows)),
        "n_tasks_with_scope_preview_rows": sum(bool(row["has_scope_preview_rows"]) for row in task_rows),
        "n_conditions": len(condition_rows),
        "not_for_thesis_claim": True,
        "blocked_reasons": t1_state.get("blocked_reasons") or c1_state.get("blocked_reasons") or [],
    }
    return state, worker_rows, task_rows, condition_rows


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--t1-dir", default=str(DEFAULT_T1_DIR))
    parser.add_argument("--c1-dir", default=str(DEFAULT_C1_DIR))
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    args = parser.parse_args(argv)
    out = Path(args.output_dir)
    state, workers, tasks, conditions = build_v1_validation_dryrun(Path(args.t1_dir), Path(args.c1_dir))
    _write_json(out / "v1_validation_dryrun_state.json", state)
    _write_csv(out / "v1_worker_validation_coverage_dryrun.csv", WORKER_FIELDS, workers)
    _write_csv(out / "v1_task_validation_coverage_dryrun.csv", TASK_FIELDS, tasks)
    _write_csv(out / "v1_condition_validation_coverage_dryrun.csv", CONDITION_FIELDS, conditions)
    print(json.dumps(state, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
