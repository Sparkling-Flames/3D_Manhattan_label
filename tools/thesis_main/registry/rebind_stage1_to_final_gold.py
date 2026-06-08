from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any


PHASE1_DIRNAME = "phase1_progress_20260324"
TRUTH_LAYER_DIRNAME = "truth_layer_extraction_20260324"
REQUIRED_GOLD_STATUS = "final_adjudicated_gold"


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


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


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _is_true(value: Any) -> bool:
    return str(value).strip().lower() == "true"


def _sorted_task_ids(values: list[str] | set[str]) -> list[str]:
    return sorted({str(value) for value in values}, key=lambda value: int(value))


def _load_gold_rows(path: Path) -> list[dict[str, Any]]:
    suffix = path.suffix.lower()
    if suffix == ".csv":
        return _read_csv(path)
    if suffix == ".jsonl":
        return _read_jsonl(path)
    raise ValueError(f"Unsupported final gold format: {path}")


def _normalize_gold_record(row: dict[str, Any]) -> dict[str, Any]:
    task_id = str(row.get("task_id", "")).strip()
    base_task_id = str(row.get("base_task_id", "")).strip()
    family_dir = str(row.get("family_dir", "")).strip()
    priority_flag = str(row.get("priority_flag", "")).strip()
    final_scope_alias = str(row.get("final_scope_alias", row.get("scope", ""))).strip()
    final_scope_binary = str(row.get("final_scope_binary", "")).strip()
    adjudication_status = str(row.get("adjudication_status", "")).strip()
    geometry_gold_ready = _is_true(row.get("geometry_gold_ready", False))
    scope_gold_ready = _is_true(row.get("scope_gold_ready", False))
    notes = str(row.get("notes", "")).strip()

    if not task_id:
        raise ValueError("Final gold row missing task_id")
    if not final_scope_alias:
        raise ValueError(f"Final gold row missing final_scope_alias for task {task_id}")
    if final_scope_binary not in {"in_scope", "oos"}:
        raise ValueError(
            f"Final gold row has invalid final_scope_binary for task {task_id}: {final_scope_binary!r}"
        )
    if adjudication_status != REQUIRED_GOLD_STATUS:
        raise ValueError(
            f"Final gold row has invalid adjudication_status for task {task_id}: {adjudication_status!r}"
        )

    return {
        "task_id": task_id,
        "base_task_id": base_task_id,
        "family_dir": family_dir,
        "priority_flag": priority_flag,
        "final_scope_alias": final_scope_alias,
        "final_scope_binary": final_scope_binary,
        "geometry_gold_ready": geometry_gold_ready,
        "scope_gold_ready": scope_gold_ready,
        "adjudication_status": adjudication_status,
        "notes": notes,
    }


def load_current_stage1_state(root: Path | None = None) -> dict[str, Any]:
    repo_root = root or _repo_root()
    phase1_dir = repo_root / "analysis_results" / PHASE1_DIRNAME
    return {
        "repo_root": repo_root,
        "manual_selection_v1": _read_json(phase1_dir / "prescreen_manual_final_selection_v1.json"),
        "manual_selection_rows_v1": _read_csv(phase1_dir / "prescreen_manual_final_selection_v1.csv"),
        "manual_binding_audit_v1": _read_json(phase1_dir / "prescreen_manual_binding_audit_v1.json"),
        "semi_selection_v5": _read_json(phase1_dir / "prescreen_semi_final_selection_v5.json"),
        "oos_binding_v1": _read_json(phase1_dir / "oos_final_quota_binding_v1.json"),
        "stage1_audit_v1": _read_json(phase1_dir / "stage1_final_binding_audit_v1.json"),
    }


def build_manual_binding_v2(
    manual_selection_v1: dict[str, Any],
    manual_selection_rows_v1: list[dict[str, str]],
    gold_by_task: dict[str, dict[str, Any]],
    final_gold_path: Path,
) -> dict[str, Any]:
    checked_rows: list[dict[str, Any]] = []
    missing_gold_task_ids: list[str] = []
    scope_mismatch_task_ids: list[str] = []
    geometry_not_ready_task_ids: list[str] = []

    for row in manual_selection_rows_v1:
        if not _is_true(row.get("keep")):
            continue
        task_id = str(row["task_id"])
        gold = gold_by_task.get(task_id)
        rebind_status = "ready"
        reason = ""
        if gold is None:
            missing_gold_task_ids.append(task_id)
            rebind_status = "missing_gold_row"
            reason = "Final gold export does not contain this selected manual task."
        elif gold["final_scope_binary"] != "in_scope":
            scope_mismatch_task_ids.append(task_id)
            rebind_status = "scope_mismatch"
            reason = "Final gold scope no longer supports this manual row as in-scope geometry."
        elif not gold["geometry_gold_ready"]:
            geometry_not_ready_task_ids.append(task_id)
            rebind_status = "geometry_not_ready"
            reason = "Final gold exists, but geometry reference is not marked ready."

        checked_rows.append(
            {
                "task_id": task_id,
                "base_task_id": row["base_task_id"],
                "final_role": row["final_role"],
                "gold_scope_alias": gold["final_scope_alias"] if gold else "",
                "rebind_status": rebind_status,
                "rebind_reason": reason,
            }
        )

    manual_binding_ready = not (
        missing_gold_task_ids or scope_mismatch_task_ids or geometry_not_ready_task_ids
    )

    return {
        "audit_name": "manual_binding_audit_v2",
        "rebind_source": str(final_gold_path),
        "truth_layer_dir": TRUTH_LAYER_DIRNAME,
        "reference_binding_status": "final_adjudicated_gold_rebound",
        "adjudication_status": REQUIRED_GOLD_STATUS,
        "manual_total_selected": manual_selection_v1["manual_total_selected"],
        "expert_anchor_count": manual_selection_v1["expert_anchor_count"],
        "non_anchor_count": manual_selection_v1["non_anchor_count"],
        "checked_rows": checked_rows,
        "missing_gold_task_ids": _sorted_task_ids(missing_gold_task_ids),
        "scope_mismatch_task_ids": _sorted_task_ids(scope_mismatch_task_ids),
        "geometry_not_ready_task_ids": _sorted_task_ids(geometry_not_ready_task_ids),
        "manual_selection_frozen": True,
        "manual_binding_ready": manual_binding_ready,
        "blocked_reasons": []
        if manual_binding_ready
        else [
            "some selected manual rows are missing from final gold, no longer in_scope, or not geometry-ready"
        ],
        "notes": [
            "This artifact rebinds the already-frozen manual selection to final adjudicated gold.",
            "It does not redesign the 22/8 split unless final gold invalidates some selected rows."
        ],
    }


def build_semi_selection_v6(
    semi_selection_v5: dict[str, Any],
    gold_by_task: dict[str, dict[str, Any]],
    final_gold_path: Path,
) -> dict[str, Any]:
    control_rows = semi_selection_v5["selected_control_rows"]
    natural_rows = [
        row for row in semi_selection_v5["selected_trap_rows"] if row.get("source_type") == "trap_natural"
    ]
    synthetic_rows = [
        row
        for row in semi_selection_v5["selected_trap_rows"]
        if row.get("source_type") == "trap_synthetic_disjoint_source"
    ]

    control_missing: list[str] = []
    control_scope_mismatch: list[str] = []
    control_geometry_not_ready: list[str] = []
    rebound_control_rows: list[dict[str, Any]] = []
    for row in control_rows:
        task_id = str(row["task_id"])
        gold = gold_by_task.get(task_id)
        rebind_status = "ready"
        reason = ""
        if gold is None:
            control_missing.append(task_id)
            rebind_status = "missing_gold_row"
            reason = "Final gold export does not contain this selected control task."
        elif gold["final_scope_binary"] != "in_scope":
            control_scope_mismatch.append(task_id)
            rebind_status = "scope_mismatch"
            reason = "Final gold scope no longer supports this control row as in-scope."
        elif not gold["geometry_gold_ready"]:
            control_geometry_not_ready.append(task_id)
            rebind_status = "geometry_not_ready"
            reason = "Final gold exists, but control geometry reference is not marked ready."
        rebound_control_rows.append(
            {
                **row,
                "gold_scope_alias": gold["final_scope_alias"] if gold else "",
                "rebind_status": rebind_status,
                "rebind_reason": reason,
            }
        )

    natural_missing: list[str] = []
    natural_scope_mismatch: list[str] = []
    natural_geometry_not_ready: list[str] = []
    rebound_natural_rows: list[dict[str, Any]] = []
    for row in natural_rows:
        task_id = str(row["task_id"])
        gold = gold_by_task.get(task_id)
        rebind_status = "ready"
        reason = ""
        if gold is None:
            natural_missing.append(task_id)
            rebind_status = "missing_gold_row"
            reason = "Final gold export does not contain this selected natural trap task."
        elif gold["final_scope_binary"] != "in_scope":
            natural_scope_mismatch.append(task_id)
            rebind_status = "scope_mismatch"
            reason = "Final gold scope no longer supports this natural trap as in-scope."
        elif not gold["geometry_gold_ready"]:
            natural_geometry_not_ready.append(task_id)
            rebind_status = "geometry_not_ready"
            reason = "Final gold exists, but natural trap geometry reference is not marked ready."
        rebound_natural_rows.append(
            {
                **row,
                "gold_scope_alias": gold["final_scope_alias"] if gold else "",
                "rebind_status": rebind_status,
                "rebind_reason": reason,
            }
        )

    carried_synthetic_rows = [
        {
            **row,
            "rebind_status": "carry_forward_frozen_synthetic_asset",
            "rebind_reason": "Synthetic trap rows remain freeze-layer assets and are carried forward from the current selected synthetic bank.",
        }
        for row in synthetic_rows
    ]

    control_binding_ready = not (
        control_missing or control_scope_mismatch or control_geometry_not_ready
    )
    natural_binding_ready = not (
        natural_missing or natural_scope_mismatch or natural_geometry_not_ready
    )
    synthetic_asset_ready = True
    semi_binding_ready = control_binding_ready and natural_binding_ready and synthetic_asset_ready

    selected_trap_rows_v6 = rebound_natural_rows + carried_synthetic_rows

    return {
        "selection_name": "prescreen_semi_final_selection_v6",
        "rebind_source": str(final_gold_path),
        "truth_layer_dir": TRUTH_LAYER_DIRNAME,
        "reference_binding_status": "final_adjudicated_gold_rebound",
        "adjudication_status": REQUIRED_GOLD_STATUS,
        "target_total": semi_selection_v5["target_total"],
        "control_target": semi_selection_v5["control_target"],
        "trap_target": semi_selection_v5["trap_target"],
        "selected_control_rows": rebound_control_rows,
        "selected_trap_rows": selected_trap_rows_v6,
        "current_selected_control_count": semi_selection_v5["current_selected_control_count"],
        "current_selected_trap_count": semi_selection_v5["current_selected_trap_count"],
        "family_allocations": semi_selection_v5["family_allocations"],
        "extension_family_notes": semi_selection_v5.get("extension_family_notes", []),
        "control_binding_ready": control_binding_ready,
        "natural_trap_binding_ready": natural_binding_ready,
        "synthetic_asset_ready": synthetic_asset_ready,
        "selection_ready": True,
        "semi_binding_ready": semi_binding_ready,
        "control_missing_gold_task_ids": _sorted_task_ids(control_missing),
        "control_scope_mismatch_task_ids": _sorted_task_ids(control_scope_mismatch),
        "control_geometry_not_ready_task_ids": _sorted_task_ids(control_geometry_not_ready),
        "natural_missing_gold_task_ids": _sorted_task_ids(natural_missing),
        "natural_scope_mismatch_task_ids": _sorted_task_ids(natural_scope_mismatch),
        "natural_geometry_not_ready_task_ids": _sorted_task_ids(natural_geometry_not_ready),
        "blocked_reasons": []
        if semi_binding_ready
        else [
            "some selected semi control or natural trap rows are missing from final gold, no longer in_scope, or not geometry-ready"
        ],
        "notes": [
            "This artifact rebinds only the final-gold-dependent parts of the existing semi freeze.",
            "Synthetic trap rows are carried forward as frozen synthetic assets rather than looked up in the latest export."
        ],
    }


def build_oos_binding_v2(
    oos_binding_v1: dict[str, Any],
    gold_by_task: dict[str, dict[str, Any]],
    final_gold_path: Path,
) -> dict[str, Any]:
    rebound_rows: list[dict[str, Any]] = []
    audit_only_rows: list[dict[str, Any]] = []
    missing_gold_task_ids: list[str] = []
    scope_mismatch_task_ids: list[str] = []
    scope_not_ready_task_ids: list[str] = []

    for row in oos_binding_v1["selected_oos_gate_rows"]:
        task_id = str(row["task_id"])
        gold = gold_by_task.get(task_id)
        rebind_status = "ready"
        reason = ""
        if gold is None:
            missing_gold_task_ids.append(task_id)
            rebind_status = "missing_gold_row"
            reason = "Final gold export does not contain this selected OOS gate task."
        elif gold["final_scope_binary"] != "oos":
            scope_mismatch_task_ids.append(task_id)
            rebind_status = "scope_mismatch"
            reason = "Final gold scope no longer supports this row as OOS."
        elif not gold["scope_gold_ready"]:
            scope_not_ready_task_ids.append(task_id)
            rebind_status = "scope_not_ready"
            reason = "Final gold exists, but OOS scope adjudication is not marked ready."
        rebound_rows.append(
            {
                **row,
                "directory_family": gold["family_dir"] if gold else "",
                "gold_scope_alias": gold["final_scope_alias"] if gold else "",
                "rebind_status": rebind_status,
                "rebind_reason": reason,
            }
        )

    for task_id in oos_binding_v1["low_priority_audit_only_task_ids"]:
        task_id = str(task_id)
        gold = gold_by_task.get(task_id)
        audit_only_rows.append(
            {
                "task_id": task_id,
                "base_task_id": gold["base_task_id"] if gold else "",
                "directory_family": gold["family_dir"] if gold else "",
                "gold_scope_alias": gold["final_scope_alias"] if gold else "",
                "priority_flag": gold["priority_flag"] if gold else "unknown",
                "final_role": "audit_only",
                "rebind_status": "ready" if gold and gold["final_scope_binary"] == "oos" else "scope_mismatch",
            }
        )

    oos_binding_ready = not (
        missing_gold_task_ids or scope_mismatch_task_ids or scope_not_ready_task_ids
    )

    return {
        "binding_name": "oos_final_quota_binding_v2",
        "rebind_source": str(final_gold_path),
        "truth_layer_dir": TRUTH_LAYER_DIRNAME,
        "reference_binding_status": "final_adjudicated_gold_rebound",
        "adjudication_status": REQUIRED_GOLD_STATUS,
        "oos_total_pool_count": oos_binding_v1["oos_total_pool_count"],
        "final_oos_gate_count": oos_binding_v1["final_oos_gate_count"],
        "audit_only_count": oos_binding_v1["audit_only_count"],
        "selected_oos_gate_rows": rebound_rows,
        "low_priority_audit_only_task_ids": oos_binding_v1["low_priority_audit_only_task_ids"],
        "low_priority_audit_only_rows": audit_only_rows,
        "scope_breakdown_in_final_gate": oos_binding_v1["scope_breakdown_in_final_gate"],
        "oos_selection_frozen": True,
        "oos_selection_ready": True,
        "oos_binding_ready": oos_binding_ready,
        "missing_gold_task_ids": _sorted_task_ids(missing_gold_task_ids),
        "scope_mismatch_task_ids": _sorted_task_ids(scope_mismatch_task_ids),
        "scope_not_ready_task_ids": _sorted_task_ids(scope_not_ready_task_ids),
        "blocked_reasons": []
        if oos_binding_ready
        else ["some selected OOS gate rows are missing from final gold, no longer OOS, or not scope-ready"],
        "notes": [
            "This artifact rebinds the existing OOS gate freeze to final adjudicated scope truth.",
            "Low-priority audit-only OOS rows remain outside the executable gate unless manually promoted later.",
            "Directory family and final adjudicated OOS subtype may diverge for isolated rows such as task560; executable imports follow final gold scope rather than folder name.",
        ],
    }


def build_stage1_binding_audit_v2(
    manual_binding_v2: dict[str, Any],
    semi_selection_v6: dict[str, Any],
    oos_binding_v2: dict[str, Any],
) -> dict[str, Any]:
    prescreen_ready = (
        manual_binding_v2["manual_binding_ready"]
        and semi_selection_v6["semi_binding_ready"]
        and oos_binding_v2["oos_binding_ready"]
    )

    blocked_reasons: list[str] = []
    for payload in (manual_binding_v2, semi_selection_v6, oos_binding_v2):
        for reason in payload.get("blocked_reasons", []):
            if reason not in blocked_reasons:
                blocked_reasons.append(reason)

    return {
        "audit_name": "stage1_final_binding_audit_v2",
        "truth_layer_dir": TRUTH_LAYER_DIRNAME,
        "reference_binding_status": "final_adjudicated_gold_rebound",
        "adjudication_status": REQUIRED_GOLD_STATUS,
        "manual_binding_ready": manual_binding_v2["manual_binding_ready"],
        "semi_binding_ready": semi_selection_v6["semi_binding_ready"],
        "oos_binding_ready": oos_binding_v2["oos_binding_ready"],
        "manual_expert_anchor_count": manual_binding_v2["expert_anchor_count"],
        "manual_non_anchor_count": manual_binding_v2["non_anchor_count"],
        "semi_control_count": semi_selection_v6["current_selected_control_count"],
        "semi_trap_count": semi_selection_v6["current_selected_trap_count"],
        "oos_final_gate_count": oos_binding_v2["final_oos_gate_count"],
        "selection_freeze_reused": True,
        "rebind_only_no_reselection": True,
        "prescreen_ready": prescreen_ready,
        "blocked_reasons": blocked_reasons,
        "notes": [
            "This audit only rebinds the existing frozen selection manifests to final gold.",
            "If any selected rows fail final-gold rebinding, the next step is minimal replacement rather than redesign."
        ],
    }


def run(final_gold_path: Path, output_dir: Path | None = None, root: Path | None = None) -> dict[str, Path]:
    state = load_current_stage1_state(root=root)
    repo_root = state["repo_root"]
    final_output_dir = output_dir or (repo_root / "analysis_results" / PHASE1_DIRNAME)

    gold_rows = [_normalize_gold_record(row) for row in _load_gold_rows(final_gold_path)]
    gold_by_task = {row["task_id"]: row for row in gold_rows}

    manual_binding_v2 = build_manual_binding_v2(
        state["manual_selection_v1"],
        state["manual_selection_rows_v1"],
        gold_by_task,
        final_gold_path,
    )
    semi_selection_v6 = build_semi_selection_v6(
        state["semi_selection_v5"],
        gold_by_task,
        final_gold_path,
    )
    oos_binding_v2 = build_oos_binding_v2(
        state["oos_binding_v1"],
        gold_by_task,
        final_gold_path,
    )
    stage1_audit_v2 = build_stage1_binding_audit_v2(
        manual_binding_v2,
        semi_selection_v6,
        oos_binding_v2,
    )

    outputs = {
        "manual_binding_v2": final_output_dir / "manual_binding_audit_v2.json",
        "semi_selection_v6": final_output_dir / "prescreen_semi_final_selection_v6.json",
        "oos_binding_v2": final_output_dir / "oos_final_quota_binding_v2.json",
        "stage1_audit_v2": final_output_dir / "stage1_final_binding_audit_v2.json",
    }
    _write_json(outputs["manual_binding_v2"], manual_binding_v2)
    _write_json(outputs["semi_selection_v6"], semi_selection_v6)
    _write_json(outputs["oos_binding_v2"], oos_binding_v2)
    _write_json(outputs["stage1_audit_v2"], stage1_audit_v2)
    return outputs


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Rebind frozen Stage 1 selections to a final adjudicated gold layer."
    )
    parser.add_argument("--final-gold", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, default=None)
    args = parser.parse_args()
    outputs = run(final_gold_path=args.final_gold, output_dir=args.output_dir)
    print(json.dumps({key: str(value) for key, value in outputs.items()}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
