"""Render the two journal method figures from the existing controlled examples."""
import argparse
from pathlib import Path
import sys

import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from matplotlib.patches import Polygon
from matplotlib.transforms import Bbox
import numpy as np

import draw_consensus_method_illustration_20261114 as consensus

REPO = Path(__file__).resolve().parents[3]
PAPERS = REPO / "docs/thesis_main"
sys.path.insert(0, str(PAPERS / "论文提纲_LaTeX_20261028/figure_package/source/quality_endpoint"))
import build_quality as quality


def render_quality(out):
    folder = out / "quality_endpoint"
    folder.mkdir(parents=True, exist_ok=True)
    for kind, delta, layout in quality.formal_examples():
        lower = kind == "lower"
        metrics = quality.score(layout)
        assert np.isclose(metrics["Q"], quality.E.score(layout, quality.REF, 8192, 16384)["Q"], atol=.01)
        assert lower == (metrics["Ddir_deg"] > 1e-6)
        fig = plt.figure(figsize=(10, 2.55))
        edit = fig.add_axes([.033, .11, .155, .81])
        quality.draw_edit(edit, kind, delta, show_pixels=False)
        plan = fig.add_axes([.19, .15, .20, .75])
        quality.draw_plan(plan, layout, arrow=lower)
        if lower:
            midpoint = layout.xz[[1, 2]].mean(axis=0)
            plan.annotate("Wall direction", xy=midpoint, xytext=(.15, -.70), ha="center",
                          color=quality.ORANGE, fontsize=10,
                          arrowprops=dict(arrowstyle="-", color=quality.ORANGE, lw=.8))
        plan.text(.5, -.065, "Footprint expands" if lower else "Footprint unchanged",
                  transform=plan.transAxes, ha="center", fontsize=10)
        room = fig.add_axes([.395, .045, .245, .91])
        _, top = quality.draw_room(room, layout, highlight=True)
        room.annotate(f"Local height\n3.00 → {layout.heights[quality.K]:.2f} m",
                      xy=top[quality.K], xytext=(1.0, 4.7), ha="center", va="center",
                      color=quality.ORANGE, fontsize=10,
                      arrowprops=dict(arrowstyle="-", color=quality.ORANGE, lw=.8))
        quality.measurements(fig.add_axes([.665, .09, .32, .82]), metrics)
        fig.savefig(folder / f"{kind}.pdf")
        plt.close(fig)
    fig = plt.figure(figsize=(10, .32))
    handles = [Line2D([], [], color=quality.GRAY, ls="--", label="Reference"),
               Line2D([], [], color=quality.BLUE, label="Edited layout"),
               Line2D([], [], color=quality.ORANGE, label="Changed geometry"),
               Line2D([], [], ls="", marker="o", color=quality.BLUE, label="Fixed image endpoint")]
    fig.legend(handles=handles, loc="center", ncol=4, frameon=False, fontsize=10)
    fig.savefig(folder / "legend.pdf")
    plt.close(fig)


def render_consensus(out):
    folder = out / "consensus_method"
    folder.mkdir(parents=True, exist_ok=True)
    result = consensus.run_pipeline(consensus.simulate(), consensus.G_SKIP)
    groups = {g["id"]: g for g in result["groups"]}
    focus = next(g for g in groups.values() if g["truth"] == "R2")
    members = [result["flat"][i] for i in focus["members"]]
    assert focus["retained"] and len(members) == 3
    layout = consensus.layout(result)
    fig = plt.figure(figsize=(8, 2.05))
    ax = fig.add_axes([0, 0, 1, 1], xlim=(0, 8), ylim=(0, 2.05), aspect="equal")
    ax.axis("off")
    # Rigid oblique view of the computed rings, with the illustrated recess facing the reader.
    x = np.array([p["x"] - .48*p["z"] for p in layout])
    y = np.array([-.44*p["z"] for p in layout])
    floor = np.column_stack((x, y-1.2))
    upper = np.column_stack((x, y + 1.2*np.array([p["top"] for p in layout])))
    points = np.vstack((floor, upper))
    lo, hi = points.min(axis=0), points.max(axis=0)
    scale = min(3.15/(hi[0]-lo[0]), 1.65/(hi[1]-lo[1]))
    origin = np.array([4.83, .16])
    floor, upper = (origin+(ring-lo)*scale for ring in (floor, upper))
    ax.fill(*floor.T, color="#F2F4F5")
    for j, p in enumerate(layout):
        k = (j+1) % len(layout)
        if all(groups[layout[i]["id"]]["truth"].startswith("R") for i in (j, k)):
            ax.add_patch(Polygon([floor[j], floor[k], upper[k], upper[j]], fc="#D9EDF5", ec="none"))
        ax.plot([floor[j,0], upper[j,0]], [floor[j,1], upper[j,1]], color="#A4ABAF", lw=.9)
    for ring in (floor, upper):
        ax.plot(*np.vstack((ring, ring[0])).T, color="#697277", lw=1)
    k = next(j for j,p in enumerate(layout) if p["id"] == focus["id"])
    top, bottom = upper[k], floor[k]
    middle = (top+bottom)/2
    orange = consensus.ORANGE
    ax.plot([top[0], bottom[0]], [top[1], bottom[1]], color=orange, lw=2.7, zorder=7)
    ax.scatter([top[0],bottom[0]], [top[1],bottom[1]], s=27, c=orange, zorder=8)
    ax.annotate("K", top, xytext=(5,4), textcoords="offset points", color=orange,
                fontsize=11, fontweight="bold")
    colors = {"A1":consensus.BLUE, "A2":"#007D62", "A3":"#87549C"}
    for x_pos, title in zip([1.67, 2.57, 3.47], ["Low", "Median", "High"]):
        ax.text(x_pos, 1.93, title, ha="center", fontsize=10,
                color=orange if title == "Median" else "#50595D")
    for key, label, row, target, caption_owner in [
        ("up", "Upper elevation", 1.53, top, "A1"),
        ("az", "Shared azimuth", .95, middle, "A1"),
        ("low", "Lower elevation", .37, bottom, "A3")
    ]:
        def value(obs):
            return float(consensus.wrap(obs[key]-focus[key])) if key=="az" else obs[key]
        ordered = sorted(members, key=value)
        assert np.isclose(value(ordered[1]), 0 if key=="az" else focus[key])
        assert ordered[1]["annotator"] == caption_owner
        ax.text(.06, row, label, va="center", fontsize=10)
        for i, obs in enumerate(ordered):
            person = obs["annotator"]
            xx = 1.49 + .9*i
            ax.plot(xx, row, consensus.SHAPES[person], mfc="white", mec=colors[person],
                    mew=1.4, ms=6.5)
            ax.text(xx+.12, row, person, color=colors[person], va="center", fontsize=10)
        ax.add_patch(plt.Rectangle((2.28,row-.12), .60, .24, fill=False, ec=orange, lw=1))
        route = row+.18
        ax.plot([2.88,3.02,3.94], [row+.07,route,route], color=orange, lw=1)
        ax.annotate("", xy=target, xytext=(3.94,route),
                    arrowprops=dict(arrowstyle="->", color=orange, lw=1, shrinkA=0, shrinkB=2))
    # Split one vector drawing at the gutter so LaTeX can typeset both captions below.
    for name, left, right in [("c_position",0,4.64),("d_layout",4.64,8)]:
        fig.savefig(folder / f"{name}.pdf", bbox_inches=Bbox.from_extents(left,0,right,2.05))
    plt.close(fig)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path, help="destination panels directory")
    args = parser.parse_args()
    render_quality(args.output)
    render_consensus(args.output)
