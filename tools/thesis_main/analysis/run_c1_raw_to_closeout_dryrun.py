from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

_PROJECT_ROOT = Path(__file__).resolve().parents[3]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from tools.thesis_main.analysis import c1_canonicalize_exports
from tools.thesis_main.analysis import run_c1_closeout_dryrun_chain
from tools.thesis_main.analysis.c1_live_collection_monitor import (
    ACTIVE_LOG_DEFAULT,
    MANUAL_ASSIGNMENT_DEFAULT,
    PLANNED_TASK_MAPPING_DEFAULT,
    SEMI_ASSIGNMENT_DEFAULT,
    WORKER_DISTRIBUTION_DEFAULT,
    write_json,
)


def materialize(
    export_json: list[Path],
    output_dir: Path,
    c2_output_dir: Path,
    reserve_pool_csv: Path,
    candidate_inventory_csv: Path,
    min_r_u_tasks: int,
    min_scene_support: int,
    min_calib: int,
    epsilon_r: float,
    tasks_per_fill: int,
    manual_assignment: Path = MANUAL_ASSIGNMENT_DEFAULT,
    semi_assignment: Path = SEMI_ASSIGNMENT_DEFAULT,
    worker_distribution: Path = WORKER_DISTRIBUTION_DEFAULT,
    planned_task_mapping: Path = PLANNED_TASK_MAPPING_DEFAULT,
    active_log: Path | None = ACTIVE_LOG_DEFAULT,
    assignment_manifest: Path | None = None,
    p1_artifacts: list[Path] | None = None,
    p1_task_evidence_csv: Path | None = None,
    p1_worker_status_csv: Path | None = None,
    p1_geometry_task_scores: Path | None = None,
    p1_worker_geometry_profile: Path | None = None,
    require_complete: bool = False,
    input_status: str = "dry_run",
    independence_audit_csv: Path | None = None,
    retrospective_provenance_amendment_csv: Path | None = None,
    temporal_event_csv: Path | None = None,
    temporal_policy_manifest: Path | None = None,
    task_purpose_manifest_csv: Path | None = None,
    candidate_roster_manifest_csv: Path | None = None,
    formal_closeout_adjudication_manifest: Path | None = None,
    formal_worker_state_csv: Path | None = None,
    formal_worker_state_manifest: Path | None = None,
) -> dict[str, Any]:
    canonical = c1_canonicalize_exports.build_canonicalization(
        export_json,
        manual_assignment=manual_assignment,
        semi_assignment=semi_assignment,
        worker_distribution=worker_distribution,
        planned_task_mapping=planned_task_mapping,
        active_log=active_log,
        output_dir=output_dir,
        require_complete=require_complete,
        input_status=input_status,
        independence_audit_csv=independence_audit_csv,
        retrospective_provenance_amendment_csv=retrospective_provenance_amendment_csv,
    )
    gate = run_c1_closeout_dryrun_chain.materialize(
        Path(canonical["canonical_csv"]),
        assignment_manifest or manual_assignment,
        reserve_pool_csv,
        output_dir,
        c2_output_dir,
        candidate_inventory_csv,
        min_r_u_tasks,
        min_scene_support,
        min_calib,
        epsilon_r,
        tasks_per_fill,
        p1_artifacts,
        p1_task_evidence_csv,
        p1_worker_status_csv,
        p1_geometry_task_scores,
        p1_worker_geometry_profile,
        input_status,
        independence_audit_csv,
        retrospective_provenance_amendment_csv,
        temporal_event_csv,
        temporal_policy_manifest,
        task_purpose_manifest_csv,
        candidate_roster_manifest_csv,
        formal_closeout_adjudication_manifest,
        formal_worker_state_csv,
        formal_worker_state_manifest,
    )
    summary = {
        "canonicalization_summary": canonical,
        "gate_summary": gate,
        "canonical_csv": canonical["canonical_csv"],
        "gate_summary_json": str(output_dir / "c1_closeout_dryrun_gate_summary.json"),
        "gate_summary_md": str(output_dir / "c1_closeout_dryrun_gate_summary.md"),
            "c2_draft_manifest": "",
            "c2_materialization_blocked": True,
        "worker_profile_sidecar_summary": str(output_dir / "worker_profile_sidecar_C1.summary.json"),
        "passed_semantics": "raw_to_closeout_dryrun_only_not_official_c1_closeout",
    }
    write_json(output_dir / "c1_raw_to_closeout_dryrun_summary.json", summary)
    return summary


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run raw C1 export canonicalization, then the C1 closeout dryrun chain.")
    parser.add_argument("--export-json", action="append", required=True, type=Path)
    parser.add_argument("--manual-assignment", type=Path, default=MANUAL_ASSIGNMENT_DEFAULT)
    parser.add_argument("--semi-assignment", type=Path, default=SEMI_ASSIGNMENT_DEFAULT)
    parser.add_argument("--worker-distribution", type=Path, default=WORKER_DISTRIBUTION_DEFAULT)
    parser.add_argument("--planned-task-mapping", type=Path, default=PLANNED_TASK_MAPPING_DEFAULT)
    parser.add_argument("--active-log", type=Path, default=ACTIVE_LOG_DEFAULT)
    parser.add_argument("--assignment-manifest", type=Path)
    parser.add_argument("--reserve-pool-csv", type=Path, required=True)
    parser.add_argument("--candidate-inventory-csv", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--c2-output-dir", type=Path, required=True)
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
    parser.add_argument("--require-complete", action="store_true")
    parser.add_argument("--input-status", choices=("dry_run", "formal"), default="dry_run")
    parser.add_argument("--independence-audit-csv", type=Path)
    parser.add_argument("--retrospective-provenance-amendment-csv", type=Path)
    parser.add_argument("--temporal-event-csv", type=Path)
    parser.add_argument("--temporal-policy-manifest", type=Path)
    parser.add_argument("--task-purpose-manifest-csv", type=Path)
    parser.add_argument("--candidate-roster-manifest-csv", type=Path)
    parser.add_argument("--formal-closeout-adjudication-manifest", type=Path)
    parser.add_argument("--formal-worker-state-csv", type=Path)
    parser.add_argument("--formal-worker-state-manifest", type=Path)
    args = parser.parse_args(argv)
    summary = materialize(
        args.export_json,
        args.output_dir,
        args.c2_output_dir,
        args.reserve_pool_csv,
        args.candidate_inventory_csv,
        args.min_r_u_tasks,
        args.min_scene_support,
        args.min_calib,
        args.epsilon_r,
        args.tasks_per_fill,
        manual_assignment=args.manual_assignment,
        semi_assignment=args.semi_assignment,
        worker_distribution=args.worker_distribution,
        planned_task_mapping=args.planned_task_mapping,
        active_log=args.active_log,
        assignment_manifest=args.assignment_manifest,
        p1_artifacts=args.p1_artifact,
        p1_task_evidence_csv=args.p1_task_evidence_csv,
        p1_worker_status_csv=args.p1_worker_status_csv,
        p1_geometry_task_scores=args.p1_geometry_task_scores,
        p1_worker_geometry_profile=args.p1_worker_geometry_profile,
        require_complete=args.require_complete,
        input_status=args.input_status,
        independence_audit_csv=args.independence_audit_csv,
        retrospective_provenance_amendment_csv=args.retrospective_provenance_amendment_csv,
        temporal_event_csv=args.temporal_event_csv,
        temporal_policy_manifest=args.temporal_policy_manifest,
        task_purpose_manifest_csv=args.task_purpose_manifest_csv,
        candidate_roster_manifest_csv=args.candidate_roster_manifest_csv,
        formal_closeout_adjudication_manifest=args.formal_closeout_adjudication_manifest,
        formal_worker_state_csv=args.formal_worker_state_csv,
        formal_worker_state_manifest=args.formal_worker_state_manifest,
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
