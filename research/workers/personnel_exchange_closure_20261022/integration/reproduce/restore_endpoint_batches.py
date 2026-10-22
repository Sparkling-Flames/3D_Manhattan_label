#!/usr/bin/env python3
"""Restore exact registered batch views from the delivered endpoint union.

Pure CSV projection: no fusion, scoring, filtering of failures, or type/precision
conversion. REQUESTS remain immutable. A small supplemental batch preserves
union endpoints (the two legacy Semi QT controls) outside central REQUESTS.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import csv
import gzip
import hashlib
import io
import json
import os
from pathlib import Path
import shutil
import tempfile

HERE = Path(__file__).resolve().parent
STUDY = HERE.parents[1]
EXTRA_BATCH = "restored_delivery_extras"
csv.field_size_limit(2**31 - 1)


def sha(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def rows(path):
    with gzip.open(path, "rt", encoding="utf-8-sig", newline="") as f:
        yield from csv.DictReader(f)


def json_save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".partial")
    tmp.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf8")
    os.replace(tmp, path)


class Writer:
    def __init__(self, path, fields):
        self.path = path
        path.parent.mkdir(parents=True, exist_ok=True)
        self.binary = path.open("wb")
        self.zipped = gzip.GzipFile(filename="", fileobj=self.binary, mode="wb", compresslevel=5, mtime=0)
        self.text = io.TextIOWrapper(self.zipped, encoding="utf-8-sig", newline="")
        self.writer = csv.DictWriter(self.text, fieldnames=fields)
        self.writer.writeheader()
        self.count = 0

    def write(self, row):
        self.writer.writerow(row)
        self.count += 1

    def close(self):
        if not self.text.closed:
            self.text.close()
            self.binary.close()


def member_identity(row):
    # Older compact geometry rows omit k; their complete member string remains
    # authoritative. Do not fill or rewrite the delivered field itself.
    size = row.get("k") or row.get("n") or len(row["member_workers"].split("|"))
    return (row["pool_id"], row["member_workers"], int(size))


def existing_keys(path):
    keys = set()
    for row in rows(path):
        key = row["team_key"]
        assert key not in keys, (str(path), "duplicate key", key)
        keys.add(key)
    return keys


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--study-dir", type=Path, default=STUDY)
    ap.add_argument("--scalars", type=Path)
    ap.add_argument("--geometry", type=Path)
    ap.add_argument("--batches-dir", type=Path, help="Source directory with */REQUESTS.csv.gz")
    ap.add_argument("--output-dir", type=Path, help="Default: the source batches directory")
    ap.add_argument("--check-only", action="store_true", help="Validate all requested keys/members and union failure states; write only a small receipt")
    ap.add_argument("--overwrite", action="store_true", help="Replace existing compact batch files after complete validation; preserve original completion receipts")
    ap.add_argument("--receipt", type=Path)
    a = ap.parse_args()
    study = a.study_dir.resolve()
    scalars = (a.scalars or study / "delivery/endpoints/ALL_REQUIRED_ENDPOINT_SCALARS.csv.gz").resolve()
    geometry = (a.geometry or study / "delivery/endpoints/ALL_REQUIRED_ENDPOINT_GEOMETRY.csv.gz").resolve()
    batches = (a.batches_dir or study / "native/batches").resolve()
    dest = (a.output_dir or batches).resolve()
    receipt_path = (a.receipt or study / "integration/reproduce/RESTORE_CHECK_RECEIPT.json").resolve()
    requests, membership, routes, request_refs = {}, {}, defaultdict(list), []
    for path in sorted(batches.glob("*/REQUESTS.csv.gz")):
        bid = path.parent.name
        assert bid != EXTRA_BATCH, "Supplemental delivery views must not be registered as native experiments"
        req = {}
        for row in rows(path):
            key = row["team_key"]
            identity = member_identity(row)
            assert key not in req, (bid, "duplicate request", key)
            assert key not in membership or membership[key] == identity, (key, "conflicting request membership")
            assert len(row["member_workers"].split("|")) == identity[2], (key, "request size")
            membership[key] = identity
            req[key] = identity
            routes[key].append(bid)
        assert req, (bid, "empty request")
        requests[bid] = req
        request_refs.append(dict(batch_id=bid, request_path=str(path), rows=len(req), sha256=sha(path)))
    assert requests, (str(batches), "no frozen REQUESTS found")
    expected = set(membership)
    writers, states, complete_counts = {}, defaultdict(Counter), Counter()
    scalar_identity, geo_keys, extra_keys = {}, set(), set()
    skipped = set()
    if not a.check_only:
        dest.mkdir(parents=True, exist_ok=True)
        for bid in requests:
            sp, gp = dest / bid / "ENDPOINT_SCALARS.csv.gz", dest / bid / "ENDPOINT_GEOMETRY.csv.gz"
            if sp.exists() and gp.exists() and not a.overwrite:
                assert existing_keys(sp) == set(requests[bid]), (bid, "existing scalar keys differ")
                assert existing_keys(gp) == set(requests[bid]), (bid, "existing geometry keys differ")
                skipped.add(bid)
    temp_parent = dest if not a.check_only else receipt_path.parent
    temp_parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="endpoint_projection_", dir=temp_parent) as temp:
        tmpdir = Path(temp)
        try:
            for kind, path in [("SCALARS", scalars), ("GEOMETRY", geometry)]:
                seen = set()
                for row in rows(path):
                    key = row["team_key"]
                    assert key not in seen, (kind, "duplicate union key", key)
                    seen.add(key)
                    identity = member_identity(row)
                    if key in membership:
                        assert identity == membership[key], (kind, key, "exact requested membership differs")
                        targets = routes[key]
                    else:
                        extra_keys.add(key)
                        targets = [EXTRA_BATCH]
                    status = row.get("score_status", "")
                    complete = row.get("complete_evaluable", "").lower()
                    if kind == "SCALARS":
                        scalar_identity[key] = (identity, status, complete)
                        for bid in targets:
                            states[bid][status] += 1
                            complete_counts[bid] += complete in ("true", "1")
                    else:
                        assert key in scalar_identity, (key, "geometry without scalar")
                        saved_identity, saved_status, saved_complete = scalar_identity[key]
                        assert identity == saved_identity, (key, "geometry/scalar membership mismatch")
                        # Legacy compact geometry may carry only identity and
                        # geometry_json. Failure status remains in its scalar.
                        assert not status or status == saved_status, (key, "geometry/scalar status mismatch")
                        assert not complete or complete == saved_complete, (key, "geometry/scalar evaluability mismatch")
                        if row.get("geometry_json"):
                            json.loads(row["geometry_json"])
                        geo_keys.add(key)
                    if not a.check_only:
                        for bid in targets:
                            if bid in skipped:
                                continue
                            pair = (bid, kind)
                            if pair not in writers:
                                writers[pair] = Writer(tmpdir / bid / f"ENDPOINT_{kind}.csv.gz", list(row))
                            writers[pair].write(row)
                if kind == "SCALARS":
                    assert not (expected - seen), ("missing requested scalar keys", len(expected - seen))
            assert set(scalar_identity) == geo_keys, ("scalar/geometry key mismatch", len(set(scalar_identity) - geo_keys))
            assert expected <= geo_keys
        finally:
            for writer in writers.values():
                writer.close()
        all_keys = dict((bid, set(req)) for bid, req in requests.items())
        if extra_keys:
            all_keys[EXTRA_BATCH] = extra_keys
        restored = []
        for bid, keys in all_keys.items():
            record = dict(batch_id=bid, required=len(keys), exported=len(keys), missing=0,
                          states=dict(states[bid]), complete_evaluable=complete_counts[bid],
                          failure_or_not_complete=len(keys)-complete_counts[bid],
                          status="checked_only" if a.check_only else ("existing_files_key_checked" if bid in skipped else "restored"))
            if not a.check_only:
                folder = dest / bid
                folder.mkdir(parents=True, exist_ok=True)
                if dest != batches and bid in requests:
                    shutil.copy2(batches / bid / "REQUESTS.csv.gz", folder / "REQUESTS.csv.gz")
                file_meta = {}
                for kind in ["SCALARS", "GEOMETRY"]:
                    output = folder / f"ENDPOINT_{kind}.csv.gz"
                    if bid not in skipped:
                        assert writers[(bid, kind)].count == len(keys), (bid, kind, "row count")
                        os.replace(writers[(bid, kind)].path, output)
                    file_meta[kind.lower()] = dict(path=str(output), rows=len(keys), bytes=output.stat().st_size, sha256=sha(output))
                record.update(file_meta)
                if bid not in skipped or not (folder / "COMPLETION.json").exists():
                    old = folder / "COMPLETION.json"
                    backup = folder / "ORIGINAL_NATIVE_COMPLETION.json"
                    if old.exists() and not backup.exists():
                        shutil.copy2(old, backup)
                    json_save(old, dict(status="complete", batch_id=bid, requested=len(keys), exported=len(keys), missing=0,
                        states=dict(states[bid]), failures_retained=True, exact_membership_retained=True,
                        no_fusion_or_scoring_in_this_step=True, restoration_from_deduplicated_delivery=True,
                        supplemental_legacy_endpoints=(bid == EXTRA_BATCH),
                        original_native_execution_receipt=(backup.name if backup.exists() else None), **file_meta))
                json_save(folder / "RESTORATION_RECEIPT.json", record)
            restored.append(record)
            print(json.dumps(record, ensure_ascii=False), flush=True)
    receipt = dict(status="complete", mode="check_only" if a.check_only else "restore",
        native_fusion_calls=0, quality_scoring_calls=0, underlying_data_version="v2",
        request_batches=len(requests), requested_references=sum(map(len, requests.values())),
        unique_requested_keys=len(expected), union_unique_keys=len(scalar_identity),
        supplemental_legacy_keys=sorted(extra_keys), missing_scalar_keys=0, missing_geometry_keys=0,
        failure_states_preserved=True, exact_membership_preserved=True,
        union_states=dict(Counter(v[1] for v in scalar_identity.values())),
        sources=[dict(path=str(p),bytes=p.stat().st_size,sha256=sha(p)) for p in [scalars,geometry]],
        requests=request_refs, batches=restored,
        compression_note="Restored compressed bytes may differ; rows and decimal text are copied without numerical conversion.")
    json_save(receipt_path, receipt)
    print(json.dumps({k:v for k,v in receipt.items() if k not in ("requests","batches","sources")}, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()
