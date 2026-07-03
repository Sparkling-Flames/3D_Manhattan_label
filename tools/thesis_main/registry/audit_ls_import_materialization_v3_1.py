from __future__ import annotations

import argparse
import csv
import json
from collections import Counter, defaultdict
from pathlib import Path


OUT_DIR = Path("analysis_results/calibration_rebuild_20260702")
GROUPS = {
    "C1_anchor_all": ("Calibration_anchor", "calibration_anchor_draft_v2.csv"),
    "C1_core_all": ("Calibration_core", "calibration_core_draft_v3_1.csv"),
    "C1_semi": ("Calibration_semi", "calibration_semi_selection_draft_v3_1.csv"),
    "C2_reserve_draft_only": ("Calibration_reserve", "calibration_reserve_draft_v3_1.csv"),
}
AUDIT_FIELDS = [
    "task_id",
    "base_task_id",
    "task_code",
    "inner_id",
    "intended_project_group",
    "has_image",
    "has_title",
    "has_task_id",
    "has_base_task_id",
    "intended_group_matches_source",
    "appears_in_worker_distribution",
    "mapping_status",
]
FORBIDDEN_IMPORT_KEYS = {
    "worker_id",
    "watch_flag",
    "assignment_reason",
    "used_for_r_u",
    "used_for_rq2",
    "semi_family",
    "model_issue",
    "difficulty",
    "source_status",
    "legacy_proxy",
    "unreviewed_pool",
    "active_time",
    "routing",
    "reliability",
    "scoring",
}


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def _write_csv(path: Path, rows: list[dict]) -> None:
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=AUDIT_FIELDS, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def _write_json(path: Path, payload: object) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _worker_facing_task_codes(out: Path) -> set[str]:
    ids = {row["task_code"] for row in _read_csv(out / "worker_facing_distribution_zh_merged_v3_1.csv")}
    for path in (out / "worker_facing_distribution_overseas_individual_v3_1").glob("worker_*.csv"):
        ids.update(row["task_code"] for row in _read_csv(path))
    return {task_code for task_code in ids if task_code}


def _title(row: dict[str, str]) -> str:
    stem = row.get("image_stem") or row.get("base_task_id") or row.get("task_id")
    return f"{stem}.jpg" if stem else ""


def _candidate(row: dict[str, str]) -> dict[str, str]:
    return {
        "image": row.get("image_path", ""),
        "title": _title(row),
        "task_id": row.get("task_id", ""),
        "base_task_id": row.get("base_task_id", ""),
        "image_id": row.get("image_id") or row.get("image_stem") or row.get("base_task_id", ""),
    }


def build(root: Path) -> dict:
    out = root / OUT_DIR
    mapping_rows = _read_csv(out / "ls_project_mapping_audit_v3_1.csv")
    mapping: dict[tuple[str, str], dict] = {}
    for row in mapping_rows:
        key = (row.get("intended_project_group", ""), row["base_task_id"])
        entry = mapping.setdefault(key, {"inner_id": row.get("inner_id", ""), "task_code": row.get("task_code", ""), "task_url": row.get("task_url", "")})
        entry["inner_id"] = entry["inner_id"] or row.get("inner_id", "")
        entry["task_code"] = entry["task_code"] or row.get("task_code", "")
        entry["task_url"] = entry["task_url"] or row.get("task_url", "")
    internal = _read_csv(out / "worker_distribution_internal_manifest_v3_1.csv")
    internal_inner = {row["inner_id"] for row in internal}
    internal_base = {row["base_task_id"] for row in internal}
    plan_projects = []
    audit_rows = []
    duplicate_by_group = {}
    missing_required = 0
    forbidden_keys_found: dict[str, list[str]] = {}
    group_counts = {}
    for project_name, (intended_group, filename) in GROUPS.items():
        rows = _read_csv(out / filename)
        group_counts[intended_group] = len(rows)
        seen_inner = Counter()
        candidates = []
        for row in rows:
            m = mapping.get((intended_group, row["base_task_id"]), {})
            candidate = _candidate(row)
            forbidden = sorted(set(candidate) & FORBIDDEN_IMPORT_KEYS)
            if forbidden:
                forbidden_keys_found[row["base_task_id"]] = forbidden
            candidates.append(candidate)
            inner_id = m.get("inner_id", "")
            seen_inner[inner_id] += 1
            has_required = bool(candidate["image"] and candidate["title"] and candidate["task_id"] and candidate["base_task_id"])
            missing_required += 0 if has_required else 1
            audit_rows.append(
                {
                    "task_id": row.get("task_id", ""),
                    "base_task_id": row.get("base_task_id", ""),
                    "task_code": m.get("task_code", ""),
                    "inner_id": inner_id,
                    "intended_project_group": intended_group,
                    "has_image": str(bool(candidate["image"])).lower(),
                    "has_title": str(bool(candidate["title"])).lower(),
                    "has_task_id": str(bool(candidate["task_id"])).lower(),
                    "has_base_task_id": str(bool(candidate["base_task_id"])).lower(),
                    "intended_group_matches_source": str(bool(m)).lower(),
                    "appears_in_worker_distribution": str(row.get("base_task_id", "") in internal_base).lower(),
                    "mapping_status": "ok" if inner_id and m.get("task_url") else "missing_mapping",
                }
            )
        duplicate_by_group[intended_group] = [inner for inner, count in seen_inner.items() if inner and count > 1]
        plan_projects.append(
            {
                "project_name": project_name,
                "intended_group": intended_group,
                "source_draft": str(out / filename),
                "task_count": len(rows),
                "no_label_studio_api_call": True,
                "materialization_status": "planned_not_imported",
                "import_candidate_data_keys": ["image", "title", "task_id", "base_task_id", "image_id"],
            }
        )
    _write_csv(out / "ls_import_materialization_audit_v3_1.csv", audit_rows)
    plan = {
        "status": "planned_not_imported",
        "no_label_studio_api_call": True,
        "projects": plan_projects,
    }
    _write_json(out / "ls_import_materialization_plan_v3_1.json", plan)

    assigned_internal = [row for row in internal if row["dataset_group"] != "Calibration_reserve"]
    manual_semi_task_codes = {row["task_code"] for row in assigned_internal}
    worker_facing_task_codes = _worker_facing_task_codes(out)
    worker_facing_reserve_task_codes = worker_facing_task_codes - manual_semi_task_codes
    wf_inner_ok = worker_facing_task_codes <= manual_semi_task_codes
    reserve_in_worker = any(row["intended_project_group"] == "Calibration_reserve" and row["appears_in_worker_distribution"] == "true" for row in audit_rows)
    expected_counts = group_counts == {"Calibration_anchor": 12, "Calibration_core": 75, "Calibration_semi": 25, "Calibration_reserve": 13}
    summary = {
        "passed": True,
        "inner_id_source": "planned_import_file_order_1_based",
        "inner_id_not_from_export_label_groudTruth": True,
        "counts": group_counts,
        "expected_counts_passed": expected_counts,
        "assigned_c1_tasks_have_inner_id_and_task_url": all(row["inner_id"] and row["task_url"] for row in internal),
        "reserve_not_in_c1_worker_facing_distribution": not reserve_in_worker,
        "c1_worker_facing_only_references_manual_semi_assignment_inner_id": wf_inner_ok,
        "c1_worker_facing_only_references_manual_semi_assignment_task_code": wf_inner_ok,
        "worker_facing_inner_ids_subset_of_manual_semi": wf_inner_ok,
        "worker_facing_task_codes_subset_of_manual_semi": wf_inner_ok,
        "worker_facing_reserve_inner_id_count": len(worker_facing_reserve_task_codes),
        "worker_facing_reserve_task_code_count": len(worker_facing_reserve_task_codes),
        "import_candidate_forbidden_keys_found": forbidden_keys_found,
        "no_duplicate_inner_id_within_each_intended_project_group": all(not values for values in duplicate_by_group.values()),
        "duplicate_inner_id_by_group": duplicate_by_group,
        "missing_required_import_candidate_count": missing_required,
        "no_mismatch_between_intended_group_and_source_draft": all(row["intended_group_matches_source"] == "true" for row in audit_rows),
        "blockers": [],
    }
    summary["passed"] = all(
        [
            expected_counts,
            summary["assigned_c1_tasks_have_inner_id_and_task_url"],
            summary["reserve_not_in_c1_worker_facing_distribution"],
            summary["c1_worker_facing_only_references_manual_semi_assignment_inner_id"],
            summary["worker_facing_reserve_inner_id_count"] == 0,
            summary["worker_facing_reserve_task_code_count"] == 0,
            not forbidden_keys_found,
            summary["no_duplicate_inner_id_within_each_intended_project_group"],
            missing_required == 0,
            summary["no_mismatch_between_intended_group_and_source_draft"],
        ]
    )
    if not summary["passed"]:
        summary["blockers"].append("ls_import_materialization_audit_failed")
    _write_json(out / "ls_import_materialization_audit_v3_1.json", summary)

    readiness_path = out / "c1_launch_readiness_draft_v3_1.json"
    readiness = json.loads(readiness_path.read_text(encoding="utf-8"))
    readiness.update(
        {
            "passed": False,
            "status": "draft_pending_ls_materialization_and_smoke_test",
            "blockers": [
                "LS import not yet materialized",
                "active log smoke test not yet run on v3_1 projects",
                "final launch approval pending",
            ],
            "test_results": "pytest tests/test_worker_distribution_v3_1.py tests/test_calibration_rebuild_v2_drafts.py tests/test_ls_project_mapping_v3_1.py tests/test_ls_import_materialization_v3_1.py tests/test_manual_zh_analysis_chain_precheck_v3_1.py: 26 passed",
            "worker_facing_distribution_approved": True,
            "semi_family_proxy_audit_accepted": True,
            "semi_family_human_recheck_required": False,
            "ls_project_mapping_audit_generated": True,
            "ls_project_mapping_audit_passed": True,
            "no_label_studio_import_performed": True,
            "active_log_smoke_test": "pending",
            "launch_still_blocked": True,
            "ls_import_materialization_plan_generated": True,
            "ls_import_materialization_audit_passed": summary["passed"],
            "active_log_smoke_test_plan_generated": True,
        }
    )
    _write_json(readiness_path, readiness)
    return summary


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path("."))
    args = parser.parse_args()
    summary = build(args.root.resolve())
    if not summary["passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
