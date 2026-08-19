"""Build the independent post-Block-2 Prompt 1 analysis pack."""

from __future__ import annotations

import csv
import hashlib
import json
import math
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.thesis_main.analysis.geometry_cluster_v2 import cluster_geometry_records
from tools.thesis_main.analysis.geometry_consensus.representation import normalize_geometry
from tools.thesis_main.analysis.paper_a_contracts import load_method_contract


OUT = ROOT / "analysis_results" / "post_block2_analysis_pack_20260817_v2"
STAGES = ("P1", "C1", "C2-B", "C2A-RP-B1", "C2A-RP-B2")
EXPECTED_STAGE_COUNTS = {"P1": 1481, "C1": 780, "C2-B": 160, "C2A-RP-B1": 40, "C2A-RP-B2": 40}
NOT_IDENTIFIABLE = "not_identifiable"
NOT_APPLICABLE = "not_applicable"
SOURCE_ABSENT = "source_absent"


def rel(path: Path) -> str:
    try:
        return path.resolve().relative_to(ROOT.resolve()).as_posix()
    except ValueError:
        return str(path.resolve()).replace("\\", "/")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def source(path: Path, role: str) -> dict[str, str]:
    return {"role": role, "path": rel(path), "sha256": sha256(path)}


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as stream:
        return list(csv.DictReader(stream))


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    fields: list[str] = []
    seen: set[str] = set()
    for row in rows:
        for key in row:
            if key not in seen:
                seen.add(key)
                fields.append(key)
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def js(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def text(value: Any, default: str = NOT_IDENTIFIABLE) -> str:
    if value is None:
        return default
    if isinstance(value, str):
        return value.strip() or default
    return str(value)


def truthy(value: Any) -> bool:
    return str(value).strip().lower() in {"true", "1", "yes"}


def bind_authoritative_buildings(
    rows: list[dict[str, Any]],
    sources: dict[str, tuple[list[dict[str, Any]], str]],
) -> None:
    lookups: dict[str, tuple[dict[str, str], str]] = {}
    for stage, (source_rows, source_name) in sources.items():
        lookup: dict[str, str] = {}
        for source_row in source_rows:
            base = str(source_row.get("base_task_id") or "").strip()
            building = str(source_row.get("building_id") or "").strip()
            if not base or not building:
                continue
            if base in lookup and lookup[base] != building:
                raise ValueError(f"conflicting building_id for {stage}:{base}: {lookup[base]} != {building}")
            lookup[base] = building
        lookups[stage] = lookup, source_name

    for row in rows:
        lookup, source_name = lookups.get(str(row.get("stage")), ({}, "source_absent"))
        building = lookup.get(str(row.get("base_task_id") or "").strip(), "")
        row["building_id"] = building or NOT_IDENTIFIABLE
        row["building_id_source"] = source_name if building else "source_absent_not_identifiable"


def identified_building(row: dict[str, Any]) -> str:
    building = str(row.get("building_id") or "").strip()
    return "" if building in {"", NOT_IDENTIFIABLE, NOT_APPLICABLE} else building


def worker_building_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [{
        "worker_id": text(row.get("worker_id")),
        "stage": row["stage"],
        "building_id": identified_building(row),
        "task_count": 1,
        "source_artifact": text(row.get("source_artifact")),
        "source_sha256": text(row.get("source_sha256")),
    } for row in rows if identified_building(row)]


def building_support_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    groups: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        if building := identified_building(row):
            groups[(str(row.get("stage")), building)].append(row)
    return [{
        "stage": stage,
        "building_id": building,
        "support_count": len(group),
        "source_artifact": ";".join(sorted({text(row.get("source_artifact")) for row in group})),
        "source_sha256": ";".join(sorted({text(row.get("source_sha256")) for row in group})),
    } for (stage, building), group in sorted(groups.items())]


def finite(value: Any) -> bool:
    try:
        return math.isfinite(float(value))
    except (TypeError, ValueError):
        return False


def path_under(root: Path, filename: str) -> Path:
    matches = [
        path for path in root.rglob(filename)
        if "calibration_" not in path.parts and "legacy" not in path.parts
    ]
    if not matches:
        raise FileNotFoundError(f"required formal artifact not found: {root}/{filename}")
    matches.sort()
    return matches[0]


def parse_corners(result: list[dict[str, Any]]) -> list[list[float]]:
    corners: list[list[float]] = []
    for item in result:
        value = item.get("value") or {}
        labels = value.get("keypointlabels") or []
        if item.get("type") == "keypointlabels" and "Corner" in labels:
            corners.append([float(value["x"]) * 10.24, float(value["y"]) * 5.12])
    return corners


def geometry_hash(corners: list[list[float]]) -> str:
    return hashlib.sha256(js(corners).encode("utf-8")).hexdigest()


def find_c1_sources() -> dict[str, Path]:
    root = ROOT / "analysis_results" / "c1_formal_audit_20260802_v16_final"
    return {
        name: path_under(root, filename)
        for name, filename in {
            "geometry": "c1_canonical_geometry.jsonl",
            "pairwise": "geometry_pairwise_similarity_C1.csv",
            "crowd": "geometry_task_crowd_structure_C1.csv",
            "building_binding": "c1_task_building_binding.csv",
            "gt_evidence": "c1_gt_quality_evidence.csv",
            "gt_analysis": "c1_gt_quality_analysis.csv",
            "views_manifest": "c1_analysis_views_manifest.json",
            "evidence_freeze": "c1_evidence_freeze_manifest.json",
            "measurement_freeze": "c1_measurement_freeze_manifest.json",
            "dependency_manifest": "analysis_dependency_manifest.json",
            "raw_input_manifest": "raw_input_manifest.json",
        }.items()
    }


def load_c1_historical_binding(c1_sources: dict[str, Path], method_path: Path) -> dict[str, Any]:
    evidence = read_json(c1_sources["evidence_freeze"])
    measurement = read_json(c1_sources["measurement_freeze"])
    raw_input = read_json(c1_sources["raw_input_manifest"])
    dependency = read_json(c1_sources["dependency_manifest"])
    expected = {}
    for item in dependency.get("dependencies", []):
        path = str(item.get("path", "")).replace("\\", "/")
        if path.startswith("D:/Work/HOHONET/"):
            path = path[len("D:/Work/HOHONET/"):]
        expected[path] = item.get("sha256")
    producer_paths = {
        "rule_manifest": "docs/thesis_main/geometry_loo_candidate_rule_manifest_v1.json",
        "geometry_cluster": "tools/thesis_main/analysis/geometry_cluster_v2.py",
        "materializer": "tools/thesis_main/analysis/geometry_consensus/materialize.py",
        "pairwise": "tools/thesis_main/analysis/geometry_consensus/pairwise.py",
        "representation": "tools/thesis_main/analysis/geometry_consensus/representation.py",
        "medoid": "tools/thesis_main/analysis/geometry_consensus/medoid.py",
    }
    current_paths = {
        "method_contract": method_path,
        "rule_manifest": ROOT / producer_paths["rule_manifest"],
        "geometry_cluster": ROOT / producer_paths["geometry_cluster"],
        "materializer": ROOT / producer_paths["materializer"],
        "pairwise": ROOT / producer_paths["pairwise"],
        "representation": ROOT / producer_paths["representation"],
        "medoid": ROOT / producer_paths["medoid"],
    }
    expected_sha = {
        "method_contract": evidence.get("method_contract_sha256"),
        **{key: expected.get(path) for key, path in producer_paths.items()},
    }
    current_sha = {key: sha256(path) for key, path in current_paths.items()}
    checks = {key: bool(expected_sha.get(key) and expected_sha[key] == current_sha[key]) for key in expected_sha}
    missing = [key for key, ok in checks.items() if not ok]
    exact = not missing
    return {
        "status": "exact_historical_binding_available" if exact else "version-bound reconstruction_not_evaluable/source_absent",
        "exact_historical_binding_available": exact,
        "historical_method_contract_version": evidence.get("method_contract_version", NOT_IDENTIFIABLE),
        "historical_method_contract_sha256": evidence.get("method_contract_sha256", NOT_IDENTIFIABLE),
        "historical_git_commit_sha": evidence.get("git_commit_sha", raw_input.get("head", NOT_IDENTIFIABLE)),
        "historical_code_pipeline_sha256": raw_input.get("code_pipeline_sha256", NOT_IDENTIFIABLE),
        "historical_full_dependency_bundle_sha256": evidence.get("full_dependency_bundle_sha256", NOT_IDENTIFIABLE),
        "historical_rule_version": "geometry_loo_candidate_v2",
        "expected_sha": expected_sha,
        "current_sha": current_sha,
        "checks": checks,
        "unavailable_components": missing,
        "historical_rule_path": producer_paths["rule_manifest"],
        "historical_producer_paths": producer_paths,
        "evidence_freeze_manifest": source(c1_sources["evidence_freeze"], "C1_EVIDENCE_FREEZE_MANIFEST"),
        "measurement_freeze_manifest": source(c1_sources["measurement_freeze"], "C1_MEASUREMENT_FREEZE_MANIFEST"),
        "dependency_manifest": source(c1_sources["dependency_manifest"], "C1_ANALYSIS_DEPENDENCY_MANIFEST"),
        "raw_input_manifest": source(c1_sources["raw_input_manifest"], "C1_RAW_INPUT_MANIFEST"),
        "measurement_freeze_status": measurement.get("C1_MEASUREMENT_FROZEN", False),
    }


def load_c1_rows(path: Path) -> list[dict[str, Any]]:
    rows = []
    file_sha = sha256(path)
    for row in read_jsonl(path):
        corners = row.get("corners_px") or row.get("polygon_points_px") or []
        rows.append({
            "stage": "C1",
            "round_id": "C1",
            "project_id": text(row.get("project_id")),
            "task_id": text(row.get("task_id") or row.get("base_task_id")),
            "base_task_id": text(row.get("base_task_id")),
            "condition": text(row.get("condition")),
            "dataset_group": text(row.get("pool") or row.get("dataset_group")),
            "worker_id": text(row.get("worker_id")),
            "annotation_id": text(row.get("annotation_id")),
            "canonical_annotation_id": text(row.get("canonical_annotation_id") or row.get("annotation_id")),
            "canonical_geometry": js(corners),
            "corners_px": js(corners),
            "n_corners": len(corners),
            "geometry_hash": text(row.get("geometry_hash"), geometry_hash(corners)),
            "canonical_valid": text(row.get("validity_status")) == "valid",
            "canonicalization_status": "frozen_c1_canonical_geometry",
            "source_artifact": rel(path),
            "source_sha256": file_sha,
            "geometry_source": text(row.get("geometry_source")),
            "task_stratum": text(row.get("task_stratum") or row.get("pool")),
            "image_id": text(row.get("scene_id") or row.get("image_id")),
            "runtime_task_id": text(row.get("ls_runtime_task_id") or row.get("task_id")),
            "observed_status": "observed_canonical",
        })
    return rows


def load_canonical_rows(path: Path, stage: str) -> list[dict[str, Any]]:
    rows = []
    file_sha = sha256(path)
    for row in read_csv(path):
        raw_geometry = row.get("canonical_geometry") or row.get("ordered_geometry") or "[]"
        try:
            corners = json.loads(raw_geometry)
        except json.JSONDecodeError:
            corners = []
        worker = row.get("worker_id") or row.get("annotator_id")
        normalized = {
            "stage": stage,
            "round_id": stage,
            "project_id": text(row.get("project_id")),
            "task_id": text(row.get("task_id") or row.get("base_task_id")),
            "base_task_id": text(row.get("base_task_id") or row.get("task_id")),
            "condition": text(row.get("condition")),
            "dataset_group": text(row.get("dataset_group")),
            "worker_id": text(worker),
            "annotation_id": text(row.get("annotation_id")),
            "canonical_annotation_id": text(row.get("canonical_annotation_id") or row.get("annotation_id")),
            "canonical_geometry": js(corners),
            "corners_px": js(corners),
            "n_corners": text(row.get("n_corners"), str(len(corners))),
            "geometry_hash": text(row.get("geometry_hash"), geometry_hash(corners)),
            "canonical_valid": text(row.get("canonical_valid")).lower() in {"true", "1"},
            "canonicalization_status": "frozen_closeout_canonical_submission",
            "source_artifact": rel(path),
            "source_sha256": file_sha,
            "geometry_source": "frozen_closeout_canonical_submission",
            "task_stratum": text(row.get("task_stratum") or row.get("dataset_group")),
            "image_id": text(row.get("image_id")),
            "runtime_task_id": text(row.get("runtime_task_id") or row.get("task_id")),
            "observed_status": "observed_canonical",
        }
        for key, value in row.items():
            if key not in normalized and value not in (None, ""):
                normalized[f"upstream_{key}"] = value
        rows.append(normalized)
    return rows


def load_p1_rows(path: Path, scope_note: Path) -> list[dict[str, Any]]:
    rows = load_canonical_rows(path, "P1")
    file_sha = sha256(path)
    note_sha = sha256(scope_note)
    for row in rows:
        row.update({
            "round_id": "P1",
            "canonicalization_status": "frozen_p1_final_gold_v2",
            "source_artifact": rel(path),
            "source_sha256": file_sha,
            "gt_population_role": "test_or_prescreen",
            "gt_provenance_class": "public_source_with_partial_local_user_correction",
            "gt_user_correction_status": "partial_local_only",
            "gt_user_verification_scope": "not_full_population",
            "gt_source_artifact": rel(scope_note),
            "gt_source_sha256": note_sha,
            "gt_provenance_version": "RAW_DATA_AND_GROUND_TRUTH_SCOPE_NOTE_20260817",
        })
    return rows


def load_block2_rows(export_paths: list[Path]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    task_count = 0
    annotation_count = 0
    project_ids: set[str] = set()
    for export_path in export_paths:
        export_sha = sha256(export_path)
        payload = read_json(export_path)
        for task in payload:
            task_count += 1
            data = task.get("data") or {}
            project_id = text(task.get("project") or data.get("project_id"))
            project_ids.add(project_id)
            runtime_task_id = text(task.get("id") or data.get("task_id"))
            for annotation in task.get("annotations") or []:
                annotation_count += 1
                corners = parse_corners(annotation.get("result") or [])
                ann_id = text(annotation.get("id"))
                worker_id = text(annotation.get("completed_by"))
                rows.append({
                    "stage": "C2A-RP-B2",
                    "round_id": "C2A-RP-B2",
                    "project_id": project_id,
                    "task_id": text(data.get("planned_task_id") or data.get("task_id") or data.get("base_task_id") or runtime_task_id),
                    "base_task_id": text(data.get("base_task_id")),
                    "condition": text(data.get("condition")),
                    "dataset_group": text(data.get("dataset_group")),
                    "worker_id": worker_id,
                    "annotation_id": ann_id,
                    "canonical_annotation_id": f"block2-{project_id}-{ann_id}",
                    "canonical_geometry": js(corners),
                    "corners_px": js(corners),
                    "n_corners": len(corners),
                    "geometry_hash": geometry_hash(corners),
                    "canonical_valid": bool(corners),
                    "canonicalization_status": "observed_raw_export_rebuilt",
                    "source_artifact": rel(export_path),
                    "source_sha256": export_sha,
                    "geometry_source": "raw_label_studio_export_keypointlabels",
                    "task_stratum": text(data.get("task_stratum")),
                    "image_id": text(data.get("image_id")),
                    "runtime_task_id": runtime_task_id,
                    "planned_task_id": text(data.get("planned_task_id")),
                    "deployment_id": text(data.get("deployment_id")),
                    "server_instance_id": text(data.get("server_instance_id")),
                    "method_contract_version": text(data.get("method_contract_version")),
                    "method_contract_sha256": text(data.get("method_contract_sha256")),
                    "c2a_assignment_manifest_sha256": text(data.get("c2a_assignment_manifest_sha256")),
                    "c2a_block_assignment_sha256": text(data.get("c2a_block_assignment_sha256")),
                    "annotation_lead_time_seconds": text(annotation.get("lead_time")),
                    "observed_status": "observed_annotation",
                    "gt_population_role": "validation",
                    "gt_provenance_class": "mp3d_hohonet_source_no_researcher_correction",
                    "gt_user_correction_status": "none",
                    "gt_user_verification_scope": "none",
                    "gt_source_artifact": rel(ROOT / "export_label" / "RAW_DATA_AND_GROUND_TRUTH_SCOPE_NOTE_20260817.md"),
                    "gt_source_sha256": sha256(ROOT / "export_label" / "RAW_DATA_AND_GROUND_TRUTH_SCOPE_NOTE_20260817.md"),
                    "gt_provenance_version": "RAW_DATA_AND_GROUND_TRUTH_SCOPE_NOTE_20260817",
                })
    return rows, {
        "runtime_task_count": task_count,
        "annotation_count": annotation_count,
        "project_ids": sorted(project_ids),
        "export_count": len(export_paths),
    }


def active_time_block2(rows: list[dict[str, Any]], active_dir: Path) -> list[dict[str, Any]]:
    manifest_path = active_dir / "ACTIVE_TIME_FREEZE_MANIFEST.json"
    manifest = read_json(manifest_path)
    jsonl_paths = sorted(active_dir.glob("*.jsonl"))
    manifest_files = manifest.get("files") or {}
    manifest_checks: list[dict[str, Any]] = []
    events: list[dict[str, Any]] = []
    for path in jsonl_paths:
        actual = sha256(path)
        declared = ""
        for key, value in manifest_files.items():
            if Path(str(key)).name == path.name:
                declared = str(value.get("sha256") if isinstance(value, dict) else value)
                break
        manifest_checks.append({"file": rel(path), "declared_sha256": text(declared), "observed_sha256": actual, "match": bool(declared and declared == actual)})
        events.extend(read_jsonl(path))
    target = {(text(row["project_id"]), text(row["runtime_task_id"]), text(row["worker_id"])) for row in rows}
    grouped: dict[tuple[str, str, str], list[dict[str, Any]]] = defaultdict(list)
    for event in events:
        key = (text(event.get("project_id")), text(event.get("task_id")), text(event.get("annotator_id")))
        if key in target:
            grouped[key].append(event)
    result: dict[tuple[str, str, str], dict[str, Any]] = {}
    for key, event_rows in grouped.items():
        by_session: dict[str, list[float]] = defaultdict(list)
        owner_valid = True
        page_gate = "not_present"
        mismatch = False
        scripts: set[str] = set()
        for event in event_rows:
            session = text(event.get("session_id"), "__single_session__")
            if finite(event.get("active_seconds")):
                by_session[session].append(float(event["active_seconds"]))
            scripts.add(text(event.get("script_version")))
            if "page_gate_eligible" in event:
                page_gate = "true" if truthy(event.get("page_gate_eligible")) else "false"
                owner_valid = owner_valid and truthy(event.get("page_gate_eligible"))
            mismatch = mismatch or truthy(event.get("store_mismatch_present"))
        total = sum(max(values) for values in by_session.values() if values)
        status = "owner_valid" if owner_valid and not mismatch and total > 0 else "not_owner_valid"
        result[key] = {
            "active_time_seconds": total if total > 0 else NOT_IDENTIFIABLE,
            "active_time_status": status,
            "active_time_event_count": len(event_rows),
            "active_time_session_count": len(by_session),
            "active_time_script_version": ";".join(sorted(scripts)) or NOT_IDENTIFIABLE,
            "active_time_page_gate_status": page_gate,
            "active_time_store_mismatch": "true" if mismatch else "false",
            "active_time_source_artifact": rel(active_dir),
            "active_time_source_sha256": sha256(manifest_path),
        }
    for row in rows:
        key = (text(row["project_id"]), text(row["runtime_task_id"]), text(row["worker_id"]))
        row.update(result.get(key, {
            "active_time_seconds": NOT_IDENTIFIABLE,
            "active_time_status": "missing_owner_valid_event",
            "active_time_event_count": 0,
            "active_time_session_count": 0,
            "active_time_script_version": NOT_IDENTIFIABLE,
            "active_time_page_gate_status": "not_identifiable",
            "active_time_store_mismatch": "not_identifiable",
            "active_time_source_artifact": rel(active_dir),
            "active_time_source_sha256": sha256(manifest_path),
        }))
    return manifest_checks


def reconcile_block2(assignments: list[dict[str, str]], observed: list[dict[str, Any]]) -> list[dict[str, Any]]:
    reconciled = []
    for assignment in assignments:
        aid = text(assignment.get("worker_id"))
        atask = text(assignment.get("task_id"))
        abase = text(assignment.get("base_task_id"))
        candidates = [
            row for row in observed
            if text(row.get("worker_id")) == aid
            and text(row.get("base_task_id")) == abase
            and atask in {
                text(row.get("task_id")),
                text(row.get("planned_task_id")),
                text(row.get("runtime_task_id")),
                text(row.get("base_task_id")),
            }
        ]
        exact = candidates[0] if len(candidates) == 1 else None
        reconciled.append({
            **assignment,
            "observed_runtime_task_id": text(exact.get("runtime_task_id")) if exact else NOT_IDENTIFIABLE,
            "observed_project_id": text(exact.get("project_id")) if exact else NOT_IDENTIFIABLE,
            "observed_deployment_id": text(exact.get("deployment_id")) if exact else NOT_IDENTIFIABLE,
            "observed_annotation_id": text(exact.get("annotation_id")) if exact else NOT_IDENTIFIABLE,
            "observed_worker_id": text(exact.get("worker_id")) if exact else NOT_IDENTIFIABLE,
            "observed_base_task_id": text(exact.get("base_task_id")) if exact else NOT_IDENTIFIABLE,
            "reconciliation_status": "exact_observed_match" if exact else "P0_assignment_observed_mapping_mismatch",
            "observed_source_artifact": text(exact.get("source_artifact")) if exact else NOT_IDENTIFIABLE,
            "observed_source_sha256": text(exact.get("source_sha256")) if exact else NOT_IDENTIFIABLE,
            "stale_runtime_mapping_used": "false",
        })
    observed_keys = {(text(row["worker_id"]), text(row["base_task_id"]), text(row["annotation_id"])) for row in observed}
    matched_keys = {
        (text(row.get("observed_worker_id")), text(row.get("observed_base_task_id")), text(row.get("observed_annotation_id")))
        for row in reconciled if row["reconciliation_status"] == "exact_observed_match"
    }
    if observed_keys != matched_keys:
        for row in reconciled:
            if row["reconciliation_status"] == "exact_observed_match":
                row["reconciliation_status"] = "P0_assignment_observed_mapping_set_mismatch"
    return reconciled


def build_geometry_record(row: dict[str, Any]) -> dict[str, Any]:
    try:
        corners = json.loads(row.get("corners_px") or row.get("canonical_geometry") or "[]")
    except json.JSONDecodeError:
        corners = []
    geometry = normalize_geometry(corners, width=1024, height=512)
    return {
        **row,
        "geometry": geometry,
        "_geometry": geometry,
        "canonical_annotation_id": text(row.get("canonical_annotation_id") or row.get("annotation_id")),
        "annotation_id": text(row.get("annotation_id")),
    }


def build_consensus(
    rows: list[dict[str, Any]],
    c1_crowd_path: Path,
    method: dict[str, Any],
    producer_sha: str,
    historical_binding: dict[str, Any],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    try:
        rule_path = ROOT / "docs" / "thesis_main" / "geometry_peer_candidate_rule_manifest_v1.json"
        rule = read_json(rule_path)
        cutoff = float((rule.get("thresholds") or {}).get("similarity_cutoff", method["geometry_cluster"]["similarity_cutoff"]))
        grid = int((rule.get("thresholds") or {}).get("boundary_grid", method["geometry_cluster"]["boundary_grid"]))
    except (FileNotFoundError, KeyError, TypeError, ValueError):
        rule_path = ROOT / "docs" / "thesis_main" / "geometry_cluster_v2.json"
        cutoff = float(method["geometry_cluster"]["similarity_cutoff"])
        grid = int(method["geometry_cluster"]["boundary_grid"])
    c1_sidecar = {(text(row.get("base_task_id")), text(row.get("condition"))): row for row in read_csv(c1_crowd_path)}
    grouped: dict[tuple[str, str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        if row["stage"] != "P1":
            grouped[(text(row["stage"]), text(row["base_task_id"]), text(row["condition"]))].append(build_geometry_record(row))
    consensus_rows: list[dict[str, Any]] = []
    consistency_rows: list[dict[str, Any]] = []
    params = {
        "min_q_boundary": cutoff,
        "min_q_wallwall": cutoff,
        "boundary_grid": grid,
        "minimum_valid_k": int(method["geometry_cluster"]["minimum_valid_k"]),
        "maximum_partition_count": int(method["geometry_cluster"]["maximum_partition_count"]),
        "maximum_search_nodes": int(method["geometry_cluster"]["maximum_search_nodes"]),
        "implementation": "tools/thesis_main/analysis/geometry_cluster_v2.py::cluster_geometry_records",
        "materializer_contract": "tools/thesis_main/analysis/geometry_consensus/materialize.py",
        "schema": "docs/thesis_main/geometry_cluster_v2.json",
    }
    for (stage, base_task_id, condition), records in sorted(grouped.items()):
        frozen = c1_sidecar.get((base_task_id, condition)) if stage == "C1" else None
        version_bound_c1 = stage == "C1" and not historical_binding["exact_historical_binding_available"]
        if version_bound_c1:
            result = {
                "schema_version": "geometry_cluster_v2",
                "base_task_id": base_task_id,
                "condition": condition,
                "valid_k": text(frozen.get("valid_k")) if frozen else len(records),
                "partition_status": text(frozen.get("partition_status")) if frozen else "not_evaluable",
                "cluster_membership_json": text(frozen.get("cluster_membership_json")) if frozen else NOT_IDENTIFIABLE,
                "ambiguity_candidates_json": text(frozen.get("ambiguity_candidates_json")) if frozen else NOT_IDENTIFIABLE,
                "cluster_count": text(frozen.get("cluster_count")) if frozen else NOT_IDENTIFIABLE,
                "largest_cluster_support": text(frozen.get("largest_cluster_support")) if frozen else NOT_IDENTIFIABLE,
                "second_cluster_support": text(frozen.get("second_cluster_support")) if frozen else NOT_IDENTIFIABLE,
                "largest_cluster_medoid_annotation_id": text(frozen.get("largest_cluster_medoid_annotation_id")) if frozen else NOT_IDENTIFIABLE,
                "largest_cluster_medoid_worker_id": text(frozen.get("largest_cluster_medoid_worker_id")) if frozen else NOT_IDENTIFIABLE,
                "largest_cluster_medoid_geometry_sha256": text(frozen.get("largest_cluster_medoid_geometry_sha256")) if frozen else NOT_IDENTIFIABLE,
                "task_crowd_structure_status": text(frozen.get("task_crowd_structure_status")) if frozen else "not_evaluable",
                "structure_reason": text(frozen.get("structure_reason")) if frozen else "version_bound_reconstruction_not_evaluable_source_absent",
            }
        else:
            result = cluster_geometry_records(
                records,
                min_q_boundary=cutoff,
                min_q_wallwall=cutoff,
                base_task_id=base_task_id,
                condition=condition,
                minimum_valid_k=int(method["geometry_cluster"]["minimum_valid_k"]),
                maximum_partition_count=int(method["geometry_cluster"]["maximum_partition_count"]),
                maximum_search_nodes=int(method["geometry_cluster"]["maximum_search_nodes"]),
            )
        compared_fields = (
            "partition_status", "cluster_membership_json", "cluster_count",
            "largest_cluster_support", "second_cluster_support",
            "largest_cluster_medoid_annotation_id",
            "task_crowd_structure_status",
        )
        mismatch_fields = []
        comparison_status = "match"
        if version_bound_c1:
            comparison_status = "version-bound reconstruction_not_evaluable/source_absent"
        elif stage == "C1":
            if frozen is None:
                comparison_status = "formal_sidecar_no_row_not_evaluable"
            else:
                for field in compared_fields:
                    left = text(result.get(field))
                    right = text(frozen.get(field))
                    if field == "cluster_membership_json":
                        try:
                            left = js(json.loads(left))
                            right = js(json.loads(right))
                        except json.JSONDecodeError:
                            pass
                    if left != right:
                        mismatch_fields.append(field)
                comparison_status = "match" if not mismatch_fields else "P0_c1_reconstruction_mismatch"
        output_status = (
            "frozen_c1_sidecar_reused_version_bound_not_recomputed" if version_bound_c1 and frozen is not None
            else "frozen_c1_sidecar_no_row_version_bound_not_evaluable" if version_bound_c1
            else "frozen_c1_sidecar_reused" if stage == "C1" and frozen is not None
            else "recomputed_formal_producer"
        )
        producer_name = "historical_c1_producer_source_absent" if version_bound_c1 else "tools/thesis_main/analysis/geometry_cluster_v2.py::cluster_geometry_records"
        consensus_rows.append({
            "stage": stage,
            "base_task_id": base_task_id,
            "condition": condition,
            "n_input_rows": len(records),
            "consensus_status": output_status,
            "consensus_producer": producer_name,
            "consensus_materializer": "tools/thesis_main/analysis/geometry_consensus/materialize.py",
            "consensus_rule_schema": "geometry_cluster_v2",
            "consensus_parameters_json": js({**params, "historical_binding": historical_binding if stage == "C1" else NOT_APPLICABLE}),
            "consensus_input_artifact": text(records[0].get("source_artifact")),
            "consensus_input_sha256": text(records[0].get("source_sha256")),
            "consensus_output_artifact": rel(c1_crowd_path) if stage == "C1" else "post_block2_geometry_reconstructed_consensus.csv",
            "consensus_output_sha256": sha256(c1_crowd_path) if stage == "C1" else "bound_after_materialization",
            "comparison_status": comparison_status,
            "comparison_mismatch_fields": ";".join(mismatch_fields) or "none",
            "producer_code_sha256": historical_binding["expected_sha"].get("geometry_cluster", NOT_IDENTIFIABLE) if stage == "C1" else producer_sha,
            **{key: text(value) if value == "" else value for key, value in result.items()},
        })
        consistency_rows.append({
            "stage": stage,
            "base_task_id": base_task_id,
            "condition": condition,
            "producer": producer_name,
            "parameters_sha256": hashlib.sha256(js(params).encode("utf-8")).hexdigest(),
            "input_artifact": text(records[0].get("source_artifact")),
            "input_sha256": text(records[0].get("source_sha256")),
            "frozen_reference_artifact": rel(c1_crowd_path) if frozen is not None else NOT_APPLICABLE,
            "frozen_reference_sha256": sha256(c1_crowd_path) if frozen is not None else NOT_APPLICABLE,
            "consistency_test_status": comparison_status,
            "mismatch_fields": ";".join(mismatch_fields) or "none",
            "recomputed_medoid_geometry_sha256": text(result.get("largest_cluster_medoid_geometry_sha256")),
            "frozen_medoid_geometry_sha256": text(frozen.get("largest_cluster_medoid_geometry_sha256")) if frozen is not None else NOT_APPLICABLE,
            "reconstruction_rule": "complete_link_partition_and_contractual_medoid",
            "formula_source": "tools/thesis_main/analysis/geometry_cluster_v2.py",
            "historical_binding_status": historical_binding["status"] if stage == "C1" else NOT_APPLICABLE,
        })
    return consensus_rows, consistency_rows


def join_sidecars(rows: list[dict[str, Any]], c1_sources: dict[str, Path]) -> None:
    crowd = {(text(row.get("base_task_id")), text(row.get("condition"))): row for row in read_csv(c1_sources["crowd"])}
    evidence: dict[str, dict[str, str]] = {}
    for row in read_csv(c1_sources["gt_evidence"]):
        for key in (row.get("canonical_annotation_id"), row.get("annotation_id")):
            if key:
                evidence[str(key)] = row
    evidence_sha = sha256(c1_sources["gt_evidence"])
    for row in rows:
        if row["stage"] != "C1":
            row.setdefault("frozen_gt_sidecar_status", NOT_APPLICABLE)
            continue
        structure = crowd.get((text(row.get("base_task_id")), text(row.get("condition"))), {})
        gt = evidence.get(text(row.get("canonical_annotation_id")), {}) or evidence.get(text(row.get("annotation_id")), {})
        row.update({
            "frozen_c1_cluster_status": text(structure.get("task_crowd_structure_status"), "formal_c1_sidecar_no_row_not_evaluable"),
            "frozen_c1_cluster_membership_json": text(structure.get("cluster_membership_json")),
            "frozen_c1_medoid_annotation_id": text(structure.get("largest_cluster_medoid_annotation_id")),
            "frozen_c1_medoid_geometry_sha256": text(structure.get("largest_cluster_medoid_geometry_sha256")),
            "frozen_c1_gt_sidecar_status": "joined_formal_c1_gt_quality_evidence" if gt else "missing_frozen_c1_gt_evidence",
            "c1_iou_to_gt": text(gt.get("iou_to_gt")),
            "c1_gt_reference_status": text(gt.get("geometry_reference_status")),
            "c1_gt_primary_analysis_eligible": text(gt.get("gt_primary_analysis_eligible")),
            "c1_gt_quality_interpretation_status": text(gt.get("quality_interpretation_status")),
            "c1_gt_source_artifact": rel(c1_sources["gt_evidence"]),
            "c1_gt_source_sha256": evidence_sha,
        })


def apply_exclusions(rows: list[dict[str, Any]], profile_status_source: dict[str, str]) -> list[dict[str, Any]]:
    exclusions: list[dict[str, Any]] = []
    for row in rows:
        reasons: list[str] = []
        if row["stage"] == "P1" and str(row.get("upstream_eligible_for_primary_analysis", "")).lower() in {"false", "0"}:
            reasons.append("p1_primary_analysis_ineligible")
        if row["stage"] != "P1" and not truthy(row.get("canonical_valid")):
            reasons.append("canonical_geometry_invalid")
        if row["stage"] == "C2A-RP-B2" and row.get("active_time_status") != "owner_valid":
            reasons.append("active_time_not_owner_valid")
        if reasons:
            primary_reason = ";".join(reasons)
            row.update({
                "exclusion_reason": primary_reason,
                "exclusion_source_rule": "Prompt_1_data_qualification_v2",
                "exclusion_source_artifact": text(row.get("source_artifact")),
                "exclusion_source_sha256": text(row.get("source_sha256")),
                "exclusion_stage": text(row.get("stage")),
                "exclusion_time_or_version": "2026-08-17_v2",
            })
            for reason in reasons:
                exclusions.append({
                    "record_type": "submission",
                    "stage": text(row.get("stage")),
                    "worker_id": text(row.get("worker_id")),
                    "task_id": text(row.get("task_id")),
                    "base_task_id": text(row.get("base_task_id")),
                    "canonical_annotation_id": text(row.get("canonical_annotation_id")),
                    "exclusion_reason": reason,
                    "source_rule": "Prompt_1_data_qualification_v2",
                    "source_artifact": text(row.get("source_artifact")),
                    "source_sha256": text(row.get("source_sha256")),
                    "decision_stage": text(row.get("stage")),
                    "decision_time_or_version": "2026-08-17_v2",
                    "status": "excluded_from_relevant_estimand",
                })
        else:
            row.update({
                "exclusion_reason": NOT_APPLICABLE,
                "exclusion_source_rule": NOT_APPLICABLE,
                "exclusion_source_artifact": NOT_APPLICABLE,
                "exclusion_source_sha256": NOT_APPLICABLE,
                "exclusion_stage": NOT_APPLICABLE,
                "exclusion_time_or_version": NOT_APPLICABLE,
            })
    exclusions.append({
        "record_type": "profile",
        "stage": "post-Block2",
        "worker_id": NOT_APPLICABLE,
        "task_id": NOT_APPLICABLE,
        "base_task_id": NOT_APPLICABLE,
        "canonical_annotation_id": NOT_APPLICABLE,
        "exclusion_reason": "post_block2_final_pooled_profile_source_absent",
        "source_rule": "tools/thesis_main/analysis/materialize_final_pooled_profile_freeze.py",
        "source_artifact": profile_status_source["producer_path"],
        "source_sha256": profile_status_source["producer_sha256"],
        "decision_stage": "post-Block2",
        "decision_time_or_version": "2026-08-17_v2",
        "status": "P0_source_absent_NO_GO",
    })
    return exclusions


def enrich_gt_validation(rows: list[dict[str, Any]], scope_note: Path) -> None:
    note_sha = sha256(scope_note)
    for row in rows:
        if row["stage"] == "P1":
            continue
        row.update({
            "gt_population_role": "validation",
            "gt_provenance_class": "mp3d_hohonet_source_no_researcher_correction",
            "gt_user_correction_status": "none",
            "gt_user_verification_scope": "none",
            "gt_source_artifact": rel(scope_note),
            "gt_source_sha256": note_sha,
            "gt_provenance_version": "RAW_DATA_AND_GROUND_TRUTH_SCOPE_NOTE_20260817",
        })


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    scope_note = ROOT / "export_label" / "RAW_DATA_AND_GROUND_TRUTH_SCOPE_NOTE_20260817.md"
    p1_path = ROOT / "analysis_results" / "prescreen_closeout_final_gold_v2_20260701" / "prescreen_canonical_annotations.csv"
    c1_sources = find_c1_sources()
    c2b_path = ROOT / "analysis_results" / "c2b_closeout_20260806_final" / "c2b_canonical_submissions.csv"
    c2b_building_path = ROOT / "analysis_results" / "c2b_closeout_20260806_final" / "c2b_canonical_risk_slope_evidence.csv"
    block1_path = ROOT / "analysis_results" / "c2a_rp_block1_reestimate_20260810_v1" / "c2a_rp_block1_canonical_submissions.csv"
    block1_building_path = ROOT / "analysis_results" / "c2a_rp_block1_reestimate_20260810_v1" / "c2a_rp_block1_risk_slope_evidence.csv"
    block2_exports = [
        ROOT / "export_label" / "c2arp_block2" / "project-84-at-2026-08-14-08-36-31615637.json",
        ROOT / "export_label" / "c2arp_block2" / "project-85-at-2026-08-14-08-36-71fffb37.json",
    ]
    block2_active_dir = ROOT / "active_logs" / "c2a_rp_block2_20260814"
    block2_assignment_path = ROOT / "analysis_results" / "c2a_rp_block2_distribution_20260810_v1" / "assignment_manifest_C2A_RP_block_2.csv"
    block2_task_pool_path = ROOT / "analysis_results" / "c2a_rp_block2_distribution_20260810_v1" / "c2a_rp_task_pool_block2.csv"
    stale_mapping_path = ROOT / "analysis_results" / "c2a_rp_block2_distribution_20260810_v1" / "c2a_rp_operational" / "c2a_rp_runtime_mapping.csv"
    profile_producer = ROOT / "tools" / "thesis_main" / "analysis" / "materialize_final_pooled_profile_freeze.py"
    cluster_producer = ROOT / "tools" / "thesis_main" / "analysis" / "geometry_cluster_v2.py"
    cluster_materializer = ROOT / "tools" / "thesis_main" / "analysis" / "geometry_consensus" / "materialize.py"
    method_path = ROOT / "docs" / "thesis_main" / "PAPER_A_METHOD_CONTRACT_CURRENT.json"
    method = load_method_contract(method_path)
    historical_binding = load_c1_historical_binding(c1_sources, method_path)

    p1_rows = load_p1_rows(p1_path, scope_note)
    c1_rows = load_c1_rows(c1_sources["geometry"])
    c2b_rows = load_canonical_rows(c2b_path, "C2-B")
    block1_rows = load_canonical_rows(block1_path, "C2A-RP-B1")
    block2_rows, block2_stats = load_block2_rows(block2_exports)
    all_rows = p1_rows + c1_rows + c2b_rows + block1_rows + block2_rows
    bind_authoritative_buildings(all_rows, {
        "C1": (read_csv(c1_sources["building_binding"]), "C1_TASK_BUILDING_BINDING_FROZEN"),
        "C2-B": (read_csv(c2b_building_path), "C2B_CANONICAL_RISK_SLOPE_EVIDENCE"),
        "C2A-RP-B1": (read_csv(block1_building_path), "C2A_RP_BLOCK1_RISK_SLOPE_EVIDENCE"),
        "C2A-RP-B2": (read_csv(block2_task_pool_path), "C2A_RP_BLOCK2_TASK_POOL"),
    })
    enrich_gt_validation(all_rows, scope_note)
    active_manifest_checks = active_time_block2(block2_rows, block2_active_dir)

    assignments = read_csv(block2_assignment_path)
    reconciliation = reconcile_block2(assignments, block2_rows)
    producer_sha = hashlib.sha256((sha256(cluster_producer) + sha256(cluster_materializer)).encode("utf-8")).hexdigest()
    consensus_rows, consistency_rows = build_consensus(all_rows, c1_sources["crowd"], method, producer_sha, historical_binding)
    join_sidecars(all_rows, c1_sources)
    consensus_by_key = {(row["stage"], row["base_task_id"], row["condition"]): row for row in consensus_rows}
    for row in all_rows:
        key = (row["stage"], text(row["base_task_id"]), text(row["condition"]))
        c = consensus_by_key.get(key)
        row.update({
            "consensus_status": text(c.get("consensus_status")) if c else ("not_applicable_p1" if row["stage"] == "P1" else "missing_consensus_record"),
            "consensus_cluster_status": text(c.get("task_crowd_structure_status")) if c else ("not_applicable_p1" if row["stage"] == "P1" else "missing_consensus_record"),
            "consensus_medoid_annotation_id": text(c.get("largest_cluster_medoid_annotation_id")) if c else ("not_applicable_p1" if row["stage"] == "P1" else NOT_IDENTIFIABLE),
            "consensus_medoid_geometry_sha256": text(c.get("largest_cluster_medoid_geometry_sha256")) if c else ("not_applicable_p1" if row["stage"] == "P1" else NOT_IDENTIFIABLE),
            "consensus_producer": text(c.get("consensus_producer")) if c else ("not_applicable_p1" if row["stage"] == "P1" else NOT_IDENTIFIABLE),
            "consensus_parameters_json": text(c.get("consensus_parameters_json")) if c else ("not_applicable_p1" if row["stage"] == "P1" else NOT_IDENTIFIABLE),
            "consensus_input_artifact": text(c.get("consensus_input_artifact")) if c else text(row.get("source_artifact")),
            "consensus_input_sha256": text(c.get("consensus_input_sha256")) if c else text(row.get("source_sha256")),
            "consensus_output_artifact": text(c.get("consensus_output_artifact")) if c else NOT_APPLICABLE,
            "consensus_output_sha256": text(c.get("consensus_output_sha256")) if c else NOT_APPLICABLE,
        })

    profile_status_source = {"producer_path": rel(profile_producer), "producer_sha256": sha256(profile_producer)}
    exclusions = apply_exclusions(all_rows, profile_status_source)
    write_csv(OUT / "post_block2_submission_master.csv", all_rows)
    write_csv(OUT / "post_block2_block2_assignment_reconciliation.csv", reconciliation)
    write_csv(OUT / "post_block2_exclusion_provenance.csv", exclusions)
    write_csv(OUT / "post_block2_geometry_reconstructed_consensus.csv", consensus_rows)
    write_csv(OUT / "post_block2_geometry_reconstruction_consistency.csv", consistency_rows)

    reconstructed_sha = sha256(OUT / "post_block2_geometry_reconstructed_consensus.csv")
    for row in all_rows:
        if row["stage"] not in {"C1", "P1"}:
            row["consensus_output_sha256"] = reconstructed_sha
    for row in consensus_rows:
        if row["stage"] not in {"C1", "P1"}:
            row["consensus_output_sha256"] = reconstructed_sha
    write_csv(OUT / "post_block2_submission_master.csv", all_rows)
    write_csv(OUT / "post_block2_geometry_reconstructed_consensus.csv", consensus_rows)

    task_groups: dict[tuple[str, str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in all_rows:
        task_groups[(row["stage"], text(row["base_task_id"]), text(row["condition"]))].append(row)
    task_context = []
    for (stage, base_task_id, condition), group in sorted(task_groups.items()):
        c = consensus_by_key.get((stage, base_task_id, condition))
        task_context.append({
            "stage": stage,
            "task_id": text(group[0].get("task_id")),
            "base_task_id": base_task_id,
            "condition": condition,
            "dataset_group": text(group[0].get("dataset_group")),
            "observed_annotation_count": len(group),
            "observed_worker_ids": ";".join(sorted({text(row.get("worker_id")) for row in group})),
            "valid_geometry_count": sum(truthy(row.get("canonical_valid")) for row in group),
            "owner_valid_active_time_count": sum(row.get("active_time_status") == "owner_valid" for row in group),
            "consensus_status": text(c.get("consensus_status")) if c else ("not_applicable_p1" if stage == "P1" else "missing_consensus_record"),
            "consensus_cluster_status": text(c.get("task_crowd_structure_status")) if c else ("not_applicable_p1" if stage == "P1" else "missing_consensus_record"),
            "cluster_membership_json": text(c.get("cluster_membership_json")) if c else ("not_applicable_p1" if stage == "P1" else NOT_IDENTIFIABLE),
            "cluster_count": text(c.get("cluster_count")) if c else ("not_applicable_p1" if stage == "P1" else NOT_IDENTIFIABLE),
            "largest_cluster_support": text(c.get("largest_cluster_support")) if c else ("not_applicable_p1" if stage == "P1" else NOT_IDENTIFIABLE),
            "largest_cluster_medoid_annotation_id": text(c.get("largest_cluster_medoid_annotation_id")) if c else ("not_applicable_p1" if stage == "P1" else NOT_IDENTIFIABLE),
            "largest_cluster_medoid_geometry_sha256": text(c.get("largest_cluster_medoid_geometry_sha256")) if c else ("not_applicable_p1" if stage == "P1" else NOT_IDENTIFIABLE),
            "consensus_producer": text(c.get("consensus_producer")) if c else ("not_applicable_p1" if stage == "P1" else NOT_IDENTIFIABLE),
            "consensus_parameters_json": text(c.get("consensus_parameters_json")) if c else ("not_applicable_p1" if stage == "P1" else NOT_IDENTIFIABLE),
            "consensus_input_artifact": text(c.get("consensus_input_artifact")) if c else text(group[0].get("source_artifact")),
            "consensus_input_sha256": text(c.get("consensus_input_sha256")) if c else text(group[0].get("source_sha256")),
            "consensus_output_artifact": text(c.get("consensus_output_artifact")) if c else NOT_APPLICABLE,
            "consensus_output_sha256": reconstructed_sha if stage not in {"C1", "P1"} else (text(c.get("consensus_output_sha256")) if c else NOT_APPLICABLE),
            "gt_provenance_class": text(group[0].get("gt_provenance_class")),
            "gt_user_correction_status": text(group[0].get("gt_user_correction_status")),
            "gt_user_verification_scope": text(group[0].get("gt_user_verification_scope")),
            "gt_source_artifact": text(group[0].get("gt_source_artifact")),
            "gt_source_sha256": text(group[0].get("gt_source_sha256")),
            "source_artifact": text(group[0].get("source_artifact")),
            "source_sha256": text(group[0].get("source_sha256")),
        })
    write_csv(OUT / "post_block2_task_context_master.csv", task_context)

    workers: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in all_rows:
        workers[text(row.get("worker_id"))].append(row)
    historical_profile = ROOT / "analysis_results" / "c2b_closeout_20260806_final" / "post_c2b_worker_profile.csv"
    profile_rows = []
    for worker_id, group in sorted(workers.items()):
        profile_rows.append({
            "worker_id": worker_id,
            "profile_status": SOURCE_ABSENT,
            "final_pooled_profile_status": SOURCE_ABSENT,
            "final_profile_producer": rel(profile_producer),
            "final_profile_producer_sha256": sha256(profile_producer),
            "historical_post_c2b_profile_source": rel(historical_profile),
            "historical_post_c2b_profile_sha256": sha256(historical_profile),
            "historical_profile_is_final_pooled": "false",
            "post_block2_profile_substitution_allowed": "false",
            "observed_submission_count": len(group),
            "observed_stage_counts": js(dict(Counter(row["stage"] for row in group))),
            "owner_valid_block2_active_time_count": sum(row.get("active_time_status") == "owner_valid" for row in group),
            "profile_exclusion_reason": "post_block2_final_pooled_profile_source_absent",
            "profile_exclusion_source_artifact": rel(profile_producer),
            "profile_exclusion_source_sha256": sha256(profile_producer),
            "profile_exclusion_stage": "post-Block2",
            "profile_exclusion_time_or_version": "2026-08-17_v2",
        })
    write_csv(OUT / "post_block2_worker_profile_master.csv", profile_rows)

    write_csv(OUT / "worker_task_incidence.csv", [{
        "worker_id": text(row.get("worker_id")),
        "stage": row["stage"],
        "task_id": text(row.get("task_id")),
        "base_task_id": text(row.get("base_task_id")),
        "annotation_id": text(row.get("annotation_id")),
        "active_time_status": text(row.get("active_time_status"), NOT_APPLICABLE),
        "active_time_seconds": text(row.get("active_time_seconds"), NOT_APPLICABLE),
        "source_artifact": text(row.get("source_artifact")),
        "source_sha256": text(row.get("source_sha256")),
    } for row in all_rows])
    write_csv(OUT / "worker_building_incidence.csv", worker_building_rows(all_rows))
    write_csv(OUT / "task_worker_support_summary.csv", [{
        "stage": stage,
        "base_task_id": base,
        "condition": condition,
        "worker_count": len({text(r.get("worker_id")) for r in group}),
        "annotation_count": len(group),
        "source_artifact": text(group[0].get("source_artifact")),
        "source_sha256": text(group[0].get("source_sha256")),
    } for (stage, base, condition), group in sorted(task_groups.items())])
    write_csv(OUT / "building_support_summary.csv", building_support_rows(all_rows))
    write_csv(OUT / "aggregation_candidate_geometries.csv", [{
        "stage": row["stage"],
        "base_task_id": text(row.get("base_task_id")),
        "canonical_annotation_id": text(row.get("canonical_annotation_id")),
        "worker_id": text(row.get("worker_id")),
        "canonical_geometry": text(row.get("canonical_geometry")),
        "consensus_status": text(row.get("consensus_status")),
        "consensus_medoid_annotation_id": text(row.get("consensus_medoid_annotation_id")),
        "source_artifact": text(row.get("source_artifact")),
        "source_sha256": text(row.get("source_sha256")),
    } for row in all_rows])
    write_csv(OUT / "routing_worker_pair_candidates.csv", [{
        "stage": stage,
        "worker_id_left": left,
        "worker_id_right": right,
        "shared_task_count": sum(
            1 for key, group in task_groups.items()
            if key[0] == stage
            and left in {text(r.get("worker_id")) for r in group}
            and right in {text(r.get("worker_id")) for r in group}
        ),
        "source_artifact": "post_block2_submission_master.csv",
        "source_sha256": "bound_after_materialization",
    } for stage in STAGES for left in sorted(workers) for right in sorted(workers) if left < right])

    stage_counts = Counter(row["stage"] for row in all_rows)
    p0: list[dict[str, str]] = []
    p1: list[dict[str, str]] = []
    for stage, expected in EXPECTED_STAGE_COUNTS.items():
        if stage_counts.get(stage, 0) != expected:
            p0.append({"id": "stage_count_mismatch", "stage": stage, "detail": f"expected={expected};observed={stage_counts.get(stage, 0)}"})
    missing_buildings = Counter(
        row["stage"] for row in all_rows
        if row["stage"] != "P1" and not identified_building(row)
    )
    if missing_buildings:
        p0.append({"id": "authoritative_building_binding_missing", "stage": "Calibration", "detail": js(dict(missing_buildings))})
    if block2_stats["runtime_task_count"] != 32 or block2_stats["annotation_count"] != 40:
        p0.append({"id": "block2_runtime_count_mismatch", "stage": "C2A-RP-B2", "detail": js(block2_stats)})
    if len(assignments) != 40 or any(row["reconciliation_status"] != "exact_observed_match" for row in reconciliation):
        p0.append({"id": "block2_assignment_reconciliation_failed", "stage": "C2A-RP-B2", "detail": "40 assignment rows must exactly match observed export annotations"})
    if not active_manifest_checks or not all(check["match"] for check in active_manifest_checks):
        p0.append({"id": "block2_active_time_manifest_sha_mismatch", "stage": "C2A-RP-B2", "detail": js(active_manifest_checks)})
    if any(row["consistency_test_status"].startswith("P0_") for row in consistency_rows if row["stage"] == "C1"):
        p0.append({"id": "c1_geometry_reconstruction_inconsistent", "stage": "C1", "detail": "formal sidecar and geometry_cluster_v2 reconstruction differ"})
    p0.append({"id": "post_block2_final_pooled_profile_source_absent", "stage": "post-Block2", "detail": f"producer searched: {rel(profile_producer)}; no formal post-Block2 snapshot exists"})
    if any(row["active_time_status"] != "owner_valid" for row in block2_rows):
        p1.append({"id": "block2_active_time_owner_valid_gap", "stage": "C2A-RP-B2", "detail": "some observed annotations lack owner-valid active time"})
    if any(row["consistency_test_status"] != "match" for row in consistency_rows if row["stage"] != "C1"):
        p1.append({"id": "recomputed_geometry_cluster_not_evaluable_or_warning", "stage": "C2/C2A-RP", "detail": "recomputed outputs are retained with explicit status"})
    submission_exclusion_count = sum(item["record_type"] == "submission" for item in exclusions)
    profile_p0_inventory_count = sum(item["record_type"] == "profile" for item in exclusions)
    if not historical_binding["exact_historical_binding_available"]:
        p1.append({"id": "c1_version_bound_reconstruction_not_evaluable_source_absent", "stage": "C1", "detail": "frozen sidecar reused; historical producer/rule source is unavailable for exact replay"})
    if submission_exclusion_count:
        p1.append({"id": "estimand_exclusions_present", "stage": "all", "detail": f"submission_exclusions={submission_exclusion_count};profile_p0_inventory={profile_p0_inventory_count};combined_inventory={len(exclusions)}"})

    provenance = {
        "schema_version": "post_block2_analysis_pack_provenance_v2",
        "pack_version": "post_block2_analysis_pack_20260817_v2",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "status": "NO-GO" if p0 else "GO",
        "prompt_2_entry_allowed": False if p0 else True,
        "block3_generated": False,
        "v1_preserved": True,
        "v1_output_touched": False,
        "git_cli_used": False,
        "git_provenance": "not_collected_user_constraint",
        "stage_counts": dict(stage_counts),
        "expected_stage_counts": EXPECTED_STAGE_COUNTS,
        "block2_runtime_observed": block2_stats,
        "block2_assignment_rows": len(assignments),
        "block2_assignment_reconciliation_exact": sum(row["reconciliation_status"] == "exact_observed_match" for row in reconciliation),
        "block2_active_time_manifest_checks": active_manifest_checks,
        "submission_exclusion_count": submission_exclusion_count,
        "profile_p0_inventory_count": profile_p0_inventory_count,
        "combined_exclusion_inventory_count": len(exclusions),
        "stale_runtime_mapping_excluded": {
            "path": rel(stale_mapping_path),
            "sha256": sha256(stale_mapping_path),
            "used_for_observed_mapping": False,
            "reason": "distribution mapping contains stale pending runtime state",
        },
        "gt_scope_note": source(scope_note, "user_confirmed_gt_scope_note"),
        "gt_provenance": {
            "test": "partial_local_only; not_full_population_user_verified",
            "validation": "mp3d_hohonet_source; no_researcher_correction; not_user_verified",
            "source_note_sha256": sha256(scope_note),
        },
        "formal_sources": [
            source(p1_path, "P1_CANONICAL_FINAL_GOLD"),
            source(c1_sources["geometry"], "C1_CANONICAL_GEOMETRY_FROZEN"),
            source(c1_sources["pairwise"], "C1_PAIRWISE_FROZEN"),
            source(c1_sources["crowd"], "C1_CROWD_STRUCTURE_FROZEN"),
            source(c1_sources["building_binding"], "C1_TASK_BUILDING_BINDING_FROZEN"),
            source(c1_sources["gt_evidence"], "C1_GT_QUALITY_EVIDENCE_FROZEN"),
            source(c1_sources["gt_analysis"], "C1_GT_QUALITY_ANALYSIS_FROZEN"),
            source(c1_sources["views_manifest"], "C1_ANALYSIS_VIEWS_MANIFEST"),
            source(c1_sources["evidence_freeze"], "C1_EVIDENCE_FREEZE_MANIFEST"),
            source(c1_sources["measurement_freeze"], "C1_MEASUREMENT_FREEZE_MANIFEST"),
            source(c1_sources["dependency_manifest"], "C1_ANALYSIS_DEPENDENCY_MANIFEST"),
            source(c1_sources["raw_input_manifest"], "C1_RAW_INPUT_MANIFEST"),
            source(ROOT / historical_binding["historical_rule_path"], "C1_HISTORICAL_RULE_MANIFEST"),
            source(c2b_path, "C2B_CANONICAL_CLOSEOUT"),
            source(c2b_building_path, "C2B_CANONICAL_RISK_SLOPE_EVIDENCE"),
            source(block1_path, "C2A_RP_BLOCK1_CANONICAL_CLOSEOUT"),
            source(block1_building_path, "C2A_RP_BLOCK1_RISK_SLOPE_EVIDENCE"),
            source(block2_assignment_path, "C2A_RP_BLOCK2_ASSIGNMENT_MANIFEST"),
            source(block2_task_pool_path, "C2A_RP_BLOCK2_TASK_POOL"),
            source(block2_active_dir / "ACTIVE_TIME_FREEZE_MANIFEST.json", "C2A_RP_BLOCK2_ACTIVE_TIME_FREEZE_MANIFEST"),
            source(scope_note, "GT_SCOPE_NOTE"),
        ] + [source(path, "C2A_RP_BLOCK2_RAW_EXPORT") for path in block2_exports],
        "producer_bindings": {
            "method_contract": source(method_path, "METHOD_CONTRACT"),
            "geometry_cluster_schema": source(ROOT / "docs" / "thesis_main" / "geometry_cluster_v2.json", "GEOMETRY_CLUSTER_SCHEMA"),
            "geometry_cluster_producer": source(cluster_producer, "GEOMETRY_CLUSTER_PRODUCER"),
            "geometry_consensus_materializer": source(cluster_materializer, "GEOMETRY_CONSENSUS_MATERIALIZER"),
            "final_pooled_profile_producer": source(profile_producer, "FINAL_POOLED_PROFILE_PRODUCER"),
        },
        "c1_historical_binding": historical_binding,
        "profile_status": {
            "final_pooled_profile": SOURCE_ABSENT,
            "p0": True,
            "post_c2b_substitution_allowed": False,
            "historical_post_c2b_source": rel(historical_profile),
            "historical_post_c2b_sha256": sha256(historical_profile),
        },
        "p0_findings": p0,
        "p1_findings": p1,
        "source_conflict_status": {
            "p1_canonical_vs_c1_raw_snapshot": "resolved_same_content_by_formal_manifest_chain",
            "c1_frozen_geometry": historical_binding["status"],
            "block2_runtime_mapping": "stale_distribution_mapping_excluded",
        },
    }
    (OUT / "POST_BLOCK2_DATA_PROVENANCE.json").write_text(json.dumps(provenance, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    qa = [
        "# post-Block2 analysis pack v2 QA",
        "",
        f"- 状态：**{provenance['status']}**",
        f"- Prompt 2：**{'允许' if provenance['prompt_2_entry_allowed'] else '禁止'}**",
        "- Block 3：未生成",
        "",
        "## Stage counts",
        "",
        "| stage | observed | expected |",
        "|---|---:|---:|",
    ]
    qa.extend(f"| {stage} | {stage_counts.get(stage, 0)} | {expected} |" for stage, expected in EXPECTED_STAGE_COUNTS.items())
    qa.extend([
        "",
        "## Inventory counts",
        "",
        f"- submission exclusions: {submission_exclusion_count}",
        f"- profile P0 inventory: {profile_p0_inventory_count}",
        f"- combined inventory rows: {len(exclusions)} ({submission_exclusion_count} submission exclusions + {profile_p0_inventory_count} profile P0 inventory)",
        "",
        "## C1 historical binding",
        "",
        f"- freeze method contract: {historical_binding['historical_method_contract_version']} / {historical_binding['historical_method_contract_sha256']}",
        f"- historical commit binding: {historical_binding['historical_git_commit_sha']}",
        f"- historical rule: {historical_binding['historical_rule_path']} / {historical_binding['expected_sha'].get('rule_manifest', NOT_IDENTIFIABLE)}",
        f"- reconstruction status: {historical_binding['status']}",
        f"- unavailable components: {','.join(historical_binding['unavailable_components']) or 'none'}",
        "",
        "## Block 2 observed reconciliation",
        "",
        f"- raw exports: {block2_stats['export_count']}",
        f"- runtime tasks: {block2_stats['runtime_task_count']}",
        f"- annotations: {block2_stats['annotation_count']}",
        f"- assignment rows: {len(assignments)}",
        f"- exact assignment matches: {sum(row['reconciliation_status'] == 'exact_observed_match' for row in reconciliation)}",
        "- observed mapping source: raw export task.data base_task_id/deployment_id plus annotation completed_by",
        "- stale distribution runtime mapping used: false",
        "",
        "## GT provenance boundary",
        "",
        "- test：仅少量局部研究者修正，不是全量 user-verified。",
        "- validation：沿用 MP3D/HoHoNet 自带来源，没有研究者自己的修正，不称为用户验证。",
        f"- binding note: {rel(scope_note)}; SHA-256 {sha256(scope_note)}",
        "",
        "## P0 findings",
        "",
    ])
    if p0:
        qa.extend(f"- {item['id']} [{item['stage']}]: {item['detail']}" for item in p0)
    else:
        qa.append("- none")
    qa.extend(["", "## P1 findings", ""])
    if p1:
        qa.extend(f"- {item['id']} [{item['stage']}]: {item['detail']}" for item in p1)
    else:
        qa.append("- none")
    (OUT / "POST_BLOCK2_DATA_QA_REPORT.md").write_text("\n".join(qa) + "\n", encoding="utf-8")

    readme = f"""# post-Block2 analysis pack 2026-08-17 v2

本目录是独立新版本，未覆盖 analysis_results/post_block2_analysis_pack_20260817_v1/。

## 结论

- QA 状态：**{provenance['status']}**
- Prompt 2：**{'禁止进入' if p0 else '可进入'}**
- Block 3：未生成。
- stage counts：P1={stage_counts.get('P1', 0)}、C1={stage_counts.get('C1', 0)}、C2-B={stage_counts.get('C2-B', 0)}、C2A-RP-Block1={stage_counts.get('C2A-RP-B1', 0)}、C2A-RP-Block2={stage_counts.get('C2A-RP-B2', 0)}。

## Block 2

两份原始 export 共 {block2_stats['runtime_task_count']} 个 runtime tasks、{block2_stats['annotation_count']} 条 annotations；按 assignment manifest 的 {len(assignments)} 条 worker×task 逐行对账。observed mapping 只使用 export task.data 的 base_task_id/deployment_id 与 annotation completed_by，distribution 中 stale pending runtime mapping 明确未使用。active time 绑定冻结 manifest 与其 JSONL SHA。

## Geometry consensus

C1 优先复用 formal audit 冻结的 canonical geometry、pairwise similarity、crowd structure、GT evidence/analysis。C1 freeze 绑定的是 {historical_binding['historical_method_contract_version']}、commit {historical_binding['historical_git_commit_sha']} 和历史 producer/rule SHA；历史 producer source 未保存在仓库，因此 C1 重建状态为 {historical_binding['status']}，不把 frozen sidecar 判为错误。C2-B、Block1、Block2 没有伪造公式，统一记录 producer、contract 参数、input SHA 与 output SHA。

## Inventory counts

- submission exclusions：{submission_exclusion_count}
- profile P0 inventory：{profile_p0_inventory_count}
- combined inventory：{len(exclusions)}，即 {submission_exclusion_count} 条 submission exclusions + {profile_p0_inventory_count} 条 profile P0，不是 {len(exclusions)} 条 submission exclusions。

## Worker profile

没有找到正式 post-Block2 final pooled profile snapshot。post_block2_worker_profile_master.csv 只提供 observed support 和 source-absent 状态；post-C2B profile 仅作为历史来源记录，禁止冒充 final pooled profile。因此当前 QA 保持 P0/NO-GO。

## GT provenance

本包保持 {rel(scope_note)} 的用户说明：test 仅少量局部修正，不是全量用户验证；validation 没有研究者自己的修正，只沿用 MP3D/HoHoNet 自带来源，不称为用户验证。该说明 SHA-256 为 {sha256(scope_note)}，并写入 provenance 与逐行字段。

## 文件

- POST_BLOCK2_DATA_PROVENANCE.json：输入、producer、SHA、stage counts、P0/P1。
- POST_BLOCK2_DATA_QA_REPORT.md：QA 报告。
- post_block2_block2_assignment_reconciliation.csv：Block 2 40 行逐行对账。
- post_block2_geometry_reconstruction_consistency.csv：formal producer 重建一致性测试。
- post_block2_exclusion_provenance.csv：每条 exclusion 的 reason/source artifact/SHA/stage/time/version。
- post_block2_worker_profile_master.csv：source-absent profile 状态，非 final pooled profile。
"""
    (OUT / "README.md").write_text(readme, encoding="utf-8")

    artifacts = {}
    for path in sorted(OUT.iterdir()):
        if path.name != "ARTIFACT_HASH_MANIFEST.json" and path.is_file():
            artifacts[path.name] = sha256(path)
    manifest = {
        "schema_version": "post_block2_artifact_hash_manifest_v2",
        "pack_version": "post_block2_analysis_pack_20260817_v2",
        "manifest_self_sha256": "not_bound_recursive",
        "artifact_count": len(artifacts),
        "artifacts": artifacts,
    }
    manifest_path = OUT / "ARTIFACT_HASH_MANIFEST.json"
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "output_dir": rel(OUT),
        "status": provenance["status"],
        "stage_counts": dict(stage_counts),
        "p0_count": len(p0),
        "p1_count": len(p1),
        "block2": block2_stats,
        "manifest_sha256": sha256(manifest_path),
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
