#!/usr/bin/env python3
"""Compare eight registered partitions on the exact same native pair panel.

No new fusion or fitting. The original16 ablation results remain independent.
The numerical pair primitives and averaging hierarchy are reused unchanged.
"""
from pathlib import Path
import argparse
import collections
import itertools
import json
import math
import os
import time
for name in ("OPENBLAS_NUM_THREADS", "OMP_NUM_THREADS", "MKL_NUM_THREADS"):
    os.environ[name] = "1"
import numpy as np
import pandas as pd
import summarize_common_panel as base

HERE = Path(__file__).resolve().parent
ROOT = base.ROOT

def analyze_pool(pid, anchors, pool, teams, labels, features):
    records = {r["worker_id"]: r for r in pool["records"]}
    expected = {b["team_key"] for a in anchors for b in a["blocks"]}
    assert expected <= teams.keys()
    signatures = {tk: base.old.signature(teams[tk]) for tk in expected}
    rows, vectors, paired_rows, coverage = [], [], [], []
    benchmark_ids = [f"F20_newCommon_Full_balanced_K{k}" for k in (2, 3)]
    for anchor in anchors:
        blocks = anchor["blocks"]
        ts = [teams[b["team_key"]] for b in blocks]
        for block, team in zip(blocks, ts):
            assert sorted(team["member_workers"]) == sorted(anchor["core_workers"] + block["worker_ids"])
            assert team["k"] == anchor["n"] and team["pool_id"] == pid
        nblocks = len(blocks)
        times = [[base.positive_block_time(records, b["worker_ids"], k + "_time_seconds") for k in ("source", "target")] for b in blocks]
        priorq = np.array([np.mean([features.loc[w, "q_beta"] for w in b["worker_ids"]]) for b in blocks])
        values = np.full((nblocks, nblocks, len(base.METRICS)), np.nan)
        disjoint = np.zeros((nblocks, nblocks), bool)
        for i, j in anchor["disjoint_pair_indices"]:
            assert set(blocks[i]["worker_ids"]).isdisjoint(blocks[j]["worker_ids"])
            pair = base.old.pair_metrics(ts[i], ts[j], signatures[blocks[i]["team_key"]], signatures[blocks[j]["team_key"]])
            assert pair["turnover"] == 2
            values[i, j] = base.primitive(ts[i], ts[j], pair, times[i], times[j])
            values[j, i] = base.primitive(ts[i], ts[j], pair, times[i], times[j], reverse=True)
            disjoint[i, j] = disjoint[j, i] = True
        meta = {k: anchor[k] for k in ("anchor_id", "pool_id", "building", "image", "difficulty", "n", "m", "replicate")}
        meta.update(sampled_block_n=nblocks, possible_blocks=anchor["possible_blocks"], exhaustive_blocks=anchor["exhaustive_blocks"], available_people=len(anchor["available_workers"]))
        compositions = {}
        for mid, mapping in labels.items():
            classes = sorted(set(mapping.values()))
            count = [[sum(mapping[w] == c for w in block["worker_ids"]) for c in classes] for block in blocks]
            strings = np.array([base.canonical(c, classes) for c in count])
            compositions[mid] = strings, strings[:, None] == strings[None, :]
        for restriction, neighbor_ok in (("all", disjoint), ("history_A_Qclose3", disjoint & (np.abs(priorq[:, None] - priorq[None, :]) <= 3))):
            masks = {}
            for mid in labels:
                _, same = compositions[mid]
                within, cross = neighbor_ok & same, neighbor_ok & ~same
                eligible = within.any(axis=1) & cross.any(axis=1)
                masks[mid] = within, cross, eligible
            common = np.logical_and.reduce([mask[2] for mask in masks.values()])
            for mid in labels:
                within, cross, eligible = masks[mid]
                coverage.append(dict(meta, method_id=mid, restriction=restriction, native_eligible_A_n=int(eligible.sum()),
                                     common8_eligible_A_n=int(common.sum()), native_without_within_A_n=int((~within.any(axis=1)).sum()),
                                     native_without_cross_A_n=int((~cross.any(axis=1)).sum())))
                strings = compositions[mid][0]
                for support, used in (("native", eligible), ("common8", common)):
                    row = base.summarize(dict(meta, method_id=mid, support=support, restriction=restriction), values, within, cross, used)
                    if row is not None:
                        rows.append(row)
                    if restriction != "all":
                        continue
                    for outvec, invec in itertools.permutations(sorted(set(strings)), 2):
                        directed_cross = cross & (strings[None, :] == invec)
                        directed_a = used & (strings == outvec) & directed_cross.any(axis=1)
                        row = base.summarize(dict(meta, method_id=mid, support=support, restriction=restriction,
                                                 outgoing_vector=outvec, incoming_vector=invec), values, within, directed_cross, directed_a, base.SPEC_METRICS)
                        if row is not None:
                            vectors.append(row)
                for benchmark in benchmark_ids:
                    if benchmark == mid:
                        continue
                    bw, bc, be = masks[benchmark]
                    paired = eligible & be
                    row = base.summarize(dict(meta, method_id=mid, full_method_id=benchmark, support="pairwise_Full_benchmark", restriction=restriction), values, within, cross, paired)
                    brow = base.summarize({}, values, bw, bc, paired)
                    if row is None:
                        continue
                    # Adapter names allow reuse of the exact prior aggregator.
                    # They are renamed before any file is written: these are
                    # substantive competitors, not random partitions.
                    for metric in base.METRICS:
                        for prefix in ("within_", "cross_", "excess_") + (("gap_",) if metric in base.STABLE else ()):
                            col = prefix + metric
                            row["full_" + col] = brow[col]
                            row["full_minus_random_" + col] = brow[col] - row[col]
                    row["full_used_block_indices"] = brow["used_block_indices"]
                    paired_rows.append(row)
    return rows, vectors, paired_rows, coverage

def pairwise_names(frame, reverse=False):
    replacements = [("full_minus_random_", "benchmark_minus_method_"), ("full_", "benchmark_")]
    if reverse:
        replacements = [(y, x) for x, y in replacements]
    def rename(col):
        for old, new in replacements:
            if col.startswith(old):
                return new + col[len(old):]
        return col
    return frame.rename(columns=rename)

def valid_parts(parts, pid):
    try:
        for kind in ("core", "vectors", "paired", "coverage"):
            pd.read_csv(parts / (pid + "." + kind + ".csv.gz"), nrows=1)
            import gzip
            gzip.decompress((parts / (pid + "." + kind + ".csv.gz")).read_bytes())
        return True
    except (OSError, EOFError):
        return False

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--phase", choices=["discovery", "assessment"], required=True)
    args = ap.parse_args()
    t0 = time.monotonic()
    regpath = HERE / "competitors/COMPETITOR_REGISTRATION.json"
    reg = base.read(regpath)
    pinfo = reg["phases"][args.phase]
    panel = ROOT / pinfo["panel_path"]
    if args.phase == "assessment":
        freeze = ROOT / "interchangeability_20261020/assessment/ASSESSMENT_FREEZE.json"
        assert freeze.exists(), "Root direction freeze required before assessment analysis"
    assert base.sha(panel / "COMMON_PANEL_REGISTRATION.json") == pinfo["registration_sha256"]
    assert base.sha(panel / "common_anchors.json.gz") == pinfo["anchor_sha256"]
    assert base.sha(panel / "common_requests.json.gz") == pinfo["request_sha256"]
    for source in reg["source_files"].values():
        assert base.sha(ROOT / source["labels_path"]) == source["labels_sha256"]
        assert base.sha(ROOT / source["manifest_path"]) == source["manifest_sha256"]
    lp = HERE / "competitors/competitor_labels.csv.gz"
    assert base.sha(lp) == reg["competitor_labels_sha256"]
    table = pd.read_csv(lp)
    labels = {mid: dict(zip(g.worker_id, g.class_id)) for mid, g in table.groupby("method_id")}
    assert len(labels) == 8 and all(sorted(m) == reg["population"] for m in labels.values())
    anchors = base.read(panel / "common_anchors.json.gz")["anchors"]
    amap = {a["anchor_id"]: a for a in anchors}
    by_pool = collections.defaultdict(list)
    for a in anchors:
        assert a["building"] in pinfo["buildings"] and a["layer"] == "ordinary_manual"
        assert a["n"] in pinfo["n_values"] and a["m"] == 2
        by_pool[a["pool_id"]].append(a)
    snapshot = ROOT / "repo/research/workers/pro_personnel_v2_archive_20261019/work_v2_20261019/fusion/INPUT_SNAPSHOT.json.gz"
    preg = base.read(panel / "COMMON_PANEL_REGISTRATION.json")
    assert base.sha(snapshot) == preg["input_sha256"]["snapshot"]
    pools = {p["pool_id"]: p for p in base.read(snapshot)["images"] if p["pool_id"] in by_pool}
    features = pd.read_csv(HERE.parent / "features_train.csv.gz").set_index("worker_id")
    out = HERE / "competitors" / args.phase
    parts = out / "parts"
    parts.mkdir(parents=True, exist_ok=True)
    receipts = []
    for pid in sorted(by_pool):
        native = panel / "native/pools" / (pid + ".json.gz")
        rp = parts / (pid + ".receipt.json")
        if rp.exists() and valid_parts(parts, pid):
            receipt = base.read(rp)
            assert receipt["script_sha256"] == base.sha(Path(__file__))
            assert receipt["registration_sha256"] == base.sha(regpath)
            assert receipt["native_sha256"] == base.sha(native)
        else:
            teams = {t["team_key"]: t for t in base.read(native)["teams"]}
            result = analyze_pool(pid, by_pool[pid], pools[pid], teams, labels, features)
            for kind, rows in zip(("core", "vectors", "paired", "coverage"), result):
                df = pd.DataFrame(rows) if rows else pd.DataFrame(columns=["anchor_id", "pool_id", "method_id"])
                if kind == "paired":
                    df = pairwise_names(df)
                base.write_csv(parts / (pid + "." + kind + ".csv.gz"), df)
            receipt = dict(pool_id=pid, phase=args.phase, anchors=len(by_pool[pid]),
                           script_sha256=base.sha(Path(__file__)), primitive_script_sha256=base.sha(HERE / "summarize_common_panel.py"),
                           registration_sha256=base.sha(regpath), native_sha256=base.sha(native),
                           row_counts={k: len(v) for k, v in zip(("core", "vectors", "paired", "coverage"), result)})
            base.write_json(rp, receipt)
        receipts.append(receipt)
        print(json.dumps(dict(phase=args.phase, completed_pools=len(receipts), total_pools=len(by_pool), elapsed=round(time.monotonic() - t0, 1))), flush=True)
    counts = {}
    for kind, keys in (("core", ["method_id", "support", "restriction"]),
                       ("vectors", ["method_id", "support", "restriction", "outgoing_vector", "incoming_vector"]),
                       ("paired", ["method_id", "full_method_id", "support", "restriction"]), ("coverage", [])):
        df = pd.concat([pd.read_csv(parts / (pid + "." + kind + ".csv.gz")) for pid in sorted(by_pool)], ignore_index=True)
        base.write_csv(out / (kind + "_evidence.csv.gz"), df)
        counts[kind] = len(df)
        if kind == "coverage":
            continue
        internal = pairwise_names(df, reverse=True) if kind == "paired" else df
        tables = base.aggregate_frame(internal, amap, keys)
        for level, result in zip(("per_image", "per_building", "aggregate"), tables):
            if kind == "paired":
                result = pairwise_names(result)
            base.write_csv(out / (kind + "_" + level + ".csv.gz"), result)
        del df, internal, tables
    base.write_json(out / "SUMMARY_RECEIPT.json", dict(schema="common26_eight_competitor_actual_pairs_v1", phase=args.phase,
                    registration_sha256=base.sha(regpath), script_sha256=base.sha(Path(__file__)),
                    primitive_script_sha256=base.sha(HERE / "summarize_common_panel.py"), request_sha256=pinfo["request_sha256"],
                    completed_pools=len(receipts), requested_teams=pinfo["unique_teams"], methods=reg["method_ids"],
                    row_counts=counts, by_pool=receipts, elapsed_seconds=time.monotonic() - t0,
                    inference="Common8 and each pairwise eligibility intersection are explicit. These repeated base-A comparisons are not independent images/people. Class projection and known capacities are fixed before outcomes were opened; no target fitting or new fusion."))

if __name__ == "__main__":
    main()
