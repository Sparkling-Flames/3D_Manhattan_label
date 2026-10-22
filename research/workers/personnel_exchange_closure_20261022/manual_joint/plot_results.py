"""Publication-style static plots of the completed registered experiment."""
from __future__ import annotations
import os
os.environ.setdefault("MPLCONFIGDIR", "/tmp/hohonet_manual_plot_cache")
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from register_design import HERE


def main():
    summary = pd.read_csv(HERE / "CONDITION_SUMMARY.csv")
    d = summary[(summary.direction == "q_up__faster") & (summary.scope == "exact_n_m") & (summary.n.astype(str) == "20")].copy()
    d["m"] = d.m.astype(int)
    d = d.sort_values("m")
    x = np.arange(len(d))
    plt.rcParams.update({"font.size": 10, "axes.spines.top": False, "axes.spines.right": False, "figure.dpi": 160})
    fig, axes = plt.subplots(2, 2, figsize=(11, 8.2), constrained_layout=True)
    ax = axes[0,0]
    lo = d.sym_B8L2 - d.sym_B8L2_building_bootstrap_low
    hi = d.sym_B8L2_building_bootstrap_high - d.sym_B8L2
    ax.errorbar(x, d.sym_B8L2, yerr=[lo,hi], fmt="o-", color="#9b481f", lw=2, capsize=4)
    ax.axhline(0, color="0.6", lw=.8)
    ax.set_title("A. Quality gain versus the mean source team")
    ax.set_ylabel("C - (A+B)/2, B8L2 points")
    ax = axes[0,1]
    ax.bar(x, d.sym_recorded_time_logratio_geomean_pct, color="#357e91", width=.6)
    ax.axhline(0, color="0.6", lw=.8)
    ax.set_title("B. Recorded total-time change")
    ax.set_ylabel("C / mean(A,B) - 1 (%)")
    ax = axes[1,0]
    ax.bar(x-.18, d.common_quality_within_abs, width=.36, label="Same class: |B-A|", color="#99a5b0")
    ax.bar(x+.18, d.sym_cross_abs_B8L2, width=.36, label="Across class: mean(|C-A|,|C-B|)", color="#c56f42")
    ax.set_title("C. Magnitude of quality change")
    ax.set_ylabel("Absolute B8L2 change")
    ax.legend(fontsize=8, loc="upper left")
    ax = axes[1,1]
    qp=d.image_sym_quality_improved/d.image_sym_quality_known
    bp=d.image_sym_QT_both_improved/d.image_sym_QT_known
    ax.bar(x-.18, qp, width=.36, color="#566e3d", label="Quality improves")
    ax.bar(x+.18, bp, width=.36, color="#9bba80", label="Quality & time improve")
    for i,(q,b) in enumerate(zip(qp,bp)):
        ax.text(i-.18,q-.06,f"{int(d.image_sym_quality_improved.iloc[i])}/{int(d.image_sym_quality_known.iloc[i])}",ha="center",fontsize=8,color="white")
        ax.text(i+.18,b+.025,f"{int(d.image_sym_QT_both_improved.iloc[i])}/{int(d.image_sym_QT_known.iloc[i])}",ha="center",fontsize=8)
    ax.set_title("D. Image-level direction of the mean effect")
    ax.set_ylabel("Proportion of evaluable images")
    ax.set_ylim(0,1.18)
    ax.legend(fontsize=8,loc="lower left")
    labels=[f"m={m}\n{int(i)} imgs\n{int(b)} bldgs" for m,i,b in zip(d.m,d.images,d.buildings)]
    for ax in axes.flat:
        ax.set_xticks(x,labels,fontsize=8)
        ax.grid(axis="y",alpha=.18)
    fig.suptitle("Manual joint classes: n=20, higher historical Q / relatively faster target",fontsize=13)
    figures=HERE/"figures"
    figures.mkdir(exist_ok=True)
    fig.savefig(figures/"MANUAL_N20_CONDITIONS.png",dpi=220)
    fig.savefig(figures/"MANUAL_N20_CONDITIONS.pdf")
    plt.close(fig)
    d.to_csv(figures/"MANUAL_N20_PLOT_VALUES.csv",index=False,encoding="utf-8-sig")


if __name__ == "__main__":
    main()
