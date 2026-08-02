"""Materialize the formal, SHA-bound C2-A-RP closeout."""

from __future__ import annotations

import argparse
import csv
import json
from collections import Counter
from pathlib import Path
from typing import Any

from tools.thesis_main.analysis.c1_materialize_c2_gap_audits import _c2a_rp_limits
from tools.thesis_main.analysis.materialize_c2b_closeout import (
    NONCOMPLETED_TERMINAL_STATUSES,
    _default_missing_reason,
    _missing_dispositions,
)
from tools.thesis_main.analysis.paper_a_contracts import METHOD_CONTRACT, load_method_contract, sha256_file
from tools.thesis_main.analysis.worker_identity import normalize_worker_id


def _rows(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as stream:
        return list(csv.DictReader(stream))


def _text(value: Any) -> str:
    return str(value or "").strip()


def _truth(value: Any) -> bool:
    return _text(value).lower() in {"true", "1", "yes", "y"}


def _int(row: dict[str, str], field: str) -> int:
    try:
        value = int(_text(row.get(field)))
    except (TypeError, ValueError) as exc:
        raise ValueError(f"C2-A-RP missing integer field:{field}") from exc
    return value


def _profile_terminal(row: dict[str, str]) -> str:
    return next((_text(row.get(field)) for field in ("terminal_status", "completion_status", "final_completion_disposition") if _text(row.get(field))), "")


def _dependency(role: str, path: Path) -> dict[str, str]:
    return {"role": role, "path": str(path.resolve()), "sha256": sha256_file(path)}


def materialize(
    precision_plan_csv: Path,
    assignment_manifest_csv: Path,
    assignment_history_csv: Path,
    submissions_csv: Path,
    post_c2a_profile_csv: Path,
    c2b_closeout: Path,
    output_json: Path,
    *,
    terminal_disposition_csv: Path | None = None,
) -> dict[str, Any]:
    method = load_method_contract()
    max_tasks, max_blocks, method_sha = _c2a_rp_limits()
    c2b = json.loads(c2b_closeout.read_text(encoding="utf-8"))
    if c2b.get("schema_version") != "c2b_closeout_v2" or c2b.get("c2b_closeout_ready") is not True or c2b.get("formal_ready") is not True:
        raise ValueError("C2-A-RP requires a formally ready C2-B closeout")
    if (c2b.get("method_contract_version") != method["contract_version"]
            or c2b.get("method_contract_sha256") != method_sha):
        raise ValueError("C2-B closeout method contract SHA is stale")

    plan = _rows(precision_plan_csv)
    assignments = _rows(assignment_manifest_csv)
    history = _rows(assignment_history_csv)
    submissions = _rows(submissions_csv)
    profiles = _rows(post_c2a_profile_csv)
    profile_by_worker = {normalize_worker_id(row.get("worker_id", "")): row for row in profiles}
    if len(profile_by_worker) != len(profiles):
        raise ValueError("C2-A-RP post-profile worker identities are not unique")

    plan_by_worker: dict[str, dict[str, str]] = {}
    for row in plan:
        worker = normalize_worker_id(row.get("worker_id", ""))
        if not worker or worker in plan_by_worker:
            raise ValueError("C2-A-RP precision plan worker identities are not unique")
        blocks = _int(row, "additional_blocks")
        ordinary = _int(row, "ordinary_tasks")
        stress = _int(row, "stress_tasks")
        if not 0 <= blocks <= max_blocks or ordinary != blocks or stress != blocks or 2 * blocks > max_tasks:
            raise ValueError("C2-A-RP precision plan exceeds the normative cap")
        plan_by_worker[worker] = row
        if worker not in profile_by_worker:
            raise ValueError(f"C2-A-RP post-profile is missing worker:{worker}")

    history_seen: set[tuple[str, str, str]] = set()
    history_worker_tasks: set[tuple[str, str]] = set()
    history_worker_bases: set[tuple[str, str]] = set()
    history_task_support: Counter[str] = Counter()
    for row in history:
        worker = normalize_worker_id(row.get("worker_id", ""))
        task = _text(row.get("task_id"))
        base = _text(row.get("base_task_id"))
        if not worker or not task or not base:
            raise ValueError("C2-A-RP assignment history has incomplete identity")
        key = (worker, task, base)
        if key in history_seen:
            raise ValueError("C2-A-RP assignment history contains duplicate task identity")
        history_seen.add(key)
        history_worker_tasks.add((worker, task))
        history_worker_bases.add((worker, base))
        history_task_support[task] += 1

    assignment_keys: set[tuple[str, str]] = set()
    assignment_bases: set[tuple[str, str]] = set()
    assignment_task_support: Counter[str] = Counter(history_task_support)
    assignment_by_worker: dict[str, list[dict[str, str]]] = {}
    for row in assignments:
        worker = normalize_worker_id(row.get("worker_id", ""))
        task = _text(row.get("task_id"))
        base = _text(row.get("base_task_id")) or task
        stratum = _text(row.get("task_stratum") or row.get("risk_bucket")).lower()
        if not worker or not task or stratum not in {"ordinary", "stress"}:
            raise ValueError("C2-A-RP assignment has incomplete identity or stratum")
        key = (worker, task)
        base_key = (worker, base)
        if key in assignment_keys or base_key in assignment_bases:
            raise ValueError("C2-A-RP task_id/base_task_id is repeated for a worker")
        if (worker, task) in history_worker_tasks or (worker, base) in history_worker_bases:
            raise ValueError("C2-A-RP assignment repeats a task already seen by the worker")
        assignment_keys.add(key)
        assignment_bases.add(base_key)
        assignment_task_support[task] += 1
        if assignment_task_support[task] > 2:
            raise ValueError("C2-A-RP task support exceeds the frozen cap")
        declared_after = _text(row.get("task_support_after"))
        if declared_after and _int(row, "task_support_after") > 2:
            raise ValueError("C2-A-RP declared task support exceeds the frozen cap")
        assignment_by_worker.setdefault(worker, []).append(row)

    expected_workers = {worker for worker, row in plan_by_worker.items() if _int(row, "additional_blocks")}
    if set(assignment_by_worker) != expected_workers:
        raise ValueError("C2-A-RP assignments do not match the precision plan")
    for worker, row in plan_by_worker.items():
        rows = assignment_by_worker.get(worker, [])
        expected = 2 * _int(row, "additional_blocks")
        if len(rows) != expected:
            raise ValueError(f"C2-A-RP assignment count mismatch:{worker}")
        counts = Counter(_text(item.get("task_stratum") or item.get("risk_bucket")).lower() for item in rows)
        if counts["ordinary"] != counts["stress"] or counts["ordinary"] != _int(row, "additional_blocks"):
            raise ValueError(f"C2-A-RP ordinary/stress pairing mismatch:{worker}")

    submitted = [(normalize_worker_id(row.get("worker_id", "")), _text(row.get("task_id"))) for row in submissions]
    if any(key not in assignment_keys for key in submitted):
        raise ValueError("C2-A-RP contains an unassigned submission")
    if len(submitted) != len(set(submitted)):
        raise ValueError("C2-A-RP duplicate/revision disposition is unresolved")
    submitted_set = set(submitted)
    missing = assignment_keys - submitted_set
    exact_dispositions, worker_dispositions = _missing_dispositions(terminal_disposition_csv)
    for key in exact_dispositions:
        if key not in missing:
            raise ValueError("C2-A-RP terminal disposition does not identify a missing task")
    assignment_workers = {worker for worker, _task in assignment_keys}
    if any(worker not in assignment_workers for worker in worker_dispositions):
        raise ValueError("C2-A-RP terminal disposition references an unknown worker")
    missing_dispositions: dict[tuple[str, str], dict[str, str]] = {}
    for worker, task in sorted(missing):
        disposition = exact_dispositions.get((worker, task)) or worker_dispositions.get(worker)
        if disposition is None:
            status = _profile_terminal(profile_by_worker[worker])
            if status in NONCOMPLETED_TERMINAL_STATUSES:
                disposition = {"terminal_status": status, "missing_reason": ""}
        if disposition is None or disposition.get("terminal_status") not in NONCOMPLETED_TERMINAL_STATUSES:
            raise ValueError("C2-A-RP missing task has no valid terminal disposition")
        status = disposition["terminal_status"]
        missing_dispositions[(worker, task)] = {
            "terminal_status": status,
            "missing_reason": disposition.get("missing_reason") or _default_missing_reason(status),
        }

    n_workers_target_met = sum(_truth(row.get("precision_target_met")) or _int(row, "additional_blocks") == 0 for row in plan_by_worker.values())
    n_workers_fallback = sum(bool(_text(row.get("unmet_reason")) or _text(row.get("routing_eligibility")) == "uncertain_fallback_global") for row in plan_by_worker.values())
    summary = {
        "schema_version": "c2a_rp_closeout_v1",
        "artifact_role": "C2A_RP_CLOSEOUT_FROZEN",
        "contract_role": "generated_subordinate",
        "method_contract_version": method["contract_version"],
        "method_contract_sha256": method_sha,
        "profile_version": c2b.get("profile_version", "") or (_text(profiles[0].get("profile_version")) if profiles else ""),
        "cohort_id": c2b.get("cohort_id", "") or (_text(profiles[0].get("cohort_id")) if profiles else ""),
        "formal_ready": True,
        "C2_A_RP_CLOSED": True,
        "n_workers_assigned": len(assignment_by_worker),
        "n_workers_completed": sum(all((worker, _text(row.get("task_id"))) in submitted_set for row in assignment_by_worker[worker]) for worker in assignment_by_worker),
        "n_workers_partial": sum(any((worker, _text(row.get("task_id"))) not in submitted_set for row in assignment_by_worker[worker]) for worker in assignment_by_worker),
        "n_assignments": len(assignments),
        "n_submissions": len(submitted),
        "n_missing": len(missing),
        "n_workers_target_met": n_workers_target_met,
        "n_workers_fallback": n_workers_fallback,
        "missing_worker_tasks": [
            {"worker_id": worker, "task_id": task, **missing_dispositions[(worker, task)]}
            for worker, task in sorted(missing)
        ],
        "closure_reason": "all_precision_targets_met_or_unsupported_adjustments_fallback" if not assignments else "all_assigned_tasks_completed_or_terminalized_at_frozen_cap",
        "precision_plan_path": str(precision_plan_csv),
        "precision_plan_sha256": sha256_file(precision_plan_csv),
        "assignment_manifest_path": str(assignment_manifest_csv),
        "assignment_manifest_sha256": sha256_file(assignment_manifest_csv),
        "assignment_history_path": str(assignment_history_csv),
        "assignment_history_sha256": sha256_file(assignment_history_csv),
        "submissions_path": str(submissions_csv),
        "submissions_sha256": sha256_file(submissions_csv),
        "post_c2a_rp_profile_path": str(post_c2a_profile_csv),
        "post_c2a_rp_profile_sha256": sha256_file(post_c2a_profile_csv),
        "c2b_closeout_path": str(c2b_closeout),
        "c2b_closeout_sha256": sha256_file(c2b_closeout),
        "terminal_disposition_path": str(terminal_disposition_csv or ""),
        "terminal_disposition_sha256": sha256_file(terminal_disposition_csv) if terminal_disposition_csv else "",
        "blockers": [],
        "dependencies": [
            _dependency("C2A_PRECISION_PLAN", precision_plan_csv),
            _dependency("C2A_ASSIGNMENT_MANIFEST", assignment_manifest_csv),
            _dependency("C2A_ASSIGNMENT_HISTORY", assignment_history_csv),
            _dependency("C2A_SUBMISSIONS", submissions_csv),
            _dependency("POST_C2A_RP_PROFILE", post_c2a_profile_csv),
            _dependency("C2B_CLOSEOUT", c2b_closeout),
            _dependency("METHOD_CONTRACT", METHOD_CONTRACT),
        ],
    }
    if terminal_disposition_csv:
        summary["dependencies"].append(_dependency("C2A_TERMINAL_DISPOSITION", terminal_disposition_csv))
    output_json.parent.mkdir(parents=True, exist_ok=True)
    output_json.write_text(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return summary


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Materialize the formal C2-A-RP closeout.")
    parser.add_argument("--precision-plan", type=Path, required=True)
    parser.add_argument("--assignment-manifest", type=Path, required=True)
    parser.add_argument("--assignment-history", type=Path, required=True)
    parser.add_argument("--submissions", type=Path, required=True)
    parser.add_argument("--post-c2a-rp-profile", type=Path, required=True)
    parser.add_argument("--c2b-closeout", type=Path, required=True)
    parser.add_argument("--terminal-disposition", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    print(json.dumps(materialize(
        args.precision_plan, args.assignment_manifest, args.assignment_history,
        args.submissions, args.post_c2a_rp_profile, args.c2b_closeout, args.output,
        terminal_disposition_csv=args.terminal_disposition,
    ), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
