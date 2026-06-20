import json
from pathlib import Path

import pytest

from tools.paper_a_manhattan.run_manhattan_hypothesis_local_review import (
    REPO_ROOT,
    _local_server_root,
    build_bridge_manifest,
    run,
    select_review_candidates,
)
from tools.paper_a_manhattan.run_manhattan_hypothesis_ranking_core import (
    build_payload,
)


def test_core_bridge_selects_ranked_candidates_and_renders_existing_viewer(tmp_path):
    core = build_payload()
    selected = select_review_candidates(core)
    ids = [row["candidate_id"] for row in selected]
    expected = []
    for bucket_name in (
        "best_balanced",
        "best_short_wall_preserving",
        "best_low_movement",
    ):
        candidate = core["portfolio_ranking"][bucket_name]["candidate"]
        if candidate and candidate["candidate_id"] not in expected:
            expected.append(candidate["candidate_id"])
    assert ids[: len(expected)] == expected
    assert len(ids) <= 5
    assert len(ids) == len(set(ids))

    canonical = {row["candidate_id"]: row for row in core["candidate_set"]}
    for row in selected[len(expected) :]:
        candidate = canonical[row["candidate_id"]]
        assert candidate["hard_gate_passed"] is True
        assert candidate["is_improving_hypothesis"] is True
        assert row["review_role"].startswith("diagnostic_")

    best_id = core["portfolio_ranking"]["best_balanced"]["candidate"]["candidate_id"]
    if best_id == "m1528_candidate_0017":
        changes = core["candidate_review_geometry"][best_id]["coordinate_changes"]
        deltas = {
            int(change["effective_pair_index"]): change["fields"]["bottom_y"]["after"] - change["fields"]["bottom_y"]["before"]
            for change in changes
        }
        assert deltas == {6: pytest.approx(-1.0), 7: pytest.approx(1.0)}

    core_path = tmp_path / "hypothesis_ranking_core.json"
    core_path.write_text(json.dumps(core), encoding="utf-8")
    manifest = build_bridge_manifest(core, core_path=core_path)
    assert manifest["core_provenance"]["sha256"]
    assert manifest["safety_boundary"]["annotation_writeback"] is False

    paths = run(
        core_path,
        tmp_path / "review",
        image_root=Path("data/mp3d_layout/img_v"),
    )
    payload = json.loads(paths["json"].read_text(encoding="utf-8"))
    assert len(payload["variants"]) <= 6
    assert payload["preferred_panel_variants"][0] == "original"
    assert _local_server_root(REPO_ROOT / "analysis_results/review") == REPO_ROOT
    assert _local_server_root(tmp_path / "review") is None
    assert set(ids) == {row["name"] for row in payload["variants"] if row["name"] != "original"}
    html = paths["html"].read_text(encoding="utf-8")
    assert '<details id="original-panorama" open>' in html
    assert 'id="original-panorama-image"' in html
    assert "Embedded local panorama · read-only" in html
    assert "data:image/jpeg;base64," in html
    assert "launcher" not in paths  # tmp_path is outside the repository server root
