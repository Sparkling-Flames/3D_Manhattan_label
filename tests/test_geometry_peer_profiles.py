import pytest

from tools.thesis_main.analysis.geometry_consensus.stability import crowd_structure
from tools.thesis_main.analysis.geometry_consensus.pairwise import peer_similarity_profiles


def _records(groups):
    return [{"worker_id": f"w{i}", "canonical_annotation_id": f"c{i}", "geometry": {"valid": True, "group": group}} for i, group in enumerate(groups)]


def _similarity(left, right, **_kwargs):
    score = .95 if left["group"] == right["group"] else .2
    return {"boundary_similarity": score, "wallwall_similarity": score, "pointwise_correspondence_compatible": True}


def test_crowd_structure_4_1_and_peer_profiles(monkeypatch):
    monkeypatch.setattr("tools.thesis_main.analysis.geometry_consensus.stability.pairwise_similarity", _similarity)
    monkeypatch.setattr("tools.thesis_main.analysis.geometry_consensus.pairwise.pairwise_similarity", _similarity)
    rows = _records([0, 0, 0, 0, 1])
    assert crowd_structure(rows)["task_crowd_structure_status"] == "dominant_with_dissent"
    profiles = peer_similarity_profiles(rows)
    assert all(row["R_peer_task"] is not None for row in profiles)
    assert all(row["R_peer_task"] == row["R_peer_conservative_median"] for row in profiles)
    assert all(row["similarity_definition"] == "min_boundary_wall" for row in profiles)


def test_crowd_structure_3_2_is_supported_multimodal(monkeypatch):
    monkeypatch.setattr("tools.thesis_main.analysis.geometry_consensus.stability.pairwise_similarity", _similarity)
    result = crowd_structure(_records([0, 0, 0, 1, 1]))
    assert result["task_crowd_structure_status"] == "supported_multimodal"
    assert result["largest_cluster_share"] == .6
    assert result["second_cluster_share"] == .4
    assert result["cluster_margin_all"] == .2
    assert result["cluster_margin_top2"] == .2


def test_crowd_structure_3_1_1_has_no_supported_second_mode(monkeypatch):
    monkeypatch.setattr("tools.thesis_main.analysis.geometry_consensus.stability.pairwise_similarity", _similarity)
    result = crowd_structure(_records([0, 0, 0, 1, 2]))
    assert result["task_crowd_structure_status"] == "dominant_with_dissent"
    assert result["second_cluster_support"] == 1


def test_crowd_structure_equal_singletons_are_not_dominant(monkeypatch):
    monkeypatch.setattr("tools.thesis_main.analysis.geometry_consensus.stability.pairwise_similarity", _similarity)
    result = crowd_structure(_records([0, 1, 2]))
    assert result["task_crowd_structure_status"] == "insufficient_or_incompatible"


def test_crowd_structure_does_not_join_topology_mismatch(monkeypatch):
    monkeypatch.setattr(
        "tools.thesis_main.analysis.geometry_consensus.stability.pairwise_similarity",
        lambda *_args, **_kwargs: {
            "boundary_similarity": .99,
            "wallwall_similarity": .99,
            "pointwise_correspondence_compatible": False,
        },
    )
    result = crowd_structure(_records([0, 0, 0]), similarity_cutoff=.95)
    assert result["largest_cluster_support"] == 1
