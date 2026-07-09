"""Materialize M-Anchor.3b candidates in the hypothesis_local_review 3D viewer.

This is preview/audit plumbing only. It does not change the M-Anchor.3b
solver output, does not write annotation patches, and does not authorize
ranking, portfolio, or downstream use.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any, Mapping, Sequence

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tools.paper_a_manhattan.run_local_3d_projection_review import run_local_review


SCHEMA_VERSION = "m_anchor_3b_local_3d_review_bridge_v1"
DEFAULT_IMAGE_ROOT = Path("data/mp3d_layout/img_v")
DEFAULT_AUDIT_PATH = Path(
    "analysis_results/paper_a_manhattan/m_anchor/"
    "task218_ann3741_m_anchor_3b/m_anchor_3b_local_chain_footprint_solver_audit.json"
)
DEFAULT_OUT_DIR = Path(
    "analysis_results/paper_a_manhattan/hypothesis_local_review/"
    "task218_ann3741_m_anchor_3b"
)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _repo_relative(path: Path) -> str:
    try:
        return path.resolve().relative_to(REPO_ROOT.resolve()).as_posix()
    except ValueError:
        return path.as_posix()


def _local_server_root(out_dir: Path) -> Path | None:
    try:
        out_dir.resolve().relative_to(REPO_ROOT.resolve())
    except ValueError:
        return None
    return REPO_ROOT


def _load_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return payload


def _field_change(before: float, after: float) -> dict[str, float | bool]:
    return {
        "before": float(before),
        "after": float(after),
        "delta": float(after) - float(before),
        "changed": abs(float(after) - float(before)) > 1e-9,
    }


def _pair_by_source_id(pairs: Sequence[Mapping[str, Any]]) -> dict[int, Mapping[str, Any]]:
    out: dict[int, Mapping[str, Any]] = {}
    for pair in pairs:
        source_pair_id = pair.get("source_pair_id")
        if source_pair_id is None:
            continue
        out[int(source_pair_id)] = pair
    return out


def _as_ordered_pairs(raw_pairs: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    ordered: list[dict[str, Any]] = []
    for index, pair in enumerate(raw_pairs, start=1):
        top = pair.get("top")
        bottom = pair.get("bottom")
        if not isinstance(top, Mapping) or not isinstance(bottom, Mapping):
            raise ValueError("ordered pair must contain top/bottom objects")
        source_pair_id = pair.get("source_pair_id")
        effective_pair_index = int(pair.get("effective_pair_index") or index)
        row = {
            "source_pair_id": source_pair_id,
            "solver_position": int(pair.get("solver_position") or effective_pair_index),
            "verified_order_source_id": pair.get("verified_order_source_id", source_pair_id),
            "effective_pair_index": effective_pair_index,
            "source_preview_order_index": int(
                pair.get("source_preview_order_index") or source_pair_id or effective_pair_index
            ),
            "top": {"x": float(top["x"]), "y": float(top["y"])},
            "bottom": {"x": float(bottom["x"]), "y": float(bottom["y"])},
        }
        if isinstance(pair.get("point_ids"), Mapping):
            row["point_ids"] = dict(pair["point_ids"])
        ordered.append(row)
    return ordered


def _required_wall_residuals(card: Mapping[str, Any]) -> list[dict[str, Any]]:
    walls = card.get("per_wall_residual_diagnostic", {}).get("walls")
    if not isinstance(walls, list):
        return []
    rows: list[dict[str, Any]] = []
    for wall in walls:
        if not isinstance(wall, Mapping):
            continue
        edge_ids = wall.get("source_edge_ids")
        edge = "-".join(str(part) for part in edge_ids) if isinstance(edge_ids, list) else None
        rows.append(
            {
                "edge": edge,
                "source_edge_ids": edge_ids,
                "before_residual_deg": wall.get("manhattan_residual_before_deg"),
                "after_residual_deg": wall.get("manhattan_residual_after_deg"),
                "residual_delta_deg": wall.get("residual_delta_deg"),
                "length_before": wall.get("length_before"),
                "length_after": wall.get("length_after"),
            }
        )
    return rows


def _coordinate_changes(
    before_pairs: Sequence[Mapping[str, Any]], after_pairs: Sequence[Mapping[str, Any]]
) -> list[dict[str, Any]]:
    before = _pair_by_source_id(before_pairs)
    changes: list[dict[str, Any]] = []
    for after_pair in after_pairs:
        source_pair_id = after_pair.get("source_pair_id")
        if source_pair_id is None:
            continue
        sid = int(source_pair_id)
        before_pair = before.get(sid)
        if before_pair is None:
            raise ValueError(f"source_pair_id {sid} is absent from baseline ordered pairs")
        fields: dict[str, dict[str, float | bool]] = {}
        for endpoint, field_prefix in (("top", "top"), ("bottom", "bottom")):
            before_endpoint = before_pair.get(endpoint)
            after_endpoint = after_pair.get(endpoint)
            if not isinstance(before_endpoint, Mapping) or not isinstance(after_endpoint, Mapping):
                raise ValueError("top/bottom endpoint must be an object")
            for axis in ("x", "y"):
                change = _field_change(before_endpoint[axis], after_endpoint[axis])
                if change["changed"]:
                    fields[f"{field_prefix}_{axis}"] = change
        if fields:
            changes.append(
                {
                    "source_pair_id": sid,
                    "solver_position": int(
                        after_pair.get("solver_position")
                        or after_pair.get("effective_pair_index")
                        or len(changes) + 1
                    ),
                    "verified_order_source_id": after_pair.get(
                        "verified_order_source_id", sid
                    ),
                    "effective_pair_index": int(after_pair["effective_pair_index"]),
                    "fields": fields,
                }
            )
    return changes


def _candidate_rows(
    audit: Mapping[str, Any], *, baseline_pairs: Sequence[Mapping[str, Any]]
) -> list[dict[str, Any]]:
    cards = audit.get("candidate_cards")
    if not isinstance(cards, list) or not cards:
        raise ValueError("M-Anchor.3b audit has no candidate_cards")
    rows: list[dict[str, Any]] = []
    for rank, card in enumerate(cards, start=1):
        if not isinstance(card, Mapping):
            continue
        if card.get("accepted") or card.get("downstream_recommendation"):
            raise ValueError("M-Anchor.3b review bridge refuses accepted/downstream candidates")
        after_pairs = card.get("corrected_coordinates")
        if not isinstance(after_pairs, list) or not after_pairs:
            raise ValueError(f"{card.get('candidate_id')} has no corrected_coordinates")
        changes = _coordinate_changes(baseline_pairs, after_pairs)
        if not changes:
            continue
        rows.append(
            {
                "candidate_id": card["candidate_id"],
                "family": "m_anchor_3b_local_chain_footprint_solver",
                "action_family": "m_anchor_3b_local_chain_footprint_solver",
                "decision_class": card.get("decision"),
                "source_stage": "m_anchor_3b",
                "source_rank": rank,
                "review_role": "m_anchor_3b_top5",
                "selection_reason": "hard_gate_then_layered_local_residual_ranking",
                "preferred_panel": rank <= 5,
                "manual_review_candidate": True,
                "automatic_fix_claimed": False,
                "direct_ls_trial_allowed": False,
                "accepted": False,
                "downstream_recommendation": False,
                "candidate_preference_authorized": False,
                "annotation_writeback": False,
                "annotation_patch_generated": False,
                "affected_edges": card.get("affected_edges", []),
                "improved_edges": card.get("improved_edges", []),
                "worsened_edges": card.get("worsened_edges", []),
                "moved_pairs": card.get("moved_pairs", []),
                "movement_by_axis": card.get("movement_by_axis", {}),
                "wall_residual_sum_before": card.get("wall_residual_sum_before"),
                "wall_residual_sum_after": card.get("wall_residual_sum_after"),
                "local_affected_residual_max_before": card.get(
                    "local_affected_residual_max_before"
                ),
                "local_affected_residual_max_after": card.get(
                    "local_affected_residual_max_after"
                ),
                "local_affected_residual_sum_before": card.get(
                    "local_affected_residual_sum_before"
                ),
                "local_affected_residual_sum_after": card.get(
                    "local_affected_residual_sum_after"
                ),
                "required_wall_residuals": _required_wall_residuals(card),
                "coordinate_changes": changes,
            }
        )
    if not rows:
        raise ValueError("M-Anchor.3b audit has no executable review candidates")
    return rows


def build_bridge_manifest(audit_path: Path) -> dict[str, Any]:
    audit = _load_json(audit_path)
    if audit.get("schema_version") != "m_anchor_3b_local_chain_footprint_solver_audit_v1":
        raise ValueError("unsupported M-Anchor.3b audit schema_version")
    if audit.get("accepted") or audit.get("downstream_recommendation"):
        raise ValueError("M-Anchor.3b bridge requires accepted/downstream=false")

    input_sources = audit.get("input_sources")
    if not isinstance(input_sources, Mapping):
        raise ValueError("M-Anchor.3b audit has no input_sources")
    baseline_source = input_sources.get("baseline_ordered_pairs")
    m1_source = input_sources.get("m_anchor_1_audit")
    m2_source = input_sources.get("m_anchor_2_human_verdict")
    if (
        not isinstance(baseline_source, Mapping)
        or not isinstance(m1_source, Mapping)
        or not isinstance(m2_source, Mapping)
    ):
        raise ValueError("M-Anchor.3b audit must record baseline, M1, and M2 sources")

    raw_baseline_path = REPO_ROOT / str(baseline_source["path"])
    m1_path = REPO_ROOT / str(m1_source["path"])
    m2_path = REPO_ROOT / str(m2_source["path"])
    raw_baseline_payload = _load_json(raw_baseline_path)
    m1_payload = _load_json(m1_path)
    m2_payload = _load_json(m2_path)
    reviewed_candidate = m2_payload.get("reviewed_candidate")
    if reviewed_candidate != "m_anchor_1_footprint_only_joint_xy":
        raise ValueError("M-Anchor.3b local review expects the M2-reviewed M1 footprint candidate")
    prototypes = m1_payload.get("solver_prototypes")
    if not isinstance(prototypes, list):
        raise ValueError("M1 audit has no solver_prototypes")
    reviewed = next(
        (
            item
            for item in prototypes
            if isinstance(item, Mapping) and item.get("candidate_id") == reviewed_candidate
        ),
        None,
    )
    if not isinstance(reviewed, Mapping) or not isinstance(
        reviewed.get("corrected_coordinates"), list
    ):
        raise ValueError("M2-reviewed M1 footprint candidate has no corrected_coordinates")
    ordered_pairs = _as_ordered_pairs(reviewed["corrected_coordinates"])

    return {
        "schema_version": SCHEMA_VERSION,
        "case_name": "task218_ann3741_m_anchor_3b",
        "source_case_name": audit.get("case_name"),
        "source_image": raw_baseline_payload.get("source_image") or m1_payload.get("source_image"),
        "ordered_pairs": ordered_pairs,
        "candidates": _candidate_rows(audit, baseline_pairs=ordered_pairs),
        "input_provenance": {
            "m_anchor_3b_audit": {
                "path": _repo_relative(audit_path),
                "sha256": _sha256(audit_path),
                "schema_version": audit.get("schema_version"),
            },
            "review_baseline_candidate": {
                "candidate_id": reviewed_candidate,
                "source": "m_anchor_1_audit.solver_prototypes.corrected_coordinates",
            },
            "raw_baseline_ordered_pairs": {
                "path": _repo_relative(raw_baseline_path),
                "sha256": _sha256(raw_baseline_path),
            },
            "m_anchor_1_audit": {
                "path": _repo_relative(m1_path),
                "sha256": _sha256(m1_path),
                "schema_version": m1_payload.get("schema_version"),
            },
            "m_anchor_2_human_verdict": {
                "path": _repo_relative(m2_path),
                "sha256": _sha256(m2_path),
                "schema_version": m2_payload.get("schema_version"),
                "reviewed_candidate": reviewed_candidate,
            },
        },
        "safety_boundary": {
            "audit_only": True,
            "preview_only": True,
            "accepted": False,
            "downstream_recommendation": False,
            "candidate_preference_authorized": False,
            "annotation_writeback": False,
            "annotation_patch_generated": False,
            "active_runner_role": False,
            "ranking_entry_allowed": False,
            "portfolio_selection_allowed": False,
        },
    }


def run(
    audit_path: Path = DEFAULT_AUDIT_PATH,
    out_dir: Path = DEFAULT_OUT_DIR,
    *,
    image_root: Path = DEFAULT_IMAGE_ROOT,
) -> dict[str, Path]:
    audit_path = audit_path.resolve()
    out_dir = out_dir.resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    manifest = build_bridge_manifest(audit_path)
    manifest_path = out_dir / "hypothesis_review_bridge_manifest.json"
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    paths = run_local_review(
        input_path=manifest_path,
        candidate_json=manifest_path,
        candidate_limit=len(manifest["candidates"]),
        out_dir=out_dir,
        image_root=image_root,
        case_name=str(manifest["case_name"]),
        width=1024,
        height=512,
        coordinate_mode="ls_percent",
        local_server_root=_local_server_root(out_dir),
    )
    paths["bridge_manifest"] = manifest_path
    return paths


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--audit-path", type=Path, default=DEFAULT_AUDIT_PATH)
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    parser.add_argument("--image-root", type=Path, default=DEFAULT_IMAGE_ROOT)
    args = parser.parse_args()
    for name, path in run(args.audit_path, args.out_dir, image_root=args.image_root).items():
        print(f"{name}: {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
