"""Audit this round's registered native batches without running any fusion.

One request manifest and one native pool are read at a time. A personnel crew is
encoded losslessly using a fixed, published worker-to-bit mapping; the main task
key is (frozen pool, exact crew). Neither a request row nor an event is an
independent image. Native caches contribute only teams actually requested by the
corresponding manifest. Old A's 122,082 historical replacement-pair observations are explicitly excluded.

Run from a restored study root (paths need not be this workstation's paths):
  python interchangeability_20261020/independent/audit_global_coverage.py --root .
No large task index or native cache is copied to the output directory.
"""
from __future__ import annotations

import argparse
import collections
import csv
import datetime
import functools
import gc
import gzip
import hashlib
import itertools
import json
import math
from pathlib import Path


STUDY = Path("interchangeability_20261020")
SNAPSHOT = Path("restored/work_personnel_typing_A_20261019/recovered/work_v2_20261019/fusion/INPUT_SNAPSHOT.json.gz")
SPLIT = Path("analysis/composition/SPLIT.json")
RUNNER = Path("analysis/composition/fusion_runner.py")
SCIENCE_COMMIT = "82c6164b0d4630de5316199c92aa405930973168"
FROZEN_INPUT_COMMIT = "e572eb73bedc4fe9056df838e458bab83c3fa423"


def batch(name, requests, native, phase, role, generator, freeze=()):
    req = STUDY / requests
    folder = STUDY / native
    return dict(batch_id=name, requests=str(req), native_dir=str(folder),
                run_receipt=str(folder / ("RUN_" + req.name.replace(".json.gz", "") + ".json")),
                phase=phase, role=role, generator=str(STUDY / generator),
                registration_files=[str(STUDY / p) for p in freeze])


# Order is a deterministic accounting convention, not an assertion of runtime
# chronology. All-pairs batch intersections are computed after the full scan.
REGISTRY = [
    batch("history_panel", "history_panel/history_requests.json.gz", "history_panel/native_runs", "history",
          "New frozen-history entrant panel for reverse training; old retained A pair observations excluded",
          "code/design_history_panel.py", ["history_panel/HISTORY_PANEL_REGISTRATION.json"]),
    batch("known_GR_integer_baseline", "independent/baseline/REQUESTS.json.gz", "independent/baseline/native_runs", "discovery+assessment",
          "Already known G/R directions; all feasible registered integer n,m; nested core",
          "independent/baseline/design_baseline.py", ["independent/baseline/BASELINE_SPEC.json", "independent/baseline/DESIGN_FREEZE.json"]),
    batch("common_panel_discovery", "forward/common_panel/common_requests.json.gz", "forward/common_panel/native", "discovery",
          "Common actual teams shared by forward and competitor classifications",
          "forward/common_panel/design_common_panel.py", ["forward/common_panel/COMMON_PANEL_REGISTRATION.json", "forward/common_panel/REGISTERED_COMPARISON.json"]),
    batch("common_panel_assessment", "forward/common_panel/assessment/common_requests.json.gz", "forward/common_panel/assessment/native", "assessment",
          "Frozen common-team assessment panel; competitors reuse these native results",
          "forward/common_panel/design_common_panel.py", ["forward/common_panel/assessment/COMMON_PANEL_REGISTRATION.json", "forward/common_panel/assessment/REGISTERED_COMPARISON.json"]),
    batch("forward_discovery", "discovery/forward_requests.json.gz", "discovery/native_forward", "discovery",
          "Forward category-block discovery, including supported task conditions",
          "code/design_blocks.py", ["discovery/FORWARD_SPEC.json"]),
    batch("reverse_discovery", "discovery/reverse_requests.json.gz", "discovery/native_reverse", "discovery",
          "Reverse category-block discovery; labels learned from frozen history",
          "code/design_blocks.py", ["discovery/REVERSE_SPEC.json"]),
    batch("condition_discovery", "condition_transfer/discovery_requests.json.gz", "condition_transfer/native_discovery", "discovery",
          "Same exact crews and reference on linked observed Manual/Semi pools",
          "code/design_condition_transfer.py"),
    batch("condition_assessment", "condition_transfer/assessment_requests.json.gz", "condition_transfer/native_assessment", "assessment",
          "Fixed same-crew Manual/Semi transfer rules on reused-v2 assessment buildings",
          "code/design_condition_transfer.py"),
    batch("mixed_discovery", "mixed_challenge/discovery_requests.json.gz", "mixed_challenge/native_discovery", "discovery",
          "Seven predeclared genuinely mixed / whole-team replacement routes",
          "code/design_mixed_challenge.py", ["independent/mixed_challenge/ASSESSMENT_DESIGN_FREEZE.json"]),
    batch("mixed_assessment", "independent/mixed_challenge/assessment_requests.json.gz", "independent/mixed_challenge/native_assessment", "assessment",
          "Same seven routes; frozen exact-vector and contrast priorities retained",
          "code/design_mixed_challenge.py", ["independent/mixed_challenge/ASSESSMENT_DESIGN_FREEZE.json", "independent/mixed_challenge/VECTOR_REPLICATION_FREEZE.json", "independent/mixed_challenge/CONTRAST_REPLICATION_FREEZE.json"]),
    batch("ratio_grid_discovery", "ratio_grid/discovery_requests.json.gz", "ratio_grid/native_discovery", "discovery",
          "Frozen pure/mixed count-vector grid with sampled personnel crews",
          "code/design_ratio_grid.py"),
    batch("ratio_same_image_replication", "ratio_grid/replication_requests.json.gz", "ratio_grid/native_replication", "discovery",
          "Five discovery-selected ratios; new exact members on the same images",
          "code/design_ratio_replication.py", ["ratio_grid/RATIO_REPLICATION_FREEZE.json"]),
    batch("ratio_assessment", "ratio_grid/assessment_requests.json.gz", "ratio_grid/native_assessment", "assessment",
          "Five frozen ratios evaluated on other reused-v2 buildings",
          "code/design_ratio_replication.py", ["ratio_grid/RATIO_REPLICATION_FREEZE.json"]),
    batch("ratio_P05_local_census", "ratio_grid/local_census/requests.json.gz", "ratio_grid/local_census/native", "discovery",
          "Post-result local mechanism census: one image, fixed n5 and four vectors; not validation",
          "code/local_ratio_census.py"),
    batch("fixed_direction_assessment", "assessment/direction_requests.json.gz", "assessment/native_directions", "assessment",
          "Frozen forward/reverse directions assessed on reused-v2 buildings",
          "code/design_blocks.py", ["assessment/DIRECTION_SPEC.json", "assessment/ASSESSMENT_FREEZE.json"]),
    batch("new2_nested_assessment", "assessment/nested_new2_requests.json.gz", "assessment/native_nested_new2", "assessment",
          "Fixed new2 bidirectional m2/m5 blocks across every feasible nested n",
          "code/design_nested_new2.py", ["assessment/NESTED_NEW2_SPEC.json", "assessment/NESTED_NEW2_DESIGN_RECEIPT.json"]),
    batch("W132_postassessment_probe", "assessment/w132_probe_requests.json.gz", "assessment/native_w132_probe", "assessment",
          "Post-assessment mechanism probe; same-class W132 alternatives enumerated",
          "reverse/assessment_interpretation/design_w132_probe.py", ["reverse/assessment_interpretation/w132_probe/REGISTER.json"]),
]


def read(path):
    with (gzip.open(path, "rt") if str(path).endswith(".gz") else open(path)) as stream:
        return json.load(stream)


def canonical(obj):
    # Match the frozen wrapper's member / pool digest, including ASCII escaping.
    return json.dumps(obj, sort_keys=True, separators=(",", ":")).encode()


def digest(obj):
    return hashlib.sha256(canonical(obj)).hexdigest()


def sha(path):
    h = hashlib.sha256()
    with open(path, "rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def team_key(pid, workers):
    return pid + "__" + digest(sorted(workers))[:20]


def atomic_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    raw = json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False).encode()
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_bytes(raw)
    tmp.replace(path)


def csv_write(path, rows):
    rows = list(rows)
    path.parent.mkdir(parents=True, exist_ok=True)
    columns = list(dict.fromkeys(k for r in rows for k in r))
    tmp = path.with_suffix(path.suffix + ".tmp")
    with open(tmp, "w", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=columns)
        writer.writeheader()
        for row in rows:
            writer.writerow({k: json.dumps(v, ensure_ascii=False, sort_keys=True) if isinstance(v, (dict, list, tuple, set)) else v for k, v in row.items()})
    tmp.replace(path)


SCIENCE_FIELDS = [
    "score_status", "B8L2", "D10", "IoU3D100", "iou_2d", "S_bottom_deg", "dir", "Hmean", "Hcenter",
    "omission", "extension", "height_mean_ratio", "complete_evaluable", "complete_floor_evaluable",
    "floor_evaluable", "connection_available", "nodes", "geometry", "minimum_support", "node_supports",
    "identity_groups_n", "unselected_groups_n", "minority_observations_n", "selected_support_min",
    "ref_node_recall_5", "ref_node_recall_9", "ref_edge_recall_5", "ref_edge_recall_9",
    "ref_matched_nodes_5", "ref_matched_nodes_9", "ref_matched_edges_5", "ref_matched_edges_9",
]


def scientific_record(team):
    return {k: team.get(k) for k in SCIENCE_FIELDS}


def compare_values(left, right, path=""):
    """Return maximal numerical difference and exact nonnumerical mismatches."""
    if isinstance(left, bool) or isinstance(right, bool):
        return 0.0, [] if left == right else [path]
    if isinstance(left, (int, float)) and isinstance(right, (int, float)):
        return abs(float(left) - float(right)), []
    if isinstance(left, dict) and isinstance(right, dict):
        if left.keys() != right.keys():
            return 0.0, [path + ":keys"]
        result = [compare_values(left[k], right[k], path + "." + k) for k in left]
    elif isinstance(left, list) and isinstance(right, list):
        if len(left) != len(right):
            return 0.0, [path + ":length"]
        result = [compare_values(a, b, path + "[" + str(i) + "]") for i, (a, b) in enumerate(zip(left, right))]
    else:
        return 0.0, [] if left == right else [path]
    return max((r[0] for r in result), default=0.0), [v for r in result for v in r[1]]


def finite(value):
    return isinstance(value, (int, float)) and math.isfinite(value)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[2])
    ap.add_argument("--out", type=Path)
    a = ap.parse_args()
    root = a.root.resolve()
    out = a.out.resolve() if a.out else root / STUDY / "independent/global_coverage"
    out.mkdir(parents=True, exist_ok=True)

    snapshot = read(root / SNAPSHOT)
    pools = {p["pool_id"]: p for p in snapshot["images"]}
    pids = sorted(pools)
    pindex = {p: i for i, p in enumerate(pids)}
    pool_bits = max(1, (len(pids) - 1).bit_length())
    pool_mask = (1 << pool_bits) - 1
    workers = sorted({r["worker_id"] for p in pools.values() for r in p["records"]})
    windex = {w: i for i, w in enumerate(workers)}
    wbits = {w: 1 << i for w, i in windex.items()}
    pool_member = {pid: {r["worker_id"]: r for r in p["records"]} for pid, p in pools.items()}
    pool_hashes = {pid: digest(p) for pid, p in pools.items()}
    split = read(root / SPLIT)
    actual_phase = {b: phase for phase, key in [("history", "history_buildings"), ("discovery", "discovery_buildings"), ("assessment", "validation_buildings")] for b in split[key]}
    image_ids = sorted({p["meta"]["image_id"] for p in pools.values()})
    image_index = {image: i for i, image in enumerate(image_ids)}
    image_bits = max(1, (len(image_ids) - 1).bit_length())
    worker_origins = {w: sorted({pool_member[pid][w]["origin"] for pid in pools if w in pool_member[pid]}) for w in workers}
    expected_runner_sha = sha(root / RUNNER)

    errors = []
    warnings = []
    checks = collections.Counter()

    def require(condition, kind, details):
        checks[kind] += 1
        if not condition:
            errors.append(dict(check=kind, **details))

    for w, origins in worker_origins.items():
        require(len(origins) == 1, "worker_origin_consistent_across_pools", dict(worker_id=w, origins=origins))

    registry = []
    for config in REGISTRY:
        r = dict(config)
        for field in ["requests", "run_receipt", "generator"]:
            path = root / r[field]
            r[field + "_exists"] = path.exists()
            r[field + "_sha256"] = sha(path) if path.exists() else None
        r["registration_sha256"] = {p: sha(root / p) if (root / p).exists() else None for p in r["registration_files"]}
        require(r["requests_exists"] and r["run_receipt_exists"], "batch_required_input_exists", dict(batch_id=r["batch_id"]))
        if not r["generator_exists"]:
            warnings.append(dict(batch_id=r["batch_id"], issue="generator_path_missing", path=r["generator"]))
        registry.append(r)
    atomic_json(out / "BATCH_REGISTRY.json", dict(schema="registered_native_batch_registry_v1", batches=registry,
        exclusions=["Restored prior-A 122082 replacement-pair observations: retained training input, not current native calls",
                    "condition_transfer/requests.json.gz is the union of the two registered phase manifests, not a third native batch",
                    "Reconstruction-check manifests and rebuilt metadata are copies, not native executions",
                    "Common-panel competitors and alternative metrics reuse the same native teams",
                    "Extra teams in any native cache that are not requested by its registered manifest",
                    "Supplementary audit and illustrative-case replays are reported separately, not new independent image evidence"]))

    # task_map retains only a tiny fingerprint and batch membership. It never
    # retains full native geometries or all request/event objects across batches.
    task_map = {}  # (crew bits << pool_bits | pool index) -> [first batch, digest, batch mask]
    global_crews = set()
    image_crews = set()
    batch_rows = []
    pool_rows = []
    status_rows = []
    n_rows = []
    condition_rows = []
    source_rows = []
    global_status = collections.Counter()
    global_n = collections.Counter()
    global_condition = collections.Counter()
    global_source = collections.Counter()
    global_worker_tasks = collections.Counter()
    global_pool_tasks = collections.Counter()
    global_pool_complete = collections.Counter()
    global_pool_finite = collections.Counter()
    global_pool_workers = collections.defaultdict(set)
    global_pool_newn = collections.defaultdict(collections.Counter)
    global_q_finite = 0
    global_complete = 0
    global_formal = 0
    global_formal_complete = 0
    duplicate_science_digest_equal = 0
    duplicate_science_digest_different = 0
    max_duplicate_abs_difference = 0.0
    duplicate_differences = []
    contexts = collections.Counter()

    @functools.lru_cache(maxsize=2)
    def old_pool(batch_index, pid):
        data = read(root / registry[batch_index]["native_dir"] / "pools" / (pid + ".json.gz"))
        return {t["team_key"]: t for t in data["teams"]}

    for bi, config in enumerate(registry):
        name = config["batch_id"]
        print(json.dumps(dict(batch=name, stage="read_manifest", index=bi + 1, total=len(registry))), flush=True)
        doc = read(root / config["requests"])
        requests = doc.pop("requests")
        event_field = "events" if "events" in doc else "blocks" if "blocks" in doc else None
        event_rows = len(doc[event_field]) if event_field else None
        links = len(doc["links"]) if "links" in doc else None
        embedded_spec_sha = digest(doc["spec"]) if "spec" in doc else None
        ledger_rows = len(doc["ledger"]) if "ledger" in doc else None
        # Events are not needed to establish native task identity.
        del doc
        gc.collect()
        seen_ids = set()
        by_pool = collections.defaultdict(dict)
        request_member_hash = hashlib.sha256()
        for q in sorted(requests, key=lambda q: q["request_id"]):
            pid, ws, rid = q["pool_id"], tuple(sorted(q["worker_ids"])), q["request_id"]
            require(rid not in seen_ids, "request_id_unique_within_manifest", dict(batch_id=name, request_id=rid))
            seen_ids.add(rid)
            require(pid in pools, "request_pool_exists_in_frozen_snapshot", dict(batch_id=name, request_id=rid, pool_id=pid))
            if pid not in pools:
                continue
            require(len(ws) == len(set(ws)) == q["k"], "request_count_and_members_unique", dict(batch_id=name, request_id=rid))
            require(set(ws) <= pool_member[pid].keys(), "request_members_in_exact_pool", dict(batch_id=name, request_id=rid))
            if not set(ws) <= pool_member[pid].keys():
                continue
            tk = team_key(pid, ws)
            require(q.get("team_key", tk) == tk, "explicit_request_team_key_matches_full_members", dict(batch_id=name, request_id=rid))
            if rid.startswith(pid + "__"):
                require(rid == tk, "team_key_request_id_matches_member_hash", dict(batch_id=name, request_id=rid))
            mask = sum(wbits[w] for w in ws)
            previous = by_pool[pid].get(mask)
            if previous:
                require(previous[0] == tk and previous[1] == ws, "lossless_member_encoding", dict(batch_id=name, request_id=rid))
                previous[2] += 1
            else:
                by_pool[pid][mask] = [tk, ws, 1]
            request_member_hash.update(canonical([rid, pid, q["k"], ws]) + b"\n")
        request_count = len(requests)
        del requests, seen_ids
        gc.collect()
        receipt = read(root / config["run_receipt"])
        requested_unique = sum(len(rs) for rs in by_pool.values())
        receipt_by_pool = {r["pool_id"]: r for r in receipt["by_pool"]}
        require(receipt["request_sha256"] == config["requests_sha256"], "native_run_receipt_request_sha", dict(batch_id=name))
        require(receipt["request_rows"] == request_count, "native_run_receipt_request_rows", dict(batch_id=name))
        require(receipt["unique_teams"] == requested_unique, "native_run_receipt_unique_tasks", dict(batch_id=name))
        require(set(receipt_by_pool) == set(by_pool), "native_run_receipt_pool_set", dict(batch_id=name))
        require(receipt["new_fusions"] == sum(r["new_teams"] for r in receipt_by_pool.values()), "new_fusions_receipt_sum", dict(batch_id=name))
        bstatus = collections.Counter()
        bn = collections.Counter()
        bcondition = collections.Counter()
        bsource = collections.Counter()
        bcrews = set()
        bimages = set()
        bbuildings = set()
        bworkers = set()
        bobjects = set()
        brecords = set()
        bcomplete = bq = bformal = bformal_complete = 0
        native_found = 0
        cache_extras = 0
        overlap_previous = 0
        for pid in sorted(by_pool):
            reqs = by_pool[pid]
            path = root / config["native_dir"] / "pools" / (pid + ".json.gz")
            require(path.exists(), "native_pool_file_exists", dict(batch_id=name, pool_id=pid))
            if not path.exists():
                continue
            data = read(path)
            context = data["context"]
            expected_context = dict(pool_digest=pool_hashes[pid], fusion_gap=7.5,
                                    main_commit=FROZEN_INPUT_COMMIT, science_commit=SCIENCE_COMMIT,
                                    runner_sha256=expected_runner_sha)
            require(context == expected_context, "native_frozen_pool_and_code_context", dict(batch_id=name, pool_id=pid, actual=context if context != expected_context else None))
            contexts[digest(context)] += 1
            native = {t["team_key"]: t for t in data["teams"]}
            require(len(native) == len(data["teams"]), "native_team_key_unique_within_pool", dict(batch_id=name, pool_id=pid))
            reqkeys = {r[0] for r in reqs.values()}
            require(reqkeys <= native.keys(), "all_requested_native_teams_present", dict(batch_id=name, pool_id=pid, missing=sorted(reqkeys - native.keys())[:5]))
            extra = len(native.keys() - reqkeys)
            cache_extras += extra
            pr = receipt_by_pool.get(pid, {})
            require(pr.get("requests") == sum(r[2] for r in reqs.values()), "per_pool_receipt_request_rows", dict(batch_id=name, pool_id=pid))
            require(pr.get("requested_unique") == len(reqs), "per_pool_receipt_unique_tasks", dict(batch_id=name, pool_id=pid))
            require(0 <= pr.get("new_teams", -1) <= len(reqs), "per_pool_new_call_bound", dict(batch_id=name, pool_id=pid))
            meta = pools[pid]["meta"]
            pworkers = set()
            pstatus = collections.Counter()
            pq = pc = 0
            for mask, (tk, ws, row_multiplicity) in reqs.items():
                if tk not in native:
                    continue
                t = native[tk]
                native_found += 1
                n = len(ws)
                expected_objects = [pool_member[pid][w]["object_id"] for w in ws]
                new_n = sum(pool_member[pid][w]["origin"] == "new" for w in ws)
                old_n = sum(pool_member[pid][w]["origin"] == "v1" for w in ws)
                require(tuple(t["member_workers"]) == ws and t["team_key"] == tk,
                        "native_members_and_crew_hash_match_request", dict(batch_id=name, pool_id=pid, team_key=tk))
                require(t["k"] == n, "native_actual_n_matches_request", dict(batch_id=name, pool_id=pid, team_key=tk))
                require(t["member_object_ids"] == expected_objects, "native_exact_record_object_ids", dict(batch_id=name, pool_id=pid, team_key=tk))
                require(t["new_n"] == new_n and t["old_n"] == old_n and new_n + old_n == n,
                        "native_source_counts_match_actual_records", dict(batch_id=name, pool_id=pid, team_key=tk))
                meta_keys = ["pool_id", "image", "image_id", "building", "condition", "layer", "reference_id", "reference_version"]
                require(all(t.get(key) == meta.get(key) for key in meta_keys), "native_exact_pool_image_reference_metadata", dict(batch_id=name, pool_id=pid, team_key=tk))
                status = t.get("score_status", "MISSING_STATUS")
                complete = bool(t.get("complete_evaluable"))
                qfinite = finite(t.get("B8L2"))
                dfinite = finite(t.get("D10"))
                require(qfinite == dfinite, "B8L2_D10_joint_finite_qualification", dict(batch_id=name, pool_id=pid, team_key=tk))
                if n == 2:
                    require(status == "two_person_deferred" and not complete and not qfinite,
                            "two_person_inherited_deferred_qualification", dict(batch_id=name, pool_id=pid, team_key=tk))
                pstatus[status] += 1
                bstatus[status] += 1
                bn[n, status, complete, qfinite] += 1
                phase = actual_phase.get(meta["building"], "unassigned")
                ckey = (phase, meta["layer"], meta["condition"], status, complete, qfinite)
                skey = (phase, new_n, old_n, status, complete, qfinite)
                bcondition[ckey] += 1
                bsource[skey] += 1
                pworkers.update(ws)
                bworkers.update(ws)
                bobjects.update(expected_objects)
                brecords.update(pool_member[pid][w]["id"] for w in ws)
                bimages.add(meta["image_id"])
                bbuildings.add(meta["building"])
                bcrews.add(mask)
                pq += qfinite
                pc += complete
                bq += qfinite
                bcomplete += complete
                bformal += n >= 3
                bformal_complete += n >= 3 and complete
                key = (mask << pool_bits) | pindex[pid]
                science = scientific_record(t)
                fingerprint = hashlib.sha256(canonical(science)).digest()
                if key in task_map:
                    old_bi, old_fingerprint, batches = task_map[key]
                    overlap_previous += 1
                    if fingerprint == old_fingerprint:
                        duplicate_science_digest_equal += 1
                    else:
                        duplicate_science_digest_different += 1
                        first = scientific_record(old_pool(old_bi, pid)[tk])
                        diff, nonnumeric = compare_values(first, science)
                        max_duplicate_abs_difference = max(max_duplicate_abs_difference, diff)
                        require(not nonnumeric and diff <= 1e-9, "duplicate_cross_batch_native_science_consistency",
                                dict(batch_id=name, first_batch=registry[old_bi]["batch_id"], pool_id=pid, team_key=tk, max_abs_difference=diff, nonnumeric_mismatches=nonnumeric))
                        duplicate_differences.append(dict(first_batch=registry[old_bi]["batch_id"], batch_id=name, pool_id=pid,
                            team_key=tk, max_abs_difference=diff, nonnumeric_mismatches=nonnumeric))
                    task_map[key][2] = batches | (1 << bi)
                else:
                    task_map[key] = [bi, fingerprint, 1 << bi]
                    global_crews.add(mask)
                    image_crews.add((mask << image_bits) | image_index[meta["image_id"]])
                    global_status[status] += 1
                    global_n[n, status, complete, qfinite] += 1
                    global_condition[ckey] += 1
                    global_source[skey] += 1
                    global_pool_tasks[pid] += 1
                    global_pool_complete[pid] += complete
                    global_pool_finite[pid] += qfinite
                    global_pool_workers[pid].update(ws)
                    global_pool_newn[pid][new_n] += 1
                    global_worker_tasks.update(ws)
                    global_complete += complete
                    global_q_finite += qfinite
                    global_formal += n >= 3
                    global_formal_complete += n >= 3 and complete
            require(pr.get("score_available") == pq, "per_pool_receipt_finite_score_count", dict(batch_id=name, pool_id=pid))
            pool_rows.append(dict(batch_id=name, pool_id=pid, image_id=meta["image_id"], image=meta["image"],
                building=meta["building"], actual_phase=actual_phase.get(meta["building"], "unassigned"), layer=meta["layer"], condition=meta["condition"],
                reference_id=meta["reference_id"], request_rows=sum(r[2] for r in reqs.values()), requested_unique_teams=len(reqs),
                native_requested_found=sum(tk in native for tk in reqkeys), native_cache_extra_teams_ignored=extra,
                reported_new_fusions=pr.get("new_teams"), complete_evaluable=pc, finite_B8L2=pq,
                actual_workers=len(pworkers), worker_ids=sorted(pworkers), score_status_counts=dict(pstatus), native_pool_sha256=sha(path)))
            del data, native
        batch_rows.append(dict(batch_id=name, registered_phase=config["phase"], request_rows=request_count,
            unique_pool_crew=requested_unique, within_manifest_repeated_rows=request_count - requested_unique,
            native_requested_found=native_found, native_new_fusions_reported=receipt["new_fusions"],
            native_requested_preexisting_at_run=requested_unique - receipt["new_fusions"],
            global_new_unique_in_registry_order=requested_unique - overlap_previous,
            overlap_with_prior_registry_batches=overlap_previous, distinct_crews_ignoring_pool=len(bcrews),
            pools=len(by_pool), true_images=len(bimages), buildings=len(bbuildings), workers=len(bworkers),
            worker_ids=sorted(bworkers), unique_object_ids=len(bobjects), unique_frozen_record_ids=len(brecords),
            complete_evaluable=bcomplete, finite_B8L2=bq, n_ge3_tasks=bformal, n_ge3_complete=bformal_complete,
            two_person_deferred=bstatus["two_person_deferred"], score_status_counts=dict(bstatus),
            native_cache_extra_teams_ignored=cache_extras, manifest_event_field=event_field, manifest_event_rows=event_rows,
            manifest_link_rows=links, manifest_ledger_rows=ledger_rows, embedded_spec_sha256=embedded_spec_sha,
            request_member_contract_sha256=request_member_hash.hexdigest(), requests_sha256=config["requests_sha256"],
            run_receipt_sha256=config["run_receipt_sha256"]))
        status_rows.extend(dict(batch_id=name, score_status=k, unique_pool_crew=v) for k, v in sorted(bstatus.items()))
        n_rows.extend(dict(batch_id=name, n=k[0], score_status=k[1], complete_evaluable=k[2], finite_B8L2=k[3], unique_pool_crew=v) for k, v in sorted(bn.items()))
        condition_rows.extend(dict(batch_id=name, actual_phase=k[0], layer=k[1], condition=k[2], score_status=k[3], complete_evaluable=k[4], finite_B8L2=k[5], unique_pool_crew=v) for k, v in sorted(bcondition.items()))
        source_rows.extend(dict(batch_id=name, actual_phase=k[0], new_n=k[1], v1_n=k[2], score_status=k[3], complete_evaluable=k[4], finite_B8L2=k[5], unique_pool_crew=v) for k, v in sorted(bsource.items()))
        print(json.dumps(dict(batch=name, stage="audited", requested_unique=requested_unique, found=native_found,
            global_unique_so_far=len(task_map), errors=len(errors))), flush=True)
        del by_pool, receipt, receipt_by_pool, bcrews
        gc.collect()

    overlap = collections.Counter()
    multiplicity = collections.Counter()
    task_hash = hashlib.sha256()
    for key, (_, _, batches) in sorted(task_map.items()):
        indices = [i for i in range(len(registry)) if batches & (1 << i)]
        multiplicity[len(indices)] += 1
        overlap.update(itertools.combinations(indices, 2))
        pid = pids[key & pool_mask]
        mask = key >> pool_bits
        ws = [w for w in workers if mask & wbits[w]]
        task_hash.update(canonical([pid, ws]) + b"\n")
    global_task_count = len(task_map)
    all_used_pools = sorted(global_pool_tasks)
    all_used_images = {pools[pid]["meta"]["image_id"] for pid in all_used_pools}
    all_used_buildings = {pools[pid]["meta"]["building"] for pid in all_used_pools}
    all_used_workers = set(global_worker_tasks)
    all_used_records = {pool_member[pid][w]["id"] for pid, ws in global_pool_workers.items() for w in ws}
    all_used_objects = {pool_member[pid][w]["object_id"] for pid, ws in global_pool_workers.items() for w in ws}

    status_rows.extend(dict(batch_id="GLOBAL_DEDUP", score_status=k, unique_pool_crew=v) for k, v in sorted(global_status.items()))
    n_rows.extend(dict(batch_id="GLOBAL_DEDUP", n=k[0], score_status=k[1], complete_evaluable=k[2], finite_B8L2=k[3], unique_pool_crew=v) for k, v in sorted(global_n.items()))
    condition_rows.extend(dict(batch_id="GLOBAL_DEDUP", actual_phase=k[0], layer=k[1], condition=k[2], score_status=k[3], complete_evaluable=k[4], finite_B8L2=k[5], unique_pool_crew=v) for k, v in sorted(global_condition.items()))
    source_rows.extend(dict(batch_id="GLOBAL_DEDUP", actual_phase=k[0], new_n=k[1], v1_n=k[2], score_status=k[3], complete_evaluable=k[4], finite_B8L2=k[5], unique_pool_crew=v) for k, v in sorted(global_source.items()))

    global_pool_rows = []
    for pid in all_used_pools:
        meta = pools[pid]["meta"]
        ws = sorted(global_pool_workers[pid])
        global_pool_rows.append(dict(pool_id=pid, image_id=meta["image_id"], image=meta["image"], building=meta["building"],
            actual_phase=actual_phase[meta["building"]], layer=meta["layer"], condition=meta["condition"], difficulty=meta["difficulty"],
            reference_id=meta["reference_id"], reference_version=meta["reference_version"], unique_pool_crew=global_pool_tasks[pid],
            complete_evaluable=global_pool_complete[pid], finite_B8L2=global_pool_finite[pid], actual_workers=len(ws),
            worker_ids=ws, new_workers=sum(worker_origins[w] == ["new"] for w in ws), v1_workers=sum(worker_origins[w] == ["v1"] for w in ws),
            new_n_distribution=dict(global_pool_newn[pid])))
    images_rows = []
    for iid in sorted(all_used_images):
        ids = [p for p in all_used_pools if pools[p]["meta"]["image_id"] == iid]
        m = pools[ids[0]]["meta"]
        images_rows.append(dict(image_id=iid, image_names=sorted({pools[p]["meta"]["image"] for p in ids}), building=m["building"],
            actual_phase=actual_phase[m["building"]], pool_ids=ids, pools=len(ids),
            conditions=sorted({pools[p]["meta"]["condition"] for p in ids}), layers=sorted({pools[p]["meta"]["layer"] for p in ids}),
            unique_pool_crew=sum(global_pool_tasks[p] for p in ids),
            workers=len(set.union(*(global_pool_workers[p] for p in ids)))))
    workers_rows = []
    for w in workers:
        ids = [p for p in all_used_pools if w in global_pool_workers[p]]
        workers_rows.append(dict(worker_id=w, origin=worker_origins[w], used_in_round=bool(ids),
            global_unique_task_appearances=global_worker_tasks[w], pools=len(ids),
            true_images=len({pools[p]["meta"]["image_id"] for p in ids}), buildings=len({pools[p]["meta"]["building"] for p in ids}),
            phases=sorted({actual_phase[pools[p]["meta"]["building"]] for p in ids}),
            layers=sorted({pools[p]["meta"]["layer"] for p in ids})))

    exports = {
        "BATCH_COVERAGE.csv": batch_rows,
        "BATCH_POOL_COVERAGE.csv": pool_rows,
        "STATUS_COUNTS.csv": status_rows,
        "N_STATUS_COUNTS.csv": n_rows,
        "CONDITION_STATUS_COUNTS.csv": condition_rows,
        "SOURCE_COUNTS.csv": source_rows,
        "GLOBAL_POOL_COVERAGE.csv": global_pool_rows,
        "GLOBAL_IMAGE_COVERAGE.csv": images_rows,
        "GLOBAL_WORKER_COVERAGE.csv": workers_rows,
        "CROSS_BATCH_OVERLAP.csv": [dict(batch_a=registry[i]["batch_id"], batch_b=registry[j]["batch_id"],
                                         shared_exact_pool_crew=overlap[i, j]) for i, j in itertools.combinations(range(len(registry)), 2)],
        "TASK_BATCH_MULTIPLICITY.csv": [dict(number_of_batches=k, global_unique_pool_crew=v) for k, v in sorted(multiplicity.items())],
        "DUPLICATE_NATIVE_NUMERIC_DIFFERENCES.csv": duplicate_differences,
    }
    for filename, rows in exports.items():
        csv_write(out / filename, rows)
    unused = [dict(pool_id=p, image_id=pools[p]["meta"]["image_id"], image=pools[p]["meta"]["image"],
                   building=pools[p]["meta"]["building"], layer=pools[p]["meta"]["layer"], condition=pools[p]["meta"]["condition"],
                   reason="No request in the 17 registered native batches; this audit does not infer mathematical infeasibility")
              for p in pids if p not in global_pool_tasks]
    csv_write(out / "UNREQUESTED_FROZEN_POOLS.csv", unused)

    # These are explicitly recorded supplemental calls, not additions to the
    # registered batches' unique scientific tasks. Illustrative exports may have
    # been repeated during editing; receipts do not instrument every invocation.
    supplementary = []
    for rel, field, kind in [
        ("independent/FOLLOWUP_REAGGREGATION_AUDIT.json", "native_replay_teams", "Independent re-fusion and scoring of old follow-up sample"),
        ("independent/baseline/results/MECHANISM_REPLAY_RECEIPT.json", "native_replayed_unique_teams", "State-only replay; existing scores reused"),
        ("cases/prepack_replay/REPLAY_RECEIPT.json", "teams", "Independent embedded-case re-fusion and scoring")]:
        path = root / STUDY / rel
        if path.exists():
            d = read(path)
            supplementary.append(dict(receipt=str(STUDY / rel), sha256=sha(path), recorded_calls=d.get(field), kind=kind,
                included_in_registered_native_calls=False, independent_new_images=False))
    atomic_json(out / "SUPPLEMENTARY_REPLAY_COUNTS.json", dict(entries=supplementary,
        scope="These are counts in surviving named receipts, not a complete cumulative profiler of every transient debug/export/replay invocation. They are not added to unique scientific support."))

    known_native_receipts = {str((root / r["run_receipt"]).resolve()) for r in registry}
    unregistered_runs = []
    for path in (root / STUDY).rglob("RUN_*.json"):
        if str(path.resolve()) in known_native_receipts:
            continue
        d = read(path)
        if "new_fusions" in d:
            unregistered_runs.append(str(path.relative_to(root)))
    require(not unregistered_runs, "all_surviving_registered_native_run_receipts_accounted_for", dict(unregistered=unregistered_runs))
    total_batch_unique = sum(r["unique_pool_crew"] for r in batch_rows)
    total_new_calls = sum(r["native_new_fusions_reported"] for r in batch_rows)
    total_rows = sum(r["request_rows"] for r in batch_rows)
    summary = dict(
        schema="global_registered_native_coverage_audit_v1",
        created_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
        all_passed=not errors, scientific_native_calls_executed_by_this_audit=0,
        batch_count=len(registry), total_request_rows=total_rows,
        sum_of_within_batch_unique_tasks=total_batch_unique,
        native_new_fusion_calls_from_run_receipts=total_new_calls,
        within_batch_requested_preexisting_cache_tasks=sum(r["native_requested_preexisting_at_run"] for r in batch_rows),
        global_unique_pool_crew=global_task_count,
        global_unique_true_image_crew=len(image_crews),
        global_distinct_crews_ignoring_all_pool_and_image_identity=len(global_crews),
        within_manifest_repeated_request_rows=total_rows - total_batch_unique,
        cross_batch_repeated_unique_task_occurrences=total_batch_unique - global_task_count,
        global_tasks_occurring_in_multiple_batches=sum(v for k, v in multiplicity.items() if k > 1),
        global_complete_evaluable=global_complete, global_finite_B8L2=global_q_finite,
        global_n_ge3_tasks=global_formal, global_n_ge3_complete_evaluable=global_formal_complete,
        global_two_person_deferred=global_status["two_person_deferred"],
        global_n_ge3_noncomplete=global_formal - global_formal_complete,
        global_score_status_counts=dict(global_status),
        global_pools=len(all_used_pools), global_true_images=len(all_used_images), global_buildings=len(all_used_buildings),
        global_workers=len(all_used_workers), global_worker_ids=sorted(all_used_workers),
        global_building_ids=sorted(all_used_buildings), global_unique_frozen_record_ids=len(all_used_records),
        global_unique_object_ids=len(all_used_objects), global_unique_pool_worker_records=sum(len(v) for v in global_pool_workers.values()),
        frozen_snapshot_pools=len(pools), frozen_snapshot_true_images=len(image_ids), frozen_snapshot_workers=len(workers),
        unrequested_snapshot_pools=len(unused), native_cache_extra_teams_ignored=sum(r["native_cache_extra_teams_ignored"] for r in batch_rows),
        duplicate_native_science_exact_digest_matches=duplicate_science_digest_equal,
        duplicate_native_science_digest_differences=duplicate_science_digest_different,
        duplicate_native_max_abs_difference=max_duplicate_abs_difference,
        global_task_member_sha256=task_hash.hexdigest(), global_task_hash_order="Lossless (crew bitmask << pool_bits | sorted pool index), ascending; hash canonical [pool_id, sorted workers] JSON plus newline",
        worker_bit_mapping=workers, pool_index_mapping=pids, pool_index_bits=pool_bits,
        checks=dict(checks), errors=errors, warnings=warnings,
        source_sha256={str(SNAPSHOT): sha(root / SNAPSHOT), str(SPLIT): sha(root / SPLIT), str(RUNNER): expected_runner_sha,
                       str(Path(__file__).resolve().relative_to(root)): sha(Path(__file__).resolve())},
        source_context=dict(current_main="445686f8f3cf6039c4ce1f60016cad1d26829044", native_frozen_input_main=FROZEN_INPUT_COMMIT,
                            native_science_commit=SCIENCE_COMMIT, explanation="Native context retains the earlier frozen input commit. Separate source-parity audit establishes unchanged source/snapshot at current main."),
        counting_boundaries=[
            "A task is frozen pool_id plus the exact distinct worker set. New teams on an old image remain repeated observations on that same image.",
            "The sum of per-batch tasks is not the global distinct-task count. Cross-batch repeats are explicitly deduplicated.",
            "Actual native calls are the sum of new_fusions in the 17 surviving run receipts; isolated caches may re-fuse a task already present in another batch.",
            "No unrequested native-cache team is counted. Companion union/reconstruction manifests and competitor/metric reanalyses are not new native batches.",
            "n=2 deferred qualification is retained separately; n>=3 noncomplete and all missing scores stay in denominators and are never scored zero.",
            "Prior retained A 122082 replacement-pair observations are historical input, not current new native calls. Named supplemental independent replays are reported separately.",
            "Counts establish actual search support, not complete enumeration of every scientifically feasible composition. Each generator's own frozen search ledger defines omitted n, vectors, sources, backgrounds and concrete teams.",
            "The 22 buildings and existing v2 images have already been explored; none are claimed to be new external blind data."
        ],
        outputs={name: dict(bytes=(out / name).stat().st_size, sha256=sha(out / name)) for name in list(exports) + ["BATCH_REGISTRY.json", "UNREQUESTED_FROZEN_POOLS.csv", "SUPPLEMENTARY_REPLAY_COUNTS.json"]}
    )
    atomic_json(out / "GLOBAL_COVERAGE_AUDIT.json", summary)
    print(json.dumps({k: summary[k] for k in ["all_passed", "batch_count", "total_request_rows", "native_new_fusion_calls_from_run_receipts",
        "global_unique_pool_crew", "global_distinct_crews_ignoring_all_pool_and_image_identity", "global_pools", "global_true_images", "global_buildings", "global_workers",
        "cross_batch_repeated_unique_task_occurrences", "duplicate_native_max_abs_difference"]}, ensure_ascii=False), flush=True)
    if errors:
        raise SystemExit("Global coverage audit failed; inspect GLOBAL_COVERAGE_AUDIT.json")


if __name__ == "__main__":
    main()
