import json
from pathlib import Path

import pytest

from tools.paper_a_manhattan.run_m_anchor_4_1_2_1_visible_range_closure import run as run_closure
from tools.paper_a_manhattan.run_m_anchor_4_1_2_visible_range_footprint_sensitivity_review import CONSTRAINTS_PATH, _validate, run


def test_m_anchor_4_1_2_reads_visible_range_sidecar_and_marks_d(tmp_path: Path) -> None:
    sidecar = tmp_path / "constraints.json"; sidecar.write_bytes(CONSTRAINTS_PATH.read_bytes())
    paths = run(tmp_path / "out", tmp_path / "review", sidecar)
    audit = json.loads(paths["audit"].read_text(encoding="utf-8"))
    assert audit["stages_executed"] == ["A", "B", "C", "D"]
    assert audit["stage_stats"]["A"]["effective_core_beam"] >= 3
    assert audit["stage_stats"]["D"]["effective_core_beam"] >= 2
    assert audit["m_anchor_4_2_height_completion_authorized"] is False
    for card in audit["review_candidates"]:
        assert card["decision"] == card["candidate_class"]
        if card["search_stage"] == "D":
            assert "maximum_absolute_delta_le_0_5" not in card["hard_gate"]
            assert card["sensitivity_only"] is True
            assert card["m_anchor_4_2_input_eligible"] is False
    report = paths["review_report"].read_text(encoding="utf-8")
    assert "no numeric change" not in report
    assert "Δ -0.050" in report


def test_m_anchor_4_1_2_1_closure_materializes_visibility_slices(tmp_path: Path) -> None:
    paths = run_closure(tmp_path / "out", tmp_path / "review")
    audit = json.loads(paths["audit"].read_text(encoding="utf-8"))
    manifest = json.loads(paths["manifest"].read_text(encoding="utf-8"))
    assert audit["schema_version"] == "m_anchor_4_1_2_1_closure_audit_v1"
    assert audit["stage_id"] == "M-Anchor.4.1.2.1"
    assert len(audit["review_candidates"]) == 4 and len(audit["visibility_candidates"]) == 9
    assert all(row["hard_gate_passed"] and row["m_anchor_4_2_input_eligible"] is False for row in audit["visibility_candidates"])
    assert manifest["case_name"] == "task218_ann3741_m_anchor_4_1_2_1"
    assert len(manifest["candidates"]) == 4 and len(manifest["visibility_candidates"]) == 9
    report = paths["review_report"].read_text(encoding="utf-8")
    html = paths["review_html"].read_text(encoding="utf-8")
    assert "SENSITIVITY ONLY" in report and "SENSITIVITY ONLY" in html
    assert manifest["visibility_candidates"][-1]["candidate_id"] in report


@pytest.mark.parametrize("key,value", [("forbidden_variables", []), ("pair_axis_ranges", {}), ("hard_anchor_clipping_policy", "ignore"), ("safety_boundary", {})])
def test_m_anchor_4_1_2_sidecar_validation_is_fail_closed(key: str, value: object) -> None:
    doc = json.loads(CONSTRAINTS_PATH.read_text(encoding="utf-8")); doc[key] = value
    with pytest.raises(ValueError): _validate(doc)
