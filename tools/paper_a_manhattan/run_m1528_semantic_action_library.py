"""Run M15.28 after the required M15.27.1 visual-review checkpoint."""

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

from tools.paper_a_manhattan.manhattan_m1528_semantic_action_library import run_action_library


ROOT = Path("analysis_results/paper_a_manhattan")
DEFAULT_ASSERTION = ROOT / "local_candidate_search/task218_ann3741/expert_assertion.json"
DEFAULT_PROJECTION = ROOT / "local_3d_projection/task218_ann3741/projection_metrics.json"
DEFAULT_M1527 = ROOT / "semantic_direct_search/task218_ann3741/semantic_direct_search.json"
DEFAULT_LEDGER = ROOT / "optimization_trace/task218_ann3741/optimization_trace_ledger.json"
DEFAULT_OUT_DIR = ROOT / "semantic_action_library/task218_ann3741"


def _read(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return value


def _source(path: Path) -> dict[str, str]:
    return {"path": path.as_posix(), "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}


def build_payload(
    *,
    assertion_path: Path = DEFAULT_ASSERTION,
    projection_path: Path = DEFAULT_PROJECTION,
    m1527_path: Path = DEFAULT_M1527,
    ledger_path: Path = DEFAULT_LEDGER,
) -> dict[str, Any]:
    ledger = _read(ledger_path)
    if ledger.get("manual_visual_review", {}).get("status") != "reviewed":
        raise ValueError("M15.28 requires a reviewed M15.27.1 optimization trace ledger")
    assertion, projection, m1527 = (_read(path) for path in (assertion_path, projection_path, m1527_path))
    if m1527.get("overall_verdict", {}).get("automatic_fix_claimed") is not False:
        raise ValueError("M15.28 requires the M15.27.1 no-automatic-fix contract")
    original = next((row for row in projection.get("variants", []) if isinstance(row, Mapping) and row.get("name") == "original"), None)
    if original is None or not isinstance(original.get("ordered_pairs"), list):
        raise ValueError("projection metrics must contain original ordered_pairs")
    config = {
        "width": int(projection["width"]),
        "height": int(projection["height"]),
        "coordinate_mode": str(projection["coordinate_mode_requested"]),
        "camera_height": float(projection["camera_height"]),
    }
    payload = run_action_library(original["ordered_pairs"], expert_assertion=assertion, projection_config=config)
    payload.update(
        {
            "case_name": "task218_ann3741",
            "visual_checkpoint": dict(ledger["manual_visual_review"]),
            "source_artifacts": {
                "expert_assertion": _source(assertion_path),
                "projection_metrics": _source(projection_path),
                "m15_27_1": _source(m1527_path),
                "optimization_trace_ledger": _source(ledger_path),
            },
        }
    )
    return payload


def render_markdown(payload: Mapping[str, Any]) -> str:
    lines = [
        "# M15.28 Semantic Action Library Expansion v1 — task218_ann3741",
        "",
        f"- Manual-review candidate available: `{payload['overall_verdict']['manual_review_candidate_available']}`",
        "- Automatic fix claimed: `False`",
        "- Every selected candidate requires visual review.",
        f"- Allowed 5-6 short-wall deficit increase: `{payload['search_config']['allowed_short_wall_deficit_band']}`",
        f"- Secondary 2-3 window enabled: `{payload['secondary_window']['enabled']}`",
        "",
        "## Portfolio",
        "",
    ]
    for name, bucket in payload["portfolio_candidates"].items():
        candidate = bucket["candidate"]
        lines.append(
            f"- `{name}`: `{candidate['candidate_id']}` ({candidate['action_family']})"
            if candidate
            else f"- `{name}`: none — {bucket['reason']}"
        )
    lines.extend(
        [
            "",
            "## Strict top 5",
            "",
            "| candidate | family | primary 6-7 | short deficit delta | movement | manual review |",
            "|---|---|---:|---:|---:|---|",
        ]
    )
    for row in payload["top_candidates"]:
        score = row["score_breakdown"]
        lines.append(
            f"| {row['candidate_id']} | {row['action_family']} | {score['primary_edge_6_7_residual']:.6f} | "
            f"{score['allowed_short_wall_deficit_delta']:.6f} | {score['movement_l1_ls_percent']:.6f} | {row['manual_review_candidate']} |"
        )
    lines.extend(["", "Expert-side deterministic dry-run only; no automatic application, annotation mutation, routing input, or formal artifact.", ""])
    return "\n".join(lines)


def run(
    out_dir: Path = DEFAULT_OUT_DIR,
    *,
    assertion_path: Path = DEFAULT_ASSERTION,
    projection_path: Path = DEFAULT_PROJECTION,
    m1527_path: Path = DEFAULT_M1527,
    ledger_path: Path = DEFAULT_LEDGER,
) -> dict[str, Path]:
    payload = build_payload(assertion_path=assertion_path, projection_path=projection_path, m1527_path=m1527_path, ledger_path=ledger_path)
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = out_dir / "semantic_action_search.json"
    report_path = out_dir / "semantic_action_search.md"
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    report_path.write_text(render_markdown(payload), encoding="utf-8")
    return {"json": json_path, "report": report_path}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    parser.add_argument("--ledger", type=Path, default=DEFAULT_LEDGER)
    args = parser.parse_args()
    for kind, path in run(args.out_dir, ledger_path=args.ledger).items():
        print(f"{kind}: {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
