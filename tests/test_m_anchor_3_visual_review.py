import json

from tools.paper_a_manhattan.run_m_anchor_3_visual_review import run


def test_m_anchor_3_visual_review_materializes_three_overlays(tmp_path):
    paths = run(tmp_path)
    manifest = json.loads(paths["manifest"].read_text(encoding="utf-8"))
    index = paths["index"].read_text(encoding="utf-8")

    assert manifest["schema_version"] == "m_anchor_3_visual_review_manifest_v1"
    assert manifest["candidate_count"] == 3
    assert manifest["accepted"] is False
    assert manifest["downstream_recommendation"] is False
    assert manifest["annotation_writeback"] is False
    assert "No writeback, no ranking, no final acceptance" in index
    for row in manifest["entries"]:
        html_path = tmp_path / row["html"]
        assert html_path.exists()
        html = html_path.read_text(encoding="utf-8")
        assert row["candidate_id"] in html
        assert "Only s6 bottom_y changes" in html
        assert "Per-wall residuals, degrees" in html
        assert "residual before" in html
        assert "6→5" in html
        assert "M-Anchor.3 visual review only" in html
        assert row["accepted"] is False
        assert row["annotation_writeback"] is False
