from __future__ import annotations

import numpy as np
import pytest

from tools.thesis_main.analysis.audit_worker_manual_strata_exploratory import (
    HIGH,
    LOW,
    UNCLASSIFIED,
    _resample_building_then_task,
    classify_probability,
    fit_worker_task_effects,
    structural_failure_audit,
)


def test_probability_rule_keeps_an_abstention_band() -> None:
    assert classify_probability(0.80) == HIGH
    assert classify_probability(0.20) == LOW
    assert classify_probability(0.50) == UNCLASSIFIED


def test_worker_task_fixed_effects_remove_task_difficulty() -> None:
    rows = [
        {"worker_id": "1", "base_task_id": "a", "building_id": "x", "quality": 0.9},
        {"worker_id": "2", "base_task_id": "a", "building_id": "x", "quality": 0.7},
        {"worker_id": "1", "base_task_id": "b", "building_id": "y", "quality": 0.7},
        {"worker_id": "2", "base_task_id": "b", "building_id": "y", "quality": 0.5},
    ]

    effects = fit_worker_task_effects(rows, ("1", "2"))

    assert effects["1"] == pytest.approx(0.1)
    assert effects["2"] == pytest.approx(-0.1)


def test_manual_bootstrap_resamples_buildings_then_tasks() -> None:
    rows = [
        {"worker_id": worker, "base_task_id": task, "building_id": building, "quality": quality}
        for building, task, quality in (("a", "a1", 0.9), ("a", "a2", 0.7), ("b", "b1", 0.5))
        for worker in ("1", "2")
    ]

    sampled = _resample_building_then_task(rows, np.random.default_rng(7))

    assert len({row["building_id"] for row in sampled}) >= 2
    assert all(str(row["base_task_id"]).startswith("bootstrap_building_") for row in sampled)
    assert all(
        {row["worker_id"] for row in sampled if row["base_task_id"] == task} == {"1", "2"}
        for task in {row["base_task_id"] for row in sampled}
    )


def test_structural_audit_uses_the_structural_numerator() -> None:
    rows = [
        {
            "condition": "manual",
            "worker_id": "2",
            "base_task_id": "core-a",
            "structural_opportunity_eligible": "True",
            "worker_structural_failure_numerator": "True",
        },
        {
            "condition": "manual",
            "worker_id": "2",
            "base_task_id": "core-b",
            "structural_opportunity_eligible": "True",
            "worker_structural_failure_numerator": "True",
        },
        {
            "condition": "semi",
            "worker_id": "2",
            "base_task_id": "core-a",
            "structural_opportunity_eligible": "True",
            "worker_structural_failure_numerator": "True",
        },
    ]

    assert structural_failure_audit(rows, {"core-a", "core-b"}) == {
        "opportunity_count": 2,
        "worker_caused_failure_count": 2,
        "worker_with_recurrent_failures_count": 1,
    }
