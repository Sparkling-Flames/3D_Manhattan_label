from tools.thesis_main.data_prep.prepare_scope_evidence_20260908 import resolve_display
from tools.thesis_main.data_prep.prepare_scope_evidence_20260908 import build
import json
from pathlib import Path


def test_identity_preserves_block_revision_and_blank():
    version = dict(stage="C1", block_index="1", project_id="2", runtime_task_id="3", worker_id="4",
                   raw_annotation_id="5", raw_annotation_version_id="old", canonical_annotation_id="canonical")
    display = {"annotation_identity": "C1|1|2|3|4|5"}
    result = resolve_display(display, {}, [version])
    assert result["join_status"] == "historical_version_only"
    assert not result["geometry_can_use_current_canonical"]
    assert resolve_display({"annotation_identity": "C1|0|2|3|4|5"}, {}, [version])["join_status"] == "missing_or_nonunique_version"
    assert resolve_display({"annotation_identity": ""}, {}, [version])["canonical_annotation_id"] is None
    canonical = {display["annotation_identity"]: {"canonical_annotation_id": "canonical"}}
    assert resolve_display(display, canonical, [version])["geometry_can_use_current_canonical"]


def test_actual_bundle_preserves_human_comments_and_scope_limits(tmp_path):
    repo = Path(__file__).resolve().parents[1]
    qa = build(repo, tmp_path)
    cases = {r["case_id"]: r for r in map(json.loads, (tmp_path / "case_evidence.jsonl").read_text("utf-8").splitlines())}
    assert len(cases) == 50 and qa["all_original_human_records_equal_backup"]
    for case in ["V04", "V15", "V27", "V48"]:
        assert cases[case]["preferred_semantic_source"] == "later_human_supplement"
        assert cases[case]["final_user_decision"] is None
        assert not cases[case]["completion_option_is_certainty"]
    links = list(map(json.loads, (tmp_path / "response_semantic_links.jsonl").read_text("utf-8").splitlines()))
    assert all(r["scope_of_claim"] == "displayed_object_only" for r in links)
    assert all(r["semantic_label_is_final_human_adjudication"] is False for r in links)
    assert all(r["semantic_label_provenance"] == (
        "direct_user_supplement_with_ai_target_binding" if r["statement_id"] == "V04-SUP1"
        else "human_quote_with_existing_ai_extraction") for r in links)
    assert not any(r["statement_id"] in ["V11-S2", "V31-S2", "V34-S1"] for r in links)
