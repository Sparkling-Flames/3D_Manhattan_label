"""Run the expert-side Manhattan Constrained Hypothesis Ranking Core."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Mapping

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tools.paper_a_manhattan.manhattan_hypothesis_portfolio import build_hypothesis_portfolio
from tools.paper_a_manhattan.manhattan_m1528_semantic_action_library import run_action_library
from tools.paper_a_manhattan.run_m1528_semantic_action_library import (
    DEFAULT_ASSERTION,
    DEFAULT_PROJECTION,
)


SCHEMA_VERSION = "manhattan_constrained_hypothesis_ranking_core_v1"
DEFAULT_OUT_DIR = Path("analysis_results/paper_a_manhattan/hypothesis_ranking_core/task218_ann3741")


def build_core_payload_from_legacy(legacy_payload: Mapping[str, Any]) -> dict[str, Any]:
    rows = list(legacy_payload.get("candidate_set", []))
    if not rows:
        raise ValueError("legacy candidate source returned no candidate_set")
    evaluations = [row["constrained_evaluation"] for row in rows]
    candidate_set: list[dict[str, Any]] = []
    for row, evaluation in zip(rows, evaluations):
        hard_passed = bool(evaluation["feasibility"]["hard_gate_passed"])
        reviewable = hard_passed and evaluation["decision_class"] != "neutral_no_improvement"
        candidate_set.append(
            {
                "candidate_id": row["candidate_id"],
                "action_family": row.get("action_family"),
                "changed_pair_indices": list(row.get("changed_pair_indices", [])),
                "decision_class": evaluation["decision_class"],
                "hard_gate_passed": hard_passed,
                "manual_review_candidate": reviewable,
                "legacy_direct_ls_trial_allowed": bool(row.get("direct_ls_trial_allowed")),
                "hypothesis_ranking_key": list(row["hypothesis_ranking_key"]),
            }
        )
    portfolio = build_hypothesis_portfolio(candidate_set, evaluations)
    suppressed = [entry["candidate"] for entry in portfolio["suppressed_candidates"]]
    hard_candidates = [row for row in candidate_set if row["hard_gate_passed"]]
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
        "case_contract": legacy_payload["case_contract"],
        "candidate_set": candidate_set,
        "constrained_evaluations": {
            row["candidate_id"]: evaluation for row, evaluation in zip(candidate_set, evaluations)
        },
        "portfolio_ranking": portfolio,
        "suppressed_candidates": suppressed,
        "legacy_diagnostics": {
            "candidate_source_schema_version": legacy_payload.get("schema_version"),
            "legacy_portfolio_candidates": legacy_payload.get("legacy_portfolio_candidates", legacy_payload.get("portfolio_candidates")),
            "legacy_local_score_total": {
                row["candidate_id"]: row.get("score_breakdown", {}).get("local_score_total")
                for row in rows
            },
            "legacy_direct_ls_trial_candidates": [
                row["candidate_id"] for row in rows if row.get("direct_ls_trial_allowed")
            ],
            "legacy_score_role": "diagnostic_only",
        },
        "overall_verdict": {
            "hypothesis_available": bool(hard_candidates),
            "manual_review_candidate_available": any(row["manual_review_candidate"] for row in candidate_set),
            "legacy_ls_trial_available": any(
                row["hard_gate_passed"] and row["legacy_direct_ls_trial_allowed"]
                for row in candidate_set
            ),
            "automatic_fix_claimed": False,
            "verdict_basis": "constrained_hard_gate",
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
    legacy["case_name"] = str(projection.get("case_name") or assertion.get("case_name"))
    return build_core_payload_from_legacy(legacy)


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
