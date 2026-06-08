from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any


PHASE1_DIRNAME = "phase1_progress_20260324"
FINAL_GOLD_DIRNAME = "final_gold_layer_20260325"
TRUTH_LAYER_DIRNAME = "truth_layer_extraction_20260324"

SEMI_V7_NAME = "prescreen_semi_final_selection_v7.json"
SEMI_V8_NAME = "prescreen_semi_final_selection_v8.json"
STAGE1_AUDIT_V4_NAME = "stage1_final_binding_audit_v4.json"


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        rows.append(json.loads(line))
    return rows


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _is_true(value: Any) -> bool:
    return str(value).strip().lower() == "true"


def _sorted_task_ids(values: list[str] | set[str]) -> list[str]:
    return sorted({str(value) for value in values}, key=lambda value: int(value))


def load_inputs(repo_root: Path) -> dict[str, Any]:
    phase1_dir = repo_root / "analysis_results" / PHASE1_DIRNAME
    truth_dir = repo_root / "analysis_results" / TRUTH_LAYER_DIRNAME
    final_gold_dir = repo_root / "analysis_results" / FINAL_GOLD_DIRNAME
    registry_rows = _read_csv(truth_dir / "trap_task_registry_v1.csv")
    final_gold_rows = _read_jsonl(final_gold_dir / "final_gold_records_v1.jsonl")
    return {
        "phase1_dir": phase1_dir,
        "semi_v7": _read_json(phase1_dir / SEMI_V7_NAME),
        "manual_binding_v2": _read_json(phase1_dir / "manual_binding_audit_v2.json"),
        "oos_binding_v2": _read_json(phase1_dir / "oos_final_quota_binding_v2.json"),
        "registry_by_task": {str(row["task_id"]): row for row in registry_rows},
        "final_gold_by_task": {str(row["task_id"]): row for row in final_gold_rows},
    }


def _build_natural_row(
    task_id: str,
    family: str,
    registry_by_task: dict[str, dict[str, str]],
    final_gold_by_task: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    registry_row = registry_by_task.get(task_id)
    if not registry_row:
        raise KeyError(f"Missing registry row for task {task_id}")
    gold_row = final_gold_by_task.get(task_id)
    rebind_status = "ready"
    rebind_reason = ""
    gold_scope_alias = ""
    if gold_row is None:
        rebind_status = "missing_gold_row"
        rebind_reason = "Final gold layer does not yet contain this natural trap task."
    else:
        gold_scope_alias = str(gold_row["final_scope_alias"])
        if str(gold_row["final_scope_binary"]) != "in_scope":
            rebind_status = "scope_mismatch"
            rebind_reason = "Final gold scope no longer supports this natural trap as in-scope."
        elif not _is_true(gold_row.get("geometry_gold_ready")):
            rebind_status = "geometry_not_ready"
            rebind_reason = "Final gold row exists, but geometry reference is not marked ready."

    return {
        "candidate_id": f"natural_{family}_{task_id}",
        "task_id": task_id,
        "base_task_id": registry_row["base_task_id"],
        "family": family,
        "source_type": "trap_natural",
        "selection_status": "natural_first_selected",
        "priority_flag": registry_row["priority_flag"],
        "review_note_flag": registry_row["review_note_flag"],
        "default_eligible": registry_row["default_eligible"],
        "gold_scope_alias": gold_scope_alias,
        "rebind_status": rebind_status,
        "rebind_reason": rebind_reason,
    }


def build_semi_v8(inputs: dict[str, Any]) -> dict[str, Any]:
    semi_v7 = inputs["semi_v7"]
    registry_by_task = inputs["registry_by_task"]
    final_gold_by_task = inputs["final_gold_by_task"]

    selected_control_rows = semi_v7["selected_control_rows"]
    carried_synthetic_rows = [
        dict(row)
        for row in semi_v7["selected_trap_rows"]
        if str(row.get("source_type")) == "trap_synthetic_disjoint_source"
    ]

    natural_rows = [
        _build_natural_row("493", "overextend_adjacent", registry_by_task, final_gold_by_task),
        _build_natural_row("577", "overextend_adjacent", registry_by_task, final_gold_by_task),
        _build_natural_row("580", "overextend_adjacent", registry_by_task, final_gold_by_task),
        _build_natural_row("505", "over_parsing", registry_by_task, final_gold_by_task),
        _build_natural_row("625", "corner_drift", registry_by_task, final_gold_by_task),
        _build_natural_row("477", "corner_duplicate", registry_by_task, final_gold_by_task),
    ]

    selected_trap_rows = natural_rows + carried_synthetic_rows

    family_allocations: list[dict[str, Any]] = [
        {
            "family": "acceptable",
            "target_count": 6,
            "current_selected_count": len(selected_control_rows),
            "current_natural_count": len(selected_control_rows),
            "current_synthetic_count": 0,
            "current_gap_count": max(0, 6 - len(selected_control_rows)),
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
                "current_gap_count": max(0, 3 - len(family_rows)),
                "role": "trap_core",
            }
        )

    natural_not_ready = [
        row for row in natural_rows if str(row["rebind_status"]) != "ready"
    ]
    natural_missing_gold_task_ids = _sorted_task_ids(
        [row["task_id"] for row in natural_not_ready if row["rebind_status"] == "missing_gold_row"]
    )
    natural_scope_mismatch_task_ids = _sorted_task_ids(
        [row["task_id"] for row in natural_not_ready if row["rebind_status"] == "scope_mismatch"]
    )
    natural_geometry_not_ready_task_ids = _sorted_task_ids(
        [row["task_id"] for row in natural_not_ready if row["rebind_status"] == "geometry_not_ready"]
    )

    control_binding_ready = bool(semi_v7["control_binding_ready"])
    natural_trap_binding_ready = not natural_not_ready
    synthetic_asset_ready = True
    trap_target = int(semi_v7["trap_target"])
    current_selected_trap_count = len(selected_trap_rows)
    selection_ready = (
        control_binding_ready
        and natural_trap_binding_ready
        and synthetic_asset_ready
        and current_selected_trap_count == trap_target
    )

    blocked_reasons: list[str] = []
    if natural_not_ready:
        blocked_reasons.append(
            "some selected semi natural trap rows are missing from final gold, no longer in_scope, or not geometry-ready"
        )

    return {
        "selection_name": "prescreen_semi_final_selection_v8",
        "parent_selection": "prescreen_semi_final_selection_v7",
        "rebind_source": str(
            inputs["phase1_dir"].parent / FINAL_GOLD_DIRNAME / "final_gold_records_v1.jsonl"
        ),
        "truth_layer_dir": TRUTH_LAYER_DIRNAME,
        "reference_binding_status": "final_adjudicated_gold_rebound",
        "adjudication_status": "final_adjudicated_gold",
        "target_total": semi_v7["target_total"],
        "control_target": semi_v7["control_target"],
        "trap_target": trap_target,
        "selected_control_rows": selected_control_rows,
        "selected_trap_rows": selected_trap_rows,
        "current_selected_control_count": len(selected_control_rows),
        "current_selected_trap_count": current_selected_trap_count,
        "family_allocations": family_allocations,
        "extension_family_notes": semi_v7.get("extension_family_notes", []),
        "policy_updates": [
            {
                "change": "natural_corner_drift_replaced",
                "old_task_id": "474",
                "new_task_id": "625",
                "reason": "task625 is the registry-aligned natural corner_drift exemplar.",
            },
            {
                "change": "overextend_adjacent_switched_to_natural_only",
                "removed_candidate_ids": [
                    "legacy_disjoint_source_010_overextend_adjacent",
                    "legacy_disjoint_source_009_overextend_adjacent",
                ],
                "natural_task_ids": ["493", "577", "580"],
                "reason": "synthetic overextend_adjacent remains the weakest construct-validity family under the current geometry-only operator implementation, so the main trap set now uses natural-only overextend evidence.",
            },
        ],
        "natural_pool_review": {
            "corner_drift": {
                "selected_task_ids": ["625"],
                "replaced_task_ids": ["474"],
                "notes": "task625 is currently the clean registry-aligned corner_drift natural exemplar.",
            },
            "overextend_adjacent": {
                "selected_task_ids": ["493", "577", "580"],
                "excluded_task_ids": ["499"],
                "notes": "task499 remains in the folder pool but the current registry aligns it more closely with corner_duplicate than clean overextend_adjacent; task580 is now added as the third natural overextend row.",
            },
        },
        "audit_stress_candidates": {
            "fail_task_ids": ["475"] if "475" in registry_by_task else [],
            "topology_failure_task_ids": [
                task_id
                for task_id, row in registry_by_task.items()
                if str(row.get("model_issue_tags", "")) == "topology_failure"
            ],
            "notes": "fail / topology_failure remain small-quota audit-only candidates and are not merged into the default main 12 traps.",
        },
        "control_binding_ready": control_binding_ready,
        "natural_trap_binding_ready": natural_trap_binding_ready,
        "synthetic_asset_ready": synthetic_asset_ready,
        "selection_ready": selection_ready,
        "semi_binding_ready": selection_ready,
        "control_missing_gold_task_ids": semi_v7.get("control_missing_gold_task_ids", []),
        "control_scope_mismatch_task_ids": semi_v7.get("control_scope_mismatch_task_ids", []),
        "control_geometry_not_ready_task_ids": semi_v7.get("control_geometry_not_ready_task_ids", []),
        "natural_missing_gold_task_ids": natural_missing_gold_task_ids,
        "natural_scope_mismatch_task_ids": natural_scope_mismatch_task_ids,
        "natural_geometry_not_ready_task_ids": natural_geometry_not_ready_task_ids,
        "blocked_reasons": blocked_reasons,
        "notes": [
            "This revision closes the natural-only overextend gap by adding task580 as the third natural overextend row.",
            "The main thesis skeleton remains 6 control + 12 main traps.",
            "fail / topology_failure remain audit-only and do not enter the default main 12 traps.",
        ],
    }


def build_stage1_audit_v4(inputs: dict[str, Any], semi_v8: dict[str, Any]) -> dict[str, Any]:
    manual_binding_v2 = inputs["manual_binding_v2"]
    oos_binding_v2 = inputs["oos_binding_v2"]
    manual_ready = bool(manual_binding_v2["manual_binding_ready"])
    oos_ready = bool(oos_binding_v2["oos_binding_ready"])
    semi_ready = bool(semi_v8["semi_binding_ready"])
    prescreen_ready = manual_ready and semi_ready and oos_ready

    blocked_reasons: list[str] = []
    if not semi_ready:
        blocked_reasons.extend(semi_v8["blocked_reasons"])
    if not manual_ready:
        blocked_reasons.extend(manual_binding_v2.get("blocked_reasons", []))
    if not oos_ready:
        blocked_reasons.extend(oos_binding_v2.get("blocked_reasons", []))

    return {
        "audit_name": "stage1_final_binding_audit_v4",
        "truth_layer_dir": TRUTH_LAYER_DIRNAME,
        "reference_binding_status": "final_adjudicated_gold_rebound",
        "adjudication_status": "final_adjudicated_gold",
        "manual_binding_ready": manual_ready,
        "semi_binding_ready": semi_ready,
        "oos_binding_ready": oos_ready,
        "manual_expert_anchor_count": int(manual_binding_v2["expert_anchor_count"]),
        "manual_non_anchor_count": int(manual_binding_v2["non_anchor_count"]),
        "semi_control_count": int(semi_v8["current_selected_control_count"]),
        "semi_trap_count": int(semi_v8["current_selected_trap_count"]),
        "oos_final_gate_count": int(oos_binding_v2["final_oos_gate_count"]),
        "selection_freeze_complete": prescreen_ready,
        "selection_freeze_reused": False,
        "rebind_only_no_reselection": False,
        "prescreen_ready": prescreen_ready,
        "blocked_reasons": blocked_reasons,
        "notes": [
            "This audit reflects the corrected task580 mapping and the natural-only overextend main-trap policy.",
            "manual and OOS continue to reuse the v2 final-gold rebinding state.",
        ],
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", default=f"analysis_results/{PHASE1_DIRNAME}")
    args = parser.parse_args()

    repo_root = _repo_root()
    inputs = load_inputs(repo_root)
    semi_v8 = build_semi_v8(inputs)
    stage1_audit_v4 = build_stage1_audit_v4(inputs, semi_v8)

    output_dir = repo_root / args.output_dir
    _write_json(output_dir / SEMI_V8_NAME, semi_v8)
    _write_json(output_dir / STAGE1_AUDIT_V4_NAME, stage1_audit_v4)


if __name__ == "__main__":
    main()
