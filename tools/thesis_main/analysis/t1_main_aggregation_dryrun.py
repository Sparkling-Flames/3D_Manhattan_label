from __future__ import annotations

import argparse
import csv
import json
from collections import defaultdict
from pathlib import Path
from typing import Any

DEFAULT_METRIC_DIR = Path("analysis_results/pipeline_smoke/c1_metric_dryrun")
DEFAULT_PREVIEW_DIR = Path("analysis_results/pipeline_smoke/c1_calibration_preview")
DEFAULT_OUTPUT_DIR = Path("analysis_results/pipeline_smoke/t1_main_dryrun")

WORKER_FIELDS = [
    "annotator_id",
    "included_for_smoke_preview",
    "n_scope_preview_rows",
    "n_geometry_preview_rows",
    "n_geometry_present_rows",
    "dry_run",
    "provisional_only",
]

TASK_FIELDS = [
    "task_id",
    "dataset_group",
    "condition",
    "task_usable_for_scope_preview",
    "task_usable_for_geometry_preview",
    "n_scope_preview_rows",
    "n_geometry_preview_rows",
    "dry_run",
    "provisional_only",
]

CONDITION_FIELDS = [
    "dataset_group",
    "condition",
    "n_tasks",
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


def build_t1_main_dryrun(metric_dir: Path = DEFAULT_METRIC_DIR, preview_dir: Path = DEFAULT_PREVIEW_DIR) -> tuple[dict[str, Any], list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    metric_root = Path(metric_dir)
    preview_root = Path(preview_dir)
    state_in = _load_json(metric_root / "c1_calibration_metric_dryrun_state.json")
    if state_in.get("formal_c1_allowed") is True:
        raise ValueError("formal_c1_allowed=true is not allowed for T1 main dry-run")
    if state_in.get("metric_dryrun_only") is not True:
        raise ValueError("metric_dryrun_only=true is required for T1 main dry-run")
    workers_in = _load_csv(metric_root / "c1_worker_metric_dryrun.csv")
    tasks_in = _load_csv(metric_root / "c1_task_metric_dryrun.csv")
    _load_csv(preview_root / "c1_response_input_preview.csv")

    worker_rows = [
        {
            "annotator_id": _safe(row.get("annotator_id")),
            "included_for_smoke_preview": _truthy(row.get("included_for_smoke_preview")),
            "n_scope_preview_rows": _int(row.get("n_scope_preview_rows")),
            "n_geometry_preview_rows": _int(row.get("n_geometry_preview_rows")),
            "n_geometry_present_rows": _int(row.get("n_geometry_present_rows")),
            "dry_run": True,
            "provisional_only": True,
        }
        for row in workers_in
    ]
    task_rows = [
        {
            "task_id": _safe(row.get("task_id")),
            "dataset_group": _safe(row.get("dataset_group")),
            "condition": _safe(row.get("condition")),
            "task_usable_for_scope_preview": _truthy(row.get("task_usable_for_scope_preview")),
            "task_usable_for_geometry_preview": _truthy(row.get("task_usable_for_geometry_preview")),
            "n_scope_preview_rows": _int(row.get("n_scope_preview_rows")),
            "n_geometry_preview_rows": _int(row.get("n_geometry_preview_rows")),
            "dry_run": True,
            "provisional_only": True,
        }
        for row in tasks_in
    ]
    grouped: dict[tuple[str, str], dict[str, Any]] = defaultdict(lambda: {"n_tasks": 0, "n_scope_preview_rows": 0, "n_geometry_preview_rows": 0})
    for row in task_rows:
        key = (str(row["dataset_group"]), str(row["condition"]))
        grouped[key]["n_tasks"] += 1
        grouped[key]["n_scope_preview_rows"] += int(row["n_scope_preview_rows"])
        grouped[key]["n_geometry_preview_rows"] += int(row["n_geometry_preview_rows"])
    condition_rows = [
        {
            "dataset_group": dataset_group,
            "condition": condition,
            "n_tasks": values["n_tasks"],
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
        "main_dryrun_only": True,
        "formal_main_allowed": False,
        "c1_metric_available": True,
        "n_workers_total": state_in.get("n_workers_total", len(worker_rows)),
        "n_workers_included_for_smoke_preview": state_in.get("n_workers_included_for_smoke_preview"),
        "n_tasks_total": state_in.get("n_tasks_total", len(task_rows)),
        "n_scope_preview_responses": state_in.get("n_scope_preview_responses"),
        "n_geometry_preview_responses": state_in.get("n_geometry_preview_responses"),
        "n_conditions": len(condition_rows),
        "not_for_thesis_claim": True,
        "blocked_reasons": state_in.get("blocked_reasons") or [],
    }
    return state, worker_rows, task_rows, condition_rows


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--metric-dir", default=str(DEFAULT_METRIC_DIR))
    parser.add_argument("--preview-dir", default=str(DEFAULT_PREVIEW_DIR))
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    args = parser.parse_args(argv)
    out = Path(args.output_dir)
    state, workers, tasks, conditions = build_t1_main_dryrun(Path(args.metric_dir), Path(args.preview_dir))
    _write_json(out / "t1_main_dryrun_state.json", state)
    _write_csv(out / "t1_worker_coverage_dryrun.csv", WORKER_FIELDS, workers)
    _write_csv(out / "t1_task_coverage_dryrun.csv", TASK_FIELDS, tasks)
    _write_csv(out / "t1_condition_coverage_dryrun.csv", CONDITION_FIELDS, conditions)
    print(json.dumps(state, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
