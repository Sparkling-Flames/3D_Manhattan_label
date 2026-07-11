import copy
import json
from pathlib import Path

import pytest

from tools.paper_a_manhattan.run_m_anchor_4_1_3_occlusion_aware_refinement import (
    SOURCE_DIR,
    _evidence,
    _validate_s10_cards,
    _validate_evidence,
    run,
)


@pytest.fixture(scope="module")
def artifacts(tmp_path_factory):
    root = tmp_path_factory.mktemp("m413")
    paths = run(root / "out", root / "review")
    return paths, json.loads(paths["audit"].read_text(encoding="utf-8"))


def test_evidence_contract_rejects_unknown_enum_and_unreviewed_authorization():
    assert len(_evidence()["pairs"][3]["variables"]["pair_x"]["sensitivity_observations"]) == 3
    doc = _evidence(); doc["pairs"][2]["variables"]["pair_x"]["evidence"] = "invented"
    with pytest.raises(ValueError, match="enum"):
        _validate_evidence(doc)
    doc = _evidence(); doc["pairs"][0]["compensation_allowed"] = True
    with pytest.raises(ValueError, match="unconfirmed identity"):
        _validate_evidence(doc)
    doc = _evidence(); doc["pairs"][2]["identity_status"] = "ambiguous"
    with pytest.raises(ValueError, match="identity"):
        _validate_evidence(doc)


def test_occlusion_contract_supports_only_hidden_semantic_latent_variable():
    doc = _evidence(); pair = doc["pairs"][2]
    pair.update(identity_status="confirmed", existence_status="confirmed", order_status="confirmed", compensation_allowed=True, top_endpoint_visibility="visible_weak", bottom_endpoint_visibility="unobservable")
    pair["variables"]["pair_x"].update(evidence="visible_weak", solver_role="soft_anchor", current_stage_authorized=False)
    pair["variables"]["bottom_y"].update(evidence="unobservable", solver_role="latent_completion", current_stage_authorized=True)
    _validate_evidence(doc)
    pair["variables"]["pair_x"].update(evidence="unobservable", solver_role="latent_completion")
    with pytest.raises(ValueError, match="both endpoints"):
        _validate_evidence(doc)


def test_m413_materializes_s3_supersession_six_ablations_and_safe_candidates(artifacts):
    paths, audit = artifacts
    contract = json.loads(paths["contract"].read_text(encoding="utf-8"))
    assert contract["fail_closed"] is False
    assert {row["constraint_id"] for row in contract["superseded_constraints"]} == {"s3_top_x", "s3_top_y", "s3_bottom_x", "s3_bottom_y"}
    ablation = json.loads(paths["ablation"].read_text(encoding="utf-8"))["candidates"]
    assert {row["candidate_id"] for row in ablation} == {
        "m_anchor_4_1_3_c1976_full", "m_anchor_4_1_3_c1976_minus_s3",
        "m_anchor_4_1_3_c1976_minus_s7", "m_anchor_4_1_3_c1976_visible_only",
        "m_anchor_4_1_3_c1976_s10_only", "m_anchor_4_1_3_c1976_hidden_compensation_only",
    }
    for row in audit["candidates"]:
        assert row["accepted"] is False and row["annotation_writeback"] is False
        assert row["m_anchor_4_2_input_eligible"] is False
        assert all(field["before"] == field["after"] for change in row["coordinate_changes"] for name, field in change["fields"].items() if name == "top_y")
        assert row["candidate_class"] != "rejected_hard_gate"
    assert audit["source_artifacts_tree_sha256_before"] == audit["source_artifacts_tree_sha256_after"]


def test_s10_pure_and_context_candidates_obey_their_distinct_contracts(artifacts):
    paths, _ = artifacts
    cards = [json.loads(line) for line in paths["s10"].read_text(encoding="utf-8").splitlines()]
    pure = [row for row in cards if row["candidate_kind"] != "c1976_context_s10_refinement"]
    context = [row for row in cards if row["candidate_kind"] == "c1976_context_s10_refinement"]
    assert [row["movement_by_semantic_axis"]["s10_pair_x"] for row in pure] == [0.5, 0.6, 0.7, 0.8, 1.0]
    assert all(set(row["movement_by_semantic_axis"]) == {"s10_pair_x"} for row in pure)
    assert context[0]["movement_by_semantic_axis"].keys() == context[-1]["movement_by_semantic_axis"].keys()
    assert all(row["not_solver_candidate"] and row["sensitivity_only"] for row in cards)
    invalid = copy.deepcopy(cards); invalid[0]["coordinate_changes"][0]["fields"]["top_x"]["delta"] = 0.9
    invalid[0]["coordinate_changes"][0]["fields"]["bottom_x"]["delta"] = 0.9
    with pytest.raises(ValueError, match="outside approved bracket"):
        _validate_s10_cards(invalid, {})


def test_review_uses_original_for_2d_compressed_for_3d_and_keeps_safety(artifacts):
    paths, _ = artifacts
    metrics = json.loads(paths["review_json"].read_text(encoding="utf-8"))
    provenance = metrics["input_provenance"]
    assert provenance["image"]["image_path"].endswith(".jpg")
    assert provenance["overlay_image"]["image_path"].endswith(".png")
    assert len(metrics["variants"]) == 6
    report = paths["review_report"].read_text(encoding="utf-8")
    html = paths["review_html"].read_text(encoding="utf-8")
    assert "audit-only" in report and "M4.2" in report
    for token in ("point radius", "marker diameter", "Active candidate changes", "Expert Evidence", "overlayImageUrl", 'min=".25"', 'value=".35"'):
        assert token in html
    assert SOURCE_DIR.exists()
