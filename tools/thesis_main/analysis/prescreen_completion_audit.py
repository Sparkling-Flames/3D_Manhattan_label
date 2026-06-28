from __future__ import annotations

import argparse
import csv
import json
from collections import defaultdict
from pathlib import Path
from typing import Any

DEFAULT_CANONICAL = Path("analysis_results/prescreen_closeout/prescreen_canonical_annotations.csv")
DEFAULT_ROSTER = Path("analysis_results/prescreen_closeout/prescreen_worker_roster.csv")
DEFAULT_OUTPUT = Path("analysis_results/prescreen_closeout/prescreen_completion_audit.csv")

FIELDS = [
    "annotator_id",
    "language",
    "manual_observed",
    "semi_observed",
    "oos_observed",
    "total_observed",
    "manual_expected",
    "semi_expected",
    "oos_expected",
    "total_expected",
    "manual_missing",
    "semi_missing",
    "oos_missing",
    "total_missing",
    "completion_rate",
    "completion_status",
    "will_continue",
    "dropout",
    "known_bad_or_process_risk",
    "eligible_for_final_completion_denominator",
    "eligible_for_primary_prescreen_candidate",
    "notes",
]


def _truthy(value: Any) -> bool:
    return str(value or "").strip().lower() in {"1", "true", "yes", "y"}


def _int(value: Any) -> int:
    text = str(value or "").strip()
    return int(float(text)) if text else 0


def _condition(row: dict[str, str]) -> str:
    text = " ".join([row.get("dataset_group", ""), row.get("condition", "")]).lower()
    if "manual" in text:
        return "manual"
    if "semi" in text:
        return "semi"
    if "oos" in text:
        return "oos"
    return "unknown"


def load_roster(path: Path) -> dict[str, dict[str, str]]:
    with path.open("r", newline="", encoding="utf-8") as f:
        return {str(row.get("annotator_id") or "").strip(): row for row in csv.DictReader(f) if str(row.get("annotator_id") or "").strip()}


def observed_counts(canonical_csv: Path) -> dict[str, dict[str, int]]:
    counts: dict[str, dict[str, int]] = defaultdict(lambda: {"manual": 0, "semi": 0, "oos": 0, "unknown": 0})
    with canonical_csv.open("r", newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            counts[str(row.get("annotator_id") or "unknown")][_condition(row)] += 1
    return counts


def _status(
    observed: int,
    expected: int,
    known_bad: bool,
    will_continue: bool,
    dropout: bool,
    roster_missing: bool,
    override: str,
) -> str:
    if override:
        return override
    if roster_missing:
        return "unknown_roster"
    if observed > expected:
        return "unexpected_extra"
    if dropout:
        return "dropout_no_future"
    if not will_continue and observed < expected:
        return "incomplete_excluded"
    if observed == expected and known_bad:
        return "known_bad_complete"
    if observed == expected:
        return "complete"
    if will_continue and observed < expected:
        return "pending_completion"
    return "incomplete_excluded"


def build_completion_audit(
    canonical_csv: Path,
    roster_csv: Path,
    *,
    exclude_known_bad_from_denominator: bool = True,
) -> list[dict[str, object]]:
    roster = load_roster(roster_csv)
    counts = observed_counts(canonical_csv)
    annotator_ids = sorted(set(roster) | set(counts), key=lambda x: int(x) if x.isdigit() else x)
    rows: list[dict[str, object]] = []

    for annotator_id in annotator_ids:
        roster_row = roster.get(annotator_id, {})
        roster_missing = annotator_id not in roster
        manual_observed = counts[annotator_id]["manual"]
        semi_observed = counts[annotator_id]["semi"]
        oos_observed = counts[annotator_id]["oos"]
        total_observed = manual_observed + semi_observed + oos_observed + counts[annotator_id]["unknown"]
        manual_expected = _int(roster_row.get("expected_manual"))
        semi_expected = _int(roster_row.get("expected_semi"))
        oos_expected = _int(roster_row.get("expected_oos"))
        total_expected = _int(roster_row.get("expected_total")) or manual_expected + semi_expected + oos_expected
        known_bad = _truthy(roster_row.get("known_bad_or_process_risk"))
        will_continue = _truthy(roster_row.get("will_continue"))
        dropout = _truthy(roster_row.get("dropout"))
        exclude_candidate = _truthy(roster_row.get("exclude_from_primary_candidate"))
        status = _status(
            total_observed,
            total_expected,
            known_bad,
            will_continue,
            dropout,
            roster_missing,
            str(roster_row.get("completion_status_override") or "").strip(),
        )
        denominator_ok = (not roster_missing) and (not dropout) and (not (known_bad and exclude_known_bad_from_denominator))
        primary_ok = denominator_ok and (not exclude_candidate) and status == "complete"
        rows.append(
            {
                "annotator_id": annotator_id,
                "language": roster_row.get("language", "unknown") if not roster_missing else "unknown",
                "manual_observed": manual_observed,
                "semi_observed": semi_observed,
                "oos_observed": oos_observed,
                "total_observed": total_observed,
                "manual_expected": manual_expected,
                "semi_expected": semi_expected,
                "oos_expected": oos_expected,
                "total_expected": total_expected,
                "manual_missing": max(manual_expected - manual_observed, 0),
                "semi_missing": max(semi_expected - semi_observed, 0),
                "oos_missing": max(oos_expected - oos_observed, 0),
                "total_missing": max(total_expected - total_observed, 0),
                "completion_rate": round(total_observed / total_expected, 6) if total_expected else "",
                "completion_status": status,
                "will_continue": will_continue,
                "dropout": dropout,
                "known_bad_or_process_risk": known_bad,
                "eligible_for_final_completion_denominator": denominator_ok,
                "eligible_for_primary_prescreen_candidate": primary_ok,
                "notes": roster_row.get("notes", "") if not roster_missing else "appears_in_canonical_but_missing_from_roster",
            }
        )
    return rows


def write_completion_audit(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(rows)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--canonical-csv", default=str(DEFAULT_CANONICAL))
    parser.add_argument("--roster-csv", default=str(DEFAULT_ROSTER))
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    parser.add_argument("--include-known-bad-in-denominator", action="store_true")
    args = parser.parse_args(argv)

    rows = build_completion_audit(
        Path(args.canonical_csv),
        Path(args.roster_csv),
        exclude_known_bad_from_denominator=not args.include_known_bad_in_denominator,
    )
    output = Path(args.output)
    write_completion_audit(output, rows)
    summary = {
        "output": str(output),
        "n_workers": len(rows),
        "completion_status_counts": {status: sum(r["completion_status"] == status for r in rows) for status in sorted({str(r["completion_status"]) for r in rows})},
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
