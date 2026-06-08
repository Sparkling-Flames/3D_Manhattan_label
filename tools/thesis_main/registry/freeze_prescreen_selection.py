from __future__ import annotations

import argparse
import csv
import json
from collections import Counter
from pathlib import Path
from typing import Any


def read_csv_rows(csv_path: Path) -> list[dict[str, Any]]:
    with csv_path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _as_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return False
    return str(value).strip().lower() == "true"


def _phase1_item_by_id(phase1_manifest: dict[str, Any], item_id: str) -> dict[str, Any]:
    for item in phase1_manifest.get("items", []):
        if item.get("item_id") == item_id:
            return item
    raise KeyError(f"Missing phase1 item: {item_id}")


def build_prescreen_manual_final_selection(
    *,
    manual_inventory_rows: list[dict[str, Any]],
    phase1_manifest: dict[str, Any],
) -> dict[str, Any]:
    manual_anchor_item = _phase1_item_by_id(phase1_manifest, "stage1_prescreen_manual_expert_anchor")
    core_rows = [row for row in manual_inventory_rows if _as_bool(row.get("joinable_for_prescreen_anchor_counting"))]
    supplement_rows = [row for row in manual_inventory_rows if not _as_bool(row.get("joinable_for_prescreen_anchor_counting"))]

    target_min = int(manual_anchor_item["thesis_target"]["min"])
    target_max = int(manual_anchor_item["thesis_target"]["max"])
    current_known_anchor_candidate_count = len(core_rows) + len(supplement_rows)

    return {
        "selection_name": "prescreen_manual_final_selection_v1",
        "selection_scope": "stage1_prescreen_manual_expert_anchor",
        "target_anchor_min": target_min,
        "target_anchor_max": target_max,
        "current_core_selected_anchor_ids": [row["anchor_task_id"] for row in core_rows if row.get("anchor_task_id")],
        "current_core_selected_base_task_ids": [row["base_task_id"] for row in core_rows],
        "current_supplement_candidate_base_task_ids": [row["base_task_id"] for row in supplement_rows],
        "current_joinable_anchor_count": len(core_rows),
        "current_known_anchor_candidate_count": current_known_anchor_candidate_count,
        "max_possible_anchor_count_from_current_known_pool": current_known_anchor_candidate_count,
        "anchor_gap_to_target_min": max(target_min - current_known_anchor_candidate_count, 0),
        "anchor_gap_to_target_max": max(target_max - current_known_anchor_candidate_count, 0),
        "selection_ready": False,
        "blocked_reasons": [
            f"current known manual anchor pool supports at most {current_known_anchor_candidate_count} rows, still below thesis target {target_min}-{target_max}",
            "supplement candidates are collected but not yet joinable in the current Stage 1 registry",
            "manual expert annotation remains in progress, so a thesis-facing final expert-anchor set cannot yet be frozen",
        ],
        "notes": [
            "This artifact freezes the current selection boundary. It does not claim that the thesis-facing manual expert-anchor set is already complete.",
            "The current core 12 anchors remain the only joinable expert anchors in the repository.",
        ],
    }


def build_prescreen_manual_non_anchor_selection(
    *,
    task_registry_rows: list[dict[str, Any]],
    phase1_manifest: dict[str, Any],
) -> dict[str, Any]:
    non_anchor_item = _phase1_item_by_id(phase1_manifest, "stage1_prescreen_manual_non_anchor")
    target_min = int(non_anchor_item["thesis_target"]["min"])
    target_max = int(non_anchor_item["thesis_target"]["max"])

    candidate_rows = [
        row
        for row in task_registry_rows
        if row.get("planned_stage") == "prescreen_manual" and not _as_bool(row.get("has_expert_ref"))
    ]

    return {
        "selection_name": "prescreen_manual_non_anchor_selection_v1",
        "selection_scope": "stage1_prescreen_manual_non_anchor",
        "target_non_anchor_min": target_min,
        "target_non_anchor_max": target_max,
        "current_candidate_registry_uids": [row.get("registry_uid", "") for row in candidate_rows],
        "current_candidate_base_task_ids": [row.get("base_task_id", "") for row in candidate_rows],
        "current_candidate_count": len(candidate_rows),
        "selected_non_anchor_registry_uids": [],
        "selection_ready": False,
        "blocked_reasons": [
            f"current PreScreen manual non-anchor candidate count is {len(candidate_rows)}, above thesis target {target_min}-{target_max}",
            "no thesis-facing keep/drop freeze exists yet for the current non-anchor candidate set",
        ],
        "notes": [
            "This artifact freezes the current non-anchor candidate pool only.",
            "A future thesis-facing non-anchor selection must reduce the current candidate set to the 8-10 target range.",
        ],
    }


def build_prescreen_semi_final_selection(semi_selection_freeze: dict[str, Any]) -> dict[str, Any]:
    selected_control_rows = semi_selection_freeze.get("selected_control_rows", [])
    current_control_candidate_rows = semi_selection_freeze.get("current_control_candidate_rows", [])
    selected_trap_rows = semi_selection_freeze.get("selected_trap_rows", [])
    control_target = int(semi_selection_freeze.get("control_target", 0))
    trap_target = int(semi_selection_freeze.get("misleading_trap_target", 0))
    trap_gap = max(trap_target - len(selected_trap_rows), 0)

    blocked_reasons = [
        f"current selected control rows = {len(selected_control_rows)} while thesis-facing control target = {control_target}",
        f"current selected realized trap rows = {len(selected_trap_rows)} while thesis-facing trap target = {trap_target}",
        "current control candidates remain candidate-only and are not bound to a thesis-facing Stage 1 control subset",
    ]
    blocked_reasons.extend(semi_selection_freeze.get("blocked_reasons", []))

    return {
        "selection_name": "prescreen_semi_final_selection_v1",
        "selection_scope": "stage1_prescreen_semi",
        "target_total": int(semi_selection_freeze.get("target_total", 0)),
        "control_target": control_target,
        "trap_target": trap_target,
        "selected_control_rows": selected_control_rows,
        "current_control_candidate_rows": current_control_candidate_rows,
        "selected_trap_rows": selected_trap_rows,
        "current_selected_control_count": len(selected_control_rows),
        "current_selected_trap_count": len(selected_trap_rows),
        "control_gap": int(semi_selection_freeze.get("control_gap", 0)),
        "trap_gap": trap_gap,
        "family_allocations": semi_selection_freeze.get("family_allocations", []),
        "open_subedges": semi_selection_freeze.get("open_subedges", []),
        "selection_ready": False,
        "blocked_reasons": blocked_reasons,
        "notes": [
            "This artifact freezes the current thesis-facing selection boundary for PreScreen_semi.",
            "It does not promote the current bundle candidates to a completed final Stage 1 semi pool.",
        ],
    }


def build_oos_gate_target_freeze_v2(
    *,
    oos_gate_pool_freeze: dict[str, Any],
    natural_failure_bank_rows: list[dict[str, Any]],
) -> dict[str, Any]:
    oos_rows = [row for row in natural_failure_bank_rows if row.get("recommended_role") == "oos_gate"]
    preferred_stage_counts = dict(Counter(row.get("task_registry_planned_stages", "") for row in oos_rows))
    dedicated_stage1_registry_bound_candidate_count = sum(
        1 for row in oos_rows if str(row.get("preferred_registry_uid", "")).startswith("stage1_")
    )

    blocked_reasons = [
        "stage1 OOS target quota remains undeclared in current repository artifacts",
        f"dedicated Stage 1 registry bound OOS candidate count is {dedicated_stage1_registry_bound_candidate_count}",
        "current OOS candidate bank still maps to non-Stage1 preferred registry contexts",
    ]
    blocked_reasons.extend(oos_gate_pool_freeze.get("blocked_reasons", []))

    return {
        "freeze_name": "oos_gate_target_freeze_v2",
        "target_role": oos_gate_pool_freeze.get("target_role", ""),
        "target_quota": None,
        "target_quota_declared": False,
        "current_candidate_ids": oos_gate_pool_freeze.get("current_candidate_ids", []),
        "candidate_bank_ids": oos_gate_pool_freeze.get("candidate_bank_ids", []),
        "oos_family_counts": oos_gate_pool_freeze.get("oos_family_counts", {}),
        "preferred_registry_stage_counts": preferred_stage_counts,
        "dedicated_stage1_registry_bound_candidate_count": dedicated_stage1_registry_bound_candidate_count,
        "manual_anchor_overlap_count": oos_gate_pool_freeze.get("manual_anchor_overlap_count", 0),
        "semi_pool_overlap_count": oos_gate_pool_freeze.get("semi_pool_overlap_count", 0),
        "target_freeze_ready": False,
        "blocked_reasons": blocked_reasons,
        "notes": [
            "current_candidate_ids remain candidate-bank identifiers only; they do not imply that a final Stage 1 OOS quota already exists.",
            "This artifact is a target-freeze attempt that remains blocked until quota and dedicated Stage 1 binding are declared.",
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Freeze current blocked selection state for PreScreen manual/semi/OOS pools.")
    parser.add_argument("--phase1-manifest", default="analysis_results/phase1_progress_20260311/phase1_target_vs_realized_manifest_v1.json")
    parser.add_argument("--manual-inventory", default="analysis_results/phase1_progress_20260311/prescreen_manual_anchor_inventory_v1.csv")
    parser.add_argument("--task-registry", default="analysis_results/registry_20260308/task_registry_v2.csv")
    parser.add_argument("--semi-selection-freeze", default="analysis_results/c_manifests_20260311/prescreen_semi_selection_freeze_v1.json")
    parser.add_argument("--oos-gate-pool-freeze", default="analysis_results/phase1_progress_20260311/oos_gate_pool_freeze_v1.json")
    parser.add_argument("--natural-failure-bank", default="analysis_results/c_manifests_20260310/natural_failure_bank_index_v1.csv")
    parser.add_argument("--phase1-output-dir", default="analysis_results/phase1_progress_20260311")
    parser.add_argument("--c-output-dir", default="analysis_results/c_manifests_20260311")
    args = parser.parse_args()

    root = Path(__file__).resolve().parents[3]
    phase1_manifest = _load_json(root / args.phase1_manifest)
    manual_inventory_rows = read_csv_rows(root / args.manual_inventory)
    task_registry_rows = read_csv_rows(root / args.task_registry)
    semi_selection_freeze = _load_json(root / args.semi_selection_freeze)
    oos_gate_pool_freeze = _load_json(root / args.oos_gate_pool_freeze)
    natural_failure_bank_rows = read_csv_rows(root / args.natural_failure_bank)

    phase1_output_dir = root / args.phase1_output_dir
    c_output_dir = root / args.c_output_dir
    phase1_output_dir.mkdir(parents=True, exist_ok=True)
    c_output_dir.mkdir(parents=True, exist_ok=True)

    manual_final_selection = build_prescreen_manual_final_selection(
        manual_inventory_rows=manual_inventory_rows,
        phase1_manifest=phase1_manifest,
    )
    (phase1_output_dir / "prescreen_manual_final_selection_v1.json").write_text(
        json.dumps(manual_final_selection, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    manual_non_anchor_selection = build_prescreen_manual_non_anchor_selection(
        task_registry_rows=task_registry_rows,
        phase1_manifest=phase1_manifest,
    )
    (phase1_output_dir / "prescreen_manual_non_anchor_selection_v1.json").write_text(
        json.dumps(manual_non_anchor_selection, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    semi_final_selection = build_prescreen_semi_final_selection(semi_selection_freeze)
    (c_output_dir / "prescreen_semi_final_selection_v1.json").write_text(
        json.dumps(semi_final_selection, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    oos_target_freeze_v2 = build_oos_gate_target_freeze_v2(
        oos_gate_pool_freeze=oos_gate_pool_freeze,
        natural_failure_bank_rows=natural_failure_bank_rows,
    )
    (phase1_output_dir / "oos_gate_target_freeze_v2.json").write_text(
        json.dumps(oos_target_freeze_v2, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
