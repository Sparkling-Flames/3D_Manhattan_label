#!/usr/bin/env python3
"""Independently rebuild and audit frozen requests, without reading fusion results.

The generators are run unchanged, sequentially in a separate temporary directory.
Every request is then checked against the original and independently against the
frozen pool membership and labels. A small JSON receipt is the only deliverable;
rebuilt manifests are scratch inputs and must be excluded from the final ZIP.
"""
from __future__ import annotations

import os
for _name in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS"):
    os.environ[_name] = "1"

import argparse
from collections import Counter, defaultdict
import csv
import gc
import gzip
import hashlib
import importlib.metadata
import json
import math
from pathlib import Path
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[2]
COMPOSITION = Path("analysis/composition")
OUT = ROOT / "analysis/independent"
SNAPSHOT = Path("restored/work_personnel_typing_A_20261019/recovered/work_v2_20261019/fusion/INPUT_SNAPSHOT.json.gz")
SPLIT = COMPOSITION / "SPLIT.json"
LABELS = [Path("analysis/forward/results/worker_labels.csv.gz"), Path("analysis/reverse/worker_labels.csv.gz")]
CONDITION_SPEC = Path("analysis/forward/condition_experiment_spec.json")
FREEZE = COMPOSITION / "VALIDATION_FREEZE.json"

# Independently recorded original file hashes before rebuilding any request.
EXPECTED = {
    "SCREEN_REQUESTS.json.gz": "edfb3b39977bed726d239edaa5889900f415f4eebf70310b3d0f8fcdf25e5ddd",
    "DISCOVERY_GRID_REQUESTS.json.gz": "02da799ae9cd2c7a7444b342f10a925dbc42294421d276c9fc545d1bfd112299",
    "DISCOVERY_BLOCK_REQUESTS.json.gz": "af2a6fa99bc45dba4d4241d669438b67cc2b01d5ba50e96032a24058d0d656b1",
    "VALIDATION_BLOCK_REQUESTS.json.gz": "202814a68491129ff332205c1392cc98217ff9ce672fb7c0227a9f3e01ef38aa",
    "DISCOVERY_CURVE_REQUESTS.json.gz": "c34247528d46e68e64cd7204d90ebfcda9a3b9c719087fe341319e55383b65d9",
    "VALIDATION_CURVE_REQUESTS.json.gz": "b96212a008d09cdea6531cd1a1b0a10552aabef1b46063ce21d7df7d8bee360a",
    "DISCOVERY_CONFIRM_REQUESTS.json.gz": "2644052e0bbfb1e9b61fdb02358009d28a18bb5b78e3ca661605ce4d85acd811",
    "VALIDATION_CONFIRM_REQUESTS.json.gz": "51548dcee2cb110279b0c59e027eeb0c71be106cc10264ad4c30e7aa1cd40a08",
    "DISCOVERY_NESTED_REQUESTS.json.gz": "3190d2d0406eb2794ffe361978dd51612b67deb0af0abe5c82996ca486b76d3c",
    "VALIDATION_NESTED_REQUESTS.json.gz": "651b0ad34e433cb6a0b4e8c65613c990547d5fd0666718b636c29ea8f38132c0",
    "DISCOVERY_CONDITION_REQUESTS.json.gz": "f6a6da3aa7c9910b92db1cfd96bcbb1706e045d163b002d22b9455afa296923b",
    "VALIDATION_CONDITION_REQUESTS.json.gz": "d67683b894e28f9a6696ed78371592b78c45da391928b449130e0f7bebb15396",
    "SPECIAL_REQUESTS.json.gz": "61fe555a6d783d6b60f978f62a2f3c18493e7b44dc5ddab318c469e6c009553e",
    "FINAL_REQUESTS.json.gz": "b033cd6974be8eb6e3add5f266a0869baf8175849b80d933cd9dd1e3f9f82be9",
}
JOBS = [
    ("SCREEN_REQUESTS.json.gz", "design_screen.py", None),
    ("DISCOVERY_GRID_REQUESTS.json.gz", "design_compositions.py", "BREADTH_SPEC.json"),
    ("DISCOVERY_BLOCK_REQUESTS.json.gz", "design_blocks.py", "BLOCK_DISCOVERY_SPEC.json"),
    ("VALIDATION_BLOCK_REQUESTS.json.gz", "design_blocks.py", "BLOCK_VALIDATION_SPEC.json"),
    ("DISCOVERY_CURVE_REQUESTS.json.gz", "design_curves.py", "CURVES_DISCOVERY_SPEC.json"),
    ("VALIDATION_CURVE_REQUESTS.json.gz", "design_curves.py", "CURVES_VALIDATION_SPEC.json"),
    ("DISCOVERY_CONFIRM_REQUESTS.json.gz", "design_curves.py", "CONFIRM_DISCOVERY_SPEC.json"),
    ("VALIDATION_CONFIRM_REQUESTS.json.gz", "design_curves.py", "CONFIRM_VALIDATION_SPEC.json"),
    ("DISCOVERY_NESTED_REQUESTS.json.gz", "design_nested.py", "NESTED_DISCOVERY_SPEC.json"),
    ("VALIDATION_NESTED_REQUESTS.json.gz", "design_nested.py", "NESTED_VALIDATION_SPEC.json"),
    ("DISCOVERY_CONDITION_REQUESTS.json.gz", "design_condition_requests.py", "discovery"),
    ("VALIDATION_CONDITION_REQUESTS.json.gz", "design_condition_requests.py", "validation"),
    ("SPECIAL_REQUESTS.json.gz", "design_special.py", None),
]
FINAL_COMPONENTS = [
    "DISCOVERY_CONFIRM_REQUESTS.json.gz", "DISCOVERY_NESTED_REQUESTS.json.gz",
    "VALIDATION_CURVE_REQUESTS.json.gz", "VALIDATION_CONFIRM_REQUESTS.json.gz",
    "VALIDATION_BLOCK_REQUESTS.json.gz", "VALIDATION_NESTED_REQUESTS.json.gz",
    "VALIDATION_CONDITION_REQUESTS.json.gz",
]


def sha(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def canonical(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"), allow_nan=False).encode()


def read(path):
    with (gzip.open(path, "rt", encoding="utf-8") if str(path).endswith(".gz") else Path(path).open(encoding="utf-8")) as f:
        return json.load(f)


def save(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.suffix == ".gz":
        path.write_bytes(gzip.compress(canonical(value), compresslevel=5, mtime=0))
    else:
        path.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")


def exact_team_key(pool_id, workers):
    # This ASCII identity serializer is independent of the fusion wrapper import.
    raw = json.dumps(sorted(workers), sort_keys=True, separators=(",", ":")).encode()
    return pool_id + "__" + hashlib.sha256(raw).hexdigest()[:20]


def load_labels():
    mappings, seen = defaultdict(dict), set()
    for path in LABELS:
        with gzip.open(ROOT / path, "rt", encoding="utf-8", newline="") as f:
            for row in csv.DictReader(f):
                domain = "all" if row["domain"] == "global" else row["domain"]
                key = row["method_id"], domain, row["worker_id"]
                assert key not in seen
                seen.add(key)
                if row["known"].lower() == "true" and row["class_id"] not in ("", "unknown"):
                    mappings[key[:2]][key[2]] = row["class_id"]
    return mappings


def applicable(pool, domain):
    layer = pool["meta"]["layer"]
    if domain == "all":
        return layer == "ordinary_manual"
    if domain in ("easy", "medium", "hard"):
        return layer == "ordinary_manual" and {"简单": "easy", "中等": "medium", "困难": "hard"}.get(pool["meta"]["difficulty"]) == domain
    if domain == "doorway":
        return layer == "doorway_manual"
    if domain in ("semi_v1", "semi_new"):
        return layer == "ordinary_semi"
    return layer == domain


def bounded_count(capacities, target):
    # Independent dynamic programming, rather than importing count enumeration.
    ways = [1] + [0] * target
    for cap in capacities:
        nxt = [0] * (target + 1)
        for total in range(target + 1):
            nxt[total] = sum(ways[total - x] for x in range(min(total, cap) + 1))
        ways = nxt
    return ways[target]


def request_signature(row):
    return [row["pool_id"], row["k"], sorted(row["worker_ids"]),
            sorted(row["counts"].items()) if "counts" in row else None, row["team_key"]]


def mapping_and_groups(row, pools, mappings, condition_rules):
    key = row["method_id"], row["domain"]
    mapping = mappings[key]
    if row["request_id"].startswith("condition__"):
        rule = condition_rules[row["phase"], *key, row["pool_id"]]
        groups = rule["class_members"]
        assert all(mapping[w] == c for c, ws in groups.items() for w in ws)
    else:
        groups = {c: [] for c in sorted(set(mapping.values()))}
        for record in pools[row["pool_id"]]["records"]:
            if record["worker_id"] in mapping:
                groups[mapping[record["worker_id"]]].append(record["worker_id"])
    return mapping, groups


def audit_requests(payload, pools, mappings, condition_rules, split):
    teams, images, buildings, workers, pids, methods, cells = set(), set(), set(), set(), set(), set(), set()
    phase_counts, layer_counts, difficulty_counts, sizes = Counter(), Counter(), Counter(), Counter()
    cell_rows, group_cache = defaultdict(list), {}
    for row in payload["requests"]:
        pid, ws, k, phase = row["pool_id"], row["worker_ids"], row["k"], row["phase"]
        pool = pools[pid]
        by_worker = {r["worker_id"]: r for r in pool["records"]}
        assert ws == sorted(ws) and len(ws) == len(set(ws)) == k and set(ws) <= by_worker.keys()
        assert row["team_key"] == exact_team_key(pid, ws)
        if phase in ("discovery", "validation"):
            assert pool["meta"]["building"] in split[phase + "_buildings"]
        else:
            assert phase == "special_descriptive" and pool["meta"]["layer"].startswith("special_")
        if "counts" in row:
            assert applicable(pool, row["domain"])
            group_key = (phase, row["method_id"], row["domain"], pid)
            if group_key not in group_cache:
                group_cache[group_key] = mapping_and_groups(row, pools, mappings, condition_rules)
            mapping, groups = group_cache[group_key]
            assert set(row["counts"]) == set(groups)
            assert all(w in mapping and w in groups[mapping[w]] for w in ws)
            actual = {c: sum(mapping[w] == c for w in ws) for c in groups}
            assert actual == row["counts"] and sum(actual.values()) == k
            assert row["composition"] == "|".join(f"{c}:{actual[c]}" for c in sorted(actual))
            if row["request_id"].startswith("condition__") and row["domain"] in ("semi_v1", "semi_new"):
                expected_origin = "v1" if row["domain"] == "semi_v1" else "new"
                assert {by_worker[w]["origin"] for w in ws} == {expected_origin}
            methods.add((row["method_id"], row["domain"]))
            cell = (row["method_id"], row["domain"], pid, k, row["composition"])
            cells.add(cell)
        else:
            assert row["family"] in ("uniform_screen", "special_descriptive")
            cell = pid, k
        cell_rows[cell].append(row)
        teams.add(row["team_key"]); workers.update(ws); pids.add(pid)
        images.add(pool["meta"]["image"]); buildings.add(pool["meta"]["building"])
        phase_counts[phase] += 1; layer_counts[pool["meta"]["layer"]] += 1
        difficulty_counts[pool["meta"]["difficulty"]] += 1; sizes[k] += 1
    support = {
        "requests": len(payload["requests"]), "unique_teams": len(teams),
        "repeated_rows_beyond_unique_teams": len(payload["requests"]) - len(teams),
        "pools": len(pids), "images": len(images), "buildings": len(buildings), "workers": len(workers),
        "method_domains": [list(x) for x in sorted(methods)], "composition_cells": len(cells),
        "requests_by_phase": dict(phase_counts), "requests_by_layer": dict(layer_counts),
        "requests_by_difficulty": dict(difficulty_counts), "requests_by_size": dict(sorted(sizes.items())),
    }
    return support, cell_rows, group_cache, (teams, images, buildings, workers, pids)


def audit_coverage(name, payload, cell_rows, groups_cache, condition_rules, pools, mappings):
    if "BLOCK" in name:
        prefix = "VALIDATION_" if name.startswith("VALIDATION") else ""
        block = read(OUT / (prefix + "BLOCK_DESIGN_AUDIT.json"))
        assert block["source_hashes"][str(COMPOSITION / name)] == EXPECTED[name]
        assert block["requests_n"] == len(payload["requests"])
        return {"independent_all_event_audit": prefix + "BLOCK_DESIGN_AUDIT.json", **block["ledger"],
                "sample_scope": "Quota-based stratified pattern sampling; <=16 mixed count vectors, <=64 core vectors, one member draw per attempted pattern; not exhaustive teams."}
    if "NESTED" in name:
        requests = {r["request_id"]: r for r in payload["requests"]}
        consumed = set()
        for chain in payload["chains"]:
            fixed, added = chain["fixed_workers"], chain["added_worker_order"]
            assert len(fixed) == len(set(fixed)) == chain["fixed_n"]
            assert len(added) == len(set(added)) and not set(fixed) & set(added)
            mapping, groups = groups_cache[chain["phase"], chain["method_id"], chain["domain"], chain["pool_id"]]
            assert all(mapping[w] == chain["fixed_class"] for w in fixed)
            assert set(added) == set(groups[chain["added_class"]])
            assert chain["possible_fixed_member_sets"] == math.comb(len(groups[chain["fixed_class"]]), len(fixed))
            assert len(chain["points"]) == min(len(added), len(fixed) + 3) + 1
            previous = set()
            for n, point in enumerate(chain["points"]):
                assert point["added_n"] == n and point["worker_ids"] == sorted(fixed + added[:n])
                assert point["k"] == len(fixed) + n
                if n:
                    assert set(point["worker_ids"]) - previous == {added[n - 1]}
                previous = set(point["worker_ids"])
                rid = chain["chain_id"] + "__n" + str(point["k"])
                assert all(requests[rid][key] == point[key] for key in ("k", "worker_ids", "counts", "team_key"))
                consumed.add(rid)
            assert chain["threshold_comparison"] == {"before_n": 2 * len(fixed), "after_n": 2 * len(fixed) + 1}
        assert consumed == requests.keys()
        return {"chains": len(payload["chains"]), "every_chain_exactly_nested": True,
                "sample_scope": "Specified fixed classes, added classes and fixed-size nodes only; finite random chains, not all fixed-member sets or addition orders."}
    grid_cells, feasible_total, exhaustive_member_cells = {}, 0, 0
    possible_member_teams_sum, sampled_member_teams_sum = 0, 0
    for ledger in payload.get("ledger", []):
        if "composition" in ledger:
            cell = (ledger["method_id"], ledger["domain"], ledger["pool_id"], ledger["k"], ledger["composition"])
            rows = cell_rows[cell]
            row = rows[0]
            _, groups = groups_cache[row["phase"], row["method_id"], row["domain"], row["pool_id"]]
            caps = {c: len(ws) for c, ws in groups.items()}
            assert ledger["available_class_sizes"] == caps
            possible = math.prod(math.comb(caps[c], n) for c, n in row["counts"].items())
            sampled = len(rows)
            assert ledger["possible_member_teams"] == str(possible)
            assert ledger["sampled_member_teams"] == sampled == len({r["team_key"] for r in rows})
            assert ledger["exhaustive_members"] == (sampled == possible)
            exhaustive_member_cells += ledger["exhaustive_members"]
            group = cell[:4]
            info = (ledger["feasible_compositions"], ledger["selected_compositions"], ledger["exhaustive_compositions"], tuple(caps.values()), set())
            stored = grid_cells.setdefault(group, info)
            assert stored[:4] == info[:4]
            assert cell[4] not in stored[4]
            stored[4].add(cell[4])
        else:
            cell = ledger["pool_id"], ledger["k"]
            rows = cell_rows[cell]
            possible = int(ledger.get("total_possible_teams", ledger.get("possible_teams")))
            assert possible == math.comb(len(pools[cell[0]]["records"]), cell[1])
            sampled = len(rows)
            assert sampled == ledger["sampled_teams"] == len({r["team_key"] for r in rows})
            assert ledger["exhaustive_teams"] == (sampled == possible)
            exhaustive_member_cells += ledger["exhaustive_teams"]
        possible_member_teams_sum += possible; sampled_member_teams_sum += sampled
    if payload.get("ledger"):
        assert sampled_member_teams_sum == len(payload["requests"])
    exhaustive_composition_cells, full_simplex_total, selected_total = 0, 0, 0
    for group, (feasible, selected, exhausted, caps, observed) in grid_cells.items():
        assert len(observed) == selected and exhausted == (selected == feasible)
        full = bounded_count(caps, group[-1])
        if "GRID" in name or "CONDITION" in name:
            assert feasible == full
        else:
            assert selected <= full
        full_simplex_total += full; selected_total += selected
        feasible_total += feasible; exhaustive_composition_cells += selected == full
    result = {
        "ledger_cells": len(payload.get("ledger", [])), "exhaustive_actual_member_cells": exhaustive_member_cells,
        "sampled_member_teams_across_cells": sampled_member_teams_sum,
        "possible_member_teams_across_selected_cells": str(possible_member_teams_sum),
    }
    if grid_cells:
        result.update(method_pool_size_cells=len(grid_cells), selected_compositions=selected_total,
                      full_feasible_simplex_compositions=full_simplex_total,
                      omitted_feasible_simplex_compositions=full_simplex_total - selected_total,
                      cells_covering_all_feasible_compositions=exhaustive_composition_cells)
    if "curve_index" in payload:
        feasible_positions, declared_cells = set(), set()
        for point in payload["curve_index"]:
            key = (payload["spec"]["phase"], point["method_id"], point["domain"], point["pool_id"])
            if key not in groups_cache:
                probe = dict(point, phase=payload["spec"]["phase"], request_id="curve__coverage_only")
                groups_cache[key] = mapping_and_groups(probe, pools, mappings, condition_rules)
            _, groups = groups_cache[key]
            declared_cells.add((point["method_id"], point["domain"], point["pool_id"], point["k"]))
            feasible = all(point["counts"][c] <= len(groups[c]) for c in groups)
            assert feasible == point["feasible"]
            if feasible:
                feasible_positions.add((point["method_id"], point["domain"], point["pool_id"], point["k"], point["composition"]))
        assert feasible_positions == cell_rows.keys()
        declared_full_simplex = 0
        zero_line_simplex = 0
        for mid, domain, pid, size in declared_cells:
            _, groups = groups_cache[payload["spec"]["phase"], mid, domain, pid]
            full = bounded_count([len(ws) for ws in groups.values()], size)
            declared_full_simplex += full
            if (mid, domain, pid, size) not in grid_cells:
                zero_line_simplex += full
        result.update(curve_positions=len(payload["curve_index"]),
                      infeasible_curve_positions=sum(not r["feasible"] for r in payload["curve_index"]),
                      declared_population_feasible_method_pool_size_cells=len(declared_cells),
                      declared_cells_with_no_feasible_selected_line=len(declared_cells - grid_cells.keys()),
                      represented_cell_full_feasible_simplex_compositions=full_simplex_total,
                      no_feasible_line_cell_full_simplex_compositions=zero_line_simplex,
                      full_feasible_simplex_compositions=declared_full_simplex,
                      omitted_feasible_simplex_compositions=declared_full_simplex - selected_total,
                      full_simplex_denominator="All declared method/pool/size cells with enough known workers overall, including cells with no feasible selected line position",
                      sample_scope="All feasible integer positions on declared one-dimensional composition lines; remaining simplex compositions omitted, concrete teams sampled.")
    elif "GRID" in name:
        result["sample_scope"] = "All feasible count vectors where within cap; otherwise deterministic separated pure/boundary/interior coverage. K6/K8 dense image panel only. Concrete teams sampled unless ledger marks exact enumeration."
    elif "CONDITION" in name:
        result["sample_scope"] = "All feasible count vectors at declared sizes for supported own-condition classes and source-qualified pools; only specified candidates, concrete teams sampled."
    else:
        result["sample_scope"] = "Uniform class-independent team sampling at declared sizes plus complete pool; exhaustive only when the finite team count is no greater than the replicate cap."
    return result


def commands(out_dir):
    common = ["--snapshot", str(SNAPSHOT), "--split", str(SPLIT)]
    for label in LABELS:
        common.extend(["--labels", str(label)])
    result = []
    for name, script, spec in JOBS:
        cmd = [sys.executable, str(COMPOSITION / script)]
        if script == "design_screen.py":
            cmd += ["--snapshot", str(SNAPSHOT), "--split", str(SPLIT)]
        elif script == "design_special.py":
            cmd += ["--snapshot", str(SNAPSHOT)]
        elif script == "design_condition_requests.py":
            cmd += ["--spec", str(CONDITION_SPEC), "--phase", spec]
        else:
            cmd += common + ["--spec", str(COMPOSITION / spec)]
        result.append((name, cmd + ["--out", str(out_dir / name)]))
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--rebuilt-dir", type=Path, default=OUT / "rebuilt_requests")
    parser.add_argument("--reuse-rebuilt", action="store_true", help="Audit previously generated scratch requests; generation receipts must exist")
    args = parser.parse_args()
    out_dir = args.rebuilt_dir.resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    started = time.monotonic()
    freeze = read(ROOT / FREEZE)
    dependencies = {SNAPSHOT, SPLIT, CONDITION_SPEC, FREEZE, *LABELS,
                    COMPOSITION / "fusion_runner.py", COMPOSITION / "materialize_stages.py", Path(__file__).relative_to(ROOT)}
    for _, script, spec in JOBS:
        dependencies.add(COMPOSITION / script)
        if spec and script != "design_condition_requests.py":
            dependencies.add(COMPOSITION / spec)
    dependencies.update(Path(p) for p in freeze["file_sha256"])
    source_hashes = {str(p): sha(ROOT / p) for p in sorted(dependencies)}
    freeze_checks = {p: source_hashes[p] == expected for p, expected in freeze["file_sha256"].items()}
    assert all(freeze_checks.values()), "A dependency no longer matches the validation freeze"
    original_hashes = {name: sha(ROOT / COMPOSITION / name) for name in EXPECTED}
    assert original_hashes == EXPECTED, "An original manifest changed after the independent pre-audit capture"
    split = read(ROOT / SPLIT)
    sets = [set(split[p + "_buildings"]) for p in ("history", "discovery", "validation")]
    assert not (sets[0] & sets[1] or sets[0] & sets[2] or sets[1] & sets[2])
    pools = {p["pool_id"]: p for p in read(ROOT / SNAPSHOT)["images"]}
    assert all(len(p["records"]) == len({r["worker_id"] for r in p["records"]}) for p in pools.values())
    mappings = load_labels()
    condition = read(ROOT / CONDITION_SPEC)
    condition_rules = {(r["stage"], r["method_id"], r["domain"], r["pool_id"]): r for r in condition["rules"]}
    assert len(condition_rules) == len(condition["rules"])
    result = {
        "schema": "personnel_composition_request_reproduction_audit_v1",
        "scope": "All 13 primary request manifests plus the derived FINAL concatenation. No fusion outcomes, validation scientific results, or cached geometries read.",
        "independent_member_checks": ["Unique request IDs", "Exact pool, k, sorted workers, class counts and recomputed team key", "Full request metadata equality", "Pool membership and frozen label count recount", "Building phase eligibility", "Own Semi source eligibility", "Ledger support recount", "Nested exact addition chains"],
        "source_sha256": source_hashes, "validation_freeze_files_match": freeze_checks,
        "jobs": 1, "blas_threads": 1, "python_executable": sys.executable,
        "packages": {p: importlib.metadata.version(p) for p in ("numpy", "pandas", "scipy", "scikit-learn")},
        "reuse_previously_generated_scratch_manifests": args.reuse_rebuilt,
        "manifests": [], "failures": [],
    }
    global_sets = [set() for _ in range(5)]
    all_request_ids, request_total = set(), 0
    generation_receipt = out_dir / "GENERATION_RECEIPTS.json"
    previous_receipts = read(generation_receipt) if args.reuse_rebuilt else {}
    for index, (name, cmd) in enumerate(commands(out_dir), 1):
        t = time.monotonic()
        print(json.dumps({"step": "audit_rebuilt_start" if args.reuse_rebuilt else "rebuild_start", "index": index, "of": len(JOBS), "manifest": name}), flush=True)
        if not args.reuse_rebuilt:
            completed = subprocess.run(cmd, cwd=ROOT, check=True, text=True, capture_output=True)
            previous_receipts[name] = {"command": cmd, "generation_seconds": round(time.monotonic() - t, 3), "generator_stdout": completed.stdout.strip()}
            save(generation_receipt, previous_receipts)
        else:
            assert name in previous_receipts and (out_dir / name).exists()
        original, rebuilt = read(ROOT / COMPOSITION / name), read(out_dir / name)
        old_by_id = {r["request_id"]: r for r in original["requests"]}
        new_by_id = {r["request_id"]: r for r in rebuilt["requests"]}
        assert len(old_by_id) == len(original["requests"]) and len(new_by_id) == len(rebuilt["requests"])
        ids_equal = old_by_id.keys() == new_by_id.keys()
        member_mismatches, row_mismatches = [], []
        old_digest, new_digest = hashlib.sha256(), hashlib.sha256()
        for rid in sorted(old_by_id.keys() | new_by_id.keys()):
            old, new = old_by_id.get(rid), new_by_id.get(rid)
            a, b = request_signature(old) if old else None, request_signature(new) if new else None
            old_digest.update(canonical([rid, a]) + b"\n"); new_digest.update(canonical([rid, b]) + b"\n")
            if a != b:
                member_mismatches.append(rid)
            if old != new:
                row_mismatches.append(rid)
        support, cells, groups_cache, supports = audit_requests(rebuilt, pools, mappings, condition_rules, split)
        coverage = audit_coverage(name, rebuilt, cells, groups_cache, condition_rules, pools, mappings)
        new_sha = sha(out_dir / name)
        entry = {"name": name, "original_sha256": original_hashes[name], "rebuilt_sha256": new_sha,
                 "byte_identical": new_sha == original_hashes[name], "request_id_sets_identical": ids_equal,
                 "every_member_signature_identical": not member_mismatches, "every_full_request_identical": not row_mismatches,
                 "member_signature_original_sha256": old_digest.hexdigest(), "member_signature_rebuilt_sha256": new_digest.hexdigest(),
                 "mismatched_member_requests": len(member_mismatches), "mismatched_full_requests": len(row_mismatches),
                 "first_mismatches": (member_mismatches or row_mismatches)[:10],
                 "exact_generation_command": previous_receipts[name]["command"],
                 "generation_seconds": previous_receipts[name]["generation_seconds"],
                 "bytes": (out_dir / name).stat().st_size, "support": support, "coverage": coverage}
        result["manifests"].append(entry)
        if not (entry["byte_identical"] and ids_equal and not member_mismatches and not row_mismatches):
            result["failures"].append({"manifest": name, "member_mismatches": len(member_mismatches), "full_request_mismatches": len(row_mismatches), "byte_identical": entry["byte_identical"]})
        assert not all_request_ids & new_by_id.keys(), "Repeated request IDs across primary manifests"
        all_request_ids.update(new_by_id); request_total += len(new_by_id)
        for acc, addition in zip(global_sets, supports):
            acc.update(addition)
        save(OUT / "REPRODUCTION_AUDIT.json", result)
        print(json.dumps({"step": "verified", "manifest": name, "requests": len(new_by_id), "byte_identical": entry["byte_identical"], "member_mismatches": len(member_mismatches)}), flush=True)
        del original, rebuilt, old_by_id, new_by_id, cells, groups_cache
        gc.collect()
    # Independent reconstruction of materialize_stages.py's declared append order.
    # Receipts preserve logical original destinations; hashes come from rebuilt bytes.
    rows, receipts = [], []
    for name in FINAL_COMPONENTS:
        p = out_dir / name
        payload = read(p)
        rows.extend(payload["requests"])
        receipts.append({"path": str(ROOT / COMPOSITION / name), "phase": payload["spec"]["phase"],
                         "requests": len(payload["requests"]), "sha256": sha(p)})
        del payload
    final = {"component_manifests": receipts, "freeze_sha256": sha(ROOT / FREEZE), "requests": rows}
    save(out_dir / "FINAL_REQUESTS.json.gz", final)
    original_final = read(ROOT / COMPOSITION / "FINAL_REQUESTS.json.gz")
    assert len(rows) == len({r["request_id"] for r in rows})
    final_rows_equal = original_final["requests"] == rows
    final_byte_equal = sha(out_dir / "FINAL_REQUESTS.json.gz") == original_hashes["FINAL_REQUESTS.json.gz"]
    result["derived_final"] = {"name": "FINAL_REQUESTS.json.gz", "components_in_order": FINAL_COMPONENTS,
                               "requests": len(rows), "unique_teams": len({r["team_key"] for r in rows}),
                               "every_request_and_order_identical": final_rows_equal, "byte_identical": final_byte_equal,
                               "original_sha256": original_hashes["FINAL_REQUESTS.json.gz"],
                               "rebuilt_sha256": sha(out_dir / "FINAL_REQUESTS.json.gz"),
                               "receipt_note": "Logical source destinations preserve the original recorded absolute paths; content hashes and rows are rebuilt independently."}
    if not (final_rows_equal and final_byte_equal):
        result["failures"].append({"manifest": "FINAL_REQUESTS.json.gz", "byte_identical": final_byte_equal, "requests_equal": final_rows_equal})
    result["all_primary_support"] = {"request_rows": request_total, "unique_request_ids": len(all_request_ids),
                                     "unique_teams": len(global_sets[0]), "images": len(global_sets[1]),
                                     "buildings": len(global_sets[2]), "workers": len(global_sets[3]), "pools": len(global_sets[4]),
                                     "repeated_rows_beyond_unique_teams": request_total - len(global_sets[0]),
                                     "derived_final_not_added_again": True}
    result["actual_coverage_and_omissions"] = [
        "SCREEN and BREADTH are discovery-only selection panels; no validation-wide reranking or full breadth grid was planned. Frozen targeted blocks/curves/confirm/nested/condition have both phases.",
        "Global labels were frozen from ten history buildings. All discovery and validation request buildings are disjoint. This check confirms request eligibility and frozen-file equality, not external blind data or new-worker generalization.",
        "Complete finite count-vector coverage is distinguished from sampled concrete membership. Sum of possible member teams across selected cells is not a count of distinct teams or independent samples.",
        "Curves cover every feasible integer position on declared lines, not all combinations of every class proportion. The full feasible simplex counts in each stage quantify the omitted count vectors.",
        "Block ledger candidate counts are a capped design frame, not all feasible real teams. The recorded one-draw core failures do not establish mathematical infeasibility.",
        "Nested additions cover specified class pairs, fixed sizes and sampled member orders only; they change total team size and supplement the same-n matched blocks.",
        "Own-condition candidates require eligible historical labels and matching Semi source opportunities. Unsupported pool-candidate counts are retained; missing opportunity is not assigned low ability.",
        "SPECIAL includes all qualified special pools descriptively without unsupported personnel categories; no ordinary, doorway or Semi category result is inferred from that branch.",
        "Confirm-stage seed changes produce independently generated requests, but concrete teams can overlap previous stages; actual distinct teams are recounted across every primary manifest.",
    ]
    result["condition_unsupported_pool_candidates"] = len(condition["unsupported_pool_candidates"])
    result["condition_unsupported_by_reason"] = dict(Counter(r["reason"] for r in condition["unsupported_pool_candidates"]))
    result["all_sources_unchanged_during_audit"] = all(sha(ROOT / p) == digest for p, digest in source_hashes.items())
    result["all_original_manifests_unchanged_during_audit"] = all(sha(ROOT / COMPOSITION / p) == digest for p, digest in original_hashes.items())
    result["all_passed"] = not result["failures"] and result["all_sources_unchanged_during_audit"] and result["all_original_manifests_unchanged_during_audit"]
    result["rebuilt_scratch_total_bytes"] = sum(p.stat().st_size for p in out_dir.glob("*REQUESTS.json.gz"))
    result["independent_generator_total_seconds"] = sum(r["generation_seconds"] for r in previous_receipts.values())
    result["delivery_exclusion"] = "Exclude rebuilt_requests and its generation receipts; retain this small audit JSON and the audit/generator source only."
    result["elapsed_seconds"] = round(time.monotonic() - started, 3)
    result["audit_script_sha256"] = sha(Path(__file__))
    save(OUT / "REPRODUCTION_AUDIT.json", result)
    print(json.dumps({k: result[k] for k in ("all_passed", "all_primary_support", "derived_final", "elapsed_seconds")}, ensure_ascii=False), flush=True)
    if not result["all_passed"]:
        raise SystemExit("Reproduction audit failed; see small JSON receipt")


if __name__ == "__main__":
    main()
