from tools.thesis_main.data_prep.build_post_block2_analysis_pack_v2 import (
    NOT_IDENTIFIABLE,
    bind_authoritative_buildings,
    building_support_rows,
    worker_building_rows,
)
from tools.thesis_main.data_prep.build_post_block2_analysis_pack_v3 import non_profile_p0_findings


def test_building_outputs_use_authoritative_buildings_not_base_task_ids():
    rows = [
        {"stage": "P1", "base_task_id": "trap_1", "worker_id": "w1", "source_artifact": "p1", "source_sha256": "p1-sha"},
        {"stage": "C1", "base_task_id": "scene_a_hash1", "worker_id": "w1", "source_artifact": "c1", "source_sha256": "c1-sha"},
        {"stage": "C1", "base_task_id": "scene_a_hash2", "worker_id": "w2", "source_artifact": "c1", "source_sha256": "c1-sha"},
        {"stage": "C2-B", "base_task_id": "scene_b_hash3", "worker_id": "w1", "source_artifact": "c2b", "source_sha256": "c2b-sha"},
        {"stage": "C2A-RP-B1", "base_task_id": "scene_b_hash3", "worker_id": "w2", "source_artifact": "b1", "source_sha256": "b1-sha"},
        {"stage": "C2A-RP-B2", "base_task_id": "scene_c_hash4", "worker_id": "w2", "source_artifact": "b2", "source_sha256": "b2-sha"},
    ]
    sources = {
        "C1": ([
            {"base_task_id": "scene_a_hash1", "building_id": "scene_a"},
            {"base_task_id": "scene_a_hash2", "building_id": "scene_a"},
        ], "c1_crowd_structure"),
        "C2-B": ([{"base_task_id": "scene_b_hash3", "building_id": "scene_b"}], "c2b_risk_evidence"),
        "C2A-RP-B1": ([{"base_task_id": "scene_b_hash3", "building_id": "scene_b"}], "block1_risk_evidence"),
        "C2A-RP-B2": ([{"base_task_id": "scene_c_hash4", "building_id": "scene_c"}], "block2_task_pool"),
    }

    bind_authoritative_buildings(rows, sources)

    assert rows[0]["building_id"] == NOT_IDENTIFIABLE
    assert [row["building_id"] for row in rows[1:]] == ["scene_a", "scene_a", "scene_b", "scene_b", "scene_c"]
    assert {row["building_id"] for row in worker_building_rows(rows)} == {"scene_a", "scene_b", "scene_c"}
    assert [(row["stage"], row["building_id"], row["support_count"]) for row in building_support_rows(rows)] == [
        ("C1", "scene_a", 2),
        ("C2-B", "scene_b", 1),
        ("C2A-RP-B1", "scene_b", 1),
        ("C2A-RP-B2", "scene_c", 1),
    ]


def test_building_binding_rejects_conflicting_authoritative_rows():
    rows = [{"stage": "C1", "base_task_id": "task", "worker_id": "w1"}]
    sources = {"C1": ([
        {"base_task_id": "task", "building_id": "scene_a"},
        {"base_task_id": "task", "building_id": "scene_b"},
    ], "c1_crowd_structure")}

    try:
        bind_authoritative_buildings(rows, sources)
    except ValueError as error:
        assert "conflicting building_id" in str(error)
    else:
        raise AssertionError("conflicting authoritative building rows must fail closed")


def test_profile_repair_does_not_hide_unrelated_p0_findings():
    findings = non_profile_p0_findings({"p0_findings": [
        {"id": "post_block2_final_pooled_profile_source_absent"},
        {"id": "authoritative_building_binding_missing", "stage": "Calibration"},
    ]})

    assert findings == [{"id": "authoritative_building_binding_missing", "stage": "Calibration"}]
