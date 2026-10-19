#!/usr/bin/env python3
"""Compact frozen-rule tables; mixed cells require both specified pure baselines.

The best pure baseline is an outcome oracle used to assess complementarity. It
is not claimed as a prospectively available personnel-selection rule.
"""
from __future__ import annotations
import argparse
import json
import math
from pathlib import Path
import numpy as np
import pandas as pd
from fusion_runner import read, write
from summarize_grid import sha
from frozen_grid_comparisons import CELL_METRICS, WITHIN_METRICS, save, finite_mean, summaries, boot_buildings

MIX_RULES = {"H4_detail_role", "H7_conditional_complement", "H8_role_mixture", "H10_semi_old_tendency", "H11_doorway"}


def against_both_pures(frame):
    rows = []
    keys = ["stage", "phase", "rule_id", "method_id", "domain", "k", "composition_b", "primary_contrast", "difficulty_filter", "pool_id"]
    subset = frame[frame.rule_id.isin(MIX_RULES)].copy()
    subset = subset[subset.composition_b.map(lambda c: sum(int(x.split(":")[1]) > 0 for x in c.split("|")) > 1)]
    for key, g in subset.groupby(keys):
        assert g.composition_a.nunique() == len(g) and len(g) <= 2
        row = dict(zip(keys, key))
        first = g.iloc[0]
        for col in ("image", "building", "difficulty", "reference_id", "reference_version", "team_keys_b", "unique_teams_b", "scored_teams_b", "complete_teams_b", "within_pairs_b", "workers_b"):
            row[col] = first[col]
        row["required_pure_baselines"] = 2
        row["observed_pure_baselines"] = len(g)
        row["finite_B8_pure_baselines"] = int(g.B8L2_mean_a.notna().sum())
        row["all_three_cell_quality_means_available"] = bool(len(g) == 2 and g.B8L2_mean_a.notna().all() and g.B8L2_mean_b.notna().all())
        row["all_three_cell_team_scores_present"] = bool(len(g) == 2 and g.all_team_scores_present.all())
        row["pure_composition_B8_json"] = json.dumps({r.composition_a: (None if pd.isna(r.B8L2_mean_a) else r.B8L2_mean_a) for r in g.itertuples()}, sort_keys=True)
        row["pure_cell_support_json"] = json.dumps({r.composition_a: {
            "request_rows": int(getattr(r, "request_rows_a", r.requested_teams_a)),
            "requested_unique_teams": int(r.requested_teams_a), "actual_unique_attempts": int(r.unique_teams_a),
            "complete": int(r.complete_teams_a), "score_available": int(r.scored_teams_a)} for r in g.itertuples()}, sort_keys=True)
        row["mixed_request_rows"] = int(first.get("request_rows_b", first.requested_teams_b))
        row["mixed_requested_unique_teams"] = int(first.requested_teams_b)
        row["each_of_three_cells_at_least3_finite_teams"] = bool(len(g) == 2 and g.scored_teams_a.ge(3).all() and first.scored_teams_b >= 3)
        row["pure_team_keys_json"] = json.dumps({r.composition_a: r.team_keys_a for r in g.itertuples()}, sort_keys=True)
        row["pure_unique_teams_total"] = int(g.unique_teams_a.sum())
        row["pure_scored_teams_total"] = int(g.scored_teams_a.sum())
        row["pure_complete_teams_total"] = int(g.complete_teams_a.sum())
        row["pure_workers_union"] = "|".join(sorted({w for ws in g.workers_a for w in ws.split("|")}))
        for metric in CELL_METRICS + WITHIN_METRICS:
            # Duplicate references to the one mixed cell must be identical.
            assert g[metric+"_b"].dropna().nunique() <= 1
            row[metric+"_mixed"] = first[metric+"_b"]
        if row["all_three_cell_quality_means_available"]:
            best = g.loc[g.B8L2_mean_a.idxmax()]
            row["best_B8_pure_composition"] = best.composition_a
            for metric in CELL_METRICS + WITHIN_METRICS:
                row[metric+"_best_B8_pure"] = best[metric+"_a"]
                row[metric+"_change"] = first[metric+"_b"] - best[metric+"_a"]
            row["actual_cross_turnover_mean_to_best_pure"] = best.same_rep_turnover_mean
        else:
            row["best_B8_pure_composition"] = ""
            for metric in CELL_METRICS + WITHIN_METRICS:
                row[metric+"_best_B8_pure"] = row[metric+"_change"] = np.nan
        rows.append(row)
    return pd.DataFrame(rows)


def aggregate_mixtures(frame, include_min3=True):
    rows = []
    keys = ["stage", "phase", "rule_id", "method_id", "domain", "k", "composition_b", "primary_contrast", "difficulty_filter"]
    if frame.empty:
        return rows
    for key, g in frame.groupby(keys):
        meta = dict(zip(keys, key))
        scopes = ["all"] + sorted(g.difficulty.unique()) if meta["difficulty_filter"] == "all" else [meta["difficulty_filter"]]
        for scope in scopes:
            h = g if scope == "all" else g[g.difficulty == scope]
            q = h.B8L2_mean_change
            row = dict(meta, reported_difficulty=scope, observed_images=len(h), observed_buildings=int(h.building.nunique()),
                       both_pure_observed_images=int(h.observed_pure_baselines.eq(2).sum()),
                       quality_comparable_images=int(q.notna().sum()), all_team_scores_present_images=int(h.all_three_cell_team_scores_present.sum()),
                       quality_comparable_buildings=int(h.loc[q.notna(), "building"].nunique()),
                       positive_images=int((q>0).sum()), negative_images=int((q<0).sum()),
                       unique_mixed_teams=int(h.unique_teams_b.sum()), scored_mixed_teams=int(h.scored_teams_b.sum()),
                       complete_mixed_teams=int(h.complete_teams_b.sum()), unique_pure_teams=int(h.pure_unique_teams_total.sum()),
                       scored_pure_teams=int(h.pure_scored_teams_total.sum()), complete_pure_teams=int(h.pure_complete_teams_total.sum()),
                       within_mixed_unique_member_pairs=int(h.within_pairs_b.sum()),
                       mixed_workers=len({w for ws in h.workers_b for w in ws.split("|")}),
                       image_ids="|".join(sorted(h.image)), building_ids="|".join(sorted(h.building.unique())))
            cols = [metric+"_change" for metric in CELL_METRICS + WITHIN_METRICS]
            b = h.groupby("building")[cols].mean()
            row.update(summaries(q, "image_B8L2_change"))
            row.update(summaries(b.B8L2_mean_change, "building_B8L2_change"))
            row["building_bootstrap_low"], row["building_bootstrap_high"] = boot_buildings(b.B8L2_mean_change, (key, scope))
            row["positive_buildings"] = int((b.B8L2_mean_change>0).sum())
            row["negative_buildings"] = int((b.B8L2_mean_change<0).sum())
            for metric in CELL_METRICS + WITHIN_METRICS:
                row[metric+"_change_image_equal"] = finite_mean(h[metric+"_change"])
                row[metric+"_change_building_equal"] = finite_mean(b[metric+"_change"])
                row[metric+"_finite_images"] = int(h[metric+"_change"].notna().sum())
                row[metric+"_finite_buildings"] = int(b[metric+"_change"].notna().sum())
                row[metric+"_mixed_image_equal"] = finite_mean(h[metric+"_mixed"])
            if q.notna().any():
                for tag, ix in (("best", q.idxmax()), ("worst", q.idxmin())):
                    row[tag+"_image"] = h.loc[ix, "image"]
                    row[tag+"_B8L2_change"] = h.loc[ix, "B8L2_mean_change"]
            rows.append(row)
    # The original H7 discovery lead required at least three finite teams in
    # EACH of the two pure cells and mixed cell. Keep this pre-existing support
    # sensitivity next to the complete common-cell means for every stage.
    h7 = frame[frame.rule_id.eq("H7_conditional_complement") & frame.each_of_three_cells_at_least3_finite_teams]
    for row in rows:
        row["support_rule"] = "all_common_cell_means"
    if include_min3 and len(h7):
        extra = aggregate_mixtures(h7, include_min3=False)
        for row in extra:
            row["support_rule"] = "each_cell_at_least3_finite_teams"
        rows.extend(extra)
    return rows


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--results", type=Path, required=True)
    args = ap.parse_args()
    receipt = read(args.results / "FROZEN_COMPARISONS_RECEIPT.json")
    per_image = pd.read_csv(args.results / "frozen_contrasts_per_image.csv.gz")
    aggregate = pd.read_csv(args.results / "frozen_contrasts_aggregate.csv.gz")
    assert len(per_image) == receipt["actual_per_image_contrasts"]
    mixtures = save(args.results / "frozen_mixture_best_pure_per_image.csv.gz", against_both_pures(per_image))
    save(args.results / "frozen_mixture_best_pure_aggregate.csv.gz", aggregate_mixtures(mixtures))
    # A compact view is selected by the frozen definition only, never its outcome.
    short = aggregate[aggregate.primary_contrast].copy()
    hard = short.rule_id.eq("H5_hard_structure")
    allowed = [f"detail_count_0_to_{k}" for k in (5,7,9)] + [f"detail_count_{math.floor(.4*k)}_to_{math.ceil(.6*k)}" for k in (5,7,9)]
    short = short[~hard | short.comparison_label.isin(allowed)]
    columns = ["stage","phase","rule_id","k","reported_difficulty","comparison_label","composition_a","composition_b",
               "paired_images","paired_buildings","quality_paired_images","building_B8L2_change_n","building_B8L2_change_mean",
               "building_bootstrap_low","building_bootstrap_high","image_B8L2_change_mean","positive_gt0_images","negative_ltminus0_images",
               "positive_buildings","negative_buildings","scored_teams_a","unique_teams_a","scored_teams_b","unique_teams_b",
               "complete_teams_a","complete_teams_b","all_team_scores_present_images","unique_workers",
               "D10_mean_change_building_equal","B8L2_p10_change_building_equal","nodes_mean_change_building_equal",
               "diag_wall_coverage_05_mean_change_building_equal","diag_corner_recall_05_mean_change_building_equal",
               "IoU3D100_mean_change_building_equal","within_abs_B8L2_change_mean_a_image_equal","within_abs_B8L2_change_mean_b_image_equal",
               "within_joint_stable_main_rate_a_image_equal","within_joint_stable_main_rate_b_image_equal",
               "within_turnover_mean_a_image_equal","within_turnover_mean_b_image_equal","actual_cross_turnover_mean_image_equal",
               "within_unique_team_pairs_a","within_unique_team_pairs_b","worst_image","worst_B8L2_change","best_image","best_B8L2_change"]
    save(args.results / "frozen_rule_compact.csv", short[[c for c in columns if c in short]])
    write(args.results / "FROZEN_FINDINGS_RECEIPT.json", dict(schema="compact_frozen_findings_v1", source_sha256=sha(Path(__file__)),
          frozen_comparisons_receipt_sha256=sha(args.results / "FROZEN_COMPARISONS_RECEIPT.json"),
          scope="All defined mixture-versus-both-pure rules; finite quality comparison requires both specified pure cells. Compact rows use a definition-based fixed selection, not sign or significance.",
          best_pure="The per-image pure with the larger actual mean B8 is an outcome oracle for complementarity assessment, not a prospective selection policy.",
          missing="Failed or unavailable pure cells are retained and never replaced by zero or by the one surviving pure."))


if __name__ == "__main__":
    main()
