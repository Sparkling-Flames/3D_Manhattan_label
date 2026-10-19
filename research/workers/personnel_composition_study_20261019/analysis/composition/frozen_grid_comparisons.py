#!/usr/bin/env python3
"""Apply frozen research questions to actual composition cells and integer curves.

Separate named stages retain the distinction between breadth discovery,
additional members on the same images, and retrospective building holdout.
No rule, label or threshold is chosen from validation outcomes in this module.
"""
from __future__ import annotations
import argparse
import collections
import hashlib
import itertools
import json
import math
import os
from pathlib import Path
for _name in ("OPENBLAS_NUM_THREADS", "OMP_NUM_THREADS", "MKL_NUM_THREADS"):
    os.environ.setdefault(_name, "1")
import numpy as np
import pandas as pd
from fusion_runner import read, write, digest
from summarize_grid import canonical_counts, labels_from_files, number, sha
from design_compositions import applicable

DIFF = {"简单": "easy", "中等": "medium", "困难": "hard"}
CELL_METRICS = ("B8L2_mean", "B8L2_p10", "B8L2_worst", "D10_mean", "D10_p10", "D10_worst",
    "complete_rate", "score_available_rate", "nodes_mean", "iou_2d_mean", "IoU3D100_mean", "omission_mean", "extension_mean",
    "diag_wall_coverage_03_mean", "diag_wall_coverage_05_mean", "diag_corner_recall_05_mean",
    "ref_node_recall_9_mean", "ref_edge_recall_9_mean", "new_n_mean", "old_n_mean")
WITHIN_METRICS = ("within_abs_B8L2_change_mean", "within_abs_B8L2_change_max", "within_abs_D10_change_mean",
    "within_joint_stable_main_rate", "within_joint_stable_strict_rate", "within_joint_stable_wide_rate",
    "within_floor_jaccard_difference_mean", "within_structure_bound_cyclic_deg_mean", "within_mean_height_prism_pair_iou_mean",
    "within_turnover_mean", "within_turnover_min", "within_turnover_max")


def save(path, rows):
    frame = rows if isinstance(rows, pd.DataFrame) else pd.DataFrame(rows)
    if not len(frame.columns):
        frame = pd.DataFrame(columns=["stage", "phase", "method_id", "domain", "k"])
    compression = {"method": "gzip", "mtime": 0} if str(path).endswith(".gz") else None
    temp = Path(path).with_name(Path(path).name + f".writing.{os.getpid()}")
    frame.to_csv(temp, index=False, float_format="%.10g", compression=compression)
    # A completed table must be fully readable before it is named in a receipt.
    if len(frame.columns):
        assert len(pd.read_csv(temp, compression="gzip" if compression else None)) == len(frame)
    os.replace(temp, path)
    return frame


def finite_mean(values):
    a = np.asarray(values, float)
    a = a[np.isfinite(a)]
    return float(a.mean()) if len(a) else np.nan


def summaries(values, prefix):
    a = np.asarray(values, float)
    a = a[np.isfinite(a)]
    result = {prefix + "_n": len(a)}
    for key, fn in (("mean", np.mean), ("median", np.median), ("p10", lambda x: np.quantile(x, .1)), ("min", np.min), ("max", np.max)):
        result[prefix + "_" + key] = float(fn(a)) if len(a) else np.nan
    return result


def boot_buildings(values, key):
    a = np.asarray(values, float)
    a = a[np.isfinite(a)]
    if len(a) < 2:
        return np.nan, np.nan
    seed = int(hashlib.sha256(("20261019|" + repr(key)).encode()).hexdigest()[:16], 16)
    rng = np.random.default_rng(seed)
    means = a[rng.integers(0, len(a), size=(2000, len(a)))].mean(axis=1)
    return tuple(float(x) for x in np.quantile(means, [.025, .975]))


def add_definition(rows, rule, method, domain, k, ca, cb, label, primary=False, difficulty="all"):
    assert sum(ca.values()) == sum(cb.values()) == k and ca != cb
    rows.append(dict(rule_id=rule, method_id=method, domain=domain, k=int(k), counts_a=ca, counts_b=cb,
                     comparison_label=label, primary_contrast=primary, difficulty_filter=difficulty))


def frozen_definitions():
    rows = []
    # Canonical zero classes are filled after loading the fixed labels.
    for rule, method, lo, hi, sizes in (
        ("H1_Q_quantile", "F_rule_Q_quantile_K3", "C01", "C03", (5, 9, 13)),
        ("H3_reverse_relation", "R_geo9_source_signed_p2_K2", "C01", "C02", (5, 9, 13)),
        ("H9_semi_new", "F_semi_new_finalQ_K2", "C01", "C02", (5,))):
        domain = "semi_new" if rule == "H9_semi_new" else "all"
        for k in sizes:
            primary = k in ((5, 9) if rule == "H1_Q_quantile" else sizes)
            add_definition(rows, rule, method, domain, k, {lo: k}, {hi: k}, "higher_class_pure_minus_lower_class_pure", primary)
            for n in range(k):
                add_definition(rows, rule, method, domain, k, {lo: k-n, hi: n}, {lo: k-n-1, hi: n+1},
                               f"higher_class_count_{n}_to_{n+1}")
    mid = "R_role_ward_K5"
    add_definition(rows, "H4_detail_role", mid, "all", 5, {"C02": 5}, {"C05": 5}, "detail_pure_minus_common_pure", True)
    for detail in (3, 4):
        mix = {"C02": 5-detail, "C05": detail}
        for pure in ("C02", "C05"):
            add_definition(rows, "H4_detail_role", mid, "all", 5, {pure: 5}, mix, f"detail_count_{detail}_mix_minus_pure_{pure}", True)
    for k in (5, 7, 9):
        low = range(math.floor(.4*k)+1)
        high = range(math.ceil(.6*k), k+1)
        for a, b in itertools.product(low, high):
            add_definition(rows, "H5_hard_structure", "R_role_ward_difficulty_K2", "hard", k,
                           {"C01": k-a, "C02": a}, {"C01": k-b, "C02": b}, f"detail_count_{a}_to_{b}", True, "hard")
    for n in (9, 10, 11):
        for pure in ("C01", "C02"):
            add_definition(rows, "H7_conditional_complement", "R_geo9_source_signed_p2_K2", "all", 13,
                           {pure: 13}, {"C01": 13-n, "C02": n}, f"relation_mix_C02count{n}_minus_pure_{pure}", n == 10, "hard")
    for a in (3, 4):
        for pure in ("C01", "C02"):
            add_definition(rows, "H8_role_mixture", mid, "all", 9, {pure: 9}, {"C01": a, "C02": 9-a},
                           f"role_mix_C01count{a}_minus_pure_{pure}", True)
    for pure in ("C01", "C02"):
        add_definition(rows, "H10_semi_old_tendency", "F_semi_old_edit_K2", "semi_v1", 5,
                       {pure: 5}, {"C01": 3, "C02": 2}, f"old_semi_mix_minus_pure_{pure}", True)
    for pure in ("C01", "C03"):
        add_definition(rows, "H11_doorway", "F_doorway_finalQ_K3", "doorway", 9,
                       {pure: 9}, {"C01": 6, "C03": 3}, f"doorway_mix_minus_pure_{pure}", True)
    return rows


def normalize_definitions(definitions, labels, freeze):
    rules = {r["id"]: r for r in freeze["frozen_rules"]}
    for d in definitions:
        rule = rules[d["rule_id"]]
        assert d["method_id"] == rule.get("method", d["method_id"])
        classes = sorted(set(labels[d["method_id"], d["domain"]].values()))
        for side in ("a", "b"):
            counts = {c: d["counts_"+side].get(c, 0) for c in classes}
            assert sum(counts.values()) == d["k"]
            d["counts_"+side] = counts
            d["composition_"+side] = canonical_counts(counts)
        d["contrast_id"] = d["rule_id"] + "__" + digest({k: v for k, v in d.items() if k != "contrast_id"})[:16]
    return definitions


def worker_trait_mean(requests, traits, feature):
    means = []
    for r in {r["team_key"]: r for r in requests}.values():
        x = [traits.get(w, {}).get(feature, np.nan) for w in r["worker_ids"]]
        if all(np.isfinite(v) for v in x):
            means.append(float(np.mean(x)))
    return finite_mean(means), len(means)


def one_contrast(stage, definition, pid, a, b, requests, traits):
    d = definition
    key = (d["method_id"], d["domain"], pid, d["k"])
    ra = requests[key + (d["composition_a"],)]
    rb = requests[key + (d["composition_b"],)]
    ma, mb = {r["replicate"]: r for r in ra}, {r["replicate"]: r for r in rb}
    wa = sorted({w for r in ra for w in r["worker_ids"]})
    wb = sorted({w for r in rb for w in r["worker_ids"]})
    turnover = [len(set(ma[r]["worker_ids"]) - set(mb[r]["worker_ids"])) for r in sorted(set(ma) & set(mb))]
    minimum = sum(abs(d["counts_a"].get(c, 0)-d["counts_b"].get(c, 0)) for c in d["counts_a"]) // 2
    assert all(t >= minimum for t in turnover)
    row = dict(stage=stage["name"], phase=stage["phase"], contrast_id=d["contrast_id"], rule_id=d["rule_id"],
               method_id=d["method_id"], domain=d["domain"], k=d["k"], composition_a=d["composition_a"], composition_b=d["composition_b"],
               comparison_label=d["comparison_label"], primary_contrast=d["primary_contrast"],
               difficulty_filter=d["difficulty_filter"], pool_id=pid, image=a.image, image_id=a.image_id, building=a.building,
               difficulty=DIFF.get(a.difficulty, a.difficulty), reference_id=a.reference_id, reference_version=a.reference_version,
               request_rows_a=int(a.request_n), request_rows_b=int(b.request_n),
               requested_teams_a=int(a.requested_unique_team_n), requested_teams_b=int(b.requested_unique_team_n),
               unique_teams_a=int(a.unique_team_n), unique_teams_b=int(b.unique_team_n),
               scored_teams_a=int(a.score_available_n), scored_teams_b=int(b.score_available_n),
               complete_teams_a=int(a.complete_n), complete_teams_b=int(b.complete_n),
               workers_a="|".join(wa), workers_b="|".join(wb), workers_union="|".join(sorted(set(wa) | set(wb))),
               team_keys_a=a.team_keys, team_keys_b=b.team_keys,
               within_pairs_a=int(a.within_unique_team_pair_n), within_pairs_b=int(b.within_unique_team_pair_n),
               minimum_count_vector_turnover=minimum, same_rep_actual_pairs=len(turnover),
               same_rep_turnover_mean=finite_mean(turnover), same_rep_turnover_min=min(turnover) if turnover else np.nan,
               same_rep_turnover_max=max(turnover) if turnover else np.nan,
               same_rep_exact_minimum_turnover_n=sum(t == minimum for t in turnover),
               all_team_scores_present=bool(a.score_available_n == a.unique_team_n and b.score_available_n == b.unique_team_n))
    for metric in CELL_METRICS + WITHIN_METRICS:
        row[metric + "_a"] = a[metric]
        row[metric + "_b"] = b[metric]
        row[metric + "_change"] = b[metric] - a[metric]
    ownq = "theta_hard" if d["domain"] == "hard" else {"semi_new": "semi_new_q_effect", "semi_v1": "semi_v1_q_effect", "doorway": "doorway_q_effect"}.get(d["domain"], "q_beta")
    for feature in sorted(set(("q_beta", ownq))):
        for side, rs in (("a", ra), ("b", rb)):
            value, known = worker_trait_mean(rs, traits, feature)
            row[feature+"_historical_team_mean_"+side] = value
            row[feature+"_all_members_known_teams_"+side] = known
        row[feature+"_historical_team_mean_change"] = row[feature+"_historical_team_mean_b"]-row[feature+"_historical_team_mean_a"]
    return row


def aggregate_contrasts(per_image):
    aggregate, building_rows = [], []
    if per_image.empty:
        return aggregate, building_rows
    keys = ["stage", "phase", "contrast_id", "rule_id", "method_id", "domain", "k", "composition_a", "composition_b", "comparison_label", "primary_contrast", "difficulty_filter"]
    for key, g in per_image.groupby(keys, dropna=False, sort=True):
        meta = dict(zip(keys, key))
        slices = ["all"] + sorted(g.difficulty.unique()) if meta["difficulty_filter"] == "all" else [meta["difficulty_filter"]]
        for scope in slices:
            h = g if scope == "all" else g[g.difficulty == scope]
            q = h.B8L2_mean_change
            row = dict(meta, reported_difficulty=scope, paired_images=len(h), paired_buildings=int(h.building.nunique()),
                       quality_paired_images=int(q.notna().sum()), all_team_scores_present_images=int(h.all_team_scores_present.sum()),
                       unique_teams_a=int(h.unique_teams_a.sum()), unique_teams_b=int(h.unique_teams_b.sum()),
                       scored_teams_a=int(h.scored_teams_a.sum()), scored_teams_b=int(h.scored_teams_b.sum()),
                       complete_teams_a=int(h.complete_teams_a.sum()), complete_teams_b=int(h.complete_teams_b.sum()),
                       within_unique_team_pairs_a=int(h.within_pairs_a.sum()), within_unique_team_pairs_b=int(h.within_pairs_b.sum()),
                       unique_workers=len({w for x in h.workers_union for w in x.split("|")}),
                       image_ids="|".join(sorted(h.image)), building_ids="|".join(sorted(h.building.unique())),
                       actual_cross_same_rep_pairs=int(h.same_rep_actual_pairs.sum()),
                       actual_cross_turnover_mean_image_equal=finite_mean(h.same_rep_turnover_mean),
                       count_vector_turnover=int(h.minimum_count_vector_turnover.iloc[0]))
            row.update(summaries(q, "image_B8L2_change"))
            for threshold in (0, 2, 5):
                row[f"positive_gt{threshold}_images"] = int((q > threshold).sum())
                row[f"negative_ltminus{threshold}_images"] = int((q < -threshold).sum())
            row["positive_fraction_scored_images"] = float((q.dropna() > 0).mean()) if q.notna().any() else np.nan
            metric_changes = [c for c in h if c.endswith("_change") and c not in ("node_count_change",)]
            by_building = h.groupby("building")[metric_changes].mean()
            for bld, b in by_building.iterrows():
                bh = h[h.building == bld]
                building_rows.append(dict(meta, reported_difficulty=scope, building=bld, images=len(bh),
                                           scored_images=int(bh.B8L2_mean_change.notna().sum()), **b.to_dict()))
            row.update(summaries(by_building.B8L2_mean_change, "building_B8L2_change"))
            row["building_bootstrap_low"], row["building_bootstrap_high"] = boot_buildings(by_building.B8L2_mean_change, (key, scope))
            row["positive_buildings"] = int((by_building.B8L2_mean_change > 0).sum())
            row["negative_buildings"] = int((by_building.B8L2_mean_change < 0).sum())
            for metric in CELL_METRICS + WITHIN_METRICS:
                row[metric+"_change_image_equal"] = finite_mean(h[metric+"_change"])
                row[metric+"_change_building_equal"] = finite_mean(by_building[metric+"_change"])
                row[metric+"_finite_paired_images"] = int(h[metric+"_change"].notna().sum())
                row[metric+"_finite_paired_buildings"] = int(by_building[metric+"_change"].notna().sum())
                for side in ("a", "b"):
                    row[metric+"_"+side+"_image_equal"] = finite_mean(h[metric+"_"+side])
            row["within_comparable_images_a"] = int(h.within_joint_stable_main_rate_a.notna().sum())
            row["within_comparable_images_b"] = int(h.within_joint_stable_main_rate_b.notna().sum())
            for feature in ("q_beta", "theta_hard", "semi_new_q_effect", "semi_v1_q_effect", "doorway_q_effect"):
                col = feature + "_historical_team_mean_change"
                if col in h:
                    row[col] = finite_mean(h[col])
            if q.notna().any():
                for tag, ix in (("best", q.idxmax()), ("worst", q.idxmin())):
                    row[tag+"_image"] = h.loc[ix, "image"]
                    row[tag+"_B8L2_change"] = h.loc[ix, "B8L2_mean_change"]
            aggregate.append(row)
    return aggregate, building_rows


def curve_tables(stage, manifest, cells, pools, split, labels):
    if not manifest.get("curve_index"):
        return [], []
    index = pd.DataFrame(manifest["curve_index"])
    index["phase"], index["stage"] = stage["phase"], stage["name"]
    cm = cells.drop(columns=["phase"])
    merged = index.merge(cm, on=["method_id", "domain", "pool_id", "k", "composition"], how="left", validate="many_to_one")
    aggregate, availability = [], []
    for key, g in merged.groupby(["method_id", "domain", "curve_id", "k", "target_class", "target_n", "target_fraction"]):
        mid, dom, cid, k, target, n, frac = key
        eligible = [p for p in pools.values() if p["meta"]["building"] in split[stage["phase"]+"_buildings"] and applicable(p, dom)]
        scope_known = sum(any(r["worker_id"] in labels[mid, dom] for r in p["records"]) for p in eligible)
        row = dict(stage=stage["name"], phase=stage["phase"], method_id=mid, domain=dom, curve_id=cid, k=int(k),
                   target_class=target, target_n=int(n), target_fraction=frac,
                   all_condition_eligible_pools=len(eligible), any_known_class_pools=scope_known,
                   positions_with_enough_total_people=len(g), feasible_pools=int(g.feasible.sum()),
                   infeasible_ratio_pools=int((~g.feasible).sum()), evaluated_pools=int(g.unique_team_n.notna().sum()))
        availability.append(row)
        assert int(g.feasible.sum()) == int(g.unique_team_n.notna().sum()), "feasible curve point missing its summary"
        h = g[g.unique_team_n.notna()]
        for scope in ["all"] + sorted(h.difficulty.dropna().unique()):
            v = h if scope == "all" else h[h.difficulty == scope]
            if not len(v):
                continue
            r = dict(row, reported_difficulty=DIFF.get(scope, scope), images=int(v.image_id.nunique()),
                     buildings=int(v.building.nunique()), unique_teams=int(v.unique_team_n.sum()),
                     scored_teams=int(v.score_available_n.sum()), complete_teams=int(v.complete_n.sum()),
                     within_comparable_images=int(v.within_joint_stable_main_rate.notna().sum()),
                     image_ids="|".join(sorted(v.image)), min_unique_teams_per_image=int(v.unique_team_n.min()),
                     max_unique_teams_per_image=int(v.unique_team_n.max()))
            for metric in CELL_METRICS + WITHIN_METRICS:
                r[metric+"_image_equal"] = finite_mean(v[metric])
                by_building = v.groupby("building")[metric].mean()
                r[metric+"_building_equal"] = finite_mean(by_building)
                r[metric+"_finite_images"] = int(v[metric].notna().sum())
                r[metric+"_finite_buildings"] = int(by_building.notna().sum())
            r["B8L2_mean_building_boot_low"], r["B8L2_mean_building_boot_high"] = boot_buildings(v.groupby("building").B8L2_mean.mean(), (stage["name"], key, scope))
            aggregate.append(r)
    return aggregate, availability


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--stages", type=Path, required=True, help="JSON list: name, phase, requests, grid; stages in chronological order")
    ap.add_argument("--freeze", type=Path, required=True)
    ap.add_argument("--snapshot", type=Path, required=True)
    ap.add_argument("--split", type=Path, required=True)
    ap.add_argument("--labels", type=Path, action="append", required=True)
    ap.add_argument("--features", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    stages, freeze, split = read(args.stages), read(args.freeze), read(args.split)
    expected_label_hashes = {value for path, value in freeze["file_sha256"].items() if Path(path).name == "worker_labels.csv.gz"}
    assert {sha(path) for path in args.labels} == expected_label_hashes, "supplied personnel labels do not equal frozen validation labels"
    labels = labels_from_files(args.labels)
    pools = {p["pool_id"]: p for p in read(args.snapshot)["images"]}
    traits = pd.read_csv(args.features).set_index("worker_id").to_dict("index")
    definitions = normalize_definitions(frozen_definitions(), labels, freeze)
    outrows, missing, curves, opportunities, overlap, stage_receipts = [], [], [], [], [], []
    prior_teams = collections.defaultdict(set)
    prior_physical_teams = set()
    for stage in stages:
        grid = Path(stage["grid"])
        receipt = read(grid / "GRID_SUMMARY_RECEIPT.json")
        assert receipt["phase"] == stage["phase"] and receipt["missing_computations"] == 0 and receipt["full_manifest_pool_coverage"]
        manifest = read(stage["requests"])
        assert sha(stage["requests"]) in receipt["input_hashes"].values(), "different request manifest from the audited grid"
        cells = pd.read_csv(grid / "cell_summary.csv.gz")
        assert len(cells) == receipt["cells"] and set(cells.phase) == {stage["phase"]}
        assert set(cells.building) <= set(split[stage["phase"]+"_buildings"])
        index = cells.set_index(["method_id", "domain", "pool_id", "k", "composition"])
        requests = collections.defaultdict(list)
        for r in manifest["requests"]:
            requests[(r["method_id"], r["domain"], r["pool_id"], r["k"], r["composition"])].append(r)
        stage_physical_teams = set()
        for key, rs in requests.items():
            current = {r["team_key"] for r in rs}
            old = prior_teams[key]
            overlap.append(dict(stage=stage["name"], phase=stage["phase"], method_id=key[0], domain=key[1], pool_id=key[2], k=key[3],
                                composition=key[4], unique_teams=len(current), previously_seen_same_cell_teams=len(current & old),
                                previously_seen_team_any_method=len(current & prior_physical_teams),
                                genuinely_new_member_teams=len(current-prior_physical_teams)))
            old.update(current)
            stage_physical_teams.update(current)
        for d in definitions:
            present = cells[(cells.method_id == d["method_id"]) & (cells.domain == d["domain"]) & (cells.k == d["k"])]
            if not len(present):
                missing.append(dict(stage=stage["name"], phase=stage["phase"], contrast_id=d["contrast_id"], rule_id=d["rule_id"],
                                    method_id=d["method_id"], domain=d["domain"], k=d["k"], pool_id="", image="", building="",
                                    coverage_scope="entire_method_domain_size", reason="not_declared_or_no_requested_cell_in_this_stage",
                                    missing_a=True, missing_b=True, composition_a=d["composition_a"], composition_b=d["composition_b"]))
                continue
            eligible = [p for p in pools.values() if p["meta"]["building"] in split[stage["phase"]+"_buildings"] and applicable(p, d["domain"])]
            if d["difficulty_filter"] != "all":
                eligible = [p for p in eligible if DIFF.get(p["meta"]["difficulty"]) == d["difficulty_filter"]]
            for p in eligible:
                pid = p["pool_id"]
                keya = (d["method_id"], d["domain"], pid, d["k"], d["composition_a"])
                keyb = (d["method_id"], d["domain"], pid, d["k"], d["composition_b"])
                havea, haveb = keya in index.index, keyb in index.index
                mapping = labels[d["method_id"], d["domain"]]
                capacities = collections.Counter(mapping[r["worker_id"]] for r in p["records"] if r["worker_id"] in mapping)
                feasiblea = all(capacities[c] >= n for c, n in d["counts_a"].items())
                feasibleb = all(capacities[c] >= n for c, n in d["counts_b"].items())
                if not havea or not haveb:
                    missing.append(dict(stage=stage["name"], phase=stage["phase"], contrast_id=d["contrast_id"], rule_id=d["rule_id"],
                                        method_id=d["method_id"], domain=d["domain"], k=d["k"], pool_id=pid, image=p["meta"]["image"],
                                        building=p["meta"]["building"], class_capacity_json=json.dumps(dict(capacities), sort_keys=True),
                                        coverage_scope="individual_pool",
                                        missing_a=not havea, missing_b=not haveb, composition_a_feasible=feasiblea, composition_b_feasible=feasibleb,
                                        reason="not_sampled_on_declared_curve_or_grid" if feasiblea and feasibleb else "insufficient_actual_class_members",
                                        composition_a=d["composition_a"], composition_b=d["composition_b"]))
                    continue
                outrows.append(one_contrast(stage, d, pid, index.loc[keya], index.loc[keyb], requests, traits))
        pointrows, pointavailability = curve_tables(stage, manifest, cells, pools, split, labels)
        curves.extend(pointrows)
        opportunities.extend(pointavailability)
        stage_receipts.append(dict(name=stage["name"], phase=stage["phase"], requests=receipt["request_rows"],
                                    unique_teams=receipt["observed_unique_teams"], images=receipt["images"], buildings=receipt["buildings"],
                                    genuinely_new_unique_teams=len(stage_physical_teams-prior_physical_teams),
                                    previously_seen_unique_teams=len(stage_physical_teams & prior_physical_teams),
                                    grid_receipt_sha256=sha(grid / "GRID_SUMMARY_RECEIPT.json")))
        prior_physical_teams.update(stage_physical_teams)
        print(json.dumps(stage_receipts[-1]), flush=True)
    per_image = save(args.out / "frozen_contrasts_per_image.csv.gz", outrows)
    aggregate, buildings = aggregate_contrasts(per_image)
    save(args.out / "frozen_contrasts_aggregate.csv.gz", aggregate)
    save(args.out / "frozen_contrasts_per_building.csv.gz", buildings)
    save(args.out / "frozen_contrast_coverage_gaps.csv.gz", missing)
    save(args.out / "integer_curve_aggregate.csv.gz", curves)
    save(args.out / "integer_curve_availability.csv.gz", opportunities)
    save(args.out / "member_replication_overlap.csv.gz", overlap)
    write(args.out / "FROZEN_COMPARISONS_RECEIPT.json", dict(schema="frozen_composition_comparisons_v1", freeze_sha256=sha(args.freeze),
          exact_frozen_label_hashes_verified=sorted(expected_label_hashes), descriptive_historical_feature_sha256=sha(args.features),
          source_sha256=sha(Path(__file__)), stages=stage_receipts, contrast_definitions=definitions,
          actual_per_image_contrasts=len(outrows), primary_building_equal=True,
          confidence_interval="descriptive 2000 resamples of observed building mean differences; not external blind confidence or a p-value success gate",
          member_comparison="within observed members with actual turnover; cross same-replicate intersections are diagnostics, not strict matched-core causal contrasts",
          score_missing="finite paired cell means only; attempts/complete/scored denominators retained; no missing-to-zero conversion",
          method_scope="H2 within-composition diagnostics accompany every comparison; H6 nested and strict replacement blocks are analyzed separately",
          curve_scope="only declared integer 1D lines; infeasible proportions and insufficient total people are explicit; line means at different n/proportions can have different image support"))


if __name__ == "__main__":
    main()
