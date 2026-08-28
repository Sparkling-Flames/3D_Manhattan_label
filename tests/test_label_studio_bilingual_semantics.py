from pathlib import Path
import hashlib
import json
from xml.etree import ElementTree


ROOT = Path(__file__).resolve().parents[1]
LS = ROOT / "tools" / "label_studio"
EN = LS / "localized" / "en"
PRECHANGE = LS / "config_history" / "uncertainty_meta_v1_prechange_20260824"
V1_HISTORY = LS / "config_history" / "scope_instruction_v1_pre_block2"
V2_MANIFEST = LS / "label_studio_xml_instruction_manifest_v2.json"
UNCERTAINTY_MANIFEST_V1 = LS / "label_studio_uncertainty_meta_manifest_v1.json"
UNCERTAINTY_MANIFEST_V2 = LS / "label_studio_uncertainty_meta_manifest_v2.json"

ACTIVE = {
    "zh_semi": LS / "label_studio_view_config.xml",
    "zh_manual": LS / "label_studio_view_config_manual.xml",
    "zh_future": LS / "label_studio_view_config_c2_future.xml",
    "en_semi": EN / "label_studio_view_config_en.xml",
    "en_manual": EN / "label_studio_view_config_manual_en.xml",
    "en_future": EN / "label_studio_view_config_c2_future_en.xml",
}
PRECHANGE_XML = {
    "zh_semi": PRECHANGE / "zh" / "xml" / "label_studio_view_config.xml",
    "zh_manual": PRECHANGE / "zh" / "xml" / "label_studio_view_config_manual.xml",
    "zh_future": PRECHANGE / "zh" / "xml" / "label_studio_view_config_c2_future.xml",
    "en_semi": PRECHANGE / "en" / "xml" / "label_studio_view_config_en.xml",
    "en_manual": PRECHANGE / "en" / "xml" / "label_studio_view_config_manual_en.xml",
    "en_future": PRECHANGE / "en" / "xml" / "label_studio_view_config_c2_future_en.xml",
}

IMAGE_FIELDS = {
    "worker_scope_response",
    "multiple_plausible_layouts",
    "perceived_difficulty",
    "difficulty_reason",
}
PROPOSAL_FIELDS = {
    "material_issue",
    "observed_defects",
    "repair_actions",
    "repair_extent",
    "issue_confidence",
}


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _choice_aliases(path: Path) -> dict[str, list[str]]:
    root = ElementTree.parse(path).getroot()
    return {
        node.attrib["name"]: [choice.attrib["alias"] for choice in node.findall("Choice")]
        for node in root.iter("Choices")
    }


def _visible_views(path: Path) -> list[dict[str, str]]:
    root = ElementTree.parse(path).getroot()
    return [node.attrib for node in root.iter("View") if node.attrib.get("visibleWhen")]


def test_uncertainty_xml_uses_the_expected_fields_by_role() -> None:
    for language in ("zh", "en"):
        manual = set(_choice_aliases(ACTIVE[f"{language}_manual"]))
        semi = set(_choice_aliases(ACTIVE[f"{language}_semi"]))
        future = set(_choice_aliases(ACTIVE[f"{language}_future"]))
        assert manual == IMAGE_FIELDS
        assert semi == IMAGE_FIELDS | PROPOSAL_FIELDS
        assert future == IMAGE_FIELDS | PROPOSAL_FIELDS


def test_uncertainty_bilingual_aliases_match() -> None:
    for role in ("semi", "manual", "future"):
        assert _choice_aliases(ACTIVE[f"zh_{role}"]) == _choice_aliases(ACTIVE[f"en_{role}"])


def test_active_xml_keeps_the_3d_preview_anchor_next_to_vis_3d() -> None:
    for path in ACTIVE.values():
        root = ElementTree.parse(path).getroot()
        parents = [
            list(parent)
            for parent in root.iter()
            if any(child.tag == "HyperText" and child.attrib.get("name") == "vis_3d" for child in parent)
        ]
        assert len(parents) == 1
        children = parents[0]
        index = next(i for i, child in enumerate(children) if child.attrib.get("name") == "vis_3d")
        assert index > 0
        assert children[index - 1].tag == "Header"
        assert children[index - 1].attrib.get("value") == "3D Layout Preview"


def test_chinese_uncertainty_xml_has_no_english_research_terms_in_visible_text() -> None:
    visible_attributes = {"value", "html", "hint", "requiredMessage"}
    for role in ("semi", "manual", "future"):
        root = ElementTree.parse(ACTIVE[f"zh_{role}"]).getroot()
        visible_text = " ".join(
            value
            for node in root.iter()
            for key, value in node.attrib.items()
            if key in visible_attributes and node.tag not in {"Image", "HyperText"}
        ).lower()
        assert not any(
            term in visible_text
            for term in ("proposal", "truth", "in-scope", "out-of-scope")
        )


def test_uncertainty_choice_values_are_frozen() -> None:
    semi = _choice_aliases(ACTIVE["zh_semi"])
    assert semi["worker_scope_response"] == ["in_scope", "out_of_scope"]
    assert semi["multiple_plausible_layouts"] == ["no", "yes"]
    assert semi["perceived_difficulty"] == ["1", "2", "3", "4", "5"]
    assert semi["difficulty_reason"] == [
        "no_specific_reason",
        "occlusion",
        "low_texture",
        "seam_or_distortion",
        "reflection_or_transparency",
        "opening_or_adjacent_space",
        "image_quality",
        "other",
    ]
    assert semi["material_issue"] == ["no", "yes"]
    assert semi["observed_defects"] == [
        "boundary_misalignment",
        "current_space_undercoverage",
        "adjacent_space_inclusion",
        "spurious_nonlayout_structure",
        "duplicate_redundant_corner",
    ]
    assert semi["repair_actions"] == [
        "move_boundary_or_corner",
        "add_missing_boundary_or_corner",
        "remove_adjacent_space_segment",
        "remove_spurious_structure",
        "merge_or_delete_duplicate_corner",
    ]
    assert semi["repair_extent"] == ["local", "multi_region", "redraw"]
    assert semi["issue_confidence"] == ["1", "2", "3", "4", "5"]


def test_conditional_display_matches_the_supervisor_draft() -> None:
    for path in ACTIVE.values():
        views = _visible_views(path)
        text = path.read_text(encoding="utf-8").lower()
        for forbidden in ("edit_operation_count", "proposal_missing", "phase_lock", "time_lock"):
            assert forbidden not in text
        assert all(row.get("whenTagName") != "difficulty_reason_status" for row in views)

    for role in ("semi", "future"):
        for language in ("zh", "en"):
            views = _visible_views(ACTIVE[f"{language}_{role}"])
            assert {
                (row.get("whenTagName"), row.get("whenChoiceValue")) for row in views
            } == {("material_issue", "yes")}


def test_worker_defects_and_repairs_are_multi_select_without_worker_primary() -> None:
    for role in ("semi", "future"):
        for language in ("zh", "en"):
            root = ElementTree.parse(ACTIVE[f"{language}_{role}"]).getroot()
            choices = {node.attrib["name"]: node.attrib for node in root.iter("Choices")}
            assert choices["observed_defects"]["choice"] == "multiple"
            assert choices["repair_actions"]["choice"] == "multiple"
            assert choices["repair_extent"]["choice"] == "single"
            assert "primary_defect" not in choices
            assert "redraw_layout" not in {
                choice.attrib.get("alias")
                for node in root.iter("Choices")
                for choice in node.findall("Choice")
            }


def test_manhattan_scope_wording_and_choice_hints_are_complete() -> None:
    for key, path in ACTIVE.items():
        root = ElementTree.parse(path).getroot()
        texts = {node.attrib["name"]: node.attrib["value"] for node in root.iter("Text")}
        assert set(texts) >= {
            "manhattan_layout_definition_text",
            "manhattan_layout_examples_text",
            "opening_closure_rule_text",
            "worker_scope_response_rule_text",
        }
        collapse = root.find(".//Collapse")
        assert collapse is not None
        assert collapse.attrib == {"bordered": "true", "open": "true"}
        panel = collapse.find("Panel")
        assert panel is not None
        assert panel.attrib["value"] in {"Manhattan 布局说明", "Manhattan Layout Guide"}
        collapsed_texts = {node.attrib.get("name") for node in panel.iter("Text")}
        assert collapsed_texts == {
            "manhattan_layout_definition_text",
            "manhattan_layout_examples_text",
            "opening_closure_rule_text",
        }
        assert "worker_scope_response_rule_text" not in collapsed_texts
        scope_text = texts["worker_scope_response_rule_text"]
        assert "Manhattan" in scope_text
        assert ("至少能够形成一个" in scope_text) if key.startswith("zh_") else ("at least one" in scope_text)

        for choices in root.iter("Choices"):
            assert choices.attrib.get("required") == "true"
            assert all(choice.attrib.get("hint", "").strip() for choice in choices.findall("Choice"))

        if key.startswith("zh_"):
            visible = " ".join(node.attrib.get("value", "") for node in root.iter("Text"))
            assert "曼哈顿世界" not in visible
            assert "研究者真值" not in visible
            assert "本题仅记录" not in visible


def test_semi_xml_places_pre_edit_fields_before_post_task_fields() -> None:
    for role in ("semi", "future"):
        for language in ("zh", "en"):
            text = ACTIVE[f"{language}_{role}"].read_text(encoding="utf-8")
            assert text.index('name="material_issue"') < text.index('name="worker_scope_response"')


def test_old_taxonomy_is_absent_from_current_xml() -> None:
    for path in ACTIVE.values():
        aliases = {alias for values in _choice_aliases(path).values() for alias in values}
        assert aliases.isdisjoint({"trivial", "acceptable", "fail", "missing_or_unusable_proposal"})


def test_v2_manifest_is_superseded_and_points_to_the_prechange_snapshot() -> None:
    manifest = json.loads(V2_MANIFEST.read_text(encoding="utf-8"))
    assert manifest["status"] == "superseded_frozen_snapshot"
    assert manifest["deployment_status"] == "superseded_without_deployment"
    assert manifest["superseded_by"] == "label_studio_uncertainty_meta_v1"
    active = {row["artifact_id"]: row for row in manifest["active_scope_v2"]["files"]}
    for key, snapshot in PRECHANGE_XML.items():
        assert (ROOT / active[key]["path"]).resolve() == snapshot.resolve()
        assert _sha256(snapshot) == active[key]["sha256"]


def test_v1_manifest_is_the_project86_development_snapshot() -> None:
    manifest = json.loads(UNCERTAINTY_MANIFEST_V1.read_text(encoding="utf-8"))
    assert manifest["status"] == "superseded_development_test_snapshot"
    assert manifest["deployment_status"] == "development_test_project_86_only_not_formal"
    assert manifest["superseded_by"] == "label_studio_uncertainty_meta_v2"
    assert manifest["snapshot_storage"] == "git_history"
    assert manifest["snapshot_git_revision"] == "e1038a9"
    assert "snapshot_root" not in manifest
    for paths in manifest["files"].values():
        for path in paths:
            assert (ROOT / path).is_file()


def test_uncertainty_v2_manifest_records_the_frozen_boundaries() -> None:
    manifest = json.loads(UNCERTAINTY_MANIFEST_V2.read_text(encoding="utf-8"))
    assert manifest["schema_version"] == "label_studio_uncertainty_meta_manifest_v2"
    assert manifest["manifest_id"] == "label_studio_uncertainty_meta_v2"
    assert manifest["deployment_status"] == "local_artifacts_ready_not_deployed"
    assert manifest["timing_basis"] == "worker_instruction_only_not_system_locked"
    assert manifest["proposal_missing_not_collected"] is True
    assert manifest["edit_operation_count_not_collected"] is True
    assert manifest["historical_data_reclassified"] is False
    assert manifest["paper_a_method_contract_changed"] is False
    assert manifest["boundaries"]["technical_time_lock"] is False
    assert manifest["boundaries"]["phase_event_persistence"] == "not_collected"
    assert manifest["boundaries"]["strict_server_auditable_timing"] is False
    assert set(manifest["image_fields"]) == IMAGE_FIELDS
    assert set(manifest["proposal_fields"]) == PROPOSAL_FIELDS
    assert manifest["worker_primary_defect_collected"] is False
    assert manifest["inactive_branch_policy"]["material_issue_no"] == "clear_on_selection_and_fail_closed_before_submit"
    assert manifest["inactive_branch_policy"]["qa_flag"] == "inactive_branch_residual_blocked"


def test_original_c1_freeze_manifest_is_still_preserved() -> None:
    freeze = V1_HISTORY / "label_studio_c1_xml_freeze_manifest_v1.json"
    manifest = json.loads(V2_MANIFEST.read_text(encoding="utf-8"))
    assert _sha256(freeze) == manifest["historical_snapshot"]["legacy_freeze_manifest_sha256"]
