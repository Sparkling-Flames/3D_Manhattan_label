import json

from tools.paper_a_manhattan import run_constrained_v0_consolidation_audit as audit


def test_consolidation_payload_freezes_two_family_shadow_state():
    payload = audit.build_consolidation_payload()
    assert payload["implemented_families"] == [
        "column_x_alignment",
        "height_target_reproject",
    ]
    assert payload["deferred_families"] == [
        "short_wall_preserving_local",
        "primary_edge_direction_family_repair",
        "floor_depth_balance",
    ]
    assert payload["active_runner_role"] is False
    assert payload["accepted"] is False
    assert payload["downstream_recommendation"] is False
    assert payload["legacy_m1528_active_source_unchanged"] is True
    per_family = payload["per_family_audit"]
    assert per_family["column_x_alignment_real"]["candidate_count"] == 0
    assert set(per_family["column_x_alignment_real"]["reasons"]) >= {
        "evidence_unavailable",
        "column_identity_unavailable",
    }
    assert per_family["height_target_reproject_real"]["candidate_count"] == 0
    assert "height_target_unavailable" in per_family["height_target_reproject_real"]["reasons"]
    assert per_family["height_target_reproject_positive_fixture"]["candidate_count"] == 1
    safety = payload["candidate_safety_summary"]
    assert safety["positive_height_coordinate_fields"] == ["top_y"]
    assert safety["positive_height_contains_x"] is False
    assert all(
        safety[name]
        for name in (
            "all_shadow_only",
            "all_accepted_false",
            "all_downstream_recommendation_false",
            "all_active_runner_role_false",
            "all_annotation_writeback_false",
        )
    )


def test_consolidation_artifact_can_be_written(tmp_path, monkeypatch):
    monkeypatch.setattr(audit, "AUDIT_ROOT", tmp_path / "audit")
    paths = audit.run(tmp_path / "audit" / "consolidated")
    payload = json.loads(paths["json"].read_text(encoding="utf-8"))
    assert paths["markdown"].is_file()
    assert payload["schema_version"] == audit.SCHEMA_VERSION
