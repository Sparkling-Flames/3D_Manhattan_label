from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any


TRUTH_LAYER_DIRNAME = "truth_layer_extraction_20260324"
TRAP_COLLECTION_DIRNAME = "trap_collection_freeze_20260320"
PHASE1_DIRNAME = "phase1_progress_20260324"

REFERENCE_BINDING_STATUS = "working_consensus_reference_bound_not_final_gold"
ADJUDICATION_STATUS = "working_consensus_not_final_gold"
BINDING_BLOCKER = (
    "current reference layer remains working_consensus_not_final_gold rather "
    "than final adjudicated gold"
)

CORE_FAMILY_BY_DIR = {
    "跨门扩张": "overextend_adjacent",
    "过度解析": "over_parsing",
    "角点错位": "corner_drift",
    "角点重复": "corner_duplicate",
}


OOS_CSV_FIELDS = [
    "task_id",
    "base_task_id",
    "keep",
    "selected_for_gate",
    "final_role",
    "priority_flag",
    "review_note_flag",
    "default_eligible",
    "scope",
    "keep_reason",
    "drop_reason",
    "reference_binding_status",
    "adjudication_status",
    "notes",
]


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fieldnames})


def _bool_text(value: bool) -> str:
    return "True" if value else "False"


def _is_true(value: Any) -> bool:
    return str(value).strip().lower() == "true"


def _sort_task_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return sorted(rows, key=lambda row: int(str(row["task_id"])))


def _sorted_task_ids(values: list[str] | set[str]) -> list[str]:
    return sorted({str(value) for value in values}, key=lambda value: int(value))


def load_inputs(root: Path | None = None) -> dict[str, Any]:
    repo_root = root or _repo_root()
    truth_dir = repo_root / "analysis_results" / TRUTH_LAYER_DIRNAME
    trap_dir = repo_root / "analysis_results" / TRAP_COLLECTION_DIRNAME
    phase1_dir = repo_root / "analysis_results" / PHASE1_DIRNAME
    return {
        "repo_root": repo_root,
        "registry_rows": _read_csv(truth_dir / "trap_task_registry_v1.csv"),
        "manual_selection": _read_json(phase1_dir / "prescreen_manual_final_selection_v1.json"),
        "manual_selection_rows": _read_csv(phase1_dir / "prescreen_manual_final_selection_v1.csv"),
        "manual_binding_audit": _read_json(phase1_dir / "prescreen_manual_binding_audit_v1.json"),
        "semi_v4": _read_json(trap_dir / "prescreen_semi_final_selection_v4.json"),
        "source_pool_v1": _read_json(trap_dir / "prescreen_semi_source_pool_freeze_v1.json"),
        "natural_preselection_v3": _read_json(
            trap_dir / "prescreen_semi_trap_natural_preselection_v3.json"
        ),
        "trap_backfill_v4": _read_json(trap_dir / "prescreen_semi_trap_backfill_v4.json"),
    }


def build_semi_control_keepdrop_resolution(
    registry_rows: list[dict[str, str]],
    semi_v4: dict[str, Any],
    source_pool_v1: dict[str, Any],
) -> dict[str, Any]:
    semi_rows = [row for row in registry_rows if row.get("bucket_dir") == "semi"]
    control_rows = [
        row
        for row in semi_rows
        if row.get("recommended_role") == "semi_control_candidate" and _is_true(row.get("default_eligible"))
    ]
    control_rows = _sort_task_rows(control_rows)
    if len(control_rows) != 6:
        raise ValueError(f"Expected 6 semi control candidates, found {len(control_rows)}")

    oos_base_ids = {
        row["base_task_id"] for row in registry_rows if row.get("bucket_dir") == "OOS"
    }
    manual_base_ids = {
        row["base_task_id"] for row in registry_rows if row.get("bucket_dir") == "manual"
    }
    source_base_ids = {
        row["base_task_id"] for row in source_pool_v1.get("current_source_rows", [])
    }
    stale_priority_base_ids = set(semi_v4.get("control_priority_flag_rows", []))

    selected_rows: list[dict[str, Any]] = []
    resolved_priority_rows: list[dict[str, Any]] = []
    current_priority_flag_rows: list[str] = []

    for row in control_rows:
        base_task_id = row["base_task_id"]
        was_stale_priority = base_task_id in stale_priority_base_ids
        if row.get("priority_flag") != "default":
            current_priority_flag_rows.append(base_task_id)

        keep_reason = "Retained as an acceptable control on the current working-consensus layer."
        if was_stale_priority and row.get("priority_flag") == "default":
            keep_reason = (
                "Retained as an acceptable control. The stale v4 folder-level priority blocker has "
                "been cleared by the latest truth-layer registry."
            )
            resolved_priority_rows.append(
                {
                    "task_id": row["task_id"],
                    "base_task_id": base_task_id,
                    "old_v4_status": "tentative_control_selected_with_stale_priority_blocker",
                    "current_priority_flag": row["priority_flag"],
                    "resolution": "keep_as_control",
                }
            )

        selected_rows.append(
            {
                "task_id": row["task_id"],
                "base_task_id": base_task_id,
                "keep": True,
                "final_role": "control",
                "priority_flag": row["priority_flag"],
                "review_note_flag": _is_true(row.get("review_note_flag")),
                "default_eligible": _is_true(row.get("default_eligible")),
                "keep_reason": keep_reason,
                "drop_reason": "",
                "notes": row.get("notes", ""),
            }
        )

    selected_base_ids = {row["base_task_id"] for row in selected_rows}
    control_binding_ready = (
        len(selected_rows) == 6
        and not current_priority_flag_rows
        and not (selected_base_ids & manual_base_ids)
        and not (selected_base_ids & oos_base_ids)
        and not (selected_base_ids & source_base_ids)
    )

    payload = {
        "resolution_name": "prescreen_semi_control_keepdrop_resolution_v1",
        "selection_scope": "stage1_prescreen_semi_control",
        "truth_layer_dir": TRUTH_LAYER_DIRNAME,
        "source_artifacts": [
            f"{TRAP_COLLECTION_DIRNAME}/prescreen_semi_final_selection_v4.json",
            f"{TRAP_COLLECTION_DIRNAME}/prescreen_semi_source_pool_freeze_v1.json",
        ],
        "target_count": 6,
        "selected_control_rows": selected_rows,
        "selected_control_count": len(selected_rows),
        "resolved_stale_priority_rows": resolved_priority_rows,
        "current_priority_flag_rows": sorted(current_priority_flag_rows),
        "manual_pool_overlap_count": len(selected_base_ids & manual_base_ids),
        "manual_pool_overlap_base_task_ids": sorted(selected_base_ids & manual_base_ids),
        "oos_pool_overlap_count": len(selected_base_ids & oos_base_ids),
        "oos_pool_overlap_base_task_ids": sorted(selected_base_ids & oos_base_ids),
        "synthetic_source_overlap_count": len(selected_base_ids & source_base_ids),
        "synthetic_source_overlap_base_task_ids": sorted(selected_base_ids & source_base_ids),
        "control_binding_ready": control_binding_ready,
        "selection_ready": control_binding_ready,
        "blocked_reasons": []
        if control_binding_ready
        else ["current semi control selection still contains active conflicts or priority blockers"],
        "notes": [
            "This resolution only closes the stale control-side blocker from v4.",
            "It does not change the semi trap family policy or the trap-side synthetic backfill."
        ],
    }
    return payload


def build_semi_final_selection_v5(
    registry_rows: list[dict[str, str]],
    manual_selection_rows: list[dict[str, str]],
    control_resolution: dict[str, Any],
    natural_preselection_v3: dict[str, Any],
    trap_backfill_v4: dict[str, Any],
    source_pool_v1: dict[str, Any],
) -> dict[str, Any]:
    manual_base_ids = {
        row["base_task_id"] for row in manual_selection_rows if _is_true(row.get("keep"))
    }
    oos_rows = [row for row in registry_rows if row.get("bucket_dir") == "OOS"]
    oos_base_ids = {row["base_task_id"] for row in oos_rows}

    selected_control_rows = control_resolution["selected_control_rows"]
    selected_trap_rows: list[dict[str, Any]] = []
    for row in natural_preselection_v3.get("selected_natural_cases", []):
        selected_trap_rows.append(
            {
                "candidate_id": row["candidate_id"],
                "task_id": row["task_id"],
                "base_task_id": row["base_task_id"],
                "family": row["family"],
                "source_type": "trap_natural",
                "selection_status": "natural_first_selected",
            }
        )
    for row in trap_backfill_v4.get("selected_synthetic_backfill", []):
        selected_trap_rows.append(
            {
                "candidate_id": row["candidate_id"],
                "base_task_id": row["base_task_id"],
                "family": row["family"],
                "source_type": "trap_synthetic_disjoint_source",
                "selection_status": "synthetic_backfill_selected",
            }
        )

    selected_control_base_ids = {row["base_task_id"] for row in selected_control_rows}
    selected_trap_base_ids = {row["base_task_id"] for row in selected_trap_rows}
    selected_source_base_ids = set(trap_backfill_v4.get("selected_source_base_task_ids", []))
    selected_natural_base_ids = {
        row["base_task_id"]
        for row in selected_trap_rows
        if row.get("source_type") == "trap_natural"
    }

    family_allocations: list[dict[str, Any]] = [
        {
            "family": "acceptable",
            "target_count": 6,
            "current_selected_count": len(selected_control_rows),
            "current_natural_count": len(selected_control_rows),
            "current_synthetic_count": 0,
            "role": "control",
        }
    ]
    for family in ("overextend_adjacent", "over_parsing", "corner_drift", "corner_duplicate"):
        family_rows = [row for row in selected_trap_rows if row["family"] == family]
        natural_count = sum(1 for row in family_rows if row["source_type"] == "trap_natural")
        synthetic_count = sum(
            1 for row in family_rows if row["source_type"] == "trap_synthetic_disjoint_source"
        )
        family_allocations.append(
            {
                "family": family,
                "target_count": 3,
                "current_selected_count": len(family_rows),
                "current_natural_count": natural_count,
                "current_synthetic_count": synthetic_count,
                "role": "trap_core",
            }
        )

    semi_rows = [row for row in registry_rows if row.get("bucket_dir") == "semi"]
    underextend_rows = [row for row in semi_rows if row.get("trap_family") == "漏标"]
    fail_rows = [row for row in semi_rows if row.get("trap_family") == "模型预标注失败"]
    topology_rows = [row for row in semi_rows if row.get("trap_family") == "拓扑崩溃"]

    extension_family_notes = [
        {
            "family": "underextend",
            "available_natural_count": len(underextend_rows),
            "default_eligible_count": sum(_is_true(row.get("default_eligible")) for row in underextend_rows),
            "low_priority_count": sum(row.get("priority_flag") == "low_priority" for row in underextend_rows),
            "available_task_ids": _sorted_task_ids([row["task_id"] for row in underextend_rows]),
            "role": "formal_extension_family",
            "notes": (
                "漏标当前不进入默认主 12 张 trap 配额，但作为正式 extension family 在 "
                "appendix operator library / natural-failure bank / lifecycle audit 中保留。"
            ),
        },
        {
            "family": "fail",
            "available_natural_count": len(fail_rows),
            "available_task_ids": _sorted_task_ids([row["task_id"] for row in fail_rows]),
            "role": "optional_small_quota",
            "notes": "模型预标注失败只保留为 low-priority / optional / audit case。",
        },
        {
            "family": "topology_failure",
            "available_natural_count": len(topology_rows),
            "available_task_ids": _sorted_task_ids([row["task_id"] for row in topology_rows]),
            "role": "audit_small_quota",
            "notes": "拓扑崩溃仍只保留固定小配额稳健性 / 审计地位，不进入默认主 trap 配额。",
        },
    ]

    control_binding_ready = bool(control_resolution.get("control_binding_ready"))
    trap_binding_ready = (
        len(selected_trap_rows) == 12
        and len(selected_control_base_ids & selected_trap_base_ids) == 0
        and len(selected_trap_base_ids & manual_base_ids) == 0
        and len(selected_trap_base_ids & oos_base_ids) == 0
        and len(selected_natural_base_ids & selected_source_base_ids) == 0
    )
    selection_ready = control_binding_ready and trap_binding_ready

    payload = {
        "selection_name": "prescreen_semi_final_selection_v5",
        "selection_scope": "stage1_prescreen_semi",
        "truth_layer_dir": TRUTH_LAYER_DIRNAME,
        "reference_binding_status": REFERENCE_BINDING_STATUS,
        "adjudication_status": ADJUDICATION_STATUS,
        "target_total": 18,
        "control_target": 6,
        "trap_target": 12,
        "selected_control_rows": selected_control_rows,
        "selected_trap_rows": selected_trap_rows,
        "current_selected_control_count": len(selected_control_rows),
        "current_selected_trap_count": len(selected_trap_rows),
        "family_allocations": family_allocations,
        "extension_family_notes": extension_family_notes,
        "selected_source_base_task_ids": sorted(selected_source_base_ids),
        "control_priority_flag_rows": control_resolution.get("current_priority_flag_rows", []),
        "control_trap_overlap_count": len(selected_control_base_ids & selected_trap_base_ids),
        "control_trap_overlap_base_task_ids": sorted(selected_control_base_ids & selected_trap_base_ids),
        "trap_manual_overlap_count": len(selected_trap_base_ids & manual_base_ids),
        "trap_manual_overlap_base_task_ids": sorted(selected_trap_base_ids & manual_base_ids),
        "trap_oos_overlap_count": len(selected_trap_base_ids & oos_base_ids),
        "trap_oos_overlap_base_task_ids": sorted(selected_trap_base_ids & oos_base_ids),
        "natural_synthetic_overlap_count": len(selected_natural_base_ids & selected_source_base_ids),
        "natural_synthetic_overlap_base_task_ids": sorted(selected_natural_base_ids & selected_source_base_ids),
        "control_source_overlap_count": len(selected_control_base_ids & selected_source_base_ids),
        "control_source_overlap_base_task_ids": sorted(selected_control_base_ids & selected_source_base_ids),
        "duplicate_trap_base_task_id_count": len(selected_trap_rows) - len(selected_trap_base_ids),
        "duplicate_trap_base_task_ids": sorted(
            {
                row["base_task_id"]
                for row in selected_trap_rows
                if sum(1 for item in selected_trap_rows if item["base_task_id"] == row["base_task_id"]) > 1
            }
        ),
        "control_binding_ready": control_binding_ready,
        "trap_binding_ready": trap_binding_ready,
        "selection_ready": selection_ready,
        "semi_binding_ready": False,
        "selection_blocked_reasons": []
        if selection_ready
        else ["current semi selection still contains unresolved control/trap conflicts"],
        "binding_blocked_reasons": [BINDING_BLOCKER],
        "notes": [
            "Default main trap quota remains organized around four core families.",
            "Underextend is retained as a formal extension family rather than promoted into the default 12-trap core.",
            "Synthetic trap rows remain freeze-layer assets rather than latest-export manual annotations."
        ],
    }
    return payload


def build_oos_final_quota_binding(registry_rows: list[dict[str, str]]) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    oos_rows = _sort_task_rows([row for row in registry_rows if row.get("bucket_dir") == "OOS"])
    selected_gate_rows: list[dict[str, Any]] = []
    csv_rows: list[dict[str, Any]] = []

    for row in oos_rows:
        selected_for_gate = _is_true(row.get("default_eligible"))
        final_role = "oos_gate" if selected_for_gate else "audit_only"
        keep_reason = (
            "Retained in the executable OOS gate because the latest scope label is OOS and no "
            "active low-priority uncertainty blocks default inclusion."
        )
        drop_reason = ""
        if not selected_for_gate:
            keep_reason = (
                "Retained only as audit-only. This row remains registry-visible, but its explicit "
                "low-priority note means the current protocol does not auto-include it in the default OOS gate."
            )
            drop_reason = (
                "Excluded from the default executable OOS quota because its current low-priority note "
                "means the OOS status is still comparatively uncertain."
            )

        csv_row = {
            "task_id": row["task_id"],
            "base_task_id": row["base_task_id"],
            "keep": _bool_text(True),
            "selected_for_gate": _bool_text(selected_for_gate),
            "final_role": final_role,
            "priority_flag": row["priority_flag"],
            "review_note_flag": row["review_note_flag"],
            "default_eligible": row["default_eligible"],
            "scope": row["current_scope_alias"],
            "keep_reason": keep_reason,
            "drop_reason": drop_reason,
            "reference_binding_status": REFERENCE_BINDING_STATUS,
            "adjudication_status": ADJUDICATION_STATUS,
            "notes": row.get("notes", ""),
        }
        csv_rows.append(csv_row)
        if selected_for_gate:
            selected_gate_rows.append(
                {
                    "task_id": row["task_id"],
                    "base_task_id": row["base_task_id"],
                    "scope": row["current_scope_alias"],
                    "priority_flag": row["priority_flag"],
                    "final_role": final_role,
                }
            )

    scope_breakdown: dict[str, int] = {}
    for row in selected_gate_rows:
        scope_breakdown[row["scope"]] = scope_breakdown.get(row["scope"], 0) + 1

    payload = {
        "binding_name": "oos_final_quota_binding_v1",
        "selection_scope": "stage1_prescreen_oos_gate",
        "truth_layer_dir": TRUTH_LAYER_DIRNAME,
        "reference_binding_status": REFERENCE_BINDING_STATUS,
        "adjudication_status": ADJUDICATION_STATUS,
        "oos_total_pool_count": len(oos_rows),
        "final_oos_gate_count": len(selected_gate_rows),
        "audit_only_count": len(oos_rows) - len(selected_gate_rows),
        "selected_oos_gate_rows": selected_gate_rows,
        "low_priority_audit_only_task_ids": _sorted_task_ids(
            [row["task_id"] for row in oos_rows if row.get("priority_flag") == "low_priority"]
        ),
        "scope_breakdown_in_final_gate": scope_breakdown,
        "oos_selection_frozen": True,
        "oos_selection_ready": True,
        "oos_binding_ready": False,
        "selection_blocked_reasons": [],
        "binding_blocked_reasons": [BINDING_BLOCKER],
        "notes": [
            "Low-priority OOS rows are interpreted as comparatively uncertain OOS cases, not as unannotatable samples.",
            "These rows remain in the registry, but do not auto-enter the default executable OOS gate."
        ],
    }
    return payload, csv_rows


def build_stage1_final_binding_audit(
    manual_selection: dict[str, Any],
    manual_selection_rows: list[dict[str, str]],
    manual_binding_audit: dict[str, Any],
    semi_selection: dict[str, Any],
    oos_binding: dict[str, Any],
    source_pool_v1: dict[str, Any],
) -> dict[str, Any]:
    manual_base_ids = {
        row["base_task_id"] for row in manual_selection_rows if _is_true(row.get("keep"))
    }
    semi_control_base_ids = {
        row["base_task_id"] for row in semi_selection.get("selected_control_rows", [])
    }
    semi_trap_base_ids = {
        row["base_task_id"] for row in semi_selection.get("selected_trap_rows", [])
    }
    semi_all_base_ids = semi_control_base_ids | semi_trap_base_ids
    oos_gate_base_ids = {
        row["base_task_id"] for row in oos_binding.get("selected_oos_gate_rows", [])
    }
    source_base_ids = {
        row["base_task_id"] for row in source_pool_v1.get("current_source_rows", [])
    }

    raw_blocked_reasons: list[str] = []
    for reason in manual_binding_audit.get("blocked_reasons", []):
        if reason not in raw_blocked_reasons:
            raw_blocked_reasons.append(reason)
    for reason in semi_selection.get("binding_blocked_reasons", []):
        if reason not in raw_blocked_reasons:
            raw_blocked_reasons.append(reason)
    for reason in oos_binding.get("binding_blocked_reasons", []):
        if reason not in raw_blocked_reasons:
            raw_blocked_reasons.append(reason)

    blocked_reasons: list[str] = []
    if any("working_consensus_not_final_gold" in reason for reason in raw_blocked_reasons):
        blocked_reasons.append(BINDING_BLOCKER)
    for reason in raw_blocked_reasons:
        if "working_consensus_not_final_gold" in reason:
            continue
        if reason not in blocked_reasons:
            blocked_reasons.append(reason)

    prescreen_ready = (
        bool(manual_binding_audit.get("manual_binding_ready"))
        and bool(semi_selection.get("semi_binding_ready"))
        and bool(oos_binding.get("oos_binding_ready"))
        and len(manual_base_ids & semi_all_base_ids) == 0
        and len(manual_base_ids & oos_gate_base_ids) == 0
        and len(semi_all_base_ids & oos_gate_base_ids) == 0
    )

    payload = {
        "audit_name": "stage1_final_binding_audit_v1",
        "truth_layer_dir": TRUTH_LAYER_DIRNAME,
        "reference_binding_status": REFERENCE_BINDING_STATUS,
        "adjudication_status": ADJUDICATION_STATUS,
        "manual_total_selected": manual_selection.get("manual_total_selected", 0),
        "manual_expert_anchor_count": manual_selection.get("expert_anchor_count", 0),
        "manual_non_anchor_count": manual_selection.get("non_anchor_count", 0),
        "semi_control_count": semi_selection.get("current_selected_control_count", 0),
        "semi_trap_count": semi_selection.get("current_selected_trap_count", 0),
        "oos_final_gate_count": oos_binding.get("final_oos_gate_count", 0),
        "manual_vs_semi_overlap_count": len(manual_base_ids & semi_all_base_ids),
        "manual_vs_semi_overlap_base_task_ids": sorted(manual_base_ids & semi_all_base_ids),
        "manual_vs_oos_overlap_count": len(manual_base_ids & oos_gate_base_ids),
        "manual_vs_oos_overlap_base_task_ids": sorted(manual_base_ids & oos_gate_base_ids),
        "semi_vs_oos_overlap_count": len(semi_all_base_ids & oos_gate_base_ids),
        "semi_vs_oos_overlap_base_task_ids": sorted(semi_all_base_ids & oos_gate_base_ids),
        "semi_control_vs_source_overlap_count": len(semi_control_base_ids & source_base_ids),
        "semi_control_vs_source_overlap_base_task_ids": sorted(semi_control_base_ids & source_base_ids),
        "manual_binding_ready": bool(manual_binding_audit.get("manual_binding_ready")),
        "semi_selection_ready": bool(semi_selection.get("selection_ready")),
        "semi_binding_ready": bool(semi_selection.get("semi_binding_ready")),
        "oos_selection_ready": bool(oos_binding.get("oos_selection_ready")),
        "oos_binding_ready": bool(oos_binding.get("oos_binding_ready")),
        "selection_freeze_complete": (
            bool(manual_binding_audit.get("manual_selection_frozen"))
            and bool(semi_selection.get("selection_ready"))
            and bool(oos_binding.get("oos_selection_frozen"))
        ),
        "stage1_binding_ready": prescreen_ready,
        "prescreen_ready": prescreen_ready,
        "blocked_reasons": blocked_reasons,
        "notes": [
            "Stage 1 selection freeze is complete on the current working-consensus layer.",
            "Executable thesis-grade readiness remains blocked until the reference layer is upgraded from working consensus to final adjudicated gold."
        ],
    }
    return payload


def run(output_dir: Path | None = None, root: Path | None = None) -> dict[str, Path]:
    inputs = load_inputs(root=root)
    repo_root = inputs["repo_root"]
    final_output_dir = output_dir or (repo_root / "analysis_results" / PHASE1_DIRNAME)

    control_resolution = build_semi_control_keepdrop_resolution(
        registry_rows=inputs["registry_rows"],
        semi_v4=inputs["semi_v4"],
        source_pool_v1=inputs["source_pool_v1"],
    )
    semi_selection = build_semi_final_selection_v5(
        registry_rows=inputs["registry_rows"],
        manual_selection_rows=inputs["manual_selection_rows"],
        control_resolution=control_resolution,
        natural_preselection_v3=inputs["natural_preselection_v3"],
        trap_backfill_v4=inputs["trap_backfill_v4"],
        source_pool_v1=inputs["source_pool_v1"],
    )
    oos_binding, oos_csv_rows = build_oos_final_quota_binding(inputs["registry_rows"])
    stage1_audit = build_stage1_final_binding_audit(
        manual_selection=inputs["manual_selection"],
        manual_selection_rows=inputs["manual_selection_rows"],
        manual_binding_audit=inputs["manual_binding_audit"],
        semi_selection=semi_selection,
        oos_binding=oos_binding,
        source_pool_v1=inputs["source_pool_v1"],
    )

    outputs = {
        "semi_control_resolution": final_output_dir / "prescreen_semi_control_keepdrop_resolution_v1.json",
        "semi_final_selection": final_output_dir / "prescreen_semi_final_selection_v5.json",
        "oos_binding_json": final_output_dir / "oos_final_quota_binding_v1.json",
        "oos_binding_csv": final_output_dir / "oos_final_quota_binding_v1.csv",
        "stage1_audit": final_output_dir / "stage1_final_binding_audit_v1.json",
    }
    _write_json(outputs["semi_control_resolution"], control_resolution)
    _write_json(outputs["semi_final_selection"], semi_selection)
    _write_json(outputs["oos_binding_json"], oos_binding)
    _write_csv(outputs["oos_binding_csv"], oos_csv_rows, OOS_CSV_FIELDS)
    _write_json(outputs["stage1_audit"], stage1_audit)
    return outputs


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Freeze semi control/trap selection, OOS binding, and Stage 1 audit."
    )
    parser.add_argument("--output-dir", type=Path, default=None)
    args = parser.parse_args()
    outputs = run(output_dir=args.output_dir)
    print(json.dumps({key: str(value) for key, value in outputs.items()}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
