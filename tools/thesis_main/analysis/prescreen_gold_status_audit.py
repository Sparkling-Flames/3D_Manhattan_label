from __future__ import annotations

import argparse
import csv
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any

_PROJECT_ROOT = Path(__file__).resolve().parents[3]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

DEFAULT_ALIGNMENT = Path("analysis_results/prescreen_closeout/prescreen_geometry_gold_alignment_audit.csv")
DEFAULT_OUTPUT_DIR = Path("analysis_results/prescreen_closeout")

AUDIT_FIELDS = [
    "task_id",
    "project_id",
    "dataset_group",
    "condition",
    "image_id",
    "base_image_key",
    "task_final_scope",
    "task_scope_adjudication_source",
    "geometry_gold_status",
    "geometry_gold_validation_level",
    "geometry_gold_source",
    "geometry_gold_task_id",
    "gold_reference_role",
    "gold_status_for_alignment",
    "gold_status_for_undercoverage",
    "gold_ambiguity_flag",
    "gold_ambiguity_reason",
    "manual_review_required",
    "dry_run",
    "notes",
]

OOS_SCOPES = {"oos_geometry", "oos_open_boundary", "oos_split_level", "oos_insufficient"}
UNRESOLVED_SCOPES = {"unknown_gold", "unresolved_mixed", "audit_only", "synthetic_scope_unresolved"}


def _safe(value: Any) -> str:
    return str(value or "").strip()


def _load_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", newline="", encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=AUDIT_FIELDS)
        writer.writeheader()
        writer.writerows(rows)


def _reference_role(row: dict[str, str]) -> str:
    dataset_group = _safe(row.get("dataset_group"))
    scope = _safe(row.get("task_final_scope"))
    validation = _safe(row.get("geometry_gold_validation_level"))
    if scope in OOS_SCOPES or dataset_group == "PreScreen_oos":
        return "oos_not_applicable"
    if scope in UNRESOLVED_SCOPES:
        return "unresolved_not_applicable"
    if validation == "source_gt_annotation_count_checked":
        return "synthetic_source_gt_checked"
    if dataset_group == "PreScreen_manual":
        return "manual_final_gold_ref"
    if dataset_group == "PreScreen_semi":
        return "semi_condition_reference_only"
    return "unresolved_not_applicable"


def _status_tuple(row: dict[str, str], role: str) -> tuple[str, str, bool, str, bool]:
    status = _safe(row.get("geometry_gold_status"))
    validation = _safe(row.get("geometry_gold_validation_level"))
    scope = _safe(row.get("task_final_scope"))
    alignment = _safe(row.get("geometry_alignment_status"))
    if alignment == "mirror_gold_mismatch":
        return "ambiguous", "not_ready", True, "mirror_gold_mismatch", True
    if role == "oos_not_applicable":
        return "not_applicable", "not_applicable", False, "oos_scope", False
    if role == "unresolved_not_applicable" or scope in UNRESOLVED_SCOPES:
        return "deferred", "not_ready", True, "unresolved_scope", True
    if status == "ready" and validation == "source_gt_annotation_count_checked":
        return "ready_for_alignment", "ready_for_undercoverage_audit", False, "synthetic_gt_checked", False
    if status == "ready" and validation == "final_gold_ref_only":
        return "reference_only_unvalidated", "reference_only_needs_review", True, "final_gold_ref_only", True
    if status in {"missing", "duplicate"}:
        return status, "not_ready", True, f"{status}_gold", True
    if status == "invalid_annotation_count":
        return "invalid", "not_ready", True, "invalid_annotation_count", True
    if status == "not_applicable":
        return "not_applicable", "not_applicable", False, "oos_scope", False
    return "deferred", "not_ready", True, "unknown", True


def _forbidden_metric_field_count(rows: list[dict[str, Any]]) -> int:
    return sum(1 for row in rows for key in row if "score" in str(key).lower())


def build_gold_status_audit(alignment_csv: Path) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    rows = _load_csv(alignment_csv)
    out: list[dict[str, Any]] = []
    for row in rows:
        role = _reference_role(row)
        alignment_status, undercoverage_status, ambiguity, reason, review = _status_tuple(row, role)
        out.append(
            {
                "task_id": _safe(row.get("task_id")),
                "project_id": _safe(row.get("project_id")),
                "dataset_group": _safe(row.get("dataset_group")),
                "condition": _safe(row.get("condition")),
                "image_id": _safe(row.get("image_id")),
                "base_image_key": _safe(row.get("base_image_key")),
                "task_final_scope": _safe(row.get("task_final_scope")),
                "task_scope_adjudication_source": _safe(row.get("task_scope_adjudication_source")),
                "geometry_gold_status": _safe(row.get("geometry_gold_status")),
                "geometry_gold_validation_level": _safe(row.get("geometry_gold_validation_level")),
                "geometry_gold_source": _safe(row.get("geometry_gold_source")),
                "geometry_gold_task_id": _safe(row.get("geometry_gold_task_id")),
                "gold_reference_role": role,
                "gold_status_for_alignment": alignment_status,
                "gold_status_for_undercoverage": undercoverage_status,
                "gold_ambiguity_flag": ambiguity,
                "gold_ambiguity_reason": reason,
                "manual_review_required": review,
                "dry_run": True,
                "notes": "dry-run gold status sidecar only; no geometry scoring or worker materialization",
            }
        )
    summary = {
        "dry_run": True,
        "runtime_task_rows": len(out),
        "gold_reference_role_counts": dict(Counter(str(row["gold_reference_role"]) for row in out)),
        "gold_status_for_alignment_counts": dict(Counter(str(row["gold_status_for_alignment"]) for row in out)),
        "gold_status_for_undercoverage_counts": dict(Counter(str(row["gold_status_for_undercoverage"]) for row in out)),
        "gold_ambiguity_flag_count": sum(bool(row["gold_ambiguity_flag"]) for row in out),
        "manual_review_required_count": sum(bool(row["manual_review_required"]) for row in out),
        "forbidden_outputs_generated": False,
        "forbidden_metric_field_count": _forbidden_metric_field_count(out),
    }
    return out, summary


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--alignment-csv", default=str(DEFAULT_ALIGNMENT))
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    args = parser.parse_args(argv)

    rows, summary = build_gold_status_audit(Path(args.alignment_csv))
    out_dir = Path(args.output_dir)
    audit_path = out_dir / "prescreen_gold_status_audit.csv"
    summary_path = out_dir / "prescreen_gold_status_summary.json"
    _write_csv(audit_path, rows)
    summary.update({"gold_status_audit_csv": str(audit_path), "gold_status_summary_json": str(summary_path)})
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
