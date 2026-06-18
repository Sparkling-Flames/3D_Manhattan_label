"""Build the read-only M15.24 hard-case audit pack."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Mapping

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tools.paper_a_manhattan.manhattan_m1520_local_candidate_search import (  # noqa: E402
    ASSERTION_SCHEMA_VERSION,
    generate_joint_candidates,
    normalize_expert_assertions,
    run_local_candidate_search,
)
from tools.paper_a_manhattan.run_local_3d_projection_review import (  # noqa: E402
    extract_ordered_pairs,
)


SCHEMA_VERSION = "m15_24_hard_case_audit_pack_v1"
SAFETY_BOUNDARY = {
    "expert_side": True,
    "offline_local_only": True,
    "annotation_write_allowed": False,
    "annotation_patch_generated": False,
    "routing_input": False,
    "formal_artifact": False,
    "correctness_oracle": False,
}
INPUT_ROOT = Path(
    "analysis_results/paper_a_manhattan/single_image_manual_test/latest_gt_checked"
)
ASSERTION_3741 = Path(
    "analysis_results/paper_a_manhattan/local_candidate_search/"
    "task218_ann3741/expert_assertion.json"
)


def _inline_assertion(
    *,
    keep: list[list[int]],
    primary: list[str],
    allowed: list[str],
    frozen: list[int],
    window: list[int],
) -> dict[str, Any]:
    return {
        "schema_version": ASSERTION_SCHEMA_VERSION,
        "keep_distinct_pairs": keep,
        "primary_edges": primary,
        "allowed_short_edges": allowed,
        "do_not_move_pairs": frozen,
        "candidate_window": window,
        "notes": [],
    }


def _case_specs() -> list[dict[str, Any]]:
    return [
        {
            "case_name": "task218_ann3741",
            "case_category": "dense_corner_topology_instability",
            "input": INPUT_ROOT / "task218_ann3741_m1516_stabilized_input.json",
            "assertion_source": "file",
            "assertion": ASSERTION_3741,
        },
        {
            "case_name": "task218_ann2369",
            "case_category": "joint_search_smoke_applicable",
            "input": INPUT_ROOT / "task218_ann2369_m1516_stabilized_input.json",
            "assertion_source": "inline",
            "assertion": _inline_assertion(
                keep=[[5, 6]],
                primary=["6-7"],
                allowed=["5-6"],
                frozen=[8],
                window=[5, 6, 7, 8],
            ),
        },
        {
            "case_name": "task238_ann2389",
            "case_category": "ineligible_safe_skip",
            "input": INPUT_ROOT / "task238_ann2389_m1516_stabilized_input.json",
            "assertion_source": "inline",
            "assertion": _inline_assertion(
                keep=[[2, 3]],
                primary=["3-4"],
                allowed=["2-3"],
                frozen=[1, 6],
                window=[2, 3, 4, 5],
            ),
        },
    ]


def _empty_row(spec: Mapping[str, Any], status: str, note: str) -> dict[str, Any]:
    return {
        "case_name": spec["case_name"],
        "case_category": spec["case_category"],
        "input_file": str(spec["input"]).replace("\\", "/"),
        "assertion_source": spec["assertion_source"],
        "applicability_status": status,
        "generated_count": 0,
        "retained_count": 0,
        "joint_candidate_count": 0,
        "direct_fix_available": False,
        "best_executable_candidate_id": None,
        "best_executable_family": None,
        "best_executable_decision_class": None,
        "best_joint_candidate_id": None,
        "best_joint_family": None,
        "best_joint_decision_class": None,
        "primary_unresolved_edges": [],
        "persistent_short_wall_edges": [],
        "assertion_violation_count": 0,
        "new_unresolved_edge_count": 0,
        "self_intersection_or_collapse_count": 0,
        "notes": [note],
    }


def _applicable_row(spec: Mapping[str, Any], result: Mapping[str, Any]) -> dict[str, Any]:
    executable = list(result["candidates"])
    topology = list(result["topology_hypotheses"])
    all_rows = [*executable, *topology]
    best = executable[0] if executable else None
    best_joint = next(
        (row for row in executable if str(row["family"]).startswith("joint_")),
        None,
    )
    joint_count = sum(
        count
        for family, count in result["candidate_generation"]["generated_count_by_family"].items()
        if family.startswith("joint_")
    )
    return {
        "case_name": spec["case_name"],
        "case_category": spec["case_category"],
        "input_file": str(spec["input"]).replace("\\", "/"),
        "assertion_source": spec["assertion_source"],
        "applicability_status": "applicable",
        "generated_count": result["candidate_generation"]["generated_count"],
        "retained_count": result["candidate_generation"]["retained_count"],
        "joint_candidate_count": joint_count,
        "direct_fix_available": bool(result["case_triage"]["direct_fix_available"]),
        "best_executable_candidate_id": best["candidate_id"] if best else None,
        "best_executable_family": best["family"] if best else None,
        "best_executable_decision_class": best["decision_class"] if best else None,
        "best_joint_candidate_id": best_joint["candidate_id"] if best_joint else None,
        "best_joint_family": best_joint["family"] if best_joint else None,
        "best_joint_decision_class": best_joint["decision_class"] if best_joint else None,
        "primary_unresolved_edges": result["case_triage"]["primary_unresolved_edges"],
        "persistent_short_wall_edges": result["case_triage"]["persistent_short_wall_edges"],
        "assertion_violation_count": sum(bool(row.get("assertion_violations")) for row in all_rows),
        "new_unresolved_edge_count": sum(bool(row.get("new_unresolved_edges")) for row in all_rows),
        "self_intersection_or_collapse_count": sum(
            bool(row.get("collapse_risk_details"))
            or bool(row.get("self_intersection", {}).get("after"))
            for row in all_rows
        ),
        "notes": [
            "Aggregate diagnostic only; detailed per-candidate evidence remains in the local search output."
        ],
    }


def build_audit_pack() -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    for spec in _case_specs():
        try:
            input_payload = json.loads((REPO_ROOT / spec["input"]).read_text(encoding="utf-8"))
            pairs, _ = extract_ordered_pairs(input_payload)
            assertion_payload = (
                json.loads((REPO_ROOT / spec["assertion"]).read_text(encoding="utf-8"))
                if spec["assertion_source"] == "file"
                else spec["assertion"]
            )
            window = assertion_payload["candidate_window"]
            assertions = normalize_expert_assertions(
                assertion_payload,
                valid_pair_indices=[int(pair["effective_pair_index"]) for pair in pairs],
                local_window=window,
            )
            if not generate_joint_candidates(pairs, assertions):
                rows.append(
                    _empty_row(
                        spec,
                        "ineligible_safe_skip",
                        f"M15.22 joint families require pairs 5/6/7/8; available pair count is {len(pairs)} and assertion window is {window}.",
                    )
                )
                continue
            result = run_local_candidate_search(
                pairs,
                local_window=window,
                expert_assertions=assertion_payload,
            )
            rows.append(_applicable_row(spec, result))
        except Exception as exc:  # audit pack records a case failure without losing other rows
            rows.append(_empty_row(spec, "error", f"{type(exc).__name__}: {exc}"))
    summary = {
        "applicable_count": sum(row["applicability_status"] == "applicable" for row in rows),
        "ineligible_safe_skip_count": sum(
            row["applicability_status"] == "ineligible_safe_skip" for row in rows
        ),
        "error_count": sum(row["applicability_status"] == "error" for row in rows),
        "direct_fix_available_count": sum(bool(row["direct_fix_available"]) for row in rows),
    }
    return {
        "schema_version": SCHEMA_VERSION,
        "safety_boundary": dict(SAFETY_BOUNDARY),
        "case_count": len(rows),
        "cases": rows,
        "summary": summary,
    }


def render_markdown(payload: Mapping[str, Any]) -> str:
    lines = [
        "# M15.24 Hard-case Audit Pack",
        "",
        "> Expert-side aggregate only: no writeback, annotation patch, routing, formal artifact, or correctness-oracle role.",
        "",
        "## Summary",
        "",
        "| case | category | status | generated | retained | joint | direct fix | best executable | best joint |",
        "|---|---|---|---:|---:|---:|---|---|---|",
    ]
    for row in payload["cases"]:
        lines.append(
            f"| {row['case_name']} | {row['case_category']} | {row['applicability_status']} | "
            f"{row['generated_count']} | {row['retained_count']} | {row['joint_candidate_count']} | "
            f"{row['direct_fix_available']} | {row['best_executable_candidate_id'] or '—'} | "
            f"{row['best_joint_candidate_id'] or '—'} |"
        )
    for row in payload["cases"]:
        lines.extend(["", f"## {row['case_name']}", ""])
        if row["applicability_status"] == "applicable":
            lines.extend(
                [
                    f"- Category: `{row['case_category']}`",
                    f"- Best executable: `{row['best_executable_candidate_id']}` / `{row['best_executable_family']}` / `{row['best_executable_decision_class']}`",
                    f"- Best joint: `{row['best_joint_candidate_id']}` / `{row['best_joint_family']}` / `{row['best_joint_decision_class']}`",
                    f"- Direct fix available: `{row['direct_fix_available']}`",
                    f"- Primary unresolved edges: `{row['primary_unresolved_edges']}`",
                    f"- Persistent short-wall edges: `{row['persistent_short_wall_edges']}`",
                    "- Why diagnostic only: retained candidates still obey assertion and geometry gates; no aggregate row authorizes direct repair.",
                ]
            )
        else:
            lines.extend(
                [
                    f"- Applicability: `{row['applicability_status']}`",
                    f"- Safe-skip reason: {row['notes'][0]}",
                ]
            )
    lines.extend(
        [
            "",
            "## Interpretation boundary",
            "",
            "- Expert-side only.",
            "- No Label Studio writeback or annotation patch.",
            "- No routing or formal artifact role.",
            "- Not a correctness oracle.",
            "",
        ]
    )
    return "\n".join(lines)


def run(out_dir: Path) -> dict[str, Path]:
    payload = build_audit_pack()
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = out_dir / "m1524_hard_case_audit_pack.json"
    report_path = out_dir / "m1524_hard_case_audit_pack.md"
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    report_path.write_text(render_markdown(payload), encoding="utf-8")
    return {"json": json_path, "report": report_path}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=Path("analysis_results/paper_a_manhattan/hard_case_audit_pack"),
    )
    args = parser.parse_args()
    for kind, path in run(args.out_dir).items():
        print(f"{kind}: {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
