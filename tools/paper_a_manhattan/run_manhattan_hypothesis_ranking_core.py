"""Run the expert-side Manhattan Constrained Hypothesis Ranking Core."""

from __future__ import annotations

import argparse
import copy
import json
import sys
from pathlib import Path
from typing import Any, Mapping

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tools.paper_a_manhattan.manhattan_hypothesis_portfolio import build_hypothesis_portfolio
from tools.paper_a_manhattan.manhattan_column_evidence import (
    compute_column_evidence,
    inventory_hohonet_source,
)
from tools.paper_a_manhattan.manhattan_constrained_hypothesis_evaluator import (
    build_hypothesis_ranking_key,
    evaluate_hypothesis,
)
from tools.paper_a_manhattan.manhattan_m1528_semantic_action_library import run_action_library
from tools.paper_a_manhattan.run_local_3d_projection_review import build_projection_variant
from tools.paper_a_manhattan.run_m1528_semantic_action_library import (
    DEFAULT_ASSERTION,
    DEFAULT_PROJECTION,
)


SCHEMA_VERSION = "manhattan_constrained_hypothesis_ranking_core_v1"
DEFAULT_OUT_DIR = Path("analysis_results/paper_a_manhattan/hypothesis_ranking_core/task218_ann3741")
AUDIT_BLOCKED_REASON = "C6.1 manual visual sanity check rejected 0019 over 0017"
POST_CHANGE_BLOCKED_REASON = "C6.2 post-change manual visual sanity check pending"


def _core_evaluation(evaluation: Mapping[str, Any]) -> dict[str, Any]:
    return {
        key: value
        for key, value in evaluation.items()
        if key not in {"legacy_score_breakdown", "local_score_total", "legacy_score_role"}
    }


def _candidate_pairs(
    baseline_pairs: list[Mapping[str, Any]], coordinate_changes: list[Mapping[str, Any]]
) -> list[dict[str, Any]]:
    pairs = copy.deepcopy(baseline_pairs)
    lookup = {int(row["effective_pair_index"]): row for row in pairs}
    for change in coordinate_changes:
        row = lookup[int(change["effective_pair_index"])]
        for field, delta in change.get("fields", {}).items():
            endpoint, axis = field.split("_", 1)
            row[endpoint][axis] = float(delta["after"])
    return pairs


def _enrich_legacy_with_column_evidence(
    legacy: dict[str, Any],
    original: Mapping[str, Any],
    projection_config: Mapping[str, Any],
    source: Mapping[str, Any],
) -> None:
    baseline_pairs = list(original["ordered_pairs"])
    for row in legacy["candidate_set"]:
        pairs = _candidate_pairs(baseline_pairs, list(row.get("coordinate_changes", [])))
        candidate_variant = build_projection_variant(
            row["candidate_id"], pairs, **projection_config
        )
        evidence = compute_column_evidence(
            source,
            baseline_pairs,
            pairs,
            coordinate_mode=str(projection_config["coordinate_mode"]),
        )
        candidate_variant["evidence"] = evidence
        evaluation = evaluate_hypothesis(
            original,
            candidate_variant,
            baseline_pairs,
            pairs,
            legacy["case_contract"],
            legacy_score_breakdown=row.get("score_breakdown"),
            legacy_trial_allowed=bool(
                row.get("direct_ls_trial_allowed")
                and row.get("legacy_m15_28_gate", {}).get("checks", {}).get(
                    "allowed_short_wall_band"
                )
            ),
        )
        row["constrained_evaluation"] = evaluation
        row["constrained_hard_gate"] = dict(evaluation["feasibility"])
        row["decision_class"] = evaluation["decision_class"]
        row["hypothesis_ranking_key"] = list(build_hypothesis_ranking_key(evaluation))
    legacy["column_evidence_source_inventory"] = {
        key: value for key, value in source.items() if key != "corners"
    }


def build_core_payload_from_legacy(legacy_payload: Mapping[str, Any]) -> dict[str, Any]:
    rows = list(legacy_payload.get("candidate_set", []))
    if not rows:
        raise ValueError("legacy candidate source returned no candidate_set")
    evaluations = [row["constrained_evaluation"] for row in rows]
    candidate_set: list[dict[str, Any]] = []
    for row, evaluation in zip(rows, evaluations):
        hard_passed = bool(evaluation["feasibility"]["hard_gate_passed"])
        candidate_set.append(
            {
                "candidate_id": row["candidate_id"],
                "action_family": row.get("action_family"),
                "changed_pair_indices": list(row.get("changed_pair_indices", [])),
                "decision_class": evaluation["decision_class"],
                "hard_gate_passed": hard_passed,
                "is_improving_hypothesis": bool(evaluation["is_improving_hypothesis"]),
                "recommended_review_candidate": False,
                "hypothesis_ranking_key": list(row["hypothesis_ranking_key"]),
            }
        )
    portfolio = build_hypothesis_portfolio(candidate_set, evaluations)
    for name, bucket in portfolio.items():
        if name in {"diagnostic_only_candidates", "suppressed_candidates"}:
            for entry in bucket:
                entry["evaluation"] = _core_evaluation(entry["evaluation"])
        elif bucket.get("evaluation"):
            bucket["evaluation"] = _core_evaluation(bucket["evaluation"])
    selected_ids = {
        bucket["candidate"]["candidate_id"]
        for name, bucket in portfolio.items()
        if name not in {"diagnostic_only_candidates", "suppressed_candidates"}
        and bucket.get("candidate")
    }
    for row in candidate_set:
        row["recommended_review_candidate"] = bool(
            row["candidate_id"] in selected_ids and row["is_improving_hypothesis"]
        )
    canonical_candidates = {row["candidate_id"]: row for row in candidate_set}
    for name, bucket in portfolio.items():
        if name in {"diagnostic_only_candidates", "suppressed_candidates"}:
            for entry in bucket:
                candidate_id = entry["candidate"]["candidate_id"]
                entry["candidate"] = dict(canonical_candidates[candidate_id])
        elif bucket.get("candidate"):
            candidate_id = bucket["candidate"]["candidate_id"]
            bucket["candidate"] = dict(canonical_candidates[candidate_id])
    evaluation_by_id = {
        row["candidate_id"]: evaluation for row, evaluation in zip(candidate_set, evaluations)
    }
    source_by_id = {row["candidate_id"]: row for row in rows}
    suppressed = []
    for row in candidate_set:
        if row["hard_gate_passed"]:
            continue
        evaluation = evaluation_by_id[row["candidate_id"]]
        source = source_by_id[row["candidate_id"]]
        suppressed.append(
            {
                "candidate_id": row["candidate_id"],
                "decision_class": evaluation["decision_class"],
                "hard_failure_reasons": list(evaluation["feasibility"]["hard_failure_reasons"]),
                "projection_metric_errors": list(evaluation["feasibility"]["projection_metric_errors"]),
                "plausibility_failure_reasons": list(evaluation["layout_plausibility"]["plausibility_failure_reasons"]),
                "action_family": row["action_family"],
                "changed_pair_indices": list(source.get("changed_pair_indices", [])),
            }
        )
    hard_candidates = [row for row in candidate_set if row["hard_gate_passed"]]
    legacy_portfolio = legacy_payload.get(
        "legacy_portfolio_candidates", legacy_payload.get("portfolio_candidates", {})
    ) or {}
    compact_legacy_portfolio = {
        name: {
            "candidate_id": bucket.get("candidate", {}).get("candidate_id") if bucket.get("candidate") else None,
            "action_family": bucket.get("candidate", {}).get("action_family") if bucket.get("candidate") else None,
            "reason": bucket.get("reason"),
        }
        for name, bucket in legacy_portfolio.items()
    }
    legacy_trial_candidates = [
        row["candidate_id"] for row in rows if row.get("direct_ls_trial_allowed")
    ]
    case_contract = dict(legacy_payload["case_contract"])
    legacy_contract_provenance = {
        key: case_contract.pop(key)
        for key in ("legacy_default_contract", "legacy_source_files")
        if key in case_contract
    }
    return {
        "schema_version": SCHEMA_VERSION,
        "case_name": legacy_payload.get("case_name"),
        "safety_boundary": {
            "expert_side_only": True,
            "offline_dry_run_only": True,
            "automatic_apply": False,
            "annotation_writeback": False,
            "worker_facing": False,
            "routing_input": False,
            "thesis_protocol_artifact": False,
        },
        "case_contract": case_contract,
        "candidate_set": candidate_set,
        "candidate_review_geometry": {
            row["candidate_id"]: {
                "coordinate_changes": copy.deepcopy(row.get("coordinate_changes", []))
            }
            for row in rows
        },
        "constrained_evaluations": {
            row["candidate_id"]: _core_evaluation(evaluation)
            for row, evaluation in zip(candidate_set, evaluations)
        },
        "column_evidence_source_inventory": copy.deepcopy(
            legacy_payload.get("column_evidence_source_inventory", {})
        ),
        "authorization_contract": {
            "candidate_set.recommended_review_candidate": "diagnostic_bucket_selection_only",
            "downstream_authority": [
                "overall_verdict.recommended_review_candidate_available",
                "portfolio_ranking.<bucket>.accepted",
                "portfolio_ranking.<bucket>.downstream_recommendation",
            ],
            "audit_blocked_effect": {
                "accepted": False,
                "downstream_recommendation": False,
            },
        },
        "portfolio_ranking": portfolio,
        "suppressed_candidates": suppressed,
        "legacy_diagnostics": {
            "candidate_source_schema_version": legacy_payload.get("schema_version"),
            "legacy_case_contract_provenance": legacy_contract_provenance,
            "legacy_portfolio_candidates": compact_legacy_portfolio,
            "legacy_local_score_total": {
                row["candidate_id"]: row.get("score_breakdown", {}).get("local_score_total")
                for row in rows
            },
            "legacy_direct_ls_trial_candidates": legacy_trial_candidates,
            "legacy_ls_trial_available": any(
                evaluation["feasibility"]["hard_gate_passed"]
                and row.get("direct_ls_trial_allowed")
                for row, evaluation in zip(rows, evaluations)
            ),
            "legacy_score_role": "diagnostic_only",
            "legacy_portfolio_role": "diagnostic_only",
        },
        "overall_verdict": {
            "hard_feasible_candidate_available": bool(hard_candidates),
            "improving_hypothesis_available": any(
                row["hard_gate_passed"] and row["is_improving_hypothesis"]
                for row in candidate_set
            ),
            "recommended_review_candidate_available": False,
            "selection_status": "audit_blocked",
            "recommended_status": "not_accepted_pending_post_change_selection_audit",
            "blocked_reason": POST_CHANGE_BLOCKED_REASON,
            "c6_1_blocked_reason": AUDIT_BLOCKED_REASON,
            "legacy_ls_trial_available": any(
                evaluation["feasibility"]["hard_gate_passed"]
                and row.get("direct_ls_trial_allowed")
                for row, evaluation in zip(rows, evaluations)
            ),
            "automatic_fix_claimed": False,
            "verdict_basis": "hard_feasibility_improvement_and_portfolio_selection",
        },
    }


def build_payload(
    *,
    assertion_path: Path = DEFAULT_ASSERTION,
    projection_path: Path = DEFAULT_PROJECTION,
) -> dict[str, Any]:
    assertion = json.loads(assertion_path.read_text(encoding="utf-8"))
    projection = json.loads(projection_path.read_text(encoding="utf-8"))
    original = next(
        (row for row in projection.get("variants", []) if row.get("name") == "original"),
        None,
    )
    if original is None or not isinstance(original.get("ordered_pairs"), list):
        raise ValueError("projection metrics must contain original ordered_pairs")
    legacy = run_action_library(
        original["ordered_pairs"],
        expert_assertion=assertion,
        projection_config={
            "width": int(projection["width"]),
            "height": int(projection["height"]),
            "coordinate_mode": str(projection["coordinate_mode_requested"]),
            "camera_height": float(projection["camera_height"]),
        },
    )
    projection_config = {
        "width": int(projection["width"]),
        "height": int(projection["height"]),
        "coordinate_mode": str(projection["coordinate_mode_requested"]),
        "camera_height": float(projection["camera_height"]),
    }
    source = inventory_hohonet_source(
        projection.get("input_provenance", {}).get("image", {}),
        repo_root=REPO_ROOT,
    )
    _enrich_legacy_with_column_evidence(legacy, original, projection_config, source)
    legacy["case_name"] = str(projection.get("case_name") or assertion.get("case_name"))
    core = build_core_payload_from_legacy(legacy)
    core["state_before"] = {
        "ordered_pairs": original["ordered_pairs"],
        "projection_config": {
            "width": int(projection["width"]),
            "height": int(projection["height"]),
            "coordinate_mode": str(projection["coordinate_mode_requested"]),
            "camera_height": float(projection["camera_height"]),
        },
        "source_variant": "original",
        "image_provenance": copy.deepcopy(
            projection.get("input_provenance", {}).get("image", {})
        ),
        "source_projection_artifact": projection_path.as_posix(),
    }
    return core


def run(out_dir: Path = DEFAULT_OUT_DIR, **kwargs: Any) -> Path:
    payload = build_payload(**kwargs)
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / "hypothesis_ranking_core.json"
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    parser.add_argument("--assertion", type=Path, default=DEFAULT_ASSERTION)
    parser.add_argument("--projection", type=Path, default=DEFAULT_PROJECTION)
    args = parser.parse_args()
    print(run(args.out_dir, assertion_path=args.assertion, projection_path=args.projection))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
