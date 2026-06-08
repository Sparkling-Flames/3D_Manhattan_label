#!/usr/bin/env python
"""Validate Paper B B0 relabel audit CSVs without changing them.

This validator is intentionally partial. It checks schema and vocabularies,
then reports conservative warnings for rows that could contaminate B1 targets.
It does not infer visual judgments and does not compute final B0 conclusions.
"""

from __future__ import annotations

import argparse
import csv
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
import re
import sys
from typing import Iterable


ALLOWED_SOURCE_GROUPS = {
    "hard_prediction_failure",
    "highest_g_score",
    "nominal_prediction_structure",
    "soft_prediction_complexity",
}

ALLOWED_EXPERT_VERDICTS = {
    "accept_bilayout_enclosed",
    "accept_with_minor_fix",
    "reject_undercoverage",
    "reject_ambiguous_or_oos",
    "reject_model_error_needs_manual_fix",
}

NA_VALUES = {"", "na", "n/a", "nan", "none", "null"}
BOOL_VALUES = {"true", "false", *NA_VALUES}
SCORE_VALUES = {"0", "1", "2", *NA_VALUES}

REQUIRED_COLUMNS = [
    "task_id",
    "image_id",
    "scene_id",
    "source_group",
    "dedup_primary",
    "hohonet_crossdoor_score",
    "bilayout_crossdoor_score",
    "overextend_reduced",
    "overparse_reduced",
    "bilayout_undercoverage",
    "bilayout_new_error",
    "both_wrong",
    "oos_suspect",
    "open_boundary_ambiguity",
    "expert_verdict",
    "usable_for_B1",
    "audit_notes",
]

BOOLEAN_COLUMNS = [
    "dedup_primary",
    "overextend_reduced",
    "overparse_reduced",
    "bilayout_undercoverage",
    "bilayout_new_error",
    "both_wrong",
    "oos_suspect",
    "open_boundary_ambiguity",
    "usable_for_B1",
]

OPTIONAL_BOOLEAN_COLUMNS = [
    "is_duplicate",
    "manual_relabel_candidate",
    "usable_after_manual_relabel",
]

SCORE_COLUMNS = ["hohonet_crossdoor_score", "bilayout_crossdoor_score"]

MINOR_FIX_RED_FLAG_RE = re.compile(
    r"moderate|major|redraw|relabel|重画|中等|大幅|重新标注",
    flags=re.IGNORECASE,
)


@dataclass
class ValidationResult:
    total_rows: int
    dedup_primary_rows: int
    reviewed_primary_rows: int
    unreviewed_primary_rows: int
    rows_by_expert_verdict: Counter[str]
    usable_for_b1_true_rows: int
    manual_relabel_candidate_rows: int | None
    errors: list[str]
    warnings: list[str]


def _norm(value: object) -> str:
    return str(value or "").strip()


def _norm_lower(value: object) -> str:
    return _norm(value).lower()


def _is_true(value: object) -> bool:
    return _norm_lower(value) == "true"


def _is_blank_or_na(value: object) -> bool:
    return _norm_lower(value) in NA_VALUES


def _row_label(row_number: int, row: dict[str, str]) -> str:
    task_id = _norm(row.get("task_id"))
    source_group = _norm(row.get("source_group"))
    return f"row {row_number} source_group={source_group!r} task_id={task_id!r}"


def read_csv_rows(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    with path.open(newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        fieldnames = reader.fieldnames or []
        rows = list(reader)
    return fieldnames, rows


def validate_csv(path: Path) -> ValidationResult:
    fieldnames, rows = read_csv_rows(path)
    field_set = set(fieldnames)
    errors: list[str] = []
    warnings: list[str] = []

    missing = [col for col in REQUIRED_COLUMNS if col not in field_set]
    if missing:
        errors.append(f"missing required columns: {', '.join(missing)}")

    boolean_columns = [c for c in BOOLEAN_COLUMNS if c in field_set]
    boolean_columns.extend(c for c in OPTIONAL_BOOLEAN_COLUMNS if c in field_set)

    rows_by_verdict: Counter[str] = Counter()
    dedup_primary_rows = 0
    reviewed_primary_rows = 0
    unreviewed_primary_rows = 0
    usable_for_b1_true_rows = 0
    manual_relabel_candidate_rows = 0 if "manual_relabel_candidate" in field_set else None

    for row_idx, row in enumerate(rows, start=2):
        label = _row_label(row_idx, row)

        source_group = _norm(row.get("source_group"))
        if source_group and source_group not in ALLOWED_SOURCE_GROUPS:
            errors.append(f"{label}: invalid source_group={source_group!r}")

        verdict = _norm(row.get("expert_verdict"))
        verdict_key = "<blank>" if _is_blank_or_na(verdict) else verdict
        rows_by_verdict[verdict_key] += 1
        if not _is_blank_or_na(verdict) and verdict not in ALLOWED_EXPERT_VERDICTS:
            errors.append(f"{label}: invalid expert_verdict={verdict!r}")

        for col in boolean_columns:
            value = _norm_lower(row.get(col))
            if value not in BOOL_VALUES:
                errors.append(f"{label}: invalid boolean value {col}={row.get(col)!r}")

        for col in SCORE_COLUMNS:
            if col in field_set:
                value = _norm_lower(row.get(col))
                if value not in SCORE_VALUES:
                    errors.append(f"{label}: invalid crossdoor score {col}={row.get(col)!r}")

        is_primary = _is_true(row.get("dedup_primary"))
        is_reviewed = not _is_blank_or_na(verdict)
        usable_for_b1 = _is_true(row.get("usable_for_B1"))

        if is_primary:
            dedup_primary_rows += 1
            if is_reviewed:
                reviewed_primary_rows += 1
            else:
                unreviewed_primary_rows += 1

        if usable_for_b1:
            usable_for_b1_true_rows += 1

        if manual_relabel_candidate_rows is not None and _is_true(row.get("manual_relabel_candidate")):
            manual_relabel_candidate_rows += 1

        if verdict in {
            "reject_model_error_needs_manual_fix",
            "reject_undercoverage",
            "reject_ambiguous_or_oos",
        } and usable_for_b1:
            warnings.append(f"{label}: {verdict} should not have usable_for_B1=true")

        if _is_true(row.get("both_wrong")) and usable_for_b1:
            warnings.append(f"{label}: both_wrong=true should not have usable_for_B1=true")

        if _is_true(row.get("oos_suspect")) and usable_for_b1:
            warnings.append(f"{label}: unresolved oos_suspect=true should not have usable_for_B1=true")

        if _is_true(row.get("bilayout_undercoverage")) and verdict == "accept_bilayout_enclosed":
            warnings.append(f"{label}: bilayout_undercoverage=true conflicts with accept_bilayout_enclosed")

        if _is_true(row.get("bilayout_new_error")) and verdict == "accept_bilayout_enclosed":
            warnings.append(f"{label}: bilayout_new_error=true conflicts with accept_bilayout_enclosed")

        notes = _norm(row.get("audit_notes"))
        if verdict == "accept_with_minor_fix" and MINOR_FIX_RED_FLAG_RE.search(notes):
            warnings.append(
                f"{label}: accept_with_minor_fix has audit_notes suggesting a moderate/major relabel"
            )

    return ValidationResult(
        total_rows=len(rows),
        dedup_primary_rows=dedup_primary_rows,
        reviewed_primary_rows=reviewed_primary_rows,
        unreviewed_primary_rows=unreviewed_primary_rows,
        rows_by_expert_verdict=rows_by_verdict,
        usable_for_b1_true_rows=usable_for_b1_true_rows,
        manual_relabel_candidate_rows=manual_relabel_candidate_rows,
        errors=errors,
        warnings=warnings,
    )


def render_report(input_path: Path, result: ValidationResult) -> str:
    lines = [
        "# B0 Partial Validation Report",
        "",
        "Status: Paper B / non-thesis-facing validator output.",
        "",
        f"Input CSV: `{input_path.as_posix()}`",
        "",
        "This report validates schema and vocabularies only. It does not infer visual judgments, does not compute final B0 descriptive metrics, and does not treat Bi-Layout cue as an OOS classifier.",
        "",
        "## Counts",
        "",
        f"- total_rows: {result.total_rows}",
        f"- dedup_primary_rows: {result.dedup_primary_rows}",
        f"- reviewed_primary_rows: {result.reviewed_primary_rows}",
        f"- unreviewed_primary_rows: {result.unreviewed_primary_rows}",
        f"- usable_for_B1_true_rows: {result.usable_for_b1_true_rows}",
    ]
    if result.manual_relabel_candidate_rows is not None:
        lines.append(f"- manual_relabel_candidate_rows: {result.manual_relabel_candidate_rows}")
    else:
        lines.append("- manual_relabel_candidate_rows: field not present")

    lines.extend(["", "## Rows By Expert Verdict", ""])
    for verdict, count in sorted(result.rows_by_expert_verdict.items()):
        lines.append(f"- `{verdict}`: {count}")

    lines.extend(["", "## Errors", ""])
    if result.errors:
        lines.extend(f"- {err}" for err in result.errors)
    else:
        lines.append("- none")

    lines.extend(["", "## Warnings", ""])
    if result.warnings:
        lines.extend(f"- {warning}" for warning in result.warnings)
    else:
        lines.append("- none")

    lines.extend(
        [
            "",
            "## Boundary",
            "",
            "- Paper B / B0 audit only.",
            "- No model training.",
            "- No A-line `P1 / C1 / C2 / T1 / V1` effect.",
            "- No formal `g_t`, `d_t`, routing, OOS classifier, or Label Studio production UI effect.",
        ]
    )
    return "\n".join(lines) + "\n"


def print_summary(result: ValidationResult) -> None:
    print(f"total_rows {result.total_rows}")
    print(f"dedup_primary_rows {result.dedup_primary_rows}")
    print(f"reviewed_primary_rows {result.reviewed_primary_rows}")
    print(f"unreviewed_primary_rows {result.unreviewed_primary_rows}")
    print(f"usable_for_B1_true_rows {result.usable_for_b1_true_rows}")
    if result.manual_relabel_candidate_rows is not None:
        print(f"manual_relabel_candidate_rows {result.manual_relabel_candidate_rows}")
    else:
        print("manual_relabel_candidate_rows field_not_present")
    print(f"errors {len(result.errors)}")
    print(f"warnings {len(result.warnings)}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, type=Path, help="B0 relabel audit CSV path")
    parser.add_argument("--report-md", type=Path, help="Optional Markdown report output path")
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Exit nonzero for warnings as well as schema/vocabulary errors",
    )
    return parser


def main(argv: Iterable[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    result = validate_csv(args.input)

    if args.report_md:
        args.report_md.parent.mkdir(parents=True, exist_ok=True)
        args.report_md.write_text(render_report(args.input, result), encoding="utf-8")

    print_summary(result)
    if result.errors:
        for err in result.errors:
            print(f"ERROR: {err}", file=sys.stderr)
        return 2
    if args.strict and result.warnings:
        for warning in result.warnings:
            print(f"WARNING: {warning}", file=sys.stderr)
        return 3
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

