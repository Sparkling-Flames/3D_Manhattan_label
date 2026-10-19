#!/usr/bin/env python3
"""Recount frozen-pool metadata and split membership; do not read new results."""
from collections import Counter
import gzip
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SNAPSHOT = ROOT / "restored/work_personnel_typing_A_20261019/recovered/work_v2_20261019/fusion/INPUT_SNAPSHOT.json.gz"
SPLIT = ROOT / "analysis/composition/SPLIT.json"
OUT = ROOT / "analysis/independent/INPUT_METADATA_RECOUNT.json"


def main():
    snapshot = json.load(gzip.open(SNAPSHOT, "rt", encoding="utf-8"))
    split = json.loads(SPLIT.read_text(encoding="utf-8"))
    pools = snapshot["images"]
    groups = {g: set(split[g + "_buildings"]) for g in ("history", "discovery", "validation")}
    assert not groups["history"] & groups["discovery"]
    assert not groups["history"] & groups["validation"]
    assert not groups["discovery"] & groups["validation"]
    buildings = {p["meta"]["building"] for p in pools}
    assert set.union(*groups.values()) == buildings
    assert len({p["pool_id"] for p in pools}) == len(pools)
    for p in pools:
        workers = [r["worker_id"] for r in p["records"]]
        objects = [r["object_id"] for r in p["records"]]
        assert len(workers) == len(set(workers)) == p["meta"]["pool_n"]
        assert len(objects) == len(set(objects))
    actual = {}
    diffs = {"简单": "easy", "中等": "medium", "困难": "hard"}
    for group, bs in groups.items():
        items = [p for p in pools if p["meta"]["building"] in bs]
        ordinary = [p for p in items if p["meta"]["layer"] == "ordinary_manual"]
        difficulties = Counter(diffs[p["meta"]["difficulty"]] for p in ordinary)
        count = dict(ordinary_pools=len(ordinary), ordinary_members=sum(len(p["records"]) for p in ordinary),
                     **{key: difficulties[key] for key in ("easy", "medium", "hard")},
                     doorway_manual=sum(p["meta"]["layer"] == "doorway_manual" for p in items),
                     ordinary_semi=sum(p["meta"]["layer"] == "ordinary_semi" for p in items))
        assert count == split["balance"][group]
        actual[group] = count
    result = dict(
        scope="Independent frozen input metadata recount only; no new fusion/category validation results read",
        snapshot_sha256=hashlib.sha256(SNAPSHOT.read_bytes()).hexdigest(),
        split_sha256=hashlib.sha256(SPLIT.read_bytes()).hexdigest(),
        pools=len(pools), images=len({p["meta"]["image_id"] for p in pools}),
        buildings=len(buildings), workers=len({r["worker_id"] for p in pools for r in p["records"]}),
        pool_layers=dict(Counter(p["meta"]["layer"] for p in pools)),
        all_pool_members_distinct=True, split_disjoint_and_covers_all_pool_buildings=True,
        group_buildings={g: len(bs) for g, bs in groups.items()},
        balance_matches_declared_exactly=True, balance=actual,
        N1_applied=snapshot["N1_applied"], fusion_gap=snapshot["fusion_gap"],
    )
    OUT.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
