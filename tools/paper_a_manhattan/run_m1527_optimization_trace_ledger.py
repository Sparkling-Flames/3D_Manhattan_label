"""Seed or update the expert-side M15.27.1 optimization trace ledger."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping


SCHEMA_VERSION = "m15_27_1_optimization_trace_ledger_v1"
ROOT = Path("analysis_results/paper_a_manhattan")
DEFAULT_M1522 = ROOT / "local_candidate_search/task218_ann3741/candidate_search.json"
DEFAULT_M1526 = ROOT / "adaptive_local_probe/task218_ann3741/adaptive_probe.json"
DEFAULT_M1527 = ROOT / "semantic_direct_search/task218_ann3741/semantic_direct_search.json"
DEFAULT_LEDGER = ROOT / "optimization_trace/task218_ann3741/optimization_trace_ledger.json"
COMPARATIVE_VERDICTS = {
    "m15_27_better",
    "m15_26_better",
    "no_material_difference",
    "inconclusive",
}


def _read(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return value


def _source(path: Path) -> dict[str, str]:
    return {"path": path.as_posix(), "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}


def _m1522_stage(payload: Mapping[str, Any]) -> dict[str, Any]:
    row = payload["candidates"][0]
    edge = next(item for item in row["required_wall_residuals"] if item["edge"] == "6-7")
    return {
        "schema_version": payload.get("schema_version"),
        "best_candidate_id": row["candidate_id"],
        "decision_class": row.get("decision_class"),
        "primary_residual_before": edge["before_residual_deg"],
        "primary_residual_after": edge["after_residual_deg"],
        "manual_review_candidate_available": bool(row.get("direct_ls_trial_allowed")),
        "automatic_fix_claimed": False,
    }


def _probe_stage(payload: Mapping[str, Any], *, current_contract: bool) -> dict[str, Any]:
    row = payload["top_candidates"][0]
    score = row["score_breakdown"]
    baseline = payload["baseline"]["score_breakdown"]
    verdict = payload.get("overall_verdict", {})
    available = (
        bool(verdict.get("manual_review_candidate_available"))
        if current_contract
        else bool(verdict.get("direct_fix_available"))
    )
    return {
        "schema_version": payload.get("schema_version"),
        "best_candidate_id": row["candidate_id"],
        "decision_class": row.get("decision_class"),
        "primary_residual_before": baseline["primary_edge_6_7_residual"],
        "primary_residual_after": score["primary_edge_6_7_residual"],
        "manual_review_candidate_available": available,
        "automatic_fix_claimed": False,
    }


def build_ledger(
    m1522_path: Path = DEFAULT_M1522,
    m1526_path: Path = DEFAULT_M1526,
    m1527_path: Path = DEFAULT_M1527,
) -> dict[str, Any]:
    m1522, m1526, m1527 = (_read(path) for path in (m1522_path, m1526_path, m1527_path))
    stages = {
        "m15_22": _m1522_stage(m1522),
        "m15_26": _probe_stage(m1526, current_contract=False),
        "m15_27_1": _probe_stage(m1527, current_contract=True),
    }
    candidate_ids = sorted(
        {
            row["candidate_id"]
            for payload in (m1522, m1526, m1527)
            for row in payload.get("top_candidates", payload.get("candidates", []))
            if isinstance(row, Mapping) and row.get("candidate_id")
        }
    )
    return {
        "schema_version": SCHEMA_VERSION,
        "case_name": "task218_ann3741",
        "source_artifacts": {
            "m15_22": _source(m1522_path),
            "m15_26": _source(m1526_path),
            "m15_27_1": _source(m1527_path),
        },
        "optimization_path": stages,
        "known_candidate_ids": candidate_ids,
        "manual_visual_review": {
            "status": "pending",
            "comparative_verdict": None,
            "selected_candidate_id": None,
            "manual_ls_trial_recommended": None,
            "notes": None,
            "reviewer": None,
            "reviewed_at": None,
        },
        "safety_boundary": {
            "expert_side": True,
            "offline_local_only": True,
            "annotation_write_allowed": False,
            "automatic_apply": False,
            "worker_facing": False,
            "routing_input": False,
            "formal_artifact": False,
        },
    }


def _atomic_write(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    os.replace(temp, path)


def seed_ledger(path: Path = DEFAULT_LEDGER, *, overwrite: bool = False) -> Path:
    if path.exists() and not overwrite:
        raise FileExistsError(f"ledger already exists: {path}")
    _atomic_write(path, build_ledger())
    return path


def record_manual_review(
    path: Path,
    *,
    comparative_verdict: str,
    selected_candidate_id: str,
    manual_ls_trial_recommended: bool,
    notes: str,
    reviewer: str | None = None,
    reviewed_at: str | None = None,
) -> Path:
    payload = _read(path)
    if payload.get("schema_version") != SCHEMA_VERSION:
        raise ValueError(f"ledger schema_version must be {SCHEMA_VERSION}")
    if comparative_verdict not in COMPARATIVE_VERDICTS:
        raise ValueError(f"unsupported comparative verdict: {comparative_verdict}")
    if selected_candidate_id not in payload.get("known_candidate_ids", []):
        raise ValueError(f"unknown candidate id: {selected_candidate_id}")
    payload["manual_visual_review"] = {
        "status": "reviewed",
        "comparative_verdict": comparative_verdict,
        "selected_candidate_id": selected_candidate_id,
        "manual_ls_trial_recommended": bool(manual_ls_trial_recommended),
        "notes": notes,
        "reviewer": reviewer,
        "reviewed_at": reviewed_at or datetime.now(timezone.utc).isoformat(),
    }
    _atomic_write(path, payload)
    return path


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ledger", type=Path, default=DEFAULT_LEDGER)
    parser.add_argument("--record-verdict", choices=sorted(COMPARATIVE_VERDICTS))
    parser.add_argument("--selected-candidate")
    parser.add_argument("--manual-ls-trial-recommended", choices=("true", "false"))
    parser.add_argument("--notes", default="")
    parser.add_argument("--reviewer")
    parser.add_argument("--reviewed-at")
    args = parser.parse_args()
    if args.record_verdict is None:
        print(seed_ledger(args.ledger))
        return 0
    if args.selected_candidate is None or args.manual_ls_trial_recommended is None:
        parser.error("recording requires --selected-candidate and --manual-ls-trial-recommended")
    print(
        record_manual_review(
            args.ledger,
            comparative_verdict=args.record_verdict,
            selected_candidate_id=args.selected_candidate,
            manual_ls_trial_recommended=args.manual_ls_trial_recommended == "true",
            notes=args.notes,
            reviewer=args.reviewer,
            reviewed_at=args.reviewed_at,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
