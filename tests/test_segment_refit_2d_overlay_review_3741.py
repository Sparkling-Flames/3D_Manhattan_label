import hashlib
import json
from pathlib import Path

from tools.paper_a_manhattan.run_segment_refit_2d_overlay_review_3741 import run

PROTECTED = (
    Path("export_label/groudTruth.json"),
    Path("tools/paper_a_manhattan/run_manhattan_hypothesis_ranking_core.py"),
    Path("tools/paper_a_manhattan/manhattan_constrained_hypothesis_evaluator.py"),
    Path("tools/paper_a_manhattan/manhattan_hypothesis_portfolio.py"),
)


def _sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_materializes_source_aware_2d_overlay_without_writeback(tmp_path):
    before = {path: _sha(path) for path in PROTECTED}
    paths = run(tmp_path)
    payload = json.loads(paths["payload"].read_text(encoding="utf-8"))
    html = paths["html"].read_text(encoding="utf-8")

    assert all(path.exists() for path in paths.values())
    assert len(paths["summary"].read_text(encoding="utf-8").splitlines()) <= 60
    assert payload["coordinate_mode"] == "ls_percent"
    assert payload["coordinate_range_check"]["all_coordinates_in_range"] is True
    assert set(payload["baseline_points_by_source_pair_id"]) == set(
        payload["corrected_points_by_source_pair_id"]
    )
    assert payload["baseline_points_by_source_pair_id"]["2"]["solver_position"] == 1
    assert payload["corrected_points_by_source_pair_id"]["2"]["source_pair_id"] == 2
    assert payload["deltas_by_source_pair_id"]["2"]["bottom_movement"] > 8.0
    assert set(payload["focus_groups"]) >= {
        "pair2",
        "pair1",
        "pair3_4",
        "pair5_6_7_8",
        "pair12_11_1",
        "pair9_10",
    }
    assert payload["source_image"] in html
    assert all(
        control in html
        for control in (
            "showBaseline",
            "showCorrected",
            "showArrows",
            "showLabels",
            "showVertical",
            "showBottom",
            "showTop",
            "onlyChanged",
            "opacity",
            "pointSize",
        )
    )
    assert all(label in html for label in ("source pair 2", "5–6–7–8", "12–11–1"))
    assert "height_review_required_9_10" in html
    assert "2D visual review only; no writeback; human must confirm." in html
    for field in (
        "accepted",
        "downstream_recommendation",
        "candidate_preference_authorized",
        "annotation_writeback",
        "annotation_patch_generated",
    ):
        assert payload[field] is False
    assert {path: _sha(path) for path in PROTECTED} == before
