#!/usr/bin/env python3
"""Replay only explicitly selected representative cases using the frozen engine.

Usage:
  python audit_representative_cases.py --case path/to/case.json [--case ...]
  python audit_representative_cases.py --selection path/to/CASE_SELECTION.json

The selection file may be a list of case paths or {"cases": [...]}, where each
entry is a path or {"case_json": "path"}. Relative case paths are resolved from
the selection file's directory. No search or case selection occurs here.

Cases use the documented case_visuals.py schema. The direct native fusion and
score path is invoked, rather than the thin wrapper's evaluate_one. Only a
small parity receipt is written; full states and duplicate final geometries
are never saved. Final geometries remain in the selected case JSON artifacts.
"""
from __future__ import annotations

import os
for _name in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS"):
    os.environ[_name] = "1"

import argparse
from collections import Counter
import csv
import dataclasses
import gzip
import hashlib
import importlib.metadata
from itertools import combinations
import json
import math
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "analysis/composition"))
import fusion_runner
from geometry_diagnostics import diagnose
from summarize_grid import pair_metrics
from shapely.geometry import Polygon


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read(path):
    with (gzip.open(path, "rt", encoding="utf-8") if str(path).endswith(".gz") else Path(path).open(encoding="utf-8")) as f:
        return json.load(f)


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False).encode()


def identity_key(pool_id, workers):
    raw = json.dumps(sorted(workers), sort_keys=True, separators=(",", ":")).encode()
    return pool_id + "__" + hashlib.sha256(raw).hexdigest()[:20]


def load_labels():
    result = {}
    for path in (ROOT / "analysis/forward/results/worker_labels.csv.gz", ROOT / "analysis/reverse/worker_labels.csv.gz"):
        with gzip.open(path, "rt", encoding="utf-8", newline="") as f:
            for row in csv.DictReader(f):
                if row["known"].lower() == "true" and row["class_id"] not in ("", "unknown"):
                    domain = "all" if row["domain"] == "global" else row["domain"]
                    result[row["method_id"], domain, row["worker_id"]] = row["class_id"]
    return result


def selected_paths(args):
    paths = [p.resolve() for p in args.case]
    if args.selection:
        selection_path = args.selection.resolve()
        selection = read(selection_path)
        entries = selection["cases"] if isinstance(selection, dict) else selection
        for entry in entries:
            value = entry if isinstance(entry, str) else entry["case_json"]
            p = Path(value)
            paths.append((selection_path.parent / p).resolve() if not p.is_absolute() else p.resolve())
    if not paths:
        raise ValueError("At least one explicit case is required; this audit never chooses cases")
    assert len(paths) == len(set(paths)), "Duplicate case paths in the explicit selection"
    return paths


def numeric_equal(a, b, tolerance):
    if a is None or b is None:
        return a is None and b is None, None
    if isinstance(a, bool) or isinstance(b, bool):
        return a == b, None
    if isinstance(a, (int, float)) and isinstance(b, (int, float)):
        assert math.isfinite(a) and math.isfinite(b)
        delta = float(b) - float(a)
        return abs(delta) <= tolerance, delta
    return a == b, None


def independent_joint_checks(a, b, recorded, fe, tolerance):
    """Recount the conjunction independently, using final native geometries."""
    ga, gb = a["geometry"] or {}, b["geometry"] or {}
    floor_difference = bound = None
    if a.get("complete_floor_evaluable") and b.get("complete_floor_evaluable"):
        pa, pb = Polygon(ga["footprint"]), Polygon(gb["footprint"])
        if pa.is_valid and pb.is_valid and pa.area > 0 and pb.area > 0:
            floor_difference = pa.symmetric_difference(pb).area / pa.union(pb).area
    aa, bb = ga.get("points"), gb.get("points")
    if aa is not None and bb is not None and len(aa) == len(bb) and len(aa) >= 6:
        bottom, top = fe.angular(aa[::2], bb[::2]), fe.angular(aa[1::2], bb[1::2])
        n = len(aa) // 2
        bound = min(max(max(float(bottom[i, (i + s) % n]), float(top[i, (i + s) % n])) for i in range(n)) for s in range(n))
    assert numeric_equal(recorded["floor_jaccard_difference"], floor_difference, tolerance)[0]
    assert numeric_equal(recorded["structure_bound_cyclic_deg"], bound, tolerance)[0]
    dq = abs(a["B8L2"] - b["B8L2"]) if a.get("B8L2") is not None and b.get("B8L2") is not None else None
    node_difference = abs(a["nodes"] - b["nodes"]) if a.get("nodes") is not None and b.get("nodes") is not None else None
    checks = {}
    for name, q, f, s in (("strict", 1., .02, 2.), ("main", 2., .05, 3.), ("wide", 5., .10, 5.)):
        decision = bool(a.get("complete_evaluable") and b.get("complete_evaluable") and dq is not None and dq <= q
                        and node_difference == 0 and floor_difference is not None and floor_difference <= f
                        and bound is not None and bound <= s)
        assert decision == recorded["joint_stable_" + name]
        checks[name] = decision
    return {"team_a": a["team_key"], "team_b": b["team_key"], "abs_B8L2": dq,
            "floor_difference_independent": floor_difference, "bound_cyclic_deg_independent": bound,
            "node_count_difference": node_difference, "joint_stability": checks,
            "all_independent_checks_passed": True}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--case", type=Path, action="append", default=[])
    parser.add_argument("--selection", type=Path)
    parser.add_argument("--restored", type=Path, default=ROOT / "restored")
    parser.add_argument("--out", type=Path, default=ROOT / "analysis/independent/REPRESENTATIVE_CASE_PARITY.json")
    parser.add_argument("--tolerance", type=float, default=1e-9)
    args = parser.parse_args()
    paths = selected_paths(args)
    input_hashes = {str(p): sha(p) for p in paths}
    if args.selection:
        input_hashes[str(args.selection.resolve())] = sha(args.selection.resolve())
    fe = fusion_runner.init_engine(args.restored)
    pools = {p["pool_id"]: p for p in fe.load_pools()}
    mappings = load_labels()
    code_paths = [Path(__file__), Path(fusion_runner.__file__), ROOT / "analysis/composition/geometry_diagnostics.py",
                  ROOT / "analysis/composition/summarize_grid.py", Path(fe.__file__).with_name("pool_io.py"),
                  Path(fe.__file__), Path(fe.__file__).parent / "INPUT_SNAPSHOT.json.gz",
                  fe.SOURCE / "tools/thesis_main/analysis/consensus_delivery_20261008.py",
                  fe.SOURCE / "tools/thesis_main/analysis/ring_correspondence_20261007.py",
                  fe.SOURCE / "tools/thesis_main/analysis/wall_consensus_population_20261014.py",
                  fe.SOURCE / "tools/thesis_main/analysis/wall_consensus_quality_20261015.py",
                  fe.SOURCE / "tools/thesis_main/analysis/quality_b8l2_d10_20261017.py",
                  fe.ENGINE / "measurement_engine.zip", fe.ENGINE / "working_models.py",
                  ROOT / "analysis/forward/results/worker_labels.csv.gz", ROOT / "analysis/reverse/worker_labels.csv.gz"]
    source_hashes = {str(p): sha(p) for p in code_paths}
    result = {
        "schema": "selected_representative_case_parity_v1",
        "scope": "Only explicit frozen representative cases; direct native fusion and B8L2/D10 replay plus separate geometry diagnostics; no case selection or broad result search",
        "jobs": 1, "blas_threads": 1, "numeric_tolerance": args.tolerance,
        "source_sha256": source_hashes, "case_input_sha256": input_hashes,
        "gap": fe.WORKING_GAP, "N1_applied": False,
        "D10_only_change": "direction_scale_deg=10.0 versus B8L2's 8.0; frozen matching and reference retained",
        "diagnostic_interpretation": "Reference-relative wall coverage and geometric true-turn recall, separate from B8L2; not validated necessary-structure correctness",
        "cases": [], "mismatches": [],
    }
    started = time.monotonic()
    replays, teams_seen, workers_seen, pools_seen = {}, set(), set(), set()
    case_ids, block_manifests, embedded_workers = set(), {}, set()
    with fe.cached_matching(), fe.scoring_engine(fe.ENGINE / "measurement_engine.zip", fe.ENGINE / "working_models.py") as (engine, models):
        result["B8L2_parameters"] = dataclasses.asdict(models.MODELS["B8L2"])
        for path in paths:
            case = read(path)
            cid = case["case_id"]
            assert cid not in case_ids
            case_ids.add(cid)
            pool = pools[case["pool_id"]]
            assert case["pool_digest"] == fusion_runner.digest(pool)
            by_worker = {r["worker_id"]: r for r in pool["records"]}
            assert len(by_worker) == len(pool["records"])
            reference = case["reference"]
            assert reference["reference_id"] == pool["meta"]["reference_id"]
            assert reference["reference_version"] == pool["meta"]["reference_version"]
            assert canonical(case["meta"]) == canonical(fe.clean(pool["meta"]))
            for field in ("target_id", "reference_version", "points_1024x512", "floor_xz_h", "full_reference_available"):
                assert canonical(reference[field]) == canonical(fe.clean(pool["reference"][field])), (cid, "reference", field)
            supplied_members = {m["worker_id"]: m for m in case.get("members", [])}
            assert len(supplied_members) == len(case.get("members", []))
            embedded_workers.update(supplied_members)
            method, domain = case.get("method_id"), case.get("domain", "all")
            for worker, member in supplied_members.items():
                record = by_worker[worker]
                assert member["object_id"] == record["object_id"] and member["origin"] == record["origin"]
                assert canonical(member["points"]) == canonical(fe.clean(record["points"]))
                assert canonical(member["frozen_record"]) == canonical(fe.clean(record)), (cid, worker, "frozen_record")
                if method:
                    assert member["class_id"] == mappings[method, domain, worker]
            case_result = {"case_id": cid, "path": str(path), "pool_id": pool["pool_id"],
                           "image": pool["meta"]["image"], "building": pool["meta"]["building"],
                           "reference_id": pool["meta"]["reference_id"], "reference_version": pool["meta"]["reference_version"],
                           "reference_geometry_exact": True,
                           "original_full_pool_digest_exact": True,
                           "reference_floor_sha256": hashlib.sha256(canonical(reference["floor_xz_h"])).hexdigest(),
                           "supplied_member_annotations_exact": True,
                           "all_embedded_frozen_records_exact": True,
                           "saved_original_pool_meta_exact": True,
                           "class_labels_checked_against_frozen_history": bool(method), "teams": []}
            for team in case["teams"]:
                ws = sorted(team["member_workers"])
                assert len(ws) == len(set(ws)) == team["k"] and set(ws) <= by_worker.keys()
                assert team["team_key"] == identity_key(pool["pool_id"], ws)
                assert sorted(team["member_object_ids"]) == sorted(by_worker[w]["object_id"] for w in ws)
                if "counts" in team:
                    assert set(ws) <= supplied_members.keys(), "Class-count verification needs supplied case members"
                    counts = Counter(supplied_members[w]["class_id"] for w in ws)
                    assert set(counts) <= team["counts"].keys()
                    assert {c: counts[c] for c in team["counts"]} == team["counts"]
                key = team["team_key"]
                if key not in replays:
                    selected = [by_worker[w] for w in ws]
                    state = fe.compact(fe.fuse(selected, gap=fe.WORKING_GAP)["automatic"])
                    assert state["n"] == len(ws)
                    assert {m["id"] for g in state["identity_groups"] for m in g["members"]} == {r["id"] for r in selected}
                    score = fe.compute_score(state, pool, engine, models)
                    geom = fe.clean(state["candidate"])
                    replays[key] = {"scores": fe.clean(score), "geometry": geom,
                                    "summary": fe.clean(fe.summarize_state(state)),
                                    "diagnostics": diagnose(geom.get("footprint"), reference["floor_xz_h"]),
                                    "transition_state": {"n": state["n"], "identity_groups": fe.clean(state["identity_groups"])},
                                    "state_sha256": fe.digest(state)}
                    replays[key]["pair_row"] = fe.clean({**pool["meta"], "team_key": key, "k": len(ws),
                        "member_workers": ws, "new_n": sum(by_worker[w]["origin"] == "new" for w in ws),
                        "geometry": geom, **fe.summarize_state(state), **score,
                        **fusion_runner.reference_structure(geom.get("points"), pool["reference"]["points_1024x512"])})
                    del state
                replay = replays[key]
                geom_exact = canonical(team["geometry"]) == canonical(replay["geometry"])
                row = {"team_key": key, "label": team.get("label"), "k": len(ws),
                       "member_workers": ws, "member_object_ids": [by_worker[w]["object_id"] for w in ws],
                       "counts": team.get("counts"), "exact_members": True, "geometry_exact": geom_exact,
                       "expected_geometry_sha256": hashlib.sha256(canonical(team["geometry"])).hexdigest(),
                       "native_geometry_sha256": hashlib.sha256(canonical(replay["geometry"])).hexdigest(),
                       "native_full_state_sha256": replay["state_sha256"], "score_checks": {}, "diagnostic_checks": {}}
                if "mechanism_groups" in team:
                    groups = [{field: group.get(field) for field in ("feature_id", "support", "selected", "center")} |
                              {"members": [{field: member.get(field) for field in ("id", "worker", "pair_index", "points")} for member in group["members"]]}
                              for group in replay["transition_state"]["identity_groups"]]
                    row["mechanism_groups_exact"] = canonical(groups) == canonical(team["mechanism_groups"])
                    if not row["mechanism_groups_exact"]:
                        result["mismatches"].append({"case_id": cid, "team_key": key, "field": "mechanism_groups"})
                if not geom_exact:
                    result["mismatches"].append({"case_id": cid, "team_key": key, "field": "geometry"})
                for field in ("B8L2", "D10", "score_status"):
                    expected, actual = team[field], replay["scores"].get(field)
                    equal, delta = numeric_equal(expected, actual, args.tolerance)
                    row["score_checks"][field] = {"expected": expected, "replayed": actual, "delta": delta, "passed": equal}
                    if not equal:
                        result["mismatches"].append({"case_id": cid, "team_key": key, "field": field, "expected": expected, "actual": actual})
                for field in ("nodes", "geometry_status", "complete_evaluable", "connection_available"):
                    if field in team:
                        equal, delta = numeric_equal(team[field], replay["summary"].get(field), args.tolerance)
                        row["score_checks"][field] = {"expected": team[field], "replayed": replay["summary"].get(field), "delta": delta, "passed": equal}
                        if not equal:
                            result["mismatches"].append({"case_id": cid, "team_key": key, "field": field})
                for field, expected in team.get("diagnostics", {}).items():
                    assert field in replay["diagnostics"], (cid, "unknown diagnostic field", field)
                    actual = replay["diagnostics"][field]
                    if isinstance(expected, (list, dict)):
                        equal, delta = canonical(expected) == canonical(actual), None
                    else:
                        equal, delta = numeric_equal(expected, actual, args.tolerance)
                    row["diagnostic_checks"][field] = {"passed": equal, "delta": delta}
                    if not equal:
                        result["mismatches"].append({"case_id": cid, "team_key": key, "field": field})
                row["replayed_core_diagnostics"] = {field: replay["diagnostics"].get(field) for field in ("diag_status", "diag_wall_coverage_03", "diag_wall_coverage_05", "diag_corner_recall_05")}
                case_result["teams"].append(row)
                teams_seen.add(key); workers_seen.update(ws); pools_seen.add(pool["pool_id"])
                print(json.dumps({"case_id": cid, "team_key": key, "geometry_exact": geom_exact,
                                  "delta_B8L2": row["score_checks"]["B8L2"]["delta"],
                                  "delta_D10": row["score_checks"]["D10"]["delta"]}), flush=True)
            if "same_size_pair_diagnostics" in case:
                actual, independent = [], []
                for a, b in combinations(case["teams"], 2):
                    if a["k"] != b["k"]:
                        continue
                    ra, rb = replays[a["team_key"]]["pair_row"], replays[b["team_key"]]["pair_row"]
                    pair = fe.clean(dict(team_a=a["team_key"], team_b=b["team_key"], **pair_metrics(ra, rb)))
                    actual.append(pair)
                    independent.append(independent_joint_checks(ra, rb, pair, fe, args.tolerance))
                assert canonical(actual) == canonical(case["same_size_pair_diagnostics"])
                case_result["same_size_pair_diagnostics_exact_from_native"] = True
                case_result["independent_joint_decision_checks"] = independent
            if "matched_block_design" in case:
                event = case["matched_block_design"]
                phase = event["phase"]
                manifest_path = ROOT / "analysis/composition" / (phase.upper() + "_BLOCK_REQUESTS.json.gz")
                if phase not in block_manifests:
                    source_hashes[str(manifest_path)] = sha(manifest_path)
                    block_manifests[phase] = {e["event_id"]: e for e in read(manifest_path)["events"]}
                assert canonical(event) == canonical(block_manifests[phase][case["block_event_id"]])
                core = set(event["core_workers"])
                sets = {arm: set(event[arm + "_workers"]) for arm in "ABC"}
                assert sets["A"] & sets["B"] == sets["A"] & sets["C"] == core
                assert len(sets["A"] - sets["B"]) == len(sets["A"] - sets["C"]) == event["m"]
                panels = {t["team_key"]: t for t in case["teams"]}
                origins = {}
                for arm in "ABC":
                    assert sorted(sets[arm]) == panels[event[arm + "_team_key"]]["member_workers"]
                    origins[arm] = dict(Counter(by_worker[w]["origin"] for w in sets[arm]))
                if event["matching"] == "source_matched":
                    assert origins["A"] == origins["B"] == origins["C"]
                case_result["matched_block_exact_against_frozen_manifest"] = True
                case_result["matched_block_core_m_source_checks"] = {"core": sorted(core), "m": event["m"], "origins": origins}
            if "full_member_chain" in case:
                chain = case["full_member_chain"]
                manifest_path = ROOT / "analysis/composition" / (chain["phase"].upper() + "_NESTED_REQUESTS.json.gz")
                source_hashes[str(manifest_path)] = sha(manifest_path)
                original_chains = {r["chain_id"]: r for r in read(manifest_path)["chains"]}
                assert canonical(chain) == canonical(original_chains[chain["chain_id"]])
                assert set(chain["fixed_workers"] + chain["added_worker_order"]) <= supplied_members.keys()
                case_result["full_member_chain_matches_frozen_request_manifest"] = True
                case_result["all_chain_member_records_embedded"] = True
            if "nested_vote_bookkeeping" in case:
                team_by_key = {t["team_key"]: t for t in case["teams"]}
                checks = []
                for recorded in case["nested_vote_bookkeeping"]:
                    before, after = recorded["before_team"], recorded["after_team"]
                    old, new = replays[before]["transition_state"], replays[after]["transition_state"]
                    old_workers, new_workers = set(team_by_key[before]["member_workers"]), set(team_by_key[after]["member_workers"])
                    assert old_workers < new_workers and sorted(new_workers - old_workers) == recorded["added_workers"]
                    native_transition = fe.clean(fe.transition(old, new))
                    assert native_transition == recorded["native_transition"]
                    old_observation_sets = [{(m["id"], m["pair_index"]) for m in group["members"]} for group in old["identity_groups"]]
                    shared = set().union(*old_observation_sets)
                    losses = []
                    for group, observations in zip(old["identity_groups"], old_observation_sets):
                        matched = [nxt for nxt in new["identity_groups"] if {(m["id"], m["pair_index"]) for m in nxt["members"]} & shared == observations]
                        assert len(matched) <= 1
                        if group["selected"] and matched and not matched[0]["selected"]:
                            nxt = matched[0]
                            losses.append({"before_group": group["feature_id"], "after_group": nxt["feature_id"],
                                           "old_observations": sorted(observations), "support_before": group["support"], "support_after": nxt["support"],
                                           "center_before": group["center"], "center_after": nxt["center"]})
                    assert canonical(fe.clean(losses)) == canonical(recorded["unchanged_identity_lost_groups"])
                    assert len(losses) == native_transition["unchanged_identity_vote_losses"]
                    checks.append({"before_team": before, "after_team": after, "native_transition_exact": True,
                                   "lost_group_evidence_exact": True, "replayed_transition": native_transition,
                                   "threshold_before": (old["n"] + 1) // 2, "threshold_after": (new["n"] + 1) // 2,
                                   "lost_group_supports": [[g["support_before"], g["support_after"]] for g in losses]})
                case_result["nested_vote_bookkeeping_checks"] = checks
                case_result["mechanism_boundary"] = "Unchanged old-observation partitions and changing vote admission are algorithm bookkeeping, not semantic necessary-node labels."
            result["cases"].append(case_result)
    result["actual_support"] = {"cases": len(paths), "team_panels": sum(len(c["teams"]) for c in result["cases"]),
                                "unique_replayed_teams": len(teams_seen), "pools": len(pools_seen),
                                "images": len({pools[p]["meta"]["image"] for p in pools_seen}),
                                "buildings": len({pools[p]["meta"]["building"] for p in pools_seen}), "workers": len(workers_seen),
                                "embedded_workers_including_overlays_and_full_chains": len(embedded_workers)}
    result["all_inputs_and_sources_unchanged"] = all(sha(p) == digest for p, digest in {**source_hashes, **input_hashes}.items())
    result["all_passed"] = not result["mismatches"] and result["all_inputs_and_sources_unchanged"]
    result["elapsed_seconds"] = time.monotonic() - started
    result["packages"] = {p: importlib.metadata.version(p) for p in ("numpy", "pandas", "scipy", "scikit-learn", "shapely")}
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    print(json.dumps({"all_passed": result["all_passed"], "support": result["actual_support"], "output": str(args.out)}, ensure_ascii=False), flush=True)
    if not result["all_passed"]:
        raise SystemExit("Representative-case parity failed; see the small audit receipt")


if __name__ == "__main__":
    main()
