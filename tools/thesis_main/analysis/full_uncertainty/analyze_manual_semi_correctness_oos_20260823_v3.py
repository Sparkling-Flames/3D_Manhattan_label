from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from tools.thesis_main.analysis.full_uncertainty import analyze_manual_semi_correctness_oos_20260823 as v1
from tools.thesis_main.analysis.full_uncertainty import analyze_manual_semi_correctness_oos_20260823_v2 as v2


ROOT = Path(__file__).resolve().parents[4]
OUT = ROOT / "analysis_results" / "manual_semi_correctness_oos_20260823"


def main() -> None:
    v2.main()

    # Resource arithmetic only; no worker-image assignment manifest is materialized here.
    designs = [
        {
            "design": "A_60_image_three_arm_power_priority",
            "images": 60,
            "arm_allocation_per_image": "5 Manual;5 Correct-Semi;5 Wrong-Semi;5 unexposed",
            "total_worker_actions": 900,
            "workers": 20,
            "manual_per_worker_mean": 15.0,
            "semi_per_worker_mean": 30.0,
            "mean_total_per_worker": 45.0,
            "primary_estimand": "within-image correctness interaction",
            "strength": "largest primary image count within 900 actions",
            "limitation": "k=5 per arm is weak for rare-mode prevalence",
        },
        {
            "design": "B_45_image_three_arm_distribution_priority",
            "images": 45,
            "arm_allocation_per_image": "rotate 7/7/6 across Manual, Correct-Semi, Wrong-Semi; all 20 workers exposed once",
            "total_worker_actions": 900,
            "workers": 20,
            "manual_per_worker_mean": 15.0,
            "semi_per_worker_mean": 30.0,
            "mean_total_per_worker": 45.0,
            "primary_estimand": "within-image correctness interaction plus denser arm-specific distribution",
            "strength": "k=6-7 per arm without repeat exposure",
            "limitation": "smaller primary image count than Design A",
        },
        {
            "design": "C_80_image_three_arm_full_budget",
            "images": 80,
            "arm_allocation_per_image": "5 Manual;5 Correct-Semi;5 Wrong-Semi;5 unexposed",
            "total_worker_actions": 1200,
            "workers": 20,
            "manual_per_worker_mean": 20.0,
            "semi_per_worker_mean": 40.0,
            "mean_total_per_worker": 60.0,
            "primary_estimand": "within-image correctness interaction",
            "strength": "largest n within stated per-worker Manual/Semi limits",
            "limitation": "higher cost; still only k=5 per arm",
        },
        {
            "design": "D_100_image_two_arm_natural_moderator",
            "images": 100,
            "arm_allocation_per_image": "5 Manual;5 Natural-Semi;10 unexposed",
            "total_worker_actions": 1000,
            "workers": 20,
            "manual_per_worker_mean": 25.0,
            "semi_per_worker_mean": 25.0,
            "mean_total_per_worker": 50.0,
            "primary_estimand": "Semi-Manual effect moderated by independently audited natural proposal quality",
            "strength": "large image count and ecological natural proposals",
            "limitation": "proposal correctness is not randomized; weaker causal claim",
        },
    ]
    design_frame = pd.DataFrame(designs)
    design_frame["formal_t1_eligible"] = False
    design_frame["assignment_manifest_materialized"] = False
    design_frame["status"] = "exploratory_alternative_study_not_frozen_t1"
    v1.write_csv(design_frame, OUT / "DESIGN_OPTIONS_RESOURCE_ACCOUNTING.csv")

    validation_path = OUT / "VALIDATION.json"
    validation = json.loads(validation_path.read_text(encoding="utf-8"))
    measured = pd.read_csv(OUT / "MEASURED_CANDIDATE_COUNTS.csv", encoding="utf-8-sig")
    hit = measured[
        (measured["stage"] == "C1")
        & (measured["lane"] == "analysis_eligible_and_in_scope")
        & (measured["definition"] == "micro_same_topology_measured_negative_metric_change")
    ]
    validation.update({
        "analysis_version": "strict_observed_fields_v3_feasible_designs_protocol_guard",
        "c1_formal_micro_candidate_rows": int(hit.iloc[0]["row_count"]) if len(hit) else 0,
        "design_options_require_no_repeat_image_exposure": True,
        "design_assignment_manifest_materialized": False,
        "design_feasibility_status": "resource_arithmetic_only",
        "invalid_k10_per_arm_designs_removed": True,
        "formal_t1_contract_unchanged": True,
        "formal_t1_design": "Manual/Semi x ordinary/stress_assist; 2 Manual + 2 Semi per image; image-level paired estimand",
        "design_options_status": "exploratory_alternative_study_not_frozen_t1",
    })
    validation_path.write_text(
        json.dumps(validation, ensure_ascii=False, indent=2), encoding="utf-8", newline="\n",
    )


if __name__ == "__main__":
    main()
