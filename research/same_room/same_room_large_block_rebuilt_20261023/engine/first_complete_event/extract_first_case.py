"""Extract the prespecified first comparable ordinary Manual structure event.

This is a new-design illustration and delivery unit, not missing-original recovery.
It does not read any target endpoint outcome when selecting the event.
"""
from pathlib import Path
import csv
import gzip
import hashlib
import json
import pandas as pd

OUT = Path(__file__).resolve().parent
BASE = Path(__file__).resolve().parents[2]


def gz_csv(path, rows):
    pd.DataFrame(rows).to_csv(path, index=False, compression={"method": "gzip", "mtime": 0})


def main():
    event_source = BASE / "design/STRICT_ABC_EVENTS.csv.gz"
    frame = pd.read_csv(event_source, usecols=["event_id", "method", "condition", "ordinary_comparable", "layer_a", "layer_b"], keep_default_na=False)
    subset = frame[(frame.method == "V3_BEHAVIOR") & (frame.condition == "manual") &
                   (frame.ordinary_comparable.astype(str).str.lower() == "true") &
                   (frame.layer_a == "ordinary_manual") & (frame.layer_b == "ordinary_manual")]
    event_id = subset.event_id.min()
    with gzip.open(event_source, "rt", encoding="utf-8-sig", newline="") as f:
        event = next(r for r in csv.DictReader(f) if r["event_id"] == event_id)
    gz_csv(OUT / "STRICT_ABC_EVENT.csv.gz", [event])
    keys = {event[f"team_key_{arm}_{view}"] for arm in "ABC" for view in "ab"}
    with gzip.open(BASE / "design/ENDPOINT_REQUESTS.csv.gz", "rt", encoding="utf-8-sig", newline="") as f:
        requests = [r for r in csv.DictReader(f) if r["team_key"] in keys]
    if len(requests) != 6:
        raise ValueError("First event must resolve to six unique exact endpoint requests")
    gz_csv(OUT / "ENDPOINT_REQUESTS.csv.gz", requests)
    frozen = BASE / "engine/frozen_repo"
    pool_source = frozen / "research/workers/pro_personnel_v2_archive_20261019/work_v2_20261019/fusion/INPUT_SNAPSHOT.json.gz"
    snapshot = json.load(gzip.open(pool_source, "rt"))
    pids = {event["pool_id_a"], event["pool_id_b"]}
    pools = [p for p in snapshot["images"] if p["pool_id"] in pids]
    if len(pools) != 2:
        raise ValueError("Both frozen pools are required")
    body = json.dumps(dict(images=pools), ensure_ascii=False, separators=(",", ":")).encode()
    (OUT / "FROZEN_TWO_POOLS.json.gz").write_bytes(gzip.compress(body, compresslevel=4, mtime=0))
    ids = {r["object_id"] for p in pools for r in p["records"]}
    time_source = frozen / "research/workers/personnel_profiles_composition_20261020/source/tables/profiles/record_index.csv.gz"
    with gzip.open(time_source, "rt", encoding="utf-8-sig", newline="") as f:
        times = [r for r in csv.DictReader(f) if r["object_id"] in ids]
    gz_csv(OUT / "TWO_POOL_RECORD_TIMES.csv.gz", times)
    roles = pd.read_csv(BASE / "design/CLASS_ROLES_AND_MEMBERS.csv", keep_default_na=False)
    roles[(roles.heldout_building == event["building"]) & (roles.method == event["method"]) &
          (roles.condition == event["condition"])].to_csv(OUT / "FROZEN_CLASS_ROLES_AND_MEMBERS.csv", index=False)
    receipt = dict(status="new_design_complete_case_not_restored_original", event_id=event_id,
        selection="lexicographically first event_id among ordinary comparable Manual V3_BEHAVIOR events; selected before endpoint outcomes",
        candidate_events=len(subset), strict_design_source=str(event_source),
        strict_design_sha256=hashlib.sha256(event_source.read_bytes()).hexdigest(),
        requested_unique_endpoints=6, repeated_native_calls_relative_to_production_run=6,
        additional_unique_production_endpoints=0, input_commit=event["input_commit"],
        frozen_two_pools=2, frozen_pool_records=sum(len(p["records"]) for p in pools), time_rows=len(times))
    (OUT / "CASE_PROVENANCE.json").write_text(json.dumps(receipt, ensure_ascii=False, indent=2))
    print(json.dumps(receipt, ensure_ascii=False))


if __name__ == "__main__":
    main()
