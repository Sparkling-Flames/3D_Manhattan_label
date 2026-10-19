#!/usr/bin/env python3
"""Small implementation parity audit; no new validation/scientific search.

Select exact legacy teams by SHA-256 rank within prespecified implementation
branches: 5 complete teams at each historical size (8/12/16/24), plus 2 teams
from each historical no_connection/below_four/invalid_floor status. Selection
uses the already published legacy table and is frozen before any recomputation.
Single process, one BLAS thread. Only selected rows and audit evidence are saved.
"""
import os
for var in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS"):
    os.environ[var] = "1"
import collections
import csv
import dataclasses
import gzip
import hashlib
import importlib.util
import importlib.metadata
import json
import math
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "analysis/independent"
LEGACY = ROOT / "restored/work_personnel_typing_A_20261019/events/native_runs"
RUNNER = ROOT / "analysis/composition/fusion_runner.py"
SEED = "implementation_parity_20261019_v1"
NUMERIC = ["B8L2", "D10", "IoU3D100", "iou_2d", "S_bottom_deg", "dir", "Hmean", "Hcenter", "omission", "extension", "height_mean_ratio"]
DISCRETE = ["k", "nodes", "below_four", "half_vote_nodes", "connection_available", "order_status", "order_tied", "geometry_status", "geometry_reason", "floor_evaluable", "complete_floor_evaluable", "complete_evaluable", "location_unresolved", "score_status"]


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def save(name, value):
    (OUT / name).write_text(json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False) + "\n", encoding="utf-8")


def parse(value):
    if value in (None, ""):
        return None
    if value in ("True", "False"):
        return value == "True"
    try:
        number = float(value)
        return number if math.isfinite(number) else None
    except (ValueError, TypeError):
        return value


def selection():
    with (LEGACY / "team_results.csv").open(encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))
    unique = {}
    for row in sorted(rows, key=lambda r: r["request_id"]):
        unique.setdefault(row["team_id"], row)
    ranked = sorted(unique.values(), key=lambda r: hashlib.sha256((SEED + "|" + r["team_id"]).encode()).hexdigest())
    selected = []
    for size in (8, 12, 16, 24):
        chosen = [r for r in ranked if r["score_status"] == "complete_conditional" and int(r["k"]) == size][:5]
        assert len(chosen) == 5
        selected.extend(chosen)
    for status in ("no_connection", "below_four", "invalid_floor"):
        chosen = [r for r in ranked if r["score_status"] == status][:2]
        assert len(chosen) == 2
        selected.extend(chosen)
    assert len(selected) == len({r["team_id"] for r in selected}) == 26
    save("PARITY_SELECTION.json", {
        "seed": SEED, "selection": "SHA-256 rank within 4 size / 3 failure strata; 20 complete + 6 historical failures; no new outputs consulted",
        "legacy_table_sha256": sha(LEGACY / "team_results.csv"),
        "legacy_request_rows": len(rows), "legacy_unique_teams": len(unique),
        "selected": [{k: r.get(k) for k in ["team_id", "request_id", "pool_id", "image", "building", "reference_id", "reference_version", "member_workers", "member_object_ids", "subset"] + DISCRETE + NUMERIC} for r in selected]
    })
    return selected


def main():
    OUT.mkdir(exist_ok=True, parents=True)
    selected = selection()
    snapshot = OUT / "fusion_runner_audited_snapshot.py"
    snapshot.write_bytes(RUNNER.read_bytes())
    spec = importlib.util.spec_from_file_location("audited_composition_runner", snapshot)
    runner = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(runner)
    fe = runner.init_engine(ROOT / "restored")
    pools = {p["pool_id"]: p for p in fe.load_pools()}
    source = fe.SOURCE
    files = {
        "runner": snapshot, "fusion_engine": Path(fe.__file__), "input_snapshot": Path(fe.__file__).parent / "INPUT_SNAPSHOT.json.gz",
        "fusion_entry": source / "tools/thesis_main/analysis/consensus_delivery_20261008.py",
        "ring_engine": source / "tools/thesis_main/analysis/ring_correspondence_20261007.py",
        "measurement_wrapper": source / "tools/thesis_main/analysis/wall_consensus_quality_20261015.py",
        "dual_scores": source / "tools/thesis_main/analysis/quality_b8l2_d10_20261017.py",
        "measurement_engine": fe.ENGINE / "measurement_engine.zip", "working_models": fe.ENGINE / "working_models.py"
    }
    file_provenance = {k: {"path": str(p), "sha256": sha(p), "bytes": p.stat().st_size} for k, p in files.items()}
    assert all(len(p["records"]) == len({r["worker_id"] for r in p["records"]}) for p in pools.values())
    grouped = collections.defaultdict(list)
    for row in selected:
        grouped[row["pool_id"]].append(row)
    results = []
    differences = []
    started = time.monotonic()
    score_cache_hits = 0
    with fe.cached_matching(), fe.scoring_engine(fe.ENGINE / "measurement_engine.zip", fe.ENGINE / "working_models.py") as (engine, models):
        parameters = dataclasses.asdict(models.MODELS["B8L2"])
        for pool_id, old_rows in sorted(grouped.items()):
            pool = pools[pool_id]
            with gzip.open(LEGACY / "pools" / pool_id / "states.json.gz", "rt", encoding="utf-8") as f:
                state_payload = json.load(f)
            old_states = {r["team_id"]: r["automatic"] for r in state_payload["states"] if r["team_id"] in {x["team_id"] for x in old_rows}}
            del state_payload
            cache = {}
            for old in old_rows:
                workers = old["member_workers"].split("|")
                assert old["reference_id"] == pool["meta"]["reference_id"]
                assert old["reference_version"] == pool["meta"]["reference_version"]
                by_worker = {r["worker_id"]: r for r in pool["records"]}
                assert sorted(by_worker[w]["object_id"] for w in workers) == sorted(old["member_object_ids"].split("|"))
                native_state = old_states[old["team_id"]]
                key = runner.digest([native_state["n"] == 2, len(native_state["node_consensus"]["nodes"]), native_state["candidate"]])
                score_cache_hits += int(key in cache)
                new = runner.evaluate_one(pool, workers, engine, models, cache, full_state=True)
                new_state = new.pop("full_state")
                row = {"team_id": old["team_id"], "team_key_new": new["team_key"], "pool_id": pool_id,
                       "image": old["image"], "building": old["building"], "k": int(old["k"]),
                       "members_exact": sorted(new["member_workers"]) == sorted(workers) and sorted(new["member_object_ids"]) == sorted(old["member_object_ids"].split("|")),
                       "state_exact": fe.canonical(native_state) == fe.canonical(new_state),
                       "geometry_exact": fe.canonical(native_state["candidate"]) == fe.canonical(new["geometry"]),
                       "old_state_sha256": fe.digest(native_state), "new_state_sha256": fe.digest(new_state),
                       "fusion_seconds": new["fusion_seconds"], "score_seconds": new["score_seconds"]}
                for field in NUMERIC + DISCRETE:
                    a, b = parse(old.get(field)), new.get(field)
                    row["old_" + field], row["new_" + field] = a, b
                    if field in NUMERIC and a is not None and b is not None:
                        row["delta_" + field] = float(b) - float(a)
                        equal = abs(row["delta_" + field]) <= 1e-9
                    else:
                        equal = a == b
                        if field in NUMERIC:
                            row["delta_" + field] = None
                    if not equal:
                        differences.append({"team_id": old["team_id"], "field": field, "old": a, "new": b})
                for field in ["members_exact", "state_exact", "geometry_exact"]:
                    if not row[field]:
                        differences.append({"team_id": old["team_id"], "field": field, "old": True, "new": False})
                results.append(row)
                print(json.dumps({"completed": len(results), "total": len(selected), "pool_id": pool_id,
                                  "k": row["k"], "old_status": old["score_status"], "state_exact": row["state_exact"],
                                  "delta_B8L2": row["delta_B8L2"], "delta_D10": row["delta_D10"]}), flush=True)
                del new, new_state
    with (OUT / "HISTORICAL_PARITY.csv").open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(results[0]))
        writer.writeheader(); writer.writerows(results)
    summary = {
        "purpose": "Independent implementation parity only; no new scientific validation results read",
        "selected_teams": len(results), "pools": len(grouped), "images": len({r["image"] for r in results}),
        "buildings": len({r["building"] for r in results}), "workers": len({w for r in selected for w in r["member_workers"].split("|")}),
        "sizes": dict(collections.Counter(r["k"] for r in results)), "statuses": dict(collections.Counter(r["old_score_status"] for r in results)),
        "all_members_exact": all(r["members_exact"] for r in results), "all_states_exact": all(r["state_exact"] for r in results),
        "all_geometries_exact": all(r["geometry_exact"] for r in results), "mismatches": differences,
        "numeric_tolerance": 1e-9,
        "max_abs_differences": {field: max([abs(r["delta_" + field]) for r in results if r["delta_" + field] is not None], default=None) for field in NUMERIC},
        "gap": fe.WORKING_GAP, "B8L2_parameters": parameters, "D10_only_change": "direction_scale_deg=10.0 (verified source)",
        "N1_applied": False, "score_cache_reuse_hits": score_cache_hits,
        "runner_unchanged_during_audit": sha(RUNNER) == sha(snapshot),
        "file_provenance": file_provenance, "elapsed_seconds": time.monotonic() - started,
        "jobs": 1, "blas_threads": 1, "python_executable": sys.executable,
        "packages": {name: importlib.metadata.version(name) for name in ("numpy", "pandas", "scipy", "scikit-learn", "shapely")}
    }
    save("HISTORICAL_PARITY_SUMMARY.json", summary)
    print(json.dumps({k: v for k, v in summary.items() if k not in ("file_provenance", "B8L2_parameters")}, ensure_ascii=False, indent=2), flush=True)
    if differences:
        raise SystemExit("Historical implementation parity failed; inspect mismatches")


if __name__ == "__main__":
    main()
