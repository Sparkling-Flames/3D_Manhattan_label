"""Read-only Aggregation-first preflight audit.

This generator writes only to its own output directory. It consumes the selected
v3 post-Block2 pack and already-materialized development outputs; it does not
run A4, create tasks, alter references, or alter any frozen input.
"""

from __future__ import annotations

import csv
import hashlib
import json
import math
import random
import statistics
from collections import Counter, defaultdict
from pathlib import Path
from statistics import NormalDist


ROOT = Path(__file__).resolve().parents[2]
OUT = Path(__file__).resolve().parent
PACK_V2 = ROOT / "analysis_results" / "post_block2_analysis_pack_20260817_v2"
PACK_V3 = ROOT / "analysis_results" / "post_block2_analysis_pack_20260817_v3"
OPP = ROOT / "analysis_results" / "post_block2_opportunity_analysis_20260817_v1"
FINAL_PROFILE = ROOT / "analysis_results" / "final_calibration_profile_20260817_v1"
SEED = 20260817
POWER_REPLICATES = 5000
ALPHA = 0.05

METHODS = [
    ("A0", "A0_current_largest_cluster_medoid"),
    ("A1", "A1_global_medoid_over_all_legal_submissions"),
    ("A2", "A2_cross_fitted_worker_quality_weighted_medoid"),
    ("A3", "A3_cluster_support_plus_worker_quality_selector"),
    ("A4", "A4_image_evidence_weighted_cluster_selector"),
    ("A5", "A5_topology_preserving_variable_corner_selector"),
]


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def rel(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_csv(path: Path, rows: list[dict[str, object]], fields: list[str] | None = None) -> None:
    if fields is None:
        fields = []
        for row in rows:
            for field in row:
                if field not in fields:
                    fields.append(field)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields or ["status"], extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def number(value: object) -> float | None:
    try:
        result = float(str(value))
        return result if math.isfinite(result) else None
    except (TypeError, ValueError):
        return None


def truthy(value: object) -> bool:
    return str(value).strip().lower() in {"true", "1", "yes"}


def unique(values: list[object]) -> list[str]:
    return sorted({str(value).strip() for value in values if str(value).strip()})


def context_key(row: dict[str, str]) -> tuple[str, str, str, str]:
    return tuple(row.get(field, "") for field in ("stage", "task_id", "base_task_id", "condition"))


def base_condition_key(row: dict[str, str]) -> tuple[str, str]:
    return row.get("base_task_id", ""), row.get("condition", "")


def scene_from_identity(base_task_id: str) -> str:
    return base_task_id.split("_", 1)[0] if "_" in base_task_id else ""


def scene_from_label(label: str) -> str:
    label = label.rsplit("/", 1)[-1].rsplit("\\", 1)[-1]
    label = label.rsplit(".", 1)[0]
    return scene_from_identity(label)


def quantile(values: list[float], q: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    index = (len(ordered) - 1) * q
    lower = math.floor(index)
    upper = math.ceil(index)
    if lower == upper:
        return ordered[lower]
    return ordered[lower] + (ordered[upper] - ordered[lower]) * (index - lower)


def pack_comparison() -> tuple[dict, dict]:
    result = {}
    for version, pack in (("v2", PACK_V2), ("v3", PACK_V3)):
        provenance = read_json(pack / "POST_BLOCK2_DATA_PROVENANCE.json")
        manifest = read_json(pack / "ARTIFACT_HASH_MANIFEST.json")
        mismatches = []
        for name, expected in manifest.get("artifacts", {}).items():
            path = pack / name
            if not path.is_file() or sha256(path) != expected:
                mismatches.append(name)
        result[version] = {
            "path": rel(pack),
            "provenance_sha256": sha256(pack / "POST_BLOCK2_DATA_PROVENANCE.json"),
            "qa_sha256": sha256(pack / "POST_BLOCK2_DATA_QA_REPORT.md"),
            "manifest_sha256": sha256(pack / "ARTIFACT_HASH_MANIFEST.json"),
            "pack_version": provenance.get("pack_version", ""),
            "status": provenance.get("status", ""),
            "prompt_2_entry_allowed": provenance.get("prompt_2_entry_allowed"),
            "profile_status": provenance.get("profile_status", {}),
            "profile_p0_inventory_count": provenance.get("profile_p0_inventory_count"),
            "artifact_count": manifest.get("artifact_count"),
            "manifest_mismatches": mismatches,
            "generator": rel(ROOT / "tools" / "thesis_main" / "data_prep" / f"build_post_block2_analysis_pack_{version}.py"),
        }
        generator = ROOT / "tools" / "thesis_main" / "data_prep" / f"build_post_block2_analysis_pack_{version}.py"
        result[version]["generator_sha256"] = sha256(generator) if generator.is_file() else ""
    selection = {
        "selected_pack": "post_block2_analysis_pack_20260817_v3",
        "selection_rule": "v3 has formal current-v23 calibration profile binding; v2 declares final pooled profile source_absent",
        "v2_not_silently_joined": True,
        "v3_manifest_verified": not result["v3"]["manifest_mismatches"],
    }
    return result, selection


def load_inputs() -> dict[str, object]:
    c1_dir = ROOT / "analysis_results" / "c1_formal_audit_20260802_v16_final" / "c1_formal_audit_20260802_7fcacc5c2d6c_bf5def46_6bc67c03"
    inputs: dict[str, object] = {
        "ctx": read_csv(PACK_V3 / "post_block2_task_context_master.csv"),
        "sub": read_csv(PACK_V3 / "post_block2_submission_master.csv"),
        "building_support": read_csv(PACK_V3 / "building_support_summary.csv"),
        "cf": read_csv(OPP / "POST_BLOCK2_AGGREGATION_OPPORTUNITY_AUDIT" / "cross_fitted_selector_results.csv"),
        "lobo": read_csv(OPP / "POST_BLOCK2_AGGREGATION_OPPORTUNITY_AUDIT" / "leave_one_building_out.csv"),
        "variable_corner": read_csv(OPP / "POST_BLOCK2_AGGREGATION_OPPORTUNITY_AUDIT" / "variable_corner_count_audit.csv"),
        "ref_queue": read_csv(ROOT / "analysis_results" / "reference_conflict_sensitivity_audit_20260805_v2" / "c1_candidate_screen" / "c1_gt_conflict_review_queue.csv"),
        "ref_registry": read_csv(ROOT / "analysis_results" / "c2a_rp_local_launch_20260807_inputs_v2" / "reference_registry_post_c2_local.csv"),
        "c1_features": read_csv(c1_dir / "c1_preannotation_task_features.csv"),
        "stage3_inventory": read_csv(ROOT / "analysis_results" / "stage3_test_preparation_20260804_v1" / "stage3_test_inventory_candidate.csv"),
        "image_listing": read_csv(ROOT / "analysis_results" / "c2b_validation_static_20260802_v16" / "static" / "c2b_candidate_image_file_listing.csv"),
        "task_features": read_csv(ROOT / "analysis_results" / "calibration_dual_track_processing_20260815_v2" / "task_feature_matrix.csv"),
        "evidence_long": read_csv(ROOT / "analysis_results" / "calibration_dual_track_processing_20260815_v2" / "calibration_evidence_long.csv"),
        "required_n": read_csv(OPP / "POST_BLOCK2_CLUSTERED_POWER" / "aggregation_required_N.csv"),
        "c1_crowd": read_csv(c1_dir / "geometry_task_crowd_structure_C1.csv"),
        "ref_scope": read_json(ROOT / "analysis_results" / "c2b_closeout_20260806_final" / "c2b_gt_scope_resolution_audit.json"),
        "c1_feature_manifest": read_json(c1_dir / "c1_preannotation_task_features_manifest.json"),
        "stage3_feature_manifest": read_json(ROOT / "analysis_results" / "stage3_test_preparation_20260804_v1" / "stage3_test_feature_candidate_manifest.json"),
        "c2_feature_manifest": read_json(ROOT / "analysis_results" / "c2b_validation_static_20260802_v16" / "static" / "c2_feature_freeze_manifest.json"),
    }
    return inputs


def reference_label(ctx: dict[str, str], base: str, conflict: set[str], pending: set[str], registry: dict[str, dict[str, str]]) -> str:
    labels: list[str] = []
    provenance = ctx.get("gt_provenance_class", "")
    if "partial_local" in provenance:
        labels.append("public_gt_test_partial_local_correction")
    elif "mp3d_hohonet" in provenance:
        labels.append("public_gt_validation_no_researcher_correction")
    if base in registry:
        labels.append(registry[base].get("reference_status", "registry_status_not_recorded"))
    if base in conflict:
        labels.append("strict_conflict_exclusion_candidate_only")
    if base in pending:
        labels.append("reference_conflict_pending")
    return ";".join(unique(labels)) or "not_recorded_or_not_required"


def context_meta(ctx: dict[str, str], sub_rows: list[dict[str, str]], c1_scene: str, raw_support: dict[str, str], conflict: set[str], pending: set[str], registry: dict[str, dict[str, str]]) -> dict[str, object]:
    base = ctx.get("base_task_id", "")
    labels = [row.get("upstream_task_label", "") for row in sub_rows]
    if c1_scene:
        scene, scene_source = c1_scene, "frozen_C1_crowd_structure_building_id"
    elif scene_from_identity(base):
        scene, scene_source = scene_from_identity(base), "derived_from_formal_task_identity_prefix"
    else:
        candidates = [scene_from_label(label) for label in labels if scene_from_label(label)]
        scene, scene_source = (candidates[0], "derived_from_upstream_task_label_prefix") if candidates else ("", "source_absent_unresolved")
    corner_values = []
    for row in sub_rows:
        points = number(row.get("n_corners"))
        if points is not None and int(points) % 2 == 0:
            corner_values.append(str(int(points) // 2))
    valid_count = sum(truthy(row.get("canonical_valid")) for row in sub_rows)
    eligible_count = sum(truthy(row.get("upstream_eligible_for_primary_analysis")) for row in sub_rows)
    return {
        "stage": ctx.get("stage", ""),
        "task_id": ctx.get("task_id", ""),
        "base_task_id": base,
        "condition": ctx.get("condition", ""),
        "dataset_group": ctx.get("dataset_group", ""),
        "mp3d_building_scene_id": scene,
        "building_scene_id_source": scene_source,
        "pack_building_id_raw": raw_support.get("building_id", ""),
        "pack_building_id_is_base_task_id": str("_" in raw_support.get("building_id", "")),
        "building_support_raw": raw_support.get("support_count", ""),
        "observed_submission_count": len(sub_rows),
        "valid_geometry_count": valid_count,
        "primary_analysis_eligible_count": eligible_count,
        "corner_count_set": ";".join(unique(corner_values)),
        "topology_status": ctx.get("consensus_cluster_status", "") or "not_recorded",
        "consensus_status": ctx.get("consensus_status", ""),
        "reference_status": reference_label(ctx, base, conflict, pending, registry),
        "gt_provenance_class": ctx.get("gt_provenance_class", ""),
        "gt_user_correction_status": ctx.get("gt_user_correction_status", ""),
        "gt_user_verification_scope": ctx.get("gt_user_verification_scope", ""),
        "gt_source_artifact": ctx.get("gt_source_artifact", ""),
        "gt_source_sha256": ctx.get("gt_source_sha256", ""),
        "aggregation_context_present": "False",
    }


def make_hierarchy(inputs: dict[str, object]) -> tuple[list[dict[str, object]], list[dict[str, object]], dict]:
    ctx = inputs["ctx"]
    sub = inputs["sub"]
    raw_support = inputs["building_support"]
    c1_crowd = inputs["c1_crowd"]
    conflict = {row.get("base_task_id", "") for row in inputs["ref_queue"]}
    pending = set(inputs["ref_scope"].get("gt_reference_pending_task_ids", []))
    registry = {row.get("base_task_id", ""): row for row in inputs["ref_registry"]}
    sub_groups: dict[tuple[str, str, str, str], list[dict[str, str]]] = defaultdict(list)
    for row in sub:
        sub_groups[context_key(row)].append(row)
    c1_scene = {(row.get("base_task_id", ""), row.get("condition", "")): row.get("building_id", "") for row in c1_crowd}
    raw_by_stage_id = {(row.get("stage", ""), row.get("building_id", "")): row for row in raw_support}
    hierarchy = []
    for row in ctx:
        meta = context_meta(row, sub_groups.get(context_key(row), []), c1_scene.get(base_condition_key(row), ""), raw_by_stage_id.get((row.get("stage", ""), row.get("base_task_id", "")), {}), conflict, pending, registry)
        hierarchy.append(meta)

    cf = inputs["cf"]
    cf_groups: dict[tuple[str, str, str], dict[str, dict[str, str]]] = defaultdict(dict)
    for row in cf:
        cf_groups[(row.get("base_task_id", ""), row.get("condition", ""), row.get("building_id", ""))][row.get("method", "")] = row
    variable = {(row.get("base_task_id", ""), row.get("condition", "")): row for row in inputs["variable_corner"]}
    agg_rows = []
    for (base, condition, building), methods in sorted(cf_groups.items()):
        ctx_candidates = [row for row in hierarchy if row.get("base_task_id") == base and row.get("condition") == condition]
        row = dict(ctx_candidates[0] if ctx_candidates else {"base_task_id": base, "condition": condition})
        row.update({"scope": "aggregation_development", "aggregation_building_id": building, "aggregation_context_present": "True"})
        var = variable.get((base, condition), {})
        row.update({
            "corner_count_set": var.get("corner_count_set", row.get("corner_count_set", "")),
            "mixed_topology": var.get("mixed_topology", ""),
            "a1_a2_cross_topology_status": var.get("A1_A2_cross_topology_status", ""),
            "a5_topology_status": var.get("A5_status", ""),
        })
        for short, method in METHODS:
            item = methods.get(method, {})
            row[f"{short.lower()}_status"] = item.get("status", "method_row_absent")
            row[f"{short.lower()}_quality"] = item.get("public_gt_quality", "")
            row[f"{short.lower()}_selected_worker_id"] = item.get("selected_worker_id", "")
        a0 = row.get("a0_quality", "")
        a2 = row.get("a2_quality", "")
        row["a0_a2_common_evaluable"] = str(bool(a0 and a2))
        row["all_a0_a2_a3_a4_a5_common_evaluable"] = str(all(row.get(f"{short.lower()}_quality", "") for short, _ in METHODS if short != "A1"))
        agg_rows.append(row)
    return hierarchy, agg_rows, {"conflict_count": len(conflict), "pending_count": len(pending), "registry_count": len(registry)}


def write_clean_a2_a0(agg_rows: list[dict[str, object]]) -> tuple[list[dict[str, object]], dict]:
    rows = []
    for row in agg_rows:
        if row.get("a0_quality") and row.get("a2_quality"):
            a0, a2 = float(row["a0_quality"]), float(row["a2_quality"])
            rows.append({
                "base_task_id": row.get("base_task_id", ""),
                "condition": row.get("condition", ""),
                "building_scene_id": row.get("aggregation_building_id", ""),
                "corner_count_set": row.get("corner_count_set", ""),
                "mixed_topology": row.get("mixed_topology", ""),
                "a0_public_gt_quality": a0,
                "clean_a2_public_gt_quality": a2,
                "task_paired_delta_clean_a2_minus_a0": a2 - a0,
                "a0_status": row.get("a0_status", ""),
                "clean_a2_status": row.get("a2_status", ""),
                "a2_definition": "worker_quality_weight_only; frozen min(boundary,wall) medoid eligibility unchanged",
                "evaluation_role": "development_only_not_confirmation",
            })
    values = [float(row["task_paired_delta_clean_a2_minus_a0"]) for row in rows]
    summary = {
        "total_aggregation_contexts": len(agg_rows),
        "a0_clean_a2_common_evaluable_tasks": len(rows),
        "mean_delta": statistics.mean(values) if values else None,
        "variance_delta": statistics.variance(values) if len(values) > 1 else None,
        "a0_evaluable": sum(bool(row.get("a0_quality")) for row in agg_rows),
        "clean_a2_evaluable": sum(bool(row.get("a2_quality")) for row in agg_rows),
        "a3_evaluable": sum(bool(row.get("a3_quality")) for row in agg_rows),
        "a4_evaluable": sum(bool(row.get("a4_quality")) for row in agg_rows),
        "a5_evaluable": sum(bool(row.get("a5_quality")) for row in agg_rows),
        "all_five_evaluable": sum(row.get("all_a0_a2_a3_a4_a5_common_evaluable") == "True" for row in agg_rows),
    }
    return rows, summary


def uncertainty_and_lobo(inputs: dict[str, object], clean_rows: list[dict[str, object]]) -> dict:
    by_building: dict[str, list[float]] = defaultdict(list)
    for row in clean_rows:
        by_building[str(row["building_scene_id"])].append(float(row["task_paired_delta_clean_a2_minus_a0"]))
    building_means = {building: statistics.mean(values) for building, values in by_building.items()}
    rng = random.Random(SEED)
    boot = [statistics.mean(building_means[rng.choice(list(building_means))] for _ in building_means) for _ in range(2000)] if building_means else []
    lobo_groups: dict[str, dict[str, dict[str, str]]] = defaultdict(dict)
    for row in inputs["lobo"]:
        lobo_groups[row.get("outer_fold", "")][row.get("method", "")] = row
    lobo = []
    for fold, methods in sorted(lobo_groups.items()):
        a0 = methods.get("A0_current_largest_cluster_medoid", {}).get("mean_public_gt_quality", "")
        a2 = methods.get("A2_cross_fitted_worker_quality_weighted_medoid", {}).get("mean_public_gt_quality", "")
        if a0 and a2:
            delta = float(a2) - float(a0)
            lobo.append({"outer_fold": fold, "a0_mean": float(a0), "clean_a2_mean": float(a2), "delta": delta, "direction": "positive" if delta > 0 else "negative" if delta < 0 else "zero"})
    values = [float(row["task_paired_delta_clean_a2_minus_a0"]) for row in clean_rows]
    return {
        "task_level": {"n": len(values), "mean": statistics.mean(values) if values else None, "variance": statistics.variance(values) if len(values) > 1 else None},
        "building_stratified": {"n_buildings": len(building_means), "building_means": building_means, "bootstrap_replicates": 2000, "seed": SEED, "ci95": [quantile(boot, 0.025), quantile(boot, 0.975)]},
        "lobo": {"n_folds_with_both_methods": len(lobo), "positive": sum(row["direction"] == "positive" for row in lobo), "negative": sum(row["direction"] == "negative" for row in lobo), "zero": sum(row["direction"] == "zero" for row in lobo), "rows": lobo},
    }


def reference_rows(inputs: dict[str, object], clean_summary: dict) -> list[dict[str, object]]:
    ref_registry = inputs["ref_registry"]
    return [
        {"reference_regime": "P1_test_public_gt", "source_path": "analysis_results/prescreen_closeout_final_gold_v2_20260701/prescreen_canonical_annotations.csv", "source_sha256": sha256(ROOT / "analysis_results/prescreen_closeout_final_gold_v2_20260701/prescreen_canonical_annotations.csv"), "coverage": 114, "readiness": "development_only", "status": "public_source_with_partial_local_user_correction", "user_verification": "not_full_population", "strict_exclusion": "not_a_reference_rewrite"},
        {"reference_regime": "C1_public_gt", "source_path": "analysis_results/c1_formal_audit_20260802_v16_final/.../c1_gt_quality_analysis.csv", "source_sha256": sha256(ROOT / "analysis_results/c1_formal_audit_20260802_v16_final/c1_formal_audit_20260802_7fcacc5c2d6c_bf5def46_6bc67c03/c1_gt_quality_analysis.csv"), "coverage": 101, "readiness": "development_evaluable_with_exclusions", "status": f"A0={clean_summary['a0_evaluable']};A2={clean_summary['clean_a2_evaluable']};all5={clean_summary['all_five_evaluable']}", "user_verification": "not_full_population", "strict_exclusion": "13_candidate_conflicts_not_modified"},
        {"reference_regime": "C1_strict_conflict_exclusion", "source_path": "analysis_results/reference_conflict_sensitivity_audit_20260805_v2/c1_candidate_screen/c1_gt_conflict_review_queue.csv", "source_sha256": sha256(ROOT / "analysis_results/reference_conflict_sensitivity_audit_20260805_v2/c1_candidate_screen/c1_gt_conflict_review_queue.csv"), "coverage": len(inputs["ref_queue"]), "readiness": "exclude_from_primary_reference_claim", "status": "candidate_only_reference_unmodified", "user_verification": "not_applicable", "strict_exclusion": "required"},
        {"reference_regime": "C2B_public_gt_registry", "source_path": "analysis_results/c2a_rp_local_launch_20260807_inputs_v2/reference_registry_post_c2_local.csv", "source_sha256": sha256(ROOT / "analysis_results/c2a_rp_local_launch_20260807_inputs_v2/reference_registry_post_c2_local.csv"), "coverage": len(ref_registry), "readiness": "development_only_pending_conflict", "status": f"geometry_reference_ready={sum(truthy(r.get('geometry_reference_ready')) for r in ref_registry)};pending={inputs['ref_scope'].get('gt_reference_pending_count', '')}", "user_verification": "researcher_validation_only", "strict_exclusion": "pending_task_not_evaluable"},
        {"reference_regime": "C2B_pending_conflict", "source_path": "analysis_results/c2b_closeout_20260806_final/c2b_gt_scope_resolution_audit.json", "source_sha256": sha256(ROOT / "analysis_results/c2b_closeout_20260806_final/c2b_gt_scope_resolution_audit.json"), "coverage": inputs["ref_scope"].get("gt_reference_pending_count", 0), "readiness": "source_absent_until_terminal_blinded_review", "status": ";".join(inputs["ref_scope"].get("gt_reference_pending_task_ids", [])), "user_verification": "not_closed", "strict_exclusion": "required"},
        {"reference_regime": "partial_export_project76", "source_path": "analysis_results/reference_conflict_sensitivity_audit_20260805_v2/partial_export_reference_summary_v1.json", "source_sha256": sha256(ROOT / "analysis_results/reference_conflict_sensitivity_audit_20260805_v2/partial_export_reference_summary_v1.json"), "coverage": 23, "readiness": "source_absent", "status": "final_export=false;tracked_raw_export_removed=true", "user_verification": "not_applicable", "strict_exclusion": "required"},
    ]


def deployability_rows(inputs: dict[str, object], agg_rows: list[dict[str, object]]) -> list[dict[str, object]]:
    agg_bases = {str(row.get("base_task_id", "")) for row in agg_rows}
    image_bases = {Path(row.get("path", "")).stem for row in inputs["image_listing"]}
    stage3_bases = {row.get("base_task_id", "") for row in inputs["stage3_inventory"]}
    task_feature_rows = inputs["task_features"]
    d_model_nonblank = sum(bool(row.get("d_model_feat", "")) for row in task_feature_rows)
    d_model_overlap = sum(bool(row.get("d_model_feat", "")) and row.get("base_task_id", "") in agg_bases for row in task_feature_rows)
    c1_features = inputs["c1_features"]
    ready_c1 = sum(truthy(row.get("preannotation_feature_ready")) for row in c1_features)
    evidence = inputs["evidence_long"]
    return [
        {"feature_group": "raw_image", "feature_name": "panorama", "source_path": "data/mp3d_layout/img_v/", "source_sha256": sha256(ROOT / "analysis_results/c2b_validation_static_20260802_v16/static/c2b_candidate_image_file_listing.csv"), "coverage": f"{len(agg_bases & image_bases)}/{len(agg_bases)} aggregation identities in frozen image listing", "generation_timing": "available_before_assignment", "reads_gt": "False", "reads_current_worker_outcome": "False", "reproducible_new_task": "True_for_file_input_only", "status": "image_available_feature_extraction_absent"},
        {"feature_group": "model_output", "feature_name": "HoHoNet_HorizonNet_or_LHFeat_preannotation", "source_path": "analysis_results/c1_formal_audit_20260802_v16_final/.../c1_preannotation_task_features.csv", "source_sha256": sha256(ROOT / "analysis_results/c1_formal_audit_20260802_v16_final/c1_formal_audit_20260802_7fcacc5c2d6c_bf5def46_6bc67c03/c1_preannotation_task_features.csv"), "coverage": f"{len(c1_features)} rows; ready={ready_c1}; d_model_feat_candidate_overlap={d_model_overlap}", "generation_timing": "preannotation_pre_task", "reads_gt": "False", "reads_current_worker_outcome": "False", "reproducible_new_task": "False_missing_frozen_model_identity", "status": "source_present_but_no_ready_frozen_matrix"},
        {"feature_group": "model_output", "feature_name": "LHFeat_candidate_descriptor_cache", "source_path": "analysis_results/stage3_test_preparation_20260804_v1/stage3_test_feature_candidate_manifest.json", "source_sha256": sha256(ROOT / "analysis_results/stage3_test_preparation_20260804_v1/stage3_test_feature_candidate_manifest.json"), "coverage": f"{inputs['stage3_feature_manifest'].get('candidate_descriptor_count', '')} candidate descriptors; inventory overlap={len(agg_bases & stage3_bases)}/{len(agg_bases)}", "generation_timing": "pre_task_candidate", "reads_gt": "False_for_candidate; reference_cache_exists_for_audit", "reads_current_worker_outcome": "False", "reproducible_new_task": "Candidate_only", "status": "candidate_only_formal_ready_false_method_v18"},
        {"feature_group": "geometry_cue", "feature_name": "boundary_line_portal_opening", "source_path": "", "source_sha256": "", "coverage": "0/101 bound A4 task feature rows", "generation_timing": "source_absent", "reads_gt": "not_evaluable", "reads_current_worker_outcome": "not_evaluable", "reproducible_new_task": "False", "status": "source_absent"},
        {"feature_group": "seam", "feature_name": "seam_robustness_or_seam_cue", "source_path": "analysis_results/c2b_validation_static_20260802_v16/static/c2_feature_freeze_manifest.json", "source_sha256": sha256(ROOT / "analysis_results/c2b_validation_static_20260802_v16/static/c2_feature_freeze_manifest.json"), "coverage": f"{inputs['c2_feature_manifest'].get('candidate_extraction_audit', {}).get('seam_audited_image_count', '')} audit images; no 101-row A4 matrix", "generation_timing": "pre_task_candidate_audit", "reads_gt": "reference_cache_for_audit_only", "reads_current_worker_outcome": "False", "reproducible_new_task": "Candidate_only", "status": "not_bound_to_A4_task_input"},
        {"feature_group": "occlusion", "feature_name": "occlusion_proxy", "source_path": "analysis_results/calibration_dual_track_processing_20260815_v2/calibration_evidence_long.csv", "source_sha256": sha256(ROOT / "analysis_results/calibration_dual_track_processing_20260815_v2/calibration_evidence_long.csv"), "coverage": f"{len(evidence)} rows", "generation_timing": "post_task_in_record; pre_task flag is not an image-evidence source", "reads_gt": "False", "reads_current_worker_outcome": "True_or_worker_annotation_derived", "reproducible_new_task": "False_for_A4_preoutcome_claim", "status": "not_deployable_as_independent_preoutcome_image_evidence"},
        {"feature_group": "worker_outcome", "feature_name": "current_task_worker_outcome", "source_path": "analysis_results/post_block2_analysis_pack_20260817_v3/post_block2_submission_master.csv", "source_sha256": sha256(PACK_V3 / "post_block2_submission_master.csv"), "coverage": "2501 submissions", "generation_timing": "post_task", "reads_gt": "No_for_selection; GT only in evaluation fields", "reads_current_worker_outcome": "True", "reproducible_new_task": "Yes_after_task_but_not_preoutcome", "status": "forbidden_for_preoutcome_A4_feature_claim"},
    ]


def split_manifest(agg_rows: list[dict[str, object]], clean_rows: list[dict[str, object]], conflict_rows: list[dict[str, object]]) -> list[dict[str, object]]:
    buildings = sorted({str(row.get("aggregation_building_id", "")) for row in agg_rows if row.get("aggregation_building_id")})
    ranked = sorted(buildings, key=lambda b: hashlib.sha256(f"{SEED}:{b}".encode()).hexdigest())
    holdout_n = max(1, math.ceil(len(buildings) * 0.25))
    holdout = set(ranked[:holdout_n])
    base_to_building = {str(row.get("base_task_id", "")): str(row.get("aggregation_building_id", "")) for row in agg_rows}
    paired_by_building = Counter(str(row.get("building_scene_id", "")) for row in clean_rows)
    conflicts_by_building = Counter()
    for conflict in conflict_rows:
        building = str(conflict.get("building_id") or conflict.get("building_scene_id") or "")
        if not building:
            building = base_to_building.get(str(conflict.get("base_task_id", "")), "")
        if building:
            conflicts_by_building[building] += 1
    split_status = "placeholder_not_effect_validation_ready" if len(buildings) < 10 or len(holdout) < 3 else "support_only_not_effect_validation_ready"
    rows = []
    for building in buildings:
        rows.append({"building_scene_id": building, "split": "internal_holdout" if building in holdout else "development", "assignment_rule": "sha256(seed:building) sorted; no A0/A2/A3/A4/A5 outcome read", "seed": SEED, "outcome_used_for_split": "False", "source_universe": "101 aggregation task-contexts", "current_task_count": sum(row.get("aggregation_building_id") == building for row in agg_rows), "a0_a2_paired_evaluable_support_count": paired_by_building.get(building, 0), "reference_conflict_count": conflicts_by_building.get(building, 0), "split_support_status": split_status})
    return rows


def t_critical(df: int) -> float:
    values = {9: 2.2621571628, 11: 2.2009851601, 14: 2.1447866879}
    if df not in values:
        raise ValueError(f"unsupported t critical df={df}")
    return values[df]


def critical_power(delta: float, se: float, critical: float) -> float:
    if se <= 0:
        return 0.0
    z = delta / se
    return (1 - NormalDist().cdf(critical - z)) + NormalDist().cdf(-critical - z)


def random_effects_components(by_building: dict[str, list[float]]) -> dict[str, object]:
    values = [value for rows in by_building.values() for value in rows]
    j = len(by_building)
    n = len(values)
    means = [statistics.mean(rows) for rows in by_building.values() if rows]
    grand = statistics.mean(values) if values else 0.0
    ss_between = sum(len(rows) * (statistics.mean(rows) - grand) ** 2 for rows in by_building.values())
    ss_within = sum((value - statistics.mean(rows)) ** 2 for rows in by_building.values() for value in rows)
    ms_between = ss_between / max(1, j - 1)
    ms_within = ss_within / max(1, n - j)
    sum_sq = sum(len(rows) ** 2 for rows in by_building.values())
    c = (n - sum_sq / max(1, n)) / max(1, j - 1)
    sigma_u2 = max(0.0, (ms_between - ms_within) / c) if c > 0 else 0.0
    sigma_e2 = max(0.0, ms_within)
    total = sigma_u2 + sigma_e2
    rho_raw = sigma_u2 / total if total > 0 else 0.0
    rho_clipped = min(0.95, max(0.0, rho_raw))
    return {
        "n_paired_tasks": n,
        "n_paired_buildings": j,
        "cluster_sizes": {building: len(rows) for building, rows in sorted(by_building.items())},
        "ss_between": ss_between,
        "ss_within": ss_within,
        "ms_between": ms_between,
        "ms_within": ms_within,
        "c_unbalanced": c,
        "sigma_u2_raw_nonnegative": sigma_u2,
        "sigma_e2_raw_nonnegative": sigma_e2,
        "empirical_icc_raw": rho_raw,
        "empirical_icc_clipped": rho_clipped,
        "icc_status": "small_cluster_noisy_estimate_J_12",
        "truncation_rule": "MSW=max(0,MSW); sigma_u2=max(0,(MSB-MSW)/C); ICC clipped to [0,0.95] only for scenario input",
    }


def simulate_power(total_variance: float, icc: float, n_tasks: int, n_buildings: int, delta: float, seed: int, replicates: int) -> dict[str, float]:
    counts = [n_tasks // n_buildings + (i < n_tasks % n_buildings) for i in range(n_buildings)]
    sum_sq = sum(count * count for count in counts)
    sigma_u2 = total_variance * icc
    sigma_e2 = total_variance * (1 - icc)
    cluster_var = sigma_u2 * sum_sq / (n_tasks * n_tasks) + sigma_e2 / n_tasks
    cluster_se = math.sqrt(cluster_var)
    critical = t_critical(n_buildings - 1)
    rng = random.Random(seed)
    significant = 0
    for _ in range(replicates):
        cluster_sum = sum(rng.gauss(0.0, math.sqrt(sigma_u2)) * count for count in counts)
        residual = rng.gauss(0.0, math.sqrt(sigma_e2 * n_tasks))
        estimate = delta + (cluster_sum + residual) / n_tasks
        if abs(estimate / cluster_se) > critical:
            significant += 1
    return {"power": significant / replicates, "clustered_se": cluster_se, "design_effect": cluster_var / (total_variance / n_tasks), "sigma_u2": sigma_u2, "sigma_e2": sigma_e2, "residual_sum_variance": sigma_e2 * n_tasks, "df": n_buildings - 1, "critical_value": critical}


def power_grid(clean_summary: dict, by_building: dict[str, list[float]]) -> tuple[list[dict[str, object]], dict]:
    central_variance = float(clean_summary["variance_delta"])
    components = random_effects_components(by_building)
    empirical_icc = float(components["empirical_icc_clipped"])
    icc_grid = [("icc_0", 0.0), ("icc_0.05", 0.05), ("icc_0.10", 0.10), ("icc_0.20", 0.20), ("icc_empirical", empirical_icc)]
    variance_grid = [("central", central_variance), ("pessimistic_2x", central_variance * 2.0)]
    deltas = [0.005, 0.010, 0.011, 0.013, 0.015, 0.016, 0.018, 0.020, 0.025]
    rows = []
    for variance_label, total_variance in variance_grid:
        for icc_label, icc in icc_grid:
            for n_tasks in (80, 100, 120):
                for n_buildings in (10, 12, 15):
                    for delta in deltas:
                        seed = SEED + n_tasks * 100000 + n_buildings * 1000 + int(icc * 1000) + (0 if variance_label == "central" else 500000)
                        result = simulate_power(total_variance, icc, n_tasks, n_buildings, delta, seed, POWER_REPLICATES)
                        rows.append({
                            "variance_scenario": variance_label,
                            "total_variance": total_variance,
                            "icc_scenario": icc_label,
                            "icc_value": icc,
                            "icc_estimation_status": "small_cluster_noisy_estimate" if icc_label == "icc_empirical" else "predeclared_sensitivity",
                            "n_tasks": n_tasks,
                            "n_buildings": n_buildings,
                            "true_delta_assumption": delta,
                            "t_approx_power_conservative_no_cluster": critical_power(delta, math.sqrt(total_variance / n_tasks), result["critical_value"]),
                            "clustered_simulation_power": result["power"],
                            "clustered_se": result["clustered_se"],
                            "design_effect": result["design_effect"],
                            "sigma_u2": result["sigma_u2"],
                            "sigma_e2": result["sigma_e2"],
                            "residual_sum_variance": result["residual_sum_variance"],
                            "df": result["df"],
                            "critical_value": result["critical_value"],
                            "variance_source": "empirical_A2_minus_A0_task_delta_variance_central_or_2x_pessimistic",
                            "icc_source": "unbalanced_one_way_random_effects; empirical_is_small_cluster_noisy",
                            "alpha": ALPHA,
                            "test": "two_sided_t_df_J_minus_1",
                            "seed": seed,
                            "replicates": POWER_REPLICATES,
                            "power_is_observed_effect": "False",
                            "current_building_capacity_status": "within_current_13" if n_buildings <= 13 else "hypothetical_beyond_current_13",
                        })
    audit = {
        "task_delta_variance_central": central_variance,
        "variance_scenarios": {"central": central_variance, "pessimistic_2x": central_variance * 2.0},
        "icc_sensitivity_grid": {label: value for label, value in icc_grid},
        "empirical_icc": empirical_icc,
        "empirical_icc_status": "small_cluster_noisy_estimate_J_12",
        "random_effects_components": components,
        "variance_component_formula": "MSB=SSB/(J-1); MSW=SSW/(N-J); C=(N-sum(n_j^2)/N)/(J-1); sigma_u2=max(0,(MSB-MSW)/C); sigma_e2=max(0,MSW); ICC=sigma_u2/(sigma_u2+sigma_e2)",
        "simulation_residual_formula": "sum_i e_i ~ Normal(0, sigma_e2*N), simulated as rng.gauss(0,sqrt(sigma_e2*N)); not sigma_e2*sum(n_j^2)",
        "critical_value_formula": "t_(1-alpha/2, J-1)",
        "nominal_alpha": ALPHA,
        "implied_conservative_alpha_by_buildings": {str(j): 2 * (1 - NormalDist().cdf(t_critical(j - 1))) for j in (10, 12, 15)},
        "alpha": ALPHA,
        "seed": SEED,
        "replicates": POWER_REPLICATES,
        "true_delta_is_simulation_assumption": True,
    }
    return rows, audit


def power_regression_tests(power_rows: list[dict[str, object]], audit: dict) -> dict[str, object]:
    checks = []
    type_i_rows = []
    for variance_label, total_variance in audit["variance_scenarios"].items():
        for icc_label, icc in audit["icc_sensitivity_grid"].items():
            for n_tasks, n_buildings in ((80, 10), (100, 12), (120, 15)):
                result = simulate_power(total_variance, icc, n_tasks, n_buildings, 0.0, SEED + 900000 + n_tasks * 100 + n_buildings, POWER_REPLICATES)
                implied_alpha = 2 * (1 - NormalDist().cdf(result["critical_value"]))
                mc_tolerance = 3 * math.sqrt(implied_alpha * (1 - implied_alpha) / POWER_REPLICATES)
                type_i_rows.append({"variance_scenario": variance_label, "icc_scenario": icc_label, "n_tasks": n_tasks, "n_buildings": n_buildings, "type_i_error": result["power"], "nominal_alpha": ALPHA, "implied_conservative_alpha": implied_alpha, "mc_tolerance_3se": mc_tolerance, "passed": abs(result["power"] - implied_alpha) <= mc_tolerance})
    checks.append({"test": "delta_zero_type_i_error", "passed": all(row["passed"] for row in type_i_rows), "rows": type_i_rows})
    grouped = defaultdict(list)
    for row in power_rows:
        grouped[(row["variance_scenario"], row["icc_scenario"], row["n_tasks"], row["n_buildings"])].append(row)
    delta_checks = []
    for key, values in grouped.items():
        ordered = sorted(values, key=lambda row: float(row["true_delta_assumption"]))
        delta_checks.extend(float(b["clustered_simulation_power"]) + 0.04 >= float(a["clustered_simulation_power"]) for a, b in zip(ordered, ordered[1:]))
    checks.append({"test": "power_non_decreasing_delta_with_mc_tolerance_0.04", "passed": all(delta_checks), "comparisons": len(delta_checks)})
    for dimension in ("n_tasks", "n_buildings"):
        comparisons = []
        fixed = defaultdict(dict)
        for row in power_rows:
            key = (row["variance_scenario"], row["icc_scenario"], row["true_delta_assumption"], row["n_buildings"] if dimension == "n_tasks" else row["n_tasks"])
            fixed[key][int(row[dimension])] = float(row["clustered_simulation_power"])
        for values in fixed.values():
            ordered = [values[key] for key in sorted(values)]
            comparisons.extend(b + 0.04 >= a for a, b in zip(ordered, ordered[1:]))
        checks.append({"test": f"power_non_decreasing_{dimension}_with_mc_tolerance_0.04", "passed": all(comparisons), "comparisons": len(comparisons)})
    residual_variance = float(audit["variance_scenarios"]["central"]) * (1 - 0.20)
    n_tasks = 100
    rng = random.Random(SEED + 910000)
    sums = [sum(rng.gauss(0.0, math.sqrt(residual_variance)) for _ in range(n_tasks)) for _ in range(10000)]
    simulated_se = statistics.stdev(sums)
    analytic_se = math.sqrt(residual_variance * n_tasks)
    checks.append({"test": "independent_residual_sum_se_matches_analytic", "analytic_se": analytic_se, "simulated_se": simulated_se, "relative_error": abs(simulated_se - analytic_se) / analytic_se, "tolerance": 0.05, "passed": abs(simulated_se - analytic_se) / analytic_se <= 0.05})
    return {"suite": "aggregation_power_regression_v2", "passed": all(check["passed"] for check in checks), "checks": checks, "formula_scope": "power scenarios use t critical and task-level independent residual variance sigma_e2*N"}


def required_n_audit(inputs: dict[str, object]) -> dict:
    dist = NormalDist()
    mde_diffs = []
    required_diffs = []
    central_mde_rows = [row for row in inputs["required_n"] if row.get("record_type") == "MDE" and row.get("assumption_set_id") == "central"]
    central_required_rows = [row for row in inputs["required_n"] if row.get("record_type") == "required_N" and row.get("assumption_set_id") == "central"]
    variance = None
    for row in inputs["required_n"]:
        if row.get("assumption_set_id") == "central" and row.get("variance_source") == "empirical_A2_minus_A0_paired_delta":
            if row.get("record_type") == "MDE" and number(row.get("n_tasks")):
                variance = number(row.get("variance", "")) or variance
    if variance is None:
        variance = 0.0011430578779364879
    for row in central_mde_rows:
        n = number(row.get("n_tasks"))
        if n is None:
            continue
        for power, field in ((0.8, "MDE_80"), (0.9, "MDE_90")):
            observed = number(row.get(field))
            expected = (dist.inv_cdf(1 - ALPHA / 2) + dist.inv_cdf(power)) * math.sqrt(variance / n)
            if observed is not None:
                mde_diffs.append(abs(observed - expected))
    for row in central_required_rows:
        effect = number(row.get("effect_size"))
        power = number(row.get("target_power"))
        required = row.get("required_N", "")
        if effect is None or power is None or not required.isdigit():
            continue
        expected = math.ceil(((dist.inv_cdf(1 - ALPHA / 2) + dist.inv_cdf(power)) ** 2) * variance / (effect * effect))
        required_diffs.append(abs(int(required) - expected))
    return {"source_path": rel(OPP / "POST_BLOCK2_CLUSTERED_POWER" / "aggregation_required_N.csv"), "source_sha256": sha256(OPP / "POST_BLOCK2_CLUSTERED_POWER" / "aggregation_required_N.csv"), "normal_formula": "(z_(1-alpha/2)+z_power)*sqrt(empirical_task_delta_variance/N)", "central_variance": variance, "max_abs_MDE_difference": max(mde_diffs) if mde_diffs else None, "max_abs_required_N_difference": max(required_diffs) if required_diffs else None, "cluster_design_effect_in_source_file": False, "interpretation": "normal approximation is internally consistent for independent-task variance but does not include building clustering; clustered table is conservative design-only evidence"}


def report_text(pack_info: dict, selection: dict, hierarchy: list[dict[str, object]], agg_rows: list[dict[str, object]], clean_summary: dict, uncertainty: dict, ref_rows: list[dict[str, object]], deploy_rows: list[dict[str, object]], split_rows: list[dict[str, object]], power_audit: dict, required_audit: dict) -> tuple[str, str]:
    a4 = next(row for row in deploy_rows if row["feature_name"] == "HoHoNet_HorizonNet_or_LHFeat_preannotation")
    lines = [
        "# Aggregation-first 前置确认审计",
        "",
        "## 最终分类",
        "",
        "`A4_DEVELOPMENT_NOT_READY`",
        "",
        "A0/A2/A3/A5 的回顾性开发证据可以保留；但真正 GT-blind、deployable、topology-aware A4 当前不能进入开发确认，因为没有覆盖目标 aggregation tasks 的 SHA-bound pre-outcome image-evidence matrix。该结论不是 A4 科学性能结论，也不是 prospective confirmation。",
        "",
        "## 输入版本选择",
        "",
        f"- 选择：`{selection['selected_pack']}`。v3 manifest mismatches：`{len(pack_info['v3']['manifest_mismatches'])}`。",
        f"- v2：`{pack_info['v2']['status']}`，profile P0 inventory=`{pack_info['v2']['profile_p0_inventory_count']}`，QA/manifest SHA 分别为 `{pack_info['v2']['qa_sha256']}` / `{pack_info['v2']['manifest_sha256']}`。",
        f"- v3：`{pack_info['v3']['status']}`，profile P0 inventory=`{pack_info['v3']['profile_p0_inventory_count']}`，formal profile 已绑定 `final_calibration_profile_20260817_v1`；QA/manifest SHA 分别为 `{pack_info['v3']['qa_sha256']}` / `{pack_info['v3']['manifest_sha256']}`。",
        "- v2 只用于版本选择审计；本次数据表全部来自 v3 和独立 development audit outputs，不跨版拼接字段。",
        "",
        "## 数据层级与分母",
        "",
        f"- v3 task/context index：`{len(hierarchy)}` 行；aggregation development universe：`{len(agg_rows)}` 个 task-context，`{len({row.get('aggregation_building_id') for row in agg_rows})}` 个 building scene。",
        "- v3 `building_support_summary.csv` 的 327/327 raw `building_id` 是带 hash 的 base_task_id，不是真实 MP3D scene；原文件未改。本次 aggregation index 使用 C1 frozen crowd sidecar 的 `building_id`，其余 task identity 仅在本地审计中标为 derived，不把 raw support summary 当作正确 building registry。",
        f"- A0 evaluable：`{clean_summary['a0_evaluable']}/101`；clean A2 evaluable：`{clean_summary['clean_a2_evaluable']}/101`；A3：`{clean_summary['a3_evaluable']}/101`；A4：`{clean_summary['a4_evaluable']}/101`；A5：`{clean_summary['a5_evaluable']}/101`。",
        f"- A0 与 clean A2 的共同可评价分母：`{clean_summary['a0_clean_a2_common_evaluable_tasks']}` 个 task；所有 A0/A2/A3/A4/A5 的共同可评价分母：`{clean_summary['all_five_evaluable']}`，因为 A4 `source_absent`。未评价的 101 行均保留在 `DATA_HIERARCHY_AND_DENOMINATOR.csv`，没有从分母删除。",
        f"- clean A2-A0 task-paired delta：n=`{clean_summary['a0_clean_a2_common_evaluable_tasks']}`，mean=`{clean_summary['mean_delta']:.9f}`，variance=`{clean_summary['variance_delta']:.9f}`。这只是 development evidence。",
        f"- LOBO 方向：`{uncertainty['lobo']['positive']}` positive、`{uncertainty['lobo']['negative']}` negative、`{uncertainty['lobo']['zero']}` zero，共 `{uncertainty['lobo']['n_folds_with_both_methods']}` 个有两方法结果的 fold，不支持稳定方向结论。",
        f"- building-stratified bootstrap：`{uncertainty['building_stratified']['n_buildings']}` 个 paired buildings，95% CI=`{uncertainty['building_stratified']['ci95']}`；few-cluster uncertainty 明显不能按 task 独立处理。",
        "",
        "## Reference readiness",
        "",
        "- public MP3D/HoHoNet reference 可用于 development 评价，但 test 只有少量局部研究者修正，validation 没有研究者自己的修正；均不称为全量 user-verified。",
        "- C1 13 条 conflict 是 candidate-only，`reference_modified=false`，必须 strict exclusion；不能依据聚合结果改 reference。",
        f"- C2-B scope audit 仍有 pending conflict count=`{inputs_ref_pending(ref_rows)}`；该条保持 source_absent/pending，不能进入 closed reference claim。",
        "- 详细 coverage、source path、SHA 和 exclusion 状态见 `REFERENCE_READINESS.csv`。",
        "",
        "## Deployability",
        "",
        f"- panorama 原图输入存在，但只证明 image file 可读；A4 所需的 pre-outcome topology/evidence feature matrix 仍缺。",
        f"- C1 preannotation feature：{a4['coverage']}；没有 ready frozen matrix。",
        "- boundary/line、portal/opening、独立 occlusion proxy 的 SHA-bound A4 source absent；现有 post-task worker flags、reference cache 或 candidate-only feature audit 不可替代。",
        "- A4 的完整 matrix 不能读取当前 task worker outcome，也不能读取任何候选聚合结果来反推 feature。",
        "",
        "## Development/holdout",
        "",
        f"- 已物化 deterministic building-disjoint split：development `{sum(row['split'] == 'development' for row in split_rows)}` buildings，internal holdout `{sum(row['split'] == 'internal_holdout' for row in split_rows)}` buildings；按 `sha256(seed:building)` 排序，seed=`{SEED}`，未读取任何 A0/A2/A3/A4/A5 outcome。",
        "- 13 个 building 足以形成一次内部留出，但不足以支持 15-building 的当前数据宣称；更重要的是 A4 image feature source absent，所以 split 只能作为后续开发占位，不能宣布 A4 development-ready。",
        "",
        "## Baseline 与功效",
        "",
        "- clean A2 只改变 worker weight，保留 frozen `min(boundary, wall)` medoid eligibility；没有把 topology mismatch 变成可评价结果。",
        f"- `aggregation_required_N.csv` 的 central normal approximation 与公式最大 MDE 差异=`{required_audit['max_abs_MDE_difference']}`，required-N 最大差异=`{required_audit['max_abs_required_N_difference']}`；它没有 building cluster design effect。",
        f"- 保守 clustered simulation 使用 task delta variance x2、经验 building ICC=`{power_audit['empirical_icc']:.6f}`、two-sided alpha=`{ALPHA}`、seed=`{SEED}`、replicates=`{POWER_REPLICATES}`。`CONSERVATIVE_CLUSTERED_POWER.csv` 中的 true_delta 只是模拟假设，不是 observed effect。",
        "",
        "## 边界",
        "",
        "- 未实现/调优最终 A4；未启动 prospective 标注；未生成 Block 3；未做 Full-vs-Global 或 continuation-routing 设计；未把 oracle evaluator 当算法性能。",
        "- 未修改 raw export、active logs、历史冻结工件、method contract、SAP、routing 或现有正式分析目录；v2/v3 pack 均未修改。",
        "",
    ]
    readme = "# Aggregation-first preflight readiness\n\n- Classification: **A4_DEVELOPMENT_NOT_READY**\n- Selected input: `post_block2_analysis_pack_20260817_v3`\n- This directory is an independent, read-only audit output.\n- A4 implementation, prospective annotation, Block3, routing continuation and scientific confirmation were not performed.\n\nSee `AGGREGATION_PREFLIGHT_REPORT.md` for denominator, reference, deployability, split and conservative power details.\n"
    return readme, "\n".join(lines)


def inputs_ref_pending(ref_rows: list[dict[str, object]]) -> object:
    for row in ref_rows:
        if row.get("reference_regime") == "C2B_pending_conflict":
            return row.get("coverage", 0)
    return 0


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    pack_info, selection = pack_comparison()
    inputs = load_inputs()
    hierarchy, agg_rows, ref_counts = make_hierarchy(inputs)
    clean_rows, clean_summary = write_clean_a2_a0(agg_rows)
    uncertainty = uncertainty_and_lobo(inputs, clean_rows)
    ref_rows = reference_rows(inputs, clean_summary)
    deploy_rows = deployability_rows(inputs, agg_rows)
    split_rows = split_manifest(agg_rows, clean_rows, inputs.get("ref_queue", []))
    by_building = defaultdict(list)
    for row in clean_rows:
        by_building[str(row["building_scene_id"])].append(float(row["task_paired_delta_clean_a2_minus_a0"]))
    power_rows, power_audit = power_grid(clean_summary, by_building)
    power_tests = power_regression_tests(power_rows, power_audit)
    required_audit = required_n_audit(inputs)

    hierarchy_fields = list(hierarchy[0]) if hierarchy else []
    agg_fields = list(agg_rows[0]) if agg_rows else []
    write_csv(OUT / "DATA_HIERARCHY_AND_DENOMINATOR.csv", hierarchy, hierarchy_fields)
    write_csv(OUT / "AGGREGATION_METHOD_DENOMINATOR.csv", [
        {"method": short, "method_name": method, "total_task_contexts": len(agg_rows), "evaluable_quality_count": sum(bool(row.get(f"{short.lower()}_quality")) for row in agg_rows), "not_evaluable_or_source_absent_count": sum(not bool(row.get(f"{short.lower()}_quality")) for row in agg_rows), "all_rows_retained": "True", "source_status": Counter(row.get(f"{short.lower()}_status", "") for row in agg_rows)}
        for short, method in METHODS
    ], ["method", "method_name", "total_task_contexts", "evaluable_quality_count", "not_evaluable_or_source_absent_count", "all_rows_retained", "source_status"])
    write_csv(OUT / "REFERENCE_READINESS.csv", ref_rows)
    write_csv(OUT / "A4_DEPLOYABILITY_MATRIX.csv", deploy_rows)
    write_csv(OUT / "DEVELOPMENT_HOLDOUT_SPLIT_MANIFEST.csv", split_rows)
    write_csv(OUT / "CLEAN_A2_A0_COMMON_DENOMINATOR.csv", clean_rows)
    write_csv(OUT / "CONSERVATIVE_CLUSTERED_POWER.csv", power_rows)
    write_json(OUT / "POWER_ASSUMPTIONS_AND_AUDIT.json", {"required_N_audit": required_audit, "clustered_power_audit": power_audit})
    write_json(OUT / "POWER_REGRESSION_TESTS.json", power_tests)
    write_json(OUT / "PACK_VERSION_COMPARISON.json", {"pack_comparison": pack_info, "selection": selection})
    write_json(OUT / "A2_A0_UNCERTAINTY_AND_LOBO.json", uncertainty)
    readme, report = report_text(pack_info, selection, hierarchy, agg_rows, clean_summary, uncertainty, ref_rows, deploy_rows, split_rows, power_audit, required_audit)
    statistical_addendum = "\n\n## 定向统计修正（v2）\n\n"
    statistical_addendum += "- residual 为 task-level 独立误差：聚合和的方差为 `sigma_e2 * N`，不再使用 `sigma_e2 * sum(n_j^2)`。\n"
    statistical_addendum += f"- 不等 cluster size 方差分量：`MSB=SSB/(J-1)`，`MSW=SSW/(N-J)`，`C=(N-sum(n_j^2)/N)/(J-1)`，`sigma_u2=max(0,(MSB-MSW)/C)`，`sigma_e2=max(0,MSW)`；经验 ICC={power_audit['empirical_icc']:.6f}，仅作为 `small_cluster_noisy_estimate_J_12`。\n"
    statistical_addendum += "- ICC sensitivity：`0, 0.05, 0.10, 0.20, empirical`；variance scenarios：`central` 与 `pessimistic_2x`；临界值为 `t(df=J-1)`。每个 scenario/ICC/N/building/delta 均单独输出。\n"
    statistical_addendum += f"- nominal alpha=`0.05`；已知 cluster_se 配合 t 临界值时 implied conservative alpha：J=10 `{power_audit['implied_conservative_alpha_by_buildings']['10']:.6f}`，J=12 `{power_audit['implied_conservative_alpha_by_buildings']['12']:.6f}`，J=15 `{power_audit['implied_conservative_alpha_by_buildings']['15']:.6f}`；delta=0 测试与该 implied alpha 比较，容差仅为 3 个 Monte Carlo 标准误。\n"
    statistical_addendum += f"- 新增 power regression tests：`{'PASS' if power_tests['passed'] else 'FAIL'}`。\n"
    statistical_addendum += "- split 表只报告 context、paired-evaluable support 和 reference conflict support，不读取或输出 holdout quality delta；支持不足时标记 placeholder。\n"
    readme += statistical_addendum
    report += statistical_addendum
    (OUT / "README.md").write_text(readme, encoding="utf-8")
    (OUT / "AGGREGATION_PREFLIGHT_REPORT.md").write_text(report, encoding="utf-8")

    inputs_for_manifest = {
        "selected_pack_provenance": PACK_V3 / "POST_BLOCK2_DATA_PROVENANCE.json",
        "selected_pack_manifest": PACK_V3 / "ARTIFACT_HASH_MANIFEST.json",
        "selected_pack_submission_master": PACK_V3 / "post_block2_submission_master.csv",
        "selected_pack_task_context_master": PACK_V3 / "post_block2_task_context_master.csv",
        "selected_pack_building_support_summary_raw": PACK_V3 / "building_support_summary.csv",
        "selected_pack_aggregation_candidates": PACK_V3 / "aggregation_candidate_geometries.csv",
        "v2_provenance_for_version_comparison": PACK_V2 / "POST_BLOCK2_DATA_PROVENANCE.json",
        "v2_manifest_for_version_comparison": PACK_V2 / "ARTIFACT_HASH_MANIFEST.json",
        "cross_fitted_selector_results": OPP / "POST_BLOCK2_AGGREGATION_OPPORTUNITY_AUDIT" / "cross_fitted_selector_results.csv",
        "leave_one_building_out": OPP / "POST_BLOCK2_AGGREGATION_OPPORTUNITY_AUDIT" / "leave_one_building_out.csv",
        "variable_corner_count_audit": OPP / "POST_BLOCK2_AGGREGATION_OPPORTUNITY_AUDIT" / "variable_corner_count_audit.csv",
        "aggregation_required_N": OPP / "POST_BLOCK2_CLUSTERED_POWER" / "aggregation_required_N.csv",
        "c1_crowd_structure": ROOT / "analysis_results" / "c1_formal_audit_20260802_v16_final" / "c1_formal_audit_20260802_7fcacc5c2d6c_bf5def46_6bc67c03" / "geometry_task_crowd_structure_C1.csv",
        "c1_preannotation_features": ROOT / "analysis_results" / "c1_formal_audit_20260802_v16_final" / "c1_formal_audit_20260802_7fcacc5c2d6c_bf5def46_6bc67c03" / "c1_preannotation_task_features.csv",
        "c1_preannotation_feature_manifest": ROOT / "analysis_results" / "c1_formal_audit_20260802_v16_final" / "c1_formal_audit_20260802_7fcacc5c2d6c_bf5def46_6bc67c03" / "c1_preannotation_task_features_manifest.json",
        "reference_conflict_queue": ROOT / "analysis_results" / "reference_conflict_sensitivity_audit_20260805_v2" / "c1_candidate_screen" / "c1_gt_conflict_review_queue.csv",
        "c2b_scope_audit": ROOT / "analysis_results" / "c2b_closeout_20260806_final" / "c2b_gt_scope_resolution_audit.json",
        "reference_registry_post_c2": ROOT / "analysis_results" / "c2a_rp_local_launch_20260807_inputs_v2" / "reference_registry_post_c2_local.csv",
        "stage3_candidate_feature_manifest": ROOT / "analysis_results" / "stage3_test_preparation_20260804_v1" / "stage3_test_feature_candidate_manifest.json",
        "c2_feature_freeze_manifest": ROOT / "analysis_results" / "c2b_validation_static_20260802_v16" / "static" / "c2_feature_freeze_manifest.json",
        "calibration_task_feature_matrix": ROOT / "analysis_results" / "calibration_dual_track_processing_20260815_v2" / "task_feature_matrix.csv",
        "calibration_evidence_long": ROOT / "analysis_results" / "calibration_dual_track_processing_20260815_v2" / "calibration_evidence_long.csv",
        "final_profile_manifest": FINAL_PROFILE / "analysis_manifest.json",
        "final_pooled_profile_frozen": FINAL_PROFILE / "pooled_worker_profile_frozen.json",
        "final_qgt_model": FINAL_PROFILE / "final_c1_c2_qgt_model_v1.json",
        "final_pooled_profile_csv": FINAL_PROFILE / "pooled_worker_profile_v2.csv",
        "scope_note": ROOT / "export_label" / "RAW_DATA_AND_GROUND_TRUTH_SCOPE_NOTE_20260817.md",
    }
    missing_inputs = [name for name, path in inputs_for_manifest.items() if not path.is_file()]
    input_sha = {name: {"path": rel(path), "sha256": sha256(path)} for name, path in inputs_for_manifest.items() if path.is_file()}
    output_files = sorted(path for path in OUT.iterdir() if path.is_file() and path.name != "analysis_manifest.json")
    manifest = {
        "schema_version": "aggregation_preflight_readiness_manifest_v1",
        "audit_version": "aggregation_preflight_readiness_20260817_v1",
        "classification": "A4_DEVELOPMENT_NOT_READY",
        "selected_pack": selection,
        "input_sha256": input_sha,
        "missing_inputs": missing_inputs,
        "output_sha256": {path.name: sha256(path) for path in output_files},
        "generator_sha256": sha256(Path(__file__)),
        "hash_mismatches": pack_info["v3"]["manifest_mismatches"],
        "manifest_self_sha256": "not_bound_recursive",
        "read_only_boundaries": {"raw_export_modified": False, "active_logs_modified": False, "historical_freeze_modified": False, "method_contract_modified": False, "sap_modified": False, "routing_modified": False, "formal_analysis_dirs_modified": False, "a4_implemented": False, "prospective_annotation_started": False, "block3_generated": False, "oracle_as_performance": False},
    }
    write_json(OUT / "analysis_manifest.json", manifest)
    print(json.dumps({"output_dir": str(OUT), "classification": manifest["classification"], "selected_pack": selection["selected_pack"], "manifest_sha256": sha256(OUT / "analysis_manifest.json"), "output_count": len(output_files)}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
