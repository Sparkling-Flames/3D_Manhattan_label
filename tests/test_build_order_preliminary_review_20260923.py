import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_review_keeps_point_identity_and_gt_edge_audit():
    data = json.loads((ROOT / "analysis_results/order_preliminary_review_20260923/建议清单.json").read_text(encoding="utf-8"))
    assert data["counts"]["checked_images"] == 10
    assert data["counts"]["canonical_new_reorder_suggestions"] == 0
    assert data["counts"]["gt_representation_suggestions"] == 3
    assert len(data["unreviewed_images"]) == 249
    for record in data["records"]:
        current = record["current_ring_order"]
        assert sorted(point for group in record["current_ring_groups"] for point in group["original_point_ids_1based"]) == list(
            range(1, 2 * len(current) + 1)
        )
        assert len(record["current_ring_edges"]) == len(current)
        assert record["pending_user_confirmation"] and not record["applied"]
        if record["verdict"] == "无法确定":
            assert record["suggested_ring_order"] is None
    assert {r["image_code"]: r["source_gt_edge_replacements"] for r in data["records"]
            if r["object_type"] == "mp3d_gt_original"} == {
                "S9hNv5qa7GM-08": 4, "q9vSo1VnCiC-24": 5, "uNb9QFRL6hY-81": 2,
            }
