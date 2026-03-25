from __future__ import annotations

import csv
import json
from pathlib import Path

from tools.rebind_stage1_to_final_gold import run


def _write_csv(path: Path, rows: list[dict[str, str]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def _setup_stage1_inputs(root: Path) -> None:
    phase1_dir = root / "analysis_results" / "phase1_progress_20260324"
    phase1_dir.mkdir(parents=True)

    manual_selection_v1 = {
        "manual_total_selected": 30,
        "expert_anchor_count": 22,
        "non_anchor_count": 8,
    }
    (phase1_dir / "prescreen_manual_final_selection_v1.json").write_text(
        json.dumps(manual_selection_v1, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    _write_csv(
        phase1_dir / "prescreen_manual_final_selection_v1.csv",
        [
            {
                "task_id": "470",
                "base_task_id": "manual_base_470",
                "keep": "True",
                "final_role": "expert_anchor",
            }
        ],
        ["task_id", "base_task_id", "keep", "final_role"],
    )
    (phase1_dir / "prescreen_manual_binding_audit_v1.json").write_text(
        json.dumps({"manual_binding_ready": False}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    semi_selection_v5 = {
        "target_total": 18,
        "control_target": 6,
        "trap_target": 12,
        "current_selected_control_count": 6,
        "current_selected_trap_count": 12,
        "family_allocations": [],
        "extension_family_notes": [],
        "selected_control_rows": [
            {
                "task_id": "492",
                "base_task_id": "semi_control_492",
                "final_role": "control",
            }
        ],
        "selected_trap_rows": [
            {
                "task_id": "493",
                "base_task_id": "semi_natural_493",
                "family": "overextend_adjacent",
                "source_type": "trap_natural",
            },
            {
                "candidate_id": "synthetic_001",
                "base_task_id": "semi_synth_001",
                "family": "corner_drift",
                "source_type": "trap_synthetic_disjoint_source",
            },
        ],
    }
    (phase1_dir / "prescreen_semi_final_selection_v5.json").write_text(
        json.dumps(semi_selection_v5, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    oos_binding_v1 = {
        "oos_total_pool_count": 10,
        "final_oos_gate_count": 9,
        "audit_only_count": 1,
        "low_priority_audit_only_task_ids": ["560"],
        "scope_breakdown_in_final_gate": {"oos_split_level": 1},
        "selected_oos_gate_rows": [
            {
                "task_id": "459",
                "base_task_id": "oos_base_459",
                "scope": "oos_open_boundary",
                "final_role": "oos_gate",
            }
        ],
    }
    (phase1_dir / "oos_final_quota_binding_v1.json").write_text(
        json.dumps(oos_binding_v1, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    (phase1_dir / "stage1_final_binding_audit_v1.json").write_text(
        json.dumps({"prescreen_ready": False}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def test_run_rebind_stage1_to_final_gold_marks_ready_when_gold_rows_cover_all(tmp_path: Path) -> None:
    _setup_stage1_inputs(tmp_path)
    final_gold = tmp_path / "final_gold.jsonl"
    final_gold.write_text(
        "\n".join(
            [
                json.dumps(
                    {
                        "task_id": "470",
                        "base_task_id": "manual_base_470",
                        "final_scope_alias": "normal",
                        "final_scope_binary": "in_scope",
                        "geometry_gold_ready": True,
                        "scope_gold_ready": True,
                        "adjudication_status": "final_adjudicated_gold",
                    },
                    ensure_ascii=False,
                ),
                json.dumps(
                    {
                        "task_id": "492",
                        "base_task_id": "semi_control_492",
                        "final_scope_alias": "normal",
                        "final_scope_binary": "in_scope",
                        "geometry_gold_ready": True,
                        "scope_gold_ready": True,
                        "adjudication_status": "final_adjudicated_gold",
                    },
                    ensure_ascii=False,
                ),
                json.dumps(
                    {
                        "task_id": "493",
                        "base_task_id": "semi_natural_493",
                        "final_scope_alias": "normal",
                        "final_scope_binary": "in_scope",
                        "geometry_gold_ready": True,
                        "scope_gold_ready": True,
                        "adjudication_status": "final_adjudicated_gold",
                    },
                    ensure_ascii=False,
                ),
                json.dumps(
                    {
                        "task_id": "459",
                        "base_task_id": "oos_base_459",
                        "final_scope_alias": "oos_open_boundary",
                        "final_scope_binary": "oos",
                        "geometry_gold_ready": False,
                        "scope_gold_ready": True,
                        "adjudication_status": "final_adjudicated_gold",
                    },
                    ensure_ascii=False,
                ),
            ]
        ),
        encoding="utf-8",
    )

    outputs = run(final_gold_path=final_gold, output_dir=tmp_path / "out", root=tmp_path)

    manual_v2 = json.loads(outputs["manual_binding_v2"].read_text(encoding="utf-8"))
    semi_v6 = json.loads(outputs["semi_selection_v6"].read_text(encoding="utf-8"))
    oos_v2 = json.loads(outputs["oos_binding_v2"].read_text(encoding="utf-8"))
    stage1_v2 = json.loads(outputs["stage1_audit_v2"].read_text(encoding="utf-8"))

    assert manual_v2["manual_binding_ready"] is True
    assert semi_v6["semi_binding_ready"] is True
    assert oos_v2["oos_binding_ready"] is True
    assert stage1_v2["prescreen_ready"] is True


def test_run_rebind_stage1_to_final_gold_blocks_when_manual_gold_missing(tmp_path: Path) -> None:
    _setup_stage1_inputs(tmp_path)
    final_gold = tmp_path / "final_gold.jsonl"
    final_gold.write_text(
        "\n".join(
            [
                json.dumps(
                    {
                        "task_id": "492",
                        "base_task_id": "semi_control_492",
                        "final_scope_alias": "normal",
                        "final_scope_binary": "in_scope",
                        "geometry_gold_ready": True,
                        "scope_gold_ready": True,
                        "adjudication_status": "final_adjudicated_gold",
                    },
                    ensure_ascii=False,
                ),
                json.dumps(
                    {
                        "task_id": "493",
                        "base_task_id": "semi_natural_493",
                        "final_scope_alias": "normal",
                        "final_scope_binary": "in_scope",
                        "geometry_gold_ready": True,
                        "scope_gold_ready": True,
                        "adjudication_status": "final_adjudicated_gold",
                    },
                    ensure_ascii=False,
                ),
                json.dumps(
                    {
                        "task_id": "459",
                        "base_task_id": "oos_base_459",
                        "final_scope_alias": "oos_open_boundary",
                        "final_scope_binary": "oos",
                        "geometry_gold_ready": False,
                        "scope_gold_ready": True,
                        "adjudication_status": "final_adjudicated_gold",
                    },
                    ensure_ascii=False,
                ),
            ]
        ),
        encoding="utf-8",
    )

    outputs = run(final_gold_path=final_gold, output_dir=tmp_path / "out", root=tmp_path)

    manual_v2 = json.loads(outputs["manual_binding_v2"].read_text(encoding="utf-8"))
    stage1_v2 = json.loads(outputs["stage1_audit_v2"].read_text(encoding="utf-8"))

    assert manual_v2["manual_binding_ready"] is False
    assert manual_v2["missing_gold_task_ids"] == ["470"]
    assert stage1_v2["prescreen_ready"] is False
