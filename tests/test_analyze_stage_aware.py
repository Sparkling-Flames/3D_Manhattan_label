import json

import pandas as pd

from analyze_stage_aware import (
    _pick_consensus_token,
    _task_scene_consensus,
    add_row_audit_columns,
    apply_default_gate,
    apply_selection_manifest,
    build_core_scene_contract,
    attach_manifest_membership,
    attach_meta_guard_status,
    attach_scene_reliability_fields,
    attach_worker_formal_fields,
    assign_core_scene,
    build_analysis_frame,
    compute_worker_scene_metrics,
    derive_thesis_readiness,
    resolve_selection_manifest,
    write_active_time_estimand_audit_v2_1,
    write_freeze_consistency_audit_v2_1,
    write_route_attribution,
    write_selection_main_facing_audit_v2_1,
    write_selection_provenance_audit_v2_1,
    write_stage1_alignment_audit_v2_1,
    write_tim_mapping_spec,
    write_tim_rule_summary,
    write_type4_evidence_v2,
)


def test_pick_consensus_token_demotes_default_alias():
    values = pd.Series(["trivial;occlusion", "occlusion", "trivial"])
    assert _pick_consensus_token(values, default="none", demote_token="trivial") == "occlusion"

    issues = pd.Series(["acceptable", "underextend", "acceptable;underextend"])
    assert _pick_consensus_token(issues, default="acceptable", demote_token="acceptable") == "underextend"


def test_task_scene_consensus_uses_meta_label_proxy():
    quality = pd.DataFrame(
        [
            {
                "task_id": "101",
                "scope": "normal",
                "difficulty": "trivial;occlusion",
                "model_issue_primary": "acceptable",
                "task_scope_is_mixed": False,
            },
            {
                "task_id": "101",
                "scope": "normal",
                "difficulty": "occlusion",
                "model_issue_primary": "underextend",
                "task_scope_is_mixed": False,
            },
            {
                "task_id": "102",
                "scope": "oos_geometry",
                "difficulty": "reflection",
                "model_issue_primary": "corner_drift",
                "task_scope_is_mixed": False,
            },
        ]
    )

    result = _task_scene_consensus(quality).set_index("task_id")

    assert result.loc["101", "scene_proxy"] == "occlusion|underextend"
    assert result.loc["102", "scene_proxy"] == "oos::oos_geometry"


def test_default_gate_keeps_only_joined_thesis_rows():
    registry = pd.DataFrame(
        [
            {
                "task_id": "1",
                "annotation_id": "11",
                "annotator_id": "2",
                "base_task_id": "base-1",
                "dataset_group": "SemiAuto_Test",
                "matched_registry_uid": "stage3_semiauto_test:1",
                "task_join_status": "matched_by_title_condition",
                "active_time_source": "log",
                "active_time_value": 25.0,
                "compat_scope": "normal",
                "compat_difficulty": "occlusion",
                "compat_model_issue": "underextend",
            },
            {
                "task_id": "2",
                "annotation_id": "12",
                "annotator_id": "2",
                "base_task_id": "base-2",
                "dataset_group": "",
                "matched_registry_uid": "",
                "task_join_status": "unmatched",
                "active_time_source": "lead_time_fallback",
                "active_time_value": 40.0,
                "compat_scope": "normal",
                "compat_difficulty": "reflection",
                "compat_model_issue": "acceptable",
            },
        ]
    )
    quality = pd.DataFrame(
        [
            {
                "task_id": "1",
                "annotator_id": "2",
                "active_time": 20.0,
                "iou": 0.9,
                "layout_used": True,
                "scope": "normal",
                "difficulty": "occlusion",
                "model_issue": "underextend",
                "scope_filled": True,
                "difficulty_filled": True,
                "difficulty_conflict": False,
                "model_issue_required": True,
                "model_issue_filled": True,
                "model_issue_conflict": False,
                "model_issue_missing_required": False,
                "model_issue_primary": "underextend",
                "task_scope_is_mixed": False,
            },
            {
                "task_id": "2",
                "annotator_id": "2",
                "active_time": 35.0,
                "iou": 0.8,
                "layout_used": True,
                "scope": "normal",
                "difficulty": "reflection",
                "model_issue": "",
                "scope_filled": True,
                "difficulty_filled": True,
                "difficulty_conflict": False,
                "model_issue_required": True,
                "model_issue_filled": False,
                "model_issue_conflict": False,
                "model_issue_missing_required": True,
                "model_issue_primary": "",
                "task_scope_is_mixed": False,
            },
        ]
    )

    analysis = build_analysis_frame(registry, quality)
    gated = apply_default_gate(analysis)

    assert list(gated["task_id"]) == ["1"]
    assert bool(analysis.loc[analysis["task_id"] == "2", "type4_flag"].iloc[0]) is True


def test_selection_manifest_and_manifest_membership_are_applied():
    df = pd.DataFrame(
        [
            {
                "task_id": "1",
                "base_task_id": "base-1",
                "annotator_id": "2",
                "matched_registry_uid": "uid-1",
                "dataset_group": "SemiAuto_Test",
            },
            {
                "task_id": "2",
                "base_task_id": "base-2",
                "annotator_id": "3",
                "matched_registry_uid": "uid-2",
                "dataset_group": "Validation_semi",
            },
        ]
    )
    selection = pd.DataFrame([{"base_task_id": "base-2"}])
    filtered = apply_selection_manifest(df, selection)

    assert list(filtered["task_id"]) == ["2"]

    anchor = pd.DataFrame([{"base_task_id": "base-2"}])
    trap = pd.DataFrame([{"base_task_id": "base-1"}])
    attached = attach_manifest_membership(filtered, anchor, trap)

    assert bool(attached["in_manual_anchor_bank"].iloc[0]) is True
    assert attached["source_bank_membership"].iloc[0] == "anchor_only"


def test_core_scene_and_worker_formal_fields_are_added():
    df = pd.DataFrame(
        [
            {
                "task_id": "1",
                "annotation_id": "11",
                "annotator_id": "1",
                "dataset_group": "SemiAuto_Test",
                "scene_proxy": "occlusion|underextend",
                "scope_bucket": "in_scope",
                "i_included": True,
                "m_included": True,
                "iou": 0.90,
                "active_time": 20.0,
                "active_time_source": "log",
                "model_issue_primary": "underextend",
            },
            {
                "task_id": "2",
                "annotation_id": "12",
                "annotator_id": "1",
                "dataset_group": "PreScreen_semi",
                "scene_proxy": "occlusion|underextend",
                "scope_bucket": "in_scope",
                "i_included": True,
                "m_included": True,
                "iou": 0.40,
                "active_time": 25.0,
                "active_time_source": "lead_time_fallback",
                "model_issue_primary": "underextend",
            },
            {
                "task_id": "3",
                "annotation_id": "13",
                "annotator_id": "1",
                "dataset_group": "Validation_semi",
                "scene_proxy": "reflection|acceptable",
                "scope_bucket": "in_scope",
                "i_included": True,
                "m_included": True,
                "iou": 0.85,
                "active_time": 30.0,
                "active_time_source": "log",
                "model_issue_primary": "acceptable",
            },
        ]
    )

    with_core_scene = assign_core_scene(df)
    enriched = attach_worker_formal_fields(with_core_scene)

    assert "core_scene" in enriched.columns
    assert "r_u_lcb" in enriched.columns
    assert "worker_group" in enriched.columns
    assert enriched["core_scene_rule_version"].iloc[0] == "scene_proxy_top4_v1"
    assert enriched["worker_group_reason"].iloc[0] in {
        "noise_low_lcb",
        "vuln_high_trust_risk",
        "vuln_scene_gap",
        "stable_default",
    }


def test_row_audit_and_meta_guard_linkage_are_explicit():
    df = pd.DataFrame(
        [
            {
                "task_id": "1",
                "annotation_id": "11",
                "annotator_id": "1",
                "dataset_group": "SemiAuto_Test",
                "task_join_status": "matched_by_title",
                "thesis_input_eligible": True,
                "i_included": True,
                "m_included": True,
                "type4_flag": True,
                "type4_reason_codes": "difficulty_missing",
                "scope_bucket": "in_scope",
                "layout_gate_reason": "",
                "active_time_source": "lead_time_fallback",
            },
            {
                "task_id": "2",
                "annotation_id": "12",
                "annotator_id": "2",
                "dataset_group": "",
                "task_join_status": "unmatched",
                "thesis_input_eligible": False,
                "i_included": False,
                "m_included": False,
                "type4_flag": False,
                "type4_reason_codes": "",
                "scope_bucket": "missing",
                "layout_gate_reason": "",
                "active_time_source": "log",
            },
        ]
    )
    accepted = pd.DataFrame([{"task_id": "1", "annotation_id": "11"}])
    rejected = pd.DataFrame(
        [{"task_id": "2", "annotation_id": "12", "reject_reasons": "difficulty_empty"}]
    )

    with_guard = attach_meta_guard_status(df, accepted, rejected)
    audited = add_row_audit_columns(with_guard, pd.DataFrame([{"task_id": "1"}]))

    row1 = audited.loc[audited["task_id"] == "1"].iloc[0]
    row2 = audited.loc[audited["task_id"] == "2"].iloc[0]

    assert row1["meta_guard_status"] == "accepted"
    assert row1["tim_highest_tier"] == "I"
    assert row1["tim_scope_rule"] == "i_tier_type4_guarded"
    assert bool(row1["tim_m_included"]) is False
    assert row1["tim_mapping_spec_version"] == "tim_mapping_spec_v2_1"
    assert "m_guard:type4_excluded" in row1["tim_reason_chain"]
    assert "type4:difficulty_missing" in row1["tim_reason_chain"]
    assert row2["meta_guard_status"] == "rejected"
    assert row2["tim_highest_tier"] == "outside_T"
    assert row2["tim_scope_rule"] == "gate_excluded"
    assert row2["default_gate_reason"] == "dataset_group_blank;join_status:unmatched"


def test_worker_scene_metrics_and_reliability_attachment():
    df = pd.DataFrame(
        [
            {
                "task_id": "1",
                "annotator_id": "a1",
                "core_scene": "occlusion|acceptable",
                "m_included": True,
                "iou": 0.9,
                "active_time": 20.0,
            },
            {
                "task_id": "2",
                "annotator_id": "a1",
                "core_scene": "occlusion|acceptable",
                "m_included": True,
                "iou": 0.8,
                "active_time": 25.0,
            },
            {
                "task_id": "3",
                "annotator_id": "a2",
                "core_scene": "other",
                "m_included": False,
                "iou": None,
                "active_time": 30.0,
            },
        ]
    )
    metrics = compute_worker_scene_metrics(df)
    enriched = attach_scene_reliability_fields(df, metrics)

    row = enriched[(enriched["annotator_id"] == "a1") & (enriched["core_scene"] == "occlusion|acceptable")].iloc[0]
    assert row["activation_status"] == "activated"
    assert pd.notna(row["r_u_s_lcb"])


def test_core_scene_contract_v2_and_route_attribution(tmp_path):
    df = pd.DataFrame(
        [
            {
                "task_id": "t1",
                "annotation_id": "11",
                "annotator_id": "w1",
                "scene_proxy": "occlusion|acceptable",
                "core_scene": "occlusion|acceptable",
                "scope_bucket": "in_scope",
                "r_u_s_lcb": 0.92,
                "r_u_lcb": 0.70,
                "activation_status": "activated",
                "tim_highest_tier": "M",
                "active_time_source": "log",
                "meta_guard_status": "accepted",
                "type4_flag": False,
            },
            {
                "task_id": "t1",
                "annotation_id": "12",
                "annotator_id": "w2",
                "scene_proxy": "occlusion|acceptable",
                "core_scene": "occlusion|acceptable",
                "scope_bucket": "in_scope",
                "r_u_s_lcb": 0.85,
                "r_u_lcb": 0.88,
                "activation_status": "activated",
                "tim_highest_tier": "M",
                "active_time_source": "log",
                "meta_guard_status": "accepted",
                "type4_flag": False,
            },
            {
                "task_id": "t2",
                "annotation_id": "13",
                "annotator_id": "w1",
                "scene_proxy": "occlusion|acceptable",
                "core_scene": "occlusion|acceptable",
                "scope_bucket": "in_scope",
                "r_u_s_lcb": 0.90,
                "r_u_lcb": 0.70,
                "activation_status": "activated",
                "tim_highest_tier": "M",
                "active_time_source": "lead_time_fallback",
                "meta_guard_status": "accepted",
                "type4_flag": False,
            },
            {
                "task_id": "t3",
                "annotation_id": "14",
                "annotator_id": "w2",
                "scene_proxy": "occlusion|acceptable",
                "core_scene": "occlusion|acceptable",
                "scope_bucket": "in_scope",
                "r_u_s_lcb": 0.86,
                "r_u_lcb": 0.88,
                "activation_status": "activated",
                "tim_highest_tier": "M",
                "active_time_source": "log",
                "meta_guard_status": "accepted",
                "type4_flag": False,
            },
        ]
    )
    contract = build_core_scene_contract(df)
    contract_row = contract.loc[contract["core_scene"] == "occlusion|acceptable"].iloc[0]
    assert contract_row["routing_role_v2"] == "routing_candidate_strict"

    write_route_attribution(df, contract, tmp_path)
    route = pd.read_csv(tmp_path / "route_attribution_v1.csv")
    candidates = pd.read_csv(tmp_path / "route_candidates_v1.csv")
    chosen = route.loc[route["task_id"] == "t1"].iloc[0]
    assert chosen["selected_worker"] == "w1"
    assert bool(chosen["used_scene_specific_reliability"]) is True
    assert int(chosen["candidate_pool_size"]) == 2
    assert "scene:core_scene::occlusion|acceptable" in chosen["decision_reason_chain"]
    assert "winner_margin" in route.columns
    assert set(["candidate_rank", "selection_rule_trace"]).issubset(candidates.columns)


def test_tim_mapping_spec_and_rule_summary_outputs(tmp_path):
    write_tim_mapping_spec(tmp_path)
    spec = json.loads((tmp_path / "tim_mapping_spec_v2_1.json").read_text(encoding="utf-8"))
    assert "rules" in spec
    assert spec["tim_mapping_spec_version"] == "tim_mapping_spec_v2_1"

    df = pd.DataFrame(
        [
            {
                "task_id": "t1",
                "annotator_id": "w1",
                "tim_scope_rule": "m_tier_layout_usable_clean",
                "tim_highest_tier": "M",
                "tim_rule_type4_flag": False,
                "tim_rule_type4_excluded_from_m": False,
                "tim_rule_meta_guard_rejected": False,
                "tim_rule_active_time_fallback": True,
            },
            {
                "task_id": "t2",
                "annotator_id": "w2",
                "tim_scope_rule": "gate_excluded",
                "tim_highest_tier": "outside_T",
                "tim_rule_type4_flag": True,
                "tim_rule_type4_excluded_from_m": True,
                "tim_rule_meta_guard_rejected": True,
                "tim_rule_active_time_fallback": False,
            },
        ]
    )
    write_tim_rule_summary(df, tmp_path)
    out = pd.read_csv(tmp_path / "tim_rule_summary_v2_1.csv")
    assert int(out["n_rows"].sum()) == 2


def test_resolve_selection_manifest_autogen_creates_non_null_path(tmp_path):
    raw = pd.DataFrame(
        [
            {
                "task_id": "1",
                "annotation_id": "11",
                "base_task_id": "base-1",
                "matched_registry_uid": "uid-1",
                "dataset_group": "SemiAuto_Test",
                "annotator_id": "w1",
                "thesis_input_eligible": True,
            },
            {
                "task_id": "2",
                "annotation_id": "12",
                "base_task_id": "base-2",
                "matched_registry_uid": "uid-2",
                "dataset_group": "",
                "annotator_id": "w2",
                "thesis_input_eligible": False,
            },
        ]
    )
    selection_df, selection_path, selection_mode, thesis_selection_ready = resolve_selection_manifest(
        raw,
        pd.DataFrame(),
        None,
        tmp_path,
    )
    assert selection_mode == "autogen_default_gate"
    assert thesis_selection_ready is False
    assert selection_path.exists()
    assert str(selection_path).endswith("selection_manifest_autogen_default_gate_v1.csv")
    assert list(selection_df["task_id"]) == ["1"]


def test_type4_evidence_v2_contains_layer_chain(tmp_path):
    df = pd.DataFrame(
        [
            {
                "task_id": "t1",
                "annotation_id": "11",
                "annotator_id": "w1",
                "dataset_group": "SemiAuto_Test",
                "meta_guard_status": "rejected",
                "meta_guard_reject_reasons": "difficulty_empty",
                "type4_flag": True,
                "type4_reason_codes": "difficulty_missing",
                "type4_source": "meta_guard+system",
                "type4_evidence_chain": "meta_guard_rejected;system_type4;lead_time_fallback",
                "active_time_source": "lead_time_fallback",
                "default_gate_pass": True,
                "selection_pass": True,
                "tim_highest_tier": "I",
                "tim_scope": "I",
                "tim_downgrade_reason": "layout:scope_missing",
                "tim_reason_chain": "passed_default_gate",
                "scope_bucket": "in_scope",
                "scene_proxy": "occlusion|acceptable",
                "core_scene": "occlusion|acceptable",
                "activation_status": "activated",
                "degeneration_status": "scene_specific",
            }
        ]
    )
    write_type4_evidence_v2(df, tmp_path)
    out = pd.read_csv(tmp_path / "type4_evidence_v2_1.csv")
    assert out.loc[0, "risk_path"] == "type4_guarded"
    assert "instrumentation_fallback" in out.loc[0, "evidence_layer_chain"]


def test_freeze_consistency_audit_v2_1_passes(tmp_path):
    row_audit = pd.DataFrame(
        [
            {
                "task_id": "t1",
                "annotation_id": "a1",
                "selection_pass": True,
                "type4_flag": True,
                "tim_scope": "I",
                "tim_highest_tier": "I",
            },
            {
                "task_id": "t2",
                "annotation_id": "a2",
                "selection_pass": True,
                "type4_flag": False,
                "tim_scope": "M",
                "tim_highest_tier": "M",
            },
        ]
    )
    type4_evidence = pd.DataFrame(
        [
            {
                "task_id": "t1",
                "annotation_id": "a1",
                "type4_flag": True,
                "tim_scope": "I",
                "tim_highest_tier": "I",
            },
            {
                "task_id": "t2",
                "annotation_id": "a2",
                "type4_flag": False,
                "tim_scope": "M",
                "tim_highest_tier": "M",
            },
        ]
    )
    payload = write_freeze_consistency_audit_v2_1(row_audit, type4_evidence, tmp_path)
    assert payload["consistency_gate_passed"] is True
    assert (tmp_path / "freeze_v2_1_consistency_audit.json").exists()


def test_stage1_alignment_audit_and_thesis_readiness_blocked(tmp_path):
    manifest = {
        "items": [
            {
                "item_id": "stage1_prescreen_manual_expert_anchor",
                "status": "under_target_and_not_aligned",
                "thesis_target": {"type": "range", "min": 20, "max": 22},
                "current_repo": {"manual_anchor_bank_joinable": 12},
            },
            {
                "item_id": "stage1_prescreen_semi_total",
                "status": "not_aligned_and_not_materialized",
                "thesis_target": {"type": "approx", "value": 18},
                "current_repo": {"split_report_planned": 30},
            },
        ]
    }
    manifest_path = tmp_path / "phase1_manifest.json"
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False), encoding="utf-8")

    audit = write_stage1_alignment_audit_v2_1(manifest_path, tmp_path)
    selection_audit = {
        "selection_main_facing_passed": False,
    }
    ready, status, blockers = derive_thesis_readiness(
        selection_mode="autogen_default_gate",
        selection_ready_flag=False,
        stage1_alignment_audit=audit,
        selection_main_facing_audit=selection_audit,
    )
    assert audit["stage1_alignment_passed"] is False
    assert ready is False
    assert status == "blocked_autogen_default_gate_selection_and_stage1_protocol_not_aligned"
    assert "stage1_protocol_not_aligned" in blockers
    assert (tmp_path / "stage1_alignment_audit_v2_1.json").exists()


def test_active_time_estimand_audit_marks_mixed(tmp_path):
    df = pd.DataFrame(
        [
            {"task_id": "1", "active_time_source": "log"},
            {"task_id": "2", "active_time_source": "lead_time_fallback"},
            {"task_id": "3", "active_time_source": "lead_time_fallback"},
        ]
    )
    payload = write_active_time_estimand_audit_v2_1(df, tmp_path)
    assert payload["mixed_estimand"] is True
    assert payload["primary_endpoint_ready"] is False
    assert payload["active_time_endpoint_status"] == "mixed_estimand_log_plus_fallback"
    assert (tmp_path / "active_time_estimand_audit_v2_1.json").exists()


def test_selection_main_facing_audit_blocks_non_main_groups(tmp_path):
    analysis_df = pd.DataFrame(
        [
            {"task_id": "1", "dataset_group": "SemiAuto_Test"},
            {"task_id": "2", "dataset_group": "Validation_semi"},
            {"task_id": "3", "dataset_group": "Pilot"},
        ]
    )
    selection_audit = write_selection_main_facing_audit_v2_1(
        analysis_df,
        selection_mode="provided",
        output_dir=tmp_path,
    )
    ready, status, blockers = derive_thesis_readiness(
        selection_mode="provided",
        selection_ready_flag=True,
        stage1_alignment_audit={"stage1_alignment_passed": True},
        selection_main_facing_audit=selection_audit,
    )
    assert selection_audit["selection_main_facing_passed"] is False
    assert "Pilot" in selection_audit["non_main_groups_present"]
    assert ready is False
    assert status == "blocked_selection_not_main_facing"
    assert blockers == ["selection_not_main_facing"]


def test_selection_provenance_audit_blocks_autogen_derived_manifest(tmp_path):
    autogen_csv = tmp_path / "selection_manifest_autogen_default_gate_v1.csv"
    autogen_csv.write_text("task_id\n1\n", encoding="utf-8")

    upstream_manifest = tmp_path / "thesis_selection_manifest_v1.json"
    upstream_manifest.write_text(
        json.dumps(
            {
                "manifest_version": "thesis_selection_manifest_v1_20260317",
                "selection_mode": "provided_manifest",
                "source": str(autogen_csv),
                "row_count": 1,
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    main_manifest = tmp_path / "thesis_selection_main_facing_v1.json"
    main_manifest.write_text(
        json.dumps(
            {
                "manifest_version": "thesis_selection_main_facing_v1_20260317",
                "selection_mode": "thesis_facing_main_execution_manifest",
                "source": str(upstream_manifest),
                "row_count": 1,
                "rows": [
                    {
                        "task_id": "1",
                        "annotation_id": "1",
                        "dataset_group": "SemiAuto_Test",
                    }
                ],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    provenance = write_selection_provenance_audit_v2_1(
        selection_path=main_manifest,
        selection_mode="provided",
        output_dir=tmp_path,
    )
    assert provenance["selection_derived_from_autogen_default_gate"] is True
    assert provenance["selection_source_independent_from_autogen"] is False
    assert provenance["source_chain_depth"] >= 2

    ready, status, blockers = derive_thesis_readiness(
        selection_mode="provided",
        selection_ready_flag=True,
        stage1_alignment_audit={"stage1_alignment_passed": True},
        selection_main_facing_audit={"selection_main_facing_passed": True},
        selection_provenance_audit=provenance,
    )
    assert ready is False
    assert status == "blocked_selection_not_independent_from_autogen"
    assert blockers == ["selection_not_independent_from_autogen"]
    assert (tmp_path / "selection_provenance_audit_v2_1.json").exists()
