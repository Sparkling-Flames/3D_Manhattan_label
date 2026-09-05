from tools.thesis_main.analysis.analyze_worker_behavior_mixture_exploratory import (
    A,
    C,
    U,
    build_worker_strata,
    classify_behavior_counts,
)


def test_behavior_rule_has_explicit_abstention() -> None:
    assert classify_behavior_counts(fixes=3, wrong_n=7, harms=1, correct_n=11) == A
    assert classify_behavior_counts(fixes=1, wrong_n=7, harms=3, correct_n=11) == C
    assert classify_behavior_counts(fixes=2, wrong_n=7, harms=2, correct_n=11) == U


def test_p1_only_panel_reproduces_expected_operational_groups() -> None:
    rows, metadata = build_worker_strata()
    assert len(rows) == 20
    assert metadata["classification_row_count"] == 360
    assert metadata["class_counts"] == {A: 9, C: 5, U: 6}
    assert all(row["correct_proposal_n"] == 11 for row in rows)
    assert all(row["wrong_proposal_n"] == 7 for row in rows)
