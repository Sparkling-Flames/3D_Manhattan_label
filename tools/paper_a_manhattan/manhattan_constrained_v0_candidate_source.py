"""Shadow-only constrained_v0 source with one bounded column-x family."""

from __future__ import annotations

from typing import Any, Mapping, Sequence

from tools.paper_a_manhattan.manhattan_candidate_source_interface import (
    OUTPUT_SCHEMA_VERSION,
    validate_candidate_source,
)


SOURCE_VERSION = "hrc_c3_2_constrained_v0_source_contract_v1"
CONTRACT_PATH = "docs/paper_a_manhattan/HRC_C3_2_CONSTRAINED_V0_SOURCE_CONTRACT_v1.md"


def _base_payload(case_contract: Mapping[str, Any], *, status: str) -> dict[str, Any]:
    return {
        "source_id": "constrained_v0",
        "source_type": "constrained_v0_candidate_source",
        "source_version": SOURCE_VERSION,
        "generator_role": "shadow_constrained_generator",
        "candidate_generation_allowed": status != "skeleton_only",
        "candidate_count": 0,
        "candidate_set": [],
        "case_contract": dict(case_contract),
        "source_provenance": {
            "contract_doc_path": CONTRACT_PATH,
            "implementation_status": status,
            "active_runner_role": False,
        },
        "source_limitations": [
            "shadow only",
            "only column_x_alignment is implemented",
            "no active selection role",
            "no accepted recommendation",
        ],
        "output_schema_version": OUTPUT_SCHEMA_VERSION,
        "no_new_candidate_strategy_introduced": status == "skeleton_only",
        "constrained_v0_implementation_status": status,
        "accepted": False,
        "downstream_recommendation": False,
    }


def build_constrained_v0_shadow_source(
    case_contract: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    payload = _base_payload(case_contract or {}, status="skeleton_only")
    payload["source_limitations"] = [
        "skeleton only",
        "no candidate families implemented",
        "no coordinate changes emitted",
        "no active selection role",
    ]
    validate_candidate_source(payload)
    return payload


def build_column_x_alignment_shadow_source(
    ordered_pairs: Sequence[Mapping[str, Any]],
    case_contract: Mapping[str, Any],
    evidence_summary: Mapping[str, Any] | None,
    projection_config: Mapping[str, Any],
) -> dict[str, Any]:
    payload = _base_payload(case_contract, status="column_x_alignment_shadow_only")
    unavailable: list[str] = []
    evidence = dict(evidence_summary or {})
    if evidence.get("evidence_status") != "available":
        unavailable.append("evidence_unavailable")
    if evidence.get("visual_conflict_flags"):
        unavailable.append("evidence_conflict")
    if evidence.get("column_identity_status") == "conflict":
        unavailable.append("column_identity_conflict")
    if evidence.get("seam_ambiguity"):
        unavailable.append("seam_ambiguity")
    required_projection = {"coordinate_mode", "width", "height"}
    if not projection_config or required_projection.difference(projection_config):
        unavailable.append("projection_config_missing")
    else:
        try:
            if not str(projection_config["coordinate_mode"]) or float(projection_config["width"]) <= 0 or float(projection_config["height"]) <= 0:
                unavailable.append("projection_config_invalid")
        except (TypeError, ValueError):
            unavailable.append("projection_config_invalid")
    if unavailable:
        payload["unavailable_summary"] = {"reasons": unavailable, "eligible_pair_count": 0}
        validate_candidate_source(payload)
        return payload

    protected = {int(value) for value in case_contract.get("protected_pairs", [])}
    movable = {
        int(index): set(fields)
        for index, fields in case_contract.get("movable_fields_by_pair", {}).items()
    }
    keep_distinct = [tuple(map(int, pair)) for pair in case_contract.get("keep_distinct_pairs", [])]
    seam_pairs = {int(value) for value in evidence.get("seam_ambiguous_pairs", [])}
    conflict_pairs = {int(value) for value in evidence.get("column_identity_conflicts", [])}
    dense_pairs = {int(value) for value in evidence.get("dense_pair_indices", [])}
    identity_by_pair = {
        int(index): status
        for index, status in evidence.get("column_identity_by_pair", {}).items()
    }
    default_margin_used = not any(
        key in case_contract for key in ("keep_distinct_margin_min", "min_column_separation")
    )
    separation_margin = float(
        case_contract.get(
            "keep_distinct_margin_min",
            case_contract.get("min_column_separation", 0.25),
        )
    )
    seam_margin = float(evidence.get("seam_margin", case_contract.get("seam_margin", 0.5)))
    seam_safe = bool(evidence.get("seam_safe", case_contract.get("seam_safe", False)))
    coordinate_upper = (
        100.0
        if "percent" in str(projection_config["coordinate_mode"]).lower()
        else float(projection_config["width"])
    )
    payload["source_provenance"].update(
        {
            "column_separation_margin": separation_margin,
            "default_margin_used": default_margin_used,
            "seam_margin": seam_margin,
        }
    )
    pair_lookup: dict[int, Mapping[str, Any]] = {}
    centers: dict[int, float] = {}
    for row in ordered_pairs:
        try:
            index = int(row["effective_pair_index"])
            centers[index] = (float(row["top"]["x"]) + float(row["bottom"]["x"])) / 2.0
            pair_lookup[index] = row
        except (KeyError, TypeError, ValueError):
            unavailable.append("missing_required_pair_fields")

    candidates = []
    for index, row in pair_lookup.items():
        reasons = []
        allowed = movable.get(index, set())
        if "x" not in allowed and not {"top_x", "bottom_x"}.issubset(allowed):
            reasons.append("x_permission_missing")
        if index in protected:
            reasons.append("protected_pair_mutation")
        if index in seam_pairs:
            reasons.append("seam_ambiguity")
        if index in conflict_pairs:
            reasons.append("column_identity_conflict")
        identity_status = identity_by_pair.get(index, evidence.get("column_identity_status"))
        if identity_status != "available":
            reasons.append(
                "column_identity_conflict"
                if identity_status == "conflict"
                else "column_identity_unavailable"
            )
        if index in dense_pairs:
            reasons.append("dense_pair_alignment_disallowed")
        top_x = float(row["top"]["x"])
        bottom_x = float(row["bottom"]["x"])
        target_x = centers[index]
        if not seam_safe and any(
            value < seam_margin or coordinate_upper - value < seam_margin
            for value in (top_x, bottom_x, target_x)
        ):
            reasons.append("seam_margin_risk")
        if top_x == bottom_x:
            reasons.append("x_residual_zero")
        distinct_partners = {
            right if left == index else left
            for left, right in keep_distinct
            if index in {left, right}
        }
        if any(
            partner in centers and abs(centers[partner] - target_x) < separation_margin
            for partner in distinct_partners
        ):
            reasons.append("keep_distinct_collapse_risk")
        if any(
            other != index and abs(center - target_x) < separation_margin
            for other, center in centers.items()
        ):
            reasons.append("order_mutation_or_pair_merge_risk")
        if reasons:
            unavailable.extend(f"pair_{index}:{reason}" for reason in reasons)
            continue
        candidates.append(
            {
                "candidate_id": f"constrained_v0_column_x_alignment_pair_{index}",
                "action_family": "column_x_alignment",
                "source_id": "constrained_v0",
                "shadow_only": True,
                "accepted": False,
                "downstream_recommendation": False,
                "changed_pair_indices": [index],
                "coordinate_changes": [
                    {
                        "effective_pair_index": index,
                        "fields": {
                            "top_x": {"before": top_x, "after": target_x, "delta": target_x - top_x},
                            "bottom_x": {"before": bottom_x, "after": target_x, "delta": target_x - bottom_x},
                        },
                    }
                ],
                "eligibility_trace": {
                    "x_permission": True,
                    "evidence_status": "available",
                    "protected_pair": False,
                    "seam_ambiguous": False,
                    "column_identity_conflict": False,
                    "column_identity_status": "available",
                    "column_separation_margin": separation_margin,
                    "default_margin_used": default_margin_used,
                    "seam_margin": seam_margin,
                    "seam_safe": seam_safe,
                },
                "hard_reject_reasons": [],
                "source_provenance": {
                    "contract_doc_path": CONTRACT_PATH,
                    "source_version": SOURCE_VERSION,
                },
                "generation_constraints": {
                    "same_pair_only": True,
                    "y_unchanged": True,
                    "order_unchanged": True,
                    "pair_identity_unchanged": True,
                    "shadow_only": True,
                },
            }
        )

    payload["candidate_set"] = candidates
    payload["candidate_count"] = len(candidates)
    payload["unavailable_summary"] = {
        "reasons": sorted(set(unavailable)),
        "eligible_pair_count": len(candidates),
    }
    validate_candidate_source(payload)
    return payload
