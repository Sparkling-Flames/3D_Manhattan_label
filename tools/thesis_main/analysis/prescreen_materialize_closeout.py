from __future__ import annotations

import argparse
import csv
import json
from collections import Counter
from pathlib import Path
from typing import Any

DEFAULT_DIR = Path("analysis_results/prescreen_closeout")
DEFAULT_WMAX = DEFAULT_DIR / "w_max_locked.json"
DEFAULT_ISSUE_REVIEW = DEFAULT_DIR / "prescreen_semi_synthetic_trap_issue_review.csv"

ADMISSION_FIELDS = [
    "worker_id",
    "platform_worker_id",
    "completion_status",
    "admission_status",
    "admission_decision",
    "admission_reason",
    "screening_recommendation",
    "screening_reason",
    "evidence_tier",
    "r_u_0",
    "r_u_0_source",
    "manual_geometry_summary",
    "scope_quality_summary",
    "active_time_source_tier",
    "fallback_watch",
    "undercoverage_watch",
    "duplicate_or_copy_risk",
    "known_bad_flag",
    "watch_flag",
    "w_max",
    "eligible_for_C1",
    "c1_handoff_note",
]

R0_FIELDS = [
    "worker_id",
    "admission_status",
    "r_u_0",
    "r_u_0_basis",
    "geometry_quality_summary",
    "scope_quality_summary",
    "blind_trust_summary",
    "completion_summary",
    "active_time_source_tier",
    "fallback_watch",
    "undercoverage_watch",
    "duplicate_copy_watch",
    "c1_priority_note",
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


def _write_csv(path: Path, fields: list[str], rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def _rate(num: float, den: float) -> str:
    return f"{(num / den):.6g}" if den else ""


def _clamp(value: float) -> float:
    return max(0.0, min(1.0, value))


def _r0(row: dict[str, str]) -> tuple[str, str, str, str]:
    alignment = _num(row.get("n_alignment_available"))
    high = _num(row.get("n_undercoverage_high"))
    medium = _num(row.get("n_undercoverage_medium"))
    geom = _clamp(1.0 - ((high + 0.5 * medium) / alignment)) if alignment else None
    scope_den = _num(row.get("n_scope_correct_in_scope")) + _num(row.get("n_scope_false_positive")) + _num(row.get("n_scope_false_negative"))
    scope = _num(row.get("n_scope_correct_in_scope")) / scope_den if scope_den else None
    parts = [value for value in (geom, scope) if value is not None]
    r0 = sum(parts) / len(parts) if parts else None
    geom_summary = f"alignment_available={int(alignment)};undercoverage_high={int(high)};undercoverage_medium={int(medium)}"
    scope_summary = (
        f"correct_in_scope={int(_num(row.get('n_scope_correct_in_scope')))};"
        f"false_positive={int(_num(row.get('n_scope_false_positive')))};"
        f"false_negative={int(_num(row.get('n_scope_false_negative')))}"
    )
    return (f"{r0:.6g}" if r0 is not None else "", "p1_proxy_scope_geometry_not_formal_r_u", geom_summary, scope_summary)


def _active_tier(row: dict[str, str]) -> str:
    if _truthy(row.get("fallback_watch")):
        return "lead_time_fallback_sensitivity_only"
    coverage = _safe(row.get("active_time_source_coverage"))
    return "active_log_primary" if coverage == "1" else "mixed_or_partial_active_time"


def _watch_flags(row: dict[str, str]) -> list[str]:
    flags = []
    if _truthy(row.get("fallback_watch")):
        flags.append("fallback_watch")
    if "undercoverage" in _safe(row.get("screening_reason")):
        flags.append("undercoverage_watch")
    if _num(row.get("n_duplicate_same_geometry")) > 0 or _num(row.get("n_revision")) > 0:
        flags.append("duplicate_audit_watch")
    if _safe(row.get("duplicate_revision_resolution")):
        flags.append(_safe(row.get("duplicate_revision_resolution")))
    if _num(row.get("n_exact_copy_low_time_events")) > 0:
        flags.append("copy_audit_watch")
    return flags


def _validate_issue_review(path: Path) -> dict[str, Any]:
    rows = _load_csv(path)
    required = {"en_task_id", "zh_task_id", "reviewed_primary_issue", "issue_label_source"}
    missing = required - set(rows[0].keys() if rows else [])
    if missing:
        raise ValueError(f"semi synthetic issue review missing fields: {sorted(missing)}")
    non_manual = [row for row in rows if _safe(row.get("issue_label_source")) != "manual_review"]
    if non_manual:
        raise ValueError("semi synthetic issue review must use issue_label_source=manual_review")
    return {
        "path": str(path),
        "n_mirror_pairs": len(rows),
        "planned_actual_mismatch_count": sum(_truthy(row.get("planned_actual_mismatch")) for row in rows),
    }


def _load_final_gold_correction_audit(path: Path | None) -> dict[str, Any]:
    if not path:
        return {}
    audit = json.loads(path.read_text(encoding="utf-8"))
    return {
        "path": str(path),
        "source_final_gold_sha256": _safe(audit.get("source_final_gold_sha256")),
        "corrected_final_gold_v2_sha256": _safe(audit.get("corrected_final_gold_v2_sha256")),
        "corrections": audit.get("corrections") or [],
    }


def build_closeout_materialization(
    rollup_csv: Path,
    w_max_json: Path,
    issue_review_csv: Path,
    final_gold_correction_audit_json: Path | None = None,
    superseded_closeout_note: str = "",
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any], str]:
    rollup = _load_csv(rollup_csv)
    wmax = json.loads(w_max_json.read_text(encoding="utf-8")) if w_max_json.exists() else {"worker_w_max": {}}
    issue_review = _validate_issue_review(issue_review_csv)
    correction_audit = _load_final_gold_correction_audit(final_gold_correction_audit_json)
    worker_wmax = {str(k): v for k, v in wmax.get("worker_w_max", {}).items()}
    admission_rows: list[dict[str, Any]] = []
    r0_rows: list[dict[str, Any]] = []
    for row in rollup:
        worker_id = _safe(row.get("annotator_id"))
        recommendation = _safe(row.get("screening_recommendation"))
        fail = recommendation == "exclude_process_risk"
        flags = [] if fail else _watch_flags(row)
        admission_status = "fail" if fail else ("pass_with_watch" if flags else "pass")
        eligible = admission_status != "fail"
        r0, r0_source, geom_summary, scope_summary = _r0(row) if eligible else ("", "not_applicable_excluded", "", "")
        reason = "screening_exclude_process_risk" if fail else (_safe(row.get("screening_reason")) or "screening_continue_candidate")
        handoff = "excluded_from_C1" if fail else (";".join(flags) if flags else "standard_C1_entry")
        admission_rows.append(
            {
                "worker_id": worker_id,
                "platform_worker_id": worker_id,
                "completion_status": _safe(row.get("completion_status")),
                "admission_status": admission_status,
                "admission_decision": "exclude" if fail else ("allow_with_watch" if flags else "allow"),
                "admission_reason": reason,
                "screening_recommendation": recommendation,
                "screening_reason": _safe(row.get("screening_reason")),
                "evidence_tier": _safe(row.get("evidence_tier")),
                "r_u_0": r0,
                "r_u_0_source": r0_source,
                "manual_geometry_summary": geom_summary,
                "scope_quality_summary": scope_summary,
                "active_time_source_tier": _active_tier(row),
                "fallback_watch": _truthy(row.get("fallback_watch")),
                "undercoverage_watch": "undercoverage" in _safe(row.get("screening_reason")),
                "duplicate_or_copy_risk": _num(row.get("n_duplicate_same_geometry")) > 0 or _num(row.get("n_revision")) > 0 or _num(row.get("n_exact_copy_low_time_events")) > 0,
                "known_bad_flag": _safe(row.get("completion_status")) in {"known_bad_complete", "incomplete_excluded"},
                "watch_flag": bool(flags),
                "w_max": worker_wmax.get(worker_id, ""),
                "eligible_for_C1": eligible,
                "c1_handoff_note": handoff,
            }
        )
        r0_rows.append(
            {
                "worker_id": worker_id,
                "admission_status": admission_status,
                "r_u_0": r0,
                "r_u_0_basis": r0_source,
                "geometry_quality_summary": geom_summary,
                "scope_quality_summary": scope_summary,
                "blind_trust_summary": "semi_issue_review_sidecar_ready_not_scored_in_screening",
                "completion_summary": f"{_safe(row.get('completion_status'))};observed={_safe(row.get('n_observed_total'))}/{_safe(row.get('n_expected_total'))}",
                "active_time_source_tier": _active_tier(row),
                "fallback_watch": _truthy(row.get("fallback_watch")),
                "undercoverage_watch": "undercoverage" in _safe(row.get("screening_reason")),
                "duplicate_copy_watch": _num(row.get("n_duplicate_same_geometry")) > 0 or _num(row.get("n_revision")) > 0 or _num(row.get("n_exact_copy_low_time_events")) > 0,
                "c1_priority_note": handoff,
            }
        )
    counts = Counter(row["admission_status"] for row in admission_rows)
    completion_counts = Counter(row["completion_status"] for row in admission_rows)
    eligible_count = counts["pass"] + counts["pass_with_watch"]
    fallback_workers = [row["worker_id"] for row in admission_rows if row["eligible_for_C1"] and row["fallback_watch"]]
    resolved_revisions = [row["admission_reason"] for row in admission_rows if str(row["admission_reason"]).startswith("manual_override_resolved_final_annotation_")]
    if eligible_count >= 16:
        mode, rq3 = "full", True
    elif eligible_count >= 12:
        mode, rq3 = "rq1_rq2_only", "conditional"
    else:
        mode, rq3 = "downgraded_stress_audit", False
    summary = {
        "materialization_status": "materialized",
        "worker_rows": len(admission_rows),
        "n_invited_or_rostered": len(admission_rows),
        "n_completed_including_known_bad": completion_counts["complete"] + completion_counts["known_bad_complete"],
        "n_complete_eligible_pool": eligible_count,
        "n_pass": counts["pass"],
        "n_pass_with_watch": counts["pass_with_watch"],
        "n_fail": counts["fail"],
        "n_manual_review_required_unresolved": 0,
        "n_eligible_for_C1": eligible_count,
        "protocol_mode": mode,
        "rq3_scene_specific_allowed": rq3,
        "reason": "P1 closeout materialized from resolved screening rollup; unresolved manual review count is zero.",
        "semi_synthetic_issue_review": issue_review,
        "final_gold_correction_audit": correction_audit,
        "forbidden_freezes_not_created": ["formal_r_u", "r_u_scene", "tau_d", "routing_profile"],
    }
    report_lines = [
            "# PreScreen Round Report",
            "",
            "P1 closeout materializes admission, r_u^(0), w_max handoff, and audit evidence only. It does not freeze formal r_u, tau_d, score, or routing.",
            "",
            f"- Workers: pass={counts['pass']}, pass_with_watch={counts['pass_with_watch']}, fail={counts['fail']}, eligible_for_C1={eligible_count}.",
            "- Active time: userscript logs are primary; lead_time fallback is sensitivity-only and appears as fallback watch.",
            f"- Fallback watch workers entering C1: {', '.join(fallback_workers) if fallback_workers else 'none'}.",
            "- Duplicate revision: resolved manual overrides are retained as audit trace and do not block admission.",
            f"- Resolved duplicate revision overrides: {', '.join(resolved_revisions) if resolved_revisions else 'none'}.",
            f"- Semi synthetic issue review: {issue_review['n_mirror_pairs']} mirror pairs from {issue_review['path']}; labels come from manual_review reviewed_* fields, not planned_operator.",
            "- Undercoverage: P1 nonblocking watch; task-majority undercoverage does not become worker-level exclusion.",
    ]
    if _safe(superseded_closeout_note):
        report_lines.append(f"- {_safe(superseded_closeout_note)}.")
    if correction_audit:
        correction_parts = [
            f"task {row.get('task_id')} {row.get('correction_type')} affected {', '.join(str(t) for t in row.get('affected_runtime_tasks', []))}"
            for row in correction_audit["corrections"]
        ]
        report_lines.append(f"- Final-gold v2 corrections: {'; '.join(correction_parts)}.")
    report = "\n".join(report_lines)
    return admission_rows, r0_rows, summary, report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--rollup-csv", default=str(DEFAULT_DIR / "prescreen_worker_screening_rollup.csv"))
    parser.add_argument("--w-max-json", default=str(DEFAULT_WMAX))
    parser.add_argument("--issue-review-csv", default=str(DEFAULT_ISSUE_REVIEW))
    parser.add_argument("--final-gold-correction-audit-json", default="")
    parser.add_argument("--output-dir", default=str(DEFAULT_DIR))
    parser.add_argument("--superseded-closeout-note", default="")
    args = parser.parse_args(argv)
    admission, r0, summary, report = build_closeout_materialization(
        Path(args.rollup_csv),
        Path(args.w_max_json),
        Path(args.issue_review_csv),
        Path(args.final_gold_correction_audit_json) if args.final_gold_correction_audit_json else None,
        superseded_closeout_note=args.superseded_closeout_note,
    )
    out_dir = Path(args.output_dir)
    admission_path = out_dir / "prescreen_worker_admission.csv"
    r0_path = out_dir / "prescreen_r0_snapshot.csv"
    pass_count_path = out_dir / "prescreen_pass_count_decision.json"
    report_path = out_dir / "prescreen_round_report.md"
    _write_csv(admission_path, ADMISSION_FIELDS, admission)
    _write_csv(r0_path, R0_FIELDS, r0)
    summary.update(
        {
            "prescreen_worker_admission_csv": str(admission_path),
            "prescreen_r0_snapshot_csv": str(r0_path),
            "prescreen_pass_count_decision_json": str(pass_count_path),
            "prescreen_round_report_md": str(report_path),
        }
    )
    pass_count_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    report_path.write_text(report + "\n", encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
