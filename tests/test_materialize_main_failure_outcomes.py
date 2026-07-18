from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path

import pytest

from tools.thesis_main.analysis.materialize_main_failure_outcomes import (
    materialize_complete_c1_dispositions,
    materialize,
    materialize_t1_rows,
    materialize_v1_rows,
)
from tools.thesis_main.registry.init_failure_disposition_rule_manifest import build_manifest


def _c1_roster() -> list[dict[str, str]]:
    return [
        {
            "project_id": "66", "ls_runtime_task_id": "200", "worker_id": "w1",
            "annotation_id": "a1", "annotation_timestamp": "2026-01-01T00:30:00Z",
        },
        {
            "project_id": "66", "ls_runtime_task_id": "201", "worker_id": "w2",
            "annotation_id": "a2", "annotation_timestamp": "2026-01-01T00:30:00Z",
        },
    ]


def _incident(tmp_path: Path, **updates: str) -> dict[str, str]:
    evidence = tmp_path / "incident.log"
    evidence.write_text("outage", encoding="utf-8")
    row = {
        "incident_id": "inc-1",
        "incident_type": "platform_unavailable",
        "occurred_at": "2026-01-01T00:00:00Z",
        "recovered_at": "2026-01-01T01:00:00Z",
        "affected_project_ids": '["66"]',
        "affected_task_ids": '["200"]',
        "affected_scope_rule": "",
        "evidence_path": evidence.name,
        "evidence_sha256": hashlib.sha256(evidence.read_bytes()).hexdigest(),
        "recorded_at": "2026-01-01T00:10:00Z",
        "recorded_before_outcome_review": "true",
    }
    return {**row, **updates}


def _write_csv(path: Path, rows: list[dict[str, str]]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def test_sparse_c1_adjudication_expands_to_complete_fail_closed_table(tmp_path: Path) -> None:
    rows, audit = materialize_complete_c1_dispositions(
        _c1_roster(),
        [{
            "project_id": "66", "ls_runtime_task_id": "200", "worker_id": "w1",
            "annotation_id": "a1", "failure_attribution": "external_system_failure",
            "incident_id": "inc-1",
        }],
        [_incident(tmp_path)],
        incident_base_dir=tmp_path,
    )

    assert [row["failure_attribution"] for row in rows] == ["external_system_failure", "none"]
    assert audit["n_canonical_annotations"] == 2


@pytest.mark.parametrize(
    ("updates", "reason"),
    [
        ({"evidence_sha256": "0" * 64}, "incident_evidence_sha256_mismatch"),
        ({"affected_task_ids": '["999"]'}, "task_outside_incident_scope"),
        ({"occurred_at": "2026-01-02T00:00:00Z"}, "annotation_outside_incident_window"),
        ({"recorded_before_outcome_review": "false"}, "incident_recorded_after_outcome_review"),
    ],
)
def test_external_incident_that_only_claims_verified_fails_closed(
    tmp_path: Path, updates: dict[str, str], reason: str
) -> None:
    rows, _ = materialize_complete_c1_dispositions(
        _c1_roster()[:1],
        [{
            "project_id": "66", "ls_runtime_task_id": "200", "worker_id": "w1",
            "annotation_id": "a1", "failure_attribution": "external_system_failure",
            "incident_id": "inc-1", "incident_evidence_status": "verified",
        }],
        [_incident(tmp_path, **updates)],
        incident_base_dir=tmp_path,
    )

    assert rows[0]["failure_attribution"] == "not_evaluable"
    assert rows[0]["failure_disposition_reason"] == reason


def test_c1_materializer_binds_manifest_registry_and_evidence_sha(tmp_path: Path) -> None:
    roster, adjudication, incidents = tmp_path / "roster.csv", tmp_path / "adjudication.csv", tmp_path / "incidents.csv"
    _write_csv(roster, _c1_roster()[:1])
    _write_csv(adjudication, [{
        "project_id": "66", "ls_runtime_task_id": "200", "worker_id": "w1",
        "annotation_id": "a1", "failure_attribution": "external_system_failure",
        "incident_id": "inc-1",
    }])
    _write_csv(incidents, [_incident(tmp_path)])
    manifest = tmp_path / "rules.json"
    manifest.write_text(json.dumps(build_manifest(locked_round="C2", contract_version="v2")), encoding="utf-8")

    summary = materialize(
        "C1", roster, tmp_path / "out", rule_manifest=manifest,
        adjudication_csv=adjudication, incident_registry_csv=incidents,
    )

    assert summary["rule_version"] == "failure_disposition_v2"
    assert summary["dependency_sha256"]["rule_manifest"] == hashlib.sha256(manifest.read_bytes()).hexdigest()
    assert summary["dependency_sha256"]["incident_evidence:inc-1"] == hashlib.sha256(
        (tmp_path / "incident.log").read_bytes()
    ).hexdigest()


def _t1_pair(pair_id: str, *, disposition: str, rerun_of: str = "", workers=("w1", "w2")):
    common = {
        "pair_id": pair_id, "pair_analysis_disposition": disposition,
        "rerun_of_pair_id": rerun_of, "rerun_sequence": "1" if rerun_of else "",
        "image_id": "img-1", "frozen_rule_version": "freeze-1",
    }
    return [
        {**common, "task_id": f"{pair_id}-m", "condition": "manual", "worker_id": workers[0],
         "row_failure_attribution": "none", "iou_to_gt": "0.6"},
        {**common, "task_id": f"{pair_id}-s", "condition": "semi", "worker_id": workers[1],
         "row_failure_attribution": "none", "iou_to_gt": "0.8"},
    ]


def test_t1_one_sided_external_reruns_whole_pair_without_mislabeling_other_row() -> None:
    original = _t1_pair("p1", disposition="rerun")
    original[0].update({
        "row_failure_attribution": "external_system_failure",
        "incident_id": "inc-1", "incident_evidence_status": "verified",
    })
    rerun = _t1_pair("p1-r1", disposition="included", rerun_of="p1", workers=("w3", "w4"))

    rows, audit = materialize_t1_rows(original + rerun)

    assert {row["source_pair_id"] for row in rows} == {"p1-r1"}
    assert {row["analysis_unit_pair_id"] for row in rows} == {"p1"}
    assert {row["row_failure_attribution"] for row in rows} == {"none"}
    assert {row["original_row_failure_attribution"] for row in rows} == {
        "external_system_failure", "none"
    }
    assert audit["resolved_rerun_pairs"] == 1


def test_t1_worker_failure_is_zero_only_in_its_condition() -> None:
    rows = _t1_pair("p1", disposition="included")
    rows[0]["row_failure_attribution"] = "worker_caused_structural_failure"

    output, _ = materialize_t1_rows(rows)

    assert output[0]["delivery_adjusted_quality"] == 0.0
    assert output[1]["delivery_adjusted_quality"] == 0.8


def test_t1_rejects_duplicate_condition_and_same_worker_rerun() -> None:
    bad = _t1_pair("p1", disposition="included")
    bad[1]["condition"] = "manual"
    with pytest.raises(ValueError, match="exactly one"):
        materialize_t1_rows(bad)

    original = _t1_pair("p1", disposition="rerun")
    original[0].update({
        "row_failure_attribution": "external_system_failure",
        "incident_id": "inc-1", "incident_evidence_status": "verified",
    })
    with pytest.raises(ValueError, match="worker-image isolation"):
        materialize_t1_rows(original + _t1_pair("p1-r1", disposition="included", rerun_of="p1"))


def _v1_original(**updates: str) -> dict[str, str]:
    row = {
        "task_id": "v1", "original_task_id": "", "policy_arm": "Full",
        "freeze_version": "freeze-1", "failure_attribution": "external_system_failure",
        "incident_id": "inc-1", "incident_evidence_status": "verified",
        "analysis_disposition": "rerun", "policy_terminal_status": "",
    }
    return {**row, **updates}


def _v1_rerun(**updates: str) -> dict[str, str]:
    row = {
        "task_id": "v1-r1", "original_task_id": "v1", "rerun_task_id": "v1-r1",
        "policy_arm": "Full", "freeze_version": "freeze-1", "failure_attribution": "none",
        "analysis_disposition": "included", "policy_terminal_status": "resolved", "iou_to_gt": "0.9",
        "rerun_sequence": "1", "reservation_id": "res-1", "reservation_arm": "Full",
        "reservation_capacity_before": "2", "reservation_capacity_after": "1",
    }
    return {**row, **updates}


def test_v1_valid_rerun_resolves_original_randomization_unit() -> None:
    rows, audit = materialize_v1_rows([_v1_original(), _v1_rerun()])

    assert rows[0]["task_id"] == "v1"
    assert rows[0]["resolved_task_id"] == "v1-r1"
    assert rows[0]["policy_arm"] == "Full"
    assert rows[0]["original_failure_attribution"] == "external_system_failure"
    assert rows[0]["itt_included"] is True
    assert rows[0]["delivery_adjusted_quality"] == 0.9
    assert audit["resolved_reruns"] == 1


@pytest.mark.parametrize(
    ("updates", "message"),
    [
        ({"policy_arm": "Global"}, "policy arm"),
        ({"freeze_version": "freeze-2"}, "freeze version"),
        ({"rerun_sequence": "2"}, "rerun_sequence"),
        ({"reservation_arm": "Global"}, "reservation arm"),
        ({"reservation_capacity_after": "2"}, "consume exactly one"),
    ],
)
def test_v1_rejects_invalid_rerun_relation(updates: dict[str, str], message: str) -> None:
    with pytest.raises(ValueError, match=message):
        materialize_v1_rows([_v1_original(), _v1_rerun(**updates)])


def test_v1_rejects_second_rerun_duplicate_reservation_and_pending_terminal() -> None:
    with pytest.raises(ValueError, match="more than one rerun"):
        materialize_v1_rows([
            _v1_original(), _v1_rerun(), _v1_rerun(task_id="v1-r2", rerun_task_id="v1-r2"),
        ])
    with pytest.raises(ValueError, match="duplicate V1 reservation"):
        materialize_v1_rows([
            _v1_original(),
            _v1_original(task_id="v2"),
            _v1_rerun(),
            _v1_rerun(task_id="v2-r1", original_task_id="v2", rerun_task_id="v2-r1"),
        ])
    with pytest.raises(ValueError, match="cannot enter final"):
        materialize_v1_rows([_v1_original(
            failure_attribution="none", analysis_disposition="included",
            policy_terminal_status="external_system_failure_pending_disposition",
        )])


def test_v1_policy_failure_stays_in_itt_with_zero_quality() -> None:
    rows, audit = materialize_v1_rows([_v1_original(
        failure_attribution="policy_caused_failure",
        analysis_disposition="included",
        policy_terminal_status="severe_failure",
    )])

    assert rows[0]["itt_included"] is True
    assert rows[0]["delivery_adjusted_quality"] == 0.0
    assert audit["policy_failure_by_arm"] == {"Full": 1}
