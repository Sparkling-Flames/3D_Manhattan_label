#!/usr/bin/env python3
"""Direct, shared-team comparison of 16 frozen forward ablation partitions.

No target-dependent refitting. Pair outcomes are calculated once and shared by
every partition; size-preserving random labels require no new fusion. Per-core
and per-directed-count-vector evidence is retained, not only a global average.
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
import sys
import time
from pathlib import Path
for key in ("OPENBLAS_NUM_THREADS", "OMP_NUM_THREADS", "MKL_NUM_THREADS"):
    os.environ[key] = "1"
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "analysis/composition"))
import summarize_grid as old

METRICS = ["joint_stable_strict", "joint_stable_main", "joint_stable_wide",
           "geometry_noQ_strict", "geometry_noQ_main", "geometry_noQ_wide",
           "floor_jaccard_difference", "structure_bound_cyclic_deg", "node_count_difference",
           "abs_B8L2_change", "abs_D10_change", "B8L2_change", "D10_change",
           "neighbor_B8L2", "neighbor_D10", "neighbor_complete", "neighbor_score_missing",
           "pair_incomplete", "quality_drop_gt5", "quality_gain_gt5", "node_count_change",
           "mean_height_prism_pair_iou", "ref_node_set_jaccard_difference_9", "ref_edge_set_jaccard_difference_9",
           "source_block_seconds_change", "source_block_log_ratio",
           "target_block_seconds_change", "target_block_log_ratio"]
SPEC_METRICS = ["joint_stable_main", "geometry_noQ_main", "floor_jaccard_difference", "structure_bound_cyclic_deg",
                "node_count_difference", "B8L2_change", "D10_change", "abs_B8L2_change", "neighbor_B8L2",
                "neighbor_complete", "quality_drop_gt5", "mean_height_prism_pair_iou", "source_block_log_ratio"]
MIDX = {m: i for i, m in enumerate(METRICS)}
STABLE = {m for m in METRICS if "stable" in m or m.startswith("geometry_noQ")}
# The first completed calculation used pandas' streaming gzip writer. Two
# compressed CSVs lacked an end marker despite a successful return. Numerical
# functions did not change; accept only CRC-checked parts from that exact code.
IO_COMPATIBLE_PART_SCRIPT_SHA256 = {"912aae0d06cba39127c7716eea38e4c8540d8d9365ce531a5db7ce77aac3afef"}


def read(path):
    with (gzip.open(path, "rt") if str(path).endswith(".gz") else open(path)) as f:
        return json.load(f)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write_json(path, value):
    def default(v):
        if isinstance(v, np.generic):
            return v.item()
        raise TypeError(type(v).__name__)
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False, default=default))


def write_csv(path, frame):
    path = Path(path)
    raw = frame.to_csv(index=False).encode()
    packed = gzip.compress(raw, compresslevel=6, mtime=0)
    assert gzip.decompress(packed) == raw
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_bytes(packed)
    assert tmp.stat().st_size == len(packed)
    assert gzip.decompress(tmp.read_bytes()) == raw
    tmp.replace(path)
    assert gzip.decompress(path.read_bytes()) == raw


def valid_csv_parts(parts, pid):
    try:
        for kind in ("core", "vectors", "random", "coverage"):
            path = parts / (pid + "." + kind + ".csv.gz")
            gzip.decompress(path.read_bytes())
        return True
    except (OSError, EOFError):
        return False


def finite(x):
    try:
        return x is not None and math.isfinite(float(x))
    except (TypeError, ValueError):
        return False


def positive_block_time(records, workers, key):
    raw = [records[w].get(key) for w in workers]
    # New-batch target_time_seconds is null (known_n=0), not an observed redo
    # time. Preserve missing inputs; never manufacture an efficiency estimate.
    return sum(float(x) for x in raw) if all(finite(x) and float(x) > 0 for x in raw) else np.nan


def canonical(counts, classes):
    return "|".join(f"{c}:{int(n)}" for c, n in zip(classes, counts))


def primitive(a, b, p, ta, tb, reverse=False):
    sign = -1 if reverse else 1
    neighbor = a if reverse else b
    out = {m: p.get(m) for m in METRICS}
    for m in ("B8L2_change", "D10_change", "node_count_change"):
        out[m] = sign * p[m] if finite(p.get(m)) else np.nan
    q = out["B8L2_change"]
    out.update(neighbor_B8L2=neighbor.get("B8L2"), neighbor_D10=neighbor.get("D10"),
               neighbor_complete=bool(neighbor.get("complete_evaluable")),
               neighbor_score_missing=not finite(neighbor.get("B8L2")), pair_incomplete=not p["both_complete"],
               quality_drop_gt5=(q < -5) if finite(q) else np.nan,
               quality_gain_gt5=(q > 5) if finite(q) else np.nan)
    for name, floor, angle in (("strict", .02, 2.), ("main", .05, 3.), ("wide", .1, 5.)):
        out[f"geometry_noQ_{name}"] = bool(p["both_complete"] and p["node_count_difference"] == 0 and
            finite(p["floor_jaccard_difference"]) and p["floor_jaccard_difference"] <= floor and
            finite(p["structure_bound_cyclic_deg"]) and p["structure_bound_cyclic_deg"] <= angle)
    for i, kind in enumerate(("source", "target")):
        x, y = ta[i], tb[i]
        out[f"{kind}_block_seconds_change"] = sign * (y - x) if finite(x) and finite(y) else np.nan
        out[f"{kind}_block_log_ratio"] = sign * math.log(y / x) if finite(x) and finite(y) and x > 0 and y > 0 else np.nan
    return np.array([float(out[m]) if finite(out[m]) else np.nan for m in METRICS])


def neighbor_means(values, mask):
    ok = mask[..., None] & np.isfinite(values)
    count = ok.sum(axis=1)
    total = np.where(ok, values, 0).sum(axis=1)
    return np.divide(total, count, out=np.full(total.shape, np.nan), where=count > 0)


def summarize(meta, values, wm, cm, eligible, metric_names=METRICS):
    bases = np.flatnonzero(eligible)
    if not len(bases):
        return None
    wmean, cmean = neighbor_means(values, wm), neighbor_means(values, cm)
    used = set(bases.tolist()) | set(np.flatnonzero(wm[bases].any(axis=0)).tolist()) | set(np.flatnonzero(cm[bases].any(axis=0)).tolist())
    row = dict(meta, eligible_A_n=len(bases), within_directed_pairs_n=int(wm[bases].sum()),
               cross_directed_pairs_n=int(cm[bases].sum()), used_block_n=len(used),
               base_block_indices=json.dumps(bases.tolist(), separators=(",", ":")),
               used_block_indices=json.dumps(sorted(used), separators=(",", ":")))
    for m in metric_names:
        i = MIDX[m]
        paired = eligible & np.isfinite(wmean[:, i]) & np.isfinite(cmean[:, i])
        n = int(paired.sum())
        x = float(wmean[paired, i].mean()) if n else np.nan
        y = float(cmean[paired, i].mean()) if n else np.nan
        row[f"within_{m}"] = x
        row[f"cross_{m}"] = y
        row[f"excess_{m}"] = y - x
        row[f"finite_paired_A_{m}"] = n
        if m in STABLE:
            row[f"gap_{m}"] = x - y
    return row


def analyze_pool(pid, anchors, pool, teams, labels, feature_methods, random_methods, features):
    records = {r["worker_id"]: r for r in pool["records"]}
    signatures = {}
    expected = {b["team_key"] for a in anchors for b in a["blocks"]}
    assert expected <= teams.keys(), "incomplete common-panel fusion cache"
    for tk in expected:
        row = teams[tk]
        assert row["pool_id"] == pid
        signatures[tk] = old.signature(row)
    core_rows, vector_rows, random_rows, eligibility_rows = [], [], [], []
    for anchor in anchors:
        blocks = anchor["blocks"]
        ts = [teams[b["team_key"]] for b in blocks]
        for block, t in zip(blocks, ts):
            assert sorted(t["member_workers"]) == sorted(anchor["core_workers"] + block["worker_ids"])
            assert t["k"] == anchor["n"]
        B = len(blocks)
        times = [[positive_block_time(records, b["worker_ids"], kind + "_time_seconds") for kind in ("source", "target")] for b in blocks]
        prior_q = np.array([np.mean([features.loc[w, "q_beta"] for w in b["worker_ids"]]) for b in blocks])
        values = np.full((B, B, len(METRICS)), np.nan)
        disjoint = np.zeros((B, B), bool)
        for i, j in anchor["disjoint_pair_indices"]:
            assert set(blocks[i]["worker_ids"]).isdisjoint(blocks[j]["worker_ids"])
            p = old.pair_metrics(ts[i], ts[j], signatures[blocks[i]["team_key"]], signatures[blocks[j]["team_key"]])
            assert p["turnover"] == 2
            values[i, j] = primitive(ts[i], ts[j], p, times[i], times[j])
            values[j, i] = primitive(ts[i], ts[j], p, times[i], times[j], reverse=True)
            disjoint[i, j] = disjoint[j, i] = True
        meta = {k: anchor[k] for k in ("anchor_id", "pool_id", "building", "image", "difficulty", "n", "m", "replicate")}
        meta.update(sampled_block_n=B, possible_blocks=anchor["possible_blocks"], exhaustive_blocks=anchor["exhaustive_blocks"],
                    available_people=len(anchor["available_workers"]))
        composition = {}
        for mid, mapping in labels.items():
            classes = sorted(set(mapping.values()))
            counts = np.array([[sum(mapping[w] == c for w in block["worker_ids"]) for c in classes] for block in blocks])
            strings = np.array([canonical(count, classes) for count in counts])
            composition[mid] = (strings, strings[:, None] == strings[None, :])
        for restriction, neighbor_ok in (("all", disjoint), ("history_A_Qclose3", disjoint & (np.abs(prior_q[:, None] - prior_q[None, :]) <= 3))):
            masks = {}
            for mid in labels:
                strings, same = composition[mid]
                wm, cm = neighbor_ok & same, neighbor_ok & ~same
                eligible = wm.any(axis=1) & cm.any(axis=1)
                masks[mid] = (wm, cm, eligible)
            common16 = np.logical_and.reduce([masks[mid][2] for mid in feature_methods])
            for mid in feature_methods:
                wm, cm, eligible = masks[mid]
                eligibility_rows.append(dict(meta, method_id=mid, restriction=restriction,
                                              native_eligible_A_n=int(eligible.sum()), common16_eligible_A_n=int(common16.sum()),
                                              native_without_within_A_n=int((~wm.any(axis=1)).sum()),
                                              native_without_cross_A_n=int((~cm.any(axis=1)).sum())))
                strings = composition[mid][0]
                for support, used_eligible in (("native", eligible), ("common16", common16)):
                    row = summarize(dict(meta, method_id=mid, support=support, restriction=restriction), values, wm, cm, used_eligible)
                    if row is not None:
                        core_rows.append(row)
                    if restriction != "all":
                        continue
                    for outvec, invec in itertools.permutations(sorted(set(strings)), 2):
                        directional_cm = cm & (strings[None, :] == invec)
                        directional_eligible = used_eligible & (strings == outvec) & directional_cm.any(axis=1)
                        drow = summarize(dict(meta, method_id=mid, support=support, restriction=restriction,
                                              outgoing_vector=outvec, incoming_vector=invec), values, wm, directional_cm,
                                         directional_eligible, SPEC_METRICS)
                        if drow is not None:
                            vector_rows.append(drow)
            for mid in random_methods:
                k = len(set(labels[mid].values()))
                fullmid = f"F20_newCommon_Full_balanced_K{k}"
                wm, cm, eligible = masks[mid]
                fw, fc, fe = masks[fullmid]
                paired = eligible & fe
                rrow = summarize(dict(meta, method_id=mid, full_method_id=fullmid, support="paired_fullK", restriction=restriction),
                                 values, wm, cm, paired)
                frow = summarize({}, values, fw, fc, paired)
                if rrow is None:
                    continue
                for m in METRICS:
                    for prefix in ("within_", "cross_", "excess_") + (("gap_",) if m in STABLE else ()):
                        col = prefix + m
                        rrow["full_" + col] = frow[col]
                        rrow["full_minus_random_" + col] = frow[col] - rrow[col]
                rrow["full_used_block_indices"] = frow["used_block_indices"]
                random_rows.append(rrow)
    return core_rows, vector_rows, random_rows, eligibility_rows


def aggregate_frame(df, anchors, prefix_keys, include_all_n=True):
    if df.empty:
        return pd.DataFrame(), pd.DataFrame(), pd.DataFrame()
    metric_cols = [c for c in df if c.startswith(("within_", "cross_", "excess_", "gap_", "full_within_", "full_cross_", "full_excess_", "full_gap_", "full_minus_random_")) and c not in ("within_directed_pairs_n", "cross_directed_pairs_n")]
    numeric = df[metric_cols].select_dtypes(include=["number"]).columns.tolist()
    phases = []
    for per_n in ([True, False] if include_all_n else [True]):
        by = prefix_keys + (["n"] if per_n else [])
        # First average the distinct metadata cores within pool/n. When n is
        # pooled, average the available n cells within a pool before buildings.
        pn = df.groupby(prefix_keys + ["building", "pool_id", "n"], dropna=False)[numeric].mean().reset_index()
        if per_n:
            images = pn
        else:
            images = pn.groupby(prefix_keys + ["building", "pool_id"], dropna=False)[numeric].mean().reset_index()
        buildings = images.groupby(by + ["building"], dropna=False)[numeric].mean().reset_index()
        overall = buildings.groupby(by, dropna=False)[numeric].mean().reset_index()
        supports = []
        for key, g in df.groupby(by, dropna=False):
            if not isinstance(key, tuple):
                key = (key,)
            d = dict(zip(by, key))
            used_teams, used_workers = set(), set()
            for r in g.itertuples():
                anchor = anchors[r.anchor_id]
                indices = set(json.loads(r.used_block_indices))
                if hasattr(r, "full_used_block_indices"):
                    indices |= set(json.loads(r.full_used_block_indices))
                for i in indices:
                    used_teams.add(anchor["blocks"][i]["team_key"])
                    used_workers.update(anchor["blocks"][i]["worker_ids"])
                used_workers.update(anchor["core_workers"])
            d.update(pools=g.pool_id.nunique(), buildings=g.building.nunique(), cores=g.anchor_id.nunique(),
                     eligible_A_observations=int(g.eligible_A_n.sum()), unique_teams=len(used_teams), unique_people=len(used_workers),
                     within_directed_pairs_observations=int(g.within_directed_pairs_n.sum()), cross_directed_pairs_observations=int(g.cross_directed_pairs_n.sum()))
            for m in ("joint_stable_main", "geometry_noQ_main", "floor_jaccard_difference", "structure_bound_cyclic_deg", "B8L2_change", "source_block_log_ratio", "target_block_log_ratio"):
                if "finite_paired_A_" + m not in g:
                    continue
                z = g.loc[g["finite_paired_A_" + m] > 0]
                d[f"finite_{m}_pools"] = z.pool_id.nunique()
                d[f"finite_{m}_buildings"] = z.building.nunique()
            supports.append(d)
        overall = overall.merge(pd.DataFrame(supports), on=by, validate="one_to_one")
        if not per_n:
            for table in (images, buildings, overall):
                table["n"] = "ALL"
        phases.append((images, buildings, overall))
    return tuple(pd.concat([item[i] for item in phases], ignore_index=True) for i in range(3))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--panel", type=Path, default=Path(__file__).resolve().parent)
    ap.add_argument("--snapshot", type=Path, default=ROOT / "repo/research/workers/pro_personnel_v2_archive_20261019/work_v2_20261019/fusion/INPUT_SNAPSHOT.json.gz")
    ap.add_argument("--labels", type=Path, default=Path(__file__).resolve().parent.parent / "worker_labels.csv.gz")
    ap.add_argument("--features", type=Path, default=Path(__file__).resolve().parent.parent / "features_train.csv.gz")
    ap.add_argument("--watch", action="store_true")
    a = ap.parse_args()
    reg = read(a.panel / "COMMON_PANEL_REGISTRATION.json")
    assert sha(a.labels) == reg["input_sha256"]["forward_labels"]
    assert sha(a.snapshot) == reg["input_sha256"]["snapshot"]
    assert sha(a.panel / "common_requests.json.gz") == reg["request_sha256"]
    assert sha(a.panel / "common_anchors.json.gz") == reg["anchor_sha256"]
    assert sha(a.panel / "random_labels.csv.gz") == reg["random_labels_sha256"]
    anchors = read(a.panel / "common_anchors.json.gz")["anchors"]
    anchor_map = {r["anchor_id"]: r for r in anchors}
    by_pool = collections.defaultdict(list)
    for row in anchors:
        assert row["building"] in reg["buildings"] and row["layer"] == "ordinary_manual"
        by_pool[row["pool_id"]].append(row)
    pools = {p["pool_id"]: p for p in read(a.snapshot)["images"] if p["pool_id"] in by_pool}
    table = pd.concat([pd.read_csv(a.labels), pd.read_csv(a.panel / "random_labels.csv.gz")], ignore_index=True)
    mids = reg["method_ids"] + reg["random_method_ids"]
    labels = {mid: dict(zip(g.worker_id, g.class_id)) for mid, g in table.loc[table.method_id.isin(mids) & table.known].groupby("method_id")}
    assert len(labels) == 56
    assert all(sorted(mapping) == reg["population"] for mapping in labels.values())
    features = pd.read_csv(a.features).set_index("worker_id")
    out = a.panel / "results"
    parts = out / "parts"
    parts.mkdir(parents=True, exist_ok=True)
    pending = set(by_pool)
    receipts = []
    t0 = time.monotonic()
    while pending:
        progressed = False
        for pid in sorted(pending):
            native = a.panel / "native/pools" / (pid + ".json.gz")
            if not native.exists():
                continue
            ready = parts / (pid + ".receipt.json")
            if ready.exists() and valid_csv_parts(parts, pid):
                receipt = read(ready)
                assert receipt["script_sha256"] in {sha(__file__)} | IO_COMPATIBLE_PART_SCRIPT_SHA256
                assert receipt["native_sha256"] == sha(native)
                assert receipt["request_sha256"] == reg["request_sha256"]
            else:
                teams = {t["team_key"]: t for t in read(native)["teams"]}
                core, vector, random, coverage = analyze_pool(pid, by_pool[pid], pools[pid], teams, labels, reg["method_ids"], reg["random_method_ids"], features)
                for name, rows in (("core", core), ("vectors", vector), ("random", random), ("coverage", coverage)):
                    frame = pd.DataFrame(rows) if rows else pd.DataFrame(columns=["anchor_id", "pool_id", "method_id"])
                    write_csv(parts / (pid + "." + name + ".csv.gz"), frame)
                receipt = dict(pool_id=pid, anchors=len(by_pool[pid]), core_rows=len(core), vector_rows=len(vector), random_rows=len(random),
                               script_sha256=sha(__file__), native_sha256=sha(native), request_sha256=reg["request_sha256"])
                write_json(ready, receipt)
            receipts.append(receipt)
            pending.remove(pid)
            progressed = True
            print(json.dumps(dict(pool_id=pid, completed_pools=len(receipts), total_pools=len(by_pool), elapsed=round(time.monotonic() - t0, 1))), flush=True)
        if pending:
            if not a.watch:
                raise RuntimeError(f"Native output missing for {len(pending)} pools; rerun --watch or after completion")
            if not progressed:
                time.sleep(10)
    frames = {}
    for name in ("core", "vectors", "random", "coverage"):
        frames[name] = pd.concat([pd.read_csv(parts / (pid + "." + name + ".csv.gz")) for pid in sorted(by_pool)], ignore_index=True)
        write_csv(out / (name + "_evidence.csv.gz"), frames[name])
    for kind, keys in (("core", ["method_id", "support", "restriction"]),
                       ("vectors", ["method_id", "support", "restriction", "outgoing_vector", "incoming_vector"]),
                       ("random", ["method_id", "full_method_id", "support", "restriction"])):
        images, buildings, aggregate = aggregate_frame(frames[kind], anchor_map, keys)
        for name, frame in (("per_image", images), ("per_building", buildings), ("aggregate", aggregate)):
            write_csv(out / (kind + "_" + name + ".csv.gz"), frame)
    write_json(out / "SUMMARY_RECEIPT.json", dict(schema="common_panel_actual_pair_summary_v1", registration_sha256=sha(a.panel / "COMMON_PANEL_REGISTRATION.json"),
               labels_sha256=sha(a.labels), features_sha256=sha(a.features), script_sha256=sha(__file__),
               requested_pools=len(by_pool), completed_pools=len(receipts), unique_teams=reg["unique_teams"],
               unordered_disjoint_pair_observations=reg["disjoint_pair_observations"], row_counts={k: len(v) for k, v in frames.items()},
               time_qualification="Source and target retained separately; positive observed block times required for cost/ratio. New target_time_seconds is null throughout (known_n=0); no observed target redo cost.",
               support="Finite metric denominators remain separate. Conditional cyclic angle excludes differing node counts; node change and noQ/joint failure remain reported. Repeated pairs are not independent samples.",
               compatible_io_only_previous_scripts=sorted(IO_COMPATIBLE_PART_SCRIPT_SHA256),
               by_pool=receipts, seconds=time.monotonic() - t0))


if __name__ == "__main__":
    main()
