import pytest

from tools.thesis_main.analysis.structural_support_comparison_20261108 import support_rows, team_counts


def group(name, workers, selected):
    return dict(feature_id=name, support=len(workers), selected=selected,
                members=[dict(worker=w, id=w, pair_index=0) for w in workers])


def test_strict_majority_tie_minority_and_unresolved_output_are_distinct():
    groups = [group("majority", "abcd", True), group("tie", "abc", True),
              group("minority", "ef", False)]
    rows = support_rows(groups, 6, "e", None)
    assert [r["support_kind"] for r in rows] == ["strict_majority", "tie", "minority"]
    assert all(r["in_complete_output"] is None for r in rows)
    totals = team_counts(rows)
    assert totals["misses_strict_majority"] and totals["includes_minority"]
    assert totals["strict_majority_in_medoid"] == 0
    assert totals["minority_in_medoid"] == 1


def test_complete_output_ids_and_duplicate_people():
    rows = support_rows([group("a", "abc", True)], 4, "a", {"a"})
    assert rows[0]["in_complete_output"] and rows[0]["in_medoid"]
    bad = group("a", "aab", True)
    with pytest.raises(AssertionError):
        support_rows([bad], 4, "a", {"a"})
