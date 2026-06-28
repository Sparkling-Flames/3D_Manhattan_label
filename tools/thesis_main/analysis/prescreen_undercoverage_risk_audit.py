from __future__ import annotations

import argparse
import csv
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

DEFAULT_ALIGNMENT = Path("analysis_results/prescreen_closeout/prescreen_worker_gold_alignment_audit.csv")
DEFAULT_OUTPUT_DIR = Path("analysis_results/prescreen_closeout")

HIGH_RATIO = 0.55
MEDIUM_RATIO = 0.75
NONE_RATIO = 0.85

AUDIT_FIELDS = [
    "annotator_id",
    "task_id",
    "dataset_group",
    "condition",
    "reference_validation_status",
    "worker_n_corners",
    "reference_n_corners",
    "bbox_area_ratio_to_reference",
    "polygon_area_ratio_to_reference",
    "undercoverage_risk_level",
    "undercoverage_reason",
    "task_majority_undercoverage_risk",
    "minority_full_room_candidate",
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


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=AUDIT_FIELDS)
        writer.writeheader()
        writer.writerows(rows)


def _float(value: Any) -> float | None:
    try:
        return float(_safe(value))
    except ValueError:
        return None


def _risk(row: dict[str, str]) -> tuple[str, str]:
    if not _truthy(row.get("alignment_available")):
        return "not_evaluable", _safe(row.get("alignment_block_reason")) or "alignment_not_available"
    ratio = _float(row.get("bbox_area_ratio_to_reference"))
    if ratio is None:
        return "not_evaluable", "missing_area_ratio"
    worker_n = int(_float(row.get("worker_n_corners")) or 0)
    ref_n = int(_float(row.get("reference_n_corners")) or 0)
    if ratio < HIGH_RATIO and worker_n <= ref_n:
        return "high", "bbox_ratio_below_0_55_and_corner_count_not_larger"
    if ratio < MEDIUM_RATIO:
        return "medium", "bbox_ratio_below_0_75"
    if ratio >= NONE_RATIO:
        return "none", "bbox_ratio_at_least_0_85"
    return "low", "bbox_ratio_between_0_75_and_0_85"


def build_undercoverage_risk_audit(alignment_csv: Path) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    alignment = _load_csv(alignment_csv)
    prepared: list[dict[str, Any]] = []
    ratios_by_task: dict[str, list[float]] = defaultdict(list)
    for row in alignment:
        level, reason = _risk(row)
        ratio = _float(row.get("bbox_area_ratio_to_reference"))
        if level != "not_evaluable" and ratio is not None:
            ratios_by_task[_safe(row.get("task_id"))].append(ratio)
        prepared.append({**row, "undercoverage_risk_level": level, "undercoverage_reason": reason, "_ratio": ratio})
    majority_tasks = {
        task_id
        for task_id, ratios in ratios_by_task.items()
        if ratios and sum(1 for ratio in ratios if ratio < MEDIUM_RATIO) > len(ratios) / 2
    }
    out: list[dict[str, Any]] = []
    for row in prepared:
        task_id = _safe(row.get("task_id"))
        majority = task_id in majority_tasks
        minority_full = bool(majority and row["_ratio"] is not None and row["_ratio"] >= NONE_RATIO)
        level = str(row["undercoverage_risk_level"])
        out.append(
            {
                "annotator_id": _safe(row.get("annotator_id")),
                "task_id": task_id,
                "dataset_group": _safe(row.get("dataset_group")),
                "condition": _safe(row.get("condition")),
                "reference_validation_status": _safe(row.get("reference_validation_status")),
                "worker_n_corners": _safe(row.get("worker_n_corners")),
                "reference_n_corners": _safe(row.get("reference_n_corners")),
                "bbox_area_ratio_to_reference": _safe(row.get("bbox_area_ratio_to_reference")),
                "polygon_area_ratio_to_reference": _safe(row.get("polygon_area_ratio_to_reference")),
                "undercoverage_risk_level": level,
                "undercoverage_reason": str(row["undercoverage_reason"]),
                "task_majority_undercoverage_risk": majority,
                "minority_full_room_candidate": minority_full,
                "manual_review_required": level in {"high", "medium", "not_evaluable"} and not minority_full,
                "dry_run": True,
                "notes": "dry-run undercoverage risk only; protected full-room minority is not bad-worker evidence",
            }
        )
    summary = {
        "dry_run": True,
        "rows": len(out),
        "thresholds": {"high_lt": HIGH_RATIO, "medium_lt": MEDIUM_RATIO, "none_gte": NONE_RATIO},
        "undercoverage_risk_level_counts": dict(Counter(str(row["undercoverage_risk_level"]) for row in out)),
        "task_majority_undercoverage_risk_count": len(majority_tasks),
        "minority_full_room_candidate_count": sum(bool(row["minority_full_room_candidate"]) for row in out),
        "forbidden_outputs_generated": False,
        "forbidden_metric_field_count": sum(1 for row in out for key in row if "score" in key.lower()),
    }
    return out, summary


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--alignment-csv", default=str(DEFAULT_ALIGNMENT))
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    args = parser.parse_args(argv)
    rows, summary = build_undercoverage_risk_audit(Path(args.alignment_csv))
    out_dir = Path(args.output_dir)
    audit_path = out_dir / "prescreen_undercoverage_risk_audit.csv"
    summary_path = out_dir / "prescreen_undercoverage_risk_summary.json"
    _write_csv(audit_path, rows)
    summary.update({"undercoverage_risk_audit_csv": str(audit_path), "undercoverage_risk_summary_json": str(summary_path)})
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
