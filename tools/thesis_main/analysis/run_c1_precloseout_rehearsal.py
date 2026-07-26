"""Materialize immutable C1 evidence bundles for the public closeout CLI."""

from __future__ import annotations

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

from tools.thesis_main.analysis import c1_canonicalize_exports
from tools.thesis_main.analysis.active_log_utils import resolve_active_log_files, validate_active_log_freeze_manifest
from tools.thesis_main.analysis.c1_live_collection_monitor import read_csv, write_csv, write_json
from tools.thesis_main.analysis.materialize_c1_operational_reference import materialize as materialize_operational_reference
from tools.thesis_main.analysis.materialize_c1_rehearsal_audits import (
    materialize_active_log_audits,
    materialize_active_time_ledgers,
    materialize_analysis_rosters,
    materialize_completion_support,
    finalize_partial_completion_support,
    materialize_geometry_anomaly_root_causes,
    materialize_final_canonical_closeout_summary,
    materialize_independence,
    materialize_project_independence_provenance,
    materialize_outside_assignment,
    materialize_row_analysis_eligibility,
    materialize_structural_validation,
    materialize_three_track_worker_state,
)
from tools.thesis_main.analysis.c1_c2_mainline import (
    formal_git_state,
    materialize_analysis_views,
    materialize_measurement_readiness,
)
from tools.thesis_main.analysis.materialize_c1_preannotation_task_features import materialize as materialize_preannotation_features
from tools.thesis_main.analysis.materialize_frozen_routing_profiles import build_global
from tools.thesis_main.analysis.materialize_p1_c1_predictive_association import build_source as build_p1_c1_source, materialize as materialize_predictive_association
from tools.thesis_main.analysis.vfinal_artifact_utils import sha256_file


REBUILD = Path("analysis_results/calibration_rebuild_20260702")
PLANNED_MAPPING = REBUILD / "ls_project_mapping_audit_v3_1.csv"
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


def _content_aggregate_sha(paths: Iterable[Path]) -> str:
    rows = [{"size": path.stat().st_size, "sha256": sha256_file(path)} for path in paths]
    return _aggregate_sha(sorted(rows, key=lambda row: (row["sha256"], row["size"])))


def _validate_collection_closure(
    path: Path | None, *, formal: bool, export_sha: str, active_freeze_manifest: Path | None,
    assignment_paths: list[Path], export_paths: list[Path], assignment_sha_override: str | None = None,
) -> tuple[bool, dict[str, Any]]:
    if not path:
        if formal:
            raise ValueError("formal mode requires --collection-closure-manifest")
        return False, {"status": "not_provided_rehearsal_only"}
    payload = json.loads(path.read_text(encoding="utf-8"))
    assignment_sha = assignment_sha_override or _aggregate_sha(_manifest_rows(assignment_paths))
    assignment_content_sha = _content_aggregate_sha(assignment_paths)
    export_content_sha = _content_aggregate_sha(export_paths)
    freeze_sha = sha256_file(active_freeze_manifest) if active_freeze_manifest and active_freeze_manifest.exists() else ""
    freeze_payload = json.loads(active_freeze_manifest.read_text(encoding="utf-8")) if active_freeze_manifest and active_freeze_manifest.exists() else {}
    expected = {
        "c1_export_aggregate_sha256": export_sha,
        "c1_active_log_freeze_manifest_sha256": freeze_sha,
        "c1_assignment_sha256": assignment_sha,
    }
    mismatches = [name for name, value in expected.items() if payload.get(name) != value]
    if "c1_assignment_sha256" in mismatches and payload.get("c1_assignment_sha256") == assignment_content_sha:
        mismatches.remove("c1_assignment_sha256")
    if "c1_export_aggregate_sha256" in mismatches and payload.get("c1_export_aggregate_sha256") == export_content_sha:
        mismatches.remove("c1_export_aggregate_sha256")
    required = ("closure_time", "operator", "late_submission_policy")
    try:
        closure_time = datetime.fromisoformat(str(payload.get("closure_time", "")).replace("Z", "+00:00"))
        cutoff_time = datetime.fromisoformat(str(freeze_payload.get("collection_cutoff_server_time", "")).replace("Z", "+00:00"))
        cutoff_matches = closure_time == cutoff_time
    except ValueError:
        cutoff_matches = False
    if not cutoff_matches:
        mismatches.append("closure_time_vs_active_log_cutoff")
    if payload.get("collection_window_closed") is not True or mismatches or any(not str(payload.get(name, "")).strip() for name in required):
        if formal:
            raise ValueError(f"invalid collection closure manifest: {mismatches or 'missing closure fields'}")
        return False, {**payload, "status": "invalid_rehearsal_manifest", "mismatches": mismatches}
    return True, {**payload, "status": "validated", "c1_assignment_sha256": assignment_sha}


def _stage_active_log_provenance(p1_closeout_dir: Path, c1_active_log: Path) -> dict[str, Any]:
    """Record stage-specific log roots; never treat a later-stage root as PreScreen."""
    configs = sorted(p1_closeout_dir.glob("*run_config*.json"), key=lambda path: path.name.lower())
    for config in configs:
        try:
            payload = json.loads(config.read_text(encoding="utf-8"))
            active = payload.get("inputs", {}).get("active_logs", {})
        except (OSError, json.JSONDecodeError):
            continue
        if not isinstance(active, dict) or not active.get("path"):
            continue
        configured = str(active["path"])
        resolved = Path(configured)
        if not resolved.is_absolute():
            resolved = _PROJECT_ROOT / resolved
        configured_resolved = resolved.resolve()
        c1_resolved = c1_active_log.resolve()
        snapshot = Path(str(active.get("snapshot_path") or ""))
        if snapshot and not snapshot.is_absolute():
            snapshot = _PROJECT_ROOT / snapshot
        immutable_snapshot = bool(
            active.get("aggregate_sha256") and snapshot.is_dir()
            and snapshot.resolve().is_relative_to(p1_closeout_dir.resolve())
        )
        valid_prescreen_source = configured_resolved == (_PROJECT_ROOT / "active_logs" / "prescreen").resolve() or immutable_snapshot
        return {
            "prescreen": {
                "stage": "PreScreen",
                "configured_root": configured,
                "resolved_root": configured_resolved.as_posix() if resolved.exists() else "",
                "snapshot_path": str(active.get("snapshot_path") or ""),
                "aggregate_sha256": str(active.get("aggregate_sha256") or ""),
                "source_config": config.resolve().as_posix(),
                "source_config_sha256": sha256_file(config),
                "validated": valid_prescreen_source,
            },
            "c1": {
                "stage": "C1",
                "configured_root": str(c1_active_log),
                "resolved_root": c1_active_log.resolve().as_posix() if c1_active_log.exists() else "",
                "validated": c1_active_log.exists(),
            },
            "prescreen_not_substituted": configured_resolved != c1_resolved,
        }
    return {
        "prescreen": {"stage": "PreScreen", "configured_root": "", "validated": False, "status": "not_evaluable"},
        "c1": {"stage": "C1", "configured_root": str(c1_active_log), "validated": c1_active_log.exists()},
        "prescreen_not_substituted": True,
        "status": "prescreen_config_missing",
    }


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
        independence_valid = [row for row in process_valid if row.get("independence_status") in {"independent", "independent_by_project_provenance", "independent_by_annotation_disposition"}]
        output.append({
            **state,
            "process_eligible": bool(process_valid),
            "independence_eligible": bool(independence_valid),
            "reference_evaluable": bool(evaluable),
            "F_struct": len(structural) / len(structural_evaluable) if structural_evaluable else "",
            "LOO_support": sum(bool(row.get("loo_reference_status")) for row in rows),
        })
    return output


def _c1_closeout_blockers(formal: bool, blockers: list[str]) -> list[str]:
    """C2 confirmation is downstream and can never block the C1 freeze owner."""
    return [*([] if formal else ["partial_c1_collection"]), *blockers]


def materialize(
    export_dirs: list[Path], active_log: Path, manual_assignment: Path,
    semi_assignment: Path, worker_distribution: Path, gt_export: Path,
    p1_closeout_dir: Path, output_root: Path, *, input_status: str,
    run_date: str | None = None,
    c1_preannotation_feature_csv: Path | None = None,
    independence_disposition: Path | None = None,
    project_independence_disposition: Path | None = None,
    structural_disposition: Path | None = None,
    duplicate_adjudication: Path | None = None, scope_adjudication: Path | None = None,
    reference_amendment: Path | None = None, outside_assignment_disposition: Path | None = None,
    completion_disposition: Path | None = None, c1_active_log_freeze_manifest: Path | None = None,
    collection_closure_manifest: Path | None = None,
    p1_integrity_dir: Path | None = None,
    active_log_snapshot_bound: bool = False,
    source_export_aggregate_sha: str | None = None,
    source_assignment_aggregate_sha: str | None = None,
) -> dict[str, Any]:
    if input_status not in {"precloseout_rehearsal", "formal"}:
        raise ValueError("input_status must be precloseout_rehearsal or formal")
    formal = input_status == "formal"
    git_state = formal_git_state(_PROJECT_ROOT)
    if formal and not git_state["clean"]:
        raise ValueError("formal mode requires a committed clean worktree")
    export_files = [item for directory in export_dirs for item in _files(directory) if item.suffix.lower() == ".json"]
    if not export_files:
        raise ValueError("no C1 export JSON files found")
    export_rows = _manifest_rows(export_files)
    export_sha = source_export_aggregate_sha or _aggregate_sha(export_rows)
    pipeline_files = sorted((Path(__file__).parent.rglob("*.py")), key=lambda path: path.as_posix())
    code_pipeline_sha = _aggregate_sha(_manifest_rows(pipeline_files))
    _active_root, active_source_files = resolve_active_log_files(active_log)
    fixed_sources = {
        "manual_assignment": manual_assignment, "semi_assignment": semi_assignment,
        "worker_distribution": worker_distribution, "gt_export": gt_export,
        "planned_mapping": PLANNED_MAPPING,
        "candidate_inventory": CANDIDATE_INVENTORY,
    }
    if c1_preannotation_feature_csv is not None:
        fixed_sources["c1_preannotation_feature"] = c1_preannotation_feature_csv
    p1_source_files = sorted((path for path in p1_closeout_dir.iterdir() if path.is_file()), key=lambda path: path.name.lower())
    p1_integrity_files = sorted((path for path in p1_integrity_dir.iterdir() if path.is_file()), key=lambda path: path.name.lower()) if p1_integrity_dir else []
    stage_active_log_provenance = _stage_active_log_provenance(p1_closeout_dir, active_log)
    if formal and (
        not stage_active_log_provenance["prescreen"].get("validated")
        or not stage_active_log_provenance.get("prescreen_not_substituted")
    ):
        raise ValueError("formal C1 requires the PreScreen active_logs/prescreen source or its immutable closeout snapshot")
    review_sources = {name: path for name, path in {
        "duplicate_adjudication": duplicate_adjudication, "structural_disposition": structural_disposition,
        "project_independence_disposition": project_independence_disposition,
        "annotation_independence_disposition": independence_disposition, "scope_adjudication": scope_adjudication,
        "reference_amendment": reference_amendment, "outside_assignment_disposition": outside_assignment_disposition,
        "completion_disposition": completion_disposition,
        "c1_active_log_freeze_manifest": c1_active_log_freeze_manifest,
        "collection_closure_manifest": collection_closure_manifest,
    }.items() if path is not None}
    analysis_input_rows = _manifest_rows([*export_files, *active_source_files, *fixed_sources.values(), *p1_source_files, *p1_integrity_files, *review_sources.values()])
    analysis_input_bundle_sha = _aggregate_sha(analysis_input_rows)
    if formal:
        if not c1_active_log_freeze_manifest or not c1_active_log_freeze_manifest.exists():
            raise ValueError("formal mode requires c1_active_log_freeze_manifest")
        validate_active_log_freeze_manifest(
            c1_active_log_freeze_manifest, active_log,
            allow_immutable_copy=active_log_snapshot_bound,
        )
    collection_window_closed, collection_closure = _validate_collection_closure(
        collection_closure_manifest, formal=formal, export_sha=export_sha,
        active_freeze_manifest=c1_active_log_freeze_manifest,
        assignment_paths=[manual_assignment, semi_assignment], export_paths=export_files,
        assignment_sha_override=source_assignment_aggregate_sha,
    )
    run_date = run_date or datetime.now().strftime("%Y%m%d")
    prefix = "c1_formal_audit" if formal else "c1_precloseout_rehearsal"
    output_dir = output_root / f"{prefix}_{run_date}_{export_sha[:12]}_{analysis_input_bundle_sha[:8]}_{code_pipeline_sha[:8]}"
    if output_dir.exists():
        raise FileExistsError(f"immutable rehearsal output already exists: {output_dir}")
    snapshots = output_dir / "raw_snapshots"
    output_dir.mkdir(parents=True)

    snapshot_exports = [_snapshot(path, snapshots, "exports") for path in export_files]
    snapshot_active = [_snapshot(path, snapshots, "active_logs") for path in active_source_files]
    fixed_snapshots = {name: _snapshot(path, snapshots, "contracts") for name, path in fixed_sources.items()}
    p1_snapshots = [_snapshot(path, snapshots, "p1_closeout") for path in p1_source_files]
    p1_integrity_snapshots = [_snapshot(path, snapshots, "p1_integrity") for path in p1_integrity_files]
    review_snapshots = {name: _snapshot(path, snapshots, "dispositions") for name, path in review_sources.items()}
    all_sources = [*export_files, *active_source_files, *fixed_sources.values(), *p1_source_files, *p1_integrity_files, *review_sources.values()]
    source_rows = _manifest_rows(all_sources)
    input_roles = {path.resolve(): name for name, path in fixed_sources.items()}
    for row in source_rows:
        row["input_role"] = input_roles.get(Path(row["path"]).resolve(), "")
    all_snapshots = [*snapshot_exports, *snapshot_active, *fixed_snapshots.values(), *p1_snapshots, *p1_integrity_snapshots, *review_snapshots.values()]
    snapshot_by_identity = {
        (sha256_file(path), path.name if path.parent.name == "active_logs" else path.name.split("_", 1)[-1]): path
        for path in all_snapshots
    }
    for row in source_rows:
        snap = snapshot_by_identity.get((row["sha256"], Path(row["path"]).name))
        row["snapshot_path"] = snap.resolve().as_posix() if snap else ""
        row["snapshot_sha256"] = sha256_file(snap) if snap else ""
    diff = _git(["diff", "--binary", "HEAD"])
    untracked = _git(["ls-files", "--others", "--exclude-standard"]).splitlines()
    if not formal:
        (output_dir / "worktree.patch").write_text(diff, encoding="utf-8")
        write_json(output_dir / "untracked_file_manifest.json", {"files": untracked, "sha256": hashlib.sha256("\n".join(untracked).encode("utf-8")).hexdigest()})
    raw_manifest = {
        "schema_version": "c1_precloseout_raw_snapshot_v1",
        "created_at": datetime.now().astimezone().isoformat(),
        "input_status": input_status,
        "aggregate_export_sha256": export_sha,
        "code_pipeline_sha256": code_pipeline_sha,
        "analysis_input_bundle_sha256": analysis_input_bundle_sha,
        "head": git_state["git_commit_sha"],
        "git_status": _git(["status", "--short"]),
        "worktree_diff_sha256": hashlib.sha256(diff.encode("utf-8")).hexdigest(),
        "worktree_patch_sha256": hashlib.sha256(diff.encode("utf-8")).hexdigest() if not formal else "",
        "untracked_file_manifest_sha256": hashlib.sha256("\n".join(untracked).encode("utf-8")).hexdigest() if not formal else "",
        "command": " ".join(sys.argv),
        "tool_version": "run_c1_precloseout_rehearsal_v3",
        "stage_active_log_provenance": stage_active_log_provenance,
        "collection_closure": collection_closure,
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
        duplicate_adjudication_csv=review_snapshots.get("duplicate_adjudication"),
    )
    # build_canonicalization owns canonical sidecars and geometry consensus.
    # Re-running either here duplicates the most expensive C1 work and risks
    # overwriting one logical artifact with a second execution.
    project_independence_evidence_summary = materialize_project_independence_provenance(
        output_dir / "c1_canonical_meta_observations.csv", output_dir,
    )
    independence_summary = materialize_independence(
        output_dir / "c1_canonical_meta_observations.csv", output_dir,
        disposition_csv=review_snapshots.get("annotation_independence_disposition"),
        project_disposition_csv=review_snapshots.get("project_independence_disposition"),
        project_evidence_csv=output_dir / "c1_project_independence_provenance_evidence.csv",
    )
    structural_summary = materialize_structural_validation(
        output_dir / "c1_canonical_annotations.csv", output_dir / "c1_canonical_geometry.jsonl", output_dir,
        disposition_csv=review_snapshots.get("structural_disposition"),
    )
    canonical_summary["failure_attribution_counts"] = structural_summary["failure_attribution_counts"]
    canonical_summary["structural_validation_summary"] = structural_summary
    write_json(output_dir / "c1_canonicalization_summary.json", canonical_summary)
    completion_summary = materialize_completion_support(
        snapshot_exports, [fixed_snapshots["manual_assignment"], fixed_snapshots["semi_assignment"]],
        output_dir / "c1_runtime_task_mapping.csv", output_dir / "c1_canonical_annotations.csv",
        output_dir / "c1_canonical_geometry.jsonl", output_dir,
        completion_disposition_csv=review_snapshots.get("completion_disposition"), collection_window_closed=collection_window_closed,
    )
    outside_summary = materialize_outside_assignment(
        output_dir / "c1_canonical_annotations.csv", output_dir,
        disposition_csv=review_snapshots.get("outside_assignment_disposition"),
    )
    active_summary = materialize_active_log_audits(
        output_dir / "c1_canonical_meta_observations.csv", snapshots / "active_logs", output_dir,
    )
    active_summary["stage"] = "C1"
    active_summary["source_root"] = str(active_log)
    active_summary["stage_active_log_provenance"] = stage_active_log_provenance
    reference_summary = materialize_operational_reference(
        output_dir / "c1_canonical_annotations.csv", output_dir / "c1_canonical_geometry.jsonl",
        fixed_snapshots["candidate_inventory"], fixed_snapshots["gt_export"], output_dir,
        scope_adjudication_csv=review_snapshots.get("scope_adjudication"),
        reference_amendment=review_snapshots.get("reference_amendment"),
    )
    row_eligibility_summary = materialize_row_analysis_eligibility(
        output_dir / "c1_canonical_annotations.csv", output_dir / "c1_annotation_version_disposition.csv",
        output_dir / "c1_gt_quality_evidence.csv", output_dir / "geometry_worker_task_loo_C1.csv",
        output_dir / "structural_validation_audit.csv", output_dir / "c1_task_outcome_reference.csv", output_dir,
        independence_csv=output_dir / "c1_independence_evidence.csv",
        outside_disposition_csv=output_dir / "c1_outside_assignment_disposition_evidence.csv",
    )
    completion_summary = finalize_partial_completion_support(
        output_dir / "c1_worker_completion_audit.csv", output_dir / "c1_row_analysis_eligibility.csv",
        output_dir, completion_summary, collection_window_closed=collection_window_closed,
    )
    roster_summary = materialize_analysis_rosters(
        output_dir / "c1_worker_completion_audit.csv", output_dir / "c1_canonical_annotations.csv", output_dir,
    )
    final_canonical_summary = materialize_final_canonical_closeout_summary(
        output_dir, completion_summary, outside_summary=outside_summary, formal=formal,
    )
    analysis_views = materialize_analysis_views(
        output_dir / "c1_gt_quality_evidence.csv", output_dir / "geometry_worker_task_loo_C1.csv",
        output_dir / "structural_validation_audit.csv", output_dir / "c1_row_analysis_eligibility.csv", output_dir,
    )
    anomaly_summary = materialize_geometry_anomaly_root_causes(
        output_dir / "c1_canonical_annotations.csv", output_dir / "c1_canonical_meta_observations.csv",
        output_dir / "c1_canonical_geometry.jsonl", output_dir / "structural_validation_audit.csv", output_dir,
        reference_csv=output_dir / "c1_task_outcome_reference.csv",
    )
    # The closeout chain consumes canonicalizer binding evidence; publish the richer
    # event/session ledger only after that contract has been evaluated.
    active_ledger_summary = materialize_active_time_ledgers(
        output_dir / "c1_canonical_meta_observations.csv", snapshots / "active_logs", output_dir,
    )
    chain = {"canonicalization_summary": canonical_summary, "operational_reference_summary": reference_summary, "row_eligibility_summary": row_eligibility_summary, "analysis_views": analysis_views}

    canonical = read_csv(output_dir / "c1_canonical_annotations.csv")
    quality = read_csv(output_dir / "c1_gt_quality_analysis.csv")
    completion_rows = read_csv(output_dir / "c1_worker_completion_audit.csv")
    roster = {row["worker_id"] for row in completion_rows}
    observed = {row["worker_id"] for row in completion_rows if int(row["observed_total_count"]) > 0}
    missing_workers = [row["worker_id"] for row in completion_rows if row["completion_status"] == "nonstarter"]
    not_evaluable = [row for row in read_csv(output_dir / "structural_validation_audit.csv") if row.get("failure_attribution") == "not_evaluable"]

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

    loo_rows = read_csv(output_dir / "geometry_worker_task_loo_C1.csv")
    pairwise_rows = read_csv(output_dir / "geometry_pairwise_similarity_C1.csv")
    valid_geometry = sum(row.get("structural_validation_status") == "passed" for row in canonical)
    if valid_geometry >= 2 and not pairwise_rows:
        raise RuntimeError("geometry LOO pipeline produced zero pairwise rows despite valid geometry")

    try:
        globals_, task_effects, model_audit = build_global(
            quality, _derived_worker_gates(quality, completion_rows),
            profile_version="precloseout_partial_c1", input_status=input_status,
        )
        write_csv(output_dir / "provisional_strong_global.csv", globals_, list(globals_[0]))
        write_csv(output_dir / "provisional_strong_global_task_effects.csv", task_effects, list(task_effects[0]))
    except (ValueError, KeyError) as exc:
        model_audit = {"status": "not_evaluable", "reason": str(exc)}
        write_csv(output_dir / "provisional_strong_global.csv", [], ["worker_id", "provisional_rank"])

    three_track_summary = materialize_three_track_worker_state(
        output_dir / "provisional_strong_global.csv", output_dir / "geometry_worker_task_loo_analysis.csv",
        output_dir / "structural_validation_analysis.csv", output_dir / "c1_worker_completion_audit.csv", output_dir,
        quality_csv=output_dir / "c1_gt_quality_analysis.csv",
        eligibility_csv=output_dir / "c1_row_analysis_eligibility.csv",
        formal=formal,
    )
    predictive_path = output_dir / "p1_to_c1_descriptive_directional_check.csv"
    worker_state_path = output_dir / ("c1_three_track_worker_state_formal.csv" if formal else "c1_three_track_worker_state.csv")
    predictive_source = build_p1_c1_source(snapshots / "p1_closeout", worker_state_path, predictive_path, correction_dir=snapshots / "p1_integrity" if p1_integrity_snapshots else None)
    predictive_summary = {**materialize_predictive_association(predictive_path, output_dir), **predictive_source}
    preannotation_summary = materialize_preannotation_features(
        [fixed_snapshots["manual_assignment"], fixed_snapshots["semi_assignment"]], fixed_snapshots["candidate_inventory"], output_dir,
        frozen_feature_csv=fixed_snapshots.get("c1_preannotation_feature"),
    )
    readiness = materialize_measurement_readiness(
        output_dir / "c1_worker_completion_audit.csv", output_dir / "c1_gt_quality_analysis.csv",
        output_dir / "geometry_worker_task_loo_analysis.csv", output_dir / "structural_validation_analysis.csv", output_dir,
        canonical_closed=bool(final_canonical_summary.get("C1_CANONICAL_CLOSED")),
        collection_window_closed=collection_window_closed,
        eligibility_csv=output_dir / "c1_row_analysis_eligibility.csv",
        preannotation_feature_ready=bool(preannotation_summary.get("n_tasks")) and preannotation_summary.get("n_ready") == preannotation_summary.get("n_tasks"),
    )
    readiness["method_contract"] = "Pilot->P1->C1->C2-B->C2-A-RP->T1->V1"
    readiness["git_commit_sha"] = git_state["git_commit_sha"]
    readiness["worktree_clean"] = bool(git_state["clean"])
    write_json(output_dir / "c1_measurement_freeze_manifest.json", readiness)
    c2_summary = {
        "status": "not_run_in_c1_stage",
        "candidate_only": True,
        "launch_ready": False,
        "n_feasible_candidate_designs": 0,
        "assignment_row_count": 0,
        "failure_reason": "C2-B design is owned by design-c2b after C1 freeze",
    }

    dependency_contracts = [
        Path("docs/thesis_main/geometry_loo_candidate_rule_manifest_v1.json"),
        Path("docs/thesis_main/c1_geometry_parser_amendment_v1.json"),
        Path("docs/thesis_main/C1_PRECLOSEOUT_AUDIT_FIELD_CONTRACT_v1.md"),
        Path("docs/thesis_main/C1_C2_ARTIFACT_FIELD_CONTRACT_v1.md"),
    ]
    dependency_rows = _manifest_rows([
        *pipeline_files, *fixed_snapshots.values(), *snapshot_exports, *snapshot_active,
        *p1_snapshots, *p1_integrity_snapshots, *review_snapshots.values(),
        *(path for path in dependency_contracts if path.exists()),
    ])
    versions = {}
    for package in ("numpy", "pandas", "scipy", "statsmodels", "patsy"):
        try: versions[package] = importlib.metadata.version(package)
        except importlib.metadata.PackageNotFoundError: versions[package] = "not_installed"
    dependency_manifest = {
        "schema_version": "paper_a_analysis_dependency_manifest_v1", "git_head": raw_manifest["head"],
        "worktree_diff_sha256": raw_manifest["worktree_diff_sha256"], "exact_command": raw_manifest["command"],
        "python_version": sys.version, "package_versions": versions, "dependencies": dependency_rows,
        "stage_active_log_provenance": stage_active_log_provenance,
    }
    dependency_manifest["code_pipeline_sha256"] = code_pipeline_sha
    dependency_manifest["analysis_input_bundle_sha256"] = analysis_input_bundle_sha
    dependency_manifest["full_dependency_bundle_sha256"] = _aggregate_sha(dependency_rows)
    write_json(output_dir / "analysis_dependency_manifest.json", dependency_manifest)

    summary = {
        "input_status": input_status,
        "method_contract": "Pilot->P1->C1->C2-B->C2-A-RP->T1->V1",
        "git_commit_sha": git_state["git_commit_sha"], "worktree_clean": bool(git_state["clean"]),
        "output_dir": str(output_dir.resolve()),
        "aggregate_export_sha256": export_sha,
        "code_pipeline_sha256": code_pipeline_sha,
        "analysis_input_bundle_sha256": analysis_input_bundle_sha,
        "full_dependency_bundle_sha256": dependency_manifest["full_dependency_bundle_sha256"],
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
        "project_independence_evidence_summary": project_independence_evidence_summary,
        "active_log_summary": active_summary,
        "stage_active_log_provenance": stage_active_log_provenance,
        "collection_closure": collection_closure,
        "active_time_ledger_summary": active_ledger_summary,
        "outside_assignment_summary": outside_summary,
        "geometry_loo_summary": {"n_pairwise_rows": len(pairwise_rows), "n_loo_rows": len(loo_rows)},
        "c2b_design_worker_profile_summary": {"status": "owned_by_design_c2b"},
        "c1_c2_design_parameter_summary": {"status": "owned_by_design_c2b"},
        "c1_preannotation_feature_summary": preannotation_summary,
        "c1_measurement_readiness": readiness,
        "three_track_worker_state_summary": three_track_summary,
        "c2_candidate_pool_summary": {
            "n_inventory_tasks": len(read_csv(fixed_snapshots["candidate_inventory"])),
            "n_tasks": 0,
            "source": "not_materialized_in_c1_stage",
        },
        "c2_task_risk_summary": {"status": "not_run_in_c1_stage"},
        "c2b_task_eligibility_evidence_summary": {"status": "not_run_in_c1_stage"},
        "p1_to_c1_predictive_summary": predictive_summary,
        "C1_CANONICAL_CLOSED": bool(readiness["C1_CANONICAL_CLOSED"]),
        "C1_MEASUREMENT_FROZEN": bool(readiness["C1_MEASUREMENT_FROZEN"]),
        "C2B_RISK_DESIGN_FROZEN": False,
        "C2B_DESIGN_FROZEN": False,
        "C2B_ASSIGNMENT_MATERIALIZED": False,
        "C2B_LAUNCH_READY": False,
        "C2B_DESIGN_READY": bool(readiness["C2B_DESIGN_READY"]),
        "formal_closeout_ready": formal and bool(readiness["C1_MEASUREMENT_FROZEN"]) and bool(final_canonical_summary["formal_closeout_ready"]), "profile_frozen": False, "c2_launch_ready": False,
        "formal_mode_executed": formal, "formal_audit_complete": formal and bool(final_canonical_summary["formal_audit_complete"]),
        "c1_evidence_frozen": False, "c2_design_frozen": False, "c2_assignment_materialized": False,
        "formal_results_materialized": formal and final_canonical_summary["formal_audit_complete"], "c2_candidate_only": not formal,
        "chain_gate": {"legacy_diagnostic_chain_consumed": False},
        "operational_reference_summary": chain.get("operational_reference_summary", {}),
        "strong_global_model_audit": model_audit,
        "c2b_candidate_summary": c2_summary,
        "c2b_assignment_row_count": 0,
        "final_canonical_closeout_summary": final_canonical_summary,
        "blockers": _c1_closeout_blockers(formal, final_canonical_summary["blockers"]),
        "downstream_blockers": ["c2b_not_confirmed"],
    }
    summary["state_machine"] = {
        "C1_COLLECTION_INCOMPLETE": bool(readiness["C1_COLLECTION_INCOMPLETE"]),
        **{name: bool(summary[name]) for name in (
            "C1_CANONICAL_CLOSED", "C1_MEASUREMENT_FROZEN", "C2B_RISK_DESIGN_FROZEN",
            "C2B_DESIGN_FROZEN", "C2B_ASSIGNMENT_MATERIALIZED", "C2B_LAUNCH_READY",
        )},
    }
    write_json(output_dir / ("formal_audit_summary.json" if formal else "rehearsal_summary.json"), summary)
    return summary
