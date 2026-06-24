"""Audit HRC scoring-layer compliance without changing evaluator or ranking logic."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any, Mapping, Sequence

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tools.paper_a_manhattan.run_manhattan_hypothesis_ranking_core import build_payload


SCHEMA_VERSION = "hrc_scoring_compliance_audit_v1"
ROOT = Path("analysis_results/paper_a_manhattan/hypothesis_ranking_core")
DEFAULT_OUT_DIR = ROOT / "scoring_compliance_audit"
CONTRACT = Path("docs/paper_a_manhattan/HRC_SCORING_LAYER_CONTRACT_v1.md")
SCORING_PRINCIPLES = Path("docs/paper_a_manhattan/评分如何制定.md")
EVALUATOR = Path("tools/paper_a_manhattan/manhattan_constrained_hypothesis_evaluator.py")
PORTFOLIO = Path("tools/paper_a_manhattan/manhattan_hypothesis_portfolio.py")
RUNNER = Path("tools/paper_a_manhattan/run_manhattan_hypothesis_ranking_core.py")
MATERIALIZATION = (
    ROOT / "evidence_input_materialization/hrc_evidence_input_materialization.json"
)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _artifact(path: Path) -> dict[str, str]:
    return {"path": path.as_posix(), "sha256": _sha256(path)}


LAYER_MAPPING = {
    "L0": [
        "feasibility.topology_valid",
        "feasibility.projection_valid",
        "feasibility.no_self_intersection",
        "feasibility.no_pair_fold",
        "feasibility.no_unapproved_order_mutation",
        "feasibility.protected_pairs_not_moved",
        "feasibility.keep_distinct_pairs_not_collapsed",
        "feasibility.authorized_mutations_only",
        "feasibility.wrap_or_seam_not_broken",
        "feasibility.hard_gate_passed",
    ],
    "L1": [
        "manhattan_feasibility.direction_family_fit",
        "manhattan_feasibility.parallel_family_residual",
        "manhattan_feasibility.turn_residual_max",
        "manhattan_feasibility.turn_residual_median",
        "manhattan_feasibility.unresolved_edge_count",
        "manhattan_feasibility.local_window_residual",
        "manhattan_feasibility.floor_ceiling_column_consistency",
        "manhattan_feasibility.wall_residual_max",
        "manhattan_feasibility.wall_residual_median",
    ],
    "L2": [
        "evidence_consistency.evidence_status",
        "evidence_consistency.visual_conflict_flags",
        "evidence_consistency.hohonet_wallwall_peak_alignment",
        "evidence_consistency.hohonet_floor_boundary_rmse_delta",
        "evidence_consistency.hohonet_ceiling_boundary_rmse_delta",
        "evidence_consistency.candidate_corner_column_delta",
        "evidence_consistency.seam_consistency_delta",
    ],
    "L3": [
        "plane_proxy_metrics",
        "height_consistency.dominant_height_h_star",
        "height_consistency.height_cluster_mad",
        "height_consistency.max_height_residual",
        "height_consistency.height_outlier_l1",
        "height_consistency.height_outlier_pairs",
    ],
    "L4": [
        "layout_plausibility.existing_short_wall_preserved",
        "layout_plausibility.short_wall_collapsed",
        "layout_plausibility.new_short_wall_created",
        "layout_plausibility.keep_distinct_margin",
        "case_contract.keep_distinct_pairs",
        "manual_evidence_sidecar",
    ],
    "L5": [
        "movement_edit_cost.movement_l1_normalized",
        "movement_edit_cost.changed_pair_count",
        "movement_edit_cost.manual_adjustment_cost_proxy",
        "legacy_diagnostics.local_score_total",
    ],
}

RANKING_KEY_MAPPING = [
    {"index": 0, "field": "not hard_gate_passed", "layer": "L0"},
    {"index": 1, "field": "direction_family_missing", "layer": "L1"},
    {"index": 2, "field": "direction_family_max_deg", "layer": "L1"},
    {"index": 3, "field": "direction_family_median_deg", "layer": "L1"},
    {"index": 4, "field": "parallel_family_missing", "layer": "L1"},
    {"index": 5, "field": "parallel_family_max_deg", "layer": "L1"},
    {"index": 6, "field": "parallel_family_median_deg", "layer": "L1"},
    {"index": 7, "field": "unresolved_edge_count", "layer": "L1"},
    {"index": 8, "field": "wall_residual_max", "layer": "L1"},
    {"index": 9, "field": "wall_residual_median", "layer": "L1"},
    {"index": 10, "field": "height_outlier_l1", "layer": "L3"},
    {"index": 11, "field": "evidence_regression", "layer": "L2"},
    {"index": 12, "field": "short_wall_collapsed_count", "layer": "L4"},
    {"index": 13, "field": "new_short_wall_count", "layer": "L4"},
    {"index": 14, "field": "short_wall_deficit_delta", "layer": "L4"},
    {"index": 15, "field": "movement_l1_normalized", "layer": "L5"},
    {"index": 16, "field": "manual_adjustment_cost_proxy", "layer": "L5"},
]


def build_audit_payload() -> dict[str, Any]:
    core = build_payload()
    materialized = json.loads(MATERIALIZATION.read_text(encoding="utf-8"))
    suppressed = core["portfolio_ranking"]["suppressed_candidates"]
    hard_failures = [
        row for row in core["candidate_set"] if not row["hard_gate_passed"]
    ]
    authorization_safe = (
        core["overall_verdict"]["recommended_review_candidate_available"] is False
        and all(
            bucket.get("accepted") is False
            and bucket.get("downstream_recommendation") is False
            for name, bucket in core["portfolio_ranking"].items()
            if name not in {"diagnostic_only_candidates", "suppressed_candidates"}
        )
    )
    baseline_only = all(
        case["c4_lite_diagnostics"]["baseline_to_baseline_materialization"]
        and not case["c4_lite_diagnostics"]["candidate_preference_claim"]
        and not case["rankable_by_current_HRC_input_summary"]["rankable"]
        for case in materialized["cases"].values()
    )

    violations = [
        {
            "code": "L1_DIRECTION_PRECEDES_MULTI_METRIC_STRUCTURE",
            "severity": "high",
            "location": "build_hypothesis_ranking_key indices 2-7",
            "finding": "direction max/median and parallel residual precede unresolved_edge_count; turn_residual and local_window_residual are absent from the global key",
        },
        {
            "code": "L2_AFTER_L3_IN_GLOBAL_KEY",
            "severity": "high",
            "location": "build_hypothesis_ranking_key indices 10-11",
            "finding": "height_outlier_l1 (L3) is compared before evidence_regression (L2)",
        },
        {
            "code": "C5_MIXED_INTO_MANHATTAN_BUCKET_KEY",
            "severity": "medium",
            "location": "manhattan_hypothesis_portfolio.manhattan_key",
            "finding": "C5 plane parallel/orthogonal proxies are embedded in the best_manhattan_feasible key before unresolved/wall residual metrics",
        },
        {
            "code": "L2_BASELINE_ONLY_CANNOT_PREFER_CANDIDATE",
            "severity": "blocking",
            "location": "C6.5a.2 evidence materialization",
            "finding": "2369/2389 C4 deltas are baseline-to-baseline zero diagnostics with no candidate projection variants; they cannot support candidate preference",
        },
        {
            "code": "L4_MANUAL_EVIDENCE_INCOMPLETE",
            "severity": "blocking",
            "location": "source readiness/manual sidecar",
            "finding": "2369 keep-distinct is projection-derived, while explicit column identity remains manual; 2389 lacks explicit column identity and keep-distinct contract",
        },
    ]
    return {
        "schema_version": SCHEMA_VERSION,
        "source_artifacts": [
            _artifact(CONTRACT),
            _artifact(SCORING_PRINCIPLES),
            _artifact(EVALUATOR),
            _artifact(PORTFOLIO),
            _artifact(RUNNER),
            _artifact(MATERIALIZATION),
        ],
        "layer_mapping": LAYER_MAPPING,
        "ranking_key_mapping": RANKING_KEY_MAPPING,
        "contract_compliance_status": "partial",
        "layer_audits": {
            "L0": {
                "status": "complete",
                "hard_gate_is_first_ranking_key_item": True,
                "hard_gate_failures_in_suppressed_candidates": len(suppressed)
                == len(hard_failures),
                "residual_height_or_movement_can_override_hard_gate": False,
            },
            "L1": {
                "status": "partial",
                "multi_metric_fields_exist": True,
                "single_direction_metric_can_dominate_current_global_key": True,
                "turn_and_local_residual_present_in_global_key": False,
            },
            "L2": {
                "status": "partial",
                "accepted_requires_runner_authorization": True,
                "current_accepted_gate_safe": authorization_safe,
                "baseline_only_diagnostics": baseline_only,
                "candidate_preference_authorized": False,
            },
            "L3": {
                "status": "partial",
                "c5_is_geometry_proxy_only": True,
                "c5_is_c4_evidence": False,
                "height_compared_after_l2_in_global_key": False,
            },
            "L4": {
                "status": "partial",
                "short_wall_and_keep_distinct_fields_exist": True,
                "manual_sidecar_complete": False,
            },
            "L5": {
                "status": "complete",
                "movement_is_final_active_tie_break": True,
                "legacy_score_in_active_ranking_key": False,
                "legacy_score_role": "diagnostic_only",
            },
        },
        "layer_order_violations": violations,
        "accepted_gate_audit": {
            "overall_recommended_review_candidate_available": core[
                "overall_verdict"
            ]["recommended_review_candidate_available"],
            "all_portfolio_buckets_accepted_false": authorization_safe,
            "downstream_recommendation_available": False,
            "status": "safe_but_audit_blocked",
        },
        "candidate_preference_blockers": [
            "2369/2389 C4 evidence is baseline-to-baseline diagnostic only",
            "candidate projection variant count is zero",
            "rankable_by_current_HRC is false",
            "manual explicit column identity is pending",
            "supporting artifacts are not manual verdicts",
        ],
        "audit_only": True,
        "evaluator_changed": False,
        "ranking_key_changed": False,
        "portfolio_changed": False,
        "active_runner_changed": False,
        "c3_changed": False,
        "accepted": False,
        "downstream_recommendation": False,
        "annotation_writeback": False,
        "c6_status": "audit_blocked",
        "c6_5b_authorized": False,
        "c6_5a_4_authorized": False,
        "next_allowed_step": "remain blocked; resolve scoring compliance findings before C6.5a.4 evaluator hardening spec",
        "status_boundaries": {
            "c3_shadow_expansion": "blocked",
            "c7_optimizer": "blocked",
            "c9_learning": "blocked",
            "c10_ranker": "blocked",
        },
    }


def render_markdown(payload: Mapping[str, Any]) -> str:
    lines = [
        "# HRC C6.5a.3 Scoring Compliance Audit",
        "",
        f"- Compliance: `{payload['contract_compliance_status']}`",
        f"- C6 status: `{payload['c6_status']}`",
        f"- C6.5b authorized: `{payload['c6_5b_authorized']}`",
        f"- Next allowed step: `{payload['next_allowed_step']}`",
        "",
        "## Layer findings",
        "",
    ]
    for layer, audit in payload["layer_audits"].items():
        lines.append(f"- `{layer}`: `{audit['status']}`")
    lines.extend(["", "## Violations", ""])
    for row in payload["layer_order_violations"]:
        lines.append(f"- `{row['code']}` ({row['severity']}): {row['finding']}")
    lines.append("")
    return "\n".join(lines)


def run(out_dir: Path = DEFAULT_OUT_DIR) -> dict[str, Path]:
    payload = build_audit_payload()
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = out_dir / "hrc_scoring_compliance_audit.json"
    md_path = out_dir / "hrc_scoring_compliance_audit.md"
    json_path.write_bytes(
        (json.dumps(payload, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    )
    md_path.write_bytes(render_markdown(payload).encode("utf-8"))
    return {"json": json_path, "markdown": md_path}


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    args = parser.parse_args(argv)
    print(run(args.out_dir)["json"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
