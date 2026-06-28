from __future__ import annotations

import argparse
import csv
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

_PROJECT_ROOT = Path(__file__).resolve().parents[3]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

DEFAULT_SCOPE_ADJUDICATION = Path("analysis_results/prescreen_closeout/prescreen_scope_adjudication.csv")
DEFAULT_SCOPE_RESPONSE = Path("analysis_results/prescreen_closeout/prescreen_scope_response_audit.csv")
DEFAULT_SYNTHETIC_SCOPE = Path("analysis_results/prescreen_closeout/prescreen_synthetic_scope_binding_audit.csv")
DEFAULT_SYNTHETIC_GEOMETRY = Path("analysis_results/prescreen_closeout/prescreen_synthetic_geometry_gt_binding_audit.csv")
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
    "geometry_gold_source",
    "geometry_gold_task_id",
    "geometry_evidence_role",
    "geometry_scoring_role",
    "manual_anchor_role",
    "manual_anchor_primary_possible",
    "admission_anchor_role",
    "admission_anchor_possible",
    "geometry_alignment_status",
    "dry_run",
    "notes",
]

ELIGIBILITY_FIELDS = ["annotator_id", *AUDIT_FIELDS]

OOS_SCOPES = {"oos_geometry", "oos_open_boundary", "oos_split_level", "oos_insufficient"}
UNRESOLVED_SCOPES = {"unknown_gold", "unresolved_mixed", "audit_only", "synthetic_scope_unresolved"}


def _safe(value: Any) -> str:
    return str(value or "").strip()


def _truthy(value: Any) -> bool:
    return _safe(value).lower() in {"1", "true", "yes", "y"}


def _load_csv(path: Path | None) -> list[dict[str, str]]:
    if not path or not path.exists():
        return []
    with path.open("r", newline="", encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def _write_csv(path: Path, fields: list[str], rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def _geometry_status(task: dict[str, str], synthetic_geometry: dict[str, str] | None) -> str:
    scope = _safe(task.get("task_final_scope"))
    explicit = _safe(task.get("geometry_gold_status"))
    if explicit:
        return explicit
    if scope in OOS_SCOPES:
        return "not_applicable"
    if scope in UNRESOLVED_SCOPES:
        return "deferred"
    if synthetic_geometry:
        binding = _safe(synthetic_geometry.get("geometry_binding_status"))
        if _truthy(synthetic_geometry.get("geometry_gold_ready")):
            return "ready"
        return {
            "missing_export_gt": "missing",
            "duplicate_export_gt": "duplicate",
            "invalid_annotation_count": "invalid_annotation_count",
        }.get(binding, "deferred")
    if scope == "in_scope" and _safe(task.get("final_gold_ref")):
        return "ready"
    return "missing"


def _roles(task: dict[str, str], status: str, synthetic_geometry: dict[str, str] | None) -> tuple[str, str, bool, bool]:
    dataset_group = _safe(task.get("dataset_group"))
    scope = _safe(task.get("task_final_scope"))
    is_synthetic = synthetic_geometry is not None or _safe(task.get("task_scope_adjudication_source")).startswith("synthetic_asset")
    if scope in OOS_SCOPES or dataset_group == "PreScreen_oos":
        return "oos_excluded", "oos_excluded", False, False
    if scope in UNRESOLVED_SCOPES or status != "ready":
        return "unresolved_excluded", "unresolved_excluded", False, False
    if dataset_group == "PreScreen_manual":
        return "manual_prescreen_candidate", "manual_primary_candidate", True, True
    if dataset_group == "PreScreen_semi" and is_synthetic:
        return "semi_synthetic_trap_audit", _safe((synthetic_geometry or {}).get("geometry_scoring_role")) or "semi_trap_audit", False, False
    if dataset_group == "PreScreen_semi":
        return "semi_condition_diagnostic", "semi_aux_geometry_alignment", False, False
    return "unresolved_excluded", "unresolved_excluded", False, False


def _alignment_status(status: str, role: str) -> str:
    if role == "oos_excluded":
        return "excluded_oos"
    if status == "ready":
        return "aligned_ready"
    return {
        "missing": "missing_gold",
        "duplicate": "duplicate_gold",
        "invalid_annotation_count": "invalid_annotation_count",
        "not_applicable": "excluded_oos",
    }.get(status, "deferred")


def _forbidden_metric_field_count(rows: list[dict[str, Any]]) -> int:
    return sum(1 for row in rows for key in row if "score" in str(key).lower())


def build_geometry_eligibility(
    scope_adjudication_csv: Path,
    scope_response_csv: Path,
    synthetic_scope_csv: Path | None = None,
    synthetic_geometry_csv: Path | None = None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    task_rows = _load_csv(scope_adjudication_csv)
    response_rows = _load_csv(scope_response_csv)
    synthetic_scope_rows = _load_csv(synthetic_scope_csv)
    synthetic_geometry_rows = _load_csv(synthetic_geometry_csv)

    synthetic_by_task = {_safe(row.get("runtime_task_id")): row for row in synthetic_scope_rows if _safe(row.get("runtime_task_id"))}
    synthetic_geometry_by_task = {_safe(row.get("runtime_task_id")): row for row in synthetic_geometry_rows if _safe(row.get("runtime_task_id"))}

    alignment_rows: list[dict[str, Any]] = []
    for task in task_rows:
        task_id = _safe(task.get("task_id"))
        synth_scope = synthetic_by_task.get(task_id)
        synth_geometry = synthetic_geometry_by_task.get(task_id)
        status = _geometry_status(task, synth_geometry)
        evidence_role, scoring_role, manual_role, manual_possible = _roles(task, status, synth_geometry or synth_scope)
        base_image_key = _safe((synth_geometry or synth_scope or {}).get("base_image_key")) or _safe(task.get("image_id"))
        row = {
            "task_id": task_id,
            "project_id": _safe(task.get("project_id")),
            "dataset_group": _safe(task.get("dataset_group")),
            "condition": _safe(task.get("condition")),
            "image_id": _safe(task.get("image_id")),
            "base_image_key": base_image_key,
            "task_final_scope": _safe(task.get("task_final_scope")),
            "task_scope_adjudication_source": _safe(task.get("task_scope_adjudication_source")),
            "geometry_gold_status": status,
            "geometry_gold_source": _safe((synth_geometry or {}).get("geometry_gold_source")) or ("final_gold" if status == "ready" else ""),
            "geometry_gold_task_id": _safe((synth_geometry or {}).get("geometry_gold_task_id")) or _safe(task.get("final_gold_ref")),
            "geometry_evidence_role": evidence_role,
            "geometry_scoring_role": scoring_role,
            "manual_anchor_role": manual_role,
            "manual_anchor_primary_possible": manual_possible,
            "admission_anchor_role": False,
            "admission_anchor_possible": False,
            "geometry_alignment_status": _alignment_status(status, evidence_role),
            "dry_run": True,
            "notes": "dry-run eligibility only; no geometry scoring or admission materialization",
        }
        alignment_rows.append(row)

    by_base: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in alignment_rows:
        if row["base_image_key"]:
            by_base[str(row["base_image_key"])].append(row)
    for rows in by_base.values():
        gold_ids = {str(row["geometry_gold_task_id"]) for row in rows if row["geometry_gold_status"] == "ready"}
        if len(rows) > 1 and len(gold_ids) > 1:
            for row in rows:
                row["geometry_alignment_status"] = "mirror_gold_mismatch"

    task_by_id = {str(row["task_id"]): row for row in alignment_rows}
    eligibility_rows: list[dict[str, Any]] = []
    for response in response_rows:
        task = task_by_id.get(_safe(response.get("task_id")))
        if not task:
            continue
        eligibility_rows.append({"annotator_id": _safe(response.get("annotator_id")), **task})

    all_output_rows = [*alignment_rows, *eligibility_rows]
    summary = {
        "dry_run": True,
        "runtime_task_rows": len(alignment_rows),
        "response_rows": len(eligibility_rows),
        "base_image_count": len({str(row["base_image_key"]) for row in alignment_rows if row["base_image_key"]}),
        "geometry_gold_status_counts": dict(Counter(str(row["geometry_gold_status"]) for row in alignment_rows)),
        "geometry_evidence_role_counts": dict(Counter(str(row["geometry_evidence_role"]) for row in alignment_rows)),
        "geometry_scoring_role_counts": dict(Counter(str(row["geometry_scoring_role"]) for row in alignment_rows)),
        "manual_anchor_possible_task_rows": sum(bool(row["manual_anchor_primary_possible"]) for row in alignment_rows),
        "admission_anchor_possible_task_rows": 0,
        "mirror_alignment_mismatch_count": sum(1 for rows in by_base.values() if len(rows) > 1 and len({str(row["geometry_gold_task_id"]) for row in rows if row["geometry_gold_status"] == "ready"}) > 1),
        "forbidden_metric_field_count": _forbidden_metric_field_count(all_output_rows),
        "forbidden_outputs_generated": False,
    }
    return alignment_rows, eligibility_rows, summary


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--scope-adjudication-csv", default=str(DEFAULT_SCOPE_ADJUDICATION))
    parser.add_argument("--scope-response-csv", default=str(DEFAULT_SCOPE_RESPONSE))
    parser.add_argument("--synthetic-scope-csv", default=str(DEFAULT_SYNTHETIC_SCOPE))
    parser.add_argument("--synthetic-geometry-csv", default=str(DEFAULT_SYNTHETIC_GEOMETRY))
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    args = parser.parse_args(argv)

    alignment_rows, eligibility_rows, summary = build_geometry_eligibility(
        Path(args.scope_adjudication_csv),
        Path(args.scope_response_csv),
        Path(args.synthetic_scope_csv) if args.synthetic_scope_csv else None,
        Path(args.synthetic_geometry_csv) if args.synthetic_geometry_csv else None,
    )
    out_dir = Path(args.output_dir)
    alignment_path = out_dir / "prescreen_geometry_gold_alignment_audit.csv"
    eligibility_path = out_dir / "prescreen_geometry_eligibility_audit.csv"
    summary_path = out_dir / "prescreen_gold_alignment_summary.json"
    _write_csv(alignment_path, AUDIT_FIELDS, alignment_rows)
    _write_csv(eligibility_path, ELIGIBILITY_FIELDS, eligibility_rows)
    summary.update(
        {
            "geometry_gold_alignment_audit_csv": str(alignment_path),
            "geometry_eligibility_audit_csv": str(eligibility_path),
            "gold_alignment_summary_json": str(summary_path),
        }
    )
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
