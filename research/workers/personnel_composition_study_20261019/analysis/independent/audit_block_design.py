#!/usr/bin/env python3
"""Audit every generated A/B/C block identity without reading fusion outcomes.

Run only after the final generation manifest has been confirmed. This script
does not import the generator; members, counts, team hashes, source balance,
pool eligibility, support, and ledger accounting are independently recounted.
"""
from collections import Counter, defaultdict
import argparse
import csv
import gzip
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "analysis/independent"
MANIFEST = ROOT / "analysis/composition/DISCOVERY_BLOCK_REQUESTS.json.gz"
GENERATOR = ROOT / "analysis/composition/design_blocks.py"
SNAPSHOT = ROOT / "restored/work_personnel_typing_A_20261019/recovered/work_v2_20261019/fusion/INPUT_SNAPSHOT.json.gz"
SPLIT = ROOT / "analysis/composition/SPLIT.json"
LABELS = [ROOT / "analysis/forward/results/worker_labels.csv.gz", ROOT / "analysis/reverse/worker_labels.csv.gz"]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path):
    with (gzip.open(path, "rt", encoding="utf-8") if path.suffix == ".gz" else path.open(encoding="utf-8")) as f:
        return json.load(f)


def team_key(pool_id, members):
    raw = json.dumps(sorted(members), sort_keys=True, separators=(",", ":")).encode()
    return pool_id + "__" + hashlib.sha256(raw).hexdigest()[:20]


def applicable(pool, domain):
    layer = pool["meta"]["layer"]
    if domain == "all":
        return layer == "ordinary_manual"
    if domain in ("easy", "medium", "hard"):
        return layer == "ordinary_manual" and {"简单": "easy", "中等": "medium", "困难": "hard"}[pool["meta"]["difficulty"]] == domain
    if domain == "doorway":
        return layer == "doorway_manual"
    if domain in ("semi_v1", "semi_new"):
        return layer == "ordinary_semi"
    return layer == domain


def bounded_vector_count(capacities, target):
    # Independent dynamic program for the number of feasible class-count cores.
    dp = [1] + [0] * target
    for capacity in capacities:
        nxt = [0] * (target + 1)
        for total in range(target + 1):
            nxt[total] = sum(dp[total - count] for count in range(min(total, capacity) + 1))
        dp = nxt
    return dp[target]


def empty_support():
    return {key: set() for key in ("events", "pools", "images", "buildings", "workers", "teams", "cores", "ordered_triples", "compositions", "transitions")}


def add_support(support, event):
    support["events"].add(event["event_id"])
    support["pools"].add(event["pool_id"])
    support["images"].add(event["image"])
    support["buildings"].add(event["building"])
    for arm in ("A", "B", "C"):
        support["workers"].update(event[arm + "_workers"])
        support["teams"].add(event[arm + "_team_key"])
    support["cores"].add((event["pool_id"], tuple(event["core_workers"])))
    support["ordered_triples"].add(tuple(event[arm + "_team_key"] for arm in ("A", "B", "C")))
    ca, cc = tuple(sorted(event["A_counts"].items())), tuple(sorted(event["C_counts"].items()))
    support["compositions"].update([(event["method_id"], event["domain"], event["k"], ca), (event["method_id"], event["domain"], event["k"], cc)])
    support["transitions"].add((event["method_id"], event["domain"], event["k"], ca, cc))


def count_support(support):
    return {key + "_n": len(value) for key, value in support.items()}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--expected-manifest-sha256", required=True)
    parser.add_argument("--manifest", type=Path, default=MANIFEST)
    parser.add_argument("--expected-phase", choices=("discovery", "validation"), default="discovery")
    parser.add_argument("--output-prefix", default="")
    args = parser.parse_args()
    manifest_path = args.manifest.resolve()
    assert sha(manifest_path) == args.expected_manifest_sha256
    source_hashes = {str(p.relative_to(ROOT)): sha(p) for p in [manifest_path, GENERATOR, SNAPSHOT, SPLIT] + LABELS}
    manifest, split = read(manifest_path), read(SPLIT)
    pools = {p["pool_id"]: p for p in read(SNAPSHOT)["images"]}
    mappings = defaultdict(dict)
    labels_seen = set()
    for path in LABELS:
        with gzip.open(path, "rt", encoding="utf-8", newline="") as f:
            for row in csv.DictReader(f):
                domain = "all" if row["domain"] == "global" else row["domain"]
                identity = row["method_id"], domain, row["worker_id"]
                assert identity not in labels_seen
                labels_seen.add(identity)
                if row["known"].lower() == "true" and row["class_id"] not in ("", "unknown"):
                    mappings[identity[:2]][row["worker_id"]] = row["class_id"]
    phase = manifest["spec"]["phase"]
    assert phase == args.expected_phase
    eligible_buildings = set(split[phase + "_buildings"])
    requests = {r["request_id"]: r for r in manifest["requests"]}
    assert len(requests) == len(manifest["requests"]) == 3 * len(manifest["events"])
    events_by_cell = defaultdict(list)
    global_support, method_support = empty_support(), defaultdict(empty_support)
    stratum_support = defaultdict(empty_support)
    seen_events, consumed_requests = set(), set()
    new_count_differences = defaultdict(Counter)
    shape_transitions, m_counts, slots_counts = Counter(), Counter(), Counter()
    shared_incoming = Counter()
    whole_category_worker_removal = 0
    category_disappearance = 0
    for event in manifest["events"]:
        eid = event["event_id"]
        assert eid not in seen_events
        seen_events.add(eid)
        pool = pools[event["pool_id"]]
        assert event["phase"] == phase and pool["meta"]["building"] in eligible_buildings
        assert applicable(pool, event["domain"])
        for key in ("building", "image", "difficulty", "layer"):
            assert event[key] == pool["meta"][key]
        mapping = mappings[event["method_id"], event["domain"]]
        classes = sorted(set(mapping.values()))
        pool_workers = {r["worker_id"]: r for r in pool["records"]}
        k, m = event["k"], event["m"]
        groups = {name: set(event[name]) for name in ("core_workers", "outgoing_workers", "within_incoming", "cross_incoming")}
        for name, group in groups.items():
            assert len(group) == len(event[name])
            assert group <= pool_workers.keys() and group <= mapping.keys()
        core, outgoing, within, cross = (groups[name] for name in ("core_workers", "outgoing_workers", "within_incoming", "cross_incoming"))
        assert len(core) == k - m and len(outgoing) == len(within) == len(cross) == m
        assert not core & (outgoing | within | cross)
        assert not outgoing & (within | cross)
        teams = {arm: set(event[arm + "_workers"]) for arm in ("A", "B", "C")}
        assert teams["A"] == core | outgoing and teams["B"] == core | within and teams["C"] == core | cross
        assert all(len(team) == k for team in teams.values())
        assert teams["A"] & teams["B"] == teams["A"] & teams["C"] == core
        assert all(len(teams["A"] - teams[arm]) == len(teams[arm] - teams["A"]) == m for arm in ("B", "C"))
        counts = {arm: {c: sum(mapping[w] == c for w in team) for c in classes} for arm, team in teams.items()}
        assert counts["A"] == counts["B"] == event["A_counts"] and counts["C"] == event["C_counts"]
        assert counts["A"] != counts["C"]
        oc = {c: sum(mapping[w] == c for w in outgoing) for c in classes}
        ic = {c: sum(mapping[w] == c for w in cross) for c in classes}
        assert oc == event["outgoing_counts"] and ic == event["incoming_counts"]
        assert {c: sum(mapping[w] == c for w in within) for c in classes} == oc
        changed = sum(abs(oc[c] - ic[c]) for c in classes) // 2
        assert event["changed_category_slots"] == changed and 1 <= changed <= m
        out_classes, in_classes = sum(n > 0 for n in oc.values()), sum(n > 0 for n in ic.values())
        assert out_classes == event["replaced_classes"] and in_classes == event["incoming_classes"]
        assert event["pattern"] == ("single_class" if out_classes == in_classes == 1 else "multi_class")
        assert event["replaced_entire_categories"] == [c for c in classes if oc[c] > 0 and counts["A"][c] == oc[c]]
        whole_category_worker_removal += bool(event["replaced_entire_categories"])
        category_disappearance += any(counts["A"][c] > 0 and counts["C"][c] == 0 for c in classes)
        reserved = outgoing | within | cross
        core_capacities = [sum(mapping.get(w) == c and w not in reserved for w in pool_workers) for c in classes]
        vector_count = bounded_vector_count(core_capacities, k - m)
        assert event["core_composition_options"] == vector_count
        assert event["core_vectors_considered"] == min(64, vector_count)
        new_counts = {arm: sum(pool_workers[w]["origin"] == "new" for w in team) for arm, team in teams.items()}
        if event["matching"] == "source_matched":
            assert event["matched_origin"] in ("new", "v1")
            assert {pool_workers[w]["origin"] for w in outgoing | within | cross} == {event["matched_origin"]}
            assert len(set(new_counts.values())) == 1
        else:
            assert event["matching"] == "unrestricted" and event["matched_origin"] == "any"
        for arm in ("B", "C"):
            new_count_differences[event["matching"] + "_A_to_" + arm][new_counts[arm] - new_counts["A"]] += 1
        for arm in ("A", "B", "C"):
            workers = sorted(teams[arm])
            assert event[arm + "_workers"] == workers
            assert event[arm + "_team_key"] == team_key(event["pool_id"], workers)
            request_id = eid + "__" + arm
            request = requests[request_id]
            consumed_requests.add(request_id)
            for key, expected in dict(event_id=eid, arm=arm, phase=phase, family="matched_block", method_id=event["method_id"],
                                      domain=event["domain"], pool_id=event["pool_id"], k=k, worker_ids=workers,
                                      team_key=event[arm + "_team_key"], counts=counts[arm],
                                      composition="|".join(f"{c}:{counts[arm][c]}" for c in classes)).items():
                assert request[key] == expected
        cell = event["method_id"], event["domain"], event["pool_id"], k
        events_by_cell[cell].append(event)
        add_support(global_support, event)
        add_support(method_support[cell[:2]], event)
        stratum = (event["method_id"], event["domain"], k, m, event["matching"], event["matched_origin"], event["pattern"])
        add_support(stratum_support[stratum], event)
        shape_transitions[("pure" if out_classes == 1 else "mixed") + "_to_" + ("pure" if in_classes == 1 else "mixed")] += 1
        m_counts[m] += 1
        slots_counts[changed] += 1
        shared_incoming[f"m{m}__shared{len(within & cross)}"] += 1
    assert consumed_requests == requests.keys()
    ledger_cells = {}
    total_failure_reasons = Counter()
    total_candidates = total_attempts = exhaustive_cells = quota_cells = zero_event_cells = 0
    for row in manifest["ledger"]:
        cell = row["method_id"], row["domain"], row["pool_id"], row["k"]
        assert cell not in ledger_cells
        ledger_cells[cell] = row
        actual = events_by_cell[cell]
        assert row["accepted_events"] == len(actual) <= row["event_quota"]
        assert row["accepted_by_mode"] == dict(Counter(e["matching"] for e in actual))
        assert row["accepted_by_pattern"] == dict(Counter(e["pattern"] for e in actual))
        assert row["accepted_by_m"] == {str(k): v for k, v in Counter(e["m"] for e in actual).items()}
        assert row["attempted_patterns"] == len(actual) + sum(row["failure_reasons"].values())
        assert row["attempted_patterns"] <= row["finite_count_pattern_candidates"]
        assert row["all_count_pattern_candidates_attempted"] == (row["attempted_patterns"] == row["finite_count_pattern_candidates"])
        total_candidates += row["finite_count_pattern_candidates"]
        total_attempts += row["attempted_patterns"]
        exhaustive_cells += row["all_count_pattern_candidates_attempted"]
        quota_cells += len(actual) == row["event_quota"]
        zero_event_cells += not actual
        total_failure_reasons.update(row["failure_reasons"])
    expected_cells = set()
    skipped_insufficient_people = 0
    for method in manifest["spec"]["methods"]:
        mid = method["method_id"]
        for domain in method.get("domains", [d for m, d in mappings if m == mid]):
            mapping = mappings[mid, domain]
            for pool in pools.values():
                if pool["meta"]["building"] not in eligible_buildings or not applicable(pool, domain):
                    continue
                eligible_n = sum(r["worker_id"] in mapping for r in pool["records"])
                for k in method["sizes"]:
                    if k + 2 <= eligible_n:
                        expected_cells.add((mid, domain, pool["pool_id"], k))
                    else:
                        skipped_insufficient_people += 1
    assert expected_cells == ledger_cells.keys()
    # No source file changed during this single read/recount pass.
    assert all(sha(ROOT / path) == digest for path, digest in source_hashes.items())
    strata_rows = []
    names = ("method_id", "domain", "k", "m", "matching", "matched_origin", "pattern")
    for key, support in sorted(stratum_support.items()):
        strata_rows.append(dict(zip(names, key), **count_support(support)))
    with (OUT / (args.output_prefix + "BLOCK_SUPPORT_RECOUNT.csv")).open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(strata_rows[0]))
        writer.writeheader()
        writer.writerows(strata_rows)
    result = {
        "scope": f"Every event and request in the confirmed {phase} block design; no fusion outcome or scientific validation result read",
        "all_identity_and_composition_invariants_passed": True,
        "all_source_matched_branches_balanced": True,
        "all_request_links_and_exact_team_keys_passed": True,
        "all_ledger_accounting_and_eligible_cells_passed": True,
        "source_hashes": source_hashes, "requests_n": len(requests), **count_support(global_support),
        "repeated_request_rows_beyond_unique_teams": len(requests) - len(global_support["teams"]),
        "repeated_events_beyond_unique_ordered_triples": len(seen_events) - len(global_support["ordered_triples"]),
        "by_method": [{"method_id": key[0], "domain": key[1], **count_support(value)} for key, value in sorted(method_support.items())],
        "m_distribution": dict(m_counts), "changed_category_slots_distribution": dict(slots_counts),
        "outgoing_to_incoming_block_shape": dict(shape_transitions),
        "same_and_cross_incoming_shared_workers": dict(shared_incoming),
        "new_worker_count_change": {key: dict(value) for key, value in new_count_differences.items()},
        "events_with_all_original_workers_of_a_category_outgoing": whole_category_worker_removal,
        "events_with_a_category_absent_in_C_after_present_in_A": category_disappearance,
        "ledger": {"cells": len(ledger_cells), "candidate_patterns_in_capped_frame": total_candidates,
                   "attempted_patterns": total_attempts, "accepted_events": len(seen_events),
                   "failure_reasons": dict(total_failure_reasons), "all_capped_frame_patterns_attempted_cells": exhaustive_cells,
                   "quota_filled_cells": quota_cells, "zero_event_cells": zero_event_cells,
                   "skipped_cells_with_fewer_than_k_plus_2_eligible_workers": skipped_insufficient_people},
        "interpretation_limits": [
            "Stratified count-pattern sampling with a per-cell quota, not uniform population sampling or exhaustive real teams",
            "Multiclass vectors and core vectors are systematically capped; only one actual member draw per selected pattern",
            "core_capacity_after_one_member_draw is a sampled-member failure, not a proof that a count pattern is mathematically infeasible",
            "m is the exact real-person turnover; changed_category_slots can be smaller than m",
            "B and C may share incoming members; both share exactly the recorded core with A",
            "Whole-category original-worker removal does not imply that category disappears from C",
            "Known workers, repeated teams and many events do not create new independent images or buildings",
        ],
    }
    (OUT / (args.output_prefix + "BLOCK_DESIGN_AUDIT.json")).write_text(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    print(json.dumps({key: result[key] for key in ("all_identity_and_composition_invariants_passed", "all_source_matched_branches_balanced", "requests_n", "events_n", "teams_n", "pools_n", "images_n", "buildings_n", "workers_n", "outgoing_to_incoming_block_shape", "ledger")}, ensure_ascii=False))


if __name__ == "__main__":
    main()
