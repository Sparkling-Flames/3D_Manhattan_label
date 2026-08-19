"""Run the diagnostic post-Block2 opportunity analyses from the QA-approved pack."""

from __future__ import annotations

import csv
import hashlib
import json
import math
import random
import statistics
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

import networkx as nx
import numpy as np
import pandas as pd
from scipy.stats import binomtest, norm, t


ROOT = Path(__file__).resolve().parents[3]
PACK = ROOT / "analysis_results" / "post_block2_analysis_pack_20260817_v3"
OUT = ROOT / "analysis_results" / "post_block2_opportunity_analysis_20260817_v1"
AGG = OUT / "POST_BLOCK2_AGGREGATION_OPPORTUNITY_AUDIT"
ROUTING = OUT / "POST_BLOCK2_MATCHED_ROUTING_FEASIBILITY"
POWER = OUT / "POST_BLOCK2_CLUSTERED_POWER"
DECISION = OUT / "POST_BLOCK2_ESTIMAND_DECISION"
SEED = 20260817
BOOTSTRAPS = 1000
ROLE = "development_cross_fitted_retrospective_audit_opportunity_estimate"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def rel(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def write_csv(path: Path, rows: list[dict[str, Any]], fields: list[str] | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if fields is None:
        fields = []
        for row in rows:
            for field in row:
                if field not in fields:
                    fields.append(field)
    fields = fields or ["status"]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def f(value: Any) -> float | None:
    try:
        result = float(str(value))
        return result if math.isfinite(result) else None
    except (TypeError, ValueError):
        return None


def truthy(value: Any) -> bool:
    return str(value).strip().lower() in {"1", "true", "yes"}


def corner_count(row: dict[str, Any]) -> int:
    explicit = f(row.get("n_corners"))
    if explicit is not None:
        points = int(explicit)
        return points // 2 if points > 0 and points % 2 == 0 else 0
    for field in ("corners_px", "ordered_geometry", "corners"):
        value = row.get(field)
        if isinstance(value, str):
            try:
                value = json.loads(value)
            except json.JSONDecodeError:
                value = []
        if isinstance(value, list) and value:
            return len(value) // 2 if len(value) % 2 == 0 else 0
    return 0


def find_c1(name: str) -> Path:
    matches = list((ROOT / "analysis_results" / "c1_formal_audit_20260802_v16_final").rglob(name))
    if len(matches) != 1:
        raise ValueError(f"expected one frozen C1 {name}, found {len(matches)}")
    return matches[0]


def verify_pack() -> dict[str, Any]:
    provenance = json.loads((PACK / "POST_BLOCK2_DATA_PROVENANCE.json").read_text(encoding="utf-8"))
    if provenance.get("status") != "GO" or not provenance.get("prompt_2_entry_allowed"):
        raise ValueError("post-Block2 pack is not QA-approved for Prompt 2")
    manifest = json.loads((PACK / "ARTIFACT_HASH_MANIFEST.json").read_text(encoding="utf-8"))
    mismatches = []
    for name, expected in manifest["artifacts"].items():
        path = PACK / name
        if not path.exists() or sha256(path) != expected:
            mismatches.append(name)
    if mismatches:
        raise ValueError(f"pack manifest mismatch: {mismatches}")
    required = {
        "worker_profile_uncertainty_inputs.csv", "empirical_variance_inputs.json",
        "post_block2_submission_master.csv", "post_block2_task_context_master.csv",
        "post_block2_worker_profile_master.csv", "aggregation_candidate_geometries.csv",
        "routing_worker_pair_candidates.csv",
    }
    missing = sorted(name for name in required if not (PACK / name).exists())
    if missing:
        raise ValueError(f"missing required pack inputs: {missing}")
    return {"manifest_sha256": sha256(PACK / "ARTIFACT_HASH_MANIFEST.json"), "artifact_count": len(manifest["artifacts"])}


def task_adjusted_training_quality(rows: list[dict[str, str]]) -> dict[str, float]:
    eligible = [row for row in rows if f(row.get("iou_to_gt")) is not None and truthy(row.get("gt_primary_analysis_eligible"))]
    if not eligible:
        return {}
    frame = pd.DataFrame({"worker": [row["worker_id"] for row in eligible], "task": [row["base_task_id"] for row in eligible], "quality": [float(row["iou_to_gt"]) for row in eligible]})
    workers = sorted(frame.worker.unique())
    tasks = sorted(frame.task.unique())
    x = np.column_stack([
        np.ones(len(frame)),
        *[(frame.worker == worker).astype(float).to_numpy() for worker in workers[1:]],
        *[(frame.task == task).astype(float).to_numpy() for task in tasks[1:]],
    ])
    beta = np.linalg.lstsq(x, frame.quality.to_numpy(), rcond=None)[0]
    worker_effect = {workers[0]: 0.0, **{worker: float(beta[index]) for index, worker in enumerate(workers[1:], start=1)}}
    task_effect_start = len(workers)
    task_effect = {tasks[0]: 0.0, **{task: float(beta[task_effect_start + index]) for index, task in enumerate(tasks[1:])}}
    mean_task = statistics.mean(task_effect.values())
    return {worker: float(beta[0] + effect + mean_task) for worker, effect in worker_effect.items()}


def medoid_key(worker: str, members: list[str], pairs: dict[tuple[str, str], tuple[float, float]], geometry_sha: str, annotation_id: str) -> tuple[Any, ...] | None:
    scores = [pairs[tuple(sorted((worker, other)))] for other in members if other != worker and tuple(sorted((worker, other))) in pairs]
    if len(scores) != max(0, len(members) - 1):
        return None
    scalar = [min(item) for item in scores] or [1.0]
    return (-statistics.median(scalar), -statistics.mean(scalar), geometry_sha, annotation_id, worker)


def select_medoid(members: list[str], pairs: dict[tuple[str, str], tuple[float, float]], geometry_sha: dict[str, str], annotation_ids: dict[str, str], weights: dict[str, float] | None = None) -> str | None:
    ranked = []
    for worker in members:
        key = medoid_key(worker, members, pairs, geometry_sha.get(worker, ""), annotation_ids.get(worker, ""))
        if key is None:
            continue
        if weights is None:
            ranked.append((key, worker))
        else:
            weighted = []
            for other in members:
                if other == worker:
                    continue
                score = pairs.get(tuple(sorted((worker, other))))
                if score is None:
                    weighted = []
                    break
                weighted.append((statistics.mean(score), max(0.0, weights.get(other, 0.0))))
            if not weighted:
                continue
            denominator = sum(weight for _, weight in weighted) or len(weighted)
            value = sum(score * (weight or 1.0) for score, weight in weighted) / denominator
            ranked.append(((-value, *key[2:]), worker))
    return min(ranked)[1] if ranked else None


def aggregation_audit() -> dict[str, Any]:
    crowd_path = find_c1("geometry_task_crowd_structure_C1.csv")
    pair_path = find_c1("geometry_pairwise_similarity_C1.csv")
    quality_path = find_c1("c1_gt_quality_analysis.csv")
    geometry_path = find_c1("c1_canonical_geometry.jsonl")
    crowd = read_csv(crowd_path)
    quality = read_csv(quality_path)
    pairs_raw = read_csv(pair_path)
    geometry_rows = [json.loads(line) for line in geometry_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    quality_by_task: dict[tuple[str, str], dict[str, dict[str, str]]] = defaultdict(dict)
    for row in quality:
        quality_by_task[(row["base_task_id"], row.get("condition", ""))][row["worker_id"]] = row
    geometry_by_task: dict[tuple[str, str], dict[str, dict[str, Any]]] = defaultdict(dict)
    for row in geometry_rows:
        geometry_by_task[(str(row["base_task_id"]), str(row.get("condition", "")))][str(row["worker_id"])] = row
    pairs_by_task: dict[tuple[str, str], dict[tuple[str, str], tuple[float, float]]] = defaultdict(dict)
    for row in pairs_raw:
        qb, qw = f(row.get("q_boundary")), f(row.get("q_wallwall"))
        if truthy(row.get("metric_compatible")) and qb is not None and qw is not None:
            pairs_by_task[(row["base_task_id"], row.get("condition", ""))][tuple(sorted((row["worker_id_left"], row["worker_id_right"])))] = (qb, qw)

    known_conflicts = set()
    queue_path = ROOT / "analysis_results" / "reference_conflict_sensitivity_audit_20260805_v2" / "c1_candidate_screen" / "c1_gt_conflict_review_queue.csv"
    if queue_path.exists():
        known_conflicts = {row["base_task_id"] for row in read_csv(queue_path) if truthy(row.get("candidate_only"))}
    buildings = sorted({row.get("building_id", "") for row in crowd if row.get("building_id")})
    results: list[dict[str, Any]] = []
    minority: list[dict[str, Any]] = []
    variable: list[dict[str, Any]] = []
    a0_checks = []
    for building in buildings:
        train_quality = [row for row in quality if row.get("building_id") != building]
        qgt = task_adjusted_training_quality(train_quality)
        for task in [row for row in crowd if row.get("building_id") == building]:
            task_id = task["base_task_id"]
            condition = task.get("condition", "")
            context_key = (task_id, condition)
            candidates = quality_by_task.get(context_key, {})
            geometries = geometry_by_task.get(context_key, {})
            pair_scores = pairs_by_task.get(context_key, {})
            clusters = json.loads(task.get("cluster_membership_json") or "[]")
            id_to_worker = {str(row.get("canonical_annotation_id") or row.get("annotation_id")): worker for worker, row in geometries.items()}
            worker_clusters = [[id_to_worker[item] for item in cluster if item in id_to_worker] for cluster in clusters]
            worker_clusters = [cluster for cluster in worker_clusters if cluster]
            largest = worker_clusters[0] if worker_clusters else []
            geometry_sha = {worker: str(row.get("geometry_hash") or row.get("geometry_sha256") or "") for worker, row in geometries.items()}
            annotation_ids = {worker: str(row.get("canonical_annotation_id") or row.get("annotation_id") or "") for worker, row in geometries.items()}
            recomputed_a0 = select_medoid(largest, pair_scores, geometry_sha, annotation_ids)
            frozen_a0 = task.get("largest_cluster_medoid_worker_id", "")
            score_keys = {worker: medoid_key(worker, largest, pair_scores, geometry_sha.get(worker, ""), annotation_ids.get(worker, "")) for worker in largest}
            score_keys = {worker: key for worker, key in score_keys.items() if key is not None}
            best_score = min((key[:2] for key in score_keys.values()), default=None)
            tied_best = {worker for worker, key in score_keys.items() if key[:2] == best_score}
            a0_ok = (not frozen_a0 and not tied_best) or (frozen_a0 in tied_best)
            a0_checks.append(a0_ok)
            corners = {}
            for worker, geometry in geometries.items():
                repaired = f(candidates.get(worker, {}).get("repaired_point_count"))
                corners[worker] = int(repaired) // 2 if repaired and int(repaired) % 2 == 0 else corner_count(geometry)
            all_workers = sorted(candidates)
            same_topology = len({corners.get(worker) for worker in all_workers}) <= 1

            selections: dict[str, tuple[str | None, str]] = {"A0_current_largest_cluster_medoid": (frozen_a0 or None, "estimated" if frozen_a0 else "not_evaluable")}
            a1 = select_medoid(all_workers, pair_scores, geometry_sha, annotation_ids)
            a2 = select_medoid(all_workers, pair_scores, geometry_sha, annotation_ids, qgt)
            selections["A1_global_medoid_over_all_legal_submissions"] = (a1, "estimated" if a1 else "not_evaluable_incomplete_cross_topology_similarity")
            selections["A2_cross_fitted_worker_quality_weighted_medoid"] = (a2, "estimated" if a2 else "not_evaluable_incomplete_cross_topology_similarity")
            cluster_scores = []
            for cluster in worker_clusters:
                supported = [qgt[w] for w in cluster if w in qgt]
                if supported:
                    cluster_scores.append((-statistics.mean(supported), -len(cluster), tuple(sorted(cluster)), cluster))
            a3_cluster = min(cluster_scores)[-1] if cluster_scores else []
            selections["A3_cluster_support_plus_worker_quality_selector"] = (select_medoid(a3_cluster, pair_scores, geometry_sha, annotation_ids), "estimated" if a3_cluster else "not_evaluable_training_support")
            selections["A4_image_evidence_weighted_cluster_selector"] = (None, "source_absent_no_frozen_preoutcome_image_evidence")
            topology_choices = []
            for topology_corner_count in sorted(set(corners.values())):
                group = [worker for worker in all_workers if corners.get(worker) == topology_corner_count]
                supported = [qgt[w] for w in group if w in qgt]
                chosen = select_medoid(group, pair_scores, geometry_sha, annotation_ids)
                if chosen and supported:
                    topology_choices.append((-statistics.mean(supported), -len(group), topology_corner_count, chosen))
            a5 = min(topology_choices)[-1] if topology_choices else None
            selections["A5_topology_preserving_variable_corner_selector"] = (a5, "estimated" if a5 else "not_evaluable_training_support")
            evaluable = [(float(row["iou_to_gt"]), worker) for worker, row in candidates.items() if f(row.get("iou_to_gt")) is not None and truthy(row.get("gt_primary_analysis_eligible"))]
            oracle = max(evaluable)[1] if evaluable else None
            selections["A_oracle_evaluator_only"] = (oracle, "evaluator_only" if oracle else "not_evaluable")
            for method, (worker, status) in selections.items():
                qrow = candidates.get(worker or "", {})
                score = f(qrow.get("iou_to_gt"))
                structurally_valid = truthy(qrow.get("structurally_valid")) if qrow else False
                results.append({
                    "analysis_role": ROLE, "outer_fold": f"leave_building_out:{building}", "building_id": building, "base_task_id": task_id, "condition": condition,
                    "method": method, "selected_worker_id": worker or "", "status": status if score is not None or method == "A4_image_evidence_weighted_cluster_selector" else "not_evaluable_reference",
                    "public_gt_quality": score if score is not None else "", "delivery_adjusted_quality": (score if structurally_valid else 0.0) if score is not None else "",
                    "structurally_valid": structurally_valid if qrow else "", "corner_count": corners.get(worker or "", ""), "a0_reconstruction_match": a0_ok,
                    "severe_geometric_error_status": "not_identifiable_no_frozen_severe_threshold", "topology_error_status": "not_identifiable_no_frozen_reference_topology_field",
                    "training_buildings_excluded_test_building": True, "inner_tuning": "none_fixed_lexicographic_rules", "gt_used_for_selection": method == "A_oracle_evaluator_only",
                })
            a0_score = f(candidates.get(frozen_a0, {}).get("iou_to_gt"))
            nonlargest_workers = [worker for cluster in worker_clusters[1:] for worker in cluster]
            best_nonlargest = max((float(candidates[w]["iou_to_gt"]), w) for w in nonlargest_workers if w in candidates and f(candidates[w].get("iou_to_gt")) is not None) if any(w in candidates and f(candidates[w].get("iou_to_gt")) is not None for w in nonlargest_workers) else None
            delta = best_nonlargest[0] - a0_score if best_nonlargest and a0_score is not None else None
            minority.append({
                "analysis_role": ROLE, "base_task_id": task_id, "condition": condition, "building_id": building, "reference_regime": "public_gt", "status": "estimated" if delta is not None else "not_evaluable",
                "largest_cluster_medoid_quality": a0_score if a0_score is not None else "", "best_nonlargest_cluster_quality": best_nonlargest[0] if best_nonlargest else "", "best_nonlargest_worker": best_nonlargest[1] if best_nonlargest else "",
                "delta_minor_minus_major": delta if delta is not None else "", "delta_ge_0_02": delta is not None and delta >= .02, "delta_ge_0_05": delta is not None and delta >= .05, "delta_ge_0_10": delta is not None and delta >= .10,
                "crowd_structure": task.get("task_crowd_structure_status", ""), "corner_count_set": ";".join(map(str, sorted(set(corners.values())))), "strict_conflict_candidate": task_id in known_conflicts,
            })
            variable.append({
                "analysis_role": ROLE, "base_task_id": task_id, "condition": condition, "building_id": building, "corner_count_set": ";".join(map(str, sorted(set(corners.values())))),
                "comparison": " vs ".join(map(str, sorted(set(corners.values())))), "mixed_topology": not same_topology, "A0_handling": "frozen_complete_link_partition_then_largest_cluster_medoid",
                "A1_A2_cross_topology_status": "not_evaluable" if not same_topology else "same_topology", "A5_status": selections["A5_topology_preserving_variable_corner_selector"][1],
                "A5_selected_corner_count": corners.get(a5 or "", ""), "coordinate_averaging_used": False,
            })

    write_csv(AGG / "cross_fitted_selector_results.csv", results)
    write_csv(AGG / "minority_mode_recovery.csv", minority)
    write_csv(AGG / "variable_corner_count_audit.csv", variable)
    ref_rows = []
    for regime in ("public_gt", "operational_corrected_reference", "strict_conflict_unavailable_exclusion"):
        for row in minority:
            status = row["status"]
            included = status == "estimated"
            if regime == "operational_corrected_reference":
                status, included = "not_evaluable_operational_reference_not_materialized", False
            elif regime.startswith("strict") and row["strict_conflict_candidate"]:
                status, included = "excluded_known_reference_conflict", False
            ref_rows.append({**row, "reference_regime": regime, "status": status, "included": included})
    write_csv(AGG / "reference_sensitivity.csv", ref_rows)
    loo = []
    for (fold, method), group in pd.DataFrame(results).groupby(["outer_fold", "method"]):
        scores = pd.to_numeric(group.public_gt_quality, errors="coerce").dropna()
        loo.append({"analysis_role": ROLE, "outer_fold": fold, "method": method, "n_tasks": len(group), "n_evaluable": len(scores), "mean_public_gt_quality": scores.mean() if len(scores) else "", "coverage": len(scores) / len(group) if len(group) else "", "status": "estimated" if len(scores) else "not_evaluable"})
    write_csv(AGG / "leave_one_building_out.csv", loo)
    write_csv(AGG / "aggregation_ablation.csv", [
        {"ablation": "R_peer_truth_prior", "status": "not_run_by_design", "reason": "R_peer rewards conformity and Prompt 2 says it must not be the primary truth prior"},
        {"ablation": "A4_image_evidence", "status": "source_absent", "reason": "no frozen pre-outcome image-evidence feature matrix bound to the pack"},
        {"ablation": "operational_reference", "status": "not_evaluable", "reason": "no frozen corrected operational reference geometry was materialized"},
    ])
    frame = pd.DataFrame(results)
    pivot = frame.pivot_table(index=["base_task_id", "condition", "building_id"], columns="method", values="public_gt_quality", aggfunc="first")
    delta = (pd.to_numeric(pivot["A2_cross_fitted_worker_quality_weighted_medoid"], errors="coerce") - pd.to_numeric(pivot["A0_current_largest_cluster_medoid"], errors="coerce")).dropna() if "A2_cross_fitted_worker_quality_weighted_medoid" in pivot and "A0_current_largest_cluster_medoid" in pivot else pd.Series(dtype=float)
    power_inputs = {"analysis_role": ROLE, "paired_method": "A2_minus_A0", "n_paired_tasks": int(len(delta)), "mean_delta": float(delta.mean()) if len(delta) else None, "variance_delta": float(delta.var(ddof=1)) if len(delta) > 1 else None, "building_count": int(pivot.reset_index().building_id.nunique()), "a0_reconstruction": {"tasks_checked": len(a0_checks), "matches": sum(a0_checks), "all_match": all(a0_checks)}, "historical_commit_object_available": False, "frozen_sidecars_used": [rel(crowd_path), rel(pair_path), rel(geometry_path)]}
    write_json(AGG / "aggregation_power_inputs.json", power_inputs)
    threshold_rows = []
    evaluable_minor = [row for row in minority if row["status"] == "estimated"]
    for threshold in (.02, .05, .10):
        count = sum(float(row["delta_minor_minus_major"]) >= threshold for row in evaluable_minor)
        ci = binomtest(count, len(evaluable_minor)).proportion_ci() if evaluable_minor else None
        threshold_rows.append({"threshold": threshold, "count": count, "n": len(evaluable_minor), "proportion": count / len(evaluable_minor) if evaluable_minor else "", "exact_ci_lower": ci.low if ci else "", "exact_ci_upper": ci.high if ci else ""})
    report = ["# Aggregation Opportunity Audit", "", f"分析角色：`{ROLE}`。不是 prospective confirmation。", "", f"A0 冻结重建检查：{sum(a0_checks)}/{len(a0_checks)} task contexts 匹配。", "", "## Minority-better exact intervals", ""]
    report += [f"- Δ≥{row['threshold']:.2f}: {row['count']}/{row['n']}，exact CI {row['exact_ci_lower']}–{row['exact_ci_upper']}" for row in threshold_rows]
    report += ["", "A4 因冻结的 pre-outcome image evidence 不存在而不可评估；operational/corrected reference 未物化，因此仅报告 public GT 与 strict exclusion。严重错误阈值未冻结，不新造阈值。"]
    (AGG / "AGGREGATION_AUDIT_REPORT.md").write_text("\n".join(report) + "\n", encoding="utf-8")
    return {"results": results, "power_inputs": power_inputs, "a0_all_match": all(a0_checks)}


def se_from_interval(row: dict[str, str], low: str, high: str) -> float | None:
    lo, hi = f(row.get(low)), f(row.get(high))
    return None if lo is None or hi is None else max((hi - lo) / 3.92, 1e-9)


def pair_probabilities(a: dict[str, str], b: dict[str, str], dq: float, dr: float, floor: float) -> tuple[float, float, float]:
    qa, qb = f(a.get("Q_GT_EB")), f(b.get("Q_GT_EB"))
    ra, rb = f(a.get("R_peer_stable")), f(b.get("R_peer_stable"))
    fa, fb = f(a.get("F_struct_EB")), f(b.get("F_struct_EB"))
    if None in (qa, qb, ra, rb, fa, fb):
        return 0.0, 0.0, 0.0
    sqa, sqb = se_from_interval(a, "Q_GT_EB_CI_lower", "Q_GT_EB_CI_upper"), se_from_interval(b, "Q_GT_EB_CI_lower", "Q_GT_EB_CI_upper")
    sra, srb = se_from_interval(a, "R_peer_CI_lower", "R_peer_CI_upper"), se_from_interval(b, "R_peer_CI_lower", "R_peer_CI_upper")
    sfa, sfb = se_from_interval(a, "F_struct_interval_lower", "F_struct_interval_upper"), se_from_interval(b, "F_struct_interval_lower", "F_struct_interval_upper")
    if None in (sqa, sqb, sra, srb, sfa, sfb):
        return 0.0, 0.0, 0.0
    qsd = math.hypot(sqa, sqb)
    rsd = math.hypot(sra, srb)
    p_q = norm.cdf((dq - (qa - qb)) / qsd) - norm.cdf((-dq - (qa - qb)) / qsd)
    p_f = norm.cdf((floor - fa) / sfa) * norm.cdf((floor - fb) / sfb)
    p_r = norm.sf((dr - abs(ra - rb)) / rsd)
    return float(p_q), float(p_f), float(p_r)


def routing_audit() -> dict[str, Any]:
    profiles = [row for row in read_csv(PACK / "post_block2_worker_profile_master.csv") if row.get("final_pooled_profile_status") == "formal_ready" and row.get("Q_GT_profile_status") == "estimated"]
    profile = {row["worker_id"]: row for row in profiles}
    grids = [(dq, dr, floor, prob) for dq in (.02, .04, .06) for dr in (.005, .01, .02) for floor in (.05, .10) for prob in (.50, .75, .90)]
    edges = []
    solutions = []
    workers = sorted(profile)
    for dq, dr, floor, threshold in grids:
        graph = nx.Graph()
        graph.add_nodes_from(workers)
        for i, left in enumerate(workers):
            for right in workers[i + 1:]:
                p_q, p_f, p_r = pair_probabilities(profile[left], profile[right], dq, dr, floor)
                qdiff = abs(float(profile[left]["Q_GT_EB"]) - float(profile[right]["Q_GT_EB"]))
                fdiff = abs(float(profile[left]["F_struct_EB"]) - float(profile[right]["F_struct_EB"]))
                rdiff = abs(float(profile[left]["R_peer_stable"]) - float(profile[right]["R_peer_stable"]))
                task_support_diff = abs(float(profile[left].get("task_support") or 0) - float(profile[right].get("task_support") or 0))
                building_support_diff = abs(float(profile[left].get("building_support") or 0) - float(profile[right].get("building_support") or 0))
                active_time_diff = abs(float(profile[left].get("T_active_task_adjusted") or 0) - float(profile[right].get("T_active_task_adjusted") or 0))
                eligible = min(p_q, p_f, p_r) >= threshold
                row = {"analysis_role": ROLE, "delta_Q": dq, "delta_R": dr, "safety_floor": floor, "probability_threshold": threshold, "worker_id_left": left, "worker_id_right": right, "p_quality_caliper": p_q, "p_structural_safe": p_f, "p_peer_contrast": p_r, "Q_imbalance": qdiff, "F_imbalance": fdiff, "R_contrast": rdiff, "formal_profile_support_compatible": True, "task_support_imbalance": task_support_diff, "building_support_imbalance": building_support_diff, "temporal_support_compatibility": "same_terminal_calibration_snapshot", "expected_workload_imbalance": active_time_diff, "eligible_edge": eligible}
                edges.append(row)
                if eligible:
                    graph.add_edge(left, right, weight=1_000_000 * rdiff - 10_000 * qdiff - 1_000 * fdiff - 10 * task_support_diff - 10 * building_support_diff - active_time_diff)
        matching = nx.max_weight_matching(graph, maxcardinality=True, weight="weight")
        solutions.append({"analysis_role": ROLE, "delta_Q": dq, "delta_R": dr, "safety_floor": floor, "probability_threshold": threshold, "construction": "1_to_1_maximum_matching", "matched_pairs": len(matching), "matched_workers": 2 * len(matching), "eligible_edges": graph.number_of_edges(), "pairs_json": json.dumps(sorted([sorted(edge) for edge in matching])), "status": "estimated"})
        solutions.append({"analysis_role": ROLE, "delta_Q": dq, "delta_R": dr, "safety_floor": floor, "probability_threshold": threshold, "construction": "1_to_m_or_pool", "matched_pairs": "", "matched_workers": len({node for edge in graph.edges for node in edge}), "eligible_edges": graph.number_of_edges(), "pairs_json": "", "status": "graph_reported_no_unique_counterfactual_matched_set"})
    write_csv(ROUTING / "eligible_pair_edges.csv", edges)
    write_csv(ROUTING / "matching_solution_by_caliper.csv", solutions)
    central = (.04, .01, .10, .75)
    central_edges = [row for row in edges if (row["delta_Q"], row["delta_R"], row["safety_floor"], row["probability_threshold"]) == central and row["eligible_edge"]]
    rng = np.random.default_rng(SEED)
    inclusion: Counter[tuple[str, str]] = Counter()
    roles: Counter[str] = Counter()
    cardinality = []
    for _ in range(BOOTSTRAPS):
        graph = nx.Graph()
        graph.add_nodes_from(workers)
        for row in central_edges:
            left, right = row["worker_id_left"], row["worker_id_right"]
            q_noise = rng.normal(0, math.hypot(se_from_interval(profile[left], "Q_GT_EB_CI_lower", "Q_GT_EB_CI_upper") or 0, se_from_interval(profile[right], "Q_GT_EB_CI_lower", "Q_GT_EB_CI_upper") or 0))
            r_noise = rng.normal(0, math.hypot(se_from_interval(profile[left], "R_peer_CI_lower", "R_peer_CI_upper") or 0, se_from_interval(profile[right], "R_peer_CI_lower", "R_peer_CI_upper") or 0))
            if abs(row["Q_imbalance"] + q_noise) <= central[0] and row["R_contrast"] + r_noise >= central[1]:
                graph.add_edge(left, right, weight=1_000_000 * max(0.0, row["R_contrast"] + r_noise) - 10_000 * abs(row["Q_imbalance"] + q_noise) - 1_000 * row["F_imbalance"])
        matching = nx.max_weight_matching(graph, maxcardinality=True, weight="weight")
        cardinality.append(len(matching))
        for edge in matching:
            pair = tuple(sorted(edge))
            inclusion[pair] += 1
            high = max(edge, key=lambda worker: float(profile[worker]["R_peer_stable"]))
            low = min(edge, key=lambda worker: float(profile[worker]["R_peer_stable"]))
            roles.update([f"high_peer:{high}", f"control:{low}"])
    stability = [{"record_type": "cardinality", "item": str(value), "count": count, "probability": count / BOOTSTRAPS, "bootstrap_replicates": BOOTSTRAPS, "seed": SEED} for value, count in sorted(Counter(cardinality).items())]
    all_pairs = [(left, right) for index, left in enumerate(workers) for right in workers[index + 1:]]
    stability += [{"record_type": "pair_inclusion", "item": f"{a}|{b}", "count": inclusion[(a, b)], "probability": inclusion[(a, b)] / BOOTSTRAPS, "bootstrap_replicates": BOOTSTRAPS, "seed": SEED} for a, b in all_pairs]
    stability += [{"record_type": role + "_role", "item": worker, "count": roles[f"{role}:{worker}"], "probability": roles[f"{role}:{worker}"] / BOOTSTRAPS, "bootstrap_replicates": BOOTSTRAPS, "seed": SEED} for role in ("high_peer", "control") for worker in workers]
    stability += [
        {"record_type": "leave_one_building_out_profile_sensitivity", "item": "all", "count": "", "probability": "", "bootstrap_replicates": 0, "seed": SEED, "status": "not_evaluable_profile_covariance_not_available_by_building"},
        {"record_type": "leave_one_task_family_out_profile_sensitivity", "item": "all", "count": "", "probability": "", "bootstrap_replicates": 0, "seed": SEED, "status": "not_evaluable_task_family_profile_snapshot_source_absent"},
    ]
    write_csv(ROUTING / "matching_bootstrap_stability.csv", stability)
    best = max((row for row in solutions if row["construction"] == "1_to_1_maximum_matching"), key=lambda row: (row["matched_workers"], -row["delta_Q"], row["delta_R"]))
    matched = {worker for pair in json.loads(best["pairs_json"]) for worker in pair}
    best_edges = [row for row in edges if row["eligible_edge"] and row["delta_Q"] == best["delta_Q"] and row["delta_R"] == best["delta_R"] and row["safety_floor"] == best["safety_floor"] and row["probability_threshold"] == best["probability_threshold"]]
    component_graph = nx.Graph((row["worker_id_left"], row["worker_id_right"]) for row in best_edges)
    matched_sets = [{"construction": "1_to_1", "status": "estimated_graph_only", **best}]
    matched_sets += [{"analysis_role": ROLE, "construction": "1_to_m_candidate_component", "status": "retrospective_graph_feasibility_not_effect", "set_id": index, "worker_ids": ";".join(sorted(component)), "set_size": len(component), "selection_basis": "maximum-cardinality sensitivity grid; not recommended caliper"} for index, component in enumerate(nx.connected_components(component_graph), start=1) if len(component) > 1]
    matched_sets.append({"construction": "high_peer_pool_vs_matched_control_pool", "status": "not_evaluable_no_historical_randomized_counterfactual", "analysis_role": ROLE})
    write_csv(ROUTING / "matched_set_results.csv", matched_sets)
    write_csv(ROUTING / "unmatched_workers.csv", [{"worker_id": worker, "matched_in_selected_sensitivity_solution": worker in matched, "reason": "" if worker in matched else "no_edge_or_displaced_by_lexicographic_matching"} for worker in workers])
    write_csv(ROUTING / "caliper_sensitivity.csv", solutions)
    write_csv(ROUTING / "routing_replay_if_valid.csv", [
        {"estimand": "fixed_budget_third_worker", "status": "not_evaluable", "reason": "historical data do not contain randomized high-peer versus quality-matched next-worker counterfactuals", "cost_claim": "not_identifiable"},
        {"estimand": "single_branch_continuation", "status": "not_evaluable", "reason": "shared continuation counterfactual cannot be reconstructed", "cost_claim": "not_identifiable"},
    ])
    (ROUTING / "ROUTING_FEASIBILITY_REPORT.md").write_text(
        "# Matched Routing Feasibility\n\n"
        f"分析角色：`{ROLE}`。对 caliper/probability grid 做了完整 graph 与 maximum matching sensitivity；中央网格使用 {BOOTSTRAPS} 次固定 seed profile perturbation。\n\n"
        "历史数据没有随机化的 next-worker counterfactual，因此不报告 routing effect，也不声称成本可识别。LOBO/leave-family profile covariance 未冻结，相关稳定性逐项标为 not_evaluable。\n",
        encoding="utf-8",
    )
    return {"best": best, "cardinality": cardinality, "workers": len(workers)}


def normal_power(effect: float, se: float, alpha: float = .05) -> float:
    if se <= 0:
        return 1.0
    z = abs(effect) / se
    critical = norm.ppf(1 - alpha / 2)
    return float(norm.sf(critical - z) + norm.cdf(-critical - z))


def clustered_simulation_power(effect: float, variance: float, n_rows: int, n_clusters: int, icc: float, seed: int) -> float:
    rng = np.random.default_rng(seed)
    n_clusters = max(2, min(n_clusters, n_rows))
    assignment = np.arange(n_rows) % n_clusters
    cluster_sd = math.sqrt(max(variance * icc, 0.0))
    residual_sd = math.sqrt(max(variance * (1 - icc), 1e-12))
    cluster_effect = rng.normal(0, cluster_sd, size=(BOOTSTRAPS, n_clusters))
    residual = rng.normal(0, residual_sd, size=(BOOTSTRAPS, n_rows))
    values = effect + cluster_effect[:, assignment] + residual
    cluster_means = np.column_stack([values[:, assignment == index].mean(axis=1) for index in range(n_clusters)])
    estimates = cluster_means.mean(axis=1)
    standard_errors = cluster_means.std(axis=1, ddof=1) / math.sqrt(n_clusters)
    critical = 1.96 if n_clusters > 30 else float(t.ppf(.975, n_clusters - 1))
    return float(np.mean(np.abs(estimates / np.maximum(standard_errors, 1e-12)) > critical))


def power_audit(aggregation: dict[str, Any], routing: dict[str, Any]) -> dict[str, Any]:
    rows = pd.DataFrame(aggregation["results"])
    pivot = rows.pivot_table(index=["base_task_id", "condition", "building_id"], columns="method", values="public_gt_quality", aggfunc="first")
    base = pivot.get("A0_current_largest_cluster_medoid")
    alt = pivot.get("A2_cross_fitted_worker_quality_weighted_medoid")
    deltas = (pd.to_numeric(alt, errors="coerce") - pd.to_numeric(base, errors="coerce")).dropna() if base is not None and alt is not None else pd.Series(dtype=float)
    central_var = float(deltas.var(ddof=1)) if len(deltas) > 1 else .0025
    scenarios = {"optimistic": central_var * .5, "central": central_var, "pessimistic": central_var * 2}
    building_counts = [5, 7, 9, 12]
    write_csv(POWER / "building_cluster_scenarios.csv", [{"assumption_set_id": name, "paired_delta_variance": var, "building_count": building, "variance_source": "A2_minus_A0_cross_fitted_task_deltas"} for name, var in scenarios.items() for building in building_counts])
    agg_grid = []
    for name, variance in scenarios.items():
        for n_tasks in (40, 50, 60, 70, 80, 100):
            for effect in (.005, .010, .015, .020, .025, .030):
                n_buildings = min(12, max(5, round(n_tasks / 8)))
                sim_seed = SEED + n_tasks * 1000 + int(effect * 100000) + list(scenarios).index(name)
                sim_power = clustered_simulation_power(effect, variance, n_tasks, n_buildings, .05, sim_seed)
                agg_grid.append({"assumption_set_id": name, "variance_source": "empirical_A2_minus_A0_paired_delta", "effect_size": effect, "n_tasks": n_tasks, "n_workers": 5, "n_pairs": "", "n_buildings": n_buildings, "analysis_model": "paired_task_delta_building_cluster_simulation", "power": sim_power, "simulation_replicates": BOOTSTRAPS, "seed": sim_seed})
    write_csv(POWER / "aggregation_power_grid.csv", agg_grid)
    required = []
    for name, variance in scenarios.items():
        for effect in (.005, .010, .015, .020, .025, .030):
            for target in (.8, .9):
                found = next((n for n in range(20, 501) if normal_power(effect, math.sqrt(variance * (1 + (n / max(5, round(n / 8)) - 1) * .05) / n)) >= target), None)
                required.append({"record_type": "required_N", "assumption_set_id": name, "effect_size": effect, "target_power": target, "required_N": found or ">500", "variance_source": "empirical_A2_minus_A0_paired_delta"})
        for n_tasks in (40, 50, 60, 70, 80, 100):
            n_buildings = min(12, max(5, round(n_tasks / 8)))
            se = math.sqrt(variance * (1 + (n_tasks / n_buildings - 1) * .05) / n_tasks)
            required.append({"record_type": "MDE", "assumption_set_id": name, "n_tasks": n_tasks, "n_buildings": n_buildings, "MDE_80": (norm.ppf(.975) + norm.ppf(.8)) * se, "MDE_90": (norm.ppf(.975) + norm.ppf(.9)) * se, "variance_source": "empirical_A2_minus_A0_paired_delta"})
    write_csv(POWER / "aggregation_required_N.csv", required)

    fixed, generalized = [], []
    pair_var = statistics.variance(routing["cardinality"]) if len(set(routing["cardinality"])) > 1 else 1.0
    for n_disagreement in (50, 80, 100, 120, 150, 200):
        for n_pairs in (5, 7, 8, 9, 10, 12):
            for effect in (.010, .015, .020, .025, .030, .040):
                residual = max(central_var, .0004)
                fixed_seed = SEED + n_disagreement * 1000 + n_pairs * 10 + int(effect * 100000)
                generalized_seed = fixed_seed + 1
                common = {"assumption_set_id": "central_design_input", "variance_source": "aggregation_delta_variance_plus_matching_cardinality_sensitivity", "effect_size": effect, "n_tasks": n_disagreement, "n_workers": 2 * n_pairs, "n_pairs": n_pairs, "n_buildings": max(5, round(n_disagreement / 10))}
                fixed.append({**common, "analysis_model": "fixed_pair_effects_clustered_simulation", "power": clustered_simulation_power(effect, residual, n_disagreement, n_pairs, .05, fixed_seed), "simulation_replicates": BOOTSTRAPS, "seed": fixed_seed})
                generalized.append({**common, "analysis_model": "random_pair_contrast_worker_generalized_clustered_simulation", "power": clustered_simulation_power(effect, residual + max(pair_var, .25) * .0001, n_disagreement, n_pairs, .20, generalized_seed), "simulation_replicates": BOOTSTRAPS, "seed": generalized_seed})
    write_csv(POWER / "routing_fixed_roster_power.csv", fixed)
    write_csv(POWER / "routing_worker_generalized_power.csv", generalized)
    routing_required = []
    for model, table in (("fixed_roster", fixed), ("worker_generalized", generalized)):
        for effect in (.010, .015, .020, .025, .030, .040):
            for pairs in (5, 7, 8, 9, 10, 12):
                subset = [row for row in table if row["effect_size"] == effect and row["n_pairs"] == pairs and row["power"] >= .8]
                routing_required.append({"record_type": "required_N", "analysis_model": model, "effect_size": effect, "n_pairs": pairs, "target_power": .8, "required_N": min((row["n_tasks"] for row in subset), default=">200")})
        for pairs in (5, 7, 8, 9, 10, 12):
            for n_disagreement in (50, 80, 100, 120, 150, 200):
                base_se = math.sqrt(max(central_var, .0004) / n_disagreement)
                multiplier = 1.0 if model == "fixed_roster" else math.sqrt(1 + .20 * (n_disagreement / pairs - 1))
                se = base_se * multiplier
                routing_required.append({"record_type": "MDE", "analysis_model": model, "n_pairs": pairs, "n_tasks": n_disagreement, "MDE_80": (norm.ppf(.975) + norm.ppf(.8)) * se, "MDE_90": (norm.ppf(.975) + norm.ppf(.9)) * se})
    write_csv(POWER / "routing_required_N.csv", routing_required)
    write_csv(POWER / "variance_sensitivity.csv", [{"assumption_set_id": name, "variance": value, "source": "empirical paired cross-fitted aggregation delta", "status": "estimated"} for name, value in scenarios.items()] + [{"assumption_set_id": "routing_counterfactual", "variance": "", "source": "historical routing counterfactual", "status": "not_identifiable"}])
    (POWER / "POWER_AUDIT_REPORT.md").write_text(
        "# Clustered Power Audit\n\n"
        f"所有表均为设计功效，不是 observed effect confirmation。Aggregation 使用 cross-fitted paired task delta 的经验方差并施加 building cluster design effect；routing 同时报告 fixed roster 与 worker-generalized 层级。固定 seed={SEED}，标称 repetitions={BOOTSTRAPS}。\n\n"
        "历史 routing 没有可识别成本反事实，因此 fixed-budget 的 cost claim 保持 not_identifiable。\n",
        encoding="utf-8",
    )
    return {"central_variance": central_var, "aggregation_grid_rows": len(agg_grid), "routing_grid_rows": len(fixed) + len(generalized)}


def decision_and_handoff(pack_audit: dict[str, Any], aggregation: dict[str, Any], routing: dict[str, Any], power: dict[str, Any]) -> None:
    routes = [
        {"route": "Route A: Aggregation-first", "scientific_question": "Does topology-preserving minority-aware aggregation improve paired task-level delivery quality versus frozen A0?", "primary_estimand": "paired task-level delivery-adjusted quality difference", "unit_of_analysis": "task/context", "causal_or_predictive_claim": "prospective paired algorithm comparison required", "required_new_data": "new task/building-disjoint 5-worker submission sets", "estimated_submission_count": "5 per task", "required_workers": "5 per task", "required_buildings": "multi-building", "MDE": "see aggregation_required_N.csv", "power central case": "see aggregation_power_grid.csv", "main_failure_mode": "A4 image evidence absent and operational reference unavailable", "main_novelty_risk": "selector complexity without independent confirmation", "dependence_on_worker_profile": "A2/A3/A5", "dependence_on_reference_quality": "high", "transferability": "conditional", "engineering_burden": "medium", "time_risk": "medium", "evidence_level": "CONDITIONAL", "reason": "A0 is auditable but some requested selectors/reference regimes are not evaluable", "load_bearing_evidence": "cross_fitted_selector_results.csv", "main_uncertainty": "independent prospective effect", "what_final_reviewer_must_decide": "whether remaining source gaps justify new confirmation data"},
        {"route": "Route B: Continuation routing", "scientific_question": "Can quality-matched peer contrast improve continuation outcomes?", "primary_estimand": "fixed-budget quality-only or full-continuation quality/cost; not both", "unit_of_analysis": "randomized disagreement task within matched roster", "causal_or_predictive_claim": "requires prospective randomization", "required_new_data": "randomized next-worker routing outcomes", "estimated_submission_count": "see routing_required_N.csv", "required_workers": "5-12 independent pairs/sets", "required_buildings": "multi-building", "MDE": "see routing_required_N.csv", "power central case": "see routing power grids", "main_failure_mode": "historical counterfactual absent", "main_novelty_risk": "pair identity instability", "dependence_on_worker_profile": "high", "dependence_on_reference_quality": "medium", "transferability": "fixed roster stronger than generalized", "engineering_burden": "high", "time_risk": "high", "evidence_level": "CONDITIONAL", "reason": "matching feasibility is auditable but effect and cost are not identifiable", "load_bearing_evidence": "matching_solution_by_caliper.csv", "main_uncertainty": "prospective routing effect", "what_final_reviewer_must_decide": "fixed_budget_quality_only versus full_continuation design"},
        {"route": "Route C: Measurement + T1 only", "scientific_question": "Characterize three-axis measurement, disagreement, multimodality and identifiability boundaries", "primary_estimand": "descriptive/predictive Calibration measurements plus frozen T1 estimand", "unit_of_analysis": "worker/task as contracted", "causal_or_predictive_claim": "no new V1 causal claim", "required_new_data": "none for Calibration report; T1 follows its own contract", "estimated_submission_count": "not set here", "required_workers": "existing roster", "required_buildings": "existing support", "MDE": "not_applicable", "power central case": "not_applicable", "main_failure_mode": "limited methodological novelty", "main_novelty_risk": "measurement-only contribution", "dependence_on_worker_profile": "descriptive", "dependence_on_reference_quality": "reported sensitivity", "transferability": "bounded", "engineering_burden": "low", "time_risk": "low", "evidence_level": "GO_CANDIDATE", "reason": "does not require inventing unavailable counterfactuals", "load_bearing_evidence": "final Calibration profile and QA-approved pack", "main_uncertainty": "final narrative value", "what_final_reviewer_must_decide": "whether to retain only the contracted measurement/T1 scope"},
    ]
    write_csv(DECISION / "route_comparison.csv", routes)
    write_json(DECISION / "aggregation_go_no_go.json", {"status": "CONDITIONAL", "analysis_role": ROLE, "reason": routes[0]["reason"], "not_final_mainline_decision": True})
    write_json(DECISION / "routing_go_no_go.json", {"status": "CONDITIONAL", "analysis_role": ROLE, "reason": routes[1]["reason"], "not_final_mainline_decision": True})
    write_json(DECISION / "cost_claim_decision.json", {"fixed_budget_third_worker": "cost_claim_not_identifiable", "single_branch_continuation": "requires_prospective_randomization", "final_decision": "not_made"})
    write_json(DECISION / "recommended_main_experiment_candidates.json", {"candidates": [{"route": row["route"], "evidence_level": row["evidence_level"]} for row in routes], "selection": "reserved_for_independent_final_review", "significance_optimization_used": False})
    (DECISION / "ESTIMAND_DECISION_REPORT.md").write_text(
        "# Estimand Decision Matrix\n\n本报告只给候选证据等级，不决定最终主线。Route A/B 均因关键不可识别项保持 CONDITIONAL；Route C 是不扩张现有因果主张的 GO_CANDIDATE。不得把该矩阵称为最终实验合同。\n",
        encoding="utf-8",
    )
    handoff = f"""# POST-BLOCK2 FINAL REVIEW HANDOFF

## 数据版本

- pack：`{rel(PACK)}`
- pack manifest SHA-256：`{pack_audit['manifest_sha256']}`
- analysis role：`{ROLE}`

## 四组分析

- Aggregation：冻结 A0 重建检查为 `{aggregation['a0_all_match']}`；A4 因 pre-outcome image evidence source absent 不可评估。
- Routing：完成 caliper/probability graph、maximum matching 与 {BOOTSTRAPS} 次 profile perturbation；历史 routing effect/cost counterfactual 不可识别。
- Clustered power：aggregation 与 routing fixed/generalized 设计网格已生成；不是 observed confirmation。
- Estimand：只输出 GO_CANDIDATE/CONDITIONAL 矩阵，未决定最终主线。

## 可用于设计但不能用于确认性主张

所有 cross-fitted selector、minority、matching 与 power 结果均为 retrospective development/opportunity evidence。A_oracle 仅为 evaluator-only bound。没有读取 T1/V1 outcome。

## Strongest evidence / counter-evidence

- Aggregation strongest evidence：task/building-disjoint paired selector表与 frozen A0 audit。
- Aggregation strongest counter-evidence：A4 与 corrected operational reference 不可识别，历史源码 commit object 本地不存在。
- Routing strongest evidence：全 sensitivity grid 的可匹配基数与 uncertainty perturbation。
- Routing strongest counter-evidence：没有随机化 next-worker counterfactual；LOBO/task-family profile covariance source absent。

## 新数据量

见 `POST_BLOCK2_CLUSTERED_POWER/aggregation_required_N.csv` 与 `routing_required_N.csv`。这些数值依赖明确的 optimistic/central/pessimistic 假设，不是招募决定。

## 当前不能下结论

不能确认 aggregation effect、routing effect、routing cost saving、operational-reference robustness，也不能由本线程冻结最终实验路线。

## 工件

- `POST_BLOCK2_AGGREGATION_OPPORTUNITY_AUDIT/`
- `POST_BLOCK2_MATCHED_ROUTING_FEASIBILITY/`
- `POST_BLOCK2_CLUSTERED_POWER/`
- `POST_BLOCK2_ESTIMAND_DECISION/`
"""
    (OUT / "POST_BLOCK2_FINAL_REVIEW_HANDOFF.md").write_text(handoff, encoding="utf-8")


def manifest(pack_audit: dict[str, Any]) -> None:
    artifacts = {rel(path): sha256(path) for path in sorted(OUT.rglob("*")) if path.is_file() and path.name != "analysis_manifest.json"}
    write_json(OUT / "analysis_manifest.json", {"schema_version": "post_block2_opportunity_analysis_manifest_v1", "analysis_role": ROLE, "scientific_confirmation": False, "policy_freeze": False, "block3_generated": False, "seed": SEED, "bootstrap_replicates": BOOTSTRAPS, "input_pack_manifest_sha256": pack_audit["manifest_sha256"], "artifacts": artifacts})


def main() -> int:
    for path in (AGG, ROUTING, POWER, DECISION):
        path.mkdir(parents=True, exist_ok=True)
    pack_audit = verify_pack()
    aggregation = aggregation_audit()
    if not aggregation["a0_all_match"]:
        raise ValueError("frozen A0 reconstruction failed; Prompt 2 requires stopping")
    routing = routing_audit()
    power = power_audit(aggregation, routing)
    decision_and_handoff(pack_audit, aggregation, routing, power)
    manifest(pack_audit)
    print(json.dumps({"output_dir": rel(OUT), "a0_reconstruction": aggregation["a0_all_match"], "bootstrap_replicates": BOOTSTRAPS, "manifest_sha256": sha256(OUT / "analysis_manifest.json")}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
