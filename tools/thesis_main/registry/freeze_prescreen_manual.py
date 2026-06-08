from __future__ import annotations

import argparse
import csv
import json
from collections import Counter
from pathlib import Path
from typing import Any


TRUTH_LAYER_DIRNAME = "truth_layer_extraction_20260324"
OUTPUT_DIRNAME = "phase1_progress_20260324"
REFERENCE_BINDING_STATUS = "working_consensus_reference_bound_not_final_gold"
ADJUDICATION_STATUS = "working_consensus_not_final_gold"
TARGET_ANCHOR_MIN = 20
TARGET_ANCHOR_MAX = 22
TARGET_TOTAL = 30
TARGET_NON_ANCHOR_MIN = 8
TARGET_NON_ANCHOR_MAX = 10

# 当前 manual pool 经逐条复核后，anchor candidate 比目标上限多 1 条。
# 先按这个顺序降到 non-anchor，以满足 22 个 anchor 的 thesis-facing 上限。
ANCHOR_DEMOTION_PRIORITY = ["509", "569"]

# 如果未来 anchor candidate 数量下滑，再按这个顺序回补。
ANCHOR_PROMOTION_PRIORITY = ["564", "570", "677", "714", "509", "569"]

SELECTION_CSV_FIELDS = [
    "task_id",
    "base_task_id",
    "keep",
    "final_role",
    "is_promoted_anchor",
    "is_demoted_anchor_candidate",
    "priority_flag",
    "review_note_flag",
    "default_eligible",
    "scope",
    "difficulty_tags",
    "model_issue_tags",
    "poly_residue_flag",
    "recommended_role",
    "keep_reason",
    "drop_reason",
    "reference_binding_status",
    "adjudication_status",
    "notes",
]


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            rows.append(json.loads(line))
    return rows


def _write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fieldnames})


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _bool_text(value: bool) -> str:
    return "True" if value else "False"


def _is_true(value: Any) -> bool:
    return str(value).strip().lower() == "true"


def _sorted_task_ids(values: set[str] | list[str]) -> list[str]:
    return sorted({str(v) for v in values}, key=lambda item: int(item))


def _tags_from_row(row: dict[str, Any], field: str) -> list[str]:
    value = row.get(field, "")
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    return [part.strip() for part in str(value).split(";") if part.strip()]


def load_inputs(root: Path | None = None) -> tuple[list[dict[str, str]], list[dict[str, Any]]]:
    repo_root = root or _repo_root()
    truth_dir = repo_root / "analysis_results" / TRUTH_LAYER_DIRNAME
    registry_rows = _read_csv(truth_dir / "trap_task_registry_v1.csv")
    annotation_rows = _read_jsonl(truth_dir / "manual_annotation_records_v1.jsonl")
    return registry_rows, annotation_rows


def _pick_demoted_anchor_ids(
    manual_rows: list[dict[str, str]],
    existing_anchor_ids: set[str],
) -> list[str]:
    if len(existing_anchor_ids) <= TARGET_ANCHOR_MAX:
        return []

    row_by_task = {row["task_id"]: row for row in manual_rows}
    demotions: list[str] = []

    for task_id in ANCHOR_DEMOTION_PRIORITY:
        row = row_by_task.get(task_id)
        if row is None or task_id not in existing_anchor_ids:
            continue
        demotions.append(task_id)
        if len(existing_anchor_ids) - len(demotions) <= TARGET_ANCHOR_MAX:
            return demotions

    for row in sorted(manual_rows, key=lambda item: int(item["task_id"])):
        task_id = row["task_id"]
        if task_id not in existing_anchor_ids or task_id in demotions:
            continue
        if row.get("priority_flag") != "special_review":
            continue
        demotions.append(task_id)
        if len(existing_anchor_ids) - len(demotions) <= TARGET_ANCHOR_MAX:
            return demotions

    raise ValueError("Unable to reduce the manual expert-anchor set to the target max")


def _pick_promoted_anchor_ids(
    manual_rows: list[dict[str, str]],
    existing_anchor_ids: set[str],
) -> list[str]:
    if TARGET_ANCHOR_MIN <= len(existing_anchor_ids) <= TARGET_ANCHOR_MAX:
        return []

    row_by_task = {row["task_id"]: row for row in manual_rows}
    promotions: list[str] = []

    for task_id in ANCHOR_PROMOTION_PRIORITY:
        row = row_by_task.get(task_id)
        if row is None or task_id in existing_anchor_ids:
            continue
        if not _is_true(row.get("default_eligible")):
            continue
        if row.get("priority_flag") == "low_priority":
            continue
        promotions.append(task_id)
        if len(existing_anchor_ids) + len(promotions) >= TARGET_ANCHOR_MIN:
            return promotions

    for row in sorted(manual_rows, key=lambda item: int(item["task_id"])):
        task_id = row["task_id"]
        if task_id in existing_anchor_ids or task_id in promotions:
            continue
        if not _is_true(row.get("default_eligible")):
            continue
        if row.get("priority_flag") == "low_priority":
            continue
        promotions.append(task_id)
        if len(existing_anchor_ids) + len(promotions) >= TARGET_ANCHOR_MIN:
            return promotions

    raise ValueError("Unable to reach the minimum manual expert-anchor target from current pool")


def _keep_reason(
    row: dict[str, str],
    final_role: str,
    is_promoted_anchor: bool,
    is_demoted_anchor: bool,
) -> str:
    task_id = row["task_id"]
    recommended_role = row.get("recommended_role", "")
    priority_flag = row.get("priority_flag", "")

    if final_role == "expert_anchor":
        if is_promoted_anchor:
            return (
                "Promoted into the expert-anchor core to satisfy the lower quota bound on the "
                "current working-consensus layer."
            )
        if priority_flag == "special_review":
            return (
                "Retained as an expert anchor. The bracketed comment is treated as a review note "
                "rather than an automatic exclusion, and the sample is still considered stably annotatable."
            )
        return "Retained as a default in-scope expert anchor on the current working-consensus layer."

    if is_demoted_anchor:
        if task_id == "509":
            return (
                "Retained as a non-anchor for quota balancing. This sample remains usable, but its "
                "possible-ambiguity note makes it the safest review-flagged row to move out of the expert-anchor core."
            )
        if task_id == "569":
            return (
                "Retained as a non-anchor for quota balancing. This sample remains usable, but the "
                "one-corner-multiple-points remark makes it a safer non-anchor than expert anchor."
            )
        return "Retained as a non-anchor for quota balancing on the current working-consensus layer."

    if recommended_role == "audit_only":
        return (
            "Retained as a non-anchor only. Current folder-level notes still indicate unstable or "
            "insufficiently reproducible geometry for the expert-anchor core."
        )

    if priority_flag == "low_priority":
        return (
            "Retained as a non-anchor because explicit low-priority samples stay in the manual pool "
            "for coverage and audit, but do not enter the expert-anchor core."
        )

    if priority_flag == "special_review":
        return (
            "Retained as a non-anchor to preserve review-flagged coverage without using it as the "
            "expert-anchor reference core."
        )

    return (
        "Retained as a non-anchor to preserve challenge coverage while keeping the expert-anchor "
        "set conservative on the current working-consensus layer."
    )


def freeze_manual_selection(
    registry_rows: list[dict[str, str]],
    annotation_rows: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], dict[str, Any], dict[str, Any]]:
    manual_rows = [row for row in registry_rows if row.get("bucket_dir") == "manual"]
    if len(manual_rows) != TARGET_TOTAL:
        raise ValueError(f"Expected {TARGET_TOTAL} manual rows, found {len(manual_rows)}")

    manual_records = [row for row in annotation_rows if row.get("bucket_dir") == "manual"]
    if len(manual_records) != TARGET_TOTAL:
        raise ValueError(f"Expected {TARGET_TOTAL} manual annotation rows, found {len(manual_records)}")

    record_by_task = {str(row["task_id"]): row for row in manual_records}
    existing_anchor_ids = {
        row["task_id"]
        for row in manual_rows
        if row.get("recommended_role") == "manual_anchor_candidate"
    }

    if len(existing_anchor_ids) < TARGET_ANCHOR_MIN:
        demoted_anchor_ids: list[str] = []
        promoted_anchor_ids = _pick_promoted_anchor_ids(manual_rows, existing_anchor_ids)
        final_anchor_ids = existing_anchor_ids | set(promoted_anchor_ids)
    elif len(existing_anchor_ids) <= TARGET_ANCHOR_MAX:
        demoted_anchor_ids = []
        promoted_anchor_ids = []
        final_anchor_ids = set(existing_anchor_ids)
    else:
        demoted_anchor_ids = _pick_demoted_anchor_ids(manual_rows, existing_anchor_ids)
        promoted_anchor_ids = []
        final_anchor_ids = existing_anchor_ids - set(demoted_anchor_ids)

    if not (TARGET_ANCHOR_MIN <= len(final_anchor_ids) <= TARGET_ANCHOR_MAX):
        raise ValueError(f"Manual anchor count out of range: {len(final_anchor_ids)}")

    selection_rows: list[dict[str, Any]] = []
    for row in sorted(manual_rows, key=lambda item: int(item["task_id"])):
        task_id = row["task_id"]
        record = record_by_task[task_id]
        final_role = "expert_anchor" if task_id in final_anchor_ids else "non_anchor"
        is_promoted_anchor = task_id in promoted_anchor_ids
        is_demoted_anchor = task_id in demoted_anchor_ids
        selection_rows.append(
            {
                "task_id": task_id,
                "base_task_id": row["base_task_id"],
                "keep": _bool_text(True),
                "final_role": final_role,
                "is_promoted_anchor": _bool_text(is_promoted_anchor),
                "is_demoted_anchor_candidate": _bool_text(is_demoted_anchor),
                "priority_flag": row["priority_flag"],
                "review_note_flag": row["review_note_flag"],
                "default_eligible": row["default_eligible"],
                "scope": row["current_scope_alias"],
                "difficulty_tags": row["difficulty_tags"],
                "model_issue_tags": row["model_issue_tags"],
                "poly_residue_flag": _bool_text(bool(record.get("poly_residue_flag"))),
                "recommended_role": row["recommended_role"],
                "keep_reason": _keep_reason(row, final_role, is_promoted_anchor, is_demoted_anchor),
                "drop_reason": "",
                "reference_binding_status": REFERENCE_BINDING_STATUS,
                "adjudication_status": ADJUDICATION_STATUS,
                "notes": row.get("notes", ""),
            }
        )

    anchor_rows = [row for row in selection_rows if row["final_role"] == "expert_anchor"]
    non_anchor_rows = [row for row in selection_rows if row["final_role"] == "non_anchor"]

    if len(anchor_rows) + len(non_anchor_rows) != TARGET_TOTAL:
        raise AssertionError("Manual selection rows do not partition the full manual pool")
    if len(non_anchor_rows) < TARGET_NON_ANCHOR_MIN or len(non_anchor_rows) > TARGET_NON_ANCHOR_MAX:
        raise ValueError(f"Manual non-anchor count out of range: {len(non_anchor_rows)}")

    semi_base_ids = {
        row["base_task_id"] for row in registry_rows if row.get("bucket_dir") == "semi"
    }
    oos_base_ids = {
        row["base_task_id"] for row in registry_rows if row.get("bucket_dir") == "OOS"
    }
    manual_base_ids = {row["base_task_id"] for row in selection_rows}

    anchor_difficulty_counter: Counter[str] = Counter()
    for row in anchor_rows:
        for tag in _tags_from_row(row, "difficulty_tags"):
            anchor_difficulty_counter[tag] += 1

    selection_summary = {
        "selection_name": "prescreen_manual_final_selection_v1",
        "selection_scope": "stage1_prescreen_manual_pool",
        "truth_layer_dir": TRUTH_LAYER_DIRNAME,
        "reference_binding_status": REFERENCE_BINDING_STATUS,
        "adjudication_status": ADJUDICATION_STATUS,
        "manual_total_pool_count": TARGET_TOTAL,
        "manual_total_selected": len(selection_rows),
        "expert_anchor_target_min": TARGET_ANCHOR_MIN,
        "expert_anchor_target_max": TARGET_ANCHOR_MAX,
        "expert_anchor_count": len(anchor_rows),
        "non_anchor_target_min": TARGET_NON_ANCHOR_MIN,
        "non_anchor_target_max": TARGET_NON_ANCHOR_MAX,
        "non_anchor_count": len(non_anchor_rows),
        "selected_expert_anchor_task_ids": _sorted_task_ids([row["task_id"] for row in anchor_rows]),
        "selected_non_anchor_task_ids": _sorted_task_ids([row["task_id"] for row in non_anchor_rows]),
        "promoted_anchor_task_ids": _sorted_task_ids(promoted_anchor_ids),
        "demoted_anchor_candidate_task_ids": _sorted_task_ids(demoted_anchor_ids),
        "retained_low_priority_non_anchor_task_ids": _sorted_task_ids(
            [row["task_id"] for row in non_anchor_rows if row["priority_flag"] == "low_priority"]
        ),
        "retained_audit_note_non_anchor_task_ids": _sorted_task_ids(
            [row["task_id"] for row in non_anchor_rows if row["recommended_role"] == "audit_only"]
        ),
        "anchor_difficulty_coverage": dict(sorted(anchor_difficulty_counter.items())),
        "selection_frozen": True,
        "manual_binding_ready": False,
        "blocked_reasons": [
            "current reference layer remains working_consensus_not_final_gold rather than final adjudicated gold",
        ],
        "notes": [
            "This file freezes the current manual pool into a thesis-facing anchor/non-anchor split on top of the working-consensus truth layer.",
            "Only explicit low-priority rows are automatically excluded from the expert-anchor core; other review notes are kept unless manually demoted for quota balancing or note-based instability.",
        ],
    }

    audit_payload = {
        "audit_name": "prescreen_manual_binding_audit_v1",
        "truth_layer_dir": TRUTH_LAYER_DIRNAME,
        "reference_binding_status": REFERENCE_BINDING_STATUS,
        "adjudication_status": ADJUDICATION_STATUS,
        "manual_total_pool_count": TARGET_TOTAL,
        "manual_total_selected": len(selection_rows),
        "expert_anchor_count": len(anchor_rows),
        "non_anchor_count": len(non_anchor_rows),
        "promoted_anchor_count": len(promoted_anchor_ids),
        "promoted_anchor_task_ids": _sorted_task_ids(promoted_anchor_ids),
        "demoted_anchor_candidate_count": len(demoted_anchor_ids),
        "demoted_anchor_candidate_task_ids": _sorted_task_ids(demoted_anchor_ids),
        "low_priority_selected_count": sum(1 for row in selection_rows if row["priority_flag"] == "low_priority"),
        "special_review_selected_count": sum(
            1 for row in selection_rows if row["priority_flag"] == "special_review"
        ),
        "review_note_selected_count": sum(
            1 for row in selection_rows if row["review_note_flag"] == "True"
        ),
        "anchor_with_review_note_count": sum(
            1 for row in anchor_rows if row["review_note_flag"] == "True"
        ),
        "selected_with_poly_residue_count": sum(
            1 for row in selection_rows if row["poly_residue_flag"] == "True"
        ),
        "selected_anchor_with_poly_residue_count": sum(
            1 for row in anchor_rows if row["poly_residue_flag"] == "True"
        ),
        "manual_vs_semi_base_task_overlap_count": len(manual_base_ids & semi_base_ids),
        "manual_vs_oos_base_task_overlap_count": len(manual_base_ids & oos_base_ids),
        "manual_selection_frozen": True,
        "anchor_target_met": TARGET_ANCHOR_MIN <= len(anchor_rows) <= TARGET_ANCHOR_MAX,
        "non_anchor_target_met": TARGET_NON_ANCHOR_MIN <= len(non_anchor_rows) <= TARGET_NON_ANCHOR_MAX,
        "manual_binding_ready": False,
        "blocked_reasons": [
            "reference layer remains working_consensus_not_final_gold, so thesis-grade final binding is not yet complete",
        ],
        "notes": [
            "Selection is complete on the current working-consensus layer.",
            "Binding remains below thesis-grade final gold because the reference layer is not yet adjudicated as final gold.",
        ],
    }

    return selection_rows, selection_summary, audit_payload


def run(output_dir: Path | None = None, root: Path | None = None) -> dict[str, Path]:
    repo_root = root or _repo_root()
    if output_dir is None:
        output_dir = repo_root / "analysis_results" / OUTPUT_DIRNAME

    registry_rows, annotation_rows = load_inputs(repo_root)
    selection_rows, selection_summary, audit_payload = freeze_manual_selection(
        registry_rows,
        annotation_rows,
    )

    selection_json_path = output_dir / "prescreen_manual_final_selection_v1.json"
    selection_csv_path = output_dir / "prescreen_manual_final_selection_v1.csv"
    binding_audit_path = output_dir / "prescreen_manual_binding_audit_v1.json"

    _write_json(selection_json_path, selection_summary)
    _write_csv(selection_csv_path, selection_rows, SELECTION_CSV_FIELDS)
    _write_json(binding_audit_path, audit_payload)

    return {
        "selection_json": selection_json_path,
        "selection_csv": selection_csv_path,
        "binding_audit": binding_audit_path,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Freeze PreScreen manual final selection.")
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=None,
        help="Optional output directory override.",
    )
    args = parser.parse_args()
    outputs = run(output_dir=args.output_dir)
    print(json.dumps({key: str(value) for key, value in outputs.items()}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
