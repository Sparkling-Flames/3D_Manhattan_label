#!/usr/bin/env python3
"""Repair order-list metadata from immutable, actually executed prefix links.

This does not register, select, execute, or modify any endpoint or result.
"""
from __future__ import annotations
import argparse
import csv
import gzip
import hashlib
import io
import json
import os
from pathlib import Path


def sha(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def atomic(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    with tmp.open("wb") as handle:
        handle.write(data)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(tmp, path)
    fd = os.open(path.parent, os.O_DIRECTORY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def read_csv(path):
    with gzip.open(path, "rt", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        fields = list(reader.fieldnames)
        rows = list(reader)
    return fields, rows


def key(pool_id, workers):
    raw = json.dumps(sorted(workers), sort_keys=True, separators=(",", ":")).encode()
    return pool_id + "__" + hashlib.sha256(raw).hexdigest()[:20]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base", type=Path, default=Path(__file__).resolve().parents[1])
    args = parser.parse_args()
    base = args.base.resolve()
    design = base / "design/NEW_EXACT_ORDER_DESIGN.csv.gz"
    register = base / "engine/register_precision_design.py"
    prefix = base / "design/NEW_PREFIX_TEAM_LINKS.csv.gz"
    original = base / "design/source_original/policy_order_metadata_20261025"
    original.mkdir(parents=True, exist_ok=True)
    for src in [design, register]:
        dst = original / src.name
        if not dst.exists():
            atomic(dst, src.read_bytes())
            assert sha(dst) == sha(src)
    immutable_paths = [
        "design/NEW_PREFIX_TEAM_LINKS.csv.gz",
        "design/EXACT_MARGINAL_TEAM_DESIGN.csv.gz",
        "design/ENDPOINT_DEPENDENCIES.csv.gz",
        "design/NEW_NATIVE_ENDPOINT_REQUESTS.csv.gz",
        "new_endpoints/NEW_ENDPOINT_SCALARS.csv.gz",
        "new_endpoints/NEW_PREFIX_VALUES_COMPACT.csv.gz",
        "new_endpoints/EXACT_MARGINAL_VALUES.csv.gz",
        "new_endpoints/NEW_ENDPOINT_GEOMETRY_COMPACT.jsonl.gz",
        "new_endpoints/TABLE_SHARD_MANIFEST.json",
    ]
    before = {rel: sha(base / rel) for rel in immutable_paths}
    fields, rows = read_csv(original / design.name)
    assert "base_worker_order" not in fields
    lookup = {row["path_id"]: row for row in rows}
    assert len(lookup) == len(rows) == 12224
    prefixes = {}
    prefix_n = 0
    with gzip.open(prefix, "rt", encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            prefixes.setdefault(row["path_id"], []).append((
                int(row["k"]), row["entrant_worker"], row["team_key"],
                int(row["target_present_n"]), row["pool_id"], row["policy"], row["base_path_id"]))
            prefix_n += 1
    assert set(prefixes) == set(lookup)
    policy_n = changed_policy_n = natural_n = team_checks = 0
    policy_counts = {}
    for row in rows:
        entries = sorted(prefixes[row["path_id"]])
        N = int(row["pool_n"])
        assert [entry[0] for entry in entries] == list(range(1, N + 1))
        actual = [entry[1] for entry in entries]
        assert len(set(actual)) == N
        base_row = lookup[row["base_path_id"]]
        assert base_row["policy"] == "natural_random"
        base_order = base_row["worker_order"].split("|")
        assert base_row["workers"] == base_row["worker_order"]
        assert set(base_order) == set(actual)
        target = set(row["target_members"].split("|")) if row["target_members"] else set()
        is_policy = row["policy"] != "natural_random"
        if is_policy:
            expected = [w for w in base_order if w in target] + [w for w in base_order if w not in target]
            assert target and target < set(actual)
            assert row["workers"] == row["worker_order"] == "|".join(base_order)
            assert actual == expected, row["path_id"]
            policy_n += 1
            policy_counts[row["policy"]] = policy_counts.get(row["policy"], 0) + 1
            changed_policy_n += actual != base_order
            row["workers"] = "|".join(actual)
            row["worker_order"] = "|".join(actual)
        else:
            assert actual == base_order
            natural_n += 1
        row["base_worker_order"] = "|".join(base_order)
        selected = []
        for k, worker, team, target_n, pool_id, policy, base_path in entries:
            assert (pool_id, policy, base_path) == (row["pool_id"], row["policy"], row["base_path_id"])
            selected.append(worker)
            assert team == key(pool_id, selected)
            assert target_n == sum(w in target for w in selected)
            team_checks += 1
    assert policy_n == 5024 and natural_n == 7200 and team_checks == prefix_n == 403376
    # Correct only order representation. All other original field strings persist.
    _, original_rows = read_csv(original / design.name)
    allowed = {"workers", "worker_order"}
    for old, new in zip(original_rows, rows):
        for field in fields:
            if old["policy"] == "natural_random" or field not in allowed:
                assert old[field] == new[field], (old["path_id"], field)
    memory = io.StringIO(newline="")
    writer = csv.DictWriter(memory, fieldnames=fields + ["base_worker_order"])
    writer.writeheader()
    writer.writerows(rows)
    uncompressed = memory.getvalue().encode("utf-8")
    atomic(design, gzip.compress(uncompressed, compresslevel=6, mtime=0))
    with gzip.open(design, "rb") as handle:
        assert handle.read() == uncompressed
    corrected_fields, corrected_rows = read_csv(design)
    assert corrected_fields == fields + ["base_worker_order"]
    assert corrected_rows == rows
    code = (original / register.name).read_text()
    replacements = [
        ("    def add_order(pool,row,order,target=()):\n        orders.append(row);members=[];target=set(target)",
         "    def add_order(pool,row,order,target=()):\n        assert row['workers']==row['worker_order']=='|'.join(order)\n        orders.append(row);members=[];target=set(target)"),
        ("policy='natural_random',workers='|'.join(order),worker_order='|'.join(order),",
         "policy='natural_random',workers='|'.join(order),worker_order='|'.join(order),base_worker_order='|'.join(order),"),
        ("prow=dict(row,policy=policy,path_id=base+'__'+policy,batch='policy_new8',",
         "prow=dict(row,policy=policy,path_id=base+'__'+policy,batch='policy_new8',\n                        workers='|'.join(po),worker_order='|'.join(po),base_worker_order='|'.join(order),"),
    ]
    for old, new in replacements:
        assert code.count(old) == 1
        code = code.replace(old, new)
    compile(code, str(register), "exec")
    atomic(register, code.encode())
    after = {rel: sha(base / rel) for rel in immutable_paths}
    assert before == after
    receipt = {
        "correction_id": "policy_order_metadata_20261025",
        "repository_commit": "40d0fe62dc62f6f6c12723af10195b7abb7bc9fe",
        "cause": "prow copied natural row without replacing workers/worker_order; actual prefix generation used correct policy po",
        "corrected_fields": ["workers", "worker_order"],
        "new_field": "base_worker_order retains the actual paired uniform base; natural rows repeat their own order",
        "order_rows": len(rows), "natural_rows_original_fields_unchanged": natural_n,
        "policy_rows_checked": policy_n, "policy_rows_actual_order_changed_from_old_metadata": changed_policy_n,
        "policy_rows_by_policy": policy_counts,
        "all_policy_orders_match_stable_target_partition_of_same_base": True,
        "all_prefix_team_keys_reconstructed_and_matched": team_checks,
        "all_other_original_order_fields_unchanged": True,
        "new_fusion_or_scoring_or_selection": 0,
        "originals_preserved": [{"path": str((original / p.name).relative_to(base)), "sha256": sha(original / p.name)} for p in [design, register]],
        "corrected_files": [{"path": str(p.relative_to(base)), "sha256": sha(p), "bytes": p.stat().st_size} for p in [design, register]],
        "unchanged_teams_links_results_and_Q_files_sha256": before,
        "canonical_design_full_gzip_eof_verified": True,
        "canonical_design_columns": corrected_fields,
        "write_method": "fully materialized gzip in memory, fsync temporary file, atomic replace, fsync directory, complete EOF and CSV comparison",
    }
    receipt_path = base / "design/POLICY_ORDER_METADATA_CORRECTION_RECEIPT.json"
    atomic(receipt_path, (json.dumps(receipt, ensure_ascii=False, indent=2) + "\n").encode())
    print(json.dumps({"receipt": str(receipt_path), "policy_rows_checked": policy_n,
        "policy_rows_changed": changed_policy_n, "prefix_team_checks": team_checks, "unchanged_result_files": len(before)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
