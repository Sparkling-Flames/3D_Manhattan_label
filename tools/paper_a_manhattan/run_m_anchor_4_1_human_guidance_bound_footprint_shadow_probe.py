"""M-Anchor.4.1 human-guidance-bound footprint shadow probe for task218_ann3741."""

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

from tools.paper_a_manhattan.run_local_3d_projection_review import run_local_review
from tools.paper_a_manhattan.run_m_anchor_1_3741 import (
    ANCHOR_SIDECAR_PATH,
    SAFETY,
    _anchor_audit,
    _anchor_constraints,
    _by_source,
    _load,
    _load_anchor_sidecar,
    _sha,
    _write_text_lf,
)
from tools.paper_a_manhattan.run_m_anchor_3_footprint_solver import (
    M1_AUDIT_PATH,
    M2_VERDICT_PATH,
    _geometry,
    _local_topology_metrics,
    _per_wall_residual_delta,
)
from tools.paper_a_manhattan.segment_aware_manhattan_refit import VERIFIED_ORDER_SOURCE_IDS


M4_ROOT = Path("analysis_results/paper_a_manhattan/m_anchor/task218_ann3741_m_anchor_4")
FEEDBACK_PATH = M4_ROOT / "m_anchor_4_human_feedback_20260709.json"
GUIDANCE_PATH = M4_ROOT / "m_anchor_4_1_human_guidance_constraints.json"
OUT_DIR = Path("analysis_results/paper_a_manhattan/m_anchor/task218_ann3741_m_anchor_4_1")
REVIEW_OUT_DIR = Path(
    "analysis_results/paper_a_manhattan/hypothesis_local_review/task218_ann3741_m_anchor_4_1"
)
DEFAULT_IMAGE_ROOT = Path("data/mp3d_layout/img_v")
TOP_K = 5
MIN_WALL_LENGTH = 0.15
TARGET_STATEMENT = (
    "M-Anchor.4.1 tests whether human-guided x/bottom_y footprint changes can "
    "be reviewed without violating visual anchors; top_y is forbidden and height is not entered."
)


def _local_server_root(out_dir: Path) -> Path | None:
    try:
        out_dir.resolve().relative_to(REPO_ROOT.resolve())
    except ValueError:
        return None
    return REPO_ROOT


def _validate_feedback(feedback: Mapping[str, Any]) -> None:
    if feedback.get("schema_version") != "m_anchor_4_human_feedback_v1":
        raise ValueError("unsupported M4 human feedback schema")
    if feedback.get("case_name") != "task218_ann3741":
        raise ValueError("M4 human feedback case_name mismatch")
    for key in (
        "accepted_as_final_fix",
        "downstream_recommendation",
        "candidate_preference_authorized",
        "annotation_writeback",
        "annotation_patch_generated",
        "active_runner_role",
    ):
        if feedback.get(key) is not False:
            raise ValueError(f"M4.1 requires feedback {key}=false")


def _validate_guidance(
    guidance: Mapping[str, Any], feedback: Mapping[str, Any]
) -> tuple[list[Mapping[str, Any]], list[Mapping[str, Any]], set[int]]:
    if guidance.get("schema_version") != "m_anchor_4_1_human_guidance_constraints_v1":
        raise ValueError("unsupported M4.1 guidance schema")
    if guidance.get("case_name") != "task218_ann3741":
        raise ValueError("M4.1 guidance case_name mismatch")
    if guidance.get("source_annotation_id") != 3741 or guidance.get("coordinate_space") != "ls_percent":
        raise ValueError("M4.1 guidance identity mismatch")
    if guidance.get("allowed_variables") != ["x", "bottom_y"]:
        raise ValueError("M4.1 must allow x + bottom_y only")
    if "top_y" not in guidance.get("forbidden_variables", []):
        raise ValueError("M4.1 must forbid top_y")
    for key, value in SAFETY.items():
        if guidance.get("safety_boundary", {}).get(key) != value:
            raise ValueError(f"M4.1 guidance safety mismatch: {key}")

    feedback_directions = {
        int(row["source_pair_id"]): (row["axis"], row["direction"])
        for row in feedback.get("manual_adjustment_guidance", [])
    }
    directional = list(guidance.get("directional_pair_ranges", []))
    if {int(row["source_pair_id"]) for row in directional} != set(feedback_directions):
        raise ValueError("M4.1 directional guidance does not match feedback pairs")
    seen = set()
    for row in directional:
        sid = int(row["source_pair_id"])
        if sid in seen or row.get("axis") != "x" or row.get("endpoint") != "both":
            raise ValueError("invalid M4.1 directional range")
        seen.add(sid)
        if feedback_directions[sid] != (row.get("axis"), row.get("direction")):
            raise ValueError(f"M4.1 directional feedback mismatch for s{sid}")
        lower, upper = float(row["min_delta"]), float(row["max_delta"])
        if row["direction"] == "left" and not (lower < 0.0 and upper < 0.0):
            raise ValueError(f"M4.1 left range must stay negative for s{sid}")
        if row["direction"] == "right" and not (lower > 0.0 and upper > 0.0):
            raise ValueError(f"M4.1 right range must stay positive for s{sid}")
        if not row.get("candidate_deltas") or any(
            not lower <= float(value) <= upper for value in row["candidate_deltas"]
        ):
            raise ValueError(f"invalid M4.1 directional sample values for s{sid}")

    micro = list(guidance.get("micro_adjustment_ranges", []))
    feedback_micro = {int(value) for value in feedback.get("micro_adjustment_allowed_pairs", [])}
    if {int(row["source_pair_id"]) for row in micro} != feedback_micro:
        raise ValueError("M4.1 micro-adjustment pairs do not match feedback")
    micro_seen = set()
    for row in micro:
        sid = int(row["source_pair_id"])
        key = (sid, row.get("endpoint"), row.get("axis"))
        if key in micro_seen or key[1:] not in {("both", "x"), ("bottom", "y")}:
            raise ValueError("invalid or duplicate M4.1 micro range")
        micro_seen.add(key)
        lower, upper = float(row["min_delta"]), float(row["max_delta"])
        cap = 0.1 if row["axis"] == "x" else 0.25
        if lower < -cap or upper > cap or 0.0 not in row.get("candidate_deltas", []):
            raise ValueError(f"M4.1 micro cap mismatch for s{sid}")

    locked = {int(value) for value in guidance.get("locked_source_pair_ids", [])}
    expected_locked = set(VERIFIED_ORDER_SOURCE_IDS) - set(feedback_directions) - feedback_micro
    if locked != expected_locked:
        raise ValueError("M4.1 locked pair set mismatch")
    return directional, micro, locked


def _range_index(rows: Sequence[Mapping[str, Any]]) -> dict[tuple[int, str], Mapping[str, Any]]:
    result = {}
    for row in rows:
        key = (int(row["source_pair_id"]), "x" if row["axis"] == "x" else "bottom_y")
        result[key] = row
    return result


def _core_deltas(directional: Sequence[Mapping[str, Any]]) -> list[dict[int, dict[str, float]]]:
    result = []
    for values in itertools.product(*(row["candidate_deltas"] for row in directional)):
        result.append({
            int(row["source_pair_id"]): {"x": float(value), "bottom_y": 0.0}
            for row, value in zip(directional, values)
        })
    return result


def _raw_delta_sets(
    directional: Sequence[Mapping[str, Any]], micro: Sequence[Mapping[str, Any]]
) -> list[dict[int, dict[str, float]]]:
    cores = _core_deltas(directional)
    midpoint = cores[len(cores) // 2]
    raw = [copy.deepcopy(row) for row in cores]
    for move in micro:
        axis = "x" if move["axis"] == "x" else "bottom_y"
        for delta in move["candidate_deltas"]:
            if float(delta) == 0.0:
                continue
            item = copy.deepcopy(midpoint)
            item[int(move["source_pair_id"])] = {"x": 0.0, "bottom_y": 0.0}
            item[int(move["source_pair_id"])][axis] = float(delta)
            raw.append(item)
    return raw


def _apply_deltas(
    before_rows: Sequence[Mapping[str, Any]], deltas: Mapping[int, Mapping[str, float]]
) -> list[dict[str, Any]]:
    rows = copy.deepcopy(list(before_rows))
    for row in rows:
        values = deltas.get(int(row["source_pair_id"]))
        if not values:
            continue
        row["top"]["x"] = float(row["top"]["x"]) + values["x"]
        row["bottom"]["x"] = float(row["bottom"]["x"]) + values["x"]
        row["bottom"]["y"] = float(row["bottom"]["y"]) + values["bottom_y"]
    return rows


def _coordinate_changes(
    before_rows: Sequence[Mapping[str, Any]], after_rows: Sequence[Mapping[str, Any]]
) -> list[dict[str, Any]]:
    before = _by_source(before_rows)
    changes = []
    for after in after_rows:
        old = before[int(after["source_pair_id"])]
        fields = {}
        for endpoint, prefix in (("top", "top"), ("bottom", "bottom")):
            for axis in ("x", "y"):
                delta = float(after[endpoint][axis]) - float(old[endpoint][axis])
                if abs(delta) > 1e-9:
                    fields[f"{prefix}_{axis}"] = {
                        "before": float(old[endpoint][axis]),
                        "after": float(after[endpoint][axis]),
                        "delta": delta,
                    }
        if fields:
            changes.append({
                "source_pair_id": int(after["source_pair_id"]),
                "solver_position": after["solver_position"],
                "verified_order_source_id": after["verified_order_source_id"],
                "effective_pair_index": after["effective_pair_index"],
                "fields": fields,
            })
    return changes


def _affected_edges(moved_pairs: Sequence[int]) -> list[list[int]]:
    return [
        [left, VERIFIED_ORDER_SOURCE_IDS[(index + 1) % len(VERIFIED_ORDER_SOURCE_IDS)]]
        for index, left in enumerate(VERIFIED_ORDER_SOURCE_IDS)
        if left in moved_pairs or VERIFIED_ORDER_SOURCE_IDS[(index + 1) % len(VERIFIED_ORDER_SOURCE_IDS)] in moved_pairs
    ]


def _movement_cost(deltas: Mapping[int, Mapping[str, float]]) -> float:
    return sum(3.0 * abs(row["x"]) + abs(row["bottom_y"]) for row in deltas.values())


def _candidate(
    index: int,
    deltas: Mapping[int, Mapping[str, float]],
    before_rows: Sequence[Mapping[str, Any]],
    constraints: Sequence[Mapping[str, Any]],
    directional: Sequence[Mapping[str, Any]],
    micro: Sequence[Mapping[str, Any]],
    locked: set[int],
) -> dict[str, Any]:
    rows = _apply_deltas(before_rows, deltas)
    before_geometry = _geometry(before_rows)
    after_geometry = _geometry(rows)
    per_wall = _per_wall_residual_delta(before_rows, rows)
    moved_pairs = sorted(sid for sid, row in deltas.items() if row["x"] or row["bottom_y"])
    affected = _affected_edges(moved_pairs)
    by_edge = {tuple(row["source_edge_ids"]): row for row in per_wall["walls"]}
    affected_walls = [by_edge[tuple(edge)] for edge in affected]
    anchor = _anchor_audit(_by_source(rows), constraints)
    directional_ranges = _range_index(directional)
    micro_ranges = _range_index(micro)
    human_direction_satisfied = all(
        float(row["min_delta"]) <= deltas.get(int(row["source_pair_id"]), {}).get("x", 0.0) <= float(row["max_delta"])
        for row in directional
    )
    pair_specific_range_satisfied = all(
        float(row["min_delta"]) <= deltas.get(sid, {}).get(axis, 0.0) <= float(row["max_delta"])
        for (sid, axis), row in directional_ranges.items()
    ) and all(
        (sid, axis) in set(directional_ranges) | set(micro_ranges) or abs(value) <= 1e-9
        for sid, values in deltas.items()
        for axis, value in values.items()
    )
    micro_adjustment_cap_satisfied = all(
        float(row["min_delta"]) <= deltas.get(sid, {}).get(axis, 0.0) <= float(row["max_delta"])
        for (sid, axis), row in micro_ranges.items()
    )
    before_by_source, after_by_source = _by_source(before_rows), _by_source(rows)
    unauthorized_pairs_unchanged = all(before_by_source[sid] == after_by_source[sid] for sid in locked)
    order_unchanged = [int(row["source_pair_id"]) for row in rows] == list(VERIFIED_ORDER_SOURCE_IDS)
    top_y_unchanged = all(
        float(before_by_source[sid]["top"]["y"]) == float(after_by_source[sid]["top"]["y"])
        for sid in before_by_source
    )
    wall = after_geometry["floorprint"]["summary"]
    local_topology = _local_topology_metrics(before_rows, rows)
    hard_gate = {
        "human_direction_satisfied": human_direction_satisfied,
        "unauthorized_pairs_unchanged": unauthorized_pairs_unchanged,
        "micro_adjustment_cap_satisfied": micro_adjustment_cap_satisfied,
        "pair_specific_range_satisfied": pair_specific_range_satisfied,
        "order_unchanged": order_unchanged,
        "no_self_intersection": not wall["self_intersection"],
        "no_pair_collapse": wall["minimum_wall_length"] >= MIN_WALL_LENGTH,
        "no_hard_visual_anchor_violation": not anchor["hard_violations"],
        "top_y_unchanged": top_y_unchanged,
    }
    hard_gate_passed = all(hard_gate.values())
    if not hard_gate_passed:
        decision = "rejected_hard_anchor_violation" if anchor["hard_violations"] else "rejected_topology_risk"
    else:
        decision = "review_available"
    local_worst_before = max(row["manhattan_residual_before_deg"] for row in affected_walls)
    local_worst_after = max(row["manhattan_residual_after_deg"] for row in affected_walls)
    local_sum_before = sum(row["manhattan_residual_before_deg"] for row in affected_walls)
    local_sum_after = sum(row["manhattan_residual_after_deg"] for row in affected_walls)
    before_wall = before_geometry["floorprint"]["summary"]
    topology_cost = sum(abs(float(row["ratio"]) - 1.0) for row in local_topology["edges"] if row["ratio"] is not None)
    return {
        "candidate_id": f"m_anchor_4_1_candidate_{index:04d}",
        "solver_scope": "footprint_shadow_probe_only",
        "changed_pairs": moved_pairs,
        "movement_by_axis": {str(sid): row for sid, row in deltas.items() if row["x"] or row["bottom_y"]},
        "visual_anchor_movement_cost": _movement_cost(deltas),
        "affected_edges": affected,
        "improved_edges": [row["source_edge_ids"] for row in affected_walls if row["residual_delta_deg"] < 0.0],
        "worsened_edges": [row["source_edge_ids"] for row in affected_walls if row["residual_delta_deg"] > 0.0],
        "per_wall_residual_diagnostic": per_wall,
        "local_topology_before_after": local_topology,
        "anchor_audit": anchor,
        "hard_gate": hard_gate,
        "hard_gate_passed": hard_gate_passed,
        "ranking_layers": {
            "L0_human_guidance_adherence": 0 if hard_gate_passed else 1,
            "L1_visual_anchor_movement_cost": _movement_cost(deltas),
            "L2_local_worst_wall_residual": local_worst_after,
            "L3_local_residual_sum": local_sum_after,
            "L3_global_residual_sum": wall["wall_residual_sum_deg"],
            "L4_topology_preservation_cost": topology_cost,
        },
        "local_worst_wall_before": local_worst_before,
        "local_worst_wall_after": local_worst_after,
        "local_residual_sum_before": local_sum_before,
        "local_residual_sum_after": local_sum_after,
        "global_residual_sum_before": before_wall["wall_residual_sum_deg"],
        "global_residual_sum_after": wall["wall_residual_sum_deg"],
        "top_y_changed": not top_y_unchanged,
        "height_not_entered": True,
        "candidate_available": decision == "review_available",
        "decision": decision,
        "coordinate_changes": _coordinate_changes(before_rows, rows),
        "corrected_coordinates": rows,
        **SAFETY,
    }


def _sort_key(row: Mapping[str, Any]) -> tuple[float, ...]:
    layers = row["ranking_layers"]
    return (
        layers["L0_human_guidance_adherence"],
        layers["L1_visual_anchor_movement_cost"],
        layers["L2_local_worst_wall_residual"],
        layers["L3_local_residual_sum"],
        layers["L3_global_residual_sum"],
        layers["L4_topology_preservation_cost"],
    )


def _summary(payload: Mapping[str, Any]) -> str:
    lines = [
        "# M-Anchor.4.1 human-guidance-bound footprint shadow probe",
        "",
        f"- Goal: {TARGET_STATEMENT}",
        "- M4.2 height completion is not authorized here; it requires a future human `partial_accept_directionally_useful` verdict for one M4.1 candidate.",
        f"- raw_candidates_evaluated: `{payload['raw_candidates_evaluated']}`",
        f"- candidate_count: `{payload['candidate_count']}`",
        "",
        "| candidate | moved pairs | L1 movement | local worst before->after | global sum before->after | decision |",
        "| --- | --- | ---: | ---: | ---: | --- |",
    ]
    for row in payload["candidate_cards"]:
        lines.append(
            f"| {row['candidate_id']} | {row['changed_pairs']} | {row['visual_anchor_movement_cost']:.3f} | "
            f"{row['local_worst_wall_before']:.3f}->{row['local_worst_wall_after']:.3f} | "
            f"{row['global_residual_sum_before']:.3f}->{row['global_residual_sum_after']:.3f} | {row['decision']} |"
        )
    return "\n".join(lines) + "\n"


def _review_manifest(
    payload: Mapping[str, Any], baseline_rows: Sequence[Mapping[str, Any]], source_image: str | None
) -> dict[str, Any]:
    return {
        "schema_version": "m_anchor_4_1_local_3d_review_bridge_v1",
        "case_name": "task218_ann3741_m_anchor_4_1",
        "source_case_name": "task218_ann3741",
        "source_image": source_image,
        "ordered_pairs": list(baseline_rows),
        "candidates": [
            {
                "candidate_id": row["candidate_id"],
                "family": "m_anchor_4_1_human_guidance_bound_footprint_shadow_probe",
                "decision_class": row["decision"],
                "manual_review_candidate": True,
                "automatic_fix_claimed": False,
                "direct_ls_trial_allowed": False,
                "coordinate_changes": row["coordinate_changes"],
                "accepted": False,
                "downstream_recommendation": False,
                "candidate_preference_authorized": False,
                "annotation_writeback": False,
                "annotation_patch_generated": False,
            }
            for row in payload["candidate_cards"]
        ],
        "safety_boundary": {**SAFETY, "preview_only": True, "ranking_entry_allowed": False, "portfolio_selection_allowed": False},
    }


def run(
    out_dir: Path = OUT_DIR,
    review_out_dir: Path = REVIEW_OUT_DIR,
    feedback_path: Path = FEEDBACK_PATH,
    guidance_path: Path = GUIDANCE_PATH,
) -> dict[str, Path]:
    feedback, guidance = _load(feedback_path), _load(guidance_path)
    _validate_feedback(feedback)
    directional, micro, locked = _validate_guidance(guidance, feedback)
    m1, m2, anchor_sidecar = _load(M1_AUDIT_PATH), _load(M2_VERDICT_PATH), _load_anchor_sidecar()
    if m2.get("accepted_as_final_fix") is not False or m2.get("annotation_writeback") is not False:
        raise ValueError("M4.1 requires the M2 baseline to remain review-only")
    baseline_rows = next(
        row for row in m1["solver_prototypes"] if row["candidate_id"] == m2["reviewed_candidate"]
    )["corrected_coordinates"]
    constraints = _anchor_constraints(anchor_sidecar)
    raw = _raw_delta_sets(directional, micro)
    cards = sorted(
        [_candidate(index, deltas, baseline_rows, constraints, directional, micro, locked) for index, deltas in enumerate(raw, start=1)],
        key=_sort_key,
    )[:TOP_K]
    payload = {
        "schema_version": "m_anchor_4_1_human_guidance_bound_footprint_shadow_probe_audit_v1",
        "case_name": "task218_ann3741",
        "goal": TARGET_STATEMENT,
        "input_provenance": {
            "m_anchor_4_human_feedback": {"path": feedback_path.as_posix(), "schema_version": feedback["schema_version"], "sha256": _sha(feedback_path)},
            "m_anchor_4_1_human_guidance_constraints": {"path": guidance_path.as_posix(), "schema_version": guidance["schema_version"], "sha256": _sha(guidance_path)},
            "m_anchor_1_audit": {"path": M1_AUDIT_PATH.as_posix(), "sha256": _sha(M1_AUDIT_PATH)},
            "m_anchor_2_human_verdict": {"path": M2_VERDICT_PATH.as_posix(), "sha256": _sha(M2_VERDICT_PATH)},
            "expert_anchor_constraints_sidecar": {"path": ANCHOR_SIDECAR_PATH.as_posix(), "sha256": _sha(ANCHOR_SIDECAR_PATH)},
            "baseline_review_candidate": m2["reviewed_candidate"],
        },
        "allowed_variables": guidance["allowed_variables"],
        "forbidden_variables": guidance["forbidden_variables"],
        "locked_source_pair_ids": sorted(locked),
        "hard_gate_order": [
            "human_direction_satisfied", "unauthorized_pairs_unchanged", "micro_adjustment_cap_satisfied",
            "pair_specific_range_satisfied", "order_unchanged", "no_self_intersection",
            "no_pair_collapse", "no_hard_visual_anchor_violation",
        ],
        "ranking_order": ["L0 human guidance adherence", "L1 visual-anchor movement cost", "L2 local worst-wall residual", "L3 local/global residual sum", "L4 topology preservation"],
        "raw_candidate_plan": "27 directional combinations plus 24 single micro-adjustment probes around the guidance midpoint",
        "raw_candidates_evaluated": len(raw),
        "candidate_count": len(cards),
        "candidate_cards": cards,
        "m_anchor_4_2_height_completion_authorized": False,
        "m_anchor_4_2_required_human_verdict": "partial_accept_directionally_useful",
        "accepted_as_final_fix": False,
        **SAFETY,
    }
    ledger = {
        "schema_version": "m_anchor_4_1_feedback_ledger_stub_v1",
        "case_name": payload["case_name"],
        "candidate_ids": [row["candidate_id"] for row in cards],
        "expert_selected_candidate": None,
        "expert_verdict": None,
        "m_anchor_4_2_height_completion_authorized": False,
        "required_expert_verdict_for_m_anchor_4_2": "partial_accept_directionally_useful",
        "accepted_as_final_fix": False,
        **SAFETY,
    }
    out_dir.mkdir(parents=True, exist_ok=True)
    audit_path = out_dir / "m_anchor_4_1_footprint_shadow_probe_audit.json"
    cards_path = out_dir / "m_anchor_4_1_candidate_cards.jsonl"
    summary_path = out_dir / "m_anchor_4_1_summary.md"
    ledger_path = out_dir / "m_anchor_4_1_feedback_ledger_stub.jsonl"
    _write_text_lf(audit_path, json.dumps(payload, ensure_ascii=False, indent=2) + "\n")
    _write_text_lf(cards_path, "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in cards))
    _write_text_lf(summary_path, _summary(payload))
    _write_text_lf(ledger_path, json.dumps(ledger, ensure_ascii=False) + "\n")

    review_out_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = review_out_dir / "hypothesis_review_bridge_manifest.json"
    manifest = _review_manifest(payload, baseline_rows, m1.get("source_image"))
    _write_text_lf(manifest_path, json.dumps(manifest, ensure_ascii=False, indent=2) + "\n")
    review_paths = run_local_review(
        input_path=manifest_path,
        candidate_json=manifest_path,
        candidate_limit=len(manifest["candidates"]),
        out_dir=review_out_dir,
        image_root=DEFAULT_IMAGE_ROOT,
        case_name="task218_ann3741_m_anchor_4_1",
        width=1024,
        height=512,
        coordinate_mode="ls_percent",
        local_server_root=_local_server_root(review_out_dir),
    )
    return {"audit": audit_path, "cards": cards_path, "summary": summary_path, "ledger": ledger_path, "review_manifest": manifest_path, **{f"review_{key}": value for key, value in review_paths.items()}}


if __name__ == "__main__":
    print(run()["audit"])
