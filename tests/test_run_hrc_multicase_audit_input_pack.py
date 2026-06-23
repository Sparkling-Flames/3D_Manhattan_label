import json

from tools.paper_a_manhattan.run_hrc_multicase_audit_input_pack import (
    CASES,
    SCHEMA_VERSION,
    build_case_pack,
    build_summary,
    run,
)


def test_multicase_input_packs_status_and_safety_flags():
    packs = {name: build_case_pack(name) for name in CASES}
    summary = build_summary(packs)

    assert summary["schema_version"] == SCHEMA_VERSION
    assert summary["available_candidate_input_cases"] == [
        "task218_ann2369",
        "task238_ann2389",
        "gt75_task533",
    ]
    assert summary["unavailable_candidate_input_cases"] == ["ordinary_compatible"]
    assert summary["baseline_only_cases"] == []
    assert summary["ready_for_c6_3e_bucket_audit"] is False
    assert summary["accepted"] is False
    assert summary["downstream_recommendation"] is False
    assert summary["active_runner_role"] is False

    for name, pack in packs.items():
        assert pack["audit_only"] is True
        assert pack["active_runner_role"] is False
        assert pack["accepted"] is False
        assert pack["downstream_recommendation"] is False
        assert pack["annotation_writeback"] is False
        assert pack["source_artifacts"]["candidate_artifact"]["sha256"]
        if name == "ordinary_compatible":
            assert pack["candidate_input_status"] == "unavailable"
            assert pack["candidate_set"] == []
            assert "baseline-only" in pack["unavailable_reason"]
        else:
            assert pack["candidate_input_status"] == "available"
            assert pack["candidate_set"]
            assert pack["unavailable_reason"] is None


def test_available_candidate_rows_are_existing_artifact_only_and_not_recommendations():
    pack = build_case_pack("task238_ann2389")
    candidate = pack["candidate_set"][0]
    assert candidate["existing_artifact_only"] is True
    assert candidate["audit_only"] is True
    assert candidate["active_runner_role"] is False
    assert candidate["accepted"] is False
    assert candidate["downstream_recommendation"] is False
    assert candidate["annotation_writeback"] is False
    assert candidate["raw_candidate_row"]["writeback_allowed"] is False


def test_multicase_input_pack_writes_summary_and_case_packs(tmp_path):
    paths = run(tmp_path)
    summary = json.loads(paths["summary_json"].read_text(encoding="utf-8"))
    assert summary["schema_version"] == SCHEMA_VERSION
    assert summary["ready_for_c6_3e_bucket_audit"] is False
    for name in CASES:
        assert paths[name].exists()
        pack = json.loads(paths[name].read_text(encoding="utf-8"))
        assert pack["case_name"] == name
