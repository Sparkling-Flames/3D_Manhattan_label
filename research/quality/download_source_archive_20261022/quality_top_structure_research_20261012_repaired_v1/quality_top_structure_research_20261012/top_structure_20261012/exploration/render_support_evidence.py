#!/usr/bin/env python3
from __future__ import annotations
import argparse
import csv
import hashlib
import json
from pathlib import Path
import numpy as np


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--results", type=Path, default=Path(__file__).resolve().parent / "results")
    args = ap.parse_args()
    out = args.results.resolve()
    figs = out.parent / "figures"
    figs.mkdir(parents=True, exist_ok=True)
    rows = list(csv.DictReader((out / "amplitude_support_all_110_rows.csv").open(encoding="utf-8-sig")))
    by = {r["case_id"]: r for r in rows}
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    ids = ["spike_narrow_support2e-05", "spike_narrow_support0.0002", "spike_support0.002_amp1.44", "spike_support0.02_amp1.44", "spike_support0.2_amp1.44"]
    p = np.array([.00002, .0002, .002, .02, .2])
    records = [by[c] for c in ids]
    fig, axs = plt.subplots(1, 2, figsize=(11.7, 4.6), constrained_layout=True)
    axs[0].plot(p*100, [float(r["annotation_height_range_over_gt_mean"]) for r in records], "o-", label="exact height span / GT mean")
    axs[0].plot(p*100, [float(r["Hstar"]) for r in records], "s--", label="existing Hstar")
    axs[0].set_ylabel("relative height quantity")
    axs[0].set_ylim(-.01, .65)
    for level, color in [(10, "#236a9f"), (20, "#af6b23"), (40, "#695091")]:
        axs[1].plot(p*100, [float(r[f"annotation_support_gtmean_{level}"])*100 for r in records], "o-", color=color, label=f"|height - own mean| > {level}% of GT mean")
    axs[1].set_yscale("log")
    axs[1].set_ylabel("exact affected floor perimeter (%)")
    for ax in axs:
        ax.set_xscale("log")
        ax.set_xlabel("floor perimeter occupied by triangular spike (%)")
        ax.grid(alpha=.25)
        ax.legend(fontsize=8)
    fig.suptitle("Same 1.44 h peak, different spatial support: amplitude and extent are reported together", fontsize=11)
    fig.savefig(figs / "spike_amplitude_and_exact_support.png", dpi=180)
    plt.close(fig)

    ids = ["T20", "S034", "S107", "S071", "T19", "S001"]
    records = [by[c] for c in ids]
    x = np.arange(len(ids))
    fig, axs = plt.subplots(1, 3, figsize=(14.4, 4.7), constrained_layout=True)
    axs[0].bar(x, [float(r["Hmean"]) for r in records], color="#3b5f78", width=.65)
    axs[0].set_title("Global mean height bias", fontsize=10)
    axs[0].set_ylabel("Hmean")
    axs[1].bar(x-.17, [float(r["annotation_height_range_over_gt_mean"]) for r in records], width=.34, color="#268c88", label="annotation")
    axs[1].bar(x+.17, [float(r["reference_height_range_over_gt_mean"]) for r in records], width=.34, color="#9b9b9b", label="reference")
    axs[1].set_title("Exact local height span", fontsize=10)
    axs[1].set_ylabel("(max - min) height / GT mean")
    axs[1].legend(fontsize=8)
    for index, (level, color) in enumerate([(10, "#236a9f"), (20, "#af6b23"), (40, "#695091")]):
        axs[2].bar(x+(index-1)*.25, [float(r[f"annotation_support_gtmean_{level}"])*100 for r in records], width=.25, color=color, label=f"> {level}% of GT mean")
    axs[2].set_title("Centered deviation: exact support", fontsize=10)
    axs[2].set_ylabel("floor perimeter (%)")
    axs[2].legend(fontsize=8)
    for ax in axs:
        ax.set_xticks(x, ids, rotation=35)
        ax.grid(axis="y", alpha=.2)
        ax.set_axisbelow(True)
    fig.suptitle("Conditional development evidence: local diagnostics do not replace global, scope or structure quality", fontsize=11)
    fig.savefig(figs / "real_height_amplitude_support.png", dpi=180)
    plt.close(fig)
    manifest = {"figures": [{"path": p.name, "bytes": p.stat().st_size, "sha256": hashlib.sha256(p.read_bytes()).hexdigest()} for p in sorted(figs.glob("*.png"))],
                "research_figures_not_blind_review_questions": True,
                "display_levels_are_not_human_thresholds": True}
    (figs / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print(json.dumps(manifest, indent=2))


if __name__ == "__main__":
    main()
