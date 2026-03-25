from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any


TRUTH_LAYER_DIRNAME = "truth_layer_extraction_20260324"
PHASE1_DIRNAME = "phase1_progress_20260324"

SCOPE_CSV_FIELDS = [
    "task_id",
    "base_task_id",
    "bucket_dir",
    "family_dir",
    "priority_annotation",
    "priority_flag",
    "recommended_role",
    "review_note_flag",
    "default_eligible",
    "scope",
    "scope_binary",
    "geometry_truth_source",
    "adjudication_status",
]


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


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


def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")


def _write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fieldnames})


def _sorted_task_ids(values: list[str] | set[str]) -> list[str]:
    return sorted({str(value) for value in values}, key=lambda value: int(value))


def load_inputs(root: Path | None = None) -> dict[str, Any]:
    repo_root = root or _repo_root()
    truth_dir = repo_root / "analysis_results" / TRUTH_LAYER_DIRNAME
    phase1_dir = repo_root / "analysis_results" / PHASE1_DIRNAME
    return {
        "repo_root": repo_root,
        "truth_summary": _read_json(truth_dir / "truth_layer_extraction_summary_v1.json"),
        "annotation_records": _read_jsonl(truth_dir / "manual_annotation_records_v1.jsonl"),
        "manual_binding_audit_v1": _read_json(phase1_dir / "prescreen_manual_binding_audit_v1.json"),
        "manual_selection_v1": _read_json(phase1_dir / "prescreen_manual_final_selection_v1.json"),
        "semi_selection_v5": _read_json(phase1_dir / "prescreen_semi_final_selection_v5.json"),
        "oos_binding_v1": _read_json(phase1_dir / "oos_final_quota_binding_v1.json"),
        "stage1_audit_v1": _read_json(phase1_dir / "stage1_final_binding_audit_v1.json"),
    }


def build_trap_corner_records(annotation_records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for row in annotation_records:
        rows.append(
            {
                "task_id": row["task_id"],
                "base_task_id": row["base_task_id"],
                "bucket_dir": row["bucket_dir"],
                "family_dir": row["family_dir"],
                "priority_annotation": row["priority_annotation"],
                "priority_flag": row["priority_flag"],
                "recommended_role": row["recommended_role"],
                "review_note_flag": row["review_note_flag"],
                "default_eligible": row["default_eligible"],
                "scope": row["scope"],
                "scope_binary": row["scope_binary"],
                "canonical_corners_norm": row["canonical_corners_norm"],
                "runtime_pairs_1024x512": row["runtime_pairs_1024x512"],
                "n_corners": row["n_corners"],
                "pair_coverage": row["pair_coverage"],
                "geometry_truth_source": row["geometry_truth_source"],
                "adjudication_status": row["adjudication_status"],
                "export_snapshot": row["export_snapshot"],
            }
        )
    return rows


def build_trap_scope_records(annotation_records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for row in annotation_records:
        rows.append(
            {
                "task_id": row["task_id"],
                "base_task_id": row["base_task_id"],
                "bucket_dir": row["bucket_dir"],
                "family_dir": row["family_dir"],
                "priority_annotation": row["priority_annotation"],
                "priority_flag": row["priority_flag"],
                "recommended_role": row["recommended_role"],
                "review_note_flag": row["review_note_flag"],
                "default_eligible": row["default_eligible"],
                "scope": row["scope"],
                "scope_binary": row["scope_binary"],
                "geometry_truth_source": row["geometry_truth_source"],
                "adjudication_status": row["adjudication_status"],
            }
        )
    return rows


def build_final_gold_preflight(
    truth_summary: dict[str, Any],
    annotation_records: list[dict[str, Any]],
    manual_selection_v1: dict[str, Any],
    manual_binding_audit_v1: dict[str, Any],
    semi_selection_v5: dict[str, Any],
    oos_binding_v1: dict[str, Any],
    stage1_audit_v1: dict[str, Any],
) -> dict[str, Any]:
    records_by_task = {str(row["task_id"]): row for row in annotation_records}

    manual_task_ids = set(manual_selection_v1["selected_expert_anchor_task_ids"]) | set(
        manual_selection_v1["selected_non_anchor_task_ids"]
    )
    semi_control_task_ids = {str(row["task_id"]) for row in semi_selection_v5["selected_control_rows"]}
    semi_natural_trap_task_ids = {
        str(row["task_id"])
        for row in semi_selection_v5["selected_trap_rows"]
        if row.get("source_type") == "trap_natural"
    }
    oos_gate_task_ids = {str(row["task_id"]) for row in oos_binding_v1["selected_oos_gate_rows"]}

    selected_task_ids = manual_task_ids | semi_control_task_ids | semi_natural_trap_task_ids | oos_gate_task_ids
    missing_selected_task_ids = _sorted_task_ids(
        [task_id for task_id in selected_task_ids if task_id not in records_by_task]
    )

    missing_scope_task_ids = _sorted_task_ids(
        [str(row["task_id"]) for row in annotation_records if not str(row.get("scope", "")).strip()]
    )
    missing_corner_task_ids = _sorted_task_ids(
        [str(row["task_id"]) for row in annotation_records if not row.get("canonical_corners_norm")]
    )

    synthetic_carry_forward_rows = [
        {
            "candidate_id": row["candidate_id"],
            "base_task_id": row["base_task_id"],
            "family": row["family"],
            "source_type": row["source_type"],
        }
        for row in semi_selection_v5["selected_trap_rows"]
        if row.get("source_type") == "trap_synthetic_disjoint_source"
    ]

    can_directly_run_rebinding_if_final_gold_matches_contract = (
        not missing_selected_task_ids and not missing_scope_task_ids and not missing_corner_task_ids
    )

    return {
        "check_name": "final_gold_preflight_check_v1",
        "truth_layer_dir": TRUTH_LAYER_DIRNAME,
        "reference_binding_status": truth_summary["summary_status"],
        "export_snapshot": truth_summary["export_snapshot"],
        "n_trap_records_total": len(annotation_records),
        "n_manual_records": truth_summary["n_manual"],
        "n_semi_records": truth_summary["n_semi"],
        "n_oos_records": truth_summary["n_oos"],
        "expected_final_gold_fields": [
            "task_id",
            "base_task_id",
            "final_scope_alias",
            "final_scope_binary",
            "geometry_gold_ready",
            "scope_gold_ready",
            "adjudication_status",
            "notes",
        ],
        "derived_split_outputs": {
            "trap_corner_records_v1": str(
                Path("analysis_results") / TRUTH_LAYER_DIRNAME / "trap_corner_records_v1.jsonl"
            ),
            "trap_scope_records_v1": str(
                Path("analysis_results") / TRUTH_LAYER_DIRNAME / "trap_scope_records_v1.csv"
            ),
        },
        "rebind_field_requirements": {
            "manual": [
                "task_id",
                "final_scope_alias",
                "final_scope_binary=in_scope",
                "geometry_gold_ready=true",
                "adjudication_status=final_adjudicated_gold",
            ],
            "semi_control": [
                "task_id",
                "final_scope_alias",
                "final_scope_binary=in_scope",
                "geometry_gold_ready=true",
                "adjudication_status=final_adjudicated_gold",
            ],
            "semi_natural_trap": [
                "task_id",
                "final_scope_alias",
                "final_scope_binary=in_scope",
                "geometry_gold_ready=true",
                "adjudication_status=final_adjudicated_gold",
            ],
            "oos_gate": [
                "task_id",
                "final_scope_alias",
                "final_scope_binary=oos",
                "scope_gold_ready=true",
                "adjudication_status=final_adjudicated_gold",
            ],
            "semi_synthetic_carry_forward": [
                "candidate_id",
                "base_task_id",
                "family",
                "source_type",
            ],
        },
        "manual_selection_snapshot": {
            "manual_total_selected": manual_selection_v1["manual_total_selected"],
            "expert_anchor_count": manual_selection_v1["expert_anchor_count"],
            "non_anchor_count": manual_selection_v1["non_anchor_count"],
            "manual_binding_ready": manual_binding_audit_v1["manual_binding_ready"],
            "selected_task_ids": _sorted_task_ids(manual_task_ids),
        },
        "semi_selection_snapshot": {
            "control_count": semi_selection_v5["current_selected_control_count"],
            "trap_count": semi_selection_v5["current_selected_trap_count"],
            "control_task_ids": _sorted_task_ids(semi_control_task_ids),
            "natural_trap_task_ids": _sorted_task_ids(semi_natural_trap_task_ids),
            "synthetic_carry_forward_rows": synthetic_carry_forward_rows,
        },
        "oos_selection_snapshot": {
            "final_oos_gate_count": oos_binding_v1["final_oos_gate_count"],
            "oos_gate_task_ids": _sorted_task_ids(oos_gate_task_ids),
            "low_priority_audit_only_task_ids": oos_binding_v1["low_priority_audit_only_task_ids"],
        },
        "task_alignment": {
            "selected_task_count_requiring_gold_rows": len(selected_task_ids),
            "missing_selected_task_ids_in_current_truth_layer": missing_selected_task_ids,
            "current_scope_missing_task_ids": missing_scope_task_ids,
            "current_corner_missing_task_ids": missing_corner_task_ids,
        },
        "status": {
            "stage1_selection_freeze_complete": stage1_audit_v1["selection_freeze_complete"],
            "prescreen_ready_currently": stage1_audit_v1["prescreen_ready"],
            "can_directly_run_rebinding_if_final_gold_matches_contract": can_directly_run_rebinding_if_final_gold_matches_contract,
            "preflight_status": "schema_ready_waiting_for_final_gold"
            if can_directly_run_rebinding_if_final_gold_matches_contract
            else "truth_layer_or_selection_manifest_needs_cleanup_before_rebinding",
        },
        "risk_items": []
        if can_directly_run_rebinding_if_final_gold_matches_contract
        else [
            "some selected rows are missing from the current truth-layer extraction, or current scope/corner extraction is incomplete"
        ],
        "notes": [
            "Current trap fine-annotation export has already been split into task-level corner and scope records.",
            "This preflight does not generate any v2 formal result; it only checks whether a future final-gold file can plug directly into the rebinding entrypoint."
        ],
    }


def run(output_dir: Path | None = None, root: Path | None = None) -> dict[str, Path]:
    inputs = load_inputs(root=root)
    repo_root = inputs["repo_root"]
    truth_dir = repo_root / "analysis_results" / TRUTH_LAYER_DIRNAME
    final_output_dir = output_dir or (repo_root / "analysis_results" / PHASE1_DIRNAME)

    corner_rows = build_trap_corner_records(inputs["annotation_records"])
    scope_rows = build_trap_scope_records(inputs["annotation_records"])
    preflight = build_final_gold_preflight(
        truth_summary=inputs["truth_summary"],
        annotation_records=inputs["annotation_records"],
        manual_selection_v1=inputs["manual_selection_v1"],
        manual_binding_audit_v1=inputs["manual_binding_audit_v1"],
        semi_selection_v5=inputs["semi_selection_v5"],
        oos_binding_v1=inputs["oos_binding_v1"],
        stage1_audit_v1=inputs["stage1_audit_v1"],
    )

    outputs = {
        "corner_records": truth_dir / "trap_corner_records_v1.jsonl",
        "scope_records": truth_dir / "trap_scope_records_v1.csv",
        "preflight": final_output_dir / "final_gold_preflight_check_v1.json",
    }
    _write_jsonl(outputs["corner_records"], corner_rows)
    _write_csv(outputs["scope_records"], scope_rows, SCOPE_CSV_FIELDS)
    _write_json(outputs["preflight"], preflight)
    return outputs


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Split trap corner/scope records and generate final-gold preflight checks."
    )
    parser.add_argument("--output-dir", type=Path, default=None)
    args = parser.parse_args()
    outputs = run(output_dir=args.output_dir)
    print(json.dumps({key: str(value) for key, value in outputs.items()}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
