from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any

DEFAULT_P1_DIR = Path("analysis_results/pipeline_smoke/p1_provisional")
DEFAULT_OUTPUT_DIR = Path("analysis_results/pipeline_smoke/c1_calibration_preview")

WORKER_FIELDS = [
    "annotator_id",
    "language",
    "completion_status",
    "expected_total",
    "observed_total",
    "pending_completion",
    "dropout",
    "known_bad_or_process_risk",
    "exclude_from_primary_candidate",
    "provisional_worker_status",
    "included_for_smoke_preview",
    "exclusion_reason_for_smoke_preview",
    "dry_run",
    "provisional_only",
]

TASK_FIELDS = [
    "task_id",
    "project_id",
    "dataset_group",
    "condition",
    "task_final_scope",
    "task_scope_adjudication_source",
    "geometry_gold_status",
    "geometry_evidence_role",
    "manual_anchor_role",
    "manual_anchor_primary_possible",
    "usable_for_scope_preview",
    "usable_for_geometry_preview",
    "dry_run",
    "provisional_only",
]

RESPONSE_FIELDS = [
    "annotator_id",
    "task_id",
    "dataset_group",
    "condition",
    "worker_scope_response",
    "geometry_valid_or_present",
    "scope_response_primary_eligible",
    "worker_included_for_smoke_preview",
    "task_usable_for_scope_preview",
    "task_usable_for_geometry_preview",
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


def _worker_include(row: dict[str, str]) -> tuple[bool, str]:
    if _truthy(row.get("pending_completion")) or _safe(row.get("completion_status")) == "pending_completion":
        return False, "pending_completion"
    if _truthy(row.get("dropout")):
        return False, "dropout"
    if _truthy(row.get("known_bad_or_process_risk")):
        return False, "known_bad_or_process_risk"
    if _truthy(row.get("exclude_from_primary_candidate")):
        return False, "exclude_from_primary_candidate"
    return True, ""


def _task_use(row: dict[str, str]) -> tuple[bool, bool]:
    scope_ok = _safe(row.get("task_final_scope")) == "in_scope"
    geom_ok = scope_ok and _safe(row.get("geometry_gold_status")) == "ready" and _truthy(row.get("manual_anchor_primary_possible"))
    return scope_ok, geom_ok


def build_c1_preview(p1_dir: Path = DEFAULT_P1_DIR, output_dir: Path | None = None) -> tuple[dict[str, Any], list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    root = Path(p1_dir)
    state_in = _load_json(root / "p1_provisional_pipeline_state.json")
    _load_json(root / "p1_provisional_stage_contract.json")
    p1_allowed = bool(state_in.get("smoke_pipeline_allowed"))
    blocked_reasons = [] if p1_allowed else list(state_in.get("readiness_blockers") or ["p1_smoke_pipeline_not_allowed"])

    workers_in = _load_csv(root / "p1_provisional_worker_table.csv")
    tasks_in = _load_csv(root / "p1_provisional_task_table.csv")
    responses_in = _load_csv(root / "p1_provisional_response_table.csv")

    if not p1_allowed:
        workers: list[dict[str, Any]] = []
        tasks: list[dict[str, Any]] = []
        responses: list[dict[str, Any]] = []
    else:
        workers = []
        for row in workers_in:
            include, reason = _worker_include(row)
            workers.append(
                {
                    "annotator_id": _safe(row.get("annotator_id")),
                    "language": _safe(row.get("language")),
                    "completion_status": _safe(row.get("completion_status")),
                    "expected_total": _safe(row.get("expected_total")),
                    "observed_total": _safe(row.get("observed_total")),
                    "pending_completion": _safe(row.get("pending_completion")),
                    "dropout": _safe(row.get("dropout")),
                    "known_bad_or_process_risk": _safe(row.get("known_bad_or_process_risk")),
                    "exclude_from_primary_candidate": _safe(row.get("exclude_from_primary_candidate")),
                    "provisional_worker_status": _safe(row.get("provisional_worker_status")),
                    "included_for_smoke_preview": include,
                    "exclusion_reason_for_smoke_preview": reason,
                    "dry_run": True,
                    "provisional_only": True,
                }
            )
        tasks = []
        for row in tasks_in:
            scope_ok, geom_ok = _task_use(row)
            tasks.append(
                {
                    "task_id": _safe(row.get("task_id")),
                    "project_id": _safe(row.get("project_id")),
                    "dataset_group": _safe(row.get("dataset_group")),
                    "condition": _safe(row.get("condition")),
                    "task_final_scope": _safe(row.get("task_final_scope")),
                    "task_scope_adjudication_source": _safe(row.get("task_scope_adjudication_source")),
                    "geometry_gold_status": _safe(row.get("geometry_gold_status")),
                    "geometry_evidence_role": _safe(row.get("geometry_evidence_role")),
                    "manual_anchor_role": _safe(row.get("manual_anchor_role")),
                    "manual_anchor_primary_possible": _safe(row.get("manual_anchor_primary_possible")),
                    "usable_for_scope_preview": scope_ok,
                    "usable_for_geometry_preview": geom_ok,
                    "dry_run": True,
                    "provisional_only": True,
                }
            )
        worker_ok = {str(row["annotator_id"]): bool(row["included_for_smoke_preview"]) for row in workers}
        task_scope = {str(row["task_id"]): bool(row["usable_for_scope_preview"]) for row in tasks}
        task_geom = {str(row["task_id"]): bool(row["usable_for_geometry_preview"]) for row in tasks}
        responses = [
            {
                "annotator_id": _safe(row.get("annotator_id")),
                "task_id": _safe(row.get("task_id")),
                "dataset_group": _safe(row.get("dataset_group")),
                "condition": _safe(row.get("condition")),
                "worker_scope_response": _safe(row.get("worker_scope_response")),
                "geometry_valid_or_present": _safe(row.get("geometry_valid_or_present")),
                "scope_response_primary_eligible": _safe(row.get("scope_response_primary_eligible")),
                "worker_included_for_smoke_preview": worker_ok.get(_safe(row.get("annotator_id")), False),
                "task_usable_for_scope_preview": task_scope.get(_safe(row.get("task_id")), False),
                "task_usable_for_geometry_preview": task_geom.get(_safe(row.get("task_id")), False),
                "dry_run": True,
                "provisional_only": True,
            }
            for row in responses_in
        ]

    state = {
        "dry_run": True,
        "provisional_only": True,
        "calibration_preview_only": True,
        "formal_c1_allowed": False,
        "p1_smoke_pipeline_allowed": p1_allowed,
        "n_workers_total": len(workers_in),
        "n_workers_included_for_smoke_preview": sum(bool(row["included_for_smoke_preview"]) for row in workers),
        "n_tasks_total": len(tasks_in),
        "n_responses_total": len(responses_in),
        "n_responses_included_for_scope_preview": sum(bool(row["worker_included_for_smoke_preview"]) and bool(row["task_usable_for_scope_preview"]) for row in responses),
        "n_responses_included_for_geometry_preview": sum(bool(row["worker_included_for_smoke_preview"]) and bool(row["task_usable_for_geometry_preview"]) for row in responses),
        "not_for_thesis_claim": True,
        "blocked_reasons": blocked_reasons,
    }
    return state, workers, tasks, responses


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--p1-dir", default=str(DEFAULT_P1_DIR))
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    args = parser.parse_args(argv)
    out = Path(args.output_dir)
    state, workers, tasks, responses = build_c1_preview(Path(args.p1_dir), out)
    _write_json(out / "c1_calibration_preview_state.json", state)
    if state["p1_smoke_pipeline_allowed"]:
        _write_csv(out / "c1_worker_input_preview.csv", WORKER_FIELDS, workers)
        _write_csv(out / "c1_task_input_preview.csv", TASK_FIELDS, tasks)
        _write_csv(out / "c1_response_input_preview.csv", RESPONSE_FIELDS, responses)
    else:
        _write_csv(out / "c1_worker_input_preview.csv", WORKER_FIELDS, [])
        _write_csv(out / "c1_task_input_preview.csv", TASK_FIELDS, [])
        _write_csv(out / "c1_response_input_preview.csv", RESPONSE_FIELDS, [])
    print(json.dumps(state, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
