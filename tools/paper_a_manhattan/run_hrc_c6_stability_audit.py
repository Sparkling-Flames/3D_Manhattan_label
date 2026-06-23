"""Materialize a read-only HRC C6 stability audit."""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Any, Mapping, Sequence

from tools.paper_a_manhattan.run_manhattan_hypothesis_ranking_core import build_payload


SCHEMA_VERSION = "hrc_c6_stability_audit_v1"
ROOT = Path("analysis_results/paper_a_manhattan")
DEFAULT_OUT_DIR = ROOT / "hypothesis_ranking_core/c6_stability_audit"
BUCKETS = (
    "best_manhattan_feasible",
    "best_height_consistent",
    "best_short_wall_preserving",
    "best_low_movement",
    "best_hohonet_consistent",
    "best_balanced",
)


def _metric(value: Any) -> float:
    return float(value) if isinstance(value, (int, float)) else math.inf


def _evidence_key(evaluation: Mapping[str, Any]) -> tuple[Any, ...]:
    evidence = evaluation.get("evidence_consistency", {})
    deltas = [
        _metric(evidence.get(name))
        for name in (
            "candidate_corner_column_delta",
            "hohonet_floor_boundary_rmse_delta",
            "hohonet_ceiling_boundary_rmse_delta",
            "seam_consistency_delta",
        )
    ]
    finite = [value for value in deltas if math.isfinite(value)]
    return (
        evidence.get("evidence_status") != "available",
        len(evidence.get("visual_conflict_flags") or []),
        sum(value > 0 for value in finite),
        sum(max(0.0, value) for value in finite),
        *deltas,
    )


def _driver(bucket: str) -> str:
    return {
        "best_manhattan_feasible": "mixed",
        "best_balanced": "mixed",
        "best_height_consistent": "height_consistency",
        "best_short_wall_preserving": "layout_plausibility",
        "best_low_movement": "movement_cost",
        "best_hohonet_consistent": "c4_evidence",
    }[bucket]


def _bucket_summary(core: Mapping[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    evaluations = core["constrained_evaluations"]
    for name in BUCKETS:
        bucket = core["portfolio_ranking"][name]
        candidate = bucket.get("candidate")
        if not candidate:
            out[name] = {
                "candidate_id": None,
                "reason": bucket.get("reason"),
                "selection_driver": _driver(name),
            }
            continue
        candidate_id = candidate["candidate_id"]
        evaluation = evaluations[candidate_id]
        evidence = evaluation.get("evidence_consistency", {})
        manhattan = evaluation.get("manhattan_feasibility", {})
        plane = evaluation.get("plane_proxy_metrics", {})
        out[name] = {
            "candidate_id": candidate_id,
            "decision_class": candidate.get("decision_class"),
            "hard_gate_passed": candidate.get("hard_gate_passed"),
            "action_family": candidate.get("action_family"),
            "selection_status": bucket.get("selection_status"),
            "accepted": bucket.get("accepted"),
            "downstream_recommendation": bucket.get("downstream_recommendation"),
            "recommended_review_candidate": candidate.get("recommended_review_candidate"),
            "selection_driver": _driver(name),
            "c2_status": {
                "direction_family_fit_status": manhattan.get("direction_family_fit_status"),
                "parallel_family_residual_status": (
                    manhattan.get("parallel_family_residual", {}) or {}
                ).get("status"),
            },
            "c5_status": plane.get("plane_proxy_status") or plane.get("status"),
            "c4_status": evidence.get("evidence_status"),
            "c4_visual_conflict_flags": list(evidence.get("visual_conflict_flags") or []),
        }
    return out


def _task3741(core: Mapping[str, Any]) -> dict[str, Any]:
    evaluations = core["constrained_evaluations"]
    c17 = evaluations["m1528_candidate_0017"]
    c19 = evaluations["m1528_candidate_0019"]
    c4_prefers_0019 = _evidence_key(c19) < _evidence_key(c17)
    bucket_ids = {
        name: summary.get("candidate_id")
        for name, summary in _bucket_summary(core).items()
    }
    return {
        "case_name": "task218_ann3741",
        "audit_mode": "active_hrc_bucket_audit",
        "bucket_summary": _bucket_summary(core),
        "selection_regression": {
            "best_manhattan_feasible_is_0017": bucket_ids["best_manhattan_feasible"] == "m1528_candidate_0017",
            "best_balanced_is_0017": bucket_ids["best_balanced"] == "m1528_candidate_0017",
            "best_height_consistent_is_0017": bucket_ids["best_height_consistent"] == "m1528_candidate_0017",
            "candidate_0019_selected_in_primary_buckets": "m1528_candidate_0019"
            in {
                bucket_ids["best_manhattan_feasible"],
                bucket_ids["best_balanced"],
                bucket_ids["best_height_consistent"],
            },
        },
        "manual_conclusion_alignment": {
            "manual_reference": "0017 narrowly passed selection-drift audit over 0019 but is not a final accepted fix",
            "selection_matches_manual_reference": bucket_ids["best_manhattan_feasible"] == "m1528_candidate_0017",
        },
        "c4_evidence_layer_check": {
            "candidate_0019_evidence_key_better_than_0017": c4_prefers_0019,
            "c4_conflict_with_manual_reference": c4_prefers_0019,
        },
        "recommendation_semantics": {
            "any_recommended_review_candidate": any(
                row.get("recommended_review_candidate") for row in core["candidate_set"]
            ),
            "overall_recommended_review_candidate_available": core["overall_verdict"][
                "recommended_review_candidate_available"
            ],
            "explanation_risk": "explained_by_overall_audit_blocked"
            if not core["overall_verdict"]["recommended_review_candidate_available"]
            else "unblocked_recommendation_risk",
        },
    }


def _projection_case(case: str) -> dict[str, Any]:
    path = ROOT / f"local_3d_projection/{case}/projection_metrics.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    original = next(row for row in payload["variants"] if row["name"] == "original")
    metrics = original["metrics"]
    dense = metrics.get("dense_pairs", {}).get("pairs", [])
    heights = metrics.get("heights", {}).get("pairs", [])
    return {
        "case_name": case,
        "audit_mode": "regression_evidence_only",
        "active_hrc_runner_status": "not_available_in_active_hrc_runner",
        "active_hrc_reason": "no active HRC candidate set for this case",
        "source_artifact": path.as_posix(),
        "dense_but_distinct_pairs": [
            [row.get("pair_i"), row.get("pair_j")]
            for row in dense
            if row.get("classification") == "dense_but_distinct_3d_corner"
        ],
        "height_outlier_pairs": [
            row.get("effective_pair_index")
            for row in heights
            if row.get("suspicious_low_height") or row.get("suspicious_high_height")
        ],
        "recommendation_semantics": {
            "accepted": False,
            "downstream_recommendation": False,
        },
        "bucket_summary": {
            name: {
                "candidate_id": None,
                "reason": "regression_evidence_only_no_active_hrc_candidate_set",
                "selection_driver": _driver(name),
            }
            for name in BUCKETS
        },
    }


def _task533() -> dict[str, Any]:
    report = ROOT / (
        "single_image_manual_test/task533_gt75/m1518_3_candidate_semantics/"
        "candidate_b_annotation_3425_m1518_3_candidate_semantics_report.md"
    )
    text = report.read_text(encoding="utf-8")
    return {
        "case_name": "gt75_task533",
        "audit_mode": "verified_order_evidence_only",
        "active_hrc_runner_status": "not_available_in_active_hrc_runner",
        "active_hrc_reason": "no active HRC candidate set for this case",
        "source_artifact": report.as_posix(),
        "verified_order_evidence_present": "order_verified_by_expert" in text,
        "duplicate_default_status_present": "compatibility_failure_duplicate" in text,
        "pair_merge_or_duplicate_recommendation_by_active_hrc": None,
        "pair_merge_or_duplicate_recommendation_reason": "no active HRC candidate set for this case",
        "recommendation_semantics": {
            "accepted": False,
            "downstream_recommendation": False,
        },
    }


def _ordinary_compatible() -> dict[str, Any]:
    fixture = Path("tests/fixtures/paper_a_manhattan/single_image_assist_pack_v1.json")
    payload = json.loads(fixture.read_text(encoding="utf-8"))
    return {
        "case_name": "ordinary_raw_keypoints_compatible_fixture",
        "audit_mode": "fixture_evidence_only",
        "active_hrc_runner_status": "not_available_in_active_hrc_runner",
        "active_hrc_reason": "no active HRC candidate set for this case",
        "source_artifact": fixture.as_posix(),
        "fixture_present": "raw_keypoints_compatible" in payload,
        "meaningless_candidate_preference_by_active_hrc": None,
        "meaningless_candidate_preference_reason": "no active HRC candidate set for this case",
        "recommendation_semantics": {
            "accepted": False,
            "downstream_recommendation": False,
        },
    }


def build_audit_payload() -> dict[str, Any]:
    core = build_payload()
    task3741 = _task3741(core)
    c4_overstrong = task3741["c4_evidence_layer_check"]["c4_conflict_with_manual_reference"]
    task2369 = _projection_case("task218_ann2369")
    task2389 = _projection_case("task238_ann2389")
    cases = {
        "task218_ann3741": task3741,
        "task218_ann2369": {
            **task2369,
            "dense_but_distinct_evidence_present": bool(task2369["dense_but_distinct_pairs"]),
            "dense_but_distinct_not_collapsed_by_active_hrc": None,
            "dense_but_distinct_not_collapsed_reason": "no active HRC candidate set for this case",
        },
        "task238_ann2389": {
            **task2389,
            "height_outlier_evidence_present": bool(task2389["height_outlier_pairs"]),
            "height_dominant_not_suppressed_by_active_hrc": None,
            "height_dominant_not_suppressed_reason": "no active HRC candidate set for this case",
        },
        "gt75_task533": _task533(),
        "ordinary_compatible": _ordinary_compatible(),
    }
    active_cases = ["task218_ann3741"]
    evidence_only_cases = [
        "task218_ann2369",
        "task238_ann2389",
        "gt75_task533",
        "ordinary_compatible",
    ]
    return {
        "schema_version": SCHEMA_VERSION,
        "audit_name": "HRC C6 stability audit",
        "active_hrc_bucket_audit_cases": active_cases,
        "evidence_only_cases": evidence_only_cases,
        "full_multi_case_bucket_audit_complete": False,
        "conclusion_basis": "only task218_ann3741 has active HRC bucket audit; other cases are evidence-only",
        "active_runner_changed": False,
        "legacy_m1528_only_active_source": core["candidate_source_metadata"]["source_id"] == "legacy_m1528",
        "accepted": False,
        "downstream_recommendation": False,
        "bucket_names": list(BUCKETS),
        "cases": cases,
        "c4_layer_strength_audit": {
            "best_manhattan_feasible_current_order": "(*evidence_key, *manhattan_key)",
            "best_balanced_current_order": "(*evidence_key, *build_hypothesis_ranking_key)",
            "c4_overstrong_risk": c4_overstrong,
            "ranking_change_recommended_now": False,
        },
        "audit_conclusion": "B: C6 still audit-blocked; only task218_ann3741 has active HRC bucket audit",
        "next_allowed_step": "C6.3c active multi-case bucket audit or C2/C5 diagnostics hardening; C3 shadow expansion remains blocked",
    }


def render_markdown(payload: Mapping[str, Any]) -> str:
    lines = [
        "# HRC C6 Stability Audit",
        "",
        f"- Schema: `{payload['schema_version']}`",
        f"- Conclusion: `{payload['audit_conclusion']}`",
        f"- Conclusion basis: `{payload['conclusion_basis']}`",
        f"- Full multi-case bucket audit complete: `{payload['full_multi_case_bucket_audit_complete']}`",
        f"- C4 overstrong risk: `{payload['c4_layer_strength_audit']['c4_overstrong_risk']}`",
        f"- Accepted: `{payload['accepted']}`",
        f"- Downstream recommendation: `{payload['downstream_recommendation']}`",
        "",
        "## Bucket selections: task218_ann3741",
        "",
    ]
    for name, summary in payload["cases"]["task218_ann3741"]["bucket_summary"].items():
        lines.append(
            f"- `{name}`: `{summary.get('candidate_id')}` / `{summary.get('selection_driver')}` / accepted=`{summary.get('accepted')}`"
        )
    lines.extend(["", "## Evidence-only cases", ""])
    for name in ("task218_ann2369", "task238_ann2389", "gt75_task533", "ordinary_compatible"):
        case = payload["cases"][name]
        lines.append(f"- `{name}`: `{case['audit_mode']}`; accepted=false; downstream=false")
    lines.append("")
    return "\n".join(lines)


def run(out_dir: Path = DEFAULT_OUT_DIR) -> dict[str, Path]:
    payload = build_audit_payload()
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = out_dir / "hrc_c6_stability_audit.json"
    markdown_path = out_dir / "hrc_c6_stability_audit.md"
    with json_path.open("w", encoding="utf-8", newline="\n") as handle:
        handle.write(json.dumps(payload, ensure_ascii=False, indent=2) + "\n")
    with markdown_path.open("w", encoding="utf-8", newline="\n") as handle:
        handle.write(render_markdown(payload))
    return {"json": json_path, "markdown": markdown_path}


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    args = parser.parse_args(argv)
    print(run(args.out_dir)["json"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
