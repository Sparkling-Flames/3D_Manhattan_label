from pathlib import Path
import hashlib
import json
from xml.etree import ElementTree


ROOT = Path(__file__).resolve().parents[1]
CHINESE = ROOT / "tools" / "label_studio" / "label_studio_view_config.xml"
ENGLISH = ROOT / "tools" / "thesis_main" / "foreign_recruitment" / "label_studio_view_config_en.xml"
CHINESE_FUTURE = ROOT / "tools" / "label_studio" / "label_studio_view_config_c2_future.xml"
ENGLISH_FUTURE = ROOT / "tools" / "thesis_main" / "foreign_recruitment" / "label_studio_view_config_c2_future_en.xml"
FREEZE = ROOT / "tools" / "label_studio" / "label_studio_c1_xml_freeze_manifest_v1.json"


def _choices(path: Path) -> dict[str, list[str]]:
    tree = ElementTree.parse(path)
    return {
        node.attrib["name"]: [choice.attrib["alias"] for choice in node.findall("Choice")]
        for node in tree.findall(".//Choices")
        if node.attrib.get("name") in {"scope", "difficulty", "model_issue"}
    }


def test_historical_and_future_bilingual_xml_keep_the_same_annotation_schema() -> None:
    assert _choices(CHINESE) == _choices(ENGLISH)
    assert _choices(CHINESE_FUTURE) == _choices(ENGLISH_FUTURE)


def test_historical_c1_xml_is_not_silently_rewritten_and_future_rules_are_separate() -> None:
    historical_chinese = CHINESE.read_text(encoding="utf-8")
    historical_english = ENGLISH.read_text(encoding="utf-8")
    future_chinese = CHINESE_FUTURE.read_text(encoding="utf-8")
    future_english = ENGLISH_FUTURE.read_text(encoding="utf-8")
    assert "Scope as the authoritative OOS signal" not in historical_chinese
    assert "acceptable is an explicit mutually exclusive answer" not in historical_english
    assert "Scope 字段是 OOS 的唯一权威信号" in future_chinese
    assert "Scope is the authoritative OOS field" in future_english
    assert "acceptable 是与所有具体 issue 互斥的显式回答" in future_chinese
    assert "acceptable is an explicit mutually exclusive answer" in future_english


def test_historical_xml_sha_is_frozen_in_manifest() -> None:
    manifest = json.loads(FREEZE.read_text(encoding="utf-8"))
    for key, path in (("chinese_sha256", CHINESE), ("english_sha256", ENGLISH)):
        assert hashlib.sha256(path.read_bytes()).hexdigest() == manifest["historical_c1"][key]
    assert manifest["formal_c1_data_present"] is False
