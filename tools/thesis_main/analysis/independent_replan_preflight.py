#!/usr/bin/env python3
"""Independent data inventory for the Paper-A experiment re-planning preflight.

This script is deliberately append-only. It scans repository analysis artefacts,
records schemas and row counts, and identifies candidate tables for worker
portrait, meta-label, active-time, reviewer-proxy, and sequential-policy analyses.
It does not modify historical inputs or silently reinterpret frozen eligibility.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
from pathlib import Path
from typing import Any

KEYWORDS = {
    "worker": ["worker", "annotator", "user", "q_gt", "qgt", "r_peer", "f_struct"],
    "task": ["task", "base_task", "image", "panorama", "building"],
    "quality": ["quality", "iou", "gt", "structural", "valid", "error"],
    "meta": ["difficulty", "scope", "model_issue", "occlusion", "seam", "reflection", "low_texture"],
    "time": ["active_time", "duration", "elapsed", "time_seconds", "owner_valid"],
    "geometry": ["geometry", "label_cor", "corner", "cluster", "medoid", "similarity"],
    "assignment": ["assignment", "condition", "stage", "mode", "manual", "semi"],
}

FOCUS_PATHS = [
    "analysis_results/post_block2_analysis_pack_20260817_v4/post_block2_submission_master.csv",
    "analysis_results/post_block2_analysis_pack_20260817_v4/post_block2_task_context_master.csv",
    "analysis_results/post_block2_analysis_pack_20260817_v4/post_block2_worker_profile_master.csv",
    "analysis_results/final_calibration_profile_20260817_v1/pooled_worker_profile_v2.csv",
    "analysis_results/final_calibration_profile_20260817_v1/final_c1_c2_qgt_worker_evidence.csv",
    "analysis_results/c1_formal_audit_20260802_v16_final/c1_formal_audit_20260802_7fcacc5c2d6c_bf5def46_6bc67c03/c1_geometry_pool_eligibility.csv",
    "analysis_results/c1_formal_audit_20260802_v16_final/c1_formal_audit_20260802_7fcacc5c2d6c_bf5def46_6bc67c03/c1_gt_quality_evidence.csv",
    "analysis_results/c1_formal_audit_20260802_v16_final/c1_formal_audit_20260802_7fcacc5c2d6c_bf5def46_6bc67c03/c1_three_track_worker_state_formal.csv",
    "analysis_results/c1_formal_audit_20260802_v16_final/c1_formal_audit_20260802_7fcacc5c2d6c_bf5def46_6bc67c03/structural_validation_analysis.csv",
    "analysis_results/c1_formal_audit_20260802_v16_final/c1_formal_audit_20260802_7fcacc5c2d6c_bf5def46_6bc67c03/c1_geometry_loo_task_crowd_structure.csv",
    "analysis_results/topology_sequential_preflight_20260818_v4_audit/TG_EF5_TASK_METRICS.csv",
    "analysis_results/topology_sequential_preflight_20260818_v4_audit/TG_EF5_OPERATING_CHARACTERISTICS.csv",
    "analysis_results/topology_sequential_preflight_20260818_v4_audit/REVIEWER_AVAILABILITY_SENSITIVITY.csv",
]


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def inspect_csv(path: Path, root: Path, sample_limit: int = 2) -> dict[str, Any]:
    header: list[str] = []
    row_count = 0
    sample_rows: list[dict[str, str]] = []
    nonempty: dict[str, int] = {}
    examples: dict[str, list[str]] = {}
    error = ""
    try:
        with path.open("r", encoding="utf-8-sig", newline="", errors="replace") as f:
            reader = csv.DictReader(f)
            header = list(reader.fieldnames or [])
            nonempty = {c: 0 for c in header}
            examples = {c: [] for c in header}
            for row in reader:
                row_count += 1
                if len(sample_rows) < sample_limit:
                    sample_rows.append({k: (v or "")[:300] for k, v in row.items()})
                for c in header:
                    value = (row.get(c) or "").strip()
                    if value:
                        nonempty[c] += 1
                        if len(examples[c]) < 4 and value not in examples[c]:
                            examples[c].append(value[:200])
    except Exception as exc:  # inventory must continue across malformed legacy files
        error = f"{type(exc).__name__}: {exc}"
    lower = [c.lower() for c in header]
    groups: dict[str, list[str]] = {}
    for group, kws in KEYWORDS.items():
        hits = [c for c, lc in zip(header, lower) if any(kw in lc for kw in kws)]
        groups[group] = hits
    score = sum(bool(v) for v in groups.values())
    return {
        "path": path.relative_to(root).as_posix(),
        "bytes": path.stat().st_size,
        "sha256": sha256(path),
        "rows": row_count,
        "columns": header,
        "column_count": len(header),
        "column_nonempty": nonempty,
        "column_examples": examples,
        "keyword_groups": groups,
        "relevance_score": score,
        "sample_rows": sample_rows,
        "error": error,
    }


def inspect_json(path: Path, root: Path) -> dict[str, Any]:
    keys: list[str] = []
    error = ""
    kind = "unknown"
    try:
        with path.open("r", encoding="utf-8-sig", errors="replace") as f:
            obj = json.load(f)
        kind = type(obj).__name__
        if isinstance(obj, dict):
            keys = list(obj.keys())[:200]
        elif isinstance(obj, list) and obj and isinstance(obj[0], dict):
            keys = list(obj[0].keys())[:200]
    except Exception as exc:
        error = f"{type(exc).__name__}: {exc}"
    return {
        "path": path.relative_to(root).as_posix(),
        "bytes": path.stat().st_size,
        "sha256": sha256(path),
        "kind": kind,
        "keys": keys,
        "error": error,
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", type=Path, default=Path.cwd())
    ap.add_argument("--output-dir", type=Path, required=True)
    args = ap.parse_args()
    root = args.root.resolve()
    out = args.output_dir.resolve()
    out.mkdir(parents=True, exist_ok=True)

    scan_roots = [root / "analysis_results", root / "active_logs", root / "docs" / "thesis_main"]
    csv_files: list[Path] = []
    json_files: list[Path] = []
    for scan_root in scan_roots:
        if not scan_root.exists():
            continue
        csv_files.extend(p for p in scan_root.rglob("*.csv") if out not in p.parents)
        json_files.extend(p for p in scan_root.rglob("*.json") if out not in p.parents)

    csv_inventory = [inspect_csv(p, root) for p in sorted(set(csv_files))]
    json_inventory = [inspect_json(p, root) for p in sorted(set(json_files))]

    with (out / "CSV_SCHEMA_INVENTORY.json").open("w", encoding="utf-8") as f:
        json.dump(csv_inventory, f, ensure_ascii=False, indent=2)
    with (out / "JSON_SCHEMA_INVENTORY.json").open("w", encoding="utf-8") as f:
        json.dump(json_inventory, f, ensure_ascii=False, indent=2)

    with (out / "CSV_SCHEMA_CATALOG.csv").open("w", encoding="utf-8", newline="") as f:
        fieldnames = [
            "path", "bytes", "rows", "column_count", "relevance_score",
            "worker_columns", "task_columns", "quality_columns", "meta_columns",
            "time_columns", "geometry_columns", "assignment_columns", "error",
        ]
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for item in sorted(csv_inventory, key=lambda x: (-x["relevance_score"], -x["rows"], x["path"])):
            groups = item["keyword_groups"]
            writer.writerow({
                "path": item["path"],
                "bytes": item["bytes"],
                "rows": item["rows"],
                "column_count": item["column_count"],
                "relevance_score": item["relevance_score"],
                "worker_columns": "|".join(groups["worker"]),
                "task_columns": "|".join(groups["task"]),
                "quality_columns": "|".join(groups["quality"]),
                "meta_columns": "|".join(groups["meta"]),
                "time_columns": "|".join(groups["time"]),
                "geometry_columns": "|".join(groups["geometry"]),
                "assignment_columns": "|".join(groups["assignment"]),
                "error": item["error"],
            })

    candidates: dict[str, list[dict[str, Any]]] = {}
    for focus in ["worker", "meta", "time", "quality", "geometry", "assignment"]:
        eligible = [i for i in csv_inventory if i["keyword_groups"][focus] and i["rows"] > 0 and not i["error"]]
        eligible.sort(key=lambda x: (-len(x["keyword_groups"][focus]), -x["relevance_score"], -x["rows"], x["path"]))
        candidates[focus] = [{
            "path": i["path"],
            "rows": i["rows"],
            "columns": i["columns"],
            "focus_columns": i["keyword_groups"][focus],
            "sample_rows": i["sample_rows"],
        } for i in eligible[:25]]
    with (out / "CANDIDATE_ANALYSIS_TABLES.json").open("w", encoding="utf-8") as f:
        json.dump(candidates, f, ensure_ascii=False, indent=2)

    inventory_by_path = {i["path"]: i for i in csv_inventory}
    focused = []
    for rel in FOCUS_PATHS:
        if rel in inventory_by_path:
            item = inventory_by_path[rel]
            focused.append({
                "path": rel,
                "rows": item["rows"],
                "bytes": item["bytes"],
                "sha256": item["sha256"],
                "columns": item["columns"],
                "column_nonempty": item["column_nonempty"],
                "column_examples": item["column_examples"],
                "sample_rows": item["sample_rows"],
            })
        else:
            focused.append({"path": rel, "missing": True})
    with (out / "FOCUS_SCHEMA_REPORT.json").open("w", encoding="utf-8") as f:
        json.dump(focused, f, ensure_ascii=False, indent=2)

    # Compact row-per-column catalogue so connector reads do not need to load a large JSON.
    with (out / "FOCUS_COLUMN_CATALOG.csv").open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["path", "rows", "column", "nonempty", "examples"])
        writer.writeheader()
        for item in focused:
            if item.get("missing"):
                writer.writerow({"path": item["path"], "rows": "", "column": "__MISSING__", "nonempty": "", "examples": ""})
                continue
            for column in item["columns"]:
                writer.writerow({
                    "path": item["path"],
                    "rows": item["rows"],
                    "column": column,
                    "nonempty": item["column_nonempty"].get(column, 0),
                    "examples": " || ".join(item["column_examples"].get(column, [])),
                })

    summary = {
        "status": "inventory_complete",
        "root": str(root),
        "csv_files_scanned": len(csv_inventory),
        "json_files_scanned": len(json_inventory),
        "csv_rows_total": sum(i["rows"] for i in csv_inventory),
        "csv_errors": [i["path"] for i in csv_inventory if i["error"]],
        "focused_tables_present": sum(1 for i in focused if not i.get("missing")),
        "focused_tables_missing": [i["path"] for i in focused if i.get("missing")],
        "top_candidates": {k: [x["path"] for x in v[:10]] for k, v in candidates.items()},
        "limitations": [
            "This pass inventories schemas only; it does not interpret post-outcome fields as pre-assignment predictors.",
            "Reviewer availability is not reviewer efficacy; actual review-role transfer requires a randomized role experiment.",
            "Public-GT and frozen-F5 outputs are development comparators, not expert delivery-harm ground truth.",
        ],
    }
    with (out / "INVENTORY_SUMMARY.json").open("w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
