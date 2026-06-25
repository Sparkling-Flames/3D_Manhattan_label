"""Generate three fixed audit-only candidates for corrected GT 4543gt."""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import sys
from pathlib import Path
from typing import Any, Mapping, Sequence

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tools.paper_a_manhattan.manhattan_case_contract import build_case_contract
from tools.paper_a_manhattan.manhattan_constrained_hypothesis_evaluator import (
    evaluate_hypothesis,
)
from tools.paper_a_manhattan.run_local_3d_projection_review import (
    build_projection_variant,
    run_local_review,
)


SCHEMA_VERSION = "hrc_c6_5a_6_candidate_dry_run_v1"
CASE_NAME = "task238_ann2389_4543gt"
SOURCE_PROJECTION = Path(
    "analysis_results/paper_a_manhattan/gt_correction_audit/"
    "task238_ann2389_4543gt/corrected_gt_projection_metrics_4543gt.json"
)
SOURCE_SNAPSHOT = Path(
    "analysis_results/paper_a_manhattan/gt_correction_audit/"
    "task238_ann2389_4543gt/corrected_gt_annotation_4543gt.json"
)
DEFAULT_OUT_DIR = Path(
    "analysis_results/paper_a_manhattan/hypothesis_ranking_core/"
    "c6_5a_6_candidate_dry_run/task238_ann2389_4543gt"
)
DEFAULT_PREVIEW_DIR = Path(
    "analysis_results/paper_a_manhattan/hypothesis_local_review/"
    "task238_ann2389_4543gt"
)
SAFETY_BOUNDARY = {
    "audit_only": True,
    "active_runner_role": False,
    "ranking_role": False,
    "portfolio_role": False,
    "accepted": False,
    "downstream_recommendation": False,
    "annotation_patch_generated": False,
    "annotation_writeback": False,
}
STATUS_BOUNDARIES = {
    "c6_5b": "blocked",
    "c3_shadow_expansion": "blocked",
    "c7_optimizer": "blocked",
    "c9_learning": "blocked",
    "c10_ranker": "blocked",
}


def _load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write_json(path: Path, payload: Any) -> None:
    path.write_bytes(
        (json.dumps(payload, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    )


def _local_server_root(out_dir: Path) -> Path | None:
    try:
        out_dir.resolve().relative_to(REPO_ROOT.resolve())
    except ValueError:
        return None
    return REPO_ROOT


def _change(
    pair: Mapping[str, Any],
    *,
    top_x: float | None = None,
    bottom_x: float | None = None,
    top_y: float | None = None,
    bottom_y: float | None = None,
) -> dict[str, Any]:
    values = {
        "top_x": (pair["top"]["x"], top_x),
        "bottom_x": (pair["bottom"]["x"], bottom_x),
        "top_y": (pair["top"]["y"], top_y),
        "bottom_y": (pair["bottom"]["y"], bottom_y),
    }
    fields = {
        name: {
            "before": float(before),
            "after": float(after),
            "delta": float(after) - float(before),
            "changed": True,
        }
        for name, (before, after) in values.items()
        if after is not None and float(after) != float(before)
    }
    return {"effective_pair_index": 2, "fields": fields}


def _apply(
    baseline_pairs: Sequence[Mapping[str, Any]],
    change: Mapping[str, Any],
) -> list[dict[str, Any]]:
    pairs = copy.deepcopy(list(baseline_pairs))
    pair = pairs[1]
    mapping = {
        "top_x": ("top", "x"),
        "bottom_x": ("bottom", "x"),
        "top_y": ("top", "y"),
        "bottom_y": ("bottom", "y"),
    }
    for field, values in change["fields"].items():
        endpoint, axis = mapping[field]
        pair[endpoint][axis] = float(values["after"])
    return pairs


def _candidate_specs(
    baseline_pairs: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    pair = baseline_pairs[1]
    return [
        {
            "candidate_id": "c6_5a_6_candidate_0001",
            "action_family": "shift_pair2_column_left_0_75",
            "coordinate_changes": [
                _change(
                    pair,
                    top_x=float(pair["top"]["x"]) - 0.75,
                    bottom_x=float(pair["bottom"]["x"]) - 0.75,
                )
            ],
        },
        {
            "candidate_id": "c6_5a_6_candidate_0002",
            "action_family": "shift_pair2_vertical_band_down_0_75",
            "coordinate_changes": [
                _change(
                    pair,
                    top_y=float(pair["top"]["y"]) + 0.75,
                    bottom_y=float(pair["bottom"]["y"]) + 0.75,
                )
            ],
        },
        {
            "candidate_id": "c6_5a_6_candidate_0003",
            "action_family": "shift_pair2_vertical_band_up_0_75",
            "coordinate_changes": [
                _change(
                    pair,
                    top_y=float(pair["top"]["y"]) - 0.75,
                    bottom_y=float(pair["bottom"]["y"]) - 0.75,
                )
            ],
        },
    ]


def build_payload() -> dict[str, Any]:
    source = _load(SOURCE_PROJECTION)
    if source.get("case_name") != CASE_NAME or source.get("pair_count") != 4:
        raise ValueError("corrected GT projection identity/pair count mismatch")
    baseline = source["variants"][0]
    baseline_pairs = baseline["ordered_pairs"]
    contract = build_case_contract(
        baseline_pairs,
        {
            "candidate_window": [2],
            "movable_fields_by_pair": {"2": ["x", "top_y", "bottom_y"]},
        },
        baseline["metrics"],
    )
    candidates = []
    for display_order, spec in enumerate(_candidate_specs(baseline_pairs), start=1):
        change = spec["coordinate_changes"][0]
        candidate_pairs = _apply(baseline_pairs, change)
        variant = build_projection_variant(
            spec["candidate_id"],
            candidate_pairs,
            width=1024,
            height=512,
            coordinate_mode="ls_percent",
            camera_height=1.6,
        )
        evaluation = evaluate_hypothesis(
            baseline,
            variant,
            baseline_pairs,
            candidate_pairs,
            contract,
            legacy_trial_allowed=False,
        )
        candidates.append(
            {
                **spec,
                "display_order": display_order,
                "ordered_pairs": candidate_pairs,
                "pair_count": len(candidate_pairs),
                "topology_preserved": len(candidate_pairs) == len(baseline_pairs) == 4,
                "short_wall_assumption": False,
                "keep_distinct_assumption": False,
                "candidate_specific_c4": {
                    "availability": "unavailable",
                    "candidate_preference_authorized": False,
                    "reason": "no candidate-specific image evidence or projection delta",
                },
                "diagnostics": {
                    "movement_cost": evaluation["movement_edit_cost"],
                    "height_consistency": evaluation["height_consistency"],
                    "wall_residual_max": evaluation["manhattan_feasibility"][
                        "wall_residual_max"
                    ],
                    "wall_residual_median": evaluation["manhattan_feasibility"][
                        "wall_residual_median"
                    ],
                    "turn_residual_max": evaluation["manhattan_feasibility"][
                        "turn_residual_max"
                    ],
                    "turn_residual_median": evaluation["manhattan_feasibility"][
                        "turn_residual_median"
                    ],
                    "self_intersection": variant["metrics"]["floorprint"][
                        "self_intersection"
                    ],
                    "short_wall_count": variant["metrics"]["floorprint"]["summary"][
                        "short_wall_count"
                    ],
                    "hard_gate_passed": evaluation["feasibility"][
                        "hard_gate_passed"
                    ],
                    "decision_class": evaluation["decision_class"],
                },
                "accepted": False,
                "downstream_recommendation": False,
            }
        )
    return {
        "schema_version": SCHEMA_VERSION,
        "case_name": CASE_NAME,
        "source_artifacts": {
            "corrected_projection": {
                "path": SOURCE_PROJECTION.as_posix(),
                "sha256": _sha256(SOURCE_PROJECTION),
                "pair_count": 4,
            },
            "corrected_gt": {
                "path": SOURCE_SNAPSHOT.as_posix(),
                "sha256": _sha256(SOURCE_SNAPSHOT),
            },
        },
        "generation_mode": "fixed_finite_audit_probes_no_search",
        "candidate_count": len(candidates),
        "candidate_set": candidates,
        "top_candidates": [
            {
                "display_order": row["display_order"],
                "candidate_id": row["candidate_id"],
                "action_family": row["action_family"],
                "movement_l1_normalized": row["diagnostics"]["movement_cost"][
                    "movement_l1_normalized"
                ],
                "height_outlier_l1": row["diagnostics"]["height_consistency"][
                    "height_outlier_l1"
                ],
                "wall_residual_max": row["diagnostics"]["wall_residual_max"],
                "turn_residual_max": row["diagnostics"]["turn_residual_max"],
            }
            for row in candidates
        ],
        "candidate_preference_authorized": False,
        "preference_status": "manual_comparison_only_no_authorized_preference",
        "generated_proposal": False,
        "generated_geometry_search_result": False,
        "safety_boundary": SAFETY_BOUNDARY,
        "status_boundaries": STATUS_BOUNDARIES,
    }


def _review_manifest(payload: Mapping[str, Any]) -> dict[str, Any]:
    snapshot = _load(SOURCE_SNAPSHOT)
    return {
        "schema_version": "hrc_c6_5a_6_local_review_manifest_v1",
        "case_name": CASE_NAME,
        "source_image": snapshot["image"],
        "ordered_pairs": _load(SOURCE_PROJECTION)["variants"][0]["ordered_pairs"],
        "candidates": [
            {
                "candidate_id": row["candidate_id"],
                "family": row["action_family"],
                "action_family": row["action_family"],
                "coordinate_changes": row["coordinate_changes"],
                "decision_class": row["diagnostics"]["decision_class"],
                "hard_gate": False,
                "assertion_violations": [],
                "manual_review_candidate": True,
                "automatic_fix_claimed": False,
                "source_stage": "c6_5a_6_fixed_candidate_dry_run",
                "review_role": f"diagnostic_{row['display_order']}",
                "selection_reason": "fixed_display_order_not_preference",
                "preferred_panel": True,
                "short_wall_edges_after": [],
                "evidence_status": "unavailable",
                "evidence_warning": (
                    "candidate-specific C4 unavailable; visual comparison only"
                ),
            }
            for row in payload["candidate_set"]
        ],
        "safety_boundary": SAFETY_BOUNDARY,
    }


def run(
    out_dir: Path = DEFAULT_OUT_DIR,
    preview_dir: Path = DEFAULT_PREVIEW_DIR,
) -> dict[str, Path]:
    payload = build_payload()
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = out_dir / "hrc_c6_5a_6_candidate_dry_run.json"
    md_path = out_dir / "hrc_c6_5a_6_candidate_dry_run.md"
    manifest_path = out_dir / "local_review_manifest.json"
    _write_json(json_path, payload)
    _write_json(manifest_path, _review_manifest(payload))
    md_path.write_bytes(
        (
            "# HRC C6.5a.6 Candidate Dry-run\n\n"
            "- Case: `task238_ann2389_4543gt`\n"
            f"- Candidate count: `{payload['candidate_count']}`\n"
            "- Generation: `fixed_finite_audit_probes_no_search`\n"
            "- Candidate preference authorized: `false`\n"
            "- Accepted/downstream/writeback: `false/false/false`\n"
            "- C6.5b/C3/C7/C9/C10: `blocked`\n\n"
            "| order | candidate | family | movement | height L1 | wall max | turn max |\n"
            "|---:|---|---|---:|---:|---:|---:|\n"
            + "\n".join(
                f"| {row['display_order']} | {row['candidate_id']} | "
                f"{row['action_family']} | {row['movement_l1_normalized']:.6f} | "
                f"{row['height_outlier_l1']:.6f} | "
                f"{row['wall_residual_max']:.6f} | "
                f"{row['turn_residual_max']:.6f} |"
                for row in payload["top_candidates"]
            )
            + "\n"
        ).encode("utf-8")
    )
    preview_paths = run_local_review(
        input_path=manifest_path,
        candidate_json=manifest_path,
        candidate_limit=payload["candidate_count"],
        out_dir=preview_dir,
        image_root=Path("data/mp3d_layout/img_v"),
        case_name=CASE_NAME,
        width=1024,
        height=512,
        coordinate_mode="ls_percent",
        camera_height=1.6,
        local_server_root=_local_server_root(preview_dir),
    )
    for path in preview_paths.values():
        path.write_bytes(path.read_bytes().replace(b"\r\n", b"\n"))
    return {
        "json": json_path,
        "markdown": md_path,
        "review_manifest": manifest_path,
        **{f"preview_{name}": path for name, path in preview_paths.items()},
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    parser.add_argument("--preview-dir", type=Path, default=DEFAULT_PREVIEW_DIR)
    args = parser.parse_args(argv)
    print(run(args.out_dir, args.preview_dir)["json"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
