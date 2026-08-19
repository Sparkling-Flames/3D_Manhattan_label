import csv
import json
from pathlib import Path

from tools.thesis_main.analysis.analyze_post_block2_opportunities import (
    BOOTSTRAPS,
    OUT,
    PACK,
    clustered_simulation_power,
    corner_count,
    verify_pack,
)


def rows(path: Path):
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def test_v3_pack_is_qa_approved_and_has_required_inputs():
    audit = verify_pack()
    assert audit["artifact_count"] >= 18
    assert (PACK / "worker_profile_uncertainty_inputs.csv").is_file()
    assert (PACK / "empirical_variance_inputs.json").is_file()


def test_corner_count_uses_wall_pair_count_and_rejects_odd_orphans():
    assert corner_count({"corners_px": [[0, 0]] * 8}) == 4
    assert corner_count({"corners_px": [[0, 0]] * 12}) == 6
    assert corner_count({"corners_px": [[0, 0]] * 9}) == 0


def test_a0_reconstruction_and_gt_firewall():
    payload = json.loads((OUT / "POST_BLOCK2_AGGREGATION_OPPORTUNITY_AUDIT" / "aggregation_power_inputs.json").read_text(encoding="utf-8"))
    assert payload["a0_reconstruction"] == {"all_match": True, "matches": 101, "tasks_checked": 101}
    selector = rows(OUT / "POST_BLOCK2_AGGREGATION_OPPORTUNITY_AUDIT" / "cross_fitted_selector_results.csv")
    assert all(row["gt_used_for_selection"] == "False" for row in selector if row["method"] != "A_oracle_evaluator_only")
    assert all(not row["selected_worker_id"] for row in selector if row["method"] == "A4_image_evidence_weighted_cluster_selector")


def test_cluster_simulation_is_seeded_and_manifest_records_1000():
    first = clustered_simulation_power(.02, .001, 40, 5, .05, 123)
    second = clustered_simulation_power(.02, .001, 40, 5, .05, 123)
    assert first == second
    assert 0 <= first <= 1
    manifest = json.loads((OUT / "analysis_manifest.json").read_text(encoding="utf-8"))
    assert BOOTSTRAPS >= 1000
    assert manifest["bootstrap_replicates"] >= 1000
    assert manifest["scientific_confirmation"] is False
    assert manifest["policy_freeze"] is False
    assert manifest["block3_generated"] is False


def test_routing_replay_does_not_invent_counterfactual():
    replay = rows(OUT / "POST_BLOCK2_MATCHED_ROUTING_FEASIBILITY" / "routing_replay_if_valid.csv")
    assert replay
    assert all(row["status"] == "not_evaluable" for row in replay)
    assert all(row["cost_claim"] == "not_identifiable" for row in replay)
