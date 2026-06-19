import hashlib
import json
from pathlib import Path

from tools.paper_a_manhattan.manhattan_m1526_adaptive_local_probe import (
    SAFETY_BOUNDARY,
)
from tools.paper_a_manhattan.run_m1526_adaptive_local_probe import run


PROTECTED_FILES = (
    Path("tools/paper_a_manhattan/manhattan_3d_projection.py"),
    Path("tools/paper_a_manhattan/manhattan_m1520_local_candidate_search.py"),
    Path("tools/paper_a_manhattan/run_m1520_local_candidate_search.py"),
    Path("tools/label_studio/vis_3d.html"),
)


def _digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_m1526_adaptive_local_probe(tmp_path):
    protected_before = {path: _digest(path) for path in PROTECTED_FILES}
    paths = run(tmp_path)
    protected_after = {path: _digest(path) for path in PROTECTED_FILES}

    assert protected_after == protected_before
    assert paths["json"].is_file()
    assert paths["report"].is_file()
    assert {path.name for path in tmp_path.iterdir()} == {
        "adaptive_probe.json",
        "adaptive_probe.md",
    }

    payload = json.loads(paths["json"].read_text(encoding="utf-8"))
    assert payload["schema_version"] == "m15_26_adaptive_local_probe_v1"
    assert payload["safety_boundary"] == SAFETY_BOUNDARY
    assert SAFETY_BOUNDARY == {
        "expert_side": True,
        "offline_local_only": True,
        "dry_run_only": True,
        "annotation_write_allowed": False,
        "annotation_patch_generated": False,
        "automatic_apply": False,
        "automatic_global_optimization": False,
        "worker_facing": False,
        "routing_input": False,
        "formal_artifact": False,
    }
    assert payload["visual_verdict_context"]["direct_fix_available"] is False

    search_space = payload["search_space"]
    movable_pairs = set(search_space["movable_pair_indices"])
    do_not_move = set(payload["expert_assertions_used"]["do_not_move_pairs"])
    assert not movable_pairs.intersection(do_not_move)
    assert 8 in do_not_move and 8 not in movable_pairs
    assert 8 in search_space["score_only_frozen_pair_indices"]
    assert search_space["fixed_anchor_pair_indices"] == [4, 8]
    assert search_space["order_mutation_allowed"] is False
    assert search_space["merge_delete_allowed"] is False
    assert search_space["auto_reorder_allowed"] is False
    assert search_space["topology_rewrite_allowed"] is False

    assert payload["search_config"]["step_schedule"] == [1.0, 0.5, 0.25, 0.125]
    assert payload["search_config"]["randomness_used"] is False
    assert payload["search_trace"]
    assert [row["step_size"] for row in payload["search_trace"]] == [
        1.0,
        0.5,
        0.25,
        0.125,
    ]
    for row in payload["search_trace"]:
        for field in (
            "round_index",
            "generated_count",
            "retained_count",
            "best_score",
            "best_candidate_id",
            "primary_edge_residual_before",
            "primary_edge_residual_after",
            "reason_for_stopping",
        ):
            assert field in row

    required_score_fields = {
        "primary_edge_6_7_residual",
        "wall_2_3_surface_or_heading_residual",
        "wall_5_6_7_8_footprint_residual",
        "y_height_consistency_residual_pairs_1_2_5_6_7_8",
        "short_wall_penalty",
        "movement_penalty",
        "anchor_violation_penalty",
        "assertion_violation_penalty",
        "fold_or_self_intersection_penalty",
        "local_score_total",
    }
    assert required_score_fields.issubset(payload["baseline"]["score_breakdown"])
    assert payload["candidates"]
    for candidate in payload["candidates"]:
        assert required_score_fields.issubset(candidate["score_breakdown"])
        assert isinstance(candidate["assertion_compliant"], bool)
        assert isinstance(candidate["assertion_violations"], list)
        assert candidate["order_mutation"] is False
        assert candidate["merge_delete"] is False
        assert candidate["auto_reorder"] is False
        assert candidate["topology_rewrite"] is False
        assert set(candidate["changed_pair_indices"]).issubset(movable_pairs)
        assert 8 not in candidate["changed_pair_indices"]
        if candidate["direct_ls_trial_allowed"]:
            assert candidate["direct_trial_gate"]["passed"] is True
            assert not candidate["direct_trial_gate"]["failed_checks"]

    assert payload["overall_verdict"]["direct_fix_available"] is False
    assert payload["overall_verdict"]["verdict"] == "no_direct_fix_available"
    assert not any(row["direct_ls_trial_allowed"] for row in payload["candidates"])
    assert all(not row["direct_ls_trial_allowed"] for row in payload["top_candidates"])
    assert any(
        "not a correctness claim" in explanation
        for row in payload["candidates"]
        for explanation in row["allowed_short_edge_explanations"]
    )

    report = paths["report"].read_text(encoding="utf-8")
    for expected in (
        "Baseline problem summary from M15.25",
        "Movable variables",
        "Fixed anchors",
        "Score components",
        "Best candidate",
        "Top 5 candidates",
        "Search trace",
        "no_direct_fix_available",
    ):
        assert expected in report
