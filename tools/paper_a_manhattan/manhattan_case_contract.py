"""Rule-based case contract for the expert-side Manhattan hypothesis core."""

from __future__ import annotations

from typing import Any, Mapping, Sequence


SCHEMA_VERSION = "manhattan_case_contract_v1"
LEGACY_SOURCE_FILES = [
    "tools/paper_a_manhattan/manhattan_m1526_adaptive_local_probe.py",
    "tools/paper_a_manhattan/manhattan_m1527_semantic_direct_search.py",
    "tools/paper_a_manhattan/manhattan_m1528_semantic_action_library.py",
]


def build_case_contract(
    layout_pairs: Sequence[Mapping[str, Any]],
    expert_assertions: Mapping[str, Any] | None = None,
    projection_metrics: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Build a conservative contract; expert assertions may override defaults."""
    assertions = dict(expert_assertions or {})
    indices = [int(row["effective_pair_index"]) for row in layout_pairs]
    available = set(indices)

    def edge(left: int, right: int) -> str | None:
        return f"{left}-{right}" if {left, right} <= available else None

    primary = [value for value in (edge(6, 7),) if value]
    secondary = [value for value in (edge(2, 3),) if value]
    window = [value for value in (5, 6, 7, 8) if value in available]
    legacy_defaults_used = bool(primary or secondary or window)

    primary = list(assertions.get("primary_edges", primary))
    secondary = list(
        assertions.get("secondary_edges", assertions.get("secondary_primary_edges", secondary))
    )
    window = list(assertions.get("local_window_pairs", assertions.get("candidate_window", window)))
    do_not_move = sorted({int(value) for value in assertions.get("do_not_move_pairs", [])})
    protected = sorted(
        {int(value) for value in assertions.get("protected_pairs", do_not_move)} | set(do_not_move)
    )
    keep_distinct = [
        [int(pair[0]), int(pair[1])]
        for pair in assertions.get("keep_distinct_pairs", [])
    ]
    allowed_short = [str(value) for value in assertions.get("allowed_short_edges", [])]
    default_fields = {str(index): ["x", "top_y", "bottom_y"] for index in window if index not in do_not_move}
    for index in assertions.get("allow_secondary_window_pairs", []):
        if int(index) not in do_not_move:
            default_fields[str(int(index))] = list(
                assertions.get("allowed_movable_fields_for_secondary", [])
            )
    movable = {
        str(key): list(value)
        for key, value in assertions.get("movable_fields_by_pair", default_fields).items()
    }
    metrics = projection_metrics or {}
    return {
        "schema_version": SCHEMA_VERSION,
        "primary_edges": primary,
        "secondary_edges": secondary,
        "local_window_pairs": window,
        "protected_pairs": protected,
        "do_not_move_pairs": do_not_move,
        "keep_distinct_pairs": keep_distinct,
        "allowed_short_edges": allowed_short,
        "movable_fields_by_pair": movable,
        "suspected_failure_family": assertions.get("suspected_failure_family", "local_manhattan_residual"),
        "order_override_status": assertions.get("order_override_status", "not_requested"),
        "topology_hypothesis_allowed": bool(assertions.get("topology_hypothesis_allowed", False)),
        "evidence_available_flags": {
            "projection_metrics": bool(metrics),
            "hohonet": bool(metrics.get("hohonet_evidence")),
            "expert_assertions": bool(assertions),
        },
        "contract_source": "rule_based_v1",
        "legacy_default_contract": {
            "used": legacy_defaults_used,
            "reason": (
                "v1 compatibility defaults mirror the legacy 6-7, 2-3, and 5-6-7-8 scope; "
                "they are case defaults, not global geometry truth"
                if legacy_defaults_used
                else "legacy default edges are unavailable in this layout"
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
