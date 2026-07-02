from __future__ import annotations

import argparse
import csv
import hashlib
import json
import shutil
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

_PROJECT_ROOT = Path(__file__).resolve().parents[3]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from tools.thesis_main.analysis.prescreen_canonicalize_export import build_canonical_tables


OUT_DIR = Path("analysis_results/calibration_rebuild_20260702/manual_zh_analysis_chain_precheck_v3_1")
REBUILD_DIR = Path("analysis_results/calibration_rebuild_20260702")
DEFAULT_EXPORT = Path(r"C:\Users\ASUS\Downloads\project-65-at-2026-07-02-16-49-f641e0f6.json")
DEFAULT_ACTIVE_LOG = Path("active_logs/new_server/active_times_2026-07-03.jsonl")
COMPLETION_BASIS = "manual_zh_smoke_fixture_only"
ENTRY_BY_GROUP = {
    "Calibration_anchor": "A",
    "Calibration_core": "B",
    "Calibration_semi": "C",
}

CANONICAL_FIELDS = [
    "source_export",
    "project_id",
    "ls_runtime_task_id",
    "task_key",
    "task_label",
    "planned_project_name",
    "planned_inner_id",
    "task_code",
    "task_id",
    "base_task_id",
    "dataset_group",
    "condition",
    "annotator_id",
    "worker_id",
    "annotation_id",
    "annotation_match_status",
    "canonical_annotation_id",
    "raw_canonical_annotation_id",
    "duplicate_annotation_ids",
    "duplicate_group_size",
    "duplicate_geometry_type",
    "duplicate_time_ambiguous",
    "active_time_key",
    "active_time",
    "active_time_source",
    "active_time_match_status",
    "active_time_source_file",
    "active_time_session_count",
    "active_time_event_count",
    "primary_active_time_eligible",
    "sensitivity_active_time_eligible",
    "lead_time_seconds",
    "geometry_hash",
    "n_corners",
    "parse_error",
    "eligible_for_primary_analysis",
    "exclusion_reason",
]

ACTIVE_FIELDS = [
    "project_id",
    "ls_runtime_task_id",
    "annotator_id",
    "worker_id",
    "annotation_id",
    "active_time_key",
    "active_time_source",
    "active_time_match_status",
    "active_time",
    "active_time_session_count",
    "active_time_event_count",
    "active_time_source_file",
    "primary_active_time_eligible",
    "binding_status",
]

REALIZED_FIELDS = [
    "public_worker_code",
    "worker_id",
    "project_id",
    "planned_project_name",
    "ls_runtime_task_id",
    "planned_inner_id",
    "task_code",
    "task_id",
    "base_task_id",
    "dataset_group",
    "assigned_expected",
    "appears_in_internal_distribution",
    "appears_in_assignment_manifest",
    "outside_assignment_submission",
    "duplicate_worker_task_submission",
    "mapping_status",
]


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def _write_csv(path: Path, fields: list[str], rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _snapshot(path: Path, out: Path, kind: str) -> dict[str, str]:
    exists = path.exists()
    snap = out / "snapshots" / path.name
    size = ""
    digest = ""
    if exists and path.is_file():
        snap.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, snap)
        size = str(path.stat().st_size)
        digest = _sha256(snap)
    return {
        "source_path": str(path),
        "snapshot_path": str(snap) if exists and path.is_file() else "",
        "exists": str(exists).lower(),
        "bytes": size,
        "sha256": digest,
        "source_kind": kind,
        "data_complete": "false",
        "completion_basis": COMPLETION_BASIS,
    }


def _load_export(path: Path) -> list[dict[str, Any]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, list):
        raise ValueError(f"{path} is not a Label Studio task-list export")
    return payload


def _task_lookup(export_path: Path) -> dict[tuple[str, str], dict[str, str]]:
    out = {}
    for idx, task in enumerate(_load_export(export_path), start=1):
        data = task.get("data") if isinstance(task.get("data"), dict) else {}
        project_id = str(task.get("project") or "")
        runtime_task_id = str(task.get("id") or task.get("task_id") or f"task_index_{idx}")
        out[(project_id, runtime_task_id)] = {
            "task_id": str(data.get("task_id") or ""),
            "base_task_id": str(data.get("base_task_id") or ""),
            "condition": str(data.get("condition") or ""),
            "source_draft": str(data.get("source_draft") or ""),
            "runtime_inner_id": str(task.get("inner_id") or ""),
        }
    return out


def _planned_group(source_draft: str) -> tuple[str, str]:
    if source_draft == "anchor":
        return "Calibration_anchor", "C1_anchor_all"
    if source_draft == "core":
        return "Calibration_core", "C1_core_all"
    if source_draft == "semi":
        return "Calibration_semi", "C1_semi"
    return "", ""


def _planned_mapping(root: Path) -> dict[tuple[str, str], dict[str, str]]:
    rows = _read_csv(root / REBUILD_DIR / "ls_project_mapping_audit_v3_1.csv")
    return {
        (row["intended_project_group"], row["base_task_id"]): row
        for row in rows
    }


def _public(worker_id: str) -> str:
    return f"W{int(worker_id):03d}" if str(worker_id).isdigit() else f"W{worker_id}"


def _assignment_sets(root: Path) -> tuple[set[tuple[str, str, str, str]], set[tuple[str, str, str, str]]]:
    manual = _read_csv(root / REBUILD_DIR / "assignment_manifest_C1_manual_draft_v3_1.csv")
    semi = _read_csv(root / REBUILD_DIR / "assignment_manifest_C1_semi_draft_v3_1.csv")
    assignment = {(r["worker_id"], r["task_id"], r["base_task_id"], r["dataset_group"]) for r in manual + semi}
    internal = _read_csv(root / REBUILD_DIR / "worker_distribution_internal_manifest_v3_1.csv")
    internal_set = {(r["worker_id"], r["task_id"], r["base_task_id"], r["dataset_group"]) for r in internal}
    return assignment, internal_set


def _binding_status(row: dict[str, Any]) -> str:
    source = row.get("active_time_source")
    status = str(row.get("active_time_match_status") or "")
    if source == "log" and status == "project+task+annotator+annotation":
        return "annotation_level_log_match"
    if source == "log":
        return "task_level_fallback_only"
    if source == "lead_time_fallback":
        return "lead_time_fallback_only"
    if "ambiguous" in status:
        return "ambiguous_log_match"
    return "missing_log"


def _event_flags(active_log: Path) -> dict[tuple[str, str, str], dict[str, bool]]:
    flags: dict[tuple[str, str, str], dict[str, bool]] = defaultdict(lambda: {"has_intermediate": False, "has_final": False})
    if not active_log.exists():
        return flags
    with active_log.open("r", encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            try:
                item = json.loads(line)
            except json.JSONDecodeError:
                continue
            key = (str(item.get("project_id") or ""), str(item.get("task_id") or ""), str(item.get("annotator_id") or ""))
            if item.get("is_manual_flush") is True:
                flags[key]["has_final"] = True
            else:
                flags[key]["has_intermediate"] = True
    return flags


def build(root: Path, export_path: Path, active_log_path: Path) -> dict[str, Any]:
    out = root / OUT_DIR
    out.mkdir(parents=True, exist_ok=True)
    manifest_rows = [
        _snapshot(export_path, out, "manual_zh_label_studio_export"),
        _snapshot(active_log_path, out, "active_log"),
    ]
    _write_csv(out / "raw_input_manifest_manual_zh_precheck_v3_1.csv", list(manifest_rows[0]), manifest_rows)

    canonical_base, _duplicates, base_summary = build_canonical_tables([export_path], active_log_path)
    task_lookup = _task_lookup(export_path)
    planned = _planned_mapping(root)
    assignments, internal = _assignment_sets(root)
    behavior = _event_flags(active_log_path)

    canonical_rows: list[dict[str, Any]] = []
    active_rows: list[dict[str, Any]] = []
    realized_rows: list[dict[str, Any]] = []
    worker_task_seen: Counter[tuple[str, str, str, str]] = Counter()

    for row in canonical_base:
        project_id = str(row["project_id"])
        runtime_task_id = str(row["task_id"])
        info = task_lookup.get((project_id, runtime_task_id), {})
        dataset_group, planned_project = _planned_group(info.get("source_draft", ""))
        mapping = planned.get((dataset_group, info.get("base_task_id", "")), {})
        worker_id = str(row["annotator_id"])
        task_id = info.get("task_id", "")
        base_task_id = info.get("base_task_id", "")
        worker_task_seen[(worker_id, task_id, base_task_id, dataset_group)] += 1
        key = (worker_id, task_id, base_task_id, dataset_group)
        assigned = key in assignments
        in_internal = key in internal
        duplicate_worker_task = worker_task_seen[key] > 1
        binding = _binding_status(row)
        active_key = f"{project_id}|{runtime_task_id}|{worker_id}|{row['annotation_id']}"
        common = {
            "ls_runtime_task_id": runtime_task_id,
            "planned_project_name": planned_project,
            "planned_inner_id": mapping.get("inner_id", ""),
            "task_code": f"{ENTRY_BY_GROUP.get(dataset_group, '')}-{mapping.get('inner_id', '')}" if dataset_group and mapping.get("inner_id") else "",
            "task_id": task_id,
            "base_task_id": base_task_id,
            "dataset_group": dataset_group,
            "condition": info.get("condition", ""),
            "worker_id": worker_id,
            "active_time_key": active_key,
        }
        c_row = {**row, **common}
        c_row["task_id"] = task_id
        c_row["eligible_for_primary_analysis"] = str(assigned and in_internal and row.get("primary_active_time_eligible") is True).lower()
        c_row["exclusion_reason"] = "" if c_row["eligible_for_primary_analysis"] == "true" else "manual_zh_precheck_not_primary_or_not_assigned"
        canonical_rows.append({field: c_row.get(field, "") for field in CANONICAL_FIELDS})
        active_rows.append(
            {
                "project_id": project_id,
                "ls_runtime_task_id": runtime_task_id,
                "annotator_id": worker_id,
                "worker_id": worker_id,
                "annotation_id": row.get("annotation_id", ""),
                "active_time_key": active_key,
                "active_time_source": row.get("active_time_source", ""),
                "active_time_match_status": row.get("active_time_match_status", ""),
                "active_time": row.get("active_time", ""),
                "active_time_session_count": row.get("active_time_session_count", ""),
                "active_time_event_count": row.get("active_time_event_count", ""),
                "active_time_source_file": row.get("active_time_source_file", ""),
                "primary_active_time_eligible": row.get("primary_active_time_eligible", False),
                "binding_status": binding,
            }
        )
        realized_rows.append(
            {
                "public_worker_code": _public(worker_id),
                "worker_id": worker_id,
                "project_id": project_id,
                "planned_project_name": planned_project,
                "ls_runtime_task_id": runtime_task_id,
                "planned_inner_id": mapping.get("inner_id", ""),
                "task_code": common["task_code"],
                "task_id": task_id,
                "base_task_id": base_task_id,
                "dataset_group": dataset_group,
                "assigned_expected": str(assigned).lower(),
                "appears_in_internal_distribution": str(in_internal).lower(),
                "appears_in_assignment_manifest": str(assigned).lower(),
                "outside_assignment_submission": str(not assigned).lower(),
                "duplicate_worker_task_submission": str(duplicate_worker_task).lower(),
                "mapping_status": mapping.get("mapping_status", "missing_mapping"),
            }
        )

    _write_csv(out / "manual_zh_canonical_annotations_precheck_v3_1.csv", CANONICAL_FIELDS, canonical_rows)
    _write_csv(out / "manual_zh_active_time_binding_audit_v3_1.csv", ACTIVE_FIELDS, active_rows)
    _write_csv(out / "manual_zh_realized_vs_assigned_audit_v3_1.csv", REALIZED_FIELDS, realized_rows)

    bind_counts = Counter(row["binding_status"] for row in active_rows)
    outside_count = sum(row["outside_assignment_submission"] == "true" for row in realized_rows)
    duplicate_worker_count = sum(row["duplicate_worker_task_submission"] == "true" for row in realized_rows)
    annotation_present = sum(bool(row["annotation_id"]) and not str(row["annotation_id"]).startswith("annotation_index_") for row in canonical_rows)
    behavior_not_strict = sum(not behavior[(row["project_id"], row["ls_runtime_task_id"], row["worker_id"])]["has_intermediate"] for row in canonical_rows)
    bare_inner_dups = any(count > 1 for count in Counter(row["planned_inner_id"] for row in realized_rows if row["planned_inner_id"]).values())
    summary = {
        "passed": False,
        "status": "manual_zh_analysis_chain_precheck",
        "scope": "manual_zh_smoke_fixture_only",
        "statistical_interpretation_allowed": False,
        "full_c1_smoke_test_passed": False,
        "n_exported_tasks": base_summary["n_tasks_seen"],
        "n_raw_annotations": base_summary["n_raw_annotation_rows"],
        "n_canonical_annotations": len(canonical_rows),
        "annotation_id_present_count": annotation_present,
        "annotation_id_missing_count": len(canonical_rows) - annotation_present,
        "annotation_level_log_match_count": bind_counts["annotation_level_log_match"],
        "task_level_fallback_count": bind_counts["task_level_fallback_only"],
        "lead_time_fallback_count": bind_counts["lead_time_fallback_only"],
        "missing_log_count": bind_counts["missing_log"],
        "primary_active_time_eligible_count": sum(str(row["primary_active_time_eligible"]) == "True" for row in active_rows),
        "duplicate_group_count": base_summary["n_duplicate_groups"],
        "revision_group_count": base_summary["n_revision_groups"],
        "outside_assignment_submission_count": outside_count,
        "duplicate_worker_task_submission_count": duplicate_worker_count,
        "manifest_back_match_passed": outside_count == 0 and all(row["appears_in_internal_distribution"] == "true" for row in realized_rows),
        "active_time_binding_passed": bool(bind_counts["annotation_level_log_match"] or bind_counts["task_level_fallback_only"]),
        "canonicalization_passed": bool(canonical_rows) and annotation_present > 0,
        "realized_vs_assigned_passed": outside_count == 0 and duplicate_worker_count == 0,
        "worker_facing_bare_inner_id_ambiguity_detected": bare_inner_dups,
        "behavior_not_strictly_verified_count": behavior_not_strict,
        "blockers": [],
        "warnings": [],
    }
    if outside_count:
        summary["blockers"].append("outside_assignment_submission_detected")
    if duplicate_worker_count:
        summary["blockers"].append("duplicate_worker_task_submission_detected")
    if bind_counts["task_level_fallback_only"]:
        summary["warnings"].append("active_log_task_level_fallback_only")
    if bare_inner_dups:
        summary["warnings"].append("bare_inner_id_ambiguous_across_projects_use_entry_plus_inner_id")
    if behavior_not_strict:
        summary["warnings"].append("behavior_not_strictly_verified_for_some_rows")
    summary["passed"] = all(
        [
            summary["canonicalization_passed"],
            summary["active_time_binding_passed"],
            summary["manifest_back_match_passed"],
            summary["realized_vs_assigned_passed"],
            summary["annotation_id_present_count"] > 0,
            summary["lead_time_fallback_count"] == 0 or summary["primary_active_time_eligible_count"] < len(canonical_rows),
        ]
    )
    _write_json(out / "manual_zh_analysis_chain_precheck_summary_v3_1.json", summary)
    _write_report(out / "manual_zh_analysis_chain_precheck_report_v3_1.md", summary)
    return summary


def _write_report(path: Path, summary: dict[str, Any]) -> None:
    lines = [
        "# manual_zh analysis-chain precheck v3.1",
        "",
        "本检查只是 manual_zh smoke fixture，用于验证 analysis-chain integration，不是 C1 statistical closeout。",
        "",
        f"- passed: {summary['passed']}",
        f"- statistical_interpretation_allowed: {summary['statistical_interpretation_allowed']}",
        f"- full_c1_smoke_test_passed: {summary['full_c1_smoke_test_passed']}",
        f"- annotation_id_present_count: {summary['annotation_id_present_count']}",
        f"- annotation_level_log_match_count: {summary['annotation_level_log_match_count']}",
        f"- task_level_fallback_count: {summary['task_level_fallback_count']}",
        f"- outside_assignment_submission_count: {summary['outside_assignment_submission_count']}",
        f"- duplicate_worker_task_submission_count: {summary['duplicate_worker_task_submission_count']}",
        f"- worker_facing_bare_inner_id_ambiguity_detected: {summary['worker_facing_bare_inner_id_ambiguity_detected']}",
        "",
        "已检查字段方向：annotation_id 保留、canonical_annotation_id 生成、active-log 不使用 lead_time 作为 primary、planned_inner_id 不替代 LS runtime task id。",
        "",
        "待 full C1 export 后验证：全 worker 覆盖、全部项目导出、正式 realized-vs-assigned、完整 active-log 行为事件。",
    ]
    if summary["blockers"]:
        lines += ["", "## Blockers", *[f"- {item}" for item in summary["blockers"]]]
    if summary["warnings"]:
        lines += ["", "## Warnings", *[f"- {item}" for item in summary["warnings"]]]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manual-zh-export", type=Path, default=DEFAULT_EXPORT)
    parser.add_argument("--active-log", type=Path, default=DEFAULT_ACTIVE_LOG)
    parser.add_argument("--root", type=Path, default=Path("."))
    args = parser.parse_args()
    build(args.root.resolve(), args.manual_zh_export, args.active_log)


if __name__ == "__main__":
    main()
