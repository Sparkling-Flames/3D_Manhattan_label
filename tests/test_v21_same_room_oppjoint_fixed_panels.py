import json

import numpy as np
import pandas as pd
import pytest

from tools.thesis_main.analysis.reaggregate_v21_same_room_oppjoint_fixed_panels_20261029 import (
    METHODS, aggregate, annotate_compositions, join_endpoints, load_engine, summarize, verify_nested_moments,
)


def example():
    panels = pd.DataFrame([dict(panel_id="p", building="B", n=2, pool_id_a="a", pool_id_b="b", reference_id_a="ra", reference_id_b="rb")])
    links = pd.DataFrame([dict(panel_id="p", member_set_key="w1|w2", team_key_a="a12", team_key_b="b12")])
    labels = pd.DataFrame([dict(method=m, heldout_building="B", worker_id=w,
                               class_id="C1", known=(w == "w1"),
                               label_stage="leave_target_building_out", input_conditions="manual", evaluation_condition="manual")
                           for m in METHODS for w in ["w1", "w2"]])
    return panels, links, labels


def test_full_team_unknowns_and_fold_identity():
    panels, links, labels = example()
    result = annotate_compositions(panels, links, labels)
    assert json.loads(result.iloc[0].OPPJOINT_K3_vector) == {"C1": 1, "unknown": 1}
    assert not result.iloc[0].both_methods_all_known
    labels["heldout_building"] = "ALL"
    with pytest.raises(AssertionError):
        annotate_compositions(panels, links, labels)


def test_duplicate_members_and_duplicate_labels_rejected():
    panels, links, labels = example()
    links["member_set_key"] = "w1|w1"
    with pytest.raises(AssertionError):
        annotate_compositions(panels, links, labels)
    panels, links, labels = example()
    with pytest.raises(AssertionError):
        annotate_compositions(panels, links, pd.concat([labels, labels.iloc[[0]]]))


def test_endpoint_identity_and_missing_time_preserved():
    panels, links, _ = example()
    endpoints = pd.DataFrame([dict(team_key=s + "12", member_workers="w1|w2", k=2,
                                  building="B", pool_id=s, reference_id="r" + s, condition="manual",
                                  complete_evaluable=(s == "a"), recorded_time_eligible=(s == "a"),
                                  recorded_time_total_seconds=10, B8L2=20 if s == "a" else np.nan)
                              for s in ["a", "b"]])
    result = join_endpoints(panels, links, endpoints, ["B8L2", "failure", "log_recorded_time"])
    assert np.isnan(result.iloc[0].B8L2_b)
    assert result.iloc[0].failure_b == 1
    assert np.isnan(result.iloc[0].log_recorded_time_b)
    endpoints.loc[1, "member_workers"] = "w1|w3"
    with pytest.raises(AssertionError):
        join_endpoints(panels, links, endpoints, ["B8L2"])


def test_reused_moments_separate_composition_and_member_response():
    engine = load_engine()
    group = pd.DataFrame({"B8L2_a": [0., 2., 4., 6., np.nan], "B8L2_b": [0., 4., 8., 12., 99.],
                          "OPPJOINT_K3_vector": ["x", "x", "y", "y", "z"]})
    result = engine.moments(group, "B8L2", "OPPJOINT_K3")
    assert result["n_requested"] == 5 and result["n_joint_finite"] == 4
    assert result["total_var_a"] == 5
    assert result["between_var_a"] == 4 and result["within_var_a"] == 1
    assert result["between_cov"] + result["within_cov"] == result["total_cov"]
    assert result["member_residual_rho"] == pytest.approx(1)


def test_complete_support_and_aggregation_flow():
    engine = load_engine()
    panel = dict.fromkeys(engine.META, 0)
    panel.update(panel_id="p", pair_key="a|b", building="B", groups="g", n=3,
                 method="V3_BEHAVIOR", ordinary_comparable=True, scope_comparable=True,
                 mid_n=3, is_primary_budget=True)
    rows = []
    for i in range(4):
        row = {"panel_id": "p", "both_methods_all_known": i != 3}
        for method in METHODS:
            row[method + "_all_known"] = i != 3
            row[method + "_vector"] = str(i // 2)
        for metric in engine.METRICS:
            row[metric + "_a"] = float(i)
            row[metric + "_b"] = float(i * 2)
        rows.append(row)
    moments, support = summarize(pd.DataFrame([panel]), pd.DataFrame(rows), engine)
    verify_nested_moments(moments)
    assert support.iloc[0].requested_team_pairs == 4
    assert support.iloc[0].common_known_team_pairs == 3
    assert set(moments.n_joint_finite) == {3}
    summary = aggregate(moments, engine)[-1]
    assert set(summary.valid_team_pair_occurrences) == {3}
