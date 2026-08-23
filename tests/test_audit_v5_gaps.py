from pathlib import Path

import pandas as pd

from tools.thesis_main.analysis.full_uncertainty.audit_v5_gaps import (
    ACTIVE_TIME_COMPUTABILITY_DESCRIPTIVE,
    C1_ACTIVE_TIME_MISSINGNESS_AUDIT,
    COVERAGE_GAP_COMPUTABILITY_AUDIT,
    EVENT_SEQUENCE_OBSERVED_FACT,
    build_audit_frames,
    build_frames,
)


def test_audit_builder_keeps_active_time_lanes_separate():
    records = pd.DataFrame(
        [
            {"stage": "C1", "condition": "manual", "base_task_id": "t1", "worker_id": "w1", "building_id": "b1", "active_time_measurement_class": "formal_frozen"},
            {"stage": "C1", "condition": "manual", "base_task_id": "t1", "worker_id": "w2", "building_id": "b1", "active_time_measurement_class": "lead_time_proxy_excluded"},
            {"stage": "C1", "condition": "manual", "base_task_id": "t2", "worker_id": "w1", "building_id": "b2", "active_time_measurement_class": "missing"},
        ]
    )
    events = pd.DataFrame(
        [
            {"project_id": "p", "task_id": "t", "annotator_id": "w", "session_id": "s1", "timestamp": 1000, "server_received_at": "1970-01-01T00:00:01Z", "in_formal_stage_scope": True, "page_gate_eligible": True, "store_mismatch_present": False, "raw_event_json": '{"script_version":"v1"}'},
            {"project_id": "p", "task_id": "t", "annotator_id": "w", "session_id": "s1", "timestamp": 62001, "server_received_at": "1970-01-01T00:01:02Z", "in_formal_stage_scope": True, "page_gate_eligible": True, "store_mismatch_present": False, "raw_event_json": '{"script_version":"v1"}'},
            {"project_id": "p", "task_id": "t", "annotator_id": "w", "session_id": "s2", "timestamp": 63001, "server_received_at": "1970-01-01T00:01:03Z", "in_formal_stage_scope": True, "page_gate_eligible": True, "store_mismatch_present": False, "raw_event_json": '{"script_version":"v1"}'},
            {"project_id": "sandbox", "task_id": "x", "annotator_id": "w", "session_id": "sx", "timestamp": 1000, "server_received_at": "1970-01-01T00:00:01Z", "in_formal_stage_scope": False, "raw_event_json": '{"is_sandbox":true}'},
        ]
    )
    frames = build_audit_frames(records, events)
    summary = frames[ACTIVE_TIME_COMPUTABILITY_DESCRIPTIVE]
    all_row = summary.loc[summary["grouping"].eq("all")].iloc[0]
    assert (all_row["active_time_n"], all_row["lead_time_proxy_n"], all_row["missing_n"]) == (1, 1, 1)
    missing = frames[C1_ACTIVE_TIME_MISSINGNESS_AUDIT]
    assert missing.loc[missing["grouping"].eq("condition"), "missing"].sum() == 1
    sequence = frames[EVENT_SEQUENCE_OBSERVED_FACT]
    session = sequence.loc[sequence["fact_type"].eq("session_sequence")]
    assert len(session) == 3
    assert bool(session.loc[session["session_id"].eq("s1"), "gap_gt_60"].iloc[0])
    assert bool(session.loc[session["session_id"].eq("s1"), "multi_session_fact"].iloc[0])
    assert sequence.loc[sequence["fact_type"].eq("field_coverage"), "coverage_field"].tolist() == ["gate", "store", "script"]
    assert "independent_expert_review" in set(frames[COVERAGE_GAP_COMPUTABILITY_AUDIT]["component"])


def test_v5_fixed_counts_and_names():
    root = Path("analysis_results/full_uncertainty_data_mining_20260821_v5")
    if not root.exists():
        return
    frames = build_frames(root)
    assert set(frames) == {
        ACTIVE_TIME_COMPUTABILITY_DESCRIPTIVE,
        C1_ACTIVE_TIME_MISSINGNESS_AUDIT,
        EVENT_SEQUENCE_OBSERVED_FACT,
        COVERAGE_GAP_COMPUTABILITY_AUDIT,
    }
    active = frames[ACTIVE_TIME_COMPUTABILITY_DESCRIPTIVE]
    row = active.loc[active["grouping"].eq("all")].iloc[0]
    assert (row["n"], row["active_time_n"], row["lead_time_proxy_n"], row["missing_n"]) == (2501, 2069, 353, 79)
    events = frames[EVENT_SEQUENCE_OBSERVED_FACT]
    sessions = events.loc[events["fact_type"].eq("session_sequence")]
    assert sessions["raw_event_count"].sum() == 34417
    assert len(sessions) == 3735
    assert sessions["formal_event_n"].sum() == 27871
    assert sessions["outside_or_stage_mismatch_n"].sum() == 6546
    c1 = frames[C1_ACTIVE_TIME_MISSINGNESS_AUDIT]
    assert c1.loc[c1["grouping"].eq("condition"), "n"].sum() == 780
    assert c1.loc[c1["grouping"].eq("condition"), "missing"].sum() == 79
