from __future__ import annotations

import hashlib

import pytest

from tools.thesis_main.analysis import build_a4_deployment_pool_identity as mod


def _sources():
    canonical = {
        "canonical_annotation_id": "a1",
        "worker_id": "w1",
        "stage": "C1",
        "round_id": "C1",
        "condition": "manual",
        "base_task_id": "b1",
        "task_id": "t1",
        "project_id": "66",
        "ls_runtime_task_id": "r1",
        "dataset_group": "Calibration_anchor",
        "source_export": "export.json",
        "source_export_sha256": "export-sha-1",
        "source_artifact": "canonical.csv",
        "source_sha256": "canonical-sha",
        "canonicalization_status": "frozen",
        "duplicate_worker_task_submission": "false",
        "duplicate_group_size": "1",
        "duplicate_annotation_ids": "",
        "duplicate_decision": "",
        "process_disposition": "",
        "appears_in_internal_distribution": "True",
    }
    runtime = {
        "project_id": "66",
        "ls_runtime_task_id": "r1",
        "task_id": "t1",
        "base_task_id": "b1",
        "condition": "manual",
        "planned_project_name": "C1_anchor_all",
        "source_export": "export.json",
    }
    realization = {
        "worker_id": "w1",
        "task_id": "t1",
        "base_task_id": "b1",
        "condition": "manual",
        "canonical_selected_submission": "True",
        "missing_submission": "False",
        "assignment_provenance": "original_assignment",
    }
    candidate = {
        "candidate_annotation_id": "a1",
        "worker_id": "w1",
        "stage": "C1",
        "panorama_identity": "b1",
        "building_scene_id": "scene1",
        "parse_status": "valid",
        "layout_corner_count": "4",
    }
    return [candidate], [canonical], [runtime], [realization]


def test_pool_key_excludes_export_sha_and_keeps_deployment_boundary():
    base = ("C1", "C1", "manual", "b1", "t1")
    pool_a = mod.deployment_pool_id(*base, "66", "r1")
    pool_b = mod.deployment_pool_id(*base, "67", "r2")
    assert pool_a != pool_b
    assert mod.deployment_pool_id(*base, "66", "r1") == pool_a
    assert mod.experimental_task_context_id(*base) != ""
    assert mod.source_sha_not_in_pool_key(pool_a, "different-export-sha")


def test_unique_join_and_zero_many_fail_closed():
    candidates, canonical, runtime, realization = _sources()
    rows, stats = mod.build_identity_rows(candidates, canonical, runtime, realization, [], mod.TEST_SOURCE_META)
    assert stats["mapped"] == 1
    assert rows[0]["mapping_status"] == "mapped"
    assert rows[0]["identity_mapping_status"] == "mapped"
    assert rows[0]["observed_canonical_runtime_source_status"] == "matched"

    many = canonical + [dict(canonical[0], source_sha256="other")]
    rows, _ = mod.build_identity_rows(candidates, many, runtime, realization, [], mod.TEST_SOURCE_META)
    assert rows[0]["mapping_status"] == "fail_closed"
    assert "canonical_annotation_join_many" in rows[0]["mapping_reason"]

    rows, _ = mod.build_identity_rows(candidates, [], runtime, realization, [], mod.TEST_SOURCE_META)
    assert rows[0]["mapping_status"] == "fail_closed"
    assert "canonical_annotation_join_zero" in rows[0]["mapping_reason"]


def test_same_pool_different_workers_do_not_split_pool():
    candidates, canonical, runtime, realization = _sources()
    second_candidate = dict(candidates[0], candidate_annotation_id="a2", worker_id="w2")
    second_canonical = dict(canonical[0], canonical_annotation_id="a2", worker_id="w2")
    second_realization = dict(realization[0], worker_id="w2")
    rows, _ = mod.build_identity_rows(
        candidates + [second_candidate],
        canonical + [second_canonical],
        runtime,
        realization + [second_realization],
        [],
        mod.TEST_SOURCE_META,
    )
    assert rows[0]["deployment_pool_id"] == rows[1]["deployment_pool_id"]


def test_missing_realization_does_not_gate_identity():
    candidates, canonical, runtime, _ = _sources()
    rows, _ = mod.build_identity_rows(candidates, canonical, runtime, [], [], mod.TEST_SOURCE_META)
    assert rows[0]["identity_mapping_status"] == "mapped"
    assert rows[0]["assignment_realization_status"] == "missing"
    assert rows[0]["development_admissibility_status"] == "not_defined"
    assert rows[0]["development_admissibility_reason"] == "eligibility_spec_not_frozen"
    assert rows[0]["canonical_selection_status"] == "formal_canonical_row_present"


def test_formal_keep_selected_duplicate_does_not_gate_identity():
    candidates, canonical, runtime, realization = _sources()
    canonical[0].update({
        "duplicate_group_size": "2",
        "duplicate_decision": "keep_selected_version",
        "process_disposition": "no_process_penalty",
    })
    rows, _ = mod.build_identity_rows(candidates, canonical, runtime, realization, [], mod.TEST_SOURCE_META)
    assert rows[0]["identity_mapping_status"] == "mapped"
    assert rows[0]["formal_duplicate_status"] == "keep_selected_version"


def test_appears_false_is_not_an_eligibility_source():
    candidates, canonical, runtime, realization = _sources()
    canonical[0]["appears_in_internal_distribution"] = "False"
    rows, _ = mod.build_identity_rows(candidates, canonical, runtime, realization, [], mod.TEST_SOURCE_META)
    assert rows[0]["development_admissibility_status"] == "not_defined"
    assert rows[0]["development_admissibility_reason"] == "eligibility_spec_not_frozen"
    assert rows[0]["appears_in_internal_distribution"] == "False"
    assert rows[0]["appears_in_internal_distribution_role"] == "not_an_eligibility_source"


def test_zero_strict_pool_with_observed_candidate_is_retained_in_summary():
    candidates, canonical, runtime, realization = _sources()
    rows, _ = mod.build_identity_rows(candidates, canonical, runtime, [], [], mod.TEST_SOURCE_META)
    summary = mod._summary_rows(rows)
    assert len(summary) == 1
    assert summary[0]["identity_candidate_count"] == 1
    assert summary[0]["observed_geometry_valid_count"] == 1
    assert summary[0]["realization_matched_geometry_valid_count"] == 0
    assert summary[0]["observed_valid_meets_k3"] == "False"
    assert summary[0]["strict_realization_sensitivity_meets_k3"] == "False"


def test_observed_and_strict_support_are_independent():
    candidates, canonical, runtime, realization = _sources()
    second_candidate = dict(candidates[0], candidate_annotation_id="a2", worker_id="w2")
    second_canonical = dict(canonical[0], canonical_annotation_id="a2", worker_id="w2")
    rows, _ = mod.build_identity_rows(
        candidates + [second_candidate],
        canonical + [second_canonical],
        runtime,
        realization,
        [],
        mod.TEST_SOURCE_META,
    )
    summary = mod._summary_rows(rows)
    assert len(summary) == 1
    assert summary[0]["observed_geometry_valid_count"] == 2
    assert summary[0]["realization_matched_geometry_valid_count"] == 1
    assert summary[0]["observed_valid_meets_k3"] == "False"
    assert summary[0]["strict_realization_sensitivity_meets_k3"] == "False"


def test_runtime_many_still_fails_identity():
    candidates, canonical, runtime, realization = _sources()
    rows, _ = mod.build_identity_rows(candidates, canonical, runtime + [dict(runtime[0], planned_project_name="other")], realization, [], mod.TEST_SOURCE_META)
    assert rows[0]["identity_mapping_status"] == "fail_closed"
    assert "runtime_mapping_join_many" in rows[0]["mapping_reason"]


def test_deny_path_and_columns():
    with pytest.raises(PermissionError):
        mod.assert_input_allowed(mod.ROOT / "export_label" / "x.csv")
    with pytest.raises(PermissionError):
        mod.validate_projection(["worker_id", "gt_iou"])
    mod.validate_projection(["height", "source_artifact"])


def test_real_candidate_input_is_580_and_v2_bytes_are_unchanged():
    rows = mod.read_csv_projection(mod.CANDIDATE_PATH, mod.CANDIDATE_COLUMNS, [])
    assert len(rows) == 580
    assert len({row["candidate_annotation_id"] for row in rows}) == 580
    assert mod.sha256(mod.CANDIDATE_PATH) == "a118056a615e3630147cdaad210e3283df419d4f7733b3bd8c2125b53f5f3f43"
    assert hashlib.sha256(mod.CANDIDATE_PATH.read_bytes()).hexdigest() == mod.sha256(mod.CANDIDATE_PATH)
