from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

_PROJECT_ROOT = Path(__file__).resolve().parents[3]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from tools.thesis_main.analysis import build_c2_assignment_manifest_from_c1_gaps
from tools.thesis_main.analysis import c1_materialize_c2_gap_audits
from tools.thesis_main.analysis import c1_materialize_quality_table
from tools.thesis_main.analysis import c1_materialize_worker_profile_sidecar
from tools.thesis_main.analysis import c1_materialize_worker_state
from tools.thesis_main.analysis.c1_live_collection_monitor import safe, truthy, write_json


def _blockers(summary: dict[str, Any]) -> list[str]:
    blockers: list[str] = []
    if summary["quality_table_blockers"]:
        blockers.append("quality_table_blockers")
    if summary["dt_backflow"]:
        blockers.append("dt_backflow")
    if summary["c2_direct_assignment"]:
        blockers.append("c2_direct_assignment")
    if not summary["reserve_only"]:
        blockers.append("reserve_only_false")
    if summary["reserve_capacity_shortfall_count"] > 0:
        blockers.append("reserve_capacity_shortfall")
    if not summary["profile_sidecar_generated"]:
        blockers.append("profile_sidecar_missing")
    if summary["profile_freeze_status"] != "C1_provisional":
        blockers.append("profile_freeze_status_not_C1_provisional")
    return blockers


def build_gate_summary(
    quality_table_summary: dict[str, Any],
    worker_state_summary: dict[str, Any],
    c2_gap_summary: dict[str, Any],
    c2_draft_summary: dict[str, Any],
    worker_profile_sidecar_summary: dict[str, Any],
    profile_summary_path: Path,
) -> dict[str, Any]:
    profile_generated = profile_summary_path.exists() and bool(worker_profile_sidecar_summary)
    summary = {
        "quality_table_summary": quality_table_summary,
        "worker_state_summary": worker_state_summary,
        "c2_gap_summary": c2_gap_summary,
        "c2_draft_summary": c2_draft_summary,
        "worker_profile_sidecar_summary": worker_profile_sidecar_summary,
        "quality_table_blockers": list(quality_table_summary.get("blockers") or []),
        "r_u_estimated": truthy(quality_table_summary.get("r_u_estimated")) or truthy(worker_state_summary.get("r_u_estimated")) or truthy(worker_profile_sidecar_summary.get("r_u_calib_estimated")),
        "dt_backflow": truthy(quality_table_summary.get("dt_backflow")),
        "worker_state_provisional": truthy(worker_state_summary.get("provisional")),
        "c2_direct_assignment": truthy(c2_gap_summary.get("direct_assignment")),
        "reserve_only": truthy(c2_draft_summary.get("reserve_only")),
        "reserve_capacity_shortfall_count": int(c2_draft_summary.get("reserve_capacity_shortfall_count") or 0),
        "profile_sidecar_generated": profile_generated,
        "profile_freeze_status": safe(worker_profile_sidecar_summary.get("profile_freeze_status")),
        "p1_predictive_validity_status": safe(worker_profile_sidecar_summary.get("p1_predictive_validity_status")) or "not_evaluable",
        "p1_informed_diagnostic_profile_status": safe(worker_profile_sidecar_summary.get("p1_informed_diagnostic_profile_status")) or "incomplete",
        "full_profile_ready": truthy(worker_profile_sidecar_summary.get("full_profile_ready")),
        "pending_adjudication_count": int(worker_profile_sidecar_summary.get("pending_adjudication_count") or 0),
        "passed": True,
        "blocked_for_launch": False,
        "blockers": [],
        "warnings": list(worker_profile_sidecar_summary.get("warnings") or []),
        "passed_semantics": "dryrun_chain_structure_only_not_official_c1_closeout",
    }
    summary["blockers"] = _blockers(summary)
    summary["blocked_for_launch"] = bool(summary["blockers"])
    return summary


def write_markdown(path: Path, summary: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# C1 Closeout Dryrun Gate Summary",
        "",
        f"- passed: {str(summary['passed']).lower()}",
        f"- blocked_for_launch: {str(summary['blocked_for_launch']).lower()}",
        f"- passed_semantics: {summary['passed_semantics']}",
        f"- p1_predictive_validity_status: {summary['p1_predictive_validity_status']}",
        "",
        "## Gate Flags",
        f"- quality_table_blockers: {', '.join(summary['quality_table_blockers']) if summary['quality_table_blockers'] else 'none'}",
        f"- r_u_estimated: {str(summary['r_u_estimated']).lower()}",
        f"- dt_backflow: {str(summary['dt_backflow']).lower()}",
        f"- worker_state_provisional: {str(summary['worker_state_provisional']).lower()}",
        f"- c2_direct_assignment: {str(summary['c2_direct_assignment']).lower()}",
        f"- reserve_only: {str(summary['reserve_only']).lower()}",
        f"- reserve_capacity_shortfall_count: {summary['reserve_capacity_shortfall_count']}",
        f"- profile_sidecar_generated: {str(summary['profile_sidecar_generated']).lower()}",
        f"- profile_freeze_status: {summary['profile_freeze_status']}",
        "",
        "## Blockers",
        *(f"- {item}" for item in summary["blockers"]),
        "" if summary["blockers"] else "- none",
        "",
        "## Warnings",
        *(f"- {item}" for item in summary["warnings"]),
        "" if summary["warnings"] else "- none",
        "",
    ]
    path.write_text("\n".join(lines), encoding="utf-8")


def materialize(
    canonical_csv: Path,
    assignment_manifest: Path,
    reserve_pool_csv: Path,
    output_dir: Path,
    c2_output_dir: Path,
    candidate_inventory_csv: Path,
    min_r_u_tasks: int,
    min_scene_support: int,
    min_calib: int,
    epsilon_r: float,
    tasks_per_fill: int,
    p1_artifacts: list[Path] | None = None,
    p1_task_evidence_csv: Path | None = None,
    p1_worker_status_csv: Path | None = None,
    p1_geometry_task_scores: Path | None = None,
    p1_worker_geometry_profile: Path | None = None,
) -> dict[str, Any]:
    quality_summary = c1_materialize_quality_table.materialize(canonical_csv, output_dir, candidate_inventory_csv)
    quality_csv = output_dir / "c1_quality_annotations.csv"
    worker_summary = c1_materialize_worker_state.materialize(quality_csv, [assignment_manifest], output_dir, min_r_u_tasks)
    worker_state_csv = output_dir / "worker_state_snapshot_C1.csv"
    gap_summary = c1_materialize_c2_gap_audits.materialize(quality_csv, worker_state_csv, output_dir, min_scene_support, min_calib, epsilon_r)
    c2_summary = build_c2_assignment_manifest_from_c1_gaps.materialize(
        reserve_pool_csv,
        Path(gap_summary["ci_precision_audit_csv"]),
        Path(gap_summary["scene_coverage_gap_csv"]),
        c2_output_dir,
        tasks_per_fill,
    )
    profile_summary = c1_materialize_worker_profile_sidecar.materialize(
        quality_csv,
        worker_state_csv,
        output_dir,
        p1_artifacts,
        p1_task_evidence_csv,
        p1_worker_status_csv,
        p1_geometry_task_scores,
        p1_worker_geometry_profile,
    )
    profile_summary_path = output_dir / "worker_profile_sidecar_C1.summary.json"
    gate_summary = build_gate_summary(quality_summary, worker_summary, gap_summary, c2_summary, profile_summary, profile_summary_path)
    write_json(output_dir / "c1_closeout_dryrun_gate_summary.json", gate_summary)
    write_markdown(output_dir / "c1_closeout_dryrun_gate_summary.md", gate_summary)
    return gate_summary


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run C1 closeout dryrun materialization chain without official launch approval.")
    parser.add_argument("--canonical-csv", type=Path, required=True)
    parser.add_argument("--assignment-manifest", type=Path, required=True)
    parser.add_argument("--reserve-pool-csv", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--c2-output-dir", type=Path, required=True)
    parser.add_argument("--candidate-inventory-csv", type=Path, required=True)
    parser.add_argument("--min-r-u-tasks", type=int, required=True)
    parser.add_argument("--min-scene-support", type=int, required=True)
    parser.add_argument("--min-calib", type=int, required=True)
    parser.add_argument("--epsilon-r", type=float, required=True)
    parser.add_argument("--tasks-per-fill", type=int, required=True)
    parser.add_argument("--p1-artifact", type=Path, action="append", default=[])
    parser.add_argument("--p1-task-evidence-csv", type=Path)
    parser.add_argument("--p1-worker-status-csv", type=Path)
    parser.add_argument("--p1-geometry-task-scores", type=Path)
    parser.add_argument("--p1-worker-geometry-profile", type=Path)
    args = parser.parse_args(argv)
    summary = materialize(
        args.canonical_csv,
        args.assignment_manifest,
        args.reserve_pool_csv,
        args.output_dir,
        args.c2_output_dir,
        args.candidate_inventory_csv,
        args.min_r_u_tasks,
        args.min_scene_support,
        args.min_calib,
        args.epsilon_r,
        args.tasks_per_fill,
        args.p1_artifact,
        args.p1_task_evidence_csv,
        args.p1_worker_status_csv,
        args.p1_geometry_task_scores,
        args.p1_worker_geometry_profile,
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
