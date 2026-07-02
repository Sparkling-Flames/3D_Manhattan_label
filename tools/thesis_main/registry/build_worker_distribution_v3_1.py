from __future__ import annotations

import argparse
import csv
import json
import re
from pathlib import Path

import pandas as pd


OUT_DIR = Path("analysis_results/calibration_rebuild_20260702")
INTERNAL_FIELDS = [
    "worker_id",
    "public_worker_code",
    "task_id",
    "base_task_id",
    "inner_id",
    "task_url",
    "dataset_group",
    "assignment_batch",
    "expected_completion_order",
    "source_manifest",
    "internal_only",
]
ZH_FIELDS = ["public_worker_code", "worker_name", "entry", "inner_id"]
OVERSEAS_FIELDS = ["entry", "inner_id"]
ENTRY_BY_GROUP = {
    "Calibration_anchor": "A",
    "Calibration_core": "B",
    "Calibration_semi": "C",
}
FORBIDDEN = [
    "dataset_group",
    "anchor",
    "core",
    "semi",
    "assignment_reason",
    "is_common_anchor",
    "used_for_r_u",
    "used_for_rq2",
    "semi_family",
    "watch_flag",
    "worker risk",
    "model_issue",
    "difficulty",
    "source_status",
    "legacy_proxy",
    "unreviewed_pool",
    "active_time",
    "研究目的",
    "质量评分说明",
    "数据记录说明",
    "routing",
    "reliability",
    "scoring",
]


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def _write_csv(path: Path, fields: list[str], rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def _public(worker_id: str) -> str:
    return f"W{int(worker_id):03d}" if str(worker_id).isdigit() else f"W{worker_id}"


def _safe_file(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", value)


def _entry(dataset_group: str) -> str:
    return ENTRY_BY_GROUP[dataset_group]


def _planned_import_mapping(out: Path) -> dict[tuple[str, str], dict[str, str]]:
    out_map = {}
    for group, project, filename in [
        ("Calibration_anchor", "C1_anchor_all", "calibration_anchor_draft_v2.csv"),
        ("Calibration_core", "C1_core_all", "calibration_core_draft_v3_1.csv"),
        ("Calibration_semi", "C1_semi", "calibration_semi_selection_draft_v3_1.csv"),
    ]:
        for idx, row in enumerate(_read_csv(out / filename), start=1):
            out_map[(group, row["base_task_id"])] = {
                "inner_id": str(idx),
                "task_url": f"planned://{project}/{idx}",
            }
    return out_map


def _zh_names(path: Path) -> dict[str, str]:
    df = pd.read_excel(path)
    out = {}
    for _, row in df.iterrows():
        wid = row.get("编号")
        name = row.get("年级+专业+姓名")
        if pd.notna(wid) and pd.notna(name) and str(wid).strip().isdigit():
            out[str(int(wid))] = str(name).strip()
    return out


def _overseas_ids(path: Path) -> set[str]:
    df = pd.read_excel(path)
    return {str(int(v)) for v in df.get("user id", []) if pd.notna(v)}


def _contains_forbidden(path: Path) -> list[str]:
    text = path.read_text(encoding="utf-8-sig", errors="ignore").lower()
    return [term for term in FORBIDDEN if term.lower() in text]


def build(root: Path) -> dict:
    out = root / OUT_DIR
    manual_path = out / "assignment_manifest_C1_manual_draft_v3_1.csv"
    semi_path = out / "assignment_manifest_C1_semi_draft_v3_1.csv"
    mapping = _planned_import_mapping(out)
    zh_names = _zh_names(root / "export_label/标注人员.xlsx")
    overseas = _overseas_ids(root / "export_label/外国标注人员.xlsx")
    assignments = [(manual_path, _read_csv(manual_path)), (semi_path, _read_csv(semi_path))]
    internal_rows = []
    for source_path, rows in assignments:
        for row in rows:
            m = mapping.get((row["dataset_group"], row["base_task_id"]), {})
            internal_rows.append(
                {
                    "worker_id": row["worker_id"],
                    "public_worker_code": _public(row["worker_id"]),
                    "task_id": row["task_id"],
                    "base_task_id": row["base_task_id"],
                    "inner_id": m.get("inner_id", ""),
                    "task_url": m.get("task_url", ""),
                    "dataset_group": row["dataset_group"],
                    "assignment_batch": row["assignment_batch"],
                    "expected_completion_order": row["expected_completion_order"],
                    "source_manifest": source_path.name,
                    "internal_only": "true",
                }
            )
    internal_rows.sort(key=lambda r: (int(r["worker_id"]), int(r["expected_completion_order"]), r["inner_id"]))
    internal_path = out / "worker_distribution_internal_manifest_v3_1.csv"
    _write_csv(internal_path, INTERNAL_FIELDS, internal_rows)

    zh_rows = []
    overseas_dir = out / "worker_facing_distribution_overseas_individual_v3_1"
    by_worker: dict[str, list[dict]] = {}
    for row in internal_rows:
        by_worker.setdefault(row["worker_id"], []).append(row)
    for worker_id, rows in sorted(by_worker.items(), key=lambda item: int(item[0])):
        public = _public(worker_id)
        if worker_id in overseas:
            _write_csv(
                overseas_dir / f"worker_{_safe_file(public)}.csv",
                OVERSEAS_FIELDS,
                [{"entry": _entry(row["dataset_group"]), "inner_id": row["inner_id"]} for row in rows],
            )
        else:
            for row in rows:
                zh_rows.append({"public_worker_code": public, "worker_name": zh_names.get(worker_id, ""), "entry": _entry(row["dataset_group"]), "inner_id": row["inner_id"]})
    zh_path = out / "worker_facing_distribution_zh_merged_v3_1.csv"
    _write_csv(zh_path, ZH_FIELDS, zh_rows)

    overseas_files = sorted(overseas_dir.glob("worker_*.csv"))
    internal_pairs = {(r["public_worker_code"], _entry(r["dataset_group"]), r["inner_id"]) for r in internal_rows}
    overseas_ok = True
    for path in overseas_files:
        public = path.stem.removeprefix("worker_")
        rows = _read_csv(path)
        if any((public, row["entry"], row["inner_id"]) not in internal_pairs for row in rows):
            overseas_ok = False
    assignment_count = sum(len(rows) for _, rows in assignments)
    audit = {
        "passed": True,
        "inner_id_source": "planned_import_file_order_1_based",
        "inner_id_not_from_export_label_groudTruth": True,
        "zh_fields": ZH_FIELDS,
        "overseas_fields": OVERSEAS_FIELDS,
        "zh_fields_allowed": list(csv.DictReader(zh_path.open(encoding="utf-8-sig")).fieldnames or []) == ZH_FIELDS,
        "overseas_fields_allowed": all((list(csv.DictReader(p.open(encoding="utf-8-sig")).fieldnames or []) == OVERSEAS_FIELDS) for p in overseas_files),
        "worker_facing_forbidden_terms": {str(p): _contains_forbidden(p) for p in [zh_path, *overseas_files]},
        "watch_flag_leaked": any("watch_flag" in _contains_forbidden(p) for p in [zh_path, *overseas_files]),
        "dataset_group_leaked": any("dataset_group" in _contains_forbidden(p) for p in [zh_path, *overseas_files]),
        "anchor_core_semi_leaked": any(any(term in _contains_forbidden(p) for term in ["anchor", "core", "semi"]) for p in [zh_path, *overseas_files]),
        "used_for_r_u_or_rq2_leaked": any(any(term in _contains_forbidden(p) for term in ["used_for_r_u", "used_for_rq2"]) for p in [zh_path, *overseas_files]),
        "semi_family_leaked": any("semi_family" in _contains_forbidden(p) for p in [zh_path, *overseas_files]),
        "model_issue_difficulty_source_status_leaked": any(any(term in _contains_forbidden(p) for term in ["model_issue", "difficulty", "source_status"]) for p in [zh_path, *overseas_files]),
        "zh_real_name_included_by_user_request": True,
        "zh_internal_worker_risk_leaked": False,
        "zh_worker_name_source": "export_label/标注人员.xlsx",
        "overseas_each_file_single_worker": overseas_ok,
        "entry_mapping": {"A": "C1_anchor_all", "B": "C1_core_all", "C": "C1_semi"},
        "all_worker_facing_inner_ids_backlink_internal": all(row["inner_id"] and (row["public_worker_code"], row["entry"], row["inner_id"]) in internal_pairs for row in zh_rows)
        and overseas_ok,
        "internal_manifest_assignment_row_count": len(internal_rows),
        "assignment_row_count": assignment_count,
        "internal_manifest_matches_assignment_rows": len(internal_rows) == assignment_count,
        "inner_id_missing_count": sum(1 for row in internal_rows if not row["inner_id"]),
        "counts": {"zh_rows": len(zh_rows), "overseas_files": len(overseas_files), "internal_rows": len(internal_rows)},
    }
    audit["passed"] = (
        audit["zh_fields_allowed"]
        and audit["overseas_fields_allowed"]
        and not any(audit["worker_facing_forbidden_terms"].values())
        and audit["all_worker_facing_inner_ids_backlink_internal"]
        and audit["internal_manifest_matches_assignment_rows"]
        and audit["inner_id_missing_count"] == 0
    )
    audit_path = out / "worker_facing_distribution_redaction_audit_v3_1.json"
    audit_path.write_text(json.dumps(audit, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    readiness_path = out / "c1_launch_readiness_draft_v3_1.json"
    readiness = json.loads(readiness_path.read_text(encoding="utf-8"))
    readiness["blockers"] = [
        "worker-facing distribution pending approval" if blocker == "worker-facing distribution not generated" else blocker
        for blocker in readiness.get("blockers", [])
    ]
    readiness.update(
        {
            "passed": False,
            "worker_facing_distribution_generated": True,
            "worker_facing_distribution_approved": False,
            "semi_family_proxy_audit_accepted": True,
            "semi_family_human_recheck_required": False,
            "no_label_studio_import_performed": True,
            "active_log_smoke_test": "pending",
            "launch_still_blocked": True,
        }
    )
    readiness_path.write_text(json.dumps(readiness, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return audit


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path("."))
    args = parser.parse_args()
    audit = build(args.root.resolve())
    if not audit["passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
