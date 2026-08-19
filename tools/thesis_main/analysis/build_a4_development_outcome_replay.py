"""Development-only A4 outcome replay over the frozen strict-pool actions."""

from __future__ import annotations

import csv
import hashlib
import json
import math
import random
from collections import Counter, defaultdict
from pathlib import Path
from statistics import mean, median, stdev


ROOT = Path(__file__).resolve().parents[3]
PRE = ROOT / "analysis_results/a4_replay_preoutcome_freeze_20260817_v1"
OUT = ROOT / "analysis_results/a4_development_outcome_replay_20260817_v1"
QUALITY = ROOT / "analysis_results/c1_formal_audit_20260802_v16_final/c1_formal_audit_20260802_7fcacc5c2d6c_bf5def46_6bc67c03/c1_gt_quality_analysis.csv"
CONFLICT = ROOT / "analysis_results/reference_conflict_sensitivity_audit_20260805_v2/c1_candidate_screen/c1_gt_conflict_review_queue.csv"
SPLIT = ROOT / "analysis_results/aggregation_preflight_readiness_20260817_v1/DEVELOPMENT_HOLDOUT_SPLIT_MANIFEST.csv"

SEED = 20260817
BOOTSTRAP_REPLICATES = 5000
VARIANTS = ("A4-S", "A4-C", "A4-L")
VARIANT_ORDER = {"A4-S": 0, "A4-C": 1, "A4-L": 2}
QUALITY_FIELDS = (
    "canonical_annotation_id", "building_id", "iou_to_gt", "gt_primary_analysis_eligible",
    "structurally_valid", "worker_caused_structural_failure", "failure_attribution",
    "public_gt_structural_status", "gt_reference_resolved", "geometry_reference_status",
)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _bool(value: object) -> bool:
    return str(value).strip().lower() in {"true", "1", "yes"}


def _finite(value: object) -> bool:
    try:
        return math.isfinite(float(value))
    except (TypeError, ValueError):
        return False


def _float(value: object) -> float | None:
    return float(value) if _finite(value) else None


def _read_csv(path: Path, fields: list[str], trace: list[dict], *, development_buildings: set[str] | None = None) -> list[dict]:
    with path.open(newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        missing = [field for field in fields if field not in (reader.fieldnames or [])]
        if missing:
            raise RuntimeError(f"missing columns in {path}: {missing}")
        rows = []
        for raw in reader:
            building = str(raw.get("building_id", ""))
            if development_buildings is not None and building not in development_buildings:
                continue
            rows.append({field: raw.get(field, "") for field in fields})
    trace.append({"path": str(path.relative_to(ROOT)), "projected_columns": fields, "development_filter": sorted(development_buildings) if development_buildings is not None else None})
    return rows


def validate_development_split(rows: list[dict], candidate_buildings: set[str]) -> tuple[set[str], set[str]]:
    if len(rows) != 13 or len({row["building_scene_id"] for row in rows}) != 13:
        raise RuntimeError("split manifest must contain exactly 13 unique buildings")
    development = {str(row["building_scene_id"]) for row in rows if row["split"] == "development"}
    locked = {str(row["building_scene_id"]) for row in rows if row["split"] == "internal_holdout"}
    if len(development) != 9 or len(locked) != 4 or development & locked:
        raise RuntimeError("split manifest must contain 9 development and 4 locked buildings")
    if {str(item) for item in candidate_buildings} != development:
        raise RuntimeError("candidate pool source is not restricted to the nine development buildings")
    return development, locked


def conflict_pool_sets(state_rows: list[dict], conflict_base_tasks: set[str], public_pool_ids: set[str]) -> tuple[set[str], set[str]]:
    all_hits = {row["deployment_pool_id"] for row in state_rows if row["base_task_id"] in conflict_base_tasks}
    return all_hits, all_hits & set(public_pool_ids)


def validate_action_keyset(state_pool_ids: set[str], action_keys: list[tuple[str, str]]) -> None:
    expected = {(pool_id, variant) for pool_id in state_pool_ids for variant in ("A0", *VARIANTS)}
    actual = set(action_keys)
    if actual != expected or len(action_keys) != len(expected):
        raise RuntimeError("preoutcome action keyset is not exactly state pools x A0/S/C/L")


def validate_preoutcome_spec(spec: dict, development_building_count: int) -> None:
    if development_building_count != 9 or spec["development_replay"]["buildings"] != "9 development buildings only":
        raise RuntimeError("preoutcome development building boundary drifted")
    gates = spec["future_effect_gates_not_evaluated"]
    expected = {
        "strong_go_delta": ">=0.015", "conditional_delta": "0.011<=delta<0.015", "no_go_delta": "<0.011",
        "effect_sensitivity_only": "0.020",
        "direction_gate": "at least 6/9 buildings non-negative and at least 5/9 strictly positive",
    }
    if any(gates.get(key) != value for key, value in expected.items()):
        raise RuntimeError("preoutcome future effect gate drifted")
    selection_rule = gates.get("selection_rule", "")
    if not all(token in selection_rule for token in ("no max-observed selection", "outer LOBO only", "ties A4-S", "A4-S retained as primary safety estimate")):
        raise RuntimeError("preoutcome LOBO/primary safety selection rule drifted")
    a4s = spec["variants"].get("A4-S", "")
    if not all(token in a4s for token in ("median of four", "median cluster score", "ties support then formal medoid", "fallback A0")):
        raise RuntimeError("preoutcome A4-S action semantics drifted")


def validate_quality_building(quality_row: dict, pool_building: str) -> None:
    if str(quality_row.get("building_id", "")) != str(pool_building):
        raise RuntimeError("quality building_id does not match pool building_scene_id")


def common_pair_eligibility(a0: dict, variant: dict) -> tuple[bool, str]:
    if not a0.get("selected") or not variant.get("selected"):
        return False, "a0_or_variant_unresolved"
    if not a0.get("gt_primary_analysis_eligible") or not variant.get("gt_primary_analysis_eligible"):
        return False, "gt_primary_reference_ineligible"
    if not _finite(a0.get("iou_to_gt")) or not _finite(variant.get("iou_to_gt")):
        return False, "quality_value_missing"
    if a0.get("quality_geometry_conflict") or variant.get("quality_geometry_conflict"):
        return False, "formal_geometry_quality_structural_conflict"
    return True, "paired_public_gt_primary"


def delivery_adjusted_quality(row: dict) -> float | None:
    if _bool(row.get("structurally_valid")):
        return _float(row.get("iou_to_gt"))
    if _bool(row.get("worker_caused_structural_failure")):
        return 0.0
    return None


def classify_effect_band(delta: float) -> str:
    if delta > 0.015 or math.isclose(delta, 0.015, rel_tol=0.0, abs_tol=1e-12):
        return "strong_go"
    if delta > 0.011 or math.isclose(delta, 0.011, rel_tol=0.0, abs_tol=1e-12):
        return "conditional"
    return "no_go"


def direction_gate(building_means: list[float | None]) -> tuple[bool, str]:
    if len(building_means) != 9 or any(value is None for value in building_means):
        return False, "missing_building"
    nonnegative = sum(float(value) >= 0 for value in building_means)
    positive = sum(float(value) > 0 for value in building_means)
    if nonnegative >= 6 and positive >= 5:
        return True, "direction_gate_pass"
    return False, f"direction_gate_fail_nonnegative_{nonnegative}_positive_{positive}"


def choose_lobo_variant(train_means: dict[str, float]) -> str:
    best = max(train_means.values())
    return next(variant for variant in VARIANTS if math.isclose(train_means[variant], best, rel_tol=0.0, abs_tol=1e-12) or train_means[variant] == best)


def build_decision(a4_s_delta: float, a4_s_building_means: list[float | None], exploratory_means: dict[str, float]) -> dict:
    effect_band = classify_effect_band(a4_s_delta)
    direction_pass, direction_reason = direction_gate(a4_s_building_means)
    classification = effect_band if direction_pass else "stability_fail_no_go"
    return {
        "a4_s_classification": classification,
        "overall_decision": classification,
        "a4_s_effect_band": effect_band,
        "a4_s_direction_gate_pass": direction_pass,
        "a4_s_direction_gate_reason": direction_reason,
        "exploratory_means_do_not_override_a4_s": exploratory_means,
        "ci_or_p_value_gate_used": False,
    }


def _verify_preoutcome_manifest(trace: list[dict]) -> tuple[dict, dict]:
    manifest_path = PRE / "analysis_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    mismatches = []
    for category in ("inputs", "outputs"):
        for relative, expected in manifest[category].items():
            path = _resolve_preoutcome_path(relative)
            actual = sha256_file(path) if path.exists() else "missing"
            if actual != expected:
                mismatches.append({"category": category, "path": relative, "expected": expected, "actual": actual})
    generator = manifest["generator"]
    generator_path = ROOT / Path(generator["path"])
    generator_actual = sha256_file(generator_path) if generator_path.exists() else "missing"
    if generator_actual != generator["sha256"]:
        mismatches.append({"category": "generator", "path": generator["path"], "expected": generator["sha256"], "actual": generator_actual})
    if mismatches:
        raise RuntimeError(f"preoutcome manifest mismatch: {mismatches}")
    trace.append({"path": str(manifest_path.relative_to(ROOT)), "projected_columns": ["inputs", "outputs", "counts", "read_only_boundaries"]})
    return manifest, json.loads((PRE / "A4_PREOUTCOME_REPLAY_SPEC.json").read_text(encoding="utf-8"))


def _resolve_preoutcome_path(relative: str) -> Path:
    root_path = ROOT / Path(relative)
    return root_path if root_path.exists() else PRE / Path(relative)


def _write_csv(path: Path, fields: list[str], rows: list[dict]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def _percentile(values: list[float], probability: float) -> float | None:
    if not values:
        return None
    values = sorted(values)
    position = (len(values) - 1) * probability
    lower, upper = math.floor(position), math.ceil(position)
    if lower == upper:
        return values[lower]
    return values[lower] + (values[upper] - values[lower]) * (position - lower)


def _bootstrap(rows: list[dict], seed: int = SEED, replicates: int = BOOTSTRAP_REPLICATES) -> tuple[float | None, float | None]:
    groups = defaultdict(list)
    for row in rows:
        if _finite(row.get("delta_iou_to_gt")):
            groups[row["building_scene_id"]].append(float(row["delta_iou_to_gt"]))
    if not groups:
        return None, None
    buildings = sorted(groups)
    rng = random.Random(seed)
    means = []
    for _ in range(replicates):
        sampled = [buildings[rng.randrange(len(buildings))] for _ in buildings]
        values = [value for building in sampled for value in groups[building]]
        means.append(mean(values))
    return _percentile(means, 0.025), _percentile(means, 0.975)


def _metric_summary(rows: list[dict], variant: str, regime: str, building: str | None) -> dict:
    eligibility_key = "public_gt_primary_paired_evaluable" if regime == "public_gt_primary" else "strict_paired_evaluable"
    selected = [row for row in rows if row["variant"] == variant and (building is None or row["building_scene_id"] == building) and row[eligibility_key] == "True"]
    deltas = [float(row["delta_iou_to_gt"]) for row in selected if _finite(row["delta_iou_to_gt"])]
    delivery = [float(row["delta_delivery_adjusted_quality"]) for row in selected if _finite(row["delta_delivery_adjusted_quality"])]
    changed = [row for row in selected if row["changed_action"].lower() == "true"]
    changed_deltas = [float(row["delta_iou_to_gt"]) for row in changed if _finite(row["delta_iou_to_gt"])]
    building_means = [] if building is not None else [
        mean([float(row["delta_iou_to_gt"]) for row in selected if row["building_scene_id"] == item]) if any(row["building_scene_id"] == item for row in selected) else None
        for item in sorted({row["building_scene_id"] for row in rows})
    ]
    ci_low, ci_high = _bootstrap(selected) if building is None else (None, None)
    return {
        "variant": variant,
        "reference_regime": regime,
        "aggregation_level": "overall" if building is None else "building",
        "building_scene_id": "" if building is None else building,
        "n": len(deltas),
        "building_count": len({row["building_scene_id"] for row in selected}),
        "task_weighted_mean_delta": mean(deltas) if deltas else "",
        "median_delta": median(deltas) if deltas else "",
        "sd_delta": stdev(deltas) if len(deltas) > 1 else "",
        "delivery_adjusted_mean_delta": mean(delivery) if delivery else "",
        "delivery_adjusted_n": len(delivery),
        "changed_action_count": len(changed),
        "changed_only_n": len(changed_deltas),
        "changed_only_mean": mean(changed_deltas) if changed_deltas else "",
        "direction": "not_evaluable" if building is None or not deltas else ("positive" if mean(deltas) > 0 else "nonnegative" if mean(deltas) == 0 else "negative"),
        "effect_band": classify_effect_band(mean(deltas)) if building is None and deltas else "",
        "bootstrap_ci_low": ci_low if building is None else "",
        "bootstrap_ci_high": ci_high if building is None else "",
        "bootstrap_seed": SEED if building is None else "",
        "bootstrap_replicates": BOOTSTRAP_REPLICATES if building is None else "",
        "bootstrap_cluster_unit": "building" if building is None else "",
    }


def _quality_record(row: dict, formal_row: dict | None, pool_building: str) -> dict:
    if formal_row is None:
        return {"present": False, "quality_reason": "quality_join_missing"}
    validate_quality_building(row, pool_building)
    record = dict(row)
    record["present"] = True
    record["selected"] = True
    record["gt_primary_analysis_eligible"] = _bool(row["gt_primary_analysis_eligible"])
    record["structurally_valid"] = _bool(row["structurally_valid"])
    record["worker_caused_structural_failure"] = _bool(row["worker_caused_structural_failure"])
    record["quality_geometry_conflict"] = record["structurally_valid"] != _bool(formal_row["normalization_valid"])
    record["quality_reason"] = "formal_geometry_quality_structural_conflict" if record["quality_geometry_conflict"] else ""
    record["delivery_adjusted_quality"] = delivery_adjusted_quality(record)
    return record


def build(output_dir: Path = OUT) -> dict:
    trace = []
    pre_manifest, pre_spec = _verify_preoutcome_manifest(trace)
    split_rows = _read_csv(SPLIT, ["building_scene_id", "split"], trace)
    state = _read_csv(PRE / "A4_STRICT_POOL_PREOUTCOME_STATE.csv", [
        "deployment_pool_id", "stage", "round_id", "condition", "base_task_id", "task_id", "project_id",
        "ls_runtime_task_id", "building_scene_id", "primary_candidate_k", "a0_selection_disposition",
        "a0_prime_medoid_candidate_annotation_id", "a0_unresolved_reason", "cluster_membership_json",
    ], trace)
    candidate_buildings = {row["building_scene_id"] for row in state}
    development_buildings, locked_buildings = validate_development_split(split_rows, candidate_buildings)
    validate_preoutcome_spec(pre_spec, len(development_buildings))
    if candidate_buildings & locked_buildings:
        raise RuntimeError("locked building appears in preoutcome pool state")
    actions = _read_csv(PRE / "A4_PREOUTCOME_POLICY_ACTIONS.csv", [
        "deployment_pool_id", "variant", "action_disposition", "selected_candidate_annotation_id",
        "selected_worker_id", "disagreement_with_a0",
    ], trace)
    action_map = {}
    for row in actions:
        key = (row["deployment_pool_id"], row["variant"])
        if key in action_map:
            raise RuntimeError(f"duplicate preoutcome action {key}")
        action_map[key] = row
    state_pool_ids = {row["deployment_pool_id"] for row in state}
    validate_action_keyset(state_pool_ids, list(action_map))
    if len(state) != 139 or len(action_map) != 556:
        raise RuntimeError("preoutcome state/action coverage is not 139 pools x 4 actions")
    if any(sum(row["action_disposition"] == "selected" for row in actions if row["variant"] == variant) != 67 for variant in ("A0", *VARIANTS)):
        raise RuntimeError("preoutcome selected count is not 67 for every action")

    denom_rows = _read_csv(PRE / "A4_REPLAY_CANDIDATE_DENOMINATOR.csv", ["candidate_annotation_id", "normalization_valid"], trace)
    formal_by_id = {row["candidate_annotation_id"]: row for row in denom_rows}
    if len(formal_by_id) != len(denom_rows):
        raise RuntimeError("formal geometry denominator candidate id is not unique")

    quality_identity_rows = _read_csv(QUALITY, ["canonical_annotation_id", "building_id"], trace)
    quality_identity_ids = [row["canonical_annotation_id"] for row in quality_identity_rows]
    if len(quality_identity_rows) != 780 or len(set(quality_identity_ids)) != len(quality_identity_ids):
        raise RuntimeError("quality canonical_annotation_id identity table is not the expected unique 780-row source")
    quality_rows = _read_csv(QUALITY, list(QUALITY_FIELDS), trace, development_buildings=development_buildings)
    quality_index = {}
    for row in quality_rows:
        key = row["canonical_annotation_id"]
        if key in quality_index:
            raise RuntimeError(f"quality canonical_annotation_id duplicated: {key}")
        quality_index[key] = row
    if len(quality_index) == 0:
        raise RuntimeError("no development quality rows consumed")

    conflict_rows = _read_csv(CONFLICT, ["base_task_id", "candidate_only"], trace)
    conflict_base_tasks = {row["base_task_id"] for row in conflict_rows if _bool(row["candidate_only"])}
    pool_base_tasks = {row["base_task_id"] for row in state}
    all_conflict_pool_ids, _ = conflict_pool_sets(state, conflict_base_tasks, set())
    if len(all_conflict_pool_ids) != 30:
        raise RuntimeError(f"all conflict pool hit count changed: {len(all_conflict_pool_ids)}")

    pool_rows = {row["deployment_pool_id"]: row for row in state}
    result_rows = []
    public_denominators = {}
    strict_denominators = {}
    for pool_id, pool in sorted(pool_rows.items()):
        a0_action = action_map[(pool_id, "A0")]
        a0_id = a0_action["selected_candidate_annotation_id"]
        a0_quality = _quality_record(quality_index[a0_id], formal_by_id.get(a0_id), pool["building_scene_id"]) if a0_action["action_disposition"] == "selected" and a0_id in quality_index else {"selected": False, "present": False, "quality_reason": "a0_unresolved_or_quality_missing"}
        for variant in VARIANTS:
            variant_action = action_map[(pool_id, variant)]
            variant_id = variant_action["selected_candidate_annotation_id"]
            variant_quality = _quality_record(quality_index[variant_id], formal_by_id.get(variant_id), pool["building_scene_id"]) if variant_action["action_disposition"] == "selected" and variant_id in quality_index else {"selected": False, "present": False, "quality_reason": "variant_unresolved_or_quality_missing"}
            public_ok, public_reason = common_pair_eligibility(a0_quality, variant_quality)
            strict_ok = public_ok and pool_id not in all_conflict_pool_ids
            strict_reason = "paired_strict_conflict_free" if strict_ok else "strict_conflict_exclusion" if public_ok else public_reason
            public_denominators.setdefault(variant, set()).add(pool_id if public_ok else "")
            strict_denominators.setdefault(variant, set()).add(pool_id if strict_ok else "")
            a0_delivery = a0_quality.get("delivery_adjusted_quality")
            variant_delivery = variant_quality.get("delivery_adjusted_quality")
            delta_delivery = variant_delivery - a0_delivery if public_ok and a0_delivery is not None and variant_delivery is not None else ""
            exclusion_reason = "" if public_ok else public_reason
            result_rows.append({
                "deployment_pool_id": pool_id, "building_scene_id": pool["building_scene_id"], "stage": pool["stage"],
                "round_id": pool["round_id"], "condition": pool["condition"], "base_task_id": pool["base_task_id"],
                "task_id": pool["task_id"], "project_id": pool["project_id"], "ls_runtime_task_id": pool["ls_runtime_task_id"],
                "variant": variant, "a0_action_disposition": a0_action["action_disposition"], "variant_action_disposition": variant_action["action_disposition"],
                "a0_candidate_annotation_id": a0_id, "variant_candidate_annotation_id": variant_id,
                "changed_action": str(a0_id != variant_id and public_ok).lower(),
                "a0_gt_primary_analysis_eligible": str(a0_quality.get("gt_primary_analysis_eligible", False)).lower(),
                "variant_gt_primary_analysis_eligible": str(variant_quality.get("gt_primary_analysis_eligible", False)).lower(),
                "a0_structurally_valid": str(a0_quality.get("structurally_valid", False)).lower(),
                "variant_structurally_valid": str(variant_quality.get("structurally_valid", False)).lower(),
                "a0_quality_geometry_conflict": str(a0_quality.get("quality_geometry_conflict", False)).lower(),
                "variant_quality_geometry_conflict": str(variant_quality.get("quality_geometry_conflict", False)).lower(),
                "a0_iou_to_gt": a0_quality.get("iou_to_gt", ""), "variant_iou_to_gt": variant_quality.get("iou_to_gt", ""),
                "a0_delivery_adjusted_quality": a0_delivery if a0_delivery is not None else "",
                "variant_delivery_adjusted_quality": variant_delivery if variant_delivery is not None else "",
                "delta_iou_to_gt": (float(variant_quality["iou_to_gt"]) - float(a0_quality["iou_to_gt"])) if public_ok else "",
                "delta_delivery_adjusted_quality": delta_delivery,
                "public_gt_primary_paired_evaluable": str(public_ok), "public_reference_reason": public_reason,
                "all_conflict_pool_hit": str(pool_id in all_conflict_pool_ids),
                "paired_conflict_exclusion": str(public_ok and pool_id in all_conflict_pool_ids),
                "strict_conflict_exclusion": str(public_ok and pool_id in all_conflict_pool_ids), "strict_paired_evaluable": str(strict_ok),
                "strict_reference_reason": strict_reason, "operational_corrected_reference_status": "not_evaluable/source_absent",
                "paired_evaluable": str(public_ok), "exclusion_reason": exclusion_reason,
            })
    for variant in VARIANTS:
        if public_denominators[variant] != public_denominators["A4-S"] or strict_denominators[variant] != strict_denominators["A4-S"]:
            raise RuntimeError("variant denominators are not identical within each reference regime")
    public_evaluable_pool_ids = public_denominators["A4-S"] - {""}
    _, paired_conflict_exclusion_ids = conflict_pool_sets(state, conflict_base_tasks, public_evaluable_pool_ids)
    if len(paired_conflict_exclusion_ids) != 12:
        raise RuntimeError(f"paired conflict exclusion count changed: {len(paired_conflict_exclusion_ids)}")
    public_n = len(public_evaluable_pool_ids)
    strict_n = len(strict_denominators["A4-S"] - {""})
    if public_n != 58 or strict_n != 46:
        raise RuntimeError(f"paired denominator invariant failed: public={public_n}, strict={strict_n}")

    summary_rows = []
    all_buildings = sorted(development_buildings)
    for regime in ("public_gt_primary", "strict_conflict_exclusion"):
        for variant in VARIANTS:
            summary_rows.append(_metric_summary(result_rows, variant, regime, None))
            summary_rows.extend(_metric_summary(result_rows, variant, regime, building) for building in all_buildings)

    lobo_rows = []
    for regime in ("public_gt_primary", "strict_conflict_exclusion"):
        eligible_key = "public_gt_primary_paired_evaluable" if regime == "public_gt_primary" else "strict_paired_evaluable"
        regime_rows = [row for row in result_rows if row[eligible_key] == "True"]
        for outer in all_buildings:
            train = [row for row in regime_rows if row["building_scene_id"] != outer]
            test = [row for row in regime_rows if row["building_scene_id"] == outer]
            train_means = {variant: mean(float(row["delta_iou_to_gt"]) for row in train if row["variant"] == variant) if any(row["variant"] == variant for row in train) else None for variant in VARIANTS}
            if any(value is None for value in train_means.values()) or not test:
                lobo_rows.append({"reference_regime": regime, "outer_building": outer, "status": "not_evaluable", "reason": "incomplete_train_or_test_support", "train_a4_s_mean": train_means["A4-S"] if train_means["A4-S"] is not None else "", "train_a4_c_mean": train_means["A4-C"] if train_means["A4-C"] is not None else "", "train_a4_l_mean": train_means["A4-L"] if train_means["A4-L"] is not None else "", "chosen_variant": "", "test_n": 0, "test_mean_delta": "", "test_building_in_train": "False"})
                continue
            chosen = choose_lobo_variant(train_means)
            test_values = [float(row["delta_iou_to_gt"]) for row in test if row["variant"] == chosen]
            lobo_rows.append({"reference_regime": regime, "outer_building": outer, "status": "evaluated", "reason": "", "train_a4_s_mean": train_means["A4-S"], "train_a4_c_mean": train_means["A4-C"], "train_a4_l_mean": train_means["A4-L"], "chosen_variant": chosen, "test_n": len(test_values), "test_mean_delta": mean(test_values), "test_building_in_train": "False"})
        for scope in ("outer_test_pooled", "outer_test_equal_building"):
            tests = [row for row in lobo_rows if row["reference_regime"] == regime and row["status"] == "evaluated" and row["outer_building"] not in ("outer_test_pooled", "outer_test_equal_building")]
            values = [float(row["test_mean_delta"]) for row in tests]
            total_n = sum(int(row["test_n"]) for row in tests)
            pooled_delta = sum(float(row["test_mean_delta"]) * int(row["test_n"]) for row in tests) / total_n if total_n else ""
            equal_building_delta = mean(values) if values else ""
            lobo_rows.append({"reference_regime": regime, "outer_building": scope, "status": "evaluated" if len(tests) == 9 else "not_evaluable", "reason": "" if len(tests) == 9 else "incomplete_outer_support", "train_a4_s_mean": "", "train_a4_c_mean": "", "train_a4_l_mean": "", "chosen_variant": "", "test_n": total_n, "test_mean_delta": pooled_delta if scope == "outer_test_pooled" else equal_building_delta, "test_building_in_train": "False"})

    primary_summary = next(row for row in summary_rows if row["variant"] == "A4-S" and row["reference_regime"] == "public_gt_primary" and row["aggregation_level"] == "overall")
    building_means = [next(row for row in summary_rows if row["variant"] == "A4-S" and row["reference_regime"] == "public_gt_primary" and row["building_scene_id"] == building)["task_weighted_mean_delta"] for building in all_buildings]
    exploratory_means = {variant: next(row for row in summary_rows if row["variant"] == variant and row["reference_regime"] == "public_gt_primary" and row["aggregation_level"] == "overall")["task_weighted_mean_delta"] for variant in ("A4-C", "A4-L")}
    decision = build_decision(float(primary_summary["task_weighted_mean_delta"]), [float(value) if value != "" else None for value in building_means], exploratory_means)
    decision.update({"seed": SEED, "bootstrap_replicates": BOOTSTRAP_REPLICATES, "primary_reference_regime": "public_gt_primary", "primary_variant": "A4-S", "public_n": public_n, "strict_n": strict_n, "conflict_pool_hits_all": len(all_conflict_pool_ids), "paired_conflict_exclusions": len(paired_conflict_exclusion_ids), "development_building_count": len(all_buildings), "locked_building_count": len(locked_buildings), "development_descriptive_not_confirmatory": True})

    output_dir.mkdir(parents=True, exist_ok=True)
    result_fields = list(result_rows[0].keys())
    summary_fields = list(summary_rows[0].keys())
    lobo_fields = list(lobo_rows[0].keys())
    _write_csv(output_dir / "A4_DEVELOPMENT_PAIRED_RESULTS.csv", result_fields, result_rows)
    _write_csv(output_dir / "A4_DEVELOPMENT_VARIANT_SUMMARY.csv", summary_fields, summary_rows)
    _write_csv(output_dir / "A4_DEVELOPMENT_LOBO_SELECTOR.csv", lobo_fields, lobo_rows)
    (output_dir / "A4_DEVELOPMENT_DECISION.json").write_text(json.dumps(decision, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    report = [
        "# A4 development outcome replay",
        "",
        f"Status: `{decision['overall_decision']}` for the frozen A4-S primary safety estimate; development descriptive only.",
        "",
        f"- Development buildings: {len(all_buildings)}; locked buildings consumed: 0.",
        f"- Public GT-primary paired denominator: {public_n}; strict-conflict sensitivity denominator: {strict_n}.",
        f"- Candidate-only conflict pool hits across all pools: {len(all_conflict_pool_ids)}; paired public exclusions: {len(paired_conflict_exclusion_ids)}.",
        f"- A4-S mean delta: {primary_summary['task_weighted_mean_delta']}; effect band: {primary_summary['effect_band']}; direction: {decision['a4_s_direction_gate_reason']}.",
        f"- A4-C/L are fixed exploratory variants and cannot upgrade A4-S: C={exploratory_means['A4-C']}, L={exploratory_means['A4-L']}.",
        f"- Bootstrap: seed={SEED}, replicates={BOOTSTRAP_REPLICATES}, cluster_unit=building; no annotation-level p-value used.",
        "- Operational corrected reference is `not_evaluable/source_absent`; public GT was not modified.",
        "- Four locked buildings were excluded at split validation and their quality values were not consumed.",
        "",
        "## Reproducibility",
        "",
        "- Pre-outcome manifest inputs and outputs were independently SHA-verified before outcome joins.",
        "- No action was recomputed; all A0/A4 action IDs came from the frozen action CSV.",
    ]
    (output_dir / "A4_DEVELOPMENT_OUTCOME_REPLAY_REPORT.md").write_text("\n".join(report) + "\n", encoding="utf-8")

    input_paths = {str((PRE / "analysis_manifest.json").relative_to(ROOT)): sha256_file(PRE / "analysis_manifest.json")}
    prior_manifest = pre_manifest
    for category in ("inputs", "outputs"):
        for relative in prior_manifest[category]:
            path = _resolve_preoutcome_path(relative)
            input_paths[str(path.relative_to(ROOT))] = sha256_file(path)
    for path in (QUALITY, CONFLICT, SPLIT):
        input_paths[str(path.relative_to(ROOT))] = sha256_file(path)
    outputs = ["A4_DEVELOPMENT_PAIRED_RESULTS.csv", "A4_DEVELOPMENT_VARIANT_SUMMARY.csv", "A4_DEVELOPMENT_LOBO_SELECTOR.csv", "A4_DEVELOPMENT_DECISION.json", "A4_DEVELOPMENT_OUTCOME_REPLAY_REPORT.md"]
    output_hashes = {name: sha256_file(output_dir / name) for name in outputs}
    manifest = {
        "schema_version": "a4_development_outcome_replay_manifest_v1",
        "generator": {"path": str(Path(__file__).relative_to(ROOT)), "sha256": sha256_file(Path(__file__))},
        "inputs": input_paths, "outputs": output_hashes, "manifest_self_hash_excluded": True,
        "counts": {"development_buildings": len(all_buildings), "locked_buildings": len(locked_buildings), "pools": len(state), "result_rows": len(result_rows), "public_n": public_n, "strict_n": strict_n, "conflict_pool_hits_all": len(all_conflict_pool_ids), "paired_conflict_exclusions": len(paired_conflict_exclusion_ids), "quality_rows_consumed": len(quality_rows)},
        "read_only_boundaries": {"active_time_read": False, "t1_v1_outcome_read": False, "locked_building_effect_read": False, "old_selector_outcome_read": False, "actions_recomputed": False, "new_experiment_started": False},
        "input_access_trace": trace,
    }
    (output_dir / "analysis_manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return manifest


if __name__ == "__main__":
    print(json.dumps(build(), indent=2, sort_keys=True))
