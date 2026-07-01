from __future__ import annotations

import argparse
import csv
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

DEFAULT_DIR = Path("analysis_results/prescreen_closeout")
DEFAULT_EXACT_COPY = Path("analysis_results/p1_exact_copy_low_time_audit/p1_worker_independence_summary.csv")
DEFAULT_MANUAL_OVERRIDES = Path("analysis_results/prescreen_closeout/prescreen_manual_overrides_20260701.json")
HIGH_REVIEW_MIN_COUNT = 2
HIGH_REVIEW_RATE = 0.2

AUDIT_FIELDS = [
    "annotator_id",
    "completion_status",
    "eligible_for_primary_prescreen_candidate",
    "n_expected_total",
    "n_observed_total",
    "n_missing_tasks",
    "active_time_source_coverage",
    "n_duplicate_same_geometry",
    "n_revision",
    "n_revision_resolved_by_manual_override",
    "duplicate_revision_resolution",
    "fallback_watch",
    "n_exact_copy_low_time_events",
    "copy_audit_recommended_action",
    "n_scope_correct_in_scope",
    "n_scope_false_positive",
    "n_scope_false_negative",
    "n_manual_anchor_eligible_responses",
    "n_alignment_available",
    "n_undercoverage_high",
    "n_undercoverage_medium",
    "n_minority_full_room_candidate",
    "n_consensus_guarded_tasks",
    "screening_recommendation",
    "screening_reason",
    "evidence_tier",
    "dry_run",
    "notes",
]


def _safe(value: Any) -> str:
    return str(value or "").strip()


def _truthy(value: Any) -> bool:
    return _safe(value).lower() in {"1", "true", "yes", "y"}


def _num(value: Any) -> float:
    try:
        return float(_safe(value))
    except ValueError:
        return 0.0


def _load_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        raise FileNotFoundError(f"missing required input: {path}")
    with path.open("r", newline="", encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def _load_optional_csv(path: Path | None) -> tuple[list[dict[str, str]], bool]:
    if not path or not path.exists():
        return [], True
    with path.open("r", newline="", encoding="utf-8-sig") as f:
        return list(csv.DictReader(f)), False


def _load_manual_overrides(path: Path | None) -> tuple[dict[tuple[str, str], str], set[str]]:
    if not path or not path.exists():
        return {}, set()
    data = json.loads(path.read_text(encoding="utf-8"))
    resolved: dict[tuple[str, str], str] = {}
    for item in data.get("duplicate_annotation_overrides", []):
        worker_id = _safe(item.get("worker_id"))
        task_id = _safe(item.get("task_id"))
        final_annotation_id = _safe(item.get("final_annotation_id"))
        if _safe(item.get("duplicate_geometry_type")) == "revision" and worker_id and task_id and final_annotation_id:
            resolved[(worker_id, task_id)] = f"manual_override_resolved_final_annotation_{final_annotation_id}"
    fallback_watch = {_safe(item.get("worker_id")) for item in data.get("fallback_watch_workers", []) if _safe(item.get("worker_id"))}
    return resolved, fallback_watch


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=AUDIT_FIELDS)
        writer.writeheader()
        writer.writerows(rows)


def _worker_id(row: dict[str, str]) -> str:
    return _safe(row.get("annotator_id") or row.get("worker_id") or row.get("completed_by"))


def _recommend(row: dict[str, Any]) -> tuple[str, str]:
    status = _safe(row["completion_status"])
    if status == "pending_completion":
        return "hold_pending_completion", "pending_completion"
    if status in {"known_bad_complete", "incomplete_excluded", "dropout_no_future"} or not _truthy(row["eligible_for_primary_prescreen_candidate"]):
        return "exclude_process_risk", "completion_or_process_risk"
    if _safe(row["copy_audit_recommended_action"]) == "fail_recommended":
        return "exclude_process_risk", "copy_low_time_fail_recommended"
    if int(row["n_revision"]) > int(row["n_revision_resolved_by_manual_override"]):
        return "manual_review", "duplicate_revision_manual_review"
    if _safe(row["duplicate_revision_resolution"]):
        return "continue_candidate", _safe(row["duplicate_revision_resolution"])
    high = int(row["n_undercoverage_high"])
    available = int(row["n_alignment_available"])
    high_rate = high / available if available else 0.0
    if high == 1:
        return "continue_candidate", "task_or_worker_undercoverage_watch"
    if high >= HIGH_REVIEW_MIN_COUNT or high_rate >= HIGH_REVIEW_RATE:
        return "continue_candidate", "task_or_worker_undercoverage_watch"
    if available == 0 and int(row["n_manual_anchor_eligible_responses"]) == 0:
        return "insufficient_evidence", "no_alignment_or_anchor_evidence"
    if int(row["n_minority_full_room_candidate"]) > 0:
        return "continue_candidate", "protected_full_room_candidate"
    return "continue_candidate", "no_major_dry_run_risk"


def _evidence_tier(row: dict[str, Any]) -> str:
    if _safe(row["screening_recommendation"]) == "exclude_process_risk":
        return "process_risk"
    if _safe(row["screening_reason"]) == "duplicate_revision_manual_review" or _safe(row["duplicate_revision_resolution"]):
        return "process_risk"
    if int(row["n_minority_full_room_candidate"]) > 0 and _safe(row["screening_reason"]) == "protected_full_room_candidate":
        return "protected_full_room"
    if _safe(row["screening_recommendation"]) == "manual_review" or "undercoverage" in _safe(row["screening_reason"]):
        return "geometry_risk"
    return "review_only"


def _manual_process_exclusion_ids(completion: list[dict[str, str]]) -> list[str]:
    ids = []
    for row in completion:
        notes = _safe(row.get("notes")).lower()
        if (
            _truthy(row.get("known_bad_or_process_risk"))
            and not _truthy(row.get("eligible_for_primary_prescreen_candidate"))
            and ("manually excluded" in notes or "manual process" in notes or "confirmed process-risk" in notes)
        ):
            ids.append(_safe(row.get("annotator_id")))
    return sorted(ids, key=lambda x: int(x) if x.isdigit() else x)


def build_worker_screening_rollup(
    completion_csv: Path,
    active_time_csv: Path,
    duplicate_csv: Path,
    scope_response_csv: Path,
    geometry_eligibility_csv: Path,
    alignment_csv: Path,
    undercoverage_csv: Path,
    consensus_guard_csv: Path,
    exact_copy_csv: Path | None = None,
    manual_overrides_json: Path | None = None,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    completion = _load_csv(completion_csv)
    active = _load_csv(active_time_csv)
    duplicate = _load_csv(duplicate_csv)
    scope = _load_csv(scope_response_csv)
    eligibility = _load_csv(geometry_eligibility_csv)
    alignment = _load_csv(alignment_csv)
    under = _load_csv(undercoverage_csv)
    guard = _load_csv(consensus_guard_csv)
    exact_copy, exact_missing = _load_optional_csv(exact_copy_csv)
    resolved_revisions, fallback_watch_workers = _load_manual_overrides(manual_overrides_json)

    active_rows = defaultdict(lambda: [0.0, 0.0])
    for row in active:
        aid = _safe(row.get("annotator_id"))
        active_rows[aid][0] += _num(row.get("n_log"))
        active_rows[aid][1] += _num(row.get("n_rows"))
        if _num(row.get("n_lead_time_fallback")) > 0 and _num(row.get("n_log")) == 0:
            fallback_watch_workers.add(aid)
    dup_same = Counter(_safe(row.get("annotator_id")) for row in duplicate if _safe(row.get("duplicate_geometry_type")) == "duplicate_same_geometry")
    revisions: Counter[str] = Counter()
    resolved_revision_counts: Counter[str] = Counter()
    revision_resolution: dict[str, str] = {}
    for row in duplicate:
        if _safe(row.get("duplicate_geometry_type")) != "revision":
            continue
        aid = _safe(row.get("annotator_id"))
        revisions[aid] += 1
        resolution = resolved_revisions.get((aid, _safe(row.get("task_id"))), "")
        if resolution:
            resolved_revision_counts[aid] += 1
            revision_resolution[aid] = resolution
    exact_events: Counter[str] = Counter()
    exact_action: dict[str, str] = {}
    for row in exact_copy:
        aid = _worker_id(row)
        action = _safe(row.get("copy_audit_recommended_action") or row.get("recommended_action"))
        n_events = int(_num(row.get("n_exact_copy_low_time_events")))
        if n_events > 0:
            exact_events[aid] += n_events
        elif action and action != "no_action":
            exact_events[aid] += 1
        if action:
            exact_action[aid] = action
    scope_counts: dict[str, Counter[str]] = defaultdict(Counter)
    for row in scope:
        scope_counts[_safe(row.get("annotator_id"))][_safe(row.get("worker_scope_response"))] += 1
    manual_anchor = Counter(_safe(row.get("annotator_id")) for row in eligibility if _truthy(row.get("manual_anchor_role")))
    alignment_available = Counter(_safe(row.get("annotator_id")) for row in alignment if _truthy(row.get("alignment_available")))
    under_counts: dict[str, Counter[str]] = defaultdict(Counter)
    minority = Counter()
    for row in under:
        aid = _safe(row.get("annotator_id"))
        if _truthy(row.get("task_majority_undercoverage_risk")):
            continue
        under_counts[aid][_safe(row.get("undercoverage_risk_level"))] += 1
        if _truthy(row.get("minority_full_room_candidate")):
            minority[aid] += 1
    guarded_tasks = {row["task_id"] for row in guard if _safe(row.get("consensus_guard_bucket")) != "consensus_safe"}
    worker_guarded = Counter(_safe(row.get("annotator_id")) for row in alignment if _safe(row.get("task_id")) in guarded_tasks)

    out: list[dict[str, Any]] = []
    for comp in completion:
        aid = _safe(comp.get("annotator_id"))
        active_log, active_total = active_rows[aid]
        fallback_watch = aid in fallback_watch_workers and _truthy(comp.get("eligible_for_primary_prescreen_candidate"))
        row = {
            "annotator_id": aid,
            "completion_status": _safe(comp.get("completion_status")),
            "eligible_for_primary_prescreen_candidate": _safe(comp.get("eligible_for_primary_prescreen_candidate")),
            "n_expected_total": _safe(comp.get("total_expected")),
            "n_observed_total": _safe(comp.get("total_observed")),
            "n_missing_tasks": _safe(comp.get("total_missing")),
            "active_time_source_coverage": f"{(active_log / active_total):.6g}" if active_total else "",
            "n_duplicate_same_geometry": dup_same[aid],
            "n_revision": revisions[aid],
            "n_revision_resolved_by_manual_override": resolved_revision_counts[aid],
            "duplicate_revision_resolution": revision_resolution.get(aid, ""),
            "fallback_watch": fallback_watch,
            "n_exact_copy_low_time_events": exact_events[aid],
            "copy_audit_recommended_action": exact_action.get(aid, ""),
            "n_scope_correct_in_scope": scope_counts[aid]["correct_in_scope"],
            "n_scope_false_positive": scope_counts[aid]["scope_false_positive"],
            "n_scope_false_negative": scope_counts[aid]["scope_false_negative"],
            "n_manual_anchor_eligible_responses": manual_anchor[aid],
            "n_alignment_available": alignment_available[aid],
            "n_undercoverage_high": under_counts[aid]["high"],
            "n_undercoverage_medium": under_counts[aid]["medium"],
            "n_minority_full_room_candidate": minority[aid],
            "n_consensus_guarded_tasks": worker_guarded[aid],
            "screening_recommendation": "",
            "screening_reason": "",
            "evidence_tier": "",
            "dry_run": True,
            "notes": "dry-run screening rollup only; no admission, rejection, or reliability profile",
        }
        row["screening_recommendation"], row["screening_reason"] = _recommend(row)
        row["evidence_tier"] = _evidence_tier(row)
        out.append(row)
    unresolved_manual_review = sum(_safe(row["screening_recommendation"]) == "manual_review" for row in out)
    has_pending = any(_safe(row.get("completion_status")) == "pending_completion" for row in completion)
    ready_for_review = not has_pending and unresolved_manual_review == 0
    eligible_fallback_watch = {_safe(row["annotator_id"]) for row in out if _truthy(row.get("fallback_watch"))}
    summary = {
        "dry_run": True,
        "screening_status": "ready_for_manual_materialization_review" if ready_for_review else "provisional_dry_run",
        "final_stage1_closeout_ready": ready_for_review,
        "ready_for_manual_materialization_review": ready_for_review,
        "stage2_roster_use": "manual_materialization_review_ready_not_formal_admission",
        "active_time_input_status": "final_with_fallback_watch" if eligible_fallback_watch else "final_primary_log_only",
        "fallback_watch_worker_ids": sorted(eligible_fallback_watch, key=lambda x: int(x) if x.isdigit() else x),
        "unresolved_manual_review_count": unresolved_manual_review,
        "manual_override_resolved_revision_count": sum(resolved_revision_counts.values()),
        "completion_input_status": "pending_workers_present"
        if has_pending
        else "no_pending_workers_in_current_completion_audit",
        "worker_rows": len(out),
        "screening_recommendation_counts": dict(Counter(str(row["screening_recommendation"]) for row in out)),
        "evidence_tier_counts": dict(Counter(str(row["evidence_tier"]) for row in out)),
        "optional_exact_copy_summary_missing": exact_missing,
        "copy_risk_evaluation_status": "not_evaluated_missing_optional_input" if exact_missing else "evaluated",
        "pending_completion_worker_count": sum(_safe(row.get("completion_status")) == "pending_completion" for row in completion),
        "pending_completion_worker_ids": [
            _safe(row.get("annotator_id")) for row in completion if _safe(row.get("completion_status")) == "pending_completion"
        ],
        "dropout_or_incomplete_excluded_count": sum(
            _safe(row.get("completion_status")) in {"dropout_no_future", "incomplete_excluded"} for row in completion
        ),
        "known_bad_or_process_risk_count": sum(_truthy(row.get("known_bad_or_process_risk")) for row in completion),
        "manual_process_exclusion_count": len(_manual_process_exclusion_ids(completion)),
        "manual_process_exclusion_ids": _manual_process_exclusion_ids(completion),
        "manual_process_exclusion_basis": "manual_process_risk_override_not_algorithmic_copy_detection",
        "forbidden_materialization_status": "not_generated",
        "undercoverage_screening_rule": {
            "p1_policy": "nonblocking_watch_only",
            "task_majority_undercoverage_risk": "excluded_from_worker_level_counts",
            "watch_high_count_gte": HIGH_REVIEW_MIN_COUNT,
            "watch_high_rate_gte": HIGH_REVIEW_RATE,
        },
        "forbidden_outputs_generated": False,
        "forbidden_metric_field_count": sum(1 for row in out for key in row if "score" in key.lower()),
    }
    return out, summary


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--completion-csv", default=str(DEFAULT_DIR / "prescreen_completion_audit.csv"))
    parser.add_argument("--active-time-csv", default=str(DEFAULT_DIR / "prescreen_active_time_source_audit.csv"))
    parser.add_argument("--duplicate-csv", default=str(DEFAULT_DIR / "prescreen_duplicate_annotation_audit.csv"))
    parser.add_argument("--scope-response-csv", default=str(DEFAULT_DIR / "prescreen_scope_response_audit.csv"))
    parser.add_argument("--geometry-eligibility-csv", default=str(DEFAULT_DIR / "prescreen_geometry_eligibility_audit.csv"))
    parser.add_argument("--alignment-csv", default=str(DEFAULT_DIR / "prescreen_worker_gold_alignment_audit.csv"))
    parser.add_argument("--undercoverage-csv", default=str(DEFAULT_DIR / "prescreen_undercoverage_risk_audit.csv"))
    parser.add_argument("--consensus-guard-csv", default=str(DEFAULT_DIR / "prescreen_consensus_guard_audit.csv"))
    parser.add_argument("--exact-copy-csv", default=str(DEFAULT_EXACT_COPY))
    parser.add_argument("--manual-overrides-json", default=str(DEFAULT_MANUAL_OVERRIDES))
    parser.add_argument("--output-dir", default=str(DEFAULT_DIR))
    args = parser.parse_args(argv)
    rows, summary = build_worker_screening_rollup(
        Path(args.completion_csv),
        Path(args.active_time_csv),
        Path(args.duplicate_csv),
        Path(args.scope_response_csv),
        Path(args.geometry_eligibility_csv),
        Path(args.alignment_csv),
        Path(args.undercoverage_csv),
        Path(args.consensus_guard_csv),
        Path(args.exact_copy_csv) if args.exact_copy_csv else None,
        Path(args.manual_overrides_json) if args.manual_overrides_json else None,
    )
    out_dir = Path(args.output_dir)
    audit_path = out_dir / "prescreen_worker_screening_rollup.csv"
    summary_path = out_dir / "prescreen_worker_screening_summary.json"
    _write_csv(audit_path, rows)
    summary.update({"worker_screening_rollup_csv": str(audit_path), "worker_screening_summary_json": str(summary_path)})
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
