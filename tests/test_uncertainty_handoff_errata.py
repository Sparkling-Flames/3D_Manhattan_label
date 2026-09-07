from __future__ import annotations

import numpy as np
import pandas as pd

from tools.thesis_main.analysis import uncertainty_handoff_errata as errata


def test_initialization_join_is_condition_and_block_exact():
    contexts = pd.DataFrame([
        {"context_key": "C1|1|img|manual", "stage": "C1", "image_id": "img", "condition": "manual", "raw_count": 2, "initialization_source_kind": "wrong"},
        {"context_key": "C1|1|img|semi", "stage": "C1", "image_id": "img", "condition": "semi", "raw_count": 2, "initialization_source_kind": "old"},
        {"context_key": "C1|2|img|semi", "stage": "C1", "image_id": "img", "condition": "semi", "raw_count": 2, "initialization_source_kind": "old"},
    ])
    proposals = pd.DataFrame([
        {"stage": "C1", "block_index": "1", "image_id": "img", "initialization_source_kind": "proposal_block1"},
        {"stage": "C1", "block_index": "2", "image_id": "img", "initialization_source_kind": "proposal_block2"},
    ])
    proposals["proposal_id"] = ["p1", "p2"]
    responses = pd.DataFrame([{"proposal_id": "p1", "raw_condition": "semi"}, {"proposal_id": "p2", "raw_condition": "semi"}])
    fixed, _ = errata.corrected_initialization(contexts, proposals, responses)
    assert fixed.initialization_source_kind.tolist() == ["manual_or_not_recorded", "proposal_block1", "proposal_block2"]


def test_constant_bootstrap_draw_is_invalid_and_denominator_is_not_replaced():
    value, status = errata.rho_status(np.ones(5), np.arange(5.0))
    assert np.isnan(value)
    assert status == "invalid_constant_x"
    assert errata.REQUESTED == 500


def test_replay_retains_invalid_draws_in_fixed_denominator():
    rows = []
    for building, x in [("A", 0.0), ("B", 1.0), ("C", 2.0)]:
        for index in range(4):
            rows.append({
                "context_key": f"P1|0|{building}_{index}|manual", "image_id": f"{building}_{index}",
                "building_id": building, "stage": "P1", "condition": "manual", "floor_count": 3,
                "initialization_source_kind": "manual_or_not_recorded", "bi_floor": x, "bi_band": x,
                "bi_linear": x, "bi_solid": x, "d_floor": index, "d_band": index,
                "d_linear": index, "d_solid": index, "cluster_count": index,
            })
    contexts = pd.DataFrame(rows)
    old = pd.DataFrame([
        {"scope": scope, "stratum": stratum, "x": x, "y": y, "ci_low": np.nan, "ci_high": np.nan}
        for scope in ["extended73", "without_synthetic", "all_n3"]
        for stratum in ["all", "P1|manual"]
        for x, y in [("bi_floor", "d_floor"), ("bi_band", "d_band"), ("bi_linear", "d_linear"), ("bi_solid", "d_solid"), ("bi_floor", "cluster_count")]
    ])
    summary, draws = errata.replay_associations(contexts, contexts, old)
    attempted = summary[summary.bootstrap_requested_n == errata.REQUESTED]
    assert len(draws) == len(attempted) * errata.REQUESTED
    assert (attempted.bootstrap_evaluable_n + attempted.bootstrap_invalid_n).eq(errata.REQUESTED).all()
    assert attempted.bootstrap_invalid_n.gt(0).any()
