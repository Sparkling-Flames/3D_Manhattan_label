import hashlib
import json
from pathlib import Path

from tools.paper_a_manhattan.run_m1525_visual_verdict_pack import (
    DEFAULT_CANDIDATE_SEARCH,
    SAFETY_BOUNDARY,
    run,
)


def test_m1525_visual_verdict_pack(tmp_path):
    paths = run(tmp_path)

    assert paths["json"].is_file()
    assert paths["report"].is_file()
    assert {path.name for path in tmp_path.iterdir()} == {
        "visual_verdict.json",
        "visual_verdict.md",
    }

    payload = json.loads(paths["json"].read_text(encoding="utf-8"))
    assert payload["schema_version"] == "m15_25_visual_verdict_pack_v1"
    assert payload["case_name"] == "task218_ann3741"
    assert payload["overall_verdict"]["direct_fix_available"] is False
    assert (
        payload["overall_verdict"]["all_candidates_direct_ls_trial_allowed"]
        is False
    )
    assert payload["overall_verdict"]["best_visual_candidate"] == "candidate_2"

    findings = payload["manual_findings"]
    assert findings["y_height_unresolved_pairs"] == [1, 2, 5, 6, 7, 8]
    assert findings["unresolved_wall_surface_footprint_regions"] == [
        "2-3",
        "5-6-7-8",
    ]
    assert findings["primary_unresolved_edge"] == "6-7"

    assert payload["safety_boundary"] == SAFETY_BOUNDARY
    assert SAFETY_BOUNDARY["annotation_write_allowed"] is False
    assert SAFETY_BOUNDARY["annotation_patch_generated"] is False
    assert SAFETY_BOUNDARY["automatic_apply"] is False
    assert SAFETY_BOUNDARY["worker_facing"] is False
    assert SAFETY_BOUNDARY["routing_input"] is False
    assert SAFETY_BOUNDARY["formal_artifact"] is False

    candidate_source = payload["source_artifacts"]["candidate_search"]
    assert candidate_source["path"] == DEFAULT_CANDIDATE_SEARCH.as_posix()
    assert candidate_source["sha256"] == hashlib.sha256(
        DEFAULT_CANDIDATE_SEARCH.read_bytes()
    ).hexdigest()
    assertion_source = payload["source_artifacts"]["expert_assertion"]
    assert assertion_source and assertion_source["path"].endswith(
        "task218_ann3741/expert_assertion.json"
    )

    verdicts = payload["per_candidate_visual_verdict"]
    assert list(verdicts) == [f"candidate_{index}" for index in range(1, 6)]
    assert verdicts["candidate_2"]["direct_fix"] is False
    assert verdicts["candidate_5"]["direct_fix"] is False
    assert all(row["sufficient"] is False for row in verdicts.values())

    report = paths["report"].read_text(encoding="utf-8")
    for expected in (
        "M15.25 Visual Verdict Pack — task218_ann3741",
        "No direct candidate fix is available.",
        "largest perturbation but still inadequate",
        "pairs `[1, 2, 5, 6, 7, 8]`",
        "`2-3` and `5-6-7-8`",
        "No candidate may be applied directly in Label Studio.",
        "m15_23_5_multi_candidate_compare_grid",
        "m15_26_primary_edge_constrained_wall_surface_probe",
    ):
        assert expected in report

    script = Path(
        "tools/paper_a_manhattan/run_m1525_visual_verdict_pack.py"
    ).read_text(encoding="utf-8")
    for forbidden_import in (
        "manhattan_3d_projection.py",
        "manhattan_m1520_local_candidate_search",
        "vis_3d.html",
    ):
        assert forbidden_import not in script
