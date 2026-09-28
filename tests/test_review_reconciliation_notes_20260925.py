"""本轮释义只连接证据，不写入最终裁决或执行点位修复。"""

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
NOTES = ROOT / "tools/thesis_main/analysis/review_reconciliation_notes_20260925.json"


def load_reviews():
    result = {}
    for reviewer, filename in (
        ("user", "全历史标注_我的审核_20260923(1).json"),
        ("yizheng", "全历史标注_我的审核_20260923 一正.json"),
    ):
        path = ROOT / f"analysis_results/review_reconciliation_20260925/evidence/{reviewer}_review.json"
        if not path.exists():
            path = Path("C:/Users/ASUS/Downloads") / filename
        source = json.loads(path.read_text(encoding="utf-8-sig"))["decisions"]
        result.update({f"{reviewer}:{key}": row for key, row in source.items()})
    return result


def test_notes_cover_all_comments_without_inheriting_decisions():
    notes = json.loads(NOTES.read_text(encoding="utf-8"))
    source = load_reviews()
    assert notes["schema"] == "review_reconciliation_notes_v1"
    assert set(notes["events"]) == {key for key, row in source.items() if row["comment"].strip()}
    assert len(notes["events"]) == 696
    assert set(notes["images"]) == {row["code"] for row in source.values()}
    for key, event in notes["events"].items():
        assert event["summary"].strip()
        assert set(event["targets"]) <= {"annotation", "image", "peers", "reference", "representation"}
        assert event["topics"]
        assert isinstance(event["unresolved_reference"], bool)
        assert "verdict" not in event and "applied" not in event
        for anchor in event["anchor_event_ids"]:
            assert anchor in notes["events"] and anchor != key
            assert source[anchor]["image_id"] == source[key]["image_id"]
    for code, image in notes["images"].items():
        for question in image["questions"]:
            assert question["kind"] in {"cross_reviewer", "same_pattern", "historical", "repair", "scope", "reference", "unresolved_reference"}
            assert all(key in notes["events"] and source[key]["code"] == code for key in question["evidence_event_ids"])
        assert all((ROOT / item["source"]).exists() for item in image["historical_notes"])


def test_comment_targets_and_repairs_remain_distinct():
    notes = json.loads(NOTES.read_text(encoding="utf-8"))
    events = notes["events"]
    blue = events["yizheng:1892d2228413184cfbd6"]
    assert blue["unresolved_reference"] and "reference" in blue["targets"]
    assert "导出未记录" in blue["summary"]
    assert "修复核查" in events["user:032cd152706166629e82"]["topics"]
    assert "修复核查" not in events["user:new_93_3583_7136_W012"]["topics"]
    pair = events["user:2a11d537c790512c"]
    assert "配对核查" in pair["topics"] and "修复核查" not in pair["topics"]
    assert "未要求交换" in pair["summary"]
    assert any(q["kind"] == "cross_reviewer" and set(q["workers"]) == {"W013", "W015"} for q in notes["images"]["jtcxE69GiFV-11"]["questions"])
    assert any(q["kind"] == "cross_reviewer" and set(q["workers"]) == {"W035", "W028"} for q in notes["images"]["x8F5xyUWy9e-01"]["questions"])


def test_missing_anchors_and_historical_disagreements_are_visible():
    notes = json.loads(NOTES.read_text(encoding="utf-8"))
    unknown = notes["events"]["user:d3d1738a5f7c5fa69f13"]
    assert unknown["unresolved_reference"] and not unknown["anchor_event_ids"]
    for code in ("UwV83HsGsw3-23", "b8cTxDM8gDG-19"):
        assert notes["images"][code]["historical_notes"]
    doorway = notes["images"]["jtcxE69GiFV-12"]
    assert doorway["doorway_hold"] and "暂不归门洞" in doorway["summary"]
    partition = notes["images"]["X7HyMhZNoso-19"]
    assert any("必须保留" in item["quote"] for item in partition["historical_notes"])
    assert any(item["kind"] == "historical" for item in partition["questions"])
