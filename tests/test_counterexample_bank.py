from tools.thesis_main.analysis.materialize_counterexample_bank import materialize_counterexample_bank


def test_candidate_is_not_failure_reference_change_profile_or_prevalence(tmp_path):
    summary = materialize_counterexample_bank([{"base_task_id": "b", "trigger": "gt_conflict"}], tmp_path)
    text = (tmp_path / "counterexample_candidates.csv").read_text(encoding="utf-8")
    assert "True,False,False,False,False" in text
    assert summary["prevalence_estimation_allowed"] is False
    assert "prevalence" not in text
