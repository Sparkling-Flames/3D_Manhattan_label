from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


PHASE1_DIRNAME = "phase1_progress_20260324"
FINAL_GOLD_DIRNAME = "final_gold_layer_20260325"
TRUTH_LAYER_DIRNAME = "truth_layer_extraction_20260324"

SEMI_V9_NAME = "prescreen_semi_final_selection_v9.json"
SEMI_V10_NAME = "prescreen_semi_final_selection_v10.json"
STAGE1_AUDIT_V5_NAME = "stage1_final_binding_audit_v5.json"
STAGE1_AUDIT_V6_NAME = "stage1_final_binding_audit_v6.json"


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


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
    import csv

    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _is_true(value: Any) -> bool:
    return str(value).strip().lower() == "true"


def load_inputs(repo_root: Path) -> dict[str, Any]:
    phase1_dir = repo_root / "analysis_results" / PHASE1_DIRNAME
    truth_dir = repo_root / "analysis_results" / TRUTH_LAYER_DIRNAME
    final_gold_dir = repo_root / "analysis_results" / FINAL_GOLD_DIRNAME
    registry_rows = _read_csv(truth_dir / "trap_task_registry_v1.csv")
    final_gold_rows = _read_jsonl(final_gold_dir / "final_gold_records_v1.jsonl")
    return {
        "phase1_dir": phase1_dir,
        "semi_v9": _read_json(phase1_dir / SEMI_V9_NAME),
        "stage1_audit_v5": _read_json(phase1_dir / STAGE1_AUDIT_V5_NAME),
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
        rebind_reason = "Final gold layer does not contain this selected natural trap task."
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


def build_semi_v10(inputs: dict[str, Any]) -> dict[str, Any]:
    semi_v9 = inputs["semi_v9"]
    registry_by_task = inputs["registry_by_task"]
    final_gold_by_task = inputs["final_gold_by_task"]

    selected_control_rows = semi_v9["selected_control_rows"]
    carried_synthetic_rows = [
        dict(row)
        for row in semi_v9["selected_trap_rows"]
        if str(row.get("source_type")) == "trap_synthetic_disjoint_source"
    ]

    natural_rows = [
        _build_natural_row("493", "overextend_adjacent", registry_by_task, final_gold_by_task),
        _build_natural_row("577", "overextend_adjacent", registry_by_task, final_gold_by_task),
        _build_natural_row("668", "overextend_adjacent", registry_by_task, final_gold_by_task),
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

    extension_notes = list(semi_v9.get("extension_family_notes", []))
    for note in extension_notes:
        family = note.get("family")
        if family == "underextend":
            note["available_natural_count"] = 3
            note["available_task_ids"] = ["579", "665", "712"]
            note["notes"] = (
                "漏标当前仍不进入默认主 12 张 trap 配额，但作为正式 extension family "
                "继续保留在 appendix operator library / natural-failure bank / lifecycle audit 中。"
                "task665 是本轮新增的 underextend natural 候选。"
            )
        elif family == "fail":
            note["notes"] = (
                "模型预标注失败当前仍只保留为低优先 / optional / holdout case；"
                "task475 不进入活跃 prescreen 主包或 active audit_stress。"
            )
        elif family == "topology_failure":
            note["notes"] = (
                "拓扑崩溃当前仍只保留 audit-only / robustness-only 地位；"
                "当前仓库尚无已物化的 topology synthetic asset。"
            )

    natural_not_ready = [row for row in natural_rows if str(row["rebind_status"]) != "ready"]
    control_binding_ready = bool(semi_v9["control_binding_ready"])
    natural_trap_binding_ready = not natural_not_ready
    synthetic_asset_ready = True
    trap_target = int(semi_v9["trap_target"])
    current_selected_trap_count = len(selected_trap_rows)
    selection_ready = (
        control_binding_ready
        and natural_trap_binding_ready
        and synthetic_asset_ready
        and current_selected_trap_count == trap_target
    )

    return {
        **semi_v9,
        "selection_name": "prescreen_semi_final_selection_v10",
        "parent_selection": "prescreen_semi_final_selection_v9",
        "rebind_source": str(
            inputs["phase1_dir"].parent / FINAL_GOLD_DIRNAME / "final_gold_records_v1.jsonl"
        ),
        "selected_control_rows": selected_control_rows,
        "selected_trap_rows": selected_trap_rows,
        "current_selected_control_count": len(selected_control_rows),
        "current_selected_trap_count": current_selected_trap_count,
        "family_allocations": family_allocations,
        "extension_family_notes": extension_notes,
        "policy_updates": list(semi_v9.get("policy_updates", []))
        + [
            {
                "change": "natural_overextend_canonical_exemplar_cleaned",
                "old_task_id": "580",
                "new_task_id": "668",
                "reason": "task668 is the cleaner latest-verified overextend_adjacent natural row, so task580 no longer occupies a main canonical slot.",
            }
        ],
        "natural_pool_review": {
            "corner_drift": {
                "selected_task_ids": ["625"],
                "replaced_task_ids": ["474"],
                "notes": "task625 is the current registry-aligned natural corner_drift exemplar.",
            },
            "overextend_adjacent": {
                "selected_task_ids": ["493", "577", "668"],
                "special_review_reserve_task_ids": ["580"],
                "excluded_task_ids": ["499"],
                "notes": "task668 is now the clean third natural overextend row; task580 remains a multi-issue special-review reserve rather than a canonical exemplar.",
            },
            "underextend": {
                "reserve_task_ids": ["579", "665", "712"],
                "notes": "task665 is the newly added underextend natural candidate; underextend remains a formal extension family and does not enter the default main 12 traps.",
            },
        },
        "natural_trap_binding_ready": natural_trap_binding_ready,
        "selection_ready": selection_ready,
        "semi_binding_ready": selection_ready,
        "natural_missing_gold_task_ids": [],
        "natural_scope_mismatch_task_ids": [],
        "natural_geometry_not_ready_task_ids": [],
        "blocked_reasons": []
        if selection_ready
        else [
            "some selected semi natural trap rows are missing from final gold, no longer in_scope, or not geometry-ready"
        ],
        "notes": [
            "This revision upgrades the third natural overextend row from task580 to task668.",
            "task580 is retained only as a special-review multi-issue reserve.",
            "task665 is recorded as a new underextend extension-family candidate.",
            "task475 remains a holdout fail candidate and does not re-enter active semi_audit_stress.",
        ],
    }


def build_stage1_audit_v6(inputs: dict[str, Any], semi_v10: dict[str, Any]) -> dict[str, Any]:
    audit_v5 = dict(inputs["stage1_audit_v5"])
    audit_v6 = json.loads(json.dumps(audit_v5, ensure_ascii=False))
    audit_v6["audit_name"] = "stage1_final_binding_audit_v6"
    audit_v6["semi_control_count"] = int(semi_v10["current_selected_control_count"])
    audit_v6["semi_trap_count"] = int(semi_v10["current_selected_trap_count"])
    audit_v6["semi_binding_ready"] = bool(semi_v10["semi_binding_ready"])
    audit_v6["selection_freeze_reused"] = False
    audit_v6["rebind_only_no_reselection"] = False
    audit_v6["prescreen_ready"] = (
        bool(audit_v6["manual_binding_ready"])
        and bool(audit_v6["semi_binding_ready"])
        and bool(audit_v6["oos_binding_ready"])
    )
    audit_v6["blocked_reasons"] = []
    audit_v6["notes"] = [
        "This audit reflects the latest verified export with task665 and task668 added to the semi candidate pool.",
        "task668 replaces task580 as the clean third natural overextend row in the main 12 traps.",
        "task580 remains reserve-only; task475 remains holdout-only.",
        "task560 remains audit-only in the OOS layer; although its directory family is 边界不可判定, the executable scope target continues to follow final gold as oos_geometry.",
    ]
    return audit_v6


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", default=f"analysis_results/{PHASE1_DIRNAME}")
    args = parser.parse_args()

    repo_root = _repo_root()
    inputs = load_inputs(repo_root)
    semi_v10 = build_semi_v10(inputs)
    audit_v6 = build_stage1_audit_v6(inputs, semi_v10)
    output_dir = repo_root / args.output_dir
    _write_json(output_dir / SEMI_V10_NAME, semi_v10)
    _write_json(output_dir / STAGE1_AUDIT_V6_NAME, audit_v6)


if __name__ == "__main__":
    main()
