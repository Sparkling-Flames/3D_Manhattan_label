"""独立读表/原几何核查人数抽样补充；不调用作者统计函数、融合或评分。"""
from __future__ import annotations

import gzip
import json
from pathlib import Path

import numpy as np
import pandas as pd
from shapely.geometry import Polygon

ROOT = Path(__file__).resolve().parents[3]
POP = ROOT / "research/workers/personnel_population_curves_v2_20261023"
BASE = POP / "sampling_precision_20261025"
OUT = BASE / "local_audit/geometry"


def stream_array(path):
    """逐对象读取旧顶层JSON数组，避免把全量几何展开到内存。"""
    decoder = json.JSONDecoder()
    with gzip.open(path, "rt", encoding="utf-8") as f:
        buf, start, eof = "", False, False
        while True:
            if not eof:
                part = f.read(1 << 20)
                eof = not part
                buf += part
            buf = buf.lstrip()
            if not start:
                assert buf.startswith("[")
                buf, start = buf[1:], True
            while True:
                buf = buf.lstrip(" \r\n\t,")
                if buf.startswith("]"):
                    assert not (buf[1:] + f.read()).strip()
                    return
                try:
                    row, end = decoder.raw_decode(buf)
                except json.JSONDecodeError:
                    if eof:
                        raise
                    break
                yield row
                buf = buf[end:]


def v_from_polygons(keys, polygons, exact=False):
    """重复的抽样团队保留频数；精确目录包含同队自配零距离。"""
    ps = [polygons.get(k) for k in keys]
    valid = [i for i, p in enumerate(ps) if p is not None]
    n, q = len(ps), len(valid)
    if q == 0 or (q < 2 and not exact):
        return np.nan, np.nan, q
    distances = np.zeros((q, q))
    for i in range(q):
        for j in range(i + 1, q):
            a, b = ps[valid[i]], ps[valid[j]]
            inter = a.intersection(b).area
            distances[i, j] = distances[j, i] = 1 - inter / (a.area + b.area - inter)
    total = distances.sum()
    if exact:
        return total / q**2, 0.0, q
    theta = total / (q * (q - 1))
    if q < 3:
        return theta, np.nan, q
    leave = np.full(n, theta)
    for i, index in enumerate(valid):
        leave[index] = (total - 2 * distances[i].sum()) / ((q - 1) * (q - 2))
    se = np.sqrt((n - 1) / n * np.square(leave - leave.mean()).sum())
    return theta, se, q


def self_check():
    a = Polygon([(0, 0), (1, 0), (1, 1), (0, 1)])
    b = Polygon([(2, 0), (3, 0), (3, 1), (2, 1)])
    ps = {"a": a, "b": b}
    assert np.isclose(v_from_polygons(["a", "a", "b"], ps)[0], 2 / 3)
    assert np.isclose(v_from_polygons(["a", "b"], ps, exact=True)[0], 0.5)
    assert np.isnan(v_from_polygons(["a", "missing"], ps)[0])
    assert v_from_polygons(["a"], ps, exact=True)[0] == 0


def natural_links():
    cols = ["pool_id", "path_id", "policy", "k", "team_key"]
    old = pd.read_csv(POP / "results/PREFIX_TEAM_LINKS.csv.gz", usecols=cols)
    old = old[old.policy.eq("natural_random")].copy()
    old["batch"] = "old24"
    new = pd.read_csv(BASE / "design/NEW_PREFIX_TEAM_LINKS.csv.gz", usecols=cols + ["batch"])
    new = new[new.policy.eq("natural_random")].copy()
    new["batch"] = new.batch.replace({"balanced_new24": "new24", "focus_new48": "focus48"})
    return pd.concat([old, new], ignore_index=True)


def case_audits(exact, links):
    wc = exact[exact.image.eq("wc2JMjhGNzB-46") & exact.k.eq(27)].copy()
    assert len(wc) == 28 and wc.team_key.nunique() == 28
    pool = set("|".join(wc.member_workers).split("|"))
    assert len(pool) == 28
    absent = [pool - set(x.split("|")) for x in wc.member_workers]
    assert all(len(x) == 1 for x in absent) and len(set(next(iter(x)) for x in absent)) == 28
    np.testing.assert_allclose(wc.marginal_weight, 1 / 28)
    q = wc.set_index("team_key").B8L2
    ordered = np.sort(q.to_numpy())
    split = np.argmax(np.diff(ordered))
    low = set(q[q < (ordered[split] + ordered[split + 1]) / 2].index)
    assert len(low) == 4
    pp = links[links.pool_id.eq(wc.pool_id.iloc[0]) & links.k.eq(27)]
    cohorts = {"old24": ["old24"], "new24": ["new24"], "combined48": ["old24", "new24"], "combined96": ["old24", "new24", "focus48"]}
    rows = []
    for name, batches in cohorts.items():
        keys = pp[pp.batch.isin(batches)].team_key
        values = q.loc[keys].to_numpy()
        rows.append(dict(cohort=name, paths=len(keys), unique_teams=keys.nunique(), low_n=int(keys.isin(low).sum()), p10=float(np.quantile(values, .1)), mean=float(values.mean())))
    rows.append(dict(cohort="exact", paths=28, unique_teams=28, low_n=4, p10=float(np.quantile(q, .1)), mean=float(q.mean())))
    frame = pd.DataFrame(rows)
    assert frame.paths.tolist() == [24, 24, 48, 96, 28], frame
    assert frame.low_n.tolist() == [1, 1, 2, 7, 4], frame
    frame.to_csv(OUT / "WC2_46_RECOMPUTED.csv", index=False)

    vf = exact[exact.image.eq("VFuaQ6m2Qom-04") & exact.k.isin([34, 35])].copy()
    loo = vf[vf.k.eq(34)]
    assert len(loo) == 35 and loo.team_key.nunique() == 35
    assert int(loo.B8L2.notna().sum()) == 32
    assert loo.nodes.value_counts().to_dict() == {4: 29, 5: 3, 3: 3}
    assert vf[vf.k.eq(35)].nodes.iloc[0] == 3 and vf[vf.k.eq(35)].B8L2.isna().all()
    with gzip.open(BASE / "analysis_geometry/case_VFua_04/VFUA_MECHANISM_GEOMETRY.json.gz", "rt", encoding="utf-8") as f:
        mechanism = json.load(f)
    endpoint_by_key = {r["team_key"]: r for r in mechanism["selected_endpoints"]}
    votes = []
    for key, state in mechanism["selected_full_states"].items():
        assert state["n"] == 34 and state["minimum_support"] == 17
        groups = {r["feature_id"]: r for r in state["identity_groups"]}
        selection = {r["feature_id"] for r in state["node_consensus"]["nodes"]}
        for fid in ["node_002", "node_015"]:
            group = groups[fid]
            support = len({m["worker"] for m in group["members"]})
            assignment_support = sum(fid in set(a["feature_ids"]) for a in state["assignments"])
            assert support == assignment_support == group["joint_support"]
            assert (fid in selection) == (support >= 17)
            votes.append(dict(team_key=key, absent_worker=endpoint_by_key[key]["absent_worker"], feature_id=fid, support=support, selected=fid in selection))
    vv = pd.DataFrame(votes)
    pivot = vv.pivot(index="absent_worker", columns="feature_id", values="support")
    assert pivot.loc["W103"].tolist() == [17, 16]
    assert pivot.loc["W113"].tolist() == [16, 17]
    assert pivot.loc["W134"].tolist() == [16, 16]
    vv.to_csv(OUT / "VFUA_VOTES_RECOMPUTED.csv", index=False)
    return {"wc2_exact_linear_p10": float(np.quantile(q, .1)), "wc2_exact_inverse_cdf_p10": float(np.quantile(q, .1, method="inverted_cdf")), "vfua_valid": 32, "vfua_failed": 3, "vfua_exact_q_mean": float(loo.B8L2.mean()), "vfua_exact_q_p10": float(loo.B8L2.dropna().quantile(.1))}


def aggregate_v(saved):
    d = saved[saved.layer.eq("ordinary_manual") & saved.pool_n.ge(30) & saved.metric.eq("V_floor") & saved.cohort.isin(["old24", "new24", "combined48"])].copy()
    rows = []
    for cohort, g in d.groupby("cohort"):
        p = g.pivot(index=["pool_id", "building"], columns="k", values="mean")
        for lo, hi in [(3, 6), (6, 10), (10, 20), (20, 30)]:
            delta = p[hi] - p[lo]
            assert len(delta) == 157 and delta.notna().all()
            for (pid, building), x in delta.items():
                rows.append(dict(cohort=cohort, pool_id=pid, building=building, k_from=lo, k_to=hi, delta=x))
    image = pd.DataFrame(rows)
    author = pd.read_csv(BASE / "analysis_geometry/results/GEOMETRY_FIXED157_INTERVAL_IMAGE.csv")
    check = image.merge(author, on=["cohort", "pool_id", "building", "k_from", "k_to"], suffixes=("_audit", "_author"), validate="one_to_one")
    assert len(check) == len(image) == len(author)
    np.testing.assert_allclose(check.delta_audit, check.delta_author, atol=1e-12)
    buildings = image.groupby(["cohort", "k_from", "k_to", "building"], as_index=False).delta.mean()
    summary = []
    for (cohort, lo, hi), g in image.groupby(["cohort", "k_from", "k_to"]):
        bb = buildings[(buildings.cohort == cohort) & (buildings.k_from == lo) & (buildings.k_to == hi)]
        summary.append(dict(cohort=cohort, k_from=lo, k_to=hi, images=len(g), delta_mean=g.delta.mean(), images_decrease=int((g.delta < -1e-9).sum()), buildings=len(bb), buildings_decrease=int((bb.delta < -1e-9).sum())))
    sf = pd.DataFrame(summary)
    assert sf[sf.cohort.eq("combined48")].buildings_decrease.eq(22).all()
    sf.to_csv(OUT / "V_FIXED157_REAGGREGATED.csv", index=False)
    buildings.to_csv(OUT / "V_BUILDINGS_REAGGREGATED.csv", index=False)
    return sf.to_dict("records")


def raw_geometry_checks(exact, links, saved):
    candidates = saved[saved.cohort.eq("combined48") & saved.metric.eq("V_floor") & saved.pool_n.ge(30)]
    selected = set()
    for difficulty in ["简单", "中等", "困难"]:
        selected.add(candidates[candidates.layer.eq("ordinary_manual") & candidates.difficulty.eq(difficulty)].sort_values("pool_id").pool_id.iloc[0])
    for image in ["VFuaQ6m2Qom-04", "wc2JMjhGNzB-46", "7y3sRwLe3Va-06"]:
        selected.update(saved[saved.image.eq(image)].pool_id.unique())
    sizes = saved.drop_duplicates("pool_id").set_index("pool_id").pool_n.to_dict()
    targets = links[links.pool_id.isin(selected)].copy()
    targets = targets[[int(r.k) in {3, 6, 10, 20, 30, int(sizes[r.pool_id])-1, int(sizes[r.pool_id])} for r in targets.itertuples()]]
    ee = exact[exact.pool_id.isin(selected) & exact.k.eq(exact.pool_n - 1)]
    keys = set(targets.team_key) | set(ee.team_key)
    fields = ["team_key", "complete_floor_evaluable"]
    scalars = {}
    paths = [POP / "results/ENDPOINT_SCALARS.csv.gz"] + sorted((BASE / "new_endpoints/table_shards/NEW_ENDPOINT_SCALARS").glob("*.csv.gz"))
    for path in paths:
        for chunk in pd.read_csv(path, usecols=fields, chunksize=30000):
            for row in chunk[chunk.team_key.isin(keys)].to_dict("records"):
                scalars[row["team_key"]] = row
    assert set(scalars) == keys
    geometries = {}
    for row in stream_array(POP / "results/ENDPOINT_GEOMETRY.json.gz"):
        if row["team_key"] in keys:
            geometries[row["team_key"]] = row.get("geometry")
    for path in sorted((BASE / "new_endpoints/table_shards/NEW_ENDPOINT_GEOMETRY_COMPACT").glob("*.jsonl.gz")):
        with gzip.open(path, "rt", encoding="utf-8") as f:
            for line in f:
                row = json.loads(line)
                if row["team_key"] in keys:
                    geometries[row["team_key"]] = row.get("geometry")
    assert set(geometries) == keys
    polygons = {}
    for key, geo in geometries.items():
        if not scalars[key]["complete_floor_evaluable"] or not geo or not geo.get("footprint"):
            continue
        poly = Polygon(geo["footprint"])
        if poly.is_valid and poly.area > 0:
            polygons[key] = poly
    cohorts = {"old24": ["old24"], "new24": ["new24"], "combined48": ["old24", "new24"], "combined96": ["old24", "new24", "focus48"]}
    results = []
    reference = saved[saved.metric.eq("V_floor")].set_index(["pool_id", "k", "cohort"])
    for (pid, k), g in targets.groupby(["pool_id", "k"]):
        for cohort, batches in cohorts.items():
            if (pid, k, cohort) not in reference.index:
                continue
            own = g[g.batch.isin(batches)]
            value, se, valid = v_from_polygons(own.team_key.tolist(), polygons)
            ref = reference.loc[(pid, k, cohort)]
            np.testing.assert_allclose([value, se], [ref["mean"], ref.mcse], atol=2e-12, equal_nan=True)
            assert valid == ref.valid_paths and len(own) == ref.attempted_paths
            results.append(dict(pool_id=pid, k=k, cohort=cohort, paths=len(own), unique_teams=own.team_key.nunique(), valid=valid, V=value, MCSE=se, author_V=ref["mean"], author_MCSE=ref.mcse))
    pd.DataFrame(results).to_csv(OUT / "V_RAW_GEOMETRY_CHECKS.csv", index=False)
    exact_refs = pd.read_csv(BASE / "analysis_geometry/results/EXACT_GEOMETRY_MARGINALS.csv")
    exact_results=[]
    for (pid,k), g in ee.groupby(["pool_id","k"]):
        value,se,q=v_from_polygons(g.team_key.tolist(),polygons,exact=True)
        ref=exact_refs[exact_refs.pool_id.eq(pid)&exact_refs.k.eq(k)&exact_refs.metric.eq("V_floor")].iloc[0]
        np.testing.assert_allclose(value,ref["exact_mean"],atol=2e-12,equal_nan=True)
        exact_results.append(dict(pool_id=pid,k=k,catalog_teams=len(g),valid=q,V=value))
    pd.DataFrame(exact_results).to_csv(OUT / "V_EXACT_GEOMETRY_CHECKS.csv",index=False)
    return dict(pools=len(selected),unique_endpoint_geometries=len(keys),path_metric_checks=len(results),exact_metric_checks=len(exact_results),max_abs_V_error=float(pd.DataFrame(results).eval('V-author_V').abs().max()))


def main():
    self_check()
    OUT.mkdir(parents=True, exist_ok=True)
    links = natural_links()
    exact = pd.read_csv(BASE / "new_endpoints/EXACT_MARGINAL_VALUES.csv.gz", low_memory=False)
    saved = pd.read_csv(BASE / "analysis_geometry/results/GEOMETRY_PATH_PRECISION.csv.gz")
    cases = case_audits(exact, links)
    aggregates = aggregate_v(saved)
    print("Cases and building summaries passed; reading representative original geometries", flush=True)
    geometry = raw_geometry_checks(exact, links, saved)
    receipt = dict(cases=cases,geometry=geometry,aggregates=aggregates,
                   boundary="No fusion/scoring replay; no all-pair geometry replay; only three packaged native states checked; P03 not downloaded")
    (OUT / "AUDIT_RESULTS.json").write_text(json.dumps(receipt,ensure_ascii=False,indent=2,allow_nan=False)+"\n",encoding="utf-8")
    print(json.dumps(receipt,ensure_ascii=False))


if __name__ == "__main__":
    main()
