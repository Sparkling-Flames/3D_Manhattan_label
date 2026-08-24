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
UNCERTAINTY_MANIFEST = LS / "label_studio_uncertainty_meta_manifest_v1.json"

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
    "scope_status",
    "multiple_plausible_layouts",
    "perceived_difficulty",
    "difficulty_reason_status",
    "difficulty_reason",
}
PROPOSAL_FIELDS = {
    "material_issue",
    "primary_issue_family",
    "secondary_issue_families",
    "required_correction",
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


def test_uncertainty_choice_values_are_frozen() -> None:
    semi = _choice_aliases(ACTIVE["zh_semi"])
    assert semi["scope_status"] == ["in_scope", "out_of_scope"]
    assert semi["multiple_plausible_layouts"] == ["no", "yes"]
    assert semi["perceived_difficulty"] == ["1", "2", "3", "4", "5"]
    assert semi["difficulty_reason_status"] == [
        "no_specific_reason",
        "one_or_more_specific_reasons",
    ]
    assert semi["difficulty_reason"] == [
        "occlusion",
        "low_texture",
        "seam_or_distortion",
        "reflection_or_transparency",
        "opening_or_adjacent_space",
        "image_quality",
        "other",
    ]
    assert semi["material_issue"] == ["no", "yes", "unsure"]
    assert semi["primary_issue_family"] == [
        "boundary_or_corner_localization",
        "underextension",
        "adjacent_space_overextension",
        "overparsing_or_ghost_structure",
        "duplicate_corner",
        "topology_order_or_closure",
        "other",
        "unsure",
    ]
    assert semi["secondary_issue_families"] == semi["primary_issue_family"][:-1]
    assert semi["required_correction"] == [
        "no_edit_needed",
        "optional_visual_micro_refinement",
        "minor_mandatory_coordinate_correction",
        "major_geometry_correction",
        "topology_change_or_redraw",
    ]
    assert semi["issue_confidence"] == ["1", "2", "3", "4", "5"]


def test_conditional_display_is_branching_not_time_locking() -> None:
    for path in ACTIVE.values():
        views = _visible_views(path)
        assert {
            (row.get("whenTagName"), row.get("whenChoiceValue")) for row in views
        } >= {("difficulty_reason_status", "one_or_more_specific_reasons")}
        text = path.read_text(encoding="utf-8").lower()
        for forbidden in ("phase_lock", "time_lock", "edit_operation_count", "proposal_missing"):
            assert forbidden not in text

    for role in ("semi", "future"):
        for language in ("zh", "en"):
            views = _visible_views(ACTIVE[f"{language}_{role}"])
            assert {
                (row.get("whenTagName"), row.get("whenChoiceValue")) for row in views
            } >= {("material_issue", "yes,unsure")}


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


def test_uncertainty_manifest_records_the_frozen_boundaries() -> None:
    manifest = json.loads(UNCERTAINTY_MANIFEST.read_text(encoding="utf-8"))
    assert manifest["schema_version"] == "label_studio_uncertainty_meta_manifest_v1"
    assert manifest["manifest_id"] == "label_studio_uncertainty_meta_v1"
    assert manifest["deployment_status"] == "local_artifacts_ready_not_deployed"
    assert manifest["timing_basis"] == "worker_instruction_only_not_system_locked"
    assert manifest["proposal_missing_not_collected"] is True
    assert manifest["edit_operation_count_not_collected"] is True
    assert manifest["historical_data_reclassified"] is False
    assert manifest["paper_a_method_contract_changed"] is False
    assert set(manifest["image_fields"]) == IMAGE_FIELDS
    assert set(manifest["proposal_fields"]) == PROPOSAL_FIELDS


def test_original_c1_freeze_manifest_is_still_preserved() -> None:
    freeze = V1_HISTORY / "label_studio_c1_xml_freeze_manifest_v1.json"
    manifest = json.loads(V2_MANIFEST.read_text(encoding="utf-8"))
    assert _sha256(freeze) == manifest["historical_snapshot"]["legacy_freeze_manifest_sha256"]
