from tools.thesis_main.analysis.build_a4_replay_preoutcome_freeze import (
    classify_primary_eligibility,
    _call_normalize,
    _partition_records,
    _medoid_ranking,
    normalized_midrank,
    decide_variant_action,
    validate_requested_projection,
)
import tools.thesis_main.analysis.build_a4_replay_preoutcome_freeze as replay
from tools.thesis_main.analysis.geometry_consensus.medoid import select_medoid


def test_primary_reason_precedence_is_mutually_exclusive():
    excluded = {"14"}
    row = {"worker_id": "14", "candidate_parse_status": "invalid"}
    assert classify_primary_eligibility(row, None, excluded)["reason"] == "parse_invalid"

    row = {"worker_id": "14", "candidate_parse_status": "valid"}
    assert classify_primary_eligibility(row, {"eligible_for_geometry_loo": True}, excluded)["reason"] == "administratively_excluded_worker"

    row = {"worker_id": "15", "candidate_parse_status": "valid"}
    assert classify_primary_eligibility(row, None, excluded)["reason"] == "join_failure"

    assert classify_primary_eligibility(
        row, {"eligible_for_geometry_loo": False}, excluded
    )["reason"] == "formal_geometry_loo_ineligible"


def test_midrank_is_bounded_and_singleton_is_one():
    assert normalized_midrank([3.0], 3.0) == 1.0
    assert normalized_midrank([1.0, 2.0, 2.0, 4.0], 2.0) == 0.5
    assert 0.0 <= normalized_midrank([1.0, 2.0, 4.0], 1.0) <= 1.0


def test_unresolved_a0_cannot_be_rescued():
    state = {
        "a0_disposition": "unresolved",
        "a0_candidate_id": "",
        "alignment_ok": True,
        "clusters": [],
    }
    action = decide_variant_action("A4-S", state, {})
    assert action["action_disposition"] == "unresolved"
    assert action["selected_candidate_annotation_id"] == ""


def test_normalization_invalid_is_fail_closed():
    normalized, valid = _call_normalize({"corners_px": [], "width": 100, "height": 100})
    assert not valid
    assert normalized["valid"] is False


def test_cluster_membership_json_is_the_formal_partition_source():
    records = [
        {"canonical_annotation_id": "a"},
        {"canonical_annotation_id": "b"},
        {"canonical_annotation_id": "c"},
    ]
    result = {
        "cluster_membership_json": "[[\"a\", \"b\"], [\"c\"]]",
        "partition_status": "unique",
        "task_crowd_structure_status": "supported_multimodal",
        "structure_reason": "unique_complete_link_partition",
        "largest_cluster_medoid_annotation_id": "a",
    }
    assert [[item["canonical_annotation_id"] for item in group] for group in _partition_records(result, records)] == [["a", "b"], ["c"]]


def test_real_medoid_api_uses_integer_indices_and_can_skip_first_record():
    records = [
        {"canonical_annotation_id": "a", "geometry_hash": "z"},
        {"canonical_annotation_id": "b", "geometry_hash": "a"},
        {"canonical_annotation_id": "c", "geometry_hash": "m"},
    ]
    pair_scores = {(0, 1): 0.1, (0, 2): 0.2, (1, 2): 0.9}
    result = select_medoid(records, (0, 1, 2), pair_scores, task_id="pool")
    assert result[0] == 2
    assert records[result[0]]["canonical_annotation_id"] != "a"


def test_medoid_builds_every_integer_pair_without_overwrite(monkeypatch):
    records = [
        {"canonical_annotation_id": "a"},
        {"canonical_annotation_id": "b"},
        {"canonical_annotation_id": "c"},
    ]
    seen = {}
    monkeypatch.setattr(replay, "_pair_score", lambda left, right: 1.0)

    def fake_select(records, indices, pair_scores, task_id):
        seen.update(pair_scores)
        return (0, "", [(0.0, 0.0, "", "a", "", 0), (0.0, 0.0, "", "b", "", 1), (0.0, 0.0, "", "c", "", 2)])

    monkeypatch.setattr(replay, "select_medoid", fake_select)
    replay._medoid(records, "pool")
    assert set(seen) == {(0, 1), (0, 2), (1, 2)}


def test_a4_s_can_select_a_different_supported_cluster_deterministically(monkeypatch):
    groups = [
        [{"canonical_annotation_id": "a", "geometry_hash": "a"}, {"canonical_annotation_id": "b", "geometry_hash": "b"}],
        [{"canonical_annotation_id": "c", "geometry_hash": "c"}, {"canonical_annotation_id": "d", "geometry_hash": "d"}],
    ]
    monkeypatch.setattr(replay, "_medoid_ranking", lambda group, pool_id: list(group))
    state = {"pool_id": "pool", "a0_disposition": "selected", "a0_candidate_id": "a", "alignment_ok": True, "clusters": groups, "largest": groups[0]}
    scores = {"a": 0.1, "b": 0.1, "c": 0.9, "d": 0.9}
    action = decide_variant_action("A4-S", state, scores)
    assert action["action_disposition"] == "selected"
    assert action["selected_candidate_annotation_id"] in {"c", "d"}


def test_a4_s_one_supported_cluster_is_a0_equivalent_not_fallback(monkeypatch):
    group = [
        {"canonical_annotation_id": "a", "geometry_hash": "a"},
        {"canonical_annotation_id": "b", "geometry_hash": "b"},
    ]
    monkeypatch.setattr(replay, "_medoid_ranking", lambda group, pool_id: list(group))
    state = {"pool_id": "pool", "a0_disposition": "selected", "a0_candidate_id": "a", "alignment_ok": True, "clusters": [group], "largest": group}
    action = decide_variant_action("A4-S", state, {"a": 0.1, "b": 0.9})
    assert action["action_disposition"] == "selected"
    assert action["selected_candidate_annotation_id"] == "a"
    assert action["failure_reason"] == "no_supported_alternative"
    assert action["fallback_status"] == ""


def test_a4_l_reranks_inside_a0_largest_cluster(monkeypatch):
    group = [
        {"canonical_annotation_id": "a", "geometry_hash": "a"},
        {"canonical_annotation_id": "b", "geometry_hash": "b"},
    ]
    monkeypatch.setattr(replay, "_medoid_ranking", lambda group, pool_id: list(group))
    state = {"pool_id": "pool", "a0_disposition": "selected", "a0_candidate_id": "a", "alignment_ok": True, "clusters": [group], "largest": group}
    action = decide_variant_action("A4-L", state, {"a": 0.1, "b": 0.9})
    assert action["action_disposition"] == "selected"
    assert action["selected_candidate_annotation_id"] == "b"
    assert action["selected_candidate_annotation_id"] != state["a0_candidate_id"]


def test_a4_c_and_l_use_full_formal_rank_for_image_ties(monkeypatch):
    group = [
        {"canonical_annotation_id": "a", "geometry_hash": "a"},
        {"canonical_annotation_id": "b", "geometry_hash": "z"},
        {"canonical_annotation_id": "c", "geometry_hash": "m"},
    ]
    pair_scores = {("a", "b"): 0.1, ("a", "c"): 0.2, ("b", "c"): 0.9}
    monkeypatch.setattr(
        replay,
        "_pair_score",
        lambda left, right: pair_scores[tuple(sorted((left["canonical_annotation_id"], right["canonical_annotation_id"])))],
    )
    state = {"pool_id": "pool", "a0_disposition": "selected", "a0_candidate_id": "a", "alignment_ok": True, "clusters": [group], "largest": group}
    scores = {"a": 0.9, "b": 0.9, "c": 0.1}
    assert [item["canonical_annotation_id"] for item in _medoid_ranking(group, "pool")] == ["c", "b", "a"]
    action_c = decide_variant_action("A4-C", state, scores)
    action_l = decide_variant_action("A4-L", state, scores)
    assert action_c["selected_candidate_annotation_id"] == "b"
    assert action_l["selected_candidate_annotation_id"] == "b"
    assert action_c["image_score_tie_count"] == 2
    assert action_l["image_score_tie_count"] == 2
    assert action_c["image_tie_break_rule"] == "full_cluster_formal_medoid_ranking"
    assert action_l["image_tie_break_rule"] == "full_cluster_formal_medoid_ranking"


def test_deny_matching_is_token_based():
    assert validate_requested_projection("allowed.csv", ["height", "source_artifact"])
    try:
        validate_requested_projection("allowed.csv", ["gt_iou"])
    except PermissionError:
        pass
    else:
        raise AssertionError("gt_iou must be denied")

    try:
        validate_requested_projection("cross_fitted_selector_results.csv", ["stage"])
    except PermissionError:
        pass
    else:
        raise AssertionError("denied source path must fail closed")
