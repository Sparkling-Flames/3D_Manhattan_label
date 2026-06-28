from __future__ import annotations

import argparse
import csv
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

DEFAULT_UNDERCOVERAGE = Path("analysis_results/prescreen_closeout/prescreen_undercoverage_risk_audit.csv")
DEFAULT_ALIGNMENT = Path("analysis_results/prescreen_closeout/prescreen_worker_gold_alignment_audit.csv")
DEFAULT_DUPLICATE = Path("analysis_results/prescreen_closeout/prescreen_duplicate_annotation_audit.csv")
DEFAULT_OUTPUT_DIR = Path("analysis_results/prescreen_closeout")

AUDIT_FIELDS = [
    "task_id",
    "dataset_group",
    "condition",
    "n_workers_evaluable",
    "n_undercoverage_high_or_medium",
    "majority_undercoverage_risk",
    "n_minority_full_room_candidates",
    "has_minority_full_room_candidate",
    "copy_cluster_dominated_consensus",
    "low_time_dominated_consensus",
    "gold_reference_disagrees_with_worker_majority",
    "semi_trap_conflict",
    "consensus_guard_bucket",
    "manual_review_required",
    "dry_run",
    "notes",
]


def _safe(value: Any) -> str:
    return str(value or "").strip()


def _truthy(value: Any) -> bool:
    return _safe(value).lower() in {"1", "true", "yes", "y"}


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


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=AUDIT_FIELDS)
        writer.writeheader()
        writer.writerows(rows)


def build_consensus_guard_audit(
    undercoverage_csv: Path,
    alignment_csv: Path,
    duplicate_csv: Path,
    exact_copy_csv: Path | None = None,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    under = _load_csv(undercoverage_csv)
    _load_csv(alignment_csv)
    duplicates = _load_csv(duplicate_csv)
    exact_copy, exact_missing = _load_optional_csv(exact_copy_csv)
    by_task: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in under:
        by_task[_safe(row.get("task_id"))].append(row)
    duplicate_by_task = Counter(
        _safe(row.get("task_id"))
        for row in duplicates
        if int(float(_safe(row.get("duplicate_group_size")) or 0)) > 1 or _safe(row.get("duplicate_geometry_type")) == "duplicate_same_geometry"
    )
    low_time_tasks = {
        _safe(row.get("task_id"))
        for row in exact_copy
        if _safe(row.get("recommended_action") or row.get("copy_audit_recommended_action")) == "fail_recommended"
    }
    out: list[dict[str, Any]] = []
    for task_id, rows in sorted(by_task.items()):
        evaluable = [row for row in rows if _safe(row.get("undercoverage_risk_level")) != "not_evaluable"]
        n_under = sum(1 for row in evaluable if _safe(row.get("undercoverage_risk_level")) in {"high", "medium"})
        majority = any(_truthy(row.get("task_majority_undercoverage_risk")) for row in rows)
        n_minority = sum(1 for row in rows if _truthy(row.get("minority_full_room_candidate")))
        copy_dominated = bool(evaluable and duplicate_by_task[task_id] >= max(1, len(evaluable) / 2))
        low_time = task_id in low_time_tasks
        insufficient = len(evaluable) < 2
        gold_conflict = majority
        semi_conflict = _safe(rows[0].get("dataset_group")) == "PreScreen_semi" and (majority or n_under > 0)
        if insufficient:
            bucket = "insufficient_evidence"
        elif n_minority:
            bucket = "minority_full_room_protection"
        elif majority:
            bucket = "majority_undercoverage_guard"
        elif copy_dominated:
            bucket = "copy_risk_guard"
        elif low_time:
            bucket = "low_time_guard"
        elif gold_conflict:
            bucket = "gold_reference_conflict_guard"
        else:
            bucket = "consensus_safe"
        out.append(
            {
                "task_id": task_id,
                "dataset_group": _safe(rows[0].get("dataset_group")),
                "condition": _safe(rows[0].get("condition")),
                "n_workers_evaluable": len(evaluable),
                "n_undercoverage_high_or_medium": n_under,
                "majority_undercoverage_risk": majority,
                "n_minority_full_room_candidates": n_minority,
                "has_minority_full_room_candidate": bool(n_minority),
                "copy_cluster_dominated_consensus": copy_dominated,
                "low_time_dominated_consensus": low_time,
                "gold_reference_disagrees_with_worker_majority": gold_conflict,
                "semi_trap_conflict": semi_conflict,
                "consensus_guard_bucket": bucket,
                "manual_review_required": bucket != "consensus_safe",
                "dry_run": True,
                "notes": "dry-run guard only; no consensus materialization",
            }
        )
    summary = {
        "dry_run": True,
        "task_rows": len(out),
        "consensus_guard_bucket_counts": dict(Counter(str(row["consensus_guard_bucket"]) for row in out)),
        "manual_review_required_count": sum(bool(row["manual_review_required"]) for row in out),
        "optional_exact_copy_summary_missing": exact_missing,
        "forbidden_outputs_generated": False,
        "forbidden_metric_field_count": sum(1 for row in out for key in row if "score" in key.lower()),
    }
    return out, summary


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--undercoverage-csv", default=str(DEFAULT_UNDERCOVERAGE))
    parser.add_argument("--alignment-csv", default=str(DEFAULT_ALIGNMENT))
    parser.add_argument("--duplicate-csv", default=str(DEFAULT_DUPLICATE))
    parser.add_argument("--exact-copy-csv", default="")
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    args = parser.parse_args(argv)
    rows, summary = build_consensus_guard_audit(
        Path(args.undercoverage_csv),
        Path(args.alignment_csv),
        Path(args.duplicate_csv),
        Path(args.exact_copy_csv) if args.exact_copy_csv else None,
    )
    out_dir = Path(args.output_dir)
    audit_path = out_dir / "prescreen_consensus_guard_audit.csv"
    summary_path = out_dir / "prescreen_consensus_guard_summary.json"
    _write_csv(audit_path, rows)
    summary.update({"consensus_guard_audit_csv": str(audit_path), "consensus_guard_summary_json": str(summary_path)})
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
