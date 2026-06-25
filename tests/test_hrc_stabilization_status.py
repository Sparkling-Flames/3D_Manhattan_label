from pathlib import Path


def test_c6_5a_7_is_completed_without_authorizing_c6_5b():
    text = Path(
        "docs/paper_a_manhattan/HRC_STABILIZATION_STATUS_v1.md"
    ).read_text(encoding="utf-8")
    assert "C6.5a.7 blocker closure audit completed" in text
    assert "`+0.25/+0.50/+0.75/+1.00`" in text
    assert "c6_5a_6_1_candidate_0003" in text
    assert "C6.5b 未授权" in text
