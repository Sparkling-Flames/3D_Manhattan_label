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

import numpy as np

_PROJECT_ROOT = Path(__file__).resolve().parents[3]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from tools.thesis_main.analysis import c1_canonicalize_exports
from tools.thesis_main.analysis.active_log_utils import resolve_active_log_files, validate_active_log_freeze_manifest
from tools.thesis_main.analysis.c1_live_collection_monitor import read_csv, write_csv, write_json
from tools.thesis_main.analysis.materialize_c1_operational_reference import materialize as materialize_operational_reference, materialize_gt_cluster_alignment
from tools.thesis_main.analysis.c1_structural_reliability_eb import materialize as materialize_structural_eb
from tools.thesis_main.analysis.materialize_counterexample_bank import materialize_counterexample_bank
from tools.thesis_main.analysis.materialize_c1_rehearsal_audits import (
    materialize_active_log_audits,
    materialize_active_time_ledgers,
    materialize_analysis_rosters,
    materialize_completion_support,
    materialize_effective_task_support,
    finalize_partial_completion_support,
    materialize_geometry_anomaly_root_causes,
    materialize_geometry_pool_eligibility,
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
    materialize_task_building_binding,
)
from tools.thesis_main.analysis.materialize_c1_preannotation_task_features import materialize as materialize_preannotation_features
from tools.thesis_main.analysis.c1_task_adjusted_quality import _BootstrapSupportFailure, estimate_task_adjusted_qgt
from tools.thesis_main.analysis.geometry_consensus.materialize import materialize_geometry_consensus
from tools.thesis_main.analysis.materialize_c1_estimand_specific_task_support import materialize as materialize_estimand_specific_task_support
from tools.thesis_main.analysis.materialize_c1_three_state_task_tags import materialize as materialize_three_state_task_tags
from tools.thesis_main.analysis.materialize_w034_authorized_extension_sensitivity import materialize as materialize_w034_sensitivity
from tools.thesis_main.analysis.materialize_p1_c1_predictive_association import build_source as build_p1_c1_source, materialize as materialize_predictive_association
from tools.thesis_main.analysis.c2b_static_evidence import validate_p1_integrity_bundle
from tools.thesis_main.analysis.vfinal_artifact_utils import sha256_file


REBUILD = Path("analysis_results/calibration_rebuild_20260702")
PLANNED_MAPPING = REBUILD / "ls_project_mapping_audit_v3_1.csv"
CANDIDATE_INVENTORY = REBUILD / "calibration_full_candidate_inventory_v3.csv"


def _validate_p1_integrity_for_mode(input_status: str, directory: Path | None) -> dict[str, Any]:
    validation = validate_p1_integrity_bundle(directory)
    if input_status == "formal" and not validation["valid"]:
        raise ValueError(f"formal C1 requires SHA-bound P1 integrity bundle:{validation['reason']}")
    return validation


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


def _is_w034(value: Any) -> bool:
    return str(value or "").strip().upper().lstrip("W0") == "34"


def _materialize_w034_original_only_profile(output_dir: Path, *, formal: bool, adjust_building: bool) -> Path:
    branch = output_dir / "w034_original_only_branch"
    branch.mkdir(parents=True, exist_ok=True)
    eligibility_path = output_dir / "c1_row_analysis_eligibility.csv"
    eligibility = read_csv(eligibility_path)
    by_annotation = {str(row.get("canonical_annotation_id", "")): row for row in eligibility}
    original_w034 = {
        annotation for annotation, row in by_annotation.items()
        if _is_w034(row.get("worker_id")) and row.get("assignment_provenance") == "original_assignment"
    }
    authorized_w034 = {
        annotation for annotation, row in by_annotation.items()
        if _is_w034(row.get("worker_id")) and row.get("assignment_provenance") == "authorized_replacement_assignment"
    }
    if not original_w034 or not authorized_w034:
        raise ValueError("W034 original-only branch requires both original and authorized canonical identities")

    def filtered(source: Path, name: str) -> Path:
        rows = read_csv(source)
        kept = []
        for row in rows:
            annotation = str(row.get("canonical_annotation_id") or row.get("annotation_id") or "")
            if _is_w034(row.get("worker_id")) and annotation in authorized_w034:
                continue
            kept.append(row)
        target = branch / name
        write_csv(target, kept, list(rows[0]) if rows else ["worker_id"])
        return target

    quality_path = filtered(output_dir / "c1_gt_quality_analysis.csv", "c1_gt_quality_original_only.csv")
    loo_path = filtered(output_dir / "geometry_worker_task_loo_analysis.csv", "geometry_loo_original_only.csv")
    peer_path = filtered(output_dir / "geometry_worker_task_peer_analysis.csv", "geometry_peer_original_only.csv")
    structural_path = filtered(output_dir / "structural_validation_analysis.csv", "structural_original_only.csv")
    eligibility_original = filtered(eligibility_path, "eligibility_original_only.csv")

    quality_rows = read_csv(quality_path)
    globals_, task_effects, audit = estimate_task_adjusted_qgt(
        quality_rows,
        estimator_contract={"bootstrap_replicates": 200 if formal else 80, "bootstrap_seed": 20260726, "adjust_stage": False, "adjust_building": adjust_building},
    )
    qgt_path = branch / "qgt_original_only.csv"
    write_csv(qgt_path, globals_, list(globals_[0]) if globals_ else ["worker_id", "Q_GT_task_adjusted"])
    write_csv(branch / "qgt_task_effects_original_only.csv", task_effects, list(task_effects[0]) if task_effects else ["base_task_id"])
    write_json(branch / "qgt_original_only_audit.json", audit)
    structural_eb_path = branch / "structural_eb_original_only.csv"
    materialize_structural_eb(
        structural_path, structural_eb_path,
        _PROJECT_ROOT / "docs" / "thesis_main" / "GLOBAL_POLICY_THRESHOLDS.json",
    )
    materialize_three_track_worker_state(
        qgt_path, loo_path, structural_path, output_dir / "c1_worker_completion_audit.csv", branch,
        quality_csv=quality_path, eligibility_csv=eligibility_original, peer_csv=peer_path,
        structural_eb_csv=structural_eb_path, formal=False,
    )
    profile = branch / "c1_three_track_worker_state.csv"
    if not profile.is_file():
        raise RuntimeError("W034 original-only profile was not materialized")
    return profile


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
    authorized_reassignment_manifest: Path | None = None, building_registry: Path | None = None,
    late_entry_assignment_manifest: Path | None = None,
    w034_active_time_validation_manifest: Path | None = None,
    w034_original_profile_csv: Path | None = None,
    w034_sensitivity_thresholds: Path | None = None,
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
    if building_registry is not None:
        fixed_sources["building_registry"] = building_registry
    p1_source_files = sorted((path for path in p1_closeout_dir.iterdir() if path.is_file()), key=lambda path: path.name.lower())
    p1_integrity_files = sorted((path for path in p1_integrity_dir.iterdir() if path.is_file()), key=lambda path: path.name.lower()) if p1_integrity_dir else []
    p1_integrity_validation = _validate_p1_integrity_for_mode(input_status, p1_integrity_dir)
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
        "authorized_reassignment_manifest": authorized_reassignment_manifest,
        "late_entry_assignment_manifest": late_entry_assignment_manifest,
        "w034_active_time_validation_manifest": w034_active_time_validation_manifest,
        "w034_original_profile_csv": w034_original_profile_csv,
        "w034_sensitivity_thresholds": w034_sensitivity_thresholds,
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
    def p1_snapshot(name: str) -> Path:
        match = next((path for path in p1_snapshots if path.name.endswith(name)), None)
        if match is None:
            raise FileNotFoundError(f"P1 closeout lacks {name}")
        return match
    canonical_summary = c1_canonicalize_exports.build_canonicalization(
        snapshot_exports,
        manual_assignment=fixed_snapshots["manual_assignment"],
        semi_assignment=fixed_snapshots["semi_assignment"],
        worker_distribution=fixed_snapshots["worker_distribution"],
        planned_task_mapping=fixed_snapshots["planned_mapping"],
        active_log=snapshots / "active_logs", output_dir=output_dir,
        require_complete=False, input_status=input_status,
        duplicate_adjudication_csv=review_snapshots.get("duplicate_adjudication"),
        authorized_reassignment_manifest=review_snapshots.get("authorized_reassignment_manifest"),
        late_entry_assignment_manifest=review_snapshots.get("late_entry_assignment_manifest"),
        w034_active_time_validation_manifest=review_snapshots.get("w034_active_time_validation_manifest"),
        candidate_inventory_csv=fixed_snapshots["candidate_inventory"],
        p1_canonical_csv=p1_snapshot("prescreen_canonical_annotations.csv"),
        p1_admission_csv=p1_snapshot("prescreen_worker_admission.csv"),
    )
    canonical_summary["three_state_task_tags"] = materialize_three_state_task_tags(
        output_dir / "c1_canonical_meta_observations.csv", output_dir,
    )
    # Canonicalization owns immutable row/meta evidence. Geometry is intentionally
    # delayed until the legal peer pool has been frozen below.
    project_independence_evidence_summary = materialize_project_independence_provenance(
        output_dir / "c1_canonical_meta_observations.csv", output_dir,
    )
    independence_summary = materialize_independence(
        output_dir / "c1_canonical_meta_observations.csv", output_dir,
        disposition_csv=review_snapshots.get("annotation_independence_disposition"),
        project_disposition_csv=review_snapshots.get("project_independence_disposition"),
        project_evidence_csv=output_dir / "c1_project_independence_provenance_evidence.csv",
        model_provenance_csv=output_dir / "c1_model_artifact_provenance.csv",
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
        authorized_reassignment_csv=review_snapshots.get("authorized_reassignment_manifest"),
        late_entry_assignment_csv=review_snapshots.get("late_entry_assignment_manifest"),
    )
    completion_rows_for_exclusion = read_csv(output_dir / "c1_worker_completion_audit.csv")
    administratively_excluded_workers = {
        row.get("worker_id", "")
        for row in completion_rows_for_exclusion
        if row.get("completion_status", "").strip().lower() == "administrative_exclusion"
    }
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
    building_summary = materialize_task_building_binding(
        output_dir / "c1_canonical_annotations.csv", fixed_snapshots.get("building_registry"), output_dir,
        formal=formal,
    )
    geometry_pool_summary = materialize_geometry_pool_eligibility(
        output_dir / "c1_canonical_annotations.csv", output_dir / "c1_annotation_version_disposition.csv",
        output_dir / "structural_validation_audit.csv", output_dir / "c1_task_outcome_reference.csv", output_dir,
        independence_csv=output_dir / "c1_independence_evidence.csv",
        outside_disposition_csv=output_dir / "c1_outside_assignment_disposition_evidence.csv",
        completion_csv=output_dir / "c1_worker_completion_audit.csv",
    )
    eligible_geometry_ids = {
        row.get("canonical_annotation_id", "") for row in read_csv(output_dir / "c1_geometry_pool_eligibility.csv")
        if str(row.get("geometry_pool_eligible", "")).lower() in {"true", "1"}
    }
    geometry_summary = materialize_geometry_consensus(
        output_dir / "c1_canonical_geometry.jsonl", output_dir,
        input_status=input_status, excluded_worker_ids=administratively_excluded_workers,
        eligible_annotation_ids=eligible_geometry_ids,
        building_binding_csv=output_dir / "c1_task_building_binding.csv",
    )
    canonical_summary["geometry_sidecars"] = geometry_summary
    canonical_summary["geometry_pool"] = geometry_pool_summary
    canonical_summary["building_binding"] = building_summary
    write_json(output_dir / "c1_canonicalization_summary.json", canonical_summary)
    row_eligibility_summary = materialize_row_analysis_eligibility(
        output_dir / "c1_canonical_annotations.csv", output_dir / "c1_annotation_version_disposition.csv",
        output_dir / "c1_gt_quality_evidence.csv", output_dir / "geometry_worker_task_loo_C1.csv",
        output_dir / "structural_validation_audit.csv", output_dir / "c1_task_outcome_reference.csv", output_dir,
        independence_csv=output_dir / "c1_independence_evidence.csv",
        outside_disposition_csv=output_dir / "c1_outside_assignment_disposition_evidence.csv",
        completion_csv=output_dir / "c1_worker_completion_audit.csv",
    )
    completion_summary = finalize_partial_completion_support(
        output_dir / "c1_worker_completion_audit.csv", output_dir / "c1_row_analysis_eligibility.csv",
        output_dir, completion_summary, collection_window_closed=collection_window_closed,
    )
    completion_summary["effective_task_support"] = materialize_effective_task_support(
        [fixed_snapshots["manual_assignment"], fixed_snapshots["semi_assignment"]],
        output_dir / "c1_canonical_annotations.csv", output_dir / "c1_geometry_pool_eligibility.csv", output_dir,
    )
    completion_summary["estimand_specific_task_support"] = materialize_estimand_specific_task_support(
        [fixed_snapshots["manual_assignment"], fixed_snapshots["semi_assignment"]],
        output_dir / "c1_canonical_annotations.csv", output_dir / "c1_row_analysis_eligibility.csv", output_dir,
        authorized_path=review_snapshots.get("authorized_reassignment_manifest"),
        late_path=review_snapshots.get("late_entry_assignment_manifest"),
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
        peer_csv=output_dir / "geometry_worker_task_peer_C1.csv",
        building_binding_csv=output_dir / "c1_task_building_binding.csv",
    )
    materialize_gt_cluster_alignment(
        output_dir / "geometry_task_crowd_structure_C1.csv",
        output_dir / "geometry_worker_task_loo_C1.csv",
        output_dir / "c1_gt_quality_evidence.csv", output_dir,
        reference_csv=output_dir / "c1_task_outcome_reference.csv", input_status=input_status,
    )
    materialize_structural_eb(
        output_dir / "structural_validation_analysis.csv",
        output_dir / "c1_structural_reliability_eb.csv",
        Path("docs/thesis_main/GLOBAL_POLICY_THRESHOLDS.json"),
    )
    counterexample_events = [
        {"stage": "C1", "base_task_id": row.get("base_task_id", ""), "trigger": "gt_conflict", "trigger_rule_version": row.get("rule_version", ""), "source_artifact": "c1_gt_conflict_review_queue.csv", "source_artifact_sha256": sha256_file(output_dir / "c1_gt_conflict_review_queue.csv"), "evidence_identity": f"{row.get('base_task_id', '')}|{row.get('trigger', '')}", "evidence_sha256": row.get("source_sha256", ""), "denominator_definition": "GT conflict trigger over eligible task crowd"}
        for row in read_csv(output_dir / "c1_gt_conflict_review_queue.csv")
    ] + [
        {"stage": "C1", "base_task_id": row.get("base_task_id", ""), "trigger": "supported_multimodality", "trigger_rule_version": row.get("rule_version", ""), "source_artifact": "geometry_task_crowd_structure_C1.csv", "source_artifact_sha256": sha256_file(output_dir / "geometry_task_crowd_structure_C1.csv"), "evidence_identity": row.get("base_task_id", ""), "evidence_sha256": row.get("source_sha256", ""), "denominator_definition": "eligible unique-worker crowd geometry"}
        for row in read_csv(output_dir / "geometry_task_crowd_structure_C1.csv")
        if row.get("task_crowd_structure_status") == "supported_multimodal"
    ] + [
        {"stage": "C1", "base_task_id": row.get("base_task_id", ""), "canonical_annotation_id": row.get("canonical_annotation_id", ""), "trigger": "worker_structural_failure", "trigger_rule_version": row.get("rule_version", ""), "source_artifact": "structural_validation_analysis.csv", "source_artifact_sha256": sha256_file(output_dir / "structural_validation_analysis.csv"), "evidence_identity": row.get("canonical_annotation_id", ""), "evidence_sha256": row.get("source_sha256", ""), "denominator_definition": "structural opportunities after process and independence gates"}
        for row in read_csv(output_dir / "structural_validation_analysis.csv")
        if row.get("failure_attribution") == "worker_caused_structural_failure"
    ] + [
        {"stage": "C1", "base_task_id": "", "canonical_annotation_id": f"worker:{row.get('worker_id', '')}", "evidence_identity": row.get("worker_id", ""), "trigger": "process_integrity", "trigger_rule_version": "c1_completion_disposition_v1", "source_artifact": "c1_worker_completion_audit.csv", "source_artifact_sha256": sha256_file(output_dir / "c1_worker_completion_audit.csv"), "denominator_definition": "administratively_excluded_worker"}
        for row in read_csv(output_dir / "c1_worker_completion_audit.csv")
        if row.get("completion_status", "").strip().lower() == "administrative_exclusion"
    ]
    materialize_counterexample_bank(counterexample_events, output_dir / "counterexample_bank")
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

    qgt_evidence_path = output_dir / "c1_task_adjusted_qgt_worker_evidence.csv"
    try:
        globals_, task_effects, model_audit = estimate_task_adjusted_qgt(
            quality,
            estimator_contract={
                "bootstrap_replicates": 200 if formal else 80,
                "bootstrap_seed": 20260726,
                "adjust_stage": False,
                "adjust_building": bool(fixed_snapshots.get("building_registry")),
            },
        )
        model_audit["building_registry_sha256"] = building_summary.get("registry_sha256", "")
        model_audit["building_binding_sha256"] = building_summary.get("output_sha256", "")
        write_csv(qgt_evidence_path, globals_, list(globals_[0]))
        write_csv(output_dir / "c1_task_adjusted_qgt_task_effects.csv", task_effects, list(task_effects[0]))
        write_json(output_dir / "c1_task_adjusted_qgt_model_audit.json", model_audit)
    except _BootstrapSupportFailure as exc:
        model_audit = {"status": "not_evaluable", **exc.audit}
        write_csv(qgt_evidence_path, [], ["worker_id", "Q_GT_task_adjusted"])
        write_csv(output_dir / "c1_task_adjusted_qgt_task_effects.csv", [], ["base_task_id", "task_random_intercept"])
        write_json(output_dir / "c1_task_adjusted_qgt_model_audit.json", model_audit)
    except (ValueError, KeyError, np.linalg.LinAlgError) as exc:
        model_audit = {"status": "not_evaluable", "reason": str(exc)}
        write_csv(qgt_evidence_path, [], ["worker_id", "Q_GT_task_adjusted"])
        write_csv(output_dir / "c1_task_adjusted_qgt_task_effects.csv", [], ["base_task_id", "task_random_intercept"])
        write_json(output_dir / "c1_task_adjusted_qgt_model_audit.json", model_audit)

    three_track_summary = materialize_three_track_worker_state(
        qgt_evidence_path, output_dir / "geometry_worker_task_loo_analysis.csv",
        output_dir / "structural_validation_analysis.csv", output_dir / "c1_worker_completion_audit.csv", output_dir,
        quality_csv=output_dir / "c1_gt_quality_analysis.csv",
        eligibility_csv=output_dir / "c1_row_analysis_eligibility.csv",
        peer_csv=output_dir / "geometry_worker_task_peer_analysis.csv",
        structural_eb_csv=output_dir / "c1_structural_reliability_eb.csv",
        formal=formal,
    )
    predictive_path = output_dir / "p1_to_c1_descriptive_directional_check.csv"
    worker_state_path = output_dir / ("c1_three_track_worker_state_formal.csv" if formal else "c1_three_track_worker_state.csv")
    pooled_profile_rows = read_csv(worker_state_path)
    original_profile_rows = [row for row in pooled_profile_rows if row.get("enrollment_batch") == "original"]
    original_profile_path = output_dir / "c1_three_track_worker_state_original_only.csv"
    write_csv(original_profile_path, original_profile_rows, list(pooled_profile_rows[0]) if pooled_profile_rows else ["schema_version", "worker_id"])
    def profile_ranks(rows: list[dict[str, Any]]) -> dict[str, int]:
        ordered = sorted(
            (row for row in rows if str(row.get("Q_GT_EB", "")).strip()),
            key=lambda row: (-float(row["Q_GT_EB"]), str(row.get("worker_id", ""))),
        )
        return {str(row["worker_id"]): index for index, row in enumerate(ordered, 1)}
    pooled_ranks, original_ranks = profile_ranks(pooled_profile_rows), profile_ranks(original_profile_rows)
    rank_displacements = {worker: pooled_ranks[worker] - rank for worker, rank in original_ranks.items() if worker in pooled_ranks}
    rolling_profile_summary = {
        "schema_version": "paper_a_rolling_profile_sensitivity_v1",
        "rolling_enrollment_activated": any(row.get("enrollment_batch") == "late_entry" for row in pooled_profile_rows),
        "pooled_profile_sha256": sha256_file(worker_state_path),
        "original_only_profile_sha256": sha256_file(original_profile_path),
        "pooled_worker_count": len(pooled_profile_rows),
        "original_worker_count": len(original_profile_rows),
        "late_entry_worker_count": len(pooled_profile_rows) - len(original_profile_rows),
        "rank_displacement_by_worker": rank_displacements,
        "maximum_absolute_rank_displacement": max((abs(value) for value in rank_displacements.values()), default=0),
    }
    write_json(output_dir / "c1_rolling_profile_sensitivity.json", rolling_profile_summary)
    sensitivity_original = review_snapshots.get("w034_original_profile_csv")
    sensitivity_thresholds = review_snapshots.get("w034_sensitivity_thresholds")
    if sensitivity_original is None and authorized_reassignment_manifest is not None:
        sensitivity_original = _materialize_w034_original_only_profile(
            output_dir, formal=formal, adjust_building=bool(fixed_snapshots.get("building_registry")),
        )
    if sensitivity_original and sensitivity_thresholds:
        w034_sensitivity_summary = materialize_w034_sensitivity(
            sensitivity_original, worker_state_path, sensitivity_thresholds,
            output_dir / "w034_original_vs_authorized_sensitivity.json",
        )
    elif formal and authorized_reassignment_manifest is not None:
        raise ValueError("formal W034 authorized extension requires frozen sensitivity thresholds")
    else:
        w034_sensitivity_summary = {"status": "not_evaluable", "reason": "original_profile_or_thresholds_not_provided"}
    if p1_integrity_validation["valid"]:
        predictive_source = build_p1_c1_source(
            snapshots / "p1_closeout", worker_state_path, predictive_path,
            correction_dir=snapshots / "p1_integrity",
        )
        predictive_summary = {**materialize_predictive_association(predictive_path, output_dir), **predictive_source, "p1_integrity": p1_integrity_validation}
    else:
        write_csv(predictive_path, [], ["worker_id", "check_name", "p1_metric_value", "c1_metric_value"])
        predictive_summary = {
            "status": "not_evaluable_missing_p1_integrity", "n_join_rows": 0,
            "n_evaluable_rows": 0, "p1_integrity": p1_integrity_validation,
            "legacy_p1_summary_fallback_used": False,
        }
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
        "rolling_profile_sensitivity": rolling_profile_summary,
        "w034_authorized_extension_sensitivity": w034_sensitivity_summary,
        "c2_candidate_pool_summary": {
            "n_inventory_tasks": len(read_csv(fixed_snapshots["candidate_inventory"])),
            "n_tasks": 0,
            "source": "not_materialized_in_c1_stage",
        },
        "c2_task_risk_summary": {"status": "not_run_in_c1_stage"},
        "c2b_task_eligibility_evidence_summary": {"status": "not_run_in_c1_stage"},
        "p1_to_c1_predictive_summary": predictive_summary,
        "p1_integrity": p1_integrity_validation,
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
