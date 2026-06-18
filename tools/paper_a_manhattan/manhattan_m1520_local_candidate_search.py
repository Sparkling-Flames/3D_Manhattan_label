"""M15.20 local-only geometry candidate search.

This is an expert-side, read-only sidecar.  It searches a bounded local window,
never writes annotations, and does not change the M15.19 projection formulas.
"""

from __future__ import annotations

import copy
import math
from typing import Any, Iterable, Mapping, Sequence

from tools.paper_a_manhattan.run_local_3d_projection_review import (
    build_projection_variant,
)


SCHEMA_VERSION = "m15_22_local_joint_candidate_search_v1"
ASSERTION_SCHEMA_VERSION = "m15_21_expert_assertion_v1"
CORE_WINDOW = (5, 6, 7, 8)
EXPANDED_WINDOW = (4, 5, 6, 7, 8, 9)
HEIGHT_PROBE_PAIRS = (5, 6, 7)
REPORT_WALL_EDGES = ((4, 5), (5, 6), (6, 7), (7, 8))
FAMILIES = (
    "column_x_align_translate",
    "height_aware_y_probe",
    "local_order_topology_hypothesis",
    "dense_corner_preservation_joint_xy",
    "joint_6_7_y_depth_balance",
    "joint_6_7_8_synchronized_xy",
    "joint_5_6_7_dense_footprint",
)
COLLAPSE_WALL_LENGTH = 0.10
COLLAPSE_FLOOR_SEPARATION = 0.10
UNRESOLVED_WALL_RESIDUAL_DEG = 15.0

SAFETY_BOUNDARY = {
    "expert_side": True,
    "offline_local_only": True,
    "dry_run_only": True,
    "annotation_write_allowed": False,
    "annotation_patch_generated": False,
    "automatic_global_optimization": False,
    "automatic_apply": False,
    "automatic_merge_delete": False,
    "worker_facing": False,
    "routing_input": False,
    "formal_artifact": False,
}


def normalize_expert_assertions(
    payload: Mapping[str, Any] | None,
    *,
    valid_pair_indices: Iterable[int],
    local_window: Sequence[int],
) -> dict[str, Any] | None:
    if payload is None:
        return None
    if payload.get("schema_version") != ASSERTION_SCHEMA_VERSION:
        raise ValueError(f"assertion schema_version must be {ASSERTION_SCHEMA_VERSION}")
    valid = set(int(value) for value in valid_pair_indices)

    def pair_list(name: str) -> list[int]:
        values = payload.get(name, [])
        if not isinstance(values, list) or any(
            isinstance(value, bool) or not isinstance(value, int) or value not in valid
            for value in values
        ):
            raise ValueError(f"assertion {name} must contain valid pair indices")
        return list(dict.fromkeys(values))

    def edges(name: str) -> list[str]:
        values = payload.get(name, [])
        if not isinstance(values, list):
            raise ValueError(f"assertion {name} must be a list")
        output: list[str] = []
        for value in values:
            try:
                left, right = (int(item) for item in str(value).split("-"))
            except (TypeError, ValueError):
                raise ValueError(f"assertion {name} contains invalid edge {value!r}") from None
            if left not in valid or right not in valid or left == right:
                raise ValueError(f"assertion {name} contains invalid edge {value!r}")
            output.append(f"{left}-{right}")
        return list(dict.fromkeys(output))

    keep_distinct = payload.get("keep_distinct_pairs", [])
    if not isinstance(keep_distinct, list):
        raise ValueError("assertion keep_distinct_pairs must be a list")
    normalized_distinct: list[list[int]] = []
    for pair in keep_distinct:
        if (
            not isinstance(pair, list)
            or len(pair) != 2
            or any(isinstance(value, bool) or not isinstance(value, int) for value in pair)
            or pair[0] == pair[1]
            or not set(pair).issubset(valid)
        ):
            raise ValueError("each keep_distinct_pairs entry must contain two valid distinct indices")
        normalized_distinct.append(pair)
    candidate_window = pair_list("candidate_window")
    if candidate_window and candidate_window != list(local_window):
        raise ValueError("assertion candidate_window must match the configured local window")
    notes = payload.get("notes", [])
    if not isinstance(notes, list) or any(not isinstance(note, str) for note in notes):
        raise ValueError("assertion notes must be a list of strings")
    return {
        "schema_version": ASSERTION_SCHEMA_VERSION,
        "case_name": payload.get("case_name"),
        "keep_distinct_pairs": normalized_distinct,
        "primary_edges": edges("primary_edges"),
        "allowed_short_edges": edges("allowed_short_edges"),
        "do_not_move_pairs": pair_list("do_not_move_pairs"),
        "candidate_window": candidate_window or list(local_window),
        "notes": notes,
    }


def _pair_index(pair: Mapping[str, Any]) -> int:
    return int(pair["effective_pair_index"])


def _pair_lookup(pairs: Sequence[Mapping[str, Any]]) -> dict[int, Mapping[str, Any]]:
    return {_pair_index(pair): pair for pair in pairs}


def _copy_pairs(pairs: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    output = copy.deepcopy(list(pairs))
    for position, pair in enumerate(output, start=1):
        pair.setdefault("effective_pair_index", position)
    return output


def _modify_pair(
    pairs: Sequence[Mapping[str, Any]], pair_index: int, **values: float
) -> list[dict[str, Any]]:
    output = _copy_pairs(pairs)
    target = next(pair for pair in output if _pair_index(pair) == pair_index)
    for field, value in values.items():
        endpoint, axis = field.split("_")
        target[endpoint][axis] = float(value)
    return output


def _candidate(
    family: str,
    label: str,
    pairs: Sequence[Mapping[str, Any]],
    changed_pair_indices: Iterable[int],
    *,
    topology_hypothesis: str | None = None,
) -> dict[str, Any]:
    return {
        "family": family,
        "label": label,
        "ordered_pairs": _copy_pairs(pairs),
        "changed_pair_indices": sorted(set(int(value) for value in changed_pair_indices)),
        "topology_hypothesis": topology_hypothesis,
    }


def generate_local_candidates(
    ordered_pairs: Sequence[Mapping[str, Any]],
    *,
    local_window: Sequence[int] = CORE_WINDOW,
) -> list[dict[str, Any]]:
    """Generate a deterministic bounded candidate set inside ``local_window``."""

    allowed = set(int(value) for value in local_window)
    if not allowed.issubset(set(_pair_lookup(ordered_pairs))):
        raise ValueError("local window contains pair indices absent from the input")
    if not set(CORE_WINDOW).issubset(allowed):
        raise ValueError("local window must contain pairs 5, 6, 7, and 8")

    original = _pair_lookup(ordered_pairs)
    rows: list[dict[str, Any]] = []

    # Family 1: align one top/bottom column, then translate that column locally.
    for pair_index in (5, 6, 7):
        if pair_index not in allowed:
            continue
        pair = original[pair_index]
        aligned = (float(pair["top"]["x"]) + float(pair["bottom"]["x"])) / 2.0
        for dx in (-0.5, -0.25, 0.0, 0.25, 0.5):
            x = aligned + dx
            changed = _modify_pair(
                ordered_pairs, pair_index, top_x=x, bottom_x=x
            )
            rows.append(
                _candidate(
                    "column_x_align_translate",
                    f"pair_{pair_index}_align_dx_{dx:+.2f}",
                    changed,
                    (pair_index,),
                )
            )

    # Family 2: both endpoints always move.  Symmetric patterns adjust height;
    # same-direction patterns probe floor depth while preserving span.
    y_patterns = (
        (-0.5, 0.5),
        (0.5, -0.5),
        (-0.5, -0.5),
        (0.5, 0.5),
        (-1.0, 1.0),
        (1.0, -1.0),
    )
    for pair_index in HEIGHT_PROBE_PAIRS:
        if pair_index not in allowed:
            continue
        pair = original[pair_index]
        for top_dy, bottom_dy in y_patterns:
            changed = _modify_pair(
                ordered_pairs,
                pair_index,
                top_y=float(pair["top"]["y"]) + top_dy,
                bottom_y=float(pair["bottom"]["y"]) + bottom_dy,
            )
            rows.append(
                _candidate(
                    "height_aware_y_probe",
                    f"pair_{pair_index}_top_{top_dy:+.2f}_bottom_{bottom_dy:+.2f}",
                    changed,
                    (pair_index,),
                )
            )

    # Family 3: adjacent local order hypotheses only.  IDs remain attached to
    # their points; nothing is merged or deleted.
    for left, right in ((5, 6), (6, 7), (7, 8)):
        if not {left, right}.issubset(allowed):
            continue
        changed = _copy_pairs(ordered_pairs)
        left_pos = next(i for i, row in enumerate(changed) if _pair_index(row) == left)
        right_pos = next(i for i, row in enumerate(changed) if _pair_index(row) == right)
        changed[left_pos], changed[right_pos] = changed[right_pos], changed[left_pos]
        rows.append(
            _candidate(
                "local_order_topology_hypothesis",
                f"swap_pair_{left}_{right}",
                changed,
                (left, right),
                topology_hypothesis=f"adjacent_order_swap_{left}_{right}",
            )
        )

    # Family 4: retain both dense corners and move 5/6 jointly.  Opposing x
    # shifts preserve/increase their separation; both y endpoints move.
    for separation_dx in (0.15, 0.30, 0.50):
        for y_shift in (-0.5, 0.5):
            changed = _copy_pairs(ordered_pairs)
            lookup = _pair_lookup(changed)
            for pair_index, direction in ((5, -1.0), (6, 1.0)):
                pair = lookup[pair_index]
                pair["top"]["x"] = float(pair["top"]["x"]) + direction * separation_dx
                pair["bottom"]["x"] = float(pair["bottom"]["x"]) + direction * separation_dx
                pair["top"]["y"] = float(pair["top"]["y"]) + y_shift
                pair["bottom"]["y"] = float(pair["bottom"]["y"]) + y_shift
            rows.append(
                _candidate(
                    "dense_corner_preservation_joint_xy",
                    f"pairs_5_6_separate_{separation_dx:.2f}_y_{y_shift:+.2f}",
                    changed,
                    (5, 6),
                )
            )
    return rows


def generate_joint_candidates(
    ordered_pairs: Sequence[Mapping[str, Any]],
    assertions: Mapping[str, Any],
) -> list[dict[str, Any]]:
    """Generate the bounded M15.22 families; pair 8 is a fixed anchor."""

    available = set(_pair_lookup(ordered_pairs))
    if not set(CORE_WINDOW).issubset(available):
        return []
    if not set(CORE_WINDOW).issubset(assertions["candidate_window"]):
        return []
    if {5, 6, 7}.intersection(assertions["do_not_move_pairs"]):
        return []
    rows: list[dict[str, Any]] = []

    for amount in (0.5, 1.0):
        for direction in (-1.0, 1.0):
            changed = _copy_pairs(ordered_pairs)
            lookup = _pair_lookup(changed)
            for pair_index, sign in ((6, direction), (7, -direction)):
                pair = lookup[pair_index]
                pair["top"]["y"] = float(pair["top"]["y"]) + sign * amount
                pair["bottom"]["y"] = float(pair["bottom"]["y"]) - sign * amount
            rows.append(
                _candidate(
                    "joint_6_7_y_depth_balance",
                    f"pairs_6_7_y_balance_{direction * amount:+.2f}",
                    changed,
                    (6, 7),
                )
            )

    for dx, dy in ((0.25, 0.5), (-0.25, -0.5), (0.5, -0.5), (-0.5, 0.5)):
        changed = _copy_pairs(ordered_pairs)
        lookup = _pair_lookup(changed)
        for pair_index, y_sign in ((6, 1.0), (7, -1.0)):
            pair = lookup[pair_index]
            pair["top"]["x"] = float(pair["top"]["x"]) + dx
            pair["bottom"]["x"] = float(pair["bottom"]["x"]) + dx
            pair["top"]["y"] = float(pair["top"]["y"]) + y_sign * dy
            pair["bottom"]["y"] = float(pair["bottom"]["y"]) + y_sign * dy
        rows.append(
            _candidate(
                "joint_6_7_8_synchronized_xy",
                f"pairs_6_7_xy_dx_{dx:+.2f}_dy_{dy:+.2f}_anchor_8",
                changed,
                (6, 7),
            )
        )

    for separation_dx in (0.15, 0.30):
        for depth_shift in (-0.5, 0.5):
            changed = _copy_pairs(ordered_pairs)
            lookup = _pair_lookup(changed)
            for pair_index, x_shift, y_shift in (
                (5, -separation_dx, depth_shift),
                (6, separation_dx, depth_shift),
                (7, separation_dx / 2.0, -depth_shift),
            ):
                pair = lookup[pair_index]
                pair["top"]["x"] = float(pair["top"]["x"]) + x_shift
                pair["bottom"]["x"] = float(pair["bottom"]["x"]) + x_shift
                pair["top"]["y"] = float(pair["top"]["y"]) + y_shift
                pair["bottom"]["y"] = float(pair["bottom"]["y"]) + y_shift
            rows.append(
                _candidate(
                    "joint_5_6_7_dense_footprint",
                    f"pairs_5_6_7_footprint_sep_{separation_dx:.2f}_depth_{depth_shift:+.2f}",
                    changed,
                    (5, 6, 7),
                )
            )
    return rows


def _wall_by_edge(variant: Mapping[str, Any]) -> dict[tuple[int, int], Mapping[str, Any]]:
    return {
        (int(row["from_pair"]), int(row["to_pair"])): row
        for row in variant["metrics"]["floorprint"]["walls"]
    }


def _wall_by_index(variant: Mapping[str, Any]) -> dict[int, Mapping[str, Any]]:
    return {
        int(row["wall_index"]): row
        for row in variant["metrics"]["floorprint"]["walls"]
    }


def _corner_by_pair(variant: Mapping[str, Any]) -> dict[int, Mapping[str, Any]]:
    return {
        int(row["corner_pair_index"]): row
        for row in variant["metrics"]["corner_turns"]["corners"]
    }


def _height_by_pair(variant: Mapping[str, Any]) -> dict[int, Mapping[str, Any]]:
    return {
        int(row["effective_pair_index"]): row
        for row in variant["metrics"]["heights"]["pairs"]
    }


def _dense_relation(
    variant: Mapping[str, Any], left: int, right: int
) -> Mapping[str, Any] | None:
    for row in variant["metrics"]["dense_pairs"]["pairs"]:
        if {int(row["pair_i"]), int(row["pair_j"])} == {left, right}:
            return row
    return None


def _sum(values: Iterable[Any]) -> float:
    return sum(float(value) for value in values if value is not None)


def _movement(
    before_pairs: Sequence[Mapping[str, Any]],
    after_pairs: Sequence[Mapping[str, Any]],
    report_pair_indices: Iterable[int],
) -> tuple[float, list[dict[str, Any]]]:
    before = _pair_lookup(before_pairs)
    after = _pair_lookup(after_pairs)
    report_pairs = set(int(value) for value in report_pair_indices)
    total = 0.0
    changes: list[dict[str, Any]] = []
    for pair_index in sorted(before):
        fields: dict[str, dict[str, float]] = {}
        for endpoint in ("top", "bottom"):
            for axis in ("x", "y"):
                old = float(before[pair_index][endpoint][axis])
                new = float(after[pair_index][endpoint][axis])
                changed = not math.isclose(old, new, abs_tol=1e-12)
                if changed:
                    total += abs(new - old)
                if pair_index in report_pairs:
                    fields[f"{endpoint}_{axis}"] = {
                        "before": old,
                        "after": new,
                        "delta": new - old,
                        "changed": changed,
                    }
        if fields:
            changes.append({"effective_pair_index": pair_index, "fields": fields})
    return total, changes


def _projected_coordinates(variant: Mapping[str, Any], pair_indices: Iterable[int]) -> list[dict[str, Any]]:
    wanted = set(pair_indices)
    return [
        {
            "effective_pair_index": int(row["effective_pair_index"]),
            "floor_3d": copy.deepcopy(row["floor_3d"]),
            "ceiling_3d": copy.deepcopy(row["ceiling_3d"]),
            "wall_height": float(row["wall_height"]),
        }
        for row in variant["projection"]["pairs"]
        if int(row["effective_pair_index"]) in wanted
    ]


def evaluate_candidate(
    baseline: Mapping[str, Any],
    raw_candidate: Mapping[str, Any],
    *,
    width: int,
    height: int,
    camera_height: float,
    coordinate_mode: str,
) -> dict[str, Any]:
    variant = build_projection_variant(
        raw_candidate["label"],
        raw_candidate["ordered_pairs"],
        width=width,
        height=height,
        coordinate_mode=coordinate_mode,
        camera_height=camera_height,
    )
    baseline_walls = _wall_by_index(baseline)
    candidate_walls = _wall_by_index(variant)
    # These positions are exactly the report contract: 4-5, 5-6, 6-7, 7-8
    # in the baseline order.  Topology hypotheses retain positional scoring
    # while the edge table makes any changed/missing adjacency explicit.
    local_wall_indices = (4, 5, 6, 7)
    wall_before = _sum(baseline_walls[i]["angle_residual_deg"] for i in local_wall_indices)
    wall_after = _sum(candidate_walls[i]["angle_residual_deg"] for i in local_wall_indices)

    baseline_corners = _corner_by_pair(baseline)
    candidate_corners = _corner_by_pair(variant)
    corner_before = _sum(baseline_corners[i]["angle_to_90_residual_deg"] for i in CORE_WINDOW)
    corner_after = _sum(candidate_corners[i]["angle_to_90_residual_deg"] for i in CORE_WINDOW)

    baseline_heights = _height_by_pair(baseline)
    candidate_heights = _height_by_pair(variant)
    height_before = _sum(abs(baseline_heights[i]["local_height_residual"]) for i in HEIGHT_PROBE_PAIRS)
    height_after = _sum(abs(candidate_heights[i]["local_height_residual"]) for i in HEIGHT_PROBE_PAIRS)

    minimum_before = min(float(baseline_walls[i]["floor_wall_length"]) for i in local_wall_indices)
    minimum_after = min(float(candidate_walls[i]["floor_wall_length"]) for i in local_wall_indices)

    required_walls = []
    before_edges = _wall_by_edge(baseline)
    after_edges = _wall_by_edge(variant)
    edge_missing_after: list[str] = []
    all_unresolved: list[str] = []
    primary_unresolved: list[str] = []
    short_wall_edges_before: list[str] = []
    short_wall_edges_after: list[str] = []
    short_penalty_before = 0.0
    short_penalty_after = 0.0
    for edge in REPORT_WALL_EDGES:
        edge_name = f"{edge[0]}-{edge[1]}"
        before_row = before_edges.get(edge)
        after_row = after_edges.get(edge)
        after_residual = float(after_row["angle_residual_deg"]) if after_row else None
        missing = after_row is None
        unresolved = missing or after_residual > UNRESOLVED_WALL_RESIDUAL_DEG
        if missing:
            edge_missing_after.append(edge_name)
        if unresolved:
            all_unresolved.append(edge_name)
            if edge == (6, 7):
                primary_unresolved.append(edge_name)
        if before_row and bool(before_row["short_wall"]):
            short_wall_edges_before.append(edge_name)
            short_penalty_before += max(
                0.0,
                float(before_row["short_wall_threshold"])
                - float(before_row["floor_wall_length"]),
            )
        if after_row and bool(after_row["short_wall"]):
            short_wall_edges_after.append(edge_name)
            short_penalty_after += max(
                0.0,
                float(after_row["short_wall_threshold"])
                - float(after_row["floor_wall_length"]),
            )
        required_walls.append(
            {
                "edge": edge_name,
                "before_residual_deg": float(before_row["angle_residual_deg"]) if before_row else None,
                "after_residual_deg": after_residual,
                "delta_deg": (
                    after_residual - float(before_row["angle_residual_deg"])
                    if before_row and after_residual is not None
                    else None
                ),
                "edge_present_after": not missing,
                "edge_missing_after": missing,
                "before_floor_wall_length": float(before_row["floor_wall_length"]) if before_row else None,
                "after_floor_wall_length": float(after_row["floor_wall_length"]) if after_row else None,
                "before_short_wall": bool(before_row["short_wall"]) if before_row else None,
                "short_wall": bool(after_row["short_wall"]) if after_row else None,
                "before_short_wall_threshold": float(before_row["short_wall_threshold"]) if before_row else None,
                "short_wall_threshold": float(after_row["short_wall_threshold"]) if after_row else None,
                "below_dynamic_short_threshold": bool(after_row["short_wall"]) if after_row else None,
            }
        )
    short_wall_worsened = (
        not set(short_wall_edges_after).issubset(short_wall_edges_before)
        or short_penalty_after > short_penalty_before + 1e-9
    )
    below_dynamic_short_threshold = bool(short_wall_edges_after)
    short_wall_preservation_explanation = (
        "pre-existing dynamic short-wall risk preserved without increased deficit"
        if below_dynamic_short_threshold and not short_wall_worsened
        else None
    )

    dense_before = _dense_relation(baseline, 5, 6)
    dense_after = _dense_relation(variant, 5, 6)
    assert dense_before is not None and dense_after is not None
    dense_floor_loss = max(
        0.0,
        float(dense_before["floor_3d_separation"])
        - float(dense_after["floor_3d_separation"]),
    )
    dense_x_loss = max(
        0.0,
        float(dense_before["center_x_separation_percent"])
        - float(dense_after["center_x_separation_percent"]),
    )
    movement, coordinate_changes = _movement(
        baseline["ordered_pairs"],
        raw_candidate["ordered_pairs"],
        raw_candidate["changed_pair_indices"],
    )

    self_intersection_before = bool(baseline["metrics"]["floorprint"]["self_intersection"])
    self_intersection_after = bool(variant["metrics"]["floorprint"]["self_intersection"])
    collapse_edges: list[str] = []
    edge_lookup = _wall_by_edge(variant)
    for left, right in ((5, 6), (6, 7)):
        wall = edge_lookup.get((left, right)) or edge_lookup.get((right, left))
        relation = _dense_relation(variant, left, right)
        if wall is not None and float(wall["floor_wall_length"]) < COLLAPSE_WALL_LENGTH:
            collapse_edges.append(f"{left}-{right}:short_wall")
        if relation is not None and float(relation["floor_3d_separation"]) < COLLAPSE_FLOOR_SEPARATION:
            collapse_edges.append(f"{left}-{right}:floor_separation")

    hard_gate_reasons: list[str] = []
    if self_intersection_after and not self_intersection_before:
        hard_gate_reasons.append("introduced_self_intersection")
    if collapse_edges:
        hard_gate_reasons.append("local_5_6_7_collapse_risk")

    components = {
        "window_wall_residual": {"before": wall_before, "after": wall_after, "delta": wall_after - wall_before},
        "window_corner_residual": {"before": corner_before, "after": corner_after, "delta": corner_after - corner_before},
        "height_residual": {"before": height_before, "after": height_after, "delta": height_after - height_before},
        "minimum_wall_length": {"before": minimum_before, "after": minimum_after, "delta": minimum_after - minimum_before},
        "minimum_wall_length_penalty": {"before": short_penalty_before, "after": short_penalty_after, "delta": short_penalty_after - short_penalty_before},
        "dense_separation_preservation": {
            "floor_3d_before": float(dense_before["floor_3d_separation"]),
            "floor_3d_after": float(dense_after["floor_3d_separation"]),
            "center_x_percent_before": float(dense_before["center_x_separation_percent"]),
            "center_x_percent_after": float(dense_after["center_x_separation_percent"]),
            "loss_penalty": dense_floor_loss + dense_x_loss,
        },
        "movement_l1_ls_percent": movement,
    }
    score = (
        components["window_wall_residual"]["delta"]
        + 0.5 * components["window_corner_residual"]["delta"]
        + 10.0 * components["height_residual"]["delta"]
        + 30.0 * components["minimum_wall_length_penalty"]["delta"]
        + 20.0 * components["dense_separation_preservation"]["loss_penalty"]
        + 0.25 * movement
    )

    if hard_gate_reasons:
        disposition = "suppressed_hard_risk"
        recommend = False
    elif raw_candidate["family"] == "local_order_topology_hypothesis":
        disposition = "neutral_review_topology_hypothesis"
        recommend = False
    elif (
        edge_missing_after
        or all_unresolved
        or short_wall_worsened
        or (below_dynamic_short_threshold and not short_wall_preservation_explanation)
    ):
        disposition = "partial_neutral_review"
        recommend = False
    elif score < -0.01:
        disposition = "suggested_manual_ls_try"
        recommend = True
    else:
        disposition = "neutral_review"
        recommend = False

    changed = raw_candidate["changed_pair_indices"]
    result = {
        "family": raw_candidate["family"],
        "label": raw_candidate["label"],
        "changed_pair_indices": changed,
        "topology_hypothesis": raw_candidate.get("topology_hypothesis"),
        "score": score,
        "score_lower_is_better": True,
        "score_components": components,
        "hard_gate": bool(hard_gate_reasons),
        "hard_gate_reasons": hard_gate_reasons,
        "collapse_risk_details": collapse_edges,
        "edge_missing_after": edge_missing_after,
        "primary_unresolved_edges": primary_unresolved,
        "all_unresolved_required_edges": all_unresolved,
        "unresolved_required_edges": all_unresolved,
        "disposition": disposition,
        "manual_ls_try_recommended": recommend,
        "height_worsened": components["height_residual"]["delta"] > 1e-9,
        "short_wall_after": below_dynamic_short_threshold,
        "short_wall_edges_after": short_wall_edges_after,
        "short_wall_worsened": short_wall_worsened,
        "below_dynamic_short_threshold": below_dynamic_short_threshold,
        "short_wall_preservation_explanation": short_wall_preservation_explanation,
        "self_intersection": {"before": self_intersection_before, "after": self_intersection_after},
        "coordinate_changes": coordinate_changes,
        "coordinates_3d": {
            "original": _projected_coordinates(baseline, changed),
            "candidate": _projected_coordinates(variant, changed),
        },
        "required_wall_residuals": required_walls,
        "ordered_pair_indices_after": [_pair_index(row) for row in raw_candidate["ordered_pairs"]],
    }
    result.update(_candidate_triage(result))
    return result


def _candidate_triage(candidate: Mapping[str, Any]) -> dict[str, Any]:
    improvement_rows: list[tuple[float, str]] = []
    fails: list[str] = []
    for wall in candidate["required_wall_residuals"]:
        before = wall["before_residual_deg"]
        after = wall["after_residual_deg"]
        if before is not None and after is not None and after < before - 0.01:
            improvement_rows.append(
                (before - after, f"{wall['edge']} residual improves {before:.3f} -> {after:.3f}")
            )
    improves = [text for _, text in sorted(improvement_rows, reverse=True)]
    if candidate["score_components"]["height_residual"]["delta"] < -0.01:
        improves.append("local height residual improves")

    for wall in candidate["required_wall_residuals"]:
        if wall["edge_missing_after"]:
            fails.append(f"{wall['edge']} is missing after candidate")
        elif wall["edge"] in candidate["all_unresolved_required_edges"]:
            fails.append(
                f"{wall['edge']} remains unresolved: "
                f"{wall['before_residual_deg']:.3f} -> {wall['after_residual_deg']:.3f}"
            )
    allowed_short = set(candidate.get("assertion_allowed_short_wall_edges", []))
    allowed_existing = [
        edge for edge in candidate["short_wall_edges_after"] if edge in allowed_short
    ]
    unallowed_short = [
        edge for edge in candidate["short_wall_edges_after"] if edge not in allowed_short
    ]
    if allowed_existing:
        fails.append(
            "allowed existing short-wall risk remains at "
            + " and ".join(allowed_existing)
            + "; allowance is not a correctness claim"
        )
    if unallowed_short:
        fails.append(
            "dynamic short-wall risk remains at "
            + " and ".join(unallowed_short)
        )
    if candidate["short_wall_worsened"]:
        fails.append("dynamic short-wall risk worsens")
    if candidate["height_worsened"]:
        fails.append("local height residual worsens")

    blocked = bool(
        candidate["hard_gate"]
        or candidate["edge_missing_after"]
        or candidate.get("assertion_violations")
    )
    preserved_short_wall_only = bool(
        candidate["below_dynamic_short_threshold"]
        and candidate["short_wall_preservation_explanation"]
        and not candidate["short_wall_worsened"]
    )
    clean_for_review = (
        not blocked
        and not candidate["all_unresolved_required_edges"]
        and not candidate["short_wall_worsened"]
        and not preserved_short_wall_only
        and candidate["family"] != "local_order_topology_hypothesis"
    )
    score_improves = float(candidate["score"]) < -0.01
    if blocked:
        decision_class = "blocked"
    elif clean_for_review:
        decision_class = "candidate_for_manual_review"
    elif (
        candidate["short_wall_worsened"]
        or preserved_short_wall_only
        or (score_improves and candidate["all_unresolved_required_edges"])
    ):
        decision_class = "partial_diagnostic"
    else:
        decision_class = "neutral_diagnostic"

    direct_ls_trial_allowed = bool(
        decision_class == "candidate_for_manual_review"
        and candidate["manual_ls_try_recommended"]
    )
    asserted_primary = candidate.get("assertion_primary_edges", [])
    unresolved_primary = [
        edge for edge in asserted_primary if edge in candidate["all_unresolved_required_edges"]
    ]
    if unresolved_primary:
        next_check = (
            "Inspect asserted primary edge "
            + ", ".join(unresolved_primary)
            + " before considering direct LS application."
        )
    elif "6-7" in candidate["all_unresolved_required_edges"]:
        next_check = "Inspect the 6-7-8 window before considering direct LS application."
    elif candidate["all_unresolved_required_edges"]:
        next_check = (
            "Inspect unresolved local edges "
            + ", ".join(candidate["all_unresolved_required_edges"])
            + " before any LS trial."
        )
    elif candidate["short_wall_edges_after"]:
        next_check = "Inspect dynamic short-wall geometry before any LS trial."
    else:
        next_check = "Perform expert visual review before any LS trial."
    summary = (
        f"{decision_class}: "
        + (improves[0] if improves else "no clear local improvement")
        + (f"; {fails[0]}" if fails else "; no required-edge blocker detected")
        + "."
    )
    return {
        "decision_class": decision_class,
        "improves": improves,
        "fails_because": fails,
        "next_expert_check": next_check,
        "direct_ls_trial_allowed": direct_ls_trial_allowed,
        "triage_summary": summary,
    }


def _apply_expert_assertions(
    candidate: dict[str, Any], assertions: Mapping[str, Any]
) -> None:
    violations: list[str] = []
    effects: list[str] = []
    changed = set(candidate["changed_pair_indices"])
    forbidden = changed.intersection(assertions["do_not_move_pairs"])
    if forbidden:
        violations.append("moves do-not-move pairs: " + ", ".join(map(str, sorted(forbidden))))
    outside = changed.difference(assertions["candidate_window"])
    if outside:
        violations.append("moves pairs outside candidate_window: " + ", ".join(map(str, sorted(outside))))
    for left, right in assertions["keep_distinct_pairs"]:
        edge = f"{left}-{right}"
        effects.append(f"keep {edge} distinct; merge/delete/topology collapse prohibited")
        if any(detail.startswith(edge + ":") for detail in candidate["collapse_risk_details"]):
            violations.append(f"violates keep_distinct_pairs at {edge}")
    allowed_existing = [
        edge
        for edge in candidate["short_wall_edges_after"]
        if edge in assertions["allowed_short_edges"]
    ]
    if allowed_existing:
        effects.append(
            "allowed existing short-wall risk (still risky): "
            + ", ".join(allowed_existing)
        )
    allowed_short_worsened: list[str] = []
    for wall in candidate["required_wall_residuals"]:
        if wall["edge"] not in assertions["allowed_short_edges"]:
            continue
        if wall["after_floor_wall_length"] is None or wall["short_wall_threshold"] is None:
            continue
        before_deficit = max(
            0.0,
            float(wall["before_short_wall_threshold"])
            - float(wall["before_floor_wall_length"]),
        )
        after_deficit = max(
            0.0,
            float(wall["short_wall_threshold"])
            - float(wall["after_floor_wall_length"]),
        )
        if after_deficit > before_deficit + 1e-9:
            allowed_short_worsened.append(wall["edge"])
    if allowed_short_worsened:
        violations.append(
            "worsens allowed existing short-wall edges: "
            + ", ".join(allowed_short_worsened)
        )
    if assertions["primary_edges"]:
        effects.append("primary edge focus: " + ", ".join(assertions["primary_edges"]))
    primary_edge_improvements = [
        wall["edge"]
        for wall in candidate["required_wall_residuals"]
        if wall["edge"] in assertions["primary_edges"]
        and wall["after_residual_deg"] is not None
        and wall["before_residual_deg"] is not None
        and wall["after_residual_deg"] < wall["before_residual_deg"] - 0.01
    ]
    baseline_unresolved = {
        wall["edge"]
        for wall in candidate["required_wall_residuals"]
        if wall["before_residual_deg"] is None
        or wall["before_residual_deg"] > UNRESOLVED_WALL_RESIDUAL_DEG
    }
    new_unresolved = [
        edge
        for edge in candidate["all_unresolved_required_edges"]
        if edge not in baseline_unresolved
    ]
    candidate.update(
        {
            "assertion_violations": violations,
            "assertion_compliant": not violations,
            "assertion_effects": effects,
            "assertion_primary_edges": list(assertions["primary_edges"]),
            "assertion_allowed_short_wall_edges": allowed_existing,
            "primary_edge_improved": primary_edge_improvements,
            "allowed_short_wall_worsened": allowed_short_worsened,
            "new_unresolved_edges": new_unresolved,
        }
    )
    if violations:
        candidate["manual_ls_try_recommended"] = False
        candidate["disposition"] = "suppressed_assertion_violation"
    candidate.update(_candidate_triage(candidate))


def _candidate_ranking_key(candidate: Mapping[str, Any]) -> tuple[Any, ...]:
    blocked = bool(
        candidate.get("hard_gate")
        or candidate.get("assertion_violations")
        or candidate.get("decision_class") == "blocked"
        or candidate.get("disposition") == "suppressed_assertion_violation"
    )
    bucket = 3 if blocked else {
        "candidate_for_manual_review": 0,
        "partial_diagnostic": 1,
        "neutral_diagnostic": 2,
    }.get(candidate.get("decision_class"), 2)
    return bucket, float(candidate["score"]), candidate["family"], candidate["label"]


def _retain_candidates_per_family(
    evaluated: Sequence[dict[str, Any]], retain_per_family: int
) -> tuple[list[dict[str, Any]], dict[str, int]]:
    retained: list[dict[str, Any]] = []
    counts: dict[str, int] = {}
    for family in FAMILIES:
        family_rows = [row for row in evaluated if row["family"] == family]
        counts[family] = len(family_rows)
        family_rows.sort(key=_candidate_ranking_key)
        retained.extend(family_rows[: max(1, retain_per_family)])
    return retained, counts


def run_local_candidate_search(
    ordered_pairs: Sequence[Mapping[str, Any]],
    *,
    width: int = 1024,
    height: int = 512,
    camera_height: float = 1.6,
    coordinate_mode: str = "ls_percent",
    local_window: Sequence[int] = CORE_WINDOW,
    retain_per_family: int = 3,
    expert_assertions: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    if coordinate_mode != "ls_percent":
        raise ValueError("M15.20 requires explicit coordinate_mode='ls_percent'")
    baseline_pairs = _copy_pairs(ordered_pairs)
    assertions = normalize_expert_assertions(
        expert_assertions,
        valid_pair_indices=_pair_lookup(baseline_pairs),
        local_window=local_window,
    )
    baseline = build_projection_variant(
        "original",
        baseline_pairs,
        width=width,
        height=height,
        coordinate_mode=coordinate_mode,
        camera_height=camera_height,
    )
    generated = generate_local_candidates(baseline_pairs, local_window=local_window)
    joint_generated: list[dict[str, Any]] = []
    if assertions:
        joint_generated = generate_joint_candidates(baseline_pairs, assertions)
        generated.extend(joint_generated)
    evaluated = [
        evaluate_candidate(
            baseline,
            row,
            width=width,
            height=height,
            camera_height=camera_height,
            coordinate_mode=coordinate_mode,
        )
        for row in generated
    ]
    if assertions:
        for row in evaluated:
            _apply_expert_assertions(row, assertions)
    retained, counts = _retain_candidates_per_family(evaluated, retain_per_family)
    executable = [
        row for row in retained if row["family"] != "local_order_topology_hypothesis"
    ]
    topology = [
        row for row in retained if row["family"] == "local_order_topology_hypothesis"
    ]
    executable.sort(key=_candidate_ranking_key)
    topology.sort(key=_candidate_ranking_key)
    for rank, row in enumerate(executable, start=1):
        row["candidate_rank"] = rank
        row["candidate_id"] = f"candidate_{rank}"
    for rank, row in enumerate(topology, start=1):
        row["topology_rank"] = rank
        row["candidate_id"] = f"topology_{rank}"
    best = executable[0] if executable else None
    case_triage = {
        "direct_fix_available": False,
        "best_executable_candidate_id": best["candidate_id"] if best else None,
        "best_executable_decision_class": best["decision_class"] if best else None,
        "primary_unresolved_edges": (
            [
                edge
                for edge in assertions["primary_edges"]
                if best and edge in best["all_unresolved_required_edges"]
            ]
            if assertions
            else (best["primary_unresolved_edges"] if best else [])
        ),
        "persistent_short_wall_edges": best["short_wall_edges_after"] if best else [],
        "recommended_next_step": (
            "Inspect asserted primary edge "
            + ", ".join(assertions["primary_edges"])
            + "; do not apply directly in LS."
            if best and assertions and assertions["primary_edges"]
            else "Continue with local joint search or expert assertion workflow; do not apply directly in LS."
            if best
            else "No executable candidate is available for review."
        ),
    }
    return {
        "schema_version": SCHEMA_VERSION,
        "scope": {
            "case_specific": assertions.get("case_name") if assertions else None,
            "local_window": list(local_window),
            "core_window": list(CORE_WINDOW),
            "height_probe_pairs": list(HEIGHT_PROBE_PAIRS),
            "global_optimization": False,
        },
        "projection_config": {
            "width": width,
            "height": height,
            "camera_height": camera_height,
            "coordinate_mode": coordinate_mode,
        },
        "safety_boundary": dict(SAFETY_BOUNDARY),
        "expert_assertions_used": assertions,
        "assertion_effects": {
            "candidate_generation_changed": bool(joint_generated),
            "joint_candidate_count": len(joint_generated),
            "gate_and_explanation_only": False,
            "violating_candidate_ids": [
                row["candidate_id"]
                for row in [*executable, *topology]
                if row.get("assertion_violations")
            ],
        },
        "case_triage": case_triage,
        "score_contract": {
            "lower_is_better": True,
            "weights": {
                "window_wall_residual_delta": 1.0,
                "window_corner_residual_delta": 0.5,
                "height_residual_delta": 10.0,
                "minimum_wall_length_penalty_delta": 30.0,
                "dense_separation_loss": 20.0,
                "movement_l1_ls_percent": 0.25,
            },
            "hard_gates": ["introduced_self_intersection", "local_5_6_7_collapse_risk"],
            "short_wall_semantics": "M15.19 floorprint wall.short_wall and wall.short_wall_threshold",
            "final_fix_authorized": False,
        },
        "baseline": {
            "ordered_pair_indices": [_pair_index(row) for row in baseline_pairs],
            "required_wall_residuals": [
                {
                    "edge": f"{left}-{right}",
                    "residual_deg": float(_wall_by_edge(baseline)[(left, right)]["angle_residual_deg"]),
                    "floor_wall_length": float(_wall_by_edge(baseline)[(left, right)]["floor_wall_length"]),
                    "short_wall": bool(_wall_by_edge(baseline)[(left, right)]["short_wall"]),
                    "short_wall_threshold": float(_wall_by_edge(baseline)[(left, right)]["short_wall_threshold"]),
                }
                for left, right in REPORT_WALL_EDGES
            ],
        },
        "candidate_generation": {
            "generated_count": len(generated),
            "generated_count_by_family": counts,
            "retained_per_family": max(1, retain_per_family),
            "retained_count": len(executable) + len(topology),
            "executable_retained_count": len(executable),
            "topology_retained_count": len(topology),
        },
        "candidates": executable,
        "topology_hypotheses": topology,
    }
