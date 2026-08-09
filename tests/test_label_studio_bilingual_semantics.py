from pathlib import Path
import hashlib
import json
from xml.etree import ElementTree


ROOT = Path(__file__).resolve().parents[1]
LS = ROOT / "tools" / "label_studio"
EN = LS / "localized" / "en"
HISTORY = LS / "config_history" / "scope_instruction_v1_pre_block2"
MANIFEST = LS / "label_studio_xml_instruction_manifest_v2.json"

ACTIVE = {
    "zh_semi": LS / "label_studio_view_config.xml",
    "zh_manual": LS / "label_studio_view_config_manual.xml",
    "zh_future": LS / "label_studio_view_config_c2_future.xml",
    "en_semi": EN / "label_studio_view_config_en.xml",
    "en_manual": EN / "label_studio_view_config_manual_en.xml",
    "en_future": EN / "label_studio_view_config_c2_future_en.xml",
}
SNAPSHOT = {
    "zh_semi": HISTORY / "zh" / "label_studio_view_config.xml",
    "zh_manual": HISTORY / "zh" / "label_studio_view_config_manual.xml",
    "zh_future": HISTORY / "zh" / "label_studio_view_config_c2_future.xml",
    "en_semi": HISTORY / "en" / "label_studio_view_config_en.xml",
    "en_manual": HISTORY / "en" / "label_studio_view_config_manual_en.xml",
    "en_future": HISTORY / "en" / "label_studio_view_config_c2_future_en.xml",
}


def _choices(path: Path) -> dict[str, list[str]]:
    tree = ElementTree.parse(path)
    return {
        node.attrib["name"]: [choice.attrib["alias"] for choice in node.findall("Choice")]
        for node in tree.findall(".//Choices")
        if node.attrib.get("name") in {"scope", "difficulty", "model_issue"}
    }


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _control_signature(path: Path) -> list[tuple[str, str, str, str, str]]:
    root = ElementTree.parse(path).getroot()
    return [
        (
            node.tag,
            node.attrib.get("name", ""),
            node.attrib.get("toName", ""),
            node.attrib.get("choice", ""),
            node.attrib.get("required", ""),
        )
        for node in root.iter()
        if node.tag in {"Image", "KeyPointLabels", "BrushLabels", "Choices", "HyperText"}
    ]


def _rule_text(path: Path, name: str) -> str:
    node = ElementTree.parse(path).find(f".//Text[@name='{name}']")
    assert node is not None
    return node.attrib["value"]


def _choice_semantics(path: Path, name: str) -> list[tuple[str, str, str]]:
    node = ElementTree.parse(path).find(f".//Choices[@name='{name}']")
    assert node is not None
    return [
        (choice.attrib["alias"], choice.attrib.get("value", ""), choice.attrib.get("hint", ""))
        for choice in node.findall("Choice")
    ]


def test_active_bilingual_xml_keeps_the_same_annotation_schema() -> None:
    for role in ("semi", "manual", "future"):
        assert _choices(ACTIVE[f"zh_{role}"]) == _choices(ACTIVE[f"en_{role}"])


def test_scope_v2_keeps_every_v1_alias() -> None:
    for key, active_path in ACTIVE.items():
        assert _choices(active_path) == _choices(SNAPSHOT[key])
        assert _control_signature(active_path) == _control_signature(SNAPSHOT[key])


def test_annotation_v2_uses_current_space_wording_without_room_ambiguity() -> None:
    active_text = "\n".join(path.read_text(encoding="utf-8") for path in ACTIVE.values())
    assert "相机所在的当前空间" in active_text
    assert "current space containing the camera" in active_text
    assert "沿属于当前空间的围护墙连续标注" in active_text
    assert "Follow its enclosing walls through corners" in active_text
    for obsolete in (
        "主房间",
        "相机房间",
        "main room",
        "camera room",
        "camera-room",
        "明确转角",
        "clear turn",
        "主指标纳入",
        "主指标剔除",
    ):
        assert obsolete not in active_text.lower()


def test_manual_and_semi_share_scope_and_difficulty_semantics() -> None:
    for language in ("zh", "en"):
        semi, manual = ACTIVE[f"{language}_semi"], ACTIVE[f"{language}_manual"]
        for field in ("scope", "difficulty"):
            assert _rule_text(semi, f"{field}_rule_text") == _rule_text(manual, f"{field}_rule_text")
            assert _choice_semantics(semi, field) == _choice_semantics(manual, field)


def test_difficulty_and_model_issue_v2_boundaries_are_explicit() -> None:
    active_text = "\n".join(path.read_text(encoding="utf-8") for path in ACTIVE.values())
    assert "同一个底层原因" in active_text
    assert "same underlying cause" in active_text
    assert "初始模型几何无需调整，可以原样提交" in active_text
    assert "needs no adjustment and can be submitted unchanged" in active_text
    assert "无论调整幅度大小" in active_text
    assert "regardless of its size" in active_text
    assert "不要额外选择 fail" in active_text
    assert "Do not additionally select fail" in active_text
    for obsolete in ("无需显著修改", "仅需微调", "no major correction", "minor adjustment"):
        assert obsolete not in active_text.lower()


def test_model_issue_is_absent_from_manual_and_present_in_semi_and_future() -> None:
    for language in ("zh", "en"):
        assert "model_issue" not in _choices(ACTIVE[f"{language}_manual"])
        assert "model_issue" in _choices(ACTIVE[f"{language}_semi"])
        assert "model_issue" in _choices(ACTIVE[f"{language}_future"])


def test_historical_and_active_xml_sha_are_frozen_in_v2_manifest() -> None:
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    assert manifest["instruction_semantic_version"] == "paper_a_annotation_instruction_v2"
    assert manifest["historical_snapshot"]["instruction_version"] == "scope_instruction_v1"
    assert manifest["active_scope_v2"]["instruction_version"] == "scope_instruction_v2"
    assert manifest["active_scope_v2"]["annotation_instruction_version"] == "paper_a_annotation_instruction_v2"
    assert manifest["active_scope_v2"]["effective_from"] == "C2-A-RP Block 2"
    assert manifest["active_scope_v2"]["alias_schema_unchanged"] is True
    assert manifest["deployment_status"] == "local_artifacts_ready_not_deployed"

    historical = {row["artifact_id"]: row for row in manifest["historical_snapshot"]["files"]}
    active = {row["artifact_id"]: row for row in manifest["active_scope_v2"]["files"]}
    for key in ACTIVE:
        assert _sha256(SNAPSHOT[key]) == historical[key]["sha256"]
        assert _sha256(ACTIVE[key]) == active[key]["sha256"]


def test_original_c1_freeze_manifest_is_preserved_with_snapshot() -> None:
    freeze = HISTORY / "label_studio_c1_xml_freeze_manifest_v1.json"
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    assert _sha256(freeze) == manifest["historical_snapshot"]["legacy_freeze_manifest_sha256"]
    historical = json.loads(freeze.read_text(encoding="utf-8"))["historical_c1"]
    assert historical["chinese_source_git_blob_sha"] == "fa083fbdbaecede42fc6c92486496a2b69441537"
    assert historical["english_source_git_blob_sha"] == "cd7cfeff16d5ec59c14758b8b9c5d825598d6282"
