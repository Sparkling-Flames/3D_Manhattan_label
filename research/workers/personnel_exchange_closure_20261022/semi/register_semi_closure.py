"""Outcome-free Semi joint-class block exchange registration.

Uses inherited outside-building labels.  Small complete ABC cells are enumerated;
larger cells use a recorded finite member/background subspace, with every source
partition inside that subspace retained.  No fusion or target-outcome reads.
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
OLD = ROOT / "research/workers/personnel_effective_exchange_conditions_20261022/joint_exchange"
SEED = "semi-closure-v2-data-20261022-source-partitions-v1"
FEATURES = ["q_history", "q_downside", "t_history", "turn_history", "short_history",
            "redundancy_history", "area_history", "height_history", "simple_turn_history",
            "complex_turn_history", "complex_short_history"]
MAX_COMPLETE_ORDERED_ABC = 1000
MIN_RESERVOIRS = 2
BACKGROUND_PATHS = 3
M_CANDIDATES = [3, 4, 5, 6]
N_ANCHORS = [10, 12, 14, 16]


def digest(x):
    return hashlib.sha256(json.dumps(x, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def h(*x):
    return digest([SEED, *x])


def team_key(pool, workers):
    return pool + "__" + digest(sorted(workers))[:20]


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(path, df):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    data = df.to_csv(index=False).encode("utf-8-sig")
    with tmp.open("wb") as f:
        f.write(gzip.compress(data, compresslevel=5, mtime=0) if path.suffix == ".gz" else data)
        f.flush()
        os.fsync(f.fileno())
    tmp.replace(path)


def save(path, obj):
    path = Path(path)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(json.dumps(obj, ensure_ascii=False, indent=2, sort_keys=True, allow_nan=False))
    tmp.replace(path)


def join(workers):
    return "|".join(sorted(workers))


def counts(workers, labels):
    return collections.Counter(labels[w] for w in workers)


def vector(workers, labels):
    return "|".join(f"{k}:{v}" for k, v in sorted(counts(workers, labels).items()))


def count_vectors(cap, total):
    keys = list(cap)

    def walk(i, remaining, v):
        if i == len(keys):
            if remaining == 0:
                yield dict(v)
            return
        key = keys[i]
        for k in range(min(cap[key], remaining) + 1):
            v[key] = k
            yield from walk(i + 1, remaining - k, v)

    yield from walk(0, total, {})


def capacity_details(cap, src, dst, n, m):
    residual = dict(cap)
    residual[src] -= 2 * m
    residual[dst] -= m
    configs = list(count_vectors(residual, n - m))
    background_sets = sum(math.prod(math.comb(cap[k], v[k]) for k in cap) for v in configs)
    # Exact set count across all feasible A/B/C endpoints in this cell.
    endpoint_sets = source_sets = target_sets = 0
    for v in count_vectors(cap, n):
        source_ok = v[src] >= m and cap[src] - v[src] >= m and cap[dst] - v[dst] >= m
        target_ok = v[dst] >= m and cap[src] - v[src] >= 2 * m
        weight = math.prod(math.comb(cap[k], v[k]) for k in cap)
        source_sets += weight * source_ok
        target_sets += weight * target_ok
        endpoint_sets += weight * (source_ok or target_ok)
    return dict(feasible_class_count_configs=len(configs),
                feasible_distinct_background_sets=str(background_sets),
                feasible_unique_endpoint_sets=str(endpoint_sets),
                feasible_source_endpoint_sets=str(source_sets),
                feasible_target_endpoint_sets=str(target_sets))


def sampled_reservoirs(source, target, m, sid):
    """Cyclic balanced covers, then fully partition each selected source union."""
    sw = sorted(source, key=lambda w: h(sid, "source_order", w))
    tw = sorted(target, key=lambda w: h(sid, "target_order", w))
    R = max(MIN_RESERVOIRS, math.ceil(len(sw) / (2 * m)), math.ceil(len(tw) / m))
    selected = set()
    for r in range(R):
        S = tuple(sorted(sw[(r * 2 * m + j) % len(sw)] for j in range(2 * m)))
        Z = tuple(sorted(tw[(r * m + j) % len(tw)] for j in range(m)))
        selected.add((S, Z))
    return sorted(selected)


def background_sets(rest, size, rid, complete):
    possibilities = math.comb(len(rest), size)
    if complete or possibilities <= BACKGROUND_PATHS:
        return [(tuple(x), "complete_background") for x in itertools.combinations(sorted(rest), size)]
    result = {}
    for i in range(BACKGROUND_PATHS):
        ordered = sorted(rest, key=lambda w: h(rid, "background_path", i, w))
        D = tuple(sorted(ordered[:size]))
        result.setdefault(D, f"background_path_{i}")
    return sorted(result.items())


def register():
    label_path = V3 / "taxonomy/ALL_METHOD_LABELS_LOBO.csv.gz"
    panel_path = V3 / "composition/PANELS.csv"
    labels_all = pd.read_csv(label_path, keep_default_na=False)
    labels = labels_all[(labels_all.method == "V3_JOINT_QT") & (labels_all.condition == "semi")].copy()
    labels = labels[labels.known.astype(str).str.lower().eq("true") & labels.heldout_building.ne("ALL")]
    for feature in FEATURES:
        labels[feature] = pd.to_numeric(labels[feature], errors="coerce")
    panels = pd.read_csv(panel_path, keep_default_na=False)
    panels = panels[(panels.condition == "semi") & (panels.source_domain == "new_only")]
    centers = labels.groupby(["condition", "heldout_building", "selected_family", "coarse_label"])[FEATURES].mean().reset_index()
    centers["historical_members"] = labels.groupby(["condition", "heldout_building", "selected_family", "coarse_label"]).size().values
    write(HERE / "INHERITED_LABELS_LOBO.csv.gz", labels)
    write(HERE / "TRAINING_CLASS_CENTERS.csv", centers)

    events, controls, capacities, domains, reservoirs = [], [], [], [], []
    teams = {}
    lookup = {b: g.set_index("worker_id") for b, g in labels.groupby("heldout_building")}

    def add_team(meta, workers):
        key = team_key(meta["pool_id"], workers)
        record = {k: meta[k] for k in ["pool_id", "image", "building", "condition", "difficulty", "layer"]}
        record.update(team_key=key, n=len(workers), k=len(workers), member_workers=join(workers))
        teams[key] = record
        return key

    for pool, panel_group in panels.groupby("pool_id", sort=True):
        meta = panel_group.iloc[0].to_dict()
        fold = lookup[meta["building"]]
        lm = fold.coarse_label.to_dict()
        ws = sorted(set(meta["domain_workers"].split("|")) & set(lm))
        unknown = sorted(set(meta["domain_workers"].split("|")) - set(lm))
        cap = dict(sorted(counts(ws, lm).items()))
        U = len(ws)
        ctr = fold.groupby("coarse_label")[FEATURES].mean()
        q_std, t_std = fold.q_history.std(ddof=0), fold.t_history.std(ddof=0)
        utility = (fold.q_history - fold.q_history.mean()) / q_std - (fold.t_history - fold.t_history.mean()) / t_std
        domains.append(dict(pool_id=pool, image=meta["image"], building=meta["building"], condition="semi",
                            source_domain="new_only_labelled", original_U=len(meta["domain_workers"].split("|")),
                            known_U=U, workers=join(ws), unknown_workers=join(unknown), class_capacity=json.dumps(cap, sort_keys=True)))

        for src, dst in itertools.permutations(sorted(cap), 2):
            delta = ctr.loc[dst] - ctr.loc[src]
            direction = ("q_up" if delta.q_history > 0 else "q_down") + "__" + ("faster" if delta.t_history < 0 else "slower")
            for m in M_CANDIDATES:
                base = dict(pool_id=pool, image=meta["image"], building=meta["building"], condition="semi",
                            source_domain="new_only_labelled", source_class=src, target_class=dst,
                            training_QT_direction=direction, U=U, source_capacity=cap[src], target_capacity=cap[dst], m=m)
                ns = sorted({n for n in N_ANCHORS + [U - 2 * m] if n >= 10 and n + 2 * m <= U})
                feasible = cap[src] >= 2 * m and cap[dst] >= m and bool(ns)
                if direction != "q_up__faster" or not feasible:
                    reason = "outside_registered_direction" if direction != "q_up__faster" else "insufficient_class_or_total_capacity"
                    capacities.append(dict(**base, n="", status=reason, registered_oriented_ABC=0, registered_physical_ABC=0))
                    continue
                source = [w for w in ws if lm[w] == src]
                target = [w for w in ws if lm[w] == dst]
                sid = h(pool, src, dst, m)
                chosen = sampled_reservoirs(source, target, m, sid)

                for n in ns:
                    theoretical = math.comb(cap[src], m) * math.comb(cap[src] - m, m) * math.comb(cap[dst], m) * math.comb(U - 3 * m, n - m)
                    complete = theoretical <= MAX_COMPLETE_ORDERED_ABC
                    block_reservoirs = (itertools.product(itertools.combinations(source, 2 * m), itertools.combinations(target, m)) if complete else chosen)
                    cell_id = h("cell", pool, src, dst, m, n)[:24]
                    cell_events = []
                    for S, Z in block_reservoirs:
                        S, Z = tuple(sorted(S)), tuple(sorted(Z))
                        rid = h("reservoir", pool, src, dst, m, S, Z)[:24]
                        rest = sorted(set(ws) - set(S) - set(Z))
                        for D, bg_path in background_sets(rest, n - m, rid, complete):
                            bid = h("background", pool, D)[:24]
                            candidate = sorted(set(ws) - set(D) - set(S))
                            Q = tuple(sorted(sorted(candidate, key=lambda w: (-float(utility.loc[w]), h("qt_tie", w)))[:m]))
                            qt_key = add_team(meta, (*D, *Q))
                            c_key = add_team(meta, (*D, *Z))
                            control_id = h("qt_control", cell_id, D, S, Z)[:24]
                            controls.append(dict(control_id=control_id, cell_id=cell_id, pool_id=pool,
                                                 image=meta["image"], building=meta["building"], condition="semi",
                                                 source_class=src, target_class=dst, n=n, m=m,
                                                 common_background=join(D), source_union=join(S), class_target_block=join(Z),
                                                 candidate_workers=join(candidate), candidate_size=len(candidate),
                                                 feasible_candidate_blocks=math.comb(len(candidate), m),
                                                 qt_workers=join(Q), team_C=c_key, team_QT=qt_key,
                                                 C_QT_actual_m=m-len(set(Z)&set(Q)), qt_same_as_class=tuple(Z)==Q,
                                                 qt_score="z_fold_q_history_minus_z_fold_t_history", uses_target_outcomes=False))
                            reservoirs.append(dict(cell_id=cell_id, pool_id=pool, image=meta["image"], building=meta["building"],
                                                   n=n, m=m, source_class=src, target_class=dst, reservoir_id=rid,
                                                   source_union=join(S), target_block=join(Z), background_id=bid,
                                                   common_background=join(D), background_path=bg_path,
                                                   cell_complete_enumeration=complete))
                            for X in itertools.combinations(S, m):
                                X = tuple(sorted(X))
                                Y = tuple(sorted(set(S) - set(X)))
                                A, B, C = [tuple(sorted((*D, *W))) for W in (X, Y, Z)]
                                keys = [add_team(meta, w) for w in (A, B, C)]
                                assert len(set(A) & set(B)) == len(set(A) & set(C)) == len(set(B) & set(C)) == n - m
                                e = {k: meta[k] for k in ["pool_id", "image", "building", "condition", "layer", "difficulty"]}
                                e.update(method_id="V3_JOINT_QT", tier="coarse", stage="semi_closure_source_partition_expansion",
                                         source_domain="new_only_labelled", n=n, m_AB=m, m_AC=m, m_BC=m,
                                         event_id=h("event", keys)[:24], physical_triple_id=digest(sorted(keys))[:24],
                                         oriented_triple_id=digest(keys)[:24], team_A=keys[0], team_B=keys[1], team_C=keys[2],
                                         A_member_workers=join(A), B_member_workers=join(B), C_member_workers=join(C),
                                         common_background=join(D), outgoing_block_X=join(X), same_count_block_Y=join(Y), changed_count_block_Z=join(Z),
                                         A_counts=vector(A,lm), B_counts=vector(B,lm), C_counts=vector(C,lm), composition_turnover_AC=m,
                                         label_scope="target_building_excluded", selection_uses_target_endpoints=False,
                                         selected_family=str(fold.selected_family.iloc[0]), coarse_k=int(fold.coarse_k.iloc[0]),
                                         source_class=src, target_class=dst, training_QT_direction=direction,
                                         design_scope="pure_class_block_source_partition_census", event_mode="pure_same_background",
                                         eligible_U=U, cell_id=cell_id, reservoir_id=rid, background_id=bid, background_path=bg_path,
                                         cell_complete_enumeration=complete, qt_control_id=control_id, team_QT=qt_key,
                                         sampling_role="both_A_B_orientations_retained_not_independent")
                                for f, val in delta.items():
                                    e["class_center_delta_" + f] = float(val) if pd.notna(val) else None
                                events.append(e)
                                cell_events.append(e)
                    ce = pd.DataFrame(cell_events).drop_duplicates("oriented_triple_id")
                    team_set = set(ce.team_A) | set(ce.team_B) | set(ce.team_C)
                    capacity = dict(**base, n=n, cell_id=cell_id, status="complete_cell" if complete else "complete_registered_subspace",
                                    theoretical_ordered_ABC=str(theoretical), theoretical_physical_ABC=str(theoretical//2),
                                    full_cell_enumeration=complete, registered_oriented_ABC=len(ce),
                                    registered_physical_ABC=ce.physical_triple_id.nunique(), registered_unique_endpoints=len(team_set),
                                    registered_background_sets=ce.common_background.nunique(),
                                    registered_source_unions=ce.reservoir_id.nunique(),
                                    registered_source_blocks=len(set(ce.outgoing_block_X)|set(ce.same_count_block_Y)),
                                    registered_target_blocks=ce.changed_count_block_Z.nunique(),
                                    registered_class_count_configs=ce[["A_counts","C_counts"]].drop_duplicates().shape[0],
                                    backgrounds_per_fixed_blocks=str(math.comb(U-3*m,n-m)),
                                    unregistered_ordered_ABC=str(theoretical-len(ce)),
                                    member_space_exhaustive=complete)
                    capacity.update(capacity_details(cap, src, dst, n, m))
                    capacities.append(capacity)

    E = pd.DataFrame(events).drop_duplicates("oriented_triple_id").sort_values(["pool_id","m_AB","n","source_class","target_class","event_id"])
    T = pd.DataFrame(teams.values()).sort_values("team_key")
    C = pd.DataFrame(controls).drop_duplicates("control_id")
    R = pd.DataFrame(reservoirs).drop_duplicates(["cell_id","reservoir_id","background_id"])
    known = set()
    cache_files = [OLD / "ALL_USED_ENDPOINT_SCALARS.csv.gz", V3 / "composition/delivery/ENDPOINT_KEY_INDEX.csv.gz"]
    cache_sources = []
    for path in cache_files:
        if path.exists():
            keys = pd.read_csv(path, usecols=["team_key"]).team_key
            known.update(keys)
            cache_sources.append(dict(file=str(path.relative_to(ROOT)), sha256=sha(path), keys=len(keys)))
    T["cached"] = T.team_key.isin(known)
    Q = T[~T.cached]
    for name, df in [("EVENTS_REGISTERED.csv.gz", E), ("TEAM_REQUEST.csv.gz", Q), ("ALL_TEAMS.csv.gz", T),
                     ("CONTINUOUS_QT_CONTROLS.csv.gz", C), ("REGISTERED_SUBSPACES.csv.gz", R),
                     ("CAPACITY_ALL_ATTEMPTS.csv", pd.DataFrame(capacities)), ("DOMAIN_INVENTORY.csv", pd.DataFrame(domains))]:
        write(HERE / name, df)
    freeze = dict(stage="before_new_target_endpoint_evaluation", seed=SEED, underlying_data="real_v2", research_round="20261022_closure",
                  method="V3_JOINT_QT", input_condition="semi", evaluation_condition="semi", target_building_excluded=True,
                  target_endpoint_outcomes_used=False, m_candidates=M_CANDIDATES, n_anchors=N_ANCHORS,
                  include_largest_feasible_n=True, registered_training_direction="q_up__faster",
                  min_balanced_reservoirs=MIN_RESERVOIRS, background_paths=BACKGROUND_PATHS,
                  complete_ordered_ABC_limit=MAX_COMPLETE_ORDERED_ABC,
                  source_partition_scope="all ordered X/Y partitions within selected 2m source union; retain both A/B orientations",
                  orientation_warning="Both orientations are algebraic mirror records, not independent replicates. Signed B-A averages cancel by design.",
                  events=len(E), physical_triples=E.physical_triple_id.nunique(), pools=E.pool_id.nunique(), buildings=E.building.nunique(),
                  cells=E.cell_id.nunique(), unique_teams=len(T), cached_teams=int(T.cached.sum()), requested_new_endpoints=len(Q),
                  qt_control_records=len(C), qt_distinct_teams=C.team_QT.nunique(),
                  label_file=str(label_path.relative_to(ROOT)), label_sha256=sha(label_path),
                  panel_file=str(panel_path.relative_to(ROOT)), panel_sha256=sha(panel_path),
                  events_sha256=sha(HERE / "EVENTS_REGISTERED.csv.gz"), request_sha256=sha(HERE / "TEAM_REQUEST.csv.gz"),
                  cache_sources=cache_sources, all_global_member_combinations_exhaustive=False, native_calls=0)
    save(HERE / "DESIGN_FREEZE.json", freeze)
    print(json.dumps(freeze, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    register()
