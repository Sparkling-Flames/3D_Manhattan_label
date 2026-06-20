import hashlib
import json
from pathlib import Path

from tools.paper_a_manhattan.manhattan_m1527_semantic_direct_search import (
    ACTION_FAMILIES,
    SAFETY_BOUNDARY,
    manual_review_candidate_available,
)
from tools.paper_a_manhattan.run_m1527_semantic_direct_search import run


PROTECTED_FILES = (
    Path("tools/paper_a_manhattan/manhattan_3d_projection.py"),
    Path("tools/paper_a_manhattan/manhattan_m1520_local_candidate_search.py"),
    Path("tools/paper_a_manhattan/run_m1520_local_candidate_search.py"),
    Path("tools/label_studio/vis_3d.html"),
)


def _digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_m1527_semantic_direct_search(tmp_path):
    before = {path: _digest(path) for path in PROTECTED_FILES}
    paths = run(tmp_path)
    assert {path: _digest(path) for path in PROTECTED_FILES} == before
    assert {path.name for path in tmp_path.iterdir()} == {
        "semantic_direct_search.json",
        "semantic_direct_search.md",
    }

    payload = json.loads(paths["json"].read_text(encoding="utf-8"))
    assert payload["schema_version"] == "m15_27_1_semantic_direct_search_v1"
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
    assert payload["semantic_action_families"] == ACTION_FAMILIES
    assert payload["semantic_variable_mapping"] == {
        "x": "azimuth",
        "top_y": "wall_height",
        "bottom_y": "floor_depth",
    }
    cluster = payload["dominant_height_cluster"]
    assert cluster["source_metric"] == "projected_wall_height"
    assert cluster["target_pair_indices"] == [1, 2, 5, 6, 7, 8]
    assert cluster["cluster_members"]
    assert cluster["height_outliers"]
    assert payload["search_trace"]
    assert set(payload["family_evaluation_counts"]) == set(ACTION_FAMILIES)
    assert payload["evaluation_count"] <= payload["search_config"]["max_evaluations"]
    assert len(payload["top_candidates"]) <= 5
    assert "candidates" not in payload
    assert payload["search_config"]["order_mutation_allowed"] is False
    assert payload["search_config"]["merge_delete_allowed"] is False
    assert payload["search_config"]["topology_rewrite_allowed"] is False
    for row in payload["top_candidates"]:
        assert row["order_mutation"] is False
        assert row["merge_delete"] is False
        assert row["topology_rewrite"] is False
        assert row["action_family"] in ACTION_FAMILIES
        assert isinstance(row["failure_reason"], list)
    verdict = payload["overall_verdict"]
    assert "direct_fix_available" not in verdict
    assert verdict["automatic_fix_claimed"] is False
    assert verdict["best_candidate_requires_visual_review"] is True
    if verdict["manual_review_candidate_available"]:
        assert payload["top_candidates"][0]["direct_ls_trial_allowed"] is True
    assert manual_review_candidate_available(payload) is verdict["manual_review_candidate_available"]
    assert manual_review_candidate_available(
        {"schema_version": "m15_27_semantic_direct_search_v1", "overall_verdict": {"direct_fix_available": True}}
    ) is True

    report = paths["report"].read_text(encoding="utf-8")
    assert "Manual-review candidate available: `True`" in report
    assert "Automatic fix claimed: `False`" in report
    assert "Direct fix available" not in report

    source = Path("tools/paper_a_manhattan/manhattan_m1527_semantic_direct_search.py").read_text(encoding="utf-8").lower()
    for forbidden in ("fetch(", "label studio api", "submit", "formal_g_t"):
        assert forbidden not in source
