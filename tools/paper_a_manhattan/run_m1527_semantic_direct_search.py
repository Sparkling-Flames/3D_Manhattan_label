"""Run M15.27 semantic direct search and write its read-only report."""

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

from tools.paper_a_manhattan.manhattan_m1527_semantic_direct_search import (
    run_semantic_direct_search,
)


ROOT = Path("analysis_results/paper_a_manhattan")
DEFAULT_VISUAL_VERDICT = ROOT / "visual_verdict/task218_ann3741/visual_verdict.json"
DEFAULT_ADAPTIVE_PROBE = ROOT / "adaptive_local_probe/task218_ann3741/adaptive_probe.json"
DEFAULT_EXPERT_ASSERTION = ROOT / "local_candidate_search/task218_ann3741/expert_assertion.json"
DEFAULT_PROJECTION_METRICS = ROOT / "local_3d_projection/task218_ann3741/projection_metrics.json"
DEFAULT_OUT_DIR = ROOT / "semantic_direct_search/task218_ann3741"


def _read(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return value


def _source(path: Path) -> dict[str, str]:
    return {"path": path.as_posix(), "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}


def build_payload(
    visual_verdict_path: Path = DEFAULT_VISUAL_VERDICT,
    adaptive_probe_path: Path = DEFAULT_ADAPTIVE_PROBE,
    expert_assertion_path: Path = DEFAULT_EXPERT_ASSERTION,
    projection_metrics_path: Path = DEFAULT_PROJECTION_METRICS,
) -> dict[str, Any]:
    visual = _read(visual_verdict_path)
    adaptive = _read(adaptive_probe_path)
    assertion = _read(expert_assertion_path)
    projection = _read(projection_metrics_path)
    original = next(
        (row for row in projection.get("variants", []) if isinstance(row, Mapping) and row.get("name") == "original"),
        None,
    )
    if original is None or not isinstance(original.get("ordered_pairs"), list):
        raise ValueError("projection metrics must contain original ordered_pairs")
    config = {
        "width": int(projection["width"]),
        "height": int(projection["height"]),
        "coordinate_mode": str(projection["coordinate_mode_requested"]),
        "camera_height": float(projection["camera_height"]),
    }
    payload = run_semantic_direct_search(
        original["ordered_pairs"],
        expert_assertion=assertion,
        projection_config=config,
        visual_verdict=visual,
        adaptive_probe=adaptive,
    )
    payload.update(
        {
            "case_name": "task218_ann3741",
            "source_artifacts": {
                "visual_verdict": _source(visual_verdict_path),
                "adaptive_probe": _source(adaptive_probe_path),
                "expert_assertion": _source(expert_assertion_path),
                "projection_metrics": _source(projection_metrics_path),
            },
        }
    )
    return payload


def render_markdown(payload: Mapping[str, Any]) -> str:
    cluster = payload["dominant_height_cluster"]
    verdict = payload["overall_verdict"]
    comparison = payload["m15_26_comparison"]
    lines = [
        "# M15.27 Semantic Direct Search v1 — task218_ann3741",
        "",
        f"**Manual-review candidate available: `{verdict['manual_review_candidate_available']}`.**",
        f"**Automatic fix claimed: `{verdict['automatic_fix_claimed']}`.**",
        f"**Best candidate requires visual review: `{verdict['best_candidate_requires_visual_review']}`.**",
        "",
        "## Semantic levers",
        "",
        "- `x` → azimuth / column lever",
        "- `top_y` → wall-height / ceiling-height lever",
        "- `bottom_y` → floor-depth / radial-distance lever",
        "",
        "## Dominant projected-height cluster",
        "",
        f"- h*: `{cluster['h_star']:.6f}`",
        f"- Members: `{cluster['cluster_members']}`",
        f"- MAD: `{cluster['mad']:.6f}`",
        f"- Outliers: `{cluster['height_outliers']}`",
        "",
        "## Top candidates",
        "",
        "| candidate | action family | decision | primary 6-7 | changed pairs | local gate | direct trial |",
        "|---|---|---|---:|---|---|---|",
    ]
    for row in payload["top_candidates"]:
        lines.append(
            f"| {row['candidate_id']} | {row['action_family']} | {row['decision_class']} | "
            f"{row['score_breakdown']['primary_edge_6_7_residual']:.6f} | "
            f"{row['changed_pair_indices']} | {row['gate_result']['passed']} | {row['direct_ls_trial_allowed']} |"
        )
    lines.extend(
        [
            "",
            "## Search trace",
            "",
            "| round | step | exploratory | mixed | pattern | accepted | family | reason |",
            "|---:|---:|---:|---|---|---|---|---|",
        ]
    )
    for row in payload["search_trace"]:
        lines.append(
            f"| {row['round_index']} | {row['step_size']} | {row['exploratory_count']} | "
            f"{row['mixed_enabled']} | {row['pattern_extension_evaluated']} | "
            f"{row['accepted_candidate_id']} | {row['accepted_action_family']} | {row['reason']} |"
        )
    lines.extend(
        [
            "",
            "## M15.26 comparison",
            "",
            f"- M15.26 best primary residual: `{comparison['m15_26_primary_edge_residual']}`",
            f"- M15.27 best primary residual: `{comparison['m15_27_primary_edge_residual']}`",
            f"- Better on primary edge: `{comparison['m15_27_primary_edge_better']}`",
            f"- Still partial: `{comparison['m15_27_still_partial']}`",
            "",
            "## Safety boundary",
            "",
            "Expert-side, offline-local, deterministic dry-run only. No annotation mutation, patch generation, automatic application, worker-facing behavior, routing input, or formal artifact is produced.",
            "",
        ]
    )
    return "\n".join(lines)


def run(out_dir: Path = DEFAULT_OUT_DIR) -> dict[str, Path]:
    payload = build_payload()
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = out_dir / "semantic_direct_search.json"
    report_path = out_dir / "semantic_direct_search.md"
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    report_path.write_text(render_markdown(payload), encoding="utf-8")
    return {"json": json_path, "report": report_path}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    args = parser.parse_args()
    for kind, path in run(args.out_dir).items():
        print(f"{kind}: {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
