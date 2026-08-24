from pathlib import Path

from tools.thesis_main.registry.materialize_c_traps import (
    APPENDIX_PERTURBATION_SECTION,
    DEFAULT_PRESCREEN_TRAP_FAMILIES,
    build_c_manifest_consistency_audit,
    build_current_bundle_vs_prescreen_target_gap,
    build_fallback_registry,
    build_xml_model_issue_operator_crosswalk,
    build_family_appendix_notes,
    build_family_coverage_rows,
    build_manual_resolution_queue,
    build_materialization_summary_v2,
    build_prescreen_semi_family_target,
    build_reject_lifecycle_rows,
    load_xml_model_issue_choices,
)


def _materialized_row(**overrides):
    row = {
        "manifest_row_id": "ctrap_001",
        "target_stage": "prescreen_semi",
        "target_dataset_group": "PreScreen_semi",
        "target_registry_uid": "stage1_prescreen_semi:1",
        "base_task_id": "scene_001",
        "source_type": "synthetic_operator",
        "operator_id": "underextend",
        "lambda_level": "medium",
        "selection_rule": "ascending_registry_uid_fill",
        "materialization_status": "reject",
        "source_corner_count": "4",
    }
    row.update(overrides)
    return row


def _generated_row(**overrides):
    row = {
        "manifest_row_id": "ctrap_001",
        "family_id": "underextend",
        "failure_code": "transform_degenerate",
    }
    row.update(overrides)
    return row


def test_reject_lifecycle_explicitizes_medium_underextend_reject():
    materialized_rows = [_materialized_row()]
    generated_bank = [_generated_row()]

    rows = build_reject_lifecycle_rows(materialized_rows=materialized_rows, generated_bank=generated_bank)

    assert len(rows) == 1
    payload = rows[0]
    assert payload["task_id"] == "stage1_prescreen_semi:1"
    assert payload["family"] == "underextend"
    assert payload["reject_stage"] == "prescreen_semi_materialization"
    assert payload["reject_reason"] == "operator_reject.transform_degenerate"
    assert payload["recoverable"] is True
    assert payload["fallback_strategy"] == "manual_resolution_required"
    assert payload["resolution_status"] == "pending_manual_resolution"


def test_fallback_registry_separates_applied_fill_from_open_manual_resolution():
    materialized_rows = [
        _materialized_row(
            manifest_row_id="ctrap_014",
            operator_id="overextend_adjacent",
            lambda_level="medium",
            materialization_status="realized",
        ),
        _materialized_row(),
    ]
    generated_bank = [_generated_row()]
    reject_rows = build_reject_lifecycle_rows(materialized_rows=materialized_rows, generated_bank=generated_bank)

    registry = build_fallback_registry(
        materialized_rows=materialized_rows,
        reject_lifecycle_rows=reject_rows,
        source_manifest="analysis_results/c_manifests_20260310/trap_manifest_draft_v1.csv",
        source_materialized_bundle="analysis_results/c_manifests_20260311/trap_manifest_materialized_v2.csv",
    )

    assert registry["registry_name"] == "fallback_registry_v1"
    assert registry["source_artifacts"]["appendix_reference"] == APPENDIX_PERTURBATION_SECTION
    assert registry["fallback_rules"][0]["fallback_type"] == "natural_failure_shortfall_to_synthetic_operator_fill"
    assert registry["fallback_rules"][0]["linkage_to_tasks"] == ["ctrap_014"]
    assert registry["fallback_rules"][1]["fallback_type"] == "operator_reject_to_manual_resolution"
    assert registry["fallback_rules"][1]["linkage_to_tasks"] == ["ctrap_001"]


def test_family_coverage_matrix_marks_realized_reject_planned_and_appendix_only():
    materialized_rows = [
        _materialized_row(manifest_row_id="ctrap_002", operator_id="over_parsing", materialization_status="realized"),
        _materialized_row(manifest_row_id="ctrap_003", operator_id="underextend", materialization_status="reject"),
    ]

    rows = build_family_coverage_rows(materialized_rows)
    by_family = {row["family"]: row for row in rows}

    assert by_family["over_parsing"]["status"] == "realized"
    assert by_family["underextend"]["status"] == "reject"
    assert by_family["topology_failure"]["status"] == "planned"
    assert by_family["acceptable"]["status"] == "appendix_only"
    assert by_family["fail"]["linked_appendix_section"] == APPENDIX_PERTURBATION_SECTION


def test_materialization_summary_v2_rolls_up_lifecycle_fallback_and_coverage():
    materialized_rows = [
        _materialized_row(manifest_row_id="ctrap_014", operator_id="overextend_adjacent", lambda_level="medium", materialization_status="realized"),
        _materialized_row(),
    ]
    reject_rows = build_reject_lifecycle_rows(materialized_rows=materialized_rows, generated_bank=[_generated_row()])
    fallback_registry = build_fallback_registry(
        materialized_rows=materialized_rows,
        reject_lifecycle_rows=reject_rows,
        source_manifest="analysis_results/c_manifests_20260310/trap_manifest_draft_v1.csv",
        source_materialized_bundle="analysis_results/c_manifests_20260311/trap_manifest_materialized_v2.csv",
    )
    family_rows = build_family_coverage_rows(materialized_rows)

    summary = build_materialization_summary_v2(
        materialized_rows=materialized_rows,
        reject_lifecycle_rows=reject_rows,
        fallback_registry=fallback_registry,
        family_coverage_rows=family_rows,
        source_manifest="analysis_results/c_manifests_20260310/trap_manifest_draft_v1.csv",
        source_import_json="import_json/outline_v2_seed20260228/stage1_prescreen_semi_import.json",
    )

    assert summary["n_rows"] == 2
    assert summary["n_realized_rows"] == 1
    assert summary["n_reject_rows"] == 1
    assert summary["n_open_reject_rows"] == 1
    assert summary["n_manual_resolution_required"] == 1
    assert summary["n_active_fallback_rules"] == 1
    assert summary["family_status_counts"]["realized"] >= 1
    assert summary["family_status_counts"]["reject"] == 1
    assert summary["appendix_family_coverage_status"]["underextend"] == "reject"


def test_consistency_audit_appendix_notes_and_manual_queue_are_machine_readable():
    materialized_rows = [
        _materialized_row(manifest_row_id="ctrap_014", operator_id="overextend_adjacent", lambda_level="medium", materialization_status="realized"),
        _materialized_row(),
    ]
    reject_rows = build_reject_lifecycle_rows(materialized_rows=materialized_rows, generated_bank=[_generated_row()])
    fallback_registry = build_fallback_registry(
        materialized_rows=materialized_rows,
        reject_lifecycle_rows=reject_rows,
        source_manifest="analysis_results/c_manifests_20260310/trap_manifest_draft_v1.csv",
        source_materialized_bundle="analysis_results/c_manifests_20260311/trap_manifest_materialized_v2.csv",
    )
    family_rows = build_family_coverage_rows(materialized_rows)

    audit = build_c_manifest_consistency_audit(
        materialized_rows=materialized_rows,
        reject_lifecycle_rows=reject_rows,
        fallback_registry=fallback_registry,
        family_coverage_rows=family_rows,
    )
    appendix_notes = build_family_appendix_notes(family_rows)
    manual_queue = build_manual_resolution_queue(reject_rows)

    assert audit["consistency_gate_passed"] is True
    assert appendix_notes["appendix_section"] == APPENDIX_PERTURBATION_SECTION
    by_family = {row["family"]: row for row in appendix_notes["family_notes"]}
    assert by_family["acceptable"]["thesis_facing_status"] == "appendix_only_not_in_current_bundle"
    assert by_family["underextend"]["thesis_facing_status"] == "partial_realized_with_unresolved_subedge"
    assert manual_queue == [
        {
            "manifest_row_id": "ctrap_001",
            "task_id": "stage1_prescreen_semi:1",
            "family": "underextend",
            "failure_code": "transform_degenerate",
            "required_action": "manual_resolution_required",
            "priority": "high",
            "notes": "family:underextend;lambda_level:medium;source_corner_count:4;failure_code:transform_degenerate;materialization_status:reject",
        }
    ]


def test_xml_model_issue_crosswalk_matches_xml_aliases_and_operator_families():
    xml_rows = load_xml_model_issue_choices(
        Path(__file__).parent.parent
        / "tools/label_studio/config_history/uncertainty_meta_v1_prechange_20260824/zh/xml"
        / "label_studio_view_config.xml"
    )
    family_rows = build_family_coverage_rows([])

    crosswalk = build_xml_model_issue_operator_crosswalk(
        xml_model_issue_choices=xml_rows,
        family_coverage_rows=family_rows,
    )

    assert [row["xml_alias"] for row in crosswalk] == [
        "acceptable",
        "overextend_adjacent",
        "underextend",
        "over_parsing",
        "corner_drift",
        "corner_duplicate",
        "topology_failure",
        "fail",
    ]
    by_family = {row["xml_alias"]: row for row in crosswalk}
    assert by_family["acceptable"]["xml_label_text"] == "模型标注质量好 (Model quality acceptable)"
    assert by_family["acceptable"]["operator_class"] == "AcceptableOperator"
    assert by_family["topology_failure"]["operator_class"] == "TopologyBreakOperator"
    assert by_family["fail"]["current_bundle_status"] == "planned"


def test_prescreen_target_and_gap_keep_thesis_readiness_blocked():
    materialized_rows = [
        _materialized_row(manifest_row_id="ctrap_002", operator_id="over_parsing", materialization_status="realized"),
        _materialized_row(manifest_row_id="ctrap_003", operator_id="corner_drift", materialization_status="realized"),
        _materialized_row(),
    ]
    reject_rows = build_reject_lifecycle_rows(materialized_rows=materialized_rows, generated_bank=[_generated_row()])
    family_rows = build_family_coverage_rows(materialized_rows)
    prescreen_target = build_prescreen_semi_family_target()

    gap = build_current_bundle_vs_prescreen_target_gap(
        materialized_rows=materialized_rows,
        reject_lifecycle_rows=reject_rows,
        family_coverage_rows=family_rows,
        prescreen_semi_family_target=prescreen_target,
    )

    assert prescreen_target["target_total_tasks"] == 18
    assert prescreen_target["normal_control_target"]["target_count"] == 6
    assert prescreen_target["misleading_trap_target"]["target_count"] == 12
    assert prescreen_target["misleading_trap_target"]["default_target_families"] == DEFAULT_PRESCREEN_TRAP_FAMILIES
    assert prescreen_target["oos_stress_policy"]["included_in_prescreen_semi_target"] is False
    assert gap["thesis_ready_for_prescreen_semi"] is False
    assert gap["target_family_counts"]["acceptable"] == 6
    assert gap["gap_by_family"]["topology_failure"]["current_bundle_status"] == "planned"
    assert gap["gap_by_family"]["fail"]["current_bundle_status"] == "planned"
    assert gap["open_subedges"] == [
        {
            "subedge_id": "underextend+medium+4-corner+transform_degenerate",
            "family": "underextend",
            "lambda_level": "medium",
            "source_corner_count": 4,
            "failure_code": "transform_degenerate",
            "manifest_row_id": "ctrap_001",
            "task_id": "stage1_prescreen_semi:1",
            "resolution_status": "pending_manual_resolution",
        }
    ]
