from pathlib import Path


def test_c6_5a_5_1_is_completed_not_next_step():
    text = Path(
        "docs/paper_a_manhattan/HRC_STABILIZATION_STATUS_v1.md"
    ).read_text(encoding="utf-8")
    assert "C6.5a.5.1 completed" in text
    assert "当前唯一允许下一步为 C6.5a.5.1" not in text
    assert "C6.5a.6.1 fixed pair2 y-step sweep audit 已物化" in text
    assert "`+0.25/+0.50/+0.75/+1.00`" in text
