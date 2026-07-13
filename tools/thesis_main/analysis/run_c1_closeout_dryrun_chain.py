from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

_PROJECT_ROOT = Path(__file__).resolve().parents[3]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from tools.thesis_main.analysis import c1_materialize_quality_table
from tools.thesis_main.analysis import c1_materialize_worker_profile_sidecar
from tools.thesis_main.analysis import c1_materialize_worker_state
from tools.thesis_main.analysis.c1_live_collection_monitor import safe, truthy, write_json
from tools.thesis_main.analysis.materialize_worker_scene_profile_candidates import materialize_worker_scene_profile_candidates
from tools.thesis_main.analysis.routing.evidence_snapshot import materialize_evidence_snapshot
from tools.thesis_main.analysis.routing.offline_replay_v2 import offline_replay_v2
from tools.thesis_main.analysis.vfinal_artifact_utils import sha256_file


def _blockers(summary: dict[str, Any]) -> list[str]:
    blockers: list[str] = []
    if summary["quality_table_blockers"]:
        blockers.append("quality_table_blockers")
    if summary["dt_backflow"]:
        blockers.append("dt_backflow")
    if not summary["profile_sidecar_generated"]:
        blockers.append("profile_sidecar_missing")
    if summary["profile_freeze_status"] != "C1_provisional":
        blockers.append("profile_freeze_status_not_C1_provisional")
    if not summary["artifacts_fresh"]:
        blockers.append("closeout_artifacts_missing_or_stale")
    if not summary["formal_inputs_present"]:
        blockers.append("formal_c1_annotation_data_missing")
    blockers.extend(["thesis_facing_closeout_blocked_pending_p1_integrity_review", "c2_decision_chain_blocked_pending_formal_closeout"])
    return blockers


def build_gate_summary(
    quality_table_summary: dict[str, Any],
    worker_state_summary: dict[str, Any],
    c2_gap_summary: dict[str, Any],
    c2_draft_summary: dict[str, Any],
    worker_profile_sidecar_summary: dict[str, Any],
    profile_summary_path: Path,
    vfinal_sidecar_summaries: dict[str, Any] | None = None,
    artifact_bundle: dict[str, Any] | None = None,
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
        "c2_direct_assignment": False,
        "reserve_only": False,
        "reserve_capacity_shortfall_count": 0,
        "profile_sidecar_generated": profile_generated,
        "profile_freeze_status": safe(worker_profile_sidecar_summary.get("profile_freeze_status")),
        "p1_descriptive_directional_check_status": safe(worker_profile_sidecar_summary.get("p1_descriptive_directional_check_status")) or "not_evaluable",
        "formal_predictive_validity_status": safe(worker_profile_sidecar_summary.get("formal_predictive_validity_status")) or "not_run_blocked",
        "p1_informed_diagnostic_profile_status": safe(worker_profile_sidecar_summary.get("p1_informed_diagnostic_profile_status")) or "incomplete",
        "full_profile_ready": truthy(worker_profile_sidecar_summary.get("full_profile_ready")),
        "full_diagnostic_profile_ready": truthy(worker_profile_sidecar_summary.get("full_diagnostic_profile_ready")),
        "p1_bundle_structurally_complete": truthy(worker_profile_sidecar_summary.get("p1_bundle_structurally_complete")),
        "pending_adjudication_count": int(worker_profile_sidecar_summary.get("pending_adjudication_count") or 0),
        "structural_contract_valid": bool(quality_table_summary.get("canonical_meta_fresh")) and not quality_table_summary.get("blockers"),
        "formal_inputs_present": False,
        "artifacts_fresh": bool(quality_table_summary.get("canonical_meta_fresh")),
        "dry_run_contract_exercised": True,
        "raw_pipeline_ready": False,
        "provisional_sidecar_ready": False,
        "formal_closeout_ready": False,
        "thesis_facing_closeout_ready": False,
        "c2_decision_chain_ready": False,
        "passed": False,
        "blocked_for_launch": True,
        "blockers": [],
        "warnings": list(worker_profile_sidecar_summary.get("warnings") or []),
        "passed_semantics": "provisional_pipeline_only_formal_closeout_and_c2_decisions_blocked",
        "vfinal_sidecars": vfinal_sidecar_summaries or {},
        "analysis_contract_ready": False,
        "formal_c1_annotation_data_present": False,
        "dry_run_is_formal_data": False,
        "closeout_input_bundle": artifact_bundle or {},
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
        f"- p1_descriptive_directional_check_status: {summary['p1_descriptive_directional_check_status']}",
        f"- formal_predictive_validity_status: {summary['formal_predictive_validity_status']}",
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
        f"- structural_contract_valid: {str(summary['structural_contract_valid']).lower()}",
        f"- formal_inputs_present: {str(summary['formal_inputs_present']).lower()}",
        f"- artifacts_fresh: {str(summary['artifacts_fresh']).lower()}",
        f"- dry_run_contract_exercised: {str(summary['dry_run_contract_exercised']).lower()}",
        f"- formal_closeout_ready: false",
        f"- thesis_facing_closeout_ready: false",
        f"- c2_decision_chain_ready: false",
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
    # C2 gap and assignment materialization are deliberately blocked until formal closeout.
    gap_summary = {"materialization_blocked": True, "direct_assignment": False}
    c2_summary = {"materialization_blocked": True, "reserve_only": False, "reserve_capacity_shortfall_count": 0}
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
    scene_summary = materialize_worker_scene_profile_candidates(
        output_dir / "worker_task_tag_observations_C1.csv",
        output_dir,
        geometry_loo_csv=output_dir / "geometry_worker_task_loo_C1.csv",
    )
    routing_snapshot_summary = materialize_evidence_snapshot(
        quality_csv,
        output_dir / "routing_evidence_snapshot_C1.csv",
    )
    scaffold_summary = offline_replay_v2(
        output_dir / "routing_evidence_snapshot_C1.csv",
        output_dir / "routing_replay_scaffold_C1.csv",
    )
    vfinal_sidecars = {
        "worker_scene_profile_candidates": scene_summary,
        "routing_evidence_snapshot": routing_snapshot_summary,
        "routing_replay_scaffold": scaffold_summary,
        "geometry_sidecars_present": (output_dir / "geometry_worker_task_loo_C1.csv").exists(),
        "formal_c1_annotation_data_present": False,
    }
    profile_summary_path = output_dir / "worker_profile_sidecar_C1.summary.json"
    bundle_paths = [canonical_csv, assignment_manifest, reserve_pool_csv, candidate_inventory_csv, output_dir / "c1_canonical_meta_observations.csv", quality_csv, output_dir / "task_tag_three_state_summary_C1.csv"]
    artifact_bundle = {"bundle_version": "c1_closeout_input_bundle_v1", "artifacts": [{"path": str(path), "exists": path.exists(), "sha256": sha256_file(path) if path.exists() else ""} for path in bundle_paths]}
    gate_summary = build_gate_summary(quality_summary, worker_summary, gap_summary, c2_summary, profile_summary, profile_summary_path, vfinal_sidecars, artifact_bundle)
    artifact_bundle["bundle_sha256"] = __import__("hashlib").sha256(json.dumps(artifact_bundle["artifacts"], sort_keys=True).encode("utf-8")).hexdigest()
    gate_summary["closeout_input_bundle"] = artifact_bundle
    (output_dir / "c1_closeout_input_bundle.json").write_text(json.dumps(artifact_bundle, ensure_ascii=False, indent=2), encoding="utf-8")
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
