"""M-Anchor.3b local chain constrained footprint solver for task218_ann3741.

Geometry residual can only decide whether a candidate is worth reviewing. It
cannot decide correctness; visual hard anchors and local topology preservation
rank above residual sum.
"""

from __future__ import annotations

import copy
import itertools
import json
import sys
from pathlib import Path
from typing import Any, Mapping, Sequence

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tools.paper_a_manhattan.run_m_anchor_1_3741 import (
    ANCHOR_SIDECAR_PATH,
    BASELINE_PATH,
    SAFETY,
    _anchor_audit,
    _anchor_constraints,
    _by_source,
    _load,
    _load_anchor_sidecar,
    _ordered,
    _per_wall_residuals,
    _sha,
    _write_text_lf,
)
from tools.paper_a_manhattan.run_m_anchor_3_footprint_solver import (
    M1_AUDIT_PATH,
    M2_VERDICT_PATH,
    _edge_length,
    _geometry,
    _local_topology_metrics,
    _per_wall_residual_delta,
)

OUT_DIR = Path("analysis_results/paper_a_manhattan/m_anchor/task218_ann3741_m_anchor_3b")
CHAIN_PAIR_IDS = (5, 6, 7, 8)
LOCAL_TOPOLOGY_EDGES = ([4, 6], [6, 5], [5, 8], [8, 7])
BOTTOM_DELTAS = (-0.5, -0.25, 0.0, 0.25, 0.5)
MAX_RAW_CANDIDATES = 200
TOP_K = 5
LOCAL_MIN_EDGE_THRESHOLD = 0.15
TARGET_STATEMENT = (
    "M-Anchor.3b tests whether local-chain x/bottom_y constrained footprint "
    "adjustments can reduce affected BEV Manhattan residuals while preserving "
    "visual anchors and local topology. top_y remains fixed and height is not entered."
)


def _check_m2_for_m3b(verdict: Mapping[str, Any], x_enabled: bool) -> None:
    authorization = verdict.get("next_stage_authorization", {})
    allowed = authorization.get("allowed_variables")
    if verdict.get("accept_for_next_stage") is not True:
        raise ValueError("M-Anchor.3b blocked: M2 accept_for_next_stage is not true")
    if verdict.get("accepted_as_final_fix") is not False:
        raise ValueError("M-Anchor.3b blocked: M2 accepted_as_final_fix must be false")
    if verdict.get("annotation_writeback") is not False:
        raise ValueError("M-Anchor.3b blocked: M2 annotation_writeback must be false")
    if verdict.get("expert_verdict") == "reject":
        raise ValueError("M-Anchor.3b blocked: M2 verdict is reject")
    if authorization.get("top_y_policy") != "fixed_for_m_anchor_3":
        raise ValueError("M-Anchor.3b blocked: top_y_policy must stay fixed")
    if authorization.get("writeback_allowed") is not False:
        raise ValueError("M-Anchor.3b blocked: writeback_allowed must be false")
    if authorization.get("ranking_entry_allowed") is not False:
        raise ValueError("M-Anchor.3b blocked: ranking_entry_allowed must be false")
    if authorization.get("solver_scope") != "footprint_only":
        raise ValueError("M-Anchor.3b blocked: solver_scope must be footprint_only")
    expected = ["bottom_y", "x"] if x_enabled else ["bottom_y"]
    if allowed != expected:
        raise ValueError(f"M-Anchor.3b blocked: allowed_variables={allowed!r}, expected {expected!r}")


def _chain_move_ranges(sidecar: Mapping[str, Any]) -> dict[int, dict[str, Mapping[str, Any]]]:
    ranges: dict[int, dict[str, Mapping[str, Any]]] = {sid: {} for sid in CHAIN_PAIR_IDS}
    for row in sidecar.get("move_ranges", []):
        sid = int(row.get("source_pair_id"))
        if sid not in ranges:
            continue
        if row.get("constraint_type") != "field_move_range":
            continue
        axis = row.get("axis")
        key = "bottom_y" if row.get("endpoint") == "bottom" and axis == "y" else axis
        if key not in {"bottom_y", "x"}:
            continue
        if key in ranges[sid]:
            raise ValueError(f"duplicate M-Anchor.3b move range for s{sid} {key}")
        ranges[sid][key] = row
    missing = [
        f"s{sid}_{key}"
        for sid, by_key in ranges.items()
        for key in ("bottom_y", "x")
        if key not in by_key
    ]
    if missing:
        raise ValueError(f"missing M-Anchor.3b move ranges: {missing}")
    return ranges


def _values_for_range(row: Mapping[str, Any]) -> tuple[float, ...]:
    min_delta = float(row["min_delta"])
    max_delta = float(row["max_delta"])
    strength = row["anchor_strength"]
    if min_delta == 0.0 and max_delta == 0.0:
        return (0.0,)
    if row["axis"] == "x":
        base = {"hard": (0.0,), "soft": (-0.2, 0.0, 0.2), "preferred": (-0.3, 0.0, 0.3)}[
            strength
        ]
    else:
        base = BOTTOM_DELTAS
    values = tuple(delta for delta in base if min_delta <= delta <= max_delta)
    if not values:
        raise ValueError(f"empty move range for s{row['source_pair_id']} {row['axis']}")
    return values


def _raw_delta_sets(ranges: Mapping[int, Mapping[str, Mapping[str, Any]]]) -> list[dict[int, dict[str, float]]]:
    bottom_values = [_values_for_range(ranges[sid]["bottom_y"]) for sid in CHAIN_PAIR_IDS]
    x_values = [_values_for_range(ranges[sid]["x"]) for sid in CHAIN_PAIR_IDS]
    raw = []
    for bottom_combo in itertools.product(*bottom_values):
        if sum(delta != 0.0 for delta in bottom_combo) > 2:
            continue
        for x_combo in itertools.product(*x_values):
            item = {
                sid: {"x": x_delta, "bottom_y": bottom_delta}
                for sid, x_delta, bottom_delta in zip(CHAIN_PAIR_IDS, x_combo, bottom_combo)
            }
            movement = sum(abs(v["bottom_y"]) + 3.0 * abs(v["x"]) for v in item.values())
            raw.append((movement, item))
    raw.sort(key=lambda row: (row[0], json.dumps(row[1], sort_keys=True)))
    return [item for _, item in raw[:MAX_RAW_CANDIDATES]]


def _apply_deltas(
    before_rows: Sequence[Mapping[str, Any]],
    deltas: Mapping[int, Mapping[str, float]],
) -> list[dict[str, Any]]:
    rows = copy.deepcopy(list(before_rows))
    for row in rows:
        sid = int(row["source_pair_id"])
        if sid not in deltas:
            continue
        row["top"]["x"] = float(row["top"]["x"]) + deltas[sid]["x"]
        row["bottom"]["x"] = float(row["bottom"]["x"]) + deltas[sid]["x"]
        row["bottom"]["y"] = float(row["bottom"]["y"]) + deltas[sid]["bottom_y"]
    return rows


def _affected_edges(moved_pairs: Sequence[int]) -> list[list[int]]:
    order = [2, 1, 3, 4, 6, 5, 8, 7, 9, 10, 12, 11]
    edges = []
    for idx, left in enumerate(order):
        right = order[(idx + 1) % len(order)]
        if left in moved_pairs or right in moved_pairs:
            edges.append([left, right])
    return edges or [list(edge) for edge in LOCAL_TOPOLOGY_EDGES]


def _wall_by_edge(per_wall: Mapping[str, Any]) -> dict[tuple[int, int], Mapping[str, Any]]:
    return {tuple(row["source_edge_ids"]): row for row in per_wall["walls"]}


def _candidate(
    index: int,
    deltas: Mapping[int, Mapping[str, float]],
    before_rows: Sequence[Mapping[str, Any]],
    constraints: Sequence[Mapping[str, Any]],
    ranges: Mapping[int, Mapping[str, Mapping[str, Any]]],
) -> dict[str, Any]:
    rows = _apply_deltas(before_rows, deltas)
    before_geometry = _geometry(before_rows)
    after_geometry = _geometry(rows)
    per_wall = _per_wall_residual_delta(before_rows, rows)
    per_wall_by_edge = _wall_by_edge(per_wall)
    moved_pairs = [sid for sid, values in deltas.items() if values["x"] or values["bottom_y"]]
    affected = _affected_edges(moved_pairs)
    affected_walls = [per_wall_by_edge[tuple(edge)] for edge in affected]
    improved = [row["source_edge_ids"] for row in affected_walls if row["residual_delta_deg"] < -1e-9]
    worsened = [row["source_edge_ids"] for row in affected_walls if row["residual_delta_deg"] > 1e-9]
    worst_before = max(affected_walls, key=lambda row: row["manhattan_residual_before_deg"])
    worst_after = max(affected_walls, key=lambda row: row["manhattan_residual_after_deg"])
    local_topology = _local_topology_metrics(before_rows, rows)
    topology_ratio_cost = sum(abs(edge["ratio"] - 1.0) for edge in local_topology["edges"])
    anchor = _anchor_audit(_by_source(rows), constraints)
    hard_x_violations = [
        {"source_pair_id": sid, "axis": "x", "delta": values["x"]}
        for sid, values in deltas.items()
        if ranges[sid]["x"]["anchor_strength"] == "hard" and values["x"] != 0.0
    ]
    movement_by_axis = {
        str(sid): values for sid, values in deltas.items() if values["x"] or values["bottom_y"]
    }
    movement_cost = sum(abs(v["bottom_y"]) + 3.0 * abs(v["x"]) for v in deltas.values())
    after_wall = after_geometry["floorprint"]["summary"]
    before_wall = before_geometry["floorprint"]["summary"]
    top_y_changed = False
    order_changed = False
    self_intersection = bool(after_geometry["floorprint"]["self_intersection"])
    pair_collapse = local_topology["local_min_edge_length"] < LOCAL_MIN_EDGE_THRESHOLD
    keep_distinct_5_6 = _edge_length(rows, 5, 6)
    keep_distinct_ok = keep_distinct_5_6 >= LOCAL_MIN_EDGE_THRESHOLD
    local_max_before = worst_before["manhattan_residual_before_deg"]
    local_max_after = worst_after["manhattan_residual_after_deg"]
    affected_sum_before = sum(row["manhattan_residual_before_deg"] for row in affected_walls)
    affected_sum_after = sum(row["manhattan_residual_after_deg"] for row in affected_walls)
    global_sum_after = after_wall["wall_residual_sum_deg"]

    hard_gate = {
        "order_unchanged": not order_changed,
        "no_self_intersection": not self_intersection,
        "no_hard_anchor_violation": not anchor["hard_violations"],
        "no_top_y_change": not top_y_changed,
        "no_pair_collapse": not pair_collapse,
        "keep_distinct_5_6": keep_distinct_ok,
        "local_min_edge_length_ok": local_topology["local_min_edge_length"] >= LOCAL_MIN_EDGE_THRESHOLD,
        "x_hard_anchors_satisfied": not hard_x_violations,
    }
    hard_gate_passed = all(hard_gate.values())
    if not hard_gate_passed:
        decision = "rejected_topology_risk"
        if anchor["hard_violations"] or hard_x_violations:
            decision = "rejected_hard_anchor_violation"
    elif local_max_after > local_max_before + 1e-9:
        decision = "neutral_review"
    elif affected_sum_after < affected_sum_before and global_sum_after < before_wall["wall_residual_sum_deg"]:
        decision = "review_available"
    else:
        decision = "neutral_review"

    return {
        "candidate_id": f"m_anchor_3b_candidate_{index:04d}",
        "affected_edges": affected,
        "improved_edges": improved,
        "worsened_edges": worsened,
        "worst_edge_before": {
            "source_edge_ids": worst_before["source_edge_ids"],
            "residual_deg": worst_before["manhattan_residual_before_deg"],
        },
        "worst_edge_after": {
            "source_edge_ids": worst_after["source_edge_ids"],
            "residual_deg": worst_after["manhattan_residual_after_deg"],
        },
        "moved_pairs": moved_pairs,
        "movement_by_axis": movement_by_axis,
        "movement_cost": movement_cost,
        "anchor_violations": anchor["violations"],
        "hard_gate": hard_gate,
        "hard_gate_passed": hard_gate_passed,
        "local_topology_before_after": local_topology,
        "per_wall_residual_diagnostic": per_wall,
        "wall_residual_sum_before": before_wall["wall_residual_sum_deg"],
        "wall_residual_sum_after": global_sum_after,
        "local_affected_residual_sum_before": affected_sum_before,
        "local_affected_residual_sum_after": affected_sum_after,
        "local_affected_residual_max_before": local_max_before,
        "local_affected_residual_max_after": local_max_after,
        "ranking_layers": {
            "L1_local_max_residual_after": local_max_after,
            "L2_local_sum_residual_after": affected_sum_after,
            "L3_global_sum_residual_after": global_sum_after,
            "L4_movement_cost": movement_cost,
            "L5_topology_ratio_cost": topology_ratio_cost,
        },
        "height_not_entered": True,
        "top_y_changed": top_y_changed,
        "reorder_changed": order_changed,
        "candidate_available": decision == "review_available",
        "decision": decision,
        "corrected_coordinates": rows,
        **SAFETY,
    }


def _sort_key(row: Mapping[str, Any]) -> tuple[Any, ...]:
    layers = row["ranking_layers"]
    return (
        0 if row["hard_gate_passed"] else 1,
        0 if row["local_affected_residual_max_after"] <= row["local_affected_residual_max_before"] else 1,
        layers["L1_local_max_residual_after"],
        layers["L2_local_sum_residual_after"],
        layers["L3_global_sum_residual_after"],
        layers["L4_movement_cost"],
        layers["L5_topology_ratio_cost"],
    )


def _summary(payload: Mapping[str, Any]) -> str:
    lines = [
        "# M-Anchor.3b task218_ann3741",
        "",
        TARGET_STATEMENT,
        "",
        "- Existing M-Anchor.3 is retained as `s6 bottom_y` sensitivity diagnostic.",
        "- Geometry residual decides review worthiness only; visual hard anchors and local topology outrank residual sum.",
        f"- raw_candidates_evaluated: `{payload['raw_candidates_evaluated']}`",
        f"- candidate_count: `{payload['candidate_count']}`",
        "",
        "| candidate | moved pairs | local max before->after | local sum before->after | global sum after | movement | decision |",
        "| --- | --- | ---: | ---: | ---: | ---: | --- |",
    ]
    for row in payload["candidate_cards"]:
        lines.append(
            f"| {row['candidate_id']} | {row['moved_pairs']} | "
            f"{row['local_affected_residual_max_before']:.3f}->{row['local_affected_residual_max_after']:.3f} | "
            f"{row['local_affected_residual_sum_before']:.3f}->{row['local_affected_residual_sum_after']:.3f} | "
            f"{row['wall_residual_sum_after']:.3f} | {row['movement_cost']:.3f} | {row['decision']} |"
        )
    return "\n".join(lines) + "\n"


def run(out_dir: Path = OUT_DIR) -> dict[str, Path]:
    m1 = _load(M1_AUDIT_PATH)
    m2 = _load(M2_VERDICT_PATH)
    sidecar = _load_anchor_sidecar()
    ranges = _chain_move_ranges(sidecar)
    x_enabled = any(
        float(ranges[sid]["x"]["min_delta"]) != 0.0 or float(ranges[sid]["x"]["max_delta"]) != 0.0
        for sid in CHAIN_PAIR_IDS
    )
    _check_m2_for_m3b(m2, x_enabled)
    constraints = _anchor_constraints(sidecar)
    before_rows = next(
        row
        for row in m1["solver_prototypes"]
        if row["candidate_id"] == m2["reviewed_candidate"]
    )["corrected_coordinates"]
    raw_delta_sets = _raw_delta_sets(ranges)
    raw_candidates = [
        _candidate(index, deltas, before_rows, constraints, ranges)
        for index, deltas in enumerate(raw_delta_sets, start=1)
    ]
    sorted_candidates = sorted(raw_candidates, key=_sort_key)
    selected = []
    seen_move_signatures = set()
    for row in sorted_candidates:
        signature = tuple(row["moved_pairs"])
        if signature in seen_move_signatures and len(selected) < TOP_K - 1:
            continue
        selected.append(row)
        seen_move_signatures.add(signature)
        if len(selected) == TOP_K:
            break
    if len(selected) < TOP_K:
        for row in sorted_candidates:
            if row not in selected:
                selected.append(row)
            if len(selected) == TOP_K:
                break

    payload = {
        "schema_version": "m_anchor_3b_local_chain_footprint_solver_audit_v1",
        "case_name": "task218_ann3741",
        "goal": TARGET_STATEMENT,
        "prior_m_anchor_3_role": "s6_bottom_y_sensitivity_diagnostic",
        "input_sources": {
            "m_anchor_1_audit": {"path": M1_AUDIT_PATH.as_posix(), "sha256": _sha(M1_AUDIT_PATH)},
            "expert_anchor_constraints_sidecar": {
                "path": ANCHOR_SIDECAR_PATH.as_posix(),
                "sha256": _sha(ANCHOR_SIDECAR_PATH),
            },
            "m_anchor_2_human_verdict": {
                "path": M2_VERDICT_PATH.as_posix(),
                "sha256": _sha(M2_VERDICT_PATH),
            },
            "baseline_ordered_pairs": {"path": BASELINE_PATH.as_posix(), "sha256": _sha(BASELINE_PATH)},
        },
        "chain_pair_ids": list(CHAIN_PAIR_IDS),
        "move_ranges_used": ranges,
        "hard_gate_order": [
            "order unchanged",
            "no self-intersection",
            "no hard anchor violation",
            "no top_y change",
            "no pair collapse",
            "5-6 keep distinct",
            "local_min_edge_length threshold",
            "x hard anchors satisfied",
        ],
        "ranking_order": [
            "L1 local affected max residual",
            "L2 local affected residual sum",
            "L3 global residual sum",
            "L4 movement cost",
            "L5 topology ratio cost",
        ],
        "raw_candidates_evaluated": len(raw_candidates),
        "candidate_count": len(selected),
        "candidate_cards": selected,
        "accepted": False,
        "accepted_as_final_fix": False,
        **SAFETY,
    }
    ledger = {
        "schema_version": "m_anchor_3b_feedback_ledger_stub_v1",
        "case_name": payload["case_name"],
        "candidate_ids": [row["candidate_id"] for row in selected],
        "expert_selected_candidate": None,
        "accepted_as_final_fix": False,
        **SAFETY,
    }

    out_dir.mkdir(parents=True, exist_ok=True)
    audit_path = out_dir / "m_anchor_3b_local_chain_footprint_solver_audit.json"
    summary_path = out_dir / "m_anchor_3b_summary.md"
    cards_path = out_dir / "m_anchor_3b_candidate_cards.jsonl"
    ledger_path = out_dir / "m_anchor_3b_feedback_ledger_stub.jsonl"
    _write_text_lf(audit_path, json.dumps(payload, ensure_ascii=False, indent=2) + "\n")
    _write_text_lf(summary_path, _summary(payload))
    _write_text_lf(cards_path, "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in selected))
    _write_text_lf(ledger_path, json.dumps(ledger, ensure_ascii=False) + "\n")
    return {"audit": audit_path, "summary": summary_path, "cards": cards_path, "ledger": ledger_path}


if __name__ == "__main__":
    print(run()["audit"])
