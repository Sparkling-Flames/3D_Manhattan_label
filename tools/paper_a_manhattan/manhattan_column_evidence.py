"""C4-lite evidence from an existing HoHoNet layout proposal."""

from __future__ import annotations

import hashlib
import math
from pathlib import Path
from typing import Any, Mapping, Sequence

import numpy as np

from lib.misc.panostretch import pano_connect_points


EVIDENCE_VERSION = "manhattan_column_evidence_v0"
KNOWN_TXT_ROOT = Path("output/mp3d_layout/HOHO_layout_aug_efficienthc_Transen1_resnet34")
KNOWN_COORDINATE_CONTRACT = "hohonet_model_output_layout_txt@1024x512"
KNOWN_WIDTH = 1024
KNOWN_HEIGHT = 512


def _unavailable(reason: str, *, candidates: Sequence[str] = ()) -> dict[str, Any]:
    return {
        "evidence_version": EVIDENCE_VERSION,
        "evidence_status": "unavailable",
        "unavailable_reason": reason,
        "missing_fields": [
            "hohonet_wallwall_peak_alignment",
            "hohonet_floor_boundary_rmse_delta",
            "hohonet_ceiling_boundary_rmse_delta",
            "candidate_corner_column_delta",
            "seam_consistency_delta",
        ],
        "source_candidates": list(candidates),
    }


def parse_hohonet_layout_txt(path: Path, *, width: int, height: int) -> dict[str, Any]:
    """Parse only explicit 2-column pairs or 3-column corner rows."""
    try:
        rows = [
            [float(value) for value in line.split()]
            for line in path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
    except (OSError, UnicodeError, ValueError) as exc:
        return _unavailable(f"invalid_hohonet_source:{type(exc).__name__}")
    if not rows or any(len(row) not in {2, 3} for row in rows):
        return _unavailable("unsupported_hohonet_layout_format")

    corners: list[dict[str, float]] = []
    if all(len(row) == 3 for row in rows):
        corners = [
            {"x": row[0], "y_ceiling": row[1], "y_floor": row[2]}
            for row in rows
        ]
        parser_method = "three_column_corner_rows"
    elif all(len(row) == 2 for row in rows) and len(rows) >= 4 and len(rows) % 2 == 0:
        for ceiling, floor in zip(rows[::2], rows[1::2]):
            if abs(ceiling[0] - floor[0]) > 1e-6:
                return _unavailable("unpaired_hohonet_corner_columns")
            corners.append(
                {
                    "x": ceiling[0],
                    "y_ceiling": min(ceiling[1], floor[1]),
                    "y_floor": max(ceiling[1], floor[1]),
                }
            )
        parser_method = "paired_two_column_rows"
    else:
        return _unavailable("mixed_or_incomplete_hohonet_layout_rows")

    if len(corners) < 2 or any(
        not (0 <= row["x"] < width)
        or not (0 <= row["y_ceiling"] < row["y_floor"] < height)
        for row in corners
    ):
        return _unavailable("hohonet_coordinates_outside_explicit_contract")
    return {
        "evidence_version": EVIDENCE_VERSION,
        "evidence_status": "available",
        "source_path": path.as_posix(),
        "source_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        "parser_method": parser_method,
        "coordinate_contract": f"hohonet_model_output_layout_txt@{width}x{height}",
        "width": width,
        "height": height,
        "corners": sorted(corners, key=lambda row: row["x"]),
        "missing_fields": [],
        "unavailable_reason": None,
    }


def inventory_hohonet_source(
    image_provenance: Mapping[str, Any], *, repo_root: Path
) -> dict[str, Any]:
    basename = str(
        image_provenance.get("source_image_basename")
        or Path(str(image_provenance.get("source_image", ""))).name
    )
    if not basename:
        return _unavailable("missing_source_image_basename")
    stem = Path(basename).stem
    candidates: list[Path] = []
    declared = image_provenance.get("proposal_source_path")
    if declared:
        candidates.append(repo_root / str(declared))
    candidates.extend((repo_root / "output/mp3d_layout").glob(f"*/{stem}.txt"))
    unique = sorted({path.resolve() for path in candidates if path.is_file()})
    if not unique:
        return _unavailable("hohonet_source_not_found")
    if len(unique) != 1:
        return _unavailable(
            "ambiguous_hohonet_sources", candidates=[path.as_posix() for path in unique]
        )
    path = unique[0]
    known_root = (repo_root / KNOWN_TXT_ROOT).resolve()
    declared_contract = image_provenance.get("proposal_coord_contract")
    if path.parent != known_root and declared_contract != KNOWN_COORDINATE_CONTRACT:
        return _unavailable(
            "missing_explicit_1024x512_coordinate_contract",
            candidates=[path.as_posix()],
        )
    return parse_hohonet_layout_txt(path, width=KNOWN_WIDTH, height=KNOWN_HEIGHT)


def _pairs_to_corners(
    pairs: Sequence[Mapping[str, Any]], width: int, height: int
) -> list[dict[str, float]]:
    return sorted(
        [
            {
                "x": 0.5
                * (float(row["top"]["x"]) + float(row["bottom"]["x"]))
                * width
                / 100.0,
                "y_ceiling": float(row["top"]["y"]) * height / 100.0,
                "y_floor": float(row["bottom"]["y"]) * height / 100.0,
            }
            for row in pairs
        ],
        key=lambda row: row["x"],
    )


def _boundary(corners: Sequence[Mapping[str, float]], width: int, height: int) -> tuple[np.ndarray, np.ndarray]:
    ceiling = np.full(width, np.nan, dtype=np.float64)
    floor = np.full(width, np.nan, dtype=np.float64)
    for index, left in enumerate(corners):
        right = corners[(index + 1) % len(corners)]
        for key, z, target in (
            ("y_ceiling", -50, ceiling),
            ("y_floor", 50, floor),
        ):
            points = pano_connect_points(
                np.array([left["x"], left[key]], dtype=np.float64),
                np.array([right["x"], right[key]], dtype=np.float64),
                z=z,
                w=width,
                h=height,
            )
            target[points[:, 0].astype(int) % width] = points[:, 1]
    if np.isnan(ceiling).any() or np.isnan(floor).any():
        raise ValueError("incomplete_connected_boundary")
    return ceiling, floor


def _rmse(left: np.ndarray, right: np.ndarray) -> float:
    return float(np.sqrt(np.mean(np.square(left - right))))


def _column_rmse(candidate: Sequence[Mapping[str, float]], reference: Sequence[Mapping[str, float]], width: int) -> float:
    distances = [
        min(min(abs(row["x"] - ref["x"]), width - abs(row["x"] - ref["x"])) for ref in reference)
        for row in candidate
    ]
    return math.sqrt(sum(value * value for value in distances) / len(distances))


def compute_column_evidence(
    source: Mapping[str, Any],
    baseline_pairs: Sequence[Mapping[str, Any]],
    candidate_pairs: Sequence[Mapping[str, Any]],
    *,
    coordinate_mode: str,
) -> dict[str, Any]:
    if source.get("evidence_status") != "available":
        return dict(source)
    if coordinate_mode != "ls_percent":
        return _unavailable("unsupported_candidate_coordinate_mode")
    width, height = int(source["width"]), int(source["height"])
    reference = list(source["corners"])
    baseline = _pairs_to_corners(baseline_pairs, width, height)
    candidate = _pairs_to_corners(candidate_pairs, width, height)
    try:
        reference_ceiling, reference_floor = _boundary(reference, width, height)
        baseline_ceiling, baseline_floor = _boundary(baseline, width, height)
        candidate_ceiling, candidate_floor = _boundary(candidate, width, height)
    except (KeyError, TypeError, ValueError) as exc:
        return _unavailable(f"column_evidence_materialization_failed:{type(exc).__name__}")

    baseline_column = _column_rmse(baseline, reference, width)
    candidate_column = _column_rmse(candidate, reference, width)
    baseline_ceiling_rmse = _rmse(baseline_ceiling, reference_ceiling)
    candidate_ceiling_rmse = _rmse(candidate_ceiling, reference_ceiling)
    baseline_floor_rmse = _rmse(baseline_floor, reference_floor)
    candidate_floor_rmse = _rmse(candidate_floor, reference_floor)
    baseline_seam = abs(baseline_ceiling[0] - baseline_ceiling[-1]) + abs(baseline_floor[0] - baseline_floor[-1])
    candidate_seam = abs(candidate_ceiling[0] - candidate_ceiling[-1]) + abs(candidate_floor[0] - candidate_floor[-1])
    deltas = {
        "candidate_corner_column_delta": candidate_column - baseline_column,
        "hohonet_ceiling_boundary_rmse_delta": candidate_ceiling_rmse - baseline_ceiling_rmse,
        "hohonet_floor_boundary_rmse_delta": candidate_floor_rmse - baseline_floor_rmse,
        "seam_consistency_delta": candidate_seam - baseline_seam,
    }
    conflicts = [name for name, value in deltas.items() if value > 1e-9]
    return {
        "evidence_version": EVIDENCE_VERSION,
        "evidence_status": "available",
        "source_provenance": {
            key: source[key]
            for key in ("source_path", "source_sha256", "parser_method", "coordinate_contract")
        },
        "hohonet_wallwall_peak_alignment": {
            "baseline_rmse_px": baseline_column,
            "candidate_rmse_px": candidate_column,
        },
        **deltas,
        "visual_conflict_flags": conflicts,
        "image_edge_support_optional": None,
        "missing_fields": ["image_edge_support_optional"],
        "unavailable_reason": None,
        "scope_boundary": {
            "existing_hohonet_proposal_only": True,
            "image_model_used": False,
            "depth_model_used": False,
        },
    }
