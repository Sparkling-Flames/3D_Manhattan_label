"""Create endpoint denominators and two scientific figures from completed runs."""
from pathlib import Path
import json
import os

os.environ.setdefault("MPLCONFIGDIR", "/tmp/worker-profile-matplotlib")
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
OUT = Path(os.environ.get("WORKER_PROFILE_OUTPUT", str(HERE))).resolve()
STAGE = OUT / "stage2"
COLORS = {"8_high": "#235a99", "4_high_4_low": "#208b85", "8_low": "#cf6e28", "random_8_from_24": "#6c7179"}
LABELS = {"8_high": "8 higher-Q", "4_high_4_low": "4 higher + 4 lower", "8_low": "8 lower-Q", "random_8_from_24": "Random 8 / full 24"}
ORDER = list(COLORS)
IMAGES = json.loads((HERE / "REGISTRATION.json").read_text())["primary_images"]


def csv(path, rows):
    d = rows if isinstance(rows, pd.DataFrame) else pd.DataFrame(rows)
    d.to_csv(path, index=False, encoding="utf-8-sig")
    return d


def coverage():
    d = pd.read_csv(OUT / "fixed_base_class_contrasts.csv")
    outcomes = [c for c in d if c.endswith("_difference")]
    rows = []
    for key, g in d.groupby(["label_axis", "candidate", "contrast"]):
        supported = g[g.a_attempts.gt(0) & g.b_attempts.gt(0)]
        for outcome in outcomes:
            paired = supported.dropna(subset=[outcome])
            rows.append(dict(label_axis=key[0], candidate=key[1], contrast=key[2], outcome=outcome,
                             candidate_bases=len(g), bases_with_both_groups=len(supported), outcome_paired_bases=len(paired),
                             outcome_images=paired.image.nunique(), outcome_buildings=paired.building_id.nunique(),
                             entrants_a_in_paired_bases=int(paired.a_attempts.sum()), entrants_b_in_paired_bases=int(paired.b_attempts.sum()),
                             complete_a_in_paired_bases=int(paired.a_complete.sum()), complete_b_in_paired_bases=int(paired.b_complete.sum()),
                             source_a_known_in_paired_bases=int(paired.source_a_known.sum()), source_b_known_in_paired_bases=int(paired.source_b_known.sum()),
                             target_a_known_in_paired_bases=int(paired.target_a_known.sum()), target_b_known_in_paired_bases=int(paired.target_b_known.sum()),
                             source_joint_quality_a=int(paired.source_active_time_seconds_joint_quality_a_n.sum()),
                             source_joint_quality_b=int(paired.source_active_time_seconds_joint_quality_b_n.sum()),
                             target_joint_quality_a=int(paired.target_matched_time_seconds_joint_quality_a_n.sum()),
                             target_joint_quality_b=int(paired.target_matched_time_seconds_joint_quality_b_n.sum())))
    cv = csv(OUT / "fixed_base_endpoint_coverage.csv", rows)
    summary = pd.read_csv(OUT / "fixed_base_contrast_summary.csv")
    summary = summary.merge(cv, on=["label_axis", "candidate", "contrast", "outcome"], validate="one_to_one")
    csv(OUT / "fixed_base_contrast_summary_with_coverage.csv", summary)
    a = pd.read_csv(OUT / "fixed_base_entrants_enriched.csv")
    csv(OUT / "fixed_base_entrant_class_coverage.csv", a.groupby("B8L2_QT", as_index=False).agg(
        entrant_opportunities=("worker_id", "size"), distinct_workers=("worker_id", "nunique"),
        complete_outputs=("complete_evaluable", "sum"), source_time_known=("source_active_time_seconds", "count"),
        target_time_known=("target_matched_time_seconds", "count")))
    swaps = pd.read_csv(OUT / "replacement_within_base.csv")
    swaps = swaps[swaps.k.eq(8) & swaps.same_pairs.gt(0) & swaps.cross_pairs.gt(0)]
    assert set(zip(swaps.image, swaps.base)) == set(zip(a.image, a.base))
    csv(OUT / "replacement_7plus1_coverage.csv", swaps.groupby(["label_axis", "candidate"], as_index=False).agg(
        bases=("base", "size"), images=("image", "nunique"), buildings=("building_id", "nunique"),
        same_class_pair_attempts=("same_pairs", "sum"), cross_class_pair_attempts=("cross_pairs", "sum"),
        unknown_class_pair_attempts=("unknown_pairs", "sum"), same_class_valid_floor_pairs=("same_floor_n", "sum"),
        cross_class_valid_floor_pairs=("cross_floor_n", "sum")))


def events():
    steps = pd.read_csv(STAGE / "prefix_transitions.csv")
    state = pd.read_csv(STAGE / "path_states.csv")[["image", "strategy", "path", "k", "connection_available"]]
    steps = steps.merge(state.rename(columns={"k": "k_from", "connection_available": "connection_available_from"}),
                        on=["image", "strategy", "path", "k_from"], validate="many_to_one")
    proper = steps[steps.k_from.ge(3)]  # k1/k2 policy transitions are reported separately.
    rows = []
    for strategy, g in list(proper.groupby("strategy")) + [("all_strategies", proper)]:
        q = g.dropna(subset=["B8L2_change"]); f = g.dropna(subset=["floor_change"])
        rows.append(dict(strategy=strategy, attempted_additions=len(g), comparable_quality_additions=len(q),
                         B8L2_decreases=int(q.B8L2_change.lt(-1e-9).sum()), D10_decreases=int(q.D10_change.lt(-1e-9).sum()),
                         B8L2_decrease_fraction=float(q.B8L2_change.lt(-1e-9).mean()),
                         comparable_floor_additions=len(f), nonzero_floor_changes=int(f.floor_change.gt(1e-12).sum()),
                         additions_with_comparable_old_identity_pairs=int(g.common_pair_comparisons.gt(0).sum()),
                         identity_repartition_steps=int(g.changed_coidentity_pairs.gt(0).sum()),
                         additions_with_selected_node_exit_without_old_identity_change=int(g.unchanged_identity_vote_losses.gt(0).sum()),
                         selected_nodes_exiting_without_old_identity_change=int(g.unchanged_identity_vote_losses.sum()),
                         complete_from_additions=int(g.complete_from.sum()), incomplete_from_additions=int((~g.complete_from).sum()),
                         complete_to_incomplete_steps=int((g.complete_from & ~g.complete_to).sum()),
                         incomplete_to_complete_steps=int((~g.complete_from & g.complete_to).sum()),
                         connected_from_additions=int(g.connection_available_from.sum()),
                         connection_lost_steps=int(g.connection_lost.sum()),
                         largest_B8L2_decrease=q.B8L2_change.min(), largest_B8L2_increase=q.B8L2_change.max(),
                         note="k_from>=3; numeric tolerance 1e-9; all are dependent replay events"))
    csv(STAGE / "transition_event_counts.csv", rows)
    examples = proper.sort_values("B8L2_change").head(3).copy()
    examples["selection_status"] = "posthoc largest numeric declines, diagnostic witnesses only"
    csv(STAGE / "negative_step_examples.csv", examples)
    endpoint = pd.read_csv(STAGE / "strategy_by_image_k.csv")
    endpoint = endpoint[endpoint.k.eq(8)]
    exact = pd.read_csv(STAGE / "exact_expected_raw_R.csv")
    endpoint = endpoint.merge(exact[["image", "strategy", "exact_expected_R"]], on=["image", "strategy"], validate="one_to_one")
    columns = ["B8L2_mean", "D10_mean", "IoU3D100_mean", "complete_evaluable_mean", "raw_R_mean", "exact_expected_R", "V_floor", "shared_members_mean"]
    bb = endpoint.groupby(["strategy", "building_id"], as_index=False)[columns].mean()
    csv(STAGE / "endpoint_by_building.csv", bb)
    rows = []
    for strategy, g in bb.groupby("strategy"):
        im = endpoint[endpoint.strategy.eq(strategy)]
        r = dict(strategy=strategy, images=len(im), buildings=len(g), sampled_terminal_teams=int(im.attempts.sum()),
                 complete_terminal_teams=int(im.quality_n.sum()), complete_source_cost_teams=int(im.source_time_n.sum()),
                 complete_target_cost_teams=int(im.target_time_n.sum()))
        for c in columns: r[c] = g[c].mean()
        rows.append(r)
    csv(STAGE / "endpoint_strategy_summary.csv", rows)


def figures():
    plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 9, "axes.spines.top": False, "axes.spines.right": False})
    data = pd.read_csv(STAGE / "strategy_by_image_k.csv")
    fig, axes = plt.subplots(7, 3, figsize=(13.5, 18.5), sharex=True)
    fields = ["B8L2_mean", "complete_evaluable_mean", "V_floor"]
    titles = ["Successful-output B8L2", "Full geometry / all attempts", "Same-k member sensitivity V"]
    for i, image in enumerate(IMAGES):
        for j, (field, title) in enumerate(zip(fields, titles)):
            ax = axes[i, j]
            for strategy in ORDER:
                d = data[(data.image == image) & (data.strategy == strategy)].sort_values("k")
                y = d[field].copy(); y[d.k.eq(2)] = np.nan
                ax.plot(d.k, y, marker="o", ms=3, lw=1.5, color=COLORS[strategy], label=LABELS[strategy])
            ax.axvspan(1.78, 2.22, color="#e4e6e9", alpha=.75, zorder=-1)
            ax.set_xlim(.7, 8.3); ax.set_xticks(range(1, 9)); ax.grid(alpha=.18)
            if j == 0:
                ax.set_ylim(0, 100); ax.set_ylabel(image, fontsize=9, labelpad=10)
            elif j == 1:
                ax.set_ylim(-.04, 1.04); ax.set_yticks([0, .5, 1]); ax.set_yticklabels(["0%", "50%", "100%"])
            else:
                ax.set_ylim(bottom=0)
            if i == 0: ax.set_title(title, fontsize=11, pad=12)
            if i == 6: ax.set_xlabel("People in the actual prefix")
    h, l = axes[0, 0].get_legend_handles_labels()
    fig.legend(h, l, loc="upper center", ncol=4, frameon=False, bbox_to_anchor=(.52, .976), fontsize=10)
    fig.suptitle("Real additions within fixed 8-person composition designs", fontsize=15, y=.997)
    fig.text(.04, .017, "Seven images / six buildings; 12 fixed random orders per strategy/image. k=2 is a policy gap (grey), not a fabricated score.\nQ and V are conditional on available full geometry; the middle column retains all attempts. V uses pairwise output 1-IoU; repeated teams and shared members remain dependent.\nEvery point uses its actual current prefix. Lower V in a smaller class pool can reflect greater member overlap. No class reaches its full source pool by k=8.", fontsize=9)
    fig.tight_layout(rect=(.02, .06, .99, .95), h_pad=1.6, w_pad=2)
    fig.savefig(OUT / "figure_1_true_prefixes.png", dpi=170)
    fig.savefig(OUT / "figure_1_true_prefixes.svg")
    plt.close(fig)

    paired = pd.read_csv(STAGE / "paired_strategy_differences_by_building.csv")
    paired = paired[paired.k.eq(8)]
    swaps = pd.read_csv(OUT / "replacement_7plus1_by_building.csv")
    swaps = swaps[(swaps.label_axis == "B8L2") & swaps.candidate.isin(["Q2", "QT"])]
    fig, axes = plt.subplots(1, 3, figsize=(15.5, 5.6))
    strategies = ["8_high", "4_high_4_low", "8_low"]
    for x, strategy in enumerate(strategies):
        g = paired[paired.contrast.eq(strategy + "_minus_random_8_from_24")].sort_values("building_id")
        offsets = np.linspace(-.14, .14, len(g))
        axes[0].scatter(x+offsets, g.B8L2_mean_difference, color=COLORS[strategy], s=35, alpha=.8)
        axes[0].plot([x-.22, x+.22], [g.B8L2_mean_difference.mean()]*2, color="black", lw=2)
        axes[1].scatter(g.shared_members_mean_difference, g.V_floor_difference, color=COLORS[strategy], s=40, alpha=.8, label=LABELS[strategy])
    axes[0].axhline(0, color="black", lw=.7); axes[0].set_xticks(range(3), ["8 high", "4 high + 4 low", "8 low"])
    axes[0].set_ylabel("B8L2 difference from random 8")
    axes[0].set_title("A. Fixed eight-person composition")
    axes[0].text(.03, .02, "Dots: 6 buildings; black bars: equal-building mean", transform=axes[0].transAxes, fontsize=8)
    axes[1].axhline(0, color="black", lw=.7); axes[1].axvline(0, color="black", lw=.7)
    axes[1].set_xlabel("Additional shared members vs random 8")
    axes[1].set_ylabel("V difference from random 8")
    axes[1].set_title("B. Lower V and greater pool overlap")
    axes[1].legend(frameon=True, facecolor="white", framealpha=.95, edgecolor="none", fontsize=8, loc="center left", bbox_to_anchor=(.02, .36))
    for candidate, x0, color in [("Q2", 0, "#235a99"), ("QT", 3, "#208b85")]:
        g = swaps[swaps.candidate.eq(candidate)].sort_values("building_id")
        for i, r in enumerate(g.itertuples()):
            jitter = (i-(len(g)-1)/2)*.035
            axes[2].plot([x0+jitter, x0+1+jitter], [r.floor_change_same, r.floor_change_cross], color=color, alpha=.5, marker="o", ms=4, lw=.8)
        axes[2].plot([x0-.2, x0+.2], [g.floor_change_same.mean()]*2, color="black", lw=2)
        axes[2].plot([x0+.8, x0+1.2], [g.floor_change_cross.mean()]*2, color="black", lw=2)
    axes[2].set_xticks([0, 1, 3, 4], ["Same Q", "Cross Q", "Same QT", "Cross QT"])
    axes[2].tick_params(axis="x", labelrotation=25)
    axes[2].set_ylabel("Floor change after one real member swap")
    axes[2].set_title("C. Exact same seven-person bases")
    for ax in axes: ax.grid(axis="y", alpha=.2)
    fig.suptitle("Composition can matter; class membership does not make people interchangeable", fontsize=14, y=.98)
    fig.text(.025, .02, "A/B: registered stage-2 design, same seven images and fixed k=8; Q is conditional on successful output and must be read with completeness.\nC: 14 existing fixed 7+1 bases, all remaining actual entrants; bases average within image, then buildings. Same and cross class swaps share exactly seven members.\nR is an original-answer pair distance; V is a fused-output distance. They measure different objects, use different normalizations, and are not individual reliability scores.", fontsize=9)
    fig.tight_layout(rect=(0, .14, 1, .93), w_pad=2.5)
    fig.savefig(OUT / "figure_2_composition_and_replacement.png", dpi=180)
    fig.savefig(OUT / "figure_2_composition_and_replacement.svg")
    plt.close(fig)


if __name__ == "__main__":
    coverage()
    events()
    figures()
    print("Endpoint denominators, transition counts and two figures generated.")
