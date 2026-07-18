from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path
from typing import Any

_PROJECT_ROOT = Path(__file__).resolve().parents[3]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from tools.thesis_main.analysis.c1_live_collection_monitor import read_csv, safe, truthy, write_csv, write_json
from tools.thesis_main.analysis.vfinal_artifact_utils import sha256_file


PRECISION_FIELDS = [
    "worker_id", "current_support", "current_ci_half_width", "target_ci_half_width",
    "additional_blocks", "ordinary_tasks", "stress_tasks", "projected_ci_half_width",
    "precision_target_met", "routing_eligibility", "unmet_reason", "design_manifest_sha256",
]


def _number(row: dict[str, str], *fields: str) -> float | None:
    for field in fields:
        value = safe(row.get(field))
        if value:
            return float(value)
    return None


def build_precision_plan(
    worker_rows: list[dict[str, str]],
    *,
    target_half_width: float,
    max_additional_blocks: int,
    manifest_sha: str,
) -> list[dict[str, Any]]:
    out = []
    for row in sorted(worker_rows, key=lambda value: safe(value.get("worker_id"))):
        worker = safe(row.get("worker_id"))
        support_raw = _number(row, "support", "n_support", "n_calib_completed")
        half_width = _number(row, "ci_half_width", "r_u_h")
        blocked = truthy(row.get("process_blocker")) or truthy(row.get("independence_blocker"))
        blocks = 0
        projected = half_width
        reason = ""
        if blocked:
            reason = "process_or_independence_blocker"
        elif not worker or support_raw is None or support_raw <= 0 or half_width is None:
            reason = "precision_not_evaluable"
        else:
            support = int(support_raw)
            while projected > target_half_width and blocks < max_additional_blocks:
                blocks += 1
                projected = half_width * math.sqrt(support / (support + 2 * blocks))
            if projected > target_half_width:
                reason = "target_not_met_at_frozen_cap"
        met = not reason and projected is not None and projected <= target_half_width
        out.append({
            "worker_id": worker,
            "current_support": "" if support_raw is None else int(support_raw),
            "current_ci_half_width": "" if half_width is None else half_width,
            "target_ci_half_width": target_half_width,
            "additional_blocks": blocks,
            "ordinary_tasks": blocks,
            "stress_tasks": blocks,
            "projected_ci_half_width": "" if projected is None else projected,
            "precision_target_met": met,
            "routing_eligibility": "eligible" if met else "uncertain_fallback_global",
            "unmet_reason": reason,
            "design_manifest_sha256": manifest_sha,
        })
    return out


def materialize(
    worker_profile_csv: Path,
    design_manifest: Path,
    output_dir: Path,
    *,
    c2b_summary: Path | None = None,
    input_status: str = "dry_run",
) -> dict[str, Any]:
    manifest = json.loads(design_manifest.read_text(encoding="utf-8"))
    if manifest.get("manifest_version") != "c2_design_v1":
        raise ValueError("unsupported C2 design manifest version")
    manifest_sha = sha256_file(design_manifest)
    expected = manifest.get("input_sha256") or {}
    actual_profile_sha = sha256_file(worker_profile_csv)
    binding_valid = expected.get("worker_profile_csv") == actual_profile_sha
    c2b_valid = input_status != "formal"
    if c2b_summary:
        c2b = json.loads(c2b_summary.read_text(encoding="utf-8"))
        c2b_valid = (
            c2b.get("design_manifest_sha256") == manifest_sha
            and bool(c2b.get("c2b_design_ready"))
            and (
                input_status != "formal"
                or c2b.get("post_c2b_worker_profile_sha256") == actual_profile_sha
            )
        )
    precision = manifest.get("precision") or {}
    target = float(precision["target_ci_half_width"])
    max_blocks = int(precision["max_additional_blocks"])
    if target <= 0 or max_blocks < 0:
        raise ValueError("precision target must be positive and max_additional_blocks non-negative")
    if not binding_valid or not c2b_valid:
        if input_status == "formal":
            raise ValueError("stale_or_unbound_c2a_rp_dependency")
    rows = build_precision_plan(
        read_csv(worker_profile_csv),
        target_half_width=target,
        max_additional_blocks=max_blocks,
        manifest_sha=manifest_sha,
    )
    output_dir.mkdir(parents=True, exist_ok=True)
    write_csv(output_dir / "precision_plan_C2A_RP.csv", rows, PRECISION_FIELDS)
    summary = {
        "design_manifest_sha256": manifest_sha,
        "worker_profile_sha256": actual_profile_sha,
        "dependency_binding_valid": binding_valid and c2b_valid,
        "n_workers": len(rows),
        "n_workers_with_precision_additions": sum(int(row["additional_blocks"]) > 0 for row in rows),
        "n_workers_unmet_at_cap": sum(bool(row["unmet_reason"]) for row in rows),
        "c2a_rp_ready": binding_valid and c2b_valid and bool(rows),
        "candidate_only": input_status != "formal",
        "launch_ready": input_status == "formal" and binding_valid and c2b_valid and bool(rows),
        "searches_new_risk_family": False,
        "modifies_c1": False,
    }
    write_json(output_dir / "precision_plan_C2A_RP.summary.json", summary)
    return summary


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Materialize C2-A-RP precision-only completion from post-C2-B worker uncertainty.")
    parser.add_argument("--worker-profile-csv", type=Path, required=True)
    parser.add_argument("--design-manifest", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--c2b-summary", type=Path)
    parser.add_argument("--input-status", choices=("dry_run", "formal"), default="dry_run")
    args = parser.parse_args(argv)
    print(json.dumps(materialize(
        args.worker_profile_csv, args.design_manifest, args.output_dir,
        c2b_summary=args.c2b_summary, input_status=args.input_status,
    ), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
