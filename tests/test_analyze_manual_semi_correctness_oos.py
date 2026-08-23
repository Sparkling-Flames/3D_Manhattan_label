from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from tools.thesis_main.analysis.full_uncertainty.analyze_manual_semi_correctness_oos_20260823 import write_csv


ROOT = Path(__file__).resolve().parents[1]


def test_outputs_are_cross_platform_and_do_not_replace_formal_t1(tmp_path: Path) -> None:
    sample = tmp_path / "sample.csv"
    write_csv(pd.DataFrame([{"value": 1}, {"value": 2}]), sample)
    assert b"\r\n" not in sample.read_bytes()

    output = ROOT / "analysis_results/manual_semi_correctness_oos_20260823"
    designs = pd.read_csv(output / "DESIGN_OPTIONS_RESOURCE_ACCOUNTING.csv", encoding="utf-8-sig")
    validation = json.loads((output / "VALIDATION.json").read_text(encoding="utf-8"))
    assert designs["formal_t1_eligible"].eq(False).all()  # noqa: E712
    assert designs["assignment_manifest_materialized"].eq(False).all()  # noqa: E712
    assert set(designs["status"]) == {"exploratory_alternative_study_not_frozen_t1"}
    assert validation["formal_t1_contract_unchanged"] is True
    assert validation["design_feasibility_status"] == "resource_arithmetic_only"
