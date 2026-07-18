from __future__ import annotations

import pytest

from tools.thesis_main.analysis.materialize_main_failure_outcomes import (
    materialize_t1_rows,
    materialize_v1_rows,
)


def test_t1_worker_failure_is_zero_in_its_condition() -> None:
    rows, audit = materialize_t1_rows([
        {"task_id": "m1", "pair_id": "i1", "condition": "manual", "failure_attribution": "worker_caused_structural_failure", "analysis_disposition": "included", "iou_to_gt": "0.8"},
        {"task_id": "s1", "pair_id": "i1", "condition": "semi", "failure_attribution": "none", "analysis_disposition": "included", "iou_to_gt": "0.7"},
    ])

    assert rows[0]["structurally_valid"] is False
    assert rows[0]["delivery_adjusted_quality"] == 0.0
    assert rows[1]["delivery_adjusted_quality"] == 0.7
    assert audit["administrative_censor_count"] == 0


def test_t1_external_incident_requires_whole_pair_rerun_or_censor() -> None:
    rows, audit = materialize_t1_rows([
        {"task_id": "m1", "pair_id": "i1", "condition": "manual", "failure_attribution": "external_system_failure", "incident_id": "inc-1", "incident_evidence_status": "verified", "analysis_disposition": "administrative_censor"},
        {"task_id": "s1", "pair_id": "i1", "condition": "semi", "failure_attribution": "external_system_failure", "incident_id": "inc-1", "incident_evidence_status": "verified", "analysis_disposition": "administrative_censor"},
    ])

    assert all(row["quality_evaluable"] is False for row in rows)
    assert audit["administrative_censor_count"] == 2


def test_t1_rejects_partial_external_pair_disposition() -> None:
    with pytest.raises(ValueError, match="whole pair"):
        materialize_t1_rows([
            {"task_id": "m1", "pair_id": "i1", "condition": "manual", "failure_attribution": "external_system_failure", "incident_id": "inc-1", "incident_evidence_status": "verified", "analysis_disposition": "rerun"},
            {"task_id": "s1", "pair_id": "i1", "condition": "semi", "failure_attribution": "none", "analysis_disposition": "included", "iou_to_gt": "0.7"},
        ])


def test_v1_policy_failure_stays_in_itt_with_zero_quality() -> None:
    rows, audit = materialize_v1_rows([
        {"task_id": "v1", "policy_arm": "Full", "failure_attribution": "policy_caused_failure", "analysis_disposition": "included", "policy_terminal_status": "severe_failure"},
    ])

    assert rows[0]["itt_included"] is True
    assert rows[0]["policy_failure"] is True
    assert rows[0]["delivery_adjusted_quality"] == 0.0
    assert audit["policy_failure_by_arm"] == {"Full": 1}


def test_v1_external_rerun_requires_frozen_same_arm_evidence() -> None:
    rows, _audit = materialize_v1_rows([
        {"task_id": "v1", "policy_arm": "Full", "failure_attribution": "external_system_failure", "incident_id": "inc-1", "incident_evidence_status": "verified", "analysis_disposition": "rerun", "policy_terminal_status": "", "rerun_of_task_id": "v0", "frozen_rule_version": "failure-disposition-v1", "rerun_capacity_reservation_id": "reserve-full-1"},
    ])
    assert rows[0]["itt_included"] is False

    with pytest.raises(ValueError, match="rerun_capacity_reservation_id"):
        materialize_v1_rows([
            {"task_id": "v1", "policy_arm": "Full", "failure_attribution": "external_system_failure", "incident_id": "inc-1", "incident_evidence_status": "verified", "analysis_disposition": "rerun", "policy_terminal_status": "", "rerun_of_task_id": "v0", "frozen_rule_version": "failure-disposition-v1"},
        ])


def test_v1_unverified_external_incident_is_not_evaluable() -> None:
    rows, audit = materialize_v1_rows([
        {"task_id": "v1", "policy_arm": "Full", "failure_attribution": "external_system_failure", "analysis_disposition": "administrative_censor", "policy_terminal_status": ""},
    ])

    assert rows[0]["analysis_disposition"] == "not_evaluable"
    assert rows[0]["itt_included"] is False
    assert audit["not_evaluable_by_arm"] == {"Full": 1}
