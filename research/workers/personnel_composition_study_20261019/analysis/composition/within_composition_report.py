#!/usr/bin/env python3
"""H2: fixed compositions, actual member turnover, and finite-capacity support."""
from __future__ import annotations
import argparse
import collections
import json
from pathlib import Path
import numpy as np
import pandas as pd
from fusion_runner import read, write
from summarize_grid import sha, labels_from_files
from frozen_grid_comparisons import DIFF, save, finite_mean

KEYS = ["method_id", "domain", "pool_id", "k", "composition"]
METHODS = {"F_rule_Q_quantile_K3", "R_geo9_source_signed_p2_K2", "R_role_ward_K5", "R_role_ward_difficulty_K2"}
PAIR_METRICS = ["abs_B8L2_change", "abs_D10_change", "floor_jaccard_difference", "structure_bound_cyclic_deg",
                "mean_height_prism_pair_iou", "joint_stable_main", "joint_stable_strict", "joint_stable_wide", "turnover"]


def selected(row):
    if row.method_id not in METHODS or int(row.k) not in (5, 9):
        return False
    c = {k: int(v) for k, v in (x.split(":") for x in row.composition.split("|")) if int(v)}
    if len(c) == 1:
        return True
    if row.method_id == "F_rule_Q_quantile_K3":
        return c == ({"C01": 2, "C03": 3} if row.k == 5 else {"C01": 3, "C03": 6})
    if row.method_id in ("R_geo9_source_signed_p2_K2", "R_role_ward_difficulty_K2"):
        return c == ({"C01": 2, "C02": 3} if row.k == 5 else {"C01": 3, "C02": 6})
    if row.k == 5:
        return c in ({"C02": 2, "C05": 3}, {"C02": 1, "C05": 4})
    return c in ({"C01": 3, "C02": 6}, {"C01": 4, "C02": 5})


def cells_for_stage(stage, pools, labels):
    root = Path(stage["grid"])
    receipt = read(root / "GRID_SUMMARY_RECEIPT.json")
    assert receipt["missing_computations"] == 0 and receipt["full_manifest_pool_coverage"]
    assert sha(stage["requests"]) in receipt["input_hashes"].values()
    cells = pd.read_csv(root / "cell_summary.csv.gz")
    cells = cells[[selected(r) for r in cells.itertuples(index=False)]].copy()
    keep = {tuple(r) for r in cells[KEYS].itertuples(index=False, name=None)}
    if not keep:
        return [], [], dict(stage=stage["name"], selected_cells=0, within_pair_rows=0)
    team_members = {}
    for r in read(stage["requests"])["requests"]:
        key = (r["method_id"], r["domain"], r["pool_id"], r["k"], r["composition"])
        if key in keep:
            team_members[r["team_key"]] = r["worker_ids"]
    usecols = KEYS + ["team_a", "team_b", "both_complete", "quality_comparable", "node_count_difference"] + PAIR_METRICS
    parts = []
    for chunk in pd.read_csv(root / "within_pairs.csv.gz", usecols=usecols, chunksize=100000):
        chunk = chunk[[tuple(r) in keep for r in chunk[KEYS].itertuples(index=False, name=None)]]
        if len(chunk):
            parts.append(chunk)
    pairs = pd.concat(parts, ignore_index=True) if parts else pd.DataFrame(columns=usecols)
    pairgroups = {key: g for key, g in pairs.groupby(KEYS)}
    rows, stable_low = [], []
    for cell in cells.itertuples(index=False):
        key = tuple(getattr(cell, c) for c in KEYS)
        pair = pairgroups.get(key, pd.DataFrame(columns=usecols))
        counts = {c: int(n) for c, n in (x.split(":") for x in cell.composition.split("|"))}
        mapping = labels[cell.method_id, cell.domain]
        capacities = collections.Counter(mapping[r["worker_id"]] for r in pools[cell.pool_id]["records"] if r["worker_id"] in mapping)
        ceiling = sum(min(n, capacities[c]-n) for c, n in counts.items())
        assert not len(pair) or (pair.turnover.ge(1).all() and pair.turnover.le(ceiling).all())
        allteams = set(json.loads(cell.team_keys))
        assert len(allteams) == cell.unique_team_n
        for m in ["all"] + sorted(int(x) for x in pair.turnover.unique()):
            p = pair if m == "all" else pair[pair.turnover.eq(m)]
            teams = set(p.team_a) | set(p.team_b)
            people = sorted({w for t in (allteams if m == "all" else teams) for w in team_members[t]})
            row = dict(stage=stage["name"], phase=stage["phase"], **dict(zip(KEYS, key)), turnover_stratum=str(m),
                       image=cell.image, building=cell.building, difficulty=DIFF.get(cell.difficulty, cell.difficulty),
                       available_unique_teams=int(cell.unique_team_n), participating_unique_teams=len(teams),
                       scored_teams=int(cell.score_available_n), complete_teams=int(cell.complete_n),
                       pair_n=len(p), complete_pair_n=int(p.both_complete.sum()), quality_pair_n=int(p.quality_comparable.sum()),
                       unique_workers=len(people), workers="|".join(people), possible_member_teams=cell.possible_member_teams,
                       theoretical_max_turnover=ceiling, class_capacities_json=json.dumps(dict(capacities), sort_keys=True),
                       mean_B8L2=cell.B8L2_mean, p10_B8L2=cell.B8L2_p10, complete_rate=cell.complete_rate,
                       all_team_scores_present=bool(cell.score_available_n == cell.unique_team_n),
                       all_teams_complete=bool(cell.complete_n == cell.unique_team_n), team_keys=cell.team_keys)
            for metric in PAIR_METRICS:
                x = p[metric].astype(float)
                row[metric+"_mean"] = finite_mean(x)
                row[metric+"_finite_pairs"] = int(x.notna().sum())
            row["abs_B8L2_change_p90"] = float(p.abs_B8L2_change.quantile(.9)) if p.abs_B8L2_change.notna().any() else np.nan
            row["turnover_p10"] = float(p.turnover.quantile(.1)) if len(p) else np.nan
            row["turnover_p90"] = float(p.turnover.quantile(.9)) if len(p) else np.nan
            row["turnover_min"] = float(p.turnover.min()) if len(p) else np.nan
            row["turnover_max"] = float(p.turnover.max()) if len(p) else np.nan
            x = pd.to_numeric(p.node_count_difference)
            row["nodes_different_rate"] = float(x[x.notna()].ne(0).mean()) if x.notna().any() else np.nan
            row["node_comparable_pairs"] = int(x.notna().sum())
            row["turnover_distribution_json"] = json.dumps({str(int(k)): int(n) for k, n in p.turnover.value_counts().sort_index().items()})
            rows.append(row)
            if m == "all" and row["available_unique_teams"] >= 3 and row["all_team_scores_present"] and row["all_teams_complete"]:
                for limit in (70, 80):
                    if row["joint_stable_main_mean"] >= .8 and row["mean_B8L2"] < limit:
                        stable_low.append(dict(row, descriptive_quality_ceiling=limit, descriptive_joint_stable_floor=.8))
    return rows, stable_low, dict(stage=stage["name"], selected_cells=len(cells), within_pair_rows=len(pairs),
                                  source_grid_receipt_sha256=sha(root / "GRID_SUMMARY_RECEIPT.json"))


def aggregate(frame):
    if frame.empty:
        return []
    rows = []
    keys = ["stage", "phase", "method_id", "domain", "k", "composition", "turnover_stratum"]
    metrics = [c+"_mean" for c in PAIR_METRICS] + ["abs_B8L2_change_p90", "turnover_p10", "turnover_p90", "nodes_different_rate", "mean_B8L2", "p10_B8L2", "complete_rate"]
    for key, g in frame.groupby(keys):
        for difficulty in ["all"] + sorted(g.difficulty.unique()):
            h = g if difficulty == "all" else g[g.difficulty == difficulty]
            row = dict(zip(keys, key))
            row.update(reported_difficulty=difficulty, images=len(h), buildings=int(h.building.nunique()),
                       within_comparable_images=int(h.pair_n.gt(0).sum()), within_comparable_buildings=int(h.loc[h.pair_n.gt(0), "building"].nunique()),
                       available_unique_teams=int(h.available_unique_teams.sum()), participating_unique_teams=int(h.participating_unique_teams.sum()),
                       scored_teams=int(h.scored_teams.sum()), complete_teams=int(h.complete_teams.sum()),
                       actual_unique_member_pairs=int(h.pair_n.sum()), quality_comparable_pairs=int(h.quality_pair_n.sum()),
                       complete_pairs=int(h.complete_pair_n.sum()), node_comparable_pairs=int(h.node_comparable_pairs.sum()),
                       actual_unique_workers=len({w for ws in h.workers for w in ws.split("|") if w}),
                       min_teams_per_image=int(h.available_unique_teams.min()), max_teams_per_image=int(h.available_unique_teams.max()),
                       single_team_only_images=int(h.available_unique_teams.eq(1).sum()), all_team_scores_present_images=int(h.all_team_scores_present.sum()),
                       actual_turnover_min=finite_mean([h.turnover_min.min()]), actual_turnover_max=finite_mean([h.turnover_max.max()]),
                       theoretical_max_turnover_min=int(h.theoretical_max_turnover.min()), theoretical_max_turnover_max=int(h.theoretical_max_turnover.max()),
                       image_ids="|".join(sorted(h.image)), building_ids="|".join(sorted(h.building.unique())))
            hist = collections.Counter()
            for item in h.turnover_distribution_json:
                hist.update(json.loads(item))
            row["raw_pair_turnover_counts_json"] = json.dumps(dict(sorted(hist.items(), key=lambda x: int(x[0]))))
            b = h.groupby("building")[metrics].mean()
            for metric in metrics:
                row[metric+"_image_equal"] = finite_mean(h[metric])
                row[metric+"_building_equal"] = finite_mean(b[metric])
                row[metric+"_finite_images"] = int(h[metric].notna().sum())
                row[metric+"_finite_buildings"] = int(b[metric].notna().sum())
            rows.append(row)
    return rows


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--stages", type=Path, required=True)
    ap.add_argument("--snapshot", type=Path, required=True)
    ap.add_argument("--freeze", type=Path, default=Path(__file__).with_name("VALIDATION_FREEZE.json"))
    ap.add_argument("--labels", type=Path, action="append", required=True)
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    frozen = read(args.freeze)
    expected_label_hashes = {v for p, v in frozen["file_sha256"].items() if Path(p).name == "worker_labels.csv.gz"}
    assert {sha(p) for p in args.labels} == expected_label_hashes, "H2 labels differ from the frozen validation labels"
    pools = {p["pool_id"]: p for p in read(args.snapshot)["images"]}
    labels = labels_from_files(args.labels)
    rows, stable_low, receipts = [], [], []
    for stage in read(args.stages):
        r, s, receipt = cells_for_stage(stage, pools, labels)
        rows.extend(r); stable_low.extend(s); receipts.append(receipt)
        print(receipt, flush=True)
    frame = save(args.out / "within_fixed_compositions_per_image.csv.gz", rows)
    summary = save(args.out / "within_fixed_compositions_aggregate.csv.gz", aggregate(frame))
    save(args.out / "within_fixed_compositions_all_turnover.csv", summary[summary.turnover_stratum.eq("all")])
    low = save(args.out / "stable_low_quality_descriptive_cells.csv.gz", stable_low)
    if len(low):
        support = low.groupby(["stage","phase","method_id","domain","k","composition","descriptive_quality_ceiling"]).agg(
            images=("image","nunique"), buildings=("building","nunique"), unique_teams=("available_unique_teams","sum"),
            actual_member_pairs=("pair_n","sum"), mean_B8L2=("mean_B8L2","mean"),
            joint_stable_main=("joint_stable_main_mean","mean"), actual_turnover=("turnover_mean","mean")).reset_index()
        save(args.out / "stable_low_quality_descriptive_support.csv", support)
    write(args.out / "WITHIN_FIXED_COMPOSITIONS_RECEIPT.json", dict(schema="within_fixed_compositions_v1", source_sha256=sha(Path(__file__)),
          freeze_sha256=sha(args.freeze), exact_frozen_label_hashes_verified=sorted(expected_label_hashes), snapshot_sha256=sha(args.snapshot),
          stages=receipts, selected_definition="All pure classes for Q quantile3, signed2, role5 and hard role2 at n5/9, plus fixed declared mixed counts listed in selected(); no validation-outcome selection.",
          aggregation="Pair metrics first summarized within the same image and exact composition; then image or building equally weighted. p90 is the within-image pair p90, not a percentile of image means.",
          missing="Cells with one available team retain support and missing within variation; no same-member pair is treated as a replacement.",
          turnover="Every actual m reported separately when observed, with capacity upper bounds. Raw pair counts are descriptive, not independent samples.",
          field_scope="Pair metrics and participating_unique_teams are restricted to the named turnover m. mean_B8L2, p10_B8L2, scored_teams, complete_teams and available_unique_teams describe the entire exact composition cell, including teams not participating in that m stratum.",
          stable_low_quality="Descriptive flags at quality<70 or<80 and main stability>=0.8, at least3 distinct complete scored teams. These flags are not an added frozen validation success criterion."))


if __name__ == "__main__":
    main()
