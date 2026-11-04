"""从原前缀复核策略，并固定跨批次人数点及重抽图片权重。

作者原件不变；缺失Q不补零；只重聚合保存结果，不调用融合或评分。
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import warnings

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
BASE = ROOT / "research/workers/personnel_population_curves_v2_20261023"
SOURCE = BASE / "sampling_precision_20261025"
POLICIES = ["joint_highq_first", "structure_moreturn_first", "joint_fast_first", "structure_dominant_first"]
PHASES = ["early_3_to_half", "low_3_to_6", "late_20_to_Nminus1", "full"]
META = ["pool_id", "image", "building", "condition", "layer", "difficulty", "pool_n"]
COMPONENTS = ["B8_floor_block", "B8_direction_block", "B8_height_block", "iou_2d", "S_bottom_deg", "dir", "Hmean"]
FIELDS = ["B8L2", "D10", "score_failure_nonpolicy", "incomplete_nonpolicy", "nodes", "floor_turn5_n", "source_time_total_seconds", "labor_kind_code"] + COMPONENTS
METRICS = ["paired_Q_delta", "paired_D10_delta", "Q_p10_delta_common", "Q_sd_delta_common_ddof1", "failure_delta", "incomplete_delta", "Q_loss_gt5_rate", "Q80_reached_delta", "Q90_reached_delta", "labor_ratio_legal", "QT_paired_Q_delta", "nodes_delta", "turn5_delta"] + [x + "_delta" for x in COMPONENTS]
BATCHES = ["old8", "new8", "combined16"]


def save(df, path):
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(path, index=False, compression={"method": "gzip", "mtime": 0} if path.suffix == ".gz" else None)


def mean_available(a, axis):
    count = np.isfinite(a).sum(axis=axis)
    return np.divide(np.nansum(a, axis=axis), count, out=np.full(count.shape, np.nan, dtype=float), where=count > 0)


def fixed_mean(a, mask, axis):
    """固定支持内只要一项不可估就保留缺失，不偷偷缩小支持。"""
    if not np.any(mask):
        shape = list(a.shape)
        del shape[axis]
        return np.full(shape, np.nan)
    return np.mean(np.take(a, np.flatnonzero(mask), axis=axis), axis=axis)


def common_k_mask(values):
    """values为batch×k×metric，输出跨批次共同可估的k×metric。"""
    return np.isfinite(values).all(axis=0)


def linear_p10(values):
    """沿path轴线性经验P10；向量化避免逐重抽的Python循环。"""
    ordered = np.sort(values, axis=1)
    count = np.isfinite(values).sum(axis=1)
    position = np.maximum(count - 1, 0) * .1
    lower = np.floor(position).astype(int)
    upper = np.ceil(position).astype(int)
    a = np.take_along_axis(ordered, lower[:, None, :], axis=1)[:, 0]
    b = np.take_along_axis(ordered, upper[:, None, :], axis=1)[:, 0]
    return np.where(count > 0, a + (b - a) * (position - lower), np.nan)


def labor_kind(value):
    if pd.isna(value):
        return ""
    s = str(value)
    if s.startswith("["):
        values = json.loads(s)
        return str(values[0]) if len(values) == 1 else ""
    return "" if "|" in s or "," in s else s


def load_prefixes():
    wanted = META + FIELDS[:-len(COMPONENTS)] + COMPONENTS + ["base_path_id", "path_id", "policy", "k", "team_key", "source_time_known_n", "time_source_kinds"]
    wanted = list(dict.fromkeys(wanted))
    old = pd.read_csv(BASE / "stability_rebuilt_20261023/inputs/PREFIX_VALUES_COMPACT.csv.gz", usecols=lambda c: c in wanted, low_memory=False)
    new = pd.concat([pd.read_csv(p, usecols=lambda c: c in wanted, low_memory=False) for p in sorted((SOURCE / "new_endpoints/table_shards/NEW_PREFIX_VALUES_COMPACT").glob("*.csv.gz"))], ignore_index=True)
    scalar_wanted = ["team_key", "time_source_kinds", "time_source_kinds_json"] + COMPONENTS
    scalar = pd.read_csv(BASE / "results/ENDPOINT_SCALARS.csv.gz", usecols=lambda c: c in scalar_wanted, low_memory=False)
    assert not scalar.team_key.duplicated().any()
    if "time_source_kinds_json" in scalar:
        scalar = scalar.rename(columns={"time_source_kinds_json": "time_source_kinds"})
    old = old.merge(scalar[[c for c in scalar if c == "team_key" or c not in old]], on="team_key", how="left", validate="many_to_one")
    for batch, frame in [("old8", old), ("new8", new)]:
        frame["batch"] = batch
        frame["labor_kind"] = frame.time_source_kinds.map(labor_kind)
        known = (frame.source_time_known_n == frame.k) & (frame.source_time_total_seconds > 0) & frame.labor_kind.ne("")
        frame.loc[~known, "source_time_total_seconds"] = np.nan
        for column in FIELDS:
            if column == "labor_kind_code":
                continue
            frame[column] = pd.to_numeric(frame[column], errors="raise")
    data = pd.concat([old, new], ignore_index=True)
    data["labor_kind_code"] = pd.Categorical(data.labor_kind).codes
    meta = old.loc[(old.layer == "ordinary_manual") & (old.pool_n >= 20), META].drop_duplicates("pool_id")
    common = set(meta.pool_id)
    for policy in POLICIES:
        common &= set(old.loc[old.policy == policy, "pool_id"]) & set(new.loc[new.policy == policy, "pool_id"])
    meta = meta[meta.pool_id.isin(common)].sort_values("pool_id").reset_index(drop=True)
    assert len(meta) == 157 and meta.building.nunique() == 22
    return data[data.pool_id.isin(common)], meta


def matrices(frame, bases, ks):
    frame = frame[frame.base_path_id.isin(bases)]
    assert not frame.duplicated(["base_path_id", "k"]).any()
    assert len(frame) == len(bases) * len(ks)
    return {c: frame.pivot(index="base_path_id", columns="k", values=c).reindex(index=bases, columns=ks).to_numpy(float) for c in FIELDS}


def statistics(n, p):
    """replicate×path×k输入；各k的共同可评、失败和劳动支持分别计算。"""
    valid = np.isfinite(n["B8L2"]) & np.isfinite(p["B8L2"])
    nq = np.where(valid, n["B8L2"], np.nan)
    pq = np.where(valid, p["B8L2"], np.nan)
    delta = pq - nq
    time = (n["source_time_total_seconds"] > 0) & (p["source_time_total_seconds"] > 0) & (n["labor_kind_code"] == p["labor_kind_code"])
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)
        p10 = linear_p10(pq) - linear_p10(nq)
        sd = np.nanstd(pq, axis=1, ddof=1) - np.nanstd(nq, axis=1, ddof=1)
    ratio = np.divide(p["source_time_total_seconds"], n["source_time_total_seconds"], out=np.full_like(delta, np.nan), where=time)
    out = [mean_available(delta, 1), mean_available(np.where(valid, p["D10"] - n["D10"], np.nan), 1), p10, sd,
           np.mean(p["score_failure_nonpolicy"] - n["score_failure_nonpolicy"], axis=1),
           np.mean(p["incomplete_nonpolicy"] - n["incomplete_nonpolicy"], axis=1),
           mean_available(np.where(valid, delta < -5, np.nan), 1),
           np.mean((p["B8L2"] >= 80).astype(float) - (n["B8L2"] >= 80), axis=1),
           np.mean((p["B8L2"] >= 90).astype(float) - (n["B8L2"] >= 90), axis=1),
           mean_available(np.where(valid, ratio, np.nan), 1), mean_available(np.where(time, delta, np.nan), 1),
           mean_available(p["nodes"] - n["nodes"], 1), mean_available(p["floor_turn5_n"] - n["floor_turn5_n"], 1)]
    out += [mean_available(np.where(valid, p[c] - n[c], np.nan), 1) for c in COMPONENTS]
    return np.stack(out, axis=-1)


def phase_masks(ks, n):
    return [(ks >= 3) & (ks <= n // 2), (ks >= 3) & (ks <= min(6, n)), (ks >= 20) & (ks < n), ks == n]


def interval(draws):
    finite = draws[np.isfinite(draws)]
    return (np.nan, np.nan) if not len(finite) else tuple(np.quantile(finite, [.025, .975]))


def aggregate(points, boots, meta, batch, policy, rng, replicates):
    rows = []
    for difficulty, group in [("全部", meta)] + list(meta.groupby("difficulty")):
        ids = group.index.to_numpy()
        for phase_i, phase in enumerate(PHASES):
            for metric_i, metric in enumerate(METRICS):
                values = points[ids, phase_i, metric_i]
                eligible = np.isfinite(values)
                positions = ids[eligible]
                values = values[eligible]
                if not len(values):
                    continue
                draws = boots[positions, :, phase_i, metric_i]
                buildings = meta.loc[positions, "building"].to_numpy()
                unique = np.unique(buildings)
                b_values = np.array([np.mean(values[buildings == b]) for b in unique])
                b_draws = np.array([np.mean(draws[buildings == b], axis=0) for b in unique])
                weights = rng.multinomial(len(unique), np.repeat(1 / len(unique), len(unique)), size=replicates)
                sizes = np.array([(buildings == b).sum() for b in unique])
                sums = b_values * sizes
                image_bd = (weights @ sums) / (weights @ sizes)
                building_bd = (weights @ b_values) / len(unique)
                for weighting, estimate, pdra, bdra in [
                    ("image_equal", values.mean(), np.mean(draws, axis=0), image_bd),
                    ("building_equal", b_values.mean(), np.mean(b_draws, axis=0), building_bd),
                ]:
                    plo, phi = interval(pdra); blo, bhi = interval(bdra)
                    rows.append(dict(batch=batch, policy=policy, difficulty=difficulty, phase=phase, metric=metric,
                        weighting=weighting, estimate=estimate, images=len(values), candidate_images=len(group), buildings=len(unique),
                        positive_images=int((values > 1e-9).sum()), negative_images=int((values < -1e-9).sum()),
                        nearzero_images=int((abs(values) <= 1e-9).sum()), path_lo=plo, path_hi=phi,
                        path_valid_replicates=int(np.isfinite(pdra).sum()), path_invalid_replicates=int((~np.isfinite(pdra)).sum()),
                        path_interval_status=("unavailable" if not np.isfinite(pdra).any() else "conditional_on_estimable_draws" if not np.isfinite(pdra).all() else "complete_support_all_draws"),
                        building_lo=blo, building_hi=bhi, bootstrap_replicates=replicates))
    return rows


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--replicates", type=int, default=1000); ap.add_argument("--seed", type=int, default=2026102521)
    ap.add_argument("--out", type=Path, default=SOURCE / "local_audit/policy"); args = ap.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    data, meta = load_prefixes()
    print("loaded", len(data), "prefixes; common", len(meta), "images", flush=True)
    original_k = pd.read_csv(SOURCE / "analysis_policy/results/POLICY_IMAGE_K_COMPARISON.csv.gz")
    original_phase = pd.read_csv(SOURCE / "analysis_policy/results/POLICY_IMAGE_PHASE_COMPARISON.csv")
    indexed_original = original_k.set_index(["pool_id", "policy", "batch", "k"]).sort_index()
    support_rows = []; phase_rows = []; krows = []; summaries = []; diagnostics = []; event_parts = []
    for pi, policy in enumerate(POLICIES):
        point = {b: np.full((len(meta), len(PHASES), len(METRICS)), np.nan) for b in BATCHES}
        boot = {b: np.full((len(meta), args.replicates, len(PHASES), len(METRICS)), np.nan, dtype=np.float32) for b in BATCHES}
        for ix, row in meta.iterrows():
            g = data[data.pool_id == row.pool_id]; ks = np.arange(1, int(row.pool_n) + 1)
            nm = {}; pm = {}; vals = {}; base_lists = {}
            for batch in BATCHES:
                use = g if batch == "combined16" else g[g.batch == batch]
                bases = sorted(set.intersection(*[set(use.loc[use.policy == p, "base_path_id"]) for p in POLICIES]))
                assert len(bases) == (16 if batch == "combined16" else 8)
                n = matrices(use[use.policy == "natural_random"], bases, ks)
                p = matrices(use[use.policy == policy], bases, ks)
                nm[batch] = n; pm[batch] = p; base_lists[batch] = bases
                vals[batch] = statistics({c: a[None] for c, a in n.items()}, {c: a[None] for c, a in p.items()})[0]
                authored = indexed_original.loc[(row.pool_id, policy, batch)].reindex(ks)[METRICS].to_numpy(float)
                assert np.array_equal(np.isfinite(vals[batch]), np.isfinite(authored)), (row.pool_id, policy, batch, "nan mismatch")
                error = np.nanmax(abs(vals[batch] - authored))
                assert error < 1e-8, (row.pool_id, policy, batch, error)
                if batch != "combined16":
                    fields = ["pool_id", "base_path_id", "k", "team_key", "B8L2", "D10", "score_failure_nonpolicy", "incomplete_nonpolicy", "source_time_total_seconds", "labor_kind"]
                    ng = use[(use.policy == "natural_random") & use.base_path_id.isin(bases)]
                    pg = use[(use.policy == policy) & use.base_path_id.isin(bases)]
                    event = ng[fields].merge(pg[fields], on=["pool_id", "base_path_id", "k"], suffixes=("_natural", "_policy"), validate="one_to_one")
                    event.insert(0, "batch", batch); event.insert(1, "policy", policy); event_parts.append(event)
            common = common_k_mask(np.stack([vals[b] for b in BATCHES]))
            phases = phase_masks(ks, int(row.pool_n))
            for batch_i, batch in enumerate(BATCHES):
                n = nm[batch]; p = pm[batch]; v = vals[batch]
                rng = np.random.default_rng(np.random.SeedSequence([args.seed, ix, batch_i]))
                draws = rng.integers(len(base_lists[batch]), size=(args.replicates, len(base_lists[batch])))
                z = statistics({c: a[draws] for c, a in n.items()}, {c: a[draws] for c, a in p.items()})
                good = np.isfinite(n["B8L2"]) & np.isfinite(p["B8L2"])
                qt = good & (n["source_time_total_seconds"] > 0) & (p["source_time_total_seconds"] > 0) & (n["labor_kind_code"] == p["labor_kind_code"])
                for j, phase in enumerate(PHASES):
                    for c, metric in enumerate(METRICS):
                        keep = common[:, c] & phases[j]
                        point[batch][ix, j, c] = fixed_mean(v[:, c], keep, 0)
                        boot[batch][ix, :, j, c] = fixed_mean(z[:, :, c], keep, 1)
                        support_rows.append(dict(pool_id=row.pool_id, image=row.image, policy=policy, phase=phase, metric=metric, batch=batch,
                            candidate_k=int(phases[j].sum()), original_valid_k=int(np.isfinite(v[phases[j], c]).sum()),
                            fixed_k=int(keep.sum()), fixed_k_list="|".join(map(str, ks[keep])),
                            point=point[batch][ix, j, c], valid_bootstraps=int(np.isfinite(boot[batch][ix, :, j, c]).sum()),
                            invalid_bootstraps=int((~np.isfinite(boot[batch][ix, :, j, c])).sum())))
                    phase_rows.append(dict(**row.to_dict(), batch=batch, policy=policy, phase=phase, base_paths=len(base_lists[batch]),
                        attempted_prefixes=int(len(base_lists[batch]) * phases[j].sum()),
                        both_Q_prefixes=int(good[:, phases[j]].sum()), legal_QT_prefixes=int(qt[:, phases[j]].sum()),
                        fixed_Q_k=int((common[:, 0] & phases[j]).sum()), **dict(zip(METRICS, point[batch][ix, j]))))
                for j, k in enumerate(ks):
                    krows.append(dict(**row.to_dict(), batch=batch, policy=policy, k=int(k), base_paths=len(base_lists[batch]),
                        both_Q_paths=int(good[:, j].sum()), legal_QT_paths=int(qt[:, j].sum()), **dict(zip(METRICS, v[j]))))
            if ix % 50 == 0:
                print(policy, ix + 1, "/", len(meta), flush=True)
        for bi, batch in enumerate(BATCHES):
            summaries.extend(aggregate(point[batch], boot[batch], meta, batch, policy, np.random.default_rng(np.random.SeedSequence([args.seed, 1000, pi, bi])), args.replicates))
    image = pd.DataFrame(phase_rows)
    compared = image.merge(original_phase[["pool_id", "batch", "policy", "phase"] + METRICS], on=["pool_id", "batch", "policy", "phase"], suffixes=("_fixed", "_author"), validate="one_to_one")
    for metric in METRICS:
        compared[metric + "_correction"] = compared[metric + "_fixed"] - compared[metric + "_author"]
    events = pd.concat(event_parts, ignore_index=True)
    author_events = pd.read_csv(SOURCE / "analysis_policy/results/POLICY_COMMON_PAIRED_EVENTS.csv.gz")
    keys = ["pool_id", "batch", "policy", "base_path_id", "k"]
    actual = events.sort_values(keys).reset_index(drop=True); expected = author_events.sort_values(keys).reset_index(drop=True)
    pd.testing.assert_frame_equal(actual[expected.columns].fillna("").astype(str)[keys + ["team_key_natural", "team_key_policy"]], expected.fillna("").astype(str)[keys + ["team_key_natural", "team_key_policy"]])
    for col in ["B8L2_natural", "B8L2_policy", "D10_natural", "D10_policy", "source_time_total_seconds_natural", "source_time_total_seconds_policy"]:
        np.testing.assert_allclose(actual[col], expected[col], rtol=1e-12, atol=1e-9, equal_nan=True)
    save(meta, args.out / "COMMON_IMAGES.csv")
    save(pd.DataFrame(support_rows), args.out / "FIXED_K_SUPPORT.csv.gz")
    save(image, args.out / "POLICY_IMAGE_PHASE_FIXED.csv")
    save(pd.DataFrame(krows), args.out / "POLICY_IMAGE_K_RECOMPUTED.csv.gz")
    save(compared, args.out / "AUTHOR_VS_FIXED_IMAGE_PHASE.csv")
    summary = pd.DataFrame(summaries)
    save(summary, args.out / "POLICY_PRECISION_FIXED_SUMMARY.csv")
    early = summary[(summary.phase == "early_3_to_half") & (summary.difficulty == "全部") & (summary.metric == "paired_Q_delta") & (summary.weighting == "image_equal")]
    save(early, args.out / "KEY_EARLY_Q_RESULTS.csv")
    receipt = dict(replicates=args.replicates, seed=args.seed, images=len(meta), buildings=int(meta.building.nunique()),
        exact_events_rebuilt=len(events), all_author_k_metrics_recomputed=True, fixed_support="per policy/image/phase/metric: k finite in old8,new8,combined16; no dropping k in bootstrap",
        aggregate="fixed eligible images and building membership; any missing image invalidates complete-panel path replicate; building bootstrap uses fixed point estimates",
        interval="pointwise empirical 2.5/97.5 percentiles; if some path draws cannot estimate all fixed k/images, the reported range is conditional on estimable draws, with counts disclosed",
        failure="all candidate phase k and all paired attempts, not quality-filtered", labor="single same semantic source, positive complete times, both Q scoreable for QT",
        original_files_changed=False, fusion_rerun=False, scoring_rerun=False)
    (args.out / "RECEIPT.json").write_text(json.dumps(receipt, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(early.to_string(index=False)); print(json.dumps(receipt, ensure_ascii=False))


if __name__ == "__main__":
    main()
