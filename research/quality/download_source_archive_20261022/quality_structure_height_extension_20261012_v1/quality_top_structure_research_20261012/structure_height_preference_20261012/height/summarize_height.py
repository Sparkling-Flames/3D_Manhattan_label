#!/usr/bin/env python3
"""Mechanism comparisons, parity audit and scientific figures (no label fitting)."""
from pathlib import Path
import json
import csv
import math
import itertools
import numpy as np
from score_existing import dump, csvwrite, csvread, sha
from candidate_functions import NEW_METHODS

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
OUT = HERE / "results"
SHOW = ["Q_v11", "Q_official_iou3d", "Q_no_topS", "Q_hsplit_top0", "Q_dbounded1_hsplit", "Q_dbounded1_hsplit_weakTop", "Q_dbounded2_hsplit", "Q_dbounded1_d10_hsplit", "Q_dunbounded_hsplit", "Q_dbounded1_hsplit_logMean"]


def main():
    real = json.loads((OUT / "candidate_scores_39.json").read_text())
    by = {r["case_id"]:r for r in real}
    initial = json.loads((OUT / "initial15_before_log_addendum/candidate_scores_39.json").read_text())
    initial_methods = [r["name"] for r in json.loads((OUT / "initial15_before_log_addendum/candidate_config.json").read_text())["candidates"]]
    initial_by = {r["record_id"]:r for r in initial}
    errors = [abs(r[k]-initial_by[r["record_id"]][k]) for r in real for k in initial_methods]
    assert max(errors) == 0
    ratio_errors = [abs(abs(r["height_mean_ratio"]-1)-r["Hmean"]) for r in real]
    assert max(ratio_errors) < 1e-12
    dump(OUT / "initial15_parity_after_log_append.json", {"records":len(real),"methods":len(initial_methods),
         "comparisons":len(errors),"maximum_absolute_score_change":max(errors),
         "maximum_absolute_Hmean_vs_actual_ratio_difference":max(ratio_errors),
         "old_config_sha256":sha(OUT / "initial15_before_log_addendum/candidate_config.json"),
         "current_initial_config_sha256":sha(HERE / "candidate_config.json"),
         "all_old_results_retained":True,"log_ratio_never_inferred_from_absolute_Hmean":True})
    key_ids = ["T01","T02","T20","T09","T22","T19","S034","S071","S107","S001"]
    key_rows = [{k:by[c].get(k) for k in ["case_id","record_id","image_code","iou_2d","dir","flat","Hmean","Hcenter","height_mean_ratio","S_top_deg","S_bottom_deg"]+SHOW} for c in key_ids]
    csvwrite(OUT / "key_real_comparison.csv", key_rows)

    matched = csvread(OUT / "matched_control_scores.csv")
    keyed = {r["case_id"]:r for r in matched}
    comparison_rows = []
    for scale in [.5,2.,10.]:
        for eps in [.05,.1,.2]:
            modes = {mode:keyed[f"matched_s{scale:g}_e{eps:g}_{mode}"] for mode in ["structure_shear","local_tilt","local_alternating","global_down","global_up"]}
            for method in SHOW:
                q = {mode:float(r[method]) for mode,r in modes.items()}
                comparison_rows.append({"floor_scale":scale,"matched_relative_top_boundary_rms_displacement":eps,
                    "method":method, **q,
                    "wall_corner_departure_deg":float(modes["structure_shear"]["shear_corner_departure_deg"]),
                    "structure_before_tilt_before_both_global":q["structure_shear"] < q["local_tilt"] < min(q["global_down"],q["global_up"]),
                    "structure_before_alternating_before_both_global":q["structure_shear"] < q["local_alternating"] < min(q["global_down"],q["global_up"]),
                    "counts_are_geometric_controls_not_human_agreement":True})
    csvwrite(OUT / "matched_geometric_penalty_order.csv", comparison_rows)
    counts = [{"method":method,"geometric_conditions":9,
        "tilt_order_count":sum(r["structure_before_tilt_before_both_global"] for r in comparison_rows if r["method"]==method),
        "alternating_order_count":sum(r["structure_before_alternating_before_both_global"] for r in comparison_rows if r["method"]==method)} for method in SHOW]
    csvwrite(OUT / "matched_order_counts_not_human_accuracy.csv", counts)
    old = csvread(OUT / "candidate_scores_prior_height71.csv")
    ids = ["equal_mean_tilted_plane_amp0.72", "equal_mean_alternating_corners_amp0.72", "spike_support0.002_amp1.44", "spike_narrow_support2e-05",
           "far_corner_scale50_bottom_delta-1", "joint_y_scale10_height_preserving_compensation", "nearest_tie_shift-1e-06", "nearest_tie_shift0", "nearest_tie_shift1e-06"]
    selected_old = [r for r in old if r["case_id"] in ids]
    csvwrite(OUT / "reused_mechanism_counterexamples.csv", [{k:r.get(k) for k in ["case_id","status","iou_2d","dir","flat","Hmean","Hcenter","S_top_deg","S_bottom_deg"]+SHOW} for r in selected_old])

    pool = json.loads((OUT / "development907_candidates.json").read_text())
    effects = []
    for subset_name, rs in [("all907_conditional",pool),("explicit143",[r for r in pool if r["applicability_confirmed"]]),("unknown764",[r for r in pool if not r["applicability_confirmed"]])]:
        for other,label in [("Q_dbounded1_hsplit_weakTop","weak_top_added"),("Q_dbounded1_Fguard","old_F_restored"),("Q_dbounded1_hsplit_logMean","global_log_replaces_absolute_relative")]:
            delta=np.array([r[other]-r["Q_dbounded1_hsplit"] for r in rs])
            effects.append({"subset":subset_name,"contrast":label,"denominator":len(rs),"delta_min":float(delta.min()),"delta_median":float(np.median(delta)),"delta_max":float(delta.max()),
                "absolute_change_ge2":int((np.abs(delta)>=2).sum()),"absolute_change_ge5":int((np.abs(delta)>=5).sum()),"absolute_change_ge10":int((np.abs(delta)>=10).sum()),
                "human_quality_improvement_not_asserted":True})
    csvwrite(OUT / "development907_candidate_ablation_effects.csv",effects)
    logrows = []
    for r in real:
        logrows.append({"case_id":r["case_id"],"record_id":r["record_id"],"image_code":r["image_code"],"height_mean_ratio":r["height_mean_ratio"],
            "relative_mean_error":r["Hmean"],"log_mean_error":abs(math.log(r["height_mean_ratio"])),
            "Q_relative":r["Q_dbounded1_hsplit"],"Q_log":r["Q_dbounded1_hsplit_logMean"],"delta":r["Q_dbounded1_hsplit_logMean"]-r["Q_dbounded1_hsplit"]})
    csvwrite(OUT / "log_mean_real39_appendix.csv",logrows)

    # Figures retain numerical axes; synthetic severity is never labeled by human grade.
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    figdir=HERE/"figures";figdir.mkdir(exist_ok=True)
    colors={"Q_v11":"#a0a0a0","Q_hsplit_top0":"#4d7992","Q_dbounded1_hsplit":"#177e6a","Q_dbounded1_d10_hsplit":"#b57528","Q_official_iou3d":"#99586e"}
    labels={"Q_v11":"v1.1","Q_hsplit_top0":"split height + old C","Q_dbounded1_hsplit":"bounded D (5 deg) + split","Q_dbounded1_d10_hsplit":"bounded D (10 deg) + split","Q_official_iou3d":"official IoU3D"}
    fig,axs=plt.subplots(1,3,figsize=(14,4.7),sharey=True,constrained_layout=True)
    mode_names=["structure_shear","local_tilt","global_down"]
    for ax,scale in zip(axs,[.5,2.,10.]):
        x=np.arange(3)
        for j,method in enumerate(colors):
            values=[float(keyed[f"matched_s{scale:g}_e0.1_{mode}"][method]) for mode in mode_names]
            ax.plot(x,values,"o-",color=colors[method],label=labels[method],lw=1.6,ms=4)
        angle=float(keyed[f"matched_s{scale:g}_e0.1_structure_shear"]["shear_corner_departure_deg"])
        ax.set_title(f"Floor scale {scale:g}; wall departure {angle:.2f} deg",fontsize=10)
        ax.set_xticks(x,["wall shear","local tilt","global down"]);ax.grid(alpha=.2);ax.set_ylim(0,103)
    axs[0].set_ylabel("Score (no human grades assigned)")
    axs[1].legend(fontsize=7,loc="lower center")
    fig.suptitle("Equal top-boundary RMS displacement / reference wall height = 10%\nThe severity order depends on geometric scale; it is not a universal weight inequality",fontsize=11)
    fig.savefig(figdir/"matched_structure_local_global.png",dpi=180);plt.close(fig)

    methods=[("Q_hsplit_top0","no top S + split"),("Q_hsplit_top1_16","weak top S + split"),("Q_dbounded1_hsplit","bounded D + split"),("Q_dbounded1_d10_hsplit","bounded D10 + split"),("Q_dbounded2_hsplit","double D cap + split")]
    cids=["T20","T09","T22","T19","S034","S071","S107"]
    fig,ax=plt.subplots(figsize=(12,5),constrained_layout=True)
    x=np.arange(len(cids))
    ax.plot(x,[by[c]["Q_v11"] for c in cids],"o--",label="v1.1",color="0.5")
    ax.plot(x,[by[c]["Q_official_iou3d"] for c in cids],"s--",label="official IoU3D",color="#99586e")
    for method,label in methods:ax.plot(x,[by[c][method] for c in cids],"o-",label=label,lw=1.2,ms=4)
    ax.set_xticks(x,cids);ax.set_ylim(0,100);ax.set_ylabel("Score");ax.grid(alpha=.2);ax.legend(ncol=2,fontsize=8)
    ax.set_title("Conditional development examples: differences of methods, not new human grades",fontsize=11)
    fig.savefig(figdir/"real_height_structure_candidates.png",dpi=180);plt.close(fig)

    fig,axs=plt.subplots(1,2,figsize=(11.5,4.7),constrained_layout=True)
    for ax,scale in zip(axs,[.5,10.]):
        rs=[r for r in matched if r["family"]=="global_height_extreme" and float(r["horizontal_scale"])==scale and r["camera_inside_height_assumption"]=="True"]
        for method,label in [("Q_v11","v1.1"),("Q_dbounded1_hsplit","absolute relative mean, scale .5"),("Q_dbounded1_mean1","absolute relative mean, scale 1"),("Q_dbounded1_hsplit_logMean","absolute log ratio, scale .5"),("Q_official_iou3d","official IoU3D")]:
            ax.plot([float(r["wall_height_ratio"]) for r in rs],[float(r[method]) for r in rs],"o-",label=label,ms=4)
        ax.set_title(f"Horizontal scale {scale:g}; all boundary tops above camera",fontsize=10)
        ax.set_xscale("log");ax.set_xticks([.5,1,1.5,2,3,5],["0.5","1","1.5","2","3","5"]);ax.set_ylim(0,102);ax.set_xlabel("Annotation / reference mean wall height");ax.grid(alpha=.2)
    axs[0].set_ylabel("Score");axs[1].legend(fontsize=7)
    fig.suptitle("Uniform horizontal ceilings: an adaptive multiplicative-height comparison\nNeither equal relative errors nor equal height ratios define a human grade",fontsize=11)
    fig.savefig(figdir/"global_height_limits_and_log_comparison.png",dpi=180);plt.close(fig)
    dump(figdir/"manifest.json",{"scientific_figures_not_blind_review":True,"figures":[{"path":p.name,"bytes":p.stat().st_size,"sha256":sha(p)} for p in sorted(figdir.glob("*.png"))]})

    summary={"initial15_score_comparisons_unchanged":len(errors),"matched_controls":65,"camera_inside_height_assumption_count":sum(r["camera_inside_height_assumption"]=="True" for r in matched),
             "matched_order_counts_are_not_human_accuracy":counts,"log_real_delta_min":min(r["delta"] for r in logrows),"log_real_delta_max":max(r["delta"] for r in logrows),
             "T20_relative_to_log_change":next(r["delta"] for r in logrows if r["case_id"]=="T20"),
             "development_ablation_effects":effects,"new_human_labels":0,"independent_validation":False}
    dump(OUT/"mechanism_summary.json",summary)
    print(json.dumps(summary,ensure_ascii=False,indent=2))


if __name__=="__main__":
    main()
