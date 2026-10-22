"""Evaluate registered Manual exchanges from completed exact-team endpoints.

No native fusion or quality scoring.  Reuses the published full event kernel,
and writes one independent pool result immediately on completion.
"""
from __future__ import annotations

import os
for _name in ("OPENBLAS_NUM_THREADS", "OMP_NUM_THREADS", "MKL_NUM_THREADS"):
    os.environ[_name] = "1"

import argparse
import csv
import gzip
import io
import json
import math
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

from register_design import HERE, ROOT, h, sha, write, save

PREVIOUS = ROOT / "research/workers/personnel_effective_exchange_conditions_20261022/joint_exchange"
OLD = ROOT / "research/workers/personnel_global_composition_20261021"
sys.path.insert(0, str(PREVIOUS))
import evaluate_joint as previous

NATIVE = HERE.parent / "native"
SYMMETRIC_FIELDS = ["sym_" + f for f in previous.COMPONENTS + previous.EXTRA] + [
    "sym_recorded_time_logratio", "sym_recorded_time_pct", "sym_Q_up", "sym_time_down", "sym_QT_both_improve",
    "sym_loss_gt5", "sym_loss_gt10", "sym_cross_abs_B8L2", "sym_abs_Q_change_advantage",
    "sym_C_failure_or_loss_gt5", "sym_C_failure_or_loss_gt10", "sym_cross_floor_jaccard_difference",
    "sym_cross_mean_height_prism_pair_difference", "sym_geometry_advantage_floor_jaccard_difference",
    "sym_geometry_advantage_mean_height_prism_pair_difference"]


def num(value):
    try:
        value = float(value)
    except (TypeError, ValueError):
        return None
    return value if math.isfinite(value) else None


def symmetric_values(r):
    """C - (A+B)/2; source-pair averaging removes arbitrary A/B orientation."""
    for f in previous.COMPONENTS + previous.EXTRA:
        a, b = num(r.get("cross_" + f)), num(r.get("net_" + f))
        r["sym_" + f] = (a + b) / 2 if a is not None and b is not None else None
    a, b, c = [num(r.get(s + "_source_time_total_seconds")) for s in "ABC"]
    comparable = str(r.get("recorded_time_single_source")).lower() == "true"
    lt = math.log(c / ((a + b) / 2)) if comparable and all(v is not None and v > 0 for v in [a, b, c]) else None
    r["sym_recorded_time_logratio"] = lt
    r["sym_recorded_time_pct"] = 100 * math.expm1(lt) if lt is not None else None
    q = r["sym_B8L2"]
    r["sym_Q_up"] = int(q > 0) if q is not None else None
    r["sym_time_down"] = int(lt < 0) if lt is not None else None
    r["sym_QT_both_improve"] = int(q > 0 and lt < 0) if q is not None and lt is not None else None
    for threshold in [5, 10]:
        r["sym_loss_gt" + str(threshold)] = int(q < -threshold) if q is not None else None
        cf = str(r.get("C_failure")).lower() == "true"
        r["sym_C_failure_or_loss_gt" + str(threshold)] = 1 if cf else (int(q < -threshold) if q is not None else None)
    ca, cb, ab = [num(r.get(key)) for key in ["cross_B8L2", "net_B8L2", "same_B8L2"]]
    r["sym_cross_abs_B8L2"] = (abs(ca) + abs(cb)) / 2 if ca is not None and cb is not None else None
    r["sym_abs_Q_change_advantage"] = r["sym_cross_abs_B8L2"] - abs(ab) if r["sym_cross_abs_B8L2"] is not None and ab is not None else None
    for f in ["floor_jaccard_difference", "mean_height_prism_pair_difference"]:
        aa, bb, ww = [num(r.get(pre + "_" + f)) for pre in ["cross", "net", "within"]]
        r["sym_cross_" + f] = (aa + bb) / 2 if aa is not None and bb is not None else None
        r["sym_geometry_advantage_" + f] = r["sym_cross_" + f] - ww if r["sym_cross_" + f] is not None and ww is not None else None
    return r


def read_json(path):
    with gzip.open(path, "rt", encoding="utf8") as stream:
        return json.load(stream)


def load_pool(pool, needed):
    teams, paths = {}, []
    paths.append(NATIVE / "reused" / (pool + ".json.gz"))
    paths.extend(p for p in sorted((NATIVE / "runtime").glob("*/" + pool + ".json.gz"))
                 if (NATIVE / "batches" / p.parent.name / "COMPLETION.json").exists())
    paths.extend(p for p in sorted((NATIVE / "runtime").glob("*/" + pool + ".FINAL_*.json.gz"))
                 if (NATIVE / "batches" / p.parent.name / "COMPLETION.json").exists())
    sources = []
    for path in paths:
        if not path.exists():
            continue
        loaded = 0
        for row in read_json(path)["teams"]:
            key = row["team_key"]
            if key not in needed:
                continue
            if key in teams:
                assert [row.get(f) for f in ["B8L2", "D10", "nodes"]] == [teams[key].get(f) for f in ["B8L2", "D10", "nodes"]]
                continue
            assert "geometry" in row
            row.update(dict(zip(previous.EXTRA, previous.expression(row["geometry"]))))
            teams[key] = row
            loaded += 1
        if loaded:
            sources.append(dict(path=str(path.relative_to(ROOT)), loaded_teams=loaded, sha256=sha(path)))
    # Portable delivery uses one deduplicated scalar/geometry union.  The small
    # restore_endpoint_batches helper reconstructs exact requested batches; this
    # fallback needs no duplicated native/runtime JSON cache and changes no
    # event formula, endpoint score, geometry or eligibility rule.
    missing = set(needed) - teams.keys()
    for scalar in sorted((NATIVE / "batches").glob("*/ENDPOINT_SCALARS.csv.gz")):
        if not missing:
            break
        geometry = scalar.with_name("ENDPOINT_GEOMETRY.csv.gz")
        if not geometry.exists() or not (scalar.parent / "COMPLETION.json").exists():
            continue
        added = set()
        for chunk in pd.read_csv(scalar, dtype=str, keep_default_na=False, chunksize=20000):
            for row in chunk[chunk.team_key.isin(missing)].to_dict("records"):
                key = row["team_key"]
                item = previous.typed(row)
                assert item["pool_id"] == pool
                teams[key] = item
                added.add(key)
        if not added:
            continue
        for chunk in pd.read_csv(geometry, dtype=str, keep_default_na=False, chunksize=20000):
            for row in chunk[chunk.team_key.isin(added)].to_dict("records"):
                teams[row["team_key"]]["geometry"] = json.loads(row["geometry_json"]) if row["geometry_json"] else None
        for key in added:
            assert "geometry" in teams[key], (key, "missing_geometry")
            teams[key].update(dict(zip(previous.EXTRA, previous.expression(teams[key]["geometry"]))))
        sources.append(dict(path=str(scalar.relative_to(ROOT)), geometry_path=str(geometry.relative_to(ROOT)),
                            loaded_teams=len(added), sha256=sha(scalar), geometry_sha256=sha(geometry),
                            portable_compact_fallback=True))
        missing -= added
    return teams, sources


def policy_result(request, teams):
    r = dict(request)
    a, b = [teams[r["team_" + v]] for v in ["A", "P"]]
    for side, t in [("A", a), ("P", b)]:
        assert t["k"] == int(r["n"])
        assert "|".join(t["member_workers"]) == r[side + "_member_workers"]
        r[side + "_failure"] = not bool(t.get("complete_evaluable"))
        r[side + "_score_status"] = t.get("score_status")
        for key in previous.COMPONENTS + previous.EXTRA:
            r[side + "_" + key] = t.get(key)
        r[side + "_source_time_total_seconds"] = t.get("source_time_total_seconds")
        r[side + "_time_source_kinds"] = t.get("time_source_kinds")
    for f in previous.COMPONENTS + previous.EXTRA:
        x, y = a.get(f), b.get(f)
        r["change_" + f] = y - x if previous.finite(x) and previous.finite(y) else None
    kinds = [a.get("time_source_kinds"), b.get("time_source_kinds")]
    comparable = (len(set(kinds)) == 1 and all(k and "|" not in k for k in kinds)
                  and all(t.get("source_time_known_n") == int(r["n"])
                          and previous.finite(t.get("source_time_total_seconds"))
                          and t["source_time_total_seconds"] > 0 for t in [a, b]))
    r["recorded_time_comparable"] = comparable
    r["change_recorded_time_logratio"] = math.log(b["source_time_total_seconds"] / a["source_time_total_seconds"]) if comparable else None
    q = r["change_B8L2"]
    r["change_Q_up"] = int(q > 0) if previous.finite(q) else None
    r["change_loss_gt5"] = int(q < -5) if previous.finite(q) else None
    r["change_loss_gt10"] = int(q < -10) if previous.finite(q) else None
    r["P_failure_or_loss_gt5"] = int(r["P_failure"] or (previous.finite(q) and q < -5))
    return r


def concatenate(files, dest, symmetric=False):
    fields = []
    for path in files:
        with gzip.open(path, "rt", encoding="utf-8-sig", newline="") as f:
            head = next(csv.reader(f))
        fields.extend(x for x in head if x not in fields)
    if symmetric:
        fields.extend(x for x in SYMMETRIC_FIELDS if x not in fields)
    tmp = dest.with_name(dest.name + ".tmp")
    rows = 0
    with tmp.open("wb") as binary:
        with gzip.GzipFile(fileobj=binary, mode="wb", compresslevel=5, mtime=0) as zipped:
            with io.TextIOWrapper(zipped, encoding="utf-8-sig", newline="") as text:
                writer = csv.DictWriter(text, fieldnames=fields)
                writer.writeheader()
                for path in files:
                    with gzip.open(path, "rt", encoding="utf-8-sig", newline="") as stream:
                        for row in csv.DictReader(stream):
                            if symmetric:
                                row = symmetric_values(row)
                            writer.writerow(row)
                            rows += 1
    tmp.replace(dest)
    return rows


def main():
    global HERE
    ap = argparse.ArgumentParser()
    ap.add_argument("--require-complete", action="store_true")
    ap.add_argument("--study-dir", type=Path, default=HERE)
    args = ap.parse_args()
    HERE = args.study_dir.resolve()
    events = pd.read_csv(HERE / "EVENTS_REGISTERED.csv.gz", dtype=str, keep_default_na=False)
    policies = pd.read_csv(HERE / "POLICIES_REGISTERED.csv.gz", dtype=str, keep_default_na=False)
    hist_df = pd.read_csv(OLD / "multivariate/continuous_features_lobo.csv.gz")
    hist = {(r.condition, r.heldout_building, r.worker_id): r for r in hist_df.itertuples()}
    _, _, sg, corner = previous.gs.setup_engine()
    ledger, pending, all_sources = [], [], []
    begun = time.monotonic()
    for pool, req in events.groupby("pool_id", sort=True):
        pq = policies[policies.pool_id.eq(pool)]
        needed = set(req.team_A) | set(req.team_B) | set(req.team_C) | set(pq.team_A) | set(pq.team_P)
        pool_id = h("pool", pool)[:20]
        folder = HERE / "results" / pool_id
        dest, pdest, receipt_path = folder / "EVENTS_COMPLETE.csv.gz", folder / "POLICIES_COMPLETE.csv.gz", folder / "COMPLETION.json"
        if receipt_path.exists():
            receipt = json.loads(receipt_path.read_text())
            assert receipt["events"] == len(req) and receipt["policies"] == len(pq)
            ledger.append(receipt)
            continue
        teams, sources = load_pool(pool, needed)
        if missing := needed - teams.keys():
            pending.append(dict(pool_id=pool, events=len(req), policies=len(pq), required_endpoints=len(needed),
                                available_endpoints=len(teams), missing_endpoints=len(missing)))
            continue
        pairs, signatures, rows = {}, {}, []
        for idx, request in enumerate(req.to_dict("records"), 1):
            result = previous.complete_event(request, teams, pairs, signatures, hist, sg, corner, "manual")
            for key in ["panel_id", "capacity_id", "background_id", "member_path", "source_partition_id"]:
                result[key] = request[key]
            result["C_failure_or_net_loss_gt5"] = bool(result["C_failure"] or (previous.finite(result["net_B8L2"]) and result["net_B8L2"] < -5))
            result["C_failure_or_net_loss_gt10"] = bool(result["C_failure"] or (previous.finite(result["net_B8L2"]) and result["net_B8L2"] < -10))
            result = symmetric_values(result)
            rows.append(result)
            if idx % 1000 == 0:
                print(pool, idx, "/", len(req), "pairs", len(pairs), "seconds", round(time.monotonic() - begun, 1), flush=True)
        data = pd.DataFrame(rows)
        assert len(data) == len(req) and not data.event_id.duplicated().any()
        write(dest, data)
        prows = [policy_result(r, teams) for r in pq.to_dict("records")]
        if prows:
            write(pdest, pd.DataFrame(prows))
        source_file = folder / "ENDPOINT_SOURCES.csv"
        write(source_file, pd.DataFrame(sources))
        all_sources.extend(sources)
        receipt = dict(pool_id=pool, events=len(data), policies=len(prows), endpoints=len(teams),
                       event_file=str(dest.relative_to(HERE)), policy_file=str(pdest.relative_to(HERE)) if prows else "",
                       event_sha256=sha(dest), policy_sha256=sha(pdest) if prows else "", native_fusion_calls=0,
                       unique_geometric_pairs=len(pairs), events_all_scored=int(data.all_scored.sum()),
                       events_all_complete=int(data.all_complete.sum()), failures_retained=True,
                       uses_frozen_event_kernel=str((PREVIOUS / "evaluate_joint.py").relative_to(ROOT)))
        save(receipt_path, receipt)
        ledger.append(receipt)
        print("SAVED", pool, len(data), "events", len(prows), "policies", flush=True)
    write(HERE / "RESULT_BATCH_INDEX.csv", pd.DataFrame(ledger))
    write(HERE / "PENDING_POOLS.csv", pd.DataFrame(pending))
    if ledger:
        concatenate([HERE / r["event_file"] for r in ledger], HERE / "EVENTS_COMPLETE.csv.gz", symmetric=True)
        pfiles = [HERE / r["policy_file"] for r in ledger if r["policy_file"]]
        if pfiles:
            concatenate(pfiles, HERE / "POLICIES_COMPLETE.csv.gz")
    save(HERE / "EVALUATION_RECEIPT.json", dict(complete=not pending, registered_events=len(events),
                completed_events=sum(r["events"] for r in ledger), completed_policies=sum(r["policies"] for r in ledger),
                pending_events=sum(r["events"] for r in pending), completed_pools=len(ledger), pending_pools=len(pending),
                native_fusion_calls=0, failure_events_not_removed=True, underlying_data_version="v2"))
    print(json.dumps(dict(complete=not pending, pools=len(ledger), pending=len(pending), seconds=time.monotonic() - begun)), flush=True)
    if args.require_complete:
        assert not pending, "Registered endpoints still pending; completed pools are already saved."


if __name__ == "__main__":
    main()
