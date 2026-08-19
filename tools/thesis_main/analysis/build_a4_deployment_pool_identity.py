"""Materialize the GT-free C1 deployment-pool identity layer."""

from __future__ import annotations

import csv
import hashlib
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Iterable

ROOT = Path(__file__).resolve().parents[3]
FORMAL = ROOT / "analysis_results/c1_formal_audit_20260802_v16_final/c1_formal_audit_20260802_7fcacc5c2d6c_bf5def46_6bc67c03"
CANDIDATE_PATH = ROOT / "analysis_results/a4_image_evidence_substrate_20260817_v2/DEVELOPMENT_CANDIDATE_GEOMETRY_DESCRIPTORS.csv"
OUT = ROOT / "analysis_results/a4_deployment_pool_identity_20260817_v1"

CANONICAL_PATH = FORMAL / "c1_canonical_annotations.csv"
RUNTIME_PATH = FORMAL / "c1_runtime_task_mapping.csv"
REALIZATION_PATH = FORMAL / "c1_assignment_realization_audit.csv"
COLLISION_PATH = FORMAL / "c1_runtime_key_collision_audit.csv"
MERGE_PATH = FORMAL / "c1_export_merge_manifest.csv"
PROJECT_SUMMARY_PATH = FORMAL / "c1_project_independence_provenance_summary.json"
RAW_MANIFEST_PATH = FORMAL / "raw_inputs/raw_input_snapshot_manifest.csv"
CLOSURE_PATH = FORMAL / "raw_snapshots/dispositions/3d0276fadf4a_c1_collection_closure_manifest.json"

INPUTS = {
    "candidate_descriptors": CANDIDATE_PATH,
    "canonical_annotations": CANONICAL_PATH,
    "runtime_mapping": RUNTIME_PATH,
    "assignment_realization": REALIZATION_PATH,
    "runtime_collision_audit": COLLISION_PATH,
    "export_merge_manifest": MERGE_PATH,
    "project_provenance_summary": PROJECT_SUMMARY_PATH,
    "raw_snapshot_manifest": RAW_MANIFEST_PATH,
    "collection_closure_manifest": CLOSURE_PATH,
}

CANDIDATE_COLUMNS = [
    "candidate_annotation_id", "worker_id", "stage", "panorama_identity", "building_scene_id",
    "parse_status", "layout_corner_count",
]
CANONICAL_COLUMNS = [
    "canonical_annotation_id", "worker_id", "round_id", "condition", "base_task_id",
    "task_id", "project_id", "ls_runtime_task_id", "dataset_group", "source_export",
    "source_export_sha256", "assignment_provenance", "duplicate_worker_task_submission",
    "duplicate_group_size", "duplicate_annotation_ids", "duplicate_decision",
    "process_disposition", "appears_in_internal_distribution",
]
RUNTIME_COLUMNS = [
    "project_id", "ls_runtime_task_id", "task_id", "base_task_id", "condition",
    "planned_project_name", "source_export",
]
REALIZATION_COLUMNS = [
    "worker_id", "task_id", "base_task_id", "condition", "canonical_selected_submission",
    "missing_submission", "assignment_provenance",
]
COLLISION_COLUMNS = [
    "project_id", "ls_runtime_task_id", "first_task_id", "collision_task_id",
    "first_base_task_id", "collision_base_task_id", "first_dataset_group",
    "collision_dataset_group", "collision_reason",
]
MERGE_COLUMNS = ["source_export", "runtime_task_count", "sha256", "bytes"]
RAW_MANIFEST_COLUMNS = ["source_path", "snapshot_path", "source_kind", "exists", "bytes", "sha256", "completion_basis"]
DENY_COLUMNS = {
    "gt", "reference", "quality", "iou", "score", "outcome", "worker_outcome", "consensus",
    "medoid", "cluster", "cluster_correctness", "difficulty",
}
DENY_PATHS = ("export_label/", "active_logs/", "analysis_results/post_block2_analysis_pack_20260817_v3/")
TEST_SOURCE_META = {name: {"path": path.as_posix(), "sha256": "test-sha"} for name, path in INPUTS.items()}

SIDECAR_FIELDS = [
    "candidate_annotation_id", "worker_id", "stage", "round_id", "condition", "base_task_id", "task_id",
    "project_id", "ls_runtime_task_id", "experimental_task_context_id", "deployment_pool_id",
    "canonical_selection_status", "assignment_realization_status", "observed_canonical_runtime_source_status",
    "identity_mapping_status", "mapping_status",
    "mapping_reason", "formal_duplicate_status", "duplicate_group_size", "duplicate_decision",
    "process_disposition", "development_admissibility_status", "development_admissibility_reason",
    "appears_in_internal_distribution", "appears_in_internal_distribution_role", "assignment_provenance",
    "candidate_parse_status",
    "candidate_layout_corner_count", "building_scene_id", "dataset_group", "source_export",
    "source_export_sha256", "source_export_provenance_status", "candidate_descriptor_artifact",
    "candidate_descriptor_sha256", "canonical_source_artifact", "canonical_source_sha256",
    "runtime_mapping_artifact", "runtime_mapping_sha256", "assignment_realization_artifact",
    "assignment_realization_sha256", "collision_audit_artifact", "collision_audit_sha256",
    "export_merge_manifest_artifact", "export_merge_manifest_sha256", "project_provenance_artifact",
    "project_provenance_sha256", "raw_snapshot_manifest_artifact", "raw_snapshot_manifest_sha256",
    "closure_manifest_artifact", "closure_manifest_sha256",
]


def rel(path: Path) -> str:
    return path.resolve().relative_to(ROOT.resolve()).as_posix()


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _normalized(path: str) -> str:
    return path.replace("\\", "/").lstrip("./")


def denied_path(path: Path) -> str | None:
    value = _normalized(rel(path)).lower()
    for rule in DENY_PATHS:
        rule = rule.lower().rstrip("/")
        if value == rule or value.startswith(rule + "/"):
            return rule
    return None


def assert_input_allowed(path: Path) -> None:
    if denied_path(path):
        raise PermissionError(f"denied input path: {denied_path(path)}")
    if path.resolve() not in {item.resolve() for item in INPUTS.values()}:
        raise PermissionError(f"input outside allowlist: {rel(path)}")


def validate_projection(columns: Iterable[str]) -> None:
    bad = sorted({
        column for column in columns
        if set(re.findall(r"[a-z0-9]+", column.lower())) & DENY_COLUMNS
    })
    if bad:
        raise PermissionError(f"denied projected columns: {bad}")


def read_csv_projection(path: Path, columns: list[str], trace: list[dict[str, object]] | None = None) -> list[dict[str, str]]:
    assert_input_allowed(path)
    validate_projection(columns)
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.reader(handle)
        header = next(reader)
        missing = sorted(set(columns) - set(header))
        if missing:
            raise ValueError(f"{rel(path)} missing columns: {missing}")
        indexes = {column: header.index(column) for column in columns}
        rows = [{column: values[indexes[column]] for column in columns} for values in reader]
    if trace is not None:
        trace.append({"path": rel(path), "input_kind": "csv_projection", "projected_columns": columns})
    return rows


def read_json(path: Path, trace: list[dict[str, object]] | None = None) -> dict[str, object]:
    assert_input_allowed(path)
    value = json.loads(path.read_text(encoding="utf-8"))
    if trace is not None:
        trace.append({"path": rel(path), "input_kind": "json_identity_metadata", "projected_columns": ["allowlisted_manifest_keys"]})
    return value


def input_metadata(trace: list[dict[str, object]]) -> dict[str, dict[str, str]]:
    result = {}
    for name, path in INPUTS.items():
        assert_input_allowed(path)
        digest = sha256(path)
        trace.append({"path": rel(path), "input_kind": "source_sha256", "projected_columns": []})
        result[name] = {"path": rel(path), "sha256": digest}
    return result


def _index(rows: list[dict[str, str]], key: str | tuple[str, ...]) -> dict[object, list[dict[str, str]]]:
    fields = (key,) if isinstance(key, str) else key
    index: dict[object, list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        index[tuple(row.get(field, "") for field in fields) if len(fields) > 1 else row.get(fields[0], "")].append(row)
    return index


def _one(index: dict[object, list[dict[str, str]]], value: object, label: str, reasons: list[str]) -> dict[str, str] | None:
    matches = index.get(value, [])
    if len(matches) == 1:
        return matches[0]
    reasons.append(f"{label}_{'zero' if not matches else 'many'}")
    return None


def experimental_task_context_id(stage: str, round_id: str, condition: str, base_task_id: str, task_id: str) -> str:
    return hashlib.sha256("\x1f".join((stage, round_id, condition, base_task_id, task_id)).encode()).hexdigest()


def deployment_pool_id(stage: str, round_id: str, condition: str, base_task_id: str, task_id: str, project_id: str, ls_runtime_task_id: str) -> str:
    return hashlib.sha256("\x1f".join((stage, round_id, condition, base_task_id, task_id, project_id, ls_runtime_task_id)).encode()).hexdigest()


def source_sha_not_in_pool_key(pool_id: str, source_export_sha256: str) -> bool:
    return pool_id != hashlib.sha256(source_export_sha256.encode()).hexdigest()


def _true(value: str) -> bool:
    return value.strip().lower() in {"true", "1", "yes"}


def _formal_duplicate_status(canonical: dict[str, str]) -> str:
    worker_duplicate = _true(canonical.get("duplicate_worker_task_submission", ""))
    try:
        group_size = int(canonical.get("duplicate_group_size", "1") or "1")
    except ValueError:
        return "unresolved_or_conflict"
    duplicate_ids = canonical.get("duplicate_annotation_ids", "").strip()
    if not worker_duplicate and group_size <= 1 and not duplicate_ids:
        return "none"
    if (
        not worker_duplicate
        and group_size > 1
        and canonical.get("duplicate_decision", "").strip().lower() == "keep_selected_version"
        and canonical.get("process_disposition", "").strip().lower() == "no_process_penalty"
    ):
        return "keep_selected_version"
    return "unresolved_or_conflict"


def build_identity_rows(
    candidates: list[dict[str, str]],
    canonical: list[dict[str, str]],
    runtime: list[dict[str, str]],
    realization: list[dict[str, str]],
    collisions: list[dict[str, str]],
    source_meta: dict[str, dict[str, str]],
) -> tuple[list[dict[str, str]], Counter]:
    canonical_index = _index(canonical, "canonical_annotation_id")
    runtime_index = _index(runtime, ("project_id", "ls_runtime_task_id", "task_id", "base_task_id", "condition"))
    realization_index = _index(realization, ("worker_id", "task_id", "base_task_id", "condition"))
    candidate_counts = Counter(row.get("candidate_annotation_id", "") for row in candidates)
    collision_keys = set()
    for row in collisions:
        collision_keys.add(tuple(row.get(key, "") for key in ("project_id", "ls_runtime_task_id", "first_task_id", "first_base_task_id", "first_dataset_group")))
        collision_keys.add(tuple(row.get(key, "") for key in ("project_id", "ls_runtime_task_id", "collision_task_id", "collision_base_task_id", "collision_dataset_group")))
    stats = Counter(total=len(candidates))
    rows = []
    for candidate in candidates:
        reasons: list[str] = []
        candidate_id = candidate.get("candidate_annotation_id", "")
        canonical_row = _one(canonical_index, candidate_id, "canonical_annotation_join", reasons)
        if candidate_counts[candidate_id] != 1:
            reasons.append("candidate_annotation_id_duplicate")
        runtime_row = None
        assignment_status = "not_applicable"
        assignment_selected = False
        duplicate_status = "missing_canonical"
        if canonical_row:
            identity_fields = ("worker_id", "stage", "base_task_id")
            for field in identity_fields:
                if candidate.get(field) and candidate[field] != canonical_row.get(field, ""):
                    reasons.append(f"{field}_conflict")
            runtime_key = tuple(canonical_row.get(key, "") for key in ("project_id", "ls_runtime_task_id", "task_id", "base_task_id", "condition"))
            runtime_row = _one(runtime_index, runtime_key, "runtime_mapping_join", reasons)
            realization_key = tuple(canonical_row.get(key, "") for key in ("worker_id", "task_id", "base_task_id", "condition"))
            realization_rows = realization_index.get(realization_key, [])
            if len(realization_rows) == 0:
                assignment_status = "missing"
            elif len(realization_rows) > 1:
                assignment_status = "ambiguous"
            else:
                assignment_status = "matched"
                assignment_selected = _true(realization_rows[0].get("canonical_selected_submission", "")) and not _true(realization_rows[0].get("missing_submission", ""))
            duplicate_status = _formal_duplicate_status(canonical_row)
            if duplicate_status == "unresolved_or_conflict":
                reasons.append("formal_duplicate_unresolved_or_conflict")
            collision_key = tuple(canonical_row.get(key, "") for key in ("project_id", "ls_runtime_task_id", "task_id", "base_task_id", "dataset_group"))
            if collision_key in collision_keys:
                reasons.append("formal_runtime_key_collision")
        selected_status = "formal_canonical_row_present" if canonical_row else "formal_canonical_row_missing_or_ambiguous"
        if canonical_row and assignment_status == "matched" and assignment_selected:
            selected_status = "assignment_realization_selected"
        elif canonical_row and assignment_status == "matched":
            selected_status = "assignment_realization_not_selected"
        elif canonical_row and assignment_status == "ambiguous":
            selected_status = "assignment_realization_ambiguous"
        admissibility_status, admissibility_reason = "not_defined", "eligibility_spec_not_frozen"
        if reasons:
            status = "fail_closed"
            stats["fail_closed"] += 1
        else:
            status = "mapped"
            stats["mapped"] += 1
        if canonical_row and runtime_row:
            context_id = experimental_task_context_id(canonical_row["stage"], canonical_row["round_id"], canonical_row["condition"], canonical_row["base_task_id"], canonical_row["task_id"])
            pool_id = deployment_pool_id(canonical_row["stage"], canonical_row["round_id"], canonical_row["condition"], canonical_row["base_task_id"], canonical_row["task_id"], canonical_row["project_id"], canonical_row["ls_runtime_task_id"])
        else:
            context_id = pool_id = ""
        observed_source_status = "matched" if canonical_row and runtime_row else "missing_or_ambiguous"
        row = {field: "" for field in SIDECAR_FIELDS}
        row.update({
            "candidate_annotation_id": candidate_id,
            "worker_id": candidate.get("worker_id", ""),
            "stage": canonical_row.get("stage", canonical_row.get("round_id", candidate.get("stage", ""))) if canonical_row else candidate.get("stage", ""),
            "round_id": canonical_row.get("round_id", "") if canonical_row else "",
            "condition": canonical_row.get("condition", "") if canonical_row else "",
            "base_task_id": canonical_row.get("base_task_id", "") if canonical_row else "",
            "task_id": canonical_row.get("task_id", "") if canonical_row else "",
            "project_id": canonical_row.get("project_id", "") if canonical_row else "",
            "ls_runtime_task_id": canonical_row.get("ls_runtime_task_id", "") if canonical_row else "",
            "experimental_task_context_id": context_id,
            "deployment_pool_id": pool_id,
            "canonical_selection_status": selected_status,
            "assignment_realization_status": assignment_status,
            "observed_canonical_runtime_source_status": observed_source_status,
            "identity_mapping_status": status,
            "mapping_status": status,
            "mapping_reason": ";".join(sorted(set(reasons))),
            "formal_duplicate_status": duplicate_status,
            "duplicate_group_size": canonical_row.get("duplicate_group_size", "") if canonical_row else "",
            "duplicate_decision": canonical_row.get("duplicate_decision", "") if canonical_row else "",
            "process_disposition": canonical_row.get("process_disposition", "") if canonical_row else "",
            "development_admissibility_status": admissibility_status,
            "development_admissibility_reason": admissibility_reason,
            "appears_in_internal_distribution": canonical_row.get("appears_in_internal_distribution", "") if canonical_row else "",
            "appears_in_internal_distribution_role": "not_an_eligibility_source" if canonical_row else "",
            "assignment_provenance": canonical_row.get("assignment_provenance", "") if canonical_row else "",
            "candidate_parse_status": candidate.get("parse_status", ""),
            "candidate_layout_corner_count": candidate.get("layout_corner_count", ""),
            "building_scene_id": candidate.get("building_scene_id", ""),
            "dataset_group": canonical_row.get("dataset_group", "") if canonical_row else "",
            "source_export": canonical_row.get("source_export", "") if canonical_row else "",
            "source_export_sha256": canonical_row.get("source_export_sha256", "") if canonical_row else "",
            "source_export_provenance_status": "unverified_in_test_fixture" if source_meta is TEST_SOURCE_META else "pending_manifest_check",
            "candidate_descriptor_artifact": source_meta["candidate_descriptors"]["path"],
            "candidate_descriptor_sha256": source_meta["candidate_descriptors"]["sha256"],
            "canonical_source_artifact": canonical_row.get("source_artifact", source_meta["canonical_annotations"]["path"]) if canonical_row else "",
            "canonical_source_sha256": canonical_row.get("source_sha256", source_meta["canonical_annotations"]["sha256"]) if canonical_row else "",
            "runtime_mapping_artifact": source_meta["runtime_mapping"]["path"],
            "runtime_mapping_sha256": source_meta["runtime_mapping"]["sha256"],
            "assignment_realization_artifact": source_meta["assignment_realization"]["path"],
            "assignment_realization_sha256": source_meta["assignment_realization"]["sha256"],
            "collision_audit_artifact": source_meta["runtime_collision_audit"]["path"],
            "collision_audit_sha256": source_meta["runtime_collision_audit"]["sha256"],
            "export_merge_manifest_artifact": source_meta["export_merge_manifest"]["path"],
            "export_merge_manifest_sha256": source_meta["export_merge_manifest"]["sha256"],
            "project_provenance_artifact": source_meta["project_provenance_summary"]["path"],
            "project_provenance_sha256": source_meta["project_provenance_summary"]["sha256"],
            "raw_snapshot_manifest_artifact": source_meta["raw_snapshot_manifest"]["path"],
            "raw_snapshot_manifest_sha256": source_meta["raw_snapshot_manifest"]["sha256"],
            "closure_manifest_artifact": source_meta["collection_closure_manifest"]["path"],
            "closure_manifest_sha256": source_meta["collection_closure_manifest"]["sha256"],
        })
        rows.append(row)
    return rows, stats


def _write_csv(path: Path, rows: list[dict[str, object]], fields: list[str]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def _write_json(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _norm_source_status(canonical: dict[str, str], merge: list[dict[str, str]], raw: list[dict[str, str]]) -> str:
    source = _normalized(canonical.get("source_export", ""))
    merge_rows = [row for row in merge if _normalized(row.get("source_export", "")) == source]
    raw_rows = [row for row in raw if _normalized(row.get("source_path", "")) == source]
    expected = canonical.get("source_export_sha256", "").lower()
    if len(merge_rows) != 1 or len(raw_rows) != 1:
        return "source_manifest_join_fail_closed"
    if merge_rows[0].get("sha256", "").lower() != expected or raw_rows[0].get("sha256", "").lower() != expected:
        return "source_sha_mismatch_fail_closed"
    return "matched"


def _summary_rows(rows: list[dict[str, str]]) -> list[dict[str, object]]:
    groups: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        if row["deployment_pool_id"]:
            groups[row["deployment_pool_id"]].append(row)
    result = []
    for pool_id in sorted(groups):
        group = groups[pool_id]
        observed_valid = [row for row in group if row["candidate_parse_status"].lower() == "valid"]
        strict_valid = [
            row for row in observed_valid
            if row["assignment_realization_status"] == "matched"
        ]
        result.append({
            "deployment_pool_id": pool_id,
            "experimental_task_context_id": group[0]["experimental_task_context_id"],
            "stage": group[0]["stage"],
            "round_id": group[0]["round_id"],
            "condition": group[0]["condition"],
            "dataset_group": group[0]["dataset_group"],
            "building_scene_id": group[0]["building_scene_id"],
            "identity_candidate_count": len(group),
            "observed_geometry_valid_count": len(observed_valid),
            "realization_matched_geometry_valid_count": len(strict_valid),
            "observed_valid_meets_k3": str(len(observed_valid) >= 3),
            "strict_realization_sensitivity_meets_k3": str(len(strict_valid) >= 3),
        })
    return result


def build(output_dir: Path = OUT) -> dict[str, object]:
    trace: list[dict[str, object]] = []
    source_meta = input_metadata(trace)
    candidates = read_csv_projection(CANDIDATE_PATH, CANDIDATE_COLUMNS, trace)
    canonical = read_csv_projection(CANONICAL_PATH, CANONICAL_COLUMNS, trace)
    for row in canonical:
        row["stage"] = row.get("round_id", "")
        row["source_artifact"] = source_meta["canonical_annotations"]["path"]
        row["source_sha256"] = source_meta["canonical_annotations"]["sha256"]
    runtime = read_csv_projection(RUNTIME_PATH, RUNTIME_COLUMNS, trace)
    realization = read_csv_projection(REALIZATION_PATH, REALIZATION_COLUMNS, trace)
    collisions = read_csv_projection(COLLISION_PATH, COLLISION_COLUMNS, trace)
    merge = read_csv_projection(MERGE_PATH, MERGE_COLUMNS, trace)
    raw = read_csv_projection(RAW_MANIFEST_PATH, RAW_MANIFEST_COLUMNS, trace)
    project_summary = read_json(PROJECT_SUMMARY_PATH, trace)
    closure = read_json(CLOSURE_PATH, trace)
    source_status = {row.get("source_export", ""): _norm_source_status(row, merge, raw) for row in canonical}
    rows, stats = build_identity_rows(candidates, canonical, runtime, realization, collisions, source_meta)
    for row in rows:
        if row["source_export"]:
            row["source_export_provenance_status"] = source_status.get(row["source_export"], "source_manifest_join_fail_closed")
            if row["source_export_provenance_status"] != "matched" and row["identity_mapping_status"] == "mapped":
                row["identity_mapping_status"] = "fail_closed"
                row["mapping_status"] = "fail_closed"
                row["mapping_reason"] = ";".join(filter(None, [row["mapping_reason"], row["source_export_provenance_status"]]))
                stats["mapped"] -= 1
                stats["fail_closed"] += 1
            row["observed_canonical_runtime_source_status"] = (
                "matched" if row["identity_mapping_status"] == "mapped" and row["source_export_provenance_status"] == "matched"
                else "fail_closed"
            )
    summary = _summary_rows(rows)
    output_dir.mkdir(parents=True, exist_ok=True)
    sidecar_path = output_dir / "A4_CANDIDATE_DEPLOYMENT_POOL_IDENTITY_C1_v1.csv"
    summary_path = output_dir / "A4_DEPLOYMENT_POOL_SUPPORT_SUMMARY.csv"
    provenance_path = output_dir / "INPUT_ACCESS_AND_PROVENANCE.json"
    report_path = output_dir / "A4_DEPLOYMENT_POOL_IDENTITY_REPORT.md"
    _write_csv(sidecar_path, rows, SIDECAR_FIELDS)
    _write_csv(summary_path, summary, list(summary[0]) if summary else ["deployment_pool_id", "identity_candidate_count"])
    provenance = {
        "schema_version": "a4_deployment_pool_identity_input_access_v1",
        "allowed_inputs": {name: {"path": value["path"], "sha256": value["sha256"]} for name, value in source_meta.items()},
        "deny_paths": list(DENY_PATHS),
        "deny_columns": sorted(DENY_COLUMNS),
        "trace": trace,
        "candidate_count": len(candidates),
        "formal_canonical_count": len(canonical),
        "formal_runtime_count": len(runtime),
        "assignment_realization_count": len(realization),
        "collision_count": len(collisions),
        "export_merge_count": len(merge),
        "project_summary_annotation_count": project_summary.get("annotation_count", ""),
        "closure_schema_version": closure.get("schema_version", ""),
        "closure_window_closed": closure.get("collection_window_closed", ""),
        "consumed_gt_reference_quality_outcome_values": False,
    }
    _write_json(provenance_path, provenance)
    status = "A4_POOL_IDENTITY_READY" if stats["fail_closed"] == 0 else "A4_POOL_IDENTITY_PARTIAL"
    eligibility_status = "A4_ELIGIBILITY_SPEC_INCOMPLETE"
    observed_valid_rows = [row for row in rows if row["identity_mapping_status"] == "mapped" and row["candidate_parse_status"].lower() == "valid"]
    strict_valid_rows = [row for row in observed_valid_rows if row["assignment_realization_status"] == "matched"]
    condition_counts = Counter(row["condition"] for row in rows if row["identity_mapping_status"] == "mapped")
    role_counts = Counter(row["dataset_group"] for row in rows if row["identity_mapping_status"] == "mapped")
    observed_support_counts = Counter(row["observed_geometry_valid_count"] for row in summary)
    strict_support_counts = Counter(row["realization_matched_geometry_valid_count"] for row in summary)
    admissibility_counts = Counter(row["appears_in_internal_distribution"] for row in rows)
    assignment_counts = Counter(row["assignment_realization_status"] for row in rows)
    duplicate_counts = Counter(row["formal_duplicate_status"] for row in rows)
    report = "\n".join([
        "# A4 deployment pool identity C1 v1",
        "",
        f"- Identity status: **{status}**",
        f"- Eligibility status: **{eligibility_status}**",
        f"- Candidates: {len(candidates)}; identity mapped: {stats['mapped']}; identity fail-closed: {stats['fail_closed']}.",
        "- Development eligibility is **not defined** in this identity layer; `eligibility_spec_not_frozen` is emitted for every candidate.",
        f"- Observed geometry-valid candidates: {len(observed_valid_rows)}; pool support: {dict(sorted(observed_support_counts.items()))}; pools meeting k=3: {sum(row['observed_valid_meets_k3'] == 'True' for row in summary)} / {len(summary)}.",
        f"- Strict realization-matched geometry-valid sensitivity: {len(strict_valid_rows)}; pool support: {dict(sorted(strict_support_counts.items()))}; pools meeting k=3: {sum(row['strict_realization_sensitivity_meets_k3'] == 'True' for row in summary)} / {len(summary)}.",
        f"- Formal appears_in_internal_distribution values: {dict(sorted(admissibility_counts.items()))}; role: not_an_eligibility_source.",
        f"- Assignment realization status: {dict(sorted(assignment_counts.items()))}; assignment status does not gate identity and is reported as provenance sensitivity.",
        f"- Formal duplicate status: {dict(sorted(duplicate_counts.items()))}; keep_selected_version does not gate identity.",
        f"- Formal canonical join: {len(candidates)} candidate rows were processed against the SHA-bound formal canonical sidecar.",
        f"- Identity deployment pools: {len(summary)}; all identity pools, including zero strict-sensitivity pools, are retained.",
        f"- Condition distribution: {dict(sorted(condition_counts.items()))}.",
        f"- Role distribution: {dict(sorted(role_counts.items()))}.",
        "- Pool key: SHA-256(stage, round_id, condition, base_task_id, task_id, project_id, ls_runtime_task_id); source export SHA is provenance only.",
        "- No GT/reference/quality/outcome/holdout values were consumed; deny paths and deny columns are enforced at the input layer.",
        "- No selector, performance estimate, contract, SAP, routing, or frozen input was changed.",
    ]) + "\n"
    report_path.write_text(report, encoding="utf-8")
    output_files = [sidecar_path, summary_path, report_path, provenance_path]
    manifest = {
        "schema_version": "a4_deployment_pool_identity_manifest_v1",
        "status": status,
        "identity_status": status,
        "eligibility_status": eligibility_status,
        "generator": {"path": rel(Path(__file__)), "sha256": sha256(Path(__file__))},
        "inputs": source_meta,
        "output_sha256": {rel(path): sha256(path) for path in output_files},
        "row_counts": {
            "candidate_identity": len(rows),
            "identity_pools": len(summary),
            "observed_geometry_valid_candidates": len(observed_valid_rows),
            "realization_matched_geometry_valid_candidates": len(strict_valid_rows),
        },
        "join_counts": dict(stats),
        "observed_valid_support_distribution": dict(sorted(observed_support_counts.items())),
        "strict_realization_sensitivity_support_distribution": dict(sorted(strict_support_counts.items())),
        "appears_in_internal_distribution_is_eligibility_source": False,
        "pool_key_fields": ["stage", "round_id", "condition", "base_task_id", "task_id", "project_id", "ls_runtime_task_id"],
        "source_export_sha_in_pool_key": False,
        "read_only_boundaries": {"v2_modified": False, "contract_modified": False, "sap_modified": False, "routing_modified": False, "frozen_inputs_modified": False, "selector_implemented": False, "holdout_effect_read": False},
    }
    _write_json(output_dir / "analysis_manifest.json", manifest)
    return manifest


def main() -> int:
    build()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
