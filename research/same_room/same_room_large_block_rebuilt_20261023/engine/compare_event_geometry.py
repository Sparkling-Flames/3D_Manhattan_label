"""Frozen within-view AB/AC/BC corner comparisons for exact strict ABC events.

Geometry/correspondence rules come from the saved native corner_distance.py.
Only exact pair caching, event linkage and bounded pool orchestration are new.
"""
from __future__ import annotations
import argparse
from concurrent.futures import ProcessPoolExecutor, wait, FIRST_COMPLETED
import csv
import gzip
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import sys
import time

HERE = Path(__file__).resolve().parent
for name in ("OPENBLAS_NUM_THREADS", "OMP_NUM_THREADS", "MKL_NUM_THREADS"):
    os.environ[name] = "1"
if (HERE / "deps").exists():
    sys.path.insert(0, str(HERE / "deps"))
import pandas as pd

CORNER_SOURCE = HERE / "frozen_repo/research/workers/personnel_interchangeability_followup_20261020/audit_corner/corner_distance.py"
spec = importlib.util.spec_from_file_location("frozen_corresponding_corner", CORNER_SOURCE)
corner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(corner)


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def file_hash(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as f:
        for b in iter(lambda: f.read(1024*1024), b""):
            h.update(b)
    return h.hexdigest()


def atomic(path, body):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    with temporary.open("wb") as f:
        f.write(body)
        f.flush()
        os.fsync(f.fileno())
    temporary.replace(path)


def save_json(path, value):
    atomic(path, json.dumps(value, sort_keys=True, ensure_ascii=False, indent=2, allow_nan=False).encode())


def read_json(path):
    return json.loads(Path(path).read_text())


def save_csv(path, rows):
    raw = pd.DataFrame(rows).to_csv(index=False).encode("utf-8-sig")
    atomic(path, gzip.compress(raw, compresslevel=4, mtime=0))


def prepare(events_path):
    header = set(pd.read_csv(events_path, nrows=0).columns)
    def field(*choices):
        found = [x for x in choices if x in header]
        if not found:
            raise ValueError("Required geometry linkage field missing, candidates=" + repr(choices))
        return found[0]
    schema = {"event_id": field("event_id", "strict_abc_event_id", "abc_event_id")}
    for view in ("a", "b"):
        schema["pool_" + view] = field("pool_id_" + view, "pool_" + view)
        for arm in ("A", "B", "C"):
            schema[arm + "_" + view] = field(f"team_key_{arm}_{view}", f"team_key_{view}_{arm}",
                                               f"{arm}_team_key_{view}", f"{arm}_{view}_team_key")
    extra = [x for x in ("pair_key", "config_id", "configuration_id", "building", "condition", "layer", "method", "n", "m") if x in header]
    frame = pd.read_csv(events_path, dtype=str, keep_default_na=False, usecols=list(set(schema.values()) | set(extra)))
    if frame[schema["event_id"]].duplicated().any():
        raise ValueError("Events must contain unique event_id")
    by_pool = {}
    for row in frame.to_dict("records"):
        for view in ("a", "b"):
            item = {"event_id": row[schema["event_id"]], "view": view,
                    "pool_id": row[schema["pool_" + view]],
                    **{a: row[schema[a + "_" + view]] for a in ("A", "B", "C")},
                    **{k: row[k] for k in extra}}
            if len({item[a] for a in ("A", "B", "C")}) != 3:
                raise ValueError("ABC are not three distinct exact teams: " + item["event_id"])
            by_pool.setdefault(item["pool_id"], []).append(item)
    return by_pool, schema, len(frame)


def compare_pool(payload):
    pid, events, endpoints, output, input_hash = payload
    started = time.monotonic()
    output = Path(output)
    base = Path(endpoints) / "parts" / pid
    receipt_path = output / "pools" / (pid + ".receipt.json")
    endpoint_receipt = base / "POOL_RECEIPT.json"
    endpoint_hash = file_hash(endpoint_receipt)
    if receipt_path.exists():
        receipt = read_json(receipt_path)
        if receipt["event_input_sha256"] != input_hash or receipt["endpoint_pool_receipt_sha256"] != endpoint_hash:
            raise ValueError("Geometry checkpoint input changed")
        for name, h in (("event_file", "event_sha256"), ("pair_file", "pair_sha256")):
            if file_hash(output / receipt[name]) != receipt[h]:
                raise ValueError("Geometry checkpoint content changed")
        return dict(receipt, resumed=True)
    needed = {r[arm] for r in events for arm in ("A", "B", "C")}
    teams = {}
    for receipt_file in sorted(base.glob("part_*.receipt.json")):
        receipt = read_json(receipt_file)
        if not set(receipt["team_keys"]) & needed:
            continue
        with gzip.open(base / receipt["geometry_file"], "rt", encoding="utf-8") as f:
            for line in f:
                row = json.loads(line)
                key = row["team_key"]
                if key in needed:
                    # Full vote state remains in original shards; correspondence needs only final geometry.
                    row.pop("full_state", None)
                    teams[key] = row
    if set(teams) != needed:
        raise ValueError("Missing registered geometry rows for completed pool: " + pid)
    cache = {}
    results = []
    for event in events:
        metadata = {k: v for k, v in event.items() if k not in ("A", "B", "C")}
        for left, right in (("A", "B"), ("A", "C"), ("B", "C")):
            source, target = event[left], event[right]
            # Ordered caching preserves the native correspondence anchor and shift semantics.
            key = (source, target)
            if key not in cache:
                row, details = corner.corner_compare(teams[source], teams[target])
                row.update(geometry_pair_key="GEOM_" + digest([pid, source, target])[:24],
                    pool_id=pid, team_key_from=source, team_key_to=target,
                    reference_id=teams[source].get("reference_id"),
                    reference_version=teams[source].get("reference_version"),
                    geometry_state_pointer_from=teams[source].get("geometry_state_pointer"),
                    geometry_state_pointer_to=teams[target].get("geometry_state_pointer"))
                cache[key] = row
            results.append(dict(metadata, comparison=left + right, **cache[key]))
    event_file = Path("pools") / (pid + ".event_geometry.csv.gz")
    pair_file = Path("pools") / (pid + ".unique_pairs.csv.gz")
    save_csv(output / event_file, results)
    save_csv(output / pair_file, list(cache.values()))
    statuses = {}
    for row in results:
        statuses[row["status"]] = statuses.get(row["status"], 0) + 1
    receipt = dict(pool_id=pid, events_in_view=len(events), event_comparison_rows=len(results),
        unique_ordered_pairs=len(cache), geometry_team_rows=len(teams), status_counts=statuses,
        event_file=str(event_file), event_sha256=file_hash(output / event_file),
        pair_file=str(pair_file), pair_sha256=file_hash(output / pair_file),
        event_input_sha256=input_hash, endpoint_pool_receipt_sha256=endpoint_hash,
        frozen_corner_source_sha256=file_hash(CORNER_SOURCE), seconds=time.monotonic()-started,
        correspondence_method_unchanged=True, per_corner_rows="Recomputable with frozen function; retained only for separately selected mechanism cases")
    save_json(receipt_path, receipt)
    return receipt


def merge_pools(output, receipts, field, target_name, expected=None):
    output = Path(output)
    columns = set()
    for r in receipts:
        with gzip.open(output / r[field], "rt", encoding="utf-8-sig", newline="") as f:
            columns.update(next(csv.reader(f)))
    prefix = ["event_id", "pair_key", "building", "view", "comparison", "pool_id", "geometry_pair_key", "team_key_from", "team_key_to", "status", "complete", "same_count"]
    columns = [c for c in prefix if c in columns] + sorted(columns - set(prefix))
    target = output / target_name
    temporary = target.with_name(target.name + ".tmp")
    stream = io.TextIOWrapper(gzip.GzipFile(filename=str(temporary), mode="wb", compresslevel=4, mtime=0),
                              encoding="utf-8-sig", newline="")
    writer = csv.DictWriter(stream, fieldnames=columns)
    writer.writeheader()
    n = 0
    for r in sorted(receipts, key=lambda x: x["pool_id"]):
        with gzip.open(output / r[field], "rt", encoding="utf-8-sig", newline="") as f:
            for row in csv.DictReader(f):
                writer.writerow(row)
                n += 1
    stream.close()
    if expected is not None and n != expected:
        raise ValueError("Geometry event comparison rows differ from six per exact event")
    temporary.replace(target)
    with gzip.open(target, "rt", encoding="utf-8-sig", newline="") as f:
        if sum(1 for _ in csv.DictReader(f)) != n:
            raise ValueError("Final gzip row count differs")
    return dict(path=target_name, rows=n, fields=len(columns), sha256=file_hash(target), all_gzip_read_to_eof=True)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--events", required=True)
    p.add_argument("--endpoints", required=True)
    p.add_argument("--output", required=True)
    p.add_argument("--jobs", type=int, default=2)
    p.add_argument("--watch", action="store_true", help="Wait for native pool checkpoints, comparing completed pools as they arrive")
    p.add_argument("--poll-seconds", type=float, default=10)
    args = p.parse_args()
    output = Path(args.output)
    output.mkdir(parents=True, exist_ok=True)
    by_pool, schema, event_count = prepare(args.events)
    input_hash = file_hash(args.events)
    save_json(output / "INPUT_SCHEMA.json", dict(event_file=str(Path(args.events).resolve()), event_sha256=input_hash,
        endpoint_folder=str(Path(args.endpoints).resolve()), columns=schema, events=event_count, pools=len(by_pool),
        comparisons="same-view AB, AC, BC; same exact event repeated across two views", corner_source_sha256=file_hash(CORNER_SOURCE)))
    pending = set(by_pool)
    running = {}
    done = []
    start = time.monotonic()
    with ProcessPoolExecutor(max_workers=args.jobs) as executor:
        while pending or running:
            available = [pid for pid in sorted(pending)
                         if (Path(args.endpoints) / "parts" / pid / "POOL_RECEIPT.json").exists()]
            for pid in available[:max(0, args.jobs-len(running))]:
                future = executor.submit(compare_pool, (pid, by_pool[pid], args.endpoints, args.output, input_hash))
                running[future] = pid
                pending.remove(pid)
            if not running:
                if not args.watch and pending:
                    raise ValueError("Native pools incomplete: " + "|".join(sorted(pending)))
                if pending:
                    time.sleep(min(30, max(1, args.poll_seconds)))
                    continue
            finished, _ = wait(running, timeout=min(30, max(1, args.poll_seconds)), return_when=FIRST_COMPLETED)
            for future in finished:
                r = future.result()
                done.append(r)
                del running[future]
                save_json(output / "PROGRESS.json", dict(finished=len(done), pending=len(pending), running=len(running),
                    seconds=time.monotonic()-start, by_pool=done))
                print(json.dumps({k: v for k, v in r.items() if k not in ("status_counts",)}), flush=True)
    event_result = merge_pools(output, done, "event_file", "EVENT_GEOMETRY_RESULTS.csv.gz", expected=6*event_count)
    pair_result = merge_pools(output, done, "pair_file", "UNIQUE_GEOMETRY_COMPARISONS.csv.gz")
    save_json(output / "COMPLETION.json", dict(events=event_count, pools=len(done), seconds=time.monotonic()-start,
        event_results=event_result, unique_pairs=pair_result, frozen_correspondence_unchanged=True,
        failures_and_different_counts_retained=True, geometry_distances_not_imputed=True))
    print(json.dumps(dict(events=event_count, pools=len(done), event_results=event_result, unique_pairs=pair_result)), flush=True)


if __name__ == "__main__":
    main()
