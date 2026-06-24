import json

from tools.paper_a_manhattan.run_hrc_shadow_global_probe_planner import (
    FAMILIES,
    SCHEMA_VERSION,
    build_planner_payload,
    run,
)


def test_shadow_global_probe_planner_is_read_only_and_contract_bounded():
    payload = build_planner_payload()
    assert payload["schema_version"] == SCHEMA_VERSION
    assert payload["families"] == list(FAMILIES)
    assert payload["planner_only"] is True
    assert payload["candidate_generated"] is False
    assert payload["geometry_variant_generated"] is False
    assert payload["active_runner_changed"] is False
    assert payload["ranking_changed"] is False
    assert payload["c3_changed"] is False
    assert payload["accepted"] is False
    assert payload["downstream_recommendation"] is False
    assert payload["annotation_writeback"] is False
    assert set(payload["status_boundaries"].values()) == {"blocked"}

    for case in payload["cases"].values():
        assert set(case["applicable_probe_families"] + case["blocked_probe_families"]) == set(FAMILIES)
        assert case["candidate_generated"] is False
        assert case["geometry_variant_generated"] is False
        assert case["accepted"] is False
        assert case["downstream_recommendation"] is False
        assert all(plan["execution_allowed"] is False for plan in case["probe_family_plans"].values())


def test_case_plans_fail_closed_on_missing_inputs():
    payload = build_planner_payload()
    cases = payload["cases"]

    assert cases["task218_ann3741"]["applicable_probe_families"] == [
        "global_height_reproject",
        "direction_family_azimuth_snap",
        "floor_depth_balance_global",
        "short_wall_preserving_floorprint_balance",
    ]
    assert cases["task218_ann3741"]["blocked_probe_families"] == ["multi_pair_x_alignment"]

    for name in ("task218_ann2369", "task238_ann2389"):
        assert cases[name]["applicable_probe_families"] == [
            "global_height_reproject",
            "floor_depth_balance_global",
        ]

    assert cases["gt75_task533"]["applicable_probe_families"] == ["global_height_reproject"]
    ordinary = cases["ordinary_compatible"]
    assert ordinary["applicable_probe_families"] == []
    assert ordinary["blocked_probe_families"] == list(FAMILIES)
    assert "ordinary_compatible" in payload["blocked_cases"]
    assert payload["ready_for_c6_5b_proposal_manifest"] is False
    assert payload["recommended_next_step"] == "collect/materialize missing source artifacts"
    forbidden = ("C3", "optimizer", "active runner", "writeback")
    assert not any(token.lower() in payload["recommended_next_step"].lower() for token in forbidden)


def test_shadow_global_probe_planner_writes_audit_artifacts(tmp_path):
    paths = run(tmp_path)
    payload = json.loads(paths["json"].read_text(encoding="utf-8"))
    assert payload["schema_version"] == SCHEMA_VERSION
    assert paths["markdown"].read_text(encoding="utf-8").startswith(
        "# HRC C6.5a Shadow Global Probe Planner"
    )
