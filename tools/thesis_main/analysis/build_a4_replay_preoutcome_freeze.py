"""Freeze a GT-blind, strict deployment-pool replay input.

This module intentionally stops before any outcome, quality, reference, or
selector fitting.  The only candidate universe is the formal C1 geometry
producer universe; assignment realization is provenance only.
"""

from __future__ import annotations

import csv
import hashlib
import json
import math
import re
from collections import Counter, defaultdict
from pathlib import Path
from statistics import median

from tools.thesis_main.analysis.geometry_cluster_v2 import cluster_geometry_records
from tools.thesis_main.analysis.geometry_consensus.medoid import (
    frozen_geometry_tie_key,
    select_medoid,
)
from tools.thesis_main.analysis.geometry_consensus.pairwise import pairwise_similarity
from tools.thesis_main.analysis.geometry_consensus.representation import normalize_geometry


ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / "analysis_results/a4_replay_preoutcome_freeze_20260817_v1"
IDENTITY = ROOT / "analysis_results/a4_deployment_pool_identity_20260817_v1/A4_CANDIDATE_DEPLOYMENT_POOL_IDENTITY_C1_v1.csv"
FORMAL = ROOT / "analysis_results/c1_formal_audit_20260802_v16_final/c1_formal_audit_20260802_7fcacc5c2d6c_bf5def46_6bc67c03"
GEOMETRY = FORMAL / "c1_canonical_geometry.jsonl"
SUMMARY = FORMAL / "c1_canonicalization_summary.json"
PAIRWISE = FORMAL / "geometry_pairwise_similarity_C1.csv"
ALIGNMENT = ROOT / "analysis_results/a4_image_evidence_substrate_20260817_v2/DEVELOPMENT_CANDIDATE_IMAGE_ALIGNMENT.csv"
RULE = ROOT / "docs/thesis_main/geometry_peer_candidate_rule_manifest_v1.json"
CONTRACT = ROOT / "docs/thesis_main/PAPER_A_METHOD_CONTRACT_CURRENT.json"
SPLIT = ROOT / "analysis_results/aggregation_preflight_readiness_20260817_v1/DEVELOPMENT_HOLDOUT_SPLIT_MANIFEST.csv"

DENY_PATHS = (
    "post_block2_opportunity_analysis_20260817_v1",
    "cross_fitted_selector_results.csv",
    "c1_gt_quality",
    "public_gt_quality",
    "active_logs",
    "holdout_effect",
)
DENY_TOKENS = {
    "gt", "reference", "quality", "iou", "outcome", "difficulty",
    "active_time", "lead_time", "worker_quality", "public_gt_quality",
    "delivery_adjusted_quality",
}
ALIGNMENT_FIELDS = (
    "vertical_edge_support",
    "ceiling_boundary_support",
    "floor_boundary_support",
    "seam_segment_boundary_support",
)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _tokens(value: str) -> set[str]:
    return set(re.findall(r"[a-z0-9]+", value.lower()))


def validate_requested_projection(path: str, columns: list[str]) -> bool:
    lowered = path.replace("\\", "/").lower()
    if any(fragment in lowered for fragment in DENY_PATHS):
        raise PermissionError(f"denied input path: {path}")
    denied = [column for column in columns if _tokens(column) & DENY_TOKENS]
    if denied:
        raise PermissionError(f"denied input columns: {denied}")
    return True


def _read_csv(path: Path, columns: list[str], trace: list[dict]) -> list[dict]:
    validate_requested_projection(str(path), columns)
    with path.open(newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        missing = [column for column in columns if column not in (reader.fieldnames or [])]
        if missing:
            raise ValueError(f"missing columns in {path}: {missing}")
        rows = [{column: row.get(column, "") for column in columns} for row in reader]
    trace.append({"path": str(path.relative_to(ROOT)), "projected_columns": columns})
    return rows


def _read_json(path: Path, trace: list[dict]) -> dict:
    validate_requested_projection(str(path), [])
    with path.open(encoding="utf-8") as handle:
        value = json.load(handle)
    trace.append({"path": str(path.relative_to(ROOT)), "projected_columns": []})
    return value


def _read_geometry(path: Path, trace: list[dict]) -> list[dict]:
    validate_requested_projection(str(path), [])
    fields = (
        "canonical_annotation_id", "worker_id", "base_task_id", "condition", "corners_px",
        "width", "height", "eligible_for_geometry_loo", "geometry_hash",
    )
    rows = []
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                raw = json.loads(line)
                rows.append({field: raw.get(field, "") for field in fields})
    trace.append({"path": str(path.relative_to(ROOT)), "projected_columns": list(fields)})
    return rows


def _first(row: dict, *names: str) -> str:
    for name in names:
        if row.get(name, "") != "":
            return str(row[name])
    return ""


def _bool(value: object) -> bool:
    return str(value).strip().lower() in {"true", "1", "yes"}


def _worker_key(value: object) -> str:
    text = str(value).strip()
    if text[:1].lower() == "w":
        text = text[1:]
    return text.lstrip("0") or "0"


def _finite(value: object) -> bool:
    try:
        return math.isfinite(float(value))
    except (TypeError, ValueError):
        return False


def classify_primary_eligibility(row: dict, geometry: dict | None, excluded_workers: set[str]) -> dict:
    """Apply the formal producer order without collapsing provenance layers."""
    if str(row.get("candidate_parse_status", "")).lower() != "valid":
        return {"eligible": False, "reason": "parse_invalid"}
    if _worker_key(row.get("worker_id", "")) in excluded_workers:
        return {"eligible": False, "reason": "administratively_excluded_worker"}
    if geometry is None:
        return {"eligible": False, "reason": "join_failure"}
    if not _bool(geometry.get("eligible_for_geometry_loo")):
        return {"eligible": False, "reason": "formal_geometry_loo_ineligible"}
    if not geometry.get("_normalization_valid", False):
        return {"eligible": False, "reason": "parse_invalid"}
    return {"eligible": True, "reason": ""}


def normalized_midrank(values: list[float], value: float) -> float:
    if len(values) == 1:
        return 1.0
    less = sum(item < value for item in values)
    equal = sum(item == value for item in values)
    rank = less + (equal + 1) / 2.0
    return (rank - 1.0) / (len(values) - 1.0)


def _formal_key(record: dict, task_id: str) -> tuple:
    return tuple(frozen_geometry_tie_key(record, task_id=task_id))


def _call_normalize(row: dict):
    corners = row.get("corners_px", row.get("corners", []))
    width = row.get("width", 1)
    height = row.get("height", 1)
    value = normalize_geometry(corners, width=width, height=height)
    return value, isinstance(value, dict) and value.get("valid") is True


def _call_cluster(records: list[dict], params: dict) -> dict:
    return cluster_geometry_records(
        records,
        min_q_boundary=params["min_q_boundary"],
        min_q_wallwall=params["min_q_wallwall"],
        minimum_valid_k=params["minimum_valid_k"],
        maximum_partition_count=params["maximum_partition_count"],
        maximum_search_nodes=params["maximum_search_nodes"],
    )


def _partition_records(result: object, records: list[dict]) -> list[list[dict]]:
    raw = result["cluster_membership_json"]
    if isinstance(raw, str):
        raw = json.loads(raw)
    if isinstance(raw, dict):
        raw = raw.get("clusters", [])
    by_id = {str(row["canonical_annotation_id"]): row for row in records}
    partitions = []
    for partition in raw:
        members = []
        for item in partition:
            key = str(item.get("canonical_annotation_id", item) if isinstance(item, dict) else item)
            if key in by_id:
                members.append(by_id[key])
        if members:
            partitions.append(members)
    return partitions


def _pair_score(left: dict, right: dict) -> float | None:
    value = pairwise_similarity(left["normalized_geometry"], right["normalized_geometry"])
    if isinstance(value, dict):
        if not _bool(value["metric_compatible"]):
            return None
        return min(float(value["q_boundary"]), float(value["q_wallwall"]))
    if isinstance(value, (tuple, list)):
        q_boundary, q_wallwall, metric_compatible = value
        return min(float(q_boundary), float(q_wallwall)) if metric_compatible else None
    raise TypeError("pairwise_similarity must return q_boundary, q_wallwall, metric_compatible")


def _medoid_ranking(members: list[dict], pool_id: str) -> list[dict]:
    scores = {}
    for index, left in enumerate(members):
        for other_index in range(index + 1, len(members)):
            score = _pair_score(left, members[other_index])
            if score is not None:
                scores[(index, other_index)] = score
    indices = tuple(range(len(members)))
    result = select_medoid(members, indices, scores, task_id=pool_id)
    ranked = result[2]
    by_id = {str(item["canonical_annotation_id"]): item for item in members}
    ranked_ids = [str(item[3]) for item in ranked]
    if set(ranked_ids) != set(by_id) or len(ranked_ids) != len(by_id):
        raise RuntimeError("formal medoid ranking does not cover the full cluster")
    return [by_id[item] for item in ranked_ids]


def _medoid(members: list[dict], pool_id: str) -> dict:
    return _medoid_ranking(members, pool_id)[0]


def _cluster_state(records: list[dict], pool_id: str, params: dict) -> dict:
    result = _call_cluster(records, params)
    partitions = _partition_records(result, records)
    status = str(result["task_crowd_structure_status"])
    reason = str(result["structure_reason"])
    unique = str(result["partition_status"]) == "unique"
    by_id = {str(row["canonical_annotation_id"]): row for row in records}
    medoid_id = str(result["largest_cluster_medoid_annotation_id"] or "")
    largest = next((group for group in partitions if medoid_id in {str(item["canonical_annotation_id"]) for item in group}), [])
    medoid = by_id.get(medoid_id) if medoid_id else None
    return {
        "status": status,
        "reason": reason,
        "partition_unique": unique,
        "partitions": partitions,
        "largest": largest,
        "medoid": medoid,
    }


def decide_variant_action(variant: str, state: dict, scores: dict[str, float]) -> dict:
    """Choose only from an already A0-evaluable pool; never rescue A0."""
    base = {
        "action_disposition": "unresolved",
        "selected_candidate_annotation_id": "",
        "fallback_status": "",
        "failure_reason": "",
        "image_score_tie_count": "",
        "image_tie_break_rule": "",
    }
    if state.get("a0_disposition") != "selected":
        base["failure_reason"] = "a0_unresolved_no_rescue"
        return base
    a0 = str(state["a0_candidate_id"])
    if not state.get("alignment_ok", False):
        base.update(action_disposition="fallback_to_a0", selected_candidate_annotation_id=a0,
                    fallback_status="alignment_not_one_to_one_or_missing")
        return base
    partitions = state.get("clusters", [])
    if variant == "A4-S":
        candidates = [group for group in partitions if len(group) >= 2]
        if len(candidates) < 2:
            base.update(action_disposition="selected", selected_candidate_annotation_id=a0,
                        failure_reason="no_supported_alternative")
            return base
        groups = candidates
    elif variant == "A4-C":
        groups = [group for group in partitions if len(group) >= 2]
        if not groups:
            base.update(action_disposition="fallback_to_a0", selected_candidate_annotation_id=a0,
                        fallback_status="no_supported_cluster")
            return base
    else:
        groups = [state.get("largest", [])]
    groups = [group for group in groups if group]
    if not groups:
        base.update(action_disposition="fallback_to_a0", selected_candidate_annotation_id=a0,
                    fallback_status="empty_cluster")
        return base

    def cluster_key(group: list[dict]) -> tuple:
        value = median(scores[str(item["canonical_annotation_id"])] for item in group)
        medoid = _medoid_ranking(group, str(state.get("pool_id", "")))[0]
        return (-value, -len(group), _formal_key(medoid, str(state.get("pool_id", ""))))

    selected_group = sorted(groups, key=cluster_key)[0]
    if variant == "A4-S":
        selected = _medoid(selected_group, str(state.get("pool_id", "")))
    else:
        top_score = max(scores[str(item["canonical_annotation_id"])] for item in selected_group)
        tied_ids = {
            str(item["canonical_annotation_id"])
            for item in selected_group
            if scores[str(item["canonical_annotation_id"])] == top_score
        }
        selected = next(
            item for item in _medoid_ranking(selected_group, str(state.get("pool_id", "")))
            if str(item["canonical_annotation_id"]) in tied_ids
        )
    selected_id = str(selected["canonical_annotation_id"])
    base.update(
        action_disposition="selected",
        selected_candidate_annotation_id=selected_id,
        selected_worker_id=str(selected.get("worker_id", "")),
    )
    if variant in {"A4-C", "A4-L"}:
        base["image_score_tie_count"] = len(tied_ids)
        base["image_tie_break_rule"] = "full_cluster_formal_medoid_ranking"
    elif variant == "A4-S":
        base["image_tie_break_rule"] = "cluster_formal_medoid_final_tie_key"
    return base


def _read_flexible_csv(path: Path, candidates: list[str], trace: list[dict]) -> list[dict]:
    validate_requested_projection(str(path), candidates)
    with path.open(newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        available = [name for name in candidates if name in (reader.fieldnames or [])]
        rows = [{name: row.get(name, "") for name in available} for row in reader]
    trace.append({"path": str(path.relative_to(ROOT)), "projected_columns": available})
    return rows


def _write_csv(path: Path, fieldnames: list[str], rows: list[dict]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def _row_index(rows: list[dict], key: str) -> dict[str, list[dict]]:
    index = defaultdict(list)
    for row in rows:
        index[str(row.get(key, ""))].append(row)
    return index


def _source_record(formal: dict, normalized: object) -> dict:
    record = dict(formal)
    record["canonical_annotation_id"] = str(formal.get("canonical_annotation_id", ""))
    record["normalized_geometry"] = normalized
    record["geometry"] = normalized
    return record


def _pairwise_audit(rows: list[dict], pools: dict[str, list[dict]]) -> dict[str, dict]:
    by_context_worker = defaultdict(set)
    for pool_id, records in pools.items():
        for record in records:
            key = (str(record.get("base_task_id", "")), str(record.get("condition", "")), str(record.get("worker_id", "")))
            by_context_worker[key].add(pool_id)
    edges = defaultdict(set)
    incompatible = defaultdict(int)
    for row in rows:
        base = _first(row, "base_task_id", "task_id", "base_task")
        condition = _first(row, "condition")
        left = _first(row, "worker_id_left", "worker_left", "worker_a", "worker_i", "worker_1")
        right = _first(row, "worker_id_right", "worker_right", "worker_b", "worker_j", "worker_2")
        if not base or not left or not right:
            continue
        pool_ids = by_context_worker[(base, condition, left)] & by_context_worker[(base, condition, right)]
        compatible = _bool(_first(row, "metric_compatible", "compatible", "is_compatible") or "true")
        for pool_id in pool_ids:
            edge = tuple(sorted((left, right)))
            if compatible:
                edges[pool_id].add(edge)
            else:
                incompatible[pool_id] += 1
    result = {}
    for pool_id, records in pools.items():
        workers = [str(item.get("worker_id", "")) for item in records]
        expected = len(workers) * (len(workers) - 1) // 2
        present = len(edges[pool_id])
        result[pool_id] = {
            "expected": expected,
            "present": present,
            "missing": max(0, expected - present),
            "incompatible": incompatible[pool_id],
        }
    return result


def _load_inputs(trace: list[dict]) -> tuple[list[dict], dict[str, list[dict]], dict, dict, dict]:
    identity_fields = [
        "candidate_annotation_id", "worker_id", "stage", "round_id", "condition",
        "base_task_id", "task_id", "project_id", "ls_runtime_task_id", "deployment_pool_id",
        "assignment_realization_status", "assignment_provenance", "observed_canonical_runtime_source_status",
        "identity_mapping_status", "formal_duplicate_status", "appears_in_internal_distribution",
        "candidate_parse_status", "building_scene_id",
    ]
    identity = _read_csv(IDENTITY, identity_fields, trace)
    formal = _read_geometry(GEOMETRY, trace)
    geometry_by_id = _row_index(formal, "canonical_annotation_id")
    normalized_by_id = {}
    for row in formal:
        normalized, valid = _call_normalize(row)
        row["_normalization_valid"] = valid
        normalized_by_id[str(row.get("canonical_annotation_id", ""))] = normalized
    align_fields = ["candidate_annotation_id", *ALIGNMENT_FIELDS]
    alignment = _read_csv(ALIGNMENT, align_fields, trace)
    alignment_by_id = _row_index(alignment, "candidate_annotation_id")
    pairwise = _read_flexible_csv(
        PAIRWISE,
        ["base_task_id", "condition", "worker_id_left", "worker_id_right", "worker_left", "worker_right",
         "worker_a", "worker_b", "worker_i", "worker_j", "worker_1", "worker_2", "metric_compatible",
         "compatible", "is_compatible"],
        trace,
    )
    summary = _read_json(SUMMARY, trace)
    rule = _read_json(RULE, trace)
    contract = _read_json(CONTRACT, trace)
    split_rows = _read_csv(SPLIT, ["building_scene_id", "split"], trace)
    return identity, geometry_by_id, normalized_by_id, alignment_by_id, {
        "pairwise": pairwise, "summary": summary, "rule": rule,
        "contract": contract, "split_rows": split_rows,
    }


def _freeze_parameters(rule: dict, contract: dict) -> dict:
    if rule["status"] != "approved" or rule["interpretation_allowed"] is not True:
        raise RuntimeError("formal geometry rule is not approved for interpretation")
    thresholds = rule["thresholds"]
    geometry_cluster = contract["geometry_cluster"]
    shared_fields = (
        "boundary_grid", "similarity_cutoff", "sensitivity_cutoffs",
        "require_pointwise_correspondence", "minimum_peer_count", "minimum_valid_k",
    )
    for field in shared_fields:
        if thresholds[field] != geometry_cluster[field]:
            raise RuntimeError(f"rule/contract geometry_cluster mismatch: {field}")
    params = {
        "min_q_boundary": float(geometry_cluster["similarity_cutoff"]),
        "min_q_wallwall": float(geometry_cluster["similarity_cutoff"]),
        "minimum_valid_k": int(geometry_cluster["minimum_valid_k"]),
        "maximum_partition_count": int(geometry_cluster["maximum_partition_count"]),
        "maximum_search_nodes": int(geometry_cluster["maximum_search_nodes"]),
    }
    return params


def build(output_dir: Path = OUT) -> dict:
    trace: list[dict] = []
    identity, geometry_by_id, normalized_by_id, alignment_by_id, extra = _load_inputs(trace)
    summary = extra["summary"]
    params = _freeze_parameters(extra["rule"], extra["contract"])
    development_buildings = {
        str(row["building_scene_id"])
        for row in extra["split_rows"]
        if str(row["split"]).lower() == "development"
    }
    identity_buildings = {str(row.get("building_scene_id", "")) for row in identity}
    if len(development_buildings) != 9 or not identity_buildings.issubset(development_buildings):
        raise RuntimeError("identity candidate source is not restricted to the nine development buildings")
    excluded = {
        _worker_key(item)
        for item in summary["geometry_sidecars"]["excluded_worker_ids"]
    }
    geometry_sha = sha256_file(GEOMETRY)
    alignment_sha = sha256_file(ALIGNMENT)
    identity_sha = sha256_file(IDENTITY)
    pairwise_sha = sha256_file(PAIRWISE)
    formal_by_id = {}
    for candidate_id, rows in geometry_by_id.items():
        if len(rows) == 1:
            formal_by_id[candidate_id] = rows[0]

    denominator = []
    primary_by_pool: dict[str, list[dict]] = defaultdict(list)
    for row in identity:
        candidate_id = str(row.get("candidate_annotation_id", ""))
        formal = formal_by_id.get(candidate_id)
        classification = classify_primary_eligibility(row, formal, excluded)
        alignment_rows = alignment_by_id.get(candidate_id, [])
        normalized = normalized_by_id.get(candidate_id)
        alignment_status = "zero" if not alignment_rows else "one" if len(alignment_rows) == 1 else "many"
        output = dict(row)
        output.update({
            "formal_geometry_loo_eligible": str(formal.get("eligible_for_geometry_loo", "")) if formal else "",
            "normalization_valid": str(bool(formal and formal.get("_normalization_valid", False))).lower(),
            "formal_producer_primary_eligible": str(classification["eligible"]).lower(),
            "primary_ineligibility_reason": classification["reason"],
            "alignment_candidate_join_status": alignment_status,
            "alignment_source_sha256": alignment_sha,
            "formal_geometry_source_sha256": geometry_sha,
            "identity_source_sha256": identity_sha,
            "pairwise_source_sha256": pairwise_sha,
        })
        denominator.append(output)
        if classification["eligible"]:
            record = _source_record(formal, normalized)
            record.update({
                "candidate_annotation_id": candidate_id,
                "worker_id": row.get("worker_id", formal.get("worker_id", "")),
                "deployment_pool_id": row.get("deployment_pool_id", ""),
                "base_task_id": row.get("base_task_id", formal.get("base_task_id", "")),
                "condition": row.get("condition", formal.get("condition", "")),
            })
            primary_by_pool[str(row.get("deployment_pool_id", ""))].append(record)

    all_pools = defaultdict(list)
    for row in identity:
        all_pools[str(row.get("deployment_pool_id", ""))].append(row)
    for pool_id in all_pools:
        primary_by_pool.setdefault(pool_id, [])
    pairwise_audit = _pairwise_audit(extra["pairwise"], primary_by_pool)
    pool_rows = []
    actions = []
    action_counts = defaultdict(Counter)
    status_counts = Counter()
    for pool_id in sorted(all_pools):
        records = primary_by_pool[pool_id]
        k = len(records)
        audit = pairwise_audit[pool_id]
        if not records:
            state = {
                "status": "not_evaluable", "reason": "empty_pool_formal_producer_exclusion",
                "partition_unique": False, "partitions": [], "largest": [], "medoid": None,
            }
        else:
            state = _cluster_state(records, pool_id, params)
        status = state["status"]
        reason = state["reason"]
        selected = bool(k >= 3 and state["partition_unique"] and status in {
            "unimodal", "dominant_with_dissent", "supported_multimodal",
        } and state["medoid"])
        if not selected and k >= 3 and audit["missing"] == 0 and audit["incompatible"] == 0:
            reason = reason or "formal_cluster_status_not_selected"
        a0_id = str(state["medoid"].get("canonical_annotation_id", "")) if selected else ""
        cluster_json = json.dumps(
            [[str(item["canonical_annotation_id"]) for item in group] for group in state["partitions"]],
            sort_keys=True,
        )
        context = all_pools[pool_id][0]
        pool_rows.append({
            "deployment_pool_id": pool_id,
            "stage": context.get("stage", ""),
            "round_id": context.get("round_id", ""),
            "condition": context.get("condition", ""),
            "base_task_id": context.get("base_task_id", ""),
            "task_id": context.get("task_id", ""),
            "project_id": context.get("project_id", ""),
            "ls_runtime_task_id": context.get("ls_runtime_task_id", ""),
            "building_scene_id": context.get("building_scene_id", ""),
            "identity_candidate_count": len(all_pools[pool_id]),
            "primary_candidate_k": k,
            "pairwise_expected_edges": audit["expected"],
            "pairwise_present_edges": audit["present"],
            "pairwise_missing_edges": audit["missing"],
            "pairwise_incompatible_edges": audit["incompatible"],
            "partition_unique": str(state["partition_unique"]).lower(),
            "partition_count": len(state["partitions"]),
            "formal_crowd_status": status,
            "formal_crowd_reason": reason,
            "cluster_membership_json": cluster_json,
            "a0_prime_medoid_candidate_annotation_id": a0_id,
            "a0_selection_disposition": "selected" if selected else "unresolved",
            "a0_unresolved_reason": "" if selected else reason,
            "candidate_universe": "formal_producer_primary",
            "reads_quality_or_outcome": "false",
        })
        state_for_action = {
            "pool_id": pool_id,
            "a0_disposition": "selected" if selected else "unresolved",
            "a0_candidate_id": a0_id,
            "alignment_ok": all(len(alignment_by_id.get(str(item["canonical_annotation_id"]), [])) == 1 for item in records)
            and all(_finite(alignment_by_id[str(item["canonical_annotation_id"])][0].get(field)) for item in records for field in ALIGNMENT_FIELDS),
            "clusters": state["partitions"],
            "largest": state["largest"],
        }
        score_by_id = {}
        if state_for_action["alignment_ok"]:
            values = {field: [float(alignment_by_id[str(item["canonical_annotation_id"])][0][field]) for item in records] for field in ALIGNMENT_FIELDS}
            for item in records:
                candidate_id = str(item["canonical_annotation_id"])
                score_by_id[candidate_id] = median(normalized_midrank(values[field], float(alignment_by_id[candidate_id][0][field])) for field in ALIGNMENT_FIELDS)
        for variant in ("A0", "A4-S", "A4-C", "A4-L"):
            if variant == "A0":
                action = {
                    "action_disposition": "selected" if selected else "unresolved",
                    "selected_candidate_annotation_id": a0_id,
                    "fallback_status": "",
                    "failure_reason": "" if selected else reason,
                    "image_score_tie_count": "",
                    "image_tie_break_rule": "",
                }
            else:
                action = decide_variant_action(variant, state_for_action, score_by_id)
            selected_id = action.get("selected_candidate_annotation_id", "")
            action_counts[variant][action["action_disposition"]] += 1
            actions.append({
                "deployment_pool_id": pool_id,
                "variant": variant,
                "primary_candidate_k": k,
                "a0_selection_disposition": "selected" if selected else "unresolved",
                "action_disposition": action["action_disposition"],
                "selected_candidate_annotation_id": selected_id,
                "selected_worker_id": next((str(item.get("worker_id", "")) for item in records if str(item["canonical_annotation_id"]) == selected_id), ""),
                "fallback_status": action.get("fallback_status", ""),
                "failure_reason": action.get("failure_reason", ""),
                "image_score_tie_count": action.get("image_score_tie_count", ""),
                "image_tie_break_rule": action.get("image_tie_break_rule", ""),
                "alignment_join_status": "one_to_one" if state_for_action["alignment_ok"] else "not_one_to_one_or_missing",
                "candidate_image_score_available": str(bool(score_by_id)).lower(),
                "disagreement_with_a0": "not_applicable" if not selected else str(bool(selected_id and selected_id != a0_id)).lower(),
                "preoutcome_fields_only": "true",
                "reads_quality_or_outcome": "false",
            })
        status_counts[status] += 1

    primary_count = sum(len(rows) for rows in primary_by_pool.values())
    reason_counts = Counter(row["primary_ineligibility_reason"] for row in denominator if row["primary_ineligibility_reason"])
    nonempty_status_counts = Counter(row["formal_crowd_status"] for row in pool_rows if int(row["primary_candidate_k"]) > 0)
    k_ge_3_rows = [row for row in pool_rows if int(row["primary_candidate_k"]) >= 3]
    invariant_failures = []
    if len(identity) != 580:
        invariant_failures.append(f"identity_rows={len(identity)}")
    if primary_count != 547:
        invariant_failures.append(f"primary_rows={primary_count}")
    if sum(_worker_key(row.get("worker_id", "")) == "14" for row in identity) != 26:
        invariant_failures.append("excluded_worker_14_count")
    if reason_counts["formal_geometry_loo_ineligible"] != 4:
        invariant_failures.append(f"formal_geometry_loo_ineligible={reason_counts['formal_geometry_loo_ineligible']}")
    if reason_counts["parse_invalid"] != 3:
        invariant_failures.append(f"parse_invalid={reason_counts['parse_invalid']}")
    if len(all_pools) != 139:
        invariant_failures.append(f"pool_count={len(all_pools)}")
    if sum(not rows for rows in primary_by_pool.values()) != 2:
        invariant_failures.append("primary_k_zero_pools")
    if sum(len(rows) >= 3 for rows in primary_by_pool.values()) != 76:
        invariant_failures.append("primary_k_ge_3_pools")
    if nonempty_status_counts != Counter({"unimodal": 26, "dominant_with_dissent": 24, "supported_multimodal": 17, "not_evaluable": 70}):
        invariant_failures.append(f"formal_status={dict(nonempty_status_counts)}")
    if sum(int(row["pairwise_missing_edges"]) for row in k_ge_3_rows) != 0:
        invariant_failures.append("pairwise_missing_edges")
    if sum(int(row["pairwise_incompatible_edges"]) for row in k_ge_3_rows) != 0:
        invariant_failures.append("pairwise_incompatible_edges")
    if sum(row["a0_selection_disposition"] == "selected" for row in pool_rows) != 67:
        invariant_failures.append("a0_selected")
    if sum(row["a0_selection_disposition"] == "unresolved" for row in pool_rows) != 72:
        invariant_failures.append("a0_unresolved")
    if sum(row["alignment_candidate_join_status"] == "one" for row in denominator if row["formal_producer_primary_eligible"] == "true") != 547:
        invariant_failures.append("alignment_primary_one_to_one")
    if invariant_failures:
        raise RuntimeError("pre-outcome freeze invariants failed: " + ", ".join(invariant_failures))

    output_dir.mkdir(parents=True, exist_ok=True)
    denominator_fields = list(identity[0].keys()) + [
        "formal_geometry_loo_eligible", "normalization_valid", "formal_producer_primary_eligible",
        "primary_ineligibility_reason", "alignment_candidate_join_status", "alignment_source_sha256",
        "formal_geometry_source_sha256", "identity_source_sha256", "pairwise_source_sha256",
    ]
    _write_csv(output_dir / "A4_REPLAY_CANDIDATE_DENOMINATOR.csv", denominator_fields, denominator)
    pool_fields = list(pool_rows[0].keys())
    _write_csv(output_dir / "A4_STRICT_POOL_PREOUTCOME_STATE.csv", pool_fields, pool_rows)
    action_fields = list(actions[0].keys())
    _write_csv(output_dir / "A4_PREOUTCOME_POLICY_ACTIONS.csv", action_fields, actions)

    spec = {
        "schema_version": "a4_preoutcome_replay_spec_v1",
        "candidate_universe": {
            "primary": "candidate_parse_status=valid AND worker_id not in c1_canonicalization_summary.excluded_worker_ids AND eligible_for_geometry_loo=true AND normalize_geometry valid",
            "rows_preserved": len(identity), "primary_rows": sum(len(rows) for rows in primary_by_pool.values()),
            "pool_key": "deployment_pool_id", "context_pooling": "forbidden",
        },
        "candidate_layers": {
            "assignment_realization": "provenance_only_not_eligibility",
            "observed_coverage": "577_diagnostic_only_not_performance_denominator",
            "k_less_than_3": "retained_as_not_evaluable",
        },
        "formal_rule_binding": {
            "rule_path": str(RULE.relative_to(ROOT)),
            "contract_path": str(CONTRACT.relative_to(ROOT)),
            "parameters": params,
            "development_buildings": sorted(development_buildings),
        },
        "a0_prime": {
            "producer": "geometry_cluster_v2.cluster_geometry_records",
            "cutoff": params["min_q_boundary"], "minimum_valid_k": params["minimum_valid_k"],
            "maximum_partition_count": params["maximum_partition_count"], "maximum_search_nodes": params["maximum_search_nodes"],
            "selected_statuses": ["unimodal", "dominant_with_dissent", "supported_multimodal"],
            "unresolved": ["empty_pool", "k_less_than_3", "no_dominant_or_supported", "non_unique_partition", "pairwise_missing_or_incompatible"],
        },
        "variants": {
            "A4-S": "unique partition; clusters support>=2; median of four per-pool normalized mid-ranks; median cluster score; ties support then formal medoid; fallback A0",
            "A4-C": "A4-S cluster choice; highest candidate image score within cluster; image ties use full_cluster_formal_medoid_ranking; fallback A0",
            "A4-L": "A0 largest cluster fixed; rerank candidates by image score; image ties use full_cluster_formal_medoid_ranking; fallback A0",
            "normalized_midrank": "k=1 -> 1; otherwise (midrank(value)-1)/(k-1), midrank=(count_less+(count_equal+1)/2)",
            "required_alignment_fields": list(ALIGNMENT_FIELDS),
            "excluded_alignment_fields": ["seam_wrap_consistency", "model_prediction", "worker_quality"],
        },
        "development_replay": {
            "buildings": "9 development buildings only",
            "outer_scheme": "building-disjoint nested/LOBO; estimate any variant choice only in outer-train; evaluate outer-test once",
            "locked_subset": "4-building A4-specific locked subset is not a virgin confirmation set",
            "true_confirmation": "requires new task/building",
        },
        "future_effect_gates_not_evaluated": {
            "strong_go_delta": ">=0.015", "conditional_delta": "0.011<=delta<0.015", "no_go_delta": "<0.011",
            "effect_sensitivity_only": "0.020", "direction_gate": "at least 6/9 buildings non-negative and at least 5/9 strictly positive",
            "selection_rule": "no max-observed selection; outer LOBO only; ties A4-S; A4-S retained as primary safety estimate",
        },
        "read_only_boundaries": {
            "outcome_read": False, "quality_read": False, "reference_read": False, "active_time_read": False,
            "holdout_effect_read": False, "training_started": False, "experiment_started": False,
        },
    }
    (output_dir / "A4_PREOUTCOME_REPLAY_SPEC.json").write_text(json.dumps(spec, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    allowlist = {
        "allowlist": [str(path.relative_to(ROOT)) for path in (IDENTITY, GEOMETRY, SUMMARY, PAIRWISE, ALIGNMENT, RULE, CONTRACT, SPLIT)],
        "deny_paths": list(DENY_PATHS),
        "deny_column_tokens": sorted(DENY_TOKENS),
        "projection_semantics": "CSV physical rows may be parsed, but only allowlisted columns are consumed; denied values are not accessed.",
        "trace": trace,
    }
    (output_dir / "INPUT_ALLOWLIST_DENYLIST.json").write_text(json.dumps(allowlist, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    generator_sha = sha256_file(Path(__file__))
    tie_pool_counts = {
        variant: sum(
            1
            for row in actions
            if row["variant"] == variant
            and row["image_score_tie_count"]
            and int(row["image_score_tie_count"]) > 1
        )
        for variant in ("A4-C", "A4-L")
    }
    report = [
        "# A4 pre-outcome strict-pool replay freeze",
        "",
        "Status: `A4_REPLAY_PREOUTCOME_FREEZE_READY` (input/algo freeze only; no performance claim).",
        "",
        f"- Identity rows: {len(identity)}; formal producer primary eligible: {primary_count}",
        f"- Strict pools: {len(all_pools)}; primary k=0: {sum(not rows for rows in primary_by_pool.values())}; k>=3: {sum(len(rows) >= 3 for rows in primary_by_pool.values())}",
        f"- A0-prime selected: {sum(item['a0_selection_disposition'] == 'selected' for item in pool_rows)}; unresolved: {sum(item['a0_selection_disposition'] == 'unresolved' for item in pool_rows)}",
        f"- Image-score tie pools: A4-C={tie_pool_counts['A4-C']}, A4-L={tie_pool_counts['A4-L']}; C/L ties use full cluster formal medoid ranking.",
        f"- Formal excluded workers: {sorted(excluded)}; W014 is retained only as an administrative exclusion fact.",
        "- Assignment realization is provenance only and does not define primary eligibility.",
        "- A4 variants cannot rescue an unresolved A0 pool; all action rows are pre-outcome.",
        "- A4-C/L image-score ties use the full cluster formal medoid ranking; A4-S cluster-score ties retain the declared support then medoid rule.",
        "- The four prior internal-holdout buildings are not read here and are not a virgin confirmation set.",
        "",
        "## Action dispositions",
        "",
    ]
    for variant in ("A0", "A4-S", "A4-C", "A4-L"):
        report.append(f"- {variant}: {dict(action_counts[variant])}")
    report.extend([
        "",
        "## Provenance and boundaries",
        "",
        f"- Generator SHA256: `{generator_sha}`",
        f"- Formal geometry SHA256: `{geometry_sha}`",
        f"- Pairwise sidecar SHA256: `{pairwise_sha}`",
        "- No GT/reference/quality/outcome/active-time/holdout-effect field was projected or consumed.",
        "- `analysis_manifest.json` hashes every other output; its own hash is intentionally excluded to avoid self-reference.",
    ])
    (output_dir / "A4_PREOUTCOME_REPLAY_REPORT.md").write_text("\n".join(report) + "\n", encoding="utf-8")

    inputs = {}
    for path in (IDENTITY, GEOMETRY, SUMMARY, PAIRWISE, ALIGNMENT, RULE, CONTRACT, SPLIT):
        inputs[str(path.relative_to(ROOT))] = sha256_file(path)
    output_names = [
        "A4_REPLAY_CANDIDATE_DENOMINATOR.csv", "A4_STRICT_POOL_PREOUTCOME_STATE.csv",
        "A4_PREOUTCOME_POLICY_ACTIONS.csv", "A4_PREOUTCOME_REPLAY_SPEC.json", "INPUT_ALLOWLIST_DENYLIST.json",
        "A4_PREOUTCOME_REPLAY_REPORT.md",
    ]
    output_hashes = {name: sha256_file(output_dir / name) for name in output_names}
    manifest = {
        "schema_version": "a4_replay_preoutcome_manifest_v1",
        "generator": {"path": str(Path(__file__).relative_to(ROOT)), "sha256": generator_sha},
        "inputs": inputs, "outputs": output_hashes,
        "manifest_self_hash_excluded": True,
        "counts": {
            "identity_rows": len(identity), "primary_rows": sum(len(rows) for rows in primary_by_pool.values()),
            "pool_count": len(all_pools), "primary_k_zero_pools": sum(not rows for rows in primary_by_pool.values()),
            "primary_k_ge_3_pools": sum(len(rows) >= 3 for rows in primary_by_pool.values()),
            "formal_status": dict(status_counts), "a0_selected": sum(item["a0_selection_disposition"] == "selected" for item in pool_rows),
            "a0_unresolved": sum(item["a0_selection_disposition"] == "unresolved" for item in pool_rows),
        },
        "read_only_boundaries": spec["read_only_boundaries"],
        "input_access_trace": trace,
    }
    (output_dir / "analysis_manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return manifest


if __name__ == "__main__":
    print(json.dumps(build(), indent=2, sort_keys=True))
