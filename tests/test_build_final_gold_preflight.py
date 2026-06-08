from __future__ import annotations

import csv
import json
from pathlib import Path

from tools.thesis_main.registry.build_final_gold_preflight import run


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")


def _write_csv(path: Path, rows: list[dict], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def test_build_final_gold_preflight_outputs_split_records_and_summary(tmp_path: Path) -> None:
    repo_root = tmp_path
    truth_dir = repo_root / "analysis_results" / "truth_layer_extraction_20260324"
    phase1_dir = repo_root / "analysis_results" / "phase1_progress_20260324"

    _write_json(
        truth_dir / "truth_layer_extraction_summary_v1.json",
        {
            "export_snapshot": "project-20-latest.json",
            "n_manual": 1,
            "n_semi": 2,
            "n_oos": 1,
            "summary_status": "working_consensus_extraction_ready_not_final_gold",
        },
    )
    _write_jsonl(
        truth_dir / "manual_annotation_records_v1.jsonl",
        [
            {
                "task_id": "101",
                "base_task_id": "base-101",
                "bucket_dir": "manual",
                "family_dir": "遮挡明显",
                "priority_annotation": "",
                "priority_flag": "default",
                "recommended_role": "manual_anchor_candidate",
                "review_note_flag": False,
                "default_eligible": True,
                "scope": "normal",
                "scope_binary": "in_scope",
                "canonical_corners_norm": [{"id": 0, "x_pct": 10, "y_top_pct": 20, "y_bottom_pct": 80}],
                "runtime_pairs_1024x512": [{"x": 100, "y_ceiling": 100, "y_floor": 400}],
                "n_corners": 1,
                "pair_coverage": 1.0,
                "geometry_truth_source": "project20_kp",
                "adjudication_status": "working_consensus_not_final_gold",
                "export_snapshot": "project-20-latest.json",
            },
            {
                "task_id": "201",
                "base_task_id": "base-201",
                "bucket_dir": "semi",
                "family_dir": "模型标注质量好",
                "priority_annotation": "",
                "priority_flag": "default",
                "recommended_role": "semi_control_candidate",
                "review_note_flag": False,
                "default_eligible": True,
                "scope": "normal",
                "scope_binary": "in_scope",
                "canonical_corners_norm": [{"id": 0, "x_pct": 30, "y_top_pct": 20, "y_bottom_pct": 80}],
                "runtime_pairs_1024x512": [{"x": 300, "y_ceiling": 100, "y_floor": 400}],
                "n_corners": 1,
                "pair_coverage": 1.0,
                "geometry_truth_source": "project20_kp",
                "adjudication_status": "working_consensus_not_final_gold",
                "export_snapshot": "project-20-latest.json",
            },
            {
                "task_id": "202",
                "base_task_id": "base-202",
                "bucket_dir": "semi",
                "family_dir": "过度解析",
                "priority_annotation": "",
                "priority_flag": "default",
                "recommended_role": "semi_trap_natural",
                "review_note_flag": False,
                "default_eligible": True,
                "scope": "normal",
                "scope_binary": "in_scope",
                "canonical_corners_norm": [{"id": 0, "x_pct": 40, "y_top_pct": 25, "y_bottom_pct": 75}],
                "runtime_pairs_1024x512": [{"x": 400, "y_ceiling": 120, "y_floor": 380}],
                "n_corners": 1,
                "pair_coverage": 1.0,
                "geometry_truth_source": "project20_kp",
                "adjudication_status": "working_consensus_not_final_gold",
                "export_snapshot": "project-20-latest.json",
            },
            {
                "task_id": "301",
                "base_task_id": "base-301",
                "bucket_dir": "OOS",
                "family_dir": "边界不可判定",
                "priority_annotation": "",
                "priority_flag": "default",
                "recommended_role": "oos_gate_candidate",
                "review_note_flag": False,
                "default_eligible": True,
                "scope": "oos_open_boundary",
                "scope_binary": "oos",
                "canonical_corners_norm": [{"id": 0, "x_pct": 50, "y_top_pct": 10, "y_bottom_pct": 90}],
                "runtime_pairs_1024x512": [{"x": 500, "y_ceiling": 50, "y_floor": 460}],
                "n_corners": 1,
                "pair_coverage": 1.0,
                "geometry_truth_source": "project20_kp",
                "adjudication_status": "working_consensus_not_final_gold",
                "export_snapshot": "project-20-latest.json",
            },
        ],
    )
    _write_json(
        phase1_dir / "prescreen_manual_binding_audit_v1.json",
        {
            "manual_binding_ready": False,
        },
    )
    _write_json(
        phase1_dir / "prescreen_manual_final_selection_v1.json",
        {
            "manual_total_selected": 1,
            "expert_anchor_count": 1,
            "non_anchor_count": 0,
            "selected_expert_anchor_task_ids": ["101"],
            "selected_non_anchor_task_ids": [],
        },
    )
    _write_json(
        phase1_dir / "prescreen_semi_final_selection_v5.json",
        {
            "current_selected_control_count": 1,
            "current_selected_trap_count": 2,
            "selected_control_rows": [
                {"task_id": "201"},
            ],
            "selected_trap_rows": [
                {
                    "candidate_id": "natural_over_parsing_202",
                    "task_id": "202",
                    "base_task_id": "base-202",
                    "family": "over_parsing",
                    "source_type": "trap_natural",
                },
                {
                    "candidate_id": "synthetic_corner_drift_001",
                    "base_task_id": "base-synth-001",
                    "family": "corner_drift",
                    "source_type": "trap_synthetic_disjoint_source",
                },
            ],
        },
    )
    _write_json(
        phase1_dir / "oos_final_quota_binding_v1.json",
        {
            "final_oos_gate_count": 1,
            "selected_oos_gate_rows": [{"task_id": "301"}],
            "low_priority_audit_only_task_ids": [],
        },
    )
    _write_json(
        phase1_dir / "stage1_final_binding_audit_v1.json",
        {
            "selection_freeze_complete": True,
            "prescreen_ready": False,
        },
    )

    outputs = run(root=repo_root)

    assert outputs["corner_records"].exists()
    assert outputs["scope_records"].exists()
    assert outputs["preflight"].exists()

    corner_rows = [
        json.loads(line)
        for line in outputs["corner_records"].read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    assert len(corner_rows) == 4
    assert corner_rows[0]["recommended_role"] == "manual_anchor_candidate"

    with outputs["scope_records"].open("r", encoding="utf-8-sig", newline="") as handle:
        scope_rows = list(csv.DictReader(handle))
    assert len(scope_rows) == 4
    assert scope_rows[0]["default_eligible"] == "True"

    preflight = json.loads(outputs["preflight"].read_text(encoding="utf-8"))
    assert preflight["status"]["preflight_status"] == "schema_ready_waiting_for_final_gold"
    assert preflight["status"]["can_directly_run_rebinding_if_final_gold_matches_contract"] is True
    assert preflight["semi_selection_snapshot"]["synthetic_carry_forward_rows"] == [
        {
            "candidate_id": "synthetic_corner_drift_001",
            "base_task_id": "base-synth-001",
            "family": "corner_drift",
            "source_type": "trap_synthetic_disjoint_source",
        }
    ]
