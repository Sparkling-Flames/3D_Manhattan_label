import copy
import json
from pathlib import Path

from tools.paper_a_manhattan.manhattan_m1520_local_candidate_search import (
    CORE_WINDOW,
    FAMILIES,
    SAFETY_BOUNDARY,
    _candidate_triage,
    generate_local_candidates,
    run_local_candidate_search,
)
from tools.paper_a_manhattan.run_m1520_local_candidate_search import (
    render_markdown_report,
    run,
)
from tools.paper_a_manhattan.run_local_3d_projection_review import extract_ordered_pairs


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
    topology = result["topology_hypotheses"]

    assert topology
    assert all(row["disposition"] in {"neutral_review_topology_hypothesis", "suppressed_hard_risk"} for row in topology)
    assert all(row["manual_ls_try_recommended"] is False for row in topology)
    assert all("candidate_rank" not in row for row in topology)
    assert all(row["family"] != "local_order_topology_hypothesis" for row in result["candidates"])
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
    assert "manual_ls_try_recommended" in report
    assert "partial_neutral_review" in report
    assert "annotation patch" in report
    assert report.index("## Executable candidates ranking") < report.index("## Read-only topology hypotheses")
    assert "Topology hypotheses are not executable candidate rankings." in report
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
    source = Path("tools/paper_a_manhattan/manhattan_m1520_local_candidate_search.py").read_text(encoding="utf-8").lower()
    runner = Path("tools/paper_a_manhattan/run_m1520_local_candidate_search.py").read_text(encoding="utf-8").lower()

    assert '"annotation_write_allowed": false' in source
    assert '"annotation_patch_generated": false' in source
    assert '"routing_input": false' in source
    assert '"formal_artifact": false' in source
    assert "writeback" not in source
    assert "formal_g_t" not in source
    assert "p1/c1/c2/t1/v1" not in source
    assert '"routing_input": true' not in source
    assert '"formal_artifact": true' not in source
    assert "annotation_patch" not in runner


def test_preserved_dynamic_short_wall_is_partial_not_manual_review():
    triage = _candidate_triage(
        {
            "family": "column_x_align_translate",
            "score": -1.0,
            "hard_gate": False,
            "edge_missing_after": [],
            "all_unresolved_required_edges": [],
            "short_wall_worsened": False,
            "below_dynamic_short_threshold": True,
            "short_wall_preservation_explanation": "pre-existing risk preserved",
            "short_wall_edges_after": ["5-6"],
            "manual_ls_try_recommended": True,
            "height_worsened": False,
            "score_components": {"height_residual": {"delta": 0.0}},
            "required_wall_residuals": [
                {
                    "edge": edge,
                    "before_residual_deg": 1.0,
                    "after_residual_deg": 1.0,
                    "edge_missing_after": False,
                }
                for edge in ("4-5", "5-6", "6-7", "7-8")
            ],
        }
    )

    assert triage["decision_class"] == "partial_diagnostic"
    assert triage["direct_ls_trial_allowed"] is False


def test_task218_ann3741_hardening_regression():
    input_path = Path(
        "analysis_results/paper_a_manhattan/single_image_manual_test/"
        "latest_gt_checked/task218_ann3741_m1516_stabilized_input.json"
    )
    pairs, _ = extract_ordered_pairs(json.loads(input_path.read_text(encoding="utf-8")))
    result = run_local_candidate_search(pairs, retain_per_family=3)
    executable = result["candidates"]
    topology = result["topology_hypotheses"]
    all_rows = [*executable, *topology]
    report = render_markdown_report(result)

    assert result["candidate_generation"]["generated_count"] == 42
    assert result["candidate_generation"]["retained_count"] == 12
    assert result["schema_version"] == "m15_20_local_candidate_search_v1_2"
    assert result["case_triage"]["direct_fix_available"] is False
    assert "6-7" in result["case_triage"]["primary_unresolved_edges"]
    assert {"5-6", "6-7"}.issubset(result["case_triage"]["persistent_short_wall_edges"])
    for row in executable:
        assert {
            "decision_class",
            "improves",
            "fails_because",
            "next_expert_check",
            "triage_summary",
            "direct_ls_trial_allowed",
        }.issubset(row)
        assert row["decision_class"] != "candidate_for_manual_review"
        assert row["direct_ls_trial_allowed"] is False
    assert all(row["disposition"] != "final_fix" for row in all_rows)
    assert all(row["manual_ls_try_recommended"] is False for row in topology)
    assert report.index("## Executable candidates ranking") < report.index("## Read-only topology hypotheses")

    align = next(row for row in executable if row["label"] == "pair_5_align_dx_+0.50")
    assert align["disposition"] in {"partial_neutral_review", "neutral_review"}
    assert "6-7" in align["all_unresolved_required_edges"]
    assert any(text.startswith("5-6 residual improves") for text in align["improves"])
    assert any(text.startswith("6-7 remains unresolved") for text in align["fails_because"])
    assert "6-7" in align["triage_summary"]

    short = next(
        row
        for row in executable
        if any(
            wall["after_floor_wall_length"] is not None
            and 0.178 < wall["after_floor_wall_length"] < 0.180
            for wall in row["required_wall_residuals"]
        )
    )
    assert short["below_dynamic_short_threshold"] is True
    assert short["short_wall_worsened"] is True
    assert short["manual_ls_try_recommended"] is False

    missing = next(row for row in topology if row["edge_missing_after"])
    assert missing["edge_missing_after"]
    assert any(
        wall["edge_missing_after"] is True
        for wall in missing["required_wall_residuals"]
    )
    topology_report = report[report.index("## Read-only topology hypotheses") :]
    assert "Diagnostic score" in topology_report
    assert "- Score:" not in topology_report
