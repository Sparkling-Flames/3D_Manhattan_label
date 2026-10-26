"""Validate completed prefix bytes against the actual registered orders.

This is a delivery association check, not another fusion experiment. Run after
both stages finish, including after extracting the necessary delivered packages.
CSV/gzip inputs are consumed to EOF; no numerical outcome is used for selection.
"""
from pathlib import Path
import argparse
import csv
import gzip
import hashlib
import json


def rows(path):
    with gzip.open(path, "rt", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            if None in row or None in row.values():
                raise ValueError(f"Malformed row in {path}")
            yield row


def main(base):
    base = base.resolve()
    plan = list(csv.DictReader((base / "design26/POOL_SAMPLING_PLAN.csv").open(encoding="utf-8-sig")))
    pool_results = []
    all_paths = set()
    prefix_total = 0
    for pool in plan:
        pid = pool["pool_id"]
        orders = {r["path_id"]: r for r in rows(base / "design26/orders_by_pool" / (pid + ".csv.gz"))}
        assert len(orders) in (208, 272), pid
        assert not all_paths.intersection(orders)
        all_paths.update(orders)
        order_members = {path: r["worker_order"].split("|") for path, r in orders.items()}
        for path, members in order_members.items():
            assert len(members) == int(pool["pool_n"]) == len(set(members)), path
            r = orders[path]
            if r["policy"] != "natural_random":
                natural = order_members[r["base_path_id"]]
                target = set(filter(None, r["target_members"].split("|")))
                assert members == [w for w in natural if w in target] + [w for w in natural if w not in target], path
        full_team_keys = set()
        for stage in (1, 2):
            expected = {(r["path_id"], int(r["k"])): r for r in rows(base / f"design26/links_by_pool/stage{stage}" / (pid + ".csv.gz"))}
            seen = set()
            keys = hashlib.sha256()
            for r in rows(base / f"new_endpoints26/stage{stage}/prefix_values" / (pid + ".csv.gz")):
                identity = (r["path_id"], int(r["k"]))
                assert identity not in seen
                seen.add(identity)
                requested = expected[identity]
                for field, value in requested.items():
                    assert r[field] == value, (pid, stage, identity, field, value, r[field])
                members = order_members[r["path_id"]][:int(r["k"])]
                assert set(r["member_workers"].split("|")) == set(members), identity
                assert len(r["member_workers"].split("|")) == int(r["k"]), identity
                assert len(r["member_object_ids"].split("|")) == int(r["k"]), identity
                assert r["entrant_worker"] == members[-1], identity
                assert r["pool_id"] == pid
                if int(r["k"]) == int(pool["pool_n"]):
                    full_team_keys.add(r["team_key"])
                keys.update((r["path_id"] + "\t" + r["k"] + "\t" + r["team_key"] + "\n").encode())
            assert seen == set(expected)
            prefix_total += len(seen)
            pool_results.append(dict(pool_id=pid, stage=stage, prefix_rows=len(seen),
                ordered_path_k_team_sha256=keys.hexdigest(), all_requested_fields_match=True,
                exact_order_prefix_members_match=True, all_read_to_EOF=True))
        assert len(full_team_keys) == 1, (pid, "full pool is not a single fixed team")
    receipt = dict(complete=True, pools=len(plan), order_records=len(all_paths), prefix_occurrences=prefix_total,
        registered_order_to_prefix_to_team_members_verified=True,
        derived_policy_stable_partition_verified=True,
        full_pool_one_unique_team_per_image_verified=True,
        no_fusion_calls=True, per_pool_stage=pool_results)
    assert len(all_paths) == 50400 and prefix_total == 1644576
    output = base / "delivery26/FINAL_PATH_LINK_VALIDATION.json"
    temporary = output.with_suffix(".writing")
    temporary.write_text(json.dumps(receipt, ensure_ascii=False, indent=2) + "\n")
    temporary.replace(output)
    print(json.dumps({k: v for k, v in receipt.items() if k != "per_pool_stage"}, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--base", type=Path, required=True)
    main(parser.parse_args().base)
