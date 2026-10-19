#!/usr/bin/env python3
"""Independent readback of count-vector summaries and archived geometry formulas.

No fusion is recomputed. This checks complete compressed output records, actual
member/count reconstruction, direct cell score summaries, and numeric parity
with the pinned historical geometry engine on deterministic real-team pairs.
"""
from __future__ import annotations
import argparse
import collections
import copy
import csv
import gzip
import itertools
import json
import math
from pathlib import Path
import numpy as np
import pandas as pd
import fusion_runner as fr
import summarize_grid as sg


def comparable(actual, expected, label):
    if expected is None or not np.isfinite(expected):
        assert pd.isna(actual), (label, actual, expected)
        return 0.
    assert np.isfinite(actual), (label, actual, expected)
    error = abs(actual - expected)
    assert error < 1e-10, (label, actual, expected, error)
    return float(error)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--grid", type=Path, required=True)
    ap.add_argument("--requests", type=Path, required=True)
    ap.add_argument("--runs", type=Path, required=True)
    ap.add_argument("--labels", type=Path, action="append", required=True)
    ap.add_argument("--restored", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args()
    receipt = fr.read(args.grid / "GRID_SUMMARY_RECEIPT.json")
    manifest = fr.read(args.requests)
    maps = sg.labels_from_files(args.labels)
    assert receipt["missing_computations"] == 0
    crc = {}
    for name, expected in receipt["outputs"].items():
        path = args.grid / name
        assert sg.sha(path) == expected["sha256"]
        with gzip.open(path, "rt", encoding="utf-8", newline="") as stream:
            count = sum(1 for _ in csv.reader(stream)) - 1
        assert count == expected["rows"]
        crc[name] = dict(csv_rows=count, bytes=path.stat().st_size, gzip_crc_and_end_marker=True)
    by_cell = collections.defaultdict(list)
    for r in manifest["requests"]:
        sg.validate_request(r, maps, receipt["phase"])
        by_cell[(r["method_id"], r["domain"], r["pool_id"], r["k"], r["composition"])].append(r)
    table = pd.read_csv(args.grid / "cell_summary.csv.gz")
    assert len(table) == len(by_cell)
    index = table.set_index(["method_id", "domain", "pool_id", "k", "composition"])
    keys = sorted(by_cell, key=fr.digest)
    sampled = keys[:24]
    failed = [key for key in keys if index.loc[key, "score_missing_n"] > 0]
    sampled = sorted(set(sampled + failed[:4]), key=fr.digest)
    fe = fr.init_engine(args.restored)
    pools = {}
    errors = []
    pair_n = scored_missing_pairs = structural_n = 0
    checks = []
    for key in sampled:
        mid, dom, pid, k, comp = key
        if pid not in pools:
            rows = fr.read(args.runs / "pools" / (pid + ".json.gz"))["teams"]
            pools[pid] = {r["team_key"]: r for r in rows}
        request_rows = by_cell[key]
        teams = [pools[pid][tk] for tk in sorted({r["team_key"] for r in request_rows})]
        summary = index.loc[key]
        assert len(teams) == summary.unique_team_n
        for metric in ("B8L2", "D10", "nodes"):
            x = np.asarray([r[metric] for r in teams if sg.number(r.get(metric)) is not None], float)
            errors.append(comparable(summary[metric + "_n"], len(x), metric + "_n"))
            functions = {"mean": np.mean, "min": np.min, "max": np.max}
            if metric != "nodes":
                functions.update(median=np.median, p10=lambda a: np.quantile(a, .1))
            for stat, fn in functions.items():
                errors.append(comparable(summary[metric + "_" + stat], float(fn(x)) if len(x) else None, metric + stat))
        stable, absq, turnovers = [], [], []
        for a, b in itertools.combinations(teams, 2):
            p = sg.pair_metrics(a, b)
            ga, gb = a.get("geometry") or {}, b.get("geometry") or {}
            native = fe.structural_distance(ga.get("points"), gb.get("points"))
            assert p["structure_reason"] == native["structure_reason"]
            assert p["bound_cyclic_shift"] == native["bound_cyclic_shift"]
            if native["structure_bound_cyclic_deg"] is not None:
                structural_n += 1
            errors.append(comparable(p["structure_bound_cyclic_deg"], native["structure_bound_cyclic_deg"], "bound_ring"))
            pa, pb = fe.footprint(ga.get("footprint")), fe.footprint(gb.get("footprint"))
            fj = prism = None
            if pa is not None and pb is not None and a.get("complete_floor_evaluable") and b.get("complete_floor_evaluable"):
                inter = pa.intersection(pb).area
                fj = 1. - inter / (pa.area + pb.area - inter)
                ha, hb = a.get("height_mean_ratio"), b.get("height_mean_ratio")
                if ha is not None and hb is not None and ha > 0 and hb > 0:
                    vi = inter * min(ha, hb)
                    prism = vi / (pa.area * ha + pb.area * hb - vi)
            errors.append(comparable(p["floor_jaccard_difference"], fj, "floor"))
            errors.append(comparable(p["mean_height_prism_pair_iou"], prism, "prism"))
            dq = p["abs_B8L2_change"]
            bound = native["structure_bound_cyclic_deg"]
            expected = bool(a.get("complete_evaluable") and b.get("complete_evaluable") and dq is not None and dq <= 2
                            and a.get("nodes") == b.get("nodes") and fj is not None and fj <= .05 and bound is not None and bound <= 3)
            assert p["joint_stable_main"] == expected
            assert p["turnover"] == len(set(a["member_workers"]) - set(b["member_workers"])) > 0
            turnovers.append(p["turnover"])
            stable.append(expected)
            if dq is not None:
                absq.append(dq)
            else:
                scored_missing_pairs += 1
            pair_n += 1
        assert len(stable) == summary.within_unique_team_pair_n
        assert sum(stable) == summary.within_joint_stable_main_n
        errors.append(comparable(summary.within_abs_B8L2_change_mean, np.mean(absq) if absq else None, "within_Q"))
        errors.append(comparable(summary.within_turnover_mean, np.mean(turnovers) if turnovers else None, "turnover"))
        checks.append(dict(method_id=mid, domain=dom, pool_id=pid, k=int(k), composition=comp, teams=len(teams), pair_n=len(stable)))
    rejections = []
    for mode in ("wrong_counts", "duplicate_worker", "wrong_phase", "wrong_hash"):
        r = copy.deepcopy(manifest["requests"][0])
        if mode == "wrong_counts":
            r["counts"][next(iter(r["counts"]))] += 1
        elif mode == "duplicate_worker":
            r["worker_ids"][0] = r["worker_ids"][1]
        elif mode == "wrong_phase":
            r["phase"] = "validation" if receipt["phase"] == "discovery" else "discovery"
        else:
            r["team_key"] = "bad"
        try:
            sg.validate_request(r, maps, receipt["phase"])
        except AssertionError:
            rejections.append(mode)
        else:
            raise AssertionError("Expected request rejection " + mode)
    fr.write(args.out, dict(schema="independent_grid_summary_audit_v1", phase=receipt["phase"],
        request_members_rebuilt=len(manifest["requests"]), cell_total=len(by_cell), inspected_cells=checks,
        exact_cell_and_numeric_parity=True, real_pairs=pair_n, quality_missing_pairs_retained=scored_missing_pairs,
        available_bound_ring_pairs=structural_n, maximum_numeric_error=max(errors),
        adversarial_request_rejections=rejections, output_crc_and_counts=crc,
        summary_receipt_sha256=sg.sha(args.grid / "GRID_SUMMARY_RECEIPT.json"),
        audit_source_sha256=sg.sha(Path(__file__)), frozen_engine_commit=fe.COMMIT))
    print(json.dumps(dict(phase=receipt["phase"], rebuilt_requests=len(manifest["requests"]), cells_checked=len(checks),
                         pair_n=pair_n, quality_missing_pairs=scored_missing_pairs, max_error=max(errors))))


if __name__ == "__main__":
    main()
