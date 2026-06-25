from pathlib import Path


def test_c6_5a_7_1_is_completed_without_authorizing_c6_5b():
    text = Path(
        "docs/paper_a_manhattan/HRC_STABILIZATION_STATUS_v1.md"
    ).read_text(encoding="utf-8")
    assert "C6.5a.7.1 human verdict materialization completed" in text
    assert "`+0.25/+0.50/+0.75/+1.00`" in text
    assert "c6_5a_6_1_candidate_0003" in text
    assert "C6.5b 未授权" in text
    assert "pair2" in text
    assert "4–5" in text
    assert "candidate_specific_image_evidence_available=false" in text
    assert "candidate_specific_c4_contract_complete=false" in text
    assert "C6.5a.9 已物化" in text
    assert "corner 来自相邻墙线交点" in text
