"""Render controlled geometry examples for Fig. 4.

Only illustrative geometry is evaluated. No empirical result is recalculated.
The scoring functions in controlled_q_engine.py are copied unchanged from the
archived eight-case geometry supplement; their B8L2 expression matches the
current manuscript's Q definition. Requires numpy, pandas, shapely, matplotlib.
"""
from pathlib import Path
import argparse
import csv
import hashlib
import importlib.util
import json
import math
import shutil
import sys

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Polygon, Rectangle
from matplotlib.lines import Line2D


HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("controlled_q_engine", HERE / "controlled_q_engine.py")
engine = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = engine
spec.loader.exec_module(engine)

BLUE, ORANGE, GRAY = "#0072B2", "#D55E00", "#585858"
INK = "#202020"
plt.rcParams.update({
    "font.family": "Liberation Sans", "font.size": 8.2,
    "text.color": INK, "axes.labelcolor": INK,
    "pdf.fonttype": 42, "ps.fonttype": 42, "svg.fonttype": "none",
    "mathtext.fontset": "dejavusans", "axes.unicode_minus": False,
    "savefig.facecolor": "white",
})


def close(points):
    return np.vstack([points, points[0]])


def canvas():
    # 0.24 of the unchanged elsarticle text width; fonts are sized for print.
    fig = plt.figure(figsize=(44.03 / 25.4, 47.0 / 25.4))
    ax = fig.add_axes([.04, .30, .92, .68])
    ax.set_aspect("equal")
    ax.set_axis_off()
    return fig, ax


def write_outputs(fig, stem):
    for extension in ("pdf", "svg", "png"):
        fig.savefig(stem.with_suffix("." + extension), dpi=600,
                    metadata={"Creator": "Matplotlib; controlled geometry source included"}
                    if extension == "pdf" else None)
    plt.close(fig)


def metrics(fig, row, color, detail):
    fig.text(.04, .155, detail, ha="left", va="center", fontsize=7.7,
             linespacing=1.35)
    fig.text(.96, .035, f"Q = {row['Q']:.2f}", ha="right", va="center",
             color=color, weight="bold", fontsize=9.6)


def extent_panel(job, row, color, out):
    fig, ax = canvas()
    r, p = job["reference"], job["assessed"]
    d = job["parameter_m"]
    xmax = 2 - d
    ax.add_patch(Rectangle((-2, -2), 4, 4, facecolor="#F5F5F5", edgecolor="none"))
    ax.add_patch(Rectangle((xmax, -2), d, 4, facecolor="#FFFFFF", hatch="////",
                           edgecolor="#BABABA", linewidth=0, zorder=2))
    ax.add_patch(Polygon(p.xz, facecolor=color, alpha=.12, edgecolor="none", zorder=3))
    ax.plot(*close(r.xz).T, color=GRAY, lw=1.05, dashes=(3.2, 2.0), zorder=4)
    ax.plot(*close(p.xz).T, color=color, lw=1.8, zorder=5)
    ax.scatter(*p.xz.T, color=color, s=13, zorder=6)
    ax.scatter([0], [0], color=INK, marker="+", s=32, linewidths=1.1, zorder=6)
    ax.text(0, -.37, "camera", ha="center", va="top", fontsize=7.5)
    if d < .6:
        # External dimension arrows keep the short 0.4 m interval legible.
        for endpoint, start in [(xmax, xmax - .45), (2, 2 + .45)]:
            ax.annotate("", xy=(endpoint, 2.35), xytext=(start, 2.35),
                        arrowprops={"arrowstyle": "-|>", "color": color, "lw": .7,
                                    "shrinkA": 0, "shrinkB": 0, "mutation_scale": 5})
    else:
        ax.annotate("", xy=(2, 2.35), xytext=(xmax, 2.35),
                    arrowprops={"arrowstyle": "<->", "color": color, "lw": .8,
                                "shrinkA": 0, "shrinkB": 0, "mutation_scale": 5})
    ax.plot([xmax, xmax], [2.05, 2.44], color=color, lw=.6)
    ax.plot([2, 2], [2.05, 2.44], color=GRAY, lw=.6)
    ax.text((xmax + 2) / 2, 2.59, f"{d:.1f} m", color=color,
            ha="center", va="bottom", fontsize=8.0)
    ax.annotate("", xy=(-2, -2.38), xytext=(2, -2.38),
                arrowprops={"arrowstyle": "<->", "color": GRAY, "lw": .7,
                            "shrinkA": 0, "shrinkB": 0, "mutation_scale": 6})
    ax.text(0, -2.58, "4 m", color=GRAY, ha="center", va="top", fontsize=7.5)
    ax.set_xlim(-2.55, 2.55)
    ax.set_ylim(-2.95, 3.05)
    metrics(fig, row, color,
            f"Floor IoU = {row['iou2d100']:.0f}%\nBoundary distance = {row['Sb_deg']:.2f}°")
    write_outputs(fig, out)


def project(layout):
    x, z = layout.xz.T
    floor = np.column_stack([.76 * x + .50 * z, -.23 * x + .39 * z])
    top = floor + np.column_stack([np.zeros(len(x)), .88 * layout.heights])
    return floor, top


def height_panel(job, row, color, out):
    fig, ax = canvas()
    r, p = job["reference"], job["assessed"]
    rb, rt = project(r)
    pb, pt = project(p)
    ax.add_patch(Polygon(pb, facecolor="#F1F1F1", edgecolor=GRAY, lw=.65, zorder=1))
    # The illustrative upper face is planar: height varies linearly in x.
    ax.add_patch(Polygon(pt, facecolor=color, alpha=.12, edgecolor="none", zorder=2))
    for a, b in [(0, 1), (1, 2)]:
        ax.add_patch(Polygon(np.vstack([pb[a], pb[b], pt[b], pt[a]]),
                            facecolor=color, alpha=.05, edgecolor="none", zorder=1))
    for b, t in zip(rb, rt):
        ax.plot([b[0], t[0]], [b[1], t[1]], color=GRAY, lw=.8,
                dashes=(3.0, 2.0), zorder=3)
    ax.plot(*close(rt).T, color=GRAY, lw=1.1, dashes=(3.0, 2.0), zorder=4)
    for b, t in zip(pb, pt):
        ax.plot([b[0], t[0]], [b[1], t[1]], color=color, lw=1.05, zorder=4)
    ax.plot(*close(pt).T, color=color, lw=1.8, zorder=5)
    ax.scatter(*pt.T, color=color, s=13, zorder=6)
    for k, xytext, align in [(0, (-2.8, 3.65), "left"), (2, (2.8, 5.0), "right")]:
        # Exact corner heights, not arbitrary graphic offsets or invented scores.
        ax.annotate(f"{p.heights[k]:.1f} m", xy=pt[k], xytext=xytext,
                    fontsize=8.2, color=color, ha=align, va="center",
                    arrowprops={"arrowstyle": "-", "color": color,
                                "lw": .7, "shrinkA": 3, "shrinkB": 3})
    # Same projection and limits in both height examples.
    ax.set_xlim(-3.1, 3.1)
    ax.set_ylim(-1.55, 5.35)
    metrics(fig, row, color,
            f"Mean height = 3.00 m\nLocal height error = {row['Hcenter']:.3f}")
    write_outputs(fig, out)


def make_legend(out):
    fig = plt.figure(figsize=(150.44 / 25.4, 7.0 / 25.4))
    fig.legend(handles=[
        Line2D([], [], color=GRAY, lw=1.1, dashes=(3.0, 2.0), label="Reference"),
        Line2D([], [], color=BLUE, lw=1.8, marker="o", ms=3, label="Smaller change"),
        Line2D([], [], color=ORANGE, lw=1.8, marker="o", ms=3, label="Larger change"),
    ], loc="center", ncol=3, frameon=False, handlelength=2.4, columnspacing=2.2,
       fontsize=8.0)
    write_outputs(fig, out)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--package-root", type=Path,
                        default=HERE.parents[1])
    args = parser.parse_args()
    root = args.package_root.resolve()
    panel_dir, data_dir = root / "panels/fig04", root / "data/fig04"
    panel_dir.mkdir(parents=True, exist_ok=True)
    data_dir.mkdir(parents=True, exist_ok=True)
    reference = engine.flat(engine.square())
    jobs = []
    for label, d in [("a", .4), ("b", 1.2)]:
        jobs.append({"panel": label, "kind": "one_wall_inward", "parameter_m": d,
                     "reference": reference,
                     "assessed": engine.flat(engine.rectangle(-2, 2-d, -2, 2))})
    for label, amplitude in [("c", .3), ("d", 1.2)]:
        jobs.append({"panel": label, "kind": "balanced_height_tilt", "parameter_m": amplitude,
                     "reference": reference,
                     "assessed": engine.Layout(engine.square(),
                                               3 + amplitude * engine.square()[:, 0] / 2)})
    rows, coordinates, convergence = [], [], []
    for job in jobs:
        m = engine.score(job["assessed"], job["reference"], nb=2048, nh=4096)
        row = {"panel": job["panel"], "kind": job["kind"],
               "parameter_m": job["parameter_m"], **m}
        rows.append(row)
        coordinates.append({"panel": job["panel"], "kind": job["kind"],
                            "parameter_m": job["parameter_m"],
                            "reference": job["reference"].data(),
                            "assessed": job["assessed"].data()})
        higher = engine.score(job["assessed"], job["reference"], nb=8192, nh=16384)
        convergence.append({"panel": job["panel"],
                            "abs_Q_difference": abs(higher["Q"]-m["Q"]),
                            "abs_Sb_deg_difference": abs(higher["Sb_deg"]-m["Sb_deg"]),
                            "abs_Hc_difference": abs(higher["Hcenter"]-m["Hcenter"])})
        color = BLUE if job["panel"] in ("a", "c") else ORANGE
        draw = extent_panel if job["kind"] == "one_wall_inward" else height_panel
        draw(job, row, color, panel_dir / ("fig04_" + job["panel"]))
    make_legend(panel_dir / "fig04_legend")
    with (data_dir / "illustrative_cases.csv").open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]))
        writer.writeheader(); writer.writerows(rows)
    (data_dir / "illustrative_geometry.json").write_text(json.dumps({
        "type": "controlled illustrative geometry, not participant data",
        "units": "metres", "camera_height_m": engine.CAMERA_HEIGHT,
        "sample_counts": {"boundary_per_direction": 2048, "height_per_direction": 4096},
        "cases": coordinates}, ensure_ascii=False, indent=2), encoding="utf-8")
    checks = {
        "formula": "100 / (1 + hypot((1/I - 1) + Sb^2/32, 1.5*D^2/(D^2+8^2)) + (Hm/0.8)^2 + (Hc/0.25)^2)",
        "engine_sha256": hashlib.sha256((HERE / "controlled_q_engine.py").read_bytes()).hexdigest(),
        "reference_self_Q": engine.score(reference, reference)["Q"],
        "floor_iou_exact_error": max(abs(rows[i]["iou2d100"] - (100 - 25*jobs[i]["parameter_m"])) for i in (0, 1)),
        "local_height_analytic_error": max(abs(rows[i]["Hcenter"] - jobs[i]["parameter_m"] / 3 * math.sqrt(2/3)) for i in (2, 3)),
        "controlled_sample_convergence": convergence,
        "all_scores_between_0_and_100": all(0 <= r["Q"] <= 100 for r in rows),
        "empirical_results_recomputed": False,
        "no_baked_panel_labels_or_titles": True,
    }
    checks["max_Q_change_at_fourfold_sampling"] = max(c["abs_Q_difference"] for c in convergence)
    assert checks["floor_iou_exact_error"] < 1e-10
    assert checks["local_height_analytic_error"] < 1e-6
    assert checks["max_Q_change_at_fourfold_sampling"] < .005
    (data_dir / "verification.json").write_text(json.dumps(checks, indent=2), encoding="utf-8")
    print(json.dumps({"panels": len(jobs), "scores": [{"panel": r["panel"], "Q": r["Q"]} for r in rows],
                      "max_Q_sampling_difference": checks["max_Q_change_at_fourfold_sampling"]}, indent=2))


if __name__ == "__main__":
    main()
