"""Audit whether existing HRC candidates are adequate for multi-case C6 review."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any, Mapping, Sequence

from tools.paper_a_manhattan.run_manhattan_hypothesis_ranking_core import build_payload


SCHEMA_VERSION = "hrc_candidate_adequacy_audit_v1"
ROOT = Path("analysis_results/paper_a_manhattan")
INPUT_PACK_SUMMARY = (
    ROOT
    / "hypothesis_ranking_core/multicase_audit_input_pack/hrc_multicase_audit_input_pack_summary.json"
)
DEFAULT_OUT_DIR = ROOT / "hypothesis_ranking_core/candidate_adequacy_audit"
ALLOWED_NEXT_STEPS = {
    "collect/materialize missing real candidate source for ordinary_compatible",
    "design shadow-only global hypothesis probe specification",
    "C2/C5 diagnostics hardening",
}


def _changed(before: Any, after: Any) -> bool:
    return isinstance(before, (int, float)) and isinstance(after, (int, float)) and before != after


def _distribution(rows: Sequence[Mapping[str, Any]], field: str) -> dict[str, int]:
    return dict(Counter(str(row.get(field) or "unknown") for row in rows))


def _variable_coverage(rows: Sequence[Mapping[str, Any]]) -> dict[str, bool]:
    coverage = {
        "x_change": False,
        "top_y_change": False,
        "bottom_y_change": False,
        "floor_depth_change": False,
        "topology_change": False,
        "global_layout_change": False,
    }
    for row in rows:
        raw = row.get("raw_candidate_row") or row
        family = str(row.get("action_family") or raw.get("operation") or raw.get("candidate_family") or "")
        x_family = any(token in family for token in ("_x", "x_", "align_x", "block_x"))
        coverage["x_change"] |= _changed(raw.get("top_x_before"), raw.get("top_x_after")) or _changed(
            raw.get("bottom_x_before"), raw.get("bottom_x_after")
        ) or x_family
        coverage["top_y_change"] |= _changed(raw.get("top_y_before"), raw.get("top_y_after")) or "top_y" in family
        coverage["bottom_y_change"] |= _changed(raw.get("bottom_y_before"), raw.get("bottom_y_after"))
        coverage["floor_depth_change"] |= "floor_depth" in family or "depth" in family
        coverage["topology_change"] |= "topology" in family or "merge" in family
        coverage["global_layout_change"] |= "global" in family or "azimuth_translate" in family
    return coverage


def _locality_coverage(rows: Sequence[Mapping[str, Any]]) -> dict[str, bool]:
    local_only = multi_pair = global_change = False
    for row in rows:
        family = str(row.get("action_family") or "")
        changed_pairs = row.get("changed_pair_indices") or [row.get("target_pair_index")]
        changed_pairs = [item for item in changed_pairs if item is not None]
        local_only |= len(changed_pairs) == 1
        multi_pair |= len(changed_pairs) > 1 or "edge_" in family
        global_change |= "global" in family or "azimuth_translate" in family
    return {"local_only": local_only, "multi_pair": multi_pair, "global": global_change}


def _risk_flags(
    *,
    candidate_input_status: str,
    candidate_count: int,
    variable_coverage: Mapping[str, bool],
    case_name: str,
) -> dict[str, bool]:
    has_geometry_diversity = any(
        variable_coverage[name]
        for name in ("x_change", "floor_depth_change", "topology_change", "global_layout_change")
    )
    height_only = (
        variable_coverage["top_y_change"]
        or variable_coverage["bottom_y_change"]
    ) and not has_geometry_diversity
    no_nonbaseline = candidate_count == 0 or candidate_input_status != "available"
    return {
        "height_only_candidates": height_only,
        "no_geometry_diversity": candidate_count > 0 and not has_geometry_diversity,
        "no_global_candidate": not variable_coverage["global_layout_change"],
        "baseline_only": False,
        "no_nonbaseline_candidate": no_nonbaseline,
        "ordinary_compatible_missing_candidate_source": case_name == "ordinary_compatible" and no_nonbaseline,
        "hard_case_candidate_space_too_narrow": height_only or no_nonbaseline,
    }


def _case_summary(
    *,
    case_name: str,
    candidate_input_status: str,
    rows: Sequence[Mapping[str, Any]],
    has_projection_metrics: bool,
    has_case_contract: bool,
    has_constrained_evaluation: bool,
    rankable_by_current_hrc: bool,
) -> dict[str, Any]:
    variable_coverage = _variable_coverage(rows)
    candidate_count = len(rows)
    return {
        "case_name": case_name,
        "candidate_input_status": candidate_input_status,
        "candidate_count": candidate_count,
        "action_family_distribution": _distribution(rows, "action_family"),
        "candidate_decision_distribution": _distribution(rows, "candidate_decision"),
        "variable_coverage": variable_coverage,
        "locality_coverage": _locality_coverage(rows),
        "readiness": {
            "has_projection_metrics": has_projection_metrics,
            "has_case_contract": has_case_contract,
            "has_constrained_evaluation": has_constrained_evaluation,
            "rankable_by_current_HRC": rankable_by_current_hrc,
        },
        "risk_flags": _risk_flags(
            candidate_input_status=candidate_input_status,
            candidate_count=candidate_count,
            variable_coverage=variable_coverage,
            case_name=case_name,
        ),
        "audit_only": True,
        "accepted": False,
        "downstream_recommendation": False,
        "annotation_writeback": False,
    }


def _task3741_summary() -> dict[str, Any]:
    core = build_payload()
    rows = list(core["candidate_set"])
    return _case_summary(
        case_name="task218_ann3741",
        candidate_input_status="available",
        rows=rows,
        has_projection_metrics=True,
        has_case_contract=True,
        has_constrained_evaluation=True,
        rankable_by_current_hrc=True,
    )


def _pack_case_summary(case_name: str, pack: Mapping[str, Any]) -> dict[str, Any]:
    projection = pack.get("source_artifacts", {}).get("projection_artifact")
    return _case_summary(
        case_name=case_name,
        candidate_input_status=str(pack["candidate_input_status"]),
        rows=list(pack.get("candidate_set") or []),
        has_projection_metrics=bool(projection),
        has_case_contract=bool(pack.get("case_contract")),
        has_constrained_evaluation=False,
        rankable_by_current_hrc=False,
    )


def _missing_dimensions(cases: Mapping[str, Mapping[str, Any]]) -> list[str]:
    missing = set()
    if cases["ordinary_compatible"]["candidate_input_status"] != "available":
        missing.add("ordinary_compatible_real_candidate_source")
    for name, summary in cases.items():
        coverage = summary["variable_coverage"]
        if not coverage["x_change"]:
            missing.add(f"{name}:x_change")
        if not coverage["floor_depth_change"]:
            missing.add(f"{name}:floor_depth_change")
        if not coverage["topology_change"]:
            missing.add(f"{name}:topology_change")
        if not coverage["global_layout_change"]:
            missing.add(f"{name}:global_layout_change")
    return sorted(missing)


def build_audit_payload(input_pack_summary: Path = INPUT_PACK_SUMMARY) -> dict[str, Any]:
    pack_summary = json.loads(input_pack_summary.read_text(encoding="utf-8"))
    cases = {"task218_ann3741": _task3741_summary()}
    cases.update(
        {
            name: _pack_case_summary(name, pack)
            for name, pack in pack_summary["packs"].items()
        }
    )
    missing = _missing_dimensions(cases)
    adequate_for_c6_3e = not pack_summary["unavailable_candidate_input_cases"]
    adequate_for_fix = adequate_for_c6_3e and not any(
        summary["risk_flags"]["hard_case_candidate_space_too_narrow"]
        for summary in cases.values()
    )
    recommended = (
        "collect/materialize missing real candidate source for ordinary_compatible"
        if "ordinary_compatible" in pack_summary["unavailable_candidate_input_cases"]
        else "design shadow-only global hypothesis probe specification"
    )
    assert recommended in ALLOWED_NEXT_STEPS
    return {
        "schema_version": SCHEMA_VERSION,
        "audit_name": "HRC C6.4 candidate adequacy audit",
        "source_input_pack_summary": input_pack_summary.as_posix(),
        "generated_new_candidates": False,
        "active_runner_changed": False,
        "ranking_changed": False,
        "c3_changed": False,
        "audit_only": True,
        "accepted": False,
        "downstream_recommendation": False,
        "annotation_writeback": False,
        "cases": cases,
        "adequate_for_c6_3e_bucket_audit": adequate_for_c6_3e,
        "adequate_for_hard_case_fix_claim": adequate_for_fix,
        "missing_candidate_dimensions": missing,
        "recommended_next_step": recommended,
    }


def render_markdown(payload: Mapping[str, Any]) -> str:
    lines = [
        "# HRC C6.4 Candidate Adequacy Audit",
        "",
        f"- Schema: `{payload['schema_version']}`",
        f"- Adequate for C6.3e bucket audit: `{payload['adequate_for_c6_3e_bucket_audit']}`",
        f"- Adequate for hard-case fix claim: `{payload['adequate_for_hard_case_fix_claim']}`",
        f"- Recommended next step: `{payload['recommended_next_step']}`",
        f"- Accepted: `{payload['accepted']}`",
        f"- Downstream recommendation: `{payload['downstream_recommendation']}`",
        "",
        "## Case summaries",
        "",
    ]
    for name, summary in payload["cases"].items():
        lines.append(
            f"- `{name}`: status=`{summary['candidate_input_status']}`, candidates={summary['candidate_count']}, actions={summary['action_family_distribution']}"
        )
    lines.extend(["", "## Missing candidate dimensions", ""])
    for item in payload["missing_candidate_dimensions"]:
        lines.append(f"- `{item}`")
    lines.append("")
    return "\n".join(lines)


def run(out_dir: Path = DEFAULT_OUT_DIR) -> dict[str, Path]:
    payload = build_audit_payload()
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = out_dir / "hrc_candidate_adequacy_audit.json"
    md_path = out_dir / "hrc_candidate_adequacy_audit.md"
    json_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    md_path.write_text(render_markdown(payload), encoding="utf-8")
    return {"json": json_path, "markdown": md_path}


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    args = parser.parse_args(argv)
    print(run(args.out_dir)["json"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
