"""Native frozen v2 exact-team runner, with bounded, restartable shard output.

Only orchestration and output retention are new. Fusion, score, eligibility,
time joins, and geometry diagnostics are imported from byte-identical sources.
"""
from __future__ import annotations

import argparse
import csv
import gzip
import hashlib
import importlib.util
import io
import json
import math
import os
from pathlib import Path
import resource
import sys
import time
from concurrent.futures import ProcessPoolExecutor, as_completed

HERE = Path(__file__).resolve().parent
FROZEN_HOME = Path(os.environ.get("HOHONET_FROZEN_ENGINE_HOME", str(HERE.parent / "prior_sources/research/same_room/same_room_large_block_rebuilt_20261023/engine"))).resolve()
REPO = Path(os.environ.get("HOHONET_NATIVE_REPOSITORY", str(FROZEN_HOME / "frozen_repo"))).resolve()
COMMIT = "40d0fe62dc62f6f6c12723af10195b7abb7bc9fe"
ORIGIN = "new_population_precision_native_20261025"
for _name in ("OPENBLAS_NUM_THREADS", "OMP_NUM_THREADS", "MKL_NUM_THREADS"):
    os.environ[_name] = "1"
os.environ.setdefault("MPLCONFIGDIR", "/tmp/hohonet_mpl")
os.environ["HOHONET_REPO"] = str(REPO)
if Path("/tmp/hohonet_deps").exists():
    sys.path.insert(0, "/tmp/hohonet_deps")


def module(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    result = importlib.util.module_from_spec(spec)
    sys.modules[name] = result
    spec.loader.exec_module(result)
    return result


adapter = module(REPO / "research/same_room/same_room_current_classes_v2_20261023/code/engine/new_team_engine.py", "frozen_same_room_adapter")
prefix = module(REPO / "research/workers/personnel_population_curves_v2_20261023/code/run_prefix_endpoints.py", "frozen_prefix_adapter")
gs = adapter.gs
pd = adapter.pd


def digest_bytes(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as f:
        for b in iter(lambda: f.read(1024 * 1024), b""):
            h.update(b)
    return h.hexdigest()


def atomic(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    with tmp.open("wb") as f:
        f.write(data)
        f.flush()
        os.fsync(f.fileno())
    tmp.replace(path)


def save_json(path, value):
    raw = json.dumps(gs.clean(value), sort_keys=True, ensure_ascii=False,
                     separators=(",", ":"), allow_nan=False).encode()
    atomic(path, gzip.compress(raw, compresslevel=4, mtime=0) if str(path).endswith(".gz") else raw)


def read_json(path):
    with (gzip.open(path, "rt", encoding="utf-8-sig") if str(path).endswith(".gz")
          else open(path, encoding="utf-8-sig")) as f:
        return json.load(f)


def save_csv(path, rows):
    raw = pd.DataFrame(rows).to_csv(index=False).encode("utf-8-sig")
    atomic(path, gzip.compress(raw, compresslevel=4, mtime=0))


def list_workers(value):
    return value if isinstance(value, list) else str(value).split("|")


def prepare_requests(path):
    path = Path(path)
    if ".json" in path.name:
        raw = read_json(path)
        requests = raw if isinstance(raw, list) else raw["requests"]
    else:
        requests = pd.read_csv(path, keep_default_na=False, dtype=str).to_dict("records")
    pools = gs.pool_lookup()
    by_pool = {}
    seen = set()
    for request in requests:
        pid = request["pool_id"]
        pool = pools[pid]
        for field in ("reference_id", "reference_version", "image", "image_id", "condition", "building"):
            if request.get(field) and request[field] != pool["meta"].get(field):
                raise ValueError("Request " + field + " differs from frozen pool: " + pid)
        workers = sorted(list_workers(request.get("member_workers", request.get("workers"))))
        if not workers or len(set(workers)) != len(workers):
            raise ValueError("Empty/duplicate workers: " + repr(request))
        by_worker = {r["worker_id"]: r for r in pool["records"]}
        if set(workers) - set(by_worker):
            raise ValueError("Unqualified workers in frozen pool: " + repr(request))
        key = gs.team_key(pid, workers)
        if request.get("team_key") and key != request["team_key"]:
            raise ValueError("Noncanonical exact team_key: " + repr(request))
        n = int(request.get("n") or request.get("k") or len(workers))
        if n != len(workers):
            raise ValueError("n disagrees with exact member count: " + key)
        own_ids = [by_worker[w]["object_id"] for w in workers]
        if request.get("member_object_ids"):
            if set(list_workers(request["member_object_ids"])) != set(own_ids):
                raise ValueError("object_id binding differs from frozen pool: " + key)
        if key in seen:
            raise ValueError("Duplicate endpoint request: " + key)
        seen.add(key)
        by_pool.setdefault(pid, []).append(dict(pool_id=pid, team_key=key, n=n,
            member_workers=workers, member_object_ids=own_ids))
    for pid in by_pool:
        by_pool[pid].sort(key=lambda r: r["team_key"])
    return pools, by_pool


class FrozenNativeEngine:
    """Single-process context: .evaluate(pool, exact_workers) returns native row."""
    def __init__(self, full_state=True):
        self.engine = adapter.Engine(full_state=full_state)
        self.pool_hashes = {}

    def __enter__(self):
        self.engine.__enter__()
        return self

    def __exit__(self, *args):
        self.engine.__exit__(*args)

    def reset_pool(self):
        self.engine.reset_pool()

    def evaluate(self, pool, workers):
        start = time.monotonic()
        pid = pool["pool_id"]
        if pid not in self.pool_hashes:
            self.pool_hashes[pid] = gs.digest(pool)
        row = self.engine.evaluate(pool, workers)
        # Retain every raw scorer component, not only the old adapter's shortlist.
        geometry = row.get("geometry")
        if geometry is not None:
            key = self.engine.fr.digest([row["k"] == 2, row.get("nodes"), geometry])
            raw_score = self.engine.scorecache.get(key)
            if raw_score:
                row.update(raw_score)
        row = prefix.geometry_enrich(row, pool, self.engine.fr)
        row.update(endpoint_origin=ORIGIN, underlying_data_version="v2",
            repository_commit=COMMIT, frozen_rules_inherited_commit="72a44e80c344975962e1071bd54d894dd86bb4b4",
            pool_input_sha256=self.pool_hashes[pid])
        # Inherited *_member_n metadata are pool-level counts; expose unambiguous aliases.
        row["pool_new_member_n"] = row.get("new_member_n")
        row["pool_old_member_n"] = row.get("old_member_n")
        row["team_new_member_n"] = row.get("new_n")
        row["team_old_member_n"] = row.get("old_n")
        row["score_available"] = row.get("B8L2") is not None
        row["policy_deferred"] = row["k"] == 2
        row["score_failure_nonpolicy"] = not row["policy_deferred"] and not row["score_available"]
        row["incomplete_nonpolicy"] = not row["policy_deferred"] and not bool(row.get("complete_evaluable"))
        row["reference_node_shortfall"] = (max(0, row["reference_nodes"] - row["nodes"])
                                           if row.get("nodes") is not None else None)
        row["native_evaluation_wall_seconds"] = time.monotonic() - start
        return row


def scalar_row(row):
    out = {}
    for k, v in row.items():
        if k in ("geometry", "full_state"):
            continue
        if k in ("member_workers", "member_object_ids", "node_supports",
                 "ref_matched_nodes_5", "ref_matched_nodes_9", "ref_matched_edges_5", "ref_matched_edges_9"):
            out[k] = "|".join(map(str, v)) if isinstance(v, list) else v
        elif isinstance(v, (dict, list)):
            out[k + "_json"] = json.dumps(v, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)
        else:
            out[k] = v
    return out


def geometry_row(row):
    fields = ("team_key", "pool_id", "image", "image_id", "building", "condition", "layer",
              "reference_id", "reference_version", "pool_input_sha256", "repository_commit",
              "endpoint_origin", "member_workers", "member_object_ids", "k", "score_status",
              "complete_evaluable", "score_available", "minimum_support", "node_supports",
              "geometry_state_pointer", "geometry_shard", "geometry_line_1based", "geometry", "full_state")
    return {k: row.get(k) for k in fields}


def write_part(folder, part_number, rows, pool_hash, request_hash):
    stem = f"part_{part_number:05d}"
    scalar = folder / (stem + ".scalars.csv.gz")
    geometry = folder / (stem + ".geometry_state.jsonl.gz")
    receipt = folder / (stem + ".receipt.json")
    relative_geometry = str(Path("parts") / rows[0]["pool_id"] / geometry.name)
    for number, row in enumerate(rows, 1):
        row["geometry_shard"] = relative_geometry
        row["geometry_line_1based"] = number
        row["geometry_state_pointer"] = relative_geometry + "#L" + str(number)
    save_csv(scalar, [scalar_row(r) for r in rows])
    body = b"".join((json.dumps(geometry_row(r), ensure_ascii=False, sort_keys=True,
                     separators=(",", ":"), allow_nan=False) + "\n").encode() for r in rows)
    atomic(geometry, gzip.compress(body, compresslevel=4, mtime=0))
    info = dict(part=part_number, rows=len(rows), pool_id=rows[0]["pool_id"],
        pool_input_sha256=pool_hash, request_sha256=request_hash,
        scalar_file=scalar.name, scalar_sha256=digest_bytes(scalar), scalar_bytes=scalar.stat().st_size,
        geometry_file=geometry.name, geometry_sha256=digest_bytes(geometry), geometry_bytes=geometry.stat().st_size,
        team_keys=[r["team_key"] for r in rows],
        score_available=sum(r["score_available"] for r in rows),
        complete=sum(bool(r.get("complete_evaluable")) for r in rows),
        failures_nonpolicy=sum(r["score_failure_nonpolicy"] for r in rows),
        native_evaluation_seconds=sum(r["native_evaluation_wall_seconds"] for r in rows))
    save_json(receipt, info)  # Receipt is committed last; orphan files are not completed checkpoints.
    return info


def compute_pool(payload):
    pool, requests, output, chunk_size, full_state = payload
    pid = pool["pool_id"]
    folder = Path(output) / "parts" / pid
    folder.mkdir(parents=True, exist_ok=True)
    pool_hash = gs.digest(pool)
    request_hash = gs.digest(requests)
    wanted = {r["team_key"]: r for r in requests}
    saved = set()
    receipts = []
    for path in sorted(folder.glob("part_*.receipt.json")):
        r = read_json(path)
        if r["pool_input_sha256"] != pool_hash or r["request_sha256"] != request_hash:
            raise ValueError("Checkpoint input/requests changed: " + str(path))
        for name, hashname in (("scalar_file", "scalar_sha256"), ("geometry_file", "geometry_sha256")):
            if digest_bytes(folder / r[name]) != r[hashname]:
                raise ValueError("Checkpoint content hash mismatch: " + str(path))
        keys = set(r["team_keys"])
        if saved & keys or not keys <= wanted.keys() or len(keys) != r["rows"]:
            raise ValueError("Checkpoint team conflict: " + str(path))
        saved.update(keys)
        receipts.append(r)
    initial = len(saved)
    started = time.monotonic()
    pending = [r for r in requests if r["team_key"] not in saved]
    pool_receipt_path = folder / "POOL_RECEIPT.json"
    if not pending and pool_receipt_path.exists():
        # Keep the completed pool's content identity stable for downstream geometry checkpoints.
        previous = read_json(pool_receipt_path)
        if previous["pool_input_sha256"] != pool_hash or previous["request_sha256"] != request_hash:
            raise ValueError("Completed pool receipt input changed")
        return dict(previous, resumed=initial, new_native=0, seconds=time.monotonic()-started)
    buffer = []
    next_part = max([r["part"] for r in receipts] + [0]) + 1
    if pending:
        with FrozenNativeEngine(full_state=full_state) as engine:
            for request in pending:
                row = engine.evaluate(pool, request["member_workers"])
                if row["team_key"] != request["team_key"] or row["k"] != request["n"]:
                    raise ValueError("Native endpoint identity differs from request")
                buffer.append(row)
                if len(buffer) >= chunk_size:
                    receipts.append(write_part(folder, next_part, buffer, pool_hash, request_hash))
                    saved.update(r["team_key"] for r in buffer)
                    next_part += 1
                    buffer = []
                    print(json.dumps(dict(pool_id=pid, checkpoint=len(saved), requested=len(requests),
                        seconds=time.monotonic()-started,
                        process_peak_rss_mib=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss/1024)), flush=True)
            if buffer:
                receipts.append(write_part(folder, next_part, buffer, pool_hash, request_hash))
                saved.update(r["team_key"] for r in buffer)
    if saved != wanted.keys():
        raise ValueError("Incomplete pool")
    result = dict(pool_id=pid, requested=len(requests), resumed=initial, new_native=len(saved)-initial,
        seconds=time.monotonic()-started, parts=len(receipts), score_available=sum(r["score_available"] for r in receipts),
        failures_nonpolicy=sum(r["failures_nonpolicy"] for r in receipts),
        complete=sum(r["complete"] for r in receipts), pool_input_sha256=pool_hash, request_sha256=request_hash)
    result["process_peak_rss_mib"] = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss/1024
    save_json(pool_receipt_path, result)
    return result


def consolidate(output, pools, by_pool):
    """Stream actual gzip shards to EOF, checking keys, membership and pairing."""
    output = Path(output)
    receipts = []
    columns = set()
    for pid in sorted(by_pool):
        for path in sorted((output / "parts" / pid).glob("part_*.receipt.json")):
            r = read_json(path)
            r["folder"] = str(path.parent.relative_to(output))
            with gzip.open(path.parent / r["scalar_file"], "rt", encoding="utf-8-sig", newline="") as f:
                columns.update(next(csv.reader(f)))
            receipts.append(r)
    first = ["team_key", "pool_id", "image", "image_id", "building", "condition", "layer", "k",
             "member_workers", "member_object_ids", "B8L2", "D10", "score_status"]
    columns = [c for c in first if c in columns] + sorted(columns - set(first))
    target = output / "ENDPOINT_SCALARS.csv.gz"
    temp = target.with_name(target.name + ".tmp")
    stream = io.TextIOWrapper(gzip.GzipFile(filename=str(temp), mode="wb", compresslevel=4, mtime=0),
                              encoding="utf-8-sig", newline="")
    writer = csv.DictWriter(stream, fieldnames=columns)
    writer.writeheader()
    seen = set()
    index = []
    by_key = {r["team_key"]: r for rows in by_pool.values() for r in rows}
    for r in receipts:
        folder = output / r["folder"]
        scalar_keys = []
        with gzip.open(folder / r["scalar_file"], "rt", encoding="utf-8-sig", newline="") as f:
            for row in csv.DictReader(f):
                key = row["team_key"]
                if key in seen or key not in by_key:
                    raise ValueError("Duplicate/unrequested scalar team: " + key)
                req = by_key[key]
                if row["pool_id"] != req["pool_id"] or int(row["k"]) != req["n"]:
                    raise ValueError("Scalar pool/n mismatch: " + key)
                if row["member_workers"].split("|") != req["member_workers"]:
                    raise ValueError("Scalar exact member mismatch: " + key)
                if set(row["member_object_ids"].split("|")) != set(req["member_object_ids"]):
                    raise ValueError("Scalar object_id mismatch: " + key)
                writer.writerow(row)
                scalar_keys.append(key)
                seen.add(key)
        geo_keys = []
        with gzip.open(folder / r["geometry_file"], "rt", encoding="utf-8") as f:
            for line in f:
                row = json.loads(line)
                key = row["team_key"]
                req = by_key[key]
                if row["pool_id"] != req["pool_id"] or row["member_workers"] != req["member_workers"]:
                    raise ValueError("Geometry exact member mismatch: " + key)
                geo_keys.append(key)
        if scalar_keys != r["team_keys"] or scalar_keys != geo_keys or len(scalar_keys) != r["rows"]:
            raise ValueError("Scalar/geometry/receipt row association differs")
        index.append({k: v for k, v in r.items() if k != "team_keys"})
    stream.close()
    if seen != by_key.keys():
        raise ValueError("Consolidation is missing registered endpoints")
    temp.replace(target)
    # Read the deliverable CSV through the gzip footer, not only its pre-zip directory.
    with gzip.open(target, "rt", encoding="utf-8-sig", newline="") as f:
        final_rows = sum(1 for _ in csv.DictReader(f))
    if final_rows != len(seen):
        raise ValueError("Final CSV row count differs")
    save_csv(output / "GEOMETRY_SHARD_INDEX.csv.gz", index)
    result = dict(endpoint_rows=final_rows, scalar_fields=len(columns), geometry_rows=sum(r["rows"] for r in receipts),
        shards=len(receipts), scalar_sha256=digest_bytes(target), all_gzip_read_to_eof=True,
        exact_requests_members_object_ids_geometry_associations_checked=True)
    save_json(output / "OUTPUT_VALIDATION.json", result)
    return result


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--requests", required=True)
    p.add_argument("--output", required=True)
    p.add_argument("--jobs", type=int, default=4)
    p.add_argument("--chunk-size", type=int, default=500)
    p.add_argument("--without-full-state", action="store_true", help="Geometry only; default retains native vote/correspondence/connection state")
    p.add_argument("--consolidate-only", action="store_true")
    args = p.parse_args()
    if args.jobs < 1 or args.chunk_size < 1:
        p.error("jobs and chunk-size must be positive")
    output = Path(args.output).resolve()
    output.mkdir(parents=True, exist_ok=True)
    pools, by_pool = prepare_requests(args.requests)
    started = time.monotonic()
    request_manifest = dict(repository_commit=COMMIT, input_request_sha256=digest_bytes(args.requests),
        requests=sum(map(len, by_pool.values())), pools=len(by_pool), full_state=not args.without_full_state,
        chunk_size=args.chunk_size, jobs=args.jobs, endpoint_origin=ORIGIN,
        request_file=str(Path(args.requests).resolve()), frozen_scoring_fusion_and_eligibility_unchanged=True)
    request_manifest["runner_sha256"] = digest_bytes(Path(__file__))
    runtime_manifest = FROZEN_HOME / "RUNTIME_SOURCE_MANIFEST.json"
    request_manifest["runtime_source_manifest_sha256"] = digest_bytes(runtime_manifest) if runtime_manifest.exists() else None
    request_manifest["native_repository_path"] = str(REPO)
    request_manifest["python_version"] = sys.version
    existing = output / "REQUEST_MANIFEST.json"
    if existing.exists():
        old = read_json(existing)
        for field in ("input_request_sha256", "full_state", "repository_commit"):
            if old[field] != request_manifest[field]:
                raise ValueError("Output directory belongs to different request/state/commit")
    else:
        save_json(existing, request_manifest)
    done = []
    if not args.consolidate_only:
        # Large pools start first; each process owns a pool and writes disjoint files.
        payloads = [(pools[pid], by_pool[pid], str(output), args.chunk_size, not args.without_full_state)
                    for pid in sorted(by_pool, key=lambda p: (-len(by_pool[p]), p))]
        with ProcessPoolExecutor(max_workers=args.jobs) as executor:
            futures = [executor.submit(compute_pool, payload) for payload in payloads]
            for future in as_completed(futures):
                r = future.result()
                done.append(r)
                save_json(output / "PROGRESS.json", dict(pools_finished=len(done), pools_total=len(by_pool),
                    seconds=time.monotonic()-started, by_pool=done))
                print(json.dumps(r), flush=True)
    validated = consolidate(output, pools, by_pool)
    receipt = dict(request_manifest, **validated, seconds=time.monotonic()-started,
        new_native=sum(r["new_native"] for r in done), resumed=sum(r["resumed"] for r in done), by_pool=done)
    save_json(output / "RUN_RECEIPT.json", receipt)
    print(json.dumps({k: v for k, v in receipt.items() if k != "by_pool"}), flush=True)


if __name__ == "__main__":
    main()
