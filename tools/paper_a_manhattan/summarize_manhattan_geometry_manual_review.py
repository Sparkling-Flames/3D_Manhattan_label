"""Summarize M15.5 manual review for Manhattan geometry-debug candidates.

This utility consumes the offline manual-review CSV produced from the M15.4
visual review sheet. It writes smoke-only sidecars and does not read or modify
Label Studio exports, annotations, routing, formal g_t, worker quality metrics,
or P1/C1/C2/T1/V1 artifacts.
"""

from __future__ import annotations

import argparse
import csv
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Mapping, Sequence


VALID_PLAUSIBLE = {"yes", "no", "unsure", ""}
VALID_LIKELY_ISSUE = {"annotation_geometry", "algorithm_overfit", "scope_disagreement", "unclear", ""}
REQUIRED_FIELDS = (
    "task_id",
    "annotation_id",
    "plausible_candidate",
    "likely_issue",
    "reviewer_note",
)
LARGE_DELTA_THRESHOLD = 5.0


def _clean(value: Any) -> str:
    return str(value or "").strip()


def _clean_choice(value: Any) -> str:
    return _clean(value).lower()


def _as_float(value: Any) -> float | None:
    text = _clean(value)
    if not text:
        return None
    try:
        return float(text)
    except ValueError:
        return None


def load_manual_review_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        missing_columns = [field for field in REQUIRED_FIELDS if field not in (reader.fieldnames or [])]
        if missing_columns:
            raise ValueError(f"{path}: missing required columns: {', '.join(missing_columns)}")
        rows = [{key: _clean(value) for key, value in row.items()} for row in reader]
    validate_rows(rows, path)
    return rows


def validate_rows(rows: Sequence[Mapping[str, str]], path: Path | None = None) -> None:
    label = str(path) if path else "<manual_review_csv>"
    for index, row in enumerate(rows, start=2):
        plausible = _clean_choice(row.get("plausible_candidate"))
        if plausible not in VALID_PLAUSIBLE:
            raise ValueError(
                f"{label}:{index}: invalid plausible_candidate={row.get('plausible_candidate')!r}; "
                "expected yes/no/unsure or empty"
            )
        likely_issue = _clean_choice(row.get("likely_issue"))
        if likely_issue not in VALID_LIKELY_ISSUE:
            raise ValueError(
                f"{label}:{index}: invalid likely_issue={row.get('likely_issue')!r}; "
                "expected annotation_geometry/algorithm_overfit/scope_disagreement/unclear or empty"
            )


def _is_completed(row: Mapping[str, str]) -> bool:
    return bool(_clean_choice(row.get("plausible_candidate"))) and bool(_clean_choice(row.get("likely_issue")))


def _is_high_risk(row: Mapping[str, str]) -> bool:
    reason = _clean_choice(row.get("problem_reason"))
    max_abs_delta = _as_float(row.get("max_abs_delta"))
    return (
        reason in {"large_candidate_delta", "self_crossing_candidate"}
        or (max_abs_delta is not None and max_abs_delta >= LARGE_DELTA_THRESHOLD)
    )


def _count_choices(rows: Sequence[Mapping[str, str]], field: str, choices: Sequence[str]) -> dict[str, int]:
    counts = Counter(_clean_choice(row.get(field)) for row in rows if _clean_choice(row.get(field)))
    return {choice: counts.get(choice, 0) for choice in choices}


def _missing_field_counts(rows: Sequence[Mapping[str, str]]) -> dict[str, int]:
    return {
        field: sum(1 for row in rows if not _clean(row.get(field)))
        for field in ("plausible_candidate", "likely_issue", "reviewer_note")
    }


def _task_interpretation(task_id: str, plausible_counts: Mapping[str, int], likely_counts: Mapping[str, int]) -> str:
    if task_id == "2948":
        return "Task 2948 is mostly stable except a few geometry-structure failures."
    if task_id == "2949":
        return "Task 2949 shows mixed behavior and is the main blocker."
    yes = plausible_counts.get("yes", 0)
    no = plausible_counts.get("no", 0)
    unsure = plausible_counts.get("unsure", 0)
    algorithm = likely_counts.get("algorithm_overfit", 0)
    if algorithm:
        return "Mixed manual review with algorithm_overfit evidence."
    if yes > no + unsure:
        return "Mostly plausible expert-side review candidates."
    return "Mixed or incomplete manual review."


def _summarize_task(task_id: str, rows: Sequence[Mapping[str, str]]) -> dict[str, Any]:
    completed_rows = [row for row in rows if _is_completed(row)]
    plausible_counts = _count_choices(rows, "plausible_candidate", ("yes", "no", "unsure"))
    likely_counts = _count_choices(
        rows,
        "likely_issue",
        ("annotation_geometry", "algorithm_overfit", "scope_disagreement", "unclear"),
    )
    high_risk_algorithm_rows = [
        {
            "task_id": _clean(row.get("task_id")),
            "annotation_id": _clean(row.get("annotation_id")),
            "plausible_candidate": _clean_choice(row.get("plausible_candidate")),
            "likely_issue": _clean_choice(row.get("likely_issue")),
            "problem_reason": _clean(row.get("problem_reason")),
            "max_abs_delta": _clean(row.get("max_abs_delta")),
        }
        for row in rows
        if _is_high_risk(row)
        and _clean_choice(row.get("likely_issue")) == "algorithm_overfit"
        and _clean_choice(row.get("plausible_candidate")) in {"unsure", "no"}
    ]
    return {
        "task_id": task_id,
        "n_review_rows": len(rows),
        "n_review_completed": len(completed_rows),
        "n_review_missing": len(rows) - len(completed_rows),
        "plausible_candidate_counts": plausible_counts,
        "likely_issue_counts": likely_counts,
        "no_and_algorithm_overfit_count": sum(
            1
            for row in rows
            if _clean_choice(row.get("plausible_candidate")) == "no"
            and _clean_choice(row.get("likely_issue")) == "algorithm_overfit"
        ),
        "unsure_and_algorithm_overfit_count": sum(
            1
            for row in rows
            if _clean_choice(row.get("plausible_candidate")) == "unsure"
            and _clean_choice(row.get("likely_issue")) == "algorithm_overfit"
        ),
        "high_risk_algorithm_overfit_rows": high_risk_algorithm_rows,
        "interpretation": _task_interpretation(task_id, plausible_counts, likely_counts),
    }


def _decision_recommendation(rows: Sequence[Mapping[str, str]]) -> str:
    high_risk_algorithm_uncertain = any(
        _is_high_risk(row)
        and _clean_choice(row.get("likely_issue")) == "algorithm_overfit"
        and _clean_choice(row.get("plausible_candidate")) in {"unsure", "no"}
        for row in rows
    )
    any_algorithm_uncertain = any(
        _clean_choice(row.get("likely_issue")) == "algorithm_overfit"
        and _clean_choice(row.get("plausible_candidate")) in {"unsure", "no"}
        for row in rows
    )
    plausible_counts = _count_choices(rows, "plausible_candidate", ("yes", "no", "unsure"))
    likely_counts = _count_choices(
        rows,
        "likely_issue",
        ("annotation_geometry", "algorithm_overfit", "scope_disagreement", "unclear"),
    )
    mostly_yes = plausible_counts["yes"] > plausible_counts["no"] + plausible_counts["unsure"]
    if high_risk_algorithm_uncertain or any_algorithm_uncertain:
        return "m16_blocked"
    if mostly_yes and likely_counts["algorithm_overfit"] == 0:
        return "m16_limited_expert_only_discussion"
    return "m16_blocked"


def summarize_manual_review(rows: Sequence[Mapping[str, str]], *, source_csv: str | None = None) -> dict[str, Any]:
    completed_rows = [row for row in rows if _is_completed(row)]
    grouped: dict[str, list[Mapping[str, str]]] = defaultdict(list)
    for row in rows:
        grouped[_clean(row.get("task_id"))].append(row)
    task_level_summary = {
        task_id: _summarize_task(task_id, task_rows)
        for task_id, task_rows in sorted(grouped.items())
    }
    summary = {
        "summary_version": "manhattan_geometry_manual_review_m15_5_v1",
        "source_csv": source_csv,
        "n_review_rows": len(rows),
        "n_review_completed": len(completed_rows),
        "n_review_missing": len(rows) - len(completed_rows),
        "missing_manual_field_counts": _missing_field_counts(rows),
        "plausible_candidate_counts": _count_choices(rows, "plausible_candidate", ("yes", "no", "unsure")),
        "likely_issue_counts": _count_choices(
            rows,
            "likely_issue",
            ("annotation_geometry", "algorithm_overfit", "scope_disagreement", "unclear"),
        ),
        "no_and_algorithm_overfit_count": sum(
            1
            for row in rows
            if _clean_choice(row.get("plausible_candidate")) == "no"
            and _clean_choice(row.get("likely_issue")) == "algorithm_overfit"
        ),
        "unsure_and_algorithm_overfit_count": sum(
            1
            for row in rows
            if _clean_choice(row.get("plausible_candidate")) == "unsure"
            and _clean_choice(row.get("likely_issue")) == "algorithm_overfit"
        ),
        "task_level_summary": task_level_summary,
        "task_2948_summary": task_level_summary.get("2948", {}),
        "task_2949_summary": task_level_summary.get("2949", {}),
        "m16_decision_recommendation": _decision_recommendation(rows),
        "guardrails": [
            "manual review aggregation is visual-review only",
            "Candidate is useful for expert-side review.",
            "Candidate is not stable enough for UI ghost candidate.",
            "no routing",
            "no worker quality metric",
            "no P1/C1/C2/T1/V1 artifact",
            "never recommend annotator-facing UI at this stage",
        ],
    }
    return summary


def write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def render_report(summary: Mapping[str, Any]) -> str:
    task_2948 = summary.get("task_2948_summary", {})
    task_2949 = summary.get("task_2949_summary", {})
    lines = [
        "# Manhattan geometry manual review summary",
        "",
        "This M15.5 summary is smoke-only / expert-side review evidence. It does not write annotations, "
        "does not change formal `g_t`, has no routing role, is no worker quality metric, "
        "and is not a `P1/C1/C2/T1/V1` artifact.",
        "",
        "Candidate is useful for expert-side review.",
        "Candidate is not stable enough for UI ghost candidate.",
        "Task 2948 is mostly stable except a few geometry-structure failures.",
        "Task 2949 shows mixed behavior and is the main blocker.",
        "M16 remains blocked until candidate gating is designed and validated.",
        "",
        "## Counts",
        "",
        f"- source_csv: `{summary.get('source_csv')}`",
        f"- n_review_rows: {summary.get('n_review_rows')}",
        f"- n_review_completed: {summary.get('n_review_completed')}",
        f"- n_review_missing: {summary.get('n_review_missing')}",
        f"- plausible_candidate_counts: `{summary.get('plausible_candidate_counts')}`",
        f"- likely_issue_counts: `{summary.get('likely_issue_counts')}`",
        f"- no_and_algorithm_overfit_count: {summary.get('no_and_algorithm_overfit_count')}",
        f"- unsure_and_algorithm_overfit_count: {summary.get('unsure_and_algorithm_overfit_count')}",
        f"- m16_decision_recommendation: `{summary.get('m16_decision_recommendation')}`",
        "",
        "## Task 2948",
        "",
        f"- summary: `{task_2948}`",
        "",
        "## Task 2949",
        "",
        f"- summary: `{task_2949}`",
        "",
        "## M16 Decision",
        "",
        "M16 ghost candidate UI remains blocked. The only acceptable next step is offline or expert-side "
        "discussion of candidate gating; no annotator-facing UI, no writeback, no routing, and no worker quality use.",
        "",
    ]
    return "\n".join(lines)


def write_report(path: Path, summary: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(render_report(summary), encoding="utf-8")


def output_paths(output_dir: Path, date: str) -> tuple[Path, Path]:
    return (
        output_dir / f"smoke_geometry_manual_review_summary_{date}.json",
        output_dir / f"smoke_geometry_manual_review_report_{date}.md",
    )


def run(input_path: Path, output_dir: Path, date: str) -> dict[str, Any]:
    rows = load_manual_review_csv(input_path)
    summary = summarize_manual_review(rows, source_csv=str(input_path))
    summary_path, report_path = output_paths(output_dir, date)
    write_json(summary_path, summary)
    write_report(report_path, summary)
    return {"summary": summary, "outputs": {"summary": str(summary_path), "report": str(report_path)}}


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, type=Path, help="Manual review CSV.")
    parser.add_argument("--output-dir", required=True, type=Path, help="Output directory.")
    parser.add_argument("--date", required=True, help="Date suffix for output sidecars.")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_arg_parser().parse_args(argv)
    result = run(args.input, args.output_dir, args.date)
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
