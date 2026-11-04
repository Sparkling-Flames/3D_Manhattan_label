"""Shared deterministic I/O, estimands and dictionaries for direct AC only."""
from __future__ import annotations

import gzip
import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
OUT = HERE.parent
REPO = OUT.parents[2]
SEED = 202611041302
BOOTSTRAP = 2000
LEGACY = "legacy_current_label_conditional"
BATCH12 = "batch12_strictABC_direct_legs"
GAP = "current_capacity_gap_supplement"
COMBINED = "legacy_plus_capacity_gap"
CORE_BUDGETS = {(6, 3), (8, 4), (10, 5), (14, 7), (20, 7)}

SCALARS = [
    "B8L2", "D10", "IoU3D100", "iou_2d", "S_bottom_deg", "dir", "Hmean", "Hcenter",
    "omission", "extension", "height_mean_ratio", "nodes", "fusion_turn_n",
    "fusion_short_turn_edges", "fusion_redundancy_n", "geometry_area_h2",
    "height_mean_h", "height_min_h", "height_max_h", "centroid_x_h", "centroid_z_h",
    "ref_node_recall_5", "ref_node_recall_9", "ref_edge_recall_5", "ref_edge_recall_9",
    "reference_node_shortfall", "reference_node_excess", "top_y_mean_px", "bottom_y_mean_px",
    "matched_ref_top_abs_deg", "matched_ref_bottom_abs_deg", "matched_ref_horizontal_abs_deg",
    "matched_ref_pair_fraction", "boundary_loss", "direction_loss", "global_height_loss",
    "local_height_loss", "height_loss", "WQ", "floor_WQ", "height_drop_current",
    "diag_wall_coverage_03", "diag_wall_coverage_05", "diag_corner_recall_05",
    "minimum_support", "identity_groups_n", "unselected_groups_n", "half_vote_nodes",
    "selected_support_min", "target_individual_B8L2_mean", "target_individual_B8L2_min",
]
STATES = ["score_status", "geometry_status", "geometry_reason", "order_status",
          "complete_evaluable", "complete_floor_evaluable", "floor_evaluable",
          "connection_available", "below_four", "location_unresolved"]
GEOMETRY = ["geometry_bev_distance_AC", "geometry_centroid_distance_AC",
            "geometry_log_area_distance_AC", "geometry_pair_angle_AC",
            "geometry_top_angle_AC", "geometry_bottom_angle_AC",
            "geometry_unmatched_pairs_AC", "geometry_same_pair_count_AC"]
IDCOLS = ["analysis_cohort", "scope", "condition", "n", "m", "class_pair"]
IMAGE_KEYS = ["pool_id", "image", "building", "official_difficulty", "structural_condition", "room_type"]

METRIC_INFO = {
    "B8L2": ("Q", "points_0_100", "higher"),
    "D10": ("D10", "points_0_100", "higher"),
    "IoU3D100": ("3D IoU", "percentage_points", "higher"),
    "iou_2d": ("2D IoU", "fraction", "higher"),
    "S_bottom_deg": ("bottom boundary error", "degree", "lower"),
    "dir": ("direction error", "degree", "lower"),
    "Hmean": ("global height deviation", "dimensionless", "lower"),
    "Hcenter": ("local height deviation", "dimensionless", "lower"),
    "omission": ("omission", "fraction", "lower"),
    "extension": ("extension", "fraction", "lower"),
    "nodes": ("selected nodes", "count", "descriptive"),
    "fusion_turn_n": ("effective turns", "count", "descriptive"),
    "fusion_short_turn_edges": ("short turn edges", "count", "descriptive"),
    "fusion_redundancy_n": ("near-collinear redundancy", "count", "descriptive"),
    "ref_node_recall_9": ("reference node recall at 9 degrees", "fraction", "higher"),
    "ref_edge_recall_9": ("reference edge recall at 9 degrees", "fraction", "higher"),
    "matched_ref_top_abs_deg": ("matched reference top error", "degree", "lower"),
    "matched_ref_bottom_abs_deg": ("matched reference bottom error", "degree", "lower"),
    "matched_ref_horizontal_abs_deg": ("matched reference horizontal error", "degree", "lower"),
    "matched_ref_pair_fraction": ("matched reference pair fraction", "fraction", "descriptive"),
    "geometry_area_h2": ("floor area", "camera_height_squared", "descriptive"),
    "boundary_loss": ("boundary loss", "dimensionless", "lower"),
    "direction_loss": ("direction loss", "dimensionless", "lower"),
    "global_height_loss": ("global height loss", "dimensionless", "lower"),
    "local_height_loss": ("local height loss", "dimensionless", "lower"),
}


def read_csv(path: Path | str, **kwargs) -> pd.DataFrame:
    return pd.read_csv(path, low_memory=False, **kwargs)


def csv(path: Path | str, frame: pd.DataFrame) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    data = frame.to_csv(index=False).encode("utf-8")
    if path.name.endswith(".gz"):
        data = gzip.compress(data, mtime=0)
    tmp = path.with_name(path.name + ".writing")
    tmp.write_bytes(data)
    tmp.replace(path)


def write_json(path: Path | str, obj) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2, default=str), encoding="utf-8")


def digest(obj) -> str:
    return hashlib.sha256(json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=True,
                                     default=lambda v: v.item() if isinstance(v, np.generic) else str(v)).encode()).hexdigest()


def sha(path: Path | str) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def members(s) -> list[str]:
    return [] if pd.isna(s) or not str(s) else str(s).split("|")


def truth(s: pd.Series) -> pd.Series:
    return s.fillna(False).astype(str).str.lower().isin(["true", "1", "1.0"])


def tier(images: int, buildings: int) -> str:
    return "none" if not images else ("supported" if images >= 10 and buildings >= 5 else "sparse")


def summary(image: pd.DataFrame, metric: str, seed_key=None, with_ci: bool = True) -> dict:
    """Image-equal mean with building-cluster uncertainty; no team-level N."""
    z = image.loc[np.isfinite(pd.to_numeric(image[metric], errors="coerce")), ["image", "building", metric]].copy()
    if z.empty:
        return {"images": 0, "buildings": 0, "support_tier": "none"}
    if z.image.duplicated().any():
        raise ValueError("summary requires one value per image")
    values = z[metric].to_numpy(float)
    buildings = z.groupby("building", sort=True)[metric].agg(["sum", "count", "mean"])
    B = len(buildings)
    avg = float(values.mean())
    out = dict(images=len(z), buildings=B, support_tier=tier(len(z), B), image_equal_mean=avg,
               image_median=float(np.median(values)), image_p10=float(np.quantile(values, .1)),
               image_p90=float(np.quantile(values, .9)), image_min=float(values.min()), image_max=float(values.max()),
               positive_images=int((values > 1e-10).sum()), negative_images=int((values < -1e-10).sum()),
               exactly_negligible_images=int((np.abs(values) <= 1e-10).sum()),
               building_equal_mean=float(buildings["mean"].mean()))
    for epsilon in [.5, 1., 2.]:
        suffix = str(epsilon).replace(".", "p")
        out.update({f"up_gt_{suffix}_images": int((values > epsilon).sum()),
                    f"down_lt_minus_{suffix}_images": int((values < -epsilon).sum()),
                    f"within_pm_{suffix}_images": int((np.abs(values) <= epsilon).sum())})
    sums = buildings["sum"].to_numpy(float)
    counts = buildings["count"].to_numpy(float)
    means = buildings["mean"].to_numpy(float)
    if B > 1:
        leave_out = (sums.sum() - sums) / (counts.sum() - counts)
        out.update(leave_one_building_out_min=float(leave_out.min()), leave_one_building_out_max=float(leave_out.max()),
                   leave_one_building_out_same_sign=bool(np.all(np.sign(leave_out) == np.sign(avg))))
    if with_ci and B > 1:
        seed = int(digest([SEED, seed_key, metric])[:8], 16)
        draw = np.random.default_rng(seed).integers(0, B, (BOOTSTRAP, B))
        bootstrap = sums[draw].sum(axis=1) / counts[draw].sum(axis=1)
        bbootstrap = means[draw].mean(axis=1)
        out.update(cluster_bootstrap_low=float(np.quantile(bootstrap, .025)),
                   cluster_bootstrap_high=float(np.quantile(bootstrap, .975)),
                   building_equal_bootstrap_low=float(np.quantile(bbootstrap, .025)),
                   building_equal_bootstrap_high=float(np.quantile(bbootstrap, .975)))
    return out


def make_image_table(pairs: pd.DataFrame, group: list[str], metrics: list[str], gap_pair_equal: bool = False) -> pd.DataFrame:
    """Physical pair -> target pool -> image; targets never acquire extra weight."""
    usable = [c for c in metrics if c in pairs]
    pool_keys = group + [c for c in ["pool_id", "image", "building"] if c not in group]
    source = pairs["component_cohort"] if "component_cohort" in pairs else pairs.get("analysis_cohort", pd.Series("", index=pairs.index))
    gap = source.eq(GAP) & (not gap_pair_equal)
    if gap.any():
        # The gap design samples X/Z blocks first and D backgrounds second.
        # Missing Q must not give a block with more surviving D choices extra
        # weight. Legacy stored pairs retain their conditional pair weighting.
        old = pairs.loc[~gap]
        new = pairs.loc[gap]
        backgrounds = new.groupby(pool_keys + ["block_id", "background_id"], dropna=False, observed=True, sort=True)[usable].mean().reset_index()
        blocks = backgrounds.groupby(pool_keys + ["block_id"], dropna=False, observed=True, sort=True)[usable].mean().reset_index()
        npools = blocks.groupby(pool_keys, dropna=False, observed=True, sort=True)[usable].mean().reset_index()
        opools = old.groupby(pool_keys, dropna=False, observed=True, sort=True)[usable].mean().reset_index()
        p = pd.concat([opools, npools], ignore_index=True)
        if p.duplicated(pool_keys).any():
            raise ValueError("Gap and legacy pools overlap within a claimed capacity-gap condition")
    else:
        p = pairs.groupby(pool_keys, dropna=False, observed=True, sort=True)[usable].mean().reset_index()
    count = pairs.groupby(pool_keys, dropna=False, observed=True).size().rename("physical_pairs").reset_index()
    p = p.merge(count, on=pool_keys, how="left", validate="one_to_one")
    img_keys = group + [c for c in ["image", "building"] if c not in group]
    out = p.groupby(img_keys, dropna=False, observed=True, sort=True)[usable].mean().reset_index()
    # Reference-derived structural conditions can differ across legitimate targets.
    # Each target domain remains separate; this collapses any within-domain target
    # repeats to a single image value, with explicit target count in the output.
    n = p.groupby(img_keys, dropna=False, observed=True).agg(physical_pairs=("physical_pairs", "sum"),
                                                          target_pools=("pool_id", "nunique")).reset_index()
    out = out.merge(n, on=img_keys, how="left", validate="one_to_one")
    context = [c for c in ["official_difficulty", "structural_condition", "room_type"] if c in pairs and c not in img_keys]
    if context:
        def unique_or_mixed(x):
            vals = sorted(set(x.dropna().astype(str)))
            return vals[0] if len(vals) == 1 else "multiple_target_contexts"
        ctx = pairs.groupby(img_keys, dropna=False, observed=True)[context].agg(unique_or_mixed).reset_index()
        out = out.merge(ctx, on=img_keys, how="left", validate="one_to_one")
    return out
