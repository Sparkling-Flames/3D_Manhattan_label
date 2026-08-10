"""Thin C2-B export -> C2-A-RP operational chain.

This module deliberately orchestrates existing Paper A materializers.  It does
not build a new C2-B design, alter an assignment, or infer deployment identity
from a worker-facing index.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import random
import shutil
import sys
import tempfile
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Iterable
from urllib.parse import quote

PROJECT_ROOT = Path(__file__).resolve().parents[3]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from tools.thesis_main.analysis.c1_materialize_c2_gap_audits import C2A_ASSIGNMENT_FIELDS, materialize as materialize_c2a_rp
from tools.thesis_main.analysis.active_log_utils import resolve_active_log_files
from tools.thesis_main.analysis.geometry_consensus.representation import normalize_geometry, normalize_ordered_reference_geometry
from tools.thesis_main.analysis.materialize_c1_c2_design_parameters import _fit_crossed_model
from tools.thesis_main.analysis.materialize_c2b_closeout import materialize as materialize_c2b_closeout
from tools.thesis_main.analysis.paper_a_contracts import METHOD_CONTRACT, load_method_contract
from tools.thesis_main.analysis.prescreen_canonicalize_export import build_canonical_tables
from tools.thesis_main.analysis.quality_core.choice_parser import extract_data
from tools.thesis_main.analysis.quality_core.geometry_metrics import compute_layout_mask_iou_from_normalized_pairs
from tools.thesis_main.analysis.vfinal_artifact_utils import sha256_file
from tools.thesis_main.analysis.worker_identity import normalize_worker_id


CHAIN_SCHEMA = "paper_a_c2b_c2a_rp_chain_v1"
RISK_EVIDENCE_SCHEMA = "c2b_canonical_risk_slope_evidence_v1"
FORMAL_MODES = {"precloseout_rehearsal", "formal"}
C2PLUS_ACTIVE_TIME_SCRIPT_VERSION = "c2plus_task_worker_active_time_20260802_v2"
C2PLUS_ACTIVE_TIME_SCHEMA_VERSION = "c2plus_task_worker_v1"
C2PLUS_ACTIVE_TIME_IDENTITY_LEVEL = "project_runtime_task_worker"


def _text(value: Any) -> str:
    return "" if value is None else str(value).strip()


def _truth(value: Any) -> bool:
    return _text(value).lower() in {"1", "true", "yes"}


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as stream:
        return list(csv.DictReader(stream))


def _write_csv(path: Path, rows: list[dict[str, Any]], fields: Iterable[str] | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    names = list(fields or [])
    for row in rows:
        for key in row:
            if key not in names:
                names.append(key)
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=names, extrasaction="raise", lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as stream:
        stream.write(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n")


def _relocate_paths(value: Any, source_root: Path, target_root: Path) -> Any:
    source_root = source_root.resolve()
    target_root = target_root.resolve()
    if isinstance(value, dict):
        return {key: _relocate_paths(item, source_root, target_root) for key, item in value.items()}
    if isinstance(value, list):
        return [_relocate_paths(item, source_root, target_root) for item in value]
    if isinstance(value, str):
        try:
            relative = Path(value).resolve().relative_to(source_root)
        except (OSError, ValueError):
            return value
        return str((target_root / relative).resolve())
    return value


def _prepare_c2a_decision_manifest(
    source_path: Path,
    worker_profile_path: Path,
    task_pool_path: Path,
    assignment_history_path: Path,
    threshold_path: Path,
    output_path: Path,
    *,
    bound_input_paths: dict[str, Path],
) -> dict[str, Any]:
    """Bind post-C2 inputs without mutating the frozen source manifest."""
    source = json.loads(source_path.read_text(encoding="utf-8"))
    if not isinstance(source, dict) or source.get("manifest_version") != "c2_design_v1":
        raise ValueError("unsupported C2 design manifest version")
    source_inputs = source.get("input_sha256") or {}
    if not isinstance(source_inputs, dict):
        raise ValueError("C2 design manifest input_sha256 must be an object")
    method = _method_identity()
    target_inputs = {str(key): value for key, value in source_inputs.items()}
    target_inputs.update({
        "worker_profile_csv": _sha(worker_profile_path),
        "c2a_task_pool_csv": _sha(task_pool_path),
        "assignment_history_csv": _sha(assignment_history_path),
        "threshold_manifest": _sha(threshold_path),
    })
    precision = dict(source.get("precision") or {})
    source_threshold_sha = _text(precision.get("threshold_manifest_sha256") or source.get("threshold_manifest_sha256"))
    precision["threshold_manifest_path"] = str(threshold_path.resolve())
    precision["threshold_manifest_sha256"] = _sha(threshold_path)
    bound = {
        **source,
        **method,
        "precision": precision,
        "input_sha256": target_inputs,
        "source_manifest_sha256": _sha(source_path),
        "source_input_sha256": dict(source_inputs),
        "source_method_contract_version": _text(source.get("method_contract_version")),
        "source_method_contract_sha256": _text(source.get("method_contract_sha256")),
        "binding_mode": "post_c2b_profile_bound",
        "bound_input_paths": {key: str(path.resolve()) for key, path in bound_input_paths.items()},
        "threshold_manifest_path": str(threshold_path.resolve()),
        "threshold_manifest_sha256": _sha(threshold_path),
        "binding_map": {
            "method_contract_sha256": {
                "source_sha256": _text(source.get("method_contract_sha256")),
                "target_sha256": method["method_contract_sha256"],
            },
            "worker_profile_csv": {
                "source_sha256": _text(source_inputs.get("worker_profile_csv")),
                "target_sha256": target_inputs["worker_profile_csv"],
            },
            "c2a_task_pool_csv": {
                "source_sha256": _text(source_inputs.get("c2a_task_pool_csv")),
                "target_sha256": target_inputs["c2a_task_pool_csv"],
            },
            "assignment_history_csv": {
                "source_sha256": _text(source_inputs.get("assignment_history_csv")),
                "target_sha256": target_inputs["assignment_history_csv"],
            },
            "threshold_manifest": {
                "source_sha256": source_threshold_sha,
                "target_sha256": target_inputs["threshold_manifest"],
            },
        },
    }
    _write_json(output_path, bound)
    return bound


def _sha(path: Path) -> str:
    return sha256_file(path)


def _active_time_provenance(
    active_log: Path | None,
    *,
    eligible_contexts: set[tuple[str, str, str]] | None = None,
) -> dict[str, Any]:
    """Summarize C2 timing input without making it part of primary analysis."""
    expected = {
        "script_version": C2PLUS_ACTIVE_TIME_SCRIPT_VERSION,
        "active_time_schema_version": C2PLUS_ACTIVE_TIME_SCHEMA_VERSION,
        "active_time_identity_level": C2PLUS_ACTIVE_TIME_IDENTITY_LEVEL,
    }
    if active_log is None:
        return {
            "status": "not_evaluable", "reason": "no_active_log", "expected": expected,
            "source_raw_event_count": 0, "raw_event_count": 0,
            "forensic_excluded_event_count": 0, "forensic_excluded_reasons": {},
            "worker_provenance": {},
        }

    root, files = resolve_active_log_files(active_log)
    file_manifest: list[dict[str, Any]] = []
    for path in files:
        try:
            relative = path.resolve().relative_to(root.resolve()).as_posix() if root else path.name
        except (OSError, ValueError):
            relative = path.name
        file_manifest.append({
            "relative_path": relative,
            "size": path.stat().st_size,
            "sha256": _sha(path),
        })
    file_manifest.sort(key=lambda row: row["relative_path"])
    aggregate = hashlib.sha256(
        json.dumps(file_manifest, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest() if file_manifest else ""

    counters = {key: Counter() for key in expected}
    normalized_contexts = None if eligible_contexts is None else {
        (_text(project), _text(task), normalize_worker_id(worker))
        for project, task, worker in eligible_contexts
    }
    eligible_projects = {project for project, _task, _worker in normalized_contexts or set()}
    eligible_workers = {worker for _project, _task, worker in normalized_contexts or set()}
    forensic_excluded_reasons: Counter[str] = Counter()
    source_event_count = 0
    worker_event_counts: Counter[str] = Counter()
    worker_current_event_counts: Counter[str] = Counter()
    worker_counters: dict[str, dict[str, Counter[str]]] = {}
    event_count = 0
    parse_error_count = 0
    for path in files:
        try:
            lines = path.open(encoding="utf-8", errors="replace")
        except OSError:
            parse_error_count += 1
            continue
        with lines:
            for line in lines:
                if not line.strip():
                    continue
                try:
                    event = json.loads(line)
                except json.JSONDecodeError:
                    parse_error_count += 1
                    continue
                if not isinstance(event, dict):
                    parse_error_count += 1
                    continue
                source_event_count += 1
                if normalized_contexts is not None:
                    project = _text(event.get("project_id"))
                    task = _text(event.get("task_id"))
                    worker = normalize_worker_id(event.get("annotator_id"))
                    if (project, task, worker) not in normalized_contexts:
                        if project not in eligible_projects:
                            exclusion_reason = "unexpected_project"
                        elif worker not in eligible_workers:
                            exclusion_reason = "unexpected_worker"
                        else:
                            exclusion_reason = "unassigned_worker_task"
                        forensic_excluded_reasons[exclusion_reason] += 1
                        continue
                event_count += 1
                for key in expected:
                    counters[key][_text(event.get(key)) or "<missing>"] += 1
                worker = normalize_worker_id(event.get("annotator_id"))
                if worker:
                    worker_event_counts[worker] += 1
                    worker_counters.setdefault(worker, {key: Counter() for key in expected})
                    current_payload = True
                    for key in expected:
                        value = _text(event.get(key)) or "<missing>"
                        worker_counters[worker][key][value] += 1
                        current_payload = current_payload and value == expected[key]
                    if current_payload:
                        worker_current_event_counts[worker] += 1

    observed = {key: dict(sorted(counter.items())) for key, counter in counters.items()}
    if not files or event_count == 0:
        status, reason = "not_evaluable", "no_parseable_events"
    elif parse_error_count or any(set(counters[key]) != {expected[key]} for key in expected):
        status, reason = "auxiliary_mixed_or_legacy", "legacy_unknown_or_mixed_payload"
    else:
        status, reason = "auxiliary_available", "current_c2plus_payload"
    worker_provenance = {}
    for worker in sorted(worker_event_counts):
        total = worker_event_counts[worker]
        current = worker_current_event_counts[worker]
        worker_provenance[worker] = {
            "status": "auxiliary_available" if current == total else "auxiliary_mixed_or_legacy",
            "reason": "current_c2plus_payload" if current == total else "worker_has_legacy_or_mixed_payload",
            "raw_event_count": total,
            "current_c2plus_event_count": current,
            "legacy_or_mixed_event_count": total - current,
            "observed": {key: dict(sorted(counter.items())) for key, counter in worker_counters[worker].items()},
        }
    return {
        "status": status,
        "reason": reason,
        "source_path": str(Path(active_log).resolve()),
        "source_root": str(root.resolve()) if root else "",
        "source_file_count": len(files),
        "source_files": file_manifest,
        "source_aggregate_sha256": aggregate,
        "raw_event_count": event_count,
        "source_raw_event_count": source_event_count,
        "forensic_excluded_event_count": sum(forensic_excluded_reasons.values()),
        "forensic_excluded_reasons": dict(sorted(forensic_excluded_reasons.items())),
        "parse_error_count": parse_error_count,
        "observed": observed,
        "expected": expected,
        "worker_provenance": worker_provenance,
    }


def _method_identity() -> dict[str, str]:
    method = load_method_contract()
    return {"method_contract_version": str(method["contract_version"]), "method_contract_sha256": _sha(METHOD_CONTRACT)}


def _path(value: str | Path) -> Path:
    return Path(value).expanduser().resolve()


def _resolve_relative(value: Any, *, bases: tuple[Path, ...]) -> Path:
    candidate = Path(_text(value))
    if candidate.is_absolute():
        return candidate
    for base in bases:
        resolved = (base / candidate).resolve()
        if resolved.is_file():
            return resolved
    return (bases[0] / candidate).resolve()


def _language_token(value: Any) -> str:
    token = _text(value).lower().replace("_", "-")
    if token in {"zh", "cn", "chinese", "中文"}:
        return "zh"
    if token in {"en", "english", "foreign", "foreign-https", "英文"}:
        return "foreign"
    raise ValueError(f"unsupported deployment language_group:{value}")


def _parse_bindings(values: list[str] | None, *, option: str) -> dict[str, Path]:
    parsed: dict[str, Path] = {}
    for value in values or []:
        if "=" not in value:
            raise ValueError(f"{option} must use deployment_id=path")
        key, raw_path = value.split("=", 1)
        key = _text(key)
        if not key or key in parsed:
            raise ValueError(f"duplicate {option} deployment_id:{key}")
        parsed[key] = _path(raw_path)
    return parsed


def _load_deployments(path: Path, assignment_rows: list[dict[str, str]]) -> tuple[dict[str, dict[str, Any]], dict[str, str]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if payload.get("schema_version") != "c2b_worker_deployment_manifest_v1":
        raise ValueError("C2-B deployment manifest schema is invalid")
    deployments = payload.get("deployments")
    if not isinstance(deployments, list) or not deployments:
        raise ValueError("C2-B deployment manifest requires deployments[]")
    workers = {normalize_worker_id(row.get("worker_id", "")) for row in assignment_rows}
    if "" in workers:
        raise ValueError("C2-B assignment contains an empty worker_id")
    by_id: dict[str, dict[str, Any]] = {}
    worker_to_deployment: dict[str, str] = {}
    for item in deployments:
        if not isinstance(item, dict):
            raise ValueError("C2-B deployment manifest contains a non-object deployment")
        deployment_id = _text(item.get("deployment_id"))
        if not deployment_id or deployment_id in by_id:
            raise ValueError("C2-B deployment manifest has duplicate deployment_id")
        language = _language_token(item.get("language_group"))
        required = ("server_instance_id", "server_url", "project_id")
        if any(not _text(item.get(field)) for field in required):
            raise ValueError(f"C2-B deployment identity is incomplete:{deployment_id}")
        raw_workers = item.get("worker_ids", item.get("workers", []))
        if not isinstance(raw_workers, list) or not raw_workers:
            raise ValueError(f"C2-B deployment has no explicit worker_ids:{deployment_id}")
        normalized_workers = [normalize_worker_id(value) for value in raw_workers]
        if any(not worker for worker in normalized_workers):
            raise ValueError(f"C2-B deployment contains an empty worker_id:{deployment_id}")
        if len(set(normalized_workers)) != len(normalized_workers):
            raise ValueError(f"C2-B deployment contains a duplicate worker_id:{deployment_id}")
        for worker in normalized_workers:
            if worker in worker_to_deployment:
                raise ValueError(f"worker maps to multiple deployments:{worker}")
            worker_to_deployment[worker] = deployment_id
        by_id[deployment_id] = {
            **item,
            "deployment_id": deployment_id,
            "language_group": item["language_group"],
            "language_token": language,
            "worker_ids": sorted(set(normalized_workers)),
        }
    if set(worker_to_deployment) != workers:
        raise ValueError("deployment manifest does not cover exactly the assigned workers")
    return by_id, worker_to_deployment


def _validate_assignment_identity(
    assignment_path: Path,
    assignment_rows: list[dict[str, str]],
    *,
    selected_design_id: str = "D8",
    expected_assignments: int = 176,
    expected_tasks: int = 46,
    expected_workers: int = 22,
) -> tuple[set[tuple[str, str]], set[str], set[str]]:
    if len(assignment_rows) != expected_assignments:
        raise ValueError(f"D8 assignment count changed:{len(assignment_rows)}")
    identity = {
        (normalize_worker_id(row.get("worker_id", "")), _text(row.get("task_id")))
        for row in assignment_rows
    }
    if any(not worker or not task for worker, task in identity) or len(identity) != len(assignment_rows):
        raise ValueError("D8 assignment has empty or duplicate worker-task identity")
    task_ids = {task for _worker, task in identity}
    workers = {worker for worker, _task in identity}
    if len(task_ids) != expected_tasks or len(workers) != expected_workers:
        raise ValueError(f"D8 assignment identity changed:workers={len(workers)},tasks={len(task_ids)}")
    if any(_text(row.get("assignment_batch_id")) != "C2B_BATCH_A" for row in assignment_rows):
        raise ValueError("D8 assignment is not C2B_BATCH_A")
    if any(_text(row.get("design_id")) != selected_design_id for row in assignment_rows):
        raise ValueError("D8 selected design identity changed")
    design_shas = {_text(row.get("design_manifest_sha256")) for row in assignment_rows}
    if len(design_shas) != 1 or "" in design_shas:
        raise ValueError("D8 design manifest identity is missing or inconsistent")
    if len({_text(row.get("base_task_id")) for row in assignment_rows}) != expected_tasks:
        raise ValueError("D8 base task identity changed")
    return identity, task_ids, workers


def _validate_launch_report(
    launch_path: Path,
    assignment_path: Path,
    deployments: dict[str, dict[str, Any]],
    *,
    allow_rehearsal: bool,
) -> dict[str, Any]:
    report = json.loads(launch_path.read_text(encoding="utf-8"))
    if report.get("schema_version") != "paper_a_c2b_launch_ready_report_v4":
        raise ValueError("C2-B chain requires the v4 multi-deployment launch report")
    method = _method_identity()
    if report.get("method_contract_sha256") != method["method_contract_sha256"]:
        raise ValueError("C2-B launch report method contract is stale")
    if report.get("assignment_sha256") != _sha(assignment_path):
        raise ValueError("C2-B launch report assignment SHA is stale")
    report_deployments = {str(item.get("deployment_id")): item for item in report.get("deployments", []) if isinstance(item, dict)}
    if set(report_deployments) != set(deployments):
        raise ValueError("C2-B launch report deployment set is incomplete")
    for deployment_id, item in report_deployments.items():
        if any(_text(item.get(field)) != _text(deployments[deployment_id].get(field)) for field in ("language_group", "server_instance_id", "project_id", "server_url")):
            raise ValueError(f"C2-B launch report deployment identity mismatch:{deployment_id}")
        planned = _path(item.get("planned_import_path", ""))
        if not planned.is_file() or item.get("planned_import_sha256") != _sha(planned):
            raise ValueError(f"C2-B planned import is missing or stale:{deployment_id}")
    if not allow_rehearsal and report.get("C2B_LAUNCH_READY") is not True:
        raise ValueError("C2-B launch report is not launch ready")
    return report


def _runtime_mapping_path(runtime_input: Path) -> tuple[Path, dict[str, Any] | None]:
    if runtime_input.suffix.lower() != ".json":
        return runtime_input, None
    payload = json.loads(runtime_input.read_text(encoding="utf-8"))
    mapping_path = _path(payload.get("runtime_mapping_path", ""))
    if not mapping_path.is_file():
        raise ValueError("runtime mapping audit lacks a valid runtime_mapping_path")
    return mapping_path, payload


def _load_runtime_mapping(path: Path) -> list[dict[str, str]]:
    rows = _read_csv(path)
    required = {"deployment_id", "project_id", "runtime_task_id", "planned_task_id", "worker_id", "server_instance_id"}
    if not rows or not required <= set(rows[0]):
        raise ValueError("runtime mapping lacks deployment-aware identity fields")
    keys = set()
    worker_task_keys = set()
    runtime_planned: dict[tuple[str, str, str], str] = {}
    project_runtime_server: dict[tuple[str, str], str] = {}
    for row in rows:
        key = tuple(_text(row.get(field)) for field in ("deployment_id", "project_id", "runtime_task_id", "worker_id"))
        worker_task = tuple(_text(row.get(field)) for field in ("deployment_id", "project_id", "planned_task_id", "worker_id"))
        runtime_key = tuple(_text(row.get(field)) for field in ("deployment_id", "project_id", "runtime_task_id"))
        project_runtime = (_text(row.get("project_id")), _text(row.get("runtime_task_id")))
        server = _text(row.get("server_instance_id"))
        if not all(key) or not all(worker_task) or not server or key in keys or worker_task in worker_task_keys:
            raise ValueError("runtime mapping contains empty or duplicate identity")
        previous_planned = runtime_planned.get(runtime_key)
        if previous_planned is not None and previous_planned != _text(row.get("planned_task_id")):
            raise ValueError("runtime mapping maps one deployment runtime task to multiple planned tasks")
        previous_server = project_runtime_server.get(project_runtime)
        if previous_server is not None and previous_server != server:
            raise ValueError("runtime mapping has a cross-server project/runtime collision")
        keys.add(key)
        worker_task_keys.add(worker_task)
        runtime_planned[runtime_key] = _text(row.get("planned_task_id"))
        project_runtime_server[project_runtime] = server
    return rows


def _load_export_payload(path: Path) -> list[dict[str, Any]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, list):
        raise ValueError(f"Label Studio export must be a task list:{path}")
    return payload


def _canonicalize_deployments(
    exports: dict[str, Path],
    active_logs: dict[str, Path | None],
    mapping_rows: list[dict[str, str]],
    assignment_by_id: dict[tuple[str, str], dict[str, str]],
    deployments: dict[str, dict[str, Any]],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    mapping_by_runtime = {
        (_text(row.get("deployment_id")), _text(row.get("project_id")), _text(row.get("runtime_task_id")), normalize_worker_id(row.get("worker_id", ""))): row
        for row in mapping_rows
    }
    rows: list[dict[str, Any]] = []
    summaries: dict[str, Any] = {}
    for deployment_id, export_path in exports.items():
        deployment_contexts = {
            (
                _text(row.get("project_id")),
                _text(row.get("runtime_task_id")),
                normalize_worker_id(row.get("worker_id", "")),
            )
            for row in mapping_rows
            if _text(row.get("deployment_id")) == deployment_id
        }
        timing_provenance = _active_time_provenance(
            active_logs.get(deployment_id), eligible_contexts=deployment_contexts,
        )
        raw_tasks = _load_export_payload(export_path)
        data_by_runtime = {
            (_text(task.get("project") or task.get("project_id")), _text(task.get("id") or task.get("task_id"))): task.get("data", {})
            for task in raw_tasks
            if isinstance(task, dict)
        }
        ordered_geometry_by_annotation: dict[tuple[str, str, str, str], str] = {}
        for task in raw_tasks:
            if not isinstance(task, dict):
                continue
            project = _text(task.get("project") or task.get("project_id"))
            runtime_task = _text(task.get("id") or task.get("task_id"))
            for index, annotation in enumerate(task.get("annotations") or [], start=1):
                if not isinstance(annotation, dict):
                    continue
                completed_by = annotation.get("completed_by")
                if isinstance(completed_by, dict):
                    worker = normalize_worker_id(
                        completed_by.get("id") or completed_by.get("email") or completed_by.get("username") or completed_by.get("pk")
                    )
                else:
                    worker = normalize_worker_id(completed_by)
                annotation_id = _text(annotation.get("id")) or f"annotation_index_{index}"
                corners, _polygon, _choices, _quality = extract_data(annotation.get("result") or [])
                ordered_geometry_by_annotation[(project, runtime_task, worker, annotation_id)] = json.dumps(
                    corners.tolist(), ensure_ascii=False, separators=(",", ":")
                )
        canonical, duplicate, summary = build_canonical_tables(
            [export_path], active_logs.get(deployment_id), duplicate_review_mode=True, round_id="C2-B",
        )
        timing_status = timing_provenance["status"]
        summaries[deployment_id] = {
            **summary, "n_duplicate_rows": len(duplicate),
            "active_log_present": active_logs.get(deployment_id) is not None,
            "timing_status": timing_status,
            "timing_provenance": timing_provenance,
        }
        for row in canonical:
            worker = normalize_worker_id(row.get("annotator_id", ""))
            project = _text(row.get("project_id"))
            runtime_task = _text(row.get("task_id"))
            binding = mapping_by_runtime.get((deployment_id, project, runtime_task, worker))
            if binding is None:
                raise ValueError(f"canonical submission is not in frozen runtime mapping:{deployment_id}/{project}/{runtime_task}/{worker}")
            planned = _text(binding.get("planned_task_id"))
            assignment = assignment_by_id.get((worker, planned))
            if assignment is None:
                raise ValueError(f"canonical submission is not in frozen assignment:{worker}/{planned}")
            data = data_by_runtime.get((project, runtime_task), {})
            if isinstance(data, dict) and _text(data.get("planned_task_id")) and _text(data.get("planned_task_id")) != planned:
                raise ValueError(f"runtime task planned_task_id disagrees with mapping:{runtime_task}")
            rows.append({
                **row,
                "deployment_id": deployment_id,
                "language_group": deployments[deployment_id]["language_group"],
                "server_instance_id": deployments[deployment_id]["server_instance_id"],
                "server_url": deployments[deployment_id]["server_url"],
                "runtime_task_id": runtime_task,
                "planned_task_id": planned,
                "task_id": planned,
                "worker_id": worker,
                "canonical_valid": str(bool(row.get("eligible_for_primary_analysis") and not row.get("parse_error"))).lower(),
                "formal_assignment_eligible": "true",
                "assignment_batch_id": _text(assignment.get("assignment_batch_id")) or "C2B_BATCH_A",
                "selected_design_id": _text(assignment.get("design_id")),
                "design_manifest_sha256": _text(assignment.get("design_manifest_sha256")),
                "task_stratum": _text(assignment.get("task_stratum")),
                "base_task_id": _text(assignment.get("base_task_id")) or planned,
                "image_id": _text(assignment.get("image_id")),
                "ordered_geometry": ordered_geometry_by_annotation.get(
                    (project, runtime_task, worker, _text(row.get("annotation_id"))), ""
                ),
                "timing_status": timing_status,
            })
    keys = [(row["worker_id"], row["planned_task_id"]) for row in rows]
    if len(keys) != len(set(keys)):
        raise ValueError("canonical C2-B submissions contain duplicate worker-task rows")
    return rows, summaries


def _load_task_index(path: Path) -> dict[str, dict[str, str]]:
    rows = _read_csv(path)
    if not rows:
        raise ValueError(f"task evidence is empty:{path}")
    index: dict[str, dict[str, str]] = {}
    for row in rows:
        for key in (_text(row.get("task_id")), _text(row.get("base_task_id"))):
            if key:
                previous = index.get(key)
                if previous and previous.get("building_id") != row.get("building_id"):
                    raise ValueError(f"task evidence has conflicting building_id:{key}")
                index[key] = row
    return index


def _load_reference_index(path: Path) -> dict[str, dict[str, str]]:
    rows = _read_csv(path)
    if not rows:
        raise ValueError(f"reference registry is empty:{path}")
    return {_text(row.get("base_task_id")) or _text(row.get("task_id")): row for row in rows if _text(row.get("base_task_id")) or _text(row.get("task_id"))}


def _load_scope_index(path: Path | None) -> dict[str, dict[str, str]]:
    if path is None:
        return {}
    rows = _read_csv(path)
    if not rows:
        raise ValueError(f"scope disposition is empty:{path}")
    index: dict[str, dict[str, str]] = {}
    for row in rows:
        key = _text(row.get("base_task_id") or row.get("task_id"))
        scope = _text(row.get("final_scope") or row.get("task_final_scope")).lower()
        if not key or scope not in {"in_scope", "oos", "unresolved"}:
            raise ValueError("scope disposition requires base_task_id and final_scope")
        if key in index:
            raise ValueError(f"scope disposition has duplicate task:{key}")
        index[key] = row
    return index


def _points(path: Path) -> list[list[float]]:
    output = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            values = line.split()
            if len(values) != 2:
                raise ValueError(f"reference point is not x y:{path}")
            output.append([float(values[0]), float(values[1])])
    return output


def _risk_slope_evidence(
    canonical_rows: list[dict[str, Any]],
    task_index: dict[str, dict[str, str]],
    reference_index: dict[str, dict[str, str]],
    *,
    reference_registry: Path,
    scope_index: dict[str, dict[str, str]] | None = None,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    evidence: list[dict[str, Any]] = []
    for row in canonical_rows:
        planned = _text(row.get("planned_task_id"))
        base_task = _text(row.get("base_task_id")) or planned
        task = task_index.get(planned) or task_index.get(base_task)
        reference = reference_index.get(base_task) or reference_index.get(planned)
        if task is None or reference is None:
            raise ValueError(f"canonical C2-B row lacks frozen task/reference evidence:{planned}")
        building = _text(task.get("building_id"))
        risk = _text(task.get("risk_design_score_A") or task.get("risk_design_score"))
        quality = ""
        status = "not_evaluable"
        reason = ""
        scope = (scope_index or {}).get(base_task) or (scope_index or {}).get(planned)
        final_scope = _text((scope or {}).get("final_scope") or (scope or {}).get("task_final_scope")).lower()
        try:
            if final_scope in {"oos", "unresolved"}:
                reason = f"scope_{final_scope}"
                raise LookupError(reason)
            pred_points = json.loads(_text(row.get("ordered_geometry") or row.get("canonical_geometry")))
            pred = normalize_geometry(pred_points)
            ref_path = _resolve_relative(reference.get("reference_path"), bases=(PROJECT_ROOT, reference_registry.parent))
            declared_reference_sha = _text(reference.get("reference_sha256"))
            if declared_reference_sha and _sha(ref_path) != declared_reference_sha:
                raise ValueError("reference_sha256_mismatch")
            ref = normalize_ordered_reference_geometry(_points(ref_path))
            reference_ready = (
                _truth(reference.get("geometry_reference_ready"))
                and _text(reference.get("reference_normalizer_status")).lower() in {"passed", "valid", "ok"}
                and (
                    _text(reference.get("registry_status")).lower().startswith("approved")
                    or _text(reference.get("reference_status")).lower() in {
                        "approved", "geometry_reference_ready", "reference_ready", "use_existing_public_gt_as_is",
                    }
                )
            )
            if not pred.get("valid") or not ref.get("valid"):
                reason = "geometry_normalization_failed"
            elif not reference_ready:
                reason = "reference_not_approved"
            else:
                value, _meta = compute_layout_mask_iou_from_normalized_pairs(pred["pairs"], ref["pairs"])
                if value is None:
                    reason = "iou_not_evaluable"
                else:
                    quality = value
                    status = "eligible"
        except LookupError:
            pass
        except (OSError, TypeError, ValueError, json.JSONDecodeError) as exc:
            reason = f"geometry_or_reference_error:{type(exc).__name__}"
        try:
            risk_value = float(risk)
            if not math.isfinite(risk_value):
                raise ValueError
        except (TypeError, ValueError):
            risk_value = ""
            status = "not_evaluable"
            reason = reason or "risk_not_numeric"
        if not building:
            status = "not_evaluable"
            reason = reason or "building_id_missing_from_frozen_evidence"
        evidence.append({
            "schema_version": RISK_EVIDENCE_SCHEMA,
            "evidence_stage": "C2B",
            "risk_model_scope": "C2B_CONFIRMATORY_CANONICAL_ONLY_FOR_C2A_RP",
            "canonical_annotation_id": _text(row.get("canonical_annotation_id")),
            "deployment_id": _text(row.get("deployment_id")),
            "project_id": _text(row.get("project_id")),
            "runtime_task_id": _text(row.get("runtime_task_id")),
            "planned_task_id": planned,
            "worker_id": _text(row.get("worker_id")),
            "task_id": _text(row.get("task_id")),
            "base_task_id": base_task,
            "image_id": _text(row.get("image_id")) or _text(task.get("image_id")),
            "building_id": building,
            "task_stratum": _text(task.get("risk_design_stratum") or row.get("task_stratum")),
            "risk": risk_value,
            "quality": quality,
            "canonical_valid": _text(row.get("canonical_valid")),
            "risk_slope_estimand_eligible": status == "eligible" and _text(row.get("canonical_valid")) == "true",
            "eligibility_status": status if _text(row.get("canonical_valid")) == "true" else "canonical_invalid",
            "ineligibility_reason": reason,
            "reference_registry_sha256": _sha(reference_registry),
            "task_pool_sha256": _text(task.get("task_risk_sha256")),
            "assignment_batch_id": _text(row.get("assignment_batch_id")),
            "design_manifest_sha256": _text(row.get("design_manifest_sha256")),
        })
    eligible = [row for row in evidence if _truth(row.get("risk_slope_estimand_eligible"))]
    return evidence, {
        "n_rows": len(evidence), "n_estimand_eligible": len(eligible),
        "support_workers": len({row["worker_id"] for row in eligible}),
        "support_tasks": len({row["base_task_id"] for row in eligible}),
        "evidence_stage": "C2B",
        "risk_model_scope": "C2B_CONFIRMATORY_CANONICAL_ONLY_FOR_C2A_RP",
    }


def _build_observed_support_audit(
    assignments: list[dict[str, Any]],
    canonical_rows: list[dict[str, Any]],
    evidence_rows: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Compare frozen planned support with observed estimand support per task."""
    planned: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in assignments:
        planned[_text(row.get("task_id"))].append(row)
    submitted = {
        (normalize_worker_id(row.get("worker_id", "")), _text(row.get("planned_task_id")))
        for row in canonical_rows
    }
    valid = {
        (normalize_worker_id(row.get("worker_id", "")), _text(row.get("planned_task_id")))
        for row in canonical_rows if _truth(row.get("canonical_valid"))
    }
    qgt_eligible = {
        (normalize_worker_id(row.get("worker_id", "")), _text(row.get("planned_task_id")))
        for row in evidence_rows
        if _truth(row.get("canonical_valid")) and _text(row.get("quality"))
    }
    risk_eligible = {
        (normalize_worker_id(row.get("worker_id", "")), _text(row.get("planned_task_id")))
        for row in evidence_rows if _truth(row.get("risk_slope_estimand_eligible"))
    }
    output: list[dict[str, Any]] = []
    for task_id, task_rows in sorted(planned.items()):
        workers = {normalize_worker_id(row.get("worker_id", "")) for row in task_rows}
        task_keys = {(worker, task_id) for worker in workers}
        submitted_count = len(task_keys & submitted)
        valid_count = len(task_keys & valid)
        risk_count = len(task_keys & risk_eligible)
        first = task_rows[0]
        output.append({
            "schema_version": "c2b_observed_support_audit_v1",
            "task_id": task_id,
            "base_task_id": _text(first.get("base_task_id")) or task_id,
            "c2_component": _text(first.get("c2_component")),
            "task_stratum": _text(first.get("task_stratum")),
            "planned_worker_support": len(workers),
            "submitted_worker_support": submitted_count,
            "canonical_valid_support": valid_count,
            "Q_GT_eligible_support": len(task_keys & qgt_eligible),
            "risk_slope_eligible_support": risk_count,
            "missing_worker_ids": ";".join(sorted(workers - {worker for worker, task in submitted if task == task_id})),
            "support_deficit": len(workers) - submitted_count,
            "peer_support_status": "observed" if valid_count >= 2 else "support_limited",
            "risk_model_support_status": "observed" if risk_count else "not_evaluable",
        })
    summary = {
        "schema_version": "c2b_observed_support_audit_v1",
        "task_count": len(output),
        "planned_worker_support_total": sum(row["planned_worker_support"] for row in output),
        "submitted_worker_support_total": sum(row["submitted_worker_support"] for row in output),
        "canonical_valid_support_total": sum(row["canonical_valid_support"] for row in output),
        "risk_slope_eligible_support_total": sum(row["risk_slope_eligible_support"] for row in output),
        "zero_submitted_support_task_count": sum(row["submitted_worker_support"] == 0 for row in output),
        "one_submitted_support_task_count": sum(row["submitted_worker_support"] == 1 for row in output),
        "support_deficit_task_count": sum(row["support_deficit"] > 0 for row in output),
    }
    return output, summary


def _merge_post_profile(
    profile_path: Path,
    evidence: list[dict[str, Any]],
    *,
    output_path: Path,
) -> tuple[dict[str, Any], list[dict[str, str]]]:
    rows = _read_csv(profile_path)
    if not rows:
        raise ValueError("C1 worker_profile_v2 is empty")
    if any(_text(row.get("schema_version")) != "worker_profile_v2" for row in rows):
        raise ValueError("post-C2 profile requires worker_profile_v2 input")
    if any("global_policy_eligible" not in row or not _text(row.get("global_policy_eligible")) for row in rows):
        raise ValueError("post-C2 profile requires explicit global_policy_eligible")
    eligible = [row for row in evidence if _truth(row.get("risk_slope_estimand_eligible"))]
    records = [
        {"worker_id": row["worker_id"], "base_task_id": row["base_task_id"], "building_id": row["building_id"], "risk": float(row["risk"]), "quality": float(row["quality"])}
        for row in eligible
    ]
    fit = _fit_crossed_model(records)
    by_worker: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in eligible:
        by_worker[row["worker_id"]].append(row)
    slopes = fit.get("worker_slopes", {}) if fit.get("status") == "estimated" else {}
    ses = fit.get("worker_slope_ses", {}) if fit.get("status") == "estimated" else {}
    group_se = float(fit.get("group_slope_se", math.nan)) if fit.get("status") == "estimated" else math.nan
    between = float(fit.get("between_worker_slope_sd", math.nan)) if fit.get("status") == "estimated" else math.nan
    for row in rows:
        worker = normalize_worker_id(row.get("worker_id", ""))
        support_rows = by_worker.get(worker, [])
        worker_slope = float(slopes.get(worker, math.nan)) if worker in slopes else math.nan
        worker_se = float(ses.get(worker, math.nan)) if worker in ses else math.nan
        estimated = bool(support_rows) and math.isfinite(worker_slope) and math.isfinite(worker_se)
        unified_sd = max((value for value in (worker_se, group_se, between) if estimated and math.isfinite(value)), default=math.nan)
        status = "estimated_crossed_model" if estimated else ("support_limited" if support_rows else "not_evaluable")
        row.update({
            "schema_version": "worker_profile_v2",
            "worker_id": worker,
            "risk_slope": worker_slope if estimated else "",
            "risk_slope_for_simulation": worker_slope if estimated else "",
            "risk_slope_se": worker_se if estimated else "",
            "risk_slope_ci_half_width": "" if not math.isfinite(unified_sd) else 1.96 * unified_sd,
            "risk_slope_support": len(support_rows),
            "observed_risk_slope_support": len(support_rows),
            "ordinary_support_observed": sum(_text(item.get("task_stratum")) == "ordinary" for item in support_rows),
            "stress_support_observed": sum(_text(item.get("task_stratum")) == "stress" for item in support_rows),
            "risk_slope_status": status,
            "c1_risk_slope_status": "estimated_from_C2B" if estimated else status,
            "support": len(support_rows),
            "ci_half_width": "" if not math.isfinite(unified_sd) else 1.96 * unified_sd,
            "risk_model_scope": "C2B_CONFIRMATORY_CANONICAL_ONLY_FOR_C2A_RP",
            "profile_purpose": "post_c2b_c2a_rp_input",
        })
    _write_csv(output_path, rows)
    return fit, rows


def _profile_manifest(
    output_path: Path,
    profile_path: Path,
    *,
    input_paths: dict[str, Path],
    profile_rows: list[dict[str, str]],
) -> dict[str, Any]:
    input_sha = {name: _sha(path) for name, path in input_paths.items()}
    profile_versions = {_text(row.get("profile_version")) for row in profile_rows if _text(row.get("profile_version"))}
    cohorts = {_text(row.get("cohort_id")) for row in profile_rows if _text(row.get("cohort_id"))}
    payload = {
        "manifest_version": "c2b_post_profile_v1",
        "artifact_role": "C2B_POST_PROFILE_MANIFEST",
        "contract_role": "generated_subordinate",
        **_method_identity(),
        "profile_version": next(iter(profile_versions), "post_c2b_worker_profile_v2"),
        "cohort_id": next(iter(cohorts), "calibration"),
        "input_sha256": input_sha,
        "output_sha256": {"post_c2b_worker_profile_csv": _sha(profile_path)},
        "post_c2b_worker_profile_path": str(profile_path.resolve()),
        "post_c2b_worker_profile_sha256": _sha(profile_path),
        "risk_model_scope": "C2B_CONFIRMATORY_CANONICAL_ONLY_FOR_C2A_RP",
        "profile_purpose": "post_c2b_c2a_rp_input",
        "frozen": True,
    }
    _write_json(output_path, payload)
    return payload


def _package_c2a_rp(
    c2a_dir: Path,
    assignment_path: Path,
    task_pool_path: Path,
    deployments: dict[str, dict[str, Any]],
    worker_to_deployment: dict[str, str],
    *,
    block_index: int,
    c2a_summary_path: Path,
    model_layout_dir: Path | None = None,
) -> dict[str, Any]:
    assignments = _read_csv(assignment_path)
    tasks = _load_task_index(task_pool_path)
    c2a_summary = json.loads(c2a_summary_path.read_text(encoding="utf-8"))
    plan_path = c2a_summary_path.parent / "precision_plan_C2A_RP.csv"
    full_assignment_path = c2a_summary_path.parent / "assignment_manifest_C2A_RP.csv"
    if not plan_path.is_file() or not full_assignment_path.is_file():
        raise ValueError("C2-A-RP planner outputs are incomplete")
    identity = {
        **_method_identity(),
        "design_manifest_sha256": _text(c2a_summary.get("design_manifest_sha256")),
        "c2b_summary_sha256": _text(c2a_summary.get("c2b_summary_sha256")),
        "post_c2b_worker_profile_sha256": _text(c2a_summary.get("worker_profile_sha256")),
        "threshold_manifest_sha256": _text(c2a_summary.get("threshold_manifest_sha256")),
        "c2a_precision_plan_sha256": _sha(plan_path),
        "c2a_assignment_manifest_sha256": _sha(full_assignment_path),
        "c2a_block_assignment_sha256": _sha(assignment_path),
        "c2a_task_pool_sha256": _sha(task_pool_path),
    }
    if any(not value for key, value in identity.items() if key.endswith("sha256")):
        raise ValueError("C2-A-RP operational package has incomplete identity hashes")
    seen = set()
    selected_assignments: list[dict[str, str]] = []
    for row in assignments:
        key = (normalize_worker_id(row.get("worker_id", "")), _text(row.get("task_id")))
        if not all(key) or key in seen:
            raise ValueError("C2-A-RP assignment has empty or duplicate worker-task identity")
        seen.add(key)
        if _text(row.get("round_id")) != "C2-A-RP" or int(float(row.get("block_index", 0) or 0)) < 1:
            raise ValueError("C2-A-RP assignment block identity is invalid")
        if _text(row.get("target_component")) != "risk_slope":
            raise ValueError("C2-A-RP operational package cannot dispatch a diagnostic target")
        if _text(row.get("task_id")) not in tasks:
            raise ValueError(f"C2-A-RP task is outside the frozen task pool:{row.get('task_id')}")
        if int(float(row.get("block_index", 0) or 0)) == block_index:
            selected_assignments.append(row)
    c2a_dir.mkdir(parents=True, exist_ok=True)
    imports_dir = c2a_dir / "imports"
    private_dir = c2a_dir / "private_lists"
    imports_dir.mkdir()
    private_dir.mkdir()
    mapping_rows: list[dict[str, Any]] = []
    import_outputs: dict[str, dict[str, Any]] = {}
    by_deployment: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in selected_assignments:
        worker = normalize_worker_id(row.get("worker_id", ""))
        deployment_id = worker_to_deployment.get(worker)
        if deployment_id not in deployments:
            raise ValueError(f"C2-A-RP worker has no deployment:{worker}")
        by_deployment[deployment_id].append(row)
    for deployment_id, deployment in deployments.items():
        task_payloads: dict[str, dict[str, Any]] = {}
        for row in by_deployment.get(deployment_id, []):
            worker = normalize_worker_id(row.get("worker_id", ""))
            task_id = _text(row.get("task_id"))
            task = tasks[task_id]
            image = _text(task.get("image") or task.get("image_path") or task.get("vis_3d"))
            if not image:
                raise ValueError(f"C2-A-RP task lacks an image URL:{task_id}")
            image = image.replace("/valid_no_occ/img/", "/img_v/")
            if image.endswith(".png"):
                image = image[:-4] + ".jpg"
            viewer = _text(task.get("vis_3d"))
            model_layout_sha256 = ""
            if model_layout_dir is not None:
                layout_path = model_layout_dir / f"{_text(task.get('base_task_id')) or task_id}.json"
                if not layout_path.is_file():
                    raise ValueError(f"C2-A-RP task lacks frozen model layout JSON:{task_id}")
                layout = json.loads(layout_path.read_text(encoding="utf-8"))
                corners = layout.get("layout", {}).get("corners", [])
                if not corners:
                    raise ValueError(f"C2-A-RP task has an empty frozen model layout:{task_id}")
                points = [{key: corner[key] for key in ("x", "y_ceiling", "y_floor")} for corner in corners]
                viewer = f"{str(deployment['server_url']).rstrip('/')}/tools/vis_3d.html?w=1024&h=512&data={quote(json.dumps(points, separators=(',', ':')))}"
                model_layout_sha256 = _sha(layout_path)
            data = {
                **identity,
                "image": image,
                "title": Path(image).name,
                "dataset_group": "C2-A-RP",
                "condition": "manual",
                "planned_task_id": task_id,
                "task_id": task_id,
                "base_task_id": _text(row.get("base_task_id")) or _text(task.get("base_task_id")) or task_id,
                "round_id": "C2-A-RP",
                "block_index": block_index,
                "task_stratum": _text(row.get("task_stratum")),
                "target_component": _text(row.get("target_component")),
                "gap_reason": _text(row.get("gap_reason")),
                "deployment_id": deployment_id,
                "language_group": deployment["language_group"],
                "server_instance_id": deployment["server_instance_id"],
                "server_url": deployment["server_url"],
                "project_id": deployment["project_id"],
                "vis_3d": viewer,
            }
            if model_layout_sha256:
                data["model_layout_sha256"] = model_layout_sha256
            if _text(task.get("image_id")):
                data["image_id"] = task["image_id"]
            task_payloads.setdefault(task_id, {"data": data})
            mapping_rows.append({
                **identity,
                "round_id": "C2-A-RP", "block_index": block_index, "worker_id": worker,
                "deployment_id": deployment_id, "language_group": deployment["language_group"],
                "server_instance_id": deployment["server_instance_id"], "server_url": deployment["server_url"],
                "project_id": deployment["project_id"], "planned_task_id": task_id,
                "runtime_task_id": "", "runtime_binding_status": "pending_manual_runtime_binding",
                "target_component": _text(row.get("target_component")),
            })
        import_path = imports_dir / f"c2a_rp_block_{block_index}_{deployment_id}.json"
        payload = list(task_payloads.values())
        _write_json(import_path, payload)
        import_outputs[deployment_id] = {
            **{key: deployment[key] for key in ("deployment_id", "language_group", "server_instance_id", "server_url", "project_id")},
            "planned_import_path": str(import_path.resolve()), "planned_import_sha256": _sha(import_path), "task_count": len(payload),
        }
    for worker in sorted(worker_to_deployment):
        path = private_dir / f"worker_{worker}_C2A_RP_block_{block_index}.csv"
        _write_csv(path, [row for row in selected_assignments if normalize_worker_id(row.get("worker_id", "")) == worker])
    mapping_path = c2a_dir / "c2a_rp_runtime_mapping.csv"
    _write_csv(mapping_path, mapping_rows)
    return {
        "schema_version": "c2a_rp_operational_package_v1",
        "round_id": "C2-A-RP", "block_index": block_index,
        **identity,
        "assignment_sha256": _sha(assignment_path), "task_pool_sha256": _sha(task_pool_path),
        "append_only": {
            "mode": _text(c2a_summary.get("dispatch_mode")) or "planned",
            "block_index": block_index,
            "block_assignment_sha256": _sha(assignment_path),
            "full_assignment_manifest_sha256": _sha(full_assignment_path),
            "prior_assignment_manifest_sha256": _text(c2a_summary.get("existing_assignment_manifest_sha256")),
        },
        "deployments": import_outputs, "runtime_mapping_path": str(mapping_path.resolve()), "runtime_mapping_sha256": _sha(mapping_path),
        "assignment_count": len(selected_assignments), "private_list_worker_count": len(worker_to_deployment),
    }


def _resolve_exports(
    deployments: dict[str, dict[str, Any]],
    *,
    zh_export: Path | None,
    foreign_export: Path | None,
    explicit: dict[str, Path],
) -> dict[str, Path]:
    result = dict(explicit)
    for language, path in (("zh", zh_export), ("foreign", foreign_export)):
        if path is None:
            continue
        matches = [deployment_id for deployment_id, item in deployments.items() if item["language_token"] == language]
        if len(matches) != 1:
            raise ValueError(f"cannot resolve {language} export to one deployment")
        if matches[0] in result:
            raise ValueError(f"duplicate export binding:{matches[0]}")
        result[matches[0]] = path
    if set(result) != set(deployments):
        raise ValueError("C2-B chain requires exactly one export per deployment")
    if any(not path.is_file() for path in result.values()):
        raise ValueError("C2-B export input is missing")
    return result


def _resolve_active_logs(
    deployments: dict[str, dict[str, Any]],
    *,
    shared: Path | None,
    explicit: dict[str, Path],
) -> dict[str, Path | None]:
    result = dict(explicit)
    unknown = set(result) - set(deployments)
    if unknown:
        raise ValueError("active log binding has unknown deployments:" + ",".join(sorted(unknown)))
    for deployment_id in deployments:
        if deployment_id not in result and shared is not None:
            result[deployment_id] = shared
        if deployment_id not in result:
            result[deployment_id] = None
        if result[deployment_id] is not None and not result[deployment_id].exists():
            raise ValueError(f"active log input is missing:{result[deployment_id]}")
    return result


def run_chain(
    *,
    zh_export: Path | None,
    foreign_export: Path | None,
    exports: dict[str, Path] | None,
    active_log: Path | None,
    deployment_active_logs: dict[str, Path] | None,
    assignment: Path,
    deployment_manifest: Path,
    launch_report: Path,
    runtime_mapping: Path,
    private_assignment_audit: Path,
    worker_profile: Path,
    design_summary: Path,
    c1_snapshot: Path,
    worker_roster: Path,
    rule_config: Path,
    task_eligibility: Path,
    reference_registry: Path,
    c2a_design_manifest: Path,
    threshold_manifest: Path,
    c2a_task_pool: Path,
    output_dir: Path,
    input_status: str = "precloseout_rehearsal",
    assignment_history: Path | None = None,
    existing_assignment_manifest: Path | None = None,
    dispatch_state: Path | None = None,
    dispatch_block_index: int | None = None,
    terminal_disposition: Path | None = None,
    reference_conflict_review_record: Path | None = None,
    scope_disposition: Path | None = None,
    model_layout_dir: Path | None = None,
) -> dict[str, Any]:
    if input_status not in FORMAL_MODES:
        raise ValueError(f"unsupported input_status:{input_status}")
    if input_status == "formal" and reference_conflict_review_record is None:
        raise ValueError("formal C2-B chain requires reference_conflict_review_record")
    if model_layout_dir is not None and not model_layout_dir.is_dir():
        raise ValueError(f"missing C2-A-RP model layout directory:{model_layout_dir}")
    source_paths = [assignment, deployment_manifest, launch_report, runtime_mapping, private_assignment_audit, worker_profile, design_summary, c1_snapshot, worker_roster, rule_config, task_eligibility, reference_registry, c2a_design_manifest, threshold_manifest, c2a_task_pool]
    if reference_conflict_review_record is not None:
        source_paths.append(reference_conflict_review_record)
    if scope_disposition is not None:
        source_paths.append(scope_disposition)
    if any(not path.is_file() for path in source_paths):
        missing = [str(path) for path in source_paths if not path.is_file()]
        raise ValueError("missing chain input:" + ",".join(missing))
    if output_dir.exists():
        raise ValueError(f"chain output directory already exists:{output_dir}")
    assignment_rows = _read_csv(assignment)
    assigned_ids, task_ids, workers = _validate_assignment_identity(assignment, assignment_rows)
    assignment_by_id = {(normalize_worker_id(row.get("worker_id", "")), _text(row.get("task_id"))): row for row in assignment_rows}
    deployments, worker_to_deployment = _load_deployments(deployment_manifest, assignment_rows)
    launch = _validate_launch_report(launch_report, assignment, deployments, allow_rehearsal=input_status != "formal")
    mapping_path, runtime_audit = _runtime_mapping_path(runtime_mapping)
    mapping_rows = _load_runtime_mapping(mapping_path)
    if len(mapping_rows) != len(assigned_ids):
        raise ValueError("frozen runtime mapping row count does not match D8 assignment")
    for row in mapping_rows:
        deployment_id = _text(row.get("deployment_id"))
        worker = normalize_worker_id(row.get("worker_id", ""))
        deployment = deployments.get(deployment_id)
        if deployment is None or worker_to_deployment.get(worker) != deployment_id:
            raise ValueError("frozen runtime mapping has an unknown deployment or worker")
        if _text(row.get("project_id")) != _text(deployment.get("project_id")):
            raise ValueError("frozen runtime mapping project identity disagrees with deployment manifest")
        if _text(row.get("server_instance_id")) != _text(deployment.get("server_instance_id")):
            raise ValueError("frozen runtime mapping server identity disagrees with deployment manifest")
        if _text(row.get("language_group")) and _language_token(row.get("language_group")) != deployment.get("language_token"):
            raise ValueError("frozen runtime mapping language identity disagrees with deployment manifest")
    mapping_ids = {(normalize_worker_id(row.get("worker_id", "")), _text(row.get("planned_task_id"))) for row in mapping_rows}
    if mapping_ids != assigned_ids:
        raise ValueError("frozen runtime mapping does not cover exactly D8 assignment")
    if runtime_audit is not None and runtime_audit.get("assignment_batch_id") not in {None, "", "C2B_BATCH_A"}:
        raise ValueError("runtime mapping audit has the wrong batch")
    export_paths = _resolve_exports(deployments, zh_export=zh_export, foreign_export=foreign_export, explicit=exports or {})
    active_paths = _resolve_active_logs(deployments, shared=active_log, explicit=deployment_active_logs or {})
    optional_inputs = {
        "assignment_history": assignment_history,
        "existing_assignment_manifest": existing_assignment_manifest,
        "dispatch_state": dispatch_state,
        "terminal_disposition": terminal_disposition,
    }
    missing_optional = [str(path) for path in optional_inputs.values() if path is not None and not path.is_file()]
    if missing_optional:
        raise ValueError("missing optional chain input:" + ",".join(missing_optional))
    chain_input_paths: dict[str, Path] = {
        "assignment": assignment,
        "deployment_manifest": deployment_manifest,
        "launch_report": launch_report,
        "runtime_mapping": runtime_mapping,
        "runtime_mapping_resolved": mapping_path,
        "private_assignment_audit": private_assignment_audit,
        "worker_profile": worker_profile,
        "design_summary": design_summary,
        "c1_snapshot": c1_snapshot,
        "worker_roster": worker_roster,
        "rule_config": rule_config,
        "task_eligibility": task_eligibility,
        "reference_registry": reference_registry,
        "c2a_design_manifest": c2a_design_manifest,
        "threshold_manifest": threshold_manifest,
        "c2a_task_pool": c2a_task_pool,
    }
    if reference_conflict_review_record is not None:
        chain_input_paths["reference_conflict_review_record"] = reference_conflict_review_record
    if scope_disposition is not None:
        chain_input_paths["scope_disposition"] = scope_disposition
    chain_input_paths.update({f"export:{deployment_id}": path for deployment_id, path in export_paths.items()})
    chain_input_paths.update({f"active_log:{deployment_id}": path for deployment_id, path in active_paths.items() if path is not None})
    chain_input_paths.update({name: path for name, path in optional_inputs.items() if path is not None})

    parent = output_dir.parent.resolve()
    parent.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix=f".{output_dir.name}.", dir=str(parent)))
    try:
        canonical, canonical_summary = _canonicalize_deployments(export_paths, active_paths, mapping_rows, assignment_by_id, deployments)
        canonical_path = staging / "c2b_canonical_submissions.csv"
        _write_csv(canonical_path, canonical)
        task_index = _load_task_index(task_eligibility)
        task_pool_shas = {_text(row.get("task_risk_sha256")) for row in task_index.values() if _text(row.get("task_risk_sha256"))}
        if len(task_pool_shas) != 1:
            raise ValueError("C2-B frozen task pool SHA is missing or inconsistent")
        task_pool_sha256 = next(iter(task_pool_shas))
        if not task_ids <= set(task_index):
            raise ValueError("D8 assignment contains a task outside the frozen C2-B task pool")
        reference_index = _load_reference_index(reference_registry)
        scope_index = _load_scope_index(scope_disposition)
        risk_evidence, risk_summary = _risk_slope_evidence(
            canonical, task_index, reference_index,
            reference_registry=reference_registry, scope_index=scope_index,
        )
        risk_path = staging / "c2b_canonical_risk_slope_evidence.csv"
        _write_csv(risk_path, risk_evidence)
        support_rows, support_summary = _build_observed_support_audit(assignment_rows, canonical, risk_evidence)
        support_path = staging / "c2b_observed_support_audit.csv"
        support_summary_path = staging / "c2b_observed_support_audit.summary.json"
        _write_csv(support_path, support_rows)
        _write_json(support_summary_path, support_summary)
        profile_path = staging / "post_c2b_worker_profile.csv"
        fit, profile_rows = _merge_post_profile(worker_profile, risk_evidence, output_path=profile_path)
        block_index = int(dispatch_block_index or 1)
        history_path = assignment_history
        if history_path is None:
            if block_index != 1:
                raise ValueError("C2-A-RP later dispatch requires an explicit assignment history")
            history_path = staging / "c2a_assignment_history_block_0.csv"
            _write_csv(history_path, [], fields=C2A_ASSIGNMENT_FIELDS)
        history_display_path = history_path if assignment_history is not None else output_dir / history_path.name
        bound_manifest_path = staging / "c2a_decision_manifest_bound.json"
        bound_manifest = _prepare_c2a_decision_manifest(
            c2a_design_manifest, profile_path, c2a_task_pool, history_path, threshold_manifest,
            bound_manifest_path,
            bound_input_paths={
                "worker_profile_csv": output_dir / profile_path.name,
                "c2a_task_pool_csv": c2a_task_pool,
                "assignment_history_csv": history_display_path,
                "threshold_manifest": threshold_manifest,
            },
        )
        input_bindings = {
            "c2b_submissions_csv": canonical_path,
            "c2b_design_summary": design_summary,
            "c1_a_snapshot": c1_snapshot,
            "c2b_assignment_csv": assignment,
            "worker_roster_csv": worker_roster,
            "rule_config": rule_config,
            "c2b_launch_report": launch_report,
            "c2b_runtime_mapping_audit": runtime_mapping,
            "c2b_private_assignment_audit": private_assignment_audit,
        }
        profile_manifest_path = staging / "c2b_post_profile_manifest.json"
        _profile_manifest(profile_manifest_path, profile_path, input_paths=input_bindings, profile_rows=profile_rows)
        _write_json(profile_manifest_path, _relocate_paths(json.loads(profile_manifest_path.read_text(encoding="utf-8")), staging, output_dir))

        closeout_path = staging / "c2b_closeout_v2.json"
        closeout = materialize_c2b_closeout(
            canonical_path, profile_path, profile_manifest_path, design_summary, c1_snapshot,
            assignment, worker_roster, rule_config, launch_report, runtime_mapping,
            private_assignment_audit, closeout_path, input_status=input_status,
            terminal_disposition_csv=terminal_disposition,
            reference_conflict_review_record=reference_conflict_review_record,
        )
        # Candidate closeout intentionally lacks formal fields in the shared
        # materializer.  Add only chain binding fields to the generated output;
        # this does not change the normative closeout implementation.
        closeout["schema_version"] = "c2b_closeout_v2"
        closeout["source_c2a_design_manifest_sha256"] = _sha(c2a_design_manifest)
        closeout["design_manifest_sha256"] = _sha(bound_manifest_path)
        closeout["c2a_decision_manifest_sha256"] = _sha(bound_manifest_path)
        closeout["c2b_submissions_sha256"] = _sha(canonical_path)
        closeout["post_c2b_worker_profile_sha256"] = _sha(profile_path)
        closeout["post_c2b_profile_manifest_sha256"] = _sha(profile_manifest_path)
        closeout["observed_support_audit_sha256"] = _sha(support_path)
        closeout["observed_support_audit_summary_sha256"] = _sha(support_summary_path)
        closeout["observed_support_summary"] = support_summary
        closeout["method_contract_sha256"] = _sha(METHOD_CONTRACT)
        closeout["task_pool_sha256"] = task_pool_sha256
        closeout.setdefault("dependencies", []).extend([
            {"role": "C2B_OBSERVED_SUPPORT_AUDIT", "path": str(support_path.resolve()), "sha256": _sha(support_path)},
            {"role": "C2B_OBSERVED_SUPPORT_AUDIT_SUMMARY", "path": str(support_summary_path.resolve()), "sha256": _sha(support_summary_path)},
        ])
        closeout["formal_ready"] = bool(input_status == "formal" and closeout.get("formal_ready"))
        closeout["candidate_only"] = not closeout["formal_ready"]
        closeout = _relocate_paths(closeout, staging, output_dir)
        _write_json(closeout_path, closeout)

        c2a_dir = staging / "c2a_rp"
        c2a_summary = materialize_c2a_rp(
            profile_path, bound_manifest_path, c2a_dir,
            c2b_summary=closeout_path, c2b_summary_sha256=_sha(closeout_path),
            task_pool_csv=c2a_task_pool, assignment_history_csv=history_path,
            existing_assignment_manifest_csv=existing_assignment_manifest,
            dispatch_state_json=dispatch_state,
            dispatch_block_index=dispatch_block_index if input_status == "formal" else block_index,
            threshold_manifest=threshold_manifest, input_status=input_status,
        )
        c2a_summary = _relocate_paths(
            json.loads((c2a_dir / "precision_plan_C2A_RP.summary.json").read_text(encoding="utf-8")), staging, output_dir,
        )
        _write_json(c2a_dir / "precision_plan_C2A_RP.summary.json", c2a_summary)
        c2a_assignment_path = c2a_dir / "assignment_manifest_C2A_RP.csv"
        block_index = int(c2a_summary.get("dispatch_block_index") or dispatch_block_index or 1)
        all_c2a_assignments = _read_csv(c2a_assignment_path)
        block_rows = [
            row for row in all_c2a_assignments
            if int(float(row.get("block_index", 0) or 0)) == block_index
        ]
        block_assignment_path = staging / f"assignment_manifest_C2A_RP_block_{block_index}.csv"
        _write_csv(block_assignment_path, block_rows, fields=list(all_c2a_assignments[0]) if all_c2a_assignments else None)
        package = _package_c2a_rp(
            staging / "c2a_rp_operational", block_assignment_path, c2a_task_pool,
            deployments, worker_to_deployment,
            block_index=block_index,
            c2a_summary_path=c2a_dir / "precision_plan_C2A_RP.summary.json",
            model_layout_dir=model_layout_dir,
        )
        package = _relocate_paths(package, staging, output_dir)
        input_sha256 = {name: _sha(path) for name, path in chain_input_paths.items()}
        for deployment_id, summary in canonical_summary.items():
            key = f"active_log:{deployment_id}"
            if key in input_sha256:
                input_sha256[key] = _text((summary.get("timing_provenance") or {}).get("source_aggregate_sha256"))
        result = {
            "schema_version": CHAIN_SCHEMA,
            "artifact_role": "C2B_TO_C2A_RP_CHAIN",
            "contract_role": "generated_subordinate",
            **_method_identity(),
            "input_status": input_status,
            "formal_ready": bool(input_status == "formal" and closeout.get("formal_ready") and c2a_summary.get("launch_ready")),
            "launch_ready": bool(input_status == "formal" and c2a_summary.get("launch_ready")),
            "operational_preview_ready": True,
            "selected_design_id": "D8",
            "assignment_sha256": _sha(assignment),
            "task_pool_sha256": task_pool_sha256,
            "assignment_count": len(assignment_rows),
            "task_count": len(task_ids),
            "worker_count": len(workers),
            "deployment_ids": sorted(deployments),
            "canonical_summary": canonical_summary,
            "timing_provenance": {deployment_id: summary.get("timing_provenance", {}) for deployment_id, summary in canonical_summary.items()},
            "risk_slope_summary": risk_summary,
            "observed_support_summary": support_summary,
            "risk_model_scope": "C2B_CONFIRMATORY_CANONICAL_ONLY_FOR_C2A_RP",
            "reference_conflict_review_closed": closeout.get("reference_conflict_review_closed", False),
            "risk_model": fit,
            "c2a_decision_manifest_sha256": _sha(bound_manifest_path),
            "source_c2a_design_manifest_sha256": _sha(c2a_design_manifest),
            "c2a_assignment_history_sha256": _sha(history_path),
            "c2a_decision_binding_map": bound_manifest["binding_map"],
            "outputs": {
                "canonical_submissions": str((output_dir / canonical_path.name).resolve()),
                "risk_slope_evidence": str((output_dir / risk_path.name).resolve()),
                "observed_support_audit": str((output_dir / support_path.name).resolve()),
                "observed_support_audit_summary": str((output_dir / support_summary_path.name).resolve()),
                "post_profile": str((output_dir / profile_path.name).resolve()),
                "post_profile_manifest": str((output_dir / profile_manifest_path.name).resolve()),
                "c2a_decision_manifest": str((output_dir / bound_manifest_path.name).resolve()),
                "c2a_assignment_history": str(history_display_path.resolve()),
                "c2b_closeout": str((output_dir / closeout_path.name).resolve()),
                "c2a_rp": str((output_dir / "c2a_rp").resolve()),
                "c2a_block_assignment": str((output_dir / block_assignment_path.name).resolve()),
                "c2a_operational_package": str((output_dir / "c2a_rp_operational").resolve()),
            },
            "c2a_rp_summary": c2a_summary,
            "c2a_operational_package": package,
            "input_sha256": input_sha256,
        }
        _write_json(staging / "c2b_c2a_rp_chain_manifest.json", _relocate_paths(result, staging, output_dir))
        staging.rename(output_dir)
        return result
    except Exception:
        shutil.rmtree(staging, ignore_errors=True)
        raise


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run the thin C2-B export to C2-A-RP chain.")
    parser.add_argument("--zh-export", type=Path)
    parser.add_argument("--foreign-export", type=Path)
    parser.add_argument("--export", action="append", default=[], metavar="DEPLOYMENT_ID=PATH")
    parser.add_argument("--active-log", type=Path)
    parser.add_argument("--deployment-active-log", action="append", default=[], metavar="DEPLOYMENT_ID=PATH")
    parser.add_argument("--assignment", type=Path, required=True)
    parser.add_argument("--deployment-manifest", type=Path, required=True)
    parser.add_argument("--launch-report", type=Path, required=True)
    parser.add_argument("--runtime-mapping", type=Path, required=True)
    parser.add_argument("--private-assignment-audit", type=Path, required=True)
    parser.add_argument("--worker-profile", type=Path, required=True)
    parser.add_argument("--design-summary", type=Path, required=True)
    parser.add_argument("--c1-snapshot", type=Path, required=True)
    parser.add_argument("--worker-roster", type=Path, required=True)
    parser.add_argument("--rule-config", type=Path, required=True)
    parser.add_argument("--task-eligibility", type=Path, required=True)
    parser.add_argument("--reference-registry", type=Path, required=True)
    parser.add_argument("--c2a-design-manifest", type=Path, required=True)
    parser.add_argument("--threshold-manifest", type=Path, required=True)
    parser.add_argument("--c2a-task-pool", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--input-status", choices=sorted(FORMAL_MODES), default="precloseout_rehearsal")
    parser.add_argument("--assignment-history", type=Path)
    parser.add_argument("--existing-assignment-manifest", type=Path)
    parser.add_argument("--dispatch-state", type=Path)
    parser.add_argument("--dispatch-block-index", type=int)
    parser.add_argument("--terminal-disposition", type=Path)
    parser.add_argument("--reference-conflict-review-record", type=Path)
    parser.add_argument("--scope-disposition", type=Path)
    parser.add_argument("--model-layout-dir", type=Path)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        result = run_chain(
            zh_export=args.zh_export, foreign_export=args.foreign_export, exports=_parse_bindings(args.export, option="--export"),
            active_log=args.active_log, deployment_active_logs=_parse_bindings(args.deployment_active_log, option="--deployment-active-log"),
            assignment=_path(args.assignment), deployment_manifest=_path(args.deployment_manifest), launch_report=_path(args.launch_report),
            runtime_mapping=_path(args.runtime_mapping), private_assignment_audit=_path(args.private_assignment_audit), worker_profile=_path(args.worker_profile),
            design_summary=_path(args.design_summary), c1_snapshot=_path(args.c1_snapshot), worker_roster=_path(args.worker_roster), rule_config=_path(args.rule_config),
            task_eligibility=_path(args.task_eligibility), reference_registry=_path(args.reference_registry), c2a_design_manifest=_path(args.c2a_design_manifest),
            threshold_manifest=_path(args.threshold_manifest), c2a_task_pool=_path(args.c2a_task_pool), output_dir=_path(args.output_dir),
            input_status=args.input_status, assignment_history=_path(args.assignment_history) if args.assignment_history else None,
            existing_assignment_manifest=_path(args.existing_assignment_manifest) if args.existing_assignment_manifest else None,
            dispatch_state=_path(args.dispatch_state) if args.dispatch_state else None, dispatch_block_index=args.dispatch_block_index,
            terminal_disposition=_path(args.terminal_disposition) if args.terminal_disposition else None,
            reference_conflict_review_record=_path(args.reference_conflict_review_record) if args.reference_conflict_review_record else None,
            scope_disposition=_path(args.scope_disposition) if args.scope_disposition else None,
            model_layout_dir=_path(args.model_layout_dir) if args.model_layout_dir else None,
        )
    except Exception as exc:
        print(json.dumps({"schema_version": CHAIN_SCHEMA, "formal_ready": False, "launch_ready": False, "reason_code": f"blocked:{type(exc).__name__}", "reason": str(exc)}, ensure_ascii=False, indent=2))
        return 2
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
