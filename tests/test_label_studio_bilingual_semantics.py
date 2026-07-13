from pathlib import Path
from xml.etree import ElementTree


ROOT = Path(__file__).resolve().parents[1]
CHINESE = ROOT / "tools" / "label_studio" / "label_studio_view_config.xml"
ENGLISH = ROOT / "tools" / "thesis_main" / "foreign_recruitment" / "label_studio_view_config_en.xml"


def _choices(path: Path) -> dict[str, list[str]]:
    tree = ElementTree.parse(path)
    return {
        node.attrib["name"]: [choice.attrib["alias"] for choice in node.findall("Choice")]
        for node in tree.findall(".//Choices")
        if node.attrib.get("name") in {"scope", "difficulty", "model_issue"}
    }


def test_bilingual_xml_keeps_the_same_annotation_schema() -> None:
    assert _choices(CHINESE) == _choices(ENGLISH)


def test_bilingual_xml_states_the_shared_exclusivity_rules() -> None:
    chinese = CHINESE.read_text(encoding="utf-8")
    english = ENGLISH.read_text(encoding="utf-8")
    assert "Scope 是 OOS 的权威判定" in chinese
    assert "Scope as the authoritative OOS signal" in english
    assert "它与任何具体 issue 互斥" in chinese
    assert "mutually exclusive with every concrete issue" in english
