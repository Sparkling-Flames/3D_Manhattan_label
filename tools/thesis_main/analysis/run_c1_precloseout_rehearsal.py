"""Run an immutable, candidate-only C1 pre-closeout rehearsal."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import shutil
import subprocess
import sys
import importlib.metadata
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable

_PROJECT_ROOT = Path(__file__).resolve().parents[3]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from tools.thesis_main.analysis import build_c2_assignment_manifest_from_c1_gaps as c2b
from tools.thesis_main.analysis import c1_canonicalize_exports
from tools.thesis_main.analysis import run_c1_closeout_dryrun_chain
from tools.thesis_main.analysis.active_log_utils import resolve_active_log_files
from tools.thesis_main.analysis.c1_live_collection_monitor import read_csv, write_csv, write_json
from tools.thesis_main.analysis.materialize_c1_operational_reference import materialize as materialize_operational_reference
from tools.thesis_main.analysis.materialize_c1_canonical_evidence_sidecars import materialize_canonical_evidence
from tools.thesis_main.analysis.materialize_c1_rehearsal_audits import (
    apply_independence,
    apply_structural_dispositions,
    materialize_active_log_audits,
    materialize_active_time_ledgers,
    materialize_analysis_rosters,
    materialize_c2_eligible_roster,
    materialize_completion_support,
    materialize_geometry_anomaly_root_causes,
    materialize_independence,
    materialize_outside_assignment,
    materialize_row_analysis_eligibility,
    materialize_structural_validation,
    materialize_three_track_worker_state,
)
from tools.thesis_main.analysis.materialize_frozen_routing_profiles import build_global
from tools.thesis_main.analysis.materialize_c2_task_risk import materialize as materialize_task_risk
from tools.thesis_main.analysis.materialize_p1_c1_predictive_association import materialize as materialize_predictive_association
from tools.thesis_main.analysis.geometry_consensus.materialize import materialize_geometry_consensus
from tools.thesis_main.analysis.vfinal_artifact_utils import sha256_file


REBUILD = Path("analysis_results/calibration_rebuild_20260702")
PLANNED_MAPPING = REBUILD / "ls_project_mapping_audit_v3_1.csv"
RESERVE_POOL = REBUILD / "calibration_reserve_draft_v3_1.csv"
CANDIDATE_INVENTORY = REBUILD / "calibration_full_candidate_inventory_v3.csv"


def _files(path: Path) -> list[Path]:
    return sorted((item for item in path.rglob("*") if item.is_file()), key=lambda item: item.as_posix().lower()) if path.is_dir() else [path]


def _manifest_rows(paths: Iterable[Path]) -> list[dict[str, Any]]:
    rows = []
    for path in sorted({item.resolve() for item in paths}, key=lambda item: item.as_posix().lower()):
        rows.append({"path": path.as_posix(), "size": path.stat().st_size, "sha256": sha256_file(path)})
    return rows


def _aggregate_sha(rows: list[dict[str, Any]]) -> str:
    payload = json.dumps(rows, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _git(command: list[str]) -> str:
    result = subprocess.run(["git", *command], cwd=_PROJECT_ROOT, check=True, capture_output=True)
    return result.stdout.decode("utf-8", errors="replace")


def _snapshot(source: Path, root: Path, category: str) -> Path:
    name = source.name if category == "active_logs" else f"{sha256_file(source)[:12]}_{source.name}"
    destination = root / category / name
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, destination)
    if sha256_file(source) != sha256_file(destination):
        raise RuntimeError(f"snapshot SHA mismatch: {source}")
    return destination


def _copy_alias(source: Path, destination: Path) -> None:
    if not source.exists():
        destination.write_text("\n" if destination.suffix == ".csv" else "{}\n", encoding="utf-8")
        return
    shutil.copy2(source, destination)


def _derived_worker_gates(quality_rows: list[dict[str, str]], workers: list[dict[str, str]]) -> list[dict[str, Any]]:
    by_worker: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in quality_rows:
        by_worker[str(row.get("worker_id", ""))].append(row)
    output = []
    for state in workers:
        worker = str(state.get("worker_id", ""))
        rows = by_worker.get(worker, [])
        manual = [row for row in rows if str(row.get("condition", "")).lower() == "manual"]
        evaluable = [row for row in manual if str(row.get("quality_evaluable", "")).lower() in {"true", "1"}]
        structural_evaluable = [row for row in manual if row.get("failure_attribution") not in {"", "not_evaluable"}]
        structural = [row for row in structural_evaluable if str(row.get("worker_caused_structural_failure", "")).lower() in {"true", "1"}]
        process_valid = [row for row in rows if str(row.get("outside_assignment_submission", "")).lower() not in {"true", "1"} and str(row.get("duplicate_worker_task_submission", "")).lower() not in {"true", "1"}]
        independence_valid = [row for row in process_valid if row.get("independence_status") == "independent"]
        output.append({
            **state,
            "process_eligible": bool(process_valid),
            "independence_eligible": bool(independence_valid),
            "reference_evaluable": bool(evaluable),
            "F_struct": len(structural) / len(structural_evaluable) if structural_evaluable else "",
            "LOO_support": sum(bool(row.get("loo_reference_status")) for row in rows),
        })
    return output


def _candidate_design_manifest(task_pool: Path, worker_profile: Path, output: Path) -> Path:
    tasks = read_csv(task_pool)
    anchors = sum(str(row.get("anchor_eligible") or row.get("is_common_anchor") or row.get("eligible_for_anchor_candidate", "")).lower() in {"true", "1"} for row in tasks)
    bridges = sum(
        str(row.get("bridge_eligible") or row.get("is_diverse_bridge") or row.get("eligible_for_reserve_candidate", "")).lower() in {"true", "1"}
        for row in tasks
    )
    candidates = []
    for common, per_worker, unique in ((2, 2, 6), (3, 3, 9), (4, 4, 12)):
        if common <= anchors and per_worker <= bridges:
            candidates.append({
                "design_id": f"rehearsal_a{common}_b{per_worker}_u{min(unique, bridges)}",
                "common_anchor_count": common,
                "bridge_per_worker": per_worker,
                "unique_bridge_tasks": min(unique, bridges),
                "min_task_support": 2,
                "max_worker_stratum_imbalance": 2,
            })
    manifest = {
        "manifest_version": "c2_design_v1",
        "artifact_role": "precloseout_candidate_enumeration_only",
        "input_sha256": {"worker_profile_csv": sha256_file(worker_profile), "task_pool_csv": sha256_file(task_pool)},
        "candidate_designs": candidates,
        "c2b_target_ci_half_width": 1.0,
        "simulation": {"seed": 20260724, "draws": 1000},
    }
    write_json(output, manifest)
    return output


def _candidate_task_pool(inventory: Path, assignments: list[Path], output: Path) -> Path:
    history = {
        value
        for path in assignments for row in read_csv(path)
        for value in (row.get("task_id", ""), row.get("base_task_id", "")) if value
    }
    rows = sorted(
        read_csv(inventory),
        key=lambda row: (int(row.get("full_pool_order") or 10**9), row.get("task_id", "")),
    )
    candidate_rows = []
    for row in rows:
        task, base = row.get("task_id", ""), row.get("base_task_id", "")
        excluded = task in history or base in history or str(row.get("hard_exclude", "")).lower() in {"true", "1"}
        if excluded or str(row.get("eligible_after_exclusion", "")).lower() not in {"true", "1"}:
            continue
        pair_count = int(float(row.get("gt_pair_count") or 0))
        candidate_rows.append({
            **row,
            "building_id": (row.get("image_id") or base).split("_", 1)[0],
            "source_split": row.get("source_pool", ""),
            "ordinary_stress": "stress" if pair_count >= 7 or pair_count <= 3 else "ordinary",
            "d_model_feat": "", "g_model_struct": pair_count,
            "d_cal_A": "", "risk_assist_candidate": "pending_c1_risk_freeze", "risk_route_candidate": "pending_c1_risk_freeze",
            # Common-anchor is a C2-B assignment role. The legacy inventory has
            # no anchor flags, so every reference-ready remaining task may be
            # considered by the frozen design simulation.
            "anchor_eligible": str(row.get("geometry_gold_ready", "")).lower() in {"true", "1"},
            "bridge_eligible": str(row.get("eligible_for_reserve_candidate", "")).lower() in {"true", "1"},
            "task_stratum": "stress" if pair_count >= 7 or pair_count <= 3 else "ordinary",
            "reference_status": "reference_ready" if str(row.get("geometry_gold_ready", "")).lower() in {"true", "1"} else "pending_adjudication",
            "scope_status": row.get("expert_review_status", ""), "history_exclusion": False,
            "p1_c1_overlap": False, "future_t1_v1_exclusion": False,
            "future_holdout_manifest_status": "not_provided_rehearsal_only",
            "candidate_role_source": "full_candidate_inventory_precloseout",
        })
    write_csv(output, candidate_rows, list(candidate_rows[0]) if candidate_rows else ["task_id"])
    return output


def materialize(
    export_dirs: list[Path], active_log: Path, manual_assignment: Path,
    semi_assignment: Path, worker_distribution: Path, gt_export: Path,
    p1_closeout_dir: Path, output_root: Path, *, input_status: str,
    run_date: str | None = None,
) -> dict[str, Any]:
    if input_status != "precloseout_rehearsal":
        raise ValueError("rehearsal requires input_status=precloseout_rehearsal")
    export_files = [item for directory in export_dirs for item in _files(directory) if item.suffix.lower() == ".json"]
    if not export_files:
        raise ValueError("no C1 export JSON files found")
    export_rows = _manifest_rows(export_files)
    export_sha = _aggregate_sha(export_rows)
    pipeline_files = sorted((Path(__file__).parent.rglob("*.py")), key=lambda path: path.as_posix())
    pipeline_sha = _aggregate_sha(_manifest_rows(pipeline_files))
    run_date = run_date or datetime.now().strftime("%Y%m%d")
    output_dir = output_root / f"c1_precloseout_rehearsal_{run_date}_{export_sha[:12]}_{pipeline_sha[:8]}"
    if output_dir.exists():
        raise FileExistsError(f"immutable rehearsal output already exists: {output_dir}")
    snapshots = output_dir / "raw_snapshots"
    output_dir.mkdir(parents=True)

    snapshot_exports = [_snapshot(path, snapshots, "exports") for path in export_files]
    _active_root, active_source_files = resolve_active_log_files(active_log)
    snapshot_active = [_snapshot(path, snapshots, "active_logs") for path in active_source_files]
    fixed_sources = {
        "manual_assignment": manual_assignment,
        "semi_assignment": semi_assignment,
        "worker_distribution": worker_distribution,
        "gt_export": gt_export,
        "planned_mapping": PLANNED_MAPPING,
        "reserve_pool": RESERVE_POOL,
        "candidate_inventory": CANDIDATE_INVENTORY,
    }
    fixed_snapshots = {name: _snapshot(path, snapshots, "contracts") for name, path in fixed_sources.items()}
    p1_source_files = sorted(
        (path for path in p1_closeout_dir.iterdir() if path.is_file()),
        key=lambda path: path.name.lower(),
    )
    p1_snapshots = [_snapshot(path, snapshots, "p1_closeout") for path in p1_source_files]
    all_sources = [*export_files, *active_source_files, *fixed_sources.values(), *p1_source_files]
    source_rows = _manifest_rows(all_sources)
    all_snapshots = [*snapshot_exports, *snapshot_active, *fixed_snapshots.values(), *p1_snapshots]
    snapshot_by_identity = {
        (sha256_file(path), path.name if path.parent.name == "active_logs" else path.name.split("_", 1)[-1]): path
        for path in all_snapshots
    }
    for row in source_rows:
        snap = snapshot_by_identity.get((row["sha256"], Path(row["path"]).name))
        row["snapshot_path"] = snap.resolve().as_posix() if snap else ""
        row["snapshot_sha256"] = sha256_file(snap) if snap else ""
    diff = _git(["diff", "--binary", "HEAD"])
    raw_manifest = {
        "schema_version": "c1_precloseout_raw_snapshot_v1",
        "created_at": datetime.now().astimezone().isoformat(),
        "input_status": "precloseout_partial_c1",
        "aggregate_export_sha256": export_sha,
        "pipeline_sha256": pipeline_sha,
        "head": _git(["rev-parse", "HEAD"]).strip(),
        "git_status": _git(["status", "--short"]),
        "worktree_diff_sha256": hashlib.sha256(diff.encode("utf-8")).hexdigest(),
        "command": " ".join(sys.argv),
        "tool_version": "run_c1_precloseout_rehearsal_v2",
        "inputs": source_rows,
    }
    write_json(output_dir / "raw_input_manifest.json", raw_manifest)

    p1_artifacts = [path for path in p1_snapshots if path.suffix.lower() in {".csv", ".json", ".jsonl"}]
    canonical_summary = c1_canonicalize_exports.build_canonicalization(
        snapshot_exports,
        manual_assignment=fixed_snapshots["manual_assignment"],
        semi_assignment=fixed_snapshots["semi_assignment"],
        worker_distribution=fixed_snapshots["worker_distribution"],
        planned_task_mapping=fixed_snapshots["planned_mapping"],
        active_log=snapshots / "active_logs", output_dir=output_dir,
        require_complete=False, input_status=input_status,
    )
    independence_summary = materialize_independence(output_dir / "c1_canonical_meta_observations.csv", output_dir)
    apply_independence(output_dir / "c1_canonical_annotations.csv", output_dir / "c1_independence_evidence.csv")
    structural_summary = materialize_structural_validation(
        output_dir / "c1_canonical_annotations.csv", output_dir / "c1_canonical_geometry.jsonl", output_dir,
    )
    apply_structural_dispositions(
        output_dir / "c1_canonical_annotations.csv", output_dir / "structural_validation_audit.csv",
    )
    canonical_summary["failure_attribution_counts"] = structural_summary["failure_attribution_counts"]
    canonical_summary["structural_validation_summary"] = structural_summary
    write_json(output_dir / "c1_canonicalization_summary.json", canonical_summary)
    materialize_canonical_evidence(
        snapshot_exports, output_dir / "c1_canonical_annotations.csv", output_dir,
        input_status=input_status,
        version_disposition_csv=output_dir / "c1_annotation_version_disposition.csv",
    )
    materialize_geometry_consensus(
        output_dir / "c1_canonical_geometry.jsonl", output_dir, input_status=input_status,
    )
    completion_summary = materialize_completion_support(
        snapshot_exports, [fixed_snapshots["manual_assignment"], fixed_snapshots["semi_assignment"]],
        output_dir / "c1_runtime_task_mapping.csv", output_dir / "c1_canonical_annotations.csv",
        output_dir / "c1_canonical_geometry.jsonl", output_dir,
    )
    roster_summary = materialize_analysis_rosters(
        output_dir / "c1_worker_completion_audit.csv", output_dir / "c1_canonical_annotations.csv", output_dir,
    )
    outside_summary = materialize_outside_assignment(output_dir / "c1_canonical_annotations.csv", output_dir)
    active_summary = materialize_active_log_audits(
        output_dir / "c1_canonical_meta_observations.csv", snapshots / "active_logs", output_dir,
    )
    reference_summary = materialize_operational_reference(
        output_dir / "c1_canonical_annotations.csv", output_dir / "c1_canonical_geometry.jsonl",
        fixed_snapshots["candidate_inventory"], fixed_snapshots["gt_export"], output_dir,
    )
    row_eligibility_summary = materialize_row_analysis_eligibility(
        output_dir / "c1_canonical_annotations.csv", output_dir / "c1_annotation_version_disposition.csv",
        output_dir / "c1_gt_quality_evidence.csv", output_dir / "geometry_worker_task_loo_C1.csv",
        output_dir / "structural_validation_audit.csv", output_dir / "c1_task_outcome_reference.csv", output_dir,
    )
    anomaly_summary = materialize_geometry_anomaly_root_causes(
        output_dir / "c1_canonical_annotations.csv", output_dir / "c1_canonical_meta_observations.csv",
        output_dir / "c1_canonical_geometry.jsonl", output_dir / "structural_validation_audit.csv", output_dir,
        reference_csv=output_dir / "c1_task_outcome_reference.csv",
    )
    gate = run_c1_closeout_dryrun_chain.materialize(
        output_dir / "c1_canonical_annotations.csv", fixed_snapshots["manual_assignment"],
        fixed_snapshots["reserve_pool"], output_dir, output_dir / "c2_candidates",
        fixed_snapshots["candidate_inventory"], 5, 1, 2, .15, 1,
        p1_artifacts=p1_artifacts, input_status=input_status,
        task_outcome_csv=output_dir / "c1_task_outcome_reference.csv",
        assignment_manifests=[fixed_snapshots["manual_assignment"], fixed_snapshots["semi_assignment"]],
    )
    # The closeout chain consumes canonicalizer binding evidence; publish the richer
    # event/session ledger only after that contract has been evaluated.
    active_ledger_summary = materialize_active_time_ledgers(
        output_dir / "c1_canonical_meta_observations.csv", snapshots / "active_logs", output_dir,
    )
    chain = {"canonicalization_summary": canonical_summary, "gate_summary": gate, "operational_reference_summary": reference_summary, "row_eligibility_summary": row_eligibility_summary}
    predictive_path = output_dir / "p1_to_c1_descriptive_directional_check.csv"
    predictive_summary = materialize_predictive_association(predictive_path, output_dir) if predictive_path.exists() else {"component_status": "not_evaluable", "reason": "p1_to_c1_source_missing"}

    canonical = read_csv(output_dir / "c1_canonical_annotations.csv")
    quality = read_csv(output_dir / "c1_gt_quality_evidence.csv")
    worker_state = read_csv(output_dir / "worker_state_snapshot_C1.csv")
    completion_rows = read_csv(output_dir / "c1_worker_completion_audit.csv")
    roster = {row["worker_id"] for row in completion_rows}
    observed = {row["worker_id"] for row in completion_rows if int(row["observed_total_count"]) > 0}
    missing_workers = [row["worker_id"] for row in completion_rows if row["completion_status"] == "nonstarter"]
    not_evaluable = [row for row in canonical if row.get("failure_attribution") == "not_evaluable"]

    _copy_alias(output_dir / "c1_canonicalization_summary.json", output_dir / "canonicalization_audit.json")
    _copy_alias(output_dir / "c1_runtime_key_collision_audit.csv", output_dir / "identity_collision_audit.csv")
    _copy_alias(output_dir / "c1_duplicate_annotation_audit.csv", output_dir / "duplicate_revision_audit.csv")
    _copy_alias(output_dir / "c1_active_time_binding_audit.csv", output_dir / "active_time_join_audit.csv")
    _copy_alias(output_dir / "structural_validation_audit.csv", output_dir / "failure_disposition.csv")
    write_json(output_dir / "failure_disposition_audit.json", {
        "n_rows": len(canonical), "n_not_evaluable": len(not_evaluable),
        "none_imputed_for_unadjudicated": False,
    })
    write_csv(output_dir / "not_evaluable_queue.csv", not_evaluable, list(canonical[0]) if canonical else ["worker_id"])
    _copy_alias(output_dir / "c1_gt_quality_evidence.csv", output_dir / "GT_quality_audit.csv")
    _copy_alias(output_dir / "geometry_worker_task_loo_C1.csv", output_dir / "LOO_status_audit.csv")
    _copy_alias(output_dir / "worker_state_snapshot_C1.csv", output_dir / "provisional_worker_state.csv")

    loo_rows = read_csv(output_dir / "geometry_worker_task_loo_C1.csv")
    pairwise_rows = read_csv(output_dir / "geometry_pairwise_similarity_C1.csv")
    valid_geometry = sum(row.get("structural_validation_status") == "passed" for row in canonical)
    if valid_geometry >= 2 and not pairwise_rows:
        raise RuntimeError("geometry LOO pipeline produced zero pairwise rows despite valid geometry")

    try:
        globals_, task_effects, model_audit = build_global(
            quality, _derived_worker_gates(quality, worker_state),
            profile_version="precloseout_partial_c1", input_status=input_status,
        )
        write_csv(output_dir / "provisional_strong_global.csv", globals_, list(globals_[0]))
        write_csv(output_dir / "provisional_strong_global_task_effects.csv", task_effects, list(task_effects[0]))
    except (ValueError, KeyError) as exc:
        model_audit = {"status": "not_evaluable", "reason": str(exc)}
        write_csv(output_dir / "provisional_strong_global.csv", [], ["worker_id", "provisional_rank"])

    three_track_summary = materialize_three_track_worker_state(
        output_dir / "provisional_strong_global.csv", output_dir / "geometry_worker_task_loo_C1.csv",
        output_dir / "structural_validation_audit.csv", output_dir / "c1_worker_completion_audit.csv", output_dir,
        quality_csv=output_dir / "c1_gt_quality_evidence.csv",
    )

    c2_roster_summary = materialize_c2_eligible_roster(
        output_dir / "c1_worker_completion_audit.csv", output_dir / "c1_canonical_annotations.csv",
        output_dir / "c1_gt_quality_evidence.csv", output_dir / "geometry_worker_task_loo_C1.csv", output_dir,
    )
    profile = output_dir / "c2_eligible_roster_C1.csv"
    raw_task_pool = _candidate_task_pool(
        fixed_snapshots["candidate_inventory"], [fixed_snapshots["manual_assignment"], fixed_snapshots["semi_assignment"]],
        output_dir / "c2b_candidate_task_pool_raw.csv",
    )
    risk_summary = materialize_task_risk(
        raw_task_pool, Path("output/layout_json"), output_dir / "c1_canonical_geometry.jsonl", output_dir,
        input_status=input_status,
        checkpoint=Path("ckpt/mp3d_layout_HOHO_layout_aug_efficienthc_Transen1_resnet34/ep300.pth"),
        reference_dir=Path("data/mp3d_layout/train_no_occ/img"), extract_lhfeat=False,
    )
    task_pool = output_dir / "c2_task_risk_inventory.csv"
    shutil.copy2(task_pool, output_dir / "c2b_candidate_task_pool.csv")
    design_manifest = _candidate_design_manifest(task_pool, profile, output_dir / "c2b_candidate_design_manifest.json")
    try:
        c2_summary = c2b.materialize(
            task_pool, profile, design_manifest,
            output_dir / "c2_candidates", input_status=input_status,
        )
    except ValueError as exc:
        c2_summary = {"candidate_only": True, "launch_ready": False, "failure_reason": str(exc)}
    _copy_alias(output_dir / "c2_candidates" / "c2b_design_candidates.csv", output_dir / "c2b_candidate_designs.csv")
    _copy_alias(output_dir / "c2_candidates" / "c2b_worker_task_graph_audit.csv", output_dir / "c2b_worker_task_graph_audit.csv")
    _copy_alias(output_dir / "c2_candidates" / "candidate_C2B_assignment.csv", output_dir / "candidate_C2B_assignment.csv")

    dependency_contracts = [
        Path("docs/thesis_main/geometry_loo_candidate_rule_manifest_v1.json"),
        Path("docs/thesis_main/C1_PRECLOSEOUT_AUDIT_FIELD_CONTRACT_v1.md"),
        Path("docs/thesis_main/C1_C2_ARTIFACT_FIELD_CONTRACT_v1.md"),
        Path("config/mp3d_layout/HOHO_layout_aug_efficienthc_Transen1_resnet34.yaml"),
        Path("ckpt/mp3d_layout_HOHO_layout_aug_efficienthc_Transen1_resnet34/ep300.pth"),
    ]
    dependency_rows = _manifest_rows([*pipeline_files, *fixed_snapshots.values(), *snapshot_exports, *snapshot_active, *(path for path in dependency_contracts if path.exists())])
    versions = {}
    for package in ("numpy", "pandas", "scipy", "statsmodels", "patsy"):
        try: versions[package] = importlib.metadata.version(package)
        except importlib.metadata.PackageNotFoundError: versions[package] = "not_installed"
    dependency_manifest = {
        "schema_version": "paper_a_analysis_dependency_manifest_v1", "git_head": raw_manifest["head"],
        "worktree_diff_sha256": raw_manifest["worktree_diff_sha256"], "exact_command": raw_manifest["command"],
        "python_version": sys.version, "package_versions": versions, "dependencies": dependency_rows,
    }
    dependency_manifest["pipeline_sha256"] = _aggregate_sha(dependency_rows)
    write_json(output_dir / "analysis_dependency_manifest.json", dependency_manifest)

    summary = {
        "input_status": "precloseout_partial_c1",
        "output_dir": str(output_dir.resolve()),
        "aggregate_export_sha256": export_sha,
        "pipeline_sha256": pipeline_sha,
        "n_export_files": len(export_files), "roster_size": len(roster),
        "observed_worker_count": len(roster & observed),
        "missing_worker_ids": missing_workers,
        "missing_workers": [f"W{int(worker):03d}" if worker.isdigit() else worker for worker in missing_workers],
        "n_not_evaluable": len(not_evaluable),
        "completion_summary": completion_summary,
        "roster_summary": roster_summary,
        "structural_validation_summary": structural_summary,
        "geometry_anomaly_summary": anomaly_summary,
        "independence_summary": independence_summary,
        "active_log_summary": active_summary,
        "active_time_ledger_summary": active_ledger_summary,
        "outside_assignment_summary": outside_summary,
        "geometry_loo_summary": {"n_pairwise_rows": len(pairwise_rows), "n_loo_rows": len(loo_rows)},
        "c2_eligible_roster_summary": c2_roster_summary,
        "three_track_worker_state_summary": three_track_summary,
        "c2_candidate_pool_summary": {
            "n_inventory_tasks": len(read_csv(fixed_snapshots["candidate_inventory"])),
            "n_tasks": len(read_csv(task_pool)),
            "source": "full_candidate_inventory_precloseout",
            "future_holdout_manifest_status": "not_provided_rehearsal_only",
        },
        "c2_task_risk_summary": risk_summary,
        "p1_to_c1_predictive_summary": predictive_summary,
        "formal_closeout_ready": False, "profile_frozen": False, "c2_launch_ready": False,
        "formal_results_materialized": False, "c2_candidate_only": True,
        "chain_gate": chain.get("gate_summary", {}),
        "operational_reference_summary": chain.get("operational_reference_summary", {}),
        "strong_global_model_audit": model_audit,
        "c2b_candidate_summary": c2_summary,
        "blockers": ["partial_c1_collection", *(["missing_workers"] if missing_workers else []), *(["not_evaluable_rows"] if not_evaluable else []), "c2b_not_confirmed"],
    }
    write_json(output_dir / "rehearsal_summary.json", summary)
    return summary


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run immutable C1 pre-closeout rehearsal from raw exports.")
    parser.add_argument("--export-dir", action="append", type=Path, required=True)
    parser.add_argument("--active-log", type=Path, required=True)
    parser.add_argument("--manual-assignment", type=Path, required=True)
    parser.add_argument("--semi-assignment", type=Path, required=True)
    parser.add_argument("--worker-distribution", type=Path, required=True)
    parser.add_argument("--gt-export", type=Path, required=True)
    parser.add_argument("--p1-closeout-dir", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--input-status", choices=("precloseout_rehearsal",), required=True)
    args = parser.parse_args(argv)
    print(json.dumps(materialize(
        args.export_dir, args.active_log, args.manual_assignment, args.semi_assignment,
        args.worker_distribution, args.gt_export, args.p1_closeout_dir,
        args.output_root, input_status=args.input_status,
    ), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
