#!/usr/bin/env python3
"""Derive all registered same-core entrant-pair changes from new native teams.

Only existing fusion outputs are read; no team is fused/scored here.  The exact
legacy comparator is reused, with cached per-team geometry signatures.  Rich
new shape diagnostics are deliberately outside this all-pair training stream.
"""
from __future__ import annotations
import argparse
import csv
import gzip
import hashlib
import io
import itertools
import json
import math
import os
from pathlib import Path
import sys
import time
from concurrent.futures import ProcessPoolExecutor, as_completed

for name in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS"):
    os.environ.setdefault(name, "1")
import pandas as pd

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT / "analysis/composition"))
from summarize_grid import pair_metrics, signature
from learn_swap_types import READ_COLUMNS, sha, write_json

PANEL_ID = "H20_metadata_allentrant_v1"


def run_pool(task):
    root, out, pid, anchors, origin = task
    root, out = Path(root), Path(out)
    p = root / "interchangeability_20261020/history_panel/native_runs/pools" / (pid + ".json.gz")
    native = json.load(gzip.open(p, "rt"))
    assert native["context"]["science_commit"] == "82c6164b0d4630de5316199c92aa405930973168"
    teams = {r["team_key"]: r for r in native["teams"]}
    requested = {key for anchor in anchors for key in anchor["entrant_teams"].values()}
    assert requested.issubset(teams), (pid, len(requested - set(teams)))
    signatures = {key: signature(teams[key]) for key in requested}
    rows = []; unique_actual_pairs = set(); duplicate_pairs = 0
    for anchor in anchors:
        core = set(anchor["core_workers"])
        assert len(core) == anchor["k"] - 1
        assert set(anchor["entrant_workers"]) == set(anchor["entrant_teams"])
        for wa, wb in itertools.combinations(sorted(anchor["entrant_workers"]), 2):
            ka, kb = anchor["entrant_teams"][wa], anchor["entrant_teams"][wb]
            a, b = teams[ka], teams[kb]
            assert set(a["member_workers"]) == core | {wa}
            assert set(b["member_workers"]) == core | {wb}
            assert a["k"] == b["k"] == anchor["k"]
            # Registered repeated anchors remain accounted for, but actual pair
            # duplicates do not gain additional training weight.
            physical_pair = tuple(sorted((ka, kb)))
            if physical_pair in unique_actual_pairs:
                duplicate_pairs += 1
                continue
            unique_actual_pairs.add(physical_pair)
            metric = pair_metrics(a, b, signatures[ka], signatures[kb])
            assert metric["turnover"] == 1 and metric["shared_workers"] == len(core)
            row = {c: None for c in READ_COLUMNS}
            row.update({k: v for k, v in metric.items() if k in row})
            row.update(event_id="H20pair_" + hashlib.sha256(json.dumps([anchor["anchor_id"], wa, wb]).encode()).hexdigest()[:24],
                       panel_id=PANEL_ID, pool_id=pid, image=a["image"], image_id=a["image_id"], building=a["building"],
                       difficulty=a["difficulty"], condition=a["condition"], layer=a["layer"],
                       reference_id=a["reference_id"], reference_version=a["reference_version"],
                       k=anchor["k"], background_id=anchor["anchor_id"], background_members="|".join(sorted(core)),
                       worker_a=wa, worker_b=wb, request_a=ka, request_b=kb, team_id_a=ka, team_id_b=kb,
                       member_workers_a="|".join(sorted(a["member_workers"])), member_workers_b="|".join(sorted(b["member_workers"])),
                       entrant_origin_a=origin[wa], entrant_origin_b=origin[wb],
                       B8L2_a=a.get("B8L2"), B8L2_b=b.get("B8L2"), D10_a=a.get("D10"), D10_b=b.get("D10"),
                       nodes_a=a.get("nodes"), nodes_b=b.get("nodes"))
            rows.append(row)
    target = out / "native_pair_chunks" / (pid + ".csv.gz")
    raw = pd.DataFrame(rows, columns=READ_COLUMNS).to_csv(index=False).encode("utf-8")
    packed = gzip.compress(raw, compresslevel=6, mtime=0)
    assert gzip.decompress(packed) == raw
    temporary = target.with_suffix(target.suffix + ".tmp")
    temporary.write_bytes(packed)
    temporary.replace(target)
    return {"pool_id": pid, "anchors": len(anchors), "requested_pairs": sum(a["pair_count"] for a in anchors),
            "unique_actual_pairs": len(rows), "duplicate_actual_pairs": duplicate_pairs,
            "native_teams_used": len(requested), "native_file_sha256": sha(p),
            "pair_file_sha256": sha(target), "pair_path": str(target.relative_to(root))}


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--root", type=Path, default=ROOT)
    ap.add_argument("--out", type=Path, default=HERE); ap.add_argument("--jobs", type=int, default=4)
    ap.add_argument("--pilot-pools", type=int)
    a = ap.parse_args(); root = a.root.resolve(); out = a.out.resolve()
    (out / "native_pair_chunks").mkdir(parents=True, exist_ok=True)
    anchor_path = root / "interchangeability_20261020/history_panel/history_anchors.json.gz"
    design = json.load(gzip.open(anchor_path, "rt")); hist = set(json.load(open(root / "analysis/composition/SPLIT.json"))["history_buildings"])
    bypool = {}
    for anchor in design["anchors"]:
        assert anchor["building"] in hist and anchor["layer"] == "ordinary_manual"
        bypool.setdefault(anchor["pool_id"], []).append(anchor)
    if a.pilot_pools:
        bypool = dict(list(sorted(bypool.items()))[:a.pilot_pools])
    features = pd.read_csv(root / "analysis/forward/results/features_train.csv.gz", usecols=["worker_id", "person_origin"])
    origin = features.set_index("worker_id").person_origin.to_dict()
    tasks = [(str(root), str(out), pid, anchors, origin) for pid, anchors in sorted(bypool.items())]
    receipts = []; start = time.perf_counter()
    with ProcessPoolExecutor(max_workers=a.jobs) as ex:
        futures = [ex.submit(run_pool, task) for task in tasks]
        for future in as_completed(futures):
            receipts.append(future.result())
            if len(receipts) % 10 == 0 or len(receipts) == len(tasks):
                print(json.dumps({"completed_pools": len(receipts), "total_pools": len(tasks),
                                  "unique_pairs": sum(r["unique_actual_pairs"] for r in receipts),
                                  "elapsed_seconds": round(time.perf_counter() - start, 1)}), flush=True)
    # Merge the already-written pool chunks once.  This is a derived compact
    # event stream, not a duplicate of final geometries or native vote caches.
    pieces = [pd.read_csv(root / r["pair_path"]) for r in sorted(receipts, key=lambda r: r["pool_id"])]
    events = pd.concat(pieces, ignore_index=True)
    assert events.event_id.is_unique
    assert set(events.building).issubset(hist)
    assert len(events) + sum(r["duplicate_actual_pairs"] for r in receipts) == sum(r["requested_pairs"] for r in receipts)
    target = out / "native_history_events.csv.gz"
    raw = events.to_csv(index=False).encode("utf-8")
    packed = gzip.compress(raw, compresslevel=6, mtime=0)
    assert gzip.decompress(packed) == raw
    temporary = target.with_suffix(target.suffix + ".tmp")
    temporary.write_bytes(packed); temporary.replace(target)
    receipt = {"schema": "native_history_legacy_pair_metrics_v1", "source_anchors_sha256": sha(anchor_path),
               "source_registration_sha256": sha(root / "interchangeability_20261020/history_panel/HISTORY_PANEL_REGISTRATION.json"),
               "comparator_path": "analysis/composition/summarize_grid.py", "comparator_sha256": sha(root / "analysis/composition/summarize_grid.py"),
               "source_fusion_commit": "82c6164b0d4630de5316199c92aa405930973168", "pools": len(receipts),
               "registered_pair_observations": sum(r["requested_pairs"] for r in receipts),
               "unique_actual_pairs": len(events), "duplicate_actual_pairs": sum(r["duplicate_actual_pairs"] for r in receipts),
               "output_path": str(target.relative_to(root)), "output_sha256": sha(target),
               "pool_receipts": sorted(receipts, key=lambda r: r["pool_id"]),
               "not_computed_fields": ["edge_relation_jaccard_difference", "selected_shared_observation_difference", "source_entrant_time_a", "source_entrant_time_b"],
               "missing_policy": "Those fields remain missing; no missing continuous score/distance is zero-filled.",
               "extra_rich_shape_metrics_computed": False, "new_fusions_or_scores": 0,
               "elapsed_seconds": time.perf_counter() - start}
    write_json(out / "NATIVE_PAIR_EXTRACTION_RECEIPT.json", receipt)


if __name__ == "__main__":
    main()
