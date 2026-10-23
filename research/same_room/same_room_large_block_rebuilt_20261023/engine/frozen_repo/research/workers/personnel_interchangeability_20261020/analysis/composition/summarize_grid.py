#!/usr/bin/env python3
"""Summarize fixed personnel count vectors and real resampled fused teams.

This consumes only the specified composition requests, never every cached team.
Missing computations are distinct from computed fusion/measurement failures.
Labels, references, frozen scores and final geometry are not altered.

The pair geometry formulas retain the archived compare_fusions.py definitions:
floor 1-IoU, same-height-base mean-height prism IoU, and maximum bound cyclic
spherical endpoint distance (including the inherited vertical half pixel).
Reference-node/edge matches are geometric diagnostics, not necessary-structure GT.
"""
from __future__ import annotations
import argparse
import collections
import csv
import gzip
import hashlib
import io
import itertools
import json
import math
import os
from pathlib import Path

for _key in ("OPENBLAS_NUM_THREADS", "OMP_NUM_THREADS", "MKL_NUM_THREADS"):
    os.environ.setdefault(_key, "1")
import numpy as np
import pandas as pd
from shapely.geometry import Polygon
from shapely.errors import GEOSException
from fusion_runner import read, write, team_key, digest
from geometry_diagnostics import diagnose, SCHEMA as DIAGNOSTIC_SCHEMA

META = ("pool_id", "image", "image_id", "building", "room_id", "condition", "layer", "difficulty",
        "scene", "reference_id", "reference_version", "reference_nodes", "pool_n")
SCORE_METRICS = ("B8L2", "D10", "IoU3D100", "iou_2d", "S_bottom_deg", "dir", "Hmean", "Hcenter",
                 "omission", "extension", "height_mean_ratio", "nodes", "candidate_pair_count",
                 "ref_node_recall_5", "ref_edge_recall_5", "ref_node_recall_9", "ref_edge_recall_9",
                 "floor_area_camera_h2", "selected_support_min", "identity_groups_n", "unselected_groups_n",
                 "minority_observations_n", "new_n", "old_n", "source_time_total_seconds", "target_time_total_seconds")
DIAG_METRICS = ("diag_wall_coverage_03", "diag_wall_coverage_05", "diag_corner_recall_05")
SCORE_METRICS += DIAG_METRICS
PAIR_METRICS = ("turnover", "abs_B8L2_change", "abs_D10_change", "floor_jaccard_difference", "floor_symdiff_h2",
                "structure_bound_cyclic_deg", "node_count_difference", "mean_height_prism_pair_iou",
                "height_ratio_pair_abs_logdiff", "ref_node_set_jaccard_difference_5", "ref_edge_set_jaccard_difference_5",
                "ref_node_set_jaccard_difference_9", "ref_edge_set_jaccard_difference_9")
MAIN_TOLERANCES = dict(abs_B8L2=2., floor_jaccard_difference=.05, bound_cyclic_degree=3.,
                       same_node_count=True, both_complete=True)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def number(x):
    if isinstance(x, (int, float, np.integer, np.floating)) and not isinstance(x, (bool, np.bool_)):
        return float(x) if math.isfinite(float(x)) else None
    return None


def compact_json(x):
    return json.dumps(x, sort_keys=True, ensure_ascii=False, separators=(",", ":"))


def scalar(x):
    return x.item() if isinstance(x, (np.generic,)) else x


class CsvSink:
    """Pool-sized CSV chunks, each closed/CRC checked before final concatenation.

    Concatenated gzip members are a standard gzip stream. No open compressed
    file handle is retained across lengthy computation intervals. The completed
    CSV is reread to count records before it is exposed under its final name.
    """
    def __init__(self, path, empty_fields=("phase", "method_id", "domain", "pool_id", "k")):
        self.path = Path(path)
        self.tmp = self.path.with_name(self.path.name + ".tmp")
        self.parts_dir = self.path.with_name(self.path.name + f".parts.{os.getpid()}")
        self.parts_dir.mkdir()
        self.parts = []
        self.text = io.StringIO(newline="")
        self.writer = None
        self.fields = None
        self.empty_fields = empty_fields
        self.rows = 0
        self.chunk_rows = 0
    def append(self, row):
        if self.writer is None:
            if self.fields is None:
                self.fields = list(row)
            self.writer = csv.DictWriter(self.text, fieldnames=self.fields, extrasaction="raise")
            if not self.parts:
                self.writer.writeheader()
        self.writer.writerow({k: scalar(v) for k, v in row.items()})
        self.rows += 1
        self.chunk_rows += 1
    def checkpoint(self, force_empty=False):
        if not self.chunk_rows and (self.parts or not force_empty):
            return
        if self.writer is None:
            csv.writer(self.text).writerow(self.empty_fields)
        raw = self.text.getvalue().encode("utf-8")
        packed = gzip.compress(raw, compresslevel=6, mtime=0)
        assert gzip.decompress(packed) == raw
        assert sum(1 for _ in csv.reader(io.StringIO(raw.decode("utf-8"), newline=""))) == self.chunk_rows + (not self.parts)
        part = self.parts_dir / f"{len(self.parts):04d}.gz"
        part.write_bytes(packed)
        assert part.stat().st_size == len(packed)
        self.parts.append(part)
        self.text.close()
        self.text = io.StringIO(newline="")
        self.writer = None
        self.chunk_rows = 0
    def close(self):
        self.checkpoint(force_empty=True)
        with self.tmp.open("wb") as stream:
            for part in self.parts:
                packed = part.read_bytes()
                assert len(gzip.decompress(packed)) > 0
                stream.write(packed)
            stream.flush()
            os.fsync(stream.fileno())
        assert self.tmp.stat().st_size == sum(p.stat().st_size for p in self.parts)
        with gzip.open(self.tmp, "rt", encoding="utf-8", newline="") as stream:
            actual_rows = sum(1 for _ in csv.reader(stream)) - 1
        assert actual_rows == self.rows, f"CSV readback {actual_rows} != emitted {self.rows}"
        self.text.close()
        self.tmp.replace(self.path)
        for part in self.parts:
            part.unlink()
        self.parts_dir.rmdir()
    def abort(self):
        try:
            self.text.close()
        finally:
            self.tmp.unlink(missing_ok=True)
            for part in self.parts:
                part.unlink(missing_ok=True)
            if self.parts_dir.exists():
                self.parts_dir.rmdir()


def labels_from_files(paths):
    pieces = []
    for p in paths:
        a = pd.read_csv(p, keep_default_na=False)
        a["domain"] = a.domain.replace({"global": "all"})
        pieces.append(a)
    table = pd.concat(pieces, ignore_index=True)
    assert not table.duplicated(["method_id", "domain", "worker_id"]).any(), "duplicate fixed label key"
    maps = {}
    for (mid, domain), g in table.groupby(["method_id", "domain"]):
        maps[(mid, domain)] = {r.worker_id: r.class_id for r in g.itertuples()
                              if str(r.known).lower() == "true" and r.class_id not in ("", "unknown")}
    return maps


def canonical_counts(counts):
    return "|".join(f"{c}:{int(n)}" for c, n in sorted(counts.items()))


def validate_request(r, labels, phase):
    assert r.get("phase") == phase, "request outside authorized analysis phase"
    assert r.get("family") == "composition_grid", "expected composition-grid requests only"
    workers = r["worker_ids"]
    assert len(workers) == len(set(workers)) == r["k"], "invalid exact member set"
    mapping = labels[(r["method_id"], r["domain"])]
    assert set(workers) <= mapping.keys(), "unknown worker is not an admissible personnel class"
    classes = sorted(set(mapping.values()))
    actual = collections.Counter(mapping[w] for w in workers)
    expected = {c: int(r["counts"].get(c, 0)) for c in classes}
    assert set(r["counts"]) <= set(classes) and all(n >= 0 for n in expected.values())
    assert expected == {c: actual[c] for c in classes}, "real members do not rebuild requested count vector"
    assert canonical_counts(expected) == r["composition"], "noncanonical/mismatched composition identity"
    assert r["team_key"] == team_key(r["pool_id"], workers), "team identity hash mismatch"


def angular(a, b):
    """Same implementation as frozen paired_split_research.study.angular."""
    a, b = np.asarray(a, float), np.asarray(b, float)
    du = ((a[:, None, 0] - b[None, :, 0] + 512.) % 1024. - 512.) * (2 * np.pi / 1024.)
    va = ((a[:, 1] + .5) / 512. - .5) * np.pi
    vb = ((b[:, 1] + .5) / 512. - .5) * np.pi
    h = np.sin((va[:, None] - vb[None, :]) / 2.) ** 2 + np.cos(va[:, None]) * np.cos(vb[None, :]) * np.sin(du / 2.) ** 2
    h = np.clip(h, 0., 1.)
    return np.degrees(2 * np.arctan2(np.sqrt(h), np.sqrt(1 - h)))


def structural_distance(pa, pb):
    if pa is None or pb is None:
        return None, "missing_connected_points", None
    if len(pa) != len(pb):
        return None, "different_pair_count", None
    if len(pa) < 6:
        return None, "below_three_pairs", None
    a, b = np.asarray(pa, float), np.asarray(pb, float)
    costs = np.maximum(angular(a[::2], b[::2]), angular(a[1::2], b[1::2]))
    n = len(costs)
    distances = np.array([np.max(costs[np.arange(n), (np.arange(n) + s) % n]) for s in range(n)])
    shift = int(np.argmin(distances))
    return float(distances[shift]), "", shift


def signature(row, reference_floor=None, diagnostic_cache=None):
    geometry = row.get("geometry") or {}
    points = geometry.get("points")
    if points is not None:
        a = np.asarray(points, float)
        if a.ndim != 2 or a.shape[1:] != (2,) or len(a) % 2 or not np.isfinite(a).all():
            raise ValueError("malformed retained final points: " + row["team_key"])
    footprint = geometry.get("footprint")
    poly = None
    if footprint is not None and len(footprint) >= 3:
        poly = Polygon(footprint)
        if not (poly.is_valid and poly.area > 0 and math.isfinite(poly.area)):
            poly = None
    out = dict(points=points, floor=poly,
                candidate_pair_count=len(points) // 2 if points is not None else None,
                floor_area_camera_h2=poly.area if poly is not None and row.get("complete_floor_evaluable") else None)
    if reference_floor is not None:
        key = digest(footprint)
        if diagnostic_cache is not None and key in diagnostic_cache:
            diagnostics = diagnostic_cache[key]
        else:
            full = diagnose(footprint, reference_floor)
            diagnostics = {k: full.get(k) for k in ("diag_status",) + DIAG_METRICS}
            if diagnostic_cache is not None:
                diagnostic_cache[key] = diagnostics
        out.update(diagnostics)
    return out


def delta(a, b, key):
    x, y = number(a.get(key)), number(b.get(key))
    return y - x if x is not None and y is not None else None


def set_jaccard(a, b):
    if a is None or b is None:
        return None
    sa, sb = set(a), set(b)
    union = sa | sb
    return len(sa ^ sb) / len(union) if union else None


def pair_metrics(a, b, sa=None, sb=None):
    """Actual result differences. Applicable within AND across count vectors."""
    assert a["pool_id"] == b["pool_id"] and a["reference_id"] == b["reference_id"]
    assert a["k"] == b["k"]
    sa = signature(a) if sa is None else sa
    sb = signature(b) if sb is None else sb
    wa, wb = set(a["member_workers"]), set(b["member_workers"])
    assert len(wa) == len(wb) == a["k"]
    nodes = delta(a, b, "nodes")
    out = dict(shared_workers=len(wa & wb), turnover=len(wa - wb), symmetric_member_difference=len(wa ^ wb),
               same_members=wa == wb, complete_a=bool(a.get("complete_evaluable")), complete_b=bool(b.get("complete_evaluable")),
               both_complete=bool(a.get("complete_evaluable") and b.get("complete_evaluable")),
               B8L2_a=number(a.get("B8L2")), B8L2_b=number(b.get("B8L2")),
               B8L2_change=delta(a, b, "B8L2"), D10_change=delta(a, b, "D10"),
               node_count_change=nodes, node_count_difference=abs(nodes) if nodes is not None else None,
               new_n_change=delta(a, b, "new_n"), floor_jaccard_difference=None, floor_symdiff_h2=None,
               mean_height_prism_pair_iou=None, height_ratio_pair_abs_logdiff=None, geometry_comparison_error="")
    out["abs_B8L2_change"] = abs(out["B8L2_change"]) if out["B8L2_change"] is not None else None
    out["abs_D10_change"] = abs(out["D10_change"]) if out["D10_change"] is not None else None
    bound, reason, shift = structural_distance(sa["points"], sb["points"])
    out.update(structure_bound_cyclic_deg=bound, structure_reason=reason, bound_cyclic_shift=shift)
    pa, pb = sa["floor"], sb["floor"]
    if pa is not None and pb is not None and a.get("complete_floor_evaluable") and b.get("complete_floor_evaluable"):
        try:
            inter = pa.intersection(pb).area
            union = pa.area + pb.area - inter
            out.update(floor_jaccard_difference=1 - inter / union if union > 0 else None,
                       floor_symdiff_h2=pa.area + pb.area - 2 * inter)
            ha, hb = number(a.get("height_mean_ratio")), number(b.get("height_mean_ratio"))
            if ha is not None and hb is not None and ha > 0 and hb > 0:
                vi = inter * min(ha, hb)
                vu = pa.area * ha + pb.area * hb - vi
                out.update(mean_height_prism_pair_iou=vi / vu if vu > 0 else None,
                           height_ratio_pair_abs_logdiff=abs(math.log(ha / hb)))
        except GEOSException as error:
            out["geometry_comparison_error"] = type(error).__name__ + ":" + str(error)
    for t in (5, 9):
        for kind in ("node", "edge"):
            out[f"ref_{kind}_set_jaccard_difference_{t}"] = set_jaccard(a.get(f"ref_matched_{kind}s_{t}"), b.get(f"ref_matched_{kind}s_{t}"))
    dq = out["abs_B8L2_change"]
    for name, q, f, s in (("strict", 1., .02, 2.), ("main", 2., .05, 3.), ("wide", 5., .10, 5.)):
        out[f"joint_stable_{name}"] = bool(out["both_complete"] and dq is not None and dq <= q and
            out["node_count_difference"] == 0 and out["floor_jaccard_difference"] is not None and
            out["floor_jaccard_difference"] <= f and bound is not None and bound <= s)
    out["quality_comparable"] = dq is not None
    return out


def describe(values, prefix, stats=("mean", "median", "p10", "min", "max", "sd")):
    x = np.asarray([v for a in values if (v := number(a)) is not None], dtype=float)
    out = {prefix + "_n": int(len(x))}
    functions = {"mean": np.mean, "median": np.median, "p10": lambda z: np.quantile(z, .1),
                 "p90": lambda z: np.quantile(z, .9), "min": np.min, "max": np.max,
                 "sd": lambda z: np.std(z, ddof=1)}
    for name in stats:
        fn = functions[name]
        out[prefix + "_" + name] = float(fn(x)) if len(x) and (name != "sd" or len(x) > 1) else None
    return out


def make_cell(requests, teams, signatures, meta, ledger, pair_sink, seen_pairs):
    first = requests[0]
    by_team = collections.defaultdict(list)
    for request in requests:
        by_team[request["team_key"]].append(request)
    present = {key: teams[key] for key in by_team if key in teams}
    rows = list(present.values())
    cell = dict(phase=first["phase"], method_id=first["method_id"], domain=first["domain"],
                **{k: meta.get(k) for k in META}, k=first["k"], composition=first["composition"],
                active_classes=sum(n > 0 for n in first["counts"].values()),
                counts_json=compact_json(first["counts"]), request_n=len(requests), requested_unique_team_n=len(by_team),
                unique_team_n=len(rows), missing_computation_n=len(by_team) - len(rows),
                duplicate_same_member_requests=len(requests) - len(by_team),
                complete_n=sum(bool(r.get("complete_evaluable")) for r in rows),
                complete_floor_n=sum(bool(r.get("complete_floor_evaluable")) for r in rows),
                score_available_n=sum(number(r.get("B8L2")) is not None for r in rows),
                score_missing_n=sum(number(r.get("B8L2")) is None for r in rows),
                fusion_exception_n=sum(r.get("score_status") == "fusion_exception" for r in rows),
                measurement_exception_n=sum(r.get("score_status") == "measurement_exception" for r in rows),
                source_time_complete_n=sum(number(r.get("source_time_total_seconds")) is not None for r in rows),
                target_time_complete_n=sum(number(r.get("target_time_total_seconds")) is not None for r in rows),
                score_status_counts=compact_json(dict(collections.Counter(str(r.get("score_status")) for r in rows))),
                geometry_reason_counts=compact_json(dict(collections.Counter(str(r.get("geometry_reason")) for r in rows))),
                diagnostic_status_counts=compact_json(dict(collections.Counter(str(signatures[r["team_key"]].get("diag_status")) for r in rows))),
                distinct_workers_n=len(set().union(*(set(r["member_workers"]) for r in rows))) if rows else 0,
                team_keys=compact_json(sorted(present)))
    cell["complete_rate"] = cell["complete_n"] / len(rows) if rows else None
    cell["score_available_rate"] = cell["score_available_n"] / len(rows) if rows else None
    for key in ("possible_member_teams", "sampled_member_teams", "exhaustive_members", "feasible_compositions", "selected_compositions", "exhaustive_compositions"):
        cell[key] = ledger.get(key)
    for metric in SCORE_METRICS:
        values = [signatures[r["team_key"]].get(metric) if metric in ("candidate_pair_count", "floor_area_camera_h2") + DIAG_METRICS else r.get(metric) for r in rows]
        statistics = ("mean", "median", "p10", "min", "max", "sd") if metric in ("B8L2", "D10") else ("mean", "min", "max")
        cell.update(describe(values, metric, statistics))
    cell["B8L2_worst"] = cell["B8L2_min"]
    cell["D10_worst"] = cell["D10_min"]
    for threshold in (5, 9):
        for kind in ("nodes", "edges"):
            lists = [r.get(f"ref_matched_{kind}_{threshold}") for r in rows]
            sets = [set(v) for v in lists if v is not None]
            prefix = f"ref_matched_{kind}_{threshold}"
            cell[prefix + "_known_teams"] = len(sets)
            cell[prefix + "_union_n"] = len(set.union(*sets)) if sets else None
            cell[prefix + "_intersection_n"] = len(set.intersection(*sets)) if sets else None
            cell[prefix + "_pattern_counts"] = compact_json(dict(collections.Counter(compact_json(v) for v in lists if v is not None)))
    pair_rows = []
    for ka, kb in itertools.combinations(sorted(present), 2):
        a, b = present[ka], present[kb]
        metrics = pair_metrics(a, b, signatures[ka], signatures[kb])
        assert not metrics["same_members"] and metrics["turnover"] > 0
        qa = min(by_team[ka], key=lambda x: x["request_id"])
        qb = min(by_team[kb], key=lambda x: x["request_id"])
        row = dict(phase=first["phase"], method_id=first["method_id"], domain=first["domain"],
                   pool_id=first["pool_id"], image_id=meta.get("image_id"), building=meta.get("building"),
                   difficulty=meta.get("difficulty"), k=first["k"], composition=first["composition"],
                   request_a=qa["request_id"], request_b=qb["request_id"], team_a=ka, team_b=kb,
                   replicate_a=qa["replicate"], replicate_b=qb["replicate"], **metrics)
        pair_sink.append(row)
        pair_rows.append(metrics)
        seen_pairs.add((ka, kb))
    cell["within_unique_team_pair_n"] = len(pair_rows)
    cell["within_both_complete_n"] = sum(p["both_complete"] for p in pair_rows)
    cell["within_quality_comparable_n"] = sum(p["quality_comparable"] for p in pair_rows)
    for mode in ("strict", "main", "wide"):
        cell[f"within_joint_stable_{mode}_n"] = sum(p[f"joint_stable_{mode}"] for p in pair_rows)
        cell[f"within_joint_stable_{mode}_rate"] = cell[f"within_joint_stable_{mode}_n"] / len(pair_rows) if pair_rows else None
    for metric in PAIR_METRICS:
        statistics = ("mean", "median", "p90", "max") if metric in ("abs_B8L2_change", "abs_D10_change") else ("mean", "min", "max")
        cell.update(describe([p[metric] for p in pair_rows], "within_" + metric, statistics))
    # Private data are returned to this pool's light cross-cell comparisons only.
    cell["_requests"] = requests
    cell["_counts"] = first["counts"]
    cell["_rep_rows"] = {r["replicate"]: teams[r["team_key"]] for r in requests if r["team_key"] in teams}
    return cell


def is_pure(cell):
    return cell["active_classes"] == 1


def composition_distance(a, b):
    return sum(abs(a["_counts"].get(c, 0) - b["_counts"].get(c, 0)) for c in set(a["_counts"]) | set(b["_counts"])) // 2


def selected_contrast(a, b, mode):
    if mode == "all":
        return True
    if mode == "none":
        return False
    if composition_distance(a, b) == 1:
        return True
    for pure, other in ((a, b), (b, a)):
        if is_pure(pure):
            c = next(c for c, n in pure["_counts"].items() if n)
            if other["_counts"].get(c, 0):
                return True
    return False


def compare_cells(a, b):
    """Light observed-count-vector comparison; no giant cross-team geometry table."""
    out = {k: a.get(k) for k in ("phase", "method_id", "domain", "pool_id", "image_id", "building", "difficulty", "k")}
    minimum = composition_distance(a, b)
    out.update(composition_a=a["composition"], composition_b=b["composition"], composition_turnover_minimum=minimum,
               changed_class_n=sum(a["_counts"].get(c, 0) != b["_counts"].get(c, 0) for c in set(a["_counts"]) | set(b["_counts"])),
               pure_a=is_pure(a), pure_b=is_pure(b), unique_teams_a=a["unique_team_n"], unique_teams_b=b["unique_team_n"],
               missing_computation_a=a["missing_computation_n"], missing_computation_b=b["missing_computation_n"],
               score_available_a=a["score_available_n"], score_available_b=b["score_available_n"])
    for key in ("B8L2_mean", "B8L2_p10", "B8L2_worst", "D10_mean", "complete_rate", "score_available_rate", "nodes_mean",
                "iou_2d_mean", "IoU3D100_mean", "omission_mean", "extension_mean", "ref_node_recall_5_mean", "ref_edge_recall_5_mean",
                "ref_node_recall_9_mean", "ref_edge_recall_9_mean", "new_n_mean", "source_time_total_seconds_mean",
                "diag_wall_coverage_03_mean", "diag_wall_coverage_05_mean", "diag_corner_recall_05_mean"):
        out[key + "_a"] = a[key]
        out[key + "_b"] = b[key]
        out[key + "_change"] = delta(a, b, key)
    common = sorted(set(a["_rep_rows"]) & set(b["_rep_rows"]))
    turnover, gains = [], []
    regained = lost = 0
    for rep in common:
        aa, bb = a["_rep_rows"][rep], b["_rep_rows"][rep]
        t = len(set(aa["member_workers"]) - set(bb["member_workers"]))
        assert t >= minimum, "actual replacement smaller than composition change"
        turnover.append(t)
        q = delta(aa, bb, "B8L2")
        if q is not None:
            gains.append(q)
        regained += bool(not aa.get("complete_evaluable") and bb.get("complete_evaluable"))
        lost += bool(aa.get("complete_evaluable") and not bb.get("complete_evaluable"))
    out.update(same_rep_pair_n=len(common), same_rep_scored_pair_n=len(gains),
               same_rep_B8L2_change_mean=float(np.mean(gains)) if gains else None,
               same_rep_B8L2_change_min=min(gains) if gains else None,
               same_rep_B8L2_change_max=max(gains) if gains else None,
               same_rep_actual_turnover_mean=float(np.mean(turnover)) if turnover else None,
               same_rep_minimum_turnover_n=sum(t == minimum for t in turnover),
               same_rep_complete_restored_n=regained, same_rep_complete_lost_n=lost)
    return out


def iter_cell_contrasts(cells, mode="all"):
    """Enumerate a single method/domain/pool/k's chosen count-vector pairs."""
    for a, b in itertools.combinations(sorted(cells, key=lambda x: x["composition"]), 2):
        if selected_contrast(a, b, mode):
            yield compare_cells(a, b)


def mixture_pure_comparisons(cells):
    pure = {next(c for c, n in a["_counts"].items() if n): a for a in cells if is_pure(a)}
    for mixed in cells:
        if is_pure(mixed):
            continue
        active = sorted(c for c, n in mixed["_counts"].items() if n)
        available = {c: pure[c] for c in active if c in pure and pure[c]["unique_team_n"]}
        scored = {c: p for c, p in available.items() if p["B8L2_mean"] is not None}
        out = {k: mixed.get(k) for k in ("phase", "method_id", "domain", "pool_id", "image_id", "building", "difficulty", "k", "composition")}
        best = max(scored, key=lambda c: scored[c]["B8L2_mean"]) if scored else None
        worst = min(scored, key=lambda c: scored[c]["B8L2_mean"]) if scored else None
        all_scored = len(scored) == len(active)
        weighted_q = sum(mixed["_counts"][c] / mixed["k"] * scored[c]["B8L2_mean"] for c in active) if all_scored else None
        weighted_complete = sum(mixed["_counts"][c] / mixed["k"] * available[c]["complete_rate"] for c in active) if len(available) == len(active) else None
        out.update(active_class_n=len(active), related_pure_cells_present=len(available), related_pure_cells_scored=len(scored),
                   all_active_pures_scored=all_scored, related_pure_compositions=compact_json({c: p["composition"] for c, p in available.items()}),
                   mixed_unique_teams=mixed["unique_team_n"], mixed_scored_teams=mixed["score_available_n"], mixed_missing_computations=mixed["missing_computation_n"],
                   mixed_B8L2_mean=mixed["B8L2_mean"], mixed_B8L2_p10=mixed["B8L2_p10"], mixed_B8L2_worst=mixed["B8L2_worst"],
                   mixed_complete_rate=mixed["complete_rate"], best_available_pure_class=best, worst_available_pure_class=worst,
                   best_available_pure_B8L2_mean=scored[best]["B8L2_mean"] if best else None,
                   worst_available_pure_B8L2_mean=scored[worst]["B8L2_mean"] if worst else None,
                   weighted_pure_B8L2_mean=weighted_q, weighted_pure_complete_rate=weighted_complete)
        for key in ("best_available_pure_B8L2_mean", "worst_available_pure_B8L2_mean", "weighted_pure_B8L2_mean"):
            x, y = mixed["B8L2_mean"], out[key]
            out["mixed_minus_" + key] = x - y if x is not None and y is not None else None
        out["mixed_minus_weighted_pure_complete_rate"] = mixed["complete_rate"] - weighted_complete if mixed["complete_rate"] is not None and weighted_complete is not None else None
        yield out


def summarize(args):
    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / "GRID_SUMMARY_RECEIPT.json").unlink(missing_ok=True)
    manifest = read(args.requests)
    split = read(args.split)
    phase = args.phase
    allowed_buildings = set(split[phase + "_buildings"])
    labels = labels_from_files(args.labels)
    pools = {p["pool_id"]: p for p in read(args.snapshot)["images"]}
    requests = manifest["requests"]
    assert len({r["request_id"] for r in requests}) == len(requests), "duplicate request ID"
    by_pool = collections.defaultdict(list)
    for r in requests:
        validate_request(r, labels, phase)
        if not args.pool or r["pool_id"] in args.pool:
            by_pool[r["pool_id"]].append(r)
    if args.pool:
        assert set(args.pool) <= set(by_pool), "requested pilot pool absent from manifest"
    ledger = {(r["method_id"], r["domain"], r["pool_id"], r["k"], r["composition"]): r for r in manifest.get("ledger", [])}
    outputs = {name: CsvSink(args.out / name) for name in ("cell_summary.csv.gz", "within_pairs.csv.gz", "composition_quality_directions.csv.gz", "mixture_vs_pure.csv.gz")}
    stats = dict(request_rows=0, requested_unique_teams=0, observed_unique_teams=0, missing_computations=0,
                 duplicate_same_member_requests=0, distinct_within_team_pairs=0, all_chosen_count_vector_pairs=0,
                 enumerated_quality_contrasts=0, within_pair_rows=0)
    unique_requested, unique_observed, seen_pairs, all_workers, images, buildings = set(), set(), set(), set(), set(), set()
    pool_receipts = []
    try:
        for pid in sorted(by_pool):
            pool_path = args.runs / "pools" / (pid + ".json.gz")
            if not pool_path.exists():
                raise FileNotFoundError("No computed pool cache; do not treat this as a fusion failure: " + str(pool_path))
            cache = read(pool_path)
            available = {r["team_key"]: r for r in cache["teams"]}
            assert len(available) == len(cache["teams"]), "duplicate cached team identity"
            wanted = {r["team_key"] for r in by_pool[pid]}
            teams = {k: available[k] for k in sorted(wanted & available.keys())}
            missing = wanted - available.keys()
            if missing and not args.allow_partial:
                raise RuntimeError(f"Pool {pid}: {len(missing)} requested teams not computed yet; no zero/failure substitution. First missing: {min(missing)}")
            pool = pools[pid]
            assert cache["context"]["pool_digest"] == digest(pool), "frozen pool/reference/input mismatch"
            meta = dict(pool["meta"], reference_nodes=len(pool["reference"]["points_1024x512"]) // 2)
            assert meta["pool_id"] == pid and meta["building"] in allowed_buildings, "cached pool outside authorized phase"
            assert all(t.get("reference_id") == meta.get("reference_id") and t.get("reference_version") == meta.get("reference_version") for t in teams.values())
            request_map = {r["team_key"]: r for r in by_pool[pid]}
            for key, team in teams.items():
                assert sorted(team["member_workers"]) == sorted(request_map[key]["worker_ids"])
                assert key == team_key(pid, team["member_workers"]) and team["k"] == request_map[key]["k"]
                assert len(set(team["member_object_ids"])) == len(team["member_workers"])
            diagnostic_cache = {}
            signatures = {key: signature(team, pool["reference"]["floor_xz_h"], diagnostic_cache) for key, team in teams.items()}
            groups = collections.defaultdict(list)
            for r in by_pool[pid]:
                groups[(r["method_id"], r["domain"], r["k"], r["composition"])].append(r)
            pools_cells = collections.defaultdict(list)
            for (mid, dom, k, comp), group in sorted(groups.items()):
                cell = make_cell(group, teams, signatures, meta, ledger.get((mid, dom, pid, k, comp), {}), outputs["within_pairs.csv.gz"], seen_pairs)
                outputs["cell_summary.csv.gz"].append({key: value for key, value in cell.items() if not key.startswith("_")})
                pools_cells[(mid, dom, k)].append(cell)
                stats["duplicate_same_member_requests"] += cell["duplicate_same_member_requests"]
            possible, emitted = 0, 0
            for (mid, _, _), cells in sorted(pools_cells.items()):
                possible += len(cells) * (len(cells) - 1) // 2
                mode = args.contrasts if not args.contrast_method or mid in args.contrast_method else "none"
                for contrast in iter_cell_contrasts(cells, mode=mode):
                    outputs["composition_quality_directions.csv.gz"].append(contrast)
                    emitted += 1
                for mixed in mixture_pure_comparisons(cells):
                    outputs["mixture_vs_pure.csv.gz"].append(mixed)
            stats["request_rows"] += len(by_pool[pid])
            stats["missing_computations"] += len(missing)
            stats["all_chosen_count_vector_pairs"] += possible
            stats["enumerated_quality_contrasts"] += emitted
            unique_requested.update(wanted)
            unique_observed.update(teams)
            all_workers.update(w for r in by_pool[pid] for w in r["worker_ids"])
            images.add(meta["image_id"])
            buildings.add(meta["building"])
            receipt = dict(pool_id=pid, requested_teams=len(wanted), observed_teams=len(teams), missing_teams=len(missing),
                           cell_n=len(groups), selected_count_vector_pairs=possible, quality_contrasts=emitted,
                           unique_diagnostic_geometries=len(diagnostic_cache),
                           pool_context=cache["context"])
            pool_receipts.append(receipt)
            for sink in outputs.values():
                sink.checkpoint()
            print(compact_json({k: v for k, v in receipt.items() if k != "pool_context"}), flush=True)
        for sink in outputs.values():
            sink.close()
    except BaseException:
        for sink in outputs.values():
            sink.abort()
        raise
    stats.update(requested_unique_teams=len(unique_requested), observed_unique_teams=len(unique_observed),
                 distinct_within_team_pairs=len(seen_pairs), within_pair_rows=outputs["within_pairs.csv.gz"].rows)
    receipt = dict(schema="personnel_composition_grid_summary_v1", phase=phase, **stats,
                   cells=outputs["cell_summary.csv.gz"].rows, pools=len(by_pool), images=len(images), buildings=len(buildings), workers=len(all_workers),
                   metadata_images=sorted(images), metadata_buildings=sorted(buildings), pool_filter=args.pool or [],
                   complete_requested_run=not bool(stats["missing_computations"]), full_manifest_pool_coverage=not bool(args.pool),
                   exact_members_and_compositions_rebuilt=True, repeated_identical_members_excluded_from_within_pairs=True,
                   all_output_gzip_crc_and_csv_record_counts_verified=True,
                   joint_stability_main=MAIN_TOLERANCES, missing_quality="None retained; Q summaries condition on finite scores and keep all attempt/failure counts",
                   missing_computation_policy="Absent requested teams are not computed failures; strict default aborts, optional partial mode counts them separately",
                   distance_definition="Archived bound cyclic maximum spherical endpoint distance, no reverse ring, inherited +0.5 vertical coordinate convention",
                   prism_definition="Same-reference mean-height prism pair IoU using final valid footprint and height_mean_ratio; common reference height cancels. Not full-room volume IoU.",
                   reference_match_definition="Fixed 5/9 degree Hungarian node match and undirected reference adjacency diagnostics; not necessary-structure correctness or new quality score",
                   geometric_diagnostic_schema=DIAGNOSTIC_SCHEMA,
                   geometric_diagnostic_definition="Fixed reference wall-length coverage at .03/.05 sqrt(reference area), direction tolerance 10 degrees; corner location recall at .05 sqrt(reference area), eligible turns above 10 degrees. Separate diagnostics, not necessary-structure correctness.",
                   contrast_mode=args.contrasts, contrast_method_filter=args.contrast_method or [],
                   omitted_chosen_count_vector_pairs=stats["all_chosen_count_vector_pairs"] - stats["enumerated_quality_contrasts"],
                   contrast_sampling="All chosen count-vector pairs considered; default emits all composition-distance-one pairs plus pure-versus-mixture pairs containing that pure class. --contrasts all emits every chosen-vector pair.",
                   replicate_pairing="Same requested replicate ID may not share original RNG draw after duplicate rejection or exhaustive small-cell enumeration; actual turnover is always measured and minimum-turnover support recorded",
                   interpretation="Cells/teams/pairs share workers and images; they are not independent image or building samples",
                   input_hashes={str(p): sha(p) for p in [args.requests, args.split, args.snapshot] + list(args.labels)},
                   geometry_diagnostics_source_sha256=sha(Path(__file__).with_name("geometry_diagnostics.py")),
                   source_code_sha256=sha(Path(__file__)), outputs={name: dict(rows=sink.rows, bytes=sink.path.stat().st_size, sha256=sha(sink.path)) for name, sink in outputs.items()},
                   by_pool=pool_receipts)
    write(args.out / "GRID_SUMMARY_RECEIPT.json", receipt)
    print(compact_json({k: v for k, v in receipt.items() if k in ("phase", "request_rows", "requested_unique_teams", "observed_unique_teams", "missing_computations", "cells", "within_pair_rows", "pools", "images", "buildings", "enumerated_quality_contrasts")}))
    return receipt


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--requests", type=Path, required=True)
    ap.add_argument("--runs", type=Path, required=True)
    ap.add_argument("--labels", type=Path, action="append", required=True)
    ap.add_argument("--split", type=Path, required=True)
    ap.add_argument("--snapshot", type=Path, required=True, help="Frozen input/reference snapshot; values are verified against each computation context")
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--phase", choices=("discovery", "validation"), default="discovery")
    ap.add_argument("--pool", action="append", help="Explicit completed-pool pilot filter")
    ap.add_argument("--allow-partial", action="store_true", help="Count uncomputed requests separately; never label them fusion failures")
    ap.add_argument("--contrasts", choices=("none", "pure_adjacent", "all"), default="pure_adjacent")
    ap.add_argument("--contrast-method", action="append", help="Optional method filter for quality direction enumeration")
    summarize(ap.parse_args())


if __name__ == "__main__":
    main()
