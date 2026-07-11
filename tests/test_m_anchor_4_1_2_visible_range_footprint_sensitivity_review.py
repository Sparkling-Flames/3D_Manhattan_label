import json
from pathlib import Path

from tools.paper_a_manhattan.run_m_anchor_4_1_2_visible_range_footprint_sensitivity_review import CONSTRAINTS_PATH, run


def test_m_anchor_4_1_2_reads_visible_range_sidecar_and_marks_d(tmp_path: Path) -> None:
    sidecar = tmp_path / "constraints.json"; sidecar.write_bytes(CONSTRAINTS_PATH.read_bytes())
    paths = run(tmp_path / "out", tmp_path / "review", sidecar)
    audit = json.loads(paths["audit"].read_text(encoding="utf-8"))
    assert audit["stages_executed"] == ["A", "B", "C", "D"]
    assert audit["stage_stats"]["A"]["effective_core_beam"] >= 3
    assert audit["stage_stats"]["D"]["effective_core_beam"] >= 2
    assert audit["m_anchor_4_2_height_completion_authorized"] is False
    report = paths["review_report"].read_text(encoding="utf-8")
    assert "no numeric change" not in report
    assert "Δ -0.050" in report
