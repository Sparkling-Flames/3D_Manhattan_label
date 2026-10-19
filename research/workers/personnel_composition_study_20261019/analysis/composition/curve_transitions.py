#!/usr/bin/env python3
"""Within-image changes along every declared composition line, with real membership.

Adjacent target counts are compared at fixed n. Size comparisons require exactly
the same complete class proportions, and compare neighboring observed sizes.
Both are descriptive sampled-team contrasts; they do not impose a shared core.
"""
from __future__ import annotations
import argparse
import collections
from fractions import Fraction
from pathlib import Path
import numpy as np
import pandas as pd
from fusion_runner import read, write
from summarize_grid import sha
from frozen_grid_comparisons import CELL_METRICS, WITHIN_METRICS, DIFF, save, finite_mean, summaries, boot_buildings


def proportions(composition, k):
    return "|".join(f"{c}:{Fraction(int(n), int(k))}" for c, n in
                    (item.split(":") for item in composition.split("|")))


def compare(stage, curve_id, kind, a, b, requests):
    assert a.pool_id == b.pool_id and a.reference_id == b.reference_id
    ka = (a.method_id, a.domain, a.pool_id, int(a.k), a.composition)
    kb = (b.method_id, b.domain, b.pool_id, int(b.k), b.composition)
    ra = {r["replicate"]: r for r in requests[ka]}
    rb = {r["replicate"]: r for r in requests[kb]}
    pairs = {(ra[i]["team_key"], rb[i]["team_key"]): (ra[i], rb[i]) for i in set(ra) & set(rb)}
    unchanged = 0
    removed, added, retained = [], [], []
    for x, y in pairs.values():
        sa, sb = set(x["worker_ids"]), set(y["worker_ids"])
        if sa == sb:
            unchanged += 1
            continue
        removed.append(len(sa - sb)); added.append(len(sb - sa)); retained.append(len(sa & sb))
    row = dict(stage=stage["name"], phase=stage["phase"], method_id=a.method_id, domain=a.domain,
               curve_id=curve_id, transition_kind=kind, pool_id=a.pool_id, image=a.image,
               building=a.building, difficulty=DIFF.get(a.difficulty, a.difficulty), reference_id=a.reference_id,
               k_a=int(a.k), k_b=int(b.k), composition_a=a.composition, composition_b=b.composition,
               target_n_a=int(a.target_n), target_n_b=int(b.target_n), target_class=a.target_class,
               target_fraction_a=float(a.target_fraction), target_fraction_b=float(b.target_fraction),
               unique_teams_a=int(a.unique_team_n), unique_teams_b=int(b.unique_team_n),
               scored_teams_a=int(a.score_available_n), scored_teams_b=int(b.score_available_n),
               complete_teams_a=int(a.complete_n), complete_teams_b=int(b.complete_n),
               all_team_scores_present=bool(a.score_available_n == a.unique_team_n and b.score_available_n == b.unique_team_n),
               actual_different_member_pairs=len(removed), identical_member_pairs_excluded=unchanged,
               removed_mean=finite_mean(removed), added_mean=finite_mean(added), retained_mean=finite_mean(retained),
               team_keys_a=a.team_keys, team_keys_b=b.team_keys)
    for metric in CELL_METRICS + WITHIN_METRICS:
        row[metric+"_a"], row[metric+"_b"] = getattr(a, metric), getattr(b, metric)
        row[metric+"_change"] = getattr(b, metric) - getattr(a, metric)
    return row


def stage_transitions(stage):
    receipt = read(Path(stage["grid"]) / "GRID_SUMMARY_RECEIPT.json")
    assert receipt["missing_computations"] == 0 and receipt["full_manifest_pool_coverage"]
    assert sha(stage["requests"]) in receipt["input_hashes"].values()
    manifest = read(stage["requests"])
    if not manifest.get("curve_index"):
        return []
    cells = pd.read_csv(Path(stage["grid"]) / "cell_summary.csv.gz")
    assert len(cells) == receipt["cells"] and set(cells.phase) == {stage["phase"]}
    requests = collections.defaultdict(list)
    for r in manifest["requests"]:
        requests[(r["method_id"], r["domain"], r["pool_id"], r["k"], r["composition"])].append(r)
    index = pd.DataFrame(manifest["curve_index"])
    index = index[index.feasible].drop_duplicates(["method_id", "domain", "pool_id", "curve_id", "k", "composition"])
    merged = index.merge(cells, on=["method_id", "domain", "pool_id", "k", "composition"], validate="many_to_one")
    assert len(merged) == len(index)
    merged["exact_full_proportion"] = [proportions(c, k) for c, k in zip(merged.composition, merged.k)]
    rows = []
    for (_, _, _, cid, _), g in merged.groupby(["method_id", "domain", "pool_id", "curve_id", "k"]):
        ordered = list(g.sort_values("target_n").itertuples(index=False))
        for a, b in zip(ordered, ordered[1:]):
            if int(b.target_n) - int(a.target_n) != 1:
                continue
            rows.append(compare(stage, cid, "adjacent_target_count_fixed_n", a, b, requests))
    for (_, _, _, cid, _), g in merged.groupby(["method_id", "domain", "pool_id", "curve_id", "exact_full_proportion"]):
        ordered = list(g.sort_values("k").itertuples(index=False))
        for a, b in zip(ordered, ordered[1:]):
            assert proportions(a.composition, a.k) == proportions(b.composition, b.k)
            rows.append(compare(stage, cid, "next_observed_n_same_full_proportion", a, b, requests))
    return rows


def aggregate(frame):
    if frame.empty:
        return []
    keys = ["stage", "phase", "method_id", "domain", "curve_id", "transition_kind", "k_a", "k_b",
            "composition_a", "composition_b", "target_class", "target_n_a", "target_n_b", "target_fraction_a", "target_fraction_b"]
    rows = []
    for key, g in frame.groupby(keys, sort=True):
        meta = dict(zip(keys, key))
        for scope in ["all"] + sorted(g.difficulty.unique()):
            h = g if scope == "all" else g[g.difficulty == scope]
            q = h.B8L2_mean_change
            row = dict(meta, reported_difficulty=scope, images=len(h), buildings=int(h.building.nunique()),
                       quality_paired_images=int(q.notna().sum()), unique_teams_a=int(h.unique_teams_a.sum()),
                       unique_teams_b=int(h.unique_teams_b.sum()), scored_teams_a=int(h.scored_teams_a.sum()),
                       scored_teams_b=int(h.scored_teams_b.sum()), complete_teams_a=int(h.complete_teams_a.sum()),
                       complete_teams_b=int(h.complete_teams_b.sum()), all_team_scores_present_images=int(h.all_team_scores_present.sum()),
                       positive_images=int((q>0).sum()), negative_images=int((q<0).sum()),
                       actual_different_member_pairs=int(h.actual_different_member_pairs.sum()),
                       removed_mean_image_equal=finite_mean(h.removed_mean), added_mean_image_equal=finite_mean(h.added_mean),
                       retained_mean_image_equal=finite_mean(h.retained_mean), image_ids="|".join(sorted(h.image)),
                       building_ids="|".join(sorted(h.building.unique())))
            changes = [metric+"_change" for metric in CELL_METRICS + WITHIN_METRICS]
            bm = h.groupby("building")[changes].mean()
            row.update(summaries(q, "image_B8L2_change"))
            row.update(summaries(bm.B8L2_mean_change, "building_B8L2_change"))
            row["building_bootstrap_low"], row["building_bootstrap_high"] = boot_buildings(bm.B8L2_mean_change, (key, scope))
            for metric in CELL_METRICS + WITHIN_METRICS:
                row[metric+"_change_image_equal"] = finite_mean(h[metric+"_change"])
                row[metric+"_change_building_equal"] = finite_mean(bm[metric+"_change"])
                row[metric+"_finite_paired_images"] = int(h[metric+"_change"].notna().sum())
                row[metric+"_finite_paired_buildings"] = int(bm[metric+"_change"].notna().sum())
            rows.append(row)
    return rows


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--stages", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    stages, rows, receipts = read(args.stages), [], []
    for stage in stages:
        r = stage_transitions(stage)
        rows.extend(r)
        receipts.append(dict(stage=stage["name"], phase=stage["phase"], per_image_transitions=len(r),
                             request_sha256=sha(stage["requests"]),
                             summary_sha256=sha(Path(stage["grid"]) / "GRID_SUMMARY_RECEIPT.json")))
        print(receipts[-1], flush=True)
    frame = save(args.out / "integer_curve_transitions_per_image.csv.gz", rows)
    summary = save(args.out / "integer_curve_transitions_aggregate.csv.gz", aggregate(frame))
    write(args.out / "CURVE_TRANSITIONS_RECEIPT.json", dict(schema="declared_curve_transitions_v1", source_sha256=sha(Path(__file__)),
          stages=receipts, per_image_transitions=len(frame), aggregated_transitions=len(summary),
          scope="Every feasible adjacent integer target count; neighboring observed n only when all class proportions match exactly.",
          membership="Actual unique same-replicate member pairs; identical teams excluded. Same replicate does not guarantee a common core. Size changes can also exchange existing workers.",
          missing="Paired finite cell means; failed teams and missing quality denominators retained. No zero filling.",
          inference="Descriptive actual fusion results on common images. All directions retained, not selected validation successes. Building means receive equal weight."))


if __name__ == "__main__":
    main()
