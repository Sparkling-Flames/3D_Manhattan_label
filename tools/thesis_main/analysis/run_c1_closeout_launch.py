"""Two-day fail-closed C1 closeout and C2-B launch orchestration."""

from __future__ import annotations

import argparse
import csv
import importlib.metadata
import json
import platform
import subprocess
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np

_PROJECT_ROOT = Path(__file__).resolve().parents[3]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from tools.thesis_main.analysis import build_c2_assignment_manifest_from_c1_gaps as c2b
from tools.thesis_main.analysis.active_log_utils import freeze_active_log_snapshot, validate_active_log_freeze_manifest
from tools.thesis_main.analysis.run_c1_precloseout_rehearsal import _aggregate_sha, _manifest_rows, materialize as materialize_c1
from tools.thesis_main.analysis.materialize_c2b_task_eligibility import materialize as materialize_c2b_task_eligibility
from tools.thesis_main.analysis.materialize_c2_task_risk import materialize_formal as materialize_task_risk
from tools.thesis_main.analysis.c1_c2_mainline import formal_git_state
from tools.thesis_main.analysis.c1_c2_mainline import materialize_c2b_design_worker_profile
from tools.thesis_main.analysis.materialize_c1_c2_design_parameters import materialize as materialize_design_parameters
from tools.thesis_main.analysis.derive_c2b_design_thresholds import derive_threshold_manifest, validate_formula_contract
from tools.thesis_main.analysis.materialize_c2_task_risk import _feature_audit_passes, freeze_feature_reference, refresh_feature_freeze_approval
from tools.thesis_main.analysis.materialize_c2b_legacy_provenance import materialize as materialize_legacy_provenance
from tools.thesis_main.analysis.materialize_p1_post_closeout_evidence_correction import materialize as materialize_p1_correction
from tools.thesis_main.analysis.materialize_p1_post_closeout_geometry_scores import materialize_scores as materialize_p1_geometry
from tools.thesis_main.analysis.c2b_static_evidence import (
    candidate_scene_mapping_key,
    materialize_history_overlap,
    materialize_building_registry_from_scene_mapping,
    materialize_p1_integrity_bundle,
    materialize_reference_candidate_leakage,
    materialize_split_proposals,
    materialize_static_freeze_manifest,
    materialize_static_model_risk,
    validate_p1_integrity_bundle,
)
from tools.thesis_main.analysis.vfinal_artifact_utils import sha256_file
from tools.thesis_main.registry.hohonet_feature_backend import extract_orbit_descriptors


COMMAND_ARTIFACT_CONTRACT = {
    "expand-building-registry": {
        "outputs": ("authoritative_building_registry.csv",),
    },
    "prepare-c2b-static": {
        "outputs": ("c2b_static_freeze_manifest.json", "c2b_source_holdout_split_proposals.summary.json"),
    },
    "freeze-c1": {
        "outputs": ("c1_active_log_freeze_manifest.json", "c1_collection_closure_manifest.json"),
    },
    "audit-c1": {
        "requires": (("freeze-c1", "c1_active_log_freeze_manifest.json"), ("freeze-c1", "c1_collection_closure_manifest.json")),
        "outputs": ("formal_audit_summary.json", "c1_measurement_freeze_manifest.json"),
    },
    "finalize-c1": {
        "requires": (("audit-c1", "formal_audit_summary.json"), ("audit-c1", "c1_measurement_freeze_manifest.json")),
        "outputs": ("c1_evidence_freeze_manifest.json",),
    },
    "design-c2b": {
        "requires": (("prepare-c2b-static", "c2b_static_freeze_manifest.json"), ("finalize-c1", "c1_evidence_freeze_manifest.json")),
        "outputs": ("c2_task_risk.summary.json", "c2b_evidence_freeze_envelope.json", "c2b_design.summary.json"),
    },
    "build-c2b": {
        "requires": (("design-c2b", "c2_task_risk.summary.json"), ("design-c2b", "c2b_design.summary.json")),
        "outputs": ("assignment_manifest_C2B.csv", "c2b_launch_ready_report.json"),
    },
    "close-c1-and-plan-c2b": {
        "requires": (("finalize-c1", "c1_evidence_freeze_manifest.json"), ("prepare-c2b-static", "c2b_static_freeze_manifest.json")),
        "outputs": ("close_c1_and_plan_c2b_state.json",),
    },
    "check-command-contract": {"outputs": ()},
}


def validate_runbook_command_contract(runbook: Path) -> dict[str, Any]:
    text = runbook.read_text(encoding="utf-8")
    missing = []
    for command, contract in COMMAND_ARTIFACT_CONTRACT.items():
        if command not in text:
            missing.append(f"missing_command:{command}")
        for artifact in contract.get("outputs", ()):
            if artifact not in text:
                missing.append(f"missing_output:{command}:{artifact}")
        for producer, artifact in contract.get("requires", ()):
            if producer not in COMMAND_ARTIFACT_CONTRACT or artifact not in COMMAND_ARTIFACT_CONTRACT[producer].get("outputs", ()):
                missing.append(f"unproduced_input:{command}:{artifact}")
    if "c2_task_risk_summary.json" in text:
        missing.append("deprecated_artifact_name:c2_task_risk_summary.json")
    return {"valid": not missing, "violations": missing, "command_count": len(COMMAND_ARTIFACT_CONTRACT)}


def _read(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as stream:
        return list(csv.DictReader(stream))


def _write(path: Path, rows: list[dict[str, Any]]) -> None:
    fields = list(dict.fromkeys(key for row in rows for key in row)) if rows else ["status"]
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields, extrasaction="ignore"); writer.writeheader(); writer.writerows(rows)


def _source_identity_aggregate(rows: list[dict[str, Any]]) -> str:
    """Hash source identity only; raw-snapshot bookkeeping must not change it."""
    return _aggregate_sha([{name: row[name] for name in ("path", "size", "sha256")} for row in rows])


def _require_approval(path: Path, evidence: Path, sha_field: str) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if payload.get("approved") is not True or payload.get(sha_field) != sha256_file(evidence):
        raise ValueError(f"approval_invalid_or_stale:{sha_field}")
    return payload


def _c2_source_images(rows: list[dict[str, str]]) -> set[str]:
    return {
        row.get("image_id", "") for row in rows
        if str(row.get("allocation", row.get("source_split_allowed", ""))).lower() in {"c2", "true", "1", "allowed"}
        and row.get("image_id")
    }


def _future_heldout_images(rows: list[dict[str, str]]) -> set[str]:
    return {
        row.get("image_id", "") for row in rows
        if row.get("image_id") and (
            str(row.get("allocation", "")).lower() in {"future_holdout", "t1", "v1", "holdout"}
            or str(row.get("future_holdout_clear", row.get("clear", ""))).lower() in {"false", "0", "held", "holdout", "blocked"}
        )
    }


def _final_risk_pool_gate(rows: list[dict[str, str]], threshold_manifest: Path) -> dict[str, Any]:
    thresholds = json.loads(threshold_manifest.read_text(encoding="utf-8"))
    values = thresholds.get("thresholds", {})
    required = (
        "minimum_eligible_task_count", "minimum_eligible_building_count",
        "minimum_ordinary_task_count", "minimum_stress_task_count",
    )
    approved = (
        thresholds.get("status") == "approved"
        and thresholds.get("formal_selection_allowed") is True
        and all(values.get(name) not in {None, ""} for name in required)
    )
    eligible = [row for row in rows if str(row.get("assignment_eligible", "")).lower() in {"true", "1"}]
    counts = Counter(row.get("risk_design_stratum", "") for row in eligible)
    buildings = {row.get("building_id", "") for row in eligible} - {""}
    observed = {
        "minimum_eligible_task_count": len(eligible),
        "minimum_eligible_building_count": len(buildings),
        "minimum_ordinary_task_count": counts["ordinary"],
        "minimum_stress_task_count": counts["stress"],
    }
    failures = [name for name in required if not approved or observed[name] < int(values.get(name) or 0)]
    return {"frozen": approved and not failures, "approved_thresholds": approved, "observed": observed, "failures": failures}


def _materialize_c2b_evidence_envelope(args: argparse.Namespace) -> dict[str, Any]:
    static = json.loads(args.static_freeze_manifest.read_text(encoding="utf-8"))
    source_approval = _require_approval(args.source_split_approval, args.source_split_evidence, "source_split_evidence_sha256")
    holdout_approval = _require_approval(args.future_holdout_approval, args.future_holdout_evidence, "future_holdout_evidence_sha256")
    split_summary_sha = static.get("artifacts", {}).get("split_proposals", {}).get("sha256", "")
    selected_proposal_id = str(source_approval.get("selected_proposal_id", "")).strip()
    split_approval_bound = (
        bool(selected_proposal_id)
        and selected_proposal_id == holdout_approval.get("selected_proposal_id")
        and source_approval.get("split_proposal_summary_sha256") == split_summary_sha
        and holdout_approval.get("split_proposal_summary_sha256") == split_summary_sha
    )
    artifacts = {
        "static_freeze_manifest": args.static_freeze_manifest,
        "feature_freeze_manifest": args.feature_freeze_manifest,
        "building_registry": args.building_registry,
        "source_split_evidence": args.source_split_evidence,
        "source_split_approval": args.source_split_approval,
        "future_holdout_evidence": args.future_holdout_evidence,
        "future_holdout_approval": args.future_holdout_approval,
        "history_overlap_audit": args.history_overlap_audit,
        "scope_registry": args.scope_registry,
        "reference_registry": args.reference_registry,
        "leakage_audit": args.feature_freeze_manifest.parent / "c2b_reference_candidate_leakage_audit.summary.json",
    }
    missing = [name for name, path in artifacts.items() if not path.exists()]
    static_feature = static.get("artifacts", {}).get("feature_freeze", {}).get("sha256", "")
    proposal_rows_raw = str(static.get("artifacts", {}).get("split_proposal_rows", {}).get("path", ""))
    proposal_rows_path = Path(proposal_rows_raw) if proposal_rows_raw else Path("__missing_split_proposal_rows__")
    proposal_rows = _read(proposal_rows_path) if proposal_rows_path.is_file() else []
    expected_allocations = {
        (row.get("image_id", ""), row.get("base_task_id", "")): row.get("allocation", "")
        for row in proposal_rows if row.get("proposal_id") == selected_proposal_id
    }

    def allocations(path: Path, *, holdout: bool = False) -> dict[tuple[str, str], str]:
        output: dict[tuple[str, str], str] = {}
        for row in _read(path):
            key = (row.get("image_id", ""), row.get("base_task_id", ""))
            allocation = str(row.get("allocation", "")).lower()
            if allocation in {"c2", "c2_source", "source", "allowed"}:
                normalized = "c2_source"
            elif allocation in {"future_holdout", "holdout", "t1", "v1"}:
                normalized = "future_holdout"
            elif holdout:
                normalized = "c2_source" if str(row.get("future_holdout_clear", "")).lower() in {"true", "1", "clear"} else "future_holdout"
            else:
                normalized = "c2_source" if str(row.get("source_split_allowed", "")).lower() in {"true", "1", "allowed"} else "future_holdout"
            output[key] = normalized
        return output

    source_allocations = allocations(args.source_split_evidence)
    holdout_allocations = allocations(args.future_holdout_evidence, holdout=True)
    selected_split_exact = bool(expected_allocations) and source_allocations == expected_allocations and holdout_allocations == expected_allocations
    bindings_ok = (
        not missing and static.get("static_evidence_frozen") is True
        and static_feature == sha256_file(args.feature_freeze_manifest)
        and split_approval_bound and selected_split_exact
    )
    rows_complete = True
    for path, status_fields in (
        (args.building_registry, ("registry_status", "reviewed_by", "reviewed_at")),
        (args.scope_registry, ("registry_status", "reviewed_by", "reviewed_at")),
        (args.reference_registry, ("registry_status", "reviewed_by", "reviewed_at")),
    ):
        rows = _read(path) if path.exists() else []
        rows_complete = rows_complete and bool(rows) and all(all(str(row.get(field, "")).strip() for field in status_fields) for row in rows)
    payload = {
        "schema_version": "paper_a_c2b_evidence_freeze_envelope_v1",
        "artifact_owner": "design-c2b", "artifacts": {
            name: {"path": path.resolve().as_posix(), "sha256": sha256_file(path)}
            for name, path in artifacts.items() if path.exists()
        },
        "source_split_approval": source_approval,
        "future_holdout_approval": holdout_approval,
        "selected_proposal_id": selected_proposal_id,
        "split_approval_bound": split_approval_bound,
        "selected_split_exact": selected_split_exact,
        "missing_artifacts": missing,
        "registry_rows_complete": rows_complete,
        "C2B_EVIDENCE_FROZEN": bindings_ok and rows_complete,
        "selected_design_frozen": False,
        "selected_task_reference_frozen": False,
        "capacity_approved": False,
    }
    path = args.output_dir / "c2b_evidence_freeze_envelope.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return payload


def _environment_manifest(checkpoint: Path, config: Path) -> dict[str, Any]:
    import torch

    packages = {}
    for name in (
        "torch", "torchvision", "numpy", "pandas", "scipy", "statsmodels",
        "scikit-learn", "Shapely", "PyYAML", "Pillow", "imageio",
    ):
        try: packages[name] = importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError: packages[name] = "missing"
    try:
        driver = subprocess.run(
            ["nvidia-smi", "--query-gpu=driver_version", "--format=csv,noheader"],
            capture_output=True, text=True, check=False,
        )
        driver_version = driver.stdout.splitlines()[0].strip() if driver.returncode == 0 and driver.stdout.strip() else ""
    except OSError:
        driver_version = ""
    device = torch.cuda.get_device_properties(0) if torch.cuda.is_available() else None
    lock_files = {
        name: _PROJECT_ROOT / "config" / name
        for name in ("paper_a_analysis_requirements.lock.txt", "paper_a_torch_requirements.lock.txt")
    }
    git_head = subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True, check=False).stdout.strip()
    diff = subprocess.run(["git", "diff", "--binary", "HEAD"], capture_output=True, check=False).stdout
    return {
        "schema_version": "paper_a_analysis_environment_v1", "python": platform.python_version(),
        "python_executable": sys.executable, "platform": platform.platform(), "packages": packages,
        "cuda_build": torch.version.cuda, "cuda_available": torch.cuda.is_available(),
        "gpu_name": torch.cuda.get_device_name(0) if torch.cuda.is_available() else "",
        "gpu_count": torch.cuda.device_count(),
        "gpu_total_memory_bytes": int(device.total_memory) if device else 0,
        "gpu_compute_capability": f"{device.major}.{device.minor}" if device else "",
        "nvidia_driver_version": driver_version,
        "checkpoint_sha256": sha256_file(checkpoint),
        "config_sha256": sha256_file(config), "formal_device": "cuda:0", "dtype": "float32",
        "physical_batch_size": 4, "automatic_device_fallback": False,
        "dependency_lock_sha256": {
            name: sha256_file(path) if path.exists() else ""
            for name, path in lock_files.items()
        },
        "git_head": git_head,
        "worktree_diff_sha256": __import__("hashlib").sha256(diff).hexdigest(),
    }


def _materialize_static_evidence_review_queues(
    inventory_csv: Path, legacy_manifest: Path, output_dir: Path,
) -> dict[str, Any]:
    """Create non-authoritative review queues for every formal C2-B registry.

    The queues deliberately contain no approved gate value.  They make the
    missing evidence visible before C1 closeout without allowing inventory
    booleans or image-name conventions to become formal evidence.
    """
    inventory = _read(inventory_csv)
    legacy_keys = {
        (row.get("image_id", ""), row.get("base_task_id", ""))
        for row in _read(legacy_manifest)
    }
    identities: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    for row in inventory:
        key = (str(row.get("image_id", "")).strip(), str(row.get("base_task_id", "")).strip())
        if not all(key) or key in seen:
            raise ValueError("candidate inventory requires unique image_id + base_task_id")
        seen.add(key)
        identities.append({
            "image_id": key[0], "base_task_id": key[1], "task_id": row.get("task_id", ""),
            "source_path": row.get("source_path", ""), "source_pool": row.get("source_pool", ""),
            "scene_id": row.get("scene_id", ""), "scene_key": row.get("scene_key", ""),
            "legacy_reverse_member": key in legacy_keys,
            "inventory_diagnostic_used_in_prescreen": row.get("used_in_prescreen", ""),
            "inventory_diagnostic_used_in_random_c1": row.get("used_in_random_c1_deprecated", ""),
            "inventory_diagnostic_geometry_gold_ready": row.get("geometry_gold_ready", ""),
            "inventory_diagnostic_scope_gold_ready": row.get("scope_gold_ready", ""),
        })

    by_scene: dict[str, dict[str, Any]] = {}
    for row in identities:
        scene_key, scene_key_source = candidate_scene_mapping_key(row)
        by_scene.setdefault(scene_key, {
            **row, "scene_mapping_key": scene_key, "scene_key_source": scene_key_source,
            "scene_key_status": "requires_human_validation", "building_id": "",
            "registry_status": "pending_scene_mapping_review", "reviewed_by": "", "reviewed_at": "",
        })
    scene_pilot = [by_scene[key] for key in sorted(by_scene)[:15]]
    scope_queue = [
        {**row, "final_scope": "", "registry_status": "pending_missing_or_conflicting_scope", "reviewed_by": "", "reviewed_at": ""}
        for row in identities
        if str(row.get("inventory_diagnostic_scope_gold_ready", "")).lower() not in {"true", "1"}
    ]
    reference_queue = [
        {**row, "geometry_reference_ready": "", "registry_status": "pending_missing_or_conflicting_reference", "reviewed_by": "", "reviewed_at": ""}
        for row in identities
        if str(row.get("inventory_diagnostic_geometry_gold_ready", "")).lower() not in {"true", "1"}
    ]
    queue_rows = {
        "authoritative_building_scene_mapping_pilot.review_queue.csv": scene_pilot,
        "scope_registry.minimal_review_queue.csv": scope_queue,
        "reference_registry.minimal_review_queue.csv": reference_queue,
    }
    outputs: dict[str, str] = {}
    for name, rows in queue_rows.items():
        path = output_dir / name
        _write(path, rows)
        outputs[name] = sha256_file(path)
    summary = {
        "schema_version": "paper_a_c2b_static_evidence_review_queues_v1",
        "n_tasks": len(identities), "formal_evidence_ready": False,
        "building_scene_pilot_count": len(scene_pilot),
        "scope_manual_review_count": len(scope_queue),
        "reference_manual_review_count": len(reference_queue),
        "inventory_sha256": sha256_file(inventory_csv),
        "legacy_manifest_sha256": sha256_file(legacy_manifest), "queue_sha256": outputs,
        "contract": "history is derived automatically; split proposals are generated separately; building review starts with at most 15 scene keys; scope/reference queues contain only missing/conflicting diagnostics; queues are non-authoritative",
    }
    (output_dir / "c2b_static_evidence_review_queues.summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8",
    )
    return summary


def prepare_c2b_static(args: argparse.Namespace) -> dict[str, Any]:
    args.output_dir.mkdir(parents=True, exist_ok=True)
    p1_dir = args.output_dir / "p1_integrity"
    correction = materialize_p1_correction(
        args.p1_closeout_dir / "prescreen_canonical_annotations.csv",
        [args.p1_closeout_dir / "p1_combined_exports_for_exact_copy_audit.json"],
        args.p1_closeout_dir / "prescreen_worker_admission.csv", p1_dir,
        initialization_import_json=list(getattr(args, "p1_initialization_import", []) or []),
    )
    geometry = materialize_p1_geometry(
        p1_dir / "p1_task_evidence_correction_v1.csv",
        args.p1_closeout_dir / "prescreen_canonical_annotations.csv",
        args.p1_closeout_dir / "prescreen_gold_status_audit.csv",
        args.p1_closeout_dir / "final_gold_records_v2_p1_closeout_corrected.jsonl", p1_dir,
    )
    p1_bundle = materialize_p1_integrity_bundle(p1_dir)
    legacy = materialize_legacy_provenance(args.legacy_manifest, args.inventory_csv, args.output_dir)
    evidence_review = _materialize_static_evidence_review_queues(
        args.inventory_csv, args.legacy_manifest, args.output_dir,
    )
    inventory_rows = _read(args.inventory_csv)
    declared_candidate_paths = {
        Path(row.get("source_path", ""))
        for row in inventory_rows
        if str(row.get("source_path", "")).strip()
    }
    missing_candidate_paths = sorted(str(path) for path in declared_candidate_paths if not path.exists())
    if not inventory_rows or len(declared_candidate_paths) != len(inventory_rows) or missing_candidate_paths:
        raise ValueError(
            "candidate inventory must bind one existing unique source_path per task; "
            f"rows={len(inventory_rows)}, unique_paths={len(declared_candidate_paths)}, "
            f"missing={missing_candidate_paths[:5]}"
        )
    candidate_paths = sorted(declared_candidate_paths)
    feature_manifest = args.output_dir / "c2_feature_freeze_manifest.json"
    candidate_cache = args.output_dir / "c2_candidate_lhfeat_cache.npz"
    if feature_manifest.exists() and candidate_cache.exists():
        feature = refresh_feature_freeze_approval(
            feature_manifest, args.feature_audit_threshold_manifest,
            checkpoint=args.checkpoint, config=args.config, reference_dir=args.reference_dir,
            candidate_inventory=args.inventory_csv,
        )
    else:
        feature = freeze_feature_reference(
            args.reference_dir, args.checkpoint, args.config,
            args.output_dir / "c2_feature_reference_cache.npz", feature_manifest,
            device=args.device, audit_threshold_manifest=args.feature_audit_threshold_manifest,
        )
        candidate_descriptors, candidate_audit = extract_orbit_descriptors(
            candidate_paths, args.checkpoint, args.config, device=args.device, batch_size=4, audit_seam=True,
        )
        ordered = [path.resolve().as_posix() for path in candidate_paths]
        np.savez_compressed(
            candidate_cache, paths=np.asarray(ordered),
            global_descriptors=np.stack([candidate_descriptors[path][0] for path in ordered]),
            local_descriptors=np.stack([candidate_descriptors[path][1] for path in ordered]),
        )
        feature.update({
            "candidate_descriptor_cache_path": candidate_cache.resolve().as_posix(),
            "candidate_descriptor_cache_sha256": sha256_file(candidate_cache),
            "candidate_inventory_sha256": sha256_file(args.inventory_csv),
            "candidate_descriptor_count": len(ordered), "candidate_extraction_audit": candidate_audit,
            "cache_reused_without_model_inference": False,
        })
    feature_thresholds = json.loads(args.feature_audit_threshold_manifest.read_text(encoding="utf-8"))
    candidate_circular_ready, candidate_seam_ready = _feature_audit_passes(
        feature.get("candidate_extraction_audit", {}),
        feature.get("candidate_extraction_audit", {}),
        feature_thresholds,
    )
    feature["candidate_off_grid_circular_robustness"] = candidate_circular_ready
    feature["candidate_seam_robustness"] = candidate_seam_ready
    feature["feature_audit_status"] = (
        "approved"
        if feature.get("circular_shift_invariant") is True
        and feature.get("seam_invariant") is True
        and candidate_circular_ready and candidate_seam_ready
        else "pending_threshold_approval_or_failed"
    )
    feature_manifest.write_text(json.dumps(feature, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    leakage = materialize_reference_candidate_leakage(
        args.reference_dir, args.reference_dir.parent / "label_cor",
        args.inventory_csv, args.layout_dir, args.output_dir,
    )
    feature["reference_candidate_leakage_audit_sha256"] = sha256_file(args.output_dir / "c2b_reference_candidate_leakage_audit.summary.json")
    feature["reference_candidate_leakage_status"] = leakage["status"]
    if not leakage["formal_feature_pool_allowed"]:
        feature["feature_audit_status"] = "failed_reference_candidate_leakage"
    feature_manifest.write_text(json.dumps(feature, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    static_risk = materialize_static_model_risk(
        feature_manifest, args.inventory_csv, args.output_dir / "c2b_static_model_risk.csv",
    )
    history = materialize_history_overlap(
        args.inventory_csv,
        p1_dir / "p1_task_evidence_correction_v1.csv",
        args.c1_assignment,
        args.output_dir / "history_overlap_audit.csv",
    )
    split: dict[str, Any] = {"status": "not_evaluable_missing_approved_building_registry"}
    if args.building_registry and args.building_registry.exists():
        split = materialize_split_proposals(
            args.inventory_csv, args.output_dir / "history_overlap_audit.csv",
            args.building_registry, args.output_dir / "c2b_static_model_risk.csv", args.output_dir,
        )
    environment = _environment_manifest(args.checkpoint, args.config)
    (args.output_dir / "paper_a_analysis_environment_manifest.json").write_text(json.dumps(environment, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    static_manifest = materialize_static_freeze_manifest(
        args.output_dir,
        {
            "p1_integrity": p1_dir / "p1_integrity_bundle_manifest.json",
            "feature_freeze": feature_manifest,
            "leakage_audit": args.output_dir / "c2b_reference_candidate_leakage_audit.summary.json",
            "leakage_audit_rows": args.output_dir / "c2b_reference_candidate_leakage_audit.csv",
            "reference_image_listing": args.output_dir / "c2b_reference_image_file_listing.csv",
            "reference_layout_listing": args.output_dir / "c2b_reference_layout_file_listing.csv",
            "candidate_image_listing": args.output_dir / "c2b_candidate_image_file_listing.csv",
            "candidate_layout_listing": args.output_dir / "c2b_candidate_layout_file_listing.csv",
            "history_overlap": args.output_dir / "history_overlap_audit.csv",
            "static_model_risk": args.output_dir / "c2b_static_model_risk.csv",
            "split_proposals": args.output_dir / "c2b_source_holdout_split_proposals.summary.json",
            "split_proposal_rows": args.output_dir / "c2b_source_holdout_split_proposals.csv",
            "split_disjointness_audit": args.output_dir / "c2b_source_holdout_split_disjointness_audit.csv",
            "environment": args.output_dir / "paper_a_analysis_environment_manifest.json",
        },
        code_sha256=_aggregate_sha(_manifest_rows([
            Path(__file__), _PROJECT_ROOT / "tools/thesis_main/analysis/c2b_static_evidence.py",
            _PROJECT_ROOT / "tools/thesis_main/analysis/materialize_c2_task_risk.py",
            _PROJECT_ROOT / "tools/thesis_main/registry/hohonet_feature_backend.py",
        ])),
    )
    return {
        "phase": "prepare-c2b-static", "p1_correction": correction,
        "p1_geometry": geometry, "p1_integrity_bundle": p1_bundle, "legacy": legacy,
        "evidence_review": evidence_review, "feature": feature,
        "leakage": leakage, "history": history, "static_risk": static_risk,
        "split_proposals": split, "static_freeze": static_manifest,
        "environment": environment,
    }


def expand_building_registry(args: argparse.Namespace) -> dict[str, Any]:
    return materialize_building_registry_from_scene_mapping(
        args.inventory_csv, args.approved_scene_mapping, args.output_csv,
    )


def check_command_contract(args: argparse.Namespace) -> dict[str, Any]:
    return validate_runbook_command_contract(args.runbook)


def preflight_calibration(args: argparse.Namespace) -> dict[str, Any]:
    required = {
        "environment": args.static_dir / "paper_a_analysis_environment_manifest.json",
        "feature_freeze": args.static_dir / "c2_feature_freeze_manifest.json",
        "p1_correction": args.static_dir / "p1_integrity" / "p1_post_closeout_correction_summary_v1.json",
        "p1_geometry": args.static_dir / "p1_integrity" / "p1_geometry_score_summary_v1.json",
        "p1_integrity_bundle": args.static_dir / "p1_integrity" / "p1_integrity_bundle_manifest.json",
        "legacy_audit": args.static_dir / "c2_legacy_reverse_candidate_audit.summary.json",
        "evidence_review": args.static_dir / "c2b_static_evidence_review_queues.summary.json",
        "leakage_audit": args.static_dir / "c2b_reference_candidate_leakage_audit.summary.json",
        "split_proposals": args.static_dir / "c2b_source_holdout_split_proposals.summary.json",
        "static_freeze": args.static_dir / "c2b_static_freeze_manifest.json",
    }
    blockers = [f"missing:{name}" for name, path in required.items() if not path.exists()]
    try:
        design_thresholds = json.loads(args.threshold_manifest.read_text(encoding="utf-8"))
        try:
            validate_formula_contract(design_thresholds)
        except ValueError:
            blockers.append("unapproved_or_incomplete:design_thresholds")
    except (OSError, json.JSONDecodeError, ValueError):
        blockers.append("invalid:design_thresholds")
    try:
        feature_thresholds = json.loads(args.feature_audit_threshold_manifest.read_text(encoding="utf-8"))
        feature_values = feature_thresholds.get("thresholds", {})
        feature_thresholds_ready = (
            feature_thresholds.get("status") == "approved"
            and feature_thresholds.get("formal_feature_freeze_allowed") is True
            and all(str(feature_thresholds.get(field, "")).strip() for field in ("approved_by", "approved_at"))
            and all(feature_values.get(field) not in {None, ""} for field in (
                "circular_relative_l2_max", "seam_relative_l2_q95",
                "minimum_circular_audited_image_count", "minimum_seam_audited_image_count",
            ))
            and feature_thresholds.get("fail_closed_rules", {}).get("require_finite_metrics") is True
        )
        if not feature_thresholds_ready:
            blockers.append("unapproved_or_incomplete:feature_thresholds")
    except (OSError, json.JSONDecodeError):
        blockers.append("invalid:feature_thresholds")
    feature_freeze: dict[str, Any] = {}
    if required["feature_freeze"].exists():
        feature_freeze = json.loads(required["feature_freeze"].read_text(encoding="utf-8"))
        if feature_freeze.get("feature_audit_status") != "approved":
            blockers.append("feature_freeze_not_approved")
    if required["p1_integrity_bundle"].exists() and not validate_p1_integrity_bundle(args.static_dir / "p1_integrity")["valid"]:
        blockers.append("p1_integrity_bundle_invalid")
    if required["leakage_audit"].exists():
        leakage = json.loads(required["leakage_audit"].read_text(encoding="utf-8"))
        if leakage.get("status") != "passed" or leakage.get("formal_feature_pool_allowed") is not True:
            blockers.append("reference_candidate_leakage_audit_failed")
    if required["split_proposals"].exists():
        split = json.loads(required["split_proposals"].read_text(encoding="utf-8"))
        if split.get("status") != "candidate_only" or split.get("approval_materialized") is not False:
            blockers.append("source_holdout_split_proposals_invalid")
    if required["static_freeze"].exists():
        static_freeze = json.loads(required["static_freeze"].read_text(encoding="utf-8"))
        if static_freeze.get("static_evidence_frozen") is not True:
            blockers.append("static_evidence_not_frozen")
    if required["environment"].exists():
        environment = json.loads(required["environment"].read_text(encoding="utf-8"))
        if not environment.get("cuda_available"): blockers.append("cuda_unavailable")
        if str(environment.get("python", "")).split(".")[:2] != ["3", "11"]: blockers.append("python_version_mismatch")
        if str(environment.get("packages", {}).get("torch", "")).split("+")[0] != "2.11.0": blockers.append("torch_version_mismatch")
        if str(environment.get("packages", {}).get("torchvision", "")).split("+")[0] != "0.26.0": blockers.append("torchvision_version_mismatch")
        if environment.get("cuda_build") != "12.8": blockers.append("cuda_build_mismatch")
        if not environment.get("nvidia_driver_version"): blockers.append("nvidia_driver_version_missing")
        if environment.get("physical_batch_size") != 4: blockers.append("physical_batch_size_mismatch")
        locks = environment.get("dependency_lock_sha256", {})
        if len(locks) != 2 or any(not value for value in locks.values()): blockers.append("dependency_lock_missing")
        if feature_freeze and any(
            environment.get(field) != feature_freeze.get(field)
            for field in ("checkpoint_sha256", "config_sha256")
        ):
            blockers.append("environment_feature_identity_mismatch")
    report = {
        "schema_version": "paper_a_calibration_preflight_v1", "ready": not blockers,
        "blockers": blockers, "static_artifacts": {name: {"path": str(path), "sha256": sha256_file(path) if path.exists() else ""} for name, path in required.items()},
        "next_stage": "freeze-c1" if not blockers else "resolve_preflight_blockers",
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return report


def _materialize_rehearsal_root_cause_report(summary: dict[str, Any]) -> dict[str, Any]:
    output_dir = Path(summary["output_dir"])
    readiness = json.loads((output_dir / "c1_measurement_freeze_manifest.json").read_text(encoding="utf-8"))
    closeout = json.loads((output_dir / "c1_final_canonical_closeout_summary.json").read_text(encoding="utf-8"))
    independence = json.loads((output_dir / "c1_independence_summary.json").read_text(encoding="utf-8"))
    model = json.loads((output_dir / "c1_task_adjusted_qgt_model_audit.json").read_text(encoding="utf-8"))
    design_thresholds = json.loads((_PROJECT_ROOT / "docs/thesis_main/C2B_DESIGN_SELECTION_THRESHOLDS.json").read_text(encoding="utf-8"))
    feature_thresholds = json.loads((_PROJECT_ROOT / "docs/thesis_main/C2B_FEATURE_AUDIT_THRESHOLDS.json").read_text(encoding="utf-8"))
    payload = {
        "schema_version": "paper_a_c1_c2b_root_cause_rehearsal_report_v1",
        "input_export_count": summary.get("n_export_files", 0),
        "state": {
            "formal_closeout_ready": bool(summary.get("formal_closeout_ready")),
            "profile_frozen": bool(summary.get("profile_frozen")),
            "c2_launch_ready": bool(summary.get("c2_launch_ready")),
            "assignment_rows": int(summary.get("c2b_assignment_row_count") or 0),
        },
        "owners": {
            "collection_closure": "freeze-c1", "formal_audit": "audit-c1",
            "c1_evidence_freeze_manifest.json": "finalize-c1",
            "c2b_static_freeze_manifest.json": "prepare-c2b-static",
            "c2b_evidence_freeze_envelope.json": "design-c2b",
            "assignment_manifest_C2B.csv": "build-c2b",
        },
        "collection": summary.get("completion_summary", {}),
        "three_axis_support_after_exclusion": closeout.get("support_after_exclusion", {}),
        "three_axis_freeze_status": {
            "Q_GT": readiness.get("Q_GT_FREEZE_STATUS"), "R_LOO": readiness.get("R_LOO_FREEZE_STATUS"),
            "F_struct": readiness.get("F_STRUCT_FREEZE_STATUS"),
        },
        "p1_integrity": summary.get("p1_integrity", {}),
        "independence": independence, "qgt_model": model,
        "feature_leakage": {"feature": summary.get("c2_task_risk_summary", {}), "leakage": {"status": "not_run_in_c1_stage"}},
        "split": {"status": "not_run_in_c1_stage", "approval_materialized": False},
        "risk_model_boundary": {"status": "not_run_until_design_c2b", "slope_model_form": ""},
        "design_threshold_blocker": {
            "status": design_thresholds.get("status"),
            "formula_contract_frozen": bool(design_thresholds.get("formula_contract_frozen")),
            "final_numeric_threshold_status": "pending_post_c1_sha_bound_derivation",
            "reviewer_input_approval_required": True,
        },
        "feature_threshold_blocker": {
            "status": feature_thresholds.get("status"), "formal_feature_freeze_allowed": feature_thresholds.get("formal_feature_freeze_allowed"),
            "null_thresholds": sorted(name for name, value in feature_thresholds.get("thresholds", {}).items() if value is None),
        },
        "closeout_blockers": summary.get("blockers", []),
    }
    path = output_dir / "c1_c2b_root_cause_rehearsal_report.json"
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return {"path": path.resolve().as_posix(), "sha256": sha256_file(path), **payload}


def rehearse_c1(args: argparse.Namespace) -> dict[str, Any]:
    summary = materialize_c1(
        args.export_dir, args.active_log, args.manual_assignment, args.semi_assignment,
        args.worker_distribution, args.gt_export, args.p1_closeout_dir, args.output_root,
        input_status="precloseout_rehearsal",
        c1_preannotation_feature_csv=getattr(args, "c1_preannotation_feature_csv", None),
        p1_integrity_dir=getattr(args, "p1_integrity_dir", None),
    )
    report = _materialize_rehearsal_root_cause_report(summary)
    return {"stage": "C1", "phase": "rehearsal", "output_dir": summary["output_dir"], "formal_closeout_ready": False, "review_required": True, "root_cause_report": report}


def freeze_c1(args: argparse.Namespace) -> dict[str, Any]:
    active = freeze_active_log_snapshot(
        args.source_live_root, args.frozen_root, args.collection_cutoff_server_time,
        args.operator, args.active_log_freeze_manifest,
    )
    closure_args = argparse.Namespace(
        export_dir=args.export_dir,
        manual_assignment=args.manual_assignment,
        semi_assignment=args.semi_assignment,
        c1_active_log_freeze_manifest=args.active_log_freeze_manifest,
        closure_time=args.collection_cutoff_server_time,
        operator=args.operator,
        late_submission_policy=args.late_submission_policy,
        output=args.collection_closure_manifest,
    )
    closure = build_collection_closure(closure_args)
    return {"stage": "C1", "phase": "freeze", "active_log": active, "collection_closure": closure}


def build_collection_closure(args: argparse.Namespace) -> dict[str, Any]:
    freeze_payload = json.loads(args.c1_active_log_freeze_manifest.read_text(encoding="utf-8"))
    frozen_root = Path(str(freeze_payload.get("frozen_root", "")))
    validate_active_log_freeze_manifest(args.c1_active_log_freeze_manifest, frozen_root)
    cutoff = datetime.fromisoformat(str(freeze_payload.get("collection_cutoff_server_time", "")).replace("Z", "+00:00"))
    closure = datetime.fromisoformat(str(args.closure_time).replace("Z", "+00:00"))
    cutoff = cutoff if cutoff.tzinfo else cutoff.replace(tzinfo=timezone.utc)
    closure = closure if closure.tzinfo else closure.replace(tzinfo=timezone.utc)
    if cutoff.astimezone(timezone.utc) != closure.astimezone(timezone.utc):
        raise ValueError("closure_time must equal the active-log collection cutoff")
    export_files = [path for directory in args.export_dir for path in directory.rglob("*.json")]
    assignment_files = [args.manual_assignment, args.semi_assignment]
    payload = {
        "schema_version": "paper_a_c1_collection_closure_v1",
        "c1_export_aggregate_sha256": _aggregate_sha(_manifest_rows(export_files)),
        "c1_active_log_freeze_manifest_sha256": sha256_file(args.c1_active_log_freeze_manifest),
        "c1_assignment_sha256": _aggregate_sha(_manifest_rows(assignment_files)),
        "collection_window_closed": True, "closure_time": args.closure_time,
        "operator": args.operator, "late_submission_policy": args.late_submission_policy,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return payload


def audit_c1(args: argparse.Namespace) -> dict[str, Any]:
    validate_active_log_freeze_manifest(args.c1_active_log_freeze_manifest, args.active_log)
    summary = materialize_c1(
        args.export_dir, args.active_log, args.manual_assignment, args.semi_assignment,
        args.worker_distribution, args.gt_export, args.p1_closeout_dir, args.output_root,
        input_status="formal", independence_disposition=args.independence_disposition,
        project_independence_disposition=args.project_independence_disposition,
        structural_disposition=args.structural_disposition,
        duplicate_adjudication=args.duplicate_adjudication,
        scope_adjudication=args.scope_adjudication,
        reference_amendment=args.reference_amendment,
        outside_assignment_disposition=args.outside_assignment_disposition,
        completion_disposition=args.completion_disposition,
        c1_preannotation_feature_csv=getattr(args, "c1_preannotation_feature_csv", None),
        c1_active_log_freeze_manifest=args.c1_active_log_freeze_manifest,
        collection_closure_manifest=args.collection_closure_manifest,
        p1_integrity_dir=getattr(args, "p1_integrity_dir", None),
    )
    return {
        "stage": "C1", "phase": "audit", "output_dir": summary["output_dir"],
        "formal_closeout_ready": bool(summary["formal_closeout_ready"]), "blockers": summary["blockers"],
    }


def finalize_c1(args: argparse.Namespace) -> dict[str, Any]:
    audit_path = args.output_dir / "formal_audit_summary.json"
    final_path = args.output_dir / "c1_final_canonical_closeout_summary.json"
    measurement_path = args.output_dir / "c1_measurement_freeze_manifest.json"
    if not all(path.exists() for path in (audit_path, final_path, measurement_path)):
        raise ValueError("finalize-c1 requires a complete formal audit bundle")
    audit, final, measurement = (json.loads(path.read_text(encoding="utf-8")) for path in (audit_path, final_path, measurement_path))
    adjudication = json.loads(args.adjudication_manifest.read_text(encoding="utf-8"))
    bundle_sha = audit.get("full_dependency_bundle_sha256", "")
    approved = adjudication.get("approved") is True and adjudication.get("input_bundle_sha256") == bundle_sha
    canonical_ready = bool(audit.get("C1_CANONICAL_CLOSED")) and bool(final.get("C1_CANONICAL_CLOSED", True))
    blockers = []
    if audit.get("input_status") != "formal": blockers.append("rehearsal_bundle_refused")
    if audit.get("method_contract") != "Pilot->P1->C1->C2-B->C2-A-RP->T1->V1" or not audit.get("git_commit_sha") or not audit.get("worktree_clean"):
        blockers.append("formal_method_contract_or_clean_commit_missing")
    if not canonical_ready: blockers.extend(final.get("canonical_blockers", []) or ["c1_canonical_not_closed"])
    if not measurement.get("C1_EVIDENCE_BUNDLE_FROZEN"): blockers.append("c1_evidence_bundle_not_frozen")
    collection_closed = audit.get("collection_closure", {}).get("status") == "validated" and measurement.get("collection_window_closed") is True
    if not collection_closed: blockers.append("collection_closure_missing_or_invalid")
    if audit.get("formal_closeout_ready") is not True or final.get("formal_closeout_ready") is not True or audit.get("blockers") or final.get("blockers"):
        blockers.append("formal_audit_or_closeout_blocked")
    if not approved: blockers.append("formal_closeout_adjudication_missing_invalid_or_stale")
    evidence_ready = canonical_ready and collection_closed and not blockers
    c2b_baseline_ready = bool(measurement.get("C2B_BASELINE_INPUT_FROZEN")) and evidence_ready
    c2b_blockers = [] if c2b_baseline_ready else ["q_gt_baseline_support_limited_or_not_frozen"]
    freeze = {"schema_version": "c1_measurement_freeze_envelope_v2", "method_contract": audit.get("method_contract", ""), "git_commit_sha": audit.get("git_commit_sha", ""), "C1_COLLECTION_INCOMPLETE": not collection_closed, "C1_CANONICAL_CLOSED": canonical_ready, "C1_MEASUREMENT_FROZEN": evidence_ready, "C1_EVIDENCE_BUNDLE_FROZEN": bool(measurement.get("C1_EVIDENCE_BUNDLE_FROZEN")) and evidence_ready, "C2B_BASELINE_INPUT_FROZEN": c2b_baseline_ready, "Q_GT_FREEZE_STATUS": measurement.get("Q_GT_FREEZE_STATUS", "pending"), "R_LOO_FREEZE_STATUS": measurement.get("R_LOO_FREEZE_STATUS", "pending"), "F_STRUCT_FREEZE_STATUS": measurement.get("F_STRUCT_FREEZE_STATUS", "pending"), "C2B_DESIGN_READY": c2b_baseline_ready, "C2B_RISK_DESIGN_FROZEN": False, "C2B_DESIGN_FROZEN": False, "C2B_ASSIGNMENT_MATERIALIZED": False, "C2B_LAUNCH_READY": False, "routing_profile_frozen": False, "formal_closeout_ready": evidence_ready, "full_dependency_bundle_sha256": bundle_sha, "adjudication_sha256": sha256_file(args.adjudication_manifest), "blockers": blockers, "c2b_baseline_blockers": c2b_blockers}
    freeze["state_machine"] = {name: bool(freeze[name]) for name in ("C1_COLLECTION_INCOMPLETE", "C1_CANONICAL_CLOSED", "C1_MEASUREMENT_FROZEN", "C2B_RISK_DESIGN_FROZEN", "C2B_DESIGN_FROZEN", "C2B_ASSIGNMENT_MATERIALIZED", "C2B_LAUNCH_READY")}
    (args.output_dir / "c1_evidence_freeze_manifest.json").write_text(json.dumps(freeze, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return {"day": 1, "phase": "measurement-freeze", "formal_closeout_ready": evidence_ready, "C1_CANONICAL_CLOSED": freeze["C1_CANONICAL_CLOSED"], "C1_MEASUREMENT_FROZEN": freeze["C1_MEASUREMENT_FROZEN"], "C2B_DESIGN_READY": freeze["C2B_DESIGN_READY"], "routing_profile_frozen": False, "blockers": blockers, "c2b_baseline_blockers": c2b_blockers}


def design_c2b(args: argparse.Namespace) -> dict[str, Any]:
    git_state = formal_git_state(_PROJECT_ROOT)
    if not git_state["clean"]:
        raise ValueError("formal C2-B design requires a committed clean worktree")
    closeout = json.loads(args.c1_closeout_summary.read_text(encoding="utf-8"))
    if closeout.get("method_contract") != "Pilot->P1->C1->C2-B->C2-A-RP->T1->V1" or not closeout.get("git_commit_sha"):
        raise ValueError("C1 freeze lacks the vFinal method contract or clean commit identity")
    if not closeout.get("C2B_BASELINE_INPUT_FROZEN"):
        raise ValueError("C1 Q_GT/process/independence baseline is not formally frozen")
    evidence_envelope = _materialize_c2b_evidence_envelope(args)
    if not evidence_envelope["C2B_EVIDENCE_FROZEN"]:
        return {
            "day": 2, "phase": "risk-plan", "risk_pool_formal_ready": False,
            "assignment_materialized": False, "design": {"candidate_only": True, "n_feasible_candidate_designs": 0},
            "state_machine": {"C2B_EVIDENCE_FROZEN": False, "C2B_RISK_DESIGN_FROZEN": False},
            "blockers": ["c2b_evidence_freeze_envelope_incomplete"],
        }
    source_rows, holdout_rows = _read(args.source_split_evidence), _read(args.future_holdout_evidence)
    c2_images = _c2_source_images(source_rows)
    held_images = _future_heldout_images(holdout_rows)
    if c2_images & held_images:
        raise ValueError("C2 source split overlaps future holdout")
    risk = materialize_task_risk(
        args.inventory_csv, args.layout_dir, args.c1_task_feature_csv, args.output_dir,
        checkpoint=args.checkpoint,
        c1_freeze_manifest=args.c1_closeout_summary, feature_freeze_manifest=args.feature_freeze_manifest,
        building_registry_csv=args.building_registry, device=args.device,
    )
    risk["git_commit_sha"] = git_state["git_commit_sha"]
    risk["worktree_clean"] = True
    risk["c2b_evidence_freeze_envelope_sha256"] = sha256_file(args.output_dir / "c2b_evidence_freeze_envelope.json")
    (args.output_dir / "c2_task_risk.summary.json").write_text(json.dumps(risk, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    evidence = materialize_c2b_task_eligibility(
        args.inventory_csv, args.output_dir / "c2_task_risk_inventory.csv",
        args.source_split_evidence, args.future_holdout_evidence,
        args.history_overlap_audit, args.scope_registry, args.reference_registry,
        args.feature_freeze_manifest, args.output_dir / "c2b_task_eligibility_evidence.csv",
    )
    evidence_rows = _read(args.output_dir / "c2b_task_eligibility_evidence.csv")
    _write(args.output_dir / "c2_selected_task_review_queue.csv", [row for row in evidence_rows if row.get("assignment_eligible", "").lower() in {"true", "1"}])
    preliminary_ready = bool(risk.get("C2_TASK_FEATURES_FROZEN")) and bool(closeout.get("C2B_BASELINE_INPUT_FROZEN"))
    parameter_summary: dict[str, Any] = {"formal_design_input_ready": False}
    profile_summary: dict[str, Any] = {"n_eligible": 0}
    derived_thresholds: dict[str, Any] = {}
    pool_gate: dict[str, Any] = {"frozen": False, "approved_thresholds": False, "observed": {}, "failures": ["design_inputs_not_ready"]}
    design_input_blocker = ""
    if preliminary_ready:
        c1_dir = args.c1_closeout_summary.parent
        parameter_summary = materialize_design_parameters(
            c1_dir / "c1_gt_quality_analysis.csv", args.output_dir / "c1_task_risk_reference.csv",
            c1_dir / "structural_validation_analysis.csv", c1_dir / "c1_worker_completion_audit.csv",
            args.output_dir, worker_state_csv=c1_dir / "c1_three_track_worker_state_formal.csv",
        )
        profile_summary = materialize_c2b_design_worker_profile(
            c1_dir / "c1_worker_completion_audit.csv", c1_dir / "c1_three_track_worker_state_formal.csv",
            args.output_dir / "c1_c2_design_parameters.csv", c1_dir / "c1_measurement_readiness_by_worker.csv",
            args.output_dir,
        )
        if parameter_summary["formal_design_input_ready"] and profile_summary["n_eligible"]:
            if not args.threshold_formula_contract.exists():
                design_input_blocker = "threshold_formula_contract_missing"
            elif not args.capacity_manifest.exists():
                design_input_blocker = "capacity_manifest_missing_before_threshold_review"
            else:
                try:
                    validate_formula_contract(json.loads(args.threshold_formula_contract.read_text(encoding="utf-8")))
                except (OSError, ValueError, TypeError, json.JSONDecodeError):
                    design_input_blocker = "threshold_formula_contract_invalid"
            if not design_input_blocker:
                threshold_review_request = {
                    "schema_version": "paper_a_c2b_threshold_input_review_request_v1",
                    "formula_contract_sha256": sha256_file(args.threshold_formula_contract),
                    "c1_design_parameters_sha256": sha256_file(args.output_dir / "c1_c2_design_parameters.csv"),
                    "capacity_manifest_sha256": sha256_file(args.capacity_manifest),
                    "candidate_enumeration_started": False,
                    "required_approval_schema_version": "paper_a_c2b_threshold_input_approval_v1",
                }
                (args.output_dir / "c2b_threshold_input_review_request.json").write_text(
                    json.dumps(threshold_review_request, indent=2, sort_keys=True) + "\n", encoding="utf-8",
                )
                if args.threshold_input_approval.exists():
                    derived_thresholds = derive_threshold_manifest(
                        args.threshold_formula_contract,
                        args.output_dir / "c1_c2_design_parameters.csv",
                        args.capacity_manifest,
                        args.threshold_input_approval,
                        args.threshold_manifest,
                    )
                    pool_gate = _final_risk_pool_gate(evidence_rows, args.threshold_manifest)
    ready = preliminary_ready and bool(parameter_summary["formal_design_input_ready"]) and bool(profile_summary["n_eligible"]) and pool_gate["frozen"]
    risk["task_eligibility_evidence"] = evidence
    risk["formal_ready"] = ready
    risk["C2B_ELIGIBLE_RISK_POOL_FROZEN"] = ready
    risk["eligible_pool_gate"] = pool_gate
    risk["derived_threshold_manifest_sha256"] = sha256_file(args.threshold_manifest) if derived_thresholds else ""
    risk["threshold_formula_contract_sha256"] = sha256_file(args.threshold_formula_contract) if args.threshold_formula_contract.exists() else ""
    risk["threshold_input_approval_sha256"] = sha256_file(args.threshold_input_approval) if args.threshold_input_approval.exists() else ""
    risk["state_machine"]["C2B_ELIGIBLE_RISK_POOL_FROZEN"] = ready
    risk["state_machine"]["C2B_RISK_DESIGN_FROZEN"] = ready
    (args.output_dir / "c2_task_risk.summary.json").write_text(json.dumps(risk, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    design_summary: dict[str, Any] = {"candidate_only": True, "n_feasible_candidate_designs": 0}
    if ready:
        worker_profile = args.output_dir / "c2b_design_worker_profile.csv"
        design_manifest = c2b.build_candidate_design_manifest(
            args.output_dir / "c2b_task_eligibility_evidence.csv", worker_profile,
            args.c1_closeout_summary, args.output_dir / "c2b_candidate_design_manifest.json",
            threshold_manifest=args.threshold_manifest,
            risk_summary=args.output_dir / "c2_task_risk.summary.json",
        )
        design_summary = c2b.enumerate_candidates(
            args.output_dir / "c2b_task_eligibility_evidence.csv", worker_profile,
            design_manifest, args.output_dir / "c2_candidates",
            c1_closeout_summary=args.c1_closeout_summary,
            risk_summary=args.output_dir / "c2_task_risk.summary.json",
            threshold_manifest=args.threshold_manifest,
            eligibility_evidence_csv=args.output_dir / "c2b_task_eligibility_evidence.csv",
        )
    if ready:
        blockers = []
    elif design_input_blocker:
        blockers = [design_input_blocker]
    elif preliminary_ready and parameter_summary["formal_design_input_ready"] and profile_summary["n_eligible"] and not args.threshold_input_approval.exists():
        blockers = ["threshold_input_approval_missing_before_candidate_enumeration"]
    elif preliminary_ready and (not parameter_summary["formal_design_input_ready"] or not profile_summary["n_eligible"]):
        blockers = ["c1_design_parameters_or_worker_profile_insufficient"]
    else:
        blockers = ["risk_or_task_eligibility_pool_insufficient"]
    return {"day": 2, "phase": "risk-plan", "risk_pool_formal_ready": ready, "assignment_materialized": False, "design": design_summary, "evidence_envelope": evidence_envelope, "state_machine": risk["state_machine"], "blockers": blockers}


def build_c2b(args: argparse.Namespace) -> dict[str, Any]:
    if not formal_git_state(_PROJECT_ROOT)["clean"]:
        raise ValueError("formal C2-B build requires a committed clean worktree")
    closeout = json.loads(args.c1_closeout_summary.read_text(encoding="utf-8"))
    risk = json.loads(args.risk_summary.read_text(encoding="utf-8"))
    if not closeout.get("C2B_BASELINE_INPUT_FROZEN"):
        raise ValueError("C1 Q_GT/process/independence baseline is not formally frozen")
    if risk.get("method_contract") != "Pilot->P1->C1->C2-B->C2-A-RP->T1->V1" or not risk.get("git_commit_sha") or not risk.get("worktree_clean"):
        raise ValueError("C2 task risk lacks the vFinal method contract or clean commit identity")
    if not risk.get("formal_ready") or not risk.get("state_machine", {}).get("C2B_RISK_DESIGN_FROZEN"):
        raise ValueError("C2 task risk is not formally frozen")
    if risk.get("derived_threshold_manifest_sha256") != sha256_file(args.threshold_manifest):
        raise ValueError("C2-B derived threshold manifest is stale or unbound")
    threshold_payload = json.loads(args.threshold_manifest.read_text(encoding="utf-8"))
    if (
        threshold_payload.get("schema_version") != "paper_a_c2b_design_selection_thresholds_v2"
        or threshold_payload.get("derivation", {}).get("capacity_manifest_sha256") != sha256_file(args.capacity_manifest)
    ):
        raise ValueError("C2-B thresholds were not mechanically derived from the frozen capacity")
    envelope_path = args.risk_summary.parent / "c2b_evidence_freeze_envelope.json"
    if not envelope_path.exists() or risk.get("c2b_evidence_freeze_envelope_sha256") != sha256_file(envelope_path):
        raise ValueError("C2 task risk lacks the bound evidence-freeze envelope")
    envelope = json.loads(envelope_path.read_text(encoding="utf-8"))
    if envelope.get("C2B_EVIDENCE_FROZEN") is not True:
        raise ValueError("C2-B evidence freeze is not ready")
    source_approval = _require_approval(args.source_split_approval, args.source_split_evidence, "source_split_evidence_sha256")
    holdout_approval = _require_approval(args.future_holdout_approval, args.future_holdout_evidence, "future_holdout_evidence_sha256")
    if (
        source_approval.get("selected_proposal_id") != envelope.get("selected_proposal_id")
        or holdout_approval.get("selected_proposal_id") != envelope.get("selected_proposal_id")
        or sha256_file(args.source_split_approval) != envelope.get("artifacts", {}).get("source_split_approval", {}).get("sha256")
        or sha256_file(args.future_holdout_approval) != envelope.get("artifacts", {}).get("future_holdout_approval", {}).get("sha256")
    ):
        raise ValueError("source/holdout approvals do not match the frozen evidence envelope")
    task_approval = _require_approval(
        args.selected_task_reference_manifest, args.task_eligibility_evidence,
        "task_eligibility_evidence_sha256",
    )
    if task_approval.get("reference_registry_sha256") != sha256_file(args.reference_registry):
        raise ValueError("selected_task_reference_approval_invalid_or_stale:reference_registry_sha256")
    if risk.get("output_inventory_sha256") != sha256_file(args.task_pool):
        raise ValueError("C2 task pool is not the inventory bound by the frozen risk summary")
    capacities = {row.get("worker_id", ""): row for row in _read(args.capacity_manifest)}
    if not capacities or len(capacities) != len(_read(args.capacity_manifest)):
        raise ValueError("C2-B capacity manifest requires unique worker rows")
    design = c2b.materialize_approved_assignment(
        args.candidate_dir, args.design_manifest, args.threshold_manifest,
        args.selected_design_approval, args.selected_task_reference_manifest,
        args.task_eligibility_evidence, args.c1_closeout_summary,
        args.risk_summary, args.output_dir,
    )
    assignment_path = args.output_dir / "assignment_manifest_C2B.csv"
    assignments, tasks = _read(assignment_path), {row["task_id"]: row for row in _read(args.task_pool)}
    assigned_by_worker = Counter(row["worker_id"] for row in assignments)
    for worker, count in assigned_by_worker.items():
        try:
            available = int(float(capacities[worker]["c2b_capacity"]))
        except (KeyError, TypeError, ValueError):
            raise ValueError(f"C2-B capacity is missing or invalid for worker {worker}")
        if count > available:
            raise ValueError(f"C2-B assignment exceeds frozen capacity for worker {worker}")
    distribution = [{
        **row,
        "image_path": row.get("image_path") or tasks.get(row["task_id"], {}).get("image_path") or tasks.get(row["task_id"], {}).get("source_path", ""),
    } for row in assignments]
    if any(not row.get("image_path") for row in distribution):
        raise ValueError("C2-B assigned task lacks a materializable image path")
    _write(args.output_dir / "worker_distribution_C2B.csv", distribution)
    worker_dir = args.output_dir / "worker_facing_distribution_C2B"; worker_dir.mkdir(parents=True, exist_ok=True)
    for worker in sorted({row["worker_id"] for row in distribution}):
        _write(worker_dir / f"worker_{worker}_C2B.csv", [row for row in distribution if row["worker_id"] == worker])
    selected_distribution = {row["task_id"]: row for row in distribution}
    imports = [{"data": {"image": row["image_path"], "title": task_id}, "meta": {"round_id": "C2-B"}} for task_id, row in sorted(selected_distribution.items())]
    import_path = args.output_dir / "label_studio_import_C2B.json"
    import_path.write_text(json.dumps(imports, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    support = Counter(row["task_id"] for row in assignments)
    audit = {
        "method_contract": risk["method_contract"], "git_commit_sha": risk["git_commit_sha"],
        "assignment_sha256": sha256_file(assignment_path), "import_sha256": sha256_file(import_path),
        "n_assignments": len(assignments), "n_workers": len({row["worker_id"] for row in assignments}),
        "n_tasks": len(support), "min_task_support": min(support.values(), default=0),
        "duplicate_worker_task_count": len(assignments) - len({(row["worker_id"], row["task_id"]) for row in assignments}),
        "import_smoke_passed": bool(imports) and all(item.get("data", {}).get("image") for item in json.loads(import_path.read_text(encoding="utf-8"))),
        "capacity_manifest_sha256": sha256_file(args.capacity_manifest),
    }
    audit["launch_ready"] = bool(design.get("launch_ready")) and audit["duplicate_worker_task_count"] == 0 and audit["import_smoke_passed"]
    (args.output_dir / "c2b_launch_ready_report.json").write_text(json.dumps(audit, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return {"day": 2, "phase": "build", "state_machine": design.get("state_machine", {}), **audit}


def _namespace_from_run_config(section: dict[str, Any]) -> argparse.Namespace:
    values: dict[str, Any] = {}
    for key, value in section.items():
        if key == "device" or value is None:
            values[key] = value
        elif isinstance(value, list):
            values[key] = [Path(item) for item in value]
        else:
            values[key] = Path(value)
    return argparse.Namespace(**values)


def close_c1_and_plan_c2b(args: argparse.Namespace) -> dict[str, Any]:
    """Resume-safe thin entry; stop at manual approvals and print one rerun command."""
    config = json.loads(args.run_config.read_text(encoding="utf-8"))
    if config.get("schema_version") != "paper_a_close_c1_plan_c2b_run_config_v1":
        raise ValueError("unsupported close-c1-and-plan-c2b run config")
    for section in ("audit_c1", "finalize_c1", "design_c2b", "build_c2b"):
        if not isinstance(config.get(section), dict):
            raise ValueError(f"close-c1-and-plan-c2b run config missing object section: {section}")
    runbook = Path(config.get("runbook") or (_PROJECT_ROOT / "docs/thesis_main/PAPER_A_C1_C2B_FORMAL_RUNBOOK.md"))
    contract = validate_runbook_command_contract(runbook)
    if not contract["valid"]:
        raise ValueError("runbook command contract invalid:" + ";".join(contract["violations"]))
    state = json.loads(args.state_output.read_text(encoding="utf-8")) if args.state_output.exists() else {
        "schema_version": "paper_a_close_c1_plan_c2b_state_v1", "phase": "not_started",
    }
    if state.get("schema_version") != "paper_a_close_c1_plan_c2b_state_v1":
        raise ValueError("unsupported close-c1-and-plan-c2b state")
    run_config_sha = sha256_file(args.run_config)
    if state.get("run_config_sha256") and state.get("run_config_sha256") != run_config_sha:
        raise ValueError("resume state is bound to a different run config SHA")
    python_executable = Path(sys.executable).resolve()
    rerun = (
        f'"{python_executable}" tools/thesis_main/analysis/run_c1_closeout_launch.py close-c1-and-plan-c2b '
        f'--run-config "{args.run_config}" --state-output "{args.state_output}"'
    )

    def build_preview() -> str:
        build_config = config.get("build_c2b", {})
        design_config = config.get("design_c2b", {})
        design_root = Path(design_config["output_dir"])
        values = {
            "c1-closeout-summary": state.get("c1_evidence_freeze_manifest", "<c1-evidence-freeze>"),
            "risk-summary": design_root / "c2_task_risk.summary.json",
            "task-pool": design_root / "c2_task_risk_inventory.csv",
            "task-eligibility-evidence": design_root / "c2b_task_eligibility_evidence.csv",
            "candidate-dir": design_root / "c2_candidates",
            "design-manifest": design_root / "c2b_candidate_design_manifest.json",
            "threshold-manifest": design_config["threshold_manifest"],
            "source-split-evidence": design_config["source_split_evidence"],
            "source-split-approval": design_config["source_split_approval"],
            "future-holdout-evidence": design_config["future_holdout_evidence"],
            "future-holdout-approval": design_config["future_holdout_approval"],
            "reference-registry": design_config["reference_registry"],
            "selected-task-reference-manifest": build_config["selected_task_reference_manifest"],
            "selected-design-approval": build_config["selected_design_approval"],
            "capacity-manifest": build_config["capacity_manifest"],
            "output-dir": build_config["output_dir"],
        }
        flags = " ".join(f'--{name} "{value}"' for name, value in values.items())
        return f'"{python_executable}" tools/thesis_main/analysis/run_c1_closeout_launch.py build-c2b {flags}'

    def persist(**updates: Any) -> dict[str, Any]:
        state.update(updates)
        state["run_config_sha256"] = run_config_sha
        state["runbook_contract"] = contract
        args.state_output.parent.mkdir(parents=True, exist_ok=True)
        args.state_output.write_text(json.dumps(state, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        return state

    if state.get("phase") == "formal_audit_blocked":
        state["phase"] = "not_started"
    if state.get("phase") == "not_started":
        audit_args = _namespace_from_run_config(config.get("audit_c1", {}))
        audit_result = audit_c1(audit_args)
        formal_output = Path(audit_result["output_dir"])
        if not audit_result["formal_closeout_ready"]:
            return persist(
                phase="formal_audit_blocked", formal_output_dir=formal_output.resolve().as_posix(),
                blockers=audit_result["blockers"], next_command=rerun,
            )
        persist(phase="awaiting_c1_closeout_adjudication", formal_output_dir=formal_output.resolve().as_posix(), blockers=[])

    if state.get("phase") in {"awaiting_c1_closeout_adjudication", "c1_evidence_freeze_blocked"}:
        adjudication_raw = config.get("finalize_c1", {}).get("adjudication_manifest")
        if not adjudication_raw or not Path(adjudication_raw).exists():
            return persist(phase="awaiting_c1_closeout_adjudication", next_command=rerun)
        finalize_args = _namespace_from_run_config({
            **config.get("finalize_c1", {}), "output_dir": state["formal_output_dir"],
        })
        finalized = finalize_c1(finalize_args)
        if not finalized["formal_closeout_ready"]:
            return persist(phase="c1_evidence_freeze_blocked", blockers=finalized["blockers"], next_command=rerun)
        persist(
            phase="c1_evidence_frozen", blockers=[], next_command=rerun,
            c1_evidence_freeze_manifest=(Path(state["formal_output_dir"]) / "c1_evidence_freeze_manifest.json").resolve().as_posix(),
        )

    if state.get("phase") in {"c1_evidence_frozen", "awaiting_split_approvals", "c2b_design_blocked"}:
        design_config = config.get("design_c2b", {})
        approvals = [design_config.get("source_split_approval"), design_config.get("future_holdout_approval")]
        if not all(value and Path(value).exists() for value in approvals):
            return persist(phase="awaiting_split_approvals", next_command=rerun)
        design_args = _namespace_from_run_config({
            **design_config, "c1_closeout_summary": state["c1_evidence_freeze_manifest"],
        })
        design = design_c2b(design_args)
        candidates_ready = bool(design.get("risk_pool_formal_ready")) and int(design.get("design", {}).get("n_feasible_candidate_designs") or 0) > 0
        return persist(
            phase="c2b_candidates_materialized" if candidates_ready else "c2b_design_blocked",
            design_result=design, next_command=build_preview() if candidates_ready else rerun,
        )
    return persist(next_command=state.get("next_command", ""))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Paper A C1 closeout and C2-B launch")
    sub = parser.add_subparsers(dest="command", required=True)

    def add_c1_inputs(command: argparse.ArgumentParser, *, active_name: str) -> None:
        command.add_argument("--export-dir", action="append", type=Path, required=True)
        command.add_argument(active_name, type=Path, required=True)
        for name in ("manual-assignment", "semi-assignment", "worker-distribution", "gt-export"):
            command.add_argument(f"--{name}", type=Path, required=True)
        command.add_argument("--p1-closeout-dir", type=Path, required=True)
        command.add_argument("--p1-integrity-dir", type=Path)
        command.add_argument("--output-root", type=Path, required=True)
        command.add_argument("--c1-preannotation-feature-csv", type=Path)

    rehearsal = sub.add_parser("rehearse-c1")
    add_c1_inputs(rehearsal, active_name="--active-log")

    static = sub.add_parser("prepare-c2b-static")
    for name in ("p1-closeout-dir", "inventory-csv", "legacy-manifest", "reference-dir", "layout-dir", "checkpoint", "config", "feature-audit-threshold-manifest", "output-dir"):
        static.add_argument(f"--{name}", type=Path, required=True)
    static.add_argument("--c1-assignment", action="append", type=Path, required=True)
    static.add_argument("--p1-initialization-import", action="append", type=Path, required=True)
    static.add_argument("--building-registry", type=Path)
    static.add_argument("--device", default="cuda:0")

    expand = sub.add_parser("expand-building-registry")
    expand.add_argument("--inventory-csv", type=Path, required=True)
    expand.add_argument("--approved-scene-mapping", type=Path, required=True)
    expand.add_argument("--output-csv", type=Path, required=True)

    contract_check = sub.add_parser("check-command-contract")
    contract_check.add_argument("--runbook", type=Path, required=True)

    preflight = sub.add_parser("preflight-calibration")
    for name in ("static-dir", "threshold-manifest", "feature-audit-threshold-manifest", "output"):
        preflight.add_argument(f"--{name}", type=Path, required=True)

    freeze = sub.add_parser("freeze-c1")
    freeze.add_argument("--source-live-root", type=Path, required=True)
    freeze.add_argument("--frozen-root", type=Path, required=True)
    freeze.add_argument("--collection-cutoff-server-time", required=True)
    freeze.add_argument("--operator", required=True)
    freeze.add_argument("--late-submission-policy", required=True)
    freeze.add_argument("--active-log-freeze-manifest", type=Path, required=True)
    freeze.add_argument("--collection-closure-manifest", type=Path, required=True)
    freeze.add_argument("--export-dir", action="append", type=Path, required=True)
    freeze.add_argument("--manual-assignment", type=Path, required=True)
    freeze.add_argument("--semi-assignment", type=Path, required=True)

    audit = sub.add_parser("audit-c1")
    add_c1_inputs(audit, active_name="--active-log")
    audit.add_argument("--c1-active-log-freeze-manifest", type=Path, required=True)
    audit.add_argument("--collection-closure-manifest", type=Path, required=True)
    audit.add_argument("--annotation-independence-disposition", dest="independence_disposition", type=Path)
    for name in ("duplicate-adjudication", "structural-disposition", "project-independence-disposition", "scope-adjudication", "reference-amendment", "outside-assignment-disposition", "completion-disposition"):
        audit.add_argument(f"--{name}", type=Path, required=True)

    finalize = sub.add_parser("finalize-c1")
    finalize.add_argument("--output-dir", type=Path, required=True)
    finalize.add_argument("--adjudication-manifest", type=Path, required=True)

    plan = sub.add_parser("design-c2b")
    for name in ("c1-closeout-summary", "inventory-csv", "layout-dir", "c1-task-feature-csv", "checkpoint", "building-registry", "source-split-evidence", "source-split-approval", "future-holdout-evidence", "future-holdout-approval", "history-overlap-audit", "scope-registry", "reference-registry", "feature-freeze-manifest", "static-freeze-manifest", "threshold-formula-contract", "threshold-input-approval", "threshold-manifest", "capacity-manifest", "output-dir"):
        plan.add_argument(f"--{name}", type=Path, required=True)
    plan.add_argument("--device", default="auto")

    build = sub.add_parser("build-c2b")
    for name in ("c1-closeout-summary", "risk-summary", "task-pool", "task-eligibility-evidence", "candidate-dir", "design-manifest", "threshold-manifest", "source-split-evidence", "source-split-approval", "future-holdout-evidence", "future-holdout-approval", "reference-registry", "selected-task-reference-manifest", "selected-design-approval", "capacity-manifest", "output-dir"):
        build.add_argument(f"--{name}", type=Path, required=True)
    close = sub.add_parser("close-c1-and-plan-c2b")
    close.add_argument("--run-config", type=Path, required=True)
    close.add_argument("--state-output", type=Path, required=True)
    args = parser.parse_args(argv)
    command = {
        "prepare-c2b-static": prepare_c2b_static,
        "expand-building-registry": expand_building_registry,
        "check-command-contract": check_command_contract,
        "preflight-calibration": preflight_calibration,
        "rehearse-c1": rehearse_c1,
        "freeze-c1": freeze_c1,
        "audit-c1": audit_c1,
        "finalize-c1": finalize_c1,
        "design-c2b": design_c2b,
        "build-c2b": build_c2b,
        "close-c1-and-plan-c2b": close_c1_and_plan_c2b,
    }[args.command]
    print(json.dumps(command(args), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
