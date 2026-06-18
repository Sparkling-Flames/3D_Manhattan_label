"""CLI for the M15.20 local candidate report."""

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

from tools.paper_a_manhattan.manhattan_m1520_local_candidate_search import (  # noqa: E402
    CORE_WINDOW,
    EXPANDED_WINDOW,
    run_local_candidate_search,
)
from tools.paper_a_manhattan.run_local_3d_projection_review import (  # noqa: E402
    extract_ordered_pairs,
)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _fmt(value: Any, digits: int = 3) -> str:
    if value is None:
        return "—"
    if isinstance(value, bool):
        return "yes" if value else "no"
    if isinstance(value, (int, float)):
        return f"{float(value):.{digits}f}"
    return str(value)


def render_markdown_report(payload: Mapping[str, Any]) -> str:
    lines = [
        "# M15.20 Local Candidate Report — task218_ann3741",
        "",
        "> 仅供专家本地只读审查。候选不是最终修复，不写回 Label Studio，不进入 routing 或正式 artifact。",
        "",
        "## Scope",
        "",
        f"- Local window: `{payload['scope']['local_window']}`",
        f"- Generated / retained: `{payload['candidate_generation']['generated_count']}` / `{payload['candidate_generation']['retained_count']}`",
        "- coordinate_mode: `ls_percent`（显式固定）",
        "- Hard gates: introduced self-intersection；5/6/7 collapse risk",
        "",
        "## Baseline walls",
        "",
        "| edge | residual (deg) | floor length |",
        "|---|---:|---:|",
    ]
    for row in payload["baseline"]["required_wall_residuals"]:
        lines.append(f"| {row['edge']} | {_fmt(row['residual_deg'])} | {_fmt(row['floor_wall_length'])} |")

    for row in payload["candidates"]:
        lines.extend(
            [
                "",
                f"## {row['candidate_id']} — {row['family']}",
                "",
                f"- Label: `{row['label']}`",
                f"- Changed pairs: `{row['changed_pair_indices']}`",
                f"- Score: `{_fmt(row['score'])}` (lower is better)",
                f"- Disposition: `{row['disposition']}`",
                f"- Recommend manual LS try: `{row['manual_ls_try_recommended']}`",
                f"- Height worsened / short wall / hard gate: `{row['height_worsened']}` / `{row['short_wall_after']}` / `{row['hard_gate']}`",
                f"- Unresolved required edges: `{row['unresolved_required_edges']}`",
                "",
                "### 2D coordinate changes",
                "",
                "| pair | field | before | after | delta | changed |",
                "|---:|---|---:|---:|---:|---|",
            ]
        )
        for change in row["coordinate_changes"]:
            for field, values in change["fields"].items():
                lines.append(
                    f"| {change['effective_pair_index']} | {field} | {_fmt(values['before'])} | {_fmt(values['after'])} | {_fmt(values['delta'])} | {values['changed']} |"
                )
        lines.extend(
            [
                "",
                "### 3D coordinates",
                "",
                "| pair | variant | floor (x,y,z) | ceiling (x,y,z) | wall height |",
                "|---:|---|---|---|---:|",
            ]
        )
        for variant_name in ("original", "candidate"):
            for point in row["coordinates_3d"][variant_name]:
                floor = point["floor_3d"]
                ceiling = point["ceiling_3d"]
                lines.append(
                    f"| {point['effective_pair_index']} | {variant_name} | ({_fmt(floor['x'])}, {_fmt(floor['y'])}, {_fmt(floor['z'])}) | ({_fmt(ceiling['x'])}, {_fmt(ceiling['y'])}, {_fmt(ceiling['z'])}) | {_fmt(point['wall_height'])} |"
                )
        lines.extend(
            [
                "",
                "### Required wall residuals",
                "",
                "| edge | before | after | delta | length after | present |",
                "|---|---:|---:|---:|---:|---|",
            ]
        )
        for wall in row["required_wall_residuals"]:
            lines.append(
                f"| {wall['edge']} | {_fmt(wall['before_residual_deg'])} | {_fmt(wall['after_residual_deg'])} | {_fmt(wall['delta_deg'])} | {_fmt(wall['after_floor_wall_length'])} | {wall['edge_present_after']} |"
            )
    lines.extend(
        [
            "",
            "## Interpretation boundary",
            "",
            "- `partial_neutral_review` 表示局部评分下降，但 6–7 或 7–8 仍未解决，不能视为最终修复。",
            "- topology hypothesis 只供人工理解局部顺序，不授权自动 reorder、merge 或 delete。",
            "- 所有候选均需人工结合全景与 3D 视觉判断；本报告不生成 annotation patch。",
            "",
        ]
    )
    return "\n".join(lines)


def run(
    *,
    input_path: Path,
    out_dir: Path,
    expanded_window: bool = False,
    retain_per_family: int = 3,
) -> dict[str, Path]:
    payload = json.loads(input_path.read_text(encoding="utf-8"))
    ordered_pairs, source = extract_ordered_pairs(payload)
    result = run_local_candidate_search(
        ordered_pairs,
        local_window=EXPANDED_WINDOW if expanded_window else CORE_WINDOW,
        retain_per_family=retain_per_family,
    )
    result["input_provenance"] = {
        "input_file": input_path.name,
        "input_sha256": _sha256(input_path),
        "ordered_pair_source": source,
    }
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = out_dir / "candidate_search.json"
    report_path = out_dir / "local_candidate_report.md"
    json_path.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    report_path.write_text(render_markdown_report(result), encoding="utf-8")
    return {"json": json_path, "report": report_path}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--out-dir", type=Path, required=True)
    parser.add_argument("--expanded-window", action="store_true")
    parser.add_argument("--retain-per-family", type=int, default=3)
    args = parser.parse_args()
    paths = run(
        input_path=args.input,
        out_dir=args.out_dir,
        expanded_window=args.expanded_window,
        retain_per_family=args.retain_per_family,
    )
    for kind, path in paths.items():
        print(f"{kind}: {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
