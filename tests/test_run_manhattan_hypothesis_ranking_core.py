import copy
import json
from pathlib import Path

from tools.paper_a_manhattan.manhattan_case_contract import build_case_contract
from tools.paper_a_manhattan.manhattan_constrained_hypothesis_evaluator import evaluate_hypothesis
from tools.paper_a_manhattan.manhattan_hypothesis_portfolio import build_hypothesis_portfolio
from tools.paper_a_manhattan.run_local_3d_projection_review import build_projection_variant
from tools.paper_a_manhattan.run_manhattan_hypothesis_ranking_core import (
    SCHEMA_VERSION,
    build_payload,
    run,
)


ROOT = Path("analysis_results/paper_a_manhattan")


def _artifact(case):
    return json.loads(
        (ROOT / f"local_3d_projection/{case}/projection_metrics.json").read_text(encoding="utf-8")
    )


def _config(payload):
    return {
        "width": int(payload["width"]),
        "height": int(payload["height"]),
        "coordinate_mode": str(payload["coordinate_mode_requested"]),
        "camera_height": float(payload["camera_height"]),
    }


def test_standalone_core_runner_schema_and_verdicts(tmp_path):
    payload = build_payload()
    assert payload["schema_version"] == SCHEMA_VERSION
    assert "portfolio_candidates" not in payload
    assert set(payload) >= {
        "case_contract",
        "candidate_set",
        "constrained_evaluations",
        "portfolio_ranking",
        "suppressed_candidates",
        "legacy_diagnostics",
        "overall_verdict",
    }
    verdict = payload["overall_verdict"]
    assert verdict["hypothesis_available"] == any(row["hard_gate_passed"] for row in payload["candidate_set"])
    assert verdict["legacy_ls_trial_available"] == any(
        row["hard_gate_passed"] and row["legacy_direct_ls_trial_allowed"]
        for row in payload["candidate_set"]
    )
    assert any(
        row["hard_gate_passed"] and not row["legacy_direct_ls_trial_allowed"]
        for row in payload["candidate_set"]
    )
    assert verdict["hypothesis_available"] is True
    assert payload["legacy_diagnostics"]["legacy_score_role"] == "diagnostic_only"
    assert payload["safety_boundary"]["automatic_apply"] is False
    assert payload["safety_boundary"]["annotation_writeback"] is False
    assert payload["safety_boundary"]["worker_facing"] is False
    assert payload["safety_boundary"]["routing_input"] is False

    output = run(tmp_path)
    assert json.loads(output.read_text(encoding="utf-8"))["schema_version"] == SCHEMA_VERSION


def test_3741_real_candidate_beats_low_legacy_score_hard_failure():
    payload = _artifact("task218_ann3741")
    baseline = next(row for row in payload["variants"] if row["name"] == "original")
    candidate = next(row for row in payload["variants"] if row["name"] == "m1527_candidate_0094")
    assertion = json.loads((ROOT / "local_candidate_search/task218_ann3741/expert_assertion.json").read_text(encoding="utf-8"))
    contract = build_case_contract(baseline["ordered_pairs"], assertion, baseline["metrics"])
    candidate_row = candidate["candidate_row"]
    good = evaluate_hypothesis(
        baseline,
        candidate,
        baseline["ordered_pairs"],
        candidate["ordered_pairs"],
        contract,
        candidate_row["score_breakdown"],
        legacy_trial_allowed=bool(candidate_row["direct_ls_trial_allowed"]),
    )

    bad_pairs = copy.deepcopy(candidate["ordered_pairs"])
    pair4 = next(row for row in bad_pairs if int(row["effective_pair_index"]) == 4)
    pair4["top"]["x"] += 0.1
    bad_variant = build_projection_variant("low_score_hard_fail", bad_pairs, **_config(payload))
    bad = evaluate_hypothesis(
        baseline,
        bad_variant,
        baseline["ordered_pairs"],
        bad_pairs,
        contract,
        {"local_score_total": -1_000_000.0},
        legacy_trial_allowed=True,
    )
    rows = [{"candidate_id": "real_3741"}, {"candidate_id": "low_score_hard_fail"}]
    portfolio = build_hypothesis_portfolio(rows, [good, bad])
    assert good["feasibility"]["hard_gate_passed"] is True
    assert bad["decision_class"] == "suppressed_hard_constraint"
    assert portfolio["best_balanced"]["candidate"]["candidate_id"] == "real_3741"
    assert {row["candidate"]["candidate_id"] for row in portfolio["suppressed_candidates"]} == {"low_score_hard_fail"}


def test_2369_dense_but_distinct_candidate_remains_rankable():
    payload = _artifact("task218_ann2369")
    baseline = payload["variants"][0]
    dense = next(
        row for row in baseline["metrics"]["dense_pairs"]["pairs"]
        if row["classification"] == "dense_but_distinct_3d_corner"
    )
    left, right = int(dense["pair_i"]), int(dense["pair_j"])
    pairs = copy.deepcopy(baseline["ordered_pairs"])
    target = next(row for row in pairs if int(row["effective_pair_index"]) == left)
    target["top"]["x"] += 0.01
    target["bottom"]["x"] += 0.01
    candidate = build_projection_variant("dense_distinct_probe", pairs, **_config(payload))
    contract = build_case_contract(
        baseline["ordered_pairs"],
        {
            "candidate_window": [left],
            "movable_fields_by_pair": {str(left): ["x"]},
            "keep_distinct_pairs": [[left, right]],
            "allowed_short_edges": [f"{left}-{right}"],
        },
        baseline["metrics"],
    )
    evaluation = evaluate_hypothesis(
        baseline, candidate, baseline["ordered_pairs"], pairs, contract
    )
    assert evaluation["feasibility"]["hard_gate_passed"] is True
    assert evaluation["layout_plausibility"]["short_wall_collapsed"] == []
    assert build_hypothesis_portfolio([{"candidate_id": "dense_distinct"}], [evaluation])["suppressed_candidates"] == []


def test_2389_real_height_probe_orders_by_dominant_cluster_residual():
    payload = _artifact("task238_ann2389")
    baseline = payload["variants"][0]
    baseline_contract = build_case_contract(baseline["ordered_pairs"], projection_metrics=baseline["metrics"])
    baseline_eval = evaluate_hypothesis(
        baseline, baseline, baseline["ordered_pairs"], baseline["ordered_pairs"], baseline_contract
    )
    target_index = baseline_eval["height_consistency"]["height_outlier_pairs"][0]
    evaluations = []
    rows = []
    for delta in (-0.5, 0.5):
        pairs = copy.deepcopy(baseline["ordered_pairs"])
        target = next(row for row in pairs if int(row["effective_pair_index"]) == target_index)
        target["top"]["y"] += delta
        candidate = build_projection_variant(f"height_{delta:+.1f}", pairs, **_config(payload))
        contract = build_case_contract(
            baseline["ordered_pairs"],
            {
                "candidate_window": [target_index],
                "movable_fields_by_pair": {str(target_index): ["top_y"]},
            },
            baseline["metrics"],
        )
        evaluations.append(evaluate_hypothesis(baseline, candidate, baseline["ordered_pairs"], pairs, contract))
        rows.append({"candidate_id": candidate["name"]})
    expected = rows[min(range(2), key=lambda index: evaluations[index]["height_consistency"]["height_outlier_l1"])]["candidate_id"]
    portfolio = build_hypothesis_portfolio(rows, evaluations)
    assert portfolio["best_height_consistent"]["candidate"]["candidate_id"] == expected
