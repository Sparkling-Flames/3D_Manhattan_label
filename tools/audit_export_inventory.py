import argparse
import csv
import json
from collections import Counter
from pathlib import Path

from build_registry_suite import (
    extract_choice_map,
    infer_runtime_condition,
    load_json,
    normalize_choice_values,
    determine_schema_version,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_EXPORT_DIR = PROJECT_ROOT / "export_label"
DEFAULT_OUTPUT_DIR = PROJECT_ROOT / "analysis_results" / "export_inventory_20260309"


FILE_CLASS_RULES = {
    "project-11-at-2026-03-07-17-05-1b4f93f3.json": {
        "source_epoch": "new_server",
        "run_class": "pilot_single_image_test",
        "formal_relevance": "exclude_from_formal_estimand",
        "recommended_use": "pipeline_validation",
        "notes": "2026-03-07 新服务器单图 semi 测试导出。",
    },
    "project-12-at-2026-03-07-17-05-72d96094.json": {
        "source_epoch": "new_server",
        "run_class": "pilot_single_image_test",
        "formal_relevance": "exclude_from_formal_estimand",
        "recommended_use": "pipeline_validation",
        "notes": "2026-03-07 新服务器单图 manual 测试导出。",
    },
    "test1.json": {
        "source_epoch": "legacy_server",
        "run_class": "ad_hoc_test_export",
        "formal_relevance": "exclude_from_formal_estimand",
        "recommended_use": "ad_hoc_debug_only",
        "notes": "临时测试导出，不应并入正式分析。",
    },
}


PROJECT_CLASS_RULES = {
    "2": {
        "source_epoch": "legacy_server",
        "run_class": "pilot_legacy_export",
        "formal_relevance": "exclude_from_formal_estimand",
        "recommended_use": "compatibility_or_pilot_audit",
        "notes": "当前仓库中的 project-2 导出均属于 pilot / 历史兼容样本。",
    }
}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Audit export_label inventory and classify pilot/formal relevance.")
    parser.add_argument("--export-dir", default=str(DEFAULT_EXPORT_DIR), help="Directory containing export JSON files")
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR), help="Directory to write CSV/JSON reports")
    return parser


def write_csv(rows: list[dict], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        output_path.write_text("", encoding="utf-8")
        return
    with output_path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def join_sorted(values) -> str:
    return ";".join(sorted(str(value) for value in values if str(value).strip()))


def resolve_classification(path: Path, project_ids: list[str]) -> dict:
    by_file = FILE_CLASS_RULES.get(path.name)
    if by_file:
        return dict(by_file)
    for project_id in project_ids:
        if project_id in PROJECT_CLASS_RULES:
            return dict(PROJECT_CLASS_RULES[project_id])
    return {
        "source_epoch": "unknown",
        "run_class": "unclassified",
        "formal_relevance": "review_needed",
        "recommended_use": "manual_review",
        "notes": "未命中仓库内冻结分类规则，需要人工确认是否属于正式分析候选。",
    }


def summarize_export(path: Path) -> tuple[dict, list[dict]]:
    tasks = load_json(path)
    project_ids = sorted({str(task.get("project") or "") for task in tasks if str(task.get("project") or "").strip()})
    dataset_groups = sorted(
        {
            str((task.get("data") or {}).get("dataset_group") or "").strip()
            for task in tasks
            if str((task.get("data") or {}).get("dataset_group") or "").strip()
        }
    )
    init_types = sorted(
        {
            str((task.get("data") or {}).get("init_type") or "").strip()
            for task in tasks
            if str((task.get("data") or {}).get("init_type") or "").strip()
        }
    )
    runtime_condition_counter: Counter = Counter()
    schema_counter: Counter = Counter()
    field_profile_counter: Counter = Counter()
    legacy_audit_rows: list[dict] = []
    annotation_count = 0
    task_with_annotations = 0

    for task in tasks:
        annotations = task.get("annotations") or []
        if annotations:
            task_with_annotations += 1
        for annotation in annotations:
            annotation_count += 1
            results = annotation.get("result") or []
            choice_map, raw_field_profile, geometry_present = extract_choice_map(results)
            schema_version = determine_schema_version(choice_map, raw_field_profile, geometry_present, results)
            schema_counter[schema_version] += 1
            field_profile_counter[raw_field_profile or "missing"] += 1
            runtime_condition_counter[infer_runtime_condition(task)] += 1
            if schema_version in {"legacy_quality_only", "mixed", "malformed"}:
                legacy_audit_rows.append(
                    {
                        "export_source_file": path.name,
                        "task_id": str(task.get("id") or ""),
                        "annotation_id": str(annotation.get("id") or ""),
                        "project_id": str(task.get("project") or ""),
                        "schema_version": schema_version,
                        "raw_field_profile": raw_field_profile or "missing",
                        "quality_choices": join_sorted(normalize_choice_values(choice_map.get("quality", []))),
                        "scope_choices": join_sorted(normalize_choice_values(choice_map.get("scope", []))),
                        "difficulty_choices": join_sorted(normalize_choice_values(choice_map.get("difficulty", []))),
                        "model_issue_choices": join_sorted(normalize_choice_values(choice_map.get("model_issue", []))),
                        "annotation_created_at": str(annotation.get("created_at") or ""),
                        "annotation_updated_at": str(annotation.get("updated_at") or ""),
                        "recommended_disposition": "exclude_from_formal_estimand_review_in_compat",
                    }
                )

    classification = resolve_classification(path, project_ids)
    summary_row = {
        "export_source_file": path.name,
        "task_count": len(tasks),
        "task_with_annotations": task_with_annotations,
        "annotation_count": annotation_count,
        "project_ids": join_sorted(project_ids),
        "dataset_groups": join_sorted(dataset_groups),
        "init_types": join_sorted(init_types),
        "runtime_conditions": join_sorted(runtime_condition_counter.keys()),
        "schema_counts": json.dumps(dict(schema_counter), ensure_ascii=False, sort_keys=True),
        "raw_field_profiles": json.dumps(dict(field_profile_counter), ensure_ascii=False, sort_keys=True),
        "legacy_like_annotation_count": sum(
            schema_counter.get(name, 0) for name in ["legacy_quality_only", "mixed", "malformed"]
        ),
        "source_epoch": classification["source_epoch"],
        "run_class": classification["run_class"],
        "formal_relevance": classification["formal_relevance"],
        "recommended_use": classification["recommended_use"],
        "notes": classification["notes"],
    }
    return summary_row, legacy_audit_rows


def main() -> int:
    args = build_parser().parse_args()
    export_dir = Path(args.export_dir)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    summary_rows: list[dict] = []
    legacy_rows: list[dict] = []
    for path in sorted(export_dir.glob("*.json")):
        row, audit_rows = summarize_export(path)
        summary_rows.append(row)
        legacy_rows.extend(audit_rows)

    summary_csv = output_dir / "export_inventory_v1.csv"
    summary_json = output_dir / "export_inventory_summary_v1.json"
    legacy_csv = output_dir / "legacy_annotation_audit_v1.csv"

    write_csv(summary_rows, summary_csv)
    write_csv(legacy_rows, legacy_csv)
    summary_json.write_text(
        json.dumps(
            {
                "export_dir": str(export_dir),
                "export_file_count": len(summary_rows),
                "formal_relevance_counts": dict(Counter(row["formal_relevance"] for row in summary_rows)),
                "run_class_counts": dict(Counter(row["run_class"] for row in summary_rows)),
                "legacy_annotation_audit_count": len(legacy_rows),
                "rows": summary_rows,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    print(f"[export-inventory] wrote {summary_csv}")
    print(f"[export-inventory] wrote {summary_json}")
    print(f"[export-inventory] wrote {legacy_csv}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())