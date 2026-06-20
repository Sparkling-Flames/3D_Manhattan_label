import hashlib
import json
from pathlib import Path

import pytest

from tools.paper_a_manhattan.manhattan_m1528_semantic_action_library import (
    ACTION_FAMILIES,
    ALLOWED_SHORT_DEFICIT_BAND,
    apply_action,
    build_action_specs,
    validate_secondary_assertions,
)
from tools.paper_a_manhattan.run_m1528_semantic_action_library import (
    DEFAULT_ASSERTION,
    DEFAULT_LEDGER,
    DEFAULT_PROJECTION,
    run,
)


PROTECTED = (
    Path("tools/paper_a_manhattan/manhattan_3d_projection.py"),
    Path("tools/paper_a_manhattan/manhattan_m1520_local_candidate_search.py"),
    Path("tools/paper_a_manhattan/run_m1520_local_candidate_search.py"),
    Path("tools/label_studio/vis_3d.html"),
)


def _digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_m1528_action_library_and_review_gate(tmp_path):
    before = {path: _digest(path) for path in PROTECTED}
    pending = json.loads(DEFAULT_LEDGER.read_text(encoding="utf-8"))
    pending_path = tmp_path / "pending.json"
    pending_path.write_text(json.dumps(pending), encoding="utf-8")
    with pytest.raises(ValueError, match="reviewed"):
        run(tmp_path / "blocked", ledger_path=pending_path)

    pending["manual_visual_review"].update(
        {
            "status": "reviewed",
            "comparative_verdict": "m15_27_better",
            "selected_candidate_id": "m1527_candidate_0094",
            "manual_ls_trial_recommended": True,
            "notes": "synthetic test checkpoint",
            "reviewed_at": "2026-06-20T12:00:00+00:00",
        }
    )
    reviewed_path = tmp_path / "reviewed.json"
    reviewed_path.write_text(json.dumps(pending), encoding="utf-8")
    paths = run(tmp_path / "output", ledger_path=reviewed_path)
    assert {path: _digest(path) for path in PROTECTED} == before
    payload = json.loads(paths["json"].read_text(encoding="utf-8"))
    assert payload["schema_version"] == "m15_28_semantic_action_library_v1"
    assert payload["case_contract"]["contract_source"] == "rule_based_v1"
    assert payload["legacy_score_role"] == "diagnostic_only"
    assert payload["portfolio_candidates_role"] == "legacy_diagnostic_only"
    assert payload["legacy_portfolio_candidates"] == payload["portfolio_candidates"]
    assert payload["overall_verdict"]["verdict_basis"] == "constrained_hard_gate_and_manual_review_gate"
    assert payload["portfolio_ranking"]["best_balanced"].get("candidate") or payload["portfolio_ranking"]["best_balanced"].get("reason")
    assert all("constrained_evaluation" in row and "hypothesis_ranking_key" in row for row in payload["top_candidates"])
    assert all(
        "legacy_m15_28_gate" in row
        and row["legacy_m15_28_gate"]["role"] == "legacy_diagnostic_only"
        and "constrained_hard_gate" in row
        for row in payload["top_candidates"]
    )
    assert payload["secondary_window"]["enabled"] is False
    assert payload["search_config"]["allowed_short_wall_deficit_band"] == 0.005
    assert len(payload["top_candidates"]) <= 5
    assert set(payload["portfolio_candidates"]) == {
        "best_primary_candidate",
        "best_height_candidate",
        "best_balanced_candidate",
        "best_short_wall_preserving_candidate",
        "best_low_movement_candidate",
    }
    assert payload["overall_verdict"]["automatic_fix_claimed"] is False
    for bucket in payload["portfolio_candidates"].values():
        if bucket["candidate"]:
            assert bucket["candidate"]["m15_28_gate"]["passed"] is True
            assert bucket["candidate"]["score_breakdown"]["allowed_short_wall_deficit_delta"] <= ALLOWED_SHORT_DEFICIT_BAND + 1e-12

    projection = json.loads(DEFAULT_PROJECTION.read_text(encoding="utf-8"))
    pairs = next(row for row in projection["variants"] if row["name"] == "original")["ordered_pairs"]
    assertion = json.loads(DEFAULT_ASSERTION.read_text(encoding="utf-8"))
    secondary = validate_secondary_assertions(assertion, list(range(1, 11)))
    specs = build_action_specs(pairs, payload["dominant_height_cluster"], payload["expert_assertions_used"], secondary, 1.0)
    families = {row["family"] for row in specs}
    assert set(ACTION_FAMILIES) - {"secondary_edge_2_3_semantic_probe"} <= families

    align = next(row for row in specs if row["family"] == "vertical_column_align_x" and row["operations"][0]["pair_index"] == 5)
    aligned = apply_action(pairs, align)
    pair5 = next(row for row in aligned if row["effective_pair_index"] == 5)
    assert pair5["top"]["x"] == pair5["bottom"]["x"]
    preserve = next(row for row in specs if row["family"] == "azimuth_translate_keep_top_bottom_delta" and row["operations"][0]["pair_index"] == 5)
    translated = apply_action(pairs, preserve)
    before5 = next(row for row in pairs if row["effective_pair_index"] == 5)
    after5 = next(row for row in translated if row["effective_pair_index"] == 5)
    assert after5["top"]["x"] - after5["bottom"]["x"] == pytest.approx(before5["top"]["x"] - before5["bottom"]["x"])

    enabled = validate_secondary_assertions(
        {
            "allow_secondary_window_pairs": [1, 2, 3],
            "secondary_primary_edges": ["2-3"],
            "allowed_movable_fields_for_secondary": ["top_y", "bottom_y", "x"],
        },
        list(range(1, 11)),
    )
    assert enabled["enabled"] is True
    assert any(row["family"] == "secondary_edge_2_3_semantic_probe" for row in build_action_specs(pairs, payload["dominant_height_cluster"], payload["expert_assertions_used"], enabled, 1.0))
