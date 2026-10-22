"""Freeze an outcome-free finite Manual joint-class exchange experiment.

Only frozen labels/history and personnel inventory are read.  Native fusion is
performed centrally after this registration; this module makes no fusion calls.
"""
from __future__ import annotations

import collections
import gzip
import hashlib
import itertools
import json
import math
import os
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
V3 = ROOT / "research/workers/personnel_useful_taxonomy_v3_20261021"
LABELS = V3 / "taxonomy/ALL_METHOD_LABELS_LOBO.csv.gz"
PANELS = V3 / "composition/PANELS.csv"
SEED = "manual-joint-closure-finite-reservoir-20261022-v1"
FEATURES = ["q_history", "q_downside", "t_history", "turn_history", "short_history",
            "redundancy_history", "area_history", "height_history", "simple_turn_history",
            "complex_turn_history", "complex_short_history"]
META = ["pool_id", "image", "building", "condition", "layer", "difficulty"]


def digest(x):
    return hashlib.sha256(json.dumps(x, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def h(*x):
    return digest([SEED, *x])


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def team_key(pool, workers):
    return pool + "__" + digest(sorted(workers))[:20]


def write(path, df):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    b = df.to_csv(index=False).encode("utf-8-sig")
    with tmp.open("wb") as stream:
        stream.write(gzip.compress(b, compresslevel=5, mtime=0) if path.suffix == ".gz" else b)
        stream.flush()
        os.fsync(stream.fileno())
    tmp.replace(path)


def save(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False))
    tmp.replace(path)


def vec(workers, labels):
    return "|".join(f"{k}:{v}" for k, v in sorted(collections.Counter(labels[w] for w in workers).items()))


def bounded_vectors(capacities, total):
    """Enumerate all feasible class-count vectors, not concrete backgrounds."""
    items = sorted(capacities.items())
    suffix = [0] * (len(items) + 1)
    for i in range(len(items) - 1, -1, -1):
        suffix[i] = suffix[i + 1] + items[i][1]

    def rec(i, left, vals):
        if i == len(items):
            if left == 0:
                yield tuple(vals)
            return
        for v in range(max(0, left - suffix[i + 1]), min(items[i][1], left) + 1):
            yield from rec(i + 1, left - v, vals + [v])

    return [k for k, _ in items], rec(0, total, [])


def main():
    labs = pd.read_csv(LABELS, keep_default_na=False)
    labs = labs[labs.method.eq("V3_JOINT_QT") & labs.condition.eq("manual")].copy()
    assert not labs.duplicated(["heldout_building", "worker_id"]).any()
    for f in FEATURES:
        labs[f] = pd.to_numeric(labs[f], errors="coerce")
    inventory = pd.read_csv(PANELS, keep_default_na=False)
    inventory = inventory[inventory.condition.eq("manual") & inventory.source_domain.eq("new_only")]
    inventory = inventory.drop_duplicates("pool_id").sort_values("pool_id")
    write(HERE / "INPUT_MANUAL_JOINT_LABELS_LOBO.csv.gz", labs)
    write(HERE / "INPUT_NEW_ONLY_DOMAINS.csv", inventory)
    center = labs[labs.known].groupby(["heldout_building", "selected_family", "coarse_label"])[FEATURES].mean().reset_index()
    write(HERE / "TRAINING_CLASS_CENTERS.csv", center)

    all_events, all_panels, all_policies, all_capacity, background_vectors = [], [], [], [], []
    teams, domains, complete_members = {}, [], []
    folds = {k: g for k, g in labs.groupby("heldout_building")}
    for meta in inventory.to_dict("records"):
        pool, building = meta["pool_id"], meta["building"]
        fold_all = folds[building]
        fold = fold_all[fold_all.known].set_index("worker_id")
        lm = fold.coarse_label.to_dict()
        universe = sorted(set(meta["domain_workers"].split("|")) & lm.keys())
        unknown = sorted(set(meta["domain_workers"].split("|")) - lm.keys())
        U = len(universe)
        cap = collections.Counter(lm[w] for w in universe)
        qhist = {w: float(fold.loc[w, "q_history"]) for w in universe}
        thist = {w: float(fold.loc[w, "t_history"]) for w in universe}
        assert all(np.isfinite(qhist[w]) and np.isfinite(thist[w]) for w in universe)
        rankings = {weight: sorted(universe, key=lambda w: (-(qhist[w] - weight * thist[w]), h("policy_tie", w)))
                    for weight in [0, 10, 20]}
        cm = center[center.heldout_building.eq(building)].set_index("coarse_label")
        domains.append({**{k: meta[k] for k in META}, "known_U": U, "unknown_workers": "|".join(unknown),
                        "known_workers": "|".join(universe), "class_capacities": vec(universe, lm)})
        for label in sorted(cap):
            for worker in universe:
                if lm[worker] == label:
                    rr = fold.loc[worker]
                    complete_members.append({"pool_id": pool, "image": meta["image"], "building": building,
                                             "worker_id": worker, "fold_class": label, "fine_class": rr.fine_label,
                                             "known": True, "origin": rr.origin,
                                             **{f: float(rr[f]) for f in FEATURES}})

        def put_team(workers, use):
            workers = tuple(sorted(workers))
            assert len(workers) == len(set(workers))
            key = team_key(pool, workers)
            if key not in teams:
                teams[key] = {**{k: meta[k] for k in META}, "team_key": key, "n": len(workers),
                              "k": len(workers), "member_workers": "|".join(workers), "first_use": use}
            return key

        for src, dst in itertools.permutations(sorted(cap), 2):
            dc = cm.loc[dst, FEATURES] - cm.loc[src, FEATURES]
            direction = ("q_up" if dc.q_history > 0 else "q_down") + ("__faster" if dc.t_history < 0 else "__slower")
            preferred = direction == "q_up__faster"
            for m in range(2, 1 + min(cap[src] // 2, cap[dst], max(0, (U - 19) // 2))):
                for n in [19, 20, 21]:
                    if U < n + 2 * m:
                        continue
                    selected = (preferred and m <= 6) or ((not preferred) and m in (3, 4) and n == 20)
                    chosen_n = n == 20 or (preferred and m >= 3)
                    selected &= chosen_n and U >= 20 + 2 * m
                    limits = dict(cap)
                    limits[src] -= 2 * m
                    limits[dst] -= m
                    classes, vectors = bounded_vectors(limits, n - m)
                    cfgs = list(vectors)
                    cfg_id = h("capacity", pool, src, dst, n, m)[:24]
                    for values in cfgs:
                        v = "|".join(f"{k}:{val}" for k, val in zip(classes, values) if val)
                        dways = math.prod(math.comb(cap[k], val) for k, val in zip(classes, values))
                        left = dict(zip(classes, values))
                        ab = math.comb(cap[src] - left[src], m) * math.comb(cap[src] - left[src] - m, m)
                        zz = math.comb(cap[dst] - left[dst], m)
                        background_vectors.append({"capacity_id": cfg_id, "pool_id": pool, "source_class": src,
                                                   "target_class": dst, "n": n, "m": m, "background_counts": v,
                                                   "concrete_backgrounds": str(dways), "ordered_ABC_for_each_background": str(ab * zz)})
                    theory = math.comb(cap[src], m) * math.comb(cap[src] - m, m) * math.comb(cap[dst], m) * math.comb(U - 3 * m, n - m)
                    assert theory == sum(int(row["concrete_backgrounds"]) * int(row["ordered_ABC_for_each_background"])
                                         for row in background_vectors[-len(cfgs):])
                    all_capacity.append({"capacity_id": cfg_id, **{k: meta[k] for k in META}, "source_domain": "new_only_labelled",
                                         "source_class": src, "target_class": dst, "training_QT_direction": direction,
                                         "n": n, "m": m, "U": U, "source_capacity": cap[src], "target_capacity": cap[dst],
                                         "feasible_background_class_configurations": len(cfgs),
                                         "feasible_concrete_backgrounds": str(sum(math.prod(math.comb(cap[k], v) for k, v in zip(classes, values)) for values in cfgs)),
                                         "theoretical_ordered_ABC": str(theory), "theoretical_unordered_source_ABC": str(theory // 2),
                                         "selected_for_new_finite_enumeration": selected,
                                         "not_selected_reason": "" if selected else "secondary_direction_or_scale_outside_frozen_budget"})
                if not ((preferred and m <= 6) or ((not preferred) and m in (3, 4))):
                    continue
                if U < 20 + 2 * m:
                    continue
                seeds = range(4 if preferred else 1)
                suse, tuse, duse = collections.Counter(), collections.Counter(), collections.Counter()
                for seed in seeds:
                    path_id = h("reservoir", pool, src, dst, m, seed)[:24]
                    ns = [20]
                    if preferred and m >= 3 and seed < 2:
                        ns = [19, 20] + ([21] if U >= 21 + 2 * m else [])
                    nmax = max(ns)
                    tsize = min(cap[dst], m + 2, U - nmax - m)
                    assert tsize >= m
                    s_bank = sorted([w for w in universe if lm[w] == src], key=lambda w: (suse[w], h(path_id, "source", w)))[:2 * m]
                    t_bank = sorted([w for w in universe if lm[w] == dst], key=lambda w: (tuse[w], h(path_id, "target", w)))[:tsize]
                    suse.update(s_bank)
                    tuse.update(t_bank)
                    rest = sorted(set(universe) - set(s_bank) - set(t_bank), key=lambda w: (duse[w], h(path_id, "background", w)))
                    assert len(rest) >= nmax - m
                    duse.update(rest[:20 - m])
                    source_pairs = []
                    for xx in itertools.combinations(sorted(s_bank), m):
                        yy = tuple(sorted(set(s_bank) - set(xx)))
                        if xx > yy:
                            continue
                        if h("orientation", pool, src, dst, sorted(s_bank), xx) > h("orientation", pool, src, dst, sorted(s_bank), yy):
                            xx, yy = yy, xx
                        source_pairs.append((xx, yy))
                    targets = list(itertools.combinations(sorted(t_bank), m))
                    assert len(source_pairs) == math.comb(2 * m, m) // 2
                    for n in ns:
                        D = tuple(sorted(rest[:n - m]))
                        panel_id = h("panel", path_id, n)[:24]
                        bgid = h("background", pool, D)[:24]
                        cap_id = h("capacity", pool, src, dst, n, m)[:24]
                        all_panels.append({**{k: meta[k] for k in META}, "panel_id": panel_id, "member_path": path_id,
                                           "background_id": bgid, "capacity_id": cap_id, "path_seed": seed,
                                           "source_class": src, "target_class": dst, "training_QT_direction": direction,
                                           "n": n, "m": m, "background_workers": "|".join(D), "background_counts": vec(D, lm),
                                           "source_reservoir": "|".join(sorted(s_bank)), "target_reservoir": "|".join(sorted(t_bank)),
                                           "source_reservoir_n": len(s_bank), "target_reservoir_n": len(t_bank),
                                           "source_unordered_partitions": len(source_pairs), "target_subsets": len(targets),
                                           "registered_ABC": len(source_pairs) * len(targets),
                                           "exhaustive_within_registered_reservoir": True, "exhaustive_full_pool": False})
                        for X, Y in source_pairs:
                            assert not (set(D) & (set(X) | set(Y))) and not (set(X) & set(Y))
                            A, B = tuple(sorted(D + X)), tuple(sorted(D + Y))
                            kA, kB = put_team(A, "ABC_source"), put_team(B, "ABC_source")
                            partition = h("partition", pool, D, sorted([X, Y]))[:24]
                            for Z in targets:
                                assert not (set(Z) & (set(D) | set(X) | set(Y)))
                                C = tuple(sorted(D + Z))
                                kC = put_team(C, "ABC_target")
                                physical = digest(sorted([kA, kB, kC]))[:24]
                                eid = h("event", kA, kB, kC)[:24]
                                all_events.append({**{k: meta[k] for k in META}, "event_id": eid, "physical_triple_id": physical,
                                                   "oriented_triple_id": digest([kA, kB, kC])[:24], "method_id": "V3_JOINT_QT",
                                                   "tier": "coarse", "source_domain": "new_only_labelled", "stage": "closure_finite_reservoir",
                                                   "panel_id": panel_id, "member_path": path_id, "background_id": bgid, "path_seed": seed,
                                                   "capacity_id": cap_id, "source_partition_id": partition, "source_class": src, "target_class": dst,
                                                   "training_QT_direction": direction, "n": n, "m_AB": m, "m_AC": m, "m_BC": m,
                                                   "team_A": kA, "team_B": kB, "team_C": kC,
                                                   "A_member_workers": "|".join(A), "B_member_workers": "|".join(B), "C_member_workers": "|".join(C),
                                                   "common_background": "|".join(D), "outgoing_block_X": "|".join(X),
                                                   "same_count_block_Y": "|".join(Y), "changed_count_block_Z": "|".join(Z),
                                                   "A_counts": vec(A, lm), "B_counts": vec(B, lm), "C_counts": vec(C, lm),
                                                   "composition_turnover_AC": m, "label_scope": "target_building_excluded",
                                                   "selected_family": str(fold.selected_family.iloc[0]), "coarse_k": int(fold.coarse_k.iloc[0]),
                                                   "event_mode": "pure_same_background", "design_scope": "whole_class_block",
                                                   "eligible_U": U, "selection_uses_target_endpoints": False,
                                                   **{"class_center_delta_" + f: float(dc[f]) for f in FEATURES}})
                        if preferred and n == 20 and m >= 3:
                            # Every source endpoint acts once as the same baseline A;
                            # this includes both halves, not only its arbitrary ABC role.
                            for X in itertools.combinations(sorted(s_bank), m):
                                A = tuple(sorted(D + X))
                                kA = put_team(A, "policy_anchor")
                                available = sorted(set(universe) - set(A))
                                avset = set(available)
                                for policy, weight, constrained in [("class_QT_10", 10, True), ("continuous_Q_0", 0, False),
                                                                      ("continuous_QT_10", 10, False), ("continuous_QT_20", 20, False)]:
                                    choice = [w for w in rankings[weight] if w in avset and ((not constrained) or lm[w] == dst)]
                                    assert len(choice) >= m
                                    R = tuple(sorted(choice[:m]))
                                    P = tuple(sorted(D + R))
                                    kP = put_team(P, policy)
                                    seats = collections.Counter(lm[w] for w in R)
                                    seats.subtract(collections.Counter(lm[w] for w in X))
                                    all_policies.append({**{k: meta[k] for k in META}, "panel_id": panel_id, "member_path": path_id,
                                                         "background_id": bgid, "policy_id": h("policy", panel_id, kA, policy)[:24],
                                                         "policy": policy, "lambda_logtime": weight, "class_constrained": constrained,
                                                         "source_class": src, "target_class": dst, "n": n, "m": m,
                                                         "training_QT_direction": direction, "team_A": kA, "team_P": kP,
                                                         "A_member_workers": "|".join(A), "P_member_workers": "|".join(P),
                                                         "common_background": "|".join(D), "outgoing_block_X": "|".join(X),
                                                         "replacement_block": "|".join(R), "available_choice_workers": "|".join(available),
                                                         "A_counts": vec(A, lm), "P_counts": vec(P, lm),
                                                         "composition_turnover": sum(abs(v) for v in seats.values()) // 2,
                                                         "historical_block_Q": float(np.mean([qhist[w] for w in R])),
                                                         "historical_block_logT": float(np.mean([thist[w] for w in R])),
                                                         "selection_uses_target_endpoints": False})
        # Save each pool independently as soon as its registration is complete.
        pool_events = pd.DataFrame([x for x in all_events if x["pool_id"] == pool])
        if len(pool_events):
            write(HERE / "registration_batches" / (h("pool", pool)[:20] + ".csv.gz"), pool_events)
        print(pool, "registered", len(pool_events), "unique_total_teams", len(teams), flush=True)

    E = pd.DataFrame(all_events)
    links = E[["event_id", "panel_id", "capacity_id", "background_id"]].drop_duplicates()
    # Distinct physical ABCs have one orientation and are delivered once.  Panel
    # links preserve every finite enumeration slot for exact recovery/coverage.
    assert E.groupby("physical_triple_id").event_id.nunique().max() == 1
    E = E.drop_duplicates("event_id").sort_values(["pool_id", "n", "m_AB", "event_id"])
    P = pd.DataFrame(all_panels)
    Q = pd.DataFrame(all_policies).drop_duplicates("policy_id")
    T = pd.DataFrame(teams.values()).sort_values("team_key")
    C = pd.DataFrame(all_capacity)
    actual = links.merge(E[["event_id", "team_A", "team_B", "team_C"]], on="event_id", validate="many_to_one")
    stat = actual.groupby("capacity_id").agg(registered_physical_ABC=("event_id", "nunique"),
                                            registered_backgrounds=("background_id", "nunique"),
                                            registered_panels=("panel_id", "nunique")).reset_index()
    C = C.merge(stat, on="capacity_id", how="left").fillna({"registered_physical_ABC": 0, "registered_backgrounds": 0, "registered_panels": 0})
    bgstat = P.groupby("capacity_id").background_counts.nunique().rename("registered_background_class_configurations").reset_index()
    C = C.merge(bgstat, on="capacity_id", how="left").fillna({"registered_background_class_configurations": 0})
    C["uncovered_unordered_source_ABC"] = [str(int(a) - int(b)) for a, b in zip(C.theoretical_unordered_source_ABC, C.registered_physical_ABC)]
    C["uncovered_concrete_backgrounds"] = [str(int(a) - int(b)) for a, b in zip(C.feasible_concrete_backgrounds, C.registered_backgrounds)]
    for name, table in [("DOMAINS.csv", pd.DataFrame(domains)), ("ACTUAL_MEMBER_LABELS.csv.gz", pd.DataFrame(complete_members)),
                        ("CAPACITY_ALL_N_M.csv.gz", C), ("FEASIBLE_BACKGROUND_CLASS_CONFIGURATIONS.csv.gz", pd.DataFrame(background_vectors)),
                        ("BACKGROUND_PANELS.csv.gz", P), ("EVENT_PANEL_LINKS.csv.gz", links), ("EVENTS_REGISTERED.csv.gz", E),
                        ("POLICIES_REGISTERED.csv.gz", Q), ("TEAM_REQUEST.csv.gz", T)]:
        write(HERE / name, table)
    summary = E.groupby(["training_QT_direction", "n", "m_AB"]).agg(events=("event_id", "size"),
                images=("pool_id", "nunique"), buildings=("building", "nunique"), backgrounds=("background_id", "nunique"),
                A_endpoints=("team_A", "nunique"), B_endpoints=("team_B", "nunique"), C_endpoints=("team_C", "nunique")).reset_index()
    write(HERE / "REGISTRATION_SUMMARY.csv", summary)
    receipt = {"study": SEED, "underlying_data_version": "v2", "frozen_before_new_target_endpoint_reads": True,
               "target_outcomes_used_for_registration": False, "native_fusion_calls": 0,
               "events": len(E), "physical_triples": E.physical_triple_id.nunique(), "finite_panels": len(P),
               "unique_teams": len(T), "policy_rows": len(Q), "images": E.pool_id.nunique(), "buildings": E.building.nunique(),
               "labels_source": str(LABELS.relative_to(ROOT)), "labels_sha256": sha(LABELS), "inventory_sha256": sha(PANELS),
               "events_sha256": sha(HERE / "EVENTS_REGISTERED.csv.gz"), "request_sha256": sha(HERE / "TEAM_REQUEST.csv.gz"),
               "source_partitions_exhaustive_within_2m_reservoir": True, "target_subsets_exhaustive_within_registered_reservoir": True,
               "full_pool_member_combinations_exhaustive": False, "all_unordered_source_partitions_oriented_once": True,
               "primary_n": 20, "primary_direction": "q_up__faster", "preferred_background_paths": 4,
               "adjacent_n_paths": 2, "control_directions": "all feasible q_down__faster/q_down__slower/q_up__slower at n20 m3/4",
               "continuous_policies": ["class_QT_10", "continuous_Q_0", "continuous_QT_10", "continuous_QT_20"],
               "continuous_policy_support": "preferred direction n20 m>=3; identical A,D,m and available worker universe",
               "missing_class_or_history_is_zero": False, "internal_validation_only": True}
    save(HERE / "DESIGN_FREEZE.json", receipt)
    print(json.dumps(receipt, ensure_ascii=False, indent=2), flush=True)
    print(summary.to_string(index=False), flush=True)


if __name__ == "__main__":
    main()
