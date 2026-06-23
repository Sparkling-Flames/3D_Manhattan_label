"""Rule-based case contract for the expert-side Manhattan hypothesis core."""

from __future__ import annotations

from typing import Any, Mapping, Sequence


SCHEMA_VERSION = "manhattan_case_contract_v1"
LEGACY_SOURCE_FILES = [
    "tools/paper_a_manhattan/manhattan_m1526_adaptive_local_probe.py",
    "tools/paper_a_manhattan/manhattan_m1527_semantic_direct_search.py",
    "tools/paper_a_manhattan/manhattan_m1528_semantic_action_library.py",
]
PRIMARY_RESIDUAL_DEG = 15.0
SECONDARY_RESIDUAL_DEG = 10.0


def _has_contract_metrics(projection_metrics: Mapping[str, Any]) -> bool:
    walls = projection_metrics.get("floorprint", {}).get("walls", [])
    if any(
        row.get("from_pair") is not None
        and row.get("to_pair") is not None
        and isinstance(row.get("angle_residual_deg"), (int, float))
        for row in walls
    ):
        return True
    heights = projection_metrics.get("heights", {}).get("pairs", [])
    if any(
        row.get("effective_pair_index") is not None
        and (
            row.get("suspicious_low_height")
            or row.get("suspicious_high_height")
            or isinstance(row.get("wall_height"), (int, float))
        )
        for row in heights
    ):
        return True
    dense = projection_metrics.get("dense_pairs", {}).get("pairs", [])
    return any(
        row.get("pair_i") is not None
        and row.get("pair_j") is not None
        and row.get("classification") is not None
        for row in dense
    )


def _infer_contract(
    indices: Sequence[int], projection_metrics: Mapping[str, Any]
) -> dict[str, Any]:
    walls = [
        row
        for row in projection_metrics.get("floorprint", {}).get("walls", [])
        if row.get("from_pair") is not None
        and row.get("to_pair") is not None
        and isinstance(row.get("angle_residual_deg"), (int, float))
    ]
    ranked = sorted(walls, key=lambda row: (-float(row["angle_residual_deg"]), int(row["from_pair"])))
    primary = [
        f"{int(row['from_pair'])}-{int(row['to_pair'])}"
        for row in ranked[:1]
        if float(row["angle_residual_deg"]) >= PRIMARY_RESIDUAL_DEG
    ]
    secondary = [
        f"{int(row['from_pair'])}-{int(row['to_pair'])}"
        for row in ranked[1:]
        if float(row["angle_residual_deg"]) >= SECONDARY_RESIDUAL_DEG
    ][:2]
    height_targets = sorted(
        int(row["effective_pair_index"])
        for row in projection_metrics.get("heights", {}).get("pairs", [])
        if row.get("suspicious_low_height") or row.get("suspicious_high_height")
    )
    keep_distinct = sorted(
        [int(row["pair_i"]), int(row["pair_j"])]
        for row in projection_metrics.get("dense_pairs", {}).get("pairs", [])
        if row.get("classification") == "dense_but_distinct_3d_corner"
    )
    positions = {value: position for position, value in enumerate(indices)}
    local: set[int] = set(height_targets)
    for name in [*primary, *secondary]:
        for value in map(int, name.split("-")):
            if value not in positions:
                continue
            position = positions[value]
            local.update(
                {
                    indices[(position - 1) % len(indices)],
                    value,
                    indices[(position + 1) % len(indices)],
                }
            )
    local.update(value for pair in keep_distinct for value in pair)
    movable = {str(index): ["x", "bottom_y"] for index in sorted(local)}
    for index in height_targets:
        movable.setdefault(str(index), [])
        if "top_y" not in movable[str(index)]:
            movable[str(index)].append("top_y")
    return {
        "inferred_primary_edges": primary,
        "inferred_secondary_edges": secondary,
        "inferred_local_window_pairs": sorted(local),
        "inferred_height_target_pairs": height_targets,
        "inferred_keep_distinct_pairs": keep_distinct,
        "inferred_movable_fields_by_pair": movable,
    }


def build_case_contract(
    layout_pairs: Sequence[Mapping[str, Any]],
    expert_assertions: Mapping[str, Any] | None = None,
    projection_metrics: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Build a conservative contract; expert assertions may override defaults."""
    assertions = dict(expert_assertions or {})
    indices = [int(row["effective_pair_index"]) for row in layout_pairs]
    metrics = projection_metrics or {}
    has_metrics = bool(metrics)
    usable_metrics = _has_contract_metrics(metrics) if has_metrics else False
    inferred = _infer_contract(indices, metrics) if indices and usable_metrics else {
        "inferred_primary_edges": [],
        "inferred_secondary_edges": [],
        "inferred_local_window_pairs": [],
        "inferred_height_target_pairs": [],
        "inferred_keep_distinct_pairs": [],
        "inferred_movable_fields_by_pair": {},
    }

    primary = inferred["inferred_primary_edges"] if usable_metrics else []
    secondary = inferred["inferred_secondary_edges"] if usable_metrics else []
    window = inferred["inferred_local_window_pairs"] if usable_metrics else []
    legacy_defaults_used = False

    primary = list(assertions.get("primary_edges", primary))
    secondary = list(
        assertions.get("secondary_edges", assertions.get("secondary_primary_edges", secondary))
    )
    window = list(assertions.get("local_window_pairs", assertions.get("candidate_window", window)))
    do_not_move = sorted({int(value) for value in assertions.get("do_not_move_pairs", [])})
    protected = sorted(
        {int(value) for value in assertions.get("protected_pairs", do_not_move)} | set(do_not_move)
    )
    keep_distinct_source = assertions.get(
        "keep_distinct_pairs", inferred["inferred_keep_distinct_pairs"]
    )
    keep_distinct = [
        [int(pair[0]), int(pair[1])]
        for pair in keep_distinct_source
    ]
    allowed_short = [str(value) for value in assertions.get("allowed_short_edges", [])]
    default_fields = {
        str(index): list(fields)
        for index, fields in inferred["inferred_movable_fields_by_pair"].items()
        if int(index) not in do_not_move
    }
    if assertions.get("candidate_window") or assertions.get("local_window_pairs"):
        default_fields = {
            str(index): ["x", "top_y", "bottom_y"]
            for index in window
            if index not in do_not_move
        }
    for index in assertions.get("allow_secondary_window_pairs", []):
        if int(index) not in do_not_move:
            default_fields[str(int(index))] = list(
                assertions.get("allowed_movable_fields_for_secondary", [])
            )
    movable = {
        str(key): list(value)
        for key, value in assertions.get("movable_fields_by_pair", default_fields).items()
    }
    contract_available = usable_metrics or bool(primary or secondary or window or movable or keep_distinct)
    fail_closed = not contract_available
    return {
        "schema_version": SCHEMA_VERSION,
        "contract_status": "available" if contract_available else "unavailable",
        "expert_review_only": fail_closed,
        "fail_closed": fail_closed,
        "primary_edges": primary,
        "secondary_edges": secondary,
        "local_window_pairs": window,
        "protected_pairs": protected,
        "do_not_move_pairs": do_not_move,
        "keep_distinct_pairs": keep_distinct,
        "allowed_short_edges": allowed_short,
        "movable_fields_by_pair": movable,
        **inferred,
        "auto_contract_summary": {
            "source": (
                "projection_rule_based_v1"
                if usable_metrics
                else "expert_assertion_only"
                if contract_available
                else "contract_unavailable_fail_closed"
            ),
            "legacy_fallback_used": legacy_defaults_used,
            "primary_residual_threshold_deg": PRIMARY_RESIDUAL_DEG,
            "secondary_residual_threshold_deg": SECONDARY_RESIDUAL_DEG,
        },
        "suspected_failure_family": assertions.get("suspected_failure_family", "local_manhattan_residual"),
        "order_override_status": assertions.get("order_override_status", "not_requested"),
        "topology_hypothesis_allowed": bool(assertions.get("topology_hypothesis_allowed", False)),
        "evidence_available_flags": {
            "projection_metrics": bool(metrics),
            "usable_projection_metrics": usable_metrics,
            "hohonet": bool(metrics.get("hohonet_evidence")),
            "expert_assertions": bool(assertions),
        },
        "contract_source": (
            "rule_based_projection_v2"
            if usable_metrics
            else "expert_assertion_only"
            if contract_available
            else "contract_unavailable"
        ),
        "legacy_default_contract": {
            "used": legacy_defaults_used,
            "reason": (
                "legacy defaults disabled; insufficient usable projection metrics"
                if not usable_metrics and not contract_available
                else "legacy default edges are disabled"
            ),
        },
        "legacy_source_files": list(LEGACY_SOURCE_FILES),
        "safety_boundary": {
            "expert_side_only": True,
            "offline_dry_run_only": True,
            "automatic_apply": False,
            "annotation_writeback": False,
            "worker_facing": False,
            "routing_input": False,
            "thesis_protocol_artifact": False,
        },
    }
