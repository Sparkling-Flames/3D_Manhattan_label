import json
from pathlib import Path

import pytest

from tools.paper_a_manhattan.materialize_manhattan_feedback_ledger_entry import (
    materialize_entry,
    run,
)


ROOT = "analysis_results/paper_a_manhattan"


def _core():
    evaluation = {
        "evaluator_version": "manhattan_constrained_hypothesis_evaluator_v1",
        "decision_class": "hard_feasible_improving_evidence_unavailable",
    }
    return {
        "schema_version": "manhattan_constrained_hypothesis_ranking_core_v1",
        "state_before": {"ordered_pairs": [], "projection_config": {"width": 1024}},
        "case_contract": {"schema_version": "manhattan_case_contract_v1"},
        "candidate_set": [
            {"candidate_id": "c1", "action_family": "legacy_height_probe"},
            {"candidate_id": "c2", "action_family": "legacy_x_probe"},
        ],
        "constrained_evaluations": {"c1": evaluation, "c2": evaluation},
    }


def _review():
    return {
        "shown_rank": ["c1", "c2"],
        "expert_selected_candidate": "c1",
        "expert_rejected_candidates": ["c2"],
        "manual_edit_after_candidate": None,
        "final_layout": {"ordered_pairs": []},
        "delta_candidate_to_final": None,
        "accepted_directly": True,
        "accepted_after_minor_edit": False,
        "rejected_reason_optional": {"c2": "height case should not be displaced by x-only edit"},
        "case_tags": ["height_dominant"],
    }


def test_materializes_feedback_ledger_schema_and_jsonl(tmp_path):
    entry = materialize_entry(_core(), _review())
    required = {
        "state_before",
        "case_contract",
        "candidate_set",
        "candidate_metrics",
        "shown_rank",
        "expert_selected_candidate",
        "expert_selected_candidate_role",
        "expert_rejected_candidates",
        "candidate_verdicts",
        "manual_edit_after_candidate",
        "final_layout",
        "final_layout_available",
        "delta_candidate_to_final",
        "accepted_directly",
        "accepted_after_minor_edit",
        "rejected_reason_optional",
        "case_tags",
        "action_family",
        "parameter_snapshot",
        "ranker_version",
        "evaluator_version",
    }
    assert set(entry) == required
    assert entry["action_family"] == "legacy_height_probe"
    assert entry["final_layout_available"] is True

    core_path, review_path, output_path = (
        tmp_path / "core.json",
        tmp_path / "review.json",
        tmp_path / "ledger.jsonl",
    )
    core_path.write_text(json.dumps(_core()), encoding="utf-8")
    review_path.write_text(json.dumps(_review()), encoding="utf-8")
    run(core_path, review_path, output_path)
    assert len(output_path.read_text(encoding="utf-8").splitlines()) == 1
    assert json.loads(output_path.read_text(encoding="utf-8"))["ranker_version"].endswith("_v1")


def test_rejects_unknown_candidate_and_conflicting_acceptance():
    review = _review()
    review["expert_selected_candidate"] = "missing"
    with pytest.raises(ValueError, match="unknown candidates"):
        materialize_entry(_core(), review)
    review = _review()
    review["accepted_after_minor_edit"] = True
    with pytest.raises(ValueError, match="mutually exclusive"):
        materialize_entry(_core(), review)


def test_materializes_task218_0017_directional_not_final_review(tmp_path):
    core_path = Path(ROOT) / (
        "hypothesis_ranking_core/task218_ann3741/hypothesis_ranking_core.json"
    )
    review_path = Path(ROOT) / (
        "hypothesis_feedback_reviews/"
        "task218_ann3741_m1528_candidate_0017_review.json"
    )
    output_path = tmp_path / "ledger.jsonl"
    run(core_path, review_path, output_path)
    entry = json.loads(output_path.read_text(encoding="utf-8"))

    assert entry["expert_selected_candidate"] == "m1528_candidate_0017"
    assert entry["accepted_directly"] is False
    assert entry["accepted_after_minor_edit"] is False
    assert entry["final_layout_available"] is False
    assert (
        entry["candidate_verdicts"]["m1528_candidate_0017"]["verdict"]
        == "reject_as_final_but_directionally_useful"
    )
    assert {
        "dense_corner",
        "local_improvement_not_global_fix",
        "short_wall_warning_not_visual_reject",
        "requires_broader_refit",
    }.issubset(entry["case_tags"])
    forbidden = {"annotation_patch", "label_studio_writeback", "model_training"}
    assert forbidden.isdisjoint(entry)
