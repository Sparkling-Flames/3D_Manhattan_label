from __future__ import annotations

import argparse
import csv
import json
from collections import Counter
from pathlib import Path
from typing import Any


MANUAL_ANCHOR_INVENTORY_FIELDNAMES = [
    "anchor_task_id",
    "base_task_id",
    "source_pool",
    "dataset_group",
    "planned_stage",
    "has_expert_ref",
    "init_type",
    "registry_uids",
    "registry_row_count",
    "joinable_for_prescreen_anchor_counting",
    "range_collected_status",
    "expert_annotation_status",
    "status_field_source",
    "notes",
]

CURRENT_MANUAL_RANGE_COLLECTED_STATUS = "collected"
CURRENT_MANUAL_EXPERT_ANNOTATION_STATUS = "in_progress"
CURRENT_MANUAL_STATUS_FIELD_SOURCE = "current_status_annotation"


def read_csv_rows(csv_path: Path) -> list[dict[str, Any]]:
    with csv_path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def write_csv(csv_path: Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> None:
    with csv_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        if rows:
            writer.writerows(rows)


def _as_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return False
    return str(value).strip().lower() == "true"


def _as_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _extract_anchor_registry_uid(registry_uids: str) -> str:
    if not registry_uids:
        return ""
    for item in str(registry_uids).split(";"):
        item = item.strip()
        if item.startswith("stage1_prescreen_manual_anchor:"):
            return item
    return ""


def _phase1_item_by_id(phase1_manifest: dict[str, Any], item_id: str) -> dict[str, Any]:
    for item in phase1_manifest.get("items", []):
        if item.get("item_id") == item_id:
            return item
    raise KeyError(f"Missing phase1 item: {item_id}")


def build_prescreen_manual_anchor_inventory(manual_anchor_bank_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    inventory_rows: list[dict[str, Any]] = []
    for row in manual_anchor_bank_rows:
        if row.get("planned_stage") != "prescreen_manual":
            continue
        if not _as_bool(row.get("has_expert_ref")):
            continue

        anchor_registry_uid = _extract_anchor_registry_uid(str(row.get("registry_uids", "")))
        joinable = bool(anchor_registry_uid) and _as_int(row.get("registry_row_count")) > 0
        notes = (
            "Current joinable PreScreen expert anchor row."
            if joinable
            else "Collected manual-bank supplement candidate; not yet joinable in the current PreScreen anchor registry."
        )
        inventory_rows.append(
            {
                "anchor_task_id": anchor_registry_uid,
                "base_task_id": row.get("base_task_id", ""),
                "source_pool": row.get("source_pools", ""),
                "dataset_group": row.get("dataset_group", ""),
                "planned_stage": row.get("planned_stage", ""),
                "has_expert_ref": _as_bool(row.get("has_expert_ref")),
                "init_type": row.get("init_type", ""),
                "registry_uids": row.get("registry_uids", ""),
                "registry_row_count": _as_int(row.get("registry_row_count")),
                "joinable_for_prescreen_anchor_counting": joinable,
                "range_collected_status": CURRENT_MANUAL_RANGE_COLLECTED_STATUS,
                "expert_annotation_status": CURRENT_MANUAL_EXPERT_ANNOTATION_STATUS,
                "status_field_source": CURRENT_MANUAL_STATUS_FIELD_SOURCE,
                "notes": notes,
            }
        )
    return inventory_rows


def build_prescreen_semi_selection_freeze(
    *,
    materialized_rows: list[dict[str, Any]],
    natural_failure_bank_rows: list[dict[str, Any]],
    prescreen_semi_family_target: dict[str, Any],
    current_bundle_gap: dict[str, Any],
) -> dict[str, Any]:
    default_target_families = prescreen_semi_family_target["misleading_trap_target"]["default_target_families"]
    selected_trap_rows = []
    for row in materialized_rows:
        if row.get("operator_id") not in default_target_families:
            continue
        if row.get("materialization_status") != "realized":
            continue
        selected_trap_rows.append(
            {
                "manifest_row_id": row.get("manifest_row_id", ""),
                "target_registry_uid": row.get("target_registry_uid", ""),
                "base_task_id": row.get("base_task_id", ""),
                "family": row.get("operator_id", ""),
                "source_type": row.get("source_type", ""),
                "materialization_status": row.get("materialization_status", ""),
                "selection_status": "current_bundle_realized_candidate",
            }
        )

    current_control_candidate_rows = []
    for row in natural_failure_bank_rows:
        if row.get("recommended_role") != "main_trap":
            continue
        if row.get("primary_issue_family") != "acceptable":
            continue
        current_control_candidate_rows.append(
            {
                "bank_id": row.get("bank_id", ""),
                "task_id": row.get("task_id", ""),
                "base_task_id": row.get("base_task_id", ""),
                "preferred_registry_uid": row.get("preferred_registry_uid", ""),
                "selection_status": "candidate_only_not_frozen_for_prescreen_semi",
            }
        )

    selected_control_rows: list[dict[str, Any]] = []
    target_allocations = {
        row["family"]: row for row in prescreen_semi_family_target.get("family_target_allocations", [])
    }
    family_allocations = []
    selected_trap_count_by_family = Counter(row["family"] for row in selected_trap_rows)
    for family, allocation in target_allocations.items():
        current_bundle_rows_for_family = [row for row in materialized_rows if row.get("operator_id") == family]
        family_allocations.append(
            {
                "family": family,
                "target_count": _as_int(allocation.get("target_count")),
                "target_role": allocation.get("target_role", ""),
                "current_bundle_row_count": len(current_bundle_rows_for_family),
                "current_bundle_realized_count": sum(
                    1 for row in current_bundle_rows_for_family if row.get("materialization_status") == "realized"
                ),
                "current_bundle_reject_count": sum(
                    1 for row in current_bundle_rows_for_family if row.get("materialization_status") == "reject"
                ),
                "current_selected_count": (
                    len(selected_control_rows)
                    if family == "acceptable"
                    else selected_trap_count_by_family.get(family, 0)
                ),
                "current_candidate_bank_count": (
                    len(current_control_candidate_rows)
                    if family == "acceptable"
                    else 0
                ),
            }
        )

    control_target = _as_int(prescreen_semi_family_target["normal_control_target"]["target_count"])
    misleading_trap_target = _as_int(prescreen_semi_family_target["misleading_trap_target"]["target_count"])
    control_gap = control_target - len(selected_control_rows)
    blocked_reasons = [
        "current C materialization bundle does not by itself freeze the thesis-facing PreScreen_semi pool",
        "acceptable control subset is still unfrozen in the current bundle and current selected control rows remain zero",
        f"current default misleading-trap realized selection count is {len(selected_trap_rows)} while the target is {misleading_trap_target}",
    ]
    blocked_reasons.extend(current_bundle_gap.get("blocked_reasons", []))

    return {
        "freeze_name": "prescreen_semi_selection_freeze_v1",
        "target_total": _as_int(prescreen_semi_family_target.get("target_total_tasks")),
        "control_target": control_target,
        "misleading_trap_target": misleading_trap_target,
        "current_bundle_rows": len(materialized_rows),
        "current_realized_rows": sum(1 for row in materialized_rows if row.get("materialization_status") == "realized"),
        "current_reject_rows": sum(1 for row in materialized_rows if row.get("materialization_status") == "reject"),
        "selected_control_rows": selected_control_rows,
        "selected_trap_rows": selected_trap_rows,
        "current_control_candidate_rows": current_control_candidate_rows,
        "family_allocations": family_allocations,
        "open_subedges": current_bundle_gap.get("open_subedges", []),
        "control_gap": control_gap,
        "selection_ready": False,
        "blocked_reasons": blocked_reasons,
        "notes": [
            "This artifact freezes current readiness state and blocker structure. It does not promote the current C bundle to a thesis-facing PreScreen_semi final pool.",
            "Current control candidates come from the reviewed natural-failure bank and remain candidate-only in this freeze artifact.",
        ],
    }


def build_oos_gate_pool_freeze(
    *,
    natural_failure_bank_rows: list[dict[str, Any]],
    task_registry_rows: list[dict[str, Any]],
) -> dict[str, Any]:
    oos_rows = [row for row in natural_failure_bank_rows if row.get("recommended_role") == "oos_gate"]
    current_candidate_ids = [str(row.get("task_id", "")) for row in oos_rows]
    oos_family_counts = dict(Counter(row.get("primary_issue_family", "") for row in oos_rows))

    manual_anchor_base_ids = {
        row.get("base_task_id", "")
        for row in task_registry_rows
        if row.get("planned_stage") == "prescreen_manual" and _as_bool(row.get("has_expert_ref"))
    }
    semi_pool_base_ids = {
        row.get("base_task_id", "")
        for row in task_registry_rows
        if row.get("planned_stage") == "prescreen_semi"
    }
    oos_base_ids = {row.get("base_task_id", "") for row in oos_rows}

    manual_anchor_overlap_count = len(oos_base_ids & manual_anchor_base_ids)
    semi_pool_overlap_count = len(oos_base_ids & semi_pool_base_ids)

    blocked_reasons = [
        "current repository artifacts do not declare a frozen Stage 1 OOS target quota",
        "current OOS rows remain a candidate bank rather than a final frozen PreScreen OOS pool",
    ]
    if any(not row.get("preferred_registry_uid") for row in oos_rows):
        blocked_reasons.append("some OOS candidate rows are not bound to a dedicated Stage 1 registry uid in current artifacts")

    return {
        "freeze_name": "oos_gate_pool_freeze_v1",
        "target_role": "candidate_bank_for_scope_gate_not_geometry_gt",
        "candidate_pool_exists": bool(oos_rows),
        "target_quota_declared": False,
        "current_candidate_ids": current_candidate_ids,
        "candidate_bank_ids": [row.get("bank_id", "") for row in oos_rows],
        "oos_family_counts": oos_family_counts,
        "manual_anchor_overlap_count": manual_anchor_overlap_count,
        "semi_pool_overlap_count": semi_pool_overlap_count,
        "scoring_mode": "scope_gate_scored_separately_from_geometry_gt",
        "ready_for_prescreen": False,
        "blocked_reasons": blocked_reasons,
        "notes": [
            "current_candidate_ids list current candidate rows only; they do not imply a final frozen OOS quota.",
            "This artifact treats the OOS layer as a candidate bank for scope/gate evaluation, not as geometry ground truth.",
        ],
    }


def build_prescreen_readiness_audit(
    *,
    phase1_manifest: dict[str, Any],
    manual_inventory_rows: list[dict[str, Any]],
    semi_selection_freeze: dict[str, Any],
    oos_gate_pool_freeze: dict[str, Any],
) -> dict[str, Any]:
    manual_anchor_item = _phase1_item_by_id(phase1_manifest, "stage1_prescreen_manual_expert_anchor")
    manual_non_anchor_item = _phase1_item_by_id(phase1_manifest, "stage1_prescreen_manual_non_anchor")
    semi_total_item = _phase1_item_by_id(phase1_manifest, "stage1_prescreen_semi_total")

    manual_anchor_current_joinable_count = sum(
        1 for row in manual_inventory_rows if _as_bool(row.get("joinable_for_prescreen_anchor_counting"))
    )
    manual_anchor_target_min = _as_int(manual_anchor_item["thesis_target"]["min"])
    manual_anchor_target_max = _as_int(manual_anchor_item["thesis_target"]["max"])
    manual_anchor_ready = False
    manual_blocked_reasons = [
        f"current joinable PreScreen expert anchors = {manual_anchor_current_joinable_count}, below thesis target {manual_anchor_target_min}-{manual_anchor_target_max}",
        "manual anchor range is collected, but expert annotation remains in progress",
    ]

    manual_non_anchor_target_min = _as_int(manual_non_anchor_item["thesis_target"]["min"])
    manual_non_anchor_target_max = _as_int(manual_non_anchor_item["thesis_target"]["max"])
    manual_non_anchor_current_count = _as_int(manual_non_anchor_item["current_repo"]["derived_from_split_report"])
    manual_non_anchor_ready = manual_non_anchor_target_min <= manual_non_anchor_current_count <= manual_non_anchor_target_max

    semi_target_total = _as_int(semi_total_item["thesis_target"]["value"])
    semi_control_target = _as_int(semi_selection_freeze["control_target"])
    semi_trap_target = _as_int(semi_selection_freeze["misleading_trap_target"])
    semi_selection_ready = _as_bool(semi_selection_freeze["selection_ready"])
    oos_gate_ready = _as_bool(oos_gate_pool_freeze["ready_for_prescreen"])

    blocked_reasons = []
    blocked_reasons.extend(manual_blocked_reasons)
    if not manual_non_anchor_ready:
        blocked_reasons.append(
            f"current PreScreen manual non-anchor count = {manual_non_anchor_current_count}, outside thesis target {manual_non_anchor_target_min}-{manual_non_anchor_target_max}"
        )
    blocked_reasons.extend(semi_selection_freeze.get("blocked_reasons", []))
    blocked_reasons.extend(oos_gate_pool_freeze.get("blocked_reasons", []))

    return {
        "audit_name": "prescreen_readiness_audit_v1",
        "manual_anchor_target_min": manual_anchor_target_min,
        "manual_anchor_target_max": manual_anchor_target_max,
        "manual_anchor_current_joinable_count": manual_anchor_current_joinable_count,
        "manual_anchor_scope": "current joinable PreScreen expert anchors only",
        "manual_anchor_range_collected": True,
        "manual_anchor_expert_annotation_status": "range_collected_annotation_in_progress",
        "manual_anchor_status_field_source": CURRENT_MANUAL_STATUS_FIELD_SOURCE,
        "manual_anchor_ready": manual_anchor_ready,
        "manual_blocked_reasons": manual_blocked_reasons,
        "manual_non_anchor_target_min": manual_non_anchor_target_min,
        "manual_non_anchor_target_max": manual_non_anchor_target_max,
        "manual_non_anchor_current_count": manual_non_anchor_current_count,
        "manual_non_anchor_ready": manual_non_anchor_ready,
        "semi_target_total": semi_target_total,
        "semi_control_target": semi_control_target,
        "semi_trap_target": semi_trap_target,
        "semi_current_bundle_rows": _as_int(semi_selection_freeze["current_bundle_rows"]),
        "semi_current_realized_rows": _as_int(semi_selection_freeze["current_realized_rows"]),
        "semi_selection_ready": semi_selection_ready,
        "semi_blocked_reasons": semi_selection_freeze.get("blocked_reasons", []),
        "oos_gate_candidate_count": len(oos_gate_pool_freeze.get("current_candidate_ids", [])),
        "oos_gate_target_declared": _as_bool(oos_gate_pool_freeze["target_quota_declared"]),
        "oos_gate_ready": oos_gate_ready,
        "oos_gate_blocked_reasons": oos_gate_pool_freeze.get("blocked_reasons", []),
        "prescreen_overall_ready": False,
        "blocked_reasons": blocked_reasons,
        "notes": [
            "This readiness audit freezes current blocked reasons and current joinable assets. It does not claim PreScreen completion.",
            "manual_anchor_range_collected and manual_anchor_expert_annotation_status are current status annotation fields, not export/registry auto-derived fields.",
        ],
    }


def build_prescreen_freeze_note(
    *,
    readiness_audit: dict[str, Any],
    semi_selection_freeze: dict[str, Any],
    oos_gate_pool_freeze: dict[str, Any],
) -> str:
    lines = [
        "# PreScreen Freeze Note v1",
        "",
        "This document records a readiness audit and freeze boundary, not a readiness completion claim.",
        "",
        "## 1. Why this is a readiness freeze rather than a completion package",
        "",
        "- The current repository can already show which Manual, Semi, and OOS assets exist and which blockers remain.",
        "- The current repository cannot yet support a thesis-facing claim that Stage 1 is aligned or formally ready to launch admission.",
        "",
        "## 2. Export evidence tiers",
        "",
        "- Legacy `export_label` files remain pilot or compatibility inputs. They are not formal thesis input.",
        "- The 2026-03-07 single-image exports are closer to the forward-compatible schema because dry-run inspection showed the new `task.data` fields that match the current design more closely.",
        "- Even so, the 2026-03-07 exports still remain pipeline-validation inputs rather than formal thesis input.",
        "- Role interpretation for the 2026-03-07 exports should follow dry-run field inspection and export inventory evidence tiers such as `source_epoch`, `run_class`, `formal_relevance`, and `recommended_use`, not export-inventory `runtime_conditions`.",
        "",
        "## 3. Current pool status",
        "",
        f"- Manual: range is collected, expert annotation is in progress, and current joinable expert-anchor count is {readiness_audit['manual_anchor_current_joinable_count']} against the thesis target {readiness_audit['manual_anchor_target_min']}-{readiness_audit['manual_anchor_target_max']}.",
        f"- Semi: current C materialization bundle has {semi_selection_freeze['current_bundle_rows']} rows with {semi_selection_freeze['current_realized_rows']} realized and {semi_selection_freeze['current_reject_rows']} reject rows. Control gap remains {semi_selection_freeze['control_gap']}.",
        "- Semi: the open `underextend + medium + 4-corner + transform_degenerate` subedge remains unresolved.",
        f"- OOS: candidate bank exists with {len(oos_gate_pool_freeze['current_candidate_ids'])} current candidate rows, but no frozen Stage 1 quota is declared.",
        "",
        "## 4. What this freeze can and cannot claim",
        "",
        "- Can write: PreScreen Manual, Semi, and OOS readiness has been frozen into machine-readable audit artifacts.",
        "- Can write: the artifacts show which assets already exist and which blockers still prevent formal Stage 1 launch.",
        "- Cannot write: `PreScreen complete`.",
        "- Cannot write: `manual anchor ready`.",
        "- Cannot write: `semi selection ready`.",
        "- Cannot write: `OOS gate finalized`.",
        "- Cannot write: `Stage 1 aligned`.",
        "- Cannot write: `admission ready` or `w_max ready to lock`.",
        "",
        "PreScreen readiness is now auditable, but formal Stage 1 launch remains blocked.",
    ]
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description="Freeze PreScreen readiness status into auditable artifacts.")
    parser.add_argument("--phase1-manifest", default="analysis_results/phase1_progress_20260311/phase1_target_vs_realized_manifest_v1.json")
    parser.add_argument("--manual-anchor-bank", default="analysis_results/c_manifests_20260310/manual_anchor_bank_index_v1.csv")
    parser.add_argument("--natural-failure-bank", default="analysis_results/c_manifests_20260310/natural_failure_bank_index_v1.csv")
    parser.add_argument("--task-registry", default="analysis_results/registry_20260308/task_registry_v2.csv")
    parser.add_argument("--materialized-bundle", default="analysis_results/c_manifests_20260311/trap_manifest_materialized_v2.csv")
    parser.add_argument("--semi-target", default="analysis_results/c_manifests_20260311/prescreen_semi_family_target_v1.json")
    parser.add_argument("--bundle-gap", default="analysis_results/c_manifests_20260311/current_bundle_vs_prescreen_target_gap_v1.json")
    parser.add_argument("--phase1-output-dir", default="analysis_results/phase1_progress_20260311")
    parser.add_argument("--c-output-dir", default="analysis_results/c_manifests_20260311")
    args = parser.parse_args()

    root = Path(__file__).resolve().parents[1]
    phase1_manifest = _load_json(root / args.phase1_manifest)
    manual_anchor_bank_rows = read_csv_rows(root / args.manual_anchor_bank)
    natural_failure_bank_rows = read_csv_rows(root / args.natural_failure_bank)
    task_registry_rows = read_csv_rows(root / args.task_registry)
    materialized_rows = read_csv_rows(root / args.materialized_bundle)
    prescreen_semi_family_target = _load_json(root / args.semi_target)
    current_bundle_gap = _load_json(root / args.bundle_gap)

    phase1_output_dir = root / args.phase1_output_dir
    c_output_dir = root / args.c_output_dir
    docs_dir = root / "docs"
    phase1_output_dir.mkdir(parents=True, exist_ok=True)
    c_output_dir.mkdir(parents=True, exist_ok=True)

    manual_inventory_rows = build_prescreen_manual_anchor_inventory(manual_anchor_bank_rows)
    write_csv(
        phase1_output_dir / "prescreen_manual_anchor_inventory_v1.csv",
        manual_inventory_rows,
        MANUAL_ANCHOR_INVENTORY_FIELDNAMES,
    )

    semi_selection_freeze = build_prescreen_semi_selection_freeze(
        materialized_rows=materialized_rows,
        natural_failure_bank_rows=natural_failure_bank_rows,
        prescreen_semi_family_target=prescreen_semi_family_target,
        current_bundle_gap=current_bundle_gap,
    )
    (c_output_dir / "prescreen_semi_selection_freeze_v1.json").write_text(
        json.dumps(semi_selection_freeze, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    oos_gate_pool_freeze = build_oos_gate_pool_freeze(
        natural_failure_bank_rows=natural_failure_bank_rows,
        task_registry_rows=task_registry_rows,
    )
    (phase1_output_dir / "oos_gate_pool_freeze_v1.json").write_text(
        json.dumps(oos_gate_pool_freeze, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    readiness_audit = build_prescreen_readiness_audit(
        phase1_manifest=phase1_manifest,
        manual_inventory_rows=manual_inventory_rows,
        semi_selection_freeze=semi_selection_freeze,
        oos_gate_pool_freeze=oos_gate_pool_freeze,
    )
    (phase1_output_dir / "prescreen_readiness_audit_v1.json").write_text(
        json.dumps(readiness_audit, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    freeze_note = build_prescreen_freeze_note(
        readiness_audit=readiness_audit,
        semi_selection_freeze=semi_selection_freeze,
        oos_gate_pool_freeze=oos_gate_pool_freeze,
    )
    (docs_dir / "prescreen_freeze_note_v1.md").write_text(freeze_note, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
