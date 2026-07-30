from tools.thesis_main.analysis.geometry_cluster_v2 import _maximum_clique_partitions
from tools.thesis_main.analysis.paper_a_contracts import validate_record


def test_policy_candidate_allows_unavailable_medoid_loo() -> None:
    validate_record("policy_candidate_v2", {
        "schema_version": "policy_candidate_v2", "worker_id": "w1", "S_G": 1.0, "global_rank_S_G": 1,
        "global_policy_eligible": True, "R_peer_stable": None, "R_peer_profile_status": "not_evaluable",
        "R_LOO_medoid": None, "LOO_medoid_status": "not_evaluable", "profile_version": "p",
    })


def test_geometry_enumerates_overlapping_maximum_clique_partitions() -> None:
    partitions, truncated, _ = _maximum_clique_partitions((0, 1, 2), {(0, 1), (1, 2)})
    assert truncated is False
    assert len(partitions) == 2
    assert {tuple(tuple(group) for group in partition) for partition in partitions} == {
        ((0, 1), (2,)), ((1, 2), (0,)),
    }
