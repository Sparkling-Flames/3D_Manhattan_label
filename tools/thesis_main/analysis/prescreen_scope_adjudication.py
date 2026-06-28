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

from tools.thesis_main.analysis.analyze_quality import extract_data, parse_quality_flags_v2

DEFAULT_CANONICAL = Path("analysis_results/prescreen_closeout/prescreen_canonical_annotations.csv")
DEFAULT_FINAL_GOLD = Path("analysis_results/final_gold_layer_20260325/final_gold_records_v1.jsonl")
DEFAULT_COMPLETION = Path("analysis_results/prescreen_closeout/prescreen_completion_audit.csv")
DEFAULT_OUTPUT_DIR = Path("analysis_results/prescreen_closeout")

TASK_FIELDS = [
    "task_id",
    "project_id",
    "dataset_group",
    "condition",
    "image_id",
    "data_title",
    "task_final_scope",
    "task_scope_adjudication_source",
    "final_gold_scope",
    "final_gold_ref",
    "worker_scope_values_seen",
    "n_worker_in_scope",
    "n_worker_oos",
    "n_worker_scope_missing",
    "mixed_scope_flag",
    "unresolved_scope_flag",
    "geometry_primary_possible",
    "notes",
]

RESPONSE_FIELDS = [
    "annotator_id",
    "language",
    "completion_status",
    "eligible_for_primary_prescreen_candidate",
    "project_id",
    "task_id",
    "dataset_group",
    "condition",
    "worker_scope_raw",
    "worker_scope_normalized",
    "task_final_scope",
    "task_scope_adjudication_source",
    "worker_scope_response",
    "geometry_valid_or_present",
    "geometry_primary_possible",
    "scope_response_primary_eligible",
    "notes",
]

ALLOWED_OOS = {"oos_geometry", "oos_open_boundary", "oos_split_level", "oos_insufficient"}
UNRESOLVED_SCOPES = {"unresolved_mixed", "unknown_gold", "audit_only"}


def _safe(value: Any) -> str:
    return str(value or "").strip()


def _load_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def _write_csv(path: Path, fields: list[str], rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def _load_completion(path: Path | None) -> dict[str, dict[str, str]]:
    if not path or not path.exists():
        return {}
    return {row["annotator_id"]: row for row in _load_csv(path)}


def _load_final_gold(path: Path) -> dict[str, dict[str, Any]]:
    index: dict[str, dict[str, Any]] = {}
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            rec = json.loads(line)
            for key in ("task_id", "base_task_id"):
                value = _safe(rec.get(key))
                if value:
                    index[f"{key}:{value}"] = rec
    return index


def _normalize_task_scope(alias: str, binary: str = "") -> str:
    text = _safe(alias).lower()
    binary = _safe(binary).lower()
    if "undercoverage" in text or "minimal" in text or "minimal-space" in text:
        return "in_scope"
    if text in {"normal", "in_scope", "inscope", "in-scope"} or binary == "in_scope":
        return "in_scope"
    if text in ALLOWED_OOS:
        return text
    if binary == "oos":
        return "oos_geometry"
    if text == "audit_only":
        return "audit_only"
    return "unknown_gold"


def _is_oos_scope(scope: str) -> bool:
    return scope in ALLOWED_OOS


def _geometry_possible(scope: str) -> bool:
    return scope == "in_scope"


def _load_export_details(canonical_rows: list[dict[str, str]]) -> tuple[dict[tuple[str, str, str], dict[str, Any]], dict[tuple[str, str, str, str], dict[str, Any]]]:
    task_index: dict[tuple[str, str, str], dict[str, Any]] = {}
    ann_index: dict[tuple[str, str, str, str], dict[str, Any]] = {}
    for export_path_text in sorted({_safe(row.get("source_export")) for row in canonical_rows if _safe(row.get("source_export"))}):
        export_path = Path(export_path_text)
        with export_path.open("r", encoding="utf-8") as f:
            tasks = json.load(f)
        for task in tasks:
            project_id = _safe(task.get("project") or task.get("project_id"))
            task_id = _safe(task.get("id") or task.get("task_id"))
            key = (export_path_text, project_id, task_id)
            task_index[key] = task
            for idx, ann in enumerate(task.get("annotations") or [], start=1):
                ann_id = _safe(ann.get("id")) or f"annotation_index_{idx}"
                ann_index[(export_path_text, project_id, task_id, ann_id)] = ann
    return task_index, ann_index


def _task_data(task: dict[str, Any] | None) -> dict[str, Any]:
    data = (task or {}).get("data")
    return data if isinstance(data, dict) else {}


def _final_gold_for(data: dict[str, Any], final_gold: dict[str, dict[str, Any]]) -> tuple[dict[str, Any] | None, str]:
    for key_name in ("task_id", "base_task_id"):
        value = _safe(data.get(key_name))
        if value:
            rec = final_gold.get(f"{key_name}:{value}")
            if rec:
                return rec, f"{key_name}:{value}"
    return None, ""


def _task_scope(data: dict[str, Any], final_gold_index: dict[str, dict[str, Any]]) -> tuple[str, str, str, str, str]:
    rec, ref = _final_gold_for(data, final_gold_index)
    if rec:
        raw = _safe(rec.get("final_scope_alias") or rec.get("final_scope_binary"))
        return _normalize_task_scope(raw, _safe(rec.get("final_scope_binary"))), "final_gold", raw, ref, ""
    data_scope = _safe(data.get("scope_gold") or data.get("scope_target"))
    if data_scope:
        return _normalize_task_scope(data_scope), "expert_review", data_scope, "task_data_scope", "fallback_to_task_data_scope_contract"
    return "unknown_gold", "missing_final_gold", "", "", "missing final_gold/task scope contract"


def _worker_scope(annotation: dict[str, Any] | None) -> tuple[str, str, bool]:
    if not annotation:
        return "", "missing", False
    corners, _poly, choice_map, quality = extract_data(annotation.get("result", []))
    flags = parse_quality_flags_v2(choice_map, quality_all=quality, mode="v2")
    raw = ";".join(choice_map.get("scope", []))
    geometry_present = bool(len(corners) > 0)
    if flags.get("scope_missing") or flags.get("is_oos") is None:
        return raw, "missing", geometry_present
    if flags.get("is_oos") is True:
        return raw, "oos", geometry_present
    return raw, "in_scope", geometry_present


def _scope_response(task_scope: str, worker_scope: str) -> str:
    if task_scope in UNRESOLVED_SCOPES or task_scope == "unknown_gold":
        return "not_applicable_unresolved"
    if worker_scope == "missing":
        return "unknown_or_missing"
    if task_scope == "in_scope" and worker_scope == "in_scope":
        return "correct_in_scope"
    if task_scope == "in_scope" and worker_scope == "oos":
        return "scope_false_positive"
    if _is_oos_scope(task_scope) and worker_scope == "oos":
        return "correct_oos"
    if _is_oos_scope(task_scope) and worker_scope == "in_scope":
        return "scope_false_negative"
    return "unknown_or_missing"


def build_scope_audits(
    canonical_csv: Path,
    final_gold_jsonl: Path,
    completion_csv: Path | None = None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    canonical_rows = _load_csv(canonical_csv)
    completion = _load_completion(completion_csv)
    final_gold_index = _load_final_gold(final_gold_jsonl)
    task_index, ann_index = _load_export_details(canonical_rows)

    task_groups: dict[tuple[str, str, str], list[dict[str, str]]] = defaultdict(list)
    parsed_rows: list[dict[str, Any]] = []
    for row in canonical_rows:
        key = (_safe(row.get("source_export")), _safe(row.get("project_id")), _safe(row.get("task_id")))
        task_groups[key].append(row)
        ann = ann_index.get((key[0], key[1], key[2], _safe(row.get("raw_canonical_annotation_id") or row.get("annotation_id"))))
        raw_scope, worker_scope, geometry_present = _worker_scope(ann)
        parsed = dict(row)
        parsed.update({"worker_scope_raw": raw_scope, "worker_scope_normalized": worker_scope, "geometry_valid_or_present": geometry_present})
        parsed_rows.append(parsed)

    by_row_key = {
        (_safe(r.get("source_export")), _safe(r.get("project_id")), _safe(r.get("task_id")), _safe(r.get("canonical_annotation_id"))): r
        for r in parsed_rows
    }

    task_rows: list[dict[str, Any]] = []
    task_scope_map: dict[tuple[str, str, str], dict[str, Any]] = {}
    for key, rows in sorted(task_groups.items()):
        task = task_index.get(key)
        data = _task_data(task)
        task_scope, source, gold_scope, gold_ref, note = _task_scope(data, final_gold_index)
        scopes = []
        n_in = n_oos = n_missing = 0
        for row in rows:
            parsed = by_row_key[(key[0], key[1], key[2], _safe(row.get("canonical_annotation_id")))]
            scope = parsed["worker_scope_normalized"]
            scopes.append(scope)
            if scope == "in_scope":
                n_in += 1
            elif scope == "oos":
                n_oos += 1
            else:
                n_missing += 1
        mixed = n_in > 0 and n_oos > 0
        unresolved = task_scope in UNRESOLVED_SCOPES or task_scope == "unknown_gold"
        task_row = {
            "task_id": key[2],
            "project_id": key[1],
            "dataset_group": rows[0].get("dataset_group", ""),
            "condition": rows[0].get("condition", ""),
            "image_id": _safe(data.get("base_task_id") or Path(_safe(data.get("title"))).stem),
            "data_title": _safe(data.get("title") or rows[0].get("task_label")),
            "task_final_scope": task_scope,
            "task_scope_adjudication_source": source,
            "final_gold_scope": gold_scope,
            "final_gold_ref": gold_ref,
            "worker_scope_values_seen": ";".join(f"{k}:{v}" for k, v in sorted(Counter(scopes).items())),
            "n_worker_in_scope": n_in,
            "n_worker_oos": n_oos,
            "n_worker_scope_missing": n_missing,
            "mixed_scope_flag": mixed,
            "unresolved_scope_flag": unresolved,
            "geometry_primary_possible": _geometry_possible(task_scope),
            "notes": note,
        }
        task_rows.append(task_row)
        task_scope_map[key] = task_row

    response_rows: list[dict[str, Any]] = []
    for row in parsed_rows:
        key = (_safe(row.get("source_export")), _safe(row.get("project_id")), _safe(row.get("task_id")))
        task_row = task_scope_map[key]
        comp = completion.get(_safe(row.get("annotator_id")), {})
        response = _scope_response(str(task_row["task_final_scope"]), str(row["worker_scope_normalized"]))
        primary_eligible = (
            response not in {"unknown_or_missing", "not_applicable_unresolved"}
            and str(comp.get("eligible_for_primary_prescreen_candidate", "True")).lower() == "true"
        )
        response_rows.append(
            {
                "annotator_id": row.get("annotator_id", ""),
                "language": comp.get("language", ""),
                "completion_status": comp.get("completion_status", ""),
                "eligible_for_primary_prescreen_candidate": comp.get("eligible_for_primary_prescreen_candidate", ""),
                "project_id": row.get("project_id", ""),
                "task_id": row.get("task_id", ""),
                "dataset_group": row.get("dataset_group", ""),
                "condition": row.get("condition", ""),
                "worker_scope_raw": row["worker_scope_raw"],
                "worker_scope_normalized": row["worker_scope_normalized"],
                "task_final_scope": task_row["task_final_scope"],
                "task_scope_adjudication_source": task_row["task_scope_adjudication_source"],
                "worker_scope_response": response,
                "geometry_valid_or_present": row["geometry_valid_or_present"],
                "geometry_primary_possible": task_row["geometry_primary_possible"],
                "scope_response_primary_eligible": primary_eligible,
                "notes": "dry_run_partial_snapshot",
            }
        )

    summary = {
        "dry_run": True,
        "data_complete": False,
        "n_tasks": len(task_rows),
        "n_responses": len(response_rows),
        "task_final_scope_counts": dict(Counter(str(r["task_final_scope"]) for r in task_rows)),
        "worker_scope_response_counts": dict(Counter(str(r["worker_scope_response"]) for r in response_rows)),
        "unknown_gold_tasks": sum(r["task_final_scope"] == "unknown_gold" for r in task_rows),
        "unresolved_mixed_tasks": sum(r["task_final_scope"] == "unresolved_mixed" for r in task_rows),
        "missing_worker_scope_rows": sum(r["worker_scope_normalized"] == "missing" for r in response_rows),
        "mixed_scope_tasks": sum(bool(r["mixed_scope_flag"]) for r in task_rows),
    }
    return task_rows, response_rows, summary


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--canonical-csv", default=str(DEFAULT_CANONICAL))
    parser.add_argument("--final-gold-jsonl", default=str(DEFAULT_FINAL_GOLD))
    parser.add_argument("--completion-csv", default=str(DEFAULT_COMPLETION))
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    args = parser.parse_args(argv)

    out_dir = Path(args.output_dir)
    task_rows, response_rows, summary = build_scope_audits(
        Path(args.canonical_csv),
        Path(args.final_gold_jsonl),
        Path(args.completion_csv) if args.completion_csv else None,
    )
    task_path = out_dir / "prescreen_scope_adjudication.csv"
    response_path = out_dir / "prescreen_scope_response_audit.csv"
    summary_path = out_dir / "prescreen_scope_summary.json"
    _write_csv(task_path, TASK_FIELDS, task_rows)
    _write_csv(response_path, RESPONSE_FIELDS, response_rows)
    summary.update({"scope_adjudication_csv": str(task_path), "scope_response_audit_csv": str(response_path)})
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
