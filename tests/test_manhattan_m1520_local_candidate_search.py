import copy
import json
from pathlib import Path

from tools.paper_a_manhattan.manhattan_m1520_local_candidate_search import (
    CORE_WINDOW,
    FAMILIES,
    SAFETY_BOUNDARY,
    generate_local_candidates,
    run_local_candidate_search,
)
from tools.paper_a_manhattan.run_m1520_local_candidate_search import (
    render_markdown_report,
    run,
)


def _pairs():
    xs = (5.0, 15.0, 25.0, 35.0, 44.8, 44.0, 52.0, 51.0, 65.0, 85.0)
    rows = []
    for index, x in enumerate(xs, start=1):
        rows.append(
            {
                "top": {"x": x + (0.2 if index == 5 else 0.0), "y": 20.0},
                "bottom": {"x": x, "y": 80.0},
                "effective_pair_index": index,
                "source_preview_order_index": index,
            }
        )
    return rows


def _lookup(rows):
    return {int(row["effective_pair_index"]): row for row in rows}


def test_generation_has_four_bounded_families_and_never_uses_bottom_only_y():
    original = _pairs()
    frozen = copy.deepcopy(original)
    candidates = generate_local_candidates(original)

    assert original == frozen
    assert {row["family"] for row in candidates} == set(FAMILIES)
    assert all(set(row["changed_pair_indices"]).issubset(CORE_WINDOW) for row in candidates)

    before = _lookup(original)
    for candidate in candidates:
        after = _lookup(candidate["ordered_pairs"])
        for pair_index in set(before) - set(CORE_WINDOW):
            assert after[pair_index] == before[pair_index]
        if candidate["family"] == "height_aware_y_probe":
            pair_index = candidate["changed_pair_indices"][0]
            assert after[pair_index]["top"]["y"] != before[pair_index]["top"]["y"]
            assert after[pair_index]["bottom"]["y"] != before[pair_index]["bottom"]["y"]


def test_topology_hypotheses_keep_every_pair_and_are_never_recommended():
    original = _pairs()
    result = run_local_candidate_search(original, retain_per_family=3)
    topology = [
        row
        for row in result["candidates"]
        if row["family"] == "local_order_topology_hypothesis"
    ]

    assert topology
    assert all(row["disposition"] in {"neutral_review_topology_hypothesis", "suppressed_hard_risk"} for row in topology)
    assert all(row["manual_ls_try_recommended"] is False for row in topology)
    assert all(sorted(row["ordered_pair_indices_after"]) == list(range(1, 11)) for row in topology)


def test_score_contract_is_local_and_partial_result_is_not_a_final_fix():
    result = run_local_candidate_search(_pairs(), retain_per_family=3)

    assert result["scope"]["local_window"] == [5, 6, 7, 8]
    assert result["scope"]["global_optimization"] is False
    assert result["score_contract"]["final_fix_authorized"] is False
    assert set(result["score_contract"]["weights"]) == {
        "window_wall_residual_delta",
        "window_corner_residual_delta",
        "height_residual_delta",
        "minimum_wall_length_penalty_delta",
        "dense_separation_loss",
        "movement_l1_ls_percent",
    }
    assert all("self_intersection" in row for row in result["candidates"])
    assert all("dense_separation_preservation" in row["score_components"] for row in result["candidates"])
    assert all(row["disposition"] != "final_fix" for row in result["candidates"])


def test_report_contains_coordinates_required_walls_and_human_try_field():
    result = run_local_candidate_search(_pairs(), retain_per_family=1)
    report = render_markdown_report(result)

    assert "2D coordinate changes" in report
    assert "3D coordinates" in report
    assert "4-5" in report and "5-6" in report and "6-7" in report and "7-8" in report
    assert "Recommend manual LS try" in report
    assert "partial_neutral_review" in report
    assert "annotation patch" in report
    for field in ("top_x", "bottom_x", "top_y", "bottom_y"):
        assert field in report


def test_cli_writes_read_only_json_and_markdown(tmp_path):
    input_path = tmp_path / "input.json"
    input_path.write_text(json.dumps({"ordered_pairs": _pairs()}), encoding="utf-8")
    paths = run(input_path=input_path, out_dir=tmp_path / "out", retain_per_family=1)

    assert paths["json"].is_file()
    assert paths["report"].is_file()
    payload = json.loads(paths["json"].read_text(encoding="utf-8"))
    assert payload["input_provenance"]["ordered_pair_source"] == "input.ordered_pairs"
    assert payload["safety_boundary"] == SAFETY_BOUNDARY
    assert payload["projection_config"]["coordinate_mode"] == "ls_percent"


def test_static_boundary_has_no_writeback_or_formal_chain():
    source = Path(
        "tools/paper_a_manhattan/manhattan_m1520_local_candidate_search.py"
    ).read_text(encoding="utf-8").lower()

    assert '"annotation_write_allowed": false' in source
    assert '"annotation_patch_generated": false' in source
    assert '"routing_input": false' in source
    assert '"formal_artifact": false' in source
    assert "writeback" not in source
    assert "formal_g_t" not in source
    assert "p1/c1/c2/t1/v1" not in source
