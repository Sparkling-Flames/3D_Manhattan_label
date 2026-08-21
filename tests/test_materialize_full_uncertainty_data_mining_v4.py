from __future__ import annotations

import pandas as pd

from tools.paper_a_manhattan.full_uncertainty.materialize_full_uncertainty_data_mining_v4 import (
    exact_building_sign_flip,
    raw_record_ledger,
    time_measurement_audit,
)


def test_raw_crosswalk_uses_context_without_claiming_chronology() -> None:
    raw = pd.DataFrame([
        {"stage": "C1", "project_id": 1, "ls_runtime_task_id": 7, "base_task_id": "t.jpg", "worker_id": 3, "annotation_id": 11, "canonical_annotation_id": "", "canonical_join_status": "raw_version_not_in_canonical_spine"},
        {"stage": "C1", "project_id": 1, "ls_runtime_task_id": 7, "base_task_id": "t.jpg", "worker_id": 3, "annotation_id": 9, "canonical_annotation_id": "sha", "canonical_join_status": "matched"},
    ])
    ledger, crosswalk = raw_record_ledger(raw)
    assert len(ledger) == 2
    assert crosswalk.iloc[0]["selected_annotation_ids"] == "9"
    assert crosswalk.iloc[0]["crosswalk_relation"] == "crosswalk_to_selected_context"
    assert "不声明版本先后" in crosswalk.iloc[0]["crosswalk_boundary_zh"]


def test_time_audit_never_relabels_lead_time_as_active_time() -> None:
    flagged = pd.DataFrame([
        {"stage": "C1", "project_id": 1, "runtime_task_id": 7, "worker_id": "3", "annotation_id": "9", "active_time_measurement_class": "formal_frozen", "active_time_observed_seconds": 12, "lead_time_seconds": 30},
        {"stage": "P1", "project_id": 2, "runtime_task_id": 8, "worker_id": "4", "annotation_id": "10", "active_time_measurement_class": "lead_time_proxy_excluded", "active_time_observed_seconds": None, "lead_time_seconds": 40},
    ])
    records, summary = time_measurement_audit(flagged, pd.DataFrame())
    assert not records["lead_time_is_active_time"].any()
    assert set(summary["time_measurement_lane"]) == {"c1_formal_active_log", "lead_time_proxy_excluded"}
    assert summary.loc[summary["time_measurement_lane"].eq("lead_time_proxy_excluded"), "active_time_observed_count"].item() == 0


def test_exact_building_sign_flip_is_deterministic() -> None:
    frame = pd.DataFrame({"building_id": ["a", "a", "b"], "value": [-1.0, -1.0, 1.0]})
    assert exact_building_sign_flip(frame, "value") == 1.0
