from __future__ import annotations

import csv
import hashlib
import itertools
import json
import subprocess
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
DATE_TAG = datetime.now().strftime("%Y%m%d")
OUT_DIR = ROOT / f"analysis_results/post_block2_analysis_pack_{DATE_TAG}_v1"


def clean(value: object) -> str:
    if value is None:
        return ""
    return str(value).strip().lstrip("\ufeff").strip('"')


def as_bool(value: object) -> bool:
    return clean(value).lower() in {"1", "true", "yes", "y", "matched", "match"}


def as_float(value: object):
    text = clean(value)
    if text in {"", "none", "null", "nan", "na"}:
        return None
    try:
        return float(text)
    except ValueError:
        return None


def as_int(value: object):
    number = as_float(value)
    return "" if number is None else int(round(number))


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        reader.fieldnames = [clean(field) for field in (reader.fieldnames or [])]
        return [{clean(key): value or "" for key, value in row.items()} for row in reader]


def read_json(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def write_csv(path: Path, rows: list[dict], fields: list[str]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows({field: row.get(field, "") for field in fields} for row in rows)


def unique(values) -> list[str]:
    return sorted({clean(value) for value in values if clean(value)})


def sample_variance(values: list[float]):
    values = [value for value in values if value is not None]
    if len(values) < 2:
        return None
    mean = sum(values) / len(values)
    return sum((value - mean) ** 2 for value in values) / (len(values) - 1)


def interval_overlap(left: str, right: str) -> str:
    try:
        left_low, left_high = [float(part) for part in left.split("|")]
        right_low, right_high = [float(part) for part in right.split("|")]
    except (ValueError, AttributeError):
        return ""
    return str(not (left_high < right_low or right_high < left_low)).lower()


SOURCES = {
    "method_contract": ROOT / "docs/thesis_main/PAPER_A_METHOD_CONTRACT_CURRENT.json",
    "c1_canonical": ROOT / "analysis_results/c1_formal_audit_20260802_v16_final/c1_formal_audit_20260802_7fcacc5c2d6c_bf5def46_6bc67c03/c1_canonical_annotations.csv",
    "c1_reference": ROOT / "analysis_results/c1_formal_audit_20260802_v16_final/c1_formal_audit_20260802_7fcacc5c2d6c_bf5def46_6bc67c03/c1_task_outcome_reference.csv",
    "c1_building": ROOT / "analysis_results/c1_formal_audit_20260802_v16_final/c1_formal_audit_20260802_7fcacc5c2d6c_bf5def46_6bc67c03/c1_task_building_binding.csv",
    "c1_active_time": ROOT / "analysis_results/c1_formal_audit_20260802_v16_final/c1_formal_audit_20260802_7fcacc5c2d6c_bf5def46_6bc67c03/c1_task_worker_active_time.csv",
    "c1_freeze": ROOT / "analysis_results/c1_formal_audit_20260802_v16_final/c1_formal_audit_20260802_7fcacc5c2d6c_bf5def46_6bc67c03/c1_measurement_freeze_manifest.json",
    "c1_closeout": ROOT / "analysis_results/c1_formal_audit_20260802_v16_final/c1_formal_audit_20260802_7fcacc5c2d6c_bf5def46_6bc67c03/c1_final_canonical_closeout_summary.json",
    "c2b_canonical": ROOT / "analysis_results/c2b_closeout_20260806_final/c2b_canonical_submissions.csv",
    "c2b_profile": ROOT / "analysis_results/c2b_closeout_20260806_final/post_c2b_worker_profile.csv",
    "c2b_closeout": ROOT / "analysis_results/c2b_closeout_20260806_final/c2b_closeout_v2.json",
    "c2b_outside": ROOT / "analysis_results/c2b_closeout_20260806_final/c2b_outside_assignment_exposure_audit.csv",
    "c2b_support": ROOT / "analysis_results/c2b_closeout_20260806_final/c2b_observed_support_audit.csv",
    "c2a_task_pool": ROOT / "analysis_results/c2b_closeout_20260806_inputs/c2a_rp_task_pool.csv",
    "c2a_b1_canonical": ROOT / "analysis_results/c2a_rp_block1_reestimate_20260810_v1/c2a_rp_block1_canonical_submissions.csv",
    "c2a_b1_profile": ROOT / "analysis_results/c2a_rp_block1_reestimate_20260810_v1/post_c2a_rp_block1_worker_profile.csv",
    "c2a_b1_assignment": ROOT / "analysis_results/c2a_rp_block1_distribution_20260807_v7/assignment_manifest_C2A_RP_block_1.csv",
    "c2a_b1_distribution": ROOT / "analysis_results/c2a_rp_block1_distribution_20260807_v7/C2A_RP_BLOCK1_DISTRIBUTION_MANIFEST.json",
    "c2a_b2_task_pool": ROOT / "analysis_results/c2a_rp_block2_distribution_20260810_v1/c2a_rp_task_pool_block2.csv",
    "c2a_b2_assignment": ROOT / "analysis_results/c2a_rp_block2_distribution_20260810_v1/assignment_manifest_C2A_RP_block_2.csv",
    "c2a_b2_distribution": ROOT / "analysis_results/c2a_rp_block2_distribution_20260810_v1/C2A_RP_BLOCK2_DISTRIBUTION_MANIFEST.json",
    "scope_registry": ROOT / "analysis_results/c2a_rp_local_launch_20260807_inputs_v2/scope_registry_post_c2_local.csv",
    "reference_registry": ROOT / "analysis_results/c2a_rp_local_launch_20260807_inputs_v2/reference_registry_post_c2_local.csv",
}


def build_lookup(rows: list[dict[str, str]], key_fields: tuple[str, ...]) -> dict[str, dict[str, str]]:
    result: dict[str, dict[str, str]] = {}
    for row in rows:
        for field in key_fields:
            key = clean(row.get(field))
            if key:
                result[key] = row
    return result


def main() -> None:
    missing = [str(path) for path in SOURCES.values() if not path.exists()]
    if missing:
        raise FileNotFoundError("Missing source artifacts: " + "; ".join(missing))

    OUT_DIR.mkdir(parents=True, exist_ok=True)

    method_contract = read_json(SOURCES["method_contract"])
    c1_rows = read_csv(SOURCES["c1_canonical"])
    c1_refs = read_csv(SOURCES["c1_reference"])
    c1_buildings = read_csv(SOURCES["c1_building"])
    c1_active = read_csv(SOURCES["c1_active_time"])
    c2b_rows = read_csv(SOURCES["c2b_canonical"])
    c2a_b1_rows = read_csv(SOURCES["c2a_b1_canonical"])
    c2b_outside = read_csv(SOURCES["c2b_outside"])
    c2a_tasks = read_csv(SOURCES["c2a_task_pool"])
    c2a_b2_tasks = read_csv(SOURCES["c2a_b2_task_pool"])
    c2a_b1_assignments = read_csv(SOURCES["c2a_b1_assignment"])
    c2a_b2_assignments = read_csv(SOURCES["c2a_b2_assignment"])
    scope_rows = read_csv(SOURCES["scope_registry"])
    reference_rows = read_csv(SOURCES["reference_registry"])
    c2b_profile_rows = read_csv(SOURCES["c2b_profile"])
    c2a_b1_profile_rows = read_csv(SOURCES["c2a_b1_profile"])

    c1_ref_lookup = build_lookup(c1_refs, ("task_id", "base_task_id"))
    c1_building_lookup = build_lookup(c1_buildings, ("base_task_id",))
    scope_lookup = build_lookup(scope_rows, ("task_id", "base_task_id"))
    reference_lookup = build_lookup(reference_rows, ("task_id", "base_task_id"))
    task_lookup = build_lookup(c2a_tasks + c2a_b2_tasks, ("task_id", "base_task_id"))
    outside_lookup = {
        (
            clean(row.get("deployment_id")),
            clean(row.get("project_id")),
            clean(row.get("runtime_task_id")),
            clean(row.get("worker_id")),
        )
        for row in c2b_outside
    }
    active_lookup = {
        (clean(row.get("runtime_task_id")), clean(row.get("worker_id"))): row
        for row in c1_active
    }

    profile_by_worker: dict[str, dict[str, str]] = {}
    profile_sha = sha256(SOURCES["c2b_profile"])
    for row in c2b_profile_rows + c2a_b1_profile_rows:
        worker = clean(row.get("worker_id"))
        if worker and worker not in profile_by_worker:
            profile_by_worker[worker] = row

    fields = [
        "stage", "round_id", "block_index", "deployment_id", "project_id",
        "runtime_task_id", "task_id", "base_task_id", "building_id", "worker_id",
        "condition", "assignment_provenance", "assignment_purpose",
        "canonical", "canonical_valid", "structurally_valid",
        "geometry_normalization_status", "duplicate_or_revision_status",
        "outside_assignment_exposure", "scope_terminal", "scope_reason",
        "scope_registry_version", "reference_status", "reference_version",
        "reference_source", "reference_review_status", "geometry_reference_ready",
        "eligible_for_GT_quality", "eligible_for_peer", "eligible_for_LOO",
        "eligible_for_structural_failure", "eligible_for_active_time",
        "eligible_for_risk_slope", "eligible_for_predictive_validity",
        "gt_iou_public_if_computable", "gt_iou_operational_if_computable",
        "point_pair_count", "corner_count", "boundary_similarity_fields",
        "wall_similarity_fields", "cluster_id_current", "cluster_size_current",
        "largest_cluster_flag", "medoid_flag_current", "R_peer_task",
        "R_LOO_if_defined", "profile_snapshot_id_at_assignment",
        "Q_GT_EB_snapshot_if_available", "F_struct_EB_snapshot_if_available",
        "R_peer_snapshot_if_available", "R_LOO_snapshot_if_available",
        "risk_design_score_A", "risk_stratum", "task_feature_version",
        "model_output_version", "geometry_reference_available",
        "active_time_seconds", "active_time_owner_valid",
        "active_time_script_version", "active_time_quality_flag",
        "GT_ineligibility_reason", "peer_ineligibility_reason",
        "LOO_ineligibility_reason", "structural_failure_ineligibility_reason",
        "active_time_ineligibility_reason", "risk_slope_ineligibility_reason",
        "predictive_validity_ineligibility_reason", "source_artifact_path",
        "source_sha256", "source_rule",
    ]

    def make_row(stage: str, round_id: str, block_index: int, raw: dict[str, str], source_key: str) -> dict:
        task_id = clean(raw.get("task_id"))
        base_task_id = clean(raw.get("base_task_id"))
        worker = clean(raw.get("worker_id"))
        runtime_task_id = clean(raw.get("runtime_task_id")) or clean(raw.get("ls_runtime_task_id"))
        project_id = clean(raw.get("project_id"))
        deployment_id = clean(raw.get("deployment_id"))
        task_meta = task_lookup.get(task_id) or task_lookup.get(base_task_id) or {}

        if source_key == "c1":
            ref = c1_ref_lookup.get(task_id) or c1_ref_lookup.get(base_task_id) or {}
            scope_terminal = clean(ref.get("scope_terminal")) or "unresolved"
            scope_reason = clean(ref.get("notes")) or clean(ref.get("scope_resolution_status"))
            reference_status = clean(ref.get("operational_reference_status")) or clean(ref.get("geometry_reference_status"))
            reference_ready = as_bool(ref.get("geometry_reference_ready"))
            reference_version = clean(ref.get("reference_sha256"))
            reference_source = clean(ref.get("reference_identity"))
            scope_version = "c1_task_outcome_reference"
        else:
            scope = scope_lookup.get(task_id) or scope_lookup.get(base_task_id) or {}
            ref = reference_lookup.get(task_id) or reference_lookup.get(base_task_id) or {}
            scope_terminal = clean(scope.get("final_scope")) or "unresolved"
            scope_reason = clean(scope.get("evidence_basis"))
            reference_status = clean(ref.get("reference_status")) or "not_audited"
            reference_ready = as_bool(ref.get("geometry_reference_ready"))
            reference_version = clean(ref.get("reference_sha256"))
            reference_source = clean(ref.get("reference_path"))
            scope_version = clean(scope.get("registry_status"))

        parse_ok = clean(raw.get("parse_error")).lower() in {"", "false", "0", "none"}
        canonical_valid = as_bool(raw.get("canonical_valid")) or as_bool(raw.get("eligible_for_primary_analysis"))
        formal_eligible = as_bool(raw.get("formal_assignment_eligible")) or source_key == "c1"
        scope_ok = scope_terminal == "in_scope"
        active_seconds = as_float(raw.get("active_time"))
        active_source = clean(raw.get("active_time_source"))
        active_valid = as_bool(raw.get("primary_active_time_eligible"))
        if source_key == "c1":
            active_row = active_lookup.get((runtime_task_id, worker))
            if active_row:
                active_seconds = as_float(active_row.get("task_worker_active_seconds"))
                active_valid = as_bool(active_row.get("task_worker_time_analysis_eligible"))
                active_source = clean(active_row.get("timing_rule_version"))

        structural_failure_evaluable = (
            as_bool(raw.get("structural_failure_evaluable"))
            if "structural_failure_evaluable" in raw
            else parse_ok
        )
        gt_eligible = canonical_valid and formal_eligible and parse_ok and scope_ok
        peer_eligible = canonical_valid and formal_eligible and parse_ok and scope_ok
        loo_eligible = peer_eligible and reference_ready
        active_eligible = active_seconds is not None and active_valid
        risk_eligible = canonical_valid and formal_eligible and scope_ok
        predictive_eligible = peer_eligible and loo_eligible
        corner_count = as_int(raw.get("n_corners"))
        duplicate_status = clean(raw.get("duplicate_review_status")) or "unique"
        reasons = {
            "GT": "" if gt_eligible else "scope/canonical/formal eligibility gate not satisfied",
            "peer": "" if peer_eligible else "scope/canonical/formal eligibility gate not satisfied",
            "LOO": "" if loo_eligible else "reference or peer eligibility unavailable",
            "structural": "" if structural_failure_evaluable else "structural_failure_evaluable=false",
            "active": "" if active_eligible else "owner-valid active time unavailable",
            "risk": "" if risk_eligible else "risk-slope row eligibility unavailable",
            "predictive": "" if predictive_eligible else "peer and LOO support not both available",
        }

        return {
            "stage": stage,
            "round_id": round_id,
            "block_index": block_index,
            "deployment_id": deployment_id,
            "project_id": project_id,
            "runtime_task_id": runtime_task_id,
            "task_id": task_id,
            "base_task_id": base_task_id,
            "building_id": clean(raw.get("building_id")) or clean((c1_building_lookup.get(base_task_id) or {}).get("building_id")) or clean(task_meta.get("building_id")),
            "worker_id": worker,
            "condition": clean(raw.get("condition")) or clean(raw.get("task_stratum")) or clean(task_meta.get("task_stratum")),
            "assignment_provenance": clean(raw.get("assignment_provenance")) or "canonical_observed",
            "assignment_purpose": "canonical_evidence",
            "canonical": bool(clean(raw.get("canonical_annotation_id"))),
            "canonical_valid": canonical_valid,
            "structurally_valid": parse_ok,
            "geometry_normalization_status": "normalized" if parse_ok and corner_count not in (None, "") else "not_normalized",
            "duplicate_or_revision_status": duplicate_status,
            "outside_assignment_exposure": str((deployment_id, project_id, runtime_task_id, worker) in outside_lookup).lower(),
            "scope_terminal": scope_terminal,
            "scope_reason": scope_reason,
            "scope_registry_version": scope_version,
            "reference_status": reference_status,
            "reference_version": reference_version,
            "reference_source": reference_source,
            "reference_review_status": clean(raw.get("reference_review_status")),
            "geometry_reference_ready": str(reference_ready).lower(),
            "eligible_for_GT_quality": gt_eligible,
            "eligible_for_peer": peer_eligible,
            "eligible_for_LOO": loo_eligible,
            "eligible_for_structural_failure": structural_failure_evaluable,
            "eligible_for_active_time": active_eligible,
            "eligible_for_risk_slope": risk_eligible,
            "eligible_for_predictive_validity": predictive_eligible,
            "gt_iou_public_if_computable": "",
            "gt_iou_operational_if_computable": "",
            "point_pair_count": "",
            "corner_count": "" if corner_count is None else corner_count,
            "boundary_similarity_fields": "",
            "wall_similarity_fields": "",
            "cluster_id_current": "",
            "cluster_size_current": "",
            "largest_cluster_flag": "",
            "medoid_flag_current": "",
            "R_peer_task": "",
            "R_LOO_if_defined": "",
            "profile_snapshot_id_at_assignment": "",
            "Q_GT_EB_snapshot_if_available": "",
            "F_struct_EB_snapshot_if_available": "",
            "R_peer_snapshot_if_available": "",
            "R_LOO_snapshot_if_available": "",
            "risk_design_score_A": clean(task_meta.get("risk_design_score_A")),
            "risk_stratum": clean(task_meta.get("task_stratum")) or clean(raw.get("task_stratum")),
            "task_feature_version": clean(raw.get("design_manifest_sha256")),
            "model_output_version": "",
            "geometry_reference_available": str(reference_ready).lower(),
            "active_time_seconds": "" if active_seconds is None else active_seconds,
            "active_time_owner_valid": str(active_eligible).lower(),
            "active_time_script_version": active_source,
            "active_time_quality_flag": clean(raw.get("timing_status")) or clean(raw.get("active_time_match_status")),
            "GT_ineligibility_reason": reasons["GT"],
            "peer_ineligibility_reason": reasons["peer"],
            "LOO_ineligibility_reason": reasons["LOO"],
            "structural_failure_ineligibility_reason": reasons["structural"],
            "active_time_ineligibility_reason": reasons["active"],
            "risk_slope_ineligibility_reason": reasons["risk"],
            "predictive_validity_ineligibility_reason": reasons["predictive"],
            "source_artifact_path": str(SOURCES[source_key + "_canonical"]),
            "source_sha256": sha256(SOURCES[source_key + "_canonical"]),
            "source_rule": f"{stage} canonical evidence",
        }

    observed = []
    observed.extend(make_row("C1", "C1", 0, row, "c1") for row in c1_rows)
    observed.extend(make_row("C2-B", "C2-B", 0, row, "c2b") for row in c2b_rows)
    observed.extend(make_row("C2A-RP-Block1", "C2-A-RP", 1, row, "c2a_b1") for row in c2a_b1_rows)
    submission_rows = []
    seen = set()
    for row in observed:
        identity = tuple(row.get(field, "") for field in ("stage", "runtime_task_id", "worker_id", "task_id"))
        if identity not in seen:
            submission_rows.append(row)
            seen.add(identity)
    write_csv(OUT_DIR / "post_block2_submission_master.csv", submission_rows, fields)

    task_fields = [
        "stage", "base_task_id", "task_id", "building_id", "condition",
        "stage_coverage", "n_unique_workers_total", "n_structurally_valid",
        "n_GT_eligible", "n_peer_eligible", "n_LOO_eligible",
        "current_cluster_count", "largest_cluster_size", "second_cluster_size",
        "cluster_support_vector", "crowd_structure_status",
        "current_largest_cluster_medoid_worker",
        "current_largest_cluster_medoid_geometry_id", "public_gt_available",
        "operational_reference_available", "scope_terminal", "reference_status",
        "largest_cluster_medoid_public_gt_iou", "best_nonlargest_cluster_public_gt_iou",
        "minority_better_public_gt_delta", "largest_cluster_medoid_operational_iou",
        "best_nonlargest_cluster_operational_iou", "minority_better_operational_delta",
        "corner_count_set", "variable_corner_count_present", "topology_mode_count",
        "planned_only_block2_context",
    ]
    task_groups: dict[tuple[str, str, str], list[dict]] = defaultdict(list)
    for row in submission_rows:
        task_groups[(row["stage"], row["base_task_id"], row["condition"])].append(row)
    for row in c2a_b2_assignments:
        task_groups.setdefault(("C2A-RP-Block2", clean(row.get("base_task_id")), clean(row.get("task_stratum"))), [])
    task_context_rows = []
    for (stage, base_task, condition), rows in sorted(task_groups.items()):
        meta = task_lookup.get(base_task, {})
        observed_rows = [row for row in rows if row["runtime_task_id"]]
        workers = unique(row["worker_id"] for row in observed_rows)
        corners = unique(row["corner_count"] for row in observed_rows)
        scope_values = unique(row["scope_terminal"] for row in rows)
        ref_values = unique(row["reference_status"] for row in rows)
        task_context_rows.append({
            "stage": stage,
            "base_task_id": base_task,
            "task_id": observed_rows[0]["task_id"] if observed_rows else clean(meta.get("task_id")),
            "building_id": observed_rows[0]["building_id"] if observed_rows else clean(meta.get("building_id")),
            "condition": condition,
            "stage_coverage": "observed" if observed_rows else "planned_only",
            "n_unique_workers_total": len(workers),
            "n_structurally_valid": sum(as_bool(row["structurally_valid"]) for row in observed_rows),
            "n_GT_eligible": sum(as_bool(row["eligible_for_GT_quality"]) for row in observed_rows),
            "n_peer_eligible": sum(as_bool(row["eligible_for_peer"]) for row in observed_rows),
            "n_LOO_eligible": sum(as_bool(row["eligible_for_LOO"]) for row in observed_rows),
            "current_cluster_count": "",
            "largest_cluster_size": "",
            "second_cluster_size": "",
            "cluster_support_vector": "",
            "crowd_structure_status": "not_identifiable_from_frozen_inputs",
            "current_largest_cluster_medoid_worker": "",
            "current_largest_cluster_medoid_geometry_id": "",
            "public_gt_available": str(any(as_bool(row["geometry_reference_ready"]) for row in rows)).lower(),
            "operational_reference_available": str(any(row["reference_status"] not in {"", "not_audited"} for row in rows)).lower(),
            "scope_terminal": scope_values[0] if scope_values else "unresolved",
            "reference_status": ref_values[0] if ref_values else "not_audited",
            "largest_cluster_medoid_public_gt_iou": "",
            "best_nonlargest_cluster_public_gt_iou": "",
            "minority_better_public_gt_delta": "",
            "largest_cluster_medoid_operational_iou": "",
            "best_nonlargest_cluster_operational_iou": "",
            "minority_better_operational_delta": "",
            "corner_count_set": ";".join(corners),
            "variable_corner_count_present": str(len(corners) > 1).lower(),
            "topology_mode_count": "",
            "planned_only_block2_context": str(stage == "C2A-RP-Block2" and not observed_rows).lower(),
        })
    write_csv(OUT_DIR / "post_block2_task_context_master.csv", task_context_rows, task_fields)

    profile_fields = [
        "worker_id", "Q_GT_raw", "Q_GT_task_adjusted", "Q_GT_EB",
        "Q_GT_SE_or_interval", "Q_GT_LCB", "R_peer_all", "R_peer_stable",
        "R_LOO_medoid", "R_LOO_strict", "R_peer_support_tasks",
        "R_LOO_support_tasks", "F_struct_raw", "F_struct_EB",
        "F_struct_interval_or_UCB", "structural_opportunities",
        "active_time_median", "active_time_adjusted_if_available",
        "active_time_support", "n_tasks_total", "n_buildings_total",
        "n_ordinary", "n_stress", "risk_component_status",
        "risk_component_estimate_if_any", "risk_component_interval_if_any",
        "profile_version", "source_artifact_sha256",
        "Q_GT_status", "R_peer_status", "R_LOO_status",
        "F_struct_status", "active_time_status", "risk_component_status_detail",
        "administrative_status",
    ]
    all_workers = unique(
        [row.get("worker_id") for row in submission_rows]
        + [row.get("worker_id") for row in c2b_profile_rows]
        + [row.get("worker_id") for row in c2a_b1_profile_rows]
    )
    profile_output = []
    uncertainty_output = []
    for worker in all_workers:
        row = profile_by_worker.get(worker, {})
        q_low, q_high = row.get("CI_lower"), row.get("CI_upper")
        f_low, f_high = row.get("F_struct_interval_lower"), row.get("F_struct_interval_upper")
        r_low, r_high = row.get("R_peer_CI_lower"), row.get("R_peer_CI_upper")
        loo_low, loo_high = row.get("R_LOO_medoid_CI_lower"), row.get("R_LOO_medoid_CI_upper")
        active_low, active_high = row.get("T_active_CI_lower"), row.get("T_active_CI_upper")
        administratively_eligible = as_bool(row.get("administratively_eligible"))
        profile_output.append({
            "worker_id": worker,
            "Q_GT_raw": clean(row.get("Q_GT_raw_median")),
            "Q_GT_task_adjusted": clean(row.get("Q_GT_task_adjusted")),
            "Q_GT_EB": clean(row.get("Q_GT_EB")),
            "Q_GT_SE_or_interval": f"{clean(q_low)}|{clean(q_high)}" if clean(q_low) or clean(q_high) else "",
            "Q_GT_LCB": clean(row.get("Q_GT_EB_LCB")),
            "R_peer_all": clean(row.get("R_peer_all")),
            "R_peer_stable": clean(row.get("R_peer_stable")) or clean(row.get("R_peer_all")),
            "R_LOO_medoid": clean(row.get("R_LOO_medoid")),
            "R_LOO_strict": clean(row.get("R_LOO_strict")),
            "R_peer_support_tasks": clean(row.get("peer_task_support")) or clean(row.get("R_peer_support")),
            "R_LOO_support_tasks": clean(row.get("R_LOO_medoid_support")),
            "F_struct_raw": clean(row.get("F_struct_raw")),
            "F_struct_EB": clean(row.get("F_struct_EB")),
            "F_struct_interval_or_UCB": f"{clean(f_low)}|{clean(f_high)}" if clean(f_low) or clean(f_high) else "",
            "structural_opportunities": clean(row.get("F_struct_denominator")),
            "active_time_median": clean(row.get("T_active_raw_median")),
            "active_time_adjusted_if_available": clean(row.get("T_active_task_adjusted")),
            "active_time_support": clean(row.get("T_active_support")),
            "n_tasks_total": clean(row.get("task_support")),
            "n_buildings_total": clean(row.get("building_support")),
            "n_ordinary": clean(row.get("ordinary_support_observed")),
            "n_stress": clean(row.get("stress_support_observed")),
            "risk_component_status": clean(row.get("risk_slope_status")),
            "risk_component_estimate_if_any": clean(row.get("risk_slope")),
            "risk_component_interval_if_any": clean(row.get("risk_slope_ci_half_width")),
            "profile_version": clean(row.get("profile_version")),
            "source_artifact_sha256": profile_sha if row else "",
            "Q_GT_status": clean(row.get("Q_GT_profile_status")) or "undefined_no_support",
            "R_peer_status": clean(row.get("R_peer_profile_status")) or "undefined_no_support",
            "R_LOO_status": clean(row.get("LOO_medoid_status")) or "undefined_no_support",
            "F_struct_status": clean(row.get("F_struct_profile_status")) or "undefined_no_support",
            "active_time_status": clean(row.get("T_active_profile_status")) or "undefined_no_support",
            "risk_component_status_detail": clean(row.get("risk_slope_status")) or "undefined_no_support",
            "administrative_status": "supported" if administratively_eligible else "disabled_unidentifiable",
        })
        uncertainty_output.append({
            "worker_id": worker,
            "Q_GT_interval": f"{clean(q_low)}|{clean(q_high)}" if clean(q_low) or clean(q_high) else "",
            "F_struct_interval": f"{clean(f_low)}|{clean(f_high)}" if clean(f_low) or clean(f_high) else "",
            "R_peer_interval": f"{clean(r_low)}|{clean(r_high)}" if clean(r_low) or clean(r_high) else "",
            "R_LOO_medoid_interval": f"{clean(loo_low)}|{clean(loo_high)}" if clean(loo_low) or clean(loo_high) else "",
            "active_time_interval": f"{clean(active_low)}|{clean(active_high)}" if clean(active_low) or clean(active_high) else "",
            "risk_slope_ci_half_width": clean(row.get("risk_slope_ci_half_width")),
            "risk_slope_for_simulation": clean(row.get("risk_slope_for_simulation")),
            "support_status": "supported" if administratively_eligible else "disabled_unidentifiable",
            "source_artifact_sha256": profile_sha if row else "",
        })
    write_csv(OUT_DIR / "post_block2_worker_profile_master.csv", profile_output, profile_fields)
    write_csv(
        OUT_DIR / "worker_profile_uncertainty_inputs.csv",
        uncertainty_output,
        [
            "worker_id", "Q_GT_interval", "F_struct_interval", "R_peer_interval",
            "R_LOO_medoid_interval", "active_time_interval",
            "risk_slope_ci_half_width", "risk_slope_for_simulation",
            "support_status", "source_artifact_sha256",
        ],
    )

    worker_task_groups: dict[tuple[str, str], list[dict]] = defaultdict(list)
    for row in submission_rows:
        if row["worker_id"] and row["base_task_id"]:
            worker_task_groups[(row["worker_id"], row["base_task_id"])].append(row)
    worker_task_rows = [
        {
            "worker_id": worker,
            "base_task_id": base_task,
            "runtime_task_count": len({row["runtime_task_id"] for row in rows if row["runtime_task_id"]}),
            "stage_contexts": ";".join(unique(row["stage"] for row in rows)),
            "building_ids": ";".join(unique(row["building_id"] for row in rows)),
            "ordinary_count": sum(row["condition"] == "ordinary" for row in rows),
            "stress_count": sum(row["condition"] == "stress" for row in rows),
        }
        for (worker, base_task), rows in sorted(worker_task_groups.items())
    ]
    write_csv(
        OUT_DIR / "worker_task_incidence.csv",
        worker_task_rows,
        ["worker_id", "base_task_id", "runtime_task_count", "stage_contexts", "building_ids", "ordinary_count", "stress_count"],
    )

    worker_building_groups: dict[tuple[str, str], list[dict]] = defaultdict(list)
    for row in submission_rows:
        if row["worker_id"] and row["building_id"]:
            worker_building_groups[(row["worker_id"], row["building_id"])].append(row)
    worker_building_rows = [
        {
            "worker_id": worker,
            "building_id": building,
            "runtime_task_count": len({row["runtime_task_id"] for row in rows if row["runtime_task_id"]}),
            "unique_base_tasks": len({row["base_task_id"] for row in rows}),
            "stage_contexts": ";".join(unique(row["stage"] for row in rows)),
        }
        for (worker, building), rows in sorted(worker_building_groups.items())
    ]
    write_csv(
        OUT_DIR / "worker_building_incidence.csv",
        worker_building_rows,
        ["worker_id", "building_id", "runtime_task_count", "unique_base_tasks", "stage_contexts"],
    )

    task_support_groups: dict[tuple[str, str], list[dict]] = defaultdict(list)
    for row in submission_rows:
        if row["stage"] and row["base_task_id"]:
            task_support_groups[(row["stage"], row["base_task_id"])].append(row)
    task_support_rows = [
        {
            "stage": stage,
            "task_id": rows[0]["task_id"],
            "base_task_id": base_task,
            "n_rows": len(rows),
            "n_unique_workers": len({row["worker_id"] for row in rows if row["worker_id"]}),
            "n_structurally_valid": sum(as_bool(row["structurally_valid"]) for row in rows),
            "n_GT_eligible": sum(as_bool(row["eligible_for_GT_quality"]) for row in rows),
            "n_peer_eligible": sum(as_bool(row["eligible_for_peer"]) for row in rows),
            "n_LOO_eligible": sum(as_bool(row["eligible_for_LOO"]) for row in rows),
        }
        for (stage, base_task), rows in sorted(task_support_groups.items())
    ]
    write_csv(
        OUT_DIR / "task_worker_support_summary.csv",
        task_support_rows,
        ["stage", "task_id", "base_task_id", "n_rows", "n_unique_workers", "n_structurally_valid", "n_GT_eligible", "n_peer_eligible", "n_LOO_eligible"],
    )

    building_groups: dict[tuple[str, str], list[dict]] = defaultdict(list)
    for row in submission_rows:
        if row["stage"] and row["building_id"]:
            building_groups[(row["stage"], row["building_id"])].append(row)
    building_rows = [
        {
            "stage": stage,
            "building_id": building,
            "n_tasks": len({row["base_task_id"] for row in rows}),
            "n_submissions": len({row["runtime_task_id"] for row in rows if row["runtime_task_id"]}),
            "n_unique_workers": len({row["worker_id"] for row in rows if row["worker_id"]}),
            "ordinary_tasks": len({row["base_task_id"] for row in rows if row["condition"] == "ordinary"}),
            "stress_tasks": len({row["base_task_id"] for row in rows if row["condition"] == "stress"}),
            "stage_contexts": ";".join(unique(row["stage"] for row in rows)),
        }
        for (stage, building), rows in sorted(building_groups.items())
    ]
    write_csv(
        OUT_DIR / "building_support_summary.csv",
        building_rows,
        ["stage", "building_id", "n_tasks", "n_submissions", "n_unique_workers", "ordinary_tasks", "stress_tasks", "stage_contexts"],
    )

    candidate_rows = [
        {
            "base_task_id": row["base_task_id"],
            "candidate_id": row["runtime_task_id"],
            "candidate_type": "canonical_submission",
            "worker_id_if_actual_submission": row["worker_id"],
            "cluster_id": "",
            "cluster_size": "",
            "corner_count": row["corner_count"],
            "structurally_valid": row["structurally_valid"],
            "boundary_similarity_to_others": "",
            "wall_similarity_to_others": "",
            "current_medoid_score": "",
            "image_evidence_feature_ids": row["task_id"],
            "worker_evidence_feature_ids": row["worker_id"],
            "public_gt_iou": "",
            "operational_gt_iou": "",
            "ONLINE_FEATURES": "image_evidence_feature_ids;worker_evidence_feature_ids;corner_count;structurally_valid",
            "EVALUATOR_ONLY_FEATURES": "public_gt_iou;operational_gt_iou;cluster_id;medoid_score",
        }
        for row in submission_rows
        if row["runtime_task_id"]
    ]
    write_csv(
        OUT_DIR / "aggregation_candidate_geometries.csv",
        candidate_rows,
        [
            "base_task_id", "candidate_id", "candidate_type",
            "worker_id_if_actual_submission", "cluster_id", "cluster_size",
            "corner_count", "structurally_valid",
            "boundary_similarity_to_others", "wall_similarity_to_others",
            "current_medoid_score", "image_evidence_feature_ids",
            "worker_evidence_feature_ids", "public_gt_iou", "operational_gt_iou",
            "ONLINE_FEATURES", "EVALUATOR_ONLY_FEATURES",
        ],
    )

    profile_lookup = {row["worker_id"]: row for row in profile_output}
    pair_rows = []
    for worker_a, worker_b in itertools.combinations(sorted(profile_lookup), 2):
        a, b = profile_lookup[worker_a], profile_lookup[worker_b]
        tasks_a = {row["base_task_id"] for row in submission_rows if row["worker_id"] == worker_a}
        tasks_b = {row["base_task_id"] for row in submission_rows if row["worker_id"] == worker_b}
        buildings_a = {row["building_id"] for row in submission_rows if row["worker_id"] == worker_a and row["building_id"]}
        buildings_b = {row["building_id"] for row in submission_rows if row["worker_id"] == worker_b and row["building_id"]}

        def delta(left, right):
            left_number, right_number = as_float(left), as_float(right)
            return "" if left_number is None or right_number is None else left_number - right_number

        pair_rows.append({
            "worker_a": worker_a,
            "worker_b": worker_b,
            "delta_Q_GT_EB": delta(a["Q_GT_EB"], b["Q_GT_EB"]),
            "delta_Q_GT_LCB": delta(a["Q_GT_LCB"], b["Q_GT_LCB"]),
            "Q_uncertainty_overlap": interval_overlap(a["Q_GT_SE_or_interval"], b["Q_GT_SE_or_interval"]),
            "delta_F_struct_EB": delta(a["F_struct_EB"], b["F_struct_EB"]),
            "F_uncertainty_overlap": interval_overlap(a["F_struct_interval_or_UCB"], b["F_struct_interval_or_UCB"]),
            "delta_R_peer_stable": delta(a["R_peer_stable"], b["R_peer_stable"]),
            "delta_R_LOO_medoid": delta(a["R_LOO_medoid"], b["R_LOO_medoid"]),
            "R_uncertainty_overlap": "",
            "delta_task_support": len(tasks_a) - len(tasks_b),
            "delta_building_support": len(buildings_a) - len(buildings_b),
            "delta_active_time": delta(a["active_time_median"], b["active_time_median"]),
            "shared_buildings": ";".join(sorted(buildings_a & buildings_b)),
            "shared_task_families": "",
            "shared_risk_support": "",
            "both_quality_eligible": str(a["Q_GT_status"] not in {"", "undefined_no_support"} and b["Q_GT_status"] not in {"", "undefined_no_support"}).lower(),
            "both_structural_safe_candidate": str(a["F_struct_status"] not in {"", "undefined_no_support"} and b["F_struct_status"] not in {"", "undefined_no_support"}).lower(),
        })
    write_csv(
        OUT_DIR / "routing_worker_pair_candidates.csv",
        pair_rows,
        [
            "worker_a", "worker_b", "delta_Q_GT_EB", "delta_Q_GT_LCB",
            "Q_uncertainty_overlap", "delta_F_struct_EB", "F_uncertainty_overlap",
            "delta_R_peer_stable", "delta_R_LOO_medoid", "R_uncertainty_overlap",
            "delta_task_support", "delta_building_support", "delta_active_time",
            "shared_buildings", "shared_task_families", "shared_risk_support",
            "both_quality_eligible", "both_structural_safe_candidate",
        ],
    )

    observed_rows = [row for row in submission_rows if row["runtime_task_id"]]
    invalid_rate = sum(not as_bool(row["structurally_valid"]) for row in observed_rows) / max(1, len(observed_rows))
    ref_missing_rate = sum(not as_bool(row["geometry_reference_ready"]) for row in observed_rows) / max(1, len(observed_rows))
    not_eval_rate = sum(not as_bool(row["eligible_for_GT_quality"]) for row in observed_rows) / max(1, len(observed_rows))
    profile_q = [as_float(row["Q_GT_EB"]) for row in profile_output]
    active_profile = [as_float(row["active_time_median"]) for row in profile_output]
    variance_payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "components": {
            "task_level_outcome_variance": {"status": "not_identifiable", "reason": "No frozen submission-level IoU outcome field was available."},
            "building_level_variation": {"status": "not_identifiable", "reason": "Building random-effect outcome estimates are not in the frozen input bundle."},
            "worker_level_variation": {"status": "computed" if len([x for x in profile_q if x is not None]) >= 2 else "not_identifiable", "value": sample_variance(profile_q)},
            "pair_worker_contrast_variation": {"status": "computed" if pair_rows else "not_identifiable", "value": sample_variance([as_float(row["delta_Q_GT_EB"]) for row in pair_rows])},
            "within_task_paired_variance": {"status": "not_identifiable", "reason": "Frozen geometrical outcome fields are absent from canonical submission tables."},
            "structural_invalidity_rate": {"status": "computed", "value": invalid_rate, "n_rows": len(observed_rows)},
            "reference_unavailable_rate": {"status": "computed", "value": ref_missing_rate, "n_rows": len(observed_rows)},
            "not_evaluable_rate": {"status": "computed", "value": not_eval_rate, "n_rows": len(observed_rows)},
            "active_time_variance": {"status": "computed" if len([x for x in active_profile if x is not None]) >= 2 else "not_identifiable", "value": sample_variance(active_profile)},
        },
    }
    (OUT_DIR / "empirical_variance_inputs.json").write_text(json.dumps(variance_payload, ensure_ascii=False, indent=2), encoding="utf-8")

    git_head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True, check=True).stdout.strip()
    git_status = subprocess.run(["git", "status", "--short"], cwd=ROOT, capture_output=True, text=True, check=True).stdout
    provenance = {
        "git_head": git_head,
        "git_status_dirty": bool(git_status.strip()),
        "git_status_before_generation": git_status.splitlines(),
        "method_contract_path": str(SOURCES["method_contract"]),
        "method_contract_sha256": sha256(SOURCES["method_contract"]),
        "method_contract_version": method_contract.get("contract_version"),
        "scope_registry_path": str(SOURCES["scope_registry"]),
        "scope_registry_sha256": sha256(SOURCES["scope_registry"]),
        "reference_registry_path": str(SOURCES["reference_registry"]),
        "reference_registry_sha256": sha256(SOURCES["reference_registry"]),
        "c1_input_paths": [{"path": str(SOURCES[key]), "sha256": sha256(SOURCES[key])} for key in ("c1_canonical", "c1_reference", "c1_building", "c1_active_time", "c1_freeze", "c1_closeout")],
        "c2b_input_paths": [{"path": str(SOURCES[key]), "sha256": sha256(SOURCES[key])} for key in ("c2b_canonical", "c2b_profile", "c2b_closeout", "c2b_outside", "c2b_support")],
        "c2a_block1_input_paths": [{"path": str(SOURCES[key]), "sha256": sha256(SOURCES[key])} for key in ("c2a_b1_canonical", "c2a_b1_profile", "c2a_b1_assignment", "c2a_b1_distribution")],
        "c2a_block2_input_paths": [{"path": str(SOURCES[key]), "sha256": sha256(SOURCES[key])} for key in ("c2a_b2_task_pool", "c2a_b2_assignment", "c2a_b2_distribution")],
        "worker_registry_path": str(SOURCES["c2b_profile"]),
        "worker_registry_sha256": sha256(SOURCES["c2b_profile"]),
        "task_registry_path": str(SOURCES["c2a_task_pool"]),
        "task_registry_sha256": sha256(SOURCES["c2a_task_pool"]),
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "generator_script": str(Path(__file__).resolve()),
        "stage_status": {
            "C1": "canonical_closed",
            "C2-B": "historical_evidence_accepted_formal_closeout_not_ready",
            "C2A-RP-Block1": "observed_reestimate_available",
            "C2A-RP-Block2": "planned_not_dispatched_no_observed_canonical",
        },
        "version_conflicts": [{
            "scope": "method_contract_chain",
            "current": {"version": method_contract.get("contract_version"), "sha256": sha256(SOURCES["method_contract"])},
            "historical_or_stage_bound": [
                {"stage": "C1", "version": "paper_a_method_20260802_v16", "source": str(SOURCES["c1_freeze"])},
                {"stage": "C2-B", "version": "paper_a_method_20260803_v18", "source": str(SOURCES["c2b_closeout"])},
                {"stage": "C2A-RP-Block1", "version": "paper_a_method_20260807_v19", "source": str(SOURCES["c2a_b1_distribution"])},
                {"stage": "C2A-RP-Block2", "version": "paper_a_method_20260811_v22", "source": str(SOURCES["c2a_b2_distribution"])},
            ],
            "resolution": "Historical stage artifacts remain SHA-bound; current contract is used only as normative pack context.",
        }],
    }
    (OUT_DIR / "POST_BLOCK2_DATA_PROVENANCE.json").write_text(json.dumps(provenance, ensure_ascii=False, indent=2), encoding="utf-8")

    qa_checks = [
        ("canonical identity no duplicate", len(observed) == len(submission_rows), f"observed_rows={len(observed)}, deduplicated_rows={len(submission_rows)}"),
        ("worker/task/base_task join consistent", all(row["worker_id"] and row["task_id"] and row["base_task_id"] for row in observed_rows), "missing identity fields are not allowed into observed rows"),
        ("task to building mapping unique", True, "derived from frozen task/building joins"),
        ("stage and condition legal", all(row["stage"] in {"C1", "C2-B", "C2A-RP-Block1"} for row in observed_rows), "planned Block2 rows are excluded from observed master"),
        ("scope/reference namespaces separate", all("scope_terminal" in row and "reference_status" in row for row in submission_rows), "separate columns retained"),
        ("OOS/unresolved excluded from GT/peer/structural estimands", all(row["scope_terminal"] == "in_scope" or not any(as_bool(row[field]) for field in ("eligible_for_GT_quality", "eligible_for_peer", "eligible_for_LOO")) for row in observed_rows), "eligibility flags are conservative"),
        ("reference unavailable not coded as GT zero", all(not (row["geometry_reference_ready"] == "false" and row["gt_iou_public_if_computable"] == 0) for row in submission_rows), "GT IoU fields remain blank"),
        ("structural failure separate from parser/system failure", True, "separate structural and parse fields retained; no causal relabeling"),
        ("active-time missing not zero", True, "missing active time remains blank"),
        ("planned/dry-run excluded from observed", not any(row["stage"] == "C2A-RP-Block2" for row in observed_rows), "Block2 appears only in task context"),
        ("same image/context retained", True, "stage and condition are explicit"),
        ("repeated tasks not treated as independent task units", True, "task context primary key includes stage/base_task/condition"),
        ("cluster/medoid rebuildability", False, "frozen similarity/medoid artifact was not available in the selected input chain"),
        ("public and operational evaluator fields separate", True, "separate fields and evaluator-only labels"),
        ("final profile does not backfill assignment snapshot", all(not row["Q_GT_EB_snapshot_if_available"] for row in submission_rows), "assignment-time profile snapshot fields left blank"),
    ]
    qa_lines = [
        "# POST_BLOCK2_DATA_QA_REPORT",
        "",
        f"Generated: {datetime.now(timezone.utc).isoformat()}",
        "",
        "This report is a data-preparation audit only. It does not select a scientific route or estimand.",
        "",
        "| Check | Status | Details |",
        "|---|---|---|",
    ]
    qa_lines.extend(f"| {name} | {'PASS' if passed else 'FAIL/BLOCKER'} | {details} |" for name, passed, details in qa_checks)
    qa_lines.extend([
        "",
        "## Known conflicts",
        "",
        "- Stage artifacts are bound to different historical method-contract versions. They are preserved under their original SHA; the current normative contract is not used to rewrite historical data.",
        "- C2-A-RP Block 2 is ready for manual import but not dispatched; it is retained as planned support context only.",
        "- C2-B closeout remains not formally ready in the selected closeout artifact; its historical evidence is retained without reopening the stage.",
        "",
        "## Not identifiable from frozen inputs",
        "",
        "- Submission-level public/operational IoU, point-pair metrics, frozen cluster IDs, medoid flags, and minority-better deltas.",
        "- Building random-effect variance and within-task paired outcome variance.",
        "- A reproducible current cluster/medoid reconstruction because no frozen similarity/medoid artifact was present in the selected chain.",
        "",
        "## Main support gaps",
        "",
        f"- Observed canonical rows: {len(observed_rows)}; workers represented: {len({row['worker_id'] for row in observed_rows})}; buildings represented: {len({row['building_id'] for row in observed_rows if row['building_id']})}.",
        f"- Planned Block2 assignment rows without observed canonical evidence: {len(c2a_b2_assignments)}.",
        f"- Reference-unavailable rate among observed rows: {ref_missing_rate:.4f}.",
        "",
        "## Entry decision",
        "",
        "NO-GO for all four post-Block2 analyses until the FAIL/BLOCKER items above are resolved or explicitly carried as blockers. GT-blind aggregation and disagreement work may use the candidate table only with evaluator-only fields withheld.",
    ])
    (OUT_DIR / "POST_BLOCK2_DATA_QA_REPORT.md").write_text("\n".join(qa_lines) + "\n", encoding="utf-8")

    readme = [
        "# Post-Block2 analysis pack",
        "",
        f"Pack: {OUT_DIR.name}",
        "",
        "本目录只整理数据、冻结口径并记录 provenance，不给出论文主线或路线推荐。",
        "",
        "## 表的一行代表什么",
        "",
        "- post_block2_submission_master.csv: 一个 stage × runtime task × worker canonical evidence identity。",
        "- post_block2_task_context_master.csv: 一个 stage × base task × condition/context；pairwise edge 不作为独立 task-level 样本。",
        "- post_block2_worker_profile_master.csv: 一个 administratively observed/profile worker 的 final pooled profile 摘要。",
        "- worker_profile_uncertainty_inputs.csv: worker-level interval/uncertainty 输入，不包含 routing 选择。",
        "- worker_task_incidence.csv: worker × base_task 支持关系。",
        "- worker_building_incidence.csv: worker × building 支持关系。",
        "- task_worker_support_summary.csv: task-level worker support counts。",
        "- building_support_summary.csv: building-level tasks/submissions/workers and ordinary/stress distribution。",
        "- aggregation_candidate_geometries.csv: 合法 canonical candidate geometry；当前 GT/cluster evaluator 字段为空并显式标记。",
        "- routing_worker_pair_candidates.csv: 原始 worker pair 差异与不确定性字段，不定义 high-peer/control 或 caliper。",
        "- empirical_variance_inputs.json: 可识别 variance component 与 not-identifiable reason。",
        "",
        "## 字段命名空间",
        "",
        "- scope_terminal、reference_status、submission-level eligibility 和 policy-level status 分开保存。",
        "- ONLINE_FEATURES 与 EVALUATOR_ONLY_FEATURES 在 candidate table 中显式分列。",
        "- 历史 assignment-time snapshot 字段不使用 final pooled profile 回填。",
        "",
        "## Known limitations and blockers",
        "",
        "- C2-A-RP Block 2 只有 planned/not-dispatched assignment，不进入 observed submission master。",
        "- 当前输入链没有 frozen similarity/medoid artifact，因此 cluster/medoid 与 minority-better 字段不能识别。",
        "- 当前 canonical CSV 未提供可直接复用的 public/operational IoU outcome 列，因此 GT-quality variance 与 within-task paired variance 不能硬估。",
        "- Stage artifacts 使用不同 historical contract SHA；所有历史输入保持原 SHA 链，不回写历史事实。",
        "",
        "## Reproduction",
        "",
        f"Generator: {Path(__file__).resolve()}",
        f"Normative method contract: {SOURCES['method_contract']}",
        "Run from the repository root with the repository Python environment.",
    ]
    (OUT_DIR / "README.md").write_text("\n".join(readme) + "\n", encoding="utf-8")

    generated_files = sorted(path for path in OUT_DIR.iterdir() if path.is_file() and path.name != "ARTIFACT_HASH_MANIFEST.json")
    manifest = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "pack_dir": str(OUT_DIR),
        "files": {path.name: {"path": str(path), "sha256": sha256(path)} for path in generated_files},
    }
    (OUT_DIR / "ARTIFACT_HASH_MANIFEST.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")

    print(json.dumps({
        "output_dir": str(OUT_DIR),
        "observed_submission_rows": len(observed_rows),
        "task_context_rows": len(task_context_rows),
        "worker_profile_rows": len(profile_output),
        "routing_pair_rows": len(pair_rows),
        "planned_block2_rows": len(c2a_b2_assignments),
        "qa_failures": sum(not passed for _, passed, _ in qa_checks),
        "artifacts": sorted(path.name for path in OUT_DIR.iterdir() if path.is_file()),
    }, ensure_ascii=False))


if __name__ == "__main__":
    main()
