"""M-Anchor.4.1.1 staged, footprint-only micro-compensation shadow probe."""

from __future__ import annotations

import copy
import hashlib
import itertools
import json
import sys
from pathlib import Path
from typing import Any, Mapping, Sequence

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tools.paper_a_manhattan.run_local_3d_projection_review import run_local_review
from tools.paper_a_manhattan.run_m_anchor_1_3741 import (
    ANCHOR_SIDECAR_PATH, SAFETY, _anchor_audit, _anchor_constraints, _by_source,
    _load, _load_anchor_sidecar, _sha, _write_text_lf,
)
from tools.paper_a_manhattan.run_m_anchor_3_footprint_solver import (
    M1_AUDIT_PATH, M2_VERDICT_PATH, _geometry, _local_topology_metrics,
    _per_wall_residual_delta,
)
from tools.paper_a_manhattan.segment_aware_manhattan_refit import VERIFIED_ORDER_SOURCE_IDS

M4_ROOT = Path("analysis_results/paper_a_manhattan/m_anchor/task218_ann3741_m_anchor_4")
FEEDBACK_PATH = M4_ROOT / "m_anchor_4_human_feedback_20260709.json"
CONSTRAINTS_PATH = M4_ROOT / "m_anchor_4_1_1_staged_constraints.json"
M41_AUDIT_PATH = Path("analysis_results/paper_a_manhattan/m_anchor/task218_ann3741_m_anchor_4_1/m_anchor_4_1_footprint_shadow_probe_audit.json")
OUT_DIR = Path("analysis_results/paper_a_manhattan/m_anchor/task218_ann3741_m_anchor_4_1_1")
REVIEW_OUT_DIR = Path("analysis_results/paper_a_manhattan/hypothesis_local_review/task218_ann3741_m_anchor_4_1_1")
DEFAULT_IMAGE_ROOT = Path("data/mp3d_layout/img_v")
REVIEW_LIMIT = 5
LOCAL_MAX_WORSENING_TOLERANCE_DEG = 0.05
RESIDUAL_IMPROVEMENT_TOLERANCE_DEG = 0.05
MIN_WALL_LENGTH = 0.15
MICRO_PAIRS = (1, 2, 3, 5, 7, 8)
DIRECTIONAL = {4: "left", 9: "left", 10: "right"}
LOCKED = {6, 11, 12}


def _local_server_root(out_dir: Path) -> Path | None:
    try:
        out_dir.resolve().relative_to(REPO_ROOT.resolve())
    except ValueError:
        return None
    return REPO_ROOT


def _validate_constraints(value: Mapping[str, Any], feedback: Mapping[str, Any]) -> None:
    if value.get("schema_version") != "m_anchor_4_1_1_staged_constraints_v1":
        raise ValueError("unsupported staged constraints schema")
    if value.get("numeric_range_status") != "human_approved" or value.get("expansion_policy") != "fail_closed_staged_escalation":
        raise ValueError("staged numeric authorization missing")
    if value.get("case_name") != "task218_ann3741" or value.get("source_annotation_id") != 3741 or value.get("coordinate_space") != "ls_percent":
        raise ValueError("sidecar identity mismatch")
    if value.get("derived_from_feedback") != FEEDBACK_PATH.name:
        raise ValueError("sidecar feedback provenance mismatch")
    if value.get("allowed_variables") != ["x", "bottom_y"] or "top_y" not in value.get("forbidden_variables", []):
        raise ValueError("sidecar variable permission mismatch")
    caps = (value.get("preferred_micro_cap"), value.get("intermediate_micro_cap"), value.get("maximum_micro_cap"))
    if caps != (0.15, 0.30, 0.50):
        raise ValueError("invalid staged caps")
    for stage, cap in zip(("A", "B", "C"), caps):
        row = value.get("stage_candidate_deltas", {}).get(stage, {})
        if float(row.get("min_delta", 1)) > float(row.get("max_delta", 0)):
            raise ValueError("min_delta exceeds max_delta")
        if any(abs(float(delta)) > float(cap) for delta in row.get("candidate_deltas", [])):
            raise ValueError("candidate_deltas exceed stage cap")
        if any(not float(row["min_delta"]) <= float(delta) <= float(row["max_delta"]) for delta in row.get("candidate_deltas", [])):
            raise ValueError("candidate_deltas outside declared interval")
    config = value.get("search_config", {})
    budgets = config.get("stage_evaluation_budget", {})
    if set(budgets) != {"A", "B", "C"} or any(int(budgets[stage]) <= 0 for stage in budgets):
        raise ValueError("invalid stage evaluation budget")
    if int(config.get("max_raw_evaluations", 0)) < sum(int(budgets[stage]) for stage in budgets):
        raise ValueError("max raw evaluation cap is below staged budget")
    if any(int(config.get(key, 0)) <= 0 for key in ("core_beam", "one_action_beam", "two_actions_per_beam")):
        raise ValueError("invalid beam configuration")
    directional_pairs = set(map(int, value.get("directional_pairs", {})))
    micro_pairs = set(value.get("micro_adjustment_pairs", []))
    locked_pairs = set(value.get("locked_source_pair_ids", []))
    if directional_pairs & micro_pairs:
        raise ValueError("directional and micro pair overlap")
    if locked_pairs & (directional_pairs | micro_pairs):
        raise ValueError("locked pair is movable")
    if directional_pairs != set(DIRECTIONAL) or micro_pairs != set(MICRO_PAIRS):
        raise ValueError("invalid directional or micro pair set")
    if locked_pairs != LOCKED:
        raise ValueError("invalid locked pair set")
    feedback_pairs = {int(row["source_pair_id"]): row["direction"] for row in feedback["manual_adjustment_guidance"]}
    if feedback_pairs != DIRECTIONAL:
        raise ValueError("feedback directional contract mismatch")
    if set(feedback["micro_adjustment_allowed_pairs"]) != set(MICRO_PAIRS):
        raise ValueError("feedback micro contract mismatch")
    for key, expected in SAFETY.items():
        if value.get("safety_boundary", {}).get(key) != expected:
            raise ValueError(f"safety mismatch: {key}")


def _stage_values(sidecar: Mapping[str, Any], stage: str) -> tuple[tuple[float, ...], tuple[float, ...]]:
    values = tuple(float(value) for value in sidecar["stage_candidate_deltas"][stage]["candidate_deltas"])
    return tuple(sorted({abs(value) for value in values if value > 0.0})), tuple(value for value in values if value)


def _actions(sidecar: Mapping[str, Any], stage: str) -> list[tuple[int, str, float]]:
    _, micro = _stage_values(sidecar, stage)
    return [(sid, axis, delta) for sid in MICRO_PAIRS for axis in ("x", "bottom_y") for delta in micro]


def _cores(sidecar: Mapping[str, Any], stage: str) -> list[dict[int, dict[str, float]]]:
    directional, _ = _stage_values(sidecar, stage)
    result = []
    for a, b, c in itertools.product(directional, repeat=3):
        result.append({4: {"x": -a, "bottom_y": 0.0}, 9: {"x": -b, "bottom_y": 0.0}, 10: {"x": c, "bottom_y": 0.0}})
    return result


def _add_actions(core: Mapping[int, Mapping[str, float]], actions: Sequence[tuple[int, str, float]]) -> dict[int, dict[str, float]]:
    result = copy.deepcopy(dict(core))
    for sid, axis, delta in actions:
        result.setdefault(sid, {"x": 0.0, "bottom_y": 0.0})[axis] += delta
    return result


def _apply(before: Sequence[Mapping[str, Any]], deltas: Mapping[int, Mapping[str, float]]) -> list[dict[str, Any]]:
    rows = copy.deepcopy(list(before))
    for row in rows:
        delta = deltas.get(int(row["source_pair_id"]), {})
        row["top"]["x"] = float(row["top"]["x"]) + float(delta.get("x", 0.0))
        row["bottom"]["x"] = float(row["bottom"]["x"]) + float(delta.get("x", 0.0))
        row["bottom"]["y"] = float(row["bottom"]["y"]) + float(delta.get("bottom_y", 0.0))
    return rows


def _changes(before: Sequence[Mapping[str, Any]], after: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    original = _by_source(before); output = []
    for row in after:
        old = original[int(row["source_pair_id"])]; fields = {}
        for endpoint in ("top", "bottom"):
            for axis in ("x", "y"):
                delta = float(row[endpoint][axis]) - float(old[endpoint][axis])
                if abs(delta) > 1e-12: fields[f"{endpoint}_{axis}"] = {"before": float(old[endpoint][axis]), "after": float(row[endpoint][axis]), "delta": delta}
        if fields: output.append({"source_pair_id": int(row["source_pair_id"]), "solver_position": row["solver_position"], "verified_order_source_id": row["verified_order_source_id"], "effective_pair_index": row["effective_pair_index"], "fields": fields})
    return output


def _movement(deltas: Mapping[int, Mapping[str, float]]) -> float:
    return sum(3 * abs(float(value.get("x", 0))) + abs(float(value.get("bottom_y", 0))) for value in deltas.values())


def _candidate(index: int, stage: str, stage_cap: float, core: Mapping[int, Mapping[str, float]], actions: Sequence[tuple[int, str, float]], before: Sequence[Mapping[str, Any]], anchor_constraints: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    deltas = _add_actions(core, actions); rows = _apply(before, deltas)
    before_geo, after_geo = _geometry(before), _geometry(rows)
    wall_before, wall_after = before_geo["floorprint"]["summary"], after_geo["floorprint"]["summary"]
    per_wall = _per_wall_residual_delta(before, rows); moved = sorted(sid for sid, value in deltas.items() if any(abs(v) > 1e-12 for v in value.values()))
    affected = [row for row in per_wall["walls"] if any(sid in row["source_edge_ids"] for sid in moved)]
    local_before = sum(row["manhattan_residual_before_deg"] for row in affected); local_after = sum(row["manhattan_residual_after_deg"] for row in affected)
    local_max_before = max(row["manhattan_residual_before_deg"] for row in affected); local_max_after = max(row["manhattan_residual_after_deg"] for row in affected)
    old, new = _by_source(before), _by_source(rows); anchor = _anchor_audit(new, anchor_constraints)
    max_delta = max(abs(v) for pair in deltas.values() for v in pair.values())
    micro_actions = [{"source_pair_id": sid, "axis": axis, "delta": delta} for sid, axis, delta in actions]
    action_keys = {(sid, axis) for sid, axis, _ in actions}
    gates = {
        "human_direction_satisfied": all(deltas[sid]["x"] < 0 if direction == "left" else deltas[sid]["x"] > 0 for sid, direction in DIRECTIONAL.items()),
        "pair_specific_range_satisfied": all(abs(v) <= stage_cap + 1e-12 for pair in deltas.values() for v in pair.values()),
        "unauthorized_pairs_unchanged": all(old[sid] == new[sid] for sid in LOCKED),
        "stage_cap_satisfied": max_delta <= stage_cap + 1e-12,
        "maximum_absolute_delta_le_0_5": max_delta <= .5 + 1e-12,
        "at_most_two_micro_actions": len(actions) <= 2,
        "no_duplicate_micro_action": len(action_keys) == len(actions),
        "order_unchanged": [row["source_pair_id"] for row in rows] == list(VERIFIED_ORDER_SOURCE_IDS),
        "top_y_unchanged": all(float(old[sid]["top"]["y"]) == float(new[sid]["top"]["y"]) for sid in old),
        "no_self_intersection": not wall_after["self_intersection"], "no_pair_collapse": wall_after["minimum_wall_length"] >= MIN_WALL_LENGTH,
        "no_hard_visual_anchor_violation": not anchor["hard_violations"], "protected_pairs_unchanged": all(old[sid] == new[sid] for sid in LOCKED),
        "no_merge_delete_new_corner": len(rows) == len(before),
    }
    passed = all(gates.values()); local_ok = local_max_after <= local_max_before + LOCAL_MAX_WORSENING_TOLERANCE_DEG
    improved = local_ok and (local_before - local_after >= RESIDUAL_IMPROVEMENT_TOLERANCE_DEG or wall_before["wall_residual_sum_deg"] - wall_after["wall_residual_sum_deg"] >= RESIDUAL_IMPROVEMENT_TOLERANCE_DEG)
    if not passed: decision = "rejected_hard_gate"
    elif improved: decision = "review_available_geometry_improved"
    elif local_after < local_before or wall_after["wall_residual_sum_deg"] < wall_before["wall_residual_sum_deg"]: decision = "neutral_geometry_tradeoff"
    else: decision = "diagnostic_human_direction_only"
    return {"candidate_id": f"m_anchor_4_1_1_{stage.lower()}_{index:04d}", "search_stage": stage, "candidate_class": decision, "decision": decision,
        "directional_core": {str(k): v for k, v in core.items()}, "micro_actions": micro_actions, "changed_pairs": moved,
        "movement_by_axis": {str(k): v for k, v in deltas.items() if any(v.values())}, "maximum_absolute_delta": max_delta, "visual_anchor_movement_cost": _movement(deltas),
        "affected_edges": [row["source_edge_ids"] for row in affected], "improved_edges": [row["source_edge_ids"] for row in affected if row["residual_delta_deg"] < 0], "worsened_edges": [row["source_edge_ids"] for row in affected if row["residual_delta_deg"] > 0],
        "floor_heading_residual_sum_deg": wall_after["wall_residual_sum_deg"], "floor_heading_residual_max_deg": wall_after["wall_residual_max_deg"], "local_floor_heading_residual_sum_deg": local_after, "local_floor_heading_residual_max_deg": local_max_after,
        "floor_heading_residual_sum_before_deg": wall_before["wall_residual_sum_deg"], "local_floor_heading_residual_sum_before_deg": local_before, "local_floor_heading_residual_max_before_deg": local_max_before,
        "wall_residual_sum_deg": wall_after["wall_residual_sum_deg"], "wall_residual_max_deg": wall_after["wall_residual_max_deg"], "legacy_alias_for": "floor_heading_residual", "per_wall_residual_diagnostic": per_wall,
        "topology_before_after": _local_topology_metrics(before, rows), "anchor_audit": anchor, "hard_gate": gates, "hard_gate_passed": passed, "hard_gate_failure_reasons": [k for k, v in gates.items() if not v], "corrected_coordinates": rows, "coordinate_changes": _changes(before, rows), "top_y_changed": False, "height_not_entered": True, **SAFETY}


def _beam_key(row: Mapping[str, Any]) -> tuple[Any, ...]:
    rank = {"review_available_geometry_improved": 0, "neutral_geometry_tradeoff": 1, "diagnostic_human_direction_only": 2, "rejected_hard_gate": 3}
    return (not row["hard_gate_passed"], rank[row["candidate_class"]], row["local_floor_heading_residual_max_deg"], row["local_floor_heading_residual_sum_deg"], row["floor_heading_residual_sum_deg"], row["visual_anchor_movement_cost"], row["candidate_id"])


def _review_key(row: Mapping[str, Any]) -> tuple[Any, ...]:
    return ({"A": 0, "B": 1, "C": 2}[row["search_stage"]], *_beam_key(row))


def _stage(sidecar: Mapping[str, Any], stage: str, before: Sequence[Mapping[str, Any]], constraints: Sequence[Mapping[str, Any]], start: int) -> tuple[list[dict[str, Any]], dict[str, int]]:
    config = sidecar["search_config"]; budget = int(config["stage_evaluation_budget"][stage]); stage_cap = float(sidecar["stage_candidate_deltas"][stage]["max_delta"])
    evaluated = []; cores = _cores(sidecar, stage)
    for core in cores:
        evaluated.append(_candidate(start + len(evaluated), stage, stage_cap, core, (), before, constraints))
    actions = _actions(sidecar, stage)
    core_limit = min(int(config["core_beam"]), max(0, (budget - len(cores) - int(config["two_actions_per_beam"])) // len(actions)))
    core_beam = sorted((row for row in evaluated if row["hard_gate_passed"]), key=_beam_key)[:core_limit]
    for core_card in core_beam:
        core = {int(k): v for k, v in core_card["directional_core"].items()}
        for action in actions: evaluated.append(_candidate(start + len(evaluated), stage, stage_cap, core, (action,), before, constraints))
    second_order_limit = min(int(config["one_action_beam"]), max(0, (budget - len(evaluated)) // int(config["two_actions_per_beam"])))
    one_beam = sorted((row for row in evaluated if row["hard_gate_passed"] and len(row["micro_actions"]) == 1), key=_beam_key)[:second_order_limit]
    for row in one_beam:
        core = {int(k): v for k, v in row["directional_core"].items()}; first = tuple(row["micro_actions"][0][key] for key in ("source_pair_id", "axis", "delta"))
        same_core = [candidate for candidate in evaluated if candidate["directional_core"] == row["directional_core"] and len(candidate["micro_actions"]) == 1]
        remaining = [candidate for candidate in sorted(same_core, key=_beam_key) if tuple(candidate["micro_actions"][0][key] for key in ("source_pair_id", "axis")) != first[:2]]
        for candidate in remaining[:int(config["two_actions_per_beam"])]:
            action = tuple(candidate["micro_actions"][0][key] for key in ("source_pair_id", "axis", "delta"))
            evaluated.append(_candidate(start + len(evaluated), stage, stage_cap, core, (first, action), before, constraints))
    if len(evaluated) > budget: raise ValueError("stage raw evaluation cap exceeded")
    return evaluated, {"configured_core_beam": int(config["core_beam"]), "effective_core_beam": len(core_beam), "configured_one_action_beam": int(config["one_action_beam"]), "effective_one_action_beam": len(one_beam), "configured_two_actions_per_beam": int(config["two_actions_per_beam"]), "effective_two_actions_per_beam": min((len([row for row in evaluated if len(row["micro_actions"]) == 2]) // len(one_beam) if one_beam else 0), int(config["two_actions_per_beam"]))}


def _review(cards: Sequence[Mapping[str, Any]]) -> tuple[list[dict[str, Any]], list[str]]:
    passed = [dict(row) for row in cards if row["hard_gate_passed"]]; selected = []; reasons = []
    for stage, limit in (("A", 3), ("B", 1), ("C", 1)):
        rows = [row for row in sorted(passed, key=_beam_key) if row["search_stage"] == stage]
        if not rows:
            reasons.append(f"stage_{stage}_contrast_unavailable")
        selected.extend(rows[:limit])
    for row in sorted(passed, key=_review_key):
        if len(selected) >= REVIEW_LIMIT: break
        if row["candidate_id"] not in {item["candidate_id"] for item in selected}: selected.append(row)
    if any(row["micro_actions"] for row in passed) and not any(row["micro_actions"] for row in selected): raise ValueError("review set omitted micro candidate")
    if sum(bool(row["micro_actions"]) for row in [r for r in passed if r["candidate_class"] == "review_available_geometry_improved"]) >= 2 and sum(bool(row["micro_actions"]) for row in selected) < 2: reasons.append("geometry_improved_micro_candidates_exceed_review_capacity")
    return selected, reasons


def _failure_reason_counts(cards: Sequence[Mapping[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for card in cards:
        for reason in card["hard_gate_failure_reasons"]:
            counts[reason] = counts.get(reason, 0) + 1
    return dict(sorted(counts.items()))


def _geometry_improved(cards: Sequence[Mapping[str, Any]]) -> bool:
    return any(row["candidate_class"] == "review_available_geometry_improved" for row in cards)


def _summary(payload: Mapping[str, Any]) -> str:
    lines = ["# M-Anchor.4.1.1 staged micro-compensation footprint shadow probe", "", f"- stages_executed: `{payload['stages_executed']}`", "- Geometry residual decides review worthiness only, not correctness or acceptance.", "- top_y/height/writeback/active ranking remain unauthorized.", "", "| candidate | stage | class | micro actions | local max before→after | local sum before→after | global sum before→after | movement |", "| --- | --- | --- | --- | ---: | ---: | ---: | ---: |"]
    for r in payload["review_candidates"]:
        lines.append(f"| {r['candidate_id']} | {r['search_stage']} | {r['candidate_class']} | {len(r['micro_actions'])} | {r['local_floor_heading_residual_max_before_deg']:.3f}→{r['local_floor_heading_residual_max_deg']:.3f} | {r['local_floor_heading_residual_sum_before_deg']:.3f}→{r['local_floor_heading_residual_sum_deg']:.3f} | {r['floor_heading_residual_sum_before_deg']:.3f}→{r['floor_heading_residual_sum_deg']:.3f} | {r['visual_anchor_movement_cost']:.3f} |")
    return "\n".join(lines) + "\n"


def run(out_dir: Path = OUT_DIR, review_out_dir: Path = REVIEW_OUT_DIR, constraints_path: Path = CONSTRAINTS_PATH) -> dict[str, Path]:
    feedback, constraints_doc = _load(FEEDBACK_PATH), _load(constraints_path); _validate_constraints(constraints_doc, feedback)
    m1, m2, anchor_sidecar = _load(M1_AUDIT_PATH), _load(M2_VERDICT_PATH), _load_anchor_sidecar()
    if m2.get("accepted_as_final_fix") is not False or m2.get("annotation_writeback") is not False: raise ValueError("M2 baseline is not review-only")
    before = next(row for row in m1["solver_prototypes"] if row["candidate_id"] == m2["reviewed_candidate"])["corrected_coordinates"]
    anchor_constraints = _anchor_constraints(anchor_sidecar); all_cards = []; stats = {}; triggers = {}; effective_beam = {}
    for stage in ("A", "B", "C"):
        cards, effective_beam[stage] = _stage(constraints_doc, stage, before, anchor_constraints, len(all_cards) + 1); all_cards.extend(cards)
        if len(all_cards) > int(constraints_doc["search_config"]["max_raw_evaluations"]): raise ValueError("raw evaluation cap exceeded")
        improved = sum(row["candidate_class"] == "review_available_geometry_improved" for row in cards)
        stats[stage] = {"raw": len(cards), "hard_gate_pass": sum(row["hard_gate_passed"] for row in cards), "geometry_improved": improved}
        triggers[stage] = "initial_preferred_range" if stage == "A" else ("prior_stage_has_no_geometry_improved_candidate" if not any(row["candidate_class"] == "review_available_geometry_improved" for row in all_cards[:-len(cards)]) else "not_executed")
        if _geometry_improved(cards): break
    review, missing = _review(all_cards)
    provenance = {"m_anchor_4_human_feedback": {"path": FEEDBACK_PATH.as_posix(), "schema_version": feedback["schema_version"], "sha256": _sha(FEEDBACK_PATH)}, "m_anchor_4_1_1_staged_constraints": {"path": constraints_path.as_posix(), "schema_version": constraints_doc["schema_version"], "sha256": _sha(constraints_path)}, "m_anchor_1_audit": {"path": M1_AUDIT_PATH.as_posix(), "sha256": _sha(M1_AUDIT_PATH)}, "m_anchor_2_human_verdict": {"path": M2_VERDICT_PATH.as_posix(), "sha256": _sha(M2_VERDICT_PATH)}, "expert_anchor_sidecar": {"path": ANCHOR_SIDECAR_PATH.as_posix(), "sha256": _sha(ANCHOR_SIDECAR_PATH)}, "m_anchor_4_1_audit": {"path": M41_AUDIT_PATH.as_posix(), "sha256": _sha(M41_AUDIT_PATH)}, "baseline_review_candidate": m2["reviewed_candidate"]}
    by_stage = {stage: [card for card in all_cards if card["search_stage"] == stage] for stage in stats}
    payload = {"schema_version": "m_anchor_4_1_1_staged_micro_compensation_probe_audit_v1", "case_name": "task218_ann3741", "before_state": m2["reviewed_candidate"], "input_provenance": provenance, "numeric_contract": {k: constraints_doc[k] for k in ("numeric_range_status", "preferred_micro_cap", "intermediate_micro_cap", "maximum_micro_cap", "expansion_policy")}, "beam_pruning": {**constraints_doc["search_config"], "effective_beam_by_stage": effective_beam, "sort": "review: stage A-primary (3), B/C contrast (1 each), then class and metrics"}, "residual_semantics": {"legacy_alias_for": "floor_heading_residual", "top_y_cannot_repair_floor_heading_residual": True}, "stages_executed": list(stats), "expansion_trigger_by_stage": triggers, "expansion_trigger_reason": triggers, "candidate_count_by_stage": {k: v["raw"] for k, v in stats.items()}, "hard_gate_pass_count_by_stage": {k: v["hard_gate_pass"] for k, v in stats.items()}, "hard_gate_fail_count_by_stage": {stage: len(cards) - sum(card["hard_gate_passed"] for card in cards) for stage, cards in by_stage.items()}, "hard_gate_failure_reason_count_by_stage": {stage: _failure_reason_counts(cards) for stage, cards in by_stage.items()}, "geometry_improved_count_by_stage": {k: v["geometry_improved"] for k, v in stats.items()}, "raw_candidates_evaluated": len(all_cards), "requested_review_slots": REVIEW_LIMIT, "realized_review_slots": len(review), "missing_slot_reasons": missing, "review_candidates": review, "m_anchor_4_2_height_completion_authorized": False, "accepted_as_final_fix": False, **SAFETY}
    ledger = {"schema_version": "m_anchor_4_1_1_feedback_ledger_stub_v1", "case_name": payload["case_name"], "candidate_ids": [r["candidate_id"] for r in review], "expert_selected_candidate": None, "expert_verdict": None, "accepted_as_final_fix": False, "m_anchor_4_2_height_completion_authorized": False, **SAFETY}
    out_dir.mkdir(parents=True, exist_ok=True); audit = out_dir / "m_anchor_4_1_1_staged_probe_audit.json"; cards = out_dir / "m_anchor_4_1_1_candidate_cards.jsonl"; summary = out_dir / "m_anchor_4_1_1_summary.md"; ledger_path = out_dir / "m_anchor_4_1_1_feedback_ledger_stub.jsonl"
    _write_text_lf(audit, json.dumps(payload, ensure_ascii=False, indent=2) + "\n"); _write_text_lf(cards, "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in review)); _write_text_lf(summary, _summary(payload)); _write_text_lf(ledger_path, json.dumps(ledger, ensure_ascii=False) + "\n")
    review_out_dir.mkdir(parents=True, exist_ok=True); manifest = review_out_dir / "hypothesis_review_bridge_manifest.json"
    bridge = {"schema_version": "m_anchor_4_1_1_local_3d_review_bridge_v1", "case_name": "task218_ann3741_m_anchor_4_1_1", "source_image": m1.get("source_image"), "ordered_pairs": before, "candidates": [{"candidate_id": r["candidate_id"], "family": "m_anchor_4_1_1_staged_micro_compensation_probe", "decision_class": r["candidate_class"], "manual_review_candidate": True, "automatic_fix_claimed": False, "direct_ls_trial_allowed": False, "coordinate_changes": r["coordinate_changes"], "accepted": False, "downstream_recommendation": False, "annotation_writeback": False, "annotation_patch_generated": False} for r in review], "safety_boundary": {**SAFETY, "preview_only": True, "ranking_entry_allowed": False, "portfolio_selection_allowed": False}}
    _write_text_lf(manifest, json.dumps(bridge, ensure_ascii=False, indent=2) + "\n")
    review_paths = run_local_review(input_path=manifest, candidate_json=manifest, candidate_limit=len(review), out_dir=review_out_dir, image_root=DEFAULT_IMAGE_ROOT, case_name="task218_ann3741_m_anchor_4_1_1", width=1024, height=512, coordinate_mode="ls_percent", local_server_root=_local_server_root(review_out_dir))
    return {"audit": audit, "cards": cards, "summary": summary, "ledger": ledger_path, "review_manifest": manifest, **{f"review_{k}": v for k, v in review_paths.items()}}


if __name__ == "__main__": print(run()["audit"])
