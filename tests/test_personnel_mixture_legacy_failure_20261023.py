import importlib.util
from pathlib import Path

import numpy as np
import pandas as pd


SCRIPT = (Path(__file__).resolve().parents[1] / "research/workers/"
          "personnel_mixture_comparison_20261022/exchanges/compare_legacy_n20.py")
spec = importlib.util.spec_from_file_location("legacy_failure", SCRIPT)
legacy = importlib.util.module_from_spec(spec)
spec.loader.exec_module(legacy)


def test_failure_contrast_keeps_events_without_three_scores():
    d = pd.DataFrame({f: [2.0, 2.0, 2.0] for f in legacy.METRICS})
    d["all_scored"] = [True, False, False]
    d["B_failure"] = [False, False, True]
    d["C_failure"] = [False, True, False]
    legacy.apply_metric_denominators(d)
    np.testing.assert_array_equal(d.net_failure_difference, [0, 1, -1])
    assert d.net_B8L2.iloc[0] == 2
    assert d.net_B8L2.iloc[1:].isna().all()


def test_failure_aggregation_uses_all_events_then_equal_images_and_buildings(monkeypatch):
    monkeypatch.setattr(legacy, "save", lambda *_: None)
    d = pd.DataFrame({f: [0.0] * 5 for f in legacy.outcome_metrics()})
    metadata = dict(condition="manual", method_id="M_structure", tier="coarse",
                    parent_fixed=False, design="strict_disjoint_ABC", n=20,
                    actual_m_AB=4, actual_m_AC=4, actual_m_BC=8,
                    seat_change_r_AC=4, difficulty="easy")
    for field, value in metadata.items():
        d[field] = value
    d["building"] = ["a", "a", "a", "a", "b"]
    d["image"] = ["a1", "a1", "a1", "a2", "b1"]
    d["physical_triple_id"] = range(5)
    d["all_scored"] = [True, False, False, True, False]
    d["B_failure"] = False
    d["C_failure"] = [False, True, True, False, True]
    d["net_B8L2"] = [4, 99, 99, 8, 99]
    legacy.apply_metric_denominators(d)
    rows = legacy.summarize(d, legacy.outcome_metrics())
    assert len(rows) == 1
    # a: mean(mean(0,1,1), 0)=1/3; b: 1; building mean=2/3.
    assert np.isclose(rows[0]["net_failure_difference"], 2 / 3)
    assert rows[0]["net_B8L2"] == 6
    assert rows[0]["events"] == 5
