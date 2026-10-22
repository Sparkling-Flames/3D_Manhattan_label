"""Registered, finite-panel personnel composition and genuine-prefix analysis.

All data are release v1. This script consumes frozen geometries and labels learned
outside the target building. It never changes geometry scores, references, source
eligibility, human exclusions, worker weights, or raw annotations.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import gzip
import hashlib
from itertools import combinations
import json
import math
import os
from pathlib import Path
import sys
import time

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
REPO = Path(os.environ.get("WORKER_PROFILE_REPO", str(ROOT / "repo"))).resolve()
OUT = Path(os.environ.get("WORKER_PROFILE_OUTPUT", str(HERE))).resolve()
OUT.mkdir(parents=True, exist_ok=True)
sys.path[:0] = [str(ROOT / "runtime_deps"), str(REPO)]
from shapely.ops import unary_union
from tools.thesis_main.analysis.wall_consensus_population_20261014 import (
    footprint, reconstruct, fuse, WORKING_GAP, compact,
)

W = REPO / "research/workers/worker_b8l2_d10_20261017"
F = REPO / "research/fusion/wall_consensus_d10_20261017"
POP = REPO / "research/fusion/wall_consensus_population_20261014"
OLDW = REPO / "research/workers/worker_wq_integration_20261015"
REG = json.loads((HERE / "REGISTRATION.json").read_text())
PRIMARY = REG["primary_images"]
OUTCOMES = ["B8L2", "D10", "raw_R", "complete_evaluable"]


def csv(name, rows):
    d = rows if isinstance(rows, pd.DataFrame) else pd.DataFrame(rows)
    d.to_csv(OUT / name, index=False, encoding="utf-8-sig")
    return d


def save(name, obj):
    def default(x):
        if isinstance(x, np.generic): return x.item()
        if isinstance(x, Path): return str(x)
        raise TypeError(type(x).__name__)
    (OUT / name).write_text(json.dumps(obj, ensure_ascii=False, indent=2, default=default), encoding="utf-8")


def finite(x):
    return x is not None and pd.notna(x) and np.isfinite(float(x))


def avg(values):
    values = [float(x) for x in values if finite(x)]
    return float(np.mean(values)) if values else np.nan


def corr(a, b):
    d = pd.DataFrame({"a": a, "b": b}).dropna()
    return d.a.corr(d.b, method="spearman") if len(d) >= 3 and d.a.nunique() > 1 and d.b.nunique() > 1 else np.nan


def composition(counts, categories):
    return "|".join(str(counts.get(c, 0)) for c in categories)


def vector_iter(capacities, k, prefix=()):
    if len(capacities) == 1:
        if 0 <= k <= capacities[0]: yield prefix + (k,)
        return
    lo = max(0, k - sum(capacities[1:]))
    for n in range(lo, min(capacities[0], k) + 1):
        yield from vector_iter(capacities[1:], k - n, prefix + (n,))


def init():
    traj = pd.read_csv(F / "trajectory_scores.csv")
    allteams = pd.read_csv(W / "team_scores.csv")
    ledger = pd.read_csv(W / "personnel_ledger.csv")
    folds = pd.read_csv(W / "fold_profiles.csv")
    bridge = pd.read_csv(F / "member_bridge.csv")
    snap = json.loads((POP / "input_snapshot.json").read_text(encoding="utf-8-sig"))
    images = {im["image"]: im for im in snap["images"]}
    assert len(traj) == 7320 and len(allteams) == 642
    assert traj.loc[traj.primary_comparison_eligible, "image"].unique().tolist() == PRIMARY
    attempts = traj[traj.image.isin(PRIMARY)].copy()
    assert len(attempts) == 4032 and attempts.primary_comparison_eligible.sum() == 3578
    assert attempts.source_pool_allowed.all() and attempts.members_equal_frozen.all()
    assert attempts.member_quality_restrictions_clear.all() and attempts.member_target_bindings_clear.all()
    assert not attempts.original_holdout.any() and not attempts.is_oos.any()
    assert attempts.current_team_target_relation.eq("all_declared_target").all()
    attempts["building_id"] = attempts.image.str.rsplit("-", n=1).str[0]

    alias, member_rows, lookup, rawdist, geometry, payloads = {}, [], {}, {}, {}, {}
    f = folds[(folds.panel.eq("current") & folds.axis.isin(["B8L2", "D10"])) |
              (folds.panel.eq("T_source") & folds.axis.eq("T_source"))].copy()
    assert not f.duplicated(["axis", "fold", "worker_id"]).any()
    f = f.set_index(["axis", "fold", "worker_id"]).to_dict("index")
    # The inventory can retain excluded/repeated source tasks for one image/person.
    # Use the frozen admitted object ID; image/person alone is not the record key.
    lm = ledger.set_index("object_id", drop=False)
    assert lm.index.is_unique
    bm = bridge.set_index("record_id")
    cached_old = pd.read_csv(OLDW / "cached_team_scores.csv").set_index(["image", "subset"])
    for image in PRIMARY:
        im = images[image]; building = im["building"]
        alias[image] = {r["worker"]: bm.loc[r["id"], "worker_id"] for r in im["records"]}
        assert len(alias[image]) == 24 and len(set(alias[image].values())) == 24
        polys = {r["worker"]: footprint(reconstruct(r)["floor"]) for r in im["records"]}
        assert all(p is not None for p in polys.values())
        union_area = unary_union(list(polys.values())).area
        rawdist[image] = {tuple(sorted((a, b))): pa.symmetric_difference(polys[b]).area / union_area
                          for a, pa in polys.items() for b in polys if a < b}
        record_by_p = {r["worker"]: r["id"] for r in im["records"]}
        for p, worker in alias[image].items():
            r = dict(image=image, building_id=building, source_worker=p, worker_id=worker)
            lr = lm.loc[bm.loc[record_by_p[p], "object_id"]]
            assert lr.image_code == image and lr.worker_id == worker and lr.condition == "manual"
            for col in ["object_id", "source_active_time_seconds", "target_matched_time_seconds", "B8L2", "D10"]:
                r[col] = lr[col]
            for axis in ["B8L2", "D10", "T_source"]:
                q = f.get((axis, building, worker))
                ok = bool(q and q["supported"])
                if q:
                    assert building not in json.loads(q["training_buildings"]), (image, worker, axis)
                r[axis + "_supported"] = ok
                r[axis + "_effect"] = q["effect"] if ok else np.nan
                r[axis + "_contexts"] = q["contexts"] if q else 0
                r[axis + "_buildings"] = q["buildings"] if q else 0
                r[axis + "_training_buildings"] = q["training_buildings"] if q else "[]"
            r["T_class"] = "fast" if r["T_source_effect"] < 0 else "slow" if finite(r["T_source_effect"]) else "unknown"
            for axis in ["B8L2", "D10"]:
                e = r[axis + "_effect"]
                r[axis + "_Q2"] = "high" if e > 0 else "low" if finite(e) else "unknown"
                r[axis + "_Qmargin2"] = "high" if e > 2 else "low" if e < -2 else "boundary" if finite(e) else "unknown"
                r[axis + "_QT"] = r[axis + "_Q2"] + "_" + r["T_class"]
            member_rows.append(r); lookup[(image, worker)] = r
        path = POP / "states" / (image + ".json.gz")
        payload = json.load(gzip.open(path, "rt", encoding="utf-8")); payloads[image] = payload
        geometry[image] = {"|".join(sorted(s["workers"])): s["automatic"] for s in payload["states"]}
        assert len(geometry[image]) == len(payload["states"])
        for s in payload["states"]:
            actual = {m["worker"] for g in s["automatic"]["identity_groups"] for m in g["members"]}
            assert actual == set(s["workers"]) and s["automatic"]["n"] == len(actual)
            ids = {r["id"] for r in im["records"] if r["worker"] in actual}
            seenids = {m["id"] for g in s["automatic"]["identity_groups"] for m in g["members"]}
            assert ids == seenids
        for r in attempts[attempts.image.eq(image)].itertuples():
            order = payload["orders"][r.path]
            assert r.subset == "|".join(sorted(order[:r.k]))
            assert len(order) == len(set(order)) == 24
            assert set(r.worker_ids.split("|")) == {alias[image][p] for p in order[:r.k]}
            state = geometry[image][r.subset]
            assert state["n"] == r.k
            assert len(state["node_consensus"]["nodes"]) == r.nodes
            assert (state["candidate"]["points"] is not None) == r.connection_available
            assert (state["candidate"].get("geometry_status") == "ok" and r.nodes >= 4) == r.complete_evaluable
        for r in allteams[allteams.image.eq(image)].itertuples():
            ps = r.subset.split("|")
            measured_R = avg(rawdist[image][tuple(sorted(ab))] for ab in combinations(ps, 2))
            assert abs(measured_R - cached_old.loc[(image, r.subset), "raw_pair_distance"]) < 1e-12
    return attempts, allteams, ledger, folds, images, alias, pd.DataFrame(member_rows), lookup, rawdist, geometry, payloads


CATS = {
    "Q2": ["high", "low", "unknown"],
    "QT": ["high_fast", "high_slow", "high_unknown", "low_fast", "low_slow", "low_unknown", "unknown_unknown"],
    "Qmargin2": ["high", "boundary", "low", "unknown"],
}


def enrich(rows, alias, lookup, rawdist, workers_col):
    result = []
    for row in rows.to_dict("records"):
        workers = row[workers_col].split("|")
        people = [lookup[(row["image"], w)] for w in workers]
        pworkers = row["subset"].split("|")
        row["raw_R"] = avg(rawdist[row["image"]][tuple(sorted(ab))] for ab in combinations(pworkers, 2)) if len(workers) >= 2 else np.nan
        for name in ["source", "target_matched"]:
            col = name + "_active_time_seconds" if name == "source" else "target_matched_time_seconds"
            ts = [p[col] for p in people]
            valid = [t for t in ts if finite(t) and t > 0]
            row[name + "_time_known_n"] = len(valid)
            row[name + "_time_missing_n"] = len(ts) - len(valid)
            row[name + "_time_known_sum_seconds"] = sum(valid) if valid else np.nan
            row[name + "_time_total_seconds"] = sum(valid) if len(valid) == len(ts) else np.nan
        for axis in ["B8L2", "D10"]:
            q = [p[axis + "_effect"] for p in people]
            row[axis + "_mean_effect"] = avg(q) if all(finite(x) for x in q) else np.nan
            for name, cats in CATS.items():
                counts = Counter(p[axis + "_" + name] for p in people)
                assert set(counts) <= set(cats), (name, counts)
                row[axis + "_" + name + "_composition"] = composition(counts, cats)
                if name == "Q2": row[axis + "_high_n"] = counts["high"]
        ts = [p["T_source_effect"] for p in people]
        row["T_mean_effect"] = avg(ts) if all(finite(x) for x in ts) else np.nan
        row["T_supported_n"] = sum(finite(x) for x in ts)
        row["T_fast_n"] = sum(p["T_class"] == "fast" for p in people)
        result.append(row)
    return pd.DataFrame(result)


def composition_tables(traj, members):
    rows = []
    for image in PRIMARY:
        m = members[members.image.eq(image)]
        d = traj[traj.image.eq(image)]
        for axis in ["B8L2", "D10"]:
            for candidate, cats in CATS.items():
                cap = Counter(m[axis + "_" + candidate]); capacities = [cap[c] for c in cats]
                for k in range(1, 25):
                    subsets = d[d.k.eq(k)]
                    bycomp = {key: g for key, g in subsets.groupby(axis + "_" + candidate + "_composition")}
                    for vec in vector_iter(capacities, k):
                        key = "|".join(map(str, vec)); g = bycomp.get(key)
                        r = dict(image=image, building_id=m.building_id.iloc[0], axis=axis, candidate=candidate, k=k,
                                 categories="|".join(cats), composition=key, pool_capacities="|".join(map(str, capacities)),
                                 feasible_exact_teams=math.prod(math.comb(c, n) for c, n in zip(capacities, vec)),
                                 observed_path_states=0 if g is None else len(g), observed_unique_subsets=0 if g is None else g.subset.nunique(),
                                 successful_states=0 if g is None else int(g.complete_evaluable.sum()),
                                 source_time_complete_states=0 if g is None else int(g.source_time_total_seconds.notna().sum()),
                                 target_time_complete_states=0 if g is None else int(g.target_matched_time_total_seconds.notna().sum()))
                        for out in OUTCOMES + ["source_time_total_seconds", "target_matched_time_total_seconds"]:
                            r[out + "_mean"] = np.nan if g is None else g[out].mean()
                        rows.append(r)
    c = csv("feasible_compositions.csv", rows)
    cs = c.groupby(["axis", "candidate", "image", "k"], as_index=False).agg(
        feasible_compositions=("composition", "size"), observed_compositions=("observed_path_states", lambda s: int(s.gt(0).sum())),
        feasible_teams=("feasible_exact_teams", "sum"), observed_path_states=("observed_path_states", "sum"),
        observed_unique_subsets=("observed_unique_subsets", "sum"))
    assert (cs.feasible_teams == cs.k.map(lambda k: math.comb(24, k))).all()
    csv("composition_coverage.csv", cs)
    return c


def path_probes(traj, payloads, lookup, alias):
    choices, summaries, matched, fullpaths = [], [], [], []
    for image in PRIMARY:
        d = traj[traj.image.eq(image)]
        for axis in ["B8L2", "D10"]:
            ranked = d[d.k.eq(8)].sort_values([axis + "_mean_effect", "path"], ascending=[False, True])
            groups = {"all_random_paths": set(ranked.path), "six_highest_first8_mean_Q": set(ranked.path.head(6)),
                      "six_lowest_first8_mean_Q": set(ranked.path.tail(6))}
            for rank, r in enumerate(ranked.itertuples(), 1):
                choices.append(dict(image=image, axis=axis, path=r.path, first8_mean_effect=getattr(r, axis + "_mean_effect"),
                                    rank=rank, selected_high=rank <= 6, selected_low=rank > 18,
                                    source_order="|".join(payloads[image]["orders"][r.path]),
                                    worker_order="|".join(alias[image][p] for p in payloads[image]["orders"][r.path])))
            for policy, paths in groups.items():
                p = d[d.path.isin(paths)]
                for k, g in p.groupby("k"):
                    r = dict(image=image, building_id=g.building_id.iloc[0], selection_axis=axis, policy=policy, k=int(k),
                             attempted_paths=len(g), complete_paths=int(g.complete_evaluable.sum()),
                             incomplete_paths=int((~g.complete_evaluable).sum()), policy_deferred_paths=int(g.k.eq(2).sum()),
                             source_time_complete_paths=int(g.source_time_total_seconds.notna().sum()),
                             target_time_complete_paths=int(g.target_matched_time_total_seconds.notna().sum()),
                             below_four_paths=int(g.below_four.sum()))
                    for out in OUTCOMES + ["source_time_total_seconds", "target_matched_time_total_seconds", axis + "_mean_effect", axis + "_high_n"]:
                        r[out + "_mean"] = g[out].mean()
                    summaries.append(r)
                for lo, hi in [(4, 8), (8, 16), (16, 24)]:
                    a = p[p.k.eq(lo)].set_index("path"); b = p[p.k.eq(hi)].set_index("path")
                    r = dict(image=image, building_id=p.building_id.iloc[0], selection_axis=axis, policy=policy, k_from=lo, k_to=hi,
                             paths=len(paths), complete_from=int(a.complete_evaluable.sum()), complete_to=int(b.complete_evaluable.sum()))
                    for out in ["B8L2", "D10", "raw_R", "source_time_total_seconds", "target_matched_time_total_seconds"]:
                        pair = a[[out]].join(b[[out]], lsuffix="_from", rsuffix="_to").dropna()
                        r[out + "_paired_n"] = len(pair)
                        r[out + "_paired_change"] = (pair[out + "_to"] - pair[out + "_from"]).mean()
                    matched.append(r)
        for path, g in d.groupby("path"):
            g = g.sort_values("k")
            for prev, cur in zip(g.to_dict("records")[:-1], g.to_dict("records")[1:]):
                added = set(cur["worker_ids"].split("|")) - set(prev["worker_ids"].split("|"))
                assert len(added) == 1
                worker = next(iter(added)); person = lookup[(image, worker)]
                r = dict(image=image, building_id=cur["building_id"], path=path, k_from=prev["k"], k_to=cur["k"],
                         added_worker_id=worker, previous_subset=prev["subset"], current_subset=cur["subset"],
                         complete_from=prev["complete_evaluable"], complete_to=cur["complete_evaluable"],
                         source_active_seconds_added=person["source_active_time_seconds"],
                         target_matched_seconds_added=person["target_matched_time_seconds"])
                for ax in ["B8L2", "D10"]:
                    r[ax + "_effect_added"] = person[ax + "_effect"]
                    r[ax + "_Q2_added"] = person[ax + "_Q2"]
                    r[ax + "_QT_added"] = person[ax + "_QT"]
                    r[ax + "_high_n_before"] = prev[ax + "_high_n"]
                for out in ["B8L2", "D10", "raw_R"]:
                    r[out + "_change"] = cur[out] - prev[out]
                fullpaths.append(r)
    csv("path_selection_manifest.csv", choices)
    ps = csv("path_policy_by_image_k.csv", summaries)
    csv("path_matched_changes.csv", matched)
    steps = pd.DataFrame(fullpaths)
    saved = pd.read_csv(POP / "transitions.csv")
    saved = saved[saved.image.isin(PRIMARY)].drop(columns=["added_worker"])
    steps = steps.merge(saved, on=["image", "path", "k_from", "k_to"], validate="one_to_one")
    assert len(steps) == 3864
    csv("true_prefix_transitions.csv", steps)
    paired = []
    for (axis, k), g in ps.groupby(["selection_axis", "k"]):
        wide = g.pivot(index=["image", "building_id"], columns="policy")
        for out in [x for x in g if x.endswith("_mean")]:
            high = wide[(out, "six_highest_first8_mean_Q")]
            low = wide[(out, "six_lowest_first8_mean_Q")]
            baseline = wide[(out, "all_random_paths")]
            for ix in wide.index:
                paired.append(dict(image=ix[0], building_id=ix[1], selection_axis=axis, k=k, outcome=out,
                                   high_minus_low=high.loc[ix]-low.loc[ix], high_minus_random=high.loc[ix]-baseline.loc[ix]))
    p = csv("path_policy_paired_by_image.csv", paired)
    bybuilding = p.groupby(["selection_axis", "k", "outcome", "building_id"], as_index=False)[["high_minus_low", "high_minus_random"]].mean()
    csv("path_policy_paired_by_building.csv", bybuilding)
    csv("path_policy_summary.csv", bybuilding.groupby(["selection_axis", "k", "outcome"], as_index=False).agg(
        high_minus_low=("high_minus_low", "mean"), high_minus_random=("high_minus_random", "mean"),
        available_buildings=("high_minus_low", "count"), positive_buildings=("high_minus_low", lambda x: int(x.gt(0).sum())),
        min_building_difference=("high_minus_low", "min"), max_building_difference=("high_minus_low", "max")))
    return steps


def fixed_base(teams, lookup):
    entrants = pd.read_csv(W / "fixed_base_entrants.csv")
    old = pd.read_csv(OLDW / "cached_team_scores.csv")[["image", "subset", "raw_pair_distance", "complete_evaluable", "complete_floor_evaluable"]]
    entrants = entrants.merge(old, on=["image", "subset"], validate="many_to_one").rename(columns={"raw_pair_distance": "raw_R"})
    d = entrants[entrants.primary].copy()
    assert len(d) == 238 and d.B8L2.notna().sum() == 229
    for col in ["B8L2_Q2", "D10_Q2", "B8L2_QT", "D10_QT", "B8L2_Qmargin2", "D10_Qmargin2", "T_class",
                "source_active_time_seconds", "target_matched_time_seconds", "T_source_effect"]:
        d[col] = [lookup[(r.image, r.worker_id)][col] for r in d.itertuples()]
    csv("fixed_base_entrants_enriched.csv", d)
    rows = []
    specs = [("Q2", "high", "low"), ("QT", "high_fast", "high_slow"), ("QT", "low_fast", "low_slow"),
             ("QT", "high_fast", "low_fast"), ("QT", "high_slow", "low_slow"), ("Qmargin2", "high", "low")]
    for (image, base), g in d.groupby(["image", "base"]):
        for axis in ["B8L2", "D10"]:
            for candidate, label_a, label_b in specs:
                a = g[g[axis + "_" + candidate].eq(label_a)]; b = g[g[axis + "_" + candidate].eq(label_b)]
                r = dict(image=image, building_id=g.building_id.iloc[0], base=base, label_axis=axis, candidate=candidate,
                         contrast=label_a+"_minus_"+label_b, a_attempts=len(a), b_attempts=len(b),
                         a_complete=int(a.complete_evaluable.sum()), b_complete=int(b.complete_evaluable.sum()),
                         source_a_known=int(a.source_active_time_seconds.notna().sum()), source_b_known=int(b.source_active_time_seconds.notna().sum()),
                         target_a_known=int(a.target_matched_time_seconds.notna().sum()), target_b_known=int(b.target_matched_time_seconds.notna().sum()))
                for out in OUTCOMES + ["source_active_time_seconds", "target_matched_time_seconds"]:
                    r[out + "_a_mean"], r[out + "_b_mean"] = a[out].mean(), b[out].mean()
                    r[out + "_difference"] = a[out].mean() - b[out].mean()
                for t in ["source_active_time_seconds", "target_matched_time_seconds"]:
                    aa = a.dropna(subset=[t]); bb = b.dropna(subset=[t])
                    for out in ["B8L2", "D10", "raw_R", "complete_evaluable"]:
                        r[t + "_joint_" + out + "_difference"] = aa[out].mean() - bb[out].mean()
                    r[t + "_joint_quality_a_n"] = int(aa.B8L2.notna().sum())
                    r[t + "_joint_quality_b_n"] = int(bb.B8L2.notna().sum())
                rows.append(r)
    base = csv("fixed_base_class_contrasts.csv", rows)
    differences = [c for c in base if c.endswith("_difference")]
    supported = base[base.a_attempts.gt(0) & base.b_attempts.gt(0)]
    im = supported.groupby(["label_axis", "candidate", "contrast", "image", "building_id"], as_index=False)[differences].mean()
    csv("fixed_base_contrasts_by_image.csv", im)
    building = im.groupby(["label_axis", "candidate", "contrast", "building_id"], as_index=False)[differences].mean()
    csv("fixed_base_contrasts_by_building.csv", building)
    summary = []
    for key, g in building.groupby(["label_axis", "candidate", "contrast"]):
        for col in differences:
            vals = g[col].dropna()
            z = dict(zip(["label_axis", "candidate", "contrast"], key))
            z.update(outcome=col, available_buildings=len(vals), mean=vals.mean(), median=vals.median(),
                     minimum=vals.min(), maximum=vals.max(), positive_buildings=int(vals.gt(0).sum()),
                     leave_one_building_min=min([vals.drop(ix).mean() for ix in vals.index], default=np.nan),
                     leave_one_building_max=max([vals.drop(ix).mean() for ix in vals.index], default=np.nan))
            summary.append(z)
    csv("fixed_base_contrast_summary.csv", summary)
    return d, base


def replacement_tables(lookup):
    pairs = pd.read_csv(W / "replacement_pairs.csv")
    assert len(pairs) == 4076
    d = pairs[pairs.primary_attempt_eligible].copy()
    for axis in ["B8L2", "D10"]:
        for candidate in CATS:
            labels = []
            for r in d.itertuples():
                a = lookup[(r.image, r.removed)][axis + "_" + candidate]
                b = lookup[(r.image, r.added)][axis + "_" + candidate]
                unknown = "unknown" in a or "unknown" in b
                labels.append("unclassified" if unknown else "same_composition" if a == b else "changed_composition")
            d[axis + "_" + candidate + "_relation"] = labels
            if candidate in ["Q2", "QT"]:
                src = "current_" + axis + "_swap" if candidate == "Q2" else "QT_" + axis + "_swap"
                expected = d[src].replace({"same_class": "same_composition", "cross_class": "changed_composition"})
                assert expected.tolist() == labels
        d[axis + "_current_effect_change"] = [lookup[(r.image, r.added)][axis+"_effect"]-lookup[(r.image, r.removed)][axis+"_effect"] for r in d.itertuples()]
    d["source_active_time_change_seconds"] = [lookup[(r.image, r.added)]["source_active_time_seconds"]-lookup[(r.image, r.removed)]["source_active_time_seconds"] for r in d.itertuples()]
    d["target_matched_time_change_seconds"] = [lookup[(r.image, r.added)]["target_matched_time_seconds"]-lookup[(r.image, r.removed)]["target_matched_time_seconds"] for r in d.itertuples()]
    for col in ["B8L2_change", "D10_change", "raw_pair_change"]: d["abs_"+col] = d[col].abs()
    csv("replacement_pairs_enriched.csv", d)
    rows = []
    for (image, k, base), g in d.groupby(["image", "k", "base"]):
        for axis in ["B8L2", "D10"]:
            for candidate in CATS:
                rel = axis + "_" + candidate + "_relation"
                same = g[g[rel].eq("same_composition")]; cross = g[g[rel].eq("changed_composition")]
                r = dict(image=image, building_id=g.building_id.iloc[0], k=k, base=base, label_axis=axis, candidate=candidate,
                         attempted_pairs=len(g), same_pairs=len(same), cross_pairs=len(cross), unknown_pairs=int(g[rel].eq("unclassified").sum()),
                         same_floor_n=int(same.floor_change.notna().sum()), cross_floor_n=int(cross.floor_change.notna().sum()))
                for out in ["floor_change", "abs_B8L2_change", "abs_D10_change", "abs_raw_pair_change"]:
                    r[out + "_same"] = same[out].mean(); r[out + "_cross"] = cross[out].mean()
                    r[out + "_cross_minus_same"] = cross[out].mean()-same[out].mean()
                rows.append(r)
    b = csv("replacement_within_base.csv", rows)
    focused = b[b.k.eq(8) & b.same_pairs.gt(0) & b.cross_pairs.gt(0)]
    cols = [x for x in focused if x.endswith("_same") or x.endswith("_cross")]
    im = focused.groupby(["label_axis", "candidate", "image", "building_id"], as_index=False)[cols].mean()
    csv("replacement_7plus1_by_image.csv", im)
    bb = im.groupby(["label_axis", "candidate", "building_id"], as_index=False)[cols].mean()
    csv("replacement_7plus1_by_building.csv", bb)
    summary = []
    for key, g in bb.groupby(["label_axis", "candidate"]):
        for col in cols:
            a = g[col].dropna(); r = dict(label_axis=key[0], candidate=key[1], outcome=col, buildings=len(a),
                                       mean=a.mean(), minimum=a.min(), maximum=a.max(), positive_buildings=int(a.gt(0).sum()))
            summary.append(r)
    csv("replacement_7plus1_summary.csv", summary)
    return d, b


def same_k_pairs(traj, geometry):
    rows = []
    for (image, k), g in traj.groupby(["image", "k"]):
        candidates = {r.subset: footprint(geometry[image][r.subset]["candidate"]["footprint"]) for r in g.itertuples()}
        for a, b in combinations(g.itertuples(), 2):
            pa, pb = candidates[a.subset], candidates[b.subset]
            both = a.complete_floor_evaluable and b.complete_floor_evaluable
            delta = 1 - pa.intersection(pb).area / pa.union(pb).area if both else np.nan
            r = dict(image=image, building_id=a.building_id, k=k, path_a=a.path, path_b=b.path, subset_a=a.subset, subset_b=b.subset,
                     shared_members=len(set(a.subset.split("|")) & set(b.subset.split("|"))),
                     same_subset=a.subset == b.subset, both_complete_floor=both,
                     both_complete_quality=a.complete_evaluable and b.complete_evaluable, floor_difference=delta,
                     abs_B8L2_difference=abs(b.B8L2-a.B8L2), abs_D10_difference=abs(b.D10-a.D10), abs_raw_R_difference=abs(b.raw_R-a.raw_R))
            for axis in ["B8L2", "D10"]:
                for candidate in ["Q2", "QT", "Qmargin2"]:
                    col = axis + "_" + candidate + "_composition"
                    r[axis + "_" + candidate + "_same_composition"] = getattr(a, col) == getattr(b, col)
            if r["same_subset"] and both: assert abs(delta) < 1e-12
            rows.append(r)
    p = csv("same_k_geometry_pairs.csv", rows)
    summaries = []
    for axis in ["B8L2", "D10"]:
        for candidate in CATS:
            col = axis+"_"+candidate+"_same_composition"
            for (image, k, same, shared), g in p.groupby(["image", "k", col, "shared_members"]):
                summaries.append(dict(image=image, building_id=g.building_id.iloc[0], k=k, label_axis=axis,
                    candidate=candidate, same_composition=same, shared_members=shared, attempted_pairs=len(g),
                    evaluable_floor_pairs=int(g.both_complete_floor.sum()), evaluable_quality_pairs=int(g.both_complete_quality.sum()),
                    floor_difference=g.floor_difference.mean(), abs_B8L2_difference=g.abs_B8L2_difference.mean(),
                    abs_D10_difference=g.abs_D10_difference.mean(), abs_raw_R_difference=g.abs_raw_R_difference.mean()))
    csv("same_k_composition_geometry_by_image.csv", summaries)
    return p


def validate_replays(images, payloads, geometry):
    def structural_numeric_match(actual, expected, differences, path=""):
        if isinstance(actual, dict) and isinstance(expected, dict):
            assert set(actual) == set(expected), (path, "keys")
            for key in actual: structural_numeric_match(actual[key], expected[key], differences, path + "." + key)
        elif isinstance(actual, list) and isinstance(expected, list):
            assert len(actual) == len(expected), (path, "length")
            for i, (a, b) in enumerate(zip(actual, expected)):
                structural_numeric_match(a, b, differences, path + "." + str(i))
        elif isinstance(actual, (float, int)) and not isinstance(actual, bool) and isinstance(expected, (float, int)) and not isinstance(expected, bool):
            delta = abs(actual - expected)
            assert delta <= 1e-10, (path, actual, expected)
            if delta: differences.append(delta)
        else:
            assert actual == expected, (path, actual, expected)
    results = []
    for image in PRIMARY:
        records = {r["worker"]: r for r in images[image]["records"]}
        for k in [3, 8]:
            subset = tuple(sorted(payloads[image]["orders"][0][:k]))
            t = time.monotonic()
            observed = compact(fuse([records[w] for w in subset], gap=WORKING_GAP)["automatic"])
            expected = geometry[image]["|".join(subset)]
            differences = []
            structural_numeric_match(observed, expected, differences)
            results.append(dict(image=image, path=0, k=k, exact_discrete_structure_equal=True,
                                numeric_tolerance=1e-10, maximum_absolute_numeric_difference=max(differences, default=0),
                                differing_numeric_scalars=len(differences), seconds=time.monotonic()-t))
    csv("independent_prefix_replay_checks.csv", results)
    return results


def run():
    started = time.monotonic()
    (traj, allteams, ledger, folds, images, alias, members, lookup, rawdist, geometry, payloads) = init()
    csv("out_of_building_member_profiles.csv", members)
    traj = enrich(traj, alias, lookup, rawdist, "worker_ids")
    csv("primary_true_path_states.csv", traj)
    primaryteams = allteams[allteams.primary_attempt_eligible].copy()
    assert len(primaryteams) == 399
    old = pd.read_csv(OLDW / "cached_team_scores.csv")[["image", "subset", "complete_evaluable", "complete_floor_evaluable"]]
    primaryteams = primaryteams.merge(old, on=["image", "subset"], validate="one_to_one")
    primaryteams = enrich(primaryteams, alias, lookup, rawdist, "workers")
    csv("frozen_teams_enriched.csv", primaryteams)
    c = composition_tables(traj, members)
    print("Composition coverage and enriched states completed", flush=True)
    steps = path_probes(traj, payloads, lookup, alias)
    entrants, base = fixed_base(primaryteams, lookup)
    replacements, replace_summary = replacement_tables(lookup)
    print("Fixed base, member replacements and true paths completed", flush=True)
    pair = same_k_pairs(traj, geometry)
    checks = validate_replays(images, payloads, geometry)
    coverage = []
    for image, g in traj.groupby("image"):
        coverage.append(dict(image=image, building_id=g.building_id.iloc[0], path_attempts=len(g), paths=g.path.nunique(),
                             unique_subsets=g.subset.nunique(), complete_states=int(g.complete_evaluable.sum()),
                             policy_deferred_k2=int(g.k.eq(2).sum()), other_incomplete_states=int((~g.complete_evaluable & g.k.ne(2)).sum()),
                             source_timed_members=int(members[members.image.eq(image)].source_active_time_seconds.notna().sum()),
                             target_timed_members=int(members[members.image.eq(image)].target_matched_time_seconds.notna().sum()),
                             all_member_endpoint_complete=bool(g[g.k.eq(24)].complete_evaluable.all())))
    csv("primary_panel_coverage.csv", coverage)
    # At the shared complete-member endpoint, path variation must be zero, including conditional failures.
    for _, g in traj[traj.k.eq(24)].groupby("image"):
        assert g.subset.nunique() == 1 and g.complete_evaluable.nunique() == 1
        assert g.B8L2.nunique(dropna=False) == 1
    same_room = pd.read_csv(REPO / "research/same_room/same_room_update_20261017/actual_18_curve_relation_coverage.csv")
    assert len(same_room) == 3 and not same_room.scope_comparable_quality_curve.any()
    sha = []
    for f in [W / "fold_profiles.csv", W / "team_scores.csv", W / "replacement_pairs.csv", W / "personnel_ledger.csv", F / "trajectory_scores.csv", POP / "input_snapshot.json"]:
        sha.append(dict(path=str(f.relative_to(REPO)), sha256=hashlib.sha256(f.read_bytes()).hexdigest(), bytes=f.stat().st_size))
    receipt = dict(data_release="v1", commit=REG["repository_commit"], primary_images=len(PRIMARY),
                   primary_buildings=traj.building_id.nunique(), primary_path_attempts=len(traj),
                   successful_states=int(traj.complete_evaluable.sum()), policy_deferred_states=int(traj.k.eq(2).sum()),
                   other_incomplete_states=int((~traj.complete_evaluable & traj.k.ne(2)).sum()),
                   original_trajectories=7320, original_teams=len(allteams), primary_teams=len(primaryteams),
                   primary_complete_teams=int(primaryteams.B8L2.notna().sum()),
                   primary_replacement_pairs=len(replacements), fixed_7plus1_attempts=len(entrants),
                   fixed_7plus1_complete=int(entrants.B8L2.notna().sum()), fixed_7plus1_bases=entrants.groupby(["image", "base"]).ngroups,
                   unique_saved_geometries_verified=sum(len(g) for g in geometry.values()),
                   exact_prefix_memberships_verified=len(traj), independent_replayed_prefixes=len(checks),
                   labels_exclude_target_building=True, source_R_matches_legacy=True, class_relation_recomputation_matches=True,
                   same_k_path_pairs=len(pair), feasible_composition_rows=len(c), interpolation=False,
                   geometry_scores_reused=True, new_experimental_fusion_geometries=0,
                   same_room_scope_comparable_complete_curves=0, source_files=sha, elapsed_seconds=time.monotonic()-started)
    save("RUN_RECEIPT.json", receipt)
    print(json.dumps(receipt, ensure_ascii=False, indent=2), flush=True)


if __name__ == "__main__": run()
