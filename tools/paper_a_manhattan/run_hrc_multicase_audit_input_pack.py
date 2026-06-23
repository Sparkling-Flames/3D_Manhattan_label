"""Materialize audit-only HRC multi-case candidate input packs."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any, Mapping, Sequence


SCHEMA_VERSION = "hrc_multicase_audit_input_pack_v1"
ROOT = Path("analysis_results/paper_a_manhattan")
DEFAULT_OUT_DIR = ROOT / "hypothesis_ranking_core/multicase_audit_input_pack"

CASES = {
    "task218_ann2369": {
        "provenance": "existing_artifact_only",
        "candidate_artifact": ROOT
        / "single_image_manual_test/latest_gt_checked/m1518_3_candidate_semantics/task218_ann2369_m1518_3_candidate_semantics_output.json",
        "projection_artifact": ROOT / "local_3d_projection/task218_ann2369/projection_metrics.json",
    },
    "task238_ann2389": {
        "provenance": "existing_artifact_only",
        "candidate_artifact": ROOT
        / "single_image_manual_test/latest_gt_checked/m1518_3_candidate_semantics/task238_ann2389_m1518_3_candidate_semantics_output.json",
        "projection_artifact": ROOT / "local_3d_projection/task238_ann2389/projection_metrics.json",
    },
    "gt75_task533": {
        "provenance": "verified_order_record_only",
        "candidate_artifact": ROOT
        / "single_image_manual_test/task533_gt75/m1518_3_candidate_semantics/candidate_b_annotation_3425_m1518_3_candidate_semantics_output.json",
        "projection_artifact": None,
    },
    "ordinary_compatible": {
        "provenance": "fixture_only",
        "candidate_artifact": Path("tests/fixtures/paper_a_manhattan/single_image_assist_pack_v1.json"),
        "projection_artifact": None,
    },
}


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _artifact(path: Path | None) -> dict[str, Any] | None:
    if path is None:
        return None
    return {
        "path": path.as_posix(),
        "sha256": _sha256(path),
    }


def _candidate_id(row: Mapping[str, Any], rank: int) -> str:
    return str(
        row.get("candidate_id")
        or f"{row.get('operation') or row.get('candidate_family') or 'candidate'}_rank_{rank}"
    )


def _candidate_set(payload: Mapping[str, Any]) -> list[dict[str, Any]]:
    rows = payload.get("height_reproject_candidate_rows") or []
    out = []
    for rank, row in enumerate(rows, 1):
        out.append(
            {
                "candidate_id": _candidate_id(row, rank),
                "source_candidate_rank": row.get("candidate_rank", rank),
                "action_family": row.get("operation") or row.get("candidate_family"),
                "candidate_decision": row.get("candidate_decision"),
                "source_schema_version": row.get("candidate_schema_version"),
                "target_pair_index": row.get("target_pair_index"),
                "existing_artifact_only": True,
                "audit_only": True,
                "active_runner_role": False,
                "accepted": False,
                "downstream_recommendation": False,
                "annotation_writeback": False,
                "raw_candidate_row": row,
            }
        )
    return out


def build_case_pack(case_name: str) -> dict[str, Any]:
    spec = CASES[case_name]
    candidate_artifact = spec["candidate_artifact"]
    source_artifacts = {"candidate_artifact": _artifact(candidate_artifact)}
    projection_artifact = _artifact(spec["projection_artifact"])
    if projection_artifact:
        source_artifacts["projection_artifact"] = projection_artifact

    payload = json.loads(candidate_artifact.read_text(encoding="utf-8"))
    candidates = _candidate_set(payload)
    status = "available" if candidates else "unavailable"
    unavailable_reason = None if candidates else "no existing non-baseline candidate rows found; baseline-only/no-op candidates are not rankable"

    return {
        "schema_version": SCHEMA_VERSION,
        "case_name": case_name,
        "source_artifacts": source_artifacts,
        "candidate_input_status": status,
        "unavailable_reason": unavailable_reason,
        "candidate_set": candidates,
        "candidate_review_geometry": {
            "source": candidate_artifact.as_posix(),
            "ordered_pairs_available": isinstance(payload.get("ordered_pairs"), list),
            "projection_variants_reference": projection_artifact,
        },
        "case_contract": None,
        "contract_status": "not_materialized_for_input_pack",
        "provenance": spec["provenance"],
        "audit_only": True,
        "active_runner_role": False,
        "accepted": False,
        "downstream_recommendation": False,
        "annotation_writeback": False,
    }


def build_summary(packs: Mapping[str, Mapping[str, Any]]) -> dict[str, Any]:
    available = [
        name for name, pack in packs.items() if pack["candidate_input_status"] == "available"
    ]
    unavailable = [
        name for name, pack in packs.items() if pack["candidate_input_status"] == "unavailable"
    ]
    baseline_only: list[str] = []
    return {
        "schema_version": SCHEMA_VERSION,
        "case_names": list(CASES),
        "available_candidate_input_cases": available,
        "unavailable_candidate_input_cases": unavailable,
        "baseline_only_cases": baseline_only,
        "ready_for_c6_3e_bucket_audit": len(available) == len(CASES),
        "audit_only": True,
        "active_runner_role": False,
        "accepted": False,
        "downstream_recommendation": False,
        "annotation_writeback": False,
        "packs": packs,
    }


def render_markdown(summary: Mapping[str, Any]) -> str:
    lines = [
        "# HRC C6.3d Multi-case Audit Input Pack",
        "",
        f"- Schema: `{summary['schema_version']}`",
        f"- Ready for C6.3e bucket audit: `{summary['ready_for_c6_3e_bucket_audit']}`",
        f"- Available: `{', '.join(summary['available_candidate_input_cases'])}`",
        f"- Unavailable: `{', '.join(summary['unavailable_candidate_input_cases'])}`",
        f"- Accepted: `{summary['accepted']}`",
        f"- Downstream recommendation: `{summary['downstream_recommendation']}`",
        "",
    ]
    for name, pack in summary["packs"].items():
        lines.append(
            f"- `{name}`: `{pack['candidate_input_status']}`; candidates={len(pack['candidate_set'])}; provenance=`{pack['provenance']}`"
        )
    lines.append("")
    return "\n".join(lines)


def run(out_dir: Path = DEFAULT_OUT_DIR) -> dict[str, Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    packs = {case_name: build_case_pack(case_name) for case_name in CASES}
    paths: dict[str, Path] = {}
    for case_name, pack in packs.items():
        case_dir = out_dir / case_name
        case_dir.mkdir(parents=True, exist_ok=True)
        path = case_dir / "hrc_audit_input_pack.json"
        path.write_text(json.dumps(pack, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        paths[case_name] = path

    summary = build_summary(packs)
    summary_json = out_dir / "hrc_multicase_audit_input_pack_summary.json"
    summary_md = out_dir / "hrc_multicase_audit_input_pack_summary.md"
    summary_json.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    summary_md.write_text(render_markdown(summary), encoding="utf-8")
    paths["summary_json"] = summary_json
    paths["summary_md"] = summary_md
    return paths


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    args = parser.parse_args(argv)
    print(run(args.out_dir)["summary_json"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
