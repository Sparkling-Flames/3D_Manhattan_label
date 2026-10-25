"""独立核对新增随机顺序、真实成员、端点和精确边际；不重跑融合。"""
from __future__ import annotations

import gzip
import hashlib
import itertools
import json
import math
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
BASE = ROOT / "research/workers/personnel_population_curves_v2_20261023"
NEW = BASE / "sampling_precision_20261025"
OUT = NEW / "local_audit/design"


def read(path, columns=None):
    return pd.read_csv(path, usecols=columns, dtype={"seed": str, "master_seed": str}, low_memory=False)


def team_key(pool_id, workers):
    # Hashing here reconstructs the scientific identity key, not a file checksum.
    b = json.dumps(sorted(workers), sort_keys=True, separators=(",", ":")).encode()
    return pool_id + "__" + hashlib.sha256(b).hexdigest()[:20]


def seed_for(pool_id, index):
    b = json.dumps(["population_precision_20261025", 2026102501, pool_id, int(index)], separators=(",", ":")).encode()
    return int.from_bytes(hashlib.sha256(b).digest()[:8], "little")


def numeric_equal(left, right, name):
    a, b = np.asarray(left, float), np.asarray(right, float)
    assert np.allclose(a, b, rtol=1e-12, atol=1e-8, equal_nan=True), name


def compare_rows(left, right, strings, numbers):
    for c in strings:
        assert left[c].fillna("").astype(str).tolist() == right[c].fillna("").astype(str).tolist(), c
    for c in numbers:
        numeric_equal(left[c], right[c], c)


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    OUT.mkdir(parents=True, exist_ok=True)
    report = {"audit_date": "2026-10-25", "data_release": "v2", "file_hashes_recomputed": False}
    compatibility = json.loads((NEW / "engine/FROZEN_SOURCE_COMPATIBILITY.json").read_text(encoding="utf-8"))
    source_paths = [r["path"] for r in compatibility["checked_core_sources"]]
    for path in source_paths:
        assert (ROOT/path).read_bytes() == (NEW/"engine/frozen_repo"/path).read_bytes(), path
    report["core_source_files_byte_compared"] = source_paths
    with gzip.open(BASE / "inputs/INPUT_SNAPSHOT.json.gz", "rt", encoding="utf-8-sig") as f:
        snap = json.load(f)
    frozen_snapshot = NEW / "engine/frozen_repo/research/workers/pro_personnel_v2_archive_20261019/work_v2_20261019/fusion/INPUT_SNAPSHOT.json.gz"
    with gzip.open(frozen_snapshot, "rt", encoding="utf-8-sig") as f:
        assert snap == json.load(f)
    report["native_input_snapshot_matches_original"] = True
    pools = {p["pool_id"]: p for p in snap["images"] if p["meta"]["layer"] in ("ordinary_manual", "doorway_manual")}
    members = {pid: {r["worker_id"]: r["object_id"] for r in p["records"]} for pid, p in pools.items()}
    assert len(pools) == 194
    plan = read(NEW / "design/POOL_SAMPLING_PLAN.csv").set_index("pool_id")
    assert set(plan.index) == set(pools)

    # Rebuild the focus list only from the saved old24 precision inputs.
    diag = read(NEW / "analysis_precision/old_diagnostics/OLD_PATH_POOL_K_PRECISION.csv.gz")
    d = diag[diag.pool_id.isin(pools) & diag.k.between(3, 20) & diag.k.lt(diag.pool_n)]
    original = read(BASE / "stability_rebuilt_20261023/inputs/PREFIX_VALUES_COMPACT.csv.gz", ["pool_id", "policy", "k", "B8L2"])
    original = original[original.pool_id.isin(pools) & original.policy.eq("natural_random")]
    moments = original.groupby(["pool_id", "k"]).B8L2.agg(["std", "count"])
    mcse = moments["std"]/np.sqrt(moments["count"])
    numeric_equal(d.Q_mean_MCSE, mcse.loc[list(zip(d.pool_id, d.k))], "old24 precision from original prefixes")
    report["focus_precision_input_recomputed_cells"] = len(d)
    focus = d.groupby("pool_id").Q_mean_MCSE.agg(lambda x: np.sqrt((x*x).mean())).rename("rms").to_frame()
    focus = focus.join(plan[["layer", "difficulty", "pool_n"]]).sort_values(["layer", "difficulty", "rms", "pool_id"], ascending=[True, True, False, True])
    eligible = focus[focus.pool_n.gt(10)].copy()
    eligible["rank"] = eligible.groupby(["layer", "difficulty"]).cumcount()+1
    selected = set(eligible[eligible.layer.eq("ordinary_manual") & eligible["rank"].le(12)].index) | set(focus[focus.layer.eq("doorway_manual")].index)
    stored = read(NEW / "analysis_precision/FOCUS_PRESELECTION_OLD24_RMS.csv").set_index("pool_id")
    assert selected == set(stored[stored.focus_selected].index) == set(plan[plan.focus_selected].index)
    numeric_equal(focus.rms, stored.loc[focus.index].old_MCSE_rms_k3to20, "old24 RMS focus")
    report["focus_pools_rebuilt_from_old24"] = len(selected)

    orders = read(NEW / "design/NEW_EXACT_ORDER_DESIGN.csv.gz").set_index("path_id", verify_integrity=True)
    old_orders = read(BASE / "design/EXACT_ORDER_DESIGN.csv.gz")
    old_roles = old_orders[old_orders.policy.ne("natural_random")].drop_duplicates(["pool_id", "policy"]).set_index(["pool_id", "policy"])
    order_arrays, seeds = {}, []
    for pid, group in orders.groupby("pool_id"):
        ws = sorted(members[pid]); n = len(ws)
        assert n == int(plan.loc[pid, "pool_n"])
        nat = group[group.policy.eq("natural_random")]
        expected_new = 72 if pid in selected else 24
        assert len(nat) == expected_new and set(nat.new_index) == set(range(expected_new))
        for path, r in group.iterrows():
            actual = r.worker_order.split("|")
            assert actual == r.workers.split("|") and sorted(actual) == ws
            seed = seed_for(pid, r.new_index)
            assert str(seed) == r.seed and str(r.master_seed) == "2026102501"
            base = np.random.default_rng(seed).permutation(ws).tolist()
            assert base == r.base_worker_order.split("|")
            if r.policy == "natural_random":
                assert base == actual
                assert r.batch == ("balanced_new24" if r.new_index < 24 else "focus_new48")
                assert np.isclose(r.sampling_weight_new_batch, 1/(24 if r.new_index < 24 else 48))
                seeds.append(seed)
            else:
                prior = old_roles.loc[(pid, r.policy)]
                for col in ("target_members", "target_class", "method", "tier", "heldout_building"):
                    assert str(r[col]) == str(prior[col]), (pid, col)
                target = set(r.target_members.split("|"))
                assert actual == [w for w in base if w in target]+[w for w in base if w not in target]
                assert r.new_index < 8 and r.batch == "policy_new8"
            order_arrays[path] = actual
    assert len(seeds) == len(set(seeds)) == 7200
    report["orders_rebuilt_from_seed"] = len(orders)
    report["natural_orders"] = len(seeds)
    report["policy_orders"] = int(orders.policy.ne("natural_random").sum())

    dep = read(NEW / "design/ENDPOINT_DEPENDENCIES.csv.gz").set_index("team_key", verify_integrity=True)
    for key, r in dep.iterrows():
        ws = r.member_workers.split("|"); own = members[r.pool_id]
        assert ws == sorted(set(ws)) and len(ws) == r.k == r.n
        assert set(ws) <= own.keys() and r.member_object_ids.split("|") == [own[w] for w in ws]
        assert team_key(r.pool_id, ws) == key
        for c in ("reference_id", "reference_version", "image_id", "condition", "layer", "pool_n"):
            assert str(r[c]) == str(pools[r.pool_id]["meta"][c]), (key, c)
    links = read(NEW / "design/NEW_PREFIX_TEAM_LINKS.csv.gz").set_index(["path_id", "k"], verify_integrity=True)
    natural_keys, policy_keys = set(), set()
    for path, rows in links.groupby(level=0, sort=False):
        order = order_arrays[path]; row = orders.loc[path]; target = set(str(row.target_members).split("|"))
        assert set(rows.index.get_level_values("k")) == set(range(1, len(order)+1))
        for (_, k), r in rows.iterrows():
            assert team_key(r.pool_id, order[:k]) == r.team_key
            assert r.entrant_worker == order[k-1]
            assert r.base_path_id == row.base_path_id and r.policy == row.policy and r.seed == row.seed
            assert r.target_present_n == sum(w in target for w in order[:k])
            (natural_keys if r.policy == "natural_random" else policy_keys).add(r.team_key)
    assert set(links.index.get_level_values(0)) == set(orders.index)

    exact = read(NEW / "design/EXACT_MARGINAL_TEAM_DESIGN.csv.gz")
    assert not exact.duplicated(["pool_id", "k", "team_key"]).any()
    for (pid, k), g in exact.groupby(["pool_id", "k"]):
        ws = sorted(members[pid]); expected = {team_key(pid, a) for a in itertools.combinations(ws, int(k))}
        assert set(g.team_key) == expected
        assert (g.finite_team_space.astype(int) == math.comb(len(ws), k)).all()
        assert np.allclose(g.marginal_weight, 1/len(expected)) and np.isclose(g.marginal_weight.sum(), 1)
    for pid, g in exact.groupby("pool_id"):
        n = len(members[pid]); assert set(g.k) == (set(range(1,n+1)) if n<=10 else {1,n-1,n})
    exact_keys = set(exact.team_key)
    assert natural_keys | policy_keys | exact_keys == set(dep.index)
    for col, keys in (("requested_natural", natural_keys), ("requested_policy", policy_keys), ("requested_exact", exact_keys)):
        assert set(dep[dep[col]].index) == keys
    report.update(prefix_links=len(links), exact_catalog_rows=len(exact), unique_registered_teams=len(dep), duplicate_path_visits=len(links)-links.team_key.nunique(), source_counts=dep.endpoint_source.value_counts().to_dict())

    identity = ["pool_id", "member_workers", "member_object_ids", "reference_id", "reference_version", "image_id", "condition", "layer"]
    state = ["score_available", "score_failure_nonpolicy", "policy_deferred", "complete_evaluable", "geometry_status", "score_status"]
    numeric = ["k", "pool_n", "B8L2", "D10", "iou_2d", "S_bottom_deg", "dir", "Hmean", "Hcenter", "nodes"]
    cols = ["team_key"]+identity+state+numeric
    scalar_parts = list((NEW / "new_endpoints/table_shards/NEW_ENDPOINT_SCALARS").glob("part_*.csv.gz"))
    new_scalar = pd.concat([read(p, cols) for p in sorted(scalar_parts)], ignore_index=True).set_index("team_key", verify_integrity=True)
    requests = read(NEW / "design/NEW_NATIVE_ENDPOINT_REQUESTS.csv.gz").set_index("team_key", verify_integrity=True)
    expected_new = set(dep[dep.endpoint_source.ne("inherited_population_20261023")].index)
    assert set(new_scalar.index) == expected_new
    assert set(requests.index) == set(dep[dep.endpoint_source.eq("new_native_required_20261025")].index)
    compare_rows(requests, dep.loc[requests.index], identity, ["k", "pool_n"])
    inherited = read(BASE / "results/ENDPOINT_SCALARS.csv.gz", cols).set_index("team_key", verify_integrity=True)
    old_keys = set(dep[dep.endpoint_source.eq("inherited_population_20261023")].index)
    assert old_keys <= set(inherited.index)
    all_scalar = pd.concat([inherited.loc[sorted(old_keys)], new_scalar], verify_integrity=True)
    assert set(all_scalar.index) == set(dep.index)
    compare_rows(all_scalar, dep.loc[all_scalar.index], identity, ["k", "pool_n"])
    bench = read(NEW / "engine/benchmark/ENDPOINT_SCALARS.csv.gz", cols).set_index("team_key", verify_integrity=True)
    bench_keys = dep[dep.endpoint_source.eq("reused_new_benchmark_20261025")].index
    compare_rows(all_scalar.loc[bench_keys], bench.loc[bench_keys], identity+state, numeric)
    assert (dep[dep.k.eq(dep.pool_n)].endpoint_source == "inherited_population_20261023").all()
    assert new_scalar.policy_deferred.eq(new_scalar.k.eq(2)).all()
    assert new_scalar.score_available.eq(new_scalar.B8L2.notna()).all()
    assert new_scalar.score_failure_nonpolicy.eq(~new_scalar.policy_deferred & ~new_scalar.score_available).all()
    good = new_scalar[new_scalar.score_available]
    floor = 1/good.iou_2d - 1 + good.S_bottom_deg**2/32
    height = (good.Hmean/.8)**2+(good.Hcenter/.25)**2
    residuals = {}
    for score, scale in (("B8L2",8),("D10",10)):
        direction = 1.5*good.dir**2/(good.dir**2+scale**2)
        pred = np.where(good.iou_2d>0, 100/(1+np.sqrt(floor**2+direction**2)+height), 0)
        numeric_equal(pred, good[score], score+" frozen formula")
        residuals[score] = float(np.max(np.abs(pred-good[score])))
    report.update(new_scalars=len(new_scalar), formal_new_requests=len(requests), scalar_states=new_scalar.score_status.value_counts().to_dict(), scored_scalar_formula_max_abs_error=residuals)
    seen = set()
    prefix_files = sorted((NEW / "new_endpoints/table_shards/NEW_PREFIX_VALUES_COMPACT").glob("part_*.csv.gz"))
    for p in prefix_files:
        pref = read(p, ["path_id", "team_key"]+identity+state+numeric).set_index(["path_id", "k"], verify_integrity=True)
        assert not (seen & set(pref.index)); seen.update(pref.index)
        assert pref.team_key.tolist() == links.loc[pref.index].team_key.tolist()
        target = all_scalar.loc[pref.team_key].reset_index()
        compare_rows(pref.reset_index(), target, identity+state, numeric)
    assert seen == set(links.index)
    vals = read(NEW / "new_endpoints/EXACT_MARGINAL_VALUES.csv.gz")
    assert set(zip(vals.pool_id, vals.k, vals.team_key)) == set(zip(exact.pool_id, exact.k, exact.team_key))
    assert not vals.duplicated(["pool_id", "k", "team_key"]).any()
    compare_rows(vals, all_scalar.loc[vals.team_key].reset_index(), identity+state, numeric)
    report["prefix_and_exact_scalar_bindings_passed"] = True
    report["limits"] = ["未重跑原生融合或原答几何评分。", "P03完整状态未下载；本审查验证标量、成员与前缀，不认证全部票账。", "种子与抽样规则可重建，预选名单只依赖旧24精度；静态文件不能独立证明实际执行时间先后。", "未重算文件SHA；身份键/随机种子算法中的SHA仅用于复现既有科学定义。"]
    (OUT/"DESIGN_ENDPOINT_AUDIT.json").write_text(json.dumps(report, ensure_ascii=False, indent=2)+"\n", encoding="utf-8")
    (OUT/"README_ZH.md").write_text("# 抽样设计与端点关联独立核查\n\n本审查从冻结人员池和正式CSV/gzip重建关系，不采用作者回执代替检查。\n\n"+"\n".join(f"- {k}：{v}" for k,v in report.items() if k!='limits')+"\n\n"+"\n".join('- '+v for v in report['limits'])+"\n\n复算：`python -m tools.thesis_main.analysis.audit_population_precision_design_20261025`。\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
