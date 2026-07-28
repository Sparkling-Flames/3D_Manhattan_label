from tools.thesis_main.analysis.materialize_counterexample_bank import materialize_counterexample_bank
import csv


def test_candidate_is_not_failure_reference_change_profile_or_prevalence(tmp_path):
    summary = materialize_counterexample_bank([{"base_task_id": "b", "trigger": "gt_conflict"}], tmp_path)
    text = (tmp_path / "counterexample_candidates.csv").read_text(encoding="utf-8")
    assert "True,False,False,False,False" in text
    assert summary["prevalence_estimation_allowed"] is False
    assert "prevalence" not in text


def test_candidate_id_is_stable_deduplicated_and_preserves_adjudication(tmp_path):
    event = {"stage": "C1", "base_task_id": "b", "canonical_annotation_id": "a", "trigger": "process_integrity", "trigger_rule_version": "v1"}
    materialize_counterexample_bank([event, event], tmp_path)
    with (tmp_path / "counterexample_candidates.csv").open(encoding="utf-8") as stream:
        candidates = list(csv.DictReader(stream))
    assert len(candidates) == 1
    adjudicated = {**candidates[0], "adjudication": "system_or_policy_issue", "reviewed_by": "r", "reviewed_at": "t", "notes": "keep"}
    with (tmp_path / "counterexample_adjudicated.csv").open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(adjudicated)); writer.writeheader(); writer.writerow(adjudicated)
    materialize_counterexample_bank([event], tmp_path)
    assert "system_or_policy_issue" in (tmp_path / "counterexample_adjudicated.csv").read_text(encoding="utf-8")
