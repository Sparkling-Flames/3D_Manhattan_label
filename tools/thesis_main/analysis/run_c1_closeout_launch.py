"""Two-day fail-closed C1 closeout and C2-B launch orchestration."""

from __future__ import annotations

import argparse
import csv
import hashlib
import importlib.metadata
import json
import math
import platform
import shutil
import subprocess
import sys
import tempfile
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable
from urllib.parse import quote

import numpy as np

_PROJECT_ROOT = Path(__file__).resolve().parents[3]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from tools.thesis_main.analysis import build_c2_assignment_manifest_from_c1_gaps as c2b
from tools.thesis_main.analysis.active_log_utils import freeze_active_log_snapshot, validate_active_log_freeze_manifest
from tools.thesis_main.analysis.materialize_c2b_task_eligibility import materialize as materialize_c2b_task_eligibility
from tools.thesis_main.analysis.materialize_c2_task_risk import materialize_formal as materialize_task_risk
from tools.thesis_main.analysis.c1_c2_mainline import formal_git_state
from tools.thesis_main.analysis.c1_c2_mainline import materialize_c2b_design_worker_profile
from tools.thesis_main.analysis.materialize_c1_c2_design_parameters import materialize as materialize_design_parameters
from tools.thesis_main.analysis.paper_a_contracts import METHOD_CONTRACT, load_method_contract, validate_generated_subordinate
from tools.thesis_main.analysis.derive_c2b_design_thresholds import derive_threshold_manifest, validate_formula_contract
from tools.thesis_main.analysis.materialize_c2_task_risk import (
    _feature_audit_passes,
    _knn,
    _layout_features,
    freeze_feature_reference,
    load_frozen_c1_risk_reference,
    refresh_feature_freeze_approval,
    score_frozen_c1_risk_candidate,
)
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
from tools.thesis_main.analysis.worker_identity import normalize_worker_id


def _manifest_rows(paths: Iterable[Path]) -> list[dict[str, Any]]:
    return [
        {"path": path.as_posix(), "size": path.stat().st_size, "sha256": sha256_file(path)}
        for path in sorted({item.resolve() for item in paths}, key=lambda item: item.as_posix().lower())
    ]


def _aggregate_sha(rows: list[dict[str, Any]]) -> str:
    payload = json.dumps(rows, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def materialize_c1(*args: Any, **kwargs: Any) -> Any:
    """Load the full C1 pipeline only for commands that actually execute it."""
    from tools.thesis_main.analysis.run_c1_precloseout_rehearsal import materialize

    return materialize(*args, **kwargs)


COMMAND_ARTIFACT_CONTRACT = {
    "rehearse-c1": {"outputs": ("analysis_dependency_manifest.json",)},
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
    "freeze-c1-batch": {"outputs": ("c1_a_analysis_snapshot.json",)},
    "design-c2b": {
        "requires": (("prepare-c2b-static", "c2b_static_freeze_manifest.json"), ("freeze-c1-batch", "c1_a_analysis_snapshot.json")),
        "outputs": ("c2_task_risk.summary.json", "c2b_evidence_freeze_envelope.json", "c2b_design.summary.json"),
    },
    "build-c2b": {
        "requires": (("design-c2b", "c2_task_risk.summary.json"), ("design-c2b", "c2b_design.summary.json")),
        "outputs": ("assignment_manifest_C2B.csv", "c2b_launch_ready_report.json"),
    },
    "repackage-c2b-v17-to-v18": {
        "outputs": (
            "c2b_selected_design_manifest_D8_v18.json",
            "c2b_worker_language_registry_v1.json",
            "c2b_worker_deployment_manifest_v1.json",
            "c2b_v17_to_v18_assignment_mapping.csv",
            "c2b_v17_to_v18_repackage_envelope_v1.json",
            "c2b_launch_ready_report.json",
        ),
    },
    "bind-c2b-runtime-mapping": {"outputs": ("c2b_runtime_task_mapping.csv", "c2b_worker_task_binding_audit.json", "c2b_private_assignment_list_audit.json")},
    "prepare-stage3-test-candidate": {
        "outputs": (
            "stage3_test_inventory_candidate.csv",
            "stage3_test_overlap_audit.csv",
            "test_task_risk_candidate.csv",
            "test_task_risk_candidate.summary.json",
        ),
    },
    "check-command-contract": {"outputs": ()},
}

FORMAL_BATCH_COMMANDS = ("rehearse-c1", "freeze-c1-batch", "design-c2b", "build-c2b", "bind-c2b-runtime-mapping")
MIGRATION_COMMANDS = ("repackage-c2b-v17-to-v18",)

C2B_V17_METHOD_VERSION = "paper_a_method_20260802_v17"
C2B_V17_METHOD_SHA256 = "5068e08ade8d1f2013b5ed66af04761c210acf74ef522229ffd39ad8f6b17b4c"
C2B_V17_D8_LAUNCH_SHA256 = "3429e45061b2dba8af314495b6286c2ea38db6e9574aefd77253d8ae4334ec88"
C2B_V17_D8_ASSIGNMENT_SHA256 = "5e43e682a46211fb35ed5588b0f22b2853997236bff814f14f1306246907a07c"
C2B_V17_D8_SELECTED_MANIFEST_SHA256 = "1dea583ae7131170611ea22ceb1a7f8887ea9e4754dd89297a7fa2235631615f"
C2B_D8_DESIGN_SHA256 = "f2b7cde8aadf29fb35a965ec49b434587feaa1c09863f74cf0e95e02e3462822"
C2B_D8_DESIGN_MANIFEST_SHA256 = "92eb0b6a501a4af02b3379d10c01a6efa9e44153e9f44a748358dca50531d5ba"
C2B_D8_TASK_POOL_SHA256 = "211ea4260415918104685440b07ce72fc17113b1764913c9215c554df901c067"
C2B_V17_D8_IMPORT_ZH_SHA256 = "3a30a85eb541edc6f2ab12d3999b95b989e717a4bca5870a0de08b51b67069c1"
C2B_V17_D8_IMPORT_FOREIGN_SHA256 = "037c1ed748c359c6a4a54deef377b7432f4c53f957c55a934c670ceb36678c53"


def validate_runbook_command_contract(runbook: Path) -> dict[str, Any]:
    text = runbook.read_text(encoding="utf-8")
    missing = []
    for command in (*FORMAL_BATCH_COMMANDS, *MIGRATION_COMMANDS):
        contract = COMMAND_ARTIFACT_CONTRACT[command]
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


DEFAULT_C2B_DEPLOYMENTS = (
    {
        "deployment_id": "c2b_zh",
        "language_group": "Chinese",
        "server_instance_id": "labelstudio_http_175_178_71_217",
        "server_url": "http://175.178.71.217:8000",
        "project_id": "",
    },
    {
        "deployment_id": "c2b_en",
        "language_group": "English",
        "server_instance_id": "labelstudio_https_sparkle0825",
        "server_url": "https://label.sparkle0825.top",
        "project_id": "",
    },
)


def _deployment_specs(path: Path | None, workers: set[str]) -> tuple[list[dict[str, Any]], str]:
    """Load the external deployment truth; never infer project identity from a display index."""
    if path is None:
        return [dict(item, worker_ids=sorted(workers), worker_registry_sha256="") for item in DEFAULT_C2B_DEPLOYMENTS], ""
    payload = json.loads(path.read_text(encoding="utf-8"))
    if payload.get("schema_version") not in {"c2b_worker_deployment_manifest_v1", "c2b_runtime_project_manifest_v1"}:
        raise ValueError("C2-B deployment manifest schema is invalid")
    deployments = payload.get("deployments")
    if not isinstance(deployments, list) or not deployments:
        raise ValueError("C2-B deployment manifest requires a non-empty deployments list")
    seen_ids: set[str] = set()
    mapped: dict[str, str] = {}
    normalized: list[dict[str, Any]] = []
    for raw in deployments:
        if not isinstance(raw, dict):
            raise ValueError("C2-B deployment manifest contains a non-object deployment")
        deployment_id = str(raw.get("deployment_id", "")).strip()
        language = str(raw.get("language_group", "")).strip()
        server = str(raw.get("server_instance_id", "")).strip()
        url = str(raw.get("server_url", "")).strip()
        project_id = str(raw.get("project_id", "")).strip()
        worker_ids = [normalize_worker_id(value) for value in raw.get("worker_ids", raw.get("workers", []))]
        if not deployment_id or not language or not server or not url or not project_id or not worker_ids:
            raise ValueError("C2-B deployment manifest has incomplete deployment identity")
        if deployment_id in seen_ids:
            raise ValueError("C2-B deployment manifest has duplicate deployment_id")
        seen_ids.add(deployment_id)
        for worker in worker_ids:
            if not worker or worker in mapped:
                raise ValueError("C2-B worker maps to zero or multiple deployments")
            mapped[worker] = deployment_id
        normalized.append({
            "deployment_id": deployment_id, "language_group": language,
            "server_instance_id": server, "server_url": url, "project_id": project_id,
            "worker_ids": sorted(set(worker_ids)),
            "worker_registry_sha256": str(raw.get("worker_registry_sha256", payload.get("worker_registry_sha256", ""))).strip(),
        })
    if set(mapped) != workers:
        raise ValueError("C2-B deployment manifest does not cover exactly the assigned workers")
    if any(not item["worker_registry_sha256"] for item in normalized):
        raise ValueError("C2-B deployment manifest lacks worker registry SHA")
    return normalized, sha256_file(path)


def _write_worker_deployment_manifest(
    output_dir: Path,
    source_path: Path,
    source_sha: str,
    deployments: list[dict[str, Any]],
    *,
    assignment_path: Path,
    selected_design_sha: str,
    batch_id: str,
) -> Path:
    method_identity = _method_identity()
    for deployment in deployments:
        deployment.update({
            "method_contract_version": method_identity["method_contract_version"],
            "method_contract_sha256": method_identity["method_contract_sha256"],
            "assignment_sha256": sha256_file(assignment_path),
            "selected_design_sha": selected_design_sha,
        })
    payload = {
        "schema_version": "c2b_worker_deployment_manifest_v1",
        "artifact_role": "C2B_WORKER_DEPLOYMENT_MANIFEST_FROZEN",
        "contract_role": "generated_subordinate",
        **_method_identity(),
        "assignment_batch_id": batch_id,
        "assignment_sha256": sha256_file(assignment_path),
        "selected_design_sha": selected_design_sha,
        "source_manifest_path": str(source_path.resolve()),
        "source_manifest_sha256": source_sha,
        "deployments": deployments,
        "frozen": True,
    }
    path = output_dir / "c2b_worker_deployment_manifest_v1.json"
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def _source_identity_aggregate(rows: list[dict[str, Any]]) -> str:
    """Hash source identity only; raw-snapshot bookkeeping must not change it."""
    return _aggregate_sha([{name: row[name] for name in ("path", "size", "sha256")} for row in rows])


_TERMINAL_CALIBRATION_STATUSES = {"completed", "closed_partial_usable", "closed_partial_insufficient", "nonstarter", "administrative_exclusion"}


def _materialize_c1_child_freeze(
    output_dir: Path,
    role: str,
    source_role: str,
    source: Path,
    *,
    formal_ready: bool,
    profile_version: str,
    cohort_id: str,
    method_version: str,
    method_sha: str,
) -> dict[str, Any]:
    source_sha = sha256_file(source) if source.is_file() else ""
    child_ready = bool(formal_ready and source_sha)
    payload = {
        "schema_version": "paper_a_c1_child_evidence_freeze_v1",
        "artifact_role": role,
        "contract_role": "generated_subordinate",
        "formal_ready": child_ready,
        "profile_version": profile_version,
        "cohort_id": cohort_id,
        "method_contract_version": method_version,
        "method_contract_sha256": method_sha,
        "source_role": source_role,
        "source_path": str(source.resolve()),
        "source_sha256": source_sha,
        "blockers": [] if child_ready else [f"missing_or_unfrozen:{source_role}"],
        "dependencies": [],
    }
    path = output_dir / f"{role.lower()}.json"
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return {
        "role": role,
        "path": str(path.resolve()),
        "sha256": sha256_file(path),
        "expected_schema": payload["schema_version"],
        "required_status_field": "formal_ready",
        "required_status_value": True,
        "profile_version": profile_version,
        "cohort_id": cohort_id,
        "frozen": child_ready,
    }


def _method_identity() -> dict[str, str]:
    method = load_method_contract()
    return {"method_contract_version": method["contract_version"], "method_contract_sha256": sha256_file(METHOD_CONTRACT)}


def _canonical_payload_sha(payload: Any) -> str:
    return hashlib.sha256(
        json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


def _read_json_object(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise FileNotFoundError(path)
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"expected JSON object:{path}")
    return payload


def _write_json_new(path: Path, payload: dict[str, Any]) -> Path:
    if path.exists():
        raise ValueError(f"target artifact already exists:{path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8", newline="\n") as stream:
        stream.write(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n")
    return path


def _write_text_new(path: Path, text: str) -> Path:
    if path.exists():
        raise ValueError(f"target artifact already exists:{path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8", newline="\n") as stream:
        stream.write(text)
    return path


def _guard_repackage_targets(output_dir: Path, target_paths: list[Path]) -> None:
    if output_dir.exists() and any(output_dir.iterdir()):
        raise ValueError(f"target artifact already exists:{output_dir}")
    existing = [str(path) for path in target_paths if path.exists()]
    if existing:
        raise ValueError("target artifact already exists:" + ",".join(existing))


def _migration_language_group(value: Any) -> str:
    token = str(value or "").strip().lower().replace("_", "-")
    if token in {"chinese", "zh", "cn", "中文"}:
        return "Chinese"
    if token in {"english", "en", "foreign", "foreign-https", "海外", "英文"}:
        return "English"
    raise ValueError(f"unsupported C2-B language group:{value}")


def _migration_source_rows(path: Path) -> list[dict[str, Any]]:
    if path.suffix.lower() == ".json":
        payload = json.loads(path.read_text(encoding="utf-8"))
        rows = payload.get("workers", payload.get("rows", payload)) if isinstance(payload, dict) else payload
        if not isinstance(rows, list):
            raise ValueError("C2-B worker language source JSON must contain workers")
        return [row for row in rows if isinstance(row, dict)]
    return [dict(row) for row in _read(path)]


def _materialize_c2b_worker_language_registry(
    assignment_rows: list[dict[str, str]],
    source_path: Path,
    *,
    method_contract_version: str,
    method_contract_sha256: str,
) -> tuple[dict[str, Any], dict[str, str]]:
    assigned_workers = {
        normalize_worker_id(row.get("worker_id", ""))
        for row in assignment_rows
        if normalize_worker_id(row.get("worker_id", ""))
    }
    if not assigned_workers:
        raise ValueError("C2-B assignment has no workers")
    declared: dict[str, str] = {}
    for row in _migration_source_rows(source_path):
        worker = normalize_worker_id(row.get("worker_id") or row.get("public_worker_code") or row.get("worker"))
        if not worker:
            raise ValueError("C2-B language source contains an empty worker identity")
        if worker in declared:
            raise ValueError(f"C2-B language source contains duplicate worker:{worker}")
        declared[worker] = _migration_language_group(row.get("language_group") or row.get("language"))
    if not declared:
        raise ValueError("C2-B language source is empty")
    if not set(declared) <= assigned_workers:
        raise ValueError("C2-B language source contains an unassigned worker")
    chinese = {worker for worker, group in declared.items() if group == "Chinese"}
    foreign_declared = {worker for worker, group in declared.items() if group == "English"}
    foreign = assigned_workers - chinese
    if foreign_declared and foreign_declared != foreign:
        raise ValueError("C2-B language source disagrees with the assigned-worker complement")
    if not chinese or not foreign:
        raise ValueError("C2-B migration requires both Chinese and English assigned workers")
    worker_groups = {
        worker: ("Chinese" if worker in chinese else "English")
        for worker in sorted(assigned_workers)
    }
    registry = {
        "schema_version": "c2b_worker_language_registry_v1",
        "artifact_role": "C2B_WORKER_LANGUAGE_REGISTRY_FROZEN",
        "contract_role": "generated_subordinate",
        "formal_ready": True,
        "method_contract_version": method_contract_version,
        "method_contract_sha256": method_contract_sha256,
        "assignment_sha256": "",
        "source_path": str(source_path.resolve()),
        "source_sha256": sha256_file(source_path),
        "language_assignment_rule": "Chinese source roster; assigned-worker complement is English",
        "workers": [
            {"worker_id": worker, "language_group": group}
            for worker, group in worker_groups.items()
        ],
        "language_groups": sorted(set(worker_groups.values())),
        "dependencies": [],
    }
    return registry, worker_groups


def _load_migration_deployment_config(
    path: Path,
    worker_groups: dict[str, str],
    source_imports: dict[str, Path],
) -> list[dict[str, Any]]:
    payload = _read_json_object(path)
    if payload.get("schema_version") != "c2b_migration_deployment_config_v1":
        raise ValueError("C2-B migration deployment config schema is invalid")
    raw_deployments = payload.get("deployments")
    if not isinstance(raw_deployments, list) or not raw_deployments:
        raise ValueError("C2-B migration deployment config requires deployments")
    normalized: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    seen_groups: set[str] = set()
    seen_import_filenames: set[str] = set()
    for raw in raw_deployments:
        if not isinstance(raw, dict):
            raise ValueError("C2-B migration deployment config contains a non-object")
        deployment_id = str(raw.get("deployment_id", "")).strip()
        language_group = _migration_language_group(raw.get("language_group"))
        server_instance_id = str(raw.get("server_instance_id", "")).strip()
        server_url = str(raw.get("server_url", "")).strip().rstrip("/")
        project_id = str(raw.get("project_id", "")).strip()
        if not deployment_id or not server_instance_id or not server_url or not project_id:
            raise ValueError("C2-B migration deployment identity is incomplete")
        if deployment_id in seen_ids or language_group in seen_groups:
            raise ValueError("C2-B migration deployment IDs or language groups are duplicated")
        seen_ids.add(deployment_id)
        seen_groups.add(language_group)
        source_path_value = raw.get("source_import_path")
        source_path = source_imports[language_group]
        if source_path_value:
            candidate = Path(str(source_path_value))
            if not candidate.is_absolute():
                candidate = (_PROJECT_ROOT / candidate).resolve()
            if candidate.resolve() != source_path.resolve():
                raise ValueError(f"C2-B deployment source import disagrees with explicit source:{deployment_id}")
        filename = str(raw.get("planned_import_filename", "")).strip()
        if not filename:
            suffix = "zh" if language_group == "Chinese" else "foreign_https"
            filename = f"c2b_D8_batch_a_import_{suffix}_v18.json"
        if Path(filename).name != filename or not filename.endswith(".json"):
            raise ValueError(f"C2-B target import filename is unsafe:{filename}")
        if filename in seen_import_filenames:
            raise ValueError("C2-B migration target import filenames are duplicated")
        seen_import_filenames.add(filename)
        normalized.append({
            "deployment_id": deployment_id,
            "language_group": language_group,
            "server_instance_id": server_instance_id,
            "server_url": server_url,
            "project_id": project_id,
            "source_import_path": str(source_path.resolve()),
            "planned_import_filename": filename,
            "worker_ids": sorted(worker for worker, group in worker_groups.items() if group == language_group),
        })
    if seen_groups != set(worker_groups.values()) or seen_groups != {"Chinese", "English"}:
        raise ValueError("C2-B migration deployment set does not cover the frozen language registry")
    return normalized


def _validate_v17_d8_sources(
    launch_report_path: Path,
    assignment_path: Path,
    selected_manifest_path: Path,
    import_paths: dict[str, Path],
) -> tuple[dict[str, Any], list[dict[str, str]], dict[str, Any], dict[str, dict[str, Any]]]:
    source_hashes = {
        "launch_report": sha256_file(launch_report_path),
        "assignment": sha256_file(assignment_path),
        "selected_design_manifest": sha256_file(selected_manifest_path),
        "import_zh": sha256_file(import_paths["Chinese"]),
        "import_foreign": sha256_file(import_paths["English"]),
    }
    expected_hashes = {
        "launch_report": C2B_V17_D8_LAUNCH_SHA256,
        "assignment": C2B_V17_D8_ASSIGNMENT_SHA256,
        "selected_design_manifest": C2B_V17_D8_SELECTED_MANIFEST_SHA256,
        "import_zh": C2B_V17_D8_IMPORT_ZH_SHA256,
        "import_foreign": C2B_V17_D8_IMPORT_FOREIGN_SHA256,
    }
    if source_hashes != expected_hashes:
        raise ValueError(f"C2-B v17 D8 source SHA mismatch:{source_hashes}")
    launch = _read_json_object(launch_report_path)
    if any((launch.get(field) != value) for field, value in {
        "schema_version": "paper_a_c2b_launch_ready_report_v3",
        "method_contract_version": C2B_V17_METHOD_VERSION,
        "method_contract_sha256": C2B_V17_METHOD_SHA256,
        "assignment_batch_id": "C2B_BATCH_A",
        "selected_design_id": "D8",
        "selected_design_sha": C2B_D8_DESIGN_SHA256,
        "selected_design_manifest_sha256": C2B_V17_D8_SELECTED_MANIFEST_SHA256,
        "task_pool_sha256": C2B_D8_TASK_POOL_SHA256,
        "assignment_sha256": C2B_V17_D8_ASSIGNMENT_SHA256,
        "n_assignments": 176,
        "n_workers": 22,
        "n_tasks": 46,
    }.items()):
        raise ValueError("C2-B v17 launch report is not the frozen D8 source")
    assignments = _read(assignment_path)
    if any(not normalize_worker_id(row.get("worker_id", "")) or not str(row.get("task_id", "")).strip() for row in assignments):
        raise ValueError("C2-B v17 D8 assignment contains an empty worker/task identity")
    pairs = {(normalize_worker_id(row.get("worker_id", "")), str(row.get("task_id", "")).strip()) for row in assignments}
    task_ids = {task for _worker, task in pairs if task}
    workers = {worker for worker, _task in pairs if worker}
    if len(assignments) != 176 or len(pairs) != 176 or len(workers) != 22 or len(task_ids) != 46:
        raise ValueError("C2-B v17 D8 assignment cardinality changed")
    if any(str(row.get("assignment_batch_id", "")).strip() != "C2B_BATCH_A" for row in assignments):
        raise ValueError("C2-B v17 D8 assignment batch identity changed")
    selected_manifest = _read_json_object(selected_manifest_path)
    if any((selected_manifest.get(field) != value) for field, value in {
        "schema_version": "paper_a_selected_c2b_design_manifest_v1",
        "method_contract_version": C2B_V17_METHOD_VERSION,
        "method_contract_sha256": C2B_V17_METHOD_SHA256,
        "selected_design_id": "D8",
        "selected_design_sha": C2B_D8_DESIGN_SHA256,
        "design_manifest_sha256": C2B_D8_DESIGN_MANIFEST_SHA256,
        "task_pool_sha256": C2B_D8_TASK_POOL_SHA256,
        "common_anchor_count": 4,
        "bridge_per_worker": 4,
    }.items()):
        raise ValueError("C2-B v17 D8 selected design identity changed")
    imports: dict[str, dict[str, Any]] = {}
    for group, path in import_paths.items():
        payload = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(payload, list) or len(payload) != 46:
            raise ValueError(f"C2-B v17 import does not contain the frozen 46-task collection:{group}")
        task_map: dict[str, Any] = {}
        for item in payload:
            if not isinstance(item, dict) or not isinstance(item.get("data"), dict):
                raise ValueError(f"C2-B v17 import contains an invalid task:{group}")
            data = item["data"]
            planned = str(data.get("planned_task_id") or data.get("task_id") or "").strip()
            if not planned or planned in task_map:
                raise ValueError(f"C2-B v17 import contains duplicate planned task:{group}")
            if any(data.get(field) != value for field, value in {
                "calibration_version": "C2-B_v17",
                "selected_design_sha": C2B_D8_DESIGN_SHA256,
                "c2b_batch_id": "C2B_BATCH_A",
            }.items()):
                raise ValueError(f"C2-B v17 import has stale D8 identity:{group}")
            if str(data.get("dataset_group", "")).upper() == "GT" or str(data.get("task_role", "")).upper() == "GT":
                raise ValueError("C2-B v17 import contains GT task")
            task_map[planned] = item
        if set(task_map) != task_ids:
            raise ValueError(f"C2-B v17 import task collection differs from D8 assignment:{group}")
        imports[group] = {"path": path, "sha256": sha256_file(path), "tasks": task_map}
    if launch.get("import_sha256") != imports["Chinese"]["sha256"]:
        raise ValueError("C2-B v17 single import envelope does not identify the historical Chinese import")
    return launch, assignments, selected_manifest, imports


def _migration_import_text(payload: list[dict[str, Any]]) -> str:
    return json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def repackage_c2b_v17_to_v18(args: argparse.Namespace) -> dict[str, Any]:
    """Rebind the frozen D8 assignment from the historical v17 envelope to v18.

    This path deliberately does not call ``build_c2b``: the latter is allowed to
    materialize a new assignment, while this migration is only a byte-preserving
    repackage of an already frozen D8 batch.
    """
    legacy_root = Path(getattr(args, "legacy_root", "analysis_results/c2b_build_20260802_v17_d8"))
    launch_report_path = Path(getattr(args, "legacy_launch_report", None) or legacy_root / "c2b_launch_ready_report.json")
    assignment_path = Path(getattr(args, "legacy_assignment", None) or legacy_root / "assignment_manifest_C2B.csv")
    selected_manifest_path = Path(
        getattr(args, "legacy_selected_design_manifest", None)
        or legacy_root / "inputs/c2b_selected_design_manifest_D8.json"
    )
    import_paths = {
        "Chinese": Path(getattr(args, "legacy_import_zh", None) or _PROJECT_ROOT / "import_json/c2b/c2b_D8_batch_a_import_zh.json"),
        "English": Path(getattr(args, "legacy_import_foreign", None) or _PROJECT_ROOT / "import_json/c2b/c2b_D8_batch_a_import_foreign_https.json"),
    }
    language_source_value = getattr(args, "worker_language_source", None)
    if not language_source_value:
        raise ValueError("C2-B migration requires an explicit frozen worker language source")
    language_source = Path(language_source_value)
    deployment_config = Path(getattr(args, "deployment_config", ""))
    if not deployment_config.is_file():
        raise ValueError("C2-B v17 to v18 migration requires an explicit deployment config with project IDs")
    output_dir = Path(getattr(args, "output_dir", "analysis_results/c2b_migration_20260803_v17_to_v18_d8"))
    target_import_dir = Path(getattr(args, "target_import_dir", _PROJECT_ROOT / "import_json/c2b"))
    target_method_path = Path(getattr(args, "target_method_contract", None) or METHOD_CONTRACT)
    target_method = load_method_contract(target_method_path)
    target_method_sha = sha256_file(target_method_path)
    current_method = load_method_contract()
    current_method_sha = sha256_file(METHOD_CONTRACT)
    if target_method.get("contract_version") != current_method.get("contract_version") or target_method_sha != current_method_sha:
        raise ValueError("C2-B migration target method contract is not the current frozen v18 contract")
    _launch, assignments, selected_manifest, source_imports = _validate_v17_d8_sources(
        launch_report_path, assignment_path, selected_manifest_path, import_paths,
    )
    registry, worker_groups = _materialize_c2b_worker_language_registry(
        assignments, language_source,
        method_contract_version=target_method["contract_version"], method_contract_sha256=target_method_sha,
    )
    registry["assignment_sha256"] = sha256_file(assignment_path)
    registry["assignment_path"] = str(assignment_path.resolve())
    registry["dependencies"] = [{
        "role": "ASSIGNMENT_MANIFEST",
        "path": str(assignment_path.resolve()),
        "sha256": sha256_file(assignment_path),
    }]
    deployment_specs = _load_migration_deployment_config(deployment_config, worker_groups, import_paths)
    target_import_paths = {
        item["deployment_id"]: (target_import_dir / item["planned_import_filename"]).resolve()
        for item in deployment_specs
    }
    selected_rebind_path = output_dir / "c2b_selected_design_manifest_D8_v18.json"
    target_assignment_path = output_dir / "assignment_manifest_C2B.csv"
    target_distribution_path = output_dir / "worker_distribution_C2B.csv"
    mapping_path = output_dir / "c2b_v17_to_v18_assignment_mapping.csv"
    registry_path = output_dir / "c2b_worker_language_registry_v1.json"
    deployment_manifest_path = output_dir / "c2b_worker_deployment_manifest_v1.json"
    launch_path = output_dir / "c2b_launch_ready_report.json"
    envelope_path = output_dir / "c2b_v17_to_v18_repackage_envelope_v1.json"
    target_paths = [
        selected_rebind_path, target_assignment_path, target_distribution_path, mapping_path,
        registry_path, deployment_manifest_path, launch_path, envelope_path,
        *target_import_paths.values(),
    ]
    _guard_repackage_targets(output_dir, target_paths)
    deployment_by_group = {item["language_group"]: item for item in deployment_specs}
    worker_to_deployment: dict[str, str] = {}
    for item in deployment_specs:
        for worker in item["worker_ids"]:
            if worker in worker_to_deployment:
                raise ValueError("C2-B migration maps a worker to multiple deployments")
            worker_to_deployment[worker] = item["deployment_id"]
    if set(worker_to_deployment) != set(worker_groups):
        raise ValueError("C2-B migration deployment set does not cover the language registry")
    mapping_rows: list[dict[str, Any]] = []
    for row_number, row in enumerate(assignments, 1):
        worker = normalize_worker_id(row.get("worker_id", ""))
        task_id = str(row.get("task_id", "")).strip()
        planned_task_id = str(row.get("planned_task_id") or task_id).strip()
        deployment_id = worker_to_deployment.get(worker, "")
        if not deployment_id or not planned_task_id:
            raise ValueError("C2-B migration assignment row lacks a deployment or planned task identity")
        group = next(group for group, item in deployment_by_group.items() if item["deployment_id"] == deployment_id)
        source_task = source_imports[group]["tasks"].get(planned_task_id)
        if source_task is None:
            raise ValueError(f"C2-B migration assignment task is absent from its source import:{planned_task_id}")
        mapping_rows.append({
            "schema_version": "c2b_v17_to_v18_assignment_mapping_v1",
            "source_assignment_row_number": row_number,
            "worker_id": worker,
            "task_id": task_id,
            "planned_task_id": planned_task_id,
            "deployment_id": deployment_id,
            "source_assignment_sha256": sha256_file(assignment_path),
            "target_assignment_sha256": sha256_file(assignment_path),
            "source_import_path": str(source_imports[group]["path"].resolve()),
            "source_import_sha256": source_imports[group]["sha256"],
            "target_import_path": str(target_import_paths[deployment_id]),
            "source_task_payload_sha256": _canonical_payload_sha(source_task["data"]),
            "source_method_contract_version": C2B_V17_METHOD_VERSION,
            "source_method_contract_sha256": C2B_V17_METHOD_SHA256,
            "target_method_contract_version": target_method["contract_version"],
            "target_method_contract_sha256": target_method_sha,
            "source_selected_design_id": "D8",
            "target_selected_design_id": "D8",
            "source_selected_design_sha": C2B_D8_DESIGN_SHA256,
            "target_selected_design_sha": C2B_D8_DESIGN_SHA256,
            "source_design_manifest_sha256": C2B_D8_DESIGN_MANIFEST_SHA256,
            "target_design_manifest_sha256": C2B_D8_DESIGN_MANIFEST_SHA256,
            "source_task_pool_sha256": C2B_D8_TASK_POOL_SHA256,
            "target_task_pool_sha256": C2B_D8_TASK_POOL_SHA256,
            "source_assignment_batch_id": "C2B_BATCH_A",
            "target_assignment_batch_id": "C2B_BATCH_A",
            "selected_design_id": "D8",
            "selected_design_sha": C2B_D8_DESIGN_SHA256,
            "assignment_batch_id": "C2B_BATCH_A",
        })
    if len(mapping_rows) != 176 or len({(row["worker_id"], row["task_id"]) for row in mapping_rows}) != 176:
        raise ValueError("C2-B migration mapping does not cover the frozen 176 assignments")
    target_import_texts: dict[str, str] = {}
    for deployment in deployment_specs:
        group = deployment["language_group"]
        source_info = source_imports[group]
        transformed: list[dict[str, Any]] = []
        for source_item in source_info["tasks"].values():
            source_data = source_item["data"]
            target_data = dict(source_data)
            target_data.update({
                "calibration_version": "C2-B_v18",
                "deployment_id": deployment["deployment_id"],
                "language_group": deployment["language_group"],
                "server_instance_id": deployment["server_instance_id"],
                "project_id": deployment["project_id"],
                "method_contract_version": target_method["contract_version"],
                "method_contract_sha256": target_method_sha,
                "migration_source_method_contract_version": C2B_V17_METHOD_VERSION,
                "migration_source_method_contract_sha256": C2B_V17_METHOD_SHA256,
                "migration_source_import_sha256": source_info["sha256"],
            })
            if target_data.get("vis_3d") != source_data.get("vis_3d"):
                raise ValueError("C2-B migration changed vis_3d without an explicit rewrite map")
            transformed.append({**source_item, "data": target_data})
        target_import_texts[deployment["deployment_id"]] = _migration_import_text(transformed)
        target_sha = hashlib.sha256(target_import_texts[deployment["deployment_id"]].encode("utf-8")).hexdigest()
        for mapping in mapping_rows:
            if mapping["deployment_id"] == deployment["deployment_id"]:
                target_item = next(
                    item for item in transformed
                    if str(item["data"].get("planned_task_id") or item["data"].get("task_id")) == mapping["planned_task_id"]
                )
                mapping["target_import_sha256"] = target_sha
                mapping["target_task_payload_sha256"] = _canonical_payload_sha(target_item["data"])
        expected_tasks = {str(row.get("task_id", "")).strip() for row in assignments if str(row.get("task_id", "")).strip()}
        actual_tasks = {
            str(item["data"].get("planned_task_id") or item["data"].get("task_id"))
            for item in transformed
        }
        if actual_tasks != set(source_info["tasks"]) or expected_tasks != actual_tasks:
            raise ValueError(f"C2-B migration import task collection differs from deployment assignment:{deployment['deployment_id']}")
        source_url_prefix = deployment["server_url"] + "/tools/vis_3d.html?"
        if any(not str(item["data"].get("vis_3d", "")).startswith(source_url_prefix) for item in transformed):
            raise ValueError(f"C2-B migration vis_3d URL origin disagrees with deployment:{deployment['deployment_id']}")
        deployment["planned_import_path"] = str(target_import_paths[deployment["deployment_id"]])
        deployment["planned_import_sha256"] = target_sha
        deployment["source_import_sha256"] = source_info["sha256"]
        deployment["task_count"] = len(transformed)
    rebind = dict(selected_manifest)
    rebind.update({
        "contract_role": "generated_subordinate",
        "method_contract_version": target_method["contract_version"],
        "method_contract_sha256": target_method_sha,
        "source_method_contract_version": C2B_V17_METHOD_VERSION,
        "source_method_contract_sha256": C2B_V17_METHOD_SHA256,
        "source_path": str(selected_manifest_path.resolve()),
        "source_sha256": sha256_file(selected_manifest_path),
        "migration_role": "v17_to_v18_rebind",
    })
    registry_path.parent.mkdir(parents=True, exist_ok=True)
    _write_json_new(selected_rebind_path, rebind)
    _write_json_new(registry_path, registry)
    target_assignment_path.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(assignment_path, target_assignment_path)
    shutil.copyfile(assignment_path, target_distribution_path)
    worker_dir = output_dir / "worker_facing_distribution_C2B"
    for worker in sorted(worker_groups):
        _write(worker_dir / f"worker_{worker}_C2B.csv", [row for row in assignments if normalize_worker_id(row.get("worker_id", "")) == worker])
    for deployment in deployment_specs:
        _write_text_new(target_import_paths[deployment["deployment_id"]], target_import_texts[deployment["deployment_id"]])
    _write(mapping_path, mapping_rows)
    registry_sha = sha256_file(registry_path)
    for deployment in deployment_specs:
        deployment.update({
            "method_contract_version": target_method["contract_version"],
            "method_contract_sha256": target_method_sha,
            "assignment_sha256": sha256_file(target_assignment_path),
            "selected_design_id": "D8",
            "selected_design_sha": C2B_D8_DESIGN_SHA256,
            "design_manifest_sha256": C2B_D8_DESIGN_MANIFEST_SHA256,
            "task_pool_sha256": C2B_D8_TASK_POOL_SHA256,
            "worker_registry_sha256": registry_sha,
        })
    deployment_manifest = {
        "schema_version": "c2b_worker_deployment_manifest_v1",
        "artifact_role": "C2B_WORKER_DEPLOYMENT_MANIFEST_FROZEN",
        "contract_role": "generated_subordinate",
        "formal_ready": True,
        **_method_identity(),
        "assignment_batch_id": "C2B_BATCH_A",
        "assignment_sha256": sha256_file(target_assignment_path),
        "selected_design_id": "D8",
        "selected_design_sha": C2B_D8_DESIGN_SHA256,
        "design_manifest_sha256": C2B_D8_DESIGN_MANIFEST_SHA256,
        "task_pool_sha256": C2B_D8_TASK_POOL_SHA256,
        "selected_design_manifest_path": str(selected_rebind_path.resolve()),
        "selected_design_manifest_sha256": sha256_file(selected_rebind_path),
        "worker_registry_path": str(registry_path.resolve()),
        "worker_registry_sha256": registry_sha,
        "source_config_path": str(deployment_config.resolve()),
        "source_config_sha256": sha256_file(deployment_config),
        "deployments": deployment_specs,
        "frozen": True,
    }
    _write_json_new(deployment_manifest_path, deployment_manifest)
    deployment_manifest_sha = sha256_file(deployment_manifest_path)
    deployment_assignment_counts = {
        item["deployment_id"]: sum(
            worker_to_deployment.get(normalize_worker_id(row.get("worker_id", ""))) == item["deployment_id"]
            for row in assignments
        )
        for item in deployment_specs
    }
    report = {
        "schema_version": "paper_a_c2b_launch_ready_report_v4",
        "artifact_role": "C2B_LAUNCH_READY",
        "contract_role": "generated_subordinate",
        "method_contract": "Pilot->P1->C1->C2-B->C2-A-RP->T1->V1",
        "method_contract_version": target_method["contract_version"],
        "method_contract_sha256": target_method_sha,
        "source_method_contract_version": C2B_V17_METHOD_VERSION,
        "source_method_contract_sha256": C2B_V17_METHOD_SHA256,
        "assignment_batch_id": "C2B_BATCH_A",
        "selected_design_id": "D8",
        "selected_design_sha": C2B_D8_DESIGN_SHA256,
        "selected_design_manifest_path": str(selected_rebind_path.resolve()),
        "selected_design_manifest_sha256": sha256_file(selected_rebind_path),
        "design_manifest_sha256": C2B_D8_DESIGN_MANIFEST_SHA256,
        "task_pool_sha256": C2B_D8_TASK_POOL_SHA256,
        "assignment_sha256": sha256_file(target_assignment_path),
        "deployment_manifest_path": str(deployment_manifest_path.resolve()),
        "deployment_manifest_sha256": deployment_manifest_sha,
        "deployments": deployment_specs,
        "n_assignments": len(assignments),
        "n_workers": len(worker_groups),
        "n_tasks": len({str(row.get("task_id", "")) for row in assignments}),
        "deployment_assignment_counts": deployment_assignment_counts,
        "assignment_distribution_consistent": True,
        "import_smoke_passed": True,
        "gt_isolated_from_worker_import": True,
        "automatic_label_studio_import": False,
        "launch_ready": True,
        "C2B_LAUNCH_READY": True,
        "formal_ready": False,
        "runtime_binding_status": "not_bound",
        "migration_envelope_path": str(envelope_path.resolve()),
        "source_historical_launch_report_path": str(launch_report_path.resolve()),
        "source_historical_launch_report_sha256": sha256_file(launch_report_path),
        "dependencies": [
            {"role": role, "path": str(path.resolve()), "sha256": sha256_file(path)}
            for role, path in (
                ("SOURCE_V17_LAUNCH_REPORT", launch_report_path),
                ("SOURCE_V17_ASSIGNMENT", assignment_path),
                ("SOURCE_V17_SELECTED_DESIGN_MANIFEST", selected_manifest_path),
                ("WORKER_LANGUAGE_SOURCE", language_source),
                ("DEPLOYMENT_CONFIG", deployment_config),
                ("TARGET_SELECTED_DESIGN_MANIFEST", selected_rebind_path),
                ("TARGET_ASSIGNMENT", target_assignment_path),
                ("TARGET_DEPLOYMENT_MANIFEST", deployment_manifest_path),
                ("METHOD_CONTRACT", METHOD_CONTRACT),
            )
        ],
    }
    _write_json_new(launch_path, report)
    target_artifacts = [
        {"role": "TARGET_SELECTED_DESIGN_MANIFEST_V18", "path": str(selected_rebind_path.resolve()), "sha256": sha256_file(selected_rebind_path)},
        {"role": "TARGET_WORKER_LANGUAGE_REGISTRY", "path": str(registry_path.resolve()), "sha256": registry_sha},
        {"role": "TARGET_ASSIGNMENT", "path": str(target_assignment_path.resolve()), "sha256": sha256_file(target_assignment_path)},
        {"role": "TARGET_WORKER_DISTRIBUTION", "path": str(target_distribution_path.resolve()), "sha256": sha256_file(target_distribution_path)},
        {"role": "TARGET_ASSIGNMENT_MAPPING", "path": str(mapping_path.resolve()), "sha256": sha256_file(mapping_path)},
        {"role": "TARGET_DEPLOYMENT_MANIFEST", "path": str(deployment_manifest_path.resolve()), "sha256": deployment_manifest_sha},
        {"role": "TARGET_LAUNCH_REPORT_V4", "path": str(launch_path.resolve()), "sha256": sha256_file(launch_path)},
        *[
            {"role": f"TARGET_PLANNED_IMPORT_{item['deployment_id']}", "path": item["planned_import_path"], "sha256": item["planned_import_sha256"]}
            for item in deployment_specs
        ],
    ]
    source_artifacts = [
        {"role": "SOURCE_V17_LAUNCH_REPORT_SINGLE_DEPLOYMENT", "path": str(launch_report_path.resolve()), "sha256": sha256_file(launch_report_path)},
        {"role": "SOURCE_V17_ASSIGNMENT", "path": str(assignment_path.resolve()), "sha256": sha256_file(assignment_path)},
        {"role": "SOURCE_V17_SELECTED_DESIGN_MANIFEST", "path": str(selected_manifest_path.resolve()), "sha256": sha256_file(selected_manifest_path)},
        {"role": "SOURCE_V17_PLANNED_IMPORT_CHINESE", "path": str(import_paths["Chinese"].resolve()), "sha256": source_imports["Chinese"]["sha256"]},
        {"role": "SOURCE_V17_PLANNED_IMPORT_ENGLISH", "path": str(import_paths["English"].resolve()), "sha256": source_imports["English"]["sha256"]},
        {"role": "SOURCE_WORKER_LANGUAGE_DISTRIBUTION", "path": str(language_source.resolve()), "sha256": sha256_file(language_source)},
        {"role": "SOURCE_DEPLOYMENT_CONFIG", "path": str(deployment_config.resolve()), "sha256": sha256_file(deployment_config)},
    ]
    envelope = {
        "schema_version": "paper_a_c2b_v17_to_v18_repackage_envelope_v1",
        "artifact_role": "C2B_V17_TO_V18_REPACKAGE_ENVELOPE_FROZEN",
        "contract_role": "generated_subordinate",
        "formal_ready": False,
        "launch_ready": True,
        "status": "prospective_repackage",
        "runtime_binding_status": "not_bound",
        "method_contract_mapping": {
            "source": {
                "contract_version": C2B_V17_METHOD_VERSION,
                "sha256": C2B_V17_METHOD_SHA256,
            },
            "target": {
                "contract_version": target_method["contract_version"],
                "sha256": target_method_sha,
                "path": str(target_method_path.resolve()),
            },
        },
        "source_method_contract_version": C2B_V17_METHOD_VERSION,
        "source_method_contract_sha256": C2B_V17_METHOD_SHA256,
        "target_method_contract_version": target_method["contract_version"],
        "target_method_contract_sha256": target_method_sha,
        "selected_design_id": "D8",
        "selected_design_sha": C2B_D8_DESIGN_SHA256,
        "design_manifest_sha256": C2B_D8_DESIGN_MANIFEST_SHA256,
        "assignment_batch_id": "C2B_BATCH_A",
        "source_assignment_sha256": C2B_V17_D8_ASSIGNMENT_SHA256,
        "target_assignment_sha256": sha256_file(target_assignment_path),
        "n_assignments": 176,
        "n_workers": 22,
        "n_tasks": 46,
        "source_artifacts": source_artifacts,
        "target_artifacts": target_artifacts,
        "assignment_mapping_path": str(mapping_path.resolve()),
        "assignment_mapping_sha256": sha256_file(mapping_path),
        "unchanged_fields": ["selected_design_id", "selected_design_sha", "design_manifest_sha256", "task_pool_sha256", "assignment_batch_id", "task_id", "planned_task_id", "task_collection", "vis_3d"],
        "changed_fields": ["method_contract_version", "method_contract_sha256", "calibration_version", "deployment_id", "language_group", "server_instance_id", "project_id", "launch_report_schema", "planned_import_filename"],
        "dependencies": target_artifacts,
    }
    _write_json_new(envelope_path, envelope)
    return report


def _require_current_subordinate(path: Path, role: str) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    validate_generated_subordinate(payload, role=role)
    return payload


def _truth(value: Any) -> bool:
    return str(value).strip().lower() in {"true", "1", "yes"}


def _identity_key(row: dict[str, Any]) -> tuple[str, str, str]:
    return (
        normalize_worker_id(row.get("worker_id", "")),
        str(row.get("base_task_id", "")).strip(),
        str(row.get("condition", "")).strip().lower(),
    )


def _normalize_worker_rows(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    return [{**row, "worker_id": normalize_worker_id(row.get("worker_id", ""))} for row in rows]


def _repair_scope(scope: dict[str, Any]) -> dict[str, list[dict[str, str]]]:
    repairs = scope.get("authorized_repair_identities")
    if not isinstance(repairs, dict):
        raise ValueError("C1_A scope requires authorized_repair_identities grouped by w034 and w001")
    normalized: dict[str, list[dict[str, str]]] = {}
    for group, expected_count in (("w034", 17), ("w001", 3)):
        entries = repairs.get(group)
        if not isinstance(entries, list) or len(entries) != expected_count:
            raise ValueError(f"C1_A scope requires exactly {expected_count} {group} authorized repair identities")
        normalized[group] = []
        seen: set[tuple[str, str, str]] = set()
        for entry in entries:
            if not isinstance(entry, dict):
                raise ValueError(f"{group} repair identity is not an object")
            item = {name: str(entry.get(name, "")).strip() for name in ("worker_id", "base_task_id", "condition", "authorized_addendum_row_identity", "authorized_addendum_row_sha256")}
            item["worker_id"] = normalize_worker_id(item["worker_id"])
            item["condition"] = item["condition"].lower()
            key = _identity_key(item)
            expected_worker = "34" if group == "w034" else "1"
            if not all(key) or key in seen or key[0] != expected_worker:
                raise ValueError(f"{group} repair identities must be complete and unique by worker/base-task/condition")
            seen.add(key); normalized[group].append(item)
    return normalized


def _snapshot_dependencies(snapshot: dict[str, Any], *roles: str) -> dict[str, Path]:
    resolved: dict[str, Path] = {}
    dependencies = snapshot.get("dependencies", [])
    if not isinstance(dependencies, list):
        raise ValueError("C1_A snapshot dependencies are invalid")
    for role in roles:
        matches = [item for item in dependencies if isinstance(item, dict) and item.get("role") == role]
        if len(matches) != 1:
            raise ValueError(f"C1_A snapshot dependency is missing or ambiguous:{role}")
        path = Path(str(matches[0].get("path", "")))
        if not path.is_file() or matches[0].get("sha256") != sha256_file(path):
            raise ValueError(f"C1_A snapshot dependency is stale or unavailable:{role}")
        resolved[role] = path
    return resolved


def _addendum_row_sha256(row: dict[str, str]) -> str:
    return hashlib.sha256(json.dumps(row, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()


def _addendum_identity_key(row: dict[str, Any]) -> tuple[str, str, str]:
    return (
        normalize_worker_id(row.get("replacement_worker_id", row.get("worker_id", ""))),
        str(row.get("base_task_id", "")).strip(),
        str(row.get("condition", "")).strip().lower(),
    )


def _write_c1_a_scoped_input(source: Path, output_dir: Path, *, workers: set[str] | None = None, base_task_ids: set[str] | None = None) -> Path:
    """Copy only the frozen C1-A rows consumed by downstream C2-B materializers."""
    rows = _read(source)
    if workers is not None:
        rows = _normalize_worker_rows(rows)
        rows = [row for row in rows if row.get("worker_id", "") in workers]
    if base_task_ids is not None:
        rows = [row for row in rows if str(row.get("base_task_id") or row.get("task_id") or "") in base_task_ids]
    target = output_dir / source.name
    _write(target, rows)
    return target


def freeze_c1_batch(args: argparse.Namespace) -> dict[str, Any]:
    """Freeze C1-A analysis/design inputs without closing future enrollment."""
    c1_dir = args.c1_output_dir.resolve()
    scope = json.loads(args.batch_scope_manifest.read_text(encoding="utf-8"))
    if scope.get("schema_version") != "paper_a_c1_batch_scope_v1" or scope.get("batch_id") != "C1_A":
        raise ValueError("freeze-c1-batch requires a C1_A batch-scope manifest")
    cutoff = str(scope.get("data_cutoff_server_time", "")).strip()
    originals = {normalize_worker_id(value) for value in scope.get("original_worker_ids", []) if normalize_worker_id(value)}
    repairs = _repair_scope(scope)
    completion_exceptions = {str(value) for value in scope.get("original_completion_exception_task_ids", []) if str(value)}
    if not cutoff or not originals:
        raise ValueError("C1_A scope must bind cutoff and original roster")
    formal_profile_path = c1_dir / "c1_three_track_worker_state_formal.csv"
    profile_path = formal_profile_path if formal_profile_path.is_file() else c1_dir / "c1_three_track_worker_state.csv"
    eligibility_path = c1_dir / "c1_row_analysis_eligibility.csv"
    required = {
        "ANALYSIS_DEPENDENCY_BUNDLE": c1_dir / "analysis_dependency_manifest.json",
        "CANONICAL_ELIGIBILITY": eligibility_path,
        "VARIABLE_K": c1_dir / "c1_estimand_specific_task_support.csv",
        "PEER": c1_dir / "geometry_worker_task_peer_analysis.csv",
        "LOO": c1_dir / "geometry_worker_task_loo_analysis.csv",
        "Q_GT": c1_dir / "c1_gt_quality_analysis.csv",
        "Q_GT_MODEL_AUDIT": c1_dir / "c1_task_adjusted_qgt_model_audit.json",
        "STRUCTURAL_EB": c1_dir / "structural_validation_analysis.csv",
        "STRUCTURAL_EB_AUDIT": c1_dir / "c1_structural_reliability_eb.csv",
        "COMPLETION": c1_dir / "c1_worker_completion_audit.csv",
        "REFERENCE": c1_dir / "c1_task_outcome_reference.csv",
        "SCOPE_FINAL_DISPOSITION": c1_dir / "c1_task_scope_final_disposition.csv",
        "BUILDING": c1_dir / "c1_task_building_binding.csv",
        "W034_SENSITIVITY": c1_dir / "w034_original_vs_authorized_sensitivity.json",
        "WORKER_PROFILE": profile_path,
        "MEASUREMENT_READINESS": c1_dir / "c1_measurement_readiness_by_worker.csv",
    }
    blockers = [f"missing:{role}" for role, path in required.items() if not path.is_file()]
    profile_rows = _normalize_worker_rows(_read(profile_path)) if profile_path.is_file() else []
    repair_workers = {entry["worker_id"] for values in repairs.values() for entry in values}
    included_workers = originals | repair_workers
    late_workers = {
        row.get("worker_id", "") for row in profile_rows
        if row.get("enrollment_batch") == "late_entry"
    }
    expected_originals = {
        row.get("worker_id", "") for row in profile_rows
        if row.get("enrollment_batch") == "original"
        and not (
            str(row.get("completion_status", "")).strip().lower() in {"nonstarter", "administrative_exclusion"}
            or str(row.get("administratively_eligible", "")).strip().lower() in {"false", "0", "no"}
        )
    }
    if originals != expected_originals:
        blockers.append(
            "original_roster_scope_mismatch:expected="
            + ",".join(sorted(expected_originals))
            + ";actual="
            + ",".join(sorted(originals))
        )
    completion_by_worker = {
        row.get("worker_id", ""): row for row in _normalize_worker_rows(_read(required["COMPLETION"]))
    } if required["COMPLETION"].is_file() else {}
    missing_completion_workers = sorted(originals - set(completion_by_worker))
    nonterminal_completion_workers = sorted(
        worker for worker in originals
        if worker in completion_by_worker
        and completion_by_worker[worker].get("completion_status", "") not in _TERMINAL_CALIBRATION_STATUSES
    )
    if missing_completion_workers:
        blockers.append("c1_a_completion_audit_missing:" + ",".join(missing_completion_workers))
    if nonterminal_completion_workers:
        blockers.append("c1_a_nonterminal_worker:" + ",".join(nonterminal_completion_workers))
    eligibility_rows = _normalize_worker_rows(_read(eligibility_path)) if eligibility_path.is_file() else []
    repair_rows: list[dict[str, str]] = []
    addendum_rows = _read(args.authorized_reassignment_manifest) if getattr(args, "authorized_reassignment_manifest", None) else []
    for group, entries in repairs.items():
        for entry in entries:
            label = ":".join((group, *(_identity_key(entry))))
            candidates = [
                row for row in eligibility_rows
                if _identity_key(row) == _identity_key(entry)
                and row.get("assignment_provenance") == "authorized_replacement_assignment"
                and _truth(row.get("formal_assignment_eligible"))
                and str(row.get("canonical_annotation_id", "")).strip()
            ]
            if len(candidates) != 1:
                blockers.append(f"authorized_repair_identity_unresolved:{label}")
                continue
            if entry["authorized_addendum_row_identity"] or entry["authorized_addendum_row_sha256"]:
                matching_addenda = [row for row in addendum_rows if _addendum_identity_key(row) == _identity_key(entry)]
                if len(matching_addenda) != 1:
                    blockers.append(f"authorized_addendum_identity_unresolved:{label}")
                    continue
                addendum = matching_addenda[0]
                row_identity = next((str(addendum.get(name, "")).strip() for name in ("authorized_addendum_row_identity", "authorized_reassignment_row_id", "row_id", "id") if str(addendum.get(name, "")).strip()), "")
                if (entry["authorized_addendum_row_identity"] and entry["authorized_addendum_row_identity"] != row_identity) or (entry["authorized_addendum_row_sha256"] and entry["authorized_addendum_row_sha256"] != _addendum_row_sha256(addendum)):
                    blockers.append(f"authorized_addendum_identity_mismatch:{label}")
                    continue
            repair_rows.append({**candidates[0], "repair_group": group})
    canonical_repair_ids = {row["canonical_annotation_id"] for row in repair_rows}
    if len(canonical_repair_ids) != 20:
        blockers.append("authorized_repair_count_not_exactly_20")
    completion_rows = {str(row.get("task_id") or row.get("planned_task_id") or row.get("canonical_annotation_id") or ""): row for row in eligibility_rows if row.get("worker_id") in originals}
    missing_completion = sorted(completion_exceptions - set(completion_rows))
    if missing_completion:
        blockers.append("original_completion_exception_missing:" + ",".join(missing_completion))
    nonterminal_completion = sorted(task for task in completion_exceptions & set(completion_rows) if not (_truth(completion_rows[task].get("formal_assignment_eligible")) or str(completion_rows[task].get("completion_status", "")) in _TERMINAL_CALIBRATION_STATUSES))
    if nonterminal_completion:
        blockers.append("original_completion_exception_not_terminal:" + ",".join(nonterminal_completion))
    included_rows = [
        row for row in eligibility_rows
        if (row.get("worker_id") in originals and row.get("assignment_provenance") == "original_assignment")
        or row.get("canonical_annotation_id") in canonical_repair_ids
    ]
    eligible_base_task_ids = sorted({str(row.get("base_task_id", "")) for row in included_rows if _truth(row.get("formal_assignment_eligible")) and row.get("base_task_id")})
    scope_rows = _read(required["SCOPE_FINAL_DISPOSITION"]) if required["SCOPE_FINAL_DISPOSITION"].is_file() else []
    terminal_scope_by_task = {
        str(row.get("base_task_id", "")): str(row.get("task_final_scope", "")).strip().lower()
        for row in scope_rows
        if str(row.get("scope_resolution_status", "")).strip().lower() in {"resolved", "terminal_unresolved"}
    }
    nonterminal_scope_tasks = sorted(
        task for task in eligible_base_task_ids
        if terminal_scope_by_task.get(task) not in {"in_scope", "oos", "unresolved"}
    )
    if nonterminal_scope_tasks:
        blockers.append("c1_a_scope_not_terminal:" + ",".join(nonterminal_scope_tasks))
    identity_rows = [{
        "canonical_annotation_id": row.get("canonical_annotation_id", ""), "worker_id": row.get("worker_id", ""),
        "base_task_id": row.get("base_task_id", ""), "condition": row.get("condition", ""),
        "assignment_provenance": row.get("assignment_provenance", ""),
        "included_in_c1_a": str(row in included_rows).lower(),
    } for row in eligibility_rows]
    identity_manifest = args.output.parent / "c1_a_canonical_annotation_identity_manifest.csv"
    _write(identity_manifest, identity_rows)
    w034 = json.loads(required["W034_SENSITIVITY"].read_text(encoding="utf-8")) if required["W034_SENSITIVITY"].is_file() else {}
    if w034.get("status") != "frozen": blockers.append("w034_sensitivity_not_frozen")
    if not any(_truth(row.get("c2_risk_model_eligible")) for row in profile_rows if row.get("worker_id") in included_workers): blockers.append("no_c2b_eligible_original_worker")
    scoped_dir = args.output.parent / "c1_a_batch_inputs"
    scoped_dependencies = {
        role: _write_c1_a_scoped_input(path, scoped_dir, workers=included_workers)
        for role, path in required.items()
        if role in {"PEER", "LOO", "Q_GT", "STRUCTURAL_EB", "COMPLETION", "WORKER_PROFILE", "MEASUREMENT_READINESS"} and path.is_file()
    }
    if required["VARIABLE_K"].is_file():
        # variable-k is task-level, so filtering it by worker_id would erase its rows.
        scoped_dependencies["VARIABLE_K"] = _write_c1_a_scoped_input(required["VARIABLE_K"], scoped_dir)
    canonical_scoped = scoped_dir / eligibility_path.name
    _write(canonical_scoped, included_rows)
    scoped_dependencies["CANONICAL_ELIGIBILITY"] = canonical_scoped
    scoped_dependencies.update({
        role: _write_c1_a_scoped_input(required[role], scoped_dir, base_task_ids=set(eligible_base_task_ids))
        for role in ("REFERENCE", "SCOPE_FINAL_DISPOSITION", "BUILDING") if required[role].is_file()
    })
    frozen = not blockers
    snapshot = {
        "schema_version": "paper_a_c1_batch_analysis_snapshot_v1", "artifact_role": "C1_A_ANALYSIS_SNAPSHOT", "batch_id": "C1_A",
        "status": "formal_design_eligible" if frozen else "provisional", "data_cutoff_server_time": cutoff,
        "source_c1_output_dir": str(c1_dir), "source_c1_output_manifest_sha256": sha256_file(required["ANALYSIS_DEPENDENCY_BUNDLE"]) if required["ANALYSIS_DEPENDENCY_BUNDLE"].is_file() else "",
        "original_worker_ids": sorted(originals), "authorized_repair_set": {"w034": [entry for entry in repairs["w034"]], "w001": [entry for entry in repairs["w001"]], "resolved_canonical_annotation_ids": sorted(canonical_repair_ids), "expected_count": 20}, "original_completion_exception_task_ids": sorted(completion_exceptions),
        "included_canonical_annotation_identity_manifest_sha256": sha256_file(identity_manifest),
        "eligible_base_task_ids": eligible_base_task_ids, "excluded_late_entry_worker_ids": sorted(late_workers), "reference_registry_sha256": sha256_file(required["REFERENCE"]) if required["REFERENCE"].is_file() else "",
        "C1_A_ANALYSIS_SNAPSHOT_MATERIALIZED": True, "C1_A_ANALYSIS_SNAPSHOT_FROZEN": frozen, "C2B_BASELINE_INPUT_FROZEN": frozen, "C2B_DESIGN_INPUT_FROZEN_FROM_C1_A": frozen,
        "C2B_ASSIGNMENT_BATCH_A_MATERIALIZED": False, "C2B_ASSIGNMENT_BATCH_B_MATERIALIZED": False,
        "CALIBRATION_ENROLLMENT_CLOSED": False, "ALL_CALIBRATION_WORKERS_TERMINAL": False, "FINAL_POOLED_PROFILE_FROZEN": False,
        "blockers": blockers, **_method_identity(),
        "dependencies": [{"role": role, "path": str(scoped_dependencies.get(role, path).resolve()), "sha256": sha256_file(scoped_dependencies.get(role, path))} for role, path in required.items() if path.is_file()] + ([{"role": "AUTHORIZED_REASSIGNMENT_MANIFEST", "path": str(args.authorized_reassignment_manifest.resolve()), "sha256": sha256_file(args.authorized_reassignment_manifest)}] if getattr(args, "authorized_reassignment_manifest", None) else []) + [{"role": "BATCH_SCOPE", "path": str(args.batch_scope_manifest.resolve()), "sha256": sha256_file(args.batch_scope_manifest)}, {"role": "CANONICAL_IDENTITY_MANIFEST", "path": str(identity_manifest.resolve()), "sha256": sha256_file(identity_manifest)}, {"role": "METHOD_CONTRACT", "path": str(METHOD_CONTRACT.resolve()), "sha256": sha256_file(METHOD_CONTRACT)}],
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(snapshot, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return snapshot


def _require_approval(path: Path, evidence: Path, sha_field: str) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if payload.get("approved") is not True or payload.get(sha_field) != sha256_file(evidence):
        raise ValueError(f"approval_invalid_or_stale:{sha_field}")
    return payload


def _c2_source_images(rows: list[dict[str, str]]) -> set[str]:
    return {
        row.get("image_id", "") for row in rows
        if str(row.get("allocation", row.get("source_split_allowed", ""))).lower() in {"c2", "c2_source", "true", "1", "allowed"}
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


_STAGE3_EXPOSURE_STAGES = ("P1", "C1", "C2B", "C2A_RP", "T1")
_STAGE3_SOURCE_METHOD_VERSION = "paper_a_method_20260802_v17"
_STAGE3_SOURCE_METHOD_SHA256 = "5068e08ade8d1f2013b5ed66af04761c210acf74ef522229ffd39ad8f6b17b4c"
_STAGE3_EXPOSURE_FLAG_FIELDS = {
    "P1": ("P1_exposed", "p1_exposed", "used_in_prescreen"),
    "C1": ("C1_exposed", "c1_exposed", "used_in_random_c1", "used_in_random_c1_deprecated"),
    "C2B": ("C2B_exposed", "c2b_exposed"),
    "C2A_RP": ("C2A_RP_exposed", "c2a_rp_exposed"),
    "T1": ("T1_exposed", "t1_exposed"),
}
_STAGE3_INVENTORY_FIELDS = (
    "schema_version", "task_id", "base_task_id", "image_id", "source_split", "source_pool",
    "building_id_candidate", "building_id", "building_registry_status",
    "image_path", "image_sha256", "gt_path", "gt_sha256", "gt_present",
    "layout_path", "layout_sha256", "layout_present", "model_input_status",
    "P1_exposed", "C1_exposed", "C2B_exposed", "C2A_RP_exposed", "T1_exposed",
    "P1_exposure_status", "C1_exposure_status", "C2B_exposure_status",
    "C2A_RP_exposure_status", "T1_exposure_status", "validation_overlap_status",
    "duplicate_test_content_status", "v1_candidate_eligible", "candidate_blockers_json",
)
_STAGE3_OVERLAP_FIELDS = (
    "schema_version", "audit_type", "stage", "image_id", "base_task_id", "test_image_sha256",
    "source_manifest_path", "source_manifest_sha256", "source_path", "source_sha256",
    "match_type", "status", "reason",
)
_STAGE3_RISK_FIELDS = (
    "schema_version", "task_id", "base_task_id", "image_id", "source_split",
    "building_id", "building_registry_status", "d_model_feat", "d_model_feat_local_max",
    "g_model_struct", "d_cal_A", "risk_design_vector_A", "risk_design_score_A",
    "risk_design_score_A_percentile", "risk_design_q75", "risk_design_stratum",
    "risk_design_stratum_source", "risk_status", "risk_missing_reason", "layout_status",
    "feature_status", "feature_audit_status", "postprocess_valid", "risk_route",
    "risk_route_status", "d_cal_F", "family_scores", "P1_exposed", "C1_exposed",
    "C2B_exposed", "C2A_RP_exposed", "T1_exposed", "v1_candidate_eligible",
    "candidate_only", "candidate_blockers_json",
)


def _stage3_resolve(path: Path | None) -> Path | None:
    if path is None:
        return None
    candidate = Path(path)
    return candidate.resolve() if candidate.is_absolute() else (_PROJECT_ROOT / candidate).resolve()


def _stage3_write_csv(path: Path, rows: list[dict[str, Any]], fields: tuple[str, ...]) -> None:
    allowed = set(fields)
    unknown = sorted({key for row in rows for key in row if key not in allowed})
    if unknown:
        raise ValueError(f"stage3 candidate CSV has undeclared fields:{unknown}")
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(fields), extrasaction="raise")
        writer.writeheader()
        writer.writerows({field: row.get(field, "") for field in fields} for row in rows)


def _stage3_file_index(directory: Path, suffixes: tuple[str, ...]) -> dict[str, Path]:
    if not directory.is_dir():
        raise ValueError(f"stage3 source directory is missing:{directory}")
    index: dict[str, Path] = {}
    for path in sorted(directory.iterdir(), key=lambda item: item.name.lower()):
        if not path.is_file() or path.suffix.lower() not in suffixes:
            continue
        stem = path.stem
        if stem in index:
            raise ValueError(f"stage3 source has duplicate image stem:{stem}")
        index[stem] = path.resolve()
    if not index:
        raise ValueError(f"stage3 source directory is empty:{directory}")
    return index


def _stage3_load_test_list(path: Path) -> list[dict[str, str]]:
    if not path.is_file():
        raise ValueError(f"stage3 test list is missing:{path}")
    rows: list[dict[str, str]] = []
    seen: set[str] = set()
    for line_number, raw in enumerate(path.read_text(encoding="utf-8-sig").splitlines(), start=1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split()
        if len(parts) != 2:
            raise ValueError(f"stage3 test list requires building_id_candidate and image_id:{path}:{line_number}")
        building, image = parts
        if image in seen:
            raise ValueError(f"stage3 test list has duplicate image_id:{image}")
        seen.add(image)
        rows.append({"building_id_candidate": building, "image_id": image})
    if not rows:
        raise ValueError("stage3 test list is empty")
    return rows


def _stage3_approved_buildings(path: Path | None) -> tuple[dict[str, dict[str, str]], str]:
    if path is None:
        return {}, ""
    if not path.is_file():
        raise ValueError(f"stage3 building registry is missing:{path}")
    mapping: dict[str, dict[str, str]] = {}
    for row in _read(path):
        approved = (
            str(row.get("registry_status", "")).lower() == "approved"
            and all(str(row.get(field, "")).strip() for field in ("building_id", "reviewed_by", "reviewed_at"))
        )
        if not approved:
            continue
        keys = {str(row.get(field, "")).strip() for field in ("image_id", "base_task_id", "task_id") if str(row.get(field, "")).strip()}
        for key in keys:
            previous = mapping.get(key)
            if previous and previous.get("building_id") != row.get("building_id"):
                raise ValueError(f"stage3 building registry has conflicting approved mapping:{key}")
            mapping[key] = row
    return mapping, sha256_file(path)


def _stage3_make_inventory(args: argparse.Namespace) -> list[dict[str, Any]]:
    test_list = _stage3_load_test_list(_stage3_resolve(args.test_list))
    images = _stage3_file_index(_stage3_resolve(args.image_dir), (".png",))
    gt = _stage3_file_index(_stage3_resolve(args.gt_dir), (".txt",))
    layouts = _stage3_file_index(_stage3_resolve(args.layout_dir), (".json",))
    for item in test_list:
        token = item["image_id"]
        prefixed = f"{item['building_id_candidate']}_{token}"
        if token not in images and prefixed in images:
            item["image_id"] = prefixed
    if len({row["image_id"] for row in test_list}) != len(test_list):
        raise ValueError("stage3 test list has duplicate resolved image_id")
    expected = {row["image_id"] for row in test_list}
    for label, index in (("image", images), ("GT", gt), ("layout", layouts)):
        missing = sorted(expected - set(index))
        extra = sorted(set(index) - expected)
        if missing or extra:
            raise ValueError(f"stage3 {label} identity mismatch:missing={missing[:5]} extra={extra[:5]}")
    buildings, _registry_sha = _stage3_approved_buildings(_stage3_resolve(args.building_registry))
    rows: list[dict[str, Any]] = []
    for item in test_list:
        image_id = item["image_id"]
        image_path, gt_path, layout_path = images[image_id], gt[image_id], layouts[image_id]
        registry = buildings.get(image_id, {})
        building_id = str(registry.get("building_id", "")).strip()
        rows.append({
            "schema_version": "paper_a_stage3_test_inventory_candidate_v1",
            "task_id": image_id, "base_task_id": image_id, "image_id": image_id,
            "source_split": "test", "source_pool": "data/mp3d_layout/test",
            "building_id_candidate": item["building_id_candidate"], "building_id": building_id,
            "building_registry_status": "approved" if building_id else "unresolved_scene_mapping",
            "image_path": image_path.as_posix(), "image_sha256": sha256_file(image_path),
            "gt_path": gt_path.as_posix(), "gt_sha256": sha256_file(gt_path), "gt_present": "true",
            "layout_path": layout_path.as_posix(), "layout_sha256": sha256_file(layout_path),
            "layout_present": "true", "model_input_status": "ready",
            "P1_exposed": "", "C1_exposed": "", "C2B_exposed": "", "C2A_RP_exposed": "", "T1_exposed": "",
            "P1_exposure_status": "not_proven", "C1_exposure_status": "not_proven",
            "C2B_exposure_status": "not_proven", "C2A_RP_exposure_status": "not_proven",
            "T1_exposure_status": "not_proven", "validation_overlap_status": "not_checked",
            "duplicate_test_content_status": "not_checked", "v1_candidate_eligible": "false",
            "candidate_blockers_json": "[]",
        })
    return rows


def _stage3_flatten_source_row(row: dict[str, Any]) -> dict[str, Any]:
    data = row.get("data") if isinstance(row.get("data"), dict) else {}
    return {**data, **row}


def _stage3_local_source_path(value: Any, source_path: Path) -> str:
    text = str(value or "").strip()
    if not text or "://" in text:
        return ""
    candidate = Path(text)
    if not candidate.is_absolute():
        for base in (source_path.parent, _PROJECT_ROOT):
            resolved = (base / candidate).resolve()
            if resolved.is_file():
                return resolved.as_posix()
        return ""
    return candidate.resolve().as_posix() if candidate.is_file() else ""


def _stage3_parse_exposure_sources(specs: list[str] | None) -> tuple[dict[str, list[dict[str, Any]]], dict[str, dict[str, str]]]:
    sources: dict[str, list[dict[str, Any]]] = defaultdict(list)
    source_meta: dict[str, dict[str, str]] = {}
    for spec in specs or []:
        if "=" not in spec:
            raise ValueError("--exposure-source must use STAGE=PATH")
        stage_raw, path_raw = spec.split("=", 1)
        stage = stage_raw.strip().upper().replace("-", "_")
        if stage not in _STAGE3_EXPOSURE_STAGES:
            raise ValueError(f"unsupported stage3 exposure stage:{stage_raw}")
        path = _stage3_resolve(Path(path_raw.strip()))
        if not path or not path.is_file():
            raise ValueError(f"stage3 exposure source is missing:{path}")
        rows = _migration_source_rows(path)
        if not rows:
            raise ValueError(f"stage3 exposure source is empty:{path}")
        flag_fields = _STAGE3_EXPOSURE_FLAG_FIELDS[stage]
        has_stage_flag = any(field in _stage3_flatten_source_row(row) for row in rows for field in flag_fields)
        for raw_row in rows:
            row = _stage3_flatten_source_row(raw_row)
            if has_stage_flag and not any(_truth(row.get(field)) for field in flag_fields if field in row):
                continue
            identifiers = {
                str(row.get(field, "")).strip()
                for field in ("image_id", "base_task_id", "task_id", "planned_task_id")
                if str(row.get(field, "")).strip()
            }
            hashes = {
                str(row.get(field, "")).strip().lower()
                for field in ("image_sha256", "candidate_image_sha256", "source_image_sha256")
                if len(str(row.get(field, "")).strip()) == 64
            }
            local_paths = {
                local for field in ("source_path", "image_path", "image", "image_url")
                if (local := _stage3_local_source_path(row.get(field), path))
            }
            if not identifiers and not hashes and not local_paths:
                continue
            sources[stage].append({
                "identifiers": identifiers, "hashes": hashes, "paths": local_paths,
                "source_path": str(path.resolve()), "source_sha256": sha256_file(path),
            })
        source_meta[f"{stage}:{path.resolve().as_posix()}"] = {
            "stage": stage, "path": str(path.resolve()), "sha256": sha256_file(path),
            "rows": str(len(rows)), "flagged_rows": str(len(sources[stage])),
        }
    return dict(sources), source_meta


def _stage3_source_matches(row: dict[str, Any], source: dict[str, Any]) -> list[str]:
    matches: list[str] = []
    identifiers = {str(row.get(field, "")).strip() for field in ("image_id", "base_task_id", "task_id") if str(row.get(field, "")).strip()}
    if identifiers & source["identifiers"]:
        matches.append("identity")
    if str(row.get("image_sha256", "")).strip().lower() in source["hashes"]:
        matches.append("content_sha256")
    if str(row.get("image_path", "")).strip() in source["paths"]:
        matches.append("path")
    return sorted(set(matches))


def _stage3_audit_inventory(args: argparse.Namespace, inventory: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], dict[str, dict[str, str]]]:
    sources, source_meta = _stage3_parse_exposure_sources(getattr(args, "exposure_source", None))
    audit_rows: list[dict[str, Any]] = []
    for stage in _STAGE3_EXPOSURE_STAGES:
        stage_sources = sources.get(stage, [])
        for row in inventory:
            matches = [(source, _stage3_source_matches(row, source)) for source in stage_sources]
            matches = [(source, types) for source, types in matches if types]
            if matches:
                status, reason = "overlap", "source_identity_or_content_match"
                match_type = ";".join(sorted({value for _source, types in matches for value in types}))
                source_paths = ";".join(sorted({source["source_path"] for source, _types in matches}))
                source_shas = ";".join(sorted({source["source_sha256"] for source, _types in matches}))
                source_manifest_path = source_paths
                source_manifest_sha = source_shas
                row[f"{stage}_exposed"] = "true"
            elif stage_sources:
                status, reason, match_type = "clear", "source_checked_no_match", ""
                source_manifest_path = ";".join(sorted({source["source_path"] for source in stage_sources}))
                source_manifest_sha = ";".join(sorted({source["source_sha256"] for source in stage_sources}))
                source_paths = source_shas = ""
                row[f"{stage}_exposed"] = "false"
            else:
                status, reason, match_type = "not_proven", "source_not_provided", ""
                source_manifest_path = source_manifest_sha = source_paths = source_shas = ""
                row[f"{stage}_exposed"] = ""
            row[f"{stage}_exposure_status"] = status
            audit_rows.append({
                "schema_version": "paper_a_stage3_test_overlap_audit_v1", "audit_type": "stage_exposure",
                "stage": stage, "image_id": row["image_id"], "base_task_id": row["base_task_id"],
                "test_image_sha256": row["image_sha256"], "source_manifest_path": source_manifest_path,
                "source_manifest_sha256": source_manifest_sha, "source_path": source_paths,
                "source_sha256": source_shas, "match_type": match_type, "status": status, "reason": reason,
            })

    validation_dir = _stage3_resolve(args.validation_image_dir)
    validation_files = _stage3_file_index(validation_dir, (".png", ".jpg", ".jpeg"))
    validation_listing = [{"path": path.as_posix(), "size": path.stat().st_size, "sha256": sha256_file(path)} for path in validation_files.values()]
    validation_sha = _aggregate_sha(sorted(validation_listing, key=lambda item: item["path"]))
    validation_by_hash = {item["sha256"]: item["path"] for item in validation_listing}
    validation_ids = set(validation_files)
    for row in inventory:
        match_type = []
        if row["image_id"] in validation_ids:
            match_type.append("identity")
        if row["image_sha256"] in validation_by_hash:
            match_type.append("content_sha256")
        status = "overlap" if match_type else "clear"
        row["validation_overlap_status"] = status
        audit_rows.append({
            "schema_version": "paper_a_stage3_test_overlap_audit_v1", "audit_type": "split_overlap",
            "stage": "VALIDATION", "image_id": row["image_id"], "base_task_id": row["base_task_id"],
            "test_image_sha256": row["image_sha256"], "source_manifest_path": str(validation_dir.resolve()),
            "source_manifest_sha256": validation_sha,
            "source_path": validation_by_hash.get(row["image_sha256"], ""),
            "source_sha256": row["image_sha256"] if row["image_sha256"] in validation_by_hash else "",
            "match_type": ";".join(match_type), "status": status,
            "reason": "test_validation_overlap" if match_type else "test_validation_disjoint",
        })

    by_hash: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in inventory:
        by_hash[row["image_sha256"]].append(row)
    for digest, rows in by_hash.items():
        duplicate = len(rows) > 1
        for row in rows:
            row["duplicate_test_content_status"] = "overlap" if duplicate else "clear"
            if duplicate:
                audit_rows.append({
                    "schema_version": "paper_a_stage3_test_overlap_audit_v1", "audit_type": "duplicate_test_content",
                    "stage": "TEST", "image_id": row["image_id"], "base_task_id": row["base_task_id"],
                    "test_image_sha256": digest, "source_manifest_path": "", "source_manifest_sha256": "",
                    "source_path": ";".join(item["image_path"] for item in rows), "source_sha256": digest,
                    "match_type": "content_sha256", "status": "overlap", "reason": "duplicate_test_image_content",
                })
    return audit_rows, source_meta


def _stage3_candidate_blockers(row: dict[str, Any]) -> list[str]:
    blockers = []
    for stage in _STAGE3_EXPOSURE_STAGES:
        if row.get(f"{stage}_exposure_status") != "clear":
            blockers.append(f"{stage}_exposure_{row.get(f'{stage}_exposure_status') or 'unknown'}")
    if row.get("validation_overlap_status") != "clear":
        blockers.append("validation_overlap")
    if row.get("duplicate_test_content_status") != "clear":
        blockers.append("duplicate_test_content")
    if row.get("building_registry_status") != "approved":
        blockers.append("building_registry_unresolved")
    return sorted(set(blockers))


def _stage3_load_feature_reference(args: argparse.Namespace) -> tuple[dict[str, Any], dict[str, Any], Path]:
    manifest_path = _stage3_resolve(args.feature_freeze_manifest)
    checkpoint = _stage3_resolve(args.checkpoint)
    config = _stage3_resolve(args.config)
    payload = _read_json_object(manifest_path)
    if payload.get("schema_version") != "paper_a_c2_feature_freeze_v2":
        raise ValueError("stage3 feature freeze manifest schema is invalid")
    if payload.get("feature_audit_status") != "approved" or not all(payload.get(flag) is True for flag in ("pca_frozen", "whitening_frozen", "circular_shift_invariant", "seam_invariant")):
        raise ValueError("stage3 requires an approved frozen feature reference")
    if payload.get("checkpoint_sha256") != sha256_file(checkpoint) or payload.get("config_sha256") != sha256_file(config):
        raise ValueError("stage3 feature reference checkpoint/config identity mismatch")
    cache = Path(str(payload.get("feature_cache_path", "")))
    if not cache.is_absolute():
        cache = (manifest_path.parent / cache).resolve()
    if not cache.is_file() or sha256_file(cache) != payload.get("reference_feature_sha256"):
        raise ValueError("stage3 frozen reference feature cache is missing or stale")
    with np.load(cache) as values:
        required = ("global_mean", "global_components", "global_scale", "local_mean", "local_components", "local_scale", "reference_global", "reference_local")
        if any(name not in values for name in required):
            raise ValueError("stage3 frozen reference feature cache is incomplete")
        cache_payload = {name: np.asarray(values[name]).copy() for name in required}
    return payload, cache_payload, cache


def _stage3_source_method_binding(args: argparse.Namespace, reference_csv: Path) -> dict[str, Any]:
    summary_path = _stage3_resolve(args.c1_risk_summary)
    summary = _read_json_object(summary_path)
    reference_sha = sha256_file(reference_csv)
    if summary.get("c1_task_risk_reference_sha256") != reference_sha:
        raise ValueError("stage3 C1 risk reference does not match its source summary")
    target = _method_identity()
    source_version = str(summary.get("method_contract_version", "")).strip()
    source_sha = str(summary.get("method_contract_sha256", "")).strip()
    if source_version != _STAGE3_SOURCE_METHOD_VERSION or source_sha != _STAGE3_SOURCE_METHOD_SHA256:
        raise ValueError("stage3 source risk summary is not the frozen v17 input")
    return {
        "source_method_contract_version": source_version,
        "source_method_contract_sha256": source_sha,
        "target_method_contract_version": target["method_contract_version"],
        "target_method_contract_sha256": target["method_contract_sha256"],
        "source_risk_summary_path": str(summary_path),
        "source_risk_summary_sha256": sha256_file(summary_path),
        "source_c1_risk_reference_path": str(reference_csv),
        "source_c1_risk_reference_sha256": reference_sha,
    }


def _stage3_materialize_risk(
    args: argparse.Namespace, inventory: list[dict[str, Any]], staging: Path,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    reference_csv = _stage3_resolve(args.c1_risk_reference)
    risk_contract_path = _stage3_resolve(args.risk_contract)
    risk_contract = _read_json_object(risk_contract_path)
    if risk_contract.get("schema_version") != "paper_a_c2b_risk_design_contract_v1":
        raise ValueError("stage3 risk contract schema is invalid")
    if risk_contract.get("method_contract_sha256") != _method_identity()["method_contract_sha256"]:
        raise ValueError("stage3 risk contract is not bound to current method contract")
    stress_quantile = float(risk_contract["stratum_rule"]["stress_quantile"])
    frozen_reference = load_frozen_c1_risk_reference(reference_csv, stress_quantile=stress_quantile)
    feature_manifest, reference_cache, reference_cache_path = _stage3_load_feature_reference(args)
    threshold_path = _stage3_resolve(args.feature_audit_threshold_manifest)
    thresholds = _read_json_object(threshold_path)
    threshold_sha = sha256_file(threshold_path)
    if feature_manifest.get("feature_audit_threshold_manifest_sha256") != threshold_sha:
        raise ValueError("stage3 feature threshold manifest is not bound to the frozen feature manifest")
    checkpoint, config = _stage3_resolve(args.checkpoint), _stage3_resolve(args.config)
    output_dir = _stage3_resolve(args.output_dir)
    image_paths = [Path(row["image_path"]) for row in inventory]
    descriptors, extraction_audit = extract_orbit_descriptors(
        image_paths, checkpoint, config, device=args.device, batch_size=4, audit_seam=True,
    )
    ordered_paths = [path.resolve().as_posix() for path in image_paths]
    candidate_cache_path = staging / "stage3_test_candidate_lhfeat_cache.npz"
    np.savez_compressed(
        candidate_cache_path,
        paths=np.asarray(ordered_paths),
        global_descriptors=np.stack([descriptors[path][0] for path in ordered_paths]),
        local_descriptors=np.stack([descriptors[path][1] for path in ordered_paths]),
    )
    circular_ready, seam_ready = _feature_audit_passes(extraction_audit, extraction_audit, thresholds)
    feature_audit_status = "approved" if circular_ready and seam_ready else "pending_threshold_approval_or_failed"
    candidate_feature_manifest = {
        "schema_version": "paper_a_stage3_test_feature_candidate_v1",
        "artifact_role": "STAGE3_TEST_FEATURE_CANDIDATE",
        "contract_role": "generated_subordinate",
        **_method_identity(), "candidate_only": True, "formal_ready": False,
        "source_feature_freeze_manifest_path": str(_stage3_resolve(args.feature_freeze_manifest)),
        "source_feature_freeze_manifest_sha256": sha256_file(_stage3_resolve(args.feature_freeze_manifest)),
        "reference_feature_cache_path": str(reference_cache_path),
        "reference_feature_cache_sha256": sha256_file(reference_cache_path),
        "candidate_descriptor_cache_path": str(output_dir / candidate_cache_path.name),
        "candidate_descriptor_cache_sha256": sha256_file(candidate_cache_path),
        "feature_audit_threshold_manifest_path": str(threshold_path),
        "feature_audit_threshold_manifest_sha256": threshold_sha,
        "candidate_descriptor_count": len(ordered_paths),
        "candidate_extraction_audit": extraction_audit,
        "candidate_circular_robustness": circular_ready,
        "candidate_seam_robustness": seam_ready,
        "feature_audit_status": feature_audit_status,
        "checkpoint_sha256": sha256_file(checkpoint), "config_sha256": sha256_file(config),
    }
    feature_manifest_path = staging / "stage3_test_feature_candidate_manifest.json"
    feature_manifest_path.write_text(json.dumps(candidate_feature_manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    source_binding = _stage3_source_method_binding(args, reference_csv)
    risk_rows: list[dict[str, Any]] = []
    for item in inventory:
        layout_status = "missing"
        layout: dict[str, Any] = {}
        try:
            layout = _layout_features(Path(item["layout_path"]))
            layout_status = str(layout.get("layout_status", "missing"))
        except (OSError, ValueError, TypeError, KeyError, json.JSONDecodeError):
            layout = {"layout_status": "invalid", "postprocess_valid": False, "g_model_struct": ""}
            layout_status = "invalid"
        descriptor = descriptors.get(Path(item["image_path"]).resolve().as_posix())
        reasons: list[str] = []
        global_distance = local_distance = d_cal = ""
        if descriptor is None:
            reasons.append("feature_descriptor_missing")
        if layout_status != "ready":
            reasons.append(f"layout_{layout_status}")
        if layout.get("postprocess_valid") is not True:
            reasons.append("layout_postprocess_invalid")
        if descriptor is not None:
            global_vector = ((descriptor[0] - reference_cache["global_mean"]) @ reference_cache["global_components"].T) / reference_cache["global_scale"]
            local_vector = ((descriptor[1] - reference_cache["local_mean"]) @ reference_cache["local_components"].T) / reference_cache["local_scale"]
            global_distance = _knn(global_vector, reference_cache["reference_global"])
            local_distance = _knn(local_vector, reference_cache["reference_local"])
        g_model_struct = layout.get("g_model_struct", "")
        try:
            if global_distance != "" and local_distance != "" and g_model_struct != "":
                candidate_vector = np.asarray([float(global_distance), float(local_distance), float(g_model_struct)], dtype=float) / frozen_reference["support_scale"]
                d_cal = _knn(candidate_vector, frozen_reference["support_matrix"] / frozen_reference["support_scale"])
            else:
                reasons.append("risk_channel_missing")
        except (TypeError, ValueError, FloatingPointError):
            reasons.append("risk_channel_invalid")
        scored = score_frozen_c1_risk_candidate({
            "d_model_feat": global_distance, "d_model_feat_local_max": local_distance,
            "g_model_struct": g_model_struct, "d_cal_A": d_cal,
        }, frozen_reference)
        if scored["risk_status"] != "ready":
            reasons.append(scored["risk_status"])
        if feature_audit_status != "approved":
            reasons.append("candidate_feature_audit_not_approved")
        row_blockers = json.loads(item["candidate_blockers_json"])
        risk_rows.append({
            "schema_version": "paper_a_stage3_test_risk_candidate_v1",
            "task_id": item["task_id"], "base_task_id": item["base_task_id"], "image_id": item["image_id"],
            "source_split": item["source_split"], "building_id": item["building_id"],
            "building_registry_status": item["building_registry_status"],
            "d_model_feat": global_distance, "d_model_feat_local_max": local_distance,
            "g_model_struct": g_model_struct, "d_cal_A": d_cal,
            "risk_design_vector_A": scored.get("risk_design_vector_A", ""),
            "risk_design_score_A": scored.get("risk_design_score_A", ""),
            "risk_design_score_A_percentile": scored.get("risk_design_score_A_percentile", ""),
            "risk_design_q75": scored.get("risk_design_q75", frozen_reference["q75"]),
            "risk_design_stratum": scored.get("risk_design_stratum", ""),
            "risk_design_stratum_source": "frozen_c1_reference_q75",
            "risk_status": "ready" if not reasons else ";".join(sorted(set(reasons))),
            "risk_missing_reason": ";".join(sorted(set(reasons))), "layout_status": layout_status,
            "feature_status": "ready" if descriptor is not None else "missing",
            "feature_audit_status": feature_audit_status,
            "postprocess_valid": layout.get("postprocess_valid", False),
            "risk_route": "", "risk_route_status": "deferred_until_post_c2_profile",
            "d_cal_F": "", "family_scores": "",
            "P1_exposed": item["P1_exposed"], "C1_exposed": item["C1_exposed"],
            "C2B_exposed": item["C2B_exposed"], "C2A_RP_exposed": item["C2A_RP_exposed"],
            "T1_exposed": item["T1_exposed"], "v1_candidate_eligible": item["v1_candidate_eligible"],
            "candidate_only": "true", "candidate_blockers_json": json.dumps(sorted(set(row_blockers + reasons)), ensure_ascii=False),
        })
    risk_summary = {
        "schema_version": "paper_a_stage3_test_risk_candidate_summary_v1",
        "artifact_role": "STAGE3_TEST_RISK_CANDIDATE",
        "contract_role": "generated_subordinate", **_method_identity(),
        "candidate_only": True, "formal_ready": False, "outcome_blind": True,
        "source_split": "test", "risk_design_stratum_rule": "frozen_c1_reference_q75",
        "risk_contract_path": str(risk_contract_path), "risk_contract_sha256": sha256_file(risk_contract_path),
        "c1_reference_path": str(reference_csv), "c1_reference_sha256": sha256_file(reference_csv),
        "c1_reference_q75": frozen_reference["q75"], "c1_reference_support_count": len(frozen_reference["reference_scores"]),
        "feature_candidate_manifest_path": str(output_dir / feature_manifest_path.name),
        "feature_candidate_manifest_sha256": sha256_file(feature_manifest_path),
        "candidate_descriptor_cache_path": str(output_dir / candidate_cache_path.name),
        "candidate_descriptor_cache_sha256": sha256_file(candidate_cache_path),
        "feature_audit_threshold_manifest_path": str(threshold_path),
        "feature_audit_threshold_manifest_sha256": threshold_sha,
        "feature_audit_status": feature_audit_status,
        "test_task_count": len(risk_rows),
        "ordinary_count": sum(row["risk_design_stratum"] == "ordinary" for row in risk_rows),
        "stress_count": sum(row["risk_design_stratum"] == "stress" for row in risk_rows),
        "risk_ready_count": sum(row["risk_status"] == "ready" for row in risk_rows),
        "risk_missing_count": sum(row["risk_status"] != "ready" for row in risk_rows),
        "structural_not_ready_count": sum(
            row["layout_status"] != "ready" or row["postprocess_valid"] is not True for row in risk_rows
        ),
        "reference_unavailable_count": 0 if reference_cache else len(risk_rows),
        "source_method_binding": source_binding,
    }
    return risk_rows, {"summary": risk_summary, "feature_manifest": candidate_feature_manifest, "feature_manifest_path": feature_manifest_path, "candidate_cache_path": candidate_cache_path}


def prepare_stage3_test_candidate(args: argparse.Namespace) -> dict[str, Any]:
    output_dir = _stage3_resolve(args.output_dir)
    if output_dir.exists():
        raise ValueError(f"target artifact already exists:{output_dir}")
    output_dir.parent.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix=f".{output_dir.name}.", dir=str(output_dir.parent)))
    try:
        inventory = _stage3_make_inventory(args)
        audit_rows, source_meta = _stage3_audit_inventory(args, inventory)
        for row in inventory:
            blockers = _stage3_candidate_blockers(row)
            row["candidate_blockers_json"] = json.dumps(blockers, ensure_ascii=False)
            row["v1_candidate_eligible"] = "true" if not blockers else "false"
        inventory_path = staging / "stage3_test_inventory_candidate.csv"
        audit_path = staging / "stage3_test_overlap_audit.csv"
        _stage3_write_csv(inventory_path, inventory, _STAGE3_INVENTORY_FIELDS)
        _stage3_write_csv(audit_path, audit_rows, _STAGE3_OVERLAP_FIELDS)
        risk_rows, risk_meta = _stage3_materialize_risk(args, inventory, staging)
        risk_path = staging / "test_task_risk_candidate.csv"
        _stage3_write_csv(risk_path, risk_rows, _STAGE3_RISK_FIELDS)
        risk_summary = dict(risk_meta["summary"])
        risk_summary.update({
            "inventory_path": str((output_dir / inventory_path.name).resolve()),
            "inventory_sha256": sha256_file(inventory_path),
            "overlap_audit_path": str((output_dir / audit_path.name).resolve()),
            "overlap_audit_sha256": sha256_file(audit_path),
            "risk_candidate_path": str((output_dir / risk_path.name).resolve()),
            "risk_candidate_sha256": sha256_file(risk_path),
            "approved_building_registry_path": str(_stage3_resolve(args.building_registry)) if args.building_registry else "",
            "approved_building_registry_sha256": sha256_file(_stage3_resolve(args.building_registry)) if args.building_registry else "",
            "source_exposure_manifests": source_meta,
            "validation_overlap_count": sum(row["validation_overlap_status"] != "clear" for row in inventory),
            "unresolved_building_count": sum(row["building_registry_status"] != "approved" for row in inventory),
            "v1_candidate_eligible_count": sum(row["v1_candidate_eligible"] == "true" for row in inventory),
            "blocked_row_count": sum(row["v1_candidate_eligible"] != "true" for row in inventory),
            "formal_launch_allowed": False,
            "stage_usage_policy": {
                "C2B_C2A_RP": "validation_only",
                "T1": "validation_remainder_only",
                "V1": "test_candidate_only_until_post_C2_profile",
            },
        })
        summary_path = staging / "test_task_risk_candidate.summary.json"
        summary_path.write_text(json.dumps(risk_summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        if output_dir.exists():
            raise ValueError(f"target artifact already exists:{output_dir}")
        staging.replace(output_dir)
        return {**risk_summary, "phase": "prepare-stage3-test-candidate", "output_dir": str(output_dir)}
    finally:
        if staging.exists():
            shutil.rmtree(staging, ignore_errors=True)


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
            "Q_GT": readiness.get("Q_GT_FREEZE_STATUS"), "R_peer": readiness.get("R_PEER_FREEZE_STATUS"),
            "F_struct": readiness.get("F_STRUCT_FREEZE_STATUS"),
            "R_LOO_medoid": readiness.get("R_LOO_MEDOID_STATUS"), "R_LOO_strict": readiness.get("R_LOO_STRICT_STATUS"),
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
        authorized_reassignment_manifest=getattr(args, "authorized_reassignment_manifest", None),
        late_entry_assignment_manifest=getattr(args, "late_entry_assignment_manifest", None),
        calibration_enrollment_registry=getattr(args, "calibration_enrollment_registry", None),
        w034_active_time_validation_manifest=getattr(args, "w034_active_time_validation_manifest", None),
        w034_preassignment_timing_verification_attestation=getattr(args, "w034_preassignment_timing_verification_attestation", None),
        building_registry=getattr(args, "building_registry", None),
        independence_disposition=getattr(args, "independence_disposition", None),
        project_independence_disposition=getattr(args, "project_independence_disposition", None),
        duplicate_adjudication=getattr(args, "duplicate_adjudication", None),
        structural_disposition=getattr(args, "structural_disposition", None),
        scope_initial_review=getattr(args, "scope_initial_review", None),
        scope_adjudication=getattr(args, "scope_adjudication", None),
        reference_amendment=getattr(args, "reference_amendment", None),
        outside_assignment_disposition=getattr(args, "outside_assignment_disposition", None),
        completion_disposition=getattr(args, "completion_disposition", None),
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
    if not getattr(args, "authorized_reassignment_manifest", None) or not getattr(args, "building_registry", None) or not getattr(args, "calibration_enrollment_registry", None):
        raise ValueError("formal C1 requires authorized reassignment, authoritative building registry, and calibration enrollment registry")
    validate_active_log_freeze_manifest(args.c1_active_log_freeze_manifest, args.active_log)
    summary = materialize_c1(
        args.export_dir, args.active_log, args.manual_assignment, args.semi_assignment,
        args.worker_distribution, args.gt_export, args.p1_closeout_dir, args.output_root,
        input_status="formal", independence_disposition=args.independence_disposition,
        project_independence_disposition=args.project_independence_disposition,
        structural_disposition=args.structural_disposition,
        scope_initial_review=getattr(args, "scope_initial_review", None),
        duplicate_adjudication=args.duplicate_adjudication,
        scope_adjudication=args.scope_adjudication,
        reference_amendment=args.reference_amendment,
        outside_assignment_disposition=args.outside_assignment_disposition,
        completion_disposition=args.completion_disposition,
        c1_preannotation_feature_csv=getattr(args, "c1_preannotation_feature_csv", None),
        c1_active_log_freeze_manifest=args.c1_active_log_freeze_manifest,
        collection_closure_manifest=args.collection_closure_manifest,
        p1_integrity_dir=getattr(args, "p1_integrity_dir", None),
        authorized_reassignment_manifest=args.authorized_reassignment_manifest,
        late_entry_assignment_manifest=getattr(args, "late_entry_assignment_manifest", None),
        calibration_enrollment_registry=args.calibration_enrollment_registry,
        w034_active_time_validation_manifest=args.w034_active_time_validation_manifest,
        w034_preassignment_timing_verification_attestation=getattr(args, "w034_preassignment_timing_verification_attestation", None),
        building_registry=args.building_registry,
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
    from tools.thesis_main.analysis.paper_a_contracts import METHOD_CONTRACT, load_method_contract, validate_serialized_record
    method = load_method_contract()
    method_sha = sha256_file(METHOD_CONTRACT)
    worker_manifest_path = args.output_dir / "c1_three_track_worker_state_manifest.json"
    worker_profile_path = args.output_dir / "c1_three_track_worker_state_formal.csv"
    enrollment_registry_path = args.output_dir / "calibration_enrollment_registry.csv"
    enrollment_summary_path = args.output_dir / "calibration_enrollment_registry.summary.json"
    w034_path = args.output_dir / "w034_original_vs_authorized_sensitivity.json"
    dependency_blockers: list[str] = []
    profile_dependency_paths: list[tuple[str, Path]] = []

    def validate_dependency_payload(payload: dict[str, Any], base: Path, trail: str) -> None:
        for index, dependency in enumerate(payload.get("dependencies", [])):
            path = Path(str(dependency.get("path", "")))
            if not path.is_absolute():
                path = base / path
            if not path.is_file() or dependency.get("sha256") != sha256_file(path):
                dependency_blockers.append(f"{trail}:{index}:stale_or_missing")
                continue
            if path.suffix.lower() == ".json":
                child = json.loads(path.read_text(encoding="utf-8"))
                if isinstance(child, dict) and child.get("dependencies"):
                    validate_dependency_payload(child, path.parent, f"{trail}:{index}")

    if not worker_manifest_path.is_file() or not worker_profile_path.is_file():
        dependency_blockers.append("worker_profile_manifest_or_csv_missing")
        worker_manifest: dict[str, Any] = {}
        worker_rows: list[dict[str, str]] = []
    else:
        worker_manifest = json.loads(worker_manifest_path.read_text(encoding="utf-8"))
        worker_rows = [validate_serialized_record("worker_profile_v2", row) for row in _read(worker_profile_path)]
        if worker_manifest.get("worker_state_sha256") != sha256_file(worker_profile_path):
            dependency_blockers.append("worker_profile_sha_mismatch")
        if worker_manifest.get("method_contract_sha256") != method_sha:
            dependency_blockers.append("worker_profile_method_contract_sha_mismatch")
        dependency_roles = {item.get("role") for item in worker_manifest.get("dependencies", [])}
        if "ENROLLMENT_REGISTRY" not in dependency_roles:
            dependency_blockers.append("worker_profile_enrollment_dependency_missing")
        for role in ("REFERENCE_REGISTRY", "BUILDING_REGISTRY", "TASK_BUILDING_BINDING"):
            if role not in dependency_roles:
                dependency_blockers.append(f"worker_profile_{role.lower()}_dependency_missing")
        for dependency in worker_manifest.get("dependencies", []):
            if dependency.get("role") in {"REFERENCE_REGISTRY", "BUILDING_REGISTRY", "TASK_BUILDING_BINDING"}:
                path = Path(str(dependency.get("path", "")))
                profile_dependency_paths.append((str(dependency["role"]), path if path.is_absolute() else worker_manifest_path.parent / path))
        validate_dependency_payload(worker_manifest, worker_manifest_path.parent, "worker_profile")
    if not enrollment_registry_path.is_file() or not enrollment_summary_path.is_file():
        dependency_blockers.append("calibration_enrollment_registry_missing")
        enrollment_rows: list[dict[str, str]] = []
        enrollment_summary: dict[str, Any] = {}
    else:
        enrollment_rows = _read(enrollment_registry_path)
        enrollment_summary = json.loads(enrollment_summary_path.read_text(encoding="utf-8"))
        registry_workers = {row.get("worker_id", "") for row in enrollment_rows}
        profile_workers = {row.get("worker_id", "") for row in worker_rows}
        if registry_workers != profile_workers:
            dependency_blockers.append("enrollment_profile_worker_set_mismatch")
        if enrollment_summary.get("status") != "validated" or enrollment_summary.get("all_registered_workers_terminal") is not True:
            dependency_blockers.append("enrollment_registry_not_validated_or_nonterminal")
        if enrollment_summary.get("registry_sha256") != sha256_file(enrollment_registry_path):
            dependency_blockers.append("enrollment_registry_sha_mismatch")
        if enrollment_summary.get("rolling_activated") is False and int(enrollment_summary.get("N_late") or 0) != 0:
            dependency_blockers.append("rolling_disabled_with_late_workers")
    if not w034_path.is_file():
        dependency_blockers.append("w034_sensitivity_freeze_missing")
        w034: dict[str, Any] = {}
    else:
        w034 = json.loads(w034_path.read_text(encoding="utf-8"))
        if w034.get("schema_version") != "w034_authorized_extension_sensitivity_freeze_v1" or w034.get("status") != "frozen":
            dependency_blockers.append("w034_sensitivity_not_frozen")
        if w034.get("method_contract_sha256") != method_sha:
            dependency_blockers.append("w034_method_contract_sha_mismatch")
        validate_dependency_payload(w034, w034_path.parent, "w034_sensitivity")
    terminal_statuses = {"completed", "closed_partial_usable", "closed_partial_insufficient", "nonstarter", "administrative_exclusion"}
    nonterminal_workers = [row.get("worker_id", "") for row in worker_rows if row.get("completion_status", "") not in terminal_statuses]
    if nonterminal_workers:
        dependency_blockers.append("nonterminal_enrollment:" + ",".join(sorted(nonterminal_workers)))
    adjudication = json.loads(args.adjudication_manifest.read_text(encoding="utf-8"))
    bundle_sha = audit.get("full_dependency_bundle_sha256", "")
    approved = adjudication.get("approved") is True and adjudication.get("input_bundle_sha256") == bundle_sha
    canonical_ready = bool(audit.get("C1_CANONICAL_CLOSED")) and bool(final.get("C1_CANONICAL_CLOSED", True))
    blockers = []
    blockers.extend(dependency_blockers)
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
    c2b_baseline_ready = bool(measurement.get("C2B_BASELINE_INPUT_FROZEN")) and evidence_ready and any(str(row.get("c2_risk_model_eligible", "")).lower() in {"true", "1"} for row in worker_rows)
    c2b_blockers = [] if c2b_baseline_ready else ["q_gt_baseline_support_limited_or_not_frozen"]
    profile_version = str(worker_manifest.get("profile_version", ""))
    cohort_id = str(worker_manifest.get("cohort_id", ""))
    child_dependencies = [
        _materialize_c1_child_freeze(
            args.output_dir, role, source_role, source,
            formal_ready=evidence_ready, profile_version=profile_version,
            cohort_id=cohort_id, method_version=method["contract_version"], method_sha=method_sha,
        )
        for role, source_role, source in (
            ("C1_ROW_ELIGIBILITY_FROZEN", "CANONICAL_ELIGIBILITY", worker_profile_path.parent / "c1_row_analysis_eligibility.csv"),
            ("C1_PEER_EVIDENCE_FROZEN", "PEER", worker_profile_path.parent / "geometry_worker_task_peer_analysis.csv"),
            ("C1_STRUCTURAL_EB_FROZEN", "STRUCTURAL_EB", worker_profile_path.parent / "c1_structural_reliability_eb.csv"),
            ("W034_SENSITIVITY_FROZEN", "W034_SENSITIVITY", w034_path),
        )
    ]
    freeze_dependencies = [
        {"role": role, "path": str(path.resolve()), "sha256": sha256_file(path)}
        for role, path in (
            ("FORMAL_AUDIT", audit_path), ("CANONICAL_CLOSEOUT", final_path),
            ("MEASUREMENT_FREEZE", measurement_path), ("WORKER_PROFILE_MANIFEST", worker_manifest_path),
            ("WORKER_PROFILE", worker_profile_path), ("ENROLLMENT_REGISTRY", enrollment_registry_path),
            ("ENROLLMENT_REGISTRY_SUMMARY", enrollment_summary_path), *profile_dependency_paths,
            ("ADJUDICATION", args.adjudication_manifest), ("METHOD_CONTRACT", METHOD_CONTRACT),
        ) if path.is_file()
    ] + child_dependencies
    freeze = {
        "schema_version": "c1_evidence_freeze_manifest_v6", "artifact_role": "C1_EVIDENCE_FROZEN",
        "contract_role": "generated_subordinate", "formal_ready": evidence_ready,
        "method_contract": audit.get("method_contract", ""), "method_contract_version": method["contract_version"],
        "method_contract_sha256": method_sha, "profile_version": profile_version, "cohort_id": cohort_id,
        "git_commit_sha": audit.get("git_commit_sha", ""), "C1_COLLECTION_INCOMPLETE": not collection_closed,
        "C1_CANONICAL_CLOSED": canonical_ready, "C1_MEASUREMENT_FROZEN": evidence_ready,
        "C1_EVIDENCE_BUNDLE_FROZEN": bool(measurement.get("C1_EVIDENCE_BUNDLE_FROZEN")) and evidence_ready,
        "C1_EVIDENCE_FROZEN": evidence_ready, "C2B_BASELINE_INPUT_FROZEN": c2b_baseline_ready,
        "Q_GT_FREEZE_STATUS": measurement.get("Q_GT_FREEZE_STATUS", "pending"),
        "R_PEER_FREEZE_STATUS": measurement.get("R_PEER_FREEZE_STATUS", "pending"),
        "F_STRUCT_FREEZE_STATUS": measurement.get("F_STRUCT_FREEZE_STATUS", "pending"),
        "R_LOO_MEDOID_STATUS": measurement.get("R_LOO_MEDOID_STATUS", "pending"),
        "R_LOO_STRICT_STATUS": measurement.get("R_LOO_STRICT_STATUS", "pending"),
        "rolling_activated": enrollment_summary.get("rolling_activated"), "N_late": enrollment_summary.get("N_late"),
        "C2B_DESIGN_READY": c2b_baseline_ready, "C2B_RISK_DESIGN_FROZEN": False,
        "C2B_DESIGN_FROZEN": False, "C2B_ASSIGNMENT_MATERIALIZED": False, "C2B_LAUNCH_READY": False,
        "routing_profile_frozen": False, "formal_closeout_ready": evidence_ready,
        "full_dependency_bundle_sha256": bundle_sha, "adjudication_sha256": sha256_file(args.adjudication_manifest),
        "blockers": blockers, "c2b_baseline_blockers": c2b_blockers,
        "dependencies": freeze_dependencies,
    }
    freeze.update({
        "expected_schema": freeze["schema_version"], "required_status_field": "C1_EVIDENCE_FROZEN",
        "required_status_value": True, "frozen": evidence_ready,
    })
    freeze["state_machine"] = {name: bool(freeze[name]) for name in ("C1_COLLECTION_INCOMPLETE", "C1_CANONICAL_CLOSED", "C1_MEASUREMENT_FROZEN", "C2B_RISK_DESIGN_FROZEN", "C2B_DESIGN_FROZEN", "C2B_ASSIGNMENT_MATERIALIZED", "C2B_LAUNCH_READY")}
    (args.output_dir / "c1_evidence_freeze_manifest.json").write_text(json.dumps(freeze, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return {"day": 1, "phase": "measurement-freeze", "formal_closeout_ready": evidence_ready, "C1_CANONICAL_CLOSED": freeze["C1_CANONICAL_CLOSED"], "C1_MEASUREMENT_FROZEN": freeze["C1_MEASUREMENT_FROZEN"], "C2B_DESIGN_READY": freeze["C2B_DESIGN_READY"], "routing_profile_frozen": False, "blockers": blockers, "c2b_baseline_blockers": c2b_blockers}


def design_c2b(args: argparse.Namespace) -> dict[str, Any]:
    git_state = formal_git_state(_PROJECT_ROOT)
    if not git_state["clean"]:
        raise ValueError("formal C2-B design requires a committed clean worktree")
    closeout = json.loads(args.c1_closeout_summary.read_text(encoding="utf-8"))
    if closeout.get("schema_version") != "paper_a_c1_batch_analysis_snapshot_v1" or closeout.get("status") != "formal_design_eligible":
        raise ValueError("C2-B design requires a formal C1_A batch analysis snapshot")
    if closeout.get("method_contract_version") != load_method_contract()["contract_version"] or closeout.get("method_contract_sha256") != sha256_file(METHOD_CONTRACT):
        raise ValueError("C1_A batch snapshot method contract is stale")
    if closeout.get("C2B_DESIGN_INPUT_FROZEN_FROM_C1_A") is not True:
        raise ValueError("C1_A design input is not frozen")
    c1_inputs = _snapshot_dependencies(
        closeout, "WORKER_PROFILE", "COMPLETION", "Q_GT", "STRUCTURAL_EB",
        "MEASUREMENT_READINESS", "CANONICAL_ELIGIBILITY", "REFERENCE", "SCOPE_FINAL_DISPOSITION", "BUILDING",
    )
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
    preliminary_ready = bool(risk.get("C2_TASK_FEATURES_FROZEN")) and bool(closeout.get("C2B_DESIGN_INPUT_FROZEN_FROM_C1_A"))
    parameter_summary: dict[str, Any] = {"formal_design_input_ready": False}
    profile_summary: dict[str, Any] = {"n_eligible": 0}
    derived_thresholds: dict[str, Any] = {}
    pool_gate: dict[str, Any] = {"frozen": False, "approved_thresholds": False, "observed": {}, "failures": ["design_inputs_not_ready"]}
    design_input_blocker = ""
    if preliminary_ready:
        worker_profile_path = c1_inputs["WORKER_PROFILE"]
        parameter_summary = materialize_design_parameters(
            c1_inputs["Q_GT"], args.output_dir / "c1_task_risk_reference.csv",
            c1_inputs["STRUCTURAL_EB"], c1_inputs["COMPLETION"],
            args.output_dir, worker_state_csv=worker_profile_path,
        )
        profile_summary = materialize_c2b_design_worker_profile(
            c1_inputs["COMPLETION"], worker_profile_path,
            args.output_dir / "c1_c2_design_parameters.csv", c1_inputs["MEASUREMENT_READINESS"],
            args.output_dir, c1_batch_snapshot=args.c1_closeout_summary,
        )
        if parameter_summary["formal_design_input_ready"] and profile_summary["n_eligible"]:
            if not args.threshold_formula_contract.exists():
                design_input_blocker = "threshold_formula_contract_missing"
            elif not args.capacity_manifest.exists():
                design_input_blocker = "capacity_manifest_missing_before_threshold_review"
            else:
                try:
                    validate_formula_contract(json.loads(args.threshold_formula_contract.read_text(encoding="utf-8")))
                    _require_current_subordinate(args.threshold_formula_contract, "threshold_formula_contract")
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


def _write_c2b_imports(
    output_dir: Path,
    distribution: list[dict[str, Any]],
    *,
    batch_id: str,
    selected_design_id: str,
    selected_design_sha: str,
    layout_dir: Path,
    deployments: list[dict[str, Any]] | None = None,
) -> dict[str, dict[str, Any]]:
    def dump(path: Path, payload: object) -> None:
        with path.open("w", encoding="utf-8", newline="\n") as stream:
            stream.write(json.dumps(payload, ensure_ascii=False, indent=2) + "\n")

    selected = {row["task_id"]: row for row in distribution}
    layouts = {}
    for task_id, row in selected.items():
        layout_path = layout_dir / f"{row.get('base_task_id') or task_id}.json"
        if not layout_path.is_file():
            raise ValueError(f"C2-B assigned task lacks model layout JSON:{task_id}")
        payload = json.loads(layout_path.read_text(encoding="utf-8"))
        corners = payload.get("layout", {}).get("corners", [])
        if not corners:
            raise ValueError(f"C2-B assigned task has empty model layout:{task_id}")
        layouts[task_id] = [{key: corner[key] for key in ("x", "y_ceiling", "y_floor")} for corner in corners]

    def worker_image(row: dict[str, Any]) -> str:
        return str(row["image_path"]).replace("/valid_no_occ/img/", "/img_v/").removesuffix(".png") + ".jpg"

    deployment_specs = deployments or [dict(item, worker_ids=[], worker_registry_sha256="") for item in DEFAULT_C2B_DEPLOYMENTS]

    def tasks(deployment: dict[str, Any]) -> list[dict[str, Any]]:
        vis_base = str(deployment["server_url"])
        # A deployment imports the frozen task collection.  Worker language
        # identity controls private assignment lists and runtime joins; it
        # must not silently shrink the planned import task pool.
        selected_for_deployment = selected
        return [{"data": {
            "image": worker_image(row),
            "vis_3d": f"{vis_base}/tools/vis_3d.html?w=1024&h=512&data={quote(json.dumps(layouts[task_id], separators=(',', ':')))}",
            "title": Path(worker_image(row)).name,
            "dataset_group": "C2-B",
            "condition": "manual",
            "task_id": task_id,
            "planned_task_id": task_id,
            "base_task_id": row.get("base_task_id") or task_id,
            "image_id": row.get("image_id") or row.get("image_stem") or row.get("base_task_id") or task_id,
            "calibration_version": "C2-B_v18",
            "source_draft": f"approved_{selected_design_id}",
            "artifact_status": "formal_c2b_import_json",
            "launch_allowed": True,
            "c2b_batch_id": batch_id,
            "selected_design_sha": selected_design_sha,
            "deployment_id": deployment["deployment_id"],
            "language_group": deployment["language_group"],
            "server_instance_id": deployment["server_instance_id"],
            "project_id": deployment.get("project_id", ""),
        }} for task_id, row in sorted(selected_for_deployment.items())]

    release_dir = _PROJECT_ROOT / "import_json" / "c2b"
    release_dir.mkdir(parents=True, exist_ok=True)
    release_stem = f"c2b_{selected_design_id}_{batch_id.removeprefix('C2B_').lower()}_import"
    outputs: dict[str, dict[str, Any]] = {}
    for index, deployment in enumerate(deployment_specs):
        payload = tasks(deployment)
        if index == 0:
            local_path = output_dir / "label_studio_import_C2B.json"
            dump(local_path, payload)
        else:
            local_path = output_dir / f"label_studio_import_C2B_{deployment['deployment_id']}.json"
            dump(local_path, payload)
        language = str(deployment["language_group"]).lower()
        suffix = "zh" if language == "chinese" else "foreign_https" if language == "english" else str(deployment["deployment_id"])
        release_path = release_dir / f"{release_stem}_{suffix}.json"
        dump(release_path, payload)
        outputs[str(deployment["deployment_id"])] = {
            **deployment,
            "planned_import_path": str(release_path.resolve()),
            "local_import_path": str(local_path.resolve()),
            "planned_import_sha256": sha256_file(release_path),
            "local_import_sha256": sha256_file(local_path),
            "task_count": len(payload),
        }
    return outputs


def _write_c2b_import(
    output_dir: Path,
    distribution: list[dict[str, Any]],
    *,
    batch_id: str,
    selected_design_id: str,
    selected_design_sha: str,
    layout_dir: Path,
) -> Path:
    """Compatibility wrapper for the historical single-file test/helper API."""
    outputs = _write_c2b_imports(
        output_dir, distribution, batch_id=batch_id, selected_design_id=selected_design_id,
        selected_design_sha=selected_design_sha, layout_dir=layout_dir,
    )
    return Path(outputs["c2b_zh"]["local_import_path"])


def _materialize_c2b_deployments(
    args: argparse.Namespace,
    distribution: list[dict[str, Any]],
    assignment_path: Path,
    *,
    batch_id: str,
    selected_design_id: str,
    selected_design_sha: str,
) -> tuple[Path, dict[str, dict[str, Any]]]:
    source = getattr(args, "deployment_manifest", None)
    if not source:
        raise ValueError("formal C2-B build requires an explicit deployment manifest with project IDs")
    specs, source_sha = _deployment_specs(source, {normalize_worker_id(row.get("worker_id", "")) for row in distribution})
    outputs = _write_c2b_imports(
        args.output_dir, distribution, batch_id=batch_id, selected_design_id=selected_design_id,
        selected_design_sha=selected_design_sha, layout_dir=args.layout_dir, deployments=specs,
    )
    frozen_specs = [outputs[item["deployment_id"]] for item in specs]
    manifest_path = _write_worker_deployment_manifest(
        args.output_dir, source, source_sha, frozen_specs,
        assignment_path=assignment_path, selected_design_sha=selected_design_sha, batch_id=batch_id,
    )
    return manifest_path, outputs


def _selected_design_inputs(args: argparse.Namespace) -> tuple[dict[str, Any], dict[str, dict[str, str]]]:
    manifest_path = getattr(args, "selected_design_manifest", None)
    if not manifest_path:
        raise ValueError("selected design manifest is required for every C2-B batch")
    manifest = _require_current_subordinate(manifest_path, "selected_design_manifest")
    if manifest.get("schema_version") != "paper_a_selected_c2b_design_manifest_v1":
        raise ValueError("selected design manifest schema is invalid")
    if manifest.get("selected_design_id") not in {"D8", "D10", "D12"}:
        raise ValueError("selected design manifest has an invalid design ID")
    if manifest.get("design_manifest_sha256") != sha256_file(args.design_manifest):
        raise ValueError("selected design manifest is not bound to the candidate design manifest")
    if manifest.get("task_pool_sha256") != sha256_file(args.task_pool):
        raise ValueError("selected design manifest task pool SHA drift")
    anchors = [str(value) for value in manifest.get("selected_common_anchor_task_ids", [])]
    bridges = [str(value) for value in manifest.get("selected_bridge_task_ids", [])]
    if len(anchors) != int(manifest.get("common_anchor_count", -1)) or len(bridges) < int(manifest.get("bridge_per_worker", 0)):
        raise ValueError("selected design manifest task counts are inconsistent")
    if set(anchors) & set(bridges):
        raise ValueError("selected design manifest anchor and bridge pools overlap")
    tasks = {str(row.get("task_id", "")): row for row in _read(args.task_pool)}
    selected = anchors + bridges
    if any(task_id not in tasks for task_id in selected):
        raise ValueError("selected design manifest references a task outside the frozen task pool")
    bridge_pool_sha = hashlib.sha256(json.dumps(sorted(bridges), separators=(",", ":")).encode("utf-8")).hexdigest()
    if manifest.get("selected_bridge_pool_sha256") != bridge_pool_sha:
        raise ValueError("selected bridge pool SHA drift")
    return manifest, tasks


def _build_c2b_batch_b(args: argparse.Namespace) -> dict[str, Any]:
    if not all(getattr(args, name, None) for name in ("batch_a_launch_report", "batch_a_assignment", "batch_worker_profile", "p1_admission_evidence")):
        raise ValueError("C2B_BATCH_B requires Batch A report/assignment, C1-B worker profile, and P1 admission evidence")
    batch_a = _require_current_subordinate(args.batch_a_launch_report, "batch_a_launch_report")
    if batch_a.get("assignment_batch_id") != "C2B_BATCH_A" or not batch_a.get("C2B_ASSIGNMENT_BATCH_A_MATERIALIZED"):
        raise ValueError("Batch B requires a frozen Batch A launch report")
    roster = _require_current_subordinate(args.c2b_roster_manifest, "batch_b_roster")
    if roster.get("worker_profile_sha256") != sha256_file(args.batch_worker_profile):
        raise ValueError("Batch B roster is not bound to the submitted C1-B worker profile")
    profiles = _normalize_worker_rows(_read(args.batch_worker_profile))
    p1 = {normalize_worker_id(row.get("worker_id", "")): row for row in _read(args.p1_admission_evidence)}
    workers = []
    for row in profiles:
        worker = row.get("worker_id", "")
        if not worker:
            continue
        if row.get("schema_version") != "worker_profile_v2" or row.get("enrollment_batch") != "late_entry" or row.get("completion_status") != "completed" or not _truth(row.get("c2_risk_model_eligible")):
            continue
        if str(p1.get(worker, {}).get("admission_status", "")).lower() not in {"pass", "admitted", "approved"}:
            raise ValueError(f"Batch B worker lacks passed P1 evidence:{worker}")
        workers.append(worker)
    if not workers:
        raise ValueError("Batch B has no P1-passed, completed C1-B formal roster workers")
    base = _normalize_worker_rows(_read(args.batch_a_assignment))
    if not base or any(row.get("assignment_batch_id") not in {"", "C2B_BATCH_A"} for row in base):
        raise ValueError("Batch A assignment is not a stable C2B_BATCH_A artifact")
    selected, task_pool = _selected_design_inputs(args)
    design_sha = str(selected["selected_design_sha"])
    if batch_a.get("selected_design_sha") != design_sha or batch_a.get("selected_design_manifest_sha256") != sha256_file(args.selected_design_manifest):
        raise ValueError("Batch A and selected design manifest do not match")
    base_by_task = {str(row.get("task_id", "")): row for row in base}
    anchor_ids = [str(value) for value in selected["selected_common_anchor_task_ids"]]
    bridge_ids = [str(value) for value in selected["selected_bridge_task_ids"]]
    bridge_per_worker = int(selected["bridge_per_worker"])
    rows: list[dict[str, Any]] = []
    for worker in sorted(set(workers)):
        for task_id in anchor_ids:
            row = {**task_pool[task_id], **base_by_task.get(task_id, {})}
            rows.append({**row, "task_id": task_id, "c2_component": "common_anchor", "worker_id": worker, "assignment_batch_id": "C2B_BATCH_B"})
        generator = selected.get("bridge_generator")
        if not isinstance(generator, dict) or not all(str(generator.get(field, "")).strip() for field in ("rule_version", "frozen_seed", "ordinary_stress_quota", "stratum_balance_rule")):
            raise ValueError("Batch B requires the frozen bridge generator contract in selected design")
        start = int(hashlib.sha256(f"{generator['frozen_seed']}:{worker}".encode("utf-8")).hexdigest(), 16) % len(bridge_ids)
        for offset in range(bridge_per_worker):
            task_id = bridge_ids[(start + offset) % len(bridge_ids)]
            row = {**task_pool[task_id], **base_by_task.get(task_id, {})}
            rows.append({**row, "task_id": task_id, "c2_component": "diverse_bridge", "worker_id": worker, "assignment_batch_id": "C2B_BATCH_B"})
    if len({(row["worker_id"], row["task_id"]) for row in rows}) != len(rows):
        raise ValueError("Batch B bridge replay generated duplicate worker-task rows")
    capacities = {normalize_worker_id(row.get("worker_id", "")): int(float(row.get("c2b_capacity", "0"))) for row in _read(args.capacity_manifest)}
    if any(sum(row["worker_id"] == worker for row in rows) > capacities.get(worker, 0) for worker in workers):
        raise ValueError("Batch B assignment exceeds frozen capacity")
    args.output_dir.mkdir(parents=True, exist_ok=True)
    assignment_path = args.output_dir / "assignment_manifest_C2B.csv"; _write(assignment_path, rows)
    _write(args.output_dir / "worker_distribution_C2B.csv", rows)
    worker_dir = args.output_dir / "worker_facing_distribution_C2B"; worker_dir.mkdir(parents=True, exist_ok=True)
    for worker in sorted(set(workers)): _write(worker_dir / f"worker_{worker}_C2B.csv", [row for row in rows if row["worker_id"] == worker])
    deployment_manifest_path, deployment_outputs = _materialize_c2b_deployments(
        args, rows, assignment_path, batch_id="C2B_BATCH_B",
        selected_design_id=str(selected["selected_design_id"]), selected_design_sha=design_sha,
    )
    report = {
        "schema_version": "paper_a_c2b_launch_ready_report_v4", "contract_role": "generated_subordinate", **_method_identity(),
        "assignment_batch_id": "C2B_BATCH_B", "selected_design_id": selected["selected_design_id"], "selected_design_sha": design_sha, "selected_design_manifest_sha256": sha256_file(args.selected_design_manifest), "task_pool_sha256": selected["task_pool_sha256"], "common_anchor_count": selected["common_anchor_count"], "bridge_per_worker": selected["bridge_per_worker"], "selected_bridge_pool_sha256": selected["selected_bridge_pool_sha256"], "assignment_sha256": sha256_file(assignment_path),
        "deployment_manifest_path": str(deployment_manifest_path), "deployment_manifest_sha256": sha256_file(deployment_manifest_path),
        "deployments": list(deployment_outputs.values()),
        "C2B_ASSIGNMENT_BATCH_A_MATERIALIZED": True, "C2B_ASSIGNMENT_BATCH_B_MATERIALIZED": True, "C2B_LAUNCH_READY": True,
        "automatic_label_studio_import": False, "n_assignments": len(rows), "n_workers": len(workers),
        "dependencies": [{"role": role, "path": str(path.resolve()), "sha256": sha256_file(path)} for role, path in (("BATCH_A_LAUNCH_REPORT", args.batch_a_launch_report), ("BATCH_A_ASSIGNMENT", args.batch_a_assignment), ("BATCH_B_ROSTER", args.c2b_roster_manifest), ("BATCH_B_PROFILE", args.batch_worker_profile), ("P1_ADMISSION", args.p1_admission_evidence), ("SELECTED_DESIGN_MANIFEST", args.selected_design_manifest), ("DESIGN_MANIFEST", args.design_manifest), ("TASK_POOL", args.task_pool), ("DEPLOYMENT_MANIFEST", deployment_manifest_path), ("METHOD_CONTRACT", METHOD_CONTRACT))],
    }
    (args.output_dir / "c2b_launch_ready_report.json").write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return {"day": 2, "phase": "build", **report}


def build_c2b(args: argparse.Namespace) -> dict[str, Any]:
    if not formal_git_state(_PROJECT_ROOT)["clean"]:
        raise ValueError("formal C2-B build requires a committed clean worktree")
    if getattr(args, "assignment_batch", "C2B_BATCH_A") == "C2B_BATCH_B":
        return _build_c2b_batch_b(args)
    closeout = json.loads(args.c1_closeout_summary.read_text(encoding="utf-8"))
    risk = json.loads(args.risk_summary.read_text(encoding="utf-8"))
    if closeout.get("schema_version") != "paper_a_c1_batch_analysis_snapshot_v1" or closeout.get("status") != "formal_design_eligible" or not closeout.get("C2B_DESIGN_INPUT_FROZEN_FROM_C1_A"):
        raise ValueError("C1_A Batch A design input is not formally frozen")
    if closeout.get("method_contract_version") != load_method_contract()["contract_version"] or closeout.get("method_contract_sha256") != sha256_file(METHOD_CONTRACT):
        raise ValueError("Batch A snapshot method contract is stale")
    _require_current_subordinate(args.c2b_roster_manifest, "c2b_roster")
    roster = json.loads(args.c2b_roster_manifest.read_text(encoding="utf-8"))
    if roster.get("c1_batch_snapshot_sha256") != sha256_file(args.c1_closeout_summary):
        raise ValueError("formal C2-B roster is not bound to the C1_A snapshot")
    validate_generated_subordinate(risk, role="c2_task_risk")
    if not risk.get("formal_ready") or not risk.get("state_machine", {}).get("C2B_RISK_DESIGN_FROZEN"):
        raise ValueError("C2 task risk is not formally frozen")
    if risk.get("derived_threshold_manifest_sha256") != sha256_file(args.threshold_manifest):
        raise ValueError("C2-B derived threshold manifest is stale or unbound")
    threshold_payload = json.loads(args.threshold_manifest.read_text(encoding="utf-8"))
    validate_generated_subordinate(threshold_payload, role="derived_threshold_manifest")
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
    _require_current_subordinate(args.design_manifest, "candidate_design")
    approval = _require_current_subordinate(args.selected_design_approval, "selected_design_approval")
    selected_manifest, _ = _selected_design_inputs(args)
    if approval.get("selected_design_id") not in (None, selected_manifest["selected_design_id"]):
        raise ValueError("selected design approval ID does not match selected design manifest")
    if approval.get("selected_design_sha") not in (None, selected_manifest["selected_design_sha"]):
        raise ValueError("selected design approval SHA does not match selected design manifest")
    design = c2b.materialize_approved_assignment(
        args.candidate_dir, args.design_manifest, args.threshold_manifest,
        args.selected_design_approval, args.selected_task_reference_manifest,
        args.task_eligibility_evidence, args.c1_closeout_summary,
        args.risk_summary, args.output_dir,
    )
    assignment_path = args.output_dir / "assignment_manifest_C2B.csv"
    assignments, tasks = _read(assignment_path), {row["task_id"]: row for row in _read(args.task_pool)}
    assignments = [{**row, "assignment_batch_id": "C2B_BATCH_A"} for row in assignments]
    _write(assignment_path, assignments)
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
    def resolvable_image(value: str) -> bool:
        value = str(value).strip()
        return value.startswith(("http://", "https://", "/data/")) or Path(value).is_file() or (_PROJECT_ROOT / value).is_file()
    if any(not resolvable_image(row["image_path"]) for row in distribution):
        raise ValueError("C2-B assigned task image path is not resolvable")
    _write(args.output_dir / "worker_distribution_C2B.csv", distribution)
    worker_dir = args.output_dir / "worker_facing_distribution_C2B"; worker_dir.mkdir(parents=True, exist_ok=True)
    for worker in sorted({row["worker_id"] for row in distribution}):
        _write(worker_dir / f"worker_{worker}_C2B.csv", [row for row in distribution if row["worker_id"] == worker])
    selected_design_sha = str(selected_manifest["selected_design_sha"])
    deployment_manifest_path, deployment_outputs = _materialize_c2b_deployments(
        args, distribution, assignment_path, batch_id="C2B_BATCH_A",
        selected_design_id=str(selected_manifest["selected_design_id"]), selected_design_sha=selected_design_sha,
    )
    support = Counter(row["task_id"] for row in assignments)
    assignment_identities = {(row["worker_id"], row["task_id"]) for row in assignments}
    distribution_identities = {(row["worker_id"], row["task_id"]) for row in distribution}
    explicit_gt_count = sum(_truth(tasks.get(row["task_id"], {}).get("is_gt")) or str(tasks.get(row["task_id"], {}).get("task_role", "")).upper() == "GT" or str(tasks.get(row["task_id"], {}).get("dataset_group", "")).upper() == "GT" for row in distribution)
    worker_files = sorted(worker_dir.glob("worker_*_C2B.csv"))
    method_sha = sha256_file(METHOD_CONTRACT)
    deployment_assignment_counts = {
        item["deployment_id"]: sum(
            normalize_worker_id(row.get("worker_id", "")) in {normalize_worker_id(worker) for worker in item.get("worker_ids", [])}
            for row in assignments
        )
        for item in deployment_outputs.values()
    }
    audit = {
        "schema_version": "paper_a_c2b_launch_ready_report_v4", "contract_role": "generated_subordinate", "method_contract": risk["method_contract"], "method_contract_version": load_method_contract()["contract_version"], "method_contract_sha256": method_sha, "git_commit_sha": risk["git_commit_sha"], "assignment_batch_id": "C2B_BATCH_A", "selected_design_id": selected_manifest["selected_design_id"], "selected_design_sha": selected_design_sha, "selected_design_manifest_sha256": sha256_file(args.selected_design_manifest), "task_pool_sha256": selected_manifest["task_pool_sha256"], "common_anchor_count": selected_manifest["common_anchor_count"], "bridge_per_worker": selected_manifest["bridge_per_worker"], "selected_bridge_pool_sha256": selected_manifest["selected_bridge_pool_sha256"],
        "deployment_manifest_path": str(deployment_manifest_path), "deployment_manifest_sha256": sha256_file(deployment_manifest_path), "deployments": list(deployment_outputs.values()),
        "n_assignments": len(assignments), "n_workers": len({row["worker_id"] for row in assignments}),
        "n_tasks": len(support), "min_task_support": min(support.values(), default=0),
        "duplicate_worker_task_count": len(assignments) - len({(row["worker_id"], row["task_id"]) for row in assignments}),
        "deployment_assignment_counts": deployment_assignment_counts,
        "deployment_task_counts": {
            item["deployment_id"]: item.get("task_count", 0)
            for item in deployment_outputs.values()
        },
        "import_smoke_passed": bool(deployment_outputs) and all(
            item.get("task_count", 0) == len(support)
            for item in deployment_outputs.values()
        ),
        "assignment_distribution_consistent": assignment_identities == distribution_identities,
        "gt_isolated_from_worker_import": explicit_gt_count == 0,
        "image_paths_resolvable": all(resolvable_image(row["image_path"]) for row in distribution),
        "capacity_manifest_sha256": sha256_file(args.capacity_manifest),
        "automatic_label_studio_import": False,
        "dependencies": [{"role": role, "path": str(path.resolve()), "sha256": sha256_file(path)} for role, path in (("C1_A_SNAPSHOT", args.c1_closeout_summary), ("C2B_ROSTER", args.c2b_roster_manifest), ("C2_RISK", args.risk_summary), ("THRESHOLDS", args.threshold_manifest), ("CAPACITY", args.capacity_manifest), ("SELECTED_DESIGN_APPROVAL", args.selected_design_approval), ("SELECTED_DESIGN_MANIFEST", args.selected_design_manifest), ("DESIGN_MANIFEST", args.design_manifest), ("TASK_POOL", args.task_pool), ("DEPLOYMENT_MANIFEST", deployment_manifest_path), ("METHOD_CONTRACT", METHOD_CONTRACT))],
    }
    audit["launch_ready"] = bool(design.get("launch_ready")) and audit["duplicate_worker_task_count"] == 0 and audit["import_smoke_passed"] and audit["assignment_distribution_consistent"] and audit["gt_isolated_from_worker_import"] and audit["image_paths_resolvable"]
    audit["C2B_LAUNCH_READY"] = audit["launch_ready"]
    audit["C2B_ASSIGNMENT_BATCH_A_MATERIALIZED"] = bool(assignments)
    audit["C2B_ASSIGNMENT_BATCH_B_MATERIALIZED"] = False
    audit["state_machine"] = {**design.get("state_machine", {}), "C2B_ASSIGNMENT_MATERIALIZED": bool(assignments), "C2B_ASSIGNMENT_BATCH_A_MATERIALIZED": bool(assignments), "C2B_ASSIGNMENT_BATCH_B_MATERIALIZED": False, "C2B_LAUNCH_READY": audit["launch_ready"]}
    (args.output_dir / "c2b_launch_ready_report.json").write_text(json.dumps(audit, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return {"day": 2, "phase": "build", "state_machine": design.get("state_machine", {}), **audit}


def _payload_tasks(path: Path) -> list[dict[str, Any]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    rows = payload if isinstance(payload, list) else payload.get("tasks", payload.get("data", []))
    if not isinstance(rows, list):
        raise ValueError("C2-B runtime/planned JSON must contain a task list")
    return [row for row in rows if isinstance(row, dict)]


def _bind_c2b_runtime_mapping_multi(args: argparse.Namespace, report: dict[str, Any]) -> dict[str, Any]:
    manifest_path = getattr(args, "deployment_manifest", None)
    if not manifest_path or not manifest_path.is_file():
        raise ValueError("formal C2-B runtime binding requires the frozen deployment manifest")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("schema_version") != "c2b_worker_deployment_manifest_v1" or sha256_file(manifest_path) != report.get("deployment_manifest_sha256"):
        raise ValueError("C2-B deployment manifest is stale or not bound to the launch report")
    method_identity = _method_identity()
    if any(report.get(field) != value for field, value in method_identity.items()):
        raise ValueError("C2-B launch report method contract is stale")
    if any(manifest.get(field) != value for field, value in method_identity.items()):
        raise ValueError("C2-B deployment manifest method contract is stale")
    if (report.get("assignment_sha256") != sha256_file(args.assignment_manifest)
            or manifest.get("assignment_batch_id") != report.get("assignment_batch_id")
            or manifest.get("assignment_sha256") != sha256_file(args.assignment_manifest)
            or manifest.get("selected_design_sha") != report.get("selected_design_sha")):
        raise ValueError("C2-B deployment manifest batch/design/assignment identity is stale")
    report_deployment_rows = report.get("deployments", [])
    manifest_deployment_rows = manifest.get("deployments", [])
    if not isinstance(report_deployment_rows, list) or not isinstance(manifest_deployment_rows, list):
        raise ValueError("C2-B deployment evidence must contain deployment lists")
    report_deployment_ids = [str(item.get("deployment_id", "")).strip() for item in report_deployment_rows if isinstance(item, dict)]
    manifest_deployment_ids = [str(item.get("deployment_id", "")).strip() for item in manifest_deployment_rows if isinstance(item, dict)]
    if (len(report_deployment_ids) != len(report_deployment_rows)
            or len(manifest_deployment_ids) != len(manifest_deployment_rows)
            or not all(report_deployment_ids) or not all(manifest_deployment_ids)
            or len(set(report_deployment_ids)) != len(report_deployment_ids)
            or len(set(manifest_deployment_ids)) != len(manifest_deployment_ids)):
        raise ValueError("C2-B deployment evidence has missing or duplicate deployment IDs")
    deployments = {str(item["deployment_id"]): item for item in report_deployment_rows}
    manifest_deployments = {str(item["deployment_id"]): item for item in manifest_deployment_rows}
    if not deployments or set(deployments) != set(manifest_deployments):
        raise ValueError("C2-B deployment set is incomplete or inconsistent")
    for deployment_id in deployments:
        report_item = deployments[deployment_id]
        manifest_item = manifest_deployments[deployment_id]
        if any(str(report_item.get(field, "")) != str(manifest_item.get(field, "")) for field in ("language_group", "server_instance_id", "project_id", "server_url", "planned_import_path", "planned_import_sha256", "worker_registry_sha256")):
            raise ValueError(f"C2-B deployment identity disagrees with the frozen manifest:{deployment_id}")
    assignment_rows = _read(args.assignment_manifest)
    distribution_rows = _read(args.worker_distribution)
    assignment_ids = {(normalize_worker_id(row.get("worker_id", "")), row.get("task_id", "")) for row in assignment_rows}
    distribution_ids = {(normalize_worker_id(row.get("worker_id", "")), row.get("task_id", "")) for row in distribution_rows}
    if assignment_ids != distribution_ids or len(assignment_ids) != len(assignment_rows):
        raise ValueError("assignment manifest and worker distribution are not a complete unique match")
    if manifest.get("assignment_sha256") != sha256_file(args.assignment_manifest):
        raise ValueError("C2-B deployment manifest assignment SHA is stale")
    worker_deployment: dict[str, str] = {}
    for deployment_id, item in manifest_deployments.items():
        for worker in item.get("worker_ids", []):
            normalized_worker = normalize_worker_id(worker)
            if not normalized_worker or normalized_worker in worker_deployment:
                raise ValueError("C2-B deployment manifest maps a worker to multiple deployments")
            worker_deployment[normalized_worker] = deployment_id
    if set(worker_deployment) != {normalize_worker_id(row.get("worker_id", "")) for row in distribution_rows}:
        raise ValueError("C2-B deployment manifest does not cover the worker distribution")
    planned_paths = getattr(args, "planned_import", None) or []
    runtime_paths = getattr(args, "runtime_export", None) or []
    if isinstance(planned_paths, Path):
        planned_paths = [planned_paths]
    if isinstance(runtime_paths, Path):
        runtime_paths = [runtime_paths]
    manifest_planned_paths = {
        Path(str(item.get("planned_import_path", ""))).resolve()
        for item in manifest_deployments.values()
    }
    if (len(planned_paths) != len(deployments)
            or {path.resolve() for path in planned_paths} != manifest_planned_paths
            or len(runtime_paths) != len(deployments)
            or len({path.resolve() for path in runtime_paths}) != len(runtime_paths)):
        raise ValueError("C2-B runtime binding requires exactly one planned import and runtime export per deployment")
    planned_by_deployment: dict[str, Path] = {}
    runtime_by_deployment: dict[str, Path] = {}
    for item in deployments.values():
        deployment_id = str(item["deployment_id"])
        planned = next((path for path in planned_paths if path.resolve() == Path(str(item.get("planned_import_path", ""))).resolve()), None)
        if planned is None:
            planned = Path(str(item.get("planned_import_path", "")))
        if not planned.is_file() or sha256_file(planned) != item.get("planned_import_sha256"):
            raise ValueError(f"C2-B planned import is missing or stale:{deployment_id}")
        planned_by_deployment[deployment_id] = planned
    for path in runtime_paths:
        if not path.is_file():
            raise ValueError(f"C2-B runtime export is missing:{path}")
        payload = json.loads(path.read_text(encoding="utf-8"))
        rows = payload if isinstance(payload, list) else payload.get("tasks", payload.get("data", []))
        if not isinstance(rows, list):
            raise ValueError(f"C2-B runtime export must contain a task list:{path}")
        declared = set()
        if isinstance(payload, dict) and str(payload.get("deployment_id", "")).strip():
            declared.add(str(payload["deployment_id"]).strip())
        for row in rows:
            if not isinstance(row, dict):
                continue
            data = row.get("data", {}) if isinstance(row.get("data", {}), dict) else {}
            deployment_id = str(row.get("deployment_id") or data.get("deployment_id") or "").strip()
            if deployment_id:
                declared.add(deployment_id)
        if len(declared) != 1 or next(iter(declared)) not in deployments:
            raise ValueError(f"C2-B runtime export must carry exactly one known deployment identity:{path.name}")
        deployment_id = next(iter(declared))
        if deployment_id in runtime_by_deployment:
            raise ValueError(f"C2-B runtime binding has duplicate runtime export for deployment:{deployment_id}")
        runtime_by_deployment[deployment_id] = path
    bindings_by_deployment: dict[tuple[str, str], dict[str, Any]] = {}
    # Runtime IDs are only safe after project identity is included.  A reuse
    # of the same project/runtime pair on another server is still ambiguous;
    # deployment_id namespaces the canonical join, but does not legitimize a
    # cross-server collision in the formal export.
    runtime_identity_seen: set[tuple[str, str]] = set()
    for deployment_id, item in deployments.items():
        planned_rows = _payload_tasks(planned_by_deployment[deployment_id])
        expected = {}
        for row in planned_rows:
            data = row.get("data", {}) if isinstance(row.get("data", {}), dict) else {}
            planned_id = str(data.get("planned_task_id", ""))
            if not planned_id or planned_id in expected or data.get("deployment_id") != deployment_id:
                raise ValueError(f"C2-B planned import has duplicate or wrong deployment identity:{deployment_id}")
            if data.get("language_group") != item.get("language_group") or data.get("server_instance_id") != item.get("server_instance_id"):
                raise ValueError(f"C2-B planned import has wrong server/language identity:{deployment_id}")
            if data.get("project_id") != item.get("project_id"):
                raise ValueError(f"C2-B planned import has wrong project identity:{deployment_id}")
            if (data.get("selected_design_sha") != report.get("selected_design_sha")
                    or data.get("c2b_batch_id") != report.get("assignment_batch_id")):
                raise ValueError(f"C2-B planned import is outside frozen batch/design:{deployment_id}")
            if (str(data.get("dataset_group", "")).upper() == "GT"
                    or str(data.get("task_role", "")).upper() == "GT"):
                raise ValueError("GT task leaked into planned C2-B import")
            expected[planned_id] = row
        # Each deployment receives the complete frozen task collection.  The
        # worker-to-deployment map is private-assignment identity, not an
        # import-pool filter.
        expected_tasks = {str(row.get("task_id", "")).strip() for row in distribution_rows if str(row.get("task_id", "")).strip()}
        if not expected_tasks:
            raise ValueError("C2-B worker distribution has no planned tasks")
        if set(expected) != expected_tasks:
            raise ValueError(f"C2-B planned import does not cover deployment assignment:{deployment_id}")
        runtime_rows = _payload_tasks(runtime_by_deployment[deployment_id])
        bound: dict[str, str] = {}
        runtime_ids_in_deployment: set[str] = set()
        for row in runtime_rows:
            data = row.get("data", {}) if isinstance(row.get("data", {}), dict) else {}
            planned_id = str(data.get("planned_task_id", ""))
            runtime_id = str(row.get("id") or row.get("task_id") or "")
            project_id = str(row.get("project") or row.get("project_id") or data.get("project_id") or "")
            if not planned_id or not runtime_id or planned_id in bound or runtime_id in runtime_ids_in_deployment or (project_id, runtime_id) in runtime_identity_seen:
                raise ValueError(f"C2-B runtime export has duplicate identity:{deployment_id}")
            if (data.get("deployment_id") != deployment_id
                    or data.get("language_group") != item.get("language_group")
                    or data.get("server_instance_id") != item.get("server_instance_id")
                    or not project_id):
                raise ValueError(f"C2-B runtime export has wrong deployment identity:{deployment_id}")
            if planned_id not in expected or data.get("selected_design_sha") != report.get("selected_design_sha") or data.get("c2b_batch_id") != report.get("assignment_batch_id"):
                raise ValueError(f"C2-B runtime export is outside frozen batch/design:{deployment_id}")
            if project_id and project_id != str(item.get("project_id")):
                raise ValueError(f"C2-B runtime export has wrong project identity:{deployment_id}")
            if str(data.get("dataset_group", "")).upper() == "GT" or str(data.get("task_role", "")).upper() == "GT":
                raise ValueError("GT task leaked into runtime C2-B import")
            bound[planned_id] = runtime_id
            runtime_ids_in_deployment.add(runtime_id)
            runtime_identity_seen.add((project_id, runtime_id))
        if set(bound) != set(expected):
            raise ValueError(f"C2-B runtime export is missing or adds planned tasks:{deployment_id}")
        for row in distribution_rows:
            worker = normalize_worker_id(row.get("worker_id", ""))
            if worker_deployment[worker] != deployment_id:
                continue
            planned_id = str(row.get("task_id", ""))
            bindings_by_deployment[(worker, planned_id)] = {
                "deployment_id": deployment_id,
                "language_group": item.get("language_group", ""),
                "server_instance_id": item.get("server_instance_id", ""),
                "project_id": item.get("project_id", ""),
                "worker_id": worker,
                "planned_task_id": planned_id,
                "runtime_task_id": bound[planned_id],
                "assignment_batch_id": report["assignment_batch_id"],
                "selected_design_sha": report["selected_design_sha"],
            }
    if {path.resolve() for path in runtime_by_deployment.values()} != {path.resolve() for path in runtime_paths}:
        raise ValueError("C2-B runtime binding does not consume exactly the supplied deployment exports")
    if len({(row["deployment_id"], row["project_id"], row["runtime_task_id"], row["worker_id"]) for row in bindings_by_deployment.values()}) != len(bindings_by_deployment):
        raise ValueError("C2-B runtime mapping is not one-to-one within deployment")
    runtime_task_counts_by_deployment = {
        deployment_id: len(_payload_tasks(runtime_path))
        for deployment_id, runtime_path in runtime_by_deployment.items()
    }
    migration_envelope_path = Path(str(report.get("migration_envelope_path", ""))) if report.get("migration_envelope_path") else None
    migration_envelope: dict[str, Any] | None = None
    if migration_envelope_path is not None:
        if not migration_envelope_path.is_file():
            raise ValueError("C2-B migration envelope is missing")
        migration_envelope = _read_json_object(migration_envelope_path)
        if migration_envelope.get("schema_version") != "paper_a_c2b_v17_to_v18_repackage_envelope_v1":
            raise ValueError("C2-B migration envelope schema is invalid")
        if (migration_envelope.get("target_method_contract_version") != report.get("method_contract_version")
                or migration_envelope.get("target_method_contract_sha256") != report.get("method_contract_sha256")
                or migration_envelope.get("selected_design_id") != report.get("selected_design_id")
                or migration_envelope.get("selected_design_sha") != report.get("selected_design_sha")
                or migration_envelope.get("assignment_batch_id") != report.get("assignment_batch_id")
                or migration_envelope.get("target_assignment_sha256") != report.get("assignment_sha256")):
            raise ValueError("C2-B migration envelope identity disagrees with the launch report")
        envelope_artifacts = {
            str(item.get("path", "")).strip(): item
            for item in migration_envelope.get("target_artifacts", [])
            if isinstance(item, dict) and str(item.get("path", "")).strip()
        }
        for path, expected_sha in ((args.launch_report, sha256_file(args.launch_report)), (manifest_path, sha256_file(manifest_path))):
            item = envelope_artifacts.get(str(path.resolve()))
            if not isinstance(item, dict) or item.get("sha256") != expected_sha:
                raise ValueError("C2-B migration envelope does not bind the static launch artifacts")
    binding_outputs = [
        args.output_dir / "c2b_runtime_task_mapping.csv",
        args.output_dir / "c2b_worker_task_binding_audit.json",
        args.output_dir / "c2b_private_assignment_list_audit.json",
    ]
    runtime_evidence_path = args.output_dir / "c2b_v17_to_v18_runtime_evidence_v1.json"
    if migration_envelope is not None and any(path.exists() for path in [*binding_outputs, runtime_evidence_path]):
        raise ValueError("C2-B runtime evidence target already exists")
    args.output_dir.mkdir(parents=True, exist_ok=True)
    mapping = args.output_dir / "c2b_runtime_task_mapping.csv"
    _write(mapping, list(bindings_by_deployment.values()))
    dependencies = [
        ("LAUNCH_REPORT", args.launch_report), ("ASSIGNMENT_MANIFEST", args.assignment_manifest),
        ("WORKER_DISTRIBUTION", args.worker_distribution), ("DEPLOYMENT_MANIFEST", manifest_path),
        ("METHOD_CONTRACT", METHOD_CONTRACT),
        ("RUNTIME_MAPPING", mapping),
        *[(f"PLANNED_IMPORT_{key}", value) for key, value in planned_by_deployment.items()],
        *[(f"RUNTIME_EXPORT_{key}", value) for key, value in runtime_by_deployment.items()],
    ]
    audit = {
        "schema_version": "paper_a_c2b_runtime_mapping_audit_v2",
        "contract_role": "generated_subordinate", **_method_identity(),
        "assignment_batch_id": report["assignment_batch_id"], "selected_design_sha": report["selected_design_sha"],
        "deployment_manifest_sha256": sha256_file(manifest_path),
        "deployment_ids": sorted(deployments),
        "project_ids": sorted({str(item.get("project_id")) for item in deployments.values()}),
        "planned_import_sha256": {key: sha256_file(value) for key, value in planned_by_deployment.items()},
        "runtime_export_sha256": {key: sha256_file(value) for key, value in runtime_by_deployment.items()},
        "runtime_mapping_sha256": sha256_file(mapping), "runtime_task_count": sum(runtime_task_counts_by_deployment.values()),
        "runtime_task_count_by_deployment": runtime_task_counts_by_deployment,
        "worker_task_binding_count": len(bindings_by_deployment), "one_to_one": True, "gt_isolated": True,
        "formal_ready": True, "C2B_RUNTIME_BINDING_READY": True,
        "dependencies": [{"role": role, "path": str(path.resolve()), "sha256": sha256_file(path)} for role, path in dependencies],
    }
    (args.output_dir / "c2b_worker_task_binding_audit.json").write_text(json.dumps(audit, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    worker_bundle = args.worker_distribution.parent / "worker_facing_distribution_C2B"
    worker_files = sorted(worker_bundle.glob("worker_*_C2B.csv")) if worker_bundle.is_dir() else []
    expected_workers = set(worker_deployment)
    private_workers = set()
    private_rows: list[dict[str, str]] = []
    private_errors: list[str] = []
    for path in worker_files:
        stem = path.stem
        worker = normalize_worker_id(stem[len("worker_"):-len("_C2B")] if stem.startswith("worker_") and stem.endswith("_C2B") else "")
        rows = _read(path)
        if not worker or worker in private_workers:
            private_errors.append(f"invalid_or_duplicate_worker_file:{path.name}")
        private_workers.add(worker)
        if any(normalize_worker_id(row.get("worker_id", "")) != worker for row in rows):
            private_errors.append(f"private_list_worker_identity_mismatch:{path.name}")
        private_rows.extend({**row, "worker_id": worker} for row in rows)
    private_ids = {(row.get("worker_id", ""), row.get("task_id", "")) for row in private_rows}
    private_complete = private_workers == expected_workers and not private_errors and len(private_rows) == len(private_ids) and private_ids == assignment_ids
    private_audit = {
        "schema_version": "paper_a_c2b_private_assignment_list_audit_v2", "contract_role": "generated_subordinate", **_method_identity(),
        "assignment_manifest_sha256": sha256_file(args.assignment_manifest), "worker_distribution_sha256": sha256_file(args.worker_distribution),
        "private_file_workers": sorted(private_workers), "expected_workers": sorted(expected_workers), "private_file_errors": private_errors,
        "private_lists_complete": private_complete, "all_assignment_rows_covered": private_complete,
        "outside_submission_policy": "exclude_from_primary_and_audit", "assignment_batch_id": report["assignment_batch_id"],
        "formal_ready": private_complete, "private_assignment_list_audit_passed": private_complete,
        "dependencies": audit["dependencies"],
    }
    (args.output_dir / "c2b_private_assignment_list_audit.json").write_text(json.dumps(private_audit, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    audit["formal_ready"] = private_complete
    audit["C2B_RUNTIME_BINDING_READY"] = private_complete
    (args.output_dir / "c2b_worker_task_binding_audit.json").write_text(json.dumps(audit, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    if not private_complete:
        raise ValueError("private assignment lists are incomplete or inconsistent")
    if migration_envelope is not None:
        envelope_artifacts = {
            str(item.get("path", "")).strip(): item
            for item in migration_envelope.get("target_artifacts", [])
            if isinstance(item, dict) and str(item.get("path", "")).strip()
        }
        assignment_mapping_path = Path(str(migration_envelope.get("assignment_mapping_path", "")))
        mapping_item = envelope_artifacts.get(str(assignment_mapping_path.resolve()))
        if (not assignment_mapping_path.is_file() or not isinstance(mapping_item, dict)
                or mapping_item.get("sha256") != migration_envelope.get("assignment_mapping_sha256")
                or sha256_file(assignment_mapping_path) != mapping_item.get("sha256")):
            raise ValueError("C2-B migration envelope assignment mapping path/SHA is stale")
        runtime_evidence = {
            "schema_version": "paper_a_c2b_v17_to_v18_runtime_evidence_v1",
            "artifact_role": "C2B_V17_TO_V18_RUNTIME_EVIDENCE",
            "contract_role": "generated_subordinate",
            "formal_ready": True,
            "runtime_binding_status": "bound",
            "method_contract_version": report["method_contract_version"],
            "method_contract_sha256": report["method_contract_sha256"],
            "source_method_contract_version": report.get("source_method_contract_version", ""),
            "source_method_contract_sha256": report.get("source_method_contract_sha256", ""),
            "selected_design_id": report["selected_design_id"],
            "selected_design_sha": report["selected_design_sha"],
            "assignment_batch_id": report["assignment_batch_id"],
            "assignment_sha256": sha256_file(args.assignment_manifest),
            "worker_task_binding_count": len(bindings_by_deployment),
            "deployment_ids": sorted(deployments),
            "project_ids": {key: str(item.get("project_id", "")) for key, item in deployments.items()},
            "server_instance_ids": {key: str(item.get("server_instance_id", "")) for key, item in deployments.items()},
            "planned_import_sha256": {key: sha256_file(value) for key, value in planned_by_deployment.items()},
            "runtime_export_sha256": {key: sha256_file(value) for key, value in runtime_by_deployment.items()},
            "runtime_task_count": sum(runtime_task_counts_by_deployment.values()),
            "runtime_task_count_by_deployment": runtime_task_counts_by_deployment,
            "runtime_mapping_path": str(mapping.resolve()),
            "runtime_mapping_sha256": sha256_file(mapping),
            "private_assignment_audit_path": str((args.output_dir / "c2b_private_assignment_list_audit.json").resolve()),
            "private_assignment_audit_sha256": sha256_file(args.output_dir / "c2b_private_assignment_list_audit.json"),
            "launch_report_path": str(args.launch_report.resolve()),
            "launch_report_sha256": sha256_file(args.launch_report),
            "deployment_manifest_path": str(manifest_path.resolve()),
            "deployment_manifest_sha256": sha256_file(manifest_path),
            "migration_envelope_path": str(migration_envelope_path.resolve()),
            "migration_envelope_sha256": sha256_file(migration_envelope_path),
            "runtime_export_paths": {key: str(value.resolve()) for key, value in runtime_by_deployment.items()},
            "dependencies": [
                {"role": "MIGRATION_ENVELOPE", "path": str(migration_envelope_path.resolve()), "sha256": sha256_file(migration_envelope_path)},
                {"role": "LAUNCH_REPORT", "path": str(args.launch_report.resolve()), "sha256": sha256_file(args.launch_report)},
                {"role": "DEPLOYMENT_MANIFEST", "path": str(manifest_path.resolve()), "sha256": sha256_file(manifest_path)},
                {"role": "RUNTIME_MAPPING", "path": str(mapping.resolve()), "sha256": sha256_file(mapping)},
                {"role": "PRIVATE_ASSIGNMENT_AUDIT", "path": str((args.output_dir / "c2b_private_assignment_list_audit.json").resolve()), "sha256": sha256_file(args.output_dir / "c2b_private_assignment_list_audit.json")},
                {"role": "METHOD_CONTRACT", "path": str(METHOD_CONTRACT.resolve()), "sha256": sha256_file(METHOD_CONTRACT)},
            ],
        }
        _write_json_new(runtime_evidence_path, runtime_evidence)
        audit["runtime_evidence_path"] = str(runtime_evidence_path.resolve())
        audit["runtime_evidence_sha256"] = sha256_file(runtime_evidence_path)
        (args.output_dir / "c2b_worker_task_binding_audit.json").write_text(json.dumps(audit, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return audit


def bind_c2b_runtime_mapping(args: argparse.Namespace) -> dict[str, Any]:
    """Bind a manual Label Studio import export to the frozen planned task IDs."""
    report = _require_current_subordinate(args.launch_report, "c2b_launch_report")
    if report.get("schema_version") == "paper_a_c2b_launch_ready_report_v4" or report.get("deployments"):
        return _bind_c2b_runtime_mapping_multi(args, report)
    if isinstance(getattr(args, "planned_import", None), list):
        if len(args.planned_import) != 1:
            raise ValueError("legacy C2-B runtime binding accepts exactly one planned import")
        args.planned_import = args.planned_import[0]
    if isinstance(getattr(args, "runtime_export", None), list):
        if len(args.runtime_export) != 1:
            raise ValueError("legacy C2-B runtime binding accepts exactly one runtime export")
        args.runtime_export = args.runtime_export[0]
    assignment_rows = _read(args.assignment_manifest)
    assignments = _read(args.worker_distribution)
    assignment_ids = {(row.get("worker_id", ""), row.get("task_id", "")) for row in assignment_rows}
    distribution_ids = {(row.get("worker_id", ""), row.get("task_id", "")) for row in assignments}
    if assignment_ids != distribution_ids or len(assignment_ids) != len(assignment_rows):
        raise ValueError("assignment manifest and worker distribution are not a complete unique match")
    imports = json.loads(args.planned_import.read_text(encoding="utf-8"))
    expected = {
        str(item.get("data", {}).get("planned_task_id", "")): item
        for item in imports if isinstance(item, dict) and item.get("data", {}).get("planned_task_id")
    }
    if not expected or set(expected) != {row.get("task_id", "") for row in assignments}:
        raise ValueError("planned import does not exactly cover the frozen worker distribution")
    runtime_payload = json.loads(args.runtime_export.read_text(encoding="utf-8"))
    runtime_rows = runtime_payload if isinstance(runtime_payload, list) else runtime_payload.get("tasks", runtime_payload.get("data", []))
    if not isinstance(runtime_rows, list):
        raise ValueError("runtime export must contain a task list")
    runtime_by_planned: dict[str, dict[str, Any]] = {}
    runtime_ids: set[str] = set()
    for row in runtime_rows:
        if not isinstance(row, dict):
            continue
        data = row.get("data", {}) if isinstance(row.get("data", {}), dict) else {}
        planned = str(data.get("planned_task_id", ""))
        runtime_id = str(row.get("id", row.get("task_id", "")))
        if not planned:
            continue
        if planned in runtime_by_planned or not runtime_id or runtime_id in runtime_ids:
            raise ValueError("runtime export has duplicate planned or runtime task IDs")
        if planned not in expected or data.get("selected_design_sha") != report.get("selected_design_sha") or data.get("c2b_batch_id") != report.get("assignment_batch_id"):
            raise ValueError("runtime export task is outside the frozen batch/design identity")
        if str(data.get("dataset_group", "")).upper() == "GT" or str(data.get("task_role", "")).upper() == "GT":
            raise ValueError("GT task leaked into runtime C2-B import")
        runtime_by_planned[planned] = row; runtime_ids.add(runtime_id)
    if set(runtime_by_planned) != set(expected):
        raise ValueError("runtime export is missing or adds planned C2-B tasks")
    bindings = [{
        "worker_id": row["worker_id"], "planned_task_id": row["task_id"],
        "runtime_task_id": str(runtime_by_planned[row["task_id"]].get("id", runtime_by_planned[row["task_id"]].get("task_id", ""))),
        "assignment_batch_id": report["assignment_batch_id"], "selected_design_sha": report["selected_design_sha"],
    } for row in assignments]
    if len({(row["worker_id"], row["runtime_task_id"]) for row in bindings}) != len(bindings):
        raise ValueError("runtime mapping is not one-to-one within worker distributions")
    args.output_dir.mkdir(parents=True, exist_ok=True)
    mapping = args.output_dir / "c2b_runtime_task_mapping.csv"; _write(mapping, bindings)
    audit = {
        "schema_version": "paper_a_c2b_runtime_mapping_audit_v1", "contract_role": "generated_subordinate", **_method_identity(),
        "assignment_batch_id": report["assignment_batch_id"], "selected_design_sha": report["selected_design_sha"],
        "runtime_mapping_sha256": sha256_file(mapping), "runtime_task_count": len(runtime_by_planned), "worker_task_binding_count": len(bindings),
        "one_to_one": True, "gt_isolated": True,
        "dependencies": [{"role": role, "path": str(path.resolve()), "sha256": sha256_file(path)} for role, path in (("LAUNCH_REPORT", args.launch_report), ("ASSIGNMENT_MANIFEST", args.assignment_manifest), ("WORKER_DISTRIBUTION", args.worker_distribution), ("PLANNED_IMPORT", args.planned_import), ("RUNTIME_EXPORT", args.runtime_export), ("METHOD_CONTRACT", METHOD_CONTRACT))],
    }
    (args.output_dir / "c2b_worker_task_binding_audit.json").write_text(json.dumps(audit, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    worker_bundle = args.worker_distribution.parent / "worker_facing_distribution_C2B"
    worker_files = sorted(worker_bundle.glob("worker_*_C2B.csv")) if worker_bundle.is_dir() else []
    expected_private_workers = {normalize_worker_id(row.get("worker_id", "")) for row in assignments if normalize_worker_id(row.get("worker_id", ""))}
    private_file_workers: set[str] = set()
    private_rows: list[dict[str, str]] = []
    private_file_errors: list[str] = []
    if not worker_files:
        private_file_errors.append("worker_facing_distribution_C2B_missing_or_empty")
    for path in worker_files:
        stem = path.stem
        worker = normalize_worker_id(stem[len("worker_"):-len("_C2B")] if stem.startswith("worker_") and stem.endswith("_C2B") else "")
        rows = _read(path)
        if not worker or worker in private_file_workers:
            private_file_errors.append(f"invalid_or_duplicate_worker_file:{path.name}")
        private_file_workers.add(worker)
        if any(normalize_worker_id(row.get("worker_id", "")) != worker for row in rows):
            private_file_errors.append(f"private_list_worker_identity_mismatch:{path.name}")
        private_rows.extend({**row, "worker_id": normalize_worker_id(row.get("worker_id", ""))} for row in rows)
    private_ids = {(row.get("worker_id", ""), row.get("task_id", "")) for row in private_rows}
    private_duplicate_count = len(private_rows) - len(private_ids)
    distribution_ids_normalized = {(normalize_worker_id(worker), task) for worker, task in distribution_ids}
    private_lists_complete = (
        private_file_workers == expected_private_workers
        and not private_file_errors
        and private_duplicate_count == 0
        and private_ids == distribution_ids_normalized
    )
    private_audit = {
        "schema_version": "paper_a_c2b_private_assignment_list_audit_v1",
        "contract_role": "generated_subordinate",
        **_method_identity(),
        "assignment_manifest_sha256": sha256_file(args.assignment_manifest),
        "worker_distribution_sha256": sha256_file(args.worker_distribution),
        "per_worker_list_bundle_sha256": _aggregate_sha(_manifest_rows(worker_files)) if worker_files else "",
        "worker_file_count": len(worker_files), "expected_worker_count": len(expected_private_workers),
        "private_file_workers": sorted(private_file_workers), "expected_workers": sorted(expected_private_workers),
        "private_file_errors": private_file_errors, "private_duplicate_worker_task_count": private_duplicate_count,
        "private_lists_complete": private_lists_complete,
        "all_assignment_rows_covered": assignment_ids == distribution_ids and len(assignment_ids) == len(assignment_rows) == len(assignments) and private_lists_complete,
        "duplicate_worker_task_count": max(len(assignment_rows) - len(assignment_ids), len(assignments) - len(distribution_ids)),
        "outside_submission_policy": "exclude_from_primary_and_audit",
        "assignment_batch_id": report["assignment_batch_id"],
        "selected_design_sha": report["selected_design_sha"],
        "formal_ready": private_lists_complete,
        "private_assignment_list_audit_passed": private_lists_complete,
        "dependencies": audit["dependencies"],
    }
    (args.output_dir / "c2b_private_assignment_list_audit.json").write_text(json.dumps(private_audit, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    audit["formal_ready"] = private_lists_complete
    audit["C2B_RUNTIME_BINDING_READY"] = private_lists_complete
    (args.output_dir / "c2b_worker_task_binding_audit.json").write_text(json.dumps(audit, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    if not private_lists_complete:
        raise ValueError("private assignment lists are incomplete or inconsistent")
    return audit


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
        command.add_argument("--authorized-reassignment-manifest", type=Path)
        command.add_argument("--late-entry-assignment-manifest", type=Path)
        command.add_argument("--calibration-enrollment-registry", type=Path)
        command.add_argument("--w034-active-time-validation-manifest", type=Path)
        command.add_argument("--w034-preassignment-timing-verification-attestation", type=Path)
        command.add_argument("--building-registry", type=Path)

    rehearsal = sub.add_parser("rehearse-c1")
    add_c1_inputs(rehearsal, active_name="--active-log")
    rehearsal.add_argument("--annotation-independence-disposition", dest="independence_disposition", type=Path)
    rehearsal.add_argument("--scope-initial-review", type=Path)
    for name in ("duplicate-adjudication", "structural-disposition", "project-independence-disposition", "scope-adjudication", "reference-amendment", "outside-assignment-disposition", "completion-disposition"):
        rehearsal.add_argument(f"--{name}", type=Path)

    static = sub.add_parser("prepare-c2b-static")
    for name in ("p1-closeout-dir", "inventory-csv", "legacy-manifest", "reference-dir", "layout-dir", "checkpoint", "config", "feature-audit-threshold-manifest", "output-dir"):
        static.add_argument(f"--{name}", type=Path, required=True)
    static.add_argument("--c1-assignment", action="append", type=Path, required=True)
    static.add_argument("--p1-initialization-import", action="append", type=Path, required=True)
    static.add_argument("--building-registry", type=Path)
    static.add_argument("--device", default="cuda:0")

    stage3 = sub.add_parser("prepare-stage3-test-candidate")
    stage3.add_argument("--test-list", type=Path, default=Path("data/mp3d_test.txt"))
    stage3.add_argument("--image-dir", type=Path, default=Path("data/mp3d_layout/test/img"))
    stage3.add_argument("--gt-dir", type=Path, default=Path("data/mp3d_layout/test/label_cor"))
    stage3.add_argument("--layout-dir", type=Path, default=Path("output/layout_json"))
    stage3.add_argument("--validation-image-dir", type=Path, default=Path("data/mp3d_layout/valid/img"))
    stage3.add_argument("--building-registry", type=Path, default=Path("analysis_results/c2b_validation_static_20260802_v16/inputs/authoritative_building_registry.csv"))
    stage3.add_argument("--c1-risk-reference", type=Path, default=Path("analysis_results/c2b_validation_design_20260802_v17/output/c1_task_risk_reference.csv"))
    stage3.add_argument("--c1-risk-summary", type=Path, default=Path("analysis_results/c2b_validation_design_20260802_v17/output/c2_task_risk.summary.json"))
    stage3.add_argument("--feature-freeze-manifest", type=Path, default=Path("analysis_results/c2b_validation_static_20260802_v16/static/c2_feature_freeze_manifest.json"))
    stage3.add_argument("--feature-audit-threshold-manifest", type=Path, default=Path("docs/thesis_main/C2B_FEATURE_AUDIT_THRESHOLDS.json"))
    stage3.add_argument("--risk-contract", type=Path, default=Path("docs/thesis_main/C2B_RISK_DESIGN_CONTRACT_v1.json"))
    stage3.add_argument("--checkpoint", type=Path, default=Path("ckpt/mp3d_layout_HOHO_layout_aug_efficienthc_Transen1_resnet34/ep300.pth"))
    stage3.add_argument("--config", type=Path, default=Path("config/mp3d_layout/HOHO_layout_aug_efficienthc_Transen1_resnet34.yaml"))
    stage3.add_argument("--exposure-source", action="append", default=[], metavar="STAGE=PATH")
    stage3.add_argument("--output-dir", type=Path, default=Path("analysis_results/stage3_test_preparation_20260804_v1"))
    stage3.add_argument("--device", default="cuda:0")

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
    audit.add_argument("--scope-initial-review", type=Path, required=True)
    for name in ("duplicate-adjudication", "structural-disposition", "scope-adjudication", "outside-assignment-disposition"):
        audit.add_argument(f"--{name}", type=Path, required=True)
    for name in ("project-independence-disposition", "reference-amendment", "completion-disposition"):
        audit.add_argument(f"--{name}", type=Path)

    finalize = sub.add_parser("finalize-c1")
    finalize.add_argument("--output-dir", type=Path, required=True)
    finalize.add_argument("--adjudication-manifest", type=Path, required=True)

    batch_freeze = sub.add_parser("freeze-c1-batch")
    batch_freeze.add_argument("--c1-output-dir", type=Path, required=True)
    batch_freeze.add_argument("--batch-scope-manifest", type=Path, required=True)
    batch_freeze.add_argument("--authorized-reassignment-manifest", type=Path)
    batch_freeze.add_argument("--output", type=Path, required=True)

    plan = sub.add_parser("design-c2b")
    for name in ("c1-closeout-summary", "inventory-csv", "layout-dir", "c1-task-feature-csv", "checkpoint", "building-registry", "source-split-evidence", "source-split-approval", "future-holdout-evidence", "future-holdout-approval", "history-overlap-audit", "scope-registry", "reference-registry", "feature-freeze-manifest", "static-freeze-manifest", "threshold-formula-contract", "threshold-input-approval", "threshold-manifest", "capacity-manifest", "output-dir"):
        plan.add_argument(f"--{name}", type=Path, required=True)
    plan.add_argument("--device", default="auto")

    build = sub.add_parser("build-c2b")
    for name in ("c1-closeout-summary", "risk-summary", "task-pool", "task-eligibility-evidence", "candidate-dir", "design-manifest", "selected-design-manifest", "threshold-manifest", "source-split-evidence", "source-split-approval", "future-holdout-evidence", "future-holdout-approval", "reference-registry", "selected-task-reference-manifest", "selected-design-approval", "capacity-manifest", "layout-dir", "output-dir"):
        build.add_argument(f"--{name}", type=Path, required=True)
    build.add_argument("--c2b-roster-manifest", type=Path, required=True)
    build.add_argument("--deployment-manifest", type=Path)
    build.add_argument("--assignment-batch", choices=("C2B_BATCH_A", "C2B_BATCH_B"), default="C2B_BATCH_A")
    for name in ("batch-a-launch-report", "batch-a-assignment", "batch-worker-profile", "p1-admission-evidence"):
        build.add_argument(f"--{name}", type=Path)

    migration = sub.add_parser("repackage-c2b-v17-to-v18")
    migration.add_argument("--legacy-root", type=Path, default=Path("analysis_results/c2b_build_20260802_v17_d8"))
    migration.add_argument("--legacy-launch-report", type=Path)
    migration.add_argument("--legacy-assignment", type=Path)
    migration.add_argument("--legacy-selected-design-manifest", type=Path)
    migration.add_argument("--legacy-import-zh", type=Path)
    migration.add_argument("--legacy-import-foreign", type=Path)
    migration.add_argument("--worker-language-source", type=Path, required=True)
    migration.add_argument("--deployment-config", type=Path, required=True)
    migration.add_argument("--output-dir", type=Path, required=True)
    migration.add_argument("--target-import-dir", type=Path, default=Path("import_json/c2b"))
    migration.add_argument("--target-method-contract", type=Path)

    runtime = sub.add_parser("bind-c2b-runtime-mapping")
    for name in ("launch-report", "assignment-manifest", "worker-distribution", "output-dir"):
        runtime.add_argument(f"--{name}", type=Path, required=True)
    runtime.add_argument("--deployment-manifest", type=Path)
    runtime.add_argument("--planned-import", action="append", type=Path)
    runtime.add_argument("--runtime-export", action="append", type=Path)
    args = parser.parse_args(argv)
    command = {
        "prepare-c2b-static": prepare_c2b_static,
        "prepare-stage3-test-candidate": prepare_stage3_test_candidate,
        "expand-building-registry": expand_building_registry,
        "check-command-contract": check_command_contract,
        "preflight-calibration": preflight_calibration,
        "rehearse-c1": rehearse_c1,
        "freeze-c1": freeze_c1,
        "freeze-c1-batch": freeze_c1_batch,
        "audit-c1": audit_c1,
        "finalize-c1": finalize_c1,
        "design-c2b": design_c2b,
        "build-c2b": build_c2b,
        "repackage-c2b-v17-to-v18": repackage_c2b_v17_to_v18,
        "bind-c2b-runtime-mapping": bind_c2b_runtime_mapping,
    }[args.command]
    print(json.dumps(command(args), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
