"""Bridge a Manhattan hypothesis core output into the existing local 3D review."""

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

from tools.paper_a_manhattan.run_local_3d_projection_review import run_local_review


SCHEMA_VERSION = "manhattan_hypothesis_local_review_bridge_v1"
DEFAULT_IMAGE_ROOT = Path("data/mp3d_layout/img_v")
BUCKETS = (
    "best_balanced",
    "best_short_wall_preserving",
    "best_low_movement",
)


def _local_server_root(out_dir: Path) -> Path | None:
    try:
        out_dir.resolve().relative_to(REPO_ROOT.resolve())
    except ValueError:
        return None
    return REPO_ROOT


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def select_review_candidates(
    core: Mapping[str, Any], *, diagnostic_limit: int = 2
) -> list[dict[str, Any]]:
    candidates = {row["candidate_id"]: row for row in core["candidate_set"]}
    evaluations = core["constrained_evaluations"]
    geometry = core["candidate_review_geometry"]
    selected: list[tuple[str, str]] = []
    seen: set[str] = set()

    def add(candidate_id: str | None, role: str) -> None:
        if candidate_id and candidate_id not in seen:
            seen.add(candidate_id)
            selected.append((candidate_id, role))

    for bucket_name in BUCKETS:
        bucket = core["portfolio_ranking"].get(bucket_name, {})
        candidate = bucket.get("candidate") or {}
        add(candidate.get("candidate_id"), bucket_name)

    diagnostic = [
        row
        for row in candidates.values()
        if row["candidate_id"] not in seen
        and row.get("hard_gate_passed")
        and row.get("is_improving_hypothesis")
    ]
    diagnostic.sort(
        key=lambda row: (*row.get("hypothesis_ranking_key", []), row["candidate_id"])
    )
    for index, row in enumerate(diagnostic[: max(0, diagnostic_limit)], start=1):
        add(row["candidate_id"], f"diagnostic_{index}")

    output: list[dict[str, Any]] = []
    for index, (candidate_id, role) in enumerate(selected):
        candidate = candidates[candidate_id]
        evaluation = evaluations[candidate_id]
        changes = geometry.get(candidate_id, {}).get("coordinate_changes")
        if not isinstance(changes, list) or not changes:
            raise ValueError(f"candidate {candidate_id} has no review geometry")
        if not evaluation["feasibility"]["hard_gate_passed"]:
            raise ValueError(f"suppressed candidate {candidate_id} cannot enter review")
        plausibility = evaluation["layout_plausibility"]
        output.append(
            {
                "candidate_id": candidate_id,
                "family": candidate.get("action_family"),
                "action_family": candidate.get("action_family"),
                "coordinate_changes": changes,
                "decision_class": candidate.get("decision_class"),
                "hard_gate": False,
                "assertion_violations": [],
                "manual_review_candidate": bool(
                    candidate.get("recommended_review_candidate")
                ),
                "automatic_fix_claimed": False,
                "source_stage": "manhattan_hypothesis_core",
                "review_role": role,
                "selection_reason": role,
                "preferred_panel": index < len(BUCKETS),
                "short_wall_edges_after": sorted(
                    set(plausibility.get("existing_short_wall_preserved", []))
                    | set(plausibility.get("new_short_wall_created", []))
                ),
            }
        )
    return output


def build_bridge_manifest(
    core: Mapping[str, Any], *, core_path: Path, diagnostic_limit: int = 2
) -> dict[str, Any]:
    state = core.get("state_before", {})
    pairs = state.get("ordered_pairs")
    if not isinstance(pairs, list) or not pairs:
        raise ValueError("core output has no state_before.ordered_pairs")
    image = state.get("image_provenance", {})
    return {
        "schema_version": SCHEMA_VERSION,
        "case_name": core.get("case_name"),
        "source_image": image.get("source_image"),
        "ordered_pairs": pairs,
        "candidates": select_review_candidates(
            core, diagnostic_limit=diagnostic_limit
        ),
        "core_provenance": {
            "path": core_path.as_posix(),
            "sha256": _sha256(core_path),
            "schema_version": core.get("schema_version"),
        },
        "safety_boundary": {
            "expert_side_only": True,
            "offline_dry_run_only": True,
            "automatic_apply": False,
            "annotation_writeback": False,
            "worker_facing": False,
            "routing_input": False,
        },
    }


def run(
    core_path: Path,
    out_dir: Path,
    *,
    image_root: Path = DEFAULT_IMAGE_ROOT,
    diagnostic_limit: int = 2,
) -> dict[str, Path]:
    core_path = core_path.resolve()
    core = json.loads(core_path.read_text(encoding="utf-8"))
    if core.get("schema_version") != "manhattan_constrained_hypothesis_ranking_core_v1":
        raise ValueError("unsupported core output schema_version")
    out_dir = out_dir.resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = out_dir / "hypothesis_review_bridge_manifest.json"
    manifest = build_bridge_manifest(
        core, core_path=core_path, diagnostic_limit=diagnostic_limit
    )
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    config = core["state_before"]["projection_config"]
    paths = run_local_review(
        input_path=manifest_path,
        candidate_json=manifest_path,
        candidate_limit=len(manifest["candidates"]),
        out_dir=out_dir,
        image_root=image_root,
        case_name=str(core.get("case_name") or core_path.stem),
        width=int(config["width"]),
        height=int(config["height"]),
        coordinate_mode=str(config["coordinate_mode"]),
        camera_height=float(config["camera_height"]),
        local_server_root=_local_server_root(out_dir),
    )
    paths["bridge_manifest"] = manifest_path
    return paths


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--core-output", type=Path, required=True)
    parser.add_argument("--out-dir", type=Path, required=True)
    parser.add_argument("--image-root", type=Path, default=DEFAULT_IMAGE_ROOT)
    parser.add_argument("--diagnostic-limit", type=int, default=2)
    args = parser.parse_args()
    for name, path in run(
        args.core_output,
        args.out_dir,
        image_root=args.image_root,
        diagnostic_limit=args.diagnostic_limit,
    ).items():
        print(f"{name}: {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
