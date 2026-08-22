import csv
from collections import Counter
from pathlib import Path

from tools.thesis_main.analysis.materialize_annotator_image_inventory import materialize


ROOT = Path(__file__).resolve().parents[1]


def rows(path: Path):
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def test_inventory_reconciles_every_canonical_worker_image(tmp_path):
    result = materialize(
        raw_annotation_fact=ROOT / "analysis_results/paper_a_data_discovery_20260820_v1/raw_annotation_fact.csv",
        worker_fact=ROOT / "analysis_results/paper_a_data_discovery_20260820_v1/worker_fact.csv",
        current_roster=ROOT / "analysis_results/c2a_rp_block2_distribution_20260810_v1/worker_facing_release/block2_worker_assignments.csv",
        prescreen_roster=ROOT / "analysis_results/prescreen_closeout_final_gold_v2_20260701/raw_inputs/prescreen_worker_roster.csv",
        chinese_roster=ROOT / "export_label/标注人员.xlsx",
        foreign_roster=ROOT / "export_label/外国标注人员.xlsx",
        exit_roster=ROOT / "export_label/退出标注.xlsx",
        output=tmp_path,
    )

    assert result == {"canonical_submissions": 2501, "workers": 26, "current_workers": 20}
    summary = {row["worker_id"]: row for row in rows(tmp_path / "annotator_summary.csv")}
    detail = rows(tmp_path / "annotator_image_inventory.csv")
    noncanonical = rows(tmp_path / "noncanonical_annotation_audit.csv")
    outside_assignment = rows(tmp_path / "outside_assignment_annotation_audit.csv")
    checks = rows(tmp_path / "inventory_checks.csv")

    assert len(summary) == 26
    assert len(detail) == 2501
    assert sum(row["current_20"] == "true" for row in summary.values()) == 20
    assert summary["10"]["display_name"] == "徐毕桐"
    assert summary["28"]["display_name"] == "Atikur Rahman"
    assert summary["11"]["status_conflict_note"] == "historical_exit_form_but_later_submitted_through_C2A_RP_B2"
    assert summary["26"]["identity_mapping_status"] == "unresolved"
    assert summary["26"]["language_group"] == "English"
    assert summary["31"]["repeated_worker_image_count"] == "1"
    assert summary["34"]["repeated_worker_image_count"] == "1"
    assert summary["10"]["outside_assignment_submission_count"] == "1"
    assert summary["31"]["outside_assignment_submission_count"] == "6"
    assert summary["34"]["outside_assignment_submission_count"] == "2"
    assert sum(row["worker_image_repeat"] == "true" for row in detail) == 4
    assert len(outside_assignment) == 9
    assert {row["stage"] for row in outside_assignment} == {"C1"}
    assert {row["assignment_match_status"] for row in outside_assignment} == {"outside_assignment_submission"}
    assert Counter(row["outside_assignment_subtype"] for row in outside_assignment) == Counter(
        {"same_image_assigned_in_other_condition": 2, "image_not_assigned_to_worker": 7}
    )
    assert {row["assignment_match_status"] for row in detail if row["stage"] == "P1"} == {
        "stage_pool_member_worker_assignment_not_evaluable"
    }
    assert len(noncanonical) == 12
    assert {row["relation_to_selected"] for row in noncanonical} == {"exact_result_duplicate", "superseded_nonidentical_version"}
    assert all(row["status"] in {"pass", "warning"} for row in checks)
    assert [row["check"] for row in checks if row["status"] == "warning"] == [
        "identity_mapping_unresolved",
        "identity_source_value_needs_confirmation",
        "P1_worker_image_assignment_not_evaluable",
    ]
