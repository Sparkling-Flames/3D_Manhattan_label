import csv
from pathlib import Path

from tools.thesis_main.analysis.audit_prescreen_topology_support import run


ROOT = Path(__file__).resolve().parents[1]


def test_real_prescreen_support_denominator_and_repair_disposition(tmp_path: Path) -> None:
    run(
        ROOT,
        ROOT / "analysis_results" / "prescreen_closeout_final_gold_v2_20260701",
        tmp_path,
        replicates=3,
        seed=20260819,
    )
    support = {row["scenario"]: row for row in csv.DictReader((tmp_path / "PRESCREEN_SUPPORT_FLOW.csv").open(encoding="utf-8"))}
    assert (support["c1_eligible_combined"]["unique_images"], support["c1_eligible_combined"]["normalizer_valid_rows"]) == ("29", "662")
    assert (support["current20_combined"]["min_valid_k"], support["current20_combined"]["tasks_k_ge_5"]) == ("19", "29")

    invalid = list(csv.DictReader((tmp_path / "PRESCREEN_NORMALIZER_DISPOSITION.csv").open(encoding="utf-8")))
    assert len(invalid) == 5
    assert not any(row["repair_applied"] == "true" for row in invalid)
    assert {row["raw_failure_reason"] for row in invalid} == {"odd_keypoint_count", "out_of_range"}
