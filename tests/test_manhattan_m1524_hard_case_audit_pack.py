import json

from tools.paper_a_manhattan.run_m1524_hard_case_audit_pack import run


def test_m1524_hard_case_audit_pack(tmp_path):
    paths = run(tmp_path)
    payload = json.loads(paths["json"].read_text(encoding="utf-8"))
    rows = {row["case_name"]: row for row in payload["cases"]}

    assert payload["schema_version"] == "m15_24_hard_case_audit_pack_v1"
    assert payload["case_count"] == 3
    assert rows["task218_ann3741"]["applicability_status"] == "applicable"
    assert rows["task218_ann3741"]["generated_count"] == 54
    assert rows["task218_ann3741"]["retained_count"] == 21
    assert rows["task218_ann3741"]["direct_fix_available"] is False
    assert rows["task218_ann2369"]["applicability_status"] == "applicable"
    assert rows["task218_ann2369"]["best_joint_candidate_id"]
    assert rows["task238_ann2389"]["applicability_status"] == "ineligible_safe_skip"
    assert all(row["direct_fix_available"] is False for row in rows.values())
    assert payload["safety_boundary"] == {
        "expert_side": True,
        "offline_local_only": True,
        "annotation_write_allowed": False,
        "annotation_patch_generated": False,
        "routing_input": False,
        "formal_artifact": False,
        "correctness_oracle": False,
    }

    report = paths["report"].read_text(encoding="utf-8")
    for text in (
        "M15.24 Hard-case Audit Pack",
        "task218_ann3741",
        "task218_ann2369",
        "task238_ann2389",
        "ineligible_safe_skip",
    ):
        assert text in report
