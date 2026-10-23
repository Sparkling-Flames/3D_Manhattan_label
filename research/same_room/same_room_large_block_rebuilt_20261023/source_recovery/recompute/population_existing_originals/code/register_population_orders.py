"""Register complete v2 pool permutations and paired category-priority orders.

This is a design-only program. It reads no target endpoint outcomes. Existing
four uniform paths are retained verbatim; their requests can hit the old cache.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import gzip
import hashlib
import io
import json
import os
from pathlib import Path
from itertools import permutations

import numpy as np
import pandas as pd

from order_policies import ROLE_SPECS, RoleBook, stable_seed


def write_bytes(path: Path, data: bytes):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    with temporary.open("wb") as f:
        f.write(data)
        f.flush()
        os.fsync(f.fileno())
    os.replace(temporary, path)


def save_csv(frame: pd.DataFrame, path: Path):
    data = frame.to_csv(index=False).encode("utf-8")
    if path.suffix == ".gz":
        data = gzip.compress(data, mtime=0)
    write_bytes(path, data)
    read_back = pd.read_csv(path, low_memory=False)
    assert read_back.shape == frame.shape


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--snapshot", required=True)
    ap.add_argument("--initial-requests", required=True)
    ap.add_argument("--labels", required=True)
    ap.add_argument("--definitions", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--natural-replicates", type=int, default=24)
    ap.add_argument("--paired-replicates", type=int, default=8)
    ap.add_argument("--master-seed", type=int, default=20261023)
    ap.add_argument("--source-commit", default="72a44e80c344975962e1071bd54d894dd86bb4b4")
    args = ap.parse_args()
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    snapshot = json.load(gzip.open(args.snapshot, "rt"))
    initial = json.load(gzip.open(args.initial_requests, "rt"))
    pools = snapshot["images"]
    old = defaultdict(list)
    for path in initial["paths"]:
        old[path["pool_id"]].append(path)
    rolebook = RoleBook(args.labels, args.definitions)
    rows, supports, pool_rows, legacy_rows = [], [], [], []
    for pool in pools:
        meta = pool["meta"]
        pid = pool["pool_id"]
        workers = sorted(r["worker_id"] for r in pool["records"])
        assert len(workers) == len(set(workers)) == meta["pool_n"]
        pool_hash = hashlib.sha256((pid + "|" + "|".join(workers)).encode()).hexdigest()[:24]
        legacy = sorted(old[pid], key=lambda x: x["draw_id"])
        assert [x["draw_id"] for x in legacy] == list(range(4))
        assert args.natural_replicates >= len(legacy)
        assert args.paired_replicates <= args.natural_replicates
        pool_rows.append(dict(meta, workers="|".join(workers), final_pool_hash=pool_hash))
        for entry in legacy:
            legacy_rows.append(dict(meta, path_id=entry["path_id"], replicate=entry["draw_id"],
                                    workers="|".join(entry["worker_order"]),
                                    legacy_request_ids="|".join(entry["request_ids"]),
                                    source_kind="historical_uniform_MC_order", master_seed=2026101901))
        metas = {}
        for policy in ROLE_SPECS:
            role_meta = rolebook.pool_role(workers, meta["condition"], meta["building"], policy)
            metas[policy] = role_meta
            supports.append(dict(meta, **role_meta, final_pool_hash=pool_hash))
        natural_rows = []
        exact_permutations = None
        if len(workers) <= 4:
            exact_permutations = list(permutations(workers))
            enum_seed = stable_seed("v2-exact-small-pool-order-catalogue", args.master_seed, pid)
            index_order = np.random.default_rng(enum_seed).permutation(len(exact_permutations))
            exact_permutations = [exact_permutations[i] for i in index_order]
        natural_count = len(exact_permutations) if exact_permutations is not None else args.natural_replicates
        for rep in range(natural_count):
            legacy_path_ids = ""
            if exact_permutations is not None:
                order = list(exact_permutations[rep])
                matched = [entry for entry in legacy if entry["worker_order"] == order]
                path_id = f"{pid}__population_20261023__exact_permutation_r{rep:03d}"
                request_ids = "|".join(matched[0]["request_ids"]) if matched else ""
                legacy_path_ids = "|".join(entry["path_id"] for entry in matched)
                seed = str(enum_seed)
                generation = "exact_small_pool_permutation_catalogue"
                seed_rule = "all N! permutations once; fixed-seed shuffled catalogue for unbiased paired subset"
                sample_kind = "exact_permutation"
            elif rep < len(legacy):
                entry = legacy[rep]
                order = entry["worker_order"]
                path_id = entry["path_id"]
                request_ids = "|".join(entry["request_ids"])
                seed = "2026101901"
                generation = "reused_existing_uniform_path"
                seed_rule = "old rng_for('uniform_order', pool_id, draw_id); exact saved order retained"
                legacy_path_ids = path_id
                sample_kind = "MC"
            else:
                rng_seed = stable_seed("v2-full-pool-prefix", args.master_seed, meta["condition"], meta["image"], rep)
                order = np.random.default_rng(rng_seed).permutation(workers).tolist()
                path_id = f"{pid}__population_20261023__natural_r{rep:03d}"
                request_ids = ""
                seed = str(rng_seed)
                generation = "new_uniform_path"
                seed_rule = "sha256 canonical JSON(namespace, master_seed, condition, image, replicate), first8 little-endian"
                sample_kind = "MC"
            assert sorted(order) == workers
            row = dict(meta, path_id=path_id, base_path_id=path_id, replicate=rep, seed=seed,
                       master_seed=args.master_seed, policy="natural_random", workers="|".join(order),
                       worker_order="|".join(order), order_kind="uniform_without_replacement_within_pool",
                       generation=generation, seed_rule=seed_rule, legacy_request_ids=request_ids,
                       legacy_path_ids=legacy_path_ids, sample_kind=sample_kind, sampling_weight=1 / natural_count,
                       final_pool_hash=pool_hash, final_pool_identity="same_actual_full_pool",
                       eligible=True, reason="supported", target_capacity=0,
                       paired_for_policy=(rep < args.paired_replicates))
            natural_rows.append(row)
            rows.append(row)
        for policy, role_meta in metas.items():
            if not role_meta["eligible"]:
                continue
            for base in natural_rows[:args.paired_replicates]:
                order, _ = rolebook.prioritize(base["workers"].split("|"), meta["condition"], meta["building"], policy)
                row = dict(meta, **role_meta, path_id=f"{base['path_id']}__{policy}",
                           base_path_id=base["path_id"], replicate=base["replicate"], seed=base["seed"],
                           master_seed=args.master_seed, workers="|".join(order),
                           worker_order="|".join(order), order_kind="class_priority_stable_binary_partition",
                           generation="new_policy_order_paired_to_uniform", seed_rule=base["seed_rule"],
                           legacy_request_ids="", final_pool_hash=pool_hash,
                           legacy_path_ids="", sample_kind=("exact_transformed_permutations" if natural_count <= args.paired_replicates
                               else "paired_subset_of_exact_permutations" if exact_permutations is not None else "MC"),
                           sampling_weight=1 / min(natural_count, args.paired_replicates),
                           final_pool_identity="same_actual_full_pool", paired_for_policy=True)
                rows.append(row)
    frame = pd.DataFrame(rows)
    support = pd.DataFrame(supports)
    for df in [frame, support]:
        for col in ["target_members", "known_members", "unknown_members"]:
            if col in df:
                df[col] = df[col].map(lambda x: "|".join(x) if isinstance(x, list) else x)
    assert not frame.path_id.duplicated().any()
    global_teams = set()
    summary = []
    for (condition, layer, policy), g in frame.groupby(["condition", "layer", "policy"]):
        teams = set()
        sequences = set()
        for r in g.to_dict("records"):
            order = r["workers"].split("|")
            sequences.add((r["pool_id"], tuple(order)))
            for k in range(1, len(order) + 1):
                teams.add((r["pool_id"], tuple(sorted(order[:k]))))
        global_teams.update(teams)
        summary.append(dict(condition=condition, layer=layer, policy=policy, pools=g.pool_id.nunique(),
                            images=g.image.nunique(), buildings=g.building.nunique(), paths=len(g),
                            distinct_sequences=len(sequences), prefix_records=int(g.pool_n.sum()),
                            distinct_prefix_teams=len(teams)))
    save_csv(frame, out / "EXACT_ORDER_DESIGN.csv.gz")
    save_csv(support, out / "POLICY_POOL_CAPACITY.csv")
    save_csv(pd.DataFrame(pool_rows), out / "ACTUAL_POOLS.csv")
    save_csv(pd.DataFrame(legacy_rows), out / "LEGACY_UNIFORM_ORDERS.csv.gz")
    save_csv(rolebook.roles, out / "LOBO_PRIORITY_ROLE_DEFINITIONS.csv")
    save_csv(pd.DataFrame(summary), out / "ORDER_COVERAGE.csv")
    manifest = dict(
        schema="v2_full_pool_population_orders_20261023_v2", source_commit=args.source_commit,
        data_version="real_annotations_v2", natural_replicates=args.natural_replicates,
        retained_uniform_replicates=4, new_uniform_replicates=args.natural_replicates - 4,
        paired_policy_replicates=args.paired_replicates, master_seed=args.master_seed,
        pools=len(pools), path_records=len(frame), prefix_records=int(frame.pool_n.sum()),
        unique_requested_team_endpoints=len(global_teams), distinct_natural_paths=int((frame.policy=="natural_random").sum()),
        source_inputs={str(Path(p)): sha(Path(p)) for p in [args.snapshot, args.initial_requests, args.labels, args.definitions]},
        orders_sha256=sha(out / "EXACT_ORDER_DESIGN.csv.gz"),
        role_selection="Building-excluded historical class centroids, fixed rules; no target outcomes used",
        unknown_policy="Retained in the random remainder, never imputed to a known class",
        duplicate_sequences="Chance duplicate permutations retained in Monte Carlo weights; deterministic endpoint calculated once",
        small_pool_rule="N<=4: all N! natural permutations once equally weighted; seeded catalogue order; up to 8 paired policy transforms",
        exact_small_pool_count=sum(len(p["records"]) <= 4 for p in pools),
        nontrivial_policy_support="Target class present and not equal to full pool; all other capacities recorded separately",
        same_pool_comparison="Stable binary partition of exact paired natural order; whole pool is identical at final n",
        new_fusions_performed_by_this_script=0,
        full_permutation_space_enumerated=False,
    )
    write_bytes(out / "ORDER_DESIGN_MANIFEST.json", json.dumps(manifest, ensure_ascii=False, indent=2).encode())
    print(json.dumps({k:manifest[k] for k in ["pools","path_records","prefix_records","unique_requested_team_endpoints"]}))


if __name__ == "__main__":
    main()
