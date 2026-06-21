import copy
import json
from pathlib import Path

import pytest

from tools.paper_a_manhattan.manhattan_case_contract import build_case_contract
from tools.paper_a_manhattan.manhattan_constrained_hypothesis_evaluator import evaluate_hypothesis
from tools.paper_a_manhattan.manhattan_hypothesis_portfolio import build_hypothesis_portfolio
from tools.paper_a_manhattan.run_local_3d_projection_review import build_projection_variant
from tools.paper_a_manhattan.run_manhattan_hypothesis_ranking_core import (
    DEFAULT_PROJECTION,
    SCHEMA_VERSION,
    build_payload,
    run,
)


ROOT = Path("analysis_results/paper_a_manhattan")
EXPERT_FIXTURE = json.loads(
    Path("tests/fixtures/manhattan_expert_verdict_regression_v1.json").read_text(encoding="utf-8")
)["cases"]


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
    assert {"portfolio_candidates", "m15_28_gate", "legacy_m15_28_gate"}.isdisjoint(payload)
    assert set(payload) >= {
        "case_contract",
        "candidate_set",
        "candidate_review_geometry",
        "constrained_evaluations",
        "portfolio_ranking",
        "suppressed_candidates",
        "legacy_diagnostics",
        "overall_verdict",
    }
    assert set(payload["portfolio_ranking"]) == {
        "best_manhattan_feasible",
        "best_height_consistent",
        "best_short_wall_preserving",
        "best_low_movement",
        "best_hohonet_consistent",
        "best_balanced",
        "diagnostic_only_candidates",
        "suppressed_candidates",
    }
    expected_selection = {
        "best_manhattan_feasible": ("m1528_candidate_0017", "legacy_trial_blocked", True, "edge_6_7_floor_depth_balance"),
        "best_balanced": ("m1528_candidate_0017", "legacy_trial_blocked", True, "edge_6_7_floor_depth_balance"),
        "best_height_consistent": ("m1528_candidate_0017", "legacy_trial_blocked", True, "edge_6_7_floor_depth_balance"),
        "best_short_wall_preserving": ("m1528_candidate_0001", "hard_feasible_neutral", True, "vertical_column_align_x"),
        "best_low_movement": ("m1528_candidate_0070", "hard_feasible_neutral", True, "azimuth_translate_keep_top_bottom_delta"),
    }
    for name, expected in expected_selection.items():
        candidate = payload["portfolio_ranking"][name]["candidate"]
        assert (
            candidate["candidate_id"],
            candidate["decision_class"],
            candidate["hard_gate_passed"],
            candidate["action_family"],
        ) == expected
    assert payload["portfolio_ranking"]["best_hohonet_consistent"]["candidate"]
    verdict = payload["overall_verdict"]
    assert verdict["hard_feasible_candidate_available"] == any(row["hard_gate_passed"] for row in payload["candidate_set"])
    assert verdict["improving_hypothesis_available"] == any(
        row["hard_gate_passed"] and row["is_improving_hypothesis"]
        for row in payload["candidate_set"]
    )
    assert any(row["recommended_review_candidate"] for row in payload["candidate_set"])
    assert verdict["recommended_review_candidate_available"] is False
    assert verdict["selection_status"] == "audit_blocked"
    assert verdict["recommended_status"] == "not_accepted_pending_post_change_selection_audit"
    assert verdict["c6_1_blocked_reason"] == "C6.1 manual visual sanity check rejected 0019 over 0017"
    assert payload["authorization_contract"]["candidate_set.recommended_review_candidate"] == "diagnostic_bucket_selection_only"
    assert payload["authorization_contract"]["audit_blocked_effect"] == {
        "accepted": False,
        "downstream_recommendation": False,
    }
    assert any(
        evaluation["feasibility"]["hard_gate_passed"]
        and candidate_id not in payload["legacy_diagnostics"]["legacy_direct_ls_trial_candidates"]
        for candidate_id, evaluation in payload["constrained_evaluations"].items()
    )
    assert verdict["hard_feasible_candidate_available"] is True
    assert payload["legacy_diagnostics"]["legacy_score_role"] == "diagnostic_only"
    assert payload["legacy_diagnostics"]["legacy_portfolio_role"] == "diagnostic_only"
    assert payload["legacy_diagnostics"]["legacy_local_score_total"]
    assert any(
        evaluation["manhattan_feasibility"]["direction_family_fit_status"] == "available"
        for evaluation in payload["constrained_evaluations"].values()
    )
    assert all(
        {"legacy_score_breakdown", "local_score_total"}.isdisjoint(evaluation)
        for evaluation in payload["constrained_evaluations"].values()
    )
    assert all(
        evaluation["plane_proxy_metrics"]["plane_proxy_status"] in {"available", "partial_available"}
        for evaluation in payload["constrained_evaluations"].values()
    )
    assert all(
        evaluation["column_evidence"]["evidence_status"] == "available"
        for evaluation in payload["constrained_evaluations"].values()
    )
    for name, bucket in payload["portfolio_ranking"].items():
        if name in {"diagnostic_only_candidates", "suppressed_candidates"}:
            continue
        assert bucket["accepted"] is False
        assert bucket["downstream_recommendation"] is False
    assert isinstance(verdict["legacy_ls_trial_available"], bool)
    for bucket in payload["legacy_diagnostics"]["legacy_portfolio_candidates"].values():
        assert set(bucket) == {"candidate_id", "action_family", "reason"}
    main_surface = {key: value for key, value in payload.items() if key != "legacy_diagnostics"}
    main_text = json.dumps(main_surface, ensure_ascii=False)
    for deprecated in (
        '"portfolio_candidates"',
        '"m15_28_gate"',
        '"legacy_m15_28_gate"',
        '"legacy_score_breakdown"',
        '"local_score_total"',
        '"legacy_default_contract"',
        '"legacy_source_files"',
    ):
        assert deprecated not in main_text
    required_suppressed = {
        "candidate_id",
        "decision_class",
        "hard_failure_reasons",
        "projection_metric_errors",
        "plausibility_failure_reasons",
        "action_family",
        "changed_pair_indices",
    }
    assert payload["suppressed_candidates"]
    assert all(set(row) == required_suppressed for row in payload["suppressed_candidates"])
    canonical = {row["candidate_id"]: row for row in payload["candidate_set"]}
    for name, bucket in payload["portfolio_ranking"].items():
        if name in {"diagnostic_only_candidates", "suppressed_candidates"}:
            entries = bucket
        else:
            entries = [bucket] if bucket.get("candidate") else []
        for entry in entries:
            candidate = entry["candidate"]
            assert candidate["recommended_review_candidate"] == canonical[candidate["candidate_id"]]["recommended_review_candidate"]
    best = payload["portfolio_ranking"]["best_balanced"]["candidate"]
    assert best["recommended_review_candidate"] is True
    geometry = payload["candidate_review_geometry"][best["candidate_id"]]["coordinate_changes"]
    if best["candidate_id"] == "m1528_candidate_0017":
        deltas = {
            int(change["effective_pair_index"]): change["fields"]["bottom_y"]["after"] - change["fields"]["bottom_y"]["before"]
            for change in geometry
        }
        assert deltas == {6: pytest.approx(-1.0), 7: pytest.approx(1.0)}
    assert payload["safety_boundary"]["automatic_apply"] is False
    assert payload["safety_boundary"]["annotation_writeback"] is False
    assert payload["safety_boundary"]["worker_facing"] is False
    assert payload["safety_boundary"]["routing_input"] is False

    output = run(tmp_path)
    assert json.loads(output.read_text(encoding="utf-8"))["schema_version"] == SCHEMA_VERSION


def test_core_column_evidence_missing_source_fails_closed(tmp_path):
    projection = json.loads(DEFAULT_PROJECTION.read_text(encoding="utf-8"))
    projection["input_provenance"]["image"]["source_image_basename"] = "missing.jpg"
    projection["input_provenance"]["image"]["source_image"] = "missing.jpg"
    path = tmp_path / "projection.json"
    path.write_text(json.dumps(projection), encoding="utf-8")

    payload = build_payload(projection_path=path)
    assert payload["column_evidence_source_inventory"]["evidence_status"] == "unavailable"
    assert all(
        evaluation["column_evidence"]["evidence_status"] == "unavailable"
        for evaluation in payload["constrained_evaluations"].values()
    )
    assert payload["portfolio_ranking"]["best_hohonet_consistent"]["candidate"] is None
    assert payload["overall_verdict"]["recommended_review_candidate_available"] is False


def test_3741_real_candidate_beats_low_legacy_score_hard_failure():
    payload = _artifact("task218_ann3741")
    baseline = next(row for row in payload["variants"] if row["name"] == "original")
    candidate = next(row for row in payload["variants"] if row["name"] == "m1527_candidate_0094")
    assertion = json.loads((ROOT / "local_candidate_search/task218_ann3741/expert_assertion.json").read_text(encoding="utf-8"))
    assert assertion["do_not_move_pairs"] == EXPERT_FIXTURE["task218_ann3741"]["do_not_move_pairs"]
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
    assert EXPERT_FIXTURE["task218_ann3741"]["hard_fail_must_be_suppressed"] is True
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
    assert dense["classification"] == EXPERT_FIXTURE["task218_ann2369"]["expected_dense_class"]
    left, right = int(dense["pair_i"]), int(dense["pair_j"])
    assert [[left, right]] == EXPERT_FIXTURE["task218_ann2369"]["keep_distinct_pairs"]
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
    assert [target_index] == EXPERT_FIXTURE["task238_ann2389"]["dominant_height_outlier_pairs"]
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
    pure_x_pairs = copy.deepcopy(baseline["ordered_pairs"])
    pure_x_target = pure_x_pairs[0]
    pure_x_target["top"]["x"] += 0.01
    pure_x_target["bottom"]["x"] += 0.01
    pure_x_variant = build_projection_variant("pure_x", pure_x_pairs, **_config(payload))
    pure_x_contract = build_case_contract(
        baseline["ordered_pairs"],
        {"candidate_window": [int(pure_x_target["effective_pair_index"])], "movable_fields_by_pair": {str(pure_x_target["effective_pair_index"]): ["x"]}},
        baseline["metrics"],
    )
    evaluations.append(
        evaluate_hypothesis(
            baseline,
            pure_x_variant,
            baseline["ordered_pairs"],
            pure_x_pairs,
            pure_x_contract,
        )
    )
    rows.append({"candidate_id": "pure_x"})
    expected = rows[min(range(2), key=lambda index: evaluations[index]["height_consistency"]["height_outlier_l1"])]["candidate_id"]
    assert min(evaluation["height_consistency"]["height_outlier_l1"] for evaluation in evaluations[:2]) < evaluations[2]["height_consistency"]["height_outlier_l1"]
    assert EXPERT_FIXTURE["task238_ann2389"]["height_candidate_must_rank_by_height_before_pure_x_tie_break"] is True
    portfolio = build_hypothesis_portfolio(rows, evaluations)
    assert portfolio["best_height_consistent"]["candidate"]["candidate_id"] == expected
