from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any

DEFAULT_CLOSEOUT_DIR = Path("analysis_results/prescreen_closeout")
DEFAULT_OUTPUT_DIR = Path("analysis_results/pipeline_smoke/p1_provisional")

ALLOWED_BLOCKERS = {"data_complete_false", "pending_completion_present"}

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


def _write_csv(path: Path, fields: list[str], rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _smoke_allowed(readiness: dict[str, Any]) -> bool:
    blockers = set(readiness.get("blockers") or [])
    return (
        blockers.issubset(ALLOWED_BLOCKERS)
        and int(readiness.get("unknown_gold_count") or 0) == 0
        and int(readiness.get("forbidden_artifact_count") or 0) == 0
        and not bool(readiness.get("geometry_score_fields_present"))
        and not list(readiness.get("missing_required_artifacts") or [])
        and readiness.get("final_gold_source_snapshot_sha256_match") is not None
        and readiness.get("export_gt_source_snapshot_sha256_match") is not None
        and int(readiness.get("source_export_snapshot_count") or 0) > 0
    )


def _worker_status(row: dict[str, str]) -> str:
    if _safe(row.get("completion_status")) == "pending_completion":
        return "pending_completion"
    if _truthy(row.get("dropout")):
        return "dropout"
    if _truthy(row.get("known_bad_or_process_risk")) or _truthy(row.get("exclude_from_primary_candidate")):
        return "process_risk_or_excluded"
    return "review_only"


def build_provisional_pipeline(closeout_dir: Path = DEFAULT_CLOSEOUT_DIR) -> tuple[list[dict[str, Any]] | dict[str, Any], ...]:
    root = Path(closeout_dir)
    readiness = _load_json(root / "p1_closeout_readiness_summary.json")
    pending = _load_json(root / "p1_pending_completion_summary.json")
    completion = _load_csv(root / "prescreen_completion_audit.csv")
    roster = {row["annotator_id"]: row for row in _load_csv(root / "prescreen_worker_roster.csv")}
    _load_csv(root / "prescreen_canonical_annotations.csv")
    scope_tasks = _load_csv(root / "prescreen_scope_adjudication.csv")
    scope_responses = _load_csv(root / "prescreen_scope_response_audit.csv")
    _load_csv(root / "prescreen_worker_scope_summary.csv")
    geometry = _load_csv(root / "prescreen_geometry_eligibility_audit.csv")
    _load_csv(root / "prescreen_geometry_gold_alignment_audit.csv")
    _load_json(root / "prescreen_gold_alignment_summary.json")

    state = {
        "dry_run": True,
        "provisional_only": True,
        "data_complete": bool(readiness.get("data_complete")),
        "formal_materialization_allowed": False,
        "smoke_pipeline_allowed": _smoke_allowed(readiness),
        "readiness_status": readiness.get("readiness_status"),
        "readiness_blockers": readiness.get("blockers") or [],
        "pending_completion_count": pending.get("pending_completion_count", readiness.get("pending_completion_count")),
        "pending_worker_ids": pending.get("pending_worker_ids") or [],
        "unknown_gold_count": readiness.get("unknown_gold_count", 0),
        "forbidden_artifact_count": readiness.get("forbidden_artifact_count", 0),
        "geometry_score_fields_present": bool(readiness.get("geometry_score_fields_present")),
        "missing_required_artifacts": readiness.get("missing_required_artifacts") or [],
        "not_for_thesis_claim": True,
        "notes": "script integration smoke test only; blocked readiness still forbids formal P1 materialization",
    }

    worker_rows = []
    for row in completion:
        rr = roster.get(_safe(row.get("annotator_id")), {})
        merged = {**row, **rr}
        worker_rows.append(
            {
                "annotator_id": _safe(row.get("annotator_id")),
                "language": _safe(merged.get("language")),
                "completion_status": _safe(row.get("completion_status")),
                "expected_total": _safe(merged.get("expected_total") or row.get("total_expected")),
                "observed_total": _safe(row.get("total_observed")),
                "pending_completion": _safe(row.get("completion_status")) == "pending_completion",
                "dropout": _safe(merged.get("dropout")),
                "known_bad_or_process_risk": _safe(merged.get("known_bad_or_process_risk")),
                "exclude_from_primary_candidate": _safe(merged.get("exclude_from_primary_candidate")),
                "provisional_worker_status": _worker_status(merged),
                "dry_run": True,
                "provisional_only": True,
            }
        )

    scope_by_task = {_safe(row.get("task_id")): row for row in scope_tasks}
    geometry_by_task: dict[str, dict[str, str]] = {}
    for row in geometry:
        geometry_by_task.setdefault(_safe(row.get("task_id")), row)
    task_rows = []
    for task_id in sorted(set(scope_by_task) | set(geometry_by_task)):
        row = scope_by_task.get(task_id, {})
        geom = geometry_by_task.get(task_id, {})
        task_rows.append(
            {
                "task_id": task_id,
                "project_id": _safe(row.get("project_id") or geom.get("project_id")),
                "dataset_group": _safe(row.get("dataset_group") or geom.get("dataset_group")),
                "condition": _safe(row.get("condition") or geom.get("condition")),
                "task_final_scope": _safe(row.get("task_final_scope") or geom.get("task_final_scope")),
                "task_scope_adjudication_source": _safe(row.get("task_scope_adjudication_source") or geom.get("task_scope_adjudication_source")),
                "geometry_gold_status": _safe(geom.get("geometry_gold_status")),
                "geometry_evidence_role": _safe(geom.get("geometry_evidence_role")),
                "manual_anchor_role": _safe(geom.get("manual_anchor_role")),
                "manual_anchor_primary_possible": _safe(geom.get("manual_anchor_primary_possible")),
                "dry_run": True,
                "provisional_only": True,
            }
        )

    response_rows = [
        {
            "annotator_id": _safe(row.get("annotator_id")),
            "task_id": _safe(row.get("task_id")),
            "dataset_group": _safe(row.get("dataset_group")),
            "condition": _safe(row.get("condition")),
            "worker_scope_response": _safe(row.get("worker_scope_response")),
            "geometry_valid_or_present": _safe(row.get("geometry_valid_or_present")),
            "scope_response_primary_eligible": _safe(row.get("scope_response_primary_eligible")),
            "dry_run": True,
            "provisional_only": True,
        }
        for row in scope_responses
    ]

    contract = {
        "this_is_not_formal_p1_materialization": True,
        "not_for_thesis_claim": True,
        "downstream_use": "script_integration_smoke_test_only",
        "may_be_discarded_after_final_freeze": True,
        "final_freeze_required_before_formal_analysis": True,
    }
    return state, worker_rows, task_rows, response_rows, contract


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--closeout-dir", default=str(DEFAULT_CLOSEOUT_DIR))
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    args = parser.parse_args(argv)
    out = Path(args.output_dir)
    state, workers, tasks, responses, contract = build_provisional_pipeline(Path(args.closeout_dir))
    _write_json(out / "p1_provisional_pipeline_state.json", state)
    _write_csv(out / "p1_provisional_worker_table.csv", WORKER_FIELDS, workers)  # type: ignore[arg-type]
    _write_csv(out / "p1_provisional_task_table.csv", TASK_FIELDS, tasks)  # type: ignore[arg-type]
    _write_csv(out / "p1_provisional_response_table.csv", RESPONSE_FIELDS, responses)  # type: ignore[arg-type]
    _write_json(out / "p1_provisional_stage_contract.json", contract)
    print(json.dumps(state, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
