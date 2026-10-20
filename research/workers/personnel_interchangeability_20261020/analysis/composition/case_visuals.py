"""Exact ERP/BEV/3D case figures from supplied frozen final geometry.

No selection, fusion, scoring, fitting, image download, or reference replacement
is performed here. See CASE_VISUALS_INTERFACE.md for the portable case schema.
The top of each 3D column follows the existing continuous-coordinate viewer
construction: a top ray uses the horizontal range of its paired bottom point.
This is a visual geometric inference at camera height one, not measured depth.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import tempfile
from typing import Any

# Keep font/cache writes in a task-specific writable directory.
os.environ.setdefault("MPLCONFIGDIR", str(Path(tempfile.gettempdir()) / "personnel_composition_matplotlib"))
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import font_manager
from matplotlib.lines import Line2D
from matplotlib import patheffects
from mpl_toolkits.mplot3d.art3d import Poly3DCollection
import numpy as np
from PIL import Image
from shapely.geometry import Polygon

WIDTH, HEIGHT = 1024.0, 512.0
TEAM_COLORS = ("#167d9a", "#b56617", "#8a49a1", "#427650", "#c65365", "#4c5e91")
CLASS_COLORS = ("#1d81a2", "#b47922", "#8b59a0", "#438863", "#be5969", "#667392", "#998940", "#7c7870")
REF_COLOR = "#303741"
REF_ERP_COLOR = "#ffe476"
GAP_COLOR = "#c51b72"


def _points(value):
    if value is None:
        return None
    array = np.asarray(value, dtype=float)
    if array.ndim != 2 or array.shape[1] != 2 or not np.isfinite(array).all():
        return None
    return array


def _ray(points):
    points = np.asarray(points, dtype=float)
    u = 2 * np.pi * (points[:, 0] / WIDTH - 0.5)
    v = np.pi * (0.5 - points[:, 1] / HEIGHT)
    return np.column_stack((np.cos(v) * np.sin(u), np.sin(v), -np.cos(v) * np.cos(u)))


def _project(points3d):
    xyz = np.asarray(points3d, dtype=float)
    x = ((np.arctan2(xyz[:, 0], -xyz[:, 2]) / (2 * np.pi) + 0.5) * WIDTH) % WIDTH
    y = (0.5 - np.arctan2(xyz[:, 1], np.hypot(xyz[:, 0], xyz[:, 2])) / np.pi) * HEIGHT
    return np.column_stack((x, y))


def viewer_geometry(points, floor=None):
    """Build only visualization coordinates; retain the given final footprint."""
    p, supplied = _points(points), _points(floor)
    result = {"floor": supplied, "floor_xyz": None, "ceiling_xyz": None,
              "status": "unavailable", "reason": "missing_or_invalid_points",
              "floor_reconstruction_max_abs_difference": None}
    if supplied is not None and len(supplied) >= 3:
        result["floor_xyz"] = np.column_stack((supplied[:, 0], -np.ones(len(supplied)), supplied[:, 1]))
    if p is None or len(p) < 6 or len(p) % 2:
        return result
    top, bottom = _ray(p[::2]), _ray(p[1::2])
    minimum_vertical = math.sin(math.radians(0.5))
    if np.any(bottom[:, 1] >= -minimum_vertical):
        result["reason"] = "bottom_wrong_hemisphere_or_near_horizon"
        return result
    derived_xyz = -bottom / bottom[:, 1, None]
    derived = derived_xyz[:, [0, 2]]
    if supplied is not None:
        if supplied.shape != derived.shape:
            raise ValueError("provided_floor_and_point_ring_sizes_differ")
        difference = float(np.max(np.abs(supplied - derived)))
        result["floor_reconstruction_max_abs_difference"] = difference
        if difference > 1e-7 * max(1.0, float(np.max(np.abs(supplied)))):
            raise ValueError("provided_floor_does_not_match_frozen_continuous_point_convention")
        derived = supplied
    result["floor"] = derived
    result["floor_xyz"] = np.column_stack((derived[:, 0], -np.ones(len(derived)), derived[:, 1]))
    horizontal = np.linalg.norm(top[:, [0, 2]], axis=1)
    if np.any(top[:, 1] <= minimum_vertical) or np.any(horizontal < 1e-8):
        result["reason"] = "top_wrong_hemisphere_near_horizon_or_pole"
        return result
    result["ceiling_xyz"] = top * (np.linalg.norm(derived, axis=1) / horizontal)[:, None]
    result.update(status="ok", reason=None,
                  footprint_valid=bool(Polygon(derived).is_valid and Polygon(derived).area > 0),
                  vertical_pair_mismatch=bool(np.any(np.abs((p[::2, 0] - p[1::2, 0] + WIDTH / 2) % WIDTH - WIDTH / 2) > 1e-6)))
    return result


def _plot_periodic(ax, curve, **style):
    curve = np.asarray(curve)
    if not len(curve) or not np.isfinite(curve).all():
        return
    x = np.unwrap(curve[:, 0] / WIDTH * 2 * np.pi) / (2 * np.pi) * WIDTH
    for offset in (-2 * WIDTH, -WIDTH, 0, WIDTH, 2 * WIDTH):
        ax.plot(x + offset, curve[:, 1], **style)


def _curve_between(a, b, samples=64):
    rays = _ray(np.asarray([a, b]))
    weights = np.linspace(0, 1, samples)[:, None]
    points3d = (1 - weights) * rays[0] + weights * rays[1]
    if np.min(np.linalg.norm(points3d, axis=1)) < 1e-9:
        return None
    return _project(points3d)


def _erp_edges(ax, points, color, linewidth=1.4, alpha=1.0, reference=False, markers=False):
    p = _points(points)
    if p is None or len(p) < 6 or len(p) % 2:
        return
    stroke = [patheffects.withStroke(linewidth=linewidth + 0.9, foreground="#151a24", alpha=0.85)] if reference else None
    style = dict(color=color, linewidth=linewidth, alpha=alpha, zorder=4 if reference else 3,
                 solid_capstyle="round", path_effects=stroke)
    pairs = p.reshape(-1, 2, 2)
    for side in (0, 1):
        for a, b in zip(pairs[:, side], np.roll(pairs[:, side], -1, axis=0)):
            curve = _curve_between(a, b)
            if curve is not None:
                _plot_periodic(ax, curve, **style)
    for pair in pairs:
        _plot_periodic(ax, pair, **style)
    if markers:
        for offset in (-WIDTH, 0, WIDTH):
            ax.scatter(p[:, 0] + offset, p[:, 1], s=8, color=color, edgecolor="#ffffff" if not reference else "#1a1d24",
                       linewidths=0.3, zorder=5)


def _erp_background(ax, photo, bounds=None):
    if photo is not None:
        for offset in (-WIDTH, 0, WIDTH):
            ax.imshow(photo, extent=(offset, offset + WIDTH, HEIGHT, 0), zorder=0)
    else:
        ax.set_facecolor("#edf0f3")
        ax.text(0.5, 0.025, "Original image unavailable", transform=ax.transAxes, ha="center", va="bottom",
                fontsize=8, color="#5c6672", bbox={"facecolor": "white", "alpha": 0.85, "edgecolor": "none"})
    if bounds is None:
        ax.set_xlim(0, WIDTH)
        ax.set_ylim(HEIGHT, 0)
    else:
        x0, x1, y0, y1 = bounds
        ax.set_xlim(x0, x1)
        ax.set_ylim(y1, y0)
    ax.set_aspect("equal", adjustable="box")
    ax.set_xticks([])
    ax.set_yticks([])
    for spine in ax.spines.values():
        spine.set_color("#c6ccd3")


def _bev_ring(ax, floor, color, linewidth=1.5, alpha=1.0, reference=False, zorder=None):
    p = _points(floor)
    if p is None or len(p) < 2:
        return
    ring = np.vstack((p, p[0]))
    ax.plot(ring[:, 0], ring[:, 1], color=color, linewidth=linewidth, alpha=alpha,
            linestyle="--" if reference else "-", zorder=zorder if zorder is not None else (4 if reference else 3))


def _highlight_reference(ax, floor, edges):
    p = _points(floor)
    if p is None:
        return
    for edge in edges:
        i = int(edge)
        if i < 0 or i >= len(p):
            raise ValueError("highlight_reference_edge_out_of_range")
        q = p[[i, (i + 1) % len(p)]]
        ax.plot(q[:, 0], q[:, 1], color="#a86405", linewidth=2.5, alpha=0.85, zorder=5)
        middle = q.mean(axis=0)
        ax.annotate("r" + str(i), middle, xytext=(4, 4), textcoords="offset points", fontsize=8,
                    color="#7b4700", bbox={"facecolor": "#fff9ec", "alpha": 0.8, "edgecolor": "none", "pad": 0.8}, zorder=8)


def _uncovered_reference(ax, floor, diagnostic):
    p = _points(floor)
    details = (diagnostic or {}).get("diag_wall_details_05")
    if p is None or details is None:
        return
    for wall in details:
        i, j = wall["reference_input_start_index"], wall["reference_input_end_index"]
        start, end = p[i], p[j]
        length = float(wall["length"])
        unit = (end - start) / length
        last = 0.0
        for low, high in wall["covered_intervals"] + [[length, length]]:
            if low > last:
                q = np.asarray([start + last * unit, start + low * unit])
                ax.plot(q[:, 0], q[:, 1], color=GAP_COLOR, linewidth=3, alpha=0.85, zorder=6)
            last = max(last, high)


def _style_bev(ax, bounds):
    ax.set_xlim(bounds[0], bounds[1])
    ax.set_ylim(bounds[2], bounds[3])
    ax.set_aspect("equal", adjustable="box")
    ax.grid(True, color="#e7eaf0", linewidth=0.6)
    ax.set_axisbelow(True)
    ax.tick_params(labelsize=7, colors="#697380")
    ax.scatter([0], [0], s=24, marker="+", color="#252a32", zorder=7)
    ax.set_xlabel("X / camera height", fontsize=8, color="#68707a")
    ax.set_ylabel("Z / camera height", fontsize=8, color="#68707a")
    for spine in ax.spines.values():
        spine.set_color("#d0d5dc")


def _wire3d(ax, geom, color, reference=False):
    floor, ceiling = geom.get("floor_xyz"), geom.get("ceiling_xyz")
    if floor is None:
        return
    floor = np.asarray(floor)
    def coordinates(xyz):
        return xyz[:, 0], xyz[:, 2], xyz[:, 1] + 1
    style = dict(color=color, linewidth=1.0 if reference else 1.45, alpha=0.65 if reference else 0.95,
                 linestyle="--" if reference else "-")
    ax.plot(*coordinates(np.vstack((floor, floor[0]))), **style)
    if ceiling is None:
        return
    ceiling = np.asarray(ceiling)
    ax.plot(*coordinates(np.vstack((ceiling, ceiling[0]))), **style)
    faces = []
    for i in range(len(floor)):
        ax.plot(*coordinates(np.vstack((floor[i], ceiling[i]))), **style)
        j = (i + 1) % len(floor)
        q = np.asarray([floor[i], floor[j], ceiling[j], ceiling[i]])
        faces.append(np.column_stack(coordinates(q)))
    if not reference and geom.get("footprint_valid") and not geom.get("vertical_pair_mismatch"):
        ax.add_collection3d(Poly3DCollection(faces, facecolors=color, alpha=0.07, edgecolors="none"))


def _style3d(ax, bounds, height_bounds, view):
    ax.set_xlim(bounds[0], bounds[1])
    ax.set_ylim(bounds[2], bounds[3])
    ax.set_zlim(*height_bounds)
    ax.set_box_aspect((bounds[1] - bounds[0], bounds[3] - bounds[2], height_bounds[1] - height_bounds[0]))
    ax.view_init(elev=view.get("elev", 24), azim=view.get("azim", -56))
    ax.set_proj_type("ortho")
    ax.scatter([0], [0], [1], marker="+", s=24, color="#202630")
    ax.tick_params(labelsize=6, pad=0, colors="#68707a")
    ax.set_xlabel("X", fontsize=8, labelpad=0)
    ax.set_ylabel("Z", fontsize=8, labelpad=0)
    ax.set_zlabel("H / camera height", fontsize=7, labelpad=1)
    for axis in (ax.xaxis, ax.yaxis, ax.zaxis):
        axis.pane.set_facecolor((0.98, 0.985, 0.99, 0.4))
        axis._axinfo["grid"]["color"] = (0.87, 0.89, 0.92, 0.6)


def _format_number(value, digits=1):
    if value is None:
        return "NA"
    try:
        return f"{float(value):.{digits}f}" if math.isfinite(float(value)) else "NA"
    except (TypeError, ValueError):
        return "NA"


def _team_header(team, index):
    label = team.get("label", chr(65 + index))
    counts = "  ".join(f"{c}×{n}" for c, n in sorted(team.get("counts", {}).items()) if n)
    n = len(team.get("member_workers", [])) or team.get("k", "?")
    scores = f"n={n}   B8L2 {_format_number(team.get('B8L2'))}   D10 {_format_number(team.get('D10'))}"
    return str(label) + ("  " + counts if counts else "") + "\n" + scores


def _bounds(geometries, supplied=None):
    if supplied is not None:
        result = list(map(float, supplied))
        if len(result) != 4 or result[0] >= result[1] or result[2] >= result[3]:
            raise ValueError("invalid_bev_limits")
        return result
    arrays = [g["floor"] for g in geometries if g.get("floor") is not None]
    if not arrays:
        return [-2, 2, -2, 2]
    points = np.vstack(arrays + [np.asarray([[0, 0]])])
    low, high = points.min(axis=0), points.max(axis=0)
    padding = max(float(np.max(high - low)) * 0.08, 0.05)
    return [float(low[0] - padding), float(high[0] + padding), float(low[1] - padding), float(high[1] + padding)]


def _heights(geometries):
    heights = [0, 1]
    for geom in geometries:
        if geom.get("ceiling_xyz") is not None:
            heights.extend((geom["ceiling_xyz"][:, 1] + 1).tolist())
    high = max(heights)
    return [min(0, min(heights)), high + max(0.08, high * 0.06)]


def _configure_font(font_path):
    if font_path:
        font_manager.fontManager.addfont(str(font_path))
        bold_path = Path(font_path).with_name(Path(font_path).name.replace("Regular", "Bold"))
        if bold_path != Path(font_path) and bold_path.is_file():
            font_manager.fontManager.addfont(str(bold_path))
        family = font_manager.FontProperties(fname=str(font_path)).get_name()
    else:
        family = "DejaVu Sans"
    plt.rcParams.update({"font.family": family, "font.size": 9, "axes.unicode_minus": False,
                         "figure.facecolor": "white", "savefig.facecolor": "white", "pdf.fonttype": 42})


def _save(fig, out, basename, formats):
    files = []
    for extension in formats:
        path = out / (basename + "." + extension)
        fig.savefig(path, dpi=190, bbox_inches="tight", pad_inches=0.08)
        files.append({"path": path.name, "bytes": path.stat().st_size, "sha256": hashlib.sha256(path.read_bytes()).hexdigest()})
    plt.close(fig)
    return files


def _validate_members(case):
    members = case.get("members", [])
    by_worker = {str(m["worker_id"]): m for m in members}
    if len(by_worker) != len(members):
        raise ValueError("duplicate_provided_worker_in_case")
    for team in case["teams"]:
        workers = list(team.get("member_workers", []))
        if len(workers) != len(set(workers)):
            raise ValueError("duplicate_team_worker_in_case")
        if team.get("k") is not None and len(workers) != team["k"]:
            raise ValueError("team_size_and_members_differ")
        if case.get("pool_id") and team.get("team_key"):
            member_digest = hashlib.sha256(json.dumps(sorted(workers), sort_keys=True, separators=(",", ":")).encode()).hexdigest()[:20]
            if team["team_key"] != case["pool_id"] + "__" + member_digest:
                raise ValueError("team_key_does_not_rebuild_from_exact_members")
        if members:
            if not set(workers) <= by_worker.keys():
                raise ValueError("case_member_geometry_missing_for_team_worker")
            if team.get("member_object_ids") is not None:
                if sorted(team["member_object_ids"]) != sorted(by_worker[w]["object_id"] for w in workers):
                    raise ValueError("case_member_object_ids_do_not_rebuild_team")
            if team.get("counts"):
                observed = {c: sum(by_worker[w].get("class_id", "unknown") == c for w in workers) for c in team["counts"]}
                if observed != team["counts"] or sum(observed.values()) != len(workers):
                    raise ValueError("case_member_classes_do_not_rebuild_composition")
    return by_worker


def render_case(case: dict[str, Any], out_dir, *, font_path=None, formats=("png",)):
    """Render supplied arms, supplied class members, and optional local zooms."""
    if not case.get("teams"):
        raise ValueError("case_needs_at_least_one_team")
    _configure_font(font_path or case.get("font_path"))
    _validate_members(case)
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    reference = case["reference"]
    ref_points, ref_floor = reference.get("points_1024x512"), reference.get("floor_xz_h")
    ref_geom = viewer_geometry(ref_points, ref_floor)
    geometries = [viewer_geometry((t.get("geometry") or {}).get("points"), (t.get("geometry") or {}).get("footprint")) for t in case["teams"]]
    bounds = _bounds([ref_geom] + geometries, case.get("view", {}).get("bev_bounds"))
    heights = _heights([ref_geom] + geometries)
    photo, photo_meta = None, {"status": "missing", "path": case.get("image_path")}
    if case.get("image_path") and Path(case["image_path"]).is_file():
        image_path = Path(case["image_path"])
        digest = hashlib.sha256(image_path.read_bytes()).hexdigest()
        if case.get("image_sha256") and case["image_sha256"] != digest:
            raise ValueError("original_image_sha256_mismatch")
        with Image.open(image_path) as im:
            dimensions = list(im.size)
            photo = np.asarray(im.convert("RGB"))
        photo_meta = {"status": "available", "path": str(image_path), "sha256": digest, "dimensions": dimensions}
    n = len(case["teams"])
    fig = plt.figure(figsize=(4.15 * n, 10.2))
    grid = fig.add_gridspec(3, n, height_ratios=(1.0, 1.5, 1.5), left=0.055, right=0.985,
                           top=0.89, bottom=0.085, wspace=0.25, hspace=0.22)
    for i, (team, geom) in enumerate(zip(case["teams"], geometries)):
        color = team.get("color", TEAM_COLORS[i % len(TEAM_COLORS)])
        ax = fig.add_subplot(grid[0, i])
        _erp_background(ax, photo)
        _erp_edges(ax, ref_points, REF_ERP_COLOR, linewidth=1.05, reference=True)
        _erp_edges(ax, (team.get("geometry") or {}).get("points"), color, linewidth=1.45, markers=True)
        ax.set_title(_team_header(team, i), fontsize=10, color=color, pad=10, linespacing=1.6)
        if i == 0:
            ax.set_ylabel("ERP", fontsize=10)
        ax = fig.add_subplot(grid[1, i])
        _bev_ring(ax, ref_floor, REF_COLOR, reference=True, linewidth=1.15)
        _highlight_reference(ax, ref_floor, case.get("highlight_reference_edges", []))
        _bev_ring(ax, geom.get("floor"), color, linewidth=1.8, zorder=7)
        _style_bev(ax, bounds)
        status = team.get("score_status", (team.get("geometry") or {}).get("status", "unknown"))
        ax.set_title("BEV  |  " + str(status), fontsize=8, pad=6, color="#515c6c")
        ax = fig.add_subplot(grid[2, i], projection="3d")
        _wire3d(ax, ref_geom, REF_COLOR, reference=True)
        _wire3d(ax, geom, color)
        _style3d(ax, bounds, heights, case.get("view", {}))
        if geom.get("ceiling_xyz") is None:
            ax.text2D(0.05, 0.95, "3D height unavailable", transform=ax.transAxes, color="#944558", fontsize=8)
        elif not geom.get("footprint_valid", False):
            ax.text2D(0.05, 0.95, "Invalid footprint: wire only", transform=ax.transAxes, color="#944558", fontsize=8)
    title = case.get("title", case.get("case_id", "Frozen composition comparison"))
    fig.suptitle(title, fontsize=15, x=0.055, y=0.98, ha="left", color="#1b2b40", weight="bold")
    if case.get("subtitle"):
        fig.text(0.055, 0.94, case["subtitle"], fontsize=9, color="#596777", ha="left")
    handles = [Line2D([0], [0], color=REF_COLOR, linestyle="--", label="Fixed reference"),
               Line2D([0], [0], color=REF_ERP_COLOR, linewidth=2, markeredgecolor="black", label="Reference in ERP")]
    handles += [Line2D([0], [0], color=t.get("color", TEAM_COLORS[i % len(TEAM_COLORS)]), label=str(t.get("label", chr(65 + i)))) for i, t in enumerate(case["teams"])]
    fig.legend(handles=handles, loc="lower left", bbox_to_anchor=(0.045, 0.035), ncol=min(6, n + 2), frameon=False, fontsize=8)
    fig.text(0.055, 0.012, "Shared axes and view. 3D uses camera height = 1; wall-top range is inferred from paired floor rays. "
             + ("Original image available." if photo is not None else "Original image missing; geometric figures retained."), fontsize=7, color="#626e7c")
    files = _save(fig, out, "comparison", formats)

    member_geometries = {}
    members = case.get("members", [])
    if members:
        classes = sorted({m.get("class_id", "unknown") for m in members})
        columns = min(4, len(classes))
        block_rows = math.ceil(len(classes) / columns)
        figure_height = 5.8 * block_rows + 1.0
        fig = plt.figure(figsize=(4.15 * columns, figure_height))
        grid = fig.add_gridspec(2 * block_rows, columns, height_ratios=[1, 1.65] * block_rows,
                               top=1 - 1.15 / figure_height, bottom=0.9 / figure_height,
                               left=0.05, right=0.98, hspace=0.26, wspace=0.26)
        for member in members:
            member_geometries[member["worker_id"]] = viewer_geometry(member.get("points"), member.get("footprint"))
        member_bounds = _bounds([ref_geom] + list(member_geometries.values()))
        for i, class_id in enumerate(classes):
            block, column = divmod(i, columns)
            group = [m for m in members if m.get("class_id", "unknown") == class_id]
            color = case.get("class_colors", {}).get(class_id, CLASS_COLORS[i % len(CLASS_COLORS)])
            old_n, new_n = sum(m.get("origin") == "v1" for m in group), sum(m.get("origin") == "new" for m in group)
            name = case.get("class_names", {}).get(class_id, class_id)
            ax = fig.add_subplot(grid[2 * block, column])
            _erp_background(ax, photo)
            for member in group:
                _erp_edges(ax, member.get("points"), color, linewidth=0.7, alpha=0.25)
            _erp_edges(ax, ref_points, REF_ERP_COLOR, linewidth=1, reference=True)
            ax.set_title(f"{class_id}  {name if name != class_id else ''}\nn={len(group)}  old={old_n}  new={new_n}", fontsize=9, color=color, pad=8)
            ax = fig.add_subplot(grid[2 * block + 1, column])
            for member in group:
                _bev_ring(ax, member_geometries[member["worker_id"]].get("floor"), color, linewidth=0.8, alpha=0.28)
            _bev_ring(ax, ref_floor, REF_COLOR, reference=True, linewidth=1.3)
            _style_bev(ax, member_bounds)
        fig.suptitle(case.get("member_overlay_title", case.get("case_id", "Case") + "  |  category-member overlays"), fontsize=14,
                     x=0.05, y=1 - 0.1 / figure_height, ha="left", color="#1b2b40", weight="bold")
        fig.text(0.05, 1 - 0.46 / figure_height, "Scope: " + case.get("member_scope", "provided case members") + "; n is actual supplied workers per class. Shared BEV axes.", fontsize=8, color="#65717e")
        fig.text(0.05, 0.08 / figure_height, "Each thin trace is one supplied person's declared ring. Fixed reference is dashed in BEV and yellow in ERP. "
                 "No participant is discarded by score for plotting.", fontsize=7, color="#65717e")
        files += _save(fig, out, "member_overlays", formats)

    zoom_bev, zoom_erp = case.get("zoom_bev"), case.get("zoom_erp")
    if zoom_bev is not None or zoom_erp is not None:
        rows = int(zoom_erp is not None) + int(zoom_bev is not None)
        fig = plt.figure(figsize=(4.15 * n, 3.5 * rows + 1.2))
        grid = fig.add_gridspec(rows, n, left=0.06, right=0.98, top=0.86, bottom=0.09, wspace=0.24, hspace=0.32)
        for i, (team, geom) in enumerate(zip(case["teams"], geometries)):
            color = team.get("color", TEAM_COLORS[i % len(TEAM_COLORS)])
            row = 0
            if zoom_erp is not None:
                ax = fig.add_subplot(grid[row, i])
                _erp_background(ax, photo, zoom_erp)
                _erp_edges(ax, ref_points, REF_ERP_COLOR, linewidth=1.3, reference=True)
                _erp_edges(ax, (team.get("geometry") or {}).get("points"), color, linewidth=1.7, markers=True)
                ax.set_title(str(team.get("label", chr(65 + i))) + "  ERP", fontsize=10, color=color)
                row += 1
            if zoom_bev is not None:
                ax = fig.add_subplot(grid[row, i])
                _bev_ring(ax, ref_floor, REF_COLOR, reference=True, linewidth=1.2)
                _highlight_reference(ax, ref_floor, case.get("highlight_reference_edges", []))
                _uncovered_reference(ax, ref_floor, team.get("diagnostics"))
                _bev_ring(ax, geom.get("floor"), color, linewidth=1.8, zorder=7)
                _style_bev(ax, zoom_bev)
                ax.set_title(str(team.get("label", chr(65 + i))) + "  BEV", fontsize=10, color=color)
        fig.suptitle(case.get("focus_title", "Local reference-structure review"), x=0.06, y=0.975,
                     ha="left", fontsize=14, color="#1b2b40", weight="bold")
        fig.text(0.06, 0.025, "r# labels are supplied fixed-reference edge indices. Magenta (when present): reference wall portions outside the separate 0.05-scale coverage diagnostic.",
                 fontsize=7, color="#667482")
        files += _save(fig, out, "local_zoom", formats)

    def geometry_receipt(g):
        return {key: g.get(key) for key in ("status", "reason", "floor_reconstruction_max_abs_difference", "footprint_valid", "vertical_pair_mismatch")}
    metadata = {
        "schema": "composition_case_visuals_v1", "case_id": case.get("case_id"),
        "case_sha256": hashlib.sha256(json.dumps(case, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()).hexdigest(),
        "renderer_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "reference_id": reference.get("reference_id"), "reference_version": reference.get("reference_version"),
        "image": photo_meta, "erp_coordinate_convention": "continuous x/W,y/H; W=1024,H=512; seam wrapped",
        "3d_construction": "Retain final/reference floor; top ray takes paired bottom horizontal range; floor H=0,camera H=1",
        "bev_bounds": bounds, "height_bounds": heights, "view": case.get("view", {}),
        "reference_geometry": geometry_receipt(ref_geom),
        "team_geometry": {str(t.get("label", i)): dict(geometry_receipt(g), team_key=t.get("team_key"),
            member_workers=t.get("member_workers"), member_object_ids=t.get("member_object_ids"), counts=t.get("counts"))
            for i, (t, g) in enumerate(zip(case["teams"], geometries))},
        "supplied_members": len(members), "member_scope": case.get("member_scope", "provided case members"),
        "member_geometry_status_counts": {status: sum(g.get("status") == status for g in member_geometries.values()) for status in ("ok", "unavailable")},
        "files": files,
    }
    (out / "render_manifest.json").write_text(json.dumps(metadata, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    return metadata


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--case", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--font", type=Path)
    parser.add_argument("--pdf", action="store_true")
    args = parser.parse_args()
    case = json.loads(args.case.read_text(encoding="utf-8"))
    if case.get("image_path") and not Path(case["image_path"]).is_absolute():
        case["image_path"] = str((args.case.parent / case["image_path"]).resolve())
    metadata = render_case(case, args.out, font_path=args.font, formats=("png", "pdf") if args.pdf else ("png",))
    print(json.dumps({"case_id": metadata["case_id"], "image_status": metadata["image"]["status"], "files": metadata["files"]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
