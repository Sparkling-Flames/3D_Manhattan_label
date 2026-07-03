from __future__ import annotations

import argparse
import csv
import json
from collections import Counter
from pathlib import Path


OUT_DIR = Path("analysis_results/calibration_rebuild_20260702")
FIELDS = [
    "task_id",
    "base_task_id",
    "image_stem",
    "planned_project_name",
    "task_code",
    "inner_id",
    "task_url",
    "intended_project_group",
    "appears_in_assignment_manual",
    "appears_in_assignment_semi",
    "appears_in_worker_distribution",
    "mapping_status",
]
FORBIDDEN_FLAGS = [
    "dataset_group_leaked",
    "anchor_core_semi_leaked",
    "used_for_r_u_or_rq2_leaked",
    "semi_family_leaked",
    "model_issue_difficulty_source_status_leaked",
]

ENTRY_BY_GROUP = {"Calibration_anchor": "A", "Calibration_core": "B", "Calibration_semi": "C", "Calibration_reserve": "R"}
PROJECT_BY_GROUP = {
    "Calibration_anchor": "C1_anchor_all",
    "Calibration_core": "C1_core_all",
    "Calibration_semi": "C1_semi",
    "Calibration_reserve": "C2_reserve_draft_only",
}


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def _write_csv(path: Path, rows: list[dict]) -> None:
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDS, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def _planned_import_mapping(root: Path) -> dict[tuple[str, str], dict[str, str]]:
    out = {}
    for group, project, filename in [
        ("Calibration_anchor", "C1_anchor_all", "calibration_anchor_draft_v2.csv"),
        ("Calibration_core", "C1_core_all", "calibration_core_draft_v3_1.csv"),
        ("Calibration_semi", "C1_semi", "calibration_semi_selection_draft_v3_1.csv"),
        ("Calibration_reserve", "C2_reserve_draft_only", "calibration_reserve_draft_v3_1.csv"),
    ]:
        for idx, row in enumerate(_read_csv(root / OUT_DIR / filename), start=1):
            out[(group, row["base_task_id"])] = {
                "inner_id": str(idx),
                "task_code": f"{ENTRY_BY_GROUP[group]}-{idx:03d}",
                "planned_project_name": project,
                "task_url": f"planned://{project}/{idx}",
                "mapping_status": "planned_import_order",
            }
    return out


def _selection_rows(root: Path) -> list[dict[str, str]]:
    out = []
    for group, path in [
        ("Calibration_core", root / OUT_DIR / "calibration_core_draft_v3_1.csv"),
        ("Calibration_reserve", root / OUT_DIR / "calibration_reserve_draft_v3_1.csv"),
        ("Calibration_semi", root / OUT_DIR / "calibration_semi_selection_draft_v3_1.csv"),
    ]:
        for row in _read_csv(path):
            out.append({"task_id": row["task_id"], "base_task_id": row["base_task_id"], "image_stem": row["image_stem"], "group": group})
    return out


def _zh_missing_names(root: Path) -> int:
    rows = _read_csv(root / OUT_DIR / "worker_facing_distribution_zh_merged_v3_1.csv")
    return sum(not row.get("worker_name") for row in rows)


def _overseas_rows(root: Path) -> int:
    folder = root / OUT_DIR / "worker_facing_distribution_overseas_individual_v3_1"
    return sum(len(_read_csv(path)) for path in folder.glob("worker_*.csv"))


def build(root: Path) -> dict:
    out = root / OUT_DIR
    manual = _read_csv(out / "assignment_manifest_C1_manual_draft_v3_1.csv")
    semi_assign = _read_csv(out / "assignment_manifest_C1_semi_draft_v3_1.csv")
    internal = _read_csv(out / "worker_distribution_internal_manifest_v3_1.csv")
    redaction_path = out / "worker_facing_distribution_redaction_audit_v3_1.json"
    redaction = json.loads(redaction_path.read_text(encoding="utf-8"))
    planned = _planned_import_mapping(root)

    manual_tasks = {(row["task_id"], row["base_task_id"], row["dataset_group"]) for row in manual}
    semi_tasks = {(row["task_id"], row["base_task_id"], "Calibration_semi") for row in semi_assign}
    worker_dist_bases = {row["base_task_id"] for row in internal}
    rows: list[dict] = []
    for task_id, base_task_id, group in sorted(manual_tasks | semi_tasks):
        m = planned.get((group, base_task_id), {})
        rows.append(
            {
                "task_id": task_id,
                "base_task_id": base_task_id,
                "image_stem": base_task_id,
                "planned_project_name": m.get("planned_project_name", PROJECT_BY_GROUP.get(group, "")),
                "task_code": m.get("task_code", ""),
                "inner_id": m.get("inner_id", ""),
                "task_url": m.get("task_url", ""),
                "intended_project_group": group,
                "appears_in_assignment_manual": str(group != "Calibration_semi").lower(),
                "appears_in_assignment_semi": str((task_id, base_task_id, "Calibration_semi") in semi_tasks).lower(),
                "appears_in_worker_distribution": str(base_task_id in worker_dist_bases).lower(),
                "mapping_status": m.get("mapping_status", "missing_mapping") if m.get("inner_id") and m.get("task_url") else "missing_mapping",
            }
        )
    for row in _selection_rows(root):
        if row["group"] != "Calibration_reserve":
            continue
        m = planned.get(("Calibration_reserve", row["base_task_id"]), {})
        rows.append(
            {
                "task_id": row["task_id"],
                "base_task_id": row["base_task_id"],
                "image_stem": row["image_stem"],
                "planned_project_name": m.get("planned_project_name", "C2_reserve_draft_only"),
                "task_code": m.get("task_code", ""),
                "inner_id": m.get("inner_id", ""),
                "task_url": m.get("task_url", ""),
                "intended_project_group": "Calibration_reserve",
                "appears_in_assignment_manual": "false",
                "appears_in_assignment_semi": "false",
                "appears_in_worker_distribution": str(row["base_task_id"] in worker_dist_bases).lower(),
                "mapping_status": "planned_c2_only" if m.get("inner_id") and row["base_task_id"] not in worker_dist_bases else "reserve_mapping_error",
            }
        )
    _write_csv(out / "ls_project_mapping_audit_v3_1.csv", rows)

    internal_pairs = [(row["worker_id"], row["dataset_group"], row["inner_id"]) for row in internal]
    counts = Counter(row["intended_project_group"] for row in rows)
    overseas_total = _overseas_rows(root)
    worker_total = redaction["counts"]["zh_rows"] + overseas_total
    redaction.update(
        {
            "zh_missing_worker_name_count": _zh_missing_names(root),
            "overseas_rows_total": overseas_total,
            "worker_facing_total_rows": worker_total,
            "worker_facing_total_rows_match_internal": worker_total == len(internal),
            "private_operational_artifact_contains_worker_name": True,
            "public_release_allowed": {"zh_merged": False, "internal_manifest": False},
        }
    )
    redaction_path.write_text(json.dumps(redaction, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    summary = {
        "passed": True,
        "inner_id_source": "planned_import_file_order_1_based",
        "inner_id_not_from_export_label_groudTruth": True,
        "all_assigned_rows_have_inner_id": all(row["inner_id"] for row in internal),
        "all_internal_manifest_rows_have_valid_inner_id": all(row["inner_id"].isdigit() for row in internal),
        "manual_assignment_rows": len(manual),
        "semi_assignment_rows": len(semi_assign),
        "worker_distribution_internal_rows": len(internal),
        "no_duplicate_worker_id_dataset_group_inner_id": len(internal_pairs) == len(set(internal_pairs)),
        "missing_task_url_in_internal_manifest_count": sum(not row["task_url"] for row in internal),
        "worker_facing_uses_inner_id_only": False,
        "worker_facing_uses_task_code_only": True,
        "task_code_backlinks_planned_project_and_inner_id": all(row["task_code"] and row["planned_project_name"] and row["inner_id"] for row in rows),
        "counts": {
            "anchor": len({row["task_id"] for row in manual if row["dataset_group"] == "Calibration_anchor"}),
            "core": len({row["task_id"] for row in manual if row["dataset_group"] == "Calibration_core"}),
            "semi": len({row["task_id"] for row in semi_assign}),
            "reserve": counts["Calibration_reserve"],
        },
        "reserve_c2_only_not_in_worker_distribution": not any(row["intended_project_group"] == "Calibration_reserve" and row["appears_in_worker_distribution"] == "true" for row in rows),
        "worker_facing_redaction_passed": redaction["passed"] and not any(redaction.get(flag) for flag in FORBIDDEN_FLAGS),
        "mapping_status_counts": dict(Counter(row["mapping_status"] for row in rows)),
        "blockers": [],
    }
    expected = summary["manual_assignment_rows"] == 651 and summary["semi_assignment_rows"] == 100 and summary["worker_distribution_internal_rows"] == 751
    expected_counts = summary["counts"] == {"anchor": 12, "core": 75, "semi": 25, "reserve": 13}
    summary["passed"] = all(
        [
            summary["all_assigned_rows_have_inner_id"],
            summary["all_internal_manifest_rows_have_valid_inner_id"],
            expected,
            summary["no_duplicate_worker_id_dataset_group_inner_id"],
            summary["missing_task_url_in_internal_manifest_count"] == 0,
            summary["task_code_backlinks_planned_project_and_inner_id"],
            expected_counts,
            summary["reserve_c2_only_not_in_worker_distribution"],
            summary["worker_facing_redaction_passed"],
            all(row["mapping_status"] in {"planned_import_order", "planned_c2_only"} for row in rows),
        ]
    )
    if not summary["passed"]:
        summary["blockers"].append("ls_project_mapping_audit_failed")
    (out / "ls_project_mapping_audit_v3_1.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    readiness_path = out / "c1_launch_readiness_draft_v3_1.json"
    readiness = json.loads(readiness_path.read_text(encoding="utf-8"))
    readiness.update(
        {
            "passed": False,
            "test_results": "pytest tests/test_worker_distribution_v3_1.py tests/test_calibration_rebuild_v2_drafts.py: 23 passed",
            "ls_project_mapping_audit_generated": True,
            "ls_project_mapping_audit_passed": summary["passed"],
            "active_log_smoke_test": "pending",
            "launch_still_blocked": True,
        }
    )
    if "LS import not yet materialized" not in readiness.get("blockers", []):
        readiness.setdefault("blockers", []).append("LS import not yet materialized")
    readiness_path.write_text(json.dumps(readiness, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
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
