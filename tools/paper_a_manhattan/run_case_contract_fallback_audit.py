"""Audit C1 case-contract fallback behavior without changing runner logic."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any, Mapping, Sequence

from tools.paper_a_manhattan.manhattan_case_contract import build_case_contract
from tools.paper_a_manhattan.run_m1528_semantic_action_library import (
    DEFAULT_ASSERTION,
    DEFAULT_PROJECTION,
)


SCHEMA_VERSION = "hrc_c1_1_case_contract_fallback_audit_v1"
AUDIT_ROOT = Path("analysis_results/paper_a_manhattan/hypothesis_ranking_core/case_contract_fallback_audit")
DEFAULT_OUT_DIR = AUDIT_ROOT / "task218_ann3741"


def _read(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return value


def _source(path: Path) -> dict[str, str]:
    return {"path": path.as_posix(), "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}


def _original(projection: Mapping[str, Any]) -> Mapping[str, Any]:
    original = next(
        (row for row in projection.get("variants", []) if row.get("name") == "original"),
        None,
    )
    if not isinstance(original, Mapping) or not isinstance(original.get("ordered_pairs"), list):
        raise ValueError("projection artifact must contain original ordered_pairs")
    return original


def _minimal_pairs() -> list[dict[str, Any]]:
    return [
        {
            "effective_pair_index": index,
            "top": {"x": float(index), "y": 20.0},
            "bottom": {"x": float(index), "y": 80.0},
        }
        for index in range(1, 9)
    ]


def _summarize_contract(name: str, contract: Mapping[str, Any]) -> dict[str, Any]:
    legacy = contract.get("legacy_default_contract", {})
    fallback_used = bool(legacy.get("used"))
    inferred_fields = [
        "inferred_primary_edges",
        "inferred_secondary_edges",
        "inferred_local_window_pairs",
        "inferred_height_target_pairs",
        "inferred_keep_distinct_pairs",
        "inferred_movable_fields_by_pair",
    ]
    return {
        "case_name": name,
        "contract_status": contract.get("contract_status"),
        "contract_source": contract.get("contract_source"),
        "fail_closed": bool(contract.get("fail_closed")),
        "expert_review_only": bool(contract.get("expert_review_only")),
        "legacy_default_contract": {
            "used": fallback_used,
            "reason": legacy.get("reason"),
        },
        "fallback_used": fallback_used,
        "risk": (
            "legacy_default_contract_in_active_contract"
            if fallback_used
            else "contract_unavailable_fail_closed"
            if contract.get("contract_status") == "unavailable"
            else None
        ),
        "auto_contract_summary": contract.get("auto_contract_summary", {}),
        "evidence_available_flags": contract.get("evidence_available_flags", {}),
        "protected_pairs": contract.get("protected_pairs", []),
        "movable_fields_by_pair": contract.get("movable_fields_by_pair", {}),
        "keep_distinct_pairs": contract.get("keep_distinct_pairs", []),
        "primary_edges": contract.get("primary_edges", []),
        "secondary_edges": contract.get("secondary_edges", []),
        "local_window_pairs": contract.get("local_window_pairs", []),
        "inferred_fields_present": {field: field in contract for field in inferred_fields},
        "inferred_fields_nonempty": {
            field: bool(contract.get(field)) for field in inferred_fields
        },
        "recommended_next_status": (
            "contract_unavailable_expert_review_only_fail_closed_candidate"
            if fallback_used or contract.get("contract_status") == "unavailable"
            else "projection_rule_based_contract_available"
        ),
        "safety_boundary": contract.get("safety_boundary", {}),
    }


def build_payload(
    *,
    projection_path: Path = DEFAULT_PROJECTION,
    assertion_path: Path = DEFAULT_ASSERTION,
) -> dict[str, Any]:
    projection = _read(projection_path)
    original = _original(projection)
    assertion = _read(assertion_path)
    real_contract = build_case_contract(
        original["ordered_pairs"], assertion, original.get("metrics", {})
    )
    synthetic_contract = build_case_contract(_minimal_pairs())
    return {
        "schema_version": SCHEMA_VERSION,
        "case_name": "task218_ann3741",
        "contract_source": real_contract.get("contract_source"),
        "legacy_default_contract": real_contract.get("legacy_default_contract", {}),
        "auto_contract_summary": real_contract.get("auto_contract_summary", {}),
        "evidence_available_flags": real_contract.get("evidence_available_flags", {}),
        "protected_pairs": real_contract.get("protected_pairs", []),
        "movable_fields_by_pair": real_contract.get("movable_fields_by_pair", {}),
        "keep_distinct_pairs": real_contract.get("keep_distinct_pairs", []),
        "inferred_fields_present": _summarize_contract("task218_ann3741", real_contract)["inferred_fields_present"],
        "cases": {
            "task218_ann3741": _summarize_contract("task218_ann3741", real_contract),
            "synthetic_missing_metrics": _summarize_contract(
                "synthetic_missing_metrics", synthetic_contract
            ),
        },
        "active_runner_unchanged": True,
        "accepted": False,
        "downstream_recommendation": False,
        "annotation_writeback": False,
        "source_artifacts": {
            "projection": _source(projection_path),
            "expert_assertion": _source(assertion_path),
        },
        "audit_conclusion": {
            "real_case_uses_legacy_default_contract": bool(
                real_contract.get("legacy_default_contract", {}).get("used")
            ),
            "synthetic_missing_metrics_fallback_used": bool(
                synthetic_contract.get("legacy_default_contract", {}).get("used")
            ),
            "legacy_default_contract_can_enter_active_case_contract": False,
            "next_step": "C1 completed; return to C6 stability audit or C2/C5 diagnostics hardening",
        },
    }


def render_markdown(payload: Mapping[str, Any]) -> str:
    lines = [
        "# HRC C1.1 Case Contract Fallback Audit",
        "",
        f"- Schema: `{payload['schema_version']}`",
        f"- Case: `{payload['case_name']}`",
        f"- Active runner unchanged: `{payload['active_runner_unchanged']}`",
        f"- Accepted: `{payload['accepted']}`",
        f"- Downstream recommendation: `{payload['downstream_recommendation']}`",
        "",
        "## Cases",
        "",
    ]
    for name, summary in payload["cases"].items():
        lines.extend(
            [
                f"### {name}",
                "",
                f"- contract_source: `{summary['contract_source']}`",
                f"- contract_status: `{summary['contract_status']}`",
                f"- fail_closed: `{summary['fail_closed']}`",
                f"- expert_review_only: `{summary['expert_review_only']}`",
                f"- legacy_default_contract.used: `{summary['legacy_default_contract']['used']}`",
                f"- auto_contract_summary.source: `{summary['auto_contract_summary'].get('source')}`",
                f"- risk: `{summary['risk']}`",
                f"- recommended_next_status: `{summary['recommended_next_status']}`",
                "",
            ]
        )
    return "\n".join(lines)


def run(out_dir: Path = DEFAULT_OUT_DIR, **kwargs: Any) -> dict[str, Path]:
    root = AUDIT_ROOT.resolve()
    destination = out_dir.resolve()
    if destination != root and root not in destination.parents:
        raise ValueError(f"audit output must stay under {AUDIT_ROOT.as_posix()}")
    payload = build_payload(**kwargs)
    destination.mkdir(parents=True, exist_ok=True)
    json_path = destination / "case_contract_fallback_audit.json"
    markdown_path = destination / "case_contract_fallback_audit.md"
    with json_path.open("w", encoding="utf-8", newline="\n") as handle:
        handle.write(json.dumps(payload, ensure_ascii=False, indent=2) + "\n")
    with markdown_path.open("w", encoding="utf-8", newline="\n") as handle:
        handle.write(render_markdown(payload) + "\n")
    return {"json": json_path, "markdown": markdown_path}


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--projection", type=Path, default=DEFAULT_PROJECTION)
    parser.add_argument("--expert-assertion", type=Path, default=DEFAULT_ASSERTION)
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    args = parser.parse_args(argv)
    print(
        run(
            args.out_dir,
            projection_path=args.projection,
            assertion_path=args.expert_assertion,
        )["json"]
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
