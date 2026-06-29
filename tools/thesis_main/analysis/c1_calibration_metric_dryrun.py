from __future__ import annotations

import argparse
import csv
import json
from collections import defaultdict
from pathlib import Path
from typing import Any

DEFAULT_PREVIEW_DIR = Path("analysis_results/pipeline_smoke/c1_calibration_preview")
DEFAULT_OUTPUT_DIR = Path("analysis_results/pipeline_smoke/c1_metric_dryrun")

WORKER_FIELDS = [
    "annotator_id",
    "language",
    "included_for_smoke_preview",
    "n_scope_preview_rows",
    "n_scope_preview_correct_in_scope",
    "n_scope_preview_correct_oos",
    "n_scope_preview_false_positive",
    "n_scope_preview_false_negative",
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


def _safe(value: Any) -> str:
    return str(value or "").strip()


def _truthy(value: Any) -> bool:
    return _safe(value).lower() in {"1", "true", "yes", "y"}


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


def build_metric_dryrun(preview_dir: Path = DEFAULT_PREVIEW_DIR) -> tuple[dict[str, Any], list[dict[str, Any]], list[dict[str, Any]]]:
    root = Path(preview_dir)
    state_in = _load_json(root / "c1_calibration_preview_state.json")
    if state_in.get("formal_c1_allowed") is True:
        raise ValueError("formal_c1_allowed=true is not allowed for metric dry-run")
    workers_in = _load_csv(root / "c1_worker_input_preview.csv")
    tasks_in = _load_csv(root / "c1_task_input_preview.csv")
    responses = _load_csv(root / "c1_response_input_preview.csv")

    worker_counts: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    task_counts: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    for row in responses:
        worker_ok = _truthy(row.get("worker_included_for_smoke_preview"))
        scope_ok = worker_ok and _truthy(row.get("task_usable_for_scope_preview"))
        geom_ok = worker_ok and _truthy(row.get("task_usable_for_geometry_preview"))
        aid = _safe(row.get("annotator_id"))
        tid = _safe(row.get("task_id"))
        if scope_ok:
            worker_counts[aid]["n_scope_preview_rows"] += 1
            task_counts[tid]["n_scope_preview_rows"] += 1
            key = f"n_scope_preview_{_safe(row.get('worker_scope_response'))}"
            if key in {
                "n_scope_preview_correct_in_scope",
                "n_scope_preview_correct_oos",
                "n_scope_preview_false_positive",
                "n_scope_preview_false_negative",
            }:
                worker_counts[aid][key] += 1
        if geom_ok:
            worker_counts[aid]["n_geometry_preview_rows"] += 1
            task_counts[tid]["n_geometry_preview_rows"] += 1
            if _truthy(row.get("geometry_valid_or_present")):
                worker_counts[aid]["n_geometry_present_rows"] += 1

    worker_rows = []
    for row in workers_in:
        aid = _safe(row.get("annotator_id"))
        counts = worker_counts[aid]
        worker_rows.append(
            {
                "annotator_id": aid,
                "language": _safe(row.get("language")),
                "included_for_smoke_preview": _truthy(row.get("included_for_smoke_preview")),
                "n_scope_preview_rows": counts["n_scope_preview_rows"],
                "n_scope_preview_correct_in_scope": counts["n_scope_preview_correct_in_scope"],
                "n_scope_preview_correct_oos": counts["n_scope_preview_correct_oos"],
                "n_scope_preview_false_positive": counts["n_scope_preview_false_positive"],
                "n_scope_preview_false_negative": counts["n_scope_preview_false_negative"],
                "n_geometry_preview_rows": counts["n_geometry_preview_rows"],
                "n_geometry_present_rows": counts["n_geometry_present_rows"],
                "dry_run": True,
                "provisional_only": True,
            }
        )

    task_rows = []
    for row in tasks_in:
        tid = _safe(row.get("task_id"))
        counts = task_counts[tid]
        task_rows.append(
            {
                "task_id": tid,
                "dataset_group": _safe(row.get("dataset_group")),
                "condition": _safe(row.get("condition")),
                "task_usable_for_scope_preview": _truthy(row.get("usable_for_scope_preview")),
                "task_usable_for_geometry_preview": _truthy(row.get("usable_for_geometry_preview")),
                "n_scope_preview_rows": counts["n_scope_preview_rows"],
                "n_geometry_preview_rows": counts["n_geometry_preview_rows"],
                "dry_run": True,
                "provisional_only": True,
            }
        )

    state = {
        "dry_run": True,
        "provisional_only": True,
        "metric_dryrun_only": True,
        "formal_c1_allowed": False,
        "c1_preview_available": True,
        "n_workers_total": len(workers_in),
        "n_workers_included_for_smoke_preview": sum(_truthy(row.get("included_for_smoke_preview")) for row in workers_in),
        "n_tasks_total": len(tasks_in),
        "n_scope_preview_responses": sum(int(row["n_scope_preview_rows"]) for row in task_rows),
        "n_geometry_preview_responses": sum(int(row["n_geometry_preview_rows"]) for row in task_rows),
        "not_for_thesis_claim": True,
        "blocked_reasons": state_in.get("blocked_reasons") or [],
    }
    return state, worker_rows, task_rows


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--preview-dir", default=str(DEFAULT_PREVIEW_DIR))
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    args = parser.parse_args(argv)
    out = Path(args.output_dir)
    state, workers, tasks = build_metric_dryrun(Path(args.preview_dir))
    _write_json(out / "c1_calibration_metric_dryrun_state.json", state)
    _write_csv(out / "c1_worker_metric_dryrun.csv", WORKER_FIELDS, workers)
    _write_csv(out / "c1_task_metric_dryrun.csv", TASK_FIELDS, tasks)
    print(json.dumps(state, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
