from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any


PHASE1_DIRNAME = "phase1_progress_20260324"
FINAL_GOLD_DIRNAME = "final_gold_layer_20260325"
TRUTH_LAYER_DIRNAME = "truth_layer_extraction_20260324"

SEMI_V6_NAME = "prescreen_semi_final_selection_v6.json"
SEMI_V7_NAME = "prescreen_semi_final_selection_v7.json"
STAGE1_AUDIT_V3_NAME = "stage1_final_binding_audit_v3.json"


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


def _load_inputs(repo_root: Path) -> dict[str, Any]:
    phase1_dir = repo_root / "analysis_results" / PHASE1_DIRNAME
    truth_dir = repo_root / "analysis_results" / TRUTH_LAYER_DIRNAME
    final_gold_dir = repo_root / "analysis_results" / FINAL_GOLD_DIRNAME
    registry_rows = _read_csv(truth_dir / "trap_task_registry_v1.csv")
    final_gold_rows = _read_jsonl(final_gold_dir / "final_gold_records_v1.jsonl")
    return {
        "phase1_dir": phase1_dir,
        "semi_v6": _read_json(phase1_dir / SEMI_V6_NAME),
        "manual_binding_v2": _read_json(phase1_dir / "manual_binding_audit_v2.json"),
        "oos_binding_v2": _read_json(phase1_dir / "oos_final_quota_binding_v2.json"),
        "registry_by_task": {str(row["task_id"]): row for row in registry_rows},
        "final_gold_by_task": {str(row["task_id"]): row for row in final_gold_rows},
    }


def _build_natural_row(task_id: str, family: str, registry_by_task: dict[str, dict[str, str]], final_gold_by_task: dict[str, dict[str, Any]]) -> dict[str, Any]:
    registry_row = registry_by_task.get(task_id)
    if not registry_row:
        raise KeyError(f"Missing registry row for task {task_id}")
    gold_row = final_gold_by_task.get(task_id)
    if not gold_row:
        raise KeyError(f"Missing final gold row for task {task_id}")
    return {
        "candidate_id": f"natural_{family}_{task_id}",
        "task_id": task_id,
        "base_task_id": registry_row["base_task_id"],
        "family": family,
        "source_type": "trap_natural",
        "selection_status": "natural_first_selected",
        "gold_scope_alias": str(gold_row["final_scope_alias"]),
        "rebind_status": "ready",
        "rebind_reason": "",
    }


def _gold_ready_for_in_scope(task_id: str, final_gold_by_task: dict[str, dict[str, Any]]) -> tuple[bool, str]:
    gold_row = final_gold_by_task.get(task_id)
    if not gold_row:
        return False, "missing_gold_row"
    if str(gold_row["final_scope_binary"]) != "in_scope":
        return False, "scope_mismatch"
    if not _is_true(gold_row.get("geometry_gold_ready")):
        return False, "geometry_not_ready"
    return True, ""


def build_semi_v7(inputs: dict[str, Any]) -> dict[str, Any]:
    semi_v6 = inputs["semi_v6"]
    registry_by_task = inputs["registry_by_task"]
    final_gold_by_task = inputs["final_gold_by_task"]

    selected_control_rows = semi_v6["selected_control_rows"]

    carried_synthetic_rows = []
    for row in semi_v6["selected_trap_rows"]:
        if str(row.get("source_type")) != "trap_synthetic_disjoint_source":
            continue
        if str(row.get("family")) == "overextend_adjacent":
            continue
        carried_synthetic_rows.append(dict(row))

    natural_rows = [
        _build_natural_row("493", "overextend_adjacent", registry_by_task, final_gold_by_task),
        _build_natural_row("577", "overextend_adjacent", registry_by_task, final_gold_by_task),
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

    missing_gold_task_ids: list[str] = []
    scope_mismatch_task_ids: list[str] = []
    geometry_not_ready_task_ids: list[str] = []
    for row in natural_rows:
        ok, failure = _gold_ready_for_in_scope(str(row["task_id"]), final_gold_by_task)
        if ok:
            continue
        if failure == "missing_gold_row":
            missing_gold_task_ids.append(str(row["task_id"]))
        elif failure == "scope_mismatch":
            scope_mismatch_task_ids.append(str(row["task_id"]))
        elif failure == "geometry_not_ready":
            geometry_not_ready_task_ids.append(str(row["task_id"]))

    natural_binding_ready = not (
        missing_gold_task_ids or scope_mismatch_task_ids or geometry_not_ready_task_ids
    )
    control_binding_ready = bool(semi_v6["control_binding_ready"])
    synthetic_asset_ready = True
    trap_target = int(semi_v6["trap_target"])
    current_selected_trap_count = len(selected_trap_rows)
    overextend_gap = max(
        0,
        next(
            allocation["current_gap_count"]
            for allocation in family_allocations
            if allocation["family"] == "overextend_adjacent"
        ),
    )

    selection_ready = (
        control_binding_ready
        and natural_binding_ready
        and synthetic_asset_ready
        and current_selected_trap_count == trap_target
    )

    blocked_reasons: list[str] = []
    if overextend_gap > 0:
        blocked_reasons.append(
            "natural-only overextend_adjacent policy leaves the main semi trap set short by 1 clean natural candidate under the current pool"
        )
    if missing_gold_task_ids or scope_mismatch_task_ids or geometry_not_ready_task_ids:
        blocked_reasons.append(
            "some selected semi natural trap rows are missing from final gold, no longer in_scope, or not geometry-ready"
        )

    return {
        "selection_name": "prescreen_semi_final_selection_v7",
        "parent_selection": "prescreen_semi_final_selection_v6",
        "rebind_source": semi_v6["rebind_source"],
        "truth_layer_dir": semi_v6["truth_layer_dir"],
        "reference_binding_status": semi_v6["reference_binding_status"],
        "adjudication_status": semi_v6["adjudication_status"],
        "target_total": semi_v6["target_total"],
        "control_target": semi_v6["control_target"],
        "trap_target": trap_target,
        "selected_control_rows": selected_control_rows,
        "selected_trap_rows": selected_trap_rows,
        "current_selected_control_count": len(selected_control_rows),
        "current_selected_trap_count": current_selected_trap_count,
        "family_allocations": family_allocations,
        "extension_family_notes": semi_v6.get("extension_family_notes", []),
        "policy_updates": [
            {
                "change": "natural_corner_drift_replaced",
                "old_task_id": "474",
                "new_task_id": "625",
                "reason": "task625 is the current natural corner_drift exemplar aligned with the registry; task474 is currently aligned with underextend rather than corner_drift.",
            },
            {
                "change": "synthetic_overextend_removed_from_main_trap",
                "removed_candidate_ids": [
                    "legacy_disjoint_source_010_overextend_adjacent",
                    "legacy_disjoint_source_009_overextend_adjacent",
                ],
                "replacement_natural_task_ids": ["577"],
                "reason": "synthetic overextend_adjacent remains the weakest construct-validity family under the current geometry-only operator implementation, so the main trap set now applies natural-only overextend evidence.",
            },
        ],
        "natural_pool_review": {
            "corner_drift": {
                "selected_task_ids": ["625"],
                "replaced_task_ids": ["474"],
                "notes": "task625 is currently the clean registry-aligned corner_drift natural exemplar.",
            },
            "overextend_adjacent": {
                "selected_task_ids": ["493", "577"],
                "excluded_task_ids": ["499"],
                "notes": "task499 remains in the folder pool but the current registry aligns it more closely with corner_duplicate than clean overextend_adjacent.",
            },
        },
        "control_binding_ready": control_binding_ready,
        "natural_trap_binding_ready": natural_binding_ready,
        "synthetic_asset_ready": synthetic_asset_ready,
        "selection_ready": selection_ready,
        "semi_binding_ready": selection_ready,
        "control_missing_gold_task_ids": semi_v6.get("control_missing_gold_task_ids", []),
        "control_scope_mismatch_task_ids": semi_v6.get("control_scope_mismatch_task_ids", []),
        "control_geometry_not_ready_task_ids": semi_v6.get("control_geometry_not_ready_task_ids", []),
        "natural_missing_gold_task_ids": _sorted_task_ids(missing_gold_task_ids),
        "natural_scope_mismatch_task_ids": _sorted_task_ids(scope_mismatch_task_ids),
        "natural_geometry_not_ready_task_ids": _sorted_task_ids(geometry_not_ready_task_ids),
        "blocked_reasons": blocked_reasons,
        "notes": [
            "This revision only tightens the semantic alignment of the semi main-trap set.",
            "It does not change the 6 control target or the four-core-family thesis skeleton.",
            "Under the current pool, natural-only overextend_adjacent leaves a one-row main-trap gap until a new clean natural candidate is added.",
        ],
    }


def build_stage1_audit_v3(inputs: dict[str, Any], semi_v7: dict[str, Any]) -> dict[str, Any]:
    manual_binding_v2 = inputs["manual_binding_v2"]
    oos_binding_v2 = inputs["oos_binding_v2"]
    manual_ready = bool(manual_binding_v2["manual_binding_ready"])
    oos_ready = bool(oos_binding_v2["oos_binding_ready"])
    semi_ready = bool(semi_v7["semi_binding_ready"])
    prescreen_ready = manual_ready and semi_ready and oos_ready

    blocked_reasons: list[str] = []
    if not semi_ready:
        blocked_reasons.extend(semi_v7["blocked_reasons"])
    if not manual_ready:
        blocked_reasons.extend(manual_binding_v2.get("blocked_reasons", []))
    if not oos_ready:
        blocked_reasons.extend(oos_binding_v2.get("blocked_reasons", []))

    return {
        "audit_name": "stage1_final_binding_audit_v3",
        "truth_layer_dir": semi_v7["truth_layer_dir"],
        "reference_binding_status": semi_v7["reference_binding_status"],
        "adjudication_status": semi_v7["adjudication_status"],
        "manual_binding_ready": manual_ready,
        "semi_binding_ready": semi_ready,
        "oos_binding_ready": oos_ready,
        "manual_expert_anchor_count": int(manual_binding_v2["expert_anchor_count"]),
        "manual_non_anchor_count": int(manual_binding_v2["non_anchor_count"]),
        "semi_control_count": int(semi_v7["current_selected_control_count"]),
        "semi_trap_count": int(semi_v7["current_selected_trap_count"]),
        "oos_final_gate_count": int(oos_binding_v2["final_oos_gate_count"]),
        "selection_freeze_complete": prescreen_ready,
        "selection_freeze_reused": False,
        "rebind_only_no_reselection": False,
        "prescreen_ready": prescreen_ready,
        "blocked_reasons": blocked_reasons,
        "notes": [
            "This audit reflects a targeted semantic revision on the semi main-trap layer.",
            "manual and OOS remain unchanged from the v2 final-gold rebinding state.",
        ],
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", default=f"analysis_results/{PHASE1_DIRNAME}")
    args = parser.parse_args()

    repo_root = _repo_root()
    inputs = _load_inputs(repo_root)
    semi_v7 = build_semi_v7(inputs)
    stage1_audit_v3 = build_stage1_audit_v3(inputs, semi_v7)

    output_dir = repo_root / args.output_dir
    _write_json(output_dir / SEMI_V7_NAME, semi_v7)
    _write_json(output_dir / STAGE1_AUDIT_V3_NAME, stage1_audit_v3)


if __name__ == "__main__":
    main()
