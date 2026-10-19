#!/usr/bin/env python3
"""Focused probes for cache reuse and interpretation of new reference diagnostics."""
import os
for key in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS"):
    os.environ[key] = "1"
import importlib.util
import json
import math
from pathlib import Path
import numpy as np
from scipy.optimize import linear_sum_assignment

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "analysis/independent"
spec = importlib.util.spec_from_file_location("audited_runner_cache_probe", OUT / "fusion_runner_audited_snapshot.py")
runner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runner)
fe = runner.init_engine(ROOT / "restored")


def save(name, value):
    (OUT / name).write_text(json.dumps(fe.clean(value), indent=2, ensure_ascii=False, allow_nan=False) + "\n", encoding="utf-8")


def erp_pair(lon_deg, top_lat_deg):
    x = 512.0 + lon_deg * 1024.0 / 360.0
    top = (top_lat_deg / 180.0 + .5) * 512.0 - .5
    bottom = (-top_lat_deg / 180.0 + .5) * 512.0 - .5
    return [[x % 1024.0, top], [x % 1024.0, bottom]]


def floor_to_points(vertices):
    points = []
    for x, z in vertices:
        points.extend(erp_pair(math.degrees(math.atan2(x, z)), -math.degrees(math.atan(1.0 / math.hypot(x, z)))))
    return points


def diagnostics():
    ref_floor = [[-2, -2], [2, -2], [2, 2], [-2, 2]]
    split_floor = [[-2, -2], [0, -2], [2, -2], [2, 2], [-2, 2]]
    ref = floor_to_points(ref_floor)
    candidate = floor_to_points(split_floor)
    identical = runner.reference_structure(ref, ref)
    subdivided = runner.reference_structure(candidate, ref)
    assert identical["ref_edge_recall_5"] == 1.0
    assert subdivided["ref_node_recall_5"] == 1.0 and subdivided["ref_edge_recall_5"] == .75
    # Three point-pairs satisfy the diagnostic's minimum input length. The last
    # pair is a distant exact match, leaving a two-by-two assignment tradeoff.
    b = erp_pair(0., -30.) + erp_pair(5.7735, -30.) + erp_pair(120., -30.)
    a = erp_pair(.57735, -26.031373) + erp_pair(1.1547, -30.) + erp_pair(120., -30.)
    av, bv = np.asarray(a), np.asarray(b)
    cost = np.maximum(fe.angular(av[::2], bv[::2]), fe.angular(av[1::2], bv[1::2]))
    ii, jj = linear_sum_assignment(cost)
    actual = runner.reference_structure(a, b)
    diagonal_all_valid = bool(np.all(np.diag(cost) <= 5.0))
    assert diagonal_all_valid and actual["ref_node_recall_5"] < 1.0
    save("REFERENCE_DIAGNOSTIC_PROBES.json", {
        "scope": "Two synthetic mathematical counterexamples, not research-image evidence; the frozen B8L2 scorer is unchanged",
        "collinear_subdivision": {"reference_floor": ref_floor, "candidate_floor": split_floor,
            "reference_points": ref, "candidate_points": candidate, "geometry_identical": True,
            "identical_result": identical, "subdivision_result": subdivided,
            "interpretation": "Same square wall geometry with one redundant collinear corner: node recall stays 1, direct adjacency recall falls to 0.75. Thus adjacency recall is not necessary-wall completeness."},
        "thresholded_sum_assignment": {"reference_points": b, "candidate_points": a, "angular_cost_deg": cost.tolist(),
            "chosen_mapping": list(zip(ii.tolist(), jj.tolist())), "all_diagonal_pairs_within_5_deg": diagonal_all_valid,
            "result": actual, "maximum_feasible_node_recall_5": 1.0,
            "interpretation": "Min-sum assignment followed by thresholding can retain fewer within-threshold pairs than maximum-cardinality matching. This diagnostic is not a maximum-recall measure."}
    })


def cache_probe():
    selected = runner.read(OUT / "PARITY_SELECTION.json")["selected"]
    old = next(r for r in selected if r["score_status"] == "complete_conditional" and int(r["k"]) == 8)
    pool = next(p for p in fe.load_pools() if p["pool_id"] == old["pool_id"])
    workers = old["member_workers"].split("|")
    cache = {}
    score_calls = 0
    original = fe.compute_score
    def counted(*args, **kwargs):
        nonlocal score_calls
        score_calls += 1
        return original(*args, **kwargs)
    fe.compute_score = counted
    try:
        with fe.cached_matching(), fe.scoring_engine(fe.ENGINE / "measurement_engine.zip", fe.ENGINE / "working_models.py") as (engine, models):
            first = runner.evaluate_one(pool, workers, engine, models, cache)
            calls_after_first = score_calls
            second = runner.evaluate_one(pool, list(reversed(workers)), engine, models, cache)
    finally:
        fe.compute_score = original
    equality = all(first[k] == second[k] for k in runner.SCORE_KEYS + ["team_key", "member_workers", "member_object_ids", "geometry"])
    assert calls_after_first == 1 and score_calls == 1 and equality
    cache_output = OUT / "cache_probe"
    req = [{"request_id": "implementation_cache_probe", "worker_ids": workers, "k": len(workers)}]
    first_receipt = runner.run_pool(ROOT / "restored", pool, req, cache_output)
    second_receipt = runner.run_pool(ROOT / "restored", pool, req, cache_output)
    assert second_receipt["new_teams"] == 0
    save("CACHE_PROBE.json", {"legacy_team_id": old["team_id"], "same_members_reordered": True,
        "same_team_key_members_geometry_scores": equality, "score_calls_first": calls_after_first,
        "score_calls_second": score_calls - calls_after_first, "memory_cache_size": len(cache),
        "disk_cache_first_receipt": first_receipt, "disk_cache_second_receipt": second_receipt,
        "scope": "Reuse of one of the already selected 26 exact historical teams; no additional independent image or team evidence"})


if __name__ == "__main__":
    diagnostics()
    cache_probe()
    print(json.dumps({"synthetic_diagnostic_counterexamples": 2, "memory_cache_reuse": "pass", "disk_cache_reuse": "pass"}), flush=True)
