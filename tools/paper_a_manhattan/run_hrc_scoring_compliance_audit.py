"""Audit current HRC L0-L5 scoring compliance without changing selection."""

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

from tools.paper_a_manhattan.manhattan_constrained_hypothesis_evaluator import (
    build_hypothesis_ranking_key,
    build_hypothesis_ranking_layers,
)
from tools.paper_a_manhattan.run_manhattan_hypothesis_ranking_core import build_payload


SCHEMA_VERSION = "hrc_scoring_compliance_audit_v1"
ROOT = Path("analysis_results/paper_a_manhattan/hypothesis_ranking_core")
DEFAULT_OUT_DIR = ROOT / "scoring_compliance_audit"
MATERIALIZATION = (
    ROOT / "evidence_input_materialization/hrc_evidence_input_materialization.json"
)
GT_CORRECTION_AUDIT = Path(
    "analysis_results/paper_a_manhattan/gt_correction_audit/"
    "task238_ann2389_4543gt/hrc_gt_correction_audit_4543gt.json"
)
CANDIDATE_DRY_RUN = (
    ROOT
    / "c6_5a_6_candidate_dry_run/task238_ann2389_4543gt/"
    "hrc_c6_5a_6_candidate_dry_run.json"
)
MANUAL_SELECTION_LEDGER = (
    ROOT
    / "c6_5a_6_2_manual_selection_ledger/task238_ann2389_4543gt/"
    "hrc_c6_5a_6_2_manual_selection_ledger.json"
)
C6_5A_7_DIR = ROOT / "c6_5a_7_blocker_closure"
SIDECAR_2369_EXPLICIT = (
    C6_5A_7_DIR
    / "manual_sidecar_explicit_column_identity_task218_ann2369.json"
)
SIDECAR_2369_KEEP = (
    C6_5A_7_DIR
    / "manual_sidecar_keep_distinct_contract_task218_ann2369.json"
)
SOURCE_PATHS = (
    Path("docs/paper_a_manhattan/HRC_SCORING_LAYER_CONTRACT_v1.md"),
    Path("docs/paper_a_manhattan/评分如何制定.md"),
    Path("docs/paper_a_manhattan/HRC_C6_5A_4_SCORING_EVALUATOR_HARDENING_SPEC_v1.md"),
    Path("tools/paper_a_manhattan/manhattan_constrained_hypothesis_evaluator.py"),
    Path("tools/paper_a_manhattan/manhattan_hypothesis_portfolio.py"),
    Path("tools/paper_a_manhattan/run_manhattan_hypothesis_ranking_core.py"),
    MATERIALIZATION,
    GT_CORRECTION_AUDIT,
    CANDIDATE_DRY_RUN,
)

LAYER_MAPPING = {
    "L0": ["feasibility.hard_gate_passed", "feasibility hard constraints"],
    "L1": [
        "unresolved_edge_count",
        "turn_residual",
        "local_window_residual",
        "floor_ceiling_column_consistency",
        "direction_family_fit",
        "parallel_family_residual",
        "wall_residual",
    ],
    "L2": [
        "evidence_available_gate",
        "evidence_conflict_gate",
        "evidence_delta_key",
    ],
    "L3": ["plane_proxy_metrics", "height_consistency"],
    "L4": ["manual_evidence", "short_wall", "layout_plausibility"],
    "L5": ["movement_edit_cost", "legacy diagnostics excluded"],
}
RANKING_FIELDS = {
    "L0": ["not hard_gate_passed"],
    "L1": [
        "unresolved_edge_count",
        "turn_residual_unavailable",
        "turn_residual_max",
        "turn_residual_median",
        "local_window_residual_unavailable",
        "local_window_residual",
        "floor_ceiling_column_consistency_unavailable",
        "floor_ceiling_column_consistency",
        "direction_family_missing",
        "parallel_family_missing",
        "direction_family_max_deg",
        "direction_family_median_deg",
        "parallel_family_max_deg",
        "parallel_family_median_deg",
        "wall_residual_max",
        "wall_residual_median",
    ],
    "L2": [
        "evidence_available_gate",
        "evidence_conflict_gate",
        "evidence_conflict_count",
        "positive_delta_count",
        "positive_delta_sum",
        "corner_column_delta",
        "floor_boundary_delta",
        "ceiling_boundary_delta",
        "seam_delta",
    ],
    "L3": [
        "plane_parallel_unavailable",
        "plane_parallel_max",
        "plane_parallel_median",
        "plane_orthogonal_unavailable",
        "plane_orthogonal_residual",
        "floor_plane_unavailable",
        "floor_plane_wall_residual_max",
        "height_outlier_l1",
        "max_height_residual",
        "height_cluster_mad",
    ],
    "L4": [
        "manual_evidence_blocked",
        "short_wall_collapsed_count",
        "new_short_wall_count",
        "short_wall_deficit_delta",
    ],
    "L5": [
        "movement_l1_normalized",
        "changed_pair_count",
        "changed_endpoint_count",
        "manual_adjustment_cost_proxy",
    ],
}


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _ranking_key_mapping() -> list[dict[str, Any]]:
    rows = []
    for layer in ("L0", "L1", "L2", "L3", "L4", "L5"):
        for field in RANKING_FIELDS[layer]:
            rows.append({"index": len(rows), "field": field, "layer": layer})
    return rows


def build_audit_payload() -> dict[str, Any]:
    core = build_payload()
    evaluation = next(iter(core["constrained_evaluations"].values()))
    layers = build_hypothesis_ranking_layers(evaluation)
    key = build_hypothesis_ranking_key(evaluation)
    materialized = json.loads(MATERIALIZATION.read_text(encoding="utf-8"))
    correction = json.loads(GT_CORRECTION_AUDIT.read_text(encoding="utf-8"))
    dry_run = json.loads(CANDIDATE_DRY_RUN.read_text(encoding="utf-8"))
    selection = json.loads(MANUAL_SELECTION_LEDGER.read_text(encoding="utf-8"))
    baseline_only = all(
        materialized["cases"][name]["c4_lite_diagnostics"][
            "baseline_to_baseline_materialization"
        ]
        and not materialized["cases"][name]["c4_lite_diagnostics"][
            "candidate_preference_claim"
        ]
        and not materialized["cases"][name][
            "rankable_by_current_HRC_input_summary"
        ]["rankable"]
        for name in ("task218_ann2369", "task238_ann2389")
    )
    authorization_safe = (
        core["overall_verdict"]["recommended_review_candidate_available"] is False
        and all(
            bucket.get("accepted") is False
            and bucket.get("downstream_recommendation") is False
            for name, bucket in core["portfolio_ranking"].items()
            if name not in {"diagnostic_only_candidates", "suppressed_candidates"}
        )
    )
    blockers = [
        {
            "code": "L2_BASELINE_ONLY_CANNOT_PREFER_CANDIDATE",
            "severity": "blocking",
            "finding": (
                "candidate-specific C4 evidence is absent for 2369, deprecated "
                "old 2389, and selected corrected-GT candidate 0003"
            ),
        },
        {
            "code": "L4_MANUAL_EVIDENCE_INCOMPLETE",
            "severity": "blocking",
            "finding": (
                "2369 explicit-column identity is available with pair2 exception; "
                "keep-distinct 4-5 is available, but partial evidence cannot authorize preference"
            ),
        },
    ]
    expected_selection = {
        "best_manhattan_feasible": "m1528_candidate_0017",
        "best_balanced": "m1528_candidate_0017",
        "best_height_consistent": "m1528_candidate_0017",
        "best_short_wall_preserving": "m1528_candidate_0001",
        "best_low_movement": "m1528_candidate_0070",
    }
    actual_selection = {
        name: core["portfolio_ranking"][name]["candidate"]["candidate_id"]
        for name in expected_selection
    }
    return {
        "schema_version": SCHEMA_VERSION,
        "audit_phase": "C6.5a.4d",
        "source_artifacts": [
            {"path": path.as_posix(), "sha256": _sha256(path)} for path in SOURCE_PATHS
        ],
        "layer_mapping": LAYER_MAPPING,
        "ranking_key_mapping": _ranking_key_mapping(),
        "ranking_layer_lengths": {name: len(value) for name, value in layers.items()},
        "ranking_key_length": len(key),
        "contract_compliance_status": "partial",
        "layer_audits": {
            "L0": {
                "status": "complete",
                "hard_gate_is_first_ranking_key_item": True,
                "residual_height_or_movement_can_override_hard_gate": False,
            },
            "L1": {
                "status": "complete",
                "single_direction_metric_can_dominate_current_global_key": False,
                "turn_and_local_residual_present_in_global_key": True,
            },
            "L2": {
                "status": "partial",
                "implementation_status": "complete",
                "data_status": "candidate_specific_evidence_incomplete",
                "baseline_only_diagnostics": baseline_only,
                "candidate_preference_authorized": False,
            },
            "L3": {
                "status": "complete",
                "c5_is_geometry_proxy_only": True,
                "c5_is_c4_evidence": False,
                "height_compared_after_l2_in_global_key": True,
                "c5_removed_from_best_manhattan_feasible_key": True,
            },
            "L4": {
                "status": "partial",
                "implementation_status": "manual_gate_supported",
                "data_status": "manual_sidecars_incomplete",
            },
            "L5": {
                "status": "complete",
                "movement_is_final_active_tie_break": True,
                "legacy_score_in_active_ranking_key": False,
                "legacy_score_role": "diagnostic_only",
            },
        },
        "layer_order_violations": [],
        "resolved_layer_order_violations": [
            "L1_DIRECTION_PRECEDES_MULTI_METRIC_STRUCTURE",
            "L2_AFTER_L3_IN_GLOBAL_KEY",
            "C5_MIXED_INTO_MANHATTAN_BUCKET_KEY",
        ],
        "compliance_blockers": blockers,
        "accepted_gate_audit": {
            "overall_recommended_review_candidate_available": False,
            "all_portfolio_buckets_accepted_false": authorization_safe,
            "downstream_recommendation_available": False,
            "status": "safe_but_audit_blocked",
        },
        "selection_regression": {
            "expected": expected_selection,
            "actual": actual_selection,
            "selection_drift": actual_selection != expected_selection,
            "accepted": False,
            "downstream_recommendation": False,
        },
        "candidate_preference_blockers": [
            "candidate-specific C4 evidence is absent for 2369, old 2389, and selected 4543gt candidate 0003",
            "2369 pair2 explicit column identity remains unresolved due to occlusion",
            "2369 keep-distinct 4-5 is human-confirmed but does not replace candidate-specific C4",
            "2389 corrected GT explicit column identity is available",
            "2389 corrected GT keep-distinct is not applicable",
            "supporting artifacts are not manual verdicts",
        ],
        "corrected_gt_audit": {
            "materialized": correction["corrected_gt_id"] == "4543gt",
            "path": GT_CORRECTION_AUDIT.as_posix(),
            "sha256": _sha256(GT_CORRECTION_AUDIT),
            "manual_evidence_available": all(
                row["verdict"] == "available"
                for row in correction["manual_sidecars"].values()
            ),
            "explicit_column_identity": "available",
            "keep_distinct_contract": "not_applicable",
            "short_wall_exists": False,
            "four_corner_layout_sufficient": True,
            "endpoint_precision_blocking": False,
            "accepted_final_fix": False,
        },
        "candidate_preference_authorized": {
            "task218_ann2369": False,
            "task238_ann2389": False,
            "task238_ann2389_4543gt": False,
        },
        "corrected_gt_status_summary": {
            "old_case": "task238_ann2389",
            "old_case_role": "deprecated_old_gt_diagnostic_only",
            "old_case_manual_requirements_are_corrected_gt_blockers": False,
            "corrected_case": "task238_ann2389_4543gt",
            "candidate_preference_authorized_old_case": False,
            "candidate_preference_authorized_corrected_case": False,
        },
        "c6_5a_6_candidate_dry_run": {
            "generated": True,
            "path": CANDIDATE_DRY_RUN.as_posix(),
            "sha256": _sha256(CANDIDATE_DRY_RUN),
            "candidate_count": dry_run["candidate_count"],
            "human_comparison_status": "selected_for_review_only",
            "selected_candidate": selection["selected_candidate"],
            "selected_y_step": selection["selected_y_step"],
            "active_ranking_changed": False,
            "candidate_preference_authorized": False,
        },
        "c6_5a_7_blocker_closure_status": {
            "2369_manual_sidecars": {
                "explicit_column_identity": {
                    "path": SIDECAR_2369_EXPLICIT.as_posix(),
                    "sha256": _sha256(SIDECAR_2369_EXPLICIT),
                    "verdict": "available_with_exception",
                },
                "keep_distinct_contract": {
                    "path": SIDECAR_2369_KEEP.as_posix(),
                    "sha256": _sha256(SIDECAR_2369_KEEP),
                    "verdict": "available",
                },
            },
            "supporting_artifacts_are_manual_verdicts": False,
            "candidate_specific_c4_complete": False,
            "c6_5b_authorized": False,
        },
        "audit_only": True,
        "evaluator_changed": True,
        "ranking_key_changed": True,
        "portfolio_changed": True,
        "active_runner_changed": False,
        "c3_changed": False,
        "accepted": False,
        "downstream_recommendation": False,
        "annotation_writeback": False,
        "c6_status": "audit_blocked",
        "c6_5b_authorized": False,
        "c6_5a_4_implementation_completed": True,
        "next_allowed_step": (
            "resolve task218_ann2369 pair2 column identity under occlusion; "
            "candidate-specific C4 evidence remains required; "
            "C6.5b remains blocked"
        ),
        "status_boundaries": {
            "c3_shadow_expansion": "blocked",
            "c7_optimizer": "blocked",
            "c9_learning": "blocked",
            "c10_ranker": "blocked",
        },
    }


def render_markdown(payload: Mapping[str, Any]) -> str:
    lines = [
        "# HRC C6.5a.4d Post-change Scoring Compliance and Selection Audit",
        "",
        f"- Ranking key length: `{payload['ranking_key_length']}`",
        f"- Selection drift: `{str(payload['selection_regression']['selection_drift']).lower()}`",
        f"- Accepted: `{str(payload['accepted']).lower()}`",
        f"- Downstream recommendation: `{str(payload['downstream_recommendation']).lower()}`",
        f"- Compliance: `{payload['contract_compliance_status']}`",
        f"- C6 status: `{payload['c6_status']}`",
        f"- C6.5b authorized: `{str(payload['c6_5b_authorized']).lower()}`",
        f"- Next allowed step: `{payload['next_allowed_step']}`",
        "",
    ]
    for layer, audit in payload["layer_audits"].items():
        lines.append(f"- `{layer}`: `{audit['status']}`")
    lines.extend(
        [
            "",
            "## Blocked boundaries",
            "",
            "- C3 shadow expansion: `blocked`",
            "- C7 optimizer: `blocked`",
            "- C9 learning: `blocked`",
            "- C10 ranker: `blocked`",
            "",
            "## Remaining manual-review boundary",
            "",
            "- 2369 explicit-column identity is available with pair2 exception; keep-distinct 4-5 is available.",
            "- Candidate-specific C4 evidence remains absent for 2369, old 2389, and selected 4543gt candidate 0003.",
            "- 2389 corrected GT has explicit column identity; keep-distinct is not applicable.",
            "- Future 3741 dense-corner / short-wall / pillar judgments remain manual-review-only.",
            "- Projection-derived artifacts may support review but cannot replace the manual verdict.",
            "",
        ]
    )
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
