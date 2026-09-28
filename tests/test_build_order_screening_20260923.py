import json
from pathlib import Path

from tools.thesis_main.analysis.build_order_screening_20260923 import curve_metrics, nonadjacent_crossings, projected_curve_crossings


ROOT = Path(__file__).resolve().parents[1]


def test_synthetic_geometry_and_full_coverage():
    assert nonadjacent_crossings([[0, 0], [1, 0], [1, 1], [0, 1]]) == 0
    assert nonadjacent_crossings([[0, 0], [1, 1], [0, 1], [1, 0]]) == 1
    bands = [[80, 180] for _ in range(512)]
    pair = [[[200, 160], [200, 360]]]
    assert curve_metrics(bands, pair)["max_kink_deg"] == 0
    bands[100][0] = 0
    assert curve_metrics(bands, pair)["max_kink_deg"] > 120
    square = [[[100, 100], [100, 400]], [[350, 100], [350, 400]],
              [[600, 100], [600, 400]], [[850, 100], [850, 400]]]
    assert projected_curve_crossings(square) == 0
    data = json.loads((ROOT / "analysis_results/order_screening_20260923/screening.json").read_text(encoding="utf-8"))
    assert data["coverage"]["annotations"] == 3019 and data["coverage"]["images"] == 259
    assert len({r["canonical_annotation_id"] for r in data["rows"]}) == 3019
    assert all(r["human_order_decision"] is None and r["human_suggested_order"] is None for r in data["rows"])
    for path in (ROOT / "tools/thesis_main/analysis/build_order_screening_20260923.py",
                 ROOT / "analysis_results/order_screening_20260923/index.html"):
        page = path.read_text(encoding="utf-8")
        assert "../order_studio_20260926/index.html?annotation=" in page
        assert "../consensus_visual_review_20260923/index.html?annotation=" not in page
