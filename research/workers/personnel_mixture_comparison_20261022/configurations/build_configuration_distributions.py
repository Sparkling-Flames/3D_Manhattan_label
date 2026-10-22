#!/usr/bin/env python3
"""Concrete composition distributions using already evaluated finite panels.

No model fitting, participant reselection, fusion or quality scoring occurs here.
The inherited design fixes D and enumerates choose(12, 6) variable-member sets.
Primary support requires every team member to have a known target-LOBO label.
Frozen geometry_common / qt_common support is an additional, explicit flag.

Run census first; aggregate can then checkpoint each condition separately.
"""
from __future__ import annotations

import argparse
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
REPO = HERE.parents[3]
SOURCE_MAIN = "ef148c82df18582228b2d23837faa2659e79eba7"
COMP = REPO / "research/workers/personnel_useful_taxonomy_v3_20261021/composition"
LABELS = REPO / "research/workers/personnel_exchange_closure_20261022/classification/ALL_METHOD_LABELS_LOBO.csv.gz"
OLD = REPO / "research/workers/personnel_v3_20261021/repro/personnel_global_composition_20261021"
METHODS = ("V3_BEHAVIOR", "V3_JOINT_QT")
STRUCT = ["turn_history", "short_history", "redundancy_history", "area_history", "height_history"]
CONTEXT = ["simple_turn_history", "complex_turn_history", "complex_short_history"]
BEHAVIOR_FIELDS = {"TURN": STRUCT[:2], "STRUCTURE": STRUCT[:3], "SCALE": STRUCT[3:], "JOINT": STRUCT, "CONTEXT": CONTEXT + STRUCT[2:]}
JOINT_FIELDS = {"EQT": STRUCT[:2], "GEQT": STRUCT[:2] + STRUCT[3:], "CQT": CONTEXT}
QT = ["q_effect", "q_downside", "t_effect", "t_tail"]
META = ["panel_id", "pool_id", "image", "building", "condition", "difficulty", "source_domain", "n", "variable_panel_no"]
METRICS = [
    "B8L2", "D10", "iou_2d", "IoU3D100", "S_bottom_deg", "dir", "Hmean", "Hcenter", "omission", "extension",
    "ref_node_recall_5", "ref_node_recall_9", "ref_edge_recall_5", "ref_edge_recall_9",
    "diag_corner_recall_05", "diag_wall_coverage_03", "diag_wall_coverage_05", "nodes",
    "fusion_turn_n", "fusion_short_turn_edges", "fusion_redundancy_n", "geometry_area_h2",
    "centroid_x_h", "centroid_z_h", "bounds_min_x_h", "bounds_max_x_h", "bounds_min_z_h", "bounds_max_z_h",
    "height_mean_h", "height_min_h", "height_max_h", "height_mean_ratio", "bottom_y_mean_px", "top_y_mean_px",
    "minimum_support", "selected_support_min", "identity_groups_n", "unselected_groups_n", "minority_observations_n", "half_vote_nodes",
    "failure", "below_four", "location_unresolved", "order_tied", "connection_available",
]


def sha(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as f:
        for b in iter(lambda: f.read(2 ** 20), b""):
            h.update(b)
    return h.hexdigest()


def digest(x):
    return hashlib.sha256(json.dumps(x, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()).hexdigest()


def team_key(pool_id, members):
    return pool_id + "__" + digest(sorted(members))[:20]


def save(frame, name):
    p = HERE / name
    p.parent.mkdir(parents=True, exist_ok=True)
    temp = p.with_name(p.name + ".partial")
    payload = frame.to_csv(index=False).encode("utf-8-sig")
    if p.name.endswith(".gz"):
        payload = gzip.compress(payload, compresslevel=5, mtime=0)
    with temp.open("wb") as f:
        assert f.write(payload) == len(payload)
        f.flush()
        os.fsync(f.fileno())
    # Verify the serialized object, including the gzip footer, before promotion.
    count = sum(len(chunk) for chunk in pd.read_csv(temp, compression="gzip" if p.name.endswith(".gz") else None, chunksize=50000, low_memory=False))
    assert count == len(frame), (name, count, len(frame))
    os.replace(temp, p)
    return {"path": name, "rows": len(frame), "columns": len(frame.columns), "bytes": p.stat().st_size, "sha256": sha(p)}


def js(name, value):
    def clean(x):
        if isinstance(x, dict):
            return {str(k): clean(v) for k, v in x.items()}
        if isinstance(x, (list, tuple)):
            return [clean(v) for v in x]
        if isinstance(x, np.generic):
            return clean(x.item())
        if isinstance(x, float) and not math.isfinite(x):
            return None
        return x
    p = HERE / name
    temp = p.with_name(p.name + ".partial")
    temp.write_text(json.dumps(clean(value), ensure_ascii=False, indent=2, allow_nan=False) + "\n")
    os.replace(temp, p)


def ws(s):
    return str(s).split("|") if isinstance(s, str) and s else []


def truth(s):
    return s.astype(str).str.lower().isin(["true", "1", "1.0"])


def count_json(classes, values):
    return json.dumps(dict(zip(classes, map(int, values))), sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def bounded_vectors(capacities, n):
    suffix = [sum(capacities[j:]) for j in range(len(capacities) + 1)]
    def visit(j, left, row):
        if j == len(capacities):
            if left == 0:
                yield tuple(row)
            return
        for k in range(max(0, left - suffix[j + 1]), min(capacities[j], left) + 1):
            yield from visit(j + 1, left - k, row + [k])
    yield from visit(0, n, [])


def frozen_common_support(labels):
    """Reproduce only the frozen eligibility mask, without fitting its models."""
    old = pd.read_csv(OLD / "composition/FROZEN_LABELS.csv")
    qt = pd.read_csv(OLD / "multivariate/continuous_features_lobo.csv.gz")
    qt = qt[qt.metric.eq("B8L2")]
    out = {}
    for (condition, fold), g in labels.groupby(["condition", "heldout_building"]):
        s = g[g.method.eq("V3_BEHAVIOR")].set_index("worker_id")
        j = g[g.method.eq("V3_JOINT_QT")].set_index("worker_id").reindex(s.index)
        q = qt[qt.condition.eq(condition) & qt.heldout_building.eq(fold)].set_index("worker_id").reindex(s.index)
        om = "M_structure" if condition == "manual" else "SP_scale"
        o = old[old.condition.eq(condition) & old.heldout_building.eq(fold) & old.method_id.eq(om)]
        o = o.pivot(index="worker_id", columns="tier", values="class_id").reindex(index=s.index, columns=["coarse", "fine"])
        family = s.selected_family.dropna().iloc[0]
        ok = truth(s.base_supported) & s[STRUCT].notna().all(axis=1)
        ok &= s[["coarse_label", "fine_label"]].notna().all(axis=1) & ~s[["coarse_label", "fine_label"]].eq("unknown").any(axis=1)
        ok &= o[["coarse", "fine"]].notna().all(axis=1) & ~o[["coarse", "fine"]].eq("unknown").any(axis=1)
        ok &= s[BEHAVIOR_FIELDS[family]].notna().all(axis=1)
        out[condition, fold, "geometry_common"] = set(s.index[ok])
        jf = j.selected_family.dropna().iloc[0]
        jok = ok & q[QT].notna().all(axis=1) & truth(q.Q_supported) & truth(q.T_supported)
        jok &= truth(j.known) & j[JOINT_FIELDS[jf] + ["q_history", "q_downside", "t_history"]].notna().all(axis=1)
        out[condition, fold, "qt_common"] = set(s.index[jok])
    return out


def load_design():
    panels = pd.read_csv(COMP / "PANELS.csv", keep_default_na=False)
    if (COMP / "DESIGN_TEAMS.csv.gz").exists() and (COMP / "PANEL_MEMBERSHIP.csv.gz").exists():
        teams = pd.read_csv(COMP / "DESIGN_TEAMS.csv.gz", usecols=["team_key", "pool_id", "image", "building", "condition", "n", "member_workers"])
        members = pd.read_csv(COMP / "PANEL_MEMBERSHIP.csv.gz", usecols=["panel_id", "team_key", "selected_variable_workers"])
        source = "inherited_exact_member_files"
    else:
        tr = {}; mr = []
        for p in panels.to_dict("records"):
            for choice in itertools.combinations(ws(p["variable_workers"]), 6):
                all_workers = sorted(ws(p["background_workers"]) + list(choice))
                key = team_key(p["pool_id"], all_workers)
                tr[key] = dict(team_key=key, **{k: p[k] for k in ["pool_id", "image", "building", "condition", "n"]}, member_workers="|".join(all_workers))
                mr.append(dict(panel_id=p["panel_id"], team_key=key, selected_variable_workers="|".join(choice)))
        teams = pd.DataFrame(tr.values())
        members = pd.DataFrame(mr)
        source = "deterministic_member_reconstruction_from_inherited_PANELS_no_fusion"
    assert not teams.team_key.duplicated().any()
    assert not members.duplicated(["panel_id", "team_key"]).any()
    assert members.groupby("panel_id").size().eq(924).all()
    assert set(members.team_key) == set(teams.team_key)
    for r in teams.itertuples():
        assert team_key(r.pool_id, ws(r.member_workers)) == r.team_key
        assert len(ws(r.member_workers)) == r.n
    return panels, teams, members, source


def census():
    panels, teams, members, design_source = load_design()
    labels = pd.read_csv(LABELS)
    common = frozen_common_support(labels)
    team_workers = dict(zip(teams.team_key, teams.member_workers.map(lambda s: set(ws(s)))))
    groups = dict(tuple(members.groupby("panel_id")))
    label_rows = []
    definitions = []
    label_maps = {}
    for (method, condition, fold), g in labels.groupby(["method", "condition", "heldout_building"]):
        if method not in METHODS or fold == "ALL":
            continue
        for tier in ["coarse", "fine"]:
            col = tier + "_label"
            known = truth(g.known) & g[col].notna() & ~g[col].isin(["unknown", "unassigned", "insufficient_evidence", ""])
            good = g[known]
            label_maps[method, condition, fold, tier] = (dict(zip(good.worker_id, good[col])), dict(zip(good.worker_id, good.coarse_label)))
            for c, cg in good.groupby(col):
                row = dict(method=method, condition=condition, heldout_building=fold, tier=tier, class_id=c,
                           selected_family=cg.selected_family.iloc[0], parent_class="|".join(sorted(cg.coarse_label.unique())),
                           members="|".join(sorted(cg.worker_id)), people=len(cg),
                           history_images_min=int(cg.n_images.min()), history_buildings_min=int(cg.n_buildings.min()),
                           history_records_sum=int(cg.n_records.sum()))
                row.update({k + "_mean": cg[k].mean() for k in STRUCT + CONTEXT + ["q_history", "q_downside", "t_history"]})
                definitions.append(row)
        gg = g.copy()
        gg["geometry_common_eligible"] = gg.worker_id.isin(common[condition, fold, "geometry_common"])
        gg["qt_common_eligible"] = gg.worker_id.isin(common[condition, fold, "qt_common"])
        label_rows.append(gg)
    save(pd.concat(label_rows, ignore_index=True), "LOBO_LABELS_USED.csv.gz")
    defs = pd.DataFrame(definitions)
    for f in ["turn_history", "complex_turn_history", "redundancy_history", "q_history", "t_history"]:
        defs[f + "_rank_in_fold"] = defs.groupby(["method", "condition", "heldout_building", "tier"])[f + "_mean"].rank(method="dense")
    save(defs, "FOLD_CLASS_DEFINITIONS.csv")
    save(panels, "PANELS_USED.csv")
    save(teams.sort_values("team_key"), "TEAM_MEMBERS.csv.gz")
    save(members.sort_values(["panel_id", "team_key"]), "PANEL_TEAMS.csv.gz")

    config_rows = []; links = []; support_rows = []; domain_states = {}
    for p in panels.to_dict("records"):
        meta = {k: p[k] for k in META}
        bg = ws(p["background_workers"]); variable = ws(p["variable_workers"]); domain = ws(p["domain_workers"])
        n = int(p["n"]); pid = p["panel_id"]
        for method, tier in itertools.product(METHODS, ("coarse", "fine")):
            l, parent = label_maps[method, p["condition"], p["building"], tier]
            classes = sorted(set(l.values()))
            bcap = [sum(l.get(w) == c for w in bg) for c in classes]
            vcap = [sum(l.get(w) == c for w in variable) for c in classes]
            dcap = [sum(l.get(w) == c for w in domain) for c in classes]
            bg_unknown = set(bg) - set(l); var_unknown = set(variable) - set(l)
            domain_known = set(domain) & set(l)
            theoretical = math.comb(12 - len(var_unknown), 6) if not bg_unknown and 12 - len(var_unknown) >= 6 else 0
            common_domain = "geometry_common" if method == "V3_BEHAVIOR" else "qt_common"
            cw = common[p["condition"], p["building"], common_domain]
            by_counts = collections.defaultdict(list)
            for row in groups[pid].itertuples():
                chosen = ws(row.selected_variable_workers)
                if bg_unknown or any(w not in l for w in chosen):
                    continue
                counts = tuple(a + sum(l[w] == c for w in chosen) for a, c in zip(bcap, classes))
                by_counts[counts].append(row.team_key)
            assert sum(map(len, by_counts.values())) == theoretical
            expected = {tuple(a + b for a, b in zip(c, bcap)): math.prod(math.comb(a, b) for a, b in zip(vcap, c)) for c in bounded_vectors(vcap, 6)} if not bg_unknown else {}
            assert set(expected) == set(by_counts)
            support_rows.append(dict(meta, method=method, tier=tier, registered_teams=924,
                                     labelled_teams=theoretical, unknown_label_teams=924 - theoretical,
                                     unknown_background_workers="|".join(sorted(bg_unknown)),
                                     unknown_variable_workers="|".join(sorted(var_unknown)),
                                     known_domain_people=len(domain_known), unknown_domain_people=len(domain) - len(domain_known),
                                     feasible_panel_configurations=len(by_counts), common_domain=common_domain,
                                     common_domain_teams=sum(team_workers[k] <= cw for kk in by_counts.values() for k in kk),
                                     status="complete_924_labelled" if theoretical == 924 else "partial_label_support" if theoretical else "no_supported_team"))
            dk = (p["pool_id"], p["source_domain"], n, method, tier)
            state = domain_states.setdefault(dk, dict(meta={k: p[k] for k in META if k not in ("panel_id", "variable_panel_no")},
                                                       method=method, tier=tier, classes=classes, capacity=dcap,
                                                       domain_n=len(domain), known_n=len(domain_known), teams=collections.defaultdict(set),
                                                       panels=collections.defaultdict(set)))
            assert state["classes"] == classes and state["capacity"] == dcap
            for counts, keys in sorted(by_counts.items()):
                assert len(keys) == expected[counts] and len(set(keys)) == len(keys)
                cid = digest(["mixture_configuration_20261022", pid, method, tier, dict(zip(classes, counts))])[:24]
                pc = collections.Counter(parent[worker] for worker in team_workers[keys[0]])
                cf = dict(meta, method=method, tier=tier, configuration_id=cid,
                          class_counts=count_json(classes, counts), background_class_counts=count_json(classes, bcap),
                          selected_variable_counts=count_json(classes, [a - b for a, b in zip(counts, bcap)]),
                          parent_class_counts=json.dumps(dict(sorted(pc.items())), separators=(",", ":")),
                          variable_class_capacity=count_json(classes, vcap), domain_class_capacity=count_json(classes, dcap),
                          background_workers="|".join(bg), variable_workers="|".join(variable),
                          theoretical_conditional_teams=expected[counts], actual_conditional_teams=len(keys),
                          member_variation_estimable=len(keys) > 1, full_domain_member_sets_same_vector=math.prod(math.comb(a, b) for a, b in zip(dcap, counts)),
                          common_domain=common_domain, common_domain_teams=sum(team_workers[k] <= cw for k in keys),
                          primary_support="every_team_member_has_target_LOBO_label", complete_conditional_enumeration=True)
                config_rows.append(cf)
                state["teams"][counts].update(keys); state["panels"][counts].add(pid)
                links.extend(dict(panel_id=pid, team_key=k, method=method, tier=tier, configuration_id=cid,
                                  common_domain_eligible=team_workers[k] <= cw) for k in sorted(keys))
        if len(support_rows) % 100 == 0:
            print(json.dumps({"stage": "census", "processed_panels": len(support_rows) // 4, "configurations": len(config_rows)}), flush=True)
    outputs = []
    outputs.append(save(pd.DataFrame(config_rows), "PANEL_CONFIGURATION_CENSUS.csv.gz"))
    outputs.append(save(pd.DataFrame(support_rows), "PANEL_SUPPORT.csv"))
    outputs.append(save(pd.DataFrame(links), "TEAM_CONFIGURATION_LINKS.csv.gz"))
    # A distinct full-pool vector denominator: no extra team endpoint is computed.
    domain_rows = []; domain_summary = []
    for dk, state in sorted(domain_states.items()):
        classes = state["classes"]; cap = state["capacity"]; n = state["meta"]["n"]
        cfg_n = 0; theoretical_n = 0; covered_n = 0
        for counts in bounded_vectors(cap, n):
            theoretical = math.prod(math.comb(a, b) for a, b in zip(cap, counts))
            observed = len(state["teams"].get(counts, set()))
            domain_rows.append(dict(state["meta"], method=state["method"], tier=state["tier"],
                                    domain_configuration_id=digest([dk, counts])[:24],
                                    class_counts=count_json(classes, counts), domain_class_capacity=count_json(classes, cap),
                                    theoretical_member_sets=theoretical, observed_unique_member_sets=observed,
                                    unobserved_member_sets=theoretical - observed,
                                    registered_backgrounds_reaching_vector=len(state["panels"].get(counts, set())),
                                    configuration_reached=observed > 0))
            cfg_n += 1; theoretical_n += theoretical; covered_n += observed
        assert theoretical_n == (math.comb(state["known_n"], n) if state["known_n"] >= n else 0)
        domain_summary.append(dict(state["meta"], method=state["method"], tier=state["tier"],
                                   domain_people=state["domain_n"], labelled_people=state["known_n"],
                                   feasible_labelled_vectors=cfg_n, reached_vectors=len(state["teams"]),
                                   theoretical_labelled_members=theoretical_n, observed_unique_labelled_members=covered_n,
                                   unobserved_labelled_members=theoretical_n - covered_n,
                                   full_domain_members=math.comb(state["domain_n"], n),
                                   teams_with_unknown_label=math.comb(state["domain_n"], n) - theoretical_n))
    outputs.append(save(pd.DataFrame(domain_rows), "DOMAIN_CONFIGURATION_CENSUS.csv.gz"))
    outputs.append(save(pd.DataFrame(domain_summary), "DOMAIN_COVERAGE.csv"))
    js("CENSUS_COMPLETE.json", dict(status="complete", source_main=SOURCE_MAIN, underlying_data="true_v2", endpoint_calls=0,
                                      panels=len(panels), unique_teams=len(teams), panel_team_links=len(members),
                                      configuration_rows=len(config_rows), classification_team_links=len(links),
                                      design_source=design_source, source_labels_sha256=sha(LABELS),
                                      source_panels_sha256=sha(COMP / "PANELS.csv"), files=outputs,
                                      denominator_note="Methods/tiers/source domains overlap; sums across them are accounting totals, not disjoint global team universes."))
    print(json.dumps({"stage": "census_complete", "panels": len(panels), "configurations": len(config_rows), "links": len(links)}, ensure_ascii=False), flush=True)


def expression(value):
    if not isinstance(value, str) or not value:
        return [np.nan] * 3
    g = json.loads(value)
    p = np.asarray((g or {}).get("footprint") or [], float)
    if p.ndim != 2 or p.shape[1] != 2 or len(p) < 3 or not np.isfinite(p).all():
        return [np.nan] * 3
    edges = np.roll(p, -1, axis=0) - p
    length = np.linalg.norm(edges, axis=1)
    prev = np.roll(edges, 1, axis=0)
    den = np.linalg.norm(prev, axis=1) * length
    if (den <= 1e-12).any():
        return [np.nan] * 3
    turn = np.degrees(np.arccos(np.clip((prev * edges).sum(axis=1) / den, -1, 1)))
    redundant = int(np.sum(turn <= 5))
    short = int(np.sum((length / length.sum() < .04) & (turn >= 15) & (np.roll(turn, -1) >= 15)))
    return [len(p) - redundant, short, redundant]


def load_endpoints(condition):
    teams = pd.read_csv(HERE / "TEAM_MEMBERS.csv.gz")
    need = set(teams.loc[teams.condition.eq(condition), "team_key"])
    scores = []; expressions = []; manifest = []
    for path in sorted((COMP / "batches").glob("batch_*/ENDPOINT_SCALARS.csv.gz")):
        if not (path.parent / "COMPLETION.json").exists():
            continue
        d = pd.read_csv(path, low_memory=False)
        d = d[d.team_key.isin(need)].copy()
        if d.empty:
            continue
        d["endpoint_source_batch"] = path.parent.name
        scores.append(d)
        geo = path.parent / "ENDPOINT_GEOMETRY.csv.gz"
        gd = pd.read_csv(geo, usecols=["team_key", "geometry_json"])
        gd = gd[gd.team_key.isin(need)]
        cache = {}
        rows = []
        for r in gd.itertuples():
            value = r.geometry_json if isinstance(r.geometry_json, str) else ""
            if value not in cache:
                cache[value] = expression(value)
            rows.append([r.team_key, *cache[value]])
        expressions.append(pd.DataFrame(rows, columns=["team_key", "fusion_turn_n", "fusion_short_turn_edges", "fusion_redundancy_n"]))
        manifest.append(dict(batch=path.parent.name, condition=condition, used_rows=len(d), scalar_path=os.path.relpath(path, REPO),
                             scalar_sha256=sha(path), geometry_path=os.path.relpath(geo, REPO), geometry_sha256=sha(geo),
                             geometry_derivation="frozen response geometry_expression: redundancy<=5deg; shortedge perimeter share<0.04 and adjacent turns>=15deg"))
        print(json.dumps({"stage": "read_existing_endpoint_batch", "condition": condition, "batch": path.parent.name, "used": len(d)}), flush=True)
    if not scores:
        raise FileNotFoundError("No completed original batch_* endpoints were found")
    d = pd.concat(scores, ignore_index=True)
    assert not d.team_key.duplicated().any()
    missing = need - set(d.team_key)
    if missing:
        save(pd.DataFrame({"team_key": sorted(missing)}), f"MISSING_ENDPOINTS_{condition}.csv")
        raise ValueError(("missing_endpoint_sets", condition, len(missing)))
    g = pd.concat(expressions, ignore_index=True)
    assert not g.team_key.duplicated().any() and set(g.team_key) == need
    d = d.merge(g, on="team_key", validate="one_to_one")
    d["complete_evaluable"] = truth(d.complete_evaluable)
    d["failure"] = (~d.complete_evaluable).astype(int)
    d["recorded_time_eligible"] = d.source_time_known_n.eq(d.k) & d.source_time_total_seconds.gt(0) & d.time_source_kinds.fillna("").ne("") & ~d.time_source_kinds.fillna("").str.contains("|", regex=False)
    d["recorded_time_total_seconds"] = d.source_time_total_seconds.where(d.recorded_time_eligible)
    for c in METRICS:
        if c not in d:
            d[c] = np.nan
        if d[c].dtype == bool:
            d[c] = d[c].astype(float)
        d[c] = pd.to_numeric(d[c], errors="coerce")
    retain = ["team_key", "pool_id", "image", "building", "condition", "k", "endpoint_source_batch", "complete_evaluable", "score_status", "geometry_status",
              "source_time_known_n", "source_time_total_seconds", "time_source_kinds", "time_source_table", "recorded_time_eligible", "recorded_time_total_seconds"] + METRICS
    retain = list(dict.fromkeys(c for c in retain if c in d))
    d = d[retain].copy()
    save(d, f"ENDPOINT_OUTCOMES_{condition}.csv.gz")
    save(pd.DataFrame(manifest), f"ENDPOINT_SOURCE_MANIFEST_{condition}.csv")
    return d


def distribution(rows, metric, time_source="not_time_metric"):
    """Every descriptive denominator is metric-specific; singleton spread is NA."""
    x = pd.to_numeric(rows[metric], errors="coerce").dropna().to_numpy(float)
    x = x[np.isfinite(x)]
    k = len(x)
    result = dict(metric=metric, time_source_kind=time_source, valid_n=k, missing_n=len(rows) - k,
                  member_variation_estimable=k >= 2, mean=np.nan, p05=np.nan, p25=np.nan, median=np.nan,
                  p75=np.nan, p95=np.nan, sd=np.nan, iqr=np.nan, minimum=np.nan, maximum=np.nan, range=np.nan)
    if k:
        result["mean"] = float(np.mean(x))
        result.update(zip(["p05", "p25", "median", "p75", "p95"], np.quantile(x, [.05, .25, .5, .75, .95])))
        result["minimum"], result["maximum"] = float(np.min(x)), float(np.max(x))
    if k >= 2:
        result.update(sd=float(np.std(x, ddof=1)), iqr=result["p75"] - result["p25"], range=result["maximum"] - result["minimum"])
    return result


def aggregate(condition):
    scores = load_endpoints(condition)
    cfg = pd.read_csv(HERE / "PANEL_CONFIGURATION_CENSUS.csv.gz")
    cfg = cfg[cfg.condition.eq(condition)].copy()
    links = pd.read_csv(HERE / "TEAM_CONFIGURATION_LINKS.csv.gz")
    links = links[links.configuration_id.isin(set(cfg.configuration_id))]
    frame = links.merge(scores, on="team_key", validate="many_to_one")
    cfg_by_id = cfg.set_index("configuration_id")
    rows = []; overview = []
    for cid, g in frame.groupby("configuration_id", sort=False):
        c = cfg_by_id.loc[cid]
        assert len(g) == c.actual_conditional_teams and not g.team_key.duplicated().any()
        base = dict(configuration_id=cid, **{k: c[k] for k in META}, method=c.method, tier=c.tier,
                    teams=len(g), scorable_teams=int(g.complete_evaluable.sum()), failed_teams=int(g.failure.sum()),
                    recorded_time_eligible_teams=int(g.recorded_time_eligible.sum()))
        time_groups = g[g.recorded_time_eligible].groupby("time_source_kinds")
        base["valid_time_source_count"] = len(time_groups)
        base["valid_time_sources"] = "|".join(sorted(time_groups.groups))
        over = dict(base, class_counts=c.class_counts, background_class_counts=c.background_class_counts,
                    selected_variable_counts=c.selected_variable_counts, parent_class_counts=c.parent_class_counts,
                    common_domain=c.common_domain, common_domain_teams=c.common_domain_teams,
                    singleton_total_team=len(g) == 1, failure_rate=float(g.failure.mean()))
        for metric in METRICS:
            r = distribution(g, metric)
            rows.append(dict(base, **r))
            if metric in ["B8L2", "D10", "IoU3D100", "nodes", "fusion_turn_n", "fusion_short_turn_edges", "geometry_area_h2", "height_mean_h", "bottom_y_mean_px", "top_y_mean_px", "S_bottom_deg", "omission", "extension"]:
                over.update({metric + "_" + k: r[k] for k in ["valid_n", "mean", "p05", "p25", "median", "p75", "p95", "sd", "iqr", "minimum", "maximum", "range"]})
        if not len(time_groups):
            rows.append(dict(base, **distribution(g.assign(recorded_time_total_seconds=np.nan), "recorded_time_total_seconds", "no_eligible_time")))
        for source, tg in time_groups:
            r = distribution(tg, "recorded_time_total_seconds", source)
            r["missing_n"] = len(g) - r["valid_n"]
            rows.append(dict(base, **r))
            if len(time_groups) == 1:
                over.update({"recorded_time_total_seconds_" + k: r[k] for k in ["valid_n", "mean", "p05", "p25", "median", "p75", "p95", "sd", "iqr", "minimum", "maximum", "range"]})
        cg = g[truth(g.common_domain_eligible)]
        over["common_domain_Q_n"] = int(cg.B8L2.notna().sum())
        over["common_domain_Q_mean"] = cg.B8L2.mean()
        overview.append(over)
        if len(overview) % 500 == 0:
            print(json.dumps({"stage": "aggregate", "condition": condition, "configuration_cells": len(overview)}), flush=True)
    out = save(pd.DataFrame(rows), f"CONFIGURATION_DISTRIBUTIONS_{condition}.csv.gz")
    summary = save(pd.DataFrame(overview), f"CONFIGURATION_OVERVIEW_{condition}.csv.gz")
    js(f"AGGREGATION_COMPLETE_{condition}.json", dict(status="complete", source_main=SOURCE_MAIN, underlying_data="true_v2",
                                                      endpoint_calls=0, unique_reused_endpoints=len(scores),
                                                      label_supported_configuration_cells=len(overview), metric_rows=len(rows),
                                                      team_method_tier_panel_links=len(frame), primary_support="all_team_members_target_LOBO_label_known",
                                                      statistic_note="Quantiles use NumPy linear interpolation; sd uses ddof=1; singleton dispersion NA. Recorded-time sources are separate. Failure is retained without zero-imputed Q.",
                                                      files=[out, summary]))
    print(json.dumps({"stage": "aggregate_complete", "condition": condition, "configurations": len(overview), "rows": len(rows)}, ensure_ascii=False), flush=True)


def rebuild_overview(condition):
    """Recover the wide presentation table from the complete saved long table."""
    long = pd.read_csv(HERE / f"CONFIGURATION_DISTRIBUTIONS_{condition}.csv.gz", low_memory=False)
    cfg = pd.read_csv(HERE / "PANEL_CONFIGURATION_CENSUS.csv.gz")
    cfg = cfg[cfg.condition.eq(condition)].copy()
    identity = ["configuration_id"] + META + ["method", "tier", "teams", "scorable_teams", "failed_teams", "recorded_time_eligible_teams", "valid_time_source_count", "valid_time_sources"]
    out = long[identity].drop_duplicates("configuration_id").copy()
    out = out.merge(cfg[["configuration_id", "class_counts", "background_class_counts", "selected_variable_counts", "parent_class_counts", "common_domain", "common_domain_teams"]], on="configuration_id", validate="one_to_one")
    out["singleton_total_team"] = out.teams.eq(1)
    out["failure_rate"] = out.failed_teams / out.teams
    selected = ["B8L2", "D10", "IoU3D100", "nodes", "fusion_turn_n", "fusion_short_turn_edges", "geometry_area_h2", "height_mean_h", "bottom_y_mean_px", "top_y_mean_px", "S_bottom_deg", "omission", "extension", "recorded_time_total_seconds"]
    fields = ["valid_n", "mean", "p05", "p25", "median", "p75", "p95", "sd", "iqr", "minimum", "maximum", "range"]
    for metric in selected:
        a = long[long.metric.eq(metric)][["configuration_id", "time_source_kind"] + fields].copy()
        if metric == "recorded_time_total_seconds":
            allowed = set(out.loc[out.valid_time_source_count.le(1), "configuration_id"])
            a = a[a.configuration_id.isin(allowed)]
        assert not a.configuration_id.duplicated().any()
        a = a.drop(columns="time_source_kind").rename(columns={k: metric + "_" + k for k in fields})
        out = out.merge(a, on="configuration_id", how="left", validate="one_to_one")
    # The complete frozen masks coincide for these registered panels, checked
    # by census. Do not generalize this identity to a different inventory.
    assert out.common_domain_teams.eq(out.teams).all()
    out["common_domain_Q_n"] = out.B8L2_valid_n
    out["common_domain_Q_mean"] = out.B8L2_mean
    assert len(out) == len(cfg)
    new = save(out, f"CONFIGURATION_OVERVIEW_{condition}.csv.gz")
    receipt_path = HERE / f"AGGREGATION_COMPLETE_{condition}.json"
    receipt = json.loads(receipt_path.read_text())
    receipt["files"] = [r if r["path"] != new["path"] else new for r in receipt["files"]]
    receipt["wide_view_serialization"] = "Rebuilt losslessly from saved complete metric rows; validated gzip footer and exact row count. No score recalculation."
    js(receipt_path.name, receipt)
    print(json.dumps(new), flush=True)


def main():
    global COMP
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=["census", "aggregate", "rebuild-overview"])
    parser.add_argument("--condition", choices=["manual", "semi"])
    parser.add_argument("--composition-dir", type=Path, default=COMP, help="Inherited composition/ directory; may be an isolated archive recovery")
    args = parser.parse_args()
    COMP = args.composition_dir.resolve()
    if args.command == "census":
        census()
    elif args.command == "rebuild-overview":
        if not args.condition:
            parser.error("rebuild-overview requires --condition")
        rebuild_overview(args.condition)
    else:
        if not args.condition:
            parser.error("aggregate requires --condition")
        aggregate(args.condition)


if __name__ == "__main__":
    main()
