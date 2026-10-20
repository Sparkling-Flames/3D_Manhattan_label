#!/usr/bin/env python3
"""Learn personnel partitions from historical *actual fusion replacements*.

No discovery/validation outcomes are loaded.  The ten history buildings are
split into five fixed two-building inner folds.  Original continuous distances
stay missing on failure; separately declared losses can penalize failed attempts.
"""
from __future__ import annotations

import argparse
import hashlib
import gzip
import itertools
import json
import math
import os
from pathlib import Path
import time

os.environ.setdefault("OMP_NUM_THREADS", "1")
os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")
os.environ.setdefault("MKL_NUM_THREADS", "1")

import numpy as np
import pandas as pd
from scipy.cluster.hierarchy import cut_tree, linkage
from scipy.spatial.distance import squareform
from sklearn.cluster import KMeans

SEED = 2026102003
OLD_PANEL = "Pro_exact_fixed_background_v1"
NESTED_PANEL = "A_nested_even_v1"
DOMAINS = ("ordinary", "hard", "small_n", "large_n", "ordinary_new", "hard_new", "hard_v1")
REPRESENTATIONS = ("joint", "geometry", "continuous", "context_joint")
ALGORITHMS = ("complete", "spectral", "partition_b0", "partition_b2")
MIN_CLASS = 4
PRIOR_BUILDINGS = 1.0
PAIR_MIN_IMAGES = 3
PAIR_MIN_BUILDINGS = 2
WORKER_MIN_IMAGES = 4
WORKER_MIN_BUILDINGS = 3

READ_COLUMNS = [
    "event_id", "panel_id", "pool_id", "image", "image_id", "building",
    "difficulty", "condition", "layer", "reference_id", "reference_version",
    "k", "background_id", "background_members", "worker_a", "worker_b",
    "request_a", "request_b", "team_id_a", "team_id_b", "member_workers_a",
    "member_workers_b", "entrant_origin_a", "entrant_origin_b", "both_complete",
    "quality_comparable", "B8L2_a", "B8L2_b", "D10_a", "D10_b",
    "abs_B8L2_change", "abs_D10_change", "joint_stable_main",
    "joint_stable_strict", "joint_stable_wide", "floor_jaccard_difference",
    "structure_bound_cyclic_deg", "node_count_difference", "nodes_a", "nodes_b",
    "mean_height_prism_pair_iou", "height_ratio_pair_abs_logdiff",
    "edge_relation_jaccard_difference", "selected_shared_observation_difference",
    "complete_a", "complete_b", "source_entrant_time_a", "source_entrant_time_b",
]
SUMMARY_METRICS = [
    "stable_main", "stable_strict", "stable_wide", "stable_geometry",
    "stable_geometry_wide", "failure", "continuous_loss", "q_tail5",
    "abs_B8L2_change", "abs_D10_change", "floor_jaccard_difference",
    "structure_bound_cyclic_deg", "prism_distance", "node_different",
    "height_ratio_pair_abs_logdiff", "context_bad", "mean_endpoint_Q",
]


def sha(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def write_json(path, value):
    Path(path).write_text(json.dumps(value, ensure_ascii=False, indent=2,
                                   allow_nan=False) + "\n", encoding="utf-8")


def write_csv(path, frame):
    path = Path(path)
    raw = frame.to_csv(index=False).encode("utf-8")
    if path.name.endswith(".gz"):
        content = gzip.compress(raw, compresslevel=6, mtime=0)
        assert gzip.decompress(content) == raw
    else:
        content = raw
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_bytes(content)
    temporary.replace(path)


def clean(value):
    if isinstance(value, dict):
        return {str(k): clean(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [clean(v) for v in value]
    if isinstance(value, np.ndarray):
        return clean(value.tolist())
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating, float)):
        return float(value) if np.isfinite(value) else None
    if isinstance(value, np.bool_):
        return bool(value)
    return value


def canonical(labels):
    groups = sorted(set(labels), key=lambda c: tuple(np.flatnonzero(labels == c)))
    return np.array([{c: i for i, c in enumerate(groups)}[c] for c in labels], int)


def domain_mask(frame, domain):
    if domain.endswith("_new") or domain.endswith("_v1"):
        base, origin = domain.rsplit("_", 1)
        return (domain_mask(frame, base) & frame.entrant_origin_a.eq(origin).to_numpy()
                & frame.entrant_origin_b.eq(origin).to_numpy())
    if domain == "ordinary":
        return np.ones(len(frame), bool)
    if domain == "hard":
        return frame.difficulty.eq("困难").to_numpy()
    if domain == "small_n":
        return frame.k.le(12).to_numpy()
    if domain == "large_n":
        return frame.k.ge(16).to_numpy()
    raise ValueError(domain)


def bool_column(frame, name):
    if frame[name].dtype == bool:
        return frame[name].to_numpy()
    vals = frame[name].astype(str)
    assert vals.isin(["True", "False"]).all(), name
    return vals.eq("True").to_numpy()


def load_history(root: Path, supplemental=None):
    split_path = root / "analysis/composition/SPLIT.json"
    split = json.loads(split_path.read_text())
    history = set(split["history_buildings"])
    old = root / "restored/work_personnel_typing_A_20261019/events"
    paths = [p for p in sorted((old / "comparisons").glob("*/events.csv.gz"))
             if p.parent.name.split("-", 1)[0] in history]
    rows = []
    for p in paths:
        f = pd.read_csv(p, usecols=READ_COLUMNS)
        assert set(f.building).issubset(history), p
        rows.append(f)
    extra_receipt = None
    if supplemental is not None:
        supplemental = Path(supplemental)
        extra = pd.read_csv(supplemental, usecols=READ_COLUMNS)
        assert set(extra.building).issubset(history)
        assert set(extra.panel_id) == {"H20_metadata_allentrant_v1"}
        assert extra.entrant_origin_a.isin(["new", "v1"]).all()
        rows.append(extra)
        extra_receipt = {"path": str(supplemental), "sha256": sha(supplemental), "events": len(extra)}
    frame = pd.concat(rows, ignore_index=True)
    assert frame.event_id.is_unique
    assert frame.layer.eq("ordinary_manual").all()
    assert frame.condition.eq("manual").all()
    assert (frame.worker_a < frame.worker_b).all()
    for name in ["both_complete", "quality_comparable", "complete_a", "complete_b"]:
        frame[name] = bool_column(frame, name)
    q = frame.abs_B8L2_change.to_numpy(float)
    floor = frame.floor_jaccard_difference.to_numpy(float)
    angle = frame.structure_bound_cyclic_deg.to_numpy(float)
    complete = frame.both_complete.to_numpy(bool)
    nodes_equal = frame.node_count_difference.eq(0).to_numpy()
    for level, q_cut, floor_cut, angle_cut in [
        ("strict", 1, .02, 2), ("main", 2, .05, 3), ("wide", 5, .1, 5)
    ]:
        expected = complete & (q <= q_cut) & (floor <= floor_cut) & nodes_equal & (angle <= angle_cut)
        assert np.array_equal(expected, bool_column(frame, "joint_stable_" + level))
        frame["stable_" + level] = expected.astype(float)
    frame["stable_geometry"] = (complete & (floor <= .05) & nodes_equal & (angle <= 3)).astype(float)
    frame["stable_geometry_wide"] = (complete & (floor <= .1) & nodes_equal & (angle <= 5)).astype(float)
    frame["failure"] = (~complete).astype(float)
    frame["prism_distance"] = 1 - frame.mean_height_prism_pair_iou
    # Original floor/prism distances remain missing.  A separately named loss
    # gives unavailable/incomplete outputs unit cost, rather than inventing IoU.
    valid = complete & np.isfinite(floor) & np.isfinite(frame.prism_distance)
    continuous = .5 * np.clip(floor / .1, 0, 1) + .5 * np.clip(frame.prism_distance / .1, 0, 1)
    frame["continuous_loss"] = np.where(valid, continuous, 1.0)
    frame["q_tail5"] = np.where(frame.quality_comparable, q > 5, np.nan)
    frame["node_different"] = np.where(complete, ~nodes_equal, np.nan)
    frame["mean_endpoint_Q"] = np.where(frame.quality_comparable, (frame.B8L2_a + frame.B8L2_b) / 2, np.nan)
    assert np.nanmax(np.abs(np.abs(frame.B8L2_b - frame.B8L2_a) - q)) < 1e-8
    # Every background belongs to one building; this adjustment never borrows
    # outcomes across an inner fold boundary.
    bgkeys = ["panel_id", "pool_id", "k", "background_id"]
    base = frame.groupby(bgkeys, observed=True).stable_main.transform("mean")
    frame["context_bad"] = .5 + ((1 - frame.stable_main) - (1 - base))
    receipt = {
        "history_buildings": sorted(history), "split_sha256": sha(split_path),
        "loaded_pool_files": [{"path": str(p.relative_to(root)), "sha256": sha(p)} for p in paths],
        "source_design_sha256": sha(old / "DESIGN.json"),
        "source_field_contract_sha256": sha(old / "FIELD_CONTRACT.json"),
        "source_common_events_expected_sha256": json.loads((old / "EVENT_VERIFICATION_RECEIPT.json").read_text())["common_events_sha256"],
        "native_source_commit": json.loads((old / "DESIGN.json").read_text())["native_source_commit"],
        "loaded_history_events": len(frame),
        "supplemental_history_panel": extra_receipt,
        "panel_support": clean(frame.groupby("panel_id").agg(events=("event_id", "size"), images=("image", "nunique"), buildings=("building", "nunique")).to_dict("index")),
        "checks": {"history_only": True, "unique_event_ids": True,
                   "original_strict_main_wide_recomputed_exact": True,
                   "absolute_Q_differences_recomputed": True},
    }
    return frame, split, receipt


def pair_building_table(frame):
    # Equal backgrounds within pool×n, equal observed n within image, then equal
    # images within building for each person pair.  Pair opportunity stays explicit.
    keys = ["worker_a", "worker_b", "building", "pool_id", "k"]
    pn = frame.groupby(keys, observed=True)[SUMMARY_METRICS].mean().reset_index()
    image = pn.groupby(keys[:-1], observed=True)[SUMMARY_METRICS].mean().reset_index()
    pb = image.groupby(["worker_a", "worker_b", "building"], observed=True)[SUMMARY_METRICS].mean().reset_index()
    counts = frame.groupby(["worker_a", "worker_b", "building"], observed=True).agg(
        events=("event_id", "size"), images=("pool_id", "nunique"),
        backgrounds=("background_id", "nunique"), n_values=("k", "nunique"),
    ).reset_index()
    return pb.merge(counts, on=["worker_a", "worker_b", "building"], validate="one_to_one")


def make_graph(frame, pb, prior=PRIOR_BUILDINGS):
    workers = pd.concat([
        frame[["worker_a", "building", "pool_id"]].rename(columns={"worker_a": "worker_id"}),
        frame[["worker_b", "building", "pool_id"]].rename(columns={"worker_b": "worker_id"}),
    ]).groupby("worker_id").agg(buildings=("building", "nunique"), images=("pool_id", "nunique"))
    eligible = sorted(workers.index[(workers.buildings >= WORKER_MIN_BUILDINGS) & (workers.images >= WORKER_MIN_IMAGES)])
    ps = pb.groupby(["worker_a", "worker_b"], observed=True)[SUMMARY_METRICS].mean()
    count = pb.groupby(["worker_a", "worker_b"], observed=True).agg(
        buildings=("building", "nunique"), images=("images", "sum"),
        events=("events", "sum"), backgrounds=("backgrounds", "sum"))
    ps = ps.join(count).reset_index()
    supported = ((ps.buildings >= PAIR_MIN_BUILDINGS) & (ps.images >= PAIR_MIN_IMAGES)
                 & ps.worker_a.isin(eligible) & ps.worker_b.isin(eligible))
    ps["relation_known"] = supported
    n = len(eligible); idx = {w: i for i, w in enumerate(eligible)}
    W = np.zeros((n, n)); matrices = {}
    expressions = {"joint": ("stable_main", True), "geometry": ("stable_geometry", True),
                   "continuous": ("continuous_loss", False), "context_joint": ("context_bad", False),
                   "tail_joint": ("stable_wide", True), "tail_geometry": ("stable_geometry_wide", True)}
    for name, (metric, reverse) in expressions.items():
        values = 1 - ps[metric] if reverse else ps[metric]
        baseline = float(values[supported].mean()) if supported.any() else .5
        D = np.ones((n, n), float)  # pessimistic unknown for complete linkage only
        for j in np.flatnonzero(supported.to_numpy()):
            a, b = idx[ps.worker_a.iloc[j]], idx[ps.worker_b.iloc[j]]
            nb = float(ps.buildings.iloc[j]); value = float(values.iloc[j])
            v = np.clip((nb * value + prior * baseline) / (nb + prior), 0, 1)
            D[a, b] = D[b, a] = v
            W[a, b] = W[b, a] = min(nb / 3, 1)
        np.fill_diagonal(D, 0)
        matrices[name] = D
    return {"workers": eligible, "worker_opportunity": workers, "pairs": ps,
            "W": W, "matrices": matrices,
            "known_pair_fraction": float((W > 0).sum() / (n * (n - 1))) if n > 1 else 0}


def repair_minimum(labels, D, W, k):
    labels = labels.copy()
    for c in range(k):
        while np.count_nonzero(labels == c) < MIN_CLASS:
            sizes = np.bincount(labels, minlength=k)
            choices = np.flatnonzero(sizes[labels] > MIN_CLASS)
            if not len(choices):
                return None
            costs = []
            for i in choices:
                own = labels == labels[i]; target = labels == c
                own[i] = False
                old = np.sum(D[i, own] * W[i, own]) / max(np.sum(W[i, own]), 1e-10)
                new = np.sum(D[i, target] * W[i, target]) / max(np.sum(W[i, target]), 1e-10)
                costs.append(new - old)
            labels[choices[int(np.argmin(costs))]] = c
    return labels


def spectral_init(D, W, k, seed):
    A = W * np.exp(-D / .20)
    degree = A.sum(axis=1)
    N = A / np.sqrt(np.maximum(degree[:, None] * degree[None, :], 1e-15))
    _, eigen = np.linalg.eigh(N)
    X = eigen[:, -k:]
    X /= np.maximum(np.linalg.norm(X, axis=1, keepdims=True), 1e-15)
    labels = KMeans(n_clusters=k, n_init=5, random_state=seed).fit_predict(X)
    return repair_minimum(labels, D, W, k)


def partition_loss(labels, D, W, k):
    same = labels[:, None] == labels[None, :]
    den = W[same].sum()
    value = (W * D)[same].sum() / max(den, 1e-10)
    sizes = np.bincount(labels, minlength=k)
    return value + .03 * float(np.square(sizes / len(labels)).sum())


def optimize_partition(labels, D, W, k, max_steps=300):
    labels = labels.copy(); n = len(labels)
    WD = W * D
    onehot = np.eye(k)[labels]
    sums = WD @ onehot; weights = W @ onehot
    sizes = onehot.sum(axis=0)
    num = float(sums[np.arange(n), labels].sum() / 2)
    den = float(weights[np.arange(n), labels].sum() / 2)
    for _ in range(max_steps):
        own_sum = sums[np.arange(n), labels]
        own_weight = weights[np.arange(n), labels]
        dn = sums - own_sum[:, None]; dd = weights - own_weight[:, None]
        values = (num + dn) / np.maximum(den + dd, 1e-10)
        balance = np.square(sizes).sum() + 2 * (sizes[None, :] - sizes[labels, None] + 1)
        values += .03 * balance / n**2
        values[np.arange(n), labels] = np.inf
        values[sizes[labels] <= MIN_CLASS, :] = np.inf
        i, c = np.unravel_index(np.argmin(values), values.shape)
        current = num / max(den, 1e-10) + .03 * np.square(sizes).sum() / n**2
        if not np.isfinite(values[i, c]) or values[i, c] >= current - 1e-10:
            break
        old = labels[i]; num += dn[i, c]; den += dd[i, c]
        labels[i] = c; sizes[old] -= 1; sizes[c] += 1
        sums[:, old] -= WD[:, i]; sums[:, c] += WD[:, i]
        weights[:, old] -= W[:, i]; weights[:, c] += W[:, i]
    return canonical(labels)


def fit_labels(graph, representation, algorithm, k, seed, minimum_class_pair_coverage=0):
    n = len(graph["workers"]); W = graph["W"]
    if n < k * MIN_CLASS:
        return None, "fewer_than_4_workers_per_requested_class"
    D = graph["matrices"][representation]
    if algorithm == "complete":
        labels = cut_tree(linkage(squareform(D, checks=False), method="complete"), n_clusters=[k])[:, 0]
        if np.bincount(labels).min() < MIN_CLASS:
            return None, "complete_linkage_created_small_class"
    elif algorithm == "spectral":
        labels = spectral_init(D, W, k, seed)
    else:
        beta = int(algorithm.rsplit("b", 1)[-1])
        tail_name = "tail_geometry" if representation in ["geometry", "continuous"] else "tail_joint"
        augmented = (D + beta * np.square(graph["matrices"][tail_name])) / (1 + beta)
        first = spectral_init(augmented, W, k, seed)
        rng = np.random.default_rng(seed)
        second = np.arange(n) % k; rng.shuffle(second)
        alternatives = [optimize_partition(first, augmented, W, k),
                        optimize_partition(second, augmented, W, k)]
        labels = min(alternatives, key=lambda a: partition_loss(a, augmented, W, k))
    if labels is None:
        return None, "minimum_size_repair_failed"
    labels = canonical(labels)
    assert len(set(labels)) == k and np.bincount(labels).min() >= MIN_CLASS
    internal = W[labels[:, None] == labels[None, :]]
    possible = sum(s * (s - 1) for s in np.bincount(labels))
    fraction = float((internal > 0).sum() / possible)
    if fraction < .75:
        return None, "within_relation_known_fraction_below_0.75"
    for c in range(k):
        ids = np.flatnonzero(labels == c)
        fraction_c = float((W[np.ix_(ids, ids)] > 0).sum() / (len(ids) * (len(ids) - 1)))
        if fraction_c < minimum_class_pair_coverage:
            return None, "individual_class_relation_coverage_below_gate"
    return labels, "ok"


def evaluate(frame, workers, labels):
    mapper = {w: int(c) for w, c in zip(workers, labels)}
    ca = frame.worker_a.map(mapper); cb = frame.worker_b.map(mapper)
    known = ca.notna() & cb.notna()
    d = frame.loc[known].copy()
    if not len(d):
        return pd.DataFrame(), {}
    d["same"] = (ca[known].to_numpy() == cb[known].to_numpy())
    # Exact common-background comparisons, each background contributes only when
    # the frozen labels support both within and between person pairs.
    keys = ["building", "pool_id", "k", "background_id", "same"]
    bg = d.groupby(keys, observed=True)[SUMMARY_METRICS].mean().reset_index()
    nc = d.groupby(keys, observed=True).agg(events=("event_id", "size"), unique_pairs=("worker_a", "size")).reset_index()
    bg = bg.merge(nc, on=keys)
    support = bg.groupby(keys[:-1], observed=True).same.nunique()
    common_keys = set(support[support == 2].index)
    mask = [tuple(v) in common_keys for v in bg[keys[:-1]].itertuples(index=False, name=None)]
    matched = bg.loc[mask]
    if not len(matched):
        return pd.DataFrame(), {"known_events": len(d), "matched_backgrounds": 0}
    pn = matched.groupby(["building", "pool_id", "k", "same"], observed=True)[SUMMARY_METRICS].mean().reset_index()
    pi = pn.groupby(["building", "pool_id", "same"], observed=True)[SUMMARY_METRICS].mean().reset_index()
    pb = pi.groupby(["building", "same"], observed=True)[SUMMARY_METRICS].mean().unstack("same")
    rows = []
    for building in pb.index:
        row = {"building": building}
        for metric in SUMMARY_METRICS:
            row["within_" + metric] = pb.loc[building, (metric, True)]
            row["between_" + metric] = pb.loc[building, (metric, False)]
        row["gap_main"] = row["within_stable_main"] - row["between_stable_main"]
        row["gap_geometry"] = row["within_stable_geometry"] - row["between_stable_geometry"]
        row["gap_continuous"] = row["between_continuous_loss"] - row["within_continuous_loss"]
        row["within_bad_wide"] = 1 - row["within_stable_wide"]
        # Declared selection aid, not a replacement for separate outcomes.
        row["selection_score"] = (row["gap_main"] + .5 * row["gap_geometry"]
                                  + .25 * row["gap_continuous"] - .5 * row["within_bad_wide"]
                                  - .1 * row["within_failure"])
        bd = matched[matched.building == building]
        row["images"] = bd.pool_id.nunique()
        row["matched_backgrounds"] = len(bd) // 2
        row["within_events"] = int(bd.loc[bd.same, "events"].sum())
        row["between_events"] = int(bd.loc[~bd.same, "events"].sum())
        rows.append(row)
    return pd.DataFrame(rows), {
        "known_events": len(d), "known_event_fraction": len(d) / len(frame),
        "matched_backgrounds": len(matched) // 2,
        "matched_images": matched.pool_id.nunique(),
        "matched_buildings": matched.building.nunique(),
        "within_events": int(matched.loc[matched.same, "events"].sum()),
        "between_events": int(matched.loc[~matched.same, "events"].sum()),
    }


def make_inner_folds(history):
    # Pure building-ID hash, fixed before evaluating any replacement outcome.
    order = sorted(history, key=lambda b: hashlib.sha256(f"{SEED}|inner|{b}".encode()).hexdigest())
    return [sorted(order[i:i + 2]) for i in range(0, len(order), 2)]


def method_id(domain, representation, algorithm, k):
    return f"R_directswap_{representation}_{algorithm}_K{k}__{domain}"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--out", type=Path, default=Path("interchangeability_20261020/reverse"))
    parser.add_argument("--domains", nargs="*", default=list(DOMAINS))
    parser.add_argument("--pilot", action="store_true")
    parser.add_argument("--supplemental-events", type=Path)
    parser.add_argument("--input-tag", default="")
    parser.add_argument("--minimum-class-pair-coverage", type=float, default=0)
    args = parser.parse_args(); root = args.root.resolve(); out = args.out
    out.mkdir(parents=True, exist_ok=True)
    source_script_sha256 = sha(Path(__file__))
    frame, split, source_receipt = load_history(root, args.supplemental_events)
    learning_panels = [OLD_PANEL] + (["H20_metadata_allentrant_v1"] if args.supplemental_events else [])
    old = frame[frame.panel_id.isin(learning_panels)].copy()
    folds = make_inner_folds(split["history_buildings"])
    registration = {
        "schema": "direct_replacement_risk_personnel_types_v1", "seed": SEED,
        "latest_document_main": "445686f8f3cf6039c4ce1f60016cad1d26829044",
        "scientific_source_commit": "82c6164b0d4630de5316199c92aa405930973168",
        "history_buildings": split["history_buildings"], "inner_heldout_buildings": folds,
        "source_panels_for_learning": learning_panels,
        "input_tag": args.input_tag,
        "not_used_for_class_learning_or_selection": [NESTED_PANEL, "discovery buildings", "validation buildings", "followup 451 events"],
        "domains": {"ordinary": "ordinary Manual all existing difficulties and all observed n; exact n values recorded per method",
                    "hard": "ordinary Manual difficulty==困难; review-based conditional domain",
                    "small_n": "ordinary Manual trained on n<=12; exact observed n values recorded per method",
                    "large_n": "ordinary Manual trained on n>=16 (observed 16/24 without supplementary panel)",
                    "ordinary_new": "ordinary Manual; both replaceable entrants are new-source; source-external workers may only be fixed background",
                    "hard_new": "difficulty==困难 and both entrants new-source; external workers fixed background only",
                    "hard_v1": "difficulty==困难 and both entrants old v1 source; external workers fixed background only"},
        "candidate_K": "Every integer 2..floor(number_of_supported_workers/4), recomputed in every training fold; no fixed upper cap.",
        "algorithms": list(ALGORITHMS), "representations": list(REPRESENTATIONS),
        "opportunity": {"worker_min_buildings": WORKER_MIN_BUILDINGS, "worker_min_images": WORKER_MIN_IMAGES,
                        "pair_min_buildings": PAIR_MIN_BUILDINGS, "pair_min_images": PAIR_MIN_IMAGES,
                        "minimum_class_size": MIN_CLASS, "within_known_pair_fraction_min": .75,
                        "each_class_known_pair_fraction_min": args.minimum_class_pair_coverage},
        "shrinkage": {"prior_equivalent_buildings": PRIOR_BUILDINGS, "center": "training-domain supported-pair mean only",
                      "unknown": "never zero distance; zero graph affinity and zero estimation weight; complete linkage uses pessimistic unit distance"},
        "risk_expressions": {"joint": "1-P(original joint_main)", "geometry": "1-P(both complete, floor<=.05, same nodes, bound angle<=3deg); no Q cutoff",
                             "continuous": "mean(.5*clip(floor_distance/.1,0,1)+.5*clip(prism_distance/.1,0,1)); unavailable/incomplete attempt gets declared loss1, original distances remain missing",
                             "context_joint": "clip(.5+mean(event joint failure minus same-background failure baseline),0,1)"},
        "partition_loss": "Known-relation weighted within distance mean + .03*sum(class fraction squared); beta2 augments distance by 2*(wide-tail risk)^2, divided by3. Minimum class4; two fixed starts; max300 improving single-person moves.",
        "selection": "Inner heldout same n/background within-versus-between comparisons; each background contributes only if both relations exist; equal n within image and equal images within building, then building equal. All scores/components/support retained.",
        "selection_score": "gap_main + .5*gap_geometry + .25*gap_continuous - .5*within_bad_wide - .1*within_geometry_failure; an aid, not the sole claim or quality/efficiency score.",
        "failures": "Joint stability false on incomplete/unscored attempts; original continuous/quality fields stay missing; finite denominators separate.",
        "timing_semantics": "time is used only for post-fit explanation, not risk formation; source/target time not conflated",
        "created_before_candidate_fitting": True,
    }
    write_json(out / "REGISTRATION.json", registration)
    write_json(out / "INPUT_AUDIT.json", clean(source_receipt))
    cvrows = []; foldledger = []; labelrows = []; manifests = {}; relations = []
    roster = sorted(set(frame.worker_a) | set(frame.worker_b))
    t0 = time.perf_counter()
    for domain in args.domains:
        data = old.loc[domain_mask(old, domain)].copy()
        full_pb = pair_building_table(data)
        full_graph = make_graph(data, full_pb)
        relation = full_graph["pairs"].copy(); relation.insert(0, "domain", domain); relations.append(relation)
        full_kmax = len(full_graph["workers"]) // MIN_CLASS
        candidates = [(rep, algo, k) for rep in REPRESENTATIONS for algo in ALGORITHMS for k in range(2, full_kmax + 1)]
        if args.pilot:
            candidates = [(rep, algo, k) for rep, algo, k in candidates if rep == "joint" and k in [2, 4, 8]]
        print(json.dumps({"domain": domain, "events": len(data), "eligible_workers": len(full_graph["workers"]),
                          "known_pair_fraction": full_graph["known_pair_fraction"], "candidates": len(candidates)}), flush=True)
        # One graph per inner fold, shared by all candidates; no heldout outcomes
        # enter graph risk, priors, eligibility, or class-size choice.
        fold_graphs = []
        for fi, test_buildings in enumerate(folds):
            train = data[~data.building.isin(test_buildings)]
            train_pb = full_pb[~full_pb.building.isin(test_buildings)]
            test = data[data.building.isin(test_buildings)]
            fold_graphs.append((fi, make_graph(train, train_pb), test))
        for ci, (rep, algo, k) in enumerate(candidates):
            mid = method_id(domain, rep, algo, k) + ("__" + args.input_tag if args.input_tag else "")
            for fi, graph, test in fold_graphs:
                labels, status = fit_labels(graph, rep, algo, k, SEED + fi * 1000 + k, args.minimum_class_pair_coverage)
                info = {"method_id": mid, "domain": domain, "fold": fi, "status": status,
                        "training_workers": len(graph["workers"]), "test_events": len(test),
                        "training_pair_known_fraction": graph["known_pair_fraction"]}
                if labels is not None:
                    result, support = evaluate(test, graph["workers"], labels)
                    for r in result.to_dict("records"):
                        cvrows.append(dict(method_id=mid, domain=domain, fold=fi, **r))
                    info.update(support)
                    info["class_sizes"] = "|".join(map(str, np.bincount(labels)))
                foldledger.append(info)
            labels, status = fit_labels(full_graph, rep, algo, k, SEED + k, args.minimum_class_pair_coverage)
            mm = {"method_id": mid, "domain": domain, "representation": rep, "algorithm": algo,
                  "requested_k": k, "full_history_status": status,
                  "known_workers": len(full_graph["workers"]) if labels is not None else 0,
                  "history_images": int(data.pool_id.nunique()), "history_buildings": sorted(data.building.unique()),
                  "training_events": len(data), "training_n_values": sorted(map(int, data.k.unique())),
                  "pair_known_fraction": full_graph["known_pair_fraction"]}
            if labels is not None:
                mm["classes"] = {f"C{c+1:02d}": [w for w, cl in zip(full_graph["workers"], labels) if cl == c] for c in range(k)}
                mm["class_sizes"] = {c: len(ws) for c, ws in mm["classes"].items()}
                lookup = {w: f"C{cl+1:02d}" for w, cl in zip(full_graph["workers"], labels)}
            else:
                lookup = {}; mm["classes"] = {}; mm["class_sizes"] = {}
            for w in roster:
                labelrows.append({"worker_id": w, "method_id": mid, "domain": domain,
                                  "class_id": lookup.get(w, ""), "known": w in lookup,
                                  "reason": "history_actual_replacement_risk" if w in lookup else
                                            (status if labels is None else "insufficient_history_opportunity"),
                                  "train_key": "history_d199d7b13dccfe7e"})
            manifests[mid] = mm
            if ci % 20 == 0:
                print(json.dumps({"domain": domain, "done": ci + 1, "candidates": len(candidates),
                                  "elapsed_seconds": round(time.perf_counter() - t0, 1)}), flush=True)
        # Incremental small outputs after each domain, so no outcome-driven
        # interruption silently drops failed candidate families.
        write_csv(out / "inner_cv_building.csv.gz", pd.DataFrame(cvrows))
        write_csv(out / "candidate_fold_ledger.csv.gz", pd.DataFrame(foldledger))
        write_csv(out / "worker_labels.csv.gz", pd.DataFrame(labelrows))
        write_csv(out / "historical_pair_relations.csv.gz", pd.concat(relations, ignore_index=True))
        write_json(out / "METHOD_MANIFEST.json", clean(manifests))
    cv = pd.DataFrame(cvrows)
    numeric = [c for c in cv.select_dtypes(include="number").columns if c != "fold"]
    summary = cv.groupby(["method_id", "domain"])[numeric].mean().reset_index()
    counts = cv.groupby(["method_id", "domain"]).agg(cv_buildings=("building", "nunique"), cv_folds=("fold", "nunique"),
                                                                   cv_images=("images", "sum"), cv_within_events=("within_events", "sum"),
                                                                   cv_between_events=("between_events", "sum")).reset_index()
    summary = summary.merge(counts, on=["method_id", "domain"], validate="one_to_one")
    write_csv(out / "candidate_cv_summary.csv", summary)
    write_json(out / "RUN_RECEIPT.json", clean({"candidate_count": len(manifests), "fold_records": len(foldledger),
               "cv_building_records": len(cvrows), "elapsed_seconds": time.perf_counter() - t0,
               "worker_labels_sha256": sha(out / "worker_labels.csv.gz"),
               "input_audit_sha256": sha(out / "INPUT_AUDIT.json"), "registration_sha256": sha(out / "REGISTRATION.json"),
               "source_script_sha256": source_script_sha256,
               "pilot": args.pilot, "no_discovery_validation_outcomes_loaded": True}))


if __name__ == "__main__":
    main()
