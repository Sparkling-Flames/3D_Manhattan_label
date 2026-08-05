import csv
import json
from pathlib import Path

import pytest

from tools.thesis_main.analysis import geometry_cluster_v2
from tools.thesis_main.analysis.materialize_c1_operational_reference import (
    freeze_spot_check_reserve_order,
    select_final_nonflagged_spot_check,
    validate_reference_review_closure,
)
from tools.thesis_main.analysis.paper_a_contracts import METHOD_CONTRACT
from tools.thesis_main.analysis.vfinal_artifact_utils import sha256_file


def test_cluster_producer_materializes_second_medoid(monkeypatch):
    def fake_similarity(left, right):
        same = left["group"] == right["group"]
        return {
            "q_boundary": 1.0 if same else 0.1,
            "q_wallwall": 1.0 if same else 0.1,
            "metric_compatible": True,
            "pointwise_correspondence_compatible": True,
        }

    monkeypatch.setattr(geometry_cluster_v2, "pairwise_similarity", fake_similarity)
    records = [
        {"canonical_annotation_id": "c1", "worker_id": "w1", "group": "a", "geometry": {"valid": True, "group": "a"}},
        {"canonical_annotation_id": "c2", "worker_id": "w2", "group": "a", "geometry": {"valid": True, "group": "a"}},
        {"canonical_annotation_id": "c3", "worker_id": "w3", "group": "b", "geometry": {"valid": True, "group": "b"}},
        {"canonical_annotation_id": "c4", "worker_id": "w4", "group": "b", "geometry": {"valid": True, "group": "b"}},
    ]

    result = geometry_cluster_v2.cluster_geometry_records(
        records, min_q_boundary=.95, min_q_wallwall=.95, base_task_id="task", minimum_valid_k=3,
    )

    assert result["second_cluster_support"] == 2
    memberships = json.loads(result["cluster_membership_json"])
    assert result["second_cluster_medoid_annotation_id"] in set(memberships[1])
    assert result["second_cluster_medoid_worker_id"] in {"w1", "w2", "w3", "w4"}


def test_spot_check_reserve_order_is_reproducible_and_skips_late_flags():
    frozen = freeze_spot_check_reserve_order({"t3", "t1", "t2", "t4", "t5", "t6"}, stage="C2-B")
    assert frozen["candidate_population_sha256"] == freeze_spot_check_reserve_order(
        ["t1", "t2", "t3", "t4", "t5", "t6"], stage="C2-B"
    )["candidate_population_sha256"]
    selected = select_final_nonflagged_spot_check(
        frozen["reserve_order"], flagged_task_ids={frozen["reserve_order"][0]}, known_issue_ids={frozen["reserve_order"][1]}, count=4,
    )
    assert len(selected) == 4
    assert frozen["reserve_order"][0] not in selected
    assert frozen["reserve_order"][1] not in selected
    with pytest.raises(ValueError, match="not_enough_nonflagged_spot_check"):
        select_final_nonflagged_spot_check(frozen["reserve_order"], flagged_task_ids=set(frozen["reserve_order"][:-1]), known_issue_ids=set(), count=2)


def _review_record(path: Path, *, status: str, disposition: str) -> Path:
    fields = [
        "schema_version", "base_task_id", "registry_status_before_review", "reference_status_before_review",
        "reference_normalizer_status_before_review", "geometry_reference_ready_before_review",
        "review_status", "reviewer_blinding", "review_evidence", "review_disposition", "reviewed_by", "reviewed_at",
        "original_reference_sha256", "method_contract_sha256",
    ]
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerow({
            "schema_version": "paper_a_reference_conflict_review_record_v2",
            "base_task_id": "known",
            "registry_status_before_review": "approved_by_frozen_reference_policy",
            "reference_status_before_review": "use_existing_public_gt_as_is",
            "reference_normalizer_status_before_review": "passed",
            "geometry_reference_ready_before_review": "true",
            "review_status": status,
            "review_disposition": disposition,
            "review_evidence": "manual_scene_review_record" if disposition else "",
            "reviewed_by": "reviewer-1" if disposition else "",
            "reviewed_at": "2026-08-05T12:00:00Z" if disposition else "",
            "reviewer_blinding": "worker_and_analysis_metric_blinded",
            "original_reference_sha256": "a" * 64,
            "method_contract_sha256": sha256_file(METHOD_CONTRACT),
        })
    return path


def test_reference_review_closure_rejects_pending_and_accepts_terminal(tmp_path):
    pending = _review_record(tmp_path / "pending.csv", status="pending_review", disposition="")
    with pytest.raises(ValueError, match="reference_conflict_pending_review"):
        validate_reference_review_closure(pending, affected_base_task_ids={"known"})
    closed = _review_record(tmp_path / "closed.csv", status="closed", disposition="retain_original")
    result = validate_reference_review_closure(closed, affected_base_task_ids={"known"})
    assert result["pending_count"] == 0
