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
from tools.thesis_main.analysis.active_log_utils import resolve_active_log_files
from tools.thesis_main.analysis.c1_live_collection_monitor import read_csv, write_csv, write_json
from tools.thesis_main.analysis.materialize_c1_operational_reference import materialize as materialize_operational_reference
from tools.thesis_main.analysis.materialize_c1_canonical_evidence_sidecars import materialize_canonical_evidence
from tools.thesis_main.analysis.materialize_c1_rehearsal_audits import (
    materialize_active_log_audits,
    materialize_active_time_ledgers,
    materialize_analysis_rosters,
    materialize_completion_support,
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
    materialize_c2b_design_worker_profile,
    materialize_measurement_readiness,
)
from tools.thesis_main.analysis.materialize_c1_preannotation_task_features import materialize as materialize_preannotation_features
from tools.thesis_main.analysis.materialize_c1_c2_design_parameters import materialize as materialize_design_parameters
from tools.thesis_main.analysis.materialize_frozen_routing_profiles import build_global
from tools.thesis_main.analysis.materialize_c2_task_risk import materialize as materialize_task_risk
from tools.thesis_main.analysis.materialize_p1_c1_predictive_association import materialize as materialize_predictive_association
from tools.thesis_main.analysis.geometry_consensus.materialize import materialize_geometry_consensus
from tools.thesis_main.analysis.vfinal_artifact_utils import sha256_file


REBUILD = Path("analysis_results/calibration_rebuild_20260702")
PLANNED_MAPPING = REBUILD / "ls_project_mapping_audit_v3_1.csv"
RESERVE_POOL = REBUILD / "calibration_reserve_draft_v3_1.csv"
CANDIDATE_INVENTORY = REBUILD / "calibration_full_candidate_inventory_v3.csv"
RISK_DESIGN_CONTRACT = _PROJECT_ROOT / "docs" / "thesis_main" / "C2B_RISK_DESIGN_CONTRACT_v1.json"


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
        return {
            "prescreen": {
                "stage": "PreScreen",
                "configured_root": configured,
                "resolved_root": configured_resolved.as_posix() if resolved.exists() else "",
                "snapshot_path": str(active.get("snapshot_path") or ""),
                "aggregate_sha256": str(active.get("aggregate_sha256") or ""),
                "source_config": config.resolve().as_posix(),
                "source_config_sha256": sha256_file(config),
                "validated": resolved.is_dir() or bool(active.get("snapshot_path")),
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


def _candidate_design_manifest(task_pool: Path, worker_profile: Path, output: Path) -> Path:
    tasks = [row for row in read_csv(task_pool) if str(row.get("assignment_eligible", "")).lower() in {"true", "1"}]
    anchors = sum(str(row.get("anchor_eligible") or row.get("is_common_anchor") or row.get("eligible_for_anchor_candidate", "")).lower() in {"true", "1"} for row in tasks)
    bridges = sum(
        str(row.get("bridge_eligible") or row.get("is_diverse_bridge") or row.get("eligible_for_reserve_candidate", "")).lower() in {"true", "1"}
        for row in tasks
    )
    worker_count = sum(str(row.get("c2_candidate_eligible", "")).lower() in {"true", "1"} for row in read_csv(worker_profile))
    def levels(low: int, high: int) -> list[int]:
        if high < low:
            return []
        span = high - low
        return sorted({low, low + (span + 2) // 3, low + (2 * span + 2) // 3, high})

    candidates = []
    # Enumerate from the realized pool rather than privileging an historical
    # a2/b2/u6-style design.  The simulation decides whether any candidate is
    # admissible; rehearsal never selects one.
    max_common = min(anchors, max(1, worker_count))
    max_per_worker = min(bridges, max(1, 2 * ((bridges + max(worker_count, 1) - 1) // max(worker_count, 1))))
    for common in levels(1, max_common):
        for per_worker in levels(1, max_per_worker):
            min_unique = max(1, (worker_count * per_worker + 1) // 2)
            for unique in levels(min_unique, min(bridges, worker_count * per_worker)):
                candidates.append({
                    "design_id": f"candidate_a{common}_b{per_worker}_u{unique}",
                    "common_anchor_count": common,
                    "bridge_per_worker": per_worker,
                    "unique_bridge_tasks": unique,
                    "min_task_support": 2,
                    "max_worker_stratum_imbalance": 2,
                })
    manifest = {
        "manifest_version": "c2_design_v1",
        "artifact_role": "precloseout_candidate_enumeration_only",
        "input_sha256": {"worker_profile_csv": sha256_file(worker_profile), "task_pool_csv": sha256_file(task_pool)},
        "risk_contract_sha256": sha256_file(RISK_DESIGN_CONTRACT),
        "threshold_manifest_sha256": sha256_file(_PROJECT_ROOT / "docs" / "thesis_main" / "C2B_DESIGN_SELECTION_THRESHOLDS.json"),
        "candidate_designs": candidates,
        "simulation": {"seed": 20260724, "draws": 1000, "resampling": "C1 empirical building/task/worker bootstrap"},
        "selection_rule": "report_pareto_candidates_only_until_frozen_post_C1_selection",
    }
    write_json(output, manifest)
    return output


def _candidate_task_pool(inventory: Path, assignments: list[Path], output: Path, reserve_pool: Path | None = None) -> Path:
    history = {
        value
        for path in assignments for row in read_csv(path)
        for value in (row.get("task_id", ""), row.get("base_task_id", "")) if value
    }
    reserve = {
        value: row for row in (read_csv(reserve_pool) if reserve_pool else [])
        for value in (row.get("task_id", ""), row.get("base_task_id", "")) if value
    }
    rows = sorted(
        read_csv(inventory),
        key=lambda row: (int(row.get("full_pool_order") or 10**9), row.get("task_id", "")),
    )
    candidate_rows = []
    legacy_audit_rows = []
    for row in rows:
        task, base = row.get("task_id", ""), row.get("base_task_id", "")
        legacy = reserve.get(task) or reserve.get(base) or {}
        history_overlap = task in history or base in history
        excluded = history_overlap or str(row.get("hard_exclude", "")).lower() in {"true", "1"}
        if legacy:
            legacy_audit_rows.append({
                "task_id": task, "base_task_id": base, "image_id": row.get("image_id", ""), "building_id": row.get("building_id", ""),
                "legacy_curated_rank": legacy.get("reserve_rank", legacy.get("selection_rank", "")), "legacy_curated_reason": legacy.get("selection_reason", legacy.get("notes", "")),
                "legacy_curated_manifest_sha256": sha256_file(reserve_pool) if reserve_pool else "", "history_overlap": history_overlap,
                "selected": False, "not_selected_reason": "history_overlap_hard_exclusion" if history_overlap else "candidate_only_precloseout",
            })
        if excluded or str(row.get("eligible_after_exclusion", "")).lower() not in {"true", "1"}:
            continue
        pair_count = int(float(row.get("gt_pair_count") or 0))
        candidate_rows.append({
            **row,
            "legacy_human_curated_candidate": bool(reserve.get(task) or reserve.get(base)),
            "legacy_curated_rank": (reserve.get(task) or reserve.get(base) or {}).get("reserve_rank", (reserve.get(task) or reserve.get(base) or {}).get("selection_rank", "")),
            "legacy_curated_reason": (reserve.get(task) or reserve.get(base) or {}).get("selection_reason", (reserve.get(task) or reserve.get(base) or {}).get("notes", "")),
            "legacy_curated_manifest_sha256": sha256_file(reserve_pool) if reserve_pool and (reserve.get(task) or reserve.get(base)) else "",
            "legacy_curated_selected_at": legacy.get("selected_at", "unknown_not_recorded" if legacy else ""),
            "legacy_curated_selection_stage": legacy.get("selection_stage", "legacy_c2_reverse_manual_screen" if legacy else ""),
            "legacy_curated_selection_blind_to_c1_outcomes": legacy.get("selection_blind_to_c1_outcomes", "not_evaluable" if legacy else ""),
            "legacy_curated_selector": legacy.get("selector", "unknown_not_recorded" if legacy else ""),
            "legacy_curated_original_pool": legacy.get("original_pool", legacy.get("source_pool", "unknown_not_recorded" if legacy else "")),
            "building_id": row.get("building_id", ""),
            "source_split": row.get("source_pool", ""),
            "g_model_struct_input_pair_count": pair_count,
            "d_model_feat": "", "g_model_struct": "", "d_cal_A": "",
            "risk_design_A": "", "risk_design_A_status": "pending_complete_C1",
            "risk_design_stratum": "", "risk_design_stratum_status": "provisional_not_frozen",
            "risk_assist_candidate": "pending_c1_risk_freeze", "risk_route_candidate": "pending_c2b_confirmation",
            # Common-anchor is a C2-B assignment role. The legacy inventory has
            # no anchor flags, so every reference-ready remaining task may be
            # considered by the frozen design simulation.
            "anchor_eligible": str(row.get("geometry_gold_ready", "")).lower() in {"true", "1"},
            "bridge_eligible": str(row.get("eligible_for_reserve_candidate", "")).lower() in {"true", "1"},
            "reference_status": "reference_ready" if str(row.get("geometry_gold_ready", "")).lower() in {"true", "1"} else "pending_adjudication",
            "scope_status": row.get("expert_review_status", ""), "history_exclusion": False,
            "p1_c1_overlap": history_overlap, "future_t1_v1_exclusion": False,
            "future_holdout_manifest_status": "not_provided_rehearsal_only",
            "candidate_role_source": "legacy_human_curated_candidate" if reserve.get(task) or reserve.get(base) else "full_candidate_inventory_precloseout",
        })
    write_csv(output, candidate_rows, list(candidate_rows[0]) if candidate_rows else ["task_id"])
    legacy_audit = [*legacy_audit_rows, *[{
        "task_id": row.get("task_id", ""), "base_task_id": row.get("base_task_id", ""), "image_id": row.get("image_id", ""), "building_id": row.get("building_id", ""),
        "legacy_curated_rank": row.get("legacy_curated_rank", ""), "legacy_curated_reason": row.get("legacy_curated_reason", ""), "legacy_selected_at": row.get("legacy_curated_selected_at", ""), "legacy_selector": row.get("legacy_curated_selector", ""), "legacy_curated_manifest_sha256": row.get("legacy_curated_manifest_sha256", ""),
        "latest_human_reviewed": row.get("latest_human_reviewed", ""), "legacy_proxy": row.get("legacy_proxy", ""), "unreviewed": row.get("unreviewed", ""),
        "history_overlap": row.get("p1_c1_overlap", ""), "feature_readiness": row.get("risk_design_A_status", ""), "risk_design_A": "", "risk_design_stratum": row.get("risk_design_stratum", ""),
        "anchor_eligible": row.get("anchor_eligible", ""), "bridge_eligible": row.get("bridge_eligible", ""), "selected": False, "not_selected_reason": "candidate_only_precloseout",
    } for row in candidate_rows if str(row.get("legacy_human_curated_candidate", "")).lower() in {"true", "1"}]]
    write_csv(output.parent / "c2_legacy_reverse_candidate_audit.csv", legacy_audit, list(legacy_audit[0]) if legacy_audit else ["task_id"])
    return output


def materialize_c2b_task_eligibility_evidence(
    inventory_csv: Path, task_risk_csv: Path, reference_csv: Path, assignment_paths: list[Path], output_csv: Path,
) -> dict[str, Any]:
    """Join every C2-B gate on image/base_task identity with immutable source SHAs."""
    inventory = read_csv(inventory_csv)
    risk = {(row.get("image_id", ""), row.get("base_task_id", "")): row for row in read_csv(task_risk_csv)}
    reference = {(row.get("image_id", ""), row.get("base_task_id", "")): row for row in read_csv(reference_csv)}
    history = {value for path in assignment_paths for row in read_csv(path) for value in (row.get("task_id", ""), row.get("base_task_id", "")) if value}
    rows = []
    for item in inventory:
        key = (item.get("image_id", ""), item.get("base_task_id", ""))
        task = item.get("task_id", "")
        risk_row, reference_row = risk.get(key, {}), reference.get(key, {})
        history_overlap = task in history or item.get("base_task_id", "") in history
        source_ok = str(item.get("source_split_allowed", "")).lower() in {"true", "1"}
        holdout_ok = str(item.get("future_holdout_clear", "")).lower() in {"true", "1"}
        scope_ok = str(reference_row.get("final_scope") or item.get("scope_status") or item.get("final_scope", "")).lower() == "in_scope"
        reference_ok = str(reference_row.get("geometry_reference_ready") or item.get("reference_status", "")).lower() in {"true", "1", "reference_ready"}
        feature_ok = bool(risk_row.get("risk_design_vector_A")) and bool(risk_row.get("risk_design_score_A"))
        risk_ok = str(risk_row.get("risk_status", "")) == "frozen"
        reasons = []
        if history_overlap: reasons.append("history_overlap")
        if not source_ok: reasons.append("source_split_not_clear")
        if not holdout_ok: reasons.append("future_holdout_not_clear")
        if not scope_ok: reasons.append("scope_not_in_scope")
        if not reference_ok: reasons.append("reference_not_ready")
        if not feature_ok: reasons.append("risk_feature_not_ready")
        if not risk_ok: reasons.append("risk_not_frozen")
        rows.append({
            "image_id": item.get("image_id", ""), "base_task_id": item.get("base_task_id", ""), "task_id": task,
            "building_id": item.get("building_id", ""), "source_split_allowed": source_ok, "future_holdout_clear": holdout_ok,
            "history_overlap": history_overlap, "scope_ready": scope_ok, "reference_ready": reference_ok,
            "feature_ready": feature_ok, "risk_ready": risk_ok, "assignment_eligible": not reasons,
            "exclusion_reason": ";".join(reasons), "inventory_sha256": sha256_file(inventory_csv),
            "task_risk_sha256": sha256_file(task_risk_csv), "reference_sha256": sha256_file(reference_csv),
        })
    write_csv(output_csv, rows)
    return {"n_tasks": len(rows), "n_eligible": sum(str(row["assignment_eligible"]).lower() == "true" for row in rows), "sha256": sha256_file(output_csv)}


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
    completion_disposition: Path | None = None,
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
    export_sha = _aggregate_sha(export_rows)
    pipeline_files = sorted((Path(__file__).parent.rglob("*.py")), key=lambda path: path.as_posix())
    code_pipeline_sha = _aggregate_sha(_manifest_rows(pipeline_files))
    _active_root, active_source_files = resolve_active_log_files(active_log)
    fixed_sources = {
        "manual_assignment": manual_assignment, "semi_assignment": semi_assignment,
        "worker_distribution": worker_distribution, "gt_export": gt_export,
        "planned_mapping": PLANNED_MAPPING, "reserve_pool": RESERVE_POOL,
        "candidate_inventory": CANDIDATE_INVENTORY,
    }
    if c1_preannotation_feature_csv is not None:
        fixed_sources["c1_preannotation_feature"] = c1_preannotation_feature_csv
    p1_source_files = sorted((path for path in p1_closeout_dir.iterdir() if path.is_file()), key=lambda path: path.name.lower())
    stage_active_log_provenance = _stage_active_log_provenance(p1_closeout_dir, active_log)
    review_sources = {name: path for name, path in {
        "duplicate_adjudication": duplicate_adjudication, "structural_disposition": structural_disposition,
        "project_independence_provenance": project_independence_disposition,
        "annotation_independence_disposition": independence_disposition, "scope_adjudication": scope_adjudication,
        "reference_amendment": reference_amendment, "outside_assignment_disposition": outside_assignment_disposition,
        "completion_disposition": completion_disposition,
    }.items() if path is not None}
    analysis_input_rows = _manifest_rows([*export_files, *active_source_files, *fixed_sources.values(), *p1_source_files, *review_sources.values()])
    analysis_input_bundle_sha = _aggregate_sha(analysis_input_rows)
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
    review_snapshots = {name: _snapshot(path, snapshots, "dispositions") for name, path in review_sources.items()}
    all_sources = [*export_files, *active_source_files, *fixed_sources.values(), *p1_source_files, *review_sources.values()]
    source_rows = _manifest_rows(all_sources)
    input_roles = {path.resolve(): name for name, path in fixed_sources.items()}
    for row in source_rows:
        row["input_role"] = input_roles.get(Path(row["path"]).resolve(), "")
    all_snapshots = [*snapshot_exports, *snapshot_active, *fixed_snapshots.values(), *p1_snapshots, *review_snapshots.values()]
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
    materialize_canonical_evidence(
        snapshot_exports, output_dir / "c1_canonical_annotations.csv", output_dir,
        input_status=input_status, version_disposition_csv=output_dir / "c1_annotation_version_disposition.csv",
    )
    project_independence_evidence_summary = materialize_project_independence_provenance(
        output_dir / "c1_canonical_meta_observations.csv", output_dir,
    )
    independence_summary = materialize_independence(
        output_dir / "c1_canonical_meta_observations.csv", output_dir,
        disposition_csv=review_snapshots.get("annotation_independence_disposition"),
        project_disposition_csv=review_snapshots.get("project_independence_provenance"),
    )
    structural_summary = materialize_structural_validation(
        output_dir / "c1_canonical_annotations.csv", output_dir / "c1_canonical_geometry.jsonl", output_dir,
        disposition_csv=review_snapshots.get("structural_disposition"),
    )
    canonical_summary["failure_attribution_counts"] = structural_summary["failure_attribution_counts"]
    canonical_summary["structural_validation_summary"] = structural_summary
    write_json(output_dir / "c1_canonicalization_summary.json", canonical_summary)
    materialize_geometry_consensus(
        output_dir / "c1_canonical_geometry.jsonl", output_dir, input_status=input_status,
    )
    completion_summary = materialize_completion_support(
        snapshot_exports, [fixed_snapshots["manual_assignment"], fixed_snapshots["semi_assignment"]],
        output_dir / "c1_runtime_task_mapping.csv", output_dir / "c1_canonical_annotations.csv",
        output_dir / "c1_canonical_geometry.jsonl", output_dir,
        completion_disposition_csv=review_snapshots.get("completion_disposition"),
    )
    roster_summary = materialize_analysis_rosters(
        output_dir / "c1_worker_completion_audit.csv", output_dir / "c1_canonical_annotations.csv", output_dir,
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
    predictive_path = output_dir / "p1_to_c1_descriptive_directional_check.csv"
    predictive_summary = materialize_predictive_association(predictive_path, output_dir) if predictive_path.exists() else {"component_status": "not_evaluable", "reason": "p1_to_c1_source_missing"}

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
        formal=formal,
    )
    preannotation_summary = materialize_preannotation_features(
        [fixed_snapshots["manual_assignment"], fixed_snapshots["semi_assignment"]], fixed_snapshots["candidate_inventory"], output_dir,
        frozen_feature_csv=fixed_snapshots.get("c1_preannotation_feature"),
    )
    readiness = materialize_measurement_readiness(
        output_dir / "c1_worker_completion_audit.csv", output_dir / "c1_gt_quality_analysis.csv",
        output_dir / "geometry_worker_task_loo_analysis.csv", output_dir / "structural_validation_analysis.csv", output_dir,
        canonical_closed=bool(final_canonical_summary.get("C1_CANONICAL_CLOSED")),
        collection_window_closed=False,
        eligibility_csv=output_dir / "c1_row_analysis_eligibility.csv",
        preannotation_feature_ready=bool(preannotation_summary.get("n_ready")),
    )
    readiness["method_contract"] = "Pilot->P1->C1->C2-B->C2-A-RP->T1->V1"
    readiness["git_commit_sha"] = git_state["git_commit_sha"]
    readiness["worktree_clean"] = bool(git_state["clean"])
    write_json(output_dir / "c1_measurement_freeze_manifest.json", readiness)
    raw_task_pool = _candidate_task_pool(
        fixed_snapshots["candidate_inventory"], [fixed_snapshots["manual_assignment"], fixed_snapshots["semi_assignment"]],
        output_dir / "c2b_candidate_task_pool_raw.csv", fixed_snapshots["reserve_pool"],
    )
    risk_summary = materialize_task_risk(
        raw_task_pool, Path("output/layout_json"), output_dir / "c1_preannotation_task_features.csv", output_dir,
        input_status=input_status,
        checkpoint=Path("ckpt/mp3d_layout_HOHO_layout_aug_efficienthc_Transen1_resnet34/ep300.pth"),
        reference_dir=Path("data/mp3d_layout/train_no_occ/img"), extract_lhfeat=False,
        risk_contract=RISK_DESIGN_CONTRACT,
        c1_freeze_manifest=output_dir / "c1_measurement_freeze_manifest.json",
    )
    task_pool = output_dir / "c2_task_risk_inventory.csv"
    shutil.copy2(task_pool, output_dir / "c2b_candidate_task_pool.csv")
    c2b_evidence_summary = materialize_c2b_task_eligibility_evidence(
        fixed_snapshots["candidate_inventory"], task_pool, output_dir / "c1_task_outcome_reference.csv",
        [fixed_snapshots["manual_assignment"], fixed_snapshots["semi_assignment"]], output_dir / "c2b_task_eligibility_evidence.csv",
    )
    parameter_summary = materialize_design_parameters(
        output_dir / "c1_gt_quality_analysis.csv", output_dir / "c1_task_risk_reference.csv", output_dir / "structural_validation_analysis.csv",
        output_dir / "c1_worker_completion_audit.csv", output_dir,
    )
    profile_summary = materialize_c2b_design_worker_profile(
        output_dir / "c1_worker_completion_audit.csv", output_dir / ("c1_three_track_worker_state_formal.csv" if formal else "c1_three_track_worker_state.csv"),
        output_dir / "c1_c2_design_parameters.csv", output_dir / "c1_measurement_readiness_by_worker.csv", output_dir,
    )
    profile = output_dir / "c2b_design_worker_profile.csv"
    design_manifest = _candidate_design_manifest(task_pool, profile, output_dir / "c2b_candidate_design_manifest.json")
    if not json.loads(design_manifest.read_text(encoding="utf-8")).get("candidate_designs"):
        c2_summary = {"candidate_only": True, "launch_ready": False, "failure_reason": "risk_pool_insufficient_no_assignment_eligible_tasks", "n_feasible_candidate_designs": 0}
        write_csv(output_dir / "c2_candidates" / "c2b_design_candidates.csv", [], ["design_id", "feasible", "failure_reason"])
        write_csv(output_dir / "c2_candidates" / "c2b_worker_task_graph_audit.csv", [], ["design_id", "worker_task_graph_connected"])
        write_csv(output_dir / "c2_candidates" / "candidate_C2B_assignment.csv", [], ["worker_id", "task_id", "assignment_launch_allowed"])
    else:
        try:
            c2_summary = c2b.materialize(
                task_pool, profile, design_manifest,
                output_dir / "c2_candidates", input_status=input_status,
                eligibility_evidence_csv=output_dir / "c2b_task_eligibility_evidence.csv",
            )
        except ValueError as exc:
            c2_summary = {"candidate_only": True, "launch_ready": False, "failure_reason": str(exc)}
    _copy_alias(output_dir / "c2_candidates" / "c2b_design_candidates.csv", output_dir / "c2b_candidate_designs.csv")
    _copy_alias(output_dir / "c2_candidates" / "c2b_worker_task_graph_audit.csv", output_dir / "c2b_worker_task_graph_audit.csv")
    _copy_alias(output_dir / "c2_candidates" / "candidate_C2B_assignment.csv", output_dir / "candidate_C2B_assignment.csv")

    dependency_contracts = [
        Path("docs/thesis_main/geometry_loo_candidate_rule_manifest_v1.json"),
        Path("docs/thesis_main/c1_geometry_parser_amendment_v1.json"),
        Path("docs/thesis_main/C1_PRECLOSEOUT_AUDIT_FIELD_CONTRACT_v1.md"),
        Path("docs/thesis_main/C1_C2_ARTIFACT_FIELD_CONTRACT_v1.md"),
        RISK_DESIGN_CONTRACT,
        Path("docs/thesis_main/C2B_DESIGN_SELECTION_THRESHOLDS.json"),
        Path("config/mp3d_layout/HOHO_layout_aug_efficienthc_Transen1_resnet34.yaml"),
        Path("ckpt/mp3d_layout_HOHO_layout_aug_efficienthc_Transen1_resnet34/ep300.pth"),
    ]
    dependency_rows = _manifest_rows([*pipeline_files, *fixed_snapshots.values(), *snapshot_exports, *snapshot_active, *p1_snapshots, *review_snapshots.values(), *(path for path in dependency_contracts if path.exists())])
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
        "active_time_ledger_summary": active_ledger_summary,
        "outside_assignment_summary": outside_summary,
        "geometry_loo_summary": {"n_pairwise_rows": len(pairwise_rows), "n_loo_rows": len(loo_rows)},
        "c2b_design_worker_profile_summary": profile_summary,
        "c1_c2_design_parameter_summary": parameter_summary,
        "c1_preannotation_feature_summary": preannotation_summary,
        "c1_measurement_readiness": readiness,
        "three_track_worker_state_summary": three_track_summary,
        "c2_candidate_pool_summary": {
            "n_inventory_tasks": len(read_csv(fixed_snapshots["candidate_inventory"])),
            "n_tasks": len(read_csv(task_pool)),
            "source": "full_candidate_inventory_precloseout",
            "future_holdout_manifest_status": "not_provided_rehearsal_only",
        },
        "c2_task_risk_summary": risk_summary,
        "c2b_task_eligibility_evidence_summary": c2b_evidence_summary,
        "p1_to_c1_predictive_summary": predictive_summary,
        "C1_CANONICAL_CLOSED": bool(readiness["C1_CANONICAL_CLOSED"]),
        "C1_MEASUREMENT_FROZEN": bool(readiness["C1_MEASUREMENT_FROZEN"]),
        "C2B_RISK_DESIGN_FROZEN": False,
        "C2B_DESIGN_FROZEN": False,
        "C2B_ASSIGNMENT_MATERIALIZED": False,
        "C2B_LAUNCH_READY": False,
        "C2B_DESIGN_READY": bool(readiness["C2B_DESIGN_READY"]),
        "formal_closeout_ready": formal and bool(readiness["C1_MEASUREMENT_FROZEN"]), "profile_frozen": False, "c2_launch_ready": False,
        "formal_mode_executed": formal, "formal_audit_complete": formal and bool(readiness["C1_CANONICAL_CLOSED"]),
        "c1_evidence_frozen": False, "c2_design_frozen": False, "c2_assignment_materialized": False,
        "formal_results_materialized": formal and final_canonical_summary["formal_audit_complete"], "c2_candidate_only": not formal,
        "chain_gate": {"legacy_diagnostic_chain_consumed": False},
        "operational_reference_summary": chain.get("operational_reference_summary", {}),
        "strong_global_model_audit": model_audit,
        "c2b_candidate_summary": c2_summary,
        "final_canonical_closeout_summary": final_canonical_summary,
        "blockers": [*(["partial_c1_collection"] if not formal else []), *final_canonical_summary["blockers"], "c2b_not_confirmed"],
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
    parser.add_argument("--run-date", help="immutable output label, e.g. 20260724_r2")
    parser.add_argument("--c1-preannotation-feature-csv", type=Path, help="frozen pre-annotation C1 model feature table")
    args = parser.parse_args(argv)
    print(json.dumps(materialize(
        args.export_dir, args.active_log, args.manual_assignment, args.semi_assignment,
        args.worker_distribution, args.gt_export, args.p1_closeout_dir,
        args.output_root, input_status=args.input_status, run_date=args.run_date,
        c1_preannotation_feature_csv=args.c1_preannotation_feature_csv,
    ), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
