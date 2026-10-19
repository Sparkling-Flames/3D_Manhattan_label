#!/usr/bin/env python3
"""Rebuild selected cases from their embedded frozen member records only.

This quick path imports the pinned fusion/scoring code through --restored but
never calls load_pools, reads the full input snapshot, or consults fusion caches.
It preserves saved point coordinates, pair binding, ring order and reference.
Only native automatic fusion with the saved frozen parameters is supported.

Examples (paths may be absolute or relative to the current directory):
  python replay_saved_cases.py --restored restored --case cases/C01.json --out replay
  python replay_saved_cases.py --restored restored --selection CASE_SELECTION.json \
      --out replay --render --font fonts/NotoSansSC-Regular.ttf

CASE_SELECTION.json is a list of paths or {"cases": [{"case_json": "cases/C01.json"}]}.
Relative entries are resolved from that file's directory. A case's relative
image_path is resolved from its own directory. No download is attempted. With
--render, a missing original image skips image rendering and retains numeric
and final-geometry replay outputs. Without --render no original image is needed.
"""
from __future__ import annotations

import os
for _name in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS"):
    os.environ[_name] = "1"

import argparse
from collections import Counter
import copy
import dataclasses
import hashlib
import importlib.metadata
from itertools import combinations
import json
import math
from pathlib import Path
import re
import sys
import time

import fusion_runner
from geometry_diagnostics import diagnose

REFERENCE_FIELDS = ("target_id", "reference_version", "floor_xz_h", "points_1024x512", "full_reference_available")
SCORES = ("B8L2", "D10", "score_status", "IoU3D100", "iou_2d", "S_bottom_deg", "dir", "Hmean", "Hcenter", "omission", "extension", "height_mean_ratio")
SUMMARY_FIELDS = ("nodes", "below_four", "half_vote_nodes", "connection_available", "order_status", "order_tied", "geometry_status", "geometry_reason", "floor_evaluable", "complete_floor_evaluable", "complete_evaluable", "location_unresolved")


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False).encode()


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def save(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")


def read(path):
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def team_key(pool_id, workers):
    raw = json.dumps(sorted(workers), sort_keys=True, separators=(",", ":")).encode()
    return pool_id + "__" + hashlib.sha256(raw).hexdigest()[:20]


def compare_value(expected, actual, tolerance):
    if expected is None or actual is None:
        return expected is None and actual is None, None
    if isinstance(expected, bool) or isinstance(actual, bool):
        return expected == actual, None
    if isinstance(expected, (int, float)) and isinstance(actual, (int, float)):
        assert math.isfinite(expected) and math.isfinite(actual)
        delta = float(actual) - float(expected)
        return abs(delta) <= tolerance, delta
    return canonical(expected) == canonical(actual), None


def mechanism_groups(state):
    return [{key: group.get(key) for key in ("feature_id", "support", "selected", "center")} |
            {"members": [{key: member.get(key) for key in ("id", "worker", "pair_index", "points")} for member in group["members"]]}
            for group in state["identity_groups"]]


def nested_bookkeeping(before, after, states, fe):
    old, new = states[before["team_key"]], states[after["team_key"]]
    old_members = set(before["member_workers"])
    new_members = set(after["member_workers"])
    assert old_members < new_members
    shared = set().union(*({(m["id"], m["pair_index"]) for m in g["members"]} for g in old["identity_groups"]))
    restricted = {}
    for group in new["identity_groups"]:
        ids = frozenset((m["id"], m["pair_index"]) for m in group["members"]) & shared
        if ids:
            assert ids not in restricted
            restricted[ids] = group
    losses = []
    for group in old["identity_groups"]:
        ids = frozenset((m["id"], m["pair_index"]) for m in group["members"])
        if ids in restricted and group["selected"] and not restricted[ids]["selected"]:
            nxt = restricted[ids]
            losses.append({"before_group": group["feature_id"], "after_group": nxt["feature_id"],
                           "old_observations": sorted(ids), "support_before": group["support"], "support_after": nxt["support"],
                           "center_before": group["center"], "center_after": nxt["center"]})
    return fe.clean({"before_team": before["team_key"], "after_team": after["team_key"],
                     "added_workers": sorted(new_members - old_members), "native_transition": fe.transition(old, new),
                     "unchanged_identity_lost_groups": losses})


def pool_from_case(case):
    """Construct the local pool solely from fields contained in this case.

    meta.pool_n and case.pool_digest describe the original full qualified pool;
    this local pool contains only the supplied case members. No full-pool digest
    equality is claimed or needed to reproduce an explicit saved member team.
    """
    reference = {key: copy.deepcopy(case["reference"][key]) for key in REFERENCE_FIELDS}
    meta = copy.deepcopy(case["meta"])
    assert meta["pool_id"] == case["pool_id"]
    assert reference["target_id"] == case["reference"]["reference_id"] == meta["reference_id"]
    assert reference["reference_version"] == meta["reference_version"]
    records, seen_workers, seen_ids = [], set(), set()
    for member in case["members"]:
        record = copy.deepcopy(member["frozen_record"])
        assert record["worker_id"] == member["worker_id"] and record["worker"] == member["worker_id"]
        assert record["object_id"] == member["object_id"] and record["origin"] == member["origin"]
        assert canonical(record["points"]) == canonical(member["points"])
        assert record["worker_id"] not in seen_workers and record["id"] not in seen_ids
        seen_workers.add(record["worker_id"]); seen_ids.add(record["id"])
        records.append(record)
    assert len(records) <= meta["pool_n"]
    return {"pool_id": case["pool_id"], "meta": meta, "reference": reference,
            "records": sorted(records, key=lambda r: r["worker_id"])}


def check_embedded_block(case, by_worker, classes):
    """Check the saved A/B/C intervention using case records alone."""
    event = case["matched_block_design"]
    assert event["event_id"] == case["block_event_id"]
    assert all(event[k] == case[k] for k in ("pool_id", "method_id", "domain"))
    k, m = event["k"], event["m"]
    core, outgoing = set(event["core_workers"]), set(event["outgoing_workers"])
    within, cross = set(event["within_incoming"]), set(event["cross_incoming"])
    assert len(core) == k - m and len(outgoing) == len(within) == len(cross) == m
    assert not (core & (outgoing | within | cross) or outgoing & (within | cross))
    sets = {"A": core | outgoing, "B": core | within, "C": core | cross}
    by_key = {t["team_key"]: t for t in case["teams"]}
    origins = {}
    for arm, workers in sets.items():
        assert sorted(workers) == event[arm + "_workers"]
        assert event[arm + "_team_key"] == team_key(case["pool_id"], workers)
        panel = by_key[event[arm + "_team_key"]]
        assert panel["member_workers"] == sorted(workers) and panel["k"] == k
        origins[arm] = dict(Counter(by_worker[w]["origin"] for w in workers))
        expected = event["A_counts"] if arm in ("A", "B") else event["C_counts"]
        actual = Counter(classes[w] for w in workers)
        assert {c: actual[c] for c in expected} == expected and set(actual) <= expected.keys()
    assert sets["A"] & sets["B"] == sets["A"] & sets["C"] == core
    assert len(sets["A"] - sets["B"]) == len(sets["A"] - sets["C"]) == m
    for workers, field in ((outgoing, "outgoing_counts"), (within, "outgoing_counts"), (cross, "incoming_counts")):
        actual = Counter(classes[w] for w in workers)
        assert {c: actual[c] for c in event[field]} == event[field]
    assert event["A_counts"] != event["C_counts"]
    if event["matching"] == "source_matched":
        assert origins["A"] == origins["B"] == origins["C"]
        assert {by_worker[w]["origin"] for w in outgoing | within | cross} == {event["matched_origin"]}
    return {"embedded_block_identity_exact": True, "same_actual_core": True,
            "same_actual_replacement_m": m, "source_counts": origins,
            "source_counts_equal": origins["A"] == origins["B"] == origins["C"],
            "frozen_full_manifest_checked_here": False}


def replay_case(case, fe, engine, models, tolerance=1e-9):
    pool = pool_from_case(case)
    params = case["fusion_parameters"]
    assert params["gap"] == fe.WORKING_GAP
    assert params["entry"] == "consensus_delivery_20261008.fuse"
    assert params["N1_applied"] is False and params.get("manual_order") is None
    assert not params.get("assisted_partitions"), "This quick replay supports the frozen automatic branch"
    if case.get("scientific_commit"):
        assert case["scientific_commit"] == fe.COMMIT
    by_worker = {r["worker_id"]: r for r in pool["records"]}
    classes = {m["worker_id"]: m["class_id"] for m in case["members"]}
    updated = copy.deepcopy(case)
    updated["teams"] = []
    receipt = {
        "case_id": case["case_id"], "pool_id": pool["pool_id"],
        "image": pool["meta"]["image"], "building": pool["meta"]["building"],
        "original_pool_member_n": pool["meta"]["pool_n"], "embedded_case_member_n": len(pool["records"]),
        "original_pool_digest_provenance_only": case.get("pool_digest"),
        "embedded_records_sha256": hashlib.sha256(canonical(pool["records"])).hexdigest(),
        "reference_sha256": hashlib.sha256(canonical(pool["reference"])).hexdigest(),
        "full_snapshot_read": False, "previous_fusion_cache_read": False,
        "frozen_point_order_preserved": True, "B8L2_parameters": dataclasses.asdict(models.MODELS["B8L2"]),
        "fusion_parameters": params, "teams": [], "mismatches": [],
    }
    seen_teams, states = set(), {}
    for team in case["teams"]:
        workers = sorted(team["member_workers"])
        assert len(workers) == len(set(workers)) == team["k"] and set(workers) <= by_worker.keys()
        key = team_key(pool["pool_id"], workers)
        assert key == team["team_key"] and key not in seen_teams
        seen_teams.add(key)
        assert sorted(team["member_object_ids"]) == sorted(by_worker[w]["object_id"] for w in workers)
        if "counts" in team:
            count = Counter(classes[w] for w in workers)
            assert set(count) <= team["counts"].keys()
            assert {c: count[c] for c in team["counts"]} == team["counts"]
        records = [by_worker[w] for w in workers]
        native, error = None, None
        try:
            native = fe.compact(fe.fuse(records, gap=params["gap"])["automatic"])
            assert native["n"] == len(workers)
            assert {m["id"] for g in native["identity_groups"] for m in g["members"]} == {r["id"] for r in records}
        except (ValueError, ArithmeticError, RuntimeError, TypeError) as exc:
            error = "fusion: " + type(exc).__name__ + ": " + str(exc)
        if native is None:
            summary = fe.empty_summary(len(workers))
            score = {"score_status": "fusion_exception", "B8L2": None, "D10": None}
            geometry, native_hash, support = None, None, {}
        else:
            summary = fe.clean(fe.summarize_state(native))
            geometry = fe.clean(native["candidate"])
            native_hash = fe.digest(native)
            states[key] = {"n": native["n"], "identity_groups": fe.clean(native["identity_groups"])}
            ns = native["node_consensus"]["nodes"]
            support = {"minimum_support": native["minimum_support"], "node_supports": [n["support"] for n in ns],
                       "identity_groups_n": len(native["identity_groups"]),
                       "unselected_groups_n": sum(not g["selected"] for g in native["identity_groups"]),
                       "minority_observations_n": sum(g["support"] for g in native["identity_groups"] if not g["selected"])}
            try:
                score = fe.clean(fe.compute_score(native, pool, engine, models))
            except (ValueError, ArithmeticError, RuntimeError, TypeError) as exc:
                error = "measurement: " + type(exc).__name__ + ": " + str(exc)
                score = {"score_status": "measurement_exception", "B8L2": None, "D10": None}
        diag = diagnose((geometry or {}).get("footprint"), pool["reference"]["floor_xz_h"])
        new = dict(team, **summary, **support, **{k: score.get(k) for k in SCORES}, geometry=geometry, diagnostics=diag)
        new["new_n"] = sum(by_worker[w]["origin"] == "new" for w in workers)
        if native is not None:
            new.update(fusion_runner.reference_structure(geometry.get("points"), pool["reference"]["points_1024x512"]))
        if native is not None and "mechanism_groups" in team:
            new["mechanism_groups"] = fe.clean(mechanism_groups(native))
        updated["teams"].append(new)
        row = {"team_key": key, "label": team.get("label"), "k": len(workers), "members_exact": True,
               "native_state_sha256": native_hash, "geometry_exact": canonical(team["geometry"]) == canonical(geometry),
               "expected_geometry_sha256": hashlib.sha256(canonical(team["geometry"])).hexdigest(),
               "replayed_geometry_sha256": hashlib.sha256(canonical(geometry)).hexdigest(),
               "mechanism_groups_exact": "mechanism_groups" not in team or canonical(team["mechanism_groups"]) == canonical(new.get("mechanism_groups")),
               "score_checks": {}, "support_checks": {}, "diagnostics_exact": canonical(team.get("diagnostics", diag)) == canonical(diag),
               "replay_error": error}
        if not row["geometry_exact"]:
            receipt["mismatches"].append({"team_key": key, "field": "geometry"})
        if not row["diagnostics_exact"]:
            receipt["mismatches"].append({"team_key": key, "field": "diagnostics"})
        if not row["mechanism_groups_exact"]:
            receipt["mismatches"].append({"team_key": key, "field": "mechanism_groups"})
        for field in SCORES + SUMMARY_FIELDS:
            if field not in team:
                continue
            passed, delta = compare_value(team[field], new.get(field), tolerance)
            row["score_checks"][field] = {"expected": team[field], "replayed": new.get(field), "delta": delta, "passed": passed}
            if not passed:
                receipt["mismatches"].append({"team_key": key, "field": field})
        for field in support:
            if field in team:
                passed, delta = compare_value(team[field], support[field], tolerance)
                row["support_checks"][field] = {"passed": passed, "delta": delta}
                if not passed:
                    receipt["mismatches"].append({"team_key": key, "field": field})
        receipt["teams"].append(row)
        print(json.dumps({"case_id": case["case_id"], "team_key": key, "geometry_exact": row["geometry_exact"],
                          "B8L2_delta": row["score_checks"]["B8L2"]["delta"],
                          "D10_delta": row["score_checks"]["D10"]["delta"]}), flush=True)
    if "same_size_pair_diagnostics" in case:
        from summarize_grid import pair_metrics
        actual = [dict(team_a=a["team_key"], team_b=b["team_key"], **pair_metrics(a, b))
                  for a, b in combinations(updated["teams"], 2) if a["k"] == b["k"]]
        actual = fe.clean(actual)
        receipt["same_size_pair_diagnostics_exact"] = canonical(actual) == canonical(case["same_size_pair_diagnostics"])
        receipt["same_size_pair_n"] = len(actual)
        updated["same_size_pair_diagnostics"] = actual
        if not receipt["same_size_pair_diagnostics_exact"]:
            receipt["mismatches"].append({"field": "same_size_pair_diagnostics"})
    if "matched_block_design" in case:
        receipt["matched_block_checks"] = check_embedded_block(case, by_worker, classes)
    if "full_member_chain" in case:
        chain = case["full_member_chain"]
        fixed, order = chain["fixed_workers"], chain["added_worker_order"]
        assert len(fixed) == len(set(fixed)) == chain["fixed_n"]
        assert len(order) == len(set(order)) and not set(fixed) & set(order)
        assert set(fixed + order) <= by_worker.keys()
        assert all(classes[w] == chain["fixed_class"] for w in fixed)
        assert all(classes[w] == chain["added_class"] for w in order)
        for point in chain["points"]:
            workers = sorted(fixed + order[:point["added_n"]])
            assert point["worker_ids"] == workers and point["k"] == len(workers)
            assert point["team_key"] == team_key(pool["pool_id"], workers)
            count = Counter(classes[w] for w in workers)
            assert {c: count[c] for c in point["counts"]} == point["counts"]
        receipt["full_member_chain_identity_checked"] = True
        receipt["full_member_chain_points"] = len(chain["points"])
        receipt["chain_note"] = "Every saved point's identities/counts are checked; only selected team panels are fused by this quick command. All chain member records are embedded for additional chosen replays."
    if "nested_vote_bookkeeping" in case:
        by_key = {team["team_key"]: team for team in case["teams"]}
        actual = [nested_bookkeeping(by_key[row["before_team"]], by_key[row["after_team"]], states, fe) for row in case["nested_vote_bookkeeping"]]
        receipt["native_transition_and_lost_group_bookkeeping_exact"] = canonical(actual) == canonical(case["nested_vote_bookkeeping"])
        receipt["replayed_nested_vote_bookkeeping"] = actual
        receipt["mechanism_boundary"] = "Native identity/threshold bookkeeping only; an unchanged group losing a vote does not establish that node's semantic necessity or correctness."
        if not receipt["native_transition_and_lost_group_bookkeeping_exact"]:
            receipt["mismatches"].append({"field": "nested_vote_bookkeeping"})
    receipt["all_passed"] = not receipt["mismatches"]
    return updated, receipt


def selected_paths(args):
    paths = [p.resolve() for p in args.case]
    if args.selection:
        source = args.selection.resolve()
        selection = read(source)
        entries = selection["cases"] if isinstance(selection, dict) else selection
        for entry in entries:
            value = entry if isinstance(entry, str) else entry["case_json"]
            p = Path(value)
            paths.append((source.parent / p).resolve() if not p.is_absolute() else p.resolve())
    if not paths:
        raise ValueError("Provide explicit --case paths or a --selection file")
    assert len(paths) == len(set(paths)), "Duplicate selected case paths"
    return paths


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--restored", type=Path, required=True, help="Restored pinned engine/code root, supplied by the package bootstrap")
    parser.add_argument("--case", type=Path, action="append", default=[])
    parser.add_argument("--selection", type=Path)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--render", action="store_true")
    parser.add_argument("--font", type=Path)
    parser.add_argument("--tolerance", type=float, default=1e-9)
    args = parser.parse_args()
    paths = selected_paths(args)
    original_hashes = {str(p): sha(p) for p in paths}
    fe = fusion_runner.init_engine(args.restored)
    sources = [Path(__file__), Path(fusion_runner.__file__), Path(__file__).with_name("geometry_diagnostics.py"),
               Path(__file__).with_name("summarize_grid.py"),
               Path(fe.__file__), Path(fe.__file__).with_name("pool_io.py"),
               fe.SOURCE / "tools/thesis_main/analysis/consensus_delivery_20261008.py",
               fe.SOURCE / "tools/thesis_main/analysis/ring_correspondence_20261007.py",
               fe.SOURCE / "tools/thesis_main/analysis/wall_consensus_population_20261014.py",
               fe.SOURCE / "tools/thesis_main/analysis/wall_consensus_quality_20261015.py",
               fe.SOURCE / "tools/thesis_main/analysis/quality_b8l2_d10_20261017.py",
               fe.ENGINE / "measurement_engine.zip", fe.ENGINE / "working_models.py"]
    source_hashes = {str(p): sha(p) for p in sources}
    started = time.monotonic()
    receipts, case_ids, all_teams = [], set(), set()
    args.out.mkdir(parents=True, exist_ok=True)
    with fe.cached_matching(), fe.scoring_engine(fe.ENGINE / "measurement_engine.zip", fe.ENGINE / "working_models.py") as (engine, models):
        for path in paths:
            case = read(path)
            cid = case["case_id"]
            assert re.fullmatch(r"[A-Za-z0-9_.-]+", cid), "case_id must be a safe artifact basename"
            assert cid not in case_ids
            case_ids.add(cid)
            updated, receipt = replay_case(case, fe, engine, models, tolerance=args.tolerance)
            receipt["case_json"] = str(path)
            receipt["case_sha256"] = original_hashes[str(path)]
            receipt["render_status"] = "not_requested"
            if args.render:
                image_value = case.get("image_path")
                image_path = Path(image_value) if image_value else None
                if image_path and not image_path.is_absolute():
                    image_path = path.parent / image_path
                if image_path and image_path.is_file():
                    if case.get("image_sha256"):
                        assert sha(image_path) == case["image_sha256"]
                    from case_visuals import render_case
                    updated["image_path"] = str(image_path.resolve())
                    render_case(updated, args.out / "figures" / cid, font_path=str(args.font) if args.font else None)
                    receipt["render_status"] = "rendered_with_saved_original"
                else:
                    receipt["render_status"] = "skipped_missing_original_numeric_replay_retained"
            # Deliberately no full states or model caches: final geometries are enough.
            compact_output = {"case_id": cid, "pool_id": case["pool_id"], "reference": case["reference"],
                              "teams": [{k: t.get(k) for k in ("team_key", "member_workers", "member_object_ids", "counts", "k", "geometry", "diagnostics", *SCORES, *SUMMARY_FIELDS, "minimum_support", "node_supports")} for t in updated["teams"]],
                              "receipt": receipt}
            compact_output["same_size_pair_diagnostics"] = updated.get("same_size_pair_diagnostics", [])
            save(args.out / (cid + ".replay.json"), compact_output)
            receipts.append(receipt)
            all_teams.update(t["team_key"] for t in case["teams"])
    summary = {
        "schema": "saved_case_portable_replay_v1", "cases": receipts, "case_n": len(receipts),
        "unique_team_n": len(all_teams), "team_panels": sum(len(r["teams"]) for r in receipts),
        "full_snapshot_required": False, "fusion_cache_required": False, "originals_required_for_numeric_replay": False,
        "all_passed": all(r["all_passed"] for r in receipts),
        "all_case_files_unchanged": all(sha(p) == digest for p, digest in original_hashes.items()),
        "all_engine_files_unchanged": all(sha(p) == digest for p, digest in source_hashes.items()),
        "source_sha256": source_hashes, "case_sha256": original_hashes,
        "jobs": 1, "blas_threads": 1, "numeric_tolerance": args.tolerance,
        "elapsed_seconds": time.monotonic() - started,
        "python": sys.version, "packages": {p: importlib.metadata.version(p) for p in ("numpy", "pandas", "scipy", "scikit-learn", "shapely")},
        "qualification_note": "Embedded classes and full-pool provenance are supplied by the frozen case. This quick path checks internal membership/composition consistency; separate independent audits establish equality to the full snapshot and history labels.",
    }
    summary["all_passed"] &= summary["all_case_files_unchanged"] and summary["all_engine_files_unchanged"]
    save(args.out / "REPLAY_SUMMARY.json", summary)
    print(json.dumps({"all_passed": summary["all_passed"], "cases": len(receipts), "unique_teams": len(all_teams), "out": str(args.out)}, ensure_ascii=False), flush=True)
    if not summary["all_passed"]:
        raise SystemExit("Saved-case replay differs from the frozen case; inspect REPLAY_SUMMARY.json")


if __name__ == "__main__":
    main()
