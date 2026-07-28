from tools.thesis_main.analysis.c1_structural_reliability_eb import estimate_structural_reliability


def test_structural_eb_reports_raw_and_shrunk_values():
    rows = ([{"worker_id": "w1", "structural_opportunity_eligible": True, "failure_attribution": "worker_caused_structural_failure"}] * 2
            + [{"worker_id": "w1", "structural_opportunity_eligible": True, "failure_attribution": "none"}] * 2
            + [{"worker_id": "w2", "structural_opportunity_eligible": True, "failure_attribution": "none"}] * 8)
    manifest = {"thresholds": {"serious_recurrent_failure_minimum_count": 2, "serious_recurrent_failure_minimum_rate": .25}}
    output, audit = estimate_structural_reliability(rows, policy_manifest=manifest)
    assert {row["worker_id"] for row in output} == {"w1", "w2"}
    assert all(0 < row["F_struct_EB"] < 1 and row["F_struct_interval_upper"] > row["F_struct_interval_lower"] for row in output)
    assert audit["prior_status"] in {"marginal_likelihood", "fallback"}
