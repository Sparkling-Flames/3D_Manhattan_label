"""Bind completed C2-B submissions to the post-C2-B worker profile consumed by C2-A-RP."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from tools.thesis_main.analysis.vfinal_artifact_utils import sha256_file


def materialize(
    submissions_csv: Path,
    post_profile_csv: Path,
    profile_manifest: Path,
    design_summary: Path,
    output_summary: Path,
) -> dict[str, Any]:
    manifest = json.loads(profile_manifest.read_text(encoding="utf-8"))
    if manifest.get("manifest_version") != "c2b_post_profile_v1":
        raise ValueError("unsupported C2-B post-profile manifest")
    design = json.loads(design_summary.read_text(encoding="utf-8"))
    if not design.get("c2b_design_ready"):
        raise ValueError("C2-B design was not ready")

    actual = {
        "c2b_submissions_csv": sha256_file(submissions_csv),
        "post_c2b_worker_profile_csv": sha256_file(post_profile_csv),
        "c2b_design_summary": sha256_file(design_summary),
    }
    declared = {
        **(manifest.get("input_sha256") or {}),
        **(manifest.get("output_sha256") or {}),
    }
    for name, digest in actual.items():
        if declared.get(name) != digest:
            raise ValueError(f"stale_or_unbound:{name}")

    summary = {
        "closeout_version": "c2b_closeout_v1",
        "c2b_design_ready": True,
        "c2b_closeout_ready": True,
        "design_manifest_sha256": design.get("design_manifest_sha256"),
        "c2b_design_summary_path": str(design_summary),
        "c2b_design_summary_sha256": actual["c2b_design_summary"],
        "c2b_submissions_path": str(submissions_csv),
        "c2b_submissions_sha256": actual["c2b_submissions_csv"],
        "post_c2b_worker_profile_path": str(post_profile_csv),
        "post_c2b_worker_profile_sha256": actual["post_c2b_worker_profile_csv"],
        "post_c2b_profile_manifest_path": str(profile_manifest),
        "post_c2b_profile_manifest_sha256": sha256_file(profile_manifest),
    }
    output_summary.parent.mkdir(parents=True, exist_ok=True)
    output_summary.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return summary


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Materialize the formal C2-B closeout SHA chain.")
    parser.add_argument("--submissions-csv", type=Path, required=True)
    parser.add_argument("--post-profile-csv", type=Path, required=True)
    parser.add_argument("--profile-manifest", type=Path, required=True)
    parser.add_argument("--design-summary", type=Path, required=True)
    parser.add_argument("--output-summary", type=Path, required=True)
    args = parser.parse_args(argv)
    print(json.dumps(materialize(
        args.submissions_csv, args.post_profile_csv, args.profile_manifest,
        args.design_summary, args.output_summary,
    ), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
