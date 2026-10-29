"""Audit all legal v2.1 pools, exact class capacity, and executed ABC/AC.

No classification, target filtering, scoring, or fusion is changed. Unknown
history can remain in D; only X/Y/Z need known classes, as in the source design.
"""
from __future__ import annotations
import argparse, collections, itertools, json
from pathlib import Path
import numpy as np
import pandas as pd


def read(path, **kwargs):
    return pd.read_csv(path, low_memory=False, **kwargs)


def blocks(s):
    if pd.isna(s) or s == "":
        return []
    if str(s).startswith("["):
        return json.loads(s)
    return str(s).split("|")


def known_class(row):
    return (str(row.get("known", True)).lower() in ("true", "1", "1.0")
            and pd.notna(row.get("class_id"))
            and str(row.get("class_id")) not in ("", "unknown", "nan", "None"))


def write(df, path):
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(path, index=False, encoding="utf-8-sig")


def image_stats(g, metric):
    v = g.dropna(subset=[metric])
    p = v.groupby(["building", "image", "pool_id"], dropna=False)[metric].mean()
    im = p.groupby(level=["building", "image"]).mean()
    b = im.groupby(level="building").mean()
    return dict(valid_events=len(v), valid_pools=len(p), valid_images=len(im),
                valid_buildings=len(b), mean_image=im.mean(), mean_building=b.mean(),
                median_image=im.median(), p10_image=im.quantile(.1), p90_image=im.quantile(.9),
                positive_images=int((im > 1e-9).sum()), negative_images=int((im < -1e-9).sum()),
                numerical_zero_images=int((im.abs() <= 1e-9).sum()),
                above_0p5_images=int((im > .5).sum()), below_minus0p5_images=int((im < -.5).sum()),
                within_pm0p5_images=int((im.abs() <= .5).sum()))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--extra-labels", type=Path, action="append", default=[])
    ap.add_argument("--capacity-only", action="store_true")
    args = ap.parse_args()
    base = args.repo / "research/workers/personnel_v21_reselection_20261029"
    out = args.out
    out.mkdir(parents=True, exist_ok=True)
    paths = [args.repo / "research/data/releases/v2.1/pools/INPUT_SNAPSHOT.json",
             args.repo / "research/data/releases/v2.1/admitted_space_extension/pools/INPUT_SNAPSHOT.json"]
    pools = [p for path in paths for p in json.loads(path.read_text(encoding="utf-8-sig"))["images"]]
    assert len({p["pool_id"] for p in pools}) == len(pools)
    labels = pd.concat([read(base / "classification/MAIN45_LABELS_ALL_LOBO.csv.gz")]
                       + [read(x) for x in args.extra_labels], ignore_index=True)
    labels = labels[labels.heldout_building != "ALL"]
    assert not labels.duplicated(["method", "heldout_building", "worker_id"]).any()
    lm = {(meth, b): {r["worker_id"]: str(r["class_id"]) for r in g.to_dict("records") if known_class(r)}
          for (meth, b), g in labels.groupby(["method", "heldout_building"])}
    methods = sorted(labels.method.unique())
    rows, dirs = [], []
    for p in pools:
        meta = p["meta"]
        if meta["condition"] != "manual":
            continue
        ws = {r["worker_id"] for r in p["records"]}
        assert len(ws) == len(p["records"])
        for method in methods:
            lookup = lm.get((method, meta["building"]), {})
            cc = collections.Counter(lookup.get(w, "unknown") for w in ws)
            known = {k: v for k, v in cc.items() if k != "unknown"}
            all_max = max([min(s // 2, t) for sc, s in known.items() for tc, t in known.items() if sc != tc] or [0])
            direct_max = max([min(s, t) for sc, s in known.items() for tc, t in known.items() if sc != tc] or [0])
            row = dict(pool_id=p["pool_id"], image=meta["image"], building=meta["building"],
                       layer=meta["layer"], scope="other" if meta.get("analysis_scope") == "other_admitted_target" else "primary",
                       condition="manual", difficulty=meta.get("difficulty"), method=method,
                       pool_n=len(ws), labelled_n=sum(known.values()), unknown_n=cc.get("unknown", 0),
                       n_classes_in_pool=len(known), class_capacities=json.dumps(cc, sort_keys=True),
                       class_max_m_ABC=all_max, actual_max_m_ABC=min(all_max, len(ws)//3),
                       class_max_m_AC=direct_max, actual_max_m_AC=min(direct_max, len(ws)//2))
            rows.append(row)
            for sc, tc in itertools.permutations(sorted(known), 2):
                dirs.append(dict(row, source_class=sc, target_class=tc,
                                 source_capacity=known[sc], target_capacity=known[tc],
                                 max_m_ABC=min(known[sc]//2, known[tc], len(ws)//3),
                                 max_m_AC=min(known[sc], known[tc], len(ws)//2)))
    cap = pd.DataFrame(rows)
    directions = pd.DataFrame(dirs)
    write(cap, out / "ALL_MANUAL_POOL_METHOD_CAPACITY.csv.gz")
    write(directions, out / "ALL_MANUAL_DIRECTED_CAPACITY.csv.gz")
    print("capacity", len(cap), "rows", len(directions), "directions", flush=True)
    if args.capacity_only:
        counts=[]
        for (method,scope,layer),g in cap.groupby(['method','scope','layer']):
            for n,m in [(10,7),(12,7),(14,7),(18,7),(20,7),(12,8),(14,8),(16,8),(18,8),(20,8),(12,4)]:
                total=g.pool_n.ge(n+2*m)
                hist=g.labelled_n.ge(3*m)
                fits=total & g.class_max_m_ABC.ge(m)
                counts.append(dict(method=method,scope=scope,layer=layer,n=n,m=m,
                                   legal_pools=len(g),legal_images=g.image.nunique(),
                                   total_n_sufficient_pools=int(total.sum()),
                                   historical_3m_sufficient_pools=int((total&hist).sum()),
                                   class_feasible_pools=int(fits.sum()),class_feasible_images=g.loc[fits,'image'].nunique(),
                                   class_feasible_buildings=g.loc[fits,'building'].nunique()))
        write(pd.DataFrame(counts),out/'KEY_N_M_CAPACITY_ALL_CANDIDATES.csv')
        return

    # Use exact registrations from each research stage, rather than treating an
    # outcome summary as proof of which members or pools were actually run.
    designs = [("global_screen", base / "additional_delivery/packages/05A/experiment/global_screen_design/EVENTS_EXACT.csv.gz")]
    designs += [(p.parent.name.removesuffix("_design"), p) for p in sorted((base / "experiment").glob("*_design/EVENTS_EXACT.csv.gz"))]
    wanted = {"event_id", "pool_id", "image", "building", "heldout_building", "method", "condition", "layer", "scope", "n", "m",
              "source_class", "target_class", "D", "X", "Y", "Z", "role_direction", "source_rank", "target_rank", "role_axis",
              "A_team_key", "B_team_key", "C_team_key", "A_members", "B_members", "C_members"}
    event_parts = []
    for stage, path in designs:
        if not path.exists():
            continue
        e = read(path, usecols=lambda c: c in wanted)
        e["stage"] = stage
        e["source_design"] = str(path.relative_to(args.repo))
        event_parts.append(e)
    events = pd.concat(event_parts, ignore_index=True)
    events = events[events.method.isin(methods) & events.condition.eq("manual")].copy()
    # Source copies sometimes repeat the same event across stages; one identity
    # retains all stage names. This does not erase different member/backgrounds.
    identity = ["method", "pool_id", "n", "m", "A_team_key", "B_team_key", "C_team_key"]
    events["stages"] = events.groupby(identity, dropna=False)["stage"].transform(lambda x: "|".join(sorted(set(x))))
    events = events.drop_duplicates(identity).copy()
    pool_lookup = {p["pool_id"]: p for p in pools}
    events["layer"] = events.pool_id.map(lambda pid: pool_lookup[pid]["meta"]["layer"])
    events["scope"] = events.pool_id.map(lambda pid: "other" if pool_lookup[pid]["meta"].get("analysis_scope") == "other_admitted_target" else "primary")
    events["design"] = np.where(events.B_team_key.notna(), "ABC", "AC")
    failures = []
    for r in events.to_dict("records"):
        d, x, y, z = [set(blocks(r.get(col))) for col in ["D", "X", "Y", "Z"]]
        bb = [d, x, z] if r["design"] == "AC" else [d, x, y, z]
        okay = all(not a & b for i, a in enumerate(bb) for b in bb[i+1:])
        okay &= len(d) == r["n"] - r["m"] and len(x) == len(z) == r["m"]
        if r["design"] == "ABC":
            okay &= len(y) == r["m"]
        if not okay:
            failures.append({"event_id": r["event_id"], "issue": "block_cardinality_or_disjointness"})
        l = lm.get((r["method"], r["building"]), {})
        if not all(l.get(w) == str(r["source_class"]) for w in x | y) or not all(l.get(w) == str(r["target_class"]) for w in z):
            failures.append({"event_id": r["event_id"], "issue": "source_or_target_label"})
    write(pd.DataFrame(failures, columns=["event_id", "issue"]), out / "IDENTITY_CHECK_FAILURES.csv")

    scalar_paths = [base / "additional_delivery/packages/05A/experiment/global_screen_endpoints/ENDPOINT_SCALARS.csv.gz"]
    scalar_paths += sorted((base / "experiment").glob("*_endpoints/ENDPOINT_SCALARS.csv.gz"))
    parts = [read(p, usecols=lambda c: c in {"team_key", "B8L2"}).assign(source_scalar=str(p.relative_to(args.repo)))
             for p in scalar_paths if p.exists()]
    scalars = pd.concat(parts, ignore_index=True)
    variation = scalars.groupby("team_key").B8L2.agg(["min", "max"])
    assert not ((variation["max"] - variation["min"]).abs() > 1e-8).any()
    scalars = scalars.drop_duplicates("team_key").set_index("team_key")
    for arm in "ABC":
        events[f"{arm}_executed"] = events[f"{arm}_team_key"].isin(scalars.index)
        events[f"{arm}_Q"] = events[f"{arm}_team_key"].map(scalars.B8L2)
    events["executed"] = events.A_executed & events.C_executed & (events.B_executed | events.design.eq("AC"))
    q3 = events[["A_Q", "B_Q", "C_Q"]].notna().all(axis=1)
    events["Q_CA"] = events.C_Q - events.A_Q
    events["Q_CB"] = events.C_Q - events.B_Q
    events["Q_within"] = (events.B_Q - events.A_Q).abs().where(q3)
    events["Q_cross"] = ((events.C_Q - events.A_Q).abs() + (events.C_Q - events.B_Q).abs()).div(2).where(q3)
    events["Q_gap"] = events.Q_cross - events.Q_within
    roles = read(base / "classification/CLASS_ROLES_COMPACT_ALL_LOBO.csv.gz")
    available_axes = [c for c in ["challenge_turn_rank_asc", "q_rank_asc", "size_rank_desc", "hard_turn_rank_asc"] if c in roles]
    role_map = roles.drop_duplicates(["method", "heldout_building", "class_id"]).set_index(["method", "heldout_building", "class_id"])
    def role_name(r):
        axis = "challenge_turn_rank_asc" if "STRUCT" in r.method else ("q_rank_asc" if "JOINT" in r.method else "size_rank_desc")
        sr = role_map.loc[(r.method, r.building, r.source_class)] if (r.method, r.building, r.source_class) in role_map.index else None
        tr = role_map.loc[(r.method, r.building, r.target_class)] if (r.method, r.building, r.target_class) in role_map.index else None
        if sr is None or tr is None or axis not in available_axes or pd.isna(sr.get(axis)) or pd.isna(tr.get(axis)):
            return "unresolved_roles"
        return f"{axis}:{int(sr[axis])}/{int(sr['k'])}->{int(tr[axis])}/{int(tr['k'])}"
    events["audit_role_direction"] = [role_name(r) for r in events.itertuples()]
    write(events, out / "ALL_EXECUTED_EVENTS_Q_AND_IDENTITIES.csv.gz")
    print("events", len(events), "identity issues", len(failures), "scalar teams", len(scalars), flush=True)

    # Enumerate every n for m7/m8, every half/above-half point, and every n>=20.
    # The total-pool denominator is fixed; stage-specific coverage is separate.
    Nmax = int(cap.pool_n.max())
    grid = sorted({(n, m) for n in range(3, Nmax+1) for m in range(1, n+1)
                   if n+2*m <= Nmax and (m in (7, 8) or 2*m >= n or n >= 20)})
    abc = events[events.design.eq("ABC")]
    grouped = {(meth, scope, layer, int(n), int(m)): g for (meth, scope, layer, n, m), g
               in abc.groupby(["method", "scope", "layer", "n", "m"], dropna=False)}
    funnel, detailed = [], []
    for (meth, scope, layer), c in cap.groupby(["method", "scope", "layer"], dropna=False):
        for n, m in grid:
            total_ok = c.pool_n >= n+2*m
            hist_ok = c.labelled_n >= 3*m
            class_ok = c.class_max_m_ABC >= m
            feasible = total_ok & class_ok
            g = grouped.get((meth, scope, layer, n, m), pd.DataFrame())
            reg_pools = set(g.pool_id) if len(g) else set()
            ex_pools = set(g.loc[g.executed, "pool_id"]) if len(g) else set()
            validcb = set(g.loc[g.Q_CB.notna(), "pool_id"]) if len(g) else set()
            validgap = set(g.loc[g.Q_gap.notna(), "pool_id"]) if len(g) else set()
            r = dict(method=meth, scope=scope, layer=layer, n=n, m=m,
                     replacement_fraction=m/n, band="exact_half" if 2*m==n else "above_half" if 2*m>n else "below_half",
                     legal_pools=len(c), legal_images=c.image.nunique(), legal_buildings=c.building.nunique(),
                     total_n_sufficient_pools=int(total_ok.sum()),
                     history_3m_sufficient_pools=int((total_ok & hist_ok).sum()),
                     class_feasible_pools=int(feasible.sum()), class_feasible_images=c.loc[feasible, "image"].nunique(),
                     class_feasible_buildings=c.loc[feasible, "building"].nunique(),
                     total_n_insufficient_pools=int((~total_ok).sum()),
                     history_insufficient_after_n_pools=int((total_ok & ~hist_ok).sum()),
                     class_distribution_insufficient_after_history_pools=int((total_ok & hist_ok & ~class_ok).sum()),
                     registered_pools=len(reg_pools), executed_pools=len(ex_pools), Q_CB_evaluable_pools=len(validcb),
                     Q_gap_evaluable_pools=len(validgap), feasible_not_registered_pools=int((feasible & ~c.pool_id.isin(reg_pools)).sum()),
                     registered_events=len(g), executed_events=int(g.executed.sum()) if len(g) else 0,
                     Q_CB_evaluable_events=int(g.Q_CB.notna().sum()) if len(g) else 0,
                     Q_gap_evaluable_events=int(g.Q_gap.notna().sum()) if len(g) else 0)
            funnel.append(r)
            if m in (7, 8) and n in (8, 10, 12, 14, 16, 18, 20, 21):
                for cr, enough_n, enough_hist, enough_class in zip(c.to_dict("records"), total_ok, hist_ok, class_ok):
                    pid = cr["pool_id"]
                    reason = ("total_pool_n_insufficient" if not enough_n else "historical_labels_below_3m" if not enough_hist
                              else "class_distribution_insufficient" if not enough_class else "not_registered" if pid not in reg_pools
                              else "registered_not_executed" if pid not in ex_pools else "Q_CB_not_evaluable" if pid not in validcb else "Q_CB_evaluable")
                    detailed.append(dict(cr, n=n, m=m, reason=reason, registered=pid in reg_pools,
                                         executed=pid in ex_pools, Q_CB_evaluable=pid in validcb, Q_gap_evaluable=pid in validgap))
    write(pd.DataFrame(funnel), out / "ABC_ALL_RELEVANT_N_M_FUNNEL.csv")
    write(pd.DataFrame(detailed), out / "M7_M8_POOL_LEVEL_FUNNEL.csv.gz")
    sums = []
    keys = ["method", "scope", "layer", "design", "audit_role_direction", "n", "m"]
    for k, g in events.groupby(keys, dropna=False):
        row = dict(zip(keys, k))
        row.update(registered_events=len(g), registered_pools=g.pool_id.nunique(), registered_images=g.image.nunique(), registered_buildings=g.building.nunique(),
                   executed_events=int(g.executed.sum()), stages="|".join(sorted(set("|".join(g.stages).split("|")))))
        for metric in ["Q_CA", "Q_CB", "Q_within", "Q_cross", "Q_gap"]:
            row.update({f"{metric}_{s}": v for s, v in image_stats(g, metric).items()})
        sums.append(row)
    write(pd.DataFrame(sums), out / "ALL_N_M_DIRECTION_Q_RESULTS.csv.gz")
    receipt = dict(pools=len(pools), manual_pools=cap.pool_id.nunique(), methods=len(methods),
                   capacity_rows=len(cap), unique_registered_events=len(events),
                   identity_check_failures=len(failures), executed_events=int(events.executed.sum()),
                   maximum_manual_pool_n=Nmax, grid_cells=grid,
                   unknown_history_policy="Unknown workers may remain in D. Source X/Y and target Z must have known LOBO classes.",
                   funnel_reason_policy="First failure: total N; then known labels <3m; then class distribution; not registered; not executed; Q missing. Separate raw counts retained.",
                   effect_aggregation="Events within pool; pools within image; image equal; building equal separately. Directions never averaged together for signed effects.",
                   practical_Q_near_zero_band=0.5, numerical_zero_tolerance=1e-9,
                   sources=[str(p.relative_to(args.repo)) for p in paths] + [str(p.relative_to(args.repo)) for _,p in designs if p.exists()]
                   + [str(p.relative_to(args.repo)) for p in scalar_paths if p.exists()])
    (out / "CAPACITY_AUDIT_RECEIPT.json").write_text(json.dumps(receipt, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({k:v for k,v in receipt.items() if k not in {"sources", "grid_cells"}}, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()
