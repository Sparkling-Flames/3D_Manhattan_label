import json

from tools.paper_a_manhattan.run_hrc_c6_stability_audit import (
    BUCKETS,
    SCHEMA_VERSION,
    build_audit_payload,
    run,
)


def test_c6_stability_audit_payload_and_task3741_buckets():
    payload = build_audit_payload()
    assert payload["schema_version"] == SCHEMA_VERSION
    assert payload["bucket_names"] == list(BUCKETS)
    assert payload["active_runner_changed"] is False
    assert payload["legacy_m1528_only_active_source"] is True
    assert payload["accepted"] is False
    assert payload["downstream_recommendation"] is False
    assert payload["active_hrc_bucket_audit_cases"] == ["task218_ann3741"]
    assert payload["evidence_only_cases"] == [
        "task218_ann2369",
        "task238_ann2389",
        "gt75_task533",
        "ordinary_compatible",
    ]
    assert payload["full_multi_case_bucket_audit_complete"] is False

    case = payload["cases"]["task218_ann3741"]
    assert case["audit_mode"] == "active_hrc_bucket_audit"
    buckets = case["bucket_summary"]
    assert set(buckets) == set(BUCKETS)
    for name, summary in buckets.items():
        assert summary.get("candidate_id") or summary.get("reason")
        if summary.get("candidate_id"):
            assert summary["hard_gate_passed"] is True
            assert summary["accepted"] is False
            assert summary["downstream_recommendation"] is False
            assert summary["selection_driver"] in {
                "c2_c5_geometry",
                "c4_evidence",
                "height_consistency",
                "layout_plausibility",
                "movement_cost",
                "mixed",
            }

    assert buckets["best_manhattan_feasible"]["candidate_id"] == "m1528_candidate_0017"
    assert buckets["best_balanced"]["candidate_id"] == "m1528_candidate_0017"
    assert buckets["best_height_consistent"]["candidate_id"] == "m1528_candidate_0017"
    assert case["selection_regression"]["candidate_0019_selected_in_primary_buckets"] is False
    assert case["recommendation_semantics"]["any_recommended_review_candidate"] is True
    assert (
        case["recommendation_semantics"]["overall_recommended_review_candidate_available"]
        is False
    )
    assert case["recommendation_semantics"]["explanation_risk"] == "explained_by_overall_audit_blocked"


def test_c6_stability_audit_regression_and_evidence_only_cases():
    payload = build_audit_payload()
    assert payload["c4_layer_strength_audit"]["c4_overstrong_risk"] is False
    assert payload["c4_layer_strength_audit"]["ranking_change_recommended_now"] is False
    assert payload["audit_conclusion"].startswith("B: C6 still audit-blocked")
    assert "C3 shadow expansion remains blocked" in payload["next_allowed_step"]

    dense = payload["cases"]["task218_ann2369"]
    assert dense["audit_mode"] == "regression_evidence_only"
    assert dense["dense_but_distinct_evidence_present"] is True
    assert dense["dense_but_distinct_not_collapsed_by_active_hrc"] is None
    assert dense["dense_but_distinct_not_collapsed_reason"] == "no active HRC candidate set for this case"
    assert dense["dense_but_distinct_pairs"]
    assert dense["recommendation_semantics"]["accepted"] is False
    assert dense["recommendation_semantics"]["downstream_recommendation"] is False

    height = payload["cases"]["task238_ann2389"]
    assert height["height_outlier_evidence_present"] is True
    assert height["height_dominant_not_suppressed_by_active_hrc"] is None
    assert height["height_dominant_not_suppressed_reason"] == "no active HRC candidate set for this case"
    assert height["height_outlier_pairs"]
    assert height["recommendation_semantics"]["accepted"] is False
    assert height["recommendation_semantics"]["downstream_recommendation"] is False

    task533 = payload["cases"]["gt75_task533"]
    assert task533["verified_order_evidence_present"] is True
    assert task533["duplicate_default_status_present"] is True
    assert task533["pair_merge_or_duplicate_recommendation_by_active_hrc"] is None
    assert task533["pair_merge_or_duplicate_recommendation_reason"] == "no active HRC candidate set for this case"

    compatible = payload["cases"]["ordinary_compatible"]
    assert compatible["fixture_present"] is True
    assert compatible["meaningless_candidate_preference_by_active_hrc"] is None
    assert compatible["meaningless_candidate_preference_reason"] == "no active HRC candidate set for this case"


def test_c6_stability_audit_writes_artifact(tmp_path):
    paths = run(tmp_path)
    payload = json.loads(paths["json"].read_text(encoding="utf-8"))
    assert payload["schema_version"] == SCHEMA_VERSION
    assert paths["markdown"].read_text(encoding="utf-8").startswith(
        "# HRC C6 Stability Audit"
    )
