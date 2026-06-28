from __future__ import annotations

import argparse
import csv
import json
from collections import defaultdict
from pathlib import Path

DEFAULT_INPUT = Path("analysis_results/prescreen_closeout/prescreen_canonical_annotations.csv")
DEFAULT_OUTPUT = Path("analysis_results/prescreen_closeout/prescreen_active_time_source_audit.csv")


def _condition(row: dict[str, str]) -> str:
    text = " ".join([row.get("dataset_group", ""), row.get("condition", "")]).lower()
    if "manual" in text:
        return "manual"
    if "semi" in text:
        return "semi"
    if "oos" in text:
        return "oos"
    return "unknown"


def _load_completion(path: Path | None) -> dict[str, dict[str, str]]:
    if not path or not path.exists():
        return {}
    with path.open("r", newline="", encoding="utf-8") as f:
        return {str(row.get("annotator_id") or "").strip(): row for row in csv.DictReader(f)}


def build_active_time_source_audit(canonical_csv: Path, completion_csv: Path | None = None) -> list[dict[str, object]]:
    completion = _load_completion(completion_csv)
    buckets: dict[tuple[str, str], dict[str, int]] = defaultdict(
        lambda: {"n_rows": 0, "n_log": 0, "n_lead_time_fallback": 0, "n_missing": 0}
    )
    with canonical_csv.open("r", newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            annotator_id = str(row.get("annotator_id") or "unknown")
            condition = _condition(row)
            source = str(row.get("active_time_source") or "missing")
            bucket = buckets[(annotator_id, condition)]
            bucket["n_rows"] += 1
            if source == "log":
                bucket["n_log"] += 1
            elif source == "lead_time_fallback":
                bucket["n_lead_time_fallback"] += 1
            else:
                bucket["n_missing"] += 1

    rows: list[dict[str, object]] = []
    for (annotator_id, condition), counts in sorted(buckets.items(), key=lambda item: (item[0][0], item[0][1])):
        n_rows = counts["n_rows"]
        n_log = counts["n_log"]
        n_fallback = counts["n_lead_time_fallback"]
        completion_row = completion.get(annotator_id, {})
        rows.append(
            {
                "annotator_id": annotator_id,
                "language": completion_row.get("language", "unknown"),
                "condition": condition,
                "completion_status": completion_row.get("completion_status", ""),
                "eligible_for_primary_prescreen_candidate": completion_row.get("eligible_for_primary_prescreen_candidate", ""),
                "n_rows": n_rows,
                "n_log": n_log,
                "n_lead_time_fallback": n_fallback,
                "n_missing": counts["n_missing"],
                "log_coverage_rate": round(n_log / n_rows, 6) if n_rows else 0.0,
                "fallback_rate": round(n_fallback / n_rows, 6) if n_rows else 0.0,
                "primary_active_time_eligible_count": n_log,
                "sensitivity_active_time_eligible_count": n_log + n_fallback,
            }
        )
    return rows


def _write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "annotator_id",
        "language",
        "condition",
        "completion_status",
        "eligible_for_primary_prescreen_candidate",
        "n_rows",
        "n_log",
        "n_lead_time_fallback",
        "n_missing",
        "log_coverage_rate",
        "fallback_rate",
        "primary_active_time_eligible_count",
        "sensitivity_active_time_eligible_count",
    ]
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--canonical-csv", default=str(DEFAULT_INPUT))
    parser.add_argument("--completion-csv", default=None)
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    args = parser.parse_args(argv)

    rows = build_active_time_source_audit(Path(args.canonical_csv), Path(args.completion_csv) if args.completion_csv else None)
    output = Path(args.output)
    _write_csv(output, rows)
    summary = {
        "output": str(output),
        "n_annotators": len({str(r["annotator_id"]) for r in rows}),
        "n_annotator_condition_rows": len(rows),
        "n_rows": sum(int(r["n_rows"]) for r in rows),
        "n_log": sum(int(r["n_log"]) for r in rows),
        "n_lead_time_fallback": sum(int(r["n_lead_time_fallback"]) for r in rows),
        "n_missing": sum(int(r["n_missing"]) for r in rows),
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
