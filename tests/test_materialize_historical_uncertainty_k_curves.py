from __future__ import annotations

import math
from collections import Counter

import pytest

from tools.thesis_main.analysis.materialize_historical_uncertainty_k_curves_20260829 import (
    _cluster,
    _partition_matches_full_restriction,
    _same_second_mode_recovered,
    building_cluster_bootstrap_ci,
    build_annotation_eligibility,
    build_disagreement_distribution,
    build_minority_mode_replay,
    build_reference_contract,
    deterministic_candidate_order,
    hypergeom_probability_at_least,
    load_inputs,
)


def test_hypergeom_probability_at_least_uses_collected_k_denominator() -> None:
    assert math.isclose(hypergeom_probability_at_least(5, 3, 3, 3), 0.1)
    assert hypergeom_probability_at_least(5, 3, 5, 3) == 1.0
    assert hypergeom_probability_at_least(5, 0, 3, 1) == 0.0
    with pytest.raises(ValueError):
        hypergeom_probability_at_least(5, 3, 6, 3)


def test_deterministic_candidate_order_is_reproducible_and_supports_nested_prefixes() -> None:
    candidates = [
        {"canonical_annotation_id": "c", "worker_id": "3"},
        {"canonical_annotation_id": "a", "worker_id": "1"},
        {"canonical_annotation_id": "b", "worker_id": "2"},
        {"canonical_annotation_id": "d", "worker_id": "4"},
    ]
    first = deterministic_candidate_order(candidates, task_id="task", replicate=7, seed=19)
    second = deterministic_candidate_order(list(reversed(candidates)), task_id="task", replicate=7, seed=19)
    assert [row["canonical_annotation_id"] for row in first] == [
        row["canonical_annotation_id"] for row in second
    ]
    assert {row["canonical_annotation_id"] for row in first[:2]} < {
        row["canonical_annotation_id"] for row in first[:3]
    }


def test_building_cluster_bootstrap_preserves_constant_task_metric() -> None:
    rows = [
        {"building_id": "b1", "value": 0.25},
        {"building_id": "b1", "value": 0.25},
        {"building_id": "b2", "value": 0.25},
    ]
    lower, upper = building_cluster_bootstrap_ci(rows, value_field="value", replicates=100, seed=3)
    assert lower == 0.25
    assert upper == 0.25


def test_selector_is_blind_to_quality_values() -> None:
    candidates = [
        {
            "canonical_annotation_id": identifier,
            "worker_id": identifier,
            "quality": quality,
            "_geometry": {
                "valid": True,
                "candidate_id": identifier,
                "frozen_geometry_sha256": identifier,
            },
        }
        for identifier, quality in (("a", 0.1), ("b", 0.5), ("c", 0.9))
    ]
    pair_map = {
        tuple(sorted(pair)): {
            "metric_compatible": True,
            "pointwise_correspondence_compatible": True,
            "q_boundary": 0.99,
            "q_wallwall": 0.99,
        }
        for pair in (("a", "b"), ("a", "c"), ("b", "c"))
    }
    selected = _cluster(candidates, "task", pair_map)["largest_cluster_medoid_annotation_id"]
    poisoned = [{**row, "quality": 1000.0 - row["quality"]} for row in candidates]
    assert _cluster(poisoned, "task", pair_map)["largest_cluster_medoid_annotation_id"] == selected


def test_same_minority_mode_is_not_generic_multimodality() -> None:
    full = [["a", "b", "c"], ["m1", "m2", "m3"]]
    sample = {"a", "b", "m1", "m2"}
    exact_prefix = [["a", "b"], ["m1", "m2"]]
    contaminated_prefix = [["a", "b", "m1"], ["m2"]]

    assert _same_second_mode_recovered(set(full[1]), sample, exact_prefix)
    assert not _same_second_mode_recovered(set(full[1]), sample, contaminated_prefix)
    assert _partition_matches_full_restriction(full, sample, exact_prefix)
    assert not _partition_matches_full_restriction(full, sample, contaminated_prefix)
    assert not _same_second_mode_recovered(set(full[1]), {"a", "b", "m1"}, [["a", "b"], ["m1"]])


def test_historical_contract_and_annotation_denominators_are_fail_closed() -> None:
    inputs = load_inputs()
    contract = build_reference_contract(inputs)
    annotations = build_annotation_eligibility(inputs, contract)
    assert len(contract) == 42
    assert Counter(row["stage"] for row in contract) == Counter({"P1": 30, "C1": 12})
    assert sum(bool(row["geometry_reference_ready"]) for row in contract) == 41
    assert len(annotations) == 1055
    assert sum(row["gt_primary_analysis_eligible"] is True for row in annotations) == 770


def test_distribution_and_same_mode_replay_denominators_are_fail_closed() -> None:
    inputs = load_inputs()
    task_rows, summaries, ecdf, associations = build_disagreement_distribution(
        inputs, bootstrap_replicates=10
    )
    assert (len(task_rows), len(summaries), len(ecdf), len(associations)) == (42, 39, 157, 6)

    full, task_k, summary, thresholds, qa = build_minority_mode_replay(
        replicates=1, bootstrap_replicates=10
    )
    assert (len(full), len(task_k), len(summary), len(thresholds)) == (42, 210, 15, 15)
    assert qa["full_supported_multimodal_task_count"] == 21
    assert qa["full_evaluable_nonmultimodal_task_count"] == 16
    assert qa["second_rank_tie_sensitive_task_count"] == 3
    assert qa["unique_second_rank_multimodal_task_count"] == 18
    assert qa["generic_multimodality_is_same_mode_claim"] is False
