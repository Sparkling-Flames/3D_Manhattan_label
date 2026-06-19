"""Run the read-only M15.26 adaptive local probe and write JSON/Markdown."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any, Mapping

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tools.paper_a_manhattan.manhattan_m1526_adaptive_local_probe import (
    run_adaptive_probe,
)


DEFAULT_CANDIDATE_SEARCH = Path(
    "analysis_results/paper_a_manhattan/local_candidate_search/"
    "task218_ann3741/candidate_search.json"
)
DEFAULT_VISUAL_VERDICT = Path(
    "analysis_results/paper_a_manhattan/visual_verdict/"
    "task218_ann3741/visual_verdict.json"
)
DEFAULT_EXPERT_ASSERTION = Path(
    "analysis_results/paper_a_manhattan/local_candidate_search/"
    "task218_ann3741/expert_assertion.json"
)
DEFAULT_PROJECTION_METRICS = Path(
    "analysis_results/paper_a_manhattan/local_3d_projection/"
    "task218_ann3741/projection_metrics.json"
)
DEFAULT_OUT_DIR = Path(
    "analysis_results/paper_a_manhattan/adaptive_local_probe/task218_ann3741"
)


def _read_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return payload


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _source(path: Path) -> dict[str, str]:
    return {"path": path.as_posix(), "sha256": _sha256(path)}


def build_payload(
    *,
    candidate_search_path: Path = DEFAULT_CANDIDATE_SEARCH,
    visual_verdict_path: Path = DEFAULT_VISUAL_VERDICT,
    expert_assertion_path: Path = DEFAULT_EXPERT_ASSERTION,
    projection_metrics_path: Path = DEFAULT_PROJECTION_METRICS,
) -> dict[str, Any]:
    candidate_search = _read_json(candidate_search_path)
    visual_verdict = _read_json(visual_verdict_path)
    assertion = _read_json(expert_assertion_path)
    projection_metrics = _read_json(projection_metrics_path)
    original = next(
        (
            row
            for row in projection_metrics.get("variants", [])
            if isinstance(row, Mapping) and row.get("name") == "original"
        ),
        None,
    )
    if original is None or not isinstance(original.get("ordered_pairs"), list):
        raise ValueError("projection metrics must contain original ordered_pairs")
    projection_config = candidate_search.get("projection_config")
    if not isinstance(projection_config, Mapping):
        raise ValueError("candidate search must contain projection_config")
    payload = run_adaptive_probe(
        original["ordered_pairs"],
        expert_assertion=assertion,
        projection_config=projection_config,
        visual_verdict=visual_verdict,
    )
    payload.update(
        {
            "case_name": "task218_ann3741",
            "source_artifacts": {
                "candidate_search": _source(candidate_search_path),
                "visual_verdict": _source(visual_verdict_path),
                "expert_assertion": _source(expert_assertion_path),
                "projection_metrics": _source(projection_metrics_path),
            },
        }
    )
    return payload


def render_markdown(payload: Mapping[str, Any]) -> str:
    search_space = payload["search_space"]
    baseline = payload["baseline"]["score_breakdown"]
    best = payload["top_candidates"][0] if payload["top_candidates"] else None
    verdict = payload["overall_verdict"]
    lines = [
        "# M15.26 Primary-Edge-Constrained Wall-Surface-Aware Adaptive Probe",
        "",
        "## Baseline problem summary from M15.25",
        "",
        "- No direct candidate fix was available in the archived visual verdict.",
        "- Pairs 1/2/5/6/7/8 retain y-height inconsistency.",
        "- Wall-surface / footprint problems remain at 2-3 and 5-6-7-8.",
        "- Primary edge 6-7 remains unresolved.",
        "",
        "## Search scope",
        "",
        f"- Movable variables: `{search_space['movable_variables']}`",
        f"- Fixed anchors: `{search_space['fixed_anchor_pair_indices']}`",
        f"- Score-only frozen pairs: `{search_space['score_only_frozen_pair_indices']}`",
        "- No order mutation, merge/delete, auto reorder, or topology rewrite.",
        "",
        "## Score components",
        "",
    ]
    for key, value in baseline.items():
        if key != "short_wall_deficits":
            lines.append(f"- `{key}` baseline: `{value}`")
    lines.extend(["", "## Best candidate", ""])
    if best is None:
        lines.append("No candidate was evaluated.")
    else:
        lines.extend(
            [
                f"- Candidate: `{best['candidate_id']}`",
                f"- Decision: `{best['decision_class']}`",
                f"- Direct LS trial allowed: `{best['direct_ls_trial_allowed']}`",
                f"- Local score: `{best['score_breakdown']['local_score_total']:.6f}`",
                f"- Primary edge 6-7: `{baseline['primary_edge_6_7_residual']:.6f}` → `{best['score_breakdown']['primary_edge_6_7_residual']:.6f}`",
                f"- Failed direct-trial checks: `{best['direct_trial_gate']['failed_checks']}`",
            ]
        )
    lines.extend(
        [
            "",
            f"**Overall verdict: `{verdict['verdict']}`; direct_fix_available = `{verdict['direct_fix_available']}`.**",
            "",
            "## Top 5 candidates",
            "",
            "| candidate | decision | score | primary 6-7 | movement | assertion compliant | direct LS trial |",
            "|---|---|---:|---:|---:|---|---|",
        ]
    )
    for row in payload["top_candidates"]:
        score = row["score_breakdown"]
        lines.append(
            f"| {row['candidate_id']} | {row['decision_class']} | "
            f"{score['local_score_total']:.6f} | "
            f"{score['primary_edge_6_7_residual']:.6f} | "
            f"{score['movement_l1_ls_percent']:.6f} | "
            f"{row['assertion_compliant']} | {row['direct_ls_trial_allowed']} |"
        )
    lines.extend(
        [
            "",
            "## Search trace",
            "",
            "| round | step | generated | retained | best | score | primary before | primary after | stop reason |",
            "|---:|---:|---:|---:|---|---:|---:|---:|---|",
        ]
    )
    for row in payload["search_trace"]:
        lines.append(
            f"| {row['round_index']} | {row['step_size']} | {row['generated_count']} | "
            f"{row['retained_count']} | {row['best_candidate_id']} | {row['best_score']:.6f} | "
            f"{row['primary_edge_residual_before']:.6f} | {row['primary_edge_residual_after']:.6f} | "
            f"{row['reason_for_stopping']} |"
        )
    lines.extend(
        [
            "",
            "## Safety boundary",
            "",
            "Expert-side, offline, deterministic dry-run only. No annotation patch, Label Studio writeback, automatic apply, global optimization, worker-facing output, routing input, or formal artifact is produced.",
            "",
        ]
    )
    return "\n".join(lines)


def run(
    out_dir: Path = DEFAULT_OUT_DIR,
    *,
    candidate_search_path: Path = DEFAULT_CANDIDATE_SEARCH,
    visual_verdict_path: Path = DEFAULT_VISUAL_VERDICT,
    expert_assertion_path: Path = DEFAULT_EXPERT_ASSERTION,
    projection_metrics_path: Path = DEFAULT_PROJECTION_METRICS,
) -> dict[str, Path]:
    payload = build_payload(
        candidate_search_path=candidate_search_path,
        visual_verdict_path=visual_verdict_path,
        expert_assertion_path=expert_assertion_path,
        projection_metrics_path=projection_metrics_path,
    )
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = out_dir / "adaptive_probe.json"
    report_path = out_dir / "adaptive_probe.md"
    json_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    report_path.write_text(render_markdown(payload), encoding="utf-8")
    return {"json": json_path, "report": report_path}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidate-search", type=Path, default=DEFAULT_CANDIDATE_SEARCH)
    parser.add_argument("--visual-verdict", type=Path, default=DEFAULT_VISUAL_VERDICT)
    parser.add_argument("--expert-assertion", type=Path, default=DEFAULT_EXPERT_ASSERTION)
    parser.add_argument("--projection-metrics", type=Path, default=DEFAULT_PROJECTION_METRICS)
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    args = parser.parse_args()
    paths = run(
        args.out_dir,
        candidate_search_path=args.candidate_search,
        visual_verdict_path=args.visual_verdict,
        expert_assertion_path=args.expert_assertion,
        projection_metrics_path=args.projection_metrics,
    )
    for kind, path in paths.items():
        print(f"{kind}: {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
