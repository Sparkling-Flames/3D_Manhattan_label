"""Final coverage by distinct replacement questions; derive only, no fusion.

The mathematical universe is all n >= 3, 1 <= m <= n, with pure source and
target blocks. D may be empty. ABC requires N >= n+2m, S >= 2m, T >= m;
AC requires N >= n+m, S >= m, T >= m. Unknown history may occur in D.
Band unions count pools once; a separate cell count preserves unrun n/m and
class directions. Neither a union nor four fully covered grids implies all
legal team sizes or member combinations have been evaluated.
"""
from __future__ import annotations

from collections import defaultdict
import gzip
import json
import os
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "audit_capacity/completed_supplement"
METHODS = ["TARGET_DSTRUCT_K3", "V21_DSTRUCT_RAW3_K3", "OPPSTRUCT_K3", "OPPJOINT_K3", "OPPJOINT_K4"]
BANDS = [
    ("fixed_m7_any_n", "ABC", lambda n, m: m == 7, "m=7, any legal n"),
    ("fixed_m8_any_n", "ABC", lambda n, m: m == 8, "m=8, any legal n"),
    ("exact_half_all_m", "ABC", lambda n, m: 2*m == n, "m/n=1/2, all m"),
    ("exact_half_m_ge7", "ABC", lambda n, m: 2*m == n and m >= 7, "m/n=1/2, m>=7"),
    ("above_half_all_m", "ABC", lambda n, m: 2*m > n, "m/n>1/2, all m, including m=n"),
    ("above_half_m_ge7", "ABC", lambda n, m: 2*m > n and m >= 7, "m/n>1/2, m>=7, including m=n"),
    ("large_team_ABC_n_ge20", "ABC", lambda n, m: n >= 20, "n>=20, strict ABC"),
    ("large_team_AC_n_ge20", "AC", lambda n, m: n >= 20, "n>=20, direct AC, no B"),
]


def write_csv(frame: pd.DataFrame, path: Path) -> None:
    tmp = path.with_name(path.name + ".tmp")
    opener = gzip.open if path.suffix == ".gz" else open
    with opener(tmp, "wt", encoding="utf-8-sig", newline="") as f:
        frame.to_csv(f, index=False)
    with open(tmp, "rb") as f:
        os.fsync(f.fileno())
    tmp.replace(path)


def pairs_text(values):
    return "|".join(f"{n}/{m}" for n, m in sorted(values))


def main():
    cap = pd.read_csv(ROOT / "audit_capacity/extended_capacity/ALL_MANUAL_POOL_METHOD_CAPACITY.csv.gz")
    cap = cap[cap.method.isin(METHODS) & cap.layer.eq("ordinary_manual")].copy()
    assert cap.groupby("method").size().eq(236).all()
    assert cap.groupby(["method", "scope"]).size().to_dict() == {
        (method, scope): size for method in METHODS for scope, size in [("primary", 206), ("other", 30)]
    }
    old = pd.read_csv(ROOT / "audit_capacity/results/ALL_EXECUTED_EVENTS_Q_AND_IDENTITIES.csv.gz", low_memory=False)
    new = pd.read_csv(OUT / "NEW_EVENTS_INDEPENDENT_Q_AND_STATUS.csv.gz", low_memory=False)
    events = pd.concat([old, new], ignore_index=True)
    events = events[events.method.isin(METHODS) & events.layer.eq("ordinary_manual")].copy()
    identity = ["method", "pool_id", "n", "m", "A_team_key", "B_team_key", "C_team_key"]
    duplicate_event_identities = int(events.duplicated(identity).sum())
    events = events.drop_duplicates(identity).copy()
    assert events.executed.all()
    assert set(events.pool_id) <= set(cap.pool_id)
    grouped_events = {key: g for key, g in events.groupby(["method", "pool_id", "design"])}
    empty_events = events.iloc[:0]
    maximum_N = int(cap.pool_n.max())
    assert maximum_N == 35
    band_grids = {}
    definitions = []
    for name, design, rule, description in BANDS:
        extra = 2 if design == "ABC" else 1
        grid = {(n, m) for n in range(3, maximum_N+1) for m in range(1, n+1)
                if n+extra*m <= maximum_N and rule(n, m)}
        band_grids[name] = grid
        definitions.append(dict(band=name, design=design, description=description,
            n_global_min=min(n for n, m in grid), n_global_max=max(n for n, m in grid),
            m_global_min=min(m for n, m in grid), m_global_max=max(m for n, m in grid),
            global_n_m_grid_count=len(grid), global_n_m_grid=pairs_text(grid),
            total_N_condition=f"N>=n+{extra}m", history_condition=f"labelled>={extra+1}m",
            pure_source_condition=f"source>={extra}m", pure_target_condition="target>=m",
            n_lower_bound=3, allow_D_empty=True, same_source_X_Y=design == "ABC",
            mutually_disjoint_blocks="D,X,Y,Z" if design == "ABC" else "D,X,Z",
            unknown_history_policy="Unknown workers allowed in D only",
            primary_Q_comparison="C-B" if design == "ABC" else "C-A"))
    rows = []
    total_outside_capacity = 0
    for c in cap.to_dict("records"):
        class_counts = {str(k): int(v) for k, v in json.loads(c["class_capacities"]).items() if str(k) != "unknown"}
        for name, design, rule, description in BANDS:
            grid = band_grids[name]
            extra = 2 if design == "ABC" else 1
            class_max_m = int(c[f"class_max_m_{design}"])
            total_pairs = {(n, m) for n, m in grid if n+extra*m <= c["pool_n"]}
            historical_pairs = {(n, m) for n, m in total_pairs if (extra+1)*m <= c["labelled_n"]}
            feasible_pairs = {(n, m) for n, m in total_pairs if m <= class_max_m}
            feasible_directions = {(n, m, s, t) for n, m in feasible_pairs
                for s, sc in class_counts.items() for t, tc in class_counts.items()
                if s != t and sc >= extra*m and tc >= m}
            assert bool(feasible_pairs) == bool(feasible_directions)
            e = grouped_events.get((c["method"], c["pool_id"], design), empty_events)
            e = e[[rule(int(n), int(m)) for n, m in zip(e.n, e.m)]].copy() if len(e) else e
            rp = set(zip(e.n.astype(int), e.m.astype(int)))
            ep = set(zip(e.loc[e.executed, "n"].astype(int), e.loc[e.executed, "m"].astype(int)))
            rd = set(zip(e.n.astype(int), e.m.astype(int), e.source_class.astype(str), e.target_class.astype(str)))
            ex = e[e.executed]
            ed = set(zip(ex.n.astype(int), ex.m.astype(int), ex.source_class.astype(str), ex.target_class.astype(str)))
            qm = "Q_CB" if design == "ABC" else "Q_CA"
            q = e[e[qm].notna()]
            qp = set(zip(q.n.astype(int), q.m.astype(int)))
            qd = set(zip(q.n.astype(int), q.m.astype(int), q.source_class.astype(str), q.target_class.astype(str)))
            triple = e[e[["A_Q", "B_Q", "C_Q"]].notna().all(axis=1)] if design == "ABC" else empty_events
            tp = set(zip(triple.n.astype(int), triple.m.astype(int)))
            td = set(zip(triple.n.astype(int), triple.m.astype(int), triple.source_class.astype(str), triple.target_class.astype(str)))
            total_outside_capacity += len(rd - feasible_directions)
            assert rp <= feasible_pairs and rd <= feasible_directions
            reason = ("pool_N_insufficient" if not total_pairs else "history_insufficient_after_N" if not historical_pairs
                else "pure_class_distribution_insufficient" if not feasible_pairs else "capacity_present_not_registered" if not rp
                else "registered_not_executed" if not ep else "primary_Q_not_evaluable" if not qp else "primary_Q_evaluable")
            rows.append(dict(method=c["method"], pool_id=c["pool_id"], image=c["image"], building=c["building"],
                scope=c["scope"], pool_n=c["pool_n"], labelled_n=c["labelled_n"], unknown_n=c["unknown_n"],
                band=name, design=design, primary_Q_comparison="C-B" if design == "ABC" else "C-A",
                total_n_sufficient=bool(total_pairs), history_sufficient_after_n=bool(historical_pairs), class_feasible=bool(feasible_pairs),
                class_feasible_with_nonempty_D=any(n > m for n, m in feasible_pairs),
                registered=bool(rp), executed=bool(ep), primary_Q_evaluable=bool(qp), triple_Q_evaluable=bool(tp), first_terminal_state=reason,
                capacity_pool_n_m_cells=len(feasible_pairs), capacity_direction_n_m_cells=len(feasible_directions),
                registered_pool_n_m_cells=len(rp), registered_direction_n_m_cells=len(rd),
                executed_pool_n_m_cells=len(ep), executed_direction_n_m_cells=len(ed),
                primary_Q_pool_n_m_cells=len(qp), primary_Q_direction_n_m_cells=len(qd),
                triple_Q_pool_n_m_cells=len(tp), triple_Q_direction_n_m_cells=len(td),
                capacity_pool_n_m_cells_not_registered=len(feasible_pairs-rp),
                capacity_direction_n_m_cells_not_registered=len(feasible_directions-rd),
                registered_events=len(e), executed_events=int(e.executed.sum()), primary_Q_evaluable_events=len(q),
                triple_Q_evaluable_events=len(triple),
                capacity_n_m_values=pairs_text(feasible_pairs), registered_n_m_values=pairs_text(rp)))
    pool_result = pd.DataFrame(rows)
    # Independent closed forms for existence of ANY legal n/m in each band.
    # They deliberately say nothing about registration of every legal cell.
    minimum_conditions = {
        "fixed_m7_any_n": (21, 7, "ABC"), "fixed_m8_any_n": (24, 8, "ABC"),
        "exact_half_all_m": (8, 2, "ABC"), "exact_half_m_ge7": (28, 7, "ABC"),
        "above_half_all_m": (7, 2, "ABC"), "above_half_m_ge7": (21, 7, "ABC"),
        "large_team_ABC_n_ge20": (22, 1, "ABC"), "large_team_AC_n_ge20": (21, 1, "AC"),
    }
    cap_index = cap.set_index(["method", "pool_id"])
    for r in pool_result.itertuples():
        min_N, min_m, design = minimum_conditions[r.band]
        cr = cap_index.loc[(r.method, r.pool_id)]
        expected = cr.pool_n >= min_N and cr[f"class_max_m_{design}"] >= min_m
        assert bool(expected) == bool(r.class_feasible)
    write_csv(pool_result, OUT / "FINAL_REPLACEMENT_BAND_POOL_FUNNEL.csv.gz")
    summaries = []
    states = ["pool_N_insufficient", "history_insufficient_after_N", "pure_class_distribution_insufficient",
              "capacity_present_not_registered", "registered_not_executed", "primary_Q_not_evaluable", "primary_Q_evaluable"]
    for population, mask in [("primary_206", pool_result.scope.eq("primary")),
                             ("other_admitted_30", pool_result.scope.eq("other")),
                             ("all_ordinary_236", pool_result.scope.isin(["primary", "other"]))]:
        for (method, band, design), g in pool_result[mask].groupby(["method", "band", "design"]):
            r = dict(method=method, population=population, band=band, design=design,
                     primary_Q_comparison="C-B" if design == "ABC" else "C-A",
                     legal_pools=len(g), legal_images=g.image.nunique(), legal_buildings=g.building.nunique(),
                     pool_n_min=int(g.pool_n.min()), pool_n_max=int(g.pool_n.max()))
            for field in ["total_n_sufficient", "history_sufficient_after_n", "class_feasible", "class_feasible_with_nonempty_D",
                          "registered", "executed", "primary_Q_evaluable", "triple_Q_evaluable"]:
                subset = g[g[field]]
                r.update({field+"_pools": len(subset), field+"_images": subset.image.nunique(), field+"_buildings": subset.building.nunique()})
            for field in ["capacity_pool_n_m_cells", "capacity_direction_n_m_cells", "registered_pool_n_m_cells",
                          "registered_direction_n_m_cells", "executed_pool_n_m_cells", "executed_direction_n_m_cells",
                          "primary_Q_pool_n_m_cells", "primary_Q_direction_n_m_cells", "triple_Q_pool_n_m_cells",
                          "triple_Q_direction_n_m_cells", "capacity_pool_n_m_cells_not_registered",
                          "capacity_direction_n_m_cells_not_registered", "registered_events", "executed_events",
                          "primary_Q_evaluable_events", "triple_Q_evaluable_events"]:
                r[field] = int(g[field].sum())
            for state in states:
                r[state+"_pools"] = int(g.first_terminal_state.eq(state).sum())
            r["capacity_present_no_event_in_band_pools"] = int((g.class_feasible & ~g.registered).sum())
            r["some_capacity_n_m_cells_not_registered_pools"] = int(g.capacity_pool_n_m_cells_not_registered.gt(0).sum())
            r["some_capacity_directions_not_registered_pools"] = int(g.capacity_direction_n_m_cells_not_registered.gt(0).sum())
            for field in ["capacity_n_m_values", "registered_n_m_values"]:
                pairs = {tuple(map(int, x.split("/"))) for s in g[field] if s for x in s.split("|")}
                r[field] = pairs_text(pairs)
                r[field.replace("values", "min_n")] = min((n for n, m in pairs), default=None)
                r[field.replace("values", "max_n")] = max((n for n, m in pairs), default=None)
                r[field.replace("values", "min_m")] = min((m for n, m in pairs), default=None)
                r[field.replace("values", "max_m")] = max((m for n, m in pairs), default=None)
            assert sum(r[state+"_pools"] for state in states) == r["legal_pools"]
            summaries.append(r)
    summary = pd.DataFrame(summaries)
    write_csv(summary, OUT / "FINAL_REPLACEMENT_BAND_COVERAGE.csv")
    write_csv(pd.DataFrame(definitions), OUT / "FINAL_REPLACEMENT_BAND_DEFINITIONS.csv")
    receipt = dict(methods=METHODS, ordinary_pools=236, distinct_images=int(cap.image.nunique()), distinct_buildings=int(cap.building.nunique()),
        primary_pools=206, other_admitted_pools=30, other_admitted_maximum_N=int(cap.loc[cap.scope.eq("other"), "pool_n"].max()),
        pool_band_rows=len(pool_result), summary_rows=len(summary), bands=len(BANDS),
        distinct_source_event_identities=len(events), duplicate_event_identities_removed=duplicate_event_identities,
        registered_direction_cells_outside_capacity=total_outside_capacity, all_registered_events_executed=bool(events.executed.all()),
        independent_closed_form_capacity_checks=len(pool_result), independent_closed_form_capacity_checks_pass=True,
        all_n_m_universe="n>=3, 1<=m<=n, N<=35; require N>=n+2m for ABC, N>=n+m for AC; D may be empty",
        scope_warning="236 pools are not 236 independent images: primary206+other30 share206images22buildings.",
        band_union_warning="Any-n bands count pools once if ANY eligible n/m is possible; they do not imply every feasible n/m is registered.",
        direction_warning="Pure-source and pure-target classes only; mixed-composition source blocks have different capacity constraints.",
        Q_warning="ABC primary=pairwise C-B; triple Q separately; AC primary=pairwise C-A, no B/triple; missing Q never zero.",
        other_scope_warning="Other-admitted 30 all N<=17, exclude m7/m8 ABC; small-m half/over-half can have real capacity.",
        coverage_limit="Only the four prespecified grids are direction-complete for five methods; other theoretical n/m/directions remain intentionally unregistered.")
    (OUT / "FINAL_REPLACEMENT_BAND_RECEIPT.json").write_text(json.dumps(receipt, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(receipt, ensure_ascii=False), flush=True)
    print(summary[summary.population.eq("primary_206")][["method", "band", "class_feasible_pools", "executed_pools", "primary_Q_evaluable_pools", "triple_Q_evaluable_pools", "capacity_present_no_event_in_band_pools", "capacity_pool_n_m_cells_not_registered"]].to_string(index=False), flush=True)


if __name__ == "__main__":
    main()
